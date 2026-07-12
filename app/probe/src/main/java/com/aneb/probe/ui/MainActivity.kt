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
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.aneb.probe.engine.TestEngine
import com.aneb.probe.net.AnebClient
import com.aneb.probe.radio.RadioCollector
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

/**
 * 阶段 0 单屏 UI：服务器地址输入 + Run S1 + radio 快照 + 可滚动日志区。
 * 测试执行：lifecycleScope 启协程，TestEngine 内部 flowOn(Dispatchers.IO)。
 *
 * TODO(阶段1)：迁前台 dataSync Service + 屏幕常亮；取证模式日志降为 1-2Hz 摘要刷新
 * （防渲染争抢 CPU 污染打点，R-16）。
 */
class MainActivity : ComponentActivity() {

    private val engine = TestEngine(AnebClient())
    private lateinit var radioCollector: RadioCollector

    /** adb 自动化：am start --es server <url> --ez autorun true 时注入（联调可观测性，不改测量语义） */
    private var intentServer: String? = null
    private var intentAutorun: Boolean = false

    private val radioPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { grants ->
            pendingRadioLog?.invoke(
                if (grants.values.all { it }) radioCollector.snapshot()
                else radioCollector.snapshot() // 未授权时 collector 自行输出 valid_low_confidence 降级串
            )
            pendingRadioLog = null
        }

    /** 权限回调后往日志区补一行（避免在回调里持有 Compose state 引用之外的东西） */
    private var pendingRadioLog: ((String) -> Unit)? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        radioCollector = RadioCollector(this)
        intentServer = intent?.getStringExtra("server")
        intentAutorun = intent?.getBooleanExtra("autorun", false) == true
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
        // 默认 10.0.2.2 = Android 模拟器指向宿主机；adb intent --es server 可覆盖
        var serverUrl by remember { mutableStateOf(intentServer ?: "http://10.0.2.2:8443") }
        var running by remember { mutableStateOf(false) }
        val logs = remember { mutableStateListOf<String>() }
        val listState = rememberLazyListState()

        // 联调可观测性：UI 日志同时镜像到 logcat（tag=AnebProbe），不改测量语义
        fun addLog(line: String) {
            android.util.Log.i("AnebProbe", line)
            logs.add(line)
        }

        // 与按钮 onClick 等价的执行路径（autorun 复用，保证 adb 自动化与手工点按一致）
        fun startRun() {
            if (running) return
            running = true
            addLog(">>> Run S1 -> $serverUrl")
            lifecycleScope.launch {
                try {
                    engine.runS1(serverUrl).collect { line -> addLog(line) }
                } catch (e: CancellationException) {
                    throw e // 不吞取消：保持结构化并发语义（fail-closed §4.6/§4.7）
                } catch (e: Exception) {
                    addLog("RUN FAILED: $e")
                } finally {
                    running = false
                }
            }
        }

        LaunchedEffect(logs.size) {
            if (logs.isNotEmpty()) listState.animateScrollToItem(logs.size - 1)
        }

        // adb 自动化：--ez autorun true 时自动触发一次 Run S1（等价点按钮，只触发一次）
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
                Button(
                    enabled = !running,
                    onClick = { startRun() },
                ) {
                    Text(if (running) "Running..." else "Run S1")
                }
                Spacer(modifier = Modifier.width(8.dp))
                Button(onClick = { onRadioSnapshot { line -> addLog(line) } }) {
                    Text("Radio snapshot")
                }
            }
            HorizontalDivider()
            LazyColumn(
                state = listState,
                modifier = Modifier.weight(1f).fillMaxWidth(),
            ) {
                // key=索引：日志 append-only（只增不删不重排），索引稳定；
                // 日志行内容可重复（如多次 "ok"），不能拿内容当 key。
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
