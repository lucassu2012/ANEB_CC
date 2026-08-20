package com.aneb.probe.ui

import com.aneb.probe.scoring.ReportAnalyzer
import com.aneb.probe.scoring.ReportAnalyzer.Method
import com.aneb.probe.scoring.Validity
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * ReportFormat 纯格式化单测：Markdown/JSON 导出与展示助手。锚定 claim scope 页脚、
 * token 投影"估算"标、null 语义（JSON 出 null 不顶 0）、样本不足引导文案。
 */
class ReportFormatTest {

    private fun summary(
        id: String,
        rtt: Double,
        ttft: Double,
        aqs: Double,
    ) = ReportAnalyzer.RunSummary(
        runId = id,
        transport = "cellular",
        rttMs = rtt,
        ttftMs = ttft,
        upMbps = 10.0,
        aqs = aqs,
        validity = Validity.VALID,
        epochMs = 1_000L + id.hashCode().toLong(),
    )

    /** ≥3 个不同 RTT 条件 → 相关模式（有敏感度发现）。 */
    private fun correlationAnalysis(): ReportAnalyzer.ReportAnalysis {
        val runs = listOf(
            summary("a", rtt = 30.0, ttft = 400.0, aqs = 88.0),
            summary("b", rtt = 90.0, ttft = 900.0, aqs = 74.0),
            summary("c", rtt = 150.0, ttft = 1500.0, aqs = 60.0),
            summary("d", rtt = 210.0, ttft = 2100.0, aqs = 52.0),
        )
        return ReportAnalyzer.analyze(runs)
    }

    @Test
    fun markdownHasClaimScopeAndEstimateMarker() {
        val md = ReportFormat.buildMarkdown(correlationAnalysis())
        assertTrue("含标题", md.contains("敏感度报告"))
        assertTrue("含 claim scope 页脚", md.contains("claim scope"))
        assertTrue("token 投影带估算标", md.contains("派生/估算"))
        assertTrue("含文献锚点 HALO", md.contains("HALO"))
    }

    /**
     * **中止 run 的告诫必须出现在两个导出面上**（T76/D-536 + D-539）。
     *
     * 此前它只在页面（`ReportScreen` 逐条渲染 `conclusions`）与分析器产出上被验过，
     * **markdown / JSON 两个导出面没有任何测试钉它**——而离线读报告的人拿到的恰恰是这两面。
     * 这是「同一事实要在每个读者拿得到的面上都可查」那一族（D-323）：本条把导出面补上。
     */
    @Test
    fun abortedRunCaveatReachesBothExportFaces() {
        val runs = listOf(
            summary("a", rtt = 30.0, ttft = 400.0, aqs = 88.0).copy(runStatus = "aborted:bound_network_lost"),
            summary("b", rtt = 90.0, ttft = 900.0, aqs = 74.0).copy(runStatus = "completed"),
            summary("c", rtt = 150.0, ttft = 1500.0, aqs = 60.0).copy(runStatus = "completed"),
            summary("d", rtt = 210.0, ttft = 2100.0, aqs = 52.0).copy(runStatus = "completed"),
        )
        val a = ReportAnalyzer.analyze(runs)
        assertTrue("markdown 导出面须带该告诫", ReportFormat.buildMarkdown(a).contains("未正常结束"))
        assertTrue("JSON 导出面须带该告诫", ReportFormat.buildJson(a).contains("未正常结束"))
    }

    @Test
    fun allCompletedRunsProduceNoCaveatOnExportFaces() {
        // 配对反例：没有它，上一条可以靠"文案恒在"通过（守卫不得恒响，D-302 同族）。
        val a = correlationAnalysis() // runStatus 全 null（未知）
        assertFalse("无中止证据时 markdown 不得凭空带告诫", ReportFormat.buildMarkdown(a).contains("未正常结束"))
        assertFalse("无中止证据时 JSON 不得凭空带告诫", ReportFormat.buildJson(a).contains("未正常结束"))
    }

    @Test
    fun jsonEmitsNullNotZeroForMissing() {
        val json = ReportFormat.buildJson(correlationAnalysis())
        assertTrue("方法字段", json.contains("\"method\":"))
        assertTrue("claimScope 字段", json.contains("\"claimScope\":"))
        // 无会话中断率实测 → sessionDropRate 应为 null（绝不 0 顶替，R-10）
        assertTrue("中断率缺失出 null", json.contains("\"sessionDropRate\":null"))
        assertFalse("不得把缺失中断率写成 0", json.contains("\"sessionDropRate\":0"))
    }

    @Test
    fun insufficientGuidanceWhenTooFewConditions() {
        val runs = listOf(summary("a", rtt = 30.0, ttft = 400.0, aqs = 88.0))
        val a = ReportAnalyzer.analyze(runs)
        assertTrue(a.method == Method.INSUFFICIENT)
        val g = ReportFormat.insufficientGuidance(a)
        assertTrue("引导文案提示补测", g.contains("不同网络条件"))
        val md = ReportFormat.buildMarkdown(a)
        assertTrue("Markdown 空态含引导", md.contains("样本") || md.contains("网络条件"))
    }

    @Test
    fun findingLineHasDirectionAndMagnitude() {
        val a = correlationAnalysis()
        val fd = a.sensitivity.firstOrNull { it.driver == "rtt" && it.metric == "ttft" }
        requireNotNull(fd)
        val line = ReportFormat.findingLine(fd)
        assertTrue("含自变量名", line.contains("RTT"))
        assertTrue("含因变量名", line.contains("TTFT"))
    }
}
