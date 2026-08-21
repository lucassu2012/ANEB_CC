package com.aneb.probe.engine

/**
 * KPI 四级分级（agent-qoe-kpi v0.1 门限表，KPI 文档 5.2；实验性）。
 * 接线层适配器——不动 scoring/ 的既有公共 API（门限锚点数字与 AqsScorer 内部表同源 5.2）。
 * 纯 JVM、无 Android 依赖。
 */
object KpiGrading {

    const val EXCELLENT = "excellent"
    const val GOOD = "good"
    const val FAIR = "fair"
    const val POOR = "poor"

    /** 低者优：value < a 优 / < b 良 / <= c 可 / 其余差。 */
    private fun lowBetter(v: Double, a: Double, b: Double, c: Double): String = when {
        v < a -> EXCELLENT
        v < b -> GOOD
        v <= c -> FAIR
        else -> POOR
    }

    /**
     * @param kpiId T1/T2/T3/T4/T5/N1/N2/U1/U2（T5 无门限恒 null）
     * @return 分级串；value=null（失败/缺失）返回 null——绝不给失败样本发分级（R-10）
     */
    fun grade(kpiId: String, value: Double?): String? {
        if (value == null) return null
        return when (kpiId) {
            "T1" -> lowBetter(value, 200.0, 500.0, 1000.0)
            "T2" -> lowBetter(value, 100.0, 200.0, 400.0)
            "T3" -> lowBetter(value, 0.005, 0.02, 0.05)
            "T4" -> when { // 优 = 0（5.2）
                value == 0.0 -> EXCELLENT
                value < 0.002 -> GOOD
                value <= 0.01 -> FAIR
                else -> POOR
            }
            "N1" -> lowBetter(value, 30.0, 60.0, 100.0)
            "N2" -> lowBetter(value, 10.0, 30.0, 80.0)
            "U2" -> lowBetter(value, 150.0, 300.0, 600.0)
            // 阶段 2 C 组（agent-qoe-kpi v0.2，5.2；additive——既有 id 分级不变）
            "C1" -> lowBetter(value, 0.005, 0.02, 0.05) // 会话中断率 0.5/2/5%
            "C2" -> lowBetter(value, 1000.0, 3000.0, 10_000.0) // 切换恢复 1/3/10s（ms）
            "U1" -> when { // 高者优（Mbps）
                value > 20.0 -> EXCELLENT
                value >= 5.0 -> GOOD
                value >= 1.0 -> FAIR
                else -> POOR
            }
            // T47 批①（D-468/D-469）：D1 半成品补齐。25/8/2 门限复用既有值，非新造——
            // 与 AqsScorer.D1_ANCHORS（2.0/8.0/25.0）及 basic_network D1 的
            // QualityTarget(excellent=25.0, good=8.0, fair=2.0) 两处独立既有取值一致。
            "D1" -> when { // 高者优（Mbps）
                value > 25.0 -> EXCELLENT
                value >= 8.0 -> GOOD
                value >= 2.0 -> FAIR
                else -> POOR
            }
            else -> null // T5 等不设门限
        }
    }

    // ------------------------------------------------------------------
    // 门限只读出口（T62 批 2，2026-08-22）——供展示层画"门限微刻度"
    // ------------------------------------------------------------------

    /**
     * 一个 KPI 的四档边界（呈现用只读投影）。
     *
     * @param a 优/良 边界；@param b 良/可 边界；@param c 可/差 边界
     * @param lowerBetter true=低者优（时延/比率类）；false=高者优（吞吐类）
     *
     * **权威仍是 [grade]**：本出口只为展示层提供"刻度上画哪三根线"，分级判定一律走
     * [grade]（含 T4"优=恰 0"这类特例——bands 表达不了它，也**不该**表达；标尺只管
     * 边界位置，档位颜色由调用方拿 grade 的结果上色）。
     *
     * **两份数字的漂移风险已被钉死**：`KpiGradingBandsParityTest` 对每个 id 断言
     * grade() 恰在 bands() 声明的边界处翻转（边界值±ε 的档位翻转逐一验）——改 grade()
     * 的字面量而不改这里（或反之），该测试当场红。改门限本身仍属测量语义变更
     * （DECISION_LOG + 红队 + spec §5.2 同步），本出口不改变这一纪律。
     */
    data class Bands(val a: Double, val b: Double, val c: Double, val lowerBetter: Boolean)

    /** [grade] 有门限的 id 的边界；T5 等无门限 id 与未知 id 返回 null。 */
    fun bands(kpiId: String): Bands? = when (kpiId) {
        "T1" -> Bands(200.0, 500.0, 1000.0, lowerBetter = true)
        "T2" -> Bands(100.0, 200.0, 400.0, lowerBetter = true)
        "T3" -> Bands(0.005, 0.02, 0.05, lowerBetter = true)
        "T4" -> Bands(0.0, 0.002, 0.01, lowerBetter = true) // 优=恰 0 的特例在 grade()
        "N1" -> Bands(30.0, 60.0, 100.0, lowerBetter = true)
        "N2" -> Bands(10.0, 30.0, 80.0, lowerBetter = true)
        "U2" -> Bands(150.0, 300.0, 600.0, lowerBetter = true)
        "C1" -> Bands(0.005, 0.02, 0.05, lowerBetter = true)
        "C2" -> Bands(1000.0, 3000.0, 10_000.0, lowerBetter = true)
        "U1" -> Bands(20.0, 5.0, 1.0, lowerBetter = false)
        "D1" -> Bands(25.0, 8.0, 2.0, lowerBetter = false)
        else -> null
    }
}
