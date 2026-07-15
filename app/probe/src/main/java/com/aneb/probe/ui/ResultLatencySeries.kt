package com.aneb.probe.ui

import com.aneb.probe.data.TokenEventEntity
import com.aneb.probe.scoring.KpiCalculator

/**
 * 专业结果视图"流式时延剖面"迷你图的**只读聚合**（纯 JVM，可单测）。
 *
 * 取一次 run 已落库的逐 token 到达序列（`token_event`），算**相邻 token 间隔时延（ITL）时序**
 * ——最能反映智能体流式"一顿一顿地出"的实时体验（尖峰=卡顿，对应 T2/T3/T4，流式在 AQS 占 55%）。
 * 优先取 S2 编码场景（AQS 的 T 组来源）中到达样本最多的一条流。
 *
 * ## 红线
 * - **R-10**：到达时刻为 null（丢弃/失败 token）的样本不参与间隔计算，绝不以 0 顶替。
 * - 分位数走 [KpiCalculator.percentileOrNull]（最近秩，R-29 同口径），非本层新算。
 * - 本序列为**展示态可视化**，非 KPI T2 精确口径（T2 另有合帧/剔除规则，见 KPI 明细卡）；
 *   仅作流式剖面直观呈现，标注"展示态"避免被当作评级结论。
 */
data class ResultLatencySeries(
    /** 相邻 token 间隔时延时序（ms），按 token 顺序 */
    val itlMs: List<Double>,
    /** 峰值（max）；无样本 null */
    val peakMs: Double?,
    /** P95（最近秩）；无样本 null */
    val p95Ms: Double?,
    /** 中位数；无样本 null */
    val medianMs: Double?,
    /** 参与计算的到达样本数 */
    val tokenCount: Int,
    /** 来源标签（如 "S2 编码 · 187 token"） */
    val sourceLabel: String,
) {
    /** 有足够样本可画图 */
    val hasSeries: Boolean get() = itlMs.size >= 2

    companion object {
        val EMPTY = ResultLatencySeries(emptyList(), null, null, null, 0, "")

        /** 严重卡顿线（ms，KPI 文档 T4）；展示态标注用 */
        const val SEVERE_STALL_MS = 1000.0

        /** 卡顿线（ms，KPI 文档 T3）；展示态标注用 */
        const val STALL_MS = 200.0

        fun of(events: List<TokenEventEntity>): ResultLatencySeries {
            if (events.isEmpty()) return EMPTY
            // 按 (场景实例, 流) 分组；每组按 seq 排序取非空到达时刻
            val groups = events.groupBy { it.scenarioKey to it.streamIndex }
            val candidates = groups.entries
                .map { (key, evs) -> key to evs.sortedBy { it.seq }.mapNotNull { it.arrivalNanos } }
                .filter { it.second.size >= 3 } // 至少 3 个到达 → ≥2 个间隔
            if (candidates.isEmpty()) return EMPTY

            // 优先 S2 编码场景（T 组来源）；组内取到达样本最多的一条流
            val s2 = candidates.filter { it.first.first.startsWith("s2") }
            val chosen = (if (s2.isNotEmpty()) s2 else candidates).maxByOrNull { it.second.size }!!
            val arrivals = chosen.second

            // 相邻间隔（ms）；单调时间轴理应非负，负值（异常）保守剔除
            val itl = arrivals.zipWithNext { a, b -> (b - a) / 1_000_000.0 }.filter { it >= 0.0 }
            if (itl.size < 2) return EMPTY

            return ResultLatencySeries(
                itlMs = itl,
                peakMs = itl.maxOrNull(),
                p95Ms = KpiCalculator.percentileOrNull(itl, 0.95),
                medianMs = KpiCalculator.percentileOrNull(itl, 0.50),
                tokenCount = arrivals.size,
                sourceLabel = "${scenarioShort(chosen.first.first)} · ${arrivals.size} token",
            )
        }

        /** 场景实例键（"s2_coding_agent#0"）→ 简短标签 */
        private fun scenarioShort(scenarioKey: String): String =
            when (scenarioKey.substringBefore('#')) {
                "s1_chat" -> "S1 对话"
                "s2_coding_agent" -> "S2 编码"
                "s3_multimodal" -> "S3 多模态"
                else -> scenarioKey.substringBefore('#')
            }
    }
}
