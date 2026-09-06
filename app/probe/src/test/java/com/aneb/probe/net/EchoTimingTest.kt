package com.aneb.probe.net

import com.aneb.probe.net.AnebClient.Companion.echoOffsetUs
import com.aneb.probe.net.AnebClient.Companion.echoRttUs
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * `/echo` 四时戳还原式（[AnebClient.Companion.echoOffsetUs] / [echoRttUs]，设计文档 §4.2）。
 *
 * **这组测试存在的理由，写在这里以免日后被当成冗余删掉**：这两行此前**内联在
 * [AnebClient.echo] 里**，而 `echo()` 要跑起来需要一个会应答的对端 ⇒ **一行都没被验过**。
 * 而紧挨着它们的 `wallSkewMs` **早已抽出并由 [WallClockSkewTest] 钉住** ——
 * **同一个函数、相邻几行，抽了一个、漏了旁边那个。** 本组补齐漏掉的那个。
 *
 * ⚠ **本组覆盖的是「四个时戳 → 两个量」的映射，不覆盖「echo() 有没有把时戳喂对位」。**
 * 后者是纯函数够不着的一层（调用点传了什么，被调方看不见）；那里只有具名实参这道
 * **复核期**防御，**测试期仍是零覆盖**。写在这里，是因为同一天我在 `uploadWindow` 上
 * 实测过这层：两条接线突变（丢掉 serverView／改回旧计时点）**全套件无人咬住**。
 * **别把「判据已钉死」读成「这条路径已覆盖」。**
 *
 * **夹具怎么造的**（全部手算，非跑出来再抄）：设客户端钟为基准，服务端钟超前 `OFF`，
 * 单向网络时延 `D`，服务端处理时长 `S`，则
 * `t1 = t0 + D_up + OFF`、`t2 = t1 + S`、`t3 = t0 + D_up + S + D_down`。
 */
class EchoTimingTest {

    // 情形 A：对称路径（单向 25ms）、服务端处理 300ms、服务端钟超前 7s。
    private val aT0 = 1_000_000L
    private val aT1 = 8_025_000L      // t0 + 25_000 + 7_000_000
    private val aT2 = 8_325_000L      // t1 + 300_000
    private val aT3 = 1_350_000L      // t0 + 50_000 + 300_000

    @Test
    fun `rtt 必须减掉服务端处理时长_否则测的是服务端不是网络`() {
        assertEquals(
            "若这里等于 350000，说明服务端处理时长（300ms）没被减掉——" +
                "那测的是服务端花了多久，不是网络花了多久，且**七倍偏大而不报错**",
            50_000L, echoRttUs(aT0, aT1, aT2, aT3),
        )
    }

    @Test
    fun `服务端处理时长既不影响 rtt 也不影响 offset`() {
        // 情形 A′：与 A 同一条链路、同一个钟差，**只把 dwell 从 300ms 改成 0**。
        // t2 与 t1 重合，t3 相应提前 300ms。
        val bT0 = 1_000_000L
        val bT1 = 8_025_000L
        val bT2 = 8_025_000L          // dwell = 0
        val bT3 = 1_050_000L          // t0 + 50_000
        assertEquals(
            "dwell 变了而 rtt 应当不变——它在 (t3−t0) 与 (t2−t1) 里同时出现、正好抵消",
            echoRttUs(aT0, aT1, aT2, aT3), echoRttUs(bT0, bT1, bT2, bT3),
        )
        assertEquals(
            "dwell 变了而 offset 也应当不变——它在 (t1−t0) 与 (t2−t3) 里符号相反、自动抵消",
            echoOffsetUs(aT0, aT1, aT2, aT3), echoOffsetUs(bT0, bT1, bT2, bT3),
        )
        // 并钉住绝对值，否则「两边都坏成同一个错数」也能让上面两条通过。
        assertEquals(50_000L, echoRttUs(bT0, bT1, bT2, bT3))
        assertEquals(7_000_000L, echoOffsetUs(bT0, bT1, bT2, bT3))
    }

    @Test
    fun `offset 的方向是服务端钟减客户端钟_两个方向都钉`() {
        // ⚠ 符号反了是**静默**的：数值大小完全正确，只是意思相反，
        // 而下游拿它做加减时不会有任何一处报错。故两个方向都要有样本。
        assertEquals(
            "服务端超前 7s ⇒ offset 应为 +7_000_000（服务端钟 − 客户端钟）",
            7_000_000L, echoOffsetUs(aT0, aT1, aT2, aT3),
        )
        // 情形 B：同一条链路、同样的 dwell，服务端钟**落后** 7s。
        val cT0 = 9_000_000L
        val cT1 = 2_025_000L          // t0 + 25_000 − 7_000_000
        val cT2 = 2_325_000L
        val cT3 = 9_350_000L
        assertEquals(
            "服务端落后 7s ⇒ offset 应为 −7_000_000；若这里是 +7_000_000，符号反了",
            -7_000_000L, echoOffsetUs(cT0, cT1, cT2, cT3),
        )
        assertEquals("换个钟差不该改变 rtt", 50_000L, echoRttUs(cT0, cT1, cT2, cT3))
    }

    @Test
    fun `上下行不对称时_offset 有已知偏差而 rtt 免疫`() {
        // 情形 C：上行 5ms、下行 45ms（往返仍是 50ms），dwell 300ms，服务端超前 7s。
        // 本式固有偏差 = (D_up − D_down)/2 = (5_000 − 45_000)/2 = −20_000。
        // ⚠ 这条钉的是一个**已知局限，不是缺陷**（KDoc 写作「误差 ±RTT/2」）：
        // 把它写成用例，是免得日后有人把这个偏差当 bug「修」掉——
        // 四时戳法在单向不对称下**无法**分辨钟差与路径不对称，这是方法本身的边界。
        val t0 = 1_000_000L
        val t1 = 8_005_000L           // t0 + 5_000 + 7_000_000
        val t2 = 8_305_000L
        val t3 = 1_350_000L           // t0 + 5_000 + 300_000 + 45_000
        assertEquals(
            "非对称路径下 offset 应为真值 7_000_000 加固有偏差 −20_000",
            6_980_000L, echoOffsetUs(t0, t1, t2, t3),
        )
        assertEquals(
            "rtt 只看往返总和，与单向如何分配无关——这里必须仍是 50_000",
            50_000L, echoRttUs(t0, t1, t2, t3),
        )
    }
}
