package com.aneb.probe.adapter

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 发送锚定 TTFT 状态机纯 JVM 单测（D-50 口径缺口收口）。
 *
 * 口径：send_anchor=输入框文本**非空→空**（input-clear 启发式，可能含手动清空误检——
 * 如实按启发式语义测试，不假装能区分）；锚定 TTFT=send_anchor→其后首个非输入框内容
 * 变化；无锚点/未闭合=null（R-10）；历史环形 ≤8。时间轴=相对纳秒（单调钟同语义）。
 */
class ObsStatsSendAnchorTest {

    private val ms = 1_000_000L // 1ms in nanos
    private val t0 = 10_000_000_000L // 任意会话起点

    private fun stats(specId: String? = "doubao") =
        ObsSessionStats(pkg = "com.larus.nova", specId = specId, observeStartNanos = t0)

    // ---------- 用例 1：无发送锚点 → null 不折 0（R-10），内容变化不误触发 ----------

    @Test
    fun `no anchor yields null ttft and empty history`() {
        val s = stats()
        s.onContentDelta(t0 + 100 * ms) // 无锚点时的内容变化：无操作
        s.onInputBoxText(0, t0 + 200 * ms) // 初始即空（空→空非转变）：不武装
        s.onContentDelta(t0 + 300 * ms)
        val snap = s.snapshot(t0 + 400 * ms)
        assertNull("R-10：无发送锚点=未测，绝不折 0", snap.ttftSendMs)
        assertTrue(snap.ttftSendHistory.isEmpty())
    }

    // ---------- 用例 2：非空→空武装锚点，首个内容变化闭合 ----------

    @Test
    fun `anchor armed on nonempty to empty and closed by first content delta`() {
        val s = stats()
        s.onInputBoxText(12, t0 + 100 * ms) // 打字（非空）
        s.onInputBoxText(0, t0 + 200 * ms) // 非空→空 = send_anchor
        s.onContentDelta(t0 + 450 * ms) // 首个非输入框内容变化 → 闭合
        val snap = s.snapshot(t0 + 500 * ms)
        assertEquals(250.0, snap.ttftSendMs!!, 1e-9)
        assertEquals(listOf(250.0), snap.ttftSendHistory)
    }

    // ---------- 用例 3：锚点武装但未闭合 → null（R-10）；输入框事件不闭合锚点 ----------

    @Test
    fun `unclosed anchor yields null and input box events never close it`() {
        val s = stats()
        s.onInputBoxText(5, t0 + 100 * ms)
        s.onInputBoxText(0, t0 + 200 * ms) // 武装
        s.onInputBoxText(3, t0 + 300 * ms) // 输入框再打字：不闭合锚点
        val snap = s.snapshot(t0 + 5_000 * ms)
        assertNull("R-10：锚点未闭合=未测，绝不折 0", snap.ttftSendMs)
        assertTrue(snap.ttftSendHistory.isEmpty())
        // 之后首个内容变化仍从原锚点（t0+200ms）起算
        s.onContentDelta(t0 + 6_000 * ms)
        assertEquals(5_800.0, s.snapshot(t0 + 6_100 * ms).ttftSendMs!!, 1e-9)
    }

    // ---------- 用例 4：重新武装取消上一个未闭合锚点（从新锚点起算，历史仅一条） ----------

    @Test
    fun `rearm cancels previous unclosed anchor`() {
        val s = stats()
        s.onInputBoxText(8, t0 + 100 * ms)
        s.onInputBoxText(0, t0 + 200 * ms) // 锚点 A（将被取消）
        s.onInputBoxText(6, t0 + 1_000 * ms) // 再打字
        s.onInputBoxText(0, t0 + 2_000 * ms) // 锚点 B：重新武装，覆盖 A
        s.onContentDelta(t0 + 2_300 * ms)
        val snap = s.snapshot(t0 + 2_400 * ms)
        assertEquals("从最新锚点 B 起算，A 已取消", 300.0, snap.ttftSendMs!!, 1e-9)
        assertEquals("A 未闭合不入历史", listOf(300.0), snap.ttftSendHistory)
    }

    // ---------- 用例 5：多次发送——最近完成值 + 历史时间升序累积 ----------

    @Test
    fun `multiple sends keep latest completed and accumulate history in order`() {
        val s = stats()
        var t = t0
        // 三轮发送：锚定 TTFT 依次 100ms / 220ms / 340ms
        for ((i, ttft) in listOf(100L, 220L, 340L).withIndex()) {
            s.onInputBoxText(10 + i, t + 10 * ms)
            s.onInputBoxText(0, t + 20 * ms)
            s.onContentDelta(t + 20 * ms + ttft * ms)
            t += 1_000 * ms
        }
        val snap = s.snapshot(t)
        assertEquals(340.0, snap.ttftSendMs!!, 1e-9)
        assertEquals(listOf(100.0, 220.0, 340.0), snap.ttftSendHistory)
    }

    // ---------- 用例 6：手动清空同样武装（input-clear 启发式的如实语义，不假装可区分） ----------

    @Test
    fun `manual clear also arms anchor heuristic semantics`() {
        val s = stats()
        s.onInputBoxText(7, t0 + 100 * ms) // 用户打字
        s.onInputBoxText(0, t0 + 200 * ms) // 语义上是手动删光——观察口径与发送清空不可区分
        s.onContentDelta(t0 + 350 * ms) // 无关内容变化闭合 → 产生一次（可能误检的）锚定值
        val snap = s.snapshot(t0 + 400 * ms)
        assertEquals("启发式如实武装：手动清空亦产出锚定值（恒 LOW/INCONCLUSIVE）",
            150.0, snap.ttftSendMs!!, 1e-9)
        assertEquals(1, snap.ttftSendHistory.size)
    }

    // ---------- 用例 7：历史环形上限 8——只留最近 8 个完成值 ----------

    @Test
    fun `history ring keeps only latest 8 completed values`() {
        val s = stats()
        var t = t0
        // 10 轮发送：锚定 TTFT = 10,20,...,100ms；环形应只留最近 8 个（30..100）
        for (i in 1..10) {
            s.onInputBoxText(5, t + 10 * ms)
            s.onInputBoxText(0, t + 20 * ms)
            s.onContentDelta(t + 20 * ms + i * 10 * ms)
            t += 1_000 * ms
        }
        val snap = s.snapshot(t)
        assertEquals(8, snap.ttftSendHistory.size)
        assertEquals(listOf(30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0), snap.ttftSendHistory)
        assertEquals("最近完成值=第 10 轮", 100.0, snap.ttftSendMs!!, 1e-9)
    }

    // ---------- 用例 8：既有字段零变——新轨不动 events/first_delta/cadence ----------

    @Test
    fun `send anchor track does not touch existing event stats`() {
        val s = stats()
        s.onInputBoxText(9, t0 + 100 * ms)
        s.onInputBoxText(0, t0 + 200 * ms)
        s.onContentDelta(t0 + 300 * ms)
        val snap = s.snapshot(t0 + 400 * ms)
        assertEquals("onInputBoxText/onContentDelta 不计入 events（onEvent 独立）", 0L, snap.events)
        assertNull(snap.firstDeltaMs)
        assertNull(snap.cadenceP50Ms)
        assertEquals("LOW/INCONCLUSIVE", snap.confidence)
    }
}
