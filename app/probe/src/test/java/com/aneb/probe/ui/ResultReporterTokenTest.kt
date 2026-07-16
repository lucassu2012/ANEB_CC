package com.aneb.probe.ui

import com.aneb.probe.data.TestRun
import com.aneb.probe.engine.AqsInputMapper
import com.aneb.probe.engine.ProfilePhase
import com.aneb.probe.engine.ResultReporter
import com.aneb.probe.engine.ScenarioProfile
import com.aneb.probe.scoring.AqsScorer
import com.aneb.probe.scoring.TokenBehaviorClassifier
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * D-29 合同单测：`run.aqs_token`（分数/子分/权重表/工作量）经 [ResultReporter.build] 落库、
 * 经 [ResultAqsBreakdown.tokenConclusionFromReportJson] 解析的**端到端往返**——上报体键与
 * 解析器口径漂移立即红灯（同 ResultAqsBreakdownTest 的防漂移手法）。
 * 另锚定 [AqsInputMapper.workloadFrom] 的工作量派生口径（facet4 双证据分类的输入 A）。
 */
class ResultReporterTokenTest {

    private fun run() = TestRun(
        runId = "run-tok", startedAtEpochMs = 1_752_000_000_000L,
        serverBase = "http://10.0.2.2:8443", mode = "quick",
        scenarioOrder = "s1_chat,s2_coding_agent,s3_multimodal", transport = "auto",
        kpiSet = "agent-qoe-kpi-v0.2", aqsVersion = AqsScorer.AQS_VERSION,
        profileVersions = "s1_chat@0.2.0", schemaVersion = "1.0",
        profileSource = "server", appVersionName = "0.3.0", appVersionCode = 1L,
        guardMetadata = "private_dns_active=false", aqsScore = 89.2, aqsLowConfidence = false,
        aqsVetoApplied = false, aqsNotComputableReason = null,
        status = "completed", reportStatus = null,
    )

    private val v01 = AqsScorer.AqsResult(
        aqsVersion = AqsScorer.AQS_VERSION, kpiSetVersion = "agent-qoe-kpi-v0.2",
        score = 89.2,
        subScores = mapOf(
            "T1" to 97.3, "T3" to 100.0, "T2" to 98.0,
            "U1" to 77.5, "U2" to 77.8, "N1" to 75.1, "N2" to 81.6,
        ),
        vetoApplied = false, lowConfidence = false, notComputableReason = null,
    )

    private val workload = TokenBehaviorClassifier.WorkloadSignal(
        uplinkBytesPerRound = 2_621_440L,
        peakToMeanRatio = 1.6,
        downlinkMediaBytes = 0L,
        tokenStreamLen = 600,
        toolLoopRounds = 8,
        hasThinkPause = true,
        shortContextMultiTurn = true,
        longStreamOrContinuous = true,
    )

    private fun tokenReport(aqsToken: AqsScorer.AqsResult): String = ResultReporter.build(
        run = run(), scenarios = emptyList(), aqs = v01,
        aqsToken = aqsToken, tokenWeightsTableId = "WEIGHTS_TOKEN_MM", tokenWorkload = workload,
    )

    @Test
    fun `往返_可计算_token子分与工作量完整还原`() {
        val tokenResult = AqsScorer.AqsResult(
            aqsVersion = AqsScorer.AQS_VERSION_TOKEN, kpiSetVersion = "agent-qoe-kpi-v0.2",
            score = 84.4,
            subScores = mapOf(
                "T1" to 97.3, "T2" to 98.0, "T3" to 100.0, "U1" to 77.5,
                "D1" to 66.0, "U2" to 77.8, "N1" to 75.1, "N2" to 81.6,
            ),
            vetoApplied = false, lowConfidence = false, notComputableReason = null,
        )
        val tc = ResultAqsBreakdown.tokenConclusionFromReportJson(tokenReport(tokenResult))
        assertNotNull(tc)
        tc!!
        assertEquals(84.4, tc.score!!, 1e-9)
        assertEquals("WEIGHTS_TOKEN_MM", tc.weightsTableId)
        assertFalse("token 子分在场不走回落", tc.subScoresFromFallback)
        assertEquals(66.0, tc.subScores.getValue("D1"), 1e-9)
        assertEquals(workload, tc.workload)
    }

    @Test
    fun `往返_D1缺失不可计算_回落v01子分且保留原因`() {
        val notComputable = AqsScorer.AqsResult(
            aqsVersion = AqsScorer.AQS_VERSION_TOKEN, kpiSetVersion = "agent-qoe-kpi-v0.2",
            score = null, subScores = emptyMap(),
            vetoApplied = false, lowConfidence = false, notComputableReason = "KPI_MISSING:D1",
        )
        val tc = ResultAqsBreakdown.tokenConclusionFromReportJson(tokenReport(notComputable))
        assertNotNull(tc)
        tc!!
        assertNull(tc.score)
        assertEquals("KPI_MISSING:D1", tc.notComputableReason)
        assertTrue("空 token 子分应回落 v0.1", tc.subScoresFromFallback)
        assertEquals(97.3, tc.subScores.getValue("T1"), 1e-9)
        // 回落子分 + 落库工作量足以驱动分类（长流→稳定性、tool_loop→低时延）
        val findings = TokenBehaviorClassifier.classify(
            tc.subScores, AqsScorer.TOKEN_WEIGHT_TABLES.getValue(tc.weightsTableId), tc.workload,
        )
        assertTrue(findings.any { it.tag == TokenBehaviorClassifier.TestBehaviorTag.STABILITY })
        assertTrue(findings.any { it.tag == TokenBehaviorClassifier.TestBehaviorTag.LOW_LATENCY })
    }

    @Test
    fun `旧上报体无aqs_token节点_解析为null`() {
        val old = ResultReporter.build(run = run(), scenarios = emptyList(), aqs = v01)
        assertNull(ResultAqsBreakdown.tokenConclusionFromReportJson(old))
    }

    @Test
    fun `workloadFrom_从profile相位确定性派生`() {
        val profiles = listOf(
            ScenarioProfile(
                profileId = "s1_chat", version = "0.2.0",
                phases = listOf(
                    ProfilePhase(type = ProfilePhase.TYPE_UPLOAD_BURST, bytes = 2048),
                    ProfilePhase(type = ProfilePhase.TYPE_TOKEN_STREAM, tokens = 600),
                ),
            ),
            ScenarioProfile(
                profileId = "s2_coding_agent", version = "0.2.0",
                phases = listOf(
                    ProfilePhase(type = ProfilePhase.TYPE_UPLOAD_BURST, bytes = 524_288),
                    ProfilePhase(type = ProfilePhase.TYPE_THINK_PAUSE, durationMs = 1500),
                    ProfilePhase(type = ProfilePhase.TYPE_TOOL_LOOP, rounds = 8),
                    ProfilePhase(type = ProfilePhase.TYPE_TOKEN_STREAM, tokens = 300),
                ),
            ),
            ScenarioProfile(
                profileId = "s3_multimodal", version = "0.2.0",
                phases = listOf(
                    ProfilePhase(type = ProfilePhase.TYPE_UPLOAD_BURST, bytes = 1_048_576),
                    ProfilePhase(type = "download_burst", bytes = 20L * 1024 * 1024),
                    ProfilePhase(type = ProfilePhase.TYPE_TOKEN_STREAM, tokens = 200),
                ),
            ),
        )
        val w = AqsInputMapper.workloadFrom(profiles)
        assertEquals(2048L + 524_288 + 1_048_576, w.uplinkBytesPerRound)
        assertEquals(20L * 1024 * 1024, w.downlinkMediaBytes)
        assertEquals(600, w.tokenStreamLen)
        assertEquals(8, w.toolLoopRounds)
        assertTrue(w.hasThinkPause)
        assertTrue("tool_loop>0 ⇒ 多轮往返", w.shortContextMultiTurn)
        assertTrue("流长 600 ≥ ${AqsInputMapper.LONG_STREAM_TOKENS} ⇒ 长流", w.longStreamOrContinuous)
        // 峰均比 = max/mean（字节级突发度代理）
        val mean = listOf(2048L, 524_288L, 1_048_576L).average()
        assertEquals(1_048_576.0 / mean, w.peakToMeanRatio, 1e-9)
    }
}
