# T50：语音首采操作协议一页（2026-08-04）

> 一页协议，供大脑/操作者按序执行。**设备窗排在 T49 之后**（设备串行，大脑协调）；
> 本文件只准备、不碰设备。数据归 v3（本文件作者）首判。
> 依据来源：`AndroidManifest.xml`、`VoiceRunner.kt`、`MainActivity.kt`、
> `VoiceTestScreen.kt`、`Entities.kt`、`AqsScorer.kt`、`docs/M7_ANCHOR_RECALIBRATION_PLAN.md`
> 源码/文档通读（workflow `wf_db2f70b1-fdb`，四路独立研究），逐条标文件:行号。

---

## ① 前提核查清单

### A. RECORD_AUDIO 权限——不存在，不会弹窗，这是最重要的一条前提

**`AndroidManifest.xml:8-15` 声明的权限全集里没有 `RECORD_AUDIO`**（debug 变体
manifest 也未追加）。全仓 `grep -riE "AudioRecord|MediaRecorder|AudioManager"` 零
命中——**语音测试从设计上不摸麦克风**，上行"帧"是按 Opus 帧节奏（20ms）造的定长
合成字节（`VoiceRunner.kt:347,575`），测的是"语音级流量的网络承载能力"，不是真实
语音链路。`docs/PROFILE4_VOICE_LOOPBACK_SPEC.md:33-50` 已把这一点升格为契约。

**核查动作**（预期全部返回"未找到该权限"，不是"denied"）：
```bash
adb shell dumpsys package com.aneb.probe | grep -A2 "RECORD_AUDIO"
adb shell dumpsys package com.aneb.probe | grep -A20 "runtime permissions:"
adb shell appops get com.aneb.probe RECORD_AUDIO
```
**⚠ 若这三条命令中任意一条真的报出 `RECORD_AUDIO`**：设备装的 APK 与本次核实的
源码不一致，优先怀疑旧签名包/临时分支构建，停止采集先核实构建来源，不要按本协议
继续执行。

**给操作者的告知**：本测试**不会**弹出麦克风权限对话框，看到测量直接开始即为
正常——不要因为"没弹权限窗"误以为 App 卡住而反复重启。

### B. VoiceTestScreen 入口路径

无 NavHost，是数据驱动的分段开关（`MainActivity.kt:611-628`、`SpeedTestScreen.kt:329-354`）。
完整点击序列：

1. 底栏 3-tab「测试」（App 默认落地 tab，`MainActivity.kt:188`）。
2. 顶部分段开关三选一，点第三段**「AI 实时交互」**（`TestModeProfiles.ALL` 第三项，
   `TestModeProfile.kt:610-611`；显示名见 `client_profiles.json:374-376`）——
   `selectedModeId` 变为 `voice_realtime`，渲染出 `VoiceTestScreen`。
3. 页面内点大按钮**「GO · 开始语音测量」**（`VoiceTestScreen.kt:140-141` →
   `startVoiceTest()`，`MainActivity.kt:455-511`）。

`VoiceTestScreen` 与 s1/s2/s3 场景体系（`TestEngine`/`QUICK`/`FORENSIC`）**完全独立**，
走自己的 `VoiceRunner` 引擎（`MainActivity.kt:90/140`），不进 v0.1/v0.2/Token AQS
主分（`VoiceRunner.kt:29-30` KDoc 原话）。

### C. 链路自检——不是看有没有权限弹窗，是看 `caliber` 字段

`startVoiceTest()` **总是优先尝试 v2 server-sim 口径**（`voiceRunner.runSim()`，
`MainActivity.kt:464`），**任何异常**（不限于协议/网络失败，`catch (e: Exception)`）
都会**静默降级**为 v1 paced-proxy 口径（`:465-472`），只在内部日志打一行
`VOICE_SIM_FAILED fallback=paced-proxy error=$e`（:469），仪表盘数值本身看不出降级
发生过。

> **⚠ 唯一真实风险点**：若不核对 `caliber` 字段（真正打印字面值 `"server-sim"`/
> `"paced-proxy"` 的是 `VoiceTestScreen.kt:291-295` 最近记录列表；`:386-391` 是
> 另一处按 caliber 分支显示不同"帧接收"文案的地方，不打印 caliber 原文，见③节），
> 很容易把降级跑出的 v1 数据当成 v2 数据去对比历史基线——两套口径 KPI 公式与
> 权重表不同（v1 权重 M7=0.10，v2 权重 M7=0.05，`AqsScorer.kt:187,206`），不能
> 混用。**采集时每一轮都要记这个字段，不能只看分数。**

`docs/PROFILE4_VOICE_LOOPBACK_SPEC.md:471-484` 记录 v2 依赖的 `/realtime-sim` 端点
（Codex 树 `server/handlers_realtime_sim.go`，本树无法构建/部署）曾在 2026-08-01
未能独立核实是否在线（文档自述这是量法本身够不到，不能当作服务端下线的证据）。**本协议
不新造端点探活方式**——直接用第②节的首轮 dry-run 结果自证：第一轮跑完看
`caliber`，若是 `server-sim` 说明端点当前可达，若是 `paced-proxy` 说明当前不可达
或有其他异常，此时不要继续按"v2 首批"的预期推进剩余轮次，先如实记录再决定是否
继续（按 v1 口径登记也是合法的登记级数据，不必等端点修复）。

---

## ② 命令/操作序列

**不是统计判据，是操作性首批规模**——`M7_ANCHOR_RECALIBRATION_PLAN.md` §1（`:25-59`）
把语音 M7 明确分三档：**登记级**（任意一次真实会话即算，无门槛）/回核级（≥30 次、
覆盖≥2 种网络条件）/改锚级（回核级+报告+复核批准）。本批"5-10 次"对应登记级，
本身无最小 n 要求；5-10 这个数字是比照同批派单 T49"5-10 run"首批探索性采集惯例
（`docs/BRAIN_TASKBOARD.md:60`）定的操作性规模，不是套用任何 n≥X 统计公式。

**单次时长**（代码常量/注释口径，**v2 是推算值非实测**——M7 预案写作时全仓零
语音语料，本节数字只供排窗口用）：
- v1 `run()`：Ping~1s + Uplink~4s + Downlink~4s ≈ **9 秒/次**（`VoiceRunner.kt:220,234,253`
  注释自带估算）。
- v2 `runSim()`：Ping~1s + Uplink(M3 段)3s + Handshake+8 轮对话~28s ≈ **32-35 秒/次**
  （按 `VoiceRunner.kt:84-134` 帧数×20ms 帧间隔推算）。
- **`/realtime-sim` 已部署、正常情况下 5-10 次实际跑的都是 v2 路径**（v1 只是
  fail-closed 兜底，不是常规路径）——**按 v2 时长估算，不要按 v1 的 9 秒估算**。

**操作序列**（每轮重复①②③）：
```bash
# 每轮开始前清空 logcat，方便区分本轮判词
adb logcat -c
```
① 操作者按第①节 B 的点击序列进入并点击「GO」。
② 等待本轮结束（预期 30-40 秒，若明显更快，大概率降级成了 v1，见下方③核对）。
③ 立即核对本轮判词：
```bash
adb logcat -s AnebProbe:I | grep VOICE
```
（TAG 固定 `AnebProbe`，全 App 共用非语音专属；语音相关行只有 4 种，见④）

**首批预算**：5×30s ≈ 2.5 分钟 至 10×40s ≈ 6.7 分钟的纯测量时间，加操作者查看/
记录间隔（仿 T37 惯例每次+30秒-1分钟），**总占用设备时间大致 5-15 分钟量级**（推算，
非实测基准）。

---

## ③ 产物与判读入口

**落库确定，上报确定没有**：M7/近零占比两字段落在 `voice_result` 表
（`VoiceResultEntity`，`Entities.kt:449-508`）——`m7MaxFrameGapMs`（:496）/
`voiceNearZeroArrivalRatio`（:507），均为可空 `Double`，默认 `null`＝"该 run 跑在
M7 落地之前"（不是"没有静默"）。`MainActivity.kt:475-502` 落库，两字段行
`:496-497`。**`ResultReporter.kt` 全文 grep 这两个字段零命中**——它们不会进入任何
服务端上报 JSON、不会出现在 `campaign_report`/CSV 分析层（`scripts/` 全文 grep 同样
零命中），只存在设备本地 Room 数据库。

**设备上唯一能看到 M7 的入口**：跑完当轮，`VoiceConclusionCard`"子分"小字行
（`VoiceTestScreen.kt:378-384`），格式形如 `M7 40（表 …_v02 · aqs-voice-v0.2）`——
**这是锚点映射后的 0-100 分**（`AqsScorer.kt:307` 锚点表 `0ms→100分,60ms→85分,
150ms→70分,400ms→40分,1000ms→0分`），**不是原始最长静默毫秒数**，且**只在刚跑完
那一屏可见，历史页翻不到**（`HistoryScreen.kt:91-92` 注释：语音行只展示落库实测值、
无详情页不可点击）。
`voiceNearZeroArrivalRatio` **完全没有 UI 消费方**（`VoiceTestScreen.kt` 全文件零
命中）——纯落库字段，若需要该值只能 `adb` 拉 Room 数据库文件直接查（拉库前参照
CLAUDE.md 的 P40 流程做完只读检查，拉 `-wal`/`-shm` 一并带走）。

**`KPI_MISSING:M7` 判读口径（本节最该记住的一句）**：等价于"这轮下行有效到达
帧数<2，算不出一个相邻帧间隔"＝**没采到**，**不是**"采到了但数值异常"——依据
`VoiceRunner.kt:201-202` 的 `maxFrameGapMs` 只在 `intervalsUs` 为空时返回 `null`；
只要有≥2 帧到达，哪怕测出的最长静默是几秒钟的极端值，也会被如实带回并映射成低分
（不是缺失）。若看到这个判词，去查同屏以"帧接收"开头的诊断行（`VoiceTestScreen.kt:385-389`，
按 `caliber` 分支显示不同文案：**v1/paced-proxy 分支**是"帧接收 X/Y"斜线格式（分母为
常量 200）；**v2/server-sim 分支**（本批实际会跑的路径，见①C）是"帧接收 X · Y 轮
protocol_ok"，**没有斜线格式**）——不要死等"X/Y"这种格式，两种口径都看"帧接收"这个
前缀，接收数过低（个位数）才是根因。

---

## ④ 中止判据表（别在设备旁边猜）

| 观察到的形状 | 含义 | 处置 |
|---|---|---|
| logcat 出现 `VOICE_SIM_FAILED fallback=paced-proxy error=...` | v2 `/realtime-sim` 端点当前不可达或协议异常，本轮自动降级为 v1 口径 | 如实记录**本轮**口径为 `paced-proxy`，不当 v2 数据用；若连续多轮都降级，暂停剩余轮次，按第①节 C 的判断先如实登记再决定是否继续，不必强求凑够 5-10 次 v2 数据 |
| logcat 最终只见 `VOICE_FAILED error=...`，没有 `VOICE_SAVED` | v1 兜底后仍失败（连接/协议层错误），本轮**无数据写入** `voice_result` | 记下 `error` 具体内容；这不是权限问题（本 App 不申请、也不会因权限失败——见①A），优先怀疑网络连通性 |
| `VOICE_SAVED` 出现，但结果卡片显示"语音分不可计算（`KPI_MISSING:M7`）" | 有数据落库，但下行有效到达帧数<2——按③的判读口径，是**没采到**不是**异常值** | 查同屏"帧接收"诊断行确认是否下行帧大量丢失（v1 显示"X/Y"、v2 显示"X · Y轮 protocol_ok"，见③）；持续出现则怀疑链路/服务端下行侧，不是设备侧操作问题 |
| 设备弹出麦克风权限请求对话框 | **不应该发生**——当前代码从未声明/请求该权限 | 停止采集，核实设备上 APK 的构建来源与当前源码是否一致，重新走①A 核查，不要继续按本协议执行 |
| 5-10 轮里 `caliber` 反复在 `server-sim`/`paced-proxy` 间切换 | `/realtime-sim` 端点时通时不通 | 如实记录**每一轮各自的** `caliber`，不要汇总平均（登记级本身就该如实记录这种波动，不是缺陷） |

---

## ⑤ UI 自动化触达（T52/D-485 补充，2026-08-05，v2 附录，不改上文判断）

**背景**：大脑代执行本协议时，②步骤 3 的「GO · 开始语音测量」按钮三次点击零反馈，
判 NOT_EXECUTED 收窗（D-485）。查因**大概率点错了对象**——共享底栏"测试" tab 圆钮
（外观也是圆形+三角形图标）与 `VoiceTestScreen.kt` 内真正的「GO · 开始语音测量」
矩形按钮长得都像"开始"，但**前者只切 tab、不启动任何测量**，且 Compose 默认不给
纯图标按钮任何 uiautomator 可读的 text/content-desc（"Compose 惯例"，D-485 原话），
两个问题叠加导致自动化路径实质不可靠。

**已修复**（T52/D-484 后续，代码侧）：`MainActivity.kt` 根节点开启
`testTagsAsResourceId`，为下列关键按钮补 `contentDescription`+`testTag`：

| 按钮 | testTag（映射为 resource-id） | contentDescription |
|---|---|---|
| 语音真正的开始按钮 | `voice_go_button` | "GO 开始语音测量" / "取消语音测量" |
| 共享底栏"测试" tab 圆钮（**不是**测量开始按钮） | `tab_bar_go_button` | "切换到测试标签页（不启动测量）" |
| Token 模式开始按钮 | `token_go_button` | "GO 开始 Token 体验测量" |
| 网络基本性能模式开始按钮 | `basic_network_go_button` | "GO 开始网络基本性能测速" |

**adb 侧定位+点击三行法**（替代裸坐标 `input tap x y`，坐标随布局/机型/滚动位置漂移，
resource-id 不会）：

```bash
adb shell uiautomator dump /sdcard/ui.xml && adb pull /sdcard/ui.xml .
# 在 dump 里搜 resource-id="voice_go_button"（或对应 tag），读它的 bounds="[x1,y1][x2,y2]"
adb shell input tap $(( (x1+x2)/2 )) $(( (y1+y2)/2 ))   # 取中心点，而非猜坐标
```

**未解决的边界**：`VoiceTestScreen` 用 `Modifier.verticalScroll` 而非 `LazyColumn`，
语音真正的 GO 按钮**理论上**始终在语义树里（不会像 LazyColumn 那样因未渲染而缺席），
但若它在当前视口外，dump 出的 `bounds` 会落在屏幕物理尺寸之外——此时须先按 bounds
估算滚动距离、`input swipe` 滚到位，再 tap；直接对越界坐标 tap 会落空。**本次未在
真机验证这条边界路径**（见 D 号常规验证只测了当前视口内点击），下次若仍零反馈，
优先检查 dump 出的 bounds 是否越界，而不是重新怀疑权限/协议前提（①②节的核查
结论不受本节影响）。

**⚠ 实测教训（D-487，正式首采窗 5/5 才发现）：每一轮都要重新 dump，坐标不可跨轮
复用**——`voice_go_button` 的 `resource-id` 本身不变，但页面结果区随上一轮渲染出
的仪表/子分内容改变了滚动位置，同一个 resource-id 在不同轮次对应的屏幕坐标
（`bounds`）会不一样。D-487 实测因为复用了第一轮 dump 出的坐标，浪费了 4 轮空点
（无 logcat 反馈、无仪表变化）才意识到问题。**正确做法**：把第②节"操作序列"里的
每一轮，都在点击前重新执行一次 dump+定位（上文"adb 侧定位+点击三行法"的完整三行，
不能只在首轮做一次、后续轮次复用同一坐标）。

**选项 (c) 核实结果**：`MainActivity.kt` 现有 intent extra `mode` 已被
`quick`/`forensic`/`continuity`/`ab` 占用（`:152-162`，测量深度/特殊 runner 选择），
**不是**顶层 UI 模式选择器（token/basic_network/voice_realtime 由独立的
`selectedModeId` composable 状态承载，`:578-628`），**当前不支持** `--es mode voice`
这个具体写法。`intentAutorun` 的 `LaunchedEffect(Unit)`（`:538-543`）目前只分发
`ab`/`continuity` 两个特殊 runner，未接 `startVoiceTest()`。若要做 intent 直驱语音，
需要新增一个不与 `mode` 冲突的 extra（如 `--es ui_mode voice_realtime`）并扩展该
`LaunchedEffect`——**本次未实现**，工作量与本节其余改动相当（数十行），如需要另开
一项，不在本次"小改动"范围内擅自扩大。

*本节证据*：`MainActivity.kt`/`VoiceTestScreen.kt`/`SpeedTestScreen.kt`/`HomeScreen.kt`/
`SpeedTestComponents.kt` 源码通读+真机 uiautomator 验证（见 D 号）；D-485（触发缘由）。

---
*T50 · v3 · 2026-08-04 · 依据=workflow `wf_db2f70b1-fdb`（四路独立研究：权限/入口、
VoiceRunner 机制与链路信号、落库与 M7 消费路径、M7 预案与规模依据）+
`AndroidManifest.xml`/`VoiceRunner.kt`/`MainActivity.kt`/`VoiceTestScreen.kt`/
`Entities.kt`/`AqsScorer.kt`/`docs/M7_ANCHOR_RECALIBRATION_PLAN.md` 源码/文档通读*
