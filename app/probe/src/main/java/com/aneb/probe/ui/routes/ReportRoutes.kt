package com.aneb.probe.ui.routes

import android.content.Context
import androidx.activity.ComponentActivity
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import com.aneb.probe.data.AnebDatabase
import com.aneb.probe.data.Exporter
import com.aneb.probe.ui.ReportFormat
import com.aneb.probe.ui.ReportMapper
import com.aneb.probe.ui.ReportScreen
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// ------------------------------------------------------------------
// 敏感度报告路由（analysis layer ③：多次 run → ReportMapper → ReportAnalyzer → ReportScreen）
// ------------------------------------------------------------------

@Composable
internal fun ReportRoute(
    db: AnebDatabase,
    appContext: Context,
    scope: CoroutineScope,
    activity: ComponentActivity,
    onBack: () -> Unit,
) {
    val analysis by produceState<com.aneb.probe.scoring.ReportAnalyzer.ReportAnalysis?>(
        initialValue = null,
    ) {
        value = withContext(Dispatchers.IO) {
            val runs = db.testRunDao().all()
            val withScenarios = runs.map { run ->
                run to db.scenarioResultDao().forRun(run.runId)
            }
            val summaries = ReportMapper.toRunSummaries(withScenarios)
            // 会话中断率：取有 C1 实测的 run 的中位数（真实测量，供上行重发投影；无则 null）
            val dropRates = runs.mapNotNull { it.aqsV02C1DropRate }.sorted()
            val sessionDrop = if (dropRates.isEmpty()) null else dropRates[dropRates.size / 2]
            com.aneb.probe.scoring.ReportAnalyzer.analyze(summaries, sessionDrop)
        }
    }
    var exportStatus by remember { mutableStateOf<String?>(null) }
    val a = analysis
    ReportScreen(
        analysis = a,
        exportStatus = exportStatus,
        onExportMarkdown = {
            if (a != null) {
                doExportReport(scope, appContext, "md", "text/markdown", ReportFormat.buildMarkdown(a)) { exportStatus = it }
            }
        },
        onExportJson = {
            if (a != null) {
                doExportReport(scope, appContext, "json", "application/json", ReportFormat.buildJson(a)) { exportStatus = it }
            }
        },
        onShare = {
            if (a != null) {
                val body = ReportFormat.buildMarkdown(a)
                val send = android.content.Intent(android.content.Intent.ACTION_SEND).apply {
                    type = "text/plain"
                    putExtra(android.content.Intent.EXTRA_SUBJECT, "ANEB 分层测试敏感度报告")
                    putExtra(android.content.Intent.EXTRA_TEXT, body)
                }
                android.util.Log.i("AnebProbe", "REPORT_SHARE chars=${body.length}")
                activity.startActivity(android.content.Intent.createChooser(send, "分享报告"))
            }
        },
        onBack = onBack,
    )
}

private fun doExportReport(
    scope: CoroutineScope,
    appContext: Context,
    format: String,
    mime: String,
    content: String,
    onStatus: (String) -> Unit,
) {
    scope.launch(Dispatchers.IO) {
        val ts = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val fileName = "aneb_report_$ts.$format"
        val outcome = Exporter.exportToDownloads(appContext, fileName, mime, content)
        val line =
            "REPORT_EXPORT format=$format file=$fileName bytes=${outcome.bytes} " +
                "status=${if (outcome.ok) "ok" else "fail"} " +
                "uri=${outcome.uri ?: "null"} error=${outcome.error?.replace(' ', '_') ?: "none"}"
        android.util.Log.i("AnebProbe", line)
        withContext(Dispatchers.Main) { onStatus(line) }
    }
}
