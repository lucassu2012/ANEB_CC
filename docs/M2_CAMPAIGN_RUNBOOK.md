# M2 外场战役 Runbook：从原始 JSONL 到《热力卡与归因报告》

> 对齐《SYSTEM_DEV_PLAN v1.0》M2 外场 MVP：6–8 点位 × 忙闲 × 双运营商，
> 分析脚本出热力卡 + 三级归因初判 → 第一份《城市 AI 业务网络体验热力卡与归因报告》。
> 全流程已于 2026-07-23 用实验室语料端到端演练通过（各段全渲染，D-106）。
> 工具口径见 `scripts/README.md`；所有命令在 `scripts/` 目录下执行，纯 Python stdlib。

## 0. 前置：定义目标网格（战役开始前一次性）

> 网格还没定？依据与工时预算见 [`M2_GRID_DESIGN_PROPOSAL.md`](M2_GRID_DESIGN_PROPOSAL.md)
> （单 run 72.4s、基线 8 点位约 2.3 个外场日、为何重复 5 次），PO 批复 D1–D4 后填入下方。

把 PO 拍板的点位清单写成网格配置（外场期间每天用它回答「下一步测哪里」）：

```json
// campaign_grid.json（示例——以 PO 定值为准）
// 键名必须是 point_id / carrier / time_band（与记录里的字段名一致）；
// 写成复数 points/carriers/time_bands 会被工具直接拒绝并提示正确键名。
{"point_id":  ["SZ-CBD-01", "SZ-UNIV-02", "SZ-METRO-03"],
 "carrier":   ["cmcc", "cucc"],
 "time_band": ["busy", "idle"]}
```

## 0.5 出发前彩排（强烈建议：外场前一天跑一次）

用合成全网格语料把整条链路预演一遍，确认工具、参数、阅读方式都就位——
**不要**在外场当天第一次见到规模化报告长什么样。

**分两趟，各练一件事**（合成一趟会两头都练不到，原因见下）：

**A. 补注演练**——练整条链路上最容易出错的那一步：

```
python synth_campaign.py -o rehearsal_raw.jsonl --unlabelled --points 2 --repeats 3
python annotate_campaign.py rehearsal_raw.jsonl -o rehearsal_labelled.jsonl --set campaign_id=drill --set point_id=DRILL-01 --set carrier=cmcc --set tier=metro --infer-time-band
```

`--unlabelled` 让语料与**今天 app 的实际输出一致**（标签接线未落地 = 无 `run.campaign`）。
注意这一趟会把**所有记录压成同一点位、同一层级、同一战役**——那正是 `--set` 的语义，
**不是**用来看报告的语料。

**B. 读报告演练**——用带标签的满网格语料，看报告真正的样子：

```
python synth_campaign.py -o rehearsal_full.jsonl
python campaign_report.py rehearsal_full.jsonl --md r.md --html r.html --csv rt
python publish_check.py rehearsal_full.jsonl
```

（`publish_check` 必然报 FAIL：彩排语料本就是合成的，正是它该拦的。）

> **为什么必须分两趟**：A 趟的 `--set point_id=…` 把 8 个点位压成 1 个、三层级压成 1 层、
> 两个战役压成 1 个，于是热力卡只剩 2 格、归因矩阵只有同城一层、
> **「优化前后对比」整段根本不存在**——而那一段的噪声尺度恰是全报告最难读的部分。
> 从前的单趟彩排就是这样：手册叫人看热力卡颜色分布与层级增量，而彩排给不出来（D-182）。

### 彩排的正确答案（B 趟对着核，不是"看看而已"）

合成语料是**按已知答案设计**的（见 `synth_campaign.py` 的 `DESIGNED_EFFECTS`）。
对不上就是工具链坏了，不是数据没效果：

- [ ] 「优化前后对比」把 **`SYNTH-P05`** 的格判为**超出噪声**且方向为改善，摘要点名它。
      **若报告说全部格都在噪声内 → 改善检测路径已坏，不要带去外场。**
- [ ] 其余点位的 opt 改善判为 `噪声内`（设计上就小于噪声）——这是**正确**行为，不是工具迟钝。
- [ ] 「接入介质」信号说**未观察到超出测量噪声的介质差异**，**不**点名"蜂窝劣于 wifi"。
- [ ] 热力卡有明显颜色梯度（末位点位最差），归因矩阵三层级增量齐全。
- [ ] 报告顶端有红色合成数据警告；CSV 能被你的表格工具正常打开（中文点位名不乱码）。

> ⛔ 彩排产物**数字全是虚构的**。见到红色合成数据警告的报告**一律不得**外发或作为任何
> 结论依据。彩排文件用完即删，**绝不可**与外场语料放同一目录。

另外重点看：摘要各条信号的读法、稳定性段的省略声明。

## 1. 语料进门：契约校验（每批语料先跑，坏语料早死）

```
python validate_results.py field_raw.jsonl
```

- exit 0 过 / 1 违规（**停下**，找生产者，别带病出报告）/ 2 无语料或 schema 不可读。
- 已知案例：`evidence/phase3/e01_results/20260712.jsonl` 及更早 = 旧版生产者输出，
  run 层缺 `transport` 等 7 个必填字段——**历史遗留语料不混入战役**。
- **绝不喂**：`evidence/phase1/calibration/*.jsonl`（逐 token 到达样本，非 result-run）；
  v3 会话的 `ds_netperf/*.jsonl`（`tier`=网络塑形档，与本层 `tier`=归因层级不同域）。

## 2. 补注战役标签（app 侧写入落地前的桥）

> ⛔ **最容易犯的错**：一天的语料跨**多个点位**，而 `--set point_id=X` 会把它们**全部**
> 打成同一个点位——标签看起来完全正常，热力卡却是错的，下游无人能发现。
> **按点位分目录**（推荐）或用 `--map` 按 run_id 精确打标。多文件配统一 `point_id` 时
> 工具会告警，但它无法替你判断这些文件是否真的同点位。

> ⛔ **同一格内三层级必须连续测完**（同城→区域→中心一轮接一轮），中途不换运营商、
> 不跨忙闲边界，**也不要中途在 wifi 与蜂窝之间切换**（`metro` 走场地 wifi、`core` 走 SIM
> 时，算出的「核心骨干增量」其实是接入介质差；报告会标 `MIXED_TRANSPORT` 并判该格增量不可用）。
> 铁律 3 的共模抵消**只在三层级条件相同时成立**；`time_band` 只到忙/闲
> 粒度（几小时宽），所以"metro 凌晨 3 点测、core 晚上 8 点测"两条都叫 `idle`，算出的
> 「核心骨干增量」其实是**时段差异**。报告会核对三层级测量的时间间隔并把超门的格标
> `TIER_TIME_SPREAD:Xh`，但**标出来时已经补不了**——只能重测该格。

采集时按**点位 + 层级**分目录存放（`raw/SZ-CBD-01/metro/`、`raw/SZ-CBD-01/regional/`…），
然后**逐点位逐层级**补注——一条命令对应一轮：

```
python annotate_campaign.py raw/SZ-CBD-01/metro/*.jsonl --out-dir labeled \
    --set campaign_id=sz-2026Q3-baseline --set point_id=SZ-CBD-01 \
    --set carrier=cmcc --set tier=metro --infer-time-band
python annotate_campaign.py raw/SZ-CBD-01/regional/*.jsonl --out-dir labeled \
    --set campaign_id=sz-2026Q3-baseline --set point_id=SZ-CBD-01 \
    --set carrier=cmcc --set tier=regional --infer-time-band
python annotate_campaign.py raw/SZ-CBD-01/core/*.jsonl --out-dir labeled \
    --set campaign_id=sz-2026Q3-baseline --set point_id=SZ-CBD-01 \
    --set carrier=cmcc --set tier=core --infer-time-band
```

> ⛔ **必须分层级各跑一条**。上面那条红线要求三层级连续测完，所以一个点位目录里
> **本来就装着三层的轮次**；若只跑一条 `--set tier=metro` 把整个点位打成同城，
> 另外两层就被**标没**了——报告会报 `TIER_MISSING:regional,core` 说它们**没测过**
> （而你明明测了），三级差分归因**根本不会发生**；更糟的是全语料变成单层级后，
> 热力卡的 `TIER_INCOMPLETE` 也**不会触发**（没有哪一格与语料不同）。
> 多文件配统一 `tier` 时工具会告警——**看见就停下**，别当噪声划过去（D-189）。

若已混装在一个目录里，用 `--map map.json`（`{run_id: {point_id: …}}`）按台账精确打标。

`--out-dir` 输出同名文件、不动输入；若输出会覆盖输入或不同目录存在同名文件，工具**直接拒绝**
（分别提示用 `--inplace`、或先改名）。单文件仍可用 `-o`。

- 非破坏：只填 gap、原有标签永不覆盖、`label_source` 记溯源。
- `--infer-time-band` 按 `started_at_epoch_ms` 推忙闲（跨时区采集给 `--tz-offset`）。

## 3. 覆盖检查（外场期间每日收工跑）

```
python coverage_matrix.py labeled/*.jsonl --config campaign_grid.json
```

未测/欠采格 = 明日路线；**计划外**格 = 疑似误标，回查台账。

**第一个点位测完当天，另跑一次采样量核算**（这时改采集计划还来得及）：

```
python stability.py labeled/day1/*.jsonl --plan
```

网格提案的 n=5 是按 CV≈5% 推的。若结论行说"X 个单元在当前 n 下分辨不了 5% 的差异"，
按它给的 `需 n≥` 上调剩余点位的复测数；n 不够又照测下去，最后拿到的是一堆标着
`噪声内` 的格——**那时已经补不了**。反之若实测离散度明显小于假设，可据此收缩复测数
省出外场工时。离散度不可估（n<2）的单元不计入核算，别把它当成"达标"。

## 4. 出报告（入口自动跑契约门，坏语料拒绝出报告）

```
python campaign_report.py labeled/*.jsonl \
    --md report.md --html report.html --csv tables --provenance provenance.json
```

**语料里有多个战役时（优化轮之后必然如此）**：除「优化前后对比」/「纵向趋势」两段外，
**其余各段会把所有战役按格池化**——那个中位数**既不是前也不是后**（受影响的格标
`MIXED_CAMPAIGN`，报告顶部也会提示）。正确做法是**各出各的、再出一份对比**：

```
python campaign_report.py labeled/day1.jsonl --campaign sz-2026Q3-baseline --md report_base.md
python campaign_report.py labeled/day1.jsonl --campaign sz-2026Q3-opt --md report_opt.md
python campaign_report.py labeled/day1.jsonl --before sz-2026Q3-baseline --after sz-2026Q3-opt --md report_compare.md
```

**头条数字取自单战役报告**；混合那份只用来看对比段。战役名打错时工具 exit 2 并列出语料中
实际有哪些战役，不会给你一份空报告。

> 出表之后要**组装成交付物**（工具产出的是表格集合，不是报告）：
> 骨架见 [`M2_REPORT_TEMPLATE.md`](M2_REPORT_TEMPLATE.md)——口径边界/方法学/免责措辞
> 已预写（§2 为红线，照抄勿改），结论与数字留占位并注明从哪一段取。

产物：markdown 报告 + 自包含 HTML + **成套 CSV**（运行时逐个打印文件名，照单归档）+
溯源 sidecar（输入文件 sha256 / 去重与坏行计数 / 塑形参数——归档必带，
"进局点的弹药"须可复现）。优化前后对比给 `--before ID --after ID`；
≥3 个战役自动出纵向趋势段。

## 5. 发布前复核（先跑自检，再过人工项）

```
python publish_check.py labeled/*.jsonl
```

FAIL=客观错误**阻断发布**（混入合成语料 / 契约违规 / 全无标签），退出码 1；
WARN=**须由人解释**后才可发布（**具体项以 `publish_check` 的实际输出为准**，不在此复制清单——每加一项这里就会过期；含低有效率 / 失真热点 / 时钟可疑 / low_conf / 序位效应 /
效应量 / 战役池化 / 标签来源 / 否决封顶 / 层级同时性 / 同一接入 / 同一客户端）；
"无法判断"一律记 WARN，**绝不**记 PASS。自检覆盖不了的人工项仍需逐条过：



- [ ] 契约门通过（无 `--skip-contract-check`；stderr 无"未经校验"告示）
- [ ] 「有效性」段：各格有效率 ≥80%，无 `LOW_VALID_RATE`（有则先解释失效原因直方图）
- [ ] 「覆盖盘点」无意外 `unlabeled` 桶（有 = 漏打标）
- [ ] `low_conf`（n<5）格已在正文标注、结论不依赖它们
- [ ] 「批化归因」段无未解释的 `失真热点`（有 = 先做失真核算再谈网络结论）
- [ ] 「序位效应」段无显著位置-KPI 相关（有 = 反平衡失效，样本重采）
- [ ] 多轮战役时，「优化前后对比」中标 `噪声内` / `噪声不可估` 的格**未被写成改善或回退**
      （自检的「效应量」项即此；全部落在噪声内 = 本轮**没有可宣称的效果**，如实写）
- [ ] **本轮三层级全部由同一台设备采集**（⚠ 契约无设备标识字段，**工具无法核对**；
      中途换机的机型差异会整个计入骨干增量且不会有任何标记——只能靠采集方确认）
- [ ] 报告落款 claim_scope 原话在（`application_end_to_end_to_probe_node`，
      不表述为 MOS/无线层评级/运营商全网 SLA）
- [ ] **报告顶端无红色「合成数据警告」**（有 = 混入了彩排语料，立即停止外发）
- [ ] 归档四件套：report.md + report.html + tables_*.csv + provenance.json

## 已知坑速查

| 症状 | 原因 | 处置 |
|---|---|---|
| 契约门 4200 条违规 | 喂了 calibration 逐 token 样本 | 换 result-run 语料 |
| 契约门报 run 缺 7 字段 | 旧版生产者历史语料 | 隔离，不进战役 |
| 报告全塌 `unlabeled` | 忘了步骤 2 补注 | 先 annotate 再报告 |
| annotate 报 multiple inputs | 多文件共用一个 `-o` | 改用 `--out-dir DIR` 批量 |
| annotate 告警"正把 point_id 统一打到 N 个文件上" | 语料可能跨多点位 | 确认同点位再继续；否则分目录或用 `--map` |
| 热力卡只有一两格、样本数异常大 | 多点位被打成同一点位 | 回查步骤 2 的打标口径，重新补注 |
| annotate 报 collide / overwrite the input | 不同目录同名文件，或 out-dir 指向输入目录 | 先改名；确要原地改用 `--inplace` |
| 语料很大担心跑不动 | — | 实测 12960 run/38880 场景（13× M2 规模）全报告 24s，线性无 O(n²) |
| Windows 控制台乱码 | 非 UTF-8 code page | 工具已内置 force_utf8_stdout，无需处理 |
| 报告顶端出现红色合成警告 | 混入 `synth_campaign.py` 彩排语料 | 剔除 `SYNTH-` 战役记录后重跑，**该报告不得外发** |
| 稳定性段写"另有 N 个稳定单元未列出" | 规模下的声明式上限（非截断） | 正常；完整数据在 `_stability.csv` |
