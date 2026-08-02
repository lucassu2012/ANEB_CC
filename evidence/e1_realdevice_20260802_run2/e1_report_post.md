# E1 已知真值刺激实验 —— 判读结果

> 出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §3.3 实验 E1。
> 状态词只用 PASS / FAIL / NOT_EXECUTED。空样本一律 NOT_EXECUTED，不折 0。

## 0. 本次刺激配置

| 项 | 值 |
|---|---|
| `interval_ms` | 800 |
| `count` | 6 |
| `roi_px` | 480 |
| `warmup` | 1 |
| `refresh_hz` | 90.000 |
| `screen_px` | 1200x2486 |
| 翻转总数 / 可用（去预热、有 commit） | 49 / 48 |
| ⚠ 重复 seq（App 被重启过，后者覆盖前者） | 6 |

**一帧 = 11.111 ms**（实测，非硬编码 33ms —— spec §3.1）。

## 1. 时钟基（跨通道比较的前提）

BOOTTIME − MONOTONIC 偏移中位数 = 94513649503167 ns，跨度 = 5729 ns（n=48）。

> 跨度不是噪声，是这段时间里设备深睡了多久。它非 0 即意味着通道 A（BOOTTIME）
> 与通道 C（MONOTONIC）**不能直接相减** —— 这修正了 spec §3.2「E_clock 已有界」
> 的适用范围：那句话对「只有通道 A」成立，通道 C 一入场就不再成立。

## 2. 按通道分列

| 通道 | 量的是什么 | n | dropped | p50 (ms) | p90 (ms) | p99 (ms) | 判定 |
|---|---|---|---|---|---|---|---|
| A 无障碍事件 | t_event → t_present（跨基，已换算） | 0 | — | — | — | — | **NOT_EXECUTED** — 通道 A 无逐事件时戳 |
| C 渲染时间线 | t_commit → t_present（同基） | 0 | 48 | — | — | — | **NOT_EXECUTED** — 缺分布或缺实测刷新率 |
| B screencap 帧差 | **不报时间误差**，只报采样周期 | 40 | — | 2035.503 | 6679.476 | 14956.360 | PASS |

**通道 A 未判读的原因**：无障碍侧无逐事件时戳：AnebAccessibilityService 今天只打 click 型 ADAPTER_EVT（无 t_boot_ns）与 5s 节流的 ADAPTER_OBS 聚合。需 :probe 侧一行 additive 扩展后方可判读，见本文件模块注释。

通道 B 检出翻转 3 次（刺激源共翻 6 次）——检出率不是时序主张，只说明 ROI 与阈值选得对不对。

## 3. 通道 A 弱检查（今天就能跑的那条）

`ADAPTER_OBS.cadence_p50_ms` vs 刺激间隔：**NOT_EXECUTED**（cadence=— ms, interval=— ms, n=0）。

> 它证不了偏移，只证「通道 A 确实看见了这串翻转」。判据带宽 ±20% 是刻意取宽的，免得被读成精度指标。

