# M2 外场战役 Runbook：从原始 JSONL 到《热力卡与归因报告》

> 对齐《SYSTEM_DEV_PLAN v1.0》M2 外场 MVP：6–8 点位 × 忙闲 × 双运营商，
> 分析脚本出热力卡 + 三级归因初判 → 第一份《城市 AI 业务网络体验热力卡与归因报告》。
> 全流程已于 2026-07-23 用实验室语料端到端演练通过（13 段全渲染，D-106）。
> 工具口径见 `scripts/README.md`；所有命令在 `scripts/` 目录下执行，纯 Python stdlib。

## 0. 前置：定义目标网格（战役开始前一次性）

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
**不要**在外场当天第一次见到规模化报告长什么样：

```
python synth_campaign.py -o rehearsal.jsonl
python campaign_report.py rehearsal.jsonl --md r.md --html r.html --csv rt
```

> ⛔ 彩排产物**数字全是虚构的**。报告顶端会印红色合成数据警告；
> 见到该警告的报告**一律不得**外发或作为任何结论依据。彩排文件用完即删，
> **绝不可**与外场语料放同一目录。

预演时重点看：摘要六信号的读法、热力卡颜色分布、归因矩阵的层级增量、
稳定性段的省略声明、CSV 能否被你的表格工具正常打开。

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

同一批（同点位同层级）多个文件用 `--out-dir` 一次补注；跨点位混装时用 `--map` 按 run_id 精确打标：

```
python annotate_campaign.py raw/day1_*.jsonl --out-dir labeled \
    --set campaign_id=sz-2026Q3-baseline --set point_id=SZ-CBD-01 \
    --set carrier=cmcc --set tier=metro --infer-time-band
```

`--out-dir` 输出同名文件、不动输入；若输出会覆盖输入或不同目录存在同名文件，工具**直接拒绝**
（分别提示用 `--inplace`、或先改名）。单文件仍可用 `-o`。

- 非破坏：只填 gap、原有标签永不覆盖、`label_source` 记溯源。
- `--infer-time-band` 按 `started_at_epoch_ms` 推忙闲（跨时区采集给 `--tz-offset`）。

## 3. 覆盖检查（外场期间每日收工跑）

```
python coverage_matrix.py labeled/*.jsonl --config campaign_grid.json
```

未测/欠采格 = 明日路线；**计划外**格 = 疑似误标，回查台账。

## 4. 出报告（入口自动跑契约门，坏语料拒绝出报告）

```
python campaign_report.py labeled/*.jsonl \
    --md report.md --html report.html --csv tables --provenance provenance.json
```

产物：markdown 报告 + 自包含 HTML + 3 张 CSV（heat/attribution/stability）+
溯源 sidecar（输入文件 sha256 / 去重与坏行计数 / 塑形参数——归档必带，
"进局点的弹药"须可复现）。优化前后对比给 `--before ID --after ID`；
≥3 个战役自动出纵向趋势段。

## 5. 发布前复核清单（逐项过，不过不发）

- [ ] 契约门通过（无 `--skip-contract-check`；stderr 无"未经校验"告示）
- [ ] 「有效性」段：各格有效率 ≥80%，无 `LOW_VALID_RATE`（有则先解释失效原因直方图）
- [ ] 「覆盖盘点」无意外 `unlabeled` 桶（有 = 漏打标）
- [ ] `low_conf`（n<5）格已在正文标注、结论不依赖它们
- [ ] 「批化归因」段无未解释的 `失真热点`（有 = 先做失真核算再谈网络结论）
- [ ] 「序位效应」段无显著位置-KPI 相关（有 = 反平衡失效，样本重采）
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
| annotate 报 collide / overwrite the input | 不同目录同名文件，或 out-dir 指向输入目录 | 先改名；确要原地改用 `--inplace` |
| 语料很大担心跑不动 | — | 实测 12960 run/38880 场景（13× M2 规模）全报告 24s，线性无 O(n²) |
| Windows 控制台乱码 | 非 UTF-8 code page | 工具已内置 force_utf8_stdout，无需处理 |
| 报告顶端出现红色合成警告 | 混入 `synth_campaign.py` 彩排语料 | 剔除 `SYNTH-` 战役记录后重跑，**该报告不得外发** |
| 稳定性段写"另有 N 个稳定单元未列出" | 规模下的声明式上限（非截断） | 正常；完整数据在 `_stability.csv` |
