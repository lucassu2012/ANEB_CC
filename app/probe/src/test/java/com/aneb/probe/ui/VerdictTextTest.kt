package com.aneb.probe.ui

import com.aneb.probe.ui.theme.Grade
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * VerdictText（普通用户"一句人话"结论生成器）单测。纯 JVM，锚定四档 + 不可计算 +
 * 低置信 + T4 否决 + 点名最拖后腿 KPI 逻辑。断言用子串（文案措辞可微调，语义锚点稳定）。
 */
class VerdictTextTest {

    private fun gen(
        score: Double?,
        lowConf: Boolean = false,
        veto: Boolean = false,
        reason: String? = null,
        grades: Map<String, Grade?> = emptyMap(),
    ) = VerdictText.generate(
        VerdictText.Input(
            score = score,
            lowConfidence = lowConf,
            vetoApplied = veto,
            notComputableReason = reason,
            kpiGrades = grades,
        ),
    )

    @Test
    fun excellent_isPositiveNoWeakness() {
        val v = gen(89.2, grades = mapOf("T1" to Grade.Excellent, "U1" to Grade.Good))
        assertTrue(v, v.contains("很适合 AI 助手"))
        // 全优/良不点名弱项
        assertFalse(v, v.contains("偏慢"))
    }

    @Test
    fun good_dailyUsable() {
        val v = gen(78.0, grades = mapOf("T1" to Grade.Excellent, "U1" to Grade.Good))
        assertTrue(v, v.contains("日常够用"))
    }

    @Test
    fun good_pointsOutWeakestKpi() {
        // 良档但 U1 只到"可"→ 应点名上传速度
        val v = gen(72.0, grades = mapOf("T1" to Grade.Excellent, "U1" to Grade.Fair))
        assertTrue(v, v.contains("日常够用"))
        assertTrue(v, v.contains("上传速度偏慢"))
    }

    @Test
    fun fair_canUseButStalls() {
        val v = gen(60.0, grades = mapOf("N1" to Grade.Fair))
        assertTrue(v, v.contains("能用但会卡"))
        assertTrue(v, v.contains("网络延迟偏高"))
    }

    @Test
    fun poor_badExperience() {
        val v = gen(40.0, grades = mapOf("T3" to Grade.Poor))
        assertTrue(v, v.contains("体验较差"))
        assertTrue(v, v.contains("卡顿"))
    }

    @Test
    fun notComputable_givesRetestGuidance_noGrade() {
        val v = gen(null, reason = "kpi_missing")
        assertTrue(v, v.contains("没能测出有效结果"))
        assertTrue(v, v.contains("重测"))
        // 不可计算绝不套四档主干
        assertFalse(v, v.contains("很适合 AI 助手"))
        assertFalse(v, v.contains("日常够用"))
    }

    @Test
    fun notComputable_reasonTranslatedNotRawCode() {
        // 英文机器码不得直接泄露给普通用户
        val v = gen(null, reason = "guard_rejected")
        assertFalse(v, v.contains("guard_rejected"))
        assertTrue(v, v.contains("守卫"))
    }

    @Test
    fun lowConfidence_appendsCaveat() {
        val v = gen(89.0, lowConf = true, grades = mapOf("T1" to Grade.Excellent))
        assertTrue(v, v.contains("很适合 AI 助手"))
        assertTrue(v, v.contains("仅供参考"))
    }

    @Test
    fun veto_overridesWithSevereStall() {
        // T4 否决即便分数被封在 54 附近，也必须点严重卡顿这一封顶主因
        val v = gen(54.0, veto = true, grades = mapOf("U1" to Grade.Fair))
        assertTrue(v, v.contains("严重卡顿"))
        // 否决主因压过普通点名（不应只说"上传偏慢"）
        assertTrue(v, v.contains("体验较差"))
    }

    @Test
    fun weakest_picksWorstBySeverity() {
        // 同时有 可 与 差 → 点名"差"那项（U2 工具循环）
        val v = gen(58.0, grades = mapOf("N1" to Grade.Fair, "U2" to Grade.Poor))
        assertTrue(v, v.contains("工具调用往返偏慢"))
        assertFalse(v, v.contains("网络延迟偏高"))
    }

    @Test
    fun nullKpiGrades_ignoredInMention() {
        // null 分级（缺失项）绝不参与点名，也不崩
        val v = gen(60.0, grades = mapOf("T1" to null, "N2" to Grade.Fair))
        assertTrue(v, v.contains("能用但会卡"))
        assertTrue(v, v.contains("网络抖动明显"))
    }

    // ---- 弱项选择规则（2026-08-19 T48 测试策略第 2 层补口）----
    // 空白面：既有 `good_pointsOutWeakestKpi` 只验"能点出弱项"，**没验点得对不对**——
    // 即 weakestKpi 的两条规则（严重度优先；平手按 KPI_MENTION_ORDER 的体验相关度排位）
    // 此前无守卫。这与「"最严重的前三个"列的真是最严重的吗」是同一族问题。

    @Test
    fun weakest_prefersHigherSeverityOverMentionOrder() {
        // T3 在 KPI_MENTION_ORDER 里排第一，但它只是"可"；N1 排最后却是"差"。
        // 规则是严重度优先 → 必须点名 N1（网络延迟），而不是靠前的 T3。
        val v = gen(60.0, grades = mapOf("T3" to Grade.Fair, "N1" to Grade.Poor))
        assertTrue(v, v.contains("网络延迟偏高"))
        assertFalse("严重度更高的 N1 在场时不应改点 T3：$v", v.contains("偶有卡顿"))
    }

    @Test
    fun weakest_breaksTiesByExperienceRelevance() {
        // 同为"可"：T3（卡顿，MENTION_ORDER 首位）vs N2（抖动，末位）
        // → 平手按体验相关度排位，应点名 T3 而非 N2。
        val v = gen(66.0, grades = mapOf("N2" to Grade.Fair, "T3" to Grade.Fair))
        assertTrue(v, v.contains("偶有卡顿"))
        assertFalse("平手时应优先体验相关度更高的 T3：$v", v.contains("网络抖动明显"))
    }

    @Test
    fun weakest_ignoresNullGradesInsteadOfRankingThemWorst() {
        // R-10：未采到的 KPI（null）不是"最差"，不得被选成弱项——
        // 否则"没测到"会被说成"这项拖后腿"。此处 T1 缺失、U1 才是真弱项。
        val v = gen(72.0, grades = mapOf("T1" to null, "U1" to Grade.Fair))
        assertTrue(v, v.contains("上传速度偏慢"))
        assertFalse("缺失的 T1 不应被当成弱项点名：$v", v.contains("首字响应偏慢"))
    }
}
