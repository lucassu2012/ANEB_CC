package com.aneb.probe.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import com.aneb.probe.ui.theme.AnebTheme
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * **渲染层红线测试**（D-501 提案 §5 第 1 层——大脑明令**保留在 48h 冲刺内**的那批，
 * 理由逐字："三条断言是测量诚实性在 UI 的最后防线，且纯函数测试够不到"）。
 *
 * ## 为什么非要查渲染树
 * D-501 点名了 `HalfGauge ?: 0` 这个先例：**一个 `?: 0` 写在 Composable 里，纯函数层
 * 根本看不见它**——`ResultFormat.formatValue()` 可以完美返回"—"，而渲染那一行的
 * Composable 仍然可以把 null 变成 0 显示出去，两边各自都"绿"，读者看到的却是个假 0。
 * 能抓住这种事的只有一件工具：**把它真渲染出来，再去渲染树里找**。
 *
 * ## 为什么此前没有，以及为什么现在有了
 * D-523 H-4 实测：`androidTest` 目录零结果、`createComposeRule` 全仓仅存于一句注释——
 * 因为本仓只有 JVM JUnit、无 Robolectric，Compose 测试一直被认为需要设备。**那个前提
 * 现在不成立**：Robolectric 4.16.1 + `android-all-instrumented:15`（API 35，与本项目
 * `compileSdk` 同版）+ `ui-test-junit4`（随 compose-bom 解析）**本机缓存全齐、离线可跑**，
 * 且走 `testImplementation` 而非 `androidTest` ⇒ **能进常设门禁链**（D-518 刚把全量单测
 * 接进 `verify_all`），不需要设备、不需要模拟器。
 *
 * 本文件覆盖三条红线里的**前两条**（渲染树无假 0、低置信角标）——它们落在已经是
 * `internal` 的 [KpiLine] 上，够得到；第三条（claim scope 页脚）所在的 Composable 目前
 * 仍是 `private`，另行处理，不为了凑数在这里放一条测不到真东西的断言。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class RenderRedlineTest {

    @get:Rule
    val compose = createComposeRule()

    private fun row(
        id: String = "T1",
        label: String = "首字响应",
        value: Double? = null,
        unit: String = "ms",
        grade: String? = null,
        lowConfidence: Boolean = false,
    ) = ResultFormat.KpiRow(
        id = id, label = label, value = value, unit = unit,
        grade = grade, lowConfidence = lowConfidence,
    )

    // ---- 红线一：渲染树里不得出现假 0（R-10）----

    @Test
    fun `缺失值在渲染树里显示为占位符而不是 0`() {
        compose.setContent { AnebTheme { KpiLine(row(value = null)) } }

        // 正面：占位符真的被渲染出来了。
        // 用计数而非 onNodeWithText（后者要求恰好一个节点）——实测缺失行会渲染出**两处**
        // 占位符：KPI 值一处、分级 chip 一处（grade 为 null 时同样按 R-10 显占位符，
        // 是正确行为）。第一版断言写成"恰好一个"当场红了，是断言写窄不是产品错。
        val placeholder = ResultFormat.formatValue(row(value = null))
        val shown = compose.onAllNodesWithText(placeholder, substring = true).fetchSemanticsNodes()
        assertEquals("缺失值必须渲染出占位符（值 + 分级各一处）", 2, shown.size)

        // 反面（这条才是红线本身）：**渲染树里一个"0"都不许有**。
        // 纯函数层永远抓不到这一条——formatValue 返回"—"是对的，而 Composable 里
        // 随便一个 `?: 0` 就能把它变回 0，两边各自都"绿"。
        val zeros = compose.onAllNodesWithText("0", substring = true).fetchSemanticsNodes()
        assertEquals("缺失值不得以 0 出现在渲染树里（R-10 假 0）", 0, zeros.size)
    }

    /**
     * **自证：上一条用的"渲染树里找 0"这个检测器，确实会响**（D-322：守卫能不能失败要造
     * 反例证明，不能靠推理）。
     *
     * 反例用**真实的 0**（0 是合法测量值）而不是去临时改产品代码——后者要动工作树，
     * D-321 记过一次"脚本自称还原了，和版本库说没差异，是两回事"的教训，能不动就不动。
     * 若哪天有人给 [KpiLine] 加了 `?: 0`，缺失行渲染出的正是这里被证明抓得住的那个形状。
     */
    @Test
    fun `自证检测器：真实的 0 会被上一条的判据抓到`() {
        compose.setContent { AnebTheme { KpiLine(row(value = 0.0, grade = "poor")) } }
        val zeros = compose.onAllNodesWithText("0", substring = true).fetchSemanticsNodes()
        assertEquals("检测器必须能看见渲染出来的 0，否则上一条是空气守卫", 1, zeros.size)
    }

    @Test
    fun `有值时照常渲染数字——防止上一条被写成永远不显示数字`() {
        // 没有这条，"渲染树里没有 0"可以靠"什么都不渲染"作弊通过。
        compose.setContent { AnebTheme { KpiLine(row(value = 150.0, grade = "good")) } }
        compose.onNodeWithText("150", substring = true).assertIsDisplayed()
    }

    // ---- 红线二：低置信必须在渲染树里显式带标 ----

    @Test
    fun `低置信行在渲染树里带出低置信标注`() {
        compose.setContent { AnebTheme { KpiLine(row(value = 150.0, grade = "good", lowConfidence = true)) } }
        compose.onNodeWithText(ResultFormat.LOW_CONFIDENCE_LABEL, substring = true).assertIsDisplayed()
    }

    @Test
    fun `非低置信行不得凭空带上该标注`() {
        compose.setContent { AnebTheme { KpiLine(row(value = 150.0, grade = "good", lowConfidence = false)) } }
        val marks = compose.onAllNodesWithText(ResultFormat.LOW_CONFIDENCE_LABEL, substring = true)
            .fetchSemanticsNodes()
        assertEquals("未标低置信的行不该出现低置信标注", 0, marks.size)
    }
}
