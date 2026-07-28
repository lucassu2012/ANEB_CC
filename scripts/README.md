# ANEB 分析脚本工具集（`scripts/`）

> 纯 Python 标准库（无第三方依赖）。消费**服务端结果 JSONL**（合同 schema 1.0，
> 见 `spec/schemas/result-run.schema.json`），产出 markdown / 自包含 HTML 报告。
> 全部工具遵守 R-10：不可计算的量输出 `None`/`—`，**绝不**以 0 或哨兵顶替。
> 这句话由 `test_null_medians_never_render_as_zero` 端到端核对（**击落式**：把某格某个数置为 `None`
> 重新渲染，该行必须少掉一个数字）——覆盖 7 个出格模块。此前它只在 1 个模块上断言
> `fmt_num(None)=="—"`，**连渲染器都没碰过**，往渲染器塞一个 `or 0` 全套测试照样全绿（D-232）。
>
> **接手这一层？先读** [`../docs/ANALYSIS_LAYER_HANDOVER.md`](../docs/ANALYSIS_LAYER_HANDOVER.md)
> ——六条不可违反的原则、八个测试维度、当前状态与上手步骤。本文件是逐工具口径，那份是"为什么"。

## 两层

| 层 | 脚本 | 粒度 | 产出 |
|---|---|---|---|
| 逐-run | `analyze_results.py` · `dashboard.py` | 单次 run | 清单/KPI 中位摘要、单文件 HTML 看板 |
| **战役级** | `campaign_report.py`（综合报告）+ 各分析段：`attribution` · `stability` · `validity_rollup` · `subscore_rollup` · `buffering_rollup` · `transport_rollup` · `trust_rollup` · `order_effect` · `trend` | 跨 run 分组 | 热力卡 · 三级归因 · 复测 CV · 有效性分母 · 分数侧归因 · 批化失真 · 介质对比 · 测量可信度 · 序位效应 · 纵向趋势 |
| 入门/守门 | `validate_results` · `corpus_health` · `publish_check` · `annotate_campaign` · `coverage_matrix` · `provenance` | 语料与发布 | 契约门 · 语料完整性 · 发布前自检 · 标签补注 · 覆盖矩阵 · 溯源清单 |
| 规格门禁 | `validate_spec_scoring` · `validate_profiles` | spec 树 | 评分包不变量 · profile spec↔runtime 一致性 |
| 彩排 | `synth_campaign` | 合成语料 | M2 规模网格 + `--chaos` 病理注入（**仅供彩排**） |

战役级层由 `campaign_common.py`（共享库）支撑，分组维度来自**可选加性** `run.campaign`
标签块——约定与生产接线路线见 [`../docs/CAMPAIGN_LABELS_CONVENTION.md`](../docs/CAMPAIGN_LABELS_CONVENTION.md)。

## 典型工作流

```
# 1) 给外场 JSONL 补注战役标签（app 侧写入落地前的桥）
python annotate_campaign.py field.jsonl -o field_labeled.jsonl \
    --set point_id=SZ-CBD-01 --set carrier=cmcc --set tier=metro \
    --set campaign_id=sz-2026Q3-baseline --infer-time-band

# 2) 出综合报告（markdown + 自包含 HTML；入口自动跑输入契约门，坏语料拒绝出报告）
python campaign_report.py field_labeled.jsonl --html report.html

# 3) 单独看某 KPI 的复测稳定性 / 三级归因
python stability.py   field_labeled.jsonl --kpi t1_ttft_ms --cv-gate 10
python attribution.py field_labeled.jsonl --kpi n1_rtt_p50_ms
```

## 各工具

### `campaign_report.py` — 战役级综合报告
点位×忙闲×运营商 **AQS 热力卡** + **分 KPI 热力卡**（读权威 `*_grade`）+ **三级差分归因矩阵**
（RTT/TTFT 双 KPI）+ **复测稳定性 CV 段** + **优化前后对比**（两战役自动或 `--before/--after`）。
`--html PATH` 另出自包含 HTML；`--md PATH` 写 markdown 文件（默认 stdout）。

### `attribution.py` — 三级差分归因
同客户端/接入/时段对同城·区域·中心三级镜像端各测一轮，客户端差分**消共模**（铁律 3）：
`接入=median(metro)`、`区域骨干+=median(regional)−median(metro)`、`核心骨干+=median(core)−median(regional)`。
缺层记 coverage 不外推；负增量记 `inversion` 不清零；`--kpi n1_rtt_p50_ms|t1_ttft_ms`。

报告另出**分段异常定位**段（`segment_profile()`）：把同一段在各单元之间比较，回答
"这一段慢是**该点位特有**还是**所有点位都这样**"——后者是本次测量路径的共性
（如到中心镜像端的物理距离），**不指向任何点位**。判据为语料内 MAD 稳健筛查
（3×1.4826×MAD），描述性、非显著性检验、不与外部基准比较；过半单元取值相同时
MAD 退化为 0，改列"与共同取值不等"的单元并注明判据已变。`未见单点异常` **不等于**
各单元相同，齐不齐看 `离差/典型` 列。

### `stability.py` — 复测变异系数（CV）门 / 采样量核算
按 (**战役**,点位,运营商,时段,**层级**,profile) 算 `CV% = 样本 stdev/mean×100`，超门（默认 10%，
对齐计划 §6 M1 验收）标 `unstable`。<2 样本 / |mean|≈0 → CV 不可计算（`None`）。
战役与层级同理都在键内：复测是针对**同一条件**的重复，混池会把战役间的真实变化当成测量噪声。
`--kpi`、`--cv-gate`。

`--plan [PCT]`（默认 5）换成**采样量核算**：以实测离散度给出该单元当前**可辨最小差异**
（√2·1.253·sd/√n，与报告的噪声尺度同一常量）及达到目标所需的每侧复测数。
**外场用法**：测完第一个点位当天跑一次——网格提案按 CV≈5% 定的 n=5，实测离散度大就得加复测，
而这时还改得动采集计划（噪声尺度只能在事后告诉你 Δ 已经淹了）。离散度不可估的单元留 `—`。

### `buffering_rollup.py` — 批化归因（取证/失真核算）
按 (点位,运营商,时段) 汇总 `scenarios[].buffering`：众数归因、批化分/sawtooth/近零到达中位、
非 `none` 占比；非 `none` 占多数（>50%）标 `失真热点`。回答"这个中位数慢，是网络慢，
还是被中间盒/设备把流批化了"。**R-05**：批化是**取证证据**，本表与下游**均不据此改判**
validity/score。空块=未检测（不计 0），缺 `attribution` 归 `unknown`（**绝不**算 `none`）。
**这条红线由差分守卫核对**：把每个场景的取证块改写成"最大批化"判定，validity 汇总、AQS 热力格、
子分汇总必须逐字节不变（`test_buffering_annotation_never_moves_validity_or_score`，21 份语料）。
此前它只被"横幅里印没印『R-05』『不改判』这几个字"守着——**核的是那句话在不在，不是那件事成不成立**（D-233）。
比例列按 3 位小数渲染——真实批化分可低至 0.007，1 位小数会显示成 `0`（读作"无批化"）。
集成进综合报告 + 独立 CLI。

### `publish_check.py` — 发布前自检（D-124）
把 runbook §5 的手工清单变成一条命令（外场收工时手工清单最容易被跳过）。
**FAIL**（阻断发布，退出码 1）=机器可以确定的客观错误：混入合成语料、契约违规、
全无战役标签、空语料。**WARN**（须由人解释后才可发布）=需要判断的：低有效率格、
失真热点、时钟可疑热点、low_conf 格、序位效应等（**完整项目单以工具实际输出为准**，此处不复制清单）。
**N/A**（`➖`，本项无可核算对象，**未作判断**）=该检查连对象都没有：单战役语料谈不上前后效应量、
无同格双介质可比就谈不上介质差异、无可归因单元就谈不上层级对账。**判 WARN 还是 N/A 看的是对象、
不是证据**——有对象而缺证据（有格但无 `server_tier_endpoint`）仍是 WARN，须由人解释。
**两者都绝不记 PASS**：读者对这张表的第一个动作是扫图标，给一项从没跑过的检查打绿勾，
和 D-163/D-198 从「批化失真/测量可信度/样本充分性」里拿掉的是同一个谎（D-229）。
PASS 的含义收紧为**该项已在非空集合上核查且未见问题**；N/A 行的说明一律含「未核算」二字，
与机器判定互为充要（有守卫盯着，见 `test_a_check_with_nothing_to_run_on_never_renders_as_pass`）。
WARN 也绝不自动升格为 PASS——工具不替人做判断，只保证作者被问到"这个格为什么这样"时答得上来。
自检**不能**替代 runbook §5 里需要人工判断的条目（结论措辞、归档完整性、claim_scope 落款）。

### `transport_rollup.py` — 接入介质对比（wifi vs cellular）（D-110）
按 (点位,运营商,时段) 出各介质 run 数 + AQS 中位 + Δ(cellular−wifi) + **噪声尺度**（D-180）。
**负值本身不等于"蜂窝更差"**：Δ 是两个中位数相减，与「优化前后」同一形状，故段内每格都带
`±` 噪声量级与备注列——标 `噪声内` 的是复测抖动、**不得写成介质差异**，标 `噪声不可估` 的是
"不知道"、同样不计入结论（彩排语料实测：7 个负 Δ **无一**超出噪声）。摘要与
`publish_check` 的「介质效应量」项与本段共用同一判据，不会分歧；**"没有可比的格"不算"比过了没问题"**——
该项曾把两者印成同一条 PASS，21 份语料里出现 15 次、其中 12 次实为无可比对象，现已拆开记 N/A（D-229）。
**"不会分歧"这句承诺本身也有守卫盯着**：闸门印的「N/M 个负 Δ 超出噪声尺度」，必须与读者在本段表里
数出来的行数逐语料相等（`test_the_gate_figure_can_be_counted_in_the_transport_table`，D-230）。
transport 取 run 显式设置；`auto` 由各场景 `network_snapshot` 观测共识
推得（生产者实写复合格式 `auto(cellular)`，取括号内实际介质）；不一致=mixed、无观测=
unknown，**均不并入任何介质**。全 unknown → 覆盖缺口告示，不出表。集成进综合报告 + 独立 CLI。

### `trust_rollup.py` — 测量可信度（时钟/流完整性/解析开销）（D-111）
热力卡时延中位数背后的**仪器**可信度：时钟可疑占比（`clock.offset_suspect`，R-22：
|漂移|>100ppm 或端点缺失——该场景 TTFT/ITL 存疑）+ |漂移|中位、seq gap/dup 异常场景数、
`parse.per_event_parse_us` 中位（解析开销大会混淆 ITL：端侧算力≠网络）。各信号分母=
实际带标注的场景数，未标注**不算干净**；全无证据 → 覆盖缺口告示。时钟可疑过半标
`时钟可疑热点`。集成进综合报告 + 独立 CLI。

### `synth_campaign.py` — 合成全网格语料（**仅供彩排**，D-116/117）
> ⛔ **产出的数字是虚构的、不是实测**。每条记录带**双重标记**（加性 `synthetic` 块 +
> `SYNTH-` 战役前缀），`campaign_report` 检出后在报告最顶端印**不可能被忽略的红色警告**；
> 两个标记任缺其一仍可检出（改标签洗不掉、删块也洗不掉）。绝不可与真实语料混合。

生成 M2 规模网格（默认 8 点位×2 运营商×忙闲×3 层级×5 重复×2 战役 = 960 run/2880 场景，
<1 秒）：按层级基准 RTT + 点位质量因子 + 忙时惩罚 + 相对噪声派生全部 KPI，并**刻意埋入**
失效场景、可疑时钟点位、批化热点、双介质点位、抖动点位、轮转序位——让报告每一段都有东西可渲染。
`--seed` 决定论：同种子产出逐字节一致，彩排可复现。分级与 AQS 为**近似合理值**，
KpiGrading.kt / spec/scoring 仍是权威。

```
python synth_campaign.py -o rehearsal.jsonl
python campaign_report.py rehearsal.jsonl --md r.md --html r.html --csv t
```

**`--chaos`：混乱语料彩排（D-125）**——真实外场数据没那么干净。该开关注入 10 种真实病理
（某点位缺 core 层 / 只测到一个运营商 / 中途 abort / 同格混 profile 版本或直方图边界或
quick-forensic / 时钟跳变 / 极端离群 / 全无效格 / 未标注记录），用来验证分析层**诚实降级**：
不崩、不编数、每种病理报在正确位置（`TIER_MISSING` 不外推、abort 的 null AQS 不进中位、
不可比混池标 `MIXED_*`、离群拉不动中位数但撑爆 CV、空值恒渲染 `—` 而非 0）。
守卫见 `tests/test_chaos_rehearsal.py`。

### `annotate_campaign.py` — 离线战役标签补注
加性注入 `run.campaign`：`--set KEY=VALUE`（统一）/ `--map map.json`（per run_id）/
`--infer-time-band`（由 `started_at_epoch_ms`+`--tz-offset` 推 busy/idle，标 inferred）。
**非破坏**：只填 gap、原有标签优先永不覆盖、不覆盖输入（除非 `--inplace`）、`label_source` 记溯源。
**批量**：`--out-dir DIR` 一次补注多个文件（输出同名），外场一天几十个文件不必逐个 `-o`；
两条护栏——输出会覆盖输入时拒绝（那是 `--inplace` 的意思）、不同目录同名文件会碰撞时拒绝。
生产接线落地后本工具仍保留（补历史语料/漏标 run），见
[`../docs/CAMPAIGN_LABELS_WIRING_SPEC.md`](../docs/CAMPAIGN_LABELS_WIRING_SPEC.md) §8。

### `corpus_health.py` — 语料完整性预检
在信任任何报告之前先跑：分析再正确，也只与其下的语料一样诚实。**ERROR（exit 1，会让聚合出错）**：
同 run_id 两异 body、坏行（静默丢数据）、`claim_scope` 漂移（不同测量口径被并进同一中位数，
R-10 红线）、缺 run 体。**WARN（exit 0，值得知道但不致错）**：良性重复 run_id（D-09 双写的
预期重导，加载时去重）、无 run_id 记录、混 `schema_version`、缺 AQS/战役标签。`--json` 出机读结果。

### `order_effect.py` — 序位效应/遗留效应诊断（D-95）
契约里的 `run.scenario_order` 与 `scenarios[].order_index` 是**拉丁方反平衡的证据**——
但证据只有被检验才算数，本工具就是那道检验。按 (profile, KPI) 问：KPI 是否系统性依赖于
**它跑在第几位**？`spread_pct = (最大位置中位 − 最小位置中位)/总中位 × 100`，超门（默认 10%，
对齐 M1 的 CV≤10% 惯例）标记疑似。**空结果就是好结果**。诚实（R-10）：不同位置 <2 → 不可计算
（**绝不**记"无效应"）；位置样本不足 → low_confidence；总中位≈0 → 比例未定义而非无穷大。
另报轮转覆盖度。集成进综合报告 + 独立 CLI。

### `validity_rollup.py` — 有效性/失效原因逐格汇总（D-96）
每个中位数背后的**样本分母**：按 (点位,运营商,时段,profile) 出 尝试/有效/低置信/失效/未知
五态计数 + 有效率（低于门默认 80% 标 `LOW_VALID_RATE`），失效原因直方图（解释样本去哪了），
按 UTC 日有效率趋势（衰减=测量装置回归信号）。`VALID_LOW_CONFIDENCE` 计入可用但单列；
`unknown` 独立成桶绝不默认算有效。防幸存者偏差——报告只显示 n=4 不显示尝试数 40 时，
若失效恰集中在恶劣条件，中位数方向性偏乐观。

### `subscore_rollup.py` — AQS 分数侧归因（D-100）
`attribution.py` 时延矩阵的分数侧对偶：时延矩阵说路径**哪段**慢，本表说分数**哪维**低。
按 (点位,运营商,时段) 出各维度（T1/T2/…/N1/N2/U1…）中位子分 + **拖累维度**（中位最低）
+ 极差。不可计算 run 子分为空不贡献（绝不 0）；全格无子分 → 该格缺席不伪造"全好"。

### `trend.py` — 纵向 N 战役趋势（D-98）
把"一前一后"推广到 ≥3 战役时序轨迹：按 (点位,运营商,时段) 出各战役中位数轨迹 + 首末Δ +
方向判定。**方向按指标极性解释**（AQS/goodput 越大越好、时延/抖动越小越好）；非单调净变化
判"混合"不冒充趋势；缺席战役留 `None` 不插值；在场点 <2 → `NEED_2_POINTS` 不可计算。
战役默认按最早 `started_at_epoch_ms` 时序排序，`--order` 可显式指定。

### `coverage_matrix.py` — 覆盖完备性矩阵（D-101，独立规划工具）
「下一步测哪里」：给定目标网格（`--points/--carriers/--time-bands` 或 `--config` JSON），
对每个联合格判 未测/欠采/已覆盖（可用=有 AQS 分），另列**计划外**已测格。欠采绝不上取为
已覆盖；无目标网格降级为描述模式（`coverage_pct=None`，不虚构目标）。对齐 M2 外场网格
验收（6–8 点位×忙闲×双运营商）。不进综合报告（规划工具需目标网格）。

### `provenance.py` — 报告溯源清单（D-99）
已发布报告是"进局点的弹药"，须可溯源可复现：每个输入文件 basename+**sha256**、
读行/去重丢弃/冲突/坏行计数、塑形参数、工具版本 + 注入的 generated_at（注入而非取墙钟，
保持报告主体可快照）。渲染为报告头「溯源」段；`campaign_report.py --provenance PATH`
另写 sidecar JSON（含全部 sha）。

### `validate_results.py` — 结果 JSONL 输入契约门（D-97，`results-contract-unit`）
分析层前门：①结构层——必填清单/`claim_scope` const/`validity` 枚举**从 schema 文件实时
读取**（永不与 schema 漂移；**这句话由 `test_every_rule_this_validator_enforces_is_read_from_the_schema`
按 `load_schema` 抽出的 8 条规则**逐条改造 schema 副本**核对：改了 schema 抽取结果必须跟着变，
且判定必须跟着抽取结果变——此前 17 个用例全用真 schema，**一个「读了文件却按自己那份硬编码判」的
验证器能全部通过**，D-234）；②跨字段 R-10 层——`kpi.<x>` 值 null ⇔ `<x>_grade` null、
`aqs.score` null ⇔ `not_computable_reason` 在场、直方图 `len(counts)==len(edges_ms)+1`
（R-27 开区间桶）。validity 大小写不敏感比对（真数据小写为权威，大小写漂移记非致命
advisory 交 schema 属主）。exit 0/1/2（2=无语料或 schema 不可读→NOT_EXECUTED）。
**`campaign_report.py` 默认在入口跑同一检查**（违规拒绝出报告，`--skip-contract-check`
为显式逃生门）。

### `validate_spec_scoring.py` — spec 评分包门（D-102，`spec-scoring-unit`，需 pyyaml）
补齐无-Android 路径的评分规则包守卫（权威对拍 `SpecScoringParityTest.kt` 受 Android
工具链门控）：weights 每表 Σ=1.0(±1e-9)+version_id；anchors 各表 points 按值严格升序、
direction 枚举、分∈[0,100]；vetoes 必填字段+比较符/种类枚举+cap∈[0,100]。只读
`spec/scoring/`；pyyaml 缺 → exit 2 NOT_EXECUTED。

### `validate_profiles.py` — profile spec↔runtime 深门（D-103，`profiles-deep`）
①语义一致性——逐 profile 比对 `spec/profiles/server/<id>.json` 与 `profiles/<id>.json`
**解析后对象相等**（对 CRLF/键序稳健；字节比对会误红），单侧存在即错；②结构——顶层必填 +
每 phase `type` 已知且必填字段类型正确（bool 不算数值）。只读两棵树；树缺 → exit 2。
守卫「先改 spec 后动代码」：一侧语义改而另一侧漏改不再静默溜过。

### `campaign_common.py` — 共享库
记录加载（按 `run.run_id` 去重）、`run.campaign` 标签优雅降级、AQS/KPI/sub_scores/
buffering 访问器、nearest-rank 分位、AQS 四级分带（锚定系统 54/70 封顶阈值）、UTF-8
stdout。被上述战役级工具 import。

## CSV 编码（D-129）

导出的 CSV 为 **UTF-8 with BOM（`utf-8-sig`）**：CSV 的用途就是给人用 Excel 打开，
而中文 Windows 的 Excel 把无 BOM 的 UTF-8 当 GBK 读——点位 `深圳-CBD-01` 会显示成
`娣卞湷-CBD-01`（已实测）。pandas 会自动剥除 BOM；用 Python 直读请指定
`encoding="utf-8-sig"`（用 `utf-8` 会让 BOM 混进第一个列名）。

## 口径红线

- `claim_scope` 恒为 `application_end_to_end_to_probe_node`：**应用层端到指定节点路径**，
  **不表述为** MOS / 无线层评级 / 运营商全网 SLA。
- 缺 `run.campaign` 标签的记录塌缩为 `unlabeled`/`unknown` 桶并在报告标注 coverage 缺口——不猜、不补零。
- 样本 < `min_samples`（默认 5）标 `low_confidence`，不隐藏。

## 测试

```
python tests/run_all.py          # 自包含 golden runner（无 pytest），exit 0/1
```
接进 `verify_all.ps1` 门禁步 `campaign-analysis-unit`（PASS/FAIL/NOT_EXECUTED 三态）。
golden 用例编码方法学不变量（已知延迟预算恢复、缺层降级、inversion 不清零、CV 已知值、
分带边界等），守卫未来重构不弱化口径。
