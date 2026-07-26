<!-- 发射台准备蓝图(launchpad-prep)：2026-07-18 并行工作流产出。
     本文件为设计蓝图，产出时未改任何生产代码/未提交生产代码。
     用途：PO 决策落定 + P40 设备经协议解锁后，据此秒执行。口径红线见正文。 -->

# Spine-1 发射台准备蓝图:API-Agent 校准 profile 端到端解锁

> 日期:2026-07-18 · 子项目 P1b(测量引擎) + P3(契约) · 活跃开发树 `E:/C Project/ANEB`
> 本文只产出蓝图,**不改任何生产代码、不提交**。所有代码块均为示意(设计锚点),非对仓库文件的修改。
> 口径铁律贯穿全文:①Profile 即数据不是代码分支;②引擎先行 UI 后行;③指标客户端单侧定义。

---

## 0. 现状盘点(先把 seam 的真实状态讲清楚)

已落地(D-63,18 单测绿 + 跨端契约符合 2/2):

- `ApiProbe.run(config, observationSink?, log)` seam 存在;`ObservationSink(datasetSecret, subject, workloadKind, emit)` 定义完整。
- `TokenObservationExport.{fromProbeOutputs, buildObservation, subjectGroupId, tokenIntervalsMs, buildJsonl}` 纯 JVM 已验证。
- 契约 `aneb-token-observation-v1` / `aneb-calibration-dataset-v1` 由 Codex 定义,本仓引用不重定义。

盘点发现的三处"看着完成、其实是空挂"的关键缺口(本蓝图核心工作面):

| 缺口 | 证据 | 影响 |
|---|---|---|
| **ObservationSink 是悬挂 seam** | `MainActivity.kt:1000-1002` 调 `ApiProbe(applicationContext).run(ApiProbe.Config(...)) { line -> ... }`,**未传 sink**;全仓无任何调用方构造 sink。 | emit 永不触发,observation 无落地去向 → 采集功能实际未接通(任务 2 是真活)。 |
| **探针恒单 workload(text)** | `ApiProbe.requestBodyJson(provider, model)` 两参纯函数,只发 `PROMPT` 文本;`run` 里 `observationSink.workloadKind` 与请求体**互不约束**(可 body=text 却 sink 标 image,错标风险)。 | §4 门限要 text/document/image/video 各 ≥20+10 → 无多模态就永远凑不齐(任务 1)。 |
| **dataset-v1 manifest 不是我方产物** | Codex `calibration.py:prepare_token_dataset` 才生成 `aneb-calibration-dataset-v1`(计算 partitions/canonical_sha256/workload_counts);我方真实输入是 **`aneb-calibration-metadata-v1`**(authorization+scope)+ 主体不重叠的 train/holdout JSONL。 | 任务 3 须重定为"metadata 构造器 + split 划分器 + 本地 pre-flight",**不重定义 dataset-v1 契约**(口径红线)。 |

另一处正确性隐患:`TokenObservationExport.observationId(providerId, startedAtEpochMs)` = `apiprobe-<provider>-<ms>`,**不含 subject**;多 subject 同毫秒采集会产生同 id → Codex `_validate_partition_disjointness` 报 `duplicate_observation_id_within_partition` 拒整个分区。

口径红线复述(全程不可越):本 seam 口径 = `application_end_to_end_to_llm_api`(API 直调),**≠** 消费级 App 画像(`spec/portraits/*.yaml`)。消费 App 的 token/think 层因 mitm 明文不可得(D-61)恒 PENDING,**绝不跨层/跨产品/跨口径回填**。metadata 的 `scope.source_kind` 因此必须是 `controlled_api_observation`,**不是** `real_application_observation`。

测试基座事实(约束脚手架形态):`app/probe/build.gradle.kts:89` 只有 `testImplementation(libs.junit)`;测试类可用 kotlinx.serialization.json(`TokenObservationExportTest` 已用)。**无 MockWebServer、无 Robolectric** → 所有新锚定必须是纯函数 / 临时目录级,不碰 Android runtime。

---

## 1. 多 workload 探针矩阵(任务 1)

### 1.1 设计

引入纯数据载体 + workload 感知的请求体构造(保持 text 分支字节级零漂移,向后兼容现有对照列与 `ProviderPresetUrlTest`)。

```kotlin
// 示意:新纯类型(无 Android 依赖,JVM 单测直喂)
data class WorkloadPayload(
    val kind: TokenObservationExport.WorkloadKind,      // 单一事实源:决定请求体形态 + observation 标注
    val text: String = ApiProbe.PROMPT,                 // 固定短 prompt(烧钱护栏)
    val mediaBase64: String? = null,                    // 已 base64 的媒体(调用方保证已过 size 上限)
    val mediaMediaType: String? = null,                 // image/jpeg · application/pdf · video/mp4
    val maxTokens: Int = ApiProbe.MAX_TOKENS,           // 逐 workload 上限(硬顶见护栏)
)
```

`requestBodyJson` 重构为 workload 分支;旧两参签名保留为 `WorkloadPayload(TEXT)` 的委托(零行为变化):

```kotlin
// 示意:ApiProbe.Companion
fun requestBodyJson(provider: LlmProvider, model: String): String =            // 旧签名保留 → 委托
    requestBodyJson(provider, model, WorkloadPayload(TokenObservationExport.WorkloadKind.TEXT))

fun requestBodyJson(provider: LlmProvider, model: String, payload: WorkloadPayload): String {
    require(estimatedPayloadBytes(payload) <= MAX_PAYLOAD_BYTES) { "payload_over_cap" } // 烧钱护栏
    val capped = payload.maxTokens.coerceAtMost(MAX_TOKENS_HARD_CEILING)                // 逐 workload 硬顶
    return when (provider) {
        LlmProvider.ANTHROPIC -> anthropicBody(model, payload, capped)   // content[] 块:text/image/document(/video 需能力确认)
        LlmProvider.OPENAI_COMPAT -> openAiBody(model, payload, capped)  // messages[0].content[]:text/image_url(...)
    }
}
```

多模态请求体形态(客户端单侧定义,按各家 wire 契约):

| workload | Anthropic content 块 | OpenAI 兼容 content 项 | 备注 |
|---|---|---|---|
| text | `{"type":"text","text":PROMPT}` | `{"type":"text","text":PROMPT}` | 现状,零漂移 |
| image | `{"type":"image","source":{"type":"base64","media_type":..,"data":..}}` | `{"type":"image_url","image_url":{"url":"data:<mt>;base64,.."}}` | 多数国产 OpenAI 兼容家支持 image_url |
| document | `{"type":"document","source":{"type":"base64","media_type":"application/pdf","data":..}}` | 家差异大(常走独立 file API 非 chat) | **需 #6 逐家确认能力** |
| video | Messages API 原生视频块支持随版本而变 | 绝大多数家不支持 | **provider 能力阻 + #6,矩阵格标 PENDING** |

### 1.2 烧钱护栏(设计文档 §9)

- `MAX_PAYLOAD_BYTES`(新 const,建议初值 512KB,#6 由 PO 收敛):`requestBodyJson` 构造前 `require` 拒超限,防媒体 payload 失控烧钱。
- `MAX_TOKENS_HARD_CEILING`(建议 256):任何 workload 的 `maxTokens` 经 `coerceAtMost` 钉死,即使调用方传大值也不越顶。
- 承接现状:`stream:true`、`retryOnConnectionFailure=false`、单次手动触发不变。

### 1.3 run() 单一事实源修复(正确性)

`run` 增加 `workload: WorkloadPayload = WorkloadPayload(TEXT)` 形参,**同时**用于请求体构造与 observation 标注,消除现有 `body=text 却 sink.workloadKind=image` 的错标面:

```kotlin
// 示意:ApiProbe.run 内
val bodyJson = requestBodyJson(config.provider, config.model, workload)   // ← 同源
...
workloadKind = workload.kind,                                            // ← 同源(不再读 sink.workloadKind)
```

`ObservationSink` 的 `workloadKind` 字段随之下沉/删除(或保留但由 run 断言与 workload.kind 一致)。

### 1.4 改动清单与状态

| 文件:函数 | 改动 | 状态 | 测试 |
|---|---|---|---|
| `apiprobe/ApiProbe.kt`:新 `WorkloadPayload` + `requestBodyJson(provider,model,payload)` + `anthropicBody/openAiBody/estimatedPayloadBytes` | workload 分支 + 委托旧签名 | **现在可验证**(纯函数) | 新 `RequestBodyMatrixTest`(见 §4) |
| `apiprobe/ApiProbe.kt`:`run` 增 `workload` 参 + 同源标注 | 单一事实源 | **现在可验证**(编译 + 经 requestBodyJson 锚定) | 同上 |
| `apiprobe/ApiProbe.kt`:`MAX_PAYLOAD_BYTES`/`MAX_TOKENS_HARD_CEILING` const | 护栏 | **现在可验证** | 上限拒绝用例 |
| 各家 workload 媒体范围/能力(document/video 支持面) | 数据,不入代码分支 | **被 PO 阻(#6)** + provider 能力确认 | — |
| 真机跑多模态 | — | **被设备阻(P40)** | — |

---

## 2. observation JSONL sink 落地(任务 2)

### 2.1 设计:纯写入类 + Android 薄适配

把落盘逻辑抽成**不依赖 Android Context 的纯类**(取 `java.io.File` 目录),这样 append/命名/轮换/原子性都能在临时目录 JVM 单测:

```kotlin
// 示意:apiprobe/ObservationJsonlWriter.kt(纯 JVM)
class ObservationJsonlWriter(
    private val dir: File,
    private val maxFileBytes: Long = 8L * 1024 * 1024,     // size 轮换阈
    private val clock: () -> Long = System::currentTimeMillis,
) {
    fun fileNameFor(epochMs: Long, providerId: String, seq: Int = 0): String =
        "aneb_token_obs_${yyyymmdd(epochMs)}_${providerId}" + (if (seq == 0) "" else "_%02d".format(seq)) + ".jsonl"

    @Synchronized fun append(observationJson: String, providerId: String) {
        val f = currentFile(providerId)                    // 按日 + size 选/滚文件
        dir.mkdirs()
        FileOutputStream(f, /*append=*/true).use { it.write((observationJson + "\n").toByteArray(Charsets.UTF_8)) }
    }
    // currentFile:同日同 provider 复用;超 maxFileBytes 递增 seq;跨日新文件
}
```

Android 薄适配(唯一碰 Context 处,不入单测):在调用方按采集配置构造 sink,`emit` 转调 writer:

```kotlin
// 示意:MainActivity.onRun(采集开关开时)
val writer = ObservationJsonlWriter(File(applicationContext.filesDir, "token_obs"))
val sink = ApiProbe.ObservationSink(
    datasetSecret = collectionConfig.datasetSecret,       // 来自 PO #3 托管,内存态,绝不入库/日志
    subject = collectionConfig.subjectAlias,              // PO #4
    emit = { line -> withContext(Dispatchers.IO) { writer.append(line, provider.id) } },
)
ApiProbe(applicationContext).run(ApiProbe.Config(provider, baseUrl, model, key), sink, workload) { line -> addLog(line) }
```

关键约束:

- **默认关**:采集开关(collectionConfig 为 null)时不传 sink → 对照列探针零行为变化(承接 D-63 语义)。
- **隐私**:writer 只写 observation JSON(已白名单 8+1 字段);datasetSecret/subject 只在内存派生 subject_group_id,绝不进文件/日志。
- 文件命名 `aneb_token_obs_<yyyymmdd>_<provider>[_NN].jsonl`;轮换按日 + `maxFileBytes`;交付 Codex 时用现有 `Exporter.exportToDownloads`(`MainActivity.kt:1023` 同款)拷到 Downloads 供 adb pull / 手工交接。
- **不进 /results 服务端上报**(口径:observation 是行为模型输入,非 ANEB 网络评分;走离线文件交接,非 P2 服务器)。

### 2.2 observationId 唯一性加固(承 §0 隐患)

```kotlin
// 示意:TokenObservationExport.observationId 增 subject 短哈希/序号,保分区内唯一
fun observationId(providerId: String, startedAtEpochMs: Long, disambiguator: String): String =
    "apiprobe-$providerId-$startedAtEpochMs-$disambiguator"   // disambiguator = subjectGroupId 后 8 hex 或单调 seq
```

`run` 传入 `subjectGroupId` 派生的短后缀,保证多 subject/同 ms 不碰撞(仍满足合同 `^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$`)。

### 2.3 改动清单与状态

| 文件:函数 | 改动 | 状态 | 测试 |
|---|---|---|---|
| 新 `apiprobe/ObservationJsonlWriter.kt` | append/命名/按日+size 轮换/原子追加 | **现在可验证**(临时目录) | 新 `ObservationJsonlWriterTest`(§4) |
| `TokenObservationExport.observationId` 增 disambiguator | 唯一性加固 | **现在可验证** | 唯一性/格式用例 |
| `apiprobe/ApiProbe.kt`:`run` 用加固 observationId | 接线 | **现在可验证** | 经 export 锚定 |
| `ui/MainActivity.kt:1000` 接 sink + 采集开关 UI | 薄适配(碰 Context) | **被 PO 阻(#3/#4 提供 secret/subject)** + 编译现在可过 | 手测(设备) |
| 真机 emit + export + adb pull | — | **被设备阻(P40)** | — |

---

## 3. metadata 生成器 + split 划分器 + 本地 pre-flight(任务 3,重定范围)

**重要口径澄清**:`aneb-calibration-dataset-v1` manifest 由 Codex `prepare-token-dataset` 生成(它算 partitions/canonical_sha256/workload_counts/split)。我方**不重定义、不生成** dataset-v1;我方产出喂给 Codex 的三样输入:

1. `aneb-calibration-metadata-v1` 文件(authorization + scope = PO 决策字段落点);
2. 主体不重叠的 `training.jsonl` / `holdout.jsonl`;
3. (可选,省一趟 Codex 往返)本地 pre-flight:数量/schema/disjoint 预检。

AUTHORIZED_TOKEN_CAPTURE_SPEC 把 authorization/scope 描述为落在 manifest 层,略有含混;**以代码为准**:这些 PO 字段由我方在 metadata 里 author,Codex prepare 原样拷入 dataset manifest。

### 3.1 metadata 契约字段(镜像 `calibration.py:validate_calibration_metadata`)

| 字段 | 约束(代码实测) | PO 决策项 | 本 seam 建议值 |
|---|---|---|---|
| `metadata_contract_version` | const `aneb-calibration-metadata-v1` | — | 固定 |
| `prepared_at` | RFC3339 UTC `^\d{4}-..T..:..:..Z$` | — | 生成时刻 |
| `authorization.status` | const `authorized` | **#1/#2** | 仅 PO 签字后置 authorized |
| `authorization.basis` | ∈ 4 值 | **#1** | `first_party_measurement`(自有账号) |
| `authorization.approved_by` | `^[A-Za-z0-9][._-]{2,127}$` | **#1** | PO 审批角色 id |
| `authorization.approved_at` | RFC3339 UTC 且 ≤ prepared_at | **#1** | PO 拍板时刻 |
| `authorization.allowed_purposes` | 非空唯一,必含 `behavior_model_calibration` | **#2** | `["behavior_model_calibration"]` |
| `authorization.content_policy` | const `derived_statistics_only` | — | 固定 |
| `authorization.content_retained` | const `false` | — | 固定 |
| `authorization.expires_at`(可选) | RFC3339 且 ≥ prepared_at | **#8** | 保留期终点 |
| `authorization.reference_id`(可选) | minLength 1 | **#1** | 真实审批引用号 |
| `scope.source_kind` | ∈ 3 值 | 口径红线 | **`controlled_api_observation`**(非 real_application_observation) |
| `scope.provider_labels` | 非空唯一字符串 | **#5** | 如 `["anthropic-direct","openai-compat-cohort"]` |
| `scope.geography_labels` | 非空唯一 | **#5** | 隐私安全地域桶 |
| `scope.device_classes` | 非空唯一 | **#5** | 设备类别桶 |
| `scope.observation_window_start/end` | RFC3339,start≤end≤prepared_at | **#5** | 采集时间窗 |
| `scope.collection_method` | `^[A-Za-z0-9][._-]{2,127}$` | — | `aneb-apiprobe-token-v1` |

### 3.2 纯函数设计(Kotlin,与 App 同工具链,JVM 可测)

```kotlin
// 示意:apiprobe/CalibrationMetadata.kt(纯 JVM)—— 产出 metadata 实例并本地自校(不重定义 schema)
object CalibrationMetadata {
    const val CONTRACT = "aneb-calibration-metadata-v1"
    data class Authorization(val basis: String, val approvedBy: String, val approvedAt: String,
                             val purposes: List<String>, val expiresAt: String? = null, val referenceId: String? = null)
    data class Scope(val providerLabels: List<String>, val geographyLabels: List<String>,
                     val deviceClasses: List<String>, val windowStart: String, val windowEnd: String,
                     val collectionMethod: String = "aneb-apiprobe-token-v1",
                     val sourceKind: String = "controlled_api_observation")

    /** @return metadata JSON;不满足契约硬约束(镜像 Codex)时抛 IllegalArgumentException(编程/配置错,非数据缺失)。 */
    fun build(preparedAt: String, auth: Authorization, scope: Scope): String { /* require 全约束后 buildJsonObject */ }
}
```

```kotlin
// 示意:apiprobe/SubjectDisjointSplit.kt(纯 JVM)—— 整 subject 归属,保 Codex disjointness + §4 计数
object SubjectDisjointSplit {
    data class Result(val training: List<String>, val holdout: List<String>, val shortfalls: List<String>)
    /**
     * 输入:已解析 observation(至少含 subject_group_id + workload_kind + observation_id)。
     * 规则:同一 subject 整体只入 train 或 holdout(subject_group_disjoint);
     *       逐 workload 保证 train ≥20 / holdout ≥10;凑不齐则记 shortfall(不硬凑、不补哨兵,R-10 精神)。
     */
    fun assign(observations: List<ParsedObs>, minTrain: Int = 20, minHoldout: Int = 10): Result { /* 贪心整主体分配 */ }
}
```

### 3.3 本地 pre-flight(必要非充分,明确边界)

我方能在无 fitted model、无设备下预检的只有**数量 / schema / disjoint**;§4 的 P50/P95 相对误差、PAUSE 占比误差、Markov 行 TVD **须 Codex calibrate 对 template 拟合后才算**——本地做不了,不假装能做。

- 载体二选一:(a) Kotlin `TokenDatasetPreflight`(纯函数,复用上面两器);(b) Python `scripts/preflight_token_dataset.py` 复用已有 jsonschema 路径(与 D-63 的 2/2 符合性检查同基座)。建议主交付 Kotlin 纯函数(任务明确要 JVM 脚手架),Python 版作 schema 冗余校验补充。
- pre-flight 检查项:每行过 `aneb-token-observation-v1.schema.json`;train/holdout observation_id 分区内唯一 + 两分区零交集;subject_group_id 两分区零交集;逐 workload train≥20/holdout≥10;metadata 过 §3.1 全约束。
- **不入 `verify_all.ps1` 仓库门禁**:数据在 gitignored `datasets/`、含 PO 真实采集,pre-flight 是操作员手跑工具,非 CI 红线。

### 3.4 改动清单与状态

| 文件:函数 | 改动 | 状态 | 测试 |
|---|---|---|---|
| 新 `apiprobe/CalibrationMetadata.kt`:`build` | 产 metadata + 镜像校验 | **现在可验证** | 新 `CalibrationMetadataTest`(§4) |
| 新 `apiprobe/SubjectDisjointSplit.kt`:`assign` | 整主体划分 + 计数保证 | **现在可验证** | 新 `SubjectDisjointSplitTest`(§4) |
| 新 `apiprobe/TokenDatasetPreflight.kt` 或 `scripts/preflight_token_dataset.py` | 数量/schema/disjoint 预检 | **现在可验证**(合成 fixtures) | Preflight 用例 |
| authorization/scope 实值(basis/approver/窗/桶/保留期) | 数据 | **被 PO 阻(#1/#2/#5/#8)** | — |
| 真实 observation 灌入 split/preflight | — | **被设备阻(P40 采集)** | — |
| prepare/calibrate/promote 执行 | Codex 工具 | **被 Codex 阻** | — |

---

## 4. 测试脚手架(无设备 JVM 锚定)

沿 `TokenObservationExportTest`(纯 JUnit4 + kotlinx.serialization.json)风格。测什么 + 怎么在无设备下 JVM 锚定:

### 4.1 `RequestBodyMatrixTest`(任务 1)

- text 分支**字节级零漂移**:`requestBodyJson(p, m)` 与 `requestBodyJson(p, m, WorkloadPayload(TEXT))` 完全相等,且等于现有硬编码(锁 `max_tokens`/`PROMPT`,防对照列被动改)。
- image 分支:Anthropic content 含 `"type":"image"` + `base64` + media_type;OpenAI 含 `data:<mt>;base64,`;断言无 PROMPT 外自由文本泄漏。
- 护栏:超 `MAX_PAYLOAD_BYTES` 的 payload → 抛 `IllegalArgumentException`;`maxTokens=9999` → 实际体内 ≤ `MAX_TOKENS_HARD_CEILING`。
- 用小合成媒体 fixture(如 8 字节假 base64),不需真实图片/设备。

### 4.2 `ObservationJsonlWriterTest`(任务 2)

- 用 JUnit `TemporaryFolder`(或 `File.createTempFile` 目录)注入 `dir`,固定 `clock`。
- append 两条 → 文件 2 行、每行合法 JSON、末尾换行;同日同 provider 复用同文件;跨日(改 clock)新文件;超 `maxFileBytes` 递增 `_NN`。
- 并发 append(多线程)不串行错行(`@Synchronized` 锚定)。
- 断言写入内容**不含** datasetSecret/subject 明文。

### 4.3 `CalibrationMetadataTest` / `SubjectDisjointSplitTest`(任务 3)

- metadata:合法输入产出过 `aneb-calibration-metadata-v1` 全约束;`status` 非 authorized、basis 越界、approved_at>prepared_at、purposes 缺 `behavior_model_calibration`、source_kind=`real_application_observation`(口径越界)→ 全部抛。
- split:构造 3 subject × 2 workload 合成集 → 断言同 subject 不跨分区、逐 workload train≥20/holdout≥10;不足时 `shortfalls` 精确列出缺口(不硬凑)。
- observationId 加固:同 provider 同 ms 不同 subject → id 不等且仍匹配合同正则。

### 4.4 pre-flight 端到端(合成)

- 用 `examples/token_observation.example.jsonl` 形态的合成多行,构造"够/不够"两组 → pre-flight 分别 PASS / 精确 FAIL 原因,验证与 Codex `_validate_partition_disjointness`、§4 计数一致。

全部脚手架**零设备、零网络、零 PO 数据**即可跑绿(`gradlew :probe:testDebugUnitTest`)。

---

## 5. 解锁后 runbook(设备 + PO 解锁后的确切步骤)

前置门(缺一不可):

1. **设备**:~~P40 现 `异常锁定`。Claude **不得手改** `SHARED_TEST_STATUS.md`(D-63:异常锁定态下 Claude 非执行者,无合法转换,手改破坏 fail-closed 状态机)。须 Codex 先清 E-01 防火墙指纹漂移/回滚(exit=97),独立复核把 `待交接→空闲`,之后 Claude 才用 `update_shared_test_status.py` 脚本 `claim`(`空闲→进行中`)。~~
   **⛔ 已于 2026-07-19 被 PO 废止**——该状态机不再是设备使用的授权依据,上述"等 Codex 复核降为空闲"**永远不会发生**,照做会把本项无限期挂起。**现行**(仓根 `CLAUDE.md`):开测前直接查设备实况(在线 + 华为桌面前台 + 只读确认无冲突 ANEB/业务 App/VPN/抓包进程与残留隧道),干净即可直接开测;测后全部停掉、撤临时规则与 `stayon`、回桌面并立即复验。**E-01 侧的防火墙指纹漂移仍是真实前置**,走其自身的受保护预检与回滚流程。
2. **PO**:8 项决策全部拍板(尤其 #3 datasetSecret 托管、#4 subject、#5 范围、#6 workload 媒体/上限)。

采集与交付步骤(每步给命令):

```powershell
# 1) 设备接手(仅 Codex 复核 待交接→空闲 后)
python scripts\update_shared_test_status.py claim --resource P40 --expected-status-sha256 <sha>

# 2) 配置采集(内存态;datasetSecret 来自 PO #3 托管,绝不落盘/入仓/入日志)
#    在 App 采集开关:填 subject 别名(#4)、选 provider、选 workload(text/image/document/video)

# 3) 逐 workload 采够量(§4:每 workload train≥20 + holdout≥10,且 holdout 主体与 train 不重叠)
#    ⇒ 每 workload 需 ≥2 组主体(train 专用 + holdout 专用),建议每侧 ≥3 主体防主体级过拟。
#    对每个 (workload × subject) 反复单次手动触发探针,只保留"干净成功"(APIPROBE_OBSERVATION generated=true)。
#    计数目标(4 workload):train ≥80 + holdout ≥40 条干净 observation。

# 4) 取出 JSONL(App 内 Export 到 Downloads 或 adb pull filesDir/token_obs)
adb pull /data/data/<pkg>/files/token_obs .\datasets\raw\

# 5) 本地 pre-flight(§3.3):数量/schema/disjoint 预检,凑不齐回步骤 3 补采
#    (Kotlin TokenDatasetPreflight 或 python scripts\preflight_token_dataset.py)

# 6) 生成 metadata(#1/#2/#5/#8 值)+ 主体不重叠 split
#    CalibrationMetadata.build(...) → metadata.json ;SubjectDisjointSplit.assign(...) → training.jsonl / holdout.jsonl
```

交 Codex 三段式(Codex 工具执行,不可跳步):

```bash
# 7) prepare:打包授权 + 主体不重叠分区,冻结摘要 → dataset_manifest.json
aneb-behavior prepare-token-dataset \
  --training training.jsonl --holdout holdout.jsonl --metadata metadata.json \
  --dataset-id aneb-apiagent-2026q3 --dataset-version 0.1.0 --out datasets/prepared/

# 8) calibrate:只用 training 拟合,只对 frozen holdout 验证(§4 门限)
#    exit 0 = holdout PASS(P50/P95 相对误差≤20% + PAUSE 占比误差≤0.05 + Markov 行 TVD≤0.15)
#    exit 1 = FAIL → 回步骤 3 补采/改采(不硬 promote)
aneb-behavior calibrate-token \
  --template tools/aneb-ai-behavior-model/models/token_multimodal_hypothesis_v0.1.json \
  --dataset-manifest datasets/prepared/dataset_manifest.json \
  --candidate-version 0.1.0 --out build/token_candidate/

# 9) promote:复算报告 + 核对候选/数据摘要一致后,才产 validated 模型(首个!)
aneb-behavior promote-token \
  --model build/token_candidate/calibrated_model.json \
  --validation build/token_candidate/validation.json \
  --dataset-manifest datasets/prepared/dataset_manifest.json \
  --out build/token_validated/model.json
```

自查是否满足 §4 门限:

- 数量:`dataset_manifest.json` 的 `partitions.training.workload_counts` / `holdout.workload_counts` 每个 workload ≥20 / ≥10。
- 误差:看 `build/token_candidate/validation.json`(`token-holdout-validation-v1`)逐 workload `status`;任一 FAIL 不 promote。
- 一致:promote 从原 manifest/holdout **重新复算**,不信报告里 `status=pass` 单字段(D-63/pipeline §5)。

收尾与握手(D-61/CLAUDE.md):

```powershell
adb shell am force-stop <pkg>                       # 设备卫生
# 从设备/配置清除 datasetSecret(不入库/不入仓);复核活动网络无 VPN 残留
python scripts\update_shared_test_status.py handoff  # 进行中 → 待交接
# 之后由 Codex 独立复核 待交接 → 空闲(Claude 不自转此步)
```

---

## 6. 一页速览:改动全景与阻塞归属

| # | 工作项 | 现在可验证 | 被设备阻 | 被 PO 阻 | 被 Codex 阻 |
|---|---|:--:|:--:|:--:|:--:|
| 1 | 多 workload requestBodyJson + 护栏 + run 单一事实源 | ✅纯函数/编译 | 真机跑 | #6 媒体范围 | — |
| 2 | ObservationJsonlWriter + observationId 加固 + sink 接线 | ✅临时目录/编译 | emit/export/pull | #3/#4 secret+subject | — |
| 3 | CalibrationMetadata + SubjectDisjointSplit + pre-flight | ✅合成 fixtures | 真实数据灌入 | #1/#2/#5/#8 | prepare/calibrate/promote 执行 |
| 4 | JVM 测试脚手架(§4 全部) | ✅零设备零网络 | — | — | — |
| 5 | 首个 validated 模型 | — | 全链依赖采集 | 全 8 项 | 三段式跑通 §4 门限 |

红线守卫(全程):observation 白名单 8+1、`additionalProperties=false`、无 prompt/content/account/key 出口;subject_group_id 恒 `hmac-sha256:<64hex>`、密钥不入库/导出/仓/日志;口径恒 `application_end_to_end_to_llm_api` / `controlled_api_observation`,绝不回填消费 App(D-61 恒 PENDING)。
