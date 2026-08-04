package com.aneb.probe.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * Room 数据模型（阶段 1 全量落库，设计文档 §7）。
 * 时延字段全部可空 Long?：失败/超时记 null，禁 0/哨兵值（R-10 失败样本语义）。
 * v3：TestRun 扩 run 级字段（模式/顺序/AQS/版本/守卫元数据/漂移率）；新增
 * ScenarioResultEntity / EchoSampleEntity；TokenEventEntity 增 scenario/stream 维度。
 */
@Entity(tableName = "test_run")
data class TestRun(
    /** UUIDv7（时间有序，见 TestEngine.newRunId） */
    @PrimaryKey val runId: String,
    val startedAtEpochMs: Long,
    val serverBase: String,
    /** quick / forensic（P1 范围 6） */
    val mode: String,
    /** 实际执行的场景顺序，如 "s1,s2,s3|s2,s3,s1|s3,s1,s2"（拉丁方证据，5.3.6） */
    val scenarioOrder: String,
    /** auto / wifi / cellular（transport 策略，P1 范围 3） */
    val transport: String,
    // ---- 版本字段（结果合同） ----
    val kpiSet: String,
    val aqsVersion: String,
    val profileVersions: String,
    val schemaVersion: String,
    /** profiles 来源：server / assets_fallback（版本不一致告警证据） */
    val profileSource: String,
    val appVersionName: String?,
    val appVersionCode: Long?,
    // ---- 守卫元数据（guardCheck metadata + 拒测原因，JSON/KV 串） ----
    val guardMetadata: String?,
    // ---- AQS（run 级；不可计算记 null，绝不 0） ----
    val aqsScore: Double?,
    val aqsLowConfidence: Boolean?,
    val aqsVetoApplied: Boolean?,
    val aqsNotComputableReason: String?,
    /** run 结束状态：completed / aborted:<reason> */
    val status: String?,
    /** 上报结果：http code / 错误摘要 */
    val reportStatus: String?,
    // ---- AQS v0.2 并列出分（阶段2 C03 遗留接线，v8 additive 列，默认 null=无 v0.2 分支） ----
    // 仅当最近 24h 内存在可用 continuity 结果（C1/C2 均非 null）时填充；
    // 无 C 数据时全部保持 null——v0.1 语义完全不变（AqsScorer 双入口，见 AqsV02Gate）。
    /** aqs-v0.2 分数；v0.2 分支存在但不可计算（如 T/U/N 缺失）时 null */
    val aqsV02Score: Double? = null,
    val aqsV02LowConfidence: Boolean? = null,
    val aqsV02VetoApplied: Boolean? = null,
    val aqsV02NotComputableReason: String? = null,
    /** v0.2 所用 continuity 数据的 runId（展示标注：数据来源可追溯） */
    val aqsV02ContinuityRunId: String? = null,
    /** v0.2 所用 continuity 数据的开始时刻（展示标注：数据时间） */
    val aqsV02ContinuityStartedAtEpochMs: Long? = null,
    /** v0.2 所用 C1 会话中断率（ratio） */
    val aqsV02C1DropRate: Double? = null,
    /** v0.2 所用 C2 切换恢复时间 P50（ms） */
    val aqsV02C2RecoveryMs: Double? = null,
    // ---- SNI 双通道连接可达性（阶段3；v10 additive 列，默认 null=未探测） ----
    // run 前对同一 E-01 分别用 {带 SNI 主机名, bare-IP} 各发 1 次 /serverinfo，
    // 把电信 NR-SA 的 SNI-keyed TLS RST 变成可量化维度（带 SNI vs bare-IP 成功率）。
    // 取值 ok / rst / timeout / error:<摘要>；未探测（如 WiFi 路径不做）保持 null。
    /** 带 SNI 主机名（sslip.io）通道 TLS 握手结果：ok/rst/timeout/error:* 或 null（未探测） */
    val sniReachable: String? = null,
    /** 带 SNI 通道探测耗时（ms）；失败或未探测记 null（禁 0 哨兵，R-10） */
    val sniReachMs: Long? = null,
    /** bare-IP 通道 TLS 握手结果：ok/rst/timeout/error:* 或 null（未探测） */
    val ipReachable: String? = null,
    /** bare-IP 通道探测耗时（ms）；失败或未探测记 null */
    val ipReachMs: Long? = null,
)

@Entity(
    tableName = "token_event",
    indices = [Index("runId"), Index(value = ["runId", "scenarioKey", "streamIndex", "seq"])],
)
data class TokenEventEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val runId: String,
    /** 场景实例键 "profileId#repeat"（取证模式同场景 3 遍需区分） */
    val scenarioKey: String,
    /** 场景内第几个 token_stream phase（0 起） */
    val streamIndex: Int,
    val seq: Long,
    /** 服务端期望发出时刻（单调 us）；缺失记 null */
    val schedUs: Long?,
    /** 服务端实际 flush 前时刻（单调 us）；缺失记 null */
    val preFlushUs: Long?,
    /** 客户端到达时刻（elapsedRealtimeNanos）；未到达/失败记 null */
    val arrivalNanos: Long?,
    val payloadBytes: Int?,
    val sameReadBatch: Boolean,
)

/**
 * 每场景结果（设计文档 §7：各 KPI 值+分级+三态+原因码+每场景网络快照）。
 * KPI 值可空（INVALID 已被 gate 置 null / 失败 null）；分级串随值为 null 时亦 null。
 */
@Entity(
    tableName = "scenario_result",
    indices = [Index("runId")],
)
data class ScenarioResultEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val runId: String,
    val profileId: String,
    val profileVersion: String,
    /** 取证模式第几遍（0 起）；快测恒 0 */
    val repeatIndex: Int,
    /** 该场景在整个 run 内的执行序号（0 起，拉丁方实际顺序证据） */
    val orderIndex: Int,
    val startedAtNanos: Long,
    val endedAtNanos: Long?,
    // ---- 三态 + 原因码 ----
    val validity: String,
    /** 逗号分隔 InvalidReason 名称；空串=无 */
    val invalidReasons: String,
    // ---- KPI 值 + 分级（KpiGrading，agent-qoe-kpi v0.1 门限） ----
    val t1TtftMs: Double?, val t1Grade: String?,
    val t2ItlP95Ms: Double?, val t2Grade: String?,
    val t2ItlP95InclCoalescedMs: Double?,
    val t3StallRate: Double?, val t3Grade: String?,
    val t3StallRateInclResume: Double?,
    val t4SevereStallRate: Double?, val t4Grade: String?,
    val t5ResumeP95Ms: Double?,
    val n1RttP50Ms: Double?, val n1Grade: String?,
    val n2JitterMs: Double?, val n2Grade: String?,
    val u1GoodputMbps: Double?, val u1Grade: String?,
    val u1GoodputExclSlowStartMbps: Double?,
    val u2ToolLoopP95Ms: Double?, val u2Grade: String?,
    val seqGapCount: Int,
    val seqDupCount: Int,
    /**
     * 低置信 KPI 清单（逗号分隔 KPI id，如 "T2,U1_excl_slow_start"；空串=无）。
     * C07：结果页/导出必须能标注 per-KPI lowConfidence（KPI 文档 5.4 展示边界），
     * KpiValue.lowConfidence 在此持久化；缺省 ""（旧行为不变）。
     */
    val lowConfidenceKpis: String = "",
    // ---- 双 clock_sync / skew（C06/R-22） ----
    val offsetStartUs: Long?,
    val offsetStartErrUs: Long?,
    val offsetEndUs: Long?,
    val offsetEndErrUs: Long?,
    /** 漂移率 ppm；不可估记 null */
    val offsetDriftPpm: Double?,
    /** |drift|>100ppm 或首尾任一端缺失（保守置疑） */
    val offsetSuspect: Boolean,
    // ---- 每场景网络快照（R-14） ----
    val netTransport: String?,
    val netCapabilities: String?,
    val netInterfaceName: String?,
    /** 服务端观察到的客户端源 IP:port（路径对账） */
    val serverObservedAddr: String?,
    // ---- 解析自监控（P0-C12） ----
    val parseDurUsTotal: Long?,
    val perEventParseUs: Double?,
    // ---- 批化检测标注（P1-C08 遗留接线，v8 additive 列；BufferingDetector 产出） ----
    // R-05 红线：score/attribution 只作标注与取证证据，绝不参与 validity 判定。
    // 未检测（无残差样本，如流失败/无 token）时全部 null（R-10：绝不记 0 顶替）。
    /** 连续批化分 ∈ [0,1]（BufferingReport.bufferingScore） */
    val bufferingScore: Double? = null,
    /** 初步归因假设（BufferingAttribution.name 小写：none/airlink_suspect/...） */
    val bufferingAttribution: String? = null,
    /** 参与分析的残差样本数 */
    val bufferingSampleCount: Int? = null,
    /** 锯齿占比（正尖峰+负残差簇，批攒-放因果签名） */
    val bufferingSawtoothRatio: Double? = null,
    /** 近零到达间隔占比 */
    val bufferingNearZeroRatio: Double? = null,
    /** 残差滞后1自相关原始值 */
    val bufferingLag1Autocorr: Double? = null,
    /** 批起点（gap-then-burst）个数 */
    val bufferingBatchCount: Int? = null,
    /** 命中率达标的最大周期网格（µs）；无达标 null */
    val bufferingBestGridUs: Long? = null,
    /** 批起点与 app_jank 事件重叠率（R-12 设备侧冻结区分） */
    val bufferingJankOverlapRatio: Double? = null,
    // ---- 场景级无线导出（RADIO_CONTEXT_WIRING_SPEC v1.0，v16 additive 列，D-367） ----
    // 蜂窝场景由 BufferingWiring.radioExport 回填;wifi 场景与 v16 之前的历史行全 null
    // (radioStale==null 即「导出从未运行」,ResultReporter 以此决定不写 radio 块)。
    // 不可得一律 null,禁 0/-1/MAX_VALUE 哨兵(R-10)。
    /** TelephonyManager.dataNetworkType 名称(NR/LTE/…),基集众数 */
    val radioRat: String? = null,
    /** LTE RSRP / NR SS-RSRP 场景中位,dBm */
    val radioRsrpDbm: Double? = null,
    /** LTE RSSNR / NR SS-SINR 场景中位,dB */
    val radioSinrDb: Double? = null,
    /** 物理小区标识,基集众数 */
    val radioPci: Int? = null,
    /** 跟踪区码,基集众数 */
    val radioTac: Int? = null,
    /** 频点号,基集众数 */
    val radioArfcn: Int? = null,
    /** 两个中位数由几个读数得出 */
    val radioSampledN: Int? = null,
    /** 中位数是否只能建立在陈旧样本上(R-02);null=导出未运行 */
    val radioStale: Boolean? = null,
    // ---- per-KPI 样本数(v17 additive 列,D-373;试点报告附二第一建议) ----
    // 「低置信」判词此前只导出结论不导出理由(哪个 KPI 差几个样本),恒真且无从定位。
    // 格式与 lowConfidenceKpis 同一短名词汇:"T1:3,T2:110,…"(名:进入统计的有效样本数);
    // null = 导出未运行(v17 之前的历史行,ResultReporter 据此不写 kpi_quality 块)。
    val kpiSampleCounts: String? = null,
    // ---- D1 半成品补齐（v19 additive 列，T47 批①，D-468/D-469）----
    // KpiCalculator 早已算出 d1GoodputMbps（PROFILE_FRAMEWORK §2.2 BM-09(b)），但此前从未
    // 落库/上线——"契约里要打分，wire 上从未出现"。本列起把它接入既有落库→上报管线。
    // null = 该 run 跑在 D1 上线之前，或本次场景无下行样本（R-10：不可测≠0）。
    val d1GoodputMbps: Double? = null,
    /** 门限复用 KpiGrading.grade("D1",…)（25/8/2，同 AqsScorer.D1_ANCHORS） */
    val d1Grade: String? = null,
    // ---- U3/D3：单流自适应窗口 goodput 探针（v20 additive 列，T47 批③，D-468/D-469；
    //      spec/PROFILE2_THROUGHPUT_PROBE_SPEC.md §8.4.2）----
    // 诊断期不进任何 AQS facet；grade 恒为 null（未接入打分，spec §8.4.4）。
    // sample_count 恒为 1（kpi_quality 词表，非本列）；low_confidence 由 rtt_dominance_ok 决定。
    // null = 该场景未跑 s4_throughput（绝大多数场景）或该 run 跑在批③上线之前。
    val u3GoodputMbps: Double? = null,
    val u3Grade: String? = null,
    val u3GoodputExclSlowStartMbps: Double? = null,
    val u3WindowTargetMs: Int? = null,
    val u3WindowActualMs: Double? = null,
    val u3BytesTransferred: Long? = null,
    val u3RttRefMsPre: Double? = null,
    val u3RttRefMsPost: Double? = null,
    val u3RttDriftRatio: Double? = null,
    val u3RttDominanceRatio: Double? = null,
    val u3RttDominanceOk: Boolean? = null,
    val d3GoodputMbps: Double? = null,
    val d3Grade: String? = null,
    val d3GoodputExclSlowStartMbps: Double? = null,
    val d3WindowTargetMs: Int? = null,
    val d3WindowActualMs: Double? = null,
    val d3BytesTransferred: Long? = null,
    val d3RttRefMsPre: Double? = null,
    val d3RttRefMsPost: Double? = null,
    val d3RttDriftRatio: Double? = null,
    val d3RttDominanceRatio: Double? = null,
    val d3RttDominanceOk: Boolean? = null,
)

/**
 * 上报体原样存档（C07 导出）：run 结束时构造的 /results JSON 原文。
 * 导出 JSON 直接复用该存档（与上报体严格同构，单一事实来源，禁止事后重算产生口径漂移）。
 * 未走到上报构造（guard_rejected / bind_failed / error 早退）的 run 无该行。
 */
@Entity(tableName = "report_body")
data class ReportBodyEntity(
    @PrimaryKey val runId: String,
    val body: String,
)

/**
 * /echo 原始 4 时间戳样本（设计文档 §7 EchoSample：仅本地全量，供 offset 质量事后审计）。
 */
@Entity(
    tableName = "echo_sample",
    indices = [Index("runId")],
)
data class EchoSampleEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val runId: String,
    val scenarioKey: String,
    /** 该 clock_sync phase 在场景内的序号（0=场景首，最后一个=场景尾） */
    val phaseIndex: Int,
    val idx: Int,
    val warmup: Boolean,
    val t0Us: Long,
    val t1Us: Long?,
    val t2Us: Long?,
    val t3Us: Long?,
    val rttUs: Long?,
    val offsetUs: Long?,
    val error: String?,
)

// ---------------------------------------------------------------------------
// 阶段 2 C 组连续性实验结果（KPI 文档 5.1/5.2 C1/C2/C3；设计文档 §8 阶段 2）
// ---------------------------------------------------------------------------

/**
 * 一次连续性实验（continuity 模式 run）的汇总结果。
 * KPI 值可空（无样本/失败 null，禁 0/哨兵值 R-10）；恢复样本原始序列以 CSV 保留。
 * v5 新增表（additive，不动既有表）。
 */
@Entity(
    tableName = "continuity_result",
    indices = [Index("runId")],
)
data class ContinuityResultEntity(
    @PrimaryKey val runId: String,
    val startedAtEpochMs: Long,
    val serverBase: String,
    /** auto / wifi / cellular */
    val transport: String,
    /** 长流参数（tokens=1200 @40tps ≈30s） */
    val tokens: Int,
    val rateTps: Double,
    // ---- C1 会话中断率 ----
    /** 实验内流式段总数（含首段与各重连段） */
    val segmentsTotal: Int,
    /** 异常断开段数（IOException / 无 summary 的流截断） */
    val abnormalDisconnects: Int,
    val c1DropRate: Double?,
    val c1Grade: String?,
    // ---- C2 切换恢复时间 ----
    /** 逐次恢复样本（ms，逗号分隔）；空串=无样本 */
    val recoveryMsCsv: String,
    /** 恢复时间中位数（ms）；无样本 null */
    val c2RecoveryMsP50: Double?,
    val c2Grade: String?,
    /**
     * 跨网迁移恢复的样本数（D-23）：原绑定句柄被真机硬切换拆除、迁到当前新默认网后恢复的次数。
     * 与 [recoveryMsCsv] 样本总数相减即 same_network 重连恢复数（两种 C2 语义，KPI 文档 §5.1）。
     * 实验未进入重连阶段（guard/bind/monitor 失败）或迁移前旧库历史行记 null（R-10）。
     */
    val c2CrossNetworkRecoveries: Int? = null,
    // ---- C3 NAT 静默挂起（阶梯 idle 探测） ----
    /** "idle_s:conn_new:echo_ms:error;..."（ContinuityMath.c3LadderCsv） */
    val c3LadderCsv: String,
    /** 模拟器 NAT 语义与运营商 CGNAT 不同：结果仅证明功能路径，不作 C3 结论 */
    val c3FunctionalOnly: Boolean,
    // ---- 豁免路径监控证据 ----
    /** 实验期间记录的 PATH_CHANGE 事件数（全量入 env_event，但不 invalidate——豁免语义） */
    val pathChangeEvents: Int,
    /** completed / recovery_failed / max_segments_reached / guard_rejected / bind_failed / monitor_failed / error:<cls> */
    val status: String,
    /** 该实验数据可参与的 AQS 版本（aqs-v0.2；出分仍需同环境场景 run 的 T/U/N 数据） */
    val aqsVersionCandidate: String,
)

// ---------------------------------------------------------------------------
// 真实 LLM API 探针结果（阶段 2；claim scope 独立，绝不进 AQS / 不进 /results 上报）
// ---------------------------------------------------------------------------

/**
 * 真实 API 探针单次结果（阶段 2 任务 #7）。
 *
 * - claimScope 恒为 `application_end_to_end_to_llm_api`（与仿真节点口径
 *   application_end_to_end_to_probe_node 明确分开）；**不进 AQS、不进 /results 上报**
 *   （若上报需扩展合同，留 TODO 阶段 3），仅本地 Room + 导出单独归类。
 * - 数值字段全部可空：失败记 null，禁 0/哨兵值（R-10）。
 * - 本行**绝不含 API key**：错误消息等自由文本入库前经 ApiKeyRedactor 兜底（单测锚定）。
 */
@Entity(tableName = "api_probe_result")
data class ApiProbeResultEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val startedAtEpochMs: Long,
    /** anthropic / openai_compat（LlmProvider.id） */
    val provider: String,
    /** anthropic_messages / openai_chat（适配器 protocolId） */
    val protocolId: String,
    /** 请求 base URL（不含 path/query；key 走 header 绝不入 URL） */
    val baseUrl: String,
    val model: String,
    /** 常量 application_end_to_end_to_llm_api（导出合同字段） */
    val claimScope: String,
    val httpCode: Int?,
    /** 传输/协议错误摘要（已过 ApiKeyRedactor）；成功 null */
    val error: String?,
    // ---- 端到端 KPI（对照列口径，不进 AQS） ----
    val ttftMs: Double?,
    val itlMedianMs: Double?,
    val itlP95Ms: Double?,
    val itlSampleCount: Int,
    val tokenEventCount: Int,
    val totalMs: Double?,
    val totalTextChars: Int,
    // ---- 服务端 usage / 结束原因 ----
    val inputTokens: Int?,
    val outputTokens: Int?,
    val stopReason: String?,
    val parseErrors: Int,
    /** 协议层错误（anthropic event:error 等，已过 redactor）；无 null */
    val protocolError: String?,
    // ---- 环境元数据（探针豁免：记录但不拒测，见 ApiProbe KDoc） ----
    val proxyDetected: Boolean,
    val vpnDetected: Boolean,
    val guardMetadata: String?,
    // ---- 读层自监控 ----
    val readCount: Int?,
    val totalBytes: Long?,
)

// ---------------------------------------------------------------------------
// 阶段 2 P2-C05：Cronet TCP(TLS) vs QUIC(h3) 背靠背 A/B（D-17/D-19）
// ---------------------------------------------------------------------------

/**
 * A/B 逐样本结果（v7 新增表，additive）。一行＝一次 Cronet 流样本。
 *
 * - [stack] 恒 "cronet"：两栈计时钩子粒度不同，与 OkHttp 场景 run 数据**不可互比**
 *   （A/B 结论只在 Cronet 栈内得出）；claim scope 仍为 probe_node 口径。
 * - [bin] 分箱（红队"QUIC 启用 ≠ 协商 h3"）：A 组恒 tcp；B 组逐样本按
 *   [negotiatedProtocol] 判定——h3 计 quic，非 h3 计 fallback（**不进对比**）。
 * - 数值字段可空：失败/不可算记 null，禁 0/哨兵值（R-10）。
 * - [sampleIndex] 为 run 内全局执行序（ABAB 交替顺序证据）。
 */
@Entity(
    tableName = "ab_result",
    indices = [Index("runId")],
)
data class AbResultEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val runId: String,
    val startedAtEpochMs: Long,
    val serverBase: String,
    /** 恒 cronet */
    val stack: String,
    /** 恒 application_end_to_end_to_probe_node（同场景 run 口径） */
    val claimScope: String,
    val profileId: String,
    /** profile 内第几个 token_stream phase（0 起） */
    val phaseIndex: Int,
    /** run 内全局执行序（0 起，ABAB 交替证据） */
    val sampleIndex: Int,
    /** a（disableQuic）/ b（enableQuic+hint） */
    val groupLabel: String,
    /** tcp / quic / fallback（分箱结果，见类 KDoc） */
    val bin: String,
    /** 逐样本协商协议（h3 判定唯一依据）；未拿到响应头 null */
    val negotiatedProtocol: String?,
    val httpCode: Int?,
    val error: String?,
    // ---- 每样本 KPI（Cronet 栈内口径） ----
    val ttftMs: Double?,
    val itlP50Ms: Double?,
    val itlP95Ms: Double?,
    val itlSampleCount: Int,
    val stallCount: Int?,
    val stallRate: Double?,
    val gapCount: Int,
    val dupCount: Int,
    val tokenEventCount: Int,
    val truncatedEarly: Boolean,
)

// ---------------------------------------------------------------------------
// 语音模式测量结果（D-42：语音结果落库；PROFILE_FRAMEWORK §4.1 观测口径）
// ---------------------------------------------------------------------------

/**
 * 语音模式单次测量结果（v12 新增表，additive；D-42）。
 *
 * - **观测口径，独立于 token AQS 各表**：v1 paced-proxy 与 v2 server-sim 两口径共用
 *   一表，以 [caliber] 区分（null=v1 paced-proxy；v2 记 VoiceRunner.SIM_CALIBER 原文）。
 *   只存 Done 样本的**实测值**——无 score 列，分数由 AqsScorer 展示时现算，绝不落库重算口径。
 * - 指标字段全部可空：未测/样本不足记 null，禁 0/哨兵值（R-10：Sample 的 null 原样落库）。
 */
@Entity(tableName = "voice_result")
data class VoiceResultEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    /** 落库时刻（epoch ms） */
    val tsEpochMs: Long,
    /** 口径标注（VoiceRunner.Sample.caliber）：null=v1 paced-proxy；v2 记 SIM_CALIBER 原文 */
    val caliber: String?,
    /** 上行入队背压出现过 → 低置信（v2）；v1 恒 false */
    val lowConfidence: Boolean,
    // ---- v1/v2 共用指标（Done 样本；null=未测/样本不足） ----
    /** RTT P50（ms） */
    val rttMs: Double?,
    /** RTT 抖动（ms） */
    val jitterMs: Double?,
    /** 上行帧间抖动 P95（ms，M3；服务端 chunk_us 权威） */
    val upFrameJitterMs: Double?,
    /** 下行帧间抖动 P95（ms，M2；v2 Done 恒 null——由 [downNetJitterMs] 取代） */
    val downFrameJitterMs: Double?,
    /** 口到耳预算（ms，M1 DERIVED；v1 口径） */
    val mouthEarBudgetMs: Double?,
    val framesSent: Int?,
    val framesRecv: Int?,
    // ---- v2 server-sim 尾部指标（v1 行恒 null，D-38） ----
    /** M4 TTS-TTFB P50（ms，已剥服务端驻留） */
    val ttfbP50Ms: Double?,
    /** M4 TTS-TTFB P95（ms） */
    val ttfbP95Ms: Double?,
    /** M2' 下行纯传输抖动 P95（ms，sched_us 差分剥离调度误差） */
    val downNetJitterMs: Double?,
    /** M1' 口到耳实测代理 P50（ms，PROXY） */
    val mouthEarProxyMs: Double?,
    /** M5 轮次切换 P50（ms） */
    val turnSwitchP50Ms: Double?,
    /** M6 打断停帧最大值（ms） */
    val bargeStopMaxMs: Double?,
    /** protocol_ok 轮数（诚实对账） */
    val turnsOk: Int?,
    // ---- v18：M7 输入（D-390 §5 B′；计分实施另批，本轮只落库） ----
    /**
     * M7 最长帧间静默（ms）＝下行帧到达序列的 `max(相邻帧间隔)`。
     *
     * **max 而非分位数**是这个字段的全部意义：M2 用 P95，而 P95 会把「罕见但致命」的
     * 长冻结整个丢掉——实测一次 4.55 秒的冻结在 599 个间隔里只占 0.67%，被切在分位点
     * 之上，于是 M2 报 25.000ms（饱和平台）而读者拿不到「4.5 秒」这个数（D-390 §5.6）。
     *
     * null ＝ 该 run 跑在 M7 落地之前，**不是**「没有静默」。
     */
    val m7MaxFrameGapMs: Double? = null,
    /**
     * 近零到达间隔占比＝`count(帧间隔 ∈ [0, NEAR_ZERO_ARRIVAL_US)) / n`，
     * 复用 `BufferingDetector.NEAR_ZERO_ARRIVAL_US`（1000µs）。
     *
     * 它答**「有没有发生」**（帧是不是批着到的），**不计分**——严重度由
     * [m7MaxFrameGapMs] 承担。两者分工刻意分开：比例量与时长量合成一个分数，
     * 读者就说不出「发生了」和「有多糟」哪个在推动结论（D-390 §5.6 建议 ②③）。
     *
     * null ＝ 该 run 跑在 M7 落地之前。
     */
    val voiceNearZeroArrivalRatio: Double? = null,
)

// ---------------------------------------------------------------------------
// 合成子测结果（恢复子测 weak-recovery-v1 D-40 + 弱网整形对照 weak-capacity-latency-v1 D-43）
// ---------------------------------------------------------------------------

/**
 * 合成子测单次结果（v13 新增表，additive）：恢复子测（[kind]="recovery"）与弱网整形对照
 * （[kind]="shaped"）两类共用一表，以 [kind] 区分，各自不用的列置 null。
 *
 * - **合成口径，独立结论**：来自服务端受控合成合同（受控中断窗口 / 逐 run 隔离整形路径），
 *   ≠ 真实断网/弱覆盖，绝不并入正常测速结论 / AQS 任何分；[confidence] 恒记
 *   LOW/INCONCLUSIVE 标注（单次合成事件不外推）。
 * - 只存 Done 样本的**实测值**，展示直接读落库值不重算（D-02）。
 * - 指标字段全部可空：未测/不可判记 null，禁 0/哨兵值（R-10：Sample 的 null 原样落库）。
 */
@Entity(tableName = "synthetic_result")
data class SyntheticResultEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    /** 落库时刻（epoch ms） */
    val tsEpochMs: Long,
    /** 子测类别：recovery（恢复子测）/ shaped（弱网整形对照） */
    val kind: String,
    /** 合同强制标注（如 "LOW/INCONCLUSIVE(单次合成事件)"）：单次合成事件不外推 */
    val confidence: String,
    // ---- recovery（kind="recovery"；shaped 行恒 null） ----
    /** 恢复时长（ms，触发 202→首个成功 echo）；未恢复/未触发 null */
    val recoveryMs: Double?,
    /** 窗口内服务器确认的受控中断 503 次数（带 outage=active 头） */
    val outage503: Int?,
    /** 质量段成功数 */
    val postSuccess: Int?,
    /** 质量段总数 */
    val postTotal: Int?,
    /** 质量段 RTT P95（ms）；样本不足 null */
    val rttP95Ms: Double?,
    /** 是否满足合同质量目标；不可判 null */
    val meetsTargets: Boolean?,
    // ---- shaped（kind="shaped"；recovery 行恒 null） ----
    /** 整形实测下行峰值（Mbps）；无样本 null */
    val shapedDownMbps: Double?,
    /** 整形实测上行峰值（Mbps）；无样本 null */
    val shapedUpMbps: Double?,
    /** 整形完成态 RTT（ms）；未测 null */
    val shapedRttMs: Double?,
)

// ---------------------------------------------------------------------------
// 环境事件时间轴（设计文档 §7 EnvEvent：设备侧冻结 vs 链路缓冲归因的关键证据）
// ---------------------------------------------------------------------------

/** 事件类型全集（R-11/R-12/R-13/R-14/R-16）。Room 中以 name 字符串存储。 */
enum class EnvEventType {
    THERMAL,      // 热状态迁移（SEVERE+ = 污染标，R-11）
    POWER_SAVE,   // 省电模式开/关（R-12）
    DOZE,         // Doze/DeviceIdle 变化（R-12）
    PATH_CHANGE,  // 默认网络漂移 / 绑定网络丢失 / VALIDATED 丢失（R-01/R-14）
    SUB_SWITCH,   // 双卡默认数据 subId 切换（R-13）
    APP_JANK,     // 10ms 哨兵线程检出进程级停顿 >30ms（R-16）
    CELL_CHANGE,  // PCI/TAC 变化（R-02 归因窗口的事件锚点）
    RAT_CHANGE,   // 制式三元组（network_type/override_type/nr_state）变化（R-15）
}

/**
 * 运行期事件模型（radio / net / engine 各监控源统一输出到该类型的 Flow）。
 * 全部计时用 SystemClock.elapsedRealtimeNanos（与 KPI 事件共用单调时间轴）。
 */
data class EnvEvent(
    val tsNanos: Long,
    val type: EnvEventType,
    val detail: String,
) {
    fun toEntity(runId: String?) = EnvEventEntity(
        runId = runId,
        tsNanos = tsNanos,
        type = type.name,
        detail = detail,
    )
}

@Entity(
    tableName = "env_event",
    indices = [Index("runId"), Index("tsNanos")],
)
data class EnvEventEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    /** 可空：事件可能发生在 run 建立前（如测前守卫阶段），落库时未绑定 run */
    val runId: String?,
    /** elapsedRealtimeNanos 单调时间轴 */
    val tsNanos: Long,
    /** EnvEventType.name */
    val type: String,
    val detail: String,
)

// ---------------------------------------------------------------------------
// 无线层 1Hz 采样（设计文档 §7 RadioSample；R-02/R-13/R-15 升级字段）
// ---------------------------------------------------------------------------

@Entity(
    tableName = "radio_sample",
    indices = [Index("runId"), Index("tsNanos")],
)
data class RadioSampleEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val runId: String?,
    /** 采样打点时刻（elapsedRealtimeNanos，回调到达轴） */
    val tsNanos: Long,
    /** CellInfo 信息生成时刻（getTimestampNanos/Millis 换算，同 elapsedRealtime 轴）；无小区记 null（R-02） */
    val cellTsNanos: Long?,
    /** requestCellInfoUpdate 超时退回缓存，或 modem 时戳距采样 >2s（R-02） */
    val stale: Boolean,
    /** 当前默认数据卡 subId（R-13）；权限缺失/无效记 -1 */
    val subId: Int,
    /** 本秒内发生过 defaultDataSubId 切换（R-13） */
    val subSwitched: Boolean,
    // ---- R-15 制式三元组：显示态与协商态分列，禁止合并为单值 ----
    /** TelephonyManager.dataNetworkType 名称（承载协商态） */
    val networkType: String,
    /** TelephonyDisplayInfo override 名称（运营商图标显示策略；API<31 记 unavailable_below_api31） */
    val overrideType: String?,
    /** ServiceState nrState（反射/toString 兜底；失败静默降级记 nsa_unknown） */
    val nrState: String,
    // ---- registered cell 快照（LTE 或 NR；无小区全 null，禁 0/哨兵值 R-10） ----
    /** "LTE" / "NR"；无 LTE/NR registered cell 记 null */
    val rat: String?,
    val pci: Int?,
    val tac: Int?,
    /** LTE=EARFCN / NR=NRARFCN */
    val arfcn: Int?,
    /** LTE=RSRP / NR=SS-RSRP (dBm) */
    val rsrp: Int?,
    /** LTE=RSRQ / NR=SS-RSRQ (dB) */
    val rsrq: Int?,
    /** LTE=RSSNR / NR=SS-SINR (dB) */
    val sinr: Int?,
    val operatorName: String?,
    // ---- GPS 路测打点（阶段3 路测模式，v9 additive 列；隐私边界见设计文档 §9.1） ----
    // 仅路测开关开启且 GPS 有 fix 时非 null：权限缺失/定位未开启/无 fix/失锁一律 null
    // （R-10 语义）。坐标只入本地 Room 与本地轨迹导出，**绝不进 /results 上报体**
    // （ResultReporter 无坐标字段，单测锚定）。
    val lat: Double? = null,
    val lon: Double? = null,
    /** fix 水平精度（米）；无精度信息 null */
    val accuracyM: Double? = null,
)

// ---------------------------------------------------------------------------
// Profile 3 无障碍观察快照落库（观察=端到端体验代理≠网络口径；恒 LOW/INCONCLUSIVE）
// ---------------------------------------------------------------------------

/**
 * 无障碍观察会话快照落库行（v14 新增表，additive；镜像 D-42/D-45 观测口径持久化）。
 *
 * - **观察口径，独立结论**：无障碍打点=端到端体验代理（含 App 渲染，≈帧级上界），
 *   ≠网络口径、≠ Profile 2 服务端仿真口径，绝不并入 AQS 任何分 / 不进 /results 上报；
 *   [confidence] 恒记 LOW/INCONCLUSIVE（真实适配器规格 PENDING-VALIDATION 撤销前口径红线）。
 * - **只落规格匹配会话**（[specId] != null）：generic 通用观察不落库（避免系统 App 噪声）；
 *   落库触发在会话切换且该会话有实质观察（events≥阈值）时，见 AnebAccessibilityService。
 * - 指标字段全部可空：无事件/不足样本记 null，禁 0/哨兵值（R-10：Snapshot 的 null 原样落库）。
 * - 展示直接读落库值不重算（D-02）；本行**不含任何文本内容**（观察模式只计时/计数红线不变）。
 */
@Entity(tableName = "adapter_obs")
data class AdapterObsEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    /** 落库时刻（epoch ms） */
    val tsEpochMs: Long,
    /** 被观察前台包名（如 com.larus.nova / com.deepseek.chat） */
    val pkg: String,
    /** 匹配到的适配器规格 id（doubao/deepseek）；null=通用观察（本表只落 specId!=null 行） */
    val specId: String?,
    /** 友好显示名（[appLabelFor] 由 specId 映射；未知规格→null，展示层缺退 pkg） */
    val appLabel: String?,
    /** 会话内观察事件总数 */
    val events: Long,
    /** 命中规格节点规则的事件数（PENDING-VALIDATION 期间仅标注计数，非闸门） */
    val ruleMatchedEvents: Long,
    /** 观察启动→首内容变化，ms；无事件=null（R-10）。端到端 TTFT 代理，非网络口径 */
    val firstDeltaMs: Long?,
    /** 变化间隔 p50，ms；不足一个间隔=null（R-10）。流式节奏代理，非 ITL 宣称 */
    val cadenceP50Ms: Double?,
    /** TTFT 簇代理（首簇起→次簇起），ms；不足两簇=null（R-10） */
    val ttftClusterMs: Double?,
    /** 发送锚定 TTFT 代理，ms；无锚点/未闭合=null（R-10；send-anchor=input-clear 启发式） */
    val ttftSendMs: Double?,
    /** 最近完成锚点来源（click/input_clear）；null=尚无完成锚点 */
    val anchorSource: String?,
    /** 观察置信标注，恒 LOW/INCONCLUSIVE（口径红线） */
    val confidence: String,
    /**
     * 前台观察会话跨度 ui-proxy，ms（spine-3 C6，session_duration_s_dist 观测源）；无事件=null（R-10）。
     * ≠真实对话会话时长（受前台切换/节流界定），恒 ui-proxy/LOW；跨会话分布见 [com.aneb.probe.adapter.SessionDurationStats]。
     */
    val sessionSpanMs: Double? = null,
) {
    companion object {
        /** 规格 id → 友好显示名（spec_adapters 目录各适配器 display_name 镜像）；未知 id → null（UI 缺退 pkg）。 */
        private val LABEL_BY_SPEC_ID: Map<String, String> = mapOf(
            "doubao" to "豆包",
            "deepseek" to "DeepSeek",
            "tongyi" to "通义千问",
            "kimi" to "Kimi",
        )

        /** 规格 id 映射友好名；null/未知规格 → null（generic 不落库，此处防御性缺退到 pkg）。 */
        fun appLabelFor(specId: String?): String? = specId?.let { LABEL_BY_SPEC_ID[it] }
    }
}
