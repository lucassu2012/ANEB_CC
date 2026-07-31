package com.aneb.probe.engine

import com.aneb.probe.data.ScenarioResultEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.scoring.AqsScorer
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * radio_ctx 上报体接线单测（RADIO_CONTEXT_WIRING_SPEC v1.0，D-367）：
 * - radioStale 非 null（导出运行过）→ `network_snapshot.radio` 八键齐备，不可得项 null；
 * - radioStale==null（wifi 场景 / v16 之前的历史行）→ **不写 radio 键**（规格 §2：
 *   不写全 null 壳），也绝不为历史行编造 stale 值。
 */
class ResultReporterRadioTest {

    private fun scenario(
        transport: String,
        stale: Boolean? = null,
        rsrp: Double? = null,
        pci: Int? = null,
        sampledN: Int? = null,
    ) = ScenarioResultEntity(
        runId = "run-1", profileId = "s1_chat", profileVersion = "1.0.0",
        repeatIndex = 0, orderIndex = 0, startedAtNanos = 0L, endedAtNanos = 1L,
        validity = "valid", invalidReasons = "",
        t1TtftMs = 150.0, t1Grade = "excellent", t2ItlP95Ms = 80.0, t2Grade = "excellent",
        t2ItlP95InclCoalescedMs = null, t3StallRate = 0.0, t3Grade = "excellent",
        t3StallRateInclResume = null, t4SevereStallRate = 0.0, t4Grade = "excellent",
        t5ResumeP95Ms = null, n1RttP50Ms = 20.0, n1Grade = "excellent",
        n2JitterMs = 3.0, n2Grade = "excellent", u1GoodputMbps = 50.0, u1Grade = "excellent",
        u1GoodputExclSlowStartMbps = null, u2ToolLoopP95Ms = null, u2Grade = null,
        seqGapCount = 0, seqDupCount = 0, lowConfidenceKpis = "",
        offsetStartUs = 100L, offsetStartErrUs = 10L, offsetEndUs = 110L,
        offsetEndErrUs = 10L, offsetDriftPpm = 1.0, offsetSuspect = false,
        netTransport = transport, netCapabilities = "caps", netInterfaceName = "if0",
        serverObservedAddr = "203.0.113.7:8443", parseDurUsTotal = 1000L, perEventParseUs = 2.0,
        radioRat = if (stale != null) "NR" else null,
        radioRsrpDbm = rsrp,
        radioSinrDb = null,
        radioPci = pci,
        radioTac = null,
        radioArfcn = null,
        radioSampledN = sampledN,
        radioStale = stale,
    )

    private fun run() = TestRun(
        runId = "run-1", startedAtEpochMs = 1_752_000_000_000L,
        serverBase = "http://10.0.2.2:8443", mode = "quick",
        scenarioOrder = "s1_chat,s2_coding_agent,s3_multimodal", transport = "auto",
        kpiSet = "agent-qoe-kpi-v0.2", aqsVersion = "aqs-v0.1",
        profileVersions = "s1_chat@0.2.0", schemaVersion = "1.0",
        profileSource = "server", appVersionName = "0.3.0", appVersionCode = 1L,
        guardMetadata = "private_dns_active=false", aqsScore = 88.5, aqsLowConfidence = false,
        aqsVetoApplied = false, aqsNotComputableReason = null,
        status = "completed", reportStatus = null,
    )

    private fun body(entity: ScenarioResultEntity): String = ResultReporter.build(
        run = run(),
        scenarios = listOf(entity to ItlHistogram.of(listOf(50.0, 80.0, 120.0))),
        aqs = AqsScorer.AqsResult(
            aqsVersion = "aqs-v0.1", kpiSetVersion = "agent-qoe-kpi-v0.2",
            score = 88.5, subScores = mapOf("T" to 90.0),
            vetoApplied = false, lowConfidence = false, notComputableReason = null,
        ),
    )

    @Test
    fun `蜂窝场景 radio 八键齐备且不可得项为 null`() {
        val b = body(scenario("cellular", stale = false, rsrp = -98.0, pci = 238, sampledN = 12))
        assertTrue(b.contains("\"radio\""))
        assertTrue(b.contains("\"rat\":\"NR\"") || b.contains("\"rat\": \"NR\""))
        assertTrue(b.contains("\"rsrp_dbm\":-98.0") || b.contains("\"rsrp_dbm\": -98.0"))
        assertTrue(b.contains("\"pci\":238") || b.contains("\"pci\": 238"))
        assertTrue(b.contains("\"sampled_n\":12") || b.contains("\"sampled_n\": 12"))
        assertTrue(b.contains("\"stale\":false") || b.contains("\"stale\": false"))
        // 不可得项显式 null，不是缺键也不是哨兵（R-10）
        assertTrue(b.contains("\"sinr_db\":null") || b.contains("\"sinr_db\": null"))
        assertTrue(b.contains("\"tac\":null") || b.contains("\"tac\": null"))
    }

    @Test
    fun `导出未运行时不写 radio 键`() {
        val b = body(scenario("wifi", stale = null))
        assertFalse("wifi/历史行不得携带 radio 键（规格 §2）", b.contains("\"radio\""))
    }
}
