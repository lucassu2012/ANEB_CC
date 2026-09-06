package com.aneb.probe.net

import com.aneb.probe.net.AnebClient.Companion.buildWindowResult
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * `uploadWindow` **响应侧接线**的守卫（A-8／C-3）。
 *
 * 🔴 **这组测试补的是一层「判据已钉死、接线仍零覆盖」的缺口，而那个缺口是量出来的**：
 * `UploadResponseViewTest` 已经把**判据**（该信服务端计数还是客户端写出量）钉死了，
 * 但我随后对**调用点**跑了两条突变，全套件扫描：
 *
 * | 接线突变 | 后果 | 当时 |
 * |---|---|---|
 * | 调用点把 `serverView` 换成 `null` | 上行速率**永远用本地缓冲写出量** | **SURVIVED** |
 * | `endNanos` 由响应头到达退回最后一次 write 返回 | A-8 的口径要害整个失效 | **SURVIVED** |
 *
 * ⇒ **「这条判据有守卫」与「生产喂给它的输入被守着」是两件事。**
 * 判据完好无损，坏的可以是**喂给它的东西**，而没有任何守卫看得见。
 *
 * **本文件先跑了一个探针再动生产代码**：全仓从没有人构造过 okhttp [Response]，
 * 而**「没人这么做过」既不是「做不到」也不是「能做到」，只是「没有先例」**——
 * 故先用一个编译周期证明工具可用（见第一条），证通了才去抽 [buildWindowResult]。
 *
 * ⚠ **仍然够不着的那一层，写明不掩饰**：本组喂的是自己造的 `headersNanos`，
 * 因此**验不到「生产代码是不是真的在响应头到达那一刻取它」**。
 * **抽纯函数只能把不可测的接线层变薄，不能消掉它。**
 */
class UploadWindowResponseTest {

    private val json = Json { ignoreUnknownKeys = true }

    private fun canned(code: Int, body: String): Response =
        Response.Builder()
            .request(Request.Builder().url("http://localhost/upload_window").build())
            .protocol(Protocol.HTTP_1_1)
            .code(code)
            .message(if (code in 200..299) "OK" else "ERR")
            .body(body.toResponseBody("application/json".toMediaType()))
            .build()

    private fun build(
        resp: Response,
        startNanos: Long = 1_000L,
        headersNanos: Long = 7_777L,
        writtenBytes: Long = 9_000L,
        windowUnderrun: Boolean = false,
    ) = buildWindowResult(json, resp, startNanos, headersNanos, writtenBytes, windowUnderrun)

    @Test
    fun `探针_可以在纯 JVM 单测里构造并读取 okhttp Response`() {
        // 这条不测业务，测的是**本组赖以成立的工具**。留着是因为：若哪天它红了，
        // 下面三条会以一种看不出真因的方式一起红，而这条会直接说出是构造 Response 坏了。
        val r = canned(200, """{"bytes":5000}""")
        assertEquals(200, r.code)
        assertTrue("2xx 必须判成功", r.isSuccessful)
        assertTrue("非 2xx 必须判失败", !canned(503, "{}").isSuccessful)
    }

    @Test
    fun `服务端权威计数优先于客户端写出量_且 0 字节是合法值`() {
        val r = build(canned(200, """{"bytes":5000,"recv_start_us":1,"recv_end_us":2}"""))
        assertEquals(
            "若这里等于 9000，说明服务端视角在接线上被丢掉了——" +
                "那测的是本地 socket 缓冲的吞吐，不是网络（实测过这条突变曾无人咬住）",
            5_000L, r.bytesTransferred,
        )
        assertEquals("客户端计数仍如实留档（诊断量）", 9_000L, r.clientWrittenBytes)
        assertEquals(5_000L, r.serverView?.bytes)

        // 边界：服务端报 0 ＝ 真收到零字节（链路没通／窗口在首块前到点），必须采用。
        assertEquals(
            "服务端报 0 时退回客户端计数，会把没通的链路写成通的",
            0L, build(canned(200, """{"bytes":0}""")).bytesTransferred,
        )
    }

    @Test
    fun `终点戳取响应头到达_不是起点也不是别的时刻`() {
        val r = build(canned(200, """{"bytes":5000}"""), startNanos = 1_000L, headersNanos = 7_777L)
        assertEquals(1_000L, r.startNanos)
        assertEquals(
            "endNanos 必须是响应头到达时刻：最后一次 write 返回只说明字节进了本地 socket " +
                "缓冲，服务端把 body 读完的证据是 2xx 响应头（A-8 口径要害）",
            7_777L, r.endNanos,
        )
    }

    @Test
    fun `非 2xx 与坏 JSON 都退回客户端计数并记 error`() {
        val bad = build(canned(503, """{"bytes":5000}"""))
        assertNull("非 2xx 的响应体不是权威计数，哪怕它解析得开", bad.serverView)
        assertEquals("退回客户端写出量", 9_000L, bad.bytesTransferred)
        assertEquals(503, bad.httpCode)
        assertEquals("http 503", bad.error)

        val broken = build(canned(200, "{not json"))
        assertNull("坏 JSON ⇒ 无权威计数（R-10）", broken.serverView)
        assertEquals(9_000L, broken.bytesTransferred)
        assertNull("2xx 本身没错，error 不该被造出来", broken.error)
    }

    @Test
    fun `underrun 标志原样透传`() {
        // 接线量：它不参与任何计算，只被搬运——而搬运也会错，且错了完全静默。
        assertTrue(build(canned(200, """{"bytes":1}"""), windowUnderrun = true).windowUnderrun)
        assertTrue(!build(canned(200, """{"bytes":1}"""), windowUnderrun = false).windowUnderrun)
    }
}
