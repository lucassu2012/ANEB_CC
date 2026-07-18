package com.aneb.probe.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * [SpeedSampleMath] 纯计算锚定（无 Android/无网络，同 `LiveTelemetryTest` 惯例）：
 * 中位数 / 抖动 / 0.6s 滑窗吞吐，含 R-10「不足则 null，绝不折 0」边界与滑窗淘汰。
 */
class SpeedSampleMathTest {

    // ---- median ----

    @Test
    fun `median null when empty`() {
        assertNull(SpeedSampleMath.median(emptyList()))
    }

    @Test
    fun `median odd count picks middle after sorting`() {
        assertEquals(3.0, SpeedSampleMath.median(listOf(5.0, 1.0, 3.0))!!, 0.0)
    }

    @Test
    fun `median even count averages the two middles`() {
        assertEquals(2.5, SpeedSampleMath.median(listOf(1.0, 4.0, 2.0, 3.0))!!, 0.0)
    }

    // ---- jitter ----

    @Test
    fun `jitter null below two samples`() {
        assertNull(SpeedSampleMath.jitter(listOf(10.0)))
    }

    @Test
    fun `jitter is median of consecutive absolute diffs`() {
        // [10,13,12,20] → |diffs| [3,1,8] → median 3
        assertEquals(3.0, SpeedSampleMath.jitter(listOf(10.0, 13.0, 12.0, 20.0))!!, 0.0)
    }

    // ---- windowMbps ----

    @Test
    fun `windowMbps null on first sample and appends it in place`() {
        val w = ArrayDeque<Pair<Long, Long>>()
        assertNull(SpeedSampleMath.windowMbps(w, nowNs = 0L, nowBytes = 0L)) // 窗<2
        assertEquals(1, w.size)
    }

    @Test
    fun `windowMbps computes bits per second across the window`() {
        val w = ArrayDeque<Pair<Long, Long>>()
        SpeedSampleMath.windowMbps(w, nowNs = 0L, nowBytes = 0L)
        // +0.5s 累计 1_000_000 字节：1e6*8 / 0.5 / 1e6 = 16 Mbps
        val mbps = SpeedSampleMath.windowMbps(w, nowNs = 500_000_000L, nowBytes = 1_000_000L)
        assertEquals(16.0, mbps!!, 1e-9)
    }

    @Test
    fun `windowMbps evicts samples older than the window`() {
        val w = ArrayDeque<Pair<Long, Long>>()
        SpeedSampleMath.windowMbps(w, 0L, 0L)                     // t=0
        SpeedSampleMath.windowMbps(w, 500_000_000L, 1_000_000L)   // t=0.5s
        // t=0.8s：淘汰 t=0（0.8-0=0.8s>0.6s），队首变 t=0.5s；dB=1.6M-1M=600k, dS=0.3s → 16 Mbps
        val mbps = SpeedSampleMath.windowMbps(w, 800_000_000L, 1_600_000L)
        assertEquals(16.0, mbps!!, 1e-9)
        assertEquals(500_000_000L, w.first().first) // t=0 已淘汰
    }

    @Test
    fun `windowMbps null when span at or below one tenth second (never folds to zero)`() {
        val w = ArrayDeque<Pair<Long, Long>>()
        SpeedSampleMath.windowMbps(w, 0L, 0L)
        // dS 恰 0.1s → 条件 dS>0.1 为 false → null（R-10，不折 0）
        assertNull(SpeedSampleMath.windowMbps(w, 100_000_000L, 500_000L))
    }
}
