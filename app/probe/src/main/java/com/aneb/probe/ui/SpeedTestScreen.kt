package com.aneb.probe.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
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
    // 实时吞吐火花线（当前相：下行/上行）+ 上下行峰值（每次起测清空）
    val history = remember { mutableStateListOf<Float>() }
    var peakUp by remember { mutableStateOf(0f) }
    var peakDown by remember { mutableStateOf(0f) }
    LaunchedEffect(running) {
        if (running) {
            history.clear()
            peakUp = 0f
            peakDown = 0f
        }
    }
    LaunchedEffect(sample) {
        // 火花线记录当前相的吞吐（下行相记 downMbps，上行相记 upMbps）
        val v = (sample?.downMbps ?: sample?.upMbps)?.toFloat() ?: return@LaunchedEffect
        history.add(v)
        if (history.size > 64) history.removeAt(0)
        sample?.upMbps?.toFloat()?.let { if (it > peakUp) peakUp = it }
        sample?.downMbps?.toFloat()?.let { if (it > peakDown) peakDown = it }
    }

    val phase = sample?.phase
    val isPing = phase == SpeedRunner.Phase.Ping
    val isDownload = phase == SpeedRunner.Phase.Download
    val accent = when (phase) {
        SpeedRunner.Phase.Ping -> c.good
        SpeedRunner.Phase.Download -> c.excellent // 下行 = 薄荷绿
        SpeedRunner.Phase.Upload -> c.brand // 上行 = 系统蓝
        else -> c.excellent
    }
    // 当前相主指标（下行相 downMbps / 上行相 upMbps）
    val mainVal = if (isDownload) sample?.downMbps else sample?.upMbps
    val phasePeak = if (isDownload) peakDown else peakUp
    // 量程自适应：随当前相峰值上探，最小 20 Mbps，取整到 10
    val gaugeMax = max(20f, ceil((phasePeak * 1.15f) / 10f) * 10f)
    val targetFrac = if (isPing) {
        // ping 阶段：RTT→0..1（0..200ms，越低越满）；无测量值保持 0（R-10：null 不驱动几何显示为"满/优"）
        val r = sample?.rttMs
        if (r == null) 0f else (1f - (r.toFloat() / 200f)).coerceIn(0f, 1f)
    } else {
        ((mainVal ?: 0.0).toFloat() / gaugeMax).coerceIn(0f, 1f)
    }
    val frac by animateFloatAsState(targetFrac, tween(220), label = "speedFrac")

    val valueText = when {
        isPing -> sample?.rttMs?.let { "%.0f".format(it) } ?: "—"
        else -> (mainVal ?: 0.0).let { "%.1f".format(it) }
    }
    val unit = when {
        isPing -> "ms 时延"
        isDownload -> "Mbps 下行"
        else -> "Mbps 上行"
    }
    val phaseLabel = when (phase) {
        SpeedRunner.Phase.Ping -> "时延 · 抖动测速中"
        SpeedRunner.Phase.Download -> "下行速率测速中（随网络波动）"
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

        // ---- 实时吞吐火花线（当前相色，体现波动）----
        Sparkline(
            values = history,
            color = accent,
            trackColor = c.surfaceMuted,
            modifier = Modifier
                .fillMaxWidth()
                .height(54.dp),
        )

        Spacer(Modifier.height(18.dp))

        // ---- 指标磁贴：时延 / 抖动 / 下行峰值 / 上行峰值 ----
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            StatTile("时延", fmt(sample?.rttMs, "%.0f"), "ms", c.good, Modifier.weight(1f))
            StatTile("抖动", fmt(sample?.jitterMs, "%.0f"), "ms", c.fair, Modifier.weight(1f))
            StatTile("下行峰值", if (peakDown > 0f) "%.1f".format(peakDown) else "—", "Mbps", c.excellent, Modifier.weight(1f))
            StatTile("上行峰值", if (peakUp > 0f) "%.1f".format(peakUp) else "—", "Mbps", c.brand, Modifier.weight(1f))
        }

        Spacer(Modifier.height(16.dp))

        // ---- 结论（测速完成后给判定，满足"每个场景一个结论"）----
        if (phase == SpeedRunner.Phase.Done) {
            ConclusionCard(
                peakDown = peakDown, peakUp = peakUp,
                rttMs = sample?.rttMs, jitterMs = sample?.jitterMs,
                reqFailed = sample?.reqFailed ?: 0, reqTotal = sample?.reqTotal ?: 0,
            )
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
            "口径：下行＝unpaced /download 排空实测吞吐（读到即到达字节）；上行＝应用层 socket 发送吞吐（≈真实上行）；时延＝echo 往返墙钟。均为观测展示，不进 AQS。",
            color = c.faint,
            fontSize = 11.sp,
        )
    }
}

/** 模式分段开关——由 [TestModeProfiles.ALL] **数据驱动**；MainActivity 在 Test tab 顶部共享渲染。
 *  新增测试模式只需往 ALL 加一个 profile，本开关自动多一段。 */
@Composable
fun TestModeSegments(
    profiles: List<TestModeProfile>,
    selectedId: String,
    enabled: Boolean,
    onSelect: (String) -> Unit,
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
        profiles.forEach { p ->
            Segment(
                label = p.displayName,
                selected = p.id == selectedId,
                enabled = enabled,
                onClick = { onSelect(p.id) },
                modifier = Modifier.weight(1f),
            )
        }
    }
}

/** 模式信息条：当前模式的副标 + 指标片（实时动态指标高亮着色）——数据源 [TestModeProfile]，
 *  直观呈现 /goal 点 3 的“测哪些指标、哪些是动态的”。MainActivity 在测量前的静息态渲染。 */
@Composable
fun ModeProfileStrip(profile: TestModeProfile) {
    val c = AnebTheme.colors
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(c.surface)
            .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Text(profile.tagline, color = c.muted, fontSize = 12.sp, fontWeight = FontWeight.Medium)
        Spacer(Modifier.height(8.dp))
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            // v2（INV-3 单一事实源）：优先读权威 facet——facet3 动态呈现指标（高亮）在前，
            // facet2 参与打分的静态指标在后（按名尽力去重）；facet 缺省的旧档回落展示投影。
            if (profile.live.isNotEmpty() || profile.metricSpecs.isNotEmpty()) {
                val dynamicNames = profile.live.map { it.label }.toSet()
                profile.live.forEach { lm -> MetricChip(lm.label, dynamic = true) }
                profile.metricSpecs
                    .filter { it.scored && it.name !in dynamicNames }
                    .forEach { m -> MetricChip(m.name, dynamic = false) }
            } else {
                profile.metrics.forEach { m -> MetricChip(m.name, dynamic = m.dynamic) }
            }
        }
        Spacer(Modifier.height(6.dp))
        Text("填充色＝实时动态指标（随网络高频波动）", color = c.faint, fontSize = 10.sp)
    }
}

@Composable
private fun MetricChip(name: String, dynamic: Boolean) {
    val c = AnebTheme.colors
    val bg = if (dynamic) c.brand else c.surfaceMuted
    val fg = if (dynamic) Color(0xFF05121A) else c.muted
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(7.dp))
            .background(bg)
            .padding(horizontal = 8.dp, vertical = 5.dp),
    ) {
        Text(
            name,
            color = fg,
            fontSize = 11.sp,
            fontWeight = if (dynamic) FontWeight.Bold else FontWeight.Medium,
        )
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
private fun ConclusionCard(
    peakDown: Float,
    peakUp: Float,
    rttMs: Double?,
    jitterMs: Double?,
    reqFailed: Int = 0,
    reqTotal: Int = 0,
) {
    val c = AnebTheme.colors
    // 简单判定门限（观测展示口径）：下行≥20 / 上行≥10 良好；时延≤60 低时延；抖动≤20 稳定
    val downOk = peakDown >= 20f
    val upOk = peakUp >= 10f
    val rttOk = (rttMs ?: 999.0) <= 60.0
    val jitOk = (jitterMs ?: 999.0) <= 20.0
    val allOk = downOk && upOk && rttOk && jitOk
    val verdict = when {
        allOk -> "网络基本性能优良：上下行充足、时延低、连接稳定，适合实时交互类 AI 应用（对话、编码、多模态）。"
        !rttOk -> "时延偏高：首字响应(TTFT)会偏慢，弱网下连续对话流畅度受影响；带宽本身尚可。"
        !downOk && upOk -> "下行偏弱：接收模型长回答/大输出可能偏慢，交互等待增多；上行与时延尚可。"
        !upOk && downOk -> "上行偏弱：上传大文件/多模态输入可能偏慢；接收模型响应流畅，短交互体验良好。"
        else -> "网络承载偏弱：上下行与时延均需改善，AI 交互可能出现明显等待与卡顿。"
    }
    val head = if (allOk) c.excellent else if ((downOk || upOk) && rttOk) c.fair else c.poor
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
            "下行峰值 %.1f · 上行峰值 %.1f Mbps · 时延 %s ms · 抖动 %s ms".format(
                peakDown, peakUp, fmt(rttMs, "%.0f"), fmt(jitterMs, "%.0f"),
            ),
            color = c.muted,
            fontSize = 11.sp,
        )

        // ---- facet2 FAIL：应用层请求失败率（门限取 BASIC_NETWORK profile 声明，INV-3）----
        if (reqTotal > 0) {
            val rate = reqFailed.toDouble() / reqTotal
            val failSpec = TestModeProfiles.BASIC_NETWORK.metricSpecs.firstOrNull { it.id == "FAIL" }
            val failColor = when {
                rate <= (failSpec?.target?.excellent ?: 0.0) -> c.excellent
                rate <= (failSpec?.target?.good ?: 0.005) -> c.good
                rate <= (failSpec?.target?.fair ?: 0.01) -> c.fair
                else -> c.poor
            }
            Spacer(Modifier.height(4.dp))
            Text(
                "请求失败 $reqFailed/$reqTotal（${"%.1f".format(rate * 100)}%）",
                color = failColor,
                fontSize = 11.sp,
            )
        }

        // ---- facet4 ai_scenario_fitness：AI 场景适配建议（§4.2；门限取 Token profile facet2）----
        val verdicts = remember(peakDown, peakUp, rttMs, jitterMs) {
            AiScenarioAdvisor.advise(
                downMbps = peakDown.takeIf { it > 0f }?.toDouble(),
                upMbps = peakUp.takeIf { it > 0f }?.toDouble(),
                rttMs = rttMs,
                jitterMs = jitterMs,
            )
        }
        if (verdicts.isNotEmpty()) {
            Spacer(Modifier.height(10.dp))
            Text("AI 场景适配（按峰值判定 · 良级门限）", fontSize = 11.sp, fontWeight = FontWeight.SemiBold, color = c.muted)
            Spacer(Modifier.height(4.dp))
            verdicts.forEach { v ->
                val (mark, col) = when (v.suitable) {
                    true -> "✓ 适合" to c.excellent
                    false -> "✗ 不适合" to c.poor
                    null -> "— 无法判定" to c.neutral
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("${v.code} ${v.title}", fontSize = 11.sp, color = c.ink, modifier = Modifier.weight(1f))
                    Text(mark, fontSize = 11.sp, fontWeight = FontWeight.Bold, color = col)
                }
                Text(v.requirement, fontSize = 9.5.sp, color = c.faint)
            }
        }
    }
}

private fun fmt(v: Double?, pattern: String): String = v?.let { pattern.format(it) } ?: "—"
