# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/order_effect.py.

Pins the diagnostic's core claim: a NULL result (no suspected effect) must mean
"counterbalancing worked", never "we couldn't tell". Every un-decidable case is
required to report itself as un-decidable instead.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import order_effect as oe
from synth import order_records, make_record


def test_no_order_effect_when_positions_agree():
    """Same KPI at both positions -> counterbalancing worked (the good null)."""
    recs = (order_records(5, value=100, order_index=0)
            + order_records(5, value=100, order_index=1))
    p = oe.analyze(recs)["profiles"][0]
    assert p["spread"] == 0
    assert p["spread_pct"] == 0
    assert p["order_effect_suspected"] is False
    assert p["low_confidence"] is False


def test_order_effect_detected_when_position_matters():
    """1st position 100ms, 2nd 140ms -> spread well over the 10% threshold."""
    recs = (order_records(5, value=100, order_index=0)
            + order_records(5, value=140, order_index=1))
    p = oe.analyze(recs)["profiles"][0]
    assert p["spread"] == 40
    assert round(p["spread_pct"], 1) == 33.3      # 40 / median(120) * 100
    assert p["order_effect_suspected"] is True


def test_threshold_is_configurable():
    recs = (order_records(5, value=100, order_index=0)
            + order_records(5, value=112, order_index=1))
    assert oe.analyze(recs, threshold_pct=5)["profiles"][0]["order_effect_suspected"] is True
    assert oe.analyze(recs, threshold_pct=50)["profiles"][0]["order_effect_suspected"] is False


def test_single_position_not_computable_not_no_effect():
    """One position can never prove absence of an order effect."""
    p = oe.analyze(order_records(5, value=100, order_index=0))["profiles"][0]
    assert p["order_effect_suspected"] is None          # NOT False
    assert p["not_computable_reason"] == "NEED_2_POSITIONS"
    assert p["low_confidence"] is True


def test_low_confidence_below_sample_floor():
    recs = (order_records(2, value=100, order_index=0)
            + order_records(2, value=100, order_index=1))
    p = oe.analyze(recs)["profiles"][0]
    assert p["low_confidence"] is True
    assert p["order_effect_suspected"] is False        # still computable


def test_near_zero_median_makes_pct_undefined_not_infinite():
    recs = (order_records(5, value=0, order_index=0)
            + order_records(5, value=0, order_index=1))
    p = oe.analyze(recs)["profiles"][0]
    assert p["spread_pct"] is None
    assert p["order_effect_suspected"] is None
    assert p["not_computable_reason"] == "MEDIAN_NEAR_ZERO"


def test_rotation_warning_when_order_never_rotated():
    """Same scenario_order everywhere = the Latin square was never rotated."""
    recs = (order_records(5, value=100, order_index=0, scenario_order="s1,s2")
            + order_records(5, value=100, order_index=1, scenario_order="s1,s2"))
    res = oe.analyze(recs)
    assert res["distinct_orders"] == 1
    assert res["rotation_warning"] is True
    assert "未轮转" in oe.render_markdown(res)


def test_no_rotation_warning_when_rotated():
    recs = (order_records(5, value=100, order_index=0, scenario_order="s1,s2")
            + order_records(5, value=100, order_index=1, scenario_order="s2,s1"))
    res = oe.analyze(recs)
    assert res["distinct_orders"] == 2
    assert res["rotation_warning"] is False


def test_absent_order_evidence_reported():
    recs = [make_record(scenarios=[("s1_chat", {"t1_ttft_ms": 100})]) for _ in range(3)]
    res = oe.analyze(recs)
    assert res["no_order_evidence"] is True
    assert "无 `run.scenario_order` 证据" in oe.render_markdown(res)


def test_per_profile_separation():
    """Two profiles must be judged independently, not pooled."""
    recs = (order_records(5, value=100, order_index=0, profile="s1_chat")
            + order_records(5, value=100, order_index=1, profile="s1_chat")
            + order_records(5, value=100, order_index=0, profile="s2_rag")
            + order_records(5, value=200, order_index=1, profile="s2_rag"))
    by = {p["profile_id"]: p for p in oe.analyze(recs)["profiles"]}
    assert by["s1_chat"]["order_effect_suspected"] is False
    assert by["s2_rag"]["order_effect_suspected"] is True


def test_markdown_renders():
    recs = (order_records(5, value=100, order_index=0)
            + order_records(5, value=140, order_index=1))
    md = oe.render_markdown(oe.analyze(recs))
    assert "序位效应诊断" in md
    assert "疑似序位偏倚" in md
