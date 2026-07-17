package com.aneb.probe.ui

import com.aneb.probe.scoring.AqsScorer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonPrimitive

/**
 * 专业结果视图的 **AQS 真实子分分解**（组 → KPI → 贡献分），纯 JVM、无 Android，可单测。
 *
 * ## 数据来源（D-02：展示层不重算测量）
 * 子分**不是本层现算**：它们是 run 结束时 [AqsScorer] 计算、并**已随 /results 上报体落库**
 * 的产物（`report_body.body` → `run.aqs.sub_scores`，键=KPI id、值=0–100 子分）。本层只做：
 * 1) 解析既有落库子分；2) × [AqsScorer.WEIGHTS] / [AqsScorer.WEIGHTS_V02]（**直接引用测量层
 * 权重表单一事实源**，不复制门限/权重）得每 KPI 贡献分。绝不重算 AqsScorer 内部逻辑，
 * 也绝不重定义任何门限/权重（红线 §2.3）。
 *
 * ## 红线
 * - R-28：AQS 数字旁必须并列三大组子分（流式/上行/基线），本分解即其数据来源。
 * - R-10：run 不可计算（sub_scores 缺失）→ 返回 `null`；展示层据此走"不可计算 / 分级近似"
 *   分支，**绝不以 0 顶替**任何 KPI 的子分或贡献分。
 *
 * 子分档色：KPI 四级门限锚点（5.2）与 AQS 分档线同锚（85/70/55），故 `aqsGrade(子分)`
 * 恰好复现该 KPI 的四级分级——[KpiContribution.gradeKey] 由子分单源推得，无需回读原始 KPI 值。
 */
object ResultAqsBreakdown {

    private val json = Json { ignoreUnknownKeys = true }

    /** 组内一个 KPI 的真实贡献分。 */
    data class KpiContribution(
        val id: String,
        /** 中文短名（如"首字响应"） */
        val label: String,
        /** 权重（分数，如 0.20），来自 [AqsScorer.WEIGHTS] 单一事实源 */
        val weight: Double,
        /** AqsScorer 落库子分 0..100 */
        val subScore: Double,
    ) {
        /** 该 KPI 满贡献分（= 权重×100，如 20.0） */
        val maxPoints: Double get() = weight * 100.0

        /** 实际贡献分（= 子分×权重，如 97.3×0.20=19.46） */
        val contributionPoints: Double get() = subScore * weight

        /**
         * 子分档色键（KpiGrading 常量）：对子分按 AQS 分档线（85/70/55）取档。
         * KPI 门限锚点与 AQS 分档线同锚，故与该 KPI 原始值的四级分级一致——**除恰好落在
         * 锚点边界的样本外**：aqsGrade 上界用 ≥、KpiGrading 上界用 <，边界处可差一档
         * （纯呈现差异，不影响任何分值；门限口径以 KpiGrading 为准，本层不重定义）。
         */
        val gradeKey: String get() = ResultFormat.aqsGrade(subScore)
    }

    /** 一个 AQS 组（流式/上行/基线/连续性）。 */
    data class Group(
        val label: String,
        val kpis: List<KpiContribution>,
    ) {
        /** 组权重（= 成员权重之和） */
        val weight: Double get() = kpis.sumOf { it.weight }

        /** 组满贡献分（= 组权重×100） */
        val maxPoints: Double get() = weight * 100.0

        /** 组实际小计贡献分（= 成员贡献分之和） */
        val subtotalPoints: Double get() = kpis.sumOf { it.contributionPoints }
    }

    /** 一次 run 的 AQS 分解。 */
    data class Breakdown(
        val aqsVersion: String,
        /** 综合分 0..100；上报体记录的 run.aqs.score */
        val score: Double?,
        val lowConfidence: Boolean,
        val vetoApplied: Boolean,
        val groups: List<Group>,
    )

    /** 组结构（KPI 文档 5.4）：KPI id 顺序 + 中文短名；权重来自 [AqsScorer]（不在此复制）。 */
    private data class Slot(val id: String, val label: String)

    private val STREAM = listOf(Slot("T1", "首字响应"), Slot("T3", "卡顿率"), Slot("T2", "Token 间隔"))
    private val UPLINK = listOf(Slot("U1", "上行"), Slot("U2", "工具循环"))
    private val BASELINE = listOf(Slot("N1", "RTT"), Slot("N2", "抖动"))
    private val CONTINUITY = listOf(Slot("C1", "会话中断"), Slot("C2", "切换恢复"))

    /**
     * v0.1 组结构（label → KPI id）：供展示层在**无落库子分**时按同构分组做分级近似
     * （R-28 头条三组子分并列的降级路径，见 ResultScreen.ApproxGroupSubscoreRow）。
     * 真实分解仍走 [fromReportJson]，绝不用此近似替代落库子分（D-02）。
     */
    val GROUP_KPI_IDS_V01: List<Pair<String, List<String>>> = listOf(
        "流式体验" to STREAM.map { it.id },
        "上行突发" to UPLINK.map { it.id },
        "网络基线" to BASELINE.map { it.id },
    )

    /**
     * 从落库上报体 JSON 解析真实子分分解。
     *
     * @return 组→KPI→贡献分；上报体缺失/无法解析/无 sub_scores（不可计算 run）一律 `null`。
     */
    fun fromReportJson(reportJson: String?): Breakdown? =
        parseNode(reportJson, nodeKey = "aqs", versionOverride = null)

    /**
     * v0.2 并列出分分解（读 `run.aqs_v02`，含连续性组，权重取 [AqsScorer.WEIGHTS_V02]）。
     * 无 v0.2 分支（run 期无 continuity 数据）→ null。D-26 起 ResultReporter additive 写入该节点。
     */
    fun v02FromReportJson(reportJson: String?): Breakdown? =
        parseNode(reportJson, nodeKey = "aqs_v02", versionOverride = AqsScorer.AQS_VERSION_V02)

    private fun parseNode(reportJson: String?, nodeKey: String, versionOverride: String?): Breakdown? {
        if (reportJson.isNullOrBlank()) return null
        return runCatching {
            val root = json.parseToJsonElement(reportJson) as? JsonObject ?: return@runCatching null
            val topVersion = root["aqs_version"]?.jsonPrimitive?.contentOrNull ?: AqsScorer.AQS_VERSION
            val aqs = (root["run"] as? JsonObject)?.get(nodeKey) as? JsonObject ?: return@runCatching null
            // 版本优先取节点内 aqs_version（v0.2 节点自带），兜底 versionOverride，再兜底顶层
            val version = aqs["aqs_version"]?.jsonPrimitive?.contentOrNull ?: versionOverride ?: topVersion
            parseAqs(aqs, version)
        }.getOrNull()
    }

    /**
     * Token facet4 结论输入（`run.aqs_token` 落库数据，D-29）。
     *
     * @param subScores 分类用子分：aqs_token.sub_scores 非空用之；空（D1 未接入期不可计算）
     *   回落 run.aqs（v0.1）子分——分类只用交集 KPI，诚实降级
     * @param subScoresFromFallback 是否走了 v0.1 回落（UI 据此标注口径）
     */
    data class TokenConclusionInput(
        val score: Double?,
        val notComputableReason: String?,
        val weightsTableId: String,
        val subScores: Map<String, Double>,
        val subScoresFromFallback: Boolean,
        val workload: com.aneb.probe.scoring.TokenBehaviorClassifier.WorkloadSignal,
        /** S1 会话完成率（D-33 实测；旧 run 无字段=null 不渲染，R-10）。 */
        val s1Rate: Double? = null,
        /** S1 总轮次。 */
        val s1Rounds: Int? = null,
        /** S1 软否决已触发（<95% 封顶 70 / <90% 封顶 54）。 */
        val s1VetoApplied: Boolean = false,
    )

    /**
     * 解析 `run.aqs_token`（分数/子分/权重表/工作量）供 facet4 结论卡。节点缺失（旧 run）/
     * 无 workload / 连回落子分都没有 → null（卡不渲染，R-10 不编造）。
     */
    fun tokenConclusionFromReportJson(reportJson: String?): TokenConclusionInput? {
        if (reportJson.isNullOrBlank()) return null
        return runCatching {
            val root = json.parseToJsonElement(reportJson) as? JsonObject ?: return@runCatching null
            val run = root["run"] as? JsonObject ?: return@runCatching null
            val tok = run["aqs_token"] as? JsonObject ?: return@runCatching null
            val wl = tok["workload"] as? JsonObject ?: return@runCatching null

            fun subsOf(node: JsonObject?): Map<String, Double> =
                (node?.get("sub_scores") as? JsonObject)?.mapNotNull { (k, v) ->
                    (v as? JsonPrimitive)?.doubleOrNull?.let { k to it }
                }?.toMap() ?: emptyMap()

            val tokenSubs = subsOf(tok)
            val fallback = tokenSubs.isEmpty()
            val subs = if (fallback) subsOf(run["aqs"] as? JsonObject) else tokenSubs
            if (subs.isEmpty()) return@runCatching null

            TokenConclusionInput(
                score = tok["score"]?.jsonPrimitive?.doubleOrNull,
                notComputableReason = tok["not_computable_reason"]?.jsonPrimitive?.contentOrNull,
                weightsTableId = tok["weights_table_id"]?.jsonPrimitive?.contentOrNull ?: "WEIGHTS_TOKEN_MM",
                subScores = subs,
                subScoresFromFallback = fallback,
                s1Rate = tok["s1_session_success_rate"]?.jsonPrimitive?.doubleOrNull,
                s1Rounds = tok["s1_rounds"]?.jsonPrimitive?.intOrNull,
                s1VetoApplied = tok["s1_veto_applied"]?.jsonPrimitive?.booleanOrNull ?: false,
                workload = com.aneb.probe.scoring.TokenBehaviorClassifier.WorkloadSignal(
                    uplinkBytesPerRound = wl["uplink_bytes_per_round"]?.jsonPrimitive?.doubleOrNull?.toLong() ?: 0L,
                    peakToMeanRatio = wl["peak_to_mean_ratio"]?.jsonPrimitive?.doubleOrNull ?: 1.0,
                    downlinkMediaBytes = wl["downlink_media_bytes"]?.jsonPrimitive?.doubleOrNull?.toLong() ?: 0L,
                    tokenStreamLen = wl["token_stream_len"]?.jsonPrimitive?.doubleOrNull?.toInt() ?: 0,
                    toolLoopRounds = wl["tool_loop_rounds"]?.jsonPrimitive?.doubleOrNull?.toInt() ?: 0,
                    hasThinkPause = wl["has_think_pause"]?.jsonPrimitive?.booleanOrNull ?: false,
                    shortContextMultiTurn = wl["short_context_multi_turn"]?.jsonPrimitive?.booleanOrNull ?: false,
                    longStreamOrContinuous = wl["long_stream_or_continuous"]?.jsonPrimitive?.booleanOrNull ?: false,
                ),
            )
        }.getOrNull()
    }

    private fun parseAqs(aqs: JsonObject, version: String): Breakdown? {
        val subObj = aqs["sub_scores"] as? JsonObject ?: return null
        val subs: Map<String, Double> = subObj.mapNotNull { (k, v) ->
            (v as? JsonPrimitive)?.doubleOrNull?.let { k to it }
        }.toMap()
        if (subs.isEmpty()) return null

        // 版本判定：以节点/上报体 aqs_version 为准，兜底看是否出现 C 组子分。
        val isV02 = version == AqsScorer.AQS_VERSION_V02 || subs.containsKey("C1") || subs.containsKey("C2")
        val weights = if (isV02) AqsScorer.WEIGHTS_V02 else AqsScorer.WEIGHTS

        fun group(label: String, slots: List<Slot>): Group? {
            val kpis = slots.mapNotNull { slot ->
                val ss = subs[slot.id] ?: return@mapNotNull null
                val w = weights[slot.id] ?: return@mapNotNull null
                KpiContribution(id = slot.id, label = slot.label, weight = w, subScore = ss)
            }
            return if (kpis.isEmpty()) null else Group(label, kpis)
        }

        val groups = buildList {
            group("流式体验", STREAM)?.let { add(it) }
            group("上行突发", UPLINK)?.let { add(it) }
            group("网络基线", BASELINE)?.let { add(it) }
            if (isV02) group("连续性", CONTINUITY)?.let { add(it) }
        }
        if (groups.isEmpty()) return null

        return Breakdown(
            aqsVersion = version,
            score = aqs["score"]?.jsonPrimitive?.doubleOrNull,
            lowConfidence = aqs["low_confidence"]?.jsonPrimitive?.booleanOrNull ?: false,
            vetoApplied = aqs["veto_applied"]?.jsonPrimitive?.booleanOrNull ?: false,
            groups = groups,
        )
    }
}
