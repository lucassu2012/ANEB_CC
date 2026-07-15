package com.aneb.probe.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.aneb.probe.ui.theme.AnebShapes
import com.aneb.probe.ui.theme.AnebTheme

/**
 * v2（suite.css `.suite-card`）卡片容器：面色 + 发丝描边 + 连续圆角（22dp），承载专业结果页
 * 各分区（AQS 头条 / 子分与权重 / KPI 明细 / REACH / 元信息）。跨屏复用（后续 history /
 * server / settings 同款）。主题跟随（深浅色自动切）。
 *
 * @param padding 内容内边距（默认 14dp，对齐 suite-card 13–14px）
 */
@Composable
fun SuiteCard(
    modifier: Modifier = Modifier,
    padding: Dp = 14.dp,
    content: @Composable ColumnScope.() -> Unit,
) {
    val colors = AnebTheme.colors
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(AnebShapes.card)
            .background(colors.surface)
            .border(1.dp, colors.hairline, AnebShapes.card)
            .padding(padding),
        content = content,
    )
}
