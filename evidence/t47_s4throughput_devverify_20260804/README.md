# T47 批③ s4_throughput 真机首次开发验证（DW-20260804-02）

**性质**：开发验证，非外场战役（PO 外场暂停令不涉）。**不进任何战役语料**。
**设备**：P40 Pro（`8MY0221126002537`），quick 模式 autorun，1 run（含 s1/s2/s3/s4_throughput 共 4 场景）。
**网络路径**：本机局域网 WiFi 与设备实测不互通（本机连的是访客网 `Huawei-Guest 6`，疑似 AP
隔离），改用 `adb reverse tcp:8443 tcp:8443`（USB 隧道）连接本机临时起的 Go server
（`server/ -addr :8443 -profiles ../profiles`，明文 HTTP，dev-only，未碰 E-01）。
**已知局限**：USB 隧道路径远快于真实蜂窝/WiFi RF 条件，本次 RTT 主导度比值（83.75×/336.59×）
远高于 spec §8.7-2 待裁定的 `[8,15]` 边界区间——本次验证证明代码链路端到端正确，**不构成**
边界区间样本分布的统计依据；后者需要更多轮次、更真实网络条件（或 weaknet 模拟）下的采集。

## 结果文件

- `s4_throughput_run1.jsonl`：完整 wire body（1 run，4 scenarios），`schema` 校验通过
  （`python scripts/validate_results.py` → `contract OK`）。
- `DW-20260804-02_logcat.txt`：全程 `AnebProbe:I` logcat 落盘。

## 关键观测（s4_throughput 场景，`scenarios[3]`）

| 字段 | 上行（U3） | 下行（D3） |
|---|---|---|
| `goodput_mbps`（含慢启动） | 403.30 | 288.53 |
| `goodput_excl_slow_start_mbps` | `null`（窗口仅 998ms，估不出爬坡） | 289.93（成功估出） |
| `window_target_ms` | 4000 | 4000 |
| `window_actual_ms` | 998.4 | 4012.4 |
| `bytes_transferred` | 50,331,648（=48MB ceiling，写满） | 144,715,473（≈138MB，未写满） |
| `window_underrun` | **true**（ceiling 先到，窗口未到点） | **false**（窗口到点，ceiling 未到） |
| `rtt_ref_ms_pre` / `_post` | 11.921 / 11.037（两方向共享同一对样本） | 同左 |
| `rtt_drift_ratio` | 0.926 | 0.926 |
| `rtt_dominance_ratio` | 83.75 | 336.59 |
| `rtt_dominance_ok` | true | true |
| `grade` | `null`（诊断期未接入打分） | `null` |

`kpi_quality.U3`/`D3`/`_excl_slow_start` 四项均 `sample_count=1, low_confidence=false`
（spec §8.4.3 设计：sample_count 恒为 1，不套用 U1/D1 的 n<3 判据）。

## 验证结论（对照 spec §8.4-§8.6 设计意图逐条核对）

1. **`window_underrun` 两种情形均真实观测到**——上行 ceiling 先到（48MB/998ms）、下行窗口先到
   （4s/138MB）——spec §8.3.3"已知边界情形"一节描述的场景在真实设备上确认存在且被正确标记。
2. **`TransferWindowAnalysis` 行为正确**：下行窗口（4s，样本更多）成功估出慢启动段
   （289.93 ≠ 288.53），上行窗口（998ms，样本少）诚实返回 `null`——不是估不准，是"测不出就
   不猜"的既定语义（同 U1 既有纪律）。
3. **`RttDominanceGuard` 在真实数据上工作正常**：两方向 ratio 远超 `RTT_DOMINANCE_MIN=10`，
   `dominance_ok=true`；本次未落入 `[8,15]` 边界区间（网络路径过快所致，见"已知局限"）。
4. **批①的 `noData` 回归修复在真机上验证有效**：s4_throughput 场景 `validity=valid`
   （非此前 bug 会产生的 `INVALID`）。
5. **诊断期零侵入 AQS 确认**：run 级 `AQS subs` 列表（T1/T2/T3/U1/U2/N1/N2）不含 U3/D3；
   `run.aqs_throughput` 字段未出现（批④前不应出现）。
6. **`scenario_order` 不受影响**：值为 `"s1_chat,s2_coding_agent,s3_multimodal"`，
   `s4_throughput` 未出现在其中（spec §8.5 设计确认）。
7. **`repeat_index`/`order_index` 正确**：`repeat_index=0`（结构性恒为 0）、
   `order_index=3`（延续 s1/s2/s3 的 0/1/2 计数器）。
8. **Room v18→v20 迁移在真机上正确执行**：既有安装（`-r` 保留数据）升级后
   `DB_WRITE scenarios=4` 成功落库，未见 Migration 异常。
9. **wire body schema 校验通过**：`validate_results.py` 对本次真实产出的 1 条记录判
   `contract OK`（含全部 22 个新字段的结构 + R-10 交叉字段不变量）。

## 未决事项（留给批④/后续裁定）

- `[8,15]` 边界区间样本分布：需要真实较慢网络条件（真实蜂窝弱网，或 `weaknet contend:N`
  背景流量竞争调试开关模拟拥塞）下的多轮采集，本次 USB 隧道路径过快无法提供。
- n≥15 独立 run 的完整分布：本次仅 1 run，仅证明代码路径正确，不构成统计样本。
