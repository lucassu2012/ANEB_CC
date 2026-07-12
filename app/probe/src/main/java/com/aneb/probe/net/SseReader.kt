package com.aneb.probe.net

import android.os.SystemClock
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okio.Buffer
import okio.BufferedSource
import okio.ByteString.Companion.encodeUtf8
import java.util.Base64

/**
 * 单个 token event 的到达记录。
 *
 * @param seq           服务端序号（R-08：KPI 对齐一律按 seq join，禁数组位置配对）
 * @param schedUs       服务端"期望发出时刻"（profile 时刻表，进程启动锚点单调 us；缺失为 -1）
 * @param preFlushUs    服务端"实际 flush 前时刻"（同上单调轴；缺失为 -1）
 * @param arrivalNanos  客户端读出该 event 所在 read 块的时刻（elapsedRealtimeNanos）
 * @param payloadBytes  payload 解码后字节数（base64 传输，R-08 杜绝随机字节与 \n\n 冲突）
 * @param sameReadBatch R-04：同一次 source.read 切出的第 2..n 个 event 标 true——
 *                      它们与前一 event 的间隔是内存读出伪 0 值，ITL 统计须剔除
 */
data class TokenEvent(
    val seq: Long,
    val schedUs: Long,
    val preFlushUs: Long,
    val arrivalNanos: Long,
    val payloadBytes: Int,
    val sameReadBatch: Boolean,
)

/** prelude 注释帧（R-20：响应头写出后先 flush 一帧，把服务端 dwell 从 T1 网络分量剥离）。 */
data class SsePrelude(
    val arrivalNanos: Long,
    /** 注释帧原文（去掉前导 ':'），形如 `prelude {"srv_ts_us":...}`，解析留给上层 */
    val raw: String,
)

data class SseStreamResult(
    val prelude: SsePrelude?,
    val events: List<TokenEvent>,
    /** summary event 的 data 原文（服务端发送自检统计），阶段 0 不深度解析 */
    val summaryRaw: String?,
    val readCount: Int,
    val totalBytes: Long,
    /** 解析失败被跳过的 event 数（R-08：跳过并计数，绝不静默错位） */
    val parseErrors: Int,
    /** EOF 时累积缓冲仍有残留 => 尾部截断 event */
    val truncatedTail: Boolean,
    /** 流 EOF 时刻（elapsedRealtimeNanos）——解析阶段起点打戳（P0-C12） */
    val eofNanos: Long,
    /** 解析完成时刻（elapsedRealtimeNanos）（P0-C12） */
    val parseEndNanos: Long,
) {
    /** 解析阶段总耗时（us）＝ parseEnd − EOF（P0-C12：解析开销不得混入 ITL 的证据） */
    val parseDurUs: Long get() = (parseEndNanos - eofNanos) / 1_000L

    /** 每 event 平均解析耗时（us）＝ parseDurUs / 事件数；无事件记 null（R-10） */
    val perEventParseUs: Double? get() = if (events.isEmpty()) null else parseDurUs.toDouble() / events.size
}

/**
 * SSE 读取器（R-04 核心）。
 *
 * 读循环规则：
 *  - 按可用量批读 `source.read(buffer, 8192)`，一次 read 返回打一次戳；
 *  - 在累积缓冲内扫描 `\n\n` 边界切 event；同一次 read 切出的多个 event 共享该 read
 *    的到达时戳，且第 2..n 个标 sameReadBatch=true（杜绝伪造 0ms ITL 稀释 P95）；
 *  - 读循环内除必要的字节切片分配外不做重活：原始 event 字节先写入预分配 ArrayList，
 *    文本解码 / JSON 解析 / base64 解码全部推迟到流读完之后。
 *    TODO(阶段1): 解析仍在读线程（EOF 后）执行，需移到独立线程并配合
 *    THREAD_PRIORITY_URGENT_AUDIO + 哨兵线程（设计文档 §4.10 / R-16）。
 *
 * 服务端 wire 约定（见 probe/README.md）：
 *  - 注释帧:  `: prelude {"srv_ts_us":...}\n\n`
 *  - token:  `event: token\ndata: {"seq":N,"sched_us":...,"pre_flush_us":...,"payload":"<base64>"}\n\n`
 *  - 结尾:   `event: summary\ndata: {...}\n\n`
 */
class SseReader(
    private val json: Json = Json { ignoreUnknownKeys = true },
) {

    @Serializable
    private data class TokenWire(
        val seq: Long,
        @SerialName("sched_us") val schedUs: Long = -1L,
        @SerialName("pre_flush_us") val preFlushUs: Long = -1L,
        val payload: String = "",
    )

    private class RawEvent(
        val bytes: ByteArray,
        val arrivalNanos: Long,
        val sameReadBatch: Boolean,
    )

    fun readStream(source: BufferedSource): SseStreamResult {
        // 预分配（S1 默认 600 token + prelude + summary，留裕量）
        val rawEvents = ArrayList<RawEvent>(1024)
        val acc = Buffer()
        val readBuf = Buffer()
        var readCount = 0
        var totalBytes = 0L

        // ---- 读循环：read → 打戳 → 切边界 → 存原始字节，别的都不做 ----
        while (true) {
            val n = source.read(readBuf, READ_CHUNK_BYTES)
            if (n == -1L) break
            val arrivalNanos = SystemClock.elapsedRealtimeNanos()
            readCount++
            totalBytes += n
            acc.writeAll(readBuf)

            var eventsInThisRead = 0
            while (true) {
                val boundary = acc.indexOf(EVENT_DELIMITER)
                if (boundary == -1L) break
                val eventBytes = acc.readByteArray(boundary)
                acc.skip(EVENT_DELIMITER.size.toLong())
                if (eventBytes.isEmpty()) continue
                rawEvents.add(
                    RawEvent(
                        bytes = eventBytes,
                        arrivalNanos = arrivalNanos,
                        // 同一 read 内第 2..n 个 event：到达间隔是伪 0（R-04）
                        sameReadBatch = eventsInThisRead > 0,
                    )
                )
                eventsInThisRead++
            }
        }
        val truncatedTail = acc.size > 0L
        // P0-C12：EOF 打戳——解析阶段（下方）与读循环（上方）的时间边界
        val eofNanos = SystemClock.elapsedRealtimeNanos()

        // ---- 解析阶段（流已读完；TODO 阶段1 移出读线程）----
        var prelude: SsePrelude? = null
        var summaryRaw: String? = null
        var parseErrors = 0
        val events = ArrayList<TokenEvent>(rawEvents.size)

        for (raw in rawEvents) {
            val text = raw.bytes.toString(Charsets.UTF_8)
            var eventName: String? = null
            var dataLine: String? = null
            var commentLine: String? = null
            // 阶段 0 简化：服务端保证单 data 行；多 data 行拼接留 TODO 阶段1
            for (line in text.split('\n')) {
                when {
                    line.startsWith(":") -> commentLine = line.removePrefix(":").trim()
                    line.startsWith("event:") -> eventName = line.removePrefix("event:").trim()
                    line.startsWith("data:") -> dataLine = line.removePrefix("data:").trim()
                }
            }
            when {
                commentLine != null && commentLine.startsWith("prelude") ->
                    prelude = SsePrelude(raw.arrivalNanos, commentLine)

                eventName == "summary" -> summaryRaw = dataLine

                eventName == "token" && dataLine != null -> {
                    try {
                        val wire = json.decodeFromString(TokenWire.serializer(), dataLine)
                        events.add(
                            TokenEvent(
                                seq = wire.seq,
                                schedUs = wire.schedUs,
                                preFlushUs = wire.preFlushUs,
                                arrivalNanos = raw.arrivalNanos,
                                payloadBytes = decodedPayloadSize(wire.payload),
                                sameReadBatch = raw.sameReadBatch,
                            )
                        )
                    } catch (e: Exception) {
                        // R-08：畸形 event 跳过并计数（后续 seq join 计 gap），绝不静默错位
                        parseErrors++
                    }
                }

                else -> parseErrors++
            }
        }

        // P0-C12：解析完成打戳；parseDurUs/perEventParseUs 由 SseStreamResult 派生输出
        val parseEndNanos = SystemClock.elapsedRealtimeNanos()

        return SseStreamResult(
            prelude = prelude,
            events = events,
            summaryRaw = summaryRaw,
            readCount = readCount,
            totalBytes = totalBytes,
            parseErrors = parseErrors,
            truncatedTail = truncatedTail,
            eofNanos = eofNanos,
            parseEndNanos = parseEndNanos,
        )
    }

    private fun decodedPayloadSize(payload: String): Int =
        try {
            Base64.getDecoder().decode(payload).size
        } catch (e: IllegalArgumentException) {
            // 非 base64（不符合 wire 约定）：退化为原文字节数
            payload.toByteArray(Charsets.UTF_8).size
        }

    companion object {
        private const val READ_CHUNK_BYTES = 8192L

        // 阶段 0 服务端固定 "\n\n" 分隔；"\r\n\r\n" 兼容留 TODO 阶段1
        private val EVENT_DELIMITER = "\n\n".encodeUtf8()
    }
}
