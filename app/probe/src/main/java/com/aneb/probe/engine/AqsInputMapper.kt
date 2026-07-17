package com.aneb.probe.engine

import com.aneb.probe.scoring.KpiCalculator
import com.aneb.probe.scoring.KpiResult
import com.aneb.probe.scoring.KpiValue
import com.aneb.probe.scoring.TokenBehaviorClassifier
import com.aneb.probe.scoring.Validity

/**
 * run 级 AQS 输入映射（P1 范围 5）。纯 JVM、无 Android 依赖。
 *
 * ## 最终口径（合同，随日志 AQS_INPUT_MAP 输出）
 * - **N1/N2 ← S1**：S1 场景 KpiResult 的 n1/n2（其输入 echoSamples 只含 S1 首次
 *   clock_sync 的样本——尾部 clock_sync 只用于 skew 插值，不进 N 组统计）。
 * - **T 组 ← S2（主场景）**：T1/T2（含并列口径）/T3（含并列口径）/T4/T5 全部取自 S2。
 *   S1/S3 的 T 组仅展示（各自 ScenarioResult 落库），不进 AQS。
 * - **U1 ← S3**：1MB 上传（S3 两次 1MB upload_burst）。进 AQS 用**含慢启动**主口径
 *   （u1GoodputMbps）；剔慢启动并列口径仅展示。S2 的 512KB 上传不进 AQS 的 U1。
 * - **U2 ← S2**：tool_loop P95。
 * - **D1 ← S3**（Token 多模态专用，PROFILE_FRAMEWORK §2.2 BM-09）：下行大对象 goodput（`/download`
 *   无限速 2xx 口径）。仅 Token 模式 `scoreToken` 用；v0.1/v0.2 权重表不含 D1，不受影响。
 * - **S1 ← 全场景聚合**（Token 会话完成率，PROFILE_FRAMEWORK §2.2 BM-06）：跨场景**成功轮次占比**
 *   （Σ成功轮次/Σ总轮次，按各场景轮数加权），非中位数——完成率是计数占比口径。仅 Token 模式软否决用。
 *
 * ## 失效语义（按 AqsScorer 现有语义处理，不新增分支）
 * - 某贡献场景 INVALID：其 KpiResult 已被 gate 置 null → 合成结果对应 KpiValue.value=null
 *   → AqsScorer 返回 KPI_MISSING:<清单>（绝不以 0 顶替，R-10）。
 * - 某贡献场景缺失（未跑/被中止）：同上，映射为 KpiValue.empty → KPI_MISSING。
 * - 合成 validity 只取 VALID / VALID_LOW_CONFIDENCE（任一贡献场景低置信即低置信）；
 *   绝不合成 INVALID——单场景失效通过 KPI_MISSING 表达，避免把其余有效场景一并抹掉。
 *
 * ## 取证模式多遍聚合
 * 同一场景多遍（forensic ×3）：逐 KPI 取**有效遍（value 非 null）的中位数**（5.3.6
 * "各场景 3 遍取中位数"）；sampleCount = 有效遍样本数之和；lowConfidence = 任一有效遍
 * 低置信。全部遍 null → 该 KPI null → KPI_MISSING。
 */
object AqsInputMapper {

    /** 机器可解析（无空格）：日志 AQS_INPUT_MAP 行原样输出。 */
    const val MAPPING_DESCRIPTION: String =
        "N1,N2<-S1.first_clock_sync;T1,T2,T3,T4,T5<-S2;U1<-S3.1MB_upload(incl_slow_start_into_AQS);U2<-S2.tool_loop;D1<-S3.download;S1<-all_scenarios.round_success_ratio"

    const val S1 = "s1_chat"
    const val S2 = "s2_coding_agent"
    const val S3 = "s3_multimodal"

    /**
     * @param resultsByScenario profileId → 该场景各遍的 KpiResult（快测=1 个，取证=3 个）
     * @return 供 AqsScorer.score 的合成 run 级 KpiResult
     */
    fun map(resultsByScenario: Map<String, List<KpiResult>>): KpiResult {
        val s1 = resultsByScenario[S1].orEmpty()
        val s2 = resultsByScenario[S2].orEmpty()
        val s3 = resultsByScenario[S3].orEmpty()

        val t1 = medianKpi(s2.map { it.t1TtftMs }, "ms")
        val t2 = medianKpi(s2.map { it.t2ItlP95Ms }, "ms")
        val t2Incl = medianKpi(s2.map { it.t2ItlP95InclCoalescedMs }, "ms")
        val t3 = medianKpi(s2.map { it.t3StallRate }, "ratio")
        val t3Incl = medianKpi(s2.map { it.t3StallRateInclResume }, "ratio")
        val t4 = medianKpi(s2.map { it.t4SevereStallRate }, "ratio")
        val t5 = medianKpi(s2.map { it.t5ResumeP95Ms }, "ms")
        val n1 = medianKpi(s1.map { it.n1RttP50Ms }, "ms")
        val n2 = medianKpi(s1.map { it.n2JitterMs }, "ms")
        val u1 = medianKpi(s3.map { it.u1GoodputMbps }, "Mbps")
        val u1Excl = medianKpi(s3.map { it.u1GoodputExclSlowStartMbps }, "Mbps")
        val u2 = medianKpi(s2.map { it.u2ToolLoopP95Ms }, "ms")
        // D1 ← S3 下行大对象 goodput（Token 多模态专用；v0.1/v0.2 不含 D1，不影响既有合成分）
        val d1 = medianKpi(s3.map { it.d1GoodputMbps }, "Mbps")
        // S1 ← 全场景成功轮次占比（计数口径，非中位数；D-33 统一口径：有逐轮数据的遍用
        // rate×count，无逐轮数据的遍自身作为一轮、成功=validity≠INVALID——INVALID 遍计入分母）
        val s1Kpi = successRateFromRuns(listOf(s1, s2, s3).flatten())

        val all = listOf(t1, t2, t2Incl, t3, t3Incl, t4, n1, n2, u1, u1Excl, u2, d1)
        val anyLowConf = all.any { it.lowConfidence } ||
            listOf(s1, s2, s3).flatten().any { it.validity == Validity.VALID_LOW_CONFIDENCE }
        val validity = if (anyLowConf) Validity.VALID_LOW_CONFIDENCE else Validity.VALID

        // 诊断计数取 T 组来源（S2）各遍求和；无 S2 即 0（诊断字段，不影响评分语义）
        return KpiResult(
            validity = validity,
            invalidReasons = emptyList(),
            seqMissingCount = s2.sumOf { it.seqMissingCount },
            seqDupCount = s2.sumOf { it.seqDupCount },
            seqGapCount = s2.sumOf { it.seqGapCount },
            expectedTokenCount = s2.sumOf { it.expectedTokenCount },
            t1TtftMs = t1,
            t2ItlP95Ms = t2,
            t2ItlP95InclCoalescedMs = t2Incl,
            t3StallRate = t3,
            t3StallRateInclResume = t3Incl,
            t4SevereStallRate = t4,
            t5ResumeP95Ms = t5,
            t5ResumeLatenciesMs = s2.flatMap { it.t5ResumeLatenciesMs },
            n1RttP50Ms = n1,
            n2JitterMs = n2,
            u1GoodputMbps = u1,
            u1GoodputExclSlowStartMbps = u1Excl,
            u2ToolLoopP95Ms = u2,
            d1GoodputMbps = d1,
            s1SessionSuccessRate = s1Kpi,
        )
    }

    /** 「长流」判定门限（单条 token 流 ≥ 此 token 数 ⇒ 稳定性敏感，PROFILE_FRAMEWORK §2.5）。 */
    const val LONG_STREAM_TOKENS = 300

    /**
     * 从冻结 profile 集派生**客观工作量信号**（facet4 双证据分类的输入 A，PROFILE_FRAMEWORK §2.5）。
     * 纯函数、只读 phases 声明值（非测量值）——工作量是 profile 合同的确定性投影：
     * - 上行/轮 = Σ upload_burst bytes；峰均比 = max/mean upload bytes（字节级突发度代理）；
     * - 下行媒体 = Σ download_burst bytes（当前 profile 集无此相位 ⇒ 0，download_burst 接入后自动非零）；
     * - 流长 = 最长单条 token_stream tokens；长流 ⇔ 流长 ≥ [LONG_STREAM_TOKENS]；
     * - 多轮往返 ⇔ 含 tool_loop（rounds 求和）。
     */
    fun workloadFrom(profiles: Collection<ScenarioProfile>): TokenBehaviorClassifier.WorkloadSignal {
        val phases = profiles.flatMap { it.phases }
        val uploadBytes = phases.filter { it.type == ProfilePhase.TYPE_UPLOAD_BURST }.map { it.bytes }
        val uplinkPerRound = uploadBytes.sum()
        val peakToMean = if (uploadBytes.isEmpty()) 1.0 else {
            val mean = uploadBytes.average()
            if (mean > 0.0) uploadBytes.max() / mean else 1.0
        }
        val downlinkMedia = phases.filter { it.type == ProfilePhase.TYPE_DOWNLOAD_BURST }.sumOf { it.bytes }
        val maxStreamTokens = phases.filter { it.type == ProfilePhase.TYPE_TOKEN_STREAM }
            .maxOfOrNull { it.tokens } ?: 0
        val toolRounds = phases.filter { it.type == ProfilePhase.TYPE_TOOL_LOOP }.sumOf { it.rounds }
        return TokenBehaviorClassifier.WorkloadSignal(
            uplinkBytesPerRound = uplinkPerRound,
            peakToMeanRatio = peakToMean,
            downlinkMediaBytes = downlinkMedia,
            tokenStreamLen = maxStreamTokens,
            toolLoopRounds = toolRounds,
            hasThinkPause = phases.any { it.type == ProfilePhase.TYPE_THINK_PAUSE },
            shortContextMultiTurn = toolRounds > 0,
            longStreamOrContinuous = maxStreamTokens >= LONG_STREAM_TOKENS,
        )
    }

    /** S1 完成率全置信最小轮数（低于即 lowConfidence，R-29；快测 3 场景=3 轮恰好达标）。 */
    const val S1_MIN_ROUNDS = 3

    /**
     * 全场景成功轮次占比（计数口径，D-33 统一语义）：Σ成功轮次 / Σ总轮次。
     *
     * - **有逐轮数据的遍**（[KpiResult.s1SessionSuccessRate] 非 null）：贡献 round(rate×count) 成功轮
     *   /count 总轮（未来 roundOutcomes 细粒度接入即走此路）；
     * - **无逐轮数据的遍**（含 INVALID 遍——gate 会把其 s1 置 null）：该遍自身作为**一轮会话**，
     *   成功=传输完整性伞口径 `validity != INVALID`（BM-06：流截断/gap 超限/外部守卫全折叠在
     *   validity；已知边界：上传 http 失败不置 INVALID，经 U1 null→KPI_MISSING 另行表达）。
     *   **INVALID 遍计入分母**——修正旧聚合把失败遍排除在外导致完成率系统性高估的偏差。
     *
     * 完成率是计数占比、非分布分位——不复用 [medianKpi]。无任何遍 → value=null（R-10）。
     */
    private fun successRateFromRuns(runs: List<KpiResult>): KpiValue {
        if (runs.isEmpty()) return KpiValue.empty("ratio")
        var totalRounds = 0
        var successRounds = 0L
        var lowConf = false
        for (r in runs) {
            val rate = r.s1SessionSuccessRate
            if (rate.value != null && rate.sampleCount > 0) {
                totalRounds += rate.sampleCount
                successRounds += Math.round(rate.value * rate.sampleCount)
                if (rate.lowConfidence) lowConf = true
            } else {
                totalRounds += 1
                if (r.validity != Validity.INVALID) successRounds += 1
            }
        }
        return KpiValue(
            value = successRounds.toDouble() / totalRounds,
            unit = "ratio",
            sampleCount = totalRounds,
            lowConfidence = lowConf || totalRounds < S1_MIN_ROUNDS,
        )
    }

    /**
     * 多遍中位数聚合：只聚合 value 非 null 的遍（INVALID 遍已被 gate 置 null，自动剔除）。
     * 全 null → KpiValue.empty（value=null → AqsScorer KPI_MISSING）。
     */
    private fun medianKpi(values: List<KpiValue>, unit: String): KpiValue {
        val valid = values.filter { it.value != null }
        if (valid.isEmpty()) return KpiValue.empty(unit)
        val median = KpiCalculator.percentileOrNull(valid.map { it.value!! }, 0.50)
        return KpiValue(
            value = median,
            unit = unit,
            sampleCount = valid.sumOf { it.sampleCount },
            lowConfidence = valid.any { it.lowConfidence },
        )
    }
}
