package com.aneb.probe.scoring

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * AqsScorer Token 模式扩展单测（Profile 框架 v1.0，PROFILE_FRAMEWORK §2.5/§5）。
 *
 * 覆盖：Token 权重表 Σ=1.0、D1 锚点边界、TXT 设计缺省 renormalize（剔 U1/D1 仍出分）、
 * MM 在表项测量失败 fail-closed（D1=null→KPI_MISSING）、S1 软/硬否决（封顶 70/54）、
 * 未知权重表抛错，以及 v0.1/v0.2 默认路径**不受 S1 否决影响**（零回归）。
 */
class AqsScorerTokenTest {

    private fun kv(v: Double?, unit: String = "ms", n: Int = 20, low: Boolean = false) =
        KpiValue(v, unit, n, low)

    /** 默认全部取"优/良"边界值（在场项子分应为 85）。d1/s1 默认 null（由各用例按需覆盖）。 */
    private fun kpiResult(
        t1: Double? = 200.0,
        t2: Double? = 100.0,
        t3: Double? = 0.005,
        t4: Double? = 0.0,
        u1: Double? = 20.0,
        u2: Double? = 150.0,
        n1: Double? = 30.0,
        n2: Double? = 10.0,
        d1: Double? = null,
        s1: Double? = null,
        validity: Validity = Validity.VALID,
        lowConfOn: Set<String> = emptySet(),
    ): KpiResult = KpiResult(
        validity = validity,
        invalidReasons = emptyList(),
        seqMissingCount = 0,
        seqDupCount = 0,
        seqGapCount = 0,
        expectedTokenCount = 600,
        t1TtftMs = kv(t1, low = "T1" in lowConfOn),
        t2ItlP95Ms = kv(t2, low = "T2" in lowConfOn),
        t2ItlP95InclCoalescedMs = kv(t2),
        t3StallRate = kv(t3, "ratio", low = "T3" in lowConfOn),
        t3StallRateInclResume = kv(t3, "ratio"),
        t4SevereStallRate = kv(t4, "ratio"),
        t5ResumeP95Ms = kv(null),
        t5ResumeLatenciesMs = emptyList(),
        n1RttP50Ms = kv(n1, low = "N1" in lowConfOn),
        n2JitterMs = kv(n2, low = "N2" in lowConfOn),
        u1GoodputMbps = kv(u1, "Mbps", low = "U1" in lowConfOn),
        u1GoodputExclSlowStartMbps = kv(u1, "Mbps"),
        u2ToolLoopP95Ms = kv(u2, low = "U2" in lowConfOn),
        d1GoodputMbps = kv(d1, "Mbps", low = "D1" in lowConfOn),
        s1SessionSuccessRate = kv(s1, "ratio"),
    )

    // ---------- 权重表单一事实源 ----------

    @Test
    fun `token mm weights sum to one and include d1`() {
        assertEquals(1.0, AqsScorer.WEIGHTS_TOKEN_MM.values.sum(), 1e-12)
        assertEquals(0.15, AqsScorer.WEIGHTS_TOKEN_MM.getValue("D1"), 1e-12)
        assertEquals(0.15, AqsScorer.WEIGHTS_TOKEN_MM.getValue("U1"), 1e-12)
        assertEquals(0.18, AqsScorer.WEIGHTS_TOKEN_MM.getValue("T1"), 1e-12)
    }

    @Test
    fun `token txt weights sum to one and exclude u1 d1 (design default)`() {
        assertEquals(1.0, AqsScorer.WEIGHTS_TOKEN_TXT.values.sum(), 1e-12)
        assertFalse(AqsScorer.WEIGHTS_TOKEN_TXT.containsKey("U1"))
        assertFalse(AqsScorer.WEIGHTS_TOKEN_TXT.containsKey("D1"))
        assertEquals(0.25, AqsScorer.WEIGHTS_TOKEN_TXT.getValue("T1"), 1e-12)
    }

    @Test
    fun `token weight tables registry maps both ids`() {
        assertEquals(AqsScorer.WEIGHTS_TOKEN_MM, AqsScorer.TOKEN_WEIGHT_TABLES["WEIGHTS_TOKEN_MM"])
        assertEquals(AqsScorer.WEIGHTS_TOKEN_TXT, AqsScorer.TOKEN_WEIGHT_TABLES["WEIGHTS_TOKEN_TXT"])
    }

    // ---------- D1 锚点边界（高者优：0→0，2→55，8→70，25→85，100→100）----------

    @Test
    fun `d1 anchor boundaries score at documented breakpoints`() {
        assertEquals(85.0, AqsScorer.scoreToken(kpiResult(d1 = 25.0, s1 = 1.0), "WEIGHTS_TOKEN_MM").subScores.getValue("D1"), 1e-9)
        assertEquals(70.0, AqsScorer.scoreToken(kpiResult(d1 = 8.0, s1 = 1.0), "WEIGHTS_TOKEN_MM").subScores.getValue("D1"), 1e-9)
        assertEquals(55.0, AqsScorer.scoreToken(kpiResult(d1 = 2.0, s1 = 1.0), "WEIGHTS_TOKEN_MM").subScores.getValue("D1"), 1e-9)
        assertEquals(0.0, AqsScorer.scoreToken(kpiResult(d1 = 0.0, s1 = 1.0), "WEIGHTS_TOKEN_MM").subScores.getValue("D1"), 1e-9)
        assertEquals(100.0, AqsScorer.scoreToken(kpiResult(d1 = 100.0, s1 = 1.0), "WEIGHTS_TOKEN_MM").subScores.getValue("D1"), 1e-9)
    }

    @Test
    fun `mm all excellent-good boundary totals 85 with token version tag`() {
        val r = AqsScorer.scoreToken(kpiResult(d1 = 25.0, s1 = 1.0), "WEIGHTS_TOKEN_MM")
        assertEquals(85.0, r.score!!, 1e-9)
        assertEquals(AqsScorer.AQS_VERSION_TOKEN, r.aqsVersion)
        assertFalse(r.vetoApplied)
        assertFalse(r.s1VetoApplied)
    }

    // ---------- INV-4：设计缺省 renormalize vs 测量失败 fail-closed ----------

    @Test
    fun `txt scores when u1 d1 absent (design default renormalized away)`() {
        // 纯文本场景本无大上下行：U1/D1=null 不应阻断出分（不在 TXT 表内）
        val r = AqsScorer.scoreToken(kpiResult(u1 = null, d1 = null, s1 = 1.0), "WEIGHTS_TOKEN_TXT")
        assertNotNull(r.score)
        assertEquals(85.0, r.score!!, 1e-9)
        assertFalse(r.subScores.containsKey("U1"))
        assertFalse(r.subScores.containsKey("D1"))
    }

    @Test
    fun `mm requires d1 - measurement failure is not computable never zero-filled`() {
        // 多模态场景 D1 在表：测量失败(value=null) → KPI_MISSING（绝不 renormalize 掉、绝不 0 顶替）
        val r = AqsScorer.scoreToken(kpiResult(d1 = null, s1 = 1.0), "WEIGHTS_TOKEN_MM")
        assertNull(r.score)
        assertNotNull(r.notComputableReason)
        assertTrue(r.notComputableReason!!.startsWith("KPI_MISSING:"))
        assertTrue(r.notComputableReason!!.contains("D1"))
    }

    // ---------- S1 软否决（PROFILE_FRAMEWORK §2.5，与 T4 同 min() 机制）----------

    @Test
    fun `s1 below 95 percent caps at 70`() {
        val r = AqsScorer.scoreToken(kpiResult(d1 = 25.0, s1 = 0.93), "WEIGHTS_TOKEN_MM")
        assertTrue(r.s1VetoApplied)
        assertEquals(70.0, r.score!!, 1e-9) // 未否决应为 85 → 封顶 70
    }

    @Test
    fun `s1 below 90 percent caps at 54`() {
        val r = AqsScorer.scoreToken(kpiResult(d1 = 25.0, s1 = 0.85), "WEIGHTS_TOKEN_MM")
        assertTrue(r.s1VetoApplied)
        assertEquals(54.0, r.score!!, 1e-9)
    }

    @Test
    fun `s1 exactly 95 percent does not veto`() {
        val r = AqsScorer.scoreToken(kpiResult(d1 = 25.0, s1 = 0.95), "WEIGHTS_TOKEN_MM")
        assertFalse(r.s1VetoApplied)
        assertEquals(85.0, r.score!!, 1e-9)
    }

    @Test
    fun `s1 veto does not raise an already lower score`() {
        // 全"可/差"边界（D1=2→55）本就低于 54 部分项，S1<0.90 封顶 54 取 min 不抬分
        val r = AqsScorer.scoreToken(
            kpiResult(
                t1 = 3000.0, t2 = 1200.0, t3 = 0.15, u1 = 0.0, u2 = 1800.0,
                n1 = 300.0, n2 = 240.0, d1 = 0.0, s1 = 0.50,
            ),
            "WEIGHTS_TOKEN_MM",
        )
        assertTrue(r.s1VetoApplied)
        assertEquals(0.0, r.score!!, 1e-9)
    }

    @Test
    fun `s1 null does not veto (rounds not measured)`() {
        val r = AqsScorer.scoreToken(kpiResult(d1 = 25.0, s1 = null), "WEIGHTS_TOKEN_MM")
        assertFalse(r.s1VetoApplied)
        assertEquals(85.0, r.score!!, 1e-9)
    }

    // ---------- T4 否决在 Token 模式仍生效 ----------

    @Test
    fun `t4 veto still applies in token mode`() {
        val r = AqsScorer.scoreToken(kpiResult(t4 = 0.02, d1 = 25.0, s1 = 1.0), "WEIGHTS_TOKEN_MM")
        assertTrue(r.vetoApplied)
        assertEquals(54.0, r.score!!, 1e-9)
    }

    // ---------- 未知权重表 ----------

    @Test
    fun `unknown weights table id throws`() {
        assertThrows(IllegalArgumentException::class.java) {
            AqsScorer.scoreToken(kpiResult(s1 = 1.0), "WEIGHTS_NOPE")
        }
    }

    // ---------- 零回归：v0.1/v0.2 默认路径不受 S1/D1 影响 ----------

    @Test
    fun `v01 default path ignores s1 and d1 fields entirely`() {
        // 低 S1 + 缺 D1，v0.1 默认出分应与既有语义一致（85），且 s1VetoApplied=false
        val r = AqsScorer.score(kpiResult(s1 = 0.50, d1 = null))
        assertFalse(r.s1VetoApplied)
        assertEquals(85.0, r.score!!, 1e-9)
        assertEquals(AqsScorer.AQS_VERSION, r.aqsVersion)
        assertFalse(r.subScores.containsKey("D1"))
    }

    @Test
    fun `low confidence on d1 propagates in mm mode`() {
        val r = AqsScorer.scoreToken(kpiResult(d1 = 25.0, s1 = 1.0, lowConfOn = setOf("D1")), "WEIGHTS_TOKEN_MM")
        assertNotNull(r.score)
        assertTrue(r.lowConfidence)
    }
}
