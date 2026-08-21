package com.aneb.probe.engine

/**
 * run 级热摘要折叠器（THERMAL 接线，D-556/普查 5e5dd67；同构先例 skipped_profiles/D-534）。
 *
 * 输入是 EnvMonitors 发出的 THERMAL 事件 detail 串——格式钉在 [EnvMonitors] emitThermal：
 * `[initial ]status=<name> polluting=<bool>`。不另立第二种编码，从既有 detail 折叠；
 * ThermalSummaryTest 反向钉住发射端模板串，EnvMonitors 改格式会当场红。
 *
 * 语义（R-10）：
 * - 一条 `status=` 事件都没有 →（null, null）＝本 run 无热监控。EnvMonitors 的不可用路径
 *   （`power_manager_unavailable` / `listener_registration_failed: …`）不含 `status=`，天然落到这里；
 * - 有 → 名字按 PowerManager 序数取 max ＋ polluting=true 条数。"none"+0 是**真实读数**
 *   （监控在位且全程干净），非缺测伪装——与计数器语义同款（TokenLiveSourceMappingTest）。
 *
 * R-11 的 SEVERE+ 判定留在 EnvMonitors（polluting 布尔），这里只折叠不重判。
 * thermalName 已覆盖 API 全值域，`status(N)` 兜底形状实际不可达；若出现则含括号不匹配
 * `\w+`、按无法解析不计入（宁缺勿错）。
 */
object ThermalSummary {

    /** `run.env` 的载荷：双 null＝无监控；两键同进退（schema 块内 required 钉住）。 */
    data class Env(val thermalMaxStatus: String?, val thermalPollutingCount: Int?)

    /** PowerManager.THERMAL_STATUS_* 名字序（EnvMonitors.thermalName 值域），下标即烈度。 */
    private val SEVERITY_ORDER =
        listOf("none", "light", "moderate", "severe", "critical", "emergency", "shutdown")

    /** 钉住 EnvMonitors.emitThermal 的 detail 格式（前缀 "initial " 有无皆匹配）。 */
    private val DETAIL_FORMAT = Regex("""status=(\w+) polluting=(true|false)""")

    fun fold(thermalDetails: List<String>): Env {
        var maxIdx = -1
        var polluting = 0
        for (d in thermalDetails) {
            val m = DETAIL_FORMAT.find(d) ?: continue // 不可用路径/未知格式：不计入
            val idx = SEVERITY_ORDER.indexOf(m.groupValues[1])
            if (idx > maxIdx) maxIdx = idx
            if (m.groupValues[2] == "true") polluting++
        }
        if (maxIdx < 0) return Env(null, null)
        return Env(SEVERITY_ORDER[maxIdx], polluting)
    }
}
