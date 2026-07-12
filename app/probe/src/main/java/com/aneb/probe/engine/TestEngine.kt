package com.aneb.probe.engine

import com.aneb.probe.net.AnebClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlin.random.Random

/**
 * 阶段 0 场景执行器：跑一次 S1（clock_sync → upload_burst 2KB → token_stream）并把
 * 全部时间戳/统计以 Flow<String> 日志形式吐给 UI。
 *
 * TODO(阶段1)：改为读 profiles/ JSON 的通用 PhaseRunner 状态机；三态 Gate 有效性守卫接线；
 * ITL 改在服务端节奏剥离后的残差域计算（R-09）；结果落 Room + 上报。
 */
class TestEngine(private val client: AnebClient) {

    /**
     * @param serverBase 形如 http://10.0.2.2:8443
     * @param tokens     600 为 s1_chat v0.2.0 全量；100 用于快验
     */
    fun runS1(serverBase: String, tokens: Int = 600): Flow<String> = flow {
        val base = serverBase.trim().trimEnd('/')
        // 设计文档 §5：每场景新建连接——运行开始先清空连接池，避免复用上一次运行遗留的
        // TCP/TLS 连接使本次 TTFT/T1 系统性偏低（阶段0验收①"连测 10 次"可比性）。
        client.evictConnections()
        emit("=== S1 run start | profile=s1_chat tokens=$tokens server=$base ===")

        // ---------------- phase 1: clock_sync（echo x20，前 3 个 warmup 丢弃，R-23 去相关间隔） ----------------
        emit("[clock_sync] echo x$ECHO_SAMPLES (first $ECHO_WARMUP = warmup, discarded; interval 100-300ms random)")
        val samples = ArrayList<AnebClient.EchoResult>(ECHO_SAMPLES)
        for (i in 0 until ECHO_SAMPLES) {
            val r = client.echo("$base/api/v1/echo")
            val tag = if (i < ECHO_WARMUP) "warmup" else "sample"
            if (r.error != null) {
                emit("  echo[$i] $tag FAILED: ${r.error} (rtt=null offset=null)") // R-10: null 不记 0
            } else {
                emit("  echo[$i] $tag t0=${r.t0Us}us t1=${r.t1Us} t2=${r.t2Us} t3=${r.t3Us} rtt=${r.rttUs}us offset=${r.offsetUs}us")
                if (i >= ECHO_WARMUP) samples.add(r)
            }
            delay(Random.nextLong(100L, 301L))
        }
        val best = samples.filter { it.rttUs != null }.minByOrNull { it.rttUs!! }
        val offsetUs: Long?
        val offsetErrUs: Long?
        if (best != null) {
            offsetUs = best.offsetUs
            offsetErrUs = best.rttUs!! / 2
            emit("[clock_sync] Cristian min-RTT sample: offset=${offsetUs}us +/- ${offsetErrUs}us (RTT/2), valid=${samples.size}/${ECHO_SAMPLES - ECHO_WARMUP}")
        } else {
            offsetUs = null
            offsetErrUs = null
            emit("[clock_sync] no valid sample -> offset=null (scenario would be invalid)")
        }

        // ---------------- phase 2: upload_burst 2KB（s1_chat: bytes=2048 chunk_kb=2） ----------------
        emit("[upload_burst] POST ${UPLOAD_BYTES}B chunk=${UPLOAD_CHUNK}B")
        val up = client.uploadBurst("$base/api/v1/upload?run=phase0", ByteArray(UPLOAD_BYTES) { 'A'.code.toByte() }, UPLOAD_CHUNK)
        if (up.error != null) {
            emit("  upload FAILED: ${up.error} (u1=null)")
        } else {
            up.chunkStamps.forEach { c ->
                emit("  chunk[${c.index}] ${c.bytes}B wroteAt=+%.2fms (claim: written-to-local-stack, R-07)"
                    .format((c.wroteAtNanos - up.startNanos) / 1e6))
            }
            val endNs = up.timing?.responseHeadersStartNs ?: up.responseNanos
            val durMs = endNs?.let { (it - up.startNanos) / 1e6 }
            emit("  upload endpoint=2xx-response-headers dur=${durMs?.let { "%.2fms".format(it) } ?: "null"} http=${up.httpCode}")
            up.timing?.let { emit("  ${it.summarize()}") }
        }

        // ---------------- phase 3: token_stream ----------------
        emit("[token_stream] GET /api/v1/stream?profile=s1_chat&tokens=$tokens")
        val s = client.runS1Stream(
            "$base/api/v1/stream?profile=s1_chat&run=phase0&tokens=$tokens",
            expectedTokens = tokens, // R-08：尾部截断检测基准（干净结束但总量不足也计 gap）
        )
        if (s.error != null || s.stream == null) {
            emit("  stream FAILED: ${s.error} (TTFT/ITL=null)") // R-10
            emit("=== S1 run ABORTED ===")
            return@flow
        }
        val st = s.stream
        s.timing?.let { emit("  ${it.summarize()}") }
        st.prelude?.let {
            emit("  prelude arrival=+%.2fms raw=%s".format((it.arrivalNanos - s.requestStartNanos) / 1e6, it.raw))
        } ?: emit("  prelude missing (T1 无法剥离服务端 dwell，R-20)")
        emit("  events=${st.events.size} reads=${st.readCount} bytes=${st.totalBytes} parseErrors=${st.parseErrors} truncatedTail=${st.truncatedTail}")

        // TTFT：请求头发出完成 → 首 token 所在 read 到达
        val ordered = st.events.sortedBy { it.seq }
        val ttftOriginNs = s.timing?.requestHeadersEndNs ?: s.requestStartNanos
        val first = ordered.firstOrNull()
        val ttftMs = first?.let { (it.arrivalNanos - ttftOriginNs) / 1e6 }

        // ITL：相邻（按 seq 排序）到达间隔；后一 event 为 sameReadBatch 的间隔是伪 0，剔除（R-04）
        val intervalsNs = ArrayList<Long>(ordered.size)
        var coalesced = 0
        for (k in 1 until ordered.size) {
            if (ordered[k].sameReadBatch) {
                coalesced++
                continue
            }
            intervalsNs.add(ordered[k].arrivalNanos - ordered[k - 1].arrivalNanos)
        }
        intervalsNs.sort()
        val itlMedianMs = percentile(intervalsNs, 0.50)?.div(1e6)
        val itlP95Ms = percentile(intervalsNs, 0.95)?.div(1e6)
        // 阶段 0 简化：stall 用原始到达间隔 >200ms 计数。
        // TODO(阶段1/R-09)：T2/T3/T4 一律改为 seq 对齐的网络贡献残差（到达间隔 − sched_us 发出间隔）。
        val stallCount = intervalsNs.count { it > STALL_THRESHOLD_NS }

        val gapLimit = (tokens * GAP_INVALID_RATIO).toInt().coerceAtLeast(1)
        val gapVerdict = if (s.gapCount > gapLimit) "INVALID (gap>${GAP_INVALID_RATIO * 100}% of tokens, R-08 fail-closed)" else "ok"

        emit("--- S1 summary ---")
        emit("  TTFT           = ${ttftMs?.let { "%.2f ms".format(it) } ?: "null"} (origin=requestHeadersEnd)")
        emit("  ITL median     = ${itlMedianMs?.let { "%.2f ms".format(it) } ?: "null"}  P95 = ${itlP95Ms?.let { "%.2f ms".format(it) } ?: "null"}  (n=${intervalsNs.size}, coalesced excluded=$coalesced)")
        emit("  stalls(>200ms) = $stallCount   [阶段0原始间隔口径，阶段1改残差域 R-09]")
        emit("  seq gaps       = ${s.gapCount} dup=${s.duplicateCount} maxSeq=${s.maxSeq} truncatedEarly=${s.truncatedEarly} -> $gapVerdict")
        emit("  clock offset   = ${offsetUs?.let { "${it}us" } ?: "null"} +/- ${offsetErrUs?.let { "${it}us" } ?: "null"} (RTT/2)")
        emit("=== S1 run complete ===")
    }.flowOn(Dispatchers.IO)

    /** sorted 必须已升序。空列表返回 null（R-10：缺数据即 null）。 */
    private fun percentile(sorted: List<Long>, p: Double): Double? {
        if (sorted.isEmpty()) return null
        val idx = ((sorted.size - 1) * p).toInt()
        return sorted[idx].toDouble()
    }

    companion object {
        private const val ECHO_SAMPLES = 20
        private const val ECHO_WARMUP = 3
        private const val UPLOAD_BYTES = 2048
        private const val UPLOAD_CHUNK = 2048
        private const val STALL_THRESHOLD_NS = 200_000_000L
        private const val GAP_INVALID_RATIO = 0.01
    }
}
