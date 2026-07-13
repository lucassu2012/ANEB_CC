package com.aneb.probe.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.engine.TestEngine
import com.aneb.probe.ui.components.SectionLabel
import com.aneb.probe.ui.components.SegmentedControl
import com.aneb.probe.ui.theme.AnebTheme

/**
 * 设置页（设计稿 §设置）：服务器（bare-IP 默认 / sslip.io / 自定义）、模式（快测/取证）、
 * 传输（自动/WiFi/蜂窝）、Kimi/LLM API 探针入口、路测开关、debug 注入提示。清晰中文。
 *
 * 纯 UI 层：状态由 MainActivity 提升（撑过配置变更、与 autorun/测量语义正交）。
 */
@Composable
fun SettingsScreen(
    serverUrl: String,
    onServerUrlChange: (String) -> Unit,
    mode: TestEngine.Mode,
    onModeChange: (TestEngine.Mode) -> Unit,
    transport: TestEngine.TransportMode,
    onTransportChange: (TestEngine.TransportMode) -> Unit,
    driveTest: Boolean,
    onDriveTestChange: (Boolean) -> Unit,
    injectActive: String?,
    onOpenApiProbe: () -> Unit,
    onBack: () -> Unit,
) {
    val colors = AnebTheme.colors
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(colors.background)
            .padding(horizontal = 20.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            BackButton(onBack)
            Spacer(Modifier.width(10.dp))
            Text("设置", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = colors.ink)
        }

        // ---- 服务器 ----
        SectionLabel("测量服务器")
        val presets = listOf(
            ServerPreset("bare-IP（默认）", "https://120.79.148.0:8443"),
            ServerPreset("sslip.io（公网 TLS）", "https://120-79-148-0.sslip.io:8443"),
        )
        presets.forEach { p ->
            val selected = serverUrl == p.url
            OptionRow(
                title = p.label,
                subtitle = p.url,
                selected = selected,
                onClick = { onServerUrlChange(p.url) },
            )
        }
        OutlinedTextField(
            value = serverUrl,
            onValueChange = onServerUrlChange,
            label = { Text("自定义服务器地址") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
        )

        // ---- 模式 ----
        SectionLabel("测量模式")
        SegmentedControl(
            options = listOf(TestEngine.Mode.QUICK, TestEngine.Mode.FORENSIC),
            selected = mode,
            onSelect = onModeChange,
            label = { if (it == TestEngine.Mode.QUICK) "快测（约 90s）" else "取证（多遍拉丁方）" },
            modifier = Modifier.fillMaxWidth(),
        )

        // ---- 传输 ----
        SectionLabel("传输通道")
        SegmentedControl(
            options = listOf(
                TestEngine.TransportMode.AUTO,
                TestEngine.TransportMode.WIFI,
                TestEngine.TransportMode.CELLULAR,
            ),
            selected = transport,
            onSelect = onTransportChange,
            label = {
                when (it) {
                    TestEngine.TransportMode.AUTO -> "自动"
                    TestEngine.TransportMode.WIFI -> "WiFi"
                    TestEngine.TransportMode.CELLULAR -> "蜂窝"
                }
            },
            modifier = Modifier.fillMaxWidth(),
        )

        // ---- API 探针入口 ----
        SectionLabel("对照：真实 LLM API 探针")
        OptionRow(
            title = "Kimi / OpenAI 兼容 API 探针",
            subtitle = "API key 走 Android Keystore 加密存储 · 独立口径不进 AQS",
            selected = false,
            onClick = onOpenApiProbe,
        )

        // ---- 路测开关（隐私边界）----
        SectionLabel("GPS 路测")
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .background(colors.surfaceElevated)
                .border(1.dp, colors.hairline, RoundedCornerShape(12.dp))
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text("记录位置轨迹（1Hz）", fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = colors.ink)
                Text(
                    "坐标仅存本机、绝不上报服务器（§9.1）",
                    fontSize = 11.sp,
                    color = if (driveTest) colors.poor else colors.muted,
                )
            }
            Switch(checked = driveTest, onCheckedChange = onDriveTestChange)
        }

        if (injectActive != null) {
            Spacer(Modifier.height(10.dp))
            Text(
                "调试注入生效：$injectActive（本次 run 非取证证据）",
                fontSize = 12.sp,
                color = colors.poor,
            )
        }

        Spacer(Modifier.height(24.dp))
        Text(
            ResultFormat.CLAIM_SCOPE_TEXT,
            fontSize = 11.sp,
            color = colors.faint,
        )
        Spacer(Modifier.height(24.dp))
    }
}

private data class ServerPreset(val label: String, val url: String)

@Composable
private fun OptionRow(title: String, subtitle: String, selected: Boolean, onClick: () -> Unit) {
    val colors = AnebTheme.colors
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(colors.surfaceElevated)
            .border(
                1.dp,
                if (selected) colors.brand else colors.hairline,
                RoundedCornerShape(12.dp),
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(title, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = colors.ink)
            Text(subtitle, fontSize = 11.sp, color = colors.muted)
        }
        if (selected) {
            Text("✓", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = colors.brand)
        }
    }
}

@Composable
internal fun BackButton(onBack: () -> Unit) {
    val colors = AnebTheme.colors
    Text(
        text = "← 返回",
        fontSize = 13.sp,
        color = colors.ink,
        modifier = Modifier
            .clip(RoundedCornerShape(9.dp))
            .background(colors.surfaceMuted)
            .border(1.dp, colors.hairline, RoundedCornerShape(9.dp))
            .clickable(onClick = onBack)
            .padding(horizontal = 12.dp, vertical = 7.dp),
    )
}
