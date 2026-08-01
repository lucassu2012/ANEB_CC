# ANEB 战役级综合报告

> # ⛔ 合成数据警告：本报告 512/512 条记录为**合成语料**
> 
> 由 `scripts/synth_campaign.py` **生成**，数字是**虚构的**、**不是实测**。仅供工具链彩排/演示——**不得**作为外场结论、进局点材料或任何对外结论的依据。

> claim_scope: `application_end_to_end_to_probe_node` — 应用层端到指定节点路径；**不表述为** MOS / 无线层评级 / 运营商全网 SLA。
> 输入记录：512；含 run.aqs：512；含 campaign 标签：512。样本地板 min_samples=5。

## 覆盖盘点

- 战役 campaign_id：{'SYNTH-EXP': 512}
- 点位 point_id：{'SYNTH-P01': 76, 'SYNTH-P02': 76, 'SYNTH-P03': 60, 'SYNTH-P04': 60, 'SYNTH-P05': 60, 'SYNTH-P06': 60, 'SYNTH-P07': 60, 'SYNTH-P08': 60}
- 运营商 carrier：{'cmcc': 256, 'cucc': 256}
- 时段 time_band：{'busy': 256, 'idle': 256}
- 服务层级 tier：{'metro': 512}
- run 状态 status：{'completed': 512}
- profile 版本：{'s1@0.2,s2@0.2,s3@0.2': 512}
- 标签来源 label_source：{'declared': 512}
- 采集时间窗：2026-07-13 12:03 UTC → 2026-07-14 05:24 UTC

## 溯源 / provenance（可复现性）

> 工具 `aneb-campaign-analysis/1.0` · 生成 2026-08-01 14:09:53 +0800 · 读 512 行 → 保留 512 条（去重丢 0）。参数 {"min_samples": 5, "attr_kpi": "n1_rtt_p50_ms", "campaign": null, "before": null, "after": null}。

> **生效门限**（改动其一即改变报告结论，复现须同值）：{"cv_gate_percent": 10.0, "stability_max_stable_rows": 25, "validity_min_rate": 0.8, "buffering_hotspot_share": 0.5, "clock_hotspot_share": 0.5, "aqs_grade_bands": [[85.0, "excellent"], [70.0, "good"], [54.0, "fair"], [0.0, "poor"]], "local_day_utc_offset_h": 8, "value_ranges_non_kpi": {"rsrp_dbm": [-160.0, -30.0], "sinr_db": [-30.0, 45.0]}, "rsrp_weak_dbm": -105.0, "rsrp_good_dbm": -95.0, "sinr_weak_db": 0.0, "sinr_good_db": 10.0, "signal_bands": ["weak", "medium", "good"], "signal_labels": {"weak": "弱", "medium": "中", "good": "良"}, "grade_order": ["excellent", "good", "fair", "poor"], "attribution_group_by": ["point_id", "carrier", "time_band", "profile_id"], "stability_group_by": ["campaign_id", "point_id", "carrier", "time_band", "tier", "profile_id"], "heat_kpis": ["t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps", "t2_itl_p95_ms"], "kpi_profile_exclusions": {"u1_goodput_mbps": ["s1_chat"]}, "stability_kpis": ["t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps"], "attribution_kpis": ["n1_rtt_p50_ms", "t1_ttft_ms"], "tier_time_spread_gate_ms": 3600000, "segment_outlier_target_false_alarm": 0.05, "segment_outlier_k_by_cells": [[5, 8.0], [9, 6.0], [1000000000, 5.0]], "segment_min_cells_to_screen": 4, "order_effect_threshold_percent": 10.0, "min_campaigns_for_trend": 3, "median_se_factor": 1.253, "mad_to_sigma": 1.4826, "epoch_ms_bounds": [1577836800000, 4102444800000], "value_ranges": {"aqs_score": [0.0, 100.0], "buffering_score": [0.0, 1.0], "n1_rtt_p50_ms": [0.0, null], "n2_jitter_ms": [0.0, null], "near_zero_arrival_ratio": [0.0, null], "sawtooth_ratio": [0.0, null], "sub_score": [0.0, 100.0], "t1_ttft_ms": [0.0, null], "t2_itl_p95_ms": [0.0, null], "t3_stall_rate": [0.0, 1.0], "t4_severe_stall_rate": [0.0, 1.0], "u1_goodput_mbps": [0.0, null], "u2_tool_loop_p95_ms": [0.0, null]}, "tiers": ["metro", "regional", "core"], "attribution_segments": ["access_component", "regional_backbone_incr", "core_backbone_incr"], "severe_incomparability_flags": ["TIER_TIME_SPREAD", "MIXED_TRANSPORT", "TIER_ENDPOINT_CONFLICT", "IMPLAUSIBLE_VALUE", "VETO_CAPPED", "TIER_INCOMPLETE"], "order_effect_kpis": ["t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps"], "transport_media": ["wifi", "cellular"], "trend_metric_key": "aqs"}

| 输入文件 | sha256 |
|---|---|
| expansion_counted.jsonl | `4497d6adb5d4…` |


## 摘要（先看这里）

> 下列每条中的示例均为该项**最严重的前三个**（其余以「等 N 个」计数，完整清单见对应段落与 CSV）。

- **体验最差格**：32 个格中无 fair/poor（最低 SYNTH-P08/cucc/busy=72）；另有 **2/512 条 run 被打分器自评低置信**（`run.aqs.low_confidence`，热力卡 `SCORER_LOW_CONF`）——**分数自己声明了不确定**，本行的分级不得当作定论。
- **分段归因**（`n1_rtt_p50_ms`；主要贡献段）：接入 60 格；最大单项 SYNTH-P08/cucc/busy/s3_multimodal·接入=57ms；各段**均未见单点异常**（判据：MAD 稳健筛查（K=5×1.4826×MAD，K 随可比单元数标定））——最大单项落在该段分布内，不宜单独归因于该单元（单元间齐不齐见「分段异常定位」段）；**36 个格因不可比标记未计入**（混介质/层级不同时/层级端点冲突/封顶/不可能取值——见归因矩阵）。
- **批化失真热点**：2 个 —— SYNTH-P03/cmcc/busy、SYNTH-P03/cucc/busy。
- **时钟可疑热点**：无。
- **有效率**：全部达门（≥80%）。
- **复测不稳定**：58/288 单元超 CV 门 —— SYNTH-P04/cucc/busy/metro/s1_chat·t1_ttft_ms、SYNTH-P04/cmcc/busy/metro/s3_multimodal·t1_ttft_ms、SYNTH-P04/cucc/idle/metro/s2_coding_agent·t1_ttft_ms 等 58 个。
- **序位效应**：已轮转，但所有 profile 的位次与单元不平衡——**本轮无法校验**是否残留序位偏倚。
- **疑似预热效应**：1/3 个 KPI 首轮系统性更差 —— n1_rtt_p50_ms（首轮劣 21%）（首轮读数偏保守；**跨格比较不受影响**，每格一样冷）。
- **无线上下文**：8/32 个格的无线证据 stale 或过薄——**这些格不足以据此排除信号因素**。
- **蜂窝劣于 wifi**：9 个格超出噪声 —— SYNTH-P07/cucc/busy(Δ-3.2±0.6)、SYNTH-P04/cmcc/busy(Δ-2.8±2.2)、SYNTH-P07/cucc/idle(Δ-2.6±0.5) 等 9 个；另有 2 个格 Δ 在噪声内——**不作介质差异的结论**。
- **分数侧归因**（拖累维度）：U1 32 格；最低 SYNTH-P08/cucc/busy·U1=29.3。
- **优化前后**：本轮仅 1 个战役，无前后可比——「有没有变好」本轮**无法回答**（需第二轮在同样的格上复测）。

> 以上为下方各段的**指路**，证据与完整表格见对应段落；口径与不可计算说明以各段为准。

## 点位 × 忙闲 × 运营商 热力卡（AQS 中位）

> `离散(sd)` 是该格 AQS 的样本标准差。**中位相同、离散天差地别的两个格,读起来一模一样**——sd=0 的格每次都一样,sd=36 的格在 20 与 95 之间来回,两者的中位数不是同一种东西。<2 个样本时留 `—`(离散未知,不是 0)。

| 点位 | 运营商 | 时段 | AQS中位 | 离散(sd) | 分级 | n | 备注 |
|---|---|---|---|---|---|---|---|
| SYNTH-P01 | cmcc | busy | 91.8 | 0.9 | excellent | 19 | **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| SYNTH-P01 | cmcc | idle | 94.9 | 0.9 | excellent | 19 | **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| SYNTH-P01 | cucc | busy | 89.6 | 1.1 | excellent | 19 | **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| SYNTH-P01 | cucc | idle | 93.4 | 0.9 | excellent | 19 | **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| SYNTH-P02 | cmcc | busy | 90 | 0.8 | excellent | 19 | MIXED_MODE:forensic/quick |
| SYNTH-P02 | cmcc | idle | 93.3 | 0.6 | excellent | 19 | MIXED_MODE:forensic/quick |
| SYNTH-P02 | cucc | busy | 88.3 | 0.8 | excellent | 19 | MIXED_MODE:forensic/quick |
| SYNTH-P02 | cucc | idle | 92 | 0.7 | excellent | 19 | MIXED_MODE:forensic/quick |
| SYNTH-P03 | cmcc | busy | 88.8 | 0.8 | excellent | 15 | — |
| SYNTH-P03 | cmcc | idle | 92.9 | 0.9 | excellent | 15 | — |
| SYNTH-P03 | cucc | busy | 86.8 | 0.5 | excellent | 15 | SCORER_LOW_CONF:1/15 |
| SYNTH-P03 | cucc | idle | 91.4 | 0.7 | excellent | 15 | — |
| SYNTH-P04 | cmcc | busy | 88.1 | 3.2 | excellent | 15 | **MIXED_TRANSPORT:cellular/wifi** |
| SYNTH-P04 | cmcc | idle | 91.3 | 3.6 | excellent | 15 | **MIXED_TRANSPORT:cellular/wifi** |
| SYNTH-P04 | cucc | busy | 86 | 3 | excellent | 15 | **MIXED_TRANSPORT:cellular/wifi** |
| SYNTH-P04 | cucc | idle | 91.6 | 3.1 | excellent | 15 | **MIXED_TRANSPORT:cellular/wifi** |
| SYNTH-P05 | cmcc | busy | 86.2 | 0.7 | excellent | 15 | — |
| SYNTH-P05 | cmcc | idle | 91.6 | 0.7 | excellent | 15 | — |
| SYNTH-P05 | cucc | busy | 84.2 | 0.6 | good | 15 | — |
| SYNTH-P05 | cucc | idle | 89.1 | 0.7 | excellent | 15 | — |
| SYNTH-P06 | cmcc | busy | 84.9 | 0.9 | good | 15 | — |
| SYNTH-P06 | cmcc | idle | 90.1 | 0.6 | excellent | 15 | SCORER_LOW_CONF:1/15 |
| SYNTH-P06 | cucc | busy | 82.4 | 0.7 | good | 15 | — |
| SYNTH-P06 | cucc | idle | 88.1 | 0.6 | excellent | 15 | — |
| SYNTH-P07 | cmcc | busy | 84.8 | 1.1 | good | 15 | **MIXED_TRANSPORT:cellular/wifi** |
| SYNTH-P07 | cmcc | idle | 89.9 | 0.7 | excellent | 15 | **MIXED_TRANSPORT:cellular/wifi** |
| SYNTH-P07 | cucc | busy | 82.3 | 1.8 | good | 15 | **MIXED_TRANSPORT:cellular/wifi** |
| SYNTH-P07 | cucc | idle | 88 | 1.4 | excellent | 15 | **MIXED_TRANSPORT:cellular/wifi** |
| SYNTH-P08 | cmcc | busy | 76 | 0.9 | good | 15 | — |
| SYNTH-P08 | cmcc | idle | 82.5 | 0.8 | good | 15 | — |
| SYNTH-P08 | cucc | busy | 72 | 1.1 | good | 15 | — |
| SYNTH-P08 | cucc | idle | 80.2 | 1 | good | 15 | — |

## 分 KPI 热力卡（原始 KPI 中位 + 上报 KpiGrading 分级）

### 分 KPI 热力卡：`t1_ttft_ms`（中位；分级=上报 KpiGrading 众数）

> `profile 跨度` 是该格**各 profile 各自中位**的范围。这张卡把一格里的所有 profile 汇成一个中位，而它们**测的不是同一件事**——实测 `u1_goodput_mbps` 在 s1_chat（上行 ~2KB 文本）只有 0.14 Mbps，在 s3_multimodal 有 16.4 Mbps；中位 10.05 **谁都不代表**。s1_chat 现已按 PO 拍板**排除**出 U1 的跨 profile 汇池（D-366：2KB 在 ~2 个 RTT 内传完，量的是时延不是带宽；被排除的读数以 RULED_OUT 计数如实交代，不静默）。跨度大就别把中位当作「该格的该 KPI」，改看下方「复测稳定性」段的逐 profile 行。

| 点位 | 运营商 | 时段 | 中位 | profile 跨度 | 分级 | n | 备注 |
|---|---|---|---|---|---|---|---|
| SYNTH-P01 | cmcc | busy | 447.7 | 431.8–453.8（3 个 profile） | good | 77 | — |
| SYNTH-P01 | cmcc | idle | 432 | 426.41–437.2（3 个 profile） | good | 77 | — |
| SYNTH-P01 | cucc | busy | 460.4 | 457.33–463.25（3 个 profile） | good | 74 | — |
| SYNTH-P01 | cucc | idle | 437.8 | 429.8–443.5（3 个 profile） | good | 74 | — |
| SYNTH-P02 | cmcc | busy | 462.85 | 453.66–471.9（3 个 profile） | good | 78 | — |
| SYNTH-P02 | cmcc | idle | 435.45 | 421.81–439.4（3 个 profile） | good | 76 | — |
| SYNTH-P02 | cucc | busy | 464.58 | 457.5–467.5（3 个 profile） | good | 71 | — |
| SYNTH-P02 | cucc | idle | 446.95 | 441.6–456.9（3 个 profile） | good | 78 | — |
| SYNTH-P03 | cmcc | busy | 462.2 | 409.14–468.2（3 个 profile） | good | 43 | — |
| SYNTH-P03 | cmcc | idle | 454 | 448.7–458.99（3 个 profile） | good | 41 | — |
| SYNTH-P03 | cucc | busy | 480.5 | 475.3–481.3（3 个 profile） | good | 42 | — |
| SYNTH-P03 | cucc | idle | 455.9 | 447.7–468.2（3 个 profile） | good | 43 | — |
| SYNTH-P04 | cmcc | busy | 453.3 | 415.33–498.15（3 个 profile） | good | 39 | — |
| SYNTH-P04 | cmcc | idle | 451.7 | 414.6–452.9（3 个 profile） | good | 43 | — |
| SYNTH-P04 | cucc | busy | 509 | 497.8–512.31（3 个 profile） | good | 41 | — |
| SYNTH-P04 | cucc | idle | 448.1 | 407.76–471.5（3 个 profile） | good | 41 | — |
| SYNTH-P05 | cmcc | busy | 481.4 | 466.3–489.4（3 个 profile） | good | 42 | — |
| SYNTH-P05 | cmcc | idle | 444.8 | 428.87–451.6（3 个 profile） | good | 45 | — |
| SYNTH-P05 | cucc | busy | 499.95 | 495.1–501.3（3 个 profile） | good | 42 | — |
| SYNTH-P05 | cucc | idle | 466.55 | 463.65–467.1（3 个 profile） | good | 42 | — |
| SYNTH-P06 | cmcc | busy | 490.96 | 487.4–494.2（3 个 profile） | good | 43 | — |
| SYNTH-P06 | cmcc | idle | 459.53 | 455.1–462.2（3 个 profile） | good | 39 | — |
| SYNTH-P06 | cucc | busy | 505.6 | 491.27–507.6（3 个 profile） | good | 45 | — |
| SYNTH-P06 | cucc | idle | 476 | 470.7–482.66（3 个 profile） | good | 43 | — |
| SYNTH-P07 | cmcc | busy | 490.9 | 465.71–498.4（3 个 profile） | good | 42 | — |
| SYNTH-P07 | cmcc | idle | 461.1 | 442.78–470.9（3 个 profile） | good | 40 | — |
| SYNTH-P07 | cucc | busy | 504.55 | 489.1–525.21（3 个 profile） | good | 44 | — |
| SYNTH-P07 | cucc | idle | 465.1 | 439.84–480.4（3 个 profile） | good | 43 | — |
| SYNTH-P08 | cmcc | busy | 536.2 | 518.91–542.15（3 个 profile） | good | 43 | — |
| SYNTH-P08 | cmcc | idle | 495.7 | 487.7–523.29（3 个 profile） | good | 45 | — |
| SYNTH-P08 | cucc | busy | 560 | 536.61–562.5（3 个 profile） | good | 43 | — |
| SYNTH-P08 | cucc | idle | 505 | 499.3–530.61（3 个 profile） | good | 43 | — |

### 分 KPI 热力卡：`n1_rtt_p50_ms`（中位；分级=上报 KpiGrading 众数）

> `profile 跨度` 是该格**各 profile 各自中位**的范围。这张卡把一格里的所有 profile 汇成一个中位，而它们**测的不是同一件事**——实测 `u1_goodput_mbps` 在 s1_chat（上行 ~2KB 文本）只有 0.14 Mbps，在 s3_multimodal 有 16.4 Mbps；中位 10.05 **谁都不代表**。s1_chat 现已按 PO 拍板**排除**出 U1 的跨 profile 汇池（D-366：2KB 在 ~2 个 RTT 内传完，量的是时延不是带宽；被排除的读数以 RULED_OUT 计数如实交代，不静默）。跨度大就别把中位当作「该格的该 KPI」，改看下方「复测稳定性」段的逐 profile 行。

| 点位 | 运营商 | 时段 | 中位 | profile 跨度 | 分级 | n | 备注 |
|---|---|---|---|---|---|---|---|
| SYNTH-P01 | cmcc | busy | 22.82 | 22.45–22.86（3 个 profile） | good | 77 | — |
| SYNTH-P01 | cmcc | idle | 16.91 | 16.83–17.11（3 个 profile） | good | 77 | — |
| SYNTH-P01 | cucc | busy | 25.66 | 25.59–25.7（3 个 profile） | good | 74 | — |
| SYNTH-P01 | cucc | idle | 18.98 | 18.97–19.06（3 个 profile） | good | 74 | — |
| SYNTH-P02 | cmcc | busy | 25.27 | 25.26–25.29（3 个 profile） | good | 78 | — |
| SYNTH-P02 | cmcc | idle | 18.61 | 18.57–18.61（3 个 profile） | good | 76 | — |
| SYNTH-P02 | cucc | busy | 28.09 | 28.08–28.12（3 个 profile） | good | 71 | — |
| SYNTH-P02 | cucc | idle | 20.91 | 20.82–21.04（3 个 profile） | good | 78 | — |
| SYNTH-P03 | cmcc | busy | 27.34 | 27.34–27.34（3 个 profile） | good | 43 | — |
| SYNTH-P03 | cmcc | idle | 19.99 | 19.94–20.11（3 个 profile） | good | 41 | — |
| SYNTH-P03 | cucc | busy | 30.94 | 30.93–30.95（3 个 profile） | good | 42 | — |
| SYNTH-P03 | cucc | idle | 22.5 | 22.5–22.54（3 个 profile） | good | 43 | — |
| SYNTH-P04 | cmcc | busy | 27.32 | 27.04–28.28（3 个 profile） | good | 39 | — |
| SYNTH-P04 | cmcc | idle | 20.01 | 20.01–20.01（3 个 profile） | good | 43 | — |
| SYNTH-P04 | cucc | busy | 32.7 | 32.59–32.71（3 个 profile） | good | 41 | — |
| SYNTH-P04 | cucc | idle | 23.06 | 23.06–23.34（3 个 profile） | good | 41 | — |
| SYNTH-P05 | cmcc | busy | 31.53 | 31.52–31.54（3 个 profile） | good | 42 | — |
| SYNTH-P05 | cmcc | idle | 23.05 | 23.05–23.05（3 个 profile） | good | 45 | — |
| SYNTH-P05 | cucc | busy | 35.01 | 35.01–35.08（3 个 profile） | good | 42 | — |
| SYNTH-P05 | cucc | idle | 26.11 | 26.11–26.11（3 个 profile） | good | 42 | — |
| SYNTH-P06 | cmcc | busy | 33.55 | 33.55–33.6（3 个 profile） | good | 43 | — |
| SYNTH-P06 | cmcc | idle | 24.59 | 24.56–24.59（3 个 profile） | good | 39 | — |
| SYNTH-P06 | cucc | busy | 37.47 | 37.47–37.47（3 个 profile） | good | 45 | — |
| SYNTH-P06 | cucc | idle | 27.86 | 27.86–27.86（3 个 profile） | good | 43 | — |
| SYNTH-P07 | cmcc | busy | 34.3 | 33.43–34.3（3 个 profile） | good | 42 | — |
| SYNTH-P07 | cmcc | idle | 24.78 | 23.83–25.74（3 个 profile） | good | 40 | — |
| SYNTH-P07 | cucc | busy | 39.25 | 39.25–39.45（3 个 profile） | good | 44 | — |
| SYNTH-P07 | cucc | idle | 28.79 | 27.73–28.79（3 个 profile） | good | 43 | — |
| SYNTH-P08 | cmcc | busy | 49.73 | 49.61–49.8（3 个 profile） | fair | 43 | — |
| SYNTH-P08 | cmcc | idle | 36.92 | 36.92–36.92（3 个 profile） | good | 45 | — |
| SYNTH-P08 | cucc | busy | 56.31 | 56.31–57.05（3 个 profile） | fair | 43 | — |
| SYNTH-P08 | cucc | idle | 41.42 | 41.42–41.52（3 个 profile） | fair | 43 | — |

### 分 KPI 热力卡：`u1_goodput_mbps`（中位；分级=上报 KpiGrading 众数）

> `profile 跨度` 是该格**各 profile 各自中位**的范围。这张卡把一格里的所有 profile 汇成一个中位，而它们**测的不是同一件事**——实测 `u1_goodput_mbps` 在 s1_chat（上行 ~2KB 文本）只有 0.14 Mbps，在 s3_multimodal 有 16.4 Mbps；中位 10.05 **谁都不代表**。s1_chat 现已按 PO 拍板**排除**出 U1 的跨 profile 汇池（D-366：2KB 在 ~2 个 RTT 内传完，量的是时延不是带宽；被排除的读数以 RULED_OUT 计数如实交代，不静默）。跨度大就别把中位当作「该格的该 KPI」，改看下方「复测稳定性」段的逐 profile 行。

| 点位 | 运营商 | 时段 | 中位 | profile 跨度 | 分级 | n | 备注 |
|---|---|---|---|---|---|---|---|
| SYNTH-P01 | cmcc | busy | 38.27 | 38.23–38.43（2 个 profile） | good | 52 | RULED_OUT:s1_chat×25（D-366） |
| SYNTH-P01 | cmcc | idle | 42.38 | 42.21–42.74（2 个 profile） | good | 52 | RULED_OUT:s1_chat×25（D-366） |
| SYNTH-P01 | cucc | busy | 36.84 | 36.64–36.86（2 个 profile） | good | 50 | RULED_OUT:s1_chat×24（D-366） |
| SYNTH-P01 | cucc | idle | 41.38 | 40.73–41.42（2 个 profile） | good | 49 | RULED_OUT:s1_chat×25（D-366） |
| SYNTH-P02 | cmcc | busy | 36.51 | 36.3–37.28（2 个 profile） | good | 52 | RULED_OUT:s1_chat×26（D-366） |
| SYNTH-P02 | cmcc | idle | 40.95 | 40.95–41.04（2 个 profile） | good | 53 | RULED_OUT:s1_chat×23（D-366） |
| SYNTH-P02 | cucc | busy | 35.12 | 34.93–35.23（2 个 profile） | good | 49 | RULED_OUT:s1_chat×22（D-366） |
| SYNTH-P02 | cucc | idle | 39.28 | 39.03–39.52（2 个 profile） | good | 52 | RULED_OUT:s1_chat×26（D-366） |
| SYNTH-P03 | cmcc | busy | 35.56 | 35.18–36.58（2 个 profile） | good | 28 | RULED_OUT:s1_chat×15（D-366） |
| SYNTH-P03 | cmcc | idle | 40.75 | 40.52–41.15（2 个 profile） | good | 28 | RULED_OUT:s1_chat×13（D-366） |
| SYNTH-P03 | cucc | busy | 33.73 | 33.69–33.81（2 个 profile） | good | 29 | RULED_OUT:s1_chat×13（D-366） |
| SYNTH-P03 | cucc | idle | 38.83 | 38.75–39.27（2 个 profile） | good | 30 | RULED_OUT:s1_chat×13（D-366） |
| SYNTH-P04 | cmcc | busy | 39.68 | 35.06–40.91（2 个 profile） | good | 25 | RULED_OUT:s1_chat×14（D-366） |
| SYNTH-P04 | cmcc | idle | 39.26 | 38.57–41.52（2 个 profile） | good | 30 | RULED_OUT:s1_chat×13（D-366） |
| SYNTH-P04 | cucc | busy | 37.8 | 34.48–38.64（2 个 profile） | good | 27 | RULED_OUT:s1_chat×14（D-366） |
| SYNTH-P04 | cucc | idle | 38.56 | 38.45–39.24（2 个 profile） | good | 28 | RULED_OUT:s1_chat×13（D-366） |
| SYNTH-P05 | cmcc | busy | 33.5 | 33.42–33.78（2 个 profile） | good | 29 | RULED_OUT:s1_chat×13（D-366） |
| SYNTH-P05 | cmcc | idle | 37.74 | 37.16–38.37（2 个 profile） | good | 30 | RULED_OUT:s1_chat×15（D-366） |
| SYNTH-P05 | cucc | busy | 31.53 | 31.23–31.57（2 个 profile） | good | 29 | RULED_OUT:s1_chat×13（D-366） |
| SYNTH-P05 | cucc | idle | 36.44 | 36.33–36.72（2 个 profile） | good | 28 | RULED_OUT:s1_chat×14（D-366） |
| SYNTH-P06 | cmcc | busy | 33.02 | 32.9–33.06（2 个 profile） | good | 28 | RULED_OUT:s1_chat×15（D-366） |
| SYNTH-P06 | cmcc | idle | 37.5 | 37.28–37.95（2 个 profile） | good | 25 | RULED_OUT:s1_chat×14（D-366） |
| SYNTH-P06 | cucc | busy | 30.7 | 30.56–31.3（2 个 profile） | good | 30 | RULED_OUT:s1_chat×15（D-366） |
| SYNTH-P06 | cucc | idle | 35.51 | 35.26–35.57（2 个 profile） | good | 30 | RULED_OUT:s1_chat×13（D-366） |
| SYNTH-P07 | cmcc | busy | 32.46 | 32.34–33.14（2 个 profile） | good | 27 | RULED_OUT:s1_chat×15（D-366） |
| SYNTH-P07 | cmcc | idle | 37.14 | 37.03–37.17（2 个 profile） | good | 27 | RULED_OUT:s1_chat×13（D-366） |
| SYNTH-P07 | cucc | busy | 31.07 | 30.82–31.08（2 个 profile） | good | 29 | RULED_OUT:s1_chat×15（D-366） |
| SYNTH-P07 | cucc | idle | 34.62 | 34.24–34.91（2 个 profile） | good | 28 | RULED_OUT:s1_chat×15（D-366） |
| SYNTH-P08 | cmcc | busy | 26.85 | 26.82–27（2 个 profile） | fair | 29 | RULED_OUT:s1_chat×14（D-366） |
| SYNTH-P08 | cmcc | idle | 31.5 | 30.96–31.82（2 个 profile） | good | 30 | RULED_OUT:s1_chat×15（D-366） |
| SYNTH-P08 | cucc | busy | 24.64 | 24.61–24.92（2 个 profile） | fair | 28 | RULED_OUT:s1_chat×15（D-366） |
| SYNTH-P08 | cucc | idle | 29.44 | 29.38–29.74（2 个 profile） | fair | 28 | RULED_OUT:s1_chat×15（D-366） |

### 分 KPI 热力卡：`t2_itl_p95_ms`（中位；分级=上报 KpiGrading 众数）

> `profile 跨度` 是该格**各 profile 各自中位**的范围。这张卡把一格里的所有 profile 汇成一个中位，而它们**测的不是同一件事**——实测 `u1_goodput_mbps` 在 s1_chat（上行 ~2KB 文本）只有 0.14 Mbps，在 s3_multimodal 有 16.4 Mbps；中位 10.05 **谁都不代表**。s1_chat 现已按 PO 拍板**排除**出 U1 的跨 profile 汇池（D-366：2KB 在 ~2 个 RTT 内传完，量的是时延不是带宽；被排除的读数以 RULED_OUT 计数如实交代，不静默）。跨度大就别把中位当作「该格的该 KPI」，改看下方「复测稳定性」段的逐 profile 行。

| 点位 | 运营商 | 时段 | 中位 | profile 跨度 | 分级 | n | 备注 |
|---|---|---|---|---|---|---|---|
| SYNTH-P01 | cmcc | busy | 77.8 | 76.36–78.2（3 个 profile） | good | 77 | — |
| SYNTH-P01 | cmcc | idle | 71.7 | 71–71.9（3 个 profile） | good | 77 | — |
| SYNTH-P01 | cucc | busy | 80.7 | 79.14–81.4（3 个 profile） | good | 74 | — |
| SYNTH-P01 | cucc | idle | 75.35 | 74.6–76.65（3 个 profile） | good | 74 | — |
| SYNTH-P02 | cmcc | busy | 80.05 | 78.5–80.6（3 个 profile） | good | 78 | — |
| SYNTH-P02 | cmcc | idle | 74.8 | 70.14–75.15（3 个 profile） | good | 76 | — |
| SYNTH-P02 | cucc | busy | 81.1 | 78.9–82.1（3 个 profile） | good | 71 | — |
| SYNTH-P02 | cucc | idle | 76.85 | 76.2–78.03（3 个 profile） | good | 78 | — |
| SYNTH-P03 | cmcc | busy | 79.7 | 72.55–82.5（3 个 profile） | good | 43 | — |
| SYNTH-P03 | cmcc | idle | 75.7 | 74.9–76.55（3 个 profile） | good | 41 | — |
| SYNTH-P03 | cucc | busy | 84.45 | 84.4–84.8（3 个 profile） | good | 42 | — |
| SYNTH-P03 | cucc | idle | 78.5 | 74.89–80.3（3 个 profile） | good | 43 | — |
| SYNTH-P04 | cmcc | busy | 82.1 | 72–85.98（3 个 profile） | good | 39 | — |
| SYNTH-P04 | cmcc | idle | 74.5 | 72.1–76.6（3 个 profile） | good | 43 | — |
| SYNTH-P04 | cucc | busy | 79.1 | 77.15–95.88（3 个 profile） | good | 41 | — |
| SYNTH-P04 | cucc | idle | 79.9 | 70.6–84.68（3 个 profile） | good | 41 | — |
| SYNTH-P05 | cmcc | busy | 83.45 | 82–84.34（3 个 profile） | good | 42 | — |
| SYNTH-P05 | cmcc | idle | 76.9 | 75.97–78（3 个 profile） | good | 45 | — |
| SYNTH-P05 | cucc | busy | 88.5 | 88.12–88.6（3 个 profile） | good | 42 | — |
| SYNTH-P05 | cucc | idle | 81.45 | 79.9–82.72（3 个 profile） | good | 42 | — |
| SYNTH-P06 | cmcc | busy | 87.8 | 86.65–88.2（3 个 profile） | good | 43 | — |
| SYNTH-P06 | cmcc | idle | 78.1 | 76.47–78.9（3 个 profile） | good | 39 | — |
| SYNTH-P06 | cucc | busy | 89.6 | 88.31–92（3 个 profile） | good | 45 | — |
| SYNTH-P06 | cucc | idle | 82.9 | 82.74–83.3（3 个 profile） | good | 43 | — |
| SYNTH-P07 | cmcc | busy | 85.95 | 77.59–86.9（3 个 profile） | good | 42 | — |
| SYNTH-P07 | cmcc | idle | 79.4 | 77.28–81.6（3 个 profile） | good | 40 | — |
| SYNTH-P07 | cucc | busy | 92.37 | 89.7–93.55（3 个 profile） | good | 44 | — |
| SYNTH-P07 | cucc | idle | 81.45 | 80.68–82.5（3 个 profile） | good | 43 | — |
| SYNTH-P08 | cmcc | busy | 99.5 | 95.68–100.1（3 个 profile） | good | 43 | — |
| SYNTH-P08 | cmcc | idle | 90.5 | 89.9–95.75（3 个 profile） | good | 45 | — |
| SYNTH-P08 | cucc | busy | 104.8 | 104.1–105.5（3 个 profile） | good | 43 | — |
| SYNTH-P08 | cucc | idle | 91.4 | 90.7–95.95（3 个 profile） | good | 43 | — |

## 复测稳定性（CV 门 ≤10%，对齐 M1 验收）

### 复测稳定性：`t1_ttft_ms`（CV% = 样本 stdev/mean；门 ≤10% 为稳定）

> **本表共 96 个单元**：✗超门 35，CV 不可计算 0，其余稳定。摘要的「N/M 单元超 CV 门」即各 KPI 分表这两个数各自相加。

| 单元 | n | 中位 | 均值 | CV% | 稳定? | 备注 |
|---|---|---|---|---|---|---|
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 25 | 453.8 | 454.64 | 4.9 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 26 | 431.8 | 439.1 | 11 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 26 | 447.8 | 450.22 | 5.7 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 25 | 437.2 | 436.23 | 4.2 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 25 | 426.41 | 435.51 | 11 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 27 | 431 | 429.82 | 5.1 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 24 | 463.25 | 464.94 | 4.6 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 27 | 457.33 | 463.59 | 12.9 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 23 | 457.8 | 458.67 | 3.8 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 25 | 429.8 | 433.86 | 4.1 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 24 | 434.64 | 433.21 | 10.9 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 25 | 443.5 | 439.86 | 3.2 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 26 | 460.25 | 458.8 | 3.9 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 27 | 453.66 | 441.87 | 12.5 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 25 | 471.9 | 466.44 | 5.4 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 23 | 435.6 | 436.39 | 4.8 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 27 | 421.81 | 430.31 | 14.5 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 26 | 439.4 | 437.3 | 4.8 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 22 | 457.5 | 464.67 | 4.9 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 23 | 462.24 | 451.24 | 10.7 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 26 | 467.5 | 467.5 | 4.1 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 26 | 441.6 | 443.77 | 4.1 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 26 | 456.9 | 443.22 | 13.4 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 26 | 449.95 | 447.43 | 4.6 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 468.2 | 467.05 | 3.6 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 13 | 409.14 | 434.54 | 11 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 15 | 463.1 | 466.68 | 4 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 452.8 | 452.77 | 2.8 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 14 | 458.99 | 453.28 | 12.7 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 14 | 448.7 | 450.43 | 4.8 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 13 | 481.3 | 486.97 | 3.9 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 475.75 | 478.35 | 13.1 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 15 | 475.3 | 478.99 | 4.7 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 468.2 | 461.38 | 4.8 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 455.67 | 448.2 | 8.6 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 447.7 | 445.69 | 4 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 498.15 | 498.56 | 21.2 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 415.33 | 436.64 | 26.1 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 13 | 447.1 | 439.59 | 27.4 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 452.9 | 447.48 | 25.6 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 443.79 | 446.42 | 17 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 414.6 | 437.79 | 21.7 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 497.8 | 493.83 | 28.2 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 512.31 | 527.8 | 17.5 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 13 | 509 | 517.8 | 16.6 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 427.4 | 450.58 | 15.3 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 13 | 407.76 | 444.66 | 26.8 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 471.5 | 484.03 | 17.9 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 466.3 | 477.61 | 11.9 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 497.4 | 503.66 | 13.7 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 455.1 | 458.4 | 14.1 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 491.27 | 491.54 | 10.3 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 482.66 | 486.87 | 11.2 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 13 | 465.71 | 469.99 | 14.6 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 14 | 442.78 | 446.41 | 13.7 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 525.21 | 511.85 | 14.6 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 14 | 439.84 | 462.26 | 13.5 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 518.91 | 517.88 | 13.2 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 523.29 | 520.92 | 13.6 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 13 | 530.61 | 515 | 16.8 | ✗超门 | — |

> 另有 **36** 个**稳定**单元未列出（表内保留全部 ✗超门、CV 不可计算、含不可能读数的单元，以及前 25 个稳定单元）。完整数据见 `<prefix>_stability.csv`。

### 复测稳定性：`n1_rtt_p50_ms`（CV% = 样本 stdev/mean；门 ≤10% 为稳定）

> **本表共 96 个单元**：✗超门 12，CV 不可计算 0，其余稳定。摘要的「N/M 单元超 CV 门」即各 KPI 分表这两个数各自相加。

| 单元 | n | 中位 | 均值 | CV% | 稳定? | 备注 |
|---|---|---|---|---|---|---|
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 25 | 22.45 | 22.2 | 6.6 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 26 | 22.84 | 22.23 | 6.2 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 26 | 22.86 | 22.38 | 6.8 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 25 | 17.11 | 16.61 | 7 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 25 | 16.83 | 16.54 | 6.9 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 27 | 16.91 | 16.57 | 6.5 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 24 | 25.59 | 25.16 | 5.8 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 27 | 25.66 | 25.28 | 6.2 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 23 | 25.7 | 25.17 | 5.4 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 25 | 19.06 | 18.64 | 5.9 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 24 | 18.97 | 18.56 | 6 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 25 | 18.97 | 18.61 | 5.7 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 26 | 25.26 | 25.2 | 2.7 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 27 | 25.27 | 25.3 | 2.5 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 25 | 25.29 | 25.3 | 2.5 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 23 | 18.61 | 18.61 | 2.1 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 27 | 18.61 | 18.7 | 2.2 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 26 | 18.57 | 18.64 | 2.4 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 22 | 28.12 | 28.23 | 2.8 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 23 | 28.08 | 28.18 | 3.4 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 26 | 28.09 | 28.14 | 2.4 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 26 | 21.04 | 21.01 | 2.4 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 26 | 20.98 | 20.97 | 2.3 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 26 | 20.82 | 20.91 | 2.7 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 27.34 | 27.37 | 2.7 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 27.04 | 27.98 | 11.6 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 27.8 | 28.19 | 10.8 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 13 | 28.28 | 28.46 | 11.2 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 20.01 | 20.63 | 16.1 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 20.01 | 20.57 | 15.5 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 20.01 | 20.57 | 15.5 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 32.71 | 32.12 | 11.2 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 32.65 | 31.75 | 11.2 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 13 | 32.59 | 31.71 | 11.7 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 23.06 | 22.42 | 13.8 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 13 | 23.34 | 22.83 | 12.9 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 23.06 | 22.47 | 12.9 | ✗超门 | — |

> 另有 **59** 个**稳定**单元未列出（表内保留全部 ✗超门、CV 不可计算、含不可能读数的单元，以及前 25 个稳定单元）。完整数据见 `<prefix>_stability.csv`。

### 复测稳定性：`u1_goodput_mbps`（CV% = 样本 stdev/mean；门 ≤10% 为稳定）

> **本表共 96 个单元**：✗超门 11，CV 不可计算 0，其余稳定。摘要的「N/M 单元超 CV 门」即各 KPI 分表这两个数各自相加。

| 单元 | n | 中位 | 均值 | CV% | 稳定? | 备注 |
|---|---|---|---|---|---|---|
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 25 | 38.63 | 38.61 | 4.9 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 26 | 38.43 | 38.72 | 5.4 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 26 | 38.23 | 38.6 | 5.2 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 25 | 42.31 | 42.67 | 5 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 25 | 42.74 | 42.74 | 4.9 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 27 | 42.21 | 42.39 | 4.9 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 24 | 36.74 | 36.73 | 4.4 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 27 | 36.86 | 37.22 | 3.7 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 23 | 36.64 | 36.9 | 5.5 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 25 | 40.96 | 40.95 | 4.9 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 24 | 41.42 | 40.84 | 5.5 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 25 | 40.73 | 40.88 | 5.5 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 26 | 37.23 | 36.99 | 4.3 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 27 | 36.3 | 36.44 | 4.4 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 25 | 37.28 | 36.95 | 4.9 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 23 | 40.8 | 40.82 | 4.1 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 27 | 40.95 | 41 | 4.3 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 26 | 41.04 | 41.14 | 4.4 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 22 | 35.59 | 35.43 | 4.5 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 23 | 34.93 | 35.02 | 5.4 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 26 | 35.23 | 35.25 | 4.1 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 26 | 39.05 | 38.72 | 3.6 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 26 | 39.52 | 39.3 | 4.2 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 26 | 39.03 | 39.25 | 3.6 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 35.73 | 36.03 | 3.4 | 稳定 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 32.43 | 34.79 | 20.7 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 40.91 | 37.8 | 21.1 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 13 | 35.06 | 36.46 | 18.1 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 37.77 | 37.63 | 12.3 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 38.57 | 40.2 | 21.5 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 41.52 | 42.37 | 17.6 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 31.56 | 34.36 | 20.3 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 38.64 | 37.39 | 18 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 13 | 34.48 | 34.7 | 16 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 38.29 | 37.62 | 19.1 | ✗超门 | — |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 39.24 | 39.73 | 21.1 | ✗超门 | — |

> 另有 **60** 个**稳定**单元未列出（表内保留全部 ✗超门、CV 不可计算、含不可能读数的单元，以及前 25 个稳定单元）。完整数据见 `<prefix>_stability.csv`。

## 序位效应诊断（t1_ttft_ms；拉丁方反平衡是否奏效）

> 判据：同 profile 各**执行位次**的中位数极差 / 总体中位数 > 10.0% 即疑似残留序位偏倚（无效应=好结果）。

> 轮转口径：共 3 种轮次，其中 32 条 run **在自身内部**已轮转（`s1,s2,s3|s2,s3,s1` 形状），反平衡在构造上成立。

> ⚠ 3 个 profile 的**执行位次与单元不平衡**（有单元未出现在每个位次）——本诊断把所有单元汇池比较，该前提不成立时位次差**不可单独归因于序位**（可能是点位/运营商/时段差穿了序位的外衣，也可能反过来掩盖真效应）。见备注列。

| profile | 位次中位数 | 极差 | 极差% | 总体中位 | 判定 | 备注 |
|---|---|---|---|---|---|---|
| s1_chat | #0:468.6(n=177) / #1:476(n=153) / #2:463.3(n=147) / #5:446(n=26) / #7:445.1(n=30) | 30.9 | 6.6 | 467.5 | **不可单独归因(单元混杂)** | **CELL_CONFOUNDED:SYNTH-P03/cmcc/busy、SYNTH-P03/cmcc/idle、SYNTH-P03/cucc/busy 等 24 个 未出现在每个位次** |
| s2_coding_agent | #0:465.2(n=154) / #1:460.3(n=176) / #2:469.5(n=150) / #3:423.5(n=31) / #8:445.5(n=31) | 46 | 10 | 462.3 | **不可单独归因(单元混杂)** | **CELL_CONFOUNDED:SYNTH-P03/cmcc/busy、SYNTH-P03/cmcc/idle、SYNTH-P03/cucc/busy 等 24 个 未出现在每个位次** |
| s3_multimodal | #0:469.7(n=149) / #1:473.4(n=153) / #2:462.6(n=184) / #4:443.5(n=31) / #6:447.4(n=30) | 29.9 | 6.4 | 464.7 | **不可单独归因(单元混杂)** | **CELL_CONFOUNDED:SYNTH-P03/cmcc/busy、SYNTH-P03/cmcc/idle、SYNTH-P03/cucc/busy 等 24 个 未出现在每个位次** |

## 序位效应诊断（n1_rtt_p50_ms；拉丁方反平衡是否奏效）

> 判据：同 profile 各**执行位次**的中位数极差 / 总体中位数 > 10.0% 即疑似残留序位偏倚（无效应=好结果）。

> 轮转口径：共 3 种轮次，其中 32 条 run **在自身内部**已轮转（`s1,s2,s3|s2,s3,s1` 形状），反平衡在构造上成立。

> ⚠ 3 个 profile 的**执行位次与单元不平衡**（有单元未出现在每个位次）——本诊断把所有单元汇池比较，该前提不成立时位次差**不可单独归因于序位**（可能是点位/运营商/时段差穿了序位的外衣，也可能反过来掩盖真效应）。见备注列。

| profile | 位次中位数 | 极差 | 极差% | 总体中位 | 判定 | 备注 |
|---|---|---|---|---|---|---|
| s1_chat | #0:26.4(n=177) / #1:26.9(n=153) / #2:26.6(n=147) / #5:21.1(n=26) / #7:22.4(n=30) | 5.8 | 22.3 | 26 | **不可单独归因(单元混杂)** | **CELL_CONFOUNDED:SYNTH-P03/cmcc/busy、SYNTH-P03/cmcc/idle、SYNTH-P03/cucc/busy 等 24 个 未出现在每个位次** |
| s2_coding_agent | #0:26.4(n=154) / #1:26.4(n=176) / #2:26.9(n=150) / #3:21.7(n=31) / #8:21.4(n=31) | 5.5 | 21.2 | 25.9 | **不可单独归因(单元混杂)** | **CELL_CONFOUNDED:SYNTH-P03/cmcc/busy、SYNTH-P03/cmcc/idle、SYNTH-P03/cucc/busy 等 24 个 未出现在每个位次** |
| s3_multimodal | #0:27(n=149) / #1:26.58(n=153) / #2:26.34(n=184) / #4:21.64(n=31) / #6:22.79(n=30) | 5.36 | 20.62 | 26 | **不可单独归因(单元混杂)** | **CELL_CONFOUNDED:SYNTH-P03/cmcc/busy、SYNTH-P03/cmcc/idle、SYNTH-P03/cucc/busy 等 24 个 未出现在每个位次** |

## 序位效应诊断（u1_goodput_mbps；拉丁方反平衡是否奏效）

> 判据：同 profile 各**执行位次**的中位数极差 / 总体中位数 > 10.0% 即疑似残留序位偏倚（无效应=好结果）。

> 轮转口径：共 3 种轮次，其中 32 条 run **在自身内部**已轮转（`s1,s2,s3|s2,s3,s1` 形状），反平衡在构造上成立。

> ⚠ 3 个 profile 的**执行位次与单元不平衡**（有单元未出现在每个位次）——本诊断把所有单元汇池比较，该前提不成立时位次差**不可单独归因于序位**（可能是点位/运营商/时段差穿了序位的外衣，也可能反过来掩盖真效应）。见备注列。

| profile | 位次中位数 | 极差 | 极差% | 总体中位 | 判定 | 备注 |
|---|---|---|---|---|---|---|
| s1_chat | #0:35.7(n=177) / #1:35.5(n=153) / #2:35.7(n=147) / #5:38.8(n=26) / #7:37.9(n=30) | 3.3 | 9.2 | 36 | **不可单独归因(单元混杂)** | **CELL_CONFOUNDED:SYNTH-P03/cmcc/busy、SYNTH-P03/cmcc/idle、SYNTH-P03/cucc/busy 等 24 个 未出现在每个位次** |
| s2_coding_agent | #0:36.8(n=154) / #1:35.8(n=176) / #2:36.4(n=150) / #3:38.7(n=31) / #8:38.3(n=31) | 2.9 | 7.9 | 36.7 | **不可单独归因(单元混杂)** | **CELL_CONFOUNDED:SYNTH-P03/cmcc/busy、SYNTH-P03/cmcc/idle、SYNTH-P03/cucc/busy 等 24 个 未出现在每个位次** |
| s3_multimodal | #0:35.32(n=149) / #1:35.42(n=153) / #2:36.47(n=184) / #4:38.48(n=31) / #6:38.35(n=30) | 3.16 | 8.73 | 36.19 | **不可单独归因(单元混杂)** | **CELL_CONFOUNDED:SYNTH-P03/cmcc/busy、SYNTH-P03/cmcc/idle、SYNTH-P03/cucc/busy 等 24 个 未出现在每个位次** |

## 预热效应（首轮是否系统性更差）

> 判据：首轮中位与**其后各轮中位的中位数**相比差 >10%（按各 KPI 自己的好坏方向；正值=首轮更差）即疑似预热效应。每轮至少 2 个样本才判。

| KPI | 各轮中位(n) | 首轮劣势% | 判定 | 备注 |
|---|---|---|---|---|
| t1_ttft_ms | #0:467.6(n=1443) / #1:439.1(n=88) / #2:446.4(n=91) | 5.6 | 无明显预热 | — |
| n1_rtt_p50_ms | #0:26.61(n=1443) / #1:21.54(n=88) / #2:22.45(n=91) | 21 | **疑似预热效应** | — |
| u1_goodput_mbps | #0:35.83(n=966) / #1:38.58(n=62) / #2:38.29(n=61) | 6.8 | 无明显预热 | RULED_OUT:533（D-366） |

## 有效性与失效原因（每格的有效样本分母）

> 全语料尝试 1728 个场景，可用 1622 （93.9%）；低于 80% 的单元标 `LOW_VALID_RATE`。INVALID 场景 KPI 为空、会被热力卡/归因静默丢弃——**此表即那些被丢弃样本的去向**。

> **有效率的分子是两列之和**：`有效率 =（有效(严格) + 低置信）/ 尝试`。低置信的场景**仍产出了可用测量**，所以它计入分子；**「有效(严格)」那一列不是分子**，拿它去除尝试会得到另一个数——`有效(严格)=0` 与 `有效率=100%` 可以同时成立，且都没错。

> **「未知」的口径**：`validity` 取值不在已知三态内（本层大小写不敏感）即计入**未知**列。**未知按「不可用」计入有效率**——这是保守方向，但它**不是失效**，而是本层读不懂那个状态。故未知占比高的格会标 `UNKNOWN_VALIDITY:x%`：该格的有效率**不应读成「这里全失败了」**，应先去查生产者写了什么。

| 点位 | 运营商 | 时段 | profile | 尝试 | 有效(严格) | 低置信 | 失效 | 未知 | 有效率 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|
| SYNTH-P01 | cmcc | busy | s1_chat | 27 | 22 | 3 | 2 | 0 | 92.6% | — |
| SYNTH-P01 | cmcc | busy | s2_coding_agent | 27 | 21 | 5 | 1 | 0 | 96.3% | — |
| SYNTH-P01 | cmcc | busy | s3_multimodal | 27 | 22 | 4 | 1 | 0 | 96.3% | — |
| SYNTH-P01 | cmcc | idle | s1_chat | 27 | 20 | 5 | 2 | 0 | 92.6% | — |
| SYNTH-P01 | cmcc | idle | s2_coding_agent | 27 | 19 | 6 | 2 | 0 | 92.6% | — |
| SYNTH-P01 | cmcc | idle | s3_multimodal | 27 | 23 | 4 | 0 | 0 | 100.0% | — |
| SYNTH-P01 | cucc | busy | s1_chat | 27 | 19 | 5 | 3 | 0 | 88.9% | — |
| SYNTH-P01 | cucc | busy | s2_coding_agent | 27 | 25 | 2 | 0 | 0 | 100.0% | — |
| SYNTH-P01 | cucc | busy | s3_multimodal | 27 | 21 | 2 | 4 | 0 | 85.2% | — |
| SYNTH-P01 | cucc | idle | s1_chat | 27 | 22 | 3 | 2 | 0 | 92.6% | — |
| SYNTH-P01 | cucc | idle | s2_coding_agent | 27 | 21 | 3 | 3 | 0 | 88.9% | — |
| SYNTH-P01 | cucc | idle | s3_multimodal | 27 | 17 | 8 | 2 | 0 | 92.6% | — |
| SYNTH-P02 | cmcc | busy | s1_chat | 27 | 19 | 7 | 1 | 0 | 96.3% | — |
| SYNTH-P02 | cmcc | busy | s2_coding_agent | 27 | 19 | 8 | 0 | 0 | 100.0% | — |
| SYNTH-P02 | cmcc | busy | s3_multimodal | 27 | 20 | 5 | 2 | 0 | 92.6% | — |
| SYNTH-P02 | cmcc | idle | s1_chat | 27 | 20 | 3 | 4 | 0 | 85.2% | — |
| SYNTH-P02 | cmcc | idle | s2_coding_agent | 27 | 24 | 3 | 0 | 0 | 100.0% | — |
| SYNTH-P02 | cmcc | idle | s3_multimodal | 27 | 21 | 5 | 1 | 0 | 96.3% | — |
| SYNTH-P02 | cucc | busy | s1_chat | 27 | 20 | 2 | 5 | 0 | 81.5% | — |
| SYNTH-P02 | cucc | busy | s2_coding_agent | 27 | 17 | 6 | 4 | 0 | 85.2% | — |
| SYNTH-P02 | cucc | busy | s3_multimodal | 27 | 23 | 3 | 1 | 0 | 96.3% | — |
| SYNTH-P02 | cucc | idle | s1_chat | 27 | 22 | 4 | 1 | 0 | 96.3% | — |
| SYNTH-P02 | cucc | idle | s2_coding_agent | 27 | 26 | 0 | 1 | 0 | 96.3% | — |
| SYNTH-P02 | cucc | idle | s3_multimodal | 27 | 20 | 6 | 1 | 0 | 96.3% | — |
| SYNTH-P03 | cmcc | busy | s1_chat | 15 | 14 | 1 | 0 | 0 | 100.0% | — |
| SYNTH-P03 | cmcc | busy | s2_coding_agent | 15 | 10 | 3 | 2 | 0 | 86.7% | — |
| SYNTH-P03 | cmcc | busy | s3_multimodal | 15 | 11 | 4 | 0 | 0 | 100.0% | — |
| SYNTH-P03 | cmcc | idle | s1_chat | 15 | 12 | 1 | 2 | 0 | 86.7% | — |
| SYNTH-P03 | cmcc | idle | s2_coding_agent | 15 | 13 | 1 | 1 | 0 | 93.3% | — |
| SYNTH-P03 | cmcc | idle | s3_multimodal | 15 | 13 | 1 | 1 | 0 | 93.3% | — |
| SYNTH-P03 | cucc | busy | s1_chat | 15 | 10 | 3 | 2 | 0 | 86.7% | — |
| SYNTH-P03 | cucc | busy | s2_coding_agent | 15 | 13 | 1 | 1 | 0 | 93.3% | — |
| SYNTH-P03 | cucc | busy | s3_multimodal | 15 | 13 | 2 | 0 | 0 | 100.0% | — |
| SYNTH-P03 | cucc | idle | s1_chat | 15 | 13 | 0 | 2 | 0 | 86.7% | — |
| SYNTH-P03 | cucc | idle | s2_coding_agent | 15 | 12 | 3 | 0 | 0 | 100.0% | — |
| SYNTH-P03 | cucc | idle | s3_multimodal | 15 | 11 | 4 | 0 | 0 | 100.0% | — |
| SYNTH-P04 | cmcc | busy | s1_chat | 15 | 10 | 4 | 1 | 0 | 93.3% | — |
| SYNTH-P04 | cmcc | busy | s2_coding_agent | 15 | 10 | 2 | 3 | 0 | 80.0% | — |
| SYNTH-P04 | cmcc | busy | s3_multimodal | 15 | 12 | 1 | 2 | 0 | 86.7% | — |
| SYNTH-P04 | cmcc | idle | s1_chat | 15 | 12 | 1 | 2 | 0 | 86.7% | — |
| SYNTH-P04 | cmcc | idle | s2_coding_agent | 15 | 15 | 0 | 0 | 0 | 100.0% | — |
| SYNTH-P04 | cmcc | idle | s3_multimodal | 15 | 13 | 2 | 0 | 0 | 100.0% | — |
| SYNTH-P04 | cucc | busy | s1_chat | 15 | 11 | 3 | 1 | 0 | 93.3% | — |
| SYNTH-P04 | cucc | busy | s2_coding_agent | 15 | 14 | 0 | 1 | 0 | 93.3% | — |
| SYNTH-P04 | cucc | busy | s3_multimodal | 15 | 12 | 1 | 2 | 0 | 86.7% | — |
| SYNTH-P04 | cucc | idle | s1_chat | 15 | 13 | 0 | 2 | 0 | 86.7% | — |
| SYNTH-P04 | cucc | idle | s2_coding_agent | 15 | 11 | 2 | 2 | 0 | 86.7% | — |
| SYNTH-P04 | cucc | idle | s3_multimodal | 15 | 13 | 2 | 0 | 0 | 100.0% | — |
| SYNTH-P05 | cmcc | busy | s1_chat | 15 | 13 | 0 | 2 | 0 | 86.7% | — |
| SYNTH-P05 | cmcc | busy | s2_coding_agent | 15 | 12 | 2 | 1 | 0 | 93.3% | — |
| SYNTH-P05 | cmcc | busy | s3_multimodal | 15 | 14 | 1 | 0 | 0 | 100.0% | — |
| SYNTH-P05 | cmcc | idle | s1_chat | 15 | 15 | 0 | 0 | 0 | 100.0% | — |
| SYNTH-P05 | cmcc | idle | s2_coding_agent | 15 | 13 | 2 | 0 | 0 | 100.0% | — |
| SYNTH-P05 | cmcc | idle | s3_multimodal | 15 | 12 | 3 | 0 | 0 | 100.0% | — |
| SYNTH-P05 | cucc | busy | s1_chat | 15 | 11 | 2 | 2 | 0 | 86.7% | — |
| SYNTH-P05 | cucc | busy | s2_coding_agent | 15 | 13 | 1 | 1 | 0 | 93.3% | — |
| SYNTH-P05 | cucc | busy | s3_multimodal | 15 | 15 | 0 | 0 | 0 | 100.0% | — |
| SYNTH-P05 | cucc | idle | s1_chat | 15 | 11 | 3 | 1 | 0 | 93.3% | — |
| SYNTH-P05 | cucc | idle | s2_coding_agent | 15 | 12 | 2 | 1 | 0 | 93.3% | — |
| SYNTH-P05 | cucc | idle | s3_multimodal | 15 | 13 | 1 | 1 | 0 | 93.3% | — |
| SYNTH-P06 | cmcc | busy | s1_chat | 15 | 14 | 1 | 0 | 0 | 100.0% | — |
| SYNTH-P06 | cmcc | busy | s2_coding_agent | 15 | 13 | 1 | 1 | 0 | 93.3% | — |
| SYNTH-P06 | cmcc | busy | s3_multimodal | 15 | 13 | 1 | 1 | 0 | 93.3% | — |
| SYNTH-P06 | cmcc | idle | s1_chat | 15 | 11 | 3 | 1 | 0 | 93.3% | — |
| SYNTH-P06 | cmcc | idle | s2_coding_agent | 15 | 9 | 3 | 3 | 0 | 80.0% | — |
| SYNTH-P06 | cmcc | idle | s3_multimodal | 15 | 12 | 1 | 2 | 0 | 86.7% | — |
| SYNTH-P06 | cucc | busy | s1_chat | 15 | 13 | 2 | 0 | 0 | 100.0% | — |
| SYNTH-P06 | cucc | busy | s2_coding_agent | 15 | 13 | 2 | 0 | 0 | 100.0% | — |
| SYNTH-P06 | cucc | busy | s3_multimodal | 15 | 13 | 2 | 0 | 0 | 100.0% | — |
| SYNTH-P06 | cucc | idle | s1_chat | 15 | 12 | 1 | 2 | 0 | 86.7% | — |
| SYNTH-P06 | cucc | idle | s2_coding_agent | 15 | 14 | 1 | 0 | 0 | 100.0% | — |
| SYNTH-P06 | cucc | idle | s3_multimodal | 15 | 14 | 1 | 0 | 0 | 100.0% | — |
| SYNTH-P07 | cmcc | busy | s1_chat | 15 | 11 | 4 | 0 | 0 | 100.0% | — |
| SYNTH-P07 | cmcc | busy | s2_coding_agent | 15 | 12 | 1 | 2 | 0 | 86.7% | — |
| SYNTH-P07 | cmcc | busy | s3_multimodal | 15 | 13 | 1 | 1 | 0 | 93.3% | — |
| SYNTH-P07 | cmcc | idle | s1_chat | 15 | 11 | 2 | 2 | 0 | 86.7% | — |
| SYNTH-P07 | cmcc | idle | s2_coding_agent | 15 | 11 | 3 | 1 | 0 | 93.3% | — |
| SYNTH-P07 | cmcc | idle | s3_multimodal | 15 | 8 | 5 | 2 | 0 | 86.7% | — |
| SYNTH-P07 | cucc | busy | s1_chat | 15 | 13 | 2 | 0 | 0 | 100.0% | — |
| SYNTH-P07 | cucc | busy | s2_coding_agent | 15 | 12 | 3 | 0 | 0 | 100.0% | — |
| SYNTH-P07 | cucc | busy | s3_multimodal | 15 | 11 | 3 | 1 | 0 | 93.3% | — |
| SYNTH-P07 | cucc | idle | s1_chat | 15 | 14 | 1 | 0 | 0 | 100.0% | — |
| SYNTH-P07 | cucc | idle | s2_coding_agent | 15 | 12 | 2 | 1 | 0 | 93.3% | — |
| SYNTH-P07 | cucc | idle | s3_multimodal | 15 | 13 | 1 | 1 | 0 | 93.3% | — |
| SYNTH-P08 | cmcc | busy | s1_chat | 15 | 13 | 1 | 1 | 0 | 93.3% | — |
| SYNTH-P08 | cmcc | busy | s2_coding_agent | 15 | 13 | 2 | 0 | 0 | 100.0% | — |
| SYNTH-P08 | cmcc | busy | s3_multimodal | 15 | 10 | 4 | 1 | 0 | 93.3% | — |
| SYNTH-P08 | cmcc | idle | s1_chat | 15 | 13 | 2 | 0 | 0 | 100.0% | — |
| SYNTH-P08 | cmcc | idle | s2_coding_agent | 15 | 12 | 3 | 0 | 0 | 100.0% | — |
| SYNTH-P08 | cmcc | idle | s3_multimodal | 15 | 14 | 1 | 0 | 0 | 100.0% | — |
| SYNTH-P08 | cucc | busy | s1_chat | 15 | 13 | 2 | 0 | 0 | 100.0% | — |
| SYNTH-P08 | cucc | busy | s2_coding_agent | 15 | 12 | 3 | 0 | 0 | 100.0% | — |
| SYNTH-P08 | cucc | busy | s3_multimodal | 15 | 7 | 6 | 2 | 0 | 86.7% | — |
| SYNTH-P08 | cucc | idle | s1_chat | 15 | 13 | 2 | 0 | 0 | 100.0% | — |
| SYNTH-P08 | cucc | idle | s2_coding_agent | 15 | 12 | 1 | 2 | 0 | 86.7% | — |
| SYNTH-P08 | cucc | idle | s3_multimodal | 15 | 13 | 2 | 0 | 0 | 100.0% | — |

### 失效原因分布

- `CLOCK_OFFSET_SUSPECT` × 42
- `PROFILE_MISMATCH` × 35
- `RETRY_EXHAUSTED` × 35
- `STREAM_ABORTED` × 29

### 有效率趋势（按本地日，UTC+8）

| 日期 | 尝试 | 可用 | 有效率 |
|---|---|---|---|
| 2026-07-13 | 447 | 416 | 93.1% |
| 2026-07-14 | 1281 | 1206 | 94.1% |

> ⚠ 各日**并非测的同一组单元**（SYNTH-P03/cmcc/busy、SYNTH-P03/cucc/busy、SYNTH-P03/cucc/idle 等 23 个未出现在每一天）——率的升降**可能是换了点位/运营商/时段**，而不是装置回归信号。逐单元的率见上表。


## 测量可信度（时钟 / 流完整性 / 解析开销）

> 上方时延中位数背后的**仪器**可信度：时钟可疑=R-22（|漂移|>100ppm 或端点缺失），该场景 TTFT/ITL 存疑；seq 异常=gap/dup>0；解析开销大会混淆 ITL（端侧算力≠网络）。各信号分母=实际带标注的场景数，未标注**不算干净**。时钟可疑过半标 `时钟可疑热点`。

| 点位 | 运营商 | 时段 | 场景 | 时钟标注 | 时钟可疑 | 漂移中位 ppm | seq 异常 | 解析 us 中位 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| SYNTH-P01 | cmcc | busy | 81 | 81 | 0 (0%) | 12.1 | 3/81 | 61.5 | — |
| SYNTH-P01 | cmcc | idle | 81 | 81 | 0 (0%) | 11.9 | 2/81 | 62.6 | — |
| SYNTH-P01 | cucc | busy | 81 | 81 | 0 (0%) | 9.4 | 1/81 | 67.1 | — |
| SYNTH-P01 | cucc | idle | 81 | 81 | 0 (0%) | 13.2 | 4/81 | 60.7 | — |
| SYNTH-P02 | cmcc | busy | 81 | 81 | 32 (40%) | 23.8 | 5/81 | 69.9 | — |
| SYNTH-P02 | cmcc | idle | 81 | 81 | 30 (37%) | 23.5 | 1/81 | 68.2 | — |
| SYNTH-P02 | cucc | busy | 81 | 81 | 31 (38%) | 21.6 | 5/81 | 66.5 | — |
| SYNTH-P02 | cucc | idle | 81 | 81 | 32 (40%) | 22.3 | 8/81 | 68.5 | — |
| SYNTH-P03 | cmcc | busy | 45 | 45 | 0 (0%) | 10.9 | 0/45 | 71.4 | — |
| SYNTH-P03 | cmcc | idle | 45 | 45 | 0 (0%) | 18.5 | 1/45 | 60.6 | — |
| SYNTH-P03 | cucc | busy | 45 | 45 | 0 (0%) | 15.1 | 2/45 | 71.9 | — |
| SYNTH-P03 | cucc | idle | 45 | 45 | 0 (0%) | 13.4 | 2/45 | 64 | — |
| SYNTH-P04 | cmcc | busy | 45 | 45 | 0 (0%) | 12.8 | 5/45 | 65.2 | — |
| SYNTH-P04 | cmcc | idle | 45 | 45 | 0 (0%) | 11.8 | 5/45 | 70.4 | — |
| SYNTH-P04 | cucc | busy | 45 | 45 | 0 (0%) | 10 | 1/45 | 59.8 | — |
| SYNTH-P04 | cucc | idle | 45 | 45 | 0 (0%) | 9.5 | 0/45 | 70.7 | — |
| SYNTH-P05 | cmcc | busy | 45 | 45 | 0 (0%) | 11 | 0/45 | 48.8 | — |
| SYNTH-P05 | cmcc | idle | 45 | 45 | 0 (0%) | 10.9 | 2/45 | 74.1 | — |
| SYNTH-P05 | cucc | busy | 45 | 45 | 0 (0%) | 10.3 | 4/45 | 68.3 | — |
| SYNTH-P05 | cucc | idle | 45 | 45 | 0 (0%) | 13.9 | 1/45 | 69 | — |
| SYNTH-P06 | cmcc | busy | 45 | 45 | 0 (0%) | 14.2 | 0/45 | 61 | — |
| SYNTH-P06 | cmcc | idle | 45 | 45 | 0 (0%) | 11.8 | 1/45 | 66.7 | — |
| SYNTH-P06 | cucc | busy | 45 | 45 | 0 (0%) | 13.1 | 0/45 | 68 | — |
| SYNTH-P06 | cucc | idle | 45 | 45 | 0 (0%) | 11 | 0/45 | 64.1 | — |
| SYNTH-P07 | cmcc | busy | 45 | 45 | 0 (0%) | 11 | 1/45 | 59.4 | — |
| SYNTH-P07 | cmcc | idle | 45 | 45 | 0 (0%) | 8.9 | 3/45 | 70.5 | — |
| SYNTH-P07 | cucc | busy | 45 | 45 | 0 (0%) | 11.7 | 1/45 | 62.9 | — |
| SYNTH-P07 | cucc | idle | 45 | 45 | 0 (0%) | 10.6 | 3/45 | 65.6 | — |
| SYNTH-P08 | cmcc | busy | 45 | 45 | 0 (0%) | 14.6 | 3/45 | 65.9 | — |
| SYNTH-P08 | cmcc | idle | 45 | 45 | 0 (0%) | 7.3 | 3/45 | 66.6 | — |
| SYNTH-P08 | cucc | busy | 45 | 45 | 0 (0%) | 16.5 | 1/45 | 63.4 | — |
| SYNTH-P08 | cucc | idle | 45 | 45 | 0 (0%) | 13.5 | 1/45 | 66.7 | — |

### 低置信定位（per-KPI 样本数）

_语料未携带 `kpi_quality`（v17 之前的生产者）——低置信**无法定位**，不等于没有。_

## 三级差分归因矩阵（n1_rtt_p50_ms，单位 ms）

> ⚠ **本轮是单层级语料**（覆盖：同城）：三级差分的骨干分解本轮**不可得**，下表只有接入段绝对值；本层**无法判断**这是采集设计如此（如单服务器试点）还是采集缺层——原因须由采集方在方法说明里写明。
> claim_scope: `application_end_to_end_to_probe_node` — 应用层路径分段，非无线层/运营商全网评级。
> 方法：铁律 3 客户端差分消共模；缺层记 coverage 不外推；负增量记 inversion 不清零。
> **前提核对**——共模抵消只在三层级条件相同时成立，逐条列出本表核对到什么程度：
> - **同一时段**：**不适用**（本轮 96 个单元无一覆盖 ≥2 层级，层级间差分不存在，本条无对象可核——不是「已核对」）。`time_band` 只到忙/闲（几小时宽），故另比测量时刻，相隔超 60 分钟标 `TIER_TIME_SPREAD`——那样的增量可能只是**时段差异**穿了骨干的外衣；无时间戳标 `TIER_TIME_UNKNOWN`（**没法查 ≠ 查过了**）。
> - **同一接入**：已核对，但**本轮含义不同**——没有层级间增量，`MIXED_TRANSPORT` 标的是**该格内混了 wifi 与蜂窝**，意思是该格绝对值不可混池，而非「增量不可用」。
> - **层级名副其实**：**不适用**（本轮 96 个单元无一覆盖 ≥2 层级，层级间差分不存在，本条无对象可核——不是「已核对」）。靠 `server_tier_endpoint` 对账。同一个端点被标成两种层级 → 标 `TIER_ENDPOINT_CONFLICT`,**该格的骨干分解不成立**(三层其实打的同一个端);语料无该字段则**无法对账**,不等于对上了。
> - **同一客户端**：**无法核对**（契约无任何设备标识字段）。中途换机的机型差异会整个计入骨干增量且**不会有任何标记**——只能由采集方书面确认（runbook §5 清单）。

| 单元 | 覆盖层级 | 接入(metro) | 区域骨干+ | 核心骨干+ | 端到端(core) | 备注 |
|---|---|---|---|---|---|---|
| point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 22.4 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 22.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 22.9 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 17.1 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 16.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 16.9 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 25.6 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 25.7 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 25.7 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 19.1 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 19 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 19 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 25.3 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 25.3 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 25.3 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 18.6 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 18.6 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 18.6 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 28.1 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 28.1 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 28.1 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 21 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 21 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 20.8 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 27.3 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 27.3 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 27.3 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 20.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 20 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 19.9 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 30.9 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 30.9 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 30.9 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 22.5 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 22.5 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 22.5 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 27 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 27.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 28.3 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 20 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 20 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 20 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 32.7 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 32.6 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 32.6 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 23.1 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 23.3 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 23.1 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P05 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 31.5 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 31.5 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 31.5 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 23.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 23.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 23.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 35 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 35.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 35 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 26.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 26.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 26.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 33.5 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 33.6 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 33.6 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 24.6 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 24.6 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 24.6 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 37.5 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 37.5 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 37.5 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 27.9 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 27.9 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 27.9 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P07 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 34.3 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 34.3 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 33.4 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 25.7 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 24.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 23.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 39.2 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 39.2 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 39.4 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 28.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 28.4 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 27.7 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P08 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 49.8 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 49.7 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 49.6 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 36.9 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 36.9 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 36.9 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 56.3 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 56.3 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 57 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 41.4 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 41.5 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 41.4 | — | — | — | TIER_MISSING:regional,core |

## 分段异常定位（n1_rtt_p50_ms，同一段跨单元比较，ms）

> **这一段回答的是**：某一段慢，是**这个点位特有**，还是**所有点位都这样**——前者指向该点位，后者是本次测量路径的**共性**（例如到中心镜像端的物理距离），**不构成任何点位的问题**。
> **口径**：与**本语料内**同段各单元的中位数比较，稳健离差 MAD，阈值 `K×1.4826×MAD`，**K 随可比单元数标定**（单元越少，MAD 本身越抖，K 越大）。这是**描述性筛查、不是显著性检验**，也**不与任何外部基准比较**；不可计算的单元不参与比较且如实计数。

> **这个筛查有多准**（每格 60000 次模拟实测，D-200）：K 的标定目标是——在**同分布的干净网格**（不存在真异常）上，误报至少一个单元的概率 ≤5%。**但时延是右偏的**，右偏数据上实测误报率是 7%（4~5 单元）→ 20%（32 单元）→ 26%（48 单元），**随网格变大而升高**（单元越多，长尾越有机会甩出一个）——**所以 `存在单点异常` 的意思是「值得去看一眼」，不是「已证明异常」**。代价也要说清楚：这个阈值只抓得住**很粗的**异常，一个 +5 稳健 σ 的真异常约有一半会被漏掉（+10 σ 才接近必中）。**少于 4 个可比单元时本段拒绝给阈值筛查结论**——那个规模下没有任何阈值达得到上述口径。（**唯一例外**：过半单元取值完全相同时，MAD 退化为 0，「与共同取值不等」是不需要标定的事实，仍如实列出，判读里会写明判据已变。）（此前阈值是固定 3σ，听着严格，实测在干净网格上误报 20%～65%，**32 单元的时延网格三次里有两次会点名一个没问题的点位**。）

> **注意**：`未见单点异常` 只表示**没有单元越过筛查阈值**，**不等于各单元相同**——单元间到底有多齐，看 `离差/典型` 一列。该列小且无异常，才说得上是路径共性。

> **参与单元里若有「样本不足」的**（`参与单元` 列会写出个数）：那些单元**等权**参与离差与筛查——一个只测过一次的单元既能把阈值拉动，也可能**自己被点名**。被点名的单元若本身样本不足，`偏高/偏低` 里会带 `*`：**先补测它，再去现场查**。

| 段 | 参与单元 | 典型值(中位) | 离差(MAD) | 离差/典型 | 偏高 | 偏低 | 判读 |
|---|---|---|---|---|---|---|---|
| 接入(metro) | 96 | 27.34 | 5.07 | 18.54% | — | — | **未见单点异常**（K=5×1.4826×MAD；干净网格误报 对称0.6%/右偏25.5%）→ 最大单项落在该段分布内，不宜单独归因于该单元 |
| 区域骨干+ | 0（另 96 不可计算） | — | — | — | — | — | 可比单元不足(<2)，无法比较 |
| 核心骨干+ | 0（另 96 不可计算） | — | — | — | — | — | 可比单元不足(<2)，无法比较 |

## 三级差分归因矩阵（t1_ttft_ms，单位 ms）

> ⚠ **本轮是单层级语料**（覆盖：同城）：三级差分的骨干分解本轮**不可得**，下表只有接入段绝对值；本层**无法判断**这是采集设计如此（如单服务器试点）还是采集缺层——原因须由采集方在方法说明里写明。
> claim_scope: `application_end_to_end_to_probe_node` — 应用层路径分段，非无线层/运营商全网评级。
> 方法：铁律 3 客户端差分消共模；缺层记 coverage 不外推；负增量记 inversion 不清零。
> **前提核对**——共模抵消只在三层级条件相同时成立，逐条列出本表核对到什么程度：
> - **同一时段**：**不适用**（本轮 96 个单元无一覆盖 ≥2 层级，层级间差分不存在，本条无对象可核——不是「已核对」）。`time_band` 只到忙/闲（几小时宽），故另比测量时刻，相隔超 60 分钟标 `TIER_TIME_SPREAD`——那样的增量可能只是**时段差异**穿了骨干的外衣；无时间戳标 `TIER_TIME_UNKNOWN`（**没法查 ≠ 查过了**）。
> - **同一接入**：已核对，但**本轮含义不同**——没有层级间增量，`MIXED_TRANSPORT` 标的是**该格内混了 wifi 与蜂窝**，意思是该格绝对值不可混池，而非「增量不可用」。
> - **层级名副其实**：**不适用**（本轮 96 个单元无一覆盖 ≥2 层级，层级间差分不存在，本条无对象可核——不是「已核对」）。靠 `server_tier_endpoint` 对账。同一个端点被标成两种层级 → 标 `TIER_ENDPOINT_CONFLICT`,**该格的骨干分解不成立**(三层其实打的同一个端);语料无该字段则**无法对账**,不等于对上了。
> - **同一客户端**：**无法核对**（契约无任何设备标识字段）。中途换机的机型差异会整个计入骨干增量且**不会有任何标记**——只能由采集方书面确认（runbook §5 清单）。

| 单元 | 覆盖层级 | 接入(metro) | 区域骨干+ | 核心骨干+ | 端到端(core) | 备注 |
|---|---|---|---|---|---|---|
| point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 453.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 431.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 447.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 437.2 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 426.4 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 431 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 463.2 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 457.3 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 457.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 429.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 434.6 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P01 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 443.5 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 460.2 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 453.7 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 471.9 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 435.6 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 421.8 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 439.4 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 457.5 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 462.2 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 467.5 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 441.6 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 456.9 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P02 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 449.9 | — | — | — | TIER_MISSING:regional,core; MIXED_MODE:forensic/quick |
| point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 468.2 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 409.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 463.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 452.8 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 459 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 448.7 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 481.3 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 475.8 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 475.3 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 468.2 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 455.7 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P03 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 447.7 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 498.1 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 415.3 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 447.1 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 452.9 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 443.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 414.6 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 497.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 512.3 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 509 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 427.4 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 407.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P04 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 471.5 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P05 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 479 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 466.3 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 489.4 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 451.6 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 428.9 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 442.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 501.3 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 497.4 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 495.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 465.2 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 463.7 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P05 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 467.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 487.4 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 490.9 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 494.2 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 460.6 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 455.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 462.2 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 505.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 491.3 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 507.6 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 470.7 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 482.7 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P06 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 474.3 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P07 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 491.2 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 465.7 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 498.4 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 470.9 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 442.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 469.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 489.1 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 525.2 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 501.3 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 480.4 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 439.8 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P07 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 464.2 | — | — | — | TIER_MISSING:regional,core; **MIXED_TRANSPORT:cellular/wifi** |
| point_id=SYNTH-P08 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城 | 542.2 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cmcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 518.9 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cmcc · time_band=busy · profile_id=s3_multimodal | 同城 | 540 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城 | 487.7 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cmcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 523.3 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cmcc · time_band=idle · profile_id=s3_multimodal | 同城 | 495.7 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cucc · time_band=busy · profile_id=s1_chat | 同城 | 562.5 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cucc · time_band=busy · profile_id=s2_coding_agent | 同城 | 536.6 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cucc · time_band=busy · profile_id=s3_multimodal | 同城 | 560 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cucc · time_band=idle · profile_id=s1_chat | 同城 | 513.1 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cucc · time_band=idle · profile_id=s2_coding_agent | 同城 | 530.6 | — | — | — | TIER_MISSING:regional,core |
| point_id=SYNTH-P08 · carrier=cucc · time_band=idle · profile_id=s3_multimodal | 同城 | 499.3 | — | — | — | TIER_MISSING:regional,core |

## 分段异常定位（t1_ttft_ms，同一段跨单元比较，ms）

> **这一段回答的是**：某一段慢，是**这个点位特有**，还是**所有点位都这样**——前者指向该点位，后者是本次测量路径的**共性**（例如到中心镜像端的物理距离），**不构成任何点位的问题**。
> **口径**：与**本语料内**同段各单元的中位数比较，稳健离差 MAD，阈值 `K×1.4826×MAD`，**K 随可比单元数标定**（单元越少，MAD 本身越抖，K 越大）。这是**描述性筛查、不是显著性检验**，也**不与任何外部基准比较**；不可计算的单元不参与比较且如实计数。

> **这个筛查有多准**（每格 60000 次模拟实测，D-200）：K 的标定目标是——在**同分布的干净网格**（不存在真异常）上，误报至少一个单元的概率 ≤5%。**但时延是右偏的**，右偏数据上实测误报率是 7%（4~5 单元）→ 20%（32 单元）→ 26%（48 单元），**随网格变大而升高**（单元越多，长尾越有机会甩出一个）——**所以 `存在单点异常` 的意思是「值得去看一眼」，不是「已证明异常」**。代价也要说清楚：这个阈值只抓得住**很粗的**异常，一个 +5 稳健 σ 的真异常约有一半会被漏掉（+10 σ 才接近必中）。**少于 4 个可比单元时本段拒绝给阈值筛查结论**——那个规模下没有任何阈值达得到上述口径。（**唯一例外**：过半单元取值完全相同时，MAD 退化为 0，「与共同取值不等」是不需要标定的事实，仍如实列出，判读里会写明判据已变。）（此前阈值是固定 3σ，听着严格，实测在干净网格上误报 20%～65%，**32 单元的时延网格三次里有两次会点名一个没问题的点位**。）

> **注意**：`未见单点异常` 只表示**没有单元越过筛查阈值**，**不等于各单元相同**——单元间到底有多齐，看 `离差/典型` 一列。该列小且无异常，才说得上是路径共性。

> **参与单元里若有「样本不足」的**（`参与单元` 列会写出个数）：那些单元**等权**参与离差与筛查——一个只测过一次的单元既能把阈值拉动，也可能**自己被点名**。被点名的单元若本身样本不足，`偏高/偏低` 里会带 `*`：**先补测它，再去现场查**。

| 段 | 参与单元 | 典型值(中位) | 离差(MAD) | 离差/典型 | 偏高 | 偏低 | 判读 |
|---|---|---|---|---|---|---|---|
| 接入(metro) | 96 | 466 | 22.8 | 4.9% | — | — | **未见单点异常**（K=5×1.4826×MAD；干净网格误报 对称0.6%/右偏25.5%）→ 最大单项落在该段分布内，不宜单独归因于该单元 |
| 区域骨干+ | 0（另 96 不可计算） | — | — | — | — | — | 可比单元不足(<2)，无法比较 |
| 核心骨干+ | 0（另 96 不可计算） | — | — | — | — | — | 可比单元不足(<2)，无法比较 |

## AQS 分数侧归因（各维度子分 + 拖累维度）

> 归因矩阵的分数侧互补：composite AQS 低时，指出是哪个 KPI 维度在拖后腿。子分 0-100，越高越好；`拖累` = 中位子分最低的维度。

| 点位 | 运营商 | 时段 | runs | T1 | T2 | T3 | N1 | N2 | U1 | U2 | 拖累 | 极差 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SYNTH-P01 | cmcc | busy | 19 | 100 | 96.4 | 97 | 91.8 | 100 | 62.5 | 92.3 | **U1**=62.5 | 37.5 | — |
| SYNTH-P01 | cmcc | idle | 19 | 100 | 99.2 | 100 | 98.2 | 100 | 73.4 | 93.3 | **U1**=73.4 | 26.6 | — |
| SYNTH-P01 | cucc | busy | 19 | 100 | 96.5 | 94.4 | 88.9 | 100 | 57.6 | 92.2 | **U1**=57.6 | 42.4 | — |
| SYNTH-P01 | cucc | idle | 19 | 100 | 98.6 | 100 | 95.8 | 100 | 67.2 | 92.6 | **U1**=67.2 | 32.8 | — |
| SYNTH-P02 | cmcc | busy | 19 | 100 | 96.6 | 94.3 | 89.2 | 100 | 58.1 | 91.7 | **U1**=58.1 | 41.9 | — |
| SYNTH-P02 | cmcc | idle | 19 | 100 | 97.9 | 100 | 96.2 | 100 | 66.3 | 92.9 | **U1**=66.3 | 33.7 | — |
| SYNTH-P02 | cucc | busy | 19 | 100 | 95.1 | 91.7 | 86.2 | 98.6 | 55.2 | 91.4 | **U1**=55.2 | 44.8 | — |
| SYNTH-P02 | cucc | idle | 19 | 100 | 97.3 | 98.7 | 93.8 | 100 | 62.9 | 91.6 | **U1**=62.9 | 37.1 | — |
| SYNTH-P03 | cmcc | busy | 15 | 100 | 95.3 | 92.3 | 87 | 99 | 55.2 | 91.1 | **U1**=55.2 | 44.8 | — |
| SYNTH-P03 | cmcc | idle | 15 | 100 | 97.9 | 99.6 | 94.8 | 100 | 67.2 | 92.4 | **U1**=67.2 | 32.8 | — |
| SYNTH-P03 | cucc | busy | 15 | 100 | 93.7 | 89 | 83.2 | 97.8 | 51.9 | 90.8 | **U1**=51.9 | 48.1 | — |
| SYNTH-P03 | cucc | idle | 15 | 100 | 97.1 | 97 | 92.1 | 100 | 62.3 | 92.2 | **U1**=62.3 | 37.7 | — |
| SYNTH-P04 | cmcc | busy | 15 | 99.7 | 99.1 | 92.4 | 87 | 99 | 47.9 | 90.6 | **U1**=47.9 | 51.8 | — |
| SYNTH-P04 | cmcc | idle | 15 | 100 | 96.5 | 99.1 | 94.7 | 100 | 59.9 | 99.7 | **U1**=59.9 | 40.1 | — |
| SYNTH-P04 | cucc | busy | 15 | 100 | 96.7 | 87.7 | 81.4 | 97.7 | 46.8 | 91.2 | **U1**=46.8 | 53.2 | — |
| SYNTH-P04 | cucc | idle | 15 | 100 | 99.7 | 95.8 | 91.5 | 100 | 61.1 | 97.3 | **U1**=61.1 | 38.9 | — |
| SYNTH-P05 | cmcc | busy | 15 | 100 | 93.9 | 88.6 | 82.6 | 97.8 | 52 | 90.3 | **U1**=52 | 48 | — |
| SYNTH-P05 | cmcc | idle | 15 | 100 | 97.3 | 96.6 | 91.5 | 100 | 61.5 | 92.4 | **U1**=61.5 | 38.5 | — |
| SYNTH-P05 | cucc | busy | 15 | 99.95 | 91.91 | 84.96 | 78.94 | 96.44 | 47.12 | 89.15 | **U1**=47.12 | 52.83 | — |
| SYNTH-P05 | cucc | idle | 15 | 100 | 95 | 93.5 | 88.3 | 99.4 | 55.3 | 92.3 | **U1**=55.3 | 44.7 | — |
| SYNTH-P06 | cmcc | busy | 15 | 100 | 92.1 | 86 | 80.5 | 96.8 | 48.5 | 89.6 | **U1**=48.5 | 51.5 | — |
| SYNTH-P06 | cmcc | idle | 15 | 100 | 96.5 | 95 | 89.9 | 100 | 58.6 | 90.6 | **U1**=58.6 | 41.4 | — |
| SYNTH-P06 | cucc | busy | 15 | 99.8 | 90.4 | 82.6 | 76.3 | 95.2 | 43 | 89.1 | **U1**=43 | 56.8 | — |
| SYNTH-P06 | cucc | idle | 15 | 100 | 94.3 | 91.9 | 86.5 | 98.9 | 53.5 | 90.8 | **U1**=53.5 | 46.5 | — |
| SYNTH-P07 | cmcc | busy | 15 | 100 | 93.7 | 85.9 | 79.7 | 96.4 | 47 | 90.1 | **U1**=47 | 53 | — |
| SYNTH-P07 | cmcc | idle | 15 | 100 | 96 | 94.5 | 88.7 | 100 | 57.1 | 92.3 | **U1**=57.1 | 42.9 | — |
| SYNTH-P07 | cucc | busy | 15 | 100 | 91.4 | 80.9 | 74.5 | 95.2 | 44.1 | 89.1 | **U1**=44.1 | 55.9 | — |
| SYNTH-P07 | cucc | idle | 15 | 100 | 94.6 | 91.4 | 85.5 | 98.8 | 54 | 90.9 | **U1**=54 | 46 | — |
| SYNTH-P08 | cmcc | busy | 15 | 98.27 | 87.13 | 70.78 | 63.44 | 90.88 | 34.33 | 86.99 | **U1**=34.33 | 63.94 | — |
| SYNTH-P08 | cmcc | idle | 15 | 100 | 91.1 | 82.7 | 76.9 | 95.4 | 42.7 | 88.5 | **U1**=42.7 | 57.3 | — |
| SYNTH-P08 | cucc | busy | 15 | 96.9 | 85.2 | 63.8 | 56.5 | 87.8 | 29.3 | 85.4 | **U1**=29.3 | 67.6 | — |
| SYNTH-P08 | cucc | idle | 15 | 99.34 | 90.83 | 79.22 | 72.19 | 93.69 | 39.79 | 89.24 | **U1**=39.79 | 59.55 | — |

## 批化(buffering)归因（取证/失真核算）

> **R-05**：批化标注为**取证证据**，**不改判** validity/score（本表亦然）。`none`=未见批化失真；非 `none` 占多数的格标 `失真热点`。空块=未检测（非 0）。

| 点位 | 运营商 | 时段 | n | 未测 | 残差样本中位 | 众数归因 | 批化分中位 | sawtooth | 近零到达 | 疑似占比 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SYNTH-P01 | cmcc | busy | 81 | 0 | 100 | none | 0.017 | 0.011 | 0 | 0% | — |
| SYNTH-P01 | cmcc | idle | 81 | 0 | 100 | none | 0.016 | 0.008 | 0 | 0% | — |
| SYNTH-P01 | cucc | busy | 81 | 0 | 100 | none | 0.016 | 0.012 | 0 | 0% | — |
| SYNTH-P01 | cucc | idle | 81 | 0 | 100 | none | 0.015 | 0.011 | 0 | 0% | — |
| SYNTH-P02 | cmcc | busy | 81 | 0 | 100 | none | 0.016 | 0.011 | 0 | 0% | — |
| SYNTH-P02 | cmcc | idle | 81 | 0 | 100 | none | 0.018 | 0.01 | 0 | 0% | — |
| SYNTH-P02 | cucc | busy | 81 | 0 | 100 | none | 0.017 | 0.011 | 0 | 0% | — |
| SYNTH-P02 | cucc | idle | 81 | 0 | 100 | none | 0.016 | 0.009 | 0 | 0% | — |
| SYNTH-P03 | cmcc | busy | 45 | 0 | 100 | middlebox_suspect | 0.5 | 0.386 | 0.291 | 100% | **失真热点** |
| SYNTH-P03 | cmcc | idle | 45 | 0 | 100 | none | 0.012 | 0.012 | 0 | 0% | — |
| SYNTH-P03 | cucc | busy | 45 | 0 | 100 | middlebox_suspect | 0.535 | 0.358 | 0.287 | 100% | **失真热点** |
| SYNTH-P03 | cucc | idle | 45 | 0 | 100 | none | 0.012 | 0.012 | 0 | 0% | — |
| SYNTH-P04 | cmcc | busy | 45 | 0 | 100 | none | 0.021 | 0.013 | 0 | 0% | — |
| SYNTH-P04 | cmcc | idle | 45 | 0 | 100 | none | 0.018 | 0.009 | 0 | 0% | — |
| SYNTH-P04 | cucc | busy | 45 | 0 | 100 | none | 0.012 | 0.007 | 0 | 0% | — |
| SYNTH-P04 | cucc | idle | 45 | 0 | 100 | none | 0.016 | 0.008 | 0 | 0% | — |
| SYNTH-P05 | cmcc | busy | 45 | 0 | 100 | none | 0.013 | 0.013 | 0 | 0% | — |
| SYNTH-P05 | cmcc | idle | 45 | 0 | 100 | none | 0.016 | 0.009 | 0 | 0% | — |
| SYNTH-P05 | cucc | busy | 45 | 0 | 100 | none | 0.017 | 0.009 | 0 | 0% | — |
| SYNTH-P05 | cucc | idle | 45 | 0 | 100 | none | 0.017 | 0.009 | 0 | 0% | — |
| SYNTH-P06 | cmcc | busy | 45 | 0 | 100 | none | 0.013 | 0.01 | 0 | 0% | — |
| SYNTH-P06 | cmcc | idle | 45 | 0 | 100 | none | 0.019 | 0.009 | 0 | 0% | — |
| SYNTH-P06 | cucc | busy | 45 | 0 | 100 | none | 0.012 | 0.01 | 0 | 0% | — |
| SYNTH-P06 | cucc | idle | 45 | 0 | 100 | none | 0.017 | 0.008 | 0 | 0% | — |
| SYNTH-P07 | cmcc | busy | 45 | 0 | 100 | none | 0.015 | 0.011 | 0 | 0% | — |
| SYNTH-P07 | cmcc | idle | 45 | 0 | 100 | none | 0.013 | 0.008 | 0 | 0% | — |
| SYNTH-P07 | cucc | busy | 45 | 0 | 100 | none | 0.014 | 0.01 | 0 | 0% | — |
| SYNTH-P07 | cucc | idle | 45 | 0 | 100 | none | 0.017 | 0.008 | 0 | 0% | — |
| SYNTH-P08 | cmcc | busy | 45 | 0 | 100 | none | 0.011 | 0.012 | 0 | 0% | — |
| SYNTH-P08 | cmcc | idle | 45 | 0 | 100 | none | 0.014 | 0.013 | 0 | 0% | — |
| SYNTH-P08 | cucc | busy | 45 | 0 | 100 | none | 0.013 | 0.008 | 0 | 0% | — |
| SYNTH-P08 | cucc | idle | 45 | 0 | 100 | none | 0.015 | 0.011 | 0 | 0% | — |

## 接入介质对比（wifi vs cellular，AQS 中位）

> transport 取 run 显式设置，`auto` 由各场景 `network_snapshot` 观测共识推得；不一致=mixed、无观测=unknown，**均不并入任何介质**。Δ=cellular−wifi（AQS 越大越好，负值=蜂窝更差）。* = 样本不足。

> **噪声尺度**：Δ 旁的 `±` 是该格测量离散度推得的**指示性**噪声量级（正态近似 SE≈1.253·sd/√n，两格求和取方根）。时延右偏，故它只指示**量级、不是显著性检验**；|Δ| 小于它的格标 `噪声内`——**不应作为改善/回退的结论**。`±0` 只表示这几次复测未观察到离散，**不等于没有噪声**；样本不足的格（标 `low_conf`）其噪声估计本身也不可靠，噪声无法估计时留 `—`、不以 0 顶替。

| 点位 | 运营商 | 时段 | wifi | cellular | Δ(cell−wifi) | 噪声 | 备注 | 其他桶 |
|---|---|---|---|---|---|---|---|---|
| SYNTH-P01 | cmcc | busy | 92.3 (n=7) | 91 (n=12) | -1.3 | ±0.4 | — | — |
| SYNTH-P01 | cmcc | idle | 95.4 (n=7) | 94.2 (n=12) | -1.2 | ±0.4 | — | — |
| SYNTH-P01 | cucc | busy | 90.64 (n=7) | 89.47 (n=12) | -1.17 | ±0.6 | — | — |
| SYNTH-P01 | cucc | idle | 94.3 (n=7) | 93.2 (n=12) | -1.1 | ±0.4 | — | — |
| SYNTH-P02 | cmcc | busy | — | 90 (n=19) | — | — | — | — |
| SYNTH-P02 | cmcc | idle | — | 93.3 (n=19) | — | — | — | — |
| SYNTH-P02 | cucc | busy | — | 88.3 (n=19) | — | — | — | — |
| SYNTH-P02 | cucc | idle | — | 92 (n=19) | — | — | — | — |
| SYNTH-P03 | cmcc | busy | — | 88.8 (n=15) | — | — | — | — |
| SYNTH-P03 | cmcc | idle | — | 92.9 (n=15) | — | — | — | — |
| SYNTH-P03 | cucc | busy | — | 86.8 (n=15) | — | — | — | — |
| SYNTH-P03 | cucc | idle | — | 91.4 (n=15) | — | — | — | — |
| SYNTH-P04 | cmcc | busy | 90.06 (n=7) | 87.23 (n=8) | -2.83 | ±2.2 | — | — |
| SYNTH-P04 | cmcc | idle | 92.5 (n=7) | 91 (n=8) | -1.5 | ±2.2 | **噪声内** | — |
| SYNTH-P04 | cucc | busy | 86.1 (n=7) | 85.8 (n=8) | -0.3 | ±2.1 | **噪声内** | — |
| SYNTH-P04 | cucc | idle | 91.6 (n=7) | 91.7 (n=8) | 0.1 | ±2 | **噪声内** | — |
| SYNTH-P05 | cmcc | busy | — | 86.2 (n=15) | — | — | — | — |
| SYNTH-P05 | cmcc | idle | — | 91.6 (n=15) | — | — | — | — |
| SYNTH-P05 | cucc | busy | — | 84.2 (n=15) | — | — | — | — |
| SYNTH-P05 | cucc | idle | — | 89.1 (n=15) | — | — | — | — |
| SYNTH-P06 | cmcc | busy | — | 84.9 (n=15) | — | — | — | — |
| SYNTH-P06 | cmcc | idle | — | 90.1 (n=15) | — | — | — | — |
| SYNTH-P06 | cucc | busy | — | 82.4 (n=15) | — | — | — | — |
| SYNTH-P06 | cucc | idle | — | 88.1 (n=15) | — | — | — | — |
| SYNTH-P07 | cmcc | busy | 85.9 (n=7) | 84.1 (n=8) | -1.8 | ±0.4 | — | — |
| SYNTH-P07 | cmcc | idle | 90.3 (n=7) | 89.4 (n=8) | -0.9 | ±0.3 | — | — |
| SYNTH-P07 | cucc | busy | 84.12 (n=7) | 80.95 (n=8) | -3.17 | ±0.6 | — | — |
| SYNTH-P07 | cucc | idle | 89.25 (n=7) | 86.66 (n=8) | -2.59 | ±0.5 | — | — |
| SYNTH-P08 | cmcc | busy | — | 76 (n=15) | — | — | — | — |
| SYNTH-P08 | cmcc | idle | — | 82.5 (n=15) | — | — | — | — |
| SYNTH-P08 | cucc | busy | — | 72 (n=15) | — | — | — | — |
| SYNTH-P08 | cucc | idle | — | 80.2 (n=15) | — | — | — | — |

## 无线上下文（信号档与小区一致性）

> 信号档沿用 App 侧 R1 判据（`BufferingDetector`）：弱=任一已知分量越线（RSRP<-105dBm 或 SINR<0dB）；良=已知分量均不越线（RSRP≥-95dBm 且 SINR≥10dB）；其余为中。**两个分量都不可得则记 `—`，不记档**。* = 带无线证据的 run 不足。

**档位分布**：弱 8 格 / 中 12 格 / 良 12 格

| 点位 | 运营商 | 时段 | 信号档 | RSRP中位 | SINR中位 | 制式 | 服务小区 | 备注 |
|---|---|---|---|---|---|---|---|---|
| SYNTH-P01 | cmcc | busy | 良 | -85.7 | 14.7 | NR | 1 个 | — |
| SYNTH-P01 | cmcc | idle | 良 | -85.3 | 15.2 | NR | 1 个 | — |
| SYNTH-P01 | cucc | busy | 良 | -85.2 | 15 | NR | 1 个 | — |
| SYNTH-P01 | cucc | idle | 良 | -84.9 | 15.6 | NR | 1 个 | — |
| SYNTH-P02 | cmcc | busy | 良 | -85.4 | 14.9 | NR | 2 个 | **MIXED_SERVING_CELL:2** |
| SYNTH-P02 | cmcc | idle | 良 | -85.1 | 15.1 | NR | 1 个 | — |
| SYNTH-P02 | cucc | busy | 良 | -84.8 | 14.7 | NR | 2 个 | **MIXED_SERVING_CELL:2** |
| SYNTH-P02 | cucc | idle | 良 | -84.9 | 14.6 | NR | 1 个 | — |
| SYNTH-P03 | cmcc | busy | 良 | -85.1 | 15.1 | NR | 1 个 | **RADIO_THIN:每场景中位 1 个读数** |
| SYNTH-P03 | cmcc | idle | 良 | -84.6 | 14.9 | NR | 1 个 | **RADIO_THIN:每场景中位 2 个读数** |
| SYNTH-P03 | cucc | busy | 良 | -86.2 | 15.1 | NR | 1 个 | **RADIO_THIN:每场景中位 1 个读数** |
| SYNTH-P03 | cucc | idle | 良 | -85 | 15.1 | NR | 1 个 | **RADIO_THIN:每场景中位 2 个读数** |
| SYNTH-P04 | cmcc | busy | 中 | -99.3 | 4.9 | NR | 1 个 | — |
| SYNTH-P04 | cmcc | idle | 中 | -100.6 | 5.3 | NR | 1 个 | — |
| SYNTH-P04 | cucc | busy | 中 | -99.2 | 6 | NR | 1 个 | — |
| SYNTH-P04 | cucc | idle | 中 | -99.3 | 5.8 | NR | 1 个 | — |
| SYNTH-P05 | cmcc | busy | 中 | -100.4 | 5 | NR | 1 个 | — |
| SYNTH-P05 | cmcc | idle | 中 | -99.8 | 5 | NR | 1 个 | — |
| SYNTH-P05 | cucc | busy | 中 | -99.5 | 5.3 | NR | 1 个 | — |
| SYNTH-P05 | cucc | idle | 中 | -100.7 | 5.1 | NR | 1 个 | — |
| SYNTH-P06 | cmcc | busy | 中 | -100.4 | 5 | LTE/NR | 1 个 | **MIXED_RAT:LTE/NR** |
| SYNTH-P06 | cmcc | idle | 中 | -99.3 | 5 | LTE/NR | 1 个 | **MIXED_RAT:LTE/NR** |
| SYNTH-P06 | cucc | busy | 中 | -100.1 | 5.4 | LTE/NR | 1 个 | **MIXED_RAT:LTE/NR** |
| SYNTH-P06 | cucc | idle | 中 | -99.8 | 5.1 | LTE/NR | 1 个 | **MIXED_RAT:LTE/NR** |
| SYNTH-P07 | cmcc | busy | 弱 | -112.2 | -2.7 | NR | 1 个 | RADIO_STALE:1 |
| SYNTH-P07 | cmcc | idle | 弱 | -111.3 | -1.5 | NR | 1 个 | RADIO_STALE:1 |
| SYNTH-P07 | cucc | busy | 弱 | -112.1 | -1.6 | NR | 1 个 | RADIO_STALE:1 |
| SYNTH-P07 | cucc | idle | 弱 | -111.2 | -0.7 | NR | 1 个 | RADIO_STALE:1 |
| SYNTH-P08 | cmcc | busy | 弱 | -112.4 | -2.1 | NR | 1 个 | **IMPLAUSIBLE_VALUE:rsrp_dbm>-30×1** |
| SYNTH-P08 | cmcc | idle | 弱 | -111 | -1.8 | NR | 1 个 | **IMPLAUSIBLE_VALUE:rsrp_dbm>-30×1** |
| SYNTH-P08 | cucc | busy | 弱 | -111.7 | -2.2 | NR | 1 个 | **IMPLAUSIBLE_VALUE:rsrp_dbm>-30×1** |
| SYNTH-P08 | cucc | idle | 弱 | -111 | -2.2 | NR | 1 个 | **IMPLAUSIBLE_VALUE:rsrp_dbm>-30×1** |

### 忙闲可比性（同点位是否挂同一小区）

> 三级归因取消后，忙闲对比是仅剩的两个对照维度之一。**若忙时与闲时挂的不是同一小区，该点位的忙闲差里混着小区差**——与 `TIER_ENDPOINT_CONFLICT` 同形，故同样只报不删。

| 点位 | 运营商 | 各时段小区 | 判定 |
|---|---|---|---|
| SYNTH-P01 | cmcc | busy:200-12000-504990; idle:200-12000-504990 | 同一小区 |
| SYNTH-P01 | cucc | busy:200-12000-504990; idle:200-12000-504990 | 同一小区 |
| SYNTH-P02 | cmcc | busy:201-12001-504990/251-12001-504990; idle:201-12001-504990 | **CELL_PARTIAL——部分时段另挂了小区，差值含小区成分** |
| SYNTH-P02 | cucc | busy:201-12001-504990/251-12001-504990; idle:201-12001-504990 | **CELL_PARTIAL——部分时段另挂了小区，差值含小区成分** |
| SYNTH-P03 | cmcc | busy:202-12002-504990; idle:202-12002-504990 | 同一小区 |
| SYNTH-P03 | cucc | busy:202-12002-504990; idle:202-12002-504990 | 同一小区 |
| SYNTH-P04 | cmcc | busy:203-12003-504990; idle:203-12003-504990 | 同一小区 |
| SYNTH-P04 | cucc | busy:203-12003-504990; idle:203-12003-504990 | 同一小区 |
| SYNTH-P05 | cmcc | busy:204-12004-504990; idle:304-12004-504990 | **CELL_CHANGED——该点位忙闲差不可单独归因于时段** |
| SYNTH-P05 | cucc | busy:204-12004-504990; idle:304-12004-504990 | **CELL_CHANGED——该点位忙闲差不可单独归因于时段** |
| SYNTH-P06 | cmcc | busy:205-12005-504990; idle:205-12005-504990 | 同一小区 |
| SYNTH-P06 | cucc | busy:205-12005-504990; idle:205-12005-504990 | 同一小区 |
| SYNTH-P07 | cmcc | busy:206-12006-504990; idle:206-12006-504990 | 同一小区 |
| SYNTH-P07 | cucc | busy:206-12006-504990; idle:206-12006-504990 | 同一小区 |
| SYNTH-P08 | cmcc | busy:207-12007-504990; idle:207-12007-504990 | 同一小区 |
| SYNTH-P08 | cucc | busy:207-12007-504990; idle:207-12007-504990 | 同一小区 |

## 纵向趋势

> **本段无数据，不是「全部平稳」。** 本语料有 **1 个带标签战役**，而趋势需要至少 **3** 个才能表达轨迹——两个只够说前后（见「优化前后对比」段），第三轮起本段自动出现。
