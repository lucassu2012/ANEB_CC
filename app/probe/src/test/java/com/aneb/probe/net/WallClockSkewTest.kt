package com.aneb.probe.net

import com.aneb.probe.net.AnebClient.Companion.WALL_SKEW_MAX_MS
import com.aneb.probe.net.AnebClient.Companion.wallClockSuspect
import com.aneb.probe.net.AnebClient.Companion.wallSkewMs
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 墙钟 skew 还原式与 `wall_clock_suspect` 判据（T64 §8.6 测试计划 / D-506）。
 *
 * 背景：D-494 那次设备墙钟错 10 天，在产物侧**结构性不可见**——`offset_*` 按 R-24 设计
 * 就免疫墙钟（两个单调计数之差，见 `engine/ClockSkewTest`），而唯一能查出它的服务端
 * `anchor_wall_unix_ns` 客户端连字段都没声明、静默丢弃（D-503）。本组钉住补上的那条链。
 */
class WallClockSkewTest {

    /** 服务端进程启动墙钟锚点（Unix ns）。量级取自 T64 §4 线上实测那次，非随手编的数。 */
    private val anchorNs = 1_786_663_903_945_004_974L

    /** 该锚点 + t1 还原出的服务端墙钟（ms）——被测还原式的独立手算值。 */
    private fun serverWallMs(t1Us: Long) = anchorNs / 1_000_000L + t1Us / 1_000L

    @Test
    fun `还原式：设备与服务端完全对齐时 skew 为 0`() {
        val t1Us = 448_184_048_659L
        assertEquals(0L, wallSkewMs(anchorNs, t1Us, serverWallMs(t1Us)))
    }

    @Test
    fun `还原式：设备快 3 秒即 skew 为正 3000ms`() {
        val t1Us = 448_184_048_659L
        assertEquals(3_000L, wallSkewMs(anchorNs, t1Us, serverWallMs(t1Us) + 3_000L))
    }

    @Test
    fun `还原式：设备慢则 skew 为负——符号不可丢`() {
        val t1Us = 448_184_048_659L
        assertEquals(-1_500L, wallSkewMs(anchorNs, t1Us, serverWallMs(t1Us) - 1_500L))
    }

    @Test
    fun `旧服务端不回带 anchor 时 skew 为 null 而不是 0（R-10）`() {
        // 0 恰是「钟完全对齐」的合法值；把「测不出」记成 0 等于凭空断言钟是对的。
        assertNull(wallSkewMs(null, 448_184_048_659L, 1_786_664_352_129L))
    }

    // ---- 判据反例（T64 §8.6 明确要求「构造反例证伪，不推理」）----

    @Test
    fun `反例一：D-494 那种 10 天偏差必须判 suspect`() {
        val tenDaysMs = 10L * 24 * 60 * 60 * 1000
        assertTrue("10 天偏差没被判可疑，那这条链就白建了", wallClockSuspect(tenDaysMs))
        assertTrue("负方向同样要判", wallClockSuspect(-tenDaysMs))
    }

    @Test
    fun `反例二：50ms 正常网络抖动量级不得判 suspect`() {
        // 本项目实测 RTT 上界 106ms（T63 §1）——若这个量级被判可疑，守卫就是噪声源。
        assertFalse(wallClockSuspect(50L))
        assertFalse(wallClockSuspect(-50L))
    }

    @Test
    fun `skew 为 null 时不判 suspect——缺证据不等于有问题`() {
        assertFalse(wallClockSuspect(null))
    }

    @Test
    fun `阈值边界是半开的：恰好等于阈值不判，超过才判`() {
        assertFalse(wallClockSuspect(WALL_SKEW_MAX_MS))
        assertTrue(wallClockSuspect(WALL_SKEW_MAX_MS + 1))
    }

    /**
     * 绊线（T64 §8.6 第三条，同 T66/D-508 形状）：阈值必须**同时**落在两侧硬约束之间——
     * 高于正常网络/NTP 抖动，且低于「错一天」这个足以毁掉按日分桶的偏差。
     * 有人把它调到区间外（为"更灵敏"调到 100ms，或为"少报警"调到 2 天），本测试即红。
     */
    @Test
    fun `绊线：阈值须夹在「正常抖动」与「错一天」之间`() {
        val normalJitterCeilingMs = 1_000L // NTP 日常偏差 <1s；本项目实测 RTT 上界 106ms
        val oneDayMs = 24L * 60 * 60 * 1000
        assertTrue(
            "阈值 $WALL_SKEW_MAX_MS 低于正常抖动上界 $normalJitterCeilingMs，会把正常波动报成钟错",
            WALL_SKEW_MAX_MS > normalJitterCeilingMs,
        )
        assertTrue(
            "阈值 $WALL_SKEW_MAX_MS 高于一天 $oneDayMs，按日分桶已经错了它还不报",
            WALL_SKEW_MAX_MS < oneDayMs,
        )
    }
}
