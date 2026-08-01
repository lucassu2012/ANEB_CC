# 闲时 radio 取证批（T2）· 2026-08-01 23:00–23:27

**方法学探针，独立 `campaign_id=m2-idlenight-20260801`，不入 M2 声明。**
大脑任务 T2：三时段无线图的最后一块。台账：**4/4 completed**
（`019fbdd7` / `019fbddd` / `019fbde3` / `019fbdea`），0 次中止。

## 结论：D-365 的「闲时更差」是时段假象，**时段解释就此否定**

**四个同出口窗横跨早高峰 / 下午 / 两次闲时，RTT 极差仅 0.83 ms。**

| 窗口 | 制式 / 服务小区 | CGNAT 出口 | 暖轮 RTT 中位 | 暖轮 TTFT 中位 |
|---|---|---|---|---|
| 07-31 下午（试点，**无 radio**） | NR_SA（D-349 **现场推断，非测量**） | **`106.92.23.196`** | **53.21** | **47.34** |
| 07-31 23:04 闲时探针（**无 radio**） | 未知 | `106.80.108.105` | 69.71 | 62.51 |
| 08-01 09:36 早高峰 | LTE pci=420 | `106.80.108.105` | 68.53 | 61.77 |
| 08-01 14:01 下午 | LTE pci=420 | `106.80.108.105` | 68.72 | 61.87 |
| **08-01 23:00 闲时（本批）** | **LTE pci=420** | `106.80.108.105` | **69.36** | **61.80** |

**读法**：出口 `…108.105` 的四个窗覆盖 **09:36 / 14:01 / 23:00 / 23:04**——
既有忙时也有闲时、既有白天也有深夜——**RTT 落在 68.53–69.71（极差 1.18 ms），
TTFT 落在 61.77–62.51（极差 0.74 ms）**。而唯一落在另一出口的那个窗差 **约 15 ms**。

> **D-365 记的「23 点反而全面更差」是怎么来的**：它拿 **07-31 下午（NR/异出口，53 ms）**
> 去比 **07-31 23:04 闲时（LTE 出口，69.7 ms）**，把两个窗之间**制式与出口同时不同**
> 这件事读成了「时段」。今天在**同一出口、同一小区**上跑满一整天，
> **时段效应实测为 1 ms 量级——它不存在。**

**仍然分不开的那一对**：唯一的低 RTT 窗**同时**是唯一的 NR 窗**和**唯一的异出口窗
（`106.92.23.196`）。所以本批**只否定了时段，没有分开制式与出口路由**。
**闭环仍需一次实测到 NR 的窗**：若届时 RTT 回到 ~53 ms 且出口仍是 `…108.105`，
则制式成立、出口被排除；若挂上 NR 仍是 ~69 ms，则制式被证伪、出口是主因。

**所有数字均由本仓语料统一重算**（暖轮 = `repeat_index >= 1`，中位数），
**不是从既往文档转述**——五个窗各自从自己的 `*_labelled.jsonl` 现算，口径逐字相同。

## 无线上下文

36/36 场景携带完整八字段，`stale=false`：

| 字段 | 值 |
|---|---|
| `rat` | `LTE` ×36 |
| `pci` / `tac` / `arfcn` | `420` / `39430` / `1650` ×36（**与今日其余三窗同一小区**） |
| `rsrp_dbm` | 中位 **−69**（范围 −69…−63），档「良」 |
| `sinr_db` | **全 null**——该 ROM 不可得，诚实空缺（与前三窗一致） |
| `sampled_n` | 26–64，逐场景不同 |

**NR 未回归**：本批仍是 LTE。至此 **08-01 全天四个窗（01:55 / 09:36 / 14:01 / 23:00）
无一测到 NR**，而 07-31 下午那次 NR 是**现场推断**（该批无 radio 字段）。

## 采集与收尾

- 预检：设备在列、无 VPN/抓包、无驻留 ANEB 进程、`wifi_on=1`（批前值）
- 收尾：**wifi_on=1、stayon=0 均已还原，零残留进程**
- **契约门**：`contract OK: 4 record(s) across 1 file(s) — structural + R-10 cross-field invariants hold`
- **全部 36 场景 `valid_low_confidence`**——与 D-374 结论一致：T1 每场景仅 1 个 TTFT 样本、
  U1 仅 1 次上传（口径下限 3），**加 run 数改善不了**，是结构性的

### ⚠ 收尾焦点判据本身是坏的（本批发现，连带订正 T1 的解释）

脚本流水记 `wrap-up: launcher focused = False (after 30s)`，而三个独立量法当场推翻它：

| 量法 | 读数 |
|---|---|
| `mCurrentFocus`（脚本一直用的） | `Window{bef519c u0 NotificationShade}` |
| **`mFocusedApp`** | **`com.huawei.android.launcher/.unihome.UniHomeLauncher`** |
| `Recent #0` | `Task type=home, com.huawei.android.launcher, visible=true` |
| `dumpsys window policy` | **`screenState=SCREEN_STATE_OFF`、`keyguard showing=true`** |

**`mCurrentFocus=NotificationShade` 不是「用户把通知栏拉下来了」，而是「屏幕已灭、锁屏中」**
——锁屏时该窗口持有窗口焦点是 Android 常态。**设备实际就在桌面上、屏灭已锁、零残留。**

**连带订正 `afternoonradio_20260801/README.md` 的那条解释**：它把同一现象归因为
「华为 ROM 收起面板是动画、脚本 sleep 8 秒抓早了」——**那个解释是错的**，
与动画和时机无关。而我据此为 T2 写的「轮询 30 秒等 launcher」**永远不可能成功**，
因为它在等一个屏灭状态下不会出现的值。**判据应改为 `mFocusedApp`**（或
`Recent #0` 的 `type=home`），并把 `screenState` 一并打印。

> 同一窗口 ID `bef519c` 横跨 T1 预检、T1 收尾、T2 预检、T2 收尾——十小时不变。
> **这个不动的 ID 本身就是「它不是真实焦点」的线索**，此前四次都没被当作线索读。

## 复现

```
cd scripts
python validate_results.py ../evidence/t2_idlenight_20260801/idlenight_raw.jsonl
python trust_rollup.py ../evidence/t2_idlenight_20260801/idlenight_labelled.jsonl
python radio_rollup.py ../evidence/t2_idlenight_20260801/idlenight_labelled.jsonl
```

**语料是怎么拉下来的**（runbook 只说「把真机拉下来的原始 JSONL」，从不说怎么拉）：
`/api/v1/results` 只支持 POST、设备无 `sqlite3`、仓内无 db→jsonl 工具，
故须把 Room 库（**连 `-wal`/`-shm` 一起**，否则漏最近写入）拉到本地再解析。
本批用 scratchpad 的 `pull_t2_corpus.py`，跑批前已对 T1 语料端到端验证：
**逐条深度相等 4/4、场景 36/36**。该脚本尚未入仓，属明日待办。
