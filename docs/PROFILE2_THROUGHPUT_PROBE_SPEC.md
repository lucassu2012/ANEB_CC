# Profile 2 单流自适应窗口 goodput 探针 · 规格草案（T47）

**状态**：规格草案 v2（已按三透镜批判复核修订）· 2026-08-04 · owner=v4 · 未动代码
**上游**：`docs/BRAIN_TASKBOARD.md` T47「APP 测量核演进」（PO 转向指令①），本文是其第一批交付之一
**产出方式**：13 子代理工作流（四维研究→三方案独立比稿→评审选主线+借鉴点→草案→三透镜批判复核
[架构契合/测量方法论/接口完整性]→终稿），全部结论均在仓库中实测核实（源码/schema/决策记录），
非纯理论设计
**方法学范本**：`docs/PROFILE4_VOICE_LOOPBACK_SPEC.md`（Profile 专属能力另立独立文档的既有先例）

---

## §0 与任务背景的分歧：先摆出三处已核实的更正

派单原文提到「与 mode 体系关系（quick/forensic/continuity/ab）」「aqs_version 按模式分表的既有架构」
「Profile 1a/1b/2/3」。逐项在仓库中核实后，以下三处与实际代码/文档不符，先更正、后设计，避免以讹传讹：

1. **mode 只有两个取值**：`TestEngine.kt:77` `enum class Mode { QUICK, FORENSIC }`，`result-run.schema.json`
   对 `run.mode` 的描述也明文「quick / forensic」。continuity/ab 不是 mode 的合法取值——它们是
   `MainActivity.kt` 里对同一个 intent extra 字符串「mode」的另外两种判等分支，各自路由到完全独立于
   TestEngine 状态机之外的 `ContinuityRunner`/`AbRunner`，从不写 `run.mode` 字段。
2. **aqs_version 不是「分表」，是同一 run 上可并存的多条 additive 平行打分**：`AqsScorer.kt` 的命名
   规则是 `aqs[-facet]-v{major}.{minor}`，现存 `aqs-v0.1`/`aqs-v0.2`/`aqs-token-v0.1`/
   `aqs-voice-v0.1`/`aqs-voice-v0.2`/`aqs-voice-sim-v0.1` 等多支并列版本号，各业务 facet 各自独立
   演进，不是互斥的"按某种分类分表"。
3. **不存在「Profile 1a/1b/2/3」这种编号**：`docs/SYSTEM_DEV_PLAN_v1.0.md` 里其实是两条完全不同的
   编号轴——`P1a/P1b/P2/P3` 是**开发子项目**标签（P1a=手机前台 UI、P1b=手机后台测量引擎、P2=服务器侧、
   P3=ANEB 标准与业务模型仓），`Profile 1/2/3/4` 才是**测试业务类型**编号（Profile 1=基础网络 L0
   原子指标、Profile 2=Token 类业务模拟、Profile 3=第三方 App 适配器观测、Profile 4=实时语音）。本文
   讨论的新能力属于 **Profile 2（token_experience）**。

---

> **位置说明**：本文档讨论的是 **Profile 2（token_experience，服务端仿真业务）** 下新增诊断场景的
> 单流自适应窗口 goodput 探针，与 `spec/adapters/INSTRUMENTATION_SPEC.md` 的标题「Profile 3 适配器
> 打点规格」及其 §0.1 声明的范围（UI 层打点事件语义 + 外部观测通道方法学 + 误差预算，服务对象是
> 豆包/DeepSeek 等第三方 App）**技术域不同**——该文件全文对 `throughput`/`bandwidth`/`goodput` 检索
> 零命中即为证据。仿照 `docs/PROFILE4_VOICE_LOOPBACK_SPEC.md`（Profile 4 语音没有把自己的规格塞进
> `INSTRUMENTATION_SPEC.md`，而是另立独立文档）的先例，本方案**另立本文件**，不插入
> `INSTRUMENTATION_SPEC.md`。是否采纳此落位，仍列入 §7 待裁定清单交大脑/PO 确认。
>
> 本文内部沿用工作流产出时的原始节号（起于「8」），未重新从「1」编号——原因是这些节号在本文与附录A
> （拆批方案）、姊妹文档《PROFILE2_THROUGHPUT_PROBE_INTERFACE.md》（v2 接口定义）之间被大量交叉引用
> （如「spec §8.3.3」「spec §8.4.2」），机械重编号跨三份文档、数十处引用点，出错代价远大于收益；
> 保留原始节号可以让这些交叉引用天然保持正确。

## 8. Profile 2 单流自适应窗口 goodput 探针（S4/U3-D3）—— T47 交付 spec 草案 v2

### 8.0 术语先行：本方案测的是什么、不是什么

**本方案的名字刻意不用「真实吞吐/真实网络承载力」**——task 背景里的口语化提法容易让读者以为
这是链路名义容量或多流聚合带宽的测量。实测约束（`app/probe/src/main/java/com/aneb/probe/net/AnebClient.kt`）：
`uploadBurst`（363-419 行）与 `downloadDrain`（496-530 行）每次调用各自只发起**一个** `client.newCall`——
**单条连接、单条 TCP 流，无任何并行**。这与 Ookla/Fast.com/iperf3 -P 等工具用多并发流探测链路容量的
做法不同：在高带宽×高RTT（高 BDP）路径上，单流吞吐会明显低于链路真实容量（受限于该流自身的拥塞窗口
爬升速度与 OkHttp/系统收发缓冲区），这是一种**新的、与 D-363 机理完全不同的失真**——D-363 是「传输
时间≈RTT」的时延伪影，这里是「传输时间已经远大于RTT、自检判据显示安全」却仍然被单流限速压低的容量
伪影。§8.4 的自检判据（RTT 主导度）对这类失真**没有识别能力**，必须在文档层面用准确的术语防止过度
宣称。

**本方案的精确定位**：**单流应用层 goodput 探针（single-flow application-layer goodput probe）**——
测的是「这一条 TCP 流在这段时间内实际跑到的速度」，不是「这条链路能跑多快」。多流聚合吞吐是明确的
**非目标**，如需要需另立提案（比照批⑤的独立立项模式）。全文后续统一使用「goodput 探针」而非
「吞吐测量」，`s4_throughput` 这个 profile_id 保留不改名（改名代价过高、且已在多处引用），但
**profile_id 本身不构成技术承诺**——技术承诺以本节文字定义为准。

### 8.1 既有吞吐能力盘点（两套、互不相交、同名不同义）

| 能力 | 位置 | 负载/时长模型 | 打分 | 持久化/上报 |
|---|---|---|---|---|
| `basic_network` 的 D1/U1 | `app/probe/.../engine/SpeedRunner.kt`；挂载于 `TestModeProfile.kt:232-245`（`scored=false`，`ThresholdGrader` 四门限） | **固定时长**（6s 滑窗，`DOWNLOAD_BYTES=1L shl 30`，`SpeedRunner.kt:38`） | 不进 AQS | **零持久化**：`grep ResultReporter/report_body` 在 `MainActivity.kt` 的 SpeedRunner 集成路径零命中 |
| `token_experience` 的 U1/D1 | `app/probe/.../engine/AqsInputMapper.kt:17-21`：`U1←S3.1MB_upload`、`D1←S3.download`（S3=`s3_multimodal`） | **固定字节数**（`spec/profiles/server/s3_multimodal.json`：两次 1MB 上传、两次 12MB 下行） | U1 进 AQS 主分（`u1GoodputMbps`）；D1 仅算出未上线 | U1 已上线（`ResultReporter.kt:151-152`）；**D1 半成品**——`KpiCalculator.kt:200/405-411` 已算出 `d1GoodputMbps`，但 `ResultReporter.kt`/`kpiValuePairs()`（`TestEngine.kt:809-822`）全文 grep `d1_goodput`/`"D1" to` 零命中——**契约里"要打分"，wire 上"从未出现"，`kpi_quality` 词表里也从未有它的位置** |

两套 U1/D1 **同名不同义**且分属两个不打通的打分引擎（`ThresholdGrader` vs `AqsScorer`）——这是本章节
KPI 命名必须避开的第一个陷阱（§8.4.1）。

### 8.2 与 D-363/D-366 的关系：如何避免重蹈覆辙

**D-363 实测结论**（`docs/DECISION_LOG.md` D-363）：U1「0.14 Mbps」不是网络事实，是负载伪影。判据 =
**耗时 ÷ 该次自身 RTT 的倍数**：

| 场景 | 负载 | 耗时/RTT 倍数 | 判定 |
|---|---|---|---|
| `s1_chat` | 2KB | 1.60–1.99×（中位 1.77） | 纯时延伪影，拥塞窗口从未打开 |
| `s2_coding_agent` | 512KB | 5.7–7.7× | 已离开时延区间，但**从未被判定为"安全"**，只是"不像 s1 那么假" |
| `s3_multimodal` | 1MB×2 | 6.8–9.8× | 已离开时延区间，`AqsInputMapper` 至今仍以此为 U1 评分口径 |

**D-366 落地**（`docs/DECISION_LOG.md` D-366）：PO 批①，`s1_chat` 退出 U1 跨 profile 汇池。**关键澄清**：
评分侧（`AqsInputMapper`）**从未被污染**——其 `U1←S3` 合同在 D-363 之前就已存在且从未变化
（`AqsInputMapper.kt:17-18/65`），S1/S2 的上传从不进 AQS。真正被 D-363 揭穿的问题在**分析层的跨
profile 汇池**（`scripts/campaign_common.py` 的 `KPI_PROFILE_EXCLUSIONS`），不在设备端打分契约。

**D-365 附带证据**（`docs/DECISION_LOG.md` D-365）：同一物理链路、同设备、同点位，仅因采集时段不同，
RTT 中位可漂移 **+26~34%（53→70ms）**。这条证据本文用来论证 §8.3.3 的必要性——RTT 基准不是恒定量，
一次性的"传输前测一下"存在被后续拥塞甩开的风险。

**"耗时÷RTT倍数"判据此前的状态**：只是一次性叙事分析（`docs/M2_PILOT_REPORT_2026-07-31.md` §2.2），
固化的只是其*结论*（分析层静态排除表），**从未固化成运行期/单测可复用的守卫函数**。

**本方案如何避免重蹈覆辙（四条，比上一版多一条——新增 §8.3.3 拥塞可见性，直接回应"RTT 自检对传输期
拥塞天生失明"这一批判）**：

1. **不用固定字节数赌安全区间，改用固定时长窗口天然保证比值**（§8.3.1）。D-363 的三档倍数之所以
   分散，根源是"负载大小是否恰好匹配当前链路速率"这一偶然关系。本方案把负载–时长关系倒过来：先固定
   测量窗口时长，传输字节数随链路速率自动伸缩。
2. **把判据变成运行期可执行代码，而不是停在诊断文档里**（§8.3.2/§8.4.1）。新增独立、无 Android 依赖
   的纯函数，把 D-363 的三个历史数据点直接固化为回归测试夹具。
3. **数值仍然真实测得时不悄悄置 null，而是显式标记 `low_confidence`**（§8.4.3），对齐既有 `kpi_quality`
   （D-373）语义。
4. **（本版新增）RTT 基准不能只测一次就假定全程有效——必须在窗口传输前后各测一次，并把漂移量显式
   落成字段**（§8.3.3）。这不是完整的拥塞检测（见下方"已知局限"），但把 D-365 已实测过的
   "同链路 RTT 可漂移 26-34%" 这一真实风险，从"自检判据完全看不见"降级为"至少有一个粗粒度的
   事后信号"，供分析层/PO 判断某次测量是否可信。

**已知局限（本版新增，诚实标注、不假装已解决）**：即便有前后两次 RTT 采样，仍**测不到窗口传输
*过程中*的瞬时拥塞**——bufferbloat 可能在窗口中段发生又在窗口结束前消退，前后两次静态采样都不
覆盖它。真正的中途监测需要新的基础设施（例如独立连接上的并发低速率 echo 探针），超出本次诊断期
批次范围，记入 §8.7 待裁定 8-8。`dominance_ok=true` 因此只应被读作"结构上不属于时延主导"，
**不是**"该数字未受拥塞影响"的保证。

### 8.3 测量协议定义

#### 8.3.1 挂载点与执行边界

新增场景 **`s4_throughput`**，挂载于既有 `token_experience` TestModeProfile 之下，与
`s1_chat`/`s2_coding_agent`/`s3_multimodal` 并列声明在同一份 `/api/v1/profiles` 响应里，但**不进入
`ProfileParser.REQUIRED_IDS`**（`app/probe/.../engine/ProfileModels.kt:81`：
`listOf("s1_chat","s2_coding_agent","s3_multimodal")`，其注释「三场景固定集合，顺序即拉丁方场景下标
0/1/2」是 order_effect 分析赖以存在的地基，`TestEngine.kt:316-320` 消费该常量驱动 3×3 拉丁方轮转）。
`ProfileParser.index()`（`ProfileModels.kt:95-100`）只校验 `REQUIRED_IDS` 是否都在 `map` 里，**不校验
map 是否恰好等于 REQUIRED_IDS**——因此 `s4_throughput.json` 存在时可以被正常加载进 `loaded.profiles`，
无需改动 `index()`。

**这只解决了"加载"，不解决"执行"**：`TestEngine.kt:316-333` 的场景循环（`runLoop@`）完全由
`val ids = ProfileParser.REQUIRED_IDS` 与 `rounds = LatinSquare.quickOrder/orders(ids.size)` 驱动，
**没有任何现成机制会让循环之外的第四个 profile 被执行**。§8.6 给出明确的挂载设计。

#### 8.3.2 两阶段流程：RTT 基准 + 定长时间窗传输（+ 窗后复测，本版新增为必选）

```
phase 1: clock_sync（复用既有 phase 类型，ProfileModels.kt:51）
  ├─ 20 个 echo 样本（沿用 s1/s2/s3 同款默认值，ScenarioRunner.kt:185）
  └─ 产出本场景自己的 rtt_ref_ms_pre（不复用 S1/N1 等其他场景的 RTT——
     scenario_order 决定了 s1 与 s4 在时间线上分离，中间夹着 s2/s3 的长耗时传输，
     网络状态可能已漂移；D-365 已实测同链路 RTT 可漂移 26-34%，这一漂移是仓库主动建模防范的真实风险）

phase 2: adaptive_download_window（新增 phase 类型，见 §8.3.5）
  ├─ 目标窗口时长 window_ms（默认建议 4000ms，见下）
  ├─ 请求上限 bytes（ceiling，非目标传输量；建议默认 512MB，见 §8.3.5 服务端约束）
  └─ 到窗口时长即取消底层请求（复用 AnebClient.downloadDrain，AnebClient.kt:496）；产出
     d3_goodput_mbps / d3_bytes_transferred / d3_window_actual_ms

phase 3: adaptive_upload_window（新增 phase 类型，同构镜像）
  ├─ 复用 AnebClient.uploadBurst（AnebClient.kt:363，与 S3 的 U1 上传同一方法）
  ├─ 请求上限 bytes（ceiling；建议默认 48MB，服务端硬顶 64MB，见 §8.3.5）
  └─ 产出 u3_goodput_mbps / u3_bytes_transferred / u3_window_actual_ms

phase 4: clock_sync（本版从"可选"改为**必选**——原因见 §8.2 第 4 条：窗后 RTT 复测是唯一能表达
  "传输前后 RTT 是否漂移"的手段，不做就彻底放弃了这个信号）
  └─ 20 个 echo 样本；产出 rtt_ref_ms_post，与 phase 1 的 rtt_ref_ms_pre 一起算出 rtt_drift_ratio
     （§8.3.3）；沿用 s3_multimodal.json 首尾各一次 clock_sync 的既有惯例
     （spec/profiles/server/s3_multimodal.json 首尾各一个 clock_sync phase）
```

窗口时长默认建议 **4000ms**（3000–5000ms 可配置区间），加上 phase1/4 各 20 样本 clock_sync（每个约
1-2s）与两个传输窗口，全场景预计约 **10-12s**（`est_duration_s` 建议值，见 §8.4.1 profile 草稿）。
**此值为本文新提议默认值，未经 PO 裁定**，见 §8.7-3。

#### 8.3.3 RTT 主导度自检（数值化判据，可执行）+ 窗后漂移诊断

```
ratio = window_actual_ms / rtt_ref_ms_pre
dominance_ok ⟺ ratio ≥ RTT_DOMINANCE_MIN(D-499 拍板=15；原建议默认 10)
             ∧ window_actual_ms ≥ ABS_FLOOR_MS(建议默认 300)
             ∧ bytes_transferred ≥ MIN_BYTES_FLOOR(建议默认 100KB)

rtt_drift_ratio = rtt_ref_ms_post / rtt_ref_ms_pre   （两者皆非 null 时才计算，否则 null）
```

- **`RTT_DOMINANCE_MIN=15`（D-499 拍板，原文建议 10 保留于下）**：判据=T63/D-498 489 真实样本阈值扫描（[10,37] 零判定差异，临界 RTT 收紧 400→267ms，§8.3.3 担心的 350ms 路径在 15 下被拒）。原论证：D-363 实测最高历史值是 s3 的 9.8×，且从未被判定为"安全"，只是"离开了
  时延区间"；10 是在该历史最高值之上留安全边际的整数取值。**已知边界风险**：§8.2 第 1 条论证里写
  "只要 RTT 本身不是病态地大（卫星/跨国高延迟中继除外）"，但落地判据是固定阈值——一条 RTT 350ms 的
  路径（未到卫星级但明显偏高）在 4000ms 窗口下 `ratio≈11.4`，恰好压过阈值、被判 `dominance_ok=true`，
  而这正是文字论证里被点名排除的那类路径的邻域。这不是可以在 spec 阶段"论证掉"的问题，**必须靠批③
  真机数据观察边界附近样本的实际表现**后再定阈值，本文不假装已解决，见 §8.7-2。
- **`ABS_FLOOR_MS=300`**：防止 RTT 极小（如同机房 WiFi RTT<5ms）时 `10×RTT` 本身退化到计时器/线程
  调度抖动量级的边界情形，与 ratio 条件取交集（AND，不是 OR）。
- **`MIN_BYTES_FLOOR=100KB`**：即便 `duration≫RTT` 结构性成立，若链路极慢导致窗口内实际传输字节数
  过少，goodput 数字本身噪声也可能过大。
- 三个常量均为**本文新提议、此前仓库从未拍板过的默认值**，必须走 `docs/DECISION_LOG.md` 正式入册
  流程，上线前不视为最终值（§8.7-2）。
- `dominance_ok=false` 时**不置 null**——数值仍然真实测得，只是标注不可信，通过 `kpi_quality` 的
  `low_confidence` 字段表达（§8.4.3），对齐 R-10：只有"测不出"才是 null，"测出但存疑"是
  `low_confidence=true` 的既有语义。
- **`rtt_drift_ratio` 不参与 `dominance_ok` 的判定**（避免又造一个循环依赖的阈值），而是作为独立
  诊断字段暴露：分析层/人工复核可以用它筛出"传输前后 RTT 差异悬殊、结果值得怀疑"的样本，即使
  `dominance_ok=true`。这是 §8.2"已知局限"段承认的那类情形（窗口中段拥塞）的**部分**弥补——
  能捕捉到"窗口结束时拥塞仍未消退"的情形，捕捉不到"窗口中段拥塞、结束前已消退"的情形。

**已知边界情形（窗口提前完成，`window_underrun`）**：若实测链路速率极快，`bytes_transferred ==
bytes_requested` 且 `window_actual_ms < window_target_ms`——即请求在窗口超时之前就已经完整传完
（`ceiling` 设小了）。此时"定长时间窗"的设计前提本身失效。本文档要求该情形必须被识别并标记
（`kpi_quality` 的 `low_confidence=true` 附加原因，或实现阶段专门记一条诊断日志），不得与正常的
"窗口到点截断"样本混算。

> **〔D-534 §2 订正：上面这两个"或"的选项不等价，而本文当初把它们并列了〕**
> 批③落地时取的是"记一条诊断日志"（`ScenarioRunner` 的 `ADAPTIVE_UPLOAD_WINDOW` /
> `ADAPTIVE_DOWNLOAD_WINDOW` 行带 `underrun=`），**字面上满足了本节**。但本节自己的目的句是
> 「**不得与正常的『窗口到点截断』样本混算**」——而**混算发生在分析层，分析层读 JSONL、
> 永远看不到日志**。同时批④验收标准（见该批次）要求如实报告"`window_underrun` 出现次数"，
> 那个数同样只能从产物里数。
> 故自 D-534 起 `u3_window_underrun`/`d3_window_underrun` **进契约**（§8.4.2 字段表，
> `boolean|null`，非必填，缺失≠false）。
> **如实记两点**：①它并非完全不可得——`window_actual_ms < window_target_ms` 且
> `bytes_transferred` 达上限即可推导，只是要三个字段加 profile 上限联合判断；
> ②`low_confidence` 那条路径**只在 `rtt_dominance_ok=true` 时可解**——ok 为 false 时
> `low_confidence` 恒真，underrun 被掩盖。进契约是为了让它有**单一来源**，
> 而不是让每个消费方各推一遍（D-264）。

> **〔D-534 §2 并入裁定 · 08-22 施工：`run.skipped_profiles` 上线〕**
> 本 spec 落地时写明「缺 profile 时静默跳过（既有容忍风格）」——实现里其实打了一行
> `PROFILE_WARN missing=s4_throughput` 日志，**准确说法是「日志里有、产物里没有」**：
> 分析层读 JSONL，无从分辨一个 run 的 s4 是「跑了」还是「被跳过」，而两者对
> 吞吐覆盖统计的含义完全不同。核实过既有通道均不合适（`guard_metadata` 是
> NetGuard 元数据、run 开头即构建完且分析层零读者——写进去等于再造一个
> 写了没人读的信号），故新增 run 级字段（大脑 08-22 裁定，合并版）：
> **`skipped_profiles`（字符串数组，非必填）**——本次 run 里「配置上应跑却因
> profile 缺失而被跳过」的 profile id 列表。`[]`=明确零跳过；`null`/缺失=该 run
> 早于本字段上线（**R-10：缺失≠空数组**——不知道跳没跳，不是知道没跳）。
> 数组为将来的可选相位留位；今天唯一生产者是本 spec 的 s4_throughput 分支。

#### 8.3.4 慢启动双口径：数据驱动，不用固定毫秒常量

**U3（上行）：直接复用既有的数据驱动检测器，不新造**——`UploadAnalysis.estimateSlowStart`
（`app/probe/.../engine/UploadAnalysis.kt:28-56`）已经是数据驱动的：要求 ≥16 个**服务端权威**
到达时戳（`chunkArrivalUs` 来自 `/upload` 响应的 `UploadServerView`，不是客户端本地写入 socket
buffer 的时刻）、用滑动窗口找首个瞬时速率达到稳态一半的位置，找不到即整体退化为 null（U1 既有语义：
excl 口径不出值，绝不猜）。s4_throughput 的 `adaptive_upload_window` 阶段复用 `AnebClient.uploadBurst`——
与 S3 的 U1 上传是**同一底层方法、同一 wire 合同**，因此天然携带同一份 `UploadServerView`，U3 的
excl_slow_start 口径可以**逐字复用** `UploadAnalysis.estimateSlowStart`，不需要新写任何检测逻辑，
只需要把 `chunk_kb`（`s4_throughput.json` 里配置为 64，与 S3 上传一致）传入。

**D3（下行）：需要一个新函数，理由是"下行的数据形状和信任模型都与上行不对称"**——
`AnebClient.downloadDrain`（`AnebClient.kt:496-530`）按 256KB **上限**读取（`source.read(readBuf,
262_144L)`），实际每次读到的字节数是**可变的**（取决于 socket 缓冲区状态），不像上行那样有
"固定 `chunk_kb` 大小的块"这个前提，`UploadAnalysis.estimateSlowStart` 的"按固定块计数"模型
不能直接套用。同时，`AnebClient.kt:492-494` 的既有注释明确指出下行读时刻**不需要**服务端回声确认
（"读到的字节即真实到达的网络字节，无上行那种写本地 socket buffer 的灌注偏差，是比上行更纯净的吞吐
口径"）——即下行侧的客户端本地时间戳已经被仓库既有设计判定为可信来源，不像上行那样必须依赖
`UploadServerView`。这两点共同决定了 D3 需要一个**按时间窗滑动、直接消费 `(累计字节数, 时间戳)`
原始采样序列**的新函数，而不是"移植/镜像"上行的按块计数模型：

```kotlin
// 新增独立、无 Android 依赖的纯函数（建议 TransferWindowAnalysis.kt，与 UploadAnalysis 同目录）
object TransferWindowAnalysis {
    /**
     * 按滑动时间窗（而非固定块计数）估计慢启动终点，适用于读取粒度可变的传输
     * （downloadDrain 的 onChunk 回调：(累计字节数, elapsedRealtimeNanos)，客户端本地时间戳
     * 已被 AnebClient.kt:492-494 判定为下行侧可信来源，不需要服务端回声）。
     * @param samples 按 tsNanos 升序的 (cumulativeBytes, tsNanos) 序列
     * @param steadyWindowUs 稳态速率估计窗口（默认取后 1s）
     * @param probeWindowUs 滑动探测窗口（默认 200ms）
     * @param steadyFraction 判定"已达稳态"的速率比例阈值（默认 0.5，对齐 UploadAnalysis 既有取值）
     * @return (slowStartUs, slowStartBytes)；样本不足或找不到终点返回 null（同 UploadAnalysis 语义：
     *   excl 口径不出值，绝不猜）
     */
    fun estimateSlowStartByRate(
        samples: List<Pair<Long, Long>>,
        steadyWindowUs: Long = 1_000_000L,
        probeWindowUs: Long = 200_000L,
        steadyFraction: Double = 0.5,
    ): Pair<Long, Long>?
}
```

该函数的单测夹具必须能被证明真的会失败（D-321/D-322 纪律：造反例，不推理）：至少覆盖
①恒定速率流（无爬坡）应返回 null；②前 1s 明显低速、之后转为 4 倍速的合成流应返回接近 1s 的
`slowStartUs`；③样本数过少（窗口提前 underrun）应返回 null。

`u3_goodput_excl_slow_start_mbps`/`d3_goodput_excl_slow_start_mbps` 双口径与既有 U1 纪律一致：
主口径含慢启动（全窗口平均），并列口径剔除爬坡段后的稳态滑窗值；无法估计慢启动时并列口径为 null。

#### 8.3.5 与既有声明式 `phases[]` 模型的接口：新增 phase 类型

`ProfilePhase`（`app/probe/.../engine/ProfileModels.kt:29-60`）与其 Go 侧镜像 `Phase`
（`server/profiles.go:30-68`）是一个"字段按 `type` 选用"的联合体，`upload_burst`/`download_burst`
两个既有 phase 类型的核心字段是 **`bytes: Long`（精确字节数）**，不存在"运行 N 毫秒"的时长概念。
`ScenarioRunner.kt:137-168` 按 `phase.type` 做 `when` 分发，**未识别的 `type` 走
`else -> emit("PHASE_SKIP ... unknown_type=...")` 分支静默跳过而不崩溃**——这意味着"固定时长窗口"
语义**不能靠复用 `upload_burst`/`download_burst` 现成执行器实现**，必须新增两个 phase 类型：

```kotlin
// ProfileModels.kt 新增字段（additive，默认值 0，旧 JSON 不受影响）
val windowMs: Int = 0,  // @SerialName("window_ms")

companion object {
    // 既有常量不变
    const val TYPE_ADAPTIVE_DOWNLOAD_WINDOW = "adaptive_download_window"
    const val TYPE_ADAPTIVE_UPLOAD_WINDOW = "adaptive_upload_window"
}
```

```go
// server/profiles.go Phase struct 新增镜像字段
WindowMs int `json:"window_ms,omitempty"`
```

**Go 侧为什么必须同步改（精确理由，非"契约性改动需双端同步"的笼统说法）**：实测核实
`server/profiles.go:126-154` 的 `loadProfiles()` 用裸 `json.Unmarshal(data, &p)`（未启用
`DisallowUnknownFields`），Go 的 `encoding/json` 对**未知输入键**默认静默忽略、不报错——所以哪怕
不改 Go 结构体，`s4_throughput.json` 也能被服务端正常解析、不会崩。**真正的风险点在 `handleProfiles`
（`server/profiles.go:157-177`）的下发路径**：它把内存里的 `Profile`/`Phase` 结构体重新 `json.Encode`
成 `GET /api/v1/profiles` 响应体下发给客户端——如果 `Phase` 结构体没有 `WindowMs` 字段，服务端在
**反序列化时读不到**这个键（字段不存在，值就是零值，Go 层面看不出"零值"和"缺失"的区别）、**再序列化
下发时这个键就会消失**。而 `ProfileRepository.kt:20/50` 显示客户端优先从服务端拉取 profile
（`profile_source="server"`），只有拉取失败才退回 `assets_fallback`——**这是主路径，不是边缘情形**。
因此不加这个字段不会让任何东西"报错"，而是会让 `window_ms` 在服务端到客户端这一跳**静默消失**，
客户端拿到的 `adaptive_download_window`/`adaptive_upload_window` 相位会因为 `windowMs` 默认值 0
而立即触发 window_underrun 式的异常行为——这比"抛异常"更隐蔽、更危险，是必须同步改动的确凿理由。

**服务端 bytes ceiling 校验不需要改动**：实测核实 `server/handlers_download.go:36`
（`positiveInt64Query(r, "bytes", defBytes, downloadMaxBytes)`）与 `server/handlers_upload.go:41/103`
（`http.MaxBytesReader(w, r.Body, uploadMaxBytes)`）两处**硬性运行期校验直接作用于请求的实际字节数/
请求体大小**，与该次请求引用的是哪个 profile、哪个 phase 类型完全无关——只要 §8.4.1 的 ceiling 默认值
（512MB/48MB）不超过服务端硬顶（1GiB/64MB），新 phase 类型天然受到与既有 `download_burst`/
`upload_burst` 完全相同的服务端保护，**零额外 Go 代码改动**。另有一个**不适用**于本方案的旁路：
`server/profiles.go:86-123` 的 `downloadDefaultsFromProfile()` 按 `?profile=X&phase=N` 查询参数、
通过 `p.downloadBurstPhase(idx)` **精确匹配 `type=="download_burst"`** 查找相位并校验其 `bytes`——
这是一条独立于场景执行主路径的可选便捷入口；实测核实 `ScenarioRunner.kt:233-234/272` 显示客户端
场景执行路径直接拼接 `?bytes=N` 裸参数请求 `/download`/`/upload`，从不使用 `?profile=X&phase=N`
这条入口，因此这个函数与 `adaptive_download_window`/`adaptive_upload_window` 两个新类型无关，不需要
跟着扩展。

### 8.4 契约字段定义

#### 8.4.1 新场景 profile 文件（新文件，需配对拍守卫——见批②）

`spec/profiles/server/s4_throughput.json`（草稿，字节数/窗口时长为建议默认值，待 §8.7 裁定）：

```json
{
  "profile_id": "s4_throughput",
  "version": "0.1.0",
  "kpi_set": "agent-qoe-kpi-v0.3",
  "description": "单流自适应窗口 goodput 探针：固定测量窗口，字节数随链路速率自然伸缩，避免 D-363 式固定负载 RTT 伪影；仅测单流应用层 goodput，非链路容量",
  "est_duration_s": 12,
  "phases": [
    { "type": "clock_sync", "samples": 20 },
    { "type": "adaptive_download_window", "window_ms": 4000, "bytes": 536870912, "chunk_kb": 256 },
    { "type": "adaptive_upload_window", "window_ms": 4000, "bytes": 50331648, "chunk_kb": 64 },
    { "type": "clock_sync", "samples": 20 }
  ]
}
```

（`bytes` 字段此处含义为**请求上限（ceiling）**，不是目标传输量——与既有 `upload_burst`/
`download_burst` 里 `bytes` 表示"精确传输量"的语义不同，属于同一字段名在不同 `type` 下的既有联合体
设计模式的延伸，需要在 `ProfileModels.kt`/`profiles.go` 的字段注释里显式区分。phase 4 的
`clock_sync` 本版从"可选"改为必选，用于 §8.3.3 的窗后 RTT 复测。）

**必须同批创建 `profiles/s4_throughput.json`**（与 `spec/profiles/server/s4_throughput.json` 语义
逐字节一致的运行时镜像）——实测核实 `scripts/validate_profiles.py` 是一个**已经存在、已经接进
`verify_all` 的 `profiles-deep` 步骤**（`scripts/verify_all.ps1:280-303`）的通用 spec↔runtime 对拍
守卫：它比较 `spec/profiles/server/<id>.json` 与 `profiles/<id>.json` 两侧的语义等价性，**在两侧任一
文件缺失时即报错**（`validate_profiles.py:104-107`）。新建 `s4_throughput.json` 若只放一侧，
`verify_all` 会立即 FAIL，不是"建议配一道守卫"，而是"不配就过不了既有发布门"。

**必须同批扩展 `scripts/validate_profiles.py` 的 `PHASE_SPEC`**（实测核实其为一个**封闭枚举**，
`validate_profiles.py:33-41`：`clock_sync/upload_burst/download_burst/think_pause/token_stream/
tool_loop` 六种已知类型，未登记的 `type` 会被 `check_structure()` 判定为
`"unknown phase type"`——`validate_profiles.py:78-81`）：

```python
PHASE_SPEC = {
    # ...既有六项不变...
    "adaptive_download_window": {"window_ms": "int", "bytes": "num", "chunk_kb": "num"},
    "adaptive_upload_window":   {"window_ms": "int", "bytes": "num", "chunk_kb": "num"},
}
```

不做这一步，`s4_throughput.json` 一落地，`verify_all` 的 `profiles-deep` 步骤就会因"未知 phase
type"报 FAIL——这是本方案能否通过既有发布门的硬约束，不是可选加固。`scripts/tests/
test_validate_profiles.py` 需要同批追加至少一条覆盖新 phase 类型的用例（正例+缺字段负例各一条，
仿现有测试对 `upload_burst`/`download_burst` 的覆盖方式）。

#### 8.4.2 `result-run.schema.json` 新增字段（`scenarios[].kpi`，全部可选/nullable，additive，
不影响任何现有 `required` 列表；实测核实 `scenarios[]` 数组**所有条目共用同一个**
`#/definitions/scenario`，没有按 `profile_id` 分支的变体 schema——`schema.json:101-103`）

**命名原则**：**不复用 `u1_`/`d1_` 前缀**——仓库里 basic_network 的 `ThresholdGrader` U1/D1 与 token 的
`AqsInputMapper` U1/D1 已经是"同名不同义"的两套 KPI（§8.1 表），本方案若再复用 `u1_goodput_mbps` 会
制造第三个同名不同义的 U1。采用与既有 `T1-T5/N1-N2/U1-U2/D1/S1` 单字母+数字命名法一致、但**数字延续
现有分组序号**的新 id：**`U3`（自适应上行探针）**——U 组已有 U1/U2，续到 U3，无冲突。下行侧本应续到
`D2`，但实测核实本仓库存在一个**更大、当前仍在活跃使用**的裸 token 命名空间：`docs/DECISION_REQUEST_
2026-08-02.md`、`docs/M2_GRID_DESIGN_PROPOSAL.md`、`docs/BRAIN_TASKBOARD.md` 里"D1/D2/D4"是网格
决策旋钮的固定编号（D1=点位真名/点位数、**D2=是否双运营商**、D4=是否忙闲两趟），截至今天
（2026-08-04）仍在被 PO 反复引用裁定。虽然两个命名空间（wire schema 字段 vs 决策文档标签）不会造成
代码级冲突，但本仓库反复点名"同名不同义"是自己踩过多次的真实缺陷模式——**本方案正是因为要避开 U1/D1
复用才选了续号方案，若不检查这一层就用掉"D2"，等于在避开一个陷阱的同时踩进另一个同构的陷阱**。
本版改用 **`D3`**（跳过 `D2`，`D1` 留给既有半成品字段，`D2` 让给网格决策旋钮的既有语义，`D3` 是
下一个未被占用的号）：

| 字段 | 类型 | 含义 | 引自 |
|---|---|---|---|
| `u3_goodput_mbps` | number\|null | 窗口内平均 goodput（含慢启动，主口径），公式同构 `KpiCalculator.kt` 的 `goodputMbps(bytes,durationNanos)` | 本文新增；口径纪律引自 `u1GoodputMbps`（`KpiCalculator.kt:191`） |
| `u3_grade` | string\|null | 分级（若批④决定接入打分，见 §8.4.4；诊断期恒为 null） | 同构 `u1_grade`（`schema.json:149`） |
| `u3_goodput_excl_slow_start_mbps` | number\|null | 剔除慢启动后的稳态口径，复用 `UploadAnalysis.estimateSlowStart`（§8.3.4） | 同构 `u1_goodput_excl_slow_start_mbps`（`schema.json:150`） |
| `u3_window_target_ms` | integer | 本次配置的目标窗口时长（来自 profile phase 的 `window_ms`） | 本文新增 |
| `u3_window_actual_ms` | number\|null | 实测窗口时长（可能因请求提前完成而小于 target，见 §8.3.3 `window_underrun`） | 本文新增 |
| `u3_bytes_transferred` | integer\|null | 窗口内实际发送字节数 | 本文新增 |
| `u3_rtt_ref_ms_pre` | number\|null | phase 1（传输前）测得的 RTT 基准 | 本文新增，复用 `n1_rtt_p50_ms` 同款口径 |
| `u3_rtt_ref_ms_post` | number\|null | phase 4（传输后，本版必选）测得的 RTT | 本文新增 |
| `u3_rtt_drift_ratio` | number\|null | `rtt_ref_ms_post / rtt_ref_ms_pre`；两者任一为 null 则整体 null | 本文新增，见 §8.3.3 |
| `u3_rtt_dominance_ratio` | number\|null | `window_actual_ms / rtt_ref_ms_pre`，即自检判据本身，一等字段 | 本文新增，见 §8.3.3 |
| `u3_rtt_dominance_ok` | boolean | 是否满足 §8.3.3 三条件交集 | 本文新增 |
| `u3_window_underrun` | boolean\|null | §8.3.3 的「窗口提前完成」情形本身：`true`=到点前已传完，`false`=正常到点截断，`null`=未跑 s4 或早于本字段上线（缺失≠false，R-10） | **D-534 §2 新增**：此前只折进 `low_confidence` 并打一条日志，而批④验收标准要数它的出现次数 |
| `d3_window_underrun` | boolean\|null | 下行方向的同一语义 | 同上 |
| `d3_goodput_mbps` / `d3_grade` / `d3_goodput_excl_slow_start_mbps`（复用 `TransferWindowAnalysis`，§8.3.4）/ `d3_window_target_ms` / `d3_window_actual_ms` / `d3_bytes_transferred` / `d3_rtt_ref_ms_pre` / `d3_rtt_ref_ms_post` / `d3_rtt_drift_ratio` / `d3_rtt_dominance_ratio` / `d3_rtt_dominance_ok` | 同构镜像（下行） | — | 同上 |

`u3_rtt_ref_ms_pre`/`d3_rtt_ref_ms_pre`（以及 `_post`/`_drift_ratio`）**两组字段取值恒相同**——两者
共享同一对 phase 1/phase 4 clock_sync 测量结果，只是各自 KPI 块自包含（逐块自包含、允许跨块重复的
风格，与仓库既有惯例一致）。消费方（分析层/v2）读取任一组即可，不需要交叉校验两组是否一致——若某
实现出现不一致，那本身就是一个 bug 信号，值得单独测试覆盖（记入批③验收标准）。

**同批顺手补齐的既有半成品**（与本方案独立、优先级更高、风险更低，§8.1 已指出）：
`d1_goodput_mbps` / `d1_grade` 两个字段——`KpiCalculator.kt` 已算出（`d1GoodputMbps`，
`KpiCalculator.kt:200/409-411`），`ResultReporter.kt` 从未 `put()`，`result-run.schema.json` 也从未
定义对应字段，`kpiValuePairs()`（`TestEngine.kt:809-822`，D-373 唯一词汇来源）也从未把 D1 纳入
`kpi_quality`。本章节要求同批补齐，避免"算了但没上线"的半成品状态延续到新 KPI 上。**不补
`d1_goodput_excl_slow_start_mbps`**——实测核实 `KpiCalculator.kt` 里 D1 只有单一口径，没有并列口径
可补，若未来要加，需要先决定下行侧的慢启动检测用 §8.3.4 新增的 `TransferWindowAnalysis` 还是别的
方案，不在本批范围内。

#### 8.4.3 `kpi_quality` 词汇扩展（复用既有机制，且明确声明与 U1/D1 的低置信判据**刻意不同**）

`scenario.kpi_quality`（`result-run.schema.json:195-206`，D-373）是仓库已有的 per-KPI 低置信表达
机制：`{sample_count, low_confidence}`，键 = KPI 短名。**本方案复用该机制，不新增 `validity` 枚举
或 `low_confidence_reason` 嵌套对象**。

新增短名 **`U3`**、**`U3_excl_slow_start`**、**`D3`**、**`D3_excl_slow_start`**，写入方式与既有词汇
完全一致——唯一词汇来源是 `TestEngine.kt:809-822` 的 `kpiValuePairs()`，本方案要求在该清单里追加
四行 `"U3" to kpi.u3GoodputMbps` 等。

**关键澄清**：U3/D3 的 `low_confidence` 触发条件**不能**类比既有 U1（`MIN_UPLOAD_SAMPLES=3`）、D1
（`MIN_DOWNLOAD=3`）的判据风格。`MIN_UPLOAD_SAMPLES=3`/`MIN_DOWNLOAD=3` 比的是**同一次场景执行内部**
有效传输次数是否 ≥3（例如 `s3_multimodal.json` 每次执行内有两次 `upload_burst`/`download_burst`，
`u1Incl.size`/`d1List.size` 数的是这两次里有效的那几次）。而 `s4_throughput.json`（§8.4.1）的设计是
**每次场景执行恰好一个** `adaptive_upload_window`/`adaptive_download_window` 相位——不是"样本不够
3 个"，而是**这个设计结构上永远只产出 1 个窗口测量**，套用"n<3→low_confidence"这把尺子对它没有意义
（会让 U3/D3 永远 low_confidence=true，不管测量质量多好，这本身就是一种谎报）。**因此 U3/D3 的
`sample_count` 恒为 `1`（结构性事实，不是低样本量信号），`low_confidence` 完全由 §8.3.3 的自检结果
决定**（`!rtt_dominance_ok` 或 window_underrun 或字节/样本数不足其一即 `true`）——**这是本方案对
既有 kpi_quality 机制的一次刻意分叉，扮演的是 U1/D1 那把"样本量下限尺子"在结构上不适用时的替代角色，
不是延续那把尺子**。这一点必须在实现与文档两处都写清楚，避免下一个读者把两者当成同一件事。

#### 8.4.4 `aqs_version` 语义：诊断期与接入期分离

沿用仓库已确认的 additive-facet 惯例（`AqsScorer.kt` 命名规则 `aqs[-facet]-v{major}.{minor}`，
现有 `aqs-v0.1`/`aqs-v0.2`/`aqs-token-v0.1`/`aqs-voice-v0.1`/`aqs-voice-v0.2`/`aqs-voice-sim-v0.1`
等并列版本号）。

- **诊断期（批③，见附录A拆批方案）**：`s4_throughput` 的 KPI **不进任何现有 AQS facet**——
  `AqsInputMapper` 的 `U1←S3`/`D1←S3` 合同（`AqsInputMapper.kt:17-21/65/68-69`）保持逐字不变，
  `run.aqs`/`run.aqs_v02`/`run.aqs_token` 三个既有字段零侵入。`scenarios[]` 数组里只是多了一条
  `profile_id=="s4_throughput"` 的诊断记录，供离线积累真实数据（比照 M2 试点纪律，n≥15 才能谈
  稳定性）。**不产出 `run.aqs_throughput` 字段**。
- **接入期（批④，需数据支撑 + 大脑/PO 正式裁定）**：视诊断期数据结果，在两条路径间二选一，
  **均不在本批 spec 范围内自行拍板**：
  1. 新增独立 additive facet `run.aqs_throughput`（`aqs_version="aqs-throughput-v0.1"`），结构对齐
     `run.aqs_v02` 现有 shape，与 `run.aqs`/`aqs_token` 完全解耦；
  2. 切换 `AqsInputMapper` 现有 `U1←S3`/`D1←S3` 映射为 `U1←S4`/`D1←S4`（或给出可解释的择优/混合
     规则），此时必须比照 `AQS_VERSION_VOICE→AQS_VERSION_VOICE_V02` 的既有先例把
     `AQS_VERSION_TOKEN` 从 `aqs-token-v0.1` 升级到 `aqs-token-v0.2`（旧常量不删），同步更新
     `AqsInputMapper.MAPPING_DESCRIPTION`（机器可解析日志行，`AqsInputMapper.kt:40-41`）及所有解析
     该字符串的下游。**若选此路径，需先解决 §8.0 的单流局限**——把一个已知会在高 BDP 路径低估
     容量的单流数字直接替换现有 U1/D1 评分口径，需要额外的方法学评审，不能只因为"有真机数据支撑"
     就自动通过。

### 8.5 mode 枚举与重复语义

**结论：`s4_throughput` 每次 `run()` 执行恰好一次，与 `config.mode` 无关（QUICK/FORENSIC 都只跑
一次），不进入 `TestEngine.kt:316-333` 的 `rounds`/拉丁方循环。**

理由：
1. `rounds = when (config.mode) { QUICK -> ...; FORENSIC -> ... }`（`TestEngine.kt:317-320`）与
   `ids = ProfileParser.REQUIRED_IDS`（3 个场景）绑死在一起，重复次数服务于"抵消 S1-S3 三场景之间
   的拉丁方排位偏倚"这一统计目的（`order_effect` 分析）。`s4_throughput` 天然不参与这个排位（§8.3.1
   已明确它不进 `REQUIRED_IDS`），重复它 3 遍不会带来同等的统计学收益。
2. 若随 forensic 重复 3 遍，会把一个已经不轻的探针（约 10-12s、下行最多 512MB/上行最多 48MB）的
   时间与流量预算再乘 3——在"诊断期先用尽量低的代价换真机数据"这一目标下不划算。
3. §8.4.3 已经把 U3/D3 的 `sample_count` 定义为结构性恒为 1——这与"只跑一次"是自洽的：若要用
   forensic 重复来提升可信度，应该体现为"多个独立 `run()`"（对应批③验收标准里的 n≥15 次独立 run），
   而不是单个 run 内部的 repeat_index 0/1/2。

**落地**：`repeat_index` 恒为 `0`；`order_index` 延续场景循环里已经用到的同一个单调计数器（即等于
"全部轮次执行完毕后场景总数"），使其在排序上自然落在"最后执行"的位置。**`scenario_order`
字符串格式完全不变**——`orderRecord.joinToString("|")`（`TestEngine.kt:554/613`）的生成代码不改动，
`s4_throughput` **不出现在这个字符串里**（它本来就不参与该字符串记录的"拉丁方实际顺序"语义，把它
硬塞进去反而会制造一个新的解析歧义）。**`run.profile_versions`（顶层聚合字段）同样完全不变**——
`ProfileParser.versionString()`（`ProfileModels.kt:102-104`）只遍历 `REQUIRED_IDS` 三元素，本方案
不扩展这个字段（理由与 scenario_order 相同：该字段的语义是"横比分组用的三场景版本串"，
`s4_throughput` 不参与横比分组）；`s4_throughput` 自己的版本号通过它在 `scenarios[]` 数组里那条
记录自带的 `profile_version` 字段（单数、场景级）表达，两个字段各司其职、互不覆盖。

### 8.6 执行接线：复用既有流水线，不建旁路

**设计决策**：`s4_throughput` 的执行**复用与 s1/s2/s3 完全相同的流水线**——
`ScenarioRunner.run()` → `ScenarioKpi.buildKpiInput()` → `KpiCalculator.calculate()` →
`buildScenarioEntity()` → `ItlHistogram.of()` → `persistScenario()`——而不是为它单独写一条捷径。
这不只是工程简洁性的考虑，而是**唯一能让 §8.4.2 之外、schema 已有的必填字段（`kpi.seq_gap_count`/
`seq_dup_count`/`itl_histogram.buckets_version`/`total` 等，均为不可空类型）在 `s4_throughput` 场景
下自动正确落值的办法**：`s4_throughput.json` 没有 `token_stream` 相位，`input.tokenSamples` 天然为
空列表，`KpiCalculator.calculate()` 对空 token 序列本来就有既定行为（`seq_gap_count=0`/
`seq_dup_count=0`——对一个空序列而言零间隔是精确值，不是 R-10 意义上的"拿 0 顶替未测量"哨兵；
`ItlHistogram.of(emptyList())` 产出标准桶结构、`total=0`）——**复用既有流水线让这些字段"免费"正确，
不需要为 s4_throughput 写任何特殊分支**。

**批③需要新增的 TestEngine.kt 代码**：`runLoop@ for ((round, order) in rounds.withIndex())`
（`TestEngine.kt:331`）结束后，需要一段新的、显式的执行块：

```
若 loaded.profiles 含 "s4_throughput"：
    以与循环体内完全相同的方式跑一次该场景（runner.run/buildKpiInput/KpiCalculator.calculate/
    buildScenarioEntity(repeatIndex=0, orderIndex=<循环结束时的计数值>)/ItlHistogram.of）
    只 scenarioReports.add(entity to hist)——不写入 kpiByScenario（AqsInputMapper.map() 的输入，
    §8.4.4 已声明诊断期零侵入，这里从数据流层面确保）
    不追加进 orderRecord（§8.5 已声明 scenario_order 不变）
否则：静默跳过（缺 profile 时的既有容忍风格，一条 PROFILE_WARN 日志足够，不 require() 抛异常）
```

`clock`/`network_snapshot`/`parse`/`buffering` 四个必填对象同样通过复用 `buildScenarioEntity()`
自动获得既有语义（`clock` 来自该次执行自己的 `outcome.offsetTrack()`；`network_snapshot.radio` 沿用
既有"仅蜂窝场景才写"的条件逻辑，`TestEngine.kt:443-447`；`parse` 两字段因无 SSE 天然为 null；
`buffering` 因无残差序列天然全 null）——全部不需要特殊分支。

### 8.7 待裁定清单（交大脑/PO）

| # | 事项 | 选项 | 本文推荐（非最终裁定） |
|---|---|---|---|
| 8-1 | 本章节落位 | (a) 插入 `INSTRUMENTATION_SPEC.md`（与文档标题/§0.1 范围冲突）/ (b) 另立独立文档（本文当前形态，仿 Profile 4 先例） | **(b)（已按此落地）** |
| 8-2 | `RTT_DOMINANCE_MIN`/`ABS_FLOOR_MS`/`MIN_BYTES_FLOOR` 三个新常量取值，含 §8.3.3 已指出的"阈值边界附近样本表现未知"风险 | 本文建议 10 / 300ms / 100KB，或调整 | **已拍板（D-499：15/300ms/100KB 转正）**——原"等真机边界分布"要求被 T63 换问法解决（现有 489 样本证明 [10,37] 区间零差异，蜂窝窗降级为确认性复核，日落尾巴见 D-499） |
| 8-3 | 窗口时长 `window_ms` 默认值 | 本文建议 4000ms（区间 3000-5000ms） | 需与 quick/forensic 时长预算协调后定；§8.5 已确定不随 forensic 重复，故只需协调单次探针本身的预算 |
| 8-4 | 下行/上行 `bytes` ceiling 默认值 | 本文建议 512MB / 48MB（服务端硬顶 1GiB / 64MB，§8.3.5 已确认零额外服务端改动） | 需真机验证是否会在极快链路上触发 `window_underrun` |
| 8-5 | 诊断期结束后是否接入打分（§8.4.4 两条路径） | 展示型诊断 vs 正式进 AQS | **必须在批①/批③立项时问清楚**，不要等批④做完才发现产品只要前者；若选路径 2（切映射），额外需要 §8.0 单流局限的方法学评审 |
| 8-6 | `s4_throughput.json` 的 `kpi_set` 是否需要独立版本号 `agent-qoe-kpi-v0.3` | 批准新版本号 / 复用现有 `v0.2` | 本文建议批准新版本号 |
| 8-7 | 是否需要用户可见的流量消耗提示 | 加提示/默认 WiFi-only / 不处理 | 产品侧需补，本文未定义 |
| 8-8 | 窗口传输*过程中*的拥塞可见性（§8.2"已知局限"：当前只有窗前/窗后两次静态 RTT，测不到窗口中段拥塞） | (a) 诊断期接受局限，仅用 `rtt_drift_ratio` 做粗粒度过滤 / (b) 立项设计独立连接并发 echo 探针（更大改动，需单独评审） | **(a)**，(b) 留作批④之后视数据需要与否单独立项 |
| 8-9 | `U3`/`D3` 命名是否最终采纳（跳过 `D2` 以避开网格决策旋钮命名空间碰撞） | 采纳 `D3` / 另选前缀彻底避开单字母+数字命名法 | 本文建议采纳 `D3`，并把"跳过 D2"的理由写进 spec 正文（已在 §8.4.2 写明），避免未来读者以为编号有缺口是笔误 |

### 8.8 本文的数字账（自查）

**本文引用的既有实测数字（全部带出处）**：D-363 三档倍数、D-365 RTT 漂移 26-34%、
`downloadMaxBytes=1GiB`（`server/handlers_download.go:13`）、`uploadMaxBytes=64MB`
（`server/handlers_upload.go:18`）、`SpeedRunner` 6s 窗口、`MIN_UPLOAD_SAMPLES=3`/`MIN_DOWNLOAD=3`
（`KpiCalculator.kt:266/271`，本版同时指出其对 U3/D3 不适用，§8.4.3）、`validate_profiles.py` 的
`PHASE_SPEC` 六项既有类型与其对新类型的拒绝行为（`validate_profiles.py:33-41/78-81`）、Go
`json.Unmarshal` 对未知键静默忽略而非报错的行为（`server/profiles.go:126-154` 未启用
`DisallowUnknownFields`）。

**本文新提议、原标记"待裁定"、现已 D-499 拍板转正的量**：`RTT_DOMINANCE_MIN=15`（拍板值；本文原提议 10）、`ABS_FLOOR_MS=300`、
`MIN_BYTES_FLOOR=100KB`、`window_ms=4000`、下行/上行 `bytes` ceiling `512MB`/`48MB`，以及 §8.7
全部九项。

**本文未验证的量**：`window_ms=4000` 在真实千兆级 WiFi 上是否会触发 `window_underrun`——需批③真机
数据；`TransferWindowAnalysis.estimateSlowStartByRate` 的三个窗口参数（`steadyWindowUs`/
`probeWindowUs`/`steadyFraction`）在真实下行流量的可变读取粒度下是否需要调整——需批②单测+批③
真机数据双重验证。

---

## 附录A 拆批实现方案（T47 交付物之二）

**总体依赖顺序**：批①②可并行（互不依赖）；批③依赖①②的产出（新常量函数 + D1 序列化补齐 +
schema 字段就绪 + profile 文件对拍守卫就绪）；批④依赖批③的真机数据 + 大脑/PO 裁定；批⑤依赖批④是否
发生；批⑥独立、不阻塞①-④。**任一批开工前必须先有 §8.7 对应待裁定项的裁定结果**。

### 批① D1 半成品补齐 + S3 现有负载的诊断日志（低风险，独立于本方案是否最终被采纳都有价值）

**范围**：
1. `KpiCalculator.kt` 已算出的 `d1GoodputMbps`（`KpiCalculator.kt:200/409-411`）接入
   `ResultReporter.kt` 的 `put()` 调用（新增 `d1_goodput_mbps`/`d1_grade` 两个 wire 字段——**不包括**
   `d1_goodput_excl_slow_start_mbps`，实测核实 D1 没有这个口径，见 §8.4.2 说明）。
2. `result-run.schema.json` 的 `scenario.kpi` 新增上述两个字段（非 `required`，纯 additive）。
3. `TestEngine.kt:809-822` 的 `kpiValuePairs()` 追加 `"D1" to kpi.d1GoodputMbps` 一行——这是
   `lowConfidenceKpis`/`kpiSampleCounts` 的唯一词汇来源，D1 上线至今从未进入这个清单，导致它连
   `kpi_quality` 都没有，本批一并补齐。
4. **具体消费方（不是"建议"，是验收项）**：`app/probe/src/main/java/com/aneb/probe/ui/ResultFormat.kt`
   新增一行 D1 渲染（实测核实该文件当前对 D1 全文零引用，U1 有专门渲染行，`ResultFormat.kt:148/200`
   附近），使 D1 从"wire 上线但仍无人读"（D-276 描述的模式换了个形态重现）变成有真实读者。
5. 给 S3 现有 1MB 上传/12MB 下行固定负载测量加一条**只读诊断日志**（`transfer_duration_ms /
   rtt_p50_ms` 比值，不做任何 gate/拒绝），把 D-363 的一次性分析变成持续观测。

**依赖**：无（可立即开工，不依赖 §8.7 任何一项裁定）。

**验收标准**：
- `d1_goodput_mbps`/`d1_grade` 两字段在真机测得的一条 wire body 里可见（非 null，`s3_multimodal`
  场景下），`schema.json` 校验通过。
- `kpi_quality.D1.sample_count`/`low_confidence` 在同一条 wire body 里可见。
- `ResultFormat.kt` 的 D1 渲染行存在，且有对应 UI 测试或至少一条断言其被调用的单测。
- App 单元测试全绿；新增至少一条断言"`d1_goodput_mbps` 在 wire 输出中存在"的序列化单测。
- 诊断日志在至少一次真机 run 里可见（格式建议
  `THROUGHPUT_DIAG scenario=s3_multimodal direction=up bytes=1048576 duration_ms=… rtt_ref_ms=… ratio=…`）。

### 批② Profile 相位契约定稿 + 对拍守卫扩展（双端同步）

**范围**：
1. **新增独立、无 Android 依赖的纯 Kotlin 函数**：
   - `RttDominanceGuard.evaluate(windowActualMs, rttRefMs, bytesTransferred): DominanceVerdict`
     （§8.3.3 三条件交集判据）；把 D-363 的三个历史数据点（s1 1.60-1.99×应判"不安全"/
     s2 5.7-7.7×/s3 6.8-9.8×）直接固化为该函数的单元测试回归夹具。
   - `TransferWindowAnalysis.estimateSlowStartByRate(...)`（§8.3.4，下行侧慢启动检测，**新造
     判据、非移植**）；至少覆盖：恒定速率流（应返回 null）、前 1s 明显低速后转 4 倍速的合成流（应
     返回接近 1s 的 `slowStartUs`）、样本不足（应返回 null）三种夹具，且必须能证明该函数**真的会
     失败**（D-321/D-322 纪律：构造反例，不推理"原理上能失败"）。
2. 在 spec 层定稿 `ProfilePhase`/`Phase`（Go）新增字段 `window_ms` 与两个新 phase 类型常量
   `adaptive_download_window`/`adaptive_upload_window`（§8.3.5），随后同步修改
   `app/probe/.../engine/ProfileModels.kt` 与 `server/profiles.go` 两侧数据结构。
3. **创建 `profiles/s4_throughput.json`**（运行时镜像，与 `spec/profiles/server/s4_throughput.json`
   语义逐字节一致）——不做这一步，已接进 `verify_all` 的 `profiles-deep` 步骤会因"spec 有、runtime
   缺"直接 FAIL（`validate_profiles.py:104-107`）。
4. **扩展 `scripts/validate_profiles.py` 的 `PHASE_SPEC`**：追加 `adaptive_download_window`/
   `adaptive_upload_window` 两项，各自的 `{window_ms: int, bytes: num, chunk_kb: num}` 必填字段
   声明——这是扩展一道**已经存在、已经在跑**的通用守卫，不是仿先例新建一道。
5. `scripts/tests/test_validate_profiles.py` 同批追加覆盖新 phase 类型的正例/负例用例。
6. 确认服务端 bytes ceiling 是否需要额外校验——**已实测核实不需要**（§8.3.5）。

**依赖**：§8.7 8-1（插入位置）、8-2（三常量默认值方向性认可）需先有大脑/PO 初步认可（不要求最终
拍板，允许"先按建议值开工，批③真机数据出来后再correct"）。

**验收标准**：
- `RttDominanceGuard` 单测覆盖：s1/s3 历史数据判定符合 D-363 记录、`ABS_FLOOR_MS`/`MIN_BYTES_FLOOR`
  边界值各至少一条用例。
- `TransferWindowAnalysis` 单测覆盖上述三种夹具，且能证明可失败（不是纯推理）。
- `ProfileModels.kt`/`server/profiles.go` 新增字段后，**既有 `s1_chat.json`/`s2_coding_agent.json`/
  `s3_multimodal.json` 三个既有 profile 文件解析零回归**。
- **`python scripts/validate_profiles.py` 本地直接跑通过**（`profiles OK: N profile(s)`），且
  `scripts/verify_all.ps1` 的 `profiles-deep` 步骤为 PASS——这是本批唯一的、可直接复跑验证的硬性
  验收标准。
- 一份 `s4_throughput.json`（spec 侧 + runtime 侧两份内容相同）能被 `ProfileParser` 成功解析（不
  要求此时已能被 `ScenarioRunner` 执行，执行逻辑留到批③）。

### 批③ App 侧最小实现：新增场景执行路径 + KPI 计算 + wire 序列化（诊断期，不进打分）

**范围**：
1. `ScenarioRunner.kt` 新增两个 `when` 分支（`ProfilePhase.TYPE_ADAPTIVE_DOWNLOAD_WINDOW ->
   runAdaptiveDownloadWindow(...)` / `TYPE_ADAPTIVE_UPLOAD_WINDOW -> runAdaptiveUploadWindow(...)`），
   内部复用 `AnebClient.downloadDrain`/`uploadBurst`，到 `window_ms` 即取消。
2. **`TestEngine.kt` 新增显式执行块**（§8.6）：`runLoop@` 循环结束后新增一段代码——若
   `loaded.profiles` 含 `"s4_throughput"`，用与循环体内**完全相同**的执行/落库流水线跑一次
   （`repeatIndex=0`，`orderIndex` 延续场景循环的同一计数器），只 append 进 `scenarioReports`，
   不进 `kpiByScenario`、不进 `orderRecord`；缺 profile 时静默跳过。
3. `KpiCalculator.kt` 新增 U3/D3 计算逻辑（含双口径 §8.3.4、自检字段落地 §8.4.2），调用
   批②的 `RttDominanceGuard`/`TransferWindowAnalysis`。
4. `TestEngine.kt:809-822` 的 `kpiValuePairs()` 追加 `U3`/`U3_excl_slow_start`/`D3`/
   `D3_excl_slow_start` 四行。**`low_confidence` 判据不是"n<3"**（结构性 `sample_count` 恒为 1，
   §8.4.3），完全由 `RttDominanceGuard`/window_underrun/字节数下限的结果决定。
5. `ResultReporter.kt` 序列化新增字段（§8.4.2 全部 u3_*/d3_* 字段，含 `_rtt_ref_ms_pre`/
   `_rtt_ref_ms_post`/`_rtt_drift_ratio` 三组共 6 个字段）——**必须闭环验证 wire body 真的带上这些
   字段**，用批①同款的"序列化单测"模式。
6. `result-run.schema.json` 补齐 `scenario.kpi` 新增字段定义（§8.4.2 表格逐字段落地）。
7. **本批 KPI 恒不进任何 AQS facet**——`AqsInputMapper` 零改动，`run.aqs`/`aqs_v02`/`aqs_token`
   三个既有字段逐字节不受影响。
8. **具体消费方（不是"建议放入详情/调试视图"，是验收项）**：分析层/发布门至少一处消费
   `u3_rtt_dominance_ok`/`d3_rtt_dominance_ok`/`u3_rtt_drift_ratio`/`d3_rtt_drift_ratio`——最低要求
   是 `scripts/publish_check.py`（若存在同类脚本）新增一条检查项统计这些字段的分布并打印，避免它们
   重蹈"上线但没人读"的覆辙（D-276 教训）；批⑥的分析层接入可以承接这个要求，但批③必须至少有一条
   最小消费方（哪怕只是一行日志统计）先行落地，不能把"是否有人读"完全推迟到批⑥。

**依赖**：批①（D1 补齐模式可复用）+ 批②（判据函数 + phase 契约 + 对拍守卫就绪）。

**验收标准**：
- 真机（P40 Pro）至少完成 **n≥15** 次独立 run 采集（比照 M2 试点纪律），`campaign_id` 独立标记
  （如 `s4-throughput-diag-YYYYMMDD`），不并入任何既有 M2/M3 战役语料。
- 采集样本中 `u3_rtt_dominance_ok`/`d3_rtt_dominance_ok` 为 `true` 的比例、`window_underrun` 出现
  次数、以及 `u3_rtt_dominance_ratio`/`d3_rtt_dominance_ratio` **落在 [8,15] 边界区间的样本占比**
  均需在验收报告中如实报告。
- 采集样本中 `u3_rtt_drift_ratio`/`d3_rtt_drift_ratio` 的分布需如实报告（不要求都接近 1，只要求
  报告真实分布），为 §8.7 8-8 项的裁定提供数据。
- App 侧既有测试套件全绿（含批②新增单测），新增 `s4_throughput` 场景相关单测覆盖：window 正常到点
  截断、`window_underrun` 边界、RTT 探测失败（`rtt_ref_ms_pre=null`）时 `u3_rtt_dominance_ok` 恒为
  `false` 三种路径，并新增一条覆盖"`sample_count` 恒为 1 且不因此触发 low_confidence"的用例。
- 契约门确认新字段不影响既有必填校验，旧客户端产出的 wire body（无 `u3_*`/`d3_*` 字段）仍能通过
  校验。
- `python scripts/validate_profiles.py` 与 `verify_all` 的 `profiles-deep` 步骤持续 PASS。
- 发布门/收工清单同步登记新分析模块的检查项（吸取 D-305 教训）。

### 批④（门槛批次，非默认执行）打分接入 —— 视批③数据 + 大脑/PO 正式裁定

**开工门槛**：批③采集的 n≥15 真机数据证实 `s4_throughput` 的 `rtt_dominance_ok` 比例与
`rtt_dominance_ratio`/`rtt_drift_ratio` 分布**显著优于/不劣于**现有 S3 口径，**且**经大脑/PO 就
§8.7 8-5（是否要打分）正式裁定为"是"。若选择"切换映射"路径，**额外需要 §8.0 单流局限的方法学评审
通过**。若裁定为"只要展示型数字"，本批整体跳过，直接进入批⑥。

**范围**（若开工）：
1. 二选一（§8.4.4）：新增独立 `run.aqs_throughput` additive facet，或切换 `AqsInputMapper` 的
   `U1←S3`/`D1←S3` 映射为 `U1←S4`/`D1←S4`。
2. 若选后者：`AqsScorer.kt` 新增 `AQS_VERSION_TOKEN_V02`（旧常量不删），同步更新
   `AqsInputMapper.MAPPING_DESCRIPTION`。
3. 若涉及打分，需新增 `U3_ANCHORS`/`D3_ANCHORS` 分级锚点，需要画像/评分属主参与校准。
4. 跑一轮突变审计式回归（D-321 纪律：为新自检函数造反例证明它真能失败）。

**依赖**：批③完整验收通过 + 裁定。

**验收标准**：
- 若切换映射：所有消费 `u1_goodput_mbps`/`d1_goodput_mbps` 的分析层代码已按 `aqs_version` 或
  `profile_id` 分组，不会把 v0.1（S3 口径）与 v0.2（S4 口径）的数字悄悄混算（D-366 教训的直接对称
  检查）。
- 历史 `aqs-token-v0.1` 记录与新 `aqs-token-v0.2` 记录在同一份聚合报告中可被正确区分展示。
- 突变审计报告：至少一处新增守卫被证明"真能失败"。

### 批⑤（可选，独立优先级，不阻塞①-④）`basic_network`/`SpeedRunner` 可评分化

若产品侧希望 `basic_network` 本身也变成可评分/可持久化能力，需要单独立项：先给它补上目前完全没有
的持久化管线，再考虑独立 additive facet。这是比批①-④大得多的新增工作量，**应作为独立提案单独
评估，不与本次 T47 交付捆绑**。

### 批⑥ 分析层 + v2 UI 接入（依赖批③交付，独立于批④是否发生）

**范围**：
1. `scripts/campaign_common.py` 等分析层脚本接入新字段（按 D-329/D-334 教训，覆盖类判据要从产物
   导出、不能手写清单），承接批③已落地的最小消费方，扩展为完整的分析视图。
2. v2 UI 团队按《`docs/PROFILE2_THROUGHPUT_PROBE_INTERFACE.md`》接入新字段渲染。
3. 若批④未发生，v2 UI 只需处理"诊断展示"路径；若批④已发生，需额外处理 `aqs_version` 分支展示
   逻辑。

**依赖**：批③（字段已上线 wire 合同）。批⑥不依赖批④是否执行。

**验收标准**：
- v2 UI 渲染新字段时对 `low_confidence`/`rtt_dominance_ok=false`/`rtt_drift_ratio` 明显偏离 1 的
  场景有显式告警文案，不悄悄用 null 隐藏（复刻 D-366"RULED_OUT 三面可见"纪律）。
- 分析层新字段有对应发布门检查项（承接批③已落地的最小消费方，二次确认覆盖完整）。

### 批次汇总表

| 批次 | 范围概述 | 依赖 | 是否默认执行 |
|---|---|---|---|
| ① | D1 半成品补齐（不含并列口径）+ 具体消费方 + S3 诊断日志 | 无 | 是 |
| ② | 判据函数（含新造的下行慢启动检测）+ Profile 相位契约定稿（双端）+ 对拍守卫扩展 | §8.7 8-1/8-2 初步认可 | 是 |
| ③ | App 侧最小实现（诊断期，不进打分；TestEngine.kt 显式新增执行块；kpi_quality 结构性分叉） | ①② | 是 |
| ④ | 打分接入（切换映射或新 facet；若切映射需额外单流局限评审） | ③ 数据 + 裁定 | **否，门槛批次** |
| ⑤ | `basic_network` 可评分化 | 无（独立提案） | 否，独立立项 |
| ⑥ | 分析层 + v2 UI 接入 | ③ | 是（不等④） |

---

**v2 接口定义**（T47 交付物之三）单独成文：见
[`docs/PROFILE2_THROUGHPUT_PROBE_INTERFACE.md`](PROFILE2_THROUGHPUT_PROBE_INTERFACE.md)。

**产出过程说明**：本文经 13 子代理工作流产出（四维研究→三方案独立比稿→评审选主线+借鉴点→草案→
三透镜批判复核[架构契合/测量方法论/接口完整性]→终稿）。研究阶段四个并行代理中一个（探针实现现状
调查）因平台内部问题返回了无效占位内容；后续设计/评审/批判各阶段代理均独立复核了相关源码（`AnebClient.kt`/
`ScenarioRunner.kt`/`UploadAnalysis.kt`/`validate_profiles.py`/`server/profiles.go` 等），实测未见
该缺口影响本文结论，特此如实记录。
