package com.aneb.probe.ui

import com.aneb.probe.data.TestRun
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 首屏「上次 run」两个标签的红线（T88 ③）。
 *
 * **缺陷形态**：`HomeScreen` 把 `android.os.Build.MODEL`（一个**当前**事实）与
 * `homeNetworkLabel(lastRun)`（**上次那一轮**的值）用 `·` 拼成一句渲染，屏上读作
 * `P40 Pro · Wi-Fi 网络` —— 读者会把**整句**读成当前状态，而那个 transport
 * 可能是三天前、在另一个网络下测的。**一个陈旧值与一个新鲜值在屏上一模一样。**
 *
 * 另一半是**合并 token**：原实现用一个 `else` 把「**尚未测试**」与「**transport 未知**」
 * 渲染成同一句「自动选择网络」——对前者是**凭空断言**（一次都没跑过，何来网络），
 * 对后者是**把未知说成已知**，而两种情况在屏上无从分辨。
 *
 * ⚠ **本文件守的是文案的「限定语」，不是排版**：真机上「时间戳会不会被 `maxLines = 1`
 * 截掉」本层看不见，**由装机后的真机截图闭合**，未闭合前不得当它已闭合。
 */
class HomeLastRunLabelTest {

    private fun run(transport: String) = TestRun(
        runId = "run-1", startedAtEpochMs = 1_752_000_000_000L,
        serverBase = "http://10.0.2.2:8443", mode = "quick",
        scenarioOrder = "s1_chat,s2_coding_agent,s3_multimodal", transport = transport,
        kpiSet = "agent-qoe-kpi-v0.2", aqsVersion = "aqs-v0.1",
        profileVersions = "s1_chat@0.2.0", schemaVersion = "1.0",
        profileSource = "server", appVersionName = "0.3.0", appVersionCode = 1L,
        guardMetadata = "private_dns_active=false", aqsScore = 88.5, aqsLowConfidence = false,
        aqsVetoApplied = false, aqsNotComputableReason = null,
        status = "completed", reportStatus = null,
    )

    @Test
    fun `网络标签必须带「上次」限定与时刻,否则会被读成当前网络`() {
        val label = homeNetworkLabel(run("wifi"))
        assertTrue(
            "缺「上次」限定：与 Build.MODEL 拼成一句后，整句会被读成当前状态（实得：$label）",
            label.contains("上次"),
        )
        assertTrue(
            "缺时刻：读者无从判断这个值有多旧（实得：$label）",
            Regex("""\d\d-\d\d \d\d:\d\d""").containsMatchIn(label),
        )
        assertTrue("丢了网络本身（实得：$label）", label.contains("Wi-Fi"))
    }

    @Test
    fun `尚未测试与 transport 未知不是同一句`() {
        val never = homeNetworkLabel(null)
        val unknown = homeNetworkLabel(run("something-else"))
        assertEquals("一次都没跑过时不该断言任何网络", "尚未测试", never)
        assertTrue("未知 transport 不该被说成已知（实得：$unknown）", unknown.contains("网络未知"))
        assertTrue("两种情况渲染成了同一句 —— 屏上无从分辨", never != unknown)
    }

    @Test
    fun `连接模式同样分开这两件事`() {
        assertEquals("尚未测试", homeConnMode(null))
        assertEquals("Wi-Fi · 多线程", homeConnMode(run("wifi")))
        assertEquals("蜂窝 · 多线程", homeConnMode(run("cellular")))
        assertTrue(
            "未知 transport 被渲染成了一个具体模式",
            homeConnMode(run("auto")).contains("未知"),
        )
    }

    @Test
    fun `transport 大小写不影响判定`() {
        assertEquals(homeConnMode(run("wifi")), homeConnMode(run("WiFi")))
        assertEquals(homeNetworkLabel(run("cellular")), homeNetworkLabel(run("CELLULAR")))
    }
}
