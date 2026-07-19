package com.aneb.probe.ui

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

/**
 * 客户端 Profile 数据化对拍单测——铁律 1「Profile 即数据」客户端落地的防漂移闸门。
 *
 * 1. assets JSON（运行时镜像）解析出的注册表与代码内硬编码兜底逐字段深度对拍：
 *    JVM 单测无 Context、[TestModeProfiles.initFrom] 不会被调用，故
 *    [TestModeProfiles.ALL] 即 FALLBACK——两份数据（文件权威 vs 代码兜底）一致性由此闭环；
 * 2. assets 镜像与 spec/profiles/client/（权威副本，单一事实源）字节级一致；
 * 3. schema_version 与 profile 顺序钉死；
 * 4. 损坏 JSON / schema 不符必须抛——运行时 fail-safe 回退路径的触发条件。
 */
class ClientProfileDataParityTest {

    private val assetsRel = "app/probe/src/main/assets/spec_profiles/client_profiles.json"
    private val specRel = "spec/profiles/client/client_profiles.json"

    /** 从模块工作目录（app/probe）向上找仓库根相对路径（同 CalibrationFixtureTest 惯例）。 */
    private fun repoFile(relFromRepoRoot: String): File {
        var cur: File? = File(System.getProperty("user.dir") ?: ".").absoluteFile
        while (cur != null) {
            val cand = File(cur, relFromRepoRoot)
            if (cand.isFile) return cand
            cur = cur.parentFile
        }
        error("找不到 $relFromRepoRoot（从 user.dir 向上未命中）")
    }

    private fun parsedFromAssets(): List<TestModeProfile> =
        TestModeProfileLoader.parse(repoFile(assetsRel).readText(Charsets.UTF_8))

    // ---------- 用例 1：assets JSON ↔ 硬编码 FALLBACK 逐字段深度对拍 ----------

    @Test
    fun `assets json deep-equals hardcoded fallback field by field`() {
        val parsed = parsedFromAssets()
        val fallback = TestModeProfiles.ALL // JVM 无 Context → 即代码内 FALLBACK
        assertEquals("profile 数", fallback.size, parsed.size)
        fallback.zip(parsed).forEach { (f, p) ->
            assertEquals("id", f.id, p.id)
            assertEquals("${f.id}.displayName", f.displayName, p.displayName)
            assertEquals("${f.id}.tagline", f.tagline, p.tagline)
            assertEquals("${f.id}.business", f.business, p.business)
            assertEquals("${f.id}.metrics", f.metrics, p.metrics)
            assertEquals("${f.id}.conclusion", f.conclusion, p.conclusion)
            assertEquals("${f.id}.version", f.version, p.version)
            assertEquals("${f.id}.businessType(facet1)", f.businessType, p.businessType)
            assertEquals("${f.id}.metricSpecs.size", f.metricSpecs.size, p.metricSpecs.size)
            f.metricSpecs.zip(p.metricSpecs).forEach { (fm, pm) ->
                assertEquals("${f.id}.metricSpec[${fm.id}](facet2)", fm, pm)
            }
            assertEquals("${f.id}.live(facet3)", f.live, p.live)
            assertEquals("${f.id}.scoring(facet4)", f.scoring, p.scoring)
            assertEquals("${f.id} 整体（data class 深度相等兜底）", f, p)
        }
        assertEquals("注册表整体", fallback, parsed)
    }

    // ---------- 用例 2：assets 镜像 ↔ spec 权威副本 字节级一致 ----------

    @Test
    fun `assets mirror and spec authoritative copy are byte identical`() {
        assertArrayEquals(
            "spec/profiles/client/ 为单一事实源，assets 为运行时镜像——两份必须字节级一致",
            repoFile(specRel).readBytes(),
            repoFile(assetsRel).readBytes(),
        )
    }

    // ---------- 用例 3：schema 版本与 profile 顺序钉死 ----------

    @Test
    fun `schema version and profile order pinned`() {
        val text = repoFile(assetsRel).readText(Charsets.UTF_8)
        assertTrue(
            "顶层 schema_version 必须为 ${TestModeProfileLoader.SCHEMA_VERSION}",
            text.contains("\"schema_version\": \"${TestModeProfileLoader.SCHEMA_VERSION}\""),
        )
        val ids = parsedFromAssets().map { it.id }
        assertEquals(listOf("token_experience", "basic_network", "voice_realtime"), ids)
        assertEquals("顺序与 FALLBACK/ALL 一致（分段开关顺序）", TestModeProfiles.ALL.map { it.id }, ids)
    }

    // ---------- 用例 4：损坏数据必须抛（触发运行时 fail-safe 回退） ----------

    @Test
    fun `corrupt json or schema mismatch throws so runtime falls back to hardcoded`() {
        try {
            TestModeProfileLoader.parse("{ not json ")
            fail("损坏 JSON 应抛异常（loadFromAssets 捕获后回退 FALLBACK）")
        } catch (expected: Exception) {
            // fail-safe 路径成立
        }
        try {
            TestModeProfileLoader.parse("""{"schema_version":"9.9.9","profiles":[]}""")
            fail("schema_version 不符应抛异常")
        } catch (expected: Exception) {
            // 版本闸门成立
        }
        // 正确 schema_version + 空 profiles → 触达 `require(profiles.isNotEmpty())`（上例用错版本会
        // 提前在 schema 闸门抛出，empty 分支从未被覆盖——此处补齐）。
        try {
            TestModeProfileLoader.parse("""{"schema_version":"${TestModeProfileLoader.SCHEMA_VERSION}","profiles":[]}""")
            fail("profiles 为空应抛异常（loadFromAssets 捕获后回退 FALLBACK）")
        } catch (expected: Exception) {
            // profiles 非空闸门成立
        }
    }
}
