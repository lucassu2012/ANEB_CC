package com.aneb.probe.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.LineHeightStyle
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp

/**
 * ANEB 排版系统。用系统字（华为端即 HarmonyOS Sans / iOS 端 PingFang），不打包字体
 * 文件（即装即用、无字体授权/体积负担）。大数字用 [DisplayScore] 的 Black 字重 +
 * tabular figures（tnum，等宽数字防跳动）。
 */
object AnebType {

    /** 系统默认字族——运行期解析为 HarmonyOS Sans SC / PingFang SC / Roboto */
    private val SystemSans = FontFamily.Default

    /** 表格数字特性：等宽数字位，仪表分数/KPI 值不因字宽变化而横向抖动 */
    private const val TABULAR = "tnum"

    /**
     * 大分数样式（仪表中心 89 / 62 …）。字号由调用点按仪表尺寸覆盖（sp 参数），
     * 此处锁定字重=Black、字距收紧、等宽数字。
     */
    val DisplayScore: TextStyle = TextStyle(
        fontFamily = SystemSans,
        fontWeight = FontWeight.Black,
        letterSpacing = (-0.04).em,
        fontFeatureSettings = TABULAR,
    )

    /** 瓦片/KPI 大数值：半粗 + 等宽数字（响应速度 35ms、上传 12.5 …） */
    val StatValue: TextStyle = TextStyle(
        fontFamily = SystemSans,
        fontWeight = FontWeight.Bold,
        letterSpacing = (-0.02).em,
        fontFeatureSettings = TABULAR,
    )

    /** Material3 Typography——仅覆盖字族与字重锚点，尺寸走 M3 默认（组件按需覆盖） */
    val Typography: Typography = Typography().run {
        val lh = LineHeightStyle(
            alignment = LineHeightStyle.Alignment.Center,
            trim = LineHeightStyle.Trim.None,
        )
        copy(
            displayLarge = displayLarge.copy(fontFamily = SystemSans, fontWeight = FontWeight.Black, lineHeightStyle = lh),
            headlineMedium = headlineMedium.copy(fontFamily = SystemSans, fontWeight = FontWeight.Bold),
            titleLarge = titleLarge.copy(fontFamily = SystemSans, fontWeight = FontWeight.Bold),
            titleMedium = titleMedium.copy(fontFamily = SystemSans, fontWeight = FontWeight.SemiBold),
            bodyLarge = bodyLarge.copy(fontFamily = SystemSans),
            bodyMedium = bodyMedium.copy(fontFamily = SystemSans),
            labelLarge = labelLarge.copy(fontFamily = SystemSans, fontWeight = FontWeight.SemiBold),
            labelSmall = labelSmall.copy(fontFamily = SystemSans, letterSpacing = 0.08.em),
        )
    }
}
