package com.aneb.probe.ui

import com.aneb.probe.engine.VoiceRunner
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * facet3 批 5a（T77）：[voiceLiveValue] 的完备性守卫。
 *
 * 判据**从产物导出**（清单会漏会过期，枚举漏不掉）：遍历 voice_realtime profile 的
 * `live[].source` 全体，逐一喂入映射函数——凡返回 null 的 source 即"profile 声明了、
 * 映射没接"的漏项（在屏上表现为该指标永远显示缺测 "—"，恰是 D-340 零读者形状的 UI 版）。
 */
class VoiceLiveSourceMappingTest {

    /** 全字段非 null 的样本：任何 source 在它上面取值都不该是 null。 */
    private fun fullSample() = VoiceRunner.Sample(
        phase = VoiceRunner.Phase.Done,
        rttMs = 46.4, jitterMs = 2.5,
        upFrameJitterMs = 3.1, downFrameJitterMs = 7.9,
        mouthEarBudgetMs = 96.0,
        framesSent = 150, framesRecv = 652, progress = 1f,
    )

    @Test
    fun `voice profile live 的每个 source 在映射里都有分支（从产物导出，非手写清单）`() {
        val live = TestModeProfiles.ALL.first { it.id == "voice_realtime" }.live
        assertTrue("voice profile 应至少声明一个动态指标", live.isNotEmpty())
        val s = fullSample()
        for (m in live) {
            assertNotNull(
                "live source `${m.source}`（指标 ${m.id}/${m.label}）在 voiceLiveValue 无分支——" +
                    "profile 声明了它而映射没接，屏上将永远显示缺测",
                voiceLiveValue(s, m.source),
            )
        }
    }

    @Test
    fun `派生 frameJitterMs 取上下行 max（M1 同款取法）`() {
        assertEquals(7.9, voiceLiveValue(fullSample(), "voice.frameJitterMs")!!, 1e-9)
    }

    @Test
    fun `派生 frameJitterMs 单边缺测取有的那边（有一半证据不等于没有证据）`() {
        val s = fullSample().copy(downFrameJitterMs = null)
        assertEquals(3.1, voiceLiveValue(s, "voice.frameJitterMs")!!, 1e-9)
    }

    @Test
    fun `派生 frameJitterMs 双边缺测才是 null（R-10）`() {
        val s = fullSample().copy(upFrameJitterMs = null, downFrameJitterMs = null)
        assertNull(voiceLiveValue(s, "voice.frameJitterMs"))
    }

    @Test
    fun `sample 为 null 时一切 source 均缺测`() {
        assertNull(voiceLiveValue(null, "rttMs"))
    }

    @Test
    fun `未知 source 返回 null 而非抛异常（组件将其渲染为缺测，守卫在完备性测试抓）`() {
        assertNull(voiceLiveValue(fullSample(), "no_such_source"))
    }
}
