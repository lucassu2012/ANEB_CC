#!/usr/bin/env python3
"""ANEB order-effect / carryover diagnostic (stdlib only).

The result contract captures `run.scenario_order` and `scenarios[].order_index`
explicitly as 拉丁方(Latin-square) counterbalancing EVIDENCE — but evidence only
counts if something checks it. This module is that check.

Question answered: does a profile's KPI depend systematically on WHERE it ran in
the sequence (1st vs 3rd)? Counterbalancing is supposed to cancel warm-up,
thermal, cache and carryover effects; if a residual position dependence survives,
every aggregated median in the campaign report carries that bias.

Method (per profile_id, per KPI):
    position_median[i] = median(KPI over all scenarios with order_index == i)
    spread     = max(position_median) - min(position_median)
    spread_pct = spread / median(all values) * 100
    order_effect_suspected = spread_pct > threshold (default 10%, matching the
                             M1 CV≤10% repeatability convention)

A NULL result is the good result: no suspected effect = counterbalancing worked.

Honesty (R-10): <2 distinct positions -> not computable (never "no effect");
positions below the sample floor -> low_confidence; an overall median of ~0 makes
spread_pct undefined rather than infinite. Separately reports ROTATION coverage:
if every run used the SAME scenario_order, the Latin square was never rotated and
counterbalancing is absent by construction — a finding in its own right.

Usage:
    python order_effect.py results/*.jsonl [--kpi t1_ttft_ms] [--threshold-pct 10]
"""
import argparse
import sys
from collections import Counter, defaultdict

import campaign_common as cc

DEFAULT_KPI = "t1_ttft_ms"
DEFAULT_THRESHOLD_PCT = 10.0
# KPIs where a position dependence would meaningfully bias the campaign medians.
ORDER_SENSITIVE_KPIS = ("t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps")


def collect_positions(records, kpi):
    """{profile_id -> {order_index -> [values]}} plus scenario_order counts."""
    cells = defaultdict(lambda: defaultdict(list))
    orders = Counter()
    for rec in records:
        order = cc.run_obj(rec).get("scenario_order")
        orders[order if isinstance(order, str) and order else "absent"] += 1
        for scn in cc.iter_scenarios(rec):
            idx = cc.scenario_order_index(scn)
            val = cc.scenario_kpi(scn, kpi)
            if idx is None or val is None:
                continue
            cells[scn.get("profile_id") or "?"][idx].append(val)
    return cells, orders


def analyze_profile(positions, min_samples=cc.DEFAULT_MIN_SAMPLES,
                    threshold_pct=DEFAULT_THRESHOLD_PCT):
    """Order-effect verdict for one profile. `positions`: {order_index -> [values]}."""
    pos = {}
    all_values = []
    for idx in sorted(positions):
        vals = positions[idx]
        if not vals:
            continue
        pos[idx] = {"median": cc.median(vals), "n": len(vals),
                    "low_confidence": len(vals) < min_samples}
        all_values.extend(vals)

    if len(pos) < 2:
        return {"positions": pos, "spread": None, "spread_pct": None,
                "overall_median": cc.median(all_values) if all_values else None,
                "order_effect_suspected": None, "low_confidence": True,
                "not_computable_reason": "NEED_2_POSITIONS"}

    medians = [p["median"] for p in pos.values()]
    spread = max(medians) - min(medians)
    overall = cc.median(all_values)
    # A near-zero overall median makes a percentage meaningless, not infinite.
    spread_pct = ((spread / abs(overall) * 100.0)
                  if overall is not None and abs(overall) > 1e-9 else None)
    return {
        "positions": pos,
        "spread": spread,
        "spread_pct": spread_pct,
        "overall_median": overall,
        "order_effect_suspected": (spread_pct > threshold_pct) if spread_pct is not None else None,
        "low_confidence": any(p["low_confidence"] for p in pos.values()),
        "not_computable_reason": None if spread_pct is not None else "MEDIAN_NEAR_ZERO",
    }


def analyze(records, kpi=DEFAULT_KPI, min_samples=cc.DEFAULT_MIN_SAMPLES,
            threshold_pct=DEFAULT_THRESHOLD_PCT):
    cells, orders = collect_positions(records, kpi)
    profiles = []
    for pid in sorted(cells):
        profiles.append({"profile_id": pid,
                         **analyze_profile(cells[pid], min_samples, threshold_pct)})
    distinct = len([k for k in orders if k != "absent"])
    return {
        "kpi": kpi,
        "threshold_pct": threshold_pct,
        "min_samples": min_samples,
        "profiles": profiles,
        "scenario_orders": dict(orders),
        "distinct_orders": distinct,
        # One order across the whole corpus = the Latin square was never rotated.
        "rotation_warning": distinct == 1,
        "no_order_evidence": distinct == 0,
    }


def render_markdown(res):
    lines = [
        f"## 序位效应诊断（{res['kpi']}；拉丁方反平衡是否奏效）",
        "",
        f"> 判据：同 profile 各**执行位次**的中位数极差 / 总体中位数 > {res['threshold_pct']}% "
        "即疑似残留序位偏倚（无效应=好结果）。",
        "",
    ]
    if res["no_order_evidence"]:
        lines.append("> ⚠ 语料无 `run.scenario_order` 证据，无法判断是否做过反平衡。")
        lines.append("")
    elif res["rotation_warning"]:
        lines.append("> ⚠ 全部记录使用**同一** `scenario_order`——拉丁方未轮转，"
                     "反平衡在构造上不成立，位次差无法与场景差分离。")
        lines.append("")

    if not res["profiles"]:
        lines.append("_无可诊断样本（记录缺 order_index 或该 KPI）。_")
        return "\n".join(lines)

    lines += ["| profile | 位次中位数 | 极差 | 极差% | 总体中位 | 判定 | 备注 |",
              "|---|---|---|---|---|---|---|"]
    for p in res["profiles"]:
        pos_txt = " / ".join(f"#{i}:{cc.fmt_num(v['median'])}(n={v['n']})"
                             for i, v in sorted(p["positions"].items())) or "—"
        if p["order_effect_suspected"] is None:
            verdict = "不可计算"
        elif p["order_effect_suspected"]:
            verdict = "**疑似序位偏倚**"
        else:
            verdict = "无明显效应"
        notes = []
        if p["not_computable_reason"]:
            notes.append(p["not_computable_reason"])
        if p["low_confidence"]:
            notes.append("low_conf")
        lines.append(
            f"| {p['profile_id']} | {pos_txt} | {cc.fmt_num(p['spread'])} | "
            f"{cc.fmt_num(p['spread_pct'])} | {cc.fmt_num(p['overall_median'])} | "
            f"{verdict} | {'; '.join(notes) or '—'} |")
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB order-effect / carryover diagnostic")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--kpi", default=DEFAULT_KPI)
    ap.add_argument("--threshold-pct", type=float, default=DEFAULT_THRESHOLD_PCT)
    ap.add_argument("--min-samples", type=int, default=cc.DEFAULT_MIN_SAMPLES)
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    recs, files = cc.load_records(args.inputs)
    res = analyze(recs, args.kpi, args.min_samples, args.threshold_pct)
    print(render_markdown(res))
    print(f"\n<!-- records={len(recs)} files={len(files)} -->", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
