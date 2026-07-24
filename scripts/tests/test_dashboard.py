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
