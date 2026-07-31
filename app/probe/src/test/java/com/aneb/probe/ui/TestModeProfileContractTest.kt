package com.aneb.probe.ui

import com.aneb.probe.scoring.AqsScorer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * TestModeProfile v2 4-facet 契约单测（Profile 框架 v1.0，PROFILE_FRAMEWORK §1.2/§2/§4.2）。
 *
 * 守护 INV-3「单一事实源」：facet4 的 weightsTableId / facet2 的 anchorRef / vetoRules
 * 必须与 [AqsScorer] 冻结的权重表、锚点、否决常量一致——防 UI 与打分引擎两处漂移。
 * 同时守护展示投影字段（[TestModeProfile.metrics] 等）与四 facet 的向后兼容。
 */
class TestModeProfileContractTest {

    private val token = TestModeProfiles.TOKEN_EXPERIENCE
    private val basic = TestModeProfiles.BASIC_NETWORK

    // ---------- 展示投影字段保留（分段开关/信息条不改）----------

    @Test
    fun `display projection fields preserved for ui`() {
        for (p in TestModeProfiles.ALL) {
            assertTrue("displayName", p.displayName.isNotBlank())
            assertTrue("tagline", p.tagline.isNotBlank())
            assertTrue("business", p.business.isNotBlank())
            assertTrue("metrics chips", p.metrics.isNotEmpty())
            assertTrue("conclusion", p.conclusion.isNotBlank())
        }
    }

    // ---------- 四 facet 均已填充 ----------

    @Test
    fun `all profiles carry version and four facets`() {
        for (p in TestModeProfiles.ALL) {
            assertTrue("version frozen", p.version.isNotBlank())
            assertNotNull("facet1 businessType", p.businessType)
            assertTrue("facet1 subScenarios", p.businessType!!.subScenarios.isNotEmpty())
            assertTrue("facet2 metricSpecs", p.metricSpecs.isNotEmpty())
            assertTrue("facet3 live", p.live.isNotEmpty())
            assertNotNull("facet4 scoring", p.scoring)
        }
    }

    // ---------- INV-3：facet4 权重表引用单一事实源 ----------

    @Test
    fun `token scoring weights table id resolves in aqs scorer single source`() {
        val id = token.scoring!!.weightsTableId
        assertTrue("weightsTableId '$id' 应存在于 AqsScorer.TOKEN_WEIGHT_TABLES", AqsScorer.TOKEN_WEIGHT_TABLES.containsKey(id))
        assertEquals("WEIGHTS_TOKEN_MM", id)
    }

    // ---------- INV-3：facet2 scored 指标的 anchorRef 与 KpiCalculator/AqsScorer id 对齐 ----------

    @Test
    fun `scored metrics reference an anchor, unscored do not require one`() {
        // scored=true 的指标必须挂锚点引用；否决/元数据项（scored=false）anchorRef 可为 null
        val scoredAnchorRefs = token.metricSpecs.filter { it.scored }.map {
            assertNotNull("scored metric ${it.id} 应有 anchorRef", it.anchorRef)
            it.anchorRef
        }
        // Token 模式 scored 指标即 MM 权重表的键（去掉否决项 T4/S1）
        val expectedScored = setOf("T1", "T2", "T3", "U1", "D1", "N1", "N2", "U2")
        assertEquals(expectedScored, token.metricSpecs.filter { it.scored }.map { it.id }.toSet())
        // anchorRef 命名与 KPI id 对齐（"T1"→"T1_ANCHORS"…）
        token.metricSpecs.filter { it.scored }.forEach {
            assertEquals("${it.id}_ANCHORS", it.anchorRef)
        }
        assertTrue(scoredAnchorRefs.contains("D1_ANCHORS"))
    }

    @Test
    fun `token scored metric ids are exactly the mm weight table keys`() {
        val scoredIds = token.metricSpecs.filter { it.scored }.map { it.id }.toSet()
        assertEquals(AqsScorer.WEIGHTS_TOKEN_MM.keys, scoredIds)
    }

    // ---------- INV-3：facet4 vetoRules 与 AqsScorer 否决常量一致 ----------

    @Test
    fun `token veto rules match aqs scorer constants`() {
        val rules = token.scoring!!.vetoRules
        val t4 = rules.single { it.kpiId == "T4" }
        assertEquals(AqsScorer.T4_VETO_THRESHOLD, t4.threshold, 1e-12)
        assertEquals(AqsScorer.T4_VETO_CAP, t4.cap, 1e-12)

        val s1Soft = rules.single { it.kpiId == "S1" && it.cap == AqsScorer.S1_VETO_SOFT_CAP }
        assertEquals(AqsScorer.S1_VETO_SOFT_THRESHOLD, s1Soft.threshold, 1e-12)

        val s1Hard = rules.single { it.kpiId == "S1" && it.cap == AqsScorer.S1_VETO_HARD_CAP }
        assertEquals(AqsScorer.S1_VETO_HARD_THRESHOLD, s1Hard.threshold, 1e-12)
    }

    // ---------- facet2 完整性：Token 子场景 / 指标计数 ----------

    @Test
    fun `token profile has six sub-scenarios and thirteen metric specs`() {
        assertEquals(6, token.businessType!!.subScenarios.size)
        assertEquals(13, token.metricSpecs.size)
        assertEquals("token-profile@0.4.0", token.version)
    }

    // ---------- D-346：token 动态口径定稿（2026-07-31 PO 批复 D-tok）----------

    @Test
    fun `token dynamic metrics are itl and stall never the paced token rate`() {
        // token 速率服务端定速（~40tps）恒稳——标 dynamic 是误导性动态提示，用户会看它"卡住"。
        // 真波动信号 = ITL（T2）与滚动卡顿（T3）；吞吐随带宽变、ITL 随拥塞抖 → 才配当动态主角
        //（spine-4 §0 红线：波动指标 = 随网络变化的量）。
        val dyn = token.metrics.filter { it.dynamic }.map { it.name }.toSet()
        assertEquals(setOf("字间时延 ITL", "卡顿"), dyn)
        // facet3 与 metrics 同口径：live 首位（中心动态）是 ITL 波形，不是定速 tps；
        // 卡顿有 live 条目且源于真实遥测字段；tps 降级但仍在列（稳态读数不删）。
        assertEquals("itl", token.live.first().id)
        assertEquals(LiveRender.WAVEFORM, token.live.first().render)
        assertTrue(token.live.any { it.id == "stall" && it.source == "stallCount" })
        assertTrue("tps 保留为稳态读数", token.live.any { it.id == "tps" })
    }

    // ---------- facet3：live 源字段无空 ----------

    @Test
    fun `live metrics have non-blank source and label`() {
        for (p in TestModeProfiles.ALL) {
            p.live.forEach {
                assertTrue("live source", it.source.isNotBlank())
                assertTrue("live label", it.label.isNotBlank())
            }
        }
    }

    // ---------- 网络综合性能独立打分（不并入 Token AQS）----------

    @Test
    fun `basic network scores independently not via aqs weights`() {
        assertEquals("ThresholdGrader", basic.scoring!!.engine)
        assertFalse("basic network 不引用 AQS 权重表",
            AqsScorer.TOKEN_WEIGHT_TABLES.containsKey(basic.scoring!!.weightsTableId))
        assertFalse(basic.scoring!!.renormalizeOnDesignDefault)
    }

    // ---------- byId 回退 ----------

    @Test
    fun `byId falls back to token experience`() {
        assertEquals(token, TestModeProfiles.byId("nonexistent"))
        assertEquals(basic, TestModeProfiles.byId("basic_network"))
    }
}
