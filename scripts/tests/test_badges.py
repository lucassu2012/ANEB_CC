# -*- coding: utf-8 -*-
"""徽章值守卫（SPEC-4 4.4 砍④脚本侧 / v3 lane）。

钉四条设计承诺：①测不到写 unknown 而不是 0/猜；②**不沿用上一次的值**
（旧 badges.txt 存在时也必须被本次真值覆盖）；③reflex 有红时徽章要说出来，
不能只印总数冒充全绿；④每个值带可核的 _source。
"""
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import badges

# 仓根：scripts/tests/ 往上两级。本文件末尾那条 D-604② 守卫要拿它当 `git -C` 的
# 工作目录——**不能靠 cwd**：门跑 `run_all.py` 时 `Push-Location` 到的是
# `scripts\tests`，不是仓根（实测；D-630 那条红就是在这个 cwd 下才复现的）。
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_GREEN_LOG = """verify_all run at 20260829-000000
=== verify_all summary (scope: all) ===
PASS           campaign-analysis-unit  campaign-analysis reflex: 741/741 passed
checks: 21 total / 0 FAIL / 0 NOT_EXECUTED / 0 SKIPPED_SCOPE
"""

_RED_LOG = """verify_all run at 20260829-000001
FAIL           campaign-analysis-unit  reflex test(s) failed; see log
campaign-analysis reflex: 739/741 passed
checks: 21 total / 1 FAIL / 0 NOT_EXECUTED / 0 SKIPPED_SCOPE
"""

_LEDGER_CSV = "face,key,count\ntotal,real_runs,110\ntotal,scenarios,624\n"


def _write(d, name, text):
    p = os.path.join(d, name)
    io.open(p, "w", encoding="utf-8", newline="").write(text)
    return p


_MULTI_SUITE_LOG = """verify_all run at 20260830-161222
PASS           campaign-analysis-unit  campaign-analysis reflex: 785/785 passed
campaign-analysis reflex: 785/785 passed
PASS           obs-tools-e1-unit  e1 reflex: 82/82 passed
e1 reflex: 82/82 passed
PASS           obs-tools-e234-unit  e234 reflex: 106/106 passed
e234 reflex: 106/106 passed
checks: 25 total / 0 FAIL / 0 NOT_EXECUTED / 0 SKIPPED_SCOPE
"""


def test_reflex_tests_sums_every_suite_on_the_gate_not_just_the_first():
    """门上有几套反例跑器，徽章就要数几套——**键名叫 `reflex_tests`，不叫「某一套」**。

    实测成因（2026-08-30）：`obs-tools-e1-unit` / `obs-tools-e234-unit` 两道门接进来后，
    门上跑 785＋82＋106＝973 条，而徽章仍报 **785**（旧实现只正则 campaign 那一套）
    ⇒ **周报模板拿它当「本仓有多少条反例」用，少报 188 且不报错**。
    ⚠ 旧实现在**单套**日志上与新实现同值，所以既有四条测试**全绿**——
    **这条必须用多套日志，否则它守不住任何东西**（同族：测试围着一条没被执行的路径打转）。

    同时钉住**同一套在日志里出现多次**（跑器原始输出 + Add-Result 汇总行）不得重复计数。
    """
    with tempfile.TemporaryDirectory() as d:
        log = _write(d, "verify_all_20260830-161222.log", _MULTI_SUITE_LOG)
        csv = _write(d, "CORPUS_LEDGER.csv", _LEDGER_CSV)
        rows = badges.build(log, csv)
    by = {k: (v, s) for k, v, s in rows}
    assert by["reflex_tests"][0] == "973", by["reflex_tests"]
    src = by["reflex_tests"][1]
    for suite in ("campaign-analysis 785", "e1 82", "e234 106"):
        assert suite in src, src          # 来源自述：数字不必读者猜它涵盖谁


def test_one_red_suite_among_several_is_not_hidden_by_the_sum():
    """多套里只要有一套不全绿，**求和不得把它抹平**——徽章在有红的那次必须出声。"""
    red = _MULTI_SUITE_LOG.replace("e1 reflex: 82/82 passed",
                                   "e1 reflex: 80/82 passed")
    with tempfile.TemporaryDirectory() as d:
        log = _write(d, "verify_all_20260830-161223.log", red)
        csv = _write(d, "CORPUS_LEDGER.csv", _LEDGER_CSV)
        rows = badges.build(log, csv)
    by = {k: (v, s) for k, v, s in rows}
    assert by["reflex_tests"][0] == "971/973", by["reflex_tests"]
    assert "NOT all green" in by["reflex_tests"][1], by["reflex_tests"]


def test_values_come_from_the_chain_log_not_from_thin_air():
    """绿链跑：三个值都取自实测行，且各带可核来源。"""
    with tempfile.TemporaryDirectory() as d:
        log = _write(d, "verify_all_20260829-000000.log", _GREEN_LOG)
        csv = _write(d, "CORPUS_LEDGER.csv", _LEDGER_CSV)
        rows = badges.build(log, csv)
    got = {k: v for k, v, _ in rows}
    assert got == {"gate_count": "21", "reflex_tests": "741",
                   "corpus_real_runs": "110"}
    for _, _, source in rows:                       # ④ 每项来源可核
        assert source and "unknown" not in source


def test_a_missing_measurement_is_unknown_never_zero_and_never_guessed():
    """日志里没有那一行 ⇒ unknown + 说明理由；**不是 0，也不是沿用上次**。

    反例证伪：把 UNKNOWN 换成 "0" 或让它回退到旧 badges.txt，本条即红。
    """
    with tempfile.TemporaryDirectory() as d:
        # 一份 T69 之前形态的旧日志：没有 checks: 行（真实发生过，首跑即撞）
        log = _write(d, "verify_all_20260101-000000.log",
                     "verify_all run\nPASS  something  ok\n")
        csv = _write(d, "CORPUS_LEDGER.csv", _LEDGER_CSV)
        rows = badges.build(log, csv)
    by = {k: (v, s) for k, v, s in rows}
    assert by["gate_count"][0] == "unknown" and by["gate_count"][0] != "0"
    assert "no 'checks: N total'" in by["gate_count"][1]
    assert by["reflex_tests"][0] == "unknown"
    assert by["corpus_real_runs"][0] == "110"        # 能测到的那项照常给值


def test_a_previous_badges_file_is_never_carried_over():
    """②旧 badges.txt 在场也必须被本次真值覆盖——过期的徽章比没有更危险。"""
    with tempfile.TemporaryDirectory() as d:
        stale = _write(d, "badges.txt",
                       "gate_count=999\nreflex_tests=999\ncorpus_real_runs=999\n")
        log = _write(d, "verify_all_20260829-000000.log", _GREEN_LOG)
        csv = _write(d, "CORPUS_LEDGER.csv", _LEDGER_CSV)
        badges.main(["--log", log, "--csv", csv, "--out", stale])
        txt = io.open(stale, encoding="utf-8").read()
    assert "999" not in txt, "旧值被沿用了"
    assert "gate_count=21" in txt and "reflex_tests=741" in txt


def test_a_red_run_is_stated_not_rounded_up_to_the_total():
    """③有红那次，徽章要印 739/741 并标 NOT all green，不能只印 741 冒充全绿。

    反例证伪：去掉 passed != total 分支（直接 return total），本条即红。
    """
    with tempfile.TemporaryDirectory() as d:
        log = _write(d, "verify_all_20260829-000001.log", _RED_LOG)
        csv = _write(d, "CORPUS_LEDGER.csv", _LEDGER_CSV)
        rows = badges.build(log, csv)
    by = {k: (v, s) for k, v, s in rows}
    assert by["reflex_tests"][0] == "739/741"
    assert "NOT all green" in by["reflex_tests"][1]


def test_rendered_face_states_the_do_not_copy_and_freshness_rules():
    """规则句必须在产物上（读者拿到的是 badges.txt，不是本文件的注释）。"""
    with tempfile.TemporaryDirectory() as d:
        log = _write(d, "verify_all_20260829-000000.log", _GREEN_LOG)
        csv = _write(d, "CORPUS_LEDGER.csv", _LEDGER_CSV)
        out = badges.render(badges.build(log, csv), log)
    assert "勿手编" in out
    assert "不要把数字抄进正文" in out
    assert "不是沿用上次" in out
    assert "新鲜度=来源日志的新鲜度" in out
    assert "verify_all_20260829-000000.log" in out   # 来源可追


def _git_show(path_in_head):
    """读 HEAD 里某个文件的字节。**刻意用字节模式**，不给 `text=True`。

    理由不是洁癖：`subprocess.run(text=True)` 不显式给 `encoding=` 时，
    父子两侧编码不一致会让 `UnicodeDecodeError` 抛在 `_readerthread` 线程里被吞掉，
    `run()` 照常返回而 `stdout` 是 **None**（D-630 实证，害主树红过一次）。
    字节模式根本不解码，天然免疫；要文本时自己 `.decode(errors=...)`。
    """
    import subprocess
    r = subprocess.run(["git", "show", "HEAD:" + path_in_head],
                       capture_output=True, cwd=_REPO)
    return r


def test_the_published_badges_name_a_log_that_is_actually_in_the_repo():
    """入库的 badges 必须点名一份**同批入库**的日志，且那日志是一次全绿 `-Scope all`。

    D-604② 原文两半：「badges 的对外数字只许出自 `-Scope all` 的绿跑，**且其点名
    日志必须随批 `git add -f` 可核**」。**后半条至今没有执行面** —— 我 `b80004b`
    只落了 badges 与清单、没落它点名的 `verify_all_20260830-232221-26204.log`，
    于是已发布的对外数字指向一个**仓里不存在的文件**，而**没有任何东西报错**。
    这比本仓熟悉的「写了门却没挂上清单」更前一格：**门根本没写**（`249ae1c` 同形）。
    本文件开篇自称钉着「④每个值带**可核**的 `_source`」——而在此之前，
    没有任何东西核过那个 source 是否真够得着。本条即那个缺席的核查。

    ⚠ **判据落在 HEAD，不落在工作区**：跑完到落库之间，工作区的 badges 必然点着
    一份还没 `add` 的新日志；拿工作区判会在**合法流程**里假红。这条守的是
    「**入库的**东西自洽」，不是「此刻磁盘上的东西自洽」。

    ⚠ 两处点名要**互相对得上**（`# 来源日志：` 与 `gate_count_source=`）：
    同一个事实写在两处，就有一处先漂的可能，而漂了没人会发现。

    绿跑判据取 `0 FAIL` 与 `0 SKIPPED_SCOPE`（**不含 NOT_EXECUTED**：它表示某道门
    什么都没验，但 `gate_count` 数的是门不是通过数，仍然诚实）。
    历史支撑：`175357` 与 `232221-26204` 两次已发布的点名日志都是 `0/0/0`。
    """
    import re
    badges_raw = _git_show("evidence/phase0/badges.txt")
    assert badges_raw.returncode == 0, (
        "HEAD 里读不到 evidence/phase0/badges.txt——徽章根本没入库？")
    body = badges_raw.stdout.decode("utf-8-sig", errors="replace")

    named = re.findall(r"来源日志：(verify_all_[0-9A-Za-z_.-]+?[.]log)", body)
    from_src = re.findall(
        r"gate_count_source=verify_all log (verify_all_[0-9A-Za-z_.-]+?[.]log)", body)
    assert named, "badges.txt 里找不到 `# 来源日志：…` 那一行"
    assert from_src, "badges.txt 里找不到 `gate_count_source=verify_all log …`"
    # ⚠ 这一条是**漂移钉，不是承重守卫**：突变审计把它停掉后套件仍绿
    # （SURVIVED），因为 HEAD 里两处本来就一致、没有可咬的东西。它要等到
    # 将来有人只改其中一处时才发挥作用。**照实标注，不假装 100% 覆盖**——
    # 本仓的规矩是给测试标清「回归钉」还是「承重守卫」。
    assert named[0] == from_src[0], (
        "同一份日志被两处点名却对不上：注释行说 %s，gate_count_source 说 %s"
        % (named[0], from_src[0]))

    log_path = "evidence/phase0/" + named[0]
    log_raw = _git_show(log_path)
    assert log_raw.returncode == 0, (
        "已入库的 badges 点名 %s，**而它不在 HEAD 里** ⇒ 对外数字指向一个仓里"
        "不存在的文件，别的 checkout 无从复核（D-604②：点名日志必须随批 "
        "`git add -f`；`249ae1c` 同形）。修法：把它 `git add -f` 进同一批。"
        % log_path)

    log = log_raw.stdout.decode("utf-8-sig", errors="replace")
    summary = [ln for ln in log.splitlines() if ln.startswith("checks:")]
    assert summary, "点名日志 %s 里没有 `checks:` 汇总行——它是一份 verify_all 日志吗" % log_path
    m = re.search(r"(\d+) total / (\d+) FAIL / (\d+) NOT_EXECUTED / (\d+) SKIPPED_SCOPE",
                  summary[-1])
    assert m, "`checks:` 行格式变了，本条的判据跟不上：%r" % summary[-1]
    _total, fail, _ne, skipped = (int(x) for x in m.groups())
    assert fail == 0, (
        "已发布的徽章出自一次**红跑**（%s：%s FAIL）——D-604②：对外数字只许出自"
        "全绿 `-Scope all`，出红则 badges 保持 M 态，宁可 M 态过夜不发布假绿"
        % (log_path, fail))
    assert skipped == 0, (
        "已发布的徽章出自一次**分层跑**（%s：%s SKIPPED_SCOPE）——那会把「本仓有"
        "几道门」钉在一次没跑全的跑上（D-604② 正是为这个立的）" % (log_path, skipped))
    assert "NOT all green" not in body, (
        "badges 自己写着 NOT all green 却被入库了：%s" % log_path)
