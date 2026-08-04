package com.aneb.probe.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * [KpiGrading.grade] 门限边界锚定（agent-qoe-kpi v0.1 5.2）——守 8 个驱动用户可见 优/良/可/差
 * chip 的门限（T1/T2/T3/T4/N1/N2/U1/U2）**两侧边界**，防有人改动门限数字/翻转比较符静默上线。
 * 低者优严格 `<优/<良/<=可`、高者优 U1 `>优/>=良/>=可`、T4 特例 0=优——每处都逐点钉死。
 * （C1/C2 已由 ContinuityMathTest 覆盖，此处不重复。）
 */
class KpiGradingTest {

    private fun g(id: String, v: Double?) = KpiGrading.grade(id, v)

    // ---- 低者优 KPI：v<a 优 / v<b 良 / v<=c 可 / 否则差（边界归属钉死）----

    @Test fun `T1 boundaries 200 500 1000`() {
        assertEquals("excellent", g("T1", 199.9))
        assertEquals("良档下边界=门限值本身（<优 严格）", "good", g("T1", 200.0))
        assertEquals("good", g("T1", 499.9))
        assertEquals("fair", g("T1", 500.0))
        assertEquals("可档含上边界（<=可）", "fair", g("T1", 1000.0))
        assertEquals("poor", g("T1", 1000.01))
    }

    @Test fun `T2 boundaries 100 200 400`() {
        assertEquals("excellent", g("T2", 99.9))
        assertEquals("good", g("T2", 100.0))
        assertEquals("fair", g("T2", 200.0))
        assertEquals("fair", g("T2", 400.0))
        assertEquals("poor", g("T2", 400.01))
    }

    @Test fun `T3 boundaries 0005 002 005`() {
        assertEquals("excellent", g("T3", 0.004))
        assertEquals("good", g("T3", 0.005))
        assertEquals("fair", g("T3", 0.02))
        assertEquals("fair", g("T3", 0.05))
        assertEquals("poor", g("T3", 0.051))
    }

    @Test fun `T4 special zero-is-excellent then 0002 001`() {
        assertEquals("优仅当恰为 0（5.2 特例）", "excellent", g("T4", 0.0))
        assertEquals("极小正值即降良（非优）", "good", g("T4", 0.0001))
        assertEquals("good", g("T4", 0.0019))
        assertEquals("fair", g("T4", 0.002))
        assertEquals("fair", g("T4", 0.01))
        assertEquals("poor", g("T4", 0.0101))
    }

    @Test fun `N1 boundaries 30 60 100`() {
        assertEquals("excellent", g("N1", 29.9))
        assertEquals("good", g("N1", 30.0))
        assertEquals("fair", g("N1", 60.0))
        assertEquals("fair", g("N1", 100.0))
        assertEquals("poor", g("N1", 100.1))
    }

    @Test fun `N2 boundaries 10 30 80`() {
        assertEquals("excellent", g("N2", 9.9))
        assertEquals("good", g("N2", 10.0))
        assertEquals("fair", g("N2", 30.0))
        assertEquals("fair", g("N2", 80.0))
        assertEquals("poor", g("N2", 80.1))
    }

    @Test fun `U2 boundaries 150 300 600`() {
        assertEquals("excellent", g("U2", 149.9))
        assertEquals("good", g("U2", 150.0))
        assertEquals("fair", g("U2", 300.0))
        assertEquals("fair", g("U2", 600.0))
        assertEquals("poor", g("U2", 600.1))
    }

    // ---- 高者优 U1（Mbps）：v>20 优 / v>=5 良 / v>=1 可 / 否则差 ----

    @Test fun `U1 higher-better boundaries 20 5 1`() {
        assertEquals("优严格 >20", "excellent", g("U1", 20.01))
        assertEquals("门限值本身归良（>优 严格）", "good", g("U1", 20.0))
        assertEquals("良含下边界（>=良）", "good", g("U1", 5.0))
        assertEquals("fair", g("U1", 4.99))
        assertEquals("可含下边界（>=可）", "fair", g("U1", 1.0))
        assertEquals("poor", g("U1", 0.99))
    }

    // ---- 高者优 D1（Mbps，T47 批①/D-468：门限复用 AqsScorer.D1_ANCHORS/basic_network
    //      D1 QualityTarget 既有取值 25/8/2，非新造）：v>25 优 / v>=8 良 / v>=2 可 / 否则差 ----

    @Test fun `D1 higher-better boundaries 25 8 2`() {
        assertEquals("优严格 >25", "excellent", g("D1", 25.01))
        assertEquals("门限值本身归良（>优 严格）", "good", g("D1", 25.0))
        assertEquals("良含下边界（>=良）", "good", g("D1", 8.0))
        assertEquals("fair", g("D1", 7.99))
        assertEquals("可含下边界（>=可）", "fair", g("D1", 2.0))
        assertEquals("poor", g("D1", 1.99))
    }

    // ---- R-10 / 无门限 KPI ----

    @Test fun `null value never graded (R-10)`() {
        assertNull("失败/缺失样本不发分级", g("T1", null))
        assertNull(g("U1", null))
    }

    @Test fun `T5 and unknown ids have no thresholds`() {
        assertNull("T5 无门限恒 null", g("T5", 123.0))
        assertNull("未知 id → null", g("XYZ", 5.0))
    }
}
