# ANEB 分析脚本工具集（`scripts/`）

> 纯 Python 标准库（无第三方依赖）。消费**服务端结果 JSONL**（合同 schema 1.0，
> 见 `spec/schemas/result-run.schema.json`），产出 markdown / 自包含 HTML 报告。
> 全部工具遵守 R-10：不可计算的量输出 `None`/`—`，**绝不**以 0 或哨兵顶替。

## 两层

| 层 | 脚本 | 粒度 | 产出 |
|---|---|---|---|
| 逐-run | `analyze_results.py` · `dashboard.py` | 单次 run | 清单/KPI 中位摘要、单文件 HTML 看板 |
| **战役级** | `campaign_report.py` · `attribution.py` · `stability.py` · `annotate_campaign.py` | 跨 run 分组 | 热力卡 · 三级归因 · 复测 CV · 优化前后对比 · 综合报告 |

战役级层由 `campaign_common.py`（共享库）支撑，分组维度来自**可选加性** `run.campaign`
标签块——约定与生产接线路线见 [`../docs/CAMPAIGN_LABELS_CONVENTION.md`](../docs/CAMPAIGN_LABELS_CONVENTION.md)。

## 典型工作流

```
# 1) 给外场 JSONL 补注战役标签（app 侧写入落地前的桥）
python annotate_campaign.py field.jsonl -o field_labeled.jsonl \
    --set point_id=SZ-CBD-01 --set carrier=cmcc --set tier=metro \
    --set campaign_id=sz-2026Q3-baseline --infer-time-band

# 2) 出综合报告（markdown + 自包含 HTML）
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

### `stability.py` — 复测变异系数（CV）门
按 (点位,运营商,时段,**层级**,profile) 算 `CV% = 样本 stdev/mean×100`，超门（默认 10%，
对齐计划 §6 M1 验收）标 `unstable`。<2 样本 / |mean|≈0 → CV 不可计算（`None`）。
`--kpi`、`--cv-gate`。

### `annotate_campaign.py` — 离线战役标签补注
加性注入 `run.campaign`：`--set KEY=VALUE`（统一）/ `--map map.json`（per run_id）/
`--infer-time-band`（由 `started_at_epoch_ms`+`--tz-offset` 推 busy/idle，标 inferred）。
**非破坏**：只填 gap、原有标签优先永不覆盖、不覆盖输入（除非 `--inplace`）、`label_source` 记溯源。

### `campaign_common.py` — 共享库
记录加载、`run.campaign` 标签优雅降级、AQS/KPI 访问、nearest-rank 分位、AQS 四级分带
（锚定系统 54/70 封顶阈值）、UTF-8 stdout。被上述战役级工具 import。

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
