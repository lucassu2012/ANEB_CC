package com.aneb.probe.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 分享卡低置信警示的红线（T88 追加件，D-610 ③ 延伸到第三面）。
 *
 * **为什么这面要单独守**：D-610 ③ 裁的是「简洁视图把不可信压成句尾括号，而专业视图有
 * 独占一行的徽章」。同一形态在分享卡上更严重——分享图是**唯一会脱离 App 传给第三人**的
 * 面，读它的人手里没有 App、没有详情页、没有任何补充上下文。而修此件前，分享卡携带低
 * 置信的唯一途径，是 `VerdictText` 追加在结论**句尾**的那个括号附注：正是被判为不合格的
 * 那个形态本身。
 *
 * ---
 * ## ⚠ 这三条守到哪一层，以及守不到哪一层（先写清，别让读者以为覆盖住了）
 *
 * 守得住：**「画不画」与「画在结论之前还是之后」这两个判定**。
 *
 * **守不住：有人把 `render()` 里那段 `lowConfBannerLayout(model)?.let { ... }` 整段删掉。**
 * 删掉后本文件三条**全绿**——纯函数还在、文案还同源、版面数还对，只是没人调它了。这正是
 * 本仓反复咬到的「三条测试围着一条从没被执行的代码路径打转而全绿」。
 *
 * 之所以停在这里而不是硬闭合：分享卡走 Canvas 离屏绘制，而**本仓单测环境没有 Robolectric
 * native runtime**（实测 `Unable to load Robolectric native runtime library`，栅格化不可用），
 * 逐像素比对根本跑不起来；补它要下载 native 构件并改动全会话共用的构建配置，代价与授权
 * 都不该由这一件承担。**该缺口由装机后的真机分享图截图闭合**，未闭合前不得当它已闭合。
 */
class ShareCardLowConfidenceTest {

    private val goodArgb = 0xFF7FD1A6.toInt()
    private val fairArgb = 0xFFEFCA72.toInt()

    /**
     * 两侧**只有 lowConfidence 一个变量**：verdict 逐字相同。
     * 真实链路上句尾附注确实会随低置信而变，但那样两侧就有两个变量，
     * 差异无法归因到横幅——「判决性检验一次只能变一个量」。
     */
    private fun model(lowConfidence: Boolean) = ShareCard.Model(
        score = 72,
        gradeLabel = "良",
        // 用 ARGB 字面量而非 android.graphics.Color.parseColor：后者在纯 JVM 单测里 not mocked，
        // 会把本文件拖去依赖 Robolectric。被测的三个判定与颜色无关，不值得为它引框架。
        gradeColorArgb = goodArgb,
        verdict = "体验尚可——AI 助手多数时候跟得上，偶尔需要等一会儿。",
        tiles = listOf(
            ShareCard.Model.Tile("820ms", "响应速度", goodArgb),
            ShareCard.Model.Tile("0", "卡顿", goodArgb),
            ShareCard.Model.Tile("4.2", "上传 Mbps", fairArgb),
        ),
        networkLine = "Wi-Fi · 5 GHz",
        lowConfidence = lowConfidence,
    )

    @Test
    fun `非低置信不画横幅`() {
        assertNull(
            "非低置信的分享卡不该出现警示横幅——警示要稀缺才有效",
            ShareCard.lowConfBannerLayout(model(lowConfidence = false)),
        )
    }

    @Test
    fun `低置信时横幅整条落在结论起绘线之上`() {
        val band = ShareCard.lowConfBannerLayout(model(lowConfidence = true))
        assertNotNull("低置信时必须有横幅版面，null ＝ 这面又退回句尾括号那一档", band)
        band!!

        assertTrue(
            "横幅底边 ${band.bottom} 越过了结论起绘线 ${ShareCard.verdictTop}：" +
                "警示落到结论之后＝让读者先形成判断、再被补一句「其实别太信」，" +
                "正是 D-610 ③ 判为不合格的那个次序",
            band.bottom <= ShareCard.verdictTop,
        )
        assertTrue(
            "文字基线 ${band.baseline} 不在横幅框 [${band.top}, ${band.bottom}] 内，字会画到框外",
            band.baseline in band.top..band.bottom,
        )
    }

    @Test
    fun `横幅文案与结果页徽章同源,不许两面各写一份`() {
        assertEquals(
            "分享卡与结果页的低置信文案必须同源；各写一份则改一处漏一处，而分叉后两面都不报错",
            lowConfBadgeText,
            ShareCard.lowConfBannerLayout(model(lowConfidence = true))?.text,
        )
    }
}
