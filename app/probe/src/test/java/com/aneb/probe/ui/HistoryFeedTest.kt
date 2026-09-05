package com.aneb.probe.ui

import com.aneb.probe.data.AdapterObsEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.data.VoiceResultEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
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

    private fun adapter(
        id: Long,
        tsEpochMs: Long,
        // 三形夹具的两个自由度（D-608／D-607：单形态夹具守不住——只喂 null+0 那一形，
        // 「仅 first_delta>0 才回退」这个错修法会照样全绿）
        firstDeltaMs: Long? = null,
        ttftClusterMs: Double? = null,
    ) = AdapterObsEntity(
        id = id,
        tsEpochMs = tsEpochMs,
        pkg = "com.larus.nova",
        specId = "doubao",
        appLabel = "豆包",
        events = 42,
        ruleMatchedEvents = 7,
        // 指标全部可空字段记 null（R-10：未测不补 0/哨兵值）
        firstDeltaMs = firstDeltaMs,
        cadenceP50Ms = null,
        ttftClusterMs = ttftClusterMs,
        ttftSendMs = null,
        anchorSource = null,
        confidence = "LOW/INCONCLUSIVE",
    )

    // ── D-608：TTFT 展示层的 R-10（三形夹具，缺一形就守不住）─────────────────
    // 缺陷原状：`ttftClusterMs ?: firstDeltaMs?.toDouble()` 把「未测到」显示成「TTFT 0 ms」。
    // null 是合并 token（三成因），而 first_delta 锚在观察启动、常态为 0 ⇒ 49.5 s 显示成
    // 0 ms，误差方向朝「看起来最快」。

    @Test
    fun `形一 簇为null且首增量为0 —— 必须判未测,绝不吐 0`() {
        // 本批 290 条 OBS 里 cluster=null 的 104 条，其 first_delta 全是这一形。
        assertNull(
            "R-10 延伸到回退层：first_delta=0 证明的是「窗开在流中途、这轮没测到」，" +
                "不是「0 毫秒出首字」——吐 0 会让 49.5 s 显示成 0 ms",
            HistoryFeed.obsTtftDisplayMs(adapter(1, 100, firstDeltaMs = 0L)),
        )
    }

    @Test
    fun `形二 簇为null但首增量为正值 —— 仍须判未测（这一形专抓错修法）`() {
        // ⚠ 三形里唯一能否证「仅 first_delta>0 才回退」那个候选修法的一形：
        // 窗开在流中途而首增量恰为 300 ms 时，那个修法会显示「TTFT 300 ms」而真值 49.5 s——
        // 门设在 0 上只挡住最扎眼的那个值，挡不住「跨锚点取值」这个机制。
        assertNull(
            "首增量与 TTFT 不同轴（锚在观察启动 vs 发送），正值同样不可冒充 TTFT",
            HistoryFeed.obsTtftDisplayMs(adapter(2, 200, firstDeltaMs = 300L)),
        )
    }

    @Test
    fun `形三 有簇值 —— 原样透出（证明修法没把好路一起堵死）`() {
        assertEquals(
            "落库的 ttftClusterMs 已在采集侧做过同口径择优（簇分割/密度谱），展示层原样透出",
            49_500.0,
            HistoryFeed.obsTtftDisplayMs(adapter(3, 300, ttftClusterMs = 49_500.0))!!,
            0.001,
        )
    }

    @Test
    fun `簇值存在时首增量不参与取值（两者同时有值也不混用）`() {
        assertEquals(
            "有簇值就用簇值；first_delta 只在副行以自己的名字出现",
            1_234.0,
            HistoryFeed.obsTtftDisplayMs(adapter(4, 400, firstDeltaMs = 0L, ttftClusterMs = 1_234.0))!!,
            0.001,
        )
    }

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
