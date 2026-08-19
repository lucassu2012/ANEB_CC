package com.aneb.probe.ui.routes

import android.content.Context
import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.aneb.probe.data.AnebDatabase
import com.aneb.probe.data.Exporter
import com.aneb.probe.data.ScenarioResultEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.radio.GeoTrack
import com.aneb.probe.ui.ResultFormat
import com.aneb.probe.ui.ResultLatencySeries
import com.aneb.probe.ui.ResultRadioSummary
import com.aneb.probe.ui.ResultScreen
import com.aneb.probe.ui.ShareCard
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private data class ResultData(
    val run: TestRun?,
    val scenarios: List<ScenarioResultEntity>,
    val reportJson: String?,
    val trackPoints: List<GeoTrack.Point>,
    val radioSummary: ResultRadioSummary,
    val latency: ResultLatencySeries,
    val loaded: Boolean,
)

@Composable
internal fun ResultRoute(
    db: AnebDatabase,
    appContext: Context,
    scope: CoroutineScope,
    activity: ComponentActivity,
    runId: String,
    onBack: () -> Unit,
) {
    val data by produceState(
        initialValue = ResultData(
            null, emptyList(), null, emptyList(),
            ResultRadioSummary.EMPTY, ResultLatencySeries.EMPTY, loaded = false,
        ),
        runId,
    ) {
        value = withContext(Dispatchers.IO) {
            // 无线样本一次读取，复用于轨迹点（GPS 路测）与无线层聚合（制式/信号）
            val radioSamples = db.radioSampleDao().forRun(runId)
            ResultData(
                run = db.testRunDao().byId(runId),
                scenarios = db.scenarioResultDao().forRun(runId),
                reportJson = db.reportBodyDao().forRun(runId)?.body,
                trackPoints = radioSamples
                    .filter { it.lat != null && it.lon != null }
                    .map { GeoTrack.Point(it.tsNanos, it.lat, it.lon, it.accuracyM) },
                radioSummary = ResultRadioSummary.of(radioSamples),
                latency = ResultLatencySeries.of(db.tokenEventDao().forRun(runId)),
                loaded = true,
            )
        }
    }
    var exportStatus by remember(runId) { mutableStateOf<String?>(null) }

    if (!data.loaded) {
        Text("加载中…", modifier = Modifier.padding(16.dp))
        return
    }
    val trackSummaries: Map<Long, GeoTrack.Summary> =
        if (data.trackPoints.isEmpty()) {
            emptyMap()
        } else {
            data.scenarios.associate { s ->
                s.id to GeoTrack.summarize(data.trackPoints, s.startedAtNanos, s.endedAtNanos)
            }
        }
    ResultScreen(
        run = data.run,
        scenarios = data.scenarios,
        reportJson = data.reportJson,
        radio = data.radioSummary,
        latency = data.latency,
        exportStatus = exportStatus,
        onExportJson = {
            val body = data.reportJson ?: return@ResultScreen
            doExport(scope, appContext, runId, "json", "application/json", body) { exportStatus = it }
        },
        onExportCsv = {
            val run = data.run ?: return@ResultScreen
            doExport(scope, appContext, runId, "csv", "text/csv", ResultFormat.buildCsv(run, data.scenarios)) {
                exportStatus = it
            }
        },
        onBack = onBack,
        trackSummaries = trackSummaries,
        hasTrack = data.trackPoints.isNotEmpty(),
        onExportTrack = {
            doExport(scope, appContext, runId, "track.csv", "text/csv", GeoTrack.buildTrackCsv(data.trackPoints)) {
                exportStatus = it
            }
        },
        onShare = { model ->
            // 分享成图：离屏 Canvas 渲染 + MediaStore 写盘属重 IO，必须离开主线程（与 doExport 同款）；
            // 仅 startActivity 回主线程。KEY=SHARE。
            scope.launch(Dispatchers.IO) {
                val uri = ShareCard.renderAndSave(appContext, model)
                withContext(Dispatchers.Main) { ShareCard.launchShare(activity, uri) }
            }
        },
    )
}

private fun doExport(
    scope: CoroutineScope,
    appContext: Context,
    runId: String,
    format: String,
    mime: String,
    content: String,
    onStatus: (String) -> Unit,
) {
    scope.launch(Dispatchers.IO) {
        val ts = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val fileName = "aneb_${runId.take(8)}_$ts.$format"
        val outcome = Exporter.exportToDownloads(appContext, fileName, mime, content)
        val line =
            "EXPORT run_id=$runId format=$format file=$fileName bytes=${outcome.bytes} " +
                "status=${if (outcome.ok) "ok" else "fail"} " +
                "uri=${outcome.uri ?: "null"} error=${outcome.error?.replace(' ', '_') ?: "none"}"
        android.util.Log.i("AnebProbe", line)
        withContext(Dispatchers.Main) { onStatus(line) }
    }
}
