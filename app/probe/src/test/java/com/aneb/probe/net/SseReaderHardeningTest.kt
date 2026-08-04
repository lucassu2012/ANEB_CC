package com.aneb.probe.net

import okio.Buffer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * T45/D-467 §6.3③：SseReader 的 CRLF 边界识别 + 多 data: 行拼接加固——两处此前均是
 * "服务端保证不这样做"的假设，零测试覆盖（SseFixtures/AnthropicAdapterTest 的 CRLF
 * 用例都在测试层自行 split，从不驱动真正的 [SseBoundaryScanner]，见调查报告）。
 *
 * 不经 [SseReader.readRaw]/[SseReader.parseRaw]：两者内部都直接调用
 * `android.os.SystemClock.elapsedRealtimeNanos()` 打戳，本仓无 Robolectric，纯 JVM
 * 单测会抛 "not mocked"——这正是调查报告里"零测试覆盖"成因，不是失误。改为直接测试
 * 两处真正改动落脚的纯函数/无 Android 依赖类：[parseSseEventFields]（多行 data: 拼接）
 * 与 [SseBoundaryScanner]（CRLF 边界，其 `onRead`/`finish` 均不触碰 SystemClock）。
 */
class SseReaderHardeningTest {

    // ---------- parseSseEventFields：多 data: 行拼接 ----------

    @Test
    fun `multiple consecutive data lines are joined with newline, not overwritten`() {
        val text = "event: token\ndata: {\"seq\":7,\"sched_us\":100,\ndata: \"pre_flush_us\":200,\"payload\":\"aGVsbG8=\"}"
        val fields = parseSseEventFields(text)

        // 修复前：dataLines 是单值 var，第二条 data: 行覆盖第一条，只剩右半截 JSON 片段
        assertEquals("token", fields.eventName)
        assertEquals(
            "{\"seq\":7,\"sched_us\":100,\n\"pre_flush_us\":200,\"payload\":\"aGVsbG8=\"}",
            fields.dataLine,
        )
    }

    @Test
    fun `single data line behavior is unchanged (regression anchor)`() {
        val fields = parseSseEventFields("event: token\ndata: {\"seq\":1}")
        assertEquals("token", fields.eventName)
        assertEquals("{\"seq\":1}", fields.dataLine)
    }

    @Test
    fun `no data line yields null not empty string (R-10)`() {
        val fields = parseSseEventFields("event: summary")
        assertEquals("summary", fields.eventName)
        assertNull(fields.dataLine)
    }

    @Test
    fun `comment line (prelude) parses independently of data lines`() {
        val fields = parseSseEventFields(": prelude {\"srv_ts_us\":1}")
        assertEquals("prelude {\"srv_ts_us\":1}", fields.commentLine)
        assertNull(fields.dataLine)
        assertNull(fields.eventName)
    }

    // ---------- SseBoundaryScanner：CRLF 边界识别 ----------

    @Test
    fun `CRLF-only stream in a single read is split into two events (no LF ever present)`() {
        val scanner = SseBoundaryScanner()
        val text = "event: token\r\ndata: {\"seq\":1}\r\n\r\nevent: summary\r\ndata: {}\r\n\r\n"
        scanner.onRead(Buffer().apply { writeUtf8(text) }, text.length.toLong(), arrivalNanos = 1_000L)
        val raw = scanner.finish(eofNanos = 2_000L)

        // 修复前：EVENT_DELIMITER 纯 "\n\n" indexOf 在纯 CRLF 流上永远找不到边界——
        // 整条流 0 事件、truncatedTail=true（全部数据静默丢失，不是崩溃）。
        assertFalse(raw.truncatedTail)
        assertEquals(2, raw.events.size)
        assertEquals("event: token\ndata: {\"seq\":1}", raw.events[0].bytes.toString(Charsets.UTF_8))
        assertEquals("event: summary\ndata: {}", raw.events[1].bytes.toString(Charsets.UTF_8))
    }

    @Test
    fun `CRLF boundary split across two onRead chunks is still recognized as one boundary`() {
        // 完整 CRLF 流：event: token\r\ndata: {"seq":1}\r\n\r\nevent: summary\r\ndata: {}\r\n\r\n
        // 在两个事件之间 \r\n\r\n 这 4 字节的第 1 字节（\r）处切开——归一化必须跨 onRead
        // 调用状态化：上次结尾的孤立 \r 要留到下次首字节判断是否与 \n 配对。
        val scanner = SseBoundaryScanner()
        val head = "event: token\r\ndata: {\"seq\":1}\r"
        val tail = "\n\r\nevent: summary\r\ndata: {}\r\n\r\n"

        scanner.onRead(Buffer().apply { writeUtf8(head) }, head.length.toLong(), arrivalNanos = 1_000L)
        scanner.onRead(Buffer().apply { writeUtf8(tail) }, tail.length.toLong(), arrivalNanos = 2_000L)
        val raw = scanner.finish(eofNanos = 3_000L)

        assertFalse(raw.truncatedTail)
        assertEquals(2, raw.events.size)
        assertEquals("event: token\ndata: {\"seq\":1}", raw.events[0].bytes.toString(Charsets.UTF_8))
        assertEquals("event: summary\ndata: {}", raw.events[1].bytes.toString(Charsets.UTF_8))
    }

    @Test
    fun `a lone trailing CR with no paired LF is not silently dropped at finish()`() {
        val scanner = SseBoundaryScanner()
        val text = "event: token\ndata: {}\n\ntrailing\r"
        scanner.onRead(Buffer().apply { writeUtf8(text) }, text.length.toLong(), arrivalNanos = 1_000L)
        val raw = scanner.finish(eofNanos = 2_000L)

        // 一个事件已切出；末尾 "trailing\r" 无配对 \n、无 \n\n 边界，留在 acc 里 → truncatedTail=true
        assertEquals(1, raw.events.size)
        assertTrue(raw.truncatedTail)
    }

    @Test
    fun `pure LF chunk boundary scanning across multiple onRead calls is unaffected (regression)`() {
        // 归一化对不含 \r 字节的输入必须是 no-op；同一次 read 切出的第 2 个 event 仍标 sameReadBatch。
        val scanner = SseBoundaryScanner()
        val firstChunk = "event: token\ndata: {\"seq\":1}\n\nevent: token\ndata: {\"seq\":2}\n\n"
        scanner.onRead(Buffer().apply { writeUtf8(firstChunk) }, firstChunk.length.toLong(), arrivalNanos = 1_000L)
        val secondChunk = "event: summary\ndata: {}\n\n"
        scanner.onRead(Buffer().apply { writeUtf8(secondChunk) }, secondChunk.length.toLong(), arrivalNanos = 2_000L)
        val raw = scanner.finish(eofNanos = 3_000L)

        assertEquals(3, raw.events.size)
        assertFalse(raw.events[0].sameReadBatch)
        assertTrue(raw.events[1].sameReadBatch) // 同一次 read 切出的第 2 个 event
        assertFalse(raw.events[2].sameReadBatch) // 第二次 read 的第 1 个 event
        assertFalse(raw.truncatedTail)
        assertEquals(firstChunk.length.toLong() + secondChunk.length.toLong(), raw.totalBytes)
    }
}
