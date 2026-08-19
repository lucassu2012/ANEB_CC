# 端到端验收战役 · 压缩半天版 runbook（T60②，08-20 执行）

> 属主 v4（大脑代起草 08-19 傍晚，v4 醒后可增订）；执行=大脑或 v4（自动化链已全套验证）
> 目标：真实混合场景实证「产品在真实一天里能做什么」——四 Profile×两网络条件，当天出报告
> 纪律总则：每窗 DW 登记+哨兵+收窗复验（W-1）；蜂窝批逐轮记 RAT；caliber 逐轮核（语音）；临时设置记录并恢复

## 组合矩阵（压缩版，n 取 D-474 下限）

| 窗 | 网络 | 内容 | n | 备注 |
|---|---|---|---|---|
| W1 上午 | WiFi（记 SSID） | s1/s2/s3 quick run | 各 5 | autorun intent 或 UI GO |
| W1 上午 | WiFi | 语音回环 | 5 | `voice_batch2.sh wifi3 5` 复用 |
| W2 下午 | 蜂窝（svc wifi disable，记录+恢复） | s1/s2/s3 quick run | 各 5 | 逐轮 RAT（getprop） |
| W2 下午 | 蜂窝 | 语音回环 | 5 | `voice_batch2.sh cell2 5` |
| （条件项） | 双网络 | s4_throughput | 各 3-5 | **仅当 E-01 已部署 s4**（D-495 复核后定）；未部署则如实缺席并在报告点名 |

预计时长：W1 ≈2h、W2 ≈2h、报告 ≈1h。与 Codex 用机错峰：开窗前实况预检（他方进程/VPN/焦点），冲突即让。

## 驱动方式（两路径，优先 a）

a. **autorun intent**（MainActivity 保留 intent 解析+run 编排，T48 §1 实测在案）：`am start ... --es mode quick --es transport <auto|cellular>`——参数名开工前先读源核实，**不凭记忆**。
b. **UI 自动化**（全套已验证）：逐轮 dump 定位 GO（testTag，debug 包）+反馈证明+熔断（NO-FEEDBACK/TIMEOUT ≤3），复用 `voice_batch2.sh` 骨架。

## 当天报告链（管线已双证可复跑，D-512）

1. 拉库：`pull_device_corpus.py`（或 run-as 拉全库）→ 当日语料 JSONL
2. 标注：`annotate_campaign.py`（战役标签=acceptance_20260820；**D-494 并桶注意**：若语料混有旧时钟纪元时间戳，先并桶再分日）
3. 报告：`campaign_report.py <当日+全量> --html` + `publish_check.py`（FAIL 0 才可写结论）
4. 语音增量：新 10 轮并入 n=30 语料做分布复核（对照 D-510 分组统计，形状变化即报）
5. 归档 `evidence/acceptance_20260820/` + 台账 D 号 + 板面收工

## 判定口径（写进报告头）

- 本战役证明的是**可用性与诚实性**（跑得通、报得实、边界清），不是网络归因（RAT/忙闲仍未定，D-471；claim scope 照常）
- 任一窗失败≥3 轮：停窗如实记录，不硬凑 n
- s4 缺席/语音回落 v1 口径等任何缺口：报告正文点名，不静默
