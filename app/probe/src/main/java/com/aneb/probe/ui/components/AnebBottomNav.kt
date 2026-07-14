package com.aneb.probe.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.ui.theme.AnebTheme

/**
 * 底部 3-tab（SpeedTest 式外壳）——Speed 测试 / 可达性 / 历史。纯展示/导航层：
 * 选中态与切换回调由上层（MainActivity）持有，本组件不持状态、不碰测量语义。
 *
 * iOS 材质：外壳走 [GlassChrome] 半透毛玻璃（与 [GlassHeader] 同款材质），上缘一道发丝线；
 * 选中段用品牌系统蓝（[AnebColors.brand]），未选中用次文本灰（[AnebColors.muted]），
 * 去掉 M3 胶囊指示器（iOS tab bar 无药丸高亮，选中即蓝染），深浅色跟随主题。
 *
 * 图标口径：本模块仅内置 material-icons-**core**（未接 extended），故按交接备选取核心集内图标——
 * Speed→[Icons.Filled.PlayArrow]（"开跑"语义）· 可达性→[Icons.Filled.Search]（"探测"语义）·
 * 历史→[Icons.AutoMirrored.Filled.List]。Speed/Wifi/SignalCellularAlt/History 属 extended，未打包。
 */
enum class AnebTab(val label: String, val icon: ImageVector) {
    Speed("测试", Icons.Filled.PlayArrow),
    Reach("可达性", Icons.Filled.Search),
    History("历史", Icons.AutoMirrored.Filled.List),
}

@Composable
fun AnebBottomNav(
    selected: AnebTab,
    onSelect: (AnebTab) -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = AnebTheme.colors
    GlassChrome(modifier = modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth()) {
            // iOS tab bar 上缘发丝线：内容从其下方滚过，不压实心分割条
            Box2Hairline(colors.hairline)
            NavigationBar(
                containerColor = Color.Transparent,
                tonalElevation = 0.dp,
                // Surface 已 safeDrawingPadding 吃掉系统条内衬，这里不再重复加窗内衬
                windowInsets = WindowInsets(0, 0, 0, 0),
            ) {
                AnebTab.values().forEach { tab ->
                    val on = tab == selected
                    NavigationBarItem(
                        selected = on,
                        onClick = { onSelect(tab) },
                        icon = { Icon(tab.icon, contentDescription = tab.label) },
                        label = {
                            Text(
                                text = tab.label,
                                fontSize = 10.5.sp,
                                fontWeight = if (on) FontWeight.SemiBold else FontWeight.Normal,
                            )
                        },
                        alwaysShowLabel = true,
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = colors.brand,
                            selectedTextColor = colors.brand,
                            unselectedIconColor = colors.muted,
                            unselectedTextColor = colors.muted,
                            indicatorColor = Color.Transparent,
                        ),
                    )
                }
            }
        }
    }
}

/** 1dp 发丝线（避开 HorizontalDivider 版本差异，用背景色薄条即可）。 */
@Composable
private fun Box2Hairline(color: Color) {
    androidx.compose.foundation.layout.Box(
        modifier = Modifier.fillMaxWidth().height(1.dp).background(color),
    )
}
