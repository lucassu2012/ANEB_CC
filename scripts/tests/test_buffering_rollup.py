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


def test_impossible_forensic_values_leave_the_medians():
    """Damage is bounded here — R-05 keeps this block annotation-only and the
    hot-spot verdict is count-based — but a batching score of -50 is still a
    number a reader would quote out of the evidence column (D-179)."""
    import campaign_common as cc
    recs = ([_rec([_b("middlebox_suspect", score=-50.0)]) for _ in range(3)]
            + [_rec([_b("middlebox_suspect", score=0.30)]) for _ in range(2)])
    c = br.analyze(recs)["cells"][0]
    assert c["score_median"] == 0.30            # the two real scores, not -50
    assert c["implausible_values"] == {"score<0": 3}
    # the count-based verdict is unaffected: all five were middlebox_suspect
    assert c["suspect_share"] == 1.0
    assert c["distortion_hotspot"] is True
    # the schema documents no upper bound for a ratio, so neither do we — only
    # the impossible side is judged, never an invented ceiling
    assert cc.value_problem("sawtooth_ratio", 7.5) is None
    assert cc.value_problem("sawtooth_ratio", -0.5) == "<0"


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
    lines = br.render_markdown(br.analyze(recs)).splitlines()
    # look columns up BY NAME: positional indices break every time a column is
    # added, which is exactly what happened when 未测/残差样本中位 landed (D-163)
    header = [x.strip() for x in
              [ln for ln in lines if ln.startswith("| 点位 ")][0].strip("|").split("|")]
    row = [x.strip() for x in
           [ln for ln in lines if ln.startswith("| P1 ")][0].strip("|").split("|")]
    col = dict(zip(header, row))
    assert col["批化分中位"] == "0.02"   # NOT "0" — a real small score must stay visible
    assert col["sawtooth"] == "0.01"
    assert col["近零到达"] == "0"        # a true 0.0 still renders as plain 0


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


_ALL_NULL = {"score": None, "attribution": None, "sample_count": None,
             "sawtooth_ratio": None, "near_zero_arrival_ratio": None}


def test_all_null_block_is_not_an_observation():
    """The shipping producer does not omit the block when nothing was measured —
    TestEngine returns null residuals and ResultReporter still writes all nine
    keys. Counting that as an observation rendered 疑似占比 0% on a corpus with
    zero batching measurements (D-163)."""
    res = br.analyze([_rec([dict(_ALL_NULL)]) for _ in range(6)])
    c = res["cells"][0]
    assert c["n"] == 0                       # nothing was measured
    assert c["not_detected"] == 6
    assert c["suspect_share"] is None        # NOT 0.0
    assert c["distortion_hotspot"] is False
    assert res["no_evidence"] is True
    md = br.render_markdown(res)
    assert "未测到批化" in md
    assert "覆盖缺口" in md


def test_unmeasured_scenarios_do_not_dilute_a_hotspot():
    """4 zero-measurement scenarios used to take a 100% hot-spot down to 43%,
    flip the cell to confident and flip the modal verdict to `unknown`."""
    real = [_b("middlebox_suspect", score=0.6, sawtooth=0.4, near_zero=0.3)]
    recs = ([_rec(list(real)) for _ in range(3)]
            + [_rec([dict(_ALL_NULL)]) for _ in range(4)])
    c = br.buffering_cells(recs)[0]
    assert c["n"] == 3 and c["not_detected"] == 4
    assert c["suspect_share"] == 1.0
    assert c["distortion_hotspot"] is True
    assert c["modal_attribution"] == "middlebox_suspect"
    assert c["low_confidence"] is True       # 3 measured < min_samples, honestly


def test_sample_count_reaches_the_reader():
    """A `none` verdict backed by 2 residual samples is not the same evidence as
    one backed by 600, and sample_count had no consumer at all."""
    big = br.buffering_cells([_rec([_b("none", score=0.01)]) for _ in range(5)])
    for c in big:
        assert c["sample_count_median"] == 100      # _b default
    md = br.render_markdown(br.analyze([_rec([_b("none", score=0.01)]) for _ in range(5)]))
    assert "残差样本中位" in md
