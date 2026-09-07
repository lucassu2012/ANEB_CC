#Requires -Version 5.1
<#
  shaper_stop.ps1 - 段 B 整形器停止器（BeanNetworkTester 版；承接线单 §4.3 / D-841）
  经 `ANEB-Shaper-Stop` 计划任务以 /RL HIGHEST 运行。
  收尾：停进程 + 卸驱动（--cleanup-driver 释放被锁的 .sys，无需重启）+ 留痕。
#>
param([switch]$ResolveOnly)   # ResolveOnly：只自证不动系统（供测试对称）
$ErrorActionPreference = 'Continue'
$ToolHome = 'C:\Program Files\aneb-shaper\BeanNetworkTester'

if ($ResolveOnly) { 'stop: BeanNetworkTester + --cleanup-driver'; return }

$env:BEAN_NO_ELEVATE = '1'
Get-Process BeanNetworkTester -ErrorAction SilentlyContinue | Stop-Process -Force
$exe = Join-Path $ToolHome 'BeanNetworkTester.exe'
if (Test-Path -LiteralPath $exe) {
    # 卸掉可能残留的 WinDivert 驱动服务（承 §四 收尾步；工具自带此子命令）。
    & $exe --cleanup-driver 2>&1 | Out-Null
}
Add-Content -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'profiles\start.log') `
    -Value ("{0} STOP" -f (Get-Date -Format s))
