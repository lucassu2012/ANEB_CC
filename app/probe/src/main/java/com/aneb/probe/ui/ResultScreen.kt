package com.aneb.probe.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.data.ScenarioResultEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.radio.GeoTrack
import com.aneb.probe.ui.components.GlassChrome
import com.aneb.probe.ui.components.GradeChip
import com.aneb.probe.ui.components.HalfGauge
import com.aneb.probe.ui.components.KpiBar
import com.aneb.probe.ui.components.ResIcon
import com.aneb.probe.ui.components.SectionLabel
import com.aneb.probe.ui.components.SegmentedControl
import com.aneb.probe.ui.components.StBanner
import com.aneb.probe.ui.components.StGraph
import com.aneb.probe.ui.components.StResItem
import com.aneb.probe.ui.components.StResults
import com.aneb.probe.ui.components.SuiteCard
import com.aneb.probe.ui.components.pressable
import com.aneb.probe.ui.theme.AnebColors
import com.aneb.probe.ui.theme.AnebElevation
import com.aneb.probe.ui.theme.AnebShapes
import com.aneb.probe.ui.theme.AnebTheme
import com.aneb.probe.ui.theme.AnebType
import com.aneb.probe.ui.theme.Grade
import com.aneb.probe.ui.theme.gradeColorByKey
import com.aneb.probe.ui.theme.invalidNeutral
import com.aneb.probe.ui.theme.lowConf
import com.aneb.probe.ui.theme.validityColor
import kotlin.math.roundToInt

/**
 * 结果页（重设计，设计稿 §01 结果双视图）：顶部 简洁/专业 分段控件切换普通/开发者视图。
 * - 普通（[ResultViewMode.Simple]）：脉冲环 + 分数 + 四级中文标签 + [VerdictText] 结论文案
 *   + 三瓦片（响应速度/卡顿/上传）+ 分享成图 + "查看详细数据"切专业；
 * - 开发者（[ResultViewMode.Detailed]）：v2 卡片化取证视图——AQS 头条（真实三组子分并列）
 *   + AQS 子分与权重（组→KPI→贡献分，真实落库子分）+ 分组 KPI 明细 + REACH + 元信息
 *   + 导出 JSON/CSV。
 *
 * 全部数据来自 Room 落库实体（TestEngine 写入口径），本层不重算（D-02 单一事实来源）。
 * AQS 子分为 run 结束时 AqsScorer 已落库的产物（report_body JSON），本层只解析+映射不重算。
 */

// 分级/有效性色统一走 AnebTheme.colors（theme-aware 单一事实源，见 ui/theme/Color.kt）：
// gradeColorByKey / gradeColor(Grade) / validityColor / invalidNeutral / lowConf。
// 不再在本文件私有写死暗色 hex（浅色主题下不跟随的偏差已消除）。

enum class ResultViewMode(val label: String) { Simple("简洁"), Detailed("专业") }

@Composable
fun ResultScreen(
    run: TestRun?,
    scenarios: List<ScenarioResultEntity>,
    reportJson: String?,
    exportStatus: String?,
    onExportJson: () -> Unit,
    onExportCsv: () -> Unit,
    onBack: () -> Unit,
    radio: ResultRadioSummary = ResultRadioSummary.EMPTY,
    latency: ResultLatencySeries = ResultLatencySeries.EMPTY,
    trackSummaries: Map<Long, GeoTrack.Summary> = emptyMap(),
    hasTrack: Boolean = false,
    onExportTrack: () -> Unit = {},
    /** 分享成图：ResultScreen 投影出展示态 Model，实际存图/分享由 Activity 承载（需 Context） */
    onShare: (ShareCard.Model) -> Unit = {},
) {
    val colors = AnebTheme.colors
    val hasReportJson = reportJson != null
    var viewMode by rememberSaveable { mutableStateOf(ResultViewMode.Simple) }

    Column(modifier = Modifier.fillMaxSize().background(colors.background).padding(horizontal = 20.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            BackButton(onBack)
            Spacer(Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text("测试结果", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = colors.ink)
                if (run != null) Text(NetworkLabel.forRun(run), fontSize = 10.5.sp, color = colors.muted)
            }
            SegmentedControl(
                options = ResultViewMode.entries.toList(),
                selected = viewMode,
                onSelect = { viewMode = it },
                label = { it.label },
            )
        }

        if (run == null) {
            Text("run 不存在", color = colors.invalidNeutral, modifier = Modifier.padding(top = 16.dp))
            return
        }

        // 内容层 + 底部玻璃操作区（§4.3/§4.4 chrome-bot）：内容从玻璃条下方滚过，操作区常驻底部。
        Box(modifier = Modifier.fillMaxWidth().weight(1f)) {
            when (viewMode) {
                ResultViewMode.Simple -> SimpleResultView(run = run, scenarios = scenarios)
                ResultViewMode.Detailed -> DetailedResultView(
                    run = run,
                    scenarios = scenarios,
                    reportJson = reportJson,
                    radio = radio,
                    latency = latency,
                    exportStatus = exportStatus,
                    trackSummaries = trackSummaries,
                    hasTrack = hasTrack,
                    onExportTrack = onExportTrack,
                )
            }
            ResultBottomBar(
                viewMode = viewMode,
                onSeeDetails = { viewMode = ResultViewMode.Detailed },
                onShare = { onShare(simpleShareModel(run, scenarios, colors)) },
                onExportJson = onExportJson,
                onExportCsv = onExportCsv,
                exportEnabledJson = hasReportJson,
                exportEnabledCsv = scenarios.isNotEmpty(),
                modifier = Modifier.align(Alignment.BottomCenter),
            )
        }
    }
}

/**
 * 底部玻璃操作区（§4.3 两按钮 查看详细/分享 · §4.4 两按钮 导出 JSON/CSV）——GlassChrome 承载，
 * 内容从其下方滚过。按视图模式切换按钮组。
 */
@Composable
private fun ResultBottomBar(
    viewMode: ResultViewMode,
    onSeeDetails: () -> Unit,
    onShare: () -> Unit,
    onExportJson: () -> Unit,
    onExportCsv: () -> Unit,
    exportEnabledJson: Boolean,
    exportEnabledCsv: Boolean,
    modifier: Modifier = Modifier,
) {
    GlassChrome(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 2.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            when (viewMode) {
                ResultViewMode.Simple -> {
                    ActionButton("查看详细数据", primary = false, modifier = Modifier.weight(1f), onClick = onSeeDetails)
                    ActionButton("分享成绩", primary = true, modifier = Modifier.weight(1f), onClick = onShare)
                }
                ResultViewMode.Detailed -> {
                    ActionButton("导出 JSON", primary = false, enabled = exportEnabledJson, modifier = Modifier.weight(1f), onClick = onExportJson)
                    ActionButton("导出 CSV", primary = false, enabled = exportEnabledCsv, modifier = Modifier.weight(1f), onClick = onExportCsv)
                }
            }
        }
    }
}

/**
 * iOS 风格操作按钮（§4 .btn）：primary=品牌填充白字（+轻抬升）；ghost=幽灵描边 ink 字。
 * 按压反馈走 [pressable]（scale .96 / 减弱动效降级透明度），16 连续圆角。
 */
@Composable
private fun ActionButton(
    text: String,
    primary: Boolean,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    val colors = AnebTheme.colors
    val container = if (primary) colors.brand else colors.surface2
    val fg = if (primary) Color.White else colors.ink
    Box(
        modifier = modifier
            .then(if (primary && enabled) Modifier.shadow(AnebElevation.level2, AnebShapes.button, clip = false) else Modifier)
            .clip(AnebShapes.button)
            .background(if (enabled) container else container.copy(alpha = 0.4f))
            .then(if (!primary) Modifier.border(1.dp, colors.hairline, AnebShapes.button) else Modifier)
            .pressable(onClick = onClick, enabled = enabled)
            .padding(vertical = 13.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text,
            color = if (enabled) fg else fg.copy(alpha = 0.5f),
            fontSize = 14.sp,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
        )
    }
}

// ------------------------------------------------------------------
// 普通用户视图
// ------------------------------------------------------------------

@Composable
private fun SimpleResultView(
    run: TestRun,
    scenarios: List<ScenarioResultEntity>,
) {
    val colors = AnebTheme.colors
    val score = run.aqsScore
    val grade = score?.let { Grade.fromAqsScore(it) }
    val band = colors.gradeColor(grade)
    val rows = ResultFormat.runKpiRows(scenarios).associateBy { it.row.id }

    val t1 = rows["T1"]?.row
    val t3 = rows["T3"]?.row
    val u1 = rows["U1"]?.row

    val verdict = simpleVerdict(run, rows)

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            // 底部留白，让内容从底部玻璃操作区（≈68dp 高）下方滚过而不被压住
            .padding(top = 8.dp, bottom = 88.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // ---- 连接横幅（结果态：分档色点 + 网络副行）----
        StBanner(
            isp = "测试完成",
            sub = NetworkLabel.forRun(run),
            action = "",
            onAction = {},
            dotColor = band,
        )

        Spacer(Modifier.height(20.dp))

        // ---- 180° 半盘 + 中心 60px 大分 / 分档 / Agent 体验分 ----
        HalfGauge(
            fraction = ((score?.toFloat() ?: 0f) / 100f),
            band = band,
            modifier = Modifier.fillMaxWidth().aspectRatio(1.8f),
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    score?.roundToInt()?.toString() ?: "—",
                    style = AnebType.DisplayScore,
                    fontSize = 60.sp,
                    color = band,
                )
                Text(grade?.labelFriendly ?: "未完成", fontSize = 15.sp, fontWeight = FontWeight.SemiBold, color = band)
                Spacer(Modifier.height(2.dp))
                Text("Agent 体验分", fontSize = 11.sp, color = colors.muted)
            }
        }

        Spacer(Modifier.height(14.dp))
        // ---- 结论句（关键结论小句分档色加粗）----
        Text(
            verdictAnnotated(verdict, band, colors.ink),
            fontSize = 14.5.sp,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(horizontal = 4.dp),
            textAlign = TextAlign.Center,
        )

        Spacer(Modifier.height(18.dp))
        // ---- 结果大数字行（响应←T1 / 上传←U1 / 卡顿←T3，各带优良可差角标）----
        StResults(
            items = listOf(
                StResItem(
                    icon = ResIcon.Down,
                    name = "响应",
                    value = t1?.value?.let { "${it.roundToInt()}" } ?: "—",
                    unit = if (t1?.value != null) "ms" else "",
                    grade = Grade.fromKey(t1?.grade),
                ),
                StResItem(
                    icon = ResIcon.Up,
                    name = "上传",
                    value = u1?.value?.let { "%.1f".format(it) } ?: "—",
                    unit = if (u1?.value != null) "Mbps" else "",
                    grade = Grade.fromKey(u1?.grade),
                ),
                StResItem(
                    icon = ResIcon.Stall,
                    name = "卡顿",
                    value = stallTileValue(t3?.value),
                    unit = "",
                    grade = Grade.fromKey(t3?.grade),
                ),
            ),
        )
    }
}

/**
 * 结论句着色：主结论小句（首个破折号「——」之前的判断词，如"很适合 AI 助手"/"能用但会卡"）
 * 染分档色 + 加粗，其余正文走 [ink]。无破折号（不可计算话术）时整句走正文，不强加分档色。
 */
private fun verdictAnnotated(verdict: String, accent: Color, ink: Color) = buildAnnotatedString {
    val sep = "——"
    val idx = verdict.indexOf(sep)
    if (idx > 0) {
        withStyle(SpanStyle(color = accent, fontWeight = FontWeight.Bold)) {
            append(verdict.substring(0, idx))
        }
        withStyle(SpanStyle(color = ink)) { append(verdict.substring(idx)) }
    } else {
        withStyle(SpanStyle(color = ink)) { append(verdict) }
    }
}

private fun stallTileValue(t3Rate: Double?): String = when {
    t3Rate == null -> "—"
    t3Rate <= 0.0 -> "0"
    else -> "%.1f%%".format(t3Rate * 100)
}

/** 结论文案（普通视图展示 + 分享卡共用，确定性同源，无重算差异）。 */
private fun simpleVerdict(run: TestRun, rows: Map<String, ResultFormat.RunKpiRow>): String =
    VerdictText.generate(
        VerdictText.Input(
            score = run.aqsScore,
            lowConfidence = run.aqsLowConfidence == true,
            vetoApplied = run.aqsVetoApplied == true,
            notComputableReason = run.aqsNotComputableReason ?: run.status,
            kpiGrades = rows.values.associate { it.row.id to Grade.fromKey(it.row.grade) },
        ),
    )

/**
 * run+scenarios → 分享卡 Model（底部"分享成绩"按钮用；与展示态同源，零重算差异）。
 * [colors] 由 composable 调用点注入：分享卡走 Canvas 绘制（脱离主题），故在此按当前主题取语义色再 toArgb。
 */
private fun simpleShareModel(
    run: TestRun,
    scenarios: List<ScenarioResultEntity>,
    colors: AnebColors,
): ShareCard.Model {
    val rows = ResultFormat.runKpiRows(scenarios).associateBy { it.row.id }
    val grade = run.aqsScore?.let { Grade.fromAqsScore(it) }
    return buildShareModel(
        run = run,
        verdict = simpleVerdict(run, rows),
        grade = grade,
        colors = colors,
        t1 = rows["T1"]?.row,
        t3 = rows["T3"]?.row,
        u1 = rows["U1"]?.row,
    )
}

/** 结果展示态 → 分享卡 Model（按当前主题 [colors] 取语义色 argb，零重算）。 */
private fun buildShareModel(
    run: TestRun,
    verdict: String,
    grade: Grade?,
    colors: AnebColors,
    t1: ResultFormat.KpiRow?,
    t3: ResultFormat.KpiRow?,
    u1: ResultFormat.KpiRow?,
): ShareCard.Model {
    fun argb(g: String?): Int = colors.gradeColorByKey(g).toArgb()
    val gradeArgb = colors.gradeColor(grade).toArgb()
    return ShareCard.Model(
        score = run.aqsScore?.roundToInt(),
        gradeLabel = grade?.labelFriendly ?: "未完成",
        gradeColorArgb = gradeArgb,
        verdict = verdict,
        tiles = listOf(
            ShareCard.Model.Tile(
                t1?.value?.let { "${it.roundToInt()}ms" } ?: "—", "响应速度", argb(t1?.grade),
            ),
            ShareCard.Model.Tile(stallTileValue(t3?.value), "卡顿", argb(t3?.grade)),
            ShareCard.Model.Tile(
                u1?.value?.let { "%.1f".format(it) } ?: "—", "上传 Mbps", argb(u1?.grade),
            ),
        ),
        networkLine = NetworkLabel.forRun(run),
    )
}

// ------------------------------------------------------------------
// 专业视图（v2：卡片化取证视图 — 真实 AQS 子分 + 分组 KPI 明细 + REACH + 元信息）
//   · AQS 子分为 AqsScorer 落库子分（report_body JSON）真实分解，非分级近似（D-02 不重算）
//   · 分组/权重/门限一律引用测量层单一事实源，展示层只映射（红线 §2.3）
// ------------------------------------------------------------------

@Composable
private fun DetailedResultView(
    run: TestRun,
    scenarios: List<ScenarioResultEntity>,
    reportJson: String?,
    radio: ResultRadioSummary,
    latency: ResultLatencySeries,
    exportStatus: String?,
    trackSummaries: Map<Long, GeoTrack.Summary>,
    hasTrack: Boolean,
    onExportTrack: () -> Unit,
) {
    // 真实子分分解（落库上报体 JSON），一次解析记忆化；不可计算/无上报体 → null
    val breakdown = remember(reportJson) { ResultAqsBreakdown.fromReportJson(reportJson) }
    // v0.2 并列分解（run.aqs_v02，D-26）；无 continuity 数据 → null（正常 run 不显示）
    val breakdownV02 = remember(reportJson) { ResultAqsBreakdown.v02FromReportJson(reportJson) }
    // Token facet4 结论（run.aqs_token，D-29）；旧 run 无节点 → null（不渲染）
    val tokenConclusion = remember(reportJson) { ResultAqsBreakdown.tokenConclusionFromReportJson(reportJson) }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(top = 4.dp, bottom = 88.dp),
    ) {
        item { AqsHeadlineCard(run, breakdown, scenarios) }
        item { LatencySection(latency) }
        item { AqsBreakdownSection(run, breakdown, scenarios) }
        breakdownV02?.let { bd -> item { AqsV02BreakdownSection(bd) } }
        tokenConclusion?.let { tc -> item { TokenConclusionSection(tc) } }
        item { KpiDetailSection(run, scenarios) }
        item { RadioSection(radio) }
        item { ReachSection(run) }
        item { MetaSection(run, scenarios, exportStatus, hasTrack, onExportTrack, reportJson != null) }
        if (scenarios.isNotEmpty()) {
            item { SectionLabel("场景明细", trailing = "${scenarios.size} 场景") }
            items(count = scenarios.size, key = { i -> scenarios[i].id }) { i ->
                SuiteCard(modifier = Modifier.padding(top = 8.dp)) {
                    ScenarioCard(scenarios[i], trackSummaries[scenarios[i].id])
                }
            }
        }
        item { ClaimScopeFooter(run) }
    }
}

// ---- AQS 头条卡（大分 + 分档 + 置信 + 三组子分并列 R-28 + claim scope）----

@Composable
private fun AqsHeadlineCard(
    run: TestRun,
    breakdown: ResultAqsBreakdown.Breakdown?,
    scenarios: List<ScenarioResultEntity>,
) {
    val colors = AnebTheme.colors
    SuiteCard(modifier = Modifier.padding(top = 4.dp)) {
        val score = run.aqsScore
        if (score != null) {
            val grade = Grade.fromAqsScore(score)
            val band = colors.gradeColor(grade)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("%.1f".format(score), style = AnebType.DisplayScore, fontSize = 46.sp, color = band)
                Spacer(Modifier.width(14.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text("${grade.labelFriendly} · AQS", fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = band)
                    Text(NetworkLabel.forRun(run), fontSize = 11.sp, color = colors.muted)
                    Text("agent-qoe-kpi · ${run.kpiSet}", fontSize = 10.sp, color = colors.faint)
                }
                ConfidenceChip(run)
            }
            // R-28：AQS 数字旁必须并列三大组子分。真实子分（落库上报体）优先；
            // 无上报体（早退/落库失败）时降级为分级近似，明确标注，绝不留空。
            Spacer(Modifier.height(12.dp))
            if (breakdown != null) {
                GroupSubscoreRow(breakdown)
            } else {
                ApproxGroupSubscoreRow(scenarios)
                Text(
                    "子分为分级近似（本 run 无落库上报体）",
                    fontSize = 9.5.sp, color = colors.faint, modifier = Modifier.padding(top = 4.dp),
                )
            }
            if (run.aqsVetoApplied == true) {
                Spacer(Modifier.height(8.dp))
                InlineBadge("T4 一票否决生效 · AQS 封顶 54", colors.poor, colors.poorSoft)
            }
            if (run.aqsLowConfidence == true) {
                Spacer(Modifier.height(8.dp))
                InlineBadge("⚠ ${ResultFormat.LOW_CONFIDENCE_LABEL} · 证据不完整，本分数仅供参考", colors.lowConf, colors.fairSoft)
            }
        } else {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("—", style = AnebType.DisplayScore, fontSize = 46.sp, color = colors.invalidNeutral)
                Spacer(Modifier.width(14.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text("AQS 不可计算", fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = colors.invalidNeutral)
                    Text(run.aqsNotComputableReason ?: run.status ?: "unknown", fontSize = 11.sp, color = colors.muted)
                }
                ConfidenceChip(run)
            }
        }
        // AQS v0.2 并列出分（若有连续性数据）
        ResultFormat.aqsV02Lines(run)?.let { lines ->
            Spacer(Modifier.height(10.dp))
            HorizontalDivider(color = colors.hairline)
            Spacer(Modifier.height(8.dp))
            Text(lines[0], fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = colors.ink)
            Text(lines[1], fontSize = 10.5.sp, fontFamily = FontFamily.Monospace, color = colors.muted)
        }
        Spacer(Modifier.height(10.dp))
        ClaimScopeChip(run)
    }
}

/** 置信状态胶囊（借鉴 Codex 语义：有效 / 低置信 / 不可计算——分数可信度一目了然）。 */
@Composable
private fun ConfidenceChip(run: TestRun) {
    val colors = AnebTheme.colors
    val (text, fg, bg) = when {
        run.aqsScore == null -> Triple("不可计算", colors.invalidNeutral, colors.neutral.copy(alpha = 0.12f))
        run.aqsLowConfidence == true -> Triple("低置信", colors.lowConf, colors.fairSoft)
        else -> Triple("有效", colors.excellent, colors.excellentSoft)
    }
    Text(
        text,
        color = fg,
        fontSize = 10.5.sp,
        fontWeight = FontWeight.Bold,
        modifier = Modifier.clip(AnebShapes.xs).background(bg).padding(horizontal = 8.dp, vertical = 4.dp),
    )
}

/** 三大组子分并列（R-28：AQS 数字旁必须同时给出流式/上行/基线子分），真实落库子分。 */
@Composable
private fun GroupSubscoreRow(breakdown: ResultAqsBreakdown.Breakdown) {
    val colors = AnebTheme.colors
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
        breakdown.groups.forEach { g ->
            val normalized = if (g.maxPoints > 0) g.subtotalPoints / g.maxPoints * 100.0 else 0.0
            GroupChip(
                label = g.label,
                band = colors.gradeColor(Grade.fromAqsScore(normalized)),
                valueText = "%.1f".format(g.subtotalPoints),
                subText = "/ ${g.maxPoints.roundToInt()}",
                modifier = Modifier.weight(1f),
            )
        }
    }
}

/**
 * 三大组子分的**分级近似**并列（R-28 降级路径：run 无落库上报体、真实子分不可得时）。
 * 每组取成员 KPI 分级的桶均值（优 1.0 / 良 .75 / 可 .5 / 差 .25），映射回四级标签——
 * 明确近似、绝不冒充落库子分（D-02）；缺量 KPI 不参与均值（R-10 不以 0 顶替）。
 */
@Composable
private fun ApproxGroupSubscoreRow(scenarios: List<ScenarioResultEntity>) {
    val colors = AnebTheme.colors
    val rows = ResultFormat.runKpiRows(scenarios).associateBy { it.row.id }
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
        ResultAqsBreakdown.GROUP_KPI_IDS_V01.forEach { (label, ids) ->
            val buckets = ids.mapNotNull { id -> Grade.fromKey(rows[id]?.row?.grade)?.let { gradeBucket(it) } }
            if (buckets.isEmpty()) {
                GroupChip(label, colors.neutral, "—", "近似", Modifier.weight(1f))
            } else {
                val g = Grade.fromAqsScore(buckets.average() * 100.0)
                GroupChip(label, colors.gradeColor(g), g.labelCn, "近似", Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun GroupChip(label: String, band: Color, valueText: String, subText: String, modifier: Modifier = Modifier) {
    val colors = AnebTheme.colors
    Column(
        modifier = modifier.clip(AnebShapes.sm).background(colors.surface2).padding(horizontal = 9.dp, vertical = 8.dp),
    ) {
        Text(label, fontSize = 9.5.sp, color = colors.muted, maxLines = 1)
        Spacer(Modifier.height(3.dp))
        Row(verticalAlignment = Alignment.Bottom) {
            Text(valueText, style = AnebType.StatValue, fontSize = 16.sp, color = band)
            Text(" $subText", fontSize = 10.sp, color = colors.faint, modifier = Modifier.padding(bottom = 1.dp))
        }
    }
}

/** 分级 → 近似占比桶（优 1.0 / 良 .75 / 可 .5 / 差 .25）；仅用于无落库子分时的分级近似。 */
private fun gradeBucket(grade: Grade): Double = when (grade) {
    Grade.Excellent -> 1.0
    Grade.Good -> 0.75
    Grade.Fair -> 0.5
    Grade.Poor -> 0.25
}

/** claim scope 胶囊（R-28：分数旁标注测量口径 + 节点，避免被误读为全网结论）。 */
@Composable
private fun ClaimScopeChip(run: TestRun) {
    val colors = AnebTheme.colors
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(
            "claim: to_probe_node",
            fontSize = 10.sp,
            fontWeight = FontWeight.SemiBold,
            color = colors.muted,
            modifier = Modifier.clip(AnebShapes.xs).background(colors.surface2).padding(horizontal = 8.dp, vertical = 4.dp),
        )
        Text("节点 ${nodeLabel(run.serverBase)}", fontSize = 10.sp, color = colors.faint, fontFamily = FontFamily.Monospace)
    }
}

private fun nodeLabel(serverBase: String): String =
    serverBase.substringAfter("://", serverBase).trimEnd('/')

@Composable
private fun InlineBadge(text: String, fg: Color, bg: Color) {
    Text(
        text,
        color = fg,
        fontSize = 12.sp,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier.fillMaxWidth().clip(AnebShapes.sm).background(bg).padding(horizontal = 10.dp, vertical = 7.dp),
    )
}

// ---- 流式时延剖面（ITL 时序迷你图；展示态，非 KPI T2 精确口径）----

@Composable
private fun LatencySection(latency: ResultLatencySeries) {
    val colors = AnebTheme.colors
    Column {
        SectionLabel(
            "流式时延剖面",
            trailing = if (latency.hasSeries) latency.sourceLabel else "无 token 时序",
        )
        SuiteCard {
            if (!latency.hasSeries) {
                Text("本 run 无足够 token 时序样本", fontSize = 12.sp, color = colors.invalidNeutral)
            } else {
                val peak = latency.peakMs ?: 1.0
                // 归一化 0..1（StGraph 口径），峰值=1.0；折线尖峰即卡顿
                val points = latency.itlMs.map { (it / peak).toFloat().coerceIn(0f, 1f) }
                StGraph(
                    title = "Token 间隔时延 (ms)",
                    nowValue = "峰值 ${peak.roundToInt()} ms",
                    points = points,
                    band = colors.good,
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    "P95 ${latency.p95Ms?.let { "${it.roundToInt()} ms" } ?: "—"} · " +
                        "中位 ${latency.medianMs?.let { "${it.roundToInt()} ms" } ?: "—"} · " +
                        "卡顿线 ${ResultLatencySeries.STALL_MS.roundToInt()}ms / 严重 ${ResultLatencySeries.SEVERE_STALL_MS.roundToInt()}ms",
                    fontSize = 10.sp, color = colors.faint,
                )
            }
        }
    }
}

// ---- AQS 子分与权重（组→KPI→贡献分，真实落库子分；无子分回退分级近似）----

// ---- Token facet4 结论卡（行为特征 + 网络建议，D-29；PROFILE_FRAMEWORK §2.5）----

/**
 * 从 `run.aqs_token` 落库数据派生结论：[TokenScoringBridge.classifyAndRecommend]
 * （双证据分类 + facet2 良锚建议行）。D-02：只消费落库子分 × 权重表单一事实源，不重算打分。
 */
@Composable
private fun TokenConclusionSection(tc: ResultAqsBreakdown.TokenConclusionInput) {
    val colors = AnebTheme.colors
    val result = remember(tc) {
        runCatching {
            TokenScoringBridge.classifyAndRecommend(
                TestModeProfiles.TOKEN_EXPERIENCE, tc.subScores, pureText = false, workload = tc.workload,
            )
        }.getOrNull()
    } ?: return
    val (findings, lines) = result
    if (findings.isEmpty()) return

    SectionLabel("行为特征与网络建议", trailing = "Token · ${tc.weightsTableId.removePrefix("WEIGHTS_TOKEN_")}")
    SuiteCard(modifier = Modifier.padding(top = 8.dp)) {
        findings.forEachIndexed { i, f ->
            if (i > 0) Spacer(Modifier.height(10.dp))
            val tagLabel = when (f.tag.name) {
                "UPLINK_BURST" -> "上行突发需求"
                "LOW_LATENCY" -> "低时延需求"
                "DOWNLINK_BANDWIDTH" -> "下行大带宽需求"
                else -> "稳定性需求"
            }
            val ok = f.satisfiedByNetwork
            val band = if (ok) colors.excellent else colors.poor
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(tagLabel, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = colors.ink, modifier = Modifier.weight(1f))
                Text(if (ok) "已满足" else "未满足", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = band)
            }
            Text(f.triggerEvidence, fontSize = 10.sp, color = colors.faint)
            Text(
                "绑定 ${f.bindingKpis.joinToString("/")} · 约束占比 ${"%.0f".format(f.intensity * 100)}%",
                fontSize = 10.sp, color = colors.muted,
            )
        }
        // S1 会话完成率（D-33 实测外显；旧 run 无字段不渲染，R-10）——BM-06 门限着色 99/97/95
        tc.s1Rate?.let { rate ->
            Spacer(Modifier.height(12.dp))
            val s1Band = when {
                tc.s1VetoApplied -> colors.poor
                rate >= 0.99 -> colors.excellent
                rate >= 0.97 -> colors.good
                rate >= 0.95 -> colors.fair
                else -> colors.poor
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("会话完成率 S1", fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = colors.ink, modifier = Modifier.weight(1f))
                Text(
                    "%.0f%%".format(rate * 100) + (tc.s1Rounds?.let { " · $it 轮" } ?: ""),
                    fontSize = 11.sp, fontWeight = FontWeight.Bold, color = s1Band,
                )
            }
            if (tc.s1VetoApplied) {
                Text(
                    "完成率触发软否决，总分已封顶（<95%→70 / <90%→54）",
                    fontSize = 10.sp, color = colors.poor,
                )
            }
        }
        if (lines.isNotEmpty()) {
            Spacer(Modifier.height(12.dp))
            Text("建议 SLA（良级门限 · 达 95%）", fontSize = 11.sp, fontWeight = FontWeight.SemiBold, color = colors.muted)
            Spacer(Modifier.height(4.dp))
            lines.forEach { line -> Text(line, fontSize = 11.sp, color = colors.ink) }
        }
        Spacer(Modifier.height(10.dp))
        val caliber = buildString {
            append("由落库工作量与子分派生（不重算打分）。")
            if (tc.subScoresFromFallback) append("Token 表出分待 D1（download_burst）接入，暂以 v0.1 子分分类；")
            tc.notComputableReason?.let { append("token_score=$it") }
        }
        Text(caliber, fontSize = 9.5.sp, color = colors.faint)
    }
}

@Composable
private fun AqsBreakdownSection(
    run: TestRun,
    breakdown: ResultAqsBreakdown.Breakdown?,
    scenarios: List<ScenarioResultEntity>,
) {
    val colors = AnebTheme.colors
    Column {
        SectionLabel("AQS 子分与权重", trailing = if (breakdown != null) "组→KPI→贡献分" else "分级近似")
        SuiteCard {
            when {
                breakdown != null -> breakdown.groups.forEachIndexed { i, g ->
                    if (i > 0) Spacer(Modifier.height(10.dp))
                    AqsGroupBlock(g)
                }
                run.aqsScore != null -> {
                    Text(
                        "无落库子分，以下为分级近似（优 1.0 / 良 .75 / 可 .5 / 差 .25）",
                        fontSize = 10.5.sp, color = colors.faint, modifier = Modifier.padding(bottom = 6.dp),
                    )
                    ApproxSubScoreBars(scenarios)
                }
                else -> Text("AQS 不可计算，无子分可展示", fontSize = 12.sp, color = colors.invalidNeutral)
            }
        }
    }
}

@Composable
private fun AqsGroupBlock(group: ResultAqsBreakdown.Group) {
    val colors = AnebTheme.colors
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = 4.dp)) {
        Text(
            "${group.label} · ${(group.weight * 100).roundToInt()}%",
            fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = colors.ink,
            modifier = Modifier.weight(1f),
        )
        Text(
            "${"%.1f".format(group.subtotalPoints)} / ${group.maxPoints.roundToInt()} 分",
            style = AnebType.StatValue, fontSize = 11.sp, color = colors.muted,
        )
    }
    group.kpis.forEach { AqsContribRow(it) }
}

@Composable
private fun AqsContribRow(kpi: ResultAqsBreakdown.KpiContribution) {
    val colors = AnebTheme.colors
    val band = colors.gradeColor(Grade.fromKey(kpi.gradeKey))
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 4.dp)) {
        Text(
            "${kpi.label} · ${(kpi.weight * 100).roundToInt()}%",
            fontSize = 11.sp, color = colors.muted, modifier = Modifier.width(96.dp),
        )
        Spacer(Modifier.width(8.dp))
        Box(
            modifier = Modifier.weight(1f).height(6.dp).clip(RoundedCornerShape(999.dp)).background(colors.surfaceMuted),
        ) {
            Box(
                Modifier
                    .fillMaxHeight()
                    .fillMaxWidth((kpi.subScore / 100.0).toFloat().coerceIn(0f, 1f))
                    .clip(RoundedCornerShape(999.dp))
                    .background(band),
            )
        }
        Spacer(Modifier.width(8.dp))
        Column(horizontalAlignment = Alignment.End, modifier = Modifier.width(66.dp)) {
            Text("%.1f".format(kpi.subScore), style = AnebType.StatValue, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = colors.ink)
            Text("${"%.1f".format(kpi.contributionPoints)}分", style = AnebType.StatValue, fontSize = 9.5.sp, color = colors.faint)
        }
    }
}

/**
 * 分级近似子分横条（无落库子分时的回退：早退/旧行/无上报体）。明确标注非精确子分，
 * 语义近似（优 1.0 / 良 .75 / 可 .5 / 差 .25 / 缺失 0），避免展示层重算 AqsScorer（D-02）。
 */
@Composable
private fun ApproxSubScoreBars(scenarios: List<ScenarioResultEntity>) {
    val weights = listOf(
        "T1" to "20%", "T3" to "20%", "T2" to "15%",
        "U1" to "15%", "U2" to "10%", "N1" to "10%", "N2" to "10%",
    )
    val rows = ResultFormat.runKpiRows(scenarios).associateBy { it.row.id }
    weights.forEach { (id, w) ->
        val r = rows[id]?.row
        val grade = Grade.fromKey(r?.grade)
        // 缺量 KPI（grade=null）→ 无填充（R-10：不以 0 顶替失败样本），值仍显 "—"
        val frac = grade?.let { gradeBucket(it).toFloat() } ?: 0f
        KpiBar(
            label = "$id $w",
            fraction = frac,
            grade = grade,
            valueText = r?.let { ResultFormat.gradeLabel(it.grade) } ?: "—",
        )
    }
}

/**
 * AQS v0.2 并列分解卡（阶段二：v0.1×0.8 + 连续性 20%）。仅当有 continuity 数据、
 * 上报体含 run.aqs_v02 时显示（D-26）；v0.1 仍为头条主分，此卡为并列补充。
 */
@Composable
private fun AqsV02BreakdownSection(breakdown: ResultAqsBreakdown.Breakdown) {
    val colors = AnebTheme.colors
    Column {
        SectionLabel(
            "AQS v0.2 子分（含连续性）",
            trailing = breakdown.score?.let { "= %.1f".format(it) } ?: "不可计算",
        )
        SuiteCard {
            Text(
                "阶段二口径：v0.1 各组 ×0.8 + 连续性 20%（C1 会话中断 / C2 切换恢复）",
                fontSize = 10.sp, color = colors.faint, modifier = Modifier.padding(bottom = 6.dp),
            )
            breakdown.groups.forEachIndexed { i, g ->
                if (i > 0) Spacer(Modifier.height(10.dp))
                AqsGroupBlock(g)
            }
        }
    }
}

// ---- KPI 明细（分组 T/N/U/C，值 + 分级 chip + 低置信；双口径并列）----

@Composable
private fun KpiDetailSection(run: TestRun, scenarios: List<ScenarioResultEntity>) {
    val byId = ResultFormat.runKpiRows(scenarios).associateBy { it.row.id }
    Column {
        SectionLabel("KPI 明细", trailing = "N←S1 / T·U2←S2 / U1←S3")
        SuiteCard {
            KpiGroupBlock("流式体验 T", listOf("T1", "T2", "T2_incl_coalesced", "T3", "T3_incl_resume", "T4"), byId)
            KpiGroupBlock("网络基线 N", listOf("N1", "N2"), byId)
            KpiGroupBlock("上行突发 U", listOf("U1", "U1_excl_slow_start", "U2"), byId)
            ContinuityDetailBlock(run)
        }
    }
}

@Composable
private fun KpiGroupBlock(title: String, ids: List<String>, byId: Map<String, ResultFormat.RunKpiRow>) {
    val colors = AnebTheme.colors
    val rows = ids.mapNotNull { byId[it] }
    if (rows.isEmpty()) return
    Text(
        title,
        fontSize = 10.5.sp, fontWeight = FontWeight.SemiBold, color = colors.faint,
        modifier = Modifier.padding(top = 8.dp, bottom = 2.dp),
    )
    rows.forEach { RunKpiRowLine(it) }
}

/** 连续性 C 组明细（AQS v0.2；来自 TestRun 既有列，复用 aqsV02Lines 同源格式化）。 */
@Composable
private fun ContinuityDetailBlock(run: TestRun) {
    val lines = ResultFormat.aqsV02Lines(run) ?: return
    val colors = AnebTheme.colors
    Text(
        "连续性 C（AQS v0.2）",
        fontSize = 10.5.sp, fontWeight = FontWeight.SemiBold, color = colors.faint,
        modifier = Modifier.padding(top = 8.dp, bottom = 2.dp),
    )
    Text(lines[0], fontSize = 12.sp, color = colors.ink)
    Text(lines[1], fontSize = 10.5.sp, fontFamily = FontFamily.Monospace, color = colors.muted)
}

@Composable
private fun RunKpiRowLine(r: ResultFormat.RunKpiRow) = KpiLine(r.row, prefix = "[${r.source}] ")

@Composable
internal fun KpiLine(row: ResultFormat.KpiRow, prefix: String = "") {
    val colors = AnebTheme.colors
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 3.dp)) {
        Box(
            modifier = Modifier.width(6.dp).height(28.dp)
                .background(if (row.value == null) colors.invalidNeutral else colors.gradeColorByKey(row.grade)),
        )
        Spacer(Modifier.width(8.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text("$prefix${row.id} ${row.label}", fontSize = 12.sp, color = colors.ink)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    ResultFormat.formatValue(row),
                    fontSize = 13.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace,
                    color = colors.ink,
                )
                Spacer(Modifier.width(8.dp))
                GradeChip(Grade.fromKey(row.grade))
                if (row.lowConfidence) {
                    Spacer(Modifier.width(8.dp))
                    Text(ResultFormat.LOW_CONFIDENCE_LABEL, fontSize = 11.sp, color = colors.lowConf)
                }
            }
        }
    }
}

// ---- 无线层 R（制式三元组 R-15 + 注册小区 + 信号中位数；协变量，不进 AQS）----

@Composable
private fun RadioSection(radio: ResultRadioSummary) {
    val colors = AnebTheme.colors
    Column {
        SectionLabel(
            "无线层 R",
            trailing = if (radio.hasSamples) {
                "${radio.registeredCount}/${radio.sampleCount} 注册 · ${radio.staleCount} 陈旧"
            } else {
                "无样本"
            },
        )
        SuiteCard {
            if (!radio.hasSamples) {
                Text("本 run 无无线层样本（模拟器 / 无 SIM / 权限缺失）", fontSize = 12.sp, color = colors.invalidNeutral)
            } else {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                    DataCell(
                        "制式（设备报告）", radio.ratLabel ?: "—", Modifier.weight(1f),
                        valueColor = if (radio.ratLabel != null) colors.excellent else null,
                    )
                    DataCell("RSRP", radio.rsrpDbm?.let { "$it dBm" } ?: "—", Modifier.weight(1f))
                }
                Spacer(Modifier.height(7.dp))
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                    DataCell("SINR", radio.sinrDb?.let { "$it dB" } ?: "—", Modifier.weight(1f))
                    DataCell("PCI / TAC", cellIdText(radio.pci, radio.tac), Modifier.weight(1f))
                }
                Spacer(Modifier.height(8.dp))
                // R-15：协商/显示/nr 态三元组分列原样呈现（"设备报告制式"，非运营商全网结论）
                Text(
                    "设备报告制式：net=${radio.networkType ?: "—"} · override=${radio.overrideType ?: "—"} · nr=${radio.nrState ?: "—"}" +
                        (radio.arfcn?.let { " · arfcn=$it" } ?: "") +
                        (radio.rsrqDb?.let { " · rsrq=$it dB" } ?: ""),
                    fontSize = 10.sp, fontFamily = FontFamily.Monospace, color = colors.faint,
                )
            }
        }
    }
}

@Composable
private fun DataCell(label: String, value: String, modifier: Modifier = Modifier, valueColor: Color? = null) {
    val colors = AnebTheme.colors
    Column(
        modifier = modifier.clip(AnebShapes.sm).background(colors.surface2).padding(horizontal = 10.dp, vertical = 9.dp),
    ) {
        Text(label, fontSize = 9.5.sp, color = colors.muted, maxLines = 1)
        Spacer(Modifier.height(4.dp))
        Text(value, style = AnebType.StatValue, fontSize = 13.sp, color = valueColor ?: colors.ink, maxLines = 1)
    }
}

private fun cellIdText(pci: Int?, tac: Int?): String =
    if (pci == null && tac == null) "—" else "${pci?.toString() ?: "—"} / ${tac?.toString() ?: "—"}"

// ---- REACH 连接可达性（候选，不进 AQS；bare-IP × SNI 双通道握手）----

@Composable
private fun ReachSection(run: TestRun) {
    val colors = AnebTheme.colors
    Column {
        SectionLabel("连接可达性 REACH", trailing = "候选 · 不进 AQS")
        SuiteCard(padding = 0.dp) {
            ReachRowV2("bare-IP 通道", run.ipReachable, run.ipReachMs)
            HorizontalDivider(color = colors.hairline)
            ReachRowV2("SNI 域名通道", run.sniReachable, run.sniReachMs)
        }
        if (run.sniReachable == null && run.ipReachable == null) {
            Text(
                "（本 run 未做 SNI 双通道探测）",
                fontSize = 10.5.sp, color = colors.faint, modifier = Modifier.padding(top = 4.dp, start = 4.dp),
            )
        }
    }
}

@Composable
private fun ReachRowV2(label: String, result: String?, ms: Long?) {
    val colors = AnebTheme.colors
    val (stateText, stateColor, iconGlyph) = when {
        result == null -> Triple("未探测", colors.faint, "·")
        result == "ok" -> Triple("OK", colors.excellent, "✓")
        result == "rst" -> Triple("RST", colors.poor, "✕")
        result == "timeout" -> Triple("超时", colors.lowConf, "!")
        else -> Triple(result.uppercase(), colors.lowConf, "!")
    }
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier.width(28.dp).height(28.dp).clip(AnebShapes.xs).background(stateColor.copy(alpha = 0.16f)),
            contentAlignment = Alignment.Center,
        ) { Text(iconGlyph, color = stateColor, fontSize = 13.sp, fontWeight = FontWeight.Bold) }
        Spacer(Modifier.width(10.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(label, fontSize = 12.5.sp, fontWeight = FontWeight.Medium, color = colors.ink)
            Text(
                when {
                    result == null -> "—"
                    result == "ok" -> "握手成功 · ${ms?.let { "$it ms" } ?: "—"}"
                    else -> "握手失败 · $stateText"
                },
                fontSize = 10.5.sp, color = colors.muted,
            )
        }
        Text(stateText, fontSize = 12.sp, fontWeight = FontWeight.Bold, color = stateColor)
    }
}

// ---- 连接与元信息（transport / 协商地址 / drift / 版本 / 轨迹导出 / 导出状态）----

@Composable
private fun MetaSection(
    run: TestRun,
    scenarios: List<ScenarioResultEntity>,
    exportStatus: String?,
    hasTrack: Boolean,
    onExportTrack: () -> Unit,
    hasReportJson: Boolean,
) {
    val colors = AnebTheme.colors
    val s = scenarios.firstOrNull()
    Column {
        SectionLabel("连接与元信息")
        SuiteCard {
            MetaLine("run", run.runId)
            MetaLine("mode · transport", "${run.mode} · ${run.transport}")
            MetaLine("status · report", "${run.status ?: "?"} · ${run.reportStatus ?: "—"}")
            if (s != null) {
                MetaLine("场景 transport", s.netTransport ?: "—")
                MetaLine("协商地址", s.serverObservedAddr ?: "—")
                MetaLine(
                    "offset drift",
                    (s.offsetDriftPpm?.let { "%.2f ppm".format(it) } ?: "—") + (if (s.offsetSuspect) " (suspect)" else ""),
                )
                ResultFormat.bufferingLabel(s)?.let { MetaLine("批化标注", it) }
            }
            MetaLine("版本", "kpi=${run.kpiSet} aqs=${run.aqsVersion} schema=${run.schemaVersion}")
            if (hasTrack) {
                Spacer(Modifier.height(8.dp))
                ActionButton("导出轨迹", primary = false, onClick = onExportTrack)
            }
            if (!hasReportJson) {
                Spacer(Modifier.height(6.dp))
                Text("该 run 未生成上报体（早退/失败），JSON 不可导出", fontSize = 10.5.sp, color = colors.invalidNeutral)
            }
            exportStatus?.let {
                Spacer(Modifier.height(6.dp))
                Text(it, fontSize = 10.sp, fontFamily = FontFamily.Monospace, color = colors.invalidNeutral)
            }
        }
    }
}

@Composable
private fun MetaLine(k: String, v: String) {
    val colors = AnebTheme.colors
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
        Text(k, fontSize = 11.sp, color = colors.muted, modifier = Modifier.width(104.dp))
        Text(v, fontSize = 11.sp, color = colors.ink, fontFamily = FontFamily.Monospace, modifier = Modifier.weight(1f))
    }
}

// ---- 场景明细卡（复用既有 KpiLine，全量单场景 KPI）----

@Composable
private fun ScenarioCard(s: ScenarioResultEntity, track: GeoTrack.Summary?) {
    val colors = AnebTheme.colors
    Column(modifier = Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(modifier = Modifier.width(10.dp).height(10.dp).background(colors.validityColor(s.validity)))
            Spacer(Modifier.width(6.dp))
            Text("${s.profileId}#${s.repeatIndex} (${s.profileVersion})", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = colors.ink)
            Spacer(Modifier.width(8.dp))
            Text(s.validity, fontSize = 12.sp, color = colors.validityColor(s.validity))
        }
        if (s.validity == "invalid") {
            Text(
                "无效原因: ${s.invalidReasons.ifEmpty { "unknown" }}（KPI 已抑制，原始事件保留）",
                fontSize = 11.sp, color = colors.invalidNeutral,
            )
        }
        Text(
            "漂移率 drift=${s.offsetDriftPpm?.let { "%.2f ppm".format(it) } ?: "—"}" +
                (if (s.offsetSuspect) " (offset_suspect)" else "") +
                "  net=${s.netTransport ?: "—"}  addr=${s.serverObservedAddr ?: "—"}",
            fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = colors.muted,
        )
        ResultFormat.bufferingLabel(s)?.let {
            Text(it, fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = colors.invalidNeutral)
        }
        if (track != null && track.points > 0) {
            Text(
                "轨迹 ${track.points} 点  起终点距离 " +
                    (track.startEndMeters?.let { "%.1f m".format(it) } ?: "—（<2 点）"),
                fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = colors.muted,
            )
        }
        ResultFormat.kpiRows(s).forEach { KpiLine(it) }
    }
}

@Composable
private fun ClaimScopeFooter(run: TestRun) {
    val colors = AnebTheme.colors
    Column(modifier = Modifier.padding(top = 16.dp, bottom = 24.dp)) {
        HorizontalDivider(color = colors.hairline)
        Text(ResultFormat.CLAIM_SCOPE_TEXT, fontSize = 11.sp, color = colors.invalidNeutral, modifier = Modifier.padding(top = 6.dp))
        Text(ResultFormat.AQS_DISCLAIMER_TEXT, fontSize = 11.sp, color = colors.invalidNeutral)
        Text("AQS 口径 to_probe_node · 更换节点会改变本分数", fontSize = 11.sp, color = colors.invalidNeutral)
        Text(
            "kpi_set=${run.kpiSet} aqs=${run.aqsVersion} schema=${run.schemaVersion} profiles=${run.profileVersions}",
            fontSize = 10.sp, fontFamily = FontFamily.Monospace, color = colors.invalidNeutral,
        )
    }
}
