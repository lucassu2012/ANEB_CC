package com.aneb.probe.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aneb.probe.ui.theme.AnebTheme
import com.aneb.probe.ui.theme.AnebType
import com.aneb.probe.ui.theme.Grade

/**
 * 数据瓦片（普通用户结果页三联瓦片：响应速度 / 卡顿次数 / 上传 Mbps）。
 * 与设计稿 .tile 一致：大值（半粗 + 等宽数字，按分级着色）+ 键名 + 分级角标。
 *
 * @param value 主数值文本（如 "35"、"0"、"12.5"）；调用方负责格式化与 null→"—"
 * @param unit 数值后缀小字（如 "ms"）；空串不显示
 * @param label 键名（如 "响应速度"）
 * @param grade 该指标分级（决定值颜色与角标；null → 中性灰）
 */
@Composable
fun StatTile(
    value: String,
    label: String,
    grade: Grade?,
    modifier: Modifier = Modifier,
    unit: String = "",
) {
    val colors = AnebTheme.colors
    val valueColor = colors.gradeColor(grade)
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(13.dp))
            .background(colors.surfaceElevated)
            .border(1.dp, colors.hairline, RoundedCornerShape(13.dp))
            .padding(horizontal = 9.dp, vertical = 11.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Row(verticalAlignment = Alignment.Bottom) {
            Text(text = value, style = AnebType.StatValue, fontSize = 17.sp, color = valueColor)
            if (unit.isNotEmpty()) {
                Text(text = unit, fontSize = 11.sp, color = valueColor, fontWeight = FontWeight.Medium)
            }
        }
        Text(text = label, fontSize = 10.sp, color = colors.muted, modifier = Modifier.padding(top = 3.dp))
        if (grade != null) {
            Text(
                text = grade.labelCn,
                fontSize = 9.5.sp,
                fontWeight = FontWeight.Bold,
                color = valueColor,
                modifier = Modifier.padding(top = 5.dp),
            )
        }
    }
}
