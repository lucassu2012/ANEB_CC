package com.aneb.probe.ui

import androidx.compose.foundation.background
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.data.ScenarioResultEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.engine.KpiGrading

/**
 * 结果页（P1-C07）：AQS 头条 + run 级 KPI 表（四级色条+双口径并列+低置信标）+
 * 场景卡片 + claim scope 页脚。朴素但信息完整（D-02）。
 * 所有数据来自 Room 落库实体，本层不重算（口径单一事实来源=TestEngine 写入）。
 */

// 四级分级色（优绿/良蓝/可橙/差红）；INVALID/缺失灰
internal val GRADE_COLORS: Map<String, Color> = mapOf(
    KpiGrading.EXCELLENT to Color(0xFF2E7D32),
    KpiGrading.GOOD to Color(0xFF1565C0),
    KpiGrading.FAIR to Color(0xFFEF6C00),
    KpiGrading.POOR to Color(0xFFC62828),
)
internal val COLOR_INVALID = Color(0xFF757575)
internal val COLOR_LOWCONF = Color(0xFFEF6C00)

internal fun gradeColor(grade: String?): Color = GRADE_COLORS[grade] ?: COLOR_INVALID

internal fun validityColor(validity: String): Color = when (validity) {
    "valid" -> Color(0xFF2E7D32)
    "valid_low_confidence" -> COLOR_LOWCONF
    else -> COLOR_INVALID
}

@Composable
fun ResultScreen(
    run: TestRun?,
    scenarios: List<ScenarioResultEntity>,
    hasReportJson: Boolean,
    exportStatus: String?,
    onExportJson: () -> Unit,
    onExportCsv: () -> Unit,
    onBack: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize().padding(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedButton(onClick = onBack) { Text("← 返回") }
            Spacer(Modifier.width(8.dp))
            Text("测试结果", fontSize = 18.sp, fontWeight = FontWeight.Bold)
        }
        if (run == null) {
            Text("run 不存在", color = COLOR_INVALID, modifier = Modifier.padding(top = 16.dp))
            return
        }
        LazyColumn(modifier = Modifier.weight(1f).fillMaxWidth()) {
            item { AqsHeadline(run) }
            item { RunMeta(run) }
            item {
                SectionTitle("KPI 总表（AQS 输入映射：N←S1 / T,U2←S2 / U1←S3）")
                Column {
                    ResultFormat.runKpiRows(scenarios).forEach { RunKpiRowLine(it) }
                }
            }
            item { SectionTitle("场景明细") }
            items(count = scenarios.size, key = { i -> scenarios[i].id }) { i ->
                ScenarioCard(scenarios[i])
            }
            item {
                SectionTitle("导出")
                Row {
                    Button(enabled = hasReportJson, onClick = onExportJson) { Text("导出 JSON") }
                    Spacer(Modifier.width(8.dp))
                    Button(enabled = scenarios.isNotEmpty(), onClick = onExportCsv) { Text("导出 CSV") }
                }
                if (!hasReportJson) {
                    Text(
                        "该 run 未生成上报体（早退/失败），JSON 不可导出",
                        fontSize = 11.sp, color = COLOR_INVALID,
                    )
                }
                exportStatus?.let {
                    Text(it, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
                }
            }
            item { ClaimScopeFooter(run) }
        }
    }
}

@Composable
private fun AqsHeadline(run: TestRun) {
    Column(modifier = Modifier.padding(vertical = 8.dp)) {
        val score = run.aqsScore
        if (score != null) {
            val grade = ResultFormat.aqsGrade(score)
            Row(verticalAlignment = Alignment.Bottom) {
                Text(
                    "%.1f".format(score),
                    fontSize = 56.sp,
                    fontWeight = FontWeight.Bold,
                    color = gradeColor(grade),
                )
                Spacer(Modifier.width(12.dp))
                Text(
                    "AQS ${ResultFormat.gradeLabel(grade)}",
                    fontSize = 22.sp,
                    color = gradeColor(grade),
                    modifier = Modifier.padding(bottom = 8.dp),
                )
            }
            if (run.aqsVetoApplied == true) {
                Text("T4 一票否决生效（封顶 54）", color = GRADE_COLORS.getValue(KpiGrading.POOR), fontSize = 13.sp)
            }
            if (run.aqsLowConfidence == true) {
                // KPI 文档 5.4：valid_low_confidence 的 AQS 必须带明显低置信标注
                Text(
                    "⚠ ${ResultFormat.LOW_CONFIDENCE_LABEL}：证据不完整，本分数仅供参考",
                    color = COLOR_LOWCONF,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
        } else {
            Text("AQS —", fontSize = 56.sp, fontWeight = FontWeight.Bold, color = COLOR_INVALID)
            Text(
                "不可计算：${run.aqsNotComputableReason ?: run.status ?: "unknown"}",
                color = COLOR_INVALID,
                fontSize = 14.sp,
            )
        }
    }
}

@Composable
private fun RunMeta(run: TestRun) {
    Text(
        "run=${run.runId}\n" +
            "mode=${run.mode} transport=${run.transport} status=${run.status ?: "?"} " +
            "report=${run.reportStatus ?: "—"}\n" +
            "order=${run.scenarioOrder}",
        fontSize = 11.sp,
        fontFamily = FontFamily.Monospace,
    )
    HorizontalDivider(modifier = Modifier.padding(vertical = 6.dp))
}

@Composable
private fun SectionTitle(text: String) {
    Text(text, fontSize = 14.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 10.dp, bottom = 4.dp))
}

@Composable
private fun RunKpiRowLine(r: ResultFormat.RunKpiRow) {
    KpiLine(r.row, prefix = "[${r.source}] ")
}

@Composable
internal fun KpiLine(row: ResultFormat.KpiRow, prefix: String = "") {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 2.dp)) {
        Box(
            modifier = Modifier
                .width(6.dp)
                .height(28.dp)
                .background(if (row.value == null) COLOR_INVALID else gradeColor(row.grade)),
        )
        Spacer(Modifier.width(8.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text("$prefix${row.id} ${row.label}", fontSize = 12.sp)
            Row {
                Text(
                    ResultFormat.formatValue(row),
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    ResultFormat.gradeLabel(row.grade),
                    fontSize = 13.sp,
                    color = gradeColor(row.grade),
                )
                if (row.lowConfidence) {
                    Spacer(Modifier.width(8.dp))
                    Text(ResultFormat.LOW_CONFIDENCE_LABEL, fontSize = 11.sp, color = COLOR_LOWCONF)
                }
            }
        }
    }
}

@Composable
private fun ScenarioCard(s: ScenarioResultEntity) {
    Column(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(modifier = Modifier.width(10.dp).height(10.dp).background(validityColor(s.validity)))
            Spacer(Modifier.width(6.dp))
            Text(
                "${s.profileId}#${s.repeatIndex} (${s.profileVersion})",
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.width(8.dp))
            Text(s.validity, fontSize = 12.sp, color = validityColor(s.validity))
        }
        if (s.validity == "invalid") {
            // INVALID：灰色 + 原因码（fail-closed 展示语义）
            Text(
                "无效原因: ${s.invalidReasons.ifEmpty { "unknown" }}（KPI 已抑制，原始事件保留）",
                fontSize = 11.sp,
                color = COLOR_INVALID,
            )
        }
        Text(
            "漂移率 drift=${s.offsetDriftPpm?.let { "%.2f ppm".format(it) } ?: "—"}" +
                (if (s.offsetSuspect) " (offset_suspect)" else "") +
                "  net=${s.netTransport ?: "—"}  addr=${s.serverObservedAddr ?: "—"}",
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
        )
        ResultFormat.kpiRows(s).forEach { KpiLine(it) }
        HorizontalDivider(modifier = Modifier.padding(top = 4.dp))
    }
}

@Composable
private fun ClaimScopeFooter(run: TestRun) {
    Column(modifier = Modifier.padding(top = 12.dp, bottom = 24.dp)) {
        HorizontalDivider()
        Text(
            ResultFormat.CLAIM_SCOPE_TEXT,
            fontSize = 11.sp,
            color = COLOR_INVALID,
            modifier = Modifier.padding(top = 6.dp),
        )
        Text(ResultFormat.AQS_DISCLAIMER_TEXT, fontSize = 11.sp, color = COLOR_INVALID)
        Text(
            "kpi_set=${run.kpiSet} aqs=${run.aqsVersion} schema=${run.schemaVersion} profiles=${run.profileVersions}",
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            color = COLOR_INVALID,
        )
    }
}
