# ANEB Probe verify_all - phase 0 verification chain (ASCII-only for PS 5.1 compatibility)
# Runs: server vet/build/test, profile JSON validation, portrait red-line guard, app toolchain probe.
# Writes: evidence/phase0/verify_all_<ts>.log (utf8) and regenerates evidence/phase0/sha256-manifest.txt
# Exit code: 0 if no FAIL (NOT_EXECUTED allowed), 1 otherwise.

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

$log = @()
$log += "verify_all run at $ts"
$log += "repo: $repo"

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
$py = $null
foreach ($c in @('python', 'python3', 'py')) { try { $py = (Get-Command $c -ErrorAction Stop).Source; break } catch {} }
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

# --- write log (utf8, never UTF-16) ---
$log -join "`r`n" | Out-File -Encoding utf8 $logPath

# --- regenerate sha256 manifest for evidence/phase0 (scripted, never manual) ---
$manifestPath = Join-Path $evidenceDir 'sha256-manifest.txt'
$lines = @()
Get-ChildItem $evidenceDir -Recurse -File | Where-Object { $_.Name -ne 'sha256-manifest.txt' } | Sort-Object FullName | ForEach-Object {
    $h = (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLower()
    $rel = $_.FullName.Substring($evidenceDir.Length + 1) -replace '\\', '/'
    $lines += "$h  $rel"
}
$lines -join "`r`n" | Out-File -Encoding utf8 $manifestPath

# --- summary ---
''
'=== verify_all summary ==='
$results | ForEach-Object { "{0,-14} {1}  {2}" -f $_.state, $_.check, $_.detail }
"log: $logPath"
"manifest: $manifestPath ($($lines.Count) files)"
$failed = @($results | Where-Object { $_.state -eq 'FAIL' })
if ($failed.Count -gt 0) { exit 1 } else { exit 0 }
