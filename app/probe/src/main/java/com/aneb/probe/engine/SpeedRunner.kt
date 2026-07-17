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
 * - **Download 阶段**：持续下载服务端 unpaced `/download?bytes=1GiB`，[AnebClient.downloadDrain]
 *   逐块 onChunk → ~0.6s 滑窗算**实时下行吞吐**；读到即真实到达字节（比上行更纯净）。
 * - **Upload 阶段**：持续上传（循环大块到 /upload，socket 发送缓冲填满后写入节奏≈真实网络
 *   上行速率），[AnebClient.uploadBurst] 逐块 onChunk → ~0.6s 滑窗算**实时上行吞吐**（波动）。
 *
 * 观测/展示口径，非 AQS/KPI；claim scope 与 token 模式独立。纯 Flow，Compose 侧 collect 驱动仪表。
 */
class SpeedRunner(private val client: AnebClient = AnebClient()) {

    enum class Phase { Ping, Download, Upload, Done }

    private companion object {
        /** 下行请求字节数 = 服务端 /download 上限 1GiB（正常网络 6s 内下不完，全程流式）。 */
        const val DOWNLOAD_BYTES = 1L shl 30

        /** 整形下行请求字节数 = 8MiB 有界 Content-Length（整形 3Mbps 下 6s 窗口内下不完，全程流式）。 */
        const val SHAPED_DOWNLOAD_BYTES = 8L shl 20

        /** 整形 Ping 阶段 echo 次数（每请求附加 RTT ~120ms，12 次约 2.5s）。 */
        const val SHAPED_PING_N = 12
    }

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
        /** 应用层请求失败数（非 2xx/IO 错误；facet2 FAIL 观测口径，主动取消不计） */
        val reqFailed: Int = 0,
        /** 应用层请求总数 */
        val reqTotal: Int = 0,
        /** 合成整形口径标记（weak-capacity-latency-v1，D-43）：true＝样本来自 [runShaped] 的
         * 服务端逐 run 隔离整形路径，展示必须标注"合成"，**绝不与正常 [run] 的样本/结论合并**。 */
        val shaped: Boolean = false,
    )

    fun run(serverBase: String): Flow<Sample> = channelFlow {
        // D-25：E-01 的 sslip 主机名在电信/部分网络被 DPI 做 SNI-keyed TLS RST（Connection reset）。
        // 直接选路 bare-IP 等价基址（同节点、同物理路径、观测口径不变）绕过；非 E-01 目标保持原样。
        val raw = serverBase.trim().trimEnd('/')
        val base = ReachabilityProbe.deriveE01Pair(raw)?.second ?: raw

        // facet2 FAIL：应用层请求失败计数（非 2xx/IO 错误；主动取消不计）——观测口径
        val reqFailed = java.util.concurrent.atomic.AtomicInteger(0)
        val reqTotal = java.util.concurrent.atomic.AtomicInteger(0)
        suspend fun emit(s: Sample) = send(s.copy(reqFailed = reqFailed.get(), reqTotal = reqTotal.get()))

        // ---- Ping 阶段（~1.7s，快速 echo；实时 RTT + 抖动）----
        val rtts = ArrayList<Double>()
        val pingN = 24
        for (i in 0 until pingN) {
            val t0 = System.nanoTime()
            val r = withContext(Dispatchers.IO) { runCatching { client.echo("$base/api/v1/echo") }.getOrNull() }
            val rttMs = (System.nanoTime() - t0) / 1e6
            reqTotal.incrementAndGet()
            if (r == null || r.error != null) reqFailed.incrementAndGet()
            // 客户端往返墙钟＝网络 RTT（恒非空、随网络波动）；首个含 TCP/TLS 建连，丢弃避免偏高。
            // 不取 echo.rttUs（其依赖服务端 wire 时戳/时钟同步，speed 模式不做同步会为 null）。
            if (i > 0 && r != null && r.error == null) rtts.add(rttMs)
            emit(Sample(Phase.Ping, median(rtts), jitter(rtts), null, null, i.toFloat() / pingN * 0.2f))
            delay(70)
        }
        val rttMed = median(rtts)
        val jit = jitter(rtts)

        // ---- Download 阶段（~6s 持续下载 /download 排空，逐块实时测速）----
        val dlBytes = AtomicLong(0)
        val dlStartNs = System.nanoTime()
        val dlDurNs = 6_000_000_000L
        val dlJob = launch(Dispatchers.IO) {
            reqTotal.incrementAndGet()
            // 主动取消（测够时长）→ 异常路径 getOrNull()=null 不计失败；真实连接/HTTP 失败才计
            runCatching {
                client.downloadDrain("$base/api/v1/download?bytes=$DOWNLOAD_BYTES") { total, _ -> dlBytes.set(total) }
            }.getOrNull()?.let { r ->
                if ((r.httpCode ?: 0) !in 200..299) reqFailed.incrementAndGet()
            }
        }
        val dlWindow = ArrayDeque<Pair<Long, Long>>()
        while (dlJob.isActive && System.nanoTime() - dlStartNs < dlDurNs) {
            val now = System.nanoTime()
            val b = dlBytes.get()
            dlWindow.addLast(now to b)
            while (dlWindow.size > 1 && now - dlWindow.first().first > 600_000_000L) dlWindow.removeFirst()
            val dB = b - dlWindow.first().second
            val dS = (now - dlWindow.first().first) / 1e9
            val mbps = if (dlWindow.size >= 2 && dS > 0.1) dB * 8.0 / dS / 1e6 else null
            val prog = 0.2f + ((now - dlStartNs).toFloat() / dlDurNs.toFloat()).coerceIn(0f, 1f) * 0.4f
            emit(Sample(Phase.Download, rttMed, jit, null, mbps, prog.coerceIn(0f, 0.59f)))
            delay(100)
        }
        dlJob.cancel() // 测够时长即取消 → 服务端随 request context 退出

        // ---- Upload 阶段（~6s 持续上传，逐块实时测速）----
        val bytes = AtomicLong(0)
        val chunk = ByteArray(4 * 1024 * 1024) // 4MB/次循环（零填充即可，服务端不校验内容）
        val upStartNs = System.nanoTime()
        val upDurNs = 6_000_000_000L
        val upJob = launch(Dispatchers.IO) {
            var acc = 0L
            while (isActive && System.nanoTime() - upStartNs < upDurNs) {
                reqTotal.incrementAndGet()
                val res = runCatching {
                    client.uploadBurst("$base/api/v1/upload?run=speed", chunk, chunkBytes = 65536) { total, _ ->
                        bytes.set(acc + total)
                    }
                }.getOrNull()
                if (res != null && (res.error != null || (res.httpCode ?: 0) !in 200..299)) reqFailed.incrementAndGet()
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
            val prog = 0.6f + ((now - upStartNs).toFloat() / upDurNs.toFloat()).coerceIn(0f, 1f) * 0.4f
            emit(Sample(Phase.Upload, rttMed, jit, mbps, null, prog.coerceIn(0f, 0.99f)))
            delay(100)
        }
        upJob.join()
        emit(Sample(Phase.Done, rttMed, jit, null, null, 1f))
    }

    /**
     * 弱网对照（合成）run（D-43）——同 [run] 的三阶段（Ping→Download→Upload→Done），但走服务端
     * `weak-capacity-latency-v1` **逐 run 隔离整形路径**（TEST_SERVER_CAPABILITIES §2/§5，合同
     * `network_comprehensive_weak_capacity_latency@1.0.0`）：聚合 ↓3Mbps/↑1Mbps + 每请求附加
     * RTT 120±30ms；**抖动由服务端按 run+seed+seq 确定性生成**，并发连接共享同 run 限速器
     * （加并发绕不开容量上限）。每个请求经 [ShapedUrls.next] 取新 URL——impair_seq 逐请求严格递增。
     *
     * 口径边界（**合成整形口径，展示必须标注，不与正常 [run] 的结论/分数合并**）：
     * - 对照仅用于并排展示"正常 vs 受控弱网"，全部样本 [Sample.shaped]=true；
     * - 合成整形 ≠ 真实弱网：合同明确排除 DNS/TCP/TLS/UDP/RSRP/SINR，初版不注入 IP 丢包/断线；
     * - **回执门 fail-closed**：首个探针必须 2xx 且带防伪头 `X-Aneb-Synthetic-Impairment`=合同 id，
     *   缺失/不匹配即抛异常，本 run INVALID（不产任何样本）。
     * 预期实测 ≈3/1Mbps，RTT ≈ 基线+120ms。
     */
    fun runShaped(serverBase: String): Flow<Sample> = channelFlow {
        // D-25：与 run() 同口径——E-01 sslip 主机名被 DPI SNI-keyed RST，选路 bare-IP 等价基址
        val raw = serverBase.trim().trimEnd('/')
        val base = ReachabilityProbe.deriveE01Pair(raw)?.second ?: raw
        val urls = ShapedUrls(
            base = base,
            runId = "cc-shape-${System.nanoTime().toString(16)}",
            seed = System.nanoTime() and 0x7FFFFFFF,
        )

        // ---- 回执门（fail-closed）：整形路径防伪回执缺失/不匹配 → run INVALID，不产结果 ----
        val receipt = withContext(Dispatchers.IO) { client.syntheticPost(urls.next("echo")) }
        check(receipt.httpCode in 200..299 && receipt.impairmentHeader == ShapedUrls.CONTRACT_ID) {
            "缺防伪回执头 X-Aneb-Synthetic-Impairment=${ShapedUrls.CONTRACT_ID}" +
                "（http=${receipt.httpCode ?: receipt.error} header=${receipt.impairmentHeader}）—— run INVALID"
        }

        val reqFailed = java.util.concurrent.atomic.AtomicInteger(0)
        val reqTotal = java.util.concurrent.atomic.AtomicInteger(0)
        suspend fun emit(s: Sample) =
            send(s.copy(reqFailed = reqFailed.get(), reqTotal = reqTotal.get(), shaped = true))

        // ---- Ping 阶段（12 次整形 echo；每请求 +120±30ms，实时 RTT + 抖动）----
        val rtts = ArrayList<Double>()
        for (i in 0 until SHAPED_PING_N) {
            val t0 = System.nanoTime()
            val r = withContext(Dispatchers.IO) { runCatching { client.echo(urls.next("echo")) }.getOrNull() }
            val rttMs = (System.nanoTime() - t0) / 1e6
            reqTotal.incrementAndGet()
            if (r == null || r.error != null) reqFailed.incrementAndGet()
            // 与 run() 同口径：客户端往返墙钟；首个含 TCP/TLS 建连，丢弃避免偏高
            if (i > 0 && r != null && r.error == null) rtts.add(rttMs)
            emit(Sample(Phase.Ping, median(rtts), jitter(rtts), null, null, i.toFloat() / SHAPED_PING_N * 0.2f))
            delay(70)
        }
        val rttMed = median(rtts)
        val jit = jitter(rtts)

        // ---- Download 阶段（~6s 排空 8MiB 有界下行；整形 3Mbps 下 6s 收 ~2.25MB，收不完即取消）----
        val dlBytes = AtomicLong(0)
        val dlStartNs = System.nanoTime()
        val dlDurNs = 6_000_000_000L
        val dlJob = launch(Dispatchers.IO) {
            reqTotal.incrementAndGet()
            runCatching {
                client.downloadDrain(urls.next("download?bytes=$SHAPED_DOWNLOAD_BYTES")) { total, _ -> dlBytes.set(total) }
            }.getOrNull()?.let { r ->
                if ((r.httpCode ?: 0) !in 200..299) reqFailed.incrementAndGet()
            }
        }
        val dlWindow = ArrayDeque<Pair<Long, Long>>()
        while (dlJob.isActive && System.nanoTime() - dlStartNs < dlDurNs) {
            val now = System.nanoTime()
            val b = dlBytes.get()
            dlWindow.addLast(now to b)
            while (dlWindow.size > 1 && now - dlWindow.first().first > 600_000_000L) dlWindow.removeFirst()
            val dB = b - dlWindow.first().second
            val dS = (now - dlWindow.first().first) / 1e9
            val mbps = if (dlWindow.size >= 2 && dS > 0.1) dB * 8.0 / dS / 1e6 else null
            val prog = 0.2f + ((now - dlStartNs).toFloat() / dlDurNs.toFloat()).coerceIn(0f, 1f) * 0.4f
            emit(Sample(Phase.Download, rttMed, jit, null, mbps, prog.coerceIn(0f, 0.59f)))
            delay(100)
        }
        dlJob.cancel()

        // ---- Upload 阶段（~6s 循环上传，1MiB/次；整形 1Mbps 下在途块允许收尾超窗）----
        val bytes = AtomicLong(0)
        val chunk = ByteArray(1 shl 20) // 1MiB/次（整形 1Mbps；每次循环经 urls.next 取新 seq）
        val upStartNs = System.nanoTime()
        val upDurNs = 6_000_000_000L
        val upJob = launch(Dispatchers.IO) {
            var acc = 0L
            while (isActive && System.nanoTime() - upStartNs < upDurNs) {
                reqTotal.incrementAndGet()
                val res = runCatching {
                    client.uploadBurst(urls.next("upload"), chunk, chunkBytes = 65536) { total, _ ->
                        bytes.set(acc + total)
                    }
                }.getOrNull()
                if (res != null && (res.error != null || (res.httpCode ?: 0) !in 200..299)) reqFailed.incrementAndGet()
                acc += chunk.size
                bytes.set(acc)
            }
        }
        val window = ArrayDeque<Pair<Long, Long>>()
        while (upJob.isActive) {
            val now = System.nanoTime()
            val b = bytes.get()
            window.addLast(now to b)
            while (window.size > 1 && now - window.first().first > 600_000_000L) window.removeFirst()
            val dB = b - window.first().second
            val dS = (now - window.first().first) / 1e9
            val mbps = if (window.size >= 2 && dS > 0.1) dB * 8.0 / dS / 1e6 else null
            val prog = 0.6f + ((now - upStartNs).toFloat() / upDurNs.toFloat()).coerceIn(0f, 1f) * 0.4f
            emit(Sample(Phase.Upload, rttMed, jit, mbps, null, prog.coerceIn(0f, 0.99f)))
            delay(100)
        }
        upJob.join()
        emit(Sample(Phase.Done, rttMed, jit, null, null, 1f))
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

/**
 * weak-capacity-latency-v1 合成整形路径 URL 构造器（D-43，[SpeedRunner.runShaped] 专用）。
 *
 * 服务端合同（TEST_SERVER_CAPABILITIES §2/§5）：该路径下**每个请求**都必须携带
 * `impair_run/impair_seed/impair_seq` 三参数，且 `impair_seq` **逐请求严格递增**——服务端按
 * run+seed+seq 确定性生成附加 RTT 抖动（120±30ms）。每次 [next] 消耗一个内部序号并返回完整 URL。
 *
 * 纯 URL 构造（无网络副作用），可脱网单测；[next] 线程安全（download/upload 阶段在 IO 协程取号）。
 *
 * @param base 服务器基址（不带尾斜杠，D-25 bare-IP 选路后）
 * @param runId 本次整形 run 的隔离 id（服务端逐 run 限速器 key）
 * @param seed 抖动种子（服务端确定性抖动输入）
 */
class ShapedUrls(private val base: String, private val runId: String, private val seed: Long) {

    private val seq = java.util.concurrent.atomic.AtomicInteger(0)

    /**
     * 取下一条整形路径 URL（消耗一个 impair_seq，严格 +1）。
     * @param endpoint 端点段，形如 `"echo"`、`"upload"` 或自带查询参数的 `"download?bytes=8388608"`
     */
    fun next(endpoint: String): String {
        val sep = if ('?' in endpoint) '&' else '?'
        return "$base/$ROUTE/$endpoint${sep}impair_run=$runId&impair_seed=$seed&impair_seq=${seq.getAndIncrement()}"
    }

    companion object {
        /** 防伪回执头 `X-Aneb-Synthetic-Impairment` 必须等于的合同 id（缺失/不匹配→INVALID）。 */
        const val CONTRACT_ID = "network_comprehensive_weak_capacity_latency@1.0.0"

        /** 逐 run 隔离整形路由（只支持 echo/download/upload 三端点）。 */
        const val ROUTE = "synthetic/weak-capacity-latency-v1/api/v1"
    }
}
