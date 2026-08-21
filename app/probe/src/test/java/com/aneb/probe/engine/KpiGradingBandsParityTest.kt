package com.aneb.probe.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * [KpiGrading.bands] 与 [KpiGrading.grade] 的**边界对拍**（T62 批 2）。
 *
 * bands() 是给展示层画门限微刻度的只读出口，它的三个数与 grade() 各分支的字面量是
 * **同一对象里的两份副本**——没有共享常量把它们拴在一起（刻意不重构 grade()：那是
 * 测量语义的权威实现，最小改动优先）。本测试就是那根拴绳：**对每个 id 断言 grade()
 * 恰在 bands() 声明的边界处翻转档位**。改任何一边的字面量而不改另一边，这里当场红。
 *
 * （改门限本身仍属测量语义变更：DECISION_LOG + 红队 + spec §5.2 同步——本测试红了
 * 不等于"改这里让它绿"，先问门限是不是真的要动。）
 */
class KpiGradingBandsParityTest {

    private val eps = 1e-9

    @Test
    fun `每个低者优 id 的 grade 恰在 bands 边界处翻转`() {
        for (id in listOf("T1", "T2", "T3", "N1", "N2", "U2", "C1", "C2")) {
            val b = KpiGrading.bands(id)!!
            assertTrue("$id 应为低者优", b.lowerBetter)
            assertEquals("$id 边界内侧应为优", KpiGrading.EXCELLENT, KpiGrading.grade(id, b.a - b.a * eps))
            assertEquals("$id v==a 应翻为良", KpiGrading.GOOD, KpiGrading.grade(id, b.a))
            assertEquals("$id v==b 应翻为可", KpiGrading.FAIR, KpiGrading.grade(id, b.b))
            assertEquals("$id v==c 仍为可（<=c）", KpiGrading.FAIR, KpiGrading.grade(id, b.c))
            assertEquals("$id c 外侧应为差", KpiGrading.POOR, KpiGrading.grade(id, b.c + b.c * eps))
        }
    }

    @Test
    fun `T4 的优等于恰零特例与 bands 共存`() {
        val b = KpiGrading.bands("T4")!!
        assertEquals(0.0, b.a, 0.0)
        assertEquals(KpiGrading.EXCELLENT, KpiGrading.grade("T4", 0.0))
        assertEquals("恰 0 之外立即为良", KpiGrading.GOOD, KpiGrading.grade("T4", 1e-6))
        assertEquals(KpiGrading.FAIR, KpiGrading.grade("T4", b.b))
        assertEquals(KpiGrading.FAIR, KpiGrading.grade("T4", b.c))
        assertEquals(KpiGrading.POOR, KpiGrading.grade("T4", b.c + 1e-6))
    }

    @Test
    fun `高者优 id 的 grade 恰在 bands 边界处翻转`() {
        for (id in listOf("U1", "D1")) {
            val b = KpiGrading.bands(id)!!
            assertTrue("$id 应为高者优", !b.lowerBetter)
            assertEquals("$id a 外侧应为优", KpiGrading.EXCELLENT, KpiGrading.grade(id, b.a + b.a * eps))
            assertEquals("$id v==a 应翻为良（>a 才优）", KpiGrading.GOOD, KpiGrading.grade(id, b.a))
            assertEquals("$id v==b 仍为良（>=b）", KpiGrading.GOOD, KpiGrading.grade(id, b.b))
            assertEquals("$id b 内侧应为可", KpiGrading.FAIR, KpiGrading.grade(id, b.b - b.b * eps))
            assertEquals("$id v==c 仍为可（>=c）", KpiGrading.FAIR, KpiGrading.grade(id, b.c))
            assertEquals("$id c 内侧应为差", KpiGrading.POOR, KpiGrading.grade(id, b.c - b.c * eps))
        }
    }

    @Test
    fun `无门限 id 的 bands 为 null 且集合与 grade 一致`() {
        assertNull("T5 无门限", KpiGrading.bands("T5"))
        assertNull("未知 id 无门限", KpiGrading.bands("X9"))
        // bands 有值的每个 id，grade 也必须真的分级（防 bands 多给）
        for (id in listOf("T1", "T2", "T3", "T4", "N1", "N2", "U1", "U2", "C1", "C2", "D1")) {
            assertTrue("bands($id) 应非空", KpiGrading.bands(id) != null)
            assertTrue("grade($id) 应真的分级", KpiGrading.grade(id, KpiGrading.bands(id)!!.b) != null)
        }
    }
}
