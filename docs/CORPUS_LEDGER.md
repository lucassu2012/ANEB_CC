# 语料台账（自动生成——勿手编）

> 本文件由 `scripts/corpus_ledger.py` 全量重算生成，手改会在下次重算时丢失。
> **使用规则**：任何「进展」声明必须引用本台账的总数与增量（例：
> 「真实 run 73 → 103（+30，豆包首批）」），不得各自手抄数字（SPEC-3 §3.1）。
> 判据：装载/去重=`cc.load_records`（run_id 首见保留、body 冲突单记），
> 合成=`cc.is_synthetic` 单列，RAT=场景级计数（一 run 可跨 RAT，不折单值）。

## 一、wire 语料（真实测量，run_id 去重后）

- **真实 run 总数：110**（场景 624；文件 39 份、原始行 3509、跨文件重复 2839 条已去、body 冲突 123 条单记、坏行 0、无 run_id 0）
- 合成记录（`is_synthetic`）：**560 条，单列不计入上行**
- 带 AQS 的 run：109；其中 low_confidence：99/109（91%）

| 维度 | 分布（run 计） |
|---|---|
| 战役 | unlabeled×27、m3-expansion-wave0×20、t39-rehearsal-nr-20260803×16、m2-pilot-20260731×12、acceptance_20260820×10、m2-afternoonradio-20260801×4、m2-busyradio-20260801×4、m2-idlenight-20260801×4、m2-idleprobe-20260731×4、m2-pilot-forensic-20260731×4、warmup-transport-probe×4、radiowire-verify-20260801×1 |
| 点位 | SZ-PILOT-01×57、unlabeled×27、PENDING-PO-01×16、home_indoor×10 |
| 运营商 | ctcc×83、unknown×27 |
| 时窗 | busy×43、idle×40、unknown×27 |
| RAT（**场景**计——一 run 可跨 RAT，不折单值） | NR×268、no_radio_block×245、LTE×111 |
| 场景有效性 | valid_low_confidence×586、valid×32、degraded×4、invalid×2 |

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

跳过（0 条契约记录，非语料）：`evidence/e1/20260801-150506/screencap_index.jsonl`、`evidence/e1/20260801-170127/screencap_index.jsonl`、`evidence/e1_realdevice_20260802/mark_rtt.jsonl`、`evidence/e1_realdevice_20260802/screencap_index.jsonl`、`evidence/e1_realdevice_20260802_run2/mark_rtt.jsonl`、`evidence/e1_realdevice_20260802_run2/screencap_index.jsonl`、`evidence/e234/20260802-163504/screencap_index.jsonl`、`evidence/e234/20260802-164148/screencap_index.jsonl`、`evidence/e234/20260802-172614/screencap_index.jsonl`、`evidence/e234/20260802-173031/screencap_index.jsonl`、`evidence/e234/20260803-154544-e1band/screencap_index.jsonl`、`evidence/e234_dryrun_20260802/dryrun-e2-over/screencap_index.jsonl`、`evidence/e234_dryrun_20260802/dryrun-e2-within/screencap_index.jsonl`、`evidence/e234_dryrun_20260802/dryrun-e3-absent/screencap_index.jsonl`、`evidence/e234_dryrun_20260802/dryrun-e3-present/screencap_index.jsonl`、`evidence/e234_dryrun_20260802/dryrun-e4-overlap/screencap_index.jsonl`、`evidence/e234_dryrun_20260802/dryrun-e4-separable/screencap_index.jsonl`、`evidence/phase1/calibration/clean_run1.jsonl`、`evidence/phase1/calibration/clean_run2.jsonl`、`evidence/phase1/calibration/nginx_nobuf_run1.jsonl`、`evidence/phase1/calibration/nginx_nobuf_run2.jsonl`、`evidence/phase1/calibration/nginx_run1.jsonl`、`evidence/phase1/calibration/nginx_run2.jsonl`、`evidence/phase1/calibration/proxied_run1.jsonl`、`evidence/phase1/calibration/proxied_run2.jsonl`、`evidence/phase3/e01_results/20260712.jsonl`
