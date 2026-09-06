package com.aneb.probe.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * [TtftAnalysis.ttftMs] 的三形态夹具（C-3／REVIEW §7.3）。
 *
 * **这组测试存在的理由，写在这里以免日后被当成冗余删掉**：本函数抽出来之前
 * **内联在 ScenarioRunner.runStream 里**，要跑到它得起一条真实 HTTP 流
 * ——于是它的边界条件**一条都没被验过**。抽出后这几条才第一次成立。
 *
 * 「三形态」＝ **有值 / 输入缺失 / 服务端未给计划时刻**。三者在下游含义各不相同，
 * 而在此前的内联写法里它们**都只表现为「ttftMs 是 null」**。
 */
class TtftAnalysisTest {

    /** 形态一：四个输入齐备 ⇒ 出值，且**服务端注入时延被剥离**。 */
    @Test
    fun `形态一_输入齐备时剥离服务端 dwell 后出值`() {
        // 到达 − 原点 ＝ 500ms；服务端计划时延 ＝ (200_000 − 50_000)µs ＝ 150ms
        // ⇒ 网络分量 ＝ 500 − 150 ＝ 350ms
        val ms = TtftAnalysis.ttftMs(
            arrivalNs = 1_500_000_000L, originNs = 1_000_000_000L,
            schedUs = 200_000L, preludeUs = 50_000L,
        )
        assertEquals(
            "若这里等于 500，说明服务端 pacing 没被减掉——那测的是服务端，不是网络",
            350.0, ms!!, 1e-9,
        )
    }

    /** 形态二：任一输入缺失 ⇒ null。**逐个缺**，不拿一个代表其余。 */
    @Test
    fun `形态二_任一输入缺失即 null_而不是用 0 顶替`() {
        assertNull("没有 token", TtftAnalysis.ttftMs(null, 1_000_000_000L, 200_000L, 50_000L))
        assertNull("计时点缺失", TtftAnalysis.ttftMs(1_500_000_000L, null, 200_000L, 50_000L))
        assertNull("schedUs 缺失", TtftAnalysis.ttftMs(1_500_000_000L, 1_000_000_000L, null, 50_000L))
        assertNull("prelude 缺失", TtftAnalysis.ttftMs(1_500_000_000L, 1_000_000_000L, 200_000L, null))
    }

    /**
     * 形态三：schedUs < 0 ＝ 服务端**没给**计划时刻（既有约定），不是一个小数值。
     *
     * ⚠ 这条是本组里最容易写错的：照算不会抛异常，只会**多减一个负数**、
     * 得出一个偏大的 TTFT，**而且看起来完全正常**。
     */
    @Test
    fun `形态三_负 schedUs 是「服务端未给」而非可用值`() {
        assertNull(
            "schedUs<0 应判 null；照算会多减一个负数、得出偏大的 TTFT 且不报错",
            TtftAnalysis.ttftMs(1_500_000_000L, 1_000_000_000L, -1L, 50_000L),
        )
        // 边界正对照：0 是**合法**计划时刻，不得与「未给」混为一谈。
        // 少了这条，一个把判据写成 `schedUs > 0` 的实现同样能通过上面那条。
        assertEquals(
            "schedUs=0 是合法值，判成缺失会静默丢掉一整类样本",
            550.0,
            TtftAnalysis.ttftMs(1_500_000_000L, 1_000_000_000L, 0L, 50_000L)!!,
            1e-9,
        )
    }
}
