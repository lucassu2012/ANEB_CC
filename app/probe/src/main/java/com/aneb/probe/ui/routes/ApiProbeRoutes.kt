package com.aneb.probe.ui.routes

import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import com.aneb.probe.apiprobe.AiReachabilityProbe
import com.aneb.probe.apiprobe.ApiKeyStore
import com.aneb.probe.apiprobe.ApiProbe
import com.aneb.probe.apiprobe.ApiProbeReport
import com.aneb.probe.apiprobe.LlmProvider
import com.aneb.probe.apiprobe.ObservationJsonlWriter
import com.aneb.probe.apiprobe.ProviderPresets
import com.aneb.probe.apiprobe.toLlmProvider
import com.aneb.probe.data.AnebDatabase
import com.aneb.probe.data.Exporter
import com.aneb.probe.ui.ApiProbeScreen
import com.aneb.probe.ui.ReachabilityBoardScreen
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// ------------------------------------------------------------------
// API Probe 路由（阶段 2：真实 API 探针，独立入口）
// ------------------------------------------------------------------

@Composable
internal fun ApiProbeRoute(
    db: AnebDatabase,
    appContext: Context,
    scope: CoroutineScope,
    onBack: () -> Unit,
    onOpenReachBoard: () -> Unit,
) {
    val keyStore = remember { ApiKeyStore(appContext) }
    var provider by rememberSaveable { mutableStateOf(keyStore.provider) }
    var baseUrl by rememberSaveable { mutableStateOf(keyStore.effectiveBaseUrl()) }
    var model by rememberSaveable { mutableStateOf(keyStore.effectiveModel()) }
    var selectedPresetId by rememberSaveable { mutableStateOf<String?>(null) }
    var keyInput by remember { mutableStateOf("") }
    var hasStoredKey by remember { mutableStateOf(keyStore.hasKey()) }
    var running by remember { mutableStateOf(false) }
    var exportStatus by remember { mutableStateOf<String?>(null) }
    val logs = remember { mutableStateListOf<String>() }
    var results by remember { mutableStateOf(emptyList<com.aneb.probe.data.ApiProbeResultEntity>()) }
    var resultsVersion by remember { mutableStateOf(0) }

    LaunchedEffect(resultsVersion) {
        results = withContext(Dispatchers.IO) { db.apiProbeResultDao().recent(20) }
    }

    fun addLog(line: String) {
        android.util.Log.i("AnebProbe", line)
        logs.add(line)
    }

    ApiProbeScreen(
        provider = provider,
        onProviderChange = { p ->
            provider = p
            if (baseUrl == LlmProvider.ANTHROPIC.defaultBaseUrl ||
                baseUrl == LlmProvider.OPENAI_COMPAT.defaultBaseUrl
            ) {
                baseUrl = p.defaultBaseUrl
            }
            if (model == LlmProvider.ANTHROPIC.defaultModel ||
                model == LlmProvider.OPENAI_COMPAT.defaultModel
            ) {
                model = p.defaultModel
            }
        },
        baseUrl = baseUrl,
        onBaseUrlChange = { baseUrl = it },
        model = model,
        onModelChange = { model = it },
        keyInput = keyInput,
        onKeyInputChange = { keyInput = it },
        hasStoredKey = hasStoredKey,
        keyStoreEncrypted = keyStore.encrypted,
        onSaveConfig = {
            keyStore.provider = provider
            keyStore.baseUrlOverride = baseUrl.takeIf { it != provider.defaultBaseUrl }
            keyStore.modelOverride = model.takeIf { it != provider.defaultModel }
            if (keyInput.isNotBlank()) {
                keyStore.setApiKey(keyInput)
                keyInput = ""
            }
            hasStoredKey = keyStore.hasKey()
            addLog("APIPROBE_CONFIG saved provider=${provider.id} key_present=$hasStoredKey")
        },
        onClearKey = {
            keyStore.setApiKey(null)
            hasStoredKey = false
            addLog("APIPROBE_CONFIG key_cleared")
        },
        running = running,
        onRun = {
            val key = keyStore.apiKey()
            if (key == null) {
                addLog("APIPROBE_SKIP reason=E-03_no_key")
            } else if (!running) {
                running = true
                scope.launch {
                    try {
                        // Profile-2 校准 observation 落地（PO 授权 2026-07-18；口径=API 直调≠消费App画像）：
                        // 每次干净成功的探针 → 一条隐私最小化 observation 追加到 App 私有 filesDir/observations/。
                        // datasetSecret 由 ApiKeyStore 自管（不经手明文）；subject=<provider>-<model>。
                        val obsWriter = ObservationJsonlWriter(File(appContext.filesDir, "observations"))
                        val obsSink = ApiProbe.ObservationSink(
                            datasetSecret = keyStore.datasetSecret(),
                            subject = "${provider.id}-$model",
                            emit = { obs -> withContext(Dispatchers.IO) { obsWriter.append(obs, provider.id) } },
                        )
                        // workload 默认 TEXT（探针请求体恒 text）；observation 的 workload_kind
                        // 由此 run 参单一决定，与请求体同源（finding #2, D-64）。
                        ApiProbe(appContext).run(
                            ApiProbe.Config(provider, baseUrl, model, key),
                            observationSink = obsSink,
                        ) { line -> withContext(Dispatchers.Main) { addLog(line) } }
                        resultsVersion++
                    } catch (e: CancellationException) {
                        throw e
                    } catch (e: Exception) {
                        addLog("APIPROBE_FAILED error=${e.javaClass.simpleName}")
                    } finally {
                        running = false
                    }
                }
            }
        },
        logs = logs,
        results = results,
        exportStatus = exportStatus,
        onExport = {
            scope.launch(Dispatchers.IO) {
                val all = db.apiProbeResultDao().all()
                val body = ApiProbeReport.buildJson(all, keyStore.apiKey())
                val ts = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
                val fileName = "aneb_apiprobe_$ts.json"
                val outcome = Exporter.exportToDownloads(
                    appContext, fileName, "application/json", body,
                )
                val line =
                    "APIPROBE_EXPORT file=$fileName bytes=${outcome.bytes} " +
                        "status=${if (outcome.ok) "ok" else "fail"} " +
                        "claim_scope=${ApiProbeReport.CLAIM_SCOPE}"
                android.util.Log.i("AnebProbe", line)
                withContext(Dispatchers.Main) { exportStatus = line }
            }
        },
        // 预置接入（mode②）：选中预置自动填 provider/base/model；key 处理逐字不变。
        presets = ProviderPresets.all,
        selectedPresetId = selectedPresetId,
        onSelectPreset = { p ->
            selectedPresetId = p.id
            provider = p.toLlmProvider()
            baseUrl = p.baseUrl
            model = p.defaultModel
        },
        onOpenReachBoard = onOpenReachBoard,
        onBack = onBack,
    )
}

// ------------------------------------------------------------------
// 可达性看板路由（mode①：AiReachabilityProbe 无 key 连接层探测，best-effort、不进 AQS）
// ------------------------------------------------------------------

@Composable
internal fun ReachBoardRoute(scope: CoroutineScope, onBack: () -> Unit) {
    var rows by remember { mutableStateOf(emptyList<AiReachabilityProbe.Result>()) }
    var running by remember { mutableStateOf(false) }
    var lastRunLabel by remember { mutableStateOf<String?>(null) }
    ReachabilityBoardScreen(
        rows = rows,
        running = running,
        onRun = {
            if (!running) {
                running = true
                // 起跑先把全部预置播种为 UNPROBED，随 onResult 逐条就地更新（看板逐条亮起，不再像卡死）
                rows = ProviderPresets.all.map { p ->
                    AiReachabilityProbe.Result(
                        presetId = p.id,
                        displayName = p.displayName,
                        host = runCatching { java.net.URI(p.baseUrl).host }.getOrNull() ?: p.baseUrl,
                        status = AiReachabilityProbe.Status.UNPROBED,
                        tlsHandshakeMs = null,
                        connectMs = null,
                        httpCode = null,
                        verified = p.verified,
                        note = null,
                    )
                }
                scope.launch {
                    try {
                        val probed = withContext(Dispatchers.IO) {
                            AiReachabilityProbe().probeAll(ProviderPresets.all) { r ->
                                withContext(Dispatchers.Main) {
                                    rows = rows.map { if (it.presetId == r.presetId) r else it }
                                }
                            }
                        }
                        val ok = probed.count { it.status == AiReachabilityProbe.Status.OK }
                        lastRunLabel = "刚刚 · ${probed.size} 家 · $ok 通"
                    } catch (e: CancellationException) {
                        throw e
                    } catch (e: Exception) {
                        android.util.Log.i(
                            "AnebProbe",
                            "AIREACH_FAILED error=${e.javaClass.simpleName}",
                        )
                    } finally {
                        running = false
                    }
                }
            }
        },
        onBack = onBack,
        lastRunLabel = lastRunLabel,
        claimScopeNote =
            "连接层口径（${AiReachabilityProbe.CLAIM_SCOPE}）：仅判定能否完成 TLS 握手" +
                "（拿到任意 HTTP 响应即通），不测 TTFT、不进 AQS，不看 2xx/4xx 语义。",
    )
}
