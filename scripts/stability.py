#!/usr/bin/env python3
"""ANEB repeatability / stability analysis — coefficient of variation (stdlib only).

Serves the plan's M1 acceptance「同点位复测 TTFT 变异系数 ≤10%」: for each cell
(point,carrier,time_band,profile) and KPI, compute CV% = stdev/mean*100 across the
repeats gathered there and flag cells whose CV exceeds the gate (default 10%). A
high CV means the measurement isn't repeatable there — the cell's median cannot be
trusted as a stable characterization.

Honesty (R-10): <2 samples -> CV None (not computable, not 0); |mean|≈0 -> None
(CV undefined, never a fabricated 0); `unstable` (CV>gate) is kept distinct from
`low_confidence` (n<min_samples). claim_scope unchanged.

Usage: python stability.py results/*.jsonl [--kpi t1_ttft_ms] [--cv-gate 10]
"""
import argparse
import statistics
import sys

import campaign_common as cc

DEFAULT_CV_GATE = 10.0  # percent — plan M1 acceptance「复测 CV ≤ 10%」
DEFAULT_STABILITY_KPIS = ("t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps")
# tier is IN the key: a repeat targets the same server tier, so pooling tiers would
# conflate tier-difference with measurement noise. CV here = true same-condition repeatability.
STAB_GROUP_BY = ("point_id", "carrier", "time_band", "tier", "profile_id")


def cv_percent(values):
    """Coefficient of variation (%) = sample stdev / mean * 100. None if <2 usable
    samples or |mean| too small for CV to be meaningful."""
    xs = [v for v in values if v is not None]
    if len(xs) < 2:
        return None
    m = statistics.fmean(xs)
    if abs(m) < 1e-9:
        return None
    return statistics.stdev(xs) / m * 100.0


def stability_cells(records, kpi_key, group_by=STAB_GROUP_BY,
                    cv_gate=DEFAULT_CV_GATE, min_samples=cc.DEFAULT_MIN_SAMPLES):
    buckets = {}
    for rec in records:
        labels = cc.campaign_labels(rec)
        for scn in cc.iter_scenarios(rec):
            v = cc.scenario_kpi(scn, kpi_key)
            if v is None:
                continue
            pid = scn.get("profile_id") or "?"
            key = tuple(pid if f == "profile_id" else (labels.get(f) or "unlabeled")
                        for f in group_by)
            buckets.setdefault(key, []).append(v)
    cells = []
    for key in sorted(buckets):
        vals = buckets[key]
        cv = cv_percent(vals)
        cells.append({
            "cell": dict(zip(group_by, key)), "kpi": kpi_key, "n": len(vals),
            "mean": cc.mean(vals), "median": cc.median(vals), "cv_percent": cv,
            "unstable": (cv is not None and cv > cv_gate),
            "low_confidence": len(vals) < min_samples,
        })
    return cells


# At M2 grid scale this table is (point x carrier x band x tier x profile) per KPI
# — ~290 rows each, which buried every other section in the rehearsal (D-117).
# Above the cap, STABLE rows are folded away and the omission is stated in full:
# unstable and not-computable rows are never dropped, and the CSV keeps everything.
DEFAULT_MAX_STABLE_ROWS = 25


def render_markdown(cells, kpi_key, cv_gate=DEFAULT_CV_GATE,
                    max_stable_rows=DEFAULT_MAX_STABLE_ROWS):
    lines = [f"### 复测稳定性：`{kpi_key}`（CV% = 样本 stdev/mean；门 ≤{cc.fmt_num(cv_gate)}% 为稳定）", ""]
    if not cells:
        lines.append(f"_无 `{kpi_key}` 数据。_")
        return "\n".join(lines)
    stable_ids = [id(c) for c in cells
                  if c["cv_percent"] is not None and not c["unstable"]]
    omitted = 0
    if max_stable_rows is not None and len(stable_ids) > max_stable_rows:
        keep = set(stable_ids[:max_stable_rows])
        omitted = len(stable_ids) - max_stable_rows
        cells = [c for c in cells
                 if c["cv_percent"] is None or c["unstable"] or id(c) in keep]
    lines += ["| 单元 | n | 中位 | 均值 | CV% | 稳定? | 备注 |",
              "|---|---|---|---|---|---|---|"]
    for c in cells:
        cell_label = " · ".join(f"{k}={cc.md_cell(v)}" for k, v in c["cell"].items())
        if c["cv_percent"] is None:
            stable = "—"
        else:
            stable = "稳定" if not c["unstable"] else "✗超门"
        notes = []
        if c["cv_percent"] is None:
            notes.append("CV 不可计算(n<2/mean≈0)")
        if c["low_confidence"]:
            notes.append("low_conf")
        note = "; ".join(notes) or "—"
        lines.append(
            f"| {cell_label} | {c['n']} | {cc.fmt_num(c['median'], 2)} | "
            f"{cc.fmt_num(c['mean'], 2)} | {cc.fmt_num(c['cv_percent'], 1)} | {stable} | {note} |")
    if omitted:
        lines += ["", f"> 另有 **{omitted}** 个**稳定**单元未列出（表内保留全部 ✗超门 与 "
                      f"CV 不可计算单元，以及前 {max_stable_rows} 个稳定单元）。"
                      "完整数据见 `<prefix>_stability.csv`。"]
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB repeatability/stability (CV) analysis")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--kpi", default="t1_ttft_ms")
    ap.add_argument("--cv-gate", type=float, default=DEFAULT_CV_GATE)
    ap.add_argument("--min-samples", type=int, default=cc.DEFAULT_MIN_SAMPLES)
    args = ap.parse_args(argv)
    cc.force_utf8_stdout()

    recs, files = cc.load_records(args.inputs)
    cells = stability_cells(recs, args.kpi, cv_gate=args.cv_gate, min_samples=args.min_samples)
    print(render_markdown(cells, args.kpi, args.cv_gate))
    unstable = sum(1 for c in cells if c["unstable"])
    print(f"\n<!-- records={len(recs)} cells={len(cells)} unstable={unstable} -->", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
