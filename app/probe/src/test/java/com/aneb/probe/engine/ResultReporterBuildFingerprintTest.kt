package com.aneb.probe.engine

import com.aneb.probe.data.ScenarioResultEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.scoring.AqsScorer
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 构建指纹上 wire 的闭环单测（A-8③／REVIEW §7.1 L1-F4）。
 *
 * **为什么要这一条**：v23 加了三列、`TestEngine` 也填了值，但**列有值 ≠ wire 上出现**
 * ——本仓在 D1 上正栽过一次「算了但从没接线」（见 [ResultReporterD1Test] 类注释）。
 * 三层各自绿而中间断一节，是这里反复出现的形状。
 *
 * ⚠ **本块只有三键，REVIEW 原文写的是四键**（含 `inject_used`）：那一键在库里**没有持久
 * 来源**（inject 只活在内存的 `TestEngine.Config.inject` 与一行 `RUN_START` logcat 里，
 * 而日志到不了分析层）。已报大脑裁，**裁定前不写没有真实来源的键**。
 * 下面第三条用例把这个缺席**钉住**：一旦有人顺手补了个假的 `inject_used`，它会红。
 */
class ResultReporterBuildFingerprintTest {

    private fun run(
        gitSha: String? = "8029f5f",
        buildTypeName: String? = "debug",
        appId: String? = "com.aneb.probe.ctree",
    ) = TestRun(
        runId = "run-1", startedAtEpochMs = 1_752_000_000_000L,
        serverBase = "http://10.0.2.2:8443", mode = "quick",
        scenarioOrder = "s1_chat", transport = "auto",
        kpiSet = "agent-qoe-kpi-v0.2", aqsVersion = "aqs-v0.1",
        profileVersions = "s1_chat@0.2.0", schemaVersion = "1.0",
        profileSource = "server", appVersionName = "0.1.0-phase0", appVersionCode = 1L,
        guardMetadata = null, aqsScore = 88.5, aqsLowConfidence = false,
        aqsVetoApplied = false, aqsNotComputableReason = null,
        status = "completed", reportStatus = null,
        buildGitSha = gitSha, buildType = buildTypeName, buildApplicationId = appId,
    )

    /** 最小可用场景行（形状照抄 [ResultReporterD1Test]，本测不关心其中任何 KPI 值）。 */
    private fun scenario(runId: String) = ScenarioResultEntity(
        runId = runId, profileId = "s1_chat", profileVersion = "0.2.0",
        repeatIndex = 0, orderIndex = 0, startedAtNanos = 0L, endedAtNanos = 1L,
        validity = "valid", invalidReasons = "",
        t1TtftMs = null, t1Grade = null, t2ItlP95Ms = null, t2Grade = null,
        t2ItlP95InclCoalescedMs = null, t3StallRate = null, t3Grade = null,
        t3StallRateInclResume = null, t4SevereStallRate = null, t4Grade = null,
        t5ResumeP95Ms = null, n1RttP50Ms = null, n1Grade = null,
        n2JitterMs = null, n2Grade = null, u1GoodputMbps = null, u1Grade = null,
        u1GoodputExclSlowStartMbps = null, u2ToolLoopP95Ms = null, u2Grade = null,
        d1GoodputMbps = null, d1Grade = null,
        seqGapCount = 0, seqDupCount = 0, lowConfidenceKpis = "",
        offsetStartUs = null, offsetStartErrUs = null, offsetEndUs = null,
        offsetEndErrUs = null, offsetDriftPpm = null, offsetSuspect = false,
        netTransport = null, netCapabilities = null, netInterfaceName = null,
        serverObservedAddr = null, parseDurUsTotal = null, perEventParseUs = null,
    )

    private fun body(r: TestRun): String = ResultReporter.build(
        run = r,
        scenarios = listOf(scenario(r.runId) to ItlHistogram.of(emptyList())),
        aqs = AqsScorer.AqsResult(
            aqsVersion = "aqs-v0.1", kpiSetVersion = "agent-qoe-kpi-v0.2",
            score = 88.5, subScores = mapOf("T" to 90.0),
            vetoApplied = false, lowConfidence = false, notComputableReason = null,
        ),
    )

    @Test
    fun `三个构建指纹字段真的出现在 wire 的 build 块里`() {
        val json = body(run())
        assertTrue("wire 上没有 build 块", json.contains("\"build\""))
        assertTrue("git_sha 没上 wire", json.contains("\"git_sha\":\"8029f5f\""))
        assertTrue("build_type 没上 wire", json.contains("\"build_type\":\"debug\""))
        assertTrue(
            "application_id 没上 wire——换名变体（.ctree）正是靠它分辨的",
            json.contains("\"application_id\":\"com.aneb.probe.ctree\""),
        )
    }

    /**
     * 三列皆 null ＝ 该 run 早于本字段上线 ⇒ **整块缺席**，而不是「块在、值为 null」。
     * 两者语义不同：缺席说「不知道」，块在值 null 说「列已上线但这条没记上」。
     * 混为一谈，会让读者把一批**老数据**误读成**新数据里的空洞**。
     */
    @Test
    fun `早于本字段上线的 run 整块缺席_而不是块在值为 null`() {
        val json = body(run(gitSha = null, buildTypeName = null, appId = null))
        assertFalse("三列皆 null 时不该出现 build 块", json.contains("\"build\""))
    }

    /**
     * **缺席钉**：`inject_used` 目前没有持久来源，故**不得出现在 wire 上**。
     * 这条不是「防回归」，是**防好心**——补一个没有来源的键比缺这个键更坏，因为读者会信它。
     * 等大脑裁定给了来源，改这条测试与改实现应当是**同一个动作**。
     */
    @Test
    fun `inject_used 在有真实来源之前不得出现在 wire 上`() {
        assertFalse(
            "wire 上出现了 inject_used，但库里没有它的持久来源——见类注释",
            body(run()).contains("inject_used"),
        )
    }
}
