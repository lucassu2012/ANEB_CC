package com.aneb.probe.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * Room 骨架（阶段 0 只建表，不强制全接线）。
 * 时延字段全部可空 Long?：失败/超时记 null，禁 0/哨兵值（R-10 失败样本语义）。
 * TODO(阶段1)：补 ScenarioResult / RadioSample / EchoSample / EnvEvent 表与三态有效性字段全集。
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
