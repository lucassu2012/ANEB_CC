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
    meta:  {cell_key -> homogeneity accumulator}. profile_VERSION is deliberately
           NOT part of the cell key (that would fragment every cell), so instead we
           record which versions/histogram edges landed in each cell and flag the
           ones that pooled incomparable measurements (D-32 / R-27).
    """
    cells, meta = {}, {}
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
            acc = meta.setdefault(key, cc.homogeneity_acc())
            cc.note_homogeneity(acc, scn)
            cc.note_run_homogeneity(acc, rec)
    return cells, excluded_no_tier, meta


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
    cells, excluded, meta = collect_tier_samples(records, kpi, group_by)
    results = []
    for key in sorted(cells):
        cell = dict(zip(group_by, key))
        entry = {"cell": cell, **attribute_cell(cells[key], min_samples)}
        mixed_pv, mixed_edges = cc.mixed_flags(meta.get(key))
        entry["mixed_profile_versions"] = mixed_pv
        entry["mixed_histogram_edges"] = mixed_edges
        mixed_modes, mixed_sources = cc.mixed_run_flags(meta.get(key))
        entry["mixed_modes"] = mixed_modes
        entry["mixed_profile_sources"] = mixed_sources
        entry["mixed_campaigns"] = cc.mixed_campaigns(meta.get(key))
        results.append(entry)
    return {
        "kpi": kpi,
        "group_by": list(group_by),
        "min_samples": min_samples,
        "cells": results,
        "excluded_no_tier": excluded,
        "claim_scope": "application_end_to_end_to_probe_node",
    }


# ------------------------------------------------- cross-cell segment profile

SEGMENTS = (("access_component", "接入(metro)"),
            ("regional_backbone_incr", "区域骨干+"),
            ("core_backbone_incr", "核心骨干+"))

# Flag at three robust sigmas. Latency is right-skewed, so this is a descriptive
# screen for "which cell stands out", not a significance test.
OUTLIER_K = 3.0


def segment_profile(result):
    """Per segment, how the cells compare WITH EACH OTHER.

    The matrix gives each cell's segments in isolation, but the decision it
    feeds is "fix this point or fix the backbone", and that turns on whether a
    segment is high at ONE cell or at ALL of them. A segment that is high
    everywhere is a property of the measured path — the distance to the core
    mirror, say — not a defect of any point; reporting it as that point's
    dominant segment without saying so invites exactly the wrong conclusion.

    Comparison is within this corpus only: same profiles, same method, no
    external baseline. Cells whose segment is not computable stay out of the
    comparison and are counted, never imputed (R-10).
    """
    rows = []
    for field, label in SEGMENTS:
        pairs = [(c, c[field]) for c in result["cells"] if c.get(field) is not None]
        vals = [v for _, v in pairs]
        missing = len(result["cells"]) - len(pairs)
        typical, spread = cc.median(vals), cc.mad(vals)
        row = {"segment": field, "label": label, "n_cells": len(pairs),
               "not_computable": missing, "typical": typical, "mad": spread,
               # spread relative to the typical value: "no cell exceeded the
               # screen" says nothing about how alike the cells are, and a
               # reader deciding "path property or point problem" needs both
               "rel_mad": (spread / abs(typical) * 100.0)
                          if (spread is not None and typical) else None,
               "high": None, "low": None, "uniform": None, "basis": None}
        if spread is None:
            row["basis"] = "insufficient"      # <2 comparable cells
        elif spread == 0:
            # Over half the cells share one value, so the 3-sigma threshold
            # degenerates to zero. Suppressing the comparison here would hide
            # the cleanest signal there is — one cell differing from an
            # otherwise identical set — so list what differs and say plainly
            # that the basis is "not equal to the common value", not 3 sigma.
            # A relative tolerance keeps float dust from reading as a finding.
            row["basis"] = "zero_spread"
            tol = 1e-9 * max(1.0, abs(typical))
            row["high"] = [{"cell": c["cell"], "value": v}
                           for c, v in pairs if v - typical > tol]
            row["low"] = [{"cell": c["cell"], "value": v}
                          for c, v in pairs if typical - v > tol]
            row["uniform"] = not (row["high"] or row["low"])
        else:
            thr = OUTLIER_K * cc.MAD_TO_SIGMA * spread
            row["basis"] = "mad"
            row["high"] = [{"cell": c["cell"], "value": v}
                           for c, v in pairs if v - typical > thr]
            row["low"] = [{"cell": c["cell"], "value": v}
                          for c, v in pairs if typical - v > thr]
            row["uniform"] = not (row["high"] or row["low"])
        rows.append(row)
    return {"kpi": result["kpi"], "segments": rows,
            "claim_scope": result["claim_scope"]}


def _seg_cell_label(cell):
    return "/".join(cc.md_cell(v) for v in cell.values())


def render_segment_profile_markdown(prof):
    kpi = prof["kpi"]
    lines = [
        f"## 分段异常定位（{kpi}，同一段跨单元比较，ms）",
        "",
        "> **这一段回答的是**：某一段慢，是**这个点位特有**，还是**所有点位都这样**——"
        "前者指向该点位，后者是本次测量路径的**共性**（例如到中心镜像端的物理距离），"
        "**不构成任何点位的问题**。",
        f"> **口径**：与**本语料内**同段各单元的中位数比较，稳健离差 MAD，阈值 "
        f"{cc.fmt_num(OUTLIER_K, 0)}×1.4826×MAD。这是**描述性筛查、不是显著性检验**，"
        "也**不与任何外部基准比较**；不可计算的单元不参与比较且如实计数。",
        "",
        "> **注意**：`未见单点异常` 只表示**没有单元越过筛查阈值**，"
        "**不等于各单元相同**——单元间到底有多齐，看 `离差/典型` 一列。"
        "该列小且无异常，才说得上是路径共性。",
        "",
        "| 段 | 参与单元 | 典型值(中位) | 离差(MAD) | 离差/典型 | 显著高 | 显著低 | 判读 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in prof["segments"]:
        if s["basis"] == "insufficient":
            verdict, high, low = "可比单元不足(<2)，无法比较", "—", "—"
        elif s["basis"] == "zero_spread" and s["uniform"]:
            verdict, high, low = "全部单元取值相同", "—", "—"
        elif s["basis"] == "zero_spread":
            verdict = ("过半单元取值相同，下列单元与之不同"
                       "（判据是**与共同取值不等**，不是 3σ）")
            high = "；".join(f"{_seg_cell_label(o['cell'])}({cc.fmt_num(o['value'], 1)})"
                             for o in s["high"]) or "—"
            low = "；".join(f"{_seg_cell_label(o['cell'])}({cc.fmt_num(o['value'], 1)})"
                            for o in s["low"]) or "—"
        elif s["uniform"]:
            verdict = "**未见单点异常**（3σ 筛查）→ 最大单项落在该段分布内，不宜单独归因于该单元"
            high = low = "—"
        else:
            verdict = "**存在单点异常** → 指向具体单元"
            high = "；".join(f"{_seg_cell_label(o['cell'])}({cc.fmt_num(o['value'], 1)})"
                             for o in s["high"]) or "—"
            low = "；".join(f"{_seg_cell_label(o['cell'])}({cc.fmt_num(o['value'], 1)})"
                            for o in s["low"]) or "—"
        n = f"{s['n_cells']}" + (f"（另 {s['not_computable']} 不可计算）"
                                 if s["not_computable"] else "")
        rel = f"{cc.fmt_num(s['rel_mad'], 1)}%" if s["rel_mad"] is not None else "—"
        lines.append(f"| {s['label']} | {n} | {cc.fmt_num(s['typical'], 1)} | "
                     f"{cc.fmt_num(s['mad'], 1)} | {rel} | {high} | {low} | {verdict} |")
    return "\n".join(lines)


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
        cell_label = " · ".join(f"{k}={cc.md_cell(v)}" for k, v in c["cell"].items())
        cov = ",".join(cc.TIER_LABELS.get(t, t) for t in c["coverage"]) or "—"
        notes = []
        if c["not_computable_reason"]:
            notes.append(c["not_computable_reason"])
        if c["inversions"]:
            # "/" not "|": a literal pipe inside a markdown table cell splits the
            # row into an extra column, so the table breaks exactly on the rows
            # carrying a warning — the ones most worth reading carefully
            # (D-127, found by the property tests).
            notes.append("inversion:" + "/".join(c["inversions"]))
        if c.get("mixed_profile_versions"):
            notes.append("MIXED_PROFILE_VERSION:" + "/".join(c["mixed_profile_versions"]))
        if c.get("mixed_histogram_edges"):
            notes.append("MIXED_HIST_EDGES")
        if c.get("mixed_campaigns"):
            notes.append("MIXED_CAMPAIGN:" + "/".join(c["mixed_campaigns"]))
        if c.get("mixed_modes"):
            notes.append("MIXED_MODE:" + "/".join(c["mixed_modes"]))
        if c.get("mixed_profile_sources"):
            notes.append("MIXED_PROFILE_SOURCE:" + "/".join(c["mixed_profile_sources"]))
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
