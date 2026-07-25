#!/usr/bin/env python3
"""ANEB campaign buffering-attribution rollup (stdlib only).

The per-scenario `buffering` block (batching score + attribution + shape stats) is
the richest UNCONSUMED schema block: it distinguishes network backpressure from
device/middlebox batching — the red-team distortion-accounting mission (R-06/R-17).

Per (point, carrier, time_band) cell, over scenarios[].buffering:
    the modal attribution category, median batching score, median sawtooth /
    near-zero-arrival ratios, and the share of scenarios NOT attributed "none".
    A cell where non-"none" batching dominates is flagged a distortion hot-spot.

R-05 (LOAD-BEARING): buffering is annotation / forensic evidence ONLY. Nothing
downstream — this tool included — may re-judge validity or score from it. Every
render says so. A cell with no buffering data is a coverage gap, not "clean".

Honesty (R-10): an all-null buffering block is 'not detected' and does not count
as a 0 score; attribution missing/None is bucketed as 'unknown', never 'none'.

Usage:
    python buffering_rollup.py results/*.jsonl
"""
import argparse
import sys
from collections import Counter, defaultdict

import campaign_common as cc

CELL_DIMS = ("point_id", "carrier", "time_band")
# Attributions that mean a distortion source is suspected (vs benign "none").
_BENIGN = {"none"}
# Share of suspect scenarios above which a cell is a distortion hot-spot. Named
# (not inline) so the provenance manifest can record the threshold a report was
# actually built with — retuning it changes what the report says (D-122).
HOTSPOT_SHARE = 0.5


def _attribution(b):
    a = b.get("attribution")
    return a if isinstance(a, str) and a else "unknown"


def buffering_cells(records, min_samples=cc.DEFAULT_MIN_SAMPLES):
    """Per-cell batching summary. A scenario counts only if it has a buffering block."""
    buckets = defaultdict(lambda: {"attr": Counter(), "score": [], "sawtooth": [],
                                    "near_zero": [], "n": 0})
    for rec in records:
        labels = cc.campaign_labels(rec)
        key = tuple(labels[d] for d in CELL_DIMS)
        for scn in cc.iter_scenarios(rec):
            b = cc.scenario_buffering(scn)
            if not b:
                continue
            g = buckets[key]
            g["n"] += 1
            g["attr"][_attribution(b)] += 1
            for field, dst in (("score", "score"), ("sawtooth_ratio", "sawtooth"),
                               ("near_zero_arrival_ratio", "near_zero")):
                v = cc.fnum(b.get(field))
                if v is not None:
                    g[dst].append(v)

    cells = []
    for key in sorted(buckets):
        g = buckets[key]
        n = g["n"]
        modal_attr = g["attr"].most_common(1)[0][0] if g["attr"] else "unknown"
        suspect = sum(c for a, c in g["attr"].items() if a not in _BENIGN and a != "unknown")
        suspect_share = (suspect / n) if n else None
        cells.append({
            "cell": dict(zip(CELL_DIMS, key)),
            "n": n,
            "modal_attribution": modal_attr,
            "attribution_counts": dict(g["attr"].most_common()),
            "score_median": cc.median(g["score"]) if g["score"] else None,
            "sawtooth_median": cc.median(g["sawtooth"]) if g["sawtooth"] else None,
            "near_zero_median": cc.median(g["near_zero"]) if g["near_zero"] else None,
            "suspect_share": suspect_share,
            # hot-spot: a majority of scenarios attributed to a distortion source
            "distortion_hotspot": bool(suspect_share is not None
                                       and suspect_share > HOTSPOT_SHARE),
            "low_confidence": n < min_samples,
        })
    return cells


def analyze(records, min_samples=cc.DEFAULT_MIN_SAMPLES):
    return {"cells": buffering_cells(records, min_samples), "min_samples": min_samples}


def render_markdown(res):
    lines = [
        "## 批化(buffering)归因（取证/失真核算）",
        "",
        "> **R-05**：批化标注为**取证证据**，**不改判** validity/score（本表亦然）。"
        "`none`=未见批化失真；非 `none` 占多数的格标 `失真热点`。空块=未检测（非 0）。",
        "",
    ]
    if not res["cells"]:
        lines.append("_无 buffering 数据（记录未含批化标注块）。_")
        return "\n".join(lines)
    lines += ["| 点位 | 运营商 | 时段 | n | 众数归因 | 批化分中位 | sawtooth | 近零到达 | 疑似占比 | 备注 |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for c in res["cells"]:
        cl = {k: cc.md_cell(v) for k, v in c["cell"].items()}   # labels are human-typed
        notes = []
        if c["distortion_hotspot"]:
            notes.append("**失真热点**")
        if c["low_confidence"]:
            notes.append("low_conf")
        share = "—" if c["suspect_share"] is None else f"{c['suspect_share'] * 100:.0f}%"
        lines.append(
            f"| {cl['point_id']} | {cl['carrier']} | {cl['time_band']} | {c['n']} | "
            # 3 digits: these are 0..1 ratios — the default 1 digit renders a real
            # 0.02 as "0", which reads as "no batching detected" (R-10 honesty).
            f"{c['modal_attribution']} | {cc.fmt_num(c['score_median'], 3)} | "
            f"{cc.fmt_num(c['sawtooth_median'], 3)} | {cc.fmt_num(c['near_zero_median'], 3)} | "
            f"{share} | {'; '.join(notes) or '—'} |")
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB campaign buffering-attribution rollup")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--min-samples", type=int, default=cc.DEFAULT_MIN_SAMPLES)
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    recs, files = cc.load_records(args.inputs)
    res = analyze(recs, args.min_samples)
    print(render_markdown(res))
    print(f"\n<!-- records={len(recs)} files={len(files)} cells={len(res['cells'])} -->",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
