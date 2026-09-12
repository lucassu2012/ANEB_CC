# -*- coding: utf-8 -*-
"""判据必须不晚于结果入库（大脑批，替代它自己那句「下次记得」）。

🔴 **这道门存在的理由**：`evidence/b2_beancap_20260912/` 的 `CRITERIA_PREREG.md` 与 `README.md`
**同一笔提交入库** ⇒ **git 时刻证不了「判据早于结果」**。那一批里内容本身救了它（预登记带把实测
排除在外 12 倍，事后拟合的判据不会长这样），但**「内容看起来不像事后拟合」不是可机械判定的判据**
——下一批可能就不长那样。而「下次记得先单独提一笔」是靠记性的形态：**说不出名字的守卫就是没有守卫。**

⚠ **判据取「不得更晚」而非「必须更早」**，这个选择是刻意的：
 - 「必须更早」会让**现存那一批立刻需要豁免项**，而**一张第一天就要加豁免的名单，它的豁免会过期**；
 - 「不得更晚」同样逮住真正要防的形状 ——**先有结果、看过结果之后再补判据、再单独提一笔**。
 同一提交算过：它证不了顺序，但也没有作假痕迹，属「未加强」不属「违规」。

⚠ **本门守的是「若存在判据文件，其入库顺序须成立」，不是「每份证据都必须有判据文件」**。
后者是内容判断（有些证据无判据可言），不该由机械门强制。

⚠ **边界（明写，免得被当成它答了别的问题）**：
 - 不跟改名（不使用 `--follow`）；文件改名后本门看到的是「新路径的首次加入」。
 - 只看**首次加入**那一笔，不看后续修改——「判据后来被改过」本门不管，那是内容审查的事。
 - 顺序判据是**祖先关系**，不是提交时刻：`git log` 的日期可被改写，祖先关系不能。
"""
import os
import subprocess

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SCRIPTS)
EVIDENCE = os.path.join(REPO_ROOT, "evidence")
PREREG_NAME = "CRITERIA_PREREG.md"
RESULT_NAME = "README.md"


def _git(*args):
    """→ (rc, stdout)。⚠ 必给 encoding+errors：不给时 stdout 会静默变 None（本仓有案）。"""
    r = subprocess.run(("git",) + args, cwd=REPO_ROOT, capture_output=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "")


def first_add_commit(relpath):
    """→ 首次把该路径加入版本库的提交哈希；从未入库则 None。"""
    rc, out = _git("log", "--diff-filter=A", "--format=%H", "--", relpath)
    if rc != 0:
        return None
    hashes = [l.strip() for l in out.splitlines() if l.strip()]
    return hashes[-1] if hashes else None      # log 是新→旧，最旧那条＝首次加入


def _is_ancestor(a, b):
    rc, _ = _git("merge-base", "--is-ancestor", a, b)
    return rc == 0                             # 注意：一个提交是自己的祖先 ⇒ 同提交回 True


def judge_order(prereg_add, result_add, ancestor_fn):
    """纯函数：给两个提交（或 None）判顺序 → (通过?, 理由)。

    抽成纯函数是为了**能喂合成输入**：干净仓上只有一种真实情形（同提交），
    「真命中」与「假命中」两个方向只能靠合成对照分别下断言。
    """
    if prereg_add is None and result_add is None:
        return True, "两者都未入库 —— 不判（还没有任何顺序可言）"
    if prereg_add is None:
        return False, "结果已入库而判据**未入库** ⇒ 正是要防的形状：先有结果、判据还没有"
    if result_add is None:
        return True, "判据已入库、结果未入库 ⇒ 顺序正确"
    if prereg_add == result_add:
        return True, "同一提交 —— 算过（证不了顺序，但无作假痕迹）"
    if ancestor_fn(prereg_add, result_add):
        return True, "判据的提交是结果的提交的祖先 ⇒ 判据更早"
    if ancestor_fn(result_add, prereg_add):
        return False, ("判据**晚于**结果入库 ⇒ 事后补判据的形状（结果 %s → 判据 %s）"
                       % (result_add[:8], prereg_add[:8]))
    return False, ("两个提交**无祖先关系**（%s 与 %s）—— 本门不猜，需人看："
                   "可能是跨分支搬运或历史被改写" % (prereg_add[:8], result_add[:8]))


def _dirs_with_prereg():
    if not os.path.isdir(EVIDENCE):
        return []
    out = []
    for name in sorted(os.listdir(EVIDENCE)):
        if os.path.isfile(os.path.join(EVIDENCE, name, PREREG_NAME)):
            out.append(name)
    return out


def test_every_prereg_is_not_committed_later_than_its_results():
    dirs = _dirs_with_prereg()
    # 非空自证：零命中要么量法坏了、要么目录改名了，**不许静默通过**（零本身正是它存在的理由）
    assert dirs, (
        "evidence/ 下一个 %s 都没找到 —— 先怀疑量法或目录改名，别当成「没有要守的东西」。"
        "若确实不再有任何预登记判据文件，改这条断言时要在提交说明里写清为什么。" % PREREG_NAME)

    problems = []
    for name in dirs:
        pre_rel = "evidence/%s/%s" % (name, PREREG_NAME)
        res_rel = "evidence/%s/%s" % (name, RESULT_NAME)
        ok, why = judge_order(first_add_commit(pre_rel), first_add_commit(res_rel), _is_ancestor)
        if not ok:
            problems.append("%s：%s" % (name, why))
    assert not problems, (
        "判据晚于结果入库：\n  " + "\n  ".join(problems)
        + "\n⚠ 判据＝「不得更晚」（同一提交算过）。修法是**下一批先单独提判据那一笔**，"
          "不是改这道门；已经发生的那一批**不要重写历史**，在证据里写明时序未被 git 证实。")


# ------------------------------------------------------------------ 合成对照（永远会跑）
def _fake_ancestor(edges):
    """edges＝{(a, b)} 表示 a 是 b 的祖先。同提交在 judge_order 里先被短路，不靠这里。"""
    return lambda a, b: (a, b) in edges


def test_same_commit_passes():
    """本仓现存那一批就是这种情形 —— 它必须过，否则这道门第一天就要豁免项。"""
    ok, why = judge_order("abc", "abc", _fake_ancestor(set()))
    assert ok and "同一提交" in why, why


def test_prereg_later_than_results_is_caught():
    """🔴 阳性对照：判据晚于结果必须红。**没有它，一道恒真的门与一道好门长得一样。**"""
    ok, why = judge_order("PRE", "RES", _fake_ancestor({("RES", "PRE")}))
    assert not ok and "晚于" in why, why


def test_results_committed_but_prereg_missing_is_caught():
    """结果入库而判据根本没入库 —— 同一形状的极端版，同样必须红。"""
    ok, why = judge_order(None, "RES", _fake_ancestor(set()))
    assert not ok and "未入库" in why, why


def test_prereg_earlier_passes():
    """真命中方向：判据更早必须**过**。收紧判据自带把门推成「永不通过」的风险，
    而那个方向**不会被上面几条阳性对照顺带确认**。"""
    ok, why = judge_order("PRE", "RES", _fake_ancestor({("PRE", "RES")}))
    assert ok and "更早" in why, why


def test_unrelated_commits_are_not_silently_passed():
    """两个提交无祖先关系时不许猜 —— 「不知道」要响亮，不能悄悄算过。"""
    ok, why = judge_order("A", "B", _fake_ancestor(set()))
    assert not ok and "无祖先关系" in why, why
