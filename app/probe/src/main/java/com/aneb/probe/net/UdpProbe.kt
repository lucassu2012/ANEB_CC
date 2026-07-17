package com.aneb.probe.net

import android.net.Network
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.SocketTimeoutException
import java.util.concurrent.atomic.AtomicLong
import kotlin.math.abs

/**
 * UDP ANEB1 应用探针 wire 编解码（纯 JVM，可脱 Android 单测）。
 *
 * 服务端合同（实测锚定，TEST_SERVER_CAPABILITIES 口径）：E-01 `120.79.148.0:8443/UDP`
 * 与 HTTP/3 共端口按魔数分流；对以 ASCII `ANEB1`（5 字节）开头且总长 >5 的 UDP 包
 * **整包原样回显**，裸 5 字节 magic 无回复。服务端不解析布局——seq/时戳布局由客户端
 * 自定，回显后自行对账。
 *
 * 客户端自定布局（17B）：`ANEB1`(5B ASCII) + u32 seq BE(4B) + u64 tsNanos BE(8B)。
 */
object UdpWire {

    /** ASCII 魔数 `ANEB1`（服务端按此分流；裸 magic 无回复，故探针包必须带 payload）。 */
    val MAGIC: ByteArray = byteArrayOf(0x41, 0x4E, 0x45, 0x42, 0x31) // "ANEB1"

    /** 探针包总长：magic 5B + u32 seq 4B + u64 tsNanos 8B。 */
    const val PACKET_BYTES = 17

    /** 编码探针包：`ANEB1` + u32 seq（大端）+ u64 tsNanos（大端）= 17 字节。 */
    fun encode(seq: Int, tsNanos: Long): ByteArray {
        val b = ByteArray(PACKET_BYTES)
        MAGIC.copyInto(b, 0)
        b[5] = (seq ushr 24).toByte()
        b[6] = (seq ushr 16).toByte()
        b[7] = (seq ushr 8).toByte()
        b[8] = seq.toByte()
        for (i in 0 until 8) {
            b[9 + i] = (tsNanos ushr (56 - 8 * i)).toByte()
        }
        return b
    }

    /**
     * 解码回显包 → (seq, tsNanos)。magic 校验失败或长度不足 [PACKET_BYTES] → null
     * （R-10：坏包绝不折成任何数值样本）。服务端整包原样回显，超长尾部字节忽略。
     */
    fun decode(bytes: ByteArray): Pair<Int, Long>? {
        if (bytes.size < PACKET_BYTES) return null
        for (i in MAGIC.indices) {
            if (bytes[i] != MAGIC[i]) return null
        }
        var seq = 0
        for (i in 5..8) seq = (seq shl 8) or (bytes[i].toInt() and 0xFF)
        var ts = 0L
        for (i in 9..16) ts = (ts shl 8) or (bytes[i].toLong() and 0xFF)
        return seq to ts
    }
}

/**
 * UDP ANEB1 应用探针：发 N 个 17B 探针包（间隔 [SEND_INTERVAL_MS]），接收线程收整包
 * 回显、按 seq 对账，得应用层"UDP 未返回率"与回显 RTT。
 *
 * 口径红线（TEST_SERVER_CAPABILITIES，Codex 维护）：
 * - **UDP 未返回率＝应用层探针未回显占比，≠IP 丢包率；现场协变量，不进任何分**；
 * - 零回包或不可达只能写"UDP 应用探针不可用"（[UdpProbeResult.unreturnedPct]=null），
 *   **不得宣称精确 IP 丢包率**（不可达≠全丢；R-10 null 绝不折 0/100）；
 * - UDP 路径不受服务端合成整形（是"未整形现场协变量"）。
 *
 * @param network 非空时 [Network.bindSocket] 绑定测量流量到指定网络（项目红线：防
 *   VPN/代理污染，R-01 同源）；null＝不绑定（AUTO 口径，与 speed 模式 HTTP 路径一致）。
 */
class UdpProbe(private val network: Network? = null) {

    /**
     * UDP 探针结果（观测协变量，不进 AQS/KPI/任何分）。
     *
     * @param unreturnedPct 未返回率（%）＝(sent−received)/sent×100。**零回包时 null 而非
     *   100**——不可达≠全丢，只能表述"UDP 应用探针不可用"（合同红线；R-10 null 绝不折 0）。
     * @param rttMedianMs 回显 RTT 中位数（发出→回显到达，单调钟）；无成功样本 null（R-10）。
     * @param rttJitterMs 回显 RTT 抖动（到达序相邻差绝对值的中位数）；样本 <2 记 null。
     * @param reordered 乱序回显数（到达时 seq 小于此前已见最大 seq 的包数）。
     */
    data class UdpProbeResult(
        val sent: Int,
        val received: Int,
        val unreturnedPct: Double?,
        val rttMedianMs: Double?,
        val rttJitterMs: Double?,
        val reordered: Int,
    )

    /**
     * 阻塞执行一轮探测（调用方置于 Dispatchers.IO；全程 ≈ N×50ms + 尾等 ≤1.5s）。
     * 发包/收包异常均吞入对账（发失败不计 sent；坏包丢弃），socket 必然关闭。
     */
    fun probe(
        host: String,
        port: Int,
        count: Int = PROBE_COUNT,
        intervalMs: Long = SEND_INTERVAL_MS,
        tailTimeoutMs: Long = TAIL_TIMEOUT_MS,
    ): UdpProbeResult {
        val socket = DatagramSocket()
        // 末包发出后再等 tailTimeoutMs 的总收尾截止；发送完成前收线程不设截止
        val deadlineNs = AtomicLong(Long.MAX_VALUE)
        val lock = Any()
        val sentAtNs = LongArray(count) { -1L } // -1＝未发出/发送失败（lock 保护）
        val echoed = BooleanArray(count)
        val rttsMs = ArrayList<Double>(count) // 到达序
        var receivedCount = 0
        var reordered = 0
        var maxSeqSeen = -1

        val rx = Thread({
            val buf = ByteArray(RECV_BUF_BYTES)
            val pkt = DatagramPacket(buf, buf.size)
            while (System.nanoTime() < deadlineNs.get()) {
                try {
                    socket.receive(pkt)
                } catch (e: SocketTimeoutException) {
                    continue // soTimeout 心跳：回头复查截止时间
                } catch (e: Exception) {
                    break // socket 已关闭/不可用：收尾
                }
                val nowNs = System.nanoTime()
                val decoded = UdpWire.decode(pkt.data.copyOf(pkt.length)) ?: continue
                val seq = decoded.first
                var allEchoed = false
                synchronized(lock) {
                    // 按 seq 对账：仅接受已发出、未重复的合法 seq（重复回显只计首个）
                    if (seq in 0 until count && !echoed[seq] && sentAtNs[seq] > 0) {
                        echoed[seq] = true
                        receivedCount++
                        if (seq < maxSeqSeen) reordered++ else maxSeqSeen = seq
                        rttsMs.add((nowNs - sentAtNs[seq]) / 1e6)
                        allEchoed = receivedCount == count
                    }
                }
                if (allEchoed) break // 全部对账完成，提前收尾
            }
        }, "aneb-udp-probe-rx").apply { isDaemon = true }

        var sent = 0
        try {
            // 项目红线：测量流量绑定指定网络（防 VPN/代理污染）；null＝AUTO 不绑定
            network?.bindSocket(socket)
            socket.soTimeout = RECV_POLL_MS
            val addr = InetAddress.getByName(host)
            rx.start()
            for (seq in 0 until count) {
                val payload = UdpWire.encode(seq, System.nanoTime())
                try {
                    synchronized(lock) { sentAtNs[seq] = System.nanoTime() }
                    socket.send(DatagramPacket(payload, payload.size, addr, port))
                    sent++
                } catch (e: Exception) {
                    synchronized(lock) { sentAtNs[seq] = -1L } // 发送失败不计 sent、不参与对账
                }
                if (seq < count - 1) Thread.sleep(intervalMs)
            }
            deadlineNs.set(System.nanoTime() + tailTimeoutMs * 1_000_000L)
            rx.join(tailTimeoutMs + RECV_POLL_MS * 2L)
        } finally {
            socket.close() // 必然关闭：也把仍阻塞在 receive 的收线程踢出
        }
        rx.join(500)

        return synchronized(lock) {
            UdpProbeResult(
                sent = sent,
                received = receivedCount,
                // 合同红线：零回包/不可达 → null（"UDP 应用探针不可用"），绝不写 100%
                unreturnedPct = if (sent == 0 || receivedCount == 0) {
                    null
                } else {
                    (sent - receivedCount) * 100.0 / sent
                },
                rttMedianMs = median(rttsMs),
                rttJitterMs = jitter(rttsMs),
                reordered = reordered,
            )
        }
    }

    private fun median(xs: List<Double>): Double? {
        if (xs.isEmpty()) return null
        val s = xs.sorted()
        val n = s.size
        return if (n % 2 == 1) s[n / 2] else (s[n / 2 - 1] + s[n / 2]) / 2.0
    }

    private fun jitter(xs: List<Double>): Double? {
        if (xs.size < 2) return null
        return median(xs.zipWithNext { a, b -> abs(b - a) })
    }

    companion object {
        /** 探针包数 N。 */
        const val PROBE_COUNT = 20

        /** 发包间隔（ms）。 */
        const val SEND_INTERVAL_MS = 50L

        /** 末包发出后的总收尾等待（ms）。 */
        const val TAIL_TIMEOUT_MS = 1500L

        /** 收包 soTimeout 心跳（ms），用于周期复查截止时间。 */
        private const val RECV_POLL_MS = 100

        /** 收包缓冲（合同回显 17B，留冗余）。 */
        private const val RECV_BUF_BYTES = 512
    }
}
