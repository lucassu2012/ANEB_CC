# -*- coding: utf-8 -*-
"""清单里每个条目的哈希，必须与盘上那个文件实算相符（承 D-822）。

🔴 **为什么要这道门**：既有的 presence 门（`test_docs_commands.py` 的
`test_every_tracked_evidence_file_has_a_hash_except_the_run_logs`）只查**条目在不在**，
**从不校验哈希与内容是否相符** ⇒ 一条哈希可以陈两个月而全绿。
**一份没有守卫校验的完整性记录，不是完整性记录。**

**方向与它相反，这是设计不是重复**：
 - presence 门 ＝ **按文件找条目**（有文件没条目即红），故必须给运行日志开例外；
 - 本门 ＝ **按条目找文件**（条目对不上盘上内容即红），**新日志根本不在条目里、天然不参与**
   ⇒ **不需要任何例外**。少一个例外就少一处日后被引错的地方。

**范围＝全仓四份，不是 phase0 一份**（这条是本门最容易被削掉的部分）：
链跑只重算 `phase0`（`verify_all.ps1` 传给 `New-EvidenceManifest.ps1` 的就是这一个目录），presence 门也只查 `phase0`。
⇒ `phase1/2/3` 三份**没有重生成器、也没有读者**。**把门也只挂 phase0，等于把那个盲区原样复制一遍。**

⚠ **判据取盘上，不取 HEAD**：取 HEAD 会造出「修它必须先跑十几分钟链跑，而在提交前门一直红」
的死循环（2026-09-07 实地踩过，为绕它拆了两笔提交）。取盘上则与修法同构——跑完链盘上即自洽。
**代价写明**：它守的是工作区、不是已发布的东西；「只提交 badges 不提交清单」这类半批提交
**本门拦不住**，那要另配判据。**不要指望一道门守两件事。**

⚠ **红了先查成因再重算 —— 但不要因为「怕抹掉痕迹」而不敢重算**。
🔴 **本文件初版在这里写错过一次，就地订正不删**：原写「对冻结那类清单，重算会把『这个文件
曾经不一样』这唯一的痕迹抹掉」。**那句对受跟踪文件是错的** —— git 一直留着旧字节。
判决性检验（三条全部命中，我实算过）：
    git show 9356de7^:evidence/phase3/demo_results.jsonl   → 转 CRLF 后 == 清单记的 1de8f775…
    git show 9356de7^:evidence/phase3/gen_demo_jsonl.py    → as-is/LF   == be88c27a…
    git show 897f474^:evidence/phase1/STATUS.json          → as-is/LF   == ba103886…
⇒ **重算不丢史实**，故不应做永久豁免。
**那先查成因还有什么用**：用来分辨这次改动**是不是合法的**——
**不问成因就重算，等于把一次没人解释得清的改动洗成「正确」**，而清单从此为它背书。

⚠ 🔴 **这道门的力量有边界，写出来免得被高估**：清单重算写在 `verify_all.ps1` 的
`if ($isRed -or $isFinalGreen)` 块内（788 行）且块内**无条件执行**（828 行）
⇒ **红跑照样重算** ⇒ 在 `phase0` 这种有重生成器的地方，**门红一次、下一跑即绿，无人动手也自愈**；
而 D-819 的「收尾复跑」发生在重算**之后** ⇒ **对这道门恒绿，那是同义反复不是确认**。
**它真正持久起作用的地方是 `phase1/2/3`** —— 没有重生成器，所以那三条能停两个月没人发现。

⚠ **写读取器时的两个坑（同侪实测各栽一次，都在这一层）**：
 - **CRLF**：`\\r` 留在文件名尾 ⇒ 三百多条**全报「文件缺失」**。
   **「全部缺失」与「零命中」是同一族假信号**：它看起来像发现，其实是量法坏了。
 - **BOM**：`phase1` 首行没有 `#` 表头，BOM 直接粘在第一条哈希前 ⇒ 被误读成「内容变了」。
四份清单**三种格式**（phase0 有 BOM＋表头；phase1 有 BOM 无表头；phase2/3 无 BOM 无表头）
⇒ **每份单独断言「解析出的条目数 > 0」**，不能只有一个全局断言——
那种断言会被第一份满足，然后**把后三份整个放过**。
"""
import glob
import hashlib
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SCRIPTS)
MANIFEST_GLOB = os.path.join(REPO_ROOT, "evidence", "*", "sha256-manifest.txt")

# 立此清单时**实测**已陈的条目：{仓根相对路径: 成因（含 commit 锚）}。
#
# **这是欠账，不是许可**——下方反向断言会在它被修好后强制把它从这里删掉，
# 否则这张表会变成一张只增不减的免罪符（同 `_DECISION_OVERLONG_PENDING_TRIM` 的先例）。
#
# **目前为空**：立此表时实测的三条已按裁定（成因查清、无一指向篡改）**全部重算**——
#   `evidence/phase1/STATUS.json`        ← 897f474（phase1 收口，两项 NOT_EXECUTED→PASS）
#   `evidence/phase3/demo_results.jsonl` ← 9356de7（A-4／D-722，demo 加 synthetic 块）
#   `evidence/phase3/gen_demo_jsonl.py`  ← 同上
# **清偿了就得删**（下方 `settled` 反向断言强制这一点），否则它会变成只增不减的免罪符。
_STALE_PENDING_RULING = {
    # 新增条目必须写清成因与 commit 锚，且**尽快清偿**——它是欠账，不是许可。
}

_HOWTO = (
    "\n修法**先查成因，再重算**："
    "\n  · 先查（`git log -1 -- <文件>` 与清单自身提交时刻孰先孰后；必要时 "
    "`git show <改动前的提交>^:<路径>` 逐形态对拍，确认清单记的就是旧字节）。"
    "**不问成因就重算，等于把一次没人解释得清的改动洗成「正确」。**"
    "\n  · `phase0` 有重生成器 ⇒ 跑 `verify_all.ps1 -Scope all` 即可；"
    "\n  · `phase1/2/3` **没有重生成器** ⇒ 需要一次显式的重算动作，只能一次性显式重算（2026-09-07 已这样做过一次）。"
    "⚠ **逐字节改**：phase3 那份清单的行尾是**双 CR**（CR CR LF），按「单个 CR」还原会每行少一字节，而 `git diff` 只显示哈希那一处、看不出来。"
    "\n  · ⚠ **不要因为「怕抹掉痕迹」而不敢重算**：受跟踪文件的旧字节 git 一直留着，"
    "重算不丢史实（本文件 docstring 有三条判决性检验）。"
)


def parse_manifest(path):
    """→ [(哈希, 文件名)]。**BOM 与 CRLF 在这里一次吃掉**，见模块 docstring。"""
    raw = io.open(path, "rb").read()
    text = raw.decode("utf-8-sig", errors="replace")   # BOM：phase1 无表头，会粘进第一条哈希
    out = []
    for line in text.splitlines():                     # splitlines 顺带吃掉 \r
        line = line.strip()                            # 再兜一层：防文件名尾部残留 \r
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            continue
        out.append((parts[0].lower(), parts[1].strip()))
    return out


def check_manifest(path):
    """→ [问题串]。按**条目**驱动：条目指不到文件、或指到的文件内容对不上，都算问题。"""
    base = os.path.dirname(path)
    problems = []
    for want, name in parse_manifest(path):
        target = os.path.join(base, name)
        if not os.path.isfile(target):
            problems.append("%s：条目指向的文件不在盘上" % name)
            continue
        got = hashlib.sha256(io.open(target, "rb").read()).hexdigest()
        if got != want:
            problems.append("%s：清单记 %s…，实算 %s…" % (name, want[:12], got[:12]))
    return problems


def _rel(path):
    return os.path.relpath(path, REPO_ROOT).replace("\\", "/")


def test_every_manifest_entry_matches_the_file_on_disk():
    manifests = sorted(glob.glob(MANIFEST_GLOB))
    # 范围自证：少于四份就意味着有清单被挪走/改名，**而那正是本门会安静缩水的方式**。
    assert len(manifests) >= 4, (
        "只找到 %d 份 sha256-manifest.txt（期望 ≥4：phase0/1/2/3）—— "
        "先怀疑是不是有清单被挪走或改名，别当成「本仓只有这些」。%s"
        % (len(manifests), [_rel(m) for m in manifests]))

    unexpected = []
    for mf in manifests:
        entries = parse_manifest(mf)
        # ⚠ **每份单独断言非空**。只有一个全局断言时，它会被第一份满足然后放过后三份——
        # 而「解析不出条目」与「条目全都相符」在结果上长得一模一样。
        assert entries, (
            "%s 解析出 0 个条目 —— **先怀疑量法坏了**（BOM？CRLF？分隔符？），"
            "别当成「这份清单是空的」" % _rel(mf))
        for p in check_manifest(mf):
            key = os.path.dirname(_rel(mf)) + "/" + p.split("：")[0]
            if key not in _STALE_PENDING_RULING:
                unexpected.append("%s → %s" % (_rel(mf), p))

    assert not unexpected, (
        "这些清单条目与盘上文件对不上，且不在已登记的待裁清单里：\n  "
        + "\n  ".join(unexpected) + _HOWTO)


def test_the_pending_list_is_a_debt_not_an_amnesty():
    """已经修好的条目必须从 `_STALE_PENDING_RULING` 删掉。

    方向与上面那条相反。**缺了它，那张表只会越加越长，而没人知道哪些还欠着。**
    """
    still_stale = set()
    for mf in sorted(glob.glob(MANIFEST_GLOB)):
        d = os.path.dirname(_rel(mf))
        for p in check_manifest(mf):
            still_stale.add(d + "/" + p.split("：")[0])
    settled = sorted(set(_STALE_PENDING_RULING) - still_stale)
    assert not settled, (
        "这些条目已与盘上相符，请从 `_STALE_PENDING_RULING` 删除：%s" % settled)


# ------------------------------------------------------------------ 合成夹具（阳性对照）
def _write(tmp, name, data, manifest_lines, bom=False, header=False):
    d = os.path.join(tmp, name)
    os.makedirs(d, exist_ok=True)
    for fn, content in data.items():
        io.open(os.path.join(d, fn), "wb").write(content)
    body = ""
    if header:
        body += "# 生成于归档跑，勿手编\n"
    body += "".join(manifest_lines)
    raw = body.encode("utf-8")
    if bom:
        raw = b"\xef\xbb\xbf" + raw
    io.open(os.path.join(d, "sha256-manifest.txt"), "wb").write(raw)
    return os.path.join(d, "sha256-manifest.txt")


def test_a_single_flipped_byte_is_caught():
    """阳性对照：改一个字节必须红。**没有它，一道恒绿的门与一道好门长得一样。**"""
    tmp = tempfile.mkdtemp()
    good = b"hello\n"
    h = hashlib.sha256(good).hexdigest()
    mf = _write(tmp, "ok", {"a.txt": good}, ["%s  a.txt\n" % h])
    assert check_manifest(mf) == []
    io.open(os.path.join(os.path.dirname(mf), "a.txt"), "wb").write(b"hellp\n")
    bad = check_manifest(mf)
    assert len(bad) == 1 and "a.txt" in bad[0], bad


def test_a_missing_target_is_caught_too():
    """条目指向的文件被删掉，也必须红——**本门是按条目驱动的，那是它的另一半**。"""
    tmp = tempfile.mkdtemp()
    good = b"hello\n"
    mf = _write(tmp, "gone", {"a.txt": good},
                ["%s  a.txt\n" % hashlib.sha256(good).hexdigest()])
    os.remove(os.path.join(os.path.dirname(mf), "a.txt"))
    bad = check_manifest(mf)
    assert len(bad) == 1 and "不在盘上" in bad[0], bad


def test_bom_and_crlf_do_not_fake_a_finding():
    """两个坑各钉一次：**它们制造的假信号看起来像发现**。

    - BOM 粘在第一条哈希前 ⇒ 会被读成「内容变了」；
    - 文件名尾残留 CR ⇒ 会被读成「文件缺失」，且是**全部**缺失。
    """
    tmp = tempfile.mkdtemp()
    good = b"x\n"
    h = hashlib.sha256(good).hexdigest()
    # 无表头 + BOM（phase1 那种形态）
    mf1 = _write(tmp, "bom", {"a.txt": good}, ["%s  a.txt\n" % h], bom=True)
    assert check_manifest(mf1) == [], "BOM 被当成了哈希的一部分"
    # CRLF 行尾（三份清单里就有这种）
    mf2 = _write(tmp, "crlf", {"a.txt": good}, ["%s  a.txt\r\n" % h])
    assert check_manifest(mf2) == [], "文件名尾部的 CR 没被吃掉 ⇒ 会全报缺失"


def test_a_manifest_without_a_trailing_newline_keeps_its_last_entry():
    """🔴 **最后一条不许被静默吃掉**——`evidence/phase3` 那份**没有行尾换行符**（末字节是 `g`，即 `gen_demo_jsonl.py` 的末字符）。

    实证（2026-09-07，同侪的校验器）：用 `while read` 扫它，**`read` 在无尾换行的最后一行上
    返回非零 ⇒ 循环体不执行 ⇒ 最后一条被静默跳过**，于是它数出 35 条而实际 36 条。
    ⚠ **那次两侧数字差 1，第一反应是「计数口径不同」——那是个说得通的解释，而它是错的。**
    **一个数对不上时，先假设某一侧的量法漏了东西，别先找一个能解释它的口径差异。**

    本文件的读取器用 `splitlines()`，天生不受影响；**但没有用例钉住就只是碰巧对**。
    """
    tmp = tempfile.mkdtemp()
    a, b = b"one\n", b"two\n"
    ha, hb = hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest()
    d = os.path.join(tmp, "notrail")
    os.makedirs(d, exist_ok=True)
    io.open(os.path.join(d, "a.txt"), "wb").write(a)
    io.open(os.path.join(d, "b.txt"), "wb").write(b)
    mf = os.path.join(d, "sha256-manifest.txt")
    # 末尾**不带**换行，且用 phase3 那种双 CR 行尾——两个形态一起钉
    io.open(mf, "wb").write(
        ("%s  a.txt\r\r\n%s  b.txt" % (ha, hb)).encode("utf-8"))
    entries = parse_manifest(mf)
    assert len(entries) == 2, ("最后一条被吃掉了：%r" % (entries,))
    assert entries[-1][1] == "b.txt", entries
    assert check_manifest(mf) == []


def test_an_unparseable_manifest_is_not_silently_empty():
    """解析不出条目时，主用例会断言失败——这里钉住解析器**确实返回空**，

    以免日后有人给 `parse_manifest` 加个「猜一猜」的兜底，把「读不懂」变成「读到 0 条」。
    """
    tmp = tempfile.mkdtemp()
    mf = _write(tmp, "junk", {"a.txt": b"x\n"}, ["这一行不是清单条目\n"])
    assert parse_manifest(mf) == []
