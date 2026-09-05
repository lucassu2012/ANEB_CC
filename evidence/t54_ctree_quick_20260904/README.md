# `t54_ctree_quick_20260904` · T54 首次跑通的两条 quick run（诊断口径）

> 口径：**诊断（diagnostic），不作吞吐线结论引用**——A-8 合入前 U3 为本地写口径、h2 不记协议、无构建指纹（M-B-011④）。
> 台账（`docs/CORPUS_LEDGER.md`）按**结构**计数：两条均为契约合法的真实 run，故总数 111→113；「诊断口径」是读法限定，不改变计数。**⚠ 台账口径说明（M-B-013①，SP-F-01）**：该 113 含 12 条合成 demo（`server/data` 合成结果，待 A-4 加 synthetic 块后重算剔除）⇒ 进展声明写作「真机 wire run 99→101（台账口径 113 含 12 demo，待 A-4）」，113 不进 PO 简报。

## 来源

- 设备 P40 Pro `8MY0221126002537`，探针包 **`com.aneb.probe.ctree`**（C 树 APK `0.1.0-phase0`，D-702 换名装机），Room 库经 `scripts/pull_device_corpus.py`（`ANEB_PKG=com.aneb.probe.ctree`）只读拉取，`--since-epoch-ms 1788451200000`（2026-09-04 00:00 +0800）。
- 对端：PC 端 C 树 server（`aneb-server/0.1.0`，TLS 自签 IP-SAN），真 WiFi 直连；见 D-703。
- 文件：`t54_quick_raw.jsonl`（2 条 run 记录，`kept=2 / skipped_before_cutoff=0 / unparseable=0`）。

## 两条 run 分别是什么（不可混读）

| run_id 前缀 | 起始（+0800） | 模式／链路 | profile 来源 | 场景 | 读法 |
|---|---|---|---|---|---|
| `01a069f2` | 2026-09-04 09:04:26 | quick／wifi | `assets_fallback`（s4 被跳过） | s1–s3 全部 `invalid`，原因 `TRUNCATED` | **失败样本**：server profile 未取到时的回落路径；只证明「回落不含 s4」，不含任何 KPI 数值 |
| `01a069f8` | 2026-09-04 09:11:53 | quick／wifi | `server` | s1–s3 `valid_low_confidence`；**s4_throughput `valid`** | D-703 那条：整链首次跑通的证据；AQS 89.09 属 quick 单次、低置信为主，不作评分结论 |

## 不回答什么

- 不是吞吐线的采样（n=1，quick，A-8 前口径）；D-587 #5 的正式采样待 A-8 合入后另开。
- 不与 `evidence/phase3/realdevice_data/` 的 G 树血统数据相加或对比——探针包、server、profile 三者均不同源。

## 守卫

- 目录名形态 `<战役>_<YYYYMMDD>`，随 `scripts/check_evidence.py` 日期包 README 规则。
- 入库当轮台账 `--check` in sync（2026-09-05 21 时段）。
