package com.aneb.probe.ui

import com.aneb.probe.data.TestRun
import com.aneb.probe.engine.ItlHistogram
import com.aneb.probe.engine.ResultReporter
import com.aneb.probe.scoring.AqsScorer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * [ResultAqsBreakdown] 契约单测：真实子分分解只解析**落库上报体**、贡献分 = 子分 × 权重，
 * 权重直引 [AqsScorer.WEIGHTS]（单一事实源）。
 *
 * 关键防漂移测试（`真实上报体端到端解析`）用 [ResultReporter.build] 造真实 JSON——
 * 若上报体键（`aqs_version`/`run.aqs.sub_scores`）与解析器口径漂移，此测立即红灯。
 */
class ResultAqsBreakdownTest {

    private fun run(version: String) = TestRun(
        runId = "run-1", startedAtEpochMs = 1_752_000_000_000L,
        serverBase = "http://10.0.2.2:8443", mode = "forensic",
        scenarioOrder = "s1_chat,s2_coding_agent,s3_multimodal", transport = "auto",
        kpiSet = "agent-qoe-kpi-v0.2", aqsVersion = version,
        profileVersions = "s1_chat@0.2.0", schemaVersion = "1.0",
        profileSource = "server", appVersionName = "0.3.0", appVersionCode = 1L,
        guardMetadata = "private_dns_active=false", aqsScore = 89.2, aqsLowConfidence = false,
        aqsVetoApplied = false, aqsNotComputableReason = null,
        status = "completed", reportStatus = null,
    )

    private fun reportJson(
        version: String,
        subScores: Map<String, Double>,
        score: Double? = 89.2,
        lowConfidence: Boolean = false,
        vetoApplied: Boolean = false,
    ): String = ResultReporter.build(
        run = run(version),
        scenarios = emptyList(),
        aqs = AqsScorer.AqsResult(
            aqsVersion = version, kpiSetVersion = "agent-qoe-kpi-v0.2",
            score = score, subScores = subScores,
            vetoApplied = vetoApplied, lowConfidence = lowConfidence, notComputableReason = null,
        ),
    )

    private val v01Subs = mapOf(
        "T1" to 97.3, "T3" to 100.0, "T2" to 98.0,
        "U1" to 77.5, "U2" to 77.8, "N1" to 75.1, "N2" to 81.6,
    )

    @Test
    fun `真实上报体端到端解析_v0_1_三组齐全`() {
        val b = ResultAqsBreakdown.fromReportJson(reportJson(AqsScorer.AQS_VERSION, v01Subs))
        assertNotNull("可计算 run 必出分解", b)
        b!!
        assertEquals("aqs-v0.1", b.aqsVersion)
        assertEquals(89.2, b.score!!, 1e-9)
        // 三组齐全，无连续性
        assertEquals(listOf("流式体验", "上行突发", "网络基线"), b.groups.map { it.label })
        val stream = b.groups.first { it.label == "流式体验" }
        assertEquals(listOf("T1", "T3", "T2"), stream.kpis.map { it.id })
    }

    @Test
    fun `贡献分等于子分乘权重_且权重直引 AqsScorer`() {
        val b = ResultAqsBreakdown.fromReportJson(reportJson(AqsScorer.AQS_VERSION, v01Subs))!!
        val t1 = b.groups.flatMap { it.kpis }.first { it.id == "T1" }
        // 权重来自 AqsScorer.WEIGHTS，绝不本地写死
        assertEquals(AqsScorer.WEIGHTS.getValue("T1"), t1.weight, 1e-9)
        assertEquals(97.3, t1.subScore, 1e-9)
        assertEquals(97.3 * AqsScorer.WEIGHTS.getValue("T1"), t1.contributionPoints, 1e-9)
        assertEquals(AqsScorer.WEIGHTS.getValue("T1") * 100.0, t1.maxPoints, 1e-9)
    }

    @Test
    fun `组小计与满分正确`() {
        val b = ResultAqsBreakdown.fromReportJson(reportJson(AqsScorer.AQS_VERSION, v01Subs))!!
        val stream = b.groups.first { it.label == "流式体验" }
        // 满分 = (0.20+0.20+0.15)×100 = 55
        assertEquals(55.0, stream.maxPoints, 1e-9)
        val expected = 97.3 * 0.20 + 100.0 * 0.20 + 98.0 * 0.15
        assertEquals(expected, stream.subtotalPoints, 1e-9)
    }

    @Test
    fun `子分档色同锚 AQS 分档线`() {
        val b = ResultAqsBreakdown.fromReportJson(reportJson(AqsScorer.AQS_VERSION, v01Subs))!!
        val kpis = b.groups.flatMap { it.kpis }.associateBy { it.id }
        // 97.3 ≥ 85 → 优；77.5 ∈ [70,85) → 良；aqsGrade 单源
        assertEquals(ResultFormat.aqsGrade(97.3), kpis.getValue("T1").gradeKey)
        assertEquals(ResultFormat.aqsGrade(77.5), kpis.getValue("U1").gradeKey)
    }

    @Test
    fun `v0_2 出现连续性组_权重取 WEIGHTS_V02`() {
        val subs = v01Subs + mapOf("C1" to 90.0, "C2" to 84.0)
        val b = ResultAqsBreakdown.fromReportJson(reportJson(AqsScorer.AQS_VERSION_V02, subs))!!
        assertEquals("aqs-v0.2", b.aqsVersion)
        assertEquals(listOf("流式体验", "上行突发", "网络基线", "连续性"), b.groups.map { it.label })
        val t1 = b.groups.flatMap { it.kpis }.first { it.id == "T1" }
        // v0.2：T1 权重 = 0.20×0.8 = 0.16（WEIGHTS_V02 单源）
        assertEquals(AqsScorer.WEIGHTS_V02.getValue("T1"), t1.weight, 1e-9)
        val c1 = b.groups.flatMap { it.kpis }.first { it.id == "C1" }
        assertEquals(AqsScorer.WEIGHTS_V02.getValue("C1"), c1.weight, 1e-9)
        // 全组权重和 = 1.0（分解无遗漏无重叠）
        assertEquals(1.0, b.groups.sumOf { it.weight }, 1e-9)
    }

    @Test
    fun `不可计算 run 无子分_返回 null（R-10 绝不 0 顶替）`() {
        // AQS 不可计算：subScores 为空、score=null（AqsScorer 语义）
        val json = reportJson(AqsScorer.AQS_VERSION, emptyMap(), score = null)
        assertNull(ResultAqsBreakdown.fromReportJson(json))
    }

    @Test
    fun `空_null_畸形输入均返回 null 不抛`() {
        assertNull(ResultAqsBreakdown.fromReportJson(null))
        assertNull(ResultAqsBreakdown.fromReportJson(""))
        assertNull(ResultAqsBreakdown.fromReportJson("   "))
        assertNull(ResultAqsBreakdown.fromReportJson("{ not json"))
        assertNull(ResultAqsBreakdown.fromReportJson("[]"))
        assertNull(ResultAqsBreakdown.fromReportJson("""{"run":{}}"""))
        assertNull(ResultAqsBreakdown.fromReportJson("""{"run":{"aqs":{}}}"""))
    }

    @Test
    fun `低置信与否决标志透传`() {
        val json = reportJson(AqsScorer.AQS_VERSION, v01Subs, lowConfidence = true, vetoApplied = true)
        val b = ResultAqsBreakdown.fromReportJson(json)!!
        assertTrue(b.lowConfidence)
        assertTrue(b.vetoApplied)
    }

    @Test
    fun `v0_2 落库上报体 aqs_v02 端到端解析（D-26 additive）`() {
        val v02Subs = v01Subs + mapOf("C1" to 90.0, "C2" to 84.0)
        val body = ResultReporter.build(
            run = run(AqsScorer.AQS_VERSION), // 顶层仍 v0.1
            scenarios = emptyList(),
            aqs = AqsScorer.AqsResult(
                aqsVersion = AqsScorer.AQS_VERSION, kpiSetVersion = "agent-qoe-kpi-v0.2",
                score = 89.2, subScores = v01Subs, vetoApplied = false, lowConfidence = false,
                notComputableReason = null,
            ),
            aqsV02 = AqsScorer.AqsResult(
                aqsVersion = AqsScorer.AQS_VERSION_V02, kpiSetVersion = "agent-qoe-kpi-v0.2",
                score = 87.5, subScores = v02Subs, vetoApplied = false, lowConfidence = true,
                notComputableReason = null,
            ),
        )
        // v0.1 主分解仍为三组（读 run.aqs），不受 aqs_v02 影响
        val v01 = ResultAqsBreakdown.fromReportJson(body)!!
        assertEquals(listOf("流式体验", "上行突发", "网络基线"), v01.groups.map { it.label })
        assertEquals("aqs-v0.1", v01.aqsVersion)
        // v0.2 分解含连续性四组（读 run.aqs_v02），权重取 WEIGHTS_V02
        val v02 = ResultAqsBreakdown.v02FromReportJson(body)!!
        assertEquals("aqs-v0.2", v02.aqsVersion)
        assertEquals(87.5, v02.score!!, 1e-9)
        assertTrue(v02.lowConfidence)
        assertEquals(listOf("流式体验", "上行突发", "网络基线", "连续性"), v02.groups.map { it.label })
        val c1 = v02.groups.flatMap { it.kpis }.first { it.id == "C1" }
        assertEquals(AqsScorer.WEIGHTS_V02.getValue("C1"), c1.weight, 1e-9)
        assertEquals(1.0, v02.groups.sumOf { it.weight }, 1e-9)
    }

    @Test
    fun `无 aqs_v02 时 v02FromReportJson 返回 null（正常 v0_1 run）`() {
        val body = reportJson(AqsScorer.AQS_VERSION, v01Subs) // 不传 aqsV02
        assertNull(ResultAqsBreakdown.v02FromReportJson(body))
        assertNotNull(ResultAqsBreakdown.fromReportJson(body)) // v0.1 仍正常
    }

    @Test
    fun `GROUP_KPI_IDS_V01 与 AqsScorer 权重表同源不漂移`() {
        val ids = ResultAqsBreakdown.GROUP_KPI_IDS_V01.flatMap { it.second }
        // 无重复
        assertEquals(ids.size, ids.toSet().size)
        // 近似分组覆盖且仅覆盖 v0.1 加权 KPI（与 AqsScorer.WEIGHTS 键集合一致，防两处漂移）
        assertEquals(AqsScorer.WEIGHTS.keys, ids.toSet())
        // 组顺序/标签稳定（R-28 三组：流式/上行/基线）
        assertEquals(listOf("流式体验", "上行突发", "网络基线"), ResultAqsBreakdown.GROUP_KPI_IDS_V01.map { it.first })
    }

    /** ItlHistogram 依赖存在性自检（防 build 里传空 scenarios 时 API 变更悄悄破坏本测的前提）。 */
    @Test
    fun `ItlHistogram of 可构造（编译期依赖锚定）`() {
        assertNotNull(ItlHistogram.of(listOf(50.0, 80.0)))
    }

    // ---- 拖累维度判词（D-505②）：判据须与报告层 subscore_rollup 逐条同口径 ----

    @Test
    fun `拖累维度＝子分最低的那个 KPI`() {
        val b = ResultAqsBreakdown.fromReportJson(reportJson(AqsScorer.AQS_VERSION, v01Subs))
        // v01Subs 最低是 N1=75.1
        assertEquals("N1", ResultAqsBreakdown.draggingDim(b)?.id)
    }

    /**
     * 对齐 `subscore_rollup.py` 那条注释点名的危险（D-179）：**最低者即拖累维度**，
     * 所以一个越界值会直接劫持这句判词。报告层用 `value_problem` 先滤，此处必须同样先滤。
     */
    @Test
    fun `越界子分不得劫持拖累维度`() {
        val subs = v01Subs + ("T1" to -5.0)   // 不可能的值：不是坏测量，根本不是测量
        val b = ResultAqsBreakdown.fromReportJson(reportJson(AqsScorer.AQS_VERSION, subs))
        assertEquals("越界值被滤掉后，拖累维度仍应是真实最低的 N1", "N1", ResultAqsBreakdown.draggingDim(b)?.id)
    }

    @Test
    fun `上越界同样剔除`() {
        val subs = v01Subs + ("N1" to 150.0)  // N1 本是最低，越界后应退出竞争
        val b = ResultAqsBreakdown.fromReportJson(reportJson(AqsScorer.AQS_VERSION, subs))
        assertEquals("N1 越界后，最低应变成 U1=77.5", "U1", ResultAqsBreakdown.draggingDim(b)?.id)
    }

    /** 报告层 `dragging = ... if medians else None`——无可用维度给 null，不是 0、不是"无"。 */
    @Test
    fun `无子分时拖累维度为 null 且判词行如实说无`() {
        val b = ResultAqsBreakdown.fromReportJson(reportJson(AqsScorer.AQS_VERSION, emptyMap()))
        assertNull(ResultAqsBreakdown.draggingDim(b))
        assertTrue(ResultAqsBreakdown.draggingVerdictLine(b).contains("无可用子分"))
    }

    @Test
    fun `breakdown 本身为 null 时不炸且如实说无`() {
        assertNull(ResultAqsBreakdown.draggingDim(null))
        assertTrue(ResultAqsBreakdown.draggingVerdictLine(null).contains("无可用子分"))
    }

    /**
     * 并列规则：报告层 `min()` over 已排序的 dict＝取排在前面的那个；此处取遍历顺序
     * （组顺序＝KPI 文档 5.4）里的第一个最小值。两侧若各解各的并列，同一份数据会给出
     * 不同判词——正是 §2.14 要防的形状，故把它钉死。
     */
    @Test
    fun `并列时取规范顺序里靠前的那个`() {
        val subs = v01Subs + ("T1" to 60.0) + ("N1" to 60.0)  // T1 在流式组，排在基线组 N1 之前
        val b = ResultAqsBreakdown.fromReportJson(reportJson(AqsScorer.AQS_VERSION, subs))
        assertEquals("T1", ResultAqsBreakdown.draggingDim(b)?.id)
    }

    @Test
    fun `判词行用报告层同一个词「拖累」并带维度与分值`() {
        val b = ResultAqsBreakdown.fromReportJson(reportJson(AqsScorer.AQS_VERSION, v01Subs))
        val line = ResultAqsBreakdown.draggingVerdictLine(b)
        assertTrue("须用报告层同一个词汇「拖累」，防同名不同义", line.contains("拖累"))
        assertTrue("须点名维度 id", line.contains("N1"))
        assertTrue("须给出分值", line.contains("75"))
    }
}
