package com.aneb.probe.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * autorun extras 的「只在 onCreate 解析」契约守卫（D-513 过程事实①）。
 *
 * **守什么**：`MainActivity` 的全部 autorun extras 只在 `onCreate` 解析一次；App 已在前台时
 * 重复 `am start --es ...` 走 `onNewIntent`，**新 extras 被静默忽略**——不崩溃、不报错、数据
 * 照出，批脚本却以为换了参数（D-513 实测：改逐轮 `force-stop` 冷启后 18/18 才对）。
 *
 * 这条守卫**不主张"应该修成动态重解析"**（那是改 autorun 编排语义，须走决策），它只保证：
 *  1. `onNewIntent` 的告警**存在且带 KEY**，静默失败始终可见；
 *  2. **extras 名字的集合被钉住** —— 将来有人新增一个 extra，本测试会红，逼他读到这个陷阱
 *     并决定"要不要也在 onNewIntent 里提示"，而不是无声地多一个会被忽略的参数。
 *
 * 量法说明：读源码文本而非反射，因为 `onCreate` 是 Android 生命周期方法，JVM 单测无法真正
 * 驱动；此处要钉的也正是**源码里写了哪些 extras**这件事本身。
 */
class AutorunExtrasContractTest {

    private fun repoFile(rel: String): File {
        var cur: File? = File(System.getProperty("user.dir") ?: ".").absoluteFile
        while (cur != null) {
            val cand = File(cur, rel)
            if (cand.isFile) return cand
            cur = cur.parentFile
        }
        error("找不到 $rel（从 user.dir 向上未命中）")
    }

    private val source: String by lazy {
        repoFile("app/probe/src/main/java/com/aneb/probe/ui/MainActivity.kt").readText(Charsets.UTF_8)
    }

    /** 源码里所有 `getXxxExtra("name")` 的 name 集合。 */
    private fun declaredExtras(): Set<String> =
        Regex("""get\w*Extra\(\s*"([^"]+)"""").findAll(source).map { it.groupValues[1] }.toSet()

    @Test
    fun `onNewIntent warns with a KEY log so ignored extras never stay silent`() {
        assertTrue(
            "MainActivity 必须有 onNewIntent —— 否则重复 am start 的 extras 被忽略这件事完全不可见",
            source.contains("override fun onNewIntent"),
        )
        assertTrue(
            "onNewIntent 必须打 AUTORUN_EXTRAS_IGNORED（KEY 日志，logcat 自动化据此发现参数没生效）",
            source.contains("AUTORUN_EXTRAS_IGNORED"),
        )
    }

    @Test
    fun `the set of autorun extras is pinned so a new one cannot be added unnoticed`() {
        // 钉住当前全集。**新增 extra 会让本测试红**——那是有意的：加参数的人必须先读到
        // 「extras 只在 onCreate 解析、重复 am start 会被忽略」这个陷阱，再决定怎么办。
        val expected = setOf(
            // run 编排
            "server", "autorun", "mode", "transport", "drive_test",
            // continuity / ab
            "c_tokens", "c3_idle", "ab_pairs", "ab_netlog",
            // debug-only 注入
            "inject", "weaknet",
            // API 探针 autorun
            "apiprobe_autorun", "apiprobe_server", "apiprobe_key",
            "apiprobe_provider", "apiprobe_model",
        )
        val actual = declaredExtras()
        assertEquals(
            "autorun extras 集合变了。新增/删除 extra 时请先读 onNewIntent 的 KDoc（D-513 陷阱：" +
                "extras 只在 onCreate 解析，App 已在前台时重复 am start 会静默忽略新值），" +
                "确认新参数在批脚本里怎么用，再更新本清单。",
            expected, actual,
        )
    }
}
