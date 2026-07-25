# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/stability.py (coefficient-of-variation gate)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import stability
import campaign_report as rpt
from synth import kpi_scenario_records


def test_cv_known_values():
    assert stability.cv_percent([10, 10, 10]) == 0.0
    # mean 10, sample stdev 2 -> CV 20%
    cv = stability.cv_percent([8, 10, 12])
    assert abs(cv - 20.0) < 1e-9


def test_cv_below_two_samples_is_none():
    assert stability.cv_percent([5]) is None
    assert stability.cv_percent([]) is None


def _cell(i, *, unstable=False, cv=3.0):
    return {"cell": {"point_id": f"P{i:02d}", "carrier": "cmcc", "time_band": "busy",
                     "tier": "metro", "profile_id": "s1_chat"},
            "n": 5, "median": 100.0, "mean": 100.0, "cv_percent": cv,
            "unstable": unstable, "low_confidence": False, "kpi": "t1_ttft_ms"}


def test_stable_row_cap_declares_what_it_omitted():
    """No silent truncation (D-117): the omission is stated, with a pointer to
    the complete data."""
    cells = [_cell(i) for i in range(40)]
    md = stability.render_markdown(cells, "t1_ttft_ms", max_stable_rows=25)
    assert md.count("point_id=P") == 25
    assert "另有 **15**" in md
    assert "_stability.csv" in md


def test_cap_never_drops_unstable_or_not_computable_rows():
    """The signal rows survive any cap — only stable ones fold away."""
    cells = ([_cell(i) for i in range(30)]
             + [_cell(90, unstable=True, cv=42.0), _cell(91, cv=None)])
    md = stability.render_markdown(cells, "t1_ttft_ms", max_stable_rows=5)
    assert "point_id=P90" in md and "point_id=P91" in md
    assert md.count("point_id=P") == 7   # 5 stable + unstable + not-computable


def test_cap_can_be_disabled_for_a_focused_look():
    """Someone who ran the standalone tool came to look at stability; the cap
    that keeps this section from swamping the report must not fold rows away
    from them (D-130)."""
    cells = [_cell(i) for i in range(40)]
    md = stability.render_markdown(cells, "t1_ttft_ms", max_stable_rows=None)
    assert md.count("point_id=P") == 40
    assert "另有" not in md


def test_no_cap_note_when_under_the_limit():
    md = stability.render_markdown([_cell(i) for i in range(3)], "t1_ttft_ms")
    assert "另有" not in md


def test_cv_mean_zero_is_none():
    assert stability.cv_percent([2, -2]) is None      # mean 0 -> undefined, not 0


def test_stable_vs_unstable_flag():
    stable = kpi_scenario_records(5, kpi={"t1_ttft_ms": 100})          # identical -> CV 0
    cells = stability.stability_cells(stable, "t1_ttft_ms", cv_gate=10.0)
    assert cells[0]["cv_percent"] == 0.0
    assert cells[0]["unstable"] is False
    # spread values 80,120,80,120,100 -> mean 100, CV ~19% > 10
    recs = (kpi_scenario_records(1, kpi={"t1_ttft_ms": 80})
            + kpi_scenario_records(1, kpi={"t1_ttft_ms": 120})
            + kpi_scenario_records(1, kpi={"t1_ttft_ms": 80})
            + kpi_scenario_records(1, kpi={"t1_ttft_ms": 120})
            + kpi_scenario_records(1, kpi={"t1_ttft_ms": 100}))
    c = stability.stability_cells(recs, "t1_ttft_ms", cv_gate=10.0)[0]
    assert c["cv_percent"] > 10.0
    assert c["unstable"] is True


def test_low_confidence_flag():
    recs = kpi_scenario_records(2, kpi={"t1_ttft_ms": 100})  # n=2 < 5
    c = stability.stability_cells(recs, "t1_ttft_ms")[0]
    assert c["low_confidence"] is True


def _campaign_kpis(values, campaign_id):
    return [r for v in values
            for r in kpi_scenario_records(1, kpi={"t1_ttft_ms": v}, campaign_id=campaign_id)]


def test_campaigns_are_not_pooled_into_repeatability():
    """Two campaigns are two conditions. Pooling them makes CV measure the
    optimisation instead of the measurement — and the runbook then sends the
    operator back to resample a cell that was fine (D-145)."""
    recs = (_campaign_kpis([398, 400, 402, 399, 401], "base")
            + _campaign_kpis([598, 600, 602, 599, 601], "opt"))
    cells = stability.stability_cells(recs, "t1_ttft_ms")
    assert len(cells) == 2
    by = {c["cell"]["campaign_id"]: c for c in cells}
    assert by["base"]["median"] == 400 and by["opt"]["median"] == 600
    for c in cells:
        assert c["n"] == 5
        assert c["cv_percent"] < 1.0
        assert c["unstable"] is False


def test_stability_csv_distinguishes_campaigns():
    """CSV is where analysts compute, and it has no banners: without campaign_id
    the two campaigns emit rows identical in every other column (D-141/145)."""
    import csv as csvmod
    import tempfile
    from synth import contractify
    recs = [contractify(r) for r in
            (_campaign_kpis([398, 400, 402, 399, 401], "base")
             + _campaign_kpis([598, 600, 602, 599, 601], "opt"))]
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "camp")
        rpt.write_csv_tables(recs, prefix)
        with open(prefix + "_stability.csv", encoding="utf-8-sig") as f:
            rows = [r for r in csvmod.DictReader(f) if r["kpi"] == "t1_ttft_ms"]
    assert {r["campaign_id"] for r in rows} == {"base", "opt"}
    assert {float(r["median"]) for r in rows} == {400.0, 600.0}
    assert all(int(r["n"]) == 5 for r in rows)


def test_required_n_and_detectable_effect_are_consistent():
    """The n the planner asks for must actually bring the resolvable difference
    down to the target — otherwise the advice is decorative."""
    import campaign_common as cc
    sd, target = 50.0, 10.0
    n = cc.required_n(sd, target)
    assert cc.min_detectable_effect(sd, n) <= target
    assert cc.min_detectable_effect(sd, n - 1) > target      # and not more than needed
    # tighter targets cost more samples, quadratically
    assert cc.required_n(sd, target / 2) >= 4 * n - 2


def test_plan_leaves_unknown_spread_unknown():
    """n=1: spread unknown, so neither what it resolves nor what it would take
    can be stated — None all the way through, never 0 and never the current n."""
    import campaign_common as cc
    assert cc.min_detectable_effect(None, 5) is None
    assert cc.required_n(None, 10) is None
    assert cc.required_n(5.0, 0) is None                     # non-positive target
    rows = stability.plan_cells(stability.stability_cells(
        kpi_scenario_records(1, kpi={"t1_ttft_ms": 100}), "t1_ttft_ms"))
    assert rows[0]["mde"] is None
    assert rows[0]["required_n"] is None
    assert rows[0]["resolves_target"] is None
    md = stability.render_plan_markdown(rows, "t1_ttft_ms")
    assert "无法核算采样量" in md


def test_plan_flags_cells_that_cannot_resolve_the_target():
    recs = _campaign_kpis([100, 130, 70, 115, 85], "base")   # CV ~24%, n=5
    rows = stability.plan_cells(stability.stability_cells(recs, "t1_ttft_ms"), 5.0)
    assert rows[0]["resolves_target"] is False
    assert rows[0]["required_n"] > 5
    md = stability.render_plan_markdown(rows, "t1_ttft_ms", 5.0)
    assert "1/1 个单元在当前 n 下分辨不了" in md
    assert "不是显著性检验" in md                            # the caveat travels with it


def test_report_includes_stability_section():
    recs = kpi_scenario_records(5, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "excellent"}, aqs=90)
    md = rpt.build_report_markdown(recs)
    assert "复测稳定性" in md
