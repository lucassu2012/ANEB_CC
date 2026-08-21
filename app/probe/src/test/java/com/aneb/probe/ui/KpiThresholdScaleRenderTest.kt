package com.aneb.probe.ui

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import com.aneb.probe.ui.theme.AnebTheme
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * 门限微刻度（T62 批 2）的渲染层红线——承 `RenderRedlineTest` 骨架。
 *
 * 守三件：①边界标签**真的**出现在渲染树（且是 KpiGrading.bands 的数字，不是 UI 写死的
 * 第二份——bands 改了标签就变，配合 `KpiGradingBandsParityTest` 拴住 grade）；②有值时
 * 落点标记在树里；③**缺失时无标记**（R-10：null 不落点——最左是"优"这个有意义的位置）。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class KpiThresholdScaleRenderTest {

    @get:Rule
    val compose = createComposeRule()

    private fun row(id: String, value: Double?, unit: String) = ResultFormat.KpiRow(
        id = id, label = "测试", value = value, unit = unit,
        grade = com.aneb.probe.engine.KpiGrading.grade(id, value), lowConfidence = false,
    )

    @Test
    fun `边界标签来自 bands 且真的渲染出来`() {
        compose.setContent { AnebTheme { KpiThresholdScale(row("T1", 350.0, "ms")) } }
        compose.onNodeWithText("200").assertExists()
        compose.onNodeWithText("500").assertExists()
        compose.onNodeWithText("1000").assertExists()
    }

    @Test
    fun `ratio 单位的边界显示为百分数`() {
        compose.setContent { AnebTheme { KpiThresholdScale(row("T3", 0.01, "ratio")) } }
        compose.onNodeWithText("0.5%").assertExists()
        compose.onNodeWithText("2%").assertExists()
        compose.onNodeWithText("5%").assertExists()
    }

    @Test
    fun `有值时落点标记在树里`() {
        compose.setContent { AnebTheme { KpiThresholdScale(row("T1", 350.0, "ms")) } }
        assertEquals(1, compose.onAllNodesWithTag("kpi-scale-marker-T1", useUnmergedTree = true)
            .fetchSemanticsNodes().size)
    }

    @Test
    fun `缺失时刻度仍在但绝无落点标记`() {
        compose.setContent { AnebTheme { KpiThresholdScale(row("T1", null, "ms")) } }
        compose.onNodeWithText("200").assertExists() // 刻度本身照显（读者知道量尺）
        assertEquals(
            "null 不落点：最左是'优'这个有意义的位置，缺失不能借用（R-10）",
            0, compose.onAllNodesWithTag("kpi-scale-marker-T1", useUnmergedTree = true)
                .fetchSemanticsNodes().size,
        )
    }

    @Test
    fun `无门限 id 整个刻度不渲染`() {
        compose.setContent { AnebTheme { KpiThresholdScale(row("T5", 800.0, "ms")) } }
        assertEquals(0, compose.onAllNodesWithTag("kpi-scale-marker-T5", useUnmergedTree = true)
            .fetchSemanticsNodes().size)
        // 没有任何边界标签（T5 无 bands）
        assertEquals(0, compose.onAllNodesWithText("200").fetchSemanticsNodes().size)
    }
}
