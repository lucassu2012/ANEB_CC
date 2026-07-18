package com.aneb.probe.ui

import com.aneb.probe.data.AdapterObsEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.data.VoiceResultEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * [HistoryFeed.merge] 契约单测（历史页统一展示）：时间降序混排、LazyColumn key 唯一
 * （run=runId，语音="voice-{id}"）、空列表退化。
 */
class HistoryFeedTest {

    private fun run(runId: String, startedAtEpochMs: Long) = TestRun(
        runId = runId,
        startedAtEpochMs = startedAtEpochMs,
        serverBase = "http://test",
        mode = "quick",
        scenarioOrder = "s1,s2,s3",
        transport = "auto",
        kpiSet = "agent-qoe-kpi-v0.1",
        aqsVersion = "aqs-v0.1",
        profileVersions = "{}",
        schemaVersion = "1",
        profileSource = "server",
        appVersionName = null,
        appVersionCode = null,
        guardMetadata = null,
        aqsScore = null,
        aqsLowConfidence = null,
        aqsVetoApplied = null,
        aqsNotComputableReason = null,
        status = "completed",
        reportStatus = null,
    )

    private fun voice(id: Long, tsEpochMs: Long) = VoiceResultEntity(
        id = id,
        tsEpochMs = tsEpochMs,
        caliber = null,
        lowConfidence = false,
        // 全部 KPI 可空字段记 null（R-10：未测不补 0/哨兵值）
        rttMs = null,
        jitterMs = null,
        upFrameJitterMs = null,
        downFrameJitterMs = null,
        mouthEarBudgetMs = null,
        framesSent = null,
        framesRecv = null,
        ttfbP50Ms = null,
        ttfbP95Ms = null,
        downNetJitterMs = null,
        mouthEarProxyMs = null,
        turnSwitchP50Ms = null,
        bargeStopMaxMs = null,
        turnsOk = null,
    )

    private fun adapter(id: Long, tsEpochMs: Long) = AdapterObsEntity(
        id = id,
        tsEpochMs = tsEpochMs,
        pkg = "com.larus.nova",
        specId = "doubao",
        appLabel = "豆包",
        events = 42,
        ruleMatchedEvents = 7,
        // 指标全部可空字段记 null（R-10：未测不补 0/哨兵值）
        firstDeltaMs = null,
        cadenceP50Ms = null,
        ttftClusterMs = null,
        ttftSendMs = null,
        anchorSource = null,
        confidence = "LOW/INCONCLUSIVE",
    )

    @Test
    fun `混排按时间降序（跨两类交错）`() {
        val merged = HistoryFeed.merge(
            runs = listOf(run("r-old", 100), run("r-new", 400)),
            voice = listOf(voice(1, 300), voice(2, 200)),
        )
        assertEquals(4, merged.size)
        assertEquals(listOf(400L, 300L, 200L, 100L), merged.map { it.epochMs })
        assertEquals(listOf("r-new", "voice-1", "voice-2", "r-old"), merged.map { it.key })
    }

    @Test
    fun `key 全列表唯一（含同刻 run 与语音并存）`() {
        val merged = HistoryFeed.merge(
            runs = listOf(run("r-1", 500), run("r-2", 500)),
            voice = listOf(voice(1, 500), voice(2, 500)),
        )
        assertEquals(4, merged.size)
        assertEquals(merged.size, merged.map { it.key }.toSet().size)
        // 语音 key 前缀合同："voice-{id}"（与 runId 命名空间隔离）
        assertTrue(merged.filterIsInstance<HistoryEntry.Voice>().all { it.key == "voice-${it.result.id}" })
        assertTrue(merged.filterIsInstance<HistoryEntry.Run>().all { it.key == it.run.runId })
    }

    @Test
    fun `同刻稳定序：run 在语音前、各自输入相对序保留`() {
        val merged = HistoryFeed.merge(
            runs = listOf(run("r-1", 500), run("r-2", 500)),
            voice = listOf(voice(9, 500), voice(3, 500)),
        )
        // sortedByDescending 稳定：拼接序（runs 在前）在同刻不被打乱
        assertEquals(listOf("r-1", "r-2", "voice-9", "voice-3"), merged.map { it.key })
    }

    @Test
    fun `三方混排按时间降序（run+语音+观察交错）`() {
        val merged = HistoryFeed.merge(
            runs = listOf(run("r-old", 100), run("r-new", 500)),
            voice = listOf(voice(1, 300)),
            adapterObs = listOf(adapter(9, 400), adapter(8, 200)),
        )
        assertEquals(5, merged.size)
        assertEquals(listOf(500L, 400L, 300L, 200L, 100L), merged.map { it.epochMs })
        assertEquals(listOf("r-new", "obs-9", "voice-1", "obs-8", "r-old"), merged.map { it.key })
    }

    @Test
    fun `key 全列表唯一（含观察 obs-{id} 与 run-语音同刻并存）`() {
        val merged = HistoryFeed.merge(
            runs = listOf(run("r-1", 500)),
            voice = listOf(voice(1, 500)),
            adapterObs = listOf(adapter(1, 500), adapter(2, 500)),
        )
        assertEquals(4, merged.size)
        assertEquals(merged.size, merged.map { it.key }.toSet().size)
        // 观察 key 前缀合同："obs-{id}"——与 runId / "voice-{id}" 命名空间隔离：
        // 观察 id=1 得 "obs-1"，与 voice id=1 的 "voice-1" 不冲突（同刻同 id 也唯一）。
        assertTrue(merged.filterIsInstance<HistoryEntry.Adapter>().all { it.key == "obs-${it.obs.id}" })
    }

    @Test
    fun `空列表退化`() {
        assertEquals(emptyList<HistoryEntry>(), HistoryFeed.merge(emptyList(), emptyList()))
        // 仅 runs：全为 Run 条目
        val onlyRuns = HistoryFeed.merge(listOf(run("r-1", 100)), emptyList())
        assertEquals(listOf("r-1"), onlyRuns.map { it.key })
        assertTrue(onlyRuns.single() is HistoryEntry.Run)
        // 仅语音：全为 Voice 条目
        val onlyVoice = HistoryFeed.merge(emptyList(), listOf(voice(7, 100)))
        assertEquals(listOf("voice-7"), onlyVoice.map { it.key })
        assertTrue(onlyVoice.single() is HistoryEntry.Voice)
    }
}
