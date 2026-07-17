# ANEB Probe — 开发交接文档（给 Codex）· 2026-07-14

> 目的：把 ANEB Probe 的设计、当前进展、**测量红线**、待办交接给 Codex 继续开发。
> **改任何东西前先读第 2 节（红线）与第 1 节权威文档；一切以仓库文档为准，勿凭记忆重述。**

---

## 0. 一句话
ANEB Probe = 测量"移动通信网络对 AI 智能体业务体验"的 **Android 取证级测量工具**（Kotlin/Compose 客户端 + Go 仿真服务端），核心产出 **AQS（Agent 体验分 0–100）**。当前主线：UI 换 **SpeedTest 式**（Claude Design v2 设计），指标内核已稳定对齐文档。仓库根：`E:\C Project\ANEB`。

## 1. 权威文档（改动前必读，一切以文档为准）
- `docs/ANEB Probe 开发设计文档.md` — 主设计文档（§11 = VpnService 流量观测设计，**未实施**）
- `docs/智能体互联网时代（Agentic Internet）移动通信网络的新型网络性能与体验诉求.md` — **§5 = agent-qoe-kpi v0.2.2**：指标定义/四级门限/AQS 权重/测量方法（指标一切以此为准）
- `docs/测量红队清单.md` — 33 项经对抗验证的测量失真风险 R-01..R-33（闭环追踪）
- `docs/DECISION_LOG.md` — 决策 D-01..D-25、否决记录、外部依赖 E-01..E-05
- `docs/参考_ChatGPT侧ANEB_AndroidEcho方案与进展_*.md` — 姊妹项目对齐

## 2. ⛔ 测量红线（绝不可破坏 — 这是取证工具，测量完整性 > 一切）
1. **claim scope 锁定**：AQS=`application_end_to_end_to_probe_node`（const 锁）；API 探针=`application_end_to_end_to_llm_api`；REACH=`application_reachability`。**禁止**表述为 MOS / 无线层 RTT / RAN 时延 / IP 层丢包 / 运营商全网评级 / SLA。
2. **R-10：缺失即 null，绝不顶 0**。失败/超时样本记 `null`，UI 显 "…"/"—"，**绝不用 0 或哨兵值**驱动任何可见几何（仪表指针/进度弧）或聚合。（本项目已因此修过一个 major：测试中半盘曾用 `aqsRunning ?: 0` 驱动指针→改由 `progress.fraction` 真实完成度驱动。）
3. **门限 / AQS 权重 / T4 否决 / 分档线已 100% 对齐文档 v0.2.2，不得擅改**。改分值=测量语义变更→须走 `DECISION_LOG` 新决策 + 红队复核 + 版本 bump。**单一事实源**：`scoring/AqsScorer.kt`（门限锚+权重+否决封顶54）、`scoring/KpiGrading.kt`（四级分级）、`ui/ResultFormat`/`ui/theme/Grade`（只映射不得重定义门限）。
4. **run 编排 / autorun intent / `engine.telemetry` 只读通道 / 各 KEY 日志（`>>> RUN`/`SCENARIO_KPI`/`AQS`/`RUN_END` 等）/ 落库口径逐字不动**。UI 重构只改展示层——`MainActivity.startRun()` 整段、engine/continuity/ab 调用、日志 KEY 内容不能被碰。
5. **key 安全**：API key 只进请求 header，出口（日志/入库/导出）全过 `ApiKeyRedactor`；绝不入日志/上报/导出/git。
6. **D-16 直连**：仿真测量客户端钉死 `Proxy.NO_PROXY`（API 探针例外——用户路径含代理属被测对象）。
7. seq-join 强制以 event 内嵌 `seq` 配对（禁数组位置）；fail-closed 三态有效性 `valid/valid_low_confidence/invalid`；批化检测在残差域分级不二值判无效。

## 3. 指标体系（已实现，勿重造）
`agent-qoe-kpi v0.2.2` 全部已在 `engine/`+`scoring/` 实现：
- **T 组（交互时延/流式）** T1 TTFT / T2 ITL P95 / T3 stall率(>200ms) / **T4 严重卡顿(>1s，一票否决>1%封顶54)** / T5 恢复时延(不进AQS)
- **U 组** U1 上行突发吞吐(1MB) / U2 工具循环P95；**C 组** C1 中断率 / C2 切换恢复(same/cross-network) / C3 NAT；**N 组** N1 RTT P50 / N2 抖动；**R 组** 无线快照(RSRP/SINR/制式)；**REACH** 握手可达性(候选)
- 四级门限 优/良/可/差（内锚 85/70/55 分段线性）；**AQS 权重** 流式55%(T1 20+T3 20+T2 15) / 上行25%(U1 15+U2 10) / 基线20%(N1 10+N2 10)，阶段二 C 组 ×0.8+20%
- 版本常量：`AqsScorer.AQS_VERSION="aqs-v0.1"`（**实为 v0.2 口径，待元数据修正为 v0.2.2 — 见 §6 additive TODO**）
- ⚠️ **审计结论（2026-07-14）**：现有实现门限/权重/否决/分档**已 100% 对齐文档 v0.2.2，无需校准**；"指标不专业"是呈现问题不是校准问题。

## 4. 仓库结构
- `app/probe/` — Android 客户端（Kotlin/Compose，minSdk29/target35/API31 P40，Room **v11**）
  - `engine/`（`TestEngine` 编排、`ContinuityRunner`、`AbRunner`）· `scoring/`（`AqsScorer`/`KpiGrading`/`ReportAnalyzer`）· `net/`（`AnebClient`/`ReachabilityProbe`/`SseReader`/`TimingEventListener`）· `radio/` · `data/`（Room）· `apiprobe/`（LLM 探针+`ProviderPresets`+`AiReachabilityProbe`）· `ui/`（Compose：`ui/theme`/`ui/components`/各 Screen/`MainActivity`）
- `server/` — Go 仿真服务端（TCP+H3 双栈；E-01=深圳阿里云 `120.79.148.0:8443`）
- `profiles/` 版本化剖面 · `evidence/` 各阶段验收证据 · `docs/` · `design_handoff_aneb_probe/`（Claude Design 交接：`tokens.css` 全组件 CSS + `screens/*.html` + `README.md`）

## 5. 当前进展（提交时间线）
| commit | 内容 |
|---|---|
| `c5c16c7` | **SpeedTest v2**：180°半盘指针表 `HalfGauge` + `SpeedTestComponents` 组件族 + 三主屏(home/testing/result简洁) + TabBar 测试/历史/设置 |
| `eb9ff2a` | SpeedTest 期1：底部 3-tab 壳（已被 v2 覆盖部分） |
| `1d09e70` | **SNI-RST 修复（D-25）**：默认 sslip.io SNI 被电信蜂窝 DPI RST→测量前探到 `sni=rst&&ip=ok` 自动切 bare-IP |
| `18a10f8` | item3 VpnService 裁定"暂不建"（D-24） |
| `5c45514` | item2：AI ①可达性看板(免key TLS 握手) + ②国内 AI 预置接入(9家：豆包/Kimi/千问/DeepSeek/GLM/混元/讯飞+⚠️文心/MiniMax) |
| `0a9b3ba` | item1：iOS 设计系统全 App 集成（P40 真机 11 图验证） |
- 阶段 0-3 全部推进至外部依赖边界；真机 P40 Pro（电信 5G SA n78）首测 **AQS≈89**。
- **构建状态**：`:probe:assembleDebug` BUILD SUCCESSFUL；`:probe:testDebugUnitTest` **346 tests / 0 failures**。

## 6. SpeedTest v2 重构 — 状态 + 待办（Codex 主要接续点）
**✅ 已完成（c5c16c7）**：`ui/components/HalfGauge.kt`（180°半盘：轨+进度弧+21刻度+5刻度数字+指针+hub，Canvas 绘制，几何见 handoff §7）；`ui/components/SpeedTestComponents.kt`（`StBanner`/`StStep`(连接→流式→上传)/`StLink`(你↔节点)/`StGraph`(实时吞吐折线)/`StResults`(结果大数字箭头行)/`AnebTabBar`(测试GO凸起/历史/设置)）；三主屏 `HomeScreen`/`TestingScreen`/`ResultScreen(简洁视图)`；可达性看板降为设置二级入口。

**⬜ 待办（下一批，沿用同套 v2 组件 + `design_handoff_aneb_probe/`）**：
1. **result-dev（专业视图）** ★优先：`ResultScreen` 的 `DetailedResultView` 换 v2 样式——全套 KPI（T/U/C/N）+ **AQS 子分真实"组→KPI→贡献分"展开**（当前是 grade 近似，需落库真实子分，动 Room schema）+ REACH 矩阵 + 每 KPI 门限微刻度。
2. **history（历史列表 v2）**：`.histrow` 样式（AQS 徽标+GradeChip+时间/模式/低置信）。
3. **server/node-select（节点选择）**：`.srvrow` 列表，对接 `serverUrl` 设置（含 bare-IP `120.79.148.0:8443` / sslip 切换）。
4. **settings（设置 v2）**：`.setgroup` 分组卡 + `.ios-toggle` 开关。
5. **share（分享成绩卡）**：`.sharecard` 离屏 Canvas 出图（复用 `ShareCard.kt`）。
6. **增量屏**：Map 路测（`GeoTrack`×AQS 着色，无 GMS 用 LocationManager）/ Scenario 场景专测（对话/编码/多模态）/ VPN 加速（占位置灰）。
7. **additive 指标项（独立 PR + 红队，勿混进 UI PR）**：C3 NAT 四级**展示**分级（不进 AQS）、REACH 候选矩阵 `{SNI×bare-IP×协议栈}` 成功率、版本串 `agent-qoe-kpi-v0.1→v0.2.2` 元数据修正。**这些不改任何现有分值**。

**v2 设计源**：Claude Design 项目「ANEB Probe 设计系统」的 `explore-speedtest`（180°半盘=已选方向 1c）。本地 `design_handoff_aneb_probe/tokens.css` 含**全部组件 CSS**（`.stbanner/.ststep/.stlink/.halfgauge/.hg-*/.stgraph/.stresults/.tabbar/.histrow/.srvrow/.setgroup/.ios-toggle/.sharecard`），`screens/*.html` + `README.md`（§4 逐屏构图 / §5 令牌 / §7 半盘几何）为视觉真相。**注意**：本地 handoff 目前是 v1（iOS 版），v2 在 Claude Design 项目里；v2 的 `tokens.css`（含半盘等全组件 CSS）已由本次开发读取并落进 Compose。

## 7. 环境 · 构建 · 坑（务必知道）
- 工具链在 `E:\tools`（JDK17=`E:\tools\jdk-17.0.19+10`、`android-sdk`、gradle）；`JAVA_HOME`/`ANDROID_HOME` User 级已设。Go 在 `C:\Program Files\Go\bin\go.exe`（`E:\tools\go` 的 zip 装坏了勿用）。
- **构建**（PowerShell）：`cd app; .\gradlew.bat :probe:assembleDebug :probe:testDebugUnitTest --% -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7897`（PS 下 `-D` 参数须用 `--%` 停止解析令牌，否则 tokenize 报错）。
- **真机 P40 Pro**（adb `8MY0221126002537`）：**现开启 `verifier_verify_adb_installs`（ICP 备案校验）**→adb 安装被导流 AppGallery 并因 app 未备案拒（`INSTALL_FAILED_ABORTED -115`）。**必须用户手动**用文件管理器点装（推 APK 到 `/sdcard/Download/`）或用户关该校验；`vibrator` 服务 adb 取不到、`shell_cmd` 通知静音。
- **Git Bash 调 adb**：`export MSYS_NO_PATHCONV=1` 防 `/data/local/tmp/...` 被 MSYS 改写成 Windows 路径。二进制拉文件用 Git Bash 重定向（PS `>` 会损坏）。
- **E-01 端点**：默认 `https://120-79-148-0.sslip.io:8443`（SNI 主机名）**在电信蜂窝被 DPI 注入 TLS RST**（R-33/D-22），已自动旁路 bare-IP `https://120.79.148.0:8443`（IP-SAN 自签证书，debug 版内置 `aneb_ip_ca` 信任锚）。PC 侧测 sslip https 用 Go/OpenSSL 栈（schannel 被杀）。
- **GateGuard hook**（ECC）：拦每个文件首次 Edit/Write 与首个 Bash，在文本呈 4 项事实后原样重试即过；批量编辑触发 LOOP/SCOPE WARNING 多为误报。PS 5.1 读无 BOM 含中文 .ps1 会乱码。
- **项目记忆**：`C:\Users\lucas\.claude\projects\E--C-Project-ANEB\memory\`（`MEMORY.md` 索引 + `aneb-project-decisions.md` + `aneb-speedtest-redesign.md`）。

## 8. 外部依赖门控（用户侧，非代码可解）
E-02 更多真机/地点回流（最高价值）· E-03 更多 API key · E-04 海外节点（**用户暂缓，先只国内**）· E-05 QoD · UDP 8443 已放行。

## 9. 给 Codex 的起手建议
1. 先读本文档 §2 红线 + §3 指标 + `docs/` 四份权威文档。
2. 续 **SpeedTest v2 §6 待办**：优先 result-dev（专业视图，信息密度最高）→ history → server/node-select → settings → share；additive 指标项单独走 PR + 红队。
3. **每屏改动跑 `assembleDebug + testDebugUnitTest`（346 基线）确保零回归**；一旦要动测量层（engine/scoring/门限/权重/claim scope/日志 KEY），**停下来问用户 + 走 DECISION_LOG**。
4. 真机验证需用户手动装 APK（§7 装机限制）。
