package com.aneb.probe.ui

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * [nearZeroRatioDisplay] 的 R-10 语义钉桩（D-488③ 展示位兑现的配套守卫）：
 * "—"（没测到）与 "0.0%"（实测零）必须可区分——把 null 显示成 0% 就是
 * R-10 明令禁止的"缺席被 0 顶替"，读者会把"无数据"误读成"确认无缓冲突发"。
 */
class NearZeroRatioDisplayTest {

    @Test
    fun `null renders as dash not zero percent (R-10)`() {
        assertEquals("—", nearZeroRatioDisplay(null))
    }

    @Test
    fun `real zero renders as zero percent, distinct from absence`() {
        assertEquals("0.0%", nearZeroRatioDisplay(0.0))
    }

    @Test
    fun `first-batch realistic value renders one decimal place`() {
        // D-488 首批实测区间 0~3.42%——3.42% 落一位小数为 3.4%
        assertEquals("3.4%", nearZeroRatioDisplay(0.0342))
    }

    @Test
    fun `full ratio renders 100 percent not clamped or overflowed`() {
        assertEquals("100.0%", nearZeroRatioDisplay(1.0))
    }
}
