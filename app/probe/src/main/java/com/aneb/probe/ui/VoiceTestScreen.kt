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
import androidx.compose.foundation.layout.width
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
import com.aneb.probe.data.VoiceResultEntity
import com.aneb.probe.engine.VoiceRunner
import com.aneb.probe.scoring.AqsScorer
import com.aneb.probe.scoring.KpiValue
import com.aneb.probe.ui.theme.AnebTheme
import com.aneb.probe.ui.theme.Grade
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

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
    contSample: VoiceRunner.Sample? = null,
    contRunning: Boolean = false,
    onStartContinuity: () -> Unit = {},
    onCancelContinuity: () -> Unit = {},
    /** 最近落库的语音记录（D-42），新→旧；空=无历史（不占位） */
    recentVoice: List<VoiceResultEntity> = emptyList(),
) {
    val c = AnebTheme.colors
    val phase = sample?.phase

    val phaseLabel = when (phase) {
        VoiceRunner.Phase.Ping -> "时延基线测量中"
        VoiceRunner.Phase.Uplink -> "上行语音帧发送中（20ms 帧节奏）"
        VoiceRunner.Phase.Downlink -> "下行 TTS 帧流接收中（50fps）"
        VoiceRunner.Phase.Handshake -> "实时会话建立中（WebSocket）"
        VoiceRunner.Phase.Turns -> "多轮语音对话仿真中（8 轮·含打断）"
        VoiceRunner.Phase.Done -> "测量完成"
        null -> if (running) "准备中…" else "点击开始语音双工测量"
    }
    // 主数值：相位相关（Ping→RTT；上/下行→帧计数；Turns→轮次帧计数；Done→口到耳）
    val (heroVal, heroUnit) = when (phase) {
        VoiceRunner.Phase.Ping -> (sample.rttMs?.let { "%.0f".format(it) } ?: "—") to "ms RTT"
        VoiceRunner.Phase.Uplink -> "${sample.framesSent}/${VoiceRunner.UPLINK_FRAMES}" to "上行帧"
        VoiceRunner.Phase.Downlink -> "${sample.framesRecv}/${VoiceRunner.DOWNLINK_FRAMES}" to "下行帧"
        VoiceRunner.Phase.Handshake -> "…" to "会话建立"
        VoiceRunner.Phase.Turns -> "${sample.framesRecv}" to "下行帧（${sample.turnsOk} 轮 OK）"
        VoiceRunner.Phase.Done ->
            ((sample.mouthEarProxyMs ?: sample.mouthEarBudgetMs)?.let { "%.0f".format(it) } ?: "—") to
                (if (sample.mouthEarProxyMs != null) "ms 口到耳(实测代理)" else "ms 口到耳预算")
        null -> "—" to "口到耳"
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

        // ---- 连续性 mini-run 卡（受控断连，D-41 预定；独立结论，不并入语音分）----
        VoiceContinuityCard(
            s = contSample,
            running = contRunning,
            voiceRunning = running,
            onStart = onStartContinuity,
            onCancel = onCancelContinuity,
        )

        Spacer(Modifier.height(16.dp))

        // ---- facet4 结论（scoreVoice：WEIGHTS_VOICE + M1>400ms 硬否决）----
        if (phase == VoiceRunner.Phase.Done) {
            VoiceConclusionCard(sample)
        }

        // ---- 最近语音记录（D-42）：只展示落库实测值，不重算分 ----
        if (recentVoice.isNotEmpty()) {
            Spacer(Modifier.height(16.dp))
            RecentVoiceSection(recentVoice)
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

/**
 * 连续性 mini-run 卡（受控断连，D-41 预定；镜像 SpeedTestScreen.RecoveryCard 卡型）：
 * 服务端受控 WS 硬关（能力合同 §2）≠真实蜂窝断网；单次事件，观测口径，不进任何分，
 * 恒 LOW/INCONCLUSIVE；与跨网迁移恢复（D-23）严格分口径。
 */
@Composable
private fun VoiceContinuityCard(
    s: VoiceRunner.Sample?,
    running: Boolean,
    voiceRunning: Boolean,
    onStart: () -> Unit,
    onCancel: () -> Unit,
) {
    val c = AnebTheme.colors
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(c.surface)
            .padding(14.dp),
    ) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("连续性 mini-run（受控断连）", color = c.muted, fontSize = 13.sp, fontWeight = FontWeight.Bold)
            if (s?.phase == VoiceRunner.Phase.Done) {
                val complete = s.continuityDetectMs != null && s.continuityResumeMs != null
                Text(
                    if (complete) "完成" else "部分缺席",
                    color = if (complete) c.excellent else c.neutral,
                    fontSize = 13.sp, fontWeight = FontWeight.Bold,
                )
            }
        }
        Spacer(Modifier.height(8.dp))
        when {
            s == null && !running -> Text(
                "服务端受控 WS 硬关（能力合同 §2）：轮 1 跑完、其 turn_summary 发出后裸关 TCP，" +
                    "测断连检出与新会话重建时长。单次事件，观测口径，不进任何分；与跨网迁移恢复(D-23)口径分开。",
                color = c.faint, fontSize = 11.sp,
            )
            running && s?.phase != VoiceRunner.Phase.Done -> {
                val phaseLabel = when (s?.phase) {
                    VoiceRunner.Phase.Handshake -> "断连会话建立中…"
                    VoiceRunner.Phase.Turns ->
                        if (s.continuityDetectMs != null) "已检出断连，重建新会话中…"
                        else "轮次运行中（收帧 ${s.framesRecv}）…"
                    else -> "准备中…"
                }
                Text(phaseLabel, color = c.good, fontSize = 12.sp)
                s?.continuityDetectMs?.let {
                    Text("检出 %.0f ms".format(it), color = c.ink, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                }
            }
            s?.phase == VoiceRunner.Phase.Done -> {
                Text(
                    "检出 ${s.continuityDetectMs?.let { "%.0f ms".format(it) } ?: "—"} · " +
                        "重建 ${s.continuityResumeMs?.let { "%.0f ms".format(it) } ?: "—"} · " +
                        "LOW/INCONCLUSIVE（单次受控事件）",
                    color = c.ink, fontSize = 13.sp,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    "服务端受控 WS 硬关≠真实蜂窝断网；与跨网迁移恢复(D-23)口径分开",
                    color = c.faint, fontSize = 10.sp,
                )
            }
        }
        Spacer(Modifier.height(10.dp))
        val btnColor = when {
            running -> c.poor
            voiceRunning -> c.surfaceMuted
            else -> c.brand
        }
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(40.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(btnColor)
                .clickable(enabled = !voiceRunning) { if (running) onCancel() else onStart() },
            contentAlignment = Alignment.Center,
        ) {
            Text(
                if (running) "取消连续性子测" else "触发连续性 mini-run",
                color = if (voiceRunning) c.faint else Color(0xFF05121A),
                fontSize = 14.sp, fontWeight = FontWeight.Bold,
            )
        }
    }
}

/**
 * 最近语音记录（D-42）：时间 + 口径 + 口到耳值，只展示 [VoiceResultEntity] 落库实测值，
 * 不重算分。口到耳优先 v2 实测代理 [VoiceResultEntity.mouthEarProxyMs]，缺失退 v1 预算
 * [VoiceResultEntity.mouthEarBudgetMs]，均无记 —（R-10 诚实缺席）。
 */
@Composable
private fun RecentVoiceSection(records: List<VoiceResultEntity>) {
    val c = AnebTheme.colors
    val fmt = remember { SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()) }
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(c.surface)
            .padding(14.dp),
    ) {
        Text("最近语音记录", color = c.muted, fontSize = 12.sp, fontWeight = FontWeight.Bold)
        records.forEach { r ->
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(fmt.format(Date(r.tsEpochMs)), color = c.ink, fontSize = 12.sp, modifier = Modifier.weight(1f))
                Text(
                    if (r.caliber == VoiceRunner.SIM_CALIBER) "server-sim" else "paced-proxy",
                    color = c.faint,
                    fontSize = 10.sp,
                )
                Spacer(Modifier.width(10.dp))
                val mouthEar = r.mouthEarProxyMs ?: r.mouthEarBudgetMs
                Text(
                    mouthEar?.let { "%.0f ms".format(it) } ?: "—",
                    color = c.ink,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
    }
}

@Composable
private fun VoiceConclusionCard(sample: VoiceRunner.Sample) {
    val c = AnebTheme.colors
    val result = remember(sample) {
        runCatching {
            if (sample.caliber == VoiceRunner.SIM_CALIBER) {
                // v2 server-sim 口径（D-38）：M1'=口到耳实测代理、M2'=sched_us 剥离纯传输抖动、
                // M4/M5/M6 实测；lowConfidence 透传（上行背压）
                AqsScorer.scoreVoiceSim(
                    n1RttMs = KpiValue(sample.rttMs, "ms", 11, lowConfidence = sample.lowConfidence),
                    n2JitterMs = KpiValue(sample.jitterMs, "ms", 11, lowConfidence = false),
                    m1MouthEarProxyMs = KpiValue(sample.mouthEarProxyMs, "ms", sample.turnsOk, lowConfidence = sample.lowConfidence),
                    m2DownNetJitterMs = KpiValue(sample.downNetJitterMs, "ms", sample.framesRecv, lowConfidence = false),
                    m3UpFrameJitterMs = KpiValue(sample.upFrameJitterMs, "ms", sample.framesSent, lowConfidence = sample.lowConfidence),
                    m4TtfbMs = KpiValue(sample.ttfbP50Ms, "ms", sample.turnsOk, lowConfidence = false),
                    m5TurnSwitchMs = KpiValue(sample.turnSwitchP50Ms, "ms", (sample.turnsOk - 1).coerceAtLeast(0), lowConfidence = false),
                    m6BargeStopMs = KpiValue(sample.bargeStopMaxMs, "ms", 2, lowConfidence = false),
                )
            } else {
                AqsScorer.scoreVoice(
                    n1RttMs = KpiValue(sample.rttMs, "ms", 11, lowConfidence = false),
                    n2JitterMs = KpiValue(sample.jitterMs, "ms", 11, lowConfidence = false),
                    m1BudgetMs = KpiValue(sample.mouthEarBudgetMs, "ms", 1, lowConfidence = false),
                    m2DownFrameJitterMs = KpiValue(sample.downFrameJitterMs, "ms", sample.framesRecv, lowConfidence = false),
                    m3UpFrameJitterMs = KpiValue(sample.upFrameJitterMs, "ms", sample.framesSent, lowConfidence = false),
                )
            }
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
        // 表名由 aqsVersion 派生，不再按 caliber 另算一遍：这两个字段并排印给用户，各算各的就会
        // 逐字打架（v0.2 出分却印 v0.1 的表名）。aqsVersion 是落库产物，表名可由它推出 → 取它为准
        // （D-02：展示层只消费落库产物）。查不到即印 "?"，不猜——未知版本印一个像样的表名，
        // 比印问号危险得多。
        val tableName = AqsScorer.VOICE_WEIGHTS_TABLE_BY_VERSION[result.aqsVersion] ?: "?"
        Text(
            "子分 " + result.subScores.entries.joinToString(" · ") { "${it.key} ${"%.0f".format(it.value)}" } +
                "（表 $tableName · ${result.aqsVersion}）",
            color = c.muted,
            fontSize = 10.sp,
        )
        Text(
            if (sample.caliber == VoiceRunner.SIM_CALIBER)
                "帧接收 ${sample.framesRecv} · ${sample.turnsOk} 轮 protocol_ok（emitted 对账口径）"
            else
                "帧接收 ${sample.framesRecv}/${VoiceRunner.DOWNLINK_FRAMES}（TCP 重传掩盖真丢帧，仅计数参考）",
            color = c.faint,
            fontSize = 10.sp,
        )
    }
}
