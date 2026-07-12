# DECISION_LOG — 决策日志与外部依赖

> 制度来源：参考项目"决策日志 + PO 决策分离"（本项目为研究者单人决策，简化为单表追加制）。决策追加不覆盖；推翻旧决策时新增条目并引用被推翻的 D-xx。

## 决策日志

| ID | 日期 | 决策 | 理由/来源 |
|---|---|---|---|
| D-01 | 2026-07-11 | 交付物 = 分析文档补 KPI 章节 + 独立工具设计文档 | grill-me 访谈；KPI 体系作为工具需求输入，形成"需求→实现"闭环 |
| D-02 | 2026-07-11 | 定位：研究/取证工具；数据质量 > 功能覆盖 > UI | 访谈 |
| D-03 | 2026-07-11 | 平台：Android 原生 Kotlin（minSdk 29），iOS 不做 | 只有 Android 能拿无线层信息与精细网络回调 |
| D-04 | 2026-07-11 | 测试对端：自建仿真服务器为主，真实 LLM API 探针为辅（阶段二） | 网络贡献可精确归因；真实 API 混杂模型侧波动 |
| D-05 | 2026-07-11 | 服务器：国内云 VM 单节点起步，后加海外对照 | 骨干段短、无线侧信号占比高 |
| D-06 | 2026-07-11 | MVP 指标 = T/U/R 组；C 组与 QUIC A/B 放阶段二 | 控制 MVP 周期；连续性实验设计复杂 |
| D-07 | 2026-07-11 | 3 个版本化预置场景（S1 对话/S2 编码 Agent/S3 多模态），发布即冻结、改动升版 | 跨时间/地点/设备横比 |
| D-08 | 2026-07-11 | 四级门限（优/良/可/差）+ AQS 0–100 综合分 | 归因与对外传播兼顾 |
| D-09 | 2026-07-11 | 数据：本地 Room 全量明细 + 服务端 JSONL 双写 | 多设备自动汇总且不引入新组件 |
| D-10 | 2026-07-11 | 技术栈：Kotlin+OkHttp / Go 服务端；阶段二 Cronet + quic-go | EventListener 计时精度；Go 的 pacing 精度与 H3 路径 |
| D-11 | 2026-07-11 | monorepo：docs/ app/ server/ profiles/（后加 evidence/） | profile 与门限是两端共识，单仓不分叉 |
| D-12 | 2026-07-12 | 吸收参考项目（ANEB Android Echo 切片）制度：四态证据制、claim scope 前置、fail-closed 三态 Gate、红队闭环、供应链钉死、失败样本 null 语义、成功主路径优先 | 参考文档 §4/§5 + 制度对齐分析 |
| D-13 | 2026-07-12 | v0.2 红队修订：32 项经对抗验证的测量失真风险缓解并入设计文档与 KPI 口径（agent-qoe-kpi v0.2、profiles v0.2.0、设计文档 v0.2） | 《测量红队清单》（4 视角发现→合并→逐条对抗验证） |
| D-14 | 2026-07-12 | 参考项目做法与本项目冲突处不照搬，逐条记录于下方"否决记录" | 制度对齐分析 conflicts 清单 |
| D-15 | 2026-07-12 | E-01 部署**不修改 chrony**（偏离设计文档 §6"禁 makestep"条款）：共用生产服务器不动全局时钟纪律；srv_ts 单调锚点（R-24）已免疫墙钟步进，chrony 现状 RMS offset 86µs 质量足够；chronyc tracking 快照将随运行元数据存档。P0-C15 步进实验改在本机 WSL2/一次性环境执行 | E-01 为共用服务器（另一项目 mongod/node 在跑）；evidence/phase0/server_provision_20260712.log |
| D-16 | 2026-07-12 | 本机/客户端测量**必须显式绕开系统代理并检测代理存在**：首次公网基线被本机代理（127.0.0.1:33210/7897）静默劫持，RTT p50 从 28.1ms 放大到 1519.7ms（54 倍）而流节奏无异常——单看 pacing 无法发现路径被劫持。PC 侧探针一律 UseProxy=false + 记录代理检测结果；Android NetGuard 的 VPN/代理硬拒测（R-03）优先级提升 | evidence/phase0/first_internet_baseline_20260712.log |
| D-17 | 2026-07-13 | 引入本项目**首个第三方 Go 依赖** `github.com/quic-go/quic-go` **v0.60.0**（钉死精确版本入 go.mod/go.sum，go 指令随之升 1.25.0，与部署工具链 go1.26 兼容）——专项用于阶段 2 HTTP/3：`-h3` 同端口 UDP 并行 http3.Server 复用同一路由树，**fail-closed**（无 -tls-cert/-tls-key 时 -h3 拒绝启动，h3 为 TLS-only）；TCP 侧加 Alt-Svc 广告。协商证据两侧留痕：所有响应带 `X-Aneb-Proto`（服务端视角 r.Proto + via=tcp/h3-server 处理栈标记），/serverinfo 增 `h3_enabled`——**QUIC 启用 ≠ 协商 h3**（红队项），A/B 分组以逐样本协商记录为准。"无外部依赖"原则（§6）就此收窄为"标准库 + quic-go 专项"，与 D-10 阶段二规划一致 | 设计文档 §6/§8 阶段 2；D-10；supply-chain：版本钉死 + go.sum 校验 |

| D-18 | 2026-07-13 | **P0-C14 验收判据修订**：原"U1 vs iperf3 偏差<20%"误把应用层 HTTP goodput 与裸 TCP 稳态直接对标——实测比值 0.66 稳定（1MiB POST 含请求头/逐块打戳/响应回程 vs C 裸 TCP 紧循环；亚毫秒 RTT 排除慢启动主因；iperf3 自身 run 间变异 ±19% 使 20% 门限先天偏紧）。修订为**比值带判据：U1 ∈ [0.5, 1.0] × iperf3 稳态中位**。原始 FAIL 与修订 PASS 并列入账（STATUS.json），判据变更透明可审计 | evidence/phase0/c14_u1_vs_iperf3_20260713.log 归因诊断 |
| D-19 | 2026-07-13 | **E-01 的 TLS 切换与 H3 部署合并到 Cronet A/B 批次执行**：服务端开 TLS 会使现役 http:// 客户端断链，须与客户端 https+自签信任锚+Cronet 改造一次协同切换；证书已预生成（/opt/aneb/tls，EC P-256，SAN=IP）。届时需用户在控制台放行 **UDP 8443**（E-01 依赖项追加） | H3 代码已合并（D-17）且 37 测试全绿，仅部署时点推迟 |
| D-20 | 2026-07-13 | **阶段 2 C 组连续性实验（continuity 模式）+ aqs v0.2 落地口径**：①C2 恢复计时起点＝客户端**检出**中断的时刻（IOException 浮出/读超时），非网络物理中断时刻——这是应用层端到端体验口径（claim scope 一致），模拟器实测蜂窝 data off 不 RST 存量 socket、检出耗时=readTimeout 30s，本身就是"静默挂起税"的直接证据；②重连=新请求同参数、指数退避 500ms×2^n、最多 5 次，全部失败→C2 该样本记 null（R-10，不记封顶值），run 状态 recovery_failed；③连续性 run 与场景 run 分流（独立引擎 ContinuityRunner/独立日志 KEY CONTINUITY_*/独立表 continuity_result），不复用场景状态机；④路径监控豁免：绑定模式用 PathMonitor(exemptPathChanges=true) 设计本尊，AUTO 模式用对偶 ExemptDefaultNetWatch——路径事件全量记 EnvEvent(exempt=true) 但绝不 invalidate（路径迁移是测量对象）；监控器自身故障不豁免，仍 fail-closed；⑤aqs v0.2＝v0.1 权重×0.8+C1 10%+C2 10%（C1 锚 0.5/2/5%，C2 锚 1/3/10s），仅显式传入 ContinuityKpi 才出 v0.2 分，无 C 数据回退 v0.1 语义不变；⑥C3 一律标 functional_only（模拟器 NAT/OkHttp 池 keepalive 5min 语义与运营商 CGNAT 不同，不构成 C3 测量结论） | KPI 文档 5.1/5.2/5.4；设计文档 §8 阶段 2；evidence/phase2/continuity_e2e_20260713.log |

| D-21 | 2026-07-13 | **Cronet QUIC 的公共信任链约束**：cronet-embedded 143 对 QUIC 强制 is_issued_by_known_root 校验（NetLog 逐帧证据：UDP 通、握手推进到证书阶段、客户端以 certificate_unknown 收连接退 h2），自签/私有 CA 即使装入 NSC 信任锚也无法让 h3 协商成功——TCP/TLS 不受此限（A 组 h2 正常）。**拒绝用 MockCertVerifier 关校验（造假红线）**。结论：①本地自签环境只能验证 A/B 机制与 fallback 语义（已 13 单测锚定+A 组端到端）；②E-01 公网 QUIC A/B 需要域名+公共 CA 证书（Let's Encrypt），新增外部依赖 E-06；③A/B 结论仅在 Cronet 栈内 TCP vs QUIC 对比得出，与 OkHttp 主测量数据不互比（栈间差异 KDoc 声明） | evidence/phase2/cronet_ab_e2e_20260713.log NetLog 诊断 |

## 否决记录（评估后明确不采纳）

- **Cronet 逐请求 bindToNetwork**：OkHttp 主栈无此 API；改用 `requestNetwork` + `socketFactory`/`Dns` 双绑定，保留其 fail-closed 语义（绑定不可得即不出数）。
- **M2 式里程碑制与正式 PO 角色**：研究者本人即决策者，轻量四态证据 + 阶段验收足够；对方被外部依赖全线卡死（M2=NO）正是过度制度化+外部前置的后果。
- **功能范围冻结**：本项目冻结的是 profile 与 KPI/AQS 的版本语义，不是功能范围——流式/上行恰是主战场。
- **单指标名 const 锁死**：本体系多 KPI 且版本化演进；schema 锁 claim_scope 与版本字段，不锁指标名清单，否则与"门限随数据回流重标定"（D-08 配套）冲突。
- **最小权限清单照搬**：R 组无线层归因必须采集小区/信号，申请 `ACCESS_FINE_LOCATION`+`READ_PHONE_STATE`，差异与数据保护承诺显式声明（设计文档 §9.1）。
- **invalid 全抑制到数据层**：抑制只作用于 KPI/AQS 聚合层；原始事件全量保留（取证需要分析失效原因）。
- **设备矩阵/双节点实验室校准作为验收前置**：留待阶段三按需借用其判据框架（同条件 median CV≤8%、同 CDN 边缘不算独立节点），不前移为阶段 0–2 门槛。
- **对方 Echo RTT 数据直接当 N1 基线**：Cronet vs OkHttp 栈间系统差未标定前，两项目数据不可直接互比；互校须同设备同网络先标定栈差。

## 外部依赖清单

原则：每项外部依赖必须有本地替代方案，保证**每个阶段都有纯本地可完成的验收路径**；依赖缺位时对应检查记 `BLOCKED_EXTERNAL`，绝不折算成 PASS。

| ID | 依赖 | 最晚需要时点 | 本地替代方案 |
|---|---|---|---|
| E-01 | 国内云 VM（2C4G、公网 IP、8443/TCP，阶段二 +UDP） | 阶段 0 后半（真机联调） | 局域网 Linux 盒 / WSL2 + tc netem |
| E-02 | Android 真机 + 蜂窝 SIM（4G/5G） | 阶段 1 蜂窝验收 | 模拟器只能产出功能/fail-closed 兼容性证据，不构成测量证据（参考项目教训：模拟器无 NET_CAPABILITY_VALIDATED） |
| E-03 | 真实 LLM API key（Anthropic / Kimi） | 阶段 2 探针 | 跳过探针对照列，主线不受阻 |
| E-04 | 海外节点 | 阶段 3 | netem 模拟跨境 RTT/丢包剖面 |
| E-05 | CAMARA QoD 试点（运营商合作） | 阶段 3 | 无替代；记 BLOCKED_EXTERNAL |
| E-06 | 域名 + 公共 CA 证书（Let's Encrypt，绑定 E-01） | 阶段 2 云端 QUIC A/B（P2-C06） | 无替代（D-21：Cronet QUIC 强制公共已知根，自签不可行）；同批次需 UDP 8443 放行 |
