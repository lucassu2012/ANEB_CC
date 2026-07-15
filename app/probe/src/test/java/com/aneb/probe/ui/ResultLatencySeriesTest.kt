package com.aneb.probe.ui

import com.aneb.probe.data.TokenEventEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * [ResultLatencySeries] 契约单测：ITL 相邻间隔、R-10（null 到达剔除）、优先 S2 编码场景、
 * 分位数/峰值聚合。
 */
class ResultLatencySeriesTest {

    private var seq = 0L
    private fun tok(scenarioKey: String, arrivalNanos: Long?, streamIndex: Int = 0) =
        TokenEventEntity(
            runId = "run-1", scenarioKey = scenarioKey, streamIndex = streamIndex, seq = seq++,
            schedUs = null, preFlushUs = null, arrivalNanos = arrivalNanos, payloadBytes = 1,
            sameReadBatch = false,
        )

    private val ms = 1_000_000L // 1ms = 1e6 ns

    @Test
    fun `空事件返回 EMPTY`() {
        val s = ResultLatencySeries.of(emptyList())
        assertEquals(ResultLatencySeries.EMPTY, s)
        assertFalse(s.hasSeries)
    }

    @Test
    fun `ITL 为相邻到达间隔（ms）`() {
        seq = 0
        // 到达 @0 / 100ms / 250ms / 300ms → 间隔 100,150,50
        val s = ResultLatencySeries.of(
            listOf(
                tok("s2_coding_agent#0", 0),
                tok("s2_coding_agent#0", 100 * ms),
                tok("s2_coding_agent#0", 250 * ms),
                tok("s2_coding_agent#0", 300 * ms),
            ),
        )
        assertTrue(s.hasSeries)
        assertEquals(listOf(100.0, 150.0, 50.0), s.itlMs)
        assertEquals(150.0, s.peakMs!!, 1e-9)
        assertEquals(4, s.tokenCount)
        assertTrue(s.sourceLabel.startsWith("S2 编码"))
    }

    @Test
    fun `null 到达剔除（R-10 绝不 0 顶替）`() {
        seq = 0
        // 中间 token 到达 null：间隔跨过缺失 token（@0→@300ms=300），不产生 0 间隔
        val s = ResultLatencySeries.of(
            listOf(
                tok("s2_coding_agent#0", 0),
                tok("s2_coding_agent#0", null),
                tok("s2_coding_agent#0", 300 * ms),
                tok("s2_coding_agent#0", 320 * ms),
            ),
        )
        // 有效到达 {0, 300ms, 320ms} → 间隔 {300, 20}
        assertEquals(listOf(300.0, 20.0), s.itlMs)
        assertEquals(3, s.tokenCount)
    }

    @Test
    fun `优先 S2 编码场景（即便 S1 样本更多）`() {
        seq = 0
        val evs = mutableListOf<TokenEventEntity>()
        // S1：5 个到达
        repeat(5) { evs += tok("s1_chat#0", it.toLong() * 100 * ms) }
        // S2：3 个到达（更少，但优先）
        repeat(3) { evs += tok("s2_coding_agent#0", it.toLong() * 50 * ms) }
        val s = ResultLatencySeries.of(evs)
        assertTrue(s.sourceLabel.startsWith("S2 编码"))
        assertEquals(3, s.tokenCount)
    }

    @Test
    fun `无 S2 时回退到样本最多的场景`() {
        seq = 0
        val evs = mutableListOf<TokenEventEntity>()
        repeat(4) { evs += tok("s1_chat#0", it.toLong() * 100 * ms) }
        repeat(3) { evs += tok("s3_multimodal#0", it.toLong() * 50 * ms) }
        val s = ResultLatencySeries.of(evs)
        assertTrue(s.sourceLabel.startsWith("S1 对话"))
        assertEquals(4, s.tokenCount)
    }

    @Test
    fun `样本不足（少于3到达）不出序列`() {
        seq = 0
        val s = ResultLatencySeries.of(
            listOf(tok("s2_coding_agent#0", 0), tok("s2_coding_agent#0", 100 * ms)),
        )
        assertFalse(s.hasSeries)
        assertEquals(ResultLatencySeries.EMPTY, s)
    }
}
