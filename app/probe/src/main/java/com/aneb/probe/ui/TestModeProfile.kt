package com.aneb.probe.ui

/**
 * 一个**测试模式**的档案（模式级 Profile）——不是 [com.aneb.probe.engine.ScenarioProfile]
 * （那是 token 引擎内部的场景/KPI 合同，粒度不同）。捕获用户 /goal 点 3 的四facet：
 * **什么业务 · 测哪些指标 · 哪些是动态的 · 得出什么结论**。
 *
 * 扩展方式（/goal 点 2）：新增一种测试模式 = 往 [TestModeProfiles.ALL] 加一个 profile
 * （+ 其测试屏 + MainActivity 里一处按 id 选屏的 when 分支）。分段开关、模式信息条均由本表数据驱动。
 */
data class TestModeProfile(
    val id: String,
    /** 分段开关/标题显示名。 */
    val displayName: String,
    /** 一句话副标。 */
    val tagline: String,
    /** 什么业务：评估的真实场景。 */
    val business: String,
    /** 测哪些指标（含是否高频动态刷新）。 */
    val metrics: List<ModeMetric>,
    /** 得出什么结论：判定口径。 */
    val conclusion: String,
)

/** 模式内一个指标。[dynamic]=是否高频动态刷新（SpeedTest 式波动展示的候选）。 */
data class ModeMetric(
    val name: String,
    val unit: String,
    val dynamic: Boolean,
)

object TestModeProfiles {

    val BASIC_NETWORK = TestModeProfile(
        id = "basic_network",
        displayName = "网络基本性能",
        tagline = "SpeedTest 式上下行速率 + 时延",
        business = "评估这条网络的原始承载力：能否流畅收发大对象、时延是否够低——判断底层网络是否" +
            "适合 AI 对话 / 编码 / 多模态。",
        metrics = listOf(
            ModeMetric("下行速率", "Mbps", dynamic = true),
            ModeMetric("上行速率", "Mbps", dynamic = true),
            ModeMetric("时延", "ms", dynamic = true),
            ModeMetric("抖动", "ms", dynamic = false),
        ),
        conclusion = "上下行 / 时延 / 抖动四门限 → 优良·尚可·偏弱，并给 AI 使用场景建议。",
    )

    val TOKEN_EXPERIENCE = TestModeProfile(
        id = "token_experience",
        displayName = "Token 体验",
        tagline = "AI 流式交互取证 → AQS 分",
        business = "从真实 AI 交互视角评估体验：首字快不快、吐字稳不稳、卡顿多不多——直接对应" +
            "“用起来爽不爽”。",
        metrics = listOf(
            ModeMetric("Token 速率", "tok/s", dynamic = true),
            ModeMetric("字间时延 ITL", "ms", dynamic = true),
            ModeMetric("首字时延 TTFT", "ms", dynamic = false),
            ModeMetric("卡顿", "次", dynamic = false),
        ),
        conclusion = "多场景 KPI 加权 → AQS 分与分级（优/良/可/差）+ 取证明细视图。",
    )

    /** 分段开关顺序即此表顺序。默认选中 [TOKEN_EXPERIENCE]（首页 token 体验）。 */
    val ALL = listOf(TOKEN_EXPERIENCE, BASIC_NETWORK)

    fun byId(id: String): TestModeProfile = ALL.firstOrNull { it.id == id } ?: TOKEN_EXPERIENCE
}
