#!/usr/bin/env python3
"""ANEB campaign coverage-completeness matrix (stdlib only).

inventory() reports only INDEPENDENT marginal counts (points, carriers, time_bands
separately), which cannot answer the field-campaign question: which JOINT
point×carrier×time_band cells are still unmeasured or under-sampled? This is the
"where still to measure" planning view against a declared target grid.

Given a target design (the intended points × carriers × time_bands), classify
every joint cell:
    UNMEASURED     — 0 usable records
    UNDER_SAMPLED  — 1 .. min_samples-1 usable records
    COVERED        — >= min_samples usable records
and separately list OFF_PLAN cells that were measured but are not in the target
(a mislabel or an unplanned point). "Usable" = has an AQS score (a record that
produced no score does not advance coverage).

Honesty (R-10): coverage % counts only COVERED planned cells over the planned
total; under-sampled cells are NOT rounded up to covered. With no target grid
declared, degrades to reporting observed joint cells and their sample counts
(descriptive), and says so — it never invents a target.

Usage:
    python coverage_matrix.py results/*.jsonl \
        --points P1,P2 --carriers cmcc,cucc --time-bands busy,idle
    python coverage_matrix.py results/*.jsonl --config grid.json
"""
import argparse
import itertools
import json
import sys
from collections import defaultdict

import campaign_common as cc

CELL_DIMS = ("point_id", "carrier", "time_band")


def observed_cells(records):
    """{(point,carrier,time_band) -> usable-record count} (usable = has AQS)."""
    counts = defaultdict(int)
    for rec in records:
        if cc.run_aqs(rec) is None:
            continue
        labels = cc.campaign_labels(rec)
        counts[tuple(labels[d] for d in CELL_DIMS)] += 1
    return counts


def analyze(records, target=None, min_samples=cc.DEFAULT_MIN_SAMPLES):
    """target: {'point_id':[...], 'carrier':[...], 'time_band':[...]} or None."""
    observed = observed_cells(records)

    if not target or not all(target.get(d) for d in CELL_DIMS):
        # Descriptive mode: no target grid — report what was observed, no invention.
        cells = [{"cell": dict(zip(CELL_DIMS, k)), "samples": observed[k],
                  "status": "COVERED" if observed[k] >= min_samples else "UNDER_SAMPLED"}
                 for k in sorted(observed)]
        return {"has_target": False, "min_samples": min_samples, "planned_total": None,
                "covered": None, "coverage_pct": None, "cells": cells, "off_plan": []}

    planned = list(itertools.product(target["point_id"], target["carrier"], target["time_band"]))
    planned_set = set(planned)
    cells, covered = [], 0
    for key in planned:
        n = observed.get(key, 0)
        if n == 0:
            status = "UNMEASURED"
        elif n < min_samples:
            status = "UNDER_SAMPLED"
        else:
            status = "COVERED"
            covered += 1
        cells.append({"cell": dict(zip(CELL_DIMS, key)), "samples": n, "status": status})
    off_plan = [{"cell": dict(zip(CELL_DIMS, k)), "samples": observed[k]}
                for k in sorted(observed) if k not in planned_set]
    total = len(planned)
    return {
        "has_target": True, "min_samples": min_samples, "planned_total": total,
        "covered": covered, "coverage_pct": (covered / total * 100.0) if total else None,
        "cells": cells, "off_plan": off_plan,
    }


_STATUS_LABEL = {"UNMEASURED": "未测", "UNDER_SAMPLED": "欠采", "COVERED": "已覆盖"}


def render_markdown(res):
    lines = ["## 覆盖完备性矩阵（联合网格：点位 × 运营商 × 时段）", ""]
    if not res["has_target"]:
        lines += [
            "> 未声明目标网格 —— 描述模式：仅列**已观测**联合单元及样本数，不虚构目标。"
            f"（样本 ≥{res['min_samples']} 记已覆盖）",
            "",
        ]
    else:
        lines += [
            f"> 目标 {res['planned_total']} 个联合单元；已覆盖（样本 ≥{res['min_samples']}）"
            f"{res['covered']} 个 = **{cc.fmt_num(res['coverage_pct'])}%**。"
            "未测/欠采即「下一步该测哪里」。",
            "",
        ]
    if not res["cells"] and not res["off_plan"]:
        lines.append("_无联合单元。_")
        return "\n".join(lines)

    lines += ["| 点位 | 运营商 | 时段 | 样本 | 状态 |", "|---|---|---|---|---|"]
    for c in res["cells"]:
        cl = c["cell"]
        lines.append(f"| {cl['point_id']} | {cl['carrier']} | {cl['time_band']} | "
                     f"{c['samples']} | {_STATUS_LABEL.get(c['status'], c['status'])} |")
    if res["off_plan"]:
        lines += ["", "### 计划外已测单元（不在目标网格；疑似误标或未规划点位）", "",
                  "| 点位 | 运营商 | 时段 | 样本 |", "|---|---|---|---|"]
        for c in res["off_plan"]:
            cl = c["cell"]
            lines.append(f"| {cl['point_id']} | {cl['carrier']} | {cl['time_band']} | "
                         f"{c['samples']} |")
    return "\n".join(lines)


def _parse_list(s):
    return [t.strip() for t in s.split(",") if t.strip()] if s else []


def _load_target(args):
    if args.config:
        with open(args.config, encoding="utf-8") as f:
            cfg = json.load(f)
        target = {d: cfg.get(d) or [] for d in CELL_DIMS}
        if not any(target.values()):
            # A config was explicitly given but yielded nothing — almost always
            # wrong key names. Falling through to descriptive mode here would let
            # someone believe coverage tracking is running when it is not, so this
            # is a hard error: 'cannot check' must never look like 'checked'.
            raise SystemExit(
                f"--config {args.config} declares no target grid.\n"
                f"  expected keys: {', '.join(CELL_DIMS)}\n"
                f"  found keys:    {', '.join(cfg) or '(none)'}\n"
                '  example: {"point_id": ["SZ-CBD-01"], "carrier": ["cmcc"], '
                '"time_band": ["busy", "idle"]}')
        unknown = [k for k in cfg if k not in CELL_DIMS]
        if unknown:
            print(f"⚠ --config: ignoring unknown key(s) {', '.join(unknown)} "
                  f"(target dims are {', '.join(CELL_DIMS)})", file=sys.stderr)
        return target
    t = {"point_id": _parse_list(args.points), "carrier": _parse_list(args.carriers),
         "time_band": _parse_list(args.time_bands)}
    return t if any(t.values()) else None


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB campaign coverage-completeness matrix")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--points", help="target point_ids, comma-separated")
    ap.add_argument("--carriers", help="target carriers, comma-separated")
    ap.add_argument("--time-bands", dest="time_bands", help="target time_bands, comma-separated")
    ap.add_argument("--config", help="JSON with point_id/carrier/time_band lists")
    ap.add_argument("--min-samples", type=int, default=cc.DEFAULT_MIN_SAMPLES)
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    target = _load_target(args)
    recs, files = cc.load_records(args.inputs)
    res = analyze(recs, target, args.min_samples)
    print(render_markdown(res))
    print(f"\n<!-- records={len(recs)} files={len(files)} -->", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
