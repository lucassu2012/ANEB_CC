# ANEB 项目交付包（滚动稿，08-21 晨定稿）

> 状态：**骨架+已定稿论据**（大脑 08-19 16:0x 起草，v1 补课完成后滚动填充；标 `〔待填〕` 处为 v1 工作面）
> 日期口径：D-494（真实历 08-19 起；此前档案日期整体慢 10 天，不改写）
> 写作红线：每条能力写「代码里在哪」+ D 号证据链，不引用设计文档中未实现的机制（D-502 教训：前台 Service 从未存在）

## 一、能实现什么（每条带证据锚）

### 1. 端到端 AI 网络体验测量（四条 Profile 线全激活）
- **Token 体验线**（s1_chat/s2_coding_agent/s3_multimodal）：TTFT/ITL/卡顿/速率全 KPI 链，AQS v0.2 出分。真实语料 73 run/489 场景（T46/D-493 体检齐备）。〔待填：KPI 清单表+代码锚点〕
- **网络基本性能线**：RTT/上下行/恢复/整形子测。〔待填〕
- **语音实时线**：回核级 n=30 跨 2 网络条件（D-507/D-510 双盲判读闭环）。**标准句（D-510 定稿）**：「M2（下行网络抖动）答得出劣化有没有发生，M7（最大帧间隙）答得出有多严重——id=32 真实卡顿中 M2 子分与无冻结会话不可区分，M7 单独把它标出（-3.40 分）」。无需录音权限（D-482）。
- **吞吐探针**（S4/U3-D3）：客户端全就绪、三常量已转正（D-499：300ms/100KB/主导度阈值 15，判据=T63 的 489 样本敏感性分析）；**服务端 s4_throughput 待 Codex 部署**（D-495：0.8.3 已上线仍缺）。
- **release 发行链全验证**（D-500+T58c 五项冒烟）：出包→签名→装机→真测量 E-01 跑通（AQS 86，零 TLS 错误），低置信声明屏上如实展示。

### 2. 测量诚实性体系（本项目最大差异化资产）
- R-10（缺失≠零）贯穿到渲染层（HalfGauge idle 修复 a50afba+渲染红线守卫 5effc8f）
- 低置信自声明+claim scope 页脚（「终端至仿真节点应用层端到端」，不外推运营商网络评级/MOS）
- 口径可追溯：AQS v0.2 冻结至真实 API 语料（D-505）、语音 v0.1/v0.2 分数不可比守卫（cb26dca）
- 核心机制表（守卫/机制 → 防什么 → 证据锚；节选最外层的一圈，全量见 scripts/tests/ 663 条与 app 测试 748+ 条）：

| 机制 | 防什么 | 锚 |
|---|---|---|
| R-10 缺失≠零（渲染层） | 「没测出来」被画成「测出来最差」（半盘 0 刻度） | a50afba 修复+GaugeMathTest 增量守卫 5effc8f |
| 低置信自声明 | 样本不足的分数被当高可信结论转述 | 屏上「本次证据不完整」实拍（T58c 冒烟④）；spec §8.4.3 三判据（含 72ff799 补齐的 window_underrun） |
| claim scope 页脚 | 报告被读成运营商网络评级/MOS | 报告头尾双面（D-323 定位加固） |
| 口径不可比守卫 | 语音 v0.1 历史分 79.8 与 v0.2 分数被跨口径比较 | test_voice_score_caliber（cb26dca 含数字边界修正） |
| RttDominanceGuard 三条件 | 小负载把「时延」冒充「带宽」（U1 0.14Mbps 伪影族） | D-499 三常量+T66 绊线（钉 window/阈值之商） |
| 发布门 publish_check | 带 FAIL 的语料出报告；WARN 未在正文交代 | verify_all 15 门（含 T58b 签名验证步 05edee3） |
| 渲染完整性守卫 | 表格被裸竖线劈碎/孤行（源码整齐渲染残缺） | test_docs_commands 22 项（D-214 族） |
| caliber 逐轮核对 | 服务端静默回落 v1 口径混入 v2 语料 | T50 §①C；35/35 零回落实证（DW-05） |
| 守卫的守卫 | 门禁跑了但不算数（UP-TO-DATE 跳过/管道退出码吞失败） | T66/D-508 输入声明修复；guard-pipe 教训（记忆库） |
| 双盲判读 | 单方推理错误被结论正确掩盖 | D-507 vs D-510（落点同、三推理订正） |

### 3. 战役分析层（scripts/，663 reflex 守卫）
- 一键复跑实证（T60 干跑 08-19）：verify_all 15/15 → campaign_report 全语料重出 → publish_check 可发布（FAIL 0）
- 〔待填：工具地图，引用 scripts/README.md 分层表〕

## 二、不能实现什么（边界分两类）

### 原理性限制（换环境也不行）
- RSRP/SINR 无线层指标软件不可仿造（D-36 族）；无线归因只能实测
- 运营商全网 SLA/MOS 结论——claim scope 明确不外推
- 〔待填：完整清单〕

### 现状限制（条件解除即可推进）
- **RAT/忙闲效应=未定**（D-471 科学重置）：制式与出口完全共线，需外场多点位分离——外场线按 PO 指令暂停中
- **吞吐真实路径样本**：等 E-01 s4 部署（Codex）——批④常量已用现有数据拍板（T63 方法），蜂窝窗降级为确认性复核（D-499 日落尾巴）
- **T3 子分在仿真语料上无分辨空间**（D-504①）：仿真服务端固定速率吐字所致，**AQS 区分度实由 U1(43.66%)/D1(45.12%) 主导**（D-493②/D-505①附加动作，防读者高估）
- 73/73 总分 low_confidence=True（场景内样本量结构性低于门槛，D-493③）——分数可用于相对比较，绝对档位标签带保留
- 〔待填：完整清单含语音 lowConfidence 恒真 bug（D-507 发现，修复在 v2 队列）〕

## 三、交付物清单〔待填：v1 主工作面〕
- APP：debug（测量主力）+ release（已验证发行链，keystore 正式版待 PO）
- 文档地图（docs/ 实枚举 67 份，08-19；**常青文档全列，一次性任务产出按索引规则找**——手写全清单必漏必过期）：
  - **治理与总纲**：`DECISION_LOG.md`（决策台账，一切裁定的单一事实源，至 D-512+）｜`BRAIN_TASKBOARD.md`（任务板+DW 设备窗登记）｜`SYSTEM_DEV_PLAN_v1.0.md`（DEV PLAN，唯一指导文档）｜根 `CLAUDE.md`（树边界+提交纪律）
  - **规格契约（常青）**：`PROFILE_FRAMEWORK.md`｜`PROFILE2_THROUGHPUT_PROBE_SPEC.md`+`_INTERFACE.md`（吞吐 S4）｜`PROFILE4_VOICE_LOOPBACK_SPEC.md`（语音）｜`M7_ANCHOR_RECALIBRATION_PLAN.md`（M7 锚点治理）｜`RADIO_CONTEXT_WIRING_SPEC.md`｜`CAMPAIGN_LABELS_CONVENTION.md`+`_WIRING_SPEC.md`（战役标签）｜`N_SAMPLE_SIZE_BY_KPI_RAT_20260804.md`（n 表，D-474）
  - **战役与报告（常青）**：`M2_CAMPAIGN_RUNBOOK.md`（注意 D-311 订正史）｜`T60_ACCEPTANCE_RUNBOOK_HALFDAY_20260819.md`（验收战役）｜`ANALYSIS_LAYER_HANDOVER.md`（分析层交接，十二红线）｜`scripts/README.md`（工具地图，仓内另册）
  - **能力与边界（交付相关）**：本文件｜`T61_APP_CAPABILITY_FACTCHECK_20260819.md`（App 能力实况核对，v2 供料）｜`T46_FULL_CORPUS_ANALYSIS_REPORT_20260804.md`（全语料体检，含订正一）｜`测量红队清单.md`
  - **一次性任务产出（T 号/日期戳文件）索引规则**：由台账 D 号行的「证据」列指回文件名——**先查 DECISION_LOG 再找文件**，不要按文件名猜内容（同名多版本如 T48/前台评审均以台账指针为准）。
- 数据资产（evidence/ 29 目录，08-19 实枚举；四类骨干）：
  - **权威语料**：`t46_full_corpus_analysis_20260804/full_corpus_labelled.jsonl`（73 run/489 场景全语料，一切分析层结论的数据源）｜`phase3/realdevice_data/voice30_voice_result_only.db`（语音 35 行单表；全库 112MB 本地留存不入库）
  - **战役档案**：`m2_pilot_20260731/`（首份真实数据战役）｜`m3_expansion_*`（扩展轮系列，PAUSED 线资产）｜`m2_rerun_20260819/`（M2 复跑正式产物，D-512）
  - **机制证据**：`nr_timeline_20260802/`（RAT 时间线+radio-zero 机制 D-457）｜`t47_s4throughput_devverify_20260804/`（吞吐真机 D-479，诊断期口径）｜`e1_realdevice_20260802/`+`e234_*`（E 系对拍）
  - **门禁日志**：`phase0/`（verify_all 历史 log+sha256-manifest 281 文件清单）
  - 读法规则：目录按「战役/任务_日期」命名，先由台账 D 号证据列定位，勿按名猜（同 docs/ 索引规则）。
- 工具链：scripts/ 战役层〔待填〕

## 四、遗留债务清单〔待填：从台账汇集〕
已知必列：E-01 s4 部署（外部）；评分 v0.2 冻结解除条件=E-03 真实 API key；语音 lowConfidence 恒真修复；window_underrun 置信判据已补（72ff799）但 D-479 文档内「高置信」旧表述待属主补订正指针；EchoWire 墙钟门施工（D-506，spec 已备）；E2 对拍施工（D-511，暂停线）；T62 批 2/5（冲刺后）；正式 keystore（PO）；E-06 公共 CA（撤私有锚日落条款）。

## 五、48h 冲刺纪要〔待填：定稿日补 D-493→D-5xx 全链〕
