package com.aneb.probe.net

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * [UploadResponseView] 的夹具（C-3／A-8，REVIEW §7.1 S3-01）。
 *
 * **这组测试存在的理由，写在这里以免日后被当成冗余删掉**：这两个判断抽出来之前
 * **内联在 [AnebClient] 的三个 `executeCancellable` 块里**，要跑到它们得起一条真实 HTTP 请求
 * ——于是**它们一行都没被验过**。更具体地：我此前自报过一次 **M2 SURVIVED**，
 * 成因正是既有夹具（`engine/ScenarioKpiUploadBytesTest`）**直接构造 `WindowTransferResult`**，
 * **绕开了 `uploadWindow` 自己的取值逻辑** ⇒ 那条测试是回归钉，不是守卫。本组补的就是那一层。
 *
 * ⚠ **已知边界，写明而不掩饰**：本组用的是**与生产同配置**的解析器
 * （`Json { ignoreUnknownKeys = true }`），**不是同一个实例**——`AnebClient.json` 是私有的。
 * 若有人改掉 `AnebClient` 里那行配置，**本组不会红**。为此下面有一条专门断言
 * 「未知键必须被容忍」，把那个配置的**行为**钉在这里：改配置的人至少会看到两处都写着它。
 * （不为测试放宽 `AnebClient` 的可见性——为可测性拓宽生产 API 是另一种代价。）
 */
class UploadResponseViewTest {

    /** 与 `AnebClient.json` 同配置。见类 KDoc 里写明的「同配置≠同实例」边界。 */
    private val json = Json { ignoreUnknownKeys = true }

    private fun body(bytes: Long) =
        """{"bytes":$bytes,"recv_start_us":1000,"recv_end_us":2000,"chunk_us":[10,20]}"""

    // ---------------- parse ----------------

    @Test
    fun `parse_2xx 且 JSON 合法时出视角`() {
        val v = UploadResponseView.parse(json, isSuccessful = true, bodyText = body(4096))
        assertEquals(4096L, v!!.bytes)
        assertEquals(1000L, v.recvStartUs)
        assertEquals(listOf(10L, 20L), v.chunkUs)
    }

    @Test
    fun `parse_非 2xx 时即使响应体能解析也必须 null`() {
        // ⚠ 这条的要害：body 是**完全合法**的 JSON。判据是 HTTP 状态，不是「解得开吗」。
        // 少了它，一个把判据写成「能解析就用」的实现会拿 4xx/5xx 响应体里的数当权威计数。
        assertNull(
            "非 2xx 的响应体不是权威计数，哪怕它解析得开",
            UploadResponseView.parse(json, isSuccessful = false, bodyText = body(4096)),
        )
    }

    @Test
    fun `parse_响应体缺失或坏 JSON 一律 null 而不是抛`() {
        assertNull("体缺失", UploadResponseView.parse(json, true, null))
        assertNull("坏 JSON", UploadResponseView.parse(json, true, "{not json"))
        assertNull("空串", UploadResponseView.parse(json, true, ""))
        // 类型不符也走同一条路（R-10：不出值，不造值，且不得把异常抛给调用方）
        assertNull("bytes 类型不符", UploadResponseView.parse(json, true, """{"bytes":"many"}"""))
    }

    @Test
    fun `parse_未知键必须被容忍`() {
        // 这条钉的是**生产解析器的配置行为**（ignoreUnknownKeys = true）。
        // 服务端将来加字段是常态；若这里变严，一次加字段就会让全部上行样本退化为 null，
        // 而症状是「服务端视角忽然全缺席」，看起来像网络问题，不像解析问题。
        val v = UploadResponseView.parse(
            json, true, """{"bytes":7,"recv_start_us":1,"recv_end_us":2,"brand_new_field":"x"}""",
        )
        assertEquals(7L, v!!.bytes)
    }

    @Test
    fun `parse_解析成功但服务端没报 bytes 时是 -1 而不是 0`() {
        // 🔴 「解析成功」不等于「服务端报了这个数」——默认值 -1 承载的正是后一种缺席。
        // 这条与下面 bytesTransferred 的 -1 分支是一对：分开测，是因为它们在两个函数里，
        // 而把 -1 误当 0（或反之）在任何单独一处都不会报错。
        val v = UploadResponseView.parse(json, true, """{"recv_start_us":1,"recv_end_us":2}""")
        assertEquals("没报 bytes 时必须留在 -1，不能塌成 0（0 是「真收到零字节」）", -1L, v!!.bytes)
    }

    // ---------------- bytesTransferred ----------------

    @Test
    fun `取值_服务端权威计数优先于客户端写出量`() {
        val v = AnebClient.UploadServerView(bytes = 5_000)
        assertEquals(
            "若这里等于 9000，测的是本地 socket 缓冲的吞吐，不是网络",
            5_000L, UploadResponseView.bytesTransferred(v, clientWrittenBytes = 9_000),
        )
    }

    @Test
    fun `取值_服务端视角缺席时退回客户端写出量`() {
        assertEquals(
            9_000L, UploadResponseView.bytesTransferred(null, clientWrittenBytes = 9_000),
        )
    }

    @Test
    fun `取值_解析成功但 bytes 为 -1 同样退回客户端写出量`() {
        // -1 ＝「服务端没报」。照用会得出一个负的传输量，而负数会一路流到速率计算里。
        val v = AnebClient.UploadServerView(bytes = -1)
        assertEquals(
            9_000L, UploadResponseView.bytesTransferred(v, clientWrittenBytes = 9_000),
        )
    }

    @Test
    fun `取值_服务端报 0 字节是合法值必须采用_不得退回客户端计数`() {
        // 🔴 本组最该钉的一条（边界正对照）：0 与 -1 含义相反。
        // 0 ＝ 服务端确实一个字节都没读到（窗口在首块写出前就到点，或链路根本没通）；
        // -1 ＝ 服务端没报这个数。**把判据写成 `> 0`，上面三条照样全绿**，
        // 而这一条会红——它是 `>= 0` 与 `> 0` 之间唯一的分辨点。
        // 更要命的是它错得不响：会把「网络没通」的样本改写成「客户端写出了 9000 字节」，
        // 那是一个**看起来完全正常的错数**，且恰好落在最该被看见的那类样本上。
        val v = AnebClient.UploadServerView(bytes = 0)
        assertEquals(
            "服务端报 0 是「真收到零字节」，退回客户端计数会把没通的链路写成通的",
            0L, UploadResponseView.bytesTransferred(v, clientWrittenBytes = 9_000),
        )
    }
}
