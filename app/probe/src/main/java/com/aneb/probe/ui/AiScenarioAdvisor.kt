package com.aneb.probe.ui

/**
 * AI 场景适配建议（BASIC_NETWORK facet4 声明的 `ai_scenario_fitness` 建议模板实现，
 * PROFILE_FRAMEWORK §4.2：「此网络适合 TK-1/2，不适合 TK-4」）。
 *
 * **数据驱动（INV-3 单一事实源）**：门限一律取自 [TestModeProfiles.TOKEN_EXPERIENCE] 的
 * facet2 [MetricSpec.target]（N1/N2 良锚、U1/D1 的 perPayloadBand 良锚），子场景清单取自其
 * facet1 [SubScenario]——本层只声明「哪个 TK 用哪档 band」，不复制任何阈值数字。
 *
 * 口径（诚实边界）：输入是基本性能模式实测的**峰值**吞吐与 echo 时延（观测展示口径，
 * 非 AQS/KPI）；峰值高估持续吞吐，判定标注"按峰值"。测量缺失（null）→ 判定 null
 * （无法判定，R-10 不编造）。纯 JVM 可单测。
 */
object AiScenarioAdvisor {

    /** 单条判定：[suitable] null=测量不足无法判定。 */
    data class Verdict(
        val code: String,
        val title: String,
        val suitable: Boolean?,
        /** 需求对照（含实测值与 ✓/✗），可读 */
        val requirement: String,
    )

    private class Req(
        val label: String,
        val measured: Double?,
        val threshold: Double,
        val higherBetter: Boolean,
        val unit: String,
    ) {
        val met: Boolean? = measured?.let { if (higherBetter) it >= threshold else it <= threshold }
        fun text(): String {
            val cmp = if (higherBetter) "≥" else "≤"
            val m = measured?.let { "%.1f".format(it) } ?: "—"
            val mark = when (met) { true -> "✓"; false -> "✗"; null -> "?" }
            return "$label$cmp${trim(threshold)}$unit(实测$m$mark)"
        }

        private fun trim(v: Double) = if (v == v.toLong().toDouble()) v.toLong().toString() else "%.1f".format(v)
    }

    /**
     * @param downMbps 实测下行峰值（Mbps）；未测 null
     * @param upMbps 实测上行峰值（Mbps）；未测 null
     * @param rttMs 实测 RTT 中位（ms）；未测 null
     * @param jitterMs 实测抖动（ms）；未测 null
     * @return 按 TOKEN_EXPERIENCE 子场景顺序的判定表
     */
    fun advise(
        downMbps: Double?,
        upMbps: Double?,
        rttMs: Double?,
        jitterMs: Double?,
        token: TestModeProfile = TestModeProfiles.TOKEN_EXPERIENCE,
    ): List<Verdict> {
        val specs = token.metricSpecs.associateBy { it.id }
        fun good(id: String): Double? = specs[id]?.target?.good
        fun bandGood(id: String, band: String): Double? = specs[id]?.target?.perPayloadBand?.get(band)?.good

        val n1 = good("N1") ?: return emptyList()
        val n2 = good("N2") ?: return emptyList()
        val u1Generic = good("U1") ?: return emptyList()
        val u1MB = bandGood("U1", "MB") ?: u1Generic
        val u1Img = bandGood("U1", "10MB") ?: u1Generic
        val u1Video = bandGood("U1", "100MB") ?: u1Generic
        val d1Generic = good("D1") ?: return emptyList()
        val d1Img = bandGood("D1", "10MB") ?: d1Generic
        val d1Video = bandGood("D1", "100MB") ?: d1Generic

        fun rtt() = Req("RTT", rttMs, n1, higherBetter = false, unit = "ms")
        fun jit() = Req("抖动", jitterMs, n2, higherBetter = false, unit = "ms")
        fun up(th: Double) = Req("上行", upMbps, th, higherBetter = true, unit = "Mbps")
        fun down(th: Double) = Req("下行", downMbps, th, higherBetter = true, unit = "Mbps")

        // 哪个 TK 用哪档 band（场景→档位的选路属场景知识；阈值本身全部来自 profile facet2）
        val reqsByCode: Map<String, List<Req>> = mapOf(
            "TK-1" to listOf(rtt(), jit()),
            "TK-2" to listOf(up(u1MB), rtt()),
            "TK-3" to listOf(up(u1Img), down(d1Img)),
            "TK-4" to listOf(up(u1Video), down(d1Video)),
            "TK-5" to listOf(down(d1Img)),
            "TK-6" to listOf(rtt(), jit(), up(u1Generic)),
        )

        val subScenarios = token.businessType?.subScenarios.orEmpty()
        return subScenarios.mapNotNull { sc ->
            val reqs = reqsByCode[sc.code] ?: return@mapNotNull null
            val suitable: Boolean? = when {
                reqs.any { it.met == false } -> false // 任一实测未达标即不适合（缺测项不阻断否定结论）
                reqs.all { it.met == true } -> true
                else -> null // 无否定证据但有缺测 → 无法判定
            }
            Verdict(
                code = sc.code,
                title = sc.title,
                suitable = suitable,
                requirement = reqs.joinToString("、") { it.text() },
            )
        }
    }
}
