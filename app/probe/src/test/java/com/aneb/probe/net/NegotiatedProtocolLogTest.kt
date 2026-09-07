package com.aneb.probe.net

import org.junit.Assert.assertEquals
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * [NegotiatedProtocolLog] 的纯 JVM 守卫（A-8⑦／D-806）。**不需要 Robolectric**——
 * 账本本身不碰 Android，这正是把它与 `Response` 解析分开的理由。
 *
 * ⚠ 本文件**只证明账本会数数**。「它真的被每条响应调用了」是另一件事，
 * 由 [AnebClientProtocolLogTest] 走真实请求证——**两件事分开测，因为它们会分开坏**。
 */
class NegotiatedProtocolLogTest {

    @Test
    fun `同一协议多次观测 → 计数累加，总数与分表一致`() {
        val log = NegotiatedProtocolLog()
        repeat(3) { log.observe("http/1.1", "HTTP/1.1;via=tcp") }
        val s = log.snapshot()
        assertEquals(3L, s.samples)
        assertEquals(mapOf("http/1.1" to 3L), s.byProtocol)
        assertEquals(mapOf("HTTP/1.1;via=tcp" to 3L), s.byProtoHeader)
        assertEquals(0L, s.headerAbsent)
    }

    @Test
    fun `混入一条 h2 → 分表出现第二个键，这正是验收要看的那个信号`() {
        val log = NegotiatedProtocolLog()
        repeat(5) { log.observe("http/1.1", "HTTP/1.1;via=tcp") }
        log.observe("h2", "HTTP/2.0;via=tcp")
        val s = log.snapshot()
        // 「全为 http/1.1」的判法＝分表恰一个键且为 http/1.1。这里故意让它不成立，
        // 证明该判法**有区分能力**——否则一张永远只有一个键的表证明不了任何事。
        assertEquals(setOf("http/1.1", "h2"), s.byProtocol.keys)
        assertEquals(6L, s.samples)
    }

    @Test
    fun `头缺席与空串是两个状态_不得合并`() {
        val log = NegotiatedProtocolLog()
        log.observe("http/1.1", null)   // 老服务端：根本不发这个头
        log.observe("http/1.1", "")     // 发了，但值是空的
        val s = log.snapshot()
        assertEquals("缺席只计 headerAbsent", 1L, s.headerAbsent)
        assertEquals("空串是一个真实的值，要进分表", mapOf("" to 1L), s.byProtoHeader)
        assertEquals(2L, s.samples)
    }

    @Test
    fun `零观测 → samples 为 0 且两张分表为空——这与「块缺席」不是一回事`() {
        val s = NegotiatedProtocolLog().snapshot()
        assertEquals(0L, s.samples)
        assertEquals(emptyMap<String, Long>(), s.byProtocol)
        assertEquals(0L, s.headerAbsent)
    }

    @Test
    fun `快照按键排序_同样的数据必须产出同样的顺序`() {
        val log = NegotiatedProtocolLog()
        // 故意乱序插入：ConcurrentHashMap 的迭代顺序不保证稳定，
        // 不排序的话上报体会随运行不同而不同，而**没有任何东西会报错**。
        listOf("h3", "http/1.1", "h2").forEach { log.observe(it, null) }
        assertEquals(listOf("h2", "h3", "http/1.1"), log.snapshot().byProtocol.keys.toList())
    }

    @Test
    fun `并发观测不丢数——OkHttp 回调本来就在多条 dispatcher 线程上`() {
        val log = NegotiatedProtocolLog()
        val threads = 4
        val each = 250
        val pool = Executors.newFixedThreadPool(threads)
        val start = CountDownLatch(1)
        val done = CountDownLatch(threads)
        repeat(threads) { t ->
            pool.execute {
                start.await()
                repeat(each) { log.observe(if (t % 2 == 0) "http/1.1" else "h2", null) }
                done.countDown()
            }
        }
        start.countDown()
        assertEquals(true, done.await(30, TimeUnit.SECONDS))
        pool.shutdown()
        val s = log.snapshot()
        assertEquals((threads * each).toLong(), s.samples)
        assertEquals((threads * each).toLong(), s.byProtocol.values.sum())
    }
}
