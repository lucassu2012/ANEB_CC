package com.aneb.probe.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * THERMAL 接线（D-556）：[ThermalSummary.fold] 的语义守卫 + 对 EnvMonitors 发射格式的反向钉。
 *
 * 折叠器从 detail 串解析（不另立第二种编码），于是「发射端模板」与「解析端正则」是一对
 * 会各自漂移的同名事实（D-315 形状）——最后一条测试直接读 EnvMonitors.kt 源码钉住模板串：
 * 发射端改格式（哪怕只改一个空格）本测试当场红，而不是折叠器静默把一切折成双 null
 * （谎称无监控，比报错危险）。
 */
class ThermalSummaryTest {

    @Test
    fun `空列表——无一条 THERMAL 事件 = 双 null（无监控）`() {
        assertEquals(ThermalSummary.Env(null, null), ThermalSummary.fold(emptyList()))
    }

    @Test
    fun `只有不可用路径事件 = 双 null——unavailable 与 registration_failed 不含 status=`() {
        assertEquals(
            ThermalSummary.Env(null, null),
            ThermalSummary.fold(
                listOf("power_manager_unavailable", "listener_registration_failed: boom"),
            ),
        )
    }

    @Test
    fun `initial_unknown（初值读取失败的诚实标记）不计入——只有它时=双 null`() {
        // 大脑批复 08-22 ③：读不到就是不知道，绝不伪装 none。若监听器随后有真事件，
        // 摘要仍按真事件出（下一行验证混合形状）。
        assertEquals(
            ThermalSummary.Env(null, null),
            ThermalSummary.fold(listOf("initial_unknown: status_read_failed")),
        )
        assertEquals(
            "初值失败但监听器活着——真事件照常折叠",
            ThermalSummary.Env("light", 0),
            ThermalSummary.fold(listOf("initial_unknown: status_read_failed", "status=light polluting=false")),
        )
    }

    @Test
    fun `只有初始 none = ("none", 0)——0 是真实读数（监控在位且全程干净），非 R-10 伪装`() {
        assertEquals(
            ThermalSummary.Env("none", 0),
            ThermalSummary.fold(listOf("initial status=none polluting=false")),
        )
    }

    @Test
    fun `max 折叠取最烈一档且与事件次序无关；moderate 未到 SEVERE，污染计数保持 0`() {
        val details = listOf(
            "initial status=none polluting=false",
            "status=moderate polluting=false",
            "status=light polluting=false",
        )
        assertEquals(ThermalSummary.Env("moderate", 0), ThermalSummary.fold(details))
        assertEquals(
            "max 必须与事件次序无关",
            ThermalSummary.Env("moderate", 0),
            ThermalSummary.fold(details.reversed()),
        )
    }

    @Test
    fun `污染计数只数 polluting=true 的事件——critical 压过 severe，计数 2`() {
        assertEquals(
            ThermalSummary.Env("critical", 2),
            ThermalSummary.fold(
                listOf(
                    "initial status=none polluting=false",
                    "status=severe polluting=true",
                    "status=critical polluting=true",
                    "status=light polluting=false",
                ),
            ),
        )
    }

    @Test
    fun `发射端格式反向钉——EnvMonitors emitThermal 的模板串必须原样在源码里`() {
        val src = repoFile("app/probe/src/main/java/com/aneb/probe/engine/EnvMonitors.kt")
            .readText(Charsets.UTF_8)
        assertTrue(
            "EnvMonitors.emitThermal 的 detail 模板改了——ThermalSummary.DETAIL_FORMAT 的正则" +
                "会静默解析不到、一切 run 折成双 null（谎称无监控）。两处必须一起改。",
            src.contains("\${prefix}status=\${thermalName(status)} polluting=\$polluting"),
        )
        assertTrue(
            "EnvMonitors 的 initial_unknown 诚实标记没了（大脑批复 08-22 ③的修复被回退）——" +
                "初值读取失败将重新伪装成正常事件或整个消失。",
            src.contains("\"initial_unknown: status_read_failed\""),
        )
    }

    @Test
    fun `调用点钉——TestEngine 必须把 fold 结果真的传给 build（函数级守卫防不住这一面）`() {
        // D-325 形状：守卫全落在函数上时，「main 不再传参」的突变必然存活——block 不会
        // 出现在 wire 上而没有任何测试变红。TestEngine 与 Android 强耦合无法单测实跑，
        // 源码钉是本层够得到的量法（格式反向钉同款）。
        val src = repoFile("app/probe/src/main/java/com/aneb/probe/engine/TestEngine.kt")
            .readText(Charsets.UTF_8)
        assertTrue(
            "TestEngine 不再把 ThermalSummary.fold(thermalDetails…) 传给 ResultReporter.build——" +
                "env 块将从一切真实 run 上消失且零测试变红。",
            src.contains("env = ThermalSummary.fold(thermalDetails.toList())"),
        )
        assertTrue(
            "THERMAL 事件不再被累计（收集点旁挂被删）——fold 恒收空列表，一切 run 双 null。",
            src.contains("if (ev.type == EnvEventType.THERMAL) thermalDetails.add(ev.detail)"),
        )
    }

    /** AdapterSpecTest 同款：从 user.dir 向上找仓根相对文件。 */
    private fun repoFile(relFromRepoRoot: String): File {
        var cur: File? = File(System.getProperty("user.dir") ?: ".").absoluteFile
        while (cur != null) {
            val cand = File(cur, relFromRepoRoot)
            if (cand.isFile) return cand
            cur = cur.parentFile
        }
        error("找不到 $relFromRepoRoot（从 user.dir 向上未命中）")
    }
}
