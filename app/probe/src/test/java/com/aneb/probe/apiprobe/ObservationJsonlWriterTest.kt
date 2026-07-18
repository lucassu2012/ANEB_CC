package com.aneb.probe.apiprobe

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files

/**
 * ObservationJsonlWriter 锚定（纯 JVM，临时目录）：每行一条 / 累积 / 多行拒绝 / 空拒绝 /
 * 按 size 轮换 / providerId 文件名安全化。
 */
class ObservationJsonlWriterTest {

    private lateinit var dir: File

    @Before
    fun setup() {
        dir = Files.createTempDirectory("obs_test").toFile()
    }

    @After
    fun teardown() {
        dir.deleteRecursively()
    }

    @Test
    fun `append writes one line per observation`() {
        val w = ObservationJsonlWriter(dir)
        w.append("{\"a\":1}", "glm")
        w.append("{\"a\":2}", "glm")
        val f = File(dir, "aneb_token_obs_glm_00.jsonl")
        assertTrue(f.exists())
        assertEquals(listOf("{\"a\":1}", "{\"a\":2}"), f.readLines())
    }

    @Test
    fun `rejects multiline observation`() {
        try {
            ObservationJsonlWriter(dir).append("{\"a\":1}\n{\"a\":2}", "glm")
            fail("expected IllegalArgumentException")
        } catch (e: IllegalArgumentException) {
            // ok
        }
    }

    @Test
    fun `rejects blank observation`() {
        try {
            ObservationJsonlWriter(dir).append("   ", "glm")
            fail("expected IllegalArgumentException")
        } catch (e: IllegalArgumentException) {
            // ok
        }
    }

    @Test
    fun `rotates to next shard when file exceeds max bytes`() {
        val w = ObservationJsonlWriter(dir, maxFileBytes = 10)
        w.append("0123456789", "glm") // 10 + newline = 11 bytes >= 10 → 下条轮换
        w.append("next", "glm")
        assertTrue(File(dir, "aneb_token_obs_glm_00.jsonl").exists())
        val shard1 = File(dir, "aneb_token_obs_glm_01.jsonl")
        assertTrue(shard1.exists())
        assertEquals(listOf("next"), shard1.readLines())
    }

    @Test
    fun `sanitizes provider id in filename`() {
        ObservationJsonlWriter(dir).append("{}", "glm/../x y")
        // '/', '.', ' ' 被剔除，仅留 [A-Za-z0-9_-]
        assertTrue(File(dir, "aneb_token_obs_glmxy_00.jsonl").exists())
    }
}
