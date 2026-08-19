# T48 · 3-tab UI 改造终态提案（设计供裁，不动手）

> 属主 v2 ｜ 2026-08-19 ｜ **只出设计，未改一行产品代码**
> 派单口径：终态提案（结合仪表切换复活 / s4 吞吐场景 / 看板降级裁定）+ 每 tab 信息架构与既有屏去留映射 + 实施拆批（含前台 Service 设计评审位）+ UI 自动化测试策略。
> 本文以**实测现状**为基线（见 §1，行数/挂载逻辑均现读代码，非记忆）。

---

## 1. 现状基线（实测，2026-08-19 HEAD=1752f35）

**导航骨架**：单 Activity + `MainTab{Test,History,Settings}` 三 tab（`components/MainTab`），下钻屏 `Screen{Home,Result,ApiProbe,ReachBoard,Report}` 隐底栏、各自返回回根。

**Test tab 内已是"模式段控驱动的单入口多模式"**（非三入口并列，比早期计划更规整）：
```
MainTab.Test
├── TestModeSegments(profiles = TestModeProfiles.ALL)   ← 数据驱动：加模式=加 profile
├── ModeProfileStrip(选中 profile)                       ← 模式信息条
└── selectedModeId 分派：
    ├── basic_network   → SpeedTestScreen   (786 行；含 recovery/shaped 子测 + recentSynthetic)
    ├── voice_realtime  → VoiceTestScreen   (421 行；含 recentVoice)
    └── 其余(token_experience) → HomeRoute  (669 行；GO 半盘 + 三主屏流)
测量中(running/speedRunning/voiceRunning) 段控与信息条隐藏 → 全屏专注
```

**UI 层规模**（`ui/` 合计 10853 行，Top）：
| 文件 | 行 | 定位 |
|---|---|---|
| `ResultScreen.kt` | 1183 | 结果（简洁+专业双视图） |
| `MainActivity.kt` | **1178** | 导航 + 全部 Route + run 编排 |
| `SpeedTestScreen.kt` | 786 | basic_network 模式屏 |
| `components/SpeedTestComponents.kt` | 697 | v2 组件族（StBanner/StStep/StLink/StGraph/StResults/AnebTabBar） |
| `HomeScreen.kt` | 669 | token_experience 模式屏（GO 半盘） |
| `TestModeProfile.kt` | 614 | 模式 profile 数据模型（+Loader 197） |
| `SettingsScreen.kt` | 522 · `VoiceTestScreen.kt` 421 · `ApiProbeScreen.kt` 391 · `ReportScreen.kt` 349 · `HistoryScreen.kt` 341 · `ReachabilityBoardScreen.kt` 262 · `ResultAqsBreakdown.kt` 234 · `HalfGauge.kt` 249 | |

**关键事实**：模式体系已 spec 驱动（`spec/profiles/client/client_profiles.json` 三 mode：`basic_network`/`token_experience`/`voice_realtime`），`HalfGauge` 180° 半盘 + v2 组件族已落地并被三主屏取用。

## 2. 终态信息架构（提案）

**维持 3-tab**（不扩 tab 数）。理由：tab 是"任务类别"不是"功能清单"；模式已由段控承载，再拆 tab 会让"测哪个模式"出现两个并列控件（tab + 段控），互相争夺同一语义。

```
① 测试 (Test)          ② 历史 (History)        ③ 设置 (Settings)
   模式段控〔3 模式〕        run 列表(AQS 徽标)       服务节点 / 传输 / 路测
   ├ basic_network         ├→ 结果(下钻)           ├→ 可达性看板(下钻)★降级位
   ├ token_experience      └  报告入口(下钻)        ├→ API 探针(下钻)
   └ voice_realtime                                └  开发者开关
   〔测量中全屏专注〕
```

**三处待裁点的提案落位**：

| 裁定点 | 提案 | 理由 |
|---|---|---|
| **仪表切换复活**（AQS/TTFT/ITL 三选一，v2 期1 曾做、v2 设计定稿时按"单指针表"取消） | **不复活为用户可见控件**；改为**模式 profile 的 `liveMetrics[].render` 数据驱动**（`LiveRender{WAVEFORM,GAUGE,RUNNING_NUMBER,BAR}` 已在 `TestModeProfile` 就位） | 用户手切核心量＝把"该看什么"甩给用户；而各模式**本就知道**自己的主指标（语音看 M7/近零到达、token 看 ITL、basic 看吞吐）。用已有 spec 字段驱动，零新控件、零新常量 |
| **s4 吞吐场景** | 客户端侧**已就绪**（DB v20 `u3_/d3_` 列 additive、`ScenarioRunner` adaptive 窗口）；UI 侧**先不建独立屏**，作为 `basic_network` 模式的一个子测（与 recovery/shaped 同位） | D-495：E-01 上 0.8.3 已上线但 **`s4_throughput` 契约仍缺** → 建 UI 会得到一个恒空的面。**待服务端补齐再接线**，此前 UI 不造"看起来能用实则无数据"的入口（R-10 精神） |
| **看板降级** | 维持**已落地的降级**：可达性看板从顶级 tab → 设置二级下钻 | 它是**连接层免 key 探测**（`application_reachability_tls_no_key`，不进 AQS），与"测体验"不同口径；放顶级会让用户误读为一种"体验测试" |

## 3. 既有屏去留映射

| 屏 | 去留 | 说明 |
|---|---|---|
| `HomeScreen` / `SpeedTestScreen` / `VoiceTestScreen` | **留**，三者并列为模式屏 | 已由段控分派，形态正确 |
| `ResultScreen`（简洁+专业） | **留**；专业视图待 v2 组件族样式对齐（见批 2） | 1183 行，最大单屏，拆分见 §4 |
| `HistoryScreen` / `ReportScreen` | 留（History tab 根 + 下钻） | |
| `SettingsScreen` | 留（Settings tab 根） | 收纳可达性/API 探针二级入口 |
| `ReachabilityBoardScreen` / `ApiProbeScreen` | 留，**均为设置二级下钻** | 口径与主测试线不同，见 §2 |
| `ShareCard` | 留（结果页触发，离屏 Canvas 出图） | |
| `MainActivity` **1178 行** | **拆**（见批 1） | 导航 + 9 个 Route + run 编排混居，是最大结构债 |

## 4. 实施拆批（每批可独立交付 + 全量验证）

> 通则：**每批跑 `:probe:assembleDebug + :probe:testDebugUnitTest` 全绿**；不动 engine/scoring/net/radio/data 测量语义、run 编排、autorun intent、日志 KEY、落库口径。

- **批 1 · MainActivity 结构拆分**（最高价值，纯搬运）
  把 9 个 `*Route` composable 从 `MainActivity.kt` 抽到 `ui/routes/`（`TestRoute`/`ResultRoute`/`HistoryRoute`/`SettingsRoute`/`ApiProbeRoute`/`ReachBoardRoute`/`ReportRoute`…），MainActivity 只留 `onCreate`+intent 解析+run 编排+导航骨架。**逐字搬运不改逻辑**，目标 1178 → ≈400 行。验收＝行为零变化（346+ 单测绿 + 真机六屏渲染）。

- **批 2 · 结果专业视图 v2 样式对齐**
  `ResultScreen` 的 `DetailedResultView` 换 v2 组件族（`StResults`/门限微刻度/`ResultAqsBreakdown` 真实"组→KPI→贡献分"）。**只改呈现不改 `ResultFormat` 口径**（D-02 单一事实源）。

- **批 3 · 前台 Service 迁移**〔**设计评审位 —— 本批需单独评审后再动手**〕
  T45 §6.4 #2 与 T48 批 C 的共同前置。**behavior-changing**：涉及测量期进程存活/Doze/省电语义，直接影响 `valid/valid_low_confidence` 判定。评审需回答：①前台 Service 生命周期与 run 生命周期的绑定点；②通知渠道与用户可见文案（不得暗示"运营商评级"）；③它对既有"测中持续监控"有效性守卫的影响；④失败路径（用户划掉通知/系统杀）如何落 `invalid` 而非静默截断。**未过评审不实施**。

- **批 4 · s4 吞吐子测接线**（**门控：E-01 契约补齐**，D-495）
  服务端 `s4_throughput` 上线后，接为 `basic_network` 子测，复用 `u3_/d3_` 已有列。

- **批 5 · 模式驱动实时呈现**（承 §2 仪表切换裁定）**〔2026-08-19 定性订正〕**
  `LiveMetric.render` 数据驱动实时区（WAVEFORM/GAUGE/RUNNING_NUMBER/BAR），删"用户手切核心量"设想。
  **实况核实**：spec 里 12 处 `render` 声明（GAUGE 3 / RUNNING_NUMBER 4 / WAVEFORM 5）、模型有字段、
  Loader 已解析，**但 UI 零消费方**——初看是"字段有生产端无读者"的经典缺口（D-340 族）。
  **但查 D-69 后订正**：`source` 侧的可解析闸门（`DynamicMetricSelection.resolveSource`）已做完，
  而 **"真机手感与渲染接线"被 D-69 显式列为剩余项并标 🟠设备**——即批 5 **不是无人发现的缺口，
  是有意留到设备窗的已知项**（渲染形态要真机验手感，纯代码改完也无法判对错）。
  **故批 5 排期归设备窗，不在纯代码批次里抢跑。**

## 5. UI 自动化测试策略

**现状（实测订正）**：UI 层**并非无测试**——103 个测试文件中 **20 个覆盖 `com.aneb.probe.ui` 包**：`ResultFormatTest`/`ResultFormatPhase3Test`/`VerdictTextTest`/`GradeTest`/`GaugeMathTest`/`ResultAqsBreakdownTest`/`NearZeroRatioDisplayTest`/`DynamismVisibilityGoldenTest`/`HistoryFeedTest`/`ReportFormatTest`/`TestModeProfileContractTest`/`KeepScreenOnPolicyTest` 等。
（写本文初稿时我断言"UI 层无自动化测试"，**核实后推翻**——教训：先数再断言。）

**真实缺口是渲染层**：无 `createComposeRule`、**无 `androidTest/` 目录**。即"数字→判词"的纯函数已被守卫，但"判词→像素"这一段无人看。据此补两层：

1. **渲染层红线测试（`createComposeRule`，JVM/Robolectric，无需真机）** ★唯一真缺口，优先做。三条断言：
   ① **R-10**：喂 null KPI 的 UI 状态，渲染树中必须出现 "…"/"—" 且**绝不出现 "0"**（含仪表指针角/进度弧的几何值）；
   ② **低置信必带 ⚠ 角标**（AQS 与任一低置信 KPI）；
   ③ **claim scope 页脚常驻**。
   理由：这三条是测量诚实性在 UI 的最后防线，且**恰好是纯函数测试够不到的**（它们测的是"渲染出来没有"，不是"算得对不对"）。先例：v2 SpeedTest 重构中 `HalfGauge` 曾用 `aqsRunning ?: 0` 驱动指针——纯函数层全绿，靠人工评审才逮到。
2. **既有纯函数层：维持并随批 2 扩**。批 2 改专业视图呈现时，同步给新增的"组→KPI→贡献分"展开加断言（`ResultAqsBreakdownTest` 已有骨架可扩）。
3. **真机仅冒烟**：六屏渲染零崩溃 + 导航可达 + logcat 无 FATAL/ANR。**不做像素级/截图回归**（设计仍在迭代，基线会天天红，维护成本 > 收益）。

## 6. 风险与边界

- 批 1 是纯搬运但**触及 MainActivity 全文件**——与任何同时改 MainActivity 的会话冲突。执行前须在板面认领并确认无并发方（CLAUDE.md 提交纪律：`git commit <pathspec>` + `git diff --cached` 逐行核）。
- 批 3 **必须先过设计评审**（behavior-changing，影响有效性判定）。
- 批 4 **外部门控**（E-01 服务端），不可在本树自解。
- 全部批次**不碰**：门限/AQS 权重/T4 否决/分档线/claim scope/日志 KEY——改这些属测量语义变更，须 DECISION_LOG + 红队复核 + 版本 bump。

## 7. 建议执行序

**批 1（结构拆分）→ 批 2（专业视图）→ 测试策略第 1、2 层 → 批 5（模式驱动呈现）**；批 3 待评审、批 4 待服务端。
理由：批 1 让后续每批的 diff 都变小变清晰；测试第 1、2 层在批 2 之后立刻补，能把"呈现层改动"锁进守卫，避免边改边退化。
