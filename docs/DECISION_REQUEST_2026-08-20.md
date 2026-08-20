# ANEB 决策请求 — 当前状态一页清（2026-08-20）

> 本页只列**此刻未闭环**的事项。上一版 [`DECISION_REQUEST_2026-08-02.md`](DECISION_REQUEST_2026-08-02.md)
> 仍是「问了什么、答了什么」的归档，按惯例不就地改。
>
> **来源**：本页各项来自 v4 在 PO 48h 自主令下完成的 T63–T73 十一单（D-498…D-532），
> 以及 T67/D-514 的八条 `high` 审计发现。
>
> **纪律**：每条都带出处（决策号 / 文件行号 / 实测命令）；查不到的写「未能核实」，不圆场（D-311）。
> **本页每条断言都在落笔前当场核实过一遍**——其中一条因此被删（见 §5 回执）。

**状态词**：🔴 待 PO 裁 ｜ 🟠 待大脑裁 ｜ 🟡 已批待执行 ｜ ✅ 已闭环 ｜ ❓ 未能核实

---

## 1. 🟠 T63 三常量拍板（`RttDominanceGuard`）

**现状核实**：`RttDominanceGuard.kt:9` 逐字写着「三个常量均为大脑 D-469 裁定 **PROVISIONAL** 记入的建议默认值」，
截至本页仍是 PROVISIONAL。判据全文见 [`T63_RTT_DOMINANCE_CONSTANTS_SENSITIVITY_20260815.md`](T63_RTT_DOMINANCE_CONSTANTS_SENSITIVITY_20260815.md)。

| # | 常量 | 现值 | v4 建议 | 理由 |
|---|---|---|---|---|
| ① | `ABS_FLOOR_MS` | `300.0` | **照批** | 防 RTT 极小时「10×RTT」退化到计时器/线程调度抖动量级；无反证 |
| ② | `MIN_BYTES_FLOOR` | `100KB` | **照批** | 字节数过少时 goodput 数字本身不成立；无反证 |
| ③ | `RTT_DOMINANCE_MIN` | `10.0` | **建议 10 → 15** | D-363 实测历史最高是 s3 的 **9.8×**，10 只留了 0.2× 边际 |

**③ 的代价要说清**：`RTT_DOMINANCE_MIN` 与窗口长度是一个除法关系——
**临界 RTT = 窗口长度 ÷ `RTT_DOMINANCE_MIN`**。4000ms 窗口下，10 对应临界 RTT 400ms，15 对应 **267ms**。
即调到 15 会让「RTT 高于 267ms 的环境」整片落进低置信。这在弱网点位是**常见而非罕见**，
故这一条**不建议 v4 自裁**，请明示。

**①②③ 可以分开裁**——①② 无争议，③ 需要一个取向判断（宁可少报还是宁可多报）。

---

## 2. 🟠 `window_underrun` 是否进 wire body

**现状核实**：`grep -c window_underrun spec/schemas/result-run.schema.json` = **0**，即**至今不是契约字段**。
它目前只活在设备内存里（`KpiCalculator` 的 `AdaptiveWindowResult.windowUnderrun`，
经「`lowConf = !rttDominanceOk || windowUnderrun`」折进 `low_confidence`）。

**后果**：产物里只看得见 `low_confidence=true`，**看不见它为什么真**。
直接影响一条已经写下的验收标准——T64 spec §8.7 那条**目前从产物算不出来**；
`evidence/t47_s4throughput_devverify_20260804/README.md` 也已因此追加过更正说明
（那里的 U3 只能读作 `low_confidence=true`，不能读作 `window_underrun`）。

**两个选项**：

- **A｜进契约**：加 `window_underrun`（bool，非必填，R-10 语义下缺失 ≠ false）。
  **代价 = 一次 schema 变更**，按本仓纪律须先 spec 后代码。**收益 = §8.7 的验收标准变成可计算的**。
- **B｜不进**：接受「低置信不说明原因」，并**同步把 §8.7 那条验收标准改掉**——
  不能留一条算不出来的标准挂在那里。

**v4 倾向 A**，但这是契约面，按纪律不自裁。
⚠ **与 §4 的 `s4_throughput` 静默跳过强相关，建议一并裁**。

---

## 3. 🟠 `status` 目前是「只写不读」——两侧都有印错的风险（本轮新硬化）

这一条本来只是「正文承诺与机制不符」，本页落笔前的实测把它变成了**可复现的具体输入**。

**核实链（每步都是当场跑的）**：

1. **报告正文印给读者的是无条件括注**：`campaign_report.py:1420` 逐字——
   「存在非 `completed` run……（run 级 AQS 为 null 不进中位）；**只显性化，不静默剔除**」。
2. **而源码自己的注释是有保留的**：同文件 `:1418` 写的是 *"an aborted run's AQS is **typically** null"*。
   —— **印出去的是无条件承诺，代码里承认的是 typically。**
3. **全语料实测**（3509 条记录，2 条非 completed）：两条 aborted 的 AQS **确实**是 null，
   **但原因是 `not_computable_reason: KPI_MISSING:T1,T2,T3,U1,U2`，不是因为它 aborted**。
   即那句承诺今天成立**纯属巧合，不是机制**。
4. **没有任何机制在兜底**：`run_status_head()` 是全仓唯一的 status 读者，
   而它只用于**分桶计数**——中位数路径里**没有任何 status 判据**。

**于是有一个反例输入，它今天就能构造出来**：
一个跑完 `s1/s2/s3` 后**在 `s4_throughput` 阶段中止**的 run。
理由是 AQS 的 `input_mapping` 实测为
「N1,N2←S1；T1..T5←S2；U1←S3；U2←S2；D1←S3；S1←all\_scenarios.round\_success\_ratio」
—— **`s4` 根本不在映射里**，而 `s4_throughput` 恰恰是主循环之后才追加的诊断相位。
这样的 run 会拿到一个**非 null、且 `low_confidence=false`** 的 AQS **进入中位数**，
而横幅正在告诉读者它不会。

**同一缺陷的另一面在设备侧**：`ui/ReportMapper.kt` 读了
`run.aqsScore` / `run.aqsLowConfidence` / `runId` / `startedAtEpochMs` / `transport`，
**`grep -c status` = 0** —— 设备 UI 会照常给一个中止的 run 显示分数，连提示都没有。

**共同形状**：**`status` 被写出来、进了契约、也进了真实语料，却没有任何消费方拿它当判据。**
（这正是本仓 D-340 记过的那个形状：字段有生产端、有契约，分析层零读者。）

**三个选项**：

- **A｜status 成为真判据**：非 `completed` 的 run，其 run 级 AQS 不进中位（**让承诺变成真的**）。
  代价 = 可能剔掉一些其实测全了的 run，且需想清是否按 `:reason` 细分。
- **B｜改措辞**：把括注改成如实的「AQS 为 null 时不进中位（与 status 无关）」。
  代价最小，但读者失去一层保护。
- **C｜A+B**：先改措辞止血，再按 A 落判据。

**v4 倾向 C**（先让印出去的话是真的，再补机制）。
**但 A 会改变已发布的数字**——凡改变已发布数字的判据变更，按本仓纪律不自裁。

设备侧那半（`ReportMapper` 不读 status）**属跨 lane**，需派单，v4 不越界动。

---

## 4. 🟠 审计剩余 3 条 `high`（来源 T67/D-514）

| 条目 | 内容 | v4 建议 |
|---|---|---|
| `s4_throughput` 静默跳过 | 相位缺失时无任何标注 | **与 §2 一并裁**（同一根因） |
| `THERMAL` / `SUB_SWITCH` 零读者 | 已采集、零消费方 | 先等裁 |
| 测前省电态无判据 | 无前置检查项 | 先等裁 |

**为什么建议先停**：这三条都是**新增消费方 / 新增判据**，属**扩大范围**，
与已完成的五条（修复既有偏离）性质不同。已完成部分见 D-514…D-532。

---

## 5. ✅ 回执：本页落笔前删掉的一条

**「T64 墙钟方案待裁」——已删，因为它是过期信息。**
核实结果：大脑**已裁定采 A 案**（D-506），客户端件已由他方落地（D-519，
`spec/schemas/result-run.schema.json:190` 的 `wall_skew_ms` + `ResultReporter.kt:188`），
阈值也已定为 60s，且 D-506 明写**分析层门归 v3（排 M7 回核后）**。

**分析层现状如实记一笔**：`grep -rn wall_skew scripts/` **零命中**，
即该字段目前在分析层仍无消费方——但这**已经有属主（v3），不是待裁项**，v4 不越界接手。

> 这条留在本页不是凑数：它是「拿过期状态去请人拍板」的一次拦截，
> 也是本仓反复记过的「当前态混历史」那个形状（D-489 那次的犯者是大脑，这次差点是 v4）。

---

## 6. 交付现状（供裁时参照）

- **Python 全量 674 passed / Kotlin 全量 815/815**，零失败。
- v4 本轮改动**已全部提交**；工作区剩余未提交项均为他方产物。
- 本轮共 11 单（T63→T73），其中审计驱动 8 单，
  修掉 **5 条 `high` + 3 条批判环节结构性缺口**（G-1/G-2/G-5）。
