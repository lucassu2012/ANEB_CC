# 四单派发索引（2026-08-28）

> 来源：PO 经远程分析会话直派。背景诊断：`docs/PROGRESS_DIAGNOSIS_AND_RESPEC_20260828.md`。
> 本索引供 PO 与大脑会话使用：四份任务书的取用方式与各会话开工令原文。
> 所有文件当前在分支 `claude/aneb-project-progress-analysis-x2wn7x`（PR #4）；本地树 `git fetch origin claude/aneb-project-progress-analysis-x2wn7x` 即得。

## 派发总表

| 单 | 任务书 | 属主会话 | 建议板号 | 硬前置 | 工期 |
|---|---|---|---|---|---|
| SPEC-1 需求基线与测试方案 v2.0 | `SPEC1_TASKBRIEF_BASELINE_TESTPLAN_20260828.md` | 20260711_ANEB测试方案_v1 | T79 | 无 | 2 工作日 |
| SPEC-2 设备与采集战线 | `SPEC2_TASKBRIEF_DEVICE_CAPTURE_20260828.md` | 20260715_ANEB系统开发_v2 | T80 | E-1 解锁（总前置） | 4–5 设备日 |
| SPEC-3 分析与报告战线 | `SPEC3_TASKBRIEF_ANALYSIS_REPORT_20260828.md` | 20260718_ANEB系统开发_v3 | T81 | 无（3.3/3.4 随数据） | 2 天 + 滚动 |
| SPEC-4 规格冻结与治理减负 | `SPEC4_TASKBRIEF_SPEC_GOVERNANCE_20260828.md` | 20260801_ANEB系统开发_v4 | T82 | 无（生效待 PO 批） | 3–4 天 + 演练 1 天 |

跨单时序：SPEC-4 的 4.2（portraits 三态论证）是 SPEC-1 裁项 B 的供稿，目标 D2 前交付；SPEC-3 的 3.3 挂 SPEC-2 语料到货触发；其余互相独立并行。

## 开工令原文（逐会话粘贴即可）

### → 20260711_ANEB测试方案_v1
【PO 派单 · SPEC-1《需求基线与测试方案 v2.0》】在本地树执行 `git fetch origin claude/aneb-project-progress-analysis-x2wn7x`，读该分支 `docs/SPEC1_TASKBRIEF_BASELINE_TESTPLAN_20260828.md`（背景：同分支 `docs/PROGRESS_DIAGNOSIS_AND_RESPEC_20260828.md`）。开工：①git status+分支确认；②任务板认领 T79 置 DOING；③按任务书 §3 执行，裁项一律留【PO-裁定占位】不预写结论；1.2 一页清最急先做。工期 2 个工作日，收工按板面纪律出 where-are-we 简报。

### → 20260715_ANEB系统开发_v2
【PO 派单 · SPEC-2《设备与采集战线》】在本地树执行 `git fetch origin claude/aneb-project-progress-analysis-x2wn7x`，读该分支 `docs/SPEC2_TASKBRIEF_DEVICE_CAPTURE_20260828.md`。开工：①git status+分支确认；②任务板认领 T80 置 DOING；③先核对 E-1（P40 是否已解锁）——未解则整单 BLOCKED_EXTERNAL 如实记板并转做 2.4 纸面核对（probe 时戳一行落没落），不空跑设备窗；已解则按 2.1 豆包先行批 → 2.5 UI 截图（搭车）→ 2.4 E1 窗顺序开工。本单进展度量=新增 run 数与覆盖，写简报首行。工期 4–5 设备日。

### → 20260718_ANEB系统开发_v3
【PO 派单 · SPEC-3《分析与报告战线》】在本地树执行 `git fetch origin claude/aneb-project-progress-analysis-x2wn7x`，读该分支 `docs/SPEC3_TASKBRIEF_ANALYSIS_REPORT_20260828.md`。开工：①git status+分支确认；②任务板认领 T81 置 DOING；③从 3.1 语料台账动手（进展的单一事实源），随后 3.2 verify_all 分层减负；3.1/3.2/3.5 零外部前置，不许被设备阻塞连坐；3.3 报告挂 v2 语料到货 T+1 触发。工期改造 2 天+随数据滚动。

### → 20260801_ANEB系统开发_v4
【PO 派单 · SPEC-4《规格冻结与治理减负》】在本地树执行 `git fetch origin claude/aneb-project-progress-analysis-x2wn7x`，读该分支 `docs/SPEC4_TASKBRIEF_SPEC_GOVERNANCE_20260828.md`。开工：①git status+分支确认；②任务板认领 T82 置 DOING（注明"树边界名单补丁在途（4.6）"）；③从 4.2 portraits 三态论证动手（SPEC-1 的一页清在等这份供稿，目标 D2 前交付），随后 4.1 aqs 冻结清单。治理类修订一律提案制，PO 批准前现行纪律照旧。工期 3–4 天+演练 1 天。

## 远程协调通道（PO 2026-08-28 批准，长期机制）

四单派发后的持续通信与进度管理走 `docs/coordination/`（本分支）：协议 `PROTOCOL.md`、点对点 `INBOX_V1..V4.md`、广播 `BROADCAST.md`、进度台账 `LEDGER.md`。各执行会话每次开工/收工 fetch 本分支查收；上行零新增动作（板面回执 + 每日 push 照旧）。协调会话每 4 小时巡检对账，>24h 无回执按协议升级 PO。

## 冲突与陈旧声明

任务书基于 C 树 GitHub 快照（提交至 2026-08-25）。若本地板面/决策日志已有更新与任务书冲突，以本地最新为准并报大脑仲裁；建议板号 T79–T82 撞号时按板面惯例后提交者改号。
