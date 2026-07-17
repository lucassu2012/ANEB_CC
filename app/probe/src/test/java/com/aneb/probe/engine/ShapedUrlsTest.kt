package com.aneb.probe.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * ShapedUrls（weak-capacity-latency-v1 合成整形路径 URL 构造）锚定（D-43；
 * TEST_SERVER_CAPABILITIES §2/§5：每请求必须携带 impair_run/impair_seed/impair_seq，
 * 且 impair_seq 逐请求严格递增——服务端按 run+seed+seq 确定性生成抖动）。
 */
class ShapedUrlsTest {

    @Test
    fun `impair三参数齐全且端点路径正确`() {
        val u = ShapedUrls("http://1.2.3.4:8080", "run-abc", 42L)
        val url = u.next("echo")
        assertTrue(url.startsWith("http://1.2.3.4:8080/synthetic/weak-capacity-latency-v1/api/v1/echo?"))
        assertTrue("impair_run=run-abc" in url)
        assertTrue("impair_seed=42" in url)
        assertTrue("impair_seq=0" in url)
    }

    @Test
    fun `seq跨请求严格递增_不同端点共享同一计数器`() {
        val u = ShapedUrls("http://h", "r", 7L)
        val seqs = listOf(u.next("echo"), u.next("download?bytes=8388608"), u.next("upload"), u.next("echo"))
            .map { url -> Regex("impair_seq=(\\d+)").find(url)!!.groupValues[1].toInt() }
        assertEquals(listOf(0, 1, 2, 3), seqs)
    }

    @Test
    fun `端点自带查询参数时用与号拼接_不产生第二个问号`() {
        val u = ShapedUrls("http://h", "r", 1L)
        val url = u.next("download?bytes=8388608")
        assertTrue("/synthetic/weak-capacity-latency-v1/api/v1/download?bytes=8388608&impair_run=r" in url)
        assertEquals(1, url.count { it == '?' })
    }

    @Test
    fun `合同常量锚定_防伪回执id与路由`() {
        assertEquals("network_comprehensive_weak_capacity_latency@1.0.0", ShapedUrls.CONTRACT_ID)
        assertEquals("synthetic/weak-capacity-latency-v1/api/v1", ShapedUrls.ROUTE)
    }
}
