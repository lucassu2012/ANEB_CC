# E2/E3/E4 装置校验 dry-run —— 2026-08-02（T17）

> ⚠ **本目录里每一个数字都由模拟器生成**（`tools/e234/sim_session.py`）。
> 它们只回答「判读脚本在已知真值下算得对不对」，**不是任何一次测量**。
> **不得入任何统计池、不得作标定值。** 零设备、零 adb、零真实 App 额度。

装置与口径说明见 [`tools/e234/README.md`](../../tools/e234/README.md)；决策 **D-402 / D-403**。

## 1. 六个场景与判读结果

每个子目录的 `RUN_KIND.json` 里带 `kind: DRY_RUN_SIMULATED` 与**注入的真值参数**
（`injected_truth` + `params`），`truth.json` 是同一份真值的单独一份。

| 目录 | 注入真值 | 判读结果 |
|---|---|---|
| `dryrun-e2-within/` | A−C 偏差 2–6 ms | `PASS`，p99 **4.604 ms** ≤ 1 帧 16.667 ms，n=6 dropped=0 |
| `dryrun-e2-over/` | A−C 偏差 45–55 ms | `FAIL`，p99 **51.509 ms** > 16.667 ms |
| `dryrun-e3-present/` | `A0→A0′` = 180 ms | `PASS`，n=6 dropped=0，p50 = p99 = **180.000 ms** |
| `dryrun-e3-absent/` | 归档实测的那种 framestats 表头 | `NOT_EXECUTED`，逐字印出 23 个实际列名 |
| `dryrun-e4-separable/` | 最大停顿 900 ms / 最短静默 3000 ms | `SEPARABLE`，区间 **(900.0, 3150.0) ms**，`c1_usable=true` |
| `dryrun-e4-overlap/` | 最大停顿 4200 ms / 最短静默 1800 ms | `OVERLAP`，重叠区 **[1950.0, 4200.0] ms**，`c1_usable=false` |

**两个 E4 场景的 `t_quiet` 都是 `NOT_EXECUTED`** —— dry-run 语料过不了标定前门。
`e4_separable` 那一行尤其要看清楚：**分离点找到了，值仍然不给**。装置验证与标定是两件事。

`dryrun-e4-separable` 的上界为什么是 3150 而不是注入的 3000：结束后静默量的是
「本轮最后一个增量 → **下一轮第一个事件**」，而下一轮第一个事件在 `t_a0 + a0_gap`
（150 ms）处，故 3000 + 150。这条口径是**乐观**的（含操作者停顿），见 `e4_report.md` §2。

## 2. 复跑

```bash
python tools/e234/sim_session.py --scenario e2_within_one_frame --out evidence/e234_dryrun_20260802/dryrun-e2-within
python tools/e234/e2_analyze.py --run-dir evidence/e234_dryrun_20260802/dryrun-e2-within --pkg com.larus.nova
python tools/e234/sim_session.py --scenario e2_over_one_frame --out evidence/e234_dryrun_20260802/dryrun-e2-over
python tools/e234/e2_analyze.py --run-dir evidence/e234_dryrun_20260802/dryrun-e2-over --pkg com.larus.nova
python tools/e234/sim_session.py --scenario e3_input_timeline_present --out evidence/e234_dryrun_20260802/dryrun-e3-present
python tools/e234/e3_analyze.py --run-dir evidence/e234_dryrun_20260802/dryrun-e3-present --pkg com.larus.nova
python tools/e234/sim_session.py --scenario e3_input_timeline_absent --out evidence/e234_dryrun_20260802/dryrun-e3-absent
python tools/e234/e3_analyze.py --run-dir evidence/e234_dryrun_20260802/dryrun-e3-absent --pkg com.larus.nova
python tools/e234/sim_session.py --scenario e4_separable --out evidence/e234_dryrun_20260802/dryrun-e4-separable
python tools/e234/e4_analyze.py --run-dir evidence/e234_dryrun_20260802/dryrun-e4-separable --pkg com.larus.nova
python tools/e234/sim_session.py --scenario e4_overlap --out evidence/e234_dryrun_20260802/dryrun-e4-overlap
python tools/e234/e4_analyze.py --run-dir evidence/e234_dryrun_20260802/dryrun-e4-overlap --pkg com.larus.nova
```

生成器**按种子确定**（默认 `--seed 20260802`），有反例钉住确定性。

## 3. 隔离可核验（三重，逐条实跑过）

| # | 做法 | 实跑证据 |
|---|---|---|
| 1 | 写盘前断言目录名带 `dryrun`，且断言在 `makedirs` **之前** | `--out evidence/e234_real_like` → **exit 2**，事后该目录**不存在** |
| 2 | 三面横幅（`RUN_KIND.json` / markdown / stdout）+ `dry_run: true` | 见各子目录三份产物 |
| 3 | 前门自己拦得住 | ① E4 拿 dry-run 语料**结构上产不出** `T_quiet`（两个场景实测均 `NOT_EXECUTED`）；② `python scripts/validate_results.py evidence/e234_dryrun_20260802/dryrun-e2-within/screencap_index.jsonl` → **exit 1，`contract VIOLATIONS: 903 in 129 record(s)`** |

反向也拦：真实采集**不许**写进带 `dryrun` 的目录名（`e234_collect.py` 启动即检）。

## 4. 突变审计

`mutation_audit_20260802.txt` —— 12 处运行时突变（**不落盘**：共享工作树里改源码再还原，
中途被杀会留下突变态，D-321 实录）。**12/12 CAUGHT，5 处单点**，已在对应测试首行标
`⚠ SOLE targeted guard`；基线 129 条全绿、还原后复跑仍 0 失败。
承重最广的是 M8（framestats 不剥尾逗号，12 条变红）—— 那正是 D-402 修的那个缺陷。

## 5. 这份 dry-run **没有**回答的问题

- P40 上的 framestats 是哪一种表头形态（**E3 的 A0 能不能锚**，D-402 / W-2）；
- 通道 C 在 P40 上到底取不取得到帧（spec §7.2 第 4 项，T7 记的 `BLOCKED_EXTERNAL`）；
- 真实会话里 `T_quiet` 到底可不可分 —— **本轮无真实语料**（`evidence/` 全量扫
  `ADAPTER_EVT.*t_boot_ns=`，本目录之外零命中），故真实结论是 `NOT_EXECUTED`，
  不是「可分」也不是「不可分」。
