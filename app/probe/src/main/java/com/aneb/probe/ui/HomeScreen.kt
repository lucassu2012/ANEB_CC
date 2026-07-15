package com.aneb.probe.ui

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import com.aneb.probe.data.TestRun
import com.aneb.probe.engine.LiveTelemetry
import com.aneb.probe.ui.components.pressable
import com.aneb.probe.ui.theme.AnebTheme
import com.aneb.probe.ui.theme.Grade
import com.aneb.probe.ui.theme.LocalReducedMotion
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin

/**
 * 首页（严格按 ANEB_UI_v2 `home.{html,css,js}` 重建，含**状态机 + 实时数据驱动动效**）：
 * 同一个中央环随 [running] + 实时遥测**原地变形**——
 * - **idle**：青绿锥形渐变呼吸环 + "开始"（轻触启动测量）；
 * - **connecting**：amber 缺口环旋转 + "正在连接..."（连接测试节点，未见首个测量信号前）；
 * - **running**：270° 速度表（进度弧 + 指针，由 log 派生 progress.fraction 驱动）+ 中心实时
 *   Token 速率 + 顶部实时指标（Token/上行/Ping/抖动/丢包）；测量结束由 MainActivity 跳结果页。
 *
 * 底部网络抽屉（idle）支持**上拉拖拽**展开明细。全部动效在 LocalReducedMotion 下降级为静态终态。
 * 纯 UI 层：数据经参数注入，测量编排/日志/落库不动（[onCancel] 仅 cancel run 协程）。
 */

private enum class HomePhase { Idle, Connecting, Running }

@Composable
fun HomeScreen(
    lastRun: TestRun?,
    running: Boolean,
    telemetry: LiveTelemetry,
    logs: List<String>,
    onStart: () -> Unit,
    onCancel: () -> Unit,
    onOpenSettings: () -> Unit,
    @Suppress("UNUSED_PARAMETER") onOpenLastResult: (String) -> Unit,
) {
    val colors = AnebTheme.colors
    val progress = TestProgressParser.parse(logs)
    val phase = when {
        !running -> HomePhase.Idle
        telemetry.rttMs == null && telemetry.tokensReceived == 0 -> HomePhase.Connecting
        else -> HomePhase.Running
    }

    Box(modifier = Modifier.fillMaxSize().background(colors.background)) {
        if (phase != HomePhase.Idle) {
            CloseButton(onCancel, modifier = Modifier.align(Alignment.TopStart).padding(6.dp))
        }

        Column(
            modifier = Modifier.fillMaxSize().padding(horizontal = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.height(if (phase == HomePhase.Idle) 16.dp else 10.dp))
            Wordmark()

            when (phase) {
                HomePhase.Idle -> {
                    Spacer(Modifier.weight(0.9f))
                    IdleRing(onStart = onStart)
                    Spacer(Modifier.height(16.dp))
                    HeroCaption("评估网络是否适合 AI 对话、编码和文件上传")
                    Spacer(Modifier.weight(1.3f))
                    NetworkSheet(lastRun = lastRun, onChangeNode = onOpenSettings)
                    Spacer(Modifier.height(10.dp))
                }
                HomePhase.Connecting -> {
                    Spacer(Modifier.weight(1f))
                    ConnectingRing()
                    Spacer(Modifier.height(16.dp))
                    HeroCaption("正在连接测试节点…")
                    Spacer(Modifier.weight(1.2f))
                }
                HomePhase.Running -> {
                    Spacer(Modifier.height(12.dp))
                    LiveMetricsRow(telemetry)
                    Spacer(Modifier.weight(1f))
                    RunningGauge(fraction = progress.fraction.coerceIn(0f, 1f), telemetry = telemetry)
                    Spacer(Modifier.height(14.dp))
                    HeroCaption("正在检查 AI 持续输出与稳定性 · ${progress.phaseName}")
                    Spacer(Modifier.weight(1.2f))
                }
            }
        }
    }
}

@Composable
private fun HeroCaption(text: String) {
    Text(
        text,
        fontSize = 11.sp,
        lineHeight = 17.sp,
        color = AnebTheme.colors.faint,
        textAlign = TextAlign.Center,
        modifier = Modifier.widthIn(max = 300.dp),
    )
}

/** 左上角取消按钮（home.css .close-button），→ cancel run。 */
@Composable
private fun CloseButton(onCancel: () -> Unit, modifier: Modifier = Modifier) {
    val colors = AnebTheme.colors
    Box(
        modifier = modifier.size(36.dp).clip(CircleShape).pressable(onClick = onCancel),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.size(22.dp)) {
            val w = 1.6.dp.toPx()
            drawLine(colors.ink, Offset(size.width * 0.18f, size.height * 0.18f), Offset(size.width * 0.82f, size.height * 0.82f), w, StrokeCap.Round)
            drawLine(colors.ink, Offset(size.width * 0.82f, size.height * 0.18f), Offset(size.width * 0.18f, size.height * 0.82f), w, StrokeCap.Round)
        }
    }
}

/** 顶部字标：弧线 AI 图标 + ANEB + PROBE（home.css .wordmark）。 */
@Composable
private fun Wordmark() {
    val c = Color(0x8CE1E8F2)
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
        Canvas(Modifier.size(18.dp)) {
            val s = size.minDimension
            val w = s * 0.075f
            drawArc(color = c, startAngle = 180f, sweepAngle = 180f, useCenter = false, topLeft = Offset(s * 0.15f, s * 0.30f), size = Size(s * 0.70f, s * 0.70f), style = Stroke(w, cap = StrokeCap.Round))
            drawLine(c, Offset(s * 0.5f, s * 0.65f), Offset(s * 0.70f, s * 0.38f), strokeWidth = w, cap = StrokeCap.Round)
            drawCircle(c, radius = s * 0.05f, center = Offset(s * 0.5f, s * 0.65f))
        }
        Text("ANEB", fontSize = 15.sp, fontWeight = FontWeight(660), letterSpacing = 0.105.em, color = c)
        Text("PROBE", fontSize = 8.5.sp, fontWeight = FontWeight(720), letterSpacing = 0.2.em, color = c)
    }
}

private val RingMint = Color(0xFF67EDCC)
private val RingCyan = Color(0xFF43E1E6)
private val RingBlue = Color(0xFF3EB4F1)
private val Amber = Color(0xFFF5EFAD)
private val AmberDim = Color(0x66ECE99B)

/** idle 青绿呼吸环（home.css .ring-stroke idle）+ "开始"，轻触 [onStart]。 */
@Composable
private fun IdleRing(onStart: () -> Unit) {
    val colors = AnebTheme.colors
    val reduced = LocalReducedMotion.current
    val glow = if (reduced) {
        1f
    } else {
        val t = rememberInfiniteTransition(label = "breathe")
        t.animateFloat(0.72f, 1f, infiniteRepeatable(tween(1900), RepeatMode.Reverse), label = "glow").value
    }
    Box(modifier = Modifier.size(198.dp).clip(CircleShape).pressable(onClick = onStart), contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val stroke = 2.5.dp.toPx()
            val r = (size.minDimension - stroke * 3) / 2f
            val brush = Brush.sweepGradient(listOf(RingMint, RingCyan, RingBlue, RingMint))
            drawCircle(brush = brush, radius = r, style = Stroke(stroke * 3f), alpha = 0.12f * glow)
            drawCircle(brush = brush, radius = r, style = Stroke(stroke), alpha = glow)
        }
        Text("开始", fontSize = 33.sp, fontWeight = FontWeight(340), letterSpacing = (-0.045).em, color = colors.ink)
    }
}

/** connecting amber 缺口旋转环（home.css connect-spin 1.7s linear）+ "正在连接..."。 */
@Composable
private fun ConnectingRing() {
    val reduced = LocalReducedMotion.current
    val angle = if (reduced) {
        0f
    } else {
        val t = rememberInfiniteTransition(label = "spin")
        t.animateFloat(0f, 360f, infiniteRepeatable(tween(1700, easing = LinearEasing), RepeatMode.Restart), label = "ang").value
    }
    Box(modifier = Modifier.size(242.dp), contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val stroke = 3.dp.toPx()
            val inset = stroke
            val topLeft = Offset(inset, inset)
            val arc = Size(size.width - inset * 2, size.height - inset * 2)
            rotate(angle) {
                drawArc(
                    brush = Brush.sweepGradient(listOf(AmberDim, Amber, Amber, AmberDim)),
                    startAngle = 12f, sweepAngle = 318f, useCenter = false,
                    style = Stroke(stroke, cap = StrokeCap.Round), topLeft = topLeft, size = arc,
                )
            }
        }
        Text("正在连接...", fontSize = 18.sp, fontWeight = FontWeight.Medium, color = Amber)
    }
}

/** running 270° 速度表（home.css .gauge，指针 rotate(-135deg + progress*2.7deg)）。 */
@Composable
private fun RunningGauge(fraction: Float, telemetry: LiveTelemetry) {
    val colors = AnebTheme.colors
    val reduced = LocalReducedMotion.current
    val frac = if (reduced) fraction else animateFloatAsState(fraction, tween(450), label = "frac").value
    val grade = telemetry.aqsRunning?.let { Grade.fromAqsScore(it) }
    val band = if (grade != null) colors.gradeColor(grade) else colors.good
    val trackColor = Color(0x522F4369)
    val tickArgb = Color(0x59CEDAEB).toArgb()

    Box(modifier = Modifier.size(270.dp), contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val trackStroke = 16.dp.toPx()
            val progStroke = 10.dp.toPx()
            val pad = trackStroke / 2 + 4.dp.toPx()
            val topLeft = Offset(pad, pad)
            val arc = Size(size.width - pad * 2, size.height - pad * 2)
            val center = Offset(size.width / 2, size.height / 2)
            val r = arc.minDimension / 2f

            drawArc(color = trackColor, startAngle = 135f, sweepAngle = 270f, useCenter = false, style = Stroke(trackStroke), topLeft = topLeft, size = arc)
            if (frac > 0f) {
                drawArc(
                    brush = Brush.sweepGradient(listOf(RingCyan, RingMint, RingBlue, RingCyan)),
                    startAngle = 135f, sweepAngle = 270f * frac, useCenter = false,
                    style = Stroke(progStroke, cap = StrokeCap.Round), topLeft = topLeft, size = arc,
                )
            }
            val aRad = Math.toRadians(135.0 + 270.0 * frac)
            val len = r * 0.72f
            val tip = Offset(center.x + (cos(aRad) * len).toFloat(), center.y + (sin(aRad) * len).toFloat())
            drawLine(Color(0x66DDE7F4), center, tip, strokeWidth = 3.dp.toPx(), cap = StrokeCap.Round)
            drawCircle(Color(0xFF182139), radius = 5.dp.toPx(), center = center)
            drawCircle(Color(0x52E7EFFA), radius = 5.dp.toPx(), center = center, style = Stroke(1.dp.toPx()))

            val paint = android.graphics.Paint().apply {
                color = tickArgb
                textSize = 9.dp.toPx()
                textAlign = android.graphics.Paint.Align.CENTER
                isAntiAlias = true
            }
            intArrayOf(0, 25, 50, 75, 100).forEach { v ->
                val ta = Math.toRadians(135.0 + 270.0 * (v / 100.0))
                val tr = r + 12.dp.toPx()
                val tx = center.x + (cos(ta) * tr).toFloat()
                val ty = center.y + (sin(ta) * tr).toFloat() + 3.dp.toPx()
                drawContext.canvas.nativeCanvas.drawText(v.toString(), tx, ty, paint)
            }
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                telemetry.tokenRatePerSec?.let { "%.1f".format(it) } ?: "…",
                fontSize = 42.sp, fontWeight = FontWeight(440), letterSpacing = (-0.06).em, color = band,
            )
            Text("Token /秒", fontSize = 11.sp, fontWeight = FontWeight.Medium, color = colors.muted, modifier = Modifier.padding(top = 6.dp))
        }
    }
}

/** 顶部实时指标（home.css .live-metrics）：吞吐行 + 质量行（值 tile，无字段项显 —，R-10）。 */
@Composable
private fun LiveMetricsRow(telemetry: LiveTelemetry) {
    Column(modifier = Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        Row(horizontalArrangement = Arrangement.spacedBy(28.dp)) {
            MetricInline("↓", "Token 流速", telemetry.tokenRatePerSec?.let { "%.0f".format(it) } ?: "—", "/秒", RingCyan)
            MetricInline("↑", "上行", telemetry.upMbps?.let { "%.1f".format(it) } ?: "—", "Mbps", Color(0xFFA779F2))
        }
        Spacer(Modifier.height(12.dp))
        Row(modifier = Modifier.fillMaxWidth()) {
            QualityTile("Ping", telemetry.rttMs?.let { "${it.roundToInt()}" } ?: "—", "ms", Modifier.weight(1f))
            VDivider()
            QualityTile("抖动", telemetry.jitterMs?.let { "${it.roundToInt()}" } ?: "—", "ms", Modifier.weight(1f))
            VDivider()
            QualityTile("丢包", "—", "%", Modifier.weight(1f))
        }
    }
}

@Composable
private fun MetricInline(dir: String, label: String, value: String, unit: String, dirColor: Color) {
    val colors = AnebTheme.colors
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(dir, fontSize = 10.sp, fontWeight = FontWeight.Bold, color = dirColor)
            Text(label, fontSize = 10.sp, color = colors.muted)
        }
        Row(verticalAlignment = Alignment.Bottom) {
            Text(value, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = colors.ink)
            Text(" $unit", fontSize = 9.sp, color = colors.muted, modifier = Modifier.padding(bottom = 1.dp))
        }
    }
}

@Composable
private fun QualityTile(label: String, value: String, unit: String, modifier: Modifier = Modifier) {
    val colors = AnebTheme.colors
    Row(modifier = modifier.padding(horizontal = 10.dp), verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, fontSize = 10.sp, color = colors.muted)
        Row(verticalAlignment = Alignment.Bottom) {
            Text(value, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = colors.ink)
            Text(unit, fontSize = 8.sp, color = colors.muted, modifier = Modifier.padding(start = 1.dp, bottom = 1.dp))
        }
    }
}

@Composable
private fun VDivider() {
    Box(Modifier.width(1.dp).height(16.dp).background(AnebTheme.colors.hairline))
}

/**
 * 底部网络抽屉（home.css .network-sheet）：摘要（节点 + 设备）+ **上拉拖拽/轻触展开**明细。
 * 拖拽累计位移在释放时决定展开/收起（对齐 home.js 的 nearest-snap 语义）。
 */
@Composable
private fun NetworkSheet(lastRun: TestRun?, onChangeNode: () -> Unit) {
    val colors = AnebTheme.colors
    var expanded by rememberSaveable { mutableStateOf(false) }
    val detailsHeight by animateDpAsState(if (expanded) 150.dp else 0.dp, tween(350), label = "sheet")
    val shape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp)
    var acc = 0f
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(shape)
            .background(colors.surface)
            .border(1.dp, colors.hairline, shape)
            .padding(bottom = 12.dp),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .pointerInput(Unit) {
                    detectVerticalDragGestures(
                        onDragStart = { acc = 0f },
                        onDragEnd = { if (acc < -18f) expanded = true else if (acc > 18f) expanded = false },
                    ) { _, dy -> acc += dy }
                }
                .padding(vertical = 9.dp),
            contentAlignment = Alignment.Center,
        ) {
            Box(Modifier.width(36.dp).height(3.dp).clip(RoundedCornerShape(999.dp)).background(colors.faint))
        }
        Row(
            modifier = Modifier.fillMaxWidth().pressable(onClick = { expanded = !expanded }).padding(horizontal = 14.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            SheetIcon(glyph = "≋")
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(homeNodeLabel(lastRun), fontSize = 14.sp, color = colors.ink, maxLines = 1)
                Text("${android.os.Build.MODEL} · ${homeNetworkLabel(lastRun)}", fontSize = 11.sp, color = colors.muted, maxLines = 1)
            }
            Text(if (expanded) "▴" else "▾", fontSize = 13.sp, color = colors.muted)
        }
        Box(modifier = Modifier.fillMaxWidth().height(detailsHeight).clipToBounds()) {
            Column {
                HorizontalDivider(color = colors.hairline)
                Spacer(Modifier.height(10.dp))
                SheetDetailRow("连接模式", homeConnMode(lastRun), null)
                Spacer(Modifier.height(12.dp))
                SheetDetailRow("测试节点", "仿真节点 E-01", onChangeNode)
                Spacer(Modifier.height(12.dp))
                SheetDetailRow("AI 工作负载", "对话 · 编码 · 文件上传", null)
            }
        }
    }
}

@Composable
private fun SheetIcon(glyph: String) {
    val colors = AnebTheme.colors
    Box(modifier = Modifier.size(27.dp).clip(CircleShape).border(1.dp, colors.hairline, CircleShape), contentAlignment = Alignment.Center) {
        Text(glyph, fontSize = 13.sp, color = colors.muted)
    }
}

@Composable
private fun SheetDetailRow(label: String, value: String, onChange: (() -> Unit)?) {
    val colors = AnebTheme.colors
    Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 15.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(label, fontSize = 10.sp, color = colors.muted)
            Text(value, fontSize = 12.sp, color = colors.ink, modifier = Modifier.padding(top = 2.dp), maxLines = 1)
        }
        if (onChange != null) {
            Text(
                "更换",
                fontSize = 9.sp,
                color = colors.good,
                modifier = Modifier
                    .clip(RoundedCornerShape(999.dp))
                    .border(1.dp, colors.good.copy(alpha = 0.2f), RoundedCornerShape(999.dp))
                    .background(colors.good.copy(alpha = 0.05f))
                    .pressable(onClick = onChange)
                    .padding(horizontal = 9.dp, vertical = 6.dp),
            )
        }
    }
}

private fun homeNodeLabel(@Suppress("UNUSED_PARAMETER") run: TestRun?): String = "仿真节点 · E-01"

private fun homeConnMode(run: TestRun?): String = when (run?.transport?.lowercase()) {
    "wifi" -> "Wi-Fi · 多线程"
    "cellular" -> "蜂窝 · 多线程"
    else -> "自动选择 · 多线程"
}

private fun homeNetworkLabel(run: TestRun?): String = when (run?.transport?.lowercase()) {
    "wifi" -> "Wi-Fi 网络"
    "cellular" -> "蜂窝网络"
    else -> "自动选择网络"
}

/** run 网络/时间副标题（跨屏用：ResultScreen 等）。 */
internal object NetworkLabel {
    private val fmt = SimpleDateFormat("MM-dd HH:mm", Locale.US)

    fun forRun(run: TestRun): String {
        val transport = when (run.transport.lowercase()) {
            "wifi" -> "WiFi"
            "cellular" -> "蜂窝"
            else -> "自动"
        }
        return "$transport · ${run.mode} · ${fmt.format(Date(run.startedAtEpochMs))}"
    }
}
