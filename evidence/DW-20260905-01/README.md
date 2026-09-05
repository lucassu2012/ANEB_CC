# `DW-20260905-01` 证据包（P2 两腿先行批：豆包 × {WiFi, 蜂窝} × F6）

> 🔑 **目录名＝批次 ID**（承 wave1 README 首条教训「下一批目录名直接用批次 ID」）：`evidence/DW-20260905-01/` ⇔ 批次 `DW-20260905-01`。
> **状态**：已收窗（2026-09-05 21 时段）；两格 DONE，权威信号见 §5。

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

- **attempt1（21:06）前置 STOP，留痕 `wifi_f6_attempt1_preflight_stop/`**：编排先起采集器、后由驱动器开豆包 ⇒ 采集器开跑时挑不到该包图层，`sf_latency.txt` 17s 内 0→0 字节，步 1a 拦下（无轮次数据）。**真因＝操作卡步 1「先把被测 App 切到前台并出一屏画面，再起采集」**——历史 9 跑 7 次栽在此，本次第 8 次；编排已加环节 0b（开豆包→核 focus==PKG→再起采集）。

### 2.1 各格前置实况（由 `orchestrator.log` 生成，未手抄）

| 格 | P1a aneb 进程数（须 1） | 豆包 | 制式 pre → post | 路由 pre → post | 起采集前前台 | 编排 |
|---|---|---|---|---|---|---|
| `wifi_f6` | 1 (须=1) | versionName=14.9.0 | NR_SA,Unknown → NR_SA,Unknown | 1.1.1.1 via 10.10.0.1 dev wlan0 table 1040 src 10.10.7.37 uid 2000  → 1.1.1.1 via 10.10.0.1 dev wlan0 table 1040 src 10.10.7.37 uid 2000 | Window{423d7be u0 com.larus.nova/com.larus.home.impl.alias.AliasActivity1} | DONE |
| `cell_f6` | 1 (须=1) | versionName=14.9.0 | NR_SA,Unknown → NR_SA,Unknown | 1.1.1.1 via 10.121.106.242 dev rmnet0 table 1008 src 10.121.106.242 uid 2000  → 1.1.1.1 via 10.121.106.242 dev rmnet0 table 1008 src 10.121.106.242 uid 2000 | Window{30627f8 u0 com.larus.nova/com.larus.home.impl.alias.AliasActivity1} | DONE |

## 3. 逐格结果（收窗时填；由产物生成）

| 格 | 退出码 | 步 1a／1c | 步 4b（`e2_analyze`） | `e2_precheck` 终态（权威信号） | 驱动器哈希 | 驱动器实际值（`<格>_driver_timing.jsonl`） |
|---|---|---|---|---|---|---|
| `wifi_f6` | driver=0 collector=0 | 1a `11736 -> 24324`；1c（2 分处）CANNOT_TELL - C 侧够了（已观测间隔 11 次），**但 A 侧只有 1/1 轮切得出次簇** < 5 ⇒… | E2 判词 FAIL（p99 15071.805ms > 1 帧 16.667ms（n=6））；通道 B PASS（跃迁 27）；clock_pin PASS；wall_to_boot PASS；turn_method operator-marks；turns 6；frames 6251 | **WORTH_RUNNING**（rc=0）：已观测间隔 36 次（>=5）、不可判间隔 0 不占多数，A 侧 6 轮可用 | `99d07b2` | 6 轮；答窗实际 75.01–75.05 s；静置实际 20.04–20.04 s |
| `cell_f6` | driver=0 collector=0 | 1a `11958 -> 24726`；1c（2 分处）CANNOT_TELL - C 侧够了（已观测间隔 10 次），**但 A 侧只有 1/1 轮切得出次簇** < 5 ⇒… | E2 判词 FAIL（p99 15252.698ms > 1 帧 16.667ms（n=6））；通道 B PASS（跃迁 37）；clock_pin PASS；wall_to_boot PASS；turn_method operator-marks；turns 6；frames 7334 | **WORTH_RUNNING**（rc=0）：已观测间隔 43 次（>=5）、不可判间隔 0 不占多数，A 侧 6 轮可用 | `99d07b2` | 6 轮；答窗实际 75.03–75.05 s；静置实际 20.00–20.04 s |
## 4. 口径与不回答什么

- 自然对照版（无整形），不得读成受控档结论；四态 `PASS / FAIL / NOT_EXECUTED / BLOCKED_EXTERNAL`；判读以 `e2_precheck` 退出码为权威信号。
- 命题单 §4 照录。

## 5. 收窗（2026-09-05 21 时段，大脑自开自收）

- **权威信号**：`e2_precheck` 退出码 0 且 WORTH_RUNNING 的格＝`wifi_f6`、`cell_f6`（2/2）；`e2_analyze` 判词与逐轮表见各格 `e2_report.md`。
- **E2 判词读法**：FAIL＝「A 事件与 C 帧簇在一帧内对齐」这一假设在该格被拒，**不是设备或网络的坏消息**；有符号分布见各格 `e2_report.md` §2（方向本身是信息，spec §2.1）。自然对照版，不读成受控档结论。
- **本窗新增的操作纠正**：采集器必须在被测 App 已在前台并出一屏后再起（attempt1 反了⇒`sf_latency` 0 字节，见 §2）；已固化为编排步 0b。
- **未回答**：两腿之间的差异是否由制式造成（n=6/格，自然对照，无整形）——留给命题单 §4；不在本包下判断。
- 设备复原：两格收尾均回到华为桌面、探针恰一进程、WiFi 回开（见各格 `orchestrator.log` 环节 6）。
