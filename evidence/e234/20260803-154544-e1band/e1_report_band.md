# E1 已知真值刺激实验 —— 判读结果

> 出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §3.3 实验 E1。
> 状态词只用 PASS / FAIL / NOT_EXECUTED。空样本一律 NOT_EXECUTED，不折 0。

## 0. 本次刺激配置

| 项 | 值 |
|---|---|
| `interval_ms` | — |
| `count` | — |
| `roi_px` | — |
| `warmup` | — |
| `refresh_hz` | — |
| `screen_px` | — |
| 翻转总数 / 可用（去预热、有 commit） | 0 / 0 |

**一帧 = 16.667 ms**（来源：SurfaceFlinger 实测（优先，L-1）；非硬编码 33ms —— spec §3.1）。

## 1. 时钟基（跨通道比较的前提）

BOOTTIME − MONOTONIC 偏移中位数 = — ns，跨度 = — ns（n=0）。

> 跨度不是噪声，是这段时间里设备深睡了多久。它非 0 即意味着通道 A（BOOTTIME）
> 与通道 C（MONOTONIC）**不能直接相减** —— 这修正了 spec §3.2「E_clock 已有界」
> 的适用范围：那句话对「只有通道 A」成立，通道 C 一入场就不再成立。

## 2. 按通道分列

| 通道 | 量的是什么 | n | dropped | p50 (ms) | p90 (ms) | p99 (ms) | 总量 vs 1 帧 |
|---|---|---|---|---|---|---|---|
| A 无障碍事件 | t_event → t_present（跨基，已换算） | 0 | — | — | — | — | **NOT_EXECUTED** — 缺时钟偏移 |
| C 渲染时间线 | t_commit → t_present（同基，**实测总量**——含 E_pipeline，非纯通道误差，D-417/D-418） | 0 | 0 | — | — | — | **NOT_EXECUTED** — 缺分布或缺实测刷新率 |
| C（framestats，L-2） | t_commit → SwapBuffersCompleted（同基，第二支路，**实测总量**——含 E_pipeline，非纯通道误差，D-417/D-418） | 0 | 0 | — | — | — | **NOT_EXECUTED** — 缺分布或缺实测刷新率 |
| B screencap 帧差 | **不报时间误差**，只报采样周期 | 164 | — | 1747.058 | 2293.103 | 3364.837 | PASS |

**通道 A 未判读的原因**：缺 BOOTTIME↔MONOTONIC 偏移，跨基比较不可做

通道 B 检出翻转 0 次（刺激源共翻 — 次）——检出率不是时序主张，只说明 ROI 与阈值选得对不对。

**通道 C 交叉验证（`--latency` vs `framestats`，L-2，spec `INSTRUMENTATION_SPEC` §6 K-2）**：NOT_EXECUTED — 至少一条支路无可用样本，跨支路比较不可做

**G-2 本义（spec §3.4，纯 `E_transport⊕E_quant` ≤ 1 帧）**：**NOT_EXECUTED** — G-2 本义需 E2 把 E_pipeline 从总量中分解出去后才可判——E1 未做（spec §3.2/§3.4，D-417/D-418）

> 上面「总量 vs 1 帧」那一列是**独立字段**，不是 G-2 本义——两者语义不同、互不代表（D-417/D-418）：即便总量列 PASS，也不能读成 G-2 本义 PASS。

**候选 C 生效（PO 批复 D-432②）**：Profile 3 时间敏感数据（通道 A 类比读法，借用通道 C 的commit→present 量级做保守上界）可读作呈现时刻的**下界**，真实呈现可能晚至 +33.333ms（单侧，不是对称±；帧基准取值规则见frame_ms_source/D-414），不再因 G-2 本义未判而恒LOW/INCONCLUSIVE（spec §3.4 候选 C 例外）。依据=run3 单窗n=53、覆盖会话前~70%（D-417 §4 截尾），下一个 E1 型设备窗（可与 E2 真机窗并窗；T30 是 forensic KPI 批、不产本条依赖的装置标定数据，D-438）后应据新数据收窄或修订。这是 E2 分解前的当下语义，不是永久判据；升级路径=候选 B（E2 可跑后按 T29 占比门提案，阈值待真实数据）。

## 3. 通道 A 弱检查（今天就能跑的那条）

`ADAPTER_OBS.cadence_p50_ms` vs 刺激间隔：**NOT_EXECUTED**（cadence=— ms, interval=— ms, n=0）。

> 它证不了偏移，只证「通道 A 确实看见了这串翻转」。判据带宽 ±20% 是刻意取宽的，免得被读成精度指标。

