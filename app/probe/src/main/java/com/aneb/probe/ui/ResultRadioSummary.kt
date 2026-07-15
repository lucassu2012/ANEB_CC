package com.aneb.probe.ui

import com.aneb.probe.data.RadioSampleEntity

/**
 * 专业结果视图"无线层"卡的**只读聚合**（纯 JVM，可单测）。把一次 run 的 1Hz
 * [RadioSampleEntity] 序列压成一组展示值：制式三元组（R-15）+ 注册小区标识 + 信号中位数。
 *
 * ## 红线
 * - **R-10**：信号值（RSRP/RSRQ/SINR）缺失（null）的样本一律**不参与**中位数，绝不以 0 顶替；
 *   无任何有效样本 → 该项 null（展示"—"）。
 * - **R-15**：制式按 {dataNetworkType(协商态), displayInfoOverride(显示态), nr_state} 三元组
 *   原样呈现，外部措辞"设备报告制式"，绝不合并成单一"运营商制式"结论；显示态/协商态分列。
 * - **R-02**：`stale` 样本（modem 时戳陈旧/超时退回缓存）**不参与信号中位数**，仅计数披露。
 *
 * 制式友好标签与 [com.aneb.probe.engine.LiveTelemetry] 派生同口径（NR→5G SA /
 * LTE+nr_connected→5G NSA / LTE→LTE），此处为展示层镜像（纯标签映射，非门限）。
 */
data class ResultRadioSummary(
    /** 友好制式标签（5G SA / 5G NSA / LTE / …）；无注册小区 → null（R-10 不臆造） */
    val ratLabel: String?,
    /** dataNetworkType 名称（协商态，R-15） */
    val networkType: String?,
    /** displayInfoOverride 名称（显示态，R-15）；API<31 或缺失 → null */
    val overrideType: String?,
    /** nr_state（R-15） */
    val nrState: String?,
    val pci: Int?,
    val tac: Int?,
    /** LTE=EARFCN / NR=NRARFCN */
    val arfcn: Int?,
    val rsrpDbm: Int?,
    val rsrqDb: Int?,
    val sinrDb: Int?,
    /** 总采样样本数 */
    val sampleCount: Int,
    /** 陈旧样本数（R-02，不参与信号中位数） */
    val staleCount: Int,
    /** 有注册 LTE/NR 小区的样本数 */
    val registeredCount: Int,
) {
    /** 有任何无线样本可展示 */
    val hasSamples: Boolean get() = sampleCount > 0

    companion object {
        val EMPTY = ResultRadioSummary(
            ratLabel = null, networkType = null, overrideType = null, nrState = null,
            pci = null, tac = null, arfcn = null, rsrpDbm = null, rsrqDb = null, sinrDb = null,
            sampleCount = 0, staleCount = 0, registeredCount = 0,
        )

        fun of(samples: List<RadioSampleEntity>): ResultRadioSummary {
            if (samples.isEmpty()) return EMPTY
            val staleCount = samples.count { it.stale }
            // 信号中位数：仅取非陈旧样本的非空值（R-02 + R-10）
            val fresh = samples.filter { !it.stale }
            val rsrp = medianInt(fresh.mapNotNull { it.rsrp })
            val rsrq = medianInt(fresh.mapNotNull { it.rsrq })
            val sinr = medianInt(fresh.mapNotNull { it.sinr })

            // 制式三元组（R-15）：取最新样本（协商/显示/nr 态三列始终存在）
            val latest = samples.maxByOrNull { it.tsNanos }
            // 注册小区标识：取最新的有注册 LTE/NR 小区的样本（rat != null）
            val registered = samples.filter { it.rat != null }
            val latestReg = registered.maxByOrNull { it.tsNanos }

            return ResultRadioSummary(
                ratLabel = latestReg?.let { ratLabel(it.rat, it.nrState) },
                networkType = latest?.networkType,
                overrideType = latest?.overrideType,
                nrState = latest?.nrState,
                pci = latestReg?.pci,
                tac = latestReg?.tac,
                arfcn = latestReg?.arfcn,
                rsrpDbm = rsrp,
                rsrqDb = rsrq,
                sinrDb = sinr,
                sampleCount = samples.size,
                staleCount = staleCount,
                registeredCount = registered.size,
            )
        }

        /**
         * 友好制式标签（与 LiveTelemetry.derive 同口径；纯标签映射非门限）。
         * NR 注册=5G SA；LTE 注册且 nr_state=connected=5G NSA；否则 LTE/原值；无小区 null。
         */
        internal fun ratLabel(rat: String?, nrState: String?): String? = when (rat) {
            "NR" -> "5G SA"
            "LTE" -> if (nrState == "connected") "5G NSA" else "LTE"
            null -> null
            else -> rat
        }

        /** 整数中位数（偶数取上中位的算术平均取整）；空 → null（R-10 绝不 0 顶替）。 */
        private fun medianInt(xs: List<Int>): Int? {
            if (xs.isEmpty()) return null
            val s = xs.sorted()
            val n = s.size
            return if (n % 2 == 1) s[n / 2] else (s[n / 2 - 1] + s[n / 2]) / 2
        }
    }
}
