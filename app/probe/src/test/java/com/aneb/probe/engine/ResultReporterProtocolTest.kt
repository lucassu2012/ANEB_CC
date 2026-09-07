package com.aneb.probe.engine

import com.aneb.probe.data.ScenarioResultEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.net.NegotiatedProtocolLog
import com.aneb.probe.scoring.AqsScorer
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * `run.negotiated_protocol` 块的序列化守卫（A-8⑦／D-806；夹具样式承
 * [ResultReporterThermalTest]，挂接先例＝同文件的 env/voice 可选参数）。
 *
 * **这个块要回答的问题**：`9c646cd` 把测量端点钉死成 HTTP/1.1，那证明「我们设了它」；
 * **本块是「它真的生效了」那一半的唯一载体**——验收判据 `negotiated_protocol` 全为
 * http/1.1 就落在这里。**一条只设不记的钉，与一条没设的钉，在语料里长得一模一样。**
 */
class ResultReporterProtocolTest {

    private fun scenario() = ScenarioResultEntity(
        runId = "run-1", profileId = "s1_chat", profileVersion = "1.0.0",
        repeatIndex = 0, orderIndex = 0, startedAtNanos = 0L, endedAtNanos = 1L,
        validity = "valid", invalidReasons = "",
        t1TtftMs = null, t1Grade = null, t2ItlP95Ms = null, t2Grade = null,
        t2ItlP95InclCoalescedMs = null, t3StallRate = null, t3Grade = null,
        t3StallRateInclResume = null, t4SevereStallRate = null, t4Grade = null,
        t5ResumeP95Ms = null, n1RttP50Ms = 20.0, n1Grade = "excellent",
        n2JitterMs = 3.0, n2Grade = "excellent", u1GoodputMbps = 50.0, u1Grade = "excellent",
        u1GoodputExclSlowStartMbps = null, u2ToolLoopP95Ms = null, u2Grade = null,
        d1GoodputMbps = null, d1Grade = null,
        seqGapCount = 0, seqDupCount = 0, lowConfidenceKpis = "",
        offsetStartUs = 100L, offsetStartErrUs = 10L, offsetEndUs = 110L,
        offsetEndErrUs = 10L, offsetDriftPpm = 1.0, offsetSuspect = false,
        netTransport = "wifi", netCapabilities = "caps", netInterfaceName = "if0",
        serverObservedAddr = "203.0.113.7:8443", parseDurUsTotal = null, perEventParseUs = null,
    )

    private fun run() = TestRun(
        runId = "run-1", startedAtEpochMs = 1_752_000_000_000L,
        serverBase = "http://10.0.2.2:8443", mode = "quick",
        scenarioOrder = "s1_chat", transport = "auto",
        kpiSet = "agent-qoe-kpi-v0.2", aqsVersion = "aqs-v0.1",
        profileVersions = "s1_chat@0.2.0", schemaVersion = "1.0",
        profileSource = "server", appVersionName = "0.3.0", appVersionCode = 1L,
        guardMetadata = null, aqsScore = 88.5, aqsLowConfidence = false,
        aqsVetoApplied = false, aqsNotComputableReason = null,
        status = "completed", reportStatus = null,
    )

    private fun body(p: NegotiatedProtocolLog.Snapshot? = null): String = ResultReporter.build(
        run = run(),
        scenarios = listOf(scenario() to ItlHistogram.of(emptyList())),
        aqs = AqsScorer.AqsResult(
            aqsVersion = "aqs-v0.1", kpiSetVersion = "agent-qoe-kpi-v0.2",
            score = 88.5, subScores = mapOf("T" to 90.0),
            vetoApplied = false, lowConfidence = false, notComputableReason = null,
        ),
        protocols = p,
    )

    /** 从真实账本取快照，而不是手搓 Snapshot——顺带钉住两者的字段对齐。 */
    private fun snap(vararg obs: Pair<String, String?>) = NegotiatedProtocolLog().apply {
        obs.forEach { (proto, header) -> observe(proto, header) }
    }.snapshot()

    @Test
    fun `参数缺省 → wire 无该键，老调用形状一字节不变`() {
        assertFalse(
            "param 默认 null 必须保持块缺席（=该 run 早于本字段上线）",
            body().contains("\"negotiated_protocol\""),
        )
    }

    @Test
    fun `全 http11 → 分表恰一个键，这就是验收要判的形状`() {
        val b = body(
            snap(
                "http/1.1" to "HTTP/1.1;via=tcp",
                "http/1.1" to "HTTP/1.1;via=tcp",
            ),
        )
        assertTrue(b.contains("\"negotiated_protocol\""))
        assertTrue("总数要落 wire", b.contains("\"samples\":2"))
        assertTrue(b.contains("\"by_protocol\":{\"http/1.1\":2}"))
        assertTrue(b.contains("\"by_proto_header\":{\"HTTP/1.1;via=tcp\":2}"))
        assertTrue("缺席数是 0 也要写出来，0 是真实读数", b.contains("\"header_absent\":0"))
    }

    @Test
    fun `混入一条 h2 → wire 上看得见第二个键（阳性对照：该判据不是恒真的）`() {
        val b = body(snap("http/1.1" to null, "h2" to null))
        assertTrue("h2 必须原样出现在 wire 上，不得被抹平", b.contains("\"h2\":1"))
        assertTrue(b.contains("\"http/1.1\":1"))
        assertTrue("两条都没头 ⇒ 缺席计 2", b.contains("\"header_absent\":2"))
    }

    @Test
    fun `零样本 → 块仍在且 samples 为 0——与块缺席是两个状态`() {
        val b = body(snap())
        assertTrue("账本在位就该有块", b.contains("\"negotiated_protocol\""))
        assertTrue(b.contains("\"samples\":0"))
        assertTrue("空分表落成空对象，不是消失", b.contains("\"by_protocol\":{}"))
    }
}
