package com.aneb.probe.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.apiprobe.LlmProvider
import com.aneb.probe.data.ApiProbeResultEntity

/**
 * 真实 API 探针屏（阶段 2）。**独立入口**：不动 TestEngine 流程；结果单独归类展示
 * （claim scope=application_end_to_end_to_llm_api，不进 AQS，不与仿真 KPI 混排）。
 *
 * E-03 缺 key 降级：无 key 时 Run 按钮禁用置灰并显示"E-03 未配置"。
 * key 输入框密文显示；key 永不回显到日志/导出（出口经 ApiKeyRedactor，单测锚定）。
 */
@Composable
fun ApiProbeScreen(
    provider: LlmProvider,
    onProviderChange: (LlmProvider) -> Unit,
    baseUrl: String,
    onBaseUrlChange: (String) -> Unit,
    model: String,
    onModelChange: (String) -> Unit,
    keyInput: String,
    onKeyInputChange: (String) -> Unit,
    hasStoredKey: Boolean,
    keyStoreEncrypted: Boolean,
    onSaveConfig: () -> Unit,
    onClearKey: () -> Unit,
    running: Boolean,
    onRun: () -> Unit,
    logs: SnapshotStateList<String>,
    results: List<ApiProbeResultEntity>,
    exportStatus: String?,
    onExport: () -> Unit,
    onBack: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize().padding(12.dp)) {
        Row(modifier = Modifier.horizontalScroll(rememberScrollState())) {
            OutlinedButton(onClick = onBack) { Text("Back") }
            Spacer(modifier = Modifier.width(8.dp))
            OutlinedButton(
                enabled = !running,
                onClick = {
                    onProviderChange(
                        when (provider) {
                            LlmProvider.ANTHROPIC -> LlmProvider.OPENAI_COMPAT
                            LlmProvider.OPENAI_COMPAT -> LlmProvider.ANTHROPIC
                        }
                    )
                },
            ) {
                Text(
                    when (provider) {
                        LlmProvider.ANTHROPIC -> "Provider: Anthropic"
                        LlmProvider.OPENAI_COMPAT -> "Provider: OpenAI兼容(Kimi)"
                    }
                )
            }
        }
        OutlinedTextField(
            value = baseUrl,
            onValueChange = onBaseUrlChange,
            label = { Text("Base URL") },
            singleLine = true,
            enabled = !running,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = model,
            onValueChange = onModelChange,
            label = { Text("Model") },
            singleLine = true,
            enabled = !running,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = keyInput,
            onValueChange = onKeyInputChange,
            label = { Text(if (hasStoredKey) "API key（已保存，输入可覆盖）" else "API key") },
            singleLine = true,
            enabled = !running,
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )
        if (!keyStoreEncrypted) {
            Text(
                "警告：Keystore 不可用，key 以应用私有明文 prefs 存储（沙箱内，见 ApiKeyStore 取舍）",
                color = MaterialTheme.colorScheme.error,
                fontSize = 11.sp,
            )
        }
        Row(
            modifier = Modifier
                .padding(vertical = 8.dp)
                .horizontalScroll(rememberScrollState()),
        ) {
            Button(enabled = !running, onClick = onSaveConfig) { Text("保存配置") }
            Spacer(modifier = Modifier.width(8.dp))
            // E-03 缺 key 降级：入口禁用置灰
            Button(enabled = !running && hasStoredKey, onClick = onRun) {
                Text(
                    when {
                        running -> "Running..."
                        !hasStoredKey -> "E-03 未配置"
                        else -> "Run API Probe"
                    }
                )
            }
            Spacer(modifier = Modifier.width(8.dp))
            OutlinedButton(enabled = !running && hasStoredKey, onClick = onClearKey) {
                Text("清除 key")
            }
            Spacer(modifier = Modifier.width(8.dp))
            OutlinedButton(enabled = results.isNotEmpty(), onClick = onExport) {
                Text("导出(独立JSON)")
            }
        }
        Text(
            "对照列口径：application_end_to_end_to_llm_api（含用户网络路径/代理/模型推理），" +
                "不进 AQS、不与仿真节点 KPI 混排",
            fontSize = 11.sp,
        )
        exportStatus?.let { Text(it, fontFamily = FontFamily.Monospace, fontSize = 10.sp) }
        HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))
        LazyColumn(modifier = Modifier.weight(1f).fillMaxWidth()) {
            items(count = results.size, key = { it }) { i ->
                val r = results[i]
                fun f(v: Double?) = if (v == null) "null" else "%.1f".format(v)
                Text(
                    "[${r.provider}/${r.model}] http=${r.httpCode ?: "-"} " +
                        "ttft=${f(r.ttftMs)}ms itl_p50=${f(r.itlMedianMs)} itl_p95=${f(r.itlP95Ms)} " +
                        "tokens=${r.tokenEventCount} total=${f(r.totalMs)}ms " +
                        "proxy=${r.proxyDetected}" +
                        (r.error?.let { " err=$it" } ?: ""),
                    fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp,
                )
            }
            items(count = logs.size, key = { 1_000_000 + it }) { index ->
                Text(text = logs[index], fontFamily = FontFamily.Monospace, fontSize = 11.sp)
            }
        }
    }
}
