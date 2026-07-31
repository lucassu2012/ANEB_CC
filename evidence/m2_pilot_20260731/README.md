# M2 试点战役证据包 · 2026-07-31

第一份**真实数据**战役的全部产物与原始语料。结论请读
[`docs/M2_PILOT_REPORT_2026-07-31.md`](../../docs/M2_PILOT_REPORT_2026-07-31.md)；
本目录是它引用的证据。目录形态的依据见 [`evidence/README.md`](../README.md)。

## 三批采集（同一位置、同一台 P40、同一天）

| 批次 | 语料 | 规模 | 用途 |
|---|---|---|---|
| **战役正片** | `pilot_raw.jsonl` / `pilot_labelled.jsonl` | 11 轮 quick × 蜂窝(ctcc) + 1 轮闲时验证 | M2 试点的正式结论 |
| 取证对照 | `forensic_raw.jsonl` / `forensic_labelled.jsonl` | 4 轮 forensic × 蜂窝 | 序位效应、预热效应 |
| 介质对照 | `transport_probe_raw.jsonl` / `transport_probe_labelled.jsonl` | 上面 4 轮 + 4 轮 forensic × WiFi | 预热成因（无线唤醒 vs App 冷启动） |

> ⚠ **只有第一批是战役声明**。后两批是**方法学探针**，各自独立 `campaign_id`，
> **不得**并入热力卡或对外结论——它们回答的是「这份报告的数字该怎么读」。

## 产物

- `pilot_report.md` / `.html` — 综合报告（含摘要与各分析段）
- `tables_*.csv`（战役正片）/ `ftables_*.csv`（取证批）— 每段一张机读表
- `capture_log.txt` / `forensic_capture_log.txt` / `wifi_capture_log.txt` — 逐轮采集流水
  （**中止的轮次只存在于这里**：它死在上报之前，语料里看不见）

## 一次性测量脚本（结论的判据，可复跑）

| 脚本 | 回答什么 | 结论 |
|---|---|---|
| `round_effect_measure.py` | 首轮更差，是轮次还是轮内位次？ | **轮次**（9~12% vs 2~4%）→ 预热效应 |
| `warmup_by_transport.py` | 预热是无线唤醒还是 App 冷启动？ | **主因无线唤醒**（蜂窝 2.4~3.6× 于 WiFi；按绝对毫秒同样 ~2×），残余 ~4% 是 App/TLS |
| `drift_check.py` | 11 次重复可交换吗（采样量算术的前提）？ | **可交换**（与时间秩相关 +0.49/+0.27/−0.15，前后半差 <3%）——诚实的否定 |

三者都只读本目录的语料、不写任何文件。`round_effect_measure.py` 的能力已升级为
分析层正式模块 [`scripts/round_effect.py`](../../scripts/round_effect.py)（D-356），
两者结论一致，可互校。

## 复现

```
cd scripts
python validate_results.py ../evidence/m2_pilot_20260731/pilot_raw.jsonl
python campaign_report.py ../evidence/m2_pilot_20260731/pilot_labelled.jsonl --campaign m2-pilot-20260731 --md r.md --html r.html --csv t
python publish_check.py ../evidence/m2_pilot_20260731/pilot_labelled.jsonl
```

输入 sha256 与全部生效门限见 `pilot_report.md` 的「溯源 / provenance」段。
