# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/dashboard.py extract() aggregation invariants.

The per-run dashboard is a labeled M2 deliverable surface but had only CLI smoke
coverage (D-108). These pin the invariants smoke cannot see: per-edge-set ITL
bucketing (R-27: counts on different edges are never summed together), the AQS
legacy fallback chain, and grade-vs-value key routing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import dashboard as db
from synth import make_record


def test_the_per_run_copies_of_the_numeric_guards_match_the_shared_ones():
    """fnum exists THREE times: campaign_common, analyze_results, dashboard.
    Both CLIs commit to stdlib only in their docstrings and nothing imports
    them, so each carries its own copy. D-148 taught the campaign layer to
    reject NaN and Infinity and reached neither: one NaN in one scenario made
    analyze_results report a KPI with median=nan over n=20 — the median of
    twenty samples destroyed by one of them, exit 0 and no warning (D-314) —
    and rendered as `nan` on the dashboard page (D-315).

    The duplication stays: making either CLI depend on campaign_common would
    change what its docstring says it is. The divergence is pinned instead. All
    three must answer the same on every value, so fixing only one of them fails.
    Compared by repr because NaN is not equal to itself, and an equality test
    that quietly passes on two NaNs would be a guard that lies.
    """
    import math
    import analyze_results as ar
    import campaign_common as cc

    values = [0, 1, -1, 2.5, float("nan"), float("inf"), float("-inf"),
              True, False, None, "5", []]
    assert any(isinstance(v, float) and not math.isfinite(v) for v in values), \
        "no non-finite value in the battery; this guard checks nothing"

    for v in values:
        got = {"campaign_common": cc.fnum(v), "analyze_results": ar.fnum(v),
               "dashboard": db.fnum(v)}
        assert len(set(repr(x) for x in got.values())) == 1, (v, got)

    poisoned = [10, 20, float("nan"), 40, 50]
    got = ar.median_or_none(poisoned)
    assert got == cc.median(poisoned), (got, cc.median(poisoned))
    assert got is not None and math.isfinite(got), (
        "one NaN still poisons the median of the values around it: %r" % got)


def test_the_two_html_escapers_agree():
    """§2.14 says EVERY group of same-named implementations needs something
    forcing them to agree, and D-315 guarded two of the three: esc() was waved
    through as "byte-identical in both files today". Byte-identical is exactly
    when a divergence is easiest to introduce and hardest to notice — dropping
    quote=True in one of them leaves attribute context unescaped on one surface
    only, and nothing on the page looks wrong until it does (D-317).
    """
    import campaign_report as cr

    for s in ["<b>", "a&b", '"q"', "'q'", "plain", 5, None, "点位 SZ-01"]:
        assert cr.esc(s) == db.esc(s), (s, cr.esc(s), db.esc(s))
    assert db.esc('"') != '"', \
        "esc does not escape quotes at all; this battery checks nothing"


def test_every_loader_drops_the_same_repeat_run_id():
    """load_records exists three times too. The campaign one de-duplicates by
    run.run_id because a run counted twice "silently INFLATES apparent
    confidence" — and neither CLI copy did. Measured: the same file listed twice
    (trivial with overlapping globs, or with D-09 dual-write files) took a
    20-run corpus to `records=40` on both, doubling every n on the page, with
    nothing on either surface to say so (D-315).

    Pinned by behaviour rather than by implementation: give all three a corpus
    whose first run_id repeats and they must return the same count.
    """
    import json
    import os
    import tempfile
    import analyze_results as ar
    import campaign_common as cc

    recs = [make_record(aqs=90, run_id="R-1"), make_record(aqs=80, run_id="R-2")]
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "c.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            for r in list(recs) + [recs[0]]:  # R-1 written twice
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        with open(p, encoding="utf-8") as f:
            assert sum(1 for _ in f) == 3, \
                "corpus does not repeat a run_id; this guard checks nothing"
        n = {"campaign_common": len(cc.load_records([p], quiet=True)[0]),
             "analyze_results": len(ar.load_records([p])),
             "dashboard": len(db.load_records([p])[0])}

    assert n["campaign_common"] == 2, n  # the reference behaviour, restated
    assert len(set(n.values())) == 1, n


def _rec(*, kpi=None, hist=None, aqs=90):
    rec = make_record(aqs=aqs, scenarios=[("s1_chat", dict(kpi or {}))])
    if hist is not None:
        rec["scenarios"][0]["itl_histogram"] = hist
    return rec


def test_itl_histograms_summed_per_edge_set():
    """R-27: different edge sets accumulate in SEPARATE buckets, never combined."""
    recs = [_rec(hist={"edges_ms": [10, 20, 50], "counts": [1, 2, 3, 4], "total": 10}),
            _rec(hist={"edges_ms": [10, 20, 50], "counts": [10, 20, 30, 40], "total": 100}),
            _rec(hist={"edges_ms": [10, 25, 50], "counts": [5, 5, 5, 5], "total": 20})]
    d = db.extract(recs)
    assert d["itl"][(10, 20, 50)] == [11, 22, 33, 44]
    assert d["itl"][(10, 25, 50)] == [5, 5, 5, 5]
    assert d["itl_total"] == 130


def test_itl_total_falls_back_to_count_sum():
    d = db.extract([_rec(hist={"edges_ms": [10, 20], "counts": [1, 2, 3]})])  # no total
    assert d["itl_total"] == 6


def test_aqs_legacy_fallback_chain():
    modern = _rec(aqs=88)
    legacy_top = _rec(aqs=None)
    legacy_top["aqs"] = 77
    legacy_result = _rec(aqs=None)
    legacy_result["aqs_result"] = {"score": 66}
    d = db.extract([modern, legacy_top, legacy_result])
    assert [r["aqs"] for r in d["runs"]] == [88, 77, 66]


def test_run_flags_extracted():
    rec = _rec(aqs=54)
    rec["run"]["aqs"]["veto_applied"] = True
    rec["run"]["aqs"]["low_confidence"] = True
    rec["run"]["status"] = "aborted:timeout"
    r = db.extract([rec])["runs"][0]
    assert r["veto"] is True
    assert r["low_conf"] is True
    assert r["status"] == "aborted:timeout"


def test_grade_keys_routed_to_grades_not_kpis():
    d = db.extract([_rec(kpi={"t1_ttft_ms": 800, "t1_grade": "good"})])
    assert d["kpis"]["s1_chat"]["t1_ttft_ms"] == [800]
    assert d["grades"]["s1_chat"]["t1"]["good"] == 1
    assert "t1_grade" not in d["kpis"]["s1_chat"]


def test_legacy_value_nesting_accepted():
    d = db.extract([_rec(kpi={"n1_rtt_p50_ms": {"value": 23.5}})])
    assert d["kpis"]["s1_chat"]["n1_rtt_p50_ms"] == [23.5]


def test_null_kpi_not_collected():
    d = db.extract([_rec(kpi={"t1_ttft_ms": None})])
    assert d["kpis"]["s1_chat"]["t1_ttft_ms"] == []


def test_validity_counter():
    a, b = _rec(), _rec()
    b["scenarios"][0]["validity"] = "invalid"
    d = db.extract([a, b])
    assert d["validity"]["valid"] == 1
    assert d["validity"]["invalid"] == 1
