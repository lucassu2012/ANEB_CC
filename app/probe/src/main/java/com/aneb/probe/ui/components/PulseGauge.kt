package com.aneb.probe.ui.components

import androidx.compose.animation.core.animateFloatAsState
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
import com.aneb.probe.ui.theme.AnebMotion
import com.aneb.probe.ui.theme.AnebTheme
import com.aneb.probe.ui.theme.AnebType
import com.aneb.probe.ui.theme.Grade
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin

/**
 * iOS 仪表盘 PulseGauge——照交接稿 README §7 与 screens/aneb.js 参数化 1:1 重写：
 *
 * 几何（212 单位坐标系 · 圆心 106；按 [size] 等比缩放）：
 * - 外圈灰底轨（[AnebColors.hairline]）+ 彩色进度弧（stroke 10、圆头、−90° 从顶起、顺时针）；
 *   偏移 `C*(1-score/100)`（C=578.05, r=92），即 sweep = progress*360°。
 * - 内圈 48 刻度点阵：点亮数 `round(progress*48)`，内半径 74、外半径 84，宽 2.4 圆头；
 *   点亮用分级色 opacity .92、未亮用文本色 opacity .16；卡顿刻度([stallPositions])红色长刻度。
 * - 中心巨大分数（计数 settle：[animatedCount]）。
 *
 * 三态（[GaugeMode]）：
 * - [GaugeMode.Idle]：暗刻度 + 中心 62px 品牌色 GO 按钮 + 三层脉冲环（[Modifier.pulseRing]）；
 * - [GaugeMode.Running]：弧/刻度填充到 [progress]、卡顿缺口，中心实时分数 + "正在合成…"；
 * - [GaugeMode.Result]：弧填充到 score/100、中心大分数 + 分级标签。
 *
 * 动画走 [animateFloatAsState]（尊重系统动画缩放：关动画时时长归零直接落终值）+ [animatedCount]
 * （尊重 LocalReducedMotion）。数字永远显示终值（缩略图/首帧安全）。
 *
 * 签名与既有调用点保持兼容（HomeScreen/TestingScreen/ResultScreen 无需改动）。
 *
 * @param mode 三态
 * @param grade 语义分级（决定弧/刻度/分数颜色；null → 中性灰）
 * @param score 0–100 分数；Running 期为实时估计、Result 期为终值；null 显 "—"
 * @param progress 弧/刻度填充比例 0f..1f（Running 用真实进度；Result 传 score/100）
 * @param stallPositions 卡顿刻度下标（0..tickCount-1），红色长刻度缺口
 * @param tickCount 刻度总数（iOS 基线 48）
 * @param centerValue 中心巨大数覆盖（非 null 时替代默认 AQS/分数渲染，只投影既有量、不改测量）；
 *   null → 走既有中心渲染（零破坏既有调用）。Idle 态始终显 GO 按钮，不承载覆盖。
 * @param centerLabel 覆盖时中心小字标签（配合 [centerValue]；null 则只显覆盖大数）
 */
@Composable
fun PulseGauge(
    mode: GaugeMode,
    grade: Grade?,
    score: Int?,
    progress: Float,
    modifier: Modifier = Modifier,
    stallPositions: List<Int> = emptyList(),
    tickCount: Int = 48,
    size: Dp = 212.dp,
    centerValue: String? = null,
    centerLabel: String? = null,
) {
    val colors = AnebTheme.colors
    val arcColor = colors.gradeColor(grade)

    // 尊重系统动画缩放：tween 在关动画时缩到 0，直接落 progress 终值（无需手读 duration scale）。
    val animatedProgress by animateFloatAsState(
        targetValue = progress.coerceIn(0f, 1f),
        animationSpec = AnebMotion.easeOutTween(AnebMotion.Dur4),
        label = "gauge-progress",
    )

    Box(modifier = modifier.size(size), contentAlignment = Alignment.Center) {
        Canvas(modifier = Modifier.size(size)) {
            val unit = this.size.minDimension / 212f // 212 单位坐标系等比缩放
            val center = Offset(this.size.width / 2f, this.size.height / 2f)
            val arcR = 92f * unit
            val arcStroke = 10f * unit
            val rin = 74f * unit
            val rout = 84f * unit
            val tickStroke = 2.4f * unit
            val stalls = stallPositions.toSet()
            val litFrac = if (mode == GaugeMode.Idle) 0f else animatedProgress

            // 外圈灰底轨
            drawCircle(
                color = colors.hairline,
                radius = arcR,
                center = center,
                style = Stroke(width = arcStroke),
            )

            // 彩色进度弧（Idle 不画；−90° 顶起、顺时针 sweep = progress*360）
            if (mode != GaugeMode.Idle && animatedProgress > 0f) {
                drawArc(
                    color = arcColor,
                    startAngle = -90f,
                    sweepAngle = animatedProgress * 360f,
                    useCenter = false,
                    topLeft = Offset(center.x - arcR, center.y - arcR),
                    size = Size(arcR * 2f, arcR * 2f),
                    style = Stroke(width = arcStroke, cap = StrokeCap.Round),
                )
            }

            // 内圈 48 刻度点阵（radial 短线 rin→rout）；点亮到 round(progress*N)，卡顿处红色长刻度
            val litCount = (litFrac * tickCount).roundToInt()
            for (i in 0 until tickCount) {
                val angleRad = Math.toRadians(-90.0 + (i.toDouble() / tickCount) * 360.0)
                val isStall = i in stalls
                val lit = i < litCount
                val cosA = cos(angleRad).toFloat()
                val sinA = sin(angleRad).toFloat()
                val r2 = if (isStall) rout + 4f * unit else rout
                val col: Color = when {
                    isStall -> colors.poor
                    lit -> arcColor.copy(alpha = 0.92f)
                    else -> colors.ink.copy(alpha = 0.16f)
                }
                drawLine(
                    color = col,
                    start = Offset(center.x + cosA * rin, center.y + sinA * rin),
                    end = Offset(center.x + cosA * r2, center.y + sinA * r2),
                    strokeWidth = if (isStall) tickStroke * 1.2f else tickStroke,
                    cap = StrokeCap.Round,
                )
            }
        }

        GaugeCenter(
            mode = mode,
            grade = grade,
            score = score,
            arcColor = arcColor,
            centerValue = centerValue,
            centerLabel = centerLabel,
        )
    }
}

/** 环心内容：Idle GO 按钮(+脉冲环) / Running 实时分数 / Result 大分数 + 分级标签 */
@Composable
private fun GaugeCenter(
    mode: GaugeMode,
    grade: Grade?,
    score: Int?,
    arcColor: Color,
    centerValue: String?,
    centerLabel: String?,
) {
    val colors = AnebTheme.colors
    // 覆盖投影：Running/Result 下 centerValue 非 null 时用「大数 + 小字」替代默认 AQS/分数渲染
    // （只把既有 LiveTelemetry 字段投影到中心，不改测量）；Idle 恒显 GO 按钮，不承载覆盖。
    if (mode != GaugeMode.Idle && centerValue != null) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = centerValue,
                style = AnebType.DisplayScore,
                fontSize = 40.sp,
                color = arcColor,
                maxLines = 1,
                softWrap = false,
            )
            if (centerLabel != null) {
                Text(centerLabel, style = AnebType.Caption, fontSize = 11.sp, color = colors.muted)
            }
        }
        return
    }
    when (mode) {
        GaugeMode.Idle -> PlayButton(brand = colors.brand)
        GaugeMode.Running -> Column(horizontalAlignment = Alignment.CenterHorizontally) {
            val shown = animatedCount(score)
            Text(
                text = shown?.toString() ?: "—",
                style = AnebType.DisplayScore,
                fontSize = 52.sp,
                color = arcColor,
            )
            Text("正在合成体验分", style = AnebType.Caption, fontSize = 10.5.sp, color = colors.muted)
        }
        GaugeMode.Result -> Column(horizontalAlignment = Alignment.CenterHorizontally) {
            val shown = animatedCount(score)
            Text(
                text = shown?.toString() ?: "—",
                style = AnebType.DisplayScore,
                fontSize = 64.sp,
                color = arcColor,
            )
            Text(
                text = grade?.labelFriendly ?: "—",
                fontSize = 14.sp,
                fontWeight = FontWeight(640),
                color = arcColor,
                textAlign = TextAlign.Center,
            )
            Text("Agent 体验分", style = AnebType.Caption, fontSize = 11.sp, color = colors.muted)
        }
    }
}

/**
 * 品牌色 62px 圆形 GO 播放键（Idle 中心）+ 三层脉冲环（[Modifier.pulseRing]，尊重减弱动效）。
 * 点击交给外层 Box.clickable 承载（HomeScreen）。
 */
@Composable
private fun PlayButton(brand: Color) {
    Box(
        modifier = Modifier.size(62.dp).pulseRing(brand),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.size(62.dp).clip(androidx.compose.foundation.shape.CircleShape)) {
            drawCircle(color = brand, radius = this.size.minDimension / 2f)
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
}

/** token 脉冲环三态 */
enum class GaugeMode { Idle, Running, Result }

// ------------------------------------------------------------------
// Preview（debugImplementation ui-tooling；不进 release）
// ------------------------------------------------------------------

@Preview(widthDp = 260, heightDp = 260, showBackground = true, backgroundColor = 0xFF000000)
@Composable
private fun PreviewGaugeIdle() {
    AnebTheme(darkTheme = true) {
        PulseGauge(mode = GaugeMode.Idle, grade = null, score = null, progress = 0f)
    }
}

@Preview(widthDp = 260, heightDp = 260, showBackground = true, backgroundColor = 0xFF000000)
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

@Preview(widthDp = 260, heightDp = 260, showBackground = true, backgroundColor = 0xFF000000)
@Composable
private fun PreviewGaugeResult() {
    AnebTheme(darkTheme = true) {
        val s = 89
        PulseGauge(mode = GaugeMode.Result, grade = Grade.Excellent, score = s, progress = s / 100f)
    }
}

/** 便利：Double 分数 → 四舍五入 Int（仪表 center 展示口径，不改测量值） */
internal fun Double.toGaugeScore(): Int = this.roundToInt()
