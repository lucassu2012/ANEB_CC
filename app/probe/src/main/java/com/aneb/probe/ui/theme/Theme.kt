package com.aneb.probe.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

/**
 * ANEB 语义色扩展——Material3 的 ColorScheme 只有通用角色（primary/surface…），
 * 装不下"四级语义色 + 分级映射"这套领域色。用一个 [AnebColors] 经 CompositionLocal
 * 下发，与 M3 ColorScheme 并存：M3 角色供标准组件，AnebColors 供仪表/分级/瓦片。
 *
 * 固定品牌（dynamicColor=false）：即装即用、跨机型视觉一致，不吃 Android 12+ 动态取色。
 * 深浅色双主题：[darkAnebColors] / [lightAnebColors]，由系统深浅色自动切换。
 */
@Immutable
data class AnebColors(
    // 品牌（交互态）
    val brand: Color,
    val brand2: Color,
    // 四级语义
    val excellent: Color,
    val good: Color,
    val fair: Color,
    val poor: Color,
    val neutral: Color,
    // 骨架
    val background: Color,
    val surface: Color,
    val surfaceElevated: Color,
    val surfaceMuted: Color,
    val hairline: Color,
    // 文本
    val ink: Color,
    val muted: Color,
    val faint: Color,
) {
    /**
     * 分级 → 语义色（单一事实来源；null/未知 → [neutral]）。
     * 接受 [Grade] 强类型；分级串入口用 [Grade.fromKey] 先转换。
     */
    fun gradeColor(grade: Grade?): Color = when (grade) {
        Grade.Excellent -> excellent
        Grade.Good -> good
        Grade.Fair -> fair
        Grade.Poor -> poor
        null -> neutral
    }

    /** 分级字符串（KpiGrading 常量）→ 语义色；便利重载，内部走 [Grade.fromKey] */
    fun gradeColor(gradeKey: String?): Color = gradeColor(Grade.fromKey(gradeKey))
}

val darkAnebColors = AnebColors(
    brand = AnebPalette.Brand,
    brand2 = AnebPalette.Brand2,
    excellent = AnebPalette.Excellent,
    good = AnebPalette.Good,
    fair = AnebPalette.Fair,
    poor = AnebPalette.Poor,
    neutral = AnebPalette.Neutral,
    background = AnebPalette.Dark.Background,
    surface = AnebPalette.Dark.Surface,
    surfaceElevated = AnebPalette.Dark.SurfaceElevated,
    surfaceMuted = AnebPalette.Dark.SurfaceMuted,
    hairline = AnebPalette.Dark.Hairline,
    ink = AnebPalette.Dark.Ink,
    muted = AnebPalette.Dark.Muted,
    faint = AnebPalette.Dark.Faint,
)

val lightAnebColors = AnebColors(
    brand = AnebPalette.Brand,
    brand2 = AnebPalette.Brand2,
    excellent = AnebPalette.Excellent,
    good = AnebPalette.Good,
    fair = AnebPalette.Fair,
    poor = AnebPalette.Poor,
    neutral = AnebPalette.Neutral,
    background = AnebPalette.Light.Background,
    surface = AnebPalette.Light.Surface,
    surfaceElevated = AnebPalette.Light.SurfaceElevated,
    surfaceMuted = AnebPalette.Light.SurfaceMuted,
    hairline = AnebPalette.Light.Hairline,
    ink = AnebPalette.Light.Ink,
    muted = AnebPalette.Light.Muted,
    faint = AnebPalette.Light.Faint,
)

private val LocalAnebColors = staticCompositionLocalOf { darkAnebColors }

// ---- M3 ColorScheme（标准组件用；品牌钴紫蓝作 primary，语义面/文本对齐 AnebColors）----

private val DarkColorScheme = darkColorScheme(
    primary = AnebPalette.Brand,
    onPrimary = Color.White,
    secondary = AnebPalette.Brand2,
    background = AnebPalette.Dark.Background,
    onBackground = AnebPalette.Dark.Ink,
    surface = AnebPalette.Dark.Surface,
    onSurface = AnebPalette.Dark.Ink,
    surfaceVariant = AnebPalette.Dark.SurfaceElevated,
    onSurfaceVariant = AnebPalette.Dark.Muted,
    outline = AnebPalette.Dark.Hairline,
    error = AnebPalette.Poor,
    onError = Color.White,
)

private val LightColorScheme = lightColorScheme(
    primary = AnebPalette.Brand,
    onPrimary = Color.White,
    secondary = AnebPalette.Brand2,
    background = AnebPalette.Light.Background,
    onBackground = AnebPalette.Light.Ink,
    surface = AnebPalette.Light.Surface,
    onSurface = AnebPalette.Light.Ink,
    surfaceVariant = AnebPalette.Light.SurfaceElevated,
    onSurfaceVariant = AnebPalette.Light.Muted,
    outline = AnebPalette.Light.Hairline,
    error = AnebPalette.Poor,
    onError = Color.White,
)

/**
 * ANEB 主题根。用法：`AnebTheme { … }`；语义色取用 `AnebTheme.colors.excellent` /
 * `AnebTheme.colors.gradeColor(grade)`。
 *
 * @param darkTheme 缺省跟随系统深浅色；测试/预览可显式覆盖。
 */
@Composable
fun AnebTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val anebColors = if (darkTheme) darkAnebColors else lightAnebColors
    CompositionLocalProvider(LocalAnebColors provides anebColors) {
        MaterialTheme(
            colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme,
            typography = AnebType.Typography,
            content = content,
        )
    }
}

/** 语义色访问器：`AnebTheme.colors.…`（M3 `MaterialTheme.colorScheme` 的领域色姊妹） */
object AnebTheme {
    val colors: AnebColors
        @Composable
        @ReadOnlyComposable
        get() = LocalAnebColors.current
}
