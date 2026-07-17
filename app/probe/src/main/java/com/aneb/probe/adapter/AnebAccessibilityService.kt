package com.aneb.probe.adapter

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Context
import android.content.Intent
import android.os.SystemClock
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityManager

/**
 * Profile 3 真实 App 适配器宿主——无障碍**观察模式 only** 打点服务。
 *
 * ## 红线：观察模式 only（用户账号红线）
 * 本服务**绝不调用 performAction / performGlobalAction / dispatchGesture**、绝不注入任何
 * 点击/输入/滚动操作、绝不代启动目标 App——动真实账号是用户红线。配置层同步钉死：
 * `res/xml/accessibility_service_config.xml` 未声明 canPerformGestures，事件类型仅订阅
 * 观察所需三种。本服务也**不读取、不存储任何文本内容**——文本仅经预编译正则做命中判定后即弃。
 *
 * ## 口径红线（与 spec/adapters/ 数据文件 caliber_redlines 字段双声明）
 * - 无障碍打点=**端到端体验代理**（含 App 渲染，≈帧级精度上界 16–33ms），**≠网络口径**；
 *   与 Profile 2 服务端仿真口径严格分标，数值不可互比；
 * - **观察模式不构成测量宣称**：真实适配器规格 PENDING-VALIDATION 撤销前，所有输出恒标
 *   LOW/INCONCLUSIVE（[AdapterObsSnapshot.CONFIDENCE]）；
 * - **R-10**：无事件 → first_delta/cadence 记 null，绝不折 0。
 *
 * ## 工作方式
 * - 订阅 TYPE_WINDOW_CONTENT_CHANGED / TYPE_VIEW_TEXT_CHANGED / TYPE_WINDOW_STATE_CHANGED；
 * - 按当前前台包名匹配 [AdapterSpecLoader] 加载的规格：匹配到 → 规格模式（事件同时按
 *   response_node 的 className/text 正则做**标注计数**——PENDING-VALIDATION 期间非闸门）；
 *   未匹配任何规格 → **通用观察（generic mode）**：对任意前台包记录事件时戳流（机制验证路径）；
 * - 会话=前台包切换分段；时钟=SystemClock.elapsedRealtimeNanos 单调钟（与 KPI 事件同轴）；
 * - 每包统计 firstDeltaMs（观察启动→首内容变化）+ 变化间隔序列（最近 256 个环形）；
 * - 输出：每 5s 或会话切换时打 KEY 日志
 *   `ADAPTER_OBS pkg=... events=N first_delta_ms=... cadence_p50_ms=...`，并发布
 *   @Volatile 只读快照 [latestSnapshot] 供 UI 读（D-02：展示层不重算）。
 *
 * ## 服务开销纪律（R-16 同精神：工具不能自己成为干扰源）
 * - 回调热路径仅：单调钟打戳 + [ObsSessionStats.onEvent] 环形写 + 预编译正则单串匹配；
 *   p50 等聚合只在 5s 节流 / 会话切换时算；
 * - **绝不取 event.source**（AccessibilityNodeInfo 跨进程 IPC，开销大且可能扰动目标 App）——
 *   故 view_id_regex 规则在观察最小开销路径不评估，留待真机验证轮按需启用（spec 中保留字段）；
 * - 忽略自身包事件（本 App 的 UI 轮询快照会触发内容变化事件，形成观察反馈环）。
 */
class AnebAccessibilityService : AccessibilityService() {

    /** 规格运行时索引：正则在服务连接时一次预编译（回调内零编译，R-16）。 */
    private class SpecRuntime(val spec: AdapterSpec) {
        val classNameRegex: Regex? = spec.responseNode.classNameRegex?.toRegexSafe()
        val textRegex: Regex? = spec.responseNode.textRegex?.toRegexSafe()

        /** 廉价标注判定：只用事件自带 className/首条 text，不取节点。 */
        fun ruleMatch(event: AccessibilityEvent): Boolean {
            classNameRegex?.let { r ->
                val cn = event.className ?: return@let
                if (r.containsMatchIn(cn)) return true
            }
            textRegex?.let { r ->
                val first = event.text.firstOrNull() ?: return@let
                if (r.containsMatchIn(first)) return true
            }
            return false
        }
    }

    private var specsByPackage: Map<String, SpecRuntime> = emptyMap()
    private var session: ObsSessionStats? = null
    private var lastEmitNanos = 0L

    override fun onServiceConnected() {
        super.onServiceConnected()
        val specs = AdapterSpecLoader.loadFromAssets(this)
        specsByPackage = specs.associate { it.packageName to SpecRuntime(it) }
        session = null
        lastEmitNanos = 0L
        running = true
        Log.i(
            TAG,
            "ADAPTER_HOST_CONNECTED specs=${specs.size}" +
                " ids=${specs.joinToString(",") { "${it.id}:${it.packageName}" }}" +
                " mode=observe-only",
        )
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        val e = event ?: return
        val now = SystemClock.elapsedRealtimeNanos()
        val pkg = e.packageName?.toString() ?: return
        if (pkg == packageName) return // 自观察反馈环屏蔽（R-16）

        when (e.eventType) {
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> {
                switchSessionIfNeeded(pkg, now)
            }
            AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED,
            AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED,
            -> {
                val s = switchSessionIfNeeded(pkg, now)
                val rt = specsByPackage[pkg]
                s.onEvent(now, ruleMatched = rt != null && rt.ruleMatch(e))
            }
            else -> return
        }

        if (now - lastEmitNanos >= EMIT_INTERVAL_NANOS) emit(now, reason = "throttle")
    }

    override fun onInterrupt() {
        // 观察模式无待撤销的进行中动作；会话统计保留，下一事件继续。
    }

    override fun onUnbind(intent: Intent?): Boolean {
        session?.let { latestSnapshot = it.snapshot(SystemClock.elapsedRealtimeNanos()) }
        running = false
        Log.i(TAG, "ADAPTER_HOST_UNBOUND")
        return super.onUnbind(intent)
    }

    /** 前台包切换 → 结算旧会话（emit 终帧）并开新会话；同包返回现会话。 */
    private fun switchSessionIfNeeded(pkg: String, nowNanos: Long): ObsSessionStats {
        val cur = session
        if (cur != null && cur.pkg == pkg) return cur
        if (cur != null) emit(nowNanos, reason = "session_switch")
        val specId = specsByPackage[pkg]?.spec?.id
        val next = ObsSessionStats(pkg = pkg, specId = specId, observeStartNanos = nowNanos)
        session = next
        return next
    }

    /** 节流聚合出口：快照发布（@Volatile）+ KEY 日志。null 打 "null"（R-10 不折 0）。 */
    private fun emit(nowNanos: Long, reason: String) {
        lastEmitNanos = nowNanos
        val snap = session?.snapshot(nowNanos) ?: return
        latestSnapshot = snap
        Log.i(
            TAG,
            "ADAPTER_OBS pkg=${snap.pkg}" +
                " mode=${snap.specId ?: "generic"}" +
                " events=${snap.events}" +
                " rule_matched=${snap.ruleMatchedEvents}" +
                " first_delta_ms=${snap.firstDeltaMs ?: "null"}" +
                " cadence_p50_ms=${snap.cadenceP50Ms?.let { "%.1f".format(it) } ?: "null"}" +
                " confidence=${snap.confidence}" +
                " reason=$reason",
        )
    }

    companion object {
        private const val TAG = "AnebProbe"

        /** 统计输出节流间隔（5s；会话切换额外立即输出）。 */
        private const val EMIT_INTERVAL_NANOS = 5_000_000_000L

        /** 服务是否已连接（诊断用；权威启用态请用 [isEnabled] 查系统）。 */
        @Volatile
        var running: Boolean = false
            private set

        /** 最近观察快照（不可变，@Volatile 单次发布；UI 只读，D-02 不重算）。 */
        @Volatile
        var latestSnapshot: AdapterObsSnapshot? = null
            private set

        /** 系统无障碍设置中本服务是否已启用（AccessibilityManager 权威查询）。 */
        fun isEnabled(context: Context): Boolean {
            val am = context.getSystemService(Context.ACCESSIBILITY_SERVICE)
                as? AccessibilityManager ?: return false
            return am.getEnabledAccessibilityServiceList(AccessibilityServiceInfo.FEEDBACK_ALL_MASK)
                .any { info ->
                    val si = info.resolveInfo?.serviceInfo
                    si?.packageName == context.packageName &&
                        si.name == AnebAccessibilityService::class.java.name
                }
        }

        /** 正则编译失败（规格数据损坏）→ null 降级为不启用该维度，不崩（fail-safe）。 */
        private fun String.toRegexSafe(): Regex? = try {
            Regex(this)
        } catch (e: Exception) {
            Log.i(TAG, "ADAPTER_SPEC_FALLBACK bad_regex=${take(60)} err=${e.javaClass.simpleName}")
            null
        }
    }
}
