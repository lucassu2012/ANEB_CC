package com.aneb.probe.engine

import android.net.Network
import com.aneb.probe.net.AnebClient
import com.aneb.probe.net.ReachabilityProbe
import com.aneb.probe.net.UdpProbe
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.channelFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.concurrent.atomic.AtomicLong

/**
 * 网络基本性能模式（SpeedTest 同款）运行器——**独立于 token 测量引擎**（[TestEngine]），
 * 与 [AbRunner] / [ContinuityRunner] 并列的一种测试模式。
 *
 * 目标：用会**随网络真实波动**的指标（上行吞吐、时延）驱动 SpeedTest 级动态仪表。
 * - **Ping 阶段**：快速 echo → 实时 RTT / 抖动（随网络波动）。
 * - **UDP 应用探针**（Ping 后、Download 前，仅正常 [run]）：ANEB1 整包回显按 seq 对账 →
 *   "UDP 未返回率"。口径：应用层探针未回显占比，**≠IP 丢包率**；现场协变量，不进任何分；
 *   零回包/不可达＝"UDP 应用探针不可用"（null，R-10）。UDP 不受合成整形，[runShaped] 不做。
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
        /** UDP 未返回率（%）＝应用层 ANEB1 探针未回显占比，**≠IP 丢包率**；现场协变量，
         * 不进任何分。零回包/不可达/探测失败均为 null＝"UDP 应用探针不可用"（R-10 绝不折 0/100）。 */
        val udpUnreturnedPct: Double? = null,
        /** UDP 探针回显 RTT 中位数（ms，发出→回显到达单调钟）；无成功样本 null（R-10）。 */
        val udpRttMs: Double? = null,
    )

    /** 最近一次 [run] 的 UDP 探针原始结果（观测协变量；MainActivity 记 `UDP_PROBE` 日志用，
     *  D-02 只读不重算）。run 起始清 null；探测失败保持 null。 */
    @Volatile
    var lastUdpProbeResult: UdpProbe.UdpProbeResult? = null
        private set

    /**
     * @param network 已绑定的测量网络（R-01：防 VPN/代理污染）；null＝AUTO 不绑定
     *   （与本模式 HTTP 路径的默认 [AnebClient] 同口径）。当前仅 UDP 探针消费。
     */
    fun run(serverBase: String, network: Network? = null, weakNet: String? = null): Flow<Sample> = channelFlow {
        // D-25：E-01 的 sslip 主机名在电信/部分网络被 DPI 做 SNI-keyed TLS RST（Connection reset）。
        // 直接选路 bare-IP 等价基址（同节点、同物理路径、观测口径不变）绕过；非 E-01 目标保持原样。
        val raw = serverBase.trim().trimEnd('/')
        val base = ReachabilityProbe.deriveE01Pair(raw)?.second ?: raw

        // 弱网伴流（DEBUG contend:N；B3，与 token 模式 [TestEngine] 共用 [WeakNet] 编排——修此前
        // 弱网开关在 SpeedTest 模式静默失效的缺口）：run 全程并行 N 条背景下行拥塞流，用独立 client
        // 免污染测量连接池。**必须显式取消**（无限循环不自终；否则 channelFlow 结构化并发等子协程
        // 完成→永不结束）：正常路径于 Upload 后统一 cancel，异常路径由 channelFlow 作用域取消。
        val contendJobs = WeakNet.parseContendN(weakNet)?.let { n ->
            val contendClient = AnebClient()
            WeakNet.launchContendDrains(this, n) {
                contendClient.downloadDrain("$base/api/v1/download?bytes=$DOWNLOAD_BYTES")
            }
        } ?: emptyList()

        // facet2 FAIL：应用层请求失败计数（非 2xx/IO 错误；主动取消不计）——观测口径
        val reqFailed = java.util.concurrent.atomic.AtomicInteger(0)
        val reqTotal = java.util.concurrent.atomic.AtomicInteger(0)
        // UDP 应用探针观测值（Ping 相位后填充；探测前/失败均 null——"UDP 应用探针不可用"，R-10）
        var udpUnreturned: Double? = null
        var udpRttMed: Double? = null
        suspend fun emit(s: Sample) = send(
            s.copy(
                reqFailed = reqFailed.get(), reqTotal = reqTotal.get(),
                udpUnreturnedPct = udpUnreturned, udpRttMs = udpRttMed,
            )
        )

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
            emit(Sample(Phase.Ping, SpeedSampleMath.median(rtts), SpeedSampleMath.jitter(rtts), null, null, i.toFloat() / pingN * 0.2f))
            delay(70)
        }
        val rttMed = SpeedSampleMath.median(rtts)
        val jit = SpeedSampleMath.jitter(rtts)

        // ---- UDP 应用探针（Ping 后、Download 前；ANEB1 整包回显按 seq 对账）----
        // 口径：UDP 未返回率＝应用层探针未回显占比，≠IP 丢包率；现场协变量，不进任何分。
        // UDP 路径不受服务端合成整形（未整形现场协变量），故只在本正常 run 执行，[runShaped] 不做。
        // 失败/不可达 → 字段保持 null（"UDP 应用探针不可用"，R-10），不影响主流程。
        lastUdpProbeResult = null
        runCatching {
            val uri = java.net.URI(base)
            val udpPort = uri.port.takeIf { it > 0 } ?: 443 // UDP 与 HTTPS 共端口（魔数分流）
            val res = withContext(Dispatchers.IO) { UdpProbe(network).probe(uri.host, udpPort) }
            lastUdpProbeResult = res
            udpUnreturned = res.unreturnedPct
            udpRttMed = res.rttMedianMs
        }
        emit(Sample(Phase.Ping, rttMed, jit, null, null, 0.2f))

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
            val mbps = SpeedSampleMath.windowMbps(dlWindow, now, b)
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
            val mbps = SpeedSampleMath.windowMbps(window, now, b)
            val prog = 0.6f + ((now - upStartNs).toFloat() / upDurNs.toFloat()).coerceIn(0f, 1f) * 0.4f
            emit(Sample(Phase.Upload, rttMed, jit, mbps, null, prog.coerceIn(0f, 0.99f)))
            delay(100)
        }
        upJob.join()
        contendJobs.forEach { it.cancel() } // 弱网伴流全程运行至此，正常路径统一取消（B3；无限循环不自终）
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
            emit(Sample(Phase.Ping, SpeedSampleMath.median(rtts), SpeedSampleMath.jitter(rtts), null, null, i.toFloat() / SHAPED_PING_N * 0.2f))
            delay(70)
        }
        val rttMed = SpeedSampleMath.median(rtts)
        val jit = SpeedSampleMath.jitter(rtts)

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
            val mbps = SpeedSampleMath.windowMbps(dlWindow, now, b)
            val prog = 0.2f + ((now - dlStartNs).toFloat() / dlDurNs.toFloat()).coerceIn(0f, 1f) * 0.4f
            emit(Sample(Phase.Download, rttMed, jit, null, mbps, prog.coerceIn(0f, 0.59f)))
            delay(100)
        }
        dlJob.cancel()

        // ---- Upload 阶段（~6s 循环上传，128KiB/次）----
        // 合同计量口径（TEST_SERVER_CAPABILITIES §5）：只累计服务端回执确认的字节，
        // 不把本机 socket 写入量当成线上 goodput——1Mbps 整形下 send buffer 一口吞下整块，
        // 写口径瞬时窗口会虚高到链路裸速（真机实证 36 Mbps vs 标称 1）。故：无 onChunk 中间
        // 计数、仅成功响应后整块入账、速率取自首请求起的全程均值（离散确认对滑窗不友好）。
        val bytes = AtomicLong(0)
        val chunk = ByteArray(128 shl 10) // 128KiB/请求（整形 1Mbps 下含注入 RTT ~1.2s/个）
        val upStartNs = System.nanoTime()
        val upDurNs = 6_000_000_000L
        val upJob = launch(Dispatchers.IO) {
            var acc = 0L
            while (isActive && System.nanoTime() - upStartNs < upDurNs) {
                reqTotal.incrementAndGet()
                val res = runCatching {
                    client.uploadBurst(urls.next("upload"), chunk, chunkBytes = 65536)
                }.getOrNull()
                val ok = res != null && res.error == null && (res.httpCode ?: 0) in 200..299
                if (!ok) {
                    reqFailed.incrementAndGet()
                    continue // 失败块不入账（未获服务端确认的字节不算 goodput）
                }
                acc += chunk.size
                bytes.set(acc)
            }
        }
        while (upJob.isActive) {
            val now = System.nanoTime()
            val b = bytes.get()
            val dS = (now - upStartNs) / 1e9
            val mbps = if (b > 0 && dS > 0.1) b * 8.0 / dS / 1e6 else null
            val prog = 0.6f + ((now - upStartNs).toFloat() / upDurNs.toFloat()).coerceIn(0f, 1f) * 0.4f
            emit(Sample(Phase.Upload, rttMed, jit, mbps, null, prog.coerceIn(0f, 0.99f)))
            delay(100)
        }
        upJob.join()
        emit(Sample(Phase.Done, rttMed, jit, null, null, 1f))
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
