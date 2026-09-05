# `DW-20260905-02` 证据包（DeepSeek 四格批：DeepSeek × {WiFi, 蜂窝} × {F6, F1}）

> 🔑 **目录名＝批次 ID**：`evidence/DW-20260905-02/` ⇔ 批次 `DW-20260905-02`。命题单 `docs/BATCH_PROPOSITION_DW-20260905-02.md`（§5 授权链与追认位）；窗令 `docs/DW_20260905_02_WINDOW_ORDER.md`。
> **授权链**：PO 令 2026-09-05 晚「继续自主运行，v4 追认后直接起 DeepSeek 四格」← v4 追认上一单 `3960617` ← D-655 (4) ← D-704②(b)；大脑自起草自开。

## 0. 格阵与参数

| 格 | 条件 | 功能／开关（D-641） | 轮 | 答窗＋静置 | 提示词 |
|---|---|---|---|---|---|
| `verify_trial_f6/f2/f1` | WiFi | P4 试水（verify 类，D-655 (3)；**不计观察格**，采集器现只写 kind=DEVICE_REAL） | 各 1 | 120／120／60 ＋20 | 三句逐字见 §2 |
| `ds_wifi_f6` | WiFi | F6，思考 ON＋搜索 OFF | 6 | 75s＋20s | `Generate an image of a red circle on a white background.` |
| `ds_cell_f6` | 蜂窝 | 同上 | 6 | 75s＋20s | 同上 |
| `ds_wifi_f1` | WiFi | F1，双 OFF | 6 | 45s＋20s | `What is 5G in one sentence` |
| `ds_cell_f1` | 蜂窝 | 同上 | 6 | 45s＋20s | 同上 |

采集器：`e234_collect.py --serial 8MY0221126002537 --pkg com.deepseek.chat --roi 400,1800,400,200 --allow-real-device --device-window DW-20260905-02 --session-seconds <按格> --screencap-period-ms 1500 --framestats-period-s 1 --no-marks`；驱动器 `tools/e234/drive_cell_ds.py`（哈希见 §2）。模式选择器（快速／专家／识图）全批保持默认「快速模式」未动。

## 1. 前置实况（由各格 `orchestrator.log` 生成，未手抄）

| 格 | P1a aneb 进程数 | 制式 pre → post | 路由 pre → post | 同包窗口数 | 开关像素核对 | sf 首行（60Hz=16666666） | 编排 |
|---|---|---|---|---|---|---|---|
| `verify_trial_f6` | 1 (须=1) | NR_SA,Unknown → NR_SA,Unknown | 1.1.1.1 via 10.10.0.1 dev wlan0 → 1.1.1.1 via 10.10.0.1 dev wlan0 | 1 (须=1；>1 疑弹窗) | 未记 | 16666666 | DONE |
| `verify_trial_f2` | 1 (须=1) | NR_SA,Unknown → NR_SA,Unknown | 1.1.1.1 via 10.10.0.1 dev wlan0 → 1.1.1.1 via 10.10.0.1 dev wlan0 | 1 (须=1；>1 疑弹窗) | think=(164, 186, 254) ON(blue) | 16666666 | DONE |
| `verify_trial_f1` | 1 (须=1) | NR_SA,Unknown → NR_SA,Unknown | 1.1.1.1 via 10.10.0.1 dev wlan0 → 1.1.1.1 via 10.10.0.1 dev wlan0 | 1 (须=1；>1 疑弹窗) | think=(156, 156, 156) OFF(achromatic) | 16666666 | DONE |
| `ds_wifi_f6` | 1 (须=1) | NR_SA,Unknown → NR_SA,Unknown | 1.1.1.1 via 10.10.0.1 dev wlan0 → 1.1.1.1 via 10.10.0.1 dev wlan0 | 1 (须=1；>1 疑弹窗) | think=(164, 186, 254) ON(blue) | 16666666 | DONE |
| `ds_cell_f6` | 1 (须=1) | NR_SA,Unknown → NR_SA,Unknown | 1.1.1.1 via 10.99.85.214 dev rmnet0 → 1.1.1.1 via 10.99.85.214 dev rmnet0 | 1 (须=1；>1 疑弹窗) | think=(164, 186, 254) ON(blue) | 16666666 | DONE |
| `ds_wifi_f1` | 1 (须=1) | NR_SA,Unknown → NR_SA,Unknown | 1.1.1.1 via 10.10.0.1 dev wlan0 → 1.1.1.1 via 10.10.0.1 dev wlan0 | 1 (须=1；>1 疑弹窗) | think=(156, 156, 156) OFF(achromatic) | 16666666 | DONE |
| `ds_cell_f1` | 1 (须=1) | NR_SA,Unknown → NR_SA,Unknown | 1.1.1.1 via 10.42.241.236 dev rmnet0 → 1.1.1.1 via 10.42.241.236 dev rmnet0 | 1 (须=1；>1 疑弹窗) | think=(156, 156, 156) OFF(achromatic) | 16666666 | DONE |

## 2. 逐格结果（由产物生成；P1 判读＝`p1_inwindow_gaps.py`，命题单 §2 口径）

### 2.1 P4 试水（三格各 1 轮，宽答窗只为观察）

| 格 | 退出码 | 步 1a／1c | A 侧 | P1 轮内间隔计数 | e2 工具（参考信号） | 驱动器 | 驱动器实际值 |
|---|---|---|---|---|---|---|---|
| `verify_trial_f6` | driver=0 collector=0 | 1a 22725 -> 56469 | A 侧内容事件 617（00:20:40.584→00:20:59.493） | **P1_HOLDS_IN_CELL**（轮 1；窗内 >400ms 间隔总数 0；窗内 disjoint 总数 0；环跨度 2.07 s；dump/轮 103；反例轮 无） | e2 判词 NOT_EXECUTED；通道 B PASS（跃迁 4）；turn_method operator-marks；逐轮 a簇/c簇/帧＝1/1/7231；precheck 1 e2_precheck verify_trial_f6: NOT_APPLICABLE - 全程连续覆盖（零丢帧边界 | `tools/e234/drive_cell_ds.py@99d07b2` | 1 轮；答窗实际 120.02–120.02 s；静置实际 20.03–20.03 s |
| `verify_trial_f2` | driver=0 collector=0 | 1a 22815 -> 56562 | A 侧内容事件 1406（00:30:55.045→00:32:42.677） | **P1_HOLDS_IN_CELL**（轮 1；窗内 >400ms 间隔总数 0；窗内 disjoint 总数 0；环跨度 2.07 s；dump/轮 104；反例轮 无） | e2 判词 NOT_EXECUTED；通道 B PASS（跃迁 4）；turn_method operator-marks；逐轮 a簇/c簇/帧＝3/1/7220；precheck 1 e2_precheck verify_trial_f2: NOT_APPLICABLE - 全程连续覆盖（零丢帧边界 | `tools/e234/drive_cell_ds.py@99d07b2` | 1 轮；答窗实际 120.05–120.05 s；静置实际 20.03–20.03 s |
| `verify_trial_f1` | driver=0 collector=0 | 1a 22674 -> 56424 | A 侧内容事件 232（00:38:55.185→00:39:04.969） | **P1_HOLDS_IN_CELL**（轮 1；窗内 >400ms 间隔总数 0；窗内 disjoint 总数 0；环跨度 2.07 s；dump/轮 52；反例轮 无） | e2 判词 NOT_EXECUTED；通道 B PASS（跃迁 2）；turn_method operator-marks；逐轮 a簇/c簇/帧＝1/1/3620；precheck 1 e2_precheck verify_trial_f1: NOT_APPLICABLE - 全程连续覆盖（零丢帧边界 | `tools/e234/drive_cell_ds.py@99d07b2` | 1 轮；答窗实际 60.03–60.03 s；静置实际 20.03–20.03 s |
| `ds_wifi_f6_attempt1_toggle_stop` | **中止留痕**（未起采集器） | [00:48:41] STOP: 开关态不符（期望 think=ON search=OFF） | — | — | — | — | — |

### 2.2 正式四格

| 格 | 退出码 | 步 1a／1c | A 侧 | P1 轮内间隔计数 | e2 工具（参考信号） | 驱动器 | 驱动器实际值 |
|---|---|---|---|---|---|---|---|
| `ds_wifi_f6` | driver=0 collector=0 | 1a 22680 -> 56427；1c 断=0 | A 侧内容事件 3747（00:52:33.736→01:01:30.901） | **P1_HOLDS_IN_CELL**（轮 6；窗内 >400ms 间隔总数 0；窗内 disjoint 总数 0；环跨度 2.07 s；dump/轮 66/65/66/65/65/65；反例轮 无） | e2 判词 NOT_EXECUTED；通道 B PASS（跃迁 27）；turn_method operator-marks；逐轮 a簇/c簇/帧＝1/1/4522 1/1/4524 1/1/4528 1/1/4522 1/1/4524 1/1/4525；precheck 1 e2_precheck ds_wifi_f6: NOT_APPLICABLE - 全程连续覆盖（零丢帧边界）且一次 | `tools/e234/drive_cell_ds.py@99d07b2` | 6 轮；答窗实际 75.00–75.05 s；静置实际 20.00–20.04 s |
| `ds_cell_f6` | driver=0 collector=0 | 1a 22590 -> 56337；1c 断=0 | A 侧内容事件 3377（01:04:47.744→01:13:47.674） | **P1_HOLDS_IN_CELL**（轮 6；窗内 >400ms 间隔总数 0；窗内 disjoint 总数 0；环跨度 2.07 s；dump/轮 66/65/66/66/65/66；反例轮 无） | e2 判词 NOT_EXECUTED；通道 B PASS（跃迁 27）；turn_method operator-marks；逐轮 a簇/c簇/帧＝1/1/4526 1/1/4528 1/1/4526 1/1/4526 1/1/4527 1/1/4526；precheck 1 e2_precheck ds_cell_f6: NOT_APPLICABLE - 全程连续覆盖（零丢帧边界）且一次 | `tools/e234/drive_cell_ds.py@99d07b2` | 6 轮；答窗实际 75.01–75.04 s；静置实际 20.04–20.05 s |
| `ds_wifi_f1` | driver=0 collector=0 | 1a 22587 -> 56334；1c 断=0 | A 侧内容事件 1422（01:17:14.254→01:23:33.790） | **P1_HOLDS_IN_CELL**（轮 6；窗内 >400ms 间隔总数 0；窗内 disjoint 总数 0；环跨度 2.07 s；dump/轮 40/40/41/40/40/40；反例轮 无） | e2 判词 NOT_EXECUTED；通道 B PASS（跃迁 13）；turn_method operator-marks；逐轮 a簇/c簇/帧＝1/1/2716 1/1/2717 1/1/2715 1/1/2717 1/1/2718 1/1/2717；precheck 1 e2_precheck ds_wifi_f1: NOT_APPLICABLE - 全程连续覆盖（零丢帧边界）且一次 | `tools/e234/drive_cell_ds.py@99d07b2` | 6 轮；答窗实际 45.01–45.04 s；静置实际 20.03–20.04 s |
| `ds_cell_f1` | driver=0 collector=0 | 1a 22725 -> 56472；1c 断=0 | A 侧内容事件 1465（01:26:27.641→01:32:47.665） | **P1_HOLDS_IN_CELL**（轮 6；窗内 >400ms 间隔总数 0；窗内 disjoint 总数 0；环跨度 2.07 s；dump/轮 40/40/40/40/40/40；反例轮 无） | e2 判词 NOT_EXECUTED；通道 B PASS（跃迁 13）；turn_method operator-marks；逐轮 a簇/c簇/帧＝1/1/2717 1/1/2716 1/1/2715 1/1/2715 1/1/2715 1/1/2716；precheck 1 e2_precheck ds_cell_f1: NOT_APPLICABLE - 全程连续覆盖（零丢帧边界）且一次 | `tools/e234/drive_cell_ds.py@99d07b2` | 6 轮；答窗实际 45.00–45.04 s；静置实际 20.00–20.05 s |

## 3. 口径与不回答什么

- 自然对照版（无整形）；四态 `PASS / FAIL / NOT_EXECUTED / BLOCKED_EXTERNAL`；P1 判读以 `p1_inwindow_gaps.py` 为准，`e2_precheck`/`e2_analyze` 判词只作参考；P3 读 `e2_precheck` 的「A侧可用轮」。命题单 §4 照录。

## 4. 收窗判读（2026-09-06 01:4x，锁定人裁；v4 追认位见命题单 §5a）

- **P1 成立（DeepSeek 的思考期在本装置上不可被 e2 观测）**：四格 24 轮，`p1_inwindow_gaps.py` 窗内 >400ms 的 C 侧间隔总数 **0**、窗内 disjoint **0**、环跨度恒 **2.07s**（＝127÷60Hz，环始终满）、每轮帧数满帧（F6 约 4522／75s，F1 约 2716／45s）；`e2_precheck` 四格与三试水格**同判 NOT_APPLICABLE**（两条不共享判据的路一致）。机制比命题写的更强：**DeepSeek 连静置期也保持 60fps 渲染**，不只是思考期。D-642③(c) 窗口量：每轮可观测窗口＝整个答窗（65–66 个 dump／F6 轮、约 40 个／F1 轮，disjoint 0），回答在 6–9s（F6）／数秒（F1）内结束，窗口覆盖充分；本批未触发 F2 回退，条款 (a)(b) 不适用。
- **P3 被拒（DeepSeek F1 的 A 侧可用轮数与豆包不同型）**：`e2_precheck`「A侧可用轮」DeepSeek F1 **0/6（WiFi）＋0/6（蜂窝）＝0/12**，豆包 F1 为 3/8＋4/6＝7/14；两格 F6 同为 0/6。机制：DeepSeek 的内容事件流连续、密集（`e2_analyze` 每轮只切出 1 个 A 簇），**切不出次簇**——这是 A 侧的结构性上界（命题单 §1b 预写），不是网络差异。开关态 F1 两格双 OFF 经像素核对，故按 §1c 可写「不同型」而非「带检索 vs 不检索」。
- **P4（次）**：四格不可判间隔＝0（period 1 下 C 侧连续覆盖），与 DW-20260905-01 两格一致。
- **e2 假设的地位**：豆包 F6 三格 FAIL（A 早于 C 12–28s，文本事件先于图像渲染）；DeepSeek 四格结构性不适用。⇒ e2「一帧对齐」在两 App 上都不能作主命题（D-715）。
- **停窗规则记账**：编排侧 1 次 STOP（`ds_wifi_f6_attempt1_toggle_stop`：开关钩子按「冷启复位为双 ON」盲点一次，像素守卫拦截，未起采集器、设备侧零损）；修为先测再点后四格零滑落。设备侧零滑落。格间间隔均 <30 分钟（D-640③④）。
- **未回答**：命题单 §4 照录；本批不读答案内容、不比 App 快慢、不回答网络诉求。模式选择器（快速／专家／识图）全批默认「快速模式」——**专家模式下思考期是否仍连续渲染未测**，不外推。
- **收窗动作**：台账重算（观察目录 +7：三试水＋四格；attempt1 无 RUN_KIND 不计；真机 wire 不变）；T80 现态改已收窗；D-715／D-716 入册；v4 追认位待补签。

### 4.1 勘误与补强（2026-09-06 02:0x，承 v4 追认 `4408a5b` 附带四条；锁定正文按 D-663② 不动，勘误记此处与 D-717）

- **①「结构性不可达」限定过宽（§2 P1）**：`e2_precheck` 的 NOT_APPLICABLE 在本批七格（三试水＋四格）全部达成；真限定是「本协议 **＋ 静置期不渲染的 App**」（豆包成立，DeepSeek 连静置期也 60fps）。原句照字面读会把七次 NOT_APPLICABLE 当工具故障，而 §4 又拿它作互证——同一材料两处相悖，以本条为准。
- **②§1b 试水数订正（结论不变）**：F2 ＝ **1406 事件／整场 107.6s（窗内 1258／98.5s）**，F1 ＝ **232／9.8s（窗内 161／1.2s）**，F6 ＝ 617／18.9s（窗内 497／9.9s）。锁定正文里的 1396／32.0s 与 228／9.7s 是**采集器仍在写日志时提前读出的数**（末事件当时尚未落盘）。F6 对照真短答 F1 仍明显非短答拒绝，D-637② 分支不触发的结论不变；但按窗内跨度 F6（9.9s）离 F1（1.2s）比离 F2（98.5s）更近，如实记。
- **③D-715 证据面订正**：豆包侧 FAIL 为 **F2／F5／F6 三个功能、七格**（wave0 `cell_f2` 19.8s、`cell_f5`／`wifi_f5` 11.5／10.4s、`cell_f6`／`wifi_f6` 12.3／17.2s、DW-01 两格 15.3／15.1s）；**F1 六格全 NOT_EXECUTED（n<5）＝没测成，不是测了没差异**；DeepSeek F1 结构性不适用。措辞改为「e2 在 F2／F5／F6 上不作主命题；F1 两侧均无 FAIL 证据，不外推」。
- **④第三条腿（帧计数）**：P1 的两条路（轮内间隔计数、`e2_precheck`）共享 `sf_latency.txt` 数据层，一致只排除判据错误；**帧计数是独立的计数量**：四格 24 轮每轮 4522–4528（F6，75.0s）／2715–2718（F1，45.0–45.1s）帧 ⇒ **60.2–60.4 fps 满帧**，dump 若漏帧此数会掉。三腿一致。

