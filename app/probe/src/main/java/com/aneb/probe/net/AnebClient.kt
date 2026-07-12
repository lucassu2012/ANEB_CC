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
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * ANEB 仿真服务器客户端（阶段 0）。
 *
 * OkHttp 配置依据设计文档 §5：
 *  - retryOnConnectionFailure(false)：重试会掩盖网络问题；
 *  - connectTimeout 10s / readTimeout 30s；
 *  - eventListenerFactory 注入 [TimingEventListener]（回调线程就地打戳）。
 *
 * TODO(阶段1)：NetGuard 网络绑定（requestNetwork + socketFactory + Dns=network::getAllByName，
 * R-01）、fail-closed 就绪守卫。（每场景禁连接池复用已由 [evictConnections] 落地。）
 */
class AnebClient {

    private val timingFactory = TimingEventListener.Factory()
    private val json = Json { ignoreUnknownKeys = true }
    private val sseReader = SseReader(json)

    private val client: OkHttpClient = OkHttpClient.Builder()
        .retryOnConnectionFailure(false)
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .eventListenerFactory(timingFactory)
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
    )

    suspend fun echo(url: String): EchoResult {
        val body = "{\"probe\":\"aneb\"}"
            .toRequestBody("application/json".toMediaType())
        val call = client.newCall(Request.Builder().url(url).post(body).build())
        val t0Us = nowUs()
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
                    EchoResult(t0Us, wire.t1Us, wire.t2Us, t3Us, offsetUs, rttUs, resp.code, null, timing)
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
     * @param expectedTokens 调用方（TestEngine）期望的 token 总数（profile 的 tokens 参数），
     *        用于尾部截断检测；seq 从 0 起，完整流应收到 seq ∈ [0, expectedTokens)。
     */
    suspend fun runS1Stream(url: String, expectedTokens: Int): StreamResult {
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
                        checkNotNull(resp.body) { "empty body for 2xx" }.source()
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

    // ---------------------------------------------------------------- upload

    /** 单块写入戳。claim scope＝"写入本地协议栈"（R-07），仅作辅助诊断。 */
    data class ChunkStamp(val index: Int, val bytes: Int, val wroteAtNanos: Long)

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
    )

    suspend fun uploadBurst(url: String, payload: ByteArray, chunkBytes: Int = 2048): UploadResult {
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
                    stamps.add(ChunkStamp(index, len, SystemClock.elapsedRealtimeNanos()))
                    offset += len
                    index++
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
                resp.body?.string() // 排空（服务端返回其视角的逐块到达序列，阶段 0 不解析）
                val error = if (resp.isSuccessful) null else "http ${resp.code}"
                UploadResult(startNanos, responseNanos, stamps, payload.size, resp.code, error, timing)
            }
        } catch (e: CancellationException) {
            throw e // 不吞取消（fail-closed §4.6/§4.7）
        } catch (e: Exception) {
            UploadResult(startNanos, null, stamps, payload.size, null, e.toString(), timingFactory.recordFor(call))
        }
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
}
