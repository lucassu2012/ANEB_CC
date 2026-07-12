package com.aneb.probe.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.data.TestRun
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 历史页（P1-C07）：TestRun 列表（时间/模式/AQS/状态/上报状态），点击进结果页。
 */
@Composable
fun HistoryScreen(
    runs: List<TestRun>,
    onOpen: (String) -> Unit,
    onBack: () -> Unit,
) {
    val fmt = SimpleDateFormat("MM-dd HH:mm:ss", Locale.US)
    Column(modifier = Modifier.fillMaxSize().padding(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedButton(onClick = onBack) { Text("← 返回") }
            Spacer(Modifier.width(8.dp))
            Text("测试历史 (${runs.size})", fontSize = 18.sp, fontWeight = FontWeight.Bold)
        }
        if (runs.isEmpty()) {
            Text("暂无历史记录", color = COLOR_INVALID, modifier = Modifier.padding(top = 16.dp))
        }
        LazyColumn(modifier = Modifier.weight(1f).fillMaxWidth()) {
            items(count = runs.size, key = { i -> runs[i].runId }) { i ->
                val run = runs[i]
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onOpen(run.runId) }
                        .padding(vertical = 8.dp),
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        val score = run.aqsScore
                        Text(
                            score?.let { "%.1f".format(it) } ?: "—",
                            fontSize = 22.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (score != null) gradeColor(ResultFormat.aqsGrade(score)) else COLOR_INVALID,
                        )
                        if (run.aqsLowConfidence == true) {
                            Spacer(Modifier.width(6.dp))
                            Text("低置信", fontSize = 11.sp, color = COLOR_LOWCONF)
                        }
                        Spacer(Modifier.width(12.dp))
                        Text(
                            "${fmt.format(Date(run.startedAtEpochMs))}  ${run.mode}/${run.transport}",
                            fontSize = 13.sp,
                        )
                    }
                    Text(
                        "status=${run.status ?: "?"} report=${run.reportStatus ?: "—"} run=${run.runId.take(13)}…",
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace,
                        color = COLOR_INVALID,
                    )
                }
                HorizontalDivider()
            }
        }
    }
}
