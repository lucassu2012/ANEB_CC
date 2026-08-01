# ANEB spec(aneb-spec 雏形)—— P3 单一事实源

> 依据《SYSTEM_DEV_PLAN v1.0》§4.3/§7:P3 的产出全部是数据/文档,被 P1/P2 消费。
> 本目录是计划中独立仓库 `aneb-spec/` 的仓内雏形(对齐路径"先立 spec/ 目录后拆仓",D-47)。

## 治理规则(铁律 1 治理面)

1. **spec 为单一事实源**:Profile 描述、结果 Schema、打分规则(权重/锚点/否决)、业务画像
   参数的权威定义都在本目录。代码或其他文档与 spec 冲突时,以 spec 为准修代码。
2. **一切跨仓库/跨模块变更先改 spec、后动代码**(计划 §7 运作规则):契约性改动
   (新增 KPI/权重表/Schema 字段/Profile 相位等)必须先在本目录落定并升版本,再动 P1/P2 代码。
3. **严格 loader 通则**(D-397;取代原「additive-only 安全」那半句)。
   **仓内 spec loader 皆严格 `Json`**——`kotlinx.serialization` 的默认实例对**未知键**与
   **类型不符**一律抛异常。因此:**往一份已被加载的 JSON 里补键,默认不可行**。
   它不是加性变更,是**双侧同提交**变更,且**顺序不可反**(先 DTO 带默认值,后 JSON+assets 镜像)。

   **两个实证案例**(都是动手前的核查把任务翻了面,不是设想):

   | loader | 严格性出处 | 补一个键的后果 | 证据强度 |
   |---|---|---|---|
   | `AdapterSpecLoader`<br>`AdapterSpec.kt:43` | `private val json = Json`,注释逐字「默认严格:未知键/类型不符即抛 → 触发 fail-safe 空列表」 | `loadFromAssets` 捕获 → **返回空列表**(单文件坏也整体回空,KDoc 逐字) → **全部** App 落回 generic → D-54 要求 `specId != null` ⇒ **`adapter_obs` 从此一条不入库,且没有任何一处会报错** | **有反例**:`AdapterSpecTest.kt:121` `strict mode rejects unknown keys` 喂 `"unknown_key": 1` 断言抛,且**先跑一次合法底座**防真空通过 |
   | `TestModeProfileLoader`<br>`TestModeProfileLoader.kt:30` | `private val json = Json`,KDoc(:20)逐字「[Json] 用严格模式(未知键即失败),防 schema 漂移静默生效」 | `loadFromAssets` 捕获 → **返回 null** → 回退代码内硬编码 FALLBACK,打 `SPEC_PROFILE_FALLBACK`;`ClientProfileDataParityTest` 用例 1 同时红(D-391 ②) | ⚠ **无反例**:那份名为「损坏数据必须抛」的用例(`ClientProfileDataParityTest.kt:94`)喂的是**坏 JSON / schema 不符 / profiles 为空**三种,**未知键一种都没喂**。该 loader 的「未知键即失败」今天只由 KDoc 与 `Json` 默认值担保 |

   **逃生口(唯一批准形态):新文件 + 新对拍。** 不往既有被加载 JSON 补键,改为另立一份数据文件,
   并**同批**给它配一道**会失败的**对拍守卫。先例:D-391 的
   `spec/profiles/client/voice_realtime_plan.json` + `scripts/validate_voice_plan.py`
   (接进 `verify_all` 的 `voice-plan-parity` 步)——当时正是因为往 `voice_realtime` 条目里
   补子对象**做不到**:运行时抛 → 回退兜底 → 要做必须改 DTO,而同一裁示禁止动 `:probe`。

   **判据是消费方,不是变更形状。** 同样叫「additive」,落在**不同消费方**上结论相反:
   `observed_ui_layer.dist`(裁定 6-7)是安全的——它的消费方是 `check_redline.py` 与
   `portrait.schema.json`(`observedLayer` 无 `additionalProperties: false`),**不是**严格
   Kotlin loader。**动手前先数消费方**(D-276),别数变更形状。

   **即使照做了「先 DTO 后 JSON」,形状门仍有一处够不着**(T14 §8.2,真 `main()` 实测):
   新增的嵌套 DTO 若**声明在 `AdapterSpec.kt` 之外的文件**,`validate_adapters.py` 对该段
   **一个键都不查**,并照旧印出 `OK: ... A1 no key the strict parser would reject ...`
   ——而那个键就在文件里(唯一差别=把该 DTO 挪回同文件的对照组当场 exit 1)。
   故**新增嵌套类型必须与根 DTO 同文件、且是 `data class`**;
   `class`(非 data)/`enum class`/`typealias` 同样整块静默不查。
   这是「补一个键」不安全的**第二个、独立的**原因。

   **原规则仍然成立的那一半**(版本纪律,未被推翻):已发布字段/权重表/锚点表
   **只增不改不删**;语义变化 = 新 id/新版本号并列
   (既有先例:aqs-v0.1 → aqs-v0.2 并列、WEIGHTS_TOKEN_MM/TXT 并列、aqs-voice-sim-v0.1 并列)。
   **被推翻的只是「additive ⇒ 安全,可以单侧改」这半句**(D-387 首次撞见,D-397 升为通则)。

   > **本条今天没有守卫(诚实缺口)**:「仓内 spec loader 皆严格」这句话本身没有任何东西核对它
   > ——新增第三个严格 loader 时,上表不会自己长出一行。应有的形态:扫 `app/**/*.kt` 里
   > `= Json` 的默认实例,与上表**对账**(清单从产物导出而非手写,D-329)。**本轮未实现**:
   > 它须接进 `scripts/verify_all.ps1` 才算数(D-394 §2.16「一道守卫『绿』之前,先证明它被执行了」),
   > 而该文件此刻有他会话未提交的改动,不得代为暂存。列为下一轮首项。
   > 同一格里的第二项:给 `TestModeProfileLoader` 补一条「未知键即抛」的反例(上表右列那个 ⚠),
   > 属 `:probe` 面,交 v2。
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
