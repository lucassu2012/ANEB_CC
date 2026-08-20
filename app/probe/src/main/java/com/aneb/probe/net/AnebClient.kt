package com.aneb.probe.net

import android.os.SystemClock
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okio.BufferedSink
import okio.ByteString.Companion.encodeUtf8
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * ANEB 仿真服务器客户端（阶段 1 接线）。
 *
 * OkHttp 配置依据设计文档 §5：
 *  - retryOnConnectionFailure(false)：重试会掩盖网络问题；
 *  - connectTimeout 10s / readTimeout 30s；
 *  - eventListenerFactory 注入 [TimingEventListener]（回调线程就地打戳）；
 *  - `proxy(Proxy.NO_PROXY)`：测量流量必须直连（D-16 红线）——即使系统留有
 *    代理配置也绝不让测量请求走代理（NetGuard 已在测前硬拒代理，这里是第二道闸）；
 *  - [bound] 非 null 时同时绑定 socketFactory 与 Dns（R-01：否则域名解析仍走默认
 *    网络 DNS，解析与承载路径分裂）。AUTO 模式传 null＝不绑定仅监控。
 */
class AnebClient(bound: BoundNetwork? = null) {

    private val timingFactory = TimingEventListener.Factory()
    private val json = Json { ignoreUnknownKeys = true }
    private val sseReader = SseReader(json)

    private val client: OkHttpClient = OkHttpClient.Builder()
        .retryOnConnectionFailure(false)
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .eventListenerFactory(timingFactory)
        .proxy(java.net.Proxy.NO_PROXY) // D-16：测量流量直连，禁走系统代理
        .apply {
            if (bound != null) {
                socketFactory(bound.socketFactory)
                dns(bound.dns)
            }
        }
        .build()

    /**
     * 清空连接池。设计文档 §5：每场景新建连接，消除 TCP/TLS 连接复用导致的 TTFT/T1
     * 不可比。TestEngine 在每次场景运行开始时调用（阶段0验收①"连测 10 次"可比性）。
     */
    fun evictConnections() {
        client.connectionPool.evictAll()
    }

    // ------------------------------------------------------------------ echo

    @Serializable
    private data class EchoWire(
        @SerialName("t1_us") val t1Us: Long,
        @SerialName("t2_us") val t2Us: Long,
        /** 服务端观察到的客户端源 IP:port（路径对账，R-01/R-31） */
        val observed: String? = null,
        /**
         * 服务端**进程启动时**的真实墙钟（Unix 纳秒）。服务端每次 /echo 都回带
         * （`server/handlers_echo.go:43-44`），客户端此前连声明都没有、静默丢弃——
         * D-503/T64 查明这是全仓唯一能校验设备墙钟的独立参照（D-340 零读者族）。
         *
         * **可空且带默认值**：旧版服务端不回该字段时反序列化不能炸（E-01 现版本已回带，
         * T64 §4 线上实测确认，但客户端不该假设对端一定是新版）。
         */
        @SerialName("anchor_wall_unix_ns") val anchorWallUnixNs: Long? = null,
    )

    /**
     * 一次 /echo 时钟同步样本。时间单位：微秒。
     * t0/t3 为客户端单调钟（elapsedRealtimeNanos/1000）；t1/t2 为服务端单调锚点钟。
     * offset = ((t1-t0)+(t2-t3))/2（服务端钟 − 客户端钟），误差 ±RTT/2（设计文档 §4.2）。
     * 失败样本：t1/t2/offset/rtt 全 null（R-10：绝不记 0）。
     */
    data class EchoResult(
        val t0Us: Long,
        val t1Us: Long?,
        val t2Us: Long?,
        val t3Us: Long?,
        val offsetUs: Long?,
        val rttUs: Long?,
        val httpCode: Int?,
        val error: String?,
        val timing: TimingRecord?,
        /** 服务端观察到的客户端源 IP:port（每场景网络快照的路径对账字段，R-01/R-31） */
        val observed: String? = null,
        /**
         * 设备墙钟 − 服务端墙钟（毫秒，可正可负）。**与 [offsetUs] 是两回事**：
         * 后者是两个单调计数之差（按 R-24 设计就不含墙钟信息，D-503 §3 实证），
         * 本字段才是「钟指得对不对」。服务端未回带 anchor 时为 null（R-10：测不出
         * 是 null，不是 0）。取样时刻＝打 t0 的同一行（不可用 run 起始墙钟做减法，
         * 那与 echo 时刻差着整个 run 前置时长，T64 §8.1）。
         */
        val wallSkewMs: Long? = null,
    )

    suspend fun echo(url: String): EchoResult {
        val body = "{\"probe\":\"aneb\"}"
            .toRequestBody("application/json".toMediaType())
        val call = client.newCall(Request.Builder().url(url).post(body).build())
        val t0Us = nowUs()
        // T64 §8.1：墙钟必须与 t0 同一时刻取——run 起始墙钟（started_at_epoch_ms）与
        // echo 时刻差着整个 run 前置时长，拿它做减法会把前置时长算进 skew。
        val deviceWallMs = System.currentTimeMillis()
        return try {
            executeCancellable(call) { resp ->
                // t3 打戳点＝收到响应头回调（与原 execute() 返回点同语义）
                val t3Us = nowUs()
                val timing = timingFactory.recordFor(call)
                if (!resp.isSuccessful) {
                    EchoResult(t0Us, null, null, t3Us, null, null, resp.code, "http ${resp.code}", timing)
                } else {
                    val wire = json.decodeFromString(
                        EchoWire.serializer(),
                        checkNotNull(resp.body) { "empty body for 2xx" }.string(),
                    )
                    val offsetUs = ((wire.t1Us - t0Us) + (wire.t2Us - t3Us)) / 2
                    val rttUs = (t3Us - t0Us) - (wire.t2Us - wire.t1Us)
                    EchoResult(
                        t0Us, wire.t1Us, wire.t2Us, t3Us, offsetUs, rttUs,
                        resp.code, null, timing, observed = wire.observed,
                        wallSkewMs = wallSkewMs(wire.anchorWallUnixNs, wire.t1Us, deviceWallMs),
                    )
                }
            }
        } catch (e: CancellationException) {
            throw e // 不吞取消（fail-closed §4.6/§4.7）
        } catch (e: Exception) {
            EchoResult(t0Us, null, null, null, null, null, null, e.toString(), timingFactory.recordFor(call))
        }
    }

    // ---------------------------------------------------------------- stream

    /**
     * S1 流式结果。gap/duplicate 由 seq join 校验（R-08）：
     * gapCount = [0..maxSeq] 中缺失的 seq 数 + 尾部截断缺失数（见 [StreamResult.truncatedEarly]）；
     * gap 超过 token 总数 1% 由上层判 invalid。
     */
    data class StreamResult(
        val requestStartNanos: Long,
        val stream: SseStreamResult?,
        val gapCount: Int,
        val duplicateCount: Int,
        val maxSeq: Long?,
        val httpCode: Int?,
        val error: String?,
        val timing: TimingRecord?,
        /**
         * 流无 HTTP 错误、无异常地"干净结束"，但收到的 token 总量 < expectedTokens：
         * 服务端/中间盒提前正常关闭连接导致的尾部整体截断（R-08 漏检分支——区间内部
         * 连续性检查测不出 [maxSeq+1, expectedTokens) 的整体缺失）。
         * 缺失数已计入 [gapCount]，参与上层 >1% invalid 判定。
         */
        val truncatedEarly: Boolean,
    )

    /**
     * 通用 SSE 流阶段执行（S1/S2/S3 的 token_stream phase 共用）。
     *
     * @param expectedTokens 调用方（ScenarioRunner）期望的 token 总数（profile 的 tokens 参数），
     *        用于尾部截断检测；seq 从 0 起，完整流应收到 seq ∈ [0, expectedTokens)。
     */
    suspend fun stream(url: String, expectedTokens: Int, onProgress: ((Int, Long) -> Unit)? = null): StreamResult {
        val call = client.newCall(
            Request.Builder().url(url).header("Accept", "text/event-stream").get().build()
        )
        val requestStartNanos = SystemClock.elapsedRealtimeNanos()
        return try {
            // SSE body 的流式读取整体放在 executeCancellable 的 onResponse 回调内完成
            // （resume 前不关闭 body）：invokeOnCancellation 覆盖从建连到读完的全程，
            // 协程取消 → call.cancel() → 读循环以 IOException 退出（fail-closed §4.6/§4.7）。
            executeCancellable(call) { resp ->
                if (!resp.isSuccessful) {
                    StreamResult(
                        requestStartNanos, null, 0, 0, null,
                        resp.code, "http ${resp.code}", timingFactory.recordFor(call),
                        truncatedEarly = false,
                    )
                } else {
                    val stream = sseReader.readStream(
                        checkNotNull(resp.body) { "empty body for 2xx" }.source(),
                        onProgress,
                    )
                    val timing = timingFactory.recordFor(call)

                    // R-08：按 seq join 校验连续性，禁数组位置配对
                    val seen = HashSet<Long>(stream.events.size * 2)
                    var duplicates = 0
                    for (e in stream.events) {
                        if (!seen.add(e.seq)) duplicates++
                    }
                    val maxSeq = seen.maxOrNull()
                    var gaps = 0
                    if (maxSeq != null) {
                        var s = 0L
                        while (s <= maxSeq) {
                            if (s !in seen) gaps++
                            s++
                        }
                    }
                    // R-08 截断漏检补丁：流干净结束但 maxSeq+1 < expectedTokens 时，
                    // 尾部整体缺失也计入 gapCount（否则 gapVerdict 会误判 ok）。
                    val received = maxSeq?.plus(1L) ?: 0L
                    val tailMissing = (expectedTokens - received).coerceAtLeast(0L).toInt()
                    gaps += tailMissing
                    StreamResult(
                        requestStartNanos, stream, gaps, duplicates, maxSeq, resp.code, null, timing,
                        truncatedEarly = tailMissing > 0,
                    )
                }
            }
        } catch (e: CancellationException) {
            throw e // 不吞取消（fail-closed §4.6/§4.7）
        } catch (e: Exception) {
            StreamResult(
                requestStartNanos, null, 0, 0, null, null, e.toString(),
                timingFactory.recordFor(call), truncatedEarly = false,
            )
        }
    }

    // ------------------------------------------- continuity stream（阶段 2 C 组）

    /**
     * 连续性实验专用流结果（阶段 2 C 组；additive——不改 [stream] 既有测量语义）。
     * 与 [stream] 的关键差异：**中断容忍**——传输层异常（IOException/流截断）时已收
     * token 的计数与到达时间戳全部保留（C1/C2 的测量对象正是中断本身），并在检出
     * 中断的当下打戳 [errorNanos]（C2 恢复计时的起点）。
     *
     * 时间戳全部为 SystemClock.elapsedRealtimeNanos（单调时间轴，读线程就地打戳）。
     */
    data class ContinuityStreamResult(
        val startNanos: Long,
        /** 首个 token event 到达时刻；一个 token 都没收到记 null（R-10） */
        val firstTokenNanos: Long?,
        /** 最后一个 SSE event 到达时刻（中断兜底锚点）；无 event 记 null */
        val lastEventNanos: Long?,
        val tokenCount: Int,
        val maxSeq: Long?,
        /** 收到 summary event（服务端正常收尾标志） */
        val sawSummary: Boolean,
        val httpCode: Int?,
        val error: String?,
        /** 传输错误检出时刻；无错误记 null */
        val errorNanos: Long?,
        val timing: TimingRecord?,
    ) {
        /** 流干净收尾：无传输错误且收到 summary；否则即"异常断开/截断"（C1 证据） */
        val completed: Boolean get() = error == null && sawSummary

        /** 本请求是否新建连接（EventListener 有 connectStart 打点即新建）；无计时记录 null */
        val connectionWasNew: Boolean? get() = timing?.let { it.connectStartNs != null }
    }

    /**
     * 连续性长流（C1/C2）：增量读 SSE，逐 event 打戳，只做轻量解析（token 计数 /
     * seq 提取 / summary 检测——恢复时间是秒级量，正则开销可忽略）。
     */
    suspend fun continuityStream(url: String): ContinuityStreamResult {
        val call = client.newCall(
            Request.Builder().url(url).header("Accept", "text/event-stream").get().build()
        )
        val startNanos = SystemClock.elapsedRealtimeNanos()
        return try {
            executeCancellable(call) { resp ->
                if (!resp.isSuccessful) {
                    ContinuityStreamResult(
                        startNanos, null, null, 0, null, sawSummary = false,
                        httpCode = resp.code, error = "http ${resp.code}",
                        errorNanos = SystemClock.elapsedRealtimeNanos(),
                        timing = timingFactory.recordFor(call),
                    )
                } else {
                    val source = checkNotNull(resp.body) { "empty body for 2xx" }.source()
                    var firstTokenNanos: Long? = null
                    var lastEventNanos: Long? = null
                    var tokenCount = 0
                    var maxSeq: Long? = null
                    var sawSummary = false
                    var error: String? = null
                    var errorNanos: Long? = null
                    val acc = okio.Buffer()
                    val readBuf = okio.Buffer()
                    try {
                        while (true) {
                            val n = source.read(readBuf, 8192L)
                            if (n == -1L) break
                            val arrival = SystemClock.elapsedRealtimeNanos()
                            acc.writeAll(readBuf)
                            while (true) {
                                val boundary = acc.indexOf(SSE_EVENT_DELIMITER)
                                if (boundary == -1L) break
                                val eventText = acc.readByteArray(boundary).toString(Charsets.UTF_8)
                                acc.skip(SSE_EVENT_DELIMITER.size.toLong())
                                if (eventText.isEmpty()) continue
                                lastEventNanos = arrival
                                when {
                                    eventText.startsWith("event: summary") -> sawSummary = true
                                    eventText.startsWith("event: token") -> {
                                        tokenCount++
                                        if (firstTokenNanos == null) firstTokenNanos = arrival
                                        SEQ_REGEX.find(eventText)?.groupValues?.get(1)
                                            ?.toLongOrNull()?.let { s ->
                                                if (maxSeq == null || s > maxSeq!!) maxSeq = s
                                            }
                                    }
                                    // prelude 注释帧等：连续性实验不做 KPI 级解析，跳过
                                }
                            }
                        }
                    } catch (e: IOException) {
                        // 中断容忍：部分数据保留 + 中断时刻就地打戳（C2 恢复计时起点）
                        error = e.toString()
                        errorNanos = SystemClock.elapsedRealtimeNanos()
                    }
                    ContinuityStreamResult(
                        startNanos, firstTokenNanos, lastEventNanos, tokenCount, maxSeq,
                        sawSummary, resp.code, error, errorNanos, timingFactory.recordFor(call),
                    )
                }
            }
        } catch (e: CancellationException) {
            throw e // 不吞取消（fail-closed §4.6/§4.7）
        } catch (e: Exception) {
            // 建连级失败（连接拒绝/无网等）：错误时刻同样打戳
            ContinuityStreamResult(
                startNanos, null, null, 0, null, sawSummary = false,
                httpCode = null, error = e.toString(),
                errorNanos = SystemClock.elapsedRealtimeNanos(),
                timing = timingFactory.recordFor(call),
            )
        }
    }

    // ---------------------------------------------------------------- upload

    /** 单块写入戳。claim scope＝"写入本地协议栈"（R-07），仅作辅助诊断。 */
    data class ChunkStamp(val index: Int, val bytes: Int, val wroteAtNanos: Long)

    /**
     * /upload 响应体（服务端视角的权威逐块到达序列，R-07）。
     * chunk_us 供慢启动爬坡估计（U1 剔慢启动并列口径）。
     */
    @Serializable
    data class UploadServerView(
        val bytes: Long = -1,
        @SerialName("recv_start_us") val recvStartUs: Long = -1,
        @SerialName("recv_end_us") val recvEndUs: Long = -1,
        @SerialName("chunk_us") val chunkUs: List<Long> = emptyList(),
        val observed: String? = null,
    )

    /**
     * 上行突发结果。U1 计时终点＝收到 2xx 响应头（服务端已读完 body，R-07）：
     * 权威终点取 timing.responseHeadersStartNs；responseNanos 为响应头回调打戳的兜底值。
     */
    data class UploadResult(
        val startNanos: Long,
        val responseNanos: Long?,
        val chunkStamps: List<ChunkStamp>,
        val totalBytes: Int,
        val httpCode: Int?,
        val error: String?,
        val timing: TimingRecord?,
        /** 服务端视角逐块到达序列；解析失败/非 2xx 记 null（R-10） */
        val serverView: UploadServerView? = null,
    )

    suspend fun uploadBurst(
        url: String,
        payload: ByteArray,
        chunkBytes: Int = 2048,
        /** 逐块回调（累计已写字节, 打戳纳秒）：供基本性能模式实时算上行吞吐。写入本地 socket
         * buffer 时刻，buffer 填满后写入节奏≈真实网络上行速率（R-07 同口径，观测用）。 */
        onChunk: ((Long, Long) -> Unit)? = null,
    ): UploadResult {
        val stamps = ArrayList<ChunkStamp>(payload.size / chunkBytes + 1)
        val body = object : RequestBody() {
            override fun contentType() = "application/octet-stream".toMediaType()
            override fun contentLength(): Long = payload.size.toLong()
            override fun writeTo(sink: BufferedSink) {
                var offset = 0
                var index = 0
                while (offset < payload.size) {
                    val len = minOf(chunkBytes, payload.size - offset)
                    sink.write(payload, offset, len)
                    sink.flush()
                    // 注意：这测的是写入本地 socket buffer 的时刻，不是线上发出时刻（R-07）
                    val ns = SystemClock.elapsedRealtimeNanos()
                    stamps.add(ChunkStamp(index, len, ns))
                    offset += len
                    index++
                    onChunk?.invoke(offset.toLong(), ns)
                }
            }
        }
        val call = client.newCall(Request.Builder().url(url).post(body).build())
        val startNanos = SystemClock.elapsedRealtimeNanos()
        return try {
            executeCancellable(call) { resp ->
                // 打戳点＝收到响应头回调（与原 execute() 返回点同语义）
                val responseNanos = SystemClock.elapsedRealtimeNanos()
                val timing = timingFactory.recordFor(call)
                val bodyText = resp.body?.string() // 排空 + 解析服务端视角逐块到达序列（R-07 权威序列）
                val serverView = if (resp.isSuccessful && bodyText != null) {
                    try {
                        json.decodeFromString(UploadServerView.serializer(), bodyText)
                    } catch (e: Exception) {
                        null // 解析失败：serverView=null，慢启动口径退化为 null（R-10）
                    }
                } else {
                    null
                }
                val error = if (resp.isSuccessful) null else "http ${resp.code}"
                UploadResult(
                    startNanos, responseNanos, stamps, payload.size, resp.code, error, timing,
                    serverView = serverView,
                )
            }
        } catch (e: CancellationException) {
            throw e // 不吞取消（fail-closed §4.6/§4.7）
        } catch (e: Exception) {
            UploadResult(startNanos, null, stamps, payload.size, null, e.toString(), timingFactory.recordFor(call))
        }
    }

    /**
     * 语音帧节奏上行（M3，观测口径，PROFILE_FRAMEWORK §4.1）：按 [intervalMs] 节奏逐帧
     * 写入并 flush（模拟 Opus ~20ms/帧小包流），服务端 /upload 的 chunk_us 权威到达序列
     * 供上行帧间抖动计算。写线程 sleep 造节奏——客户端调度抖动叠加进测得帧抖动
     * （观测上界，口径注明）。复用 [UploadResult]（stamps/serverView 同构）。
     */
    suspend fun uploadPaced(
        url: String,
        frames: Int,
        frameBytes: Int,
        intervalMs: Long,
        onFrame: ((Int, Long) -> Unit)? = null,
    ): UploadResult {
        val stamps = ArrayList<ChunkStamp>(frames)
        val frame = ByteArray(frameBytes) { 'V'.code.toByte() }
        val body = object : RequestBody() {
            override fun contentType() = "application/octet-stream".toMediaType()
            override fun contentLength(): Long = (frames * frameBytes).toLong()
            override fun writeTo(sink: BufferedSink) {
                for (i in 0 until frames) {
                    sink.write(frame)
                    sink.flush()
                    val ns = SystemClock.elapsedRealtimeNanos()
                    stamps.add(ChunkStamp(i, frameBytes, ns))
                    onFrame?.invoke(i + 1, ns)
                    if (i < frames - 1) Thread.sleep(intervalMs)
                }
            }
        }
        val call = client.newCall(Request.Builder().url(url).post(body).build())
        val startNanos = SystemClock.elapsedRealtimeNanos()
        return try {
            executeCancellable(call) { resp ->
                val responseNanos = SystemClock.elapsedRealtimeNanos()
                val timing = timingFactory.recordFor(call)
                val bodyText = resp.body?.string()
                val serverView = if (resp.isSuccessful && bodyText != null) {
                    try {
                        json.decodeFromString(UploadServerView.serializer(), bodyText)
                    } catch (e: Exception) {
                        null // 解析失败：serverView=null（R-10）
                    }
                } else {
                    null
                }
                val error = if (resp.isSuccessful) null else "http ${resp.code}"
                UploadResult(
                    startNanos, responseNanos, stamps, frames * frameBytes, resp.code, error, timing,
                    serverView = serverView,
                )
            }
        } catch (e: CancellationException) {
            throw e // 不吞取消（fail-closed §4.6/§4.7）
        } catch (e: Exception) {
            UploadResult(startNanos, null, stamps, frames * frameBytes, null, e.toString(), timingFactory.recordFor(call))
        }
    }

    // -------------------------------------------------------------- download

    data class DownloadResult(
        val startNanos: Long,
        /** body 读完/中断时刻；异常无值记 null（R-10） */
        val bodyEndNanos: Long?,
        val bytesRead: Long,
        val httpCode: Int?,
        val error: String?,
    )

    /**
     * 基本性能模式：下行大对象排空。GET（含 ?bytes=N），按 256KB 读并逐块回调
     * (累计已读字节, 打戳纳秒)——**读到的字节即真实到达的网络字节**（无上行那种写本地 socket
     * buffer 的灌注偏差，是比上行更纯净的吞吐口径）。读完即丢（只测吞吐，不留内容）。
     * 协程取消 → call.cancel() → 服务端随 request context 退出。观测用，不进 AQS。
     */
    suspend fun downloadDrain(
        url: String,
        onChunk: ((Long, Long) -> Unit)? = null,
    ): DownloadResult {
        val call = client.newCall(Request.Builder().url(url).get().build())
        val startNanos = SystemClock.elapsedRealtimeNanos()
        return try {
            executeCancellable(call) { resp ->
                if (!resp.isSuccessful) {
                    DownloadResult(startNanos, null, 0L, resp.code, "http ${resp.code}")
                } else {
                    val source = checkNotNull(resp.body) { "empty body for 2xx" }.source()
                    val readBuf = okio.Buffer()
                    var total = 0L
                    var err: String? = null
                    try {
                        while (true) {
                            val n = source.read(readBuf, 262_144L) // 256KB/次
                            if (n == -1L) break
                            readBuf.clear() // 只测吞吐，读到即丢
                            total += n
                            onChunk?.invoke(total, SystemClock.elapsedRealtimeNanos())
                        }
                    } catch (e: IOException) {
                        err = e.toString() // 取消/中断：保留已读字节，就地记错
                    }
                    DownloadResult(startNanos, SystemClock.elapsedRealtimeNanos(), total, resp.code, err)
                }
            }
        } catch (e: CancellationException) {
            throw e // 不吞取消（fail-closed §4.6/§4.7）
        } catch (e: Exception) {
            DownloadResult(startNanos, null, 0L, null, e.toString())
        }
    }

    /**
     * 单流自适应窗口 goodput 探针产出（U3/D3，T47 批③，D-468/D-469；
     * spec/PROFILE2_THROUGHPUT_PROBE_SPEC.md §8.3.2）。
     * @param windowUnderrun true=传输在窗口到点前已自然结束（服务端 ceiling 先到/写满 maxBytes），
     *   不是"到点截断"——KpiCalculator 需要区分这两种停止原因（spec §8.3.3 已知边界情形）。
     */
    data class WindowTransferResult(
        val startNanos: Long,
        /** 窗口到点/流自然结束/异常中断的时刻；异常无法打戳记 null（R-10） */
        val endNanos: Long?,
        val bytesTransferred: Long,
        val httpCode: Int?,
        val error: String?,
        val windowUnderrun: Boolean,
    )

    /**
     * 下行自适应窗口排空（D3）：GET（含 `?bytes=N` ceiling），到 [windowMs] 即
     * `call.cancel()` 并停止——不像 [downloadDrain] 那样一直读到服务端自然结束。
     * 逐块回调 (累计已读字节, 打戳纳秒) 供 [com.aneb.probe.engine.TransferWindowAnalysis]
     * 做慢启动检测（口径同 downloadDrain：读到的字节即真实到达的网络字节）。
     */
    suspend fun downloadWindow(
        url: String,
        windowMs: Long,
        onChunk: ((Long, Long) -> Unit)? = null,
    ): WindowTransferResult {
        val call = client.newCall(Request.Builder().url(url).get().build())
        val startNanos = SystemClock.elapsedRealtimeNanos()
        val deadlineNanos = startNanos + windowMs * 1_000_000L
        return try {
            executeCancellable(call) { resp ->
                if (!resp.isSuccessful) {
                    WindowTransferResult(startNanos, null, 0L, resp.code, "http ${resp.code}", windowUnderrun = false)
                } else {
                    val source = checkNotNull(resp.body) { "empty body for 2xx" }.source()
                    val readBuf = okio.Buffer()
                    var total = 0L
                    var err: String? = null
                    var underrun = false
                    var endNanos = startNanos
                    try {
                        while (true) {
                            val now = SystemClock.elapsedRealtimeNanos()
                            if (now >= deadlineNanos) {
                                call.cancel() // 窗口到点：主动收线，不等服务端 ceiling
                                endNanos = now
                                break
                            }
                            val n = source.read(readBuf, 262_144L) // 256KB/次
                            if (n == -1L) {
                                underrun = true // 流早于窗口自然结束（服务端 ceiling 先到）
                                endNanos = SystemClock.elapsedRealtimeNanos()
                                break
                            }
                            readBuf.clear() // 只测吞吐，读到即丢
                            total += n
                            endNanos = SystemClock.elapsedRealtimeNanos()
                            onChunk?.invoke(total, endNanos)
                        }
                    } catch (e: IOException) {
                        err = e.toString() // 真实传输中断（非窗口到点触发的 cancel）：就地记错
                        endNanos = SystemClock.elapsedRealtimeNanos()
                    }
                    WindowTransferResult(startNanos, endNanos, total, resp.code, err, underrun)
                }
            }
        } catch (e: CancellationException) {
            throw e // 不吞取消（fail-closed §4.6/§4.7）
        } catch (e: Exception) {
            WindowTransferResult(startNanos, null, 0L, null, e.toString(), windowUnderrun = false)
        }
    }

    /**
     * 上行自适应窗口发送（U3）：chunked 请求体（`contentLength()=-1`，不预知总量——
     * 与 [uploadBurst] 的精确字节数语义不同），到 [windowMs] 或 [maxBytes] ceiling
     * 先到者即停止写入并正常结束请求体（不需要 call.cancel()：提前 return 出
     * writeTo() 天然结束 chunked 流，服务端按已收到的字节数正常响应）。
     */
    suspend fun uploadWindow(
        url: String,
        windowMs: Long,
        maxBytes: Long,
        chunkBytes: Int = 65536,
        onChunk: ((Long, Long) -> Unit)? = null,
    ): WindowTransferResult {
        val startNanos = SystemClock.elapsedRealtimeNanos()
        val deadlineNanos = startNanos + windowMs * 1_000_000L
        var written = 0L
        var underrun = false
        var endNanos = startNanos
        val chunk = ByteArray(chunkBytes.coerceAtLeast(1)) { 'A'.code.toByte() }
        val body = object : RequestBody() {
            override fun contentType() = "application/octet-stream".toMediaType()
            override fun contentLength(): Long = -1L // 窗口化：不预知总传输量，走 chunked
            override fun writeTo(sink: BufferedSink) {
                while (written < maxBytes) {
                    val now = SystemClock.elapsedRealtimeNanos()
                    if (now >= deadlineNanos) {
                        endNanos = now
                        return // 窗口到点：正常结束 chunked 流，不写剩余字节
                    }
                    val len = minOf(chunk.size.toLong(), maxBytes - written).toInt()
                    sink.write(chunk, 0, len)
                    sink.flush()
                    written += len
                    endNanos = SystemClock.elapsedRealtimeNanos()
                    onChunk?.invoke(written, endNanos)
                }
                underrun = true // 写满 maxBytes ceiling，窗口尚未到点
                endNanos = SystemClock.elapsedRealtimeNanos()
            }
        }
        val call = client.newCall(Request.Builder().url(url).post(body).build())
        return try {
            executeCancellable(call) { resp ->
                val error = if (resp.isSuccessful) null else "http ${resp.code}"
                resp.body?.close()
                WindowTransferResult(startNanos, endNanos, written, resp.code, error, underrun)
            }
        } catch (e: CancellationException) {
            throw e // 不吞取消（fail-closed §4.6/§4.7）
        } catch (e: Exception) {
            WindowTransferResult(startNanos, endNanos, written, null, e.toString(), underrun)
        }
    }

    // ------------------------------------------------------ synthetic probe

    /**
     * 合成弱网路径探针结果（D-40，weak-recovery-v1 等合同）。
     * @param impairmentHeader 防伪回执 `X-Aneb-Synthetic-Impairment`（成功响应必须携带，缺失→INVALID）
     * @param outageHeader 受控中断标记 `X-Aneb-Synthetic-Outage`（窗口内 503 携带 "active"）
     */
    data class SyntheticProbeResult(
        val httpCode: Int?,
        /** 请求发出→响应头收到 墙钟（ms）；传输失败 null（R-10） */
        val wallMs: Double?,
        val error: String?,
        val impairmentHeader: String?,
        val outageHeader: String?,
        val body: String?,
    )

    /**
     * 合成路径 POST 探针（echo/recovery 触发共用）：小体 POST，捕获回执头与墙钟。
     * 观测口径（合成整形路径），不进 N1/AQS。
     */
    suspend fun syntheticPost(url: String, payload: String = "ping"): SyntheticProbeResult {
        val call = client.newCall(
            Request.Builder().url(url)
                .post(payload.toRequestBody("text/plain".toMediaType()))
                .build()
        )
        val t0 = SystemClock.elapsedRealtimeNanos()
        return try {
            executeCancellable(call) { resp ->
                val wallMs = (SystemClock.elapsedRealtimeNanos() - t0) / 1e6
                SyntheticProbeResult(
                    httpCode = resp.code,
                    wallMs = wallMs,
                    error = null,
                    impairmentHeader = resp.header("X-Aneb-Synthetic-Impairment"),
                    outageHeader = resp.header("X-Aneb-Synthetic-Outage"),
                    body = resp.body?.string()?.take(512),
                )
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            SyntheticProbeResult(null, null, e.toString(), null, null, null)
        }
    }

    // ---------------------------------------------------------- realtime-sim

    /**
     * `/realtime-sim` 会话工厂（D-38，语音 server-sim 口径）：**复用本 client 的 OkHttpClient**，
     * 自动继承三红线——NO_PROXY（D-16）、绑定网 socketFactory/Dns（R-01）、
     * retryOnConnectionFailure(false)。禁止绕过本工厂自建 WS client。
     */
    fun realtimeSim(
        base: String,
        plan: RealtimeWire.SessionPlan,
        disconnectAfterTurn: Int? = null,
    ): RealtimeSimSession {
        val wsUrl = base.trim().trimEnd('/')
            .replaceFirst("https://", "wss://")
            .replaceFirst("http://", "ws://") +
            "/api/v1/realtime-sim" +
            (disconnectAfterTurn?.let { "?controlled_disconnect_after_turn=$it" } ?: "")
        val planJson = RealtimeWire.jsonOut.encodeToString(RealtimeWire.SessionPlan.serializer(), plan)
        return RealtimeSimSession(client, wsUrl, planJson)
    }

    // -------------------------------------------------------------- toolloop

    /**
     * 一轮工具循环结果（U2）。端到端终点＝下行 body 读完（2KB 全收到）。
     * trecv/tsend 来自响应头 X-Aneb-Trecv-Us / X-Aneb-Tsend-Us（服务端单调锚点 us）；
     * 实际 serverProc = tsend − trecv（比名义 200ms 更准，供 U2 剥离）。
     */
    data class ToolLoopResult(
        val startNanos: Long,
        /** 下行 body 读完时刻；失败记 null（R-10） */
        val bodyEndNanos: Long?,
        val downBytes: Long?,
        val trecvUs: Long?,
        val tsendUs: Long?,
        val httpCode: Int?,
        val error: String?,
        val timing: TimingRecord?,
    )

    suspend fun toolLoop(url: String, upBytes: Int): ToolLoopResult {
        val payload = ByteArray(upBytes) { 'T'.code.toByte() }
        val call = client.newCall(
            Request.Builder().url(url)
                .post(payload.toRequestBody("application/octet-stream".toMediaType()))
                .build()
        )
        val startNanos = SystemClock.elapsedRealtimeNanos()
        return try {
            executeCancellable(call) { resp ->
                val timing = timingFactory.recordFor(call)
                if (!resp.isSuccessful) {
                    resp.body?.string()
                    ToolLoopResult(startNanos, null, null, null, null, resp.code, "http ${resp.code}", timing)
                } else {
                    val body = checkNotNull(resp.body) { "empty body for 2xx" }.bytes()
                    val bodyEndNanos = SystemClock.elapsedRealtimeNanos() // 端到端终点＝body 读完
                    val trecv = resp.header("X-Aneb-Trecv-Us")?.toLongOrNull()
                    val tsend = resp.header("X-Aneb-Tsend-Us")?.toLongOrNull()
                    ToolLoopResult(
                        startNanos, bodyEndNanos, body.size.toLong(), trecv, tsend,
                        resp.code, null, timing,
                    )
                }
            }
        } catch (e: CancellationException) {
            throw e // 不吞取消（fail-closed §4.6/§4.7）
        } catch (e: Exception) {
            ToolLoopResult(startNanos, null, null, null, null, null, e.toString(), timingFactory.recordFor(call))
        }
    }

    // -------------------------------------------- profiles / results（控制面）

    /** 控制面简单响应（profiles 拉取 / results 上报共用）。 */
    data class HttpTextResult(val httpCode: Int?, val body: String?, val error: String?)

    /** GET /api/v1/profiles（P1 范围 1：拉不到用打包内置 assets 副本并告警） */
    suspend fun fetchProfiles(url: String): HttpTextResult =
        simpleCall(client.newCall(Request.Builder().url(url).get().build()))

    /** POST /api/v1/results（P1 范围 8：400 时 body 含 errors 清单，调用方打日志） */
    suspend fun postResults(url: String, jsonBody: String): HttpTextResult =
        simpleCall(
            client.newCall(
                Request.Builder().url(url)
                    .post(jsonBody.toRequestBody("application/json".toMediaType()))
                    .build()
            )
        )

    private suspend fun simpleCall(call: Call): HttpTextResult = try {
        executeCancellable(call) { resp ->
            val body = resp.body?.string()
            HttpTextResult(resp.code, body, if (resp.isSuccessful) null else "http ${resp.code}")
        }
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        HttpTextResult(null, null, e.toString())
    } finally {
        timingFactory.recordFor(call) // 控制面不计时，但必须取走记录防泄漏
    }

    // ------------------------------------------------- cancellable execution

    /**
     * 以可取消方式执行 [call]，并在 OkHttp 调度线程的 onResponse 回调内就地消费响应
     * （含流式 body 读取），suspend 等待 [consume] 的结果。
     *
     * 取消链路（fail-closed，设计文档 §4.6/§4.7）：协程取消 → invokeOnCancellation →
     * call.cancel() → 底层 socket 关闭 → consume 内的阻塞读以 IOException 退出；此时
     * continuation 已处于 cancelled 状态，resume/resumeWithException 按协程语义被忽略。
     *
     * 之所以把 consume 放进 onResponse（而非 resume 出 Response 后再读 body）：若 resume
     * 后才读流，invokeOnCancellation 只覆盖挂起等待响应头的窗口，body 读循环期间的协程
     * 取消无法再触达 call.cancel()，SSE 长流最长会拖满 readTimeout 30s。
     *
     * 计时语义不变：所有打戳仍用 SystemClock.elapsedRealtimeNanos()，回调线程与原先
     * flowOn(Dispatchers.IO) 的执行线程同为后台线程（TimingEventListener 本就在
     * OkHttp 回调线程打戳）。
     */
    private suspend fun <T> executeCancellable(call: Call, consume: (Response) -> T): T =
        suspendCancellableCoroutine { cont ->
            cont.invokeOnCancellation { call.cancel() }
            call.enqueue(object : Callback {
                override fun onFailure(call: Call, e: IOException) {
                    if (!cont.isCancelled) cont.resumeWithException(e)
                }

                override fun onResponse(call: Call, response: Response) {
                    val result = try {
                        response.use(consume)
                    } catch (e: Exception) {
                        if (!cont.isCancelled) cont.resumeWithException(e)
                        return
                    }
                    if (!cont.isCancelled) cont.resume(result)
                }
            })
        }

    private fun nowUs(): Long = SystemClock.elapsedRealtimeNanos() / 1_000L

    companion object {
        /** 服务端固定 "\n\n" 分隔（与 SseReader 同一 wire 约定） */
        private val SSE_EVENT_DELIMITER = "\n\n".encodeUtf8()
        private val SEQ_REGEX = Regex("\"seq\"\\s*:\\s*(\\d+)")

        /**
         * 判 `wall_clock_suspect` 的阈值（毫秒，D-506 裁定 60s；**PROVISIONAL**）。
         *
         * **这个常量不敏感，别以为 60000 是标定出来的**（T64 §8.4 明写要把这句写进代码）：
         * 两侧硬约束差约三个数量级——下界须**高于**正常网络/NTP 抖动（本项目实测 RTT
         * 上界 106ms，T63 §1；NTP 日常偏差 <1s），上界须**低于**任何足以毁掉判读的偏差
         * （按日分桶只要错 1 天＝8.64e7 ms 结论就全错）。区间极宽，故取 60s 只需落在
         * 区间内，不必精调；有真实 skew 分布支撑前维持 PROVISIONAL。
         */
        const val WALL_SKEW_MAX_MS: Long = 60_000L

        /**
         * 由 echo 响应还原「设备墙钟 − 服务端墙钟」（毫秒，可正可负）。纯函数，离线可单测。
         *
         * `serverWallMs = anchorWallUnixNs/1e6 + t1Us/1e3`——anchor 是服务端进程启动时的
         * 墙钟，t1 是该请求到达时距进程启动的单调微秒差（T64 §8.1，还原式经线上实测验证）。
         *
         * @param anchorWallUnixNs 服务端进程启动墙钟；null（旧服务端不回带）⇒ 返回 null
         * @param t1Us 服务端接收时刻（单调锚点微秒）
         * @param deviceWallMs 客户端打 t0 的**同一时刻**取的 `System.currentTimeMillis()`
         * @return skew；测不出为 null（R-10：不是 0）
         */
        fun wallSkewMs(anchorWallUnixNs: Long?, t1Us: Long, deviceWallMs: Long): Long? {
            if (anchorWallUnixNs == null) return null
            val serverWallMs = anchorWallUnixNs / 1_000_000L + t1Us / 1_000L
            return deviceWallMs - serverWallMs
        }

        /**
         * 墙钟是否可疑。**标记非否决**（D-506）：KPI 计时全走单调钟（R-24），墙钟错
         * 不污染 KPI 值、只污染"哪天测的"。skew 为 null（测不出）⇒ false，不因缺证据判疑。
         */
        fun wallClockSuspect(skewMs: Long?): Boolean =
            skewMs != null && kotlin.math.abs(skewMs) > WALL_SKEW_MAX_MS
    }
}
