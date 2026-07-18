package com.aneb.probe.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.data.AdapterObsEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.data.VoiceResultEntity
import com.aneb.probe.engine.VoiceRunner
import com.aneb.probe.ui.components.GradeChip
import com.aneb.probe.ui.components.pressable
import com.aneb.probe.ui.theme.AnebElevation
import com.aneb.probe.ui.theme.AnebShapes
import com.aneb.probe.ui.theme.AnebTheme
import com.aneb.probe.ui.theme.AnebType
import com.aneb.probe.ui.theme.Grade
import com.aneb.probe.ui.theme.lowConf
import com.aneb.probe.ui.theme.onGrade
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.roundToInt

/**
 * 历史混排条目（历史页统一展示）：TestRun / 语音记录 / 观察记录按时间降序混入同一列表。
 * key 全列表唯一——run 用 runId，语音用 "voice-{id}"，观察用 "obs-{id}"（LazyColumn key 合同）。
 */
sealed interface HistoryEntry {
    /** LazyColumn key（全列表唯一） */
    val key: String
    /** 排序时刻（epoch ms，降序混排依据） */
    val epochMs: Long

    data class Run(val run: TestRun) : HistoryEntry {
        override val key: String get() = run.runId
        override val epochMs: Long get() = run.startedAtEpochMs
    }

    data class Voice(val result: VoiceResultEntity) : HistoryEntry {
        override val key: String get() = "voice-${result.id}"
        override val epochMs: Long get() = result.tsEpochMs
    }

    data class Adapter(val obs: AdapterObsEntity) : HistoryEntry {
        override val key: String get() = "obs-${obs.id}"
        override val epochMs: Long get() = obs.tsEpochMs
    }
}

/** 历史页混排纯函数（抽出 Composable 便于单测）。 */
object HistoryFeed {
    /**
     * TestRun + 语音记录 + 观察记录按时间降序合成混合列表。
     * sortedByDescending 稳定：同刻条目保持拼接序（run → 语音 → 观察）、各自输入相对序（key 仍唯一）。
     */
    fun merge(
        runs: List<TestRun>,
        voice: List<VoiceResultEntity>,
        adapterObs: List<AdapterObsEntity> = emptyList(),
    ): List<HistoryEntry> =
        (runs.map { HistoryEntry.Run(it) } +
            voice.map { HistoryEntry.Voice(it) } +
            adapterObs.map { HistoryEntry.Adapter(it) })
            .sortedByDescending { it.epochMs }
}

/**
 * 历史页（重设计，设计稿 §历史，iOS 化）：Room TestRun 列表——每行 grade 色分数徽标（tabular）
 * + iOS soft grade chip + 时间/模式/传输 + 状态；点击进对应结果页，整卡按压缩放。
 * 历史统一展示：语音记录（[VoiceResultEntity]）与 TestRun 按时间降序混排；语音行只展示
 * 落库实测值、无详情页不可点击（D-02 不重算分）。数据全部来自 Room（本层不重算）。
 * LazyColumn key 保留唯一（run=runId，语音="voice-{id}"）。
 */
@Composable
fun HistoryScreen(
    runs: List<TestRun>,
    onOpen: (String) -> Unit,
    onGenerateReport: () -> Unit,
    onBack: () -> Unit,
    voiceResults: List<VoiceResultEntity> = emptyList(),
    adapterObs: List<AdapterObsEntity> = emptyList(),
) {
    val colors = AnebTheme.colors
    val fmt = SimpleDateFormat("MM-dd HH:mm", Locale.US)
    val entries = HistoryFeed.merge(runs, voiceResults, adapterObs)
    Column(modifier = Modifier.fillMaxSize().background(colors.background).padding(horizontal = 20.dp)) {
        Spacer(Modifier.height(8.dp))
        GlassHeader("测试历史 (${entries.size})", onBack) {
            Text(
                text = "生成报告",
                fontSize = 12.5.sp,
                fontWeight = FontWeight.SemiBold,
                color = colors.brand2,
                modifier = Modifier
                    .clip(AnebShapes.pill)
                    .background(colors.surfaceMuted)
                    .border(1.dp, colors.hairline, AnebShapes.pill)
                    .then(Modifier.pressable(onClick = onGenerateReport))
                    .padding(horizontal = 12.dp, vertical = 7.dp),
            )
        }
        if (entries.isEmpty()) {
            Text("暂无历史记录", color = colors.muted, modifier = Modifier.padding(top = 24.dp))
        }
        LazyColumn(
            modifier = Modifier.weight(1f).fillMaxWidth(),
            contentPadding = PaddingValues(top = 10.dp, bottom = 16.dp),
        ) {
            items(count = entries.size, key = { i -> entries[i].key }) { i ->
                when (val entry = entries[i]) {
                    is HistoryEntry.Run -> HistoryRow(entry.run, fmt, onOpen)
                    is HistoryEntry.Voice -> VoiceHistoryRow(entry.result, fmt)
                    is HistoryEntry.Adapter -> AdapterHistoryRow(entry.obs, fmt)
                }
            }
        }
    }
}

@Composable
private fun HistoryRow(run: TestRun, fmt: SimpleDateFormat, onOpen: (String) -> Unit) {
    val colors = AnebTheme.colors
    val score = run.aqsScore
    val grade = score?.let { Grade.fromAqsScore(it) }
    val gradeColor = colors.gradeColor(grade)
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 5.dp)
            .shadow(AnebElevation.level1, AnebShapes.card, clip = false)
            .clip(AnebShapes.card)
            .background(colors.surface)
            .border(1.dp, colors.hairline, AnebShapes.card)
            .then(Modifier.pressable(onClick = { onOpen(run.runId) }))
            .padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier.size(44.dp).clip(AnebShapes.tile).background(gradeColor),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                score?.roundToInt()?.toString() ?: "—",
                style = AnebType.StatValue,
                fontSize = 17.sp,
                // 徽标底色为分级色：文字反色按底色亮度择近黑/近白，保证深浅主题对比（token 化）。
                color = colors.onGrade(grade),
            )
        }
        Spacer(Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    grade?.labelFriendly ?: "未完成",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = if (grade != null) gradeColor else colors.muted,
                )
                if (grade != null) {
                    Spacer(Modifier.width(7.dp))
                    GradeChip(grade)
                }
                if (run.aqsLowConfidence == true) {
                    Spacer(Modifier.width(6.dp))
                    LowConfChip()
                }
            }
            Text(
                "${fmt.format(Date(run.startedAtEpochMs))} · ${run.mode} · ${run.transport}",
                fontSize = 11.5.sp,
                color = colors.muted,
                modifier = Modifier.padding(top = 2.dp),
            )
            Text(
                "status=${run.status ?: "?"} report=${run.reportStatus ?: "—"}",
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                color = colors.faint,
            )
        }
        Text("›", fontSize = 20.sp, color = colors.faint)
    }
}

/**
 * 语音记录历史行（镜像 [HistoryRow] 卡型，不可点击——语音无结果详情页）：
 * 时间 + 「语音」标签 + 口径（[VoiceRunner.SIM_CALIBER]→server-sim，否则 paced-proxy）
 * + 口到耳值（优先 [VoiceResultEntity.mouthEarProxyMs]，缺退 [VoiceResultEntity.mouthEarBudgetMs]，
 * 均无显 —，R-10 诚实缺席）+ lowConfidence 色注。只展示落库实测值，不重算分（D-02）。
 */
@Composable
private fun VoiceHistoryRow(result: VoiceResultEntity, fmt: SimpleDateFormat) {
    val colors = AnebTheme.colors
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 5.dp)
            .shadow(AnebElevation.level1, AnebShapes.card, clip = false)
            .clip(AnebShapes.card)
            .background(colors.surface)
            .border(1.dp, colors.hairline, AnebShapes.card)
            .padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier.size(44.dp).clip(AnebShapes.tile).background(colors.surfaceMuted),
            contentAlignment = Alignment.Center,
        ) {
            Text("语音", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = colors.brand2)
        }
        Spacer(Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    if (result.caliber == VoiceRunner.SIM_CALIBER) "server-sim" else "paced-proxy",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = colors.ink,
                )
                if (result.lowConfidence) {
                    Spacer(Modifier.width(6.dp))
                    LowConfChip()
                }
            }
            Text(
                fmt.format(Date(result.tsEpochMs)),
                fontSize = 11.5.sp,
                color = colors.muted,
                modifier = Modifier.padding(top = 2.dp),
            )
        }
        val mouthEar = result.mouthEarProxyMs ?: result.mouthEarBudgetMs
        Text(
            "口到耳 " + (mouthEar?.let { "%.0f ms".format(it) } ?: "—"),
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            color = colors.ink,
        )
    }
}

/**
 * 观察记录历史行（镜像 [VoiceHistoryRow] 卡型，不可点击——观察无结果详情页）：
 * [AdapterObsEntity.appLabel]（豆包/DeepSeek 友好名，缺退 pkg）+「AI体验」标签 + 关键值
 * （TTFT 簇代理 [AdapterObsEntity.ttftClusterMs] 优先，缺退首增量 [AdapterObsEntity.firstDeltaMs]，
 * 均无显 —，R-10 诚实缺席）+ cadence 副行 + 恒 LOW/INCONCLUSIVE（观察口径红线）色注。
 * 只展示落库实测值，不重算（D-02）；观察=端到端体验代理≠网络口径。
 */
@Composable
private fun AdapterHistoryRow(obs: AdapterObsEntity, fmt: SimpleDateFormat) {
    val colors = AnebTheme.colors
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 5.dp)
            .shadow(AnebElevation.level1, AnebShapes.card, clip = false)
            .clip(AnebShapes.card)
            .background(colors.surface)
            .border(1.dp, colors.hairline, AnebShapes.card)
            .padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier.size(44.dp).clip(AnebShapes.tile).background(colors.surfaceMuted),
            contentAlignment = Alignment.Center,
        ) {
            Text("AI体验", fontSize = 10.5.sp, fontWeight = FontWeight.Bold, color = colors.brand2)
        }
        Spacer(Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    obs.appLabel ?: obs.pkg,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = colors.ink,
                )
                // 观察模式恒 LOW/INCONCLUSIVE（规格 PENDING-VALIDATION 撤销前口径红线）
                Spacer(Modifier.width(6.dp))
                LowConfChip()
            }
            Text(
                "${fmt.format(Date(obs.tsEpochMs))} · AI体验",
                fontSize = 11.5.sp,
                color = colors.muted,
                modifier = Modifier.padding(top = 2.dp),
            )
            Text(
                "cadence " + (obs.cadenceP50Ms?.let { "%.0f ms".format(it) } ?: "—"),
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                color = colors.faint,
            )
        }
        // 关键值：TTFT 簇代理优先，缺退观察启动→首增量（均无显 —，R-10）
        val ttft = obs.ttftClusterMs ?: obs.firstDeltaMs?.toDouble()
        Text(
            "TTFT " + (ttft?.let { "%.0f ms".format(it) } ?: "—"),
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            color = colors.ink,
        )
    }
}

/** 低置信 soft chip（iOS 柔和底角标；沿用结果页 fair 语义色）。 */
@Composable
private fun LowConfChip() {
    val colors = AnebTheme.colors
    Text(
        text = "低置信",
        fontSize = 10.sp,
        fontWeight = FontWeight.Bold,
        color = colors.lowConf,
        modifier = Modifier
            .clip(AnebShapes.xs)
            .background(colors.fairSoft)
            .padding(horizontal = 6.dp, vertical = 3.dp),
    )
}
