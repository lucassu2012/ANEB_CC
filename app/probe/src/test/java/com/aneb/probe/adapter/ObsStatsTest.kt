package com.aneb.probe.adapter

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * 观察打点统计纯 JVM 单测：first_delta / 环形窗口（256 覆盖）/ nearest-rank p50 / R-10。
 * 时间轴全部用相对纳秒（与 SystemClock.elapsedRealtimeNanos 单调钟同语义）。
 */
class ObsStatsTest {

    private val ms = 1_000_000L // 1ms in nanos
    private val t0 = 10_000_000_000L // 任意会话起点

    private fun stats(specId: String? = null) =
        ObsSessionStats(pkg = "com.example.app", specId = specId, observeStartNanos = t0)

    // ---------- 用例 1：无事件 → null 不折 0（R-10） ----------

    @Test
    fun `no events yields null first delta and null cadence`() {
        val snap = stats().snapshot(t0 + 5_000 * ms)
        assertEquals(0L, snap.events)
        assertNull("R-10：无事件=未测，first_delta 绝不折 0", snap.firstDeltaMs)
        assertNull("R-10：无间隔=未测，cadence 绝不折 0", snap.cadenceP50Ms)
        assertEquals("LOW/INCONCLUSIVE", snap.confidence)
    }

    // ---------- 用例 2：first_delta = 观察启动 → 首内容变化 ----------

    @Test
    fun `first delta measured from observe start to first event`() {
        val s = stats()
        s.onEvent(t0 + 750 * ms)
        s.onEvent(t0 + 900 * ms)
        val snap = s.snapshot(t0 + 1_000 * ms)
        assertEquals(750L, snap.firstDeltaMs)
        assertEquals(2L, snap.events)
    }

    // ---------- 用例 3：单事件无间隔 → cadence null（R-10）；双事件出首个间隔 ----------

    @Test
    fun `cadence needs at least one interval`() {
        val s = stats()
        s.onEvent(t0 + 100 * ms)
        assertNull(s.snapshot(t0 + 200 * ms).cadenceP50Ms)
        s.onEvent(t0 + 130 * ms)
        assertEquals(30.0, s.snapshot(t0 + 200 * ms).cadenceP50Ms!!, 1e-9)
    }

    // ---------- 用例 4：nearest-rank p50（与 KpiCalculator.percentileOrNull 同约定） ----------

    @Test
    fun `cadence p50 uses nearest rank convention`() {
        // 间隔 [100, 200]：rank = ceil(0.5×2) = 1 → 100（偶数集取低位，不做线性插值）
        val even = stats()
        even.onEvent(t0)
        even.onEvent(t0 + 100 * ms)
        even.onEvent(t0 + 300 * ms)
        assertEquals(100.0, even.snapshot(t0 + 400 * ms).cadenceP50Ms!!, 1e-9)

        // 间隔 [50, 100, 400]：rank = ceil(0.5×3) = 2 → 100
        val odd = stats()
        odd.onEvent(t0)
        odd.onEvent(t0 + 50 * ms)
        odd.onEvent(t0 + 150 * ms)
        odd.onEvent(t0 + 550 * ms)
        assertEquals(100.0, odd.snapshot(t0 + 600 * ms).cadenceP50Ms!!, 1e-9)
    }

    // ---------- 用例 5：环形只留最近 256 个间隔（旧间隔被覆盖出窗） ----------

    @Test
    fun `ring keeps only latest 256 intervals`() {
        val s = stats()
        var t = t0
        s.onEvent(t) // 首事件不产生间隔
        // 先 300 个 10ms 间隔（前 44 个将被覆盖出窗）
        repeat(300) { t += 10 * ms; s.onEvent(t) }
        // 再 256 个 50ms 间隔——恰好灌满整环，10ms 间隔全部出窗
        repeat(256) { t += 50 * ms; s.onEvent(t) }
        val snap = s.snapshot(t + 100 * ms)
        assertEquals(50.0, snap.cadenceP50Ms!!, 1e-9)
        assertEquals(1L + 300L + 256L, snap.events)
        // first_delta 仍锚定首事件（环形覆盖不影响）
        assertEquals(0L, snap.firstDeltaMs)
    }

    // ---------- 用例 6：规则命中仅标注计数（非闸门）+ 快照字段透传 ----------

    @Test
    fun `rule matched events are annotation counts not gates`() {
        val s = stats(specId = "doubao")
        s.onEvent(t0 + 10 * ms, ruleMatched = false) // 未命中规则也全量入时戳流
        s.onEvent(t0 + 20 * ms, ruleMatched = true)
        s.onEvent(t0 + 30 * ms, ruleMatched = true)
        val snap = s.snapshot(t0 + 40 * ms)
        assertEquals(3L, snap.events)
        assertEquals(2L, snap.ruleMatchedEvents)
        assertEquals("doubao", snap.specId)
        assertEquals("com.example.app", snap.pkg)
        assertEquals(t0, snap.sessionStartNanos)
        assertEquals(t0 + 40 * ms, snap.updatedAtNanos)
        assertEquals(10L, snap.firstDeltaMs)
    }
}
