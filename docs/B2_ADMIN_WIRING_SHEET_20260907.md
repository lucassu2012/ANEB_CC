# 段 B 整形器接线单（需管理员执行，2026-09-07）

> **为什么这份要 PO 亲手跑**：不是授权问题（PO 已给常设授权 D-836），是**执行权限问题**——
> 这几步要写入管理员独写目录、并替换一个跑在 `/RL HIGHEST` 提权任务里的脚本。**大脑与 v4 都是非提权会话，物理上做不了。**
> 承 D-809（PO 裁换整形器）、D-836（下载授权）、D-837/838/839（核验结论）、`docs/B2_SHAPER_VERIFICATION_20260907.md`。

## §0 现状与要改什么

`E:\tools\aneb-shaper\` 现在的接线是给 **clumsy** 用的，而 clumsy 已被判出局（无无头模式，D-792／D-809）。
替代件 `BeanNetworkTester v0.6.0` 已下载、已核验、**无头 CLI 已实跑证成**（v4 步骤 0–2）。
本单把接线切到新工具，**并顺手关掉一条实测出来的提权路径**。

## §1 🔴 先读这一条：一条被实测出来的提权路径

从**非提权会话**直接试写（不是读 ACL——ACL 在这件事上骗过我们一次）：

| 目录 | 非管理员可写 |
|---|---|
| `E:\tools\aneb-shaper`（根） | **YES** |
| `E:\tools\aneb-shaper\bin` | NO |
| `E:\tools\aneb-shaper\profiles` | **YES** |

而 `bin\shaper.ps1` 第 3 行读的正是 `profiles\current.args`，读完把内容交给 `Start-Process`，
**整个脚本跑在 `/RL HIGHEST` 的提权任务里**。

⇒ **一个非管理员可写的文件，在给一个提权进程喂参数。**

⚠ **这不是 bug，是设计**：非提权会话本来就要靠这个文件配置参数。**今天拦住它的是 `shaper.ps1` 里那条白名单正则**——它只认 clumsy 的旗标，字符类收得很紧。**那条正则是这条链上唯一的安全边界。**

🔴 **而换工具恰恰要重写那条正则，同时新工具带着 clumsy 没有的破坏性旗标**：`rst_prob`（TCP RST 注入）、`block_ip`（阻断）、`lan_mode`。**白名单写松一格，一个非管理员就能经提权任务发起全机 RST 注入或阻断。**

## §2 因此本单换掉「过滤」这个思路（推荐做法，理由在下面）

**不再让非提权侧写「参数」，改成只让它写一个「档名」。**

- `profiles\current.args`（可被非管理员写）→ 内容改成**一个档名**，例如 `f6-cell-200ms`；
- `bin\shaper.ps1`（管理员独写）里放一张**固定的档名到参数的表**；
- 档名不在表里就拒绝，**表以外的参数根本无从表达**。

**为什么推荐这个而不是「把正则写紧一点」**：
**过滤器可以被绕过，菜单不能。** 而且——**那条正则无论如何都要从头重写**（clumsy 的旗标一个都不能用了），
所以选安全的那个设计**不多花任何代价**，只是重写成另一种形状。

## §3 执行前置：这一步归 v4，不归 PO

✅ **已完成（v4，`03e9270`）。** 脚本、菜单、反例守卫都已入 `scripts/shaper/`，门禁 859/859 RC=0。

⚠ **我原先在这里写的示例是错的**：我写成 `--filter "outbound and ip.DstAddr == ..."`，
那是 **clumsy／裸 WinDivert 的语法**。BeanNetworkTester 的 `--filter` 是**枚举**
`{both,out,in,tcp,udp,ping,loopback}`，作用域靠 `--dst-ip` 指定。
**v4 查了 `--help` 才发现，没照抄我给的形状**——这是对的做法，记在这里免得后来人回头照抄我那句。

交付的三档（每档都用 `--print-config` 验过，且破坏性旋钮全为默认）：

| 档名 | 参数串 |
|---|---|
| `delay_lat200` | `--filter out --dst-ip 223.5.5.5 --latency 200` |
| `loss_5pct` | `--filter out --dst-ip 223.5.5.5 --loss 5` |
| `cap_up_1mbit` | `--filter out --dst-ip 223.5.5.5 --up 125 --buffer 1000` |

### §3.1 两处大脑裁定（v4 报上来待钉的）

**（一）限速单位：标签是比特率，工具吃字节率，换算按十进制，但——不靠读定案，靠测定案。**

战役计划自己写着「1.44MB<6s 需 **≥4.3Mbps** 上行」，同一份文件的阶梯是 `up2m/1m/512k/256k/128k`
⇒ **标签是 bit/s**。而 `--up` 吃的是 KB/s ⇒ 换算 `÷8 ÷1000`，`1 Mbps → 125 KB/s`。v4 取的值对。

⚠ **但这只是假设，不是定案**：工具的「KB」是 1000 还是 1024，读文档答不了，
**而步骤 4 本来就要实测达成速率**。⇒ **实测值落在预期带即认，落不进就改常数、不改标签。**

🔴 **档名写意图，证据写实测，两者永远不许互相覆盖。** `cap_up_1mbit` 是我们要的那个数；
实测 0.98 或 1.05 Mbps 都记在证据里。**一旦拿实测值去改档名，就再也看不出换算错过。**

**（二）目标 IP：验收用 223.5.5.5，战役目标另加已验菜单项——但这里有一个必须先说破的代价。**

菜单设计的代价是**不灵活**：每加一个目标 IP 或一个阶梯级，都要改一次**管理员独写文件**。
阶梯五级 × 两方向 × 若干目标，条目会很多，**后来人一定会想把它参数化回去**——那等于退回原来的注入面。

⇒ **允许的做法**：菜单可以由**两张钉死的表**（目标表 × 档位表）在脚本内**生成**叉积，
**但那两张表必须留在同一个管理员独写文件里**。这样既去掉了条目的繁琐，又不引入任何来自非提权侧的自由文本。
⇒ **不允许的做法**：让 `current.args` 携带 IP、速率、或任何非档名的内容。

## §4 管理员步骤（PowerShell，以管理员身份运行）

### 4.1 建立管理员独写的工具目录并放置工具

> **2026-09-12 订正**：原先此处写「`<v4 提供的 zip 路径>`」占位符。五天后不该让 PO 去找某个会话的临时目录。
> 校验过的包已放到 **`E:\tools\aneb-shaper\`**（与 clumsy 的包同处，哈希已登记进同目录 `SHA256SUMS.txt`），
> 且**哈希核对从注释改成了会当场失败的命令**——因为那个目录非管理员可写（§1），核对不是可选项。

```powershell
$zip  = 'E:\tools\aneb-shaper\BeanNetworkTester-v0.6.0-windows-x64.zip'
$want = '3d6a17ae8880a675f0fc23eeb1f5520a638fb1433ae9ea6ef77ca4df85cbed1a'
$got  = (Get-FileHash -Algorithm SHA256 -Path $zip).Hash.ToLower()
if ($got -ne $want) { throw "zip 哈希不符，停手。got=$got" }
$dst = 'C:\Program Files\aneb-shaper'
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Expand-Archive -Path $zip -DestinationPath $dst -Force
Get-ChildItem "$dst\BeanNetworkTester" | Select-Object -First 5
```

期望：哈希行不抛错；最后一行列出 `BeanNetworkTester.exe` 与 `_internal\`。
**层级已核**：zip 顶层目录是 `BeanNetworkTester/`，解到 `aneb-shaper` 下正落在
`scripts/shaper/shaper.ps1` 第 26 行写死的 `$ToolHome = 'C:\Program Files\aneb-shaper\BeanNetworkTester'`。

**为什么是 `C:\Program Files\`**：Windows 默认即管理员独写，**不需要手改 ACL**，
而手改 ACL 是最容易改错、且改错了不报错的一步。

### 4.2 验证放置后的目录确实非管理员不可写

```powershell
New-Item -ItemType File -Path 'C:\Program Files\aneb-shaper\.wtest' -ErrorAction Stop
```

🔴 **这一条必须在一个「非管理员」窗口里跑，期望它失败。**
在管理员窗口里跑它必然成功，**证明不了任何事**——E-2 那张单子上我们已经栽过一次同款
（当时 §3 写的检查在管理员窗口里恒过，后来才改掉）。

### 4.3 替换 shaper.ps1（内容由 v4 按 §2 形状与 §3 参数串给出）

新脚本要满足四条，**v4 交稿时逐条自证**：

1. 读 `current.args`，**只接受档名**，正面枚举，档名不在表里即抛错；
2. 参数表里**只有**三档所需（延迟／丢包／限速）＋ `--filter`／`--target`；
3. **有反例测它**——只有正例的白名单，放宽成「什么都放行」照样全绿；
4. 启动时置 `BEAN_NO_ELEVATE=1`——任务已是 `/RL HIGHEST`，**不需要程序再自提权**，
   关掉它反而更干净（承 D-838①）。

⚠ **本条第 3 点原先写的是「确保 `rst_prob`／`block_ip`／`lan_mode` 过不了」，已订正。**
那是一份**黑名单**，而本单 §2 正在论证要用**白名单**——**我在自己的单子里写了自己反对的那个形状**。
照原字面实现，下面这些照样能到达。`--print-config` 的 33 键里，破坏性或改变作用域的**至少有十一个**：

```
block_ip  block_port  rst_prob  rst_cooldown  syn_drop
corrupt   dup         flap_down flap_period   lan_mode  internet_only
```

⇒ **正因为「要挡的」这份名单我第一次就没列全，才更该用菜单**：
**菜单不需要知道要挡什么，它只需要知道要放什么。** 一份漏了的黑名单不会报错。

### 4.4 从仓里部署两个脚本（方向已订正）

⚠ **本节原先写反了**：我写的是「从 `E:\tools` 拷进仓里」。**v4 已经把脚本直接写进仓了**（`03e9270`），
所以方向是**从仓里拷到管理员目录**。旧的 `E:\tools\aneb-shaper\bin\shaper.ps1` 是 clumsy 版，**不再使用**。

```powershell
$dst = 'C:\Program Files\aneb-shaper'
Copy-Item 'E:\C Project\ANEB\scripts\shaper\shaper.ps1'      "$dst\shaper.ps1"
Copy-Item 'E:\C Project\ANEB\scripts\shaper\shaper_stop.ps1' "$dst\shaper_stop.ps1"
```

**用 `Copy-Item` 而不是重新创建文件** —— 理由见下一节。

### 4.5 🔴 拷完必须验 BOM，这一条不能省

```powershell
foreach ($f in 'shaper.ps1','shaper_stop.ps1') {
  $b = [System.IO.File]::ReadAllBytes("C:\Program Files\aneb-shaper\$f")[0..2]
  '{0}: {1}' -f $f, $(if ($b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF) { 'BOM 在' } else { '⚠ 缺 BOM，停手' })
}
```

**为什么**（v4 实测，这个坑咬过他一次）：
**无 BOM 的 UTF-8 PowerShell 脚本，只要含中文注释，PS 5.1 下 `param()` 绑定会静默失效**——
脚本照常跑，但 `-ArgsFile` 之类的命名参数**不绑定、回落默认值、不报任何错**，
连 `Tokenize` 语法检查都照过。

🔴 **落到这条链上的后果**：提权任务读参数会**静默走默认路径**，
而「读错了文件」与「读对了文件」在输出上长得一模一样。
⇒ 这也是为什么 4.4 要用 `Copy-Item`（按字节搬运）而**不是**重新敲一个文件出来。

### 4.6 版本管理的那道守卫（归 v4，部署后补）

两个脚本现已入库（`scripts/shaper/`，D-841 已闭合前半）。**后半还缺**：一道
「**管理员目录里那份，与库里那份逐字节一致**」的守卫。
⇒ 部署路径定下来之后由 v4 补，**判据取字节不取行**（今天已经栽过：`git diff` 是关于行的，D-829）。

## §5 跑完之后（v4 执行，不需要 PO）

按 `docs/B2_SHAPER_VERIFICATION_20260907.md` §7 的步骤 3–6：

3. 经现有 schtasks 通道、**从非提权会话**起停，实测弹不弹交互式提示。
   ⚠ 通道本身**已经证成**（D-790：非提权触发 `/RL HIGHEST`，clumsy 真被拉起，善后干净），
   本步要答的是更窄的那个问题：**新工具在这条通道上起来时的行为**。
4. **目标 IP 的 RTT 抬到预期带才算过，同时打一个不该被影响的对照 IP。**
   没有那个对照，「目标没变」排不掉「量法不灵敏」。
5. `sc query WinDivert` 确认驱动**真的加载了**（工具自带的 `--doctor` 是天然预检）。
6. 收尾：停、复验 RTT 回基线、`--cleanup-driver`、无残留。

**任一步不过就停下来报，不试参数。**

## §6 本单不做的一件

`E:\tools\aneb-shaper\` 那套 clumsy 自此不再使用。**本单不删它**——
它是 D-790／D-792 的实物证据。要清理请另裁，**别顺手做在本单里**。
