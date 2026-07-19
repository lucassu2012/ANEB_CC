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

        // ── 密度谱 TTFT（v4，事件密度谱——纯时戳统计，不依赖静默/锚点/节点）常量 ──
        // 选型=方案 A（密度基线偏离法）：把发送后内容事件流按步桶化为前缀直方图 → 组滑窗密度谱
        // → 取发送后前 K 窗中位数为基线 → 首个相对基线结构性跃变窗 = 响应起点候选。补 v3 簇分割在
        // 「思考期播放生成动画」栈（DeepSeek：持续 CONTENT、cadence~0.1ms 同帧合流、无 >400ms
        // 静默 → ttftClusterMs=null）的缺口（D-52/D-53）。

        /**
         * 密度谱步进/桶粒度：100ms。取值依据：D-52 真机豆包流式响应 token 到达 ~100ms/字，一桶
         * ≈一 token 间隔，足以把「思考稳态→响应」的密度跃变定位到 ~100ms 分辨率。
         */
        const val DENSITY_STEP_NANOS: Long = 100_000_000L

        /**
         * 密度谱滑动窗宽（以步进为单位）：2 步 = 200ms（任务书示例窗宽）。取值依据：200ms 窗跨
         * ~2 个响应 token 间隔，平滑单事件抖动而不糊掉跃变点。窗 w[i]=Σ bucket[i..i+此值-1]，相邻窗
         * 重叠一步（步进<窗宽）→ 跃变点 ~100ms 分辨率。
         */
        const val DENSITY_WINDOW_STEPS = 2

        /**
         * 密度谱桶数（前缀直方图，**非**环形覆盖）：128 桶 × 100ms = 12.8s 观察跨度。取值依据：
         * 覆盖推理类 App 现实「思考+首字」时长上限；超出即诚实 null（R-10 不猜），不无限扩内存
         * （128 int = 512B/会话）。
         */
        const val DENSITY_BUCKET_COUNT = 128

        /**
         * 密度谱基线窗数 K：取发送后前 5 个滑窗密度**中位数**为「发送后初始稳态」基线。取值依据：
         * 中位数对「气泡上屏」单窗突发鲁棒（气泡突发 ≤1 窗，5 窗中位数不受其抬高），5 窗又足够短，
         * 能在任何合理响应到达前锁定思考稳态。
         */
        const val DENSITY_BASELINE_WINDOWS = 5

        /**
         * 密度谱上跃倍率：某窗密度 ≥ 基线 ×2 判结构性上跃（静止思考→响应，豆包型：思考期 UI 静止
         * 无内容事件、基线≈0，响应流上屏 → 密度自 0 抬升）。取值依据：2× 是保守、无歧义的倍增，
         * 远超同帧合流抖动。
         */
        const val DENSITY_JUMP_UP_FACTOR = 2

        /**
         * 密度谱下跃倍率倒数：某窗密度 ≤ 基线 ×0.5（整数判据 密度×此值 ≤ 基线）判结构性下跃
         * （高频思考动画→低频响应 token，DeepSeek 型：动画 cadence~0.1ms 高密度 → 响应 ~100ms 低密度）。
         * 与上跃对称的减半判据。
         */
        const val DENSITY_JUMP_DOWN_FACTOR_INV = 2

        /**
         * 密度谱下跃最小基线：基线 <4 时不做下跃判定。取值依据：低计数下的「减半」是 ±1~2 事件噪声、
         * 非结构性；仅当思考动画基线足够高（≥4 事件/窗）时，减半到响应 token 才是可信信号（不为出数
         * 降低判据可信度——判据触发不了就诚实 null）。
         */
        const val DENSITY_MIN_BASELINE_FOR_DROP = 4

        /**
         * 密度谱静默基线下的响应起跃最小计数：基线=0（静止思考，豆包型思考期无内容事件）时，首个
         * 密度 ≥2 事件的窗判响应起点。取值依据：200ms 窗内 ≥2 事件区分真实流式起点与孤立杂事件。
         */
        const val DENSITY_MIN_JUMP_COUNT = 2

        /** 密度谱跃变 TTFT 来源标注（[AdapterObsSnapshot.densityAnchorSource]），检出跃变时取此值。 */
        const val SOURCE_DENSITY = "density"

        /**
         * TTFT 代理合理性上界（D-56）：30_000ms。任何 TTFT 代理（send/cluster/density）超此值即判
         * **结构不适配脏值** → null（不落脏值,R-10 诚实缺席优于错值）。取值依据：真实 AI 首字延迟
         * 含推理类深度思考现实上界约十余秒,30s 留足余量;超 30s 必是事件流结构错配（真机实证：Kimi
         * K2.6 复杂 Compose UI ttft_cluster=54558ms=54s 明显非首字,三方法均不适配该 App）。
         */
        const val TTFT_CEILING_MS = 30_000.0

        private const val NONE = Long.MIN_VALUE

        /** TTFT 代理合理性过滤：null 或 >[TTFT_CEILING_MS] → null（脏值抑制，D-56）。 */
        private fun sane(ttftMs: Double?): Double? =
            if (ttftMs == null || ttftMs > TTFT_CEILING_MS) null else ttftMs
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

    // ── 密度谱 TTFT（v4）状态：内容事件按 [DENSITY_STEP_NANOS] 步桶落桶（前缀直方图），窗格
    // 原点=簇首 [firstClusterStartNanos]（发送后首个内容事件，与 v3 簇首同一锚点，输入活动一并
    // 重置）。热路径仅一次除法+一次自增（R-16 O(1) 零分配）；滑窗聚合/基线偏离检测全在 [snapshot]。
    private val densityBucket = IntArray(DENSITY_BUCKET_COUNT)

    // ── 发送场景门控（D-56）：会话内曾有真实输入活动（textLen>0 打字）才认定「发送对话场景」，
    // TTFT 代理（cluster/density）方有发送语义。防非发送场景脏值——真机实证：generic 探路千问
    // （无规格,输入未匹配→簇窗未重置）ttft_cluster=16145ms、Kimi 纯滚动 ttft_density=500ms 均为
    // 「无发送却出 TTFT」的脏值,门控后诚实 null（R-10）。有规格发消息（input_node 匹配打字）正常置位。
    private var sawInputActivity = false

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
            // v4：密度谱窗格与簇首同源，输入活动一并清桶重置（下次内容事件重设窗格原点）。清桶
            // 在低频输入路径（非内容 delta 热路径），128 int fill 可忽略；R-16 热路径口径不变。
            // v3.2 守卫延伸至 v4：仅 textLen>0（真实打字）重置——响应期 len=0 的输入轨事件
            // （DeepSeek 无 text 载荷 TEXT_CHANGED）不清窗，否则密度谱永不闭合。
            densityBucket.fill(0)
            sawInputActivity = true // D-56：真实打字=发送对话场景，TTFT 代理由此获发送语义
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

        // ── 密度谱（v4）：以簇首 firstClusterStartNanos 为窗格原点落桶计数。上方簇块保证此刻
        // firstClusterStartNanos 已非 NONE（首事件即置位，落桶 idx=0）。O(1)：一次除法+一次自增，
        // 不依赖静默/锚点——DeepSeek 型思考期播放动画（持续 CONTENT、无 >400ms 静默、v3 簇分割
        // 失效）也照常入桶，把「思考稳态→响应」的密度结构性跃变留待 snapshot 检测。超出桶跨度
        // （>12.8s）的事件不落桶（对应 snapshot 侧诚实 null，不猜）。
        val densityAnchor = firstClusterStartNanos
        val bucketIdx = ((tsNanos - densityAnchor) / DENSITY_STEP_NANOS).toInt()
        if (bucketIdx in 0 until DENSITY_BUCKET_COUNT) densityBucket[bucketIdx]++

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
    fun snapshot(nowNanos: Long): AdapterObsSnapshot {
        // D-56 发送场景门控：无真实输入活动（非发送场景）→ TTFT 代理诚实 null，绝不出脏值。
        // 再过合理性上界 sane()：超 30s 的结构错配脏值（如 Kimi 54558ms）一并抑制为 null。
        val densityMs = sane(if (sawInputActivity) ttftDensityMs(nowNanos) else null)
        return AdapterObsSnapshot(
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
        sessionSpanMs = if (lastEventNanos == NONE) {
            null // R-10：无内容事件=无观察会话活动，绝不折 0
        } else {
            (lastEventNanos - observeStartNanos) / 1_000_000.0 // 前台观察会话跨度（ui-proxy）
        },
        ttftSendMs = if (lastTtftSendNanos == NONE) {
            null // R-10：无发送锚点/锚点未闭合=未测，绝不折 0
        } else {
            sane(lastTtftSendNanos / 1_000_000.0) // 合理性上界（D-56）
        },
        ttftSendHistory = ttftSendHistory(),
        anchorSource = completedAnchorSource,
        ttftClusterMs = if (!sawInputActivity || firstClusterStartNanos == NONE ||
            secondClusterStartNanos == NONE
        ) {
            null // R-10：非发送场景（D-56 门控）/不足两簇=未测，绝不折 0
        } else {
            sane((secondClusterStartNanos - firstClusterStartNanos) / 1_000_000.0) // 上界（D-56）
        },
        ttftDensityMs = densityMs, // v4 密度跃变 TTFT 代理（null=数据不足/无跃变，R-10）
        densityAnchorSource = if (densityMs == null) null else SOURCE_DENSITY,
        )
    }

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

    /**
     * 密度谱（v4）TTFT 代理：把发送后内容事件流按 [DENSITY_STEP_NANOS] 桶化为前缀直方图，组成
     * [DENSITY_WINDOW_STEPS] 步宽的滑窗密度谱，取发送后前 [DENSITY_BASELINE_WINDOWS] 窗密度中位数
     * 为「发送后初始稳态」基线，返回**首个相对基线结构性跃变窗**距簇首的偏移（ms）。
     *
     * 选型=**方案 A（密度基线偏离法，任务书推荐）**：纯整数运算、无浮点累积，比 CUSUM 变点检测更
     * 简单稳健。检出双向——上跃（≥基线×[DENSITY_JUMP_UP_FACTOR]，静止思考→响应；基线=0 时改用绝对
     * 下限 [DENSITY_MIN_JUMP_COUNT]）与下跃（≤基线×0.5，高频思考动画→低频响应 token，仅当基线
     * ≥[DENSITY_MIN_BASELINE_FOR_DROP] 才判，避免低计数噪声）。锚点=簇首 [firstClusterStartNanos]
     * （发送后首内容事件，与 v3 同锚），不依赖静默/发送锚点/节点——纯时戳密度统计。
     *
     * **诚实边界**：启发式，密度跃变≠精确首字；发送场景外无发送语义；恒 LOW/INCONCLUSIVE；完整
     * 滑窗数 <[DENSITY_BASELINE_WINDOWS]+1（数据不足）或全程无跃变（纯稳态）→ null（R-10 绝不折 0，
     * 不为出数降低判据可信度）。仅 [snapshot] 调用（含桶求和/排序，不进热路径）。
     */
    private fun ttftDensityMs(nowNanos: Long): Double? {
        val anchor = firstClusterStartNanos
        if (anchor == NONE) return null // 无内容事件=未测（R-10）
        val elapsed = nowNanos - anchor
        if (elapsed < 0) return null
        // 已完整流逝的步桶数（桶 k 覆盖 [k,k+1)×step，其末端 ≤ elapsed 才算完整、密度可信；末个
        // 未满桶不计入 → 快照落在窗中途不会把半个窗读成假下跃）。
        val completeSteps = minOf(DENSITY_BUCKET_COUNT, (elapsed / DENSITY_STEP_NANOS).toInt())
        // 滑窗 w[i]=Σ bucket[i..i+WINDOW_STEPS-1]，需连续 WINDOW_STEPS 个完整桶
        val windowCount = completeSteps - DENSITY_WINDOW_STEPS + 1
        if (windowCount < DENSITY_BASELINE_WINDOWS + 1) return null // 数据不足=未测（R-10）
        // 基线=前 K 窗密度中位数（nearest-rank p50，与 [cadenceP50Ms] 同约定；中位数抗气泡突发单窗）
        val baseWins = IntArray(DENSITY_BASELINE_WINDOWS) { windowDensity(it) }
        baseWins.sort()
        val rank = ceil(0.5 * DENSITY_BASELINE_WINDOWS).toInt().coerceIn(1, DENSITY_BASELINE_WINDOWS)
        val baseline = baseWins[rank - 1]
        // 从第 K 窗起扫首个结构性跃变窗（纯整数比较，Long 防溢出）
        for (i in DENSITY_BASELINE_WINDOWS until windowCount) {
            val d = windowDensity(i)
            val jump = if (baseline == 0) {
                d >= DENSITY_MIN_JUMP_COUNT // 静止思考(豆包型)后响应上跃（基线×倍率退化为绝对下限）
            } else {
                d.toLong() >= baseline.toLong() * DENSITY_JUMP_UP_FACTOR || // 上跃 ≥2×
                    (baseline >= DENSITY_MIN_BASELINE_FOR_DROP && // 下跃 ≤0.5×（d×2 ≤ baseline）
                        d.toLong() * DENSITY_JUMP_DOWN_FACTOR_INV <= baseline.toLong())
            }
            if (jump) return (i * (DENSITY_STEP_NANOS / 1_000_000L)).toDouble() // 窗 i 起点距簇首偏移
        }
        return null // 全程无跃变=纯稳态=未测（R-10 绝不折 0）
    }

    /** 滑窗 i 的事件密度=其覆盖的 [DENSITY_WINDOW_STEPS] 个连续步桶计数之和（仅 [snapshot] 调用）。 */
    private fun windowDensity(i: Int): Int {
        var sum = 0
        for (k in 0 until DENSITY_WINDOW_STEPS) sum += densityBucket[i + k]
        return sum
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
     * **会话时长 ui-proxy**（spine-3 C6，session_duration_s_dist 观测源），ms：本前台观察会话的
     * 跨度＝观察启动(observeStart)→最后内容事件(lastEvent)。**诚实边界**：这是**前台观察会话跨度**
     * （UI 呈现层，恒 LOW/INCONCLUSIVE），受前台包切换/观察节流界定、终点取最后内容事件而非真实
     * 会话结束——**≠真实对话会话时长**（后者需网络/会话级 instrumentation），不翻 params 门，只作
     * params_fit_approx 的 ui-proxy 锚点。R-10：无事件=null，绝不折 0。跨会话分布见
     * [SessionDurationStats.aggregate]。
     */
    val sessionSpanMs: Double? = null,
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
    /**
     * **密度谱 TTFT 代理**（v4），ms：内容事件按滑动时间窗密度谱统计（步进
     * [ObsSessionStats.DENSITY_STEP_NANOS]/窗宽 [ObsSessionStats.DENSITY_WINDOW_STEPS] 步），取
     * 发送后前 [ObsSessionStats.DENSITY_BASELINE_WINDOWS] 窗中位数为初始稳态基线，返回首个相对基线
     * 结构性跃变窗距簇首的偏移。**不靠静默/锚点/节点，纯时戳密度**——补 v3 簇分割 [ttftClusterMs]
     * 在「思考期播放生成动画」栈（DeepSeek：持续 CONTENT 无 >400ms 静默、ttftClusterMs=null）的缺口
     * （D-52/D-53）。启发式，密度跃变≠精确首字；发送场景外无义；数据不足/无跃变=null（R-10）；恒
     * LOW/INCONCLUSIVE。v3 [ttftClusterMs] 与 v4 两法并存（豆包走 v3、DeepSeek 走 v4，快照都带，
     * UI/落库可择优）。
     */
    val ttftDensityMs: Double? = null,
    /**
     * 密度谱跃变来源标注（与 [ttftDensityMs] 配对）：[ObsSessionStats.SOURCE_DENSITY]="density"
     * （检出密度跃变）| null（无跃变/数据不足，与 ttftDensityMs=null 同步）。
     */
    val densityAnchorSource: String? = null,
) {
    val confidence: String get() = CONFIDENCE

    companion object {
        /** 观察模式恒定置信标注（口径红线）。 */
        const val CONFIDENCE = "LOW/INCONCLUSIVE"
    }
}
