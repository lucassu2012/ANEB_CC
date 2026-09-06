package com.aneb.probe.engine

/**
 * T1（TTFT 网络分量）的纯函数（C-3／REVIEW §7.3）。
 *
 * **为什么要抽出来**：这段计算此前**内联在 [ScenarioRunner] 的 runStream 里**，而那条路径要跑起来
 * 需要一条真实 HTTP 流 —— 于是**它一行都没被单测覆盖过**。本仓已被同一形状咬过：
 * 「三条测试围着一条从没被执行的代码路径打转而全绿」。抽成纯函数后，
 * 边界条件（缺时戳、负 sched）**可以逐个钉住**，不必起网络。
 *
 * **口径**：请求头发完 → 首 token 到达的墙钟差，**减去服务端已知的注入时延**
 * （首 token 的 schedUs 减 prelude 的 srv_ts_us ＝ profile 首 token 的名义 pacing 延迟）。
 * 剥离它，剩下的才是网络分量；不剥离就把服务端**故意的等待**算进了网络。
 */
object TtftAnalysis {

    /**
     * @param arrivalNs 首 token 到达的单调纳秒；null ＝ 这一轮没有 token
     * @param originNs  请求头发完的单调纳秒（timing.requestHeadersEndNs）；null ＝ 计时点缺失
     * @param schedUs   首 token 的服务端计划时刻（微秒）；**负值 ＝ 服务端未给**
     * @param preludeUs prelude 的 srv_ts_us（微秒）；null ＝ prelude 缺失或解析失败
     * @return 毫秒；**任一输入缺失即 null**（R-10／R-20：不出值，不造值）
     *
     * ⚠ **四个入参缺任何一个都必须返回 null，而不是用 0 顶替**：
     * 0 是一个合法的时戳，顶替之后算出来的是一个**看起来完全正常的错数**；
     * 而 null 会被下游如实记成「这一轮没有 T1 样本」。
     */
    fun ttftMs(arrivalNs: Long?, originNs: Long?, schedUs: Long?, preludeUs: Long?): Double? {
        if (arrivalNs == null || originNs == null || schedUs == null || preludeUs == null) return null
        // schedUs < 0 是服务端「本条没给计划时刻」的既有约定（承 ScenarioRunner 原判据
        // `first.schedUs >= 0`），**不是一个可用的小数值** —— 照算会把它当成「计划在原点之前」，
        // 于是多减一个负数、得出偏大的 TTFT，而且不报错。
        if (schedUs < 0) return null
        return (arrivalNs - originNs) / 1e6 - (schedUs - preludeUs) / 1e3
    }
}
