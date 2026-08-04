# T48：3-tab UI 改造设计方案（供大脑裁定，不动手）

**任务来源**：大脑派单（本会话记录），承 T45 审计。要求：设计方案供裁，不实现；产出一页设计文档，过裁后开工，入 D 号。

**方法论**：4 路只读并行调查（workflow `wf_97748107-eeb`，116 次工具调用，零代码改动）——HomeScreen 现状/吞吐双线关系/导航图与死屏/UI 自动化测试先例。全部结论均带 file:line 引用，非凭记忆。

---

## §1 现状基线（本提案需要的新增事实，T45 已写清的不复述）

1. **现行 3-tab＝测试/历史/设置**（`MainTab`，`SpeedTestComponents.kt:68-72`），非旧计划"Speed测试/可达性看板/历史"（T45 已记）。**"设置"本不在旧计划里**，是后来的结构性增补。
2. **测试 tab 内部已是"一个屏+模式切换"，不是"三选一切标签页"**：`Screen.Home` 根下按 `selectedModeId`（`TestModeSegments`，`MainActivity.kt:578-583`）原地渲染 `HomeScreen`（token，默认）/ `SpeedTestScreen`（basic_network）/ `VoiceTestScreen`（voice_realtime）三选一，`screen` 值全程不变（`MainActivity.kt:116-118` 自己的 KDoc 已说明这是两套独立状态机：tab/mode 层 vs Screen 下钻层）。**这本身已经是一种"三合一"设计**，且已稳定运行、M7/仪表切换等最近改动都建立在这个结构上。
3. **`Screen` 密封接口 6 个变体，5 个可达，仅 `Testing` 死**（逐点 grep 核实零写入点）：`Home`/`Result`/`ApiProbe`/`ReachBoard`/`Report` 全部可达；`Testing` 无任何写入点，连"潜在 autorun 路径"的注释都经核实是假的（autorun 三条路径没有一条会设 `screen = Screen.Testing`）。
4. **可达性看板降级是已裁定、有理由的决定**（D-463①），非本批范围：`ReachBoard` 从顶级 tab 降为设置二级入口，理由="复活需使用场景支撑，T46 全语料报告出来后看什么数据值得可视化再议"。**本提案不复活它**。
5. **`s4_throughput` 已上线却零 UI 面**：每次 Token 模式测试都会静默跑这个诊断场景（`TestEngine.kt:525-599`）、已落库，但 UI 层（`app/probe/src/main/java/com/aneb/probe/ui/`）对 `u3GoodputMbps`/`d3GoodputMbps` 零引用。**T47 自己的 spec（`PROFILE2_THROUGHPUT_PROBE_SPEC.md` §8.0）明确声明这不是"真实吞吐"**（单流应用层 goodput，非多流聚合容量测量，故意避开这个措辞），而 D-469 8-5 已裁定它是"**展示型诊断，不进 AQS**"——即设计意图本来就是要显示，只是不计分。
6. **`TestingScreen.kt` 死屏的独有内容已经清点完**：连接横幅/阶段步进器/设备-节点连线/实时吞吐折线/token流条/分层实时指标区，比已迁移的仪表切换器大得多；但与 `HomeScreen.kt` 共享 `TestProgressParser`（删除前必须先把它挪到独立文件，否则会带走 `HomeScreen` 依赖的解析器）。D-463③已裁定："若未来 UI 改造批覆盖其功能则随批删除"——**本批即那个"未来批"**。
7. **零 UI 自动化测试设施**：无 `androidTest`、无 Compose UI-test / Espresso 依赖（`build.gradle.kts`/`libs.versions.toml` 逐项核实）。项目对"设备侧代码"的既有原则（`tools/e234` 测试文件自述）：**真正碰设备/adb 的函数刻意不 mock，只用真机验证；离线测试只钉能钉住的那部分（门禁判据/参数解析/契约形状）**。
8. **一处记忆引用订正**：调查按大脑原话去搜"UI-mode 测试易错需主动盯"这条教训在 `DECISION_LOG.md` 里的出处，搜了约 35 遍未命中——它实际记在本人跨会话记忆文件里，说的是**另一个工具**（`fast_ui.py`，自动化第三方 DeepSeek 聊天 App 做时延测量，不是 ANEB 自己的 Compose UI）。本仓库真正同族的教训是 D-49/D-50/D-52/D-53/D-408/D-409/D-410/D-453（无障碍服务/E1-E234 实机取证链路的静默失败陷阱）——见 §5。

---

## §2 终态提案：**维持现行 3-tab（测试/历史/设置）为终态，不新增/不改名 tab**

**不采纳旧计划的理由**：旧计划"Speed测试/可达性看板/历史"是 2026-07-14 在测量核尚未成型、可达性看板还是顶级功能时定的；现状已经分叉且分叉方向都有独立裁定支撑（可达性看板降级=D-463①有意决定；模式切换收进单一测试 tab=已稳定运行的架构，不是权宜之计）。**新终态不是旧计划的三块，是对现状的确认+清理，不是重新发明**。

**核心判断**："测试 tab 内一屏三模式（token/basic-network/voice）"本身就是比"三个独立顶级 tab"更好的信息架构——三种模式共享同一批量级操作（GO/取消/查看上次结果），用户不需要因为换模式而重新学一套导航；这个模式切换器已经是稳定基础设施，本次不动它的骨架，只处理骨架之外仍未了结的两件事：**TestingScreen 死屏怎么处置**、**s4_throughput 诊断信息怎么露出**。

---

## §3 信息架构 + 屏幕去留映射

| Tab | 根屏 | 下钻/子屏 | 处置 |
|---|---|---|---|
| 测试 | `Screen.Home`→按模式原地渲染 `HomeScreen`(token,默认)/`SpeedTestScreen`(basic_network)/`VoiceTestScreen`(voice_realtime) | `Screen.Result`(完成后跳转/"上次结果"入口) | 三个模式屏**全部保留**，均为活代码且各自被最近改动（M7/仪表切换）验证过。`HomeScreen` 顺带修 3 处小毛病（见§4A） |
| 历史 | `HistoryScreen`（合并 `TestRun`/`VoiceResultEntity`/`AdapterObsEntity` 三类） | `Screen.Result`(点行)、`Screen.Report`(生成报告) | 不动，未被 D-462/463 点名有问题 |
| 设置 | `SettingsScreen`（服务器/模式/传输/路测开关/调试标志+Profile 3 适配器只读区） | `Screen.ApiProbe`→`Screen.ReachBoard`（两条入口） | 不动 |
| — | `Screen.Testing`（死屏） | — | **删除**（见§4A），先抽出共享的 `TestProgressParser` |

**s4_throughput 的落位**：不新增 tab/屏，加进 `Screen.Result` 的场景明细区——新增一行"U3/D3 单流 goodput（诊断，未计入 AQS）"，直接读已落库的 `scenario_result` 字段，零改 `TestEngine`/`AqsScorer`（D-469 8-5 已裁定的"展示型诊断"落地，纯 Result 屏读数）。

---

## §4 实施拆批

| 批 | 内容 | 风险 | 前置/裁决 |
|---|---|---|---|
| **A（机械/低风险）** | ①抽出 `TestProgressParser` 到独立文件；②删除 `TestingScreen.kt` 整屏+`Screen.Testing` 变体；③顺手修 `HomeScreen.kt` 三处：`onOpenLastResult` 死参数（接线或删除，二选一）、`homeNodeLabel` 硬编码"仿真节点·E-01"忽略 `lastRun`（接上真实值）、仪表核心量切换器在与所选指标无关的子阶段不做禁用态提示（补一个禁用视觉） | 低——纯清理+已验证过的既有模式补边角 | 无需外部裁决，符合 §6.2 式"分钟-小时级"标准，静默入 D 号即可 |
| **B（Result 屏新增）** | `Screen.Result` 场景明细加 U3/D3 诊断行，读 `scenario_result` 已落库字段 | 低——纯读，不改计分/接线 | 无需外部裁决（D-469 8-5 已授权"展示型诊断"） |
| **C（设计评审位，本批只占位不动手）** | `§6.4#2` 前台 Service 迁移——behavior-changing，影响长 autorun 窗口后台存活策略，与本批"长时保活/连续测量"话题相邻但不是同一件事 | 未评估（需先设计评审） | **不在本批范围**，只在此登记为下一个待评审项，等大脑/PO 排期 |
| **D（明确不做）** | 可达性看板复活为顶级 tab | — | D-463①已裁：等 T46 报告给出可视化需求再议，本批不空等也不预支 |

---

## §5 UI 自动化测试策略

**现状**：零 Compose-test/Espresso 基础设施，这不是缺口，是与本仓一贯纪律一致的选择——**碰 Android/设备的代码刻意不 mock，只用真机验证；能离线钉住的只有纯函数/契约/解析**（`tools/e234` 测试哲学原话）。本批不引入 Espresso：新增依赖+长期维护成本，且当前改动（删死屏、加一个诊断行）复杂度不足以论证这笔投入。

**订正**：本人跨会话记忆里"UI 模式测试易错需主动盯"那条，实指 `fast_ui.py`（自动化第三方 DeepSeek App），与本仓 Compose UI 无关，此处不套用。**本仓真正同族的教训**是无障碍服务/E1-E234 实机取证链路反复踩过的坑（D-49/50/52/53/408/409/410/453）——**"跑完了"不等于"跑对了"**：服务被拦截而不报错（D-49）、进程被杀而不重绑（D-50）、日志被系统吞掉+App 被冻结导致零观察却不报错（D-52）、检查步骤没独立成闸门而顶掉别人的测试（D-53）、观测窗口与刺激窗口零重叠却产出"看起来正常"的零方差数据（D-408/409）、锁屏陷阱导致 App 秒 pause 而日志不报错（D-410）、监控栈随会话重启静默失效 70 分钟无人发现（D-453）。

**本批落地动作**：批 A/B 完成后，**真机手动冒烟，主动盯不是等完成**——①三种模式各起跑一次到完成，确认导航/展示不受死屏删除影响；②历史/设置下钻逐条点一遍确认无死链；③确认无残留对已删 `TestingScreen`/`GaugeMetric`（该屏本地枚举）符号的引用（编译期已能拦大部分，冒烟只补编译拦不住的运行时路径，如 log 解析）。这是主动盯的手动验收，不是新增自动化套件。

---

## §6 诚实缺口/未决项

- `ReachBoard` 当年从顶级 tab 降级的**具体原因**未查（T45 审计已提示这个缺口）——不影响本提案（降级维持已是裁定），但如果以后要复活它，找到那次降级的具体讨论会有用。
- `SpeedRunner`/`SpeedTestScreen` 严格说也不是"真实吞吐"（同为单流），但本提案不touch它——它冻结但完整可用，改它是独立的"吞吐模式"话题（T47 边界），本批不越界。
- 批 B 的诊断行具体排版/文案未定稿，留实现时按 Result 屏既有约定处理，不在设计文档层面预先写死。

---

*证据*：workflow `wf_97748107-eeb`（4 agent 只读调查，journal 存档于会话 transcript）；D-462/D-463（T45 前序裁定）；D-469（s4_throughput 8-5 展示型诊断裁定）；`docs/PROFILE2_THROUGHPUT_PROBE_SPEC.md` §8.0（"单流 goodput 非真实吞吐"术语边界）。
