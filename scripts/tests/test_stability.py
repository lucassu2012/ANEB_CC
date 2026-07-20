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
