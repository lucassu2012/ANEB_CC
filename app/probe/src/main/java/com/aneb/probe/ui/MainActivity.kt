package com.aneb.probe.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.aneb.probe.BuildConfig
import com.aneb.probe.data.AnebDatabase
import com.aneb.probe.data.Exporter
import com.aneb.probe.data.ScenarioResultEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.engine.TestEngine
import com.aneb.probe.radio.RadioCollector
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 阶段 1 UI（P1-C07）：单 Activity 状态切换导航——
 * Home（运行/日志，行为与 C05 一致）/ Result（AQS+KPI+claim scope）/ History（TestRun 列表）。
 *
 * adb 自动化（联调可观测性，不改测量语义）：
 *   am start ... --es server <url> --ez autorun true [--es mode quick|forensic]
 *   [--es transport auto|wifi|cellular] [--es inject truncate:50]
 * autorun 默认快测；inject 仅 BuildConfig.DEBUG 生效（C09 前置）。
 * C07：手动 run 结束自动跳结果页；autorun 不跳（保持 logcat 自动化验收流程不变）。
 */
class MainActivity : ComponentActivity() {

    private lateinit var engine: TestEngine
    private lateinit var radioCollector: RadioCollector
    private lateinit var db: AnebDatabase

    private var intentServer: String? = null
    private var intentAutorun: Boolean = false
    private var intentMode: TestEngine.Mode = TestEngine.Mode.QUICK
    private var intentTransport: TestEngine.TransportMode = TestEngine.TransportMode.AUTO
    private var intentInject: String? = null

    private val radioPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { _ ->
            pendingRadioLog?.invoke(radioCollector.snapshot())
            pendingRadioLog = null
        }

    private var pendingRadioLog: ((String) -> Unit)? = null

    /** 单 Activity 内导航状态 */
    private sealed interface Screen {
        data object Home : Screen
        data object History : Screen
        data class Result(val runId: String, val fromHistory: Boolean) : Screen
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        engine = TestEngine(applicationContext)
        radioCollector = RadioCollector(this)
        db = AnebDatabase.get(applicationContext)
        intentServer = intent?.getStringExtra("server")
        intentAutorun = intent?.getBooleanExtra("autorun", false) == true
        intentMode = when (intent?.getStringExtra("mode")?.lowercase()) {
            "forensic" -> TestEngine.Mode.FORENSIC
            else -> TestEngine.Mode.QUICK // autorun intent 默认快测
        }
        intentTransport = when (intent?.getStringExtra("transport")?.lowercase()) {
            "wifi" -> TestEngine.TransportMode.WIFI
            "cellular" -> TestEngine.TransportMode.CELLULAR
            else -> TestEngine.TransportMode.AUTO // 模拟器用 AUTO（不绑定仅监控）
        }
        // C09 前置：注入透传仅 debug 构建生效，release 恒 null
        intentInject = if (BuildConfig.DEBUG) intent?.getStringExtra("inject") else null
        setContent {
            MaterialTheme {
                // C07：内容避让系统栏（否则顶部按钮压在状态栏下，点击被系统吃掉）
                Surface(modifier = Modifier.fillMaxSize().safeDrawingPadding()) {
                    var screen by remember { mutableStateOf<Screen>(Screen.Home) }
                    // C07 评审修复：Home 屏状态提升到 when(screen) 之上——原先 remember 在
                    // Home 分支内部，手动 run 结束自动跳 Result 后返回会 dispose 重建，
                    // 静默重置已输入的服务器地址/模式/日志。intent 默认值只在状态初始化时
                    // 生效一次（autorun 路径不变）。rememberSaveable 额外撑过配置变更。
                    var serverUrl by rememberSaveable { mutableStateOf(intentServer ?: "http://10.0.2.2:8443") }
                    var mode by rememberSaveable { mutableStateOf(intentMode) }
                    var transport by rememberSaveable { mutableStateOf(intentTransport) }
                    // running/logs 生命周期绑当前 Activity 实例（run 协程随 lifecycleScope
                    // 消亡、大列表不进 Bundle）：普通 remember，往返导航存活即可
                    var running by remember { mutableStateOf(false) }
                    val logs = remember { mutableStateListOf<String>() }
                    when (val s = screen) {
                        is Screen.Home -> ProbeScreen(
                            serverUrl = serverUrl,
                            onServerUrlChange = { serverUrl = it },
                            mode = mode,
                            onModeChange = { mode = it },
                            transport = transport,
                            onTransportChange = { transport = it },
                            running = running,
                            onRunningChange = { running = it },
                            logs = logs,
                            onOpenHistory = { screen = Screen.History },
                            onRunFinished = { runId ->
                                screen = Screen.Result(runId, fromHistory = false)
                            },
                        )
                        is Screen.History -> HistoryRoute(
                            onOpen = { runId -> screen = Screen.Result(runId, fromHistory = true) },
                            onBack = { screen = Screen.Home },
                        )
                        is Screen.Result -> ResultRoute(
                            runId = s.runId,
                            onBack = {
                                screen = if (s.fromHistory) Screen.History else Screen.Home
                            },
                        )
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // History / Result 路由（Room 加载）
    // ------------------------------------------------------------------

    @Composable
    private fun HistoryRoute(onOpen: (String) -> Unit, onBack: () -> Unit) {
        val runs by produceState(initialValue = emptyList<TestRun>()) {
            value = withContext(Dispatchers.IO) { db.testRunDao().all() }
        }
        HistoryScreen(runs = runs, onOpen = onOpen, onBack = onBack)
    }

    private data class ResultData(
        val run: TestRun?,
        val scenarios: List<ScenarioResultEntity>,
        val reportJson: String?,
        val loaded: Boolean,
    )

    @Composable
    private fun ResultRoute(runId: String, onBack: () -> Unit) {
        val data by produceState(initialValue = ResultData(null, emptyList(), null, loaded = false), runId) {
            value = withContext(Dispatchers.IO) {
                ResultData(
                    run = db.testRunDao().byId(runId),
                    scenarios = db.scenarioResultDao().forRun(runId),
                    reportJson = db.reportBodyDao().forRun(runId)?.body,
                    loaded = true,
                )
            }
        }
        var exportStatus by remember(runId) { mutableStateOf<String?>(null) }

        if (!data.loaded) {
            Text("加载中…", modifier = Modifier.padding(16.dp))
            return
        }
        ResultScreen(
            run = data.run,
            scenarios = data.scenarios,
            hasReportJson = data.reportJson != null,
            exportStatus = exportStatus,
            onExportJson = {
                val body = data.reportJson ?: return@ResultScreen
                doExport(runId, "json", "application/json", body) { exportStatus = it }
            },
            onExportCsv = {
                val run = data.run ?: return@ResultScreen
                doExport(runId, "csv", "text/csv", ResultFormat.buildCsv(run, data.scenarios)) {
                    exportStatus = it
                }
            },
            onBack = onBack,
        )
    }

    /**
     * 导出到 Downloads（MediaStore，无需存储权限）+ EXPORT 日志（key=value 合同；
     * 新增 KEY，不动既有 KEY 集）。
     */
    private fun doExport(
        runId: String,
        format: String,
        mime: String,
        content: String,
        onStatus: (String) -> Unit,
    ) {
        lifecycleScope.launch(Dispatchers.IO) {
            val ts = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            val fileName = "aneb_${runId.take(8)}_$ts.$format"
            val outcome = Exporter.exportToDownloads(applicationContext, fileName, mime, content)
            val line =
                "EXPORT run_id=$runId format=$format file=$fileName bytes=${outcome.bytes} " +
                    "status=${if (outcome.ok) "ok" else "fail"} " +
                    "uri=${outcome.uri ?: "null"} error=${outcome.error?.replace(' ', '_') ?: "none"}"
            android.util.Log.i("AnebProbe", line)
            withContext(Dispatchers.Main) { onStatus(line) }
        }
    }

    // ------------------------------------------------------------------
    // Home（C05 行为不变 + History 入口 + run 结束自动跳结果页）
    // ------------------------------------------------------------------

    /** Home 屏：状态全部提升到调用方（setContent 作用域），本层只读参数+回调（C07 评审修复） */
    @Composable
    private fun ProbeScreen(
        serverUrl: String,
        onServerUrlChange: (String) -> Unit,
        mode: TestEngine.Mode,
        onModeChange: (TestEngine.Mode) -> Unit,
        transport: TestEngine.TransportMode,
        onTransportChange: (TestEngine.TransportMode) -> Unit,
        running: Boolean,
        onRunningChange: (Boolean) -> Unit,
        logs: SnapshotStateList<String>,
        onOpenHistory: () -> Unit,
        onRunFinished: (String) -> Unit,
    ) {
        val listState = rememberLazyListState()

        // 联调可观测性：UI 日志同时镜像到 logcat（tag=AnebProbe），模拟器自动化从 logcat 提取
        fun addLog(line: String) {
            android.util.Log.i("AnebProbe", line)
            logs.add(line)
        }

        // fromAutorun：autorun 模式 run 结束不跳结果页（保持既有 logcat 自动化验收流程）
        fun startRun(fromAutorun: Boolean) {
            if (running) return
            onRunningChange(true)
            addLog(">>> RUN mode=${mode.name.lowercase()} transport=${transport.name.lowercase()} -> $serverUrl")
            lifecycleScope.launch {
                var runId: String? = null
                var navigated = false
                fun jumpToResult() {
                    val id = runId
                    if (!fromAutorun && !navigated && id != null) {
                        navigated = true
                        onRunFinished(id)
                    }
                }
                try {
                    engine.run(
                        TestEngine.RunConfig(
                            serverBase = serverUrl,
                            mode = mode,
                            transport = transport,
                            inject = intentInject,
                        )
                    ).collect { line ->
                        addLog(line)
                        // 从 RUN_START 行提取 run_id（日志合同字段，C07 导航用）
                        if (runId == null && line.startsWith("RUN_START ")) {
                            runId = Regex("run_id=(\\S+)").find(line)?.groupValues?.get(1)
                        }
                        // run 结束自动跳结果页（autorun 不跳）：RUN_END 时 TestRun/
                        // report_body 均已落库（日志合同顺序），可安全导航
                        if (line.startsWith("RUN_END ")) jumpToResult()
                    }
                    jumpToResult() // 兜底：flow 正常完成但未见 RUN_END 行
                } catch (e: CancellationException) {
                    throw e // 不吞取消（fail-closed §4.6/§4.7）
                } catch (e: Exception) {
                    addLog("RUN_FAILED error=$e")
                } finally {
                    onRunningChange(false)
                }
            }
        }

        LaunchedEffect(logs.size) {
            if (logs.isNotEmpty()) listState.animateScrollToItem(logs.size - 1)
        }

        LaunchedEffect(Unit) {
            if (intentAutorun) {
                intentAutorun = false
                startRun(fromAutorun = true)
            }
        }

        Column(modifier = Modifier.fillMaxSize().padding(12.dp)) {
            OutlinedTextField(
                value = serverUrl,
                onValueChange = onServerUrlChange,
                label = { Text("Server base URL") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            // C07：按钮加宽后窄屏溢出，行内横向滚动（朴素方案，不动按钮语义）
            Row(
                modifier = Modifier
                    .padding(vertical = 8.dp)
                    .horizontalScroll(rememberScrollState()),
            ) {
                Button(enabled = !running, onClick = { startRun(fromAutorun = false) }) {
                    Text(if (running) "Running..." else "Run")
                }
                Spacer(modifier = Modifier.width(8.dp))
                OutlinedButton(
                    enabled = !running,
                    onClick = {
                        onModeChange(
                            if (mode == TestEngine.Mode.QUICK) {
                                TestEngine.Mode.FORENSIC
                            } else {
                                TestEngine.Mode.QUICK
                            }
                        )
                    },
                ) {
                    Text(if (mode == TestEngine.Mode.QUICK) "Mode: Quick" else "Mode: Forensic")
                }
                Spacer(modifier = Modifier.width(8.dp))
                OutlinedButton(
                    enabled = !running,
                    onClick = {
                        onTransportChange(
                            when (transport) {
                                TestEngine.TransportMode.AUTO -> TestEngine.TransportMode.WIFI
                                TestEngine.TransportMode.WIFI -> TestEngine.TransportMode.CELLULAR
                                TestEngine.TransportMode.CELLULAR -> TestEngine.TransportMode.AUTO
                            }
                        )
                    },
                ) {
                    Text("Net: ${transport.name}")
                }
                Spacer(modifier = Modifier.width(8.dp))
                OutlinedButton(onClick = { onRadioSnapshot { line -> addLog(line) } }) {
                    Text("Radio")
                }
                Spacer(modifier = Modifier.width(8.dp))
                OutlinedButton(onClick = onOpenHistory) {
                    Text("History")
                }
            }
            if (intentInject != null) {
                Text(
                    "INJECT ACTIVE: $intentInject (debug only, run is NOT evidential)",
                    color = MaterialTheme.colorScheme.error,
                    fontSize = 12.sp,
                )
            }
            HorizontalDivider()
            LazyColumn(
                state = listState,
                modifier = Modifier.weight(1f).fillMaxWidth(),
            ) {
                // key=索引：日志 append-only（只增不删不重排），索引稳定
                items(count = logs.size, key = { index -> index }) { index ->
                    Text(text = logs[index], fontFamily = FontFamily.Monospace, fontSize = 11.sp)
                }
            }
        }
    }

    private fun onRadioSnapshot(log: (String) -> Unit) {
        val needed = arrayOf(
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.ACCESS_FINE_LOCATION,
        )
        val missing = needed.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isEmpty()) {
            log(radioCollector.snapshot())
        } else {
            log("radio: requesting permissions ${missing.joinToString(",")} ...")
            pendingRadioLog = log
            radioPermissionLauncher.launch(missing.toTypedArray())
        }
    }
}
