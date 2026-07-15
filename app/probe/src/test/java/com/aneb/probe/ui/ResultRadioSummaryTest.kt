package com.aneb.probe.ui

import com.aneb.probe.data.RadioSampleEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * [ResultRadioSummary] 契约单测：R-10（null 不参与中位数、绝不 0 顶替）、R-02（stale 排除）、
 * R-15（制式三元组 + 友好标签），及注册小区/信号中位数聚合。
 */
class ResultRadioSummaryTest {

    private fun sample(
        ts: Long,
        stale: Boolean = false,
        networkType: String = "LTE",
        overrideType: String? = null,
        nrState: String = "none",
        rat: String? = null,
        pci: Int? = null,
        tac: Int? = null,
        arfcn: Int? = null,
        rsrp: Int? = null,
        rsrq: Int? = null,
        sinr: Int? = null,
    ) = RadioSampleEntity(
        runId = "run-1", tsNanos = ts, cellTsNanos = ts, stale = stale, subId = 1,
        subSwitched = false, networkType = networkType, overrideType = overrideType, nrState = nrState,
        rat = rat, pci = pci, tac = tac, arfcn = arfcn, rsrp = rsrp, rsrq = rsrq, sinr = sinr,
        operatorName = "CT",
    )

    @Test
    fun `空样本返回 EMPTY`() {
        val s = ResultRadioSummary.of(emptyList())
        assertEquals(ResultRadioSummary.EMPTY, s)
        assertFalse(s.hasSamples)
        assertNull(s.rsrpDbm)
    }

    @Test
    fun `RSRP 中位数排除 stale 与 null（R-02+R-10）`() {
        val s = ResultRadioSummary.of(
            listOf(
                sample(1, rsrp = -90),
                sample(2, rsrp = -95),
                sample(3, rsrp = -100),
                sample(4, stale = true, rsrp = -50), // stale 排除
                sample(5, rsrp = null),              // null 排除
            ),
        )
        assertEquals(-95, s.rsrpDbm) // 中位数 of {-90,-95,-100}
        assertEquals(5, s.sampleCount)
        assertEquals(1, s.staleCount)
    }

    @Test
    fun `全 null 信号 → 中位数 null（绝不 0 顶替 R-10）`() {
        val s = ResultRadioSummary.of(listOf(sample(1), sample(2)))
        assertNull(s.rsrpDbm)
        assertNull(s.rsrqDb)
        assertNull(s.sinrDb)
        assertTrue(s.hasSamples)
    }

    @Test
    fun `注册小区取最新样本的标识`() {
        val s = ResultRadioSummary.of(
            listOf(
                sample(1, rat = "LTE", pci = 100, tac = 5),
                sample(3, rat = "NR", pci = 317, tac = 7699, arfcn = 633984), // 最新
                sample(2, rat = "LTE", pci = 200, tac = 6),
            ),
        )
        assertEquals("5G SA", s.ratLabel)
        assertEquals(317, s.pci)
        assertEquals(7699, s.tac)
        assertEquals(633984, s.arfcn)
        assertEquals(3, s.registeredCount)
    }

    @Test
    fun `制式友好标签映射（R-15 同 LiveTelemetry 口径）`() {
        assertEquals("5G SA", ResultRadioSummary.of(listOf(sample(1, rat = "NR"))).ratLabel)
        assertEquals(
            "5G NSA",
            ResultRadioSummary.of(listOf(sample(1, rat = "LTE", nrState = "connected"))).ratLabel,
        )
        assertEquals("LTE", ResultRadioSummary.of(listOf(sample(1, rat = "LTE", nrState = "none"))).ratLabel)
        // 无注册小区（rat=null）→ 无制式（R-10 不臆造）
        assertNull(ResultRadioSummary.of(listOf(sample(1, rat = null))).ratLabel)
    }

    @Test
    fun `制式三元组取最新样本的协商_显示_nr 三列（R-15 分列）`() {
        val s = ResultRadioSummary.of(
            listOf(
                sample(1, networkType = "LTE", overrideType = "LTE_CA", nrState = "none"),
                sample(2, networkType = "NR", overrideType = "NR_SA", nrState = "connected"),
            ),
        )
        assertEquals("NR", s.networkType)
        assertEquals("NR_SA", s.overrideType)
        assertEquals("connected", s.nrState)
    }
}
