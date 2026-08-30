package com.aneb.probe.ui

import com.aneb.probe.engine.SpeedRunner
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * facet3 批 5b：[speedLiveValue] 的完备性守卫（[VoiceLiveSourceMappingTest] 模板同款）。
 *
 * 判据**从产物导出**：遍历 basic_network profile 的 `live[].source` 全体逐一喂入映射——
 * 凡返回 null 的 source 即"profile 声明了、映射没接"的漏项（屏上永远显示缺测 "—"，
 * D-340 零读者形状的 UI 版）。profile 将来加指标而映射漏接，本测试当场红。
 */
class SpeedLiveSourceMappingTest {

    // ── D-610 ②：空闲态仪表单位不得冒充某一相 ──────────────────────────────
    // 缺陷原状：`val unit = when { ... else -> "Mbps 上行" }`，phase==null 的空闲态落进
    // 「上行」⇒ 仪表读作「— Mbps 上行」，像有一次上行测量正待出数，实则什么都没开始。
    // 同屏 phaseLabel 当时已显式处理 null ⇒ 相邻两层一诚实一撒谎，而撒谎那层是大字。

    @Test
    fun `空闲未开始 —— 单位须说「尚未开始」,绝不冒充上行`() {
        assertEquals(
            "phase=null 且未运行＝什么都没开始；旧 else 分支会说「Mbps 上行」",
            "尚未开始",
            speedGaugeUnit(phase = null, peakDownMbps = 0f, running = false),
        )
    }

    @Test
    fun `空闲但已点开始 —— 说「准备中」,仍不冒充上行`() {
        assertEquals(
            "running=true 而 phase 尚未产生首个样本：是准备中，不是上行相",
            "准备中",
            speedGaugeUnit(phase = null, peakDownMbps = 0f, running = true),
        )
    }

    @Test
    fun `四个相位各有自己的文案（穷举 when 的回归钉）`() {
        // 逐个相位钉住，兼作「将来新增相位」的提醒：when(phase) 已穷举，
        // 新增枚举值会在**编译期**报错，而不是静默落进「Mbps 上行」——
        // 这条断言守的是文案本身，编译器守的是「不许再有兜底」。
        assertEquals("ms 时延", speedGaugeUnit(SpeedRunner.Phase.Ping, 0f, true))
        assertEquals("Mbps 下行", speedGaugeUnit(SpeedRunner.Phase.Download, 0f, true))
        assertEquals("Mbps 上行", speedGaugeUnit(SpeedRunner.Phase.Upload, 0f, true))
        assertEquals("Mbps 下行峰值", speedGaugeUnit(SpeedRunner.Phase.Done, 87.3f, false))
        assertEquals(
            "完成态无下行峰值时退上行峰值（既有行为，不在本次修改范围）",
            "Mbps 上行峰值",
            speedGaugeUnit(SpeedRunner.Phase.Done, 0f, false),
        )
    }

    /** 全字段非 null 的样本：任何 source 在它上面取值都不该是 null。 */
    private fun fullSample() = SpeedRunner.Sample(
        phase = SpeedRunner.Phase.Download,
        rttMs = 28.1, jitterMs = 4.2,
        upMbps = 11.6, downMbps = 87.3,
        progress = 0.5f,
        reqFailed = 0, reqTotal = 12,
        udpUnreturnedPct = 1.5, udpRttMs = 30.2,
    )

    @Test
    fun `basic profile live 的每个 source 在映射里都有分支（从产物导出，非手写清单）`() {
        val live = TestModeProfiles.ALL.first { it.id == "basic_network" }.live
        assertTrue("basic_network profile 应至少声明一个动态指标", live.isNotEmpty())
        val s = fullSample()
        for (m in live) {
            assertNotNull(
                "live source `${m.source}`（指标 ${m.id}/${m.label}）在 speedLiveValue 无分支——" +
                    "profile 声明了它而映射没接，屏上将永远显示缺测",
                speedLiveValue(s, m.source),
            )
        }
    }

    @Test
    fun `sample 为 null 时一切 source 均缺测`() {
        assertNull(speedLiveValue(null, "rttMs"))
        assertNull(speedLiveValue(null, "downMbps"))
    }

    @Test
    fun `未知 source 返回 null 而非抛异常（组件渲染为缺测，漏接由完备性测试抓）`() {
        assertNull(speedLiveValue(fullSample(), "no_such_field"))
    }
}
