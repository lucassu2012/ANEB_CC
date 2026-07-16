package com.aneb.probe.ui

/**
 * 一个**测试模式**的档案（模式级 Profile）——不是 [com.aneb.probe.engine.ScenarioProfile]
 * （那是 token 引擎内部的场景/KPI 合同，粒度不同）。捕获用户 /goal 点 3 的四facet：
 * **什么业务 · 测哪些指标（含质量目标）· 哪些动态呈现 · 得出什么结论**。
 *
 * ## v2 形式化（Profile 框架 v1.0，docs/PROFILE_FRAMEWORK.md §1.2）
 * additive 演进：`displayName/tagline` 及展示投影字段（`business/metrics/conclusion`）原样保留，
 * 供分段开关（[TestModeSegments]）、模式信息条（[ModeProfileStrip]）与标题不改；**新增**四 facet
 * 形式化契约（[businessType]/[metricSpecs]/[live]/[scoring]，均带默认值向后兼容）：
 *
 * ```
 * Profile ⟨BusinessType, MetricSpec[], LiveMetric[], ScoringModel⟩
 * ├─ facet1 businessType   业务类型 + 子场景表（客观工作量信号）
 * ├─ facet2 metricSpecs    全量【业务∪网络指标】+ 每指标质量目标 + 可度量性
 * ├─ facet3 live           APP 高频动态呈现的关键指标（LiveTelemetry 只读通道，R-16）
 * └─ facet4 scoring        打分评估模型/算法（权重表·锚点·否决 引用单一事实源）
 * ```
 *
 * ## 单一事实源（INV-3）
 * [MetricSpec.anchorRef] / [ScoringModelSpec.weightsTableId] 只**引用**
 * [com.aneb.probe.scoring.AqsScorer] 内已冻结的锚点/权重表（字符串键控），Profile 本身不复制阈值数字——
 * 避免 UI 与打分引擎两处漂移。
 *
 * 扩展方式（/goal 点 2）：新增一种测试模式 = 往 [TestModeProfiles.ALL] 加一个 profile
 * （+ 其测试屏 + MainActivity 里一处按 id 选屏的 when 分支）。分段开关、模式信息条均由本表数据驱动。
 */
data class TestModeProfile(
    val id: String,
    /** 分段开关/标题显示名（保留）。 */
    val displayName: String,
    /** 一句话副标（保留）。 */
    val tagline: String,
    /** 什么业务：评估的真实场景（展示投影，权威源见 [businessType]）。 */
    val business: String,
    /** 测哪些指标（含是否高频动态刷新）——信息条展示投影，全量权威源见 [metricSpecs]。 */
    val metrics: List<ModeMetric>,
    /** 得出什么结论：判定口径（展示投影，权威源见 [scoring]）。 */
    val conclusion: String,

    // ── v2 4-facet 形式化契约（additive，带默认值向后兼容）─────────────────
    /** 模式档版本，发布即冻结、改必升版本（对齐 ScenarioProfile 合同）。 */
    val version: String = "",
    /** facet1：业务类型 + 客观工作量子场景。 */
    val businessType: BusinessType? = null,
    /** facet2：全量指标规格（业务∪网络，含质量目标/口径/可度量性）。 */
    val metricSpecs: List<MetricSpec> = emptyList(),
    /** facet3：APP 动态呈现关键指标（LiveTelemetry 只读源，不参与测量口径，R-16）。 */
    val live: List<LiveMetric> = emptyList(),
    /** facet4：打分模型规格（引用单一事实源的权重/锚点/否决）。 */
    val scoring: ScoringModelSpec? = null,
)

/** 模式内一个指标（信息条展示投影）。[dynamic]=是否高频动态刷新（SpeedTest 式波动展示的候选）。 */
data class ModeMetric(
    val name: String,
    val unit: String,
    val dynamic: Boolean,
)

// ────────────────────────────────────────────────────────────────────────────
//  facet1：业务类型
// ────────────────────────────────────────────────────────────────────────────

/** facet1：业务类型 + 客观工作量子场景（行为分类的输入 A）。 */
data class BusinessType(
    /** 评估的真实场景（展示 [TestModeProfile.business] 的权威源）。 */
    val summary: String,
    /** 子场景表（上下行工作量信号）。 */
    val subScenarios: List<SubScenario> = emptyList(),
)

/** 一个客观工作量子场景（如 Token 类的 TK-1..TK-6）。 */
data class SubScenario(
    val code: String,
    val title: String,
    /** 上行工作量描述（字节/突发/token 流）。 */
    val uplink: String,
    /** 下行工作量描述。 */
    val downlink: String,
    /** 声明式行为提示（最终标签由 facet4 双证据判定，此处仅描述性）。 */
    val behaviorHint: List<BehaviorTag> = emptyList(),
)

/** 行为特征标签（PROFILE_FRAMEWORK §2.5 双证据分类的输出标签集）。 */
enum class BehaviorTag { UPLINK_BURST, LOW_LATENCY, DOWNLINK_BANDWIDTH, STABILITY }

// ────────────────────────────────────────────────────────────────────────────
//  facet2：指标规格
// ────────────────────────────────────────────────────────────────────────────

/** facet2：一条指标的完整规格。业务指标与网络指标同构，[group] 区分。 */
data class MetricSpec(
    /** KPI id（"T1"/"U1"/"D1"/"S1"…映射 KpiCalculator/report 字段）。 */
    val id: String,
    val name: String,
    val unit: String,
    val group: MetricGroup,
    /** 计时端点/口径（含减法项，如剥服务端 dwell）。 */
    val definition: String,
    val direction: Direction,
    /** 质量目标（四级门限 + 达标比例口径）。 */
    val target: QualityTarget,
    /** 可度量性 + 局限（模拟条件下）。 */
    val measurability: Measurability,
    /** 是否进 AQS 加权（TPS/Token 消耗=false，仅呈现/元数据）。 */
    val scored: Boolean,
    /** 复用哪张 AnchorMap（"T1_ANCHORS"/"D1_ANCHORS"…），null=不打分或否决项。 */
    val anchorRef: String? = null,
)

/** T 流式 / U 上行 / D 下行 / N 基线 / C 连续性 / S 成功率 / BIZ 业务代理。 */
enum class MetricGroup { T, U, D, N, C, S, BIZ }
enum class Direction { LOWER_BETTER, HIGHER_BETTER }
enum class Measurability { MEASURABLE, PROXY, DERIVED, NOT_MEASURABLE }

/** 质量目标：四级锚点 + 达标比例（低者优→P95≤X；高者优→P5≥X）。 */
data class QualityTarget(
    /** 优/良边界值（优档下锚）。null=该级不设。 */
    val excellent: Double? = null,
    /** 良/可边界值。 */
    val good: Double? = null,
    /** 可/差边界值。 */
    val fair: Double? = null,
    /** 差档下锚（低者优场景的封底；高者优可 null）。 */
    val poorFloor: Double? = null,
    /** 达标比例口径分位（默认 0.95）。 */
    val slaPercentile: Double = 0.95,
    /** 建议 SLA 取到哪一级门限。 */
    val slaTargetLevel: Level = Level.GOOD,
    /** 分档门限（如 MB/10MB/100MB 上行独立门限）；null=统一门限。 */
    val perPayloadBand: Map<String, Band>? = null,
)

enum class Level { EXCELLENT, GOOD, FAIR, POOR }
data class Band(val excellent: Double, val good: Double, val fair: Double)

// ────────────────────────────────────────────────────────────────────────────
//  facet3：动态呈现
// ────────────────────────────────────────────────────────────────────────────

/** facet3：动态呈现关键指标（LiveTelemetry 只读源，R-16 不参与测量口径）。 */
data class LiveMetric(
    val id: String,
    val label: String,
    val unit: String,
    /** LiveTelemetry 源字段名（"tokenRatePerSec"/"rttMs"/"itlRecentMs"/"liveUpMbps"…）。 */
    val source: String,
    val render: LiveRender,
    val windowMs: Int,
    val refreshMs: Int,
)

enum class LiveRender { WAVEFORM, GAUGE, RUNNING_NUMBER, BAR }

// ────────────────────────────────────────────────────────────────────────────
//  facet4：打分模型
// ────────────────────────────────────────────────────────────────────────────

/** facet4：打分模型规格（引用单一事实源的权重/锚点/否决）。 */
data class ScoringModelSpec(
    /** 打分引擎（默认复用 AqsScorer；网络综合性能类用四门限分级）。 */
    val engine: String = "AqsScorer",
    /** 权重表 id（"WEIGHTS_TOKEN_MM"/"WEIGHTS_TOKEN_TXT"…，AqsScorer.TOKEN_WEIGHT_TABLES 键）。 */
    val weightsTableId: String,
    /** 否决规则（T4>1%→cap54；S1<95%→cap70…，同 AqsScorer 机制）。 */
    val vetoRules: List<VetoRule> = emptyList(),
    /** 设计缺省 KPI 是否归一化（区别于测量失败 null；INV-4）。 */
    val renormalizeOnDesignDefault: Boolean = true,
    /** 优/良/可/差分档线复用（aqsGrade）。 */
    val gradeMapId: String = "aqsGrade",
    /** 行为分类规则 id（双证据）。 */
    val behaviorRuleId: String = "",
    /** 建议输出模板 id。 */
    val recommendationTemplateId: String = "",
)

/** 一条否决规则：[kpiId] [op] [threshold] → 封顶 [cap]（op 取 "gt"/"lt"）。 */
data class VetoRule(val kpiId: String, val op: String, val threshold: Double, val cap: Double)

// ────────────────────────────────────────────────────────────────────────────
//  模式表（数据驱动分段开关与信息条）
// ────────────────────────────────────────────────────────────────────────────

object TestModeProfiles {

    val BASIC_NETWORK = TestModeProfile(
        id = "basic_network",
        displayName = "网络基本性能",
        tagline = "SpeedTest 式上下行速率 + 时延",
        business = "评估这条网络的原始承载力：能否流畅收发大对象、时延是否够低——判断底层网络是否" +
            "适合 AI 对话 / 编码 / 多模态。",
        metrics = listOf(
            ModeMetric("下行速率", "Mbps", dynamic = true),
            ModeMetric("上行速率", "Mbps", dynamic = true),
            ModeMetric("时延", "ms", dynamic = true),
            ModeMetric("抖动", "ms", dynamic = false),
        ),
        conclusion = "上下行 / 时延 / 抖动四门限 → 优良·尚可·偏弱，并给 AI 使用场景建议。",
        // ── v2 4-facet（PROFILE_FRAMEWORK §4.2）──────────────────────────
        version = "basic-network-profile@0.1.0",
        businessType = BusinessType(
            summary = "评估这条网络的原始承载力（不含 AI 语义）：裸测 /download·/upload·/echo，" +
                "无 pacing 干扰、最纯净口径，判断底层网络是否适合 AI 对话/编码/多模态。",
            subScenarios = listOf(
                SubScenario(
                    code = "BN-1", title = "下行排空",
                    uplink = "KB 触发", downlink = "unpaced /download 持续排空（读到即到达）",
                    behaviorHint = listOf(BehaviorTag.DOWNLINK_BANDWIDTH),
                ),
                SubScenario(
                    code = "BN-2", title = "上行灌注",
                    uplink = "应用层 socket 持续发送", downlink = "2xx 确认",
                    behaviorHint = listOf(BehaviorTag.UPLINK_BURST),
                ),
                SubScenario(
                    code = "BN-3", title = "时延基线",
                    uplink = "echo 小包", downlink = "echo 回包（剔驻留）",
                    behaviorHint = listOf(BehaviorTag.LOW_LATENCY),
                ),
            ),
        ),
        metricSpecs = listOf(
            MetricSpec(
                id = "D1", name = "下行速率", unit = "Mbps", group = MetricGroup.D,
                definition = "GET /download 无限速 identity，字节×8/耗时（观测展示口径）",
                direction = Direction.HIGHER_BETTER,
                target = QualityTarget(excellent = 25.0, good = 8.0, fair = 2.0),
                measurability = Measurability.MEASURABLE, scored = false, anchorRef = null,
            ),
            MetricSpec(
                id = "U1", name = "上行速率", unit = "Mbps", group = MetricGroup.U,
                definition = "POST /upload 应用层 socket 发送吞吐（≈真实上行）",
                direction = Direction.HIGHER_BETTER,
                target = QualityTarget(excellent = 20.0, good = 5.0, fair = 1.0),
                measurability = Measurability.MEASURABLE, scored = false, anchorRef = null,
            ),
            MetricSpec(
                id = "N1", name = "时延 RTT", unit = "ms", group = MetricGroup.N,
                definition = "POST /echo 应用层往返 P50，剔服务端驻留(t2−t1)、剔预热",
                direction = Direction.LOWER_BETTER,
                target = QualityTarget(excellent = 30.0, good = 60.0, fair = 100.0, poorFloor = 300.0),
                measurability = Measurability.MEASURABLE, scored = false, anchorRef = null,
            ),
            MetricSpec(
                id = "N2", name = "抖动", unit = "ms", group = MetricGroup.N,
                definition = "RTT P95−P50（分位差口径，非逐包 IPDV）",
                direction = Direction.LOWER_BETTER,
                target = QualityTarget(excellent = 10.0, good = 30.0, fair = 80.0, poorFloor = 240.0),
                measurability = Measurability.MEASURABLE, scored = false, anchorRef = null,
            ),
            MetricSpec(
                id = "FAIL", name = "请求失败率", unit = "ratio", group = MetricGroup.S,
                definition = "应用层请求非 2xx/IOException 占比",
                direction = Direction.LOWER_BETTER,
                target = QualityTarget(excellent = 0.0, good = 0.005, fair = 0.01),
                measurability = Measurability.MEASURABLE, scored = false, anchorRef = null,
            ),
        ),
        live = listOf(
            LiveMetric("dl", "下行速率", "Mbps", "liveDownMbps", LiveRender.GAUGE, windowMs = 0, refreshMs = 300),
            LiveMetric("ul", "上行速率", "Mbps", "liveUpMbps", LiveRender.GAUGE, windowMs = 0, refreshMs = 300),
            LiveMetric("rtt", "时延", "ms", "rttMs", LiveRender.WAVEFORM, windowMs = 2000, refreshMs = 200),
        ),
        // 网络综合性能独立输出：四门限分级 + AI 场景建议，不并入 Token AQS。
        scoring = ScoringModelSpec(
            engine = "ThresholdGrader",
            weightsTableId = "", // 无 AQS 加权，直接四门限分级
            vetoRules = emptyList(),
            renormalizeOnDesignDefault = false,
            gradeMapId = "fourThreshold",
            recommendationTemplateId = "ai_scenario_fitness",
        ),
    )

    val TOKEN_EXPERIENCE = TestModeProfile(
        id = "token_experience",
        displayName = "Token 体验",
        tagline = "AI 流式交互取证 → AQS 分",
        business = "从真实 AI 交互视角评估体验：首字快不快、吐字稳不稳、卡顿多不多——直接对应" +
            "“用起来爽不爽”。",
        metrics = listOf(
            ModeMetric("Token 速率", "tok/s", dynamic = true),
            ModeMetric("字间时延 ITL", "ms", dynamic = true),
            ModeMetric("首字时延 TTFT", "ms", dynamic = false),
            ModeMetric("卡顿", "次", dynamic = false),
        ),
        conclusion = "多场景 KPI 加权 → AQS 分与分级（优/良/可/差）+ 取证明细视图。",
        // ── v2 4-facet（PROFILE_FRAMEWORK §2）────────────────────────────
        version = "token-profile@0.3.0",
        businessType = BusinessType(
            summary = "用户在 kimi/deepseek/qwen 对话框的多模态互动——上行 KB 文本、MB 文档、" +
                "10MB 图、100MB 视频（大小可调、可多次）；下行返回文本/文档/图片/视频。ANEB 为模拟" +
                "（非真实 API 接入），stimulus 由服务端行为模型确定性生成。",
            subScenarios = listOf(
                SubScenario(
                    "TK-1", "纯文本对话",
                    uplink = "KB 文本（~2KB 单次微突发，chunk 2KB）",
                    downlink = "稳态 token 流（40 tps，600 tok）",
                    behaviorHint = listOf(BehaviorTag.LOW_LATENCY, BehaviorTag.STABILITY),
                ),
                SubScenario(
                    "TK-2", "文档理解",
                    uplink = "MB 文档（0.5–5MB，可多次，chunk 64KB）",
                    downlink = "结构化摘要流（40–60 tps）",
                    behaviorHint = listOf(BehaviorTag.UPLINK_BURST, BehaviorTag.LOW_LATENCY),
                ),
                SubScenario(
                    "TK-3", "图片多模态",
                    uplink = "10MB 图（上下行交替，可多次）",
                    downlink = "视觉分析代码流（40 tps，200 tok×N）",
                    behaviorHint = listOf(BehaviorTag.UPLINK_BURST, BehaviorTag.STABILITY),
                ),
                SubScenario(
                    "TK-4", "视频多模态",
                    uplink = "100MB 视频（持续大流，单次可调）",
                    downlink = "文本流可夹图/视频返回",
                    behaviorHint = listOf(BehaviorTag.UPLINK_BURST, BehaviorTag.STABILITY),
                ),
                SubScenario(
                    "TK-5", "下行大对象",
                    uplink = "KB 触发指令",
                    downlink = "10–100MB 图/视频 bulk（走 /download，纳入 D1）",
                    behaviorHint = listOf(BehaviorTag.DOWNLINK_BANDWIDTH),
                ),
                SubScenario(
                    "TK-6", "编码 Agent",
                    uplink = "MB prompt(512KB) + 工具上行 8KB×8",
                    downlink = "突发簇代码流(100tps，簇间 pause) + 工具下行 2KB×8",
                    behaviorHint = listOf(BehaviorTag.LOW_LATENCY, BehaviorTag.UPLINK_BURST, BehaviorTag.STABILITY),
                ),
            ),
        ),
        metricSpecs = listOf(
            MetricSpec(
                id = "T1", name = "首Token时延 TTFT", unit = "ms", group = MetricGroup.T,
                definition = "prompt 末字节 → 首 token 首字节，减服务端已知注入 dwell（network-only 口径进 AQS）",
                direction = Direction.LOWER_BETTER,
                target = QualityTarget(excellent = 200.0, good = 500.0, fair = 1000.0, poorFloor = 3000.0),
                measurability = Measurability.MEASURABLE, scored = true, anchorRef = "T1_ANCHORS",
            ),
            MetricSpec(
                id = "T2", name = "字间时延 ITL P95", unit = "ms", group = MetricGroup.T,
                definition = "校正 ITL=相邻到达间隔−flush 间隔+名义间隔，剔合帧伪 0 与 resume",
                direction = Direction.LOWER_BETTER,
                target = QualityTarget(excellent = 100.0, good = 200.0, fair = 400.0, poorFloor = 1200.0),
                measurability = Measurability.MEASURABLE, scored = true, anchorRef = "T2_ANCHORS",
            ),
            MetricSpec(
                id = "T3", name = "卡顿率", unit = "ratio", group = MetricGroup.T,
                definition = "校正 ITL>200ms 占比（样本集同 T2 主口径，不含 resume）",
                direction = Direction.LOWER_BETTER,
                target = QualityTarget(excellent = 0.005, good = 0.02, fair = 0.05, poorFloor = 0.15),
                measurability = Measurability.MEASURABLE, scored = true, anchorRef = "T3_ANCHORS",
            ),
            MetricSpec(
                id = "T4", name = "严重卡顿率", unit = "ratio", group = MetricGroup.T,
                definition = "校正 ITL>1000ms 占比；>1% 一票否决封顶 54",
                direction = Direction.LOWER_BETTER,
                target = QualityTarget(excellent = 0.0, good = 0.002, fair = 0.01),
                measurability = Measurability.MEASURABLE, scored = false, anchorRef = null,
            ),
            MetricSpec(
                id = "TPS", name = "TPS", unit = "tok/s", group = MetricGroup.BIZ,
                definition = "有效 TPS=已收 token/到达跨度，对照 offered=rate_tps（达成率辅助）",
                direction = Direction.HIGHER_BETTER,
                target = QualityTarget(excellent = 0.95, good = 0.90, fair = 0.80), // delivered/offered 达成率
                measurability = Measurability.PROXY, scored = false, anchorRef = null,
            ),
            MetricSpec(
                id = "S1", name = "会话完成率", unit = "ratio", group = MetricGroup.S,
                definition = "成功轮次/总轮次；成功=流未截断∧gap≤1%∧无 INVALID∧上传 2xx（传输完整性口径，非 AI 正确率）",
                direction = Direction.HIGHER_BETTER,
                target = QualityTarget(excellent = 0.99, good = 0.97, fair = 0.95, poorFloor = 0.90),
                measurability = Measurability.MEASURABLE, scored = false, anchorRef = null, // 软否决项，非加权
            ),
            MetricSpec(
                id = "TOKB", name = "Token/字节消耗", unit = "count", group = MetricGroup.BIZ,
                definition = "token 事件数 + Σlognormal 字节（确定性已知，不随网络变化）",
                direction = Direction.HIGHER_BETTER,
                target = QualityTarget(), // 无质量门限
                measurability = Measurability.DERIVED, scored = false, anchorRef = null,
            ),
            MetricSpec(
                id = "U1", name = "上行 goodput", unit = "Mbps", group = MetricGroup.U,
                definition = "2xx 口径=字节×8/耗时，含慢启动主口径 + 剔慢启动并列口径",
                direction = Direction.HIGHER_BETTER,
                target = QualityTarget(
                    excellent = 20.0, good = 5.0, fair = 1.0,
                    perPayloadBand = mapOf(
                        "MB" to Band(excellent = 20.0, good = 8.0, fair = 5.0),
                        "10MB" to Band(excellent = 25.0, good = 12.0, fair = 8.0),
                        "100MB" to Band(excellent = 25.0, good = 15.0, fair = 10.0),
                    ),
                ),
                measurability = Measurability.MEASURABLE, scored = true, anchorRef = "U1_ANCHORS",
            ),
            MetricSpec(
                id = "D1", name = "下行 goodput", unit = "Mbps", group = MetricGroup.D,
                definition = "GET /download 无限速 2xx 有效字节×8/耗时，逐次 P50（token 流受 pacing 禁作带宽）",
                direction = Direction.HIGHER_BETTER,
                target = QualityTarget(
                    excellent = 25.0, good = 8.0, fair = 2.0,
                    // §2.3 D1 分档：返回文档/10MB 图 ≥12 良；100MB 视频 sustained ≥15 良/≥25 优
                    perPayloadBand = mapOf(
                        "10MB" to Band(excellent = 20.0, good = 12.0, fair = 8.0),
                        "100MB" to Band(excellent = 25.0, good = 15.0, fair = 10.0),
                    ),
                ),
                measurability = Measurability.MEASURABLE, scored = true, anchorRef = "D1_ANCHORS",
            ),
            MetricSpec(
                id = "N1", name = "RTT P50", unit = "ms", group = MetricGroup.N,
                definition = "echo 应用层往返 P50，剔服务端驻留(t2−t1)、剔 2–3 预热样本",
                direction = Direction.LOWER_BETTER,
                target = QualityTarget(excellent = 30.0, good = 60.0, fair = 100.0, poorFloor = 300.0),
                measurability = Measurability.MEASURABLE, scored = true, anchorRef = "N1_ANCHORS",
            ),
            MetricSpec(
                id = "N2", name = "抖动", unit = "ms", group = MetricGroup.N,
                definition = "RTT P95−P50（分位差口径，非逐包 IPDV）",
                direction = Direction.LOWER_BETTER,
                target = QualityTarget(excellent = 10.0, good = 30.0, fair = 80.0, poorFloor = 240.0),
                measurability = Measurability.MEASURABLE, scored = true, anchorRef = "N2_ANCHORS",
            ),
            MetricSpec(
                id = "U2", name = "工具循环时延 P95", unit = "ms", group = MetricGroup.C,
                definition = "tool_loop 单轮 − 服务端 proc 的 P95（proc 优先用实测 X-Aneb-Trecv/Tsend）；仅 TK-6",
                direction = Direction.LOWER_BETTER,
                target = QualityTarget(excellent = 150.0, good = 300.0, fair = 600.0, poorFloor = 1800.0),
                measurability = Measurability.MEASURABLE, scored = true, anchorRef = "U2_ANCHORS",
            ),
            MetricSpec(
                id = "LOSS", name = "丢包代理", unit = "ratio", group = MetricGroup.N,
                definition = "代理 seqGap（TCP 下≈0）+ retrans_total 共变量；无独立门限（诊断/共变量）",
                direction = Direction.LOWER_BETTER,
                target = QualityTarget(),
                measurability = Measurability.NOT_MEASURABLE, scored = false, anchorRef = null,
            ),
        ),
        live = listOf(
            LiveMetric("tps", "Token 速率", "tok/s", "tokenRatePerSec", LiveRender.RUNNING_NUMBER, windowMs = 1000, refreshMs = 200),
            LiveMetric("rtt", "RTT", "ms", "rttMs", LiveRender.WAVEFORM, windowMs = 2000, refreshMs = 200),
            LiveMetric("itl", "字间时延 ITL", "ms", "itlRecentMs", LiveRender.WAVEFORM, windowMs = 2000, refreshMs = 200),
            LiveMetric("up", "上行速率", "Mbps", "liveUpMbps", LiveRender.GAUGE, windowMs = 0, refreshMs = 300),
            LiveMetric("aqs", "AQS 运行分", "", "aqsRunning", LiveRender.RUNNING_NUMBER, windowMs = 0, refreshMs = 0),
        ),
        // 多模态默认取 MM 表；纯文本子场景（TK-1）由采集层改选 WEIGHTS_TOKEN_TXT（U1/D1 设计缺省 renormalize）。
        scoring = ScoringModelSpec(
            engine = "AqsScorer",
            weightsTableId = "WEIGHTS_TOKEN_MM",
            vetoRules = listOf(
                VetoRule(kpiId = "T4", op = "gt", threshold = 0.01, cap = 54.0),
                VetoRule(kpiId = "S1", op = "lt", threshold = 0.95, cap = 70.0),
                VetoRule(kpiId = "S1", op = "lt", threshold = 0.90, cap = 54.0),
            ),
            renormalizeOnDesignDefault = true,
            gradeMapId = "aqsGrade",
            behaviorRuleId = "token_dual_evidence",
            recommendationTemplateId = "token_sla_recommendation",
        ),
    )

    /** 分段开关顺序即此表顺序。默认选中 [TOKEN_EXPERIENCE]（首页 token 体验）。 */
    val ALL = listOf(TOKEN_EXPERIENCE, BASIC_NETWORK)

    fun byId(id: String): TestModeProfile = ALL.firstOrNull { it.id == id } ?: TOKEN_EXPERIENCE
}
