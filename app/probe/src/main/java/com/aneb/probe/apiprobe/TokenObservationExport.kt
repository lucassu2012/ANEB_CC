package com.aneb.probe.apiprobe

import kotlinx.serialization.json.add
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * Profile 2 校准输入采集器：把 **API 直调探针**的逐 token 到达序列导出为符合 Codex
 * `aneb-token-observation-v1` 合同的**隐私最小化派生统计**（单 session 一条 observation），
 * 供 Codex 授权校准流水线（`tools/aneb-ai-behavior-model` 的 prepare→calibrate→promote）消费。
 *
 * **口径铁律（D-62）**：本导出体口径 = **API 直调**（`application_end_to_end_to_llm_api`），
 * **≠** 消费 App 画像（`spec/portraits/` 下的 app yaml）。翻的是「API/编程 Agent」profile 门，
 * **绝不注入消费 App（豆包/DeepSeek/千问/Kimi App）的 token/think 字段**——那层因 mitm
 * 明文不可得（D-61）恒 PENDING。口径标注落在 **dataset manifest 层**（calibration-dataset-v1），
 * 不落单条 observation（合同 additionalProperties=false）。
 *
 * **隐私红线（对齐 token-observation-v1 + P3_CALIBRATION_PIPELINE §3）**：
 *  - `additionalProperties=false` → 只输出合同 8 必需 + 1 可选字段，**绝不含**
 *    prompt/content/account/api-key（无自由文本出口面）；
 *  - `subject_group_id` 必须 **数据集专用密钥的 HMAC-SHA256**（普通 `SHA256(account)` 去标识化
 *    不足），格式 `hmac-sha256:<64 lowercase hex>`；密钥不入库、不入导出、不同数据集换密钥。
 *
 * **R-10 缺失语义**：数据不足以构成合法 observation（无合法 token 间隔 / output<1 /
 * payload<1）时返回 null 让调用方**跳过该 session**，绝不补 0/哨兵。
 *
 * 纯 JVM、无 Android 依赖 → JVM 单测直接锚定（见 TokenObservationExportTest）。
 */
object TokenObservationExport {

    /** token-observation-v1 合同版本常量（schema `observation_contract_version` const）。 */
    const val CONTRACT_VERSION = "aneb-token-observation-v1"

    /** 合同 `workload_kind` 枚举（按**输入类型**分；output 恒为 token 流）。 */
    enum class WorkloadKind(val id: String) {
        TEXT("text"), DOCUMENT("document"), IMAGE("image"), VIDEO("video")
    }

    // schema 约束：subject_group_id 与 observation_id 的正则（合同原文）
    private val SUBJECT_RE = Regex("^hmac-sha256:[0-9a-f]{64}$")
    private val OBS_ID_RE = Regex("^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")

    /**
     * 从 token 到达序列重建 `token_intervals_ms`（合同要 minItems≥1、items exclusiveMinimum 0）。
     *
     * 复用 [ApiProbeKpi] 单一口径：剔除 `sameReadBatch` 合帧伪 0 间隔（R-04 组内只留组首间隔）
     * 与恰 ≤0 的间隔（5.1 同款）——与对照列 ITL 样本口径一致，保证两处不漂移。
     *
     * @return 合法间隔（ms，全 >0）；空列表 = 不足以构成合法 observation（调用方须跳过）。
     */
    fun tokenIntervalsMs(arrivals: List<LlmTokenArrival>): List<Double> {
        val out = ArrayList<Double>(arrivals.size)
        for (i in 1 until arrivals.size) {
            val cur = arrivals[i]
            if (cur.sameReadBatch) continue // R-04：合帧伪 0 间隔剔除
            val dtMs = (cur.arrivalNanos - arrivals[i - 1].arrivalNanos) / 1e6
            if (dtMs <= 0.0) continue // exclusiveMinimum 0：非正间隔不入
            out.add(dtMs)
        }
        return out
    }

    /**
     * 数据集专用 HMAC-SHA256 去标识化（P3_CALIBRATION_PIPELINE §3：普通 `SHA256(account)`
     * 不构成足够去标识化）。同数据集内同一 subject 稳定 → 可检查同数据集主体泄漏；
     * 换数据集换密钥 → 降低跨数据集关联风险。
     *
     * @param datasetSecret 数据集专用密钥（不入库/不入导出；不同数据集必须更换）
     * @param subject       主体标识（仅用于派生，绝不写入 observation 输出）
     * @return `hmac-sha256:<64 lowercase hex>`
     */
    fun subjectGroupId(datasetSecret: ByteArray, subject: String): String {
        require(datasetSecret.isNotEmpty()) { "datasetSecret must not be empty" }
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(datasetSecret, "HmacSHA256"))
        val digest = mac.doFinal(subject.toByteArray(Charsets.UTF_8))
        return "hmac-sha256:" + digest.joinToString("") { "%02x".format(it) }
    }

    /**
     * 构造单条符合 `aneb-token-observation-v1` 的 observation JSON。
     *
     * @param observationId          `^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$`（合同格式；调用方生成）
     * @param subjectGroupId         [subjectGroupId] 产出（`hmac-sha256:<64hex>`）
     * @param workloadKind           输入类型
     * @param payloadBytes           输入 payload 字节（≥1；如请求体字节数）
     * @param processingDelayMs      处理等待（≥0；如首 token 前的 TTFT/处理等待，对照列口径）
     * @param outputTokenCount       服务端 usage 输出 token 数（≥1；缺失时可用 delta 事件数近似，调用方决定）
     * @param arrivals               token delta 到达序列（用于重建 token_intervals_ms）
     * @param responseArtifactBytes  可选：响应产物字节（如流总字节）
     * @return observation JSON 字符串；不满足合同硬约束（无合法间隔 / output<1 / payload<1 /
     *         delay<0）时返回 null（R-10：调用方跳过，绝不补哨兵）。
     * @throws IllegalArgumentException observationId / subjectGroupId 格式非法（编程错误，非数据缺失）
     */
    fun buildObservation(
        observationId: String,
        subjectGroupId: String,
        workloadKind: WorkloadKind,
        payloadBytes: Int,
        processingDelayMs: Double,
        outputTokenCount: Int,
        arrivals: List<LlmTokenArrival>,
        responseArtifactBytes: Long? = null,
    ): String? {
        require(OBS_ID_RE.matches(observationId)) { "observation_id must match $OBS_ID_RE" }
        require(SUBJECT_RE.matches(subjectGroupId)) { "subject_group_id must be hmac-sha256:<64hex>" }
        // R-10 数据缺失 → 跳过（非异常）
        val intervals = tokenIntervalsMs(arrivals)
        if (intervals.isEmpty()) return null // token_intervals_ms minItems 1
        if (outputTokenCount < 1) return null // output_token_count minimum 1
        if (payloadBytes < 1) return null // payload_bytes minimum 1
        if (processingDelayMs < 0.0) return null // processing_delay_ms minimum 0
        if (responseArtifactBytes != null && responseArtifactBytes < 0) return null // minimum 0

        return buildJsonObject {
            put("observation_contract_version", CONTRACT_VERSION)
            put("observation_id", observationId)
            put("subject_group_id", subjectGroupId)
            put("workload_kind", workloadKind.id)
            put("payload_bytes", payloadBytes)
            put("processing_delay_ms", processingDelayMs)
            put("output_token_count", outputTokenCount)
            putJsonArray("token_intervals_ms") { intervals.forEach { add(it) } }
            if (responseArtifactBytes != null) put("response_artifact_bytes", responseArtifactBytes)
        }.toString()
    }

    /**
     * 合规 `observation_id`（合同 `^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$`）：
     * `apiprobe-<providerId>-<startedAtEpochMs>`。providerId 只含 [a-z_]、时间戳只含数字，
     * 均在字符集内；首字符 'a' 满足起始 alnum 约束。纯函数便于单测锚定唯一性/格式。
     */
    fun observationId(providerId: String, startedAtEpochMs: Long): String =
        "apiprobe-$providerId-$startedAtEpochMs"

    /**
     * 从**一次 API 探针**的输出构造 observation（[buildObservation] 的探针适配层）：封装两个
     * 口径决策，其余同 [buildObservation]（R-10：数据不足返回 null 让调用方跳过该 session）。
     *  - `output_token_count`：优先服务端 usage（[outputTokens]）；缺失时按合同允许回退 delta
     *    事件数（[tokenEventCount]，合同原文"缺失时可用 delta 事件数近似"）。两者皆不足(<1)→null。
     *  - `processing_delay_ms`：用探针 TTFT（[ttftMs]，请求发起→首 token）；缺失(无 token 到达)→null。
     *
     * 纯 JVM、无 Android 依赖 → JVM 单测直接锚定（见 TokenObservationExportTest）。
     *
     * @param requestBodyBytes 请求体字节数（UTF-8；作 payload_bytes，须 ≥1）
     * @param ttftMs           探针 TTFT（ms）；null = 无 token 到达 → 返回 null
     * @param outputTokens     服务端 usage 输出 token 数；null = usage 缺失（走回退）
     * @param tokenEventCount  delta 事件数（usage 缺失时的回退近似）
     */
    fun fromProbeOutputs(
        observationId: String,
        subjectGroupId: String,
        workloadKind: WorkloadKind,
        requestBodyBytes: Int,
        ttftMs: Double?,
        outputTokens: Int?,
        tokenEventCount: Int,
        arrivals: List<LlmTokenArrival>,
        responseArtifactBytes: Long? = null,
    ): String? {
        val delay = ttftMs ?: return null // 无 TTFT（无 token 到达）→ 不构成合法 observation
        val outCount = outputTokens ?: tokenEventCount // 合同允许：usage 缺失回退 delta 事件数
        return buildObservation(
            observationId = observationId,
            subjectGroupId = subjectGroupId,
            workloadKind = workloadKind,
            payloadBytes = requestBodyBytes,
            processingDelayMs = delay,
            outputTokenCount = outCount,
            arrivals = arrivals,
            responseArtifactBytes = responseArtifactBytes,
        )
    }

    /**
     * JSONL 批：每行一条 observation。传入前应已过滤 [buildObservation] 的 null（跳过的 session）。
     */
    fun buildJsonl(observations: List<String>): String = observations.joinToString("\n")
}
