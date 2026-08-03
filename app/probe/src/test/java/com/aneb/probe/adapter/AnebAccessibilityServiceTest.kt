package com.aneb.probe.adapter

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * [AnebAccessibilityService.formatAdapterEvtLine] 契约锚定（T27④）。
 *
 * 这行字符串是**消费方早已写好的契约**：`tools/e1/e1_analyze.py` 的
 * `parse_adapter_events()` 按 `k=v` 全局搜索取 `t_boot_ns=`，字段名/顺序改了
 * 消费方就读不到（D-276 反面教材）。本测试钉的是**字面格式**，不是"编译过了"。
 */
class AnebAccessibilityServiceTest {

    @Test
    fun `click type line carries t_boot_ns in the expected key=value shape`() {
        val line = AnebAccessibilityService.formatAdapterEvtLine(
            type = "click", cls = "android.widget.Button", desc = "发送",
            txtLen = 0, pkg = "com.larus.nova", tBootNs = 123_456_789_012L,
        )
        assertEquals(
            "ADAPTER_EVT type=click cls=android.widget.Button desc=发送" +
                " txt_len=0 pkg=com.larus.nova t_boot_ns=123456789012",
            line,
        )
    }

    @Test
    fun `content type line carries t_boot_ns too — not just click`() {
        // 3d31512 之前 content 分支完全不打这行；这条测试钉住「两种类型都有」，
        // 免得将来有人重构时把 content 分支的调用悄悄漏掉。
        val line = AnebAccessibilityService.formatAdapterEvtLine(
            type = "content", cls = "androidx.compose.ui.platform.ComposeView",
            desc = "null", txtLen = 42, pkg = "com.deepseek.chat", tBootNs = 987_654_321_000L,
        )
        assertEquals(
            "ADAPTER_EVT type=content cls=androidx.compose.ui.platform.ComposeView" +
                " desc=null txt_len=42 pkg=com.deepseek.chat t_boot_ns=987654321000",
            line,
        )
    }

    @Test
    fun `t_boot_ns stays last even when desc contains a space`() {
        // 消费方按 k=v 全局搜索、dict 后写覆盖先写——t_boot_ns 必须在行尾才安全
        // （3d31512 手工验证过这一点，这里把它钉成自动化断言，不再靠人工复核）。
        val line = AnebAccessibilityService.formatAdapterEvtLine(
            type = "click", cls = "android.widget.Button", desc = "发送 按钮",
            txtLen = 0, pkg = "com.larus.nova", tBootNs = 1L,
        )
        assertTrue(
            "t_boot_ns 必须是最后一个 k=v 字段，desc 带空格时才不会截断它: $line",
            line.endsWith(" t_boot_ns=1"),
        )
    }
}
