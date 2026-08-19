# ANEB 战役级综合报告

> claim_scope: `application_end_to_end_to_probe_node` — 应用层端到指定节点路径；**不表述为** MOS / 无线层评级 / 运营商全网 SLA。
> 输入记录：73；含 run.aqs：73；含 campaign 标签：73。样本地板 min_samples=5。

## 覆盖盘点

- 战役 campaign_id：{'m3-expansion-wave0': 20, 'm3-expansion-busyband-20260803': 16, 'm2-pilot-20260731': 12, 'warmup-transport-probe': 8, 'm2-afternoonradio-20260801': 4, 'm2-busyradio-20260801': 4, 'm2-idlenight-20260801': 4, 'm2-idleprobe-20260731': 4, 'radiowire-verify-20260801': 1}
- 点位 point_id：{'SZ-PILOT-01': 73}
- 运营商 carrier：{'ctcc': 73}
- 时段 time_band：{'busy': 43, 'idle': 30}
- 服务层级 tier：{'metro': 73}
- run 状态 status：{'completed': 73}
- profile 版本：{'s1_chat@0.2.1;s2_coding_agent@0.2.1;s3_multimodal@0.3.0': 73}
- 标签来源 label_source：{'set': 33, 'set+inferred:time_band(tz=+8)': 24, 'set+inferred:time_band(tz=+8)+t46_relabel:rehearsal_to_real_point_and_campaign_id': 16}
- 采集时间窗：2026-07-31 05:36 UTC → 2026-08-03 18:20 UTC

## 溯源 / provenance（可复现性）

> 工具 `aneb-campaign-analysis/1.0` · 生成 2026-08-19 16:36:44 +0800 · 读 73 行 → 保留 73 条（去重丢 0）。参数 {"min_samples": 5, "attr_kpi": "n1_rtt_p50_ms", "campaign": null, "before": null, "after": null}。

> **生效门限**（改动其一即改变报告结论，复现须同值）：{"cv_gate_percent": 10.0, "stability_max_stable_rows": 25, "validity_min_rate": 0.8, "buffering_hotspot_share": 0.5, "clock_hotspot_share": 0.5, "aqs_grade_bands": [[85.0, "excellent"], [70.0, "good"], [54.0, "fair"], [0.0, "poor"]], "local_day_utc_offset_h": 8, "value_ranges_non_kpi": {"rsrp_dbm": [-160.0, -30.0], "sinr_db": [-30.0, 45.0]}, "rsrp_weak_dbm": -105.0, "rsrp_good_dbm": -95.0, "sinr_weak_db": 0.0, "sinr_good_db": 10.0, "signal_bands": ["weak", "medium", "good"], "signal_labels": {"weak": "弱", "medium": "中", "good": "良"}, "grade_order": ["excellent", "good", "fair", "poor"], "attribution_group_by": ["point_id", "carrier", "time_band", "profile_id"], "stability_group_by": ["campaign_id", "point_id", "carrier", "time_band", "tier", "profile_id"], "heat_kpis": ["t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps", "t2_itl_p95_ms"], "kpi_profile_exclusions": {"u1_goodput_mbps": ["s1_chat"]}, "stability_kpis": ["t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps"], "scenario_side_kpis": ["t1_ttft_ms", "t2_itl_p95_ms", "u2_tool_loop_p95_ms"], "network_side_kpis": ["n1_rtt_p50_ms", "n2_jitter_ms"], "plan_target_effect_pct": 5.0, "plan_max_ok_rows": 25, "plan_power": 0.8, "attribution_kpis": ["n1_rtt_p50_ms", "t1_ttft_ms"], "tier_time_spread_gate_ms": 3600000, "segment_outlier_target_false_alarm": 0.05, "segment_outlier_k_by_cells": [[5, 8.0], [9, 6.0], [1000000000, 5.0]], "segment_min_cells_to_screen": 4, "order_effect_threshold_percent": 10.0, "min_campaigns_for_trend": 3, "median_se_factor": 1.253, "mad_to_sigma": 1.4826, "epoch_ms_bounds": [1577836800000, 4102444800000], "value_ranges": {"aqs_score": [0.0, 100.0], "buffering_score": [0.0, 1.0], "n1_rtt_p50_ms": [0.0, null], "n2_jitter_ms": [0.0, null], "near_zero_arrival_ratio": [0.0, null], "sawtooth_ratio": [0.0, null], "sub_score": [0.0, 100.0], "t1_ttft_ms": [0.0, null], "t2_itl_p95_ms": [0.0, null], "t3_stall_rate": [0.0, 1.0], "t4_severe_stall_rate": [0.0, 1.0], "u1_goodput_mbps": [0.0, null], "u2_tool_loop_p95_ms": [0.0, null]}, "tiers": ["metro", "regional", "core"], "attribution_segments": ["access_component", "regional_backbone_incr", "core_backbone_incr"], "severe_incomparability_flags": ["TIER_TIME_SPREAD", "MIXED_TRANSPORT", "TIER_ENDPOINT_CONFLICT", "IMPLAUSIBLE_VALUE", "VETO_CAPPED", "TIER_INCOMPLETE"], "order_effect_kpis": ["t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps"], "transport_media": ["wifi", "cellular"], "trend_metric_key": "aqs"}

| 输入文件 | sha256 |
|---|---|
| full_corpus_labelled.jsonl | `3cb73024d916…` |


> ⚠ **`time_band` 有 40/73 条是工具推断的**（按 `started_at_epoch_ms` 的本地小时,非现场记录;规则与所用时区偏移见「覆盖盘点」的 `label_source`）。忙闲差异的结论**须注明这一点**——推断错时段会把两类流量混在一起,而表面上看不出来。

> ⚠ 本语料含 **9 个战役**（m2-afternoonradio-20260801, m2-busyradio-20260801, m2-idlenight-20260801, m2-idleprobe-20260731, m2-pilot-20260731, m3-expansion-busyband-20260803, m3-expansion-wave0, radiowire-verify-20260801, warmup-transport-probe）。除「优化前后对比」/「纵向趋势」两段外，**各段均按格池化了所有战役**——受影响的格标 `MIXED_CAMPAIGN`，其中位数**既不是前也不是后**。要看单个战役，用 `--campaign <id>`。

## 摘要（先看这里）

> 下列每条中的示例均为该项**最严重的前三个**（其余以「等 N 个」计数，完整清单见对应段落与 CSV）。

- **体验最差格**：2 个格中无 fair/poor（最低 SZ-PILOT-01/ctcc/idle=87.2）；且这 **73 条 run 全部被打分器自评低置信**（`run.aqs.low_confidence`，热力卡 `SCORER_LOW_CONF`）——**分数自己声明了不确定**，本行的分级不得当作定论。
- **分段归因**（`n1_rtt_p50_ms`；主要贡献段）：接入 3 格；最大单项 SZ-PILOT-01/ctcc/idle/s2_coding_agent·接入=73.1ms；各段**均未见单点异常**（判据：MAD 稳健筛查（K=6×1.4826×MAD，K 随可比单元数标定））——最大单项落在该段分布内，不宜单独归因于该单元（单元间齐不齐见「分段异常定位」段）；**3 个格因不可比标记未计入**（混介质/层级不同时/层级端点冲突/封顶/不可能取值——见归因矩阵）。
- **批化失真**：无热点格。
- **时钟可疑热点**：无。
- **有效率**：全部达门（≥80%）。
- **复测不稳定**：19/72 单元超 CV 门 —— SZ-PILOT-01/ctcc/busy/metro/s1_chat·t1_ttft_ms、SZ-PILOT-01/ctcc/busy/metro/s3_multimodal·u1_goodput_mbps、SZ-PILOT-01/ctcc/busy/metro/s1_chat·n1_rtt_p50_ms 等 19 个；另有 **18 个单元 CV 不可计算**（n<2 或均值≤0，**未计入分母**，见稳定性段**备注**列的 `CV 不可计算` 标记）。
- **疑似序位偏倚**：1/9 处位置-KPI 相关 —— s1_chat/n1_rtt_p50_ms（极差 12.5%）（反平衡可能失效，**本报告的 KPI 中位数据此存疑**）。
- **疑似预热效应**：1/3 个 KPI 首轮系统性更差 —— u1_goodput_mbps（首轮劣 13.4%）（首轮读数偏保守；**跨格比较不受影响**，每格一样冷）。
- **无线上下文**：1/2 个格的无线证据 stale 或过薄——**这些格不足以据此排除信号因素**。
- **接入介质**：无同格双介质可比，或蜂窝不劣于 wifi。
- **分数侧归因**（拖累维度）：N1 2 格；最低 SZ-PILOT-01/ctcc/idle·N1=66.1。
- **纵向趋势**（9 个战役）：improving 1 格、noise_unknown 1 格。

> 以上为下方各段的**指路**，证据与完整表格见对应段落；口径与不可计算说明以各段为准。

## 点位 × 忙闲 × 运营商 热力卡（AQS 中位）

> `离散(sd)` 是该格 AQS 的样本标准差。**中位相同、离散天差地别的两个格,读起来一模一样**——sd=0 的格每次都一样,sd=36 的格在 20 与 95 之间来回,两者的中位数不是同一种东西。<2 个样本时留 `—`(离散未知,不是 0)。

| 点位 | 运营商 | 时段 | AQS中位 | 离散(sd) | 分级 | n | 备注 |
|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 89.8 | 1.2 | excellent | 43 | SCORER_LOW_CONF:43/43; MIXED_CAMPAIGN:m2-afternoonradio-20260801/m2-busyradio-20260801/m2-pilot-20260731/m3-expansion-busyband-20260803/warmup-transport-probe; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| SZ-PILOT-01 | ctcc | idle | 87.2 | 1.3 | excellent | 30 | SCORER_LOW_CONF:30/30; MIXED_CAMPAIGN:m2-idlenight-20260801/m2-idleprobe-20260731/m2-pilot-20260731/m3-expansion-wave0/radiowire-verify-20260801; MIXED_MODE:forensic/quick |

## 分 KPI 热力卡（原始 KPI 中位 + 上报 KpiGrading 分级）

### 分 KPI 热力卡：`t1_ttft_ms`（中位；分级=上报 KpiGrading 众数）

> `profile 跨度` 是该格**各 profile 各自中位**的范围。这张卡把一格里的所有 profile 汇成一个中位，而它们**测的不是同一件事**——实测 `u1_goodput_mbps` 在 s1_chat（上行 ~2KB 文本）只有 0.14 Mbps，在 s3_multimodal 有 16.4 Mbps；中位 10.05 **谁都不代表**。s1_chat 现已按 PO 拍板**排除**出 U1 的跨 profile 汇池（D-366：2KB 在 ~2 个 RTT 内传完，量的是时延不是带宽；被排除的读数以 RULED_OUT 计数如实交代，不静默）。跨度大就别把中位当作「该格的该 KPI」，改看下方「复测稳定性」段的逐 profile 行。

| 点位 | 运营商 | 时段 | 中位 | profile 跨度 | 分级 | n | 备注 |
|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 53.13 | 52.77–54.78（3 个 profile） | excellent | 321 | MIXED_CAMPAIGN:m2-afternoonradio-20260801/m2-busyradio-20260801/m2-pilot-20260731/m3-expansion-busyband-20260803/warmup-transport-probe |
| SZ-PILOT-01 | ctcc | idle | 61.78 | 54.55–64.06（3 个 profile） | excellent | 168 | MIXED_CAMPAIGN:m2-idlenight-20260801/m2-idleprobe-20260731/m2-pilot-20260731/m3-expansion-wave0/radiowire-verify-20260801 |

### 分 KPI 热力卡：`n1_rtt_p50_ms`（中位；分级=上报 KpiGrading 众数）

> `profile 跨度` 是该格**各 profile 各自中位**的范围。这张卡把一格里的所有 profile 汇成一个中位，而它们**测的不是同一件事**——实测 `u1_goodput_mbps` 在 s1_chat（上行 ~2KB 文本）只有 0.14 Mbps，在 s3_multimodal 有 16.4 Mbps；中位 10.05 **谁都不代表**。s1_chat 现已按 PO 拍板**排除**出 U1 的跨 profile 汇池（D-366：2KB 在 ~2 个 RTT 内传完，量的是时延不是带宽；被排除的读数以 RULED_OUT 计数如实交代，不静默）。跨度大就别把中位当作「该格的该 KPI」，改看下方「复测稳定性」段的逐 profile 行。

| 点位 | 运营商 | 时段 | 中位 | profile 跨度 | 分级 | n | 备注 |
|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 64.25 | 62.85–65.23（3 个 profile） | fair | 321 | MIXED_CAMPAIGN:m2-afternoonradio-20260801/m2-busyradio-20260801/m2-pilot-20260731/m3-expansion-busyband-20260803/warmup-transport-probe |
| SZ-PILOT-01 | ctcc | idle | 71.71 | 70.52–73.13（3 个 profile） | fair | 168 | MIXED_CAMPAIGN:m2-idlenight-20260801/m2-idleprobe-20260731/m2-pilot-20260731/m3-expansion-wave0/radiowire-verify-20260801 |

### 分 KPI 热力卡：`u1_goodput_mbps`（中位；分级=上报 KpiGrading 众数）

> `profile 跨度` 是该格**各 profile 各自中位**的范围。这张卡把一格里的所有 profile 汇成一个中位，而它们**测的不是同一件事**——实测 `u1_goodput_mbps` 在 s1_chat（上行 ~2KB 文本）只有 0.14 Mbps，在 s3_multimodal 有 16.4 Mbps；中位 10.05 **谁都不代表**。s1_chat 现已按 PO 拍板**排除**出 U1 的跨 profile 汇池（D-366：2KB 在 ~2 个 RTT 内传完，量的是时延不是带宽；被排除的读数以 RULED_OUT 计数如实交代，不静默）。跨度大就别把中位当作「该格的该 KPI」，改看下方「复测稳定性」段的逐 profile 行。

| 点位 | 运营商 | 时段 | 中位 | profile 跨度 | 分级 | n | 备注 |
|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 12.82 | 10.53–16.64（2 个 profile） | good | 214 | MIXED_CAMPAIGN:m2-afternoonradio-20260801/m2-busyradio-20260801/m2-pilot-20260731/m3-expansion-busyband-20260803/warmup-transport-probe; RULED_OUT:s1_chat×107（D-366） |
| SZ-PILOT-01 | ctcc | idle | 5.33 | 4.79–5.42（2 个 profile） | good | 112 | MIXED_CAMPAIGN:m2-idlenight-20260801/m2-idleprobe-20260731/m2-pilot-20260731/m3-expansion-wave0/radiowire-verify-20260801; RULED_OUT:s1_chat×56（D-366） |

### 分 KPI 热力卡：`t2_itl_p95_ms`（中位；分级=上报 KpiGrading 众数）

> `profile 跨度` 是该格**各 profile 各自中位**的范围。这张卡把一格里的所有 profile 汇成一个中位，而它们**测的不是同一件事**——实测 `u1_goodput_mbps` 在 s1_chat（上行 ~2KB 文本）只有 0.14 Mbps，在 s3_multimodal 有 16.4 Mbps；中位 10.05 **谁都不代表**。s1_chat 现已按 PO 拍板**排除**出 U1 的跨 profile 汇池（D-366：2KB 在 ~2 个 RTT 内传完，量的是时延不是带宽；被排除的读数以 RULED_OUT 计数如实交代，不静默）。跨度大就别把中位当作「该格的该 KPI」，改看下方「复测稳定性」段的逐 profile 行。

| 点位 | 运营商 | 时段 | 中位 | profile 跨度 | 分级 | n | 备注 |
|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 27.97 | 13.39–29.73（3 个 profile） | excellent | 321 | MIXED_CAMPAIGN:m2-afternoonradio-20260801/m2-busyradio-20260801/m2-pilot-20260731/m3-expansion-busyband-20260803/warmup-transport-probe |
| SZ-PILOT-01 | ctcc | idle | 31.43 | 20.63–35.68（3 个 profile） | excellent | 168 | MIXED_CAMPAIGN:m2-idlenight-20260801/m2-idleprobe-20260731/m2-pilot-20260731/m3-expansion-wave0/radiowire-verify-20260801 |

## 复测稳定性（CV 门 ≤10%，对齐 M1 验收）

### 复测稳定性：`t1_ttft_ms`（CV% = 样本 stdev/mean；门 ≤10% 为稳定）

> **本表共 30 个单元**：✗超门 10，CV 不可计算 6，其余稳定。摘要的「N/M 单元超 CV 门」即各 KPI 分表这两个数各自相加。

> **场景内生抖动判据**（承 D-372）：同格同 profile 下本 KPI 超 CV 门、而网络侧（`n1_rtt_p50_ms`/`n2_jitter_ms`）**未**超门的单元标 `SCENARIO_INTRINSIC_JITTER`（**场景内生抖动**）——D-372 实测同批 RTT 平稳而 TTFT 独抖、两者相关 0.00，故**这些单元的 `需 n≥` 不是加测网络样本的理由**（加 run 只是把一个不在链路上的方差摊薄）。**本表 0 个**。

| 单元 | n | 中位 | 均值 | CV% | 稳定? | 备注 |
|---|---|---|---|---|---|---|
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 12 | 60.03 | 59.84 | 7.4 | 稳定 | — |
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 61.13 | 60.45 | 6.9 | 稳定 | — |
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 12 | 63.95 | 62.68 | 7.3 | 稳定 | — |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 12 | 59.31 | 60.73 | 15.5 | ✗超门 | — |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 61.93 | 62.18 | 4.7 | 稳定 | — |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 12 | 64.14 | 65 | 6.5 | 稳定 | — |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 12 | 57.12 | 58.25 | 10.2 | ✗超门 | — |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 62.31 | 62.88 | 4.1 | 稳定 | — |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 12 | 64.3 | 64.97 | 5 | 稳定 | — |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 12 | 59.61 | 59.94 | 11.1 | ✗超门 | — |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 63.61 | 62.38 | 4.9 | 稳定 | — |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 12 | 62.74 | 63.7 | 9.3 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 11 | 53.26 | 53.05 | 5.5 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 11 | 54.07 | 54.85 | 10.3 | ✗超门 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 11 | 53.01 | 53.26 | 5.9 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 1 | 47.19 | 47.19 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 1 | 59.32 | 59.32 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 1 | 51.17 | 51.17 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 48 | 51.03 | 50.77 | 8 | 稳定 | — |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 48 | 51.21 | 52.1 | 7.5 | 稳定 | — |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 48 | 50.39 | 51.33 | 6.5 | 稳定 | — |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 30 | 50.49 | 51.28 | 13.9 | ✗超门 | — |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 30 | 65.63 | 64.9 | 12.8 | ✗超门 | — |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 30 | 62.37 | 64.17 | 14.9 | ✗超门 | — |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 1 | 62.45 | 62.45 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 1 | 60.63 | 60.63 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 1 | 62.18 | 62.18 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 24 | 64.5 | 67.96 | 35.3 | ✗超门 | — |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 24 | 68.55 | 67.98 | 27.1 | ✗超门 | — |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 24 | 69 | 66.9 | 26.7 | ✗超门 | — |

### 复测稳定性：`n1_rtt_p50_ms`（CV% = 样本 stdev/mean；门 ≤10% 为稳定）

> **本表共 30 个单元**：✗超门 5，CV 不可计算 6，其余稳定。摘要的「N/M 单元超 CV 门」即各 KPI 分表这两个数各自相加。

| 单元 | n | 中位 | 均值 | CV% | 稳定? | 备注 |
|---|---|---|---|---|---|---|
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 12 | 68.59 | 69.43 | 3.4 | 稳定 | — |
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 71.3 | 70.98 | 3.6 | 稳定 | — |
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 12 | 69.71 | 70.09 | 1.8 | 稳定 | — |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 12 | 68.62 | 70.69 | 4.7 | 稳定 | — |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 70.61 | 70.39 | 3.3 | 稳定 | — |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 12 | 68.53 | 69.36 | 3.2 | 稳定 | — |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 12 | 69.2 | 70.66 | 4.4 | 稳定 | — |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 71.05 | 71.04 | 3.5 | 稳定 | — |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 12 | 71.48 | 70.94 | 3.3 | 稳定 | — |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 12 | 70.44 | 70.64 | 3.6 | 稳定 | — |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 71.08 | 72.08 | 3.7 | 稳定 | — |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 12 | 70.18 | 70.07 | 3.1 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 11 | 65.03 | 65.37 | 3.3 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 11 | 65.07 | 64.17 | 3.6 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 11 | 62.55 | 62.58 | 4.4 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 1 | 64.19 | 64.19 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 1 | 63.41 | 63.41 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 1 | 59.38 | 59.38 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 48 | 57.89 | 59.78 | 9.3 | 稳定 | — |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 48 | 60.43 | 60.49 | 8.6 | 稳定 | — |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 48 | 59.92 | 59.51 | 7.2 | 稳定 | — |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 30 | 73.52 | 72.68 | 13.7 | ✗超门 | — |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 30 | 77.84 | 75.37 | 10.6 | ✗超门 | — |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 30 | 77.13 | 74.77 | 9.6 | 稳定 | — |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 1 | 74.46 | 74.46 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 1 | 72.97 | 72.97 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 1 | 70.8 | 70.8 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 24 | 74.33 | 75.1 | 27.1 | ✗超门 | — |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 24 | 76.82 | 74.92 | 24.4 | ✗超门 | — |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 24 | 73.57 | 73.75 | 23.3 | ✗超门 | — |

### 复测稳定性：`u1_goodput_mbps`（CV% = 样本 stdev/mean；门 ≤10% 为稳定）

> **本表共 30 个单元**：✗超门 4，CV 不可计算 6，其余稳定。摘要的「N/M 单元超 CV 门」即各 KPI 分表这两个数各自相加。

| 单元 | n | 中位 | 均值 | CV% | 稳定? | 备注 |
|---|---|---|---|---|---|---|
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 12 | 0.12 | 0.12 | 4.7 | 稳定 | — |
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 9.92 | 10.08 | 12.1 | ✗超门 | — |
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 12 | 15.87 | 15.85 | 5.9 | 稳定 | — |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 12 | 0.13 | 0.12 | 7.2 | 稳定 | — |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 10.84 | 10.58 | 8.5 | 稳定 | — |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 12 | 15.95 | 15.58 | 8.1 | 稳定 | — |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 12 | 0.12 | 0.12 | 7.9 | 稳定 | — |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 9.74 | 9.85 | 9.8 | 稳定 | — |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 12 | 15.12 | 15.07 | 4.5 | 稳定 | — |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 12 | 0.12 | 0.12 | 6.7 | 稳定 | — |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 9.66 | 9.88 | 7.7 | 稳定 | — |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 12 | 16.23 | 16.37 | 6.9 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 11 | 0.14 | 0.14 | 6.2 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 11 | 10.05 | 10.11 | 8.3 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 11 | 16.43 | 16.56 | 5.2 | 稳定 | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 1 | 0.14 | 0.14 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 1 | 11.18 | 11.18 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 1 | 17.07 | 17.07 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 48 | 0.15 | 0.15 | 5.6 | 稳定 | — |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 48 | 11.39 | 11.38 | 9.7 | 稳定 | — |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 48 | 17.94 | 17.94 | 8.8 | 稳定 | — |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 30 | 0.13 | 0.13 | 9.8 | 稳定 | — |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 30 | 4.49 | 4.53 | 3.4 | 稳定 | — |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 30 | 5.11 | 5.1 | 3.6 | 稳定 | — |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 1 | 0.12 | 0.12 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 1 | 8.61 | 8.61 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 1 | 18.72 | 18.72 | — | — | CV 不可计算(n<2); low_conf |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 24 | 0.12 | 0.12 | 26.1 | ✗超门 | — |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 24 | 9.22 | 9.71 | 19.3 | ✗超门 | — |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 24 | 15.71 | 14.44 | 30.7 | ✗超门 | — |

## 采样量核算（目标：分辨 5% 的差异）

> **这一段是「还要测多少」的依据**，`复测稳定性` 是「测得准不准」——同一批单元，两个问题。扩展轮 `n≥` 的决定就出自本段的 `需 n≥(80%)` 列。完整（未折叠）数据见 `<prefix>_plan.csv`，或单独跑 `python stability.py <corpus> --kpi <KPI> --plan`。

### 采样量核算：`t1_ttft_ms`（目标：分辨 5% 的差异）

> **口径**：`可辨最小差异` = 以本单元实测离散度，两个同样大小的单元之间需要多大差异才会超出噪声尺度（√2·1.253·sd/√n）。它是**量级指示、不是显著性检验**（时延右偏）。离散度未知（n<2）的单元一律留 `—`，**不以 0 或当前 n 顶替**。

> ⚠ **两个「需 n≥」不是一回事，规划采样量要看后一个**：`需 n≥(平)` 是让目标差异**正好等于**噪声尺度的复测数——在那个 n 上，一个**真实存在**的目标差异只有**约五成**会被判为「超出噪声」（实测 52%~58%，n=5~40，D-201）；此前本段把这个数称作「足够」，**那是把抛硬币说成了保证**。`需 n≥(80%)` 才是「有 80% 把握看见它」所需的数，约为前者的 3.39 倍（判据是 |Δ|>噪声，故系数为 1+z=1.842；**不是**双侧显著性检验的 z₁₋α/₂+z₁₋β，那会多要 7.85 倍的外场工时，去买一个本报告从不作出的承诺）。

> ⚠ **两个「可辨最小差异」同理**：`(平)` 是**恰好等于**噪声尺度的差异——真有这么大的差异，也只有约五成会被判为「超出噪声」；`(80%)` 才是「这一格有 80% 把握分辨出来」的差异，约为前者的 1.842 倍。右侧「达标?」按 80% 判——**此前本表只印 `(平)` 那一个数，判词却按八成给**，一列按五成报、一列按八成判，并排放在同一行（D-240）。

| 单元 | n | 中位 | CV% | 超门? | 可辨最小差异(平) | 占中位(平) | 可辨最小差异(80%) | 达标?(80%) | 需 n≥(平) | 需 n≥(80%) |
|---|---|---|---|---|---|---|---|---|---|---|
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 12 | 60.03 | 7.4 | 达门 | 2.28 | 3.8% | 4.19 | ✗不足 | 7 | 24 |
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 61.13 | 6.9 | 达门 | 2.12 | 3.5% | 3.91 | ✗不足 | 6 | 20 |
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 12 | 63.95 | 7.3 | 达门 | 2.35 | 3.7% | 4.33 | ✗不足 | 7 | 23 |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 12 | 59.31 | 15.5 | **✗超门** | 4.83 | 8.1% | 8.9 | ✗不足 | 32 | 109 |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 61.93 | 4.7 | 达门 | 1.5 | 2.4% | 2.76 | 达标 | 3 | 10 |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 12 | 64.14 | 6.5 | 达门 | 2.17 | 3.4% | 3.99 | ✗不足 | 6 | 19 |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 12 | 57.12 | 10.2 | **✗超门** | 3.05 | 5.3% | 5.61 | ✗不足 | 14 | 47 |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 62.31 | 4.1 | 达门 | 1.31 | 2.1% | 2.42 | 达标 | 3 | 8 |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 12 | 64.3 | 5 | 达门 | 1.65 | 2.6% | 3.03 | 达标 | 4 | 11 |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 12 | 59.61 | 11.1 | **✗超门** | 3.41 | 5.7% | 6.29 | ✗不足 | 16 | 54 |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 63.61 | 4.9 | 达门 | 1.57 | 2.5% | 2.89 | 达标 | 3 | 10 |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 12 | 62.74 | 9.3 | 达门 | 3.04 | 4.9% | 5.61 | ✗不足 | 12 | 39 |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 11 | 53.26 | 5.5 | 达门 | 1.55 | 2.9% | 2.86 | ✗不足 | 4 | 13 |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 11 | 54.07 | 10.3 | **✗超门** | 3.03 | 5.6% | 5.58 | ✗不足 | 14 | 47 |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 11 | 53.01 | 5.9 | 达门 | 1.68 | 3.2% | 3.09 | ✗不足 | 5 | 15 |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 1 | 47.19 | — | — | — | —% | — | — | — | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 1 | 59.32 | — | — | — | —% | — | — | — | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 1 | 51.17 | — | — | — | —% | — | — | — | — |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 48 | 51.03 | 8 | 达门 | 1.04 | 2% | 1.92 | 达标 | 9 | 28 |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 48 | 51.21 | 7.5 | 达门 | 0.99 | 1.9% | 1.83 | 达标 | 8 | 25 |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 48 | 50.39 | 6.5 | 达门 | 0.86 | 1.7% | 1.58 | 达标 | 6 | 19 |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 30 | 50.49 | 13.9 | **✗超门** | 2.3 | 4.6% | 4.24 | ✗不足 | 26 | 85 |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 30 | 65.63 | 12.8 | **✗超门** | 2.69 | 4.1% | 4.95 | ✗不足 | 21 | 69 |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 30 | 62.37 | 14.9 | **✗超门** | 3.09 | 5% | 5.7 | ✗不足 | 30 | 101 |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 1 | 62.45 | — | — | — | —% | — | — | — | — |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 1 | 60.63 | — | — | — | —% | — | — | — | — |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 1 | 62.18 | — | — | — | —% | — | — | — | — |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 24 | 64.5 | 35.3 | **✗超门** | 8.67 | 13.4% | 15.96 | ✗不足 | 174 | 588 |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 24 | 68.55 | 27.1 | **✗超门** | 6.66 | 9.7% | 12.26 | ✗不足 | 91 | 307 |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 24 | 69 | 26.7 | **✗超门** | 6.47 | 9.4% | 11.92 | ✗不足 | 85 | 287 |

> **结论**：17/24 个单元在当前 n 下**没有 80% 的把握**看见 5% 的差异；这些单元的建议复测数中位为 **n≥47**（每侧）。 其中 **10 个**单元的当前 n 恰好落在「差异等于噪声尺度」附近——**那只有约五成把握**，不要据此认为采样量已经够了。 另有 6 个单元离散度不可估，**未计入**。

> ⚠ 其中 **10 个单元 CV 已超门**（标 `✗超门`）。对这些单元,`需 n≥` 只是把噪声摊薄的算术,**不解决它们本身不可重复**——先查原因(设备/环境/场景本身不稳)再重采,不要照着这个数字硬加复测。

### 采样量核算：`n1_rtt_p50_ms`（目标：分辨 5% 的差异）

> **口径**：`可辨最小差异` = 以本单元实测离散度，两个同样大小的单元之间需要多大差异才会超出噪声尺度（√2·1.253·sd/√n）。它是**量级指示、不是显著性检验**（时延右偏）。离散度未知（n<2）的单元一律留 `—`，**不以 0 或当前 n 顶替**。

> ⚠ **两个「需 n≥」不是一回事，规划采样量要看后一个**：`需 n≥(平)` 是让目标差异**正好等于**噪声尺度的复测数——在那个 n 上，一个**真实存在**的目标差异只有**约五成**会被判为「超出噪声」（实测 52%~58%，n=5~40，D-201）；此前本段把这个数称作「足够」，**那是把抛硬币说成了保证**。`需 n≥(80%)` 才是「有 80% 把握看见它」所需的数，约为前者的 3.39 倍（判据是 |Δ|>噪声，故系数为 1+z=1.842；**不是**双侧显著性检验的 z₁₋α/₂+z₁₋β，那会多要 7.85 倍的外场工时，去买一个本报告从不作出的承诺）。

> ⚠ **两个「可辨最小差异」同理**：`(平)` 是**恰好等于**噪声尺度的差异——真有这么大的差异，也只有约五成会被判为「超出噪声」；`(80%)` 才是「这一格有 80% 把握分辨出来」的差异，约为前者的 1.842 倍。右侧「达标?」按 80% 判——**此前本表只印 `(平)` 那一个数，判词却按八成给**，一列按五成报、一列按八成判，并排放在同一行（D-240）。

| 单元 | n | 中位 | CV% | 超门? | 可辨最小差异(平) | 占中位(平) | 可辨最小差异(80%) | 达标?(80%) | 需 n≥(平) | 需 n≥(80%) |
|---|---|---|---|---|---|---|---|---|---|---|
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 12 | 68.59 | 3.4 | 达门 | 1.21 | 1.8% | 2.23 | 达标 | 2 | 6 |
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 71.3 | 3.6 | 达门 | 1.31 | 1.8% | 2.41 | 达标 | 2 | 6 |
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 12 | 69.71 | 1.8 | 达门 | 0.64 | 0.9% | 1.18 | 达标 | 1 | 2 |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 12 | 68.62 | 4.7 | 达门 | 1.7 | 2.5% | 3.13 | 达标 | 3 | 10 |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 70.61 | 3.3 | 达门 | 1.21 | 1.7% | 2.22 | 达标 | 2 | 5 |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 12 | 68.53 | 3.2 | 达门 | 1.14 | 1.7% | 2.1 | 达标 | 2 | 5 |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 12 | 69.2 | 4.4 | 达门 | 1.59 | 2.3% | 2.93 | 达标 | 3 | 9 |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 71.05 | 3.5 | 达门 | 1.26 | 1.8% | 2.33 | 达标 | 2 | 6 |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 12 | 71.48 | 3.3 | 达门 | 1.21 | 1.7% | 2.23 | 达标 | 2 | 5 |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 12 | 70.44 | 3.6 | 达门 | 1.29 | 1.8% | 2.38 | 达标 | 2 | 6 |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 71.08 | 3.7 | 达门 | 1.36 | 1.9% | 2.51 | 达标 | 2 | 7 |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 12 | 70.18 | 3.1 | 达门 | 1.09 | 1.6% | 2.01 | 达标 | 2 | 4 |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 11 | 65.03 | 3.3 | 达门 | 1.14 | 1.8% | 2.1 | 达标 | 2 | 5 |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 11 | 65.07 | 3.6 | 达门 | 1.24 | 1.9% | 2.29 | 达标 | 2 | 6 |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 11 | 62.55 | 4.4 | 达门 | 1.49 | 2.4% | 2.74 | 达标 | 3 | 9 |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 1 | 64.19 | — | — | — | —% | — | — | — | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 1 | 63.41 | — | — | — | —% | — | — | — | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 1 | 59.38 | — | — | — | —% | — | — | — | — |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 48 | 57.89 | 9.3 | 达门 | 1.42 | 2.5% | 2.62 | 达标 | 12 | 40 |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 48 | 60.43 | 8.6 | 达门 | 1.33 | 2.2% | 2.45 | 达标 | 10 | 32 |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 48 | 59.92 | 7.2 | 达门 | 1.09 | 1.8% | 2.01 | 达标 | 7 | 22 |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 30 | 73.52 | 13.7 | **✗超门** | 3.22 | 4.4% | 5.92 | ✗不足 | 23 | 78 |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 30 | 77.84 | 10.6 | **✗超门** | 2.57 | 3.3% | 4.74 | ✗不足 | 14 | 45 |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 30 | 77.13 | 9.6 | 达门 | 2.32 | 3% | 4.27 | ✗不足 | 11 | 37 |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 1 | 74.46 | — | — | — | —% | — | — | — | — |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 1 | 72.97 | — | — | — | —% | — | — | — | — |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 1 | 70.8 | — | — | — | —% | — | — | — | — |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 24 | 74.33 | 27.1 | **✗超门** | 7.37 | 9.9% | 13.57 | ✗不足 | 95 | 320 |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 24 | 76.82 | 24.4 | **✗超门** | 6.61 | 8.6% | 12.17 | ✗不足 | 72 | 241 |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 24 | 73.57 | 23.3 | **✗超门** | 6.2 | 8.4% | 11.42 | ✗不足 | 69 | 232 |

> **结论**：6/24 个单元在当前 n 下**没有 80% 的把握**看见 5% 的差异；这些单元的建议复测数中位为 **n≥155**（每侧）。 其中 **3 个**单元的当前 n 恰好落在「差异等于噪声尺度」附近——**那只有约五成把握**，不要据此认为采样量已经够了。 另有 6 个单元离散度不可估，**未计入**。

> ⚠ 其中 **5 个单元 CV 已超门**（标 `✗超门`）。对这些单元,`需 n≥` 只是把噪声摊薄的算术,**不解决它们本身不可重复**——先查原因(设备/环境/场景本身不稳)再重采,不要照着这个数字硬加复测。

### 采样量核算：`u1_goodput_mbps`（目标：分辨 5% 的差异）

> **口径**：`可辨最小差异` = 以本单元实测离散度，两个同样大小的单元之间需要多大差异才会超出噪声尺度（√2·1.253·sd/√n）。它是**量级指示、不是显著性检验**（时延右偏）。离散度未知（n<2）的单元一律留 `—`，**不以 0 或当前 n 顶替**。

> ⚠ **两个「需 n≥」不是一回事，规划采样量要看后一个**：`需 n≥(平)` 是让目标差异**正好等于**噪声尺度的复测数——在那个 n 上，一个**真实存在**的目标差异只有**约五成**会被判为「超出噪声」（实测 52%~58%，n=5~40，D-201）；此前本段把这个数称作「足够」，**那是把抛硬币说成了保证**。`需 n≥(80%)` 才是「有 80% 把握看见它」所需的数，约为前者的 3.39 倍（判据是 |Δ|>噪声，故系数为 1+z=1.842；**不是**双侧显著性检验的 z₁₋α/₂+z₁₋β，那会多要 7.85 倍的外场工时，去买一个本报告从不作出的承诺）。

> ⚠ **两个「可辨最小差异」同理**：`(平)` 是**恰好等于**噪声尺度的差异——真有这么大的差异，也只有约五成会被判为「超出噪声」；`(80%)` 才是「这一格有 80% 把握分辨出来」的差异，约为前者的 1.842 倍。右侧「达标?」按 80% 判——**此前本表只印 `(平)` 那一个数，判词却按八成给**，一列按五成报、一列按八成判，并排放在同一行（D-240）。

| 单元 | n | 中位 | CV% | 超门? | 可辨最小差异(平) | 占中位(平) | 可辨最小差异(80%) | 达标?(80%) | 需 n≥(平) | 需 n≥(80%) |
|---|---|---|---|---|---|---|---|---|---|---|
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 12 | 0.12 | 4.7 | 达门 | 0 | 2.5% | 0.01 | 达标 | 3 | 10 |
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 9.92 | 12.1 | **✗超门** | 0.62 | 6.3% | 1.15 | ✗不足 | 19 | 65 |
| campaign_id=m2-afternoonradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 12 | 15.87 | 5.9 | 达门 | 0.48 | 3% | 0.88 | ✗不足 | 5 | 15 |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 12 | 0.13 | 7.2 | 达门 | 0 | 3.7% | 0.01 | ✗不足 | 7 | 22 |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 10.84 | 8.5 | 达门 | 0.46 | 4.2% | 0.84 | ✗不足 | 9 | 30 |
| campaign_id=m2-busyradio-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 12 | 15.95 | 8.1 | 达门 | 0.65 | 4.1% | 1.19 | ✗不足 | 8 | 27 |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 12 | 0.12 | 7.9 | 达门 | 0 | 4.1% | 0.01 | ✗不足 | 9 | 28 |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 9.74 | 9.8 | 达门 | 0.49 | 5.1% | 0.91 | ✗不足 | 13 | 43 |
| campaign_id=m2-idlenight-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 12 | 15.12 | 4.5 | 达门 | 0.34 | 2.3% | 0.64 | 达标 | 3 | 9 |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 12 | 0.12 | 6.7 | 达门 | 0 | 3.4% | 0.01 | ✗不足 | 6 | 19 |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 9.66 | 7.7 | 达门 | 0.39 | 4% | 0.71 | ✗不足 | 8 | 27 |
| campaign_id=m2-idleprobe-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 12 | 16.23 | 6.9 | 达门 | 0.57 | 3.5% | 1.06 | ✗不足 | 6 | 21 |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 11 | 0.14 | 6.2 | 达门 | 0 | 3.3% | 0.01 | ✗不足 | 5 | 17 |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 11 | 10.05 | 8.3 | 达门 | 0.45 | 4.5% | 0.82 | ✗不足 | 9 | 30 |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 11 | 16.43 | 5.2 | 达门 | 0.46 | 2.8% | 0.84 | ✗不足 | 4 | 12 |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 1 | 0.14 | — | — | — | —% | — | — | — | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 1 | 11.18 | — | — | — | —% | — | — | — | — |
| campaign_id=m2-pilot-20260731 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 1 | 17.07 | — | — | — | —% | — | — | — | — |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 48 | 0.15 | 5.6 | 达门 | 0 | 1.4% | 0 | 达标 | 4 | 14 |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 48 | 11.39 | 9.7 | 达门 | 0.28 | 2.5% | 0.52 | 达标 | 12 | 40 |
| campaign_id=m3-expansion-busyband-20260803 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 48 | 17.94 | 8.8 | 达门 | 0.4 | 2.3% | 0.74 | 达标 | 10 | 34 |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 30 | 0.13 | 9.8 | 达门 | 0 | 3.2% | 0.01 | ✗不足 | 13 | 41 |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 30 | 4.49 | 3.4 | 达门 | 0.05 | 1.1% | 0.09 | 达标 | 2 | 6 |
| campaign_id=m3-expansion-wave0 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 30 | 5.11 | 3.6 | 达门 | 0.06 | 1.2% | 0.11 | 达标 | 2 | 6 |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s1_chat | 1 | 0.12 | — | — | — | —% | — | — | — | — |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 1 | 8.61 | — | — | — | —% | — | — | — | — |
| campaign_id=radiowire-verify-20260801 · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 1 | 18.72 | — | — | — | —% | — | — | — | — |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s1_chat | 24 | 0.12 | 26.1 | **✗超门** | 0.01 | 9.5% | 0.02 | ✗不足 | 87 | 293 |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 24 | 9.22 | 19.3 | **✗超门** | 0.68 | 7.3% | 1.25 | ✗不足 | 52 | 176 |
| campaign_id=warmup-transport-probe · point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 24 | 15.71 | 30.7 | **✗超门** | 1.6 | 10.2% | 2.95 | ✗不足 | 100 | 339 |

> **结论**：17/24 个单元在当前 n 下**没有 80% 的把握**看见 5% 的差异；这些单元的建议复测数中位为 **n≥28**（每侧）。 其中 **12 个**单元的当前 n 恰好落在「差异等于噪声尺度」附近——**那只有约五成把握**，不要据此认为采样量已经够了。 另有 6 个单元离散度不可估，**未计入**。

> ⚠ 其中 **4 个单元 CV 已超门**（标 `✗超门`）。对这些单元,`需 n≥` 只是把噪声摊薄的算术,**不解决它们本身不可重复**——先查原因(设备/环境/场景本身不稳)再重采,不要照着这个数字硬加复测。

## 序位效应诊断（t1_ttft_ms；拉丁方反平衡是否奏效）

> 判据：同 profile 各**执行位次**的中位数极差 / 总体中位数 > 10.0% 即疑似残留序位偏倚（无效应=好结果）。

> 轮转口径：共 3 种轮次，其中 45 条 run **在自身内部**已轮转（`s1,s2,s3|s2,s3,s1` 形状），反平衡在构造上成立。

| profile | 位次中位数 | 极差 | 极差% | 总体中位 | 判定 | 备注 |
|---|---|---|---|---|---|---|
| s1_chat | #0:53.353(n=73) / #5:52.688(n=45) / #7:51.829(n=45) | 1.524 | 2.868 | 53.13 | 无明显效应 | — |
| s2_coding_agent | #1:61.14(n=73) / #3:59.62(n=45) / #8:59.13(n=45) | 2.01 | 3.35 | 59.98 | 无明显效应 | — |
| s3_multimodal | #2:59.4(n=73) / #4:58.88(n=45) / #6:60.03(n=45) | 1.15 | 1.94 | 59.4 | 无明显效应 | — |

## 序位效应诊断（n1_rtt_p50_ms；拉丁方反平衡是否奏效）

> 判据：同 profile 各**执行位次**的中位数极差 / 总体中位数 > 10.0% 即疑似残留序位偏倚（无效应=好结果）。

> 轮转口径：共 3 种轮次，其中 45 条 run **在自身内部**已轮转（`s1,s2,s3|s2,s3,s1` 形状），反平衡在构造上成立。

| profile | 位次中位数 | 极差 | 极差% | 总体中位 | 判定 | 备注 |
|---|---|---|---|---|---|---|
| s1_chat | #0:69.51(n=73) / #5:66.79(n=45) / #7:61.05(n=45) | 8.46 | 12.54 | 67.44 | **疑似序位偏倚** | — |
| s2_coding_agent | #1:71.31(n=73) / #3:68.31(n=45) / #8:66.93(n=45) | 4.38 | 6.44 | 68.06 | 无明显效应 | — |
| s3_multimodal | #2:68.36(n=73) / #4:67.64(n=45) / #6:66.63(n=45) | 1.73 | 2.56 | 67.51 | 无明显效应 | — |

## 序位效应诊断（u1_goodput_mbps；拉丁方反平衡是否奏效）

> 判据：同 profile 各**执行位次**的中位数极差 / 总体中位数 > 10.0% 即疑似残留序位偏倚（无效应=好结果）。

> 轮转口径：共 3 种轮次，其中 45 条 run **在自身内部**已轮转（`s1,s2,s3|s2,s3,s1` 形状），反平衡在构造上成立。

| profile | 位次中位数 | 极差 | 极差% | 总体中位 | 判定 | 备注 |
|---|---|---|---|---|---|---|
| s1_chat | #0:0.133779(n=73) / #5:0.132858(n=45) / #7:0.136418(n=45) | 0.003559 | 2.651241 | 0.134257 | 无明显效应 | ROUNDING_UNRECONCILED |
| s2_coding_agent | #1:9.878308(n=73) / #3:10.271608(n=45) / #8:10.391761(n=45) | 0.513452 | 5.012926 | 10.242566 | 无明显效应 | ROUNDING_UNRECONCILED |
| s3_multimodal | #2:15.800498(n=73) / #4:16.434656(n=45) / #6:15.899089(n=45) | 0.634158 | 3.955785 | 16.03115 | 无明显效应 | ROUNDING_UNRECONCILED |

## 预热效应（首轮是否系统性更差）

> 判据：首轮中位与**其后各轮中位的中位数**相比差 >10%（按各 KPI 自己的好坏方向；正值=首轮更差）即疑似预热效应。每轮至少 2 个样本才判。

| KPI | 各轮中位(n) | 首轮劣势% | 判定 | 备注 |
|---|---|---|---|---|
| t1_ttft_ms | #0:58.02(n=219) / #1:56.75(n=135) / #2:54.69(n=135) | 4.1 | 无明显预热 | — |
| n1_rtt_p50_ms | #0:69.51(n=219) / #1:67.64(n=135) / #2:63.48(n=135) | 6 | 无明显预热 | — |
| u1_goodput_mbps | #0:10.61(n=146) / #1:12.41(n=90) / #2:12.1(n=90) | 13.4 | **疑似预热效应** | RULED_OUT:163（D-366） |

## 有效性与失效原因（每格的有效样本分母）

> 全语料尝试 489 个场景，可用 489 （100.0%）；低于 80% 的单元标 `LOW_VALID_RATE`。INVALID 场景 KPI 为空、会被热力卡/归因静默丢弃——**此表即那些被丢弃样本的去向**。

> **有效率的分子是两列之和**：`有效率 =（有效(严格) + 低置信）/ 尝试`。低置信的场景**仍产出了可用测量**，所以它计入分子；**「有效(严格)」那一列不是分子**，拿它去除尝试会得到另一个数——`有效(严格)=0` 与 `有效率=100%` 可以同时成立，且都没错。

> **「未知」的口径**：`validity` 取值不在已知三态内（本层大小写不敏感）即计入**未知**列。**未知按「不可用」计入有效率**——这是保守方向，但它**不是失效**，而是本层读不懂那个状态。故未知占比高的格会标 `UNKNOWN_VALIDITY:x%`：该格的有效率**不应读成「这里全失败了」**，应先去查生产者写了什么。

| 点位 | 运营商 | 时段 | profile | 尝试 | 有效(严格) | 低置信 | 失效 | 未知 | 有效率 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | s1_chat | 107 | 0 | 107 | 0 | 0 | 100.0% | — |
| SZ-PILOT-01 | ctcc | busy | s2_coding_agent | 107 | 0 | 107 | 0 | 0 | 100.0% | — |
| SZ-PILOT-01 | ctcc | busy | s3_multimodal | 107 | 0 | 107 | 0 | 0 | 100.0% | — |
| SZ-PILOT-01 | ctcc | idle | s1_chat | 56 | 0 | 56 | 0 | 0 | 100.0% | — |
| SZ-PILOT-01 | ctcc | idle | s2_coding_agent | 56 | 0 | 56 | 0 | 0 | 100.0% | — |
| SZ-PILOT-01 | ctcc | idle | s3_multimodal | 56 | 0 | 56 | 0 | 0 | 100.0% | — |

### 有效率趋势（按本地日，UTC+8）

| 日期 | 尝试 | 可用 | 有效率 |
|---|---|---|---|
| 2026-07-31 | 144 | 144 | 100.0% |
| 2026-08-01 | 111 | 111 | 100.0% |
| 2026-08-03 | 144 | 144 | 100.0% |
| 2026-08-04 | 90 | 90 | 100.0% |

> ⚠ 各日**并非测的同一组单元**（SZ-PILOT-01/ctcc/busy、SZ-PILOT-01/ctcc/idle未出现在每一天）——率的升降**可能是换了点位/运营商/时段**，而不是装置回归信号。逐单元的率见上表。


## 测量可信度（时钟 / 流完整性 / 解析开销）

> 上方时延中位数背后的**仪器**可信度：时钟可疑=R-22（|漂移|>100ppm 或端点缺失），该场景 TTFT/ITL 存疑；seq 异常=gap/dup>0；解析开销大会混淆 ITL（端侧算力≠网络）。各信号分母=实际带标注的场景数，未标注**不算干净**。时钟可疑过半标 `时钟可疑热点`。

| 点位 | 运营商 | 时段 | 场景 | 时钟标注 | 时钟可疑 | 漂移中位 ppm | seq 异常 | 解析 us 中位 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 321 | 321 | 40 (12%) | 30.3 | 0/321 | 132.6 | — |
| SZ-PILOT-01 | ctcc | idle | 168 | 168 | 60 (36%) | 67.2 | 0/168 | 139.1 | — |

### 低置信定位（per-KPI 样本数）

| KPI | 标注场景 | 低置信 | 最小样本数 |
|---|---|---|---|
| T1 | 306 | 306 (100%) | 1 |
| U1 | 306 | 306 (100%) | 1 |
| U1_excl_slow_start | 306 | 72 (24%) | 0 |
| N1 | 306 | 0 (0%) | 17 |
| N2 | 306 | 0 (0%) | 17 |
| T2 | 306 | 0 (0%) | 397 |
| T2_incl_coalesced | 306 | 0 (0%) | 397 |
| T3 | 306 | 0 (0%) | 397 |
| T3_incl_resume | 306 | 0 (0%) | 397 |
| T4 | 306 | 0 (0%) | 397 |
| T5 | 306 | 0 (0%) | 0 |
| U2 | 306 | 0 (0%) | 0 |

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
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · profile_id=s1_chat | 同城 | 65.2 | — | — | — | TIER_MISSING:regional,core; MIXED_CAMPAIGN:m2-afternoonradio-20260801/m2-busyradio-20260801/m2-pilot-20260731/m3-expansion-busyband-20260803/warmup-transport-probe; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 65.1 | — | — | — | TIER_MISSING:regional,core; MIXED_CAMPAIGN:m2-afternoonradio-20260801/m2-busyradio-20260801/m2-pilot-20260731/m3-expansion-busyband-20260803/warmup-transport-probe; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · profile_id=s3_multimodal | 同城 | 62.8 | — | — | — | TIER_MISSING:regional,core; MIXED_CAMPAIGN:m2-afternoonradio-20260801/m2-busyradio-20260801/m2-pilot-20260731/m3-expansion-busyband-20260803/warmup-transport-probe; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · profile_id=s1_chat | 同城 | 70.5 | — | — | — | TIER_MISSING:regional,core; MIXED_CAMPAIGN:m2-idlenight-20260801/m2-idleprobe-20260731/m2-pilot-20260731/m3-expansion-wave0/radiowire-verify-20260801; MIXED_MODE:forensic/quick |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 73.1 | — | — | — | TIER_MISSING:regional,core; MIXED_CAMPAIGN:m2-idlenight-20260801/m2-idleprobe-20260731/m2-pilot-20260731/m3-expansion-wave0/radiowire-verify-20260801; MIXED_MODE:forensic/quick |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · profile_id=s3_multimodal | 同城 | 71.9 | — | — | — | TIER_MISSING:regional,core; MIXED_CAMPAIGN:m2-idlenight-20260801/m2-idleprobe-20260731/m2-pilot-20260731/m3-expansion-wave0/radiowire-verify-20260801; MIXED_MODE:forensic/quick |

## 分段异常定位（n1_rtt_p50_ms，同一段跨单元比较，ms）

> **这一段回答的是**：某一段慢，是**这个点位特有**，还是**所有点位都这样**——前者指向该点位，后者是本次测量路径的**共性**（例如到中心镜像端的物理距离），**不构成任何点位的问题**。
> **口径**：与**本语料内**同段各单元的中位数比较，稳健离差 MAD，阈值 `K×1.4826×MAD`，**K 随可比单元数标定**（单元越少，MAD 本身越抖，K 越大）。这是**描述性筛查、不是显著性检验**，也**不与任何外部基准比较**；不可计算的单元不参与比较且如实计数。

> **这个筛查有多准**（每格 60000 次模拟实测，D-200）：K 的标定目标是——在**同分布的干净网格**（不存在真异常）上，误报至少一个单元的概率 ≤5%。**但时延是右偏的**，右偏数据上实测误报率是 7%（4~5 单元）→ 20%（32 单元）→ 26%（48 单元），**随网格变大而升高**（单元越多，长尾越有机会甩出一个）——**所以 `存在单点异常` 的意思是「值得去看一眼」，不是「已证明异常」**。代价也要说清楚：这个阈值只抓得住**很粗的**异常，一个 +5 稳健 σ 的真异常约有一半会被漏掉（+10 σ 才接近必中）。**少于 4 个可比单元时本段拒绝给阈值筛查结论**——那个规模下没有任何阈值达得到上述口径。（**唯一例外**：过半单元取值完全相同时，MAD 退化为 0，「与共同取值不等」是不需要标定的事实，仍如实列出，判读里会写明判据已变。）（此前阈值是固定 3σ，听着严格，实测在干净网格上误报 20%～65%，**32 单元的时延网格三次里有两次会点名一个没问题的点位**。）

> **注意**：`未见单点异常` 只表示**没有单元越过筛查阈值**，**不等于各单元相同**——单元间到底有多齐，看 `离差/典型` 一列。该列小且无异常，才说得上是路径共性。

> **参与单元里若有「样本不足」的**（`参与单元` 列会写出个数）：那些单元**等权**参与离差与筛查——一个只测过一次的单元既能把阈值拉动，也可能**自己被点名**。被点名的单元若本身样本不足，`偏高/偏低` 里会带 `*`：**先补测它，再去现场查**。

| 段 | 参与单元 | 典型值(中位) | 离差(MAD) | 离差/典型 | 偏高 | 偏低 | 判读 |
|---|---|---|---|---|---|---|---|
| 接入(metro) | 6 | 67.9 | 3.4 | 5% | — | — | **未见单点异常**（K=6×1.4826×MAD；干净网格误报 对称4.7%/右偏9.4%）→ 最大单项落在该段分布内，不宜单独归因于该单元 |
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
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · profile_id=s1_chat | 同城 | 52.8 | — | — | — | TIER_MISSING:regional,core; MIXED_CAMPAIGN:m2-afternoonradio-20260801/m2-busyradio-20260801/m2-pilot-20260731/m3-expansion-busyband-20260803/warmup-transport-probe; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · profile_id=s2_coding_agent | 同城 | 54.8 | — | — | — | TIER_MISSING:regional,core; MIXED_CAMPAIGN:m2-afternoonradio-20260801/m2-busyradio-20260801/m2-pilot-20260731/m3-expansion-busyband-20260803/warmup-transport-probe; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=busy · profile_id=s3_multimodal | 同城 | 52.8 | — | — | — | TIER_MISSING:regional,core; MIXED_CAMPAIGN:m2-afternoonradio-20260801/m2-busyradio-20260801/m2-pilot-20260731/m3-expansion-busyband-20260803/warmup-transport-probe; **MIXED_TRANSPORT:cellular/wifi**; MIXED_MODE:forensic/quick |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · profile_id=s1_chat | 同城 | 54.6 | — | — | — | TIER_MISSING:regional,core; MIXED_CAMPAIGN:m2-idlenight-20260801/m2-idleprobe-20260731/m2-pilot-20260731/m3-expansion-wave0/radiowire-verify-20260801; MIXED_MODE:forensic/quick |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · profile_id=s2_coding_agent | 同城 | 64.1 | — | — | — | TIER_MISSING:regional,core; MIXED_CAMPAIGN:m2-idlenight-20260801/m2-idleprobe-20260731/m2-pilot-20260731/m3-expansion-wave0/radiowire-verify-20260801; MIXED_MODE:forensic/quick |
| point_id=SZ-PILOT-01 · carrier=ctcc · time_band=idle · profile_id=s3_multimodal | 同城 | 62.9 | — | — | — | TIER_MISSING:regional,core; MIXED_CAMPAIGN:m2-idlenight-20260801/m2-idleprobe-20260731/m2-pilot-20260731/m3-expansion-wave0/radiowire-verify-20260801; MIXED_MODE:forensic/quick |

## 分段异常定位（t1_ttft_ms，同一段跨单元比较，ms）

> **这一段回答的是**：某一段慢，是**这个点位特有**，还是**所有点位都这样**——前者指向该点位，后者是本次测量路径的**共性**（例如到中心镜像端的物理距离），**不构成任何点位的问题**。
> **口径**：与**本语料内**同段各单元的中位数比较，稳健离差 MAD，阈值 `K×1.4826×MAD`，**K 随可比单元数标定**（单元越少，MAD 本身越抖，K 越大）。这是**描述性筛查、不是显著性检验**，也**不与任何外部基准比较**；不可计算的单元不参与比较且如实计数。

> **这个筛查有多准**（每格 60000 次模拟实测，D-200）：K 的标定目标是——在**同分布的干净网格**（不存在真异常）上，误报至少一个单元的概率 ≤5%。**但时延是右偏的**，右偏数据上实测误报率是 7%（4~5 单元）→ 20%（32 单元）→ 26%（48 单元），**随网格变大而升高**（单元越多，长尾越有机会甩出一个）——**所以 `存在单点异常` 的意思是「值得去看一眼」，不是「已证明异常」**。代价也要说清楚：这个阈值只抓得住**很粗的**异常，一个 +5 稳健 σ 的真异常约有一半会被漏掉（+10 σ 才接近必中）。**少于 4 个可比单元时本段拒绝给阈值筛查结论**——那个规模下没有任何阈值达得到上述口径。（**唯一例外**：过半单元取值完全相同时，MAD 退化为 0，「与共同取值不等」是不需要标定的事实，仍如实列出，判读里会写明判据已变。）（此前阈值是固定 3σ，听着严格，实测在干净网格上误报 20%～65%，**32 单元的时延网格三次里有两次会点名一个没问题的点位**。）

> **注意**：`未见单点异常` 只表示**没有单元越过筛查阈值**，**不等于各单元相同**——单元间到底有多齐，看 `离差/典型` 一列。该列小且无异常，才说得上是路径共性。

> **参与单元里若有「样本不足」的**（`参与单元` 列会写出个数）：那些单元**等权**参与离差与筛查——一个只测过一次的单元既能把阈值拉动，也可能**自己被点名**。被点名的单元若本身样本不足，`偏高/偏低` 里会带 `*`：**先补测它，再去现场查**。

| 段 | 参与单元 | 典型值(中位) | 离差(MAD) | 离差/典型 | 偏高 | 偏低 | 判读 |
|---|---|---|---|---|---|---|---|
| 接入(metro) | 6 | 54.67 | 1.87 | 3.42% | — | — | **未见单点异常**（K=6×1.4826×MAD；干净网格误报 对称4.7%/右偏9.4%）→ 最大单项落在该段分布内，不宜单独归因于该单元 |
| 区域骨干+ | 0（另 6 不可计算） | — | — | — | — | — | 可比单元不足(<2)，无法比较 |
| 核心骨干+ | 0（另 6 不可计算） | — | — | — | — | — | 可比单元不足(<2)，无法比较 |

## AQS 分数侧归因（各维度子分 + 拖累维度）

> 归因矩阵的分数侧互补：composite AQS 低时，指出是哪个 KPI 维度在拖后腿。子分 0-100，越高越好；`拖累` = 中位子分最低的维度。

| 点位 | 运营商 | 时段 | runs | T1 | T2 | T3 | N1 | N2 | U1 | U2 | 拖累 | 极差 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 43 | 96 | 97.9 | 100 | 68.5 | 84.8 | 81.5 | 85.1 | **N1**=68.5 | 31.5 | — |
| SZ-PILOT-01 | ctcc | idle | 30 | 95.2 | 96.9 | 100 | 66.1 | 81.3 | 70.3 | 84 | **N1**=66.1 | 33.9 | — |

## 批化(buffering)归因（取证/失真核算）

> **R-05**：批化标注为**取证证据**，**不改判** validity/score（本表亦然）。`none`=未见批化失真；非 `none` 占多数的格标 `失真热点`。空块=未检测（非 0）。

| 点位 | 运营商 | 时段 | n | 未测 | 残差样本中位 | 众数归因 | 批化分中位 | sawtooth | 近零到达 | 疑似占比 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 321 | 0 | 599 | none | 0.041 | 0.02 | 0 | 18% | — |
| SZ-PILOT-01 | ctcc | idle | 168 | 0 | 599 | none | 0.207 | 0.298 | 0 | 30% | — |

## 接入介质对比（wifi vs cellular，AQS 中位）

> transport 取 run 显式设置，`auto` 由各场景 `network_snapshot` 观测共识推得；不一致=mixed、无观测=unknown，**均不并入任何介质**。Δ=cellular−wifi（AQS 越大越好，负值=蜂窝更差）。* = 样本不足。

> **噪声尺度**：Δ 旁的 `±` 是该格测量离散度推得的**指示性**噪声量级（正态近似 SE≈1.253·sd/√n，两格求和取方根）。时延右偏，故它只指示**量级、不是显著性检验**；|Δ| 小于它的格标 `噪声内`——**不应作为改善/回退的结论**。`±0` 只表示这几次复测未观察到离散，**不等于没有噪声**；样本不足的格（标 `low_conf`）其噪声估计本身也不可靠，噪声无法估计时留 `—`、不以 0 顶替。

| 点位 | 运营商 | 时段 | wifi | cellular | Δ(cell−wifi) | 噪声 | 备注 | 其他桶 |
|---|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 87.3 (n=4*) | 90 (n=39) | 2.7 | ±0.6 | — | — |
| SZ-PILOT-01 | ctcc | idle | — | 87.2 (n=30) | — | — | — | — |

## 无线上下文（信号档与小区一致性）

> 信号档沿用 App 侧 R1 判据（`BufferingDetector`）：弱=任一已知分量越线（RSRP<-105dBm 或 SINR<0dB）；良=已知分量均不越线（RSRP≥-95dBm 且 SINR≥10dB）；其余为中。**两个分量都不可得则记 `—`，不记档**。* = 带无线证据的 run 不足。

**档位分布**：弱 0 格 / 中 1 格 / 良 1 格

| 点位 | 运营商 | 时段 | 信号档 | RSRP中位 | SINR中位 | 制式 | 服务小区 | 出口 IP | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 良 | -83 | 20 | LTE/NR | 3 个 | 6 个 | **MIXED_SERVING_CELL:3**; **MIXED_RAT:LTE/NR**; RADIO_STALE:7; **MIXED_EGRESS:6** |
| SZ-PILOT-01 | ctcc | idle | 中 | -98 | 16.5 | LTE/NR | 2 个 | 3 个 | **MIXED_SERVING_CELL:2**; **MIXED_RAT:LTE/NR**; **MIXED_EGRESS:3** |

### 忙闲可比性（同点位是否挂同一小区）

> 三级归因取消后，忙闲对比是仅剩的两个对照维度之一。**若忙时与闲时挂的不是同一小区，该点位的忙闲差里混着小区差**——与 `TIER_ENDPOINT_CONFLICT` 同形，故同样只报不删。

| 点位 | 运营商 | 各时段小区 | 判定 |
|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy:420-39430-1650/672-10119936-627264/672-10119936-633984; idle:420-39430-1650/90-9766400-633984 | **CELL_PARTIAL——部分时段另挂了小区，差值含小区成分** |

## 纵向趋势（aqs；↑ 越大越好）

> 战役时序：m2-pilot-20260731 → warmup-transport-probe → m2-idleprobe-20260731 → radiowire-verify-20260801 → m2-busyradio-20260801 → m2-afternoonradio-20260801 → m2-idlenight-20260801 → m3-expansion-busyband-20260803 → m3-expansion-wave0。缺席战役的格记 `—` 不插值；方向按指标极性解释为 改善/回退/混合。

> **噪声尺度**：Δ 旁的 `±` 是该格测量离散度推得的**指示性**噪声量级（正态近似 SE≈1.253·sd/√n，两格求和取方根）。时延右偏，故它只指示**量级、不是显著性检验**；|Δ| 小于它的格标 `噪声内`——**不应作为改善/回退的结论**。`±0` 只表示这几次复测未观察到离散，**不等于没有噪声**；样本不足的格（标 `low_conf`）其噪声估计本身也不可靠，噪声无法估计时留 `—`、不以 0 顶替。

| 点位 | 运营商 | 时段 | m2-pilot-20260731 | warmup-transport-probe | m2-idleprobe-20260731 | radiowire-verify-20260801 | m2-busyradio-20260801 | m2-afternoonradio-20260801 | m2-idlenight-20260801 | m3-expansion-busyband-20260803 | m3-expansion-wave0 | 首末Δ | 噪声 | 方向 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SZ-PILOT-01 | ctcc | busy | 89 | 89.2 | — | — | 89.2 | 89.4 | — | 90.6 | — | 1.6 | ±0.3 | 改善 | low_conf |
| SZ-PILOT-01 | ctcc | idle | 89.3 | — | 89.1 | 89.3 | — | — | 89.2 | — | 86.8 | -2.5 | — | 噪声不可估 | low_conf |

html -> ../evidence/m2_rerun_20260819/m2_rerun_report.html
