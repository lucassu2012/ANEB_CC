package com.aneb.probe.apiprobe

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/**
 * finding #2（D-64）锚定：ApiProbe 请求体与 observation 的 `workload_kind` **同源**。
 *
 * [ApiProbe.run] 用单一 `workload` 既构造请求体（[ApiProbe.requestBodyJson]）又标注
 * observation，二者由构造即不可能分叉。本测试守住这条同源保证的机制点——
 * requestBodyJson 只为 TEXT 构造真实请求体；多模态（image/document/video）无端点规格，
 * **绝不投机用 text 冒充其标注** → 显式抛错。故探针永不可能"body=text 却标 image"
 * （旧 `ObservationSink.workloadKind` 独立字段的分叉隐患，已移除）。
 */
class ApiProbeWorkloadTest {

    @Test
    fun `text workload builds the fixed short-prompt body for every provider`() {
        for (p in LlmProvider.entries) {
            val body = ApiProbe.requestBodyJson(p, p.defaultModel, TokenObservationExport.WorkloadKind.TEXT)
            assertTrue(body, body.contains("\"max_tokens\":${ApiProbe.MAX_TOKENS}"))
            assertTrue(body, body.contains("\"stream\":true"))
        }
    }

    @Test
    fun `workload defaults to text so existing two-arg callers are unchanged`() {
        for (p in LlmProvider.entries) {
            assertEquals(
                ApiProbe.requestBodyJson(p, p.defaultModel),
                ApiProbe.requestBodyJson(p, p.defaultModel, TokenObservationExport.WorkloadKind.TEXT),
            )
        }
    }

    @Test
    fun `non-text workloads are rejected until a real multimodal body exists`() {
        val nonText = listOf(
            TokenObservationExport.WorkloadKind.DOCUMENT,
            TokenObservationExport.WorkloadKind.IMAGE,
            TokenObservationExport.WorkloadKind.VIDEO,
        )
        for (p in LlmProvider.entries) {
            for (w in nonText) {
                try {
                    ApiProbe.requestBodyJson(p, p.defaultModel, w)
                    fail("expected IllegalArgumentException for workload=${w.id} provider=${p.id}")
                } catch (e: IllegalArgumentException) {
                    // 抛错信息带上 workload id，便于诊断误配
                    assertTrue(e.message ?: "", (e.message ?: "").contains(w.id))
                }
            }
        }
    }
}
