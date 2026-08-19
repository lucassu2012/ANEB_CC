package com.aneb.probe.engine

import com.aneb.probe.net.TokenEvent
import com.aneb.probe.scoring.AdaptiveWindowResult
import com.aneb.probe.scoring.EchoSample
import com.aneb.probe.scoring.InvalidReason
import com.aneb.probe.scoring.KpiInput
import com.aneb.probe.scoring.ToolLoopSample
import com.aneb.probe.scoring.TokenSample
import com.aneb.probe.scoring.TtftSample
import com.aneb.probe.scoring.DownloadResult as KpiDownloadResult
import com.aneb.probe.scoring.UploadResult as KpiUploadResult

/**
 * ScenarioOutcome → KpiInput 映射（接线层适配器，P1 范围 5；不改 scoring/ 公共 API）。
 * 除 [buildKpiInput] 直接吃 outcome 外，核心变换均为纯函数、可 JVM 单测。
 */
object ScenarioKpi {

    /** profile 内生停顿判定线：同流内相邻 seq 的服务端名义间隔 ≥250ms 视为 pause（T5 剔除口径，R-09） */
    const val PAUSE_SCHED_US = 250_000L

    /** 服务端 /upload 读块大小（server/handlers_upload.go uploadChunkSize），慢启动估计用 */
    const val SERVER_UPLOAD_CHUNK_BYTES = 65_536L

    class StreamTokens(val expectedTokens: Int, val events: List<TokenEvent>)

    class TokenJoin(val samples: List<TokenSample>, val pauseSeqs: Set<Long>)

    /**
     * 多 token_stream 合并（S2 两段流 / S3 两段流 → 单场景 KpiInput）：
     *
     * - **seq 重编号**：流 k 的 seq 平移 base_k = Σ 前序流 expectedTokens，保证场景内唯一；
     * - **跨流边界禁配对**：流 k>0 的 seq==0 样本 sched/preFlush 置 null——跨 HTTP 连接的
     *   "到达间隔"内含 tool_loop/think_pause 整段时长且两端锚点不同，既不是 ITL 也不是
     *   resume；置空后 KpiCalculator 的配对条件（双端时间戳齐备）自然跳过该对（以及
     *   该流首对 (0,1)，每流损失 1 个配对样本，量级 1/300）。
     * - **pauseSeqs**：同流内相邻 present seq 的 schedΔ ≥ [PAUSE_SCHED_US] → 后者标 resume
     *   （簇间停顿 300–800ms；稳态间隔 16–25ms，阈值 10 倍以上安全）。
     */
    fun joinStreams(streams: List<StreamTokens>): TokenJoin {
        val samples = ArrayList<TokenSample>()
        val pauseSeqs = HashSet<Long>()
        var base = 0L
        for ((k, st) in streams.withIndex()) {
            for (e in st.events) {
                val crossBoundary = k > 0 && e.seq == 0L
                samples.add(
                    TokenSample(
                        seq = base + e.seq,
                        srvSchedUs = if (crossBoundary || e.schedUs < 0) null else e.schedUs,
                        srvPreFlushUs = if (crossBoundary || e.preFlushUs < 0) null else e.preFlushUs,
                        arrivalNanos = e.arrivalNanos,
                        sameReadBatch = e.sameReadBatch,
                    )
                )
            }
            // pause 检测（首见样本，按 seq 排序）
            val bySeq = HashMap<Long, TokenEvent>()
            for (e in st.events) bySeq.putIfAbsent(e.seq, e)
            val seqs = bySeq.keys.sorted()
            for (s in seqs) {
                val a = bySeq[s] ?: continue
                val b = bySeq[s + 1] ?: continue
                if (a.schedUs >= 0 && b.schedUs >= 0 && b.schedUs - a.schedUs >= PAUSE_SCHED_US) {
                    pauseSeqs.add(base + s + 1)
                }
            }
            base += st.expectedTokens
        }
        return TokenJoin(samples, pauseSeqs)
    }

    /**
     * T2/T3/T4 主口径校正 ITL 样本序列（ms）——KpiCalculator.calculate 内部配对逻辑的镜像
     * （corrected = arrivalΔ − flushΔ + schedΔ；剔 coalesced/resume/0 到达间隔），供 ITL
     * 对数分桶直方图上报（R-27 合同：服务端复算 stall 率须与本地一致；单测锚定两者等价）。
     */
    fun correctedItlSamplesMs(samples: List<TokenSample>, pauseSeqs: Set<Long>): List<Double> {
        val bySeq = HashMap<Long, TokenSample>()
        for (s in samples) bySeq.putIfAbsent(s.seq, s)
        val out = ArrayList<Double>()
        for (seq in bySeq.keys.sorted()) {
            val a = bySeq[seq] ?: continue
            val b = bySeq[seq + 1] ?: continue
            val aArr = a.arrivalNanos ?: continue
            val bArr = b.arrivalNanos ?: continue
            val aFlush = a.srvPreFlushUs ?: continue
            val bFlush = b.srvPreFlushUs ?: continue
            val aSched = a.srvSchedUs ?: continue
            val bSched = b.srvSchedUs ?: continue
            if (b.sameReadBatch) continue
            if (b.seq in pauseSeqs) continue
            val arrivalMs = (bArr - aArr) / 1e6
            if (arrivalMs == 0.0) continue
            out.add(arrivalMs - (bFlush - aFlush) / 1e3 + (bSched - aSched) / 1e3)
        }
        return out
    }

    /**
     * 场景原始产出 → KpiCalculator 输入。
     *
     * - N1/N2 输入＝**首次 clock_sync** 的 echo 样本（5.1"每场景开始前采样"；尾部
     *   clock_sync 只用于 skew 插值，不进 N 组——AqsInputMapper 合同同款口径）；
     * - U1：终点=2xx 响应头；慢启动爬坡由服务端权威逐块序列估计（UploadAnalysis）；
     * - U2：serverProc 优先用 X-Aneb-Trecv/Tsend 实测差，缺失退名义 proc_ms；
     * - streamTruncated：任一流传输错误/尾部截断/提前干净关闭，或场景被中止。
     */
    fun buildKpiInput(
        outcome: ScenarioRunner.ScenarioOutcome,
        externalInvalidReasons: List<InvalidReason>,
    ): KpiInput {
        val join = joinStreams(
            outcome.streams.map { StreamTokens(it.expectedTokens, it.result.stream?.events ?: emptyList()) }
        )

        val echoSamples = outcome.clockSyncs.firstOrNull()?.samples.orEmpty().map { rec ->
            EchoSample(
                rttNanos = if (rec.result.error == null) rec.result.rttUs?.times(1000L) else null,
                warmup = rec.warmup,
            )
        }

        val uploads = outcome.uploads.map { up ->
            val sv = up.result.serverView
            val slowStart = if (sv != null && sv.recvStartUs >= 0) {
                UploadAnalysis.estimateSlowStart(sv.chunkUs, sv.recvStartUs, SERVER_UPLOAD_CHUNK_BYTES)
            } else {
                null
            }
            KpiUploadResult(
                bytes = up.profileBytes,
                durationNanos = up.durationNanos,
                http2xx = up.result.error == null && (up.result.httpCode ?: 0) in 200..299,
                slowStartNanos = slowStart?.first?.times(1000L),
                slowStartBytes = slowStart?.second,
            )
        }

        // D1：下行大对象拉取（PROFILE_FRAMEWORK §2.2 BM-09 口径(b)；bytes 取实收字节，
        // 成功时=Content-Length；失败样本 durationNanos=null 不进统计，R-10）
        val downloads = outcome.downloads.map { dl ->
            KpiDownloadResult(
                bytes = dl.result.bytesRead,
                durationNanos = dl.durationNanos,
                http2xx = dl.result.error == null && (dl.result.httpCode ?: 0) in 200..299,
            )
        }

        val toolLoops = outcome.toolLoops.map { tl ->
            val r = tl.result
            val actualProcUs = if (r.trecvUs != null && r.tsendUs != null) r.tsendUs - r.trecvUs else null
            ToolLoopSample(
                totalNanos = r.bodyEndNanos?.minus(r.startNanos),
                serverProcNanos = (actualProcUs?.times(1000L)) ?: (tl.nominalProcMs * 1_000_000L),
            )
        }

        // ---- U3/D3：单流自适应窗口 goodput 探针（T47 批③，spec §8.3-§8.4）----
        // RTT 基准取本场景自己的 phase 1/phase 4 clock_sync（不复用其他场景/pooled 的 N1，
        // 理由同既有 N1 惯例：网络状态可能已漂移，D-365 实测同链路 RTT 可漂移 26-34%）。
        fun clockSyncRttP50Ms(cs: ScenarioRunner.ClockSyncOutcome?): Double? {
            val rtts = cs?.samples.orEmpty()
                .filter { !it.warmup }
                .mapNotNull { it.result.rttUs }
                .map { it / 1000.0 }
            return com.aneb.probe.scoring.KpiCalculator.percentileOrNull(rtts, 0.50)
        }
        val rttRefMsPre = clockSyncRttP50Ms(outcome.clockSyncs.getOrNull(0))
        val rttRefMsPost = clockSyncRttP50Ms(outcome.clockSyncs.getOrNull(1))

        fun adaptiveWindow(w: ScenarioRunner.AdaptiveWindowOutcome?): AdaptiveWindowResult? {
            if (w == null) return null
            val r = w.result
            val windowActualNanos = r.endNanos?.let { it - r.startNanos }
            val slowStart = TransferWindowAnalysis.estimateSlowStartByRate(w.samples)
            val dominance = RttDominanceGuard.evaluate(
                windowActualMs = windowActualNanos?.let { it / 1e6 } ?: 0.0,
                rttRefMs = rttRefMsPre,
                bytesTransferred = r.bytesTransferred,
            )
            return AdaptiveWindowResult(
                windowTargetMs = w.windowTargetMs,
                windowActualNanos = windowActualNanos,
                bytesTransferred = r.bytesTransferred,
                http2xx = r.error == null && (r.httpCode ?: 0) in 200..299,
                slowStartUs = slowStart?.first,
                slowStartBytes = slowStart?.second,
                rttRefMsPre = rttRefMsPre,
                rttRefMsPost = rttRefMsPost,
                rttDominanceRatio = dominance.ratio,
                rttDominanceOk = dominance.ok,
                // 批③漏搬的一环：该值此前只出现在 ScenarioRunner 的一行 logcat 里，
                // 从未进入 KPI 层，故 spec §8.4.3 要求它参与的 low_confidence 判定一直缺一条。
                windowUnderrun = r.windowUnderrun,
            )
        }
        val adaptiveUpload = adaptiveWindow(outcome.uploadWindows.firstOrNull())
        val adaptiveDownload = adaptiveWindow(outcome.downloadWindows.firstOrNull())

        val ttfts = outcome.streams.map { TtftSample(it.ttftMs) }

        val truncated = outcome.abortReason != null || outcome.streams.any {
            it.result.error == null && (it.result.truncatedEarly || it.result.stream?.truncatedTail == true)
        } || outcome.streams.any { it.result.error != null }

        return KpiInput(
            tokenSamples = join.samples,
            pauseSeqs = join.pauseSeqs,
            echoSamples = echoSamples,
            uploadResults = uploads,
            downloadResults = downloads,
            toolLoopSamples = toolLoops,
            ttftSamples = ttfts,
            streamTruncated = truncated,
            externalInvalidReasons = externalInvalidReasons,
            adaptiveUpload = adaptiveUpload,
            adaptiveDownload = adaptiveDownload,
        )
    }
}
