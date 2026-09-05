# AQS 评分口径版本冻结清单（单一登记表）

> 属主：v4（spec lane，T82/SPEC-4 · 4.1）。**用途：任何人拿本表能回答「这两个分数能不能比」。**
> **本表是「人读索引」，不是新事实源**——version_id / 权重 / 锚点的事实源仍是
> `spec/scoring/weights.yaml`+`anchors.yaml`（逐字导出自 `AqsScorer.kt`，`SpecScoringParityTest` 对拍）；
> 本表引用它们，由 `spec/scoring/check_versions.py` 守卫防止两者漂移（见 §3）。
> 建 `spec/scoring/VERSIONS.md` 而非塞进 `spec/README.md` 新节：单一职责、守卫可直接指向、与 weights.yaml 同目录作其人读面。

## 0. 为什么需要这张表（一个当场的实证）

SPEC-4 任务书列举现役口径时写「aqs-v0.1 / v0.2 / aqs-token-v0.1 / aqs-voice-v0.1 / v0.2 / aqs-voice-sim-v0.1 **六支**」——
**漏了 `aqs-voice-sim-v0.2`**。实际是 **7 个 version_id / 8 张权重表**（`aqs-token-v0.1` 一个版本戳挂两张表）。
连派单人都数不全，正是「口径以新版本并列吸收变化、却从无一页清单」的代价。本表把这 7 支一次钉齐，并配守卫防再漏。

## 1. 七支现役口径 · 五列总表

> 「可比范围」列是本表的核心：**当且仅当 version_id 完全相同，两个分数才可比**（规则见 §2）。

| version_id | 权重表 · 定义位置 | 适用入口 | 可比范围 | 现役状态 | 引用先例 |
|---|---|---|---|---|---|
| `aqs-v0.1` | `WEIGHTS`（weights.yaml:9-19 / AqsScorer.kt:77，T1/T3 .20、T2/U1 .15、U2/N1/N2 .10） | 每个主 run 无条件出分（TestEngine.kt:625 `score()`）；含 T4 一票否决 | 仅 `aqs-v0.1` 之间 | **现行**（主赛道基线） | MVP，agent-qoe-kpi KPI 文档 §5.4 |
| `aqs-v0.2` | `WEIGHTS_V02`（weights.yaml:20-33，=WEIGHTS×0.8 + C1 .10 + C2 .10 派生） | continuity 数据门放行才**并列**出分（AqsV02Gate，不替换 v0.1） | 仅 `aqs-v0.2` 之间；**与 v0.1 不可比**（加 C 组改尺度） | **已实现·冻结**（D-505；73/73 实测语料零出分，解冻条件=E-03 真实 API key 语料） | D-26 / D-505 |
| `aqs-token-v0.1` | `WEIGHTS_TOKEN_MM`（weights.yaml:34-45，含 D1）+ `WEIGHTS_TOKEN_TXT`（:46-56，剔 U1/D1，INV-4 设计缺省） | Token 模式每 run additive（TestEngine.kt:663 硬编码 `WEIGHTS_TOKEN_MM`）；含 S1 会话完成率软/硬否决 | **见 §2 token 特例**（MM 与 TXT 共版本戳但不同表，不建议直接横比） | **现行** | PROFILE_FRAMEWORK §2.5 / D-29 / D-33 |
| `aqs-voice-v0.1` | `WEIGHTS_VOICE`（weights.yaml:57-66，M1 .30/M2 .20/M3 .15/N1 .15/N2 .20） | 语音**非 sim / paced-proxy** 口径（D-31）；M1 为口到耳预算 DERIVED（含从未实测的 `CODEC_JB_BUDGET_MS=60`，D-377，非真实 MOS） | 仅 `aqs-voice-v0.1` 之间 | **历史兼容**（生产语音非 sim 分支已改调 v0.2，本戳留作历史语料版本兼容） | D-31 |
| `aqs-voice-v0.2` | `WEIGHTS_VOICE_V02`（weights.yaml:67-87，=v0.1 + M7 .10，从 M2/M3 匀出） | VoiceTestScreen 非 SIM 分支（传 m7MaxFrameGapMs）；M7 测了但 null → KPI_MISSING:M7，绝不降级 v0.1 | 仅 `aqs-voice-v0.2` 之间；**与 v0.1 不可比**（M7 改尺度，D-404 立界） | **现行**（语音非 sim） | D-404 / D-390 §5.6 / VOICE_STALL_KPI_PROPOSAL |
| `aqs-voice-sim-v0.1` | `WEIGHTS_VOICE_SIM`（weights.yaml:88-101，M1–M6 + N1/N2） | 语音 **server-sim 实测**口径（D-38，走 Codex `/realtime-sim`）；**79.8 分的产地** | 仅 `aqs-voice-sim-v0.1` 之间；**与 voice-v0.1 不可比**（测量法+KPI 集不同，见 §2 sim 特例） | **历史**（生产 sim 分支已落 v0.2；79.8 系此戳） | D-38 / D-377 |
| `aqs-voice-sim-v0.2` | `WEIGHTS_VOICE_SIM_V02`（weights.yaml:102-119，=sim + M7 .05） | VoiceTestScreen SIM 分支（`caliber==SIM_CALIBER`，传 m7） | 仅 `aqs-voice-sim-v0.2` 之间；**与 sim-v0.1 不可比**（M7 界，D-404） | **现行**（语音 sim） | D-404 |

## 2. 可比性规则（本表的判词依据）

**铁律：当且仅当两个分数的 `version_id` 完全相同，它们才可比。** 跨 version_id 一律不可比——
不同权重表 = 不同 KPI 权重 = 不同尺度，把它们放一张榜是拿两把不同刻度的尺量长短。四条推论与两个特例：

1. **v0.1 vs v0.2（任何族）不可比**——新增 KPI（网络族的 C 组、语音族的 M7）重分配了权重、改变了尺度。
   语音族的 M7 界由 D-404 明确立下（M7 引入不原地升版，并列新建 v0.2 两表）。
2. **sim vs 非 sim（语音）不可比**——不是「仿真 vs 真实」，两者都是真实测量：`aqs-voice-v0.1` 是
   paced-proxy 观测口径（M1 口到耳预算 DERIVED），`aqs-voice-sim-v0.1` 是 `/realtime-sim` server-sim
   口径（M 组变实测 sched_us 剥离，且**多 M4 TTS-TTFB / M5 轮次切换 / M6 打断停帧**三项）。测量方法与 KPI 集都不同。
3. **token 特例**：`aqs-token-v0.1` 下 `WEIGHTS_TOKEN_MM`（多模态，含 D1）与 `WEIGHTS_TOKEN_TXT`（纯文本，
   剔 U1/D1）**共一个 version_id 但是两张表**——同一评分体系对「多模态/纯文本」两种内容的两个变体。
   同版本戳意味着同评分体系，但**两表权重构成不同，分数不建议直接横比**（横比时须点明是 MM 还是 TXT）。
   这是本表唯一「同 version_id、可比性仍需限定」的结构，特此显式标出。
4. **basic_network 特例**：网络基本性能线走 `ThresholdGrader` 四档，**根本不是 AQS**——不在本表，
   与任何 `aqs-*` 分数不可比（交付包 T61 供料 §1「三模式不共权重表，跨模式分数不可互比」）。此处点名防误比。
5. **79.8 锚点**：属 `aqs-voice-sim-v0.1`，M7 引入前口径，**不与 v0.2 后的分数比较**（D-404；既有守卫
   `scripts/tests/test_voice_score_caliber.py` 钉死：任何引用 79.8 的 md 同文件须点口径 id）。

## 3. 守卫：新增评分口径必须先在本表登记

**`spec/scoring/check_versions.py`（本单新建，照 `spec/portraits/check_redline.py` 的 spec-lane 自守卫先例）**，
形态照 D-248 常量归档 + `AqsScorerVoiceTest.kt:182`「语音版本→权重表映射须覆盖全部版本」推广到**全口径**：

- **判据（双向咬合，照 R1/R19c 纪律）**：从 `weights.yaml` 正则枚举全部 `version_id`（**单一事实源**，
  已由 `SpecScoringParityTest` 与 `AqsScorer.kt` 对拍），与本表 §1 登记的 version_id 集合**必须相等**：
  - `weights.yaml 有、本表无` → 红（新增口径没登记——正是本单要防的「又漏一个」）；
  - `本表有、weights.yaml 无` → 红（登记了不存在的版本，或版本号写错）。
- **为什么判据落在 weights.yaml 而非 Kotlin 常量**：weights.yaml 是机器可读且已对拍的镜像，
  Python 守卫无需跨语言 grep；第三处字面量=第三个会漂的地方（§2.14），故本表不复制权重数值，只登记 version_id + 指针。
- **依赖 spec/README §3 add-only 版本纪律**：weights.yaml 里已发布权重表「只增不改不删」，
  故本表登记的历史版本（v0.1 族）不会因表被删而突然「查无此戳」——与既有语音口径守卫同一依赖。

## 4. 边界与诚实缺口

- 本表**不新增任何事实**：删掉本表，评分逻辑与 weights.yaml 不受影响；本表的价值是「一处回答可比性」，
  由守卫保证它与事实源同步。
- 本表**只登记 aqs-* 评分版本**，不含 `basic_network`（非 AQS，见 §2.4）与 KPI 门限锚点（那是 anchors.yaml 的域）。
- 「适用入口」列的行号是采集时（2026-08-29）的实况锚点，会随代码演进漂移——它是**导航指针不是契约**，
  契约是 version_id 本身；行号若失效以 grep `AQS_VERSION` / weights.yaml `version_id` 为准。
