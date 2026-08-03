# T43 外场执行包（2026-08-04）

> 作者：v3 执行会话 · 2026-08-04 · 状态：**交付，供 PO 外场使用**
> 背景（大脑派单原话）：「扩展轮外场的瓶颈是 PO 的时间——把每个点位的操作成本压到
> 『走到、按卡、离开』。」本文件四节对应大脑派单的①②③④，互相独立，PO 可以只打印
> 需要的那一节。
> 依据来源：`docs/M2_CAMPAIGN_RUNBOOK.md` §0.6.1/§6（逐字摘录，命令未改写）、
> `docs/M3_EXPANSION_ROUND_RUNBOOK_ADDENDUM.md` §1/§3.1/§3.2/§4/§5（逐字摘录）、
> `evidence/nr_timeline_20260802/T37_E2_COLLECTION_PROTOCOL_20260803.md` ④（失败表
> 风格模板）、`docs/T33_GRID_PREP_20260803.md`（换名操作单/工时公式）、`CLAUDE.md`
> P40 实况流程、T42（`docs/BRAIN_TASKBOARD.md`，本文件撰写时正在跑的真实彩排批，
> 哨兵/campaign_id 命名照抄它的先例）。**本文件不新造任何命令——每一条都能在上面
> 某个既有文件里逐字找到出处**，新增的只是"把散落各处的命令按现场执行顺序重排"。

---

## 1. 每点位操作卡（到点→开采→自检→收尾，复制粘贴执行）

> ⚠ 下面的命令块假定 `adb` 已连上目标设备且只有一台（多台时每条命令自己加
> `-s <序列号>`）。**每一条命令都要看回显，不看回显等于没做**（D-349 原话）。

### 到点（第一件事，还没开始测就先做）

1. **设备状态检查**（确认干净，无残留会话）：
   ```
   adb shell dumpsys window | grep mFocusedApp
   ```
   应显示 `com.huawei.android.launcher`。不是这个 → 停，先按 `CLAUDE.md` 第 3 条协调，
   不得自行停掉不明会话。

2. **建哨兵**（照 T42 先例，防止和另一个执行方撞车）：
   ```
   echo "<日期>-<序号> · <你的身份> · 点位<点位名>×<运营商>×<忙闲>" > evidence/nr_timeline_20260802/DEVICE_BUSY
   ```
   若该文件已存在且不是你自己建的 → **停，先协调**，不得覆盖。收尾时删除（见下）。

3. **记原值 + 关 WiFi**（不关会导致蜂窝网被系统中途撕掉，实测第 28 秒死于
   `bound_network_lost`，D-349）：
   ```
   adb shell settings get global wifi_on     # 记下这个数字，收尾要恢复成它
   adb shell svc wifi disable
   adb shell "dumpsys connectivity | grep 'Active default network'"   # 确认蜂窝是默认网
   ```

4. **开实时 logcat 落盘**（另开一个窗口，全程挂着——环缓冲仅 256KiB，7 分钟后
   事后翻就什么都捞不到了）：
   ```
   adb logcat -c
   adb logcat -v time -s AnebProbe:I > campaign_logcat_<点位>_<运营商>_<忙闲>.txt
   ```

5. **预热轮**（PO 批复 D-366；先跑一轮丢弃的，把无线唤醒开销移出第一条计入 run）：
   - 用下面"开采"里同样的命令跑一轮 quick；
   - `RUN_END` 后**立刻在台账记下这条 `run_id`，标"预热丢弃"**；
   - 紧接着（**别超过 1 分钟**，射频回落了预热就白跑）开始跑计入的 n 轮。

### 开采

**quick 模式**（每格 16 次：1 预热 + 15 计入）：
```
adb shell am start -n com.aneb.probe/.ui.MainActivity \
  --es server <url> --ez autorun true \
  [--es transport cellular] [--es inject truncate:50]
```
不写 `--es mode` 时默认就是 quick，写 `--es mode quick` 也一样。

**forensic 模式**（仅当天被指定为"取证格"的点位才跑；每格 6 次：1 预热 + 5 计入）：
```
adb shell am start -n com.aneb.probe/.ui.MainActivity \
  --es server <url> --ez autorun true --es mode forensic \
  [--es transport cellular] [--es inject truncate:50]
```
- 一次 `am start` = 一条完整的 9 场景取证 run（3 场景 × 3 位次拉丁方 × 每格 5 轮设计）；
  **`scenario_order` 由 App 自动生成写入语料，操作者不需要手动排位次、不需要手动切
  profile 顺序**——只管按启动、等它跑完。
- 判完成：logcat 里看到 `RUN_END run_id=<id> status=completed` 和 `REPORT http=200`。
- 看到 `status=aborted:*`：**这轮没有上报，不进语料**，直接重跑（新 `run_id`，算新样本
  不是重复）——同时把这次中止记进台账（下面"收尾"的台账项）。

### 自检（每格测完、当天收工前各跑一次）

```
python validate_results.py <今天拉下来的counted.jsonl>
python coverage_matrix.py <quick子集.jsonl> --config docs/campaign_grid_shenzhen.json
python stability.py <quick子集.jsonl> --kpi t1_ttft_ms --plan
python stability.py <quick子集.jsonl> --kpi n1_rtt_p50_ms --plan
```

> ⚠ 后三条必须喂 **quick 子集**（`split_by_run_mode.py` 切出来的那份），不能喂全量——
> 取证 run 混进来会让"每格几个网络样本"这个数不再可读（彩排实测过这个坑）。

**若今天含取证格**，额外单独再跑一次（**不能和 quick 数据混在同一份报告里**，混了会
让"序位效应"判成误报的"单元混杂"）：
```
python campaign_report.py <forensic子集.jsonl> --md report_forensic.md --html report_forensic.html --csv tables_forensic --provenance provenance_forensic.json
python publish_check.py <forensic子集.jsonl>
```

任何一条命令 exit 非 0 或报告顶端出现红色「合成数据警告」→ **当场停，不要带病继续到下
一个点位**，联系大脑判断。

### 收尾（当天最后一轮跑完就做，别拖到出报告之后）

```
adb shell am force-stop com.aneb.probe          # 停掉本次起的 App
adb shell svc wifi enable                       # 恢复到点时记的原值
adb shell svc power stayon false                # 撤掉常亮
adb shell input keyevent KEYCODE_HOME            # 回桌面
rm evidence/nr_timeline_20260802/DEVICE_BUSY     # 删哨兵
```

**复验**（五条都要对上，缺一条不算收尾干净）：
```
adb shell "settings get global wifi_on"                        # 应回到到点时记的原值
adb shell "settings get global stay_on_while_plugged_in"       # 应为 0
adb shell "dumpsys window | grep mFocusedApp"                  # 应是 huawei…UniHomeLauncher
adb shell "dumpsys window policy | grep screenState"           # 屏灭时应是 SCREEN_STATE_OFF
adb shell "ps -A | grep -iE 'aneb|vpn|tcpdump' | grep -v grep" # 应无输出
```

**台账人工核对**（自动化核不了，只能靠人）：
- 每格记「完成 N / 尝试 M」，M>N 时写清楚原因（如 `bound_network_lost`）；
- 每格恰好 **1 条**标「预热丢弃」的 `run_id`，且确已排除出计入语料；
- （可选，非必需）出口 IP 交叉验证：设备联网状态下访问 `ifconfig.me` 一类查询页
  截图存证，与语料里 `server_observed_addr` 核对是否一致——出口 IP 本身已随语料
  自动落盘，这一步只是抽验，不是必须做的记录动作。

### 失败形状：现场能查的 vs 只能事后查的（分两张表，别混着看）

**表 A：现场能判断、当场就能处置的**（观察到什么形状 → 什么含义 → 怎么处置，
风格照 T37 协议④）：

| 观察到的形状 | 含义 | 处置 |
|---|---|---|
| `RUN_END ... status=aborted:bound_network_lost` | WiFi 没真关掉，或系统又把蜂窝网撕了 | 核对 `dumpsys connectivity` 确认蜂窝是默认网，重跑该轮（新 run_id） |
| `adb logcat -d` 翻不到任何一行 `AnebProbe` | 环缓冲已被刷屏冲掉，说明采集期间没开实时落盘 | 无法补救这一轮的 logcat；下一轮起务必开着实时落盘窗口 |
| 该等 60 秒/该间隔的地方几乎瞬间就过去了，或两条本该分开的日志时间戳完全相同 | 脚本文件缺 BOM 导致行被静默吞掉（D-449，watcher 脚本已修，若用的是旧副本会复现） | 停，核对脚本文件是否为修复后版本，不要凭"看起来在正常跑"继续 |
| 台账上某格漏了「预热丢弃」那一条 `run_id` | 预热轮没跑，或跑了但没记 | 现场补跑一轮预热丢弃轮再继续——**这条不能留到事后补救**，没预热的正式轮已经带着约 4% 冷启动残余混进语料 |
| `validate_results.py`/`publish_check.py` 任何一条 exit 非 0 或报告顶端红色合成数据警告 | 契约违规或数据混入彩排语料 | 当场停，别继续到下一个点位，联系大脑 |
| 收尾复验五条有任一条对不上 | 收尾没做干净（WiFi/常亮/哨兵未恢复） | 补做那一条，直到五条全部对上再离开 |

**表 B：现场无法判断，正常收尾即可——不代表数据一定没问题，如实标注**：

| 已知问题 | 为什么现场看不出来 | 该怎么办 |
|---|---|---|
| radio 归零（无线上下文字段永久 null/stale） | App 不崩溃、不报错、界面完全正常；采样在后台 1Hz 静默写库，不经过任何 UI；诊断日志需要 adb 连接才可见，不是屏幕上能读到的东西 | **不用现场判断，正常收尾**。屏幕全程常亮 ≠ 这轮 radio 数据一定正常，二者已知无必然关系（不要把"屏幕亮着"当作这个问题的信号）。留给分析层核对 |
| 序位偏倚 / 预热效应等统计层面的信号 | 需要一批数据算出来的统计量，单条 run 现场看不出规律 | 正常收尾，留给报告链（`campaign_report.py`）算 |

---

## 2. wave 拆分：wave-1 网格变体（不等 8 个点位名凑齐就能开跑）

**现状**：`docs/campaign_grid_shenzhen.json` 是完整 32 格（8 点位×2 运营商×2 忙闲）；
`docs/campaign_grid_shenzhen_wave1.json`（本次新增，见下）是一份**模板化的子集**——
文件里放了 3 个占位点位槽位，**PO 现场从中选定 2 或 3 个真实点位、删掉多余槽位**即可
直接使用，不用等全部 8 个名字都到位。

> **如实说明（技术边界）**：仓库里没有任何点位间地理位置/远近关系的数据——
> `campaign_grid_shenzhen.json` 只有 `point_id`/`carrier`/`time_band` 三个逻辑维度，
> 不含坐标或地址。**"选哪 2-3 个近点"这件事，代码或文档都给不出答案，必须由 PO
> 现场判断**（本节工作流已按此设计：网格文件与工时公式都不预设选哪几个点，只管
> "选定之后怎么算、怎么改名"）。

### 换名操作单（wave-1 专用，四处同改，照 T33 §1 的清单缩小范围）

| # | 位置 | 现状（占位） | wave-1 选定后怎么改 |
|---|---|---|---|
| 1 | `docs/campaign_grid_shenzhen_wave1.json` | `point_id` 数组 3 个 `PENDING-PO-01`/`02`/`03` | 若选 2 个近点，删掉第 3 个槽位；若选 3 个，全部替换为真名；**不要留占位、不要补假名** |
| 2 | 补注命令（现场逐点位打标实际敲的命令） | 模板：`python annotate_campaign.py raw/<真名>/*.jsonl --out-dir labeled --set campaign_id=m3-expansion-wave1 --set point_id=<真名> --set carrier=<ctcc\|cmcc> --set tier=metro --infer-time-band` | `<真名>` 与 `carrier` 按当次实际所测填入 |
| 3 | `docs/M3_EXPANSION_ROUND_RUNBOOK_ADDENDUM.md` §6 | "所有点位一律记为 `PENDING-PO-01`…`08`" | wave-1 落地时，在该节**追加**一行"wave-1 已用点位：&lt;列出真名&gt;（本节其余占位部分照旧，待剩余点位到位后再改）"，不删除原有占位声明（那是 32 格完整网格的存档） |
| 4 | `docs/M2_CAMPAIGN_RUNBOOK.md` §0.6:238-240 的补注示例 | 旧式占位 `SZ-CBD-01` | 同第 2 项，把示例里的占位换成 wave-1 的真名（若与 T33 主换名批次先后到达，以后到的为准，两处不能一个换一个不换） |

**没有第五处**（继承 T33 §1 自查结论：ADDENDUM §5 收工清单只引用网格文件路径、不引用
其中的值，改第 1 项即自动生效）。

### wave-1 自己的工时（按 T33 §3 公式重算，不能直接拿 3.414 天打折）

> T33 §3 原话："点位数变少时……取证子集**不建议线性缩放**……点位数变少时取证子集
> 格数应等于新点位数（每点位仍留 1 个代表格）……不能直接把 3.414 天按比例打折。"

**若 wave-1 选 2 个点位**：
- quick 主体：2 点位 × 2 运营商 × 2 忙闲 × 16 run/格 × 72.4s = 128 run × 72.4s
  = 9,267.2s ≈ 2.574 小时
- 取证子集：2 格（每点位 1 代表格）× 5 run/格 × 6.5min = 10 run × 6.5min = 65min
  ≈ 1.083 小时
- 合计纯测量 3.657 小时 → +40% 现场开销 → 5.120 小时 → ÷6 小时/外场日
  ≈ **0.853 外场日**（不到一天）

**若 wave-1 选 3 个点位**：
- quick 主体：3 × 2 × 2 × 16 × 72.4s = 192 run × 72.4s = 13,900.8s ≈ 3.861 小时
- 取证子集：3 格 × 5 run/格 × 6.5min = 97.5min ≈ 1.625 小时
- 合计纯测量 5.486 小时 → +40% → 7.680 小时 → ÷6 ≈ **1.280 外场日**

两种情形都**远小于**完整 32 格的 3.414 天，符合"不等全部点位名凑齐就能跑"的设计意图。
**若 cmcc 因下节③的双卡缺口暂不可测**，上述数字需按单运营商重算（运营商维度从 2
降为 1，quick/取证两段的 run 总数各减半，其余公式不变）——届时另算，本节先给双运营
商版本作为目标态。

---

## 3. 行前检查单

### ⚠ 已确认的硬前置缺口——双卡未落实（2026-08-04，adb 实测，非假设）

大脑派单原话点名"32 格网格假设双运营商，若 P40 无第二张卡这是从未被暴露的硬前置"——
**本次撰写本文件时已用 adb 直查确认，这个风险是真实存在的，不是需要"以防万一"检查
的假设性条款**：

```
adb -s 8MY0221126002537 shell getprop gsm.sim.state
→ LOADED,ABSENT
adb -s 8MY0221126002537 shell getprop gsm.sim.operator.alpha
→ 中国电信,
```

**卡槽 1 = 中国电信（ctcc，已落实，与 T39/D-454 独立核实的 `carrier=ctcc` 互相印证）；
卡槽 2 = ABSENT（空，没插卡）**。也就是说**当前设备只能测 ctcc 一个运营商，cmcc 完全
不可测**——32 格网格（含本文件②的 wave-1 变体）里全部 cmcc 相关的格，现在一条都采
不了。

**PO 外场前必须先解决以下两件事之一**：
1. **插入第二张卡**（cmcc）——需要 PO 确认：卡二实体是否已备好、真实号码/套餐是否
   已知、插卡后是否需要重启设备或手动切换 SIM 优先级；插卡后重新跑上面两条 adb 命令
   确认变为 `LOADED,LOADED`，再开始正式采集；
2. **明确改为单运营商网格**（16 格，删掉 cmcc 那一半）——若 PO 判断短期内拿不到第二张
   卡，应尽快告知大脑，网格文件与工时数字都需要同步改（本文件②的 wave-1 数字已经
   给出"若单运营商需重算"的提示，但**未替代完整重算**，真要走这条路需要另一次
   正式改动，不是本文件自动生效的）。

### 其余行前项

- [ ] **充电宝**：满电，且确认能同时给设备供电+不影响采集（部分充电宝的输出会被系统
      识别为"已插电"从而影响 `stayon`/省电策略判断——外场前用一次实测确认干净）。
- [ ] **`stayon` 原值**：出发前先查一次 `adb shell settings get global stay_on_while_plugged_in`，
      记录原值，与 wifi_on 原值一起写进当天台账（收尾复验要对照它，不是想当然对回 0/false）。
- [ ] **前晚验机**：设备开机、能连上 adb、`mFocusedApp` 是桌面、无残留 VPN/抓包进程——
      前一晚先做一次，别等到现场才发现设备没充上电或连不上 adb。
- [ ] **服务端可达性**：出发前从外网（非公司/家庭 WiFi，用蜂窝或热点）访问一次
      `<server_url>` 确认能通，避免到点位后才发现服务端在防火墙白名单外。
- [ ] **台账模板已打印/已同步到手机**：到点后要记的东西（run_id、预热丢弃标记、
      完成N/尝试M）现场手写效率最高，提前准备好模板别现场现造格式。

---

## 4. 外场协作纪律：大脑逐 run 盯采

**目标协作节奏**（大脑派单原话）："PO 采一个 run，大脑这边 T44 工具即时验一个，问题
当场重采不白跑。"

**更新（2026-08-04，追加不改上文历史）**：本节最初撰写时 T44 状态为 DOING，下面①②
段是当时的原始记录（保留不改，与本文件一贯做法一致）；T44 已在同一天交付
（**D-459**，`scripts/verify_run.py`，属主 v4）。**判定工具已存在**，但"大脑远程逐
run 盯采"这条完整协作纪律里，工具只解决了"怎么判"这一半，"大脑怎么第一时间拿到
刚落库的那条 run 的 JSONL、判完怎么转达给现场的 PO"这一半**仍未定义**——如实标注，
不假装已经打通。

**`verify_run.py` 真实用法**（三查合一：契约门+radio 覆盖+出口一致，全部复用既有
判据函数，不重新定义"合格"）：
```
python scripts/verify_run.py <这条run的.jsonl或glob>
```
- 退出码 `0`=PASS，`1`=FAIL（契约门/radio 覆盖/出口一致三查之一没过，判词会点名
  具体哪一查、差多少），`2`=读不了输入；
- 单行判词，`PASS`或`FAIL: <具体原因>`，不含糊说"有问题"。
- **前提**：得先有这条 run 的 `.jsonl`——`verify_run.py` 本身不连设备也不连服务端，
  只读本地已有的文件。谁在跑它、这条 run 的 JSONL 怎么第一时间到那个人手上（现场
  PO 自己有笔记本能拉、还是靠大脑在服务端侧另有轮询手段）——**这条链路本文件同样
  未定义**，是下一步要补的（登记为跟进项，不在本次范围内代为设计）。

**原始记录①（撰写时 T44 尚未交付，如实保留）**：这条协作纪律依赖的落地即验工具是
T44（`docs/BRAIN_TASKBOARD.md` 所列，属主 v4，撰写本文件时状态为 DOING，尚未交付）。
T44 要做的是"per-run 实时验证脚本：run 落库→契约门+radio 覆盖+出口读出→单行判词，
外场自检零判断成本"——这正是本文件①"自检"一节里那几条命令的更快替代品。**T44
交付前，①的自检命令需要操作者自己手动跑**（**现已交付，若操作者当场有该 run 的
JSONL，可用上面的 `verify_run.py` 一条命令替代①自检段的前两条**，但①自检段列的
`validate_results.py`/`coverage_matrix.py` 等命令仍是当天收工汇总用的，不能完全
被单 run 判词取代）。

**原始记录②——T44 就绪后的协作节奏（撰写时的目标态描述，转达机制仍未落地，如实
保留）**：
1. PO 跑完一条 run（`RUN_END ... status=completed`）；
2. 对这条 run 跑契约门+radio 覆盖+出口读出，给出单行判词（**现已可用 `verify_run.py`
   实现这一步**）；
3. 大脑通过既有的跨会话消息渠道把判词转达 PO（**转达机制本身仍未定义**——是否需要
   PO 主动查看某个文件/等待通知，本文件不预先猜测）；
4. 若判词不过，PO **当场重采**（新 run_id），不必等回到办公室才发现这轮数据有问题
   要重新跑一趟；
5. 若判词过，PO 直接进入下一格/下一轮，不需要额外确认。

**操作者当前能做的**：①"到点"步骤里的实时 logcat 落盘与哨兵机制照旧执行；若现场
有笔记本且能拿到刚才那条 run 的 JSONL，可以自己跑一次 `verify_run.py` 立刻自查，
不必等大脑那边的转达机制补齐。

---

## 附：本文件覆盖范围之外、明确留给后续处理的事项

- wave-1 具体选哪 2-3 个近点：**PO 现场判断**（②已说明技术边界）。
- 双卡缺口的最终解法（插卡 or 改单运营商）：**PO 决策**（③已列出两个选项，未替 PO
  拍板）。
- T44 交付后本文件④需要更新为具体调用方式：**跟进项，不在本次范围**。
