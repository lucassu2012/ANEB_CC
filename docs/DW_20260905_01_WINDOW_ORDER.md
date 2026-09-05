# DW-20260905-01 战役窗令（**P2 两腿先行批 · 大脑自起草，D-655 授权链**）

> **激活记录**：2026-09-05 由大脑按 PO 令 09-05「按 D-655 授权链自起草新单并开窗跑 P2 两腿」激活；命题单 `docs/BATCH_PROPOSITION_DW-20260905-01.md`（§5 授权链与追认位）。
> 本令只做「已裁定事项的集成」，逐条挂锚；与命题单／操作卡 v2 冲突时以两者为准并当场入册。

## 一、激活条件（缺一不开窗）

| # | 条件 | 判据 | 现态 | 锚 |
|---|---|---|---|---|
| P0 | 通道 A 功能验证通过 | 开一次豆包看 `ADAPTER_EVT`，不信 settings 读回 | **✅ 09-05 20:17 `ADAPTER_EVT=14`，Bound=1，服务组件＝`com.aneb.probe.ctree/…AnebAccessibilityService`** | D-705；D-611③④ |
| P1 | 命题单 §5 锁定 | 新批次 ID＋授权链＋追认位 | **✅ 本单 §5（代签，追认位开）** | D-655；D-704②(b) |
| P2 | 构建对应性成立 | 只认 `lastUpdateTime`（禁 versionName）；对象＝**`com.aneb.probe.ctree`** | **✅ `2026-09-04 09:02:32`（sha256 `f7a31a4b…`，D-703①）** | D-581（对象换包名，M-B-008②） |
| P3 | 驱动器身份可记 | 本窗驱动器＝`tools/e234/drive_cell.py`@**`99d07b2`**（A-1 四件：pin_console 首条语句／focus 精确匹配＋Awake／`-s SERIAL`＋单引号包裹／prompt isascii＋首行落盘）；每格 README 记哈希 | **✅ A-1 已合入 `99d07b2`（e234 reflex 130/130，15 突变全 CAUGHT）** | REVIEW §7.1 A-1；D-621③ |
| P4 | DeepSeek 额度试水 | 仅 DeepSeek 格前做 | **本批 P2 两腿不涉，顺延** | D-622② |
| P5 | 操作卡对版 | `DW_NEXT_OPERATOR_CARD_v2_DRAFT_20260830.md` ＋ P1a（`a14bb40`） | **✅** | D-653③ |
| P6 | 设备实况干净（P40 五步）＋ P1a | `ps -A` 匹配 aneb **恰一行**（即 ctree 的无障碍服务进程）；无 VPN tun；桌面焦点 | 开窗时逐条跑并写进格 README | 根 CLAUDE.md；D-704④ |

## 二、格阵与参数（承 D-655 (4)，参数照抄上窗健康格 `wifi_f6`／`cell_f6`）

| 格 | 条件 | 功能 | 轮 | 答窗＋静置 | 提示词（G-2 定稿） |
|---|---|---|---|---|---|
| 1 | WiFi | F6 图像生成 | 6 | 75s ＋ 20s | `Generate an image of a red circle on a white background.` |
| 2 | 蜂窝 | F6 图像生成 | 6 | 75s ＋ 20s | 同上（同功能两条件**必须同参**，命题单 §1c） |

采集器：`e234_collect.py --serial 8MY0221126002537 --pkg com.larus.nova --roi 400,1800,400,200 --allow-real-device --device-window DW-20260905-01 --session-seconds 700 --screencap-period-ms 1500 --framestats-period-s 1 --no-marks --out evidence/DW-20260905-01/<格名>`；
驱动器：`ANEB_SERIAL=8MY0221126002537 python tools/e234/drive_cell.py evidence/DW-20260905-01/<格名> 6 "<提示词>" 75 20`（A-1 后形态）。
**每格必做**：开跑前/跑完后各读一次 `gsm.network.type`；切网后 `ip route get 120.79.148.0` 核实生效（禁 dumpsys connectivity）；步 1a/1c（操作卡）；`e2_precheck` 退出码为权威信号；每格 README 记驱动器哈希（P3）。

## 三、停窗规则

D-643 版（D-655 (2) 统一）：第二次机械性滑落＝停下报裁；第三次（任意侧）＝无条件收窗。第 3 格以后（DeepSeek）本批不排。

## 四、本窗不回答什么

命题单 §4 照录；另：本窗为**自然对照版**（无整形，E-2 段 B 未落），不得读成「网络诉求」的受控档结论。
