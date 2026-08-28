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
