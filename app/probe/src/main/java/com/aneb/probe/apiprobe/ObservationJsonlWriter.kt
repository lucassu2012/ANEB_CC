package com.aneb.probe.apiprobe

import java.io.File

/**
 * Profile-2 校准 observation 的 JSONL 落盘器（D-64 之后把"预留实采"seam 接到真实落地）。
 *
 * 每行一条 `aneb-token-observation-v1` observation，append 到 [dir] 下按 provider 命名的分片文件，
 * 单片超过 [maxFileBytes] 轮换（`_00`→`_01`…）。**纯 [File] 依赖、无 Android Context** → JVM 单测
 * 直接用临时目录锚定（append/累积/多行拒绝/轮换）。
 *
 * **隐私**：observation 由 [TokenObservationExport] 产出，已隐私最小化（无 prompt/content/key）；
 * 文件落 App 私有目录（非 root 不可读），不导出原文；本类不接触 datasetSecret/subject。
 */
class ObservationJsonlWriter(
    private val dir: File,
    private val maxFileBytes: Long = 4L * 1024 * 1024,
) {

    /**
     * 追加一条 observation（必须是**单行** JSON，无内部换行——JSONL 每行一条的硬约束）。
     * @return 实际写入的分片文件。
     * @throws IllegalArgumentException observation 为空或含换行（编程错误，非数据缺失）。
     */
    @Synchronized
    fun append(observationJson: String, providerId: String): File {
        require(observationJson.isNotBlank() && !observationJson.contains('\n')) {
            "observation must be non-blank single-line JSON"
        }
        if (!dir.exists()) dir.mkdirs()
        val file = currentFile(providerId)
        file.appendText(observationJson + "\n", Charsets.UTF_8)
        return file
    }

    /**
     * 当前应写入的分片：按 [providerId] 命名，若最新分片已达 [maxFileBytes] 则进位到下一序号。
     * providerId 先做文件名安全化（仅保留 [A-Za-z0-9_-]，空则记 `unknown`）。
     */
    fun currentFile(providerId: String): File {
        val safe = providerId.filter { it.isLetterOrDigit() || it == '_' || it == '-' }
            .ifBlank { "unknown" }
        var seq = 0
        var file = File(dir, name(safe, seq))
        while (file.exists() && file.length() >= maxFileBytes) {
            seq++
            file = File(dir, name(safe, seq))
        }
        return file
    }

    private fun name(providerId: String, seq: Int): String =
        "aneb_token_obs_${providerId}_${"%02d".format(seq)}.jsonl"
}