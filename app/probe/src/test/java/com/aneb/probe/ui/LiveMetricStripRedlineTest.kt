package com.aneb.probe.ui

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.assertIsDisplayed
import com.aneb.probe.ui.components.LiveMetricStrip
import com.aneb.probe.ui.theme.AnebTheme
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * T77 批 5a：[LiveMetricStrip] 的渲染树红线（[RenderRedlineTest] 同族第四件）。
 *
 * 钉两条：①**全缺测时树里必须是 "—" 且绝不出现假 0**（R-10 到渲染树——组件把
 * null 变 0 的话，映射层测试各自全绿也拦不住，D-501 HalfGauge 先例）；
 * ②**有值时数字真的渲染出来**（strip 不是装饰——值进树才算接线成功；本条同时防
 * "采样协程没跑、永远空转"这类静默失效——D-508 守卫要能失败的精神）。
 *
 * metrics 用 voice profile 的**真 live 清单**（不造合成清单——测的就是生产接线）。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class LiveMetricStripRedlineTest {

    @get:Rule
    val compose = createComposeRule()

    private val voiceLive = TestModeProfiles.ALL.first { it.id == "voice_realtime" }.live

    @Test
    fun `全缺测渲染为破折号且树中无假零`() {
        compose.setContent {
            AnebTheme { LiveMetricStrip(metrics = voiceLive, values = { null }) }
        }
        compose.mainClock.advanceTimeBy(500)
        compose.waitForIdle()
        // 每个指标一个 "—"
        assertEquals(voiceLive.size, compose.onAllNodesWithText("—").fetchSemanticsNodes().size)
        // 绝不出现假 0（整数/两位小数两种格式都查）
        for (zero in listOf("0", "0.0", "0.00")) {
            assertTrue(
                "缺测被渲染成 $zero ——R-10 假零（D-501 HalfGauge 先例的 strip 版）",
                compose.onAllNodesWithText(zero).fetchSemanticsNodes().isEmpty(),
            )
        }
        compose.onNodeWithTag("live_metric_strip").assertIsDisplayed()
    }

    @Test
    fun `有值时格式化数字真的进树（接线成功且采样协程在跑）`() {
        compose.setContent {
            AnebTheme {
                LiveMetricStrip(
                    metrics = voiceLive,
                    values = { source -> if (source == "rttMs") 46.4 else null },
                )
            }
        }
        compose.mainClock.advanceTimeBy(500)
        compose.waitForIdle()
        assertTrue(
            "rttMs=46.4 未渲染进树——采样或渲染链断了",
            compose.onAllNodesWithText("46.4").fetchSemanticsNodes().isNotEmpty(),
        )
        // 其余两个指标仍缺测
        assertEquals(voiceLive.size - 1, compose.onAllNodesWithText("—").fetchSemanticsNodes().size)
    }
}
