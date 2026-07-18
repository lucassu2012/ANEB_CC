package com.aneb.probe.adapter

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * 密度谱 TTFT v4（[AdapterObsSnapshot.ttftDensityMs]）单测——选型=方案 A（密度基线偏离法）。
 *
 * 机制（纯时戳统计，不依赖静默/锚点/节点）：把发送后内容事件流按 100ms 步桶化为前缀直方图 →
 * 组 200ms（2 步）滑窗密度谱 → 取发送后前 5 窗中位数为「发送后初始稳态」基线 → 首个相对基线
 * 结构性跃变窗（上跃 ≥2× / 静止基线下 ≥2 事件；下跃 ≤0.5× 且基线 ≥4）= 响应起点候选。
 *
 * 场景锚定（D-52/D-53 真机实证）：
 * - 豆包（View 系，思考期 UI 静止无内容事件）：气泡突发→静默→响应，基线≈0，响应上跃检出；
 * - DeepSeek（Compose，思考期播放生成动画持续 CONTENT、cadence~0.1ms 无 >400ms 静默、v3
 *   簇分割 ttftClusterMs=null）：高频动画→低频响应 token，密度下跃检出（v4 补 v3 缺口）。
 *
 * 诚实边界：启发式，密度跃变≠精确首字；数据不足/无跃变=null（R-10 绝不折 0，不为出数凑值）。
 */
class ObsStatsDensityTest {

    private fun stats() = ObsSessionStats(pkg = "t", specId = null, observeStartNanos = 0L).also {
        // D-56 发送场景门控：模拟会话曾有真实输入活动（打字），使 TTFT 代理获发送语义。
        // 时戳 -1 早于所有用例的正时戳，onInputBoxText 不落桶、仅置位+重置簇窗（无副作用）。
        it.onInputBoxText(1, -1L)
    }

    private val ms = 1_000_000L

    /**
     * (a) DeepSeek 型：思考期动画高频稳态 → 流式响应低频 token = **密度下跃检出**。
     * 同时确认 v3 簇分割在此栈失效（ttftClusterMs=null）——v4 正是补此缺口。
     */
    @Test
    fun `animation steady high-freq to streaming drop is detected`() {
        val s = stats()
        // 思考期动画：1000~2000ms，5ms 高频 cadence（每 100ms 桶 20 事件，200ms 窗密度 40）
        var t = 1000L
        while (t < 2000L) {
            s.onContentDelta(t * ms)
            t += 5
        }
        // 流式响应：2000ms 起，100ms token cadence（每 200ms 窗仅 2 事件 → ≤基线×0.5）
        t = 2000L
        while (t < 3000L) {
            s.onContentDelta(t * ms)
            t += 100
        }
        val snap = s.snapshot(3500 * ms)
        // 基线(前5窗)=动画40；响应窗=2 ≤ 40×0.5 且基线≥4 → 下跃。窗10 起点距簇首(1000)=1000ms
        assertNotNull("动画→响应密度下跃应检出", snap.ttftDensityMs)
        assertEquals(1000.0, snap.ttftDensityMs!!, 0.001)
        assertEquals("检出即标注来源 density", ObsSessionStats.SOURCE_DENSITY, snap.densityAnchorSource)
        // v3 簇分割靠 >400ms 静默——动画无静默 + 响应 100ms 也无静默 → 恒 null（v4 补此缺口）
        assertNull("DeepSeek 栈 v3 簇分割失效", snap.ttftClusterMs)
    }

    /**
     * (b) 豆包型：思考期 UI 静止（无内容事件）→ 响应上屏 = **密度上跃检出**，且与 v3 簇分割
     * 同方向、同量级（1900ms）——两法一致。
     */
    @Test
    fun `doubao static thinking then response is detected and agrees with v3`() {
        val s = stats()
        // 发送后气泡上屏：1000ms 起 3 事件 8ms（桶0 突发）
        s.onContentDelta(1000 * ms)
        s.onContentDelta(1008 * ms)
        s.onContentDelta(1016 * ms)
        // 思考静默：1016~2900ms 无内容事件（>400ms → v3 也分簇）
        // 响应：2900ms 起，100ms cadence
        var t = 2900L
        while (t <= 3500L) {
            s.onContentDelta(t * ms)
            t += 100
        }
        val snap = s.snapshot(3600 * ms)
        // 基线(前5窗)=median{3,0,0,0,0}=0；响应窗=2 ≥ 最小跃变计数2 → 上跃。窗19 起点=1900ms
        assertNotNull("静止思考→响应密度上跃应检出", snap.ttftDensityMs)
        assertEquals(1900.0, snap.ttftDensityMs!!, 0.001)
        // v3 簇分割：首簇起1000→静默>400ms→次簇起2900 = 1900ms，v4 与之一致方向/量级
        assertEquals("v4 与 v3 一致", 1900.0, snap.ttftClusterMs!!, 0.001)
    }

    /** (c) 纯稳态（均匀 100ms cadence，无思考→响应结构切换）= 无跃变 → null（R-10）。 */
    @Test
    fun `pure steady cadence yields null`() {
        val s = stats()
        var t = 1000L
        repeat(30) { // 每桶1事件、每窗密度2、基线2<下跃最小基线4 → 既不上跃也不下跃
            s.onContentDelta(t * ms)
            t += 100
        }
        // snapshot@4000ms 恰覆盖 30 桶（末事件@3900），无尾部空桶；全窗稳态 → null
        assertNull("纯稳态无跃变=未测（R-10 绝不折 0）", s.snapshot(4000 * ms).ttftDensityMs)
    }

    /** (d) 数据不足（完整滑窗数 <基线窗数+1）/ 无内容事件 = null（R-10）。 */
    @Test
    fun `insufficient data yields null`() {
        val s = stats()
        s.onContentDelta(1000 * ms)
        s.onContentDelta(1100 * ms)
        s.onContentDelta(1200 * ms)
        // elapsed 300ms → 3 完整桶 → 2 窗 < 6（=基线5+1）→ 数据不足
        assertNull("完整滑窗数<K+1=数据不足", s.snapshot(1300 * ms).ttftDensityMs)
        // 无任何内容事件 → 无窗格原点 → null
        assertNull("无内容事件=未测", stats().snapshot(5000 * ms).ttftDensityMs)
    }

    /**
     * (e) 发送锚点（真实打字，textLen>0）重置后**重新起窗**：重置前的杂内容事件（App 打开渲染）
     * 不污染窗格；且响应期 len=0 输入轨事件（DeepSeek 无 text 载荷 TEXT_CHANGED）不误重置。
     */
    @Test
    fun `input reset restarts density window`() {
        val s = stats()
        // 重置前的杂内容事件（App 打开渲染）：100~500ms 高频，若不重置会污染基线/锚点
        var t = 100L
        while (t < 500L) {
            s.onContentDelta(t * ms)
            t += 5
        }
        // 用户真实打字（textLen>0）→ 清桶重置密度窗格（v3.2 守卫：仅 textLen>0 重置）
        s.onInputBoxText(5, 600 * ms)
        // 发送后干净的豆包型流：气泡@1000 + 静默 + 响应@2900
        s.onContentDelta(1000 * ms)
        s.onContentDelta(1008 * ms)
        s.onContentDelta(1016 * ms)
        t = 2900L
        while (t <= 3500L) {
            s.onContentDelta(t * ms)
            // 响应中途一次 len=0 输入轨事件：v3.2 守卫，不得清窗（否则密度谱永不闭合）
            if (t == 3000L) s.onInputBoxText(0, 3000 * ms)
            t += 100
        }
        // 锚点=重置后首事件1000ms（非重置前100ms），跃变@2900 → 1900ms
        assertEquals(1900.0, s.snapshot(3600 * ms).ttftDensityMs!!, 0.001)
    }

    /**
     * (f-1) 基线偏离阈值边界（**含**）：某窗密度=基线×2 恰判上跃。
     * 构造：桶0..5 各 2 事件 → 前5窗密度均4、基线=4；桶6=6 → 窗5=桶5+桶6=2+6=8=2×4 → 上跃@500ms。
     */
    @Test
    fun `baseline deviation boundary inclusive at 2x`() {
        val s = stats()
        fillBucket(s, 0, 2)
        fillBucket(s, 1, 2)
        fillBucket(s, 2, 2)
        fillBucket(s, 3, 2)
        fillBucket(s, 4, 2)
        fillBucket(s, 5, 2)
        fillBucket(s, 6, 6) // 窗5=2+6=8=2×基线4（含=判跃变）
        fillBucket(s, 7, 2)
        fillBucket(s, 8, 2)
        // snapshot@1900ms → elapsed900 → 9完整桶 → 窗0..7；窗5 首个跃变 → 500ms
        assertEquals(500.0, s.snapshot(1900 * ms).ttftDensityMs!!, 0.001)
    }

    /**
     * (f-2) 基线偏离阈值边界（**不含**）：某窗密度=基线×2−1 不判跃变，全程稳态 → null（不为出数凑值）。
     * 构造：桶0..5 各 2、桶6=5 → 窗5=2+5=7<8、窗6=5+2=7<8，余窗稳态4 → 无跃变。
     */
    @Test
    fun `baseline deviation just below 2x yields null`() {
        val s = stats()
        fillBucket(s, 0, 2)
        fillBucket(s, 1, 2)
        fillBucket(s, 2, 2)
        fillBucket(s, 3, 2)
        fillBucket(s, 4, 2)
        fillBucket(s, 5, 2)
        fillBucket(s, 6, 5) // 窗5=2+5=7 < 8=2×基线4 → 不跃
        fillBucket(s, 7, 2)
        fillBucket(s, 8, 2)
        assertNull("窗密度<2×基线 → 不判跃变（R-10 不凑）", s.snapshot(1900 * ms).ttftDensityMs)
    }

    /**
     * 在第 k 个 100ms 步桶（锚点=首事件@1000ms）内放 count 个内容事件，均落于
     * [1000+k*100, 1000+(k+1)*100)（桶内 1ms 间隔，count<100 保证同桶）。首次调用（桶0）
     * 落的首事件即置密度窗格原点。测试须按桶序 0,1,2… 调用以保证锚点=1000ms。
     */
    private fun fillBucket(s: ObsSessionStats, k: Int, count: Int) {
        for (j in 0 until count) s.onContentDelta((1000L + k * 100 + j) * ms)
    }
}
