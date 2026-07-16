package com.aneb.probe.ui

import androidx.compose.foundation.background
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.engine.VoiceRunner
import com.aneb.probe.scoring.AqsScorer
import com.aneb.probe.scoring.KpiValue
import com.aneb.probe.ui.theme.AnebTheme
import com.aneb.probe.ui.theme.Grade

/**
 * AI 实时交互（语音）模式屏——[VoiceRunner] 的展示层（PROFILE_FRAMEWORK §4.1）。
 * 与 [SpeedTestScreen]/[HomeScreen] 并列的模式屏。纯展示：数值来自 [VoiceRunner.Sample]
 * （观测口径）；facet4 结论经 [AqsScorer.scoreVoice] 出分（WEIGHTS_VOICE + M1 硬否决）。
 */
@Composable
fun VoiceTestScreen(
    sample: VoiceRunner.Sample?,
    running: Boolean,
    onStart: () -> Unit,
    onCancel: () -> Unit,
) {
    val c = AnebTheme.colors
    val phase = sample?.phase

    val phaseLabel = when (phase) {
        VoiceRunner.Phase.Ping -> "时延基线测量中"
        VoiceRunner.Phase.Uplink -> "上行语音帧发送中（20ms 帧节奏）"
        VoiceRunner.Phase.Downlink -> "下行 TTS 帧流接收中（50fps）"
        VoiceRunner.Phase.Done -> "测量完成"
        null -> if (running) "准备中…" else "点击开始语音双工测量"
    }
    // 主数值：相位相关（Ping→RTT；上/下行→帧计数；Done→口到耳预算）
    val (heroVal, heroUnit) = when (phase) {
        VoiceRunner.Phase.Ping -> (sample.rttMs?.let { "%.0f".format(it) } ?: "—") to "ms RTT"
        VoiceRunner.Phase.Uplink -> "${sample.framesSent}/${VoiceRunner.UPLINK_FRAMES}" to "上行帧"
        VoiceRunner.Phase.Downlink -> "${sample.framesRecv}/${VoiceRunner.DOWNLINK_FRAMES}" to "下行帧"
        VoiceRunner.Phase.Done -> (sample.mouthEarBudgetMs?.let { "%.0f".format(it) } ?: "—") to "ms 口到耳预算"
        null -> "—" to "口到耳预算"
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 12.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(28.dp))
        Text(heroVal, color = c.ink, fontSize = 54.sp, fontWeight = FontWeight.Bold)
        Text(heroUnit, color = c.muted, fontSize = 15.sp)
        Spacer(Modifier.height(8.dp))
        Text(phaseLabel, color = if (phase == VoiceRunner.Phase.Done) c.excellent else c.good, fontSize = 13.sp)

        Spacer(Modifier.height(22.dp))

        // ---- 指标磁贴：RTT / 上行帧抖动 / 下行帧抖动 / 口到耳预算 ----
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            VoiceTile("RTT", sample?.rttMs, "%.0f", "ms", c.good, Modifier.weight(1f))
            VoiceTile("上行帧抖动", sample?.upFrameJitterMs, "%.1f", "ms", c.brand, Modifier.weight(1f))
            VoiceTile("下行帧抖动", sample?.downFrameJitterMs, "%.1f", "ms", c.excellent, Modifier.weight(1f))
            VoiceTile("口到耳预算", sample?.mouthEarBudgetMs, "%.0f", "ms", c.fair, Modifier.weight(1f))
        }

        Spacer(Modifier.height(16.dp))

        // ---- facet4 结论（scoreVoice：WEIGHTS_VOICE + M1>400ms 硬否决）----
        if (phase == VoiceRunner.Phase.Done) {
            VoiceConclusionCard(sample)
        }

        Spacer(Modifier.height(24.dp))

        val btnColor = if (running) c.poor else c.brand
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
                .clip(RoundedCornerShape(16.dp))
                .background(btnColor)
                .clickable { if (running) onCancel() else onStart() },
            contentAlignment = Alignment.Center,
        ) {
            Text(
                if (running) "取消测量" else "GO · 开始语音测量",
                color = Color(0xFF05121A), fontSize = 18.sp, fontWeight = FontWeight.Bold,
            )
        }
        Spacer(Modifier.height(8.dp))
        Text(
            "口径：上行=20ms 帧节奏小包（服务端逐帧到达权威，含客户端调度抖动上界）；下行=50fps 帧流" +
                "（客户端到达间隔）；口到耳=RTT+max(帧抖动)+编解码/缓冲常数 ${VoiceRunner.CODEC_JB_BUDGET_MS.toInt()}ms 的" +
                "网络预算（非真实音频链路）。观测展示，独立出分。",
            color = c.faint,
            fontSize = 11.sp,
        )
    }
}

@Composable
private fun androidx.compose.foundation.layout.RowScope.VoiceTile(
    label: String,
    value: Double?,
    pattern: String,
    unit: String,
    accent: Color,
    modifier: Modifier = Modifier,
) {
    val c = AnebTheme.colors
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(c.surface)
            .padding(vertical = 12.dp, horizontal = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(label, color = c.muted, fontSize = 10.sp)
        Spacer(Modifier.height(4.dp))
        Text(value?.let { pattern.format(it) } ?: "—", color = accent, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        Text(unit, color = c.faint, fontSize = 10.sp)
    }
}

@Composable
private fun VoiceConclusionCard(sample: VoiceRunner.Sample) {
    val c = AnebTheme.colors
    val result = remember(sample) {
        runCatching {
            AqsScorer.scoreVoice(
                n1RttMs = KpiValue(sample.rttMs, "ms", 11, lowConfidence = false),
                n2JitterMs = KpiValue(sample.jitterMs, "ms", 11, lowConfidence = false),
                m1BudgetMs = KpiValue(sample.mouthEarBudgetMs, "ms", 1, lowConfidence = false),
                m2DownFrameJitterMs = KpiValue(sample.downFrameJitterMs, "ms", sample.framesRecv, lowConfidence = false),
                m3UpFrameJitterMs = KpiValue(sample.upFrameJitterMs, "ms", sample.framesSent, lowConfidence = false),
            )
        }.getOrNull()
    } ?: return
    val score = result.score
    val head: Color
    val verdict: String
    if (score == null) {
        head = c.neutral
        verdict = "语音分不可计算（${result.notComputableReason ?: "指标缺失"}）——诚实缺席，不以 0 顶替。"
    } else {
        val grade = Grade.fromAqsScore(score)
        head = c.gradeColor(grade)
        verdict = if (result.vetoApplied) {
            "口到耳预算超 ${AqsScorer.M1_VETO_THRESHOLD_MS.toInt()}ms 红线——对话自然度不可用，分数封顶。"
        } else {
            when (grade.labelFriendly) {
                "优秀" -> "语音双工承载优秀：口到耳预算低、帧流平稳，适合 GPT-Live 式实时对话。"
                "良好" -> "语音双工承载良好：实时对话可用，帧抖动或时延有小幅余量不足。"
                "一般" -> "语音双工承载一般：对话可感延迟/顿挫，弱网时体验波动明显。"
                else -> "语音双工承载不足：口到耳/抖动超预算，实时语音体验受损。"
            }
        }
    }
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(c.surface)
            .padding(14.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("语音体验分", color = head, fontSize = 13.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
            Text(score?.let { "%.1f".format(it) } ?: "—", color = head, fontSize = 22.sp, fontWeight = FontWeight.Bold)
        }
        Spacer(Modifier.height(6.dp))
        Text(verdict, color = c.ink, fontSize = 13.sp)
        Spacer(Modifier.height(8.dp))
        Text(
            "子分 " + result.subScores.entries.joinToString(" · ") { "${it.key} ${"%.0f".format(it.value)}" } +
                "（表 WEIGHTS_VOICE · ${AqsScorer.AQS_VERSION_VOICE}）",
            color = c.muted,
            fontSize = 10.sp,
        )
        Text(
            "帧接收 ${sample.framesRecv}/${VoiceRunner.DOWNLINK_FRAMES}（TCP 重传掩盖真丢帧，仅计数参考）",
            color = c.faint,
            fontSize = 10.sp,
        )
    }
}
