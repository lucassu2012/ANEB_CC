# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/campaign_report.py + campaign_common bands."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import campaign_common as cc
import campaign_report as rpt
from synth import aqs_records, make_record, kpi_scenario_records


def test_heatcard_cells_and_grades():
    recs = (aqs_records(91, 5, point="P1", time_band="busy")
            + aqs_records(60, 5, point="P1", time_band="idle"))
    cells = rpt.heat_cells(recs)
    by = {(c["cell"]["point_id"], c["cell"]["time_band"]): c for c in cells}
    assert by[("P1", "busy")]["aqs_median"] == 91
    assert by[("P1", "busy")]["grade"] == "excellent"
    assert by[("P1", "busy")]["n"] == 5
    assert by[("P1", "busy")]["low_confidence"] is False
    assert by[("P1", "idle")]["grade"] == "fair"


def test_low_confidence_cell():
    cells = rpt.heat_cells(aqs_records(80, 2, point="P2"))  # n=2 < 5
    assert cells[0]["low_confidence"] is True


def test_before_after_delta():
    recs = (aqs_records(70, 5, point="P1", time_band="busy", campaign_id="base")
            + aqs_records(85, 5, point="P1", time_band="busy", campaign_id="opt"))
    cmp = rpt.compare_campaigns(recs, "base", "opt")
    assert len(cmp["rows"]) == 1
    r = cmp["rows"][0]
    assert r["before"] == 70
    assert r["after"] == 85
    assert r["delta"] == 15


def test_before_after_only_one_side():
    recs = aqs_records(70, 5, point="P1", campaign_id="base")  # no 'opt' side
    cmp = rpt.compare_campaigns(recs, "base", "opt")
    r = cmp["rows"][0]
    assert r["before"] == 70
    assert r["after"] is None
    assert r["delta"] is None          # not fabricated
    assert r["low_confidence"] is True  # one side missing -> flagged


def test_graceful_without_labels():
    recs = [make_record(aqs=88, scenarios=[]) for _ in range(3)]  # no campaign block
    inv = rpt.inventory(recs)
    assert inv["with_campaign"] == 0
    cells = rpt.heat_cells(recs)
    assert len(cells) == 1
    assert cells[0]["cell"] == {"point_id": "unlabeled", "carrier": "unknown",
                                "time_band": "unknown"}


def test_aqs_grade_band_boundaries():
    assert cc.aqs_grade(85) == "excellent"
    assert cc.aqs_grade(84.999) == "good"
    assert cc.aqs_grade(70) == "good"
    assert cc.aqs_grade(69.999) == "fair"
    assert cc.aqs_grade(54) == "fair"
    assert cc.aqs_grade(53.999) == "poor"
    assert cc.aqs_grade(None) == "n/a"


def test_percentile_nearest_rank():
    assert cc.percentile([1, 2, 3, 4, 5], 50) == 3
    assert cc.percentile([1, 2, 3, 4, 5], 90) == 5
    assert cc.percentile([], 50) is None


def test_full_report_builds_and_marks_claim_scope():
    recs = aqs_records(91, 5)
    md = rpt.build_report_markdown(recs)
    assert "application_end_to_end_to_probe_node" in md
    assert "热力卡" in md
    html_out = rpt.build_report_html(recs, "2026-01-01 00:00:00")
    assert "<!DOCTYPE html>" in html_out
    assert "战役级综合报告" in html_out


def test_report_flags_unlabeled_corpus():
    recs = [make_record(aqs=88, scenarios=[]) for _ in range(3)]
    md = rpt.build_report_markdown(recs)
    assert "无 `run.campaign` 标签" in md  # honest coverage warning


def test_kpi_grade_field_mapping():
    assert rpt.kpi_grade_field("n1_rtt_p50_ms") == "n1_grade"
    assert rpt.kpi_grade_field("t1_ttft_ms") == "t1_grade"
    assert rpt.kpi_grade_field("u1_goodput_mbps") == "u1_grade"


def test_kpi_heatcard_median_and_authoritative_grade():
    recs = kpi_scenario_records(5, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "excellent"})
    cells = rpt.kpi_heat_cells(recs, "n1_rtt_p50_ms")
    assert len(cells) == 1
    c = cells[0]
    assert c["median"] == 20
    assert c["grade"] == "excellent"   # from the record's n1_grade, not AQS bands
    assert c["n"] == 5
    assert c["low_confidence"] is False


def test_kpi_heat_modal_grade_majority():
    recs = (kpi_scenario_records(3, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "excellent"})
            + kpi_scenario_records(2, kpi={"n1_rtt_p50_ms": 90, "n1_grade": "poor"}))
    c = rpt.kpi_heat_cells(recs, "n1_rtt_p50_ms")[0]
    assert c["grade"] == "excellent"   # 3 > 2 modal
    assert c["n"] == 5


def test_report_includes_per_kpi_sections():
    recs = kpi_scenario_records(5, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "excellent"}, aqs=90)
    md = rpt.build_report_markdown(recs)
    assert "分 KPI 热力卡" in md
    assert "n1_rtt_p50_ms" in md
