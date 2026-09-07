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

**v4 须先交出 §4.3 需要的确切参数串**（本单故意留空，不猜）：
用 `--help` 与 `--print-config` 确认 BeanNetworkTester v0.6.0 的**旗标确切拼法**，产出形如
`--filter "..." --target ... --latency 200` 的完整行。**这一步不需要管理员，v4 自己能做。**

⇒ **PO 请等 v4 把参数串交上来再跑本单**，免得跑两趟。

## §4 管理员步骤（PowerShell，以管理员身份运行）

### 4.1 建立管理员独写的工具目录并放置工具

```powershell
$dst = 'C:\Program Files\aneb-shaper'
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Expand-Archive -Path '<v4 提供的 zip 路径>' -DestinationPath $dst -Force
Get-ChildItem $dst
```

期望 zip 的 `sha256 = 3d6a17ae8880a675f0fc23eeb1f5520a638fb1433ae9ea6ef77ca4df85cbed1a`（12,900,470 字节）。

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

### 4.4 把两个脚本纳入版本管理

```powershell
New-Item -ItemType Directory -Force -Path 'E:\C Project\ANEB\scripts\shaper' | Out-Null
Copy-Item 'E:\tools\aneb-shaper\bin\shaper.ps1'      'E:\C Project\ANEB\scripts\shaper\shaper.ps1'
Copy-Item 'E:\tools\aneb-shaper\bin\shaper_stop.ps1' 'E:\C Project\ANEB\scripts\shaper\shaper_stop.ps1'
```

**为什么**：这两个脚本**当前不受 git 跟踪**（`git ls-files` 对 `shaper` 只命中三份 docs 与一份 evidence），
而其中一个**承载着上面说的那条唯一安全边界**。⇒ **一条改了没有任何东西会报的安全控制。**
（与今天上午那份「无人校验的完整性记录」是同一个形状，D-822。）
入库后由 v4 补一道守卫：**盘上那份与库里那份须一致**。

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
