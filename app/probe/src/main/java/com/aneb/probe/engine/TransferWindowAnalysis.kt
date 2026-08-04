package com.aneb.probe.engine

/**
 * 下行慢启动检测（spec/PROFILE2_THROUGHPUT_PROBE_SPEC.md §8.3.4，T47 批②，D-468/D-469）。
 *
 * **新造判据、非移植 [UploadAnalysis.estimateSlowStart]**：`downloadDrain` 按 256KB 上限
 * 读取，实际每次读到的字节数可变（取决于 socket 缓冲区状态），不像上行那样有"固定块大小"
 * 前提，上行的按块计数模型不能直接套用；下行侧客户端本地时间戳已被判定为可信来源
 * （不需要服务端回声），因此改用按滑动时间窗、直接消费 `(累计字节数, 时间戳)` 原始采样
 * 序列的新算法。纯 JVM、无 Android 依赖。
 */
object TransferWindowAnalysis {

    private const val MIN_SAMPLES = 4

    /**
     * 检测方法：先用流末尾 [steadyWindowUs] 估计稳态速率，再用宽度 [probeWindowUs] 的
     * 滑动窗口逐点计算瞬时速率——**只有先观测到低于阈值的瞬时速率、随后才转为达标**，
     * 才判定为一次真实的慢启动爬坡（避免把"从一开始就是稳态"的恒定速率流误判为有爬坡）。
     *
     * @param samples 按 tsNanos 升序的 (cumulativeBytes, tsNanos) 序列
     * @param steadyWindowUs 稳态速率估计窗口（默认取流末尾 1s）
     * @param probeWindowUs 滑动探测窗口（默认 200ms）
     * @param steadyFraction 判定"已达稳态"的速率比例阈值（默认 0.5，对齐 UploadAnalysis 既有取值）
     * @return (slowStartUs, slowStartBytes)；样本不足、无法估计稳态速率、或从未观测到
     *   "先低后高"的转折（例如恒定速率流）时返回 null——excl 口径不出值，绝不猜。
     */
    fun estimateSlowStartByRate(
        samples: List<Pair<Long, Long>>,
        steadyWindowUs: Long = 1_000_000L,
        probeWindowUs: Long = 200_000L,
        steadyFraction: Double = 0.5,
    ): Pair<Long, Long>? {
        if (samples.size < MIN_SAMPLES) return null
        val startBytes = samples.first().first
        val startNs = samples.first().second
        val endNs = samples.last().second

        // ---- 稳态速率：流末尾 steadyWindowUs 的平均速率 ----
        val steadyStartNs = endNs - steadyWindowUs * 1000L
        val steadySamples = samples.filter { it.second >= steadyStartNs }
        if (steadySamples.size < 2) return null
        val steadyBytes = steadySamples.last().first - steadySamples.first().first
        val steadyDurNs = steadySamples.last().second - steadySamples.first().second
        if (steadyDurNs <= 0 || steadyBytes <= 0) return null
        val steadyRate = steadyBytes.toDouble() / steadyDurNs // bytes/ns
        val threshold = steadyRate * steadyFraction

        // ---- 滑动探测：找首个"先低后高"的转折点 ----
        val probeWindowNs = probeWindowUs * 1000L
        var everBelowThreshold = false
        var lo = 0
        for (hi in 1 until samples.size) {
            val hiTs = samples[hi].second
            while (lo < hi && samples[lo].second < hiTs - probeWindowNs) lo++
            val windowNs = hiTs - samples[lo].second
            if (windowNs <= 0) continue
            val windowBytes = samples[hi].first - samples[lo].first
            val instRate = windowBytes.toDouble() / windowNs
            if (instRate < threshold) {
                everBelowThreshold = true
            } else if (everBelowThreshold) {
                val slowStartUs = (hiTs - startNs) / 1000L
                val slowStartBytes = samples[hi].first - startBytes
                return Pair(slowStartUs, slowStartBytes)
            }
        }
        return null // 未观测到"先低后高"的转折——恒定速率流或稳态窗口本身不可信
    }
}
