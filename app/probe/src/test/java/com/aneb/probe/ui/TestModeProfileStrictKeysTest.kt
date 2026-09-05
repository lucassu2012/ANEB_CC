package com.aneb.probe.ui

import java.io.File
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * `TestModeProfileLoader` 的**严格解析**反例测试（T84，承 v3 §9.2 #5 的 `:probe` 那一半）。
 *
 * **为什么要有它**：loader 的 KDoc 写着「[Json] 用严格模式（**未知键即失败**），防 schema
 * 漂移静默生效」，实现处也写着「默认严格：未知键/类型不符即抛 → 触发 fail-safe 回退」——
 * **但这个承诺此前只活在注释里**。`Json` 的严格是 kotlinx 的**默认值**，一次
 * `Json { ignoreUnknownKeys = true }` 的编辑就能把它关掉，而**编译过、既有单测也全过**：
 * `ClientProfileDataParityTest` 用例 4 只覆盖了**坏 JSON / schema 不符 / profiles 为空**三种，
 * 独独没有未知键。**注释拦不住任何东西**（同 T83 的形状）。
 *
 * **为什么这条值钱**：未知键被静默忽略 ＝ **schema 漂移不再触发 fail-safe 回退**——
 * 数据文件长出一个新字段时，App 会**当作正常数据继续跑**，而不是退回代码内兜底。
 * 那正是「静默生效」四个字要防的事。
 *
 * ## 本测试如何排除「夹具坏了」这个混淆
 * 只断言「注入未知键后 `parse` 抛异常」是不够的——**我把 JSON 改坏了也会抛**，
 * 两者在红绿灯上一模一样（本仓反复付学费的那种错）。故每条反例都配一条**控制**：
 * 用**宽松解析器**（`ignoreUnknownKeys = true`）把同一段文本再解一遍，**必须成功**
 * ⇒ 证明文本仍是合法 JSON、且**唯一的差别就是那个未知键**。
 */
class TestModeProfileStrictKeysTest {

    /** 从模块工作目录（app/probe）向上找仓库根相对路径（同 [ClientProfileDataParityTest] 惯例）。 */
    private fun repoFile(relFromRepoRoot: String): File {
        var cur: File? = File(System.getProperty("user.dir") ?: ".").absoluteFile
        while (cur != null) {
            val cand = File(cur, relFromRepoRoot)
            if (cand.isFile) return cand
            cur = cur.parentFile
        }
        error("找不到 $relFromRepoRoot（从 user.dir 向上未命中）")
    }

    private fun realJson(): String = repoFile(ASSETS_REL).readText(Charsets.UTF_8)

    /** 宽松解析器——只用来证明「文本仍是合法 JSON」，不参与被测行为。 */
    private val lenient = Json { ignoreUnknownKeys = true }

    private fun assertStillValidJson(text: String, where: String) {
        // 若这一步抛，说明是**我的注入把 JSON 弄坏了**，而不是 loader 在拒未知键。
        lenient.parseToJsonElement(text)
        assertTrue("$where：注入后文本已不是合法 JSON——夹具坏了，本条反例不成立", true)
    }

    private fun assertParseRejects(text: String, where: String) {
        val threw = try {
            TestModeProfileLoader.parse(text)
            false
        } catch (e: Exception) {
            true
        }
        assertTrue(
            "$where：`parse` 没有拒绝未知键——严格模式被关掉了（多半是 " +
                "`Json { ignoreUnknownKeys = true }`），schema 漂移将静默生效、不再触发 fail-safe 回退",
            threw,
        )
    }

    @Test
    fun `the real data file parses — so any failure below is caused by the injected key`() {
        // 控制组：不先证明「原文能过」，下面的「抛了」就说明不了任何事。
        val profiles = TestModeProfileLoader.parse(realJson())
        assertTrue("真实数据文件解析出的 profiles 不应为空", profiles.isNotEmpty())
    }

    @Test
    fun `an unknown key at the top level is rejected`() {
        val text = realJson()
        val at = text.indexOf('{')
        assertTrue("真实数据文件不是以 { 开头，注入点假设不成立", at >= 0)
        val mutated = text.substring(0, at + 1) + "\"$UNKNOWN_KEY\": 1," + text.substring(at + 1)
        assertStillValidJson(mutated, "顶层")
        assertParseRejects(mutated, "顶层")
    }

    @Test
    fun `an unknown key nested inside a profile is rejected too`() {
        // 顶层严格不蕴含嵌套严格——这是**另一条**性质，值得单独钉。
        val text = realJson()
        val marker = "\"profiles\""
        val pi = text.indexOf(marker)
        assertTrue("真实数据文件里找不到 \"profiles\"，注入点假设不成立", pi >= 0)
        val objStart = text.indexOf('{', text.indexOf('[', pi))
        assertTrue("找不到 profiles 数组里的第一个对象，注入点假设不成立", objStart >= 0)
        val mutated = text.substring(0, objStart + 1) +
            "\"$UNKNOWN_KEY\": 1," + text.substring(objStart + 1)
        assertStillValidJson(mutated, "profiles[0] 内")
        assertParseRejects(mutated, "profiles[0] 内")
    }

    @Test
    fun `the guard is proven to bite — the same text passes once strictness is off`() {
        // 这条把「本测试到底在测什么」钉死：**同一段文本、同一个 DTO，唯一的差别是
        // `ignoreUnknownKeys` 这一个开关**。严格侧拒 + 宽松侧过 ⇒ 上面两条反例测的
        // 确实是「严格性」本身；而**一旦有人把严格关掉，它们就会变绿**——即它们守的
        // 正是这个开关。宽松解析器只在本测试内构造，**不改一行生产代码**。
        val text = realJson()
        val at = text.indexOf('{')
        val mutated = text.substring(0, at + 1) + "\"$UNKNOWN_KEY\": 1," + text.substring(at + 1)

        assertParseRejects(mutated, "咬合证明·严格侧")

        val decoded =
            lenient.decodeFromString<TestModeProfileLoader.ClientProfilesFileDto>(mutated)
        assertTrue(
            "宽松解析器也没解出 profiles——说明这段文本还有别的毛病，" +
                "上面两条反例的「抛」就不能归因于未知键",
            decoded.profiles.isNotEmpty(),
        )
    }

    private companion object {
        private const val ASSETS_REL =
            "app/probe/src/main/assets/spec_profiles/client_profiles.json"

        /**
         * 注入用的键名。刻意取一个**不可能与真实 schema 撞车**的名字——
         * 若哪天它真进了 schema，本测试会变成假绿，而那种失效是静默的。
         */
        private const val UNKNOWN_KEY = "aneb_t84_unknown_probe_key"
    }
}
