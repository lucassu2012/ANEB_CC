# ANEB 战役级综合报告

> claim_scope: `application_end_to_end_to_probe_node` — 应用层端到指定节点路径；**不表述为** MOS / 无线层评级 / 运营商全网 SLA。
> 输入记录：144；含 run.aqs：144；含 campaign 标签：144。样本地板 min_samples=5。

## 覆盖盘点

- 战役 campaign_id：{'base': 72, 'opt': 72}
- 点位 point_id：{'P1': 72, 'P2': 72}
- 运营商 carrier：{'cmcc': 144}
- 时段 time_band：{'busy': 72, 'idle': 72}
- 服务层级 tier：{'core': 48, 'metro': 48, 'regional': 48}
- run 状态 status：{'completed': 144}
- profile 版本：{'t': 144}
- 采集时间窗：2026-07-13 12:00 UTC → 2026-07-13 12:00 UTC

> ⚠ 本语料含 **2 个战役**（base, opt）。除「优化前后对比」/「纵向趋势」两段外，**各段均按格池化了所有战役**——受影响的格标 `MIXED_CAMPAIGN`，其中位数**既不是前也不是后**。要看单个战役，用 `--campaign <id>`。

## 摘要（先看这里）

- **体验最差格**：2 个格 AQS 达 fair/poor —— P1/cmcc/busy(68)、P2/cmcc/busy(68)。
- **分段归因**（主要贡献段）：核心骨干 4 格；最大单项 P1/cmcc/busy/s1_chat·核心骨干=27ms；各段**均未见单点异常**（3σ 筛查）——最大单项落在该段分布内，不宜单独归因于该单元（单元间齐不齐见「分段异常定位」段）。
- **批化失真热点**：1 个 —— P1/cmcc/busy。
- **测量可信度**：无 clock/seq/parse 证据（覆盖缺口，非全部可信）。
- **有效率**：全部达门（≥80%）。
- **复测稳定性**：24 个单元全部达门。
- **接入介质**：无 transport 证据（覆盖缺口）。
- **分数侧归因**（拖累维度）：N2 4 格；最低 P1/cmcc/busy·N2=82。
- **优化前后**（base → opt）：4 个共同格中 4 个 Δ 超出噪声——改善 4、回退 0、持平 0；AQS 中位Δ 12。

> 以上为下方各段的**指路**，证据与完整表格见对应段落；口径与不可计算说明以各段为准。

## 点位 × 忙闲 × 运营商 热力卡（AQS 中位）

| 点位 | 运营商 | 时段 | AQS中位 | 分级 | n | 备注 |
|---|---|---|---|---|---|---|
| P1 | cmcc | busy | 68 | fair | 36 | MIXED_CAMPAIGN:base/opt |
| P1 | cmcc | idle | 73 | good | 36 | MIXED_CAMPAIGN:base/opt |
| P2 | cmcc | busy | 68 | fair | 36 | MIXED_CAMPAIGN:base/opt |
| P2 | cmcc | idle | 73 | good | 36 | MIXED_CAMPAIGN:base/opt |

## 分 KPI 热力卡（原始 KPI 中位 + 上报 KpiGrading 分级）

### 分 KPI 热力卡：`n1_rtt_p50_ms`（中位；分级=上报 KpiGrading 众数）

| 点位 | 运营商 | 时段 | 中位 | 分级 | n | 备注 |
|---|---|---|---|---|---|---|
| P1 | cmcc | busy | 38 | good | 36 | MIXED_CAMPAIGN:base/opt |
| P1 | cmcc | idle | 38 | good | 36 | MIXED_CAMPAIGN:base/opt |
| P2 | cmcc | busy | 38 | good | 36 | MIXED_CAMPAIGN:base/opt |
| P2 | cmcc | idle | 38 | good | 36 | MIXED_CAMPAIGN:base/opt |

## 复测稳定性（CV 门 ≤10%，对齐 M1 验收）

### 复测稳定性：`n1_rtt_p50_ms`（CV% = 样本 stdev/mean；门 ≤10% 为稳定）

| 单元 | n | 中位 | 均值 | CV% | 稳定? | 备注 |
|---|---|---|---|---|---|---|
| campaign_id=base · point_id=P1 · carrier=cmcc · time_band=busy · tier=core · profile_id=s1_chat | 6 | 65 | 65 | 0 | 稳定 | — |
| campaign_id=base · point_id=P1 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 6 | 20 | 20 | 0 | 稳定 | — |
| campaign_id=base · point_id=P1 · carrier=cmcc · time_band=busy · tier=regional · profile_id=s1_chat | 6 | 38 | 38 | 0 | 稳定 | — |
| campaign_id=base · point_id=P1 · carrier=cmcc · time_band=idle · tier=core · profile_id=s1_chat | 6 | 65 | 65 | 0 | 稳定 | — |
| campaign_id=base · point_id=P1 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 6 | 20 | 20 | 0 | 稳定 | — |
| campaign_id=base · point_id=P1 · carrier=cmcc · time_band=idle · tier=regional · profile_id=s1_chat | 6 | 38 | 38 | 0 | 稳定 | — |
| campaign_id=base · point_id=P2 · carrier=cmcc · time_band=busy · tier=core · profile_id=s1_chat | 6 | 65 | 65 | 0 | 稳定 | — |
| campaign_id=base · point_id=P2 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 6 | 20 | 20 | 0 | 稳定 | — |
| campaign_id=base · point_id=P2 · carrier=cmcc · time_band=busy · tier=regional · profile_id=s1_chat | 6 | 38 | 38 | 0 | 稳定 | — |
| campaign_id=base · point_id=P2 · carrier=cmcc · time_band=idle · tier=core · profile_id=s1_chat | 6 | 65 | 65 | 0 | 稳定 | — |
| campaign_id=base · point_id=P2 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 6 | 20 | 20 | 0 | 稳定 | — |
| campaign_id=base · point_id=P2 · carrier=cmcc · time_band=idle · tier=regional · profile_id=s1_chat | 6 | 38 | 38 | 0 | 稳定 | — |
| campaign_id=opt · point_id=P1 · carrier=cmcc · time_band=busy · tier=core · profile_id=s1_chat | 6 | 65 | 65 | 0 | 稳定 | — |
| campaign_id=opt · point_id=P1 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 6 | 20 | 20 | 0 | 稳定 | — |
| campaign_id=opt · point_id=P1 · carrier=cmcc · time_band=busy · tier=regional · profile_id=s1_chat | 6 | 38 | 38 | 0 | 稳定 | — |
| campaign_id=opt · point_id=P1 · carrier=cmcc · time_band=idle · tier=core · profile_id=s1_chat | 6 | 65 | 65 | 0 | 稳定 | — |
| campaign_id=opt · point_id=P1 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 6 | 20 | 20 | 0 | 稳定 | — |
| campaign_id=opt · point_id=P1 · carrier=cmcc · time_band=idle · tier=regional · profile_id=s1_chat | 6 | 38 | 38 | 0 | 稳定 | — |
| campaign_id=opt · point_id=P2 · carrier=cmcc · time_band=busy · tier=core · profile_id=s1_chat | 6 | 65 | 65 | 0 | 稳定 | — |
| campaign_id=opt · point_id=P2 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 6 | 20 | 20 | 0 | 稳定 | — |
| campaign_id=opt · point_id=P2 · carrier=cmcc · time_band=busy · tier=regional · profile_id=s1_chat | 6 | 38 | 38 | 0 | 稳定 | — |
| campaign_id=opt · point_id=P2 · carrier=cmcc · time_band=idle · tier=core · profile_id=s1_chat | 6 | 65 | 65 | 0 | 稳定 | — |
| campaign_id=opt · point_id=P2 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 6 | 20 | 20 | 0 | 稳定 | — |
| campaign_id=opt · point_id=P2 · carrier=cmcc · time_band=idle · tier=regional · profile_id=s1_chat | 6 | 38 | 38 | 0 | 稳定 | — |

## 序位效应诊断（n1_rtt_p50_ms；拉丁方反平衡是否奏效）

> 判据：同 profile 各**执行位次**的中位数极差 / 总体中位数 > 10.0% 即疑似残留序位偏倚（无效应=好结果）。

> ⚠ 语料无 `run.scenario_order` 证据，无法判断是否做过反平衡。

| profile | 位次中位数 | 极差 | 极差% | 总体中位 | 判定 | 备注 |
|---|---|---|---|---|---|---|
| s1_chat | #0:38(n=48) / #1:38(n=48) / #2:38(n=48) | 0 | 0 | 38 | 无明显效应 | — |

## 有效性与失效原因（每格的有效样本分母）

> 全语料尝试 144 个场景，可用 120 （83.3%）；低于 80% 的单元标 `LOW_VALID_RATE`。INVALID 场景 KPI 为空、会被热力卡/归因静默丢弃——**此表即那些被丢弃样本的去向**。

| 点位 | 运营商 | 时段 | profile | 尝试 | 有效 | 低置信 | 失效 | 未知 | 有效率 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|
| P1 | cmcc | busy | s1_chat | 36 | 30 | 0 | 6 | 0 | 83.3% | — |
| P1 | cmcc | idle | s1_chat | 36 | 30 | 0 | 6 | 0 | 83.3% | — |
| P2 | cmcc | busy | s1_chat | 36 | 30 | 0 | 6 | 0 | 83.3% | — |
| P2 | cmcc | idle | s1_chat | 36 | 30 | 0 | 6 | 0 | 83.3% | — |


## 测量可信度（时钟 / 流完整性 / 解析开销）

> 上方时延中位数背后的**仪器**可信度：时钟可疑=R-22（|漂移|>100ppm 或端点缺失），该场景 TTFT/ITL 存疑；seq 异常=gap/dup>0；解析开销大会混淆 ITL（端侧算力≠网络）。各信号分母=实际带标注的场景数，未标注**不算干净**。时钟可疑过半标 `时钟可疑热点`。

_无可信度证据（clock/seq/parse 块均未标注）——覆盖缺口，非全部可信。_

## 三级差分归因矩阵（n1_rtt_p50_ms，单位 ms）

> claim_scope: `application_end_to_end_to_probe_node` — 应用层路径分段，非无线层/运营商全网评级。
> 方法：铁律 3 客户端差分消共模；缺层记 coverage 不外推；负增量记 inversion 不清零。

| 单元 | 覆盖层级 | 接入(metro) | 区域骨干+ | 核心骨干+ | 端到端(core) | 备注 |
|---|---|---|---|---|---|---|
| point_id=P1 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城,区域,中心 | 20 | 18 | 27 | 65 | MIXED_CAMPAIGN:base/opt |
| point_id=P1 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城,区域,中心 | 20 | 18 | 27 | 65 | MIXED_CAMPAIGN:base/opt |
| point_id=P2 · carrier=cmcc · time_band=busy · profile_id=s1_chat | 同城,区域,中心 | 20 | 18 | 27 | 65 | MIXED_CAMPAIGN:base/opt |
| point_id=P2 · carrier=cmcc · time_band=idle · profile_id=s1_chat | 同城,区域,中心 | 20 | 18 | 27 | 65 | MIXED_CAMPAIGN:base/opt |

## 分段异常定位（n1_rtt_p50_ms，同一段跨单元比较，ms）

> **这一段回答的是**：某一段慢，是**这个点位特有**，还是**所有点位都这样**——前者指向该点位，后者是本次测量路径的**共性**（例如到中心镜像端的物理距离），**不构成任何点位的问题**。
> **口径**：与**本语料内**同段各单元的中位数比较，稳健离差 MAD，阈值 3×1.4826×MAD。这是**描述性筛查、不是显著性检验**，也**不与任何外部基准比较**；不可计算的单元不参与比较且如实计数。

> **注意**：`未见单点异常` 只表示**没有单元越过筛查阈值**，**不等于各单元相同**——单元间到底有多齐，看 `离差/典型` 一列。该列小且无异常，才说得上是路径共性。

| 段 | 参与单元 | 典型值(中位) | 离差(MAD) | 离差/典型 | 显著高 | 显著低 | 判读 |
|---|---|---|---|---|---|---|---|
| 接入(metro) | 4 | 20 | 0 | 0% | — | — | 全部单元取值相同 |
| 区域骨干+ | 4 | 18 | 0 | 0% | — | — | 全部单元取值相同 |
| 核心骨干+ | 4 | 27 | 0 | 0% | — | — | 全部单元取值相同 |

## AQS 分数侧归因（各维度子分 + 拖累维度）

> 归因矩阵的分数侧互补：composite AQS 低时，指出是哪个 KPI 维度在拖后腿。子分 0-100，越高越好；`拖累` = 中位子分最低的维度。

| 点位 | 运营商 | 时段 | runs | T1 | N1 | N2 | 拖累 | 极差 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| P1 | cmcc | busy | 36 | 98 | 95 | 82 | **N2**=82 | 16 | — |
| P1 | cmcc | idle | 36 | 98 | 95 | 88 | **N2**=88 | 10 | — |
| P2 | cmcc | busy | 36 | 98 | 95 | 82 | **N2**=82 | 16 | — |
| P2 | cmcc | idle | 36 | 98 | 95 | 88 | **N2**=88 | 10 | — |

## 批化(buffering)归因（取证/失真核算）

> **R-05**：批化标注为**取证证据**，**不改判** validity/score（本表亦然）。`none`=未见批化失真；非 `none` 占多数的格标 `失真热点`。空块=未检测（非 0）。

| 点位 | 运营商 | 时段 | n | 众数归因 | 批化分中位 | sawtooth | 近零到达 | 疑似占比 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| P1 | cmcc | busy | 36 | middlebox_suspect | 0.42 | 0.35 | 0.28 | 100% | **失真热点** |
| P1 | cmcc | idle | 36 | none | 0.02 | 0.01 | 0 | 0% | — |
| P2 | cmcc | busy | 36 | none | 0.02 | 0.01 | 0 | 0% | — |
| P2 | cmcc | idle | 36 | none | 0.02 | 0.01 | 0 | 0% | — |

## 接入介质对比（wifi vs cellular，AQS 中位）

> transport 取 run 显式设置，`auto` 由各场景 `network_snapshot` 观测共识推得；不一致=mixed、无观测=unknown，**均不并入任何介质**。Δ=cellular−wifi（AQS 越大越好，负值=蜂窝更差）。* = 样本不足。

_无 transport 证据（run 均为 auto 且无 network_snapshot 观测）——覆盖缺口，非数据。_

## 优化前后对比（before=`base` → after=`opt`，AQS 中位）

> **噪声尺度**：Δ 旁的 `±` 是该格测量离散度推得的**指示性**噪声量级（正态近似 SE≈1.253·sd/√n，两格求和取方根）。时延右偏，故它只指示**量级、不是显著性检验**；|Δ| 小于它的格标 `噪声内`——**不应作为改善/回退的结论**。`±0` 只表示这几次复测未观察到离散，**不等于没有噪声**；样本不足的格（标 `low_conf`）其噪声估计本身也不可靠，噪声无法估计时留 `—`、不以 0 顶替。

| 点位 | 运营商 | 时段 | before | after | Δ | 备注 |
|---|---|---|---|---|---|---|
| P1 | cmcc | busy | 62 | 74 | 12 ↑ ±0 | — |
| P1 | cmcc | idle | 67 | 79 | 12 ↑ ±0 | — |
| P2 | cmcc | busy | 62 | 74 | 12 ↑ ±0 | — |
| P2 | cmcc | idle | 67 | 79 | 12 ↑ ±0 | — |
