# ANEB spec(aneb-spec 雏形)—— P3 单一事实源

> 依据《SYSTEM_DEV_PLAN v1.0》§4.3/§7:P3 的产出全部是数据/文档,被 P1/P2 消费。
> 本目录是计划中独立仓库 `aneb-spec/` 的仓内雏形(对齐路径"先立 spec/ 目录后拆仓",D-47)。

## 治理规则(铁律 1 治理面)

1. **spec 为单一事实源**:Profile 描述、结果 Schema、打分规则(权重/锚点/否决)、业务画像
   参数的权威定义都在本目录。代码或其他文档与 spec 冲突时,以 spec 为准修代码。
2. **一切跨仓库/跨模块变更先改 spec、后动代码**(计划 §7 运作规则):契约性改动
   (新增 KPI/权重表/Schema 字段/Profile 相位等)必须先在本目录落定并升版本,再动 P1/P2 代码。
3. **additive-only**:已发布字段/权重表/锚点表只增不改不删;语义变化 = 新 id/新版本号并列
   (既有先例:aqs-v0.1 → aqs-v0.2 并列、WEIGHTS_TOKEN_MM/TXT 并列、aqs-voice-sim-v0.1 并列)。
4. 既有红线对 spec 同样生效:**R-10**(可空字段=测量失败/未测,null 绝不以 0/哨兵顶替)、
   **D-02**(展示层只消费落库产物,不重算测量/打分)。

## schema_version(语义化版本)

- spec 自身版本本轮起版 **1.0.0**(各数据文件顶部 `schema_version` 字段)。
  注意区别:结果上报体顶层 `schema_version: "1.0"` 是 P1↔P2 的 wire 合同字段
  (ResultReporter.SCHEMA_VERSION),见 `schemas/result-run.schema.json`,两者独立演进。
- MAJOR:不兼容变更(原则上禁止,走新 id 并列);MINOR:向后兼容新增;PATCH:勘误/注释。
- 引擎声明支持的 schema 区间(计划 §4.3 第 5 条):拆仓后由各仓 CLAUDE.md 声明所依赖的
  aneb-spec 版本区间。

## 目录

| 目录 | 内容 | 状态 |
|---|---|---|
| `profiles/server/` | 服务端场景 Profile 权威副本(s1_chat / s2_coding_agent / s3_multimodal) | 镜像仓根 `profiles/`(见下) |
| `schemas/` | 结果上报体 JSON Schema(`run.report_body`,draft-07) | 锚定 ResultReporter 实况 |
| `scoring/` | AqsScorer 打分规则机器可读化(权重/锚点/否决,YAML) | 导出+对拍(见下) |
| `portraits/` | Profile 3 业务画像参数(首批:豆包 + DeepSeek,D-48) | PENDING-CAPTURE 占位 |

## profiles/server/ 镜像关系与收敛计划

- 仓根 `profiles/*.json` 是**服务端加载路径与客户端 assets 的现行同源目录**(D-32),
  本轮**保留不动**——不破坏服务端 loadProfiles 与 `scripts/deploy_server.ps1` 的既有读取路径。
- `spec/profiles/server/` 自本轮起为**权威副本**:此后 profile 变更先改这里、同步仓根、再走部署。
- 收敛计划:后续单独一轮把构建/部署脚本的读取路径切到 `spec/profiles/server/`,
  仓根 `profiles/` 目录退役(涉及部署链,勿与治理骨架混做)。

## 与服务端能力合同(TEST_SERVER_CAPABILITIES.md)的关系

- E-01 共享测试服务器的**唯一权威能力合同**是 `TEST_SERVER_CAPABILITIES.md`,由 **Codex 维护**
  并随部署回写验证(docs/DECISION_LOG.md **D-37**);**服务端部署权 = 仅 Codex**(**D-35**)。
- 因此:spec 内 `profiles/server/` 的任何变更要在 E-01 生效,**必须经 Codex 合并部署**
  (先例:s3@0.3.0 download_burst 按我方合并规格附录由 Codex 合并,D-35/D-37)。
- 分工语义:**spec 定义"应然"(变更提案与权威定义),能力合同记录"实然"(E-01 实况)**;
  两者出现偏差时,以能力合同为线上实况、以 spec 为待合并的变更提案。

## scoring/ 状态:本轮为"导出+对拍",代码引用 spec 为终态

- 本轮 `scoring/*.yaml` 由 `app/probe/src/main/java/com/aneb/probe/scoring/AqsScorer.kt`
  **逐字导出**;代码**不反向引用** YAML(避免大改既有打分链的风险)。
- 防漂移由一致性对拍单测守护:
  `app/probe/src/test/java/com/aneb/probe/spec/SpecScoringParityTest.kt`
  ——权重表全量、锚点全量(含插值与 clamp 行为)、否决常量、版本 id 逐值对拍,
  **任何一侧改动而另一侧未跟进即红**。
- 终态(铁律 1):P1/P2 运行期直接解析 spec 数据文件,打分规则彻底数据化;届时移除对拍层。

## portraits/ 红线

业务画像采集(PCAPdroid 免 root 抓包 / mitmproxy 解密自有账号流量,计划 §4.3)完成前,
`source_portrait: "PENDING-CAPTURE"` 的画像文件**不得用于模拟参数宣称**;
其全部参数为 [GUESS]/null 占位,回填后须把 `source_portrait` 改为可追溯的采集标识
(如 `doubao-app-capture-2026Q3`)并升版本。
