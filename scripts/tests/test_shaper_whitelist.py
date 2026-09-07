# -*- coding: utf-8 -*-
"""`scripts/shaper/shaper.ps1` 的白名单/菜单守卫（承接线单 §4.3 条件 3 / D-838 / D-840）。

🔴 **为什么这道门是安全关键**：`shaper.ps1` 经 `ANEB-Shaper-Start` 以 /RL HIGHEST **提权**运行，
而它读的 `current.args` 在**非管理员可写**目录（D-840 第三条提权路径）。**拦住任意旗标注入的
唯一边界就是这个菜单**——current.args 只能选档名，档名→参数写死在脚本里。

两类断言，缺一不可：
 - **静态（不依赖 powershell）**：`$MENU` 的每个值**只含允许旗标**——这是「白名单不是黑名单」
   做成可测的形式：我枚举**允许**什么，任何不在允许集里的旗标（含所有破坏性旗标）即红。
   ⚠ 不写「禁止 rst-prob/…」那种黑名单——一份漏了的黑名单不会报错（D-838 订正的正是这个）。
 - **行为（反例；需 powershell）**：把注入串喂进 current.args，`-ResolveOnly` 必须**抛错**。
   没有反例，一个「什么都放行」的菜单照样全绿（§4.3 条件 3 原话）。
"""
import os
import re
import shutil
import subprocess
import tempfile

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SCRIPTS)
SHAPER = os.path.join(SCRIPTS, "shaper", "shaper.ps1")

# **允许集**（正面枚举）。菜单里出现任何不在此集的 `--flag` 即判红。
# 只含三族整形 + 作用域所需，绝不含破坏性/改作用域旗标。
ALLOWED_FLAGS = {
    "--filter", "--dst-ip", "--dst-port",
    "--latency", "--jitter", "--loss", "--loss-burst",
    "--up", "--down", "--buffer",
}
# 这些一旦出现在任何菜单值里就是重大回归（仅用于失败信息更直白；判据仍是「⊆ 允许集」）。
KNOWN_DESTRUCTIVE = {
    "--rst-prob", "--block-ip", "--block-port", "--lan-mode", "--internet-only",
    "--syn-drop", "--corrupt", "--dup", "--flap-period", "--flap-down",
    "--max-size", "--spike-prob", "--spike-ms", "--nat-timeout", "--target",
}


def _shaper_text():
    with open(SHAPER, encoding="utf-8") as fh:
        return fh.read()


def _menu_entries():
    """→ {档名: [该行里出现的所有 --flag]}。含 $TARGET 展开（TARGET 里的旗标也算）。"""
    text = _shaper_text()
    m = re.search(r"\$MENU\s*=\s*@\{(.*?)\n\}", text, re.S)
    assert m, "找不到 $MENU = @{ ... } 块 —— 先怀疑脚本结构变了，别当成没有菜单"
    block = m.group(1)
    tm = re.search(r"\$TARGET\s*=\s*@\((.*?)\)", text, re.S)
    assert tm, "找不到 $TARGET = @( ... ) —— 作用域定义变了"
    target_flags = re.findall(r"--[a-z][a-z-]*", tm.group(1))
    entries = {}
    for line in block.splitlines():
        m2 = re.match(r"\s*'([^']+)'\s*=", line)
        if not m2:
            continue
        flags = re.findall(r"--[a-z][a-z-]*", line)
        if "$TARGET" in line:
            flags = target_flags + flags
        entries[m2.group(1)] = flags
    return entries


def test_menu_is_not_empty_and_covers_three_families():
    entries = _menu_entries()
    assert entries, "菜单解析为空 —— 先怀疑量法坏了，别当成没有档位"
    joined = " ".join(f for fs in entries.values() for f in fs)
    assert "--latency" in joined, "菜单缺延迟档"
    assert "--loss" in joined, "菜单缺丢包档"
    assert ("--up" in joined or "--down" in joined), "菜单缺限速档"


def test_every_menu_value_uses_only_allowed_flags():
    """🔴 核心：白名单＝每个菜单值的旗标 ⊆ 允许集。任何越界旗标（含破坏性）即红。"""
    bad = []
    for name, flags in _menu_entries().items():
        for f in flags:
            if f not in ALLOWED_FLAGS:
                tag = "（破坏性！）" if f in KNOWN_DESTRUCTIVE else ""
                bad.append("%s: %s%s" % (name, f, tag))
    assert not bad, (
        "这些菜单值含允许集之外的旗标：\n  " + "\n  ".join(bad)
        + "\n允许集＝" + ", ".join(sorted(ALLOWED_FLAGS))
        + "\n（这是白名单：要加旗标先加进 ALLOWED_FLAGS 并想清为什么安全，别在菜单里偷偷放）")


def test_every_menu_value_pins_scope():
    """§三-C：每档都必须显式限定作用域（--dst-ip 或 --dst-port），绝不吃默认全机。"""
    for name, flags in _menu_entries().items():
        assert ("--dst-ip" in flags or "--dst-port" in flags), (
            "档 %s 未显式限定作用域 ⇒ 会影响全机流量（§三-C）" % name)


# ---------------------------------------------------------------- 行为反例（需 powershell）
def _ps():
    return shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")


def _resolve(name_line):
    """把 name_line 写进临时 current.args，跑 shaper.ps1 -ResolveOnly，→ (returncode, stdout)。"""
    ps = _ps()
    d = tempfile.mkdtemp()
    af = os.path.join(d, "current.args")
    with open(af, "w", encoding="utf-8") as fh:
        fh.write(name_line)
    r = subprocess.run(
        [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SHAPER,
         "-ArgsFile", af, "-ResolveOnly"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=60)
    return r.returncode, (r.stdout or "")


def test_good_name_resolves_bad_name_and_injection_are_rejected():
    """反例：只有正例的白名单，放宽成「什么都放行」照样全绿 ⇒ 必须有拒绝的反例。"""
    if not _ps():
        import pytest
        pytest.skip("本机无 powershell ⇒ 跳过行为反例（静态白名单断言已跑）；Windows 上应执行")

    rc, out = _resolve("delay_lat200")
    assert rc == 0, "合法档名 delay_lat200 竟被拒: rc=%s out=%r" % (rc, out)
    assert "--latency 200" in out, out
    for f in KNOWN_DESTRUCTIVE:
        assert f not in out, "解析结果混入破坏性旗标 %s: %r" % (f, out)

    rc, _ = _resolve("--rst-prob 100")
    assert rc != 0, "注入 --rst-prob 竟被接受 ⇒ 菜单不是白名单"
    rc, _ = _resolve("delay_lat200 --block-ip 8.8.8.8")
    assert rc != 0, "档名后挂 --block-ip 竟被接受 ⇒ 存在旗标注入"
    rc, _ = _resolve("nonexistent_tier")
    assert rc != 0, "未知档名竟被接受"
    rc, _ = _resolve("")
    assert rc != 0, "空 current.args 竟被接受"
