package com.aneb.probe.adapter

import kotlin.math.ceil

/**
 * 会话时长分布聚合——**纯 JVM**（零 Android 依赖，单测直接调用；spine-3 C6）。
 *
 * 把多个观察会话的 [AdapterObsSnapshot.sessionSpanMs]（前台观察会话跨度 ui-proxy）聚合为
 * session_duration_s_dist 的分布锚点：p50/p90/p99（秒）+ 样本数 + 极值。分位用 nearest-rank
 * （rank=ceil(p×n)，与 [ObsSessionStats] cadence/密度谱 p50 同约定，全仓一致）。
 *
 * ## 口径红线（与 params_fit_approx session_duration_s_dist 的 caliber 一致）
 * - 输入是**前台观察会话跨度**（UI 呈现层代理），**≠真实对话会话时长**——不翻 params 门，
 *   恒 ui-proxy / LOW；
 * - **R-10**：无样本→null，绝不折 0；样本不足分布阈值（[MIN_SAMPLES_FOR_DIST]）时
 *   [SessionDurationDist.belowDistThreshold]=true，调用方须保持 keep_pending、不得升 ui-proxy 以上；
 * - 只做统计不做归因：本对象不判定会话"完成/中断"，只汇总跨度。
 */
object SessionDurationStats {

    /**
     * 建议分布样本阈值（§1.2 判据阶梯：少于此一律 LOW、保持 fit 段不翻门）。低于此仍返回
     * 汇总（供诊断），但 [SessionDurationDist.belowDistThreshold] 置真。
     */
    const val MIN_SAMPLES_FOR_DIST = 30

    /**
     * 聚合会话跨度（ms）为分布。null/非有限/负值样本被剔除（脏值不入统计）；净样本为空→null（R-10）。
     * @param spanMsSamples 各会话的 [AdapterObsSnapshot.sessionSpanMs]（含 null，将被过滤）
     */
    fun aggregate(spanMsSamples: List<Double?>): SessionDurationDist? {
        val clean = spanMsSamples.asSequence()
            .filterNotNull()
            .filter { it.isFinite() && it >= 0.0 }
            .map { it / 1000.0 } // ms → s
            .toList()
            .sorted()
        if (clean.isEmpty()) return null // R-10：无有效样本=未测
        return SessionDurationDist(
            count = clean.size,
            p50Sec = nearestRank(clean, 0.50),
            p90Sec = nearestRank(clean, 0.90),
            p99Sec = nearestRank(clean, 0.99),
            minSec = clean.first(),
            maxSec = clean.last(),
            belowDistThreshold = clean.size < MIN_SAMPLES_FOR_DIST,
        )
    }

    /** nearest-rank 分位（rank=ceil(p×n)，1..n；[sorted] 须已升序非空）。 */
    private fun nearestRank(sorted: List<Double>, p: Double): Double {
        val rank = ceil(p * sorted.size).toInt().coerceIn(1, sorted.size)
        return sorted[rank - 1]
    }
}

/**
 * 会话时长分布快照（秒）。ui-proxy 口径——不构成 params-grade 测量宣称。
 * @param belowDistThreshold 样本 < [SessionDurationStats.MIN_SAMPLES_FOR_DIST]：调用方须保持 keep_pending
 */
data class SessionDurationDist(
    val count: Int,
    val p50Sec: Double,
    val p90Sec: Double,
    val p99Sec: Double,
    val minSec: Double,
    val maxSec: Double,
    val belowDistThreshold: Boolean,
)
