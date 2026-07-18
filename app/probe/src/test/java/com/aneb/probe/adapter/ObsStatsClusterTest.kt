package com.aneb.probe.adapter

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * send-anchor v3 簇分割 TTFT（[AdapterObsSnapshot.ttftClusterMs]）单测。
 *
 * 场景锚定（D-52 真机实证）：豆包发送后「用户气泡上屏」簇（簇内间隔 ~8ms）→ 模型思考
 * 静默（>500ms）→ 流式响应簇（簇内 ~100ms）。首簇起→次簇起 = TTFT 簇代理；
 * 不足两簇 = null（R-10）；只取会话内第一对簇。
 */
class ObsStatsClusterTest {

    private fun stats() = ObsSessionStats(pkg = "t", specId = null, observeStartNanos = 0L).also {
        // D-56 发送场景门控：模拟会话曾有真实输入活动（打字），使 TTFT 代理获发送语义。
        // 时戳 -1 早于所有用例的正时戳，onInputBoxText 不落桶、仅置位+重置簇窗（无副作用）。
        it.onInputBoxText(1, -1L)
    }

    private val ms = 1_000_000L

    @Test
    fun `two clusters split by silence yield cluster ttft`() {
        val s = stats()
        // 首簇：3 事件，簇内 8ms
        s.onContentDelta(1_000 * ms)
        s.onContentDelta(1_008 * ms)
        s.onContentDelta(1_016 * ms)
        // 思考静默 600ms（> 400ms 阈值）→ 次簇起
        s.onContentDelta(1_616 * ms)
        s.onContentDelta(1_716 * ms)
        val snap = s.snapshot(2_000 * ms)
        // 首簇起 1000ms → 次簇起 1616ms = 616ms
        assertEquals(616.0, snap.ttftClusterMs!!, 0.001)
    }

    @Test
    fun `single cluster yields null`() {
        val s = stats()
        s.onContentDelta(1_000 * ms)
        s.onContentDelta(1_100 * ms) // 100ms < 400ms 阈值：同簇（流式节奏不误分）
        s.onContentDelta(1_200 * ms)
        assertNull("不足两簇=未测（R-10 绝不折 0）", s.snapshot(2_000 * ms).ttftClusterMs)
    }

    @Test
    fun `no content events yields null`() {
        assertNull(stats().snapshot(1_000 * ms).ttftClusterMs)
    }

    @Test
    fun `only first cluster pair captured on multiple silences`() {
        val s = stats()
        s.onContentDelta(1_000 * ms) // 首簇起
        s.onContentDelta(1_600 * ms) // 静默 600ms → 次簇起（第一对锁定）
        s.onContentDelta(3_000 * ms) // 再静默 1400ms → 不再改写
        assertEquals(600.0, s.snapshot(4_000 * ms).ttftClusterMs!!, 0.001)
    }

    @Test
    fun `streaming cadence at 100ms stays one cluster`() {
        val s = stats()
        var t = 1_000L
        repeat(20) { // 20 个 100ms 间隔的流式事件——恒同簇
            s.onContentDelta(t * ms)
            t += 100
        }
        assertNull(s.snapshot(t * ms).ttftClusterMs)
    }

    @Test
    fun `cluster gap over sanity ceiling is suppressed to null`() {
        // D-56：Kimi 型脏值——两簇间隔 54s（>30s 上界）→ sane() 抑制为 null（诚实缺席优于错值）。
        val s = stats()
        s.onContentDelta(1_000 * ms) // 首簇起
        s.onContentDelta(55_000 * ms) // 静默 54s → 次簇起；簇跨度 54000ms > 30000ms 上界
        assertNull("超 30s 合理性上界的簇 TTFT 应抑制为 null", s.snapshot(56_000 * ms).ttftClusterMs)
    }

    @Test
    fun `no input activity gates cluster to null`() {
        // D-56 发送场景门控：无输入活动（直接构造，不经 stats() 的注入）→ cluster null。
        val s = ObsSessionStats(pkg = "t", specId = null, observeStartNanos = 0L)
        s.onContentDelta(1_000 * ms)
        s.onContentDelta(1_616 * ms) // 静默 616ms → 两簇成立，但无输入活动
        assertNull("非发送场景（无输入活动）TTFT 门控为 null", s.snapshot(2_000 * ms).ttftClusterMs)
    }
}
