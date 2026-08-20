package com.aneb.probe.ui

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import com.aneb.probe.ui.components.ResIcon
import com.aneb.probe.ui.components.StResItem
import com.aneb.probe.ui.components.StResults
import com.aneb.probe.ui.theme.AnebTheme
import com.aneb.probe.ui.theme.Grade
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * **结果大数字行（`StResults`）的渲染层红线**——承 `RenderRedlineTest` 的骨架与理由，
 * 覆盖它没覆盖的那个组件（现有 9 条测的是 `KpiLine`/`ClaimScopeFooter`/`RunningGauge`/
 * `HalfGauge`）。
 *
 * **为什么这个组件值得单测**：它是**简洁结果页最显眼的三个数**（响应/上传/卡顿），
 * 而"缺失怎么显示"这件事**写在调用方的内联表达式里**（`ResultScreen`：
 * `t1?.value?.let { "${it.roundToInt()}" } ?: "—"`，且缺失时把 `unit` 一并置空）。
 * 那正是 D-529/`HalfGauge ?: 0` 那个先例的形状：**纯函数层看不见的 `?:`**。
 * 这里从组件侧钉住"喂进来什么就必须原样渲染出来、绝不把缺失变成 0"。
 *
 * 另一条**位置**断言承 D-538：三列的顺序（响应→上传→卡顿）本身是语义——读者按位置认列，
 * 换序等于换了读法，而"有没有"型断言插头插尾都过。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class StResultsRenderTest {

    @get:Rule
    val compose = createComposeRule()

    /** 与 `ResultScreen` 简洁视图同构的三列；`value`/`unit` 按调用方口径构造。 */
    private fun items(
        t1: Double?,
        u1: Double?,
        stalls: Int?,
    ) = listOf(
        StResItem(ResIcon.Down, "响应", t1?.let { "${it.toInt()}" } ?: "—", if (t1 != null) "ms" else "", Grade.Excellent),
        StResItem(ResIcon.Up, "上传", u1?.let { "%.1f".format(it) } ?: "—", if (u1 != null) "Mbps" else "", Grade.Good),
        StResItem(ResIcon.Stall, "卡顿", stalls?.toString() ?: "—", if (stalls != null) "次" else "", null),
    )

    private fun render(list: List<StResItem>) {
        compose.setContent { AnebTheme { StResults(items = list) } }
    }

    @Test
    fun `三个数全缺失时渲染占位符而不是 0`() {
        render(items(t1 = null, u1 = null, stalls = null))
        // **4 个而不是 3 个**：三列的值各一处，**外加第三列 `grade = null` 时 GradeChip 也显
        // 占位符**（`GradeChip` 实现里 `grade == null -> "—"`，那是正确行为：分级未知同样
        // 按 R-10 显缺失而不是编一个档位）。初版我按"恰好 3 个"断言，实测 4 个——
        // **是断言写窄，不是产品错**（§5.1 坑 #2 同款，那里记的也正是"KPI 值一处、分级 chip
        // 一处"）。故这里断言"至少 3 个值占位符 + 允许分级占位符"，用下界而非等号。
        val placeholders = compose.onAllNodesWithText("—").fetchSemanticsNodes().size
        org.junit.Assert.assertTrue(
            "三列缺失至少应渲染 3 个占位符（含分级 chip 可能的第 4 个）；实测 $placeholders",
            placeholders >= 3,
        )
        // R-10：绝不能出现假 0（含 "0"/"0.0"/"0 次"）
        for (fake in listOf("0", "0.0", "0 次")) {
            assertEquals(
                "缺失不得渲染成 $fake —— 假 0 会把'没测出来'读成'测出来是 0'（R-10）",
                0, compose.onAllNodesWithText(fake).fetchSemanticsNodes().size,
            )
        }
    }

    @Test
    fun `自证检测器：真实的 0 会被上一条的判据抓到`() {
        // 0 是**合法测量值**（卡顿 0 次是好结果）。若上一条的"无 0"判据其实抓不到任何东西，
        // 它就是个永远绿的空守卫——这条用真实的 0 证明检测器会响（D-322 造反例，不改产品代码）。
        render(items(t1 = null, u1 = null, stalls = 0))
        assertEquals(
            "真实的 0 必须被同一判据看见，否则上一条是空守卫",
            1, compose.onAllNodesWithText("0").fetchSemanticsNodes().size,
        )
    }

    @Test
    fun `有值时照常渲染数字与单位——防止上一条被写成永远不显示数字`() {
        render(items(t1 = 35.0, u1 = 12.5, stalls = 2))
        compose.onNodeWithText("35").assertExists()
        compose.onNodeWithText("12.5").assertExists()
        compose.onNodeWithText("2").assertExists()
        compose.onNodeWithText("ms").assertExists()
        compose.onNodeWithText("Mbps").assertExists()
    }

    @Test
    fun `缺失时单位也一并省略——不留一个孤零零的 ms 让人以为测到了`() {
        render(items(t1 = null, u1 = 12.5, stalls = null))
        // 只有上传有值，故只应出现它的单位
        assertEquals("缺失列不得留下单位", 0, compose.onAllNodesWithText("ms").fetchSemanticsNodes().size)
        compose.onNodeWithText("Mbps").assertExists()
    }

    @Test
    fun `三列顺序即语义——响应在前、上传居中、卡顿在后（D-538 位置断言）`() {
        render(items(t1 = 35.0, u1 = 12.5, stalls = 2))
        val ys = listOf("响应", "上传", "卡顿").map {
            compose.onNodeWithText(it).fetchSemanticsNode().positionInRoot.y
        }
        assertEquals("三列都应渲染出来", 3, ys.size)
        // 纵向堆叠：y 严格递增即顺序正确。只断言"有没有"会漏掉换序（D-538）。
        for (i in 1 until ys.size) {
            org.junit.Assert.assertTrue(
                "第 $i 列应排在第 ${i - 1} 列之后（读者按位置认列，换序等于换读法）；实测 y=$ys",
                ys[i] > ys[i - 1],
            )
        }
    }
}
