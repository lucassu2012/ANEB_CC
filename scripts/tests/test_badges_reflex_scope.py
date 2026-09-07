# -*- coding: utf-8 -*-
"""反向守卫：**链上任何一道门自述跑了 reflex 测试，就必须进得了 `reflex_tests` 这个聚合数**。

🔴 **为什么要一道反向的**（这是本文件存在的全部理由）：
`badges.reflex_tests` 用正则从链跑日志里捞「谁在里面」。它的 `_source` 串把捞到的逐套列出，
**读起来非常可信** —— 但**一个自述来源的聚合数，告诉你的是它的构成，不是它的完整性**：
那串列的是「谁在里面」，**没有人能从中看出「谁不在」**。

实证两次，同一个 bug：
- 2026-08-30：接进 `obs-tools-e1/e234` 两道门后，徽章仍只报 `campaign-analysis` ⇒ **少报 188**；
  修法是「求和 ＋ 让来源自述」。
- 2026-09-07（本轮全链）：`adapters-spec-unit` 42／`portraits-redline-unit` 46／
  `portraits-schema-unit` 10 三道门**自述跑的就是 reflex 测试**，只因措辞是
  `ran 42 reflex tests: …` 而非 `<套名> reflex: 42/42 passed` ⇒ **98 条全部落在分子外**
  （1078 而非 1176）。**上一次的修法放宽了模式，却没解决「范围」。**

⇒ **第三次同形只是换一族措辞的事。** 所以这里不再放宽模式，而是从**反面**判：

    凡链跑摘要里某道 PASS 门的明细含 `reflex`，它的条数就必须出现在收集器的总数里；
    **本文件读不懂的措辞判红，不跳过。**

**它与收集器不共享哪一层**（否则两法互证是假的）：
 - **枚举单位不同**：本文件只认**摘要块里的门结果行**（门名→明细），收集器扫的是全文任意行；
 - **取数方式不同**：本文件按显式列出的形状表取「总数」，收集器按它自己的两条正则取；
 - **失败语义不同**：**收集器对读不懂的行是「静默不收」，本文件是「判红」** —— 这一条是关键，
   收集器根本没有与之对应的行为。
共享的只有「同一份日志」，那是不可避免的一层，写出来免得把互证说大。

⚠ **只管 PASS 门**：红门的明细是 `reflex test(s) failed; see log`，**含 reflex 但无计数**。
红门的计数由 `test_badges.py` 的「NOT all green」那条负责，不在本文件范围内——
**范围写出来，因为一条不说明自己边界的守卫，日后会被当成它没答过的问题的答案。**
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/

import badges as bd  # noqa: E402

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SCRIPTS)
CHAIN_LOG_GLOB = os.path.join(REPO_ROOT, "evidence", "phase0", "verify_all_*.log")

SUMMARY_MARKER = "=== verify_all summary"
_GATE_LINE = re.compile(r"^(PASS|FAIL|NOT_EXECUTED|SKIPPED_SCOPE)\s+(\S+)\s\s+(.*?)\s*$")

# 已知的自述形状。**加一族新措辞就得在这里显名加一条**——那正是本文件要制造的摩擦：
# 悄悄换措辞会红，而不是悄悄少算。
_SHAPES = (
    # `campaign-analysis reflex: 841/841 passed`
    (re.compile(r"\breflex:\s*\d+\s*/\s*(\d+)\s*passed"), 1),
    # `ran 42 reflex tests: 42 passed, 0 failed` / `ran 10 schema reflex tests: …`
    (re.compile(r"\bran\s+(\d+)[^:]*\breflex tests:\s*\d+\s+passed"), 1),
)


def _summary_block(text):
    """只取摘要块。**取全文会把跑器原始输出也算进来，同一套被数两遍。**"""
    i = text.find(SUMMARY_MARKER)
    return text[i:] if i != -1 else ""


def gate_reflex_totals(text):
    """→ ({门名: 条数}, [读不懂的行])。读不懂**单列返回**，由调用方判红——
    **不在这里 continue**：静默跳过正是本文件要防的那个动作。"""
    totals, unparsed = {}, []
    for line in _summary_block(text).splitlines():
        m = _GATE_LINE.match(line)
        if not m:
            continue
        state, gate, detail = m.group(1), m.group(2), m.group(3)
        if "reflex" not in detail.lower():
            continue
        if state != "PASS":
            continue          # 红门计数归 test_badges.py，见模块 docstring
        for pat, grp in _SHAPES:
            hit = pat.search(detail)
            if hit:
                totals[gate] = int(hit.group(grp))
                break
        else:
            unparsed.append("%s: %s" % (gate, detail))
    return totals, unparsed


def problems(text, collector_value):
    """把「本文件独立数出来的」与「收集器报的」对齐，列出所有不一致。"""
    out = []
    totals, unparsed = gate_reflex_totals(text)
    for u in unparsed:
        out.append("自述 reflex 但本守卫读不懂其措辞（**新措辞必须显名加进 _SHAPES**）：" + u)
    if not totals and not unparsed:
        out.append("摘要块里一条自述 reflex 的 PASS 门都没有 —— 先怀疑量法坏了，别当成没有门")
    mine = sum(totals.values())
    try:
        theirs = int(str(collector_value))
    except (TypeError, ValueError):
        out.append("收集器报了非整数 %r（红套件会报 'p/t'，那种情况本守卫不比总数）"
                   % (collector_value,))
        return out
    if mine != theirs:
        out.append(
            "范围不一致：本守卫按门数出 %d（%s），而 `badges.reflex_tests` 报 %d。"
            "差额 %d —— **有门自述跑了 reflex，却没进那个聚合数**。"
            % (mine, ", ".join("%s=%d" % kv for kv in sorted(totals.items())),
               theirs, mine - theirs))
    return out


# ---------------------------------------------------------------- 合成夹具（永远会跑）
#
# ⚠ **夹具必须同时含两族措辞**。既有 `test_badges.py` 的夹具**只有形状 1**——
# **夹具与收集器出自同一个假设**，这正是那 98 条能安静躲过所有测试的第三层原因。
_LOG_TWO_SHAPES = """\
=== verify_all summary (scope: all) ===
PASS           adapters-spec-unit  ran 42 reflex tests: 42 passed, 0 failed
PASS           portraits-schema-unit  ran 10 schema reflex tests: 10 passed, 0 failed
PASS           campaign-analysis-unit  campaign-analysis reflex: 841/841 passed
PASS           obs-tools-e1-unit  e1 reflex: 85/85 passed
PASS           voice-plan-parity  voice plan parity OK: 9 constants matched
checks: 5 total / 0 FAIL / 0 NOT_EXECUTED / 0 SKIPPED_SCOPE
"""


def test_the_guard_counts_both_wordings_not_just_the_canonical_one():
    totals, unparsed = gate_reflex_totals(_LOG_TWO_SHAPES)
    assert not unparsed, unparsed
    assert totals == {
        "adapters-spec-unit": 42,
        "portraits-schema-unit": 10,
        "campaign-analysis-unit": 841,
        "obs-tools-e1-unit": 85,
    }, totals
    assert sum(totals.values()) == 978


def test_it_catches_exactly_the_2026_09_07_gap():
    """把收集器的值换成「只数形状 1」的那个数 ⇒ 必须红，并说出差额。

    这是本文件的**阳性对照**：它证明这道检查有区分能力，不是恒真的。
    """
    only_shape_one = 841 + 85
    out = problems(_LOG_TWO_SHAPES, only_shape_one)
    assert out, "少算 52 条却没报——这道守卫是哑的"
    joined = " ".join(out)
    assert "范围不一致" in joined and "52" in joined, out


def test_an_unknown_wording_goes_red_instead_of_being_skipped():
    """🔴 **最要紧的一条**：读不懂 ⇒ 红，不是 ⇒ 跳过。

    「悄悄少算」与「没有这道门」在总数上长得一模一样；只有判红能把它们分开。
    """
    log = _LOG_TWO_SHAPES.replace(
        "PASS           obs-tools-e1-unit  e1 reflex: 85/85 passed",
        "PASS           obs-tools-e1-unit  e1 executed 85 reflex cases OK",
    )
    totals, unparsed = gate_reflex_totals(log)
    assert "obs-tools-e1-unit" not in totals
    assert len(unparsed) == 1 and "obs-tools-e1-unit" in unparsed[0], unparsed
    out = problems(log, 893)      # 42+10+841，恰好与本守卫数出的相等
    assert any("读不懂其措辞" in p for p in out), (
        "两边**碰巧相等**时也必须红——否则新措辞会在总数对上的那一刻永久隐身。%r" % (out,))


# ---------------------------------------------------------------- 真链跑日志（有则跑）
def test_the_latest_chain_log_has_no_uncounted_reflex_gate():
    """对**真的**链跑日志跑同一比对。

    ⚠ 鲜克隆里没有链跑日志（`verify_all_*.log` 被 `.gitignore` 排除）⇒ 本条会 **SKIP**，
    而跑器会把 SKIP 显名印出来——**「没跑」不许伪装成「过了」**。
    """
    logs = sorted(glob.glob(CHAIN_LOG_GLOB))
    if not logs:
        import pytest
        pytest.skip("本树无 verify_all_*.log（链跑日志被 .gitignore 排除）；合成夹具那几条已跑")
    log = logs[-1]
    with open(log, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    totals, _ = gate_reflex_totals(text)
    assert totals, ("在 %s 的摘要块里一条自述 reflex 的门都没有 —— "
                    "先查是不是摘要标记变了，别当成没有门" % os.path.basename(log))
    val, src = bd.reflex_tests(log)
    out = problems(text, val)
    assert not out, "\n".join(out) + "\n（来源：%s；收集器自述：%s）" % (
        os.path.basename(log), src)
