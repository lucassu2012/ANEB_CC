package com.aneb.probe.ui

import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.sin
import kotlin.random.Random

/**
 * spine-4 核心洞察的机器锚定（蓝图 §0 → §5 golden）：**SpeedTest 级"动态感"来自
 * 随网络真实波动的指标；服务端 pacing 定速的 token 速率天生不动，绝不当波动主角。**
 *
 * 方法：合成序列（固定种子，确定性）喂 [GaugeMath.gaugeFraction] 同款归一，比指针
 * 分数序列的方差——吞吐显著波动、定速 token 速率≈平线。这是"指标选择问题不是 UI bug"
 * 的可执行证据：若日后有人把 token 速率接成动态主角（§4.3 现状 dynamic=true 的误导），
 * 本测试的数字即反驳依据（正式改口=PO 决策项，见蓝图 §2.2⚠）。
 */
class DynamismVisibilityGoldenTest {

    private fun variance(xs: List<Float>): Double {
        val mean = xs.map { it.toDouble() }.average()
        return xs.map { (it.toDouble() - mean) * (it.toDouble() - mean) }.average()
    }

    /** 真实网络样吞吐：均值 45 Mbps，慢波动（sin）+ 快抖动（±15），量程 100。 */
    private fun throughputFracs(): List<Float> {
        val rnd = Random(42)
        return (0 until 120).map {
            val mbps = 45.0 + 30.0 * sin(it / 7.0) + rnd.nextDouble(-15.0, 15.0)
            GaugeMath.gaugeFraction(mbps.coerceAtLeast(0.0), 100f)
        }
    }

    /** 服务端 pacing 定速 token 速率：40±0.5 tps（D-27 实测特征），同款归一。 */
    private fun tokenRateFracs(): List<Float> {
        val rnd = Random(42)
        return (0 until 120).map { GaugeMath.gaugeFraction(40.0 + rnd.nextDouble(-0.5, 0.5), 100f) }
    }

    @Test
    fun `fluctuating throughput drives visible gauge motion`() {
        assertTrue("吞吐指针分数方差应显著（波动可见）", variance(throughputFracs()) > 0.01)
    }

    @Test
    fun `paced token rate is visually flat so it must not be the dynamic hero`() {
        assertTrue("定速 token 速率指针方差≈0（视觉平线）", variance(tokenRateFracs()) < 1e-4)
    }

    @Test
    fun `contrast between the two is at least two orders of magnitude`() {
        val ratio = variance(throughputFracs()) / variance(tokenRateFracs())
        assertTrue("吞吐/token 速率方差比应 ≥100×（洞察量化钉死），实测 $ratio", ratio >= 100.0)
    }
}
