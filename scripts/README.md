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
| **战役级** | `campaign_report.py`（综合报告）+ 各分析段：`attribution` · `stability` · `validity_rollup` · `subscore_rollup` · `buffering_rollup` · `transport_rollup` · `trust_rollup` · `radio_rollup` · `order_effect` · `trend` | 跨 run 分组 | 热力卡 · 三级归因 · 复测 CV · 有效性分母 · 分数侧归因 · 批化失真 · 介质对比 · 测量可信度 · 无线上下文 · 序位效应 · 纵向趋势 |
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
（`K×1.4826×MAD`，**K 随可比单元数标定**——单元越少 MAD 越抖，K 越大；固定 3σ 已于
D-200 退役），描述性、非显著性检验、不与外部基准比较；**少于 4 个可比单元不给筛查
结论**（该规模下没有任何阈值压得住申明的误报率）。过半单元取值相同时 MAD 退化为 0，
改列"与共同取值不等"的单元并注明判据已变——这是唯一不受 4 单元下限约束的分支，
因为它不需要标定。`未见单点异常` **不等于**各单元相同，齐不齐看 `离差/典型` 列。

### `stability.py` — 复测变异系数（CV）门 / 采样量核算
按 (**战役**,点位,运营商,时段,**层级**,profile) 算 `CV% = 样本 stdev/mean×100`，超门（默认 10%，
对齐计划 §6 M1 验收）标 `unstable`。<2 样本 / |mean|≈0 → CV 不可计算（`None`）。
默认 KPI 列表含 **t2_itl**（D-560 起：热污染的首要标的是解析/渲染路径的 ITL，
「ITL 表的热状态列」须有 ITL 行）；每格附「热状态」列＝格内带热监控证据 run 的最重
`thermal_max_status` + 污染 run 数（无证据＝—，不是 "none"；R-10/R-11；CSV 三列同批）。
战役与层级同理都在键内：复测是针对**同一条件**的重复，混池会把战役间的真实变化当成测量噪声。
`--kpi`、`--cv-gate`。

`--plan [PCT]`（默认 5）换成**采样量核算**：以实测离散度给出该单元当前**可辨最小差异**
及达到目标所需的每侧复测数——**两者都各有两个口径，并排印出**：
`(平)` 是恰好等于噪声尺度的量（√2·1.253·sd/√n，与报告的噪声尺度同一常量），
**真有这么大的差异也只有约五成会被判为「超出噪声」**；`(80%)` 才是有 80% 把握分辨/看见的那个数，
约为前者的 1.842 倍。**「达标?」按 80% 判**——此前表里只印 `(平)` 而判词按 80%，
一列按五成报、一列按八成判（D-201 治了「需 n≥」那一对，D-240 补上「可辨最小差异」这一对）。
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

### `badges.py` — 徽章值：文档引它、不抄数字（SPEC-4 §4.4 砍④脚本侧）
链跑归档时顺带产 `evidence/phase0/badges.txt`（`gate_count` / `reflex_tests` /
`corpus_real_runs`，各带 `_source` 说明取自哪一行）。**要治的毛病**：前台文档写死
门数与测试数，而这些数每次提交都在变（本仓已出过「文档 15 门实际 19 门」「758 tests
早已过期」）。**只写这次真测到的值**：测不到写 `unknown`，**不写 0、不沿用上次、不猜**
——过期的徽章比没有徽章更危险；reflex 有红时印 `739/741` 并标注，不冒充全绿。
只在**归档的那几次**产出（分层跑不落 evidence，自然也不覆盖徽章）。

### `corpus_ledger.py` — 语料台账：进展的单一事实源（SPEC-3 §3.1/T81）
一条命令全量重算数据资产：evidence/ 全部 jsonl 逐文件试装载（内容判定非名单，
D-273）→ `cc.load_records` 去重合并 → 真实/合成拆分（`is_synthetic` 单列绝不混入）
→ 按战役/点位/运营商/时窗（run 计）与 RAT/有效性（**场景**计——一 run 可跨 RAT
不折单值）分桶，设备侧 Room 库单独一节**不可与 wire 语料相加**。产物
`docs/CORPUS_LEDGER.md`（勿手编）+ 同名 CSV。**使用规则：任何「进展」声明必须
引用台账总数与增量，不得手抄数字**。守卫钉住与 `campaign_report` 清点行的对拍。

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
**退出码即契约**：`exit 1` 当且仅当出现 FAIL 行——WARN 可以留着、**N/A 也不参与阻断**。
此前这个数字没有任何东西守着（测试不跑它的 CLI，`verify_all` 也不跑这个工具），
而 D-229 刚给它数的那些行加了第四种严重度；现由 `test_publish_check_exit_code_is_decided_by_fail_alone`
按四种语料核对，并要求「带 WARN 与 N/A 却仍 exit 0」的情形至少出现两次（D-238）。

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
unknown，**均不并入任何介质**（**两个桶各查一遍**：`test_no_bucket_outside_the_two_media_is_pooled_into_one`；
此前只有 unknown 查过并桶，mixed 只钉在 `resolve_transport` 那一步——**标签判对了，仍可能并错桶**，D-235）。
全 unknown → 覆盖缺口告示，不出表。集成进综合报告 + 独立 CLI。

### `trust_rollup.py` — 测量可信度（时钟/流完整性/解析开销）（D-111）
热力卡时延中位数背后的**仪器**可信度：时钟可疑占比（`clock.offset_suspect`，R-22：
|漂移|>100ppm 或端点缺失——该场景 TTFT/ITL 存疑）+ |漂移|中位、seq gap/dup 异常场景数、
`parse.per_event_parse_us` 中位（解析开销大会混淆 ITL：端侧算力≠网络）。各信号分母=
实际带标注的场景数，未标注**不算干净**；全无证据 → 覆盖缺口告示。时钟可疑过半标
`时钟可疑热点`。集成进综合报告 + 独立 CLI。
**墙钟门（D-506/T68）**：第四个信号 `clock.wall_skew_ms`——`drift_ppm` 答"钟走得稳吗"，
它答"钟指得对吗"。判据 `|skew| > WALL_SKEW_MAX_MS(60s)`，**标记非否决**（KPI 计时走单调钟
R-24 不受污染，被污染的是"哪天测的"——**该处置已由 B2 终裁自动化**：分桶钟源
由语料证据自动判定，见有效率趋势表头与 CSV `day_clock` 列，注记改为指针不再复述劝告）；
出现即点名，不设"过半"门槛——按日分桶是逐条读的。**分母与时钟信号分开**（EchoWire 接线前
的语料带 `offset_suspect` 却不带 `wall_skew_ms`，共用分母会把"没测"读成"没问题"）；
`None` ⇒ 不判疑也不计入分母。阈值是 `AnebClient.WALL_SKEW_MAX_MS` 的**跨语言副本**
（设备侧算得出 `wallClockSuspect()` 却没把该 bool 落进 wire），故配跨端守卫直接从
`AnebClient.kt` 抽字面量比对，任一侧改动即红；上游若落了 bool，应改读它并删本侧常量。

### `radio_rollup.py` — 无线上下文（信号档与小区一致性）（D-284）
三级归因随 D-48 取消后，`PLAN_ALIGNMENT` §7.3 记下的替代是「单点参考端 + 多维协变量」，
而**无线上下文是其中第一顺位**。读 `scenarios[].network_snapshot.radio`：按 App 侧 R1
判据定档（`RSRP<-105dBm` 或 `SINR<0dB` → 弱；两项均不越线 → 良；两个分量都不可得 → **不定档**），
并标三类混淆——同格混了多个服务小区（`MIXED_SERVING_CELL`）、混了制式（`MIXED_RAT`）、
以及**同点位忙闲挂了不同小区**（`CELL_CHANGED`，与 `TIER_ENDPOINT_CONFLICT` 同形：
差值真实、但归因不成立）。`stale` 样本只排除并计数、绝不入池；把「不可得」写成 `0` dBm
的取值由值域检查拦下。**语料无该块时本段照出**，写明是**采集缺口而非「信号良好」**——
接线未落地前这就是它要传达的事。集成进综合报告 + CSV + 独立 CLI。

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
「不覆盖输入」按**四种输出去向逐一核对**（stdout / `-o` / `--out-dir` / `--inplace`），判据是**等价关系**：
输入字节变，当且仅当给了 `--inplace`——反向那半同样要紧，**`--inplace` 若悄悄变成空操作，
屏幕上照样打印「annotated 2/2 records」，而语料根本没标**（此前只有 `--out-dir` 查过输入，
`--inplace` 在整个测试套件里一次都没被执行过，D-236）。
**批量**：`--out-dir DIR` 一次补注多个文件（输出同名），外场一天几十个文件不必逐个 `-o`；
两条护栏——输出会覆盖输入时拒绝（那是 `--inplace` 的意思）、不同目录同名文件会碰撞时拒绝。
生产接线落地后本工具仍保留（补历史语料/漏标 run），见
[`../docs/CAMPAIGN_LABELS_WIRING_SPEC.md`](../docs/CAMPAIGN_LABELS_WIRING_SPEC.md) §8。

### `corpus_health.py` — 语料完整性预检
在信任任何报告之前先跑：分析再正确，也只与其下的语料一样诚实。
（**退出码按三类 ERROR 逐类核对**，判据是等价关系：`exit 1` ⟺ 页面印出 `## ERROR`——
此前该模块的用例全在进程内调函数，**CLI 一次都没跑过，`main()` 若对坏语料返回 0 没人会发现**，D-237。）
**ERROR（exit 1，会让聚合出错）**：
同 run_id 两异 body、坏行（静默丢数据）、`claim_scope` 漂移（不同测量口径被并进同一中位数，
R-10 红线）、缺 run 体。**WARN（exit 0，值得知道但不致错）**：良性重复 run_id（D-09 双写的
预期重导，加载时去重）、无 run_id 记录、混 `schema_version`、缺 AQS/战役标签。`--json` 出机读结果。

### `split_by_run_mode.py` — 按 `run.mode` 切 quick/forensic 分面（D-415②/T20①）
扩展轮出发前必做：`run.mode` 是契约必填字段（`result-run.schema.json:25`），quick 与
forensic 的采样密度截然不同，`stability.py --plan` 在两者混池的语料上核算出的"够不够量"
没有意义（现场当天要跑的两条 `--plan`，见 `M3_EXPANSION_ROUND_RUNBOOK_ADDENDUM.md` §5
第 4 项）。缺 `mode` 的记录 = 违约数据，如实拒绝并计数，**不是第三种 mode，不静默丢**
（D-336 形状）；值只认恰好等于 `"quick"`/`"forensic"`，其余字符串（含 `continuity`/`ab`
这类 `MainActivity.kt` 支持的真实模式）一律归入 `rejected` 的 `other_mode` 桶——不是
"错误数据"，只是这个工具的切分范围之外，交下游按需处理。`--quick-out`/`--forensic-out`
不给时默认写 `<stem>_quick.jsonl`/`<stem>_forensic.jsonl`；两个输出路径相同（含指回输入
本身）或输入路径读不了都直接非零退出、不写半成品。**`dedupe=False`**：同 `run_id` 两份
不同 body 的冲突记录不在这一层去重/检测，各自按 mode 落进对应子集——下游 `stability.py`
等默认 `dedupe=True`，冲突留给那一层捕获，本工具不做是为了不与"每条输入记录恰好被记
一次"这个单一职责冲突。
```
python split_by_run_mode.py counted.jsonl --quick-out quick.jsonl --forensic-out forensic.jsonl
```

### `verify_run.py` — per-run 落地即验：单行判词（T44①）
外场/夜间采集用：一个 run 刚落库，PO 或 v2 立刻要知道"这条能不能算数"，不能等回程
跑完整报告链才发现要重采。三查**全部复用既有工具的判据函数，不重写**（D-315"同名
实现"教训）：契约门=`validate_results.load_schema`/`.validate_records`（逐字复用，
本工具不碰 schema）；radio 覆盖=`radio_rollup.radio_of()`+同一条 `stale is True` 判据，
逐场景计数，写成 `covered/total`（run 里实际有几个场景就是分母，不写死 9）；出口读出
=`radio_rollup.egress_ip()`，非空计数+批内去重后看唯一值个数，`>1` 即
`publish_check.py` 的 `MIXED_EGRESS` 同一判据（`len(egress_ips) > 1`），不重新定义
"不一致"。本工具唯一新增的是把三查合成**一行**：全过 `PASS: ...`，不过
`FAIL: <哪一查、差多少>`——不含糊地说"有问题"。
```
python verify_run.py <run.jsonl 或 glob>
```

### `round_effect.py` — 预热效应诊断（首轮是否系统性更差，D-356）
取证模式每场景跑多遍，`scenarios[].repeat_index` 就是**轮次**（快测恒 0）。本工具按轮次切，
问：**第一轮是不是系统性更差**？首轮中位 vs 其后各轮中位的中位数，按各 KPI 自己的好坏方向
（复用 `trend.metric_higher_is_better`，不另立方向表）算「首轮劣势%」，超门（默认 10%）标疑似。
**与 `order_effect.py` 分工**：那个按**绝对 `order_index`** 分组答「位次偏倚」，而三轮拉丁方下
一个 profile 的三个位次**恰好落在三个不同轮次**——同一份真实语料两种切法给出 9~12% vs 2~4%
（D-355），两者合起来才分得清**预热**与**遗留效应**，而这决定操作者该做什么（丢首轮 vs 修反平衡）。
诚实（R-10）：只有一轮 → `SINGLE_ROUND`**不可校验**，并明说「本报告绝对值均为冷启动口径」；
某轮样本 <2 → 不判；缺 `repeat_index` 的场景**单独计数**，绝不并入第 0 轮。集成进综合报告 + 独立 CLI。

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
按**本地日**（UTC+8，与 `--infer-time-band` 同一偏移，见 `campaign_common.DEFAULT_TZ_OFFSET_H`）
有效率趋势（衰减=测量装置回归信号）；CSV 列名为 `local_day`，因为导出物离开页面后
就没有那句小标题替它说明是哪种「日」了（D-318）。**日取自哪把钟由 B2 终裁自动判定**
（2026-08-22）：全部已定日 run 带 `clock.wall_skew_ms` ⇒ 整表按**服务端**时刻分桶，
否则整表设备墙钟——部分证据不得升级、不得同表混两把钟；键源写在表头与 CSV
`day_clock` 列上，混合语料另有回退横幅。`VALID_LOW_CONFIDENCE` 计入可用但单列；
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

**`campaign_report.py` 自身的退出码**（均已实测）：`0`=已产出；`1`=契约门 FAIL、拒绝出
报告；`2`=用法/环境问题——空语料（`NOT_EXECUTED`）、`--campaign` 打错（会列出语料里实际
有哪些战役）、**输出路径不可用**（目录不存在，或把目录当成了文件名）。**输出路径在读语料
之前就检**（D-306）：此前四个输出旗标遇到打错的路径都抛 Python 栈回溯，而 md 先于 csv 写
出，`--md ok.md --csv nope/c` 会先落一份 markdown 再崩——**退出时磁盘上不会再留下半套交付
物**。

**输出路径的两种策略（有意不同，D-307）**：`annotate_campaign.py --out-dir` 命名的是**目录**，
不存在就**建**（runbook §2 的批量补注正依赖这一点）；`campaign_report.py` 的 `--md`/`--html`/
`--provenance`（文件）与 `--csv`（前缀）命名的**不是目录**，父目录不存在就**拒绝**——替一个打错
的父目录建目录，等于把交付物撒到没人会去找的地方。全仓只有这两个 CLI 带路径型写出旗标，
其余只写 stdout。

### `validate_spec_scoring.py` — spec 评分包门（D-102，`spec-scoring-unit`，需 pyyaml）
补齐无-Android 路径的评分规则包守卫（权威对拍 `SpecScoringParityTest.kt` 受 Android
工具链门控）：weights 每表 Σ=1.0(±1e-9)+version_id；anchors 各表 points 按值严格升序、
direction 枚举、分∈[0,100]；vetoes 必填字段+比较符/种类枚举+cap∈[0,100]。只读
`spec/scoring/`；pyyaml 缺 → exit 2 NOT_EXECUTED。

### `scoring_what_if.py` — 评分体系 what-if 模拟器（T59 决策就绪包配套，**不改生产评分代码**）
把全语料里**已落库的子分**当输入，重算"权重表/总分公式/置信门槛换一种写法，73 run 的
分数与档位会怎么变"，供拍板时看代价——`AqsScorer.kt` 一个字节都不动。
**自证资格先行**：每次运行先用**现行**权重表重算并与已落库 `run.aqs.score`/
`run.aqs_token.score` 逐 run 比对，最大绝对差 ≥1e-9 就拒绝输出任何 what-if 数字
（复现不了现状就没资格模拟改动）；权重表若在 `AqsScorer.kt` 侧被改动，这一步会当场失败。
三组案：①T3 权重再分配（A0 基线/A1 减半/A2 降至保险位，释放量按其余项现有比例分摊、Σ 仍为 1）
②短板惩罚函数（B0 基线/B1 min 拉动/B2 阈值扣分/B3 软封顶）③置信门槛（3/2/1）。
每案给分数区间+档位分布+**档位迁移矩阵**。档位阈值取 `campaign_common.AQS_GRADE_BANDS`
单一来源。决策③会同时印出**实测** `low_confidence` 分母与本表能覆盖的分母
（仅 306/489 场景带 `kpi_quality`），避免把"本表算得出来的"读成"只有这些"。只读语料、只写 stdout。

### `validate_profiles.py` — profile spec↔runtime 深门（D-103，`profiles-deep`）
①语义一致性——逐 profile 比对 `spec/profiles/server/<id>.json` 与 `profiles/<id>.json`
**解析后对象相等**（对 CRLF/键序稳健；字节比对会误红），单侧存在即错；②结构——顶层必填 +
每 phase `type` 已知且必填字段类型正确（bool 不算数值）。只读两棵树；树缺 → exit 2。
守卫「先改 spec 后动代码」：一侧语义改而另一侧漏改不再静默溜过。

### `pull_device_corpus.py` — 真机语料拉取（D-393；runbook 采集步的唯一可执行答案）
把设备 Room 库拉到本地并抽出 `report_body` 为 JSONL。**它填的是 runbook 一句
「把真机拉下来的原始 JSONL」却从不说怎么拉的缺口**：`/api/v1/results` **只支持 POST**
（`server/handlers_results.go:67`）、设备**无 `sqlite3`**、仓内此前**无 db→jsonl 工具**。
**必须连 `-wal`/`-shm` 一起拉**——App 用 WAL 写，只取 `.db` 会漏掉最近若干 run。
设备侧 `run-as … cat` **只读**，不改任何状态。

**隔离单批用 `--since-epoch-ms`**：`report_body` 存的是**该机全部历史 run**，不传截止点
就把全部倒出来。截止时间由**关联 `test_run.startedAtEpochMs`** 取得——
`report_body` 自己**没有时间列**，早期版本因此让 `--since-epoch-ms` **静默失效**
（该取 4 条取了 67 条仍报 success，红线 §2.16 第七例）；现改为关联取时间，
**关联不上就抛异常，绝不静默放行**。`--inspect` 只打印表结构、不写盘。

### `validate_voice_plan.py` — Profile 4 语音执行计划对拍门（D-390 §5.1，`voice-plan-parity`）
对拍 `spec/profiles/client/voice_realtime_plan.json` 与 `VoiceRunner.kt`：①**真读 Kotlin 源取常量**
（9 个 `const val` + 计划工厂内的字面量 + 打断轮索引）逐值比对——这是
`validate_spec_scoring.py` **刻意不做**的一步（那份只校验 YAML 自身不变量）；
②派生值 `derived_nominal_kbps` **重算**不信任字面量；③两个计划都在 wire 限额内；
④数字自身蕴含的合理性（打断点必须落在上行段内、打断轮索引必须是真轮次、
连续性断连轮不能是末轮，否则其后无轮次、重建无从观测）。只读两份文件；缺任一 → exit 2。

**为什么这道门必须存在**：Kotlin 侧的 `VoiceExecutionPlanParityTest.kt` 更强（它比对
`defaultSimPlan()` **实际生成**的计划），但**在发布门里不执行**——`verify_all` 只跑
`assembleDebug`，且 Gradle 在只有模块外文件变化时把 `testDebugUnitTest` 判 `UP-TO-DATE`
整个跳过（实测三处 spec 突变全存活）。本门双向突变审计 **10/10 咬住**，
含「改常量名让正则失效」也必须响——**提取器失效要报错，不许静默跳过比较**。

### `campaign_common.py` — 共享库
记录加载（按 `run.run_id` 去重）、`run.campaign` 标签优雅降级、AQS/KPI/sub_scores/
buffering 访问器、nearest-rank 分位、AQS 四级分带（锚定系统 54/70 封顶阈值）、UTF-8
stdout。被上述战役级工具 import。

## CSV 编码（D-129）

导出的 CSV 为 **UTF-8 with BOM（`utf-8-sig`）**：CSV 的用途就是给人用 Excel 打开，
而中文 Windows 的 Excel 把无 BOM 的 UTF-8 当 GBK 读——点位 `深圳-CBD-01` 会显示成
`娣卞湷-CBD-01`（已实测）。pandas 会自动剥除 BOM；用 Python 直读请指定
`encoding="utf-8-sig"`（用 `utf-8` 会让 BOM 混进第一个列名）。

## CSV 的 `synthetic` 列（D-303）

每张导出表的**最后一列**恒为 `synthetic`（`True`/`False`，语料级）。红色合成数据横幅
只印在 md/HTML 顶部，而 **CSV 只有列、没有横幅可看**——分析员是在这些文件上做计算的。
此前 CSV 里能看出「数字是虚构的」全靠 `point_id`/`campaign_id` 恰好带 `SYNTH-` 前缀，
纯属偶然：`_order_effect.csv` 按 profile×KPI×序位组织、`_segment_profile.csv` 按 KPI×段
组织，**两张表无论语料怎么标都不可能带出这个信息**；单战役工作流下 `_comparison.csv`
也同样没有。真实语料读 `False`——**留空会被读成「不知道」，那是 R-10 反过来犯**。

## 战役报告走哪条链：wire 批 vs 观察批（D-576/D-577，2026-08-29 裁定 A 案）

**两类语料，两条链，不可互喂**：

| 语料类型 | 例 | 分析链 | 产物 |
|---|---|---|---|
| **wire 批**（ANEB probe 契约 JSONL） | wave-1、s4 吞吐批 | `campaign_report` + `publish_check` | md+HTML+CSV 三面 + 发布门 |
| **观察批**（a11y／帧差／抓包） | 豆包先行批（T78） | `tools/e234/e2_analyze.py` 等 | e234 分析产物 + 判读页 |

**为什么不能互喂**：观察批产物（`adapter.log`／`screencap_index.jsonl`／pcap）**结构上没有**
`run.campaign.campaign_id` 等契约字段——那是「字段不该存在」，不是「忘了填」（D-576）；
喂 `validate_results.py` 即 `exit 1 contract VIOLATIONS`。反方向也不做：**不给观察量套
KPI 契约**去凑一份「看起来像 AQS 语料其实不是」的东西（D-577 否 B 案的理由）。

**观察批判读页归档**：`evidence/doubao_wave0_<日期>/`
（⚠ **不是 `doubao_pilot_`**——旧名，2026-08-29 按 SPEC-2 §2.1 验收判据统一为 `wave0`；
本仓已有人照旧名写过一次，包括我）。子结构按 e234 惯例：每格每轮一目录
（**每格一目录** `<条件>_<功能>/`——取值已定案（`de79afa`）：日期 `YYYYMMDD`、条件 `wifi`/`cell`、功能 `f1`..`f6`，**锚格 `wifi_f1_anchor/`**；含 `adapter.log`／`screencap_index.jsonl`／`collect_notes.json`；
**轮次不建子目录**——靠 `mark_rtt.jsonl` 的 `t` 标记分轮，采集脚本本就设计成一格一次会话。
⚠ 本行初版写的 `<条件>_<功能>_r<轮次>/` 是错的，与采集侧定案矛盾，2026-08-29 随 `80dd18e` 同步），
判读页与战役 README 落目录根。**每格还有第三类产物** `pcapdroid/`（通道 D，
采集侧 `b214f10` 定：**每格独立起停**、只留「方向+字节数+时戳」级统计不留载荷）
——它是 **F3/F4 上行诉求的唯一证据源**；该格缺 `pcapdroid/` ⇒ **F3/F4 的上行结论不给**
（不是「按其它通道估一个」）。

**判读入口**（工具属主给可执行形态，参数以 `--help` 为准，不靠转述）：

```
python tools/e234/e2_analyze.py --run-dir evidence/doubao_wave0_20260829/wifi_f1 --pkg com.larus.nova --out-md wifi_f1.md
```

每格跑一次（`--run-dir` 指到**格目录**，不是战役根；轮次在格内由 `t` 标记分），
产物汇总进判读页。

**为什么只点 `e2_analyze` 一只**（采集侧板面提到「三只 analyze」，此处实测收窄）：
三只接口同构（都吃 `--run-dir`/`--pkg`），**结构上都跑得起来**，但用途不同——
`e3_analyze` 判 `A0 → A0′` 间隔、`e4_analyze` 标定 `T_quiet`，且各自带一个**语义前提旗标**
（`--allow-handle-input-start-proxy` / `--a2-method {v3-cluster,operator-mark}`）——
那是口径选择，**不是本批默认适用**。豆包批要不要跑这两只、旗标取哪个值，
**需要先有一格实语料验过再定**；在那之前判读页只用 `e2_analyze`，
不预先把两只未验的工具写成流程（否则就是把「结构上能跑」当成「适用」）。

**判读第 0 步：先查战役 README 的必填项在不在**（采集侧 `ed24d95` 定的八条，
其中五条是判读的**硬依赖**——缺了不是「少一段」，是**结论没有支撑**）：

| 依赖项 | 判读里用来做什么 | 缺了的后果 |
|---|---|---|
| 每格时间戳 | 与锚格、切换点对齐 | 块间对照无从落位 |
| 每次网络切换时间戳 | 判断有无「块中途切」 | 该块条件不纯而看不出来 |
| 每功能提示词逐字 | 确认锚格与块 1 **真同负载** | 锚格前提不可验，整条漂移判据失效 |
| 锚格 vs 块 1 对照结论 | 判读页第一段 | 无从判断块间能不能比 |
| ROI 值 + 两帧自检均值 | 帧差量的有效性 | 无法证明 ROI 没框在静态区 |

**⚠ 读 ROI 自检时先排一个假阳性**（采集侧 `7025986` 实测，2026-08-29）：
`roi_mean = 0.0` **是屏灭的签名，不是「ROI 框在静态区」**——息屏后 `screencap`
照抓、照落盘、帧头正常，均值恒 `0.0`（**是合法数字不是 `None`**），
两种成因的读数**长得一模一样**而处置相反。判读遇到 `0.0` 先查该格时段设备是否息屏
（对 README 的每格时间戳与切换时戳），**别直接判「ROI 作废、重量一遍」——那个方向是反的**。

**查出缺项就在判读页首段写明「本批缺 X，故 Y 类结论不给」**——不替缺失的证据
补一个推断（R-10 在判读层的同一条：不可算的量不给值）。

**⚠ 代码级语义的适用前提：读的源码 ≠ 设备上跑的二进制**（采集侧 `2347a6a` 提出，
本节以下所有「代码怎么写的」结论都受它限制）。装机构建是 `0.1.0-phase0` / `2026-08-20`，
而下面的语义（含累计不重置）是从**今日源码**读出的——两者**未必同源**。
**已由第二层实证解除（`a1712e3`，我独立复核）**：`adapter/` 自安装日（08-20）起 **0 提交**，
`AnebAccessibilityService.kt` 与 `ObsStats.kt` 最后改动分别为 **08-03 / 07-19**——均早于安装日，
**故本节的代码级语义对该装机二进制成立**（诚实的否定）。
但**前提本身仍要写进判读页**：一旦重装或 `adapter/` 有新提交，这条结论即刻失效，
需重跑上面那两条核查。战役 README 必填项第 11 条记 `versionName` 与 `lastUpdateTime`，
**让语料可归属到一个具体二进制**——那是重跑这条核查的唯一锚点。
（**为什么这条不能省**：若两者不同源而按源码语义读数，**读出来的东西看起来完全正常**
——与本节 `roi_mean=0.0` 同族：错法不报错，只给出一个像样的数。）

**`rule_matched` 怎么读**（v2 以代码为据答，我逐处复核过，2026-08-29）：
该计数在 `adapter.log` 里，产出端 `AnebAccessibilityService.kt:357`、捕获端
`e234_collect.py` 的 `logcat -s AnebProbe:I`，行首 `ADAPTER_OBS`。
**🔴 它是会话内累计、不重置**——`ObsStats.kt` 全类只有初始化(:132)/自增(:180)/读出(:287)
三处，**无任何重置路径**（我 grep 复核，非采信转述）。因此：
- 每格一次会话 ⇒ **末行 = 该格全部轮次的合计**，不是某一轮的值；
- 要 per-round 就**拿相邻 `reason=throttle` 行做差**（每 5s 一行），再用
  `mark_rtt.jsonl` 的 `t` 标记时戳对齐轮次；
- **直接把末行当单轮值用，会把 5 轮读成 1 轮**——这是本量最容易出的错。

**基线用批内自产，不用 26/28**（v2 第 4 问答复，我采纳）：历史 26/28 测于**未知构建**
（可证不是 14.4.0，n=1，且同为会话累计口径），**降格为历史参考、不作对照判据**。
判读基线取**批内**：块 1 首格 F1/WiFi 即本批 App 版本的实测基线，锚格重复同格给出
批内稳定性。这比「只登记绝对值」强——**相对判读站得住，因为基线与被比数同版本同口径**。

**⚠ 锚格控得住时段，控不住制式**（采集侧 `603838f`／G-5，窗外实测
`gsm.network.type = NR_SA`——本批「蜂窝」是 5G 独立组网，不是 LTE；而 **NR↔LTE 在一批内会漂**）。
**判读后果**：锚格一致只能否定**时段**漂移，**不能**否定制式漂移；若某格期间发生回落，
「蜂窝 vs WiFi」的差里就混进了「NR vs LTE」。**故判读页的条件对照必须自带限定**——
写清各格实际制式——**唯一来源是战役 README 的记载**（我核过：`e234_collect.py` 不采制式、
`e2_analyze.py` 也不读，观察通道产物里**没有** `radio` 块；此处初版写「取 `radio` 证据或
README 记载」是给了一个不存在的选项，2026-08-29 自查订正）。
**采集侧已按前后各读一次记账**（`e927eb2`，接本 lane 提点）：每格开跑前与跑完各读一次
`gsm.network.type` 并排写进 README，于是三种情形可分——**前后两点同 NR ⇒ 照常判读；
两点同 LTE ⇒ 条件成立但与 NR 格按制式分池、不可并读；前后不一致 ⇒ 格内漂移，
该格任何条件结论都不给（单列保留并如实标注）**。
**⚠ 措辞约定（v2 加深一层，我漏了这点）**：两点采样**排除不掉 NR→LTE→NR 的往返漂移**，
故判读页一律写「**前后两点实测同制式，格内瞬时漂移不可排除**」，
**不写「全程 NR」**——降一档说，比说满了被推翻强。（若某批 README 只有单次读数，退回弱化处置：
「制式以窗前单次实测为准，格内漂移不可排除」，条件结论降一档。）
制式不一致的格**单列不并入**，
且结论句里不得只写「蜂窝」而不说是哪种制式。**这是 D-393 那个最贵形状的复发面**：
当年把「制式+出口同时不同」读成了时段差异，靠四个同出口窗才把时段解释否定掉。

**⚠ 若某个条件整批缺席，「条件对照」这一段不成立**（不是「少几格」）。
本批设计是 WiFi×蜂窝双条件，而采集侧记着 WiFi 侧有环境阻塞（`cb75f0f`：PC 热点
不可行、改推 USB tether）。**判读处置**：只拿到单条件 ⇒ 判读页**删掉条件对照段**，
改为该条件下的绝对值登记 + 逐功能横向比较，并在首段写明「本批只采到 <条件>，
条件对照不成立」——**不拿锚格或历史数去凑一个跨条件结论**（锚格只证批内稳定性，
不是另一个条件的替身）。

**判读前置：先看锚格，再决定块间能不能比**（随采集侧 `35e3a17` 定案同步）。
本批分 4 块交替采集，**块间不可直接对照**——块 1 是 F1/F2/F3、块 4 是 F4/F5/F6，
条件同而工作负载不同，读数本来就该不同（那正是本批要测的东西），
于是「时段漂移」与「功能差异」**完全共线**。可比的判据是收尾补跑的**锚格**
（F1/WiFi × 5 轮，与块 1 的 F1/WiFi **同条件同功能**）：两者显著不同 ⇒ 期间确有漂移，
**条件对照打折**；一致 ⇒ 块间比较才站得住。**判读页必须先写锚格结论，再写条件对照**
——顺序反了就是拿一个未经检验的前提去支撑结论。

## 口径红线

- `claim_scope` 恒为 `application_end_to_end_to_probe_node`：**应用层端到指定节点路径**，
  **不表述为** MOS / 无线层评级 / 运营商全网 SLA。
- 缺 `run.campaign` 标签的记录塌缩为 `unlabeled`/`unknown` 桶并在报告标注 coverage 缺口——不猜、不补零。
- 样本 < `min_samples`（默认 5）标 `low_confidence`，不隐藏。
- **语音双通道边界（大脑裁定 2026-08-22，随 voice 摘要上 wire 一并写明）**：wire 的
  run 级 voice 摘要**只供战役报告链并入与横幅计数**；**语音判读（T65 式锚点判读、
  逐轮明细分析）的权威通道仍是设备库 `voice_result` 全表**——摘要不得被当判读源，
  两用途分清。本层消费方建成后须在其 docstring 复述本边界。

## 测试

```
python tests/run_all.py          # 自包含 golden runner（无 pytest），exit 0/1
```
接进 `verify_all.ps1` 门禁步 `campaign-analysis-unit`（PASS/FAIL/NOT_EXECUTED 三态）。

**分层触发（SPEC-3 §3.2/T81，2026-08-28）**：`verify_all.ps1 -Scope server|app|scripts|spec|all`
——**减频不减门**：既有门的语义与 gate-integrity 一律未动（门数随后续接线增长，
以链跑汇总行 `checks: N total` 为准，此处不写死），层外的门显名记
**第四态 `SKIPPED_SCOPE`**（「本次没请它验」，与 NOT_EXECUTED 的「想验验不了」严格分开，
两者都绝不折算 PASS）。**`-Scope all` 保留给收官/入册/交接点**，分层跑供日常改动自检。
实测耗时：`spec` 2.7s / `server` 14.9s / `scripts` 200s / `all` 10 分钟以上。
**`-Strict` 现为默认**（NOT_EXECUTED 计败，四态核心语义）；要旧的宽松行为显式加 `-Lenient`。
**归档策略**：只有「收官全绿」（`-Scope all` 且零 FAIL/零 NOT_EXECUTED）与「红门样本」
（任一 FAIL 或幽灵命令，任意 scope）落 `evidence/phase0/` 并重生成 sha256 清单；
日常分层跑写 `$env:TEMP` 并打印路径——不再每跑一次就往 evidence 里堆一份日志。
golden 用例编码方法学不变量（已知延迟预算恢复、缺层降级、inversion 不清零、CV 已知值、
分带边界等），守卫未来重构不弱化口径。
