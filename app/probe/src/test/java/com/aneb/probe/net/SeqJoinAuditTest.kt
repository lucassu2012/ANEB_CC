package com.aneb.probe.net

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * [SeqJoinAudit] 的补充夹具（R-08，C-3）。
 *
 * 🔴 **这组测试只写两条，而这个「只」字是量出来的、不是估的**：
 * `engine/AbRunnerTest` 早已覆盖本函数的主干（它测 `sampleKpi`，而 `sampleKpi` 现在委派给这里）。
 * 我对本实现跑了四条突变，**先量既有覆盖能咬住哪几条**：
 *
 * | 突变 | AbRunnerTest 单独 |
 * |---|---|
 * | 重复判据反转（`!seen.add` → `seen.add`） | **CAUGHT** ⇒ 不重复造 |
 * | `gapCount` 丢掉尾部整体缺失 | **CAUGHT** ⇒ 不重复造 |
 * | `received` 改用 `events.size` | **SURVIVED** ⇒ 本文件第一条 |
 * | 去掉 `coerceAtLeast(0)` 下钳 | **SURVIVED** ⇒ 本文件第二条 |
 *
 * ⚠ **别因为「AbRunnerTest 已经测了 seq 审计」就删掉本文件**：它的夹具是
 * `seq=[0,1,1,3]`、`expectedTokens=6`，其中 **`events.size` 恰好等于 `maxSeq+1`**（都是 4——
 * 重复带来的 +1 与区间缺口带来的 −1 正好抵消）⇒ **那个夹具在两种写法下给出同一个数，
 * 它分辨不了它们**。这不是那条测试的缺陷，是夹具取值的巧合；本文件补的正是这个分辨点。
 *
 * ⚠ 附一条我自己的教训：`received` 不能用 `events.size` 这件事，**我先把它写进了
 * [SeqJoinAudit] 的注释**，然后突变审计告诉我**没有任何东西守着它**。
 * **把判据写进注释 ≠ 判据被守住。**
 */
class SeqJoinAuditTest {

    private fun token(seq: Long) = TokenEvent(
        seq = seq,
        schedUs = seq * 20_000,
        preFlushUs = seq * 20_000,
        arrivalNanos = seq * 20_000_000,
        payloadBytes = 100,
        sameReadBatch = false,
    )

    @Test
    fun `尾部缺失按去重后的 maxSeq 算_不按事件条数`() {
        // seq = 0,1,1,2（4 个事件、3 个不同 seq），期望 6。
        // 正确：maxSeq=2 ⇒ received=3 ⇒ 尾缺 {3,4,5}=3；区间 [0..2] 无缺口 ⇒ gapCount=3。
        // 若改用 events.size(=4) 当 received ⇒ 尾缺算成 2 ⇒ gapCount=2，**少报一个缺失 token**。
        // ⚠ 这个夹具刻意让 events.size(4) ≠ maxSeq+1(3)，否则两种写法给出同一个数
        //   —— AbRunnerTest 的夹具正是恰好相等的那种，故它对这条完全无感。
        val r = SeqJoinAudit.audit(
            listOf(token(0), token(1), token(1), token(2)), expectedTokens = 6,
        )
        assertEquals(
            "若这里等于 2，说明尾部缺失是按事件条数算的——" +
                "dupseq 注入下事件比实收 seq 多，会把缺失的尾巴算没",
            3, r.gapCount,
        )
        assertEquals("尾缺 {3,4,5}", 3, r.tailMissing)
        assertEquals("重复一次", 1, r.duplicateCount)
        assertEquals(2L, r.maxSeq)
        assertTrue(r.truncatedEarly)
    }

    @Test
    fun `服务端多发时尾部缺失下钳到零_gapCount 不得为负`() {
        // seq = 0..4（收到 5 个），而 profile 只声明 3 个 ⇒ received(5) > expected(3)。
        // 正确：tailMissing 下钳到 0，gapCount=0，不判截断。
        // 去掉下钳 ⇒ tailMissing=−2 ⇒ gapCount=−2：**一个负的缺失计数**，
        // 它会一路流进 gapVerdict，并且**能把别处真实的 gap 抵消掉**——
        // 那比报错更坏，因为结果看起来只是「更干净」。
        val r = SeqJoinAudit.audit(
            (0L..4L).map(::token), expectedTokens = 3,
        )
        assertEquals("负的 gapCount 会抵消掉别处真实的缺口", 0, r.gapCount)
        assertEquals(0, r.tailMissing)
        assertEquals(0, r.duplicateCount)
        assertFalse("收得比预期多不是截断", r.truncatedEarly)
    }
}
