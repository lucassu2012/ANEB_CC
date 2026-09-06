package com.aneb.probe.net

/**
 * seq join 连续性审计（R-08）——gap／duplicate／尾部整体截断的**单一实现**。
 *
 * **为什么抽出来（两个理由，第二个更硬）**：
 * 1. 这段判读此前**内联在 [AnebClient.stream] 的 `executeCancellable` 块里**，
 *    要跑到它得起一条真实 SSE 流 ⇒ **一行都没被单测覆盖过**。而服务端的三种故障注入
 *    （`dupseq`／`malformed`／`truncate`，见 `server/handlers_stream.go`）**正是冲它来的**。
 * 2. 🔴 **它有两份**：`AnebClient.stream` 与 `engine/AbRunner.sampleKpi` **逐行同构**
 *    （仅变量名 `duplicates`／`dups` 之差），而 `AbRunner` 的 KDoc 还自注「同 AnebClient.stream」
 *    —— **重复被记录了，然后就留在那儿**。两份都没被测过，且**任何一方改了，另一方不会有任何提示**。
 *    本次两处都改为调用本函数，**合并前已逐行核对两份语义一致**（不是看注释说一致）。
 *
 * **口径（承 R-08，逐字搬运，语义未变）**：
 * - `duplicateCount` ＝ 同一 seq 出现多次的次数（按 join 判，**禁按数组位置配对**）；
 * - `gapCount` ＝ `[0..maxSeq]` 区间内缺失的 seq 数 **加上** [Result.tailMissing]；
 * - `tailMissing` ＝ `expectedTokens − (maxSeq+1)`，下钳到 0。
 */
object SeqJoinAudit {

    /**
     * @param gapCount 已含 [tailMissing]，即上层 `StreamResult.gapCount` 的口径
     * @param maxSeq 收到的最大 seq；**一个 token 都没收到时为 null**（R-10：不是 0）
     * @param tailMissing 尾部整体缺失数；单列是因为 [truncatedEarly] 由它派生，
     *   而两个调用点若各自用 `gapCount > 0` 去判截断，会把**区间内部的 gap** 一起误判成截断
     */
    data class Result(
        val gapCount: Int,
        val duplicateCount: Int,
        val maxSeq: Long?,
        val tailMissing: Int,
    ) {
        /** 流「干净结束」但收到的 token 少于预期 ⇒ 尾部整体截断（R-08 漏检分支）。 */
        val truncatedEarly: Boolean get() = tailMissing > 0
    }

    /**
     * @param events 已解析的 token 事件（顺序不重要，本审计按 seq join，不按到达次序）
     * @param expectedTokens profile 声明的 token 总数；用于补计尾部整体截断
     *
     * 🔴 **`tailMissing` 那一项是 R-08 的漏检补丁，不是锦上添花**：区间 `[0..maxSeq]`
     * 内部的 gap 靠下面那个 while 就能查出来，但**尾部被整段砍掉时 maxSeq 自己就变小了**，
     * 于是区间扫描**一个缺口都看不见、`gapCount` 为 0、判读一路绿**。
     * 服务端的 `truncate` 注入测的正是这条路。
     */
    fun audit(events: List<TokenEvent>, expectedTokens: Int): Result {
        // R-08：按 seq join 校验连续性，禁数组位置配对。
        val seen = HashSet<Long>(events.size * 2)
        var duplicates = 0
        for (e in events) {
            if (!seen.add(e.seq)) duplicates++
        }
        val maxSeq = seen.maxOrNull()
        var gaps = 0
        if (maxSeq != null) {
            var s = 0L
            while (s <= maxSeq) {
                if (s !in seen) gaps++
                s++
            }
        }
        // ⚠ `received` 取自**去重后的 maxSeq**，不是 `events.size`：
        // 有 dupseq 注入时 events 比实收 seq 多，用 size 会把缺失的尾巴算没。
        val received = maxSeq?.plus(1L) ?: 0L
        val tailMissing = (expectedTokens - received).coerceAtLeast(0L).toInt()
        return Result(
            gapCount = gaps + tailMissing,
            duplicateCount = duplicates,
            maxSeq = maxSeq,
            tailMissing = tailMissing,
        )
    }
}
