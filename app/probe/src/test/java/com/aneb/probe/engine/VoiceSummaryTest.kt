package com.aneb.probe.engine

import com.aneb.probe.data.VoiceResultEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * voice 摘要接线（大脑 08-22 裁定 voice 半）：[VoiceSummary.select] 的窗口/保真守卫
 * + TestEngine 调用点钉（D-325 形状——函数级守卫防不住「不再传参」，ThermalSummaryTest 同款）。
 *
 * 保真警戒重点：mouthEarProxyP50Ms ← 实体 mouthEarProxyMs（M1' PROXY），**不是**
 * mouthEarBudgetMs（M1 DERIVED）——夹具刻意给两个字段不同值，映射拿错哪个当场红。
 */
class VoiceSummaryTest {

    private val NOW = 1_783_950_000_000L

    /** v2 口径全值行；budget 与 proxy 刻意不同值（保真对照）。 */
    private fun row(
        tsEpochMs: Long = NOW - 60_000L,
        caliber: String? = "server-sim-v2",
        lowConfidence: Boolean = false,
        mouthEarProxyMs: Double? = 412.0,
        mouthEarBudgetMs: Double? = 999.0,
        turnsOk: Int? = 12,
        m7MaxFrameGapMs: Double? = 180.5,
    ) = VoiceResultEntity(
        tsEpochMs = tsEpochMs, caliber = caliber, lowConfidence = lowConfidence,
        rttMs = 55.0, jitterMs = 4.0, upFrameJitterMs = 6.0, downFrameJitterMs = null,
        mouthEarBudgetMs = mouthEarBudgetMs, framesSent = 100, framesRecv = 100,
        ttfbP50Ms = 210.0, ttfbP95Ms = 300.0, downNetJitterMs = 5.5,
        mouthEarProxyMs = mouthEarProxyMs, turnSwitchP50Ms = 800.0, bargeStopMaxMs = 120.0,
        turnsOk = turnsOk, m7MaxFrameGapMs = m7MaxFrameGapMs,
    )

    @Test
    fun `空候选 = null——run 不出 voice 块（块缺席=窗内无 Done 行）`() {
        assertNull(VoiceSummary.select(emptyList(), NOW))
    }

    @Test
    fun `窗内行逐字段保真——特别是 proxy(M1') 不是 budget(M1)`() {
        val v = VoiceSummary.select(listOf(row()), NOW)!!
        assertEquals("server-sim-v2", v.caliber)
        assertEquals(180.5, v.m7MaxFrameGapMs!!, 0.0)
        assertEquals(
            "mouthEarProxyP50Ms 必须来自实体 mouthEarProxyMs(M1' PROXY=412.0)，" +
                "不是 mouthEarBudgetMs(M1 DERIVED=999.0)——一字之差两个口径",
            412.0, v.mouthEarProxyP50Ms!!, 0.0,
        )
        assertEquals(false, v.lowConfidence)
        assertEquals(12, v.turnsOk)
        assertEquals(NOW - 60_000L, v.tsEpochMs)
    }

    @Test
    fun `v1 形状行原样透传——caliber-proxy-turnsOk 的 null 是合法状态不是缺陷`() {
        val v = VoiceSummary.select(
            listOf(row(caliber = null, mouthEarProxyMs = null, turnsOk = null, m7MaxFrameGapMs = null)),
            NOW,
        )!!
        assertNull(v.caliber)
        assertNull(v.mouthEarProxyP50Ms)
        assertNull(v.turnsOk)
        assertNull(v.m7MaxFrameGapMs)
    }

    @Test
    fun `超龄行剔除——24h 窗含边界（AqsV02Gate 同款判据形状）`() {
        assertNull(
            "超窗 1ms 必须剔除（超龄语音证据与本次 run 环境不可比）",
            VoiceSummary.select(listOf(row(tsEpochMs = NOW - VoiceSummary.MAX_AGE_MS - 1L)), NOW),
        )
        val boundary = VoiceSummary.select(listOf(row(tsEpochMs = NOW - VoiceSummary.MAX_AGE_MS)), NOW)
        assertEquals("恰在窗界=含边界，须挂接", NOW - VoiceSummary.MAX_AGE_MS, boundary!!.tsEpochMs)
    }

    @Test
    fun `未来时刻的脏数据剔除`() {
        assertNull(VoiceSummary.select(listOf(row(tsEpochMs = NOW + 1L)), NOW))
    }

    @Test
    fun `调用点钉——TestEngine 必须真查库真传参（D-325：函数级守卫防不住这一面）`() {
        val src = repoFile("app/probe/src/main/java/com/aneb/probe/engine/TestEngine.kt")
            .readText(Charsets.UTF_8)
        assertTrue(
            "TestEngine 不再从 voiceResultDao().recent(1) 取候选——voice 块将从一切真实 run 消失且零测试变红",
            src.contains("db.voiceResultDao().recent(1)"),
        )
        assertTrue(
            "TestEngine 不再把 voiceSummary 传给 ResultReporter.build",
            src.contains("voice = voiceSummary,"),
        )
    }

    /** AdapterSpecTest 同款：从 user.dir 向上找仓根相对文件。 */
    private fun repoFile(relFromRepoRoot: String): File {
        var cur: File? = File(System.getProperty("user.dir") ?: ".").absoluteFile
        while (cur != null) {
            val cand = File(cur, relFromRepoRoot)
            if (cand.isFile) return cand
            cur = cur.parentFile
        }
        error("找不到 $relFromRepoRoot（从 user.dir 向上未命中）")
    }
}
