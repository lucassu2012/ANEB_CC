# T61 素材 · App 端能力条目实况核对（v2 供 v1 直接引用）

> 2026-08-19｜**只读核对，未改任何产品代码**｜每条均现读代码/spec 得出，非引自记忆或旧文档。
> 用途：v1 起草 `DELIVERY_PACKAGE_v1_DRAFT.md` 的「终版能力边界报告」时，App 端条目可直接采信本表；
> 与设计文档冲突处**以本表为准并已标出**（设计文档有未修正的分叉，见 §4）。

---

## 1. 测试模式：三个（spec 驱动，加模式=加 profile）

单一事实源 `spec/profiles/client/client_profiles.json`（+ `app/probe/.../TestModeProfile.kt` 的 FALLBACK 三份镜像）。

| 模式 id | 展示名 | 评分引擎 | 权重表 | 否决规则 |
|---|---|---|---|---|
| `token_experience` | Token 体验 | `AqsScorer` | `WEIGHTS_TOKEN_MM` | T4>1%→封顶54；**S1<0.95→封顶70；S1<0.9→封顶54** |
| `basic_network` | 网络基本性能 | **`ThresholdGrader`**（非 AQS） | —（`fourThreshold` 分档） | 无 |
| `voice_realtime` | AI 实时交互 | `AqsScorer` | `WEIGHTS_VOICE` | **M1>400ms→封顶54** |

**边界（现状类）**：三模式**不共用一张权重表**，`basic_network` 甚至不走 AQS 引擎——**跨模式分数不可互比**。报告若并列三模式分数，必须写明这一点。

## 2. UI 呈现（截至 `dc9db13`）

| 能力 | 实况 | 证据 |
|---|---|---|
| 导航 | 底部 3-tab（测试/历史/设置），下钻屏隐底栏 | `MainActivity` + `components/MainTab` |
| 测试屏 | 模式段控驱动单入口多模式（`TestModeProfiles.ALL` 数据驱动） | `MainActivity` Test 分支 |
| 主仪表 | 180° 半盘指针表（轨+进度弧+21刻度+指针+hub），Canvas 绘制 | `components/HalfGauge.kt` |
| SpeedTest 组件族 | `StBanner`/`StStep`/`StLink`/`StGraph`/`StResults`/`AnebTabBar` | `components/SpeedTestComponents.kt` |
| 结果页 | 简洁/专业双视图；专业含 AQS 头条+真实子分展开+KPI 明细+无线+REACH+场景明细+claim scope 页脚 | `ResultScreen.kt`（10 个 section） |
| 子分展开 | **真实子分**（落库上报体 JSON）优先；无上报体时降级为分级近似**并标注** | `ResultAqsBreakdown.fromReportJson` / `Approx*` |
| 分享卡 | 离屏 Canvas 出图，投影结果页展示态 | `ShareCard.kt` |
| 路由分层 | 9 个 Route 已外移 `ui/routes/`，MainActivity 1178→**753 行** | T62 `90fbd02` |

**边界（现状类）**：`LiveMetric.render`（spec 里 12 处声明：GAUGE 3/RUNNING_NUMBER 4/WAVEFORM 5）**UI 尚无消费方**——`source` 侧闸门已做（D-69），**渲染接线是 D-69 显式列出的剩余项、标 🟠设备**（需真机验手感）。**不是缺陷，是已知待办。**

## 3. 发布形态（T58b `dc9db13` 后）

| 项 | 实况 |
|---|---|
| `assembleRelease` | ✅ 可出包（此前被 lintVital 拦，D-500① 精准豁免后通过） |
| 签名 | ✅ 可签；当前用**临时 throwaway keystore**（CN 写死 `NOT a release identity`），**正式发布 keystore 归 PO**（D-500④ 待办） |
| 签名可选性 | 无密钥的协作方**照样能构建**（回落 unsigned，不阻断） |
| 混淆 | `isMinifyEnabled=false`；R8 三高危面已登记（反射/Room v20 迁移/入口 `@Serializable` keep），**开启前置=keep 规则 + 12 个 MigrationVxTest 全量**（D-500②） |
| 自签证书 | release **携带**收窄版 NSC：仅 `120.79.148.0` 单 IP + `aneb_ip_ca` + system 双锚（D-500③ A 案）。**日落条款**：E-06 公共 CA 落地后撤私有锚 |
| 体积 | debug 61.1MB / release 50.6MB（主要是 Cronet 原生库） |

**边界（原理性）**：release 之所以必须带私有锚，是因为**电信蜂窝对 sslip.io 主机名注入 TLS RST**（R-33 实测/D-22 定案/D-25 自动旁路），bare-IP 是旁路落点。这是**运营商中间盒行为**，非本工具可自解——属原理性边界。

## 4. ⚠ 与设计文档的已知分叉（报告若照抄设计文档会出错）

**「前台 Service（`dataSync`）承载测试执行」——设计文档 §6/§7.2/§风险表都这么写，但代码从未有过该 Service。**
- 实况：唯一 `<service>` 是无障碍观察 `AnebAccessibilityService`；`FOREGROUND_SERVICE*` 权限已声明但**无人使用**；`main/AndroidManifest.xml` 里还留着 `TODO 阶段 1：迁到 dataSync 前台 Service` 的注释。
- 测量期实际靠 **`FLAG_KEEP_SCREEN_ON` 窗口 flag**（`KeepScreenOnPolicy`，T25/D-427），实测背书 **D-437：135/135 场景零 stale**。
- 二者**防的不是同一件事**：前台 Service 防"进程被杀/切后台"，`KEEP_SCREEN_ON` 防"息屏→EMUI cell info 节流"。
- **详见** `docs/FOREGROUND_SERVICE_DESIGN_REVIEW_20260819.md`（v2 评审，建议暂不实施 + 修文档；**大脑尚未裁**）。
- **给 v1 的建议**：能力边界报告写"测量期存活保障"时，**照实况写 `FLAG_KEEP_SCREEN_ON` + D-427/D-437**，不要写前台 Service；并把该分叉列进遗留债务清单。

## 5. 遗留债务（App 端，供 v1 §③ 采信）

| # | 债务 | 状态 |
|---|---|---|
| 1 | 设计文档「前台 Service」分叉未修 | 评审已交，**待大脑裁**（见 §4） |
| 2 | `LiveMetric.render` 渲染接线 | D-69 已知剩余项，🟠 待设备窗 |
| 3 | 正式发布 keystore | **PO 待办**（D-500④） |
| 4 | R8 未开启 | 已登记，需 keep 规则 + 迁移测试全量（D-500②） |
| 5 | `s4_throughput` UI 未建 | **外部门控**：E-01 契约仍缺（D-495） |
| 6 | 渲染层（Compose）无自动化测试 | 无 `createComposeRule`/`androidTest`；纯函数层已覆盖（**101 套件 / 758 tests**），红线判定已尽量抽成纯函数补守（见 `a50afba`/`5be1667`） |

## 6. 墙钟战线（v3 供稿 2026-08-22，全链属主；大脑派单入 T61 配套）

**一句话能力**：系统不信任设备墙钟——每条测量自带「设备钟与生产基准钟差了多少」的
证据（`clock.wall_skew_ms`，键恒在、测不出为 null），分析层在**五个判定点**逐一消费它；
KPI 数值本身不受墙钟影响（计时走单调钟，R-24），被守住的是**判读前提**：
哪天测的、忙时还是闲时、优化前后谁在前。

**链路（设备 → wire → 分析，全部已落地）**：
- **基准与测量**：E-01 服务端钟为基准（NTP 同步生产节点，D-506 裁定）；设备经 EchoWire
  往返测 skew（`AnebClient.wallSkewMs`，单调增量正确加回锚点）。对真实 E-01 实测
  skew = **26ms**，判疑阈值 60s，余量约 2300 倍（D-547）——基准前提有实测背书。
- **wire**：`ResultReporter` 每场景 `clock.wall_skew_ms`，additive 字段（旧生产者不带=
  合法缺席，绝不被读成 0），并有「键恒在、null 非 0」守卫钉住（ResultReporterD1Test）。
- **分析层五个消费点**（阈值单一来源 `trust_rollup.WALL_SKEW_MAX_MS`，与 Kotlin 常量有
  跨语言对账守卫；「服务端时刻」单一实现 `cc.run_server_started_ms`）：
  ①信任表第四信号（可疑计数，自有分母，D-540）；②按日分桶警示与 **B2 三态**
  （全证据整表换服务端钟／混合整表回退+横幅／零证据逐字节不变，表头与 CSV
  `day_clock` 列声明键源，D-541→D-555）；③推断忙闲标签翻转计数（D-543）；④优化前后
  次序按服务端钟复核、只报真的会互换的（D-545/D-552，含 N 战役趋势）；
  ⑤发布门三分支——**语料无该字段判「未核算」而非 PASS**（查不了≠查过了，D-549）。

**给交付包读者的三个要点**：
1. **标记非否决**：墙钟可疑不作废任何 KPI 值，只标注日期/时段/次序类判读需以服务端锚
   复核，警示均附可执行换算式（`started_at_epoch_ms − clock.wall_skew_ms`）。
2. **已发布报告一律不重排**：现存全部语料出自接线前生产者（48 文件实测零该字段），
   B2 换键对它们逐字节无影响——真实语料 A/B diff 验证过（仅生成时间戳行不同）。
3. **缺证据不算干净**：接线前语料的报告会如实印「墙钟未核算」，这是能力而非缺陷——
   系统区分「查过没问题」与「没法查」。

出处：D-506（裁定）/ D-540/541/543/545/549/552/555（五消费点）/ D-547（实测背书）/
`DECISION_REQUEST_WALL_DAY_BUCKET_20260822.md`（B2 裁定纪录）/ D-553（RC 核实纪律，
本链所有「全绿」声明按其执行）。

## 附：单测基线（报告引用请用此数）

**101 套件 / 758 tests / 0 失败 / 0 错误**（2026-08-19 `--rerun-tasks` 全量实测）。
⚠ 板面与部分旧文档里的 **"346"/"324" 是七月旧数，已过期**；引用测试计数请现算，且**避免在 `--tests` 单类过滤后汇总**（Gradle 会只留一个 XML，汇总必残缺）。
