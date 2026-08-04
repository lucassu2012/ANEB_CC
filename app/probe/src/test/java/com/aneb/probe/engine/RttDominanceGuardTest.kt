package com.aneb.probe.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * [RttDominanceGuard.evaluate] 判据锚定（spec §8.3.3，T47 批②，D-468/D-469）。
 * 核心钉点：D-363 的三档历史倍数（s1 1.60-1.99×/s2 5.7-7.7×/s3 6.8-9.8×）在新的
 * RTT_DOMINANCE_MIN=10 门槛下**全部**应判 ok=false——包括历史最高值 s3 的 9.8×，
 * 这正是本文档比 D-363 一次性分析更严格的地方（10 是留在 9.8 之上的安全边际）。
 */
class RttDominanceGuardTest {

    // ---- D-363 历史数据回归夹具：三档倍数在新阈值下应全判"不安全" ----

    @Test fun `s1_chat 历史倍数 1_77x 判不安全`() {
        // D-363: s1_chat 2KB 负载耗时/RTT = 1.60-1.99x，取中位 1.77
        val v = RttDominanceGuard.evaluate(windowActualMs = 354.0, rttRefMs = 200.0, bytesTransferred = 200_000L)
        assertFalse("s1 历史最假区间必须判不安全", v.ok)
        assertEquals(1.77, v.ratio!!, 1e-9)
    }

    @Test fun `s2_coding_agent 历史倍数 6_5x 判不安全`() {
        // D-363: s2 512KB 负载耗时/RTT = 5.7-7.7x，取中位 6.5，仍 < 新阈值 10
        val v = RttDominanceGuard.evaluate(windowActualMs = 650.0, rttRefMs = 100.0, bytesTransferred = 200_000L)
        assertFalse(v.ok)
        assertEquals(6.5, v.ratio!!, 1e-9)
    }

    @Test fun `s3_multimodal 历史最高值 9_8x 仍判不安全（比 D-363 更严格的关键点）`() {
        // D-363: s3 1MB 负载耗时/RTT = 6.8-9.8x，AqsInputMapper 至今仍以此为 U1 评分口径，
        // 但从未被判定为"安全"——本判据的 10 就是刻意设在这个历史最高值之上。
        val v = RttDominanceGuard.evaluate(windowActualMs = 980.0, rttRefMs = 100.0, bytesTransferred = 200_000L)
        assertFalse("即使是 D-363 历史最高值 9.8x 也必须判不安全", v.ok)
        assertEquals(9.8, v.ratio!!, 1e-9)
    }

    // ---- 安全区 ----

    @Test fun `倍数 15x 且窗口字节数均达标时判安全`() {
        val v = RttDominanceGuard.evaluate(windowActualMs = 1500.0, rttRefMs = 100.0, bytesTransferred = 200_000L)
        assertTrue(v.ok)
        assertEquals(15.0, v.ratio!!, 1e-9)
    }

    // ---- ratio 边界（>= 严格纳入，本仓惯例：门限值本身归入达标侧） ----

    @Test fun `ratio 恰为 10 且其余达标时判安全（大于等于）`() {
        val v = RttDominanceGuard.evaluate(windowActualMs = 1000.0, rttRefMs = 100.0, bytesTransferred = 200_000L)
        assertEquals(10.0, v.ratio!!, 1e-9)
        assertTrue(v.ok)
    }

    @Test fun `ratio 9_99 判不安全`() {
        val v = RttDominanceGuard.evaluate(windowActualMs = 999.0, rttRefMs = 100.0, bytesTransferred = 200_000L)
        assertFalse(v.ok)
    }

    // ---- AND 语义：三条件缺一不可，不是 OR（用高倍数掩盖其他两条件不达标来证伪） ----

    @Test fun `ratio 极高但窗口时长低于 ABS_FLOOR_MS 时仍判不安全`() {
        // ratio=100（远超阈值）但 windowActualMs=250 < ABS_FLOOR_MS=300
        val v = RttDominanceGuard.evaluate(windowActualMs = 250.0, rttRefMs = 2.5, bytesTransferred = 200_000L)
        assertEquals(100.0, v.ratio!!, 1e-9)
        assertFalse("高 ratio 不能掩盖窗口时长过短", v.ok)
    }

    @Test fun `ratio 与窗口时长均达标但字节数低于下限时仍判不安全`() {
        val v = RttDominanceGuard.evaluate(windowActualMs = 1500.0, rttRefMs = 100.0, bytesTransferred = 50_000L)
        assertEquals(15.0, v.ratio!!, 1e-9)
        assertFalse("高 ratio 不能掩盖字节数不足", v.ok)
    }

    // ---- RTT 探测失败：不猜，直接判不安全 ----

    @Test fun `rttRefMs 为 null 时判不安全且 ratio 为 null（不猜）`() {
        val v = RttDominanceGuard.evaluate(windowActualMs = 1500.0, rttRefMs = null, bytesTransferred = 200_000L)
        assertFalse(v.ok)
        assertNull(v.ratio)
    }

    @Test fun `rttRefMs 为 0 时判不安全（防除零）`() {
        val v = RttDominanceGuard.evaluate(windowActualMs = 1500.0, rttRefMs = 0.0, bytesTransferred = 200_000L)
        assertFalse(v.ok)
        assertNull(v.ratio)
    }
}
