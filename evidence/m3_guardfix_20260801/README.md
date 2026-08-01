# T8 · GUARD_DIFF P0 修复的复跑证据（C-1 / D-380）

> 2026-08-01 · v3 执行会话 · 承 `docs/M3_EXPANSION_ROUND_GUARD_DIFF.md` C-1
> 语料 = T6 彩排那一份，**未重造**：`evidence/m3_expansion_rehearsal_20260801/`
> 用固定 `SEED=20260801` 重生成，5 份产物 SHA-256 与 `CORPUS_SHA256.txt` **逐条吻合**
> （已核对，见下 §2）——故本目录与 T6 目录的差异**只可能来自代码改动**。

## ⛔ 隔离声明（D-270）

**本目录每一个数字都是虚构的**（合成语料，`campaign_id` 以 `SYNTH-` 开头且带 `synthetic` 块），
一律不得外发、不得作为任何结论依据。`publish_check` 对两份语料都照常 `⛔ FAIL 合成语料`、exit 1
——**那条 FAIL 是合格线本身，不是缺陷**。

## 1. 这份证据要证明什么

C-1：`round_effect` 缺 `order_effect` 自 D-335 起就有的**汇池前提守卫**，于是方向 B
（quick 主体 + 取证子集）的池化形状让它印出 **21% 的假预热信号**。
D-380 补上同款守卫后，**同一份语料**上必须出现两件事：

| # | 要看到的 | 在哪 |
|---|---|---|
| A | 主链路（池化）：21% 那一行**改判为拒绝**，并**点名**缺失的格 | `01_round_effect_pooled_AFTER.md` |
| B | 取证子集单跑：**仍然 ✅ PASS**（守卫不能误伤正确的语料） | `02_round_effect_forensic_AFTER.md` / `04_...` |

## 2. 语料指纹（重生成后对账，不是「默认一致」）

```
149cb57f…  2990852  expansion_raw.jsonl
4497d6ad…  2736387  expansion_counted.jsonl
d869bda5…  2330061  expansion_counted_quick.jsonl
70f8e546…   406326  expansion_counted_forensic.jsonl
200d73fc…     3251  warmup_ledger.csv
```

**5/5 与 T6 归档的 `CORPUS_SHA256.txt` 逐字节吻合。**

## 3. 实测结果（数出来的，不是转述）

### A. 主链路（`expansion_counted.jsonl`，512 run）

| KPI | 各轮中位(n) | 首轮劣势% | 修复前判定 | **修复后判定** |
|---|---|---|---|---|
| `t1_ttft_ms` | #0:467.6(n=1443) / #1:439.1(n=88) / #2:446.4(n=91) | 5.6 | 无明显预热 | **不可单独归因(单元混杂)** |
| `n1_rtt_p50_ms` | #0:26.61(n=1443) / #1:21.54(n=88) / #2:22.45(n=91) | **21** | **疑似预热效应** | **不可单独归因(单元混杂)** |
| `u1_goodput_mbps` | #0:35.83(n=966) / #1:38.58(n=62) / #2:38.29(n=61) | 6.8 | 无明显预热 | **不可单独归因(单元混杂)** |

点名的格：`CELL_CONFOUNDED:SYNTH-P03/cmcc/busy、SYNTH-P03/cmcc/idle、SYNTH-P03/cucc/busy
等 **24 个** 未出现在每一轮`（32 格 − 取证子集 8 格 = 24，**对得上**）。

> **测得的百分比仍然印在表上**——前提**限定**它，不**抹掉**它（D-335 对 `极差` 列的同一条规矩）。
> 那组 1443/88/91 的极不对称 n 也照旧印着，读者现在能看见判词为什么被拒。

### B. 取证子集单跑（`expansion_counted_forensic.jsonl`，32 run）

三个 KPI 全部 `无明显预热`（首轮劣势 1.2 / 0.6 / 0.6%），**零 `CELL_CONFOUNDED`**。
发布门：`✅ PASS 预热效应 3 个 KPI 均未见首轮劣化` + `✅ PASS 序位效应` +
`✅ PASS 序位效应·单元混杂`。**守卫没有误伤正确的语料。**

### C. C-3 自动跟着对（**验证过，不是假定**）

GUARD_DIFF C-3 说摘要与发布门「修 C-1 自动跟着对」。实测两处都改了，且**两处代码一个字没动**
（只在 `_ORDER_UNJUDGED_WHY` 加了新码的译文，否则会印裸标识符）：

- 摘要 bullet：`**预热效应**：有多轮语料，但各位次/各轮由不同的单元供样——汇池前提不成立，
  差异不可单独归因——**本轮无法校验**首轮是否更差。`
- 发布门：`➖ N/A | 预热效应 | 有多轮语料，但…汇池前提不成立…——预热效应**本轮未核算**`
  （修复前是 `⚠ WARN … 1/3 个 KPI 首轮系统性更差（n1_rtt_p50_ms(21.0%)）`）

### D. 三面各自核对（D-303：按模块计数会把「两张表只导一张」藏起来）

| 面 | 核法 | 结果 |
|---|---|---|
| markdown | `report.md` 数 occurrence | `不可单独归因(单元混杂)` ×12、`CELL_CONFOUNDED` ×12、段首横幅 ×1 |
| HTML | `report.html` 数 occurrence | **同为 ×12 / ×12 / ×1**（md→HTML 单一来源，D-107） |
| CSV | `exp_round_effect.csv` | 新列 `round_cell_imbalance`=`True`、`round_cells_uneven` 点名到格；`warm_up_suspected` 为空=已拒判 |

> 12 = 序位效应 3 段 × 3 profile 行（既有，D-335）+ 预热效应 3 个 KPI 行（本次新增）。

## 4. 预期中的**非回归**差异

`exp_radio.csv` 比 T6 那份多一列 `egress_ips`——那是 **D-376（T9）** 落地的结果，
**不是本次改动引起的**，也不是回归。T6 README 「同种子字节可复现」对 CSV 面自 D-376 起
**有条件成立**，该口径由 T9 属主补。

## 5. 复跑命令

```bash
# 0. 语料（工作目录 = evidence/m3_expansion_rehearsal_20260801/）
python shape_expansion_corpus.py
sha256sum expansion_*.jsonl warmup_ledger.csv     # 与 CORPUS_SHA256.txt 对账

# 1..3（工作目录 = scripts/；D=T6 语料目录，E=本目录）
python round_effect.py   $D/expansion_counted.jsonl
python round_effect.py   $D/expansion_counted_forensic.jsonl
python publish_check.py  $D/expansion_counted.jsonl
python publish_check.py  $D/expansion_counted_forensic.jsonl
python campaign_report.py $D/expansion_counted.jsonl \
    --md $E/report.md --html $E/report.html --csv $E/exp
```

## 6. B-1/B-3/B-5 与 B-2 的复跑（D-382 / D-383）

同一份语料，同一次报告。**三面各自数出来的命中数**（D-303：按模块计数会把
「两张表只导一张」藏起来）：

| 面 | `SCENARIO_INTRINSIC_JITTER` | 段首横幅 | 中文短语「场景内生抖动」 |
|---|---|---|---|
| markdown（`report.md`） | 25 | 1 | 26 |
| HTML（`report.html`） | **25** | **1** | **26** |
| CSV（`exp_stability.csv`） | 独立列 `scenario_intrinsic_jitter`：**23 True** | ✗（CSV 无横幅，这是它的形态） | ✗（列名即编码，D-337） |

25 = 横幅 1 + 摘要 1 + 表格行 23。CSV 的 `scenario_jitter_reason` 四种取值实测分布：
`""`(=已标) 23、`network_side_unstable` 12、`not_applicable` 253。

摘要 bullet（B-3）：

> **复测不稳定**：58/288 单元超 CV 门 —— … 等 58 个；**其中 23 个属场景内生抖动**
> （标 `SCENARIO_INTRINSIC_JITTER`，**不作为加测网络样本的理由**——那部分方差不在链路上，D-372）。

### B-2：结论句拆开后，数字往**反方向**动了

`06_stability_plan_t1_AFTER.md`（quick 分面，`t1_ttft_ms`）：

| | 单元数 | 建议复测数中位 |
|---|---|---|
| **旧口径**（全汇池） | 43 | **n≥78** |
| **新口径 · 网络侧**（本段唯一可据以加样本的） | 23 | **n≥111** |
| **新口径 · 场景内生**（单列，不并入） | 20 | n≥78 |

**GUARD_DIFF B-2 当初推断「那个 78 由 s2 主导」——主导是对的，方向说反了。**
旧口径不是把 n 报高，是**报低了约三成**：把一群「不该据此加样本」的低需求汇进来，
稀释掉了网络侧真正需要的采样量。**而这正是 n≥15 那个决定所依赖的同一张表。**

`07_stability_plan_n1_AFTER.md`（网络侧 KPI）对「场景内生」**零命中**——判据不越界。

## 7. A-1(a) 的复跑（D-388）

| 面 | 核法 | 结果 |
|---|---|---|
| markdown | `report.md` | `## 采样量核算` 段 ×1；决定 n 的那一列 `需 n≥(80%)` ×7 |
| HTML | `report.html` | 段标题 ×4（1 段头 + 3 个分 KPI 小节）；`需 n≥(80%)` **同为 ×7** |
| CSV | `exp_plan.csv` | **288 行 × 24 列，全量不折叠**（md 折叠已达标行并点名指向它） |

折叠在三张分表各自声明：`另有 **28** / **47** / **52** 个**已达标**单元未列出`——
**✗不足 / ✗超门 / 不可核算 / 场景内生抖动的行一律不折**，那些正是读者来这一段的理由。

`exp_plan.csv` 实测：`t1_ttft_ms` 网络侧仍不足的 20 个格，`required_n_at_power` 中位 **123**
（与 §6 那张表的 111 不同，因为这一份是全量语料、那一份是 quick 分面——**两个数各自对得上自己的口径**）。

---

*承 D-270 / D-303 / D-335 / D-337 / D-354 / D-364 / D-372 / D-376 / **D-380 / D-382 / D-383 / D-388**；GUARD_DIFF C-1 / C-3 / A-1 / B-1 / B-2 / B-3 / B-5；彩排 F-2。*
