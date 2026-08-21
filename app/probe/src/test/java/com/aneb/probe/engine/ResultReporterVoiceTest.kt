package com.aneb.probe.engine

import com.aneb.probe.data.ScenarioResultEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.scoring.AqsScorer
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * voice 摘要接线（大脑 08-22 裁定 voice 半）：`run.voice` 块的序列化守卫
 * （[ResultReporterThermalTest] 同款形状：块缺席/全值/null 透传三种语义 + 老形状）。
 */
class ResultReporterVoiceTest {

    private fun scenario() = ScenarioResultEntity(
        runId = "run-1", profileId = "s1_chat", profileVersion = "1.0.0",
        repeatIndex = 0, orderIndex = 0, startedAtNanos = 0L, endedAtNanos = 1L,
        validity = "valid", invalidReasons = "",
        t1TtftMs = null, t1Grade = null, t2ItlP95Ms = null, t2Grade = null,
        t2ItlP95InclCoalescedMs = null, t3StallRate = null, t3Grade = null,
        t3StallRateInclResume = null, t4SevereStallRate = null, t4Grade = null,
        t5ResumeP95Ms = null, n1RttP50Ms = 20.0, n1Grade = "excellent",
        n2JitterMs = 3.0, n2Grade = "excellent", u1GoodputMbps = 50.0, u1Grade = "excellent",
        u1GoodputExclSlowStartMbps = null, u2ToolLoopP95Ms = null, u2Grade = null,
        d1GoodputMbps = null, d1Grade = null,
        seqGapCount = 0, seqDupCount = 0, lowConfidenceKpis = "",
        offsetStartUs = 100L, offsetStartErrUs = 10L, offsetEndUs = 110L,
        offsetEndErrUs = 10L, offsetDriftPpm = 1.0, offsetSuspect = false,
        netTransport = "wifi", netCapabilities = "caps", netInterfaceName = "if0",
        serverObservedAddr = "203.0.113.7:8443", parseDurUsTotal = null, perEventParseUs = null,
    )

    private fun run() = TestRun(
        runId = "run-1", startedAtEpochMs = 1_752_000_000_000L,
        serverBase = "http://10.0.2.2:8443", mode = "quick",
        scenarioOrder = "s1_chat,s2_coding_agent,s3_multimodal", transport = "auto",
        kpiSet = "agent-qoe-kpi-v0.2", aqsVersion = "aqs-v0.1",
        profileVersions = "s1_chat@0.2.0", schemaVersion = "1.0",
        profileSource = "server", appVersionName = "0.3.0", appVersionCode = 1L,
        guardMetadata = null, aqsScore = 88.5, aqsLowConfidence = false,
        aqsVetoApplied = false, aqsNotComputableReason = null,
        status = "completed", reportStatus = null,
    )

    private fun body(voice: VoiceSummary.Voice? = null): String = ResultReporter.build(
        run = run(),
        scenarios = listOf(scenario() to ItlHistogram.of(emptyList())),
        aqs = AqsScorer.AqsResult(
            aqsVersion = "aqs-v0.1", kpiSetVersion = "agent-qoe-kpi-v0.2",
            score = 88.5, subScores = mapOf("T" to 90.0),
            vetoApplied = false, lowConfidence = false, notComputableReason = null,
        ),
        voice = voice,
    )

    @Test
    fun `voice 参数缺省 → wire 无 voice 键——老调用形状一字节不变`() {
        assertFalse(
            "param 默认 null 必须保持块缺席（=窗内无 Done 行或早于上线）",
            body().contains("\"voice\":"),
        )
    }

    @Test
    fun `v2 全值行六键逐字落 wire——含溯源 ts_epoch_ms`() {
        val b = body(
            VoiceSummary.Voice(
                caliber = "server-sim-v2", m7MaxFrameGapMs = 180.5,
                mouthEarProxyP50Ms = 412.0, lowConfidence = false,
                turnsOk = 12, tsEpochMs = 1_783_943_000_000L,
            ),
        )
        assertTrue(b.contains("\"caliber\":\"server-sim-v2\""))
        assertTrue(b.contains("\"m7_max_frame_gap_ms\":180.5"))
        assertTrue(b.contains("\"mouth_ear_proxy_p50_ms\":412.0"))
        assertTrue(b.contains("\"low_confidence\":false"))
        assertTrue(b.contains("\"turns_ok\":12"))
        assertTrue(b.contains("\"ts_epoch_ms\":1783943000000"))
    }

    @Test
    fun `v1 形状行 → 可空四键 JsonNull 真落 wire——键在值 null 不是键消失（R-10）`() {
        val b = body(
            VoiceSummary.Voice(
                caliber = null, m7MaxFrameGapMs = null, mouthEarProxyP50Ms = null,
                lowConfidence = false, turnsOk = null, tsEpochMs = 1_783_943_000_000L,
            ),
        )
        assertTrue(b.contains("\"caliber\":null"))
        assertTrue(b.contains("\"m7_max_frame_gap_ms\":null"))
        assertTrue(b.contains("\"mouth_ear_proxy_p50_ms\":null"))
        assertTrue(b.contains("\"turns_ok\":null"))
        assertTrue("溯源键任何形状下都非 null", b.contains("\"ts_epoch_ms\":1783943000000"))
    }
}
