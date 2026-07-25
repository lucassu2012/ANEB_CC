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


def test_homogeneous_cell_not_flagged():
    recs = (tier_records("metro", "n1_rtt_p50_ms", 20, 5, profile_version="0.2")
            + tier_records("regional", "n1_rtt_p50_ms", 35, 5, profile_version="0.2")
            + tier_records("core", "n1_rtt_p50_ms", 60, 5, profile_version="0.2"))
    c = attribution.attribute(recs)["cells"][0]
    assert c["mixed_profile_versions"] == []
    assert c["mixed_histogram_edges"] is False


def test_mixed_profile_version_flagged():
    """D-32: s1@0.2 and s1@0.3 are different measurements — pooling must be visible."""
    recs = (tier_records("metro", "n1_rtt_p50_ms", 20, 3, profile_version="0.2")
            + tier_records("metro", "n1_rtt_p50_ms", 20, 3, profile_version="0.3")
            + tier_records("core", "n1_rtt_p50_ms", 60, 5, profile_version="0.2"))
    c = attribution.attribute(recs)["cells"][0]
    assert c["mixed_profile_versions"] == ["0.2", "0.3"]
    assert "MIXED_PROFILE_VERSION" in attribution.render_markdown(
        attribution.attribute(recs))


def test_mixed_histogram_edges_flagged():
    """R-27: counts on different edges are not summable — flag, don't combine."""
    recs = (tier_records("metro", "n1_rtt_p50_ms", 20, 3, edges_ms=[10, 20, 50])
            + tier_records("metro", "n1_rtt_p50_ms", 20, 3, edges_ms=[10, 25, 50])
            + tier_records("core", "n1_rtt_p50_ms", 60, 5, edges_ms=[10, 20, 50]))
    c = attribution.attribute(recs)["cells"][0]
    assert c["mixed_histogram_edges"] is True


def test_mixed_mode_and_profile_source_flagged():
    """Survey gap 9: quick vs forensic (repeat rigor) and server vs assets_fallback
    (profile provenance) are non-comparable pools — flag, don't hide (D-113)."""
    recs = (tier_records("metro", "n1_rtt_p50_ms", 20, 3)
            + tier_records("metro", "n1_rtt_p50_ms", 20, 3)
            + tier_records("core", "n1_rtt_p50_ms", 60, 5))
    for r in recs[:3]:
        r["run"]["mode"] = "forensic"
        r["run"]["profile_source"] = "assets_fallback"
    c = attribution.attribute(recs)["cells"][0]
    assert c["mixed_modes"] == ["forensic", "quick"]
    assert c["mixed_profile_sources"] == ["assets_fallback", "server"]
    md = attribution.render_markdown(attribution.attribute(recs))
    # "/" not "|" — a pipe would split the markdown table cell (D-127)
    assert "MIXED_MODE:forensic/quick" in md
    assert "MIXED_PROFILE_SOURCE:assets_fallback/server" in md


def test_homogeneous_mode_not_flagged():
    recs = (tier_records("metro", "n1_rtt_p50_ms", 20, 5)
            + tier_records("core", "n1_rtt_p50_ms", 60, 5))
    c = attribution.attribute(recs)["cells"][0]
    assert c["mixed_modes"] == []
    assert c["mixed_profile_sources"] == []


def test_mixed_flag_does_not_suppress_the_numbers():
    """The guard REPORTS incomparability; it must not silently drop the cell."""
    recs = (tier_records("metro", "n1_rtt_p50_ms", 20, 3, profile_version="0.2")
            + tier_records("metro", "n1_rtt_p50_ms", 20, 3, profile_version="0.3")
            + tier_records("regional", "n1_rtt_p50_ms", 35, 5, profile_version="0.2")
            + tier_records("core", "n1_rtt_p50_ms", 60, 5, profile_version="0.2"))
    c = attribution.attribute(recs)["cells"][0]
    assert c["access_component"] == 20
    assert c["regional_backbone_incr"] == 15
    assert c["mixed_profile_versions"] == ["0.2", "0.3"]


def test_chinese_and_carrier_aliases_normalized():
    # 中文 tier + carrier 别名应规范化，与英文规范键落同一单元
    recs = (tier_records("同城", "n1_rtt_p50_ms", 20, 5, carrier="移动")
            + tier_records("core", "n1_rtt_p50_ms", 60, 5, carrier="cmcc"))
    res = attribution.attribute(recs)
    assert len(res["cells"]) == 1, res   # 同城->metro, 移动->cmcc collapse to one cell
    c = res["cells"][0]
    assert c["cell"]["carrier"] == "cmcc"
    assert c["access_component"] == 20


def _point(pid, metro, regional, core, n=5):
    """One point's three tiers with a known budget."""
    return (tier_records("metro", "n1_rtt_p50_ms", metro, n, point=pid)
            + tier_records("regional", "n1_rtt_p50_ms", regional, n, point=pid)
            + tier_records("core", "n1_rtt_p50_ms", core, n, point=pid))


def _segs(recs):
    prof = attribution.segment_profile(attribution.attribute(recs))
    return {s["segment"]: s for s in prof["segments"]}


def test_segment_profile_finds_the_one_odd_point():
    """The matrix shows each cell alone; the decision it feeds — fix this point
    or fix the backbone — needs the cells compared with each other (D-146)."""
    recs = []
    for i, core in enumerate((68, 70, 72, 69, 71, 70)):   # core incr = core - 42
        recs += _point(f"P{i:02d}", 30, 42, core)
    recs += _point("P99", 30, 42, 200)
    segs = _segs(recs)
    assert segs["access_component"]["uniform"] is True
    assert segs["regional_backbone_incr"]["uniform"] is True
    odd = segs["core_backbone_incr"]
    assert odd["uniform"] is False
    assert [o["cell"]["point_id"] for o in odd["high"]] == ["P99"]
    assert odd["low"] == []


def test_segment_profile_does_not_invent_an_outlier():
    """No anomaly must read as no anomaly — a screen that cries wolf gets
    ignored (D-134)."""
    recs = []
    for i, core in enumerate((68, 70, 72, 69, 71, 70)):
        recs += _point(f"P{i:02d}", 30, 42, core)
    segs = _segs(recs)
    assert all(s["uniform"] is True for s in segs.values())
    assert all(s["high"] == [] and s["low"] == [] for s in segs.values())


def test_zero_spread_still_reports_the_odd_cell():
    """Over half the cells identical drives MAD to 0 and the 3-sigma threshold
    to nothing — the cleanest signal there is must not be the one suppressed."""
    recs = []
    for i in range(6):
        recs += _point(f"P{i:02d}", 30, 42, 70)
    recs += _point("P99", 30, 42, 200)
    odd = _segs(recs)["core_backbone_incr"]
    assert odd["mad"] == 0
    assert odd["basis"] == "zero_spread"
    assert [o["cell"]["point_id"] for o in odd["high"]] == ["P99"]
    md = attribution.render_segment_profile_markdown(
        attribution.segment_profile(attribution.attribute(recs)))
    assert "不是 3σ" in md          # the weaker basis is stated, not hidden


def test_uniform_verdict_does_not_claim_the_cells_are_alike():
    """'No cell crossed the screen' is not 'the cells are the same'. The verdict
    must state the weaker true thing and expose the spread that carries the rest."""
    recs = []
    for i, core in enumerate((50, 70, 90, 60, 80, 70)):   # wide but no outlier
        recs += _point(f"P{i:02d}", 30, 42, core)
    seg = _segs(recs)["core_backbone_incr"]
    assert seg["uniform"] is True
    assert seg["rel_mad"] > 10                            # cells are NOT alike
    md = attribution.render_segment_profile_markdown(
        attribution.segment_profile(attribution.attribute(recs)))
    assert "未见单点异常" in md
    assert "不等于各单元相同" in md
    assert "各单元一致" not in md


def test_segment_profile_reaches_markdown_and_csv():
    import campaign_report as rpt
    import csv as csvmod
    import tempfile
    from synth import contractify
    recs = []
    for i in range(6):
        recs += _point(f"P{i:02d}", 30, 42, 70)
    recs += _point("P99", 30, 42, 200)
    recs = [contractify(r) for r in recs]
    md = rpt.build_report_markdown(recs)
    html = rpt.build_report_html(recs, "2026-01-01 00:00:00")
    assert "分段异常定位" in md and "分段异常定位" in html
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "camp")
        rpt.write_csv_tables(recs, prefix)
        with open(prefix + "_segment_profile.csv", encoding="utf-8-sig") as f:
            rows = [r for r in csvmod.DictReader(f)
                    if r["kpi"] == "n1_rtt_p50_ms" and r["segment"] == "core_backbone_incr"]
    assert len(rows) == 1
    assert "P99" in rows[0]["high_cells"]
    assert rows[0]["uniform"] == "False"


HOUR_MS = 3600_000


def _tier_at(tier, val, offset_ms, n=5, point="P1"):
    """One tier's repeats starting at a given offset, one per minute."""
    campaign = {"campaign_id": "base", "tier": tier, "point_id": point,
                "carrier": "cmcc", "time_band": "idle"}
    return [make_record(campaign=campaign,
                        scenarios=[("s1_chat", {"n1_rtt_p50_ms": val})],
                        started_ms=1783944000000 + offset_ms + i * 60000)
            for i in range(n)]


def test_tiers_measured_hours_apart_are_flagged():
    """铁律 3 cancels the common mode only if the tiers share conditions, and
    time_band is hours wide — metro at 03:00 and core at 20:00 are both "idle",
    so the core increment would be a diurnal effect in a backbone's clothes.
    Checkable from the timestamps, and never checked before (D-155)."""
    recs = (_tier_at("metro", 30, 0) + _tier_at("regional", 42, 10 * 60000)
            + _tier_at("core", 70, 8 * HOUR_MS))
    c = attribution.attribute(recs)["cells"][0]
    assert c["tier_time_confound"] is True
    assert abs(c["tier_time_spread_ms"] / HOUR_MS - 8) < 0.1
    md = attribution.render_markdown(attribution.attribute(recs))
    assert "TIER_TIME_SPREAD:8h" in md
    assert "时段差异" in md                      # the caveat says what goes wrong


def test_interleaved_tiers_are_not_flagged():
    """One cell measured back to back is ~18 min — must not cry wolf (D-134)."""
    recs = (_tier_at("metro", 30, 0) + _tier_at("regional", 42, 10 * 60000)
            + _tier_at("core", 70, 20 * 60000))
    c = attribution.attribute(recs)["cells"][0]
    assert c["tier_time_confound"] is False
    # the caveat mentions the marker too — match the form only a row carries
    assert "**TIER_TIME_SPREAD:" not in attribution.render_markdown(
        attribution.attribute(recs))


def test_missing_timestamps_are_unknown_not_fine():
    """No timestamps means the premise cannot be checked — which is not the
    same as the premise holding (R-10)."""
    recs = (tier_records("metro", "n1_rtt_p50_ms", 30, 5)
            + tier_records("core", "n1_rtt_p50_ms", 70, 5))
    for r in recs:
        r["run"].pop("started_at_epoch_ms", None)
    res = attribution.attribute(recs)
    c = res["cells"][0]
    assert c["tier_time_spread_ms"] is None
    assert c["tier_time_confound"] is None
    assert "TIER_TIME_UNKNOWN" in attribution.render_markdown(res)


def test_single_tier_cell_has_nothing_to_compare():
    recs = tier_records("metro", "n1_rtt_p50_ms", 30, 5)
    c = attribution.attribute(recs)["cells"][0]
    assert c["tier_time_spread_ms"] is None
    # …and the note is not emitted for a cell that could never have a spread
    assert "| TIER_TIME_UNKNOWN" not in attribution.render_markdown(
        attribution.attribute(recs))


def _tier_on(tier, val, transport, n=5):
    campaign = {"campaign_id": "base", "tier": tier, "point_id": "P1",
                "carrier": "cmcc", "time_band": "busy"}
    out = []
    for _ in range(n):
        r = make_record(campaign=campaign,
                        scenarios=[("s1_chat", {"n1_rtt_p50_ms": val})])
        r["run"]["transport"] = transport
        out.append(r)
    return out


def test_tiers_on_different_access_media_are_flagged():
    """铁律 3 also requires the same ACCESS. metro over venue wifi and core over
    the SIM makes the core increment a wifi-vs-cellular gap wearing a backbone
    label — and transport is right there in the record (D-157)."""
    recs = (_tier_on("metro", 20, "wifi") + _tier_on("regional", 35, "wifi")
            + _tier_on("core", 90, "auto(cellular)"))     # compound form, D-110
    c = attribution.attribute(recs)["cells"][0]
    assert c["mixed_transports"] == ["cellular", "wifi"]
    assert c["core_backbone_incr"] == 55                  # reported, not suppressed
    md = attribution.render_markdown(attribution.attribute(recs))
    assert "**MIXED_TRANSPORT:cellular/wifi**" in md
    assert "接入差" in md                                  # the caveat says what it is


def test_same_access_across_tiers_is_not_flagged():
    recs = (_tier_on("metro", 20, "wifi") + _tier_on("regional", 35, "wifi")
            + _tier_on("core", 90, "wifi"))
    c = attribution.attribute(recs)["cells"][0]
    assert c["mixed_transports"] == []
    assert "MIXED_TRANSPORT:" not in attribution.render_markdown(
        attribution.attribute(recs))
