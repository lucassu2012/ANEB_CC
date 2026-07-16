package com.aneb.probe.scoring

/**
 * Token 体验 facet-4 行为特征分类 + 网络建议输出（Profile 框架 v1.0，PROFILE_FRAMEWORK §2.5）。
 *
 * 纯 JVM、无 Android 依赖、确定性——把「客观工作量信号」与「本次测量的绑定约束」两路证据合成，
 * 产出用户可读的「行为特征 + 网络建议」双条结论（UI 只做渲染，本模块不含展示）。
 *
 * ## 双证据（dual-evidence）
 * - **输入 A（客观工作量，[WorkloadSignal]）**：来自 `ScenarioProfile.phases` 的量值——∑上行字节/轮、
 *   峰均比、下行媒体字节、token 流长、tool_loop rounds、think_pause 有无、短上下文多轮/长流连续。
 *   A 决定「这个业务声明了哪个行为特征」（即该特征是否与本业务相关）。
 * - **输入 B（本次测量，AQS 子分×权重）**：`painᵢ = weightᵢ × (100 − subScoreᵢ)`；某绑定 KPI pain 越高
 *   ⇔ 分越低 ⇔ 网络越「未满足」该特征。B 决定「网络是否满足了 A 声明的特征」。
 *
 * 标签仅当 A 成立时发（业务相关），并由 B 报告是否被网络满足 + 量化强度（该 facet pain ÷ 总 pain）。
 * 多标签可并存（s3 典型「上行突发+下行大带宽+稳定性」；s1 典型「低时延」单标）。
 *
 * ## 与打分引擎的关系（复用，不重写）
 * 直接吃 [AqsScorer.AqsResult.subScores] 与所选权重表（[AqsScorer.WEIGHTS_TOKEN_MM] 等），
 * 不重算任何门限/口径（INV-1/INV-3）。
 */
object TokenBehaviorClassifier {

    /** 上行突发工作量门限（∑上行/轮 ≥10MB 发「上行突发」标）。 */
    const val UPLINK_BURST_BYTES: Long = 10L * 1024 * 1024

    /** 峰均比高判定（突发性强）。 */
    const val PEAK_TO_MEAN_HIGH: Double = 3.0

    /** 下行大带宽工作量门限（下行媒体 ≥10MB 发「下行大带宽」标）。 */
    const val DOWNLINK_MEDIA_BYTES: Long = 10L * 1024 * 1024

    /** 「网络已满足」的子分阈值（良级=70；绑定 KPI 子分≥此值视为满足）。 */
    const val SATISFIED_SUBSCORE: Double = 70.0

    /**
     * 客观工作量信号（输入 A）。由 `ScenarioProfile.phases` 落库量值填充；本模块只读不改。
     *
     * @param uplinkBytesPerRound ∑上行字节/轮
     * @param peakToMeanRatio 上行速率峰均比（突发性）
     * @param downlinkMediaBytes 下行媒体字节（图/视频 bulk）
     * @param tokenStreamLen token 流长度（token 数）
     * @param toolLoopRounds tool_loop 轮数（agentic）
     * @param hasThinkPause 是否含 think_pause
     * @param shortContextMultiTurn 短上下文多轮（低时延往返敏感）
     * @param longStreamOrContinuous 长流 ∨ 会话连续（稳定性敏感）
     */
    data class WorkloadSignal(
        val uplinkBytesPerRound: Long = 0,
        val peakToMeanRatio: Double = 1.0,
        val downlinkMediaBytes: Long = 0,
        val tokenStreamLen: Int = 0,
        val toolLoopRounds: Int = 0,
        val hasThinkPause: Boolean = false,
        val shortContextMultiTurn: Boolean = false,
        val longStreamOrContinuous: Boolean = false,
    )

    /**
     * 一条行为特征发现。
     *
     * @param tag 行为特征标签
     * @param triggerEvidence 触发证据（工作量量值，可读）
     * @param satisfiedByNetwork 绑定 KPI 是否被网络满足（子分≥良级）
     * @param intensity 量化强度 = 该 facet pain ÷ 总 pain（0..1；总 pain=0 时为 0）
     * @param bindingKpis 绑定 KPI 清单
     */
    data class BehaviorFinding(
        val tag: TestBehaviorTag,
        val triggerEvidence: String,
        val satisfiedByNetwork: Boolean,
        val intensity: Double,
        val bindingKpis: List<String>,
    )

    /** 行为特征标签（与 UI 层 BehaviorTag 同义，此处 scoring 包内独立枚举，避免 ui→scoring 反向依赖）。 */
    enum class TestBehaviorTag { UPLINK_BURST, LOW_LATENCY, DOWNLINK_BANDWIDTH, STABILITY }

    /**
     * 双证据行为分类。
     *
     * @param subScores AQS 子分（KPI id → 0..100），来自 [AqsScorer.AqsResult.subScores]
     * @param weights 所选权重表（KPI id → 权重），来自 [AqsScorer.TOKEN_WEIGHT_TABLES]
     * @param workload 客观工作量信号（输入 A）
     * @return 命中的行为特征清单（按强度降序；多标签可并存）
     */
    fun classify(
        subScores: Map<String, Double>,
        weights: Map<String, Double>,
        workload: WorkloadSignal,
    ): List<BehaviorFinding> {
        // pain_i = weight_i × (100 − subScore_i)，仅对同时在子分与权重表中的 KPI
        val pain: Map<String, Double> = weights.keys
            .filter { subScores.containsKey(it) }
            .associateWith { id -> weights.getValue(id) * (100.0 - subScores.getValue(id)) }
        val totalPain = pain.values.sum()

        fun painOf(vararg ids: String): Double = ids.sumOf { pain[it] ?: 0.0 }
        fun intensity(vararg ids: String): Double = if (totalPain <= 0.0) 0.0 else painOf(*ids) / totalPain
        fun satisfied(vararg ids: String): Boolean =
            ids.all { (subScores[it] ?: 100.0) >= SATISFIED_SUBSCORE }

        val findings = ArrayList<BehaviorFinding>()

        // 上行突发：∑上行/轮 ≥10MB ∨ 峰均比高 → 发标；U1 绑定
        if (workload.uplinkBytesPerRound >= UPLINK_BURST_BYTES || workload.peakToMeanRatio >= PEAK_TO_MEAN_HIGH) {
            findings.add(
                BehaviorFinding(
                    tag = TestBehaviorTag.UPLINK_BURST,
                    triggerEvidence = "∑上行/轮=${humanBytes(workload.uplinkBytesPerRound)}，峰均比=${fmt(workload.peakToMeanRatio)}",
                    satisfiedByNetwork = satisfied("U1"),
                    intensity = intensity("U1"),
                    bindingKpis = listOf("U1"),
                )
            )
        }

        // 低时延：短上下文多轮 ∧ (T1+N1) → 发标
        if (workload.shortContextMultiTurn) {
            findings.add(
                BehaviorFinding(
                    tag = TestBehaviorTag.LOW_LATENCY,
                    triggerEvidence = "短上下文多轮往返（tool_loop=${workload.toolLoopRounds}）",
                    satisfiedByNetwork = satisfied("T1", "N1"),
                    intensity = intensity("T1", "N1"),
                    bindingKpis = listOf("T1", "N1"),
                )
            )
        }

        // 下行大带宽：下行媒体 ≥10MB ∧ D1 在表 → 发标
        if (workload.downlinkMediaBytes >= DOWNLINK_MEDIA_BYTES && weights.containsKey("D1")) {
            findings.add(
                BehaviorFinding(
                    tag = TestBehaviorTag.DOWNLINK_BANDWIDTH,
                    triggerEvidence = "下行媒体=${humanBytes(workload.downlinkMediaBytes)}",
                    satisfiedByNetwork = satisfied("D1"),
                    intensity = intensity("D1"),
                    bindingKpis = listOf("D1"),
                )
            )
        }

        // 稳定性：长流 ∨ 会话连续 ∧ (T2/T3/N2) → 发标
        if (workload.longStreamOrContinuous) {
            findings.add(
                BehaviorFinding(
                    tag = TestBehaviorTag.STABILITY,
                    triggerEvidence = "长流/会话连续（token 流长=${workload.tokenStreamLen}${if (workload.hasThinkPause) "，含 think" else ""}）",
                    satisfiedByNetwork = satisfied("T2", "T3", "N2"),
                    intensity = intensity("T2", "T3", "N2"),
                    bindingKpis = listOf("T2", "T3", "N2"),
                )
            )
        }

        return findings.sortedByDescending { it.intensity }
    }

    /**
     * 建议 SLA 目标行（PROFILE_FRAMEWORK §2.5「建议 SLA」段）：只对命中标签的绑定 facet 输出，
     * 避免全量堆砌。X=目标分级门限（默认良锚），P=[slaPercentile]（默认 95%）。
     *
     * @param findings [classify] 输出
     * @param targets 绑定 KPI 的目标（KPI id → [RecTarget]）；缺失的 KPI 跳过
     * @param slaPercentile 达标比例分位（默认 0.95）
     * @return 每命中标签一条可读建议行（未满足的标签在行尾标注「（本次未满足）」）
     */
    fun recommend(
        findings: List<BehaviorFinding>,
        targets: Map<String, RecTarget>,
        slaPercentile: Double = 0.95,
    ): List<String> {
        val pct = (slaPercentile * 100).toInt()
        return findings.map { f ->
            val parts = f.bindingKpis.mapNotNull { id ->
                targets[id]?.let { t ->
                    val cmp = if (t.higherBetter) "≥" else "≤"
                    "${t.name}${cmp}${fmt(t.goodThreshold)}${t.unit}"
                }
            }
            val head = tagLabel(f.tag)
            val body = if (parts.isEmpty()) "（无绑定门限）" else parts.joinToString("、") + " 达 $pct%"
            val suffix = if (f.satisfiedByNetwork) "" else "（本次未满足）"
            "$head：$body$suffix"
        }
    }

    /** 建议模板绑定 KPI 目标（从 MetricSpec.QualityTarget 良锚投影而来）。 */
    data class RecTarget(
        val name: String,
        val goodThreshold: Double,
        val unit: String,
        val higherBetter: Boolean,
    )

    private fun tagLabel(tag: TestBehaviorTag): String = when (tag) {
        TestBehaviorTag.UPLINK_BURST -> "上行突发→上行条"
        TestBehaviorTag.LOW_LATENCY -> "低时延→TTFT/RTT 条"
        TestBehaviorTag.DOWNLINK_BANDWIDTH -> "下行大带宽→下行条"
        TestBehaviorTag.STABILITY -> "稳定性→ITL/抖动/stall 条"
    }

    private fun fmt(v: Double): String = when {
        v == v.toLong().toDouble() -> v.toLong().toString()
        // <1 的小数（如卡顿率良锚 0.02）保留两位有效小数——%.1f 会把 0.02 显示成误导性的 "0.0"
        kotlin.math.abs(v) < 1.0 -> String.format("%.2f", v).trimEnd('0').trimEnd('.')
        else -> String.format("%.1f", v)
    }

    private fun humanBytes(b: Long): String = when {
        b >= 1024L * 1024 * 1024 -> "${fmt(b / 1024.0 / 1024 / 1024)}GB"
        b >= 1024L * 1024 -> "${fmt(b / 1024.0 / 1024)}MB"
        b >= 1024L -> "${fmt(b / 1024.0)}KB"
        else -> "${b}B"
    }
}
