# E2 / E3 / E4 执行装置 —— 操作说明与现状

> 承 `spec/adapters/INSTRUMENTATION_SPEC.md` §3.3（T17 产出，2026-08-02）。
> 状态词只用 `PASS` / `FAIL` / `NOT_EXECUTED` / `BLOCKED_EXTERNAL`。
> 下列命令的工作目录**一律是仓根**（D-320：带路径的命令要按它自己的工作目录解析一遍）。
> 决策入册 **D-402 / D-403**。

## 0. 先读：装置边界与设备红线

- **采集只有一只脚本，判读分三只**。spec §3.3 的依赖序图逐字写着 E4「可与 E3 并行，
  **共用同一批会话录轨**」，E2 又同为「一次真实会话同时开三条通道」。
  一次设备窗最贵的是会话本身，不是解析。
- **本装置不替谁解除 P40 红线**。`e1_collect.device_allowed()` 对 `ELS-*` 是硬拒绝
  （`DENY_REASON`：P40 归设备批 T1/T2 独占），而 spec §3.3 三个实验的资源栏都写着
  「P40 + 已装 App，需排窗」。缺的是一次**排窗授权**，而授权不是脚本能自己发的。
  做法：型号被 denylist 拒时必须给 `--device-window <ID>`，且**该 ID 必须能在
  `docs/BRAIN_TASKBOARD.md` 里查到**。**这个解锁形状本身待大脑裁定**（见 §5）。
- **dry-run 的数字一个都不许进真实语料池**，隔离做法见 §4（可核验，不是声称）。

## 1. 怎么跑

采集（**需真机窗 + 已装目标 App**；ROI 无默认值，见 `parse_roi` 的理由）：

```bash
python tools/e234/e234_collect.py --serial <serial> --pkg com.larus.nova \
    --roi 60,900,960,600 --allow-real-device --device-window <任务板上的窗 ID> \
    --session-seconds 900 --framestats-period-s 20
```

采集过程中的**操作者标记**（打进设备自己的 logcat，判读侧据此切轮）：

| 键 | 含义 |
|---|---|
| `a` | `answer_complete` —— 回答**看起来**已经完成的那一刻（E4 的外部真值） |
| `s` | `answer_start` —— 回答首字上屏（Compose 栈上 v3 不闭合时用） |
| `t` | `turn_start` —— 本轮开始 |
| `q` | 结束采集 |

判读（三只脚本各读同一个 run 目录）：

```bash
python tools/e234/e2_analyze.py --run-dir <run> --pkg com.larus.nova
python tools/e234/e3_analyze.py --run-dir <run> --pkg com.larus.nova
python tools/e234/e4_analyze.py --run-dir <run> --pkg com.larus.nova
```

离线反例（不需要任何设备）与突变审计：

```bash
python tools/e234/tests/run_tests.py          # 80/80
python tools/e234/tests/mutation_audit.py     # 12 处突变，运行时不落盘
```

模拟器 dry-run（**产出目录名必须带 `dryrun`，否则当场拒绝写盘**）：

```bash
python tools/e234/sim_session.py --scenario e4_overlap \
    --out evidence/e234_dryrun_20260802/dryrun-e4-overlap
```

## 2. 三个实验各量什么、判据是什么

| 实验 | 量 | 判据（spec 原文） | 本装置的产出 |
|---|---|---|---|
| **E2** | 同一锚点 A2 在各通道给出的时刻之差 | `\|t_A − t_C\|` 的 p99 > 1 帧 → 通道 A 单独不足以支撑 M3 门（§3.4 G-3） | `\|Δ\|` 分布 + **有符号**分布 + 通道 B 佐证 |
| **E3** | `A0 → A0′`（点击 → 用户气泡上屏） | 给出分布；**它不是"误差"，是被测 App 的输入处理耗时** | 分布 + 交回 §6-6 的 p50/p99；**本页刻意没有门** |
| **E4** | 流式内停顿 vs 结束后静默 | 有分离点 → `T_quiet`；**重叠 → C-1 单独不可用，A4 必须走 C-3 合取** | `SEPARABLE` / `OVERLAP` / `NOT_EXECUTED` + 重叠区与样例 |

三条口径决定（理由见 D-403，此处只点名）：

1. **E2 今天只有两个时刻可比，不是三个** —— 通道 B 的时戳是宿主侧的，与设备钟之间
   隔着一次从没标定过的 adb 往返（沿用 spec §2.2 与 e1 的既有裁断）。
2. **E4 的「回答结束」只接受外部标签，判据用极值不用分位数** —— 拿静默门限切轮就是
   用待标定量标定它自己；而 C-1 是逐轮应用的规则，一次超限就是一次误判。
3. **E4 的「结束后静默」含操作者停顿，是乐观量** —— 连它都重叠，`C-1 不可用`是硬结论；
   它分开了，结论只是**有条件**成立。

## 3. 现状（2026-08-02，**模拟器 dry-run，零设备零 adb**）

| 场景 | 注入真值 | 判读结果 |
|---|---|---|
| `e2_within_one_frame` | A−C 偏差 2–6 ms | **PASS**，p99 4.604 ms ≤ 1 帧 16.667 ms，n=6 dropped=0 |
| `e2_over_one_frame` | A−C 偏差 45–55 ms | **FAIL**，p99 51.509 ms > 16.667 ms |
| `e3_input_timeline_present` | `A0→A0′` = 180 ms | **PASS**，n=6 dropped=0，p50 = p99 = 180.000 ms |
| `e3_input_timeline_absent` | 归档实测的那种表头 | **NOT_EXECUTED**，逐字印出 23 个实际列名 |
| `e4_separable` | 最大停顿 900 ms / 最短静默 3000 ms | **SEPARABLE**，区间 (900.0, 3150.0) ms，`c1_usable=True` |
| `e4_overlap` | 最大停顿 4200 ms / 最短静默 1800 ms | **OVERLAP**，重叠区 [1950.0, 4200.0] ms，`c1_usable=False` |

> **这六行不是测量，是装置校验。** 它们只回答「判读脚本在已知真值下算得对不对」。
> 两个 E4 场景的 `t_quiet` **都是 `NOT_EXECUTED`** —— dry-run 语料过不了标定前门（§4）。

**真实语料的三个实验结论都是 `NOT_EXECUTED`**，原因已核实而非猜测：仓内不存在任何带
逐事件时戳的真实会话录轨（`evidence/` 全量扫 `ADAPTER_EVT.*t_boot_ns=`，dry-run 目录
之外**零命中**；三份真机 Room 库均无 adapter 相关表）。probe 侧的 `t_boot_ns` 是
2026-08-02 才落的一行，此前没有任何一次真实会话产出过它。

## 4. dry-run 隔离：三重，且每一重都实跑过

1. **写盘前断言**（`assert_isolation_before_write`）：dry-run 产物的目录名必须带
   `dryrun`；**真实采集反过来也不许穿这件外衣**（两个方向都拦）。断言跑在
   `makedirs` **之前** —— 反例直接查「抛的时候盘上有没有留下目录」（D-306 形状）。
   实跑：`--out evidence/e234_real_like` 当场 exit 2，事后该目录**不存在**。
2. **三面横幅**（D-303）：`RUN_KIND.json` + markdown 首屏 + stdout 各印一次，
   结果对象带 `dry_run: true`；**注入的真值参数原样落在 `RUN_KIND.json` 里**。
3. **前门自己拦得住**：
   - `refuse_calibration_from_dry_run()` 让 E4 拿 dry-run 语料时**结构上产不出**
     `T_quiet` —— 装置验证与标定是两件事，这一条把它钉死；
   - 既有契约门也拦：把 dry-run 的 `screencap_index.jsonl` 喂
     `scripts/validate_results.py`，**exit 1，`contract VIOLATIONS: 903 in 129 record(s)`**。

## 5. 待裁 / 待办（**本装置不自行裁定**）

| # | 事项 |
|---|---|
| **W-1** | **排窗解锁形状**：型号命中 denylist 时要求 `--device-window <ID>` 且 ID 须在任务板上可查 —— 这个形状是否被接受，属大脑裁定。不接受则本装置在 P40 上恒拒。 |
| **W-2** | **通道 C 的输入事件时戳在 P40 上有没有**（D-402）：归档那台设备的 framestats 表头只有 `InputEventId`，没有 `Oldest/NewestInputEvent`。若 P40 同形，**E3 与 §3.4 G-4 会一路卡在 `NOT_EXECUTED`**。是否启用 `HandleInputStart` 旁路（它单独成池、口径不同）属口径决定。 |
| **W-3** | **通道 B 的宿主↔设备时钟标定**：补上它，E2 才真是「三通道」对拍。属新增工作，本轮不发明。 |
| **W-4** | **T14 待裁 C-2 仍在**：`gate_verdict` 不看 `dropped`、不设最小 n。本装置把这两个数印在判定旁边，但**门限定在哪属口径决定**，不由脚本发明。 |
| **W-5** | **v3 簇分割用在 DeepSeek 上要额外论证**（§1.4）。本装置按**结构判据**处理（分不出两簇即 `NOT_EXECUTED` + 原因），不写死包名白名单 —— 白名单会在 App 改版那天悄悄说谎。E4 另有 `--a2-method operator-mark` 一条路。 |

## 6. 与 `tools/e1` 的关系

**复用，不复制**（D-315：没有依赖边的副本最难察觉）。直接 import 自 `tools/e1`：
`device_allowed` / `Adb` / `_pump` / `find_layer_name` / `pick_layer` /
`roi_mean_from_raw` / `STIM_PKG` / `STIM_ACT`（采集侧），
`parse_stim_log` / `clock_offset_ns` / `usable_flips` / `parse_sf_latency` /
`parse_framestats` / `parse_adapter_events` / `parse_screencap_index` /
`screencap_sampling_stats` / `summarize` / `gate_verdict` / `percentile`（判读侧）。
反例跑器也是 import 那一只（`run_tests.discover(here)`），不是抄一份。

时钟钉桩复用的是 **E1 刺激源本身**：它是我们自己的 App，不联网、不申请权限、
不碰目标 App 的额度或账号，而它每次翻转把 BOOTTIME 与 MONOTONIC **同帧打出** ——
这正是通道 A（BOOTTIME）与通道 C（MONOTONIC）相减所缺的那个偏移。
会话前后各钉一次，**漂移 > 1 帧即拒**（E2 的门本身就是「p99 ≤ 1 帧」）。

---
*E2/E3/E4 装置 v0.1 · 2026-08-02 · T17 · 装置就绪，三个实验均待真机窗*
