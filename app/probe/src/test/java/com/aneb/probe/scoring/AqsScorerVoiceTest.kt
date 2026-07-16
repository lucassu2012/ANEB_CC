package com.aneb.probe.scoring

import com.aneb.probe.engine.VoiceRunner
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 语音实时交互出分锚定（PROFILE_FRAMEWORK §4.1，D-31）：WEIGHTS_VOICE Σ=1、
 * scoreVoice 加权/硬否决/缺失语义，及 VoiceRunner 纯函数（帧抖动 P95 / 口到耳预算合成）。
 */
class AqsScorerVoiceTest {

    private fun v(value: Double?, unit: String = "ms", n: Int = 10) =
        KpiValue(value, unit, n, lowConfidence = false)

    @Test
    fun `WEIGHTS_VOICE 权重和为 1`() {
        assertEquals(1.0, AqsScorer.WEIGHTS_VOICE.values.sum(), 1e-9)
    }

    @Test
    fun `全优良输入_出分且子分含 M 组与基线`() {
        val r = AqsScorer.scoreVoice(
            n1RttMs = v(25.0), n2JitterMs = v(3.0),
            m1BudgetMs = v(95.0), m2DownFrameJitterMs = v(5.0), m3UpFrameJitterMs = v(8.0),
        )
        assertTrue("应可计算", r.score != null)
        assertEquals(AqsScorer.AQS_VERSION_VOICE, r.aqsVersion)
        assertEquals(setOf("M1", "M2", "M3", "N1", "N2"), r.subScores.keys)
        assertTrue("全优良应高分", r.score!! > 85.0)
        assertTrue(!r.vetoApplied)
    }

    @Test
    fun `M1 超 400ms 红线_硬否决封顶 54`() {
        val r = AqsScorer.scoreVoice(
            n1RttMs = v(25.0), n2JitterMs = v(3.0),
            m1BudgetMs = v(450.0), m2DownFrameJitterMs = v(5.0), m3UpFrameJitterMs = v(8.0),
        )
        assertTrue("M1>400 应触发硬否决", r.vetoApplied)
        assertTrue("分数应封顶 ≤54", r.score!! <= AqsScorer.T4_VETO_CAP)
    }

    @Test
    fun `在表指标缺失_KPI_MISSING 不以 0 顶替`() {
        val r = AqsScorer.scoreVoice(
            n1RttMs = v(25.0), n2JitterMs = v(3.0),
            m1BudgetMs = v(95.0), m2DownFrameJitterMs = v(null), m3UpFrameJitterMs = v(8.0),
        )
        assertNull("缺 M2 → 分 null（R-10）", r.score)
        assertEquals("KPI_MISSING:M2", r.notComputableReason)
    }

    @Test
    fun `帧抖动P95_精确节奏为0_离群被P95捕获_样本不足null`() {
        // 20ms 名义节奏（µs）：完全精确 → 0
        val exact = List(100) { 20_000L }
        assertEquals(0.0, VoiceRunner.frameJitterP95Ms(exact, 20_000L)!!, 1e-9)
        // 100 个间隔里 6 个 60ms 离群（偏差 40ms）→ P95 落在离群带
        val outliers = List(94) { 20_000L } + List(6) { 60_000L }
        assertEquals(40.0, VoiceRunner.frameJitterP95Ms(outliers, 20_000L)!!, 1e-9)
        // <2 间隔 → null（R-10）
        assertNull(VoiceRunner.frameJitterP95Ms(listOf(20_000L), 20_000L))
    }

    @Test
    fun `口到耳预算_RTT加最大帧抖动加常数_任一缺失null`() {
        val b = VoiceRunner.mouthEarBudgetMs(rttP50Ms = 20.0, upJitterMs = 5.0, downJitterMs = 10.0)
        assertEquals(20.0 + 10.0 + VoiceRunner.CODEC_JB_BUDGET_MS, b!!, 1e-9)
        assertNull(VoiceRunner.mouthEarBudgetMs(null, 5.0, 10.0))
        assertNull(VoiceRunner.mouthEarBudgetMs(20.0, null, 10.0))
        assertNull(VoiceRunner.mouthEarBudgetMs(20.0, 5.0, null))
    }
}
