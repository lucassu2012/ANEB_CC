package com.aneb.probe.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.data.TestRun
import com.aneb.probe.ui.components.GaugeMode
import com.aneb.probe.ui.components.PulseGauge
import com.aneb.probe.ui.theme.AnebTheme
import com.aneb.probe.ui.theme.AnebType
import com.aneb.probe.ui.theme.Grade
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.roundToInt

/**
 * 首页（设计稿 §01 首页）：token 脉冲环 Idle + 中心大 GO 按钮，一个大决定"轻触开始"；
 * 上次结果 chip（Room 最近 run，grade 色）；副入口小按钮进历史/设置。
 *
 * 纯 UI 层：数据经参数注入（[lastRun] 由 MainActivity 查 Room），点击回调上抛。
 */
@Composable
fun HomeScreen(
    lastRun: TestRun?,
    running: Boolean,
    onStart: () -> Unit,
    onOpenHistory: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenLastResult: (String) -> Unit,
) {
    val colors = AnebTheme.colors
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(colors.background)
            .padding(horizontal = 20.dp),
    ) {
        // ---- 品牌行 + 副入口 ----
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 10.dp, bottom = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Row(verticalAlignment = Alignment.Bottom) {
                    Text("A", fontSize = 17.sp, fontWeight = FontWeight.Black, color = colors.ink)
                    Text("NEB", fontSize = 17.sp, fontWeight = FontWeight.Black, color = colors.brand2)
                }
                Text("智能体网络测试", fontSize = 10.5.sp, color = colors.muted)
            }
            Spacer(Modifier.weight(1f))
            MiniNavButton("历史", onOpenHistory)
            Spacer(Modifier.width(8.dp))
            MiniNavButton("设置", onOpenSettings)
        }

        Spacer(Modifier.weight(1f))

        // ---- token 脉冲环 Idle + 中心 GO ----
        Box(
            modifier = Modifier
                .align(Alignment.CenterHorizontally)
                .clip(RoundedCornerShape(120.dp))
                .clickable(enabled = !running, onClick = onStart),
            contentAlignment = Alignment.Center,
        ) {
            PulseGauge(mode = GaugeMode.Idle, grade = null, score = null, progress = 0f)
        }
        Text(
            "轻触开始 · 约 90 秒",
            fontSize = 12.5.sp,
            color = colors.muted,
            modifier = Modifier.align(Alignment.CenterHorizontally).padding(top = 12.dp),
        )

        Spacer(Modifier.weight(1f))

        // ---- 上次结果 chip ----
        if (lastRun != null) {
            LastResultChip(lastRun, onClick = { onOpenLastResult(lastRun.runId) })
        }
        Spacer(Modifier.height(20.dp))
    }
}

@Composable
private fun MiniNavButton(label: String, onClick: () -> Unit) {
    val colors = AnebTheme.colors
    Text(
        text = label,
        fontSize = 12.sp,
        color = colors.muted,
        modifier = Modifier
            .clip(RoundedCornerShape(8.dp))
            .background(colors.surfaceMuted)
            .border(1.dp, colors.hairline, RoundedCornerShape(8.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 6.dp),
    )
}

@Composable
private fun LastResultChip(run: TestRun, onClick: () -> Unit) {
    val colors = AnebTheme.colors
    val score = run.aqsScore
    val grade = score?.let { Grade.fromAqsScore(it) }
    val gradeColor = colors.gradeColor(grade)
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(13.dp))
            .background(colors.surfaceMuted)
            .border(1.dp, colors.hairline, RoundedCornerShape(13.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier.size(34.dp).clip(RoundedCornerShape(9.dp)).background(gradeColor),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = score?.roundToInt()?.toString() ?: "—",
                style = AnebType.StatValue,
                fontSize = 14.sp,
                color = androidx.compose.ui.graphics.Color(0xFF05121A),
            )
        }
        Spacer(Modifier.width(11.dp))
        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.Center) {
            Text(
                "上次：${grade?.labelFriendly ?: "未完成"}",
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
                color = colors.ink,
            )
            Text(
                NetworkLabel.forRun(run),
                fontSize = 11.sp,
                color = colors.muted,
            )
        }
        Text("›", fontSize = 18.sp, color = colors.faint)
    }
}

/** run 网络/时间副标题（"电信 5G SA · 深圳 · 昨天"占位口径；无地理信息只显 transport+时间）。 */
internal object NetworkLabel {
    private val fmt = SimpleDateFormat("MM-dd HH:mm", Locale.US)

    fun forRun(run: TestRun): String {
        val transport = when (run.transport.lowercase()) {
            "wifi" -> "WiFi"
            "cellular" -> "蜂窝"
            else -> "自动"
        }
        return "$transport · ${run.mode} · ${fmt.format(Date(run.startedAtEpochMs))}"
    }
}
