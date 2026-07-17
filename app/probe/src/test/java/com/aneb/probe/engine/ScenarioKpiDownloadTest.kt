package com.aneb.probe.engine

import com.aneb.probe.net.AnebClient
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * D1 采集链适配层锚定（download_burst → [ScenarioRunner.DownloadOutcome] →
 * [ScenarioKpi.buildKpiInput] → KpiInput.downloadResults；PROFILE_FRAMEWORK §2.4）。
 * 只测本层映射与计时端点判定；D1 统计口径由 KpiCalculatorD1S1Test 锚定（不重复）。
 */
class ScenarioKpiDownloadTest {

    private fun outcomeWith(vararg dls: ScenarioRunner.DownloadOutcome): ScenarioRunner.ScenarioOutcome {
        val profile = ScenarioProfile(profileId = "s3_multimodal", version = "0.3.0", phases = emptyList())
        val o = ScenarioRunner.ScenarioOutcome(profile, "s3_multimodal#0")
        o.downloads.addAll(dls)
        return o
    }

    private fun dl(
        index: Int,
        bytesRead: Long,
        endNanos: Long?,
        httpCode: Int? = 200,
        error: String? = null,
    ) = ScenarioRunner.DownloadOutcome(
        index = index,
        profileBytes = 10L * 1024 * 1024,
        result = AnebClient.DownloadResult(
            startNanos = 1_000_000_000L,
            bodyEndNanos = endNanos,
            bytesRead = bytesRead,
            httpCode = httpCode,
            error = error,
        ),
    )

    @Test
    fun `成功样本_时长为body排空端点_bytes取实收字节`() {
        val ok = dl(index = 0, bytesRead = 10_485_760L, endNanos = 2_000_000_000L)
        assertEquals(1_000_000_000L, ok.durationNanos)

        val input = ScenarioKpi.buildKpiInput(outcomeWith(ok), externalInvalidReasons = emptyList())
        assertEquals(1, input.downloadResults.size)
        val d = input.downloadResults.single()
        assertEquals(10_485_760L, d.bytes)
        assertEquals(1_000_000_000L, d.durationNanos)
        assertTrue(d.http2xx)
    }

    @Test
    fun `非2xx与中途IO错误_均判失败样本_时长null不进统计`() {
        val http500 = dl(index = 0, bytesRead = 0L, endNanos = 1_100_000_000L, httpCode = 500)
        val ioMidRead = dl(index = 1, bytesRead = 4_096L, endNanos = 1_200_000_000L, error = "java.io.IOException: reset")

        assertNull("非 2xx 失败样本时长必为 null（R-10）", http500.durationNanos)
        assertNull("中途 IO 错误失败样本时长必为 null（R-10）", ioMidRead.durationNanos)

        val input = ScenarioKpi.buildKpiInput(outcomeWith(http500, ioMidRead), externalInvalidReasons = emptyList())
        assertEquals(2, input.downloadResults.size)
        assertFalse(input.downloadResults[0].http2xx)
        assertFalse(input.downloadResults[1].http2xx)
        assertTrue(input.downloadResults.all { it.durationNanos == null })
    }

    @Test
    fun `实收字节与相位声明不匹配_判失败样本时长null(服务器能力合同字节校验)`() {
        // 静默短读(无 error、2xx、但 bytesRead < profileBytes 10MiB)→ fail-closed 记 null
        val shortRead = dl(index = 0, bytesRead = 4_096L, endNanos = 1_500_000_000L)
        assertNull("字节不匹配必须记 null 不记 0", shortRead.durationNanos)

        val input = ScenarioKpi.buildKpiInput(outcomeWith(shortRead), externalInvalidReasons = emptyList())
        assertTrue(input.downloadResults.single().durationNanos == null)
    }

    @Test
    fun `无download相位_downloadResults为空_不影响既有输入`() {
        val input = ScenarioKpi.buildKpiInput(outcomeWith(), externalInvalidReasons = emptyList())
        assertTrue(input.downloadResults.isEmpty())
    }
}
