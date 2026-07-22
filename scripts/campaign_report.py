#!/usr/bin/env python3
"""ANEB campaign-level comprehensive report generator (stdlib only).

The M2 deliverable《城市 AI 业务网络体验热力卡与归因报告》/ standing-goal
"1000+样本综合报告" — assembled from the results JSONL corpus:

  1. 覆盖盘点 (inventory & coverage of campaign labels)
  2. 点位×忙闲×运营商 热力卡 (AQS median + four-level grade per cell)
  3. 三级(同城/区域/中心)差分归因矩阵 (delegates to attribution.py)
  4. 优化前后对比 (before/after campaign delta, when two campaigns present)

Emits a comprehensive markdown report and, optionally, a self-contained HTML
report (inline CSS, no external deps — same discipline as dashboard.py).

Grouping labels come from the OPTIONAL run.campaign block (graceful degradation to
"unlabeled"/"unknown"); see docs/CAMPAIGN_LABELS_CONVENTION.md. R-10: cells below
the sample floor are flagged low_confidence — never hidden, never zero-filled.

Usage:
    python campaign_report.py results/*.jsonl [--html report.html]
                                              [--before ID --after ID]
                                              [--attr-kpi n1_rtt_p50_ms]
"""
import argparse
import csv
import html
import sys
from collections import Counter, defaultdict

import campaign_common as cc
import attribution
import order_effect
import provenance as prov_mod
import stability
import subscore_rollup
import trend
import validity_rollup

HEAT_DIMS = ("point_id", "carrier", "time_band")


def esc(s):
    return html.escape(str(s))


# ---------------------------------------------------------------- inventory

def inventory(records):
    inv = {
        "records": len(records),
        "with_campaign": 0,
        "campaigns": Counter(), "points": Counter(),
        "carriers": Counter(), "time_bands": Counter(), "tiers": Counter(),
        "aqs_present": 0,
    }
    for rec in records:
        labels = cc.campaign_labels(rec)
        has_campaign = bool(cc.run_obj(rec).get("campaign"))
        inv["with_campaign"] += int(has_campaign)
        inv["campaigns"][labels["campaign_id"]] += 1
        inv["points"][labels["point_id"]] += 1
        inv["carriers"][labels["carrier"]] += 1
        inv["time_bands"][labels["time_band"]] += 1
        inv["tiers"][labels["tier"] or "unknown"] += 1
        if cc.run_aqs(rec) is not None:
            inv["aqs_present"] += 1
    return inv


# ---------------------------------------------------------------- heat card

def heat_cells(records, min_samples=cc.DEFAULT_MIN_SAMPLES, campaign_id=None):
    """AQS by (point_id, carrier, time_band). Returns sorted list of cell dicts.
    Optional campaign_id filter (for before/after)."""
    buckets = defaultdict(list)
    for rec in records:
        labels = cc.campaign_labels(rec)
        if campaign_id is not None and labels["campaign_id"] != campaign_id:
            continue
        aqs = cc.run_aqs(rec)
        if aqs is None:
            continue
        key = tuple(labels[d] for d in HEAT_DIMS)
        buckets[key].append(aqs)
    cells = []
    for key in sorted(buckets):
        vals = buckets[key]
        med = cc.median(vals)
        cells.append({
            "cell": dict(zip(HEAT_DIMS, key)),
            "aqs_median": med,
            "grade": cc.aqs_grade(med),
            "n": len(vals),
            "low_confidence": len(vals) < min_samples,
        })
    return cells


def render_heatcard_markdown(cells):
    lines = ["## 点位 × 忙闲 × 运营商 热力卡（AQS 中位）", ""]
    if not cells:
        lines.append("_无 AQS 数据可成卡（记录缺 run.aqs.score）。_")
        return "\n".join(lines)
    lines += [
        "| 点位 | 运营商 | 时段 | AQS中位 | 分级 | n | 备注 |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in cells:
        note = "low_conf" if c["low_confidence"] else "—"
        lines.append(
            f"| {c['cell']['point_id']} | {c['cell']['carrier']} | {c['cell']['time_band']} | "
            f"{cc.fmt_num(c['aqs_median'])} | {c['grade']} | {c['n']} | {note} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------- before/after

def compare_campaigns(records, before_id, after_id, min_samples=cc.DEFAULT_MIN_SAMPLES):
    """Per-cell AQS delta (after - before) keyed by (point,carrier,time_band)."""
    before = {tuple(c["cell"].values()): c for c in heat_cells(records, min_samples, before_id)}
    after = {tuple(c["cell"].values()): c for c in heat_cells(records, min_samples, after_id)}
    rows = []
    for key in sorted(set(before) | set(after)):
        b, a = before.get(key), after.get(key)
        bm = b["aqs_median"] if b else None
        am = a["aqs_median"] if a else None
        delta = (am - bm) if (bm is not None and am is not None) else None
        rows.append({
            "cell": dict(zip(HEAT_DIMS, key)),
            "before": bm, "after": am, "delta": delta,
            "low_confidence": bool((b and b["low_confidence"]) or (a and a["low_confidence"])
                                   or b is None or a is None),
        })
    return {"before_id": before_id, "after_id": after_id, "rows": rows}


def render_comparison_markdown(cmp):
    lines = [f"## 优化前后对比（before=`{cmp['before_id']}` → after=`{cmp['after_id']}`，AQS 中位）", ""]
    if not cmp["rows"]:
        lines.append("_两战役无共同单元可比。_")
        return "\n".join(lines)
    lines += [
        "| 点位 | 运营商 | 时段 | before | after | Δ | 备注 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in cmp["rows"]:
        d = r["delta"]
        arrow = ""
        if d is not None:
            arrow = " ↑" if d > 0 else (" ↓" if d < 0 else " =")
        notes = []
        if r["before"] is None:
            notes.append("仅 after")
        if r["after"] is None:
            notes.append("仅 before")
        if r["low_confidence"]:
            notes.append("low_conf")
        note = "; ".join(notes) or "—"
        lines.append(
            f"| {r['cell']['point_id']} | {r['cell']['carrier']} | {r['cell']['time_band']} | "
            f"{cc.fmt_num(r['before'])} | {cc.fmt_num(r['after'])} | "
            f"{cc.fmt_num(d)}{arrow} | {note} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------- per-KPI heat

# Default KPIs for per-KPI heat cards: first-byte, RTT, goodput, inter-token.
DEFAULT_KPI_HEAT = ("t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps", "t2_itl_p95_ms")


def kpi_grade_field(kpi_key):
    """Authoritative per-KPI grade field name (KpiGrading, e.g. n1_rtt_p50_ms -> n1_grade)."""
    return kpi_key.split("_")[0] + "_grade"


def kpi_heat_cells(records, kpi_key, min_samples=cc.DEFAULT_MIN_SAMPLES):
    """Heat cells for one raw KPI: median value + modal AUTHORITATIVE grade (from the
    record's *_grade field, not the AQS presentation bands) per (point,carrier,time_band)."""
    gfield = kpi_grade_field(kpi_key)
    buckets = defaultdict(lambda: {"vals": [], "grades": Counter()})
    for rec in records:
        labels = cc.campaign_labels(rec)
        key = tuple(labels[d] for d in HEAT_DIMS)
        for scn in cc.iter_scenarios(rec):
            v = cc.scenario_kpi(scn, kpi_key)
            if v is None:
                continue
            buckets[key]["vals"].append(v)
            g = (scn.get("kpi") or scn.get("kpis") or {}).get(gfield)
            if isinstance(g, str):
                buckets[key]["grades"][g] += 1
    cells = []
    for key in sorted(buckets):
        b = buckets[key]
        modal = b["grades"].most_common(1)[0][0] if b["grades"] else None
        cells.append({
            "cell": dict(zip(HEAT_DIMS, key)), "kpi": kpi_key,
            "median": cc.median(b["vals"]), "grade": modal, "n": len(b["vals"]),
            "low_confidence": len(b["vals"]) < min_samples,
        })
    return cells


def render_kpi_heatcard_markdown(cells, kpi_key):
    lines = [f"### 分 KPI 热力卡：`{kpi_key}`（中位；分级=上报 KpiGrading 众数）", ""]
    if not cells:
        lines.append(f"_无 `{kpi_key}` 数据。_")
        return "\n".join(lines)
    lines += ["| 点位 | 运营商 | 时段 | 中位 | 分级 | n | 备注 |",
              "|---|---|---|---|---|---|---|"]
    for c in cells:
        note = "low_conf" if c["low_confidence"] else "—"
        lines.append(
            f"| {c['cell']['point_id']} | {c['cell']['carrier']} | {c['cell']['time_band']} | "
            f"{cc.fmt_num(c['median'], 2)} | {c['grade'] or '—'} | {c['n']} | {note} |")
    return "\n".join(lines)


# ---------------------------------------------------------------- assembly

def _auto_compare_ids(inv):
    """If exactly two labeled campaigns exist, return (before, after) by name sort."""
    labeled = sorted(c for c in inv["campaigns"] if c != "unlabeled")
    return (labeled[0], labeled[1]) if len(labeled) == 2 else (None, None)


def build_report_markdown(records, min_samples=cc.DEFAULT_MIN_SAMPLES,
                          attr_kpi=attribution.DEFAULT_KPI,
                          before_id=None, after_id=None, kpi_heat=DEFAULT_KPI_HEAT,
                          provenance=None):
    inv = inventory(records)
    cells = heat_cells(records, min_samples)

    if before_id is None and after_id is None:
        before_id, after_id = _auto_compare_ids(inv)

    parts = [
        "# ANEB 战役级综合报告",
        "",
        "> claim_scope: `application_end_to_end_to_probe_node` — 应用层端到指定节点路径；"
        "**不表述为** MOS / 无线层评级 / 运营商全网 SLA。",
        f"> 输入记录：{inv['records']}；含 run.aqs：{inv['aqs_present']}；"
        f"含 campaign 标签：{inv['with_campaign']}。样本地板 min_samples={min_samples}。",
        "",
        "## 覆盖盘点",
        "",
        f"- 战役 campaign_id：{dict(inv['campaigns'])}",
        f"- 点位 point_id：{dict(inv['points'])}",
        f"- 运营商 carrier：{dict(inv['carriers'])}",
        f"- 时段 time_band：{dict(inv['time_bands'])}",
        f"- 服务层级 tier：{dict(inv['tiers'])}",
        "",
    ]
    # Optional chain-of-custody block. Omitted (None) keeps the body deterministic
    # for the regression snapshot; the CLI injects a real manifest.
    if provenance is not None:
        parts.append(prov_mod.render_markdown(provenance))
        parts.append("")
    if inv["with_campaign"] == 0:
        parts.append("> ⚠ 全部记录无 `run.campaign` 标签——热力卡/归因/前后对比塌缩为单格 "
                     "`unlabeled`。接线见 docs/CAMPAIGN_LABELS_CONVENTION.md §4。")
        parts.append("")
    parts.append(render_heatcard_markdown(cells))
    parts.append("")
    parts.append("## 分 KPI 热力卡（原始 KPI 中位 + 上报 KpiGrading 分级）")
    parts.append("")
    any_kpi = False
    for k in kpi_heat:
        kc = kpi_heat_cells(records, k, min_samples)
        if kc:
            any_kpi = True
            parts.append(render_kpi_heatcard_markdown(kc, k))
            parts.append("")
    if not any_kpi:
        parts.append("_无场景 KPI 数据。_")
        parts.append("")
    parts.append(f"## 复测稳定性（CV 门 ≤{cc.fmt_num(stability.DEFAULT_CV_GATE)}%，对齐 M1 验收）")
    parts.append("")
    any_stab = False
    for k in stability.DEFAULT_STABILITY_KPIS:
        sc = stability.stability_cells(records, k, cv_gate=stability.DEFAULT_CV_GATE,
                                       min_samples=min_samples)
        if sc:
            any_stab = True
            parts.append(stability.render_markdown(sc, k))
            parts.append("")
    if not any_stab:
        parts.append("_无场景 KPI 数据。_")
        parts.append("")
    # Measurement-validity check on the medians above: did Latin-square
    # counterbalancing actually cancel execution-position bias? (D-95)
    any_order = False
    for k in order_effect.ORDER_SENSITIVE_KPIS:
        res = order_effect.analyze(records, kpi=k, min_samples=min_samples)
        if res["profiles"]:
            any_order = True
            parts.append(order_effect.render_markdown(res))
            parts.append("")
    if not any_order:
        parts.append("## 序位效应诊断")
        parts.append("")
        parts.append("_无 `order_index` 证据，无法校验反平衡是否奏效。_")
        parts.append("")
    # The denominator behind every median above: how many attempts were made,
    # and where the dropped (INVALID, null-KPI) ones went. (D-96)
    parts.append(validity_rollup.render_markdown(validity_rollup.analyze(records)))
    parts.append("")
    for k in attribution.ATTRIBUTABLE_KPIS:
        attr = attribution.attribute(records, kpi=k, min_samples=min_samples)
        if k == attr_kpi or attr["cells"]:  # primary always; secondary only if it has cells
            parts.append(attribution.render_markdown(attr))
            parts.append("")
    # Score-side complement to the latency attribution: which AQS dimension drags. (D-100)
    parts.append(subscore_rollup.render_markdown(subscore_rollup.analyze(records, min_samples)))
    parts.append("")
    if before_id and after_id:
        parts.append(render_comparison_markdown(
            compare_campaigns(records, before_id, after_id, min_samples)))
        parts.append("")
    # 3+ labeled campaigns: before/after can't express a trajectory — add one. (D-98)
    labeled = [c for c in inv["campaigns"] if c != "unlabeled"]
    if len(labeled) >= 3:
        parts.append(trend.render_markdown(trend.analyze(records, min_samples=min_samples)))
        parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------- HTML

def _heat_grid_html(cells, value_key="aqs_median"):
    """Pivot: rows = point_id × carrier, cols = time_band, colored by grade.
    value_key selects the numeric shown (aqs_median for the AQS card, median for
    per-KPI cards)."""
    if not cells:
        return "<p class='empty'>无数据可成卡。</p>"
    time_bands = sorted({c["cell"]["time_band"] for c in cells})
    rows = defaultdict(dict)  # (point,carrier) -> time_band -> cell
    for c in cells:
        rows[(c["cell"]["point_id"], c["cell"]["carrier"])][c["cell"]["time_band"]] = c
    head = "<tr><th>点位</th><th>运营商</th>" + "".join(f"<th>{esc(t)}</th>" for t in time_bands) + "</tr>"
    body = []
    for (point, carrier) in sorted(rows):
        tds = [f"<td class='lbl'>{esc(point)}</td><td class='lbl'>{esc(carrier)}</td>"]
        for t in time_bands:
            c = rows[(point, carrier)].get(t)
            if not c:
                tds.append("<td>—</td>")
                continue
            grade = c["grade"] or "n/a"
            bg, fg = cc.GRADE_COLORS.get(grade, cc.GRADE_COLORS["n/a"])
            lc = " *" if c["low_confidence"] else ""
            tds.append(f"<td style='background:{bg};color:{fg}'><b>{cc.fmt_num(c[value_key], 2)}</b>"
                       f"<span class='sub'>{esc(grade)} · n={c['n']}{lc}</span></td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    return f"<div class='scroll'><table>{head}{''.join(body)}</table></div>"


def _attr_table_html(attr):
    """One three-tier attribution table as HTML."""
    rows = []
    for c in attr["cells"]:
        cell_label = " · ".join(f"{k}={v}" for k, v in c["cell"].items())
        cov = ",".join(cc.TIER_LABELS.get(t, t) for t in c["coverage"]) or "—"
        notes = []
        if c["not_computable_reason"]:
            notes.append(c["not_computable_reason"])
        if c["inversions"]:
            notes.append("inversion:" + "|".join(c["inversions"]))
        if c.get("mixed_profile_versions"):
            notes.append("MIXED_PROFILE_VERSION:" + "|".join(c["mixed_profile_versions"]))
        if c.get("mixed_histogram_edges"):
            notes.append("MIXED_HIST_EDGES")
        if c["low_confidence"]:
            notes.append("low_conf")
        rows.append(
            f"<tr><td class='lbl'>{esc(cell_label)}</td><td>{esc(cov)}</td>"
            f"<td>{cc.fmt_num(c['access_component'])}</td>"
            f"<td>{cc.fmt_num(c['regional_backbone_incr'])}</td>"
            f"<td>{cc.fmt_num(c['core_backbone_incr'])}</td>"
            f"<td>{cc.fmt_num(c['end_to_end_core'])}</td>"
            f"<td>{esc('; '.join(notes) or '—')}</td></tr>")
    return (
        "<div class='scroll'><table><tr><th>单元</th><th>覆盖</th><th>接入</th>"
        "<th>区域骨干+</th><th>核心骨干+</th><th>端到端</th><th>备注</th></tr>"
        + ("".join(rows) or "<tr><td colspan='7' class='empty'>无可归因单元</td></tr>")
        + "</table></div>")


def build_report_html(records, generated_at, min_samples=cc.DEFAULT_MIN_SAMPLES,
                      attr_kpi=attribution.DEFAULT_KPI, before_id=None, after_id=None):
    inv = inventory(records)
    cells = heat_cells(records, min_samples)
    if before_id is None and after_id is None:
        before_id, after_id = _auto_compare_ids(inv)

    kpi_grids = ""
    for k in DEFAULT_KPI_HEAT:
        kc = kpi_heat_cells(records, k, min_samples)
        if kc:
            kpi_grids += (f"<h2>分 KPI 热力卡：{esc(k)}（中位 + 上报分级）</h2>"
                          + _heat_grid_html(kc, "median"))

    attr_sections = ""
    for k in attribution.ATTRIBUTABLE_KPIS:
        attr = attribution.attribute(records, kpi=k, min_samples=min_samples)
        if k == attr_kpi or attr["cells"]:
            attr_sections += (f"<h2>三级差分归因矩阵（{esc(k)}，ms）</h2>" + _attr_table_html(attr))

    cmp_html = ""
    if before_id and after_id:
        cmp = compare_campaigns(records, before_id, after_id, min_samples)
        crows = []
        for r in cmp["rows"]:
            d = r["delta"]
            color = "#137333" if (d is not None and d > 0) else ("#c5221f" if (d is not None and d < 0) else "#444")
            crows.append(
                f"<tr><td class='lbl'>{esc(r['cell']['point_id'])} · {esc(r['cell']['carrier'])} · "
                f"{esc(r['cell']['time_band'])}</td><td>{cc.fmt_num(r['before'])}</td>"
                f"<td>{cc.fmt_num(r['after'])}</td>"
                f"<td style='color:{color};font-weight:600'>{cc.fmt_num(d)}</td></tr>")
        cmp_html = (
            f"<h2>优化前后对比（{esc(before_id)} → {esc(after_id)}）</h2>"
            "<div class='scroll'><table><tr><th>单元</th><th>before</th><th>after</th><th>Δ AQS</th></tr>"
            + ("".join(crows) or "<tr><td colspan='4' class='empty'>无共同单元</td></tr>")
            + "</table></div>")

    warn = ""
    if inv["with_campaign"] == 0:
        warn = ("<p class='warn'>全部记录无 run.campaign 标签——热力卡/归因/对比塌缩为单格。"
                "接线见 docs/CAMPAIGN_LABELS_CONVENTION.md §4。</p>")

    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ANEB 战役级综合报告</title>
<style>
body{{font-family:'Segoe UI',system-ui,sans-serif;margin:0;background:#f6f7f9;color:#202124}}
.wrap{{max-width:1000px;margin:0 auto;padding:24px 16px 48px}}
h1{{font-size:22px}} h2{{font-size:16px;margin:28px 0 10px;border-bottom:1px solid #ddd;padding-bottom:6px}}
table{{border-collapse:collapse;width:100%;font-size:12.5px;background:#fff}}
th,td{{border:1px solid #e0e0e0;padding:5px 8px;text-align:right;white-space:nowrap}}
th{{background:#f1f3f4;text-align:center}} td.lbl{{text-align:left;font-weight:600}}
td .sub{{display:block;font-size:10px;opacity:.75;font-weight:400}}
.scroll{{overflow-x:auto}}
.empty{{color:#5f6368;font-style:italic;text-align:center}}
.warn{{color:#b06000;background:#fef7e0;padding:8px 12px;border-radius:6px}}
.note{{font-size:12px;color:#5f6368}}
footer{{margin-top:36px;font-size:12px;color:#5f6368;border-top:1px solid #ddd;padding-top:12px}}
</style></head><body><div class="wrap">
<h1>ANEB 战役级综合报告</h1>
<p class="note">生成时间：{esc(generated_at)} · 记录 {inv['records']} · 含 AQS {inv['aqs_present']} · 含标签 {inv['with_campaign']} · min_samples={min_samples}</p>
{warn}
<h2>点位 × 忙闲 × 运营商 热力卡（AQS 中位；* = 样本不足 low_conf）</h2>
{_heat_grid_html(cells)}
{kpi_grids}
{attr_sections}
{cmp_html}
<footer>claim_scope: <b>application_end_to_end_to_probe_node</b> — 应用层路径分段，不代表运营商网络端到端体验/MOS。<br>
ANEB 战役级报告 · stdlib-only 生成 · 标签约定见 docs/CAMPAIGN_LABELS_CONVENTION.md。</footer>
</div></body></html>"""


def write_csv_tables(records, prefix, min_samples=cc.DEFAULT_MIN_SAMPLES,
                     stability_kpi="n1_rtt_p50_ms"):
    """Dump the campaign tables as CSV for external analysis (Excel/pandas). Writes
    <prefix>_heat.csv / _attribution.csv / _stability.csv. Returns the paths written.
    None values are emitted as empty cells (R-10: not fabricated to 0)."""
    def _cell(v):
        return "" if v is None else v

    written = []
    heat = heat_cells(records, min_samples)
    p = prefix + "_heat.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["point_id", "carrier", "time_band", "aqs_median", "grade", "n", "low_confidence"])
        for c in heat:
            w.writerow([c["cell"]["point_id"], c["cell"]["carrier"], c["cell"]["time_band"],
                        _cell(c["aqs_median"]), c["grade"], c["n"], c["low_confidence"]])
    written.append(p)

    attr = attribution.attribute(records, min_samples=min_samples)
    p = prefix + "_attribution.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["point_id", "carrier", "time_band", "profile_id", "kpi", "access",
                    "regional_incr", "core_incr", "end_to_end_core", "coverage",
                    "low_confidence", "not_computable_reason"])
        for c in attr["cells"]:
            cell = c["cell"]
            w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                        cell.get("profile_id"), attr["kpi"], _cell(c["access_component"]),
                        _cell(c["regional_backbone_incr"]), _cell(c["core_backbone_incr"]),
                        _cell(c["end_to_end_core"]), "|".join(c["coverage"]),
                        c["low_confidence"], c["not_computable_reason"] or ""])
    written.append(p)

    scells = stability.stability_cells(records, stability_kpi, min_samples=min_samples)
    p = prefix + "_stability.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["point_id", "carrier", "time_band", "tier", "profile_id", "kpi", "n",
                    "median", "mean", "cv_percent", "unstable", "low_confidence"])
        for c in scells:
            cell = c["cell"]
            w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                        cell.get("tier"), cell.get("profile_id"), c["kpi"], c["n"],
                        _cell(c["median"]), _cell(c["mean"]), _cell(c["cv_percent"]),
                        c["unstable"], c["low_confidence"]])
    written.append(p)
    return written


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB campaign-level comprehensive report")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--html", help="also write a self-contained HTML report to this path")
    ap.add_argument("--md", help="write the markdown report to this path (else stdout)")
    ap.add_argument("--attr-kpi", default=attribution.DEFAULT_KPI,
                    choices=attribution.ATTRIBUTABLE_KPIS)
    ap.add_argument("--min-samples", type=int, default=cc.DEFAULT_MIN_SAMPLES)
    ap.add_argument("--before", help="campaign_id for before/after 'before'")
    ap.add_argument("--after", help="campaign_id for before/after 'after'")
    ap.add_argument("--csv", help="also write heat/attribution/stability tables as <PREFIX>_*.csv")
    ap.add_argument("--provenance", help="write the full manifest (with sha256) to this JSON path")
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")

    stats = {}
    recs, files = cc.load_records(args.inputs, stats=stats)
    params = {"min_samples": args.min_samples, "attr_kpi": args.attr_kpi,
              "before": args.before, "after": args.after}
    prov = prov_mod.compute(files, stats, params, generated_at=now)

    md = build_report_markdown(recs, args.min_samples, args.attr_kpi, args.before,
                               args.after, provenance=prov)
    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"markdown -> {args.md} (records={len(recs)})")
    else:
        print(md)
    if args.html:
        out = build_report_html(recs, now, args.min_samples, args.attr_kpi, args.before, args.after)
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"html -> {args.html}")
    if args.csv:
        paths = write_csv_tables(recs, args.csv, args.min_samples)
        print("csv -> " + ", ".join(paths))
    if args.provenance:
        prov_mod.write_sidecar(prov, args.provenance)
        print(f"provenance -> {args.provenance}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
