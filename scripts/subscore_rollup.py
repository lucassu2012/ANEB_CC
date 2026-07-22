#!/usr/bin/env python3
"""ANEB campaign AQS sub-score attribution (stdlib only).

The SCORE-side complement to attribution.py's latency matrix. attribution shows
WHERE on the path latency accrues; this shows WHICH KPI dimension drags a cell's
composite AQS down. The campaign layer otherwise reads only run.aqs.score, so a
report could say a cell scores poorly but not why.

Per (point, carrier, time_band) cell, over run.aqs.sub_scores ({T1,T2,N1,…} ->
0-100): the median sub-score per dimension, plus the DRAGGING dimension (lowest
median) and the spread (best - worst) showing how uneven the profile is.

Honesty (R-10): a not-computable run has an empty sub_scores map and contributes
nothing (never a 0); a cell with no sub-scores has dragging_dim None (not a
fabricated "all good"); a dimension present in only some runs is still summarized
over the runs that have it, with its own n. Cells below the floor are low_confidence.

Usage:
    python subscore_rollup.py results/*.jsonl
"""
import argparse
import sys
from collections import defaultdict

import campaign_common as cc

CELL_DIMS = ("point_id", "carrier", "time_band")
# Canonical dimension display order (T=token/latency, N=network, U=uplink); any
# unknown key still shows, appended after these in sorted order.
_DIM_ORDER = ["T1", "T2", "T3", "T4", "N1", "N2", "U1", "U2"]


def _dim_sort_key(dim):
    return (_DIM_ORDER.index(dim) if dim in _DIM_ORDER else len(_DIM_ORDER), dim)


def subscore_cells(records, min_samples=cc.DEFAULT_MIN_SAMPLES):
    """Per-cell median sub-score per dimension + the dragging (lowest) dimension."""
    buckets = defaultdict(lambda: defaultdict(list))   # cell -> dim -> [values]
    counts = defaultdict(int)                           # cell -> runs with any sub-score
    for rec in records:
        subs = cc.run_sub_scores(rec)
        if not subs:
            continue
        labels = cc.campaign_labels(rec)
        key = tuple(labels[d] for d in CELL_DIMS)
        counts[key] += 1
        for dim, val in subs.items():
            buckets[key][dim].append(val)

    cells = []
    for key in sorted(buckets):
        per_dim = buckets[key]
        dims = {}
        for dim in sorted(per_dim, key=_dim_sort_key):
            vals = per_dim[dim]
            dims[dim] = {"median": cc.median(vals), "n": len(vals)}
        medians = {d: v["median"] for d, v in dims.items()}
        dragging = min(medians, key=lambda d: medians[d]) if medians else None
        spread = (max(medians.values()) - min(medians.values())) if medians else None
        cells.append({
            "cell": dict(zip(CELL_DIMS, key)),
            "dims": dims,
            "runs": counts[key],
            "dragging_dim": dragging,
            "dragging_median": medians.get(dragging) if dragging else None,
            "spread": spread,
            "low_confidence": counts[key] < min_samples,
        })
    return cells


def analyze(records, min_samples=cc.DEFAULT_MIN_SAMPLES):
    cells = subscore_cells(records, min_samples)
    all_dims = []
    for c in cells:
        for d in c["dims"]:
            if d not in all_dims:
                all_dims.append(d)
    all_dims.sort(key=_dim_sort_key)
    return {"cells": cells, "dimensions": all_dims, "min_samples": min_samples}


def render_markdown(res):
    lines = [
        "## AQS 分数侧归因（各维度子分 + 拖累维度）",
        "",
        "> 归因矩阵的分数侧互补：composite AQS 低时，指出是哪个 KPI 维度在拖后腿。"
        "子分 0-100，越高越好；`拖累` = 中位子分最低的维度。",
        "",
    ]
    if not res["cells"]:
        lines.append("_无 run.aqs.sub_scores 数据（记录不可计算或缺子分）。_")
        return "\n".join(lines)

    dims = res["dimensions"]
    header = "| 点位 | 运营商 | 时段 | runs | " + " | ".join(dims) + " | 拖累 | 极差 | 备注 |"
    sep = "|" + "---|" * (4 + len(dims) + 3)
    lines += [header, sep]
    for c in res["cells"]:
        cl = c["cell"]
        cellvals = []
        for d in dims:
            cellvals.append(cc.fmt_num(c["dims"][d]["median"]) if d in c["dims"] else "—")
        drag = (f"**{c['dragging_dim']}**={cc.fmt_num(c['dragging_median'])}"
                if c["dragging_dim"] else "—")
        note = "low_conf" if c["low_confidence"] else "—"
        lines.append(
            f"| {cl['point_id']} | {cl['carrier']} | {cl['time_band']} | {c['runs']} | "
            + " | ".join(cellvals)
            + f" | {drag} | {cc.fmt_num(c['spread'])} | {note} |")
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB campaign AQS sub-score attribution")
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
