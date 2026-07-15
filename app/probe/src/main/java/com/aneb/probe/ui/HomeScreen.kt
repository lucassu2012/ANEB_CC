package com.aneb.probe.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import com.aneb.probe.data.TestRun
import com.aneb.probe.ui.components.pressable
import com.aneb.probe.ui.theme.AnebTheme
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 首页（严格按 ANEB_UI_v2 `home.html` idle 态重建）：深海军蓝底 + 顶部字标（ANEB PROBE）+
 * 中央**青绿光环（"开始"）** 作为 GO（轻触启动测量）+ 说明句 + 底部**网络抽屉**（节点/设备，
 * 可展开看连接模式/测试节点/AI 工作负载，"更换"入设置）。
 *
 * 纯 UI 层：数据经参数注入，[onStart] 触发既有 startRun 编排（测量语义不动）。
 * 底部 5 标签导航为跨屏结构，随导航重构一并落地（本屏不含底栏，由 MainActivity Scaffold 承载）。
 */
@Composable
fun HomeScreen(
    lastRun: TestRun?,
    running: Boolean,
    onStart: () -> Unit,
    onOpenSettings: () -> Unit,
    @Suppress("UNUSED_PARAMETER") onOpenLastResult: (String) -> Unit,
) {
    val colors = AnebTheme.colors
    Box(modifier = Modifier.fillMaxSize().background(colors.background)) {
        Column(
            modifier = Modifier.fillMaxSize().padding(horizontal = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.height(16.dp))
            Wordmark()

            Spacer(Modifier.weight(0.9f))

            CircularStartRing(running = running, onStart = onStart)
            Spacer(Modifier.height(16.dp))
            Text(
                "评估网络是否适合 AI 对话、编码和文件上传",
                fontSize = 11.sp,
                lineHeight = 17.sp,
                color = colors.faint,
                textAlign = TextAlign.Center,
                modifier = Modifier.widthIn(max = 290.dp),
            )

            Spacer(Modifier.weight(1.3f))

            NetworkSheet(lastRun = lastRun, onChangeNode = onOpenSettings)
            Spacer(Modifier.height(10.dp))
        }
    }
}

/** 顶部字标：弧线 AI 图标 + ANEB + PROBE（home.css .wordmark，55% 透明的浅色）。 */
@Composable
private fun Wordmark() {
    val c = Color(0x8CE1E8F2) // rgba(225,232,242,.55)
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
        Canvas(Modifier.size(18.dp)) {
            val s = size.minDimension
            val w = s * 0.075f
            // 半圆弧（AI 弧）
            drawArc(
                color = c, startAngle = 180f, sweepAngle = 180f, useCenter = false,
                topLeft = Offset(s * 0.15f, s * 0.30f), size = Size(s * 0.70f, s * 0.70f),
                style = Stroke(w, cap = StrokeCap.Round),
            )
            // 指针斜线 + 圆心点
            drawLine(c, Offset(s * 0.5f, s * 0.65f), Offset(s * 0.70f, s * 0.38f), strokeWidth = w, cap = StrokeCap.Round)
            drawCircle(c, radius = s * 0.05f, center = Offset(s * 0.5f, s * 0.65f))
        }
        Text("ANEB", fontSize = 15.sp, fontWeight = FontWeight(660), letterSpacing = 0.105.em, color = c)
        Text("PROBE", fontSize = 8.5.sp, fontWeight = FontWeight(720), letterSpacing = 0.2.em, color = c)
    }
}

/**
 * 中央青绿光环（home.css .ring-stroke idle 态）：mint→cyan→blue 锥形渐变细环 + 柔光，
 * 中心"开始"；轻触 = [onStart]（[running] 时禁用）。
 */
@Composable
private fun CircularStartRing(running: Boolean, onStart: () -> Unit) {
    val colors = AnebTheme.colors
    val mint = Color(0xFF67EDCC)
    val cyan = Color(0xFF43E1E6)
    val blue = Color(0xFF3EB4F1)
    Box(
        modifier = Modifier
            .size(198.dp)
            .clip(CircleShape)
            .pressable(onClick = onStart, enabled = !running),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.fillMaxSize()) {
            val stroke = 2.5.dp.toPx()
            val r = (size.minDimension - stroke * 3) / 2f
            val brush = Brush.sweepGradient(listOf(mint, cyan, blue, mint))
            // 柔光（更宽、低透明）
            drawCircle(brush = brush, radius = r, style = Stroke(stroke * 3f), alpha = 0.12f)
            // 主环
            drawCircle(brush = brush, radius = r, style = Stroke(stroke))
        }
        Text(
            text = if (running) "测试中" else "开始",
            fontSize = if (running) 22.sp else 33.sp,
            fontWeight = FontWeight(340),
            letterSpacing = (-0.045).em,
            color = colors.ink,
        )
    }
}

/** 底部网络抽屉（home.css .network-sheet）：摘要（节点 + 设备）+ 可展开明细。 */
@Composable
private fun NetworkSheet(lastRun: TestRun?, onChangeNode: () -> Unit) {
    val colors = AnebTheme.colors
    var expanded by rememberSaveable { mutableStateOf(false) }
    val shape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp)
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(shape)
            .background(colors.surface)
            .border(1.dp, colors.hairline, shape)
            .padding(bottom = 12.dp),
    ) {
        // 抓手
        Box(Modifier.fillMaxWidth().padding(vertical = 9.dp), contentAlignment = Alignment.Center) {
            Box(Modifier.width(36.dp).height(3.dp).clip(RoundedCornerShape(999.dp)).background(colors.faint))
        }
        // 摘要行（轻触展开/收起）
        Row(
            modifier = Modifier.fillMaxWidth().pressable(onClick = { expanded = !expanded }).padding(horizontal = 14.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            SheetIcon(glyph = "≋")
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(homeNodeLabel(lastRun), fontSize = 14.sp, color = colors.ink, maxLines = 1)
                Text(
                    "${android.os.Build.MODEL} · ${homeNetworkLabel(lastRun)}",
                    fontSize = 11.sp, color = colors.muted, maxLines = 1,
                )
            }
            Text(if (expanded) "▴" else "▾", fontSize = 13.sp, color = colors.muted)
        }
        if (expanded) {
            Spacer(Modifier.height(8.dp))
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

@Composable
private fun SheetIcon(glyph: String) {
    val colors = AnebTheme.colors
    Box(
        modifier = Modifier.size(27.dp).clip(CircleShape).border(1.dp, colors.hairline, CircleShape),
        contentAlignment = Alignment.Center,
    ) { Text(glyph, fontSize = 13.sp, color = colors.muted) }
}

@Composable
private fun SheetDetailRow(label: String, value: String, onChange: (() -> Unit)?) {
    val colors = AnebTheme.colors
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 15.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
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

/** 抽屉摘要节点标签（无实时节点名，用占位"仿真节点"口径）。 */
private fun homeNodeLabel(@Suppress("UNUSED_PARAMETER") run: TestRun?): String = "仿真节点 · E-01"

/** 连接模式（用上次 run 的传输通道近似）。 */
private fun homeConnMode(run: TestRun?): String = when (run?.transport?.lowercase()) {
    "wifi" -> "Wi-Fi · 多线程"
    "cellular" -> "蜂窝 · 多线程"
    else -> "自动选择 · 多线程"
}

/** 首页网络标签（无实时 ISP，用上次 run 的传输通道近似；无历史 run → 自动）。 */
private fun homeNetworkLabel(run: TestRun?): String = when (run?.transport?.lowercase()) {
    "wifi" -> "Wi-Fi 网络"
    "cellular" -> "蜂窝网络"
    else -> "自动选择网络"
}

/** run 网络/时间副标题（"电信 5G SA · 深圳 · 昨天"占位口径；无地理信息只显 transport+时间）。 */
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
