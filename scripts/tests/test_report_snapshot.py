# -*- coding: utf-8 -*-
"""Whole-report regression snapshot for build_report_markdown().

Per-invariant tests assert individual values; none catch a dropped section, a
reordered tier, a changed heading, or reworded warning text. This freezes the
entire markdown report for a FIXED synthetic corpus and byte-compares.

build_report_markdown() is deterministic (no wall-clock; provenance omitted; all
ordering via sorted()/insertion-order Counters), so the snapshot is stable. run_id
varies per fixture but is never rendered, so it does not affect the output.

Update the golden intentionally after reviewing a diff:
    python test_report_snapshot.py --update
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import campaign_report as rpt
from synth import make_record

GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures",
                      "report_snapshot.md")


def _corpus():
    """A fixed, rich corpus exercising most report sections deterministically:
    2 campaigns (before/after), 2 points, busy/idle, 3 tiers, a KPI + grade,
    order_index positions, and a validity mix."""
    recs = []
    for cid, aqs_base in (("base", 62), ("opt", 74)):
        for point in ("P1", "P2"):
            for tb in ("busy", "idle"):
                aqs = aqs_base + (5 if tb == "idle" else 0)
                for tier, rtt in (("metro", 20), ("regional", 38), ("core", 65)):
                    for i in range(6):
                        rec = make_record(
                            campaign={"campaign_id": cid, "tier": tier, "point_id": point,
                                      "carrier": "cmcc", "time_band": tb},
                            aqs=aqs,
                            sub_scores={"T1": 98, "N1": 95, "N2": 88 - (6 if tb == "busy" else 0)},
                            scenarios=[("s1_chat", {"n1_rtt_p50_ms": rtt, "n1_grade": "good"})])
                        rec["scenarios"][0]["order_index"] = i % 3
                        rec["scenarios"][0]["validity"] = "valid" if i < 5 else "invalid"
                        recs.append(rec)
    return recs


def _generate():
    return rpt.build_report_markdown(_corpus())


def test_report_matches_snapshot():
    assert os.path.exists(GOLDEN), \
        "golden missing — run: python scripts/tests/test_report_snapshot.py --update"
    with open(GOLDEN, encoding="utf-8") as f:
        golden = f.read()
    got = _generate()
    if got != golden:
        # first differing line, to make the failure actionable
        gl, gg = golden.splitlines(), got.splitlines()
        where = next((i for i in range(max(len(gl), len(gg)))
                      if i >= len(gl) or i >= len(gg) or gl[i] != gg[i]), None)
        ctx = ""
        if where is not None:
            exp = gl[where] if where < len(gl) else "<EOF>"
            act = gg[where] if where < len(gg) else "<EOF>"
            ctx = f" first diff at line {where + 1}:\n  golden: {exp!r}\n  got:    {act!r}"
        raise AssertionError("report output drifted from snapshot; review, then "
                             "--update if intended." + ctx)


def test_snapshot_is_deterministic():
    assert _generate() == _generate()


def _update():
    os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
    with open(GOLDEN, "w", encoding="utf-8", newline="\n") as f:
        f.write(_generate())
    print(f"updated {GOLDEN}")


if __name__ == "__main__":
    if "--update" in sys.argv:
        _update()
    else:
        test_report_matches_snapshot()
        print("snapshot OK")
