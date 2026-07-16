package com.aneb.probe.scoring

import kotlin.math.min

/**
 * AQS 综合评分（aqs v0.1，KPI 文档 5.4；门限常量表 = agent-qoe-kpi v0.1，5.2）。
 *
 * ## 映射规则
 * 每个 KPI 按四级门限锚点做分段线性映射：优/良边界=85 分、良/可=70 分、可/差=55 分，
 * 级内线性插值，上限 100、下限 0。
 *
 * 5.4 只定义了 85/70/55 三个内部锚点（红队 R-28：优档上锚与差档下锚未定义区）。
 * 本实现按以下**显式补全锚点**（aqs v0.1 实现内定义，随版本号锁定、待阶段一标定修订）：
 * - 时延/比率类（低者优）：0 → 100 分；3×(可/差边界) → 0 分；
 * - U1 吞吐（高者优）：0 Mbps → 0 分；100 Mbps → 100 分。
 * 锚点之间线性插值，越界 clamp 到端点分。
 *
 * ## 权重（MVP，5.4 表）
 * T1 20% + T3 20% + T2 15% + U1 15% + U2 10% + N1 10% + N2 10%（合计 100%）。
 * T4 为一票否决项：T4 > 1% 时 AQS 封顶 54（不参与加权）。
 *
 * ## 进入评分的口径
 * - T2：主口径（合帧组内只保留组首间隔，5.4）；
 * - T3：主口径（不含 resume_latency，T5 已剔除，R-09）；
 * - U1：含慢启动主口径（2xx 有效 goodput）；
 * - T5 不进 AQS（5.1）。
 *
 * ## 有效性语义（5.4 / R-10）
 * - INVALID 场景不出分（score = null + 原因）；
 * - 任一权重项 KPI 值缺失（null）→ AQS 不可计算（score = null + 缺失项清单），绝不以 0 分顶替；
 * - VALID_LOW_CONFIDENCE 或任一权重项带 lowConfidence → 出分但 lowConfidence = true
 *   （展示层必须带低置信标注）。
 *
 * 表述边界：AQS 是实验性应用层综合体验分，测量对象为"终端至指定仿真节点的应用层路径"，
 * 禁止表述为 MOS/无线层评级/运营商全网评级/SLA 结论（5.4）。
 */
object AqsScorer {

    const val AQS_VERSION: String = "aqs-v0.1"

    /**
     * 阶段 2 版本（KPI 文档 5.4：阶段二引入 C 组后，v0.1 权重 ×0.8，C 组占 20%
     * = C1 10% + C2 10%）。仅当调用方提供连续性数据（[ContinuityKpi]）时可选出分；
     * 无 C 数据一律走 v0.1 默认（additive，不改 v0.1 语义）。
     */
    const val AQS_VERSION_V02: String = "aqs-v0.2"

    /**
     * Token 体验模式版本（Profile 框架 v1.0，PROFILE_FRAMEWORK §2/§5）。按模态选权重表
     * （[WEIGHTS_TOKEN_MM] / [WEIGHTS_TOKEN_TXT]），新增 D1 加权项 + S1 软否决；
     * 打分管线仍复用 [scoreWith]（INV-1：复用而非重写）。与 v0.1/v0.2 并列、互不影响。
     */
    const val AQS_VERSION_TOKEN: String = "aqs-token-v0.1"

    /** 语音实时交互模式版本（PROFILE_FRAMEWORK §4.1，additive；观测口径出分，不并入 v0.1/v0.2/Token） */
    const val AQS_VERSION_VOICE: String = "aqs-voice-v0.1"
    const val KPI_SET_VERSION: String = KpiCalculator.KPI_SET_VERSION

    /** T4 一票否决线（比率），KPI 文档 5.4 */
    const val T4_VETO_THRESHOLD: Double = 0.01

    /** T4 否决时的 AQS 封顶分 */
    const val T4_VETO_CAP: Double = 54.0

    /** S1 会话完成率软否决（PROFILE_FRAMEWORK §2.5，与 T4 同机制）：<0.95 封顶 70。 */
    const val S1_VETO_SOFT_THRESHOLD: Double = 0.95
    const val S1_VETO_SOFT_CAP: Double = 70.0

    /** S1 硬否决：<0.90 封顶 54。 */
    const val S1_VETO_HARD_THRESHOLD: Double = 0.90
    const val S1_VETO_HARD_CAP: Double = 54.0

    /** M1 口到耳预算硬否决（语音模式，§4.1「口到耳超红线一票否决」）：>400ms 封顶 54 */
    const val M1_VETO_THRESHOLD_MS: Double = 400.0

    /** 权重表（合计 1.0），KPI 文档 5.4 */
    val WEIGHTS: Map<String, Double> = mapOf(
        "T1" to 0.20,
        "T3" to 0.20,
        "T2" to 0.15,
        "U1" to 0.15,
        "U2" to 0.10,
        "N1" to 0.10,
        "N2" to 0.10,
    )

    /**
     * v0.2 权重表（合计 1.0）：v0.1 各项 ×0.8 + C1 10% + C2 10%（KPI 文档 5.4 阶段二条款）。
     * 由 v0.1 表推导（单一事实来源，防两表手工漂移）。
     */
    val WEIGHTS_V02: Map<String, Double> =
        WEIGHTS.mapValues { it.value * 0.8 } + mapOf("C1" to 0.10, "C2" to 0.10)

    /**
     * Token 体验·多模态权重表（PROFILE_FRAMEWORK §2.5，含 MB/10MB/100MB 上下行，合计 1.0）。
     * 相对 v0.1 抬升上下行（U1+D1=0.30）与 TTFT、压低 tool_loop。新增 D1（下行 goodput）加权项。
     * 本表为单一事实源（无更基元的派生源），Σ=1.0 由单测守护。
     */
    val WEIGHTS_TOKEN_MM: Map<String, Double> = mapOf(
        "T1" to 0.18,
        "T3" to 0.15,
        "T2" to 0.12,
        "U1" to 0.15,
        "D1" to 0.15,
        "U2" to 0.05,
        "N1" to 0.10,
        "N2" to 0.10,
    )

    /**
     * Token 体验·纯文本权重表（PROFILE_FRAMEWORK §2.5，上传≪1MB、无媒体返回，合计 1.0）。
     * U1/D1 属**设计缺省**（该业务本无大上下行）→ 按 INV-4 从表中剔除，对在场 KPI 归一化后独立标定，
     * 与「测量失败(value=null)不可计算」严格区分：设计缺省不入表→不参评；测量失败在表→KPI_MISSING。
     * Σ=1.0 由单测守护。
     */
    val WEIGHTS_TOKEN_TXT: Map<String, Double> = mapOf(
        "T1" to 0.25,
        "T3" to 0.22,
        "T2" to 0.18,
        "U2" to 0.05,
        "N1" to 0.15,
        "N2" to 0.15,
    )

    /** Token 模式权重表注册（`ScoringModelSpec.weightsTableId` 字符串键控，单一事实源）。 */
    val TOKEN_WEIGHT_TABLES: Map<String, Map<String, Double>> = mapOf(
        "WEIGHTS_TOKEN_MM" to WEIGHTS_TOKEN_MM,
        "WEIGHTS_TOKEN_TXT" to WEIGHTS_TOKEN_TXT,
    )

    /**
     * 语音实时交互权重表（PROFILE_FRAMEWORK §4.1：权重向 M 组 + 抖动/稳定性倾斜——
     * 语音对连续性/抖动远比吞吐敏感；无吞吐加权项）。Σ=1.0 由单测守护。
     * M1=口到耳预算(观测口径=RTT+max(帧抖动)+编解码/播放缓冲名义常数)；
     * M2=下行帧间抖动 P95；M3=上行帧间抖动 P95（服务端 chunk_us 权威到达序列）。
     */
    val WEIGHTS_VOICE: Map<String, Double> = mapOf(
        "M1" to 0.30,
        "M2" to 0.20,
        "M3" to 0.15,
        "N1" to 0.15,
        "N2" to 0.20,
    )

    /**
     * 单调锚点表：(KPI 值, 分数) 对，按值升序。端点外 clamp。
     * 门限数字全部来自 KPI 文档 5.2（agent-qoe-kpi v0.1，实验性）。
     */
    internal class AnchorMap(private val anchors: List<Pair<Double, Double>>) {
        init {
            require(anchors.size >= 2)
            require(anchors.zipWithNext().all { (a, b) -> a.first < b.first }) { "锚点值必须严格升序" }
        }

        fun score(value: Double): Double {
            if (value <= anchors.first().first) return anchors.first().second
            if (value >= anchors.last().first) return anchors.last().second
            for (i in 1 until anchors.size) {
                val (x0, y0) = anchors[i - 1]
                val (x1, y1) = anchors[i]
                if (value <= x1) {
                    return y0 + (value - x0) / (x1 - x0) * (y1 - y0)
                }
            }
            return anchors.last().second // 不可达
        }
    }

    // ---- 门限锚点常量表（agent-qoe-kpi v0.1，5.2；补全锚点见类 KDoc）----
    // 低者优：0→100，优/良→85，良/可→70，可/差→55，3×可差→0
    internal val T1_ANCHORS = AnchorMap(listOf(0.0 to 100.0, 200.0 to 85.0, 500.0 to 70.0, 1000.0 to 55.0, 3000.0 to 0.0))
    internal val T2_ANCHORS = AnchorMap(listOf(0.0 to 100.0, 100.0 to 85.0, 200.0 to 70.0, 400.0 to 55.0, 1200.0 to 0.0))
    internal val T3_ANCHORS = AnchorMap(listOf(0.0 to 100.0, 0.005 to 85.0, 0.02 to 70.0, 0.05 to 55.0, 0.15 to 0.0))
    internal val N1_ANCHORS = AnchorMap(listOf(0.0 to 100.0, 30.0 to 85.0, 60.0 to 70.0, 100.0 to 55.0, 300.0 to 0.0))
    internal val N2_ANCHORS = AnchorMap(listOf(0.0 to 100.0, 10.0 to 85.0, 30.0 to 70.0, 80.0 to 55.0, 240.0 to 0.0))
    internal val U2_ANCHORS = AnchorMap(listOf(0.0 to 100.0, 150.0 to 85.0, 300.0 to 70.0, 600.0 to 55.0, 1800.0 to 0.0))

    // 高者优（U1，Mbps）：0→0，可/差=1→55，良/可=5→70，优/良=20→85，100→100
    internal val U1_ANCHORS = AnchorMap(listOf(0.0 to 0.0, 1.0 to 55.0, 5.0 to 70.0, 20.0 to 85.0, 100.0 to 100.0))

    // 高者优（D1 下行 goodput，Mbps；PROFILE_FRAMEWORK §2.3/§5，结构同 U1）：
    // 0→0，可/差=2→55，良/可=8→70，优/良=25→85，100→100（返回下行略高于上行 + 蜂窝下行利好，锚点整体高于 U1）
    internal val D1_ANCHORS = AnchorMap(listOf(0.0 to 0.0, 2.0 to 55.0, 8.0 to 70.0, 25.0 to 85.0, 100.0 to 100.0))

    // ---- C 组门限锚点（agent-qoe-kpi v0.2 / KPI 文档 5.2；补全锚点规则同 v0.1）----
    // C1 会话中断率（ratio，低者优）：0.5% / 2% / 5%，差档下锚 3×0.05=0.15
    internal val C1_ANCHORS = AnchorMap(listOf(0.0 to 100.0, 0.005 to 85.0, 0.02 to 70.0, 0.05 to 55.0, 0.15 to 0.0))

    // C2 切换恢复时间（ms，低者优）：1s / 3s / 10s，差档下锚 3×10000=30000；
    // "失败"（恢复不成功）按 R-10 记 null → v0.2 不可计算（KPI_MISSING:C2），绝不以封顶值顶替
    internal val C2_ANCHORS = AnchorMap(listOf(0.0 to 100.0, 1000.0 to 85.0, 3000.0 to 70.0, 10000.0 to 55.0, 30000.0 to 0.0))

    // ---- M 组门限锚点（语音实时交互，PROFILE_FRAMEWORK §4.1；observation 口径）----
    // M1 口到耳预算（ms，低者优）：150/300/400（对话自然度红线），差档下锚 3×400=1200
    internal val M1_ANCHORS = AnchorMap(listOf(0.0 to 100.0, 150.0 to 85.0, 300.0 to 70.0, 400.0 to 55.0, 1200.0 to 0.0))

    // M2/M3 帧间抖动（ms，低者优；下行/上行同锚，§4.1 抖动<30ms 达 95%）——与 N2 数值同
    // 但语义独立（帧到达间隔对名义 20ms 节奏的偏差 P95，非 RTT 分位差），单列防口径漂移
    internal val M_FRAME_JITTER_ANCHORS = AnchorMap(listOf(0.0 to 100.0, 10.0 to 85.0, 30.0 to 70.0, 80.0 to 55.0, 240.0 to 0.0))

    /**
     * AQS 评分结果。
     *
     * @param score 0–100 综合分；不可计算时 null（绝不 0）
     * @param subScores 各权重项子分（KPI id → 0–100），可计算时非空
     * @param vetoApplied T4 > 1% 一票否决已触发（分数封顶 54）
     * @param s1VetoApplied S1 会话完成率软否决已触发（<0.95 封顶 70 / <0.90 封顶 54）；仅 Token 模式出分时可能为 true
     * @param lowConfidence 低置信（VALID_LOW_CONFIDENCE 场景或任一权重项样本不足），展示必须带标
     * @param notComputableReason 不可计算原因（"INVALID_SCENARIO:…" / "KPI_MISSING:…"）
     */
    data class AqsResult(
        val aqsVersion: String,
        val kpiSetVersion: String,
        val score: Double?,
        val subScores: Map<String, Double>,
        val vetoApplied: Boolean,
        val lowConfidence: Boolean,
        val notComputableReason: String?,
        val s1VetoApplied: Boolean = false,
    )

    /**
     * C 组（连续性）评分输入（阶段 2 连续性实验产出，aqs v0.2 专用）。
     * 失败语义与 [KpiValue] 一致：无有效样本/恢复失败一律 value=null（R-10），
     * v0.2 对 null 的处理与 T/U/N 组相同——不可计算（KPI_MISSING），绝不以 0 顶替。
     *
     * @param c1SessionDropRate 会话中断率（ratio：异常断开次数/流式段总数，跨段聚合）
     * @param c2RecoveryMs 切换恢复时间（ms：中断时刻→重连流首 token 到达；多样本取中位数）
     */
    data class ContinuityKpi(
        val c1SessionDropRate: KpiValue,
        val c2RecoveryMs: KpiValue,
    )

    fun score(kpi: KpiResult): AqsResult =
        scoreWith(kpi, extraInputs = emptyMap(), weights = WEIGHTS, version = AQS_VERSION)

    /**
     * aqs v0.2 出分入口（additive）：仅当 [continuity] 非 null 时按 v0.2 权重
     * （v0.1×0.8 + C1 10% + C2 10%）计算并标注版本号 [AQS_VERSION_V02]；
     * continuity=null 时语义与 [score] (v0.1) 完全一致——无连续性数据的 run
     * 保持 v0.1 默认（KPI 文档 5.4 阶段二条款）。
     */
    fun score(kpi: KpiResult, continuity: ContinuityKpi?): AqsResult {
        if (continuity == null) return score(kpi)
        return scoreWith(
            kpi,
            extraInputs = mapOf(
                "C1" to continuity.c1SessionDropRate,
                "C2" to continuity.c2RecoveryMs,
            ),
            weights = WEIGHTS_V02,
            version = AQS_VERSION_V02,
        )
    }

    /**
     * Token 体验模式出分入口（PROFILE_FRAMEWORK §2.5，additive）：按 [weightsTableId]
     * 从 [TOKEN_WEIGHT_TABLES] 选权重表（多模态 "WEIGHTS_TOKEN_MM" / 纯文本 "WEIGHTS_TOKEN_TXT"），
     * 复用同一 [scoreWith] 打分管线（INV-1）。
     *
     * 与 v0.1/v0.2 的差异（全 additive、互不影响）：
     * - **renormalize（INV-4）**：只要求「在表」的 KPI 非 null——不在表的设计缺省项（如 TXT 的 U1/D1）
     *   不参评、不判 KPI_MISSING；在表项 value=null 才判 KPI_MISSING（测量失败 fail-closed）。
     * - **D1 加权项**：MM 表含 D1（下行 goodput），走 [D1_ANCHORS]。
     * - **S1 软否决**：会话完成率 <0.95 封顶 70、<0.90 封顶 54（与 T4 同 min() 机制）。
     *
     * @throws IllegalArgumentException 未知 [weightsTableId]
     */
    fun scoreToken(kpi: KpiResult, weightsTableId: String): AqsResult {
        val weights = TOKEN_WEIGHT_TABLES[weightsTableId]
            ?: throw IllegalArgumentException("未知 Token 权重表: $weightsTableId")
        return scoreWith(
            kpi,
            extraInputs = emptyMap(),
            weights = weights,
            version = AQS_VERSION_TOKEN,
            applyS1Veto = true,
        )
    }

    /**
     * 语音实时交互出分入口（PROFILE_FRAMEWORK §4.1，additive）：M 组经 extraInputs 注入
     * （同 C1/C2 先例），N1/N2 走最小 KpiResult；[WEIGHTS_VOICE] 加权 + M1 口到耳硬否决。
     * 观测口径（口到耳=预算合成、帧抖动含客户端调度抖动上界），独立出分不并入既有 AQS。
     */
    fun scoreVoice(
        n1RttMs: KpiValue,
        n2JitterMs: KpiValue,
        m1BudgetMs: KpiValue,
        m2DownFrameJitterMs: KpiValue,
        m3UpFrameJitterMs: KpiValue,
    ): AqsResult = scoreWith(
        KpiResult(
            validity = Validity.VALID,
            invalidReasons = emptyList(),
            seqMissingCount = 0,
            seqDupCount = 0,
            seqGapCount = 0,
            expectedTokenCount = 0,
            t1TtftMs = KpiValue.empty("ms"),
            t2ItlP95Ms = KpiValue.empty("ms"),
            t2ItlP95InclCoalescedMs = KpiValue.empty("ms"),
            t3StallRate = KpiValue.empty("ratio"),
            t3StallRateInclResume = KpiValue.empty("ratio"),
            t4SevereStallRate = KpiValue.empty("ratio"),
            t5ResumeP95Ms = KpiValue.empty("ms"),
            t5ResumeLatenciesMs = emptyList(),
            n1RttP50Ms = n1RttMs,
            n2JitterMs = n2JitterMs,
            u1GoodputMbps = KpiValue.empty("Mbps"),
            u1GoodputExclSlowStartMbps = KpiValue.empty("Mbps"),
            u2ToolLoopP95Ms = KpiValue.empty("ms"),
        ),
        extraInputs = mapOf(
            "M1" to m1BudgetMs,
            "M2" to m2DownFrameJitterMs,
            "M3" to m3UpFrameJitterMs,
        ),
        weights = WEIGHTS_VOICE,
        version = AQS_VERSION_VOICE,
        applyM1Veto = true,
    )

    private fun scoreWith(
        kpi: KpiResult,
        extraInputs: Map<String, KpiValue>,
        weights: Map<String, Double>,
        version: String,
        applyS1Veto: Boolean = false,
        applyM1Veto: Boolean = false,
    ): AqsResult {
        if (kpi.validity == Validity.INVALID) {
            return AqsResult(
                aqsVersion = version,
                kpiSetVersion = KPI_SET_VERSION,
                score = null,
                subScores = emptyMap(),
                vetoApplied = false,
                lowConfidence = false,
                notComputableReason = "INVALID_SCENARIO:" + kpi.invalidReasons.joinToString(","),
            )
        }

        // 候选权重项取值（口径见类 KDoc）。按所选权重表**投影**——不在表的项（如 TXT 的 U1/D1、
        // 或 v0.1 的 D1/C1/C2）自动剔除，即 INV-4 的「设计缺省 renormalize」；在表项才要求非 null。
        val candidateInputs: Map<String, KpiValue> = mapOf(
            "T1" to kpi.t1TtftMs,
            "T2" to kpi.t2ItlP95Ms,
            "T3" to kpi.t3StallRate,
            "U1" to kpi.u1GoodputMbps,
            "D1" to kpi.d1GoodputMbps,
            "U2" to kpi.u2ToolLoopP95Ms,
            "N1" to kpi.n1RttP50Ms,
            "N2" to kpi.n2JitterMs,
        ) + extraInputs
        val inputs = candidateInputs.filterKeys { it in weights.keys }
        val missing = inputs.filterValues { it.value == null }.keys.sorted()
        if (missing.isNotEmpty()) {
            // 在表权重项缺失 → AQS 不可计算（R-10：绝不以 0 分顶替失败样本）
            return AqsResult(
                aqsVersion = version,
                kpiSetVersion = KPI_SET_VERSION,
                score = null,
                subScores = emptyMap(),
                vetoApplied = false,
                lowConfidence = false,
                notComputableReason = "KPI_MISSING:" + missing.joinToString(","),
            )
        }

        val anchorMaps: Map<String, AnchorMap> = mapOf(
            "T1" to T1_ANCHORS,
            "T2" to T2_ANCHORS,
            "T3" to T3_ANCHORS,
            "U1" to U1_ANCHORS,
            "D1" to D1_ANCHORS,
            "U2" to U2_ANCHORS,
            "N1" to N1_ANCHORS,
            "N2" to N2_ANCHORS,
            "C1" to C1_ANCHORS,
            "C2" to C2_ANCHORS,
            "M1" to M1_ANCHORS,
            "M2" to M_FRAME_JITTER_ANCHORS,
            "M3" to M_FRAME_JITTER_ANCHORS,
        )
        val subScores = inputs.mapValues { (id, v) -> anchorMaps.getValue(id).score(v.value!!) }
        var total = subScores.entries.sumOf { (id, s) -> s * weights.getValue(id) }

        // T4 一票否决：>1% 时封顶 54（T4 缺失时不触发否决，但 T4 属流式场景必备诊断项）
        val t4 = kpi.t4SevereStallRate.value
        var veto = t4 != null && t4 > T4_VETO_THRESHOLD
        // M1 口到耳预算硬否决（语音模式，§4.1）：>400ms 对话自然度红线，同 min() 机制
        if (applyM1Veto) {
            val m1 = extraInputs["M1"]?.value
            if (m1 != null && m1 > M1_VETO_THRESHOLD_MS) veto = true
        }
        if (veto) total = min(total, T4_VETO_CAP)

        // S1 会话完成率软否决（仅 Token 模式，与 T4 同 min() 机制；先判更严的硬否决）
        var s1Veto = false
        if (applyS1Veto) {
            val s1 = kpi.s1SessionSuccessRate.value
            if (s1 != null && s1 < S1_VETO_SOFT_THRESHOLD) {
                s1Veto = true
                val cap = if (s1 < S1_VETO_HARD_THRESHOLD) S1_VETO_HARD_CAP else S1_VETO_SOFT_CAP
                total = min(total, cap)
            }
        }

        val lowConf = kpi.validity == Validity.VALID_LOW_CONFIDENCE ||
            inputs.values.any { it.lowConfidence }

        return AqsResult(
            aqsVersion = version,
            kpiSetVersion = KPI_SET_VERSION,
            score = total,
            subScores = subScores,
            vetoApplied = veto,
            lowConfidence = lowConf,
            notComputableReason = null,
            s1VetoApplied = s1Veto,
        )
    }
}
