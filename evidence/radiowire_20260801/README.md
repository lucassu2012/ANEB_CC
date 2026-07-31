# radio_ctx 接线真机验证 · 2026-08-01 01:53–01:58

**接线验证语料,独立 `campaign_id=radiowire-verify-20260801`,不入任何战役声明。**
验证对象 = D-367 的无线上下文接线(`RADIO_CONTEXT_WIRING_SPEC` v1.0 生产侧验收 §6),
同时是 **D-366 预热轮丢弃协议的首次实用**。

## 台账

| 轮 | run_id | 处置 |
|---|---|---|
| 预热轮 | `019fb94f-1c9c-7f69-a8f5-f837391abf50` | **丢弃**(D-366 协议;完成但不拉取不入语料) |
| 计入轮 | `019fb951-67e2-7cdb-8096-0f1ea2c799b8` | `counted_raw.jsonl` / `counted_labelled.jsonl` |

覆盖安装(Room v15→16 迁移实机通过,无 Migration 异常);收尾核验干净
(WiFi 恢复=1、stayon=0、Launcher、无残留进程),见 `capture_log.txt`。

## 验收结果(规格 §6 生产侧)

三个蜂窝场景的 `network_snapshot.radio` **八键齐备**:
`rat=LTE`、`rsrp_dbm=-63`、**`sinr_db=null`(该 ROM 的 LTE RSSNR 不可得——诚实 null,
不是哨兵,R-10 语义实战首验)**、`pci=420/tac=39430/arfcn=1650`、
`sampled_n=27/63/37`(全新鲜)、`stale=false`。契约门放行;
`radio_rollup` 首次在真实数据出段(`radio_rollup_output.md`):信号档**良**、
SINR 记 `—`、小区可识别、薄样本带 `*`、忙闲可比性如实报「无从核对」。

## 顺带的实测发现(接线第一晚就开始还债)

**凌晨 01:55 挂的是 LTE(pci 420),而白天试点为 NR_SA(D-349)**——这正是
D-365 闲时探针列为「无法排除」的制式/小区变化,现在是可测事实了。单轮不定性;
下次忙闲对照(radio 已接线)可直接回答「23 点变差」三个候选解释中的这一个。

## 复现

```
cd scripts
python validate_results.py ../evidence/radiowire_20260801/counted_raw.jsonl
python radio_rollup.py ../evidence/radiowire_20260801/counted_labelled.jsonl
```
