<!-- 由多智能体设计工作流产出、经审阅归档；实现前以此为准 -->

# ANEB Profile 框架设计 v1.0

**副标题：4-Facet 形式化 · Token 类完整范例 · 服务端 AI 行为模拟模型 · 多类别扩展 · AQS/KPI 复用契约**

> 范围声明（沿用 `AqsScorer` KDoc）：本框架所有指标测量对象为「终端至指定仿真节点的应用层端到端路径」，为**实验性应用层指标**，禁表述为 MOS / 无线层评级 / 运营商全网评级 / SLA 结论。所有失败样本记 `null` 绝不记 0（R-10）；样本不足出值但带 `lowConfidence`（R-29）。

---

## 0. 设计总纲与四条不变量

| 编号 | 不变量 | 落地约束 |
|---|---|---|
| INV-1 | **复用而非重写** | 打分 = `KpiCalculator → AqsScorer → aqsGrade` 三层管线原样继承；扩展一律 additive（新权重表 / 新锚点 / 新 KPI），不改公共 API、不改既有测量口径。 |
| INV-2 | **四层职责隔离** | ①服务端 AI 行为模拟模型（造 stimulus，独占「像不像真实 AI」声明，须网络无关+确定性）→②Wire 契约（服务端如实透出自注入 dwell 供 APP 减）→③ANEB APP（只测网络/QoE，把 stimulus 当黑盒）→④打分/呈现（Profile facet-4 驱动）。 |
| INV-3 | **单一事实源** | 权重表、锚点表、门限只有一份定义；派生表（如 `WEIGHTS_V02 = WEIGHTS×0.8 + C`）由基表推导，防两表手工漂移。 |
| INV-4 | **fail-closed 与口径分离** | 「测量失败」(value=null) = 不可计算，绝不 0 顶替；「设计缺省」(该业务本无此 facet) = renormalize 归一化。二者严格区分。 |

---

## 1. Profile 框架（4-Facet 形式化）

### 1.1 四 Facet 的形式定义（通用于所有测试类别）

一个**测试模式 Profile** = 四元组 `⟨BusinessType, MetricSpec[], LiveMetric[], ScoringModel⟩`，对应用户 `/goal` 的四问：**什么业务 · 测哪些指标（含质量目标）· 哪些动态呈现 · 得出什么结论**。

```
Profile
├─ facet1 BusinessType     业务类型 + 子场景表（工作量客观信号）
├─ facet2 MetricSpec[]     全量【业务指标 ∪ 网络指标】+ 每指标质量目标 + 可度量性
├─ facet3 LiveMetric[]     APP 高频动态呈现的关键指标（telemetry 只读通道）
└─ facet4 ScoringModel     打分评估模型/算法（权重·门限·否决·行为分类·建议输出）
```

### 1.2 形式化数据结构（实现就绪 Kotlin 契约）

现 `E:\C Project\ANEB\app\probe\src\main\java\com\aneb\probe\ui\TestModeProfile.kt` 仅四浅字段（`tagline/business/metrics{name,unit,dynamic}/conclusion`），无法承载「全量指标+质量目标+口径+可度量性+打分模型引用」。下面是**演进版**（v2），保持 `displayName/tagline` 供分段开关与标题不改，其余升级为 4-facet 形式化契约：

```kotlin
// ui/TestModeProfile.kt  —— v2（4-facet 形式化；additive 演进，旧字段保留）
data class TestModeProfile(
    val id: String,
    val version: String,            // 新增：模式档版本，发布即冻结、改必升版本（对齐 ScenarioProfile 合同）
    val displayName: String,        // 分段开关/标题（保留）
    val tagline: String,            // 一句话副标（保留）

    // ── facet1 业务类型 ───────────────────────────────
    val business: BusinessType,

    // ── facet2 全量指标 + 质量目标 + 可度量性 ─────────
    val metrics: List<MetricSpec>,

    // ── facet3 APP 动态呈现关键指标 ───────────────────
    val live: List<LiveMetric>,

    // ── facet4 打分模型/算法 ──────────────────────────
    val scoring: ScoringModelSpec,
)

/** facet1：业务类型 + 客观工作量子场景（行为分类的输入 A）。 */
data class BusinessType(
    val summary: String,                       // 评估的真实场景（旧 business 文本迁入）
    val subScenarios: List<SubScenario>,       // 子场景表（上下行工作量信号）
)
data class SubScenario(
    val code: String, val title: String,       // e.g. "TK-3","图片多模态"
    val uplink: String, val downlink: String,  // 工作量描述（字节/突发/token 流）
    val behaviorHint: List<BehaviorTag>,        // 声明式提示（最终标签由 facet4 双证据判定）
)
enum class BehaviorTag { UPLINK_BURST, LOW_LATENCY, DOWNLINK_BANDWIDTH, STABILITY }

/** facet2：一条指标的完整规格。业务指标与网络指标同构，group 区分。 */
data class MetricSpec(
    val id: String,                 // "T1","U1","D1","BM-01"…（映射 KpiCalculator / report 字段）
    val name: String, val unit: String,
    val group: MetricGroup,         // T 流式 / U 上行 / D 下行 / N 基线 / C 连续性 / S 成功率 / BIZ 业务代理
    val definition: String,         // 计时端点/口径（含减法项，如剥服务端 dwell）
    val direction: Direction,       // LOWER_BETTER / HIGHER_BETTER
    val target: QualityTarget,      // 质量目标（四级门限 + 达标比例口径）
    val measurability: Measurability, // 可度量性：MEASURABLE / PROXY / DERIVED / NOT_MEASURABLE + 局限说明
    val scored: Boolean,            // 是否进 AQS 加权（TPS/Token 消耗=false，仅呈现/元数据）
    val anchorRef: String?,         // 复用哪张 AnchorMap（"T1_ANCHORS"…），null=不打分
)
enum class MetricGroup { T, U, D, N, C, S, BIZ }
enum class Direction { LOWER_BETTER, HIGHER_BETTER }
enum class Measurability { MEASURABLE, PROXY, DERIVED, NOT_MEASURABLE }

/** 质量目标：四级锚点 + 达标比例（低者优→P95≤X；高者优→P5≥X）。 */
data class QualityTarget(
    val excellent: Double?, val good: Double?, val fair: Double?, val poorFloor: Double?,
    val slaPercentile: Double,      // 0.95 默认
    val slaTargetLevel: Level = Level.GOOD, // 建议 SLA 取到哪一级门限
    val perPayloadBand: Map<String, Band>? = null, // 分档门限（如 MB/10MB/100MB 上行）
)
enum class Level { EXCELLENT, GOOD, FAIR, POOR }
data class Band(val excellent: Double, val good: Double, val fair: Double)

/** facet3：动态呈现关键指标（LiveTelemetry 只读源，R-16 不参与测量口径）。 */
data class LiveMetric(
    val id: String, val label: String, val unit: String,
    val source: String,             // "tokenRatePerSec"/"rttMs"/"itlRecentMs"/"liveUpMbps"…
    val render: LiveRender,          // WAVEFORM / GAUGE / RUNNING_NUMBER / BAR
    val windowMs: Int, val refreshMs: Int,
)
enum class LiveRender { WAVEFORM, GAUGE, RUNNING_NUMBER, BAR }

/** facet4：打分模型规格（引用单一事实源的权重/锚点/否决）。 */
data class ScoringModelSpec(
    val engine: String = "AqsScorer",          // 复用打分引擎
    val weightsTableId: String,                // "WEIGHTS_TOKEN_MM" / "WEIGHTS_TOKEN_TXT" / "WEIGHTS" / …
    val vetoRules: List<VetoRule>,             // T4>1%→cap54；S1<90%→cap54…（同 AqsScorer 机制）
    val renormalizeOnDesignDefault: Boolean,   // 设计缺省 KPI 是否归一化（区别于 null 失败）
    val gradeMapId: String = "aqsGrade",       // 优/良/可/差分档线复用
    val behaviorRuleId: String,                // 行为分类规则（双证据）
    val recommendationTemplateId: String,      // 建议输出模板
)
data class VetoRule(val kpiId: String, val op: String, val threshold: Double, val cap: Double)
```

### 1.3 与现有代码的对接关系（三层 Profile 概念对齐，勿混淆）

| 层 | 类型 | 归属 | 粒度 | 本框架动作 |
|---|---|---|---|---|
| 模式级 | `ui/TestModeProfile.kt` | APP | 一种测试模式（Token 体验 / 基本性能 / 语音…） | **本节 v2 扩展主体** |
| 场景级 | `engine/ProfileModels.kt::ScenarioProfile` | Wire 合同（Go `profiles.go` ↔ Kotlin） | 一条 s1/s2/s3 场景 + phases + `presentation` | facet2/3/4 的**权威投影源**；模式级引用它 |
| 呈现级 | `ScenarioProfile.presentation{liveMetricLabel, metricIds, conclusionPolicyId, liveWindowMs, uiRefreshMs}` | Wire（codex 树已有） | UI 动效/结论策略 | facet3/facet4 的下沉字段，模式级 Profile 与之对齐 |

**扩展落地要点**：`TestModeProfiles.ALL` 仍是「加一个 profile = 加一种模式」，但每个 `MetricSpec.anchorRef` / `ScoringModelSpec.weightsTableId` 只**引用** `AqsScorer` 内已冻结的锚点与权重表（字符串键控），Profile 本身不复制阈值数字——避免 UI 与打分引擎两处漂移（INV-3）。

---

## 2. Token 类测试 Profile（完整范例）

`id = "token_experience"`，`version = "token-profile@0.4.0"`，绑定 `behavior_model_id` 见 §3。

### 2.1 Facet-1｜业务类型 + 子场景表

**业务类型**：用户在 kimi.com / chat.deepseek.com / qianwen.com 对话框的**多模态互动**——上行有 KB 文本、MB 文档（PPT/Word/PDF）、10MB 图片、100MB 视频（大小可调、可多次）；下行是返回的文本/文档/图片/视频。ANEB 为**模拟**（非真实 API 接入），stimulus 由 §3 的服务端行为模型确定性生成。

| 子场景 | 上行工作量 | 下行工作量 | 声明行为特征 | 映射 phase |
|---|---|---|---|---|
| **TK-1 纯文本对话** | KB 文本（~2KB 单次微突发，chunk 2KB） | 稳态 token 流（40 tps，600 tok，median 120B） | 低时延 + 下行稳定 | clock_sync→upload_burst→token_stream |
| **TK-2 文档理解** | MB 文档（0.5–5MB，可多次，chunk 64KB） | 结构化摘要流（40–60 tps） | 上行中等突发 + 下行低时延 + 长 think(2–3s) | upload_burst→think_pause→token_stream |
| **TK-3 图片多模态** | 10MB 图（上下行交替，可多次） | 视觉分析代码流（40 tps，200 tok×N） | 上行大突发 + 上下行交替稳定 | upload_burst↔token_stream×N |
| **TK-4 视频多模态** | 100MB 视频（持续大流，单次可调） | 文本流可夹图/视频返回 | 上行持续大带宽 + 会话稳定（C1/C2 权重升） | upload_burst(100MB)→think→token_stream |
| **TK-5 下行大对象** | KB 触发指令 | 10–100MB 图/视频 **bulk**（走 `/api/v1/download` 或归基本性能模式） | 下行大带宽 | trigger→**download_burst**（新增） |
| **TK-6 编码 Agent** | MB prompt(512KB) + 工具上行 8KB×8 | 突发簇代码流(cluster 100tps，簇间 pause 300–800ms) + 工具下行 2KB×8 | 低时延往返 + 突发簇稳定 + 上行突发 | upload_burst→tool_loop×8→token_stream(burst) |

> 关键取舍：TK-5 下行大带宽**不能用 token 流测**（token 流受 `rate_tps` pacing）；须走无节流 `/download` 端点或新增 `download_burst` 相位（见 §2.4 D1 / §3）。

### 2.2 Facet-2a｜全量【业务指标】表（定义 + 质量目标 + 模拟可度量性）

| ID | 指标 | 定义（计时端点/口径） | 质量目标（四级 / 达标比例） | 模拟可度量性 & 进 AQS |
|---|---|---|---|---|
| BM-01 | 上传送达时延 | 上传首字节 write → 2xx 响应头首字节（服务端读完 body 才回 2xx=代理锚点） | KB(TK-1)：<300/800/2000ms；MB+ 改用 U1 goodput 门限+达标比例 | MEASURABLE，单端免时钟同步；不含握手（连接复用）。经 U1 打分，本身作伴随量 |
| BM-02 | 首Token时延 TTFT (T1) | prompt 末字节 → 首 token 首字节，**减服务端已知注入 dwell**（think_pause + prelude srv_ts_us→pre_flush_us） | <200/500/1000ms（否则差）；**权重 0.18(MM)/0.25(TXT)** | MEASURABLE；双报 raw(含 AI dwell，可感知口径)+network-only(剥 dwell，进 AQS)。**进 AQS** |
| BM-03 | TPS | 有效 TPS = 已收 token/到达跨度，对照 offered=rate_tps | 相对达成率 delivered/offered ≥0.95/0.90/0.80；不设绝对门限 | PROXY，**不进 AQS**：服务端固定 pacing，健康网络 TPS≈offered，不随带宽提升。仅 facet3 动效 + 达成率辅助 |
| BM-04 | 字间时延 ITL P95 (T2) | 校正 ITL=相邻到达间隔−flush 间隔+名义间隔，剔合帧伪 0 与 resume | <100/200/400ms；**权重 0.12(MM)/0.18(TXT)** | MEASURABLE 主口径，下行流畅度最灵敏信号。依赖服务端双时戳。**进 AQS** |
| BM-05 | 卡顿/严重卡顿 (T3/T4) | T3=校正 ITL>200ms 占比；T4=>1000ms 占比 | T3<0.5%/2%/5%（权重 0.15(MM)/0.22(TXT)）；**T4=0/<0.2%/≤1%，>1% 一票否决封顶 54** | MEASURABLE；金样本本地回环 T3 应=0（R-09）。**T3 进 AQS，T4 否决** |
| BM-06 | 会话完成率 (S1) | 成功轮次/总轮次；成功=流未截断 ∧ gap≤1% ∧ 无 INVALID ∧ 上传 2xx | ≥99%/97%/95%（达标比例口径） | MEASURABLE（传输完整性口径，**非 AI 答案正确率**）。**新增 S1，软否决：<95%封顶70、<90%封顶54** |
| BM-07 | Token/字节消耗 | token 事件数(200/300/600/800) + Σlognormal 字节 | 无质量门限 | DERIVED，确定性完全已知但不随网络变化。**绝不进打分**，仅 workload/cost 元数据 |
| BM-08 | 上行 goodput (U1) | 2xx 口径=字节×8/耗时，含慢启动主口径 + 剔慢启动并列口径 | >20/5/1Mbps（否则差）；分档见 §2.3；**权重 0.15(MM)** | MEASURABLE；慢启动剥离需 ≥16 块(≥1MB)，KB 档只测时延。**进 AQS** |
| BM-09 | 下行 goodput (D1) | 口径(a)token 流=受节流**禁作带宽**；口径(b)=`/download` 无限速 字节×8/耗时 | 仅口径(b)设门限，见 §2.3 | 口径(a)NOT_MEASURABLE；口径(b)MEASURABLE。**新增 D1 进 AQS，权重 0.15(MM)** |
| BM-10 | RTT P50 (N1) | echo 应用层往返 P50，剔服务端驻留(t2−t1)，剔 2–3 预热样本 | <30/60/100ms（否则差）；权重 0.10 | MEASURABLE（应用层 echo，非无线层/ICMP）。**进 AQS** |
| BM-11 | 抖动 (N2) | RTT P95−P50 | <10/30/80ms（否则差）；权重 0.10 | MEASURABLE（分位差口径，非逐包 IPDV）。**进 AQS** |
| BM-12 | 丢包 | 无一等 KPI；代理 seqGap（TCP 下≈0）+ retrans_total(TCP_INFO 共变量) | 无独立门限（诊断/共变量） | NOT_MEASURABLE（作一等指标）。绝不写 0 顶替(R-10)。经 stall/ITL 间接反映 |
| BM-13 | 工具循环时延 (U2) | tool_loop 单轮 − 服务端 proc 的 P95（proc 优先用 X-Aneb-Trecv/Tsend 实测） | <150/300/600ms；权重 0.05(MM)/0.05(TXT)。**仅 TK-6 适用** | MEASURABLE（proc 固定 200ms 模拟工具，剥离后反映网络往返）。**进 AQS** |

### 2.3 Facet-2b｜全量【网络指标】表（口径 + 分档门限「X Mbps 达 95%」）

| ID | 网络指标 | 口径/端点 | 质量目标（达标比例=P5≥X 或 P95≤X） | AQS 锚点复用 |
|---|---|---|---|---|
| N1 | RTT P50 | `POST /echo` 四时间戳，剔驻留 t2−t1，剔预热 | RTT P95 ≤100ms 达 95%（可）；良 P50≤60、优≤30 | `N1_ANCHORS` 30/60/100 |
| N2 | 抖动 P95−P50 | 同 echo 样本集 | ≤30ms 达 95%（良）；硬门限 ≤80ms | `N2_ANCHORS` 10/30/80 |
| U1 | 上行 goodput（含慢启动） | `POST /upload` 64KB 读、读完回 2xx | **分档**：MB 文档 ≥8Mbps 达 95%；10MB 图 ≥12；100MB 视频 sustained ≥15（良）/≥25（优） | `U1_ANCHORS` 1/5/20（**Token 大文件档建议上调 10/20/40 或按 payload 独立分档**） |
| U1x | 上行持续吞吐（剔慢启动） | 服务端 `chunk_us` 权威序列 → `estimateSlowStart` | 100MB 稳态 ≥20Mbps 达 95%；10MB 稳态 ≥15；爬坡段 ≤前 1–2s/若干 MB | 同 U1 并列口径；大文件建议新增「剔前 2s 后每 1s 滑窗 P50/最小值」量化 sustained |
| D1 | 下行 goodput（**新增**） | `GET /download?bytes=N` 无限速、identity、精确 Content-Length | 返回文档/10MB 图 ≥12Mbps 达 95%；100MB 视频 sustained ≥15（良）/≥25（优） | **新增 `D1_ANCHORS=[0→0,2→55,8→70,25→85,100→100]`**（结构同 U1，高者优） |
| T2 | 校正 ITL P95 | `SseReader` arrivalNanos + 服务端 seq/sched_us/pre_flush_us，按 seq join | ≤200ms 达 95%（可）；优 ≤100 | `T2_ANCHORS` 100/200/400 |
| T3/T4 | 卡顿/严重卡顿率 | 同 T2 样本集（剔 coalesced/resume） | T3<2% 达（良）/硬 <5%；**T4<1%（超即否决封顶 54）** | `T3_ANCHORS` 0.5%/2%/5%；`T4_VETO_THRESHOLD=0.01→CAP=54` |
| U2 | 工具循环往返 P95 | `POST /toolloop?proc_ms=&down_bytes=`，剔 proc，每场景新建连(evict) | ≤300ms 达 95%（良）/硬 ≤600ms | `U2_ANCHORS` 150/300/600 |
| LOSS | 丢包代理/完整性 | seqGap/dup + truncatedEarly + http 非 2xx/IOException | seqGap<0.5%（硬 gate 1%→`GAP_EXCEEDED`）；截断=0→`TRUNCATED` 剔场景；http 失败<1% | 有效性 gate，**不进 AQS 加权** |

> **达标比例统一口径**：吞吐类「≥X Mbps 达 95%」⇔ 分布 **P5≥X**（保障级=worst-5% 慢尾）；时延类「≤X ms 达 95%」⇔ **P95≤X**，与 `KpiCalculator.percentileOrNull` 最近秩(rank=ceil(p×n))同源。单场景输出 P50/P95，跨 run 达标比例由聚合层在多次运行（现基线 362 run）统计。

### 2.4 Facet-3｜APP 动态呈现关键指标（LiveTelemetry 只读，R-16）

| Live 指标 | source | 呈现 | 窗口/刷新 | 说明 |
|---|---|---|---|---|
| Token 速率 | `tokenRatePerSec` | RUNNING_NUMBER + WAVEFORM | 1s / 200ms | 与 BM-03 同源；`TPS≈1000/ITL_median`，仅动效不进打分 |
| RTT | `rttMs` | WAVEFORM | 2s / 200ms | 实时波形，观测抖动直觉 |
| 字间时延 ITL | `itlRecentMs` | WAVEFORM | 2s / 200ms | 最近若干 token 的粗粒度 ITL（非 KPI 主口径） |
| 上行速率 | `liveUpMbps`/`upMbps` | GAUGE | 大文件上传期 / 300ms | TK-2/3/4 上传爬坡实时可视 |
| AQS 运行分 | `aqsRunning` | RUNNING_NUMBER | 场景末 / — | 边测边累积的运行态 AQS |

### 2.5 Facet-4｜打分算法（公式 + 权重 + 门限来源 + 行为分类 + 建议输出）

**三层管线（复用 `KpiCalculator→AqsScorer→aqsGrade`，additive 扩展）**

1. **指标层**：复用 T1/T2/T3/T4/U1/U2/N1/N2；新增 **D1**（同 U1 口径，2xx 有效字节÷耗时，逐次 P50，`MIN_DOWNLOAD=3`）、**S1**（成功轮次÷总轮次）。
2. **分项分层**：每 KPI 过 `AnchorMap` 分段线性（优/良=85、良/可=70、可/差=55，端点 clamp）得 0–100 子分。复用现 7 张锚点表 + 新增 `D1_ANCHORS`。
3. **综合分层**：`total = Σ subScoreᵢ × weightᵢ`；沿用 T4 一票否决 `t4>0.01 → min(total,54)`；新增 S1 软否决 `<0.95→min(total,70)`、`<0.90→min(total,54)`（与 T4 同机制）；`aqsGrade` 出优/良/可/差。

**权重表（单一事实源派生，随 profile 模态选表）**

| 表 | T1 | T3 | T2 | U1 | D1 | U2 | N1 | N2 | Σ | 适用 |
|---|---|---|---|---|---|---|---|---|---|---|
| `WEIGHTS_TOKEN_MM`（多模态 s3） | 0.18 | 0.15 | 0.12 | 0.15 | 0.15 | 0.05 | 0.10 | 0.10 | 1.00 | 含 MB/10MB/100MB 上下行 |
| `WEIGHTS_TOKEN_TXT`（纯文本 s1） | 0.25 | 0.22 | 0.18 | — | — | 0.05 | 0.15 | 0.15 | 1.00 | 上传≪1MB、无媒体返回 |

> `WEIGHTS_TOKEN_TXT` 中 U1/D1 属**设计缺省**（业务本无大上下行）→ 按 INV-4 剔除后对在场 KPI **renormalize**；须与「测量失败(value=null)不可计算绝不 0」严格区分。相对 v0.1，MM 表抬升上下行(U1+D1=0.30)与 TTFT、压低 tool_loop。

**门限来源（人因预算 × profile 工作量反推，非拍脑袋）**

- T1 200/500/1000ms：<200ms 瞬时感、<1s 心流、>1s 游离、>3s 放弃。
- T2 100/200/400ms：阅读速度反推 10/5/2.5 tok/s。
- T3 0.5%/2%/5% + T4 veto 1%：200ms=一次可感停顿；~300 token 流下 5%≈15 次可见顿挫。
- U1 20/5/1Mbps、D1 25/8/2Mbps：按最大件在交互容忍预算内传完反推 `R=Size×8/T_budget`（100MB/40s≈20Mbps 优；返回下行略高于上行+蜂窝下行利好，故 D1 锚点整体高于 U1）。
- N1 30/60/100ms、N2 10/30/80ms、U2 150/300/600ms：RTT 构成 TTFT/tool_loop 下界；抖动是 ITL 方差上游；agentic 单轮净网络预算。
- S1 99/97/95%：生产级 AI 服务可容忍失败交互率。

**行为特征分类（双证据：客观工作量信号 A ∧ 该 facet 为绑定约束 B）**

- 输入 A（`ScenarioProfile.phases` 已落库）：∑上行字节/轮、峰均比、下行媒体字节、token 流长、tool_loop rounds、think_pause 有无。
- 输入 B（本次测量）：`painᵢ = weightᵢ×(100−subScoreᵢ)`，按组(T/U/D/N)汇总，Top 组=绑定约束。
- 四标签规则：
  - **上行突发**：∑上行/轮 ≥10MB ∨ 峰均比高 → 发标；U1 pain 居前=「未满足」。
  - **低时延**：短上下文多轮 ∧ (T1+N1) pain 占比高 → 发标。
  - **下行大带宽**：下行媒体 ≥10MB ∧ D1 pain 居前 → 发标。
  - **稳定性**：长流 ∨ 会话连续 ∧ (T2/T3/N2 或 v0.2 的 C1/C2) pain 居前 → 发标。
- 输出每标签 `{触发证据(工作量量值), 是否被网络满足(绑定 KPI 分级), 量化强度=facet pain÷总 pain}`。多标签可并存（s3 典型「上行突发+下行大带宽+稳定性」；s1 典型「低时延」单标）。

**网络建议输出模板（只对命中标签的绑定 facet 输出，避免全量堆砌）**

```
实测（P=本 run 实际达标比例）：
  本次 上行>5Mbps 达 82%、RTT<60ms 达 91%、下行>8Mbps 达 76%、ITL<200ms 达 88%
建议 SLA（P=95%，X=目标分级门限=良锚，业务要求高取优锚）：
  为达良级 Token 体验，建议 上行>5Mbps≥95%、下行>8Mbps≥95%、RTT<60ms≥95%、
  ITL<200ms≥95%、严重卡顿率<1%
facet→条目：上行突发→上行条；下行大带宽→下行条；低时延→TTFT/RTT 条；稳定性→ITL/抖动/stall 条
```

---

## 3. 模拟模型（驻留服务端，与 APP 并行）

**目标**：一套**网络无关 + 确定性 + 可标定 + 可冻结**的 AI 行为模型，让 stimulus「像真实 kimi/deepseek/qwen」，好让 APP 把网络单独隔离测量。现服务端 8 端点（`echo/profiles/stream/upload/download/toolloop/results/serverinfo`）的 stimulus 完全确定性，但缺 7 处保真：真实 TTFT 分布、非平稳 TPS/frame-batching、多模态 payload 结构、下行渐进生成节奏、think 复杂度函数、真实失败/token 计量、每模型标定证据。

### 3.1 A 层｜Payload Profiles（上下行内容模型，按 业务×模态）

- **上行**：`text(KB)` / `document(MB，真实压缩性+multipart 边界开销)` / `image(10MB)` / `video(100MB，分块+断点续传)`。参数化为 upload **campaign**`{modality, size_dist, repeat_count, inter_upload_gap}`。扩展 `upload_burst` phase 增 `content_class` 与 chunk/resumable 语义；服务端**仍只记 `chunk_us`**（保持 U1 单端可测不变）。
- **下行**：文本延用 `token_stream`；新增 **`artifact_stream{class:doc/image/video, total_bytes, generation_cadence}`**——按「生成节奏」渐进吐字节（限速曲线由模型给，区别于 `/download` 不限速裸测），把「AI 边生成边下发」建模出来。TK-5 bulk 下行用新增 **`download_burst`** 相位接 `/download`，goodput 纳入 KpiResult/AQS(D1)。

### 3.2 B 层｜响应时序 / TPS 模型（每模型参数化）

- **TTFT 模型**：首 token 前注入 `ttft_us = base_queue + prefill_slope·input_tokens + model_const`，从标定分布（shifted-lognormal/gamma）按 `model_id` 抽样。服务端经 prelude/首 event **显式透出注入值**（延用 `srv_ts_us/sched_us` 口径），使 APP 的 T1 减法项（`KpiCalculator.TtftSample` 契约中「服务端已知注入时延」）**真正非零、可减**——补上当前「减法项恒为 0」的缺口。
- **解码 TPS 模型**：每模型 `mean_tps + jitter + 上下文衰减(rate_schedule 非平稳)` + SSE `frame-batching(tokens_per_frame` 按 vendor 匹配`)`；token 字节改为每模型 byte/token 直方图，替换全局写死的 `median=120/sigma=0.6`。
- **think 模型**：`think_us = f(task_class, input_size, model)`；reasoning 模型 think 期间按低 TPS 吐 think token（替换现 `think_pause` 客户端固定常数）。
- **确定性契约**：全部经 `tokengen.GenerateTokens` 落地——同 seed+同参数包 ⇒ 逐 token 完全相同时刻表（`tokengen.go` 已有不变量），仅把参数从「全局常数」升级为「每模型参数包」。

### 3.3 标定到真实 kimi/deepseek/qwen

- **采集**：`tools/capture` + `apiprobe/AiReachabilityProbe`（或 mockllm 式适配器）抓真实端点 SSE/上传/下载 ground-truth trace。
- **拟合**：对 TTFT 分布、TPS 分布/衰减、frame-batching、token 字节直方图、上下行大小与节奏曲线做参数估计，产出**版本化参数包** `behavior-model-v0.x/{kimi,deepseek,qwen}`（单一事实源，防漂移）。
- **绑定**：profile 增字段 `behavior_model_id@version + model_provider`；profile+seed→确定性重放。随包附**真实端点采样溯源**（trace 出处、拟合参数、残差/拟合优度），使评审可核验「截至日期 X 本模拟匹配真实 AI」——这是当前最薄弱、最该补的证据链（现唯一近似标定物仅 `median120/sigma0.6` 常数，无 provenance）。

### 3.4 与 APP 的边界（解耦点 = 减法接口）

| 契约面 | 服务端如实透出 | APP 据此减掉的服务端伪迹 |
|---|---|---|
| `/stream` | `sched_us / pre_flush_us` + summary 四数组(`timer_late`服务端失真 vs `flush_block`网络回压严格分列) + `retrans_total` | 校正 ITL 剥服务端调度漂移；TTFT 剥注入 dwell |
| `/upload` | `chunk_us` 逐块到达权威序列 | 慢启动段估计（U1x） |
| `/toolloop` | `X-Aneb-Trecv/Tsend-Us` 实测 proc | U2 剥固定 proc |
| `/serverinfo` | `srv_ts_us + anchor_wall_unix_ns` 单调→墙钟映射(R-24) | 时钟对齐 |

> **红线**：行为模型**独占「真实性」声明**且必须网络无关+确定性；APP **从不判断「像不像真实 AI」**，只测网络/QoE。二者靠上述 wire 减法接口解耦。冻结制品并列：`profile@version`（现 0.2.0）+ **新增 `behavior_model_id@version` + 标定证据**，与 `server_version / kpi_set / aqs_version` 同盖入结果溯源。

---

## 4. 另两类测试的框架化草图（4-Facet 要点差异）

### 4.1 AI 实时交互（GPT-Live 式语音互动）

| Facet | 要点 |
|---|---|
| **1 业务类型** | 全双工语音对话：上行连续音频帧（Opus ~24–40kbps 小包高频）+ 下行 TTS 音频流；关注「打断/抢话(barge-in)」「轮次切换」。子场景：连续对话 / 打断插话 / 长时静音保活。 |
| **2 全量指标** | 新 **M 组（媒体实时）**：口到耳时延 `mouth-to-ear`（上行采集→下行播放，端到端）、语音首响时延 `TTS-TTFB`、**帧到达抖动 + PLC/丢帧率**（音频对丢包比 token 敏感）、轮次切换时延、barge-in 生效时延、连续双工稳定性(C1 中断/C2 恢复)。网络指标复用 N1/N2 + 上行小包 RTT。**质量目标**：口到耳 <150/300/400ms（对话自然度红线）；音频丢帧 <1%；抖动 <30ms 达 95%。可度量性：音频需**独立媒体端点**（非 token 流），丢帧可直接测（区别于 token 类丢包不可测）。 |
| **3 动态呈现** | 口到耳时延实时波形、上/下行码率、抖动缓冲深度、丢帧计数——**动效重点从「Token 速率」转向「口到耳时延 + 抖动缓冲」**。 |
| **4 打分侧重** | 权重向 **M 组 + N2 抖动 + C1/C2 稳定性**倾斜（语音对连续性/抖动远比吞吐敏感）；引入类 E-model 的时延-中断联合惩罚；口到耳超红线一票否决。复用 `AnchorMap/veto/aqsGrade` 机制，新增 `M_*_ANCHORS` 与 `WEIGHTS_VOICE`。 |

### 4.2 网络综合性能（basic_network，SpeedTest 式）

| Facet | 要点 |
|---|---|
| **1 业务类型** | 评估这条网络的**原始承载力**（不含 AI 语义）：能否流畅收发大对象、时延是否够低——判断底层网络是否适合 AI 对话/编码/多模态。 |
| **2 全量指标** | 下行速率(Mbps)、上行速率(Mbps)、RTT(ms)、抖动(ms)、应用层请求失败率。**质量目标**：四门限（优良·尚可·偏弱）。全部 MEASURABLE（`/download` `/upload` `/echo` 裸测，无 pacing 干扰，是最纯净口径）。 |
| **3 动态呈现** | 下行/上行速率大表盘 + 时延实时波形（现 `SpeedRunner`/`liveUpMbps` 已有），动效最强。 |
| **4 打分侧重** | 上下行/时延/抖动四门限 → 优良·尚可·偏弱 + **AI 使用场景建议**（「此网络适合 TK-1/2，不适合 TK-4」）。独立输出，不并入 Token AQS。 |

---

## 5. 与现有 AQS/KPI 体系的关系

**复用（口径与门限已存在，原样继承）**

- 三层管线 `KpiCalculator → AqsScorer → aqsGrade`、公共 API 不动。
- T/U/N/C 组 KPI：T1/T2/T3/T4/U1/U2/N1/N2（+ v0.2 的 C1/C2）。
- `AnchorMap.score()` 分段线性、`scoreWith()` 加权循环、`T4_VETO_THRESHOLD=0.01/CAP=54`、`aqsGrade/KpiGrading` 分档线、fail-closed(R-10)、`percentileOrNull` 最近秩。
- 权重派生手法：`WEIGHTS_V02 = WEIGHTS×0.8 + C`（单一事实源）。

**扩展（全 additive）**

- 新权重表 `WEIGHTS_TOKEN_MM / WEIGHTS_TOKEN_TXT`（由单一事实源派生，防漂移）。
- 新锚点 `D1_ANCHORS=[0→0,2→55,8→70,25→85,100→100]`（结构同 `U1_ANCHORS`，高者优）。
- 新 KPI：D1（`MIN_DOWNLOAD=3`）、S1（成功率）；S1 软否决 `<95%→70 / <90%→54`（同 T4 机制）。
- 「设计缺省 renormalize」vs「测量失败 null 不可计算」的区分逻辑（INV-4）。
- 按模态选权重表（`ScoringModelSpec.weightsTableId`）；落库沿用 `report_body.run.aqs.sub_scores`，`ResultAqsBreakdown` 直接引用新表。
- U1 大文件分档门限（10/20/40）或按 payload 独立门限；U1x sustained 滑窗。

**红线（测量口径绝不乱改）**

- T2 校正 ITL 的双时戳 join、U1 goodput 的 2xx 口径、RTT 的 echo 剔驻留口径、慢启动的 `chunk_us` 权威序列——**均不改**。
- TPS **不单列打分 KPI**（T2/T3 是更敏感替身）；Token 消耗**绝不进打分**（固定常数会污染 AQS）；丢包**不设一等门限**（TCP+应用层不可直接测，用 retrans 共变量 + stall/ITL 间接反映）。
- 失败样本 null 绝不 0；claim scope 锁「终端至仿真节点应用层端到端」，禁外推 MOS/无线层/SLA。

---

## 6. 落地路线（分步 + 每步验证）

**门禁（全程）**：build/test gate + 基线 362 run 回归——任何改动须保证既有 S1/S2/S3 的 AQS 子分与总分**不回归**（快照对比）。

### Step 1 — Token Profile 数据结构 + 打分 + UI 结论（纯 APP 侧，先行）

1. 扩展 `ui/TestModeProfile.kt` → v2（§1.2 四 facet 契约），`TOKEN_EXPERIENCE` 填满 §2 四 facet；旧 `displayName/tagline` 保留供分段开关。
2. `AqsScorer` 加 `WEIGHTS_TOKEN_MM/TXT`、`D1_ANCHORS`、S1 软否决、按模态选表逻辑（全 additive）。
3. `KpiCalculator` 加 D1（`/download` 已存在，接 goodput）、S1（成功轮次口径已有字段）。
4. UI facet3 动效接 `LiveTelemetry` 现有源；facet4 结论输出「行为特征 + 网络建议」双条（§2.5 模板）。

**验证**：单测——各权重表 Σ=1.0；renormalize 正确（TXT 剔 U1/D1）；T4/S1 否决触发；金样本本地回环 T3=0（R-09）；`null` 不计 0（R-10）；既有 3 场景 AQS 快照零回归（362 baseline）。

### Step 2 — 服务端 AI 行为模拟模型标定（server 侧，可与 APP 解耦并行）

1. 加 phase：`upload_burst.content_class` + `artifact_stream` + `download_burst`；升 profile 版本。
2. 加 B 层：TTFT 注入（透出可减 dwell）、非平稳 TPS/frame-batching、think 函数、每模型 byte/token 直方图。
3. `tools/capture` 抓 kimi/deepseek/qwen trace → 拟合 → `behavior-model-v0.x/{kimi,deepseek,qwen}` 参数包 + 溯源。
4. profile 绑 `behavior_model_id@version`，盖入结果溯源。

**验证**：确定性重放（同 seed+参数包→逐 token 相同时刻表）；APP 侧 T1 减法项**非零可减**（对比注入前后）；D1 goodput 在 `download_burst` 可测；标定残差/拟合优度随包留证。

### Step 3 — 其它类别落地

1. **网络综合性能**：现 `basic_network` 已具雏形，补 §4.2 facet2 失败率 + facet4「AI 场景建议」。
2. **AI 实时交互（GPT-Live）**：新增音频媒体端点 + M 组 KPI + `M_*_ANCHORS` + `WEIGHTS_VOICE`（§4.1）；复用 veto/grade 机制。

**验证**：每类独立输出、互不污染 Token AQS；语音口到耳/丢帧可测性验证；各模式 `TestModeProfiles.ALL` 加一条即接入（模式表数据驱动分段开关与信息条）。

---

### 关键文件锚点（实现入口）

- `E:\C Project\ANEB\app\probe\src\main\java\com\aneb\probe\ui\TestModeProfile.kt` — facet 契约扩展主体（现 6 字段 → v2 四 facet）。
- `E:\C Project\ANEB\app\probe\src\main\java\com\aneb\probe\scoring\AqsScorer.kt` — 加 `WEIGHTS_TOKEN_*` / `D1_ANCHORS` / S1 软否决（现 `WEIGHTS` L56、`WEIGHTS_V02` L70、锚点 L99–115、veto L50/53）。
- `KpiCalculator.kt` — 加 D1 / S1；`ProfileModels.kt::ScenarioProfile.presentation` — facet3/4 wire 投影；`server/` 的 `tokengen.go / handlers_stream.go / handlers_upload.go / handlers_download.go` — §3 行为模型 phase 与 TTFT 注入落地点。

