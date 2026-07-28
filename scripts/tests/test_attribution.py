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
import campaign_common as cc
from synth import tier_records, make_record


def test_impossible_value_does_not_manufacture_backbone_latency():
    """A negative metro median does not merely lower one number: the differential
    turns it into 540ms of "regional backbone" that never existed — this report's
    headline claim, and it would send a team to a segment that is fine. Nothing
    checked value ranges and no flag fired (D-178)."""
    K = "n1_rtt_p50_ms"
    recs = (tier_records("metro", K, -500, 5) + tier_records("regional", K, 40, 5)
            + tier_records("core", K, 80, 5))
    c = attribution.attribute(recs)["cells"][0]
    # the invented increment is gone, and its absence is stated rather than guessed
    assert c["access_component"] is None
    assert c["regional_backbone_incr"] is None
    assert c["core_backbone_incr"] == 40        # this half was never contaminated
    assert c["implausible_values"] == {"n1_rtt_p50_ms<0": 5}
    flags = attribution.incomparability_flags(c)
    assert "IMPLAUSIBLE_VALUE:n1_rtt_p50_ms<0×5" in flags
    assert "TIER_MISSING:metro" in flags        # says WHICH tier went missing, too
    # severe: a producer that wrote an impossible value is not trustworthy for
    # the values it wrote alongside it
    assert "IMPLAUSIBLE_VALUE" in attribution.SEVERE_FLAGS


# One cell shape per severe flag: the minimum that PRODUCES it. Asserting
# is_severe(x) for x in SEVERE_FLAGS would be a tautology — the first version of
# this test was exactly that, and passed while proving nothing.
_PRODUCES_SEVERE = {
    "TIER_TIME_SPREAD": {"tier_time_confound": True, "tier_time_spread_ms": 7200_000},
    "MIXED_TRANSPORT": {"mixed_transports": ["cellular", "wifi"]},
    "TIER_ENDPOINT_CONFLICT": {"tier_endpoint_conflicts": {"https://m": ["core", "metro"]}},
    "IMPLAUSIBLE_VALUE": {"implausible_values": {"n1_rtt_p50_ms<0": 3}},
    "VETO_CAPPED": {"veto_n": 2, "n": 5},
    "TIER_INCOMPLETE": {"missing_tiers": ["core"]},
}


def test_every_severe_flag_is_producible_and_emphasised():
    """SEVERE_FLAGS promises "renderers that can emphasise, should emphasise
    these", and that promise was kept by three separate copies of one expression
    with nothing checking the RULE. A seventh entry would have emphasised nothing
    and no test would have noticed. This also answers the D-183 question of the
    table: can each declared flag actually be produced at all? (D-184)"""
    assert set(_PRODUCES_SEVERE) == set(attribution.SEVERE_FLAGS), \
        "a severe flag with no cell shape producing it is a declaration, not a marker"
    for flag, cell in _PRODUCES_SEVERE.items():
        rendered = attribution.md_flags(cell)
        hit = [f for f in rendered if f.strip("*").startswith(flag)]
        assert hit, f"{flag} is declared severe but no cell produced it: {rendered}"
        assert all(f.startswith("**") and f.endswith("**") for f in hit), (flag, hit)
    # …and an ordinary marker must NOT be emphasised
    plain = attribution.md_flags({"mixed_profile_versions": ["0.1", "0.2"],
                                  "low_confidence": True})
    assert plain and not any(f.startswith("**") for f in plain), plain

    # …and the emphasis survives onto the pages. Everything above is md_flags on
    # a synthetic dict — a pure function, not a deliverable. The promise names
    # renderers, so a renderer that stopped emphasising would have gone unseen
    # (the shape D-232 named, applied here). Measured: markdown carries it as
    # ** ** and the HTML as <b>, so this costs nothing to pin (D-261).
    import re
    import campaign_report as rpt
    from test_campaign_report import _every_marker_corpus
    recs = _every_marker_corpus()
    md = rpt.build_report_markdown(recs)
    html = rpt.build_report_html(recs, "2026-01-01 00:00:00")
    # Which flags this corpus PRODUCES, not which names appear in the page: the
    # section's own method paragraph names TIER_ENDPOINT_CONFLICT in prose, and
    # a substring test read that as a marker on a row. Same substitute-criterion
    # mistake this file keeps catching — caught here before the commit.
    produced = {f.split(":")[0]
                for c in attribution.attribute(recs)["cells"]
                for f in attribution.incomparability_flags(c)}
    on_page = sorted(produced & set(attribution.SEVERE_FLAGS))
    assert len(on_page) >= 2, ("this corpus produces too few severe flags to "
                               f"prove anything: {on_page}")
    for flag in on_page:
        assert re.search(r"\*\*" + re.escape(flag) + r"[^*]*\*\*", md), (
            f"{flag} reaches the markdown unemphasised")
        assert re.search(r"<b>[^<]*" + re.escape(flag), html), (
            f"{flag} reaches the HTML unemphasised")


def test_severe_and_ordinary_markers_render_differently():
    """The rule end-to-end on one real cell: severe bolded, ordinary plain."""
    K = "n1_rtt_p50_ms"
    recs = (tier_records("metro", K, -5, 5)          # IMPLAUSIBLE_VALUE: severe
            + tier_records("regional", K, 40, 2))     # low_conf: ordinary
    c = attribution.attribute(recs)["cells"][0]
    rendered = attribution.md_flags(c)
    bolded = [f for f in rendered if f.startswith("**")]
    plain = [f for f in rendered if not f.startswith("**")]
    assert any("IMPLAUSIBLE_VALUE" in f for f in bolded)
    assert any("low_conf" in f for f in plain)
    # every bolded one is severe and every plain one is not — the rule, not a case
    assert all(attribution.is_severe(f.strip("*")) for f in bolded)
    assert all(not attribution.is_severe(f) for f in plain)


def test_a_cell_of_only_impossible_values_still_gets_a_row():
    """With every sample dropped the cell has no tier data left, so it would
    vanish from the matrix without a word — the one outcome R-10 forbids."""
    recs = tier_records("metro", "n1_rtt_p50_ms", -1, 5)
    cells = attribution.attribute(recs)["cells"]
    assert len(cells) == 1
    assert "IMPLAUSIBLE_VALUE:n1_rtt_p50_ms<0×5" in attribution.incomparability_flags(cells[0])


def test_range_guard_does_not_cry_wolf_on_bad_networks():
    """The one place this project must not over-flag: a genuinely awful network
    is the finding, not an error. Only impossible values are caught."""
    assert cc.value_problem("n1_rtt_p50_ms", 8000) is None       # 8s RTT: real, terrible
    assert cc.value_problem("t1_ttft_ms", 120000) is None        # 2min TTFT: real
    assert cc.value_problem("u1_goodput_mbps", 0) is None        # zero throughput: real
    assert cc.value_problem("t4_severe_stall_rate", 1.0) is None  # 100% stalls: real
    assert cc.value_problem("n1_rtt_p50_ms", -0.1) == "<0"       # impossible
    assert cc.value_problem("t4_severe_stall_rate", 1.5) == ">1"  # not a fraction
    assert cc.value_problem("aqs_score", 100) is None
    assert cc.value_problem("aqs_score", 100.5) == ">100"
    assert cc.value_problem("unknown_field", -999) is None       # no declared range


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
    # ⚠ SOLE targeted guard on the WORDING half of handover §2.10 (D-186's
    #   mutation map); the report snapshot also fires, but a snapshot approves
    #   whatever --update is run against. D-187 guards the summary bullet and
    #   the dispersion column, which are different halves of the same principle.
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


def test_dispersion_column_is_present_and_populated():
    """§2.10's other half: the caveat tells the reader to judge uniformity from
    the 离差/典型 column, so that column has to exist and carry a number. The
    mutation audit found this half held only by the report snapshot and a
    column-count check, either of which a wording edit could sail past (D-187)."""
    recs = []
    for i, core in enumerate((50, 70, 90, 60, 80, 70)):   # wide but no outlier
        recs += _point(f"P{i:02d}", 30, 42, core)
    md = attribution.render_segment_profile_markdown(
        attribution.segment_profile(attribution.attribute(recs)))
    header = [ln for ln in md.splitlines() if ln.startswith("| 段 ")][0]
    cols = [c.strip() for c in header.split("|")]
    assert "离差/典型" in cols, header          # by NAME, not by position or count
    idx = cols.index("离差/典型")
    rows = [ln for ln in md.splitlines()
            if ln.startswith("| ") and "---" not in ln and not ln.startswith("| 段 ")]
    assert rows, "corpus must produce segment rows"
    vals = {ln.split("|")[1].strip(): ln.split("|")[idx].strip() for ln in rows}
    assert any(v not in ("—", "") for v in vals.values()), vals  # computable => a number
    # …and it must be the number the caveat points at: these cells are visibly
    # not alike, so the column has to say so even though no cell crossed the screen
    seg = _segs(recs)["core_backbone_incr"]
    assert seg["uniform"] is True and seg["rel_mad"] > 10
    core_cell = [v for k, v in vals.items() if "核心" in k or "core" in k][0]
    assert float(core_cell.rstrip("%")) == round(seg["rel_mad"], 1)


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
    # ...and the VERDICT reaches both, not just the heading. The CSV half of this
    # test has always checked content — which cell is the outlier, whether the
    # segment is uniform — while the two rendered surfaces were evidenced by a
    # section title. Empty the section's rows, keep the heading, and this used to
    # pass on the two surfaces a reader actually looks at (D-260). Scoped to the
    # section, because P99 appears in the heat card too.
    seg_md = md.split("## 分段异常定位")[1].split("\n## ")[0]
    seg_html = html.split("分段异常定位")[1].split("<h2>")[0]
    assert "P99" in seg_md, "the outlier point never reaches the markdown section"
    assert "P99" in seg_html, "the outlier point never reaches the HTML section"
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


def _ep_tier(tier_name, val, endpoint, n=5):
    campaign = {"campaign_id": "base", "tier": tier_name, "point_id": "P1",
                "carrier": "cmcc", "time_band": "busy",
                "server_tier_endpoint": endpoint}
    return [make_record(campaign=campaign,
                        scenarios=[("s1_chat", {"n1_rtt_p50_ms": val})])
            for _ in range(n)]


METRO_EP = "https://metro.example:8443"


def test_three_tiers_hitting_one_endpoint_is_flagged():
    """The tier label is what the operator typed; server_tier_endpoint is what
    the run actually hit. The field was written by annotate and read by nobody,
    so a corpus whose three tiers all hit the metro mirror produced a full
    backbone decomposition (regional +20, core +40) with an empty note and a
    green publish gate (D-167)."""
    recs = (_ep_tier("metro", 30, METRO_EP) + _ep_tier("regional", 50, METRO_EP)
            + _ep_tier("core", 90, METRO_EP))
    c = attribution.attribute(recs)["cells"][0]
    assert c["core_backbone_incr"] == 40        # still reported, never suppressed
    conflicts = c["tier_endpoint_conflicts"]
    assert list(conflicts) == [METRO_EP]
    assert conflicts[METRO_EP] == ["core", "metro", "regional"]
    flags = attribution.incomparability_flags(c)
    assert any(f.startswith("TIER_ENDPOINT_CONFLICT:") for f in flags)
    md = attribution.render_markdown(attribution.attribute(recs))
    assert "TIER_ENDPOINT_CONFLICT" in md
    assert "层级名副其实" in md                  # the premise checklist item


def test_distinct_endpoints_are_not_flagged():
    recs = (_ep_tier("metro", 30, METRO_EP)
            + _ep_tier("regional", 50, "https://regional.example:8443")
            + _ep_tier("core", 90, "https://core.example:8443"))
    c = attribution.attribute(recs)["cells"][0]
    assert c["tier_endpoint_conflicts"] == {}
    assert c["tier_endpoints_known"] is True
    assert attribution.incomparability_flags(c) == []


def test_absent_endpoint_is_unknown_not_reconciled():
    """No field means the reconciliation could not run — not that it passed."""
    recs = (tier_records("metro", "n1_rtt_p50_ms", 30, 5)
            + tier_records("core", "n1_rtt_p50_ms", 90, 5))
    c = attribution.attribute(recs)["cells"][0]
    assert c["tier_endpoints_known"] is False
    assert c["tier_endpoint_conflicts"] == {}


# ---------------------------------------------------- outlier screen calibration

def _clean_grid_false_alarm(n_cells, k, trials=4000, skewed=False, seed=4242):
    """Fraction of CLEAN grids (one distribution, no real outlier present) that
    the screen flags. Same construction as the offline calibration, fixed seed."""
    import math
    import random
    rng = random.Random(seed + n_cells)
    hits = 0
    for _ in range(trials):
        if skewed:
            vals = [math.exp(rng.gauss(math.log(100), 0.45)) for _ in range(n_cells)]
        else:
            vals = [rng.gauss(100, 15) for _ in range(n_cells)]
        med, mad = cc.median(vals), cc.mad(vals)
        if not mad:
            continue
        if any(abs(v - med) > k * cc.MAD_TO_SIGMA * mad for v in vals):
            hits += 1
    return hits / float(trials)


def test_outlier_screen_meets_the_false_alarm_rate_it_publishes():
    """The section prints specific false-alarm percentages. Re-measure them.

    A constant retuned without re-measuring turns the printed caliber into a
    false statement — the exact shape this layer keeps finding (D-197/198/199),
    so the CLAIM is pinned here, not just the constant.
    """
    # every bucket boundary and both parities inside them — the first cut of the
    # table sampled every OTHER n and shipped a figure that was wrong for n=5 by
    # nearly double, because an odd sample's median is a data point and MAD
    # behaves differently
    for n in (4, 5, 6, 7, 8, 9, 10, 11, 12, 20, 32):
        k = attribution.outlier_k(n)
        sym, skew = attribution.outlier_false_alarm(n)
        got_sym = _clean_grid_false_alarm(n, k)
        got_skew = _clean_grid_false_alarm(n, k, skewed=True)
        # the published figure is the WORST n in its bucket, so it must never
        # understate; 4k trials give ~1pt of sampling error
        assert got_sym <= sym + 0.015, ("understated sym", n, k, sym, got_sym)
        assert got_skew <= skew + 0.015, ("understated skew", n, k, skew, got_skew)
        # …and not be so conservative that it stops describing anything
        assert sym - got_sym < 0.05, ("wildly overstated sym", n, k, sym, got_sym)
        # the symmetric case is what K is calibrated against, so it must hold
        assert got_sym <= attribution.OUTLIER_TARGET_FALSE_ALARM + 0.015, (n, got_sym)


def test_the_old_flat_threshold_really_was_crying_wolf():
    """Pins WHY the calibration exists: a flat 3 sigma fires on a clean 32-cell
    latency grid most of the time. Reverting to a flat threshold now fails with
    the price stated, instead of leaving it to memory."""
    flat = _clean_grid_false_alarm(32, 3.0, skewed=True)
    assert flat > 0.5, flat
    tuned = _clean_grid_false_alarm(32, attribution.outlier_k(32), skewed=True)
    assert tuned < flat / 1.5, (flat, tuned)


def test_every_screen_verdict_carries_its_caliber():
    """A flag with no false-alarm rate beside it reads as proof (D-200)."""
    recs = []
    for i, core in enumerate((50, 70, 90, 60, 80, 70, 65, 75)):
        for tier, val in (("metro", 30), ("regional", 42), ("core", core)):
            recs += tier_records(tier, "n1_rtt_p50_ms", val, 5, point="P%02d" % i)
    md = attribution.render_segment_profile_markdown(
        attribution.segment_profile(attribution.attribute(recs)))
    assert "干净网格误报" in md
    assert "1.4826" in md
    assert "3σ 筛查" not in md          # the retired wording, gone from the section


def test_the_three_components_still_add_to_the_end_to_end_as_printed():
    """The row is a decomposition, so the reader will add it up.

    access + regional + core telescopes into the end-to-end median exactly,
    but each number used to be rounded on its own: 100.04 + 50.02 + 50.02
    printed as 100 + 50 + 50 beside a total of 200.1, and 36% of three-tier
    rows failed the addition the row invites (D-219).
    """
    import campaign_common as cc

    recs = []
    for tier, v in (("metro", 100.04), ("regional", 150.06), ("core", 200.08)):
        recs += tier_records(tier, "n1_rtt_p50_ms", v, 5, point="P1")
    res = attribution.attribute(recs)
    complete = [c for c in res["cells"] if c["end_to_end_core"] is not None]
    assert complete, "fixture produced no complete three-tier cell"
    c = complete[0]

    # The fixture must carry the hazard, or the assertion below costs nothing:
    # rounded independently at the default precision these do NOT add up.
    naive = [float(cc.fmt_num(v)) for v in (c["access_component"],
                                            c["regional_backbone_incr"],
                                            c["core_backbone_incr"])]
    assert abs(sum(naive) - float(cc.fmt_num(c["end_to_end_core"]))) > 1e-9, (
        "fixture no longer reproduces the independent-rounding drift — "
        "this test would pass on the broken renderer too")

    row = [ln for ln in attribution.render_markdown(res).splitlines()
           if ln.startswith("| point_id")][0]
    printed = [x.strip() for x in row.strip().strip("|").split("|")]
    access, regional, core, e2e = (float(printed[i]) for i in (2, 3, 4, 5))
    assert abs((access + regional + core) - e2e) < 1e-9, row
    assert "ROUNDING_UNRECONCILED" not in printed[6], row

    # And when no precision reconciles them, the helper says so rather than
    # printing an addition that does not work. These three parts sum to the
    # total exactly in float, yet every digit count leaves the row one unit
    # short.
    parts, total, ok = cc.fmt_parts_summing(
        (34.704659243637408, 144.42088596261448, 36.141875305059415),
        215.26742051131131)
    assert ok is False, (parts, total)
    assert cc.fmt_parts_summing((1.0, 2.0), None)[2] is None   # nothing to check
