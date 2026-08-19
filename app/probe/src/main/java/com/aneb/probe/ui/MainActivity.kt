package com.aneb.probe.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.lifecycleScope
import com.aneb.probe.BuildConfig
import com.aneb.probe.apiprobe.ApiProbe
import com.aneb.probe.apiprobe.LlmProvider
import com.aneb.probe.data.AnebDatabase
import com.aneb.probe.data.SyntheticResultEntity
import com.aneb.probe.data.VoiceResultEntity
import com.aneb.probe.engine.AbRunner
import com.aneb.probe.engine.ContinuityRunner
import com.aneb.probe.engine.SpeedRunner
import com.aneb.probe.engine.SyntheticRecoveryRunner
import com.aneb.probe.engine.TestEngine
import com.aneb.probe.engine.VoiceRunner
import com.aneb.probe.radio.RadioCollector
import com.aneb.probe.ui.components.AnebTabBar
import com.aneb.probe.ui.components.MainTab
import com.aneb.probe.ui.routes.ApiProbeRoute
import com.aneb.probe.ui.routes.HistoryRoute
import com.aneb.probe.ui.routes.HomeRoute
import com.aneb.probe.ui.routes.ReachBoardRoute
import com.aneb.probe.ui.routes.ReportRoute
import com.aneb.probe.ui.routes.ResultRoute
import com.aneb.probe.ui.theme.AnebTheme
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * 单 Activity 状态切换导航（UI 重设计）：
 *   Home（GO 大按钮 + 上次结果）/ Testing（脉冲环实时进度）/ Result（双视图）/
 *   History / Settings / ApiProbe。
 *
 * 测量语义、adb 自动化、logcat 合同全部不动——run 编排（engine.run 收集、autorun、
 * 各 KEY 日志）与阶段 1 逐字一致，仅展示层从"日志控制台"重构为设计稿界面。
 *
 * adb 自动化（不改测量语义）：
 *   am start ... --es server <url> --ez autorun true [--es mode quick|forensic|continuity|ab]
 *   [--es transport auto|wifi|cellular] [--es inject truncate:50]
 * C07：手动 run 结束自动跳结果页；autorun 不跳（保持 logcat 自动化验收流程不变）。
 */
class MainActivity : ComponentActivity() {

    private lateinit var engine: TestEngine
    private lateinit var continuityRunner: ContinuityRunner
    private lateinit var abRunner: AbRunner
    private lateinit var speedRunner: SpeedRunner
    private lateinit var syntheticRecoveryRunner: SyntheticRecoveryRunner
    private lateinit var voiceRunner: VoiceRunner
    private lateinit var radioCollector: RadioCollector
    private lateinit var db: AnebDatabase

    /** autorun 测量窗常亮策略（T25，D-427）；生命周期在 onCreate/onDestroy 驱动。 */
    private val keepScreenOnPolicy = KeepScreenOnPolicy()

    private var intentServer: String? = null
    private var intentAutorun: Boolean = false
    private var intentMode: TestEngine.Mode = TestEngine.Mode.QUICK
    private var intentTransport: TestEngine.TransportMode = TestEngine.TransportMode.AUTO
    private var intentInject: String? = null
    private var intentWeakNet: String? = null
    private var intentDriveTest: Boolean = false

    private var intentContinuity: Boolean = false
    private var intentCTokens: Int = ContinuityRunner.DEFAULT_TOKENS
    private var intentC3IdleS: List<Int> = ContinuityRunner.DEFAULT_C3_IDLE_S

    private var intentAb: Boolean = false
    private var intentAbPairs: Int = AbRunner.DEFAULT_PAIRS
    private var intentAbNetlog: Boolean = false

    private val radioPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { _ -> }

    /**
     * 下钻子状态机（SpeedTest 式外壳）：Home=当前 tab 的根哨兵（此时显底栏 [AnebTabBar]），
     * 其余为下钻屏（隐底栏、靠各自返回键回根）。底部 3-tab 测试/历史/设置见 [MainTab]，均是
     * Home 哨兵下按 tab 选根，不再是 Screen 值。可达性看板 [ReachBoard] 已从顶级 tab 降为设置里
     * 的二级下钻入口。Result.fromHistory 仅为兼容 startRun 逐字构造保留（导航现由 tab 决定回根）。
     */
    private sealed interface Screen {
        data object Home : Screen
        data class Result(val runId: String, val fromHistory: Boolean) : Screen
        data object ApiProbe : Screen
        data object ReachBoard : Screen
        data object Report : Screen
    }

    @OptIn(ExperimentalComposeUiApi::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // 铁律 1：Profile 数据文件加载（assets 权威；失败回退硬编码兜底，KEY=SPEC_PROFILE_FALLBACK）
        TestModeProfiles.initFrom(applicationContext)
        engine = TestEngine(applicationContext)
        continuityRunner = ContinuityRunner(applicationContext)
        abRunner = AbRunner(applicationContext)
        speedRunner = SpeedRunner()
        syntheticRecoveryRunner = SyntheticRecoveryRunner()
        voiceRunner = VoiceRunner()
        radioCollector = RadioCollector(this)
        db = AnebDatabase.get(applicationContext)
        intentServer = intent?.getStringExtra("server")
        intentAutorun = intent?.getBooleanExtra("autorun", false) == true
        // T25/D-427：autorun 测量窗内常亮，避免 EMUI 息屏节流 cell info 采样降级为 stale
        // （三个替代假说均已实测排除，见 D-426/D-427）；这同时是口径正确性修复——试点
        // LTE 语料是屏亮态采集的，保持同态才可比（详述见 KeepScreenOnPolicy 类注释）。
        // 手动模式 autorun=false，held 恒为 false，窗口 flag 从不被设置——零改动。
        keepScreenOnPolicy.onCreate(intentAutorun)
        if (keepScreenOnPolicy.held) {
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
        intentMode = when (intent?.getStringExtra("mode")?.lowercase()) {
            "forensic" -> TestEngine.Mode.FORENSIC
            else -> TestEngine.Mode.QUICK
        }
        intentContinuity = intent?.getStringExtra("mode")?.lowercase() == "continuity"
        intentCTokens = intent?.getIntExtra("c_tokens", ContinuityRunner.DEFAULT_TOKENS)
            ?.takeIf { it > 0 } ?: ContinuityRunner.DEFAULT_TOKENS
        intentC3IdleS = intent?.getStringExtra("c3_idle")
            ?.split(',')?.mapNotNull { it.trim().toIntOrNull()?.takeIf { v -> v > 0 } }
            ?.takeIf { it.isNotEmpty() } ?: ContinuityRunner.DEFAULT_C3_IDLE_S
        intentAb = intent?.getStringExtra("mode")?.lowercase() == "ab"
        intentAbPairs = intent?.getIntExtra("ab_pairs", AbRunner.DEFAULT_PAIRS)
            ?.takeIf { it > 0 } ?: AbRunner.DEFAULT_PAIRS
        intentAbNetlog = BuildConfig.DEBUG && intent?.getBooleanExtra("ab_netlog", false) == true
        intentTransport = when (intent?.getStringExtra("transport")?.lowercase()) {
            "wifi" -> TestEngine.TransportMode.WIFI
            "cellular" -> TestEngine.TransportMode.CELLULAR
            else -> TestEngine.TransportMode.AUTO
        }
        intentInject = if (BuildConfig.DEBUG) intent?.getStringExtra("inject") else null
        intentWeakNet = if (BuildConfig.DEBUG) intent?.getStringExtra("weaknet") else null
        intentDriveTest = intent?.getBooleanExtra("drive_test", false) == true
        maybeApiProbeAutorun()

        setContent {
            AnebTheme {
                // iOS chrome 接入点：应用底用 OLED 背景（--a #000 / 浅色 #F2F2F7），safe-area
                // 内衬；各屏顶/底毛玻璃 chrome 由 GlassChrome 承载（内容留待下一阶段）。
                Surface(
                    color = AnebTheme.colors.background,
                    // T52/D-485：树根开启 testTagsAsResourceId，Compose 的 Modifier.testTag
                    // 才会映射成 uiautomator/accessibility 树里的 resource-id（默认只对 Compose
                    // 自身测试框架 onNodeWithTag 可见，adb 侧读不到）——一次性根设置，全树受益。
                    modifier = Modifier.fillMaxSize().safeDrawingPadding()
                        .semantics { testTagsAsResourceId = true },
                ) {
                    var screen by remember { mutableStateOf<Screen>(Screen.Home) }
                    // 底部 3-tab 外壳选中态（默认 Speed）；下钻只在 Home 哨兵下按 tab 决定根，
                    // 故切 tab 只发生在各 tab 根（切换前后 screen 均为 Home），子状态天然互不串扰。
                    var tab by rememberSaveable { mutableStateOf(MainTab.Test) }
                    var serverUrl by rememberSaveable {
                        mutableStateOf(intentServer ?: "https://120-79-148-0.sslip.io:8443")
                    }
                    var mode by rememberSaveable { mutableStateOf(intentMode) }
                    var transport by rememberSaveable { mutableStateOf(intentTransport) }
                    var driveTest by rememberSaveable { mutableStateOf(intentDriveTest) }
                    var running by remember { mutableStateOf(false) }
                    val logs = remember { mutableStateListOf<String>() }
                    // 实时遥测上提到根：供首页在测量中原地驱动仪表（R-16 只读观测，不回压热路径）
                    val telemetry by engine.telemetry.collectAsStateWithLifecycle()
                    // 持有 run 协程句柄，供首页"取消"按钮中断（cancel → CancellationException → finally running=false）
                    var runJob by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }
                    // 网络基本性能模式（SpeedTest）：模式开关 + 独立 run 状态/实时样本/协程句柄
                    var selectedModeId by rememberSaveable { mutableStateOf(TestModeProfiles.TOKEN_EXPERIENCE.id) }
                    var speedRunning by remember { mutableStateOf(false) }
                    var speedSample by remember { mutableStateOf<SpeedRunner.Sample?>(null) }
                    var speedJob by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }
                    // 恢复子测（weak-recovery-v1 合成合同，D-40）：独立于测速的观测态
                    var recoveryRunning by remember { mutableStateOf(false) }
                    var recoverySample by remember { mutableStateOf<SyntheticRecoveryRunner.Sample?>(null) }
                    var recoveryJob by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }
                    // 弱网对照（weak-capacity-latency-v1 合成整形，D-43）：合成口径，不并入正常测速结论
                    var shapedRunning by remember { mutableStateOf(false) }
                    var shapedSample by remember { mutableStateOf<SpeedRunner.Sample?>(null) }
                    var shapedJob by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }
                    // 语音实时交互模式（§4.1）：独立 run 状态/实时样本/协程句柄
                    var voiceRunning by remember { mutableStateOf(false) }
                    var voiceSample by remember { mutableStateOf<VoiceRunner.Sample?>(null) }
                    var voiceJob by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }
                    // 语音连续性 mini-run（受控断连，D-41 预定）：独立于主语音测量的观测态
                    var contRunning by remember { mutableStateOf(false) }
                    var contSample by remember { mutableStateOf<VoiceRunner.Sample?>(null) }
                    var contJob by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }

                    fun addLog(line: String) {
                        android.util.Log.i("AnebProbe", line)
                        logs.add(line)
                    }

                    // ---- run 编排（与阶段 1 逐字一致；仅把导航接到新界面）----
                    fun startRun(fromAutorun: Boolean) {
                        if (running) return
                        running = true
                        // 测试原地留在首页（环变形驱动），不再跳独立测试页；RUN_END 仍由 jumpToResult 跳结果页
                        addLog(">>> RUN mode=${mode.name.lowercase()} transport=${transport.name.lowercase()} -> $serverUrl")
                        runJob = lifecycleScope.launch {
                            var runId: String? = null
                            var navigated = false
                            fun jumpToResult() {
                                val id = runId
                                if (!fromAutorun && !navigated && id != null) {
                                    navigated = true
                                    screen = Screen.Result(id, fromHistory = false)
                                }
                            }
                            try {
                                engine.run(
                                    TestEngine.RunConfig(
                                        serverBase = serverUrl,
                                        mode = mode,
                                        transport = transport,
                                        inject = intentInject,
                                        driveTest = driveTest,
                                        weakNet = intentWeakNet,
                                    )
                                ).collect { line ->
                                    addLog(line)
                                    if (runId == null && line.startsWith("RUN_START ")) {
                                        runId = Regex("run_id=(\\S+)").find(line)?.groupValues?.get(1)
                                    }
                                    if (line.startsWith("RUN_END ")) jumpToResult()
                                }
                                jumpToResult()
                            } catch (e: CancellationException) {
                                throw e
                            } catch (e: Exception) {
                                addLog("RUN_FAILED error=$e")
                                if (!fromAutorun) screen = Screen.Home
                            } finally {
                                running = false
                            }
                        }
                    }

                    fun startContinuityRun() {
                        if (running) return
                        running = true
                        addLog(">>> CONTINUITY transport=${transport.name.lowercase()} -> $serverUrl")
                        lifecycleScope.launch {
                            try {
                                continuityRunner.run(
                                    ContinuityRunner.Config(
                                        serverBase = serverUrl,
                                        transport = transport,
                                        tokens = intentCTokens,
                                        c3IdleSeconds = intentC3IdleS,
                                    )
                                ).collect { line -> addLog(line) }
                            } catch (e: CancellationException) {
                                throw e
                            } catch (e: Exception) {
                                addLog("CONTINUITY_FAILED error=$e")
                            } finally {
                                running = false
                            }
                        }
                    }

                    fun startAbRun() {
                        if (running) return
                        running = true
                        addLog(">>> AB pairs=$intentAbPairs -> $serverUrl")
                        lifecycleScope.launch {
                            try {
                                abRunner.run(
                                    AbRunner.Config(
                                        serverBase = serverUrl,
                                        pairs = intentAbPairs,
                                        netlog = intentAbNetlog,
                                    )
                                ).collect { line -> addLog(line) }
                            } catch (e: CancellationException) {
                                throw e
                            } catch (e: Exception) {
                                addLog("AB_FAILED error=$e")
                            } finally {
                                running = false
                            }
                        }
                    }

                    // 网络基本性能测速（独立于 token 引擎；实时样本驱动 SpeedTest 式仪表）
                    fun startSpeedTest() {
                        if (speedRunning || shapedRunning) return
                        speedRunning = true
                        speedSample = null
                        addLog(">>> SPEED -> $serverUrl")
                        speedJob = lifecycleScope.launch {
                            try {
                                // UDP 探针网络：speed 模式未做 requestNetwork 绑定（AUTO 口径，
                                // 与本模式 HTTP 路径一致），传当前默认网 bindSocket 使 UDP 与
                                // HTTP 测量走同一网络；未来引入绑定网时改传 bound.network。
                                val net = getSystemService(android.net.ConnectivityManager::class.java)
                                    ?.activeNetwork
                                speedRunner.run(serverUrl, network = net, weakNet = intentWeakNet).collect { speedSample = it }
                                // UDP 未返回率＝应用层探针未回显占比，≠IP 丢包率；现场协变量不进分。
                                // unreturned=null＝"UDP 应用探针不可用"（零回包/不可达，R-10 不折 0/100）
                                val u = speedRunner.lastUdpProbeResult
                                addLog(
                                    "UDP_PROBE sent=${u?.sent ?: 0} recv=${u?.received ?: 0} " +
                                        "unreturned=${u?.unreturnedPct?.let { p -> "%.1f%%".format(p) } ?: "null"}"
                                )
                            } catch (e: CancellationException) {
                                throw e
                            } catch (e: Exception) {
                                addLog("SPEED_FAILED error=$e")
                            } finally {
                                speedRunning = false
                            }
                        }
                    }

                    // 恢复子测（weak-recovery-v1 合成受控中断；观测口径，恒 LOW/INCONCLUSIVE）
                    fun startRecoveryTest() {
                        if (recoveryRunning || speedRunning) return
                        recoveryRunning = true
                        recoverySample = null
                        addLog(">>> RECOVERY(synthetic) -> $serverUrl")
                        recoveryJob = lifecycleScope.launch {
                            try {
                                syntheticRecoveryRunner.run(serverUrl).collect { recoverySample = it }
                                recoverySample?.let {
                                    addLog(
                                        "RECOVERY_SYNTH recovery_ms=${it.recoveryMs?.let { m -> "%.1f".format(m) } ?: "null"} " +
                                            "outage_503=${it.outageConfirmed} post=${it.postSuccess}/${it.postTotal} " +
                                            "rtt_p95=${it.postRttP95Ms?.let { m -> "%.1f".format(m) } ?: "null"} " +
                                            "meets=${it.meetsTargets ?: "null"} confidence=LOW_INCONCLUSIVE",
                                    )
                                }
                                // 合成子测落库（镜像 D-42 手法）：仅 Done 样本入库——实测值原样
                                // 落库（R-10：null 不补 0），恒注 LOW/INCONCLUSIVE，shaped 列置 null。
                                recoverySample?.takeIf { it.phase == SyntheticRecoveryRunner.Phase.Done }?.let { s ->
                                    val rowId = withContext(Dispatchers.IO) {
                                        db.syntheticResultDao().insert(
                                            SyntheticResultEntity(
                                                tsEpochMs = System.currentTimeMillis(),
                                                kind = "recovery",
                                                confidence = s.confidence,
                                                recoveryMs = s.recoveryMs,
                                                outage503 = s.outageConfirmed,
                                                postSuccess = s.postSuccess,
                                                postTotal = s.postTotal,
                                                rttP95Ms = s.postRttP95Ms,
                                                meetsTargets = s.meetsTargets,
                                                shapedDownMbps = null,
                                                shapedUpMbps = null,
                                                shapedRttMs = null,
                                            )
                                        )
                                    }
                                    addLog("RECOVERY_SAVED id=$rowId meets=${s.meetsTargets ?: "null"}")
                                }
                            } catch (e: CancellationException) {
                                throw e
                            } catch (e: Exception) {
                                addLog("RECOVERY_SYNTH_FAILED error=$e")
                            } finally {
                                recoveryRunning = false
                            }
                        }
                    }

                    // 弱网对照（weak-capacity-latency-v1 合成整形；与正常测速互斥，观测口径不并入正常结论）
                    fun startShapedTest() {
                        if (shapedRunning || speedRunning) return
                        shapedRunning = true
                        shapedSample = null
                        addLog(">>> SPEED_SHAPED(synthetic) -> $serverUrl")
                        shapedJob = lifecycleScope.launch {
                            try {
                                var downPeak = 0.0
                                var upPeak = 0.0
                                speedRunner.runShaped(serverUrl).collect {
                                    it.downMbps?.let { v -> if (v > downPeak) downPeak = v }
                                    it.upMbps?.let { v -> if (v > upPeak) upPeak = v }
                                    shapedSample = it
                                }
                                addLog(
                                    "SPEED_SHAPED down_peak=${"%.2f".format(downPeak)} up_peak=${"%.2f".format(upPeak)} " +
                                        "rtt=${shapedSample?.rttMs?.let { m -> "%.1f".format(m) } ?: "null"}",
                                )
                                // 合成子测落库（镜像 D-42 手法）：仅 Done 样本入库——落聚合峰值
                                // downPeak/upPeak（0 峰＝无样本，R-10 落 null 不落 0）与完成态
                                // Sample.rttMs，恒注 LOW/INCONCLUSIVE，recovery 列置 null。
                                shapedSample?.takeIf { it.phase == SpeedRunner.Phase.Done }?.let { s ->
                                    val rowId = withContext(Dispatchers.IO) {
                                        db.syntheticResultDao().insert(
                                            SyntheticResultEntity(
                                                tsEpochMs = System.currentTimeMillis(),
                                                kind = "shaped",
                                                confidence = "LOW/INCONCLUSIVE(单次合成事件)",
                                                recoveryMs = null,
                                                outage503 = null,
                                                postSuccess = null,
                                                postTotal = null,
                                                rttP95Ms = null,
                                                meetsTargets = null,
                                                shapedDownMbps = downPeak.takeIf { it > 0.0 },
                                                shapedUpMbps = upPeak.takeIf { it > 0.0 },
                                                shapedRttMs = s.rttMs,
                                            )
                                        )
                                    }
                                    addLog("SHAPED_SAVED id=$rowId down=${"%.2f".format(downPeak)} up=${"%.2f".format(upPeak)}")
                                }
                            } catch (e: CancellationException) {
                                throw e
                            } catch (e: Exception) {
                                addLog("SPEED_SHAPED_FAILED error=$e")
                            } finally {
                                shapedRunning = false
                            }
                        }
                    }

                    // 语音双工测量（独立于 token 引擎；观测口径）
                    fun startVoiceTest() {
                        if (voiceRunning) return
                        voiceRunning = true
                        voiceSample = null
                        addLog(">>> VOICE -> $serverUrl")
                        voiceJob = lifecycleScope.launch {
                            try {
                                try {
                                    // v2 server-sim 口径优先（D-38，/realtime-sim）
                                    voiceRunner.runSim(serverUrl).collect { voiceSample = it }
                                } catch (e: CancellationException) {
                                    throw e
                                } catch (e: Exception) {
                                    // 服务端不支持/协议失败 → 降级 v1 paced-proxy 口径并如实标注（不伪造 sim 数据）
                                    addLog("VOICE_SIM_FAILED fallback=paced-proxy error=$e")
                                    voiceSample = null
                                    voiceRunner.run(serverUrl).collect { voiceSample = it }
                                }
                                // D-42 语音结果落库：仅 Done 样本入库——实测值原样落库（R-10：
                                // null 不补 0），不落分数（展示时 AqsScorer 现算）。
                                voiceSample?.takeIf { it.phase == VoiceRunner.Phase.Done }?.let { s ->
                                    val rowId = withContext(Dispatchers.IO) {
                                        db.voiceResultDao().insert(
                                            VoiceResultEntity(
                                                tsEpochMs = System.currentTimeMillis(),
                                                caliber = s.caliber,
                                                lowConfidence = s.lowConfidence,
                                                rttMs = s.rttMs,
                                                jitterMs = s.jitterMs,
                                                upFrameJitterMs = s.upFrameJitterMs,
                                                downFrameJitterMs = s.downFrameJitterMs,
                                                mouthEarBudgetMs = s.mouthEarBudgetMs,
                                                framesSent = s.framesSent,
                                                framesRecv = s.framesRecv,
                                                ttfbP50Ms = s.ttfbP50Ms,
                                                ttfbP95Ms = s.ttfbP95Ms,
                                                downNetJitterMs = s.downNetJitterMs,
                                                mouthEarProxyMs = s.mouthEarProxyMs,
                                                turnSwitchP50Ms = s.turnSwitchP50Ms,
                                                bargeStopMaxMs = s.bargeStopMaxMs,
                                                turnsOk = s.turnsOk,
                                                m7MaxFrameGapMs = s.m7MaxFrameGapMs,
                                                voiceNearZeroArrivalRatio = s.voiceNearZeroArrivalRatio,
                                            )
                                        )
                                    }
                                    addLog("VOICE_SAVED id=$rowId caliber=${s.caliber ?: "paced-proxy"}")
                                }
                            } catch (e: CancellationException) {
                                throw e
                            } catch (e: Exception) {
                                addLog("VOICE_FAILED error=$e")
                            } finally {
                                voiceRunning = false
                            }
                        }
                    }

                    // 语音连续性 mini-run（受控断连；与主语音测量互斥；观测口径，恒 LOW/INCONCLUSIVE）
                    fun startVoiceContinuity() {
                        if (contRunning || voiceRunning) return
                        contRunning = true
                        contSample = null
                        addLog(">>> VOICE_CONT(controlled-disconnect) -> $serverUrl")
                        contJob = lifecycleScope.launch {
                            try {
                                voiceRunner.runSimContinuity(serverUrl).collect { contSample = it }
                                contSample?.let {
                                    addLog(
                                        "VOICE_CONT detect_ms=${it.continuityDetectMs?.let { m -> "%.1f".format(m) } ?: "null"} " +
                                            "resume_ms=${it.continuityResumeMs?.let { m -> "%.1f".format(m) } ?: "null"} " +
                                            "confidence=LOW_INCONCLUSIVE",
                                    )
                                }
                            } catch (e: CancellationException) {
                                throw e
                            } catch (e: Exception) {
                                addLog("VOICE_CONT_FAILED error=$e")
                            } finally {
                                contRunning = false
                            }
                        }
                    }

                    LaunchedEffect(Unit) {
                        if (intentAutorun) {
                            intentAutorun = false
                            when {
                                intentAb -> startAbRun()
                                intentContinuity -> startContinuityRun()
                                else -> startRun(fromAutorun = true)
                            }
                        }
                    }

                    // ---- SpeedTest 式底部 3-tab 外壳（测试 GO 凸起 / 历史 / 设置，[AnebTabBar]）----
                    // 底栏仅在各 tab 根（screen==Home）显示；下钻屏（Testing/Result/ApiProbe/
                    // ReachBoard/Report）隐底栏、Testing 运行中保持全屏专注。contentWindowInsets 置 0：
                    // Surface 已 safeDrawingPadding 统一吃系统条，避免二次内衬。
                    val atRoot = screen is Screen.Home
                    Scaffold(
                        modifier = Modifier.fillMaxSize(),
                        containerColor = AnebTheme.colors.background,
                        contentWindowInsets = WindowInsets(0, 0, 0, 0),
                        bottomBar = {
                            // 测量中隐藏底栏（首页原地进入连接/测试态，全屏专注，对齐 home.html）
                            if (atRoot && !running && !speedRunning && !voiceRunning) {
                                AnebTabBar(current = tab, onSelect = { tab = it })
                            }
                        },
                    ) { innerPadding ->
                        Box(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
                            when (val s = screen) {
                                // ---- 各 tab 根（显底栏）：测试=Home / 历史=History / 设置=Settings ----
                                is Screen.Home -> when (tab) {
                                    MainTab.Test -> Column(modifier = Modifier.fillMaxSize()) {
                                        // 模式开关 + 模式信息条——由 TestModeProfiles.ALL 数据驱动（加模式=加 profile）；
                                        // 两模式共享；测量中隐藏，全屏专注。
                                        if (!running && !speedRunning && !voiceRunning) {
                                            Column(
                                                modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp),
                                                verticalArrangement = Arrangement.spacedBy(10.dp),
                                            ) {
                                                TestModeSegments(
                                                    profiles = TestModeProfiles.ALL,
                                                    selectedId = selectedModeId,
                                                    enabled = true,
                                                    onSelect = { selectedModeId = it },
                                                )
                                                ModeProfileStrip(TestModeProfiles.byId(selectedModeId))
                                            }
                                        }
                                        if (selectedModeId == TestModeProfiles.BASIC_NETWORK.id) {
                                            // 最近合成子测记录：recoveryRunning/shapedRunning 翻 false
                                            // （run 结束、落库已完成）后重载；启动时首载
                                            val recentSynthetic by produceState(
                                                initialValue = emptyList<SyntheticResultEntity>(),
                                                recoveryRunning, shapedRunning,
                                            ) {
                                                value = withContext(Dispatchers.IO) { db.syntheticResultDao().recent(10) }
                                            }
                                            SpeedTestScreen(
                                                sample = speedSample,
                                                running = speedRunning,
                                                onStart = { startSpeedTest() },
                                                onCancel = { speedJob?.cancel() },
                                                recoverySample = recoverySample,
                                                recoveryRunning = recoveryRunning,
                                                onStartRecovery = { startRecoveryTest() },
                                                onCancelRecovery = { recoveryJob?.cancel() },
                                                shapedSample = shapedSample,
                                                shapedRunning = shapedRunning,
                                                onStartShaped = { startShapedTest() },
                                                onCancelShaped = { shapedJob?.cancel() },
                                                recentSynthetic = recentSynthetic,
                                            )
                                        } else if (selectedModeId == TestModeProfiles.VOICE_REALTIME.id) {
                                            // 最近语音记录（D-42）：voiceRunning 翻 false（run 结束）后重载
                                            val recentVoice by produceState(
                                                initialValue = emptyList<VoiceResultEntity>(), voiceRunning,
                                            ) {
                                                value = withContext(Dispatchers.IO) { db.voiceResultDao().recent(5) }
                                            }
                                            VoiceTestScreen(
                                                sample = voiceSample,
                                                running = voiceRunning,
                                                onStart = { startVoiceTest() },
                                                onCancel = { voiceJob?.cancel() },
                                                contSample = contSample,
                                                contRunning = contRunning,
                                                onStartContinuity = { startVoiceContinuity() },
                                                onCancelContinuity = { contJob?.cancel() },
                                                recentVoice = recentVoice,
                                            )
                                        } else {
                                            HomeRoute(
                                                db = db,
                                                running = running,
                                                telemetry = telemetry,
                                                logs = logs,
                                                onStart = { startRun(fromAutorun = false) },
                                                onCancel = { runJob?.cancel() },
                                                onOpenSettings = { tab = MainTab.Settings },
                                                onOpenResult = { runId ->
                                                    screen = Screen.Result(runId, fromHistory = false)
                                                },
                                            )
                                        }
                                    }
                                    MainTab.History -> HistoryRoute(
                                        db = db,
                                        onOpen = { runId ->
                                            screen = Screen.Result(runId, fromHistory = true)
                                        },
                                        onGenerateReport = { screen = Screen.Report },
                                        onBack = { tab = MainTab.Test },
                                    )
                                    MainTab.Settings -> SettingsScreen(
                                        serverUrl = serverUrl,
                                        onServerUrlChange = { serverUrl = it },
                                        mode = mode,
                                        onModeChange = { mode = it },
                                        transport = transport,
                                        onTransportChange = { transport = it },
                                        driveTest = driveTest,
                                        onDriveTestChange = { turningOn ->
                                            driveTest = turningOn
                                            if (turningOn &&
                                                ContextCompat.checkSelfPermission(
                                                    this@MainActivity, Manifest.permission.ACCESS_FINE_LOCATION,
                                                ) != PackageManager.PERMISSION_GRANTED
                                            ) {
                                                radioPermissionLauncher.launch(
                                                    arrayOf(Manifest.permission.ACCESS_FINE_LOCATION),
                                                )
                                            }
                                            android.util.Log.i("AnebProbe", "DRIVE_TEST_TOGGLE enabled=$turningOn")
                                        },
                                        injectActive = listOfNotNull(
                                            intentInject?.let { "inject=$it" },
                                            intentWeakNet?.let { "weaknet=$it" },
                                        ).joinToString(" ").ifBlank { null },
                                        onOpenApiProbe = { screen = Screen.ApiProbe },
                                        // 可达性看板已降为设置二级入口（下钻屏）。
                                        onOpenReachBoard = { screen = Screen.ReachBoard },
                                        onBack = { tab = MainTab.Test },
                                    )
                                }
                                // ---- 下钻屏（隐底栏；各自返回键回当前 tab 根）----
                                is Screen.Report -> ReportRoute(
                                    db = db,
                                    appContext = applicationContext,
                                    scope = lifecycleScope,
                                    activity = this@MainActivity,
                                    onBack = { screen = Screen.Home },
                                )
                                is Screen.Result -> ResultRoute(
                                    db = db,
                                    appContext = applicationContext,
                                    scope = lifecycleScope,
                                    activity = this@MainActivity,
                                    runId = s.runId,
                                    // 回根：tab 已记住来路（测试 手动测/上次结果 或 历史 tab 下钻），
                                    // 回到 Home 哨兵即落回当前 tab 根。
                                    onBack = { screen = Screen.Home },
                                )
                                is Screen.ApiProbe -> ApiProbeRoute(
                                    db = db,
                                    appContext = applicationContext,
                                    scope = lifecycleScope,
                                    // 从设置根下钻而来：回 Home 哨兵即落回设置 tab 根。
                                    onBack = { screen = Screen.Home },
                                    onOpenReachBoard = { screen = Screen.ReachBoard },
                                )
                                is Screen.ReachBoard -> ReachBoardRoute(
                                    scope = lifecycleScope,
                                    onBack = { screen = Screen.Home },
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    override fun onDestroy() {
        // T25/D-427：无条件释放（未持有时是安全的空操作，不会误清手动模式的窗口态；
        // 手动模式下 keepScreenOnPolicy.held 恒为 false，本分支从不执行）。
        if (keepScreenOnPolicy.held) {
            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
        keepScreenOnPolicy.onDestroy()
        super.onDestroy()
    }

    /**
     * API 探针 adb 自动化（模拟器 E2E 验收；仅 debug 构建生效）。结果只看 logcat 的
     * APIPROBE_RESULT 行（tag=AnebProbe），不落 UI。
     */
    private fun maybeApiProbeAutorun() {
        if (!BuildConfig.DEBUG) return
        if (intent?.getBooleanExtra("apiprobe_autorun", false) != true) return
        val server = intent?.getStringExtra("apiprobe_server") ?: return
        val key = intent?.getStringExtra("apiprobe_key") ?: return
        val provider = when (intent?.getStringExtra("apiprobe_provider")?.lowercase()) {
            "anthropic" -> LlmProvider.ANTHROPIC
            else -> LlmProvider.OPENAI_COMPAT
        }
        val model = intent?.getStringExtra("apiprobe_model") ?: provider.defaultModel
        lifecycleScope.launch {
            try {
                ApiProbe(applicationContext).run(
                    ApiProbe.Config(provider, server, model, key)
                ) { line -> android.util.Log.i("AnebProbe", line) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                android.util.Log.i("AnebProbe", "APIPROBE_FAILED error=${e.javaClass.simpleName}")
            }
        }
    }
}
