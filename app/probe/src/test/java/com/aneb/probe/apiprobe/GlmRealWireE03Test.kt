package com.aneb.probe.apiprobe

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * E-03 P1：拿 **GLM 真端点的 wire** 喂**生产解析器**，与服务端 `usage` 对账。
 *
 * ## 为什么在这里，而不是在 Python 侧数
 *
 * 本批要校的是**别人真正在用的那份代码**。若在采集脚本里另写一份计数，校的就是**一份
 * 重新实现** —— 本仓为「我验的对象与别人要用的对象是不是同一个」付过学费。
 * [LlmStreamAdapter] 的 KDoc 自己写着「纯函数、无 Android 依赖，**JVM 单测直接喂固定
 * 夹具**」，所以这不是绕路，是它写明的用法。**因此本批不需要设备。**
 *
 * ## 对照量的来源与它的边界
 *
 * `usage.completion_tokens` 是本批**唯一有独立实现背书**的量：它由 GLM 侧算出，
 * 与我们数 delta 的规则**不共享任何一层**。⚠ 在 mock 上做同样的对账**没有意义** ——
 * mock 的 usage 与它的 token 流出自同一段代码，一致是**构造保证**的
 * （本仓「同一缺陷喂出两个假独立方法」）。
 *
 * ⚠ **不等时不预设哪边对**：命题单登记了两解并列（分词口径差 / 量法缺陷）。
 * 本测试若红，**先看差值形态再下结论，不要直接改解析器去迁就 usage**。
 *
 * ## 真 wire 带来的、mock 没有的形态（本批实测）
 *
 * GLM 把 `usage` 挂在**带 `finish_reason` 的那一帧**上，不是独立的 usage-only 尾帧；
 * 而 [OpenAiSseAdapter] 注释提到的正是后者。**两种形态解析器都得吃得下**，
 * 此前只在 mock 上见过一种。
 */
class GlmRealWireE03Test {

    private fun fixture(name: String): String {
        val stream = javaClass.getResourceAsStream("/glm_e03/$name.sse")
        assertNotNull("真 wire 夹具缺失：/glm_e03/$name.sse", stream)
        // ⚠ **归一化行尾，否则新 clone 上整条测试会静默变样**：git 会按 autocrlf
        // 把 `.sse` checkout 成 CRLF，而 [SseFixtures.toRawEvents] 按 "\n\n" 切 event
        // ⇒ CRLF 下**一个 event 都切不出来，整条流被当成一个**，解析结果面目全非。
        // 行尾不是被测对象（抓取时 `\r\n` 已被剥掉），故这里归一化是**恢复语义**不是掩盖。
        // 仓内 `.gitattributes` 全仓策略单列待裁、试点期禁动，故修在消费方。
        return stream!!.bufferedReader(Charsets.UTF_8).use { it.readText() }
            .replace("\r\n", "\n").replace("\r", "\n")

    }

    private fun parseFixture(name: String): LlmParseResult =
        OpenAiSseAdapter().parse(SseFixtures.toRawEvents(fixture(name)))

    /** 三笔冒烟全部走一遍：**逐笔都要对账**，不许只看一笔就宣布命题成立。 */
    private val cells = listOf("smoke_a", "smoke_b", "smoke_c")

    /**
     * 该轮是否进 **P3 形状池**。判据与命题单 §1c 同源：**`finish_reason` 非 `stop` 不进**。
     *
     * ⚠ **它仍然进 P1 差额分析** —— 两个用途不混池：截断轮的 usage 反映的是**实际吐出的量**，
     * 对「解析器数出 vs usage」的对账**依然有效**；而它的**形状**（速率曲线、静默）被
     * 人为截断，进 P3 会污染形状结论。
     *
     * ⚠ 判据落在**解析器产出的 `stopReason`** 上，不落在采集器上：
     * 采集器**刻意不解析**（本批设计核心，有守卫钉着），而生产解析器本就产出这个字段。
     * **为了记一个字段而在采集器里开一个解析的口子，会把「校生产量法」退化成「校重新实现」。**
     */
    private fun inP3Pool(r: LlmParseResult): Boolean = r.stopReason == "stop"

    @Test
    fun `production parser survives the real wire without silent damage`() {
        // P2：危险的不是解析失败（那会计数），是**解析成功而结果是错的**。
        // 本条只排除「连解析都没走完」这一层；真正的判据是下面的 P1。
        for (c in cells) {
            val r = parseFixture(c)
            assertEquals("$c: 解析器报了 parseErrors", 0, r.parseErrors)
            assertNull("$c: 解析器报了 protocolError", r.protocolError)
            // ⚠ **不把 "stop" 写死**：D-661④ 的 3×3 里，短/中两档 `max_tokens` 压在自然
            // 长度以下 ⇒ 预期 `finish_reason=length`。写死 "stop" 会让那六笔**一到就红，
            // 而红的理由是错的**（它们本就该是 length，不是缺陷）。
            // 判的是**池规则**不是那个值：非 `stop` 的轮**不进 P3 形状池，只进 P1 差额分析**
            // （§1c 已写死）。⇒ 这里只断言它是**已登记的两种之一**；
            // 谁进 P3 由 [inP3Pool] 决定，判据与单子同源。
            assertTrue(
                "$c: finish_reason=${r.stopReason} 不是已登记的取值（stop/length）—— " +
                    "出现第三种就说明池规则没覆盖它，必须先回单子登记再跑",
                r.stopReason in setOf("stop", "length"),
            )
            assertTrue("$c: 一个 token 都没数到 —— 夹具或切分坏了", r.arrivals.isNotEmpty())
        }
    }

    @Test
    fun `the parser counts exactly the non-empty content frames`() {
        // P1 的**已确立**那一半：解析器完全按它文档写的规则在做，**零误计**。
        // 实测三笔：非空 content 帧 243/265/241，解析器数出 243/265/241 —— 一个不差。
        // ⇒ 「解析器数错了」这条**已被排除**；这条守卫防的是将来有人改坏它。
        for (c in cells) {
            val text = fixture(c)
            // ⚠ **等价性的前提**：生产规则还认 `reasoning_content`（推理模型用），
            // 而本条的独立计数只认 `content` ⇒ **本条比生产规则窄**。
            // 在本批夹具上两者等价，**因为这里一个 reasoning_content 都没有** —— 
            // 把这个前提断言出来，否则将来换成推理模型时本条会因**错误的理由**变红。
            assertTrue(
                "$c: 夹具里出现了 reasoning_content —— 本条的独立计数比生产规则窄，不再等价",
                !text.contains("reasoning_content"),
            )
            val frames = text.lineSequence()
                .filter { it.startsWith("data:") && it.trim() != "data: [DONE]" }
                .count { line ->
                    // 只做**形态计数**，不复制解析规则：找 delta 里非空 content 的帧。
                    Regex(""""delta"\s*:\s*\{[^}]*"content"\s*:\s*"(?!")""")
                        .containsMatchIn(line)
                }
            assertEquals("$c: 解析器数出的不等于非空 content 帧数", frames, parseFixture(c).arrivals.size)
        }
    }

    @Test
    fun `arrivals are content frames not tokens and the gap is a small constant`() {
        // ⚠ **本批最要紧的发现，而它是一条关于命名的发现，不是关于算错的发现。**
        //
        // `arrivals` 被下游当「token 到达」用（ITL、token 速率都由它算），
        // **而它实为「内容帧到达」**。真端点上两者不等：
        //   smoke_a 243 vs usage 248（-5）／smoke_b 265 vs 269（-4）／smoke_c 241 vs 246（-5）
        //
        // **差额恒定在 4–5，与响应长度无关**（帧数 241–265 而差额不随之变）
        // ⇒ 签名是**固定开销**，不是**按帧合并**（后者会随长度成比例；
        // 实测多字符帧有 21/12/14 个，远多于差额，合并解释不了它）。
        // ⚠ 领先候选＝GLM 计入了若干**不下发**的特殊/格式 token；**没有它的分词器证不了**，
        // 故按命题单登记的规则**允许「不可归因」，不硬选**。
        //
        // ⚠ 为什么不把这条写成「相等」的红门：**P1 的结论是「不成立」，那是本批的产出，
        // 不是一个待修的 bug**。把结论钉成永久红门，会让下一个人去「修」一个没坏的解析器。
        // 本条改钉**形态**：解析器不多数、差额不爆炸。形态一变即红。
        //
        // 🔴 **在 mock 上这条永远看不出来**：mock 每帧一 token 且 usage 与 token 流同源
        // ——一致是构造保证的。这正是本批要真端点的理由。
        for (c in cells) {
            val r = parseFixture(c)
            val usage = r.outputTokens!!
            val gap = usage - r.arrivals.size
            assertTrue("$c: 解析器数得比 usage 还多（$gap）—— 形态变了，本条的诊断不再适用", gap >= 0)
            assertTrue("$c: 差额 $gap 超出实测区间 0..12，形态已变，需重新归因", gap <= 12)
        }
    }

    @Test
    fun `pool membership follows finish reason and the smoke three all qualify`() {
        // ⚠ 让 [inP3Pool] **承重**，否则它就是「写了门没挂上」。
        // 断言的是**关于数据的事实**：三笔冒烟 `finish_reason` 全为 `stop`（`max_tokens=800`
        // 未生效、模型自然停）⇒ **三笔全进 P3 池**。
        // ⚠ **3×3 落地后本条的期望要改成「九取三」**：短/中两档压在自然长度以下、预期
        // `length` ⇒ 只有长档进 P3。**改期望时连这句一起改**，别只改数字。
        val inPool = cells.count { inP3Pool(parseFixture(it)) }
        assertEquals(
            "冒烟三笔应全部进 P3 池（全为 stop）；若这里变了，要么参数变了、" +
                "要么 GLM 的自然停长度变了 —— 两种都得先回单子登记再继续",
            3, inPool,
        )
    }

    @Test
    fun `the fixtures really are three distinct captures`() {
        // ⚠ 防一种静默失败：三份夹具若因转换出错而内容相同，上面两条会「三笔全过」
        // 而实际只验了一笔。**n 是这里唯一撑得住「逐笔都对账」这句话的东西。**
        val texts = cells.map { fixture(it) }
        assertEquals("夹具去重后少于三份 —— 三笔冒烟没有真的各自入夹具", 3, texts.toSet().size)
    }
}
