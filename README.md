# ANEB — Agent Network Experience Benchmark

研究智能体互联网时代移动通信网络新型性能与体验诉求，并提供配套测量工具 **ANEB Probe**。

## 仓库结构

- `docs/` — 研究文档
  - 《智能体互联网时代（Agentic Internet）移动通信网络的新型网络性能与体验诉求》：诉求分析 + Agent-QoE KPI 体系（agent-qoe-kpi v0.2：指标/门限/测量方法/声明边界，第五部分）
  - 《ANEB Probe 开发设计文档》（v0.2）：测试工具的架构、技术选型、分阶段实现计划、红队修订
  - 《测量红队清单》：32 项经多代理对抗验证的测量失真风险与闭环计划（10 项 high）
  - 《DECISION_LOG》：决策日志（D-xx）、否决记录、外部依赖清单（E-xx）
  - 《参考_ChatGPT侧ANEB_AndroidEcho方案与进展》：并行姊妹项目制度借鉴（只读参考）
- `profiles/` — 版本化测试场景配置 v0.2.0（客户端/服务端共享，发布即冻结，改动须升版本）
  - `s1_chat.json` 对话流（对照组）
  - `s2_coding_agent.json` 编码 Agent 流（主场景）
  - `s3_multimodal.json` 多模态流
- `evidence/` — 验收证据目录（四态证据制，规则见其 README）
- `app/` — Android 客户端（Kotlin，minSdk 29）［阶段 0 待建］
- `server/` — Go 仿真服务器（SSE token 发生器 / 上行汇 / 结果落盘）［阶段 0 待建］

**命名消歧**：本项目对外称 **ANEB Probe**；并行姊妹项目（Application Echo RTT 垂直切片）称 **ANEB Android Echo 切片**，两者同属 ANEB 研究计划、范围互补。

## 当前状态

设计基线 v0.2（含红队修订与制度对齐）已完成，进入阶段 0：骨架与计时联调。开工清单见设计文档 §10，验收证据按 evidence/ 四态制度落盘。
