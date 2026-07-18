package com.aneb.probe.ui

/**
 * facet3（[TestModeProfile.live]）动态指标选择与 **source 可解析闸门**（spine-4 §4.2）。
 *
 * 背景：facet3 号称"动态呈现关键指标单一事实源"，但渲染层各屏硬编码、`source` 字符串
 * 曾是悬空文档（basic_network 声明 `liveDownMbps`，而其数据面 SpeedRunner.Sample 字段
 * 实为 `downMbps`）。本对象补上"每个 live.source 必须解析到真实数据面字段"的机器闸门
 * （`Facet3SourceResolvableTest` 锚定），杜绝悬空 source 再混入 profile 数据。
 *
 * ## 解析规则（单一事实源）
 * 三模式三条**互不共享**的数据面（蓝图 §1.1），source 按 profile 归属面解析：
 *  - `token_experience` → [DataPlane.TELEMETRY]（engine.LiveTelemetry 字段）
 *  - `basic_network`    → [DataPlane.SPEED_SAMPLE]（engine.SpeedRunner.Sample 字段）
 *  - `voice_realtime`   → [DataPlane.VOICE_SAMPLE]（engine.VoiceRunner.Sample 字段）
 * `voice.` 前缀显式指定 VOICE_SAMPLE 面（仅 voice_realtime 可用，他模式解析为 null）。
 * 派生别名（如 `voice.frameJitterMs` = max(up/downFrameJitterMs)，M1 同款取法）在
 * [VOICE_DERIVED] 登记其成分字段，同受闸门校验。
 *
 * 字段全集手抄自各 data class——**防漂移由测试反射闭环**（Facet3SourceResolvableTest
 * 用 Java 反射断言全集 ⊆ 真实类字段；字段改名/删除即红），此处不引运行时反射。
 */
object DynamicMetricSelection {

    /** 三条独立数据面（蓝图 §1.1：互不共享 telemetry）。 */
    enum class DataPlane { TELEMETRY, SPEED_SAMPLE, VOICE_SAMPLE }

    /**
     * 解析结果：source 落到哪个面的哪个字段。
     * @param derivedFrom 非空=派生别名，列出真实成分字段（闸门校验成分而非别名本身）
     */
    data class FieldRef(
        val plane: DataPlane,
        val field: String,
        val derivedFrom: List<String> = emptyList(),
    )

    /** engine.LiveTelemetry 字段全集（token 面）。 */
    val TELEMETRY_FIELDS: Set<String> = setOf(
        "rttMs", "jitterMs", "rsrp", "sinr", "rat", "upMbps", "liveUpMbps",
        "ttftMs", "itlRecentMs", "itlMedianMs", "stallCount", "tokensReceived", "tokenRatePerSec",
        "phase", "subPhase", "fraction", "aqsRunning",
    )

    /** engine.SpeedRunner.Sample 字段全集（basic_network 面）。 */
    val SPEED_SAMPLE_FIELDS: Set<String> = setOf(
        "phase", "rttMs", "jitterMs", "upMbps", "downMbps", "progress",
        "reqFailed", "reqTotal", "shaped", "udpUnreturnedPct", "udpRttMs",
    )

    /** engine.VoiceRunner.Sample 字段全集（voice 面）。 */
    val VOICE_SAMPLE_FIELDS: Set<String> = setOf(
        "phase", "rttMs", "jitterMs", "upFrameJitterMs", "downFrameJitterMs", "mouthEarBudgetMs",
        "framesSent", "framesRecv", "progress", "ttfbP50Ms", "ttfbP95Ms", "downNetJitterMs",
        "mouthEarProxyMs", "turnSwitchP50Ms", "bargeStopMaxMs", "turnsOk", "caliber",
        "lowConfidence", "continuityDetectMs", "continuityResumeMs",
    )

    /** voice 面派生别名 → 真实成分字段（frameJitterMs = max(上/下行帧抖动)，M1 同款取法）。 */
    val VOICE_DERIVED: Map<String, List<String>> = mapOf(
        "frameJitterMs" to listOf("upFrameJitterMs", "downFrameJitterMs"),
    )

    /** profile id → 数据面归属；未知模式 null（新增模式必须先在此登记）。 */
    fun planeOf(profileId: String): DataPlane? = when (profileId) {
        "token_experience" -> DataPlane.TELEMETRY
        "basic_network" -> DataPlane.SPEED_SAMPLE
        "voice_realtime" -> DataPlane.VOICE_SAMPLE
        else -> null
    }

    /**
     * source 可解析闸门：解析到真实字段返回 [FieldRef]，否则 null（悬空——测试据此揪出）。
     * `voice.` 前缀仅 voice_realtime 面合法；派生别名按 [VOICE_DERIVED] 展开成分。
     */
    fun resolveSource(profileId: String, source: String): FieldRef? {
        val plane = planeOf(profileId) ?: return null
        return if (source.startsWith("voice.")) {
            if (plane != DataPlane.VOICE_SAMPLE) return null
            val name = source.removePrefix("voice.")
            when {
                name in VOICE_SAMPLE_FIELDS -> FieldRef(plane, name)
                name in VOICE_DERIVED -> FieldRef(plane, name, VOICE_DERIVED.getValue(name))
                else -> null
            }
        } else {
            val fields = when (plane) {
                DataPlane.TELEMETRY -> TELEMETRY_FIELDS
                DataPlane.SPEED_SAMPLE -> SPEED_SAMPLE_FIELDS
                DataPlane.VOICE_SAMPLE -> VOICE_SAMPLE_FIELDS
            }
            if (source in fields) FieldRef(plane, source) else null
        }
    }

    /** 该 profile 的动态指标集（facet3 投影；顺序即数据顺序）。 */
    fun dynamicMetrics(profile: TestModeProfile): List<LiveMetric> = profile.live
}
