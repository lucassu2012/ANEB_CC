package com.aneb.probe.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.material3.Text
import com.aneb.probe.ui.theme.AnebTheme
import com.aneb.probe.ui.LiveMetric
import com.aneb.probe.ui.LiveRender
import kotlinx.coroutines.delay

/**
 * facet3 批 5a（T77，D-501 批 5 首半/D-69 剩余项）：`LiveMetric.render` 的第一个渲染消费方。
 *
 * profile 声明的动态指标（[LiveMetric]）在此按 `render` 四型数据驱动渲染——加指标=改 profile，
 * 不再各屏硬编码（spec 12 处 render 声明此前零读者，T48 §2 裁定①的落地）。
 *
 * ## 口径纪律（与渲染红线三断言同族，D-526/D-527/D-529）
 * - **R-10 到几何**：值为 null 时数字显 "—" 且**不画任何几何**（无折线点/无弧/无条）——
 *   半盘 0 刻度是"最差"不是"空"（D-529 原始案例），折线画到底、条画到零同理。
 * - **量程自适应**：[LiveMetric] 无量程字段，GAUGE/BAR 用会话内最大值做满量程
 *   （速率类无上界，固定满量程要么截断要么永远走不满）。
 * - 采样节奏=profile 的 `refreshMs`（0 按 300ms 兜底），窗口=`windowMs`（WAVEFORM 用）。
 *
 * @param values source → 当前值。屏方从自己的数据面构造（三面互不共享，蓝图 §1.1）；
 *   source 到字段的解析责任在屏方（配完备性守卫），本组件只认 null=缺测。
 */
@Composable
fun LiveMetricStrip(
    metrics: List<LiveMetric>,
    values: (String) -> Double?,
    modifier: Modifier = Modifier,
) {
    if (metrics.isEmpty()) return
    Row(
        modifier = modifier.fillMaxWidth().testTag("live_metric_strip"),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        for (m in metrics) {
            LiveMetricCell(m, values, Modifier.weight(1f))
        }
    }
}

@Composable
private fun LiveMetricCell(m: LiveMetric, values: (String) -> Double?, modifier: Modifier) {
    val c = AnebTheme.colors
    val refreshMs = if (m.refreshMs > 0) m.refreshMs.toLong() else 300L
    val windowMs = if (m.windowMs > 0) m.windowMs.toLong() else 2000L

    // 滑窗历史（WAVEFORM 用全部、GAUGE/BAR 用其 max 做自适应满量程）；tick 驱动重组
    val history = remember(m.id) { ArrayDeque<Pair<Long, Double>>() }
    var tick by remember(m.id) { mutableLongStateOf(0L) }
    var sessionMaxBits by remember(m.id) { mutableLongStateOf(0L) }

    LaunchedEffect(m.id) {
        while (true) {
            val now = android.os.SystemClock.elapsedRealtime()
            val v = values(m.source)
            if (v != null && v.isFinite()) {
                history.addLast(now to v)
                if (v > Double.fromBits(sessionMaxBits)) sessionMaxBits = v.toRawBits()
            }
            while (history.isNotEmpty() && now - history.first().first > windowMs) history.removeFirst()
            tick = now
            delay(refreshMs)
        }
    }

    @Suppress("UNUSED_EXPRESSION") tick // 读一次以订阅采样重组
    val latest = history.lastOrNull()?.second
    val maxScale = Double.fromBits(sessionMaxBits).takeIf { it > 0.0 }

    Column(modifier = modifier.testTag("live_metric_${m.id}"), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(m.label, color = c.muted, fontSize = 11.sp)
        when (m.render) {
            LiveRender.RUNNING_NUMBER -> Unit // 数字即主体，下方统一渲染
            LiveRender.WAVEFORM -> Waveform(history.toList(), windowMs, latest != null, c.good, Modifier.fillMaxWidth().height(28.dp))
            LiveRender.GAUGE -> ScaledArc(latest, maxScale, c.brand, Modifier.fillMaxWidth().height(28.dp))
            LiveRender.BAR -> ScaledBar(latest, maxScale, c.excellent, Modifier.fillMaxWidth().height(10.dp).padding(vertical = 2.dp))
        }
        Row(verticalAlignment = Alignment.Bottom) {
            // R-10：null 显 "—" 绝不显 0；渲染树守卫钉此处（LiveMetricStripRedlineTest）
            Text(
                latest?.let { fmtLive(it) } ?: "—",
                color = c.ink,
                fontSize = if (m.render == LiveRender.RUNNING_NUMBER) 22.sp else 14.sp,
                fontWeight = FontWeight.Bold,
            )
            if (m.unit.isNotEmpty()) Text(" ${m.unit}", color = c.muted, fontSize = 10.sp)
        }
    }
}

/** 数字格式：≥100 取整、≥10 一位小数、其余两位（速率/时延跨三个量级的通用折中）。 */
internal fun fmtLive(v: Double): String = when {
    v >= 100 -> "%.0f".format(v)
    v >= 10 -> "%.1f".format(v)
    else -> "%.2f".format(v)
}

/** 窗口折线：无点=只画基线灰轨（不画折线——缺测不是零，R-10）。 */
@Composable
private fun Waveform(points: List<Pair<Long, Double>>, windowMs: Long, hasData: Boolean, color: Color, modifier: Modifier) {
    val c = AnebTheme.colors
    Canvas(modifier) {
        drawLine(c.faint, Offset(0f, size.height - 1f), Offset(size.width, size.height - 1f), 1f)
        if (!hasData || points.size < 2) return@Canvas
        val tEnd = points.last().first
        val tStart = tEnd - windowMs
        val vMax = points.maxOf { it.second }.coerceAtLeast(1e-9)
        val path = Path()
        points.forEachIndexed { i, (t, v) ->
            val x = ((t - tStart).toFloat() / windowMs.toFloat()).coerceIn(0f, 1f) * size.width
            val y = size.height - (v / vMax).toFloat().coerceIn(0f, 1f) * (size.height - 2f)
            if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        drawPath(path, color, style = Stroke(width = 2f))
    }
}

/** 自适应满量程弧（180°）：null 只画灰轨不画进度（D-529：几何缺测≠最左端）。 */
@Composable
private fun ScaledArc(value: Double?, maxScale: Double?, color: Color, modifier: Modifier) {
    val c = AnebTheme.colors
    Canvas(modifier) {
        val stroke = Stroke(width = 5f)
        val rect = androidx.compose.ui.geometry.Rect(4f, 4f, size.width - 4f, size.height * 2f - 4f)
        drawArc(c.faint, 180f, 180f, false, rect.topLeft, rect.size, style = stroke)
        if (value == null || maxScale == null) return@Canvas
        val frac = (value / maxScale).toFloat().coerceIn(0f, 1f)
        drawArc(color, 180f, 180f * frac, false, rect.topLeft, rect.size, style = stroke)
    }
}

/** 自适应横条：null 只画灰轨。 */
@Composable
private fun ScaledBar(value: Double?, maxScale: Double?, color: Color, modifier: Modifier) {
    val c = AnebTheme.colors
    Box(modifier) {
        Canvas(Modifier.fillMaxWidth().height(10.dp)) {
            drawLine(c.faint, Offset(0f, size.height / 2), Offset(size.width, size.height / 2), size.height)
            if (value == null || maxScale == null) return@Canvas
            val frac = (value / maxScale).toFloat().coerceIn(0f, 1f)
            drawLine(color, Offset(0f, size.height / 2), Offset(size.width * frac, size.height / 2), size.height)
        }
    }
}
