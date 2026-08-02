package com.aneb.probe.ui

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * [KeepScreenOnPolicy] 纯逻辑单测（T25，D-427）。钉的是"该不该持有"这个可判定的
 * 决策，不是 `window.addFlags`/`clearFlags` 本身——那部分需要真机验证（本仓
 * app/probe 只有 JVM JUnit，无 Robolectric/instrumented test）。
 */
class KeepScreenOnPolicyTest {

    @Test
    fun autorun_holdsScreenOn() {
        val p = KeepScreenOnPolicy()
        p.onCreate(autorun = true)
        assertTrue(p.held)
    }

    @Test
    fun manual_neverHoldsScreenOn() {
        // 手动模式（autorun=false）零改动：held 恒为 false，MainActivity 因此
        // 从不调用 window.addFlags——这是"additive，只动 autorun 路径"的落地方式。
        val p = KeepScreenOnPolicy()
        p.onCreate(autorun = false)
        assertFalse(p.held)
    }

    @Test
    fun onDestroy_releasesAfterAutorunHold() {
        val p = KeepScreenOnPolicy()
        p.onCreate(autorun = true)
        assertTrue(p.held)
        p.onDestroy()
        assertFalse(p.held)
    }

    @Test
    fun onDestroy_withoutPriorHold_isSafeNoop() {
        // 手动模式下 onDestroy 被调用（Activity 销毁的一部分）时，held 已是 false，
        // 释放动作必须是空操作，绝不能误清一个从未持有过的标志。
        val p = KeepScreenOnPolicy()
        p.onCreate(autorun = false)
        p.onDestroy()
        assertFalse(p.held)
    }

    @Test
    fun secondOnCreate_reevaluatesFromCurrentAutorunFlag() {
        // 生命周期状态机不缓存历史：每次 onCreate 只看这一次传入的 autorun 值——
        // 覆盖"前一次持有、这一次是手动模式"与反向两种交替，均不应互相污染。
        val p = KeepScreenOnPolicy()
        p.onCreate(autorun = true)
        assertTrue(p.held)
        p.onDestroy()
        p.onCreate(autorun = false)
        assertFalse(p.held)
        p.onCreate(autorun = true)
        assertTrue(p.held)
    }
}
