# DW-20260905-02 战役窗令（**DeepSeek 四格批 · 大脑自起草，D-655 授权链**）

> **激活记录**：2026-09-05 晚由大脑按 PO 令「继续自主运行，v4 追认后直接起 DeepSeek 四格」激活（v4 追认上一单 `3960617` 已合入 `8f4d4b0`）；命题单 `docs/BATCH_PROPOSITION_DW-20260905-02.md`（§5 授权链与追认位）。
> 本令只做「已裁定事项的集成」，逐条挂锚；与命题单／操作卡 v2 冲突时以两者为准并当场入册。

## 一、激活条件（缺一不开正式格）

| # | 条件 | 判据 | 现态 | 锚 |
|---|---|---|---|---|
| P0 | 通道 A 对 DeepSeek 有事件 | DeepSeek 规格 `input_node=VALIDATED-PARTIAL`、`response_node/send_button=PENDING-VALIDATION`（X6b）⇒ 不信规格，**在 P4 试水里实核 `adapter.log` 有 `pkg=com.deepseek.chat` 的内容事件** | **✅ 试水 F6/F2/F1 各 617/1396/228 条 `pkg=com.deepseek.chat` 内容事件** | D-705；X6b；D-579 |
| P1 | 命题单 §5 锁定 | 新批次 ID＋授权链＋追认位 | **✅ 已锁定 2026-09-06 00:4x（§5，追认位开）** | D-655；D-704②(b) |
| P2 | 构建对应性成立 | 只认 `lastUpdateTime`；对象＝**`com.aneb.probe.ctree`** | **✅ `2026-09-04 09:02:32`（sha256 `f7a31a4b…`，D-703①）**；DeepSeek 端 `2.2.2`／`lastUpdateTime=2026-07-19 15:02:06`（与 `spec/adapters/deepseek.json` 记载一致） | D-581 |
| P3 | 驱动器身份可记 | 本窗驱动器＝`tools/e234/drive_cell_ds.py`@**`99d07b2`**（drive_cell.py 的 DeepSeek 孪生，D-638①；A-1 四件同批）；每格 README 记哈希 | **✅ 与豆包驱动器同哈希** | D-638①；REVIEW §7.1 A-1 |
| P4 | **DeepSeek 三轮试水** | `evidence/DW-20260905-02/ds_trial_wifi/`，WiFi，1×F6＋1×F2＋1×F1，答四件（发送键／「+」开新对话／F6 是否短答／限流）；**不许拿豆包额度外推** | **✅ 00:19–00:44 跑完：发送键✓／「+」开新对话✓／F6 非短答（与 F2 同量级，照原案）／无限流；见命题单 §1b** | D-622②；D-637②；D-641④ |
| P5 | 操作卡对版 | `DW_NEXT_OPERATOR_CARD_v2_DRAFT_20260830.md` ＋ P1a（`a14bb40`）＋ **步 0b「App 先前台出一屏再起采集」**（DW-20260905-01 固化） | **✅** | D-653③；D-711 |
| P6 | 设备实况干净（P40 五步）＋ P1a | `ps -A` 匹配 aneb **恰一行**；无 VPN tun；桌面焦点 | 编排步 0 逐条跑并写进格 README | 根 CLAUDE.md；D-704④ |
| P7 | **DeepSeek 开关态** | 3／4 格：深度思考 ON＋智能搜索 OFF；5／6 格：双 OFF；每格开跑前设好、截图（仓外）自读核色、README 记 | **✅ 编排钩子每格重设并像素核对（am kill 后复位为双 ON，试水实测）** | D-641②；D-638② |

## 二、格阵与参数（承 D-655 (4)、T33 §3 第 3–6 格；**逐格交替 WiFi／蜂窝**，X1／D-622②）

| 格 | 条件 | 功能／开关 | 轮 | 答窗＋静置 | 提示词（逐字） |
|---|---|---|---|---|---|
| 试水 | WiFi | F6→F2→F1 各 1 轮；开关按各自功能 | 3 | 75+20／75+20／45+20 | 见下三句 |
| 3 | WiFi | F6（思考 ON＋搜索 OFF）；**D-637② 分支：F6 短答 ⇒ 改 F2** | 6 | 75s ＋ 20s | `Generate an image of a red circle on a white background.`（F2：`Think step by step and explain in detail: why is the square root of 2 irrational?`） |
| 4 | 蜂窝 | 同格 3（同功能两条件必须同参） | 6 | 75s ＋ 20s | 同格 3 |
| 5 | WiFi | F1（双 OFF） | 6 | 45s ＋ 20s（同豆包 `cell_f1b`） | `What is 5G in one sentence` |
| 6 | 蜂窝 | F1（双 OFF） | 6 | 45s ＋ 20s | 同格 5 |

采集器：`e234_collect.py --serial 8MY0221126002537 --pkg com.deepseek.chat --roi <试水实核值> --allow-real-device --device-window DW-20260905-02 --session-seconds <F6:700／F1:480／试水:420> --screencap-period-ms 1500 --framestats-period-s 1 --no-marks --out evidence/DW-20260905-02/<格名>`；
驱动器：`ANEB_SERIAL=8MY0221126002537 python tools/e234/drive_cell_ds.py evidence/DW-20260905-02/<格名> <轮> "<提示词>" <答窗> 20`。
**ROI**：`--roi` 无默认值，DeepSeek 响应区位置与豆包不同——试水先用 `400,1800,400,200` 起跑，**以通道 B `transitions_detected` 是否 >0 判 ROI 落对没落对**；落错即改并在正式格前定死，四格同 ROI。
**每格必做**：开跑前/跑完后各读一次 `gsm.network.type`；切网后 `ip route get 1.1.1.1` 核实生效；步 1a/1c；`e2_precheck` 退出码为权威信号；README 记驱动器哈希（P3）与开关态（P7）。

## 三、停窗规则

D-643 版（D-655 (2) 统一）：第二次机械性滑落＝停下报裁；第三次（任意侧）＝无条件收窗。**格 3 预期会「失败」（e2 判 `NOT_APPLICABLE`）——那是产出，不重跑**（X6）。

## 四、本窗不回答什么

命题单 §4 照录；本窗为**自然对照版**（无整形），不得读成「网络诉求」的受控档结论；不读答案内容，只读结构量。
