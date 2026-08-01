# M3 扩展轮 · 合成彩排全链路证据包（T6 ②）

> 2026-08-01 · v3 执行会话 · 承 `docs/M3_EXPANSION_ROUND_PROPOSAL.md`（T3）
> 口径：大脑裁定**方向 B =「quick 主体 + 取证子集」**（依据即提案 §4.3；**待 PO 确认**，
> 它只影响工时表，不影响本链路形状）。

---

## ⛔ 隔离声明（D-270）

**本目录下每一个数字都是虚构的，全部产物一律不得外发、不得作为任何结论依据。**

隔离是**可核验的**，不是声明：

| 隔离手段 | 怎么核 |
|---|---|
| 双重合成标记 | 每条记录带 `synthetic` 块**且** `campaign_id` 以 `SYNTH-` 开头。`shape_expansion_corpus.py::assert_isolated()` 在**写盘之前**逐条断言，任一条不成立即 `SystemExit`、不产出文件。 |
| 产物不出目录 | 同一函数断言每个输出路径的 `dirname` 恰等于本目录；越界即拒绝写盘。 |
| 前门自己拦得住 | `publish_check` 对三份语料**全部**报 `⛔ FAIL 合成语料 N/N 条`、exit 1。**这条 FAIL 是彩排的合格线，不是缺陷**（runbook §0.5 页脚同款）。 |
| 与真实语料零接触 | 本轮全程未读写 `evidence/m2_pilot_20260731/` 等任何真实语料目录；语料由 `synth_campaign.generate()` 就地合成，无外部输入文件。 |
| 战役隔离 | 单战役 `SYNTH-EXP`，故 `MIXED_CAMPAIGN` 天然为零（D-270 的另一半：全量报告里那 192 行池化归因，在单战役形状下不会出现）。 |

---

## 1. 可复跑命令（逐条照抄即可重现）

工作目录标在每条前面。产物**全部**落在 `evidence/m3_expansion_rehearsal_20260801/`。
语料由固定 `SEED=20260801` 决定，**同种子字节可复现**。

```bash
# ── 0. 造语料（工作目录 = evidence/m3_expansion_rehearsal_20260801/）
python shape_expansion_corpus.py

# ── 1..9 全部在 scripts/ 下跑；D 为本证据目录的相对路径
cd scripts
D=../evidence/m3_expansion_rehearsal_20260801

# 1. 契约门（坏语料早死）
python validate_results.py            $D/expansion_counted.jsonl

# 2. 出报告（md + HTML + 17 张 CSV）
python campaign_report.py             $D/expansion_counted.jsonl \
    --md $D/expansion_counted_report.md --html $D/expansion_counted_report.html \
    --csv $D/exp

# 3. 发布门（主链路）
python publish_check.py               $D/expansion_counted.jsonl

# 4. 发布门（**取证子集单独**——见下 F-1/F-2，这一步不是可选的）
python publish_check.py               $D/expansion_counted_forensic.jsonl

# 5. 发布门（**含预热轮的原始拉取**，用来对照台账排除到底改变了什么）
python publish_check.py               $D/expansion_raw.jsonl

# 6/7. 采样量核算（runbook §3；**只喂 quick 主体**）
python stability.py $D/expansion_counted_quick.jsonl --kpi t1_ttft_ms    --plan
python stability.py $D/expansion_counted_quick.jsonl --kpi n1_rtt_p50_ms --plan

# 8/9. 覆盖矩阵（全量 vs 仅 quick——两个数不一样，见 F-4）
python coverage_matrix.py $D/expansion_counted.jsonl \
    --points SYNTH-P01,SYNTH-P02,SYNTH-P03,SYNTH-P04,SYNTH-P05,SYNTH-P06,SYNTH-P07,SYNTH-P08 \
    --carriers cmcc,cucc --time-bands busy,idle
python coverage_matrix.py $D/expansion_counted_quick.jsonl \
    --points SYNTH-P01,SYNTH-P02,SYNTH-P03,SYNTH-P04,SYNTH-P05,SYNTH-P06,SYNTH-P07,SYNTH-P08 \
    --carriers cmcc,cucc --time-bands busy,idle
```

> ⚠ **四份 `.jsonl` 语料不入库**（本目录 `.gitignore` 列明），因为它们是**确定性可重生成**的：
> 步骤 0 用固定 `SEED=20260801` 重跑即可。**「可重生成」这句话本身是可核对的**——
> 每份的 SHA-256 与字节数记在 [`CORPUS_SHA256.txt`](CORPUS_SHA256.txt)，重跑后对账即可，
> 对不上就说明生成路径变了（不要默认它一定一致）。**分析产物（报告 / CSV / 各步 stdout）
> 全部入库**，因为那才是结论所依据的东西。真实语料不适用此规则——真实测量不可重生成。

各步输出已归档为 `00_shape.txt` / `01_validate_counted.txt` / `02_report_counted.txt` /
`03_publish_check_counted.md` / `04_publish_check_forensic_subset.md` /
`05_publish_check_raw_with_warmup.md` / `06_stability_plan_t1.md` /
`07_stability_plan_n1.md` / `08_coverage_matrix.md` / `09_coverage_matrix_quick_only.md`。

## 2. 语料形状（`shape_expansion_corpus.py` 造的是什么）

`synth_campaign.py` 造的是 **M2 的形状**——`mode="quick"`、每场景 `repeat_index=0`、
全语料同一个 `scenario_order`。扩展轮要的三样东西它一样都造不出来，故本目录带一只
**一次性整形器**（先例：`evidence/m2_pilot_20260731/s2_jitter_probe.py`），它 `import`
`scripts/synth_campaign` 后就地整形，**不改 `scripts/` 一个字**。

| 语料 | run 数 | 组成 |
|---|---|---|
| `expansion_raw.jsonl` | 552 | 拉取到的全部：512 quick（32 格 × 16）+ 40 取证（8 格 × 5） |
| `expansion_counted.jsonl` | 512 | 按台账排除 40 条预热轮后：480 quick（32 格 × **15**）+ 32 取证（8 格 × **4**） |
| `expansion_counted_quick.jsonl` | 480 | 主体分面 |
| `expansion_counted_forensic.jsonl` | 32 | 取证子集分面 |
| `warmup_ledger.csv` | 40 行 | 每条预热轮的 `run_id` + `disposition=预热丢弃` + `authority=D-366` |

网格：8 点位 × 双运营商 × 忙闲 × **单层级 metro**（D-48 单实例 E-01）= 32 格；
点位一律占位 `SYNTH-P01..P08`（**真名 PENDING-PO**；此处沿用生成器前缀，因为
`SYNTH-` 本身就是合成标记 #2，换成别的名字会削弱标记）。取证子集 = 前两个点位 ×
双运营商 × 忙闲 = 8 格，每格 4 轮计入（提案 §4.2 的「建议 4 轮」）。

### 设计效应（给彩排一个「对着核」的答案，同 `DESIGNED_EFFECTS` 的纪律）

下列幅度都是**设计值**，其**出处是已归档决策里的实测值**；本脚本不产生任何新测量，
其输出**不得**被引用为测量：

| # | 设计效应 | 设计源 |
|---|---|---|
| E1 | s2 的场景侧 KPI（T1/T2/U2）额外抖，**而同批 `n1_rtt_p50_ms` 不抖** | D-353 实测 CV 5.5/10.3/5.9%；D-372 判定其为场景内生 |
| E2 | 每格第一条 run（预热轮）系统性更差，且**只有台账认得它** | D-358（蜂窝丢一轮预热值 RTT≈15%）、D-366（台账排除） |
| E3 | 取证 run 内部三轮次轮转齐全（`order_index` 0..8、`repeat_index` 0/0/0/1/1/1/2/2/2、`scenario_order` 三段以 `\|` 连） | D-354 |

---

## 3. 链路结论：**通过**，且新形状**未被任何守卫误拒**

`validate_results` exit 0（512/512 合规）→ `campaign_report` exit 0（md + HTML + 17 CSV
全出）→ `publish_check` **FAIL 1 / WARN 8 / N/A 2**，唯一的 FAIL 是**合成语料**那条，
即彩排的合格线本身。**没有一条守卫因为「n=15」「s2 抖」「9 位次取证」这些新形状而报错、
崩溃或拒绝出报告。**

三条设计效应逐条兑现：

| # | 兑现证据（取自归档产物） |
|---|---|
| E1 | `expansion_counted_quick.jsonl` 逐 profile 的**格中位 CV**：`t1_ttft_ms` s1 **4.12%** / s2 **13.11%** / s3 **4.48%**；同批 `n1_rtt_p50_ms` s1 **2.66%** / s2 **2.59%** / s3 **2.49%**。**s2 只在场景侧抖，网络侧与 s1/s3 齐平**——D-372 的形状原样再现。落到报告上：`exp_stability.csv` 里 `t1_ttft_ms` 超 CV 门的格 **s2 占 27/32，s1 与 s3 各 4/32**。 |
| E2 | 同一算法在 `expansion_raw.jsonl`（含预热轮）上：`t1_ttft_ms` s1 **5.59%** / s2 **13.47%** / s3 **5.52%**；`n1_rtt_p50_ms` s1 **5.77%** / s2 **5.74%** / s3 **5.66%**。**把预热轮排除掉，网络侧 CV 从 ~5.7% 掉到 ~2.6%（少一半多）**，s1/s3 的 TTFT CV 也降约三分之一。这就是 D-366 台账排除买到的东西，**而它只在数字上看得见——分析层没有任何一个面能指认哪条 run 是预热轮**（见下 F-3）。 |
| E3 | 取证子集单独过门：**序位效应 ✅ PASS「9 处均未见序位偏倚」**、**序位效应·单元混杂 ✅ PASS「9 处各位次由同一组单元供样，汇池前提成立」**、**预热效应 ✅ PASS「3 个 KPI 均未见首轮劣化」**。D-353 的「拉丁方未轮转」缺陷在这一面上**已消失**。 |

---

## 4. 彩排真正挖出来的东西（F-1..F-5）

守卫没有误拒——**误的是方向 B 的分析计划**。以下五条全部由本次彩排暴露，
**只在此登记，不改代码**（改动清单见 `docs/M3_EXPANSION_ROUND_GUARD_DIFF.md`）。

### F-1 ⛔ 池化在一份报告里时，取证子集**校验不了序位**——而那正是它存在的理由

主链路（`expansion_counted.jsonl`）的发布门：

> ⚠ WARN 序位效应 | 已轮转，但**所有 profile 的执行位次与单元不平衡**——本轮无法校验是否残留序位偏倚
> ⚠ WARN 序位效应·单元混杂 | **9 处**执行位次与单元不平衡

报告正文点了名：`CELL_CONFOUNDED:SYNTH-P03/cmcc/busy … 等 **24 个** 未出现在每个位次`。

**根因是构造性的**：quick 主体给出的是位次 #0/#1/#2（32 个格**全都**供样），取证子集给出
位次 #0..#8（**只有 8 个格**供样）。于是位次 #3..#8 由 8 个格喂、位次 #0..#2 由 32 个格喂，
D-335 立的那条汇池前提当场不成立。**守卫是对的**：它拒绝把「点位差」当成「序位差」。

**处置（不改代码）**：取证子集**必须单独出一份报告/过一次门**（上文命令 4）。
单独跑时三条全部 PASS。→ 已写进 runbook 增补草案的收工清单。

### F-2 ⛔ 同一处池化让「预热效应」印出一个 **21% 的假信号**

主链路预热效应段：

| KPI | 各轮中位(n) | 首轮劣势% | 判定 |
|---|---|---|---|
| `n1_rtt_p50_ms` | #0:26.61(**n=1443**) / #1:21.54(**n=88**) / #2:22.45(**n=91**) | **21** | **疑似预热效应** |

`round_effect` 按 `repeat_index` 跨 run 汇池。quick run 只有 `repeat_index=0`，于是
**第 0 轮的池 = 全部 8 个点位**（含最差的那个），**第 1/2 轮的池 = 只有子集那 2 个最好的点位**。
21% 里没有一点是预热，**全是格构成差**。`expansion_raw.jsonl` 上同样印 18.9%——
**说明它与预热轮在不在语料里无关**，进一步坐实根因是池化而非预热。

段落**如实印出了 1443 / 88 / 91 这组极不对称的 n**（诚实），但**判词照下**。
`order_effect` 有 D-335 那条汇池前提守卫，**`round_effect` 没有同款**。

**处置（不改代码）**：同 F-1，预热效应只认取证子集那一面；单独跑时 PASS。

### F-3 ✅ 诚实的否定：分析层**确实**没有任何一个面能指认「哪条是预热轮」——而 D-366 早就这么说了

`round_effect` 回答的是**一条 run 内部**的轮次（`repeat_index`），
被丢弃的预热轮是**一整条 run**，它在语料里与计入轮长得一模一样。
本轮实测：`expansion_raw.jsonl` 与 `expansion_counted.jsonl` 的发布门**逐条同判**
（FAIL 1 / WARN 8 / N/A 2，两侧「预热效应」都因 F-2 那个假信号而 WARN）。
**差别只出现在数字上**（E2 那组 CV），没有出现在任何标记或判词上。

这**不是缺陷**——D-366 原话「台账是唯一能认出它的地方」。登记它，是为了让下一个人
不要指望发布门去替他核对「预热轮排干净了没有」。**那件事只有台账能核，且必须人工核。**

### F-4 ⚠ 覆盖矩阵的「样本」列在方向 B 下**不等于 n**

`08_coverage_matrix.md`（全量）：子集那 8 个格印 **19**（= 15 quick + 4 取证），
其余 24 格印 15。`09_coverage_matrix_quick_only.md`（仅 quick）：32 格**全印 15**。

「样本」= 该格 run 数，不分模式（`repeat_index` 那一列已由 D-344 撤销，理由仍成立）。
于是**每日收工那一步无法核对「n≥15 网络样本」这条判据**——19 既可能是 15+4，
也可能是 19 条 quick。**处置（不改代码）**：收工的覆盖检查**喂 quick 分面**。

### F-5 ⚠ 提案建议的「每格 4 轮取证」低于 `DEFAULT_MIN_SAMPLES=5`，取证格**必定**标 low_conf

取证子集单跑：`⚠ WARN 样本充分性 | 8/8 个格 n<5（标 low_conf，结论不应依赖）`。

提案 §4.2 的「≥2 轮为最低、建议 4 轮」是**为每位次 n≥4** 定的（序位判据），
而热力卡的样本门 `DEFAULT_MIN_SAMPLES=5` 数的是**每格 run 数**。两个判据都对，
**只是不是同一个量**，撞在一起的结果是取证格的 AQS 结论恒不可用。
序位/预热三段**不受影响**（它们汇池后每位次 n=32），受影响的是取证格的热力卡与 AQS。

**这是一个待 PO / 大脑拍的口径题**，两条路都成立：
(a) 取证每格改 **5 轮**（对齐样本门，代价 = 每格多一轮 6.5 min）；
(b) 维持 4 轮并**明写**「取证子集只用于序位/预热校验，其热力卡格不作结论」。
本文**不擅定**，登记为待定。

---

## 5. 本轮**没有**发现的（诚实的否定，逐条写出来）

- 契约门**没有**误拒 9 场景 / `mode="forensic"` / `repeat_index=0..2` 的记录：512/512 合规。
- 报告前门**没有**因为新形状拒绝出报告：md、HTML、17 张 CSV 全部产出，exit 0。
- **没有**出现 `MIXED_CAMPAIGN`（单战役）、`TIER_ENDPOINT_UNVERIFIED`（单层级、端点唯一）。
- `RULED_OUT`（D-366 的 U1←s1_chat 排除）在新形状下照常工作并计数：预热效应段 `RULED_OUT:533`。
- n=15 **没有**触发任何「样本过多/过少」类的守卫；主链路样本充分性 ✅ PASS「全部 32 个格样本充足」。
- `SCENARIO_INTRINSIC_JITTER` 在 md / HTML / CSV **三面各 0 次命中**——**它还不存在**，
  本轮只造出了它该标注的那个形状（E1），标记本身属改动清单第 1 条。

---

*产物清单见本目录；语料生成器 `shape_expansion_corpus.py`（一次性彩排工具，非 `scripts/` 生产件）。
承 D-270 / D-303 / D-309 / D-335 / D-340 / D-344 / D-353 / D-354 / D-358 / D-366 / D-372。*
