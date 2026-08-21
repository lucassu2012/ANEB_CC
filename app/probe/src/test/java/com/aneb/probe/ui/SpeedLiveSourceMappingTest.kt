package com.aneb.probe.ui

import com.aneb.probe.engine.SpeedRunner
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
