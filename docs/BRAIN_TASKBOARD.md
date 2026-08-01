# C 树大脑任务板（属主：Fable 5 大脑会话）

> 执行会话（v2/v3）开工前先在此认领：状态置 DOING 填属主；收工置 DONE 填证据路径并输出 where-are-we 简报。状态词只用 TODO / DOING / DONE / BLOCKED。大脑对每个 DONE 有权抽查复核。
> 本板只管「谁在做什么」；技术裁定仍走 `DECISION_LOG.md`，PO 待决仍走 DECISION_REQUEST 文件，不在此复制。

*最后更新：2026-08-01 13:4x（属主调整：v2 今日上下文最热——D-373 v17 APK 出自其手，故设备侧 T1/T2 归 v2；v3 冷启动，接文档侧 T3。PO 已授权大脑直接指挥，指令经会话消息下达）*

## 今日任务（2026-08-01）

| ID | 任务 | 属主 | 状态 | 验收判据 | 证据 |
|---|---|---|---|---|---|
| T1 | **装 v17 APK + ≥14:00 下午 radio 批**（合并执行：先装 D-373 所产 debug APK 并核对构建对应提交，再跑下午批） | v2 | DOING | ① Room v16→17 实机迁移成功、`kpi_quality` 首次真实落盘且契约门放行；② radio 八字段齐备；③ 对 D-370 假设给出判定：下午窗 NR 是否回归、暖轮 RTT 是否回落至 ~53ms 量级（判定写入 DECISION_LOG） | evidence/ 待填 |
| T2 | **≥23:00 闲时 radio 批**（三时段无线图最后一块） | v2 | TODO | 闲时窗 radio 八字段 + CGNAT 出口 IP 记录；三时段（早高峰/下午/闲时）制式与 RTT 对照表落 DECISION_LOG，「闲时更差=制式差」链条闭合或明确否定 | evidence/ 待填 |
| T3 | **扩展轮设计提案**（D-353/D-372 尾巴）**〔大脑验收 PASS 2026-08-01：五判据全满足，溯源纪律到位；后续=T6〕** | v3 | DONE | n≥15 依 s1/s3 网络侧 CV 论证；s2 单列口径或放宽 MDE 二选一并给理由；点位真名留占位标注待 PO；产出=提案文档或 runbook 增补，不预写未测数字 | `docs/M3_EXPANSION_ROUND_PROPOSAL.md`（①n≥15 依 s1/s3 CV 5.5/5.9%、排除 s2 CV 承 D-372；②s2 取单列口径；③点位 `SZ-PILOT-01` 占位待 PO；④预热轮+1/格计入工时(D-366)、取证模式循环 3×3 拉丁方；⑤全数字标源+待测清单） |
| T4 | **步骤 B 悬置监控**（GLM 校准包 D-369 已交 G 树侧，等待消费；CalibrationMetadata 重启条件挂 G 树校验器/schema 入仓，见 D-359） | 大脑 | DOING | 每日只读检查 G 树有无消费/入仓迹象；3 天无动静升级 PO | — |
| T6 | **扩展轮执行就绪包**（承 T3 提案，大脑验收 T3=PASS 后续派） | v3 | DOING | ① runbook 扩展轮增补草案（n≥15、s2 单列 `SCENARIO_INTRINSIC_JITTER`、预热轮 D-366、3×3 拉丁方、radio+CGNAT 随采硬前置、点位真名 PENDING-PO）；② 按「quick 主体+取证子集」口径（大脑裁定方向，待 PO 确认）合成彩排全链路 synth→report→publish_check，验证 n=15/s2 单列形状不被现有守卫误拒（D-309 形状对账）；③ 守卫/渲染面差异清单（只列不改，零差异也要如实写） | evidence/+docs/ 待填 |
| T5 | **步骤 C：Profile 3 适配器规格先行**（豆包 + DeepSeek，PO 2026-08-01 批准增开 v4 承接） | v4 | DONE | ① 两 App 的打点事件定义（何为首帧响应/回答完成等）与外部观测方法规格；② 打点误差预算论证（M3 门=≤1 帧≈33ms，出处 SYSTEM_DEV_PLAN §6）；③ 画像参数采集口径与 [GUESS] 替换路径；④ App 改版/风控脆弱性风险与缓解各≥2 条；⑤ 规格阶段不碰设备，确需真机探索先报大脑排窗 | `spec/adapters/INSTRUMENTATION_SPEC.md` v0.1.0（①五锚点 A0–A4＋新命名 A0′，两 App 各自判据阶梯，**A4 回答完成当前零判据**故新设 C-1/C-2/C-3；②四通道 A/B/C/D＋兜底 E，**结论=不接通道 C（gfxinfo/SurfaceFlinger）则「≤1 帧」不可判**；③E_anchor⊕E_transport⊕E_quant⊕E_clock 四项仅末项有界→**M3 打点误差门当前 NOT_EXECUTED**，配 E1–E4 实验设计（E1 无需 P40）；④适配器只能翻 7 字段中的 `session_duration_s_dist`，且依赖 A4；⑤改版 4 条＋风控 4 条＋OEM 5 条。**未碰 P40、未新增任何实测数字**。八项待裁定见 §6，解阻关键=6-1 口径读法、6-5 通道 C 排窗）；`spec/adapters/README.md` 加入口指针；verify_all 13/13 PASS（`evidence/phase0/verify_all_20260801-140136.log`） |

设备注意（T1/T2 共用 P40）：照根 `CLAUDE.md` 实况流程；冷启动协议=每格丢弃预热轮（D-366）；关 WiFi 属临时设置须照原值恢复；logcat 实时落盘（环缓冲 256KiB 七分钟冲净）；无人值守遇驻留进程按「有活动服务=别人的会话，立即放弃」处理。

## 排队中（本周，待 T1–T3 收口后大脑排期）

- ~~步骤 C 规格先行~~ → 已提级为 T5（v4 承接，2026-08-01）
- 步骤 D：Profile 4 语音回环（依赖 T5 规格框架落定后排期）
- 步骤 E：M2 复跑准备（依赖扩展轮设计 + PO 点位真名）
- 未归属 token 观测批归档确认（等 PO，D-369）

## 警戒线

1. 若 `git log` 出现非本方新提交或工作树有不明改动：**停，报大脑**。背景：2026-08-01 有一条错误分工指令流出，G 树 `BRAIN_STATUS.md` 因此把本树三个线头错误记账为「移交 Codex」——若 Codex 依此进入本树会撞车。
2. ~~领先远端 353 提交未备份~~ **已解除**：PO 2026-08-01 批准推送，`dcd5046..e5cf0b9` 已上 origin（github.com/lucassu2012/ANEB_CC）。此后纪律：**每日收工提交后随手 push**（PO 已批准该方向）。
3. 两执行会话同刻只允许一个使用 P40。
