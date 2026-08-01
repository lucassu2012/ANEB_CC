# 扩展轮形状进生成器 · 对拍 + 全链路复跑证据包（T12 ② ④）

> 2026-08-01 · v3 执行会话 · 承 `docs/M3_EXPANSION_ROUND_GUARD_DIFF.md` **C-4**
> 决策 **D-389**。上游证据包 = `evidence/m3_expansion_rehearsal_20260801/`（T6，
> 由一次性整形器所产；该整形器已于本轮降格为历史证据，**未删**）。

---

## ⛔ 隔离声明（D-270）

**本目录下每一个数字都是虚构的，全部产物一律不得外发、不得作为任何结论依据。**

隔离是**可核验的**，不是声明：

| 隔离手段 | 怎么核 |
|---|---|
| 双重合成标记 | 每条记录带 `synthetic` 块**且** `campaign_id` 以 `SYNTH-` 开头。`synth_campaign.assert_double_marked()` 在**写盘之前**逐条断言，任一条不成立即 `ValueError`、**一个文件都不产出**（守卫：`test_expansion_records_are_double_marked_before_anything_is_written`，它连「失败后目录里是不是真的空的」都查）。 |
| 前门自己拦得住 | `publish_check` 对三份语料**全部**报 `⛔ FAIL 合成语料 N/N 条`、exit 1。**这条 FAIL 是彩排的合格线，不是缺陷。** |
| 与真实语料零接触 | 全程未读写任何真实语料目录；`git status` 对 `m2_pilot_20260731` / `afternoonradio_20260801` / `busyradio_20260801` / `m2_idleprobe_20260731` 全部为空。 |
| 战役隔离 | 单战役 `SYNTH-EXP`；全仓 `grep -rl SYNTH-EXP` 只命中 `docs/` 与三个 `evidence/m3_*` 目录，**没有一处落在真实语料池里**。 |

---

## 1. 可复跑命令

```bash
# ── 0. 造语料（工作目录 = scripts/；D 为本证据目录的相对路径）
cd scripts
D=../evidence/m3_expansion_gen_20260801
python synth_campaign.py -o $D/expansion --expansion --seed 20260801

# ── 1..9 与 T6 那份逐条对应（只有第 0 步换了工具）
python validate_results.py  $D/expansion_counted.jsonl
python campaign_report.py   $D/expansion_counted.jsonl \
    --md $D/expansion_counted_report.md --html $D/expansion_counted_report.html \
    --csv $D/exp
python publish_check.py     $D/expansion_counted.jsonl
python publish_check.py     $D/expansion_counted_forensic.jsonl
python publish_check.py     $D/expansion_raw.jsonl
python stability.py $D/expansion_counted_quick.jsonl --kpi t1_ttft_ms    --plan
python stability.py $D/expansion_counted_quick.jsonl --kpi n1_rtt_p50_ms --plan
P=SYNTH-P01,SYNTH-P02,SYNTH-P03,SYNTH-P04,SYNTH-P05,SYNTH-P06,SYNTH-P07,SYNTH-P08
python coverage_matrix.py $D/expansion_counted.jsonl       --points $P --carriers cmcc,cucc --time-bands busy,idle
python coverage_matrix.py $D/expansion_counted_quick.jsonl --points $P --carriers cmcc,cucc --time-bands busy,idle
```

各步 stdout 已归档为 `00_shape.txt` … `09_coverage_matrix_quick_only.md`；
`10_crosscheck_vs_one_off_shaper.txt` 是 ② 的对拍流水。
四份 `.jsonl` 不入库（`.gitignore` 列明），指纹见 `CORPUS_SHA256.txt`。

> ⚠ **T6 那份用 `--forensic-runs` 等价于 4**（提案原「建议 4 轮」）；
> **本轮用生成器默认 5**（**D-379** 已把它定为 5 并作废「4 轮」）。故本目录与
> T6 目录的取证侧数字**本来就不该相同**——要做逐字节对拍，见下方 ② 那一节，
> 它显式把参数钉回 4。

---

## 2. ② 金标准对拍结论：**等价，且唯一差异已定位到字段**

同参数（含 `forensic_runs_per_cell=4`）同种子，`generate_expansion()` 与
`shape_expansion_corpus.py` 的产物：

| 语料 | 对象级逐条比较 | 字节级 vs 归档 SHA-256 |
|---|---|---|
| `counted_quick`（480） | **0 条不同** | **MATCH**（`d869bda5…`，2330061 字节，逐字节相同） |
| `warmup_ledger.csv`（40 行） | — | **MATCH**（`200d73fc…`，3251 字节，逐字节相同） |
| `counted_forensic`（32） | 32 条不同，**全部只差 `synthetic.generator` 一个字段** | 差 256 字节；只把这 32 条的该字段归一化后 **MATCH** |
| `counted`（512） | 32 条不同（同上，全为 forensic） | 差 256 字节；归一化后 **MATCH** |
| `raw`（552） | 40 条不同（同上，全为 forensic） | 差 320 字节；归一化后 **MATCH** |

**唯一差异 = `synthetic.generator`**：取证记录此前盖 `shape_expansion_corpus.py`，
现在如实盖 `synth_campaign.py`。三件事让它成为「订正」而非「回归」：

1. **零读者**——全仓只有 `campaign_common.is_synthetic()` 碰 `synthetic`，它只看
   「是不是一个 dict」或看 `SYNTH-` 前缀；`generator` / `version` 两个键
   `grep` 下来在分析层**一个消费方都没有**。故它不改变任何一个分析结论。
2. **归档那份本来就自相矛盾**——同一次运行产出的语料里，quick 半边写着
   `synth_campaign.py`、取证半边写着 `shape_expansion_corpus.py`。现在两半一致。
3. **字节差核账对得上**：`'shape_expansion_corpus.py'` 比 `'synth_campaign.py'`
   长 8 字节，差异记录数 × 8 = 实测字节差（40×8=320 / 32×8=256），一字不多。

**没有第二处差异。** 这条对拍已固化为常驻守卫
`test_the_generator_still_reproduces_the_one_off_shaper`（整形器留在 evidence/
不删，正是为了让它一直有参照物），容许清单写成**逐字段白名单**——任何新差异都会
让它变红。

> 📌 第一版对拍脚本把四份语料**全部**报成 DIFF，其中包括一份逐条对象完全相同的。
> 根因是**量法**：它哈希的是内存里 `"\n".join(...)` 的结果，而写盘走文本模式，
> Windows 上每条记录行尾是 CRLF——「差异」是每条记录 1 字节的**测量仪器自身**。
> 归档的这份已改为**用生产写入路径落盘后再哈希真实字节**。

---

## 3. ④ 全链路复跑：**零误拒**

| 步骤 | 结果 |
|---|---|
| 契约门 | `contract OK: 520 record(s)` exit 0 |
| 报告 | md + HTML + **18 张 CSV** exit 0 |
| 发布门（主链路 counted 520） | **FAIL 1 / WARN 8 / N/A 3** |
| 发布门（取证子集 40） | **FAIL 1 / WARN 4 / N/A 3** |
| 发布门（含预热的 raw 560） | **FAIL 1 / WARN 8 / N/A 3** |
| `--plan` t1 / n1、覆盖矩阵 ×2 | exit 0 |

**三处 FAIL 全部且仅仅是「合成语料」**——即彩排的合格线本身。新形状**没有被任何
守卫误拒**。

与 T6 那份的差异，逐条都有出处、**没有一条是本轮引入的**：

| 差异 | 出处 |
|---|---|
| CSV 17 张 → **18 张**（新增 `exp_plan.csv`） | **D-388**（T8 ④：决定 n 的那个数进报告三面） |
| `exp_radio.csv` 多一列 **`egress_ips`** | **D-376**（T9：CGNAT 出口 IP 与服务小区并排）。实测差集 = 今日−归档 `['egress_ips']`、归档−今日 `[]`，**恰好一列**。 |
| 主链路「预热效应」由 `⚠ WARN` 变 `➖ N/A 汇池前提不成立` | **D-380**（T8 ①：`round_effect` 补汇池前提守卫）。`exp_round_effect.csv` 的 `round_cells_uneven` 列点名 24 个格（P03–P08 × 4），与 D-380 记的 32−8=24 对得上。 |
| 取证子集「样本充分性」由恒标 low_confidence 变 **✅ PASS 全部 8 个格样本充足** | **D-379**（T8 ⑤：取证 4 轮 → **5 轮**）。这正是 T6 记的 **F-5** 那条缺陷，本轮实测已消失。 |
| 取证子集「预热效应」**✅ PASS 3 个 KPI 均未见首轮劣化** | D-380 的另一半：子集内部汇池前提成立，守卫不误伤正确语料。 |

### 三个面各自核对（D-303：**分开数**，不合并）

| 特性 | md | HTML | CSV |
|---|---|---|---|
| 场景内生抖动 | `SCENARIO_INTRINSIC_JITTER` ×26、中文「场景内生抖动」×28 | **同为 ×26 / ×28** | `exp_stability.csv` 两独立列，取值分布 **22 True / 12 `network_side_unstable` / 254 `not_applicable`**（合计 288 = 96 单元 × 3 KPI） |
| 取证轮转 | 「序位效应」段 ×3 | 同 | `exp_order_effect.csv` 45 行；`exp_round_effect.csv` 9 行，带 `round_cell_imbalance` / `round_cells_uneven` 两列 |
| 预热轮 | **无任何面能指认它** | 同 | 同 |

> **「预热轮无面可指认」是 T6 记的 F-3，本轮复核**仍然成立**，而且它是对的**：
> D-366 的口径就是预热轮会正常上报、语料里没有任何字段说明自己是预热，
> 唯一认得它的是台账（本目录 `expansion_warmup_ledger.csv`，40 行，
> `disposition=预热丢弃` / `authority=D-366`）。生成器**刻意不给记录加一个
> 「我是预热」的合成专用字段**——加了，彩排就是在演一个外场根本造不出来的形状。
> 这一点有守卫钉着：`test_the_ledger_is_the_only_thing_that_knows_which_run_was_a_warm_up`
> 同时查「台账说了算」与「语料里没有自称预热的字样」两个方向。

> 📌 `SCENARIO_INTRINSIC_JITTER` 的 CSV 分布是 **22/12/254**，而 D-382 在 T6 语料上
> 记的是 23/12/253。**不是回归**：本轮取证子集由 32 run 变 40 run（D-379），
> 那 8 个取证格的 CV 随之变动，一个格因此翻面。总数 288 不变。
> `--plan` 两句结论（网络侧 **n≥111** / 场景内生 **78**）与 D-383 逐字吻合——
> 因为它们只喂 `counted_quick`，而那份与归档**逐字节相同**。
