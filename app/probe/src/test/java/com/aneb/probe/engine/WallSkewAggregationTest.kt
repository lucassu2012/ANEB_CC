package com.aneb.probe.engine

import com.aneb.probe.net.AnebClient
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * `ScenarioKpi.wallSkewP50Ms` 的汇池口径（T64 §8.2-3 / D-506）。
 *
 * 钉三件事：warmup 样本必须剔除（同既有 `clockSyncRttP50Ms` 惯例）、**跨 phase 汇池**
 * （与按 phase 分开的 RTT 基准刻意不同）、以及无有效样本时返回 null 而非 0。
 */
class WallSkewAggregationTest {

    private fun echo(skewMs: Long?): AnebClient.EchoResult = AnebClient.EchoResult(
        t0Us = 0L, t1Us = 1L, t2Us = 2L, t3Us = 3L,
        offsetUs = 0L, rttUs = 1_000L, httpCode = 200, error = null, timing = null,
        wallSkewMs = skewMs,
    )

    private fun phase(vararg samples: Pair<Boolean, Long?>): ScenarioRunner.ClockSyncOutcome =
        ScenarioRunner.ClockSyncOutcome(
            phaseIndex = 0,
            point = ClockSyncPoint(offsetUs = 0L, errUs = 0L, clientMidUs = 0L, validSamples = samples.size),
            samples = samples.mapIndexed { i, (warmup, skew) ->
                ScenarioRunner.EchoRecord(idx = i, warmup = warmup, result = echo(skew))
            },
        )

    @Test
    fun `取非 warmup 样本的中位`() {
        val cs = phase(false to 10L, false to 20L, false to 30L)
        assertEquals(20L, ScenarioKpi.wallSkewP50Ms(listOf(cs)))
    }

    @Test
    fun `warmup 样本必须被剔除——否则预热轮的坏钟会污染判读`() {
        // warmup 那条是 10 天；若没剔除，中位会被拉走。
        val tenDays = 10L * 24 * 60 * 60 * 1000
        val cs = phase(true to tenDays, false to 10L, false to 20L, false to 30L)
        assertEquals(20L, ScenarioKpi.wallSkewP50Ms(listOf(cs)))
    }

    @Test
    fun `跨 phase 汇池：首尾两次 clock_sync 的样本合起来取中位`() {
        // 与旁边 clockSyncRttP50Ms 按 phase 分开刻意不同——墙钟对不对是一个场景一个数。
        // 三个样本（奇数）避开偶数取法争议，专测「汇池」这一件事。
        val pre = phase(false to 10L, false to 20L)
        val post = phase(false to 30L)
        assertEquals(20L, ScenarioKpi.wallSkewP50Ms(listOf(pre, post)))
    }

    /**
     * 把 P50 的取法**显式钉住**：本仓 `KpiCalculator.percentileOrNull` 是**最近秩法**
     * （`rank = ceil(p × n)`，取下侧那个真实样本），**不是插值中位数**——偶数个样本时
     * `[100, 200]` 给 100 而不是 150。
     *
     * 这条单独立一个测试，是因为落地时我自己先写错了断言（想当然按插值算，红了两条）。
     * 取法本身没问题——它与既有 `clockSyncRttP50Ms` 同一个函数、同一套口径；危险的是
     * 它从没有被任何测试写明过，下一个人照样会误读。现在写明了。
     */
    @Test
    fun `P50 口径＝最近秩取下侧真实样本，不做插值`() {
        val cs = phase(false to 100L, false to 200L)
        assertEquals(100L, ScenarioKpi.wallSkewP50Ms(listOf(cs)))
    }

    @Test
    fun `旧服务端：全部样本 skew 为 null 时结果为 null 而非 0（R-10）`() {
        val cs = phase(false to null, false to null)
        assertNull(ScenarioKpi.wallSkewP50Ms(listOf(cs)))
    }

    @Test
    fun `部分样本有值时只用有值的那些，不把 null 当 0 拉低中位`() {
        // 有值的是 {100, 200, 300}；若把两个 null 当 0 混进来，中位会掉到 100 以下。
        val cs = phase(false to null, false to 100L, false to null, false to 200L, false to 300L)
        assertEquals(200L, ScenarioKpi.wallSkewP50Ms(listOf(cs)))
    }

    @Test
    fun `没有任何 clock_sync phase 时为 null`() {
        assertNull(ScenarioKpi.wallSkewP50Ms(emptyList()))
    }

    @Test
    fun `全是 warmup 时为 null——不因为有样本就硬给一个数`() {
        val cs = phase(true to 10L, true to 20L)
        assertNull(ScenarioKpi.wallSkewP50Ms(listOf(cs)))
    }

    @Test
    fun `负 skew（设备慢）不被丢弃，符号保留`() {
        val cs = phase(false to -5_000L, false to -5_000L)
        assertEquals(-5_000L, ScenarioKpi.wallSkewP50Ms(listOf(cs)))
    }
}
