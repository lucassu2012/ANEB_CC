package com.aneb.probe.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * [AiScenarioAdvisor]（BASIC_NETWORK facet4 `ai_scenario_fitness` 模板）锚定：
 * 门限**只**来自 TOKEN_EXPERIENCE facet2（INV-3——改 profile 门限本测试自动跟随，
 * 不锚定具体数字），判定语义 = 任一实测未达标→不适合；全达标→适合；无否定证据但缺测→null。
 */
class AiScenarioAdvisorTest {

    private fun verdictOf(code: String, vs: List<AiScenarioAdvisor.Verdict>) =
        vs.first { it.code == code }

    @Test
    fun `全指标优良_六场景全部适合`() {
        // 取自 profile 的良锚上界内：rtt<N1.good, jitter<N2.good, up/down 超所有 band 良锚
        val vs = AiScenarioAdvisor.advise(downMbps = 400.0, upMbps = 200.0, rttMs = 20.0, jitterMs = 3.0)
        assertEquals(6, vs.size)
        assertTrue("全指标优良应全部适合", vs.all { it.suitable == true })
    }

    @Test
    fun `上行不足_大上行场景不适合_纯文本仍适合`() {
        // up=10：< U1 100MB band 良锚(15) → TK-4 不适合；< 10MB band(12) → TK-3 不适合；
        // ≥ MB band(8) → TK-2 适合；TK-1 无上行需求不受影响
        val vs = AiScenarioAdvisor.advise(downMbps = 400.0, upMbps = 10.0, rttMs = 20.0, jitterMs = 3.0)
        assertEquals(false, verdictOf("TK-4", vs).suitable)
        assertEquals(false, verdictOf("TK-3", vs).suitable)
        assertEquals(true, verdictOf("TK-2", vs).suitable)
        assertEquals(true, verdictOf("TK-1", vs).suitable)
    }

    @Test
    fun `高时延_低时延场景不适合_下行场景不受影响`() {
        val vs = AiScenarioAdvisor.advise(downMbps = 400.0, upMbps = 200.0, rttMs = 150.0, jitterMs = 3.0)
        assertEquals(false, verdictOf("TK-1", vs).suitable)
        assertEquals(false, verdictOf("TK-6", vs).suitable)
        assertEquals(true, verdictOf("TK-5", vs).suitable)
    }

    @Test
    fun `缺测下行_下行场景无法判定而非否定_R10`() {
        val vs = AiScenarioAdvisor.advise(downMbps = null, upMbps = 200.0, rttMs = 20.0, jitterMs = 3.0)
        assertNull("下行未测 → TK-5 无法判定", verdictOf("TK-5", vs).suitable)
        assertNull("下行未测 → TK-3 无法判定（上行达标无否定证据）", verdictOf("TK-3", vs).suitable)
        assertEquals(true, verdictOf("TK-1", vs).suitable)
    }

    @Test
    fun `缺测但另一实测已否定_仍判不适合`() {
        // 下行缺测 + 上行仅 1（< 10MB band 良锚）→ TK-3 有否定证据 → 不适合（缺测不阻断否定）
        val vs = AiScenarioAdvisor.advise(downMbps = null, upMbps = 1.0, rttMs = 20.0, jitterMs = 3.0)
        assertEquals(false, verdictOf("TK-3", vs).suitable)
    }

    @Test
    fun `需求串含实测对照标记`() {
        val vs = AiScenarioAdvisor.advise(downMbps = 400.0, upMbps = 10.0, rttMs = 20.0, jitterMs = 3.0)
        val tk4 = verdictOf("TK-4", vs)
        assertTrue("需求串应含未达标记 ✗", tk4.requirement.contains("✗"))
        assertTrue("需求串应含实测值", tk4.requirement.contains("10.0"))
    }
}
