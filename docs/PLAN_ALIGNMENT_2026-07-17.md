# ANEB 进展对齐报告——按《系统开发计划 v1.0》架构映射

> 2026-07-17。权威指导 = [SYSTEM_DEV_PLAN_v1.0.md](SYSTEM_DEV_PLAN_v1.0.md)(产品负责人拍板,"3 个子项目 + 1 个横切机制")。
> 本文把**已交付的实际进展**逐项挂到 P1a/P1b/P2/P3 + Profile 横切上,标注完成度与缺口。
> 现状事实源:本仓 `feat/result-dev-v2`(HEAD d5a1379)、[DECISION_LOG.md](DECISION_LOG.md) D-1..D-46、[PROFILE_FRAMEWORK.md](PROFILE_FRAMEWORK.md)、Codex 维护的 TEST_SERVER_CAPABILITIES.md(E-01 权威能力合同)。

---

## 0. 一页结论

| 计划单元 | 完成度 | 一句话状态 |
|---|---|---|
| **P1b 测量引擎** | **≈85%**(v1 范围) | 计划列的 8 个关键模块 7 个已交付并真机验证;缺 Profile 3 真实 App 适配器宿主 |
| **P1a 前台 UI** | **超前**(计划 M4 才启动) | 三模式屏+动态仪表+历史/结果/分享已达 Speedtest 观感;严格遵守"UI 不承载测量逻辑"(D-02) |
| **P2 服务器侧** | **≈70%**(等价矩阵) | 计划的 5 类端点全部有等价实现(Go, aneb-server/0.7.0, Codex 部署);缺三级部署(归因输入) |
| **P3 标准与业务模型** | **≈40%,最大缺口** | 4-facet 框架+打分规则+服务端 Profile 数据文件已冻结;**业务画像采集未做(参数仍 [GUESS] 初值)**、客户端 Profile 未数据化、无独立 spec 治理 |
| **横切 Profile 体系** | **服务端侧已兑现,客户端侧半兑现** | 服务端 profiles/*.json 被两个独立客户端(本项目+Codex App)共同消费并互证——"一套方案适配多种业务"在 token 类上已是事实 |
| 里程碑位置 | **M1 完成、M3 完成一半、M4 部分超前;M0 治理面欠账、M2 未启动** | 详见 §6 |

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
| `/v1/voice/echo`(RTP/WebRTC 回环) | `/realtime-sim`(WS 双工仿真:计划帧/打断/受控断连/逐帧 sched_us) | 形态不同:WS 仿真**强于**纯回环(可控轮次语义);RTP 形态留待 Profile 4 真实语音阶段评估 |
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

## 6. 里程碑映射

| 里程碑 | 计划验收 | 现状 |
|---|---|---|
| M0 契约冻结 | 双方解析同一 descriptor 跑通空流程 | 🟡 实质超额(全 KPI 跨实现互证)、治理欠账(无独立 spec 仓/schema_version/结果 Schema 文件) |
| M1 核心闭环 | 实验室 Profile 1+2,JSONL 含 radio_ctx,TTFT CV≤10% | ✅ 完成并超出:真机(P40/5G/4G)Profile 1+2+4(仿真轨),Room+report_body 含 radio_ctx;取证模式 ×3 重复;分数自愈合同(D-29) |
| M2 外场 MVP | 6–8 点位×忙闲×双运营商,热力卡+三级归因 | ❌ 未启动(依赖三级部署拍板+外场活动) |
| M3 真实业务与语音 | 画像采集回填;Profile 3 首批适配器;Profile 4 语音回环 | 🟡 半:语音回环侧超额完成(WS 双工仿真+M1–M6 全实测);画像采集与适配器未动 |
| M4 产品化 | UI+报告,非开发者可独立完成测试 | 🟡 部分超前:UI 已达标;报告自动生成有雏形(ReportFormat/ReportScreen);"非开发者独立完成"未验收 |

## 7. 计划 §9 拍板项的现实状态

1. **P1 技术栈** → **已被现实回答:Kotlin 原生**(计划推荐 A;无线上下文/前台服务/Compose 全在用)。建议关闭。
2. **P2 技术栈** → **已被现实回答:Go**(Codex 维护 0.7.0;计划的"瓶颈终态"直接到位)。建议关闭。
3. **云平台与三级部署区域+试点城市** → **仍待拍板**(当前仅单实例 E-01=阿里云华南)。M2 的前置。
4. **Profile 3 首批两个 App**(推荐豆包+DeepSeek)→ **仍待拍板**。M3 适配器的前置。

## 8. 沿计划架构的增量对齐路径(不推倒重来)[FRAME 建议]

当前单仓(app+server/+profiles/+docs/)≈ 计划五仓的 monorepo 折叠,单人+AI 节奏下建议**先立 spec 目录、后拆仓**:

- **对齐-1(可立即做,无外部依赖)**:仓内新建 `spec/` 目录 = aneb-spec 雏形——迁入 profiles/、新增结果 JSON Schema、KPI/权重表导出为机器可读 YAML(代码引用它而非反向)、schema_version 起版。客户端 TestModeProfile 改为解析 spec 数据(铁律 1 客户端侧补课)。
- **对齐-2(依赖拍板 3)**:三级部署脚本与区域实例 → M2 外场。
- **对齐-3(依赖用户资源/拍板 4)**:业务画像采集(抓包→拟合→回填 descriptor,替换 [GUESS];副产品=真实入云 PoP 清单)+ Profile 3 首批适配器。
- **对齐-4(持续)**:与 Codex 的服务端协作已天然符合"P2 按 P3 数据适配"模式(D-35/D-37 合同流程),spec 目录成型后把 TEST_SERVER_CAPABILITIES 与 profiles 的变更流程并入"先改 spec、后动代码"规则。

---
*对齐报告 v1 · 2026-07-17 · 后续进展沿本映射更新*
