package com.aneb.probe.ui

import com.aneb.probe.scoring.AqsScorer
import com.aneb.probe.scoring.TokenBehaviorClassifier

/**
 * Token 模式 Profile ↔ 打分/建议引擎的**纯 JVM 桥接**（无 Compose 依赖，可独立单测）。
 *
 * 把 [TestModeProfile] 的 4-facet 契约投影为打分层所需的入参，闭合两条单一事实源链路（INV-3）：
 * - **facet4 按模态选权重表**：纯文本子场景（如 TK-1，U1/D1 设计缺省）走 `WEIGHTS_TOKEN_TXT`，
 *   其余多模态走 profile 声明的 [ScoringModelSpec.weightsTableId]（默认 `WEIGHTS_TOKEN_MM`）。
 * - **facet2 → facet4 建议目标投影**：网络建议行的门限**只来自** facet2 [MetricSpec.target] 的良锚，
 *   不在 facet4 重复硬编码阈值——避免 UI 与打分引擎两处漂移。
 */
object TokenScoringBridge {

    /**
     * 按模态解析权重表 id。
     *
     * @param profile Token 模式 profile（读其 facet4 声明的默认表）
     * @param pureText 本次是否为纯文本子场景（U1/D1 设计缺省）——true 走 TXT 表
     * @return AqsScorer.TOKEN_WEIGHT_TABLES 中存在的表 id
     */
    fun weightsTableIdFor(profile: TestModeProfile, pureText: Boolean): String {
        val id = if (pureText) "WEIGHTS_TOKEN_TXT" else (profile.scoring?.weightsTableId ?: "WEIGHTS_TOKEN_MM")
        require(AqsScorer.TOKEN_WEIGHT_TABLES.containsKey(id)) { "未知 Token 权重表: $id" }
        return id
    }

    /**
     * facet2 → 建议目标投影：取 profile 全部**有良锚**的指标（业务∪网络），产出
     * `KPI id → RecTarget`（name/良锚门限/单位/方向），供 [TokenBehaviorClassifier.recommend] 组行。
     * 无良锚（如纯元数据/不可测项）的指标跳过。
     */
    fun recTargets(profile: TestModeProfile): Map<String, TokenBehaviorClassifier.RecTarget> =
        profile.metricSpecs.mapNotNull { m ->
            val good = m.target.good ?: return@mapNotNull null
            m.id to TokenBehaviorClassifier.RecTarget(
                name = m.name,
                goodThreshold = good,
                unit = m.unit,
                higherBetter = m.direction == Direction.HIGHER_BETTER,
            )
        }.toMap()

    /**
     * 一步到位：分类 + 建议（facet2 目标 + facet4 分类，单一事实源）。
     *
     * @param profile Token 模式 profile
     * @param subScores AQS 子分（[AqsScorer.AqsResult.subScores]）
     * @param pureText 是否纯文本子场景（决定权重表）
     * @param workload 客观工作量信号（输入 A）
     * @return 行为发现 + 对应建议行（一一对应，行序同 findings）
     */
    fun classifyAndRecommend(
        profile: TestModeProfile,
        subScores: Map<String, Double>,
        pureText: Boolean,
        workload: TokenBehaviorClassifier.WorkloadSignal,
    ): Pair<List<TokenBehaviorClassifier.BehaviorFinding>, List<String>> {
        val tableId = weightsTableIdFor(profile, pureText)
        val weights = AqsScorer.TOKEN_WEIGHT_TABLES.getValue(tableId)
        val findings = TokenBehaviorClassifier.classify(subScores, weights, workload)
        val lines = TokenBehaviorClassifier.recommend(findings, recTargets(profile))
        return findings to lines
    }
}
