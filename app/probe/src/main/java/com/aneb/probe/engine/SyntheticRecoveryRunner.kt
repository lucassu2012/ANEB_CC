package com.aneb.probe.engine

import com.aneb.probe.net.AnebClient
import com.aneb.probe.net.ReachabilityProbe
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.channelFlow
import kotlinx.coroutines.withContext
import kotlin.math.ceil

/**
 * 网络综合性能类·恢复子测（D-40）——走 E-01 `weak-recovery-v1` **合成**合同
 * （TEST_SERVER_CAPABILITIES §5，network_comprehensive_weak_recovery@1.0.0）：
 * 基线整形 ↓5/↑2Mbps+RTT80±20ms;`POST .../recovery` 武装该 run 一次性 2000ms 请求
 * 不可用窗口(202)→窗口内同 run 探针 503+`X-Aneb-Synthetic-Outage: active`→
 * **恢复时长=触发 202 收到→首个成功 echo**;随后 12 请求质量段。
 *
 * 口径边界（与 [ContinuityRecovery] 的**真实**迁移恢复 D-23 严格分开，绝不混算）：
 * - 合成受控窗口 ≠ 真实蜂窝断网/RSRP 弱化/IP 丢包；结论只证明该应用请求窗口与本
 *   app 的恢复探测行为。
 * - **回执 fail-closed**：基线探针必须带防伪头 `X-Aneb-Synthetic-Impairment`=合同 id，
 *   窗口 503 必须带 outage=active——缺失即本 run INVALID（不产分）。
 * - 合同规定**单次事件恒 LOW/INCONCLUSIVE**（不得外推长期恢复可靠性）。
 * - 独立结论（network-recovery-score-v1 语义），不并入容量/时延/AQS 任何分。
 */
class SyntheticRecoveryRunner(private val client: AnebClient = AnebClient()) {

    enum class Phase { Baseline, Arming, Outage, Quality, Done }

    data class Sample(
        val phase: Phase,
        /** 基线（整形后）echo 墙钟中位（ms）；未测 null */
        val baselineRttMs: Double?,
        /** 恢复时长（ms，触发 202→首个成功 echo）；未恢复/未触发 null（R-10） */
        val recoveryMs: Double?,
        /** 窗口内服务器确认的受控中断 503 次数（带 outage=active 头） */
        val outageConfirmed: Int,
        /** 窗口内失败探针总数 */
        val failedProbes: Int,
        /** 质量段成功数/总数 */
        val postSuccess: Int,
        val postTotal: Int,
        /** 质量段 RTT P95（ms）；样本不足 null */
        val postRttP95Ms: Double?,
        /** 防伪回执链完好（基线回执头 + 中断 outage 头都见到） */
        val receiptOk: Boolean,
        /** 是否满足合同质量目标（恢复≤3000ms ∧ 成功率≥95% ∧ RTT P95≤300ms）；不可判 null */
        val meetsTargets: Boolean?,
        val progress: Float,
    ) {
        /** 合同强制标注：单次事件不外推。 */
        val confidence: String get() = "LOW/INCONCLUSIVE(单次合成事件)"
    }

    companion object {
        const val CONTRACT_ID = "network_comprehensive_weak_recovery@1.0.0"
        const val ROUTE = "synthetic/weak-recovery-v1/api/v1"

        // 合同质量目标（TEST_SERVER_CAPABILITIES §5）
        const val TARGET_RECOVERY_MS = 3000.0
        const val TARGET_SUCCESS_RATE = 0.95
        const val TARGET_RTT_P95_MS = 300.0
        const val QUALITY_PROBES = 12

        /** 合同目标判定（纯函数，单测锚定）；任一输入缺失→null（R-10，不可判不硬判）。 */
        fun meetsTargets(recoveryMs: Double?, successes: Int, total: Int, rttP95Ms: Double?): Boolean? {
            if (recoveryMs == null || rttP95Ms == null || total == 0) return null
            val rate = successes.toDouble() / total
            return recoveryMs <= TARGET_RECOVERY_MS && rate >= TARGET_SUCCESS_RATE && rttP95Ms <= TARGET_RTT_P95_MS
        }

        /** 最近秩 P95（ms）；样本 <2 → null（R-10）。 */
        fun p95(xs: List<Double>): Double? {
            if (xs.size < 2) return null
            val s = xs.sorted()
            return s[ceil(0.95 * s.size).toInt().coerceIn(1, s.size) - 1]
        }
    }

    fun run(serverBase: String): Flow<Sample> = channelFlow {
        val raw = serverBase.trim().trimEnd('/')
        val base = ReachabilityProbe.deriveE01Pair(raw)?.second ?: raw
        val runId = "cc-rec-${System.nanoTime().toString(16)}"
        val seed = System.nanoTime() and 0x7FFFFFFF
        var seq = 0
        fun url(endpoint: String) =
            "$base/$ROUTE/$endpoint?impair_run=$runId&impair_seed=$seed&impair_seq=${seq++}"

        suspend fun probe(endpoint: String) =
            withContext(Dispatchers.IO) { client.syntheticPost(url(endpoint)) }

        // ---- Baseline：3 次整形 echo；回执门 fail-closed ----
        val baseRtts = ArrayList<Double>()
        var receiptSeen = false
        repeat(3) { i ->
            val r = probe("echo")
            if (r.httpCode in 200..299) {
                r.wallMs?.let { baseRtts.add(it) }
                if (r.impairmentHeader == CONTRACT_ID) receiptSeen = true
            }
            send(Sample(Phase.Baseline, baseRtts.medianOrNull(), null, 0, 0, 0, 0, null, receiptSeen, null, 0.05f + i * 0.05f))
            delay(150)
        }
        check(receiptSeen) { "缺防伪回执头 X-Aneb-Synthetic-Impairment=$CONTRACT_ID —— run INVALID" }
        val baseline = baseRtts.medianOrNull()

        // ---- Arming：触发一次性 2000ms 中断窗口（202）----
        send(Sample(Phase.Arming, baseline, null, 0, 0, 0, 0, null, true, null, 0.22f))
        val trig = probe("recovery")
        check(trig.httpCode == 202) { "recovery 触发非 202：${trig.httpCode ?: trig.error}" }
        val triggerAckNs = System.nanoTime()

        // ---- Outage：轮询 echo 至首个成功；统计 outage=active 的 503 ----
        var outageConfirmed = 0
        var failedProbes = 0
        var recoveryMs: Double? = null
        val outageDeadlineNs = triggerAckNs + 10_000_000_000L // 10s 上限
        while (System.nanoTime() < outageDeadlineNs) {
            val r = probe("echo")
            if (r.httpCode in 200..299) {
                recoveryMs = (System.nanoTime() - triggerAckNs) / 1e6
                break
            }
            failedProbes++
            if (r.httpCode == 503 && r.outageHeader == "active") outageConfirmed++
            send(
                Sample(
                    Phase.Outage, baseline, null, outageConfirmed, failedProbes, 0, 0, null, true, null,
                    (0.25f + failedProbes * 0.02f).coerceAtMost(0.6f),
                )
            )
            delay(120)
        }
        // 未见服务器确认中断 → 结论不可判（可能窗口错过/未生效），诚实标注
        val outageObserved = outageConfirmed > 0

        // ---- Quality：恢复后 12 请求 ----
        val postRtts = ArrayList<Double>()
        var postSuccess = 0
        for (i in 0 until QUALITY_PROBES) {
            val r = probe("echo")
            if (r.httpCode in 200..299) {
                postSuccess++
                r.wallMs?.let { postRtts.add(it) }
            }
            send(
                Sample(
                    Phase.Quality, baseline, recoveryMs, outageConfirmed, failedProbes,
                    postSuccess, i + 1, p95(postRtts), true, null,
                    0.62f + (i + 1f) / QUALITY_PROBES * 0.35f,
                )
            )
            delay(150)
        }

        val verdict = if (!outageObserved) null else meetsTargets(recoveryMs, postSuccess, QUALITY_PROBES, p95(postRtts))
        send(
            Sample(
                Phase.Done, baseline, recoveryMs, outageConfirmed, failedProbes,
                postSuccess, QUALITY_PROBES, p95(postRtts), true, verdict, 1f,
            )
        )
    }

    private fun List<Double>.medianOrNull(): Double? {
        if (isEmpty()) return null
        val s = sorted()
        return if (s.size % 2 == 1) s[s.size / 2] else (s[s.size / 2 - 1] + s[s.size / 2]) / 2.0
    }
}
