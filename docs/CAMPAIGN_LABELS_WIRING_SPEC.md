# 战役标签生产接线规格 v1.0（spec-first 交接件）

> **给谁**：spec 属主 / P1 客户端 lane（app/ + spec/ 写权）。
> **本文件由分析层 lane 撰写**（只读 app//spec/ 后成文，未改动其任何文件）——按铁律
> 「先改 spec、后动代码」，这是实施前应先审定的规格。
> **前置**：口径与降级语义见 [`CAMPAIGN_LABELS_CONVENTION.md`](CAMPAIGN_LABELS_CONVENTION.md)；
> 本文件只讲**怎么落地**。
> **为什么现在做**：分析层（`scripts/`，16+ 工具、228 golden、M2 规模彩排通过）已全部就绪，
> 唯一未接线的就是让真实 run 自带标签。不接线则每批外场语料都要人工离线补注，
> 既费时又是 M2 当天最大的人为出错面。

---

## 1. 变更总览（三处，全部加性）

| # | 位置 | 变更 | 破坏性 |
|---|---|---|---|
| S1 | `spec/schemas/result-run.schema.json` | `run.properties` 加**可选** `campaign` 定义 | 无（不进 `required`） |
| S2 | `app/probe/.../data/Entities.kt` + `AnebDatabase.kt` | `TestRun` 加 6 个**可空**列 + Room 15→16 加性迁移 | 无（可空无默认，历史行 NULL） |
| S3 | `app/probe/.../engine/ResultReporter.kt` | `build()` 条件写入 `run.campaign` | 无（null 时整块不写） |
| S4 | P1a 发起页 | 采集标签（详见 §5） | 新增可选 UI |

**兼容性论证**：`result-run.schema.json` 全层 `additionalProperties: true`；服务端
`validateResultContract` 只校验必填、不拒新增字段；分析层 `campaign_common.campaign_labels`
读到即用、读不到降级为 `unlabeled`/`unknown`（已有 golden 守卫）。故**老客户端 × 新服务端**、
**新客户端 × 老分析脚本**两个方向都安全。

---

## 2. S1：schema 加性定义（可直接粘贴）

置于 `properties.run.properties` 内，**不加入** `run.required`（现为 11 项，保持不变）：

```jsonc
"campaign": {
  "type": "object",
  "description": "可选战役标签块（分组维度）。缺失=未标注，分析层降级为 unlabeled/unknown，绝不猜测。",
  "additionalProperties": true,
  "properties": {
    "campaign_id": { "type": ["string", "null"], "description": "战役标识，建议 <城市>-<年季>-<批次>；优化前后对比按此分组" },
    "tier":        { "type": ["string", "null"], "description": "服务层级：metro / regional / core（三级差分归因输入）" },
    "point_id":    { "type": ["string", "null"], "description": "外场测点标识（热力卡行）" },
    "carrier":     { "type": ["string", "null"], "description": "运营商：cmcc / cucc / ctcc / 自定义" },
    "time_band":   { "type": ["string", "null"], "description": "时段：busy / idle" },
    "label_source":{ "type": ["string", "null"], "description": "标签来源溯源串，如 ui / auto:carrier / inferred:time_band，多来源用 + 连接" },
    "server_tier_endpoint": { "type": ["string", "null"], "description": "可选诊断：本 run 目标服务端（层级对账），不参与分组" }
  }
}
```

**为何字段全部可空而非省略**：一次外场里"这个 run 没选点位"与"这个 run 点位是空串"必须可区分；
可空 + 分析层 `unlabeled` 桶已覆盖前者。**为何不加 `enum` 锁 tier/carrier/time_band**：
外场会遇到自定义运营商与临时层级命名，锁死会让真实数据进不了库（与 D-08「门限随数据回流
重标定」同精神）；取值合法性由分析层呈现（未知值单独成桶），不由 schema 拒收。

**注意**：`label_source` 与离线补注 `scripts/annotate_campaign.py` 写的是**同一字段同一语义**
（该脚本已在用 `map`/`set`/`inferred:time_band` 这类标记，多来源 `+` 连接）。
接线后离线补注仍可用于补历史语料，两条路径不冲突：补注只填 gap，**app 写入的标签永不被覆盖**。

---

## 3. S2：持久化（Room 15→16 加性迁移）

**为什么要落库而不只是传参**：标签在发起测试时选定，必须与 run 一同持久化——否则历史页
看不到、重新上报会丢标签。这与 D-77/78 给 `adapter_obs` 加 `sessionSpanMs` 的加性迁移同型。

`TestRun`（[Entities.kt:14](../app/probe/src/main/java/com/aneb/probe/data/Entities.kt:14)）新增，
风格对齐既有可空列（`appVersionName: String?`、`guardMetadata: String?`）：

```kotlin
// ---- 战役标签（可选；缺失=未标注，R-10：绝不以空串/默认值顶替）----
val campaignId: String? = null,
val campaignTier: String? = null,
val campaignPointId: String? = null,
val campaignCarrier: String? = null,
val campaignTimeBand: String? = null,
val campaignLabelSource: String? = null,
```

迁移按 [AnebDatabase.kt](../app/probe/src/main/java/com/aneb/probe/data/AnebDatabase.kt) 既有
`MIGRATION_N_M_SQL: List<String>` + `object : Migration(N, M)` 模式，`version = 15` → `16`：

```kotlin
internal val MIGRATION_15_16_SQL: List<String> = listOf(
    "ALTER TABLE test_run ADD COLUMN campaignId TEXT",
    "ALTER TABLE test_run ADD COLUMN campaignTier TEXT",
    "ALTER TABLE test_run ADD COLUMN campaignPointId TEXT",
    "ALTER TABLE test_run ADD COLUMN campaignCarrier TEXT",
    "ALTER TABLE test_run ADD COLUMN campaignTimeBand TEXT",
    "ALTER TABLE test_run ADD COLUMN campaignLabelSource TEXT",
)
```

**约束**（与既有迁移注释一致）：列名 = 字段名；`String?` → `TEXT`；**可空、无默认值**
（历史行为 NULL = "当时未标注"，与 R-10 null 语义一致）；Room 迁移后按 `@Entity` 期望
schema 逐列校验，偏差 fail-fast。**真机迁移须实测**（P40 上验证 `user_version` 15→16
且既有数据存活，做法同 D-78）。

---

## 4. S3：上报体写入

[ResultReporter.kt:28](../app/probe/src/main/java/com/aneb/probe/engine/ResultReporter.kt:28)
`build()` 的 `put("run", buildJsonObject { ... })` 内，**沿用既有 `aqs_v02` / `aqs_token`
的条件加性写法**（`if (x != null) put(...)`）：

```kotlin
// 战役标签（加性）：整块仅在有任一标签时写入——无标签的 run 上报体与今天逐字节一致
if (run.campaignId != null || run.campaignPointId != null || run.campaignCarrier != null ||
    run.campaignTimeBand != null || run.campaignTier != null) {
    put("campaign", buildJsonObject {
        put("campaign_id", run.campaignId)
        put("tier", run.campaignTier)
        put("point_id", run.campaignPointId)
        put("carrier", run.campaignCarrier)
        put("time_band", run.campaignTimeBand)
        put("label_source", run.campaignLabelSource)
    })
}
```

**关键**：块内各字段**照写 null**（不做 "null 就省略"），这样"选了点位没选运营商"与
"整个 run 没标注"在语料里可区分。**整块**在全部标签为 null 时不写——保证未使用该功能的
用户上报体零变化。

---

## 5. S4：P1a 采集要求（发起测试页）

| 标签 | 采集方式 | 溯源标记 | 诚实约束 |
|---|---|---|---|
| `campaign_id` | 文本输入 + 最近使用下拉（一场战役内反复用同一个） | `ui` | 不自动生成，空即空 |
| `point_id` | 文本输入 + 最近使用下拉 | `ui` | **不用 GPS 自动命名**（点位是人给的业务标识，不是坐标） |
| `carrier` | `TelephonyManager` 自动填 + 允许人工覆盖 | 自动=`auto:carrier`，人改=`ui` | 读不到即留空，**绝不**默认 cmcc |
| `time_band` | 由 `started_at_epoch_ms` 本地小时推断 + 允许人工覆盖 | 推断=`inferred:time_band`，人改=`ui` | 推断值必须打 `inferred` 标记（与离线补注同规则） |
| `tier` | 下拉 metro/regional/core | `ui` | **须与本次实际目标服务端一致**——见下方陷阱 3 |

多来源时 `label_source` 用 `+` 连接（如 `ui+auto:carrier+inferred:time_band`），与
`annotate_campaign.py` 写法一致。

**建议交互**：一场战役里除 `tier` 外的标签在多次测试间**粘滞**（记住上次选择），
外场一天要跑几十轮，每轮重填是主要出错源。

---

## 6. 验收标准（做完怎么算对）

1. **契约门**：带标签与不带标签的真实上报体，`python scripts/validate_results.py <file>` 均 exit 0。
2. **schema 门**：`verify_all.ps1` 的 `results-contract-unit` PASS（该验证器**从 schema 文件实时
   读取**必填清单，schema 改动会被它立即反映，不会漂移）。
3. **回归**：未标注 run 的上报体与改动前**逐字节一致**（整块不写的保证）。
4. **端到端**：一批带标签的真实 run →
   `python scripts/campaign_report.py <file> --md r.md`，报告「覆盖盘点」显示真实
   point/carrier/time_band 分布、**不出现** "全部记录无 run.campaign 标签" 告警。
5. **迁移**：真机 `user_version` 15→16，既有数据存活，无异常（同 D-78 做法）。
6. **溯源**：自动填与推断的标签在 `label_source` 里可辨认（抽查若干条记录）。

---

## 7. 陷阱清单（实施时最容易做错的五件事）

1. **把 campaign 加进 `required`** —— 会让所有老客户端上报立刻违约。它必须是可选的。
2. **给缺失标签填默认值**（如 carrier 默认 `cmcc`、time_band 默认 `busy`）—— 直接违反 R-10：
   缺测量 ≠ 某个值。分析层已有 `unlabeled`/`unknown` 桶专门承接缺失，填默认值只会把
   coverage 缺口伪装成数据。
3. **`tier` 与实际目标服务端不一致** —— 三级差分归因的整个方法学（铁律 3 共模抵消）
   建立在"同客户端同接入对三级镜像端各测一轮"之上。若 UI 标了 `core` 而实际打的是同城端，
   归因矩阵会给出**看起来合理但完全错误**的骨干增量。建议 `tier` 由实际选用的服务端配置
   **派生**而非人工独立选择，并把目标端写进 `server_tier_endpoint` 供对账。
4. **推断值不打 `inferred` 标记** —— 忙闲推断是本地小时启发式（近似），未标记就会被当作
   实测事实。离线补注已建立该规则，接线必须沿用。
5. **在标签写入路径上做任何"顺手清洗"**（trim 后为空转 null 可以；大小写归一、
   同义词映射不要做）—— 分析层负责呈现与分桶，生产者负责如实记录。两者混淆会让
   "数据里到底是什么"无法回答。

---

## 8. 与离线补注的关系（接线后仍保留）

`scripts/annotate_campaign.py` **不废弃**：接线前的历史语料、以及接线后偶发漏标的 run，
仍靠它补注。优先级规则已实现且有 golden 守卫：**记录上已有的标签 > `--map`（按 run_id）>
`--set`（统一）> `--infer-time-band`**——即 **app 写入的标签永远赢**，补注只填空缺。

---

*v1.0 · 2026-07-25 · 分析层 lane 撰写，待 spec 属主 / P1 lane 审定实施。*
*相关：[`CAMPAIGN_LABELS_CONVENTION.md`](CAMPAIGN_LABELS_CONVENTION.md)（口径）、*
*[`M2_CAMPAIGN_RUNBOOK.md`](M2_CAMPAIGN_RUNBOOK.md)（外场操作）、`scripts/README.md`（分析工具集）。*
