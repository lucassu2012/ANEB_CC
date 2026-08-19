package com.aneb.probe.scoring

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * KpiCalculator U3/D3（单流自适应窗口 goodput 探针）扩展单测（T47 批③，D-468/D-469；
 * spec/PROFILE2_THROUGHPUT_PROBE_SPEC.md §8.4.2/§8.4.3）。
 *
 * 覆盖：窗口 goodput 主口径/剔慢启动并列口径、sample_count 恒为 1（不套用 n<3 判据）、
 * low_confidence 完全由 rttDominanceOk 决定、http2xx=false 记 null、auxiliary 诊断字段
 * 直通、rtt_drift_ratio 计算、null 输入向后兼容。
 */
class KpiCalculatorU3D3Test {

    // 48MB in 4s = 48*1024*1024*8/4/1e6 ≈ 100.66 Mbps
    private fun window(
        windowTargetMs: Int = 4000,
        windowActualNanos: Long? = 4_000_000_000L,
        bytesTransferred: Long = 50_331_648L,
        http2xx: Boolean = true,
        slowStartUs: Long? = null,
        slowStartBytes: Long? = null,
        rttRefMsPre: Double? = 100.0,
        rttRefMsPost: Double? = 100.0,
        rttDominanceOk: Boolean = true,
        rttDominanceRatio: Double? = 40.0,
        windowUnderrun: Boolean = false,
    ) = AdaptiveWindowResult(
        windowTargetMs = windowTargetMs,
        windowActualNanos = windowActualNanos,
        bytesTransferred = bytesTransferred,
        http2xx = http2xx,
        slowStartUs = slowStartUs,
        slowStartBytes = slowStartBytes,
        rttRefMsPre = rttRefMsPre,
        rttRefMsPost = rttRefMsPost,
        rttDominanceRatio = rttDominanceRatio,
        rttDominanceOk = rttDominanceOk,
        windowUnderrun = windowUnderrun,
    )

    // ---------- U3 主口径 ----------

    @Test
    fun `u3 goodput computed from bytesTransferred over windowActualNanos`() {
        val out = KpiCalculator.calculate(KpiInput(adaptiveUpload = window()))
        assertEquals("Mbps", out.u3GoodputMbps.unit)
        assertEquals(50_331_648L * 8.0 / 4.0 / 1e6, out.u3GoodputMbps.value!!, 1e-6)
    }

    @Test
    fun `u3 sample_count is always 1 when window ran, not an n-below-3 signal`() {
        val out = KpiCalculator.calculate(KpiInput(adaptiveUpload = window()))
        assertEquals(1, out.u3GoodputMbps.sampleCount)
    }

    @Test
    fun `u3 low_confidence follows rttDominanceOk not sample count`() {
        // sample_count 恒为 1（结构性事实），但 dominance 失败时仍应标 low_confidence——
        // 证明这里用的不是 MIN_UPLOAD_SAMPLES 的 n<3 判据（n=1 若套用该判据会恒为 true）。
        val ok = KpiCalculator.calculate(KpiInput(adaptiveUpload = window(rttDominanceOk = true)))
        assertFalse(ok.u3GoodputMbps.lowConfidence)
        val bad = KpiCalculator.calculate(KpiInput(adaptiveUpload = window(rttDominanceOk = false)))
        assertTrue(bad.u3GoodputMbps.lowConfidence)
        assertEquals(1, bad.u3GoodputMbps.sampleCount) // 样本数不变，只是标了低置信
    }

    @Test
    fun `u3 http2xx false yields null value never zero`() {
        val out = KpiCalculator.calculate(KpiInput(adaptiveUpload = window(http2xx = false)))
        assertNull(out.u3GoodputMbps.value)
        assertEquals(0, out.u3GoodputMbps.sampleCount)
    }

    @Test
    fun `u3 null windowActualNanos yields null value`() {
        val out = KpiCalculator.calculate(KpiInput(adaptiveUpload = window(windowActualNanos = null)))
        assertNull(out.u3GoodputMbps.value)
    }

    // ---------- U3 剔慢启动并列口径 ----------

    @Test
    fun `u3 excl slow start subtracts ramp bytes and nanos`() {
        // 4s 窗口传 48MB，前 0.5s 爬坡传了 4MB——剔除后剩 3.5s 传 44MB
        val out = KpiCalculator.calculate(
            KpiInput(
                adaptiveUpload = window(
                    windowActualNanos = 4_000_000_000L,
                    bytesTransferred = 48 * 1_048_576L,
                    slowStartUs = 500_000L,
                    slowStartBytes = 4 * 1_048_576L,
                ),
            )
        )
        val remainBytes = 48 * 1_048_576L - 4 * 1_048_576L
        val remainNs = 4_000_000_000L - 500_000L * 1000L
        val expected = remainBytes * 8.0 / (remainNs / 1e9) / 1e6
        assertEquals(expected, out.u3GoodputExclSlowStartMbps.value!!, 1e-6)
    }

    @Test
    fun `u3 excl slow start is null when ramp info missing`() {
        val out = KpiCalculator.calculate(
            KpiInput(adaptiveUpload = window(slowStartUs = null, slowStartBytes = null)),
        )
        assertNull("估不出慢启动就不猜（同 U1 既有语义）", out.u3GoodputExclSlowStartMbps.value)
    }

    // ---------- auxiliary 诊断字段直通 ----------

    @Test
    fun `u3 auxiliary fields pass through and drift ratio is computed`() {
        val out = KpiCalculator.calculate(
            KpiInput(
                adaptiveUpload = window(
                    windowTargetMs = 4000,
                    windowActualNanos = 4_012_000_000L,
                    bytesTransferred = 23_145_728L,
                    rttRefMsPre = 29.1,
                    rttRefMsPost = 30.4,
                    rttDominanceRatio = 137.8,
                ),
            )
        )
        assertEquals(4000, out.u3WindowTargetMs)
        assertEquals(4012.0, out.u3WindowActualMs!!, 1e-6)
        assertEquals(23_145_728L, out.u3BytesTransferred)
        assertEquals(29.1, out.u3RttRefMsPre!!, 1e-9)
        assertEquals(30.4, out.u3RttRefMsPost!!, 1e-9)
        assertEquals(30.4 / 29.1, out.u3RttDriftRatio!!, 1e-9)
        assertEquals(137.8, out.u3RttDominanceRatio!!, 1e-9)
        assertTrue(out.u3RttDominanceOk)
    }

    @Test
    fun `u3 drift ratio null when either rtt ref missing`() {
        val out = KpiCalculator.calculate(
            KpiInput(adaptiveUpload = window(rttRefMsPre = 29.1, rttRefMsPost = null)),
        )
        assertNull(out.u3RttDriftRatio)
    }

    // ---------- D3 镜像（下行独立于 U3） ----------

    @Test
    fun `d3 is independent of u3 and mirrors the same computation`() {
        val out = KpiCalculator.calculate(
            KpiInput(
                adaptiveUpload = window(bytesTransferred = 10_000_000L, rttDominanceOk = false),
                adaptiveDownload = window(bytesTransferred = 400_000_000L, rttDominanceOk = true),
            )
        )
        assertTrue("u3 独立判 low_confidence", out.u3GoodputMbps.lowConfidence)
        assertFalse("d3 不受 u3 影响", out.d3GoodputMbps.lowConfidence)
        assertEquals(400_000_000L * 8.0 / 4.0 / 1e6, out.d3GoodputMbps.value!!, 1e-6)
    }

    // ---------- null 输入向后兼容 ----------

    @Test
    fun `default kpi result has null u3 and d3 when scenario never ran s4_throughput`() {
        val out = KpiCalculator.calculate(KpiInput(ttftSamples = listOf(TtftSample(150.0))))
        assertNull(out.u3GoodputMbps.value)
        assertNull(out.d3GoodputMbps.value)
        assertNull(out.u3WindowTargetMs)
        assertFalse(out.u3RttDominanceOk) // 默认值 false（Entity 层用 windowTargetMs!=null 区分 null vs false）
    }

    @Test
    fun `s4_throughput-shaped input (only adaptive window, no token-upload-download-toolloop-round) is not NO_DATA`() {
        // 真实 s4_throughput 场景的实际形状：只有 clock_sync + adaptive window 两类 phase。
        // 回归钉子：曾经因 noData 判定漏算 adaptiveUpload/adaptiveDownload，导致这类场景
        // 恒被误判 NO_DATA→INVALID，U3/D3 值恒被 gate 成 null（批③单测首跑即抓到）。
        val out = KpiCalculator.calculate(KpiInput(adaptiveUpload = window(), adaptiveDownload = window()))
        assertFalse(out.invalidReasons.contains(InvalidReason.NO_DATA))
        assertTrue(out.validity != Validity.INVALID)
        assertEquals(50_331_648L * 8.0 / 4.0 / 1e6, out.u3GoodputMbps.value!!, 1e-6)
    }

    @Test
    fun `u3 low_confidence contributes to scenario validity`() {
        val out = KpiCalculator.calculate(KpiInput(adaptiveUpload = window(rttDominanceOk = false)))
        assertEquals(Validity.VALID_LOW_CONFIDENCE, out.validity)
    }

    // ---------- window_underrun -> low_confidence（spec §8.4.3 的第二条判据，批③漏落，D-478 -> 本次补齐）----------
    //
    // spec §8.4.3 逐字：「low_confidence 完全由 §8.3.3 的自检结果决定
    // （!rtt_dominance_ok 或 window_underrun 或字节/样本数不足其一即 true）」。
    // 批③只落了 !rtt_dominance_ok 一条。D-479 真机首跑即命中漏掉的那条：
    // 上行 48MB ceiling 先于 4000ms 窗口到达（underrun=true），当时被标成 low_confidence=false
    // 发表出去——**一个方向错误的置信度标记，比没有标记更危险**。
    // 下面按 D-322「守卫能不能失败要造反例证明」配对：正例、反例、下行侧、以及两条件同时成立。

    @Test fun `window_underrun 为真时 U3 判低置信（即便 dominance 通过）`() {
        val out = KpiCalculator.calculate(
            KpiInput(adaptiveUpload = window(rttDominanceOk = true, windowUnderrun = true)),
        )
        assertTrue("dominance 通过但窗口提前结束，spec §8.4.3 要求判低置信", out.u3GoodputMbps.lowConfidence)
        assertTrue("剔慢启动口径同样应判低置信", out.u3GoodputExclSlowStartMbps.lowConfidence)
    }

    @Test fun `window_underrun 为假且 dominance 通过时 U3 判高置信（反例：不是恒为真）`() {
        val out = KpiCalculator.calculate(
            KpiInput(adaptiveUpload = window(rttDominanceOk = true, windowUnderrun = false)),
        )
        assertFalse("两条件都健康时不应判低置信，否则该标志退化为恒真", out.u3GoodputMbps.lowConfidence)
    }

    @Test fun `window_underrun 为真时 D3 同样判低置信（下行侧不遗漏）`() {
        val out = KpiCalculator.calculate(
            KpiInput(adaptiveDownload = window(rttDominanceOk = true, windowUnderrun = true)),
        )
        assertTrue("下行侧同一判据", out.d3GoodputMbps.lowConfidence)
    }

    @Test fun `dominance 不通过与 window_underrun 同时成立时仍判低置信（或的语义）`() {
        val out = KpiCalculator.calculate(
            KpiInput(adaptiveUpload = window(rttDominanceOk = false, windowUnderrun = true)),
        )
        assertTrue(out.u3GoodputMbps.lowConfidence)
    }
}
