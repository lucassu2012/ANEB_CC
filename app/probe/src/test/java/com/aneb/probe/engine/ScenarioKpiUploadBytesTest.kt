package com.aneb.probe.engine

import com.aneb.probe.net.AnebClient
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * U1 上行字节对账（T73，承 T67/D-514 审计）——与下行 [ScenarioKpiDownloadTest] 对称。
 *
 * **要防的事故**：`server/handlers_upload.go` 的读循环对**任何非 MaxBytes 的读错误**
 * （连接中断、客户端提前关闭）都是 `break` 后**照常回 200 + 已收到的 total**。
 * 而此前 [ScenarioRunner.UploadOutcome.durationNanos] **只查 `error == null`**——
 * 连 2xx 都没查，更没拿服务端实收字节对账。于是一次被中途截断的上传会被报成
 * 「一次成功的、较小的上传」，而 U1 的字节数取 `profileBytes`（profile 声明值，
 * 见 [ScenarioKpi]）而非实收值 —— **吞吐被高估**。
 *
 * 判据本来就在手边：服务端每次都回 `bytes`，客户端也早已解析进
 * [AnebClient.UploadServerView.bytes]，只是从没有人拿它与发送量对账。
 * 下行侧 D-37 早已按 Codex 合同做了同一件事，本组测试把上行补成对称。
 */
class ScenarioKpiUploadBytesTest {

    private val declared = 512L * 1024

    private fun up(
        serverBytes: Long? = declared,
        httpCode: Int? = 200,
        error: String? = null,
        profileBytes: Long = declared,
    ) = ScenarioRunner.UploadOutcome(
        index = 0,
        profileBytes = profileBytes,
        result = AnebClient.UploadResult(
            startNanos = 1_000_000_000L,
            responseNanos = 2_000_000_000L,
            chunkStamps = emptyList(),
            totalBytes = declared.toInt(),
            httpCode = httpCode,
            error = error,
            timing = null,
            serverView = serverBytes?.let {
                AnebClient.UploadServerView(bytes = it, recvStartUs = 1, recvEndUs = 2)
            },
        ),
    )

    @Test fun `实收字节与相位声明一致_判成功样本_时长可用`() {
        assertEquals(1_000_000_000L, up(serverBytes = declared).durationNanos)
    }

    @Test fun `实收字节少于声明_判失败样本_时长null(截断上传不得报成成功)`() {
        // 服务端只收到一半就被 break 出循环、照常回 200——此前这里会给出一个高估的 U1。
        assertNull(up(serverBytes = declared / 2).durationNanos)
    }

    @Test fun `非2xx_判失败样本_时长null(此前连2xx都没查)`() {
        assertNull(up(httpCode = 500).durationNanos)
    }

    @Test fun `传输层错误_判失败样本_时长null(既有行为不变)`() {
        assertNull(up(error = "stream reset").durationNanos)
    }

    @Test fun `serverView缺失时不据此判死_保留既有R10语义`() {
        // 响应体解析失败 → serverView=null 是「慢启动口径退化为 null」的既有语义，
        // 不应连带把 U1 也判死（否则一次 JSON 解析抖动会误杀一个真实成功的上传）。
        assertEquals(1_000_000_000L, up(serverBytes = null).durationNanos)
    }

    @Test fun `profileBytes未声明时跳过字节对账_与下行同口径`() {
        assertEquals(1_000_000_000L, up(serverBytes = 1L, profileBytes = 0L).durationNanos)
    }

    // ------------------------------------------------------------------ U3（窗口上传）
    //
    // **U1 与 U3 是两种上传，A-8 原文把它们混成了一种（D-721 已裁）**：
    // - U1 是一次**完整请求**：服务端回 2xx 就意味着请求体已整体收下，客户端 written 与
    //   服务端字节**由构造相等**；时长锚在响应头，serverView 只是确认、不是依赖。
    //   ⇒ 上面那条「serverView 缺失时不据此判死」是对的，本批不动它。
    // - U3 是**按窗截断**的上传：窗口到点即停写，**留在本地 socket 缓冲里的尾巴服务端
    //   从未读到**。此时 written 必然 ≥ 服务端字节，两者不再由构造相等 ⇒ 字节非要服务端
    //   视角不可，缺了只能记 null（R-10「无事件不造数」）。

    private val profile =
        ScenarioProfile(profileId = "s4_throughput", version = "0.3.0", phases = emptyList())

    /** @param serverBytes null ＝ 2xx 但响应体缺失或坏 JSON（解析不出 serverView） */
    private fun uploadWindow(serverBytes: Long?, written: Long) =
        ScenarioRunner.AdaptiveWindowOutcome(
            windowTargetMs = 4000,
            result = AnebClient.WindowTransferResult(
                startNanos = 1_000_000_000L,
                endNanos = 5_000_000_000L,
                // 传输层在无权威计数时退回 written（AnebClient 既有回退）；
                // 本组要验的正是 **KPI 层不该把这个回退值当成 bytes_transferred 上报**。
                bytesTransferred = serverBytes ?: written,
                httpCode = 200,
                error = null,
                windowUnderrun = false,
                serverView = serverBytes?.let {
                    AnebClient.UploadServerView(bytes = it, recvStartUs = 1, recvEndUs = 2)
                },
                clientWrittenBytes = written,
            ),
            samples = emptyList(),
        )

    private fun u3(serverBytes: Long?, written: Long) =
        ScenarioRunner.ScenarioOutcome(profile, "s4_throughput#0")
            .also { it.uploadWindows.add(uploadWindow(serverBytes, written)) }
            .let { ScenarioKpi.buildKpiInput(it, emptyList()) }
            .adaptiveUpload

    @Test fun `U3取服务端权威计数_written34MB_server30MB_判30MB`() {
        // A-8 的核心事故：拿客户端 written 当上行字节 ⇒ 把窗口关闭时还堵在本地缓冲、
        // 服务端从未读到的那 4 MB 也算成「传过去了」⇒ 吞吐系统性高估约 13%。
        val server = 30L * 1024 * 1024
        val written = 34L * 1024 * 1024
        assertEquals(server, u3(serverBytes = server, written = written)?.bytesTransferred)
    }

    @Test fun `U3在2xx但坏JSON时字节与时长与慢启动全null_不退回written`() {
        val w = u3(serverBytes = null, written = 34L * 1024 * 1024)
        assertNull("无服务端权威计数时不得把 written 当 bytes_transferred 上报", w?.bytesTransferred)
        assertNull("字节不可信 ⇒ 时长置 null，下游才算不出那个偏高的速率", w?.windowActualNanos)
        assertNull("慢启动估计依赖服务端逐块序列，同样只能 null", w?.slowStartUs)
    }
}
