# 远程协调通道协议 v1.0（PO 2026-08-28 指令建立）

## 角色

- **远程协调会话**（云端，本协议维护者）：四单（T79–T82 / SPEC-1..4）进度管理、跨会话通信中转、PO 升级接口。定时巡检，7×24 可被唤醒。**不取代大脑会话**——本地技术仲裁、验收抽查仍归大脑；本通道补的是"跨端通信 + 进度台账 + PO 升级"。
- **执行会话** v1（测试方案）/ v2（设备采集）/ v3（分析报告）/ v4（规格治理）。

## 通道定义（全部走 git，无需任何新工具）

**下行（协调 → 执行）**：分支 `claude/aneb-project-progress-analysis-x2wn7x` 上的 `docs/coordination/`：
- `INBOX_V1.md` … `INBOX_V4.md`：点对点信件，每条带编号（M-V1-001 …）。
- `BROADCAST.md`：广播（全体可读），每条带编号（B-001 …）。

执行会话**每次开工与收工**各执行一次（只读，不检出不合并，对工作树零影响）：

```
git fetch origin claude/aneb-project-progress-analysis-x2wn7x
git show origin/claude/aneb-project-progress-analysis-x2wn7x:docs/coordination/INBOX_V<n>.md
git show origin/claude/aneb-project-progress-analysis-x2wn7x:docs/coordination/BROADCAST.md
```

**上行（执行 → 协调）**：**零新增动作**——沿用既有纪律即可：板面认领/回执/进度备注 + where-are-we 简报 + 每日收工 push。协调会话定时 fetch `origin/feat/result-dev-v2` 对账。急件（希望协调侧下个巡检优先处理）可在提交说明里加 `[@remote]` 标记，可选。

**已读约定**：板面回执或简报中引用信件编号（如"已阅 M-V2-001"）即视为送达；协调侧据此更新台账，不另设回执文件。

## 巡检节奏

协调会话每 4 小时自动巡检一次：fetch 双分支 → 对账 T79–T82 板面行与新提交 → 更新 `LEDGER.md` → 需要时写 INBOX/BROADCAST 并推送。无变化则只更新台账时间戳，不打扰任何人。

## 升级阶梯

- **L1**（默认）：INBOX 催办/解阻答复，等下次开工被读到。
- **L2**：某单 >24h 无板面回执且无提交 → 向 PO 升级（会话消息/推送），附一条可直接粘贴的催办令——PO 只需粘贴，不需组织语言。
- **L3**：需 PO 裁定的阻塞（8 项清单类）→ 汇入/引用决策请求一页清，向 PO 升级。

## 生效与安装

- 本协议经 PO 2026-08-28 指令建立。协调侧只写本分支，**永不直接提交执行会话的工作分支**（警戒线 1 照旧：执行分支上出现非本方提交仍应停下报大脑）。
- 板面头部指针一行由 SPEC-1 属主（v1）随 T79 认领时落入 `BRAIN_TASKBOARD.md`（见 INBOX_V1 M-V1-001），此后所有会话每次开工必读任务板即可看到本协议。
