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
)
