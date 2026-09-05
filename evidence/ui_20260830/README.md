# T80/2.5 UI 视觉证据链 + L82「设备窗验手感」半项（2026-08-30）

> **仓内 UI 截图此前停在 07-14／07-18**（`evidence/phase3/ios_redesign/` 与 `ai_modes/`）。
> 本包补上 08-22 三件新特性的实况，并附一批现场手感发现。
> **口径**：本包只拍 **ANEB 自家 App**（`com.aneb.probe`），不含任何第三方 App 内容；
> 截图内无 SSID/BSSID（入库前逐张自查，状态栏只有运营商名）。

## 1. 构建与实据链（D-581）

| | |
|---|---|
| 装机前 | `lastUpdateTime=2026-08-20 11:17:40`，probe 进程已跑 **5 天 4 小时** |
| 装机后 | `lastUpdateTime=2026-08-30 16:20:30`（APK 构建于 2026-08-30 13:07） |
| **⚠ 两个构建 `versionName` 同为 `0.1.0-phase0`** | ⇒ **唯一判别量是 `lastUpdateTime`**，版本名分不出来 |
| 无障碍绑定 | **装机后存活，且功能验证过**——不是只看 `settings`，是实跑出 15 条 `ADAPTER_EVT` ＋ 1 条 `ADAPTER_OBS` |
| 安全设置 | **未改动任何一项** |

**D-581 三层重验（`03_d581_reverify.txt`）**：`adapter/` 自新 `lastUpdateTime` 起 **0 提交**；
四份 spec 与 assets 镜像**逐份同提交**；APK 内四份 adapter 资源与仓内 **md5 逐一相同**。
⇒ **新实据链对 `2026-08-30 16:20:30` 这个构建成立；下一次 T78 型采集窗开窗前不得再重装。**

## 2. 截图清单（2.5 四项全覆盖）

| 文件 | 覆盖 2.5 的哪一项 |
|---|---|
| `10_home.png` | **三模式屏** ＋ `LiveMetricStrip` 四型渲染（Token 体验屏） |
| `11_mode_basic_network.png` | 同上（网络基本性能屏） |
| `12_mode_ai_realtime.png` | 同上（AI 实时交互屏）——**填充蓝 vs 未填充灰肉眼可辨** |
| `20_history.png` | 历史列表（发现一的现场） |
| `30_result_simple.png` | **ResultScreen 简洁视图** |
| `31_result_pro.png` / `32_result_pro_kpi.png` | **ResultScreen 专业视图** ＋ **KPI 门限微刻度**（「卡顿线 200ms / 严重 1000ms」） |

## 3. 🔴 发现一：历史页把「TTFT 未测到」显示成「TTFT 0 ms」

**代码没有违反 R-10**——`HistoryScreen.kt:319` 逐字是 `?: "—"`，格式化那一层是对的。
**违反发生在回退链上**（`HistoryScreen.kt:317`）：`obs.ttftClusterMs ?: obs.firstDeltaMs?.toDouble()`。

**实测**（`evidence/doubao_wave0_20260830/` 十格 290 条 `ADAPTER_OBS`）：
`ttft_cluster_ms = null` 的有 **104 条**，这 104 条的 `first_delta_ms` 分布是 **全部为 0**。
⇒ **「TTFT 0 ms」在该批中恒等于「TTFT 未测到」。**

**而 `ttft_cluster_ms = null` 是一个合并 token**（同日查明，见该包 `FINDINGS_RAW.md` §0）：
可能是「没形成次簇」／「形成了但 >30s 被 `TTFT_CEILING_MS` 删掉」／「形成了但没播报」。
⇒ **一轮真实簇值 49470 ms 的记录，在屏上显示为 `TTFT 0 ms`。从 49 秒显示成 0 毫秒，方向还是「看起来最快」。**

**形状**：四个各自都站得住的决定合起来产生了它——①一个 `null` 承载三种成因；
②回退到 `firstDeltaMs` 是静默的；③`firstDeltaMs` 在「观察启动时 App 已在渲染」时恒为 0，而那是常态；
④标签仍写 `TTFT`。**没有任何一行代码写错，R-10 的目的（不显活的 0.0）却被绕过了。**
⇒ **R-10 这类红线管住了「格式化那一层」，管不住「回退那一层」。**

## 4. 发现二：简洁视图与专业视图对「这个分数可不可信」的呈现强度差很远

同一次 run（蜂窝 · quick · 08-20 07:47）：

- **简洁视图**（默认）：大绿表盘 **90 · 优秀** ＋「你的网络很适合 AI 助手——响应快、几乎不卡顿…」，
  免责句在**句尾括号**里：「（本次证据不完整，分数仅供参考）」；
- **专业视图**：顶部黄色 **参考** 徽章 ＋「低置信原因：3 个场景判定为低置信；
  KPI D1/T1/U1/U1_excl_slow_start 证据不足」，**逐项列出**。

⇒ **默认那一面把「不可信」压成一个括号，而它正是非专业读者会看的那一面。**
（同族：本仓已有的「摘要面才是被执行的那面」。）

## 5. 发现三／四（轻）

**三**：悬浮播放按钮**遮挡正文**，两屏可复现（`11` 底部磁贴被截、`12` 的「连续性 mini-run」段落被压）。
**四**：`SpeedTestScreen.kt` 的 `unit` 那个 `when` 没有「尚未开始」分支，落到 `else -> "Mbps 上行"`
⇒ 空闲屏同时出现「Mbps 上行」与「点击开始网络基本性能测速」。

## 6. 一条我自己报错又自纠的（保留，因为它本身是手感发现）

首屏底卡写「仿真节点 · E-01 / ELS-AN00 · **蜂窝网络**」，而设备当时在 **WiFi** 上。
我一度当成缺陷；查 `HomeScreen.kt:663` 后确认 `homeNetworkLabel(run)` 取的是**上一次 TestRun 的 transport**，
**代码正确**。⚠ **但那张卡没有任何时间标记、位置就在「开始」按钮正下方，读起来像在描述即将开始的这次测试**——
**读错的是我，当天读了一整天这个仓的人。**

---

## 7. 🔴 收窗时我把仪器关掉了（如实记，且它拦住下一个窗）

**收窗执行 `am force-stop com.aneb.probe` 之后**：

    enabled_accessibility_services = null
    accessibility_enabled          = 0
    dumpsys accessibility → Bound:{} Enabled:{} Crashed:{{com.aneb.probe/...AnebAccessibilityService}}

**而它在此之前是好的**（同包 `01_post_install.txt` / `02_service_functional.txt`）：
装机后 16:20:34 绑定在，16:21 **功能验证通过**——实跑出 15 条 `ADAPTER_EVT`。

⇒ **安卓把「被强停的无障碍服务」记为崩溃并整体禁用；`force-stop` 什么都不报。**
⚠ **不宣称观察到真崩溃**——`Crashed` 是安卓对强停的标签，两者在此分不开；**但因果时序明确**。

**根因在协议本身**：根 `CLAUDE.md` 的收窗流程写「停掉本次启动的一切应用/服务」。
对**豆包**执行它整天无害（豆包不提供无障碍服务）；**对自家探针执行同一条，就把通道 A 关了。**
⇒ **又一次「为守规矩而新增的那个步骤，自己越了另一条线」，而且这条是静默的。**
已把例外写进 `T78_DOUBAO_PILOT_COLLECTION_PROTOCOL_20260829.md` §⑤ 第 1 条。

**⛔ 当前状态：设备没有通道 A。** 恢复要写 `settings secure`（安全设置），**本会话不代做**。
需要人来办：设备上「设置 → 辅助功能 → 已下载的服务 → ANEB Probe → 开启」，
**或**由人执行 `settings put secure enabled_accessibility_services ...` ＋ `accessibility_enabled 1`。
**恢复后必须功能验证**（开一次被测 App 看有没有 `ADAPTER_EVT`）——**别只看 `settings` 读回来了**。

**⇒ 在有人恢复之前，别开任何需要通道 A 的窗**（T78 型采集、E1 真机窗、T88 装机后的验证）——**开了就是空跑。**
**⇒ 给 T88 的提醒**：**装机本身不破坏绑定**（本窗实证：装完还在）；**破坏它的是 `force-stop`**。
