# ANEB 项目全面评估（2026-09-05）——进展、代码级审读与可执行计划

> 评估时点：2026-09-05 07:00Z（北京时间 15:00）。评估对象：上游分支 `feat/result-dev-v2` 顶 `0687228`（2026-09-04 09:47 +0800，此后零提交）。
> 方法：九个镜头（Android 引擎／Android 适配·UI·数据／Go 服务端／PC 采集工具／分析脚本与门禁／规格契约／证据与语料／治理与进度／目标对齐）各由一名读者按 file:line 读代码与证据，再各由一名核查者逐条试图推翻；随后完整性批评与计划起草各一名；合计 20 个智能体、672 次工具调用、117 分钟。读者共提出 116 条发现，核查结果：**确认 88、限定 28、推翻 0**；核查者另补漏 26 条；数字指标 100 项复算，19 项被订正。本报告只采用确认与限定后的口径；被订正的数字一律用核查值。
> 全部测试在本评估的 Linux 鲜克隆上实跑（不是转述徽章）：Go `vet/build/test` 与 `-race` 全绿；tools 反例 e234 122/122、e1 85/85、e03 6/6；scripts 812/813（唯一红项为 `verify_all.ps1:479` 引用被 `.gitignore` 忽略的 `server/data/results`，环境依赖）；spec 109/109（需先装 `jsonschema`）；e234 突变审计 25/25 CAUGHT。
> 上次评审：[REVIEW_20260902.md](REVIEW_20260902.md)。本报告对其 §4 十二项逐一对账（§6）。

---

## 0. 一句话

**仪器与治理远远走在语料前面：三万行探针、六千行服务端、四万行工具与脚本，门禁 27 道全绿；但立项问题「豆包各功能对网络的诉求」至今零条受控形态数据，D-655 窗令下达后 52 小时一格未开，上游已静默 29 小时；同时语料记账在源头失真（12 条合成 demo 计入「真实 run 111」、真机 run 100% 低置信），T54 吞吐线的第一份真样本带着三处未修的口径缺陷落在仓外。** 项目不缺能力，缺的是「把设备时段花在主命题上」的排序，以及把已知的十几处 S 级缺陷在开窗前修掉。

最重要的三件事（顺序即优先级）：
1. **今日开窗，且窗前先修驱动器四件**（focus 守卫、docstring 空转、`-s serial`、引号转义，合计 ≤ 半天）；开窗由大脑自起草自开（D-655 已立授权链），不再串行在缺席的执行窗上。
2. **整形形态的段 B／段 C 干跑本周落仓**（PO 已裁解阻、装置已下载、提权已批），否则 T78 报告只能是「自然对照版」。
3. **语料与口径先诚实再扩采**：demo 出 real、台账重算（111→99）、低置信门槛入册、U3 改服务端权威口径 + 测量端点钉死 HTTP/1.1 + 构建指纹，之后才允许 T54 重复 5–10 run。

---

## 1. 数字面（全部可核，命令见附录 B）

| 维度 | 数值 | 说明 |
|---|---|---|
| 上游静默 | **≈29.2 h**（0687228 09-04 09:47 +0800 → 评估时点 07:00Z；本报告入分支时 11:50Z 已 ≈34 h） | 0902 评审记录的上一次静默为 46 h；两周内第二次超 24 h |
| D-655 窗令 → 首格 | **≈52.7 h，0 格** | T80 最后登记 DW-20260831-01；全 docs/ 无 DW-2026090x |
| 提交（08-28→09-04） | 686（非合并 653）；逐日 11/289/187/50/21/0/106/22 | 09-03 起 110 笔非合并，docs-only 80/110（73%），≤2 行 53/110，`board(` 前缀 49/110 |
| 触及代码的提交（09-02 起） | 27 笔 | 其中 app 8、tools 10（9 笔 e03）、scripts 10、server 0 |
| Kotlin（app/probe main） | 28,909 行；测量主链 14,306 行 | 单测 131 文件／932 `@Test`／16,135 行；网络层（AnebClient/ScenarioRunner.runStream/SseReader.readRaw）零单测 |
| Go（server/） | 2,241 生产 + 3,270 测试（97 个 Test 函数） | 自 08-22 导入后零提交；`go test -race` 手跑绿，门禁未带 `-race` |
| Python tools/ | 8,474 行（生产 4,855） | 213 条反例全绿；突变审计 25/25 CAUGHT（不含驱动器） |
| Python scripts/ | 33,515 行（生产 14,164） | 813 个测试函数；`campaign_report.py` 3,032 行含 595 行单函数；`publish_check.check` 670 行/158 分支 |
| spec/ + profiles/ | 6,065 行 | 自 08-30 14:08 起零提交 |
| 语料台账（落盘） | 真实 run **111** | 含 `evidence/phase3/demo_results.jsonl` 12 条合成 demo（`run_id demo-000…011`） |
| 语料（本评估复算，去重剔 demo） | 唯一 run 110 → 真机 **98**（PC 工作树含 server/data 为 99） | 低置信 **97/98**；forensic 49/50 低置信；无分 1；「10 条高置信 run」全部是合成 demo |
| 契约违规 | 40 条／110 记录，**全部来自 demo 文件** | 缺 `buffering` ×36 + `validity=degraded` ×4 |
| 观察通道目录（台账 §四） | DEVICE_REAL 24 | = wave0 14（含 VOID 4）+ wave1 2（含 VOID 1）+ t90 验证格 1 + 08-02/03 e1stimulus 7；豆包非 VOID 实格 **11**，可承载结论 **5** |
| e2 判词（wave0 12 份） | NOT_EXECUTED 7／FAIL 5／PASS 0 | wave1、t90 三目录 0 份判读产物 |
| 08-28 起设备在格采样时长 | **141 min**（wave0 115 + wave1 23 + t90 3） | 非 VOID 101 min；可承载结论 5 格 52 min；轮次 93 |
| 受控形态格／DeepSeek 格／F3-F4 上行字节 | **0／0／0** | 整形器段 A 已下载（D-697），段 B 派出 28 h 无回执 |
| D-703 首份 s4 valid 样本 | run `01a069f8`，d3 86.45／u3 75.03 Mbps | 归档仓外 `E:\tools\aneb-ctree\runs`；evidence 与台账零命中 |
| 裁定 D-655…D-704 | 50 条，均 **1,431** 字，最长 4,179，≤200 字 **0** 条 | 自我订正 30/50；主题：E-03 14、面册/守卫 11–12、盘满 7、s4 5–6、整形 4–6、T88 2–3 |
| 治理载体 | DECISION_LOG 1.54 MB／733 行；任务板 307 KB，T78 单行 54 KB，板头停在 08-01 | 面册 §4 一级条目 61→75（冻结令当日 +14） |
| 0902 计划 P0-1…P2-12 | 严格完成 2／部分 5／未动 4／PO 撤销 1 | 按 1／0.5 计 41%；P0 链 1.5/3；PO 五项亲裁 5/5 已答 |

---

## 2. 现状总览：目标、能力与关键路径

### 2.1 项目要回答什么

需求基线 v2.4（`docs/REQUIREMENTS_BASELINE_v2.0.md:30`）：Android 探针 + 仿真服务端，按业务 Profile 产出可复算、带诚实标注的 KPI/AQS，三条 claim scope，不外推为运营商评级。当前主交付是 PO 08-24 直派的 **T78「豆包各功能对网络的诉求」**（形态轴 WiFi／蜂窝／热点整形／netem，App 轴豆包→DeepSeek→Kimi→通义）。战役方案十单元中，D（多模态上行）被列为「最强迁移点」，证据源为通道 D。

### 2.2 能力矩阵（代码里真有 / 文档有代码无 / 都没有）

| 需求 | 状态 | 证据 |
|---|---|---|
| 三场景 token 体验 s1–s3（TTFT/ITL/卡顿/AQS） | ✅ 代码在、语料在 | `engine/TestEngine.kt`、`scoring/KpiCalculator.kt`、`scoring/AqsScorer.kt`；wire 真机 run 98 |
| s4 单流吞吐（U3/D3，RTT 主导度） | ✅ 代码在（C 树独有）、首样本 1（仓外） | `engine/RttDominanceGuard.kt`、`net/AnebClient.kt:575-679`；D-703 |
| 蜂窝／WiFi 显式绑定 + 无线上下文 | ✅ | `net/NetGuard.kt:142,240-251`；`radio/RadioCollector.kt` 1 Hz |
| 第三方 App 观察（通道 A 无障碍 / B 帧差 / C framestats） | ✅ 代码在；豆包 11 实格、DeepSeek 0 | `adapter/AnebAccessibilityService.kt`；`tools/e234/e234_collect.py` |
| 通道 D（PCAPdroid 上行字节） | ⚠ 文档有、已降可选；与 gnirehtet VPN 槽位互斥未验 | `B2_SHAPER_BUILD_SHEET_20260903.md:139,157` |
| 热点整形形态（gnirehtet + clumsy/WinDivert） | ⚠ 装置已下载（仓外），段 B/C 未跑，采集链无 tier 字段 | D-697；`tools/e234/e234_collect.py` grep `tier` 为 0 |
| netem／上下行限速档（膝点、悬崖） | ❌ 无 Linux 盒；clumsy 限速为丢包式非令牌桶，D-656① 裁「本批不覆盖」 | D-694①、D-696 |
| RCT／A4 回答完成判据（C/G 单元） | ❌ NOT_EXECUTED；驱动器的 `answer_complete` 是定时器不是观测 | `INSTRUMENTATION_SPEC.md:149-156`；`tools/e234/drive_cell.py:86-90,129-132` |
| 多流吞吐（D-587 #5「立即可跑」） | ❌ 零 run；能力全在 G 树侧（`NetworkSpeedEngine` + E-01 0.8.3） | `grep -rn parallel server/*.go` 仅注释 |
| Profile 4 语音 | ✅ 1,444 行 + 8 测试文件；v2 口径依赖 E-01 G 树的 `/api/v1/realtime-sim`，C 树 server 零实现 | `net/RealtimeSimSession.kt:18` |
| 语料契约门 + 台账 | ⚠ 门只校验 gitignored 2 条；台账鲜克隆不可复算 | `scripts/verify_all.ps1:471-497`；`corpus_ledger.py:38` |

### 2.3 关键路径（今天 → T78 有数据支撑的结论）

```
N1 无设备前置：驱动器四件 + 采集器通道 C 守卫 + 零事件轮分流      [TODO，≤1.5 天，无阻塞]
      ↓
N2 通道 A 在 .ctree 包上开回并功能验证（Bound 恰 1 + ADAPTER_EVT>0）  [BLOCKED：恢复命令只在人的记忆里，组件 id 已变]
      ↓
N4 新批次命题单 + 一句窗令（D-704②(b)）                              [TODO：串行在缺席的执行窗上]
      ↓
N5 基线窗：豆包 wifi_f6_b/cell_f6 + DeepSeek 四格（自然对照）        [TODO：无需整形无需提权]
      ↓                                   N3 E-2 提权窗 → 段 B 自环 → 段 C 设备命中 [BLOCKED on PO 开管理员窗 / v4 回执]
N7 语料台账诚实化（并行，无阻塞）              ↓
      ↓                                   N6 整形窗：豆包 F1/F6 × ≥3 档 × ≥2 格
N8 判读：e2/e3/e4 + k=20 并排 + 零事件轮单列      ↓
      ↓ ←───────────────────────────────────────┘
N9 T78 结论 v0.1（09-19）：可测单元 A/B/E/G(+I)；D/C/F/H 显名 NOT_MEASURABLE
```

诚实的 ETA：基线版结论最短 4 个工作日；整形版按实证节律（六天三窗、每窗 ≈2 h、可判格率 ≈0.7 格/h）10–15 天；段 C 若 VPN 互斥或转发路径命不中，再 +2 周。

### 2.4 阻塞树（谁能解）

- 根：D-655 格阵窗未开。
- 直接原因：D-704② 五步 0/5——①通道 A 未开回（`.ctree` 无障碍服务未启用）；②③执行窗前置复核与起草：执行窗 61bd2401 自 D-655 起 24.7 h 无动作，之后只有两笔一行提交；④大脑复签：大脑 09-04 09:47 后静默；⑤T80 登记：无人写。
- 上游 A：执行窗可用性（**PO 核实会话能否 resume，或改派大脑**）。
- 上游 B：大脑议程被 s4/E-01 血统支线（D-695…D-703 五条 16k 字）与面册/签核占满（**大脑自限**）。
- 上游 C：本地在线状态不可观测——git 分不清关机／停摆／未推送（**PO**）。
- 上游 D：新前置持续生成（P1a、TAG 后缀、双签）（**大脑一句豁免**）。
- 协调侧已发 M-B-010 三选一并推送 PO；四个上游里三个的解只在 PO 或大脑手上。

---

## 3. 各子系统代码级评估

每节先说它做什么与做得对的地方，再列经核查的缺陷。严重度：**high**＝让测量结论失真、让数据进不了语料池或让项目目标无法达成；medium＝明显返工／失效风险；low＝整洁度。「delta」列对照 0902 评审。路径均相对仓根。

### 3.1 Android 探针核心（engine / net / apiprobe / radio / scoring / 构建）

**架构一句话**：一次 run 从 `NetGuard.guardCheck` 拒 VPN → 按 `TransportMode` 绑网 → `/api/v1/profiles` 优先、assets 兜底 → 环境监控 + 1 Hz 无线采样 → 场景循环（QUICK 固定序／FORENSIC 3×3 拉丁方）→ `ScenarioRunner` 逐相位（clock_sync 20×、warmup 3、上传/下载字节对账、SSE 流一次 read 一次戳 8 KB）→ `KpiCalculator`（校正 ITL、门槛 echo10/tool8/upload3/ttft3/itl100/download3）→ Room v22 → s4 诊断分支 → `AqsScorer` aqs-v0.1 → `ResultReporter` 上报。C 树独有：`adaptive_download_window`/`adaptive_upload_window` 两相位（`engine/ProfileModels.kt:54,67-68`）。

**做得对的**：全链单调钟（`net/AnebClient.kt:870`、`net/TimingEventListener.kt:50`、`net/SseReader.kt:273`）；读线程零重活 + 合帧标记 + 解析线程分离（`SseReader.kt:127-149,263-293`）；fail-closed 取消链与无竞态场景门（`AnebClient.kt:850-868`、`engine/ScenarioGate.kt:35-47`）；R-10 null 语义贯穿（`KpiCalculator.kt:152-161`、`AqsScorer.kt:576-588`）；spec↔代码对拍成体系并把 spec/profiles 声明为 Gradle 测试输入（`SpecScoringParityTest` 5 条、`build.gradle.kts:178-193`）；供应链版本全钉死；T88 修复带突变审计并如实登记 SURVIVED。

| id | 级 | 发现（经核查） | 证据 | 修法 | 属主/量 | delta |
|---|---|---|---|---|---|---|
| L1-F2 | **high** | 低置信标结构性恒真：门槛 `MIN_TTFT/UPLOAD/DOWNLOAD_SAMPLES=3` 而 profile 每场景只有 1–2 个样本，取证遍聚合按 OR。真机唯一 run 低置信 97/98，forensic 49/50 | `scoring/KpiCalculator.kt:349-354,445-451,473,493,549-554`；`engine/AqsInputMapper.kt:183-193`；`profiles/s1..s3` 相位计数；D-466（08-04）已知 | 大脑二选一入册：(a) run 级聚合 Σ sampleCount 判；(b) profile 声明 expected_n；回放语料验证 forensic 比例下降；`RenderRedlineTest` 加反例。注：s4 的 U3/D3 按 spec §8.4.3 `sample_count=1, low_confidence=false`，不受此影响 | scoring + 大脑裁 / M | D-466 已知未修；T88 三面警示因此将常亮 |
| L1-F1 / S3-01 | **high**（S3 定级） | s4 **U3 上行 goodput 用本地 socket 写入量与本地末次写时戳**，丢弃 `/upload` 响应里的服务端权威 `bytes/chunk_us`（`resp.body?.close()`）；与同 app 的 U1「终点＝2xx 头」口径自相矛盾，正是服务端注释自己警告的假吞吐 | `net/AnebClient.kt:648-673`；`engine/ScenarioKpi.kt:192-203`；`server/handlers_upload.go:32-34,45-70`；`docs/PROFILE2_THROUGHPUT_PROBE_SPEC.md:231-238` | `uploadWindow` 解析 `UploadServerView`，bytes 取服务端、终点取响应头到达、慢启动用 `UploadAnalysis.estimateSlowStart(chunkUs…)`；`KpiCalculatorU3D3Test` 加「written>server bytes」夹具。D-703 首样本 excl(68.47)<incl(75.03) 与此相容但单次不能定因（与 S3-02 的 h2 解释互斥） | app lane / S | 新发现；uploadWindow 另建经 D-478 批准，但服务端对账要求未随之落地 |
| L1-F3 / S6-02 | medium | `kpi_set` 版本戳分叉：wire 写 v0.2（`TestEngine.kt:1129`），计算与锚点自称 v0.1（`KpiCalculator.kt:335`、`spec/scoring/anchors.yaml:10`），profiles s1–s3 v0.2、s4 v0.3；对拍守卫只盯 `AqsScorer.KPI_SET_VERSION` | `SpecScoringParityTest.kt:219` | 单一常量；parity 加 TestEngine 断言；`validate_profiles.py` 校 `profile.kpi_set` 属登记集；大脑裁 wire 值 | v2+v4 / S | 新发现 |
| L1-F4 | medium | 上报体无构建指纹：`versionCode=1/versionName=0.1.0-phase0` 数月不变，.ctree debug 包与 G 树包在语料同形；D-699「只认哈希/版本号」在语料里做不到 | `build.gradle.kts:15-26`；`engine/ResultReporter.kt:80-81`；`ui/MainActivity.kt:194-195`（DEBUG 门控 inject） | `buildConfigField GIT_SHA/BUILD_TYPE/APPLICATION_ID`；`run.build{}` additive 块；Room v23；分析侧对 debug∧inject 标 non_forensic | app lane / S | 新发现 |
| L1-F6 | medium | AUTO 传输模式下蜂窝 radio 块被 `transport=="cellular"` 字符串等值丢弃（AUTO 写 `auto(cellular)`），分析层却把它归为蜂窝；默认设置正是 AUTO | `engine/TestEngine.kt:451,583,1104-1115`；`ui/MainActivity.kt:92`；`scripts/campaign_common.py:683-690` | 抽 `isCellular(netSnap)` 两处统一；`ResultReporterRadioTest` 加 `auto(cellular)` 夹具 | app lane / S | 新发现（latent，语料 AUTO 场景暂全为 wifi） |
| L1-F7 / S3-05 | medium | profile 相位静默降级：`window_ms` 缺失 `coerceAtLeast(1)` 跑 1 ms 窗仍出值；未知 phase 只打 `PHASE_SKIP` 不进 INVALID；服务端 `json.Unmarshal` 不拒未知键、`/profiles` 再序列化剥字段（与 D-699④a 在 0.8.3 踩到的同型） | `engine/ScenarioRunner.kt:210,341-342,369-370`；`engine/ProfileModels.kt:54,93`；`server/profiles.go:147-149,177-182`；`scripts/validate_profiles.py:45-46` | 客户端 fail-closed（抛 ENGINE_ERROR、新增 `InvalidReason.PROFILE_UNSUPPORTED`）；服务端 `DisallowUnknownFields` + 原样下发 + 文件↔端点 DeepEqual 测试 | app + v2 / S | 新发现 |
| L1-F8 | medium | 网络层与计时公式零单测：无 MockWebServer；`AnebClient.stream` gap/尾截断、echo 公式、window underrun、TTFT 公式均无覆盖；Robolectric 已入仓（4.16.1）可直接测 `readRaw` | `grep -rln MockWebServer app/probe/src/test` 空；`SseReaderHardeningTest.kt:15-19` | 加 `okhttp3:mockwebserver:4.12.0`，四条路径各一测；TTFT 抽纯函数 | app lane / M | 新发现 |
| L1-missed | medium | U1 字节对账在 `serverView` 解析失败时 **fail-open**：2xx + 坏 JSON 仍以本地口径出 goodput | `engine/ScenarioRunner.kt:61-72`；`net/AnebClient.kt:420-424` | serverView==null 时 durationNanos 置 null（R-10），记 diagnostic | app lane / S | 新发现 |
| L1-F5 | low | TTFT 剥离项用名义 `sched_us` 而非实际 `pre_flush_us`；生产 profile 无注入/合帧时差异微秒级 | `engine/ScenarioRunner.kt:410-417`；`server/handlers_stream.go:129-152` | 并列双口径或抽纯函数加「服务端迟到 50 ms 主口径不变」测试 | app / S | 新发现（口径选择） |
| L1-F9/F10/F11 | low | echo t0 打在 enqueue 前含线程投递；合帧标记只覆盖同一次 8 KB read；D3 窗口起点含一个 RTT 零字节段（≈2.3%） | `net/AnebClient.kt:114-132,580-582`；`net/SseReader.kt:127-149,369` | 见各条 recommendation | app / S | 新发现 |
| L1-F12/F13 | low | T88 五件改对但 ShareCard 渲染守卫 M4 SURVIVED、HomeScreen M1 未验、真机屏验未做；.ctree 测量包为 debug 变体（DEBUG 门控开放 inject），后缀属性不校验前导点；debug NSC 的 LAN 锚不泄漏到 release | `ShareCardLowConfidenceTest.kt:19-44`；`src/debug/res/xml/network_security_config.xml:35-44` | `ShareCard.drawTo(Canvas)` 接缝；T54 下窗顺带屏验；语料标 build_type | v4 / S | 0902 M6 部分推进 |

### 3.2 Android 适配层（通道 A）、Room 数据层与 UI

**架构一句话**：`AnebAccessibilityService`（443 行）订阅 CONTENT/TEXT/STATE/CLICKED 四类事件，入口一次取 `elapsedRealtimeNanos`，DEBUG 门控逐事件打 `ADAPTER_EVT`（E2 通道 A 的唯一输入），5 s 节流打 `ADAPTER_OBS`，会话切换时经 `Channel(32, DROP_OLDEST)` 落 Room `adapter_obs`；规格来自 `spec/adapters/*.json` 的字节镜像。Room v22、13 实体、16 条显式迁移。对齐责任在 PC 侧（`tools/e234/e234_common.py` 的 `fit_wall_to_boot`/`clock_pin`）。

**做得对的**：「零 perform*」红线三层同源（KDoc、xml 无 `canPerformGestures`、`ObservationRedLineSourceScanTest` 源码扫描含自反例），生产源 grep 0 命中；不读不存文本（只计长度、DEBUG 门控、desc 截断 40）；R-10 在 `ObsStats` 落实（null 不折 0、30 s 上界）；迁移纪律与派生式注册表守卫（`MigrationRegistryTest`）；规格 loader 严格 JSON、坏文件整体回空。

| id | 级 | 发现 | 证据 | 修法 | 属主/量 | delta |
|---|---|---|---|---|---|---|
| L2-F3 | medium | 通道 A 在 0687228 时点**无启用与功能验证记录**：D-702 装 .ctree 后组件 id 变为 `com.aneb.probe.ctree/com.aneb.probe.adapter.AnebAccessibilityService`，D-703 只验 s4，D-704② 明言「通道 A 开回之后」；仓内无任何写 `enabled_accessibility_services` 的脚本，恢复靠人记 D-634 的两条 adb | D-702①、D-704②；`ui/SettingsScreen.kt:181-218` 只跳系统设置页 | 新增 `scripts/a11y_check.py`（只读）与 `a11y_recover.py --confirm`（写后 20 s 内 `ADAPTER_EVT>0` 才 PASS），并作 `e234_collect` 前置；注意 `settings put` 是整值覆盖，先 `get` 再决定追加/替换 | v3 + 大脑 / M | 0902 H4 已知未闭合（登记第二次归零） |
| L2-F2 | medium | 双包并存后 logcat TAG 同为 `AnebProbe`，采集（`logcat -s`）与解析（`parse_adapter_events`）都不看 pid：两服务同启即重复事件、cadence 塌向 0 而无门报错；现有防线只有流程卡 P1a 与 D-704④ 现态约束 | `adapter/AnebAccessibilityService.kt:372`；`tools/e234/e234_collect.py:278-283`；`tools/e1/e1_analyze.py:222,226-245` | TAG 由 `BuildConfig.APPLICATION_ID` 派生；`ADAPTER_EVT` 行加 `app=`；解析器断言单一 pid；采集前置 `dumpsys accessibility` Bound 恰 1 | v4 + v3 / M | 新发现（D-702 后） |
| L2-F1 + missed | medium | 74d424d 把默认 `transport=auto` 渲染成「网络未知」并用测试钉死；同文件 `NetworkLabel.forRun` 却显「自动」，历史页原样显 `auto`——三处三种陈述 | `ui/HomeScreen.kt:668-691,701`；`HomeLastRunLabelTest.kt:64-67`；`ui/routes/HomeRoutes.kt:31-34`（lastRun 不看 status） | 抽 `transportLabel()` 单点映射；测试改 auto→含「自动」；lastRun 过滤 status | v4 / S | 新发现（09-03 引入） |
| L2-F5/F6 + missed | medium | `adapter_obs.ttftClusterMs` 写入时 `cluster ?: density` 两口径择优合列且不记来源，实体 KDoc、历史页注释、判读侧「不可互换」三处互斥；README 的 STALE 降级策略运行时零调用者，也不记被测 App versionCode | `AnebAccessibilityService.kt:268`；`data/Entities.kt:738-739`；`ui/HistoryScreen.kt:92,342-349`；`adapter/AdapterSpec.kt:262-269`（`stalenessAgainst` 无调用） | v23 加 `ttftSource/ttftDensityMs/targetVersionCode`；订正三处注释；README 改「报告不门控」或实现二选一 | v4 / M | 新发现 |
| L2-missed | medium | `logAdapterEvent` KDoc 说「CONTENT/TEXT 不逐条打」，代码对每条 content 事件都打——按注释重构会静默切断 E2 通道 A 输入而单测仍绿 | `AnebAccessibilityService.kt:198,305` | 改 KDoc；加断言调用点存在 | v4 / S | 新发现 |
| L2-F4 | low | `ADAPTER_EVT` 只记回调入口 BOOTTIME，不记 `event.eventTime`；追加可量投递延迟分布（改进项） | `AnebAccessibilityService.kt:164`；`INSTRUMENTATION_SPEC.md:176-206` | 追加 `evt_up_ms` 字段，判读加 delivery_ms 分布；先真机核非 0 | v4+v3 / S | 新发现 |
| L2-F7/F12 | low | 只在「切到别的包」时落库，`onUnbind/onDestroy` 不入队；IME 包名只读一次；5 s 节流无定时器 | `AnebAccessibilityService.kt:147-150,213,220-231,338` | onUnbind 入队后 close；ContentObserver；Handler 定时 emit | v4 / S | 新发现 |
| L2-F8 + missed | low | 红线守卫 FORBIDDEN 缺 `dispatchGesture/GLOBAL_ACTION_`、xml 层无守卫；spec `observe_events` 两类 vs xml 四类 vs KDoc「三种」三份不同 | `ObservationRedLineSourceScanTest.kt:318-335`；`res/xml/accessibility_service_config.xml:10` | 补 FORBIDDEN 与 xml 断言；`validate_adapters.py` 加 R-observe | v4 / S | 新发现 |
| L2-F9/F11 | low | 历史页三种行与分享卡无渲染层测试；17 个 data 测试无一在真实 SQLite 上跑迁移（`MigrationTestHelper` 只在注释中出现） | `RenderRedlineTest.kt`（History 0 命中）；`MigrationV8Test.kt:10` | 复用已入仓的 Robolectric 加渲染与迁移执行测试 | v4 / M | 新发现 |
| L2-F10 | low | 「只有版本戳没有分数」的 TestRun 行是设计内五路之四；error 路径丢已算出的 AQS；`pull_device_corpus` 不按 status 过滤 | `engine/TestEngine.kt:121,139,182,744,757,879-921`；`data/Daos.kt:7-17` | catch 路径 copy(status)；拉取脚本按 status 前缀判有效 run | v4+v3 / S | 新发现 |

### 3.3 Go 仿真服务端（server/）

**架构一句话**：单包 Go 程序（go 1.25，唯一依赖 quic-go v0.60），9 条 `/api/v1/*` 路由（echo/profiles/stream/upload/download/artifact_stream/toolloop/results/serverinfo）；`/stream` 绝对时刻表 pacing、三列解耦滞后、故障注入受 `-allow-inject` 门控；TLS 按 SNI 分流 IP-SAN 证书，`-h3` 同端口 UDP 并行；`tcpinfo` 仅 Linux 且仅 `/stream` 尾部取一次累计重传。**自 08-22 导入后零提交**；E-01 线上是另一血统 0.8.3（D-695）。

**做得对的**：单调锚点时钟贯穿；能抓「攒缓冲」实现的实时性测试（`handlers_stream_test.go:508-593`）；配置面 fail-closed；结果合同硬校验 + 并发追加不交织；「不知道≠0」的 n/a 纪律；h3 用真 quic-go 进程内验证；仓内只有公钥证书；`go test -race` 无数据竞争。

| id | 级 | 发现 | 证据 | 修法 | 属主/量 | delta |
|---|---|---|---|---|---|---|
| S3-02 | **high** | TLS 下 Go 默认协商 **HTTP/2**（无 `TLSNextProto`/`Protocols` 限制），OkHttp 默认接受：T54 形态的 SSE/s4 实际走 h2（每流 1 MB 接收窗、DATA 分帧），客户端不记录协商协议，h1/h2 样本不可区分；服务端其实带 `X-Aneb-Proto` 证据头，只是客户端不记 | `server/main.go:122-129,157-159`；`server/tls.go:67`；`server/h3.go:24,34-36`；`net/AnebClient.kt:42-50`（无 `protocols()`）；`net/TimingEventListener.kt:80`（收到 protocol 未落库） | `srv.TLSNextProto = map[...]{}`（或 Go 1.24+ `srv.Protocols` 只 SetHTTP1）；`tls_test` 断言 `resp.Proto=="HTTP/1.1"`；客户端逐样本记 `response.protocol` 与 `X-Aneb-Proto`；E-01 侧 `curl --http2` 核一次以定历史语料回填范围 | v2 + v3 / S | 新发现（D-703 首次以 TLS 跑 T54 起实际存在） |
| S3-03 | medium | 两条 server 血统互不覆盖：C 树缺 `/api/v1/realtime-sim`（voice 依赖）与 0.8.3 独有端点/flag；E-01 缺 `WindowMs`——任一形态都跑不全 s1–s4 + voice | `server/main.go:35-43,57-71`；`net/RealtimeSimSession.kt:18`；D-695③⑤、D-699④a | 先出「功能并集表」，PO 裁二选一（不替换＝双形态分层禁合池；替换＝先移植 realtime-sim） | 大脑裁 / M | 部分已知 |
| S3-04 | medium | `scripts/deploy_server.ps1` 硬编码只装 s1/s2/s3（s4 留 /tmp）、只装 tls/ip 而 unit 依赖 tls/public 且 `-h3`、`gen_cert.sh` 输出路径与 unit 不一致；照跑会覆盖 0.8.3 血统 unit；若线上无 public 证书则 3 s 重启循环 | `deploy_server.ps1:53,81,83,87-88,95,110`；`server/aneb-server.service:10-12`；`scripts/gen_cert.sh:16,31` | 硬闸（远端 `/serverinfo` 非本血统即拒）、遍历 `/tmp/*.json`、补 public 段、`-WhatIf`；`.gitignore` 补 `server/certs/*_key.pem` | v2 / S | 新发现；D-695③ 禁令维持 |
| S3-06 | medium | 服务端自报身份只有常量 `aneb-server/0.1.0`，与 g3-g4-rc 血统的 exe 同串；无 VCS 修订、无 CHANGELOG | `server/main.go:15,51,144`；D-695②、D-701② | `debug.ReadBuildInfo` 写 `/serverinfo.vcs_revision`；`X-Aneb-Server` 追加哈希；升 0.2.0 | v2 / S | 新发现 |
| S3-07 | medium | `X-Aneb-Server` 路径劫持指纹在 app 的 HTTP 路径无消费者（仅 WS 路径校验） | `server/main.go:47-53`；app 仅 `RealtimeSimSession.kt:194,214` | `AnebClient` 校验前缀，缺失即 `path_hijack_suspect` 中止 | app / S | 新发现 |
| S3-08 | medium | s4 关键路径测试缺口：`/upload` 无 chunked 提前结束/413/断开/并发用例，`/download` 无取消/并发；无 h2-over-TLS 用例；门禁 `go test` 不带 `-race` | `handlers_upload_test.go`（仅 2 个 Test）；`verify_all.ps1:74` | 补五类用例；门禁改 `-race` | v2 / M | 新发现 |
| S3-09 | medium | T54 形态（Windows PC 跑 server）协变量退化：`retrans_total` 缺省、serverinfo 两项 n/a、无 `tcp_slow_start_after_idle=0` 等价物；与 E-01 Linux 样本合池需分层 | `server/tcpinfo_other.go:9`；`handlers_serverinfo.go:40-44,70-71` | 台账加 `server_goos/server_lineage/network_position` 三列并禁合池 | v3 / S | 新发现 |
| S3-missed | medium | 门禁只在 Windows 跑 `go test`：`tcpinfo_linux.go` 与「Linux 必有 retrans_total」分支从未进门，仓内无 CI；`retrans_total` 是连接累计值、无流首基线，h2 复用下混入其它请求；s4 两端都不在 REQUIRED 集合，版本漂移零告警 | `verify_all.ps1:66-74`；`server/tcpinfo_test.go:69-80`；`handlers_stream.go:244-252`；`profiles_test.go:40`；`ProfileModels.kt:91,107,114` | 加 Linux 侧 `go test -c` 执行步；summary 加 `retrans_start/delta`；profiles_test 与 `DIAGNOSTIC_IDS` 覆盖 s4 | v2/v4 / M | 新发现 |
| S3-10/11/12/13 | low | `/stream` 参数校验顺序与覆盖语义不一致；`/results` 无幂等键、按本地日期分桶；长连接端点无并发上限、`/toolloop` 睡眠不看 ctx；时钟不可注入、`tcpi_rtt` 已在结构体未导出；「防慢速 DoS」下限算术允许 11.6 天 | `handlers_stream.go:318,334-346,336,347-350`；`handlers_results.go:43,105`；`handlers_upload.go:119-122`；`clock.go:12-19` | 见各条 | v2 / S–M | 新发现 |

### 3.4 PC 侧采集／驱动／判读工具（tools/）

**架构一句话**：`e234_collect.py` 一格＝设备门（词边界匹配 T80 登记的 DW 号）→ `RUN_KIND.json` 第一个落盘 → E1 钉桩·前 → 三线程（logcat 泵入 `adapter.log`；`_dump_channel_c` 周期 `SurfaceFlinger --latency` + `gfxinfo framestats`，含 T90 图层自愈；`_sample_roi` 通道 B）→ 钉桩·后 → `collect_notes.json`。驱动器 `drive_cell(.py/_ds.py)` 固定坐标盲点 + `AnebE4MARK` 标记。判读 `e2_precheck`（三态前置 + 仪器分母）→ `e2/e3/e4_analyze`，门统一走 `GATE_MIN_N=5`。

**做得对的**：T90 图层自愈真机验过（139 次 dump 仅 6 段空窗，重挑 #2968→#2988）；判读侧有分母（`DUMP_SURVIVAL_FLOOR=0.95`）；共享常量读生产者不抄字面量（`CLUSTER_GAP_NANOS` 从 `ObsStats.kt` 正则取，取不到即抛）；dry-run 隔离是结构性的；判词词表分离；突变审计免疫「装置没跑起来」（1dd164c 教训写进代码）。

| id | 级 | 发现 | 证据 | 修法 | 属主/量 | delta |
|---|---|---|---|---|---|---|
| L4-F1 | **high** | 驱动器前台守卫 `focus_ok` 仍是整份 `dumpsys window` 子串：黑屏/后台可放行，`input tap` 落到别的 App 零报错，产出「表面完整」的空格；驱动器零测试 | `tools/e234/drive_cell.py:73-79`；`drive_cell_ds.py:75-81`；末次改动 b5cb4f3（09-01） | 解析 `mCurrentFocus` 包名精确等于 PKG 且 `dumpsys power` 含 `mWakefulness=Awake`；`sh` 可注入；三态夹具 | 61bd2401 / S | **0902 P0-2④ 已知未修** |
| L4-F2 | medium | `e1_io.pin_console_utf8()` 在两只驱动器里仍写在 `main()` 的 docstring 内（AST 零 Call）；D-650④ 仍记「九只工具编码自锁完成」 | `drive_cell.py:93-100`；`drive_cell_ds.py:95-102` | 移到 docstring 之后作首条语句；AST 断言 Call==1；D-650④ 出订正条 | 61bd2401/v3 / S | 0902 已知未修 |
| L4-F3 | medium | 通道 C 采集线程无异常守卫：一次 adb 超时（`Adb.text` 30/45 s）即线程静默死亡，`collect()` 照写 notes，`dump_survival` 看不见（issued 小而 survival=100%） | `e234_collect.py:385-425`（0 个 try/except），对照 `:466-468`；`tools/e1/e1_collect.py:131-134`；`e2_precheck.py:424-447` | 循环体 try/except 计数继续；acct 记 `t_first/t_last/cadence_s`；precheck 加 `sf_coverage` <0.9 ⚠ | v3 / S | 新发现 |
| L4-F4 + missed | medium | dump 实测节拍＝名义周期 + adb 往返（1.20–1.29 s，非 1 s），睡眠不减 dump 耗时；`--framestats-period-s` 默认 int **20** 与帮助文案矛盾（DW-02 首窗即因此 disjoint 9）；两只解析器只认 `sf_latency` 首行周期头，而 `11111111` 只出现在零帧 dump（死图层头），首段空窗的格整格按 11.1 ms/帧误判 | `e234_collect.py:421-424,501`；`e2_precheck.py:217-240,482`；`tools/e1/e1_analyze.py:354`；`evidence/e234/20260802-172614/sf_latency.txt`（5/5 段零帧） | 补偿式等待、默认 1.0、记实测节拍与 `refresh_period_ns` 分布；周期头取「首个含帧段」 | v3 / M | 0902 M5 部分已知；「P40 曾跑 90 Hz」为误读，撤回 |
| L4-F5 + missed | medium | e2/e3 把「零回答轮」并入「不足两簇」；`segment_turns` 零事件时误报 whole-run；`e2_precheck.channel_a_anchors` 把零事件轮计入「A 侧切不出次簇」——豆包限流/网络失败（恰是诉求最该记的事件）被当方法学缺口丢弃，DeepSeek P1 两种失败混成一种 | `e2_analyze.py:91-103`；`e3_analyze.py:132-137`；`e234_session.py:90-91,124-126`；`e2_precheck.py:346-349,398-404` | `if not ts: _drop('零事件')`；新增 `TURN_METHOD_NO_EVENTS`；precheck 分母分列 | v3 / S | 新发现 |
| L4-F6 | medium | 两只驱动器 148/154 行逐字重复；`sh()` 无 `-s serial`（多设备即空串→恒 STOP 且文案误导）；ds 版报错仍写「前台已不是豆包」；P2-10 合一零进展 | `drive_cell.py:69-71`；`drive_cell_ds.py:46-50,81` | 先四件双写；窗后 `--app {doubao,deepseek}` 合一复用 `e1_collect.Adb(serial)` | v3 / M | 0902 P2-10 未动 |
| L4-F7 | medium | D-615④ 的 k=20 相对门限至今零代码，「并排对照表」（P2-9）无工具承接；F1/F2 短答类「A 侧不足两簇」是 n 的主瓶颈 | `grep -rn 'k=20\|relative_gap' tools/ scripts/` 0 命中；`e234_common.py:65-78` | 新增 `gap_compare.py`（400 ms vs k∈{10,20,40}），对 12 格离线跑入判读页 | v3 / M | 0902 P2-9 未动 |
| L4-F8 | medium | 09-02 以来 tools/ 10 次提交 9 次落在 e03、1 次审计注释，采集主链/驱动器/分析器零提交；E-03 校的是 API 模式 ITL 语义，不直接服务 T78 | `git log --since=2026-09-02 --stat -- tools/` | 驱动器四件打成一个 ≤1 天提交；E-03 改名链挂装机批 | 大脑排期 / S | 恶化 |
| L4-missed | medium | 图层开跑时缺席则通道 C 整格 NOT_EXECUTED 且永不重挑——T90 自愈只覆盖「出过帧后死」 | `e234_collect.py:295-300,348-367,401` | layer 为 None 时循环内定时 `_relist_layer` | v3 / S | 新发现 |
| L4-F9…F14 | low | `--pin-through-session` 产物无人读；prompt 直接交设备 shell（引号/非 ASCII 静默失败，F5/F6 提示词从未被裁）；突变审计不覆盖 CLI 接线与线程循环；`glm_capture` 时戳是缓冲读出时刻；设备门文案「子串」与实现「词边界」不符；`sim_session.py` 带 BOM | 见各条 | 见各条 | v3 / S | 新发现 |

### 3.5 分析脚本流水线与 27 道门禁（scripts/）

**架构一句话**：wire 链 `validate_results`（从 schema 实时读规则）→ `campaign_common.load_records`（run_id 首见去重）→ `campaign_report`（入口自跑 contract_gate）→ `publish_check` 四态；观察链只在 `corpus_ledger` §四按 `RUN_KIND.json` 枚举三分类单列。`verify_all.ps1` 27 道门：server 3／spec 9+3／scripts 5+3（obs 枚举）／app 4，四态 + 幽灵检测 + `-Strict` 默认，末尾归档日志→徽章→sha256 清单。

**做得对的**：四态语义与幽灵检测把「没跑」与「跑过且过」在退出码上分开；obs 门枚举化 + 两层元守卫（文件差集、步名差集）把门层「真绿不在清单」结构性关闭并自证一次；徽章链闭合（点名日志真在 HEAD、清单排除 gitignored）；57 条属性测试对全部渲染器跑 20 个随机种子；0902 的 M6（台账未重算）与 D-700（点名日志漏 add -f）已修。

| id | 级 | 发现 | 证据 | 修法 | 属主/量 | delta |
|---|---|---|---|---|---|---|
| SP-F-01 | **high** | 12 条演示记录（`run_id demo-000…011`，`gen_demo_jsonl.py random.seed(42)`）被计入「真实 run 111」与徽章 `corpus_real_runs`，且是全语料**唯一**的 40 条契约违规来源；`is_synthetic` 只认 `synthetic` 块或 `SYNTH-` 前缀 | `scripts/campaign_common.py:588-596`；`corpus_ledger.py:261-267`；`docs/CORPUS_LEDGER.md:14,28,72`；`badges.txt:12`；本评估实跑 `validate_results.py demo_results.jsonl` → 40/12 | 给 demo 加 `synthetic` 块；`summarize` 后对 real 集跑 `validate_records` 非空即 `--check` 退 1；反例；重算并在 D 条写明 111→99 | v3 / S | 新发现（0902 §1 接受了 111 口径） |
| SP-F-02 | **high** | `results-contract-unit` 只校验 gitignored 的 `server/data/results`（2 条），已入库 110 条 wire 语料**从未过门**；鲜克隆必 NOT_EXECUTED → `-Strict` exit 1 | `verify_all.ps1:471-497`；`.gitignore:12`；09-04 归档日志 L377「2 record(s) across 2 file(s)」 | `corpus_ledger --list-corpus` 喂门；PASS 判词要求 ≥31 文件/≥99 记录 | v3 / S | 新发现 |
| SP-F-03 / F7-12 | medium | 台账与 `corpus-ledger-fresh` 门只能在 PC 复现：`DEFAULT_ROOTS` 含 gitignored 的 `server/data/results`，8 份合成 jsonl 被目录级 `.gitignore` 忽略；鲜克隆 `--check` RC=2，`--root evidence` RC=1 DRIFT | `corpus_ledger.py:38`；`evidence/m3_expansion_gen_20260801/.gitignore` | 大脑裁根策略三选一；验收＝鲜克隆 `--check` 退 0 | 大脑裁 + v3 / M | 新发现 |
| SP-F-04 | medium | `test_every_path_literal_in_verify_all_resolves` 把 gitignored 目录当必须存在，PC 以外必红，与它要防的 0x08 退格缺陷混为一谈 | `scripts/tests/test_docs_commands.py:1706-1739` | 判据加 `git check-ignore -q` 放行并显名 | v3 / S | 新发现 |
| SP-F-07 / S6-07 | medium | 观察通道（T78 主数据线）**没有自己的契约门**：合格判据只有 `RUN_KIND.json` 在场 + 两文件非空；坏行（wifi_f1_VOID2）只进「装载失败」不进 FAIL；spec 里无任何 schema | `corpus_ledger.py:166-213`；`grep -rn RUN_KIND spec/` 0 | `spec/schemas/obs-cell.schema.json` + `scripts/validate_obs.py` 接第 28 道门 | v3 + 大脑裁边界 / M | 新发现 |
| SP-missed | medium | 台账把 schema 枚举外的 `validity=degraded×4` 当普通桶印到「单一事实源」；28/111 无战役标签 run（12 demo + 16 netem/t39 排除件）计入 real 却不能出报告，台账没说它们是什么 | `corpus_ledger.py:270-298`；`docs/CORPUS_LEDGER.md:23-26` | `buckets` 对照 schema enum；加「可出报告 run」行与徽章 | v3 / S | 新发现 |
| SP-F-05 | medium | 三只脚本零测试，其中 `validate_voice_plan.py` 是活门（voice-plan-parity）却无红反例；`pull_device_corpus.py` 09-04 刚改无测试 | 引用统计 0 | 各补 0/1/2 三态反例 | v3 / M | 新发现 |
| SP-F-06 | medium | `publish_check.check` 670 行/158 分支、`write_csv_tables` 595/78、`render_summary_markdown` 495/136；重复 `import trust_rollup` | `campaign_report.py:515,1489,2146`；`publish_check.py:46-47,74,746` | 拆函数 + 「无函数 >250 行」ast 守卫 | v3 / L | 新发现 |
| SP-F-08/F-09/F-10/F-11/F-12 | low | 标签分布依赖文件名字典序（labelled 胜出仅因 'l'<'r'）；`run_all.py` 只捕 Exception（pytest.skip 是 BaseException）；`$skipped` 复用、`[switch]$Strict` 被覆盖、3 份 py 带 BOM；`scripts/README.md` 834 行中约 400 行是判读散文（08-28 起 42/85 提交只改 README）；`.gitattributes` 仍未落（D-647⑤/0902 P1-8） | 见各条 | 见各条 | v3 / S | F-11 为 0902 H3 具体形态；F-12 0902 已知未修 |

### 3.6 规格与契约（spec/、profiles/）——三端一致性

**架构一句话**：五类数据文件各有生产/消费三端：服务端 profile（仓根 `profiles/` 与 `spec/profiles/server/` 逐字节相同，app assets 直接取仓根）；结果上报体 `result-run.schema.json`（app `ResultReporter` 生产、server 只校 5 字段、scripts 从 schema 实时读规则）；打分规则 yaml 逐字导出自 `AqsScorer`（`SpecScoringParityTest` 反射对拍 + `check_versions.py` 双向咬合 + 值指纹）；画像 yaml 三层 + `check_redline` R1–R20；适配器 json ↔ assets 字节镜像、`validate_adapters.py` 从 `AdapterSpec.kt` DTO 派生规则。**spec/ 自 08-30 14:08 起零提交。**

**做得对的**：三份 profile 同源；adapters 形状门从消费方 DTO 派生而非手写；AQS 口径双向咬合 + 值指纹冻结；radio 四常量三份副本各有守卫；严格 loader 通则被实证并补反例（T84）；「新文件 + 新对拍」逃生口有先例（voice_realtime_plan）。

| id | 级 | 发现 | 证据 | 修法 | 属主/量 | delta |
|---|---|---|---|---|---|---|
| S6-01 + missed | medium | 裁项 B（PO 08-30 裁「正式放弃」）**6 天未施工**，`check_redline` 仍把两字段机器冻结在 PENDING-BY-CALIBER（8 处），按裁定改会被 R19d 判红；D-655…D-704 五十条零提及；板面 T82 把「施工」记成前一天无关的 D-583（R5b）——DONE 行记的是一个**假闭环** | `spec/portraits/check_redline.py:103,107-109,359-363`；四 yaml 各 2 处；`taskboard T82 行` | 大脑一句裁终态标签（复用 `N/A-BY-CALIBER` 或新增 `ABANDONED-BY-PO`）；v4 一次提交改守卫 + 四 yaml + R19d 反向；T82 订正补残项行 | v4 / S | 0902 P1-7 未动；M-V4-003 无回执 |
| S6-06 | medium | schema 的 `network_snapshot.radio` 块（`additionalProperties:false`、8 键必填）前门未接线（`validate_results` 对 radio 零处理）；`kpi_quality` 描述列 12 键而生产者已 16 键；server 合同校验比 schema 少 `run/scenarios` 两项必填；`:274` 注释仍称枚举大写 | `scripts/validate_results.py:158,227,243,253,274-277`；`spec/schemas/result-run.schema.json:8,126,207-222,227`；`server/handlers_results.go:33-58` | `load_schema` 抽 radio_spec 走 `_check_block`；描述改同源；server 补两项 | v3 + v2 / S | 新发现（radio 是 T78 判读首选协变量） |
| S6-08 + S3-missed | low | `run.profile_versions` 与 `version_mismatch` 只覆盖 s1–s3，s4 版本不入串；README 目录表也只列三者 | `ProfileModels.kt:91,113-114`；`ProfileRepository.kt:38-42`；`spec/README.md:71` | `versionString` 遍历全部 id；`DIAGNOSTIC_IDS` | v2 / S | 新发现 |
| S6-09 | low | 「发布即冻结、改动须升版本」只有声明无机器面（除 weights 值指纹）；08-30 画像语义改动（status PENDING→N/A）未升 `schema_version` | `git show ed02d88 -- spec/portraits/kimi.yaml`；`spec/README.md:41-46,60-63` | 加 `content_version` + 状态集合指纹守卫 | v4 / S | 新发现 |
| S6-03/04/05/10/11 | low | `CAMPAIGN_LABELS_WIRING_SPEC` S1–S4 三端从未落地（但 T78 走观察通道不受影响）；E-03 结论未回写 calibration 且 yaml 无代码消费方；`validate_profiles.PHASE_SPEC` 不认服务端已实现的 `artifact_stream`；DeepSeek 适配器 send_button 注记未同步；`INSTRUMENTATION_SPEC` 仍自标「DRAFT 未上机」而 tools/e234 已按它产出 24 个目录；README 目录表缺三个目录 | 见各条 | 见各条 | v2/v3/v4 / S | 新发现 |

### 3.7 证据与语料（evidence/、CORPUS_LEDGER）——数据到底有多少、能答什么

**架构一句话**：三条链——wire（探针→server→jsonl→`corpus_ledger`→台账→徽章→门）、观察（`e234_collect` 每格 `RUN_KIND.json` + 六种采样文件，四态只靠目录名 `_VOIDn` 与 README 散文）、API 对照（GLM `raw_sse.jsonl`，kind=api_cmp）。`evidence/README` 六条规则由 `check_evidence.py` 守 5 条，**sha256 清单（规则 3）不在守卫内**。

**做得对的**：格级产物齐整可独立复算（本评估用 `e2_precheck` 复跑 17 格与 README/T33 表逐格一致）；作废格保留且真被用上（cell_f2_VOID1 是驱动器版本翻转点的唯一证据）；自撤回/订正带日期写在证据包里；台账双链分离并同步到 09-03；GLM 12 组帧数/usage 可由原始字节逐字重算；判读侧对样本量克制。

| id | 级 | 发现 | 证据 | 修法 | 属主/量 | delta |
|---|---|---|---|---|---|---|
| F7-01 | **high** | T78 立项问题在数据上仍是**空矩阵**：可承载结论的格只有 F5×WiFi、F5×蜂窝、F6×WiFi、F6×蜂窝 + 1 个 F6 时段对照（各 n=6）；F1/F2 六格全 CANNOT_TELL；F3/F4 上行 0 字节；整形 0；DeepSeek 0；漂移锚 0。唯一像结论的「F5/F6 两条件不敏感」是在两档好网络之间比出来的 | `e2_precheck` 复跑 17 格 → WORTH_RUNNING 6（含 1 VOID）；`T78_…PROTOCOL.md:5,445`；`T33_…MATRIX.md:52,164`；`DOUBAO_WAVE0_JUDGMENT.md:14,25` | 台账 §四加「功能×形态×可承载判词」派生表，空格显式列出；下窗前置一格成功锚格 + 一格 F3（开通道 D） | v3 + 61bd2401 / M | 0902 H1 未修 |
| F7-02 + G8-missed | **high** | 台账「24 个观察格」把 VOID 5、验证格 1（t90）、08-02/03 e1stimulus 7 与豆包实格 11 混计；`RUN_KIND` 无 state 字段，`corpus_ledger.py` 无 VOID/verify 分支；D-655③「t90 立新 kind verify 不进观察格计数」裁了未施工（台账两次重算都没落）；7 格 e1stimulus 的 RUN_KIND 是 08-22 一并回填的，与表注「采集器自己写的标记」相反 | `docs/CORPUS_LEDGER.md:16,89,134,136,138`；`corpus_ledger.py:197-209,445`；`git log -S'RUN_KIND.json' | tail -1` → f507014 | `e234_collect` 收窗写 `RUN_KIND.state∈{valid,void,verify}+void_reason`；台账拆 `device_real_valid/void/verify` 三列；历史目录按后缀回填并在表注写明回填目录 | v3 + 61bd2401 / S | 新发现（0902 M6 只指出滞后） |
| F7-03 / F7-07 + missed | **high** | 判读页写死的**判决性实验**（dump 周期 20→1 后复跑同一格看 |t_A−t_C| 是否塌到帧级）所需数据 `wave1/wifi_f6` 已在仓 5 天无人算。本评估在副本上一键算出：**p99 = 28,440.6 ms（n=6）**，比周期 20 s 的 17,230 ms 更大——按判读页两分支只剩「语义事件说成立」，即 e2（通道 A 与 C 同帧）在豆包负载上**结构性不成立**，五格 FAIL 不是采集伪影 | `DOUBAO_WAVE0_JUDGMENT.md:145-146`；`evidence/wave1_20260831/wifi_f6/`（无 e2_result）；`e2_analyze --run-dir <副本> --pkg com.larus.nova` 输出 | v3 在仓内正式跑并落 `e2_result.json` + `DW_20260831_01_JUDGMENT.md`；命题单把 e2 从主命题降为不适用，改用通道 B 首跳变作旁证 | v3 / S（半天） | 0902 P1-8 已知未修；本评估补充：不只是补页，答案已在手 |
| F7-04 | **high** | 08-28 起 5 个战役证据包（wave0/wave1/t90/glm_e03/ui）**一律没有 sha256 清单**，phase0 清单 0 行涉及它们，`check_evidence.py` 不查规则 3 | `find evidence -iname 'sha256-manifest*'` → 仅 phase0–3；`verify_all.ps1:779-783` 写死 phase0 | `-Scope all` 对每个含 RUN_KIND 的日期包生成清单；`check_evidence` 新规则；一次性回填 | v4 + v3 / M | 新发现 |
| F7-05 / G8-07 | medium | D-703 首份 s4 valid 样本在仓外；口径互相矛盾：M-B-009 要 111→112，而 D-663(a)/T49 定 quick 单次＝诊断口径不进战役语料；台账里 acceptance_20260820 的 10 条 quick run 早已在池，说明该口径从未被执行 | `grep -rl 01a069f8 evidence` 0；D-703⑤⑥；`acceptance_20260820_raw.jsonl mode=quick ×10` | 大脑一句裁：入 evidence 存档 + `corpus_ledger` 加 `diagnostic_runs` 单列（不与 real 相加）；D-587 #5 已授权跑，不需 PO 再裁 | 大脑 → v3 / S | 新发现 |
| F7-06 | medium | 观察通道没有样本量判据：`N_SAMPLE_SIZE_BY_KPI_RAT` 只覆盖 wire KPI；F5/F6「无可辨差异」建立在 n=6+6、LOW 之上且无功效计算；cell_f5 可核/不可判 10:10 平局按字面过门 | `grep N_SAMPLE_SIZE tools/e234 docs/DOUBAO_WAVE0_JUDGMENT` 0；`BATCH_PROPOSITION_DW-NEXT.md:97,99,108` | 用现有 12 值 bootstrap，按 `required_n_at_power` 反推检出 10%/20% 差所需轮数写进文档新节；结论强制带「未达功效」句 | v3 / S | 新发现 |
| F7-08 | medium | GLM E-03 批（12 笔）对 T78 主命题贡献为零（命题单自认「装置/量法对照，不是网络测量」）；产出是探针内部命名修正（`arrivals` 实为内容帧到达，差额 ≈1.5%） | `BATCH_PROPOSITION_GLM_E03.md:218-222`；本评估独立解析 12 组帧数/usage 与 README 完全一致 | 进展声明归「探针量法校准」，不放 T78 下 | v3/v4 / S | 新发现 |
| F7-09 / GA-missed | medium | wave0 README「四功能×两条件已齐」与判读页「只有 F5/F6 可承载」并存；F1 提示词把「一句话」写进负载；**PO 简报首句「答案是不敏感」与判读页「本批不回答网络诉求」相反，六天未勘误** | `evidence/doubao_wave0_20260830/README.md:37,155`；`docs/PO_BRIEF_DOUBAO_CAMPAIGN_20260830.md:7` vs `DOUBAO_WAVE0_JUDGMENT.md:14` | README 改「各有 1 格落库，可承载仅 F5/F6」；简报顶部加勘误行；「范围外≠结论」入模板 | 61bd2401 + 大脑 / S | 新发现 |
| F7-missed | medium | `e2_result.json` 子块 `status=PASS`（样本量够）与顶层 `verdict=FAIL` 并存，按 `"PASS"` 计数会得 12/12 假阳性 | `tools/e234/e2_analyze.py:112-113` | 子块键改 `sample_ok`，verdict 只留顶层 | v3 / S | 新发现 |
| F7-10/11 | low | VOID 格 collect_notes 路径指向改名前目录（现指向有效格）；VOID2 第 83 行 5,792 字节 NUL 坏行；`check_evidence` 只查日期包，e1/e234 两个非日期包 7 个采集目录无 README、2 个无 RUN_KIND | 见各条 | 见各条 | 61bd2401 / v4 / S | 新发现 |

### 3.8 治理与进度——计划 vs 交付、节律、阻塞

**架构一句话**：五个载体（DECISION_LOG 单表追加、任务板四态词、审计面册、门禁/徽章/台账、窗件三件）+ 一条协调通道（本分支 `docs/coordination/`，L2 >24 h 无回执升级 PO）。契约：开窗先在 T80 登记 DW 号（采集器排窗门查板面）、命题单按新批次 ID 实例化且双签、收窗即重算台账。

**做得对的**：PO 裁定回路分钟级（B-008 → D-655 窗令 ≈20 分钟），E-03 单日闭环；08-29 以来第一条新 wire 真实 run（D-703）并推翻「防火墙挡入站」一月旧案（实为 PC WLAN 掉线）；T88 装机链在 PO 不在场下走通且不顶 G 树包；自审制度真在逮错（D-700 两 high、D-702 假阴性、D-703 前置断言）；闲置会话消化纸面件（cd5239ba 20 分钟交 P1-5 三笔）；协调通道 L2 有实效（M-B-007 → D-702 ≈3 h 45 m 大脑接管装机）。

| id | 级 | 发现 | 证据 | 修法 | 属主/量 | delta |
|---|---|---|---|---|---|---|
| G8-01 | **high** | D-655 格阵窗自窗令起 ≈52.7 h **零格**，T80 无新 DW，上游静默 ≈29 h（PO 09-03 原话「要一直保持推进状态」） | `grep -rhoE 'DW-2026090[1-9]' docs/` 空；T80 状态格 `PARTIAL_DONE`；`git log -1` | 大脑今日落 D-704② 五步（通道 A 开回→P40 实况→自起草新单写授权链→T80 登记→跑 P2 两腿）；任一步卡住即在 T80 写「阻塞＝X」 | 大脑 / M | H2 恶化：两周内第二次 24 h+ 静默 |
| G8-02 | **high** | 执行窗 61bd2401 自 D-655 起 24.7 h 无动作，之后仅两笔一行 docs（归属靠 D-704③ 转述）；三封 INBOX 无回执；而 D-704② 把新单起草与前置复核串在它身上——「装了不跑」 | `git show --stat 549b991 a14bb40`；`INBOX_V1.md:3-13` | 大脑按 D-655 授权链直接起草，复签换 v4；T80 属主改「大脑（61bd2401 出现则从格 1 接手）」；PO 核实会话能否 resume | 大脑 + PO / S | H2 未修 |
| G8-03 | **high** | 0902 §4 严格完成 2/12：P0-2 五件四件未动（全是 S 级：通道 A 验证、DeepSeek 试水、三处误导移交件、驱动器两处）；P0-3、P1-7、P2-9、P2-10 未动 | 逐项核（§6 表） | v3 已「转只读态」（D-685）却有空——派做 P0-2③④（<1 h，无设备） | v3 / S | 计划本身未执行 |
| G8-04 | **high** | 大脑对自己的闸门反向：D-655 只采纳 P1-4 一半（D 条不再以「入面册候选」作结，这条守住了），未采纳「零新增一级条目」——同日面册 §4 61→75（+14，9 条由 D-670 亲派）；裁定均 1,431 字、0 条 ≤200；09-03 08:00–14:00 六小时 37 条裁定 42.5k 字 + 106 提交，同时段数据线零动作 | `git show 104c934:docs/AUDIT_PLAYBOOK_v1.md` 61 → HEAD 75；`python3 len()` 统计 | 闸门做成机检：`test_playbook_frozen`（§4 ≤75 行）、`test_decision_length`（D-705 起 ≤200 字或含「证据包：」指针）、状态词守卫 | 大脑立规 + v4 / S | H3 恶化（均字数 1,000→1,431） |
| G8-05 / GA-F12 | **high** | PO 选了「解阻整形形态」，但设备侧零动作：段 A 下载完成（D-697，仓外），**段 B 09-04 08:48 派 v4 后 28 h 无任何可见回执**（产物只落 scratchpad，对 git 天然不可见）；段 C 三件（转发路径命中、VPN 互斥、时钟对齐）全未验；P40 侧 gnirehtet 装机与 VPN 授权（不需 E-2）未动；先行批协议「`ip route get` 走 wlan*」前置在 USB→PC→以太网形态下会失效 | T78 板面尾段（986a782）；`git log --since=09-04T09:00 | grep -iE 'clumsy|E-2|段 B'` 空；`B2_SHAPER_BUILD_SHEET.md:70-76,139,157` | 段 B 回执必须落仓 `evidence/b2_selfloop_<ts>/README.md`；设备侧 gnirehtet 干跑不等 E-2；整形批协议附录（前置改「tether 通 + 默认路由经 tun + PC 上行可控」）；`RUN_KIND` 加 `tier/shaper_effective/uplink` | v4 + 大脑/61bd2401 / M | H1 未修；P1-6 由 PO 裁定关闭但执行 0/2 |
| G8-06 | medium | D-655 自身连带承诺未兑现 4 件：M-B-002 对账、PR #4 并入（上游仍无 `docs/coordination/` 而板头引用它）、收工心跳行（最近 10 提交 0 命中）、T80 状态改实况 | `git ls-tree HEAD docs/coordination/` 空；`git log -10 --format=%B | grep -c '下次预计开工'` 0 | 心跳行做成软守卫（badges 单列）；PR #4 cherry-pick 一次；T80 改 DOING/BLOCKED 并写一行实况 | 大脑 / S | M8 部分未修 |
| G8-08 + missed | medium | 治理载体超出「开工必读」可读性：DECISION_LOG 1.54 MB/733 行无索引、任务板 307 KB、T78 单行 54 KB、板头停在 08-01；板自定四态词被 T80 `PARTIAL_DONE` 违反且无守卫；板面督导机制 L251 硬规则「任一执行会话空闲 >30 分钟必须派活或写明理由」被违反 24 h+ 而无一行落板 | `wc -c`；`docs/BRAIN_TASKBOARD.md:2-3,8,10,82,251` | 任务板拆活动/归档两文件；`scripts/decision_index.py` 生成 `DECISION_INDEX.md`；状态词与「会话 24 h 有实况」两条守卫 | 大脑 + v4 / M | 新发现（M6 结构性根因） |
| G8-09 | medium | 09-03/09-04 节律＝白天集中爆发后整段停机，爆发内容偏离关键路径（09-04 五条 s4/E-01 血统裁定 16k 字，格阵零条） | 小时分布 | 可机检排序规则：T80 存在「已裁未开」窗时，当日首笔提交须触及 T80 或 evidence/ 新格 | 大脑 / S | H3 形状再现 |
| G8-11/12/13/14 | low | P1-8 v3 五件只落 1/5 而 v3 闲置；P1-5 代做件卡在「候属主追认」；P2-12 多数未落；「27/27 绿」鲜克隆不可复现且依赖未声明（pytest/jsonschema） | 见各条 | 见各条 | v3/大脑 / S | 未修 |

### 3.9 目标对齐——代码与数据是否在回答项目要回答的问题

| id | 级 | 发现 | 证据 | 修法 | 属主/量 | delta |
|---|---|---|---|---|---|---|
| GA-F1 | **high** | T78 主命题至今零条受控形态格；D-655 P0-1(4) 把下一窗定为 P2 两腿 + DeepSeek 四格（仍是可观测性题），整形设备侧段 C 明写「窗后」 | D-655；`DOUBAO_WAVE0_JUDGMENT.md:14` | 段 B + 段 C 第一件并入下窗前置 P0；格阵第一格改批 A 的 F1×lat200×5 轮作整形链冒烟 | 大脑改窗令 / M | H1 未修 |
| GA-F2 | **high** | 战役「最强迁移点」D 单元（F3/F4 上行 + 限速档）在能力链上断三处；应显式登记「本战役回答 A/B/E/G(cadence-only)/I；不答 D/F/H；C/J 弱化」，否则「没有膝点数据」会被读成「没有膝点」 | `DOUBAO_NETPERF_CAMPAIGN_PLAN.md:36-46,184`；`B2_…:89-90,125-131,212-220,240-242`；D-694① | 在 T78 目标句下登记可答单元并配 D 号；裁 D-696 保底 (d)；F3/F4 先用陪跑模式验 UI 导航 | 大脑→PO / S | 新发现 |
| GA-F3 + missed | **high** | 批 G/C 依赖的 RCT/A4 判据与 E4 标定全 NOT_EXECUTED；**驱动器的 `answer_complete` 是固定等秒的定时器不是观测**，与人工按 `a` 的标记同名同格式，`e4_analyze` 对其不设防——拿它标定 T_quiet 是自证循环 | `INSTRUMENTATION_SPEC.md:149-156,374-383`；`tools/e234/drive_cell.py:86-90,129-132`；`e4_analyze.py:16-19`；cell_f1 adapter.log 含 8 条 | 驱动器发标改 `answer_wait_elapsed`（或 `source=timer`），判读一律按无标记处理；整形批 F2 轮由操作者打真标记 | 61bd2401 + v3 / S | 新发现 |
| GA-F4 | **high** | 三条血统并存：设备默认包＝G 树 g3-g4-rc、E-01＝0.8.3、C 树 .ctree 并存装机；s4 首样本仓外不进台账；两包同 TAG、组件 id 随包名变 | D-699/701/702/703；`a14bb40` P1a | 见 3.1 L1-F4、3.2 L2-F2、3.7 F7-05 | 大脑/v3/app / S | 新发现 |
| GA-F5 | medium | 09-03/04 编队工时主要流向与主命题无关的线：E-03 14–18 条裁定、面册/元守卫 11–12、盘满 7；直接推进整形链约 6 条 | 主题分类 | 下 10 条裁定 ≤200 字；E-03 只留改名链；面册零新增直到整形批出首格 | 大脑 / S | H3 局部恶化 |
| GA-F9 | medium | 「唯一现行需求源」自身过期：总计划 #3/#4 外场行与 §5「等 Codex 部署 s4」仍按可执行行印出；基线四处「代回填待属主追认」、版本停 v2.4 | `TEST_MASTER_PLAN_v2.0.md:17-18,162`；`REQUIREMENTS_BASELINE_v2.0.md:3,69,79,89,130,179` | 划线注 D-587；§5 改「我方自办（D-703）」；追认并升 v3.0 | cd5239ba / 61bd2401 / S | P1-5 部分完成 |
| GA-F10 | medium | 多流吞吐（D-587 #5「立即可跑」）零 run，能力全在 G 树侧；与 T78 无关，混入报告会被读成豆包吞吐诉求 | `grep -rn parallel server/*.go` 仅注释 | 二选一入册：降级「非 T78 路径」或与 T54 同窗顺带跑并标口径 | 大脑 / S | M6 未修 |
| GA-F6/F7/F11/F13 | low–medium | 语料零增两日以上（可判格仍 4–5）；窗产能≈0.7 可判格/h 与在场节律是 ETA 主导变量；Profile 4 与 T78 无交集应在报告范围声明「不含」；鲜克隆两处环境依赖 | 见各条 | 见各条 | v3/大脑 / S | 已知 |

---

## 4. 做得好的（跨镜头，全部经核查）

1. **测量骨架是对的**：全链单调钟、读线程零重活、fail-closed 取消、R-10 null 语义、U1/D1 字节对账、spec↔代码对拍成体系，服务端单调锚点 + 绝对时刻表 pacing + `-race` 无竞争。这些是别的团队常常做错的地方，这里没错。
2. **红线机器化**：通道 A「零 perform*」三层同源 + 源码扫描守卫自带反例；e03 抓取器「不解析、key 不落盘」做在结构上；严格 loader 通则补了反例（T84）。
3. **门禁的语义纪律**：四态（PASS/FAIL/NOT_EXECUTED/SKIPPED_SCOPE）+ 幽灵检测 + 元守卫两层差集，把门层「真绿只是不在清单上」结构性关闭，且当场自证过一次（12d63dd→bc85fc6）。
4. **工具链反例与突变审计**：213 条反例、25/25 CAUGHT、突变审计免疫「装置没跑起来」；T90 图层自愈是真机验过的可归因修法；判读侧补上了仪器分母。
5. **证据包的诚实**：自撤回/订正带日期写在包里（FINDINGS_RAW §0 总撤回）、作废格保留并真被用上、GLM 数据可由原始字节逐字重算、判读对样本量克制（「n=6+6 任何显著性判词都会比数据强」）。
6. **裁定回路与自审**：PO 裁定 20 分钟进窗令；E-03 单日闭环；T88 装机 PO 不在场走通且不顶 G 树包；D-700/D-702/D-703 的自审真逮到错；30/50 条裁定含订正——这是纪律真在运转的证据，不是教义。
7. **T54 首链跑通推翻一月旧案**：「防火墙挡入站」实为 PC WLAN 掉线；C 树探针经真 WiFi + TLS 对接 PC 端 C 树 server 拿到首份 s4 valid 样本（主导度 43 ≫ 15）。
8. **协调通道有实效**：L2 升级（M-B-007）到大脑接管装机（D-702）3 h 45 m；PO 五项亲裁 5/5 已答；闲置会话被用来消化纸面件。
9. **供应链与密钥卫生**：Gradle 全版本钉死 + wrapper sha256；仓内只有公钥证书；整形器下载做了双源 sha256 锚定并如实登记「本体无外部锚」。

---

## 5. 不足（按严重度归并；细节见 §3 各表）

**High（10 条）**
- **H1 主命题零受控数据，窗令后零格，上游静默 29 h**（G8-01/02、GA-F1、F7-01）。装了不跑：关键路径串行在缺席的执行窗上，大脑议程被 s4 支线与面册占满。
- **H2 语料记账源头失真**：12 条合成 demo 计入「真实 run 111」且是唯一契约违规源；真机 run 100% 低置信（门槛 3 vs 样本 1–2，OR 聚合）；契约门只校验 gitignored 2 条；台账鲜克隆不可复算（SP-F-01/02/03、L1-F2、F7-12）。
- **H3 T54/s4 口径缺陷未修先采**：U3 本地写口径丢服务端 bytes；TLS 默认 h2 不记协议；上报体无构建指纹；首样本仓外且口径互相矛盾（S3-01/02、L1-F1/F4、F7-05）。D-703⑥「同链路重复 5–10 run」若照做，会把三处混杂一起烙进语料。
- **H4 观察通道计数口径失真**：台账 24 格 = 实格 11 + VOID 5 + 验证 1 + 回填 7；D-655③ verify kind 裁了未落（F7-02）。
- **H5 判决性实验数据在仓 5 天未算**：wave1/wifi_f6 e2 p99 = 28.4 s（周期 1 s），e2 命题在现装置结构性不成立，应据此收口而非再等（F7-03/07）。
- **H6 驱动器三缺陷 0902 点名后未修 + 通道 C 线程无守卫 + 零回答轮混判**（L4-F1/F2/F3/F5/F6）：下窗一开就带着已知的假零风险。
- **H7 战役 D/C/G 单元能力链断裂**：F3/F4 上行 0 字节、限速档不覆盖、RCT/E4 未标定且驱动器标记是定时器（GA-F2/F3）；不显式登记就会被读成「豆包对上行不敏感」。
- **H8 整形线设备侧零动作、段 B 无回执**（G8-05、GA-F12）。
- **H9 治理复发**：裁定均 1,431 字、面册冻结当日 +14、板面自定规则被违反、载体不可读（G8-04/08/09、GA-F5）。
- **H10 战役证据包无 sha256 清单且守卫不查**（F7-04）。

**Medium（择要）**：双包同 TAG 无 pid 过滤（L2-F2）；通道 A 未开回、无恢复脚本（L2-F3）；首屏 auto→「未知」被测试固化（L2-F1）；adapter_obs 两口径合列（L2-F5/F6）；kpi_set 三处不一（L1-F3/S6-02）；AUTO 蜂窝丢 radio（L1-F6）；相位静默降级两端（L1-F7/S3-05）；网络层零单测（L1-F8）；U1 对账 fail-open（L1-missed）；server 血统不可追溯、两血统互不覆盖、部署脚本危险（S3-03/04/06）；X-Aneb-Server 无消费者（S3-07）；s4 测试缺口与 Linux 门禁缺席（S3-08/missed）；T54 Windows 协变量退化（S3-09）；dump 节拍/默认 20 s/周期头首行（L4-F4+missed）；k=20 无工具（L4-F7）；E-03 占用工具时段（L4-F8）；裁项 B 6 天未施工 + T82 假闭环（S6-01）；radio 块前门未接线（S6-06）；观察通道无 schema/无契约门（S6-07/SP-F-07）；观察通道无样本量判据（F7-06）；PO 简报首句与判读页相反（GA-missed）；三脚本零测试、超长函数、.gitattributes 未落（SP-F-05/06/12）；总计划/基线过期（GA-F9）；多流吞吐零 run（GA-F10）；D-655 连带承诺 4 件未兑现（G8-06）。

**Low**：见 §3 各表末行。

---

## 6. 上次评审（0902）计划执行对账

| 项 | 内容 | 现状 | 证据 |
|---|---|---|---|
| P0-1 | 一句窗令 | **已完成**（D-655，09-03 08:20，PO 答复后 ≈20 分钟） | D-655 |
| P0-2 | 复工前置五件 | **部分 1/5**：⑤台账重算已做（3552986）；①通道 A 验证未做（D-702「未启动 App」）；②DeepSeek 试水未做；③三处误导移交件原样（速查卡 L50/L95、wave1 README L245「ds 尚未创建」）；④驱动器两处未动 | 本评估 grep |
| P0-3 | 跑窗 | **未动**：无 DW-2026090x | `grep -rhoE` 空 |
| P1-4 | 大脑先对自己落刀 | **部分**：狭义（不再以「入面册候选」作结）守住；广义（折叠后零新增）反向 61→75；CLAUDE.md 无「记账/200 字」 | §3.8 |
| P1-5 | SPEC-1 基线回填 | **已完成（代做）**：cd5239ba 三笔；追认未落，版本未升 | 463a077/bf1b640/c27b49e |
| P1-6 | 「网络诉求」前置 PO 二选一 | **PO 已裁**（解阻整形）；执行 0/2 | D-655② |
| P1-7 | 裁项 B 施工 | **未动**（8 处 PENDING-BY-CALIBER） | §3.6 |
| P1-8 | v3 五件无设备件 | **部分 1/5**：台账归档已做；依赖格映射追认、T+1 判读页、.gitattributes、t90 README 句未做 | §3.8 G8-11 |
| P2-9 | k=20 并排复算 | **未动** | L4-F7 |
| P2-10 | 驱动器合一 | **未动** | L4-F6 |
| P2-11 | 作息与心跳 | **PO 撤销作息窗**；心跳行 D-655 立而未执行（0 命中） | G8-06 |
| P2-12 | 协调通道 v1.1 | **部分**：协调侧自改已做；PR #4 未并、「INBOX 已阅」0 行、M-B-002 未对账 | G8-13 |
| §5 五项 PO 亲裁 | | **5/5 已答**（09-03） | REVIEW_20260902 §7 |

完成率：严格 2/12，按 1/0.5 计 41%；P0 链 1.5/3。**结论：裁定链通、执行链断**——PO 与大脑的裁定当天落地，交给执行会话和「无设备件」的部分几乎全部停在原地。

---

## 7. 可执行计划

### 7.0 四条排序原则（本计划全部据此）

1. **以格计功**：只要 T80 存在「已裁未开」的窗，当日第一笔提交必须触及 T80 行或 evidence/ 新格；裁定、面册、签核一律排在其后。
2. **先修再采**：驱动器四件（A-1）与通道 C 守卫（A-2）合入前不开观察窗；U3/协议/构建指纹三件（A-7）合入前不做 T54 重复采样——现在采的每一条都要事后打「口径不同、禁合池」标签。
3. **大脑自开窗**：D-655 已立「代签须写授权链并留追认位」，新单起草与开窗不再串行在缺席的执行窗上；61bd2401 出现则从格 1 接手。
4. **无设备件不等设备**：A-3/A-4/B-3…B-10 全部不需要 P40，派给闲置的 v3/v4 立即做。

属主用编队 id：大脑＝Fable 5 大脑会话；61bd2401＝执行窗（local_85fe7be8）；v3＝local_b1769d1f；v4＝local_00236200；PO＝只裁不做。

### 7.1 今日／48 小时内（至 09-07 05:00Z）

| id | 项 | 属主/量 | 步骤（可直接执行） | 验收（可机检） |
|---|---|---|---|---|
| **A-0** | **落 D-704② 五步并开窗跑 P2 两腿** | 大脑 / M（≤3 h 设备） | ①`settings get secure enabled_accessibility_services` 后按需 put `com.aneb.probe.ctree/com.aneb.probe.adapter.AnebAccessibilityService`（整值覆盖，先看清是否要保留 G 树项）；开豆包核 `ADAPTER_EVT>0` 与 `dumpsys power` 含 `mWakefulness=Awake`；②P40 五步实况 + P1a（`ps -A | grep aneb` 恰一行）；③按 D-704②(b) 以新批次 ID 复制命题单，主命题只减不增，写授权链，复签换 v4；④T80 先登记 `DW-2026090X-01`；⑤`e234_collect --framestats-period-s 1` 跑豆包 wifi_f6_b→cell_f6；收窗即重算台账。**前提：A-1 已合入并把新哈希写进窗令 P3；若 A-1 未合入则本项顺延 ≤ 半天，不硬开** | `grep -oE 'DW-2026090[5-9]-01' docs/BRAIN_TASKBOARD.md` 非空；`ls evidence/<新目录>/*/RUN_KIND.json | wc -l ≥2`；两格 `e2_precheck` 为 WORTH_RUNNING；任一步卡住则 T80 写「阻塞＝X」 |
| **A-1** | **驱动器四件一提交**（窗前硬前置，不含合一） | 61bd2401（缺席则 v3）/ S（≤0.5 天） | `drive_cell.py`/`drive_cell_ds.py`：`e1_io.pin_console_utf8()` 移出 docstring 作 `main()` 首条语句；`focus_ok()` 改 `re.search(r'mCurrentFocus=Window\{[^}]*\s(\S+)/', sh('dumpsys','window'))` 取包名精确等于 PKG 且 `dumpsys power` 含 `mWakefulness=Awake`；`sh()` 改 `['adb','-s',SERIAL,'shell',*quoted]`（SERIAL 取 `ANEB_SERIAL`，缺失 exit 2；参数设备侧单引号包裹；模块级 `SH=sh` 供注入）；`main()` 开头 `assert prompt.isascii()` 并把 prompt 写进 `_driver_timing.jsonl` 首行；ds 版 STOP 文案用 PKG 变量；新增 `tools/e234/tests/test_drive_cell.py` ≥5 条（AST Call==1、focus 三态、引号转义、多轮账目、缺 serial）；D-650④ 出订正条 | `python3 -c "import ast;…"` 两文件 `pin_console_utf8` Call==1；`grep -c 'PKG in sh' tools/e234/drive_cell*.py` = 0；`grep -c 豆包 drive_cell_ds.py` = 0；`run_tests.py` 全绿含 test_drive_cell |
| **A-2** | 采集器通道 C 三处：线程异常守卫 + 节拍补偿/实测节拍入账 + 周期头取「首个含帧段」+ 图层缺席也重挑 | v3 / M（1 天） | `_dump_channel_c` 循环体 `try/except (TimeoutExpired, OSError)` 计数继续；acct 记 `t_first/t_last/cadence_s`；`--framestats-period-s` 改 float 默认 1.0，补偿式等待；`collect_notes.sf_dumps` 记 `cadence_s` 与 `refresh_period_ns` 各值计数；layer 为 None 时循环内定时 `_relist_layer`；`e1_analyze.py:354` 与 `e2_precheck.py:217-240` 取第一段含 ≥1 帧行的周期头；precheck 加 `sf_coverage`（<0.9 ⚠ CANNOT_TELL）与 `margin`（<20% ⚠）；反例 + 突变 M26/M27 | `awk 'NR>=385&&NR<=440' e234_collect.py | grep -c except ≥1`；`mutation_audit.py` 27/27；对 `t90_verify/relist1` 输出 margin≈0.39；对 `e234/20260802-172614` 不再印「90Hz」 |
| **A-3** | 零回答轮成因分流（e2/e3/session/precheck） | v3 / S（0.5 天） | e2/e3 在 `v3_anchors` 前 `if not ts: _drop('该轮窗内零事件（App 未回答或通道 A 无打点）')`；`segment_turns` 零事件但有标记→按标记切、新增 `TURN_METHOD_NO_EVENTS`；`channel_a_anchors` 增 `turns_zero_events` 并从分母分列；`sim_session` 加注入项（顺手去 BOM）；反例各 1 + 突变 M28 | 对 `wave1/wifi_f6_b_VOID1` 跑 e2 的 `drop_reasons` 含「零事件」键；`head -c3 sim_session.py` ≠ `ef bb bf`；28/28 CAUGHT |
| **A-4** | **语料台账诚实化**：demo 出 real、契约门吃受跟踪语料、鲜克隆测试不红 | v3 / S（0.5 天） | `demo_results.jsonl` 每行加 `"synthetic":{"generator":"gen_demo_jsonl.py","seed":42}`（生成器同步）；`is_synthetic` 增 `run_id` 以 `demo-` 开头判据；`corpus_ledger` 增 `--list-corpus`，`summarize` 后对 real 集跑 `validate_records` 非空即 `--check` 退 1；`verify_all.ps1:471-497` 改喂清单，PASS 判词要求 file(s)≥31 且 record(s)≥99；`test_every_path_literal…` 对 `git check-ignore -q` 命中的父目录放行并显名；反例「demo- 且无 synthetic 块不得进 real」；重算台账/徽章；D 条写明 111→99 与「10 高置信 run 全为合成」 | `grep -o '真实 run 总数：[0-9]*' docs/CORPUS_LEDGER.md` = 99；`validate_results.py $(corpus_ledger.py --list-corpus)` 退 0；`pytest scripts/tests -q` 813 passed |
| **A-5** | **判决性实验收口**：复算 `wave1/wifi_f6` e2 并出 DW-20260831-01 判读页 | v3 / S（半天） | `python3 tools/e234/e2_analyze.py --run-dir evidence/wave1_20260831/wifi_f6 --pkg com.larus.nova` 落 `e2_result.json/e2_report.md`；与 DW-02 wifi_f6（p99 17,230 ms）并排；按判读页 :145 两分支下判（本评估副本复算 p99 28,440.6 ms ⇒「语义事件说成立」）；写 `docs/DW_20260831_01_JUDGMENT.md`；命题单模板把 e2 从主命题移出，改用通道 B 首跳变作旁证；`e2_analyze` 子块 `status` 改名 `sample_ok`；T81 板面回写 | `evidence/wave1_20260831/wifi_f6/e2_result.json` 存在且 n≥5；判读页含两格 p99 对照与二选一判词；T81 行「未出」改为路径 |
| **A-6** | 通道 A 恢复/验证脚本化并在 .ctree 包上实证 | v3（脚本）+ 大脑（设备）/ M（1 天，设备 ≤15 min） | `scripts/a11y_check.py`（只读 `dumpsys accessibility` + `settings get`，输出 Bound/Crashed/组件 id 与 ANEB_PKG 是否一致、Bound 数恰 1，纯函数解析 ≥4 单测）；`scripts/a11y_recover.py --confirm`（D-634 形态，写后 20 s 内 `ADAPTER_EVT>0` 才 PASS，结果落 `evidence/a11y_verify_<ts>/`）；`e234_collect.device_gate` 之后调用 a11y_check，FAIL 拒采；大脑按 P40 实况在 .ctree 包上跑一次写 D 条 | `python3 scripts/a11y_check.py` 输出 `bound=1 pkg=com.aneb.probe.ctree`；`evidence/a11y_verify_*/result.json` 含 `adapter_evt_count≥1` |
| **A-7** | **E-2 提权窗 + B-2 段 B 自环 + 段 C 设备干跑**（整形可行性） | PO（开窗 5 min）→ v4（段 B）→ 大脑/61bd2401（段 C）/ M | PO：管理员 PowerShell `cd E:\C Project\ANEB` 后 `claude --resume` 选 v4；v4：`IsInRole(Administrator)` 打印 True 入 D 条；clumsy 首跑加载 WinDivert.sys（`driverquery | findstr WinDivert`）；基线 ping、Lag=200 ms、后 ping；三档配置存仓外 `E:\tools\aneb-shaper\profiles\`；**产物落仓** `evidence/b2_selfloop_<ts>/README.md`；段 C：P40 装 gnirehtet 并授权 VPN，`ip route get 120.79.148.0` 出口为 tether，设备侧 ping 看 RTT 抬升带，同窗第一件验 gnirehtet 与 PCAPdroid 是否互斥（互斥即入册转裁）；收尾停 gnirehtet/clumsy、`adb reverse --remove-all`、复验路由与 tun 无残留 | `evidence/b2_selfloop_*/README.md` 含 IsInRole=True、driverquery 命中、两组 ping 中位数且后者落在基线 +200±30 ms；`evidence/b2_devicecheck_*/README.md` 含 `ip route get` 原文与设备侧 RTT 两组中位数；D 条登记「整形形态可用/不可用 + 互斥结论」 |
| **A-8** | T54 复采前三件：U3 回服务端权威口径、测量端点钉死 HTTP/1.1 并记协商协议、上报体加构建指纹 | v4 / M（1 天） | `AnebClient.uploadWindow` 解析 `UploadServerView`，`bytesTransferred=serverView.bytes`（与 written 不一致记 diagnostic）、`endNanos`=响应头到达；`ScenarioKpi.adaptiveWindow` 上行改 `UploadAnalysis.estimateSlowStart(chunkUs, recvStartUs, 65536)`；`serverView==null` 时 U1/U3 `durationNanos` 置 null（R-10）；`server/main.go` 设 `srv.TLSNextProto = map[string]func(*http.Server,*tls.Conn,http.Handler){}`，`tls_test` 断言 TLS 下 `resp.Proto=="HTTP/1.1"`；`AnebClient` 逐样本记 `response.protocol` 与 `X-Aneb-Proto` 上报（additive）；`build.gradle.kts` `buildConfigField GIT_SHA/BUILD_TYPE/APPLICATION_ID` + `require(anebAppIdSuffix.startsWith('.'))`；TestRun 加三列（Room v23 + MigrationV23Test + schemas/23.json）；`ResultReporter.run.build{git_sha,build_type,application_id,inject_used}`；scripts 对 debug∧inject 标 non_forensic；单测：`KpiCalculatorU3D3Test`「written=34 MB、server=30 MB ⇒ 30 MB」、`ScenarioKpiUploadBytesTest`「2xx+坏 JSON ⇒ null」 | `go test -race -count=1 .` 绿且 `grep -n TLSNextProto server/main.go` 非空；`./gradlew :probe:testDebugUnitTest` 绿；新 run JSONL `.run.build.git_sha` 与 `git rev-parse --short HEAD` 一致，`negotiated_protocol` 全为 http/1.1；D-703 首样本在台账标「U3 客户端口径、h2」禁合池 |

### 7.2 本周（至 09-12）

| id | 项 | 属主/量 | 步骤 | 验收 |
|---|---|---|---|---|
| B-1 | 基线窗补齐六格（自然对照）+ T+1 判读页 | 大脑（窗令）→ 61bd2401/大脑（执行）→ v3（判读）/ L | 在 A-0 两腿之后同窗或次窗跑 DeepSeek wifi_f6/cell_f6/wifi_f1/cell_f1；每格 `RUN_KIND.json` 记驱动器哈希、D-641 开关态、格间单调钟间隔、逐轮内容事件计数；停窗规则取一条并执行「第 N 次滑落即停」；收窗重算台账；T+1 出 `e2_precheck/e2_analyze` 判读页并把 A-3 的零事件轮单列 | 六格 `RUN_KIND.json` + `collect_notes.json`（`sf_coverage≥0.9`）；豆包两格 WORTH_RUNNING 且 A 侧可用轮 ≥5；`grep -c <新ID> docs/CORPUS_LEDGER.md ≥6` |
| B-2 | 整形窗：豆包 F1/F6 × ≥3 档（cap/delay/loss）× ≥2 格 | 61bd2401（设备）+ v4（整形侧）/ L | 前置＝A-7 干跑 README 齐；每档起 gnirehtet+clumsy → 采 F6 与 F1 各 1 格 → 停整形复验路由；`RUN_KIND.json` 记 `tier/shaper_profile/shaper_effective/uplink`（记实际生效值不记意图）；每档前后各跑一次 `/echo` 与 s4 下行落 `shaper_checks/` 作「整形在位」证据；整形批协议附录（前置改「tether 通 + 默认路由经 tun + PC 上行可控」，替换先行批的 `ip route get` 走 wlan* 判据） | ≥6 格 `shaper_profile≠null`；每档 `shaper_checks` 的 echo RTT/goodput 与档位一致；`e2_precheck` ≥4 格 WORTH_RUNNING；若 A-7 未通过则本项顺延、报告降为「自然对照版」并在标题显名 |
| B-3 | 采集链与台账增「整形档」与「状态」字段（落 D-655③） | v3 + 61bd2401 / S | `e234_collect.py` 加 `--tier/--uplink` 写 `RUN_KIND.json`（缺省 good）；收窗写 `RUN_KIND.state∈{valid,void,verify}+void_reason`；历史目录按 `_VOID` 后缀与 t90 名一次性回填并在表注列出 7 个 08-22 回填目录；`corpus_ledger.observation_runs()` 输出 `device_real_valid/void/verify` 三列与 kind×tier 分布；`buckets` 对照 schema enum，枚举外值渲染为 `enum_outside:<v>`；加「可出报告 run」「可承载结论格」两行进徽章；T33 §4 增量锚改「+N valid 格」 | CSV 含 `device_real_valid_dirs=11、void_dirs=5、verify_dirs=1`（按当前数据）；tests 加反例：受控格缺 tier 即拒、`validity=degraded` 不得以普通桶出现 |
| B-4 | 台账在鲜克隆可复现 + `.gitattributes` | 大脑裁根策略 + v3 / M | 大脑三选一（8 份合成 jsonl 与 server/data 2 份入受跟踪目录 / 显式 --root / 缺根按可见根比对并点名）；按裁定改 `DEFAULT_ROOTS` 与 `--check` 判词；仓根 `.gitattributes`（`* text=auto eol=lf`，二进制显式 -text）在树净时单独提交并 renormalize，清单自述改「库内 blob 形态」；`test_corpus_ledger` 加「鲜克隆 --check 退 0」用例；仓根加 `requirements-dev.txt`（pytest、jsonschema、pyyaml） | 新 `git worktree` 中 `python scripts/corpus_ledger.py --check` 退 0；`ls .gitattributes` 存在；两台机器 `sha256-manifest.txt` 逐行相同 |
| B-5 | 双包隔离：TAG 随变体、`ADAPTER_EVT` 带 app 字段、解析器 pid 单一性、采集前置 Bound 恰 1 | v4（app）+ v3（tools）/ M | `AnebAccessibilityService.TAG` 由 `BuildConfig.APPLICATION_ID` 派生（默认包保持 `AnebProbe` 逐字不变，.ctree→`AnebProbe-ctree`）；`formatAdapterEvtLine` 追加 `app=`（`t_boot_ns` 仍行尾）；`e1_collect.DEFAULT_ADAPTER_TAG` 与 `e234_collect` 的 `logcat -s` 按 ANEB_PKG 派生；`parse_adapter_events` 解析 `-v time` 行首 pid，`content_events` 多 pid → NOT_EXECUTED；`device_gate` 后调用 a11y_check | ctree 构建 `logcat -s AnebProbe-ctree:I` 可见事件；tools 新增「两 pid 混入 → NOT_EXECUTED」用例绿 |
| B-6 | 探针版本/来源账目与两处静默降级 | v4 / S（0.5 天） | `TestEngine.KPI_SET` 改引用 `KpiCalculator.KPI_SET_VERSION`（wire 值由大脑一句裁 v0.1/v0.2 入 D 条）；`SpecScoringParityTest.version_ids_parity` 增 TestEngine 断言；`validate_profiles.py` 校 `profile.kpi_set` 属登记集，`VERSIONS.md` 增 kpi_set 节；`TestEngine` 抽 `isCellular()` 覆盖 `auto(cellular)`；`ScenarioRunner` 对 `windowMs<=0/bytes<=0` 抛 ENGINE_ERROR、未知 phase → `InvalidReason.PROFILE_UNSUPPORTED`；`ProfileParser.versionString` 遍历全部 id | `grep -rn 'agent-qoe-kpi-v0\.' app/probe/src/main` 只剩 1 处；`ResultReporterRadioTest` 夹具 `auto(cellular)` 出 radio 块；缺 `window_ms` 的 profile 使场景 INVALID |
| B-7 | low_confidence 门槛口径裁定与实现 | 大脑（裁）→ v4（改）/ M | 大脑入册：(a) `AqsInputMapper.medianKpi` 改 `lowConfidence = Σvalid.sampleCount < 门槛`；或 (b) profile 每 KPI 声明 `expected_n`；按裁定改并回放语料（去重剔 demo）统计新旧比例入 D 条；`RenderRedlineTest` 加「forensic 高置信 run 不显徽章」反例；KPI 文档 5.1 同步 | 回放 forensic run 低置信比例 <50%、quick ≥90%；语料台账标 aqs 口径版本 |
| B-8 | 服务端身份可追溯 + profile 合同 fail-closed + s4 进 REQUIRED 对拍 + 门禁 `-race` | v4/v2 / M（1 天） | `main.go` 用 `runtime/debug.ReadBuildInfo` 写 `/serverinfo.vcs_revision` 与启动日志，`X-Aneb-Server` 追加 `+<12 位哈希>`（RealtimeSimSession/VoiceRunner 前缀匹配同步），`serverVersion→0.2.0`，建 `server/CHANGELOG.md`；`loadProfiles` `DisallowUnknownFields` + `json.RawMessage` 原样下发 + 文件↔端点 DeepEqual 测试；`profiles_test` required 加 s4 并断言两相位 `window_ms==4000`；app `DIAGNOSTIC_IDS=[s4_throughput]` 参与 versionString/loadAssets；`verify_all.ps1` server-test 改 `go test -race -count=1 ./...`，加 server-buildinfo 步 | `curl -sk https://127.0.0.1:8443/api/v1/serverinfo | jq .vcs_revision` 与 HEAD 前 12 位一致；含未知键的 profile 使启动失败；`grep -n '\-race' scripts/verify_all.ps1` 非空 |
| B-9 | UI 三处：`transport=auto` 单点映射、历史页/分享卡渲染层测试、`ShareCard.drawTo` 接缝、T88 屏验收口 | v4 / S（0.5 天 + 开窗顺带截图） | `HomeScreen.kt` 抽 `transportLabel()`（auto→「自动（系统默认网络）」），首屏/结果页/历史页共用；`HomeLastRunLabelTest` 改 auto→含「自动」；`HomeRoutes.lastRun` 过滤 status；`RenderRedlineTest` 加 HistoryScreen 三种行；`ShareCard.drawTo(Canvas)` 用记录型 Canvas 断言横幅先于结论，重跑 M4 为 CAUGHT，补跑 74d424d 的 M1；开窗顺带截图归档 evidence，T88 转 DONE | `grep -c '"auto"' HomeScreen.kt ≥1`；相关单测绿；删除 render 调用块后 ShareCard 测试至少 1 红；板面 T88 DONE 且证据列有截图路径 |
| B-10 | 裁项 B 施工（P1-7）+ T82 假闭环订正 | 大脑裁标签 → v4 / S（0.5 天） | 大脑一句裁终态标签（复用 `N/A-BY-CALIBER` 或新增 `ABANDONED-BY-PO` 入 `CAPTURE_STATUSES` 不入 BLOCKING）；`check_redline.py` RULED_STATUS 两字段改终态；四 yaml `params_capture_status` 两字段改终态、reason 引 D-592①；`test_check_redline` R19d 反向；板面 T82「施工 D-583」改「施工 <新哈希>」并补残项行 | `grep -c 'status: PENDING-BY-CALIBER' spec/portraits/*.yaml` 全 0；`check_redline.py` exit 0；`pytest spec/portraits -q` 绿含新反例 |
| B-11 | k=20 相对门限离线并排复算工具（P2-9，不换口径） | v3 / M（1 天） | 新增 `tools/e234/gap_compare.py --run-dir …`：每轮每通道输出 400 ms 绝对 vs `gap>k×median(gap)` k∈{10,20,40} 的簇数/A2/是否闭合；对 wave0 11 格 + wave1 wifi_f6 + B-1 六格离线跑入判读页附节（引 D-615④）；作废判据机器化（比值分布落 [15,25] 非空即 ⚠）；单测 ≥3 | 对 ≥12 格产出 ≥12 行×4 口径表；`run_tests` 含 `test_gap_compare` |
| B-12 | 治理机检三条 + 板面/日志可读性 + 编队实况表 + 收工心跳 | 大脑立规 + v4 落守卫 / M | `scripts/tests` 新增：`test_playbook_frozen`（§4 ≤75 行，解冻须改测试并引 D 号）、`test_decision_length`（D-705 起 ≤200 字或含「证据包：」指针）、`test_board_status_words`（状态列开头整词 ∈ 四态，容忍单元格内竖线；先修 T80）、`test_session_liveness`（在册会话板行 24 h 内须有实况或「无活理由」）；任务板拆活动表/归档表，板头加「编队实况」表（端点 id、最后自身提交、在线/离线/只读）并自动写「最后更新」；`scripts/decision_index.py` 生成 `DECISION_INDEX.md` 入 verify_all；每次收工提交末尾固定「下次预计开工／停机至」（badges 软检查）；协调侧 L2 判据改「T80 行 24 h 无变化」；PR #4 cherry-pick `docs/coordination` 一次；T79 由大脑追认 cd5239ba 三笔；总计划 #3/#4 划线注 D-587、§5 改「我方自办」、基线升 v3.0（cd5239ba/61bd2401） | 四条守卫进 verify_all 并绿；`BRAIN_TASKBOARD.md ≤40 KB`；`DECISION_INDEX.md` 行数 = D 行数；`git log -1 --format=%B | grep -E '下次预计开工|停机至'` 非空；`git ls-tree HEAD docs/coordination/` 非空 |

### 7.3 两周（至 09-19）

| id | 项 | 属主/量 | 步骤 | 验收 |
|---|---|---|---|---|
| C-1 | **T78 结论报告 v0.1**：逐功能网络诉求 SLA 表 + 不可测项显名 + 数据来源哈希 | v3（起草）→ 大脑（四态复核）→ PO（认可）/ L（2 天） | `docs/DOUBAO_NETPERF_REPORT_20260919.md`：每功能一行——可测维度（A/B/E/G/I）→ 基线 WiFi/蜂窝判读（e2/e3/e4 + gap_compare 并排）→ 整形档表现（B-2 有则填，无则 NOT_EXECUTED 带原因）→ 建议 SLA；D/F/H 行写 `NOT_MEASURABLE-BY-REDLINE`（D-24/49/61），C/J 写弱化原因；每个数字带 evidence 目录 + RUN_KIND 哈希 + 判读页链接；零回答轮、CANNOT_TELL 格单列不入均值；附「与 DeepSeek NetPerf 论文 v4 的净迁移差异表」与「本报告不能回答的问题」；范围声明「不含 Profile 4、不含多流吞吐、不含 E-03」；标题显名「缩小版」或「自然对照版」；PO 简报模板加「范围外≠结论」固定句并给 08-30 简报补勘误行 | 报告存在且 `grep -c NOT_MEASURABLE-BY-REDLINE ≥3`、`grep -c 'evidence/' ≥12`；每个 SLA 行引用的格在 CORPUS_LEDGER 可查；DECISION_LOG 有 PO 认可 D 条；T78 状态改「REPORTED v0.1」 |
| C-2 | T54 复采 5–10 run（修后口径）并分层入台账 | 61bd2401/大脑（设备）+ v3 / M | 前提 A-8 合入且 .ctree 重装（build 块含 git_sha）；PC 起 C 树 server（TLSNextProto 已置空）；按 D-703 形态跑 5–10 次 s4，每 run 记 `serverinfo.goos/version`；台账新增 `server_goos/server_lineage/network_position` 三列并对 D-703 首样本标「U3 客户端口径、h2」禁合池；D-703 首样本本身入 `evidence/t54_wifi_smoke_20260904/`（`RUN_KIND kind=verify` 或 `diagnostic_runs` 单列，不与 real 相加）；T54 runbook 写明 Windows 缺省项；设备时段让位 T78（见 7.4 #3） | 台账 s4 行三列非空且 ≥5 行 git_sha 一致；`grep -rl 01a069f8 evidence` 非空；`.run.build.build_type` 记录变体 |
| C-3 | 探针网络层单测基线（MockWebServer）覆盖 U3/TTFT/取消链 | v4 / M（1.5 天） | `libs.versions.toml` 加 `okhttp3:mockwebserver:4.12.0`；`AnebClientStreamTest`（dupseq/malformed/truncate 三注入）、`AnebClientEchoTest`（固定 t1/t2）、`AnebClientWindowTest`（ceiling 先到→underrun；服务端 bytes≠written 取服务端）；TTFT 抽纯函数 `ttftMs(arrivalNs, originNs, schedUs, preludeUs)` + 三形态夹具；echo t0 改取 `callStartNs` 或并列记差值 | `grep -rln MockWebServer app/probe/src/test | wc -l ≥3`；删除 `gaps += tailMissing` 后至少 1 红 |
| C-4 | 驱动器合一 `--app {doubao,deepseek}`（P2-10，窗后） | v3 / M（1 天） | `APP_PROFILES={pkg,taps,name}`；复用 `e1_collect.Adb(serial)`；删 `drive_cell_ds.py`，README 记新旧哈希映射；`test_drive_cell` 覆盖两 App；一次 ≤3 分钟只读验证窗核四坐标 | `ls tools/e234/drive_cell*.py` 只有 1 个；`run_tests` 全绿；窗令 P3 记单一哈希 |
| C-5 | 观察格契约门（第 28 道门 `obs-corpus-contract`）+ 战役包 sha256 清单进链 | v3 + v4 / M | `spec/schemas/obs-cell.schema.json`（RUN_KIND 必填键与枚举含 `state/tier/driver_sha`、`screencap_index/mark_rtt` 行契约）；`scripts/validate_obs.py`（退出 0/1/2）接 verify_all 并登 Test-InScope；`e234_common.assert_isolation_before_write` 登记 `api_cmp`；坏行（wifi_f1_VOID2）转 FAIL 或显式豁免；`verify_all -Scope all` 对每个含 RUN_KIND 的日期包生成 `<包>/sha256-manifest.txt`，`check_evidence.py` 新规则「含 RUN_KIND 的日期包必有清单且条目 ⊇ 受跟踪文件」，一次性回填 5 包；`INSTRUMENTATION_SPEC` 升 0.2.0 并改状态「IMPLEMENTED-BY tools/e234」；spec/README 目录表补三目录并写明观察通道权威文件 | `gate_count=28`；`find evidence -name sha256-manifest.txt | wc -l ≥9`；`check_evidence.py` 对缺清单的合成包报 violations=1；`test_gate_coverage` 全绿 |
| C-6 | `adapter_obs` 溯源列（v23）+ 最后一段落库 + 5 s 定时 emit + IME 动态刷新 + 红线守卫补边 | v4 / M（1.5 天） | `AdapterObsEntity` 加 `ttftSource/ttftDensityMs/targetVersionCode`（与 A-8 的 TestRun 三列合并为同一版迁移）；`enqueuePersist` 分列落；`onServiceConnected` 缓存各 spec 包 versionCode；`onUnbind` 入队后 close；Handler 定时 5 s emit；ContentObserver 监听 `default_input_method`；订正 `Entities.kt:738`、`HistoryScreen.kt:342`、`AnebAccessibilityService.kt:28-29/:305` 三处注释；FORBIDDEN 追加 `dispatchGesture/GLOBAL_ACTION_`，xml 断言不含 `canPerformGestures`，`validate_adapters` 加 `observe_events ⊆ xml eventTypes`；`ADAPTER_EVT` 追加 `evt_up_ms`（先真机核非 0） | `MigrationRegistryTest` 绿且 schemas 最大版本=23；真机开豆包后 `am kill` 探针 adapter_obs 多 1 行；`ObservationRedLineSourceScanTest` 用例 +3 |
| C-7 | 服务端 s4 路径测试补齐 + retrans 流首基线 + Linux 侧门禁 + `X-Aneb-Server` 客户端校验 + 观察通道样本量表 + E4 标定 | v4（server/app）+ v3 + 61bd2401 / M | `/upload` 加 chunked 在 N 字节后结束→bytes==N、>64 MB→413、客户端 1 MB 后 Close 不 panic、4 路并发各自 bytes 正确；`/download` 加 ctx 取消；`handlers_stream` 在 prelude 后先 `connTotalRetrans`，summary 增 `retrans_start/retrans_delta`；verify_all 加 `server-test-linux` 步（`GOOS=linux go test -c` 经 `ssh -i ~/.ssh/aneb_e01` 在 E-01 或 WSL2 只跑测试二进制，不碰 0.8.3 unit）；`AnebClient` 校验 `X-Aneb-Server` 前缀，缺失即 `path_hijack_suspect`；用 F5/F6 各 12 值 bootstrap + `required_n_at_power` 写 `N_SAMPLE_SIZE_BY_KPI_RAT` 新节「观察通道」；驱动器 `answer_complete` 改 `answer_wait_elapsed`（`e4_analyze` 对 timer 来源按无标记处理），整形批 F2 轮由操作者按 `a` 打真标记，窗后跑 e4 | `grep -c '^func Test' server/handlers_upload_test.go ≥6`；归档日志含 `server-test-linux PASS`；`grep -rn path_hijack_suspect app/probe/src ≥2`；文档新节含 ≥2 KPI × 两效应量的 n；`evidence/<批次>/e4_report.md` 状态非空 |

### 7.4 需要 PO 亲裁的（各附「不裁的默认」）

1. **E-2 提权的常态化形式**：每次整形窗 PO 亲自开管理员 PowerShell 起 claude CLI（≈5 min/窗）；还是一次性批准 D-702③ 的 `schtasks /RL HIGHEST` 替代（代价＝该脚本对本用户可写即一条提权通道）；或先 (a) 完成干跑再评估转 (b)。**默认 (a)**：编队等 PO 开窗；A-7/B-2 顺延，C-1 退为「自然对照版」。
2. **T78 报告的可答范围**：按 CAMPAIGN_PLAN v0.1.0 净迁移认可「A/B/E/G/I 可测；D/F/H 标 NOT_MEASURABLE-BY-REDLINE；C/J 弱化」，规模为缩小版（豆包 F1/F6 × 三档）；还是要求全功能矩阵（顺延至 10 月）；或再加一条 UI 口径之外的独立度量（需解红线）。**默认 (a)**，报告标题带「缩小版」。08-24 板面 B-3 至今未见明文裁定。
3. **设备时段优先级**：T78 基线/整形窗 vs T54 复采（5–10 run）争 P40 时谁先。**默认 T78 先**，T54 在 A-8 合入后的 T78 窗间隙执行。
4. **E-01 上 0.8.3 server 是否允许被 C 树 server 替换**：不替换（双形态分层禁合池）；替换（先移植 realtime-sim 并过功能并集表，走 deploy 硬闸）；并存（另端口 `aneb-server-ctree`）。**默认不替换**，D-695③ 禁令维持。
5. **（人办件）Linux 盒**：限速档（膝点/悬崖）正式不覆盖已由 D-694① 定；若 PO 后续能提供一台 Linux 小机或 WSL2 可用，B-2 增 netem 档。不裁即维持不覆盖。

### 7.5 应停止或降级的活动

| 停什么 | 为什么（证据） |
|---|---|
| E-03 GLM 抓取器与 `arrivals` 改名链继续占用 v3 工具时段 | 09-02 以来 tools/ 10 次提交 9 次在 e03，采集主链零提交；E-03 校的是 API 模式 ITL 语义，对 T78 贡献为零（L4-F8、F7-08）。降为「M 系列 API KPI 复核时再启用」，改名链挂装机批 |
| 引用「真实 run 111」与「10 条高置信 run」 | 12 条合成 demo、唯一契约违规源；真机 98/99 run 中 97 低置信（SP-F-01、L1-missed）。A-4 落地前任何报告/周报不得引用 |
| 在 A-8 合入前继续 T54 复采并把 s4 样本入正式语料 | U3 本地写口径、h2 不记协议、无构建指纹（S3-01/02、L1-F4）；现在采的每条都要事后打「禁合池」标签 |
| 面册新增一级条目、千字裁定 | 冻结令当日 61→75；D-655…704 均 1,431 字、0 条 ≤200；09-03 六小时 37 条裁定同时段数据线零动作（G8-04/09）。冻结到整形批出首格；D-705 起摘要 ≤200 字，细节走证据包指针 |
| `scripts/README.md` 继续作判读日记增长 | 834 行中约 400 行判读散文，42/85 提交只改 README（SP-F-11）。迁 `docs/OBS_JUDGMENT_GUIDE.md` 一个提交 |
| 把 `sf_latency` 首行 `11111111` 读作「P40 跑 90 Hz」并据此算环缓冲余量 | 仓内所有 11111111 头行都落在零帧 dump（L4-missed）。余量按每格 `refresh_period_ns` 分布算 |
| 两只驱动器并行手改 | 148/154 行逐字重复，修一处漏一处即签名分叉（L4-F6）。A-1 四件双写、C-4 合一，此间禁止只改一只 |
| 对 E-01 执行 `scripts/deploy_server.ps1` | 硬编码只装 s1–s3、不装 unit 所需 public 证书、会覆盖 0.8.3 血统 unit（S3-04）；D-695③ 禁令维持 |
| 把 D-703 的 quick 单次 run 写成「wire +1」 | D-663(a)/T49 定 quick 单次＝诊断口径不进战役语料；应单列 diagnostic（F7-05） |

### 7.6 可核 KPI（本周 / 两周）

| KPI | 现值 | 1 周目标 | 2 周目标 | 怎么量 |
|---|---|---|---|---|
| T78 可判读观察格（`e2_precheck=WORTH_RUNNING` 且 RUN_KIND 齐） | 0（DW-20260831-01 六格零完成；旧 11 格为旧驱动器） | ≥4 | ≥10（基线 ≥6 + 整形 ≥4；A-7 未过则 ≥6 并显名「无整形」） | 对 `find evidence -name RUN_KIND.json -newer docs/coordination/REVIEW_20260902.md` 的目录逐个跑 `e2_precheck` 计 WORTH_RUNNING |
| 驱动器/采集器 0902 已知缺陷余量（focus 子串、docstring 空转、无 serial、通道 C 无守卫） | 4/4 未修 | 0/4 | 0/4 且驱动器合一 | `grep -c 'PKG in sh'`、AST Call 计数、`grep -c "'adb','shell'"`、`awk 'NR>=385&&NR<=440' e234_collect.py | grep -c except` |
| 语料台账诚实度 | 台账 111（含 12 demo）；门只校验 2 条 gitignored | 台账 99；门覆盖 ≥99 条受跟踪记录、退 0 | 99 + T54 新 run；鲜克隆 `--check` 退 0 | `corpus_ledger.py --root evidence` 重算；`validate_results.py $(corpus_ledger.py --list-corpus)` |
| 整形形态可用性 | 0/3 档（IsInRole=False，未干跑） | 3/3 档干跑通过（`evidence/b2_selfloop_*`） | 3/3 档各 ≥2 格豆包语料 | `ls evidence/b2_selfloop_*/README.md`；`grep -l '"shaper_profile": "' $(find evidence -name RUN_KIND.json) | wc -l` |
| 探针测量口径缺陷（U3 本地口径、h2 不记协议、无构建指纹、AUTO 丢 radio、相位静默降级、kpi_set 三处不一） | 6/6 未修 | 3/6（A-8） | 0/6（B-6） | `grep -c serverView AnebClient.kt`、`grep -c TLSNextProto server/main.go`、`grep -c GIT_SHA build.gradle.kts`、`grep -c 'auto(cellular)' TestEngine.kt`、`grep -c 'coerceAtLeast(1)' ScenarioRunner.kt`（目标 0）、`grep -rn 'agent-qoe-kpi-v0\.' app/probe/src/main | wc -l`（目标 1） |
| 真机 forensic run 低置信恒真率 | 49/50 | 口径裁定入册 | 回放 forensic <50%、quick ≥90% | 去重剔 demo 后按 mode 统计 `run.aqs.low_confidence` |
| 治理节律 | 静默 29 h；裁定均 1,431 字；心跳行 0 | 静默 ≤12 h；D-705 起 10 条中位 ≤400 字；最近 3 次收工含心跳行 | 四条治理守卫进门；`BRAIN_TASKBOARD.md ≤40 KB` | `git log` 间隔；`awk length` 统计；`git log -3 --format=%B | grep -c '下次预计开工'` |

### 7.7 会话分工一览（今日起）

- **大脑**：A-0（开窗）、A-6 设备执行、A-7 段 C、B-1 窗令与命题单、B-4/B-7/B-10 三句裁定、B-12 立规与 PR #4 并入；自约束：D-705 起 ≤200 字、面册零新增、收工心跳行。
- **61bd2401（缺席则大脑接管）**：A-1、B-1/B-2 设备执行、C-2、C-7 的 E4 真标记；T79 追认。
- **v3**：A-2、A-3、A-4、A-5、A-6 脚本、B-3、B-4 施工、B-11、C-1 起草、C-4、C-5 门、C-7 样本量表。
- **v4**：A-7 段 B、A-8、B-5、B-6、B-7 施工、B-8、B-9、B-10、B-12 守卫、C-3、C-5 清单守卫、C-6、C-7 server。
- **cd5239ba（闲置纸面件）**：总计划/基线过期行订正与升版（B-12 尾项）。
- **PO**：开一次管理员窗（A-7）；四项裁定（7.4）；核实本地四个会话是否在跑。
- **协调侧（本会话）**：本报告入分支与 PR #4；B-008 后继广播；L2 判据改「T80 行 24 h 无变化」；每巡对照 7.6 KPI 写实值。

---

## 8. 附录

### A. 代码地图（本评估读过的关键文件；行数为 0687228 时点）

| 子系统 | 文件 | 行数 | 职责 |
|---|---|---|---|
| 探针引擎 | `app/probe/src/main/java/com/aneb/probe/engine/TestEngine.kt` | 1,269 | run 编排：守卫/绑网/profiles/监控/场景循环/s4 分支/AQS/上报/落库；`KPI_SET` :1129 |
| | `engine/ScenarioRunner.kt` | 483 | 逐相位执行；U1/D1 对账 :61-102；TTFT 公式 :410-417；窗口相位 :335-386 |
| | `net/AnebClient.kt` | 912 | OkHttp 客户端：echo/stream/upload/download/window/toolloop；`uploadWindow` :633-679 |
| | `net/SseReader.kt` | 405 | SSE 边界扫描/打戳/`sameReadBatch`/解析线程；`READ_CHUNK_BYTES=8192` |
| | `scoring/KpiCalculator.kt` | 627 | KPI 计算；门槛常量 :349-354；U3/D3 :497-501 |
| | `scoring/AqsScorer.kt` | 647 | 8 权重表/7 版本/否决；T4>1% 封顶 54 |
| | `engine/ScenarioKpi.kt`、`AqsInputMapper.kt`、`ResultReporter.kt`、`RttDominanceGuard.kt`、`TransferWindowAnalysis.kt`、`UploadAnalysis.kt`、`ProfileModels.kt`、`ProfileRepository.kt` | 241/194/302/52/70/57/115/64 | 映射、聚合、上报体、主导度、慢启动、profile 模型与加载 |
| | `radio/RadioCollector.kt`；`net/cronet/CronetStreamClient.kt`；`engine/AbRunner.kt`；`engine/VoiceRunner.kt`；`net/RealtimeSimSession.kt` | 607/329/439/667/252 | 1 Hz 无线；Cronet A/B；语音 v1/v2 |
| | `app/probe/build.gradle.kts`；`app/gradle/libs.versions.toml`；`src/debug|main/res/xml/network_security_config.xml` | 194/75/45+24 | applicationId 后缀属性、签名回落、版本钉死、NSC |
| 适配/数据/UI | `adapter/AnebAccessibilityService.kt`；`adapter/ObsStats.kt`；`adapter/AdapterSpec.kt` | 443/467/313 | 通道 A 宿主、四代 TTFT 代理、严格 loader |
| | `data/Entities.kt`；`data/AnebDatabase.kt`；`data/Daos.kt` | 765/648/163 | 13 实体、v22、16 条迁移 |
| | `ui/HomeScreen.kt`；`ui/HistoryScreen.kt`；`ui/ShareCard.kt`；`ui/ResultScreen.kt`；`ui/SettingsScreen.kt`；`ui/routes/HomeRoutes.kt` | 729/367/298/1,308/522/74 | 首屏/历史/分享卡/结果/设置 |
| | 单测重点：`ObservationRedLineSourceScanTest`、`MigrationRegistryTest`、`MigrationV22Test`、`HistoryFeedTest`、`HomeLastRunLabelTest`、`ShareCardLowConfidenceTest`、`SpecScoringParityTest`、`KpiCalculatorU3D3Test`、`RenderRedlineTest` | | |
| 服务端 | `server/main.go`；`handlers_stream.go`；`tokengen.go`；`profiles.go`；`handlers_upload.go`；`handlers_download.go`；`handlers_artifact.go`；`handlers_results.go`；`handlers_echo.go`；`handlers_serverinfo.go`；`tls.go`；`h3.go`；`tcpinfo*.go`；`clock.go` | 164/505/244/183/136/141/254/123/59/78/80/115/55+76+9/19 | 见 §3.3 |
| | `server/aneb-server.service`；`scripts/deploy_server.ps1`；`scripts/gen_cert.sh`；`server/tools/{gencert,h3check,capture,mockllm}` | 25/132/41/110+36+166+155 | 部署面与工具 |
| 工具 | `tools/e234/e234_collect.py`；`e234_common.py`；`e234_session.py`；`e2_precheck.py`；`e2/e3/e4_analyze.py`；`drive_cell.py`；`drive_cell_ds.py`；`sim_session.py`；`tests/mutation_audit.py` | 551/439/131/581/243+270+334/154/156/352/395 | 见 §3.4 |
| | `tools/e1/e1_collect.py`；`e1_analyze.py`；`e1_io.py`；`tools/e03/glm_capture.py` | 336/1,032/37/191 | E1 采集/判读；GLM 抓取 |
| 脚本/门禁 | `scripts/verify_all.ps1`；`badges.py`；`corpus_ledger.py`；`validate_results.py`；`campaign_common.py`；`campaign_report.py`；`publish_check.py`；`check_evidence.py`；`corpus_health.py`；`tests/run_all.py`；`tests/test_gate_coverage.py`；`tests/test_docs_commands.py`；`tests/test_report_properties.py` | 859/157/590/401/1,277/3,032/788/308/145/87/306/2,173/2,964 | 见 §3.5 |
| 规格 | `spec/schemas/result-run.schema.json`；`spec/scoring/{weights,anchors,vetoes,radio_bands}.yaml`、`VERSIONS.md`、`check_versions.py`；`spec/portraits/*.yaml`、`check_redline.py`；`spec/adapters/*.json`、`validate_adapters.py`、`INSTRUMENTATION_SPEC.md`；`spec/profiles/server/*.json`；`profiles/*.json` | 278/…/440/453/666 | 见 §3.6 |
| 证据/治理 | `evidence/README.md`；`evidence/doubao_wave0_20260830/README.md`；`evidence/wave1_20260831/README.md`；`evidence/t90_verify_20260901/README.md`；`evidence/glm_e03_20260903/README.md`；`docs/CORPUS_LEDGER.md`；`docs/DOUBAO_WAVE0_JUDGMENT_20260830.md`；`docs/BRAIN_TASKBOARD.md`；`docs/DECISION_LOG.md`；`docs/AUDIT_PLAYBOOK_v1.md`；`docs/B2_SHAPER_BUILD_SHEET_20260903.md`；`docs/DOUBAO_NETPERF_CAMPAIGN_PLAN_20260824.md`；`docs/T78_DOUBAO_PILOT_COLLECTION_PROTOCOL_20260829.md` | 27/297/246/80/116/138/429/262/733/220/246/328/964 | 见 §3.7–3.9 |

### B. 关键数字的核查命令（在上游工作树执行）

```bash
# 语料：记录数 / 唯一 run / 非 demo / 低置信 / forensic
python3 - <<'PY'
import json,glob;R={};n=0
for f in glob.glob('evidence/**/*.jsonl',recursive=True):
    for l in open(f,encoding='utf-8',errors='replace'):
        if '"kpi_set"' not in l: continue
        r=json.loads(l);n+=1;R.setdefault(r['run']['run_id'],r)
real=[r for k,r in R.items() if not k.startswith('demo-')]
print(n,len(R),len(real),sum(1 for r in real if r['run'].get('aqs',{}).get('low_confidence')))
PY
# demo 是唯一违规源
cd scripts && python3 validate_results.py ../evidence/phase3/demo_results.jsonl | tail -1   # 40 in 12
# U3 / h2 / 构建指纹
grep -n 'resp.body?.close()' app/probe/src/main/java/com/aneb/probe/net/AnebClient.kt
grep -c 'protocols(' app/probe/src/main/java/com/aneb/probe/net/AnebClient.kt              # 0
grep -c 'TLSNextProto\|NextProtos' server/*.go                                               # 0
grep -c GIT_SHA app/probe/build.gradle.kts                                                   # 0
# 驱动器三缺陷
grep -n 'PKG in sh\|pin_console_utf8\|\["adb", "shell"' tools/e234/drive_cell*.py
git log -1 --format='%h %ci' -- tools/e234/drive_cell.py                                     # b5cb4f3 09-01
# 首屏 auto
grep -c '"auto"' app/probe/src/main/java/com/aneb/probe/ui/HomeScreen.kt                     # 0
# 11111111 只在零帧段
for f in evidence/e234/20260802-172614/sf_latency.txt evidence/t90_verify_20260901/relist1/sf_latency.txt; do tr -d '\r' <$f | awk 'NF==1{p=$1;c[p]+=0} NF==3{c[p]++} END{for(k in c)print k,c[k]}'; done
# 判决性实验
python3 tools/e234/e2_analyze.py --run-dir <evidence/wave1_20260831/wifi_f6 的副本> --pkg com.larus.nova   # p99 28440.559 ms
# 治理
git log -1 --format=%ci 0687228
python3 -c "L=[len(r) for r in open('docs/DECISION_LOG.md',encoding='utf-8') if r.startswith('| D-6') or r.startswith('| D-70')];print(len(L),sum(L)//len(L))"
grep -rhoE 'DW-2026090[1-9]-[0-9]{2}' docs/ | sort -u                                       # 空
# 门禁复现
cd server && go vet ./... && go build ./... && go test -race -count=1 ./...
python3 tools/e234/tests/run_tests.py; python3 tools/e1/tests/run_tests.py; python3 tools/e03/tests/run_tests.py
cd scripts && python3 -m pytest tests -q                                                      # 812 passed, 1 failed（环境）
cd spec && python3 -m pytest -q                                                               # 109 passed（需 jsonschema）
```

### C. 核查统计与被订正的口径

- 读者发现 116 条：确认 88、限定 28、推翻 0；核查者补漏 26 条；数字指标 100 项复算，19 项订正。
- 被订正的主要口径（本报告已采用核查值）：语料「333 run」为记录数，唯一 run 110、真机 98/99；「10 条高置信 run」全为合成 demo；scripts 测试「364/1」为 `-x` 首轮，全量 812/1；「P40 曾跑 90 Hz」为死图层头行误读；U3 缺陷定级取 high（T54 主要产出）而非 medium（不进 AQS）；「D-655 连带六件 1/6」应按原文六件约 3.5/6；「面册冻结当日自破」应为「未采纳广义冻结」，狭义承诺守住；docs-only「74/110」应为 80/110；GLM 单笔时长 1.0–15.8 s；驱动器逐字相同 148/154 行；单点守卫 12 条；Robolectric 渲染测试 4 文件；`MigrationTestHelper` 在注释出现 1 次；E-03 差额 ≈1.5%；`CAMPAIGN_LABELS` 缺口不影响走观察通道的 T78；calibration yaml 已自述「含 SSE 合帧」；`artifact_stream` 等为服务端整形旋钮、app 不认属设计。
- 两条互斥解释未定因：D-703 首样本 `u3 excl<incl` 可由「本地写缓冲伪影」或「h2 流控」解释，单样本不能定案；A-8 修后复跑一次即可分辨。

### D. 开放问题（需要仓外信息或裁定）

1. 本地 PC 与四个会话在 09-04 09:47 +0800 之后是否仍在运行（git 分不清关机/停摆/未推送）；61bd2401 能否 resume。
2. E-2 段 B 是否已执行（产物只落 scratchpad，对 git 不可见）；gnirehtet 与 PCAPdroid VPN 槽位是否互斥。
3. D-703 的 PC server 是否带 `-h3`、`X-Aneb-Proto` 值；E-01 的 0.8.3 是否禁用了 HTTP/2（决定历史语料回填范围）。
4. `run.kpi_set` 正确值是 v0.1 还是 v0.2；s4 的 v0.3 有无定义文档。
5. 低置信门槛在 KPI 规格里的语义是场景级还是 run 级（`docs/` 下无 AGENT_QOE_KPI 独立文档，规则散在《智能体互联网时代…》与 D-466）。
6. 装机的 .ctree APK 对应哪个 git 提交（D-702 只记 sha256）；T88 修复「推断已装机（≥74d424d），未验证」。
7. PC 工作树 `server/certs` 是否含私钥且是否已 `git add`（`.gitignore` 不挡 `aneb_ip_key.pem`）。
8. `evidence/phase3/demo_results.jsonl` 计入「真实 run」是否曾有裁定；`results-contract-unit` 指向 `server/data/results` 是刻意守上传落点还是路径遗留。
9. 豆包免费档上限（累计已用 ≈105 轮）；F5/F6 提示词从未被裁。
10. 观察通道产物是否属于 spec 单一事实源范围；若不属，其权威文件是哪一份。

### E. 方法说明与限制

- 代码在本评估的 Linux 鲜克隆上以只读方式审读与实跑；未跑 Gradle（无 Android SDK），Android 单测结论来自源码阅读与提交记录。
- 九镜头读者 + 九核查者的完整输出（每镜头 40–65 KB，含每条发现的核查理由与命令）存于协调会话 scratchpad，未入仓；本报告引用的 file:line 均出自其中并经核查者复核。
- 综合阶段：工作流的批评者与计划起草者首轮只收到 5/9 镜头（摘要超长被截断）；重跑时因会话额度限制失败。本报告 §4–§7 由协调会话基于全部 9 镜头文件人工综合，首轮批评者的 10 项「发布前必核」全部由协调会话亲自复核通过（§B）。
- 会话归属靠提交说明与 D 条转述（作者均为同一 GitHub 账号，提交无会话署名）。
- 本报告不修改任何上游文件；所有修法建议由各属主按 CLAUDE.md 提交纪律（pathspec 提交、`git show --stat` 复核）落地。

---

*协调会话（云端）2026-09-05。上一版：[REVIEW_20260902.md](REVIEW_20260902.md)。协议：[PROTOCOL.md](PROTOCOL.md)。*
