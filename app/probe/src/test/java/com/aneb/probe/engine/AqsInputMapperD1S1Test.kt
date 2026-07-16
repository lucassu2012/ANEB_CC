package com.aneb.probe.engine

import com.aneb.probe.scoring.AqsScorer
import com.aneb.probe.scoring.KpiResult
import com.aneb.probe.scoring.KpiValue
import com.aneb.probe.scoring.Validity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * AqsInputMapper Token 专用 D1/S1 传导单测（Profile 框架 v1.0）：
 * D1 ← S3 下行大对象 goodput；S1 ← 全场景成功轮次占比（计数聚合，非中位数）。
 * 并守护 v0.1 合成分不受 D1/S1 影响（零回归）。
 */
class AqsInputMapperD1S1Test {

    private fun mbps(v: Double?, n: Int = 5) = KpiValue(v, "Mbps", if (v == null) 0 else n, false)
    private fun ratio(v: Double?, n: Int) = KpiValue(v, "ratio", n, false)

    /** 一份可控 KpiResult，默认全 VALID、基本 KPI 齐备；d1/s1 单独覆盖。 */
    private fun kpi(
        t1: Double? = 100.0, t2: Double? = 50.0, t3: Double? = 0.0, t4: Double? = 0.0,
        n1: Double? = 20.0, n2: Double? = 5.0, u1: Double? = 30.0, u2: Double? = 100.0,
        d1: KpiValue = mbps(null),
        s1: KpiValue = KpiValue.empty("ratio"),
    ): KpiResult = KpiResult(
        validity = Validity.VALID, invalidReasons = emptyList(),
        seqMissingCount = 0, seqDupCount = 0, seqGapCount = 0, expectedTokenCount = 100,
        t1TtftMs = KpiValue(t1, "ms", 150, false),
        t2ItlP95Ms = KpiValue(t2, "ms", 150, false),
        t2ItlP95InclCoalescedMs = KpiValue(t2, "ms", 150, false),
        t3StallRate = KpiValue(t3, "ratio", 150, false),
        t3StallRateInclResume = KpiValue(t3, "ratio", 150, false),
        t4SevereStallRate = KpiValue(t4, "ratio", 150, false),
        t5ResumeP95Ms = KpiValue(null, "ms", 0, false),
        t5ResumeLatenciesMs = emptyList(),
        n1RttP50Ms = KpiValue(n1, "ms", 20, false),
        n2JitterMs = KpiValue(n2, "ms", 20, false),
        u1GoodputMbps = KpiValue(u1, "Mbps", 5, false),
        u1GoodputExclSlowStartMbps = KpiValue(null, "Mbps", 0, false),
        u2ToolLoopP95Ms = KpiValue(u2, "ms", 8, false),
        d1GoodputMbps = d1,
        s1SessionSuccessRate = s1,
    )

    @Test
    fun `d1 comes from s3 download only`() {
        val composite = AqsInputMapper.map(
            mapOf(
                // 只有 S3 有真实 D1；S1/S2 的 D1 设毒值，若被误采会污染
                AqsInputMapper.S1 to listOf(kpi(d1 = mbps(0.001))),
                AqsInputMapper.S2 to listOf(kpi(d1 = mbps(0.001))),
                AqsInputMapper.S3 to listOf(kpi(d1 = mbps(40.0))),
            )
        )
        assertEquals(40.0, composite.d1GoodputMbps.value!!, 1e-9)
    }

    @Test
    fun `s1 aggregates success rounds across scenarios by count`() {
        // s1_chat: 3 轮全成功(3)；s2: 4 轮 0.75(3)；s3: 3 轮全成功(3) → 9/10 = 0.9
        val composite = AqsInputMapper.map(
            mapOf(
                AqsInputMapper.S1 to listOf(kpi(s1 = ratio(1.0, 3))),
                AqsInputMapper.S2 to listOf(kpi(s1 = ratio(0.75, 4))),
                AqsInputMapper.S3 to listOf(kpi(s1 = ratio(1.0, 3))),
            )
        )
        assertEquals(0.9, composite.s1SessionSuccessRate.value!!, 1e-9)
        assertEquals(10, composite.s1SessionSuccessRate.sampleCount) // 总轮次
    }

    @Test
    fun `s1 null when no rounds anywhere`() {
        val composite = AqsInputMapper.map(
            mapOf(
                AqsInputMapper.S1 to listOf(kpi()),
                AqsInputMapper.S2 to listOf(kpi()),
                AqsInputMapper.S3 to listOf(kpi()),
            )
        )
        assertNull(composite.s1SessionSuccessRate.value) // 无轮次 → null，绝不 0
    }

    @Test
    fun `d1 null when s3 has no download`() {
        val composite = AqsInputMapper.map(mapOf(AqsInputMapper.S2 to listOf(kpi())))
        assertNull(composite.d1GoodputMbps.value)
    }

    @Test
    fun `v01 composite score unaffected by d1 s1 presence (zero regression)`() {
        val base = mapOf(
            AqsInputMapper.S1 to listOf(kpi(n1 = 20.0, n2 = 5.0)),
            AqsInputMapper.S2 to listOf(kpi(t1 = 150.0, t2 = 80.0, u2 = 120.0)),
            AqsInputMapper.S3 to listOf(kpi(u1 = 25.0)),
        )
        val withoutExtras = AqsScorer.score(AqsInputMapper.map(base)).score
        val withExtras = mapOf(
            AqsInputMapper.S1 to listOf(kpi(n1 = 20.0, n2 = 5.0, s1 = ratio(0.50, 4))),
            AqsInputMapper.S2 to listOf(kpi(t1 = 150.0, t2 = 80.0, u2 = 120.0, s1 = ratio(0.50, 4))),
            AqsInputMapper.S3 to listOf(kpi(u1 = 25.0, d1 = mbps(40.0), s1 = ratio(0.50, 4))),
        )
        val withScore = AqsScorer.score(AqsInputMapper.map(withExtras)).score
        // v0.1 权重表不含 D1/S1，且 S1 否决只在 scoreToken 生效 → 合成分完全一致
        assertEquals(withoutExtras!!, withScore!!, 1e-9)
    }

    @Test
    fun `token scoreToken consumes mapped d1 and s1`() {
        // S3 齐备 D1，全场景高完成率 → MM 出分且不触发 S1 否决
        val composite = AqsInputMapper.map(
            mapOf(
                AqsInputMapper.S1 to listOf(kpi(n1 = 20.0, n2 = 5.0, s1 = ratio(1.0, 5))),
                AqsInputMapper.S2 to listOf(kpi(t1 = 150.0, t2 = 80.0, t3 = 0.0, u2 = 120.0, s1 = ratio(1.0, 5))),
                AqsInputMapper.S3 to listOf(kpi(u1 = 25.0, d1 = mbps(40.0), s1 = ratio(1.0, 5))),
            )
        )
        val r = AqsScorer.scoreToken(composite, "WEIGHTS_TOKEN_MM")
        assertTrue("MM 出分（D1 已从 S3 映射）", r.score != null)
        assertTrue(r.subScores.containsKey("D1"))
        assertEquals(false, r.s1VetoApplied) // 完成率 1.0 → 不否决
    }
}
