package com.aneb.probe.scoring

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * KpiCalculator D1（下行 goodput）/ S1（会话完成率）扩展单测（Profile 框架 v1.0，
 * PROFILE_FRAMEWORK §2.2 BM-06/BM-09）。
 *
 * 覆盖：D1 2xx 口径 goodput 逐次 P50、非 2xx 剔除记 null（R-10）、MIN_DOWNLOAD 低置信（R-29）；
 * S1 成功轮次占比、无轮次 null；INVALID 场景 gate 置 null；download/round-only 输入非 NO_DATA。
 */
class KpiCalculatorD1S1Test {

    // 1MB in 0.1s = 1e6*8/0.1/1e6 = 80 Mbps
    private fun dl(bytes: Long = 1_000_000L, durMs: Double = 100.0, ok: Boolean = true) =
        DownloadResult(bytes = bytes, durationNanos = (durMs * 1e6).toLong(), http2xx = ok)

    // ---------- D1 下行 goodput ----------

    @Test
    fun `d1 is median 2xx goodput across downloads`() {
        // 三次：80 / 40 / 160 Mbps → P50(最近秩 rank=ceil(0.5*3)=2) = 80
        val out = KpiCalculator.calculate(
            KpiInput(
                downloadResults = listOf(
                    dl(durMs = 100.0), // 80
                    dl(durMs = 200.0), // 40
                    dl(durMs = 50.0),  // 160
                ),
            )
        )
        assertEquals("Mbps", out.d1GoodputMbps.unit)
        assertEquals(80.0, out.d1GoodputMbps.value!!, 1e-6)
        assertEquals(3, out.d1GoodputMbps.sampleCount)
        assertFalse(out.d1GoodputMbps.lowConfidence)
    }

    @Test
    fun `d1 non-2xx download is excluded and never zero-filled`() {
        val out = KpiCalculator.calculate(KpiInput(downloadResults = listOf(dl(ok = false))))
        assertNull(out.d1GoodputMbps.value) // 失败样本 → null，绝不 0（R-10）
        assertEquals(0, out.d1GoodputMbps.sampleCount)
    }

    @Test
    fun `d1 below min download is low confidence`() {
        // 2 次有效下载 < MIN_DOWNLOAD(3) → 出值但带低置信（R-29）
        val out = KpiCalculator.calculate(KpiInput(downloadResults = listOf(dl(), dl())))
        assertEquals(2, out.d1GoodputMbps.sampleCount)
        assertTrue(out.d1GoodputMbps.lowConfidence)
        // 且 run 判 VALID_LOW_CONFIDENCE
        assertEquals(Validity.VALID_LOW_CONFIDENCE, out.validity)
    }

    @Test
    fun `d1 zero-duration download is excluded`() {
        val bad = DownloadResult(bytes = 1_000_000L, durationNanos = 0L, http2xx = true)
        val out = KpiCalculator.calculate(KpiInput(downloadResults = listOf(bad, dl(), dl(), dl())))
        assertEquals(3, out.d1GoodputMbps.sampleCount) // 0 耗时项剔除
    }

    // ---------- S1 会话完成率 ----------

    @Test
    fun `s1 is success round ratio`() {
        val out = KpiCalculator.calculate(
            KpiInput(roundOutcomes = listOf(true, true, true, false).map { RoundOutcome(it) })
        )
        assertEquals("ratio", out.s1SessionSuccessRate.unit)
        assertEquals(0.75, out.s1SessionSuccessRate.value!!, 1e-9)
        assertEquals(4, out.s1SessionSuccessRate.sampleCount)
    }

    @Test
    fun `s1 all success is one`() {
        val out = KpiCalculator.calculate(
            KpiInput(roundOutcomes = (1..10).map { RoundOutcome(true) })
        )
        assertEquals(1.0, out.s1SessionSuccessRate.value!!, 1e-9)
    }

    @Test
    fun `s1 no rounds yields null never zero`() {
        val out = KpiCalculator.calculate(
            KpiInput(echoSamples = (1..20).map { EchoSample(20_000_000L) })
        )
        assertNull(out.s1SessionSuccessRate.value) // 无轮次样本 → null（绝不 0，R-10）
    }

    // ---------- 有效性 Gate ----------

    @Test
    fun `download-only input is not NO_DATA`() {
        val out = KpiCalculator.calculate(KpiInput(downloadResults = listOf(dl(), dl(), dl())))
        assertFalse(out.invalidReasons.contains(InvalidReason.NO_DATA))
        assertTrue(out.validity != Validity.INVALID)
    }

    @Test
    fun `round-only input is not NO_DATA`() {
        val out = KpiCalculator.calculate(KpiInput(roundOutcomes = listOf(RoundOutcome(true))))
        assertFalse(out.invalidReasons.contains(InvalidReason.NO_DATA))
    }

    @Test
    fun `invalid scenario gates d1 and s1 to null`() {
        val out = KpiCalculator.calculate(
            KpiInput(
                downloadResults = listOf(dl(), dl(), dl()),
                roundOutcomes = listOf(true, false).map { RoundOutcome(it) },
                streamTruncated = true, // → INVALID(TRUNCATED)
            )
        )
        assertEquals(Validity.INVALID, out.validity)
        assertNull(out.d1GoodputMbps.value)
        assertNull(out.s1SessionSuccessRate.value)
    }

    @Test
    fun `default kpi result has null d1 and s1 (backward compatible)`() {
        // 无 download/round 输入的既有场景：D1/S1 默认 null，不影响既有 KPI
        val out = KpiCalculator.calculate(
            KpiInput(ttftSamples = listOf(TtftSample(150.0)))
        )
        assertNull(out.d1GoodputMbps.value)
        assertNull(out.s1SessionSuccessRate.value)
    }
}
