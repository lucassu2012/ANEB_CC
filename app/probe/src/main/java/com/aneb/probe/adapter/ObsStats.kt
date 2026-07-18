package com.aneb.probe.adapter

import kotlin.math.ceil

/**
 * 无障碍观察打点统计——**纯 JVM**（零 Android 依赖，单测直接实例化）。
 *
 * ## 职责切分（R-16 同精神：回调内仅时戳+环形写）
 * [onEvent] 是无障碍回调热路径：只做首事件打戳 + 间隔环形写 + 计数自增，O(1) 零分配；
 * p50 排序等聚合只在 [snapshot]（宿主 5s 节流 / 会话切换时）调用。
 *
 * ## 口径（详见 spec/adapters/ 与 [AnebAccessibilityService] KDoc 双声明）
 * - firstDeltaMs ≈ 端到端 TTFT 代理（观察会话启动→首次内容变化），含 App 渲染，非网络口径；
 * - cadenceP50Ms ≈ 流式节奏代理（变化间隔 p50，最近 [RING_CAPACITY] 个间隔环形窗口）；
 * - ttftSendMs ≈ **发送锚定 TTFT 代理**：send_anchor（输入框文本非空→空）→ 其后首个
 *   非输入框内容变化事件。**send-anchor=input-clear 启发式**——观察口径无法区分"发送清空"
 *   与"用户手动清空"，可能包含手动清空误检；如实声明，恒 LOW/INCONCLUSIVE；
 * - R-10：无事件 → firstDeltaMs=null；不足一个间隔 → cadenceP50Ms=null；
 *   无发送锚点/锚点未闭合 → ttftSendMs=null，绝不折 0。
 *
 * 线程模型：单写者（无障碍回调线程）调用 [onEvent]/[snapshot]；跨线程只经
 * [AdapterObsSnapshot]（不可变，@Volatile 发布）传递，本类自身不做同步。
 */
class ObsSessionStats(
    val pkg: String,
    /** 匹配到的适配器规格 id；null = 通用观察（generic mode，机制验证路径）。 */
    val specId: String?,
    /** 会话观察起点（SystemClock.elapsedRealtimeNanos 单调钟）。 */
    val observeStartNanos: Long,
) {
    companion object {
        /** 保留最近多少个变化间隔（环形覆盖，任务书钉死 256）。 */
        const val RING_CAPACITY = 256

        /** 发送锚定 TTFT 历史保留条数（环形覆盖，任务书钉死 8）。 */
        const val SEND_HISTORY_CAPACITY = 8

        /** 锚点来源标注：发送按钮点击（send-anchor v2，[onSendAnchor]）。 */
        const val SOURCE_CLICK = "click"

        /** 锚点来源标注：输入框清空启发式（send-anchor v1，[onInputBoxText]）。 */
        const val SOURCE_INPUT_CLEAR = "input_clear"

        /**
         * 簇分割静默阈值（send-anchor v3）：内容事件间隔 > 此值即分簇。取值依据（真机实证，
         * D-52）：豆包发送后「用户气泡上屏」簇内间隔 ~8ms、流式响应簇内 ~100ms，两簇之间的
         * 模型思考静默 >500ms——400ms 界稳分两簇且不误分流式簇。
         */
        const val CLUSTER_GAP_NANOS: Long = 400_000_000L

        private const val NONE = Long.MIN_VALUE
    }

    private var firstEventNanos = NONE
    private var lastEventNanos = NONE
    private var eventCount = 0L
    private var ruleMatchedCount = 0L
    private val ring = LongArray(RING_CAPACITY)
    private var ringSize = 0
    private var ringNext = 0

    // ── 发送锚定 TTFT 状态机（send-anchor=input-clear 启发式，见类 KDoc 口径段）──
    /** 上一次输入框文本是否非空（非空→空转变=锚点武装条件）。 */
    private var lastInputNonEmpty = false

    /** 当前未闭合锚点时戳；NONE=无锚点。重新武装即覆盖（=取消上一个未闭合锚点）。 */
    private var sendAnchorNanos = NONE

    /** 最近一次**完成**的发送锚定 TTFT（纳秒）；NONE=尚无完成值（R-10 → null）。 */
    private var lastTtftSendNanos = NONE

    /** 当前未闭合锚点来源（[SOURCE_CLICK]|[SOURCE_INPUT_CLEAR]）；null=无未闭合锚点。 */
    private var pendingAnchorSource: String? = null

    /** 最近一次**完成**锚点的来源（与 [lastTtftSendNanos] 配对，快照 anchorSource 暴露）；null=尚无完成值。 */
    private var completedAnchorSource: String? = null

    private val sendRing = LongArray(SEND_HISTORY_CAPACITY)
    private var sendRingSize = 0
    private var sendRingNext = 0

    // ── 簇分割 TTFT（send-anchor v3）状态：会话内内容事件流的首/次簇起点 ──
    private var firstClusterStartNanos = NONE
    private var secondClusterStartNanos = NONE
    private var lastContentDeltaNanos = NONE

    /**
     * 热路径：记一次内容变化事件。仅打戳/环形写/计数，O(1) 零分配。
     * @param ruleMatched 事件是否命中规格节点规则（PENDING-VALIDATION 期间仅标注计数，
     *   不作闸门——不命中也全量入时戳流）。
     */
    fun onEvent(nowNanos: Long, ruleMatched: Boolean = false) {
        eventCount++
        if (ruleMatched) ruleMatchedCount++
        if (firstEventNanos == NONE) {
            firstEventNanos = nowNanos
        } else {
            ring[ringNext] = nowNanos - lastEventNanos
            ringNext = (ringNext + 1) % RING_CAPACITY
            if (ringSize < RING_CAPACITY) ringSize++
        }
        lastEventNanos = nowNanos
    }

    /**
     * 热路径：输入框文本变化（宿主按事件 className 匹配 input_node.class_name_regex 分流）。
     * 文本从非空→空 = **send_anchor 武装**（对话类 App 发送后输入框即清空的启发式；
     * 用户手动清空同样武装——观察口径无法区分，如实声明，恒 LOW/INCONCLUSIVE）。
     * 重复武装覆盖（=取消）上一个未闭合锚点。O(1) 零分配；只收文本**长度**不收内容
     * （不读取、不存储任何文本内容的红线不变）。
     */
    fun onInputBoxText(textLen: Int, tsNanos: Long) {
        if (lastInputNonEmpty && textLen == 0) {
            // click 优先（谁先武装算谁）：已有未闭合 click 锚点时 input-clear 不覆盖；否则武装/覆盖
            // 旧未闭合 input-clear 锚点（v1 覆盖语义不变——现有锚点非 click 时行为零变）。
            if (!(sendAnchorNanos != NONE && pendingAnchorSource == SOURCE_CLICK)) {
                sendAnchorNanos = tsNanos // 非空→空：武装
                pendingAnchorSource = SOURCE_INPUT_CLEAR
            }
        }
        lastInputNonEmpty = textLen > 0
        // v3.1：输入框活动重置簇状态——簇观察窗从最近输入活动之后起算，把「App 打开渲染簇」
        // 排除在外（真机实证 D-52：不重置时首簇=打开渲染，ttft_cluster_ms=7184ms 语义混杂；
        // 重置后=发送→用户气泡簇→思考静默→响应簇，语义纯净）。
        // v3.2：仅**有内容**的输入活动（textLen>0，真实打字）重置——len=0 的输入轨事件
        // （DeepSeek Compose 无 text 载荷的 TEXT_CHANGED 走通配规则进输入轨）不得在响应期
        // 反复误重置簇窗，否则 Compose 栈 ttft_cluster 永不闭合。
        if (textLen > 0) {
            firstClusterStartNanos = NONE
            secondClusterStartNanos = NONE
            lastContentDeltaNanos = NONE
        }
    }

    /**
     * 热路径：**发送按钮点击**锚点（send-anchor v2；宿主按 send_button 规则用事件自带字段
     * className/text/contentDescription 命中后调用，绝不取 event.source）。武装并**覆盖任何
     * 旧未闭合锚点**（含 input-clear 锚点）；其后 click 锚点不被 input-clear 覆盖——click 优先于
     * input-clear（谁先武装算谁：正常序列点击先于输入框清空）。O(1) 零分配；不读节点/文本（红线不变）。
     */
    fun onSendAnchor(tsNanos: Long) {
        sendAnchorNanos = tsNanos
        pendingAnchorSource = SOURCE_CLICK
    }

    /**
     * 热路径：非输入框内容变化——闭合最近未闭合锚点得一次发送锚定 TTFT，
     * 写入最近值 + 历史环形（≤[SEND_HISTORY_CAPACITY]）。无锚点则无操作。O(1) 零分配。
     */
    fun onContentDelta(tsNanos: Long) {
        // ── 簇分割（send-anchor v3）：会话内内容事件按 >CLUSTER_GAP_NANOS 静默分簇。
        // 发送场景下首簇≈用户气泡上屏（紧跟发送点击）、次簇首事件≈响应首增量——
        // 首簇起→次簇起=ttft_cluster_ms（TTFT 簇代理）。只捕获会话内第一对簇（单次发送
        // 观察场景）；非发送场景（滚动等）该值无发送语义——观察口径，恒 LOW/INCONCLUSIVE。
        if (firstClusterStartNanos == NONE) {
            firstClusterStartNanos = tsNanos
        } else if (secondClusterStartNanos == NONE &&
            lastContentDeltaNanos != NONE &&
            tsNanos - lastContentDeltaNanos > CLUSTER_GAP_NANOS
        ) {
            secondClusterStartNanos = tsNanos
        }
        lastContentDeltaNanos = tsNanos

        val anchor = sendAnchorNanos
        if (anchor == NONE) return
        val delta = tsNanos - anchor
        lastTtftSendNanos = delta
        completedAnchorSource = pendingAnchorSource // 与 lastTtftSendNanos 配对（诊断用）
        sendRing[sendRingNext] = delta
        sendRingNext = (sendRingNext + 1) % SEND_HISTORY_CAPACITY
        if (sendRingSize < SEND_HISTORY_CAPACITY) sendRingSize++
        sendAnchorNanos = NONE
        pendingAnchorSource = null
    }

    /** 聚合出不可变快照（仅节流/会话切换时调用；含排序，不进热路径）。 */
    fun snapshot(nowNanos: Long): AdapterObsSnapshot = AdapterObsSnapshot(
        pkg = pkg,
        specId = specId,
        events = eventCount,
        ruleMatchedEvents = ruleMatchedCount,
        firstDeltaMs = if (firstEventNanos == NONE) {
            null // R-10：无事件=未测，绝不折 0
        } else {
            (firstEventNanos - observeStartNanos) / 1_000_000
        },
        cadenceP50Ms = cadenceP50Ms(),
        sessionStartNanos = observeStartNanos,
        updatedAtNanos = nowNanos,
        ttftSendMs = if (lastTtftSendNanos == NONE) {
            null // R-10：无发送锚点/锚点未闭合=未测，绝不折 0
        } else {
            lastTtftSendNanos / 1_000_000.0
        },
        ttftSendHistory = ttftSendHistory(),
        anchorSource = completedAnchorSource,
        ttftClusterMs = if (firstClusterStartNanos == NONE || secondClusterStartNanos == NONE) {
            null // R-10：不足两簇=未测，绝不折 0
        } else {
            (secondClusterStartNanos - firstClusterStartNanos) / 1_000_000.0
        },
    )

    /** 历史环形 → 时间升序列表（仅快照时调用，不进热路径）。 */
    private fun ttftSendHistory(): List<Double> {
        if (sendRingSize == 0) return emptyList()
        val start = if (sendRingSize < SEND_HISTORY_CAPACITY) 0 else sendRingNext
        return List(sendRingSize) { i ->
            sendRing[(start + i) % SEND_HISTORY_CAPACITY] / 1_000_000.0
        }
    }

    /**
     * 最近秩 p50（nearest-rank，rank=ceil(p×n)——与 KpiCalculator.percentileOrNull 同约定）。
     * 环形数组 [0, ringSize) 恰为有效区（覆盖写原地进行），排序副本不动原环。
     * 无间隔 → null（R-10）。
     */
    private fun cadenceP50Ms(): Double? {
        if (ringSize == 0) return null
        val sorted = ring.copyOf(ringSize).apply { sort() }
        val rank = ceil(0.5 * ringSize).toInt().coerceIn(1, ringSize)
        return sorted[rank - 1] / 1_000_000.0
    }
}

/**
 * 观察快照——不可变 data class，宿主经 @Volatile 单次发布，UI 只读（D-02：展示层不重算）。
 * 观察模式不构成测量宣称：[confidence] 恒为 LOW/INCONCLUSIVE
 * （真实适配器规格 PENDING-VALIDATION 撤销前的口径红线）。
 */
data class AdapterObsSnapshot(
    val pkg: String,
    /** 匹配规格 id；null = generic mode（通用观察）。 */
    val specId: String?,
    val events: Long,
    /** 命中规格节点规则的事件数（PENDING-VALIDATION 期间仅标注，非闸门）。 */
    val ruleMatchedEvents: Long,
    /** 观察启动→首内容变化，ms；无事件=null（R-10）。端到端 TTFT 代理，非网络口径。 */
    val firstDeltaMs: Long?,
    /** 变化间隔 p50，ms；不足一个间隔=null（R-10）。流式节奏代理，非 ITL 宣称。 */
    val cadenceP50Ms: Double?,
    val sessionStartNanos: Long,
    val updatedAtNanos: Long,
    /**
     * 发送锚定 TTFT 代理，ms：send_anchor（输入框非空→空）→ 其后首个非输入框内容变化；
     * 取最近一次**完成**值。**send-anchor=input-clear 启发式**——可能包含用户手动清空误检
     * （观察口径无法区分），恒 LOW/INCONCLUSIVE；无锚点/未闭合=null（R-10）。
     */
    val ttftSendMs: Double? = null,
    /** 历次完成的发送锚定 TTFT（最近 [ObsSessionStats.SEND_HISTORY_CAPACITY]=8 个环形，时间升序）。 */
    val ttftSendHistory: List<Double> = emptyList(),
    /**
     * 最近一次**完成**的发送锚定来源标注（与 [ttftSendMs] 配对，便于真机诊断哪套启发式在生效）：
     * [ObsSessionStats.SOURCE_CLICK]（点击锚点 v2）| [ObsSessionStats.SOURCE_INPUT_CLEAR]（输入清空 v1）|
     * null（尚无完成锚点，与 ttftSendMs=null 同步）。
     */
    val anchorSource: String? = null,
    /**
     * **TTFT 簇代理**（send-anchor v3），ms：会话内内容事件按 >[ObsSessionStats.CLUSTER_GAP_NANOS]
     * 静默分簇，首簇起（发送场景≈用户气泡上屏）→次簇起（≈响应首增量）。不依赖任何锚点事件
     * （豆包发送按钮不派发 CLICKED、输入清空不发 TEXT_CHANGED——两代锚点均失效后的纯时戳结构法，
     * D-52 真机实证簇结构）。只取会话内第一对簇；非发送场景无发送语义；不足两簇=null（R-10）；
     * 恒 LOW/INCONCLUSIVE。
     */
    val ttftClusterMs: Double? = null,
) {
    val confidence: String get() = CONFIDENCE

    companion object {
        /** 观察模式恒定置信标注（口径红线）。 */
        const val CONFIDENCE = "LOW/INCONCLUSIVE"
    }
}
