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
import androidx.compose.foundation.layout.width
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
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.aneb.probe.BuildConfig
import com.aneb.probe.engine.TestEngine
import com.aneb.probe.radio.RadioCollector
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

/**
 * 阶段 1 简朴 UI（完整结果页是 C07 另做）：服务器地址 + 模式开关（快测/取证）+
 * transport 开关（AUTO/WIFI/CELLULAR）+ Run + 可滚动日志区。
 *
 * adb 自动化（联调可观测性，不改测量语义）：
 *   am start ... --es server <url> --ez autorun true [--es mode quick|forensic]
 *   [--es transport auto|wifi|cellular] [--es inject truncate:50]
 * autorun 默认快测；inject 仅 BuildConfig.DEBUG 生效（C09 前置）。
 */
class MainActivity : ComponentActivity() {

    private lateinit var engine: TestEngine
    private lateinit var radioCollector: RadioCollector

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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        engine = TestEngine(applicationContext)
        radioCollector = RadioCollector(this)
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
                Surface(modifier = Modifier.fillMaxSize()) {
                    ProbeScreen()
                }
            }
        }
    }

    @Composable
    private fun ProbeScreen() {
        var serverUrl by remember { mutableStateOf(intentServer ?: "http://10.0.2.2:8443") }
        var mode by remember { mutableStateOf(intentMode) }
        var transport by remember { mutableStateOf(intentTransport) }
        var running by remember { mutableStateOf(false) }
        val logs = remember { mutableStateListOf<String>() }
        val listState = rememberLazyListState()

        // 联调可观测性：UI 日志同时镜像到 logcat（tag=AnebProbe），模拟器自动化从 logcat 提取
        fun addLog(line: String) {
            android.util.Log.i("AnebProbe", line)
            logs.add(line)
        }

        fun startRun() {
            if (running) return
            running = true
            addLog(">>> RUN mode=${mode.name.lowercase()} transport=${transport.name.lowercase()} -> $serverUrl")
            lifecycleScope.launch {
                try {
                    engine.run(
                        TestEngine.RunConfig(
                            serverBase = serverUrl,
                            mode = mode,
                            transport = transport,
                            inject = intentInject,
                        )
                    ).collect { line -> addLog(line) }
                } catch (e: CancellationException) {
                    throw e // 不吞取消（fail-closed §4.6/§4.7）
                } catch (e: Exception) {
                    addLog("RUN_FAILED error=$e")
                } finally {
                    running = false
                }
            }
        }

        LaunchedEffect(logs.size) {
            if (logs.isNotEmpty()) listState.animateScrollToItem(logs.size - 1)
        }

        LaunchedEffect(Unit) {
            if (intentAutorun) {
                intentAutorun = false
                startRun()
            }
        }

        Column(modifier = Modifier.fillMaxSize().padding(12.dp)) {
            OutlinedTextField(
                value = serverUrl,
                onValueChange = { serverUrl = it },
                label = { Text("Server base URL") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Row(modifier = Modifier.padding(vertical = 8.dp)) {
                Button(enabled = !running, onClick = { startRun() }) {
                    Text(if (running) "Running..." else "Run")
                }
                Spacer(modifier = Modifier.width(8.dp))
                OutlinedButton(
                    enabled = !running,
                    onClick = {
                        mode = if (mode == TestEngine.Mode.QUICK) {
                            TestEngine.Mode.FORENSIC
                        } else {
                            TestEngine.Mode.QUICK
                        }
                    },
                ) {
                    Text(if (mode == TestEngine.Mode.QUICK) "Mode: Quick" else "Mode: Forensic")
                }
                Spacer(modifier = Modifier.width(8.dp))
                OutlinedButton(
                    enabled = !running,
                    onClick = {
                        transport = when (transport) {
                            TestEngine.TransportMode.AUTO -> TestEngine.TransportMode.WIFI
                            TestEngine.TransportMode.WIFI -> TestEngine.TransportMode.CELLULAR
                            TestEngine.TransportMode.CELLULAR -> TestEngine.TransportMode.AUTO
                        }
                    },
                ) {
                    Text("Net: ${transport.name}")
                }
                Spacer(modifier = Modifier.width(8.dp))
                OutlinedButton(onClick = { onRadioSnapshot { line -> addLog(line) } }) {
                    Text("Radio")
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
