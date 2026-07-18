# 授权 Token 采集接口规格 + PO 决策项（任务 #5 / D-63）

> 日期：2026-07-18（Asia/Shanghai）
> 范围：ANEB App 侧 API 直调探针 → observation 采集 seam；与 Codex `tools/aneb-ai-behavior-model` 校准流水线的交接；启动真实采集前必须由 Product Owner 拍板的决策项。

## 0. 边界与口径（先讲清楚）

- **口径 = `application_end_to_end_to_llm_api`（API 直调）**，**≠ 消费级 App 画像**（`spec/portraits/{doubao,deepseek,tongyi,kimi}.yaml`）。后者 token/think 层因 mitm 明文不可得（D-61）**恒 PENDING**，本 seam 绝不回填它们。
- **非仿真级**：本 seam 产出的 observation 喂 Codex 校准流水线，**不翻 ANEB App 的 params 门控**（`source_portrait` 仍 PENDING-CAPTURE，`params` 仍全 null）。它翻的是 **API/编程 Agent** 那道 profile 门。
- **契约由 Codex 定义，本仓引用不重定义**：`aneb-token-observation-v1` / `aneb-calibration-dataset-v1` / `aneb-model-validation-v1`（见 `DevSpace/aneb-probe-codex-v0.2.0/tools/aneb-ai-behavior-model/schemas/` 与 `docs/P3_CALIBRATION_PIPELINE_2026-07-18.md`）。
- **符合性已程序化验证**（2026-07-18）：`TokenObservationExport.buildObservation` 的输出形状（含/不含 `response_artifact_bytes` 两条路径）经 Python jsonschema 校验 **2/2 符合** `aneb-token-observation-v1.schema.json`。

## 1. ANEB App 侧采集接口（已建 + 已验证，#2/D-63）

代码：`app/probe/.../apiprobe/{ApiProbe.kt, TokenObservationExport.kt}`。

- **接口 seam**：`ApiProbe.run(config, observationSink: ObservationSink? = null, log)`。
  - `ObservationSink(datasetSecret: ByteArray, subject: String, workloadKind = TEXT, emit: suspend (String)->Unit)`。
  - **仅当传入 sink 且探针"干净成功"（`error == null` 且有解析结果）时**才生成并 `emit(observation)`；否则记 `APIPROBE_OBSERVATION generated=false reason=probe_not_clean|insufficient_data`。
  - **不传 sink = 对照列探针零行为变化**（默认关，向后兼容——两处既有调用零改动）。
- **隐私红线**（对齐契约 §3）：
  - `subject_group_id` = **数据集专用密钥的 HMAC-SHA256**（`hmac-sha256:<64hex>`）；普通 `SHA256(account)` 不足。密钥与 subject **仅用于派生，绝不入库/导出/日志**。
  - 白名单 8 必需 + 1 可选字段，`additionalProperties=false`——**无 prompt/content/account/key 出口面**。
- **探针输出 → observation 映射口径**（`TokenObservationExport.fromProbeOutputs`）：
  | observation 字段 | 来源 | 缺失语义 |
  |---|---|---|
  | `payload_bytes` | 请求体 UTF-8 字节数 | ≥1 否则跳过 |
  | `processing_delay_ms` | 探针 TTFT（请求发起→首 token） | null（无 token 到达）→ 整条跳过 |
  | `output_token_count` | 服务端 usage；**缺失回退 delta 事件数**（合同允许） | 两者皆 <1 → 跳过 |
  | `token_intervals_ms` | 相邻 delta 到达间隔，剔除合帧伪 0（R-04）与非正间隔 | minItems<1 → 跳过 |
  | `response_artifact_bytes` | 流总字节（可选） | 省略 |
  | `observation_id` | `apiprobe-<providerId>-<startedAtEpochMs>` | — |
  - **R-10**：数据不足以构成合法 observation 时返回 null 让调用方**跳过该 session**，绝不补 0/哨兵。
- **单测**：`TokenObservationExportTest` **18 项全绿**（schema 白名单 / HMAC 去标识化 / 间隔重建 / usage 回退 / TTFT 缺失跳过 / observationId 格式）。

## 2. 到 Codex 校准流水线的交接

- **本侧产出**：observation **JSONL**（每行一条，`TokenObservationExport.buildJsonl`；调用方负责把 `emit` 的行落地成文件/上传）。
- **Codex 侧三段式**（不可跳步，见流水线 §2）：`prepare-token-dataset` → `calibrate-token` → `promote-token`。
- **数据集 manifest = `aneb-calibration-dataset-v1`（Codex 维护）**：用途必须含 `behavior_model_calibration`；`content_retained=false`；observation 与 subject **两级零重叠**；训练/留出分区 + 摘要冻结。
- **口径标注落 manifest 层**（`calibration-dataset-v1`：授权基础/用途/时间窗/地域桶/设备类别/采集方法），**不落单条 observation**（其 `additionalProperties=false`）。
- **验证门限**（流水线 §4，仅约束行为模型、不进 ANEB 网络评分）：每 workload ≥20 train + ≥10 holdout；payload/处理等待/输出 token/间隔的 P50·P95 相对误差 ≤20%；PAUSE(>200ms) 占比绝对误差 ≤0.05；FAST/NORMAL/PAUSE Markov 转移矩阵每行 TVD ≤0.15。

## 3. PO 决策项（gate 真实采集；对齐流水线 §7 + §3）——**均待 PO 拍板**

启动真机实采**前**，Product Owner 必须逐项裁定（`[NEEDS-PO]`）：

1. **[NEEDS-PO] 授权基础**：用哪个账号/订阅采集？合法来源声明（自有账号/获授权）。
2. **[NEEDS-PO] 用途**：确认含 `behavior_model_calibration`（manifest 硬要求）。
3. **[NEEDS-PO] 数据集专用密钥（datasetSecret）托管**：存哪、谁持有、轮换策略；**不入库/不入导出/不入仓**；不同数据集换密钥。
4. **[NEEDS-PO] subject 定义与去标识化范围**：`subject` 取什么（账号别名？）；如何保证 observation 与 subject 两级零重叠。
5. **[NEEDS-PO] 采集范围**：时间窗 / 地域桶 / 设备类别 / 采集方法（§7 要求全部明确并写入 manifest）。
6. **[NEEDS-PO] workload 覆盖**：验证需 text/document/image/video 各 ≥20 train+10 holdout；**当前探针仅固定 text 短 prompt**（`ApiProbe.PROMPT` + `max_tokens` 硬顶烧钱护栏）→ 多 workload 探针矩阵是 unlock 前置（未来工作）。
7. **[NEEDS-PO] 数据集去向/组装**：observation JSONL 落地位置 + 如何交付 Codex；**跨境**——API 直调可能出境，observation 已隐私最小化（无 prompt/content/key），但数据集去向与存储地需 PO 定。
8. **[NEEDS-PO] 保留/删除**：`content_retained=false` 已由契约保证；派生统计的保留期与删除策略。

## 4. 当前状态 & 未决

- ✅ 接口 seam 已建并验证（18 单测 + 跨端契约符合性 2/2 + 无 sink 零行为变化）。
- ✅ `check_redline.py` 已接入本地门禁 `verify_all.ps1`（`portraits-redline` 检查，PASS 实测）。
- ⏸ **未启动真实采集**：等 PO 决策 1–8 + P40 设备从异常锁定解除（`SHARED_TEST_STATUS.md` 握手）。
- ⏭ 探针目前单 workload（text）；多 workload matrix + 首个 validated 模型均在 PO 提供授权派生统计之后（流水线 §7）。
- ⚠️ 在真实数据到位前，继续用 hypothesis Profile 做网络测量**允许**，但对外只能称"产品假设驱动的可重复仿真"（流水线 §1/§7）。
