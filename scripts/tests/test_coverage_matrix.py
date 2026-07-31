# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/coverage_matrix.py (joint-grid completeness)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import json
import tempfile
import types

import coverage_matrix as cm
from synth import aqs_records, make_record

TARGET = {"point_id": ["P1", "P2"], "carrier": ["cmcc", "cucc"],
          "time_band": ["busy", "idle"]}   # 2*2*2 = 8 joint cells


def test_off_plan_rows_share_the_cells_key_set():
    """D-341's structural half, kept past the removal of the repeat column.

    The 「不同重复」 column itself was withdrawn by D-344 (the contract defines
    `repeat_index` only inside a scenario; `run.repeat_index` has no producer,
    so the column was inert on all real data). What stays is the shape D-341
    fixed: whatever keys a planned cell carries, an off-plan cell carries the
    same ones minus `status` — a key added to `cells` and forgotten on
    `off_plan` fails here without anyone hand-listing column names.
    """
    res = cm.analyze(aqs_records(90, 3, point="P9", carrier="cmcc",
                                 time_band="busy"), target=TARGET)
    assert res["off_plan"], "fixture built no off-plan cell"
    assert set(res["off_plan"][0]) == set(res["cells"][0]) - {"status"}, (
        res["off_plan"][0], res["cells"][0])


def _status(res, point, carrier, tb):
    for c in res["cells"]:
        cl = c["cell"]
        if (cl["point_id"], cl["carrier"], cl["time_band"]) == (point, carrier, tb):
            return c["status"], c["samples"]
    raise KeyError((point, carrier, tb))


def test_planned_total_is_the_cartesian_product():
    res = cm.analyze([], TARGET)
    assert res["planned_total"] == 8
    assert res["covered"] == 0
    assert all(c["status"] == "UNMEASURED" for c in res["cells"])
    assert res["coverage_pct"] == 0.0


def test_covered_vs_undersampled_vs_unmeasured():
    recs = (aqs_records(90, 5, point="P1", carrier="cmcc", time_band="busy")   # covered
            + aqs_records(90, 2, point="P1", carrier="cmcc", time_band="idle"))  # under
    res = cm.analyze(recs, TARGET)
    assert _status(res, "P1", "cmcc", "busy") == ("COVERED", 5)
    assert _status(res, "P1", "cmcc", "idle") == ("UNDER_SAMPLED", 2)
    assert _status(res, "P2", "cucc", "busy") == ("UNMEASURED", 0)
    assert res["covered"] == 1
    assert round(res["coverage_pct"], 1) == 12.5    # 1/8


def test_undersampled_not_rounded_up_to_covered():
    recs = aqs_records(90, 4, point="P1", carrier="cmcc", time_band="busy")  # 4 < 5
    res = cm.analyze(recs, TARGET)
    assert _status(res, "P1", "cmcc", "busy") == ("UNDER_SAMPLED", 4)
    assert res["covered"] == 0                       # honest: not counted


def test_records_without_aqs_do_not_advance_coverage():
    recs = [make_record(campaign={"campaign_id": "c", "point_id": "P1", "carrier": "cmcc",
                                  "time_band": "busy"}, aqs=None, scenarios=[])
            for _ in range(9)]
    res = cm.analyze(recs, TARGET)
    assert _status(res, "P1", "cmcc", "busy") == ("UNMEASURED", 0)   # no AQS = not usable


def test_off_plan_cells_listed_separately():
    recs = aqs_records(90, 5, point="P9", carrier="cmcc", time_band="busy")  # P9 not in target
    res = cm.analyze(recs, TARGET)
    assert len(res["off_plan"]) == 1
    assert res["off_plan"][0]["cell"]["point_id"] == "P9"
    # off-plan does not inflate planned coverage
    assert res["covered"] == 0


def test_descriptive_mode_without_target():
    recs = (aqs_records(90, 5, point="P1") + aqs_records(90, 2, point="P2"))
    res = cm.analyze(recs, target=None)
    assert res["has_target"] is False
    assert res["coverage_pct"] is None               # never invents a target
    statuses = {c["cell"]["point_id"]: c["status"] for c in res["cells"]}
    assert statuses["P1"] == "COVERED"
    assert statuses["P2"] == "UNDER_SAMPLED"


def test_partial_target_falls_back_to_descriptive():
    """A target missing a dimension is not a grid — degrade, don't crash.

    Defence in depth for programmatic callers; the CLI now rejects a partial
    target at _load_target, so nobody reaches this path from the command line."""
    res = cm.analyze(aqs_records(90, 5), target={"point_id": ["P1"], "carrier": [],
                                                 "time_band": []})
    assert res["has_target"] is False


def test_markdown_target_mode():
    res = cm.analyze(aqs_records(90, 5, point="P1", carrier="cmcc", time_band="busy"), TARGET)
    md = cm.render_markdown(res)
    assert "覆盖完备性矩阵" in md
    assert "未测" in md                               # some cells unmeasured
    assert "%" in md


def test_markdown_descriptive_mode():
    md = cm.render_markdown(cm.analyze(aqs_records(90, 5), target=None))
    assert "描述模式" in md


def _args(config=None, points=None, carriers=None, time_bands=None):
    return types.SimpleNamespace(config=config, points=points, carriers=carriers,
                                 time_bands=time_bands)


def _write_cfg(d, obj):
    p = os.path.join(d, "grid.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    return p


def test_config_with_wrong_key_names_is_a_hard_error():
    """Plural key names (points/carriers/time_bands) silently produced an empty
    target and fell through to descriptive mode — the user would believe coverage
    tracking was running when it was not (D-119)."""
    with tempfile.TemporaryDirectory() as d:
        cfg = _write_cfg(d, {"points": ["P1"], "carriers": ["cmcc"],
                             "time_bands": ["busy"]})
        try:
            cm._load_target(_args(cfg))
        except SystemExit as e:
            msg = str(e)
            assert "declares no values for" in msg
            assert "point_id" in msg           # tells you the expected keys
            assert "points" in msg             # and what you actually wrote
        else:
            raise AssertionError("wrong key names must not be accepted silently")


def test_config_with_correct_keys_loads():
    with tempfile.TemporaryDirectory() as d:
        cfg = _write_cfg(d, {"point_id": ["P1", "P2"], "carrier": ["cmcc"],
                             "time_band": ["busy"]})
        assert cm._load_target(_args(cfg)) == {
            "point_id": ["P1", "P2"], "carrier": ["cmcc"], "time_band": ["busy"]}


def test_partial_config_is_a_hard_error_too():
    # ⚠ SOLE targeted guard on handover §2.12's "the guard's predicate must be
    #   the consumer's predicate" (D-186's mutation map). Reverting this to any()
    #   is exactly the D-173 defect, and nothing else would notice.
    """One plural typo is enough. D-119 made a WHOLLY empty target fatal, but the
    guard tested any() while analyze() requires all() — so a config with two good
    keys and one typo passed the guard, fell through to descriptive mode, and
    printed the banner '未声明目标网格' at someone who had just declared one. The
    error must name the dims that came up empty, not just the ones it recognised."""
    with tempfile.TemporaryDirectory() as d:
        cfg = _write_cfg(d, {"point_id": ["P1"], "carrier": ["cmcc"],
                             "time_bands": ["busy"]})       # plural on ONE dim
        try:
            cm._load_target(_args(cfg))
        except SystemExit as e:
            assert "time_band" in str(e)                    # names the empty dim
        else:
            raise AssertionError("a partly-empty target must not reach descriptive mode")


def test_partial_flags_are_a_hard_error():
    """Same hole via the flag path: --points/--carriers without --time-bands."""
    try:
        cm._load_target(_args(points="P1", carriers="cmcc"))
    except SystemExit as e:
        assert "--time-bands" in str(e)
    else:
        raise AssertionError("an incomplete flag grid must not reach descriptive mode")


def test_no_flags_at_all_is_descriptive_mode():
    """Asking for nothing is a legitimate request — only a HALF-asked grid lies."""
    assert cm._load_target(_args()) is None


def test_complete_flags_load():
    assert cm._load_target(_args(points="P1,P2", carriers="cmcc", time_bands="busy,idle")) == {
        "point_id": ["P1", "P2"], "carrier": ["cmcc"], "time_band": ["busy", "idle"]}
