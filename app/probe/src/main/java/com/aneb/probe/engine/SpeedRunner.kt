package com.aneb.probe.engine

import com.aneb.probe.net.AnebClient
import com.aneb.probe.net.ReachabilityProbe
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.channelFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.concurrent.atomic.AtomicLong
import kotlin.math.abs

/**
 * 网络基本性能模式（SpeedTest 同款）运行器——**独立于 token 测量引擎**（[TestEngine]），
 * 与 [AbRunner] / [ContinuityRunner] 并列的一种测试模式。
 *
 * 目标：用会**随网络真实波动**的指标（上行吞吐、时延）驱动 SpeedTest 级动态仪表。
 * - **Ping 阶段**：快速 echo → 实时 RTT / 抖动（随网络波动）。
 * - **Upload 阶段**：持续上传（循环大块到 /upload，socket 发送缓冲填满后写入节奏≈真实网络
 *   上行速率），[AnebClient.uploadBurst] 逐块 onChunk → ~0.6s 滑窗算**实时上行吞吐**（波动）。
 * - **Download**：需服务端 `/download` 全速端点（未接入）→ 暂 downMbps=null（后续迭代）。
 *
 * 观测/展示口径，非 AQS/KPI；claim scope 与 token 模式独立。纯 Flow，Compose 侧 collect 驱动仪表。
 */
class SpeedRunner(private val client: AnebClient = AnebClient()) {

    enum class Phase { Ping, Upload, Done }

    data class Sample(
        val phase: Phase,
        val rttMs: Double?,
        val jitterMs: Double?,
        /** 实时上行吞吐（Mbps，~0.6s 滑窗）；无值 null */
        val upMbps: Double?,
        /** 实时下行吞吐（Mbps）；需服务端 /download，暂 null */
        val downMbps: Double?,
        /** 进度 0..1 */
        val progress: Float,
    )

    fun run(serverBase: String): Flow<Sample> = channelFlow {
        // D-25：E-01 的 sslip 主机名在电信/部分网络被 DPI 做 SNI-keyed TLS RST（Connection reset）。
        // 直接选路 bare-IP 等价基址（同节点、同物理路径、观测口径不变）绕过；非 E-01 目标保持原样。
        val raw = serverBase.trim().trimEnd('/')
        val base = ReachabilityProbe.deriveE01Pair(raw)?.second ?: raw

        // ---- Ping 阶段（~1.7s，快速 echo；实时 RTT + 抖动）----
        val rtts = ArrayList<Double>()
        val pingN = 24
        for (i in 0 until pingN) {
            val t0 = System.nanoTime()
            val r = withContext(Dispatchers.IO) { runCatching { client.echo("$base/api/v1/echo") }.getOrNull() }
            val rttMs = (System.nanoTime() - t0) / 1e6
            // 客户端往返墙钟＝网络 RTT（恒非空、随网络波动）；首个含 TCP/TLS 建连，丢弃避免偏高。
            // 不取 echo.rttUs（其依赖服务端 wire 时戳/时钟同步，speed 模式不做同步会为 null）。
            if (i > 0 && r != null && r.error == null) rtts.add(rttMs)
            send(Sample(Phase.Ping, median(rtts), jitter(rtts), null, null, i.toFloat() / pingN * 0.35f))
            delay(70)
        }
        val rttMed = median(rtts)
        val jit = jitter(rtts)

        // ---- Upload 阶段（~6s 持续上传，逐块实时测速）----
        val bytes = AtomicLong(0)
        val chunk = ByteArray(4 * 1024 * 1024) // 4MB/次循环（零填充即可，服务端不校验内容）
        val upStartNs = System.nanoTime()
        val durNs = 6_000_000_000L
        val upJob = launch(Dispatchers.IO) {
            var acc = 0L
            while (isActive && System.nanoTime() - upStartNs < durNs) {
                runCatching {
                    client.uploadBurst("$base/api/v1/upload?run=speed", chunk, chunkBytes = 65536) { total, _ ->
                        bytes.set(acc + total)
                    }
                }
                acc += chunk.size
                bytes.set(acc)
            }
        }
        val window = ArrayDeque<Pair<Long, Long>>() // (nanoTime, 累计字节)
        while (upJob.isActive) {
            val now = System.nanoTime()
            val b = bytes.get()
            window.addLast(now to b)
            while (window.size > 1 && now - window.first().first > 600_000_000L) window.removeFirst()
            val dB = b - window.first().second
            val dS = (now - window.first().first) / 1e9
            val mbps = if (window.size >= 2 && dS > 0.1) dB * 8.0 / dS / 1e6 else null
            val prog = 0.35f + ((now - upStartNs).toFloat() / durNs.toFloat()).coerceIn(0f, 1f) * 0.6f
            send(Sample(Phase.Upload, rttMed, jit, mbps, null, prog.coerceIn(0f, 0.97f)))
            delay(100)
        }
        upJob.join()
        send(Sample(Phase.Done, rttMed, jit, null, null, 1f))
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
}
