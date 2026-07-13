package com.aneb.probe.ui.components

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.ui.theme.AnebTheme
import com.aneb.probe.ui.theme.AnebType
import com.aneb.probe.ui.theme.Grade
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin

/**
 * token 脉冲环——ANEB 的标志视觉。环上每一格刻度 = 一个 token，卡顿处留红色缺口，
 * 一眼看出"转速表看不出"的节奏。设计基准：scratchpad/aneb_app_design.html 的 gauge。
 *
 * 三态（[GaugeMode]）：
 * - [GaugeMode.Idle]：暗刻度 + 中心播放按钮（品牌色圆），静止；
 * - [GaugeMode.Running]：grade 色弧填充到 [progress]、刻度点亮到同比例、
 *   [stallPositions] 处红色长刻度缺口；中心显示实时合成中的分数 + "…"；
 * - [GaugeMode.Result]：弧填充到 score/100、中心大分数 + 分级标签。
 *
 * 动画走 [animateFloatAsState]，尊重系统动画缩放（Settings 关动画时时长归零，直接落终值）。
 *
 * @param mode 三态
 * @param grade 语义分级（决定弧/刻度/分数颜色；null → 中性灰）
 * @param score 0–100 分数；Running 期为实时估计、Result 期为终值；null 显 "—"
 * @param progress 弧/刻度填充比例 0f..1f（Running 用真实进度；Result 可传 score/100）
 * @param stallPositions 卡顿刻度下标（0..tickCount-1），红色长刻度
 * @param tickCount 刻度总数（= 环上 token 格数），默认 60
 */
@Composable
fun PulseGauge(
    mode: GaugeMode,
    grade: Grade?,
    score: Int?,
    progress: Float,
    modifier: Modifier = Modifier,
    stallPositions: List<Int> = emptyList(),
    tickCount: Int = 60,
    size: Dp = 212.dp,
) {
    val colors = AnebTheme.colors
    val arcColor = colors.gradeColor(grade)

    // 尊重系统动画缩放：animateFloatAsState 用平台动画时钟，关动画时 tween 时长被缩到 0，
    // 直接落到 progress 终值（无需手动读 ANIMATOR_DURATION_SCALE）。
    val animatedProgress by animateFloatAsState(
        targetValue = progress.coerceIn(0f, 1f),
        animationSpec = tween(durationMillis = 600),
        label = "gauge-progress",
    )

    Box(modifier = modifier.size(size), contentAlignment = Alignment.Center) {
        Canvas(modifier = Modifier.size(size)) {
            val stroke = this.size.minDimension
            val center = Offset(this.size.width / 2f, this.size.height / 2f)
            val radius = stroke / 2f - 16f
            val stalls = stallPositions.toSet()

            // 底环（暗描边）
            drawCircle(
                color = colors.hairline,
                radius = radius,
                center = center,
                style = Stroke(width = 3f),
            )

            // 进度弧（Idle 不画；-90° 起点在顶端，顺时针填充）
            if (mode != GaugeMode.Idle && animatedProgress > 0f) {
                val arcWidth = if (mode == GaugeMode.Result) 9f else 7f
                drawArc(
                    color = arcColor,
                    startAngle = -90f,
                    sweepAngle = animatedProgress * 360f,
                    useCenter = false,
                    topLeft = Offset(center.x - radius, center.y - radius),
                    size = Size(radius * 2f, radius * 2f),
                    style = Stroke(width = arcWidth, cap = StrokeCap.Round),
                )
            }

            // 刻度：每格一 token；点亮到 progress 比例，卡顿处红色长刻度缺口
            val litFrac = if (mode == GaugeMode.Idle) 0f else animatedProgress
            for (i in 0 until tickCount) {
                val frac = if (tickCount > 1) i.toFloat() / (tickCount - 1) else 0f
                val angleRad = Math.toRadians((-90.0 + frac * 360.0))
                val isStall = i in stalls
                val lit = frac <= litFrac
                val r1 = radius - 6f
                val r2 = radius + if (isStall) 9f else 6f
                val col: Color = when {
                    isStall -> colors.poor
                    lit -> arcColor
                    else -> colors.hairline
                }
                val w = if (isStall) 2.4f else 1.6f
                val cosA = cos(angleRad).toFloat()
                val sinA = sin(angleRad).toFloat()
                drawLine(
                    color = col,
                    start = Offset(center.x + cosA * r1, center.y + sinA * r1),
                    end = Offset(center.x + cosA * r2, center.y + sinA * r2),
                    strokeWidth = w,
                    cap = StrokeCap.Round,
                )
            }
        }

        GaugeCenter(mode = mode, grade = grade, score = score, arcColor = arcColor)
    }
}

/** 环心内容：Idle 播放按钮 / Running 实时分数 / Result 大分数 + 分级标签 */
@Composable
private fun GaugeCenter(mode: GaugeMode, grade: Grade?, score: Int?, arcColor: Color) {
    val colors = AnebTheme.colors
    when (mode) {
        GaugeMode.Idle -> PlayButton(brand = colors.brand)
        GaugeMode.Running -> Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = (score?.toString() ?: "—"),
                style = AnebType.DisplayScore,
                fontSize = 52.sp,
                color = arcColor,
            )
            Text("正在合成体验分", fontSize = 10.5.sp, color = colors.muted)
        }
        GaugeMode.Result -> Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = (score?.toString() ?: "—"),
                style = AnebType.DisplayScore,
                fontSize = 62.sp,
                color = arcColor,
            )
            Text(
                text = grade?.labelFriendly ?: "—",
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = arcColor,
                textAlign = TextAlign.Center,
            )
            Text("Agent 体验分", fontSize = 10.5.sp, color = colors.muted)
        }
    }
}

/** 品牌色圆形播放键（Idle 中心）；纯绘制，点击交给外层 Box.clickable 承载 */
@Composable
private fun PlayButton(brand: Color) {
    Canvas(modifier = Modifier.size(58.dp).clip(androidx.compose.foundation.shape.CircleShape)) {
        drawCircle(color = brand, radius = this.size.minDimension / 2f)
        // 播放三角（略向右偏移视觉居中）
        val w = this.size.width
        val h = this.size.height
        val tri = Path().apply {
            moveTo(w * 0.40f, h * 0.34f)
            lineTo(w * 0.40f, h * 0.66f)
            lineTo(w * 0.66f, h * 0.50f)
            close()
        }
        drawPath(tri, color = Color.White)
    }
}

/** token 脉冲环三态 */
enum class GaugeMode { Idle, Running, Result }

// ------------------------------------------------------------------
// Preview（debugImplementation ui-tooling；不进 release）
// ------------------------------------------------------------------

@Preview(widthDp = 260, heightDp = 260, showBackground = true, backgroundColor = 0xFF0A0E17)
@Composable
private fun PreviewGaugeIdle() {
    AnebTheme(darkTheme = true) {
        PulseGauge(mode = GaugeMode.Idle, grade = null, score = null, progress = 0f)
    }
}

@Preview(widthDp = 260, heightDp = 260, showBackground = true, backgroundColor = 0xFF0A0E17)
@Composable
private fun PreviewGaugeRunning() {
    AnebTheme(darkTheme = true) {
        PulseGauge(
            mode = GaugeMode.Running,
            grade = Grade.Good,
            score = 62,
            progress = 0.62f,
            stallPositions = listOf(12, 23),
        )
    }
}

@Preview(widthDp = 260, heightDp = 260, showBackground = true, backgroundColor = 0xFF0A0E17)
@Composable
private fun PreviewGaugeResult() {
    AnebTheme(darkTheme = true) {
        val s = 89
        PulseGauge(mode = GaugeMode.Result, grade = Grade.Excellent, score = s, progress = s / 100f)
    }
}

/** 便利：Double 分数 → 四舍五入 Int（仪表 center 展示口径，不改测量值） */
internal fun Double.toGaugeScore(): Int = this.roundToInt()
