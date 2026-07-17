package com.aneb.probe.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * weak-recovery-v1 合同目标判定锚定（D-40；TEST_SERVER_CAPABILITIES §5：
 * 恢复≤3000ms ∧ 恢复后 12 请求成功率≥95% ∧ RTT P95≤300ms；缺输入不可判→null，R-10）。
 */
class SyntheticRecoveryRunnerTest {

    @Test
    fun `全部达标_true`() {
        assertEquals(
            true,
            SyntheticRecoveryRunner.meetsTargets(recoveryMs = 2100.0, successes = 12, total = 12, rttP95Ms = 152.6),
        )
    }

    @Test
    fun `恢复超时或成功率或RTT不达标_false`() {
        assertEquals(false, SyntheticRecoveryRunner.meetsTargets(3100.0, 12, 12, 150.0)) // 恢复>3000
        assertEquals(false, SyntheticRecoveryRunner.meetsTargets(2000.0, 11, 12, 150.0)) // 11/12≈91.7%<95%
        assertEquals(false, SyntheticRecoveryRunner.meetsTargets(2000.0, 12, 12, 320.0)) // RTT P95>300
    }

    @Test
    fun `输入缺失_不可判null不硬判`() {
        assertNull(SyntheticRecoveryRunner.meetsTargets(null, 12, 12, 150.0))
        assertNull(SyntheticRecoveryRunner.meetsTargets(2000.0, 12, 12, null))
        assertNull(SyntheticRecoveryRunner.meetsTargets(2000.0, 0, 0, 150.0))
    }

    @Test
    fun `p95最近秩_与项目分位手法一致`() {
        // 12 样本 → rank=ceil(0.95*12)=12 → 最大值
        val xs = (1..12).map { it * 10.0 }
        assertEquals(120.0, SyntheticRecoveryRunner.p95(xs)!!, 1e-9)
        assertNull(SyntheticRecoveryRunner.p95(listOf(1.0))) // <2 → null
    }
}
