# `DW-20260831-01` 证据包（豆包 ＋ DeepSeek × {WiFi, 蜂窝}）

> **本包在飞** —— 窗未收，格陆续落地。**收窗前不得引用本包任何数值下结论。**

## 0. 这一窗是什么

- **批次 ID**：`DW-20260831-01`（命题单 `docs/BATCH_PROPOSITION_DW-NEXT.md`，锁定 `a85115f` @ 09:43）
- **窗令**：`docs/DW_NEXT_WINDOW_ORDER_DRAFT_20260831.md`（已激活；D-635／D-636）
- **格阵**（T33 §3，**逐格交替、不按条件分组**）：

| # | 格 | App | 形态 | 功能 | 轮 | 命题 |
|---|---|---|---|---|---|---|
| 1 | `wifi_f6` | 豆包 | WiFi | F6 图像生成 | 6 | P2 |
| 2 | `cell_f6` | 豆包 | 蜂窝 | F6 | 6 | P2 |
| 3 | `ds_wifi_f6` | DeepSeek | WiFi | F6 | 6 | **P1（预期失败＝产出）** |
| 4 | `ds_cell_f6` | DeepSeek | 蜂窝 | F6 | 6 | P1 |
| 5 | `ds_wifi_f1` | DeepSeek | WiFi | F1 短答 | 6 | P3 |
| 6 | `ds_cell_f1` | DeepSeek | 蜂窝 | F1 | 6 | P3 |

## 1. 采集参数（**开窗前定死，逐格照抄**）

```
python tools/e234/e234_collect.py --serial <SN> --pkg <PKG> \
  --roi 400,1800,400,200 --allow-real-device --device-window DW-20260831-01 \
  --session-seconds 700 --screencap-period-ms 1500 --framestats-period-s 1 --no-marks \
  --out evidence/wave1_20260831/<格名>
```

- **`--framestats-period-s 1`**：本批唯一相对 DW-02 改动的采集参数（D-599／D-600）。
  界 ＝ `127 × sf_latency 首行` ＝ `127 × 16666666ns` ＝ **2.117s**（读 DW-02 的值，
  **首格产物落地后回验**）；周期 1s **＜** 界 ✅。
  ⚠ **因此本批 C 侧与 DW-02 的 C 侧不直接可比**——那正是次命题 P4 要量的东西。
- **`--screencap-period-ms 1500` 与 `--session-seconds 700`**：**照抄 DW-02**，
  不是新选的——DW-02 `wifi_f6` 实测样本 467、跨度 700s、间隔 p50 **1500ms**（本窗开窗前实测复核）。
  **改它会破坏 P2 与 DW-02 初值的可比性。**
- **驱动器**：`tools/e234/drive_cell.py`，**每格记提交哈希**（P3／D-621）。

## 2. 逐格记录

（每格落地后补：轮数／答窗与静置的**意图值与实际值**／驱动器哈希／
`layer` 是否非空／`clock_pin.status`／`turn_method`／制式前后两读／`ip route get` 出口。）

_（在飞，暂无）_

## 3. 状态

**在飞。** 收窗后按窗令与速查卡 §4 C1–C8 补齐，并做红线自证。
