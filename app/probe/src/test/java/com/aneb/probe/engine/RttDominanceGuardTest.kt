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

    @Test fun `ratio 恰为 15 且其余达标时判安全（大于等于，D-499 后阈值）`() {
        val v = RttDominanceGuard.evaluate(windowActualMs = 1500.0, rttRefMs = 100.0, bytesTransferred = 200_000L)
        assertEquals(15.0, v.ratio!!, 1e-9)
        assertTrue(v.ok)
    }

    @Test fun `ratio 14_99 判不安全（D-499 后阈值）`() {
        val v = RttDominanceGuard.evaluate(windowActualMs = 1499.0, rttRefMs = 100.0, bytesTransferred = 200_000L)
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

    // ---- 绊线：window_ms 与 RTT_DOMINANCE_MIN 的耦合（T63/D-498 发现，本条为其落地守卫）----
    //
    // 判据的实际保护强度不是 RTT_DOMINANCE_MIN 单独决定的，而是这两个数的商：
    //     临界 RTT = window_ms / RTT_DOMINANCE_MIN
    // RTT 超过临界值的路径会被判 dominance_ok=false。两个数分处两个文件
    // （window_ms 在 profiles/s4_throughput.json，阈值在 RttDominanceGuard.kt），
    // 此前没有任何代码/注释/测试把它们联系起来——改动其一即静默改变保护强度
    // （把 window_ms 减半，RTT 保护也随之减半，而没有东西会说一句话）。这正是
    // D-264「一个常量是不是单一来源，别看它定义在哪——改它一次看数字动不动」的形状。
    //
    // 本测试不决定任何新常量，只把当前两个已定值的**乘积语义**钉住：任一被改动时
    // 本测试失败，迫使改动者回头读 T63 的敏感性分析
    // （docs/T63_RTT_DOMINANCE_CONSTANTS_SENSITIVITY_20260815.md）再决定另一个要不要跟着动。
    //
    // window_ms 从真实 profile 文件读取而非在此复制一份——否则只是又造了一个会
    // 各自漂移的副本（D-315 同名实现纪律）。

    /** 从模块工作目录（app/probe）向上找仓库根相对路径（同 VoiceExecutionPlanParityTest 惯例）。 */
    private fun repoFile(relFromRepoRoot: String): java.io.File {
        var cur: java.io.File? = java.io.File(System.getProperty("user.dir") ?: ".").absoluteFile
        while (cur != null) {
            val cand = java.io.File(cur, relFromRepoRoot)
            if (cand.isFile) return cand
            cur = cur.parentFile
        }
        error("找不到 $relFromRepoRoot（从 user.dir 向上未命中）")
    }

    /** 读 s4_throughput profile 里两个 adaptive window 相位的 window_ms（应一致）。 */
    private fun profileWindowMs(): Int {
        val text = repoFile("profiles/s4_throughput.json").readText(Charsets.UTF_8)
        val found = Regex("\"window_ms\"\\s*:\\s*(\\d+)").findAll(text)
            .map { it.groupValues[1].toInt() }.toList()
        assertTrue("profile 里应有至少两个 window_ms（上下行各一）", found.size >= 2)
        assertEquals("上下行 window_ms 不一致会让临界 RTT 两个方向不同，本绊线的前提失效",
            1, found.distinct().size)
        return found.first()
    }

    @Test fun `绊线 window_ms 与阈值的商即临界RTT 任一改动都应让本测试失败（T63D-498）`() {
        val windowMs = profileWindowMs()
        val threshold = RttDominanceGuard.RTT_DOMINANCE_MIN

        // 当前双方已定值：4000ms 窗口（批②落地）÷ 阈值 15（D-499 拍板转正）≈ 266.67ms 临界。
        assertEquals("window_ms 变了：请回读 T63 敏感性分析，确认阈值是否要跟着动", 4000, windowMs)
        assertEquals("RTT_DOMINANCE_MIN 变了：请回读 T63/D-499（[10,37] 对现有语料等价；改值须新 D 号）",
            15.0, threshold, 1e-9)

        val criticalRttMs = windowMs / threshold
        assertEquals("临界 RTT = window_ms / 阈值", 4000.0 / 15.0, criticalRttMs, 1e-9)
    }

    @Test fun `绊线 恰在临界RTT上的路径判安全 略超即判不安全（临界值真的是那个数）`() {
        val windowMs = profileWindowMs().toDouble()
        val criticalRttMs = windowMs / RttDominanceGuard.RTT_DOMINANCE_MIN

        // 恰好等于临界 RTT：ratio 恰为阈值，按 >= 语义判安全
        val atCritical = RttDominanceGuard.evaluate(
            windowActualMs = windowMs, rttRefMs = criticalRttMs, bytesTransferred = 200_000L)
        assertTrue("RTT 恰在临界值上应判安全（ratio 恰等于阈值）", atCritical.ok)

        // 略超临界 RTT：ratio 跌破阈值，判不安全
        val justOver = RttDominanceGuard.evaluate(
            windowActualMs = windowMs, rttRefMs = criticalRttMs * 1.01, bytesTransferred = 200_000L)
        assertFalse("RTT 略超临界值即应判不安全", justOver.ok)
    }
}
