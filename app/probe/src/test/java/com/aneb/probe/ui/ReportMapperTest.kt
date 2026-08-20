package com.aneb.probe.ui

import com.aneb.probe.data.ScenarioResultEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.scoring.Validity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * ReportMapper 纯映射单测：Room 落库实体 → ReportAnalyzer.RunSummary。
 * 锚定来源场景映射（T←S2 / N←S1 / U1←S3）、null 语义（R-10 绝不 0）、有效性降级。
 */
class ReportMapperTest {

    private fun run(
        runId: String = "r1",
        transport: String = "cellular",
        aqs: Double? = 72.0,
        lowConf: Boolean? = false,
        c1: Double? = null,
        epoch: Long = 1_000L,
        status: String = "completed",
    ) = TestRun(
        runId = runId,
        startedAtEpochMs = epoch,
        serverBase = "https://x",
        mode = "quick",
        scenarioOrder = "s1_chat,s2_coding_agent,s3_multimodal",
        transport = transport,
        kpiSet = "agent-qoe-kpi-v0.1",
        aqsVersion = "aqs-v0.1",
        profileVersions = "1.0.0",
        schemaVersion = "11",
        profileSource = "server",
        appVersionName = "0.1.0",
        appVersionCode = 1L,
        guardMetadata = null,
        aqsScore = aqs,
        aqsLowConfidence = lowConf,
        aqsVetoApplied = false,
        aqsNotComputableReason = null,
        status = status,
        reportStatus = "200",
        aqsV02C1DropRate = c1,
    )

    private fun scenario(
        profileId: String,
        t1: Double? = null,
        t2: Double? = null,
        t3: Double? = null,
        u1: Double? = null,
        n1: Double? = null,
        n2: Double? = null,
    ) = ScenarioResultEntity(
        runId = "r1",
        profileId = profileId,
        profileVersion = "1.0.0",
        repeatIndex = 0,
        orderIndex = 0,
        startedAtNanos = 0L,
        endedAtNanos = 1L,
        validity = "valid",
        invalidReasons = "",
        t1TtftMs = t1, t1Grade = null,
        t2ItlP95Ms = t2, t2Grade = null,
        t2ItlP95InclCoalescedMs = null,
        t3StallRate = t3, t3Grade = null,
        t3StallRateInclResume = null,
        t4SevereStallRate = null, t4Grade = null,
        t5ResumeP95Ms = null,
        n1RttP50Ms = n1, n1Grade = null,
        n2JitterMs = n2, n2Grade = null,
        u1GoodputMbps = u1, u1Grade = null,
        u1GoodputExclSlowStartMbps = null,
        u2ToolLoopP95Ms = null, u2Grade = null,
        seqGapCount = 0,
        seqDupCount = 0,
        offsetStartUs = null, offsetStartErrUs = null,
        offsetEndUs = null, offsetEndErrUs = null,
        offsetDriftPpm = null,
        offsetSuspect = false,
        netTransport = null,
        netCapabilities = null,
        netInterfaceName = null,
        serverObservedAddr = null,
        parseDurUsTotal = null,
        perEventParseUs = null,
    )

    @Test
    fun mapsMetricsFromSourceScenarios() {
        val scenarios = listOf(
            scenario("s1_chat", n1 = 30.0, n2 = 4.0),
            scenario("s2_coding_agent", t1 = 800.0, t2 = 120.0, t3 = 0.02),
            scenario("s3_multimodal", u1 = 12.5),
        )
        val s = ReportMapper.toRunSummary(run(), scenarios)
        assertEquals(800.0, s.ttftMs!!, 1e-9)
        assertEquals(120.0, s.itlP95Ms!!, 1e-9)
        assertEquals(0.02, s.stallRate!!, 1e-9)
        assertEquals(12.5, s.upMbps!!, 1e-9)
        assertEquals(30.0, s.rttMs!!, 1e-9)
        assertEquals(4.0, s.jitterMs!!, 1e-9)
        assertEquals(72.0, s.aqs!!, 1e-9)
        assertEquals("cellular", s.transport)
        assertNull("真机无 netem 剖面", s.netemProfile)
        assertNull("丢包未注入 → null（绝不 0）", s.lossPct)
        assertEquals(Validity.VALID, s.validity)
    }

    @Test
    fun medianAcrossRepeats() {
        // 取证模式同 profileId 多遍 → 中位数
        val scenarios = listOf(
            scenario("s2_coding_agent", t1 = 100.0),
            scenario("s2_coding_agent", t1 = 300.0),
            scenario("s2_coding_agent", t1 = 200.0),
        )
        val s = ReportMapper.toRunSummary(run(aqs = null), scenarios)
        assertEquals(200.0, s.ttftMs!!, 1e-9)
    }

    @Test
    fun allNullBecomesInvalid() {
        val s = ReportMapper.toRunSummary(run(aqs = null), emptyList())
        assertEquals(Validity.INVALID, s.validity)
        assertNull(s.ttftMs)
    }

    @Test
    fun lowConfidencePropagates() {
        val scenarios = listOf(scenario("s2_coding_agent", t1 = 500.0))
        val s = ReportMapper.toRunSummary(run(lowConf = true), scenarios)
        assertEquals(Validity.VALID_LOW_CONFIDENCE, s.validity)
    }

    // ---- T76/D-534 §3 设备半：status 从"只写不读"变成"读了并说出来" ----

    @Test
    fun `run status 被带进 RunSummary——闭合零读`() {
        val scenarios = listOf(scenario("s2_coding_agent", t1 = 500.0))
        val s = ReportMapper.toRunSummary(run(status = "aborted:bound_network_lost"), scenarios)
        assertEquals("aborted:bound_network_lost", s.runStatus)
    }

    /**
     * **中止的 run 仍按原判据进聚合，validity 一个字不改**：过滤那半是分析层的裁定
     * （D-534 §3），设备侧只负责"带上并说出来"。这条把边界钉住，防后人以为设备侧
     * 也该顺手多加一道过滤——两侧各判各的会让同一个 run 在两处结论不一致。
     */
    @Test
    fun `中止 run 的 validity 不因 status 而改变（过滤归分析层）`() {
        val scenarios = listOf(scenario("s2_coding_agent", t1 = 500.0))
        val s = ReportMapper.toRunSummary(run(status = "aborted:bound_network_lost"), scenarios)
        assertEquals(Validity.VALID, s.validity)
    }

    @Test
    fun `status 归一化：取冒号前、折大小写（与分析层 run_status_head 同一条）`() {
        assertEquals("aborted", ReportAnalyzerStatus.head("aborted:bound_network_lost"))
        assertEquals("completed", ReportAnalyzerStatus.head("COMPLETED"))
        assertEquals("completed", ReportAnalyzerStatus.head("  completed  "))
        assertNull("空白视同未知", ReportAnalyzerStatus.head("   "))
        assertNull(ReportAnalyzerStatus.head(null))
    }

    /**
     * 两个方向的 null 语义**刻意不同**，各防一件事，别把它们看成同一条：
     * - `isCompleted(null)` 为 **false**：防"把未知当健康"（缺证据不等于跑完，R-10）。
     * - 而结论文案里**不点名** status 未知的老 run：防"把未知当故障"——它们根本没有
     *   status 可读，报"中止"是冤枉（该分支由 ReportAnalyzer 侧测试覆盖）。
     */
    @Test
    fun `状态未知不算跑完——缺证据不等于健康`() {
        assertEquals(false, ReportAnalyzerStatus.isCompleted(null))
        assertEquals(true, ReportAnalyzerStatus.isCompleted("completed"))
        assertEquals(false, ReportAnalyzerStatus.isCompleted("aborted:x"))
    }
}

/** 转调 [com.aneb.probe.scoring.ReportAnalyzer] 的状态判据，纯粹为让本测试读起来短。 */
private object ReportAnalyzerStatus {
    fun head(s: String?) = com.aneb.probe.scoring.ReportAnalyzer.statusHead(s)
    fun isCompleted(s: String?) = com.aneb.probe.scoring.ReportAnalyzer.isCompleted(s)
}
