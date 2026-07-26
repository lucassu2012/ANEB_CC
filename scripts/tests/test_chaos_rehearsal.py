# -*- coding: utf-8 -*-
"""Chaos rehearsal: the analysis layer must degrade HONESTLY on messy field data.

The clean synthetic corpus rehearses the happy path. Real field data arrives with
a tier never reached, a point measured on one carrier, runs aborted mid-way,
profile versions mixed into one cell, a clock that jumped, one absurd outlier, a
cell where everything failed, and records nobody labelled.

For each of those there is a specific thing the layer is supposed to DO — and a
specific thing it must never do: crash, or invent a number where there is no
measurement. These pin both (D-125).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import campaign_report as rpt
import publish_check as pc
import synth_campaign as sc
import validate_results as vr

_CORPUS = []


def _chaos():
    """Full-grid corpus with every pathology seeded (built once, reused)."""
    if not _CORPUS:
        _CORPUS.append(sc.inject_chaos(
            sc.generate(points=6, repeats=4, campaigns=("base",)), seed=7))
    return _CORPUS[0]


_MD = []


def _md():
    if not _MD:
        _MD.append(rpt.build_report_markdown(_chaos()))
    return _MD[0]


def _section(md, title_startswith):
    for chunk in re.split(r"(?m)^## ", md)[1:]:
        if chunk.startswith(title_startswith):
            return chunk
    raise AssertionError(f"section not found: {title_startswith}")


def test_chaos_corpus_still_satisfies_the_contract():
    """Messy is not the same as malformed: these are things a real producer
    emits, so they must still pass the input contract — otherwise this would be
    testing the front door instead of the degradation behaviour."""
    errors, _ = vr.validate_records(_chaos(), vr.load_schema(vr.DEFAULT_SCHEMA))
    assert errors == [], errors[:3]


def test_whole_report_renders_without_crashing():
    md = _md()
    assert "ANEB 战役级综合报告" in md
    assert len(md.splitlines()) > 50


def test_missing_tier_is_reported_not_extrapolated():
    assert "TIER_MISSING" in _section(_md(), "三级差分归因矩阵（n1")


def test_aborted_runs_surface_and_never_score_zero():
    md = _md()
    assert "'aborted'" in _section(md, "覆盖盘点")
    assert "只显性化" in md
    # an aborted run carries a null AQS; it must never enter a median as 0
    seen = False
    for rec in _chaos():
        if str(rec["run"].get("status", "")).startswith("aborted"):
            seen = True
            assert rec["run"]["aqs"]["score"] is None
            assert rec["run"]["aqs"]["not_computable_reason"]
    assert seen, "fixture should contain aborted runs"


def test_incomparable_pools_are_flagged():
    """Covers pathologies mixed_profile_version, mixed_histogram_edges and
    mixed_mode — named here so the coverage invariant below can find them."""
    md = _md()
    for marker in ("MIXED_PROFILE_VERSION", "MIXED_HIST_EDGES", "MIXED_MODE"):
        assert marker in md, marker


def test_single_carrier_point_is_reported_unmeasured_not_filled_in():
    """Pathology single_carrier. Its expected behaviour was written down in
    CHAOS_PATHOLOGIES and never checked by anything — the same gap D-182 found in
    the rehearsal corpus, one level down (D-183)."""
    from collections import defaultdict
    import campaign_common as cc
    import coverage_matrix as cm
    recs = _chaos()
    seen = defaultdict(set)
    for rec in recs:
        lab = cc.campaign_labels(rec)
        seen[lab["point_id"]].add(lab["carrier"])
    points = sorted(p for p in seen if p != "unlabeled")
    short = [p for p in points if len(seen[p]) == 1]
    assert short, "chaos corpus must contain a single-carrier point"
    res = cm.analyze(recs, {"point_id": points, "carrier": ["cmcc", "cucc"],
                            "time_band": ["busy", "idle"]})
    gaps = [c for c in res["cells"]
            if c["cell"]["point_id"] in short and c["status"] == "UNMEASURED"]
    assert gaps, "the untested carrier must be listed as UNMEASURED"
    # never quietly credited: zero samples is a gap, not a covered cell
    assert all(c["samples"] == 0 for c in gaps)


def test_every_declared_pathology_is_actually_checked():
    """CHAOS_PATHOLOGIES documents what each injected fault should produce. A
    pathology nobody asserts is a promise with no guard behind it — which is
    exactly what single_carrier was. Whoever adds one must name its key in the
    test that covers it; no separate mapping table to fall out of date."""
    with open(__file__, encoding="utf-8") as f:
        src = f.read()
    unchecked = [k for k, _ in sc.CHAOS_PATHOLOGIES if k not in src]
    assert not unchecked, f"pathologies with no test naming them: {unchecked}"


def test_clock_jump_becomes_a_trust_hotspot():
    assert "时钟可疑热点" in _section(_md(), "测量可信度")


def test_extreme_outlier_breaks_cv_not_the_median():
    """A 50x outlier must not drag the median (that is why medians are used),
    but it must show up as instability rather than being quietly absorbed."""
    assert "✗超门" in _section(_md(), "复测稳定性")


def test_all_invalid_cell_reports_zero_rate():
    validity = _section(_md(), "有效性与失效原因")
    assert re.search(r"\|\s*0(\.0)?%?\s*\|", validity), "0% valid-rate row missing"
    assert "LOW_VALID_RATE" in validity


def test_unlabelled_records_land_in_the_unlabeled_bucket():
    assert "unlabeled" in _section(_md(), "覆盖盘点")


def test_missing_tier_rows_carry_a_placeholder_not_a_zero():
    """A not-computable increment must render as the em-dash, never as 0 — a
    zero standing in for 'unknown' is the exact failure R-10 forbids."""
    attr = _section(_md(), "三级差分归因矩阵（n1")
    checked = 0
    for line in attr.splitlines():
        if not line.startswith("| ") or "TIER_MISSING" not in line:
            continue
        checked += 1
        assert "—" in [c.strip() for c in line.strip("|").split("|")], line
    assert checked, "fixture should contain TIER_MISSING rows"


def test_publish_check_flags_the_mess_without_crashing():
    sev = {r["item"]: r["severity"] for r in pc.check(_chaos())}
    assert sev["合成语料"] == pc.FAIL          # it IS a synthetic corpus
    assert sev["战役标签"] == pc.WARN          # some records unlabelled
    assert sev["有效率"] == pc.WARN
    assert sev["测量可信度"] == pc.WARN
