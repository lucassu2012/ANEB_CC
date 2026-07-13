package com.aneb.probe.ui

import androidx.compose.foundation.background
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.data.ScenarioResultEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.engine.KpiGrading
import com.aneb.probe.radio.GeoTrack
import com.aneb.probe.ui.components.GaugeMode
import com.aneb.probe.ui.components.GradeChip
import com.aneb.probe.ui.components.KpiBar
import com.aneb.probe.ui.components.PulseGauge
import com.aneb.probe.ui.components.SectionLabel
import com.aneb.probe.ui.components.SegmentedControl
import com.aneb.probe.ui.components.StatTile
import com.aneb.probe.ui.theme.AnebTheme
import com.aneb.probe.ui.theme.Grade
import kotlin.math.roundToInt

/**
 * 结果页（重设计，设计稿 §01 结果双视图）：顶部 简洁/专业 分段控件切换普通/开发者视图。
 * - 普通（[ResultViewMode.Simple]）：脉冲环 + 分数 + 四级中文标签 + [VerdictText] 结论文案
 *   + 三瓦片（响应速度/卡顿/上传）+ 分享成图 + "查看详细数据"切专业；
 * - 开发者（[ResultViewMode.Detailed]）：全量 KPI 明细表（双口径）+ REACH 矩阵 + 连接信息
 *   + 导出 JSON/CSV。
 *
 * 全部数据来自 Room 落库实体（TestEngine 写入口径），本层不重算（D-02 单一事实来源）。
 */

// 四级分级色（专业视图 KPI 明细用；INVALID/缺失灰）——HistoryScreen 亦复用这些内部常量
internal val GRADE_COLORS: Map<String, Color> = mapOf(
    KpiGrading.EXCELLENT to Color(0xFF2FD98A),
    KpiGrading.GOOD to Color(0xFF35B7F0),
    KpiGrading.FAIR to Color(0xFFF6A821),
    KpiGrading.POOR to Color(0xFFF5566B),
)
internal val COLOR_INVALID = Color(0xFF8792A6)
internal val COLOR_LOWCONF = Color(0xFFF6A821)

internal fun gradeColor(grade: String?): Color = GRADE_COLORS[grade] ?: COLOR_INVALID

internal fun validityColor(validity: String): Color = when (validity) {
    "valid" -> Color(0xFF2FD98A)
    "valid_low_confidence" -> COLOR_LOWCONF
    else -> COLOR_INVALID
}

enum class ResultViewMode(val label: String) { Simple("简洁"), Detailed("专业") }

@Composable
fun ResultScreen(
    run: TestRun?,
    scenarios: List<ScenarioResultEntity>,
    hasReportJson: Boolean,
    exportStatus: String?,
    onExportJson: () -> Unit,
    onExportCsv: () -> Unit,
    onBack: () -> Unit,
    trackSummaries: Map<Long, GeoTrack.Summary> = emptyMap(),
    hasTrack: Boolean = false,
    onExportTrack: () -> Unit = {},
    /** 分享成图：ResultScreen 投影出展示态 Model，实际存图/分享由 Activity 承载（需 Context） */
    onShare: (ShareCard.Model) -> Unit = {},
) {
    val colors = AnebTheme.colors
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
            Text("run 不存在", color = COLOR_INVALID, modifier = Modifier.padding(top = 16.dp))
            return
        }

        when (viewMode) {
            ResultViewMode.Simple -> SimpleResultView(
                run = run,
                scenarios = scenarios,
                onSeeDetails = { viewMode = ResultViewMode.Detailed },
                onShare = onShare,
            )
            ResultViewMode.Detailed -> DetailedResultView(
                run = run,
                scenarios = scenarios,
                hasReportJson = hasReportJson,
                exportStatus = exportStatus,
                onExportJson = onExportJson,
                onExportCsv = onExportCsv,
                trackSummaries = trackSummaries,
                hasTrack = hasTrack,
                onExportTrack = onExportTrack,
            )
        }
    }
}

// ------------------------------------------------------------------
// 普通用户视图
// ------------------------------------------------------------------

@Composable
private fun SimpleResultView(
    run: TestRun,
    scenarios: List<ScenarioResultEntity>,
    onSeeDetails: () -> Unit,
    onShare: (ShareCard.Model) -> Unit,
) {
    val colors = AnebTheme.colors
    val score = run.aqsScore
    val grade = score?.let { Grade.fromAqsScore(it) }
    val rows = ResultFormat.runKpiRows(scenarios).associateBy { it.row.id }

    val t1 = rows["T1"]?.row
    val t3 = rows["T3"]?.row
    val u1 = rows["U1"]?.row

    val verdict = VerdictText.generate(
        VerdictText.Input(
            score = score,
            lowConfidence = run.aqsLowConfidence == true,
            vetoApplied = run.aqsVetoApplied == true,
            notComputableReason = run.aqsNotComputableReason ?: run.status,
            kpiGrades = rows.values.associate { it.row.id to Grade.fromKey(it.row.grade) },
        ),
    )

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        PulseGauge(
            mode = GaugeMode.Result,
            grade = grade,
            score = score?.roundToInt(),
            progress = (score?.toFloat() ?: 0f) / 100f,
        )
        Spacer(Modifier.height(14.dp))
        Text(
            verdict,
            fontSize = 14.5.sp,
            color = colors.ink,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(horizontal = 4.dp),
            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
        )
        Spacer(Modifier.height(16.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            StatTile(
                value = t1?.value?.let { "${it.roundToInt()}" } ?: "—",
                unit = if (t1?.value != null) "ms" else "",
                label = "响应速度",
                grade = Grade.fromKey(t1?.grade),
                modifier = Modifier.weight(1f),
            )
            StatTile(
                value = stallTileValue(t3?.value),
                label = "卡顿",
                grade = Grade.fromKey(t3?.grade),
                modifier = Modifier.weight(1f),
            )
            StatTile(
                value = u1?.value?.let { "%.1f".format(it) } ?: "—",
                label = "上传 Mbps",
                grade = Grade.fromKey(u1?.grade),
                modifier = Modifier.weight(1f),
            )
        }
        Spacer(Modifier.height(18.dp))
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(9.dp)) {
            OutlinedButton(onClick = onSeeDetails, modifier = Modifier.weight(1f)) {
                Text("查看详细数据")
            }
            Button(
                onClick = {
                    onShare(
                        buildShareModel(run, verdict, grade, t1, t3, u1),
                    )
                },
                modifier = Modifier.weight(1f),
            ) { Text("分享成绩") }
        }
    }
}

private fun stallTileValue(t3Rate: Double?): String = when {
    t3Rate == null -> "—"
    t3Rate <= 0.0 -> "0"
    else -> "%.1f%%".format(t3Rate * 100)
}

/** 结果展示态 → 分享卡 Model（在 composable 内取语义色 argb，零重算）。 */
private fun buildShareModel(
    run: TestRun,
    verdict: String,
    grade: Grade?,
    t1: ResultFormat.KpiRow?,
    t3: ResultFormat.KpiRow?,
    u1: ResultFormat.KpiRow?,
): ShareCard.Model {
    fun argb(g: String?): Int = (GRADE_COLORS[g] ?: COLOR_INVALID).toArgb()
    val gradeArgb = (grade?.let { GRADE_COLORS[it.key] } ?: COLOR_INVALID).toArgb()
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
// 开发者视图（原 P1-C07 全量内容 + REACH 矩阵 + 连接信息）
// ------------------------------------------------------------------

@Composable
private fun DetailedResultView(
    run: TestRun,
    scenarios: List<ScenarioResultEntity>,
    hasReportJson: Boolean,
    exportStatus: String?,
    onExportJson: () -> Unit,
    onExportCsv: () -> Unit,
    trackSummaries: Map<Long, GeoTrack.Summary>,
    hasTrack: Boolean,
    onExportTrack: () -> Unit,
) {
    LazyColumn(modifier = Modifier.fillMaxSize()) {
        item { AqsHeadline(run) }
        item { AqsSubScoreBars(scenarios) }
        item { ReachMatrix(run) }
        item { ConnectionInfo(scenarios) }
        item { RunMeta(run) }
        item {
            SectionLabel("KPI 总表（AQS 输入映射：N←S1 / T,U2←S2 / U1←S3）")
            Column { ResultFormat.runKpiRows(scenarios).forEach { RunKpiRowLine(it) } }
        }
        item { SectionLabel("场景明细") }
        items(count = scenarios.size, key = { i -> scenarios[i].id }) { i ->
            ScenarioCard(scenarios[i], trackSummaries[scenarios[i].id])
        }
        item {
            SectionLabel("导出")
            Row {
                Button(enabled = hasReportJson, onClick = onExportJson) { Text("导出 JSON") }
                Spacer(Modifier.width(8.dp))
                Button(enabled = scenarios.isNotEmpty(), onClick = onExportCsv) { Text("导出 CSV") }
                Spacer(Modifier.width(8.dp))
                Button(enabled = hasTrack, onClick = onExportTrack) { Text("导出轨迹") }
            }
            if (!hasReportJson) {
                Text(
                    "该 run 未生成上报体（早退/失败），JSON 不可导出",
                    fontSize = 11.sp, color = COLOR_INVALID,
                )
            }
            exportStatus?.let { Text(it, fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = COLOR_INVALID) }
        }
        item { ClaimScopeFooter(run) }
    }
}

/**
 * AQS 子分横条：用 run 级 KPI（AqsInputMapper 映射视图）的分级 + 权重标注渲染。
 * 横条填充按分级色语义呈现（值不是 0–100 子分——子分需 AqsScorer，不落 Room；此处以
 * 分级映射为主，避免展示层重算 AqsScorer 内部子分，D-02）。T4 否决在头条已标注。
 */
@Composable
private fun AqsSubScoreBars(scenarios: List<ScenarioResultEntity>) {
    val weights = mapOf(
        "T1" to "20%", "T3" to "20%", "T2" to "15%", "U1" to "15%",
        "U2" to "10%", "N1" to "10%", "N2" to "10%",
    )
    val rows = ResultFormat.runKpiRows(scenarios).associateBy { it.row.id }
    SectionLabel("AQS 子分与权重")
    weights.forEach { (id, w) ->
        val r = rows[id]?.row
        val grade = Grade.fromKey(r?.grade)
        // 分级 → 条填充占比（优 1.0 / 良 0.75 / 可 0.5 / 差 0.25 / 缺失 0），语义近似非精确子分
        val frac = when (grade) {
            Grade.Excellent -> 1.0f
            Grade.Good -> 0.75f
            Grade.Fair -> 0.5f
            Grade.Poor -> 0.25f
            null -> 0f
        }
        KpiBar(
            label = "$id $w",
            fraction = frac,
            grade = grade,
            valueText = r?.let { ResultFormat.gradeLabel(it.grade) } ?: "—",
        )
    }
}

/** REACH 连接可达性矩阵（SNI 域名 / bare-IP × 握手结果）——数据取自 TestRun 既有列。 */
@Composable
private fun ReachMatrix(run: TestRun) {
    val colors = AnebTheme.colors
    SectionLabel("连接可达性 REACH")
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(colors.surfaceElevated),
    ) {
        ReachRow("SNI 域名", run.sniReachable, run.sniReachMs, header = false)
        HorizontalDivider(color = colors.hairline)
        ReachRow("bare-IP", run.ipReachable, run.ipReachMs, header = false)
    }
    if (run.sniReachable == null && run.ipReachable == null) {
        Text("（本 run 未做 SNI 双通道探测）", fontSize = 11.sp, color = COLOR_INVALID, modifier = Modifier.padding(top = 4.dp))
    }
}

@Composable
private fun ReachRow(label: String, result: String?, ms: Long?, header: Boolean) {
    val colors = AnebTheme.colors
    val ok = result == "ok"
    val color = when {
        result == null -> colors.muted
        ok -> colors.excellent
        else -> colors.poor
    }
    Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 9.dp)) {
        Text(label, fontSize = 12.sp, color = colors.muted, modifier = Modifier.width(90.dp))
        Text(
            when {
                result == null -> "未探测"
                ok -> "OK ${ms?.let { "${it}ms" } ?: ""}"
                else -> result.uppercase()
            },
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            color = color,
        )
    }
}

/** 连接信息：transport / 协商地址 / offset drift（取首个场景快照，零重算）。 */
@Composable
private fun ConnectionInfo(scenarios: List<ScenarioResultEntity>) {
    val s = scenarios.firstOrNull() ?: return
    val colors = AnebTheme.colors
    SectionLabel("连接信息")
    Text(
        "transport=${s.netTransport ?: "—"}  addr=${s.serverObservedAddr ?: "—"}\n" +
            "offset drift=${s.offsetDriftPpm?.let { "%.2f ppm".format(it) } ?: "—"}" +
            (if (s.offsetSuspect) " (suspect)" else "") +
            (ResultFormat.bufferingLabel(s)?.let { "\n$it" } ?: ""),
        fontSize = 11.sp,
        fontFamily = FontFamily.Monospace,
        color = colors.muted,
    )
}

// ---- 以下为原 P1-C07 详情组件（保留内部实现，专业视图复用）----

@Composable
private fun AqsHeadline(run: TestRun) {
    val colors = AnebTheme.colors
    Column(modifier = Modifier.padding(vertical = 8.dp)) {
        val score = run.aqsScore
        if (score != null) {
            val grade = ResultFormat.aqsGrade(score)
            Row(verticalAlignment = Alignment.Bottom) {
                Text("%.1f".format(score), fontSize = 44.sp, fontWeight = FontWeight.Black, color = gradeColor(grade))
                Spacer(Modifier.width(10.dp))
                Text(
                    "AQS ${ResultFormat.gradeLabel(grade)}",
                    fontSize = 18.sp, color = gradeColor(grade),
                    modifier = Modifier.padding(bottom = 6.dp),
                )
            }
            if (run.aqsVetoApplied == true) {
                Text("T4 一票否决生效（封顶 54）", color = GRADE_COLORS.getValue(KpiGrading.POOR), fontSize = 13.sp)
            }
            if (run.aqsLowConfidence == true) {
                Text(
                    "⚠ ${ResultFormat.LOW_CONFIDENCE_LABEL}：证据不完整，本分数仅供参考",
                    color = COLOR_LOWCONF, fontSize = 14.sp, fontWeight = FontWeight.Bold,
                )
            }
        } else {
            Text("AQS —", fontSize = 44.sp, fontWeight = FontWeight.Black, color = COLOR_INVALID)
            Text(
                "不可计算：${run.aqsNotComputableReason ?: run.status ?: "unknown"}",
                color = COLOR_INVALID, fontSize = 14.sp,
            )
        }
        ResultFormat.aqsV02Lines(run)?.let { lines ->
            Text(lines[0], fontSize = 15.sp, fontWeight = FontWeight.Bold, color = colors.ink)
            Text(lines[1], fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = COLOR_INVALID)
        }
    }
}

@Composable
private fun RunMeta(run: TestRun) {
    val colors = AnebTheme.colors
    Text(
        "run=${run.runId}\nmode=${run.mode} transport=${run.transport} status=${run.status ?: "?"} " +
            "report=${run.reportStatus ?: "—"}\norder=${run.scenarioOrder}",
        fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = colors.muted,
    )
    HorizontalDivider(modifier = Modifier.padding(vertical = 6.dp), color = colors.hairline)
}

@Composable
private fun RunKpiRowLine(r: ResultFormat.RunKpiRow) = KpiLine(r.row, prefix = "[${r.source}] ")

@Composable
internal fun KpiLine(row: ResultFormat.KpiRow, prefix: String = "") {
    val colors = AnebTheme.colors
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 3.dp)) {
        Box(
            modifier = Modifier.width(6.dp).height(28.dp)
                .background(if (row.value == null) COLOR_INVALID else gradeColor(row.grade)),
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
                    Text(ResultFormat.LOW_CONFIDENCE_LABEL, fontSize = 11.sp, color = COLOR_LOWCONF)
                }
            }
        }
    }
}

@Composable
private fun ScenarioCard(s: ScenarioResultEntity, track: GeoTrack.Summary?) {
    val colors = AnebTheme.colors
    Column(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(modifier = Modifier.width(10.dp).height(10.dp).background(validityColor(s.validity)))
            Spacer(Modifier.width(6.dp))
            Text("${s.profileId}#${s.repeatIndex} (${s.profileVersion})", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = colors.ink)
            Spacer(Modifier.width(8.dp))
            Text(s.validity, fontSize = 12.sp, color = validityColor(s.validity))
        }
        if (s.validity == "invalid") {
            Text(
                "无效原因: ${s.invalidReasons.ifEmpty { "unknown" }}（KPI 已抑制，原始事件保留）",
                fontSize = 11.sp, color = COLOR_INVALID,
            )
        }
        Text(
            "漂移率 drift=${s.offsetDriftPpm?.let { "%.2f ppm".format(it) } ?: "—"}" +
                (if (s.offsetSuspect) " (offset_suspect)" else "") +
                "  net=${s.netTransport ?: "—"}  addr=${s.serverObservedAddr ?: "—"}",
            fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = colors.muted,
        )
        ResultFormat.bufferingLabel(s)?.let {
            Text(it, fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = COLOR_INVALID)
        }
        if (track != null && track.points > 0) {
            Text(
                "轨迹 ${track.points} 点  起终点距离 " +
                    (track.startEndMeters?.let { "%.1f m".format(it) } ?: "—（<2 点）"),
                fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = colors.muted,
            )
        }
        ResultFormat.kpiRows(s).forEach { KpiLine(it) }
        HorizontalDivider(modifier = Modifier.padding(top = 4.dp), color = colors.hairline)
    }
}

@Composable
private fun ClaimScopeFooter(run: TestRun) {
    val colors = AnebTheme.colors
    Column(modifier = Modifier.padding(top = 12.dp, bottom = 24.dp)) {
        HorizontalDivider(color = colors.hairline)
        Text(ResultFormat.CLAIM_SCOPE_TEXT, fontSize = 11.sp, color = COLOR_INVALID, modifier = Modifier.padding(top = 6.dp))
        Text(ResultFormat.AQS_DISCLAIMER_TEXT, fontSize = 11.sp, color = COLOR_INVALID)
        Text(
            "kpi_set=${run.kpiSet} aqs=${run.aqsVersion} schema=${run.schemaVersion} profiles=${run.profileVersions}",
            fontSize = 10.sp, fontFamily = FontFamily.Monospace, color = COLOR_INVALID,
        )
    }
}
