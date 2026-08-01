# ANEB 进展对齐报告——按《系统开发计划 v1.0》架构映射

> 2026-07-17。权威指导 = [SYSTEM_DEV_PLAN_v1.0.md](SYSTEM_DEV_PLAN_v1.0.md)(产品负责人拍板,"3 个子项目 + 1 个横切机制")。
> 本文把**已交付的实际进展**逐项挂到 P1a/P1b/P2/P3 + Profile 横切上,标注完成度与缺口。
> 现状事实源:本仓 `feat/result-dev-v2`(HEAD d5a1379)、[DECISION_LOG.md](DECISION_LOG.md) D-1..D-46、[PROFILE_FRAMEWORK.md](PROFILE_FRAMEWORK.md)、Codex 维护的 TEST_SERVER_CAPABILITIES.md(E-01 权威能力合同)。

---

## 0. 一页结论（v2 更新，2026-07-18，D-47..D-58 后）

| 计划单元 | 完成度 | 一句话状态 |
|---|---|---|
| **P1b 测量引擎** | **≈95%** | 计划 8 个关键模块**全部交付**并真机验证（含 Profile 3 适配器宿主 D-49）;仅剩真实 App 探针宿主的深化 |
| **P1a 前台 UI** | **超前**(计划 M4 才启动) | 三模式屏+动态仪表+历史(四类混排)/结果/分享已达 Speedtest 观感;严守 D-02 |
| **P2 服务器侧** | **≈75%**(等价矩阵) | 5 类端点全有等价实现(Go, aneb-server/0.7.0, Codex 部署);三级部署→单实例 E-01(D-48 拍板,不再是缺口);Profile 2 真实标定建议已交付 Codex(D-58) |
| **P3 标准与业务模型** | **≈70%(从 40% 大幅推进)** | spec 治理✓(对齐-1)、4-facet+打分规则✓、客户端 Profile 数据化✓;**业务画像采集从 [GUESS] 推进到三口径真实实测**（Profile 3 UI 层 4 App + 网络层 4 App + Profile 2 API token 标定 n=5,D-50..D-58）;剩:画像网络层 token 明文(需 mitm)、多样本置信 |
| **横切 Profile 体系** | **服务端+客户端双侧兑现** | 服务端 profiles/*.json 双客户端互证;客户端 Profile 已数据化(D-46);spec/ 目录统一治理(profiles/schemas/scoring/portraits/calibration/adapters) |
| 里程碑位置 | **M1 完成超出、M3 大幅推进(画像采集三口径真实数据)、M4 部分超前;M0 治理已补(spec/)、M2 未启动(外场,用户关闭)** | 详见 §6;画像详见 `docs/PROFILE3_PORTRAIT_2026-07-18.md` |

**关键跃迁(v1→v2)**:v1(D-47)时 P3 最大缺口=画像采集全 [GUESS];v2 已用无障碍观察(UI 层)+PCAPdroid 抓包(网络层)+Kimi API 直调(token 层)三口径采到 4 个真实 App/API 的实测画像,ANEB 首次拥有真实 AI 业务体验数据。三口径严格分标(UI 呈现≠网络传输≠API token)。

---

## 1. P1b 测量引擎(计划:优先级最高)

计划关键模块逐项对照:

| 计划模块 | 状态 | 实现锚点 |
|---|---|---|
| Profile 解释器 | ✅ | 客户端自动获取服务端 `/profiles`(相位驱动 `ScenarioRunner`);assets 回退;profile_versions 落库分组横比(D-32) |
| 传输探针(事件级计时,ms 精度) | ✅ | `AnebClient`(OkHttp 事件级 TimingFactory;NO_PROXY/绑定网/不重试三红线);Cronet QUIC 已评估,受公共 CA 限制列为 P2-C06(D-21) |
| SSE/token 流解析器 | ✅ | `/stream` 逐 token 到达序列 → TTFT/T1(剥服务端 dwell)/TPS/ITL/卡顿;实时 token 计数(D-27) |
| 上传器 | ✅ | `uploadBurst`(R-07 写口径)+ 合成整形路径回执确认口径(D-43 教训:两口径分场景) |
| Agent 步进执行器 | ✅ | `/toolloop` 串行步进(TCTI 族) |
| 无线上下文采集器 | ✅ | RAT/RSRP/SINR/小区 ID(TelephonyManager)→ 落库+结果页 `ResultRadioSummary`+drive_test 标注 |
| 会话记录器 | ✅ | Room v13:`TestRun`(report_body JSON)+ `voice_result`(D-42)+ `synthetic_result`(D-45);历史页统一混排(D-46) |
| (Profile 3)真实 App 适配器宿主 | ❌ 未做 | 计划 M3 项;无障碍/录屏打点宿主未设计 |

**铁律 3(客户端单侧定义)符合度:✅ 完全符合,且是同一手法。** 本项目独立收敛到了与计划相同的差分法:T1 = 客户端墙钟 − 服务端内嵌 dwell(对钟偏不敏感);语音 M2' = 到达间隔 − 服务端 sched_us 间隔差分(精确剥服务端调度抖动,D-38);M4 TTS-TTFB 剥 (pre_write−commit_recv)。服务端全端点内嵌时戳/序号(chunk_us、sched_us、turn_summary 三时戳、UDP 回显)= 计划要求的服务端配合面。[KNOWN]

**计划未列但已交付的引擎能力**(超出项):合成弱网双合同客户端(容量整形 D-43 / 受控中断恢复 D-40)、语音受控断连连续性(D-41)、UDP ANEB1 应用探针(D-44,未返回率≠丢包率口径)、背景伴流自拥塞弱网 contend:N(D-36)、跨网迁移恢复(D-23)。

## 2. P1a 前台 UI(计划:引擎稳定后启动,M4)

**实际超前完成大半。** 三模式屏(Token 体验/网络基本性能/AI 实时交互,数据驱动 `TestModeProfiles.ALL` 注册表——加模式=加 profile 条目)、SpeedTest 级动态仪表(实时 RTT/吞吐驱动指针+火花线,相位门控 D-28)、历史页(混排三类记录)、结果页(AQS 分解+行为特征与网络建议卡+无线上下文)、分享卡、设置页。**"UI 不承载任何测量逻辑,只调引擎 API"= 本仓 D-02 红线,自始遵守。** [KNOWN]

计划的 UI 范围内未做:点位地图(依赖外场 M2)。

## 3. P2 服务器侧

**技术栈现实:Go(非计划推荐的 FastAPI)。** 部署权已移交 Codex(D-35,产品负责人裁定),现网 aneb-server/0.7.0,能力合同=Codex 维护的 TEST_SERVER_CAPABILITIES.md(D-37)。计划自己预留了"压测瓶颈时以 Go 重写"的终态——现实直接处于终态,且 pacing 抖动已由铁律 3 差分化解,**建议维持 Go、关闭该拍板项**。[INFERRED, HIGH]

计划端点矩阵对照:

| 计划端点 | 现网等价物 | 差异 |
|---|---|---|
| `/v1/tokens` SSE(T_srv/TPS/膨胀/思考段) | `/stream`(rate_tps/tokens/TTFT-dwell 注入/rate_schedule/SSE 批帧/思考停顿——Step2 机制层全齐) | 机制✅;**画像参数未标定**(P3 缺口) |
| `/v1/upload`(10MB/100MB/1GB 档) | `/upload`(≤64MiB,64KiB 读块到达时戳) | 100MB/1GB 档需扩(已列 TK-4 扩档,需 Codex 配合) |
| `/v1/agent/step` | `/toolloop` | ✅ |
| `/v1/voice/echo`(RTP/WebRTC 回环) | `/realtime-sim`(WS 双工仿真:计划帧/打断/受控断连/逐帧 sched_us) | 形态不同:WS 仿真**强于**纯回环(可控轮次语义);RTP 形态留待 Profile 4 真实语音阶段评估。**2026-08-01 补(T10,D-377)**:该等价物**不在本树**——`server/main.go` 注册的 9 条路由无语音端点,handler 权威在 **Codex 树** `handlers_realtime_sim.go`(`RealtimeSimSession.kt:18-19`),故**本仓不可构建/重新部署它**;而 `WEIGHTS_VOICE_SIM` 有 **0.35 权重(M4+M5+M6)只在该端点上可测**。RTP 形态的前置也**不是端点**:App 零 `AudioRecord`/`AudioTrack`、无 `RECORD_AUDIO`,真实 M2E 链路整段未接,详见 `PROFILE4_VOICE_LOOPBACK_SPEC.md` §1.1/§5.5 |
| `/v1/speed` | `/echo`+`/download`(≤1GiB)+UDP ANEB1 探针 | ✅ |
| (计划未列)合成弱网 | `/synthetic/weak-capacity-latency-v1` + `/synthetic/weak-recovery-v1`(防伪回执合同) | 超出项 |
| 时间戳内嵌(铁律 3) | 全端点已内嵌 | ✅ |

**缺口:三级部署(同城/区域/中心)未做**——当前单实例 E-01。这是 M2 归因矩阵的输入,依赖计划 §9-3 拍板(云平台/区域/试点城市)。[KNOWN]

## 4. P3 标准与业务模型(最大缺口所在)

| 计划产出物 | 状态 | 说明 |
|---|---|---|
| Profile 描述文件库 | 🟡 半 | **服务端侧✅数据文件**:`profiles/*.json`(s1/s2/s3@0.3.0,相位声明式,版本化)——铁律 1 在服务端已兑现,且被两个独立客户端消费互证;**客户端侧❌代码**:`TestModeProfile.kt` 是结构化 Kotlin 注册表(4-facet 全量),未外置为 YAML/JSON——铁律 1 的偏离点 |
| KPI 定义与评分规则包 | 🟡 半 | 打分全链在代码(KpiCalculator/AqsScorer:权重表 WEIGHTS_TOKEN_MM/TXT/VOICE/VOICE_SIM、锚点、否决)+文档(PROFILE_FRAMEWORK §2);**未机器可读化独立成包** |
| 业务画像参数集 | ❌ **未做** | 当前 s3 多模态/TPS/思考段等参数全部 [FRAME/GUESS] 初值;Step2 真实平台标定(kimi/deepseek/qwen)一直阻塞于 API key(用户资源);抓包画像活动(PCAPdroid/mitmproxy)未启动——**计划 M3 的核心活动,也是"模拟真实业务"成色的分水岭** |
| 结果记录 Schema | 🟡 半 | `run.report_body` JSON 结构稳定(往返测试锚定)但无独立 JSON Schema 文件与版本治理 |
| 版本号与兼容性规则 | 🟡 半 | 服务端 profile 版本化(0.2.x/0.3.0)+客户端容忍未知字段+AQS_VERSION_* 表 id;无 spec 仓级 schema_version |
| 目标业务清单 v1 | ❌ App 类全未触 | Token/API 类已模拟(未标定);豆包/元宝/千问 App/DeepSeek App/Kimi App(Profile 3)零进展;豆包实时语音(Profile 4 真实轨)零进展 |

## 5. 横切:Profile 体系

**计划的核心命题"前端 App 与后端服务器共同适配同一套 Profile"在 token 类上已是运行事实**:服务端 `profiles/` 单一事实源 → 本项目客户端与 Codex App 两个独立实现各自解析执行同一 descriptor,并对 D1(12MiB download_burst 精确字节)、恢复时长(2084–2227ms vs 2151ms)、UDP 未返回率(0% vs 0%)三度跨实现互证。[KNOWN] 这正是 M0"双方能解析同一 descriptor"验收标准的强化版(计划要求空流程,现实是全 KPI 互证)。

**与计划契约形态的差距**:现行 descriptor 是服务端相位 JSON(server 段),未含计划 YAML 示例中的 client 段(connection/repeats/record)与 kpi 段——这两段目前在客户端代码/facet 注册表里。走向计划形态 = 把 TestModeProfile 的 facet2/facet4 与采集配置外置进 descriptor。[INFERRED]

### 5.1 计划点名的字段 ← 实现里的名字(2026-07-30 实测)

计划 §5.2 的 descriptor 示例含 10 个 snake_case 字段名,**7 个在本仓的代码与 spec 里一次都没出现过**。
逐个查过后分三类——**区别要紧:名字漂移是静默的不一致,而「还没做」是正常的待办**:

| 计划里的名字 | 实况 | 类别 |
|---|---|---|
| `radio_ctx` | 能力有(`RadioCollector` 采 rsrp/sinr/pci/tac/arfcn、Room 存、App 内部消费),但**导出契约里没有**,且实现从不用这个名字 | **名字漂移 + 导出缺口**(D-284,已出接线规格) |
| `token_arrivals` | 能力有,实现叫 **`arrivals`**(`ApiProbe` / `AnthropicSseAdapter` / `ApiProbeKpi`) | **名字漂移**(仅命名,能力齐备) |
| `t_srv_ms` | 本仓找不到任何近似名——但它是**服务端**配置,而服务端在 Codex 那棵树,**本树看不到** | **查不了**(≠ 不存在) |
| `maps_to` / `prompt_set` / `think_gaps` / `seg_timestamps` | descriptor 结构与 Profile 3 / A2 型的采集项,按路线图属 M3 | **未建**(正常待办) |

**为什么这条不做成守卫**:「漂移」与「还没做」的区别**推导不出来**——硬立一条「计划点名的字段必须存在」,
会把 M3 的正常待办全报成缺陷,正是本层拒绝的那种吵闹守卫。故此处只做一次性对账、把结论写下来,
下一个人不必重新推导(D-295)。

## 6. 里程碑映射

| 里程碑 | 计划验收 | 现状 |
|---|---|---|
| M0 契约冻结 | 双方解析同一 descriptor 跑通空流程 | 🟡 实质超额(全 KPI 跨实现互证)、治理欠账(无独立 spec 仓/schema_version/结果 Schema 文件) |
| M1 核心闭环 | 实验室 Profile 1+2,JSONL 含 radio_ctx,TTFT CV≤10% | ✅ 完成并超出:真机(P40/5G/4G)Profile 1+2+4(仿真轨),Room+report_body 含 radio_ctx;取证模式 ×3 重复;分数自愈合同(D-29) |
| M2 外场 MVP | 6–8 点位×忙闲×双运营商,热力卡+三级归因 | 🟡 **半**(2026-07-29 复核)：**分析层已就绪并加固**(热力卡/归因/稳定性/优化前后对比/发布前自检,501 条守卫全绿、`verify_all` 13/13,含单层级降级路径);**三级归因按 D-48 已不可得**(单实例 E-01),归因退化为接入段绝对值+多维协变量;**仅缺外场采集本身**(网格提案 v2.0 已按单层级重算:160 run/0.75 外场日,或 n=11 的 352 run/1.65 天) |
| M3 真实业务与语音 | 画像采集回填;Profile 3 首批适配器;Profile 4 语音回环 | 🟡 半:语音回环侧超额完成(WS 双工仿真+M1–M6 全实测);画像采集与适配器未动 |
| M4 产品化 | UI+报告,非开发者可独立完成测试 | 🟡 部分超前:UI 已达标;报告自动生成有雏形(ReportFormat/ReportScreen);"非开发者独立完成"未验收 |

## 7. 计划 §9 拍板项——**已全部落定(产品负责人 2026-07-17,D-48)**

1. **P1 技术栈 = Kotlin 原生** ✅ 关闭(按现实更新)。
2. **P2 技术栈 = Go** ✅ 关闭(按现实更新;Codex 维护 aneb-server/0.7.0)。
3. **部署形态 = 单实例 E-01** ✅ 拍板(放弃三级同城/区域/中心)。**影响**:M2 归因失去三级差分输入,归因改以单点参考端+多维协变量(无线上下文/UDP 未整形协变量/忙闲/双运营商)为主;计划 §2 架构图三级部署段按此收缩。
   **2026-07-29 补记**:产品负责人再次确认"利旧现有服务器、不再增加新服务器",并**首次点名试点城市=深圳**(D-48 只答了实例形态,城市悬空至此)。同日复核发现 **`M2_GRID_DESIGN_PROPOSAL` v1.0(2026-07-25)从未与本条对账**——它晚于 D-48 八天,仍按三层级排 480 run 并把"三层级必须齐"列为不可交易;若照批,行程会按三倍规模排向并不存在的镜像端。提案已升 v2.0 重算并写明此事(D-283)。
4. **Profile 3 首批 App = 豆包 + DeepSeek** ✅ 拍板(计划推荐原案,一重一轻两档适配难度)。M3 适配器前置就位。

## 7.5 计划正文中**已失效的字样**（一处集中枚举，2026-08-01 新增）

> 计划 v1.0 是不随决策改写的基线，增量以本报告为准。问题是：失效字样此前**散在本报告三处**
> （§3 表格、§6 里程碑行、§7 拍板 3），没有任何一处能让读者**枚举**「计划里哪些话已经不算数了」。
> 新读者按计划字面读到的仍是原话。本节把它们收在一起，此后失效一条就在这里加一行。

| 计划位置 | 已失效字样 | 现行事实 | 出处 |
|---|---|---|---|
| §2 架构图 / §6 M2 行 | 「三级部署（同城/区域/中心）」「三级归因/三级差分」 | 单实例 E-01；归因改以单点参考端+多维协变量（无线上下文/UDP 未整形协变量/忙闲/双运营商）为主 | D-48（2026-07-17 拍板）；本报告 §3/§6/§7-3 |
| §5.1 Profile 3 行 | 「客户端行为 = **适配器驱动真实 App** + 帧级打点」 | **Profile 3 是旁观，不是驱动**。观察模式 only、绝不 `performAction`、绝不代启动 App（理由：动真实账号是用户红线）。任何「驱动/编排真实 App」的能力宣称一律不成立 | **D-385**（2026-08-01）；红线出自 D-49；`spec/adapters/INSTRUMENTATION_SPEC.md` §0.3 M-1 |
| §8 风险表（适配器脆弱） | 缓解写「**账号池** + 频控」 | **不建账号池**——与「自有账号、自有设备、账号是用户资源」红线直接冲突。改用四条不碰账号的缓解：观察 only 零注入／额度与频次最小化／仅观测自身／不解密不 MITM。另立计划未点名的第三类风险：OEM 系统侧五条（共同形状是**失败时静默出错值或静默无数据而不报错**），规定为采集前置检查表 | **D-386**（2026-08-01）；红线出自 D-49/D-50；`INSTRUMENTATION_SPEC` §5.2/§5.3 |
| §6 M3 行 | 「适配器打点误差 ≤1 帧（**≈33ms**）」——**未失效，但口径此前从未定义** | 参照系定为**呈现口径**（相对像素上屏）；交互口径拆为独立测量项 `A0→A0′`，不称「误差」；门限用「1 帧」表述，毫秒值**按实测刷新率换算、不硬编码 33**（60/90/120Hz 上一帧分别是 16.7/11.1/8.3ms） | **D-384**（2026-08-01）；`INSTRUMENTATION_SPEC` §3.1/§3.4 |

## 7.6 `PROFILE_FRAMEWORK §4.1`(语音)与实现的差集(一处集中枚举,2026-08-01 新增)

> **为什么不并进 §7.5**:§7.5 的标题限定是「**计划正文**中已失效的字样」,而本节四条是
> **另一份文档**(`docs/PROFILE_FRAMEWORK.md`)与实现的差集。塞进去会让 §7.5 自己的标题变成假的。
> 两节同构、互为指引:失效字样看 §7.5,框架↔实现差集看这里。
>
> **为什么现在才有这一节**:`PROFILE_FRAMEWORK §4.1` 是 M 组口径的**上位权威**——全仓
> **52 处**代码与 spec 逐字点名它(`AqsScorer.kt` 11 处、`KpiCalculator.kt` 10 处、
> `VoiceRunner.kt:20`、`weights.yaml:58`、`vetoes.yaml:22`、`anchors.yaml:83` …),
> 而**两份文档之间从没对过账**(`RADIO_CONTEXT_WIRING_SPEC.md:37` 记的正是这个形状)。
> 差集由 T10 规格 `PROFILE4_VOICE_LOOPBACK_SPEC.md` §5.7 逐条取证,大脑 2026-08-01 裁示 a–d 入册、e 走裁决。

| §4.1 怎么说 | 实现现状 | 性质 / 出处 |
|---|---|---|
| **(a)** 「音频需**独立媒体端点(非 token 流)**」 | v1 用 `/api/v1/stream` + `/api/v1/upload`,即 token 流端点(`server/main.go:37-38`);规格 §4.3 自承「`/stream` 帧路径与语音 v1 的 M2 是同一条」 | **正面矛盾**,是 **D-31「零服务端部署」的直接后果**。故 §1.1 那句「测的是语音要走的网络承载、不是音频链路」与 §4.1 的这条要求**是同一件事的两种说法**——§4.1 写成前置条件,规格写成事后边界 |
| **(b)** 「权重向 M 组 + N2 抖动 + **C1/C2 稳定性**倾斜;引入**类 E-model 的时延-中断联合惩罚**」 | `WEIGHTS_VOICE`/`WEIGHTS_VOICE_SIM` 两表**均无 C1/C2、无联合惩罚**(`weights.yaml:57-80`) | **未实施且从未登记**。规格 §2 逐字抄了权重却没核这条差集 |
| **(c)** 「Opus **~24–40 kbps**」 | 实现为 160 B / 20 ms ＝ **64 kbps**(`VoiceRunner.kt:80/83`),是框架业务模型的 **1.6–2.7 倍** | **偏离,未登记**。现由 `validate_voice_plan.py` 的 `derived_nominal_kbps` **重算**钉住,改帧参数即报 |
| **(d)** 子场景「连续对话／打断插话／**长时静音保活**」 | 生产端已登记 VC-1/VC-2/VC-3,其中 **VC-2「barge-in 突发帧」与 VC-3「静音期心跳」标注为"未接入"**(`TestModeProfile.kt:502-515`) | **部分未实施**;规格 §0 盘点表原漏列 |
| **(e)** 「**丢帧可直接测**」＋质量目标「音频丢帧 <1%」 | `voice_realtime.metricSpecs` 的 `FRLOSS.measurability = NOT_MEASURABLE`、`scored=false`;而 `PROFILE_FRAMEWORK §5` 红线又写「丢包不设一等门限(TCP+应用层不可直接测…)」 | **⏳ 待裁决(不入册为已定)**——**框架内部 §4.1 与 §5 自相矛盾,两处必须改一处**。大脑 2026-08-01 记:怀疑两句说的是不同层(应用层帧丢失＝seq 缺口可测 vs IP 层丢包不可称),裁定前将读原文,若属层混淆则裁「§4.1 限定为应用层 seq 缺口口径」 |

## 8. 沿计划架构的增量对齐路径(不推倒重来)[FRAME 建议]

当前单仓(app+server/+profiles/+docs/)≈ 计划五仓的 monorepo 折叠,单人+AI 节奏下建议**先立 spec 目录、后拆仓**:

- **对齐-1 ✅ 已完成(2026-07-17,D-48 拍板当日落地)**:`spec/` 目录已建(README 治理规则+schema_version 1.0.0 起版;profiles/server 权威副本;schemas/result-run.schema.json;scoring/ 三 YAML 逐字导出+SpecScoringParityTest 反射对拍防漂移,红测验证;portraits/ 豆包+DeepSeek 占位标 PENDING-CAPTURE)。客户端 Profile 已数据化(spec/profiles/client + assets 镜像+加载器 fail-safe 回退,公共 API 零破坏,ClientProfileDataParityTest 双份对拍;真机烟测:三模式屏正常、无 SPEC_PROFILE_FALLBACK)。本轮为"导出+对拍"形态,代码反向引用 spec 为终态留待后续。
- **对齐-2(依赖拍板 3)**:~~三级部署脚本与区域实例~~ → **随拍板 3 取消**(单实例 E-01,不再增服务器)。M2 外场改为**单层级采集**:分析层已就绪(2026-07-29 加单层级降级说明),网格提案 v2.0 已按此重算工时;不买服务器时"分段"这一问能答到什么程度,见提案 §4.1(公共 PoP 做 L0 分层可本轮顺带做,真实业务端参照留 M3)。**余下阻塞只剩设备与外场行程本身。**
- **对齐-3(依赖用户资源/拍板 4)**:业务画像采集(抓包→拟合→回填 descriptor,替换 [GUESS];副产品=真实入云 PoP 清单)+ Profile 3 首批适配器。
- **对齐-4(持续)**:与 Codex 的服务端协作已天然符合"P2 按 P3 数据适配"模式(D-35/D-37 合同流程),spec 目录成型后把 TEST_SERVER_CAPABILITIES 与 profiles 的变更流程并入"先改 spec、后动代码"规则。

---
*对齐报告 v1 · 2026-07-17 · 后续进展沿本映射更新*
*v1.1 · 2026-07-29 · 刷新 M2 现状(分析层就绪、仅缺采集);补记试点城市=深圳与提案对账缺口(D-283)*
