package com.aneb.probe.ui.routes

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import com.aneb.probe.data.AdapterObsEntity
import com.aneb.probe.data.AnebDatabase
import com.aneb.probe.data.TestRun
import com.aneb.probe.data.VoiceResultEntity
import com.aneb.probe.ui.HistoryScreen
import com.aneb.probe.ui.HomeScreen
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

// ------------------------------------------------------------------
// Home / History / Result 路由（Room 加载）
// ------------------------------------------------------------------

@Composable
internal fun HomeRoute(
    db: AnebDatabase,
    running: Boolean,
    telemetry: com.aneb.probe.engine.LiveTelemetry,
    logs: List<String>,
    onStart: () -> Unit,
    onCancel: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenResult: (String) -> Unit,
) {
    // 最近一次 run（run 结束 running→false 时刷新，带出上次结果 chip）
    val lastRun by produceState<TestRun?>(initialValue = null, running) {
        value = withContext(Dispatchers.IO) {
            db.testRunDao().all().maxByOrNull { it.startedAtEpochMs }
        }
    }
    HomeScreen(
        lastRun = lastRun,
        running = running,
        telemetry = telemetry,
        logs = logs,
        onStart = onStart,
        onCancel = onCancel,
        onOpenSettings = onOpenSettings,
        onOpenLastResult = onOpenResult,
    )
}

@Composable
internal fun HistoryRoute(
    db: AnebDatabase,
    onOpen: (String) -> Unit,
    onGenerateReport: () -> Unit,
    onBack: () -> Unit,
) {
    val runs by produceState(initialValue = emptyList<TestRun>()) {
        value = withContext(Dispatchers.IO) { db.testRunDao().all() }
    }
    // 历史统一展示：语音记录混入历史列表（每次进入历史页 produceState 重启即刷新）
    val voiceResults by produceState(initialValue = emptyList<VoiceResultEntity>()) {
        value = withContext(Dispatchers.IO) { db.voiceResultDao().recent(100) }
    }
    // 观察记录（Profile 3 无障碍观察快照）混入历史列表——只落规格匹配会话，恒 LOW/INCONCLUSIVE
    val adapterObs by produceState(initialValue = emptyList<AdapterObsEntity>()) {
        value = withContext(Dispatchers.IO) { db.adapterObsDao().recent(100) }
    }
    HistoryScreen(
        runs = runs,
        onOpen = onOpen,
        onGenerateReport = onGenerateReport,
        onBack = onBack,
        voiceResults = voiceResults,
        adapterObs = adapterObs,
    )
}
