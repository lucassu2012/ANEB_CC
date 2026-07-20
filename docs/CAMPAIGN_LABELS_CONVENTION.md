# ANEB 战役标签约定 v0.1（campaign labels）

> 用途：为**战役级分析与报告层**（三级归因矩阵 · 点位×忙闲×运营商热力卡 · 优化前后对比 · 综合报告）
> 提供结果记录的分组维度。当前结果体 Schema（`spec/schemas/result-run.schema.json`，schema_version 1.0）
> **没有**承载点位/运营商/时段/服务层级标签——本文件定义补齐这些维度的**可选、加性**约定。
>
> **状态：分析层约定（提案），未接线到生产。** 分析脚本（`scripts/campaign_report.py`、`scripts/attribution.py`）
> 读到 `run.campaign` 即用、读不到优雅降级（不因缺标签报错，不以哨兵顶替——R-10 精神）。
> 生产接线（spec 加性定义 + 客户端 `ResultReporter` 写入 + P1a 选签 UI）留作**后续 spec-first 干净交接**，见 §4。

---

## 1. 为什么需要（缺口来源）

开发计划 v1.0 §6 里程碑 **M2 外场 MVP** 的验收物是《城市 AI 业务网络体验热力卡与归因报告》，其数据结构要求：

- **点位 × 忙闲 × 双运营商**网格（热力卡）——需 `point_id` / `time_band` / `carrier`；
- **三级（同城/区域/中心）差分归因**（架构图"归因矩阵"，§4.2"三级差分即归因输入"）——需 `tier`；
- **优化前后对比**——需 `campaign_id`（或时间范围）区分两批测量。

现结果体 Schema 只有 `run.transport`（auto/wifi/cellular）、`scenario.network_snapshot.*`、
`scenario.kpi.n1_rtt_p50_ms` 等，**无上述四个分组维度**。故战役分析需要一层标签约定。

## 2. 约定：可选加性 `run.campaign` 块

结果体 Schema 声明 `additionalProperties: true`（双端合同显式容忍未知字段，Go 服务端 `validateResultContract`
只校验必填、不拒新增）。因此新增一个**可选** `run.campaign` 对象是**合同安全的加性变更**——旧记录无此块照常有效，
新记录带此块也通过校验。

```jsonc
"run": {
  "run_id": "...",
  // …既有字段…
  "campaign": {                      // 可选；缺失=未标注战役（分析层降级为单格"unlabeled"）
    "campaign_id": "shenzhen-2026Q3-baseline",  // 战役标识（优化前后对比按此分组）
    "tier": "metro",                 // 服务层级：metro(同城) | regional(区域) | core(中心)；缺失=未知层级
    "point_id": "SZ-CBD-01",         // 点位标识（外场测点，热力卡行）
    "carrier": "cmcc",               // 运营商：cmcc(移动) | cucc(联通) | ctcc(电信) | 其它自定义
    "time_band": "busy",             // 时段：busy(忙时) | idle(闲时)；缺失=未知时段
    "server_tier_endpoint": "https://metro.example:8443"  // 可选诊断：本 run 目标服务端（层级对账）
  }
}
```

### 2.1 字段语义与取值

| 字段 | 类型 | 取值 | 缺失时分析层行为 |
|---|---|---|---|
| `campaign_id` | string | 自由标识，建议 `<城市>-<年季>-<批次>` | 归入 `campaign_id="unlabeled"`；优化前后对比不可用 |
| `tier` | string | `metro` / `regional` / `core` | 该 run 不进三级归因（记 coverage 缺口，不猜层级） |
| `point_id` | string | 外场测点自由标识 | 热力卡归入 `point_id="unlabeled"` 单格 |
| `carrier` | string | `cmcc`/`cucc`/`ctcc`/自定义 | 热力卡 carrier 维塌缩为 `carrier="unknown"` |
| `time_band` | string | `busy` / `idle` | 热力卡 time_band 维塌缩为 `time_band="unknown"` |
| `server_tier_endpoint` | string(可选) | URL | 仅诊断，不参与分组 |

**R-10 铁律**：任何缺失标签**绝不**折算成默认值当真值参与统计——降级为显式 `unlabeled`/`unknown` 桶并在报告里
标注 coverage 缺口。热力卡某格样本数 < 阈值（默认 3）标 `low_confidence`，不隐藏、不补零。

## 3. 三级差分归因方法学（铁律 3：客户端时间戳差分消共模）

同一客户端、同一接入网、同一时段，对三级镜像服务端各测一轮，得 `tier ∈ {metro, regional, core}` 的
网络层 KPI（RTT `n1_rtt_p50_ms`，或 TTFT `t1_ttft_ms`）。差分归因：

```
access_component        = median(RTT_metro)                    # 接入路径地板（末端+同城汇聚；蜂窝含无线段）
regional_backbone_incr  = median(RTT_regional) − median(RTT_metro)   # 区域骨干往返增量
core_backbone_incr      = median(RTT_core)    − median(RTT_regional) # 核心骨干往返增量
```

- 三级同客户端/同接入/同时段 → **接入分量在差分中消去**（共模抵消，铁律 3），增量项**净化**为骨干段贡献。
- TTFT 差分同理消去服务端处理 `T_srv`（镜像同逻辑）→ `(TTFT_core − TTFT_metro)` 净得网络路径增量，
  与 RTT 差分互为交叉校验。
- **诚实约束**：
  - 某层级缺失 → 对应增量 `null`（不可计算），报告记 coverage，不外推。
  - **负增量**（区域快于同城）不静默 clamp 到 0——记为 `inversion`（路由/anycast/CDN 边缘比标称层级更近，或测量噪声），如实呈现。
  - 每层级样本 < `MIN_SAMPLES`（默认 5）→ 该格 `low_confidence`。
  - `claim_scope` 恒为 `application_end_to_end_to_probe_node`：归因是**应用层路径分段**，**不表述为**无线层评级/运营商全网 SLA/MOS。

## 4. 生产接线（后续 spec-first 交接，本轮不做）

分析层就绪后，让真实 run 携带 `run.campaign` 需要（按铁律"先改 spec、后动代码"）：

1. **spec**：`result-run.schema.json` 的 `run.properties` 加**可选** `campaign` 定义（加性，不进 `required`）。
2. **客户端**：`app/probe/.../engine/ResultReporter.kt` 从测试发起参数写入 `run.campaign`；
   来源 = P1a 选签 UI（计划 §4.1"测试发起：选 Profile/场景标签"）。
3. **P1a**：发起测试时采集点位/运营商/时段/战役标签（运营商可由 `TelephonyManager` 自动填，时段可由 `started_at_epoch_ms` 推）。

在此之前，标签可由**离线补注**注入历史 JSONL（`scripts/` 提供补注辅助），或分析层按 `started_at_epoch_ms`
推 `time_band`、按现有 `guard_metadata`/`network_snapshot` 推运营商作为**降级近似**（标注为推断、非 KNOWN）。

---

*v0.1 · 2026-07-20 · 分析层约定，未接线生产。消费者：`scripts/campaign_report.py`、`scripts/attribution.py`。*
