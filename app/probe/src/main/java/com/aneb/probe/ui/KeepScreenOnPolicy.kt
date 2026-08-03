package com.aneb.probe.ui

/**
 * autorun 测量窗常亮策略（T25，D-427）。
 *
 * 背景：radio_ctx 覆盖率一度只有 2/9（D-424）。T23/T24 判别三个候选根因——
 * 采样协程死亡（413 行 1Hz 全程无缺口，实测排除）、普通 `screen_off_timeout`
 * 超时（配置 600s vs 实际 18–50s 息屏，数量级不成立，实测排除）、`stayon` 时序
 * 竞态（源码核实 stayon 在息屏前至少 29–31 秒已生效，实测排除）——剩 EMUI 自有
 * 息屏机制最可能（间接推断）：息屏后系统对 cell info 更新节流，采集器如实把样本
 * 降级为 stale（D-426）。三个已排除假说都不是"调对参数"能解的，因为它们本就
 * 不是根因；剩下的路子是应用层直接持有屏幕，不依赖系统级 `stayon` 是否被 EMUI
 * 覆盖——即本策略要落的 `FLAG_KEEP_SCREEN_ON`（窗口 flag：Activity 可见期自动
 * 生效、窗口销毁自动失效，见 `MainActivity.onCreate`/`onDestroy` 的实际调用点）。
 *
 * 这同时是口径正确性修复，不只是"让数据不缺"：**既有试点/取证语料是操作者
 * 在场、屏幕常亮状态下采集的**（订正，T36：此前这里写"试点 LTE 语料"，但
 * `pilot_labelled.jsonl`（"试点"，n=11）经 T34/D-441 独立核实实为
 * NR@106.86.109.60，不是 LTE——RAT 标签错了，"操作者在场屏亮"这一采集条件
 * 本身不受影响，是本段论证真正依赖的前提）；NR run 前 44 秒同为屏亮态。保持
 * autorun 窗口全程常亮，才能让未来批次与既有语料处于同一屏态，彼此可比——
 * 否则跨批次判读里，屏态差异会混进其它变量（制式、时段等），无法区分。
 *
 * 范围边界（additive，只动 autorun 路径）：手动模式下 `autorun=false`，
 * `onCreate(false)` 后 [held] 恒为 `false`，窗口 flag 从不被设置——手动模式
 * 由人持续操作屏幕，本就不会被系统判定为空闲息屏，不需要也不应该被这条策略
 * 影响，故 `MainActivity` 里驱动手动 run 的 `startRun(fromAutorun = false)`
 * 路径完全不读取本类。
 *
 * 只做纯逻辑、不碰 `Window`/`Activity`：本仓 `app/probe` 只有 JVM JUnit
 * （`testImplementation(libs.junit)`），无 Robolectric/instrumented test，
 * 真正调用 `window.addFlags`/`clearFlags` 的一线代码无法用单测覆盖，只能靠
 * 真机验证。本类把"该不该持有"这个可判定的决策从 Activity 生命周期里抽出来，
 * 让这部分逻辑不依赖真机也能钉住（[KeepScreenOnPolicyTest]）。
 *
 * **真机验证已落账（T30，D-437，2026-08-03）**：15/15 个清洁 NR_SA run、
 * 135 个场景，radio 覆盖率 **135/135（100%）**、15/15 run 零 stale——
 * 2.6 小时连续窗口零复现此前的息屏归零现象（对照 D-424 的原始缺口 2/9），
 * 本注释开头的口径正确性理由（保屏使 NR/LTE 批次同态可比）现在有实测背书。
 */
internal class KeepScreenOnPolicy {

    /** 当前是否应持有屏幕常亮标志；仅供 [MainActivity] 读取以决定是否调用 window flag。 */
    var held: Boolean = false
        private set

    /** onCreate 阶段调用：autorun 才持有；手动模式（`autorun=false`）不持有。 */
    fun onCreate(autorun: Boolean) {
        held = autorun
    }

    /** onDestroy 阶段调用：无条件释放。未持有时是安全的空操作，不会误清手动模式的窗口态。 */
    fun onDestroy() {
        held = false
    }
}
