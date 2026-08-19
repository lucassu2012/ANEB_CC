package com.aneb.probe.ui

import kotlin.math.ceil
import kotlin.math.max
import kotlin.math.roundToInt

/**
 * 仪表/火花线的纯计算（抽取自 SpeedTestScreen / HomeScreen 内联实现，**行为逐位一致**）：
 * 量程自适应、指针分数、峰值累积、火花线归一、ITL→平滑度映射。composable 只保留绘制，
 * 数值全走此处（spine-4 §4.1；同 [com.aneb.probe.engine.SpeedSampleMath] / LiveTelemetry.derive 抽取惯例）。
 *
 * R-10 红线：无测量值（null）**不得驱动几何显示为"满/优"**——pingFraction(null)=0、
 * gaugeFraction(null)=0（指针停底），文本层另行显"—"。
 */
object GaugeMath {

    /** 量程自适应：随峰值上探 15% 后向上取整到 [roundTo]，下限 [min]。 */
    fun autoGaugeMax(peak: Float, min: Float = 20f, roundTo: Float = 10f): Float =
        max(min, ceil((peak * 1.15f) / roundTo) * roundTo)

    /** 吞吐指针分数 0..1；null→0（R-10：不显"满"）。 */
    fun gaugeFraction(value: Double?, gaugeMax: Float): Float =
        ((value ?: 0.0).toFloat() / gaugeMax).coerceIn(0f, 1f)

    /** ping 指针分数：RTT→0..1（0..[fullAtMs]，越低越满）；null→0（R-10：不显"优"）。 */
    fun pingFraction(rttMs: Double?, fullAtMs: Float = 200f): Float =
        if (rttMs == null) 0f else (1f - (rttMs.toFloat() / fullAtMs)).coerceIn(0f, 1f)

    /** 峰值单调累积；样本 null 保持原值（起测清零由调用方做）。 */
    fun peak(prev: Float, sample: Float?): Float =
        if (sample != null && sample > prev) sample else prev

    /** 火花线归一：vmax 归一（下限 1 防除小数放大噪声）；<2 点→空（不画）。 */
    fun sparklineNormalize(values: List<Float>): List<Float> {
        if (values.size < 2) return emptyList()
        val vmax = max(1f, values.max())
        return values.map { it / vmax }
    }

    /** ITL(ms)→流式平滑度 0.05..1（1=丝滑，[ceilingMs] 及以上封底 0.05——保留可见 hairline）。 */
    fun itlToSmoothness(itlMs: Double, ceilingMs: Double = 1000.0): Float =
        (1.0 - itlMs / ceilingMs).coerceIn(0.05, 1.0).toFloat()

    /** 首页原地仪表读数投影（T45，接活 [com.aneb.probe.ui.HomeGaugeMetric]）。 */
    /**
     * 结果页半盘的"有无读数"判定（R-10 几何侧）。
     *
     * 半盘上 `fraction = 0f` 不是"空"——它是**最左端刻度＝最差**这个有意义的位置。
     * 因此 AQS 不可计算（null）时必须走 [HalfGauge] 的 `idle`（只画灰轨灰刻度、
     * 不画指针/进度弧/hub），而不能把 0 当"没有"画上去，否则"没测出来"会被渲染成
     * "测出来很差"。中心文字侧早已显 "—"，本判定让几何与文字同口径。
     *
     * 抽成纯函数而非留在 Composable 内联表达式里，是为了让它可被单测钉住
     * （渲染层无 createComposeRule，内联表达式无人能守）。
     */
    fun resultGaugeIsIdle(aqsScore: Double?): Boolean = aqsScore == null

    /** 结果页半盘弧位：仅在有读数时有意义；无读数时调用方须传 idle=true 使其不被绘制。 */
    fun resultGaugeFraction(aqsScore: Double?): Float =
        ((aqsScore?.toFloat() ?: 0f) / 100f).coerceIn(0f, 1f)

    data class GaugeReadout(val fraction: Float, val centerVal: String, val centerLabel: String)

    /**
     * 按选中核心量投影仪表读数。AQS 有自然 0–100 量程，直接驱动弧位（复用 [gaugeFraction]，
     * 与既有 R-10 null→0 语义一致）；TTFT/ITL 是无界延迟值，没有现成量程可套——弧位沿用
     * [autoFrac]（继续表达"传输活跃度"），只换中心文字，不为它们发明可能误导的新刻度。
     */
    fun homeGaugeReadout(
        metric: HomeGaugeMetric,
        autoFrac: Float,
        autoVal: String,
        autoLabel: String,
        aqsRunning: Double?,
        ttftMs: Double?,
        itlMedianMs: Double?,
    ): GaugeReadout = when (metric) {
        HomeGaugeMetric.Auto -> GaugeReadout(autoFrac, autoVal, autoLabel)
        HomeGaugeMetric.Aqs -> GaugeReadout(
            fraction = gaugeFraction(aqsRunning, 100f),
            centerVal = aqsRunning?.roundToInt()?.toString() ?: "…",
            centerLabel = "AQS",
        )
        HomeGaugeMetric.Ttft -> GaugeReadout(autoFrac, ttftMs?.let { "%.0f".format(it) } ?: "…", "首字延迟 ms")
        HomeGaugeMetric.Itl -> GaugeReadout(autoFrac, itlMedianMs?.let { "%.0f".format(it) } ?: "…", "ITL 中位 ms")
    }
}

/**
 * 首页原地仪表的核心量切换（T45，接活已删除的旧"测试中"屏遗留的 `GaugeMetric` 死代码，D-462；
 * 该屏本体已随 T48/批A 整屏删除，此枚举是它唯一存活下来的设计遗产）。
 * 未直接复用旧屏的 `GaugeMetric`：这里多一个 [Auto]（默认，逐字复刻改造前行为）。
 */
enum class HomeGaugeMetric(val label: String) {
    Auto("自动"), Aqs("AQS"), Ttft("首字延迟"), Itl("ITL"),
}
