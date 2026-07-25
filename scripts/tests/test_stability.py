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


def test_report_includes_stability_section():
    recs = kpi_scenario_records(5, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "excellent"}, aqs=90)
    md = rpt.build_report_markdown(recs)
    assert "复测稳定性" in md
