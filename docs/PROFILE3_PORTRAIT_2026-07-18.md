# Profile 3 业务画像采集成果快照（2026-07-18）

> SYSTEM_DEV_PLAN §4.3「业务画像采集」M3 里程碑的阶段成果。本文汇总已采集的 **UI 呈现层**
> 真实 App 观察数据（无障碍事件观察，非抓包）。**网络层画像（PCAPdroid）仍 PENDING**，
> 与本层严格分标（计划铁律 3）。权威数据在 `spec/portraits/*.yaml` 的 `observed_ui_layer` 段。

## 1. 一页成果

计划 §4.3 要求「模拟真实业务行为必须有实测参数，否则模拟参数就是 [GUESS]」。本阶段用
**无障碍观察模式**（P1b 适配器宿主，D-49~D-56）在 P40 真机上采到 4 个主流对话 App 的
UI 呈现层端到端 TTFT 与流式节奏——**ANEB 首次拥有真实 AI App 业务体验实测数据**，
不再是 [GUESS] 初值。

| App | 包名 | UI 栈 | 端到端 TTFT | 流式节奏 cadence | 采集方法 | 结果 |
|---|---|---|---|---|---|---|
| 豆包 | com.larus.nova | 原生 View | **1984 ms** | 100 ms（8 轮稳定） | v3 簇分割 | ✓ |
| DeepSeek | com.deepseek.chat | 自绘 Compose | **500 ms** | 同帧合流 | v4 密度谱 | ✓ |
| 通义千问 | com.aliyun.tongyi | UC WebView | **1203 ms** | 66 ms | v3+v4 互证 | ✓ |
| Kimi | com.moonshot.kimichat | 复杂 Compose | — | — | 三法均不适配 | 诚实缺席 |

**覆盖三种主流 Android UI 栈（View / Compose / WebView），方法对 3/4 App 有效。**

## 2. 口径边界（必读，防误用）

- **本层 = UI 呈现口径**：无障碍事件观察到的「发送 → 响应首字上屏」延迟，**含 App 渲染管线**，
  ≈帧级精度上界（16–33ms）。**≠网络 ITL/TTFT**，与 Profile 2 服务端仿真口径**严格分标**，
  两层数值不可互比、不可互填（D 红线 / 计划铁律 3）。
- **恒 LOW/INCONCLUSIVE**：观察模式不构成测量宣称；单次/少样本，非统计置信。
- **网络层仍 PENDING**：`spec/portraits/*.yaml` 的 `params` 段（请求大小/token 间隔/思考静默
  /PoP·IP）全为 null，待 PCAPdroid 抓包（M3 网络层采集）回填，届时 `source_portrait` 才脱离
  PENDING-CAPTURE。**当前不得以本层数据反推或声称网络层画像。**

## 3. 方法学沉淀（TTFT 观察三代 + 两红线）

采集方法在真机迭代中演进（D-50~D-56），核心发现：**无障碍事件测 TTFT 依赖 App 事件流结构，
非万能**——不同 UI 栈需不同方法：

- **v1 input-clear 锚点**（输入框清空启发式）：豆包 View 容器重建不发 TEXT_CHANGED、DeepSeek
  Compose 无 text 载荷 → 均失效（D-51）。
- **v2 点击锚点**（TYPE_VIEW_CLICKED）：豆包自定义 View 不派发 CLICKED → 失效；标准控件 App 可用（D-52）。
- **v3 簇分割**（>400ms 静默分簇）：思考期 UI 静止的栈成立（豆包 1984ms）；播放动画的栈失效（D-52/53）。
- **v4 密度谱**（事件密度结构性跃变）：补 v3，思考期动画栈成立（DeepSeek 500ms）；两法对千问互证（D-55/56）。
- **两条健壮性红线**（D-56）：①发送场景门控（会话须有真实输入活动才认发送场景，否则 TTFT null——
  修 generic 脏值）；②合理性上界 30s（超真实 AI 首字上界的结构错配脏值 → null——修 Kimi 54558ms）。

**Kimi 如实记为方法边界**：三法均不可靠，诚实 null 优于接受 54558ms 脏值（R-10）。

## 3.5 网络层画像（D-57 PCAPdroid 抓包，新增）

用 PCAPdroid（免 root 模拟 VPN，观察模式只读 SNI/IP/字节，不解密）采到 4 App 的**真实入云拓扑**
（计划 §4.3「真实入云 PoP/IP 清单」，归因直接可用）——不同大模型 App 用不同云基础设施：

| App | 云基础设施 | 对话主通道（实测） | 入云端点/IP |
|---|---|---|---|
| 豆包 | 字节自有 `*.doubao.com` | **WebSocket + HTTPS API** | wss100-normal-lq / api5-normal-hl / frontier5-audio-ws-lq（音频）;单轮 ~10–18KB |
| 千问 | 阿里/UC 夸克 `upaas.quark.cn` | HTTPS/TLS 443 | unpm-upaas / ucdc.upaas;IP 110.253.191.12 / 114.250.44.6 |
| DeepSeek | 火山引擎 `volces.com`（字节系） | 待补（本次仅背景） | apmplus.volces.com（APM/DNS） |
| Kimi | 极光推送 `jpush` + 自有 | 待补（本次仅背景） | sis.jpush.* / UDP 19000 / easytomessage.com |

**口径边界**：抓包 = 网络传输层（SNI/IP/字节），**TLS 加密下无明文 token 时序**——`params` 的
token_interval/think_pause 仍 PENDING（需 mitm 解密或保持 UI 层）。豆包/千问抓到对话主连接（发过消息），
DeepSeek/Kimi 仅背景连接（本次未发消息）。权威数据在 portraits 的 `observed_network_layer` 段。
**发现印证**：豆包对话走 WebSocket——与我方语音 realtime-sim 的 WebSocket 仿真方向一致（D-38）。

## 4. 数据可回溯性

- 权威画像数据：`spec/portraits/{doubao,deepseek,tongyi,kimi}.yaml` → `observed_ui_layer` + `observed_network_layer` 两段；
- 落库记录：Room `adapter_obs` 表（D-54），历史页「AI体验」行可视（豆包/千问 id 1/4 等）；
- 决策实录：DECISION_LOG D-49~D-57；
- 采集机制：`adapter/AnebAccessibilityService`（UI 层，观察模式 only 绝不 performAction）+ PCAPdroid（网络层，只读不解密）。

## 5. 后续（网络层 + 更多 App）

1. **网络层画像（M3 核心，PCAPdroid）**：抓包 → 请求大小/token 间隔/思考静默/PoP·IP，回填 params；
   本层与已采 UI 层合成完整画像（两层口径并存、分标）。
2. **Kimi UI 层**：待 v5 方法（复杂 Compose 事件流适配）或改抓包口径。
3. **更多 App**：元宝/文心等对话类同法扩采；抖音等视频类属 Profile 5 扩展位（业务语义不同）。

---
*Profile 3 画像成果快照 v1 · 2026-07-18 · UI 呈现层 4 App 采集完成，网络层待续*
