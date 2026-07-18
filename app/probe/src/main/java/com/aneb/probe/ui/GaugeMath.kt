package com.aneb.probe.ui

import kotlin.math.ceil
import kotlin.math.max

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
}
