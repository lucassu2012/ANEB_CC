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
# conflate tier-difference with measurement noise. CV here = true same-condition
# repeatability.
#
# campaign_id is in the key for exactly the same reason (D-145). Two campaigns are
# two conditions — that is the entire premise of the before/after comparison — so
# pooling them makes CV measure the optimisation instead of the repeatability. It
# is not a blend like the heat card's, it is a wrong number: two campaigns of
# CV 0.4% and 0.26% around medians 400 and 600 pool to CV 21% and get flagged
# unstable, and the runbook then tells the operator to go resample a cell whose
# measurement was excellent.
STAB_GROUP_BY = ("campaign_id", "point_id", "carrier", "time_band", "tier", "profile_id")


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
            "stdev": cc.stdev(vals),   # absolute spread, for the sample-size plan
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


# The grid proposal sized the campaign at n=5 assuming CV≈5%, which resolves a
# ~5% difference. Field spread is whatever it is, so the assumption has to be
# checked against the first day's data while there is still time to change the
# plan — the noise scale (D-144) only tells you afterwards that the delta drowned.
DEFAULT_TARGET_EFFECT_PCT = 5.0


def plan_cells(cells, target_pct=DEFAULT_TARGET_EFFECT_PCT):
    """Per cell: what the repeats actually resolve, and how many it would take to
    resolve `target_pct`% of the cell median. Unknown spread stays None all the
    way through — 'we cannot say' must not render as 'resolves everything'."""
    out = []
    for c in cells:
        sd, n, med = c["stdev"], c["n"], c["median"]
        mde = cc.min_detectable_effect(sd, n)
        target_abs = (abs(med) * target_pct / 100.0) if med is not None else None
        req = cc.required_n(sd, target_abs)
        row = dict(c)
        row["mde"] = mde
        row["mde_pct"] = (mde / abs(med) * 100.0) if (mde is not None and med) else None
        row["target_abs"] = target_abs
        row["required_n"] = req
        row["resolves_target"] = (req <= n) if req is not None else None
        out.append(row)
    return out


def render_plan_markdown(rows, kpi_key, target_pct=DEFAULT_TARGET_EFFECT_PCT):
    lines = [f"### 采样量核算：`{kpi_key}`（目标：分辨 {cc.fmt_num(target_pct, 1)}% 的差异）", ""]
    if not rows:
        lines.append(f"_无 `{kpi_key}` 数据。_")
        return "\n".join(lines)
    lines += [
        "> **口径**：`可辨最小差异` = 以本单元实测离散度，两个同样大小的单元之间需要多大差异"
        "才会超出噪声尺度（√2·1.253·sd/√n）。它是**量级指示、不是显著性检验**（时延右偏）。"
        "`需 n≥` 是把可辨差异压到目标所需的**每侧**复测数。离散度未知（n<2）的单元一律留 `—`，"
        "**不以 0 或当前 n 顶替**。",
        "",
        "| 单元 | n | 中位 | CV% | 可辨最小差异 | 占中位 | 达标? | 需 n≥ |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        cell_label = " · ".join(f"{k}={cc.md_cell(v)}" for k, v in r["cell"].items())
        ok = "—" if r["resolves_target"] is None else ("达标" if r["resolves_target"] else "✗不足")
        lines.append(
            f"| {cell_label} | {r['n']} | {cc.fmt_num(r['median'], 2)} | "
            f"{cc.fmt_num(r['cv_percent'], 1)} | {cc.fmt_num(r['mde'], 2)} | "
            f"{cc.fmt_num(r['mde_pct'], 1)}% | {ok} | {cc.fmt_num(r['required_n'])} |")
    judged = [r for r in rows if r["resolves_target"] is not None]
    short = [r for r in judged if not r["resolves_target"]]
    unknown = len(rows) - len(judged)
    lines.append("")
    if not judged:
        lines.append(f"> **结论**：{len(rows)} 个单元离散度均不可估（n<2），"
                     "**无法核算采样量**——先补足复测再核算。")
    else:
        need = cc.median([r["required_n"] for r in short]) if short else None
        verdict = (f"> **结论**：{len(short)}/{len(judged)} 个单元在当前 n 下分辨不了 "
                   f"{cc.fmt_num(target_pct, 1)}% 的差异")
        verdict += (f"；这些单元的建议复测数中位为 **n≥{cc.fmt_num(need)}**（每侧）。"
                    if need is not None else "。")
        if unknown:
            verdict += f" 另有 {unknown} 个单元离散度不可估，**未计入**。"
        lines.append(verdict)
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB repeatability/stability (CV) analysis")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--kpi", default="t1_ttft_ms")
    ap.add_argument("--cv-gate", type=float, default=DEFAULT_CV_GATE)
    ap.add_argument("--min-samples", type=int, default=cc.DEFAULT_MIN_SAMPLES)
    # The row cap exists because this section would otherwise dominate the
    # comprehensive report (D-117). Someone who ran THIS tool came to look at
    # stability, so the standalone default is uncapped (D-130).
    ap.add_argument("--max-stable-rows", type=int, default=0,
                    help="fold away all but N stable rows (0 = show everything; "
                         f"the comprehensive report uses {DEFAULT_MAX_STABLE_ROWS})")
    ap.add_argument("--plan", nargs="?", type=float, const=DEFAULT_TARGET_EFFECT_PCT,
                    default=None, metavar="PCT",
                    help="sample-size check instead of the CV table: what the "
                         "repeats resolve, and how many are needed to resolve "
                         f"PCT%% of the cell median (default {DEFAULT_TARGET_EFFECT_PCT})")
    args = ap.parse_args(argv)
    cc.force_utf8_stdout()

    recs, files = cc.load_records(args.inputs)
    cells = stability_cells(recs, args.kpi, cv_gate=args.cv_gate, min_samples=args.min_samples)
    if args.plan is not None:
        if args.plan <= 0:
            print("--plan 的目标差异须为正数（它是要分辨的差异占中位的百分比）", file=sys.stderr)
            return 2
        print(render_plan_markdown(plan_cells(cells, args.plan), args.kpi, args.plan))
    else:
        print(render_markdown(cells, args.kpi, args.cv_gate,
                              max_stable_rows=args.max_stable_rows or None))
    unstable = sum(1 for c in cells if c["unstable"])
    print(f"\n<!-- records={len(recs)} cells={len(cells)} unstable={unstable} -->", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
