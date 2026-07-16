package com.aneb.probe.ui

import com.aneb.probe.scoring.AqsScorer
import com.aneb.probe.scoring.TokenBehaviorClassifier.TestBehaviorTag
import com.aneb.probe.scoring.TokenBehaviorClassifier.WorkloadSignal
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * TokenScoringBridge 单测：facet4 按模态选表 + facet2→facet4 建议目标投影（单一事实源，INV-3）。
 */
class TokenScoringBridgeTest {

    private val token = TestModeProfiles.TOKEN_EXPERIENCE

    // ---------- 按模态选表 ----------

    @Test
    fun `multimodal picks profile default mm table`() {
        assertEquals("WEIGHTS_TOKEN_MM", TokenScoringBridge.weightsTableIdFor(token, pureText = false))
    }

    @Test
    fun `pure text picks txt table`() {
        assertEquals("WEIGHTS_TOKEN_TXT", TokenScoringBridge.weightsTableIdFor(token, pureText = true))
    }

    @Test
    fun `resolved table id exists in aqs scorer registry`() {
        for (pt in listOf(true, false)) {
            val id = TokenScoringBridge.weightsTableIdFor(token, pureText = pt)
            assertTrue(AqsScorer.TOKEN_WEIGHT_TABLES.containsKey(id))
        }
    }

    @Test
    fun `unknown declared table throws`() {
        val bad = token.copy(scoring = token.scoring!!.copy(weightsTableId = "WEIGHTS_NOPE"))
        assertThrows(IllegalArgumentException::class.java) {
            TokenScoringBridge.weightsTableIdFor(bad, pureText = false)
        }
    }

    // ---------- facet2 → RecTarget 投影 ----------

    @Test
    fun `rec targets projected from facet2 good anchors single source`() {
        val targets = TokenScoringBridge.recTargets(token)
        // U1/D1 高者优、良锚来自 facet2（U1 good=5、D1 good=8）
        assertEquals(5.0, targets.getValue("U1").goodThreshold, 1e-9)
        assertTrue(targets.getValue("U1").higherBetter)
        assertEquals(8.0, targets.getValue("D1").goodThreshold, 1e-9)
        // T1/N1 低者优、良锚（T1 good=500、N1 good=60）
        assertEquals(500.0, targets.getValue("T1").goodThreshold, 1e-9)
        assertFalse(targets.getValue("T1").higherBetter)
        assertEquals(60.0, targets.getValue("N1").goodThreshold, 1e-9)
        // 无良锚的元数据项（TOKB/LOSS）不投影
        assertFalse(targets.containsKey("TOKB"))
        assertFalse(targets.containsKey("LOSS"))
    }

    @Test
    fun `rec target thresholds match profile metric specs exactly`() {
        val targets = TokenScoringBridge.recTargets(token)
        token.metricSpecs.filter { it.target.good != null }.forEach { m ->
            assertEquals("target for ${m.id}", m.target.good!!, targets.getValue(m.id).goodThreshold, 1e-12)
            assertEquals(m.unit, targets.getValue(m.id).unit)
        }
    }

    // ---------- 一步到位：分类 + 建议 ----------

    @Test
    fun `classify and recommend produces aligned findings and lines`() {
        val perfect = AqsScorer.WEIGHTS_TOKEN_MM.keys.associateWith { 100.0 }.toMutableMap()
        perfect["U1"] = 40.0 // 上行未满足
        val wl = WorkloadSignal(
            uplinkBytesPerRound = 12L * 1024 * 1024,
            downlinkMediaBytes = 15L * 1024 * 1024,
        )
        val (findings, lines) = TokenScoringBridge.classifyAndRecommend(token, perfect, pureText = false, workload = wl)
        assertEquals(findings.size, lines.size)
        assertTrue(findings.any { it.tag == TestBehaviorTag.UPLINK_BURST })
        val upLine = lines.single { it.startsWith("上行突发") }
        assertTrue("良锚门限来自 facet2（上行 good=5）", upLine.contains("上行 goodput≥5Mbps 达 95%"))
        assertTrue("U1=40 未满足", upLine.contains("（本次未满足）"))
    }

    @Test
    fun `pure text run uses txt weights so downlink tag suppressed`() {
        val txtPerfect = AqsScorer.WEIGHTS_TOKEN_TXT.keys.associateWith { 100.0 }
        val wl = WorkloadSignal(downlinkMediaBytes = 50L * 1024 * 1024, shortContextMultiTurn = true)
        val (findings, _) = TokenScoringBridge.classifyAndRecommend(token, txtPerfect, pureText = true, workload = wl)
        // TXT 表无 D1 → 即便下行媒体大也不发下行标；短上下文多轮 → 低时延标
        assertTrue(findings.none { it.tag == TestBehaviorTag.DOWNLINK_BANDWIDTH })
        assertTrue(findings.any { it.tag == TestBehaviorTag.LOW_LATENCY })
    }
}
