package com.aneb.probe.engine

import kotlin.math.abs

/**
 * 网络基本性能模式的纯计算（抽取自 [SpeedRunner] 的内联/私有实现，**行为逐位一致**）：
 * 中位数、抖动、0.6s 滑窗吞吐。无 Android/无网络依赖 → JVM 单测直接锚定（见
 * `SpeedSampleMathTest`），与仓内 `LiveTelemetry.derive` 抽取先例同惯例。
 *
 * 口径红线（R-10 诚实缺席）：样本不足以构成合法测量（空序列 / 窗<2 / dS≤0.1s）时返回
 * null，**绝不折 0**——0 Mbps 与"测不出"语义不同，下游据 null 显缺省而非"满/空"。
 */
object SpeedSampleMath {

    /** 中位数；空 → null（R-10）。偶数个取中间两数均值。 */
    fun median(xs: List<Double>): Double? {
        if (xs.isEmpty()) return null
        val s = xs.sorted()
        val n = s.size
        return if (n % 2 == 1) s[n / 2] else (s[n / 2 - 1] + s[n / 2]) / 2.0
    }

    /** 抖动＝相邻样本绝对差的中位数；<2 样本 → null（R-10）。 */
    fun jitter(xs: List<Double>): Double? {
        if (xs.size < 2) return null
        return median(xs.zipWithNext { a, b -> abs(b - a) })
    }

    /**
     * 0.6s 滑窗实时吞吐（Mbps）。**就地维护** [window]：追加当前样本 `(nowNs, nowBytes)`、
     * 淘汰早于 [windowNs] 的队首，再取窗口首尾的字节/时间差分算速率。
     * 窗<2 或 dS≤0.1s → null（R-10，绝不折 0）。
     *
     * 与 [SpeedRunner] 三处滑窗块（run 的下行/上行窗、runShaped 的下行窗）**逐位一致**——
     * 三处内联实现统一抽取至此，单一事实源便于回归锚定。（runShaped 上行是**故意的全程均值**，
     * 非滑窗，见 SpeedRunner 内注释，不走本函数。）
     *
     * @param window 跨采样保持的可变窗口 `(nanoTime, 累计字节)`；本函数追加并淘汰后即为最新状态
     * @param nowNs 当前单调钟纳秒
     * @param nowBytes 当前累计字节
     */
    fun windowMbps(
        window: ArrayDeque<Pair<Long, Long>>,
        nowNs: Long,
        nowBytes: Long,
        windowNs: Long = 600_000_000L,
    ): Double? {
        window.addLast(nowNs to nowBytes)
        while (window.size > 1 && nowNs - window.first().first > windowNs) window.removeFirst()
        val dB = nowBytes - window.first().second
        val dS = (nowNs - window.first().first) / 1e9
        return if (window.size >= 2 && dS > 0.1) dB * 8.0 / dS / 1e6 else null
    }
}
