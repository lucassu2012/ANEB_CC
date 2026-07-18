package com.aneb.probe.ui

import com.aneb.probe.engine.LiveTelemetry
import com.aneb.probe.engine.SpeedRunner
import com.aneb.probe.engine.VoiceRunner
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * facet3 source 可解析闸门锚定（spine-4 §4.2/§5）：**每个 `live.source` 必须解析到
 * 真实数据面字段**——曾经 basic_network 的 `liveDownMbps`/`liveUpMbps` 是悬空文档字符串
 * （其数据面 SpeedRunner.Sample 字段实为 downMbps/upMbps），本闸门杜绝该类漂移再犯。
 * 字段全集与真实 data class 的一致性由 Java 反射闭环（改名/删字段即红）。
 */
class Facet3SourceResolvableTest {

    @Test
    fun `every live source in every profile resolves to a real field`() {
        for (p in TestModeProfiles.ALL) { // JVM 无 Context → FALLBACK；与 JSON 的一致性由对拍测试保证
            for (m in DynamicMetricSelection.dynamicMetrics(p)) {
                assertNotNull(
                    "${p.id}.live[${m.id}].source='${m.source}' 悬空（未解析到任何数据面字段）",
                    DynamicMetricSelection.resolveSource(p.id, m.source),
                )
            }
        }
    }

    @Test
    fun `formerly dangling sources are rejected by the gate`() {
        // §4.2 修复前 basic_network 的两个悬空声明——闸门必须拒绝（负例防回归）
        assertNull(DynamicMetricSelection.resolveSource("basic_network", "liveDownMbps"))
        assertNull(DynamicMetricSelection.resolveSource("basic_network", "liveUpMbps"))
    }

    @Test
    fun `voice prefix only resolves on the voice plane`() {
        assertNotNull(DynamicMetricSelection.resolveSource("voice_realtime", "voice.mouthEarBudgetMs"))
        assertNull(DynamicMetricSelection.resolveSource("token_experience", "voice.mouthEarBudgetMs"))
    }

    @Test
    fun `derived alias resolves with its real component fields`() {
        val ref = DynamicMetricSelection.resolveSource("voice_realtime", "voice.frameJitterMs")
        assertNotNull("frameJitterMs 是登记过的派生别名（max(up/down)，M1 同款）", ref)
        assertEquals(listOf("upFrameJitterMs", "downFrameJitterMs"), ref!!.derivedFrom)
    }

    @Test
    fun `unknown profile id resolves nothing`() {
        assertNull(DynamicMetricSelection.resolveSource("no_such_mode", "rttMs"))
    }

    // ---- 防漂移闭环：手抄字段全集 ⊆ 真实 data class 字段（Java 反射） ----

    private fun declaredFieldNames(cls: Class<*>): Set<String> =
        cls.declaredFields.map { it.name }.toSet()

    @Test
    fun `field universes are subsets of the real data classes`() {
        val telemetry = declaredFieldNames(LiveTelemetry::class.java)
        val speed = declaredFieldNames(SpeedRunner.Sample::class.java)
        val voice = declaredFieldNames(VoiceRunner.Sample::class.java)
        assertEquals("TELEMETRY_FIELDS 含不存在字段", emptySet<String>(), DynamicMetricSelection.TELEMETRY_FIELDS - telemetry)
        assertEquals("SPEED_SAMPLE_FIELDS 含不存在字段", emptySet<String>(), DynamicMetricSelection.SPEED_SAMPLE_FIELDS - speed)
        assertEquals("VOICE_SAMPLE_FIELDS 含不存在字段", emptySet<String>(), DynamicMetricSelection.VOICE_SAMPLE_FIELDS - voice)
        DynamicMetricSelection.VOICE_DERIVED.values.flatten().forEach {
            assertTrue("派生别名成分 $it 不存在于 VoiceRunner.Sample", it in voice)
        }
    }
}
