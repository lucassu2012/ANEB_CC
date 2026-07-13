package com.aneb.probe.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * ANEB 品牌色板（照设计稿 scratchpad/aneb_app_design.html 的 CSS 变量 1:1 落地）。
 *
 * 纯颜色常量表——不含语义映射（语义/分级映射见 [AnebColors] 与 Grade.kt）。
 * 命名沿用设计稿：brand=交互态、exc/good/fair/poor=四级语义、
 * pageXxx=页面骨架、a*=App 屏内层（phone 内容区）。
 *
 * 设计取舍：四级语义色编码"好→坏"，只用于仪表/分数/分级；品牌钴紫蓝极度克制，
 * 仅交互态（开始按钮、当前分段标签），几乎不与语义色同框。
 */
object AnebPalette {

    // ---- 品牌（交互态专用） ----
    val Brand = Color(0xFF5D5FEF)
    val Brand2 = Color(0xFF7D7FFB)

    // ---- 四级语义色（优/良/可/差；设计稿 --exc/--good/--fair/--poor） ----
    val Excellent = Color(0xFF2FD98A)
    val Good = Color(0xFF35B7F0)
    val Fair = Color(0xFFF6A821)
    val Poor = Color(0xFFF5566B)

    /** 无效/缺失/低置信中性灰（R-10 失败样本：绝不发语义色） */
    val Neutral = Color(0xFF8792A6)

    // ---- 暗色主题（navy-ink 底；phone 内容区 a* 口径） ----
    object Dark {
        val Background = Color(0xFF0A0E17) // --a / --pagebg
        val Surface = Color(0xFF141A26) // 卡片底色（surface 变体）
        val SurfaceElevated = Color(0xFF161D2B) // --acard 抬升卡片
        val SurfaceMuted = Color(0xFF0D1424) // --a2 段控/次级面
        val Hairline = Color(0xFF26314A) // --ahair 描边
        val Ink = Color(0xFFEEF2F8) // --aink 主文本（冷白）
        val Muted = Color(0xFF8B96AC) // --amut 次文本
        val Faint = Color(0xFF586178) // --afaint 三级文本/暗刻度
    }

    // ---- 亮色主题（跟随系统深浅色；phone.lightapp 口径） ----
    object Light {
        val Background = Color(0xFFF4F6FB) // --a
        val Surface = Color(0xFFFFFFFF) // --acard
        val SurfaceElevated = Color(0xFFFFFFFF)
        val SurfaceMuted = Color(0xFFEAEEF6) // --a2
        val Hairline = Color(0xFFE2E7F1) // --ahair
        val Ink = Color(0xFF141A26) // --aink
        val Muted = Color(0xFF5C667A) // --amut
        val Faint = Color(0xFF9AA4B6) // --afaint
    }
}
