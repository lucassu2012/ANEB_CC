# -*- coding: utf-8 -*-
"""元守卫：每个受跟踪的测试文件都必须被 `scripts/verify_all.ps1` 的某条路径覆盖。

**为什么要有它**（D-674 ④b，承 D-671 ④⑤）：本仓已出现三例「**门真绿、但不在清单上**」
（e1 跑器／e234 跑器／`tools/e03/tests`）。三例的共性**不是「有人忘了」，是接线机制要求有人记得**：
`run_all.py`（`os.listdir`）与 `go test ./...` 是**枚举式**、新文件自动收编；而 `obsSuite`
是**硬编码目录列表**，新目录必须有人手动加一行。本守卫把「还有谁没进门」从**记性**改成**差集**。

⚠ **本守卫自己最容易犯的两个错，都是属主在 `f1e2734` 那次人工扫描中实测栽过的**，
故**先断言量法、再断言差集**（本仓「零命中先验量法」的应用，而这次两个方向都栽过）：

- **① 太宽 ⇒ 假覆盖**：拿「路径在 `verify_all.ps1` 里**出现过**」当判据，会把
  **只出现在注释里**的目录名记成已覆盖。**「被提及」≠「被执行」** ⇒ 本文件只认
  `Join-Path $repo '...'` 这类**真实调用目标**与 `obsSuite` 的 `Dir =`，不做全文子串匹配。
- **② 太窄 ⇒ 假缺口**：只抽 `Add-Result '单引号字面量'` 会**整段漏掉**插值形
  `Add-Result "server-$name"`，属主据此造出过一个「**Go 测试根本没在跑**」的假警报
  ⇒ 本文件断言两种形态都被抽到。

⚠ **豁免是自失效的**：`tools/e03/tests` 现按 D-671 ④／D-674 ④a 待接线（v3 批后落）。
**一旦它真被覆盖，本守卫会红并要求删掉这条豁免**——豁免不会烂在这里。
"""
import os
import re

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(TESTS_DIR)
REPO_ROOT = os.path.dirname(SCRIPTS)
VERIFY_ALL = os.path.join(SCRIPTS, "verify_all.ps1")

# 待接线的已知缺口：键＝仓内相对目录（正斜杠），值＝裁定锚。
# ⚠ 自失效：该目录一旦被 verify_all 覆盖，test_exemptions_expire_when_no_longer_needed 会红。
# ⚠ 现为空，且**这个空是被本文件自己逼出来的**：`tools/e03/tests` 的豁免写下约十分钟后，
# v3 的接线并线进来，`test_exemptions_expire_when_no_longer_needed` **当场变红**并要求删除它。
# ⇒ 自失效豁免不是纸面纪律，它在本仓已实测生效一次（2026-09-03）。
PENDING_WIRING = {}

# 枚举形接线的构造判据：**逐字**取自 verify_all.ps1 的枚举块。
# 那边改写法这边会红 —— 红了要去核「枚举还在不在」，不是把这两行放宽。
ENUM_HEAD = "Get-ChildItem (Join-Path $repo 'tools')"
ENUM_PROBE = "tests/run_tests.py"

_SKIP_DIRS = {".git", "__pycache__", "node_modules", "build", ".gradle", "evidence"}


def _read_verify_all():
    with open(VERIFY_ALL, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _norm(p):
    return p.replace("\\", "/").strip("/")


def _explicit_targets(ps):
    """verify_all 真正调用的具名文件（`Join-Path $repo '...'`），不是「文中出现过的字符串」。"""
    return set(_norm(m) for m in re.findall(r"Join-Path \$repo '([^']+)'", ps))


def _obs_dirs(ps):
    """obsSuite 的 `Dir = '...'` 目录（硬编码形态）。"""
    return set(_norm(m) for m in re.findall(r"Dir\s*=\s*'([^']+)'", ps))


def _enumerated_tool_dirs(ps):
    """接线若已升级为枚举形（D-674 ④a），把 verify_all **会枚举到**的 tools 目录视为已覆盖。

    ⚠ **判据认「构造」不认「提及」**（2026-09-03 实测订正）：初版判据是宽匹配
    `tools/` + 通配 + `/tests`，而该字面量在 `verify_all.ps1` 里**只出现在枚举零命中时的
    FAIL 提示文字里**，真正的枚举代码里一个字都没有 —— 即本文件 docstring 自列的失败形态
    ①「**被提及 ≠ 被执行**」。且方向是**变松**：删掉枚举块、留着那句提示语，本守卫照样绿。
    初版注释写的「漏判只会让本守卫更严，不会更松」**只覆盖假阴性方向，不覆盖这个方向**。

    ⚠ **第二处对齐**：目录判据改成与 verify_all 同款（须有 `tests/run_tests.py`），
    不再用「磁盘上有 `tests/` 目录」这个**更宽**的面。两面当下恰好相等
    （`tools/e1_stimulus` 无 `tests/`），**而恰好相等不是相等**。
    """
    if not (ENUM_HEAD in ps and ENUM_PROBE in ps and "$obsSuites" in ps):
        return set()
    out = set()
    tools = os.path.join(REPO_ROOT, "tools")
    if os.path.isdir(tools):
        for name in sorted(os.listdir(tools)):
            if os.path.isfile(os.path.join(tools, name, "tests", "run_tests.py")):
                out.add("tools/%s/tests" % name)
    return out

def _autodiscovery_roots(ps):
    """自动发现型覆盖根：只有当 runner 确实按 listdir 收集时才算。"""
    roots = set()
    if "scripts/tests/run_all.py" in _explicit_targets(ps):
        with open(os.path.join(TESTS_DIR, "run_all.py"), encoding="utf-8") as fh:
            src = fh.read()
        # 手写清单会漂；只有真 listdir 才算「新文件自动进门」
        if "os.listdir" in src:
            roots.add("scripts/tests")
    return roots


def _tracked_py_tests():
    out = []
    for base, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for f in files:
            if f.startswith("test_") and f.endswith(".py"):
                out.append(_norm(os.path.relpath(os.path.join(base, f), REPO_ROOT)))
    return sorted(out)


def _covered(path, explicit, obs, enumerated, roots):
    d = os.path.dirname(path)
    return path in explicit or d in obs or d in enumerated or d in roots


# --------------------------------------------------------------------------
# 先验量法：这三条不过，下面的差集数没有意义（零收集／坏正则都会给出一个漂亮的空差集）
# --------------------------------------------------------------------------

def test_the_extractors_actually_extract_before_any_difference_is_trusted():
    ps = _read_verify_all()
    explicit = _explicit_targets(ps)
    obs = _obs_dirs(ps)
    enumerated = _enumerated_tool_dirs(ps)
    files = _tracked_py_tests()

    assert len(explicit) >= 5, "具名调用目标只抽到 %d 个 —— 正则坏了，差集会假空" % len(explicit)
    assert "spec/portraits/check_redline.py" in explicit, \
        "已知一定被调用的目标没抽到 ⇒ 量法在这份文件上不工作（零命中先验量法）"
    assert obs or enumerated, (
        "obsSuite 两种形态（硬编码 `Dir = '...'` ／ tools 枚举）都零命中 —— "
        "差集会把 e1/e234/e03 全部误报成缺口")
    if not obs:
        # 枚举形是当下的活形态：量法前验落到「它认不认得出已知一定在跑的门」
        assert {"tools/e1/tests", "tools/e234/tests"} <= enumerated, (
            "枚举形抽取器认不出 e1/e234 ⇒ 量法在这份文件上不工作（零命中先验量法）")
    assert len(files) >= 30, "全仓只发现 %d 个 test_*.py —— 枚举坏了或目录空了" % len(files)


def test_gate_entry_enumeration_sees_interpolated_names_not_only_quoted_literals():
    """属主实测过的第二个坑：只抽单引号字面量会漏掉整段 Go 门，造出假缺口。"""
    ps = _read_verify_all()
    quoted = set(re.findall(r"Add-Result '([^']+)'", ps))
    interpolated = re.findall(r'Add-Result "([^"]+)"', ps)
    assert quoted, "单引号形态的门条目一个都没抽到"
    assert interpolated, (
        "插值形态的门条目（Add-Result \"x-$name\"）一个都没抽到 —— "
        "只按字面量枚举会把 server-vet/build/test 整段漏掉，据此报出的『某某没在跑』是假警报"
    )


def test_go_suite_is_covered_by_the_recursive_go_test_step():
    """Go 侧由 `go test ./...` 递归覆盖；这条防它被悄悄改成只测某个包。"""
    ps = _read_verify_all()
    assert re.search(r"'test',\s*'-count=1',\s*'\./\.\.\.'", ps), \
        "verify_all 里找不到递归的 go test ./... —— server/*_test.go 可能已脱离门禁"


# --------------------------------------------------------------------------
# 差集本体
# --------------------------------------------------------------------------

def test_every_tracked_python_test_file_is_covered_by_some_gate():
    ps = _read_verify_all()
    explicit, obs = _explicit_targets(ps), _obs_dirs(ps)
    enumerated, roots = _enumerated_tool_dirs(ps), _autodiscovery_roots(ps)

    uncovered = [p for p in _tracked_py_tests()
                 if not _covered(p, explicit, obs, enumerated, roots)]
    unexpected = [p for p in uncovered if os.path.dirname(p) not in PENDING_WIRING]

    assert not unexpected, (
        "这些测试文件不在 verify_all 的任何一条执行路径上 —— 它们是真绿的门，"
        "只是没人会跑它们：\n  " + "\n  ".join(unexpected) +
        "\n⇒ 接线是一次裁定，不要在这里加豁免；先报，再裁。"
    )


def test_exemptions_expire_when_no_longer_needed():
    """豁免自失效：待接线目录一旦真被覆盖，本条即红，要求删掉那条豁免。

    ⚠ 本仓的教训是「**豁免加进去不会有人再取出来**」；让它在不再需要时**主动报红**，
    是唯一不依赖记性的取出方式。
    """
    ps = _read_verify_all()
    obs = _obs_dirs(ps)
    enumerated, roots = _enumerated_tool_dirs(ps), _autodiscovery_roots(ps)

    stale = [d for d in PENDING_WIRING if d in obs or d in enumerated or d in roots]
    assert not stale, (
        "这些目录已经被 verify_all 覆盖了，PENDING_WIRING 里的豁免该删掉：\n  "
        + "\n  ".join("%s（原因栏：%s）" % (d, PENDING_WIRING[d]) for d in stale)
    )


def test_every_gate_step_name_is_registered_in_a_scope_list():
    """**第二层**：门跑了，但步名没登进 `Test-InScope` 名单 ⇒ 层外**从汇总里彻底消失**。

    ⚠ **这一层原本不在本文件里，是被一句夸奖逼出来的**：D-677 ① 判「元守卫＝结构性关闭的
    承担者」，属主去核那句断言，发现本文件当时**只关闭了第一层**（测试文件没落在任何门上），
    **查不出第二层**（门进了、步名没登记 ⇒ 出层时既不跑、也不记 `SKIPPED_SCOPE`，
    悄悄消失）。⇒ **补此条后那个判定才成立**；不补而照收，就是拿一句好话当验过。

    判据方向刻意只取**危险的那一侧**（declared ⊆ scoped）：漏登会让门静默消失；
    反向（名单里有已不存在的步）只会多打印一行 SKIPPED_SCOPE，不伤判读。
    """
    ps = _read_verify_all()
    scoped = set()
    # ⚠ 允许 `Test-InScope 'x' (@(...) + $var)` 形：scripts 那行加了 `$obsNames` 之后
    # 外面多了一层括号，原正则要求 `@(` 紧跟 ⇒ **整条 scripts 名单一个名都抽不到**。
    for m in re.finditer(r"Test-InScope\s+'[a-z]+'\s+\(?@\(([^)]*)\)([^\n]*)", ps):
        scoped |= set(re.findall(r"'([^']+)'", m.group(1)))
        if "$obsNames" in m.group(2):
            # 名单用变量登记的那部分：按 verify_all 的推名规则展开
            scoped |= _obs_step_names(ps)
    declared = set(re.findall(r"Add-Result '([^']+)'", ps)) | _obs_step_names(ps)

    assert len(scoped) >= 10, "Test-InScope 名单只抽到 %d 个 —— 正则坏了，下面的差集会假空" % len(scoped)
    assert "obs-tools-e1-unit" in scoped, "已知一定在名单里的步名没抽到 ⇒ 量法不工作"
    assert declared, "门条目一个都没抽到"

    unregistered = sorted(declared - scoped)
    assert not unregistered, (
        "这些门会跑，但步名没登进任何 Test-InScope 名单 —— **出层时它们不跑、也不记 "
        "SKIPPED_SCOPE，从汇总里彻底消失**，而汇总看起来一切正常：\n  "
        + "\n  ".join(unregistered)
    )


def _obs_step_names(ps):
    """obsSuite 步名：硬编码 `Name = '...'` ∪ **枚举形推出的** `obs-tools-<x>-unit`。

    ⚠ 枚举化（D-674 ④a）后仓里**一个 `Name = '...'` 字面量都不剩**，只认字面量会让本文件
    两条差集**同时假空**——而假空长得跟「全都登记好了」一模一样。
    步名规则逐字对齐 verify_all 的 `('obs-tools-' + $_.Name + '-unit')`。
    """
    names = set(re.findall(r"Name\s*=\s*'([^']+)'", ps))
    for d in _enumerated_tool_dirs(ps):
        names.add("obs-tools-%s-unit" % d.split("/")[1])
    return names


def test_pending_wiring_entries_point_at_real_directories():
    """豁免不许挂在一个不存在的目录上——那样它永远不会过期。"""
    missing = [d for d in PENDING_WIRING
               if not os.path.isdir(os.path.join(REPO_ROOT, *d.split("/")))]
    assert not missing, "PENDING_WIRING 指向不存在的目录：%s" % missing
