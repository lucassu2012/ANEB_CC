package com.aneb.probe.ui.theme

import com.aneb.probe.engine.KpiGrading

/**
 * AQS 四级分级 → 语义色 / 中文标签 / 用户友好标签的**单一事实来源**（展示层）。
 *
 * 与 engine/KpiGrading 对齐（分级字符串常量同源：excellent/good/fair/poor）；
 * 本文件只做"分级串 → 展示态"的映射，绝不重定义门限（门限锚点在 KpiGrading /
 * AqsScorer，测量层单一事实来源）。
 *
 * 三套标签的用途区分：
 * - [labelCn] 优/良/可/差：开发者/专业视图的紧凑角标（与 ResultFormat.gradeLabel 一致）；
 * - [labelFriendly] 优秀/良好/一般/较差：普通用户视图的分数副标题；
 * - [color] 四级语义色：仪表弧、分数、chip、KpiBar。
 */
enum class Grade(
    /** engine 侧分级字符串（KpiGrading 常量），跨层唯一键 */
    val key: String,
    /** 紧凑中文角标：优/良/可/差 */
    val labelCn: String,
    /** 用户友好长标签：优秀/良好/一般/较差 */
    val labelFriendly: String,
) {
    Excellent(KpiGrading.EXCELLENT, "优", "优秀"),
    Good(KpiGrading.GOOD, "良", "良好"),
    Fair(KpiGrading.FAIR, "可", "一般"),
    Poor(KpiGrading.POOR, "差", "较差");

    companion object {
        /**
         * engine 分级串 → [Grade]；null 或未知（值缺失/无门限/INVALID）→ null。
         * 绝不把未知分级折叠成某一档（R-10：失败样本不发分级）。
         */
        fun fromKey(key: String?): Grade? = when (key) {
            KpiGrading.EXCELLENT -> Excellent
            KpiGrading.GOOD -> Good
            KpiGrading.FAIR -> Fair
            KpiGrading.POOR -> Poor
            else -> null
        }

        /**
         * AQS 分数 → [Grade]（门限 ≥85 优 / 70–85 良 / 55–70 可 / <55 差，KPI 文档 5.4）。
         * 与 ResultFormat.aqsGrade 同门限（此处返回强类型枚举，供仪表/分数着色）。
         */
        fun fromAqsScore(score: Double): Grade = when {
            score >= 85.0 -> Excellent
            score >= 70.0 -> Good
            score >= 55.0 -> Fair
            else -> Poor
        }
    }
}
