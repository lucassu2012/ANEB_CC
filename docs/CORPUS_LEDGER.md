# 语料台账（自动生成——勿手编）

> 本文件由 `scripts/corpus_ledger.py` 全量重算生成，手改会在下次重算时丢失。
> **使用规则**：任何「进展」声明必须引用本台账的总数与增量（例：
> 「真实 run 73 → 103（+30，SZ-PILOT-01 扩展轮）」），不得各自手抄数字（SPEC-3 §3.1）。
> ⚠ **增量必须说清是哪条链**：观察通道批次（豆包先行批等）产出 **0 条 wire run**
> ——其产物喂 `validate_results.py` 即 contract VIOLATIONS，结构上进不了 wire 池，
> 见第四节。把观察批写成「真实 run +N」正是本台账要拦的那种手抄。
> 判据：装载/去重=`cc.load_records`（run_id 首见保留、body 冲突单记），
> 合成=`cc.is_synthetic` 单列，RAT=场景级计数（一 run 可跨 RAT，不折单值）。

## 一、wire 语料（真实测量，run_id 去重后）

- **真实 run 总数：101**（场景 598；文件 42 份、原始行 3513、跨文件重复 2840 条已去、body 冲突 123 条单记、坏行 0、无 run_id 0）
- 合成记录（`is_synthetic`）：**572 条，单列不计入上行**
- 证据资格（`is_admissible`，**与 mode 正交，单列不并入上行**）：可作证据 **0**／不可作证据 **0**／**未知 101**（原因：build_block_absent×101）
- 观察通道另有 **34 个真机采集目录**（dry-run 6 个、API 对照批 12 个，**三者各自单列、均不计入上行**；第四节）——其产物结构上进不了 wire 池
- 带 AQS **分数**的 run（`run.aqs.score` 非空）：99；其中 low_confidence：99/99（100%）｜顶层 `aqs_version` 版本戳共 101 条，其中 **2 条只有版本戳、没有分数**（两个量不可混用）

  > ⚠ **上行的 low_confidence 比例是结构性的，不表示这些 run 数据有问题**（D-743）：`T1` 在现行 profile 下样本数恒不达其门限（**本页作者实测**：每场景 `token_stream` 相位 s1=1／s2=2／s3=2／s4=0，**至多 2 个**），而 run 级低置信按「任一 KPI 低置信」上抛 ⇒ **只要一个真实 run 出了分，它必然低置信**。判决性对照（**本页作者独立复算**）：真实侧 99/99＝100%，而合成侧仅 5/572＝0.9%——合成语料的样本数是编出来的，从没触发过这条。
  > ⇒ **加轮不能摘帽**，只能改 profile 相位数或门限；**引用本行时不得把它当作数据质量证据**。
  > ⚠ **要查成因就读场景的 `kpi_quality` 块**——它**逐 KPI**带 `sample_count` 与 `low_confidence`（v17 起在 wire 上）。**本页作者实测**：真实侧 `T1` 有样本 382 个场景**全部低置信**、`U1` 382／382、`U1_excl_slow_start` 90／90、`D1` 12／12，而 `N1`／`N2`（各 384）与 `T2`／`T3`／`T4`／`T5`／`U2`／`U3`／`D3` **零低置信** ⇒ 钉住 run 的就这四个。
  > ⚠ **但它有覆盖边界**（2026-09-06 实测，**分母是全部真实 run 101 条、不是上行那 99 条带分 run**——两个集合不同，别混用）：**只有 63 条带该块**（598 个场景里 388 个），其余早于 v17 ⇒ **那些仍查不出成因**；合成侧 **0 条带该块**——这也是它低置信率只有 0.9% 的另一半原因。
  > 🔴 **本段是 2026-09-06 的勘误**：初版写成「wire 不带逐 KPI 的`sample_count`／`low_confidence`、台账无从判定成因」，**是错的**（D-744 撤回该说法）。留这行是因为那句错话已经进过台账一次。

- **单点位最大样本：`SZ-PILOT-01` 57 条**（其余具名外场点位：无）｜**已排除**：`PENDING-PO-01` 16（占位符，真名待回填，**不是第二个点位的证据**）；`home_indoor` 10（非外场）；无点位标签 18（不是一个点位）
  > 引用「（外场）单点位有多少」**直接引本行**，不要自己从下方维度表里挑——能自己挑就能挑错。
| 维度 | 分布（run 计） |
|---|---|
| 战役 | m3-expansion-wave0×20、unlabeled×18、t39-rehearsal-nr-20260803×16、m2-pilot-20260731×12、acceptance_20260820×10、m2-afternoonradio-20260801×4、m2-busyradio-20260801×4、m2-idlenight-20260801×4、m2-idleprobe-20260731×4、m2-pilot-forensic-20260731×4、warmup-transport-probe×4、radiowire-verify-20260801×1 |
| 点位 | SZ-PILOT-01×57、unlabeled×18、PENDING-PO-01×16、home_indoor×10（**PENDING-PO-01 是占位符不是点位**：真名待回填，不可当作一个真实站点计入覆盖） |
| 运营商 | ctcc×83、unknown×18 |
| 时窗 | busy×43、idle×40、unknown×18 |
| RAT（**场景**计——一 run 可跨 RAT，不折单值） | NR×268、no_radio_block×219、LTE×111 |
| 场景有效性 | valid_low_confidence×592、invalid×4、valid×2 |

## 二、设备侧 Room 库（与第一节**不可相加**——同 run 两面）

| 库 | test_run | scenario_result | voice_result |
|---|---|---|---|
| evidence/acceptance_20260820/acceptance_pull_aneb-probe.db | 9 | 29 | 5 |
| evidence/phase3/realdevice_data/aneb-probe-cellular.db | 6 | 26 | — |
| evidence/phase3/realdevice_data/aneb-probe-cellular2.db | 6 | 26 | — |
| evidence/phase3/realdevice_data/aneb-probe.db | 3 | 11 | — |
| evidence/phase3/realdevice_data/voice30_aneb-probe.db | 117 | 662 | 35 |
| evidence/phase3/realdevice_data/voice30_voice_result_only.db | — | — | 35 |

## 三、装载明细

| 文件 | 契约记录 | 原始行 |
|---|---|---|
| evidence/acceptance_20260820/acceptance_20260820_labeled.jsonl | 10 | 10 |
| evidence/acceptance_20260820/acceptance_20260820_raw.jsonl | 10 | 10 |
| evidence/afternoonradio_20260801/afternoon_labelled.jsonl | 4 | 4 |
| evidence/afternoonradio_20260801/afternoon_raw.jsonl | 4 | 4 |
| evidence/busyradio_20260801/busyradio_labelled.jsonl | 4 | 4 |
| evidence/busyradio_20260801/busyradio_raw.jsonl | 4 | 4 |
| evidence/m2_idleprobe_20260731/idle_labelled.jsonl | 4 | 4 |
| evidence/m2_idleprobe_20260731/idle_raw.jsonl | 4 | 4 |
| evidence/m2_pilot_20260731/forensic_labelled.jsonl | 4 | 4 |
| evidence/m2_pilot_20260731/forensic_raw.jsonl | 4 | 4 |
| evidence/m2_pilot_20260731/pilot_labelled.jsonl | 12 | 12 |
| evidence/m2_pilot_20260731/pilot_raw.jsonl | 12 | 12 |
| evidence/m2_pilot_20260731/transport_probe_labelled.jsonl | 8 | 8 |
| evidence/m2_pilot_20260731/transport_probe_raw.jsonl | 8 | 8 |
| evidence/m3_expansion_gen_20260801/expansion_counted.jsonl | 520 | 520 |
| evidence/m3_expansion_gen_20260801/expansion_counted_forensic.jsonl | 40 | 40 |
| evidence/m3_expansion_gen_20260801/expansion_counted_quick.jsonl | 480 | 480 |
| evidence/m3_expansion_gen_20260801/expansion_raw.jsonl | 560 | 560 |
| evidence/m3_expansion_rehearsal_20260801/expansion_counted.jsonl | 512 | 512 |
| evidence/m3_expansion_rehearsal_20260801/expansion_counted_forensic.jsonl | 32 | 32 |
| evidence/m3_expansion_rehearsal_20260801/expansion_counted_quick.jsonl | 480 | 480 |
| evidence/m3_expansion_rehearsal_20260801/expansion_raw.jsonl | 552 | 552 |
| evidence/m3_expansion_wave0_20260803/wave0_counted_labelled.jsonl | 20 | 20 |
| evidence/m3_expansion_wave0_20260803/wave0_counted_raw.jsonl | 20 | 20 |
| evidence/m3_expansion_wave0_20260803/wave0_forensic_subset.jsonl | 5 | 5 |
| evidence/m3_expansion_wave0_20260803/wave0_quick_subset.jsonl | 15 | 15 |
| evidence/m3_expansion_wave0_20260803/wave0_raw.jsonl | 23 | 23 |
| evidence/phase3/demo_results.jsonl | 12 | 12 |
| evidence/phase3/netem_server_results_20260713.jsonl | 8 | 8 |
| evidence/radiowire_20260801/counted_labelled.jsonl | 1 | 1 |
| evidence/radiowire_20260801/counted_raw.jsonl | 1 | 1 |
| evidence/t2_idlenight_20260801/idlenight_labelled.jsonl | 4 | 4 |
| evidence/t2_idlenight_20260801/idlenight_raw.jsonl | 4 | 4 |
| evidence/t39_report_chain_rehearsal_20260803/nr_0803_excluded_afternoon.jsonl | 3 | 3 |
| evidence/t39_report_chain_rehearsal_20260803/nr_0803_morning16_labelled.jsonl | 16 | 16 |
| evidence/t39_report_chain_rehearsal_20260803/nr_0803_morning16_raw.jsonl | 16 | 16 |
| evidence/t39_report_chain_rehearsal_20260803/nr_0803_raw.jsonl | 19 | 19 |
| evidence/t46_full_corpus_analysis_20260804/full_corpus_labelled.jsonl | 73 | 73 |
| evidence/t47_s4throughput_devverify_20260804/s4_throughput_run1.jsonl | 1 | 1 |
| evidence/t54_ctree_quick_20260904/t54_quick_raw.jsonl | 2 | 2 |
| server/data/results/20260713.jsonl | 1 | 1 |
| server/data/results/20260804.jsonl | 1 | 1 |

跳过（0 条契约记录，非语料）：`evidence/DW-20260905-01/cell_f6/screencap_index.jsonl`、`evidence/DW-20260905-01/cell_f6_driver_timing.jsonl`、`evidence/DW-20260905-01/wifi_f6/screencap_index.jsonl`、`evidence/DW-20260905-01/wifi_f6_attempt1_preflight_stop/screencap_index.jsonl`、`evidence/DW-20260905-01/wifi_f6_driver_timing.jsonl`、`evidence/DW-20260905-02/ds_cell_f1/screencap_index.jsonl`、`evidence/DW-20260905-02/ds_cell_f1_driver_timing.jsonl`、`evidence/DW-20260905-02/ds_cell_f6/screencap_index.jsonl`、`evidence/DW-20260905-02/ds_cell_f6_driver_timing.jsonl`、`evidence/DW-20260905-02/ds_wifi_f1/screencap_index.jsonl`、`evidence/DW-20260905-02/ds_wifi_f1_driver_timing.jsonl`、`evidence/DW-20260905-02/ds_wifi_f6/screencap_index.jsonl`、`evidence/DW-20260905-02/ds_wifi_f6_driver_timing.jsonl`、`evidence/DW-20260905-02/verify_trial_f1/screencap_index.jsonl`、`evidence/DW-20260905-02/verify_trial_f1_driver_timing.jsonl`、`evidence/DW-20260905-02/verify_trial_f2/screencap_index.jsonl`、`evidence/DW-20260905-02/verify_trial_f2_driver_timing.jsonl`、`evidence/DW-20260905-02/verify_trial_f6/screencap_index.jsonl`、`evidence/DW-20260905-02/verify_trial_f6_driver_timing.jsonl`、`evidence/doubao_wave0_20260830/cell_f1/screencap_index.jsonl`、`evidence/doubao_wave0_20260830/cell_f1b/screencap_index.jsonl`、`evidence/doubao_wave0_20260830/cell_f2/screencap_index.jsonl`、`evidence/doubao_wave0_20260830/cell_f2_VOID1/screencap_index.jsonl`、`evidence/doubao_wave0_20260830/cell_f5/screencap_index.jsonl`、`evidence/doubao_wave0_20260830/cell_f5_driver_timing.jsonl`、`evidence/doubao_wave0_20260830/cell_f6/screencap_index.jsonl`、`evidence/doubao_wave0_20260830/cell_f6_driver_timing.jsonl`、`evidence/doubao_wave0_20260830/wifi_f1/screencap_index.jsonl`、`evidence/doubao_wave0_20260830/wifi_f1_VOID1/screencap_index.jsonl`、`evidence/doubao_wave0_20260830/wifi_f1_VOID3/screencap_index.jsonl`、`evidence/doubao_wave0_20260830/wifi_f1_anchor/screencap_index.jsonl`、`evidence/doubao_wave0_20260830/wifi_f2/screencap_index.jsonl`、`evidence/doubao_wave0_20260830/wifi_f5/screencap_index.jsonl`、`evidence/doubao_wave0_20260830/wifi_f5_driver_timing.jsonl`、`evidence/doubao_wave0_20260830/wifi_f6/screencap_index.jsonl`、`evidence/doubao_wave0_20260830/wifi_f6_driver_timing.jsonl`、`evidence/e1/20260801-150506/screencap_index.jsonl`、`evidence/e1/20260801-170127/screencap_index.jsonl`、`evidence/e1_realdevice_20260802/mark_rtt.jsonl`、`evidence/e1_realdevice_20260802/screencap_index.jsonl`、`evidence/e1_realdevice_20260802_run2/mark_rtt.jsonl`、`evidence/e1_realdevice_20260802_run2/screencap_index.jsonl`、`evidence/e234/20260802-163504/screencap_index.jsonl`、`evidence/e234/20260802-164148/screencap_index.jsonl`、`evidence/e234/20260802-172614/screencap_index.jsonl`、`evidence/e234/20260802-173031/screencap_index.jsonl`、`evidence/e234/20260803-154544-e1band/screencap_index.jsonl`、`evidence/e234_dryrun_20260802/dryrun-e2-over/screencap_index.jsonl`、`evidence/e234_dryrun_20260802/dryrun-e2-within/screencap_index.jsonl`、`evidence/e234_dryrun_20260802/dryrun-e3-absent/screencap_index.jsonl`、`evidence/e234_dryrun_20260802/dryrun-e3-present/screencap_index.jsonl`、`evidence/e234_dryrun_20260802/dryrun-e4-overlap/screencap_index.jsonl`、`evidence/e234_dryrun_20260802/dryrun-e4-separable/screencap_index.jsonl`、`evidence/glm_e03_20260903/smoke_a/raw_sse.jsonl`、`evidence/glm_e03_20260903/smoke_b/raw_sse.jsonl`、`evidence/glm_e03_20260903/smoke_c/raw_sse.jsonl`、`evidence/glm_e03_20260903/t150_1/raw_sse.jsonl`、`evidence/glm_e03_20260903/t150_2/raw_sse.jsonl`、`evidence/glm_e03_20260903/t150_3/raw_sse.jsonl`、`evidence/glm_e03_20260903/t60_1/raw_sse.jsonl`、`evidence/glm_e03_20260903/t60_2/raw_sse.jsonl`、`evidence/glm_e03_20260903/t60_3/raw_sse.jsonl`、`evidence/glm_e03_20260903/t800_1/raw_sse.jsonl`、`evidence/glm_e03_20260903/t800_2/raw_sse.jsonl`、`evidence/glm_e03_20260903/t800_3/raw_sse.jsonl`、`evidence/phase1/calibration/clean_run1.jsonl`、`evidence/phase1/calibration/clean_run2.jsonl`、`evidence/phase1/calibration/nginx_nobuf_run1.jsonl`、`evidence/phase1/calibration/nginx_nobuf_run2.jsonl`、`evidence/phase1/calibration/nginx_run1.jsonl`、`evidence/phase1/calibration/nginx_run2.jsonl`、`evidence/phase1/calibration/proxied_run1.jsonl`、`evidence/phase1/calibration/proxied_run2.jsonl`、`evidence/phase3/e01_results/20260712.jsonl`、`evidence/t90_verify_20260901/relist1/screencap_index.jsonl`、`evidence/t90_verify_20260901/relist1/sf_layer_probe.jsonl`、`evidence/wave1_20260831/wifi_f6/screencap_index.jsonl`、`evidence/wave1_20260831/wifi_f6_b_VOID1/screencap_index.jsonl`、`evidence/wave1_20260831/wifi_f6_b_VOID1_driver_timing.jsonl`、`evidence/wave1_20260831/wifi_f6_driver_timing.jsonl`

⚠ **装载失败（坏行/读不了，不等于「不是语料」）**：`evidence/doubao_wave0_20260830/wifi_f1_VOID2/screencap_index.jsonl`（1 处）

## 四、观察通道采集（与第一节**不可相加**——两条链口径不同）

- 状态分列（D-718 B-3，**与上面按 kind 的分类正交、两组都不相加**）：有效 **43**／作废 **6**／试水 **3**／未登记 **0**；**其中真机有效格 25**（DEVICE_REAL×25、api_cmp×12、DRY_RUN_SIMULATED×6）　⚠ **「有效」是 `state=valid` 的字面义，不等于「真机观察格」**：dry-run 与 API 对照批同样是「有效」，但它们不是真机格；未登记＝早于 `state` 字段上线的老目录，也不进真机格

| 目录 | kind | state | 实验 | 包名 | 文件数 |
|---|---|---|---|---|---|
| evidence/DW-20260905-01/cell_f6 | DEVICE_REAL | valid | E2,E3,E4 | `com.larus.nova` | 15 |
| evidence/DW-20260905-01/wifi_f6 | DEVICE_REAL | valid | E2,E3,E4 | `com.larus.nova` | 15 |
| evidence/DW-20260905-01/wifi_f6_attempt1_preflight_stop | DEVICE_REAL | void（attempt_aborted） | E2,E3,E4 | `com.larus.nova` | 7 |
| evidence/DW-20260905-02/ds_cell_f1 | DEVICE_REAL | valid | E2,E3,E4 | `com.deepseek.chat` | 16 |
| evidence/DW-20260905-02/ds_cell_f6 | DEVICE_REAL | valid | E2,E3,E4 | `com.deepseek.chat` | 16 |
| evidence/DW-20260905-02/ds_wifi_f1 | DEVICE_REAL | valid | E2,E3,E4 | `com.deepseek.chat` | 16 |
| evidence/DW-20260905-02/ds_wifi_f6 | DEVICE_REAL | valid | E2,E3,E4 | `com.deepseek.chat` | 16 |
| evidence/DW-20260905-02/verify_trial_f1 | DEVICE_REAL | verify | E2,E3,E4 | `com.deepseek.chat` | 16 |
| evidence/DW-20260905-02/verify_trial_f2 | DEVICE_REAL | verify | E2,E3,E4 | `com.deepseek.chat` | 16 |
| evidence/DW-20260905-02/verify_trial_f6 | DEVICE_REAL | verify | E2,E3,E4 | `com.deepseek.chat` | 16 |
| evidence/doubao_wave0_20260830/cell_f1 | DEVICE_REAL | valid | E2,E3,E4 | `com.larus.nova` | 10 |
| evidence/doubao_wave0_20260830/cell_f1b | DEVICE_REAL | valid | E2,E3,E4 | `com.larus.nova` | 10 |
| evidence/doubao_wave0_20260830/cell_f2 | DEVICE_REAL | valid | E2,E3,E4 | `com.larus.nova` | 10 |
| evidence/doubao_wave0_20260830/cell_f2_VOID1 | DEVICE_REAL | void（void_marked_in_dir_name_and_readme） | E2,E3,E4 | `com.larus.nova` | 6 |
| evidence/doubao_wave0_20260830/cell_f5 | DEVICE_REAL | valid | E2,E3,E4 | `com.larus.nova` | 10 |
| evidence/doubao_wave0_20260830/cell_f6 | DEVICE_REAL | valid | E2,E3,E4 | `com.larus.nova` | 10 |
| evidence/doubao_wave0_20260830/wifi_f1 | DEVICE_REAL | valid | E2,E3,E4 | `com.larus.nova` | 10 |
| evidence/doubao_wave0_20260830/wifi_f1_VOID1 | DEVICE_REAL | void（void_marked_in_dir_name_and_readme） | E2,E3,E4 | `com.larus.nova` | 10 |
| evidence/doubao_wave0_20260830/wifi_f1_VOID2 | DEVICE_REAL | void（void_marked_in_dir_name_and_readme） | E2,E3,E4 | `com.larus.nova` | 8 |
| evidence/doubao_wave0_20260830/wifi_f1_VOID3 | DEVICE_REAL | void（void_marked_in_dir_name_and_readme） | E2,E3,E4 | `com.larus.nova` | 10 |
| evidence/doubao_wave0_20260830/wifi_f1_anchor | DEVICE_REAL | valid | E2,E3,E4 | `com.larus.nova` | 10 |
| evidence/doubao_wave0_20260830/wifi_f2 | DEVICE_REAL | valid | E2,E3,E4 | `com.larus.nova` | 10 |
| evidence/doubao_wave0_20260830/wifi_f5 | DEVICE_REAL | valid | E2,E3,E4 | `com.larus.nova` | 10 |
| evidence/doubao_wave0_20260830/wifi_f6 | DEVICE_REAL | valid | E2,E3,E4 | `com.larus.nova` | 10 |
| evidence/e1_realdevice_20260802 | DEVICE_REAL | valid | E2,E3,E4 | `com.aneb.e1stimulus` | 12 |
| evidence/e1_realdevice_20260802_run2 | DEVICE_REAL | valid | E2,E3,E4 | `com.aneb.e1stimulus` | 12 |
| evidence/e234/20260802-163504 | DEVICE_REAL | valid | E2,E3,E4 | `com.aneb.e1stimulus` | 7 |
| evidence/e234/20260802-164148 | DEVICE_REAL | valid | E2,E3,E4 | `com.aneb.e1stimulus` | 10 |
| evidence/e234/20260802-172614 | DEVICE_REAL | valid | E2,E3,E4 | `com.aneb.e1stimulus` | 7 |
| evidence/e234/20260802-173031 | DEVICE_REAL | valid | E2,E3,E4 | `com.aneb.e1stimulus` | 12 |
| evidence/e234/20260803-154544-e1band | DEVICE_REAL | valid | E2,E3,E4 | `com.aneb.e1stimulus` | 10 |
| evidence/e234_dryrun_20260802/dryrun-e2-over | DRY_RUN_SIMULATED | valid | — | — | 11 |
| evidence/e234_dryrun_20260802/dryrun-e2-within | DRY_RUN_SIMULATED | valid | — | — | 11 |
| evidence/e234_dryrun_20260802/dryrun-e3-absent | DRY_RUN_SIMULATED | valid | — | — | 11 |
| evidence/e234_dryrun_20260802/dryrun-e3-present | DRY_RUN_SIMULATED | valid | — | — | 11 |
| evidence/e234_dryrun_20260802/dryrun-e4-overlap | DRY_RUN_SIMULATED | valid | — | — | 11 |
| evidence/e234_dryrun_20260802/dryrun-e4-separable | DRY_RUN_SIMULATED | valid | — | — | 11 |
| evidence/glm_e03_20260903/smoke_a | api_cmp | valid | E-03 | — | 3 |
| evidence/glm_e03_20260903/smoke_b | api_cmp | valid | E-03 | — | 3 |
| evidence/glm_e03_20260903/smoke_c | api_cmp | valid | E-03 | — | 3 |
| evidence/glm_e03_20260903/t150_1 | api_cmp | valid | E-03 | — | 3 |
| evidence/glm_e03_20260903/t150_2 | api_cmp | valid | E-03 | — | 3 |
| evidence/glm_e03_20260903/t150_3 | api_cmp | valid | E-03 | — | 3 |
| evidence/glm_e03_20260903/t60_1 | api_cmp | valid | E-03 | — | 3 |
| evidence/glm_e03_20260903/t60_2 | api_cmp | valid | E-03 | — | 3 |
| evidence/glm_e03_20260903/t60_3 | api_cmp | valid | E-03 | — | 3 |
| evidence/glm_e03_20260903/t800_1 | api_cmp | valid | E-03 | — | 3 |
| evidence/glm_e03_20260903/t800_2 | api_cmp | valid | E-03 | — | 3 |
| evidence/glm_e03_20260903/t800_3 | api_cmp | valid | E-03 | — | 3 |
| evidence/t90_verify_20260901/relist1 | DEVICE_REAL | valid | E2,E3,E4 | `com.larus.nova` | 9 |
| evidence/wave1_20260831/wifi_f6 | DEVICE_REAL | valid | E2,E3,E4 | `com.larus.nova` | 10 |
| evidence/wave1_20260831/wifi_f6_b_VOID1 | DEVICE_REAL | void（void_marked_in_dir_name_and_readme） | E2,E3,E4 | `com.larus.nova` | 10 |

> 这些目录**产出 0 条 wire run**——产物喂 `validate_results.py` 即 contract VIOLATIONS。列在这里是为了让「一个设备窗跑完、台账一个数都不动」不再发生，**不是**为了相加。判据＝目录里有 `RUN_KIND.json`（采集器自己写的标记，非文件名清单）；早于该标记的采集目录不在此表，仍落在第三节的通用桶里。
>
> ⚠ **本表不是采集目录的全集**：另有 **3 个**目录有采集产物却无 `RUN_KIND.json`，故数不进来（2026-09-06 全扫实测，判据面**不扩**，列出来只为让读者别把本表当全集）——`evidence/e1/20260801-150506` 与 `evidence/e1/20260801-170127`（各 6–7 个产物的正式跑，**早于标记上线**，见 `observation_runs` docstring 的边界说明），以及 `evidence/DW-20260905-02/ds_wifi_f6_attempt1_toggle_stop`（只有 `orchestrator.log`，**夭折于写标记之前**）。
