package com.aneb.probe.adapter

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 观察红线的**常设**守卫：`app/probe` 生产源码里不得出现 `performAction` /
 * `performGlobalAction` / `getSource` 的**调用点**（D-49 观察 only、D-57）。
 *
 * **为什么要有这只测试（T83，承 v4 治理债审计 #2）**：这两条红线此前**只活在
 * KDoc 注释里**——[AnebAccessibilityService] 头部自述「本服务绝不调用
 * performAction / performGlobalAction」。而注释拦不住任何东西：**一次编辑加进
 * 一个调用，能过掉本仓所有既有门**（编译过、单测过，`check_redline` 管的是画像
 * 不是这里）。一次性 grep 实证只证明「那一刻是零」，不证明明天还是零。
 *
 * **为什么扫源码而不是断言行为**：这两个 API 的危险不在「调用后返回什么」，而在
 * **调用这件事本身**——`performAction` 会替用户操作 App（红线：观察 only），
 * `getSource` 走跨进程取节点（红线：最小开销路径，且够得到内容）。**一个行为测试
 * 只能证明当前代码路径没走到它，源码扫描才能证明它根本不在**。
 *
 * **判据必须分辨注释与调用**：红线自述那句注释、以及 `AdapterSpec` 里解释
 * 「view_id_regex 为何存而不评估」的两处注释，都**合法地**提到这些 API。
 * 所以本测试先剥掉注释与字符串字面量再扫——**只数出现次数的守卫，会在下一个人
 * 修 KDoc 时误红，而误红的守卫很快就会被人关掉**。
 *
 * 本文件自带反例用例，因为**一只从未红过的守卫，和一只不会红的守卫，在绿灯上
 * 长得一模一样**。
 */
class ObservationRedLineSourceScanTest {

    /**
     * 剥掉 Kotlin 的行注释、块注释与字符串字面量，保留其余字符与换行。
     *
     * 保留换行是为了让命中能报出**行号**——一个只说「有违规」不说在哪的守卫，
     * 会让下一个人自己去 grep，而他 grep 的判据未必和这里一致。
     */
    private fun stripCommentsAndStrings(src: String): String {
        val out = StringBuilder(src.length)
        var i = 0
        var inLine = false
        var inBlock = false
        var inStr = false
        var inChar = false
        while (i < src.length) {
            val c = src[i]
            val next = if (i + 1 < src.length) src[i + 1] else ' '
            when {
                inLine -> {
                    if (c == '\n') {
                        inLine = false
                        out.append(c)
                    }
                    i++
                }
                inBlock -> {
                    if (c == '*' && next == '/') {
                        inBlock = false
                        i += 2
                    } else {
                        if (c == '\n') out.append(c)
                        i++
                    }
                }
                inStr -> {
                    if (c == '\\') {
                        i += 2
                    } else {
                        if (c == '"') inStr = false
                        if (c == '\n') out.append(c)
                        i++
                    }
                }
                inChar -> {
                    if (c == '\\') i += 2 else {
                        if (c == '\'') inChar = false
                        i++
                    }
                }
                c == '/' && next == '/' -> {
                    inLine = true
                    i += 2
                }
                c == '/' && next == '*' -> {
                    inBlock = true
                    i += 2
                }
                c == '"' -> {
                    inStr = true
                    i++
                }
                c == '\'' -> {
                    inChar = true
                    i++
                }
                else -> {
                    out.append(c)
                    i++
                }
            }
        }
        return out.toString()
    }

    /** 在剥净的文本里找禁用 API，回 `"<行号>: <API>"`。 */
    private fun scanForbidden(src: String): List<String> {
        val stripped = stripCommentsAndStrings(src)
        val hits = mutableListOf<String>()
        stripped.split("\n").forEachIndexed { idx, line ->
            for (api in FORBIDDEN) {
                if (line.contains(api)) hits += "${idx + 1}: $api"
            }
        }
        return hits
    }

    /** 定位 `app/probe/src/main/java`——不假设 Gradle 的工作目录，逐级向上找。 */
    private fun mainSourceRoot(): File {
        var dir: File? = File(".").absoluteFile
        while (dir != null) {
            for (rel in arrayOf("src/main/java", "app/probe/src/main/java")) {
                val cand = File(dir, rel)
                if (cand.isDirectory) return cand
            }
            dir = dir.parentFile
        }
        throw AssertionError(
            "找不到 app/probe 的 main 源码目录——**本测试就此 fail-closed**。" +
                "一个扫不到文件的扫描器没有资格说「通过」。" +
                "当前工作目录=${File(".").absoluteFile}",
        )
    }

    @Test
    fun `no production source under app-probe calls performAction or getSource`() {
        val root = mainSourceRoot()
        val files = root.walkTopDown().filter { it.isFile && it.name.endsWith(".kt") }.toList()
        // fail-closed：文件数为 0 说明量法坏了，不是「没有违规」——这两者在绿灯上一样。
        assertTrue(
            "扫到 ${files.size} 个 .kt（< $MIN_FILES_SCANNED）——量法坏了，不是没有违规（root=$root）",
            files.size >= MIN_FILES_SCANNED,
        )
        // 第二层：**有没有让它看该看的东西**。上面那条只保证「扫到了 ≥10 个文件」，
        // 不保证扫的是**这两个**——而红线正是写在它们头上的。少了这条，扫描器指错
        // 目录也会一路绿灯（同「0 假阳性的工具指错对象照样给你一片假绿」）。
        val names = files.map { it.name }.toSet()
        for (must in MUST_SCAN) {
            assertTrue(
                "扫描集里没有 $must——扫描器多半指错了目录（root=$root，共 ${files.size} 个 .kt）",
                must in names,
            )
        }
        val offenders = mutableListOf<String>()
        for (f in files) {
            for (hit in scanForbidden(f.readText())) {
                offenders += "${f.relativeTo(root).path} $hit"
            }
        }
        assertEquals(
            "app/probe 生产源码出现了观察红线禁用的 API 调用点（D-49 观察 only / D-57）。" +
                "注释与字符串已剥除，故这些是**真调用**：\n" + offenders.joinToString("\n"),
            emptyList<String>(),
            offenders,
        )
    }

    @Test
    fun `the scanner catches a real call, not just any mention`() {
        val fixture = """
            package x
            class Y {
                fun z(node: Any) {
                    node.performAction(1)
                }
            }
        """.trimIndent()
        val hits = scanForbidden(fixture)
        assertTrue(
            "塞进夹具的 performAction 调用没被咬住：$hits",
            hits.any { it.endsWith("performAction") },
        )
    }

    @Test
    fun `the kotlin property form event-dot-source is caught too, not just getSource`() {
        // 这条是本守卫最容易漏的形状：Java 的 `getSource()` 在 Kotlin 里写作 `.source`。
        // 只搜 `getSource` 的扫描器对下面这段一无所知——而红线自述的原话恰恰点名了它。
        val fixture = """
            package x
            class Y {
                fun z(event: Any) {
                    val node = event.source
                }
            }
        """.trimIndent()
        val hits = scanForbidden(fixture)
        assertTrue("Kotlin 属性形态 event.source 没被咬住：$hits", hits.any { it.endsWith("event.source") })
    }

    @Test
    fun `a comment or a string that merely names the api is not a violation`() {
        // 这正是红线自述那句注释、以及 AdapterSpec 解释「view_id_regex 存而不评估」
        // 两处注释的形状。它们必须放行，否则下一个人修 KDoc 就会被误红。
        val fixture = """
            package x
            /** 本服务绝不调用 performAction / performGlobalAction，也绝不取 event.source。 */
            class Y {
                // view_id_regex 需 AccessibilityNodeInfo（getSource 跨进程），故存而不评估
                val note = "performAction 只出现在这句字符串里"
            }
        """.trimIndent()
        assertEquals(
            "注释/字符串里的提及被误判成违规了",
            emptyList<String>(),
            scanForbidden(fixture),
        )
    }

    private companion object {
        /**
         * `performGlobalAction` 一并纳入：板面派件写的是「performAction／getSource」，
         * 而 [AnebAccessibilityService] 头部自述的红线原话是「绝不调用 performAction /
         * performGlobalAction」——**以源码自述的那句为准更严，且当前实测同样为零**，
         * 故纳入不会带来假红。
         */
        private val FORBIDDEN = listOf(
            // —— 替用户操作（红线：观察 only）
            "performGlobalAction",
            "performAction",
            // —— 取节点的四条入口。**只禁 `getSource` 是不够的**：Java 的 `getSource()`
            // 在 Kotlin 里按属性访问写作 `event.source`，一条 `val n = event.source`
            // 会完全绕过只搜 `getSource` 的扫描器——而**红线自述那句原话正是「绝不取
            // event.source」**，即文档早就点名了这个形态，是扫描器没跟上。
            // 其余两条是取节点的另外两个标准 API；类型名本身也纳入，因为任何用法都得提它。
            // 四者在当前生产源码里的出现**全部落在注释中**（实测：`event.source` 6、
            // `AccessibilityNodeInfo` 3、另两个各 0），剥注释后为零，故纳入不带来假红。
            "event.source",
            "rootInActiveWindow",
            "findAccessibilityNodeInfos",
            "AccessibilityNodeInfo",
            "getSource",
        )

        /** 当前 `app/probe` 主源集远多于此；这个下限只用来区分「没有违规」与「没扫到」。 */
        private const val MIN_FILES_SCANNED = 10

        /**
         * 必须落在扫描集里的文件——**红线就写在它们头上**，它们不在场就说明扫错了目录。
         * 这是「验自造工具的第二层」：第一层证明它**能抓**，这一层证明它**看了该看的**。
         */
        private val MUST_SCAN = listOf("AnebAccessibilityService.kt", "AdapterSpec.kt")
    }
}
