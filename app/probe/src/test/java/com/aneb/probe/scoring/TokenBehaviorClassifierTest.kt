package com.aneb.probe.scoring

import com.aneb.probe.scoring.TokenBehaviorClassifier.BehaviorFinding
import com.aneb.probe.scoring.TokenBehaviorClassifier.RecTarget
import com.aneb.probe.scoring.TokenBehaviorClassifier.TestBehaviorTag
import com.aneb.probe.scoring.TokenBehaviorClassifier.WorkloadSignal
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * TokenBehaviorClassifier 双证据行为分类 + 建议输出单测（PROFILE_FRAMEWORK §2.5）。
 * 覆盖：pain=weight×(100−subScore) 强度、satisfied（子分≥良级）、多标签并存/单标、
 * D1 设计缺省不发下行标、按强度降序、建议行只对命中标签输出 + 未满足标注。
 */
class TokenBehaviorClassifierTest {

    private val mm = AqsScorer.WEIGHTS_TOKEN_MM

    private fun perfect(): MutableMap<String, Double> =
        mm.keys.associateWith { 100.0 }.toMutableMap()

    private fun findingOf(list: List<BehaviorFinding>, tag: TestBehaviorTag) = list.single { it.tag == tag }

    // ---------- 多模态典型：上行突发 + 下行大带宽 + 稳定性 ----------

    @Test
    fun `multimodal workload emits uplink downlink stability with pain-weighted intensity`() {
        val sub = perfect().apply {
            put("U1", 40.0) // pain = 0.15×60 = 9.0
            put("D1", 70.0) // pain = 0.15×30 = 4.5
        }
        val wl = WorkloadSignal(
            uplinkBytesPerRound = 12L * 1024 * 1024,
            downlinkMediaBytes = 15L * 1024 * 1024,
            longStreamOrContinuous = true,
            tokenStreamLen = 600,
        )
        val out = TokenBehaviorClassifier.classify(sub, mm, wl)
        val tags = out.map { it.tag }.toSet()
        assertEquals(setOf(TestBehaviorTag.UPLINK_BURST, TestBehaviorTag.DOWNLINK_BANDWIDTH, TestBehaviorTag.STABILITY), tags)

        val up = findingOf(out, TestBehaviorTag.UPLINK_BURST)
        val dn = findingOf(out, TestBehaviorTag.DOWNLINK_BANDWIDTH)
        // totalPain = 9.0 + 4.5 = 13.5
        assertEquals(9.0 / 13.5, up.intensity, 1e-9)
        assertEquals(4.5 / 13.5, dn.intensity, 1e-9)
        assertFalse("U1=40<70 → 未满足", up.satisfiedByNetwork)
        assertTrue("D1=70≥70 → 满足", dn.satisfiedByNetwork)
        // 稳定性绑定 T2/T3/N2 全满分 → intensity 0、满足
        val st = findingOf(out, TestBehaviorTag.STABILITY)
        assertEquals(0.0, st.intensity, 1e-9)
        assertTrue(st.satisfiedByNetwork)
    }

    @Test
    fun `findings sorted by intensity descending`() {
        val sub = perfect().apply { put("U1", 40.0); put("D1", 70.0) }
        val wl = WorkloadSignal(
            uplinkBytesPerRound = 12L * 1024 * 1024,
            downlinkMediaBytes = 15L * 1024 * 1024,
            longStreamOrContinuous = true,
        )
        val out = TokenBehaviorClassifier.classify(sub, mm, wl)
        assertEquals(TestBehaviorTag.UPLINK_BURST, out.first().tag) // 强度最高在前
        val intensities = out.map { it.intensity }
        assertEquals(intensities.sortedDescending(), intensities)
    }

    // ---------- 纯文本典型：仅低时延单标 ----------

    @Test
    fun `text workload emits only low latency`() {
        val txt = AqsScorer.WEIGHTS_TOKEN_TXT
        val sub = txt.keys.associateWith { 100.0 }.toMutableMap().apply {
            put("T1", 50.0) // pain = 0.25×50 = 12.5
            put("N1", 80.0) // pain = 0.15×20 = 3.0
        }
        val wl = WorkloadSignal(shortContextMultiTurn = true, toolLoopRounds = 3)
        val out = TokenBehaviorClassifier.classify(sub, txt, wl)
        assertEquals(listOf(TestBehaviorTag.LOW_LATENCY), out.map { it.tag })
        val ll = out.single()
        // totalPain = 12.5 + 3.0 = 15.5，绑定=(T1+N1)=全部 → intensity 1.0
        assertEquals(1.0, ll.intensity, 1e-9)
        assertFalse("T1=50<70 → 未满足", ll.satisfiedByNetwork)
    }

    // ---------- 峰均比高也触发上行突发（即使字节未达 10MB）----------

    @Test
    fun `high peak-to-mean ratio triggers uplink burst`() {
        val sub = perfect()
        val wl = WorkloadSignal(uplinkBytesPerRound = 1L * 1024 * 1024, peakToMeanRatio = 4.0)
        val out = TokenBehaviorClassifier.classify(sub, mm, wl)
        assertEquals(setOf(TestBehaviorTag.UPLINK_BURST), out.map { it.tag }.toSet())
    }

    // ---------- 设计缺省：D1 不在权重表则不发下行标 ----------

    @Test
    fun `downlink tag suppressed when d1 not in weight table`() {
        val txt = AqsScorer.WEIGHTS_TOKEN_TXT // 无 D1
        val sub = txt.keys.associateWith { 100.0 }
        val wl = WorkloadSignal(downlinkMediaBytes = 50L * 1024 * 1024)
        val out = TokenBehaviorClassifier.classify(sub, txt, wl)
        assertTrue("TXT 表无 D1 → 不发下行标", out.none { it.tag == TestBehaviorTag.DOWNLINK_BANDWIDTH })
    }

    // ---------- 无工作量证据 → 无标签 ----------

    @Test
    fun `no workload evidence yields no findings`() {
        val out = TokenBehaviorClassifier.classify(perfect(), mm, WorkloadSignal())
        assertTrue(out.isEmpty())
    }

    @Test
    fun `zero total pain yields zero intensity not divide by zero`() {
        val out = TokenBehaviorClassifier.classify(
            perfect(), mm,
            WorkloadSignal(uplinkBytesPerRound = 20L * 1024 * 1024),
        )
        assertEquals(1, out.size)
        assertEquals(0.0, out.single().intensity, 1e-12)
        assertTrue(out.single().satisfiedByNetwork)
    }

    // ---------- 建议输出：只对命中标签、未满足标注 ----------

    @Test
    fun `recommend outputs one line per hit tag with sla percentile and unmet marker`() {
        val sub = perfect().apply { put("U1", 40.0); put("D1", 90.0) }
        val wl = WorkloadSignal(
            uplinkBytesPerRound = 12L * 1024 * 1024,
            downlinkMediaBytes = 15L * 1024 * 1024,
        )
        val out = TokenBehaviorClassifier.classify(sub, mm, wl)
        val targets = mapOf(
            "U1" to RecTarget("上行", 5.0, "Mbps", higherBetter = true),
            "D1" to RecTarget("下行", 8.0, "Mbps", higherBetter = true),
        )
        val lines = TokenBehaviorClassifier.recommend(out, targets)
        assertEquals(2, lines.size)
        val upLine = lines.single { it.startsWith("上行突发") }
        assertTrue(upLine.contains("上行≥5Mbps 达 95%"))
        assertTrue("U1 未满足应标注", upLine.contains("（本次未满足）"))
        val dnLine = lines.single { it.startsWith("下行大带宽") }
        assertTrue(dnLine.contains("下行≥8Mbps 达 95%"))
        assertFalse("D1=90≥70 满足，不应标注未满足", dnLine.contains("（本次未满足）"))
    }
}
