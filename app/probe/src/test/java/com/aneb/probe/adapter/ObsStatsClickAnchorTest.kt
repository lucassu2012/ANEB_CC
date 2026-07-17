package com.aneb.probe.adapter

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 发送锚定 TTFT v2（点击锚点）纯 JVM 单测（D-52；D-51 v1 input-clear 在豆包/DeepSeek 失效后的方向）。
 *
 * 口径：send_anchor v2=**发送按钮点击**（宿主按 send_button 规则用事件自带字段命中→[ObsSessionStats.onSendAnchor]，
 * 观察被动收 TYPE_VIEW_CLICKED，非注入）；锚定 TTFT=send_anchor→其后首个非输入框内容变化（[ObsSessionStats.onContentDelta] 闭合）。
 * 两启发式并存：**click 优先于 input_clear**（谁先武装算谁——正常序列点击先于输入框清空，click 锚点一旦武装即不被 input-clear 覆盖）；
 * onSendAnchor 覆盖任何旧未闭合锚点（含 input-clear）。快照 [AdapterObsSnapshot.anchorSource] 标注最近**完成**锚点来源（诊断用）。
 * 无锚点/未闭合=null（R-10）；ObsStats 自身**绝不自行武装**——无 onSendAnchor 调用（宿主 send_button 不命中）即无 click 锚点。
 */
class ObsStatsClickAnchorTest {

    private val ms = 1_000_000L // 1ms in nanos
    private val t0 = 20_000_000_000L // 任意会话起点

    private fun stats(specId: String? = "doubao") =
        ObsSessionStats(pkg = "com.larus.nova", specId = specId, observeStartNanos = t0)

    // ---------- 用例 1：点击武装锚点，首个内容变化闭合，anchorSource=click ----------

    @Test
    fun `click anchor armed and closed by first content delta with source click`() {
        val s = stats()
        s.onSendAnchor(t0 + 100 * ms) // 发送按钮点击（命中 send_button 规则）
        s.onContentDelta(t0 + 400 * ms) // 首个非输入框内容变化 → 闭合
        val snap = s.snapshot(t0 + 500 * ms)
        assertEquals(300.0, snap.ttftSendMs!!, 1e-9)
        assertEquals(listOf(300.0), snap.ttftSendHistory)
        assertEquals("click", snap.anchorSource)
    }

    // ---------- 用例 2：重新点击覆盖上一个未闭合 click 锚点（从最新锚点起算） ----------

    @Test
    fun `rearm click overwrites previous unclosed click anchor`() {
        val s = stats()
        s.onSendAnchor(t0 + 100 * ms) // 锚点 A（未闭合）
        s.onSendAnchor(t0 + 500 * ms) // 锚点 B：覆盖 A
        s.onContentDelta(t0 + 800 * ms)
        val snap = s.snapshot(t0 + 900 * ms)
        assertEquals("从最新点击 B 起算，A 已被覆盖", 300.0, snap.ttftSendMs!!, 1e-9)
        assertEquals(listOf(300.0), snap.ttftSendHistory)
        assertEquals("click", snap.anchorSource)
    }

    // ---------- 用例 3：click 优先于 input_clear——点击先武装，其后输入框清空不覆盖 ----------

    @Test
    fun `click takes priority over later input clear`() {
        val s = stats()
        s.onInputBoxText(12, t0 + 50 * ms) // 用户打字（非空）
        s.onSendAnchor(t0 + 100 * ms) // 点击发送 → click 锚点武装
        s.onInputBoxText(0, t0 + 200 * ms) // 输入框清空（非空→空）：已有 click 锚点 → 不覆盖
        s.onContentDelta(t0 + 450 * ms) // 闭合
        val snap = s.snapshot(t0 + 500 * ms)
        assertEquals("从 click 锚点(t0+100)起算，非 input_clear(t0+200)", 350.0, snap.ttftSendMs!!, 1e-9)
        assertEquals("click 优先", "click", snap.anchorSource)
    }

    // ---------- 用例 4：onSendAnchor 覆盖已武装的 input_clear 锚点（click 优先的另一侧） ----------

    @Test
    fun `click anchor overwrites pending input clear anchor`() {
        val s = stats()
        s.onInputBoxText(7, t0 + 100 * ms)
        s.onInputBoxText(0, t0 + 200 * ms) // input_clear 锚点武装（未闭合）
        s.onSendAnchor(t0 + 300 * ms) // 点击 → 覆盖 input_clear 锚点
        s.onContentDelta(t0 + 600 * ms)
        val snap = s.snapshot(t0 + 700 * ms)
        assertEquals("从 click 锚点(t0+300)起算", 300.0, snap.ttftSendMs!!, 1e-9)
        assertEquals("click", snap.anchorSource)
    }

    // ---------- 用例 5：纯 input_clear 路径 → anchorSource=input_clear（v1 附加标注，行为零变） ----------

    @Test
    fun `pure input clear path annotates source input_clear`() {
        val s = stats()
        s.onInputBoxText(9, t0 + 100 * ms)
        s.onInputBoxText(0, t0 + 200 * ms) // input_clear 武装（无 click）
        s.onContentDelta(t0 + 500 * ms)
        val snap = s.snapshot(t0 + 600 * ms)
        assertEquals(300.0, snap.ttftSendMs!!, 1e-9)
        assertEquals("input_clear", snap.anchorSource)
    }

    // ---------- 用例 6：无 onSendAnchor 且无 input_clear → null（无规则不武装，R-10 诚实缺席） ----------

    @Test
    fun `no arm without send anchor or input clear yields null and null source`() {
        val s = stats()
        // 宿主 send_button 不命中 → 从不调 onSendAnchor；内容变化不得自行武装
        s.onContentDelta(t0 + 100 * ms)
        s.onContentDelta(t0 + 200 * ms)
        val snap = s.snapshot(t0 + 300 * ms)
        assertNull("R-10：无锚点=未测，绝不折 0", snap.ttftSendMs)
        assertNull("无完成锚点 → anchorSource=null", snap.anchorSource)
        assertTrue(snap.ttftSendHistory.isEmpty())
    }

    // ---------- 用例 7：anchorSource 仅与**完成**值配对——新未闭合锚点不改已报值 ----------

    @Test
    fun `anchor source pairs with completed value only not pending`() {
        val s = stats()
        s.onSendAnchor(t0 + 100 * ms)
        s.onContentDelta(t0 + 300 * ms) // 完成：200ms，click
        s.onInputBoxText(5, t0 + 400 * ms)
        s.onInputBoxText(0, t0 + 500 * ms) // 新 input_clear 锚点武装（未闭合）
        val snap = s.snapshot(t0 + 600 * ms)
        assertEquals("仍报最近完成值 200ms", 200.0, snap.ttftSendMs!!, 1e-9)
        assertEquals("仍报最近完成来源 click（未闭合的新锚点不泄漏）", "click", snap.anchorSource)
    }

    // ---------- 用例 8：点击轨零变既有事件统计（events/first_delta/cadence 独立） ----------

    @Test
    fun `click track does not touch existing event stats`() {
        val s = stats()
        s.onSendAnchor(t0 + 100 * ms)
        s.onContentDelta(t0 + 300 * ms)
        val snap = s.snapshot(t0 + 400 * ms)
        assertEquals("onSendAnchor/onContentDelta 不计入 events（onEvent 独立）", 0L, snap.events)
        assertNull(snap.firstDeltaMs)
        assertNull(snap.cadenceP50Ms)
        assertEquals("LOW/INCONCLUSIVE", snap.confidence)
    }
}
