package com.aneb.probe.scoring

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * `run.status` 判定的**跨端一致性**守卫（T76/D-536 自查产物，2026-08-20）。
 *
 * **为什么需要它**：同一个 `status` 字段有**两份独立实现**——设备侧 [ReportAnalyzer.statusHead]/
 * [ReportAnalyzer.isCompleted]（Kotlin）与分析侧 `scripts/campaign_common.py:run_status_head`
 * （Python）。当初 T76 是照着 Python 侧"逐字镜像"写的，但**镜像不是机制**：没有任何东西
 * 阻止将来有人只改一边。这正是 §2.14「同名不同义」防的那类，也是 D-315「共享实现要数副本」
 * 的跨语言版。
 *
 * **实测发现（本守卫的由来）**：核对时确实查出一处分叉——**空串 `""`**：
 *  - Python `run_status_head("")` → `None` → 消费方判「可进中位」放行；
 *  - Kotlin 侧 T76 那行按**原始字段** `runStatus != null` 判，空串非 null → **标为 aborted**。
 * 同一条记录两端读法相反。当前真实语料（`{completed, COMPLETED, aborted:bound_network_lost}`）
 * 没有空串，故零危害——**但那是语料碰巧，不是机制**。分叉已报大脑待裁（统一到「空串＝未知」）。
 *
 * **本守卫只钉两端**「归一化函数」**这一层**（`statusHead` vs `run_status_head`），
 * 不钉消费方判据——后者正是待裁项，裁完再补。
 *
 * 量法：**从 Python 源码里把规则读出来**（split/strip/lower 三步 + 空串处理），而不是在这边
 * 写死一份"我以为 Python 是这样"的复制品——那样只会造出第三份实现。
 */
class StatusJudgementParityTest {

    private fun repoFile(rel: String): File {
        var cur: File? = File(System.getProperty("user.dir") ?: ".").absoluteFile
        while (cur != null) {
            val cand = File(cur, rel)
            if (cand.isFile) return cand
            cur = cur.parentFile
        }
        error("找不到 $rel（从 user.dir 向上未命中）")
    }

    private val pySource: String by lazy {
        repoFile("scripts/campaign_common.py").readText(Charsets.UTF_8)
    }

    /** 抽出 `run_status_head` 的函数体（到下一个顶层 def 为止）。 */
    private fun pyBody(): String {
        val i = pySource.indexOf("def run_status_head")
        assertTrue("scripts/campaign_common.py 里应有 run_status_head（分析侧单一来源）", i >= 0)
        val j = pySource.indexOf("\ndef ", i + 1)
        return if (j > 0) pySource.substring(i, j) else pySource.substring(i)
    }

    @Test
    fun `python side still normalises with the same three steps kotlin does`() {
        val body = pyBody()
        // Kotlin: status?.substringBefore(':')?.trim()?.lowercase()?.takeIf { it.isNotEmpty() }
        assertTrue("Python 侧应仍按 ':' 切主状态（与 Kotlin substringBefore(':') 同）", body.contains("split(\":\""))
        assertTrue("Python 侧应仍 strip（与 Kotlin trim() 同）", body.contains(".strip()"))
        assertTrue("Python 侧应仍折小写（与 Kotlin lowercase() 同）", body.contains(".lower()"))
        assertTrue(
            "Python 侧应仍把空/空白 status 归一为 None（与 Kotlin takeIf{isNotEmpty()} 同语义）",
            body.contains("not st.strip()") || body.contains("strip()") && body.contains("return None"),
        )
    }

    @Test
    fun `kotlin statusHead agrees with the python rule on every real corpus value`() {
        // 真实语料实测取值（T70 全语料 3511 条 + 本轮复核）：只有这三种。
        // 若将来语料出现新取值而两端读法不同，本守卫不会自动发现——故同时钉住"取值集合"
        // 这件事本身：新增取值时请回到本测试补一行，并顺便核对两端。
        val corpusValues = mapOf(
            "completed" to "completed",
            "COMPLETED" to "completed",              // 大小写折叠（T70 修的那处误报）
            "aborted:bound_network_lost" to "aborted", // 去 :reason
        )
        for ((raw, expected) in corpusValues) {
            assertEquals("statusHead($raw) 应与分析侧一致", expected, ReportAnalyzer.statusHead(raw))
        }
        assertTrue("completed 判为跑完", ReportAnalyzer.isCompleted("COMPLETED"))
        assertTrue("aborted 不判为跑完", !ReportAnalyzer.isCompleted("aborted:bound_network_lost"))
        // R-10：未知不当作跑完（"缺证据≠健康"）
        assertTrue("null 不判为跑完", !ReportAnalyzer.isCompleted(null))
    }

    @Test
    fun `blank status folds to unknown on the kotlin side too`() {
        // 这是分叉点所在（已报大脑待裁）：归一化层两端**一致**——都把空/空白折成 null；
        // 分歧发生在消费方判据（Kotlin T76 按原始字段判 null）。本条锁住归一化这一层不再漂。
        assertEquals("空串应折成 null（未知）", null, ReportAnalyzer.statusHead(""))
        assertEquals("空白串应折成 null（未知）", null, ReportAnalyzer.statusHead("   "))
        assertEquals("只有 reason 无主状态也折成 null", null, ReportAnalyzer.statusHead(":only_reason"))
    }
}
