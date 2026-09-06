package com.aneb.probe.net

import kotlinx.serialization.json.Json

/**
 * 上行响应的**服务端视角解析**与**字节取值**（A-8／C-3，承 REVIEW §7.1 S3-01）。
 *
 * **为什么抽出来**：这两个判断此前**内联在 [AnebClient] 的三个 `executeCancellable` 块里**，
 * 而那些块要跑起来需要一条真实 HTTP 请求 —— 于是**它们一行都没被单测覆盖过**。
 * 本仓已被同一形状咬过两次：一次是「三条测试围着一条从没被执行的代码路径打转而全绿」；
 * 一次是我自己报出来的 **M2 SURVIVED** —— 夹具直接构造 `WindowTransferResult`，
 * **绕开了 `uploadWindow` 自己的取值逻辑**，于是那条测试是回归钉、不是守卫。
 * 抽成纯函数后，边界条件不必起网络就能逐个钉住。
 *
 * ⚠ **这里没有 MockWebServer 也能测的原因**：解析与取值都不需要 socket；
 * 需要 socket 的是「请求真的发出去了吗」—— 那是另一个问题，留给 C-3 待批的那几件。
 */
object UploadResponseView {

    /**
     * 从响应体解出服务端视角；**非 2xx、体缺失、坏 JSON 一律 null**（R-10：不出值，不造值）。
     *
     * @param json 调用方的解析器（`AnebClient` 用的是 `ignoreUnknownKeys = true`）——
     *   作为入参而非在此自建，是为了让**被测的解析器就是线上那一个**：
     *   自建一个宽松度不同的实例，测出来的宽容度就不是生产的宽容度。
     */
    fun parse(
        json: Json,
        isSuccessful: Boolean,
        bodyText: String?,
    ): AnebClient.UploadServerView? {
        if (!isSuccessful || bodyText == null) return null
        return try {
            json.decodeFromString(AnebClient.UploadServerView.serializer(), bodyText)
        } catch (e: Exception) {
            // 解析失败 ⇒ 无权威计数，退化为 null（R-10）。
            // 时长会在 ScenarioKpi.adaptiveWindow 被一并置 null，故不会被拿去算速率。
            null
        }
    }

    /**
     * 上行窗口的传输字节数：**服务端权威计数优先，缺席时退回客户端写出量**。
     *
     * 两者不是同一个量：`write` 返回只意味着字节进了本地 socket 缓冲，
     * **离开设备与被服务端读完都还没发生** —— 拿它算上行速率，等于把本地缓冲的吞吐算进网络。
     *
     * 🔴 **`bytes >= 0` 这个判据是全函数最容易写坏的一处**：
     * [AnebClient.UploadServerView.bytes] 的**默认值是 -1**，所以一个**解析成功**的视角
     * 仍可能带着 -1，那表示「服务端没报这个数」。而 **0 是合法值**（服务端确实一个字节都没读到，
     * 例如窗口在首块写出前就到点）。把判据写成 `> 0`，会在**服务端真收到 0 字节**时
     * 静默改用客户端计数 —— 那是一个**看起来完全正常的错数**，
     * 且恰好落在「网络其实没通」那一类样本上。
     *
     * @param serverView null ＝ 非 2xx／体缺失／坏 JSON（见 [parse]）
     * @param clientWrittenBytes 客户端写出量，仅在服务端计数缺席时兜底
     */
    fun bytesTransferred(
        serverView: AnebClient.UploadServerView?,
        clientWrittenBytes: Long,
    ): Long = serverView?.bytes?.takeIf { it >= 0 } ?: clientWrittenBytes
}
