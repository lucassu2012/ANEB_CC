#Requires -Version 5.1
<#
  shaper.ps1 - 段 B 整形器启动器（BeanNetworkTester 版；承接线单 §4.3 / D-838 / D-840 / D-841）

  安全模型（这是这条链上唯一的安全边界，见 D-840）：
    - 本脚本经 `ANEB-Shaper-Start` 计划任务以 /RL HIGHEST **提权**运行；
    - 它读的 current.args 位于**非管理员可写**的目录（profiles/），因此 current.args
      **只允许放一个档名**，档名→参数的映射（$MENU）写死在**本脚本**里，
      而本脚本须部署在**管理员独写**目录（建议 C:\Program Files\aneb-shaper\）。
    - ⇒ 非管理员能选菜单里的档，**不能注入任何旗标**。这是白名单/菜单，不是黑名单：
      菜单不需要知道要挡什么，只需要知道要放什么；一份漏了的黑名单不会报错（D-838 订正）。

  ⚠ $MENU 的每个值都是**print-config 已验**的固定参数数组，且**不含任何破坏性/改作用域旗标**
    （rst-prob / block-ip / block-port / lan-mode / internet-only / syn-drop / corrupt / dup /
     flap-* 一律不出现）。新增档位只许照此形状加，且加完必须过 test_shaper_whitelist.py。
#>
param(
    # current.args 路径。默认＝本脚本旁 ..\profiles\current.args。测试用它指向临时文件。
    [string]$ArgsFile,
    # 只解析档名->参数并打印，**不启动**任何进程（供 test_shaper_whitelist.py 驱动）。
    [switch]$ResolveOnly
)
$ErrorActionPreference = 'Stop'

# 部署后 BeanNetworkTester 的家（管理员独写）。仅启动时需要；ResolveOnly 不碰它。
$ToolHome = 'C:\Program Files\aneb-shaper\BeanNetworkTester'

# ---- 菜单：档名 -> 固定参数数组。current.args 只能选键，不能供值。----
# 作用域固定为「出站 + 仅目标 IP」（§三-C：绝不吃默认全机作用域）。
# 目标 = 223.5.5.5（验收目标，与旧 current.args 一致）。战役目标 IP 另作已验菜单项加入。
# 档位取三族各一（延迟/丢包/限速），承 §2.2 阶梯（lat50/100/200/400/800、loss1/2/5/10、
# up 阶梯）；本表先出「每族一行」，阶梯其余级按同一形状扩。
$TARGET = @('--filter', 'out', '--dst-ip', '223.5.5.5')
$MENU = @{
    # 延迟 200ms（旧 current.args 的档；lat200）
    'delay_lat200'  = $TARGET + @('--latency', '200')
    # 丢包 5%（loss5；代表级，阶梯 loss1/2/5/10 同形）
    'loss_5pct'     = $TARGET + @('--loss', '5')
    # 限速：--up 单位为 KB/s。⚠ 125 KB/s ＝ 1 Mbit/s（**假设 up 阶梯标签为 Mbps**，待 PO/战役钉死）。
    #   这是 clumsy 出不了的档（无令牌桶，D-656① 曾剔除）；BeanNetworkTester 的 --up/--buffer 能出。
    'cap_up_1mbit'  = $TARGET + @('--up', '125', '--buffer', '1000')
}

# ---- 解析档名 ----
if (-not $ArgsFile) { $ArgsFile = Join-Path (Split-Path -Parent $PSScriptRoot) 'profiles\current.args' }
if (-not (Test-Path -LiteralPath $ArgsFile)) { throw "current.args 不存在: $ArgsFile" }
$name = (Get-Content -LiteralPath $ArgsFile -TotalCount 1)
if ($null -ne $name) { $name = $name.Trim() }
if (-not $name) { throw 'current.args 为空' }
if (-not $MENU.ContainsKey($name)) {
    throw ("档名不在菜单: '{0}'。可选: {1}" -f $name, (($MENU.Keys | Sort-Object) -join ', '))
}
$callArgs = $MENU[$name]

if ($ResolveOnly) {
    # 供测试：只打印解析结果，绝不启动、绝不碰驱动。
    $callArgs -join ' '
    return
}

# ---- 启动（提权任务内；不需程序再自提权，反而更干净：D-838①）----
$env:BEAN_NO_ELEVATE = '1'
$exe = Join-Path $ToolHome 'BeanNetworkTester.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "BeanNetworkTester 未部署: $exe" }
Get-Process BeanNetworkTester -ErrorAction SilentlyContinue | Stop-Process -Force
$launch = $callArgs + @('--duration', '0', '--log-file',
    (Join-Path (Split-Path -Parent $PSScriptRoot) 'profiles\bean.log'))
Start-Process -FilePath $exe -ArgumentList $launch -WorkingDirectory $ToolHome
Add-Content -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'profiles\start.log') `
    -Value ("{0} START {1} => {2}" -f (Get-Date -Format s), $name, ($launch -join ' '))
