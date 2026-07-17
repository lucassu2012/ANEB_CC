package com.aneb.probe.engine

import com.aneb.probe.net.AnebClient
import com.aneb.probe.net.ReachabilityProbe
import com.aneb.probe.net.RealtimeSimSession
import com.aneb.probe.net.RealtimeWire
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.channelFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.max

/**
 * AI 实时交互（语音，GPT-Live 式）模式运行器——与 [SpeedRunner] 并列的观测口径模式
 * （PROFILE_FRAMEWORK §4.1）。**零服务端部署**：
 * - **上行帧**：[AnebClient.uploadPaced] 按 20ms 帧节奏发小包（模拟 Opus 上行），服务端
 *   `/upload` 的 `chunk_us` 权威到达序列 → **上行帧间抖动 M3**（含客户端调度抖动，观测上界）。
 * - **下行帧**：已部署 `/stream?tokens=&rate_tps=50` 实测输出精确 20ms 帧节奏（sched_us 差
 *   恰 20000µs），客户端 arrivalNanos 帧间隔 → **下行帧间抖动 M2**。
 * - **口到耳预算 M1**（DERIVED，口径注明）＝RTT_P50 + max(上/下行帧抖动 P95) +
 *   编解码/播放缓冲名义常数 [CODEC_JB_BUDGET_MS]——网络贡献的口到耳下界预算，非真实音频链路实测。
 *
 * 观测/展示口径，不进 v0.1/v0.2/Token AQS；facet4 经 [com.aneb.probe.scoring.AqsScorer.scoreVoice]
 * 独立出分（WEIGHTS_VOICE + M1>400ms 硬否决）。
 */
class VoiceRunner(private val client: AnebClient = AnebClient()) {

    enum class Phase { Ping, Uplink, Downlink, Handshake, Turns, Done }

    data class Sample(
        val phase: Phase,
        val rttMs: Double?,
        val jitterMs: Double?,
        /** 上行帧间抖动 P95（ms，M3；服务端 chunk_us 权威）；未测/样本不足 null */
        val upFrameJitterMs: Double?,
        /** 下行帧间抖动 P95（ms，M2；客户端 arrivalNanos）；未测/样本不足 null */
        val downFrameJitterMs: Double?,
        /** 口到耳预算（ms，M1 DERIVED）；任一成分缺失 null（R-10） */
        val mouthEarBudgetMs: Double?,
        val framesSent: Int,
        val framesRecv: Int,
        val progress: Float,
        // ── v2 server-sim 口径尾部字段（D-38；additive 默认 null，v1 run() 不受影响）──
        /** M4 TTS-TTFB P50（ms，实测：speech_commit→首 ANED，已剥服务端驻留）；null=未测 */
        val ttfbP50Ms: Double? = null,
        /** M4 TTS-TTFB P95（ms） */
        val ttfbP95Ms: Double? = null,
        /** M2' 下行纯传输抖动 P95（ms；帧内嵌 sched_us 差分剥离服务端调度误差） */
        val downNetJitterMs: Double? = null,
        /** M1' 口到耳实测代理 P50（ms；末上行帧→首 ANED 剥驻留 + 编解码常数；标 PROXY） */
        val mouthEarProxyMs: Double? = null,
        /** M5 轮次切换 P50（ms；上轮 summary→下轮首 ANED，剥计划上行时长与驻留） */
        val turnSwitchP50Ms: Double? = null,
        /** M6 打断停帧最大值（ms；barge_in 发出→末 ANED 到达） */
        val bargeStopMaxMs: Double? = null,
        /** protocol_ok 轮数（诚实对账） */
        val turnsOk: Int = 0,
        /** 口径标注：null=v1 paced-proxy；"server-sim(aneb-realtime-session-v1)"=v2 */
        val caliber: String? = null,
        /** 上行入队背压出现过（ws.queueSize>0）→ 低置信 */
        val lowConfidence: Boolean = false,
    )

    companion object {
        /** 语音帧节奏（Opus 典型 20ms/帧） */
        const val FRAME_INTERVAL_MS = 20L

        /** 帧大小（~64kbps 语音帧量级） */
        const val FRAME_BYTES = 160

        /** 上/下行各 ~4s（200 帧 × 20ms） */
        const val UPLINK_FRAMES = 200
        const val DOWNLINK_FRAMES = 200

        /** 编解码 + 播放抖动缓冲名义预算（ms，口径常数：codec ~20 + playout buffer ~40） */
        const val CODEC_JB_BUDGET_MS = 60.0

        /** v2 server-sim 口径标注（contract_version 直接入库，D-38） */
        const val SIM_CALIBER = "server-sim(aneb-realtime-session-v1)"

        /** v2 中 M3 专用 uploadPaced 帧数（3s 短段；M3 权威仍是 /upload chunk_us） */
        const val SIM_M3_FRAMES = 150

        /**
         * 默认 8 轮语音计划（D-38 §4）：20ms×160B≈64kbps Opus 量级（与 v1 口径常数一致，
         * M2/M3 跨口径可比）；75 上行帧≈1.5s 说话、100 下行帧≈2s TTS、300ms 模拟思考
         * （剥离后不进 KPI）；idx 3/6 为打断轮（barge_in@25 帧，expected_stop 250ms）。
         * 全部字段已逐项过合同限额（turns≤32、frame_ms∈[10,100]、帧数/字节/等待在界）。
         */
        fun defaultSimPlan(seed: Long): RealtimeWire.SessionPlan = RealtimeWire.SessionPlan(
            sessionId = "voice-sim-${seed.toString(16)}",
            seed = seed,
            setupMs = 200.0,
            frameMs = 20,
            turns = (0 until 8).map { i ->
                val interrupted = i == 3 || i == 6
                RealtimeWire.TurnPlan(
                    turnId = "t$i", turnIndex = i, startAfterPreviousMs = 0,
                    uplinkFrames = 75, uplinkFrameBytes = FRAME_BYTES, responseWaitMs = 300,
                    plannedDownlinkFrames = 100, downlinkFrameBytes = FRAME_BYTES,
                    interrupted = interrupted,
                    bargeInAfterFrames = if (interrupted) 25 else null,
                    expectedStopWithinMs = if (interrupted) 250 else null,
                )
            },
        )

        /**
         * 帧间抖动 P95（ms）＝相邻到达间隔对名义帧间隔偏差绝对值的最近秩 P95。
         * 间隔样本 <2 → null（R-10）。
         */
        fun frameJitterP95Ms(intervalsUs: List<Long>, nominalUs: Long): Double? {
            if (intervalsUs.size < 2) return null
            val devs = intervalsUs.map { abs(it - nominalUs) / 1000.0 }.sorted()
            val rank = ceil(0.95 * devs.size).toInt().coerceIn(1, devs.size)
            return devs[rank - 1]
        }

        /**
         * 口到耳预算（ms，DERIVED）＝RTT_P50 + max(上行帧抖动, 下行帧抖动) + [CODEC_JB_BUDGET_MS]。
         * 任一成分缺失 → null（R-10：不以部分成分冒充整体预算）。
         */
        fun mouthEarBudgetMs(rttP50Ms: Double?, upJitterMs: Double?, downJitterMs: Double?): Double? {
            if (rttP50Ms == null || upJitterMs == null || downJitterMs == null) return null
            return rttP50Ms + max(upJitterMs, downJitterMs) + CODEC_JB_BUDGET_MS
        }
    }

    fun run(serverBase: String): Flow<Sample> = channelFlow {
        // D-25：E-01 sslip SNI-RST → bare-IP 等价基址（同节点同路径）
        val raw = serverBase.trim().trimEnd('/')
        val base = ReachabilityProbe.deriveE01Pair(raw)?.second ?: raw

        // ---- Ping（~1s，12 次 echo；墙钟 RTT，丢首个建连样本）----
        val rtts = ArrayList<Double>()
        val pingN = 12
        for (i in 0 until pingN) {
            val t0 = System.nanoTime()
            val r = withContext(Dispatchers.IO) { runCatching { client.echo("$base/api/v1/echo") }.getOrNull() }
            val rttMs = (System.nanoTime() - t0) / 1e6
            if (i > 0 && r != null && r.error == null) rtts.add(rttMs)
            send(Sample(Phase.Ping, median(rtts), quantJitter(rtts), null, null, null, 0, 0, i.toFloat() / pingN * 0.2f))
            delay(70)
        }
        val rttMed = median(rtts)
        val nJit = quantJitter(rtts)

        // ---- Uplink 帧（~4s：200 帧 × 20ms × 160B → /upload；chunk_us 权威到达）----
        val sent = AtomicInteger(0)
        var upResult: AnebClient.UploadResult? = null
        val upJob = launch(Dispatchers.IO) {
            upResult = runCatching {
                client.uploadPaced(
                    "$base/api/v1/upload?run=voice",
                    frames = UPLINK_FRAMES, frameBytes = FRAME_BYTES, intervalMs = FRAME_INTERVAL_MS,
                ) { n, _ -> sent.set(n) }
            }.getOrNull()
        }
        while (upJob.isActive) {
            val prog = 0.2f + sent.get().toFloat() / UPLINK_FRAMES * 0.35f
            send(Sample(Phase.Uplink, rttMed, nJit, null, null, null, sent.get(), 0, prog.coerceIn(0f, 0.55f)))
            delay(100)
        }
        val upIntervalsUs = upResult?.serverView?.chunkUs.orEmpty().zipWithNext { a, b -> b - a }
        val upJitter = frameJitterP95Ms(upIntervalsUs, FRAME_INTERVAL_MS * 1000)

        // ---- Downlink 帧（~4s：/stream?tokens=200&rate_tps=50，20ms 节奏；arrivalNanos）----
        val recv = AtomicInteger(0)
        var streamResult: AnebClient.StreamResult? = null
        val dlJob = launch(Dispatchers.IO) {
            streamResult = runCatching {
                client.stream(
                    "$base/api/v1/stream?tokens=$DOWNLINK_FRAMES&rate_tps=50&run=voice",
                    expectedTokens = DOWNLINK_FRAMES,
                ) { n, _ -> recv.set(n) }
            }.getOrNull()
        }
        while (dlJob.isActive) {
            val prog = 0.55f + recv.get().toFloat() / DOWNLINK_FRAMES * 0.4f
            send(
                Sample(
                    Phase.Downlink, rttMed, nJit, upJitter, null, null,
                    sent.get(), recv.get(), prog.coerceIn(0f, 0.97f),
                )
            )
            delay(100)
        }
        val arrivals = streamResult?.stream?.events.orEmpty().map { it.arrivalNanos }
        val downIntervalsUs = arrivals.zipWithNext { a, b -> (b - a) / 1000 }
        val downJitter = frameJitterP95Ms(downIntervalsUs, FRAME_INTERVAL_MS * 1000)

        // ---- Done：口到耳预算合成 ----
        val budget = mouthEarBudgetMs(rttMed, upJitter, downJitter)
        send(Sample(Phase.Done, rttMed, nJit, upJitter, downJitter, budget, sent.get(), recv.get(), 1f))
    }

    // ─────────────────────────────────────────────────────────────────────
    //  v2 server-sim 口径（D-38）：/realtime-sim WebSocket 会话编排
    //  相位序 Ping(/echo)→Uplink(/upload 专供 M3)→Handshake→Turns(8 轮)→Done。
    //  协议/时戳合同见 RealtimeWire KDoc；协议致命错误一律抛出（fail-closed 不产部分分）。
    // ─────────────────────────────────────────────────────────────────────

    fun runSim(serverBase: String): Flow<Sample> = channelFlow {
        val raw = serverBase.trim().trimEnd('/')
        val base = ReachabilityProbe.deriveE01Pair(raw)?.second ?: raw

        // ---- Ping（同 v1 口径：12 次 echo 墙钟，丢首个建连样本 → N1/N2）----
        val rtts = ArrayList<Double>()
        for (i in 0 until 12) {
            val t0 = System.nanoTime()
            val r = withContext(Dispatchers.IO) { runCatching { client.echo("$base/api/v1/echo") }.getOrNull() }
            val rttMs = (System.nanoTime() - t0) / 1e6
            if (i > 0 && r != null && r.error == null) rtts.add(rttMs)
            send(Sample(Phase.Ping, median(rtts), quantJitter(rtts), null, null, null, 0, 0, i / 12f * 0.15f, caliber = SIM_CALIBER))
            delay(70)
        }
        val rttMed = median(rtts)
        val nJit = quantJitter(rtts)

        // ---- Uplink（v1 相位原样保留专供 M3：wire 无逐上行帧服务端时戳，chunk_us 仍是唯一权威）----
        val sent = AtomicInteger(0)
        var upResult: AnebClient.UploadResult? = null
        val upJob = launch(Dispatchers.IO) {
            upResult = runCatching {
                client.uploadPaced(
                    "$base/api/v1/upload?run=voice_sim",
                    frames = SIM_M3_FRAMES, frameBytes = FRAME_BYTES, intervalMs = FRAME_INTERVAL_MS,
                ) { n, _ -> sent.set(n) }
            }.getOrNull()
        }
        while (upJob.isActive) {
            send(Sample(Phase.Uplink, rttMed, nJit, null, null, null, sent.get(), 0, (0.15f + sent.get().toFloat() / SIM_M3_FRAMES * 0.15f).coerceIn(0f, 0.3f), caliber = SIM_CALIBER))
            delay(100)
        }
        val upIntervalsUs = upResult?.serverView?.chunkUs.orEmpty().zipWithNext { a, b -> b - a }
        val upJitter = frameJitterP95Ms(upIntervalsUs, FRAME_INTERVAL_MS * 1000)

        // ---- Handshake：WS 升级 + 计划首帧 + session_ready ----
        send(Sample(Phase.Handshake, rttMed, nJit, upJitter, null, null, sent.get(), 0, 0.32f, caliber = SIM_CALIBER))
        val plan = defaultSimPlan(seed = System.nanoTime())
        val session = client.realtimeSim(base, plan)
        session.connect()
        try {
            // 应用层指纹（fail-closed）：WS 101 升级响应不带 X-Aneb-Server（gorilla 自写 101、
            // 绕过 header 中间件，真机实证）；改校验 session_ready 回显的 session_id 与计划一致。
            val ready = awaitControl(session, type = "session_ready", timeoutMs = 15_000)
            check(ready.sessionId == plan.sessionId) { "session_ready id mismatch: ${ready.sessionId}" }

            // ---- Turns：逐轮 上行发帧→commit→收下行(可打断)→turn_summary ----
            val ledger = ArrayList<TurnLedger>(plan.turns.size)
            var framesRecvTotal = 0
            var backpressure = false
            val payload = ByteArray(plan.turns.first().uplinkFrameBytes) { (it * 31 + 17).toByte() }
            for ((i, t) in plan.turns.withIndex()) {
                session.sendText(RealtimeWire.jsonOut.encodeToString(RealtimeWire.TurnStart.serializer(), RealtimeWire.TurnStart(turnId = t.turnId, turnIndex = i)))
                // 上行绝对期限调度（不累积漂移）
                val t0 = android.os.SystemClock.elapsedRealtimeNanos()
                var lastUpEnqUs = 0L
                for (seq in 0 until t.uplinkFrames) {
                    val lagNs = t0 + seq * plan.frameMs * 1_000_000L - android.os.SystemClock.elapsedRealtimeNanos()
                    if (lagNs > 0) delay(lagNs / 1_000_000)
                    lastUpEnqUs = nowUs()
                    session.sendFrame(RealtimeWire.encodeUplink(i, seq, payload))
                }
                if (session.queueSize() > 0) backpressure = true // 背压：入队打戳含排队 → 低置信
                val commitEnqUs = nowUs()
                session.sendText(RealtimeWire.jsonOut.encodeToString(RealtimeWire.SpeechCommit.serializer(), RealtimeWire.SpeechCommit(turnId = t.turnId)))

                // 收下行帧直至 turn_summary；打断轮在第 bargeInAfterFrames 帧后发 barge_in
                val frames = ArrayList<RealtimeWire.DownFrame>(t.plannedDownlinkFrames)
                var bargeEnqUs: Long? = null
                var summary: RealtimeWire.InboundControl? = null
                var summaryArrivalUs = 0L
                kotlinx.coroutines.withTimeout(20_000) {
                    while (summary == null) {
                        when (val m = session.inbound.receive()) {
                            is RealtimeSimSession.In.Frame -> {
                                val f = RealtimeWire.decodeDownlink(m.bytes, m.arrivalUs) ?: continue
                                if (f.turnIndex != i) continue // 迷途帧不入统计
                                frames.add(f)
                                if (t.interrupted && bargeEnqUs == null && frames.size == t.bargeInAfterFrames) {
                                    bargeEnqUs = nowUs()
                                    session.sendText(RealtimeWire.jsonOut.encodeToString(RealtimeWire.BargeIn.serializer(), RealtimeWire.BargeIn(turnId = t.turnId)))
                                }
                            }
                            is RealtimeSimSession.In.Text -> {
                                val c = RealtimeWire.jsonIn.decodeFromString(RealtimeWire.InboundControl.serializer(), m.text)
                                when (c.type) {
                                    "turn_summary" -> { summary = c; summaryArrivalUs = m.arrivalUs }
                                    "error" -> error("realtime-sim error: ${c.message}")
                                    else -> Unit // pong 等
                                }
                            }
                        }
                    }
                }
                framesRecvTotal += frames.size
                ledger.add(TurnLedger(t, commitEnqUs, lastUpEnqUs, bargeEnqUs, frames, summary!!, summaryArrivalUs))
                send(
                    Sample(
                        Phase.Turns, rttMed, nJit, upJitter, null, null, sent.get(), framesRecvTotal,
                        (0.35f + (i + 1f) / plan.turns.size * 0.6f).coerceIn(0f, 0.97f),
                        turnsOk = ledger.count { it.summary.protocolOk == true },
                        caliber = SIM_CALIBER, lowConfidence = backpressure,
                    )
                )
            }
            awaitControl(session, type = "session_summary", timeoutMs = 10_000)

            // ---- KPI 合成（剥离公式见 D-38 设计 §2；服务端时戳同基准两两相减免钟偏）----
            check(ledger.all { it.summary.protocolOk == true }) { "protocol_ok=false in ${ledger.count { it.summary.protocolOk != true }} turns" }
            val ttfbs = ledger.mapNotNull { l ->
                val first = l.frames.firstOrNull() ?: return@mapNotNull null
                val dwellUs = (l.summary.firstDownlinkPreWriteUs ?: return@mapNotNull null) - (l.summary.commitRecvUs ?: return@mapNotNull null)
                (first.arrivalUs - l.commitEnqUs - dwellUs) / 1000.0
            }
            val jitterDevsUs = ledger.flatMap { l ->
                l.frames.zipWithNext { a, b -> abs((b.arrivalUs - a.arrivalUs) - (b.schedUs - a.schedUs)) }
            }
            val mouthEars = ledger.mapNotNull { l ->
                val first = l.frames.firstOrNull() ?: return@mapNotNull null
                val dwellUs = (l.summary.firstDownlinkPreWriteUs ?: return@mapNotNull null) - (l.summary.commitRecvUs ?: return@mapNotNull null)
                (first.arrivalUs - l.lastUpEnqUs - dwellUs) / 1000.0 + CODEC_JB_BUDGET_MS
            }
            val switches = ledger.zipWithNext { prev, next ->
                val first = next.frames.firstOrNull() ?: return@zipWithNext null
                val dwellUs = (next.summary.firstDownlinkPreWriteUs ?: return@zipWithNext null) - (next.summary.commitRecvUs ?: return@zipWithNext null)
                val uplinkUs = next.plan.uplinkFrames.toLong() * plan.frameMs * 1000L
                (first.arrivalUs - prev.summaryArrivalUs - uplinkUs - dwellUs) / 1000.0
            }.filterNotNull()
            val bargeStops = ledger.mapNotNull { l ->
                val enq = l.bargeEnqUs ?: return@mapNotNull null
                val last = l.frames.lastOrNull() ?: return@mapNotNull null
                (last.arrivalUs - enq) / 1000.0
            }
            send(
                Sample(
                    Phase.Done, rttMed, nJit, upJitter, null, null, sent.get(), framesRecvTotal, 1f,
                    ttfbP50Ms = median(ttfbs),
                    ttfbP95Ms = p95(ttfbs),
                    downNetJitterMs = if (jitterDevsUs.size < 2) null else p95(jitterDevsUs.map { it / 1000.0 }),
                    mouthEarProxyMs = median(mouthEars),
                    turnSwitchP50Ms = median(switches),
                    bargeStopMaxMs = bargeStops.maxOrNull(),
                    turnsOk = ledger.count { it.summary.protocolOk == true },
                    caliber = SIM_CALIBER,
                    lowConfidence = backpressure,
                )
            )
        } finally {
            session.cancel()
        }
    }

    private class TurnLedger(
        val plan: RealtimeWire.TurnPlan,
        val commitEnqUs: Long,
        val lastUpEnqUs: Long,
        val bargeEnqUs: Long?,
        val frames: List<RealtimeWire.DownFrame>,
        val summary: RealtimeWire.InboundControl,
        val summaryArrivalUs: Long,
    )

    /** 等待指定 type 的控制消息（跳过其它 TEXT；error 型即抛，fail-closed）。 */
    private suspend fun awaitControl(session: RealtimeSimSession, type: String, timeoutMs: Long): RealtimeWire.InboundControl =
        kotlinx.coroutines.withTimeout(timeoutMs) {
            while (true) {
                val m = session.inbound.receive()
                if (m !is RealtimeSimSession.In.Text) continue
                val c = RealtimeWire.jsonIn.decodeFromString(RealtimeWire.InboundControl.serializer(), m.text)
                when (c.type) {
                    type -> return@withTimeout c
                    "error" -> error("realtime-sim error: ${c.message}")
                    else -> Unit
                }
            }
            @Suppress("UNREACHABLE_CODE")
            error("unreachable")
        }

    private fun nowUs(): Long = android.os.SystemClock.elapsedRealtimeNanos() / 1000

    private fun p95(xs: List<Double>): Double? {
        if (xs.isEmpty()) return null
        val s = xs.sorted()
        val rank = ceil(0.95 * s.size).toInt().coerceIn(1, s.size)
        return s[rank - 1]
    }

    private fun median(xs: List<Double>): Double? {
        if (xs.isEmpty()) return null
        val s = xs.sorted()
        return if (s.size % 2 == 1) s[s.size / 2] else (s[s.size / 2 - 1] + s[s.size / 2]) / 2.0
    }

    private fun quantJitter(xs: List<Double>): Double? {
        if (xs.size < 2) return null
        return median(xs.zipWithNext { a, b -> abs(b - a) })
    }
}
