# 段 B 步骤 3–6：BeanNetworkTester 真整形实证（2026-09-12）

> 批次：段 B 整形器换代（clumsy → BeanNetworkTester v0.6.0）的**真整形验收**。
> 与 `evidence/b2_beanverify_20260907/`（步骤 0–2，零副作用）**不是同一件事**：那份证的是
> 「有无头 CLI」，**本份证的是「它跑起来真的开始整形」** —— 即 D-789 那条唯一只能靠实跑回答的未知。
> 授权基础＝用户本会话常设授权「驱动加载授权，后续一律同意授权」（覆盖本项目整形链）。
> ⚠ **本份只验了延迟档**；丢包档与限速档**未验**，边界见 §7，**不得由延迟档外推**。

## 1. 起跑前现态（我从非提权会话自核，非采信转述）

| 项 | 实测 |
|---|---|
| 本会话提权态 | `IsInRole(Administrator)=False` ⇒ **非提权**（段 B 前提） |
| `bin\shaper.ps1`／`shaper_stop.ps1` | 与仓内 `scripts/shaper/` 同名文件 **sha256 逐位相同** |
| 工具本体 | `C:\Program Files\aneb-shaper\BeanNetworkTester\BeanNetworkTester.exe` 在位 |
| 两个计划任务 | 仍指 `bin\shaper.ps1`／`bin\shaper_stop.ps1`，`RunLevel=Highest`，`State=Ready` |
| 驱动 | `sc query WinDivert` = **1060 服务不存在**（干净起点） |

## 2. 🔴 对照 IP：大脑建议的那个不可达，已换（这一步不是形式）

判据是「**同样可达**且不在 `--dst-ip` 内」。实测：

```
114.114.114.114  ok=0/20   ← 完全不可达，弃用
1.1.1.1          ok=8 但 RTT 恒为 0（被本地应答/取整），读数可疑，弃用
223.6.6.6        ok=8  中位 11ms  稳定  ← 采用（近对照）
119.29.29.29     ok=8  中位 36ms  稳定  ← 采用（远对照）
```

⚠ **拿一个本来就不可达的 IP 当对照，「对照没变」是因为它压根没有读数** ——
那不是排除了「量法不灵敏」，那**正是另一种量法不灵敏**。

**用两个对照而非一个**：
- **近对照 `223.6.6.6`**（AliDNS 同族邻居）⇒ 验作用域**精确到 IP 而非网段**；
- **远对照 `119.29.29.29`**（异运营商）⇒ 验整形无全局外溢。

## 3. 基线（整形前，同一时间窗）

| 角色 | IP | n | 中位 | 极差 |
|---|---|---|---|---|
| 目标 | 223.5.5.5 | 20 | **11** | 11–19 |
| 近对照 | 223.6.6.6 | 20 | 11 | 10–16 |
| 远对照 | 119.29.29.29 | 20 | 37 | 36–41 |

⇒ `delay_lat200` 的**预期带**＝ 11 + 200 = **211 ± 30 ⇒ 181..241 ms**。

## 4. 步骤 3：非提权触发 `/RL HIGHEST`

`current.args` 写入 `delay_lat200`。⚠ **强制无 BOM**：`shaper.ps1` 用 `Trim()` 后做
`ContainsKey`，而 **BOM 不会被 `Trim()` 去掉**，会让档名变成 `\ufeffdelay_lat200` 直接抛错。
实测写入 12 字节、首字节 `100/101/108`（非 `239/187/191`）。

```
schtasks /Run /TN ANEB-Shaper-Start
  SUCCESS: Attempted to run the scheduled task   rc=0
  LastTaskResult=0        无任何交互式提示（UAC）
start.log 新增（脚本自己写的）：
  2026-09-12T01:58:58 START delay_lat200 => --filter out --dst-ip 223.5.5.5 --latency 200 --duration 0 --log-file ...
进程：BeanNetworkTester PID=19680
```

⇒ 菜单解析成功（档名 → 固定参数数组）、参数正是菜单里那串、工具被真正拉起。
⚠ 通道本身（非提权能否触发 Highest）**早由 D-790 证过**，本步答的只是**新工具在这条通道上的行为**。

## 5. 🔴 步骤 4／5：整形真的生效，且作用域精确

**步骤 5 — 驱动真的加载**（外部观测，非工具自述）：

```
sc query WinDivert
  TYPE  : 1  KERNEL_DRIVER
  STATE : 4  RUNNING          ← 整形前是 1060「服务不存在」
```

**步骤 4 — RTT**：

| 角色 | IP | 基线 | 整形中 | 判定 |
|---|---|---|---|---|
| **目标** | 223.5.5.5 | 11 | **212**（211–219） | **+201 ms，落带 181..241** ✅ |
| 近对照 | 223.6.6.6 | 11 | **11**（11–12） | 不变 ✅ |
| 远对照 | 119.29.29.29 | 37 | **37**（36–41） | 不变 ✅ |

三条结论，逐条有独立支撑：
1. **整形生效**：抬升 **+201 ms** 与注入的 200 ms 几乎精确吻合；`min` 亦由 11 抬到 211
   ⇒ 是**稳定注入**而非偶发抖动。
2. **量法灵敏**：两个对照都能读出稳定读数且**纹丝不动** ⇒ 「目标变了」不是量法漂移。
3. **作用域精确到 IP**：近对照 `223.6.6.6` 与目标同族相邻却**完全不受影响** ⇒ `--dst-ip`
   是精确匹配而非网段匹配（§三-C「绝不吃默认全机作用域」在实测上成立）。

📌 **对照 clumsy**：D-792 那次目标 RTT 11→**12** ms（根本没生效）；本次 11→**212** ms。
**这就是换代要买的那个东西。**

## 6. 步骤 6：收尾

```
schtasks /Run /TN ANEB-Shaper-Stop   rc=0   LastTaskResult=0
start.log: 2026-09-12T02:04:58 STOP
进程残留：无            驱动：sc query WinDivert = 1060 不存在（已卸载）
目标 RTT：212 → 12 ms（回基线）      近对照：11 ms 不变
临时探测文件残留：无
```

**额外旁证 —— 工具自身的计数器**（`bean.log` 尾部，与菜单白名单的设计意图互相印证）：

```
[340.0s] pkts=38281 loss=0 syn=0 nat=0 rst=0/0 lan=0 localnet=0 block=0 corrupt=0 rate=0 queue=0
```

⇒ **所有破坏性计数全为 0**（无 RST 注入、无阻断、无损坏、无 LAN 切断），与
`--print-config` 里那些破坏性键保持默认一致。

## 7. ⚠ 未验证的边界（**不得外推**）

- **只验了 `delay_lat200` 一档。** `loss_5pct` 与 `cap_up_1mbit` 用的是**不同的整形机制**
  （丢包 vs 令牌桶限速），**能否生效不能从延迟档外推**（承 D-789：这正是 clumsy 栽的形状）。
- **丢包档**可用大样本 ping 验（5% 丢包需 ~200 次样本才可靠），未跑。
- **限速档的验证前提尚未解决**：测达成上行速率需要**向目标打真实流量**，而当前目标
  `223.5.5.5` 是公共 DNS，**不适合承受压测流量**。⇒ 需先定一个可承压的端点，
  该选择属战役/PO 范围，不由本份决定。
- 限速档按 D-843：**落带即认，落不进改 `125` 这个常数、不改档名**；实测值只写证据。

## 8. 复现命令

```powershell
# 基线（整形前）
Test-Connection 223.5.5.5 -Count 20 ; Test-Connection 223.6.6.6 -Count 20
# 起（非提权会话）
[IO.File]::WriteAllText('E:\tools\aneb-shaper\profiles\current.args','delay_lat200',(New-Object Text.UTF8Encoding($false)))
schtasks /Run /TN ANEB-Shaper-Start
sc.exe query WinDivert            # 应 STATE=4 RUNNING
# 量（目标应落 181..241；两对照应不变）
Test-Connection 223.5.5.5 -Count 20
# 收
schtasks /Run /TN ANEB-Shaper-Stop
sc.exe query WinDivert            # 应回 1060
```

## 9. 本份自身的边界

- RTT 用 `Test-Connection` 取 `ResponseTime` 数组算中位数，**不解析 ping 的文本输出**
  （该环境下中文 ping 输出会乱码，文本解析易错）。
- 中位数与极差同印；单点均值不作判据。
- 原始 CSV（`baseline.csv`／`shaped.csv`）在会话 scratchpad，未入库；上面的命令可独立重算。
