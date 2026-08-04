package com.aneb.probe.engine

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/*
 * 场景 profile 数据模型（与 server/profiles.go 的 Go 结构一一对应，两端共享合同）。
 * 纯 JVM、无 Android 依赖，可直接单测。
 * profile 一旦发布即冻结，修改必须升版本号（设计文档 §3）。
 */

@Serializable
data class ProfileTokenBytes(
    val dist: String = "lognormal",
    val median: Double = 120.0,
    val sigma: Double = 0.6,
)

@Serializable
data class ProfileBurst(
    @SerialName("cluster_tps") val clusterTps: Double = 0.0,
    @SerialName("pause_ms") val pauseMs: List<Int> = emptyList(),
    @SerialName("cluster_geom_p") val clusterGeomP: Double = 0.0,
)

/** phase 联合体：字段按 [type] 选用（同 Go 侧 Phase）。 */
@Serializable
data class ProfilePhase(
    val type: String,
    // clock_sync
    val samples: Int = 0,
    // upload_burst
    val bytes: Long = 0,
    @SerialName("chunk_kb") val chunkKb: Int = 0,
    // think_pause
    @SerialName("duration_ms") val durationMs: Int = 0,
    // token_stream
    val tokens: Int = 0,
    @SerialName("rate_tps") val rateTps: Double = 0.0,
    @SerialName("token_bytes") val tokenBytes: ProfileTokenBytes? = null,
    val burst: ProfileBurst? = null,
    val seed: Long = 0,
    // tool_loop
    val rounds: Int = 0,
    @SerialName("up_bytes") val upBytes: Long = 0,
    @SerialName("down_bytes") val downBytes: Long = 0,
    @SerialName("server_proc_ms") val serverProcMs: Int = 0,
    // adaptive_download_window / adaptive_upload_window（T47 批②，D-468/D-469；
    // spec/PROFILE2_THROUGHPUT_PROBE_SPEC.md §8.3.5）：目标窗口时长。
    // bytes/chunk_kb 两个既有字段在这两个新 type 下复用为「请求上限(ceiling)」/
    // 「读写块大小」，与 upload_burst/download_burst 下「精确传输量」的语义不同——
    // 同一字段名在不同 type 下的既有联合体设计模式的延伸（本文件顶部注释已声明）。
    @SerialName("window_ms") val windowMs: Int = 0,
) {
    companion object {
        const val TYPE_CLOCK_SYNC = "clock_sync"
        const val TYPE_UPLOAD_BURST = "upload_burst"
        const val TYPE_THINK_PAUSE = "think_pause"
        const val TYPE_TOKEN_STREAM = "token_stream"
        const val TYPE_TOOL_LOOP = "tool_loop"

        /** 下行大对象拉取（D1，PROFILE_FRAMEWORK §2.4；服务端 profiles.go 已支持同名相位）。 */
        const val TYPE_DOWNLOAD_BURST = "download_burst"

        // T47 批②（D-468/D-469）：单流自适应窗口 goodput 探针（U3/D3）新增两个 phase 类型。
        const val TYPE_ADAPTIVE_DOWNLOAD_WINDOW = "adaptive_download_window"
        const val TYPE_ADAPTIVE_UPLOAD_WINDOW = "adaptive_upload_window"
    }
}

@Serializable
data class ScenarioProfile(
    @SerialName("profile_id") val profileId: String,
    val version: String,
    @SerialName("kpi_set") val kpiSet: String = "",
    val description: String = "",
    @SerialName("est_duration_s") val estDurationS: Double = 0.0,
    val phases: List<ProfilePhase> = emptyList(),
)

/** GET /api/v1/profiles 响应体。 */
@Serializable
data class ProfilesResponse(
    @SerialName("server_version") val serverVersion: String = "",
    val profiles: List<ScenarioProfile> = emptyList(),
)

object ProfileParser {
    /** 三场景固定集合（阶段 1 范围），顺序即拉丁方的场景下标 0/1/2。 */
    val REQUIRED_IDS = listOf("s1_chat", "s2_coding_agent", "s3_multimodal")

    private val json = Json { ignoreUnknownKeys = true }

    /** 解析 /api/v1/profiles 响应。缺任一必需场景即抛（profile 是两端共享合同，禁静默缺省）。 */
    fun parseServerResponse(body: String): Map<String, ScenarioProfile> {
        val resp = json.decodeFromString(ProfilesResponse.serializer(), body)
        return index(resp.profiles)
    }

    /** 解析单个 profile JSON（打包内置 assets 副本路径）。 */
    fun parseSingle(body: String): ScenarioProfile =
        json.decodeFromString(ScenarioProfile.serializer(), body)

    fun index(profiles: List<ScenarioProfile>): Map<String, ScenarioProfile> {
        val map = profiles.associateBy { it.profileId }
        val missing = REQUIRED_IDS.filter { it !in map }
        require(missing.isEmpty()) { "missing required profiles: $missing" }
        return map
    }

    /** 版本串（结果合同 profile_versions 字段 + 版本一致性告警用）。 */
    fun versionString(profiles: Map<String, ScenarioProfile>): String =
        REQUIRED_IDS.joinToString(";") { id -> "$id@${profiles[id]?.version ?: "missing"}" }
}
