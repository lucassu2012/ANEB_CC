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
}
