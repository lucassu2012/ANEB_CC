<#
.SYNOPSIS
  重算某个 evidence 目录的 SHA256 清单。**默认只报不写。**

.DESCRIPTION
  本文件是从 `verify_all.ps1` 的归档块**提取**出来的同一段逻辑（不是第二个生成器）——
  链跑照旧调它并传 `evidence/phase0`，链外可手工调它传别的目录。
  **不许再写第三个**：四份清单三种格式，正是因为它们曾被不同的东西在不同时候生成，
  而它制造的不符与真不符长得一模一样。

  🔴 **为什么需要链外这条路**：`verify_all.ps1` 只在「收官全绿」时重算清单
  （D-825／(a′)）。而哈希门（`scripts/tests/test_manifest_hashes.py`）一旦红，
  `campaign-analysis-unit` 即 FAIL ⇒ `$isFinalGreen` 恒假 ⇒ **链永远解不开它自己**。
  那是设计（红要持久），**本脚本就是唯一的在册解锁路径**。

  🔴 **它天生是一个「洗白按钮」，所以默认不写盘**：不问成因就重算，
  等于把一次没人解释得清的改动洗成「正确」，而清单从此为它背书。
  ⇒ 默认逐条打印 old→new 让人先看；真要写必须显式 `-Write`；
  **提交说明里每条变化各写一句成因**。让分类那一步无法被跳过，是本工具唯一要防的东西。

  ⚠ **不要拿它去「归一」phase1/2/3 的格式**（2026-09-07 裁不做）：phase0 的表头自述
  「由 verify_all.ps1 自动重算」，而那三份**不由**链跑重算、也不许由链跑重算 ⇒
  把这套表头写进去就是写进一句假话。三种格式作为已知债务保留，由形态用例钉住。

.PARAMETER Write
  真正写盘。不给则只报不写（退出码仍为 0——**「有差异」不是失败，是要人来判**）。
#>
param(
    [Parameter(Mandatory = $true)][string]$EvidenceDir,
    [string]$Repo,
    [switch]$Write)

$ErrorActionPreference = 'Continue'
if (-not $Repo) { $Repo = Split-Path -Parent $PSScriptRoot }
$evidenceDir = (Resolve-Path -LiteralPath $EvidenceDir).Path.TrimEnd('\')
$manifestPath = Join-Path $evidenceDir 'sha256-manifest.txt'
$evRel = $evidenceDir.Substring($Repo.Length + 1) -replace '\\', '/'

# T89(b)：先整批取出「未跟踪且被 .gitignore 忽略」的文件，**一次 git 调用**。
# ⚠ **失败必须朝「不排除」那侧倒**：git 缺失时 `& git` 不会自己把 $LASTEXITCODE 置位，
# 于是先探 git 是否存在，再把 $LASTEXITCODE 预置成哨兵 99：git 真跑过才会被覆盖。
$ignoredSet = @{}
$gitOk = $false
if (Get-Command git -ErrorAction SilentlyContinue) {
    $global:LASTEXITCODE = 99
    $ign = & git -C $Repo ls-files --others --ignored --exclude-standard -- $evRel 2>$null
    if ($LASTEXITCODE -eq 0) {
        $gitOk = $true
        foreach ($f in $ign) { if ($f) { $ignoredSet[$f] = $true } }
    }
}

$mlines = @()
$newMap = @{}
$skipped = 0
Get-ChildItem $evidenceDir -Recurse -File | Where-Object { $_.FullName -ne $manifestPath } | Sort-Object FullName | ForEach-Object {
    $rel = $_.FullName.Substring($evidenceDir.Length + 1) -replace '\\', '/'
    if ($gitOk -and $ignoredSet.ContainsKey("$evRel/$rel")) { $skipped++; return }
    $h = (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLower()
    $mlines += "$h  $rel"
    $newMap[$rel] = $h
}

# --- 现清单读入（**BOM／CRLF／无尾换行**三个形态一次吃掉，三者今天各害过一次）---
$oldMap = @{}
if (Test-Path -LiteralPath $manifestPath) {
    $raw = [System.IO.File]::ReadAllBytes($manifestPath)
    if ($raw.Length -ge 3 -and $raw[0] -eq 0xEF -and $raw[1] -eq 0xBB -and $raw[2] -eq 0xBF) {
        $txt = [System.Text.Encoding]::UTF8.GetString($raw, 3, $raw.Length - 3)
    } else {
        $txt = [System.Text.Encoding]::UTF8.GetString($raw)
    }
    foreach ($ln in ($txt -split "`n")) {
        $t = $ln.Trim()
        if (-not $t -or $t.StartsWith('#')) { continue }
        $m = [regex]::Match($t, '^([0-9a-fA-F]{64})\s+(.+)$')
        if ($m.Success) { $oldMap[$m.Groups[2].Value.Trim()] = $m.Groups[1].Value.ToLower() }
    }
}

# --- 条目级 delta：**必须由工具单独报出来**，别指望从 git diff 里看 ---
# `git diff` 是关于行的，不是关于字节的：它既会漏掉真的字节改动，也会虚报整片改动。
$changed = @(); $added = @(); $removed = @()
foreach ($k in ($newMap.Keys | Sort-Object)) {
    if (-not $oldMap.ContainsKey($k)) { $added += $k }
    elseif ($oldMap[$k] -ne $newMap[$k]) { $changed += $k }
}
foreach ($k in ($oldMap.Keys | Sort-Object)) { if (-not $newMap.ContainsKey($k)) { $removed += $k } }

"目标：$manifestPath"
"条目：现清单 $($oldMap.Count) 条 → 本次算出 $($mlines.Count) 条（已排除 gitignored $skipped 条；git 可用=$gitOk）"
foreach ($k in $changed)  { "  ~ $k  $($oldMap[$k].Substring(0,12))… -> $($newMap[$k].Substring(0,12))…" }
foreach ($k in $added)    { "  + $k  （新增，此前不在清单里）" }
foreach ($k in $removed)  { "  - $k  （移除，盘上已无或已被忽略）" }
if ($changed.Count -eq 0 -and $added.Count -eq 0 -and $removed.Count -eq 0) { "  （无条目级差异）" }

if (-not $Write) {
    "**未写盘**（默认只报不写）。确认每条变化都能说清成因后，加 -Write 重跑，并把成因逐条写进提交说明。"
    exit 0
}

$mhdr = @(
    # ⚠ 出处这一句**必须与写入者无关**：它有两条写入路径（链跑与链外手工），
    # 若按写入者取词，这一行会在两者之间来回翻 —— 而这份文件的全部意义是稳定。
    "# $evRel 的 SHA256 清单 —— 由 scripts/New-EvidenceManifest.ps1 重算（链跑 verify_all.ps1 -Scope all 亦调用它），勿手编。",
    '# 【这是本机 checkout 的形态快照，不是仓库内容的规范哈希】：文件落到磁盘的字节',
    '# 受本机 core.autocrlf 与 .gitattributes 影响，换一台机器 checkout 出来的行尾可能不同。',
    '# ⇒ 哈希对不上时**先核行尾形态，再怀疑内容被改**。（全仓行尾策略单列待裁，试点期禁动。）',
    '# 已排除两类：①清单自身；②本 checkout 中被 .gitignore 忽略的未跟踪文件',
    '#   （绝大多数是 verify_all_*.log 运行日志，只在本机存在、别处无从复核）。',
    '# ⚠ 因此本清单**不含当次运行日志**；当次日志路径见 badges.txt 与本次 verify_all 输出。',
    '# ⚠⚠ 【本表头描述的是「清单生成的那一刻」，不是「入库后的状态」】：归档提交会在',
    '#   清单生成**之后**把当次运行日志 `git add -f` 入库 ⇒ 入库后必然短暂存在',
    '#   **已跟踪、却不在本清单里**的日志，它不属于上面任何一类。下次重算即收入。',
    '#   ⇒ 拿本清单核对账时把这一类算进去，别当成不一致去查（有人为此查过二十分钟）。',
    '#   守它的是 `test_every_tracked_evidence_file_has_a_hash_except_the_run_logs`：',
    '#   已跟踪却未列的**必须全部是 verify_all_*.log**，其余一律红。',
    "# 行格式：<sha256 小写><两个空格><相对 $evRel 的路径，斜杠分隔>；``#`` 开头为注释。"
)
($mhdr + $mlines) -join "`r`n" | Out-File -Encoding utf8 $manifestPath
$mnote = if ($gitOk) { "，已排除 gitignored $skipped 条" } else { '；⚠ git 不可用，未能排除 gitignored' }
"manifest: $manifestPath ($($mlines.Count) files$mnote)"
