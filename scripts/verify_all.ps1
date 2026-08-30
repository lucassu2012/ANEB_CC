# ANEB Probe verify_all - phase 0 verification chain (ASCII-only for PS 5.1 compatibility)
# Runs: server vet/build/test, profile JSON validation, portrait red-line guard, app toolchain probe.
# Writes: evidence/phase0/verify_all_<ts>.log (utf8) and regenerates evidence/phase0/sha256-manifest.txt
# Exit code: 0 if no FAIL (NOT_EXECUTED allowed by default), 1 otherwise.
#            With -Strict, NOT_EXECUTED also exits 1. Either way the summary now always
#            prints the NOT_EXECUTED count and names them (T69): a check that verified
#            NOTHING must never be indistinguishable from one that passed.

# -Strict: treat NOT_EXECUTED as failure (default off; see summary block at the end).
param(
    # SPEC-3 §3.2（T81）：分层触发。all=全链（收官/入册/交接点专用）；其余只跑
    # 该层的门，未跑的门以 SKIPPED_SCOPE 显名列出——绝不折算 PASS，也不冒充
    # NOT_EXECUTED（那是「想验验不了」，这是「本次没请它验」）。
    [ValidateSet('server','app','scripts','spec','all')][string]$Scope = 'all',
    # -Strict 自 SPEC-3 §3.2 起为默认（NOT_EXECUTED 计败）；开关保留作兼容名。
    # 要旧的宽松行为用 -Lenient 显式退出。
    [switch]$Strict,
    [switch]$Lenient)
$Strict = -not $Lenient

$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
$evidenceDir = Join-Path $repo 'evidence\phase0'
New-Item -ItemType Directory -Force $evidenceDir | Out-Null
# ⚠ 时间戳带 **PID**（T89，承 D-612④）：原先只有秒级 `yyyyMMdd-HHmmss`，**无进程区分**
# ⇒ 两个 verify_all 在同一秒启动会**共用同一个 $logPath 互相覆盖**，且不报错。
# 本树是共享工作树、同刻常有多个会话在跑门，这不是理论风险。
# 形状仍匹配 `.gitignore` 的 `verify_all_*.log` 与 `badges.py:latest_log` 的 glob；
# 时间戳是**定宽前缀**，故按名排序在跨时间戳时仍正确。
# ⚠ 同秒内两条日志的先后由 PID **字符串**比较决定（"9999" > "10000"）——**那是任意的**；
# 但 verify_all 总是显式把 $logPath 传给 badges.py，`latest_log` 只是手工调用时的兜底。
$ts = (Get-Date -Format 'yyyyMMdd-HHmmss') + "-$PID"
$logPath = Join-Path $evidenceDir "verify_all_$ts.log"
$results = @()

function Add-Result([string]$check, [string]$state, [string]$detail) {
    $script:results += [pscustomobject]@{ check = $check; state = $state; detail = $detail }
    "$state  $check  $detail"
}

function Test-InScope([string]$layer, [string[]]$gates) {
    # 层外的门逐个显名记 SKIPPED_SCOPE（沉默的跳过=没有检查项，2.9）；
    # 汇总与退出码都认得这个状态：不算 PASS、不算 FAIL、不触发 -Strict。
    if ($Scope -eq 'all' -or $Scope -eq $layer) { return $true }
    foreach ($g in $gates) {
        $script:log += Add-Result $g 'SKIPPED_SCOPE' ('out of -Scope ' + $Scope)
    }
    return $false
}

$log = @()
$log += "verify_all run at $ts"
$log += "repo: $repo"


# --- 共享工具链探测（python）：必须在任何 -Scope 层块之外 ---
# SPEC-3 §3.2 施工自伤记录：初版把它留在 spec 层块内，`-Scope scripts` 跑时
# 整块不执行 ⇒ $py 为空 ⇒ 本层两道门双双报「missing: python」——**实测当场
# 咬出**（分层跑 2.1s 里 0 PASS）。共享探测与被圈的门不是一回事，外提。
$py = $null
foreach ($c in @('python', 'python3', 'py')) { try { $py = (Get-Command $c -ErrorAction Stop).Source; break } catch {} }

if (Test-InScope 'server' @('server-vet','server-build','server-test')) {
# --- locate go ---
$goCandidates = @('C:\Program Files\Go\bin\go.exe', 'E:\tools\go\bin\go.exe')
$go = $null
foreach ($c in $goCandidates) { if (Test-Path $c) { $go = $c; break } }
if (-not $go) { try { $go = (Get-Command go -ErrorAction Stop).Source } catch {} }
$log += "go: $(if ($go) { $go } else { 'NOT FOUND' })"

# --- server checks ---
if ($go) {
    Push-Location (Join-Path $repo 'server')
    foreach ($step in @(@('vet', @('vet', './...')), @('build', @('build', './...')), @('test', @('test', '-count=1', './...')))) {
        $name = $step[0]; $goArgs = $step[1]
        $out = & $go @goArgs 2>&1 | Out-String
        $state = if ($LASTEXITCODE -eq 0) { 'PASS' } else { 'FAIL' }
        $log += "--- server-$name (exit $LASTEXITCODE) ---"
        $log += $out
        $log += Add-Result "server-$name" $state "go $($goArgs -join ' ')"
    }
    Pop-Location
} else {
    foreach ($name in 'vet', 'build', 'test') {
        $log += Add-Result "server-$name" 'NOT_EXECUTED' 'go toolchain not found'
    }
}

}

if (Test-InScope 'spec' @('profiles-valid','portraits-redline','adapters-spec','adapters-spec-unit','portraits-redline-unit','portraits-schema','portraits-schema-unit','spec-versions','spec-versions-unit')) {
# --- profile validation ---
$profileErrors = @()
$profileFiles = Get-ChildItem (Join-Path $repo 'profiles') -Filter '*.json'
foreach ($f in $profileFiles) {
    try {
        $p = Get-Content -Raw -Encoding UTF8 $f.FullName | ConvertFrom-Json
        foreach ($field in 'profile_id', 'version', 'kpi_set', 'phases') {
            if ($null -eq $p.$field) { $profileErrors += "$($f.Name): missing $field" }
        }
        if ($p.phases.Count -lt 1) { $profileErrors += "$($f.Name): empty phases" }
    } catch { $profileErrors += "$($f.Name): parse error: $_" }
}
if ($profileFiles.Count -eq 0) { $profileErrors += 'no profile files found' }
$log += Add-Result 'profiles-valid' $(if ($profileErrors.Count -eq 0) { 'PASS' } else { 'FAIL' }) $(if ($profileErrors.Count -eq 0) { "$($profileFiles.Count) profiles ok" } else { $profileErrors -join '; ' })

# --- Profile-3 portrait red-line guard (D-62): params gate intact, no caliber overclaim ---
# check_redline.py exit: 0=all invariants hold (PASS) / 1=violation(s) (FAIL) / 2=env gap
# (pyyaml missing or no yaml found) -> NOT_EXECUTED (honest, per this script's philosophy).
$redlineScript = Join-Path $repo 'spec\portraits\check_redline.py'
if ($py -and (Test-Path $redlineScript)) {
    $out = & $py $redlineScript 2>&1 | Out-String
    $code = $LASTEXITCODE
    $log += "--- portraits-redline (exit $code) ---"
    $log += $out
    if ($code -eq 0) {
        $log += Add-Result 'portraits-redline' 'PASS' 'check_redline.py'
    } elseif ($code -eq 2) {
        $log += Add-Result 'portraits-redline' 'NOT_EXECUTED' (($out -split "`n" | Select-Object -First 1).Trim())
    } else {
        $log += Add-Result 'portraits-redline' 'FAIL' 'red-line violation(s); see log'
    }
} else {
    $missing = @()
    if (-not $py) { $missing += 'python' }
    if (-not (Test-Path $redlineScript)) { $missing += 'check_redline.py' }
    $log += Add-Result 'portraits-redline' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

# --- Profile-3 ADAPTER spec shape gate (T11/D-387) -------------------------------------
# Until now nothing in this chain looked at spec/adapters/ at all: the byte-parity between
# the spec copies and the assets the device actually loads was guarded only by AdapterSpecTest,
# and this script runs assembleDebug, not the unit tests. So editing spec/adapters/*.json and
# forgetting the mirror passed the local gate in silence.
# The gate also refuses any key the app's strict Json would reject — that failure mode is not a
# crash, it is fail-safe returning an EMPTY spec list: every app drops to generic and adapter_obs
# stops persisting (D-54), with nothing reported anywhere. exit: 0=PASS / 1=violation(s).
$adapterScript = Join-Path $repo 'spec\adapters\validate_adapters.py'
if ($py -and (Test-Path $adapterScript)) {
    $out = & $py $adapterScript 2>&1 | Out-String
    $code = $LASTEXITCODE
    $log += "--- adapters-spec (exit $code) ---"
    $log += $out
    if ($code -eq 0) {
        $log += Add-Result 'adapters-spec' 'PASS' 'validate_adapters.py'
    } else {
        $log += Add-Result 'adapters-spec' 'FAIL' 'adapter-spec violation(s); see log'
    }
} else {
    $missing = @()
    if (-not $py) { $missing += 'python' }
    if (-not (Test-Path $adapterScript)) { $missing += 'validate_adapters.py' }
    $log += Add-Result 'adapters-spec' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

# --- ADAPTER spec gate SELF-TEST: reflex tests guard the guard (same pattern as portraits) ---
$adapterTest = Join-Path $repo 'spec\adapters\test_validate_adapters.py'
if ($py -and (Test-Path $adapterTest)) {
    Push-Location (Join-Path $repo 'spec\adapters')
    $out = & $py $adapterTest 2>&1 | Out-String
    $code = $LASTEXITCODE
    Pop-Location
    $log += "--- adapters-spec-unit (exit $code) ---"
    $log += $out
    if ($code -eq 0) {
        $log += Add-Result 'adapters-spec-unit' 'PASS' (($out -split "`n" | Select-Object -First 1).Trim())
    } else {
        $log += Add-Result 'adapters-spec-unit' 'FAIL' 'reflex test(s) failed; see log'
    }
} else {
    $missing = @()
    if (-not $py) { $missing += 'python' }
    if (-not (Test-Path $adapterTest)) { $missing += 'test_validate_adapters.py' }
    $log += Add-Result 'adapters-spec-unit' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

# --- Profile-3 portrait red-line guard SELF-TEST (D-65): reflex tests guard the guard ---
# Runs the self-contained reflex runner (no pytest needed). exit: 0=all reflex tests pass /
# 1=a red/green reflex failed (guard weakened or a rule regressed) -> FAIL.
$redlineTest = Join-Path $repo 'spec\portraits\test_check_redline.py'
if ($py -and (Test-Path $redlineTest)) {
    Push-Location (Join-Path $repo 'spec\portraits')
    $out = & $py $redlineTest 2>&1 | Out-String
    $code = $LASTEXITCODE
    Pop-Location
    $log += "--- portraits-redline-unit (exit $code) ---"
    $log += $out
    if ($code -eq 0) {
        $log += Add-Result 'portraits-redline-unit' 'PASS' (($out -split "`n" | Select-Object -First 1).Trim())
    } else {
        $log += Add-Result 'portraits-redline-unit' 'FAIL' 'reflex test(s) failed; see log'
    }
} else {
    $missing = @()
    if (-not $py) { $missing += 'python' }
    if (-not (Test-Path $redlineTest)) { $missing += 'test_check_redline.py' }
    $log += Add-Result 'portraits-redline-unit' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

# --- AQS 版本冻结守卫 + 其自守卫（SPEC-4 4.1 / D-567；接门半由 SPEC-3 代做）---
# check_versions.py exit: 0=weights 与 AQS_VERSIONS 登记表一致 / 非 0=有未登记或
# 对不上的 version_id。
#
# **自守卫用 pytest 跑，而不是照 portraits 那样 `& $py <file>`**：那份姊妹文件
# （test_check_redline.py）自带 `__main__` runner，直接执行会真跑；而这一份没有
# ——**当脚本执行它，7 条测试一条都不跑、退出码恒 0**（实测：脚本跑零输出 RC=0，
# pytest 跑 7 passed）。照抄形态就会造出一道永远绿的假门，而 gate-integrity 也
# 抓不到（python 在、不抛 CommandNotFoundException）——D-532「从落地起没跑过却
# 每次报 PASS」的同一形状。pytest 缺席时如实记 NOT_EXECUTED，不冒充 PASS。
$versionsScript = Join-Path $repo 'spec\scoring\check_versions.py'
if ($py -and (Test-Path $versionsScript)) {
    $out = & $py $versionsScript 2>&1 | Out-String
    $code = $LASTEXITCODE
    $log += "--- spec-versions (exit $code) ---"
    $log += $out
    if ($code -eq 0) {
        $log += Add-Result 'spec-versions' 'PASS' 'check_versions.py'
    } else {
        $log += Add-Result 'spec-versions' 'FAIL' 'version registry drift; see log'
    }
} else {
    $missing = @()
    if (-not $py) { $missing += 'python' }
    if (-not (Test-Path $versionsScript)) { $missing += 'spec/scoring/check_versions.py' }
    $log += Add-Result 'spec-versions' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

$versionsTest = Join-Path $repo 'spec\scoring\test_check_versions.py'
$hasPytest = $false
if ($py) {
    & $py -c "import pytest" 2>&1 | Out-Null
    $hasPytest = ($LASTEXITCODE -eq 0)
}
if ($py -and $hasPytest -and (Test-Path $versionsTest)) {
    $out = & $py -m pytest $versionsTest -q 2>&1 | Out-String
    $code = $LASTEXITCODE
    $log += "--- spec-versions-unit (exit $code) ---"
    $log += $out
    if ($code -eq 0) {
        $log += Add-Result 'spec-versions-unit' 'PASS' (($out -split "`n" | Where-Object { $_ -match 'passed' } | Select-Object -First 1).Trim())
    } else {
        $log += Add-Result 'spec-versions-unit' 'FAIL' 'reflex test(s) failed; see log'
    }
} else {
    $missing = @()
    if (-not $py) { $missing += 'python' }
    elseif (-not $hasPytest) { $missing += 'pytest（该文件无自带 runner，脚本执行会零测试假绿）' }
    if (-not (Test-Path $versionsTest)) { $missing += 'spec/scoring/test_check_versions.py' }
    $log += Add-Result 'spec-versions-unit' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}


# --- Profile-3 portrait SHAPE gate (spine-3 #6): jsonschema validates the three-layer
# document structure (params / params_fit_approx / observed_*), complementing check_redline
# semantics. exit: 0=PASS / 2=NOT_EXECUTED (pyyaml or jsonschema missing) / else FAIL.
$schemaScript = Join-Path $repo 'spec\portraits\validate_schema.py'
if ($py -and (Test-Path $schemaScript)) {
    $out = & $py $schemaScript 2>&1 | Out-String
    $code = $LASTEXITCODE
    $log += "--- portraits-schema (exit $code) ---"
    $log += $out
    if ($code -eq 0) {
        $log += Add-Result 'portraits-schema' 'PASS' 'validate_schema.py'
    } elseif ($code -eq 2) {
        $log += Add-Result 'portraits-schema' 'NOT_EXECUTED' (($out -split "`n" | Select-Object -First 1).Trim())
    } else {
        $log += Add-Result 'portraits-schema' 'FAIL' 'schema violation(s); see log'
    }
} else {
    $missing = @()
    if (-not $py) { $missing += 'python' }
    if (-not (Test-Path $schemaScript)) { $missing += 'validate_schema.py' }
    $log += Add-Result 'portraits-schema' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

# --- Profile-3 portrait SHAPE gate SELF-TEST (spine-3 #6): reflex tests guard the schema ---
# Self-contained runner (no pytest). exit: 0=all reflex pass / 1=a red/green reflex failed
# (schema weakened or a shape constraint regressed) -> FAIL.
$schemaTest = Join-Path $repo 'spec\portraits\test_portrait_schema.py'
if ($py -and (Test-Path $schemaTest)) {
    Push-Location (Join-Path $repo 'spec\portraits')
    $out = & $py $schemaTest 2>&1 | Out-String
    $code = $LASTEXITCODE
    Pop-Location
    $log += "--- portraits-schema-unit (exit $code) ---"
    $log += $out
    if ($code -eq 0) {
        $log += Add-Result 'portraits-schema-unit' 'PASS' (($out -split "`n" | Select-Object -First 1).Trim())
    } else {
        $log += Add-Result 'portraits-schema-unit' 'FAIL' 'reflex test(s) failed; see log'
    }
} else {
    $missing = @()
    if (-not $py) { $missing += 'python' }
    if (-not (Test-Path $schemaTest)) { $missing += 'test_portrait_schema.py' }
    $log += Add-Result 'portraits-schema-unit' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

}

# ⚠ 这张名单必须与本块内**实际 Add-Result 的门名**逐一对齐：漏登记的门在层外
# 既不跑、也不记 SKIPPED_SCOPE，而是**从汇总里彻底消失**——正是 `Test-InScope`
# 自己注释里写的「沉默的跳过＝没有检查项」。`obs-tools-*` 两道 2026-08-30 补登。
# （它们测的是 `tools/`，归 'scripts' 层是因为那是分析 lane 的层，不是路径前缀。）
if (Test-InScope 'scripts' @('campaign-analysis-unit','results-contract-unit','evidence-rules','corpus-ledger-fresh','obs-tools-e1-unit','obs-tools-e234-unit')) {
# --- 语料台账新鲜度门（T82 §9.2 #12）：台账开篇写着「勿手编」，而此前没有任何
# 东西核对它——手改能一直活到下次重算，期间那两面仍被当作单一事实源引用。
# 本门只比不写：落盘的 md/CSV 必须与现算逐字节相同。不一致的两种成因（有人手改／
# 语料变了没重算）后果相同：被引用的数字不再是当前语料算出来的，故都记 FAIL。
# ⚠ **必须 Push-Location 到仓根**（2026-08-30 实测）：`corpus_ledger.py` 的默认
# `--md`/`--csv` 是**相对路径**（`docs/CORPUS_LEDGER.md`），而本门此前不切目录，
# 于是**同一份代码、同一个仓，从不同 cwd 调 verify_all 会给出不同结论**——
# 实测一次 `-Scope all` 报 FAIL，日志里真正的话是 `No such file or directory`。
# 邻近几道门（campaign-analysis-unit / obs-tools-*）本来就 Push-Location，**只有这道漏了**。
# exit: 0=一致 / 1=真漂移 / 2=**没比成**（读不了，多半是 cwd 不对）——2 不是漂移。
$ledgerScript = Join-Path $repo 'scripts/corpus_ledger.py'
if ($py -and (Test-Path $ledgerScript)) {
    Push-Location $repo
    $out = & $py $ledgerScript --check 2>&1 | Out-String
    $code = $LASTEXITCODE
    Pop-Location
    $log += "--- corpus-ledger-fresh (exit $code) ---"
    $log += $out
    $head = ($out -split "`n" | Where-Object { $_ -match 'corpus ledger check:' } | Select-Object -First 1)
    if ($code -eq 0) {
        $log += Add-Result 'corpus-ledger-fresh' 'PASS' $head
    } elseif ($code -eq 2) {
        # 「没比成」不冒充「比过了、不一致」——判词点对成因，处置才会对
        $log += Add-Result 'corpus-ledger-fresh' 'NOT_EXECUTED' $head
    } else {
        $log += Add-Result 'corpus-ledger-fresh' 'FAIL' $head
    }
} else {
    $missing = @()
    if (-not $py) { $missing += 'python' }
    if (-not (Test-Path $ledgerScript)) { $missing += 'scripts/corpus_ledger.py' }
    $log += Add-Result 'corpus-ledger-fresh' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

# --- evidence/ RULE gate (T82 §9.2 #4/#6/#7/#13/#14): evidence/README 立了六条规则而
# 此前一条都没有守卫。接上五条 + 一条 README 蕴含项（列出的证据文件必须真在盘上）。
# 四态判据从 README 解析，不再抄一份。exit: 0=干净 / 1=有违规或过期豁免 -> FAIL /
# 2=判据缺失（README 解析不出规则 1）-> NOT_EXECUTED，**不冒充 PASS**（D-511/D-532）。
$evidenceGuard = Join-Path $repo 'scripts\check_evidence.py'
if ($py -and (Test-Path $evidenceGuard)) {
    $out = & $py $evidenceGuard --root (Join-Path $repo 'evidence') 2>&1 | Out-String
    $code = $LASTEXITCODE
    $log += "--- evidence-rules (exit $code) ---"
    $log += $out
    $head = ($out -split "`n" | Where-Object { $_ -match 'evidence guard:' } | Select-Object -First 1)
    if ($code -eq 0) {
        $log += Add-Result 'evidence-rules' 'PASS' $head
    } elseif ($code -eq 2) {
        $log += Add-Result 'evidence-rules' 'NOT_EXECUTED' 'evidence/README 解析不出规则 1；判据缺失不放行'
    } else {
        $log += Add-Result 'evidence-rules' 'FAIL' $head
    }
} else {
    $missing = @()
    if (-not $py) { $missing += 'python' }
    if (-not (Test-Path $evidenceGuard)) { $missing += 'scripts/check_evidence.py' }
    $log += Add-Result 'evidence-rules' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

# --- Campaign-level analysis & reporting layer SELF-TEST (D-87): golden reflex tests ---
# Guards scripts/{campaign_common,attribution,campaign_report}.py — three-tier differential
# attribution + point×time×carrier heat card + before/after comparison. Self-contained runner
# (stdlib only, no pytest). exit: 0=all reflex pass / 1=a golden reflex failed -> FAIL.
$campaignTest = Join-Path $repo 'scripts\tests\run_all.py'
if ($py -and (Test-Path $campaignTest)) {
    Push-Location (Join-Path $repo 'scripts\tests')
    $out = & $py $campaignTest 2>&1 | Out-String
    $code = $LASTEXITCODE
    Pop-Location
    $log += "--- campaign-analysis-unit (exit $code) ---"
    $log += $out
    if ($code -eq 0) {
        $log += Add-Result 'campaign-analysis-unit' 'PASS' (($out -split "`n" | Where-Object { $_ -match 'reflex:' } | Select-Object -First 1).Trim())
    } else {
        $log += Add-Result 'campaign-analysis-unit' 'FAIL' 'reflex test(s) failed; see log'
    }
} else {
    $missing = @()
    if (-not $py) { $missing += 'python' }
    if (-not (Test-Path $campaignTest)) { $missing += 'scripts/tests/run_all.py' }
    $log += Add-Result 'campaign-analysis-unit' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

# --- Observation-channel analysis tools SELF-TEST (T81 §7-2, 2026-08-30) ---
# Guards tools/e1/* and tools/e234/* — the E1..E4 collectors/analyzers plus the new
# e2_precheck applicability assertion. Self-contained runners (no pytest).
# exit: 0=all reflex pass / 1=a reflex failed -> FAIL / 5=zero collected -> FAIL.
#
# **为什么现在才接进来**：这两只跑器自 2026-08-02 就存在，`tools/e1/tests/run_tests.py`
# 的 docstring 逐字写着三态退出码「以便直接接进 `scripts/verify_all.ps1`」——
# **而它们从未被接进来**（2026-08-30 全仓核：只有 docs 与两份 README 提到它们，
# 本文件零引用）。于是 180+ 条守卫观察通道分析工具的反例，**只在有人手动想起时才跑**。
#
# 这不是 D-532 那种「门没跑却报 PASS」，是更安静的一种：**门是绿的、也是真绿的，
# 只是不在清单上** —— `gate_count` 从来没把它们数进去，所以谁也不会发现少了什么。
# ⇒ **「写好了一道门」与「那道门在门禁清单上」是两件事**，后者要单独去核；
# 而**自称「已备好接入」的东西最容易被当成已接入**——那句话本身读起来就像完成态。
#
# 5 也判 FAIL：零收集意味着枚举坏了或目录空了，那时「全绿」是假的（D-275/D-364）。
foreach ($obsSuite in @(
    @{ Name = 'obs-tools-e1-unit';   Dir = 'tools/e1/tests' },
    @{ Name = 'obs-tools-e234-unit'; Dir = 'tools/e234/tests' })) {
    $obsDir = Join-Path $repo $obsSuite.Dir
    $obsRunner = Join-Path $obsDir 'run_tests.py'
    if ($py -and (Test-Path $obsRunner)) {
        Push-Location $obsDir
        $out = & $py $obsRunner 2>&1 | Out-String
        $code = $LASTEXITCODE
        Pop-Location
        $log += ("--- " + $obsSuite.Name + " (exit $code) ---")
        $log += $out
        if ($code -eq 0) {
            $log += Add-Result $obsSuite.Name 'PASS' (($out -split "`n" | Where-Object { $_ -match 'reflex:' } | Select-Object -First 1).Trim())
        } elseif ($code -eq 5) {
            $log += Add-Result $obsSuite.Name 'FAIL' 'zero tests collected (enumeration broken or dir empty)'
        } else {
            $log += Add-Result $obsSuite.Name 'FAIL' 'reflex test(s) failed; see log'
        }
    } else {
        $missing = @()
        if (-not $py) { $missing += 'python' }
        if (-not (Test-Path $obsRunner)) { $missing += ($obsSuite.Dir + '/run_tests.py') }
        $log += Add-Result $obsSuite.Name 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
    }
}

# --- Result JSONL INPUT CONTRACT gate (D-97): validate the committed corpus against
# spec/schemas/result-run.schema.json (structural required/const/enum) + the R-10
# cross-field invariants draft-07 cannot express (value<->grade null coupling,
# aqs.score<->reason, histogram counts==edges+1). Guards the analysis layer's inputs.
# exit: 0=contract holds -> PASS / 2=no corpus or schema unreadable -> NOT_EXECUTED /
# else=violations -> FAIL. Validity CASE drift is a non-fatal advisory, not a failure.
$contractScript = Join-Path $repo 'scripts\validate_results.py'
$resultsGlob = Join-Path $repo 'server\data\results\*.jsonl'
if ($py -and (Test-Path $contractScript)) {
    $out = & $py $contractScript $resultsGlob 2>&1 | Out-String
    $code = $LASTEXITCODE
    $log += "--- results-contract-unit (exit $code) ---"
    $log += $out
    if ($code -eq 0) {
        $log += Add-Result 'results-contract-unit' 'PASS' (($out -split "`n" | Where-Object { $_ -match 'contract OK' } | Select-Object -First 1).Trim())
    } elseif ($code -eq 2) {
        $log += Add-Result 'results-contract-unit' 'NOT_EXECUTED' 'no result corpus to validate'
    } else {
        $log += Add-Result 'results-contract-unit' 'FAIL' 'contract violation(s); see log'
    }
} else {
    $missing = @()
    if (-not $py) { $missing += 'python' }
    if (-not (Test-Path $contractScript)) { $missing += 'scripts/validate_results.py' }
    $log += Add-Result 'results-contract-unit' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

}

if (Test-InScope 'spec' @('spec-scoring-unit','profiles-deep','voice-plan-parity')) {
# --- Spec SCORING-PACK gate (D-102): the authoritative parity guard
# (SpecScoringParityTest.kt) is Android-toolchain-gated, so in the usual no-Android
# run the scoring YAMLs are ungated. This validates the invariants they declare:
# weights Σ=1.0, anchor points strictly ascending, veto structure. Reads spec/scoring
# (never writes it). exit: 0=PASS / 2=pyyaml missing or files absent -> NOT_EXECUTED /
# else=violations -> FAIL.
$scoringScript = Join-Path $repo 'scripts\validate_spec_scoring.py'
if ($py -and (Test-Path $scoringScript)) {
    $out = & $py $scoringScript 2>&1 | Out-String
    $code = $LASTEXITCODE
    $log += "--- spec-scoring-unit (exit $code) ---"
    $log += $out
    if ($code -eq 0) {
        $log += Add-Result 'spec-scoring-unit' 'PASS' (($out -split "`n" | Where-Object { $_ -match 'spec-scoring OK' } | Select-Object -First 1).Trim())
    } elseif ($code -eq 2) {
        $log += Add-Result 'spec-scoring-unit' 'NOT_EXECUTED' 'pyyaml missing or no scoring files'
    } else {
        $log += Add-Result 'spec-scoring-unit' 'FAIL' 'scoring invariant violation(s); see log'
    }
} else {
    $missing = @()
    if (-not $py) { $missing += 'python' }
    if (-not (Test-Path $scoringScript)) { $missing += 'scripts/validate_spec_scoring.py' }
    $log += Add-Result 'spec-scoring-unit' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

# --- Profile spec<->runtime PARITY + structure gate (D-103): the inline
# profiles-valid step above checks only the runtime copy's 4 fields; this deepens it
# with semantic spec<->runtime parity (server profiles have no parity guard) and
# per-phase structure. Reads spec/profiles/server + profiles (never writes them).
# exit: 0=PASS / 2=a tree absent -> NOT_EXECUTED / else=violations -> FAIL.
$profilesScript = Join-Path $repo 'scripts\validate_profiles.py'
if ($py -and (Test-Path $profilesScript)) {
    $out = & $py $profilesScript 2>&1 | Out-String
    $code = $LASTEXITCODE
    $log += "--- profiles-deep (exit $code) ---"
    $log += $out
    if ($code -eq 0) {
        $log += Add-Result 'profiles-deep' 'PASS' (($out -split "`n" | Where-Object { $_ -match 'profiles OK' } | Select-Object -First 1).Trim())
    } elseif ($code -eq 2) {
        $log += Add-Result 'profiles-deep' 'NOT_EXECUTED' 'profile tree(s) absent'
    } else {
        $log += Add-Result 'profiles-deep' 'FAIL' 'profile parity/structure violation(s); see log'
    }
} else {
    $missing = @()
    if (-not $py) { $missing += 'python' }
    if (-not (Test-Path $profilesScript)) { $missing += 'scripts/validate_profiles.py' }
    $log += Add-Result 'profiles-deep' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

# --- Profile-4 VOICE execution-plan parity gate (D-390 5.1): same shape as
# spec-scoring-unit above, and for the same reason -- VoiceExecutionPlanParityTest.kt
# is Android-toolchain-gated and this script runs assembleDebug, not the unit tests.
# Worse, it was MEASURED not to run even by hand: Gradle marks testDebugUnitTest
# UP-TO-DATE when only a file outside the module changed, so three separate spec
# mutations all survived. This checker is the one that actually gates. It reads the
# Kotlin source and compares the exported numbers against the constants they mirror
# (which validate_spec_scoring.py deliberately does not do), plus the file's own
# invariants. Reads spec/profiles/client + app/.../VoiceRunner.kt, never writes.
# exit: 0=PASS / 2=an input absent -> NOT_EXECUTED / else=violations -> FAIL.
$voicePlanScript = Join-Path $repo 'scripts\validate_voice_plan.py'
if ($py -and (Test-Path $voicePlanScript)) {
    $out = & $py $voicePlanScript 2>&1 | Out-String
    $code = $LASTEXITCODE
    $log += "--- voice-plan-parity (exit $code) ---"
    $log += $out
    if ($code -eq 0) {
        $log += Add-Result 'voice-plan-parity' 'PASS' (($out -split "`n" | Where-Object { $_ -match 'voice plan parity OK' } | Select-Object -First 1).Trim())
    } elseif ($code -eq 2) {
        $log += Add-Result 'voice-plan-parity' 'NOT_EXECUTED' 'spec or VoiceRunner.kt absent'
    } else {
        $log += Add-Result 'voice-plan-parity' 'FAIL' 'voice plan spec<->code drift; see log'
    }
} else {
    $missing = @()
    if (-not $py) { $missing += 'python' }
    if (-not (Test-Path $voicePlanScript)) { $missing += 'scripts/validate_voice_plan.py' }
    $log += Add-Result 'voice-plan-parity' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

}

if (Test-InScope 'app' @('app-assembleDebug','app-parity-tests','app-unit-tests-full','app-release-signing')) {
# --- app toolchain probe (build requires JDK + Android SDK) ---
$jdk = $null; try { $jdk = (Get-Command java -ErrorAction Stop).Source } catch {}
$sdk = ($env:ANDROID_HOME) -or (Test-Path "$env:LOCALAPPDATA\Android\Sdk")
$wrapperJar = Test-Path (Join-Path $repo 'app\gradle\wrapper\gradle-wrapper.jar')
if ($jdk -and $sdk -and $wrapperJar) {
    Push-Location (Join-Path $repo 'app')
    $out = & .\gradlew.bat ':probe:assembleDebug' '--no-daemon' 2>&1 | Out-String
    $state = if ($LASTEXITCODE -eq 0) { 'PASS' } else { 'FAIL' }
    $log += $out
    $log += Add-Result 'app-assembleDebug' $state 'gradlew :probe:assembleDebug'
    Pop-Location
} else {
    $missing = @()
    if (-not $jdk) { $missing += 'JDK' }
    if (-not $sdk) { $missing += 'AndroidSDK' }
    if (-not $wrapperJar) { $missing += 'gradle-wrapper.jar' }
    $log += Add-Result 'app-assembleDebug' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

# --- spec<->runtime PARITY tests, forced to actually run (D-391/D-394 red line 2.16)
# Until now this gate ran assembleDebug only, so ClientProfileDataParityTest /
# SpecScoringParityTest / AdapterSpecTest / VoiceExecutionPlanParityTest were never
# executed here at all -- and even by hand Gradle skipped them as UP-TO-DATE whenever
# only a file OUTSIDE the module changed (measured: three spec mutations all survived).
# The whole "export + parity" discipline rested on tests nothing was running.
# Task-scoped --rerun forces just this task, not the upstream chain: measured 9-12s
# here versus 129s for --rerun-tasks, and a spec mutation is CAUGHT either way.
if ($jdk -and $sdk -and $wrapperJar) {
    Push-Location (Join-Path $repo 'app')
    $out = & .\gradlew.bat ':probe:testDebugUnitTest' '--tests' '*ParityTest' `
        '--tests' '*AdapterSpecTest' '--rerun' '--no-daemon' 2>&1 | Out-String
    $state = if ($LASTEXITCODE -eq 0) { 'PASS' } else { 'FAIL' }
    $log += "--- app-parity-tests ---"
    $log += $out
    $log += Add-Result 'app-parity-tests' $state 'gradlew :probe:testDebugUnitTest --tests *ParityTest --tests *AdapterSpecTest --rerun'

    # --- FULL unit-test gate (T69, closes T67/D-514 finding G-1) ---
    # Before this, the chain ran only *ParityTest + *AdapterSpecTest. Every other unit test
    # (RttDominanceGuardTest, MigrationRegistryTest, KpiCalculator*, AqsScorer*, the 13
    # MigrationV*Test files, ...) sat OUTSIDE the standing chain: whether it ran depended on
    # a human remembering, not on a gate. That rewrote the meaning of every "has a test"
    # claim in this repo -- "tested" only ever meant "someone ran it by hand once".
    #
    # Why viable only now: the comment above records that Gradle marked testDebugUnitTest
    # UP-TO-DATE whenever a file OUTSIDE the module changed, so spec mutations survived.
    # That root cause was fixed in T66/D-508 + T68/D-517 by declaring the repo-root
    # spec/profiles/assets/schemas dirs as test inputs in app/probe/build.gradle.kts.
    # Task-scoped --rerun additionally forces this task regardless of up-to-date state.
    #
    # The parity gate above is deliberately KEPT as its own check so a parity break is still
    # named distinctly in the summary instead of being buried in a whole-suite FAIL.
    #
    # 工作目录：本块从头到尾必须留在 `app/`。**Pop-Location 曾在这一步之前**，于是本门
    # 在仓库根下调 `.\gradlew.bat` —— 那里根本没有这个文件（wrapper 在 `app/`）。
    # PowerShell 的 CommandNotFoundException **不设 `$LASTEXITCODE`**，于是它沿用上面
    # parity 那次成功的 0，判据算出 **PASS**：**这道门从落地起就一次没跑过，却每次都报绿**
    # ——恰是它被创建来消灭的那个毛病（D-518：「有测试」只意味着「有人手工跑过」），
    # 也是本仓「守卫管道退出码陷阱」红线的同一形状。日志里那行 `.\gradlew.bat 不存在`
    # 与汇总里的 PASS 并排出现，是发现它的直接证据。
    $out = & .\gradlew.bat ':probe:testDebugUnitTest' '--rerun' '--no-daemon' 2>&1 | Out-String
    $state = if ($LASTEXITCODE -eq 0) { 'PASS' } else { 'FAIL' }
    Pop-Location
    $log += "--- app-unit-tests-full ---"
    $log += $out
    $log += Add-Result 'app-unit-tests-full' $state 'gradlew :probe:testDebugUnitTest --rerun (whole suite)'
} else {
    $missing = @()
    if (-not $jdk) { $missing += 'JDK' }
    if (-not $sdk) { $missing += 'AndroidSDK' }
    if (-not $wrapperJar) { $missing += 'gradle-wrapper.jar' }
    $log += Add-Result 'app-parity-tests' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
    $log += Add-Result 'app-unit-tests-full' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

# --- release signing dual-track (T58b / D-500(4)) ---
# The signingConfig fallback lives in build.gradle.kts, where no JVM unit test can reach it.
# Both directions matter, asymmetrically: "no keys -> unsigned, build still succeeds" failing
# is loud (collaborators' builds break), but "keys present yet silently produced an UNSIGNED
# apk" is the dangerous one -- it is only discovered at install time. The script verifies both
# and reports SKIP (not PASS) when no keystore is configured, so "not verified" never looks
# like "verified". It restores local.properties in a finally block.
$signScript = Join-Path $repo 'scripts/verify_signing_fallback.ps1'
if ($jdk -and $sdk -and $wrapperJar -and (Test-Path $signScript)) {
    $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $signScript 2>&1 | Out-String
    $state = if ($LASTEXITCODE -eq 0) { 'PASS' } else { 'FAIL' }
    $log += "--- app-release-signing ---"
    $log += $out
    $log += Add-Result 'app-release-signing' $state 'scripts/verify_signing_fallback.ps1 (signed + unsigned-fallback)'
} else {
    $missing = @()
    if (-not $jdk) { $missing += 'JDK' }
    if (-not $sdk) { $missing += 'AndroidSDK' }
    if (-not $wrapperJar) { $missing += 'gradle-wrapper.jar' }
    if (-not (Test-Path $signScript)) { $missing += 'verify_signing_fallback.ps1' }
    $log += Add-Result 'app-release-signing' 'NOT_EXECUTED' ("missing: " + ($missing -join ', '))
}

}


# --- summary（先算清，再按归档策略落盘；SPEC-3 §3.2/T81）---
$failed  = @($results | Where-Object { $_.state -eq 'FAIL' })
$notRun  = @($results | Where-Object { $_.state -eq 'NOT_EXECUTED' })
$skipped = @($results | Where-Object { $_.state -eq 'SKIPPED_SCOPE' })
$sum = @()
$sum += ''
$sum += "=== verify_all summary (scope: $Scope) ==="
$sum += ($results | ForEach-Object { "{0,-14} {1}  {2}" -f $_.state, $_.check, $_.detail })
$sum += ("checks: {0} total / {1} FAIL / {2} NOT_EXECUTED / {3} SKIPPED_SCOPE" -f `
    $results.Count, $failed.Count, $notRun.Count, $skipped.Count)

# --- NOT_EXECUTED must be visible, not silently folded into a green run (T69, G-1) ---
# SPEC-3 §3.2（T81，2026-08-28）把 -Strict 翻为**默认开**：NOT_EXECUTED 不折算 PASS
# 是本仓四态证据的核心语义（诊断 §2.3 保①），此前「不翻默认」的顾虑（惊扰他会话）
# 由 PO 裁定解除；要旧行为用 -Lenient 显式退出。SKIPPED_SCOPE 与 NOT_EXECUTED 是
# 两回事：前者=操作者主动圈定范围（本次没请它验），后者=想验而验不了。
if ($notRun.Count -gt 0) {
    $sum += 'NOT_EXECUTED checks (these verified NOTHING):'
    $sum += ($notRun | ForEach-Object { "  - {0}  {1}" -f $_.check, $_.detail })
    if (-not $Strict) { $sum += '  (-Lenient 生效：exit code 忽略这些——它们仍一个都没验)' }
}
if ($skipped.Count -gt 0) {
    $sum += ("SKIPPED_SCOPE checks (out of -Scope {0}; 收官/入册前必须补跑 -Scope all):" -f $Scope)
    $sum += ($skipped | ForEach-Object { "  - {0}" -f $_.check })
}

# --- guard for the guards（D-532）：判据语义原样保留 ---
# 有没有哪一步的命令**根本没启动过**。CommandNotFoundException 不设 $LASTEXITCODE，
# "if ($LASTEXITCODE -eq 0)" 会沿用上一条成功的 0——app 全量单测门曾因此从落地起
# 一次没跑过却每次报 PASS。字符串签名初版被突变证伪（语句级错误在管道启动前
# 抛出，2>&1 捕不到），故查 $Error；探针的裸名字探测（python/go/java）是设计行为，
# 判别=目标名长得像路径或带 bat/cmd/exe 扩展。
$ghosts = @($Error | Where-Object {
    $_.CategoryInfo.Reason -eq 'CommandNotFoundException' -and
    ($_.CategoryInfo.TargetName -match '[\\/]' -or $_.CategoryInfo.TargetName -match '\.(bat|cmd|exe)$')
})
if ($ghosts.Count -gt 0) {
    $sum += ''
    $sum += 'FAIL  gate-integrity  某一步的命令根本没启动（命令不存在），其 PASS 不可信'
    $sum += ($ghosts | ForEach-Object { '  找不到的命令: ' + $_.CategoryInfo.TargetName } | Select-Object -Unique)
    $sum += '  为什么这会造出假绿: CommandNotFoundException 不设 $LASTEXITCODE,'
    $sum += '  于是 "if ($LASTEXITCODE -eq 0) { PASS }" 会沿用上一条命令成功的 0（D-532 实例）'
    $sum += '  处置: 先修工作目录/命令路径再重跑；在此之前本次汇总里的 PASS 都不可信'
}
$log += $sum
$sum | ForEach-Object { $_ }

# --- 归档策略（SPEC-3 §3.2）：只归档「收官全绿」与「红门样本」——日常分层跑
# 不落 evidence（诊断实测 274 份日志全入库是流程开销大头）。收官全绿 =
# ⚠ 2026-08-29 起 `.gitignore` 忽略 `evidence/phase0/verify_all_*.log`
#（T86/D-586）。脚本照常写盘，但**要把某次留成证据必须 `git add -f`**——
# 普通 `git add` 会报错并退出 1（实测：点名该文件+提示 -f，非静默）。
# 已跟踪的旧日志不受影响；被 STATUS.json/badges.txt 点名的那几份仍在库。
# -Scope all 且 0 FAIL、0 NOT_EXECUTED、无幽灵；红门样本 = 任一 FAIL 或幽灵
# （任意 scope——红的诊断价值要留档）。其余写到 TEMP，路径照样打印。
$isRed = ($failed.Count -gt 0) -or ($ghosts.Count -gt 0)
$isFinalGreen = ($Scope -eq 'all') -and (-not $isRed) -and ($notRun.Count -eq 0)
if ($isRed -or $isFinalGreen) {
    $log -join "`r`n" | Out-File -Encoding utf8 $logPath
    "log: $logPath  ($(if ($isRed) { '红门样本归档' } else { '收官全绿归档' }))"
    # ⚠ **顺序是承重的：徽章必须在清单之前刷新**（2026-08-30，D-612）。
    # 原先清单写在徽章之前 ⇒ 写清单那一刻 `badges.txt` 还是**上一跑**那份 ⇒
    # **清单里 badges 的哈希从来没对过一次**（0/2：首跑该文件还不存在被漏收；
    # 此后每次归档跑都记成陈旧值）。比特级实证：清单记的值 ＝ 拿上一次归档日志
    # 重跑 `badges.py` 得到的字节。而 `badges.py` 把来源日志名写进正文、`$ts` 每跑必变
    # ⇒ 内容每跑都不同，不存在"碰巧相同蒙混过关"的分支。
    #
    # **这条能活到今天，是因为清单没有读者**：全仓没有任何守卫/测试回读它
    # （`check_evidence.py` 对 manifest/sha256/badges 三词零命中）。
    # ⇒ **描述别人的产物必须最后生成；而一份没有读者的清单，这种错永远不会自己报出来。**
    #
    # ⚠ 反向脚注（比正向更要紧）：**清单与 badges「相符」不是健康信号**——
    # 徽章那步 `NOT_EXECUTED` 或写出前失败时 badges.txt 没被改写，清单反而相符。
    # 所以判据是顺序，不是"这次对上了没有"。
    # --- 徽章值（SPEC-4 4.4 砍④脚本侧）：只在**归档的那几次**产出，
    # 因为徽章的新鲜度就是来源日志的新鲜度——分层跑不落 evidence，也就
    # 不该去覆盖一份看起来像"刚测的"徽章。测不到的项由脚本写 unknown。
    # 路径用**正斜杠**：本行初版写作 scripts 反斜杠-b adges.py 那种形式，
    # 而那个「反斜杠-b」在落盘时被吞成**一个真实退格符 0x08**（heredoc 转义坑）。
    # grep 与编辑器都把它渲染没了，肉眼与工具都看不出异常——**这正是它能活下来的原因**。
    # 后果：Test-Path 恒 False，而当时 if 又**没有 else**，于是这条接线自 3a1577a 起
    # 一次都没跑过、也一次都没吭声，`badges.txt` 因此从不存在（D-532 的纯粹形态）。
    # 正斜杠在 Windows 上照样解析，且对这一整类吞字免疫。
    $badgeScript = Join-Path $repo 'scripts/badges.py'
    if ($py -and (Test-Path $badgeScript)) {
        & $py $badgeScript --log $logPath 2>&1 | Out-String | Write-Output
    } else {
        # 静默跳过正是上面那个 bug 能活这么久的原因；缺什么就说什么。
        $bm = @()
        if (-not $py) { $bm += 'python' }
        if (-not (Test-Path $badgeScript)) { $bm += 'scripts/badges.py' }
        "badges: NOT_EXECUTED (missing: $($bm -join ', ')) —— 徽章未刷新"
    }
    # --- regenerate sha256 manifest for evidence/phase0 (scripted, never manual) ---
    # **必须排在徽章之后**（见上方 D-612 注释）：清单描述的是 evidence/phase0 的现态，
    # 而 badges.txt 是本块里最后一个被写的文件。**无条件执行**，不得并进上面的
    # `if ($py -and ...)` 分支——徽章没刷新时清单照样要记录当时的真实现态。
    $manifestPath = Join-Path $evidenceDir 'sha256-manifest.txt'
    $evRel = $evidenceDir.Substring($repo.Length + 1) -replace '\\', '/'

    # T89(b)：先整批取出「未跟踪且被 .gitignore 忽略」的文件，**一次 git 调用**，
    # 别每个文件跑一次 check-ignore（清单三百多条，那是三百多次进程）。
    # 为什么要排除：这些绝大多数是 verify_all_*.log 运行日志，只在本机存在
    # ⇒ 留着会让**清单内容变成「本 checkout 跑过多少次」的函数**，
    # 每跑一次就多一行**别的 checkout 无从复核**的行。清单的用处正是让别人能核。
    # ⚠ 判据是 check-ignore 语义（未跟踪 **且** 被忽略），**不是**「未跟踪」——
    # 刚产生、马上要入库的证据文件是未跟踪但不被忽略的，它必须进清单。
    # ⚠ 已跟踪的 verify_all_*.log（在 .gitignore 那条规则之前入过库的）**照收**：
    # 别的 checkout 确实有它们、核得动，排除它们才是丢信息。
    $ignoredSet = @{}
    $gitOk = $false
    # ⚠ **失败必须朝「不排除」那侧倒**：git 缺失时 `& git` 不会自己把 $LASTEXITCODE
    # 置非零，它会**留着上一条命令的值**——若那个值恰好是 0，就会走进「已排除」分支、
    # 拿一个空集合当结果，然后**宣称排除过**。（同族即本文件 §673 记的 D-532。）
    # 所以先探 git 是否存在，再把 $LASTEXITCODE 预置成哨兵 99：git 真跑过才会被覆盖。
    # ⚠⚠ 必须写 `$global:` —— 首跑实测（2026-08-30）：裸写 `$LASTEXITCODE = 99`
    # 会在**脚本作用域**新建一个局部变量把全局那个遮住，而 `& git` 写的是全局那个
    # ⇒ 读回来永远是 99、`$gitOk` 永远 false、**排除功能整个静默失效**。
    # 三个独立脚本一次只变一个量测过：局部赋值读 99／`$global:` 读 0／不预置读 0。
    # 它当时没变成假绿，只因为哨兵朝安全侧倒 + stdout 会明说「未能排除」——
    # **那句话是唯一的告警**，所以下面那行 $mnote 不许省。
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $global:LASTEXITCODE = 99
        $ign = & git -C $repo ls-files --others --ignored --exclude-standard -- $evRel 2>$null
        if ($LASTEXITCODE -eq 0) {
            $gitOk = $true
            foreach ($ip in $ign) { if ($ip) { $ignoredSet[$ip.Trim()] = $true } }
        }
    }

    $mlines = @()
    $skipped = 0
    # T89(c)：过滤清单自身用**全路径**比较，不用 `.Name`。
    # 原先写 `$_.Name -ne 'sha256-manifest.txt'` 而这里带 `-Recurse`
    # ⇒ 任何子目录里的同名文件也会被静默排除，且不报错。
    Get-ChildItem $evidenceDir -Recurse -File | Where-Object { $_.FullName -ne $manifestPath } | Sort-Object FullName | ForEach-Object {
        $rel = $_.FullName.Substring($evidenceDir.Length + 1) -replace '\\', '/'
        if ($gitOk -and $ignoredSet.ContainsKey("$evRel/$rel")) { $skipped++; return }
        $h = (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLower()
        $mlines += "$h  $rel"
    }

    # T89(a)：让清单**自述**它是什么。此前它没有表头，读者只能从文件名猜，
    # 于是哈希对不上时第一反应是「内容被改了」，而最常见的真因是行尾形态不同。
    # ⚠ 表头里**不写条数**——写了就每跑一次变一次，正好抵消上面消 churn 的目的；
    # 条数走 stdout / 本次 verify_all 日志。
    $mhdr = @(
        '# evidence/phase0 的 SHA256 清单 —— 由 scripts/verify_all.ps1（-Scope all）自动重算，勿手编。',
        '# 【这是本机 checkout 的形态快照，不是仓库内容的规范哈希】：文件落到磁盘的字节',
        '# 受本机 core.autocrlf 与 .gitattributes 影响，换一台机器 checkout 出来的行尾可能不同。',
        '# ⇒ 哈希对不上时**先核行尾形态，再怀疑内容被改**。（全仓行尾策略单列待裁，试点期禁动。）',
        '# 已排除两类：①清单自身；②本 checkout 中被 .gitignore 忽略的未跟踪文件',
        '#   （绝大多数是 verify_all_*.log 运行日志，只在本机存在、别处无从复核）。',
        '# ⚠ 因此本清单**不含当次运行日志**；当次日志路径见 badges.txt 与本次 verify_all 输出。',
        '# 行格式：<sha256 小写><两个空格><相对 evidence/phase0 的路径，斜杠分隔>；`#` 开头为注释。'
    )
    ($mhdr + $mlines) -join "`r`n" | Out-File -Encoding utf8 $manifestPath
    $mnote = if ($gitOk) { "，已排除 gitignored $skipped 条" } else { '；⚠ git 不可用，未能排除 gitignored' }
    "manifest: $manifestPath ($($mlines.Count) files$mnote)"
} else {
    $scratchLog = Join-Path $env:TEMP ("verify_{0}_{1}.log" -f $Scope, $ts)
    $log -join "`r`n" | Out-File -Encoding utf8 $scratchLog
    "log: $scratchLog  (未归档——分层/非收官跑不落 evidence，SPEC-3 §3.2)"
}

if ($ghosts.Count -gt 0) { exit 1 }
if ($failed.Count -gt 0) { exit 1 }
if ($Strict -and $notRun.Count -gt 0) { exit 1 }
exit 0