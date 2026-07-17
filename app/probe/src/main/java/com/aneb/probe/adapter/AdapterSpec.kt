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
) {
    /** 真机验证前恒 true——驱动的一切输出恒标 LOW/INCONCLUSIVE。 */
    val pendingValidation: Boolean get() = status == AdapterSpecLoader.STATUS_PENDING
}

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
