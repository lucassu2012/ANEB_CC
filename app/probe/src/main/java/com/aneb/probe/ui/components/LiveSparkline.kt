package com.aneb.probe.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.aneb.probe.ui.theme.AnebTheme

/**
 * 实时波形条（测试中界面 AI 业务层的"冲击力"核心）——把一段滑窗数值序列画成竖条，
 * 超过 [poorThresholdMs] 的卡顿值用 poor 语义色高亮，其余用 base 分级色。设计稿视觉后续
 * 由 Claude Design 归一：本组件只做功能性绘制，颜色一律取 theme token（不硬编码）。
 *
 * 语义边界：本组件是**纯展示**，输入即 [LiveTelemetry.itlRecentMs] 等既有只读投影，
 * 不做任何测量口径计算（阈值只影响着色，不改任何落库/日志）。空序列显基线（不显 0 顶替）。
 *
 * @param values 滑窗数值（如校正 ITL ms / RTT ms）；空＝只画基线
 * @param poorThresholdMs 高亮阈值（超过即 poor 色）；null＝不高亮
 * @param barColor 常态竖条色（调用方传 grade 语义色）
 * @param height 波形高度
 */
@Composable
fun LiveSparkline(
    values: List<Double>,
    barColor: Color,
    modifier: Modifier = Modifier,
    poorThresholdMs: Double? = null,
    height: Dp = 46.dp,
) {
    val colors = AnebTheme.colors
    val poorColor = colors.poor
    val baseline = colors.hairline
    Canvas(
        modifier = modifier
            .fillMaxWidth()
            .height(height),
    ) {
        val w = size.width
        val h = size.height
        // 基线（底部细描边），无数据时也可见"待接收"骨架
        drawLine(
            color = baseline,
            start = Offset(0f, h - 1f),
            end = Offset(w, h - 1f),
            strokeWidth = 1f,
        )
        if (values.isEmpty()) return@Canvas

        // 尾对齐：最新值贴右侧（波形从右往左推进的直觉）
        val n = values.size
        val maxV = (values.maxOrNull() ?: 1.0).coerceAtLeast(1e-6)
        val slot = w / n.coerceAtLeast(1)
        val barW = (slot * 0.62f).coerceIn(1.5f, 10f)
        for (i in 0 until n) {
            val v = values[i]
            val frac = (v / maxV).coerceIn(0.0, 1.0).toFloat()
            val barH = (frac * (h - 3f)).coerceAtLeast(2f)
            val cx = slot * (i + 0.5f)
            val isPoor = poorThresholdMs != null && v > poorThresholdMs
            drawLine(
                color = if (isPoor) poorColor else barColor,
                start = Offset(cx, h - 1f),
                end = Offset(cx, h - 1f - barH),
                strokeWidth = barW,
                cap = StrokeCap.Round,
            )
        }
    }
}
