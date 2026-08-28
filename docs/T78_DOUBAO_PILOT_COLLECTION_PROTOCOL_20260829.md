# T78 豆包先行批 · 采集操作协议（E-1 解锁即用）

> 属主：v2 会话（61bd2401）· 2026-08-29 · 板号 **T78** · 仿 [`T50_VOICE_FIRST_COLLECTION_PROTOCOL_20260804.md`](T50_VOICE_FIRST_COLLECTION_PROTOCOL_20260804.md) 四段形状
> **适用范围**：仅**先行批**（基线 + WiFi/蜂窝自然对照，只卡 E-1）。L3 整形批（批 D/G/A）另需 E-2/E-3，不走本协议。
> **规模与工时**：60 轮 = 6 功能 × 2 条件 × 每格 N≥5，≈2 小时 ≈ 0.5 设备窗——推导见 [`DOUBAO_NETPERF_CAMPAIGN_PLAN_20260824.md`](DOUBAO_NETPERF_CAMPAIGN_PLAN_20260824.md) §10。
> **红线**：观察 only（绝不 `performAction`、绝不代启动 App，D-385/D-49）；不解密不 MITM（D-24/D-61）；额度与频次最小化（D-386）。

---

## ① 前提核查清单（任一不满足则不开窗——避免开窗即空跑，D-481 先例）

### A. E-1 设备可达且已解锁（本批唯一硬阻塞）
```
adb devices
adb shell dumpsys window | findstr mDreamingLockscreen
```
- `adb devices` 为空 = 设备离线（USB 未连或关机），**比屏锁更前一步**；
- `mDreamingLockscreen=true` = 真锁（PIN/图案），**swipe 不解**，须在场者物理解锁（D-481 同款）。

> **🔴 实况（2026-08-29 本会话只读亲验，未唤醒未改状态）**：
> `adb devices` → `8MY0221126002537 device`（**已在线**）、`ro.product.model` → `ELS-AN00`（确认 P40）；
> `mAwake=false / mScreenOnFully=false / mDreamingLockscreen=true`（**屏灭且锁着**）；
> `mCurrentFocus=NotificationShade` + `mFocusedApp=华为桌面`。
> **⇒ E-1 已从两阶阻塞（离线＋锁屏）降为一阶（仅锁屏）**——一页清 #4 记的「`adb devices` 为空、
> 完全离线」**已过期**，**PO 的到场动作从「连 USB ＋ 解锁」减为「解锁」一件**。
> **`NotificationShade` 不是通知栏被拉下**：按 **D-393** 教训它是**屏灭锁屏的表征**，
> 而 `mFocusedApp=华为桌面` 证明**除锁屏外设备是干净的**（无残留应用），符合开测前提。

### B. 观察通道三件（A/B/D）各自可用
| 通道 | 核查动作 | 不满足的后果 |
|---|---|---|
| **A** 无障碍事件流 | `AnebAccessibilityService` 已启用且**已重绑**；**事件流单会话不碎段**；**豆包 14.7.0 仍是 View 系**（判据见 §1.D） | 主通道（TTFT/cadence/RCT）无数据 |
| **B** `screencap` ROI 帧差 | 现场量出豆包响应区 ROI（`x,y,w,h`）——`e234_collect.py --roi` **必填无默认值**；**量法与两帧自检见 §1.G**（框在静态区不报错，是无声失败） | 交叉验证缺失；⚠ B 采样 ~2–3.5s/帧（E1 实测），**只作粗验、不能判 1 帧级** |
| **D** PCAPdroid 免解密抓包 | 已授 VPN、只读方向字节 | F3/F4 上行诉求**失去证据源**（这是本批最强的一块） |

> **🔵 锁屏下已预验的三条（2026-08-29 只读，开窗时不必重做，直接省窗内时间）**：
> | 前置 | 实测 | 结论 |
> |---|---|---|
> | a11y 服务已启用 | `enabled_accessibility_services` = `com.aneb.probe/…AnebAccessibilityService`；`accessibility_enabled` = `1` | ✅ **已启用**（⚠「**已重绑**」仍须解锁后确认——重绑是解锁态动作） |
> | 豆包版本 | `dumpsys package com.larus.nova` → `versionName=14.7.0` | ✅ **14.7.0 在位**（与方案记载一致；⚠ 版本漂的**真实风险不在正则**——本文 v1.1 订正，见 §1.D） |
> | deviceidle 白名单 | `dumpsys deviceidle whitelist` → `user,com.aneb.probe,10306` | ✅ **探针在白名单**（豆包是被观察方，不需入白名单） |
>
> **🔵 同批只读验掉的另四项（开窗资源前提，2026-08-29）**：
> | 项 | 实测 | 结论 |
> |---|---|---|
> | **通道 D 的 PCAPdroid** | `pm list packages` → `com.emanuelef.remote_capture` | ✅ **已装**——F3/F4 上行诉求的**唯一证据源**在位 |
> | 电量 / 温度 | `level=81`、`temperature=250`（25.0℃）、`status=4` | ✅ 跑 ≈2 小时够用 |
> | 存储 | `/data` 可用 **208 GB**（14% 使用） | ✅ 60 轮产物 + 抓包绰绰有余 |
> | 当前 IME | `default_input_method` = `com.baidu.input_huawei/.ImeService` | ✅ **豁免逻辑认得它**（见下） |
>
> **⚠ 由 IME 这项牵出「a11y 必须重绑」的真正理由（不是形式要求）**：
> `AnebAccessibilityService` 的豁免取 `default_input_method` 再 `substringBefore('/')`
> → `com.baidu.input_huawei`，与实测一致，**豁免会生效**。**但 `imePkg` 只在
> `onServiceConnected()` 读一次**：若 IME 在服务绑定之后被换过，豁免就指向旧值、
> **D-51 的会话碎段复现**（D-51 实证：百度输入法的 STATE 与候选栏 CONTENT/TEXT 事件把
> 观察切成 8/1/8 三段；修复＝IME 包全事件豁免，实证 DeepSeek 单会话 `events=108`）。
> **故 ①B 的「已重绑」不是走过场——它是让 IME 豁免重新取值的唯一途径。**
>
> **⚠ 本文 v1.1 订正（我引错了症状）**：v1.0 此处写「碎段导致 `ttft_send_ms` 恒 null」。
> 查 D-51/D-52 后更正——`ttft_send_ms` 在豆包上**与 IME 无关地恒 null**（v1 input-clear
> 因发送后容器重建不发 TEXT_CHANGED 而失效；v2 点击锚点因**豆包自定义 View 零 CLICKED 事件**
> 被 D-52 真机证伪）。**碎段今天真正污染的是 `ttft_cluster_ms` 与 `cadence`**——即本批的核心量，
> 因为 v3 簇分割靠「>400ms 静默」切簇，**碎段会把一次问答切成多个会话、簇结构失真**。
> 结论方向不变（重绑仍是硬前提），但**代价比 v1.0 说的更大，不是更小**。

> **仍须解锁后才能做的四条**：①a11y **重绑**；②**UI 栈判定**（豆包 14.7.0 是否仍 View 系——
> **本批最大风险项**，判据与做法见 §1.D）；③IME/systemui 豁免核实；④**ROI 现场量**
> （`--roi` 必填无默认值）。
> **开窗第一件做 ②**：它若失败，后续 60 轮的核心量全部失真，且修复时间挪不出窗外。

### C. OEM 系统侧五条前置（`INSTRUMENTATION_SPEC` §5.3；任一不满足则数据不得入库）
deviceidle 白名单已加 · IME/systemui 已豁免 · a11y 服务已重绑 · 诊断日志走 `Log.i` · **UI 栈判定为 View 系且事件流不碎段**（§1.D）。
> 这五条的共同形状是「**失败时静默出错值或静默无数据而不报错**」（D-386）——所以必须**开窗前逐条核**，不能事后看数据像不像。

### D. 版本漂风险订正（v1.1，2026-08-29；**推翻本文 v1.0 的风险排序**）

**v1.0 写的**：「节点正则是对 14.4.0 写的、已漂 3 版，重验是最大风险项」。**查代码与决策日志后，这个定性是错的。**

**实据三条（可逐条复核）**：

| # | 事实 | 出处 |
|---|---|---|
| 1 | **运行时只编译 `class_name` 正则**，`view_id_regex` 存而不评估（取 `getSource` 跨进程开销，R-16／D-49 偏离 2） | `AnebAccessibilityService.kt:58`（注释）与 `:65/:69/:72`（三处 `toRegexSafe()` 全是 `classNameRegex`）；`AdapterSpec.kt:198` |
| 2 | 被评估的两条都是**框架类名**，不含 App 版本特征：input＝`android\.widget\.EditText`，response＝`android\.widget\.TextView\|androidx\.recyclerview\.widget\.RecyclerView`。**唯二含 `com.larus.nova:id/…` 的是 view_id，恰好不评估** | `spec/adapters/doubao.json` |
| 3 | **本批核心量不依赖任何正则**：`ttft_ui_ms` 来自 **v3 簇分割**，D-52 逐字「**纯时戳结构法，不依赖任何锚点事件**」；response 侧 `ruleMatch()` 只做**标注计数、非闸门**（漂了掉 `rule_matched` 计数，不丢数据） | D-52；`AnebAccessibilityService.kt:41`、`:77-87` |

**故正则漂移的真实后果**＝`rule_matched` 计数下降，**不是数据缺失**。判读时按 D-50 基线对照即可：首份实测 `events=28 rule_matched=26`（≈93%）。

**真正的版本漂风险是另一件事——UI 栈迁移**：豆包若从 View 系迁到 Compose，按 **D-51 实证**（DeepSeek＝Compose）事件会**同帧突发合流**，`cadence_p50` 从豆包 View 系的 ~100ms **塌到 0.2–0.4ms**，而 v3 簇分割的 >400ms 静默判据建立在逐帧节奏之上——**簇结构随之失真，核心量作废**。D-51 同时记着「两栈打点口径**不可互比**」，故这不是精度问题而是**口径问题**。

**开窗第一件事的判据（一轮问答即可判，无需跑满）**：手动开豆包问一句，读 `ADAPTER_OBS` 的 `cadence_p50_ms`。

| 读到 | 判定 | 动作 |
|---|---|---|
| 落 **99–112ms** 带（D-51/D-52 累计 8 轮 99.4–111.6） | ✅ 仍 View 系 | 照 §2 开跑 |
| **< 5ms** | ❌ 已迁 Compose | **停本批**。核心量口径变更，须先重定簇判据——**这是窗内不可压缩项，不要硬跑** |
| 介于两者之间 | ⚠ 不明 | 记录原值、按 §4 中止判据处理，不自行解释 |

**⚠ 别踩的坑之二：`doubao.json` 的 `package_note` 有一句与文件自身矛盾**。它（D-405，2026-08-02 过渡标注）写着「**三条节点规则本就全 PENDING-VALIDATION（正则全 null、宿主走 generic 兜底、规则不作打点闸门）**」。**四份适配器并排数过，这句对豆包是假的**：

| 适配器 | `input_node` / `response_node` / `send_button` 的 status | 「正则全 null」 |
|---|---|---|
| kimi、tongyi | 三段全 `PENDING-VALIDATION` | ✅ **真** |
| **doubao** | `VALIDATED` / `VALIDATED-PARTIAL` / `PENDING-VALIDATION` | ❌ **假**——前两段各带 `view_id`+`class_name` 两条 |
| deepseek | `VALIDATED-PARTIAL` / `PENDING` / `PENDING` | ❌ 部分假（两段各带 `class_name`） |

那句对 kimi/tongyi 成立，却被写进了**唯二有已验证正则**的两份。**结论「只标注不停用」仍对，但理由是 §1.D 实据 1–3（只评估框架类名 + 核心量不经正则），不是「正则全 null」**——按 D-405 自己的话，「**一条经不起查的理由比没有理由更糟**」。开窗时**别照那句去推断适配器跑在 generic 兜底**：D-50 基线 `ADAPTER_OBS mode=doubao events=28 rule_matched=26` 证明它跑在规格模式且规则在匹配。

**⚠ 别踩的坑之一（会白烧窗内时间）**：`spec/adapters/doubao.json` 的 `send_button.note` 写着「发送按钮特征**待**真机 `ADAPTER_EVT` 诊断日志反推回填」。**这条诊断 D-52 已经跑过并证伪**——豆包自定义 View **零 `TYPE_VIEW_CLICKED` 事件**，点击锚点路线对豆包不可用（四正则留 null 是**有意保留能力**给标准控件 App，不是待办）。**不要照那句注记再跑一遍。**（spec 注记本身是双侧严格解析文件，按 D-387 不在本批顺手改，已报大脑。）

### E. e234 装置的设备红线（会挡住你，别现场才发现）
`e234_collect.py` 对 P40（`ELS-*` denylist）**必须**给 `--device-window <ID>`，且该 ID 须能在 `docs/BRAIN_TASKBOARD.md` 查到。
→ **开窗前先在板面登记 DW 号**（`DW-YYYYMMDD-NN`），否则脚本拒跑。
> **这道门实际验的是什么（2026-08-29 实证六案，非文档转述）**：`device_gate()` 用 **纯子串匹配**（`device_window not in taskboard_text`，读整个板面文件）——**验的是「这串字符在板面出现过」，不是「这个窗是给这次采集的、且现在有效」**。实测：已撤销的窗号（板面写着"该窗已撤销"）、别人任务的窗号、以及被另一个号包含的前缀（板上 `DW-…-011` 而你给 `DW-…-01`）**三种都放行**。
> **大脑 08-29 裁定（三种分开处置）**：**「前缀包含」修**——纯技术漏洞，改词边界匹配一行修、零措辞依赖、不引新假拒面，施工并入 v3 在飞的那笔；**「撤销窗 / 别人窗」不修**——甄别只能靠板面措辞，那是新的假拒来源，而**授权强度本来自「人要先去板上登记」这个动作与事后可查，不来自字符串校验的严密度**。故下面这条对操作者的意义**长期有效**。
> **对操作者的意义**：门拦得住「凭记忆瞎写一个号」，但**拦不住你用错号**——所以登记时用**当天当次的新号**，别复用旧号，也别指望门帮你发现拿错了窗（大脑 08-29 裁 7-5=案 A 时已知悉此实况）。

### F. 额度上限预检（本协议新增，方案 §10.4 点名）
- 豆包免费档**轮次上限未核**；60 轮有触顶风险。
- **开窗第一件事**：先跑 3 轮试水，确认无限流提示再进正式批；**触顶即停并如实记录已完成格数**，不换账号（账号是用户资源，D-49）。


### G. ROI 现场量的最小动作（窗内约 2 分钟；`--roi` 必填无默认值）

**设备几何（2026-08-29 锁屏下只读实测，开窗时不必重测）**

| 项 | 值 | 来源 |
|---|---|---|
| 物理分辨率 | **1200 × 2640** | `adb shell wm size` |
| 密度 | 530 dpi | `adb shell wm density` |
| 旋转 | `ROTATION_0`（竖屏） | `dumpsys window` |
| 状态栏高 | **154 px**（`mAppBounds=Rect(0, 154 - 1200, 2640)`） | 同上 |

**格式与校验**（`tools/e234/e234_collect.py` 的 `parse_roi`，逐条对着源码）

- 写法 `x,y,w,h`，**四个非负整数**；`w`/`h` 必须为正，否则报**人话错误不是栈回溯**。
- 边界自检：`x+w` 不超过 1200、`y+h` 不超过 2640。完全越界时 `roi_mean_from_raw` 返回 `None`（**这一种不会静默**）。

**⚠ 真正的危险不是打错，是格式打对却框在静态区**。`parse_roi` 的 docstring 逐字：
「**猜一个坐标出来会让通道 B 安静地测一块空白**（选错层不报错那件事的同款形状）」。
框在留白／标题栏／输入框上时，`roi_mean` 每帧都是一个**像样但永不变**的数，
`--screencap-period-ms` 照常采样、脚本照常成功、产物照常落盘——**没有任何一处会报错**。

**故量完必须做这一步自检（两帧对照，能当场证伪）**：

1. 对话页静止（无回复流动）时取一帧：`adb exec-out screencap > roi_idle.raw`
2. 让豆包出一段回复，**流式呈现进行中**再取一帧：`adb exec-out screencap > roi_busy.raw`
3. 用同一组 `x,y,w,h` 各算一次灰度均值，**两个数必须明显不同**。
   相等或只差末位小数则 **ROI 框在静态区，作废重量**，不要开跑。

```python
# 存成 roi_check.py 再跑（注意：别用 python -c，PS 内联多行/含引号会吞字）
import sys
sys.path.insert(0, 'tools/e1')
import e1_collect as e1
x, y, w, h = 0, 0, 0, 0                      # <- 填你量到的 ROI
for name in ('roi_idle.raw', 'roi_busy.raw'):
    print(name, e1.roi_mean_from_raw(open(name, 'rb').read(), x, y, w, h))
```

> **本节不给候选矩形**：响应区位置是「这台设备这个 App 这一版」的一次实测，
> 我在窗外量不到；按 `parse_roi` 自己的理由，**给一个没量过的坐标比不给更危险**——
> 它会让人跳过上面这步自检。**R-10 同精神：没测到就是没测到，不猜。**
---

## ② 执行顺序（本协议的核心设计点：抗时序混淆 vs 省切换时间）

**问题**：12 格 = 6 功能 × 2 条件。若按条件分组（先 WiFi 全 6 功能 30 轮、再切蜂窝 30 轮），
**只需 1 次网络切换**、最省时；但那样 **WiFi 批全在前、蜂窝批全在后**——期间若服务端负载、
网络状态或账号限流发生漂移，**「条件差」与「时段差」不可分离**。

> 这正是 **D-393** 记下的形状：当年拿 07-31 下午（NR/异出口）比 07-31 闲时（LTE/本出口），
> 把制式与出口的差异读成了时段差异；后来四个同出口窗横跨早晚高峰实测 RTT 极差仅 1.18ms，
> 时段解释因此被否定。**先行批只有 2 个条件、每格又只有 N=5，最经不起这种混淆。**

**定案：分块交替（4 块）**，每块 3 个功能：

| 块 | 条件 | 功能 | 轮数 | 累计切换 |
|---|---|---|---|---|
| 1 | WiFi | F1 文本 / F2 深度思考 / F3 识图 | 15 | 0 |
| 2 | 蜂窝 | F1 / F2 / F3 | 15 | 1 |
| 3 | 蜂窝 | F4 文件 / F5 联网搜索 / F6 图像生成 | 15 | 1（同条件续跑） |
| 4 | WiFi | F4 / F5 / F6 | 15 | 2 |

- **切换次数 = 2**（不是 §10 估算的 6，工时略优于估算，**不改结论**）；
- **每个功能的两个条件相隔不超过一块**（≈30 分钟），把漂移窗口压到最小；
- **每格必记时间戳**（见 ③）——事后可用它检验「块 1 的 WiFi」与「块 4 的 WiFi」是否一致：
  **两块同条件的读数若显著不同，说明期间有漂移，条件对照本身要打折**。这是本协议留的自检钩子。

**采集命令**（每格一次会话；参数照 `tools/e234/e234_collect.py`）：
```
python tools/e234/e234_collect.py --serial <SN> --pkg com.larus.nova --roi <x,y,w,h> --allow-real-device --device-window DW-YYYYMMDD-NN --out evidence/doubao_wave0_<日期>/<条件>_<功能>_r<轮次>
```
> 通道 D（PCAPdroid）与上述**并行**手动起停，其产物单独归档（脚本不管抓包）。

---

## ③ 产物与判读入口

**落点**：`evidence/doubao_wave0_<日期>/`
> **目录名以 SPEC-2 任务书 §2.1 的验收判据为准**（原写 `doubao_pilot_`，2026-08-29 自查发现与任务书不一致——**验收时目录名对不上就是没达标**，已统一为 `doubao_wave0_`）。
```
<条件>_<功能>_r<轮次>/     每格每轮一目录（脚本 --out）
  adapter.log            通道 A 事件流（TTFT/cadence/RCT 的原料）
  screencap_index.jsonl  通道 B 帧差标量
  collect_notes.json     采集元数据（含时间戳——②的自检钩子靠它）
  pcapdroid/             通道 D 抓包（手动归档，只留方向字节统计，不留载荷）
README.md                  战役说明：格阵、执行顺序实况、每格时间戳、偏离记录
```

**⚠ 战役标识：本批不用 `campaign_id`，而用目录名 + README（与 SPEC-2 §2.1 字面的差异，已核清）**

SPEC-2 §2.1 的验收判据写「首批语料落库（**独立 `campaign_id`**）」——**该字段对本批不适用**，理由是机制层面的：
- `campaign_id` 是 **ANEB probe 的 wire 语料字段**（`run.campaign.campaign_id`，见 `CAMPAIGN_LABELS_CONVENTION.md`），
  缺失即归 `unlabeled` 桶；
- 但**豆包先行批走观察通道**（A 无障碍 / B 帧差 / D 抓包），产物是 `adapter.log` / `screencap_index.jsonl` / pcap，
  **不是 wire 语料**——`tools/e234/e234_collect.py` 全文无 `campaign`/`label` 参数，其 README 亦实测
  「把 dry-run 的 `screencap_index.jsonl` 喂 `scripts/validate_results.py` → **exit 1，contract VIOLATIONS**」，
  即这批产物**结构上就进不了 wire 语料池**，自然也没有那个字段可填。
- **本批的战役标识因此落在两处**：**目录名** `evidence/doubao_wave0_<日期>/` 与 **README 首行**（写明批次、条件、格阵、时间窗）。
  验收时以这两处认定「独立批次」，**不以 wire 的 `campaign_id` 认定**。
- ⚠ **反过来的红线仍在**：本批产物**不得**被塞进 wire 语料池或与 ANEB 自有 run 混池——两者口径完全不同
  （ui-proxy vs 网络层），混池即违 §③ 判读口径与铁律 3。

**⚠ 先行批实际能产出什么（本批的产出承诺边界，2026-08-29 审 §3 后补）**

方案 §9 把先行批描述为测「UI-TTFT / cadence / **RCT** 与多模态上行字节」，但按 §3 指标表逐条核，**其中两项带未解阻的前提**：

| 指标 | 本批能否产出 | 依据 |
|---|---|---|
| **TTFT_ui**（A0′→A2） | ✅ **能** | 通道 A 主判据现成；⚠ 起点是 **A0′（气泡上屏）非 A0（点击发送）**，两者差一个**从未测量过**的量（待 E3），转述时不得说成「按下发送到看见首字」 |
| **cadence_ui**（A3 间隔） | ✅ **能** | 同上；口径＝**节奏代理，非网络 ITL** |
| **上行字节 / upload_ms** | ✅ **能**（通道 D） | 免解密只读方向字节；**网络传输层口径，绝不与 UI 口径相减**（跨口径红线） |
| **RCT**（A4−A0′） | ⚠ **不能，或只能给未标定的临时值** | **A4 判据三级（C-1/C-2/C-3）全 `NOT_EXECUTED`**，`T_quiet` 待 **E4** 标定（`INSTRUMENTATION_SPEC` §1.5）。**E4 恰是本协议 #7 那批、尚未跑** |
| **stall 代理** | ⚠ **阈值未标定** | §3 原文：「阈待标定；原文用 ≥1s，**本战役阈需在豆包 cadence 分布上重定**」。**本批可先采分布、不下 stall 判定** |

**执行时照此办**：①**RCT 与 stall 不作为本批的承诺产出**——采到的原始事件流照常归档，判读页里**如实写「A4/阈值未解阻，本批不给 RCT 与 stall 结论」**；②若开窗时 E4 已跑出 `T_quiet`，再回头用本批录轨补算（事件流已存，不必重采）；③**绝不用一个临时拍的阈值凑出 RCT/stall 数字**——那正是「有数字比没数字更危险」的形状。

**判读口径（R-10 与红线）**：
- 所有 UI 侧指标恒标 **ui-proxy 口径，≠ 网络 ITL/TTFT**，`confidence ≤ LOW`（`INSTRUMENTATION_SPEC` §4.4：G-5 未 PASS 前恒 LOW）；
- **N=5 是登记级下限**——产出**不给置信区间**，恒标 LOW/登记级（方案 §6.2）；
- 缺测记 `null` 不记 0（R-10）；某格没跑成就**如实少一格**，不用别的格补。

---

## ④ 中止判据表（别在设备旁边猜）

> **本表经与脚本实际拒绝路径逐条对照（2026-08-29 自查）**：`e234_collect.py` 的 `device_gate` 与 `parse_roi` 共 6 条拒绝/异常路径，**初版表漏了其中三类**（型号未知 fail-closed / 读不到任务板 / ROI 格式错），已补齐——**「我自己就是执行者」不能代替核对**。

| 观察到的形状 | 含义 | 处置 |
|---|---|---|
| `adb devices` 空 / `mDreamingLockscreen=true` | E-1 未解 | **不开窗**。如实记 BLOCKED_EXTERNAL，等在场者（D-481 先例：开窗即空跑是浪费） |
| 脚本报「型号命中 denylist 且无 `--device-window`」 | 板面未登记 DW 号 | 先登记再跑；**不要试图用 `--allow-real-device` 硬闯**（它绕不过 denylist，设计如此） |
| 脚本报「**型号未知 / 非模拟器无旗标**」 | **fail-closed**：`getprop` 读不到机型时一律拒（不是 denylist 那条，`--device-window` 救不了） | 先确认 `adb shell getprop ro.product.model` 有输出；读不到通常是设备未授权 USB 调试或掉线，回 ①A 重核 |
| 脚本报「**读不到任务板**」 | 与「查无此项」**不是同一回事**：这是板面文件本身读不到（路径/权限/编码） | 核 `docs/BRAIN_TASKBOARD.md` 是否存在且可读；**别急着改 DW 号**——号可能没错，是板读不到 |
| 脚本抛 `ROI 要写成 x,y,w,h 四个非负整数` / `ROI 的宽高必须为正` | ①B 现场量的 ROI 写错格式或量成了零宽高 | 重量一次：`adb shell wm size` 看分辨率，截图确认响应区像素范围；**四个数用英文逗号、无空格也可**（脚本容忍空格但不容忍缺项） |
| 豆包出现限流/额度提示 | 免费档触顶（①F 预检没挡住） | **立即停**，如实记录已完成格数与触顶轮次；**不换账号**（D-49） |
| 通道 A 无事件 | a11y 未重绑 / 进程被 iAware 冻结 / 豁免失效 | 停本批，记为前置未满足，不产出数据（**不要靠事后看数据像不像**，D-386） |
| `cadence_p50_ms` < 5ms | **豆包已迁 Compose**，v3 簇判据失效（§1.D） | 停本批。**本批最大风险项**；记原值与版本号，核心量口径须先重定，**不在窗内硬修** |
| `rule_matched / events` 显著低于 D-50 基线 26/28 | 节点正则对 14.7.0 漂了 | **不停批**——`ruleMatch` 是标注计数非闸门（§1.D 实据 3）。记录比值，产物照出，回填 spec 留下轮 |
| 通道 D 抓不到豆包流量 | VPN 未授或 App 走了未捕获通道 | F3/F4 的上行结论**不得给出**（失去唯一证据源）；F1/F2 的 UI 侧仍可继续 |
| 同一格 5 轮里 UI 读数跨度极大（如 TTFT 相差 >3×） | 可能撞上网络波动或服务端排队 | **如实记录全部 5 轮，不剔除异常值**（登记级本就该记录波动）；README 标注该格「跨度大，n=5 不足以分辨」 |
| 块 1 与块 4 的 WiFi 读数显著不同 | 期间有漂移（②的自检钩子响了） | **条件对照打折**：README 明写「WiFi 两块不一致，条件差与时段差不可分离」——**不要挑一块当代表** |
| 设备弹出任何需要授权的对话框 | 不应发生（本批观察 only、不 `performAction`） | 停止采集，核实是否误触发了注入路径，走 ①B 重核 |

---

## ⑤ 收窗动作（照根 `CLAUDE.md` 设备实况流程）

1. 停本次启动的一切应用/服务（含 PCAPdroid、a11y 观察）；
2. 恢复本次改动的临时设置（网络条件切回原值、`stayon` 等）；
3. 回华为桌面并**立即复验干净**（仅桌面可见但仍有后台/VPN/临时规则时，**不得称干净**）；
4. 产物落 `evidence/doubao_wave0_<日期>/` 并写 README（格阵实况 + 每格时间戳 + 全部偏离）；
5. 板面 T78 更新状态与证据路径，出 where-are-we 简报。
6. **窗后待办（D-578 裁「窗前不修、窗后修」）**：以**一次 `spec/adapters/doubao.json` + `app/probe/src/main/assets/spec_adapters/doubao.json` 同提交**修两条已成误导的 note——
   ①`send_button.note` 的「待真机 `ADAPTER_EVT` 诊断反推回填」（**D-52 已跑过并证伪**：豆包自定义 View 零 `TYPE_VIEW_CLICKED`；四正则留 null＝**有意保留能力**给标准控件 App）；
   ②`package_note` 的「三条节点规则本就全 `PENDING-VALIDATION`（正则全 null）」（**对本文件为假**：`input_node`=`VALIDATED`、`response_node`=`VALIDATED-PARTIAL`，各带两条正则；该句只对 kimi/tongyi 成立，deepseek 亦部分假——顺带核 deepseek 那份）。
   并定 `send_button` 的 `PENDING` 状态去留，跑 `validate_adapters.py` A3 + `AdapterSpecTest` + `verify_all` 后配 D 号收尾。执行方 v2 或 v3。
   > ⚠ **D-578 原文称本条「已列入协议窗后清单防漏」，实测当时 ⑤ 只有 5 条、并无此条**——那句是意图不是实况，现补齐（已回报大脑）。

---

*T78 先行批采集操作协议 · 2026-08-29 · 开窗前逐条核 ①，开窗后照 ② 跑，异常查 ④，收窗照 ⑤*
