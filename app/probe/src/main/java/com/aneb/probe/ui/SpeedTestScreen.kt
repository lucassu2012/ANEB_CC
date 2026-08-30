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
import androidx.compose.foundation.layout.width
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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.data.SyntheticResultEntity
import com.aneb.probe.engine.SpeedRunner
import com.aneb.probe.engine.SyntheticRecoveryRunner
import com.aneb.probe.ui.theme.AnebTheme
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.cos
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
    // 恢复子测（weak-recovery-v1 合成合同，D-40；独立结论恒 LOW/INCONCLUSIVE）
    recoverySample: SyntheticRecoveryRunner.Sample? = null,
    recoveryRunning: Boolean = false,
    onStartRecovery: () -> Unit = {},
    onCancelRecovery: () -> Unit = {},
    // 弱网对照（weak-capacity-latency-v1 合成整形，D-43；合成口径，不并入正常结论）
    shapedSample: SpeedRunner.Sample? = null,
    shapedRunning: Boolean = false,
    onStartShaped: () -> Unit = {},
    onCancelShaped: () -> Unit = {},
    /** 最近落库的合成子测记录（恢复/整形共表），新→旧；空=无历史（不占位） */
    recentSynthetic: List<SyntheticResultEntity> = emptyList(),
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
        peakUp = GaugeMath.peak(peakUp, sample?.upMbps?.toFloat())
        peakDown = GaugeMath.peak(peakDown, sample?.downMbps?.toFloat())
    }
    // 弱网对照（合成整形）run 的实测峰值（每次起测清空；与正常 run 峰值并排展示，绝不合并）
    var shapedPeakUp by remember { mutableStateOf(0f) }
    var shapedPeakDown by remember { mutableStateOf(0f) }
    LaunchedEffect(shapedRunning) {
        if (shapedRunning) {
            shapedPeakUp = 0f
            shapedPeakDown = 0f
        }
    }
    LaunchedEffect(shapedSample) {
        shapedPeakUp = GaugeMath.peak(shapedPeakUp, shapedSample?.upMbps?.toFloat())
        shapedPeakDown = GaugeMath.peak(shapedPeakDown, shapedSample?.downMbps?.toFloat())
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
    val isDone = phase == SpeedRunner.Phase.Done
    // 当前相主指标（下行相 downMbps / 上行相 upMbps）；完成态收尾显**下行峰值**
    // （对齐 SpeedTest 最终大数，不再显 0.0；无下行峰值退上行峰值）
    val mainVal = when {
        isDone -> peakDown.takeIf { it > 0f }?.toDouble() ?: peakUp.takeIf { it > 0f }?.toDouble()
        isDownload -> sample?.downMbps
        else -> sample?.upMbps
    }
    val phasePeak = when {
        isDone -> if (peakDown > 0f) peakDown else peakUp
        isDownload -> peakDown
        else -> peakUp
    }
    // 量程自适应：随当前相峰值上探，最小 20 Mbps，取整到 10
    val gaugeMax = GaugeMath.autoGaugeMax(phasePeak)
    val targetFrac = if (isPing) {
        // ping 阶段：RTT→0..1（0..200ms，越低越满）；无测量值保持 0（R-10：null 不驱动几何显示为"满/优"）
        GaugeMath.pingFraction(sample?.rttMs)
    } else {
        GaugeMath.gaugeFraction(mainVal, gaugeMax)
    }
    val frac by animateFloatAsState(targetFrac, tween(220), label = "speedFrac")

    val valueText = when {
        isPing -> sample?.rttMs?.let { "%.0f".format(it) } ?: "—"
        else -> mainVal?.let { "%.1f".format(it) } ?: "—" // 无测量值显 —（R-10，不显活的 0.0）
    }
    val unit = speedGaugeUnit(phase, peakDown, running)
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

        // ---- 指标磁贴（批 5b 收敛后）：抖动 / 下行峰值 / 上行峰值 / UDP 未返回 ----
        // 时延磁贴已删——与下方 facet3 实时区的 rtt（WAVEFORM）同源重复；留下的四块都不在
        // live 声明里（峰值＝会话极值非瞬时、UDP＝取证协变量、抖动无 live 条目），不是遗漏。
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            StatTile("抖动", fmt(sample?.jitterMs, "%.0f"), "ms", c.fair, Modifier.weight(1f))
            StatTile("下行峰值", if (peakDown > 0f) "%.1f".format(peakDown) else "—", "Mbps", c.excellent, Modifier.weight(1f))
            StatTile("上行峰值", if (peakUp > 0f) "%.1f".format(peakUp) else "—", "Mbps", c.brand, Modifier.weight(1f))
            // UDP 未返回率＝应用层 ANEB1 探针未回显占比，≠IP 丢包率；现场协变量，不进任何分。
            // 值来自引擎 Sample（D-02 UI 不重算）；null 显 "—"；探针相位已跑过（越过 Ping）仍
            // null → 副文案"探针不可用"（零回包/不可达≠全丢，不得宣称精确 IP 丢包率）。
            val udpRan = phase == SpeedRunner.Phase.Download || phase == SpeedRunner.Phase.Upload || isDone
            StatTile(
                "UDP 未返回",
                fmt(sample?.udpUnreturnedPct, "%.1f"),
                if (udpRan && sample?.udpUnreturnedPct == null) "探针不可用" else "%",
                c.neutral,
                Modifier.weight(1f),
            )
        }

        Spacer(Modifier.height(16.dp))

        // ---- facet3 数据驱动实时区（T77 批 5b）：basic_network profile.live（dl/ul/rtt）----
        // source→字段映射见 [speedLiveValue]，完备性由 SpeedLiveSourceMappingTest 钉住
        // （profile 加指标而映射漏＝测试红，voice 模板同款）。
        com.aneb.probe.ui.components.LiveMetricStrip(
            metrics = TestModeProfiles.ALL.first { it.id == "basic_network" }.live,
            values = { source -> speedLiveValue(sample, source) },
        )

        Spacer(Modifier.height(16.dp))

        // ---- 恢复子测卡（weak-recovery-v1 合成受控中断；独立结论，不并入测速分）----
        RecoveryCard(
            s = recoverySample,
            running = recoveryRunning,
            speedRunning = running,
            onStart = onStartRecovery,
            onCancel = onCancelRecovery,
        )

        Spacer(Modifier.height(16.dp))

        // ---- 弱网对照卡（weak-capacity-latency-v1 合成整形；合成口径，不并入正常结论）----
        ShapedCompareCard(
            s = shapedSample,
            running = shapedRunning,
            speedRunning = running,
            normalPeakDown = peakDown,
            normalPeakUp = peakUp,
            shapedPeakDown = shapedPeakDown,
            shapedPeakUp = shapedPeakUp,
            onStart = onStartShaped,
            onCancel = onCancelShaped,
        )

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
                // T52/D-485：网络基本性能模式真正的开始测量按钮（与共享底栏"测试" tab
                // 圆钮是两回事）。
                .testTag("basic_network_go_button")
                .semantics { contentDescription = if (running) "取消网络基本性能测速" else "GO 开始网络基本性能测速" }
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

        // ---- 最近合成子测（恢复/整形）：只展示落库实测值，不重算（D-02）----
        if (recentSynthetic.isNotEmpty()) {
            Spacer(Modifier.height(16.dp))
            RecentSyntheticSection(recentSynthetic)
        }
    }
}

/**
 * 最近合成子测记录：时间 + kind 标签（恢复/整形）+ 关键值 + 恒注 LOW/INCONCLUSIVE
 * （落库 [SyntheticResultEntity.confidence] 原文）。只展示落库实测值，不重算（D-02）；
 * 缺失值记 —（R-10 诚实缺席）。镜像 VoiceTestScreen 的 RecentVoiceSection。
 */
@Composable
private fun RecentSyntheticSection(records: List<SyntheticResultEntity>) {
    val c = AnebTheme.colors
    val fmt = remember { SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()) }
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(c.surface)
            .padding(14.dp),
    ) {
        Text("最近合成子测", color = c.muted, fontSize = 12.sp, fontWeight = FontWeight.Bold)
        records.forEach { r ->
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(fmt.format(Date(r.tsEpochMs)), color = c.ink, fontSize = 12.sp, modifier = Modifier.weight(1f))
                val isRecovery = r.kind == "recovery"
                Text(
                    if (isRecovery) "恢复" else "整形",
                    color = if (isRecovery) c.good else c.brand,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                )
                Spacer(Modifier.width(10.dp))
                val value = if (isRecovery) {
                    val meets = when (r.meetsTargets) {
                        true -> "✓"
                        false -> "✗"
                        null -> "—"
                    }
                    "恢复 ${r.recoveryMs?.let { "%.0f".format(it) } ?: "—"} ms · meets $meets"
                } else {
                    "↓${r.shapedDownMbps?.let { "%.2f".format(it) } ?: "—"}/" +
                        "↑${r.shapedUpMbps?.let { "%.2f".format(it) } ?: "—"} Mbps"
                }
                Text(value, color = c.ink, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            }
            Text(r.confidence, color = c.faint, fontSize = 9.5.sp)
        }
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
        val norm = GaugeMath.sparklineNormalize(values)
        if (norm.isEmpty()) return@Canvas
        val n = norm.size
        val dx = size.width / (n - 1).toFloat()
        var prev = Offset(0f, size.height - norm[0] * size.height)
        for (i in 1 until n) {
            val x = dx * i
            val y = size.height - norm[i] * size.height
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

/** 恢复子测卡（weak-recovery-v1；受控 2s 中断→恢复时长+质量段；恒 LOW/INCONCLUSIVE）。 */
@Composable
private fun RecoveryCard(
    s: SyntheticRecoveryRunner.Sample?,
    running: Boolean,
    speedRunning: Boolean,
    onStart: () -> Unit,
    onCancel: () -> Unit,
) {
    val c = AnebTheme.colors
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(c.surface)
            .padding(14.dp),
    ) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("恢复子测（合成受控中断）", color = c.muted, fontSize = 13.sp, fontWeight = FontWeight.Bold)
            if (s?.phase == SyntheticRecoveryRunner.Phase.Done) {
                val (label, col) = when (s.meetsTargets) {
                    true -> "达标" to c.excellent
                    false -> "未达标" to c.poor
                    null -> "不可判" to c.neutral
                }
                Text(label, color = col, fontSize = 13.sp, fontWeight = FontWeight.Bold)
            }
        }
        Spacer(Modifier.height(8.dp))
        when {
            s == null && !running -> Text(
                "触发服务端 2s 请求不可用窗口，测本机恢复时长与恢复后质量（weak-recovery-v1，" +
                    "独立结论，不并入测速分）。",
                color = c.faint, fontSize = 11.sp,
            )
            running && s?.phase != SyntheticRecoveryRunner.Phase.Done -> {
                val phaseLabel = when (s?.phase) {
                    SyntheticRecoveryRunner.Phase.Baseline -> "基线整形探测中（↓5/↑2Mbps +80±20ms）"
                    SyntheticRecoveryRunner.Phase.Arming -> "武装中断窗口…"
                    SyntheticRecoveryRunner.Phase.Outage -> "中断中：已确认 ${s.outageConfirmed} 次 503(outage=active)"
                    SyntheticRecoveryRunner.Phase.Quality -> "恢复后质量段 ${s.postSuccess}/${s.postTotal}"
                    else -> "准备中…"
                }
                Text(phaseLabel, color = c.good, fontSize = 12.sp)
                s?.recoveryMs?.let {
                    Text("恢复用时 %.0f ms".format(it), color = c.ink, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                }
            }
            s?.phase == SyntheticRecoveryRunner.Phase.Done -> {
                Text(
                    "恢复 ${s.recoveryMs?.let { "%.0f ms".format(it) } ?: "—"} · 中断确认 ${s.outageConfirmed} 次 · " +
                        "恢复后 ${s.postSuccess}/${s.postTotal} · RTT P95 ${s.postRttP95Ms?.let { "%.0f ms".format(it) } ?: "—"}",
                    color = c.ink, fontSize = 13.sp,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    "${s.confidence} · 合成窗口≠真实断网/弱covering，与跨网迁移恢复(D-23)口径分开",
                    color = c.faint, fontSize = 10.sp,
                )
            }
        }
        Spacer(Modifier.height(10.dp))
        val btnColor = when {
            running -> c.poor
            speedRunning -> c.surfaceMuted
            else -> c.brand
        }
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(40.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(btnColor)
                .clickable(enabled = !speedRunning) { if (running) onCancel() else onStart() },
            contentAlignment = Alignment.Center,
        ) {
            Text(
                if (running) "取消恢复子测" else "触发恢复子测",
                color = if (speedRunning) c.faint else Color(0xFF05121A),
                fontSize = 14.sp, fontWeight = FontWeight.Bold,
            )
        }
    }
}

/** 弱网对照卡（weak-capacity-latency-v1；同三阶段走服务端逐 run 隔离整形路径 ↓3/↑1Mbps +120±30ms；
 *  合成整形口径——对照仅并排展示，不并入正常测速结论/分数）。 */
@Composable
private fun ShapedCompareCard(
    s: SpeedRunner.Sample?,
    running: Boolean,
    speedRunning: Boolean,
    normalPeakDown: Float,
    normalPeakUp: Float,
    shapedPeakDown: Float,
    shapedPeakUp: Float,
    onStart: () -> Unit,
    onCancel: () -> Unit,
) {
    val c = AnebTheme.colors
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(c.surface)
            .padding(14.dp),
    ) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("弱网对照（合成 3/1Mbps +120ms）", color = c.muted, fontSize = 13.sp, fontWeight = FontWeight.Bold)
            if (s?.phase == SpeedRunner.Phase.Done) {
                Text("完成", color = c.excellent, fontSize = 13.sp, fontWeight = FontWeight.Bold)
            }
        }
        Spacer(Modifier.height(8.dp))
        when {
            s == null && !running -> Text(
                "同三阶段测速经服务端逐 run 隔离整形路径（↓3/↑1Mbps，每请求 +120±30ms 确定性抖动），" +
                    "与正常测速并排对照受控弱网体验（weak-capacity-latency-v1，合成口径，不并入正常结论）。",
                color = c.faint, fontSize = 11.sp,
            )
            running && s?.phase != SpeedRunner.Phase.Done -> {
                val phaseLabel = when (s?.phase) {
                    SpeedRunner.Phase.Ping -> "整形时延探测中（+120±30ms）"
                    SpeedRunner.Phase.Download -> "整形下行测速中（聚合 3Mbps 上限）"
                    SpeedRunner.Phase.Upload -> "整形上行测速中（聚合 1Mbps 上限）"
                    else -> "整形路径回执核验中…"
                }
                Text(phaseLabel, color = c.good, fontSize = 12.sp)
                Text(
                    "下行 ${fmt(s?.downMbps, "%.2f")} · 上行 ${fmt(s?.upMbps, "%.2f")} Mbps · RTT ${fmt(s?.rttMs, "%.0f")} ms",
                    color = c.ink, fontSize = 16.sp, fontWeight = FontWeight.Bold,
                )
            }
            s?.phase == SpeedRunner.Phase.Done -> {
                // 对照行：正常峰值（本次会话已有正常 run 时）vs 整形实测峰值
                val nd = if (normalPeakDown > 0f) "%.1f".format(normalPeakDown) else "—"
                val nu = if (normalPeakUp > 0f) "%.1f".format(normalPeakUp) else "—"
                val sd = if (shapedPeakDown > 0f) "%.2f".format(shapedPeakDown) else "—"
                val su = if (shapedPeakUp > 0f) "%.2f".format(shapedPeakUp) else "—"
                Text("正常峰值 ↓$nd / ↑$nu Mbps", color = c.ink, fontSize = 13.sp)
                Text(
                    "整形实测 ↓$sd / ↑$su Mbps · RTT ${fmt(s.rttMs, "%.0f")} ms",
                    color = c.brand, fontSize = 13.sp, fontWeight = FontWeight.Bold,
                )
                Spacer(Modifier.height(4.dp))
                Text("合成整形口径,不并入正常结论", color = c.faint, fontSize = 10.sp)
            }
        }
        Spacer(Modifier.height(10.dp))
        val btnColor = when {
            running -> c.poor
            speedRunning -> c.surfaceMuted
            else -> c.brand
        }
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(40.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(btnColor)
                .clickable(enabled = !speedRunning) { if (running) onCancel() else onStart() },
            contentAlignment = Alignment.Center,
        ) {
            Text(
                if (running) "取消弱网对照" else "开始弱网对照",
                color = if (speedRunning) c.faint else Color(0xFF05121A),
                fontSize = 14.sp, fontWeight = FontWeight.Bold,
            )
        }
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

/**
 * basic_network 面 source→字段映射（LiveMetricStrip 取值器；批 5b）。
 * 完备性由 SpeedLiveSourceMappingTest 钉住；未知 source 返回 null（组件渲染为缺测）。
 */
/**
 * 仪表单位文案（抽出 Composable 便于单测；D-610 ② 轻件）。
 *
 * **旧写法用 `else -> "Mbps 上行"` 兜底，于是 `phase == null` 的空闲态落进「上行」**——
 * 仪表读作「— Mbps 上行」，像是有一次上行测量正待出数，而实际上**什么都还没开始**。
 * 同一屏的 `phaseLabel` 当时已显式处理了 `null`（「点击开始网络基本性能测速」）⇒
 * **相邻两层一诚实一撒谎，而撒谎的那层是大字**。与 D-608 的 TTFT 回退同族：
 * R-10 说的「未测不折 0」，在文案层等价于「**未开始不冒充某一相**」。
 *
 * **刻意用 `when (phase)` 穷举而不用 `else`**：`SpeedRunner.Phase` 是封闭枚举，穷举后
 * 编译器会强制为每个相位给出文案——**将来新增一个相位不会再静默落进「上行」**。
 * 这消掉的是**缺陷类**，不只是本次这一个实例。
 */
internal fun speedGaugeUnit(
    phase: SpeedRunner.Phase?,
    peakDownMbps: Float,
    running: Boolean,
): String = when (phase) {
    null -> if (running) "准备中" else "尚未开始"
    SpeedRunner.Phase.Ping -> "ms 时延"
    SpeedRunner.Phase.Download -> "Mbps 下行"
    SpeedRunner.Phase.Upload -> "Mbps 上行"
    SpeedRunner.Phase.Done -> if (peakDownMbps > 0f) "Mbps 下行峰值" else "Mbps 上行峰值"
}

internal fun speedLiveValue(sample: SpeedRunner.Sample?, source: String): Double? {
    if (sample == null) return null
    return when (source) {
        "rttMs" -> sample.rttMs
        "jitterMs" -> sample.jitterMs
        "upMbps" -> sample.upMbps
        "downMbps" -> sample.downMbps
        "progress" -> sample.progress.toDouble()
        "udpUnreturnedPct" -> sample.udpUnreturnedPct
        "udpRttMs" -> sample.udpRttMs
        else -> null
    }
}
