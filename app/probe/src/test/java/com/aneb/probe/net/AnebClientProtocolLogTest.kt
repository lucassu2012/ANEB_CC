package com.aneb.probe.net

import android.os.SystemClock
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * **接线层**守卫：证明账本真的被每条响应调用（A-8⑦／D-806）。
 *
 * **为什么非要走真实请求**：[NegotiatedProtocolLogTest] 已经证明账本会数数，但那不能
 * 证明**有人在数**。C-3 刚给过一次同形教训——`uploadWindow` 的四个实参各造一枚突变、
 * **四枚全存活**，因为夹具直接构造结果对象、绕过了真实路径。
 * ⇒ 判据必须**从 `AnebClient` 的公开方法进去**，让 `executeCancellable` 真的跑一遍。
 *
 * ⚠ 影子钟 [ShadowRealSystemClock] 复用自 `AnebClientWindowTest`（同包）；本文件不测时长，
 * 但 `AnebClient` 的调用路径会读 `SystemClock`，缺影子会在别处炸。
 */
@RunWith(RobolectricTestRunner::class)
@Config(shadows = [ShadowRealSystemClock::class])
class AnebClientProtocolLogTest {

    /**
     * 🔴 **服务端头名的字面量，故意不引 `AnebClient.PROTO_EVIDENCE_HEADER`**。
     *
     * 实测教训（本笔突变审计 P3）：夹具原本用那个常量来**设置**响应头 ⇒ 常量写岔时
     * 两侧一起岔，**测试照样全绿**——「被测方与判据出自同一个假设」的又一例，
     * 与 `check_expected_n` 那次（D-707 笔② §6）同形。判据必须与被测方**独立取值**。
     */
    private val SERVER_HEADER_LITERAL = "X-Aneb-Proto"

    private lateinit var server: MockWebServer

    @Before fun setUp() { server = MockWebServer().apply { start() } }

    @After fun tearDown() { server.shutdown() }

    private fun url(path: String) = server.url(path).toString()

    @Test
    fun `一次真实请求 → 账本记下 http11 与服务端证据头`() {
        val log = NegotiatedProtocolLog()
        val client = AnebClient(protocolLog = log)
        server.enqueue(
            MockResponse().setResponseCode(200)
                .setHeader(SERVER_HEADER_LITERAL, "HTTP/1.1;via=tcp")
                .setBody("{}"),
        )
        val r = runBlocking { client.fetchProfiles(url("/api/v1/profiles")) }
        assertEquals(200, r.httpCode)

        val s = log.snapshot()
        assertEquals("一次请求＝一条样本", 1L, s.samples)
        // MockWebServer 明文 HTTP/1.1 ⇒ OkHttp 侧协商结果就是 http/1.1。
        assertEquals(mapOf("http/1.1" to 1L), s.byProtocol)
        assertEquals(mapOf("HTTP/1.1;via=tcp" to 1L), s.byProtoHeader)
        assertEquals(0L, s.headerAbsent)
    }

    @Test
    fun `服务端不发证据头 → 记为缺席而不是编一个值`() {
        val log = NegotiatedProtocolLog()
        val client = AnebClient(protocolLog = log)
        server.enqueue(MockResponse().setResponseCode(200).setBody("{}"))
        runBlocking { client.fetchProfiles(url("/api/v1/profiles")) }

        val s = log.snapshot()
        assertEquals(1L, s.samples)
        assertEquals("头缺席不得进分表（R-10：无事件不造数）", emptyMap<String, Long>(), s.byProtoHeader)
        assertEquals(1L, s.headerAbsent)
    }

    @Test
    fun `非2xx 也要记 —— 失败样本恰恰最该看协议`() {
        val log = NegotiatedProtocolLog()
        val client = AnebClient(protocolLog = log)
        server.enqueue(
            MockResponse().setResponseCode(500)
                .setHeader(SERVER_HEADER_LITERAL, "HTTP/1.1;via=tcp")
                .setBody("boom"),
        )
        runBlocking { client.fetchProfiles(url("/api/v1/profiles")) }
        assertEquals(1L, log.snapshot().samples)
    }

    @Test
    fun `响应体读取中途断开 → 仍记一条（观测点在 try 之外，不是写在注释里的许诺）`() {
        // 🔴 这条钉的是接线点的**位置**：`observe` 写在 `response.use(consume)` 的 try
        // **之前**。若把它挪进 try、或挪到 consume 之后，本例会掉到 0 ——
        // 而那正是「失败样本静默不计」的形状：总数看着干净，因为坏样本根本没进分母。
        val log = NegotiatedProtocolLog()
        val client = AnebClient(protocolLog = log)
        server.enqueue(
            MockResponse().setResponseCode(200)
                .setHeader(SERVER_HEADER_LITERAL, "HTTP/1.1;via=tcp")
                .setBody("x".repeat(4096))
                .setSocketPolicy(SocketPolicy.DISCONNECT_DURING_RESPONSE_BODY),
        )
        val r = runBlocking { client.fetchProfiles(url("/api/v1/profiles")) }
        assertTrue("本例要的就是一次读体失败", r.error != null || r.body == null)
        assertEquals("响应头已到手 ⇒ 协议已协商完 ⇒ 这条样本必须在账本里", 1L, log.snapshot().samples)
    }

    @Test
    fun `多次请求累加 —— 账本按 client 实例持有，不是每次请求新开一本`() {
        val log = NegotiatedProtocolLog()
        val client = AnebClient(protocolLog = log)
        repeat(3) {
            server.enqueue(
                MockResponse().setResponseCode(200)
                    .setHeader(SERVER_HEADER_LITERAL, "HTTP/1.1;via=tcp")
                    .setBody("{}"),
            )
        }
        repeat(3) { runBlocking { client.fetchProfiles(url("/api/v1/profiles")) } }
        assertEquals(3L, log.snapshot().samples)
    }

    @Test
    fun `不传账本时 client 自带一本 —— 既有构造点一字不改仍能记`() {
        val client = AnebClient()
        server.enqueue(MockResponse().setResponseCode(200).setBody("{}"))
        runBlocking { client.fetchProfiles(url("/api/v1/profiles")) }
        assertEquals(1L, client.protocolLog.snapshot().samples)
    }

    @Test
    fun `头名与服务端源码逐字一致 —— 跨语言字面量走样两边都不报错`() {
        // 这个头名分处 Kotlin 与 Go 两侧，**没有编译器会核它俩**。写岔的后果不是报错，
        // 是所有样本安静地记成「头缺席」——一个看着合理的数。范式承 D-264／D-508。
        var cur: java.io.File? = java.io.File(System.getProperty("user.dir") ?: ".").absoluteFile
        var go: java.io.File? = null
        while (cur != null && go == null) {
            val c = java.io.File(cur, "server/h3.go")
            if (c.isFile) go = c
            cur = cur.parentFile
        }
        assertTrue("找不到 server/h3.go —— 先怀疑量法坏了，别当成不一致", go != null)
        val src = go!!.readText()
        assertTrue(
            "server/h3.go 未以字面量 \"$SERVER_HEADER_LITERAL\" 设置该头",
            src.contains("Set(\"" + SERVER_HEADER_LITERAL + "\""),
        )
        assertEquals(
            "Kotlin 常量与服务端字面量必须逐字相同",
            SERVER_HEADER_LITERAL, AnebClient.PROTO_EVIDENCE_HEADER,
        )
    }

    /** 影子钟在位的自证：缺了它，本包其他用例会以「时间不走」的形态假过（见 C-3 记述）。 */
    @Test
    fun `影子钟真的在走`() {
        val a = SystemClock.elapsedRealtimeNanos()
        Thread.sleep(5)
        assertTrue("elapsedRealtimeNanos 必须前进", SystemClock.elapsedRealtimeNanos() > a)
    }
}
