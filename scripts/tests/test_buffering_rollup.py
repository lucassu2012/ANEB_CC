# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/buffering_rollup.py (forensic batching rollup).

Encodes the R-05 red line: buffering is annotation-only evidence. These tests
pin the honesty rules (empty block = not detected, missing attribution =
'unknown' not 'none', null score never becomes 0) and the hot-spot threshold.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import buffering_rollup as br
from synth import make_record


def _rec(bufs, *, point="P1", carrier="cmcc", time_band="busy"):
    """One record whose scenarios carry the given buffering blocks (one per scenario)."""
    rec = make_record(
        campaign={"campaign_id": "base", "tier": "metro", "point_id": point,
                  "carrier": carrier, "time_band": time_band},
        aqs=90, scenarios=[("s1_chat", {}) for _ in bufs])
    for scn, b in zip(rec["scenarios"], bufs):
        scn["buffering"] = b
    return rec


def _b(attribution="none", score=0.01, sawtooth=0.0, near_zero=0.0):
    return {"score": score, "attribution": attribution, "sample_count": 100,
            "sawtooth_ratio": sawtooth, "near_zero_arrival_ratio": near_zero,
            "batch_count": 0}


def test_modal_attribution_and_medians():
    recs = [_rec([_b("none", score=0.01)]) for _ in range(3)] \
        + [_rec([_b("none", score=0.03)]) for _ in range(2)]
    c = br.analyze(recs)["cells"][0]
    assert c["n"] == 5
    assert c["modal_attribution"] == "none"
    assert c["score_median"] == 0.01            # median of [.01,.01,.01,.03,.03]
    assert c["suspect_share"] == 0.0
    assert c["distortion_hotspot"] is False


def test_distortion_hotspot_flagged_when_batching_dominates():
    recs = ([_rec([_b("middlebox_suspect", sawtooth=0.4)]) for _ in range(4)]
            + [_rec([_b("none")]) for _ in range(1)])
    c = br.analyze(recs)["cells"][0]
    assert c["modal_attribution"] == "middlebox_suspect"
    assert c["suspect_share"] == 0.8            # 4/5 non-none
    assert c["distortion_hotspot"] is True


def test_exactly_half_is_not_a_hotspot():
    recs = ([_rec([_b("airlink_suspect")]) for _ in range(2)]
            + [_rec([_b("none")]) for _ in range(2)])
    c = br.analyze(recs)["cells"][0]
    assert c["suspect_share"] == 0.5
    assert c["distortion_hotspot"] is False     # strictly > 0.5 required


def test_empty_buffering_block_skipped():
    recs = [_rec([{}]) for _ in range(3)]       # no batching annotation at all
    assert br.analyze(recs)["cells"] == []


def test_missing_attribution_is_unknown_not_none():
    recs = [_rec([{"score": 0.5}]) for _ in range(3)]   # no 'attribution' key
    c = br.analyze(recs)["cells"][0]
    assert c["modal_attribution"] == "unknown"
    # 'unknown' is neither a distortion suspect nor benign 'none'
    assert c["suspect_share"] == 0.0


def test_null_score_not_counted_as_zero():
    recs = [_rec([{"attribution": "none", "score": None}]) for _ in range(3)]
    c = br.analyze(recs)["cells"][0]
    assert c["score_median"] is None            # not 0.0
    assert c["n"] == 3                          # still counted (block present)


def test_low_confidence_below_floor():
    recs = [_rec([_b("none")]) for _ in range(3)]   # 3 < DEFAULT_MIN_SAMPLES (5)
    assert br.analyze(recs)["cells"][0]["low_confidence"] is True


def test_cells_separated_per_cell():
    recs = ([_rec([_b("middlebox_suspect")], point="P1") for _ in range(5)]
            + [_rec([_b("none")], point="P2") for _ in range(5)])
    by = {c["cell"]["point_id"]: c for c in br.analyze(recs)["cells"]}
    assert by["P1"]["distortion_hotspot"] is True
    assert by["P2"]["distortion_hotspot"] is False


def test_markdown_renders_r05_caveat():
    recs = [_rec([_b("middlebox_suspect")]) for _ in range(5)]
    md = br.render_markdown(br.analyze(recs))
    assert "R-05" in md
    assert "不改判" in md
    assert "失真热点" in md


def test_small_score_not_rendered_as_zero():
    """A real 0.02 batching score must not print as "0" — that reads as 'none detected'."""
    recs = [_rec([_b("none", score=0.02, sawtooth=0.01)]) for _ in range(5)]
    row = [ln for ln in br.render_markdown(br.analyze(recs)).splitlines()
           if ln.startswith("| P1 ")][0]
    col = [x.strip() for x in row.strip("|").split("|")]
    # point | carrier | band | n | modal | score | sawtooth | near_zero | share | notes
    assert col[5] == "0.02"     # NOT "0" — a real small score must stay visible
    assert col[6] == "0.01"
    assert col[7] == "0"        # a true 0.0 still renders as plain 0


def test_markdown_empty_when_no_buffering():
    md = br.render_markdown(br.analyze([_rec([{}]) for _ in range(3)]))
    assert "无 buffering 数据" in md


def test_tied_attribution_is_not_a_modal_attribution():
    """This is a forensic verdict: network slow, or something batched the stream.
    Deciding a tie by input order would make it depend on file order (D-148)."""
    cells = br.buffering_cells([_rec([_b("none"), _b("middlebox_suspect")])])
    assert cells[0]["modal_attribution"] is None
    assert cells[0]["attribution_tie"] == ["middlebox_suspect", "none"]
    assert "ATTR_TIE:middlebox_suspect/none" in br.render_markdown(
        {"cells": cells, "min_samples": 5})
