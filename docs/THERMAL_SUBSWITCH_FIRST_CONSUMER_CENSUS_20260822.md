# THERMAL / SUB_SWITCH 首消费方清点与首看（2026-08-22，v3）

> **派单**（大脑，08-22 新 48h 窗第一单）：D-534 §4 解冻件——两个已采集信号各找第一消费方：
> THERMAL 与 app_jank/ITL 污染标的关联分析、SUB_SWITCH 与 RAT 时间线的对账；
> **先数语料再建守卫，空气守卫不建**。
> **纪律**：只读已拉取的设备库（`evidence/phase3/realdevice_data/*.db`），未触碰 P40；
> 每个数字出自可复跑的 SQL，命令附于文中。

---

## 1. 清点（先数语料）

```sql
SELECT type, COUNT(*) FROM env_event GROUP BY type;   -- 对五个 .db 各跑一遍，只读
```

| 库 | APP_JANK | THERMAL | SUB_SWITCH | 备注 |
|---|---|---|---|---|
| voice30_aneb-probe.db（117 run） | 9229 | 5（1 light + 4 moderate） | **0** | 主库 |
| aneb-probe.db | 89 | 0 | **0** | |
| aneb-probe-cellular.db / cellular2.db | 89 / 89 | 1 / 1 | **0** | 同一事件两次拉取（runId+tsNanos 全同） |
| voice30_voice_result_only.db | — | — | — | 无 env_event 表 |

**唯一化后全库**：THERMAL **6 个唯一事件**（2 light + 4 moderate，`polluting` 全为 false——
无一达到 SEVERE 污染标）；SUB_SWITCH **零命中**。

## 2. SUB_SWITCH：空气，按纪律不建（与 RAT 时间线的对账为空对账）

全部采集期间默认数据 subId 零切换（监听器在注册：EnvMonitors 对注册失败会记事件，
库里也没有失败事件——是「监听着但没发生」，不是「没监听」）。**对账对象不存在，
消费方不建**（D-302：0 次出现的条件等于测空气）。解禁条件：出现双卡切换的采集语料。

## 3. THERMAL：设备库内非空气，但**分析层面上仍是空气——信号不上 wire**

- 首看（只读关联，无对照设计，**方向性参考、不可归因**）：

```text
-- moderate 热状态 run 的场景 vs 其余（voice30，t2ItlP95Ms 非空）
thermal_moderate=0: 619 场景, ITL p95 均值 25.9ms, TTFT 均值 55.1ms
thermal_moderate=1:  36 场景, ITL p95 均值 28.9ms(+11.6%), TTFT 均值 53.3ms(≈持平)
```

  方向与机制预期一致（热限频先伤解析/渲染路径的 ITL、不伤网络 TTFT），但 n=36、
  无时段/点位对照，**只配「值得跟踪」不配「已证实」**；高 jank run（2521/2467 事件）
  反而全部无热事件——jank 的主因不是热。
- **真正的缺口**：`ResultReporter.kt` 对 env_event **零引用**——THERMAL 不进 result JSONL，
  分析层（scripts/，吃 wire 语料）永远看不见它。在 scripts/ 建 THERMAL 消费方=空气守卫，
  **不建**（对本库 48 个 wire 语料文件 grep thermal = 0，与 §1 的 DB 面非零并存）。

## 4. 建议（请裁）

1. **接线先行（v2 lane，与 `clock.wall_skew_ms` 同构的 additive 路子）**：wire 的 run 级
   增补 env 摘要（如 `run.env.thermal_max_status` + `polluting_event_count`），键恒在、
   无监控为 null；分析层消费方**等字段上 wire 后再建**，届时首个消费方=发布门
   「污染标 run 计数」+ ITL 表的热状态列。
2. SUB_SWITCH 维持空气判定，随双卡语料解禁。
3. 本页 §3 的首看数字**不进任何报告**（无对照、不可归因），仅作接线优先级的依据。

—— v3，2026-08-22。出处：D-534 §4（冻结与解冻）/ R-11（THERMAL SEVERE+ 污染标）/
R-13（SUB_SWITCH）/ D-302（空气守卫纪律）/ D-506 链（additive 接线先例）。
