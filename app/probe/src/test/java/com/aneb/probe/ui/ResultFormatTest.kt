package com.aneb.probe.ui

import com.aneb.probe.data.ScenarioResultEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.engine.KpiGrading
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Locale

/**
 * P1-C07 结果页/导出纯逻辑单测：AQS 分级边界（5.4）、per-KPI 低置信标注、
 * 双口径并列展示、CSV 场景×KPI 展平与 null 语义（R-10：null 绝不显示为 0）。
 */
class ResultFormatTest {

    private fun scenario(
        profileId: String = "s2_coding_agent",
        repeatIndex: Int = 0,
        validity: String = "valid",
        invalidReasons: String = "",
        lowConfidenceKpis: String = "",
        t1: Double? = 150.0,
        t2: Double? = 80.0,
        u1: Double? = 25.0,
        d1: Double? = null,
        u3: Double? = null,
        u3DominanceOk: Boolean? = null,
        d3: Double? = null,
        d3DominanceOk: Boolean? = null,
    ) = ScenarioResultEntity(
        runId = "run-1",
        profileId = profileId,
        profileVersion = "1.0.0",
        repeatIndex = repeatIndex,
        orderIndex = 0,
        startedAtNanos = 0L,
        endedAtNanos = 1L,
        validity = validity,
        invalidReasons = invalidReasons,
        t1TtftMs = t1, t1Grade = KpiGrading.grade("T1", t1),
        t2ItlP95Ms = t2, t2Grade = KpiGrading.grade("T2", t2),
        t2ItlP95InclCoalescedMs = t2?.let { it + 5.0 },
        t3StallRate = 0.001, t3Grade = KpiGrading.grade("T3", 0.001),
        t3StallRateInclResume = 0.002,
        t4SevereStallRate = 0.0, t4Grade = KpiGrading.grade("T4", 0.0),
        t5ResumeP95Ms = null,
        n1RttP50Ms = 20.0, n1Grade = KpiGrading.grade("N1", 20.0),
        n2JitterMs = 5.0, n2Grade = KpiGrading.grade("N2", 5.0),
        u1GoodputMbps = u1, u1Grade = KpiGrading.grade("U1", u1),
        u1GoodputExclSlowStartMbps = u1?.let { it + 2.0 },
        u2ToolLoopP95Ms = 120.0, u2Grade = KpiGrading.grade("U2", 120.0),
        d1GoodputMbps = d1, d1Grade = KpiGrading.grade("D1", d1),
        u3GoodputMbps = u3, u3RttDominanceOk = u3DominanceOk,
        d3GoodputMbps = d3, d3RttDominanceOk = d3DominanceOk,
        seqGapCount = 0,
        seqDupCount = 0,
        lowConfidenceKpis = lowConfidenceKpis,
        offsetStartUs = 100L, offsetStartErrUs = 10L,
        offsetEndUs = 110L, offsetEndErrUs = 10L,
        offsetDriftPpm = 12.34,
        offsetSuspect = false,
        netTransport = "auto(wifi)",
        netCapabilities = "caps",
        netInterfaceName = "wlan0",
        serverObservedAddr = "1.2.3.4:5678",
        parseDurUsTotal = 1000L,
        perEventParseUs = 2.0,
    )

    private fun run() = TestRun(
        runId = "run-1",
        startedAtEpochMs = 1_752_000_000_000L,
        serverBase = "http://10.0.2.2:8443",
        mode = "quick",
        scenarioOrder = "s1_chat,s2_coding_agent,s3_multimodal",
        transport = "auto",
        kpiSet = "agent-qoe-kpi-v0.2",
        aqsVersion = "aqs-v0.1",
        profileVersions = "s1_chat:1.0.0",
        schemaVersion = "1.0",
        profileSource = "server",
        appVersionName = "0.1.0",
        appVersionCode = 1L,
        guardMetadata = null,
        aqsScore = 88.5,
        aqsLowConfidence = false,
        aqsVetoApplied = false,
        aqsNotComputableReason = null,
        status = "completed",
        reportStatus = "http=200",
    )

    // ---- AQS 分级边界（5.4：≥85 优 / 70–85 良 / 55–70 可 / <55 差） ----

    @Test
    fun aqsGradeBoundaries() {
        assertEquals(KpiGrading.EXCELLENT, ResultFormat.aqsGrade(85.0))
        assertEquals(KpiGrading.EXCELLENT, ResultFormat.aqsGrade(100.0))
        assertEquals(KpiGrading.GOOD, ResultFormat.aqsGrade(84.99))
        assertEquals(KpiGrading.GOOD, ResultFormat.aqsGrade(70.0))
        assertEquals(KpiGrading.FAIR, ResultFormat.aqsGrade(69.99))
        assertEquals(KpiGrading.FAIR, ResultFormat.aqsGrade(55.0))
        assertEquals(KpiGrading.POOR, ResultFormat.aqsGrade(54.99))
        assertEquals(KpiGrading.POOR, ResultFormat.aqsGrade(0.0))
    }

    @Test
    fun gradeLabels() {
        assertEquals("优", ResultFormat.gradeLabel(KpiGrading.EXCELLENT))
        assertEquals("良", ResultFormat.gradeLabel(KpiGrading.GOOD))
        assertEquals("可", ResultFormat.gradeLabel(KpiGrading.FAIR))
        assertEquals("差", ResultFormat.gradeLabel(KpiGrading.POOR))
        assertEquals("—", ResultFormat.gradeLabel(null))
    }

    // ---- KPI 行：双口径并列 + 低置信标注 ----

    @Test
    fun kpiRowsContainDualViewRows() {
        val rows = ResultFormat.kpiRows(scenario())
        val ids = rows.map { it.id }
        // 双口径并列（KPI 文档 5.1）：T2 剔/含 coalesced、T3 剔/含 resume、U1 含/剔慢启动
        assertTrue("T2_incl_coalesced" in ids)
        assertTrue("T3_incl_resume" in ids)
        assertTrue("U1_excl_slow_start" in ids)
        // 并列口径行不给分级（防误读为评级结论）
        assertNull(rows.first { it.id == "T2_incl_coalesced" }.grade)
        assertNull(rows.first { it.id == "U1_excl_slow_start" }.grade)
        // 主口径行有分级
        assertEquals(KpiGrading.EXCELLENT, rows.first { it.id == "T2" }.grade)
    }

    @Test
    fun kpiRowsIncludeD1WithSharedThresholds() {
        // T47 批①（D-468/D-469）：D1 半成品补齐——此前 wire 上线但结果页无渲染（D-276 反模式）
        val rows = ResultFormat.kpiRows(scenario(d1 = 30.0))
        val d1 = rows.first { it.id == "D1" }
        assertEquals(30.0, d1.value!!, 1e-9)
        assertEquals(KpiGrading.EXCELLENT, d1.grade) // 门限复用 KpiGrading（25/8/2），非新造
    }

    @Test
    fun kpiRowsD1NullRendersDashNotZero() {
        val rows = ResultFormat.kpiRows(scenario(d1 = null))
        val d1 = rows.first { it.id == "D1" }
        assertNull(d1.value)
        assertNull(d1.grade)
        assertEquals("—", ResultFormat.formatValue(d1)) // R-10：未测出≠0
    }

    @Test
    fun kpiRowsIncludeU3D3AsUngradedDiagnostics() {
        // T48/批B（D-469 8-5：展示型诊断，不进 AQS）——U3/D3 必须永不带分级，
        // 防止一个诊断值被读成正式 KPI 评级（同 T5 的"不进 AQS"先例）。
        val rows = ResultFormat.kpiRows(scenario(u3 = 40.0, d3 = 300.0))
        val u3 = rows.first { it.id == "U3" }
        val d3 = rows.first { it.id == "D3" }
        assertEquals(40.0, u3.value!!, 1e-9)
        assertNull(u3.grade)
        assertEquals(300.0, d3.value!!, 1e-9)
        assertNull(d3.grade)
    }

    @Test
    fun kpiRowsU3D3NullRendersDashNotZero() {
        // 绝大多数场景没跑 s4_throughput，null 是常态（R-10：未测出≠0）
        val rows = ResultFormat.kpiRows(scenario())
        val u3 = rows.first { it.id == "U3" }
        val d3 = rows.first { it.id == "D3" }
        assertNull(u3.value)
        assertEquals("—", ResultFormat.formatValue(u3))
        assertNull(d3.value)
        assertEquals("—", ResultFormat.formatValue(d3))
    }

    @Test
    fun kpiRowsU3D3LowConfidenceComesFromRttDominanceNotSampleCount() {
        // Entities.kt 字段注释：sample_count 恒为 1 是结构性事实非低样本量信号，
        // U3/D3 的低置信判据是 rtt_dominance_ok，不是通用 lowConfidenceKpis 词表
        // （即便 lowConfidenceKpis 完全不提 U3/D3，dominance=false 时仍须标注）。
        val rows = ResultFormat.kpiRows(
            scenario(u3 = 40.0, u3DominanceOk = false, d3 = 300.0, d3DominanceOk = true, lowConfidenceKpis = ""),
        )
        assertTrue(rows.first { it.id == "U3" }.lowConfidence)
        assertFalse(rows.first { it.id == "D3" }.lowConfidence)
    }

    @Test
    fun lowConfidenceMarksParsedPerKpi() {
        val rows = ResultFormat.kpiRows(scenario(lowConfidenceKpis = "T2,U1_excl_slow_start"))
        assertTrue(rows.first { it.id == "T2" }.lowConfidence)
        assertTrue(rows.first { it.id == "U1_excl_slow_start" }.lowConfidence)
        assertFalse(rows.first { it.id == "T1" }.lowConfidence)
    }

    @Test
    fun nullValueRendersDashAndNoGrade() {
        val rows = ResultFormat.kpiRows(scenario(t1 = null))
        val t1 = rows.first { it.id == "T1" }
        assertNull(t1.value)
        assertNull(t1.grade)
        assertEquals("—", ResultFormat.formatValue(t1)) // R-10：null 绝不显示为 0
    }

    // ---- run 级 KPI 表（AQS 输入映射镜像：N←S1 / T,U2←S2 / U1←S3） ----

    @Test
    fun runKpiRowsFollowAqsInputMapping() {
        val s1 = scenario(profileId = "s1_chat")
        val s2 = scenario(profileId = "s2_coding_agent", t1 = 300.0)
        val s3 = scenario(profileId = "s3_multimodal", u1 = 8.0, d1 = 12.0)
        val rows = ResultFormat.runKpiRows(listOf(s1, s2, s3))
        val t1 = rows.first { it.row.id == "T1" }
        assertEquals("S2", t1.source)
        assertEquals(300.0, t1.row.value!!, 1e-9)
        val u1 = rows.first { it.row.id == "U1" }
        assertEquals("S3", u1.source)
        assertEquals(8.0, u1.row.value!!, 1e-9)
        val n1 = rows.first { it.row.id == "N1" }
        assertEquals("S1", n1.source)
        // T47 批①（D-468/D-469）：D1 来源场景同 AqsInputMapper 合同 D1←S3
        val d1 = rows.first { it.row.id == "D1" }
        assertEquals("S3", d1.source)
        assertEquals(12.0, d1.row.value!!, 1e-9)
    }

    @Test
    fun runKpiRowsForensicMedianSkipsNullRepeats() {
        // 取证 3 遍：一遍 INVALID（值 null）→ 只聚合有效遍（5.3.6/R-10）
        val a = scenario(profileId = "s2_coding_agent", repeatIndex = 0, t1 = 100.0)
        val b = scenario(profileId = "s2_coding_agent", repeatIndex = 1, t1 = null, validity = "invalid")
        val c = scenario(profileId = "s2_coding_agent", repeatIndex = 2, t1 = 200.0)
        val rows = ResultFormat.runKpiRows(listOf(a, b, c))
        // percentileOrNull([100,200], 0.5) = ceil(0.5*2)=1 → sorted[0] = 100
        assertEquals(100.0, rows.first { it.row.id == "T1" }.row.value!!, 1e-9)
    }

    // ---- CSV：场景×KPI 展平 ----

    @Test
    fun csvFlattensScenarioByKpi() {
        val scenarios = listOf(
            scenario(profileId = "s1_chat"),
            scenario(profileId = "s2_coding_agent"),
        )
        val csv = ResultFormat.buildCsv(run(), scenarios)
        val lines = csv.trim().split('\n')
        assertEquals(ResultFormat.CSV_HEADER, lines[0])
        // 每场景 15 个 KPI 行（含双口径并列项；T47 批①/D-468 起含 D1；T48/批B 起含 U3/D3 诊断行）
        assertEquals(1 + 2 * 15, lines.size)
        // 每行列数与表头一致
        val cols = ResultFormat.CSV_HEADER.split(',').size
        lines.forEach { assertEquals(cols, it.split(',').size) }
        assertTrue(lines[1].startsWith("run-1,quick,agent-qoe-kpi-v0.2,aqs-v0.1,s1_chat,"))
    }

    @Test
    fun csvNullValueIsEmptyNeverZero() {
        val csv = ResultFormat.buildCsv(run(), listOf(scenario(t1 = null)))
        val t1Line = csv.trim().split('\n').first { ",T1," in it }
        val cells = t1Line.split(',')
        val valueIdx = ResultFormat.CSV_HEADER.split(',').indexOf("value")
        val gradeIdx = ResultFormat.CSV_HEADER.split(',').indexOf("grade")
        assertEquals("", cells[valueIdx])
        assertEquals("", cells[gradeIdx])
    }

    @Test
    fun csvEscapesReservedChars() {
        assertEquals("plain", ResultFormat.csvEscape("plain"))
        assertEquals("\"a,b\"", ResultFormat.csvEscape("a,b"))
        assertEquals("\"a\"\"b\"", ResultFormat.csvEscape("a\"b"))
        // invalid_reasons 含逗号（多原因码）时整字段加引号，不破坏列结构
        val csv = ResultFormat.buildCsv(
            run(),
            listOf(scenario(validity = "invalid", invalidReasons = "PATH_CHANGED,GUARD_FAILED", t1 = null)),
        )
        assertTrue(csv.contains("\"PATH_CHANGED,GUARD_FAILED\""))
    }

    // ---- locale 回归（C07 评审修复）：数值格式固定 Locale.ROOT ----

    @Test
    fun csvNumberFormatIsLocaleIndependent() {
        val prev = Locale.getDefault()
        try {
            // 逗号小数区域：未固定 locale 时 "%.2f" 会输出 "12,34"，
            // 触发 csvEscape 加引号并破坏机器解析口径
            Locale.setDefault(Locale.GERMANY)
            val csv = ResultFormat.buildCsv(run(), listOf(scenario()))
            val lines = csv.trim().split('\n')
            val header = ResultFormat.CSV_HEADER.split(',')
            val driftIdx = header.indexOf("offset_drift_ppm")
            // offsetDriftPpm=12.34 → 恒点号小数
            lines.drop(1).forEach { assertEquals("12.34", it.split(',')[driftIdx]) }
            // 列数不被逗号小数污染
            lines.forEach { assertEquals(header.size, it.split(',').size) }
            // 展示层 formatValue 同样固定 Locale.ROOT
            val rows = ResultFormat.kpiRows(scenario())
            assertEquals("150.0 ms", ResultFormat.formatValue(rows.first { it.id == "T1" }))
            assertEquals("0.10%", ResultFormat.formatValue(rows.first { it.id == "T3" }))
        } finally {
            Locale.setDefault(prev)
        }
    }

    // ---- claim scope 声明（KPI 文档声明边界，页脚固定文案锚点） ----

    @Test
    fun claimScopeTextIsPinned() {
        assertEquals(
            "测量对象为终端至指定仿真节点的应用层路径，非无线层/运营商全网结论",
            ResultFormat.CLAIM_SCOPE_TEXT,
        )
        assertTrue(ResultFormat.AQS_DISCLAIMER_TEXT.contains("实验性"))
        assertTrue(ResultFormat.LOW_CONFIDENCE_LABEL.contains("low_confidence"))
    }
}
