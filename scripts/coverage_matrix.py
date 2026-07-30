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
import sys
from collections import defaultdict

import campaign_common as cc

CELL_DIMS = ("point_id", "carrier", "time_band")
_DIM_FLAG = {"point_id": "--points", "carrier": "--carriers", "time_band": "--time-bands"}


def observed_cells(records):
    """{(point,carrier,time_band) -> usable-record count} (usable = has AQS)."""
    counts = defaultdict(int)
    for rec in records:
        if cc.run_aqs(rec) is None:
            continue
        labels = cc.campaign_labels(rec)
        counts[tuple(labels[d] for d in CELL_DIMS)] += 1
    return counts


def repeat_spread(records):
    """{cell -> (distinct run.repeat_index, records whose index is missing)}.

    D3 asks for 11 REPEATS per cell; this matrix counted RECORDS. Twelve records
    that are three repeats re-run four times read as COVERED, identically to
    twelve distinct ones — measured, not argued. run_id de-duplication cannot
    see it either: a crash-and-retry writes a NEW run_id carrying the SAME
    repeat_index (D-340).

    Same usable-record filter as observed_cells, word for word, or the two
    numbers on one row would not be comparable. A missing index counts as
    unknown, never as one more repeat (R-10).
    """
    seen, unknown = defaultdict(set), defaultdict(int)
    for rec in records:
        if cc.run_aqs(rec) is None:
            continue
        key = tuple(cc.campaign_labels(rec)[d] for d in CELL_DIMS)
        ri = cc.run_obj(rec).get("repeat_index")
        if isinstance(ri, int) and not isinstance(ri, bool):
            seen[key].add(ri)
        else:
            unknown[key] += 1
    return {k: (len(seen.get(k) or ()), unknown.get(k, 0))
            for k in set(seen) | set(unknown)}


def analyze(records, target=None, min_samples=cc.DEFAULT_MIN_SAMPLES):
    """target: {'point_id':[...], 'carrier':[...], 'time_band':[...]} or None."""
    observed = observed_cells(records)
    spread = repeat_spread(records)

    if not target or not all(target.get(d) for d in CELL_DIMS):
        # Descriptive mode: no target grid — report what was observed, no invention.
        cells = [{"cell": dict(zip(CELL_DIMS, k)), "samples": observed[k],
                  "distinct_repeats": spread.get(k, (0, 0))[0],
                  "repeats_unknown": spread.get(k, (0, 0))[1],
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
        d_rep, u_rep = spread.get(key, (0, 0))
        cells.append({"cell": dict(zip(CELL_DIMS, key)), "samples": n,
                      "distinct_repeats": d_rep, "repeats_unknown": u_rep,
                      "status": status})
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

    # 「不同重复」 beside 「样本」: D3 asks for 11 REPEATS and this table counted
    # RECORDS, so twelve records that are three repeats re-run four times read
    # exactly like twelve distinct ones (D-340).
    lines += ["| 点位 | 运营商 | 时段 | 样本 | 不同重复 | 状态 |",
              "|---|---|---|---|---|---|"]
    for c in res["cells"]:
        cl = {k: cc.md_cell(v) for k, v in c["cell"].items()}   # labels are human-typed
        d_rep, u_rep = c.get("distinct_repeats"), c.get("repeats_unknown")
        # None is not zero on any surface — the guard that exists to stop that
        # caught this column the moment it was written (R-10)
        rep = (cc.fmt_num(None, 0) if d_rep is None else f"{d_rep}") \
            + (f"(+{u_rep} 无编号)" if u_rep else "")
        # a record with no repeat_index is not a repeat we can vouch for, so it
        # is never folded into the distinct count — but it still counts toward
        # `samples`, which is why the reuse test allows for it. And when the
        # sample count is not a number, reuse is not judgeable: say nothing
        # rather than compare against a stand-in zero.
        if (isinstance(c.get("samples"), int) and d_rep is not None
                and c["samples"] > d_rep + (u_rep or 0)):
            rep += " **REPEATS_REUSED**"
        lines.append(f"| {cl['point_id']} | {cl['carrier']} | {cl['time_band']} | "
                     f"{c['samples']} | {rep} | "
                     f"{_STATUS_LABEL.get(c['status'], c['status'])} |")
    if res["off_plan"]:
        lines += ["", "### 计划外已测单元（不在目标网格；疑似误标或未规划点位）", "",
                  "| 点位 | 运营商 | 时段 | 样本 |", "|---|---|---|---|"]
        for c in res["off_plan"]:
            cl = {k: cc.md_cell(v) for k, v in c["cell"].items()}   # labels are human-typed
            lines.append(f"| {cl['point_id']} | {cl['carrier']} | {cl['time_band']} | "
                         f"{c['samples']} |")
    return "\n".join(lines)


def _parse_list(s):
    return [t.strip() for t in s.split(",") if t.strip()] if s else []


def _load_target(args):
    # analyze() needs EVERY dim populated — a grid is their product, so one empty
    # dim makes it empty. The guards below therefore test all(), not any(): a
    # partly-filled target still degrades to descriptive mode, whose banner then
    # tells someone who DID declare a grid that no grid was declared. One plural
    # typo on one key is enough to get there. 'cannot check' must never look like
    # 'checked' — and must never look like 'checking'.
    if args.config:
        cfg = cc.load_operator_json(
            args.config,
            '{"point_id": ["SZ-CBD-01"], "carrier": ["cmcc"], '
            '"time_band": ["busy", "idle"]}')
        target = {d: cfg.get(d) or [] for d in CELL_DIMS}
        empty = [d for d in CELL_DIMS if not target[d]]
        if empty:
            raise SystemExit(
                f"--config {args.config} declares no values for: {', '.join(empty)}.\n"
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
    if not any(t.values()):
        return None                    # nothing asked for — descriptive mode IS the answer
    missing = [_DIM_FLAG[d] for d in CELL_DIMS if not t[d]]
    if missing:
        raise SystemExit(
            f"target grid is incomplete — missing {', '.join(missing)}.\n"
            "  all three dims are required (the grid is their product);\n"
            "  omit all three to get descriptive mode instead.")
    return t


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
