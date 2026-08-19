package com.aneb.probe.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * [GaugeMath] 纯计算锚定（spine-4 §4.1 抽取，无 Android）：量程自适应 / 指针分数 /
 * 峰值累积 / 火花线归一 / ITL→平滑度。重点守 R-10——null 测量值不得驱动几何"满/优"。
 */
class GaugeMathTest {

    // ---- autoGaugeMax ----

    @Test
    fun `autoGaugeMax floors at min for zero and tiny peaks`() {
        assertEquals(20f, GaugeMath.autoGaugeMax(0f), 0f)
        assertEquals(20f, GaugeMath.autoGaugeMax(10f), 0f) // 10*1.15=11.5→ceil 到 20，仍=下限
    }

    @Test
    fun `autoGaugeMax rounds up to ten above headroom`() {
        assertEquals(40f, GaugeMath.autoGaugeMax(30f), 0f)      // 34.5 → 40
        assertEquals(30f, GaugeMath.autoGaugeMax(17.4f), 1e-4f) // 20.01 → 30
        assertEquals(110f, GaugeMath.autoGaugeMax(95f), 0f)     // 109.25 → 110
    }

    // ---- gaugeFraction / pingFraction（R-10）----

    @Test
    fun `gaugeFraction null folds to zero not full`() {
        assertEquals(0f, GaugeMath.gaugeFraction(null, 40f), 0f)
    }

    @Test
    fun `gaugeFraction scales and clamps`() {
        assertEquals(0.5f, GaugeMath.gaugeFraction(20.0, 40f), 1e-6f)
        assertEquals(1f, GaugeMath.gaugeFraction(80.0, 40f), 0f) // 超量程 clamp 1
    }

    @Test
    fun `pingFraction null is zero never excellent`() {
        assertEquals(0f, GaugeMath.pingFraction(null), 0f)
    }

    @Test
    fun `pingFraction lower rtt is fuller and clamps at both ends`() {
        assertEquals(1f, GaugeMath.pingFraction(0.0), 0f)
        assertEquals(0.5f, GaugeMath.pingFraction(100.0), 1e-6f)
        assertEquals(0f, GaugeMath.pingFraction(200.0), 0f)
        assertEquals(0f, GaugeMath.pingFraction(300.0), 0f) // 超界 clamp 0
    }

    // ---- peak ----

    @Test
    fun `peak is monotonic and ignores null`() {
        var p = 0f
        p = GaugeMath.peak(p, 5f)
        p = GaugeMath.peak(p, null) // null 保持
        p = GaugeMath.peak(p, 3f)   // 更小保持
        assertEquals(5f, p, 0f)
        p = GaugeMath.peak(p, 9f)
        assertEquals(9f, p, 0f)
    }

    // ---- sparklineNormalize ----

    @Test
    fun `sparklineNormalize empty below two points`() {
        assertTrue(GaugeMath.sparklineNormalize(listOf(7f)).isEmpty())
    }

    @Test
    fun `sparklineNormalize divides by max with floor one`() {
        assertEquals(listOf(0.5f, 1f), GaugeMath.sparklineNormalize(listOf(5f, 10f)))
        // 全小值：vmax 下限 1，不放大噪声
        assertEquals(listOf(0.2f, 0.4f), GaugeMath.sparklineNormalize(listOf(0.2f, 0.4f)))
    }

    // ---- itlToSmoothness ----

    @Test
    fun `itlToSmoothness maps zero to silky and holds floor at ceiling`() {
        assertEquals(1f, GaugeMath.itlToSmoothness(0.0), 0f)
        assertEquals(0.5f, GaugeMath.itlToSmoothness(500.0), 1e-6f)
        assertEquals(0.05f, GaugeMath.itlToSmoothness(1000.0), 1e-6f) // 封底可见 hairline
        assertEquals(0.05f, GaugeMath.itlToSmoothness(2000.0), 1e-6f)
    }

    // ---- homeGaugeReadout（T45，D-462：首页原地仪表核心量切换）----

    @Test
    fun `homeGaugeReadout auto passes through the caller's projection untouched`() {
        val r = GaugeMath.homeGaugeReadout(
            metric = HomeGaugeMetric.Auto,
            autoFrac = 0.42f, autoVal = "12.3", autoLabel = "上行 Mbps",
            aqsRunning = 77.0, ttftMs = 55.0, itlMedianMs = 9.0,
        )
        assertEquals(0.42f, r.fraction, 0f)
        assertEquals("12.3", r.centerVal)
        assertEquals("上行 Mbps", r.centerLabel)
    }

    @Test
    fun `homeGaugeReadout aqs uses its own 0 to 100 scale not autoFrac`() {
        val r = GaugeMath.homeGaugeReadout(
            metric = HomeGaugeMetric.Aqs,
            autoFrac = 0.9f, autoVal = "ignored", autoLabel = "ignored",
            aqsRunning = 65.0, ttftMs = null, itlMedianMs = null,
        )
        assertEquals(0.65f, r.fraction, 1e-6f) // 65/100，不是 autoFrac 的 0.9
        assertEquals("65", r.centerVal)
        assertEquals("AQS", r.centerLabel)
    }

    @Test
    fun `homeGaugeReadout aqs null folds fraction to zero and text to ellipsis, not autoFrac or 0 text`() {
        val r = GaugeMath.homeGaugeReadout(
            metric = HomeGaugeMetric.Aqs,
            autoFrac = 0.9f, autoVal = "ignored", autoLabel = "ignored",
            aqsRunning = null, ttftMs = null, itlMedianMs = null,
        )
        assertEquals(0f, r.fraction, 0f) // R-10：null 不驱动几何"满"
        assertEquals("…", r.centerVal)   // R-10：null 不伪装成 0
    }

    @Test
    fun `homeGaugeReadout ttft and itl borrow autoFrac for the arc but show their own text`() {
        val ttft = GaugeMath.homeGaugeReadout(
            metric = HomeGaugeMetric.Ttft,
            autoFrac = 0.31f, autoVal = "ignored", autoLabel = "ignored",
            aqsRunning = null, ttftMs = 48.6, itlMedianMs = null,
        )
        assertEquals(0.31f, ttft.fraction, 0f) // 沿用 autoFrac，不发明新刻度
        assertEquals("49", ttft.centerVal)     // 四舍五入，无小数
        assertEquals("首字延迟 ms", ttft.centerLabel)

        val itl = GaugeMath.homeGaugeReadout(
            metric = HomeGaugeMetric.Itl,
            autoFrac = 0.31f, autoVal = "ignored", autoLabel = "ignored",
            aqsRunning = null, ttftMs = null, itlMedianMs = null, // 无值
        )
        assertEquals(0.31f, itl.fraction, 0f)
        assertEquals("…", itl.centerVal) // R-10：无值显省略号，不显 0
        assertEquals("ITL 中位 ms", itl.centerLabel)
    }

    // ---- R-10 呈现层补口（增量守卫，2026-08-19 T48 测试策略第 1 层）----
    // 说明（如实标注冗余边界）：本文件此前**已有** 4 条 homeGaugeReadout 守卫，
    // 其中 `aqs null folds fraction to zero and text to ellipsis` 已钉住 AQS 单点的
    // R-10 语义（突变审计验证：把 `?: "…"` 改成 `?: "0"`，该条与下面第一条同时咬住）。
    // 下面两条只补它们**没覆盖的两处**，不重复既有断言：
    //   ① 已有守卫只测 AQS 一个 metric；TTFT/ITL 在缺失时显什么，此前无人守。
    //   ② 四个核心量的中心副标题是否两两可辨——切换器的可读性前提，此前无人守。

    @Test
    fun `every metric renders missing as ellipsis never as zero`() {
        // 遍历全部 metric：缺失一律不得渲染成 0/0.0（R-10：缺失即缺失，不以 0 顶替）。
        // 覆盖既有守卫的空白面 —— 它只测了 Aqs 一个分支。
        for (m in HomeGaugeMetric.values()) {
            val r = GaugeMath.homeGaugeReadout(
                metric = m,
                autoFrac = 0.42f, autoVal = "…", autoLabel = "Token /秒",
                aqsRunning = null, ttftMs = null, itlMedianMs = null,
            )
            assertTrue(
                "metric=$m 缺失时中心文字为 ${r.centerVal}，不得以 0 顶替（R-10）",
                r.centerVal != "0" && r.centerVal != "0.0" && r.centerVal != "0.00",
            )
        }
        // 三个有量纲的核心量必须显式显省略号（Auto 透传上游文案，不在此列）
        val ellipsisOnly = listOf(HomeGaugeMetric.Aqs, HomeGaugeMetric.Ttft, HomeGaugeMetric.Itl)
        for (m in ellipsisOnly) {
            val r = GaugeMath.homeGaugeReadout(
                metric = m,
                autoFrac = 0.42f, autoVal = "ignored", autoLabel = "ignored",
                aqsRunning = null, ttftMs = null, itlMedianMs = null,
            )
            assertEquals("metric=$m", "…", r.centerVal)
        }
    }

    @Test
    fun `center labels stay pairwise distinct so the switcher stays legible`() {
        // 切换核心量后，用户靠中心副标题判断"现在看的是哪个量"；标题重复＝切换不可读。
        val labels = HomeGaugeMetric.values().map { m ->
            GaugeMath.homeGaugeReadout(
                metric = m,
                autoFrac = 0.42f, autoVal = "v", autoLabel = "Token /秒",
                aqsRunning = 62.0, ttftMs = 350.0, itlMedianMs = 87.0,
            ).centerLabel
        }
        assertEquals("中心副标题不得重复：$labels", labels.size, labels.toSet().size)
    }
}
