package com.aneb.probe.engine

/**
 * RTT 主导度自检（spec/PROFILE2_THROUGHPUT_PROBE_SPEC.md §8.3.3，T47 批②，D-468/D-469）。
 * 判据：`ratio = windowActualMs / rttRefMs ≥ RTT_DOMINANCE_MIN`，且窗口时长/字节数不低于
 * 各自下限（三条件交集，AND 不是 OR）——用于判断一次固定时长窗口传输是否"结构上不属于
 * 时延主导"，是把 D-363 一次性叙事分析（耗时÷RTT倍数）变成运行期可执行代码的落地。
 *
 * 三个常量均为大脑 D-469 裁定 PROVISIONAL 记入的建议默认值，批③真机数据后正式拍板
 * （spec §8.7-2），不是最终值。纯 JVM、无 Android 依赖。
 */
object RttDominanceGuard {

    /** D-363 实测最高历史值是 s3 的 9.8×，10 是在其上留安全边际的整数取值。PROVISIONAL。 */
    const val RTT_DOMINANCE_MIN = 10.0

    /** 防止 RTT 极小时 `10×RTT` 退化到计时器/线程调度抖动量级。PROVISIONAL。 */
    const val ABS_FLOOR_MS = 300.0

    /** 即便 duration≫RTT 结构性成立，字节数过少时 goodput 数字本身噪声也可能过大。PROVISIONAL。 */
    const val MIN_BYTES_FLOOR = 100L * 1024L // 100KB

    data class DominanceVerdict(
        /** 三条件交集是否全部满足 */
        val ok: Boolean,
        /** windowActualMs / rttRefMs；rttRefMs 不可用时为 null */
        val ratio: Double?,
    )

    /**
     * @param windowActualMs 实测窗口时长（ms）
     * @param rttRefMs 传输前测得的 RTT 基准（ms）；null = RTT 探测失败，视为不安全（不猜）
     * @param bytesTransferred 窗口内实际传输字节数
     */
    fun evaluate(windowActualMs: Double, rttRefMs: Double?, bytesTransferred: Long): DominanceVerdict {
        if (rttRefMs == null || rttRefMs <= 0.0) {
            return DominanceVerdict(ok = false, ratio = null)
        }
        val ratio = windowActualMs / rttRefMs
        val ok = ratio >= RTT_DOMINANCE_MIN &&
            windowActualMs >= ABS_FLOOR_MS &&
            bytesTransferred >= MIN_BYTES_FLOOR
        return DominanceVerdict(ok, ratio)
    }
}
