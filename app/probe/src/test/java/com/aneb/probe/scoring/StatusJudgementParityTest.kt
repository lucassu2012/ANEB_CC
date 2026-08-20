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

    /**
     * **消费方判据这一层，现在可以钉了**（本类 docstring 原写着「后者正是待裁项，裁完再补」）。
     * D-534 §3 已裁且两半均已落码：分析半 `run_pools_into_stats`（`a81dfee`/T75）、
     * 设备半 `ReportAnalyzer` 的告诫句谓词（D-536 + D-539 修分叉）。**两端此刻一致**：
     *
     * - **未知**（缺失/空/空白）：分析侧**进池**（`head is None` → True）；设备侧**不报**"未正常结束"。
     * - **`completed`**（含 `COMPLETED`）：进池 / 不报。
     * - **`aborted:<任何 reason>`**：不进池 / 报。
     *
     * **未知那一格是本条真正的看点**：两端都选"未知＝良性"，理由同源——缺席是合同合法态
     * （schema 把 `status` 类型写作 `["string","null"]`），当故障处理就是"读缺席为值"、违 R-10。
     * 而 D-539 之前设备侧按**原始字段**判空，空串会被报成中止、与分析侧相反——**本条就是
     * 那次分叉的防复发装置**。
     */
    @Test
    fun `consumer predicates agree on all three status classes now that both halves landed`() {
        val py = pySource
        val i = py.indexOf("def run_pools_into_stats")
        assertTrue("分析侧应有 run_pools_into_stats（D-534 §3 判据落点）", i >= 0)
        val end = py.indexOf("\ndef ", i + 1).takeIf { it > 0 } ?: py.length
        val body = py.substring(i, end)
        // 源码文本钉住"未知进池"：它是零实例分支（真实语料 3509 条无不可用 status），
        // 语料测不到，只能钉源码——该函数自己的 docstring 也是这么说的（D-302 同族）。
        assertTrue(
            "分析侧应仍是「未知或 completed 才进池」——若被改成只认 completed，" +
                "未知会被当故障踢出分母，与设备侧相反且违 R-10",
            body.contains("head is None or head ==") || body.contains("head is None or head=="),
        )

        // 设备侧三类取值的对照（是否报"未正常结束"）
        assertEquals("null 折未知", null, ReportAnalyzer.statusHead(null))
        assertEquals("空串折未知", null, ReportAnalyzer.statusHead(""))
        assertTrue("completed 不报", ReportAnalyzer.isCompleted("completed"))
        assertTrue("COMPLETED 不报（大小写折平）", ReportAnalyzer.isCompleted("COMPLETED"))
        assertTrue("aborted 要报", !ReportAnalyzer.isCompleted("aborted:bound_network_lost"))
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
