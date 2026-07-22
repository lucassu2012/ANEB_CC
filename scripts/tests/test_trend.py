# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/trend.py (N-campaign longitudinal trend).

Pins: chronological ordering by started_at (not id sort), polarity-correct
improving/regressing, non-monotonic paths reported as 'mixed' not a false trend,
and missing-campaign gaps left as None rather than interpolated.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import trend
from synth import aqs_records, kpi_scenario_records


def _camp(aqs, cid, started_ms, *, n=5, point="P1", carrier="cmcc", time_band="busy"):
    return aqs_records(aqs, n, point=point, carrier=carrier, time_band=time_band,
                       campaign_id=cid, started_ms=started_ms)


def test_three_campaign_improving_aqs():
    recs = (_camp(60, "c1", 1000) + _camp(72, "c2", 2000) + _camp(85, "c3", 3000))
    res = trend.analyze(recs)
    assert res["campaigns"] == ["c1", "c2", "c3"]
    c = res["cells"][0]
    assert c["trajectory"] == [60, 72, 85]
    assert c["first_last_delta"] == 25
    assert c["direction"] == "improving"     # AQS higher=better
    assert c["monotonic"] is True


def test_ordering_is_chronological_not_id_sort():
    """c_zzz ran first, c_aaa last: order must follow time, not the id string."""
    recs = (_camp(50, "c_zzz", 1000) + _camp(90, "c_aaa", 5000))
    assert trend.analyze(recs)["campaigns"] == ["c_zzz", "c_aaa"]


def test_explicit_order_overrides():
    recs = (_camp(50, "c1", 1000) + _camp(90, "c2", 2000))
    res = trend.analyze(recs, order=["c2", "c1"])
    assert res["campaigns"] == ["c2", "c1"]
    assert res["cells"][0]["trajectory"] == [90, 50]


def test_regressing_aqs():
    recs = (_camp(85, "c1", 1000) + _camp(60, "c2", 2000))
    assert trend.analyze(recs)["cells"][0]["direction"] == "regressing"


def test_latency_polarity_lower_is_better():
    """For n1_rtt, a DECREASE is an improvement (equal ts -> id tie-break c1<c2)."""
    recs = (kpi_scenario_records(5, kpi={"n1_rtt_p50_ms": 80}, campaign_id="c1")
            + kpi_scenario_records(5, kpi={"n1_rtt_p50_ms": 40}, campaign_id="c2"))
    res = trend.analyze(recs, metric="n1_rtt_p50_ms")
    assert res["campaigns"] == ["c1", "c2"]
    c = res["cells"][0]
    assert c["first_last_delta"] == -40
    assert c["direction"] == "improving"     # lower latency = better


def test_non_monotonic_is_mixed_not_false_trend():
    recs = (_camp(60, "c1", 1000) + _camp(90, "c2", 2000) + _camp(65, "c3", 3000))
    c = trend.analyze(recs)["cells"][0]
    assert c["monotonic"] is False
    assert c["direction"] == "mixed"         # net +5 but dipped -> not "improving"


def test_missing_campaign_gap_not_interpolated():
    recs = (_camp(60, "c1", 1000, point="P1") + _camp(80, "c3", 3000, point="P1")
            + _camp(70, "c2", 2000, point="P2"))   # P1 absent from c2
    res = trend.analyze(recs)
    assert res["campaigns"] == ["c1", "c2", "c3"]
    p1 = next(c for c in res["cells"] if c["cell"]["point_id"] == "P1")
    assert p1["trajectory"] == [60, None, 80]      # gap, not 70
    assert p1["present_count"] == 2
    assert p1["first_last_delta"] == 20            # first/last PRESENT points


def test_single_present_point_not_computable():
    recs = (_camp(60, "c1", 1000, point="P1")
            + _camp(70, "c2", 2000, point="P2"))   # each cell in one campaign only
    p1 = next(c for c in trend.analyze(recs)["cells"] if c["cell"]["point_id"] == "P1")
    assert p1["direction"] is None
    assert p1["not_computable_reason"] == "NEED_2_POINTS"


def test_single_campaign_renders_guidance():
    res = trend.analyze(_camp(80, "c1", 1000))
    assert len(res["campaigns"]) == 1
    assert "少于 2 个战役" in trend.render_markdown(res)


def test_low_confidence_flagged():
    recs = (_camp(60, "c1", 1000, n=2) + _camp(80, "c2", 2000, n=2))
    assert trend.analyze(recs)["cells"][0]["low_confidence"] is True


def test_markdown_renders_trajectory():
    recs = (_camp(60, "c1", 1000) + _camp(72, "c2", 2000) + _camp(85, "c3", 3000))
    md = trend.render_markdown(trend.analyze(recs))
    assert "纵向趋势" in md
    assert "改善" in md
    assert "c1 → c2 → c3" in md
