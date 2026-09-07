package com.aneb.probe.net

import android.os.SystemClock
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.Implementation
import org.robolectric.annotation.Implements
import java.util.concurrent.TimeUnit

/**
 * 走**真实**单调时间的 `SystemClock` 影子（**仅测试作用域**，不动任何生产代码）。
 *
 * 🔴 **为什么必须有它（实测，不是推理）**：Robolectric 默认 `LooperMode.PAUSED`，
 * `SystemClock.elapsedRealtimeNanos()` 是**模拟钟，只在 idle 时前进**。
 * 本文件第一版探针实测：**真实 `Thread.sleep(300)` 之后它走了 0 ms。**
 *
 * ⇒ 后果不是「测得不准」，是**两件事在原理上分不开**：
 * - `uploadWindow` 的**窗口到点**判据读的就是这个钟 ⇒ 钟不动 ⇒ **deadline 永不触发**，
 *   写循环会一直跑到 `maxBytes`，「到点停写」这个行为根本不会发生；
 * - 「终点戳取**响应头到达**还是**最后一次 write 返回**」⇒ 两个时刻读到同一个值 ⇒
 *   **对的实现与错的实现产出完全相同的数字，而断言照样通过（0 == 0）**。
 *
 * ⚠ 这是「量法失败与目标缺席长得一样」的又一形，且**它会伪装成绿灯**。
 * ⚠ 并且它说明：这两项的堵点**不只是「没有会读的对端」，还有「没有真实的钟」**——
 * 申请 MockWebServer 时给出的理由只写了前一半，两个条件缺一不可。
 */
@Implements(SystemClock::class)
class ShadowRealSystemClock {
    companion object {
        @Implementation
        @JvmStatic
        fun elapsedRealtimeNanos(): Long = System.nanoTime()

        @Implementation
        @JvmStatic
        fun elapsedRealtime(): Long = System.nanoTime() / 1_000_000L
    }
}

/**
 * `AnebClient.uploadWindow` 的端到端守卫（A-8／C-3 最后一项，PO 2026-09-07 批准依赖）。
 *
 * **补的是什么**：此前 `uploadWindow` 的**调用点供给层**实测**四个实参各造一枚突变、
 * 四枚全部存活**（时戳／写出量／underrun／起点戳），而**请求侧行为**（窗口到点停写、
 * chunked）从未被任何测试驱动过。两者都够不着的原因是同一个：
 * **它们要观测的不是一个值，而是一个行为**——需要一个会读的对端 ＋ 一个会走的钟。
 *
 * ⚠ **不给 `AnebClient` 开注入缝**：`uploadWindow` 本来就收 URL，把它指向 MockWebServer
 * 即可驱动**真实**的那一条路径。为可测性放宽生产 API 是另一个取舍，本笔不做。
 */
@RunWith(RobolectricTestRunner::class)
@Config(shadows = [ShadowRealSystemClock::class])
class AnebClientWindowTest {

    private lateinit var server: MockWebServer
    private val client = AnebClient()

    @Before fun setUp() { server = MockWebServer().apply { start() } }
    @After fun tearDown() { server.shutdown() }

    private fun url() = server.url("/upload_window").toString()

    @Test
    fun `探针_装上真实时钟影子后单调钟随真实时间前进`() {
        // 保留在文件里的理由同 UploadWindowResponseTest 的探针：**把「工具坏了」从
        // 「业务坏了」里分出来**。这条一旦红，下面所有时间类断言都不再有意义——
        // 而没有它，那些断言会以「两个时刻读到同一个值」的方式**静默失效并全部变绿**。
        val t0 = SystemClock.elapsedRealtimeNanos()
        Thread.sleep(300)
        val deltaMs = (SystemClock.elapsedRealtimeNanos() - t0) / 1_000_000.0
        assertTrue(
            "真实 sleep 300ms 后单调钟只走了 %.3f ms（不带影子时实测正是 0）".format(deltaMs),
            deltaMs > 100.0,
        )
    }

    @Test
    fun `终点戳是响应头到达_不是最后一次写入返回`() {
        // 服务端把**响应头**推迟 500ms 才发；请求体很小，写完只需几毫秒。
        // ⇒ 「最后一次 write 返回」与「响应头到达」相差约 500ms，两者一眼可辨。
        server.enqueue(
            MockResponse().setBody("""{"bytes":65536}""")
                .setHeadersDelay(500, TimeUnit.MILLISECONDS)
        )
        val r = runBlocking {
            client.uploadWindow(url(), windowMs = 5_000, maxBytes = 65_536, chunkBytes = 16_384)
        }
        // 🔴 先断言请求本身成功，再谈时长。**失败路径下 `endNanos` 的初值就是 `startNanos`**
        // （见 `uploadWindow` 的 catch 分支），于是时长恰好 0.0 ——
        // **而那与「终点戳取错」在数字上完全同形**。
        // 实测踩过：一次陈旧 Gradle 守护进程锁住 classes.jar 导致请求失败，
        // 被下面那条断言的文案报成了「你的时戳口径错了」，白查一轮。
        // ⇒ 量法自己的失败必须先被排除，否则它会冒充被测对象的失败。
        assertNull("请求本身失败了，下面的时长断言测的是失败路径而非口径：${r.error}", r.error)
        assertEquals("HTTP 必须是 200", 200, r.httpCode)
        val durationMs = (r.endNanos!! - r.startNanos) / 1_000_000.0
        assertTrue(
            "窗口时长 %.1f ms —— 若明显小于 500ms，说明终点戳取的是最后一次 write 返回；".format(durationMs) +
                "那只说明字节进了本地 socket 缓冲，**服务端把 body 读完的证据是 2xx 响应头**（A-8 口径要害）。" +
                "若接近 0，说明起点戳也被污染了",
            durationMs >= 450.0,
        )
        assertTrue("上界只作量级 sanity，不是口径断言：%.1f ms".format(durationMs), durationMs < 5_000.0)
    }

    @Test
    fun `写满 ceiling 而窗口未到点_判 underrun 且客户端写出量等于 ceiling`() {
        server.enqueue(MockResponse().setBody("""{"bytes":65536}"""))
        val r = runBlocking {
            client.uploadWindow(url(), windowMs = 10_000, maxBytes = 65_536, chunkBytes = 16_384)
        }
        assertTrue("写满 ceiling 而窗口远未到点 ⇒ underrun", r.windowUnderrun)
        assertEquals(
            "客户端写出量必须如实等于 ceiling —— 它是**诊断量**，与服务端权威计数不是同一个量",
            65_536L, r.clientWrittenBytes,
        )
        // 服务端确实收到了这些字节（否则上面那个数只是客户端的一厢情愿）
        assertEquals(65_536L, server.takeRequest().bodySize)
    }

    @Test
    fun `窗口到点则停止写入_不判 underrun 且写出量远小于 ceiling`() {
        server.enqueue(MockResponse().setBody("""{"bytes":1}"""))
        // ⚠ ceiling 的取值有**两侧**约束，只顾一头就会出事（实测踩过）：
        // - 下界：要大到真实代码在窗口内写不满，否则绑定的是 ceiling 而非 deadline，
        //   这条就根本测不到「到点停写」；
        // - 🔴 上界：**突变体会把 ceiling 整个写进 MockWebServer 的内存缓冲**
        //   （去掉「到点收笔」那一行后，循环只剩 ceiling 一个约束）。首版取 512MB，
        //   突变审计因此挂死而不是变红——而**「突变体跑不完」与「突变体没被咬住」
        //   在产物上同形**：两者都表现为「没有失败记录」。
        // 故取 50ms × 64MB：真实代码约写几 MB（离下面 32MB 阈值有三倍余量），
        // 突变体写满 64MB 在几百毫秒内结束，内存也扛得住。
        val ceiling = 64L * 1024 * 1024
        val r = runBlocking {
            client.uploadWindow(url(), windowMs = 50, maxBytes = ceiling, chunkBytes = 16_384)
        }
        assertTrue(
            "到点停写 ⇒ 不是 underrun（underrun 专指『写满 ceiling 而窗口未到点』，两者互斥）",
            !r.windowUnderrun,
        )
        // 阈值取 ceiling/2（32MB）而非 /4：50ms 内真实写出量随机器吞吐浮动，
        // 快机器上可能超过 16MB 而造成**假红**；而突变体写满 64MB，32MB 仍分得开。
        assertTrue(
            "写出量 ${r.clientWrittenBytes} 应远小于 ceiling $ceiling —— " +
                "若等于 ceiling，说明窗口到点没有停下写循环",
            r.clientWrittenBytes!! < ceiling / 2,
        )
    }

    @Test
    fun `请求走 chunked 且服务端权威计数优先于客户端写出量`() {
        // 服务端报一个**与客户端写出量不同**的数，才分得出用的是哪一个。
        server.enqueue(MockResponse().setBody("""{"bytes":12345}"""))
        val r = runBlocking {
            client.uploadWindow(url(), windowMs = 10_000, maxBytes = 65_536, chunkBytes = 16_384)
        }
        assertEquals(
            "若这里等于 65536，说明服务端权威计数在接线上被丢掉了——那测的是本地缓冲吞吐，不是网络",
            12_345L, r.bytesTransferred,
        )
        assertEquals("客户端计数仍如实留档", 65_536L, r.clientWrittenBytes)
        assertNotNull(r.serverView)

        val rec = server.takeRequest()
        assertEquals(
            "窗口化上行不预知总量（contentLength = -1）⇒ 必须走 chunked；" +
                "若变成 Content-Length，写循环就没法在到点那一刻半途收笔",
            "chunked", rec.headers["Transfer-Encoding"],
        )
    }
}
