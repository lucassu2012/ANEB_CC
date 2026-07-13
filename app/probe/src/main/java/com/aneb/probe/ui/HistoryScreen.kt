package com.aneb.probe.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.data.TestRun
import com.aneb.probe.ui.theme.AnebTheme
import com.aneb.probe.ui.theme.AnebType
import com.aneb.probe.ui.theme.Grade
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.roundToInt

/**
 * 历史页（重设计，设计稿 §历史）：Room TestRun 列表——每行 grade 色分数徽标 +
 * 时间/模式/传输 + 状态；点击进对应结果页。数据全部来自 Room（本层不重算）。
 */
@Composable
fun HistoryScreen(
    runs: List<TestRun>,
    onOpen: (String) -> Unit,
    onBack: () -> Unit,
) {
    val colors = AnebTheme.colors
    val fmt = SimpleDateFormat("MM-dd HH:mm", Locale.US)
    Column(modifier = Modifier.fillMaxSize().background(colors.background).padding(horizontal = 20.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            BackButton(onBack)
            Spacer(Modifier.width(10.dp))
            Text("测试历史 (${runs.size})", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = colors.ink)
        }
        if (runs.isEmpty()) {
            Text("暂无历史记录", color = colors.muted, modifier = Modifier.padding(top = 24.dp))
        }
        LazyColumn(modifier = Modifier.weight(1f).fillMaxWidth()) {
            items(count = runs.size, key = { i -> runs[i].runId }) { i ->
                HistoryRow(runs[i], fmt, onOpen)
            }
        }
    }
}

@Composable
private fun HistoryRow(run: TestRun, fmt: SimpleDateFormat, onOpen: (String) -> Unit) {
    val colors = AnebTheme.colors
    val score = run.aqsScore
    val grade = score?.let { Grade.fromAqsScore(it) }
    val gradeColor = colors.gradeColor(grade)
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 5.dp)
            .clip(RoundedCornerShape(13.dp))
            .background(colors.surfaceElevated)
            .border(1.dp, colors.hairline, RoundedCornerShape(13.dp))
            .clickable { onOpen(run.runId) }
            .padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier.size(42.dp).clip(RoundedCornerShape(10.dp)).background(gradeColor),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                score?.roundToInt()?.toString() ?: "—",
                style = AnebType.StatValue,
                fontSize = 16.sp,
                color = Color(0xFF05121A),
            )
        }
        Spacer(Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    grade?.labelFriendly ?: "未完成",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = if (grade != null) gradeColor else colors.muted,
                )
                if (run.aqsLowConfidence == true) {
                    Spacer(Modifier.width(6.dp))
                    Text("低置信", fontSize = 10.sp, color = COLOR_LOWCONF)
                }
            }
            Text(
                "${fmt.format(Date(run.startedAtEpochMs))} · ${run.mode} · ${run.transport}",
                fontSize = 11.sp,
                color = colors.muted,
            )
            Text(
                "status=${run.status ?: "?"} report=${run.reportStatus ?: "—"}",
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                color = colors.faint,
            )
        }
        Text("›", fontSize = 18.sp, color = colors.faint)
    }
}
