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
 * - R-10：无事件 → firstDeltaMs=null；不足一个间隔 → cadenceP50Ms=null，绝不折 0。
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
        private const val NONE = Long.MIN_VALUE
    }

    private var firstEventNanos = NONE
    private var lastEventNanos = NONE
    private var eventCount = 0L
    private var ruleMatchedCount = 0L
    private val ring = LongArray(RING_CAPACITY)
    private var ringSize = 0
    private var ringNext = 0

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
    )

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
) {
    val confidence: String get() = CONFIDENCE

    companion object {
        /** 观察模式恒定置信标注（口径红线）。 */
        const val CONFIDENCE = "LOW/INCONCLUSIVE"
    }
}
