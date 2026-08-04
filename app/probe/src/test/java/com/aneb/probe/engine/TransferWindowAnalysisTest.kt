package com.aneb.probe.engine

import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * [TransferWindowAnalysis.estimateSlowStartByRate] 锚定（spec §8.3.4，T47 批②，
 * D-468/D-469）。三种必测夹具（spec 明文要求）+ 两条边界补充，均为构造出的反例而非
 * 纯推理（D-321/D-322 纪律）。
 */
class TransferWindowAnalysisTest {

    private fun sample(tMs: Long, bytes: Long) = Pair(bytes, tMs * 1_000_000L)

    // ---- 夹具①：恒定速率流（无爬坡）应返回 null ----

    @Test fun `恒定速率流全程 1000 字节每毫秒应返回 null`() {
        // 21 个采样点，t=0..4000ms 每 200ms 一个，速率恒为 1000 bytes/ms——
        // 稳态窗口（末尾 1s）算出的速率与全程完全一致，瞬时速率从不低于阈值，
        // 意味着"从未观测到先低后高的转折"，函数必须诚实返回 null 而不是猜一个假的转折点。
        val samples = (0..20).map { i -> sample(i * 200L, i * 200L * 1000L) }
        assertNull(TransferWindowAnalysis.estimateSlowStartByRate(samples))
    }

    // ---- 夹具②：前 1s 明显低速、之后转为 4 倍速 → 应返回接近 1s 的 slowStartUs ----

    @Test fun `前1秒低速后转4倍速的合成流应在约1秒处检出转折`() {
        // t∈[0,1000]ms：1000 bytes/ms（慢）；t∈(1000,4000]ms：4000 bytes/ms（稳态，4 倍速）。
        // 稳态窗口取末尾 1s（t=3000..4000ms，完全落在快速段）算出稳态速率 4000 bytes/ms，
        // 阈值=2000。慢速段瞬时速率 1000<2000（先低），快速段瞬时速率 4000>=2000（后高）。
        val samples = (0..40).map { i ->
            val t = i * 100L
            val bytes = if (t <= 1000L) t * 1000L else 1_000_000L + (t - 1000L) * 4000L
            sample(t, bytes)
        }
        val result = TransferWindowAnalysis.estimateSlowStartByRate(samples)
        assertTrue("必须检出转折（不能返回 null）", result != null)
        val (slowStartUs, slowStartBytes) = result!!
        // 允许滑动探测窗口（200ms）本身带来的滞后，接近 1s 定义为 [0.9s, 1.4s] 区间
        assertTrue(
            "slowStartUs=$slowStartUs 应接近 1s（900_000..1_400_000us）",
            slowStartUs in 900_000L..1_400_000L,
        )
        assertTrue("slowStartBytes 应为正", slowStartBytes > 0L)
    }

    // ---- 夹具③：样本数过少（窗口提前 underrun）应返回 null ----

    @Test fun `样本数少于4个应返回null`() {
        val samples = listOf(sample(0, 0), sample(100, 50_000))
        assertNull(TransferWindowAnalysis.estimateSlowStartByRate(samples))
    }

    // ---- 边界补充：稳态窗口本身零字节进度（steadyBytes<=0），不可信时不猜 ----

    @Test fun `稳态窗口内字节数无增长时返回null`() {
        val samples = listOf(sample(0, 0), sample(3, 0), sample(6, 0), sample(10, 0))
        assertNull(TransferWindowAnalysis.estimateSlowStartByRate(samples))
    }

    @Test fun `反例证伪——把快慢两段对调后不应再检出原转折点`() {
        // D-321/D-322纪律：不满足于"能返回非null"，要证明函数对时序敏感、不是恒定返回同一答案。
        // 先快后慢（先高后低，从未出现"先低后高"）应返回 null，与夹具②的"先低后高"结果不同。
        val samples = (0..40).map { i ->
            val t = i * 100L
            val bytes = if (t <= 1000L) t * 4000L else 4_000_000L + (t - 1000L) * 1000L
            sample(t, bytes)
        }
        assertNull(
            "先快后慢从未出现'先低后高'的转折，必须返回 null——证明函数不是无脑返回非 null",
            TransferWindowAnalysis.estimateSlowStartByRate(samples),
        )
    }
}
