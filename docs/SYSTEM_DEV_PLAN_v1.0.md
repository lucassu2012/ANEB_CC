# ANEB 系统开发计划 v1.0

> 依据:产品负责人 2026-07-17 项目重构决定。本文件是后续 ANEB 系统开发的**唯一指导文档**,方法论细节见《ANEB_Token与AI业务网络体验标准方法论_v0.9》。
> 标签体系沿用:[KNOWN]/[COMPUTED]/[INFERRED]/[COMMON]/[FRAME]/[GUESS] + 置信度。
>
> ⚠ **本文是 v1.0 基线,不随决策改写;增量以 `PLAN_ALIGNMENT_2026-07-17.md` 为准。**
> 已经改掉的最大一条是**部署形态**:本文多处按「同城/区域/中心三级各一实例」写
> (§4.2 部署、§5 Profile 2 端点矩阵、§6 的 M1/M2、§7 部署脚本、§9 第 3 项),
> 而 **D-48(2026-07-17,与本文同日)定为只保留单实例 E-01**——三级差分归因因此**不可得**,
> 归因退化为接入段绝对值加多维协变量(见 `PLAN_ALIGNMENT` §7 第 3 条)。
> 读到本文任何「三级」字样,请连同那一条一起读:**照本文规划外场行程,会按三倍规模
> 排向并不存在的镜像端**——这个错误真的发生过一次(D-283)。

---

## 1. 项目重构决定(产品负责人拍板)

ANEB 从单体开发模式重构为 **3 个子项目 + 1 个横切机制**:

- **P1 手机端 App 开发**(P1a 前台 UI 设计 / P1b 后台测量引擎)
- **P2 服务器侧开发**(按测试业务内容适配调整)
- **P3 ANEB 标准与业务模型开发**(Agent/AI 业务体验标准 + 现网真实业务的行为模拟规范)
- **横切机制:测试 Profile 体系**——前端 App 与后端服务器共同适配同一套 Profile,实现"一套方案适配多种业务模型"。

## 2. 总体架构

```
                ┌────────────────────────────────────┐
                │ P3 ANEB 规范与业务模型库(aneb-spec) │
                │ Profile描述文件 · KPI定义 · 评分规则 │
                │ 业务画像参数 · 结果Schema · 版本号   │
                └─────────┬──────────────┬───────────┘
              读取契约(数据)│              │读取契约(数据)
          ┌───────────────▼───┐    ┌─────▼──────────────────┐
          │ P1 手机端 App      │    │ P2 服务器侧             │
          │  P1a UI 壳         │ 测 │  token发生器(SSE)       │
          │  P1b 测量引擎      │◄──►│  上传汇 / Agent步进端点  │
          │  (含Profile3适配器) │    │  语音回环 / 测速参考端   │
          └─────────┬─────────┘    └────────────────────────┘
                    │ 另:Profile3 直连真实App服务端(豆包/DeepSeek等)
                    ▼
          统一结果 JSONL(单一Schema)
                    ▼
          分析与报告层(热力卡 · 归因矩阵 · 优化前后对比)
```

## 3. 三条架构铁律(先立规矩,后写代码)

**铁律 1:Profile 即数据,不是代码分支。**
每个 Profile 是一份声明式描述文件(YAML),由 P3 定义、P1/P2 解析执行。新增业务模型 = 新增一份 YAML,不改引擎代码。这是"一套方案适配多种业务"的唯一可持续实现方式;否则每加一个业务就 fork 一次代码,三个月后必然失控。[INFERRED, HIGH]

**铁律 2:引擎先行,UI 后行。**
P1b 测量引擎作为独立库/前台服务开发,自带最简调试界面即可产出外场数据;P1a 的 UI 是引擎的壳,排在数据闭环跑通之后。这样 D3"先做实践"不被 UI 工期阻塞。[FRAME 排序原则]

**铁律 3:所有 v1 指标客户端单侧定义。**
所有计分指标只用客户端时间戳(RTT 合成),不依赖端云时钟同步;服务端在 token 内嵌发送时间戳仅作诊断——客户端用到达间隔与内嵌间隔的差分序列剥离服务端发包抖动(该差分对时钟偏移不敏感)[COMPUTED, HIGH]。这一条同时解决了"Python 服务端 pacing 抖动污染网络抖动测量"的问题。

## 4. 子项目定义

### 4.1 P1 手机端 App 开发

**P1b 测量引擎(优先级最高)**
- 职责:解析 Profile 描述文件 → 执行测量会话 → 采集**无线上下文**(RAT/RSRP/SINR/小区ID/切换事件,来自 TelephonyManager)→ 输出统一 Schema 的 JSONL → 上报/导出。
- 关键模块:Profile 解释器、传输探针(Cronet/OkHttp 事件级计时,ms 精度)、SSE/token 流解析器、上传器、Agent 步进执行器、无线上下文采集器、会话记录器、(Profile 3)真实 App 适配器宿主。
- **技术栈裁决(需产品负责人确认)**:
  - A. **Kotlin 原生(推荐)**:唯一能拿全无线上下文(RSRP/小区)的路线——归因矩阵依赖它;Cronet 事件计时精度最好;前台服务支持长会话与移动性测试。[INFERRED, HIGH]
  - B. Flutter:跨平台好看,但无线上下文与精确计时都要走平台通道,增加抖动与开发面。[INFERRED, MED]
  - C. Termux/Python 原型:最快出数,但**拿不到无线上下文**,只能当一次性验证。此项修正我上一轮的 MVP 建议——Termux 路线因缺失归因所需的 radio_ctx 而降级为可选热身,不作为正式路线。[公开修正]
- iOS 说明:iOS 公开 API 不提供 RSRP/小区级无线信息 [COMMON, HIGH],故**安卓先行**是被迫的正确,iOS 版本仅作 Profile 1/3 的端到端参考,列入远期。

**P1a 前台 UI 设计(引擎稳定后启动)**
- 范围:测试发起(选 Profile/场景标签)、实时仪表(token 流可视化、瞬时 KPI)、历史记录与点位地图、结果分享卡片。设计基调:专业工具感(Speedtest 级完成度是及格线)。
- UI 不承载任何测量逻辑,只调引擎 API。

### 4.2 P2 服务器侧开发

- 职责:实现 Profile 所需的全部**可控参考端点矩阵**,按 P3 的业务画像参数运行:
  - `/v1/tokens`:SSE token 发生器(可配 T_srv、TPS、token 数、封装膨胀、思考静默段)——覆盖 A1/A2 模拟;
  - `/v1/upload`:上传汇(参考负载 10MB/100MB/1GB)——A3;
  - `/v1/agent/step`:Agent 步进端点(N 步串行工具调用模拟,可配每步 T_srv 与响应大小)——C1/C2;
  - `/v1/voice/echo`:语音回环端点(RTP/WebRTC echo,测 FRD/M2E 链路部分)——B1;
  - `/v1/speed`:基础测速端(或直接复用成熟测速件)——Profile 1;
  - 全端点在响应中内嵌服务端时间戳与序号(铁律 3)。
- 部署:同城/区域/中心三级各一实例(镜像同一份),三级差分即归因输入。
- 技术栈:**Python FastAPI(推荐)**——开发速度契合现有技能栈,pacing 抖动已由铁律 3 化解;若后续压测发现发包调度成为瓶颈,再以 Go 重写 token 发生器单模块 [INFERRED, MED]。
- "根据测试业务内容适配调整"的实现方式:P2 不为具体业务写死逻辑,只暴露参数化端点;业务差异全部体现在 P3 的 Profile 参数里(铁律 1)。

### 4.3 P3 ANEB 标准与业务模型开发(spec 仓库,单一事实源)

- 产出物(全部是数据/文档,被 P1/P2 消费):
  1. **Profile 描述文件库**(见第 5 章);
  2. **KPI 定义与评分规则包**(沿用方法论 v0.9 第 4/6 章,机器可读化);
  3. **业务画像参数集**:目标现网业务的流量行为模型;
  4. **结果记录 Schema**(方法论附录 B 的 JSON Schema 化);
  5. 版本号与兼容性规则(语义化版本,引擎声明支持的 schema 区间)。
- **目标业务清单 v1**:
  - Token/API 类(Profile 2 模拟对象):Kimi、Claude Code(Agent 长会话代表)、DeepSeek、通义千问 API;
  - 流行 App 类(Profile 3 真实测量对象,用户量更大):豆包、腾讯元宝、通义千问 App、DeepSeek App、Kimi App;
  - 实时语音类(Profile 4):豆包实时语音等。
  - 清单由产品负责人增删。
- **关键新增活动:业务画像采集**。"模拟真实业务行为"必须有实测参数,否则模拟参数就是 [GUESS]。方法:自有设备对目标业务抓包(加密流量仍可得:包时序/大小/方向/SNI/目的 IP;PCAPdroid 免 root 可用);对未做证书锁定的 App 可用 mitmproxy 解密自有账号流量拿到真实 token 时序 [COMMON, MED];提取请求大小分布、token 间隔分布、思考静默时长、工具调用节奏、会话时长 → 拟合为 Profile 参数。此活动同时产出副产品:各业务真实入云 PoP/IP 清单(规划归因直接可用)。

---

## 5. Profile 体系 v1(横切契约)

### 5.1 Profile 总表

| Profile | 名称 | 测什么 | 映射方法论 4类10型 | 客户端行为 | 服务端 | 主 KPI |
|---|---|---|---|---|---|---|
| **Profile 1** | 基础网络 | L0 原子:上下行速率、RTT、抖动、丢包、握手、入云多点时延 | L0 层 | 标准测速 + 多 PoP 探测 | P2 测速端 + 公共 PoP | UL/DL、RTT、jitter、入云时延 |
| **Profile 2** | Token 类业务模拟 | 可控 token 流 / 长思考 / 上传 / Agent 步进 | A1、A2、A3、C1、C2 | 按 descriptor 回放业务行为(Kimi/Claude Code/DeepSeek/千问画像) | P2 tokenperf 端点矩阵(三级) | TTFT、NetTTFT、DTR、TSR/SDR、SNO p99、SSR、TCTI、TTUC |
| **Profile 3** | 流行 App 真实业务 | 豆包/元宝/千问等真实端到端 | A1、A3(真实轨) | 适配器驱动真实 App + 帧级打点 | 无(真实业务服务端) | 端到端 TTFT、SDR、RCT + 部分归因 |
| **Profile 4** | 实时 AI 语音 | 双工语音链路 | B1 | 语音客户端(先回环,后真实语音 App) | P2 语音回环端点 | FRD、M2E、BRL、抖动、丢包 |
| 扩展位 P5+ | AIGC 下载 / 实时视觉 / 端云协同 | — | A4、B2、D1 | 后续版本 | 后续版本 | — |

### 5.2 Profile 描述文件示例(契约的样子)

```yaml
profile_id: P2.A1.kimi-chat
schema_version: "1.0"
maps_to: A1
source_portrait: kimi-app-capture-2026Q3   # 业务画像出处(可追溯)
server:
  endpoint: /v1/tokens
  t_srv_ms: 300        # 服务端处理时延真值
  tps: 28              # 由画像拟合
  tokens: 620
  framing: sse-json
  think_gaps: []       # A2 型在此配置思考静默段
client:
  connection: [cold, warm]   # 冷/暖连接各测
  repeats: 20
  record: [ttft, token_arrivals, radio_ctx, seg_timestamps]
kpi: [TTFT, NetTTFT, DTR, TSR, SDR, RCR]
```

Profile 3 的 descriptor 将 `server` 段替换为 `adapter: doubao-v1` + `prompt_set: standard-20`;Profile 4 替换为语音参数段。**契约冻结 = schema_version 1.0 发布,此后 P1/P2 并行开发互不阻塞。**

---

## 6. 开发路线图(里程碑与验收)

| 里程碑 | 周期 | 内容 | 验收标准 |
|---|---|---|---|
| **M0 契约冻结** | 第 1 周 | Profile Schema v1 + 结果 Schema v1 + 五仓库骨架 + 示例 descriptor ×4 | P1/P2 双方能解析同一 descriptor 跑通空流程 |
| **M1 核心闭环** | 第 2–3 周 | P2 端点矩阵(tokens/upload/agent/speed)三级部署;P1b 引擎最小版(Kotlin,Profile 1/2) | 实验室跑通 Profile 1+2,JSONL 落盘含 radio_ctx;同点位复测 TTFT 变异系数 ≤10% |
| **M2 外场 MVP** | 第 4–5 周 | 6–8 点位 × 忙闲 × 双运营商外场;分析脚本出热力卡 + 三级归因初判 | 产出第一份《城市 AI 业务网络体验热力卡与归因报告》(带数据进局点的弹药) |
| **M3 真实业务与语音** | 第 6–8 周 | 业务画像采集(抓包→参数拟合→回填 Profile 2);Profile 3 首批适配器(建议豆包 + DeepSeek);Profile 4 语音回环 | 适配器打点误差 ≤1 帧(≈33ms);画像参数替换 [GUESS] 初值 |
| **M4 产品化** | 第 9–12 周 | P1a UI(Compose)+ 报告自动生成;Profile 库扩展(A3/A4 并入) | 非开发者可独立完成一次点位测试并导出报告 |

计划为单人 + AI 辅助开发(Claude Code)节奏 [FRAME 计划, MED];M3 的适配器与画像采集是最大不确定项,预留 1–2 周缓冲。

## 7. 仓库结构与运作模式(Agent 原生开发)

```
aneb-spec/            # P3:profiles/ schemas/ scoring/ portraits/ docs/  ←单一事实源
aneb-server/          # P2:FastAPI 端点矩阵 + 三级部署脚本
aneb-engine-android/  # P1b:Kotlin 测量引擎(库 + 前台服务 + 调试面板)
aneb-app-ui/          # P1a:Compose UI 壳(M4 启动)
aneb-adapters/        # Profile 3:每 App 一个适配器模块(视为易耗品,App 改版即重写)
```

运作规则:每仓库自带 CLAUDE.md,声明所依赖的 aneb-spec 版本;**一切跨仓库变更先改 spec、后动代码**;契约变更走 spec 仓库的版本递增。三个子项目由此可并行推进而不互相踩踏——这套结构同时是给编码 Agent 的任务边界。

## 8. 风险清单

| 风险 | 等级 | 缓解 |
|---|---|---|
| Profile 3 适配器脆弱(App 改版/风控) | 高 [INFERRED, HIGH] | 适配器按易耗品设计;账号池 + 频控;打点走无障碍节点监听为主、录屏逐帧为兜底 |
| 业务画像参数失真 | 中 [INFERRED, MED] | M3 抓包实测替换初值;descriptor 标注 source_portrait 可追溯 |
| 证书锁定导致无法解密真 token 时序 | 中 [COMMON, MED] | 退化为包时序/大小分析,精度足够拟合节奏参数 |
| 服务端发包抖动污染测量 | 已化解 | 铁律 3 差分法 [COMPUTED, HIGH] |
| 长会话/移动性测试的系统限电 | 中 | 前台服务 + 白名单设置;测试机常电 |
| 外场流量成本(百 MB 级上传×多轮) | 低 | 大流量卡;上传档位按场景裁剪 |

## 9. 待产品负责人拍板(本轮)

1. **P1 技术栈**:A Kotlin 原生(推荐)/ B Flutter / C 先 Termux 热身。
2. **P2 技术栈**:Python FastAPI(推荐)/ Go。
3. **云平台与三级部署区域 + 试点城市**(承接上轮未决):决定 P2 部署脚本目标。
4. **Profile 3 首批两个 App**:推荐豆包 + DeepSeek(一重一轻,覆盖两档适配难度)。

*v1.0 · 2026-07-17 · 拍板后进入 M0*
