package com.aneb.probe.ui

import android.content.Context
import android.util.Log
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * 客户端 Profile 数据加载器——铁律 1「Profile 即数据，不是代码分支」的客户端落地。
 *
 * ## 单一事实源与镜像
 * - 权威副本：仓库 `spec/profiles/client/client_profiles.json`（先改 spec、后动代码）；
 * - 运行时镜像：`assets/spec_profiles/client_profiles.json`（[ClientProfileDataParityTest]
 *   守护两份文件字节级一致 + 与代码内 FALLBACK 逐字段对拍防漂移）。
 *
 * ## fail-safe（测量工具不能因数据文件损坏而崩）
 * [loadFromAssets] 任何异常（缺文件/坏 JSON/schema 不符）→ 返回 null 并打
 * KEY=SPEC_PROFILE_FALLBACK 日志，[TestModeProfiles] 回退代码内硬编码兜底数据。
 * [Json] 用严格模式（未知键即失败），防 schema 漂移静默生效。
 */
object TestModeProfileLoader {

    /** assets 内运行时镜像路径。 */
    const val ASSET_PATH = "spec_profiles/client_profiles.json"

    /** 当前支持的数据文件 schema 版本（不符即回退，改结构必升版本）。 */
    const val SCHEMA_VERSION = "1.0.0"

    private val json = Json // 默认严格：未知键/类型不符即抛 → 触发 fail-safe 回退

    /**
     * 纯 JVM 解析（不触 Android API，单测经相对路径读文件后直接复用）。
     * schema 版本不符或 profiles 为空即抛。
     */
    fun parse(text: String): List<TestModeProfile> {
        val file = json.decodeFromString<ClientProfilesFileDto>(text)
        require(file.schemaVersion == SCHEMA_VERSION) {
            "unsupported schema_version=${file.schemaVersion} (expect $SCHEMA_VERSION)"
        }
        require(file.profiles.isNotEmpty()) { "profiles empty" }
        return file.profiles.map { it.toModel() }
    }

    /** 运行时从 assets 加载；任何异常 → null（调用方回退 FALLBACK），打 KEY 日志。 */
    fun loadFromAssets(context: Context): List<TestModeProfile>? = try {
        val text = context.assets.open(ASSET_PATH).use { input ->
            input.readBytes().toString(Charsets.UTF_8)
        }
        parse(text)
    } catch (e: Exception) {
        Log.i(
            "AnebProbe",
            "SPEC_PROFILE_FALLBACK error=${e.javaClass.simpleName} msg=${e.message?.take(120)}",
        )
        null
    }

    // ────────────────────────────────────────────────────────────────────────
    //  可序列化 DTO——与 TestModeProfile 域模型逐字段 1:1；枚举直接复用域类型
    //  （kotlinx 内建按名称序列化），默认值与域模型一致（缺省字段行为不漂移）。
    // ────────────────────────────────────────────────────────────────────────

    @Serializable
    data class ClientProfilesFileDto(
        @SerialName("schema_version") val schemaVersion: String,
        val profiles: List<ProfileDto>,
    )

    @Serializable
    data class ProfileDto(
        val id: String,
        val displayName: String,
        val tagline: String,
        val business: String,
        val metrics: List<ModeMetricDto>,
        val conclusion: String,
        val version: String = "",
        val businessType: BusinessTypeDto? = null,
        val metricSpecs: List<MetricSpecDto> = emptyList(),
        val live: List<LiveMetricDto> = emptyList(),
        val scoring: ScoringModelSpecDto? = null,
    ) {
        fun toModel() = TestModeProfile(
            id = id,
            displayName = displayName,
            tagline = tagline,
            business = business,
            metrics = metrics.map { ModeMetric(it.name, it.unit, it.dynamic) },
            conclusion = conclusion,
            version = version,
            businessType = businessType?.toModel(),
            metricSpecs = metricSpecs.map { it.toModel() },
            live = live.map { it.toModel() },
            scoring = scoring?.toModel(),
        )
    }

    @Serializable
    data class ModeMetricDto(val name: String, val unit: String, val dynamic: Boolean)

    @Serializable
    data class BusinessTypeDto(
        val summary: String,
        val subScenarios: List<SubScenarioDto> = emptyList(),
    ) {
        fun toModel() = BusinessType(summary, subScenarios.map { it.toModel() })
    }

    @Serializable
    data class SubScenarioDto(
        val code: String,
        val title: String,
        val uplink: String,
        val downlink: String,
        val behaviorHint: List<BehaviorTag> = emptyList(),
    ) {
        fun toModel() = SubScenario(code, title, uplink, downlink, behaviorHint)
    }

    @Serializable
    data class MetricSpecDto(
        val id: String,
        val name: String,
        val unit: String,
        val group: MetricGroup,
        val definition: String,
        val direction: Direction,
        val target: QualityTargetDto,
        val measurability: Measurability,
        val scored: Boolean,
        val anchorRef: String? = null,
    ) {
        fun toModel() = MetricSpec(
            id = id, name = name, unit = unit, group = group, definition = definition,
            direction = direction, target = target.toModel(), measurability = measurability,
            scored = scored, anchorRef = anchorRef,
        )
    }

    @Serializable
    data class QualityTargetDto(
        val excellent: Double? = null,
        val good: Double? = null,
        val fair: Double? = null,
        val poorFloor: Double? = null,
        val slaPercentile: Double = 0.95,
        val slaTargetLevel: Level = Level.GOOD,
        val perPayloadBand: Map<String, BandDto>? = null,
    ) {
        fun toModel() = QualityTarget(
            excellent = excellent, good = good, fair = fair, poorFloor = poorFloor,
            slaPercentile = slaPercentile, slaTargetLevel = slaTargetLevel,
            perPayloadBand = perPayloadBand?.mapValues { (_, b) -> Band(b.excellent, b.good, b.fair) },
        )
    }

    @Serializable
    data class BandDto(val excellent: Double, val good: Double, val fair: Double)

    @Serializable
    data class LiveMetricDto(
        val id: String,
        val label: String,
        val unit: String,
        val source: String,
        val render: LiveRender,
        val windowMs: Int,
        val refreshMs: Int,
    ) {
        fun toModel() = LiveMetric(id, label, unit, source, render, windowMs, refreshMs)
    }

    @Serializable
    data class ScoringModelSpecDto(
        val engine: String = "AqsScorer",
        val weightsTableId: String,
        val vetoRules: List<VetoRuleDto> = emptyList(),
        val renormalizeOnDesignDefault: Boolean = true,
        val gradeMapId: String = "aqsGrade",
        val behaviorRuleId: String = "",
        val recommendationTemplateId: String = "",
    ) {
        fun toModel() = ScoringModelSpec(
            engine = engine,
            weightsTableId = weightsTableId,
            vetoRules = vetoRules.map { VetoRule(it.kpiId, it.op, it.threshold, it.cap) },
            renormalizeOnDesignDefault = renormalizeOnDesignDefault,
            gradeMapId = gradeMapId,
            behaviorRuleId = behaviorRuleId,
            recommendationTemplateId = recommendationTemplateId,
        )
    }

    @Serializable
    data class VetoRuleDto(val kpiId: String, val op: String, val threshold: Double, val cap: Double)
}
