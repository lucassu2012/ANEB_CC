package com.aneb.probe.net

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 两份 `network_security_config.xml`（`src/main` 与 `src/debug`）的 E-01 段对拍守卫（T58b/D-500③）。
 *
 * **为什么需要这个守卫**：Android 的 NSC 是**整份资源覆盖、不是合并**——debug 变体存在同名文件时，
 * `src/main` 的那份对 debug 构建**完全失效**。因此 main 版里的 E-01 bare-IP 信任锚必须在 debug 版里
 * **重复一份**，否则 debug 构建（＝当前全部真机测量在用的变体）会丢掉 `aneb_ip_ca` 锚、连不上
 * SNI-RST 旁路通道（R-33/D-22/D-25），而**症状是运行期连接失败、编译期毫无提示**。
 *
 * 落地时这条约束只靠两份文件头的注释互相点名——这正是 D-315「共享实现要数副本」的形状：
 * 没有依赖边把两者牵在一起，改一处不会有任何东西提醒你改另一处。本测试就是那个提醒。
 *
 * 守什么（三条，均为"改了就红"）：
 *  1. 两份都必须声明 E-01 IP 的 `domain-config`，且**信任锚集合逐字相同**；
 *  2. E-01 段**一律禁明文**（`cleartextTrafficPermitted="false"`）——明文只允许出现在 debug 的模拟器段；
 *  3. `src/main`（release 也用）**不得放行任何明文**。
 */
class NetworkSecurityConfigParityTest {

    private val e01Ip = "120.79.148.0"

    /** 从模块工作目录（app/probe）向上找仓库根相对路径（同 RttDominanceGuardTest 惯例）。 */
    private fun repoFile(relFromRepoRoot: String): java.io.File {
        var cur: java.io.File? = java.io.File(System.getProperty("user.dir") ?: ".").absoluteFile
        while (cur != null) {
            val cand = java.io.File(cur, relFromRepoRoot)
            if (cand.isFile) return cand
            cur = cur.parentFile
        }
        error("找不到 $relFromRepoRoot（从 user.dir 向上未命中）")
    }

    private fun nsc(variant: String): String =
        repoFile("app/probe/src/$variant/res/xml/network_security_config.xml").readText(Charsets.UTF_8)

    /** 抽出包含 E-01 IP 的那个 <domain-config> 整段（去注释、压空白，便于逐字比对）。 */
    private fun e01Block(xml: String, variant: String): String {
        val noComments = xml.replace(Regex("""(?s)<!--.*?-->"""), "")
        // 注意用内联 (?s) 而非 RegexOption.DOT_MATCHES_ALL 参数形式——后者在本处不生效，
        // 曾使本守卫报"找不到 E-01 段"（blocks=0）而文件其实完全正确：**坏的是量法不是被测对象**。
        val blocks = Regex("""(?s)<domain-config.*?</domain-config>""")
            .findAll(noComments).map { it.value }.toList()
        val hit = blocks.filter { it.contains(e01Ip) }
        assertEquals("$variant 应恰有一个包含 $e01Ip 的 domain-config", 1, hit.size)
        return hit.first().replace(Regex("""\s+"""), " ").trim()
    }

    @Test
    fun `both variants declare the E01 anchor block verbatim identical`() {
        val main = e01Block(nsc("main"), "main")
        val debug = e01Block(nsc("debug"), "debug")
        assertEquals(
            "两份 NSC 的 E-01 段必须逐字相同：NSC 是整份覆盖非合并，debug 少了这段" +
                "就会在运行期丢掉 aneb_ip_ca 锚（编译期无提示）。改一处必须改另一处。",
            main, debug,
        )
        // 锚点本身也点名，防止"两边一起被改错"这种同步但错误的状态
        assertTrue("E-01 段必须含 aneb_ip_ca 私有锚", main.contains("@raw/aneb_ip_ca"))
        assertTrue("E-01 段必须保留 system 锚（将来换正规证书不必改配置）", main.contains("src=\"system\""))
    }

    @Test
    fun `E01 block never permits cleartext in either variant`() {
        for (v in listOf("main", "debug")) {
            val block = e01Block(nsc(v), v)
            assertFalse(
                "$v 的 E-01 段不得放行明文（该通道是 https:8443；明文只允许出现在 debug 的模拟器段）",
                block.contains("cleartextTrafficPermitted=\"true\""),
            )
        }
    }

    @Test
    fun `main variant which ships in release permits no cleartext at all`() {
        val mainXml = nsc("main").replace(Regex("""(?s)<!--.*?-->"""), "")
        assertFalse(
            "src/main 的 NSC 会随 release 出厂，不得放行任何明文流量（模拟器明文段只属 debug）",
            mainXml.contains("cleartextTrafficPermitted=\"true\""),
        )
    }
}
