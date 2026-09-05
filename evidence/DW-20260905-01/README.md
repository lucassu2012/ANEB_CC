# `DW-20260905-01` 证据包（P2 两腿先行批：豆包 × {WiFi, 蜂窝} × F6）

> 🔑 **目录名＝批次 ID**（承 wave1 README 首条教训「下一批目录名直接用批次 ID」）：`evidence/DW-20260905-01/` ⇔ 批次 `DW-20260905-01`。
> **状态**：开窗中（2026-09-05）；收窗后本行改写并补 §5。

## 0. 这一窗是什么

- **批次 ID**：`DW-20260905-01`（命题单 `docs/BATCH_PROPOSITION_DW-20260905-01.md` §5 代签＋追认位；窗令 `docs/DW_20260905_01_WINDOW_ORDER.md`）
- **授权链**：PO 令 2026-09-05 ← D-655 ← D-704②(b)；大脑自起草自开
- **格阵**（D-655 (4)，P2 两腿先行，同窗连续）：

| # | 格 | App | 形态 | 功能 | 轮 | 命题 |
|---|---|---|---|---|---|---|
| 1 | `wifi_f6` | 豆包 | WiFi | F6 图像生成 | 6 | P2 |
| 2 | `cell_f6` | 豆包 | 蜂窝 | F6 | 6 | P2 |

## 1. 采集参数（开窗前定死，逐格照抄）

```
python tools/e234/e234_collect.py --serial 8MY0221126002537 --pkg com.larus.nova --roi 400,1800,400,200 --allow-real-device --device-window DW-20260905-01 --session-seconds 700 --screencap-period-ms 1500 --framestats-period-s 1 --no-marks --out evidence/DW-20260905-01/<格名>
ANEB_SERIAL=8MY0221126002537 python tools/e234/drive_cell.py evidence/DW-20260905-01/<格名> 6 "Generate an image of a red circle on a white background." 75 20
```

驱动器哈希（A-1 四件后）：见各格 README 与 §3。驱动器逐轮实际值落 `<格名>_driver_timing.jsonl`（包级）。

## 2. 前置实况（开窗时逐条填）

- P40 五步、P1a（`ps -A` 匹配 aneb 恰一行）、通道 A（D-705）、构建对应（ctree `lastUpdateTime=2026-09-04 09:02:32`）、豆包版本、制式 pre/post、路由 pre/post——由各格 `orchestrator.log` 与 README 记。

## 3. 逐格结果（收窗时填）

（每格一行：退出码／步 1a·1c·4b 判词／`e2_precheck` 状态／驱动器哈希）

## 4. 口径与不回答什么

- 自然对照版（无整形），不得读成受控档结论；四态 `PASS / FAIL / NOT_EXECUTED / BLOCKED_EXTERNAL`；判读以 `e2_precheck` 退出码为权威信号。
- 命题单 §4 照录。

## 5. 收窗（收窗时填）
