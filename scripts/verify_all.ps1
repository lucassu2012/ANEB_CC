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
$ts = Get-Date -Format 'yyyyMMdd-HHmmss'
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

if (Test-InScope 'scripts' @('campaign-analysis-unit','results-contract-unit','evidence-rules')) {
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
# -Scope all 且 0 FAIL、0 NOT_EXECUTED、无幽灵；红门样本 = 任一 FAIL 或幽灵
# （任意 scope——红的诊断价值要留档）。其余写到 TEMP，路径照样打印。
$isRed = ($failed.Count -gt 0) -or ($ghosts.Count -gt 0)
$isFinalGreen = ($Scope -eq 'all') -and (-not $isRed) -and ($notRun.Count -eq 0)
if ($isRed -or $isFinalGreen) {
    $log -join "`r`n" | Out-File -Encoding utf8 $logPath
    # --- regenerate sha256 manifest for evidence/phase0 (scripted, never manual) ---
    $manifestPath = Join-Path $evidenceDir 'sha256-manifest.txt'
    $mlines = @()
    Get-ChildItem $evidenceDir -Recurse -File | Where-Object { $_.Name -ne 'sha256-manifest.txt' } | Sort-Object FullName | ForEach-Object {
        $h = (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLower()
        $rel = $_.FullName.Substring($evidenceDir.Length + 1) -replace '\\', '/'
        $mlines += "$h  $rel"
    }
    $mlines -join "`r`n" | Out-File -Encoding utf8 $manifestPath
    "log: $logPath  ($(if ($isRed) { '红门样本归档' } else { '收官全绿归档' }))"
    "manifest: $manifestPath ($($mlines.Count) files)"
    # --- 徽章值（SPEC-4 4.4 砍④脚本侧）：只在**归档的那几次**产出，
    # 因为徽章的新鲜度就是来源日志的新鲜度——分层跑不落 evidence，也就
    # 不该去覆盖一份看起来像"刚测的"徽章。测不到的项由脚本写 unknown。
    $badgeScript = Join-Path $repo 'scriptsadges.py'
    if ($py -and (Test-Path $badgeScript)) {
        & $py $badgeScript --log $logPath 2>&1 | Out-String | Write-Output
    }
} else {
    $scratchLog = Join-Path $env:TEMP ("verify_{0}_{1}.log" -f $Scope, $ts)
    $log -join "`r`n" | Out-File -Encoding utf8 $scratchLog
    "log: $scratchLog  (未归档——分层/非收官跑不落 evidence，SPEC-3 §3.2)"
}

if ($ghosts.Count -gt 0) { exit 1 }
if ($failed.Count -gt 0) { exit 1 }
if ($Strict -and $notRun.Count -gt 0) { exit 1 }
exit 0