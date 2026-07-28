# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/subscore_rollup.py (score-side attribution)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import subscore_rollup as ss
from synth import make_record


def _rec(subs, *, point="P1", carrier="cmcc", time_band="busy", tier="metro",
         campaign_id="base"):
    return make_record(
        campaign={"campaign_id": campaign_id, "tier": tier, "point_id": point,
                  "carrier": carrier, "time_band": time_band},
        aqs=90, sub_scores=subs, scenarios=[])


def test_impossible_sub_score_cannot_hijack_the_dragging_dimension():
    """The LOWEST median IS the dragging dimension, so one out-of-range value
    takes over the report's answer to "which dimension drags this cell down" —
    and the summary's 分数最低维 signal reads exactly that. Sub-scores are 0..100
    per the schema ("KPI id → 0-100 子分"), unchecked until D-179."""
    recs = [_rec({"T1": 80, "T2": 60, "N1": -9999}) for _ in range(5)]
    c = ss.analyze(recs)["cells"][0]
    assert c["dragging_dim"] == "T2"            # the real laggard, not the corrupt one
    assert c["dragging_median"] == 60
    assert c["spread"] == 20                    # 80 - 60, not 10079
    assert "N1" not in c["dims"]                # out of the aggregate…
    assert c["implausible_values"] == {"N1<0": 5}          # …counted where it shows
    assert "IMPLAUSIBLE_VALUE:N1<0×5" in ss.render_markdown(ss.analyze(recs))


def test_cell_of_only_impossible_sub_scores_still_gets_a_row():
    recs = [_rec({"N1": 100.5}) for _ in range(3)]         # just past the 0..100 edge
    cells = ss.analyze(recs)["cells"]
    assert len(cells) == 1
    assert cells[0]["dragging_dim"] is None                # not a fabricated verdict
    assert cells[0]["implausible_values"] == {"N1>100": 3}


def test_dragging_dimension_is_the_lowest():
    recs = [_rec({"T1": 99, "N1": 98, "N2": 60}) for _ in range(5)]
    c = ss.analyze(recs)["cells"][0]
    assert c["dims"]["N2"]["median"] == 60
    assert c["dragging_dim"] == "N2"           # lowest sub-score drags composite
    assert c["dragging_median"] == 60
    assert c["spread"] == 39                    # 99 - 60


def test_medians_per_dimension():
    recs = ([_rec({"T1": 90, "N2": 80}) for _ in range(3)]
            + [_rec({"T1": 100, "N2": 60}) for _ in range(2)])
    c = ss.analyze(recs)["cells"][0]
    assert c["dims"]["T1"]["median"] == 90      # median of [90,90,90,100,100]
    assert c["dims"]["N2"]["median"] == 80      # median of [80,80,80,60,60]
    assert c["runs"] == 5


def test_empty_sub_scores_contribute_nothing():
    recs = [_rec({}) for _ in range(3)]         # not-computable runs
    res = ss.analyze(recs)
    assert res["cells"] == []                    # no fabricated cell


def test_cell_with_no_subscores_is_absent_not_all_good():
    recs = ([_rec({"T1": 95, "N2": 55}, point="P1") for _ in range(5)]
            + [_rec({}, point="P2") for _ in range(5)])   # P2 all not-computable
    pts = {c["cell"]["point_id"] for c in ss.analyze(recs)["cells"]}
    assert pts == {"P1"}                         # P2 absent, not "dragging_dim None all good"


def test_dimension_present_in_only_some_runs():
    recs = ([_rec({"T1": 90, "N2": 80}) for _ in range(3)]
            + [_rec({"T1": 90}) for _ in range(2)])       # N2 missing in 2 runs
    c = ss.analyze(recs)["cells"][0]
    assert c["dims"]["N2"]["n"] == 3            # summarized over the runs that have it
    assert c["dims"]["T1"]["n"] == 5


def test_low_confidence_below_floor():
    recs = [_rec({"T1": 90, "N2": 80}) for _ in range(3)]  # 3 < 5
    assert ss.analyze(recs)["cells"][0]["low_confidence"] is True


def test_dimension_display_order_canonical():
    recs = [_rec({"N2": 80, "T1": 90, "U1": 70}) for _ in range(5)]
    # T before N before U regardless of dict insertion order
    assert ss.analyze(recs)["dimensions"] == ["T1", "N2", "U1"]


def test_cells_separated_per_cell():
    recs = ([_rec({"T1": 90, "N2": 50}, point="P1") for _ in range(5)]
            + [_rec({"T1": 60, "N2": 95}, point="P2") for _ in range(5)])
    by = {c["cell"]["point_id"]: c for c in ss.analyze(recs)["cells"]}
    assert by["P1"]["dragging_dim"] == "N2"
    assert by["P2"]["dragging_dim"] == "T1"


def test_markdown_renders():
    recs = [_rec({"T1": 99, "N2": 60}) for _ in range(5)]
    md = ss.render_markdown(ss.analyze(recs))
    assert "分数侧归因" in md
    assert "N2" in md


def test_markdown_empty_when_no_subscores():
    md = ss.render_markdown(ss.analyze([_rec({}) for _ in range(3)]))
    assert "无 run.aqs.sub_scores" in md


def test_the_spread_column_matches_the_subscores_printed_beside_it():
    """极差 is max − min of the numbers in the same row, so subtract and check.

    Rounded on their own, 32.45 / 25.26 / 35.25 printed as 32.5 / 25.3 / 35.2
    beside a spread of 10, and the two printed extremes differ by 9.9 — 23% of
    rows disagreed with themselves (D-220). The dragging figure is held to the
    same precision as its own column, which is D-207's rule.
    """
    import campaign_common as cc

    subs = {"T1": 32.45, "N1": 25.26, "N2": 35.25}
    res = ss.analyze([_rec(dict(subs)) for _ in range(5)])
    c = res["cells"][0]

    # The fixture must still carry the hazard, or this passes on the old code.
    naive = {d: float(cc.fmt_num(c["dims"][d]["median"])) for d in subs}
    assert abs((max(naive.values()) - min(naive.values()))
               - float(cc.fmt_num(c["spread"]))) > 1e-9, (
        "fixture no longer reproduces the independent-rounding drift")

    md = ss.render_markdown(res)
    header = [x.strip() for x in
              [ln for ln in md.splitlines() if ln.startswith("| 点位")][0]
              .strip().strip("|").split("|")]
    row = [ln for ln in md.splitlines() if ln.startswith("| P1 |")][0]
    cells = [x.strip() for x in row.strip().strip("|").split("|")]

    dim_vals = [float(cells[header.index(d)]) for d in ("T1", "N1", "N2")]
    spread = float(cells[header.index("极差")])
    assert abs((max(dim_vals) - min(dim_vals)) - spread) < 1e-9, row
    assert "ROUNDING_UNRECONCILED" not in cells[-1], row

    # The dragging figure repeats one of the columns; it may not repeat it at a
    # different precision.
    drag = cells[header.index("拖累")]
    assert drag.startswith("**N1**="), drag
    assert drag.split("=", 1)[1] == cells[header.index("N1")], (drag, cells)
