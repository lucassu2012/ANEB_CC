# 测前省电态判据设计（D-534 §4 解冻件，先数后建；v4，2026-08-22）

> **单源**：大脑 08-22 铃「设计省电模式/Doze 前置检查该不该进 NetGuard 三态门——
> 注意 D-502 评审已论证**测中** POWER_SAVE 直通 invalidate，这里问的是**测前**静态检查」。
> 本文=设计供裁，三案一荐；「数」的部分已全部实测，「建」的部分只落了
> **无需裁定的那半**（修一个既有实现从未兑现其注释意图的竞态，见 §2）。

## 1. 先数：测前省电态今天处于什么状态（五条全实测）

| # | 事实 | 出处 |
|---|---|---|
| 1 | **测中判据健在**：POWER_SAVE/DOZE 变化 → `invalidate("power_state_changed:…")`，initial 刻意豁免 | `TestEngine`（§4.6 注释） |
| 2 | **测中判据全语料零触发**：`power_state_changed` 在全部 JSONL 零命中 | grep 全 evidence |
| 3 | **测前状态设计上有采集**（`EnvMonitors.start()` 发三条 initial 事件，注释明言「初始状态显式入时间轴，区分无事件与未监控」），**实现上从未兑现**——replay=0 的 SharedFlow 在零订阅者时事件消失，而 TestEngine 先 start 后挂 collect | 见 §2 竞态实证 |
| 4 | **wire 上零 env 字段**：`env_event` 只落 Room，schema 内 env 零命中——即使修好 initial，**分析层仍看不到**测前省电态 | `result-run.schema.json` |
| 5 | **NetGuard 测前门只查 VPN/代理**（R-03 两族四条判据），不查电源态 | `NetGuard.guardCheck` |

**竞态实证（表中 #3）**：voice30 库 19 run 的 `env_event`——非 initial 事件 **9243 条**
（APP_JANK 9229 / THERMAL 5 / PATH·CELL·RAT_CHANGE 14，链路完全通畅），
**initial 全类 = 0**。写下的意图没有守卫，随启动时序静默漂移（D-267 形状）。
连带后果：**历史语料里每个 run 的测前电源态都不可知**——本文任何「发生率」都无从数起，
这本身就是修竞态的理由。

## 2. 已落的半件（无需裁定：修既有意图，非新判据）

`EnvMonitors._events` 加 `replay = 4`（每 run 新建实例，无跨 run 泄漏；调换 start/collect
顺序不可靠——launch 的订阅挂载是异步的，调序只是把窗口变小不是关掉）。
配 `EnvMonitorsInitialReplayTest`（刻意复现 TestEngine 的先 start 后订阅时序；
突变 replay→0 实测变红）。`TestEngine` 的 initial 豁免此前从未真正被用到，现在起
initial 事件到达 collect 但**不触发 invalidate**（豁免正是为此写的）。
效果：从此每个 run 的 `env_event` 表都带三条 initial 行——**测前电源态从不可知变为已归档**。

## 3. 建：三案供裁

| 案 | 内容 | 代价 | 判断 |
|---|---|---|---|
| A｜不进门 | 维持 §2 修复即止；测前电源态只活在 Room `env_event` | 零 | 分析层仍盲——JSONL 是分析层唯一输入（T60① 定性），Room 侧信号它永远读不到；「写了没人读」是本仓最反复点名的形状（D-330/D-340） |
| **B｜进 metadata 态（荐）** | `guardCheck` 读 `isPowerSaveMode`/`isDeviceIdleMode` 写进 **metadata KV**（不进 reasons、不拒测）→ 随既有 `guard_metadata` 字段上 wire | **零 schema 变更**（`guard_metadata` 本就在契约且已上 wire）；App 侧约 4 行 + 测试 | **标记非否决**，照 D-506 墙钟先例：省电态影响的是「测量环境质量」不是「测量有效性」——数据仍是真实测量，该标记不该丢弃 |
| C｜进 reasons 态（拒测） | 省电/Doze 时 `guardCheck` 拒测 | 同 B 的改动量 | **过重且方向危险**：弱网外场（电池供电、无充电条件）正是最需要测的场景，拒测=系统性删掉低电环境的样本——**这是对分母的选择性偏倚**，比带标记的样本更伤结论；且 R-12 测中直通 invalidate 管的是「状态**变化**破坏一致性」，全程处于省电是**稳定环境**，两者语义不同 |

**推荐 B**。补充两点边界：

- B 的 metadata 键建议 `power_save=true|false`、`device_idle=true|false`——布尔实值，
  不做「suspect」之类的判词（判词留给分析层；生产端只给事实）。
- 分析层消费方（谁读 `guard_metadata` 里的这两个键）**另单**：guard_metadata 现状是
  自由 KV 串、分析层零读者（D-544 §2 核实过）——接消费方是一件独立的活，
  不该搭在本裁定里扩范围（D-331：修在唯一知道它的地方，不是给每个下游装门）。

## 4. 验证现状

Kotlin 全量强制重跑 **119 套件 / 876 tests / 0 失败**（含 §2 的新守卫与突变审计）。
