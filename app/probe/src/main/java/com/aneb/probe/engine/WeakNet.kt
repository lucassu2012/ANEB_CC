package com.aneb.probe.engine

/**
 * 弱网伴流调试开关解析——**纯 JVM**（零 Android 依赖，单测直接调用）。
 *
 * `contend:N` 是**调试弱网**开关（非取证；仅 DEBUG/UI 门控）：run 全程并行 N 条背景下行大流对
 * 接入链路制造真实拥塞（bufferbloat）。见 `docs/WEAK_NETWORK_SIMULATION.md §2`。
 *
 * 本对象只做**解析**（把 `--es weaknet "contend:N"` 的字符串规格解析为并行流数 N），拥塞流的
 * 编排由各引擎（[TestEngine] token 模式 / [SpeedRunner] basic_network 模式）各自实现。抽取自
 * TestEngine 原内联解析（行为逐位一致），使解析可单测、且两引擎共用单一事实源（免弱网开关在
 * SpeedTest 模式静默失效——B1，crosscut runbook §1.3/§7）。
 */
object WeakNet {

    /** 拥塞并行流数下限（1 条起，`contend:0` 抬到 1）。 */
    const val CONTEND_MIN = 1

    /** 拥塞并行流数上限（8 条封顶，防调试开关打爆设备/链路）。 */
    const val CONTEND_MAX = 8

    /**
     * 解析 `contend:N` → 并行拥塞流数（[CONTEND_MIN]..[CONTEND_MAX]）。
     * 无 `contend:` 前缀 / 非数字 / null → null（不启拥塞）。`contend:0`→1、`contend:9`→8（钳制）。
     */
    fun parseContendN(spec: String?): Int? =
        spec?.substringAfter("contend:", "")?.trim()?.toIntOrNull()?.coerceIn(CONTEND_MIN, CONTEND_MAX)
}
