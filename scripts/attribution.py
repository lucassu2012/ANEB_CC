#!/usr/bin/env python3
"""ANEB three-tier differential latency attribution (stdlib only).

Decomposes application-layer path latency into ACCESS / REGIONAL-BACKBONE /
CORE-BACKBONE segments by differencing the same network KPI measured against
three mirrored server tiers (metro/同城, regional/区域, core/中心) under the
SAME client + access network + time band (铁律 3: client-side differencing
cancels the common-mode access component, netting the backbone increments).

Methodology (docs/CAMPAIGN_LABELS_CONVENTION.md §3):
    access_component       = median(KPI_metro)                         # 接入路径地板
    regional_backbone_incr = median(KPI_regional) - median(KPI_metro)  # 区域骨干增量
    core_backbone_incr     = median(KPI_core)     - median(KPI_regional)# 核心骨干增量
    (access + regional_incr + core_incr telescopes to median(KPI_core))

Honesty (R-10): a missing tier -> that increment is None (not extrapolated);
negative increments are reported as `inversion` (routing/anycast/CDN edge closer
than the nominal tier, or noise) and NEVER clamped to 0; a tier with < min_samples
is flagged low_confidence. claim_scope stays application_end_to_end_to_probe_node.

Usage:
    python attribution.py results/*.jsonl [--kpi n1_rtt_p50_ms|t1_ttft_ms]
"""
import argparse
import sys

import campaign_common as cc

# KPIs meaningful for path attribution (network round-trip / first-byte latency).
ATTRIBUTABLE_KPIS = ("n1_rtt_p50_ms", "t1_ttft_ms")
DEFAULT_KPI = "n1_rtt_p50_ms"
DEFAULT_GROUP_BY = ("point_id", "carrier", "time_band", "profile_id")


def _cell_key(labels, profile_id, group_by):
    parts = []
    for field in group_by:
        parts.append(profile_id if field == "profile_id" else labels.get(field, "unlabeled"))
    return tuple(parts)


def collect_tier_samples(records, kpi=DEFAULT_KPI, group_by=DEFAULT_GROUP_BY):
    """Group KPI samples by (cell, tier). Returns (cells, excluded_no_tier).

    cells: {cell_key(tuple) -> {tier -> [values]}}
    excluded_no_tier: count of records with no usable tier label (coverage gap).
    """
    cells = {}
    excluded_no_tier = 0
    for rec in records:
        labels = cc.campaign_labels(rec)
        tier = labels["tier"]
        if tier is None:
            excluded_no_tier += 1
            continue
        for scn in cc.iter_scenarios(rec):
            val = cc.scenario_kpi(scn, kpi)
            if val is None:
                continue
            pid = scn.get("profile_id") or "?"
            key = _cell_key(labels, pid, group_by)
            cells.setdefault(key, {}).setdefault(tier, []).append(val)
    return cells, excluded_no_tier


def attribute_cell(tier_samples, min_samples=cc.DEFAULT_MIN_SAMPLES):
    """Differential attribution for one cell. `tier_samples`: {tier -> [values]}."""
    tiers = {}
    for tier in cc.TIERS:
        vals = tier_samples.get(tier) or []
        if vals:
            tiers[tier] = {
                "median": cc.median(vals),
                "n": len(vals),
                "low_confidence": len(vals) < min_samples,
            }

    def med(t):
        return tiers[t]["median"] if t in tiers else None

    metro, regional, core = med("metro"), med("regional"), med("core")

    def incr(hi, lo):
        return (hi - lo) if (hi is not None and lo is not None) else None

    regional_incr = incr(regional, metro)
    core_incr = incr(core, regional)

    inversions = []
    if regional_incr is not None and regional_incr < 0:
        inversions.append("regional<metro")
    if core_incr is not None and core_incr < 0:
        inversions.append("core<regional")

    coverage = [t for t in cc.TIERS if t in tiers]
    missing = [t for t in cc.TIERS if t not in tiers]
    reason = ("TIER_MISSING:" + ",".join(missing)) if missing else None
    low_conf = any(tiers[t]["low_confidence"] for t in tiers)

    return {
        "tiers": tiers,
        "access_component": metro,
        "regional_backbone_incr": regional_incr,
        "core_backbone_incr": core_incr,
        "end_to_end_core": core,          # telescoped total (access+regional+core incr)
        "inversions": inversions,
        "coverage": coverage,
        "low_confidence": low_conf,
        "not_computable_reason": reason,
    }


def attribute(records, kpi=DEFAULT_KPI, group_by=DEFAULT_GROUP_BY,
              min_samples=cc.DEFAULT_MIN_SAMPLES):
    """Full attribution over a record set. Returns a dict with per-cell results
    and coverage metadata."""
    cells, excluded = collect_tier_samples(records, kpi, group_by)
    results = []
    for key in sorted(cells):
        cell = dict(zip(group_by, key))
        results.append({"cell": cell, **attribute_cell(cells[key], min_samples)})
    return {
        "kpi": kpi,
        "group_by": list(group_by),
        "min_samples": min_samples,
        "cells": results,
        "excluded_no_tier": excluded,
        "claim_scope": "application_end_to_end_to_probe_node",
    }


# ---------------------------------------------------------------- rendering

def render_markdown(result):
    kpi = result["kpi"]
    lines = [
        f"## 三级差分归因矩阵（{kpi}，单位 ms）",
        "",
        f"> claim_scope: `{result['claim_scope']}` — 应用层路径分段，非无线层/运营商全网评级。",
        "> 方法：铁律 3 客户端差分消共模；缺层记 coverage 不外推；负增量记 inversion 不清零。",
        "",
    ]
    if result["excluded_no_tier"]:
        lines.append(f"> ⚠ coverage：{result['excluded_no_tier']} 条记录无 tier 标签，未进归因。")
        lines.append("")
    if not result["cells"]:
        lines.append("_无可归因单元（记录均缺 tier 标签或缺该 KPI）。_")
        return "\n".join(lines)

    header = ("| 单元 | 覆盖层级 | 接入(metro) | 区域骨干+ | 核心骨干+ | "
              "端到端(core) | 备注 |")
    sep = "|---|---|---|---|---|---|---|"
    lines += [header, sep]
    for c in result["cells"]:
        cell_label = " · ".join(f"{k}={v}" for k, v in c["cell"].items())
        cov = ",".join(cc.TIER_LABELS.get(t, t) for t in c["coverage"]) or "—"
        notes = []
        if c["not_computable_reason"]:
            notes.append(c["not_computable_reason"])
        if c["inversions"]:
            notes.append("inversion:" + "|".join(c["inversions"]))
        if c["low_confidence"]:
            notes.append("low_conf")
        note = "; ".join(notes) or "—"
        lines.append(
            f"| {cell_label} | {cov} | {cc.fmt_num(c['access_component'])} | "
            f"{cc.fmt_num(c['regional_backbone_incr'])} | {cc.fmt_num(c['core_backbone_incr'])} | "
            f"{cc.fmt_num(c['end_to_end_core'])} | {note} |"
        )
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB three-tier differential attribution")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--kpi", default=DEFAULT_KPI, choices=ATTRIBUTABLE_KPIS)
    ap.add_argument("--min-samples", type=int, default=cc.DEFAULT_MIN_SAMPLES)
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    recs, files = cc.load_records(args.inputs)
    result = attribute(recs, kpi=args.kpi, min_samples=args.min_samples)
    print(render_markdown(result))
    print(f"\n<!-- records={len(recs)} files={len(files)} cells={len(result['cells'])} -->",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
