# M3 扩展轮 wave-0：SZ-PILOT-01 × ctcc × idle（首格真实数据）

> DW-20260803-04 · v2 · 2026-08-03 23:4x 大脑派单 → 2026-08-04 00:11–02:28 采集
> 承 T42；扩展轮口径见 `docs/M3_EXPANSION_ROUND_RUNBOOK_ADDENDUM.md`（quick 主体
> §3.1 预热轮 16 采 15 计 + 取证子集 §3.2 5 轮/格，D-379）。

## 0. 这是什么

扩展轮 32 格正式网格（`docs/campaign_grid_shenzhen.json`）的点位名仍是
`PENDING-PO-01..08` 占位，真名待 PO。本批用已知真名的家点位
`SZ-PILOT-01`（M2 试点点位）先行落地扩展轮口径本身——**这不是 32 格里的一格，
是在真名到位前验证"批式发射+逐run落地即验+quick/forensic 分面报告"整条链路
能不能在真实数据上跑通**。真名到位后可能需要把 `SZ-PILOT-01` 补进网格
（作为第 9 个点位，或替换某个 PENDING-PO 占位）——**本次未做这个决定，
留给 PO/大脑**。

## 1. 采集

批式发射（改自 `nr_batch_brain.ps1` 已验证过的可靠模式），脚本与逐 run 日志
不在本目录（活在本会话 scratchpad，非仓内文件；日志副本见
`evidence/nr_timeline_20260802/wave0_20260803.log`）。

- **22 次 `am start`**：quick 16 次（1 次预热丢弃 + 15 次计入，3 场景/run）+
  forensic 6 次（1 次预热丢弃 + 5 次计入，9 场景/run，D-379）。
- **22/22 全部 `status=completed`，逐 run 落地即验全部 PASS**（契约状态 + 场景数
  匹配 + radio 覆盖 100%[quick 3/3、forensic 9/9] + 出口读出齐），零失败、
  未触发"不过即停"分支。
- **一处需要如实记录的异常**：RUN 5 结束（00:26:34）到其"落地即验"结果打印
  （01:07:31）之间有约 **41 分钟的静默间隔**，期间控制台曾打出一行
  `adb.exe: unknown command E:\...\adb.exe`。**最终该 run 的验证结果仍为
  PASS**（场景/radio/出口三查齐），且这条 run 本身在异常出现**之前**就已经
  正常结束（00:26:34），故实测数据本身不受影响；后续 17 次发射（RUN 6–22）
  全部在正常节奏下完成，无再现。**根因未查**——候选是宿主机在此期间进入
  睡眠/USB 连接短暂复位（解释异常消息与恰好整数量级的停顿时长），但**没有
  做过交叉验证，如实标注为未证实的猜测，不是结论**。

## 2. 语料链路

| 文件 | 内容 | 产出方式 |
|---|---|---|
| `wave0_raw.jsonl` | 本次拉取窗口内设备上的全部 23 条 report_body（含 1 条无关的 pounce/T35 run `019fc83d`） | `pull_device_corpus.py --since-epoch-ms <批次起点>` |
| `wave0_counted_raw.jsonl` | 精确按台账（22 run 的 role 字段）过滤：20 条计入 run，排除 2 条预热丢弃 + 1 条无关 run | `wave0_filter_counted.py`（scratchpad，读台账不手抄 run_id） |
| `wave0_counted_labelled.jsonl` | 补注 `campaign_id=m3-expansion-wave0`、`point_id=SZ-PILOT-01`、`carrier=ctcc`、`tier=metro`、`time_band=idle`（显式设，非 `--infer-time-band`） | `annotate_campaign.py` |
| `wave0_quick_subset.jsonl` / `wave0_forensic_subset.jsonl` | 按 `run.mode` 拆分（15/5） | `split_by_run_mode.py` |

两次契约门（原始过滤后 + 补注后）均 `contract OK`（20 条，结构+R-10 交叉字段
均成立）。

## 3. 报告（quick 分面 + forensic 子集分别单独出，§5 第 2 条纪律）

- `report.md`/`report.html`/`tables_*.csv`/`provenance.json`：全部 20 条计入
  run 的主报告。`publish_check` **可发布（FAIL 0 / WARN 5 / N/A 4）**。
- `report_forensic.md`/`report_forensic.html`/`tables_forensic_*.csv`/
  `provenance_forensic.json`：仅 5 条取证 run 单独出的报告（避免与 quick
  混池导致序位效应误判"单元混杂"）。`publish_check` 同样**可发布**
  （FAIL 0 / WARN 5 / N/A 4）。
- `coverage_matrix.md`：`SZ-PILOT-01 × ctcc × idle` 落在"计划外已测单元"
  （不在当前 32 格 `PENDING-PO` 网格内，如实原样呈现，非 bug）。
- `plan_t1_ttft_ms.md` / `plan_n1_rtt_p50_ms.md`：§1 判据依据的两条
  `--plan` 采样量核算（quick 分面）。

## 4. 登记纪律：本文件不做优劣判断，只如实列出以下观察

- **`t1_ttft_ms` 三个 profile 的 CV 全部超门**（13.3% / 12.7% / 16.6%，
  s1/s2/s3），`n1_rtt_p50_ms` 两个超门（s1 11.2%、s2 10.2%）、s3 未超门
  （7.5%）——这批数据本身离散度不小，`stability.py --plan` 建议的复测数
  （80% 把握）中位 n≥81（t1）/n≥41（n1），远高于当前 n=15；先查原因
  （设备/环境/场景本身不稳）再决定是否照此复测，工具本身如此提醒。
- **`n1_rtt_p50_ms` 中位 ≈ 80–81ms**——供后续与既有登记对照参考
  （不在本文件下结论；T34/T36 已有的出口/制式对照表见
  `evidence/nr_timeline_20260802/`，若要把这一格接入那张地图，需另有登记）。
- **forensic 子集（n=5 真实 run）序位效应 4/9 处疑似位置-KPI 相关**——
  §3.2 增补文档记的"彩排实测取证子集单独过门序位效应✅PASS"是**合成语料**
  上的结果；这是首次在**真实**取证数据上单独跑这条检查，4/9 可能是真实
  外场噪声（n=5 很薄），也可能真有序位相关，**本文件不判定**，留给后续
  更大样本核实。
- **`SZ-PILOT-01` 目前不在 32 格网格文件里**——`coverage_matrix.py` 因此把
  它归入"计划外已测单元"而非网格内的一格；是否要把它正式补进网格是一个
  待裁决定，不是本次采集本身的缺陷。

## 5. 收尾

设备已复验干净（`wifi_on` 恢复原值 1、`stayon` 恢复 0、无残留 aneb/vpn 进程、
焦点回到 launcher）；哨兵 `evidence/nr_timeline_20260802/DEVICE_BUSY` 已删除。

---
*wave-0 · v2 · 2026-08-04 · 数据源=真机批采（`pull_device_corpus.py` 本会话
独立拉取），逐环节命令与产出如上，非转录*
