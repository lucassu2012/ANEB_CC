package com.aneb.probe.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.ui.components.GaugeMode
import com.aneb.probe.ui.components.PulseGauge
import com.aneb.probe.ui.theme.AnebTheme
import com.aneb.probe.ui.theme.Grade

/**
 * 测试中屏（设计稿 §01 测试中）：脉冲环 Running（progress 由 run 进度驱动）+ 阶段标签
 * "2/3·编码 Agent 流" + 实时 token 流条（stall 红点）+ 4 个 livemini。
 *
 * 进度由 [TestProgressParser] 从 TestEngine 既有日志 KEY 行（SCENARIO_START/SCENARIO_KPI/
 * ORDER/AQS/RUN_END）派生——**不改 TestEngine 输出格式**（UI 层只读既有合同字段）。
 * RSRP/制式取不到时显 "…"（[radioLabel] 由 MainActivity 注入 RadioCollector 快照）。
 *
 * @param logs run 日志（append-only，MainActivity 提供）
 * @param radioRsrp 无线信号 RSRP 文本（如 "−93"）；取不到 null
 * @param radioRat 制式文本（如 "5G SA"）；取不到 null
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun TestingScreen(
    logs: List<String>,
    radioRsrp: String?,
    radioRat: String?,
) {
    val colors = AnebTheme.colors
    // logs 为 append-only SnapshotStateList，每新增一行都会重组；按行数记忆化避免逐帧全量重扫（O(n²)）
    val progress = remember(logs.size) { TestProgressParser.parse(logs) }
    val animated by animateFloatAsState(
        targetValue = progress.fraction,
        animationSpec = tween(500),
        label = "testing-progress",
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(colors.background)
            .padding(horizontal = 20.dp),
    ) {
        Column(modifier = Modifier.padding(top = 12.dp, bottom = 4.dp)) {
            Text("测试中", fontSize = 17.sp, fontWeight = FontWeight.Black, color = colors.ink)
            Text(
                "${progress.scenarioIndex + 1} / ${progress.totalScenarios} · ${progress.phaseName}",
                fontSize = 10.5.sp,
                color = colors.muted,
            )
        }

        Spacer(Modifier.height(16.dp))
        Box(modifier = Modifier.align(Alignment.CenterHorizontally)) {
            PulseGauge(
                mode = GaugeMode.Running,
                grade = Grade.Good,
                score = null,
                progress = animated,
                stallPositions = progress.stallTickPositions,
            )
        }

        // 阶段实时提示（闪烁 live 点）
        Row(
            modifier = Modifier.align(Alignment.CenterHorizontally).padding(top = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(modifier = Modifier.size(6.dp).clip(CircleShape).background(colors.good))
            Spacer(Modifier.width(8.dp))
            Text(progress.liveHint, fontSize = 12.5.sp, color = colors.muted)
        }

        Spacer(Modifier.height(14.dp))
        TokenStreamStrip(fill = animated, stalls = progress.stallCount)

        Spacer(Modifier.height(16.dp))
        FlowRow(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            maxItemsInEachRow = 2,
        ) {
            LiveMini("首字延迟", progress.ttftMs?.let { "${it.toInt()}ms" } ?: "…", Modifier.weight(1f))
            LiveMini("卡顿", "${progress.stallCount} 次", Modifier.weight(1f))
            LiveMini("信号 RSRP", radioRsrp ?: "…", Modifier.weight(1f))
            LiveMini("制式", radioRat ?: "…", Modifier.weight(1f))
        }
        Spacer(Modifier.weight(1f))
    }
}

@Composable
private fun TokenStreamStrip(fill: Float, stalls: Int) {
    val colors = AnebTheme.colors
    val total = 40
    val lit = (fill * total).toInt().coerceIn(0, total)
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(3.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        for (i in 0 until total) {
            // 卡顿红点：把观测到的 stall 数均匀落在已点亮段内
            val isStall = stalls > 0 && lit > 0 && (i < lit) &&
                ((i + 1) % (lit / stalls.coerceAtLeast(1)).coerceAtLeast(1) == 0) &&
                (i / ((lit / stalls.coerceAtLeast(1)).coerceAtLeast(1)) < stalls)
            val color = when {
                isStall -> colors.poor
                i < lit -> colors.good
                else -> colors.faint
            }
            val dot = if (isStall) 6.dp else 5.dp
            Box(modifier = Modifier.size(dot).clip(CircleShape).background(color))
        }
    }
}

@Composable
private fun LiveMini(key: String, value: String, modifier: Modifier = Modifier) {
    val colors = AnebTheme.colors
    Row(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(colors.surfaceElevated)
            .border(1.dp, colors.hairline, RoundedCornerShape(12.dp))
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.Bottom,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(key, fontSize = 11.sp, color = colors.muted)
        Spacer(Modifier.width(6.dp))
        Text(value, fontSize = 14.sp, fontWeight = FontWeight.Bold, color = colors.ink)
    }
}

/**
 * run 进度派生（纯逻辑，可单测）。从 TestEngine 既有日志 KEY 行折叠出结构化进度——
 * 不改 TestEngine 输出格式（UI 层解析既有合同字段）。
 */
object TestProgressParser {

    data class LiveProgress(
        val runId: String?,
        val scenarioIndex: Int,
        val totalScenarios: Int,
        val phaseName: String,
        val fraction: Float,
        val ttftMs: Double?,
        val stallCount: Int,
        val finished: Boolean,
        val finishedRunId: String?,
    ) {
        val liveHint: String get() = "正在测：${phaseName}的 token 流是否顺滑"

        /** stall 落在环刻度（60 格）上的下标近似（卡顿缺口位置）。 */
        val stallTickPositions: List<Int>
            get() = if (stallCount <= 0) emptyList() else (1..stallCount).map {
                ((it.toFloat() / (stallCount + 1)) * 60f * fraction).toInt().coerceIn(0, 59)
            }
    }

    private val PROFILE_NAMES = mapOf(
        "s1_chat" to "闲聊对话",
        "s2_coding_agent" to "编码 Agent 流",
        "s3_multimodal" to "多模态上传",
    )

    fun parse(logs: List<String>): LiveProgress {
        var runId: String? = null
        var total = 3 // 快测缺省 3 场景
        var scenarioIndex = 0
        var currentProfile: String? = null
        var completedKpis = 0
        var latestTtft: Double? = null
        var stalls = 0
        var finished = false
        var finishedRunId: String? = null

        for (line in logs) {
            when {
                line.startsWith("RUN_START ") ->
                    runId = field(line, "run_id")
                line.startsWith("ORDER ") -> {
                    // order=s1,s2,s3 → 场景总数（首个 ORDER 即可）
                    field(line, "order")?.let { total = it.split(',').size.coerceAtLeast(1) }
                }
                line.startsWith("SCENARIO_START ") -> {
                    scenarioIndex = field(line, "order_index")?.toIntOrNull() ?: scenarioIndex
                    currentProfile = field(line, "scenario")?.substringBefore('#')
                }
                line.startsWith("SCENARIO_KPI ") -> {
                    completedKpis++
                    field(line, "t1_ms")?.toDoubleOrNull()?.let { latestTtft = it }
                    val t3 = field(line, "t3")?.toDoubleOrNull()
                    if (t3 != null && t3 > 0.0) stalls++
                }
                line.startsWith("RUN_END ") -> {
                    finished = true
                    finishedRunId = field(line, "run_id") ?: runId
                }
            }
        }

        val fraction = ((completedKpis.toFloat() + if (finished) 0f else 0.5f) / total)
            .coerceIn(0f, 1f)
        val phaseName = PROFILE_NAMES[currentProfile] ?: "网络场景"
        return LiveProgress(
            runId = runId,
            scenarioIndex = scenarioIndex.coerceIn(0, (total - 1).coerceAtLeast(0)),
            totalScenarios = total,
            phaseName = phaseName,
            fraction = fraction,
            ttftMs = latestTtft,
            stallCount = stalls,
            finished = finished,
            finishedRunId = finishedRunId,
        )
    }

    /** 从 "key=value" 合同行提取字段（空白分隔；值到下一个空白止）。 */
    private fun field(line: String, key: String): String? =
        Regex("(?:^|\\s)${Regex.escape(key)}=(\\S+)").find(line)?.groupValues?.get(1)
}
