# 闲时对照探针 · 2026-07-31 23:04–23:31

**方法学探针,独立 `campaign_id=m2-idleprobe-20260731`,不得并入 M2 试点声明**(与
`m2_pilot_20260731` 的取证/介质两批同一地位)。回答试点网格唯一没回答的维度:
**同点位、同设备、同蜂窝,忙时 vs 闲时差多少**。

## 语料

| 文件 | 内容 |
|---|---|
| `idle_raw.jsonl` / `idle_labelled.jsonl` | 4 轮 forensic × 蜂窝(ctcc),23:04–23:31,`time_band=idle` |
| `idle_capture_log.txt` / `idle_logcat.txt` | 逐轮采集流水与设备日志(4/4 completed,无中止) |

对照侧 = `../m2_pilot_20260731/forensic_labelled.jsonl`(忙时 4 轮 forensic,同点位同设备)。

采集为无人值守批:预检发现 `com.aneb.probe` 驻留进程(**非本批启动**),按只读深查
归因为 D-347 良性缓存形状(零活动服务、屏幕 Asleep、静置 2h29m、无 VPN)后才开测;
判据已固化进批脚本(有活动服务=别人的会话,立即放弃)。收尾核验:WiFi 恢复、
stayon 关、无残留进程。

## 判据与结论(`busy_vs_idle.py`,判据先于数据定死)

只比**暖轮**(`repeat_index>=1`,D-355/D-358:排除冷启动伪装成时段效应);
「超噪声」仅当两侧暖轮**区间完全不相交**(n≈8/侧,更细的检验是仪式)。
输出固化于 `busy_vs_idle_output.txt`。

**结论:闲时反而全面更差**——9 行里 **6 行区间完全不相交**:
RTT 中位 +26~34%(53→70ms 量级)、TTFT +26~34%;AQS 由 90.0–91.4 降到 88.7–89.3。
上行吞吐仅 s1(时延代理,D-363)超噪声变差,s2/s3 在噪声内。

**三个候选解释,今晚的数据分不开,不定性**:
1. **路径变了(已测到)**:CGNAT 出口 IP 忙时 `106.92.23.196` → 闲时 `106.80.108.105`,
   出省/出网关路由可能不同;
2. **基站夜间节能**(载波/符号关断、更深 DRX)——行业已知、方向吻合,但本轮无证据;
3. **小区/频段改变**——**无法排除**:无线上下文尚未接线(`RADIO_CONTEXT_WIRING_SPEC`),
   这正是它该提优先级的又一实证。

**对 M2 的含义**:D4 拍板「只测忙时」侥幸躲开了一个真变量——**时段差异真实存在且
方向反直觉**,若外场扩点要跨时段,无线上下文与出口 IP 必须随采。

## 复现

```
cd scripts
python validate_results.py ../evidence/m2_idleprobe_20260731/idle_raw.jsonl
python ../evidence/m2_idleprobe_20260731/busy_vs_idle.py ../evidence/m2_pilot_20260731/forensic_labelled.jsonl ../evidence/m2_idleprobe_20260731/idle_labelled.jsonl
```
