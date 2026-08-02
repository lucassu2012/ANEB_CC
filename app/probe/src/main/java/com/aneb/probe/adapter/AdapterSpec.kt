package com.aneb.probe.adapter

import android.content.Context
import android.util.Log
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * Profile 3 真实 App 适配器规格——数据驱动加载器（铁律 1「适配器规格=数据文件，不是代码分支」）。
 *
 * ## 单一事实源与镜像（与 [com.aneb.probe.ui.TestModeProfileLoader] 同模式）
 * - 权威副本：仓库 `spec/adapters/` 下各 `.json`（先改 spec、后动代码）；
 * - 运行时镜像：`assets/spec_adapters/` 下各 `.json`（AdapterSpecTest 守护两份字节级一致）。
 *
 * ## 格式决定：JSON（非 YAML）
 * 与 client_profiles 一致性优先——kotlinx.serialization 严格模式（未知键即失败）原生支持 JSON、
 * 加载链完全同模式；YAML 需引入第三方解析依赖且无同等严格模式保证。
 *
 * ## fail-safe（测量工具不能因数据文件损坏而崩）
 * [loadFromAssets] 任何异常（缺目录/坏 JSON/schema 不符）→ 返回空列表并打
 * KEY=ADAPTER_SPEC_FALLBACK 日志；宿主 [AnebAccessibilityService] 无规格时自动降级为
 * 通用观察（generic mode），机制验证路径不受影响。
 *
 * ## 口径红线（与 spec 文件 caliber_redlines 字段双声明）
 * - 无障碍打点=**端到端体验代理**（含 App 渲染，≈帧级精度上界 16–33ms），**≠网络口径**；
 *   与 Profile 2 服务端仿真口径严格分标，数值不可互比；
 * - 规格 `status: PENDING-VALIDATION` 撤销前，其驱动的一切输出恒标 **LOW/INCONCLUSIVE**，
 *   观察模式不构成测量宣称；
 * - R-10：无事件 → first_delta/cadence 记 null，绝不折 0。
 */
object AdapterSpecLoader {

    /** assets 内运行时镜像目录。 */
    const val ASSET_DIR = "spec_adapters"

    /** 当前支持的数据文件 schema 版本（不符即抛→fail-safe，改结构必升版本）。 */
    const val SCHEMA_VERSION = "1.0.0"

    /** PENDING-VALIDATION 状态字面量（规格生命周期闸门，见 spec/adapters/README.md）。 */
    const val STATUS_PENDING = "PENDING-VALIDATION"

    private val json = Json // 默认严格：未知键/类型不符即抛 → 触发 fail-safe 空列表

    /**
     * 纯 JVM 解析单个规格文件（不触 Android API，单测直接复用）。
     * schema 版本不符 / id 或 package 为空 / observe_events 为空 /
     * kpi_mapping 缺 first_delta 或 delta_cadence 即抛。
     */
    fun parse(text: String): AdapterSpec {
        val file = json.decodeFromString<AdapterSpecFileDto>(text)
        require(file.schemaVersion == SCHEMA_VERSION) {
            "unsupported schema_version=${file.schemaVersion} (expect $SCHEMA_VERSION)"
        }
        val a = file.adapter
        require(a.id.isNotBlank()) { "adapter.id blank" }
        require(a.packageName.isNotBlank()) { "adapter.package blank" }
        require(a.observeEvents.isNotEmpty()) { "observe_events empty" }
        require("first_delta" in a.kpiMapping && "delta_cadence" in a.kpiMapping) {
            "kpi_mapping must contain first_delta and delta_cadence"
        }
        return a.toModel()
    }

    /**
     * 运行时从 assets 加载全部规格；任何异常 → 空列表（宿主降级 generic mode），打 KEY 日志。
     * 单文件损坏也整体回空——规格集半残比全无更危险（半残会让部分 App 静默走错口径标注）。
     */
    fun loadFromAssets(context: Context): List<AdapterSpec> = try {
        val names = context.assets.list(ASSET_DIR)
            ?.filter { it.endsWith(".json") }
            ?.sorted()
            .orEmpty()
        names.map { name ->
            context.assets.open("$ASSET_DIR/$name").use { input ->
                parse(input.readBytes().toString(Charsets.UTF_8))
            }
        }
    } catch (e: Exception) {
        Log.i(
            "AnebProbe",
            "ADAPTER_SPEC_FALLBACK error=${e.javaClass.simpleName} msg=${e.message?.take(120)}",
        )
        emptyList()
    }

    // ────────────────────────────────────────────────────────────────────────
    //  可序列化 DTO——与 spec/adapters/ 数据文件逐字段 1:1（严格模式防 schema 漂移静默生效）
    // ────────────────────────────────────────────────────────────────────────

    @Serializable
    data class AdapterSpecFileDto(
        @SerialName("schema_version") val schemaVersion: String,
        val adapter: AdapterDto,
    )

    /**
     * 规格核对时的 App 版本戳（D-387 / T11 裁定 6-4）。
     *
     * **必须声明在本文件内**，不是风格偏好而是硬约束：`spec/adapters/validate_adapters.py`
     * 用正则从 **`AdapterSpec.kt` 这一个文件**派生允许键/必填键/类型（其 L55 硬编码路径、
     * L65 抓 `@SerialName`）。T14 用一个 ghost 键做过对照实验——**把本 DTO 挪到别的文件，
     * 门印 `OK: all adapter-spec invariants hold`、零违规；挪回同文件，四份 JSON 逐一被点名**。
     * 也就是说放在别处时，这一整段**一个键都不会被检查**。
     *
     * 四个序列名照 T14 报告 §2.2 定案，**不要另起**（改掉会触发 `R21b`/`R21c`/`R21d`，
     * 而设备侧照样接受该文件——又一个「门说没问题、其实没查」的形状）。
     */
    @Serializable
    data class VersionStampDto(
        /** 核对时的 `versionName`，如 `"1.2.3"`。 */
        @SerialName("version_name") val versionName: String,
        /** 核对时的 `versionCode`（`dumpsys package <pkg>` 只读取得，不改设备）。 */
        @SerialName("version_code") val versionCode: Long,
        /**
         * 核对日期，**`YYYY-MM-DD`**，如 `"2026-01-01"`。
         *
         * 不是 ISO-8601 带时刻——门 `R21d` 只认日期形态（`validate_adapters.py`）。
         * 初稿这里写的是 `"2026-01-01T00:00:00Z"`，被 R21d 当场咬住；
         * **KDoc 与门不一致时，以门为准**，因为门是唯一会拦住错误数据的那一侧。
         */
        @SerialName("captured_at") val capturedAt: String,
        /**
         * 版本号怎么来的，如 `"dumpsys package"`——写下来才好判断它可不可信（门 `R21e`）。
         */
        @SerialName("source") val source: String,
    )

    @Serializable
    data class AdapterDto(
        val id: String,
        @SerialName("display_name") val displayName: String,
        @SerialName("app_id") val appId: String,
        @SerialName("package") val packageName: String,
        @SerialName("package_note") val packageNote: String = "",
        val status: String,
        @SerialName("launch_hint") val launchHint: String = "",
        @SerialName("input_node") val inputNode: NodeRuleDto,
        @SerialName("response_node") val responseNode: NodeRuleDto,
        @SerialName("send_button") val sendButton: SendButtonRuleDto,
        @SerialName("observe_events") val observeEvents: List<String>,
        @SerialName("kpi_mapping") val kpiMapping: Map<String, KpiProxyDto>,
        @SerialName("caliber_redlines") val caliberRedlines: CaliberDto,
        /**
         * 该规格最后一次**在真机上核对过**的 App 版本（D-387 / T11 裁定 6-4）。
         *
         * `= null` 默认：**规格没核对过是合法状态**，不是错误——四份数据文件里没有这一段时
         * 照常解析。缺席的语义是「不知道对哪个版本验过」，而不是「对任何版本都成立」；
         * 消费侧据此把该规格标 `STALE`，**绝不静默当作最新**（R-10：不可计算 ≠ 零）。
         */
        @SerialName("validated_against_version") val validatedAgainstVersion: VersionStampDto? = null,
    ) {
        fun toModel() = AdapterSpec(
            id = id,
            displayName = displayName,
            appId = appId,
            packageName = packageName,
            packageNote = packageNote,
            status = status,
            launchHint = launchHint,
            inputNode = inputNode.toModel(),
            responseNode = responseNode.toModel(),
            sendButton = sendButton.toModel(),
            observeEvents = observeEvents,
            kpiMapping = kpiMapping.mapValues { (_, v) -> KpiProxy(v.proxyFor, v.caliber) },
            caliber = CaliberRedlines(
                claimScope = caliberRedlines.claimScope,
                confidenceCeiling = caliberRedlines.confidenceCeiling,
                r10 = caliberRedlines.r10,
            ),
            validatedAgainstVersion = validatedAgainstVersion?.let {
                VersionStamp(
                    versionName = it.versionName,
                    versionCode = it.versionCode,
                    capturedAt = it.capturedAt,
                    source = it.source,
                )
            },
        )
    }

    @Serializable
    data class NodeRuleDto(
        @SerialName("view_id_regex") val viewIdRegex: String? = null,
        @SerialName("class_name_regex") val classNameRegex: String? = null,
        @SerialName("text_regex") val textRegex: String? = null,
        val status: String = STATUS_PENDING,
        val note: String = "",
    ) {
        fun toModel() = NodeRule(viewIdRegex, classNameRegex, textRegex, status, note)
    }

    /**
     * 发送按钮匹配规则 DTO（send-anchor v2 点击锚点；D-51 v1 input-clear 启发式失效后的方向）。
     * 四正则维度均可空（缺=不启用该维度）；[contentDescRegex] 为按钮无障碍描述（如「发送」），
     * 是 View/Compose 两栈发送按钮常见可匹配特征。CLICKED 事件仅用**事件自带**字段
     * （className/text/contentDescription）匹配，绝不取 event.source（R-16，跨进程 IPC）——
     * 故 [viewIdRegex] 运行时不评估，仅留存备真机诊断回填参考（同 response_node.view_id_regex）。
     */
    @Serializable
    data class SendButtonRuleDto(
        @SerialName("view_id_regex") val viewIdRegex: String? = null,
        @SerialName("class_name_regex") val classNameRegex: String? = null,
        @SerialName("text_regex") val textRegex: String? = null,
        @SerialName("content_desc_regex") val contentDescRegex: String? = null,
        val status: String = STATUS_PENDING,
        val note: String = "",
    ) {
        fun toModel() =
            SendButtonRule(viewIdRegex, classNameRegex, textRegex, contentDescRegex, status, note)
    }

    @Serializable
    data class KpiProxyDto(
        @SerialName("proxy_for") val proxyFor: String,
        val caliber: String,
    )

    @Serializable
    data class CaliberDto(
        @SerialName("claim_scope") val claimScope: String,
        @SerialName("confidence_ceiling") val confidenceCeiling: String,
        val r10: String,
    )
}

// ────────────────────────────────────────────────────────────────────────────
//  域模型（纯数据，UI/宿主只读消费；D-02：不在展示层重算任何口径）
// ────────────────────────────────────────────────────────────────────────────

/** 单个 App 的适配器规格（易耗品：App 改版即改数据文件，不改代码）。 */
data class AdapterSpec(
    val id: String,
    val displayName: String,
    val appId: String,
    val packageName: String,
    val packageNote: String,
    val status: String,
    val launchHint: String,
    val inputNode: NodeRule,
    val responseNode: NodeRule,
    val sendButton: SendButtonRule,
    val observeEvents: List<String>,
    val kpiMapping: Map<String, KpiProxy>,
    val caliber: CaliberRedlines,
    /**
     * 最后一次在真机上核对该规格时的 App 版本；**null = 从未核对过**（D-387 / 裁定 6-4）。
     * 缺席是合法状态，语义是「不知道对哪个版本验过」——**不是**「对任何版本都成立」。
     */
    val validatedAgainstVersion: VersionStamp? = null,
) {
    /** 真机验证前恒 true——驱动的一切输出恒标 LOW/INCONCLUSIVE。 */
    val pendingValidation: Boolean get() = status == AdapterSpecLoader.STATUS_PENDING

    /**
     * 规格是否**可能**已过期：宿主 App 现装版本与核对版本对不上，或压根没核对过。
     *
     * 三态刻意不折叠成布尔：`null`（没核对过）与「核对过但版本变了」是两回事——
     * 前者是**没有证据**，后者是**有证据表明它变了**，把两者当同一件事上报，
     * 读者就分不清「不知道」和「知道不对」（R-10）。
     */
    fun stalenessAgainst(installedVersionCode: Long?): Staleness = when {
        validatedAgainstVersion == null -> Staleness.NEVER_VALIDATED
        installedVersionCode == null -> Staleness.INSTALLED_VERSION_UNKNOWN
        installedVersionCode != validatedAgainstVersion.versionCode -> Staleness.STALE
        else -> Staleness.CURRENT
    }

    enum class Staleness { CURRENT, STALE, NEVER_VALIDATED, INSTALLED_VERSION_UNKNOWN }
}

/** 规格核对时的 App 版本戳（D-387 / 裁定 6-4）。 */
data class VersionStamp(
    val versionName: String,
    val versionCode: Long,
    val capturedAt: String,
    val source: String,
)

/**
 * 发送按钮匹配规则（send-anchor v2 点击锚点）。四正则维度均可空=不启用该维度；
 * 全空 → 宿主 sendButtonMatch 恒不命中（R-10 诚实缺席：无数据不猜测、不武装）。
 * [contentDescRegex]=按钮无障碍描述（如「发送」/「Send」）；[viewIdRegex] 需
 * AccessibilityNodeInfo（getSource 跨进程），观察最小开销路径不评估（R-16），仅留存备诊断回填。
 */
data class SendButtonRule(
    val viewIdRegex: String?,
    val classNameRegex: String?,
    val textRegex: String?,
    val contentDescRegex: String?,
    val status: String,
    val note: String,
)

/**
 * 节点匹配规则（viewId/className/text 正则，均可空=不启用该维度）。
 * PENDING-VALIDATION 期间仅作标注计数、不作打点闸门（规则错误不得静默丢事件）；
 * view_id_regex 需 AccessibilityNodeInfo（getSource 跨进程取节点，开销大）——观察最小
 * 开销路径（R-16）不取节点，留待真机验证轮按需启用。
 */
data class NodeRule(
    val viewIdRegex: String?,
    val classNameRegex: String?,
    val textRegex: String?,
    val status: String,
    val note: String,
)

/** KPI 代理映射条目（proxy_for=代理什么，caliber=口径声明——非网络口径，严格分标）。 */
data class KpiProxy(val proxyFor: String, val caliber: String)

/** 口径红线三联（spec 文件与 KDoc 双声明中的数据侧）。 */
data class CaliberRedlines(val claimScope: String, val confidenceCeiling: String, val r10: String)
