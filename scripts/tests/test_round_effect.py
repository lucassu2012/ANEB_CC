# -*- coding: utf-8 -*-
"""Reflex tests for scripts/round_effect.py (warm-up / first-round penalty)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import round_effect as re_
from synth import make_record


def _rounds(kpi, per_round, drop_round=False):
    """One record whose scenarios carry the given {round: [values]} for `kpi`.

    Profile is s2_coding_agent: neutral under the D-366 ruling — s1_chat's u1
    readings are ruled out of cross-profile pools, so an s1 fixture would hand
    the u1 direction test an empty pool instead of a verdict.
    """
    rec = make_record(campaign={"campaign_id": "c", "tier": "metro", "point_id": "P1",
                                "carrier": "ctcc", "time_band": "busy"},
                      aqs=88, scenarios=[])
    scns = []
    for rnd, values in sorted(per_round.items()):
        for v in values:
            scn = {"profile_id": "s2_coding_agent", "profile_version": "0.2.1",
                   "kpi": {kpi: v}}
            if not drop_round:
                scn["repeat_index"] = rnd
            scns.append(scn)
    rec["scenarios"] = scns
    return [rec]


def _entry(res, kpi):
    return [e for e in res["kpis"] if e["kpi"] == kpi][0]


def test_first_round_penalty_is_flagged_on_latency():
    """D-355's shape: round 0 slower than the rounds after it."""
    # 52.75 vs median(47.2, 47.05)=47.125 -> +11.9%. The original fixture gave
    # 9.81% — just UNDER the 10% gate — and asserted True anyway; it was wrong
    # from birth and nobody knew, because run_all's hand-written module list
    # never included this file (D-364).
    recs = _rounds("t1_ttft_ms", {0: [53.0, 52.5], 1: [47.0, 47.4], 2: [47.2, 46.9]})
    e = _entry(re_.analyze(recs), "t1_ttft_ms")
    assert e["warm_up_suspected"] is True, e
    assert e["first_round_penalty_pct"] > 10
    assert e["not_computable_reason"] is None


def test_a_corpus_without_warm_up_is_not_nagged():
    """The half that matters: a flat corpus must come back clean, or the section
    becomes noise the reader learns to skip."""
    recs = _rounds("t1_ttft_ms", {0: [50.0, 50.2], 1: [50.1, 49.9], 2: [50.0, 50.3]})
    e = _entry(re_.analyze(recs), "t1_ttft_ms")
    assert e["warm_up_suspected"] is False, e
    assert abs(e["first_round_penalty_pct"]) < 2


def test_goodput_direction_is_not_inverted():
    """Higher is better for goodput, so a LOWER first round is the warm-up. A sign
    error here would report a warm-up as an improvement - the direction comes from
    trend.metric_higher_is_better rather than a second copy of the rule (2.14)."""
    warm = _rounds("u1_goodput_mbps", {0: [10.0, 10.2], 1: [12.0, 11.9], 2: [11.5, 11.6]})
    e = _entry(re_.analyze(warm), "u1_goodput_mbps")
    assert e["warm_up_suspected"] is True, e
    assert e["first_round_penalty_pct"] > 10

    # ...and the mirror image: a first round that is FASTER must not be called a
    # warm-up just because it differs.
    fast = _rounds("u1_goodput_mbps", {0: [12.0, 12.1], 1: [10.0, 10.2], 2: [10.1, 10.0]})
    e2 = _entry(re_.analyze(fast), "u1_goodput_mbps")
    assert e2["warm_up_suspected"] is False, e2
    assert e2["first_round_penalty_pct"] < 0


def test_single_round_says_so_instead_of_no_effect():
    """Quick mode is one round. 「查不了」 must not read as 「没问题」 (R-10) - and
    this is the case that matters most, because a single-round corpus is exactly
    the one whose absolute numbers are all cold-start numbers."""
    recs = _rounds("t1_ttft_ms", {0: [50.0, 51.0, 49.0]})
    res = re_.analyze(recs)
    e = _entry(res, "t1_ttft_ms")
    assert e["warm_up_suspected"] is None
    assert e["not_computable_reason"] == "SINGLE_ROUND"
    md = re_.render_markdown(res)
    assert "只有一轮" in md and "冷启动口径" in md, md
    assert "无明显预热" not in md, "a corpus that cannot be checked must not read as clean"


def test_one_sample_per_round_is_not_a_verdict():
    """Two rounds holding one reading each is a difference of two numbers - the
    same arithmetic floor CV and the order-effect positions already use."""
    recs = _rounds("t1_ttft_ms", {0: [52.0], 1: [47.0]})
    e = _entry(re_.analyze(recs), "t1_ttft_ms")
    assert e["warm_up_suspected"] is None
    assert e["not_computable_reason"] == "UNREPLICATED_ROUNDS"


def test_a_scenario_without_a_round_is_not_counted_as_round_zero():
    """R-10: an absent repeat_index is unknown, never merged into the first round
    - which would silently change the very number this section is about."""
    recs = _rounds("t1_ttft_ms", {0: [50.0, 50.5]}, drop_round=True)
    e = _entry(re_.analyze(recs), "t1_ttft_ms")
    assert e["rounds"] == {}, e
    assert e["unknown_round_n"] == 2
    assert e["not_computable_reason"] == "SINGLE_ROUND"


def test_a_label_less_corpus_is_not_blamed_on_quick_mode():
    """D-364: distinct_rounds==0 with values present means the corpus has NO
    repeat_index at all — a producer regression or a foreign corpus, not quick
    mode (quick writes repeat_index=0 too). The old single banner attributed it
    to 「quick 模式每场景只跑一遍」 and dropped the unknown-round note: a
    forensic corpus that lost its labels read as 「单轮、冷启动口径」 — a
    plausible lie about WHY warm-up cannot be checked."""
    recs = _rounds("t1_ttft_ms", {0: [50.0, 50.5]}, drop_round=True)
    s = re_.summarize(recs)
    assert s["no_round_labels"] is True and s["unknown_round_n"] == 2, s
    md = re_.render_markdown(re_.analyze(recs))
    assert "缺失轮次编号" in md and "repeat_index" in md, md
    assert "quick 模式每场景只跑一遍" not in md, md

    # ...and the genuine single round keeps its banner, does not borrow this one.
    s2 = re_.summarize(_rounds("t1_ttft_ms", {0: [50.0, 51.0]}))
    assert s2["no_round_labels"] is False and s2["single_round"] is True, s2

    # Both front doors translate every code this module can emit (D-354's map
    # gained the round codes in D-364; the emitted set is derived from source,
    # not hand-listed, so a new code without a translation fails here).
    import inspect
    import re as regex
    import campaign_report as rpt
    emitted = set(regex.findall(r'not_computable_reason"\]\s*=\s*"(\w+)"',
                                inspect.getsource(re_)))
    assert emitted, "the derived emitted-code set went empty — fix the scan"
    missing = emitted - set(rpt._ORDER_UNJUDGED_WHY)
    assert not missing, (
        f"round_effect emits {missing} with no reader-words translation — "
        "the raw identifier would print into PO-facing prose on both front doors")


def test_summary_and_section_agree():
    """One source for both front doors (2.14, D-338): whatever the section
    judges, the summary counts."""
    recs = _rounds("t1_ttft_ms", {0: [52.0, 51.5], 1: [47.0, 47.4], 2: [47.2, 46.9]})
    res, s = re_.analyze(recs), re_.summarize(recs)
    judged = [e for e in res["kpis"] if e["warm_up_suspected"] is not None]
    assert s["judged"] == len(judged)
    assert len(s["suspected"]) == sum(1 for e in judged if e["warm_up_suspected"])
    assert s["single_round"] is False and s["distinct_rounds"] == 3


def test_markdown_prints_the_measured_percentage_even_when_under_threshold():
    """Measured on real data: TTFT came in at 9.5%, just under the gate. Printing
    only the verdict would hide a number the reader should weigh themselves."""
    recs = _rounds("t1_ttft_ms", {0: [51.0, 51.2], 1: [48.0, 48.2], 2: [48.1, 48.0]})
    md = re_.render_markdown(re_.analyze(recs))
    assert "无明显预热" in md
    assert "6.2" in md or "6.3" in md, md
