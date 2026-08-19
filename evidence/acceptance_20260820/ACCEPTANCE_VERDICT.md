# 端到端验收战役判定页（DW-20260820-01，大脑执行）

> 真实历 2026-08-20 上午｜runbook=`docs/T60_ACCEPTANCE_RUNBOOK_HALFDAY_20260819.md`｜claim scope=终端至仿真节点应用层端到端（照常，不外推运营商评级/MOS）

## 判定：本战役所证明的（可用性与诚实性，非网络归因）

1. **跑得通**：20/20 轮零失败零人工干预——quick run 10（WiFi 5+蜂窝 NR_SA 5，autorun intent 驱动，RUN_END status=completed 10/10）+ 语音回环 10（WiFi 5+蜂窝 5，caliber 10/10 server-sim v2 零回落）。单轮 ~2.5 分钟（quick）/~50 秒（语音）。
2. **报得实**：当日语料（10 run/新 DB 纪元）经 annotate→campaign_report→publish_check 全链，**发布门 FAIL 0**（首跑 FAIL 1=carrier 未标注，补实测标签后过——门在工作）。WARN 7 条随报告正文横幅交代。
3. **边界清**：s4_throughput 如实缺席（E-01 未部署，D-495）；出口混用 WARN 按 §10 分段呈现不池化；无线样本 stale 排除如实标注。

## 实况记录

- 窗口纪律：DW 登记（09a75d8）→哨兵→采集→WiFi 临时关闭已恢复复验（Transports: WIFI）→桌面焦点收尾。
- **DB 纪元切换事件**：08-19 装机冒烟 `adb uninstall` 清了 App 数据（Room 从 id=1 重计）——历史语音 35 行已提前归档（`voice30_voice_result_only.db`，a78506e）**零损失**；本战役语料即新纪元全量，天然干净。跨纪元计数时以 run_id（UUID 不重置）为准，勿用 local id。
- 过程修复一处：autorun extras 只在 onCreate 解析，重复 am start 走 onNewIntent 被忽略——批脚本改每轮 force-stop 冷启（首见 W1 轮 2/3 NO-START，修后 18/18 连续成功）。

## 产物

`acceptance_20260820_raw.jsonl`（10 run 原始）｜`acceptance_20260820_labeled.jsonl`（标注后，campaign_id/point_id/carrier/time_band）｜`acceptance_report.md/.html`（战役报告）｜`publish_check.md`（可发布，FAIL 0/WARN 7/N-A 6）｜`acceptance_20260820_pull_aneb-probe.db`（当日库快照，含 voice_result 10 行）
