# ANEB 战役级综合报告

> claim_scope: `application_end_to_end_to_probe_node` — 应用层端到指定节点路径；**不表述为** MOS / 无线层评级 / 运营商全网 SLA。
> 输入记录：12；含 run.aqs：12；含 campaign 标签：12。样本地板 min_samples=5。

## 覆盖盘点

- 战役 campaign_id：{'m2-pilot-20260731': 12}
- 点位 point_id：{'SZ-PILOT-01': 12}
- 运营商 carrier：{'ctcc': 12}
- 时段 time_band：{'busy': 11, 'idle': 1}
- 服务层级 tier：{'metro': 12}
- run 状态 status：{'completed': 12}
- profile 版本：{'s1_chat@0.2.1;s2_coding_agent@0.2.1;s3_multimodal@0.3.0': 12}
- 标签来源 label_source：{'set+inferred:time_band(tz=+8)': 12}
- 采集时间窗：2026-07-31 05:36 UTC → 2026-07-31 06:23 UTC

## 溯源 / provenance（可复现性）

> 工具 `aneb-campaign-analysis/1.0` · 生成 2026-07-31 17:35:42 +0800 · 读 12 行 → 保留 12 条（去重丢 0）。参数 {"min_samples": 5, "attr_kpi": "n1_rtt_p50_ms", "campaign": "m2-pilot-20260731", "before": null, "after": null}。

> **生效门限**（改动其一即改变报告结论，复现须同值）：{"cv_gate_percent": 10.0, "stability_max_stable_rows": 25, "validity_min_rate": 0.8, "buffering_hotspot_share": 0.5, "clock_hotspot_share": 0.5, "aqs_grade_bands": [[85.0, "excellent"], [70.0, "good"], [54.0, "fair"], [0.0, "poor"]], "local_day_utc_offset_h": 8, "value_ranges_non_kpi": {"rsrp_dbm": [-160.0, -30.0], "sinr_db": [-30.0, 45.0]}, "rsrp_weak_dbm": -105.0, "rsrp_good_dbm": -95.0, "sinr_weak_db": 0.0, "sinr_good_db": 10.0, "signal_bands": ["weak", "medium", "good"], "signal_labels": {"weak": "弱", "medium": "中", "good": "良"}, "grade_order": ["excellent", "good", "fair", "poor"], "attribution_group_by": ["point_id", "carrier", "time_band", "profile_id"], "stability_group_by": ["campaign_id", "point_id", "carrier", "time_band", "tier", "profile_id"], "heat_kpis": ["t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps", "t2_itl_p95_ms"], "stability_kpis": ["t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps"], "attribution_kpis": ["n1_rtt_p50_ms", "t1_ttft_ms"], "tier_time_spread_gate_ms": 3600000, "segment_outlier_target_false_alarm": 0.05, "segment_outlier_k_by_cells": [[5, 8.0], [9, 6.0], [1000000000, 5.0]], "segment_min_cells_to_screen": 4, "order_effect_threshold_percent": 10.0, "min_campaigns_for_trend": 3, "median_se_factor": 1.253, "mad_to_sigma": 1.4826, "epoch_ms_bounds": [1577836800000, 4102444800000], "value_ranges": {"aqs_score": [0.0, 100.0], "buffering_score": [0.0, 1.0], "n1_rtt_p50_ms": [0.0, null], "n2_jitter_ms": [0.0, null], "near_zero_arrival_ratio": [0.0, null], "sawtooth_ratio": [0.0, null], "sub_score": [0.0, 100.0], "t1_ttft_ms": [0.0, null], "t2_itl_p95_ms": [0.0, null], "t3_stall_rate": [0.0, 1.0], "t4_severe_stall_rate": [0.0, 1.0], "u1_goodput_mbps": [0.0, null], "u2_tool_loop_p95_ms": [0.0, null]}, "tiers": ["metro", "regional", "core"], "attribution_segments": ["access_component", "regional_backbone_incr", "core_backbone_incr"], "severe_incomparability_flags": ["TIER_TIME_SPREAD", "MIXED_TRANSPORT", "TIER_ENDPOINT_CONFLICT", "IMPLAUSIBLE_VALUE", "VETO_CAPPED", "TIER_INCOMPLETE"], "order_effect_kpis": ["t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps"], "transport_media": ["wifi", "cellular"], "trend_metric_key": "aqs"}

| 输入文件 | sha256 |
|---|---|
| pilot_labelled.jsonl | `36f620dad297…` |


> ⚠ **`time_band` 有 12/12 条是工具推断的**（按 `started_at_epoch_ms` 的本地小时,非现场记录;规则与所用时区偏移见「覆盖盘点」的 `label_source`）。忙闲差异的结论**须注明这一点**——推断错时段会把两类流量混在一起,而表面上看不出来。

## 摘要（先看这里）

> 下列每条中的示例均为该项**最严重的前三个**（其余以「等 N 个」计数，完整清单见对应段落与 CSV）。

- **体验最差格**：2 个格中无 fair/poor（最低 SZ-PILOT-01/ctcc/busy=89）——其中 **1 个格 low_confidence**，不要据它们判定好坏；且这 **12 条 run 全部被打分器自评低置信**（`run.aqs.low_confidence`，热力卡 `SCORER_LOW_CONF`）——**分数自己声明了不确定**，本行的分级不得当作定论。
- **分段归因**（`n1_rtt_p50_ms`；主要贡献段）：接入 6 格；最大单项 SZ-PILOT-01/ctcc/busy/s2_coding_agent·接入=65.1ms；各段**均未见单点异常**（判据：MAD 稳健筛查（K=6×1.4826×MAD，K 随可比单元数标定））——最大单项落在该段分布内，不宜单独归因于该单元（单元间齐不齐见「分段异常定位」段）。
- **批化失真**：无热点格。
- **时钟可疑热点**：无。
- **有效率**：全部达门（≥80%）。
- **复测不稳定**：1/9 单元超 CV 门 —— SZ-PILOT-01/ctcc/busy/metro/s2_coding_agent·t1_ttft_ms；另有 **9 个单元 CV 不可计算**（n<2 或均值≤0，**未计入分母**，见稳定性段**备注**列的 `CV 不可计算` 标记）。
- **序位效应**：全语料只有**一种轮次**——**拉丁方未轮转**，反平衡在构造上不成立，位次差无法与场景差分离。
- **预热效应**：语料**只有一轮**（quick 每场景一遍）——**无法校验**；而单轮模式测到的永远是第一轮，故本报告**绝对值均为冷启动口径**（取证语料实测首轮时延高 8–12%、吞吐低 10–16%，D-355）。
- **无线上下文**：本轮语料**完全没有**——**无从核对**结论里是否混着信号差异（**采集缺口，不是「信号良好」**；生产侧接线规格见 `docs/RADIO_CONTEXT_WIRING_SPEC.md`）。
- **接入介质**：无同格双介质可比，或蜂窝不劣于 wifi。
- **分数侧归因**（拖累维度）：N1 2 格；最低 SZ-PILOT-01/ctcc/busy·N1=68.1。
- **优化前后**：本轮仅 1 个战役，无前后可比——「有没有变好」本轮**无法回答**（需第二轮在同样的格上复测）。

> 以上为下方各段的**指路**，证据与完整表格见对应段落；口径与不可计算说明以各段为准。

## 点位 × 忙闲 × 运营商 热力卡（AQS 中位）

> `离散(sd)` 是该格 AQS 的样本标准差。**中位相同、离散天差地别的两个格,读起来一模一样**——sd=0 的格每次都一样,sd=36 的格在 20 与 95 之间来回,两者的中位数不是同一种东西。<2 个样本时留 `—`(离散未知,不是 0)。

| 点位 | 运营商 | 时段 | AQS中位 | 离散(sd) | 分级 | n | 备注 |
|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 89 | 0.6 | excellent | 11 | SCORER_LOW_CONF:11/11 |
| SZ-PILOT-01 | ctcc | idle | 89.3 | — | excellent | 1 | SCORER_LOW_CONF:1/1; low_conf |

## 分 KPI 热力卡（原始 KPI 中位 + 上报 KpiGrading 分级）

### 分 KPI 热力卡：`t1_ttft_ms`（中位；分级=上报 KpiGrading 众数）

> `profile 跨度` 是该格**各 profile 各自中位**的范围。这张卡把一格里的所有 profile 汇成一个中位，而它们**测的不是同一件事**——实测 `u1_goodput_mbps` 在 s1_chat（上行 ~2KB 文本）只有 0.14 Mbps，在 s3_multimodal 有 16.4 Mbps；中位 10.05 **谁都不代表**。跨度大就别把中位当作「该格的该 KPI」，改看下方「复测稳定性」段的逐 profile 行。

| 点位 | 运营商 | 时段 | 中位 | profile 跨度 | 分级 | n | 备注 |
|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 53.26 | 53.01–54.07（3 个 profile） | excellent | 33 | — |
| SZ-PILOT-01 | ctcc | idle | 51.17 | 47.19–59.32（3 个 profile） | excellent | 3 | low_conf |

### 分 KPI 热力卡：`n1_rtt_p50_ms`（中位；分级=上报 KpiGrading 众数）

> `profile 跨度` 是该格**各 profile 各自中位**的范围。这张卡把一格里的所有 profile 汇成一个中位，而它们**测的不是同一件事**——实测 `u1_goodput_mbps` 在 s1_chat（上行 ~2KB 文本）只有 0.14 Mbps，在 s3_multimodal 有 16.4 Mbps；中位 10.05 **谁都不代表**。跨度大就别把中位当作「该格的该 KPI」，改看下方「复测稳定性」段的逐 profile 行。

| 点位 | 运营商 | 时段 | 中位 | profile 跨度 | 分级 | n | 备注 |
|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 64.13 | 62.55–65.07（3 个 profile） | fair | 33 | — |
| SZ-PILOT-01 | ctcc | idle | 63.41 | 59.38–64.19（3 个 profile） | fair | 3 | low_conf |

### 分 KPI 热力卡：`u1_goodput_mbps`（中位；分级=上报 KpiGrading 众数）

> `profile 跨度` 是该格**各 profile 各自中位**的范围。这张卡把一格里的所有 profile 汇成一个中位，而它们**测的不是同一件事**——实测 `u1_goodput_mbps` 在 s1_chat（上行 ~2KB 文本）只有 0.14 Mbps，在 s3_multimodal 有 16.4 Mbps；中位 10.05 **谁都不代表**。跨度大就别把中位当作「该格的该 KPI」，改看下方「复测稳定性」段的逐 profile 行。

| 点位 | 运营商 | 时段 | 中位 | profile 跨度 | 分级 | n | 备注 |
|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 10.05 | 0.14–16.43（3 个 profile） | good | 33 | — |
| SZ-PILOT-01 | ctcc | idle | 11.18 | 0.14–17.07（3 个 profile） | good | 3 | low_conf |

### 分 KPI 热力卡：`t2_itl_p95_ms`（中位；分级=上报 KpiGrading 众数）

> `profile 跨度` 是该格**各 profile 各自中位**的范围。这张卡把一格里的所有 profile 汇成一个中位，而它们**测的不是同一件事**——实测 `u1_goodput_mbps` 在 s1_chat（上行 ~2KB 文本）只有 0.14 Mbps，在 s3_multimodal 有 16.4 Mbps；中位 10.05 **谁都不代表**。跨度大就别把中位当作「该格的该 KPI」，改看下方「复测稳定性」段的逐 profile 行。

| 点位 | 运营商 | 时段 | 中位 | profile 跨度 | 分级 | n | 备注 |
|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 29.5 | 15.02–30.31（3 个 profile） | excellent | 33 | — |
| SZ-PILOT-01 | ctcc | idle | 29.12 | 12.41–29.41（3 个 profile） | excellent | 3 | low_conf |

## 复测稳定性（CV 门 ≤10%，对齐 M1 验收）

### 复测稳定性：`t1_ttft_ms`（CV% = 样本 stdev/mean；门 ≤10% 为稳定）

> **本表共 6 个单元**：✗超门 1，CV 不可计算 3，其余稳定。摘要的「N/M 单元超 CV 门」即各 KPI 分表这两个数各自相加。

| 单元 | n | 中位 | 均值 | CV% | 稳定? | 备注 |
|---|---|---|---|---|---|---|
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 11 | 53.26 | 53.05 | 5.5 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 11 | 54.07 | 54.85 | 10.3 | ✗超门 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 11 | 53.01 | 53.26 | 5.9 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 1 | 47.19 | 47.19 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 1 | 59.32 | 59.32 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 1 | 51.17 | 51.17 | — | — | CV 不可计算(n<2); low_conf |

### 复测稳定性：`n1_rtt_p50_ms`（CV% = 样本 stdev/mean；门 ≤10% 为稳定）

> **本表共 6 个单元**：✗超门 0，CV 不可计算 3，其余稳定。摘要的「N/M 单元超 CV 门」即各 KPI 分表这两个数各自相加。

| 单元 | n | 中位 | 均值 | CV% | 稳定? | 备注 |
|---|---|---|---|---|---|---|
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 11 | 65.03 | 65.37 | 3.3 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 11 | 65.07 | 64.17 | 3.6 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 11 | 62.55 | 62.58 | 4.4 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 1 | 64.19 | 64.19 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 1 | 63.41 | 63.41 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 1 | 59.38 | 59.38 | — | — | CV 不可计算(n<2); low_conf |

### 复测稳定性：`u1_goodput_mbps`（CV% = 样本 stdev/mean；门 ≤10% 为稳定）

> **本表共 6 个单元**：✗超门 0，CV 不可计算 3，其余稳定。摘要的「N/M 单元超 CV 门」即各 KPI 分表这两个数各自相加。

| 单元 | n | 中位 | 均值 | CV% | 稳定? | 备注 |
|---|---|---|---|---|---|---|
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 11 | 0.14 | 0.14 | 6.2 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 11 | 10.05 | 10.11 | 8.3 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 11 | 16.43 | 16.56 | 5.2 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 1 | 0.14 | 0.14 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 1 | 11.18 | 11.18 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 1 | 17.07 | 17.07 | — | — | CV 不可计算(n<2); low_conf |

## 序位效应诊断（t1_ttft_ms；拉丁方反平衡是否奏效）

> 判据：同 profile 各**执行位次**的中位数极差 / 总体中位数 > 10.0% 即疑似残留序位偏倚（无效应=好结果）。

> ⚠ 全语料只有**一种轮次**（`scenario_order` 按 `|` 拆分后）——拉丁方未轮转，反平衡在构造上不成立，位次差无法与场景差分离。

| profile | 位次中位数 | 极差 | 极差% | 总体中位 | 判定 | 备注 |
|---|---|---|---|---|---|---|
| s1_chat | #0:53.2(n=12) | — | — | 53.2 | 不可计算 | NEED_2_POSITIONS; low_conf |
| s2_coding_agent | #1:54.7(n=12) | — | — | 54.7 | 不可计算 | NEED_2_POSITIONS; low_conf |
| s3_multimodal | #2:52.9(n=12) | — | — | 52.9 | 不可计算 | NEED_2_POSITIONS; low_conf |

## 序位效应诊断（n1_rtt_p50_ms；拉丁方反平衡是否奏效）

> 判据：同 profile 各**执行位次**的中位数极差 / 总体中位数 > 10.0% 即疑似残留序位偏倚（无效应=好结果）。

> ⚠ 全语料只有**一种轮次**（`scenario_order` 按 `|` 拆分后）——拉丁方未轮转，反平衡在构造上不成立，位次差无法与场景差分离。

| profile | 位次中位数 | 极差 | 极差% | 总体中位 | 判定 | 备注 |
|---|---|---|---|---|---|---|
| s1_chat | #0:64.9(n=12) | — | — | 64.9 | 不可计算 | NEED_2_POSITIONS; low_conf |
| s2_coding_agent | #1:64.8(n=12) | — | — | 64.8 | 不可计算 | NEED_2_POSITIONS; low_conf |
| s3_multimodal | #2:62.2(n=12) | — | — | 62.2 | 不可计算 | NEED_2_POSITIONS; low_conf |

## 序位效应诊断（u1_goodput_mbps；拉丁方反平衡是否奏效）

> 判据：同 profile 各**执行位次**的中位数极差 / 总体中位数 > 10.0% 即疑似残留序位偏倚（无效应=好结果）。

> ⚠ 全语料只有**一种轮次**（`scenario_order` 按 `|` 拆分后）——拉丁方未轮转，反平衡在构造上不成立，位次差无法与场景差分离。

| profile | 位次中位数 | 极差 | 极差% | 总体中位 | 判定 | 备注 |
|---|---|---|---|---|---|---|
| s1_chat | #0:0.1(n=12) | — | — | 0.1 | 不可计算 | NEED_2_POSITIONS; low_conf |
| s2_coding_agent | #1:10.2(n=12) | — | — | 10.2 | 不可计算 | NEED_2_POSITIONS; low_conf |
| s3_multimodal | #2:16.5(n=12) | — | — | 16.5 | 不可计算 | NEED_2_POSITIONS; low_conf |

## 预热效应（首轮是否系统性更差）

> 本轮语料**只有一轮**（quick 模式每场景只跑一遍）——**预热效应无法校验**。**这不等于没有**：取证语料实测首轮时延高 8–12%、吞吐低 10–16%（D-355），而单轮模式测到的**永远是那一轮**，所以本报告的**绝对值均为冷启动口径**；跨格比较不受影响（每格一样冷）。


## 有效性与失效原因（每格的有效样本分母）

> 全语料尝试 36 个场景，可用 36 （100.0%）；低于 80% 的单元标 `LOW_VALID_RATE`。INVALID 场景 KPI 为空、会被热力卡/归因静默丢弃——**此表即那些被丢弃样本的去向**。

> **有效率的分子是两列之和**：`有效率 =（有效(严格) + 低置信）/ 尝试`。低置信的场景**仍产出了可用测量**，所以它计入分子；**「有效(严格)」那一列不是分子**，拿它去除尝试会得到另一个数——`有效(严格)=0` 与 `有效率=100%` 可以同时成立，且都没错。

> **「未知」的口径**：`validity` 取值不在已知三态内（本层大小写不敏感）即计入**未知**列。**未知按「不可用」计入有效率**——这是保守方向，但它**不是失效**，而是本层读不懂那个状态。故未知占比高的格会标 `UNKNOWN_VALIDITY:x%`：该格的有效率**不应读成「这里全失败了」**，应先去查生产者写了什么。

| 点位 | 运营商 | 时段 | profile | 尝试 | 有效(严格) | 低置信 | 失效 | 未知 | 有效率 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | s1_chat | 11 | 0 | 11 | 0 | 0 | 100.0% | — |
| SZ-PILOT-01 | ctcc | busy | s2_coding_agent | 11 | 0 | 11 | 0 | 0 | 100.0% | — |
| SZ-PILOT-01 | ctcc | busy | s3_multimodal | 11 | 0 | 11 | 0 | 0 | 100.0% | — |
| SZ-PILOT-01 | ctcc | idle | s1_chat | 1 | 0 | 1 | 0 | 0 | 100.0% | — |
| SZ-PILOT-01 | ctcc | idle | s2_coding_agent | 1 | 0 | 1 | 0 | 0 | 100.0% | — |
| SZ-PILOT-01 | ctcc | idle | s3_multimodal | 1 | 0 | 1 | 0 | 0 | 100.0% | — |


## 测量可信度（时钟 / 流完整性 / 解析开销）

> 上方时延中位数背后的**仪器**可信度：时钟可疑=R-22（|漂移|>100ppm 或端点缺失），该场景 TTFT/ITL 存疑；seq 异常=gap/dup>0；解析开销大会混淆 ITL（端侧算力≠网络）。各信号分母=实际带标注的场景数，未标注**不算干净**。时钟可疑过半标 `时钟可疑热点`。

| 点位 | 运营商 | 时段 | 场景 | 时钟标注 | 时钟可疑 | 漂移中位 ppm | seq 异常 | 解析 us 中位 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 33 | 33 | 3 (9%) | 26.6 | 0/33 | 150.4 | — |
| SZ-PILOT-01 | ctcc | idle | 3 | 3 | 1 (33%) | 24 | 0/3 | 233.8 | low_conf |

## 三级差分归因矩阵（n1_rtt_p50_ms，单位 ms）

> ⚠ **本轮是单层级语料**（覆盖：同城）：三级差分的骨干分解本轮**不可得**，下表只有接入段绝对值；本层**无法判断**这是采集设计如此（如单服务器试点）还是采集缺层——原因须由采集方在方法说明里写明。
> claim_scope: `application_end_to_end_to_probe_node` — 应用层路径分段，非无线层/运营商全网评级。
> 方法：铁律 3 客户端差分消共模；缺层记 coverage 不外推；负增量记 inversion 不清零。
> **前提核对**——共模抵消只在三层级条件相同时成立，逐条列出本表核对到什么程度：
> - **同一时段**：**不适用**（本轮 6 个单元无一覆盖 ≥2 层级，层级间差分不存在，本条无对象可核——不是「已核对」）。`time_band` 只到忙/闲（几小时宽），故另比测量时刻，相隔超 60 分钟标 `TIER_TIME_SPREAD`——那样的增量可能只是**时段差异**穿了骨干的外衣；无时间戳标 `TIER_TIME_UNKNOWN`（**没法查 ≠ 查过了**）。
> - **同一接入**：已核对，但**本轮含义不同**——没有层级间增量，`MIXED_TRANSPORT` 标的是**该格内混了 wifi 与蜂窝**，意思是该格绝对值不可混池，而非「增量不可用」。
> - **层级名副其实**：**不适用**（本轮 6 个单元无一覆盖 ≥2 层级，层级间差分不存在，本条无对象可核——不是「已核对」）。靠 `server_tier_endpoint` 对账。同一个端点被标成两种层级 → 标 `TIER_ENDPOINT_CONFLICT`,**该格的骨干分解不成立**(三层其实打的同一个端);语料无该字段则**无法对账**,不等于对上了。
> - **同一客户端**：**无法核对**（契约无任何设备标识字段）。中途换机的机型差异会整个计入骨干增量且**不会有任何标记**——只能由采集方书面确认（runbook §5 清单）。

| 单元 | 覆盖层级 | 接入(metro) | 区域骨干+ | 核心骨干+ | 端到端(core) | 备注 |
|---|---|---|---|---|---|---|
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · profile_id=s1_chat | 同城 | 65 | — | — | — | TIER_MISSING:regional,core |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 65.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · profile_id=s3_multimodal | 同城 | 62.5 | — | — | — | TIER_MISSING:regional,core |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · profile_id=s1_chat | 同城 | 64.2 | — | — | — | TIER_MISSING:regional,core; low_conf |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 63.4 | — | — | — | TIER_MISSING:regional,core; low_conf |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · profile_id=s3_multimodal | 同城 | 59.4 | — | — | — | TIER_MISSING:regional,core; low_conf |

## 分段异常定位（n1_rtt_p50_ms，同一段跨单元比较，ms）

> **这一段回答的是**：某一段慢，是**这个点位特有**，还是**所有点位都这样**——前者指向该点位，后者是本次测量路径的**共性**（例如到中心镜像端的物理距离），**不构成任何点位的问题**。
> **口径**：与**本语料内**同段各单元的中位数比较，稳健离差 MAD，阈值 `K×1.4826×MAD`，**K 随可比单元数标定**（单元越少，MAD 本身越抖，K 越大）。这是**描述性筛查、不是显著性检验**，也**不与任何外部基准比较**；不可计算的单元不参与比较且如实计数。

> **这个筛查有多准**（每格 60000 次模拟实测，D-200）：K 的标定目标是——在**同分布的干净网格**（不存在真异常）上，误报至少一个单元的概率 ≤5%。**但时延是右偏的**，右偏数据上实测误报率是 7%（4~5 单元）→ 20%（32 单元）→ 26%（48 单元），**随网格变大而升高**（单元越多，长尾越有机会甩出一个）——**所以 `存在单点异常` 的意思是「值得去看一眼」，不是「已证明异常」**。代价也要说清楚：这个阈值只抓得住**很粗的**异常，一个 +5 稳健 σ 的真异常约有一半会被漏掉（+10 σ 才接近必中）。**少于 4 个可比单元时本段拒绝给阈值筛查结论**——那个规模下没有任何阈值达得到上述口径。（**唯一例外**：过半单元取值完全相同时，MAD 退化为 0，「与共同取值不等」是不需要标定的事实，仍如实列出，判读里会写明判据已变。）（此前阈值是固定 3σ，听着严格，实测在干净网格上误报 20%～65%，**32 单元的时延网格三次里有两次会点名一个没问题的点位**。）

> **注意**：`未见单点异常` 只表示**没有单元越过筛查阈值**，**不等于各单元相同**——单元间到底有多齐，看 `离差/典型` 一列。该列小且无异常，才说得上是路径共性。

> **参与单元里若有「样本不足」的**（`参与单元` 列会写出个数）：那些单元**等权**参与离差与筛查——一个只测过一次的单元既能把阈值拉动，也可能**自己被点名**。被点名的单元若本身样本不足，`偏高/偏低` 里会带 `*`：**先补测它，再去现场查**。

| 段 | 参与单元 | 典型值(中位) | 离差(MAD) | 离差/典型 | 偏高 | 偏低 | 判读 |
|---|---|---|---|---|---|---|---|
| 接入(metro) | 6，其中 3 个样本不足 | 63.8 | 1.2 | 1.9% | — | — | **未见单点异常**（K=6×1.4826×MAD；干净网格误报 对称4.7%/右偏9.4%）→ 最大单项落在该段分布内，不宜单独归因于该单元 |
| 区域骨干+ | 0（另 6 不可计算） | — | — | — | — | — | 可比单元不足(<2)，无法比较 |
| 核心骨干+ | 0（另 6 不可计算） | — | — | — | — | — | 可比单元不足(<2)，无法比较 |

## 三级差分归因矩阵（t1_ttft_ms，单位 ms）

> ⚠ **本轮是单层级语料**（覆盖：同城）：三级差分的骨干分解本轮**不可得**，下表只有接入段绝对值；本层**无法判断**这是采集设计如此（如单服务器试点）还是采集缺层——原因须由采集方在方法说明里写明。
> claim_scope: `application_end_to_end_to_probe_node` — 应用层路径分段，非无线层/运营商全网评级。
> 方法：铁律 3 客户端差分消共模；缺层记 coverage 不外推；负增量记 inversion 不清零。
> **前提核对**——共模抵消只在三层级条件相同时成立，逐条列出本表核对到什么程度：
> - **同一时段**：**不适用**（本轮 6 个单元无一覆盖 ≥2 层级，层级间差分不存在，本条无对象可核——不是「已核对」）。`time_band` 只到忙/闲（几小时宽），故另比测量时刻，相隔超 60 分钟标 `TIER_TIME_SPREAD`——那样的增量可能只是**时段差异**穿了骨干的外衣；无时间戳标 `TIER_TIME_UNKNOWN`（**没法查 ≠ 查过了**）。
> - **同一接入**：已核对，但**本轮含义不同**——没有层级间增量，`MIXED_TRANSPORT` 标的是**该格内混了 wifi 与蜂窝**，意思是该格绝对值不可混池，而非「增量不可用」。
> - **层级名副其实**：**不适用**（本轮 6 个单元无一覆盖 ≥2 层级，层级间差分不存在，本条无对象可核——不是「已核对」）。靠 `server_tier_endpoint` 对账。同一个端点被标成两种层级 → 标 `TIER_ENDPOINT_CONFLICT`,**该格的骨干分解不成立**(三层其实打的同一个端);语料无该字段则**无法对账**,不等于对上了。
> - **同一客户端**：**无法核对**（契约无任何设备标识字段）。中途换机的机型差异会整个计入骨干增量且**不会有任何标记**——只能由采集方书面确认（runbook §5 清单）。

| 单元 | 覆盖层级 | 接入(metro) | 区域骨干+ | 核心骨干+ | 端到端(core) | 备注 |
|---|---|---|---|---|---|---|
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · profile_id=s1_chat | 同城 | 53.3 | — | — | — | TIER_MISSING:regional,core |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 54.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · profile_id=s3_multimodal | 同城 | 53 | — | — | — | TIER_MISSING:regional,core |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · profile_id=s1_chat | 同城 | 47.2 | — | — | — | TIER_MISSING:regional,core; low_conf |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 59.3 | — | — | — | TIER_MISSING:regional,core; low_conf |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · profile_id=s3_multimodal | 同城 | 51.2 | — | — | — | TIER_MISSING:regional,core; low_conf |

## 分段异常定位（t1_ttft_ms，同一段跨单元比较，ms）

> **这一段回答的是**：某一段慢，是**这个点位特有**，还是**所有点位都这样**——前者指向该点位，后者是本次测量路径的**共性**（例如到中心镜像端的物理距离），**不构成任何点位的问题**。
> **口径**：与**本语料内**同段各单元的中位数比较，稳健离差 MAD，阈值 `K×1.4826×MAD`，**K 随可比单元数标定**（单元越少，MAD 本身越抖，K 越大）。这是**描述性筛查、不是显著性检验**，也**不与任何外部基准比较**；不可计算的单元不参与比较且如实计数。

> **这个筛查有多准**（每格 60000 次模拟实测，D-200）：K 的标定目标是——在**同分布的干净网格**（不存在真异常）上，误报至少一个单元的概率 ≤5%。**但时延是右偏的**，右偏数据上实测误报率是 7%（4~5 单元）→ 20%（32 单元）→ 26%（48 单元），**随网格变大而升高**（单元越多，长尾越有机会甩出一个）——**所以 `存在单点异常` 的意思是「值得去看一眼」，不是「已证明异常」**。代价也要说清楚：这个阈值只抓得住**很粗的**异常，一个 +5 稳健 σ 的真异常约有一半会被漏掉（+10 σ 才接近必中）。**少于 4 个可比单元时本段拒绝给阈值筛查结论**——那个规模下没有任何阈值达得到上述口径。（**唯一例外**：过半单元取值完全相同时，MAD 退化为 0，「与共同取值不等」是不需要标定的事实，仍如实列出，判读里会写明判据已变。）（此前阈值是固定 3σ，听着严格，实测在干净网格上误报 20%～65%，**32 单元的时延网格三次里有两次会点名一个没问题的点位**。）

> **注意**：`未见单点异常` 只表示**没有单元越过筛查阈值**，**不等于各单元相同**——单元间到底有多齐，看 `离差/典型` 一列。该列小且无异常，才说得上是路径共性。

> **参与单元里若有「样本不足」的**（`参与单元` 列会写出个数）：那些单元**等权**参与离差与筛查——一个只测过一次的单元既能把阈值拉动，也可能**自己被点名**。被点名的单元若本身样本不足，`偏高/偏低` 里会带 `*`：**先补测它，再去现场查**。

| 段 | 参与单元 | 典型值(中位) | 离差(MAD) | 离差/典型 | 偏高 | 偏低 | 判读 |
|---|---|---|---|---|---|---|---|
| 接入(metro) | 6，其中 3 个样本不足 | 53.13 | 1.45 | 2.73% | — | — | **未见单点异常**（K=6×1.4826×MAD；干净网格误报 对称4.7%/右偏9.4%）→ 最大单项落在该段分布内，不宜单独归因于该单元 |
| 区域骨干+ | 0（另 6 不可计算） | — | — | — | — | — | 可比单元不足(<2)，无法比较 |
| 核心骨干+ | 0（另 6 不可计算） | — | — | — | — | — | 可比单元不足(<2)，无法比较 |

## AQS 分数侧归因（各维度子分 + 拖累维度）

> 归因矩阵的分数侧互补：composite AQS 低时，指出是哪个 KPI 维度在拖后腿。子分 0-100，越高越好；`拖累` = 中位子分最低的维度。

| 点位 | 运营商 | 时段 | runs | T1 | T2 | T3 | N1 | N2 | U1 | U2 | 拖累 | 极差 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 11 | 95.9 | 97.7 | 100 | 68.1 | 84.3 | 81.4 | 77.9 | **N1**=68.1 | 31.9 | — |
| SZ-PILOT-01 | ctcc | idle | 1 | 95.6 | 98.1 | 100 | 68.4 | 88.7 | 82.1 | 74.7 | **N1**=68.4 | 31.6 | low_conf |

## 批化(buffering)归因（取证/失真核算）

> **R-05**：批化标注为**取证证据**，**不改判** validity/score（本表亦然）。`none`=未见批化失真；非 `none` 占多数的格标 `失真热点`。空块=未检测（非 0）。

| 点位 | 运营商 | 时段 | n | 未测 | 残差样本中位 | 众数归因 | 批化分中位 | sawtooth | 近零到达 | 疑似占比 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 33 | 0 | 599 | none | 0.028 | 0.023 | 0 | 33% | — |
| SZ-PILOT-01 | ctcc | idle | 3 | 0 | 599 | none | 0.043 | 0.02 | 0 | 33% | low_conf |

## 接入介质对比（wifi vs cellular，AQS 中位）

> transport 取 run 显式设置，`auto` 由各场景 `network_snapshot` 观测共识推得；不一致=mixed、无观测=unknown，**均不并入任何介质**。Δ=cellular−wifi（AQS 越大越好，负值=蜂窝更差）。* = 样本不足。

> **噪声尺度**：Δ 旁的 `±` 是该格测量离散度推得的**指示性**噪声量级（正态近似 SE≈1.253·sd/√n，两格求和取方根）。时延右偏，故它只指示**量级、不是显著性检验**；|Δ| 小于它的格标 `噪声内`——**不应作为改善/回退的结论**。`±0` 只表示这几次复测未观察到离散，**不等于没有噪声**；样本不足的格（标 `low_conf`）其噪声估计本身也不可靠，噪声无法估计时留 `—`、不以 0 顶替。

| 点位 | 运营商 | 时段 | wifi | cellular | Δ(cell−wifi) | 噪声 | 备注 | 其他桶 |
|---|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | — | 89 (n=11) | — | — | — | — |
| SZ-PILOT-01 | ctcc | idle | — | 89.3 (n=1*) | — | — | — | — |

## 无线上下文（信号档与小区一致性）

_本轮语料**不含无线上下文**——这是**采集缺口，不是「信号良好」**。无线量在设备侧已采集(RadioCollector)并被 App 内部消费,但 `ResultReporter` 写入 `network_snapshot` 的只有 transport/capabilities/interface/server_observed_addr,故本层从未见过任何无线取值。三级归因按 D-48 取消后,无线上下文是 `PLAN_ALIGNMENT` §7.3 点名的**第一顺位替代协变量**——接线规格见 `docs/RADIO_CONTEXT_WIRING_SPEC.md`。_

## 纵向趋势

> **本段无数据，不是「全部平稳」。** 本语料有 **1 个带标签战役**，而趋势需要至少 **3** 个才能表达轨迹——两个只够说前后（见「优化前后对比」段），第三轮起本段自动出现。
