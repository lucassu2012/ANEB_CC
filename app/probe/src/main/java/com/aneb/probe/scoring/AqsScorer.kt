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

    /** 语音 v2 server-sim 口径版本（D-38；旧 [AQS_VERSION_VOICE] 不动）。 */
    const val AQS_VERSION_VOICE_SIM: String = "aqs-voice-sim-v0.1"

    /**
     * 语音 v2 server-sim 权重表（D-38 §3；/realtime-sim 实测口径）：
     * M1=口到耳实测代理 P50、M2=下行纯传输抖动 P95（sched_us 差分剥离）、M3=上行帧抖动
     * （paced-proxy 并列保留）、M4=TTS-TTFB P50（剥服务端驻留）、M5=轮次切换 P50、
     * M6=打断停帧 max。Σ=1.0 由单测守护。
     */
    val WEIGHTS_VOICE_SIM: Map<String, Double> = mapOf(
        "M1" to 0.20,
        "M2" to 0.15,
        "M3" to 0.10,
        "M4" to 0.15,
        "M5" to 0.10,
        "M6" to 0.10,
        "N1" to 0.10,
        "N2" to 0.10,
    )

    /** 语音 v0.2 版本（D-390 §5.6；M7 入表）。旧 [AQS_VERSION_VOICE] 不动——见 [WEIGHTS_VOICE_V02]。 */
    const val AQS_VERSION_VOICE_V02: String = "aqs-voice-v0.2"

    /** 语音 sim v0.2 版本（同上）。 */
    const val AQS_VERSION_VOICE_SIM_V02: String = "aqs-voice-sim-v0.2"

    /**
     * 语音 v0.2 权重表（Σ=1.0，单测守护）：v0.1 + M7=最长帧间静默 max。
     *
     * **为什么并列而不是把 [WEIGHTS_VOICE] 原地改**：spec/README.md §3「已发布权重表只增
     * 不改不删，语义变化=新 id 并列」（先例 [WEIGHTS] → [WEIGHTS_V02]）。原地改会让语料里
     * 已盖 `aqsVersion="aqs-voice-v0.1"` 的历史分数在 spec 里查无此表——版本戳指向一个不
     * 存在的定义，而能重算历史分正是盖这个戳的全部理由。
     *
     * 0.10 从 M2（0.20→0.15）与 M3（0.15→0.10）出，M1/N1/N2 一分未动：这两项与 M7 量的是
     * 同一串帧间间隔的两个尾巴（P95 vs max），稀释它们=同一现象内部重新分配；若从 M1/N 组
     * 扣，等于用「静默变重要了」去论证「时延变次要了」，那是两件事。
     */
    val WEIGHTS_VOICE_V02: Map<String, Double> = mapOf(
        "M1" to 0.30,
        "M2" to 0.15,
        "M3" to 0.10,
        "M7" to 0.10,
        "N1" to 0.15,
        "N2" to 0.20,
    )

    /**
     * 语音 sim v0.2 权重表（Σ=1.0，单测守护）：[WEIGHTS_VOICE_SIM] + M7。
     *
     * M7 在 sim 口径只拿 0.05（v1 口径的一半）：这里已有 M6=打断停帧 max 在管「最坏的一次卡」
     * 的一部分。两者不同源（M6 是打断后的收敛，M7 是任意时刻的静默），但读者拿到的是同一类
     * 信号，给满权重会把「卡」在总分里数两遍。0.05 从 M2/M3 出，理由同 [WEIGHTS_VOICE_V02]。
     */
    val WEIGHTS_VOICE_SIM_V02: Map<String, Double> = mapOf(
        "M1" to 0.20,
        "M2" to 0.12,
        "M3" to 0.08,
        "M4" to 0.15,
        "M5" to 0.10,
        "M6" to 0.10,
        "M7" to 0.05,
        "N1" to 0.10,
        "N2" to 0.10,
    )

    /**
     * 版本 id → 权重表名的单一事实源。
     *
     * 存在的理由是一处**已经在骗人**的展示：[com.aneb.probe.ui.VoiceTestScreen] 把表名与
     * 版本号并排印给用户，而表名当时由 `if (caliber == SIM) "WEIGHTS_VOICE_SIM" else
     * "WEIGHTS_VOICE"` 独立算出——口径一分叉（v0.2 出分却仍印 v0.1 的表名），并排的两个字段
     * 就会逐字打架。凡「同一事实印在两处」，让第二处从第一处派生，而不是各算各的（§2.14）。
     */
    val VOICE_WEIGHTS_TABLE_BY_VERSION: Map<String, String> = mapOf(
        AQS_VERSION_VOICE to "WEIGHTS_VOICE",
        AQS_VERSION_VOICE_V02 to "WEIGHTS_VOICE_V02",
        AQS_VERSION_VOICE_SIM to "WEIGHTS_VOICE_SIM",
        AQS_VERSION_VOICE_SIM_V02 to "WEIGHTS_VOICE_SIM_V02",
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

    /** M4 TTS-TTFB（ms，D-38；语音首响远严于 token TTFT——对话自然度） */
    internal val M4_TTFB_ANCHORS = AnchorMap(listOf(0.0 to 100.0, 100.0 to 85.0, 250.0 to 70.0, 500.0 to 55.0, 1500.0 to 0.0))

    /** M5 轮次切换（ms，D-38） */
    internal val M5_TURN_SWITCH_ANCHORS = AnchorMap(listOf(0.0 to 100.0, 150.0 to 85.0, 300.0 to 70.0, 600.0 to 55.0, 2000.0 to 0.0))

    /** M6 打断停帧（ms，D-38；55 分档=默认 expected_stop_within_ms=250） */
    internal val M6_STOP_ANCHORS = AnchorMap(listOf(0.0 to 100.0, 80.0 to 85.0, 150.0 to 70.0, 250.0 to 55.0, 1000.0 to 0.0))

    /**
     * M7 最长帧间静默（ms，低者优；D-390 §5.6 订正后的首选判据）。
     *
     * **判据是 max 不是分位数**——这是 M7 存在的全部理由。M2 用 P95，而 P95 把「罕见但致命」
     * 的长冻结整个丢掉：实测一次 4.55 秒冻结在 599 个间隔里只占 0.67%，落在分位点之上被切掉，
     * 于是 M2 报 25.000ms 的饱和平台，读者拿不到「4.5 秒」这个数。
     *
     * 门限不发明新数字：60=[com.aneb.probe.engine.VoiceRunner.CODEC_JB_BUDGET_MS]（名义抖动
     * 缓冲深度，低于它缓冲吸收得掉）；150/400=PROFILE_FRAMEWORK §4.1 口到耳自然度红线的第一/
     * 第三档，其中 400 亦即 [M1_VETO_THRESHOLD_MS]。
     *
     * **1000 是 PROVISIONAL**：五个门限里唯一没有仓内出处的数。保留它而不用 400 作末点，是因为
     * 400 末点会让 500ms 与 5s 同分（都 0），丢掉「严重度可传导」这个 M7 存在的意义。
     * **第一批真实语音语料出来后必须回核**（同 PROFILE4_VOICE_LOOPBACK_SPEC §7 的回核义务）：
     * 全仓零语音语料，今天判不了它对真实分布合不合适。
     */
    internal val M7_MAX_GAP_ANCHORS = AnchorMap(listOf(0.0 to 100.0, 60.0 to 85.0, 150.0 to 70.0, 400.0 to 40.0, 1000.0 to 0.0))

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
        voiceKpiShell(n1RttMs, n2JitterMs),
        extraInputs = mapOf(
            "M1" to m1BudgetMs,
            "M2" to m2DownFrameJitterMs,
            "M3" to m3UpFrameJitterMs,
        ),
        weights = WEIGHTS_VOICE,
        version = AQS_VERSION_VOICE,
        applyM1Veto = true,
    )

    /**
     * 语音 v0.2 出分入口（D-390 §5.6，additive）：在 v0.1 五项基础上加 M7=最长帧间静默 max，
     * 走 [WEIGHTS_VOICE_V02] 并盖版本号 [AQS_VERSION_VOICE_V02]。上面的 5 参 [scoreVoice]
     * **行为逐字不变**——签名、权重表、版本戳、出分全同（本轮只把它内部那段重复的 KpiResult
     * 字面量抽成了 [voiceKpiShell]），**没有 M7 的 run（含全部历史语料）结论完全不变**。
     *
     * **选版本按「调用方有没有测这一项」，不按「测出来是不是 null」**（同 [score] 的
     * `continuity` 先例）：
     * - 调用 5 参重载 = 这次运行根本没有 M7 这个概念 → v0.1，天经地义；
     * - 调用本重载而 `m7MaxFrameGapMs.value == null` = 测了但**失败** → 沿用 [scoreWith] 的
     *   在表项 fail-closed，判 `KPI_MISSING:M7`（R-10）。
     *
     * 这里**故意不做**「M7 为 null 就悄悄退回 v0.1」的降级：那样出来的分会盖 v0.1 的戳，
     * 而这一轮实际上是按 v0.2 口径跑的——版本戳会替一个它没算过的口径背书，
     * 比不出分危险得多。丢一个分是可恢复的，一个说谎的版本戳不可恢复。
     */
    fun scoreVoice(
        n1RttMs: KpiValue,
        n2JitterMs: KpiValue,
        m1BudgetMs: KpiValue,
        m2DownFrameJitterMs: KpiValue,
        m3UpFrameJitterMs: KpiValue,
        m7MaxFrameGapMs: KpiValue,
    ): AqsResult = scoreWith(
        voiceKpiShell(n1RttMs, n2JitterMs),
        extraInputs = mapOf(
            "M1" to m1BudgetMs,
            "M2" to m2DownFrameJitterMs,
            "M3" to m3UpFrameJitterMs,
            "M7" to m7MaxFrameGapMs,
        ),
        weights = WEIGHTS_VOICE_V02,
        version = AQS_VERSION_VOICE_V02,
        applyM1Veto = true,
    )

    /**
     * 语音 v2 server-sim 出分入口（D-38，additive；/realtime-sim 实测口径）：
     * M1=口到耳实测代理、M2=下行纯传输抖动（sched_us 剥离）、M3=上行帧抖动（paced-proxy 并列）、
     * M4=TTS-TTFB（剥服务端驻留）、M5=轮次切换、M6=打断停帧。[WEIGHTS_VOICE_SIM] 加权 +
     * M1 口到耳硬否决（阈值复用 [M1_VETO_THRESHOLD_MS]，代理值语义同为口到耳 ms）。
     * 旧 [scoreVoice]/[WEIGHTS_VOICE] 零改动（paced-proxy 口径继续可用）。
     */
    fun scoreVoiceSim(
        n1RttMs: KpiValue,
        n2JitterMs: KpiValue,
        m1MouthEarProxyMs: KpiValue,
        m2DownNetJitterMs: KpiValue,
        m3UpFrameJitterMs: KpiValue,
        m4TtfbMs: KpiValue,
        m5TurnSwitchMs: KpiValue,
        m6BargeStopMs: KpiValue,
    ): AqsResult = scoreWith(
        voiceKpiShell(n1RttMs, n2JitterMs),
        extraInputs = mapOf(
            "M1" to m1MouthEarProxyMs,
            "M2" to m2DownNetJitterMs,
            "M3" to m3UpFrameJitterMs,
            "M4" to m4TtfbMs,
            "M5" to m5TurnSwitchMs,
            "M6" to m6BargeStopMs,
        ),
        weights = WEIGHTS_VOICE_SIM,
        version = AQS_VERSION_VOICE_SIM,
        applyM1Veto = true,
    )

    /**
     * 语音 sim v0.2 出分入口（D-390 §5.6，additive）：sim 六项 + M7，走 [WEIGHTS_VOICE_SIM_V02]
     * 并盖 [AQS_VERSION_VOICE_SIM_V02]。上面的 8 参 [scoreVoiceSim] 行为逐字不变。
     *
     * 选版本与 null 语义同 6 参 [scoreVoice]（按「有没有测这一项」选，测了而失败 → `KPI_MISSING:M7`，
     * **不**静默降级到 v0.1）——那条推理写在那边，此处不复制，避免两处解释各自漂移。
     */
    fun scoreVoiceSim(
        n1RttMs: KpiValue,
        n2JitterMs: KpiValue,
        m1MouthEarProxyMs: KpiValue,
        m2DownNetJitterMs: KpiValue,
        m3UpFrameJitterMs: KpiValue,
        m4TtfbMs: KpiValue,
        m5TurnSwitchMs: KpiValue,
        m6BargeStopMs: KpiValue,
        m7MaxFrameGapMs: KpiValue,
    ): AqsResult = scoreWith(
        voiceKpiShell(n1RttMs, n2JitterMs),
        extraInputs = mapOf(
            "M1" to m1MouthEarProxyMs,
            "M2" to m2DownNetJitterMs,
            "M3" to m3UpFrameJitterMs,
            "M4" to m4TtfbMs,
            "M5" to m5TurnSwitchMs,
            "M6" to m6BargeStopMs,
            "M7" to m7MaxFrameGapMs,
        ),
        weights = WEIGHTS_VOICE_SIM_V02,
        version = AQS_VERSION_VOICE_SIM_V02,
        applyM1Veto = true,
    )

    /**
     * 语音四个出分入口共用的 [KpiResult] 壳：语音口径不产出 T/U 组，按 R-10 一律 `empty`
     * （**未测**，不是 0），只把 N1/N2 填进去；M 组一律走 `extraInputs`。
     *
     * 抽出来的理由是副本会漂：同一段 20 行字面量原本在 [scoreVoice]/[scoreVoiceSim] 各一份，
     * 加上两个 v0.2 入口就是四份，而 [KpiResult] 每加一个字段就要人手同步四处——
     * 漏掉任何一处都不会红，只会让那个入口的某项悄悄变成另一个值。
     */
    private fun voiceKpiShell(n1RttMs: KpiValue, n2JitterMs: KpiValue): KpiResult = KpiResult(
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
            "M4" to M4_TTFB_ANCHORS,
            "M5" to M5_TURN_SWITCH_ANCHORS,
            "M6" to M6_STOP_ANCHORS,
            "M7" to M7_MAX_GAP_ANCHORS,
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
