package com.aneb.probe.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.engine.SpeedRunner
import com.aneb.probe.ui.theme.AnebTheme
import kotlin.math.ceil
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.sin

/**
 * 网络基本性能模式（SpeedTest 同款）测试屏——[SpeedRunner] 的展示层。
 *
 * 与 [HomeScreen]（Token 体验模式）并列的模式屏，顶部分段可切回 Token。视觉目标：**SpeedTest 级
 * 动态**——指针/大数随[SpeedRunner]的**实时上行吞吐**（会随网络波动）高频刷新，火花线记录抖动轨迹。
 *
 * 纯展示：所有数值来自 [SpeedRunner.Sample]（观测态，非 AQS/KPI）；测速逻辑在引擎侧。
 */
@Composable
fun SpeedTestScreen(
    sample: SpeedRunner.Sample?,
    running: Boolean,
    onStart: () -> Unit,
    onCancel: () -> Unit,
) {
    val c = AnebTheme.colors
    // 实时上行火花线 + 峰值（每次起测清空）
    val history = remember { mutableStateListOf<Float>() }
    var peakUp by remember { mutableStateOf(0f) }
    LaunchedEffect(running) {
        if (running) {
            history.clear()
            peakUp = 0f
        }
    }
    LaunchedEffect(sample) {
        val up = sample?.upMbps?.toFloat() ?: return@LaunchedEffect
        history.add(up)
        if (history.size > 64) history.removeAt(0)
        if (up > peakUp) peakUp = up
    }

    val phase = sample?.phase
    val isPing = phase == SpeedRunner.Phase.Ping
    val accent = when (phase) {
        SpeedRunner.Phase.Ping -> c.good
        SpeedRunner.Phase.Upload -> c.brand
        else -> c.excellent
    }
    // 量程自适应：随峰值上探，最小 20 Mbps，取整到 10
    val gaugeMax = max(20f, ceil((peakUp * 1.15f) / 10f) * 10f)
    val targetFrac = if (isPing) {
        // ping 阶段：RTT→0..1（0..200ms，越低越满）；无测量值保持 0（R-10：null 不驱动几何显示为"满/优"）
        val r = sample?.rttMs
        if (r == null) 0f else (1f - (r.toFloat() / 200f)).coerceIn(0f, 1f)
    } else {
        ((sample?.upMbps ?: 0.0).toFloat() / gaugeMax).coerceIn(0f, 1f)
    }
    val frac by animateFloatAsState(targetFrac, tween(220), label = "speedFrac")

    val valueText = when {
        isPing -> sample?.rttMs?.let { "%.0f".format(it) } ?: "—"
        else -> (sample?.upMbps ?: 0.0).let { "%.1f".format(it) }
    }
    val unit = if (isPing) "ms 时延" else "Mbps 上行"
    val phaseLabel = when (phase) {
        SpeedRunner.Phase.Ping -> "时延 · 抖动测速中"
        SpeedRunner.Phase.Upload -> "上行速率测速中（随网络波动）"
        SpeedRunner.Phase.Done -> "测速完成"
        null -> if (running) "准备中…" else "点击开始网络基本性能测速"
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 12.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(16.dp))

        // ---- 主仪表 ----
        SpeedGauge(frac = frac, valueText = valueText, unit = unit, phaseLabel = phaseLabel, accent = accent)

        Spacer(Modifier.height(20.dp))

        // ---- 实时上行火花线（体现波动）----
        Sparkline(
            values = history,
            color = c.brand,
            trackColor = c.surfaceMuted,
            modifier = Modifier
                .fillMaxWidth()
                .height(54.dp),
        )

        Spacer(Modifier.height(18.dp))

        // ---- 指标磁贴 ----
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            StatTile("时延", fmt(sample?.rttMs, "%.0f"), "ms", c.good, Modifier.weight(1f))
            StatTile("抖动", fmt(sample?.jitterMs, "%.0f"), "ms", c.fair, Modifier.weight(1f))
            StatTile("上行峰值", if (peakUp > 0f) "%.1f".format(peakUp) else "—", "Mbps", c.brand, Modifier.weight(1f))
            StatTile("下行", "—", "待接入", c.neutral, Modifier.weight(1f))
        }

        Spacer(Modifier.height(16.dp))

        // ---- 结论（测速完成后给判定，满足"每个场景一个结论"）----
        if (phase == SpeedRunner.Phase.Done) {
            ConclusionCard(peakUp = peakUp, rttMs = sample?.rttMs, jitterMs = sample?.jitterMs)
        }

        Spacer(Modifier.height(24.dp))

        // ---- GO / 取消 ----
        val btnColor = if (running) c.poor else c.brand
        val btnLabel = if (running) "取消测速" else "GO · 开始测速"
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
                .clip(RoundedCornerShape(16.dp))
                .background(btnColor)
                .clickable { if (running) onCancel() else onStart() },
            contentAlignment = Alignment.Center,
        ) {
            Text(btnLabel, color = Color(0xFF05121A), fontSize = 18.sp, fontWeight = FontWeight.Bold)
        }
        Spacer(Modifier.height(8.dp))
        Text(
            "口径：应用层上行吞吐（socket 发送节奏≈真实网络上行速率）与 echo 往返时延；观测展示，不进 AQS。下行需服务端全速端点，后续接入。",
            color = c.faint,
            fontSize = 11.sp,
        )
    }
}

/** 模式分段开关（Token 体验 | 网络基本性能）——由 MainActivity 在 Test tab 顶部共享渲染。 */
@Composable
fun TestModeSegments(
    basicSelected: Boolean,
    enabled: Boolean,
    onSelectToken: () -> Unit,
    onSelectBasic: () -> Unit,
) {
    val c = AnebTheme.colors
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(c.surfaceMuted)
            .padding(4.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Segment("Token 体验", selected = !basicSelected, enabled = enabled, onClick = onSelectToken, modifier = Modifier.weight(1f))
        Segment("网络基本性能", selected = basicSelected, enabled = enabled, onClick = onSelectBasic, modifier = Modifier.weight(1f))
    }
}

@Composable
private fun androidx.compose.foundation.layout.RowScope.Segment(
    label: String,
    selected: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val c = AnebTheme.colors
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(9.dp))
            .background(if (selected) c.brand else Color.Transparent)
            .clickable(enabled = enabled && !selected) { onClick() }
            .padding(vertical = 10.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            label,
            color = if (selected) Color(0xFF05121A) else c.muted,
            fontSize = 14.sp,
            fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
        )
    }
}

@Composable
private fun SpeedGauge(frac: Float, valueText: String, unit: String, phaseLabel: String, accent: Color) {
    val c = AnebTheme.colors
    Box(contentAlignment = Alignment.Center, modifier = Modifier.size(258.dp)) {
        Canvas(Modifier.fillMaxSize()) {
            val stroke = 22f
            val start = 135f
            val sweepTotal = 270f
            val topLeft = Offset(stroke, stroke)
            val arcSize = Size(size.width - stroke * 2, size.height - stroke * 2)
            drawArc(
                color = c.surfaceMuted, startAngle = start, sweepAngle = sweepTotal, useCenter = false,
                topLeft = topLeft, size = arcSize, style = Stroke(width = stroke, cap = StrokeCap.Round),
            )
            drawArc(
                color = accent, startAngle = start, sweepAngle = (sweepTotal * frac).coerceIn(0f, sweepTotal),
                useCenter = false, topLeft = topLeft, size = arcSize, style = Stroke(width = stroke, cap = StrokeCap.Round),
            )
            // 指针
            val ang = Math.toRadians((start + sweepTotal * frac).toDouble())
            val cx = size.width / 2
            val cy = size.height / 2
            val r = size.width / 2 - stroke - 6f
            val nx = cx + r * cos(ang).toFloat()
            val ny = cy + r * sin(ang).toFloat()
            drawLine(accent, Offset(cx, cy), Offset(nx, ny), strokeWidth = 6f, cap = StrokeCap.Round)
            drawCircle(accent, radius = 11f, center = Offset(cx, cy))
            drawCircle(c.background, radius = 5f, center = Offset(cx, cy))
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(valueText, color = c.ink, fontSize = 54.sp, fontWeight = FontWeight.Bold)
            Text(unit, color = c.muted, fontSize = 15.sp)
            Spacer(Modifier.height(8.dp))
            Text(phaseLabel, color = accent, fontSize = 13.sp, fontWeight = FontWeight.Medium)
        }
    }
}

@Composable
private fun Sparkline(values: List<Float>, color: Color, trackColor: Color, modifier: Modifier = Modifier) {
    Canvas(modifier.clip(RoundedCornerShape(10.dp))) {
        drawLine(trackColor, Offset(0f, size.height), Offset(size.width, size.height), strokeWidth = 2f)
        if (values.size < 2) return@Canvas
        val vmax = max(1f, values.max())
        val n = values.size
        val dx = size.width / (n - 1).toFloat()
        var prev = Offset(0f, size.height - (values[0] / vmax) * size.height)
        for (i in 1 until n) {
            val x = dx * i
            val y = size.height - (values[i] / vmax) * size.height
            val cur = Offset(x, y)
            drawLine(color, prev, cur, strokeWidth = 4f, cap = StrokeCap.Round)
            prev = cur
        }
    }
}

@Composable
private fun androidx.compose.foundation.layout.RowScope.StatTile(
    label: String,
    value: String,
    unit: String,
    accent: Color,
    modifier: Modifier = Modifier,
) {
    val c = AnebTheme.colors
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(c.surface)
            .padding(vertical = 12.dp, horizontal = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(label, color = c.muted, fontSize = 11.sp)
        Spacer(Modifier.height(4.dp))
        Text(value, color = accent, fontSize = 20.sp, fontWeight = FontWeight.Bold)
        Text(unit, color = c.faint, fontSize = 10.sp)
    }
}

@Composable
private fun ConclusionCard(peakUp: Float, rttMs: Double?, jitterMs: Double?) {
    val c = AnebTheme.colors
    // 简单判定门限（观测展示口径）：上行≥10 良好 / 时延≤60 低时延 / 抖动≤20 稳定
    val upOk = peakUp >= 10f
    val rttOk = (rttMs ?: 999.0) <= 60.0
    val jitOk = (jitterMs ?: 999.0) <= 20.0
    val verdict = when {
        upOk && rttOk && jitOk -> "网络基本性能优良：上行充足、时延低、连接稳定，适合实时交互类 AI 应用。"
        !upOk && rttOk -> "时延低但上行偏弱：上传大文件/多模态输入可能偏慢，短交互体验良好。"
        !rttOk && upOk -> "带宽尚可但时延偏高：首字响应会偏慢，弱网可能影响连续对话流畅度。"
        else -> "网络承载偏弱：上行与时延均需改善，AI 交互可能出现明显等待与卡顿。"
    }
    val head = if (upOk && rttOk && jitOk) c.excellent else if (upOk || rttOk) c.fair else c.poor
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(c.surface)
            .padding(14.dp),
    ) {
        Text("测试结论", color = head, fontSize = 13.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(6.dp))
        Text(verdict, color = c.ink, fontSize = 13.sp)
        Spacer(Modifier.height(8.dp))
        Text(
            "上行峰值 %.1f Mbps · 时延 %s ms · 抖动 %s ms".format(
                peakUp, fmt(rttMs, "%.0f"), fmt(jitterMs, "%.0f"),
            ),
            color = c.muted,
            fontSize = 11.sp,
        )
    }
}

private fun fmt(v: Double?, pattern: String): String = v?.let { pattern.format(it) } ?: "—"
