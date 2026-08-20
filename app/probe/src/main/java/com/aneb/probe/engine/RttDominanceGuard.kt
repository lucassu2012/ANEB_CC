package com.aneb.probe.engine

/**
 * RTT 主导度自检（spec/PROFILE2_THROUGHPUT_PROBE_SPEC.md §8.3.3，T47 批②，D-468/D-469）。
 * 判据：`ratio = windowActualMs / rttRefMs ≥ RTT_DOMINANCE_MIN`，且窗口时长/字节数不低于
 * 各自下限（三条件交集，AND 不是 OR）——用于判断一次固定时长窗口传输是否"结构上不属于
 * 时延主导"，是把 D-363 一次性叙事分析（耗时÷RTT倍数）变成运行期可执行代码的落地。
 *
 * 三个常量已由大脑 D-499 正式拍板转正（判据=T63/D-498：489 个真实 RTT 样本的阈值扫描，
 * [10,37] 区间对全部样本判定相同即调整零误拒代价；spec §8.7-2 流程视为走毕）。
 * 日落尾巴：E-01 部署 s4 后首个蜂窝窗做确认性复核，出现 >267ms RTT 样本即回看 D-499。
 * 纯 JVM、无 Android 依赖。
 */
object RttDominanceGuard {

    /**
     * D-499 拍板 10→15：临界 RTT 从 400ms 收紧到 267ms（=window 4000ms ÷ 15）——
     * spec §8.3.3 亲口担心的 350ms 路径在 15 下被拒而 10 下放行；489 真实样本
     * max=106.15ms，[10,37] 区间内零误拒（T63 ③）。历史最高倍数 s3 的 9.8×（D-363）
     * 在 10/15 下判定一致，对取值无区分力（T63 ⑤诚实的否定）。
     */
    const val RTT_DOMINANCE_MIN = 15.0

    /** 防止 RTT 极小时倍数判据退化到计时器/线程调度抖动量级。D-499 转正（4000ms 窗结构性不咬合+真机 underrun 998.4ms 留极端防护）。 */
    const val ABS_FLOOR_MS = 300.0

    /** 字节数过少时 goodput 数字本身不成立。D-499 转正（换算门槛 0.205Mbps 恰挡 D-366 已裁伪影 0.14Mbps，独立提出后吻合=强印证）。 */
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
