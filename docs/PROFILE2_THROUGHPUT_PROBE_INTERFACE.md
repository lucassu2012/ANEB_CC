# 面向 v2 UI 团队的接口定义 · Profile 2 单流自适应窗口 goodput 探针（T47）

**状态**：接口定义 v2（已按三透镜批判复核修订）· 2026-08-04 · owner=v4 · 未动代码
**姊妹文档**：[`docs/PROFILE2_THROUGHPUT_PROBE_SPEC.md`](PROFILE2_THROUGHPUT_PROBE_SPEC.md)
（权威契约定义在 §8.4；本文是面向 v2 消费方的精确重述 + 边界说明）
**目标**：v2 团队可直接照此实现 UI，无需再确认字段名/类型/出现条件。

---

**相对上一版的主要修正**（供已看过上一版的读者快速定位改动）：§3 的 JSON 示例改为
**schema-完整**（补齐所有既有必填字段，不再是一个通不过 schema 校验的片段）；下行侧 KPI id 从
`D2` 改名 `D3`（避开与网格决策旋钮"D2=双运营商"的命名空间碰撞）；`profile_version` 字段格式改正
为裸 semver（不带 `id@` 前缀）；`scenario_order` 一节改为明确声明"完全不变，`s4_throughput` 不出现
在其中"，删除了上一版暗示"追加第四段"的示例；新增 §0 术语澄清（单流 goodput，非链路容量）；
新增关于 `sample_count`/`low_confidence` 语义分叉、以及 `run.profile_versions`（顶层聚合字段）不
扩展的明确说明。

---

## 0. 术语澄清：这组字段测的是什么（先读这个，避免文案层面过度宣称）

`u3_*`/`d3_*` 这组字段是**单流应用层 goodput**（这一条 TCP 连接在这段时间内实际跑到的速度），
**不是**链路名义容量、也不是多流聚合带宽。实测约束：底层 `AnebClient.downloadDrain`/
`uploadBurst` 每次调用只发起一个 HTTP 请求，无并行连接——在高带宽×高延迟路径上，这类单流测量会
系统性地低于链路真实容量（类比：`iperf3` 不加 `-P` 参数时的单流模式）。

**UI 文案要求**：不要把这组数字包装成"网速""带宽""链路速度"等会被理解为链路容量的措辞，建议使用
"本次连接实测速度""单流传输速度"一类更精确的表述。这一点比"数字对不对"更容易被产品阶段忽略，
必须在文案设计阶段就处理，不能留到上线后才发现。

---

## 1. `mode` 枚举——**不新增取值**

`result-run.schema.json` 的 `run.mode` 字段（`schema.json:29`：`"description": "quick / forensic"`）
**保持原样，只有两个取值**，源码验证 `TestEngine.kt:77`：`enum class Mode { QUICK, FORENSIC }`。
本次新增能力**不占用、不扩展这个字段**——而且**与 mode 无关**：`s4_throughput` 无论 QUICK 还是
FORENSIC 都只执行一次（见 §3 "`repeat_index` 恒为 0"一节的说明），不像 s1/s2/s3 那样 FORENSIC
下会有 3 条 `repeat_index=0/1/2` 的记录。

v2 UI 若要判断"这个 run 是否包含吞吐探针"，应读 `scenarios[]` 数组里是否存在
`profile_id == "s4_throughput"` 的条目，**不要**读 `run.mode`：

```typescript
// v2 判断逻辑伪代码
const throughputEntry = run.scenarios.find(s => s.profile_id === "s4_throughput");
const hasThroughputProbe = throughputEntry !== undefined;
```

---

## 2. `scenario_order` 字符串——**完全不变，`s4_throughput` 不出现在其中**

`run.scenario_order`（`schema.json:30`，格式示例 `"s1,s2,s3|s2,s3,s1"`）的生成代码
（`orderRecord.joinToString("|")`，`TestEngine.kt:554/613`）**完全不改动**。`s4_throughput`
在设计上不参与拉丁方轮转（spec §8.3.1/§8.5），因此**不会**、也**不应该**出现在这个字符串里——
这个字段的语义就是"S1-S3 三场景的实际执行顺序证据"，`s4_throughput` 混进去反而会制造一个新的
解析歧义（它到底算不算参与了轮转、要不要被 `|` 分隔）。

v2 UI 解析该字符串时**无需做任何改动**，继续按"最多三个逗号分隔项、若干个 `|` 分隔的轮次段"解析
即可。

---

## 3. `scenarios[]` 数组新增条目——`profile_id == "s4_throughput"`

**出现条件**：仅当该 run 实际执行了 `s4_throughput` 场景时出现（该场景缺 profile 时静默跳过，不
会以"空字段"形式出现——v2 应按"整个数组条目可能不存在"处理，不是"存在但字段为 null"）。**历史
run（本能力上线前采集的数据）该条目恒不存在。**

**`repeat_index` 恒为 `0`**——无论 `run.mode` 是 `quick` 还是 `forensic`，`s4_throughput` 每次
`run()` 只执行一次（spec §8.5），**不会像 s1/s2/s3 那样在 forensic 模式下出现 `repeat_index`
0/1/2 三条记录**。v2 UI 若已有"按 `repeat_index` 分组取中位数"的展示逻辑（用于 s1/s2/s3），
**不要**把 `s4_throughput` 套进同一套分组逻辑——它天然只有一条记录，直接展示即可。

**`sample_count` 恒为 `1`，且这不代表低置信**：`kpi_quality.U3.sample_count`/
`kpi_quality.D3.sample_count` 恒为 `1`——这是设计上的结构性事实（`s4_throughput.json` 每次执行只
产出一次窗口测量，不像 `s3_multimodal.json` 那样每次执行内有两次上传/下行可供取中位数），**不是**
"样本量不足 3"的信号。`low_confidence` 完全由 `*_rtt_dominance_ok`/`window_underrun`/字节数下限的
自检结果决定，与 `sample_count` 数值本身无关。v2 UI **不应该**因为看到 `sample_count: 1` 就自行
判定为低置信或加告警——只应该读 `low_confidence` 这个字段本身。

以下是**schema-完整**的示例（补齐了 `result-run.schema.json` 里 `#/definitions/scenario.kpi` 的
既有必填字段，并说明这些既有字段为什么天然是这些值——参见 spec §8.6"执行接线"；数值均为合成
占位示例，非真实采集数据）：

```json
{
  "profile_id": "s4_throughput",
  "profile_version": "0.1.0",
  "repeat_index": 0,
  "order_index": 9,
  "validity": "valid",
  "invalid_reasons": "",
  "kpi": {
    "t1_ttft_ms": null, "t1_grade": null,
    "t2_itl_p95_ms": null, "t2_grade": null, "t2_itl_p95_incl_coalesced_ms": null,
    "t3_stall_rate": null, "t3_grade": null, "t3_stall_rate_incl_resume": null,
    "t4_severe_stall_rate": null, "t4_grade": null,
    "t5_resume_p95_ms": null,
    "n1_rtt_p50_ms": null, "n1_grade": null,
    "n2_jitter_ms": null, "n2_grade": null,
    "u1_goodput_mbps": null, "u1_grade": null, "u1_goodput_excl_slow_start_mbps": null,
    "u2_tool_loop_p95_ms": null, "u2_grade": null,
    "seq_gap_count": 0,
    "seq_dup_count": 0,
    "u3_goodput_mbps": 46.1,
    "u3_grade": null,
    "u3_goodput_excl_slow_start_mbps": 52.3,
    "u3_window_target_ms": 4000,
    "u3_window_actual_ms": 4012,
    "u3_bytes_transferred": 23145728,
    "u3_rtt_ref_ms_pre": 29.1,
    "u3_rtt_ref_ms_post": 30.4,
    "u3_rtt_drift_ratio": 1.045,
    "u3_rtt_dominance_ratio": 137.8,
    "u3_rtt_dominance_ok": true,
    "d3_goodput_mbps": 812.4,
    "d3_grade": null,
    "d3_goodput_excl_slow_start_mbps": 855.0,
    "d3_window_target_ms": 4000,
    "d3_window_actual_ms": 4005,
    "d3_bytes_transferred": 406847488,
    "d3_rtt_ref_ms_pre": 29.1,
    "d3_rtt_ref_ms_post": 30.4,
    "d3_rtt_drift_ratio": 1.045,
    "d3_rtt_dominance_ratio": 141.5,
    "d3_rtt_dominance_ok": true
  },
  "kpi_quality": {
    "U3": { "sample_count": 1, "low_confidence": false },
    "D3": { "sample_count": 1, "low_confidence": false }
  },
  "clock": { "offset_start_us": 12345, "offset_end_us": 12890, "drift_ppm": 4.1, "offset_suspect": false },
  "network_snapshot": { "transport": "wifi", "capabilities": "...", "interface": "wlan0", "server_observed_addr": "10.0.0.5:41822" },
  "parse": { "parse_dur_us": null, "per_event_parse_us": null },
  "buffering": { "score": null, "attribution": null, "sample_count": 0 },
  "itl_histogram": { "buckets_version": "log2-1..8192+thresholds-v1", "edges_ms": [1,2,4,8,16], "counts": [0,0,0,0,0,0], "total": 0 }
}
```

**为什么 `seq_gap_count`/`seq_dup_count` 是 `0` 而不是 `null`（不违反 R-10）**：这两个字段在 schema
里就是不可空 integer（`schema.json:153-154`）。`s4_throughput` 没有 `token_stream` 相位，因此没有
序列号概念——"空序列上的 gap/dup 计数"精确地等于 0，这是字面上的真值，不是"测不出所以拿 0 顶替"的
哨兵值，两者语义不同。`itl_histogram.total=0` 同理。这些值不需要任何特殊分支产出——复用与
s1/s2/s3 完全相同的计算流水线（spec §8.6）会让它们自动落到这些值。

**逐字段类型与含义**（权威定义见 spec §8.4.2，此处为 v2 消费视角的精简重述）：

| 字段路径 | 类型 | 含义 | UI 处理要点 |
|---|---|---|---|
| `kpi.u3_goodput_mbps` | `number \| null` | 上行窗口内平均 goodput（含慢启动，主口径） | 主展示数值；`null` 时按"未测出"渲染（R-10：不可测≠0）。**文案避免"上行网速"，建议"上行连接速度"** |
| `kpi.u3_grade` | `string \| null` | 分级 | **诊断期恒为 `null`**（未接入打分）；不要因为 `null` 就渲染"最差档"，应渲染"未评级/诊断中" |
| `kpi.u3_goodput_excl_slow_start_mbps` | `number \| null` | 剔慢启动稳态口径 | 建议作为主数值旁的次要/展开信息 |
| `kpi.u3_window_target_ms` / `u3_window_actual_ms` | `integer` / `number \| null` | 目标/实测窗口时长 | 若 `actual < target` 且 `bytes_transferred == 请求 ceiling`，即触发了 `window_underrun`——建议 UI 展示层附加提示"链路速率超出本次探测量程" |
| `kpi.u3_bytes_transferred` | `integer \| null` | 实际传输字节数 | 可换算展示为 MB |
| `kpi.u3_rtt_ref_ms_pre` | `number \| null` | 传输前（phase 1）测得的 RTT 基准 | 建议放入"详情/调试"视图 |
| `kpi.u3_rtt_ref_ms_post` | `number \| null` | 传输后（phase 4）测得的 RTT | 建议放入"详情/调试"视图，与 pre 值并列展示 |
| `kpi.u3_rtt_drift_ratio` | `number \| null` | `post/pre` 比值，偏离 1 越远说明传输前后网络状态变化越大 | **偏离 1 超过约 20-30%（对齐 D-365 实测的 26-34% 漂移量级）时建议附加提示"测量期间网络状态发生变化，结果可能受影响"**；这是一个粗粒度信号，不代表窗口传输*过程中*一定发生了拥塞，也不代表没发生（spec §8.2"已知局限"） |
| `kpi.u3_rtt_dominance_ratio` | `number \| null` | 窗口时长/传输前 RTT 倍数（自检判据本身） | **建议在详情/调试视图暴露**，延续仓库"判据可核对而非黑箱"风格 |
| `kpi.u3_rtt_dominance_ok` | `boolean` | 自检是否通过 | `false` 时数值仍展示，但需配合 `kpi_quality.U3.low_confidence` 一并显示告警标记 |
| `d3_*` 十个字段 | 同构镜像（下行） | 同上 | 同上；命名为 `D3` 而非 `D2`，因为 `D2` 在本仓库当前是网格采集决策旋钮的固定编号（"是否双运营商"），与本组 KPI 字段无关但共享同一裸 token 命名空间，为避免"同名不同义"沿用了下一个未占用的数字 |
| `kpi_quality.U3.sample_count` | `integer \| null` | 恒为 `1`（见上文说明，不代表低置信） | 不建议单独展示这个数字（容易被误读为"只测了一次不可靠"），如需展示应配文案说明这是设计如此 |
| `kpi_quality.U3.low_confidence` | `boolean` | 该 KPI 是否触发 §8.3.3 自检失败 | **`true` 时 UI 必须显式呈现告警**（如"⚠ 本次测量置信度较低"） |

**`validity`/`invalid_reasons`**：与既有 `s1_chat` 等场景同构，三态 `valid`/`valid_low_confidence`/
`invalid`。若该场景本身因网络错误整体失败，`validity` 应为 `invalid`，此时 `kpi.*` 字段应按既有
gate 语义全部为 `null`。

---

## 4. 不会出现/不会扩展的字段——诊断期明确排除

- **`run.profile_versions`（顶层聚合字段）不会扩展**：该字段（`schema.json:16`，"本 run 各场景
  profile 版本串"）由 `ProfileParser.versionString()`（`ProfileModels.kt:102-104`）生成，只遍历
  `REQUIRED_IDS` 三个场景，**本方案不改这个函数**——`s4_throughput` 不参与它的"横比分组"语义
  （spec §8.5）。v2 如果需要 `s4_throughput` 自己的版本号，**请读 `scenarios[].profile_version`**
  （该场景条目自带的场景级字段，即 §3 示例里的 `"0.1.0"`），不要尝试从 `run.profile_versions` 里
  解析出第四段——它不会出现在那里。
- `run.aqs_throughput`（新 additive facet）——只有批④（打分接入，门槛批次）被批准并落地后才可能
  出现。**v2 不应假设它存在，也不应把它的缺席渲染成 0 分或任何负面判词**。
- `scenarios[].kpi.u3_grade` / `d3_grade` 的**非 null 取值**——诊断期恒为 `null`。若某天看到非
  null 取值，说明批④已落地。
- `d1_goodput_mbps` 等字段的**历史缺席**——批①上线前采集的 `s3_multimodal` 场景记录里没有这些
  字段，v2 若已有相关展示逻辑，需按"可选字段，历史数据缺席"处理。
- `d1_goodput_excl_slow_start_mbps`——**本方案不会产出这个字段**（实测核实 D1 没有这个口径的既有
  实现）。

---

## 5. `aqs_version` 分支处理（仅在批④发生后才需要，本节为前瞻性说明）

若后续批④落地且选择"切换 `AqsInputMapper` 映射"路径（而非新增独立 facet），
`run.aqs_token.aqs_version` 会出现从 `"aqs-token-v0.1"` 升级到 `"aqs-token-v0.2"` 的取值：

| `aqs_token.aqs_version` | U1/D1 数据来源 |
|---|---|
| `aqs-token-v0.1`（现状及批④前） | `S3`（固定字节数负载，单流应用层 goodput，见 §0） |
| `aqs-token-v0.2`（若批④选择切换映射） | `S4`（自适应时长窗口，同样是单流应用层 goodput——**切换映射不会改变"单流"这个方法学局限**，只是改变了负载/时长模型，见 spec §8.4.4 对该路径的额外方法学评审要求） |

若批④选择"新增独立 `run.aqs_throughput` facet"路径而非切换映射，则本节不适用，
`aqs_token.aqs_version` 保持 `aqs-token-v0.1` 不变。**具体走哪条路径由批④裁定决定，v2 在批④正式
立项前无需为此预留代码分支**。

---

## 6. 与现有 `basic_network`（SpeedTest 式仪表）的关系说明——避免用户困惑

`s4_throughput`（`token_experience` 内的诊断场景，一次性"跑分"式测量，与 `mode` 无关只执行一次）
与 `basic_network` 的 `SpeedRunner` 实时仪表（`app/probe/.../engine/SpeedRunner.kt`，6 秒滑窗实时
波动展示，**零持久化、不进 wire 合同、v2 目前也读不到它的历史记录**）是**两种并存但完全独立的
测速语义**：

| | `basic_network`（SpeedRunner） | `s4_throughput`（本次新增） |
|---|---|---|
| 触发方式 | 独立 tab，用户主动点击 | 挂在 `token_experience` run 内自动执行，每次 run 恰好一次 |
| 展示形态 | 实时波动仪表 | 事后回看的一次性数值（wire body 字段） |
| 持久化 | 无 | 有（Room + wire 上报） |
| v2 是否可读 | 否 | 是（本文档定义的字段） |
| 是否进入 AQS | 否 | 诊断期否；批④视裁定 |
| 测量口径 | 单流，固定 6s 窗口 | 单流，可配置窗口（默认 4s）+ 双向 RTT 主导度自检 |

两者都是**单流**测量，都不代表链路容量——这一点在 UI 文案阶段就应统一处理（如"实时网速测试"vs
"本次会话吞吐诊断"），避免用户把两个不同方法学产出的数字直接对比产生"为什么不一样"的困惑或不信任。
