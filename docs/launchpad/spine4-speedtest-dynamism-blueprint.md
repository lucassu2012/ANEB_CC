<!-- 发射台准备蓝图(launchpad-prep)：2026-07-18 并行工作流产出。
     本文件为设计蓝图，产出时未改任何生产代码/未提交生产代码。
     用途：PO 决策落定 + P40 设备经协议解锁后，据此秒执行。口径红线见正文。 -->

# Spine-4 蓝图：SpeedTest 级测试动态可视化

> 子项目 P1a(UI 壳) + 指标选择 · 横切 Profile。**本文件仅蓝图,不改任何生产代码、不提交。** 蓝图内代码片段为示意,产出是文档。
> 活跃开发树 = `E:/C Project/ANEB`(绝对路径读)。设备当前**异常锁定**(P40,Codex 持有),故全部真机项归入解锁 runbook。

---

## 0. 一句话结论(把洞察钉死)

**SpeedTest 级"动态感"来自会随网络真实波动的指标,不是服务端定速的 token 速率。**

- **网络综合性能模式**:动态主角 = 实时下/上行吞吐(`SpeedRunner` 已建,0.6s 滑窗随网络起伏)。**已跑通,SpeedTest 感天然成立。**
- **Token 模式**:token 流服务端定速(~40tps,稳)→ **速率恒定不体现波动**。逐 token 抖动的**字间时延 ITL / 卡顿(T2/T3)才是波动信号**。这是**指标选择问题,不是 UI bug**,也不能靠让服务端"造波动"来修(那会污染口径)。
- **AI 实时交互(语音)模式**:动态主角 = 帧间抖动 + 口到耳预算;但现 `VoiceRunner` 仅在**相末**算帧抖动,相位内无高频波形(见 §2.3 缺口)。

一句话红线:**波动指标 = 随网络变化的量**。吞吐随带宽变、ITL 随拥塞抖、RTT 随排队变 → 可做动态;token 速率被 pacing 钳住、Token/字节消耗是确定性常数 → **绝不当动态主指标**。

---

## 1. 现状盘点(读码结论)

### 1.1 三模式三条独立数据面(关键:互不共享 telemetry)

| 模式 | profile id | 数据源 | 展示屏 | 采样/刷新 | 动态实现现状 |
|---|---|---|---|---|---|
| Token 体验 | `token_experience` | `engine.telemetry: Flow<LiveTelemetry>` | `HomeScreen` | 采样协程 ~100ms;ITL 窗 40 样本 | 中心大数=**token 速率**(定速→不动);ITL 火花线"流式平滑度"已在(`RunningSparkline`) |
| 网络基本性能 | `basic_network` | `SpeedRunner.Sample` Flow(**不经 LiveTelemetry**) | `SpeedTestScreen` | `delay(100)`(10Hz) + **0.6s 滑窗** | 指针/大数随实时吞吐高频刷新 + 火花线记轨迹。**SpeedTest 感成立** |
| AI 实时交互 | `voice_realtime` | `VoiceRunner.Sample` Flow(不经 LiveTelemetry) | `VoiceTestScreen` | `delay(100)` 但帧抖动**仅相末**算 | 相位内只有帧计数在跳,**无高频波形** |

> 三条数据面各自 collect 到 `MainActivity` 的独立 state(`telemetry` / `speedSample` / `voiceSample`),分别注入各屏。**没有统一的"动态数据面"抽象。**

### 1.2 Profile facet3(`live`)当前只是"描述投影",未真正驱动渲染

- `ModeProfileStrip`(`SpeedTestScreen.kt:362`)读 `profile.live` 只用来渲染**信息条 chip**(标签 + `dynamic` 高亮色),**不把 `source` 字段绑到实时数据**。
- 反证:`basic_network` 的 facet3 声明 `{source:"liveDownMbps", render:GAUGE}`,但 `LiveTelemetry` **没有 `liveDownMbps` 字段**,`SpeedTestScreen` 也**不读 LiveTelemetry**——它直接读 `Sample.downMbps`。即 facet3 的 `source` 目前是**悬空文档字符串**。
- 结论:facet3 号称"动态呈现关键指标单一事实源",但渲染层是**各屏硬编码**,两者未闭环。**这是本 spine 最该补的一致性缺口**(§4 verifiable-now)。

### 1.3 纯逻辑埋在 @Composable 里,当前无法 JVM 单测

以下"纯计算"全部内联在 composable 函数体内,无独立纯函数、无测试:

| 计算 | 位置 | 说明 |
|---|---|---|
| 量程自适应 `gaugeMax` | `SpeedTestScreen.kt:138` | `max(20f, ceil(peak*1.15/10)*10)` |
| 指针分数 `targetFrac` / ping 分数 | `SpeedTestScreen.kt:139-145` | ping:`1-rtt/200` clamp;R-10:null→0 不显"满" |
| 火花线归一 | `SpeedTestScreen.kt:483-493`(`Sparkline`) | `vmax=max(1,max)`,逐点 `1 - v/vmax` |
| 峰值累积 | `SpeedTestScreen.kt:98-112` | `peakUp/peakDown`,每次起测清空 |
| ITL→平滑度映射 | `HomeScreen.kt:384` | `(1 - it/1000).coerceIn(0.05,1.0)` |
| 上行/流式相 gauge 选值 | `HomeScreen.kt:158-178` | 子相位门控选 token 速率 vs 实时上行 |

对照:仓库已有**强抽取先例**——`LiveTelemetry.derive`(`engine/LiveTelemetry.kt:75`,纯函数 + `LiveTelemetryTest`)、`AiScenarioAdvisor.advise`(`ui/AiScenarioAdvisor.kt:51`,纯 + 测)、`TestProgressParser.parse`(HomeScreen 用)。**同款抽取是本 spine 的主线工作。**

### 1.4 高频数据面细节(读 `SpeedRunner`)

- 下行(`run` L147-159)与上行(L181-193):`ArrayDeque<(nanoTime,bytes)>`,`while(now-first>600ms) removeFirst`,`mbps = dB*8/dS/1e6`,`delay(100)`。**窗<2 或 dS≤0.1 → null**(R-10 诚实缺席)。
- **口径纯净度差异(重要)**:下行走 `downloadDrain` "读到即到达字节",滑窗吞吐**真实**;上行滑窗测的是**写 socket buffer 节奏**(≈真实上行,但非 goodput 终点)。整形对照 `runShaped` **故意不用滑窗、改全程均值**——因 1Mbps 整形下 send buffer 一口吞整块,滑窗瞬时窗会虚高到链路裸速(真机实证 36 vs 标称 1 Mbps,见 SpeedRunner.kt:277-281)。
  → **蓝图取舍**:滑窗动态"手感"只对 download-drain 与 paced 路径诚实;上行动态可展示但副文案须标"写入节奏"。
- gauge 动画:`animateFloatAsState(targetFrac, tween(220))`(SpeedTestScreen);HomeScreen gauge `tween(500)` + 弧尖脉冲 `tween(850)`。

---

## 2. 指标选择:per-mode 动态指标清单

### 2.1 判定规则(单一事实源)

一个指标可当"高频动态刷新主角",当且仅当:**(a) 随网络条件变化(非服务端定速/非确定性常数)** 且 **(b) 采样粒度 ≤1s 可得中间值**。否则归"稳态结论指标"(只在收尾给一次判定)。

### 2.2 清单(建议值;标注需 PO 拍板处)

| 模式 | 动态/高频(主角) | 渲染 | 稳态结论(收尾一次) | 说明 |
|---|---|---|---|---|
| **basic_network** | 下行吞吐 `Sample.downMbps`、上行吞吐 `upMbps`、RTT `rttMs` | 表盘指针 + 火花线 / 波形 | 抖动 `jitterMs`、下/上行峰值、UDP 未返回率、请求失败率、AI 场景适配 | **现状即对**:三 dynamic=true 与洞察一致 |
| **token_experience** | **ITL `itlRecentMs`(T2)**、卡顿计数(T3,滚动)、实时上行(上传相 `liveUpMbps`) | 火花线/抖动带 为主 | TTFT(T1)、AQS 分、TPS 达成率、会话完成率 | **建议改口**:见下 ⚠ |
| **voice_realtime** | 帧间抖动 `frameJitterMs`、口到耳预算(滚动)、RTT | 波形 + running number | 帧接收总数、M4/M5/M6、语音分 | 相位内高频尚缺(§2.3) |

⚠ **token 模式的 profile 数据现状 vs 建议(需 PO)**:
- 现状 `metrics`:`Token 速率 dynamic=true`、`ITL dynamic=true`、`TTFT dynamic=false`、`卡顿 dynamic=false`;`live` 里 `tps` 用 `RUNNING_NUMBER`。
- **问题**:把"Token 速率"标 dynamic=true 是**误导性动态提示**——它定速不动,用户看它"卡住"。
- **建议**:`Token 速率 dynamic=true→false`(降为稳态读数,仍显但不作波动主角);`卡顿 dynamic=false→true`(滚动卡顿计数是真波动);`live.tps` 保留但从"波动主角"降级,**ITL 波形上位为中心动态**。
- **代价**:改 `metrics.dynamic` 与 `live` = 动 profile **三处数据**(`spec/profiles/client/client_profiles.json`、`app/probe/src/main/assets/spec_profiles/client_profiles.json`、`TestModeProfile.kt` 的 `FALLBACK_TOKEN_EXPERIENCE`)**须字节级同步**,`ClientProfileDataParityTest` 会守护(改一处漏两处即红)。**属口径/产品决策 → PO 阻。**

### 2.3 缺口:语音相位内无高频波动

`VoiceRunner.run`(VoiceRunner.kt:191)与 `runSim`:帧抖动 `upJitter/downJitter` 由 `frameJitterP95Ms` 在**相末 job 完成后**算(L226-227、L250-252),相位内 `Sample` 只更新 `framesSent/framesRecv` 计数。故 `voice_realtime` 的 facet3 `{source:"voice.frameJitterMs", render:WAVEFORM}` **相位内无数据可喂**。
- **下行波形**:可纯客户端实现——`client.stream` 的 `onToken(n,_)` 现只回计数,需扩为回**最近到达间隔**(arrivalNanos 差),即可在相位内驱动波形(**我方 P1b,设备阻仅限手感验证**)。
- **上行波形**:`chunk_us` 是服务端相末全量透出,相位内增量需服务端逐帧回执(**Codex/服务端阻**);替代=用客户端发送调度间隔做 proxy 并标注。

---

## 3. 高频刷新数据面:够不够 + 哪些可 JVM 测

### 3.1 现有采样窗够不够"SpeedTest 感"

- basic_network:**10Hz 轮询 + 0.6s 滑窗 + 220ms tween**。对照商用 SpeedTest(多为 ~200–500ms 刷新)——**现档已够,甚至更快**。是否再提频属**手感调参(设备阻 + PO 门限)**,不建议盲目提到 60Hz(0.6s 滑窗会把高频抹平,提轮询频率无收益)。
- token:ITL 波形窗 40 样本、facet3 声明 2000ms 窗/200ms 刷新。40 样本 ≈ 40 token,40tps 下约 1s——**够体现逐 token 抖动**。D-27/D-28 已修"流内不出中途数据"根因(atomic 在途计数)。
- **建议参数(需 PO 确认为验收门限)**:滑窗 0.6s(吞吐)、200ms 刷新(波形)、tween 200–250ms;token ITL 波形保留 40 窗。

### 3.2 纯逻辑(可无设备 JVM 测)的边界

**可 JVM 测(纯计算,无 Android/无网络)**:
- 滑窗吞吐:给定 `(nanoTime,bytes)` 序列 → 期望 Mbps;窗口 600ms 淘汰;窗<2/dS≤0.1→null。
- 峰值累积(单调不减,起测清零)。
- `gaugeMax` 量程自适应、`gaugeFraction` clamp、ping 分数(null→0)。
- 火花线归一(vmax 归一;ITL `1-it/1000` clamp 0.05..1;<2 点→空)。
- `frameJitterP95Ms`(已纯,VoiceRunner.kt:174,但测在别处)、`mouthEarBudgetMs`(已纯,L185)。
- **动态指标选择**:给定 mode + facet3 → 动态指标集与渲染类型。

**不可 JVM 测(必须真机,属"手感")**:
- 指针/波形在真实网络下"看着流畅、有起伏"。
- 刷新是否被主线程卡顿/GC 打断。
- 弱网(RSRP/SINR 变化)下吞吐/ITL 的**真实**波动幅度(软件不能伪造无线层,见 weaknet 备忘)。
- 减弱动效(`LocalReducedMotion`)降级是否仍传达信息。

---

## 4. 实现蓝图:file:函数 改动清单(每项标注阻塞态)

> 状态图例:🟢现在可验证(锁无关) · 🟠被设备阻 · 🔵被 PO 阻 · 🟣被 Codex 阻

### 4.1 抽取纯逻辑(新建文件,不动现有渲染语义)

**新建 `engine/SpeedSampleMath.kt`** 🟢
```kotlin
object SpeedSampleMath {
    /** 0.6s 滑窗吞吐(Mbps);窗<2 或 dS≤0.1 → null(R-10)。纯:输入 (nanoTime,bytes) 队列。 */
    fun windowMbps(window: List<Pair<Long, Long>>, nowNs: Long, nowBytes: Long, windowNs: Long = 600_000_000L): Double?
    /** 峰值单调累积。 */ fun peak(prev: Float, sample: Float?): Float
    fun median(xs: List<Double>): Double?     // 迁移 SpeedRunner 私有
    fun jitter(xs: List<Double>): Double?      // 迁移 SpeedRunner 私有
}
```
- 落地:`SpeedRunner.run/runShaped` 的滑窗块(L147-159/181-193/262-274/302-310)改调用它;`median/jitter`(L315-325)迁入。**行为零变**,只为可测。

**新建 `ui/GaugeMath.kt`** 🟢
```kotlin
object GaugeMath {
    fun autoGaugeMax(peak: Float, min: Float = 20f, roundTo: Float = 10f): Float
    fun gaugeFraction(value: Double?, gaugeMax: Float): Float          // clamp 0..1;null→0
    fun pingFraction(rttMs: Double?, fullAtMs: Float = 200f): Float    // null→0(R-10)
    fun sparklineNormalize(values: List<Float>): List<Float>          // vmax 归一;<2→空
    fun itlToSmoothness(itlMs: Double, ceilingMs: Double = 1000.0): Float // 1-it/ceil clamp 0.05..1
}
```
- 落地:`SpeedGauge`/`Sparkline`/`targetFrac`(SpeedTestScreen)与 `RunningSparkline`(HomeScreen L384)改调用。**composable 只保留绘制,数值全走纯函数。**

### 4.2 facet3 真正成为动态渲染单一事实源

**新建 `ui/DynamicMetricSelection.kt`** 🟢(纯逻辑) / 🟠(接线手感)
```kotlin
object DynamicMetricSelection {
    data class Dyn(val id: String, val label: String, val source: String, val render: LiveRender)
    /** 从 profile.live 取动态指标(单一事实源);过滤出当前相位适用者。 */
    fun dynamicMetrics(profile: TestModeProfile): List<Dyn>
    /** 校验:每个 live.source 必须能解析到已知遥测/Sample 字段。 */
    fun resolveSource(source: String): FieldRef?   // 未知→null(测试据此揪悬空 source)
}
```
- 用途:`ModeProfileStrip` 高亮仍数据驱动;新增"source 可解析"闸门修 `liveDownMbps` 悬空问题(要么给 basic_network live 换成 `Sample.downMbps` 语义源,要么在 `LiveTelemetry` 补 `liveDownMbps` 并让 SpeedTest 供值——**建议前者,不硬塞 telemetry**)。
- 接线到真实渲染(让 SpeedTestScreen/HomeScreen 按 facet3 决定画哪个波形)属 UI 行为改动 → 🟠(手感需设备验)。

### 4.3 profile 数据口径调整(token 动态指标)🔵

- 改 `metrics[Token 速率].dynamic true→false`、`metrics[卡顿].dynamic false→true`,并同步 `live` 主次;**三文件字节级同步**(spec / assets / `FALLBACK_TOKEN_EXPERIENCE`)。
- 门禁:`ClientProfileDataParityTest`(三份对拍 + 字节一致 + 顺序钉死)。**PO 拍板后一次性改,勿分批。**

### 4.4 语音相位内高频波形

- `client.stream` 回调扩最近到达间隔 → `VoiceRunner.run` 相位内 emit 下行帧抖动波形。**下行 🟠(我方可实现,手感设备阻);上行 🟣(需服务端逐帧 chunk_us 增量)。**

---

## 5. 测试脚手架(测什么 + 无设备 JVM 锚定)

> 全部纯 JVM(`src/test`,JUnit4,同 `LiveTelemetryTest` 惯例),不触 Android/网络/设备。

| 新增测试 | 断言要点 | 状态 |
|---|---|---|
| `engine/SpeedSampleMathTest` | 合成 `(t,bytes)` 序列 → 已知 Mbps;600ms 窗淘汰;窗<2/dS≤0.1→**null 不折 0**;peak 单调、起测清零 | 🟢 |
| `ui/GaugeMathTest` | `autoGaugeMax` 取整到 10、下限 20;`gaugeFraction` clamp;`pingFraction(null)=0`(R-10);`sparklineNormalize(<2)=空` | 🟢 |
| `ui/SparklineItlTest` | `itlToSmoothness(1000)=0.05` 封底、`(0)=1`;单调递减 | 🟢 |
| `ui/DynamicMetricSelectionTest` | 每 mode facet3→期望动态集 & render;basic=下/上/RTT,token=ITL/卡顿(PO 定稿后),voice=帧抖动/口到耳/RTT | 🟢 |
| `ui/Facet3SourceResolvableTest` | **每个 `live.source` 必解析到真实字段**——现会因 `liveDownMbps` 悬空而红,倒逼 §4.2 修复 | 🟢 |
| 扩 `TestModeProfileContractTest` | `metrics.dynamic` 集合 == facet3 `live` 动态集(单一事实源一致性) | 🟢 |
| `ui/DynamismVisibilityGoldenTest` | **把洞察编码为断言**:喂"随机起伏吞吐序列"→ `gaugeFraction` 序列方差 > 阈值;喂"定速 token 速率序列(40±0.5)"→ 方差 ≈ 0。证明"吞吐可做动态、token 速率不可" | 🟢 |
| 回归门禁 | 抽取后既有 3 场景 AQS 子分/总分**零回归**(基线 362 run 快照);`ClientProfileDataParityTest` 绿 | 🟢 |

金样本来源(无设备):合成序列 + 从历史落库(`SyntheticResultEntity`/`VoiceResultEntity`/token event)导出的**真实采样重放**,喂纯函数比对。

---

## 6. 解锁后 runbook(设备/PO 解锁后跑的确切步骤)

### 6.1 前置(严格按 CLAUDE.md 共享协议)

1. 读 `E:\G Project\ANEB\SHARED_TEST_STATUS.md`;当前 = **异常锁定**(Codex 持 lease `21abc40c…`)。**不得操作,直到状态回 `空闲`。**
2. 状态 `空闲` 后,由执行者本人置 `进行中`(填执行者/任务/资源/开始时间),**不得让 PO 改状态**。
3. 测毕置 `待交接`;清理(退 App、停 VPN/抓包、清临时规则)后由另一角色独立复核方可 `空闲`。

### 6.2 真机验证步骤(手感 = 只能真机)

```
# 装包
adb install -r app/probe/build/outputs/apk/debug/app-probe-debug.apk
# 起 App(SpeedTest/Voice 由 UI 分段切,非 autorun intent)
adb shell am start -n com.aneb.probe/.ui.MainActivity --es server https://120-79-148-0.sslip.io:8443
```
1. 切"网络基本性能"分段 → GO;录屏观察:指针/大数**随网络起伏高频刷新**、火花线记轨迹、下→上行相切换配色。
2. 切"Token 体验" → GO;**核心洞察真机核验**:ITL"流式平滑度"火花线**在动**,而 token 速率大数**基本不动**——证实指标选择正确。
3. 弱网对照:用内置 `weaknet contend:N` debug 开关(D-36 背景流)制造真实拥塞,重复 1/2,确认吞吐/ITL 波动幅度**放大**;再点 SpeedTestScreen 的"弱网对照"(合成整形卡)并排看。
4. 语音模式 GO;若已接 §4.4 下行波形,核验相位内帧抖动波形随网络动。
5. 减弱动效(系统开关)下重跑,确认降级为静态终态仍可读。

### 6.3 每场景一条结论的验收清单(三品类 × 四要素)

对每模式产出**一行结论**(对齐"每个场景一个结论"):

- basic_network:`下行峰值 X / 上行峰值 Y Mbps · RTT Z ms · 抖动 W ms → 优良/尚可/偏弱 + AI 场景适配(TK-1..6 ✓/✗)`
- token_experience:`ITL 中位 X ms · 卡顿 N 次 · TTFT Y ms · AQS 分 S(级) → 流畅/可感顿挫/受损`
- voice_realtime:`口到耳 X ms · 帧抖动 Y ms · RTT Z ms · 语音分 S → 优/良/可/差(M1 红线是否触发)`

验收门(需 PO 在 6 前定死数值):目标刷新率、"波动可见"最小幅度、tween 时长、token 是否以 ITL 为中心动态。

---

## 7. 落地顺序(锁无关先行)

1. **§4.1 抽取纯函数 + §5 全部 🟢 测试**(含 `DynamismVisibilityGoldenTest`、`Facet3SourceResolvableTest`)——现在就做,行为零变、可回归。
2. **§4.2 facet3 source 一致性修复**(补 `resolveSource` 闸门,修 `liveDownMbps` 悬空)——锁无关。
3. **等 PO**:§2.2⚠ + §4.3 token 动态口径改口(三文件同步 + 对拍);§6.3 验收门限数值。
4. **等设备**:§6 真机手感 runbook;§4.2 渲染接线的手感验证。
5. **等 Codex**:§4.4 上行相位内帧抖动增量(服务端逐帧 chunk_us);§3.2 若 PO 仍想让 token 速率"动"——但**口径结论不变:token 波动主指标恒为 ITL**。

---

## 附:关键文件锚点

- `app/probe/src/main/java/com/aneb/probe/ui/SpeedTestScreen.kt` — `SpeedTestScreen`(L63)、`targetFrac/gaugeMax`(L127-146)、`Sparkline`(L479)、`SpeedGauge`(L441)、`ModeProfileStrip`(L362)。
- `.../ui/HomeScreen.kt` — gauge 选值(L158-178)、`RunningGauge`(L302)、`RunningSparkline`(L381)、`LiveMetricsRow`(L416)。
- `.../ui/VoiceTestScreen.kt` — hero(L69)、`VoiceTile`(L157)。
- `.../engine/SpeedRunner.kt` — `run` 滑窗(L147-159/181-193)、`runShaped` 全程均值(L277-310)、`Sample`(L48)、`median/jitter`(L315-325)。
- `.../engine/LiveTelemetry.kt` — `derive`(L75)、`ITL_WINDOW=40`/`LIVE_STALL_MS=500`(L62-65)。
- `.../engine/VoiceRunner.kt` — `frameJitterP95Ms`(L174)、`mouthEarBudgetMs`(L185)、`run`(L191)。
- `.../ui/TestModeProfile.kt` — `ModeMetric.dynamic`(L56)、`LiveMetric`(L144)、`FALLBACK_*`。
- 数据三件套:`spec/profiles/client/client_profiles.json` ↔ `app/probe/src/main/assets/spec_profiles/client_profiles.json` ↔ `TestModeProfile.kt` FALLBACK;守护 `app/probe/src/test/.../ui/ClientProfileDataParityTest.kt`、`TestModeProfileContractTest.kt`。
- 抽取先例:`LiveTelemetry.derive`+`LiveTelemetryTest`、`AiScenarioAdvisor`(L51)。
