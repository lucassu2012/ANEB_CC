package com.aneb.probe.apiprobe

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/**
 * aneb-token-observation-v1 导出器锚定（纯 JVM）：schema 符合性 / HMAC 去标识化 /
 * 白名单（无 prompt/content/key 出口）/ 间隔重建口径 / R-10 缺失跳过。
 */
class TokenObservationExportTest {

    private fun arrival(i: Int, atMs: Long, batch: Boolean = false) =
        LlmTokenArrival(index = i, arrivalNanos = atMs * 1_000_000L, sameReadBatch = batch, textChars = 2)

    private val secret = "dataset-secret-2026Q3".toByteArray()
    private val sgid: String get() = TokenObservationExport.subjectGroupId(secret, "acct-1")

    private val allowedFields = setOf(
        "observation_contract_version", "observation_id", "subject_group_id", "workload_kind",
        "payload_bytes", "processing_delay_ms", "output_token_count", "token_intervals_ms",
        "response_artifact_bytes",
    )

    // ---- subject_group_id (HMAC-SHA256 去标识化) ----

    @Test
    fun `subject_group_id matches contract format`() {
        val id = TokenObservationExport.subjectGroupId(secret, "acct-1")
        assertTrue(id, Regex("^hmac-sha256:[0-9a-f]{64}$").matches(id))
    }

    @Test
    fun `subject_group_id deterministic for same secret and subject`() {
        assertEquals(
            TokenObservationExport.subjectGroupId(secret, "acct-1"),
            TokenObservationExport.subjectGroupId(secret, "acct-1"),
        )
    }

    @Test
    fun `subject_group_id differs by secret and by subject`() {
        val base = TokenObservationExport.subjectGroupId(secret, "acct-1")
        assertNotEquals(base, TokenObservationExport.subjectGroupId("other-secret".toByteArray(), "acct-1"))
        assertNotEquals(base, TokenObservationExport.subjectGroupId(secret, "acct-2"))
    }

    @Test
    fun `empty dataset secret rejected`() {
        try {
            TokenObservationExport.subjectGroupId(ByteArray(0), "acct-1")
            fail("expected IllegalArgumentException")
        } catch (e: IllegalArgumentException) {
            // ok
        }
    }

    // ---- token_intervals_ms 重建口径 ----

    @Test
    fun `intervals exclude sameReadBatch and nonpositive`() {
        // 1000,1020,1020(batch),1020,1060 → 20(ok) / batch skip / 0 skip / 40(ok) => [20,40]
        val arrivals = listOf(
            arrival(0, 1000),
            arrival(1, 1020),
            arrival(2, 1020, batch = true),
            arrival(3, 1020),
            arrival(4, 1060),
        )
        assertEquals(listOf(20.0, 40.0), TokenObservationExport.tokenIntervalsMs(arrivals))
    }

    // ---- buildObservation schema 符合性 + 白名单 ----

    @Test
    fun `observation emits only contract fields with correct values`() {
        val json = TokenObservationExport.buildObservation(
            observationId = "obs-001",
            subjectGroupId = sgid,
            workloadKind = TokenObservationExport.WorkloadKind.TEXT,
            payloadBytes = 48,
            processingDelayMs = 3063.0,
            outputTokenCount = 40,
            arrivals = listOf(arrival(0, 1000), arrival(1, 1259), arrival(2, 1515)),
            responseArtifactBytes = 8192L,
        )!!
        val obj = Json.parseToJsonElement(json).jsonObject
        // 白名单：无合同外字段（含无 prompt/content/key 出口）
        assertEquals(emptySet<String>(), obj.keys - allowedFields)
        assertFalse(obj.containsKey("prompt"))
        assertFalse(obj.containsKey("content"))
        assertEquals("aneb-token-observation-v1", obj["observation_contract_version"]!!.jsonPrimitive.content)
        assertEquals("obs-001", obj["observation_id"]!!.jsonPrimitive.content)
        assertEquals("text", obj["workload_kind"]!!.jsonPrimitive.content)
        assertEquals("48", obj["payload_bytes"]!!.jsonPrimitive.content)
        assertEquals("40", obj["output_token_count"]!!.jsonPrimitive.content)
        assertTrue(Regex("^hmac-sha256:[0-9a-f]{64}$").matches(obj["subject_group_id"]!!.jsonPrimitive.content))
        val iv = obj["token_intervals_ms"]!!.jsonArray.map { it.jsonPrimitive.content.toDouble() }
        assertEquals(listOf(259.0, 256.0), iv) // (1259-1000), (1515-1259)
    }

    @Test
    fun `response_artifact_bytes omitted when null`() {
        val json = TokenObservationExport.buildObservation(
            "obs-1", sgid, TokenObservationExport.WorkloadKind.TEXT,
            payloadBytes = 10, processingDelayMs = 100.0, outputTokenCount = 3,
            arrivals = listOf(arrival(0, 0), arrival(1, 50)),
            responseArtifactBytes = null,
        )!!
        assertFalse(Json.parseToJsonElement(json).jsonObject.containsKey("response_artifact_bytes"))
    }

    // ---- R-10 缺失跳过（返回 null，绝不补哨兵） ----

    @Test
    fun `null when no valid intervals`() {
        assertNull(
            TokenObservationExport.buildObservation(
                "obs-1", sgid, TokenObservationExport.WorkloadKind.TEXT,
                10, 100.0, 3, listOf(arrival(0, 0)),
            ),
        )
    }

    @Test
    fun `null when output token count below one`() {
        assertNull(
            TokenObservationExport.buildObservation(
                "obs-1", sgid, TokenObservationExport.WorkloadKind.TEXT,
                10, 100.0, 0, listOf(arrival(0, 0), arrival(1, 50)),
            ),
        )
    }

    @Test
    fun `null when payload bytes below one`() {
        assertNull(
            TokenObservationExport.buildObservation(
                "obs-1", sgid, TokenObservationExport.WorkloadKind.TEXT,
                0, 100.0, 3, listOf(arrival(0, 0), arrival(1, 50)),
            ),
        )
    }

    // ---- 格式非法 = 编程错误（抛，非跳过） ----

    @Test
    fun `illegal observation_id throws`() {
        try {
            TokenObservationExport.buildObservation(
                "x", sgid, TokenObservationExport.WorkloadKind.TEXT,
                10, 100.0, 3, listOf(arrival(0, 0), arrival(1, 50)),
            )
            fail("expected IllegalArgumentException")
        } catch (e: IllegalArgumentException) {
            // ok
        }
    }

    @Test
    fun `illegal subject_group_id throws`() {
        try {
            TokenObservationExport.buildObservation(
                "obs-1", "sha256:notenough", TokenObservationExport.WorkloadKind.TEXT,
                10, 100.0, 3, listOf(arrival(0, 0), arrival(1, 50)),
            )
            fail("expected IllegalArgumentException")
        } catch (e: IllegalArgumentException) {
            // ok
        }
    }

    // ---- JSONL 批 ----

    @Test
    fun `jsonl joins observations by newline`() {
        val a = TokenObservationExport.buildObservation(
            "obs-1", sgid, TokenObservationExport.WorkloadKind.TEXT, 10, 100.0, 3,
            listOf(arrival(0, 0), arrival(1, 50)),
        )!!
        val b = TokenObservationExport.buildObservation(
            "obs-2", sgid, TokenObservationExport.WorkloadKind.TEXT, 10, 100.0, 3,
            listOf(arrival(0, 0), arrival(1, 60)),
        )!!
        val jsonl = TokenObservationExport.buildJsonl(listOf(a, b))
        assertEquals(2, jsonl.split("\n").size)
        assertTrue(jsonl.lines().all { it.contains("aneb-token-observation-v1") })
    }

    // ---- fromProbeOutputs（探针适配层：usage 回退 + TTFT 缺失跳过）+ observationId ----

    @Test
    fun `observationId matches contract format and disambiguates subjects`() {
        val sg1 = TokenObservationExport.subjectGroupId(secret, "acct-1")
        val sg2 = TokenObservationExport.subjectGroupId(secret, "acct-2")
        val id1 = TokenObservationExport.observationId("anthropic", 1_721_318_580_000L, sg1)
        val id2 = TokenObservationExport.observationId("anthropic", 1_721_318_580_000L, sg2)
        assertTrue(id1, Regex("^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$").matches(id1))
        // 同 ms 同 provider、不同 subject → 不同 id（D-64:防 Codex 分区重复 id 拒绝）
        assertNotEquals(id1, id2)
    }

    @Test
    fun `fromProbeOutputs uses server usage output tokens when present`() {
        val json = TokenObservationExport.fromProbeOutputs(
            observationId = "obs-1", subjectGroupId = sgid,
            workloadKind = TokenObservationExport.WorkloadKind.TEXT,
            requestBodyBytes = 48, ttftMs = 3063.0,
            outputTokens = 40, tokenEventCount = 12,
            arrivals = listOf(arrival(0, 1000), arrival(1, 1259), arrival(2, 1515)),
            responseArtifactBytes = 8192L,
        )!!
        val obj = Json.parseToJsonElement(json).jsonObject
        assertEquals("40", obj["output_token_count"]!!.jsonPrimitive.content) // usage 优先于回退
        assertEquals(3063.0, obj["processing_delay_ms"]!!.jsonPrimitive.content.toDouble(), 0.0)
        val iv = obj["token_intervals_ms"]!!.jsonArray.map { it.jsonPrimitive.content.toDouble() }
        assertEquals(listOf(259.0, 256.0), iv)
    }

    @Test
    fun `fromProbeOutputs falls back to token event count when usage missing`() {
        val json = TokenObservationExport.fromProbeOutputs(
            observationId = "obs-1", subjectGroupId = sgid,
            workloadKind = TokenObservationExport.WorkloadKind.TEXT,
            requestBodyBytes = 48, ttftMs = 500.0,
            outputTokens = null, tokenEventCount = 7,
            arrivals = listOf(arrival(0, 1000), arrival(1, 1100)),
        )!!
        val obj = Json.parseToJsonElement(json).jsonObject
        assertEquals("7", obj["output_token_count"]!!.jsonPrimitive.content) // 回退 delta 事件数
    }

    @Test
    fun `fromProbeOutputs null when ttft missing`() {
        assertNull(
            TokenObservationExport.fromProbeOutputs(
                observationId = "obs-1", subjectGroupId = sgid,
                workloadKind = TokenObservationExport.WorkloadKind.TEXT,
                requestBodyBytes = 48, ttftMs = null,
                outputTokens = 40, tokenEventCount = 12,
                arrivals = listOf(arrival(0, 1000), arrival(1, 1259)),
            ),
        )
    }

    @Test
    fun `fromProbeOutputs null when usage missing and event count below one`() {
        assertNull(
            TokenObservationExport.fromProbeOutputs(
                observationId = "obs-1", subjectGroupId = sgid,
                workloadKind = TokenObservationExport.WorkloadKind.TEXT,
                requestBodyBytes = 48, ttftMs = 500.0,
                outputTokens = null, tokenEventCount = 0,
                arrivals = listOf(arrival(0, 1000), arrival(1, 1100)),
            ),
        )
    }
}
