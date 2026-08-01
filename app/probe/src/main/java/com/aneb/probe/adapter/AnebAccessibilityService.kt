package com.aneb.probe.adapter

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Context
import android.content.Intent
import android.os.SystemClock
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityManager
import com.aneb.probe.BuildConfig
import com.aneb.probe.data.AdapterObsEntity
import com.aneb.probe.data.AnebDatabase
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch

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
 * - **发送锚定 TTFT（ttft_send_ms）**：TEXT_CHANGED 事件按自带 className 匹配规格
 *   input_node.class_name_regex 分流（generic mode 兜底 EditText 正则）——输入框文本
 *   非空→空即武装 send_anchor，其后首个非输入框内容变化闭合为一次锚定 TTFT。
 *   **send-anchor=input-clear 启发式**：可能包含用户手动清空误检（观察口径无法区分），
 *   恒 LOW/INCONCLUSIVE；无锚点/未闭合=null（R-10）；
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

        /** 输入框判定正则（input_node.class_name_regex；坏正则/缺维度→null，宿主用兜底）。 */
        val inputClassNameRegex: Regex? = spec.inputNode.classNameRegex?.toRegexSafe()

        // ── send-anchor v2：发送按钮点击匹配正则（send_button；仅事件自带字段，view_id 不评估）──
        val sendBtnClassRegex: Regex? = spec.sendButton.classNameRegex?.toRegexSafe()
        val sendBtnTextRegex: Regex? = spec.sendButton.textRegex?.toRegexSafe()
        val sendBtnDescRegex: Regex? = spec.sendButton.contentDescRegex?.toRegexSafe()

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

        /**
         * 发送按钮点击判定（send-anchor v2）：**仅用 CLICKED 事件自带字段**
         * （className / 首条 text / contentDescription），绝不取 event.source（R-16）。
         * 语义=**已配置维度全部命中**（AND）——精确优先，避免泛按钮点击误武装 TTFT 测量；
         * **无任何可评估维度（三正则全空）→ 恒不命中**（R-10 诚实缺席：无数据不猜测、不武装）。
         * view_id_regex 需 getSource，观察最小开销路径不评估（留存备诊断回填）。
         */
        fun sendButtonMatch(event: AccessibilityEvent): Boolean {
            var anyDimension = false
            sendBtnClassRegex?.let { r ->
                anyDimension = true
                val cn = event.className ?: return false
                if (!r.containsMatchIn(cn)) return false
            }
            sendBtnTextRegex?.let { r ->
                anyDimension = true
                val first = event.text.firstOrNull() ?: return false
                if (!r.containsMatchIn(first)) return false
            }
            sendBtnDescRegex?.let { r ->
                anyDimension = true
                val desc = event.contentDescription ?: return false
                if (!r.containsMatchIn(desc)) return false
            }
            return anyDimension
        }
    }

    private var specsByPackage: Map<String, SpecRuntime> = emptyMap()
    private var session: ObsSessionStats? = null
    private var lastEmitNanos = 0L

    /** 默认输入法包名（onServiceConnected 时读 default_input_method）；其事件全豁免。 */
    @Volatile
    private var imePkg: String? = null

    // ── 观察快照落库（R-16：回调热路径仅 trySend，DB 写在 IO 消费协程；onDestroy 取消）──
    /** 落库协程作用域（SupervisorJob 隔离单次失败；onDestroy 取消）。 */
    private val persistScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    /** 轻量落库队列：热路径 trySend 快照行，消费协程串行 DB 写；满则丢最旧（不阻塞回调）。 */
    private val obsPersistChannel = Channel<AdapterObsEntity>(
        capacity = OBS_PERSIST_CAPACITY,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )

    override fun onCreate() {
        super.onCreate()
        startObsPersistConsumer()
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        val specs = AdapterSpecLoader.loadFromAssets(this)
        specsByPackage = specs.associate { it.packageName to SpecRuntime(it) }
        // IME 包全事件豁免：键盘候选栏/布局的 CONTENT/TEXT 事件不属于被观察业务，
        // 且会在打字期间把目标 App 会话切段、清掉 send-anchor 状态机
        // （真机实证：百度输入法把 com.larus.nova 观察切成两段，ttft_send_ms 恒 null）。
        imePkg = runCatching {
            android.provider.Settings.Secure.getString(contentResolver, "default_input_method")
                ?.substringBefore('/')
        }.getOrNull()
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
        if (pkg == imePkg) return // IME 事件全豁免（键盘事件≠被观察业务；防打字期会话切段）
        // systemui 豁免：状态栏时钟/通知的零星 CONTENT 事件会切断目标 App 观察会话
        // （真机实证：systemui 单事件把豆包会话切成两段，破坏 v3 簇结构与锚点状态）。
        if (pkg == "com.android.systemui") return

        when (e.eventType) {
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> {
                // 不切会话：IME（输入法键盘弹收）与瞬态窗口的 STATE 事件会在打点关键期
                // （发送锚点武装后）误切会话、清掉状态机——真机实证：百度输入法窗口把
                // com.larus.nova 观察切成 8/1/8 三段，ttft_send_ms 恒 null。会话只由
                // CONTENT/TEXT 事件驱动开启/切换；真实切 App 后新前台必然很快有内容事件。
            }
            AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED,
            AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED,
            -> {
                val s = switchSessionIfNeeded(pkg, now)
                val rt = specsByPackage[pkg]
                s.onEvent(now, ruleMatched = rt != null && rt.ruleMatch(e))
                // 发送锚定分流：TEXT_CHANGED 且 className 命中输入框规则 → 输入框文本轨
                // （send-anchor=input-clear 启发式）；其余（含 CONTENT_CHANGED）→ 内容变化轨。
                if (e.eventType == AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED &&
                    isInputBoxEvent(e, rt)
                ) {
                    s.onInputBoxText(textLenOf(e), now)
                } else {
                    s.onContentDelta(now)
                }
                // E1 通道 A 的逐事件时戳（T7 记的「ADAPTER_EVT 不带任何时间戳」）。
                // 传 `now`——即本次 onAccessibilityEvent 入口算的那个 elapsedRealtimeNanos，
                // 不在这里再取一次：再取会得到一个**晚于**会话状态机所用的时刻，
                // 两条时间线就此错开，而错开多少没人量得出来。
                logAdapterEvent(e, pkg, "content", now)
            }
            AccessibilityEvent.TYPE_VIEW_CLICKED -> {
                // send-anchor v2 点击锚点：先事件级诊断打点（DEBUG 门控，供真机反推发送按钮特征），
                // 再按 send_button 规则用**事件自带**字段匹配（绝不 getSource）；命中→武装 send_anchor。
                // 无规格 / 规格 send_button 全空 / 不匹配 → 不武装（R-10 诚实缺席），诊断日志仍已打。
                logAdapterEvent(e, pkg, "click", now)
                val rt = specsByPackage[pkg]
                if (rt != null && rt.sendButtonMatch(e)) {
                    switchSessionIfNeeded(pkg, now).onSendAnchor(now)
                }
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

    override fun onDestroy() {
        obsPersistChannel.close()
        persistScope.cancel()
        super.onDestroy()
    }

    /** 启动落库消费协程（onCreate 一次；串行消费 channel 做 DB 写，与回调热路径解耦）。 */
    private fun startObsPersistConsumer() {
        persistScope.launch {
            val dao = AnebDatabase.get(applicationContext).adapterObsDao()
            for (row in obsPersistChannel) {
                runCatching { dao.insert(row) }
                    .onSuccess { id ->
                        Log.i(TAG, "ADAPTER_OBS_SAVED id=$id app=${row.appLabel ?: row.pkg}")
                    }
                    .onFailure { e ->
                        Log.i(TAG, "ADAPTER_OBS_SAVE_FAIL err=${e.javaClass.simpleName}")
                    }
            }
        }
    }

    /**
     * 观察快照落库入队（R-16：回调热路径仅本方法——构造不可变行 + [Channel.trySend]，无 IO/无阻塞；
     * DB 写在 [persistScope] 的 IO 消费协程）。只落**规格匹配**（specId!=null）且**有实质观察**
     * （events≥[PERSIST_MIN_EVENTS]）的会话快照——generic 通用观察 / 碎快照不落库（避免系统 App
     * 噪声与海量碎行）；channel 满时 DROP_OLDEST（丢最旧不阻塞回调）。tsEpochMs 于此刻取墙钟。
     */
    private fun enqueuePersist(snap: AdapterObsSnapshot?) {
        val specId = snap?.specId ?: return // generic（specId=null）不落库
        if (snap.events < PERSIST_MIN_EVENTS) return
        obsPersistChannel.trySend(
            AdapterObsEntity(
                tsEpochMs = System.currentTimeMillis(),
                pkg = snap.pkg,
                specId = specId,
                appLabel = AdapterObsEntity.appLabelFor(specId),
                events = snap.events,
                ruleMatchedEvents = snap.ruleMatchedEvents,
                firstDeltaMs = snap.firstDeltaMs,
                cadenceP50Ms = snap.cadenceP50Ms,
                // 端到端 TTFT 代理择优（D-55）：v3 簇分割优先、v4 密度谱兜底——二者口径同轴
                // （发送→响应首字，含渲染，UI 呈现口径，恒 LOW/INCONCLUSIVE），互补覆盖不同 UI 栈：
                // 豆包(View 系,思考期静止)→cluster 有值;DeepSeek(Compose,思考期动画)→cluster=null、
                // density 有值。历史页 TTFT 展示此择优列，两栈 App 均可回溯。
                ttftClusterMs = snap.ttftClusterMs ?: snap.ttftDensityMs,
                ttftSendMs = snap.ttftSendMs,
                anchorSource = snap.anchorSource,
                confidence = snap.confidence,
                sessionSpanMs = snap.sessionSpanMs, // spine-3 C6：会话时长 ui-proxy 落库
            ),
        )
    }

    /**
     * 输入框事件判定：仅用事件自带 className（绝不取 event.source，R-16）匹配当前规格
     * input_node.class_name_regex；无规格（generic mode）或规格缺该维度/坏正则 → 兜底
     * EditText 正则（数据缺失不瘫机制）。className 缺失 → 判非输入框。
     */
    private fun isInputBoxEvent(event: AccessibilityEvent, rt: SpecRuntime?): Boolean {
        val cn = event.className ?: return false
        val regex = rt?.inputClassNameRegex ?: GENERIC_INPUT_CLASS_REGEX
        return regex.containsMatchIn(cn)
    }

    /** event.text 合计长度（零分配循环；只计长不读内容——文本红线不变）。 */
    private fun textLenOf(event: AccessibilityEvent): Int {
        var len = 0
        val texts = event.text
        for (i in texts.indices) len += texts[i]?.length ?: 0
        return len
    }

    /**
     * 事件级诊断日志（send-anchor v2 关键交付；[BuildConfig.DEBUG] 门控，release 无输出）。
     * 每个 CLICKED 事件打一行，供主会话真机反推豆包/DeepSeek 发送按钮的 className/contentDesc
     * 特征后回填 spec send_button。**仅事件自带字段**：className + contentDescription（按钮无障碍
     * 标签，如「发送」，截断防刷屏）+ 文本**长度** txt_len（不含内容——文本红线不变）+ pkg；
     * 绝不取 event.source（R-16）。CONTENT/TEXT 事件量大不逐条打，仅 CLICKED。
     */
    private fun logAdapterEvent(
        event: AccessibilityEvent,
        pkg: String,
        type: String,
        tBootNs: Long,
    ) {
        if (!BuildConfig.DEBUG) return
        val cls = event.className ?: "null"
        val desc = event.contentDescription?.let(::truncateForLog) ?: "null"
        // Log.i 而非 Log.d：华为 EMUI 默认丢弃 D 级日志（真机实证 ADAPTER_EVT 恒不可见）；
        // BuildConfig.DEBUG 门控已保证 release 无输出，I 级仅影响 debug 构建可见性。
        //
        // `t_boot_ns` 与 `type=content` 都不是我起的名字——它们是**消费方早已写好的契约**：
        // `tools/e1/e1_analyze.py` 的 `parse_adapter_events()` **只收带 `t_boot_ns=` 的行**
        // （没有该字段的行被如实忽略，其 docstring 写着「忽略比『用行到达顺序编个时戳』安全」），
        // 而该文件第 40 行逐字给出了期望格式：
        //   `ADAPTER_EVT type=content cls=<cls> txt_len=<n> pkg=<pkg> t_boot_ns=<ns>`。
        // 若这里另起一个名字（如 obs_ns），字段就没有读者，通道 A 依旧 NOT_EXECUTED——
        // 那正是 D-276 反复记的那个反面教材：**要一个没人读的字段**。
        //
        // 既有字段一个不动（additive）；`type` 由调用方给，click 保持原值。
        Log.i(
            TAG,
            "ADAPTER_EVT type=$type cls=$cls desc=$desc" +
                " txt_len=${textLenOf(event)} pkg=$pkg t_boot_ns=$tBootNs",
        )
    }

    /** 诊断日志文本截断（防长文本刷屏；仅用于事件自带 contentDescription，非用户内容）。 */
    private fun truncateForLog(cs: CharSequence): String {
        val s = cs.toString()
        return if (s.length <= EVT_LOG_DESC_MAX) s else s.take(EVT_LOG_DESC_MAX) + "…"
    }

    /** 前台包切换 → 结算旧会话（emit 终帧）并开新会话；同包返回现会话。 */
    private fun switchSessionIfNeeded(pkg: String, nowNanos: Long): ObsSessionStats {
        val cur = session
        if (cur != null && cur.pkg == pkg) return cur
        // 会话切换：结算旧会话终帧（emit 打日志+发布快照）并把快照入落库队列（规格匹配+实质
        // 观察才落，见 enqueuePersist；R-16：此处仅 trySend，DB 写在 IO 消费协程）。
        if (cur != null) enqueuePersist(emit(nowNanos, reason = "session_switch"))
        val specId = specsByPackage[pkg]?.spec?.id
        val next = ObsSessionStats(pkg = pkg, specId = specId, observeStartNanos = nowNanos)
        session = next
        return next
    }

    /**
     * 节流聚合出口：快照发布（@Volatile）+ KEY 日志。null 打 "null"（R-10 不折 0）。
     * 返回本次快照（供会话切换落库入队复用，避免二次 snapshot 排序开销）；无会话返回 null。
     */
    private fun emit(nowNanos: Long, reason: String): AdapterObsSnapshot? {
        lastEmitNanos = nowNanos
        val snap = session?.snapshot(nowNanos) ?: return null
        latestSnapshot = snap
        Log.i(
            TAG,
            "ADAPTER_OBS pkg=${snap.pkg}" +
                " mode=${snap.specId ?: "generic"}" +
                " events=${snap.events}" +
                " rule_matched=${snap.ruleMatchedEvents}" +
                " first_delta_ms=${snap.firstDeltaMs ?: "null"}" +
                " cadence_p50_ms=${snap.cadenceP50Ms?.let { "%.1f".format(it) } ?: "null"}" +
                " session_span_ms=${snap.sessionSpanMs?.let { "%.1f".format(it) } ?: "null"}" +
                " confidence=${snap.confidence}" +
                " reason=$reason" +
                " ttft_send_ms=${snap.ttftSendMs?.let { "%.1f".format(it) } ?: "null"}" +
                " anchor_source=${snap.anchorSource ?: "null"}" +
                " ttft_cluster_ms=${snap.ttftClusterMs?.let { "%.1f".format(it) } ?: "null"}" +
                " ttft_density_ms=${snap.ttftDensityMs?.let { "%.1f".format(it) } ?: "null"}",
        )
        return snap
    }

    companion object {
        private const val TAG = "AnebProbe"

        /** 统计输出节流间隔（5s；会话切换额外立即输出）。 */
        private const val EMIT_INTERVAL_NANOS = 5_000_000_000L

        /** 落库触发最小事件数（会话切换时该会话 events≥此值才落库，避免海量碎快照）。 */
        private const val PERSIST_MIN_EVENTS = 5L

        /** 落库队列容量（满则 DROP_OLDEST；观察快照低频，32 足够缓冲突发切换）。 */
        private const val OBS_PERSIST_CAPACITY = 32

        /** 事件级诊断日志 contentDescription 截断上限（防长文本刷屏，R-16；DEBUG only）。 */
        private const val EVT_LOG_DESC_MAX = 40

        /**
         * 输入框判定兜底正则（generic mode / 规格缺 input_node.class_name_regex 时用；
         * 数据缺失不瘫发送锚定机制）。一次编译（R-16）。
         */
        private val GENERIC_INPUT_CLASS_REGEX = Regex("android\\.widget\\.EditText")

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
