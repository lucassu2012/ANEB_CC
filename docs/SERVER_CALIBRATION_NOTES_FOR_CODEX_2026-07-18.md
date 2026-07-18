# 给 Codex 的 Profile 2 服务端仿真标定交付（2026-07-18，D-58）

> 用途：Profile 2（`/stream` token 仿真）的 TTFT/TPS/ITL/思考段参数此前为 [GUESS]。现有**真实
> Kimi Code API 标定数据**（首份，计划 Step2 一直阻塞项）。本文把标定值整理为**可评估的服务端
> 仿真校准建议**，供 Codex 按需采纳（部署权=Codex，D-35；此文不改任何 E-01 配置）。
> 权威数据：`spec/calibration/kimi-code-api-k2.7.yaml`。

## 1. 标定数据（真实测量，n=5 分布）

Kimi Code API（`api.kimi.com/coding`，Anthropic Messages 协议，模型 k2.7-code-highspeed），
5 个不同技术 prompt 流式采集：

| 指标 | 实测 | 口径 |
|---|---|---|
| 服务端首响应（message_start） | median **3063ms**（range 2917–3120，极稳定） | 请求→首个 SSE 事件，含公网 RTT |
| 首 token TTFT | median **3645ms** | 请求→首个 token delta |
| token 间隔 ITL | median **259ms**（range 253–337） | 相邻 delta；thinking/text 两段+跨 prompt 三重互证 |
| TPS | **~4 tok/s** | output_tokens / 生成时长 |
| 用户可见首字（含思考） | **~39s**（n=1，思考主导） | text 首字；k 系列强制深度思考 33–60s+ |

## 2. 关键画像特征（影响仿真设计）

- **k 系列强制深度思考是刚性特性**：k2.7 对「1加1等于几」这种极简问题也思考 467+ token/>65s——
  「highspeed」名不副实。**用户可见首字始终由思考时长主导（几十秒）**，不适合快速对话场景。
- **token 节奏稳定**：ITL ~259ms/token、TPS ~4/s，跨思考/正式回复两段一致——服务端 token 生成
  是稳定节奏，仿真可用固定间隔近似（而非随机抖动主导）。
- **首响应延迟稳定**：~3s（含公网 RTT），range 仅 203ms。

## 3. 服务端 `/stream` 仿真校准建议（供评估）

若要让 Profile 2 仿真「像 Kimi Code k2.7」，建议参数（相对现有 [GUESS]）：

| 仿真参数 | 现状 | 建议校准值 | 依据 |
|---|---|---|---|
| `t_srv_ms`（首响应/TTFT-dwell） | [GUESS] | **~3000ms**（服务端首响应）+ **思考段 33–60s**（若模拟推理模型） | message_start 3063ms + 思考主导 |
| `tps`（token 速率） | [GUESS] | **~4 tok/s**（k 系列 API 口径） | ITL 259ms → 3.9 tok/s |
| `think_gaps`（思考静默段） | 空/[GUESS] | **前置一段 33–60s 思考静默**（k 系列必须） | 用户可见首字 39s 由思考主导 |
| token 间隔抖动 | — | ITL p95/median = 337/259 ≈ **1.3×**（低抖动） | 间隔分布集中 |

## 4. 口径边界（严格，勿混用）

- 本标定 = **API 直调 token 流口径**（网络+服务端），**≠** Profile 3 App 的 UI 呈现层
  （豆包 1984ms 等）或网络传输层（入云拓扑）——三口径分标，见 `docs/PROFILE3_PORTRAIT_2026-07-18.md`。
- **Kimi Code API（编程接口 k2.7）≠ Kimi App（消费产品）**：两者可能不同后端/模型，标定值不可
  直接套用到 Kimi App 画像。
- 采集环境：PC/公网 WiFi（非受控网络），含公网 RTT；n=5（首响应/ITL）/n=1（用户可见首字）；
  同一模型同一网络 → **恒 LOW/INCONCLUSIVE**。TPS ~4 偏低疑含推理限速，非服务端峰值。

## 5. 采纳方式

Codex 自行评估是否将上述建议并入 `/stream` 仿真参数（或某个新 profile 如 `kimi_reasoning_sim`）。
若采纳，建议标注 `behavior_model_id` 含标定来源（如 `kimi-k2.7-api-2026-07-18`）以可追溯。
本文不改任何 E-01 配置——纯建议交付。

---
*Profile 2 标定交付 v1 · 2026-07-18 · 首份真实 LLM API 标定*
