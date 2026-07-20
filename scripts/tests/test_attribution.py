# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/attribution.py (three-tier differential).

Each test encodes a methodology invariant so a future refactor that weakens it
fails loudly. Synthetic fixtures with a KNOWN latency budget → attribution must
recover each segment; honest degradation and inversion handling are pinned.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import attribution
from synth import tier_records, make_record


def test_known_budget_recovered():
    # access=20, +regional 15 -> 35, +core 25 -> 60
    recs = (tier_records("metro", "n1_rtt_p50_ms", 20, 5)
            + tier_records("regional", "n1_rtt_p50_ms", 35, 5)
            + tier_records("core", "n1_rtt_p50_ms", 60, 5))
    res = attribution.attribute(recs)
    assert len(res["cells"]) == 1, res
    c = res["cells"][0]
    assert c["access_component"] == 20
    assert c["regional_backbone_incr"] == 15
    assert c["core_backbone_incr"] == 25
    assert c["end_to_end_core"] == 60
    assert c["coverage"] == ["metro", "regional", "core"]
    assert c["low_confidence"] is False
    assert c["inversions"] == []
    assert c["not_computable_reason"] is None
    assert res["excluded_no_tier"] == 0


def test_telescoping_identity():
    recs = (tier_records("metro", "n1_rtt_p50_ms", 12, 5)
            + tier_records("regional", "n1_rtt_p50_ms", 31, 5)
            + tier_records("core", "n1_rtt_p50_ms", 77, 5))
    c = attribution.attribute(recs)["cells"][0]
    total = c["access_component"] + c["regional_backbone_incr"] + c["core_backbone_incr"]
    assert abs(total - c["end_to_end_core"]) < 1e-9


def test_missing_tier_degrades_honestly():
    recs = (tier_records("metro", "n1_rtt_p50_ms", 20, 5)
            + tier_records("core", "n1_rtt_p50_ms", 60, 5))  # no regional
    c = attribution.attribute(recs)["cells"][0]
    assert c["access_component"] == 20
    assert c["regional_backbone_incr"] is None   # needs regional
    assert c["core_backbone_incr"] is None        # core-regional undefined w/o regional
    assert c["end_to_end_core"] == 60
    assert "regional" in c["not_computable_reason"]
    assert c["coverage"] == ["metro", "core"]


def test_inversion_reported_not_clamped():
    # regional FASTER than metro (routing/anycast) -> negative increment kept
    recs = (tier_records("metro", "n1_rtt_p50_ms", 30, 5)
            + tier_records("regional", "n1_rtt_p50_ms", 20, 5)
            + tier_records("core", "n1_rtt_p50_ms", 50, 5))
    c = attribution.attribute(recs)["cells"][0]
    assert c["regional_backbone_incr"] == -10     # NOT clamped to 0
    assert "regional<metro" in c["inversions"]
    assert c["core_backbone_incr"] == 30


def test_low_confidence_below_floor():
    recs = (tier_records("metro", "n1_rtt_p50_ms", 20, 3)
            + tier_records("regional", "n1_rtt_p50_ms", 35, 3)
            + tier_records("core", "n1_rtt_p50_ms", 60, 3))  # n=3 < min_samples 5
    c = attribution.attribute(recs)["cells"][0]
    assert c["low_confidence"] is True


def test_no_tier_labels_excluded():
    recs = [make_record(campaign={"campaign_id": "x", "point_id": "P1"},
                        scenarios=[("s1_chat", {"n1_rtt_p50_ms": 20})]) for _ in range(4)]
    res = attribution.attribute(recs)
    assert res["cells"] == []
    assert res["excluded_no_tier"] == 4


def test_ttft_kpi_selectable():
    recs = (tier_records("metro", "t1_ttft_ms", 100, 5)
            + tier_records("regional", "t1_ttft_ms", 140, 5)
            + tier_records("core", "t1_ttft_ms", 180, 5))
    c = attribution.attribute(recs, kpi="t1_ttft_ms")["cells"][0]
    assert c["access_component"] == 100
    assert c["regional_backbone_incr"] == 40
    assert c["core_backbone_incr"] == 40


def test_chinese_and_carrier_aliases_normalized():
    # 中文 tier + carrier 别名应规范化，与英文规范键落同一单元
    recs = (tier_records("同城", "n1_rtt_p50_ms", 20, 5, carrier="移动")
            + tier_records("core", "n1_rtt_p50_ms", 60, 5, carrier="cmcc"))
    res = attribution.attribute(recs)
    assert len(res["cells"]) == 1, res   # 同城->metro, 移动->cmcc collapse to one cell
    c = res["cells"][0]
    assert c["cell"]["carrier"] == "cmcc"
    assert c["access_component"] == 20
