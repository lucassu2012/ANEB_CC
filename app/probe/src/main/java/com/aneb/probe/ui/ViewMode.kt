package com.aneb.probe.ui

/**
 * 结果页展示视图模式（普通用户 / 开发者）——UI 层概念，与 TestEngine.Mode（quick/forensic
 * 测量模式）正交、互不影响。顶部 modeSeg 分段控件切换此模式：
 * - [Simple]：普通用户视图（大分数 + 一句人话 + 三瓦片）；
 * - [Detailed]：开发者视图（全量 KPI + 无线层 + REACH 矩阵 + 导出）。
 *
 * 由 setContent 作用域的 rememberSaveable 持有（撑过配置变更），是 modeSeg 的单一事实来源。
 */
enum class ViewMode {
    Simple,
    Detailed;

    /** 分段控件文案（简洁 / 专业） */
    val label: String get() = when (this) {
        Simple -> "简洁"
        Detailed -> "专业"
    }
}
