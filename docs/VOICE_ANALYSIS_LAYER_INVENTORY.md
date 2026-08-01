# 语音数据在分析层的读者盘点（T15 ② · 盘点先行）

> **一句话**：语音 KPI 一个字节都没有进过导出契约，所以 `scripts/` 战役层**结构上就看不见它**。
> 18 个字段里 **17 个零读者**，唯一那个非零的读的还是**规格常量而不是数据列**。
>
> **大脑的假设（近零读者）判定 CONFIRMED**——但「零」的**原因**比「零」本身重要：
> 不是分析层忘了写读者，是**上游根本没有产出物可读**。写读者之前要先有数据出得来。

*2026-08-02 · v3 执行会话 · 承 T15 ②*

**方法学范本**：T9（[`RADIO_CONTEXT_WIRING_SPEC.md`](RADIO_CONTEXT_WIRING_SPEC.md)）与
T10（[`PROFILE4_VOICE_LOOPBACK_SPEC.md`](PROFILE4_VOICE_LOOPBACK_SPEC.md) §0）——**盘点先行**，
先数清已有的，再写缺的。本文沿用 T9 那张「事实 / 证据」表与「逐字段点名读者」的形状。

---

## §0 结论先行

| 问 | 答 | 判据 |
|---|---|---|
| `VoiceResultEntity` 到底几个字段？ | **18 个**（派单说的 18 对得上），但其中**只有 14 个是 KPI 度量**，另 4 个是元数据（`id` / `tsEpochMs` / `caliber` / `lowConfidence`） | `Entities.kt:416-452`，字段表从源码解析而非手抄 |
| 14 个 KPI 字段在 `scripts/` 有几个读者？ | **全部 0** | 见 §2 逐字段表 |
| 4 个元数据字段呢？ | `id` / `tsEpochMs` / `lowConfidence` **均 0**；`caliber` **1**，且读的是**规格常量不是数据列** | 见 §2 与 §3 同名词辨析 |
| D-38 的真机 79.8 分在哪？ | **哪儿都没有落盘**——它只活在散文里（5 份文档），当时是从屏幕上读下来记进决策日志的 | §4 |
| 近零读者假设 | **CONFIRMED** | — |
| 但根因是什么？ | **不是分析层缺读者，是导出契约里没有语音**（结构性失明，T9 的同一形状） | §1 |

---

## §1 根因：语音数据**结构上到不了**分析层

分析层唯一的输入是 run 契约导出的 jsonl 语料。语音不在其中——四条各自独立的实测事实：

| 事实 | 证据 |
|---|---|
| 设备侧**有**采集与落库 | `Entities.kt:416` `@Entity(tableName = "voice_result")`，18 列齐备 |
| App 内部**有**消费 | `VoiceTestScreen.kt`（出分与口径分流）、`HistoryScreen.kt`（历史行只显口到耳值）、`MainActivity.kt`、`Daos.kt`（`insert` / `recent`） |
| 导出契约里**没有** | `spec/schemas/result-run.schema.json` 的 `kpi` 必填项只有 `t1_ttft_ms` / `t2_itl_p95_ms` / `t3_stall_rate` / `t4_severe_stall_rate` / `n1_rtt_p50_ms` / `n2_jitter_ms` / `u1_goodput_mbps` / `u2_tool_loop_p95_ms` / `seq_gap_count` / `seq_dup_count`——**无一语音字段**，全文 `voice` 零命中 |
| 上报侧**没有** | `engine/ResultReporter.kt` 全文件 `voice` **零命中**（大小写不敏感计数 = 0）；`voice_result` 表的消费方全在 `ui/` 与 `data/`，**没有任何导出/上传方** |
| 归档语料里**没有** | `evidence/` 全部 `*.jsonl` 扫 `mouth_ear` / `ttfb_p50` / `barge_stop` / `turn_switch` / `turns_ok` / `voice` —— **零文件命中** |

**这正是 T9 当年那句话的语音版**：设备侧有采集、App 内部有消费、导出契约里一个字段都没有，
所以战役分析层永远看不到它。区别在于 T9 那次**消费方已经写好并跑通了**（`radio_rollup.py` 先落地、
就等字段），而语音这次**两侧都还没有**——所以本文不是接线规格，只是盘点。

---

## §2 逐字段读者表（`scripts/` 战役/分析层，55 个 `.py`）

判定口径：**读者 = 该字段的值真的被取用**（读 key、比对、聚合、渲染）。
同名不同义的命中**不计入**，但**逐条列出**（§3），因为「有命中」与「有读者」是两件事。

### 2.1 元数据 4 列

| # | 字段 | 读者数 | 谁读它 / 或零读者 |
|---|---|---|---|
| 1 | `id` | **0** | 裸词 `id` 在 `scripts/` 有 35 处命中，**全部是泛用局部变量**（`campaign_common.py` / `campaign_report.py` 等），与 `voice_result.id` 无关 |
| 2 | `tsEpochMs` | **0** | 唯一命中 `pull_device_corpus.py:117`，是**找时间列的候选名清单**（`"ts_epoch_ms","tsepochms","created_at"`），它找的是 `test_run` 的开跑时刻、抽的是 `report_body`，**从不碰 `voice_result` 表** |
| 3 | `caliber` | **1（且只读规格侧）** | `validate_voice_plan.py:163` `_eq(errs, "v2.caliber", kconst["SIM_CALIBER"], v2.get("caliber"))`——比的是 `voice_realtime_plan.json` 与 `VoiceRunner.kt` **常量**是否一致（D-391 的对拍门）。**它读的是口径的词汇表，不是任何一行落库数据**。另 8 处命中是英文行文里的 "the caliber"（§3） |
| 4 | `lowConfidence` | **0** | 141 处 `low_confidence` 命中**全部是战役层自己的格级低置信**（`n < min_samples`，D-313），与语音的「上行入队背压」**完全不同义**（§3） |

### 2.2 v1/v2 共用 KPI 7 列

| # | 字段 | 读者数 | 谁读它 / 或零读者 |
|---|---|---|---|
| 5 | `rttMs` | **0** | **零读者**。`rtt` 词干在 `scripts/` 有 200 处，全属网络 KPI `n1_rtt_p50_ms` 域，非语音列 |
| 6 | `jitterMs` | **0** | **零读者**。`jitter` 词干 98 处，全属 `n2_jitter_ms` 与场景抖动域 |
| 7 | `upFrameJitterMs` | **0** | **零读者**（整词与词干 `up_frame_jitter` 双双 0 命中） |
| 8 | `downFrameJitterMs` | **0** | **零读者**（词干 `down_frame_jitter` 0 命中） |
| 9 | `mouthEarBudgetMs` | **0** | **零读者**（词干 `mouth_ear_budget` 0 命中） |
| 10 | `framesSent` | **0** | **零读者**（词干 `frames_sent` 0 命中） |
| 11 | `framesRecv` | **0** | **零读者**（词干 `frames_recv` 0 命中） |

### 2.3 v2 server-sim 尾部 KPI 7 列（D-38 新增）

| # | 字段 | 读者数 | 谁读它 / 或零读者 |
|---|---|---|---|
| 12 | `ttfbP50Ms` | **0** | **零读者**（词干 `ttfb_p50` 0 命中） |
| 13 | `ttfbP95Ms` | **0** | **零读者**（词干 `ttfb_p95` 0 命中） |
| 14 | `downNetJitterMs` | **0** | **零读者**（词干 `down_net_jitter` 0 命中） |
| 15 | `mouthEarProxyMs` | **0** | **零读者**（词干 `mouth_ear_proxy` 0 命中） |
| 16 | `turnSwitchP50Ms` | **0** | **零读者**（词干 `turn_switch_p50` 0 命中） |
| 17 | `bargeStopMaxMs` | **0** | **零读者**。`barge` 在 `scripts/` 只出现在 `validate_voice_plan.py`（`barge_in_after_frames`），那是**执行计划的参数**，不是这一列的**测量结果** |
| 18 | `turnsOk` | **0** | **零读者**（词干 `turns_ok` 0 命中） |

**合计：18 个字段 / 17 个零读者 / 1 个只读规格常量 / 0 个读数据列。**

---

## §3 我如何防住两个已知的量法陷阱

### 3.1 拼接出来的字段名（T6/T8 教训，D-340）

只做整词 grep 会漏掉**运行时拼出来**的名字（`kpi_key.split("_")[0] + "_grade"` 是仓内实例）。
处置**三层**，不是一层：

1. **字段清单从源码解析**，不手抄——正则从 `Entities.kt` 的 `data class VoiceResultEntity(...)`
   块里取 `val <name>:`，避免手写清单漏项（D-275/D-329）。
2. **整词 + 词干双扫**：每个字段除 camelCase/snake_case 两种拼法外，再剥掉
   `_ms` / `_p50` / `_p95` 尾缀取**词干**做子串扫描——一个被拼出来的
   `"ttfb" + "_p50_ms"` 会在词干 `ttfb_p50` 或 `ttfb` 上现形。
3. **把拼接点本身枚举出来**：扫 `scripts/` 全部 f-string 插值 / `+ "_后缀"` / `"前缀_" +` /
   `.format(` / `%(`，共 **1055 处**；再筛出**行内出现任一语音词干**的，得 **71 处**，逐条看过。
   结论：71 处全部由 `turn`(29) / `down`(14) / `stop`(9) / `confidence`(7) / `jitter`(7) /
   `sent`(6) / `turns`(3) / `caliber`(2) / `barge`(1) 这些**通用词**触发，
   **没有任何一处能拼出语音字段名**；`ttfb` 触发数为 **0**。

> **诚实的边界**：这条只证明「今天的 `scripts/` 拼不出这些名字」，
> 不证明「以后也拼不出」。它是一次测量，不是一道守卫。

### 3.2 同名不同义（比零读者更容易骗人）

三个词在本仓有**两套互不相干的含义**，naive grep 会把它们算成读者：

| 词 | 语音域含义 | 战役层含义（命中的其实是这个） | 命中数 |
|---|---|---|---|
| `low_confidence` | 上行入队背压出现过（`VoiceRunner` 逐样本） | 该格样本数 `n < min_samples`（D-313 格级置信） | 141 |
| `caliber` | `SIM_CALIBER` 口径标注（v1 null / v2 原文） | ①英文行文 "the caliber"（判词的口径，8 处）②`attribution.py` 的 `_screen_caliber` 筛查口径 | 8 |
| `rtt` / `jitter` | 语音 RTT P50 / 抖动 | `n1_rtt_p50_ms` / `n2_jitter_ms` 网络 KPI | 298 |

**若不做这一步辨析，本盘点会把 `lowConfidence` 报成「141 个读者」——方向完全相反。**

---

## §4 D-38 的真机 79.8 分：它在哪

| 事实 | 证据 |
|---|---|
| **79.8 从未落盘** | `VoiceResultEntity` **不存分数、不存评分版本号**（18 列里没有），这是 D-42 那轮定下的诚实设计；`VOICE_STALL_KPI_PROPOSAL.md` §4 已逐处核实过 |
| 出分只在**内存里**发生 | `scoreVoice`/`scoreVoiceSim` **只被 UI 与单测调用**，输入是实时 `VoiceRunner.Sample` 而非库行（`VoiceTestScreen.kt:309/317/328`）；历史页**刻意不重算分** |
| 它今天**只活在散文里** | `DECISION_LOG.md`(D-38)、`MEASUREMENT_CAMPAIGN_2026-07-17.md:30/49`、`PROFILE4_VOICE_LOOPBACK_SPEC.md:19/475/716`、`VOICE_STALL_KPI_PROPOSAL.md` §4、`BRAIN_TASKBOARD.md`——**5 份文档，零份数据** |
| 分析层读者数 | **0**（没有任何产物可读） |

> ⚠ **一条量法警告，替下一个人省半小时**：`grep -rn "79\.8"` 全仓有 **150+ 命中**，
> 其中 **140+ 在 `evidence/**/*.jsonl` 里**，看上去像「语音分进语料了」。
> 逐条打开是 `"t2_itl_p95_ms": 79.8` ——**扩展轮合成语料里一个巧合的数值**，与语音无关。
> 判据不该是数字长得像，而该是**键名**：全部语料扫语音键名，**零命中**（§1 末行）。

---

## §5 这份盘点**没做到**的（诚实缺口）

- 只数了 `scripts/`（派单指定的战役/分析层）。**`app/` 侧读者未逐字段数**——
  §1 只确认了「有 UI 消费方、无导出方」，没有做 18×消费方的完整矩阵。
- `SyntheticResultEntity`（同文件 `Entities.kt:469`，恢复子测/弱网整形）**未纳入本次盘点**，
  它可能有同样的形状；派单没点名它，我不擅自扩范围，但**登记在此**。
- 本文是**一次测量，不是一道守卫**：今天字段加一列、或分析层哪天拼出一个语音名字，
  没有任何东西会告诉你本文过期了。应有形态见 §3.1 末的边界声明。
