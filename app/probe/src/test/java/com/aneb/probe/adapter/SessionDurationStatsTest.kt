package com.aneb.probe.adapter

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 会话时长 ui-proxy 纯 JVM 单测（spine-3 C6）：[ObsSessionStats] 的 sessionSpanMs 计算
 * （观察启动→最后内容事件，R-10 无事件→null）+ [SessionDurationStats.aggregate] 跨会话分布
 * （脏值过滤 / ms→s / nearest-rank / 阈值门）。时间轴用相对纳秒（同 SystemClock 单调钟语义）。
 */
class SessionDurationStatsTest {

    private val ms = 1_000_000L
    private val t0 = 10_000_000_000L
    private fun stats() = ObsSessionStats("com.example.app", specId = "doubao", observeStartNanos = t0)

    // ---- sessionSpanMs（会话跨度 = lastEvent − observeStart，非 updatedAt） ----

    @Test
    fun `no events yields null session span (R-10)`() {
        assertNull("R-10：无事件=无观察会话活动，绝不折 0", stats().snapshot(t0 + 5_000 * ms).sessionSpanMs)
    }

    @Test
    fun `session span spans observe start to last content event not snapshot time`() {
        val s = stats()
        s.onEvent(t0 + 100 * ms)
        s.onEvent(t0 + 900 * ms) // 最后内容事件在 900ms
        val snap = s.snapshot(t0 + 5_000 * ms) // 快照时间 5000ms 不参与
        assertEquals("跨度取 lastEvent−start=900，非 updatedAt", 900.0, snap.sessionSpanMs!!, 1e-9)
    }

    @Test
    fun `single event span is observe-start to that event not null`() {
        val s = stats()
        s.onEvent(t0 + 42 * ms) // 唯一事件；跨度=observeStart→该事件=42ms（有活动，区别于无事件的 null）
        assertEquals(42.0, s.snapshot(t0 + 100 * ms).sessionSpanMs!!, 1e-9)
    }

    // ---- aggregate：分布聚合 ----

    @Test
    fun `aggregate empty or all-null is null (R-10)`() {
        assertNull(SessionDurationStats.aggregate(emptyList()))
        assertNull(SessionDurationStats.aggregate(listOf(null, null)))
    }

    @Test
    fun `aggregate filters null negative and non-finite samples`() {
        // 净样本 = {1000, 2000}ms → {1,2}s
        val d = SessionDurationStats.aggregate(
            listOf(1000.0, null, -5.0, Double.NaN, Double.POSITIVE_INFINITY, 2000.0),
        )!!
        assertEquals(2, d.count)
        assertEquals(1.0, d.minSec, 1e-9)
        assertEquals(2.0, d.maxSec, 1e-9)
        // p50 rank=ceil(0.5×2)=1 → 1.0s
        assertEquals(1.0, d.p50Sec, 1e-9)
    }

    @Test
    fun `aggregate converts ms to seconds and uses nearest rank quantiles`() {
        // {1000,2000,3000}ms → {1,2,3}s；p50 rank=ceil(.5×3)=2→2s, p90=ceil(.9×3)=3→3s, p99=3→3s
        val d = SessionDurationStats.aggregate(listOf(3000.0, 1000.0, 2000.0))!!
        assertEquals(3, d.count)
        assertEquals(2.0, d.p50Sec, 1e-9)
        assertEquals(3.0, d.p90Sec, 1e-9)
        assertEquals(3.0, d.p99Sec, 1e-9)
    }

    @Test
    fun `below threshold flags small samples and clears at threshold`() {
        assertTrue("3 < 30 → 保持 keep_pending", SessionDurationStats.aggregate(listOf(1.0, 2.0, 3.0))!!.belowDistThreshold)
        val thirty = (1..SessionDurationStats.MIN_SAMPLES_FOR_DIST).map { (it * 1000).toDouble() }
        assertFalse("达阈值 → belowDistThreshold 清零", SessionDurationStats.aggregate(thirty)!!.belowDistThreshold)
    }
}
