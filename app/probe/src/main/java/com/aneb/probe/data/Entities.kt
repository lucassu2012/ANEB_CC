package com.aneb.probe.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * Room 骨架（阶段 0 只建表，不强制全接线）。
 * 时延字段全部可空 Long?：失败/超时记 null，禁 0/哨兵值（R-10 失败样本语义）。
 * 阶段 1 本批新增：EnvEventEntity（环境事件时间轴）与 RadioSampleEntity（无线层 1Hz 采样）。
 * TODO(阶段1 后续)：补 ScenarioResult / EchoSample 表与三态有效性字段全集。
 */
@Entity(tableName = "test_run")
data class TestRun(
    @PrimaryKey val runId: String, // TODO(阶段1): UUIDv7
    val startedAtEpochMs: Long,
    val serverBase: String,
    val profileId: String?,
    val profileVersion: String?,
    /** valid / valid_low_confidence / invalid（三态 Gate，阶段 0 可为 null=未评估） */
    val validity: String?,
    val invalidReason: String?,
    // ---- 时延类字段一律可空（失败记 null）----
    val ttftNs: Long?,
    val itlMedianNs: Long?,
    val itlP95Ns: Long?,
    val stallCount: Int?,
    val seqGapCount: Int?,
    val clockOffsetUs: Long?,
    val clockOffsetErrUs: Long?,
    val uploadDurNs: Long?,
)

@Entity(
    tableName = "token_event",
    indices = [Index("runId"), Index(value = ["runId", "seq"])],
)
data class TokenEventEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val runId: String,
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
