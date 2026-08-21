package com.aneb.probe.ui

import com.aneb.probe.engine.LiveTelemetry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * facet3 批 5b：[tokenLiveValue] 的完备性守卫（[VoiceLiveSourceMappingTest] 模板同款）。
 *
 * 判据**从产物导出**：遍历 token_experience profile 的 `live[].source` 全体逐一喂入映射。
 * 另钉两处本面特有语义：`itlRecentMs` 是滑窗列表、映射取**最新一项**（strip 每 refreshMs
 * 采样自建波形窗）；计数器（stallCount）为 0 是**真实读数**而非 R-10 伪装——伪装指
 * "缺测冒充 0"，计数器从测量开始就在。
 */
class TokenLiveSourceMappingTest {

    /** 全字段非 null 的遥测：任何 source 在它上面取值都不该是 null。 */
    private fun fullTelemetry() = LiveTelemetry(
        rttMs = 44.5, jitterMs = 6.1, rsrp = -96, sinr = 8, rat = "NR_SA",
        upMbps = 9.8, liveUpMbps = 10.2,
        ttftMs = 210.0, itlRecentMs = listOf(21.0, 35.5, 18.2), itlMedianMs = 22.4,
        stallCount = 1, tokensReceived = 480, tokenRatePerSec = 41.7,
        phase = "s2_coding_agent", subPhase = "token_stream", fraction = 0.6,
        aqsRunning = 82.3,
    )

    @Test
    fun `token profile live 的每个 source 在映射里都有分支（从产物导出，非手写清单）`() {
        val live = TestModeProfiles.ALL.first { it.id == "token_experience" }.live
        assertTrue("token_experience profile 应至少声明一个动态指标", live.isNotEmpty())
        val t = fullTelemetry()
        for (m in live) {
            assertNotNull(
                "live source `${m.source}`（指标 ${m.id}/${m.label}）在 tokenLiveValue 无分支——" +
                    "profile 声明了它而映射没接，屏上将永远显示缺测",
                tokenLiveValue(t, m.source),
            )
        }
    }

    @Test
    fun `itlRecentMs 取滑窗最新一项——strip 逐拍采样自建波形`() {
        assertEquals(18.2, tokenLiveValue(fullTelemetry(), "itlRecentMs")!!, 1e-9)
        assertNull("空窗（未开始流式）应为缺测", tokenLiveValue(LiveTelemetry.EMPTY, "itlRecentMs"))
    }

    @Test
    fun `计数器的 0 是真实读数不是伪装——与可空指标的缺测区分开`() {
        // EMPTY 遥测：可空指标（rttMs 等）缺测 → null；计数器（stallCount）从测量开始就在 → 0.0
        assertNull(tokenLiveValue(LiveTelemetry.EMPTY, "rttMs"))
        assertEquals(0.0, tokenLiveValue(LiveTelemetry.EMPTY, "stallCount")!!, 0.0)
    }

    @Test
    fun `未知 source 返回 null 而非抛异常（组件渲染为缺测，漏接由完备性测试抓）`() {
        assertNull(tokenLiveValue(fullTelemetry(), "no_such_field"))
    }
}
