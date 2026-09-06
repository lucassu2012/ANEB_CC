package com.aneb.probe.net

import kotlinx.serialization.json.Json
import okio.Buffer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * [SseReader] 对**畸形 event** 的处置（R-08：跳过并计数，绝不静默错位）。
 * 对应服务端 `?inject=malformed:N` 那一路（`server/handlers_stream.go:182`）。
 *
 * 🔴 **为什么此前零覆盖，以及那个理由早就不成立了**：
 * 同目录的 [SseReaderHardeningTest] 逐字写着「不经 [SseReader.readRaw]/[SseReader.parseRaw]：
 * 两者内部都直接调用 `SystemClock.elapsedRealtimeNanos()` 打戳，**本仓无 Robolectric**，
 * 纯 JVM 单测会抛 not mocked」。那句话写于 `fb82de4`（2026-08-04）时是对的；
 * 而 **Robolectric 已于 `186d1b7`（2026-08-20，D-526）引入**，同目录的
 * [NetGuardPowerMetadataTest] 就在用它。
 * ⇒ **一条被记录的障碍，在它被解除之后仍挡着人**——没有人回头问「那条限制当初挡住了什么」。
 * 本文件即是回头把它拿掉：`@RunWith(RobolectricTestRunner)` 之后，
 * `parseRaw` 的打戳一行不用改就能在 JVM 上跑。
 *
 * ⚠ 既有的 14 处 `parseErrors` 断言**全部落在 `apiprobe/` 的 OpenAI／Anthropic 适配器**
 * （另一个解析器）；`SseReader` 自己的那个计数，在本文件之前没有任何断言。
 */
@RunWith(RobolectricTestRunner::class)
class SseReaderMalformedTest {

    private val reader = SseReader(Json { ignoreUnknownKeys = true })

    private fun tokenEvent(seq: Long, payload: String = "x") =
        """event: token
data: {"seq":$seq,"sched_us":${seq * 20_000},"pre_flush_us":${seq * 20_000},"payload":"$payload"}"""

    /** 事件以 `\n\n` 分隔（同 [SseReader] 的 wire 约定）；末尾补一个分隔符使缓冲清空。 */
    private fun stream(vararg events: String) =
        Buffer().writeUtf8(events.joinToString("\n\n") + "\n\n")

    @Test
    fun `畸形 event 跳过并计数_且后续 event 的 seq 不移位`() {
        // seq 1 那一条的 data 是坏 JSON；0 与 2 完好。
        val r = reader.readStream(
            stream(
                tokenEvent(0),
                "event: token\ndata: {not json}",
                tokenEvent(2),
            )
        )
        assertEquals("畸形一条 ⇒ 计一次", 1, r.parseErrors)
        assertEquals(
            "🔴 R-08 的要害是**不静默错位**：跳过第 2 条之后，第 3 条必须仍带它自己的 seq=2。" +
                "若这里读出 [0,1]，说明 seq 是按数组位置补出来的，那会把一次丢失伪装成一次完整接收",
            listOf(0L, 2L), r.events.map { it.seq },
        )
    }

    @Test
    fun `畸形造成的缺口由 seq join 记成 gap_而不是凭空消失`() {
        // parseRaw 的注释原文写着「畸形 event 跳过并计数（**后续 seq join 计 gap**）」——
        // 那是一句**跨函数的断言**，本条把它钉住：解析侧丢掉的 seq，必须在审计侧现形。
        // 少了这条，两侧各自「正确」而缺失在中间蒸发：解析器说「我跳过了 1 条」，
        // 审计器说「我收到的都连续」，**没有任何一处报告那个 token 没了**。
        val r = reader.readStream(
            stream(tokenEvent(0), "event: token\ndata: {not json}", tokenEvent(2))
        )
        val audit = SeqJoinAudit.audit(r.events, expectedTokens = 3)
        assertEquals("区间 [0..2] 缺 {1}", 1, audit.gapCount)
        assertEquals("不是尾部截断——尾巴收到了", 0, audit.tailMissing)
        assertEquals(2L, audit.maxSeq)
    }

    @Test
    fun `token 事件缺 data 行时计入 parseErrors_而不是静默忽略`() {
        // 「有 event: token 却没有 data:」与「根本没有这条 event」在下游完全不同：
        // 前者是链路/服务端出了问题，后者只是流结束。静默忽略会把前者读成后者。
        val r = reader.readStream(stream(tokenEvent(0), "event: token", tokenEvent(1)))
        assertEquals(1, r.parseErrors)
        assertEquals(listOf(0L, 1L), r.events.map { it.seq })
    }

    @Test
    fun `干净流解析零错误且 prelude 被认出`() {
        // 正对照：少了它，一个「把什么都算成 parseError」的实现同样能通过上面三条。
        val r = reader.readStream(
            stream(""":prelude {"srv_ts_us":1000}""", tokenEvent(0), tokenEvent(1))
        )
        assertEquals("干净流不得报解析错误", 0, r.parseErrors)
        assertEquals(listOf(0L, 1L), r.events.map { it.seq })
        assertNotNull("prelude 注释帧必须被认出（R-20 要靠它剥离服务端 dwell）", r.prelude)
    }
}
