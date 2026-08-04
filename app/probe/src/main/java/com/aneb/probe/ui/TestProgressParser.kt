package com.aneb.probe.ui

/**
 * run 进度派生（纯逻辑，可单测）。从 TestEngine 既有日志 KEY 行折叠出结构化进度——
 * 不改 TestEngine 输出格式（UI 层解析既有合同字段）。
 *
 * T48/批A：从已删除的 `TestingScreen.kt` 抽出独立文件——`HomeScreen.kt` 一直是它的
 * 消费方（死屏删除前先搬家，避免带走 HomeScreen 依赖的解析器）。
 */
object TestProgressParser {

    data class LiveProgress(
        val runId: String?,
        val scenarioIndex: Int,
        val totalScenarios: Int,
        val phaseName: String,
        val fraction: Float,
        val ttftMs: Double?,
        val stallCount: Int,
        val finished: Boolean,
        val finishedRunId: String?,
    ) {
        val liveHint: String get() = "正在测：${phaseName}的 token 流是否顺滑"

        /** stall 落在环刻度（60 格）上的下标近似（卡顿缺口位置）。 */
        val stallTickPositions: List<Int>
            get() = if (stallCount <= 0) emptyList() else (1..stallCount).map {
                ((it.toFloat() / (stallCount + 1)) * 60f * fraction).toInt().coerceIn(0, 59)
            }
    }

    private val PROFILE_NAMES = mapOf(
        "s1_chat" to "闲聊对话",
        "s2_coding_agent" to "编码 Agent 流",
        "s3_multimodal" to "多模态上传",
    )

    fun parse(logs: List<String>): LiveProgress {
        var runId: String? = null
        var total = 3 // 快测缺省 3 场景
        var scenarioIndex = 0
        var currentProfile: String? = null
        var completedKpis = 0
        var latestTtft: Double? = null
        var stalls = 0
        var finished = false
        var finishedRunId: String? = null

        for (line in logs) {
            when {
                line.startsWith("RUN_START ") ->
                    runId = field(line, "run_id")
                line.startsWith("ORDER ") -> {
                    // order=s1,s2,s3 → 场景总数（首个 ORDER 即可）
                    field(line, "order")?.let { total = it.split(',').size.coerceAtLeast(1) }
                }
                line.startsWith("SCENARIO_START ") -> {
                    scenarioIndex = field(line, "order_index")?.toIntOrNull() ?: scenarioIndex
                    currentProfile = field(line, "scenario")?.substringBefore('#')
                }
                line.startsWith("SCENARIO_KPI ") -> {
                    completedKpis++
                    field(line, "t1_ms")?.toDoubleOrNull()?.let { latestTtft = it }
                    val t3 = field(line, "t3")?.toDoubleOrNull()
                    if (t3 != null && t3 > 0.0) stalls++
                }
                line.startsWith("RUN_END ") -> {
                    finished = true
                    finishedRunId = field(line, "run_id") ?: runId
                }
            }
        }

        val fraction = ((completedKpis.toFloat() + if (finished) 0f else 0.5f) / total)
            .coerceIn(0f, 1f)
        val phaseName = PROFILE_NAMES[currentProfile] ?: "网络场景"
        return LiveProgress(
            runId = runId,
            scenarioIndex = scenarioIndex.coerceIn(0, (total - 1).coerceAtLeast(0)),
            totalScenarios = total,
            phaseName = phaseName,
            fraction = fraction,
            ttftMs = latestTtft,
            stallCount = stalls,
            finished = finished,
            finishedRunId = finishedRunId,
        )
    }

    /** 从 "key=value" 合同行提取字段（空白分隔；值到下一个空白止）。 */
    private fun field(line: String, key: String): String? =
        Regex("(?:^|\\s)${Regex.escape(key)}=(\\S+)").find(line)?.groupValues?.get(1)
}
