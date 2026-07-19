package com.aneb.probe.engine

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * 弱网伴流调试开关（解析 + 拥塞编排）——**零 Android 依赖**，单测直接调用。
 *
 * `contend:N` 是**调试弱网**开关（非取证；仅 DEBUG/UI 门控）：run 全程并行 N 条背景下行大流对
 * 接入链路制造真实拥塞（bufferbloat）。见 `docs/WEAK_NETWORK_SIMULATION.md §2`。
 *
 * [parseContendN] 解析规格、[launchContendDrains] 编排拥塞流——两引擎（[TestEngine] token 模式 /
 * [SpeedRunner] basic_network 模式）**共用同一事实源**，免弱网开关在 SpeedTest 模式静默失效
 * （crosscut runbook §1.3/§7 B1/B2）。抽取自 TestEngine 原内联实现（行为逐位一致）。
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

    /**
     * 在 [scope] 内起 [n] 条背景拥塞流——各流 `while(isActive){ runCatching { drain() } }` 循环
     * 制造持续下行拥塞，返回可取消的 [Job] 列表（调用方须在 run 收尾/finally 统一 cancel）。
     * 用独立 [drain]（调用方传入独立 client 的 downloadDrain）免污染测量连接池；`runCatching`
     * 吞瞬时错误让流持续（cancel 时 isActive=false 使循环退出）。两引擎共用此编排（B2）。
     */
    fun launchContendDrains(scope: CoroutineScope, n: Int, drain: suspend () -> Unit): List<Job> =
        List(n) {
            scope.launch(Dispatchers.IO) {
                while (isActive) { runCatching { drain() } }
            }
        }
}
