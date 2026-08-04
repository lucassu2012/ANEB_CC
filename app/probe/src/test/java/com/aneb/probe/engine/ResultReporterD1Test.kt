package com.aneb.probe.engine

import com.aneb.probe.data.ScenarioResultEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.scoring.AqsScorer
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * D1 半成品补齐序列化单测（T47 批①，D-468/D-469）：KpiCalculator 早已算出 d1GoodputMbps，
 * 但此前 ResultReporter/kpiValuePairs() 从未接线——"契约里要打分，wire 上从未出现"（spec §8.1）。
 * 本测锚定 d1_goodput_mbps/d1_grade 真的出现在 wire body 里，闭环验证不重蹈"算了但没上线"。
 */
class ResultReporterD1Test {

    private fun scenario(d1: Double? = null, d1Grade: String? = null) = ScenarioResultEntity(
        runId = "run-1", profileId = "s3_multimodal", profileVersion = "1.0.0",
        repeatIndex = 0, orderIndex = 0, startedAtNanos = 0L, endedAtNanos = 1L,
        validity = "valid", invalidReasons = "",
        t1TtftMs = null, t1Grade = null, t2ItlP95Ms = null, t2Grade = null,
        t2ItlP95InclCoalescedMs = null, t3StallRate = null, t3Grade = null,
        t3StallRateInclResume = null, t4SevereStallRate = null, t4Grade = null,
        t5ResumeP95Ms = null, n1RttP50Ms = 20.0, n1Grade = "excellent",
        n2JitterMs = 3.0, n2Grade = "excellent", u1GoodputMbps = 50.0, u1Grade = "excellent",
        u1GoodputExclSlowStartMbps = null, u2ToolLoopP95Ms = null, u2Grade = null,
        d1GoodputMbps = d1, d1Grade = d1Grade,
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

    private fun body(entity: ScenarioResultEntity): String = ResultReporter.build(
        run = run(),
        scenarios = listOf(entity to ItlHistogram.of(emptyList())),
        aqs = AqsScorer.AqsResult(
            aqsVersion = "aqs-v0.1", kpiSetVersion = "agent-qoe-kpi-v0.2",
            score = 88.5, subScores = mapOf("T" to 90.0),
            vetoApplied = false, lowConfidence = false, notComputableReason = null,
        ),
    )

    @Test
    fun `d1_goodput_mbps 与 d1_grade 真的出现在 wire body 里`() {
        val b = body(scenario(d1 = 12.5, d1Grade = "fair"))
        assertTrue("d1_goodput_mbps 键必须存在", b.contains("\"d1_goodput_mbps\""))
        assertTrue(b.contains("\"d1_goodput_mbps\":12.5") || b.contains("\"d1_goodput_mbps\": 12.5"))
        assertTrue(b.contains("\"d1_grade\":\"fair\"") || b.contains("\"d1_grade\": \"fair\""))
    }

    @Test
    fun `d1 为 null 时键仍存在、值为 null（R-10：不可测不是缺键也不是 0）`() {
        val b = body(scenario(d1 = null, d1Grade = null))
        assertTrue("即使为 null，d1_goodput_mbps 键也必须存在（additive 字段恒写）",
            b.contains("\"d1_goodput_mbps\""))
        assertTrue(b.contains("\"d1_goodput_mbps\":null") || b.contains("\"d1_goodput_mbps\": null"))
        assertFalse("绝不用 0 顶替未测量（R-10）", b.contains("\"d1_goodput_mbps\":0"))
    }
}
