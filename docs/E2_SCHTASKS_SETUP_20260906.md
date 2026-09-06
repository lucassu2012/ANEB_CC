# E-2 提权常态化：`schtasks /RL HIGHEST` 一次性创建单（PO 亲裁 (b)，D-712(1)）

> **给 PO 照抄的单子。只需在「管理员 PowerShell」里跑一次 §2；此后编队任何非提权会话都能起／停整形器，不再需要您开窗。**
> 设计目标＝把 D-712(1) 点名的代价「脚本对本用户可写＝常开提权通道」**堵掉**：被提权执行的可执行文件与包装脚本放**仅 Administrators/SYSTEM 可写**的目录；非提权侧只能改「档位参数」一行文本，且包装脚本按**白名单**校验后才传给 clumsy（clumsy 的参数只影响过滤与整形，不含任何代码执行面）。
> 依据：D-702③（schtasks 替代方案）、D-712(1)、D-656③／D-657（`clumsy-0.3-win64-a.zip` sha256 ＝ `f50dc734148815831c67d9fc2c246c22d421c53dcea51e26eee905b0b2806c27`，与 D-657 登记值一致；**范围限定**：clumsy 上游 release 不发布校验和、GitHub 资产 digest 为空，第二源只有资产大小 536789 一致——本比对只证「登记→解压之间未被改」，**不证溯源**（cd5239ba 09-06 指出，采纳））；clumsy 命令行旗标核自上游源码 `src/utils.c`（`--key value` 形态）、`src/lag.c`／`drop.c`／`bandwidth.c`（`<模块>-inbound/-outbound/-time/-chance/-bandwidth`）、`src/main.c`（`--filter`，带参启动即开始过滤）。

## 1. 现状（2026-09-06 11:2x，大脑核）

- 绿色包已按批准下载并校验：`E:\tools\aneb-shaper\clumsy-0.3-win64-a.zip`、`gnirehtet-rust-win64-v2.5.1.zip`（`SHA256SUMS.txt` 为 gnirehtet 官方值，`sha256sum -c` OK）；已解包到 `E:\tools\aneb-shaper\clumsy\`（`clumsy.exe`、`WinDivert.dll`、`WinDivert64.sys`、`config.txt`）与 `E:\tools\aneb-shaper\gnirehtet\`。
- 本机 Claude 桌面会话不带管理员令牌（D-702③ 实测 `IsInRole(Administrator)=False`）；`WinDivert.sys` 尚未加载过（`driverquery` 无 WinDivert）。

## 2. 您要做的（管理员 PowerShell，一次；约 2 分钟）

右键「Windows PowerShell」→「以管理员身份运行」，整段粘贴：

```powershell
# --- 0. 目录与文件（bin 仅管理员可写；profiles 用户可写） ---
$root = 'E:\tools\aneb-shaper'; $bin = "$root\bin"; $prof = "$root\profiles"
New-Item -ItemType Directory -Force $bin, $prof | Out-Null
Copy-Item "$root\clumsy\clumsy.exe", "$root\clumsy\WinDivert.dll", "$root\clumsy\WinDivert64.sys" $bin -Force

# --- 1. 包装脚本：读 profiles\current.args，白名单校验，再起 clumsy（带参即开始过滤） ---
@'
$ErrorActionPreference = 'Stop'
$bin = 'E:\tools\aneb-shaper\bin'; $argsFile = 'E:\tools\aneb-shaper\profiles\current.args'
$line = (Get-Content -LiteralPath $argsFile -TotalCount 1)
if (-not $line) { throw 'current.args 为空' }
# 白名单：只允许 clumsy 的过滤/整形旗标与安全字符（字母数字 . : / = ! & | ( ) < > 空格 引号 短横）
if ($line -notmatch '^(--(filter|lag|lag-inbound|lag-outbound|lag-time|drop|drop-inbound|drop-outbound|drop-chance|bandwidth|bandwidth-inbound|bandwidth-outbound|bandwidth-bandwidth)\s+("[A-Za-z0-9 .:/=!&|()<>-]+"|[A-Za-z0-9.]+)\s*)+$') { throw "current.args 未过白名单: $line" }
Get-Process clumsy -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Process -FilePath "$bin\clumsy.exe" -ArgumentList $line -WorkingDirectory $bin
Add-Content -LiteralPath 'E:\tools\aneb-shaper\profiles\start.log' -Value ("{0} START {1}" -f (Get-Date -Format s), $line)
'@ | Set-Content -LiteralPath "$bin\shaper.ps1" -Encoding UTF8

@'
Get-Process clumsy -ErrorAction SilentlyContinue | Stop-Process -Force
Add-Content -LiteralPath 'E:\tools\aneb-shaper\profiles\start.log' -Value ("{0} STOP" -f (Get-Date -Format s))
'@ | Set-Content -LiteralPath "$bin\shaper_stop.ps1" -Encoding UTF8

# --- 2. ACL：bin 只许 Administrators/SYSTEM 写，Users 只读执行；profiles 允许 Users 修改 ---
icacls $bin /inheritance:r /grant:r 'Administrators:(OI)(CI)F' 'SYSTEM:(OI)(CI)F' 'Users:(OI)(CI)RX' | Out-Null
icacls $prof /inheritance:r /grant:r 'Administrators:(OI)(CI)F' 'SYSTEM:(OI)(CI)F' 'Users:(OI)(CI)M' | Out-Null

# --- 3. 两个计划任务（最高权限，按需触发；无日程） ---
$ps = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File'
schtasks /Create /F /TN 'ANEB-Shaper-Start' /SC ONCE /ST 00:00 /RL HIGHEST /RU "$env:USERDOMAIN\$env:USERNAME" /TR "$ps `"$bin\shaper.ps1`""
schtasks /Create /F /TN 'ANEB-Shaper-Stop'  /SC ONCE /ST 00:00 /RL HIGHEST /RU "$env:USERDOMAIN\$env:USERNAME" /TR "$ps `"$bin\shaper_stop.ps1`""

# --- 4. 自检：任务存在且为最高权限；bin 的 ACL 无 Users 写位 ---
schtasks /Query /TN 'ANEB-Shaper-Start' /V /FO LIST | Select-String 'Run As User|Task To Run|Highest'
icacls $bin | Select-String 'Users'
```

> 若 `/RU` 那行报「无法创建，需要密码」：改用 `/RU "$env:USERDOMAIN\$env:USERNAME" /IT` 或删去 `/RU`（默认当前用户）。**不要**改成 `SYSTEM` 帐户——clumsy 有 GUI，须在您的桌面会话里运行才能被看到与停掉。

## 3. 首次验证（🔴 **必须在非提权窗跑，不要在管理员窗跑**；≈1 分钟）

> 🔴 **这一步不只是验证，它是整套设计的判决性检验，所以跑的地方比跑本身更重要。**
> 本单的全部价值压在一条**至今无实证**的假设上：**非提权会话能否触发一个 `/RL HIGHEST` 的任务**（V1 在 `docs/E2_WINDOW_FIRST_HOUR_20260906.md` §5-4 点出，全项目查无实证）。
> **在管理员窗里跑这段，它一定会过，而它证明不了任何我们要证明的事**——管理员窗本来就能起 clumsy，根本不需要计划任务。**验的不是要验的那个东西。**
> ⇒ **PO 只跑 §2；§3 交给 v4（或任一非提权会话）跑**，实录里写明**跑它的那个窗不带管理员令牌**。
> ⚠ 若 §3 在非提权窗**报拒绝**（access denied／任务不运行），**那不是配置错，是本方案的前提不成立**——停下报大脑换方案，**不要试图给那个会话提权**。

```powershell
# 非提权 PowerShell（Git Bash 写法见 §4.1）。下面第一条 schtasks /Run 就是那条判决性检验。
Set-Content -LiteralPath 'E:\tools\aneb-shaper\profiles\current.args' -Value '--filter "outbound and ip.DstAddr == 223.5.5.5" --lag on --lag-outbound on --lag-time 200' -Encoding ASCII
ping -n 5 223.5.5.5                      # 基线 RTT
schtasks /Run /TN 'ANEB-Shaper-Start'; Start-Sleep 4
driverquery | findstr /I WinDivert       # 须出现 WinDivert（内核驱动已加载）
ping -n 5 223.5.5.5                      # 判据正面写：RTT 整体抬升约 200ms 才算过；「没报错」不算
schtasks /Run /TN 'ANEB-Shaper-Stop'; Start-Sleep 2
ping -n 3 223.5.5.5                      # 回到基线
```

## 4. 此后编队怎么用（非提权会话，无需您在场）

1. 写档位：`Set-Content E:\tools\aneb-shaper\profiles\current.args '<clumsy 参数一行>'`（例：`--filter "outbound and !loopback" --drop on --drop-outbound on --drop-inbound on --drop-chance 10`）。
2. 起／停——**先看你在哪个 shell 里，这不是废话，见 §4.1**：
   - **PowerShell（推荐，照抄即可）**：起 `schtasks /Run /TN ANEB-Shaper-Start`；停 `schtasks /Run /TN ANEB-Shaper-Stop`。
   - **Git Bash（必须加前缀）**：`MSYS_NO_PATHCONV=1 schtasks /Run /TN ANEB-Shaper-Start`。
   每次起／停在 `profiles\start.log` 留行，供格 README 引用。
   ⚠ **`schtasks /Run` 返回 0 只表示「任务已被拉起」，不表示整形器在跑、更不表示整形生效**——判据仍照 §3 正面写：`Get-Process clumsy` 有进程 ＋ `driverquery` 见 WinDivert ＋ 目标 RTT 抬升到预期带。
3. 段 B（v4）／段 C（设备侧）的过滤器写法与档位表以 `docs/B2_SHAPER_BUILD_SHEET_20260903.md` §4 为准；限速档本批不覆盖（D-656①）。

### 4.1 ⚠ Git Bash 会吃掉 `schtasks` 的 `/` 参数（2026-09-06 18:5x 实测，大脑）

MSYS 路径转换把 `/Query`、`/Run`、`/TN` 当成 Unix 路径改写，于是：

```
$ schtasks /Query /TN '\Microsoft\Windows\Defrag\ScheduledDefrag'
错误: 无效参数/选项 - 'C:/Program Files/Git/Query'。          # rc=1

$ MSYS_NO_PATHCONV=1 schtasks /Query /TN '\Microsoft\Windows\Defrag\ScheduledDefrag'
ScheduledDefrag        N/A        已禁用                      # rc=0，真实数据
```

**三条要记住的**：

- **单斜杠 ＋ `MSYS_NO_PATHCONV=1` 才对**。改成 `//Run` **不管用**——那会被原样传成 `//Run`，schtasks 一样拒。
- **那条报错指向一个路径，不指向 shell** ⇒ 撞上的人最可能的误判是「任务没建成，PO 的 §2 没跑成」，然后去动本来正常的东西。**看到 `'C:/Program Files/Git/...'` 就知道是 shell 不是任务。**
- **「任务不存在」与「参数被改写」长得不一样，认准这两句**：前者是 `错误: 系统找不到指定的文件。`，后者是 `错误: 无效参数/选项 - 'C:/…'`。**要确认任务在不在，用能返回真实数据的那一式去问**，别拿一条本身就跑不通的命令的失败当「任务不存在」的证据。

> 本节由大脑在 PO 执行 §2 **之前**实测补入：源文件三个（`clumsy.exe`／`WinDivert.dll`／`WinDivert64.sys`）经核仍在 `E:\tools\aneb-shaper\clumsy\`，`bin\`／`profiles\` 尚不存在 ⇒ §2 确未执行。

## 5. 回滚（管理员窗）

```powershell
schtasks /Delete /F /TN 'ANEB-Shaper-Start'; schtasks /Delete /F /TN 'ANEB-Shaper-Stop'
Remove-Item -Recurse -Force 'E:\tools\aneb-shaper\bin', 'E:\tools\aneb-shaper\profiles'
```

## 6. 不回答什么

- 本单只解「谁来提权」；整形是否命中 gnirehtet 转发路径（段 C）与档语义正交性归 B-2／建造单。
- 白名单堵的是「任意程序被提权执行」；它不阻止合法用户把过滤器写错——过滤器写错时 clumsy 安静地什么都不做，判据必须正面写（RTT 抬升到预期带才算过）。
