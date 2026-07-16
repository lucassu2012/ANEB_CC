package com.aneb.probe.engine

import com.aneb.probe.net.AnebClient
import com.aneb.probe.net.ReachabilityProbe
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

    enum class Phase { Ping, Uplink, Downlink, Done }

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
