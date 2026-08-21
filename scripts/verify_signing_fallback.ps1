# T58b/D-500④ 签名双轨的可执行验证（构建面无法用 JVM 单测覆盖，故以脚本固化）。
#
# 验什么（两个方向，缺一不可）：
#   A. 密钥齐备  → 产出 probe-release.apk 且 apksigner verify 通过（签名真的被用上）
#   B. 密钥缺失  → 回落 probe-release-unsigned.apk 且**构建不失败**
#      （D-500④ 承诺"不阻断没有密钥的协作方构建"——v3/v4/Codex 拉代码照样能 build）
#
# 为什么两个方向都要验：风险不对称。B 方向失败是"别人构建崩"，显眼；
# **A 方向失败是"密钥明明在却没被用上、静默产出 unsigned 包"，直到装机才发现**。
#
# 用法： pwsh -File scripts/verify_signing_fallback.ps1
# 前置： local.properties 里已配 aneb* 四键（否则 A 段会被如实报为 SKIP 而非伪装通过）

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$appDir = Join-Path $repo 'app'
$outDir = Join-Path $appDir 'probe\build\outputs\apk\release'
$lp = Join-Path $appDir 'local.properties'
$env:JAVA_HOME = 'E:\tools\jdk-17.0.19+10'
$env:ANDROID_HOME = 'E:\tools\android-sdk'

function Invoke-Release {
    Push-Location $appDir
    try { & .\gradlew.bat :probe:assembleRelease --% -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7897 | Out-Null }
    finally { Pop-Location }
    return $LASTEXITCODE
}
function Get-ReleaseApk { Get-ChildItem "$outDir\*.apk" -ErrorAction SilentlyContinue | Select-Object -First 1 }

$fail = 0
$hasKeys = (Test-Path $lp) -and ((Get-Content $lp -Raw) -match 'anebStoreFile')

# ---- A. 密钥齐备 → signed ----
if ($hasKeys) {
    Remove-Item "$outDir\*.apk" -ErrorAction SilentlyContinue
    if ((Invoke-Release) -ne 0) { Write-Output 'A: FAIL 构建失败'; $fail++ }
    else {
        $apk = Get-ReleaseApk
        if (-not $apk) {
            # 实战教训（2026-08-22 verify_all 日志）：共享工作树里他方并发构建可在
            # Invoke-Release 与本行之间清掉 outputs——若不判空，$apk.FullName 为空串，
            # apksigner 报 "Missing APK" 崩成一堆 NativeCommandError，**读日志的人看不出
            # 是"没产出 APK"还是"签名坏了"**。清晰 FAIL 出来。
            Write-Output 'A: FAIL 构建报成功但 outputs 里没有 APK（多为并发构建清理了产物；重跑即可）'; $fail++
        }
        elseif ($apk.Name -like '*unsigned*') {
            Write-Output "A: FAIL 密钥齐备却产出 $($apk.Name)（签名未被用上——最危险的静默失败）"; $fail++
        } else {
            $signer = & "$env:ANDROID_HOME\build-tools\35.0.0\apksigner.bat" verify --print-certs $apk.FullName 2>&1 | Select-String 'certificate DN'
            if ($signer) { Write-Output "A: PASS $($apk.Name) / $($signer -replace '.*DN: ','')" }
            else { Write-Output "A: FAIL $($apk.Name) 未通过 apksigner verify"; $fail++ }
        }
    }
} else { Write-Output 'A: SKIP（local.properties 无 aneb* 键，无密钥可验——如实跳过，不算通过）' }

# ---- B. 密钥缺失 → unsigned 且构建成功 ----
$bak = "$lp.verifybak"
if (Test-Path $lp) { Copy-Item $lp $bak -Force; (Get-Content $lp) | Where-Object { $_ -notmatch '^aneb' } | Set-Content $lp -Encoding utf8 }
try {
    Remove-Item "$outDir\*.apk" -ErrorAction SilentlyContinue
    if ((Invoke-Release) -ne 0) { Write-Output 'B: FAIL 无密钥时构建失败（违背 D-500④ 不阻断承诺）'; $fail++ }
    else {
        $apk = Get-ReleaseApk
        if (-not $apk) { Write-Output 'B: FAIL 构建报成功但 outputs 里没有 APK（同 A 分支注释）'; $fail++ }
        elseif ($apk.Name -like '*unsigned*') { Write-Output "B: PASS 回落 $($apk.Name)，构建未中断" }
        else { Write-Output "B: FAIL 无密钥却产出 $($apk.Name)"; $fail++ }
    }
} finally {
    if (Test-Path $bak) { Move-Item $bak $lp -Force }   # 无论如何还原（含中途异常）
}

if ($fail -eq 0) { Write-Output 'RESULT: PASS'; exit 0 } else { Write-Output "RESULT: FAIL ($fail)"; exit 1 }
