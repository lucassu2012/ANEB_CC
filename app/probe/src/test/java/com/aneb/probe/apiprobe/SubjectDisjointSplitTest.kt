package com.aneb.probe.apiprobe

import com.aneb.probe.apiprobe.SubjectDisjointSplit.ParsedObs
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * [SubjectDisjointSplit.assign] 锚定（spine-1 §3.2/§4，合成 fixture）：主体不重叠、id 零交集、
 * 计数下限达标/不足如实记 shortfall（不硬凑）、确定性、空输入。
 */
class SubjectDisjointSplitTest {

    /** n 条同 subject 同 workload 的 obs（id=subject-workload-i）。 */
    private fun obs(subject: String, workload: String, n: Int): List<ParsedObs> =
        (1..n).map { ParsedObs("$subject-$workload-$it", subject, workload) }

    @Test
    fun `each subject stays whole in one partition`() {
        val all = obs("s1", "text", 5) + obs("s2", "text", 5) + obs("s3", "text", 5)
        val r = SubjectDisjointSplit.assign(all, minTrain = 1, minHoldout = 1)
        for (s in listOf("s1", "s2", "s3")) {
            val ids = all.filter { it.subjectGroupId == s }.map { it.observationId }.toSet()
            val inTrain = ids.all { it in r.training }
            val inHold = ids.all { it in r.holdout }
            assertTrue("$s 必须整体落在一侧（异或）", inTrain xor inHold)
        }
    }

    @Test
    fun `partitions are id-disjoint and cover all observations`() {
        val all = obs("s1", "text", 3) + obs("s2", "text", 3)
        val r = SubjectDisjointSplit.assign(all, minTrain = 1, minHoldout = 1)
        assertTrue("train/holdout 零交集", (r.training.toSet() intersect r.holdout.toSet()).isEmpty())
        assertEquals("覆盖全部 obs", all.map { it.observationId }.toSet(), (r.training + r.holdout).toSet())
        assertEquals("无重复成员", r.training.size + r.holdout.size, (r.training + r.holdout).toSet().size)
    }

    @Test
    fun `meets per-workload mins with sufficient subjects and no shortfall`() {
        val all = (1..30).flatMap { obs("s%02d".format(it), "text", 1) } // 30 主体各 1 条 text
        val r = SubjectDisjointSplit.assign(all) // 默认 20/10
        assertTrue("充足数据→无 shortfall: ${r.shortfalls}", r.shortfalls.isEmpty())
        assertEquals(20, r.training.size)
        assertEquals(10, r.holdout.size)
    }

    @Test
    fun `records shortfall honestly when insufficient and never pads`() {
        val all = (1..15).flatMap { obs("s%02d".format(it), "text", 1) } // 仅 15 < 20+10
        val r = SubjectDisjointSplit.assign(all) // 默认 20/10
        assertTrue("train 不足如实记 shortfall", r.shortfalls.any { it.contains("text") && it.contains("train") })
        assertEquals("不硬凑：总数守恒", 15, r.training.size + r.holdout.size)
        assertEquals("holdout 先满足", 10, r.holdout.size)
        assertEquals("train 短缺如实", 5, r.training.size)
    }

    @Test
    fun `is deterministic for same input`() {
        val all = (1..12).flatMap { obs("s%02d".format(it), "text", 1) }
        assertEquals(SubjectDisjointSplit.assign(all), SubjectDisjointSplit.assign(all))
    }

    @Test
    fun `empty input yields empty result`() {
        val r = SubjectDisjointSplit.assign(emptyList())
        assertTrue(r.training.isEmpty() && r.holdout.isEmpty() && r.shortfalls.isEmpty())
    }
}
