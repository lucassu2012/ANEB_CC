package com.aneb.probe.adapter

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

/**
 * 适配器规格数据文件对拍单测——铁律 1「适配器规格=数据文件」的防漂移闸门
 * （模式同 ClientProfileDataParityTest）。
 *
 * 1. assets 运行时镜像可被严格解析，关键身份字段（id/package/status）钉死；
 * 2. assets 镜像与 spec/adapters/（权威副本）字节级一致；
 * 3. 严格模式拒未知键 / schema 版本闸门 / 必填 kpi_mapping 键——运行时 fail-safe
 *    （ADAPTER_SPEC_FALLBACK → 空列表 → generic mode）的触发条件；
 * 4. 口径红线双声明的数据侧存在性（PENDING-VALIDATION / LOW/INCONCLUSIVE / 非网络口径）。
 */
class AdapterSpecTest {

    private val assetsDir = "app/probe/src/main/assets/spec_adapters"
    private val specDir = "spec/adapters"

    /** 从模块工作目录（app/probe）向上找仓库根相对路径（同 ClientProfileDataParityTest 惯例）。 */
    private fun repoFile(relFromRepoRoot: String): File {
        var cur: File? = File(System.getProperty("user.dir") ?: ".").absoluteFile
        while (cur != null) {
            val cand = File(cur, relFromRepoRoot)
            if (cand.isFile) return cand
            cur = cur.parentFile
        }
        error("找不到 $relFromRepoRoot（从 user.dir 向上未命中）")
    }

    private fun parseAsset(name: String): AdapterSpec =
        AdapterSpecLoader.parse(repoFile("$assetsDir/$name").readText(Charsets.UTF_8))

    /** 最小合法规格 JSON（负向用例底座；[extra] 注入到 adapter 对象内）。 */
    private fun specJson(
        schema: String = AdapterSpecLoader.SCHEMA_VERSION,
        pkg: String = "com.example.app",
        kpiKeys: String = """
            "first_delta": {"proxy_for": "x", "caliber": "y"},
            "delta_cadence": {"proxy_for": "x", "caliber": "y"}
        """.trimIndent(),
        extra: String = "",
    ): String = """
        {
          "schema_version": "$schema",
          "adapter": {
            "id": "t",
            "display_name": "T",
            "app_id": "t-app",
            "package": "$pkg",
            "status": "PENDING-VALIDATION",
            "input_node": {},
            "response_node": {},
            "observe_events": ["TYPE_WINDOW_CONTENT_CHANGED"],
            "kpi_mapping": { $kpiKeys },
            "caliber_redlines": {
              "claim_scope": "c", "confidence_ceiling": "LOW/INCONCLUSIVE", "r10": "r"
            }$extra
          }
        }
    """.trimIndent()

    // ---------- 用例 1：豆包规格解析 + 身份字段钉死（D-48 首批） ----------

    @Test
    fun `doubao asset parses with pinned identity`() {
        val s = parseAsset("doubao.json")
        assertEquals("doubao", s.id)
        assertEquals("com.larus.nova", s.packageName)
        // 2026-07-18 P40 装机实测后：包名/节点均已核实（D-50），状态不再 PENDING
        assertEquals("VALIDATED-OBSERVED", s.status)
        assertTrue("装机核实后 pendingValidation 撤销", !s.pendingValidation)
        assertEquals(
            listOf("TYPE_WINDOW_CONTENT_CHANGED", "TYPE_VIEW_TEXT_CHANGED"),
            s.observeEvents,
        )
        assertTrue("[KNOWN] 装机核实标注必须在", s.packageNote.contains("[KNOWN]"))
        // 节点规则已实测回填（uiautomator dump 锚定，D-50）
        assertEquals("com\\.larus\\.nova:id/message_list", s.responseNode.viewIdRegex)
        assertEquals("VALIDATED-PARTIAL", s.responseNode.status)
        assertEquals("com\\.larus\\.nova:id/input", s.inputNode.viewIdRegex)
    }

    // ---------- 用例 2：DeepSeek 规格解析 + 身份字段钉死（D-48 首批） ----------

    @Test
    fun `deepseek asset parses with pinned identity`() {
        val s = parseAsset("deepseek.json")
        assertEquals("deepseek", s.id)
        assertEquals("com.deepseek.chat", s.packageName)
        // 2026-07-18 P40 装机实测后：包名核实、Compose UI 通配输入规则（D-51）
        assertEquals("VALIDATED-OBSERVED", s.status)
        assertTrue("装机核实后 pendingValidation 撤销", !s.pendingValidation)
        assertEquals(".*", s.inputNode.classNameRegex)
        assertEquals(setOf("first_delta", "delta_cadence"), s.kpiMapping.keys)
    }

    // ---------- 用例 3：assets 镜像 ↔ spec 权威副本 字节级一致（两文件） ----------

    @Test
    fun `assets mirror and spec authoritative copies are byte identical`() {
        for (name in listOf("doubao.json", "deepseek.json")) {
            assertArrayEquals(
                "spec/adapters/$name 为单一事实源，assets 为运行时镜像——两份必须字节级一致",
                repoFile("$specDir/$name").readBytes(),
                repoFile("$assetsDir/$name").readBytes(),
            )
        }
    }

    // ---------- 用例 4：严格模式拒未知键（防 schema 漂移静默生效） ----------

    @Test
    fun `strict mode rejects unknown keys`() {
        AdapterSpecLoader.parse(specJson()) // 底座本身必须合法
        try {
            AdapterSpecLoader.parse(specJson(extra = """, "unknown_key": 1"""))
            fail("未知键应抛异常（运行时 ADAPTER_SPEC_FALLBACK → 空列表 → generic mode）")
        } catch (expected: Exception) {
            // 严格模式闸门成立
        }
    }

    // ---------- 用例 5：schema 版本闸门 + 必填校验 ----------

    @Test
    fun `schema version mismatch or invalid fields throw`() {
        try {
            AdapterSpecLoader.parse(specJson(schema = "9.9.9"))
            fail("schema_version 不符应抛异常")
        } catch (expected: Exception) {
        }
        try {
            AdapterSpecLoader.parse(specJson(pkg = ""))
            fail("package 为空应抛异常")
        } catch (expected: Exception) {
        }
        try {
            AdapterSpecLoader.parse(
                specJson(kpiKeys = """"first_delta": {"proxy_for": "x", "caliber": "y"}"""),
            )
            fail("kpi_mapping 缺 delta_cadence 应抛异常")
        } catch (expected: Exception) {
        }
    }

    // ---------- 用例 6：口径红线双声明的数据侧（KDoc 之外，spec 文件也必须声明） ----------

    @Test
    fun `caliber redlines declared in both spec files`() {
        for (name in listOf("doubao.json", "deepseek.json")) {
            val s = parseAsset(name)
            assertTrue("$name claim_scope 须声明非网络口径", s.caliber.claimScope.contains("网络口径"))
            assertTrue(
                "$name claim_scope 须声明与 Profile 2 严格分标",
                s.caliber.claimScope.contains("Profile 2"),
            )
            assertTrue(
                "$name confidence_ceiling 须声明 LOW/INCONCLUSIVE 恒定",
                s.caliber.confidenceCeiling.contains("LOW/INCONCLUSIVE"),
            )
            assertTrue("$name r10 须声明 null 不折 0", s.caliber.r10.contains("null"))
            // kpi_mapping 每条都带 caliber 声明
            s.kpiMapping.values.forEach { assertTrue(it.caliber.isNotBlank()) }
        }
    }
}
