# 无线上下文接线规格 v1.0（分析层 → P1b/spec 交接）

> **一句话**：设备侧已经采集了无线上下文，App 内部也在用，但**导出的 run 契约里一个无线
> 字段都没有**，所以战役分析层永远看不到它。本规格请求把它加进 `network_snapshot`。
>
> **本规格与常规「请加个字段」的不同**：**消费方已经写好并跑通了**。下表每个字段都点名
> 了它在分析层的读者与用途；`radio_rollup.py` 已合入综合报告与 CSV，并有专属守卫。
> 字段一到，本层零改动即可产出。**没有消费方的字段本规格一个都不要**（§4）。

*v1.0 · 2026-07-29 · 分析层 lane 撰写 · 承 D-284*

---

## 1. 为什么现在提

三级差分归因随 **D-48（2026-07-17）** 取消（只保留单实例 E-01），
`PLAN_ALIGNMENT` §7 第 3 条为此记下的替代方案是：

> 归因改以**单点参考端 + 多维协变量（无线上下文** / UDP 未整形协变量 / 忙闲 / 双运营商**）**为主

**无线上下文是这句话里点名的第一顺位协变量，而它不在分析层拿得到的数据里。**
这不是推断，是实测：

| 事实 | 证据 |
|---|---|
| 设备侧**有**完整采集 | `app/probe/.../radio/RadioCollector.kt`（NR `ssRsrp`/`ssSinr`、LTE `rsrp`/`rsrq`/`sinr`、`pci`/`tac`/`arfcn`） |
| App 内部**有**消费 | `BufferingDetector` 的 R1 弱信号联动、`ReportAnalyzer` 的自变量维度、结果页无线摘要 |
| 导出契约里**没有** | `ResultReporter.kt` 写入 `network_snapshot` 的仅 `transport` / `capabilities` / `interface` / `server_observed_addr`；全文件无任何无线字段 |
| 归档语料里**没有** | 全仓 `evidence/` 中提到 rsrp 的四个文件全是日志与 markdown，**无一份 result-run 语料带无线数据** |
| 计划里的名字**对不上** | 计划 §5.2 的 descriptor 写 `record: [..., radio_ctx, ...]`，而 `radio_ctx` 这个名字**在代码库中一次都没出现过**——两份文档之间从没对过账 |

## 2. 请求的形状（加性，不动既有字段）

在**每个场景**的 `network_snapshot` 下新增可选对象 `radio`。蜂窝场景才写；
wifi 场景**不写该键**（而不是写一个全 null 的壳）。

```json
"network_snapshot": {
  "transport": "cellular",
  "capabilities": "INTERNET,VALIDATED",
  "interface": "rmnet0",
  "server_observed_addr": "203.0.113.7:8443",
  "radio": {
    "rat": "NR",
    "rsrp_dbm": -98,
    "sinr_db": 7,
    "pci": 238,
    "tac": 12345,
    "arfcn": 504990,
    "sampled_n": 12,
    "stale": false
  }
}
```

## 3. 逐字段：语义、单位、以及**谁在读它**

| 字段 | 类型/单位 | 语义 | 分析层的消费方（函数级） |
|---|---|---|---|
| `rat` | string 或 null | `TelephonyManager.dataNetworkType` 名称（`NR`/`LTE`/…） | `radio_rollup._samples` 计数 → 同格多制式标 `MIXED_RAT`：一个格里混了两种制式，它的中位数谁也不代表 |
| `rsrp_dbm` | number 或 null，dBm | LTE RSRP / NR SS-RSRP，**场景期间中位** | `radio_rollup` 入池取中位 → `campaign_common.signal_band()` 定档；值域检查 `rsrp_dbm ∈ [-160,-30]` |
| `sinr_db` | number 或 null，dB | LTE RSSNR / NR SS-SINR，**场景期间中位** | 同上；R1 判据的第二分量；值域 `[-30,45]` |
| `pci` | integer 或 null | 物理小区标识 | `radio_rollup.cell_key` 三元组之一 |
| `tac` | integer 或 null | 跟踪区码 | 同上 |
| `arfcn` | integer 或 null | 频点号 | 同上——三者合成服务小区标识，驱动 `MIXED_SERVING_CELL` 与 **`CELL_CHANGED`**（同点位忙闲挂了不同小区 → 该点位忙闲差里混着小区差） |
| `sampled_n` | integer ≥0 或 null | 上面两个中位数**由几个读数得出** | `radio_rollup` 取各场景中位与样本门限比较 → `RADIO_THIN`：格里 run 数够、但每次只采到一两个读数，是另一种「薄」 |
| `stale` | boolean | 该样本是否已超出采集侧的新鲜度窗口 | `radio_rollup._samples` **排除并计数** → `RADIO_STALE`；**排除不等于没问题**，报告会明说 |

**R-10 语义（硬性）**：任何一项不可得一律写 `null`，**不得**写 `0`、`-1`、
`Integer.MAX_VALUE` 或其他哨兵。分析层的值域检查会把 `0` dBm 拦成
`IMPLAUSIBLE_VALUE`——它比真实读数高约 65 dB，一旦入池能把一个弱信号格算成良好格。

## 4. **本规格不要什么，以及为什么**

- **不要 `rsrq`**：设备侧有，但分析层**目前没有任何读者**。要一个没人读的字段，正是
  D-276 记下的反面教材。将来若有消费方，再走一次同样的流程即可。
- **不要 `cell_key` 这类合成标识**：请给 `pci`/`tac`/`arfcn` 原始值，合成规则留在分析层
  ——合成规则是可测的，而生产者替下游做的语义决定不是。
- **不要整段时间序列**：本层按场景取中位，不需要逐样本序列；真要做细粒度分析时再谈。

## 5. 阈值搬进 spec（**可直接动手的交接，不是建议**）

R1 的四个阈值今天**只存在于** `app/probe/src/main/java/com/aneb/probe/scoring/BufferingDetector.kt`：

| 常量 | 现值 | 含义 |
|---|---|---|
| `RSRP_WEAK_DBM` | `-105.0` | 弱信号线（dBm） |
| `RSRP_GOOD_DBM` | `-95.0` | 良信号下界（dBm） |
| `SINR_WEAK_DB` | `0.0` | 弱信号线（dB） |
| `SINR_GOOD_DB` | `10.0` | 良信号下界（dB） |

`spec/` 树里没有它们的位置，后果是**任何第二个消费方都只能抄一份**——分析层现在就抄了。
抄本已被守卫钉住（`test_the_signal_bands_match_the_producer_that_defines_them` 逐个读
Kotlin 源码对账，任一侧漂移即失败），所以不是隐患；但这是**不该存在的重复**，
且每多一个消费方就多一份。

### 5.1 放哪、长什么样

**`spec/scoring/radio_bands.yaml`**，格式对齐同目录既有的 `vetoes.yaml`：
`schema_version: "1.0.0"` + 头部注明**逐字导出的来源**（哪个 .kt 的哪些常量）+
点名负责对拍的测试。内容形如：

```yaml
schema_version: "1.0.0"
bands:
  rsrp_weak_dbm: -105.0
  rsrp_good_dbm: -95.0
  sinr_weak_db: 0.0
  sinr_good_db: 10.0
```

**组合语义也要写进头部注释**——它比数值更容易被抄错：弱 = **任一已知分量**越线；
良 = **已知分量均不越线**（未知分量不阻止「良」，也不为它背书）；两个分量都不可得 = **不定档**。

### 5.2 两边各做什么

| 谁 | 做什么 | 为什么 |
|---|---|---|
| **P1b / spec lane** | 建 `spec/scoring/radio_bands.yaml`；在 Kotlin 侧加一条对拍测试，形如既有的 `SpecScoringParityTest.veto_constants_parity`——**代码侧常量全集必须被该文件覆盖** | 与 scoring 包同一套路：**导出 + 对拍**，而不是让代码去读 YAML |
| **P1b / spec lane** | 给该文件在 `scripts/validate_spec_scoring.py` 的 `_CHECKS` 里加一个检查器（四键齐备、均为数、`weak < good`），**或**在 `_NO_INVARIANTS` 里写明它为何无需不变量检查 | **该门已改为遍历目录**：未注册的 YAML 会让 `spec-scoring-unit` 直接失败并点名（D-291）——文件落地即被看管，不会静默无人校验 |
| **分析层（本 lane）** | 把 `test_the_signal_bands_match_the_producer_that_defines_them` 的对账目标从 `.kt` 源码换成该 YAML | 少一跳跨树依赖，并让 spec **在事实上**成为单一事实源，而不只是原则上 |

**三步互不阻塞，顺序无所谓。** 文件先落地也行——门会立刻要求给它一个检查器，那正是想要的效果。

## 6. 验收（两边各自可独立验证）

**生产侧**：一次真机 run 的 JSONL 里，蜂窝场景的 `network_snapshot.radio` 八个键齐备，
不可得项为 `null`；wifi 场景无 `radio` 键。

**分析层侧（现在就能跑，无需等接线）**：

```bash
python synth_campaign.py -o rehearsal_radio.jsonl --radio --tiers metro --campaigns SZ
```

```bash
python radio_rollup.py rehearsal_radio.jsonl
```

彩排语料按设计**同时产出**七个标记（`MIXED_SERVING_CELL` / `MIXED_RAT` /
`CELL_CHANGED` / `CELL_PARTIAL` / `RADIO_STALE` / `RADIO_THIN` /
`IMPLAUSIBLE_VALUE`）与弱/中/良三档，故「工具能不能咬住」不必靠承诺。
第八个标记 `RADIO_ABSENT` 由单测覆盖（默认网格里每个格都有无线数据，
产不出该情形——**这一点是写下来的，不是漏掉的**）。

**接线未落地期间**：综合报告的「无线上下文」段照常出现，写明**这是采集缺口、
不是「信号良好」**，并指回本规格。缺口因此在每一份报告里都是可见的。

---

*相关：[`CAMPAIGN_LABELS_WIRING_SPEC.md`](CAMPAIGN_LABELS_WIRING_SPEC.md)（C1 标签接线，同类交接）、
[`M2_GRID_DESIGN_PROPOSAL.md`](M2_GRID_DESIGN_PROPOSAL.md) §4.1（不买服务器时的分段替代路线）。*
