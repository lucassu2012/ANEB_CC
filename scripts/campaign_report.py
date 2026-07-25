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
import re
import sys
from collections import Counter, defaultdict

import campaign_common as cc
import attribution
import buffering_rollup
import order_effect
import provenance as prov_mod
import stability
import subscore_rollup
import transport_rollup
import trend
import trust_rollup
import validate_results as vr
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
        "statuses": Counter(),
        # version dimensions that define what the numbers MEAN — pooling across
        # them compares different metric/scoring definitions under one name (D-137)
        "kpi_sets": Counter(), "aqs_versions": Counter(), "app_versions": Counter(),
        # which profile versions produced these measurements — the precondition
        # for comparing one point against another at all (D-139)
        "profile_version_sets": Counter(),
        # measurement window — the deliverable states when the data was collected,
        # and a reader cannot judge a heat card without knowing that (D-138)
        "first_ms": None, "last_ms": None,
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
        # `aborted:<reason>` buckets by the prefix; reasons stay in the raw record
        status = cc.run_obj(rec).get("status")
        inv["statuses"][(status.split(":", 1)[0] if isinstance(status, str) and status
                         else "unknown")] += 1
        inv["profile_version_sets"][rec.get("profile_versions") or "absent"] += 1
        inv["kpi_sets"][rec.get("kpi_set") or "absent"] += 1
        inv["aqs_versions"][rec.get("aqs_version") or "absent"] += 1
        inv["app_versions"][cc.run_obj(rec).get("app_version_code")
                            if cc.run_obj(rec).get("app_version_code") is not None
                            else "absent"] += 1
        started = cc.run_started_ms(rec)
        if started is not None:
            inv["first_ms"] = started if inv["first_ms"] is None else min(inv["first_ms"], started)
            inv["last_ms"] = started if inv["last_ms"] is None else max(inv["last_ms"], started)
        if cc.run_aqs(rec) is not None:
            inv["aqs_present"] += 1
    return inv


def _utc_stamp(ms):
    """epoch ms -> 'YYYY-MM-DD HH:MM UTC'. UTC deliberately: the records carry no
    timezone, so rendering in local time would silently assume one (and would make
    the report non-reproducible across machines)."""
    if ms is None:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ms / 1000.0, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def corpus_warnings(inv):
    """Corpus-wide incomparability notices, as plain strings.

    Shared by the markdown and HTML reports: these used to be emitted only in the
    markdown preamble, which the md->html conversion drops (it splits on '## '),
    so the HTML deliverable silently lacked every one of them (D-140).
    """
    out = []
    ver_mixed = []
    for key, label in (("kpi_sets", "kpi_set"), ("aqs_versions", "aqs_version"),
                       ("profile_version_sets", "profile_versions"),
                       ("app_versions", "app_version_code")):
        if len(inv[key]) > 1:
            ver_mixed.append(f"{label}={dict(inv[key])}")
    if ver_mixed:
        out.append("语料**跨版本**：" + "；".join(ver_mixed) +
                   "。`kpi_set` 定义指标是什么、`aqs_version` 定义分数怎么算、"
                   "`profile_versions` 决定跨点位是否可比、`app_version_code` 是采集它的"
                   "构建——**跨版本聚合可能在把不同定义的数字当同一指标平均**。工具无法"
                   "判断该次版本变更是否改动了定义，请人工确认后在报告中说明，或按版本"
                   "分别出报告。")
    # Cross-campaign pooling is the most consequential incomparability: a cell
    # holding a baseline round and an optimisation round shows a median that is
    # neither. Say so BEFORE the heat card, not only in the per-cell note (D-135).
    labeled_ids = [c for c in inv["campaigns"] if c != "unlabeled"]
    if len(labeled_ids) > 1:
        out.append(f"本语料含 **{len(labeled_ids)} 个战役**（{', '.join(sorted(labeled_ids))}）。"
                   "除「优化前后对比」/「纵向趋势」两段外，**各段均按格池化了所有战役**——"
                   "受影响的格标 `MIXED_CAMPAIGN`，其中位数**既不是前也不是后**。"
                   "要看单个战役，用 `--campaign <id>`。")
    return out


def _cell_label(cell, dims=("point_id", "carrier", "time_band")):
    """Compact cell label. Callers whose cells are keyed on more dimensions must
    pass them all — a label that drops key dimensions renders as duplicates and
    the reader cannot tell which cell is meant."""
    return "/".join(cc.md_cell(cell.get(k, "?")) for k in dims
                    if cell.get(k) is not None)


def _top(items, n=3):
    return "、".join(items[:n]) + (f" 等 {len(items)} 个" if len(items) > n else "")


def render_summary_markdown(records, min_samples=cc.DEFAULT_MIN_SAMPLES,
                            attr_kpi=attribution.DEFAULT_KPI):
    """Signal before evidence (D-117).

    At M2 grid scale the report is ~1600 lines; the findings that decide what to
    do next — bad cells, distortion hot-spots, suspect clocks, low validity,
    unstable cells — were buried in the middle of it. This lifts them to the top.
    It only points INTO the detailed sections below; nothing is hidden, and the
    distinction between "no problem" and "no data" is kept explicit (R-10).
    """
    lines = ["## 摘要（先看这里）", ""]
    bullets = []

    cells = heat_cells(records, min_samples)
    scored = sorted((c for c in cells if c["aqs_median"] is not None),
                    key=lambda c: c["aqs_median"])
    weak = [f"{_cell_label(c['cell'])}({cc.fmt_num(c['aqs_median'], 1)})"
            for c in scored if c["grade"] in ("poor", "fair")]
    if not scored:
        bullets.append("**体验最差格**：无 AQS 数据（覆盖缺口，非全部良好）。")
    elif weak:
        bullets.append(f"**体验最差格**：{len(weak)} 个格 AQS 达 fair/poor —— {_top(weak)}。")
    else:
        bullets.append(f"**体验最差格**：无 fair/poor 格（最低 "
                       f"{_cell_label(scored[0]['cell'])}="
                       f"{cc.fmt_num(scored[0]['aqs_median'], 1)}）。")

    # The report is titled "heat card AND ATTRIBUTION"; the summary told the
    # reader which cells are bad but never which path segment caused it — the
    # whole point of the attribution matrix (D-142).
    attr = attribution.attribute(records, kpi=attr_kpi, min_samples=min_samples)
    seg_names = {"access_component": "接入", "regional_backbone_incr": "区域骨干",
                 "core_backbone_incr": "核心骨干"}
    dominant, not_computable = Counter(), 0
    worst = None
    for c in attr["cells"]:
        parts_ = {k: c[k] for k in seg_names if c[k] is not None}
        if not parts_:
            not_computable += 1
            continue
        top = max(parts_, key=lambda k: parts_[k])
        dominant[seg_names[top]] += 1
        if worst is None or parts_[top] > worst[1]:
            worst = (f"{_cell_label(c['cell'], attr['group_by'])}·{seg_names[top]}",
                     parts_[top])
    if not attr["cells"]:
        bullets.append(f"**分段归因**：无可归因单元（`{attr_kpi}` 缺数据或缺层级）。")
    elif not dominant:
        bullets.append(f"**分段归因**：{not_computable} 个格不可计算"
                       "（层级缺失，记 TIER_MISSING，不外推）。")
    else:
        tail = f"；另有 {not_computable} 个格不可计算" if not_computable else ""
        bullets.append("**分段归因**（主要贡献段）：" +
                       "、".join(f"{k} {v} 格" for k, v in dominant.most_common()) +
                       (f"；最大单项 {worst[0]}={cc.fmt_num(worst[1], 1)}ms" if worst else "")
                       + tail + "。")

    bres = buffering_rollup.analyze(records, min_samples)
    hot = [_cell_label(c["cell"]) for c in bres["cells"] if c["distortion_hotspot"]]
    if not bres["cells"]:
        bullets.append("**批化失真**：无批化标注（覆盖缺口，非未见失真）。")
    else:
        bullets.append(f"**批化失真热点**：{len(hot)} 个 —— {_top(hot)}。" if hot
                       else "**批化失真**：无热点格。")

    tres = trust_rollup.analyze(records, min_samples)
    clock_hot = [_cell_label(c["cell"]) for c in tres["cells"] if c["clock_hotspot"]]
    if tres["no_evidence"]:
        bullets.append("**测量可信度**：无 clock/seq/parse 证据（覆盖缺口，非全部可信）。")
    else:
        bullets.append(f"**时钟可疑热点**：{len(clock_hot)} 个 —— {_top(clock_hot)}"
                       "（该格时延中位数存疑）。" if clock_hot else "**时钟可疑热点**：无。")

    vres = validity_rollup.analyze(records)
    # validity cells are keyed on profile_id too — drop it and several cells
    # render as the same label, which the reader cannot act on (D-125)
    low_valid = [_cell_label(c["cell"], ("point_id", "carrier", "time_band",
                                         "profile_id"))
                 + f"({c['valid_rate'] * 100:.0f}%)"
                 for c in vres["cells"] if c["below_min_rate"]]
    if not vres["cells"]:
        bullets.append("**有效率**：无场景数据。")
    else:
        bullets.append(f"**有效率不达门**：{len(low_valid)} 个格 —— {_top(low_valid)}。"
                       if low_valid else
                       f"**有效率**：全部达门（≥{vres['min_rate'] * 100:.0f}%）。")

    unstable, measured = [], 0
    for k in stability.DEFAULT_STABILITY_KPIS:
        for c in stability.stability_cells(records, k, min_samples=min_samples):
            if c["cv_percent"] is None:
                continue
            measured += 1
            if c["unstable"]:
                # stability cells are keyed on tier+profile too — include them,
                # or the labels collapse into indistinguishable duplicates
                unstable.append(_cell_label(
                    c["cell"], ("point_id", "carrier", "time_band", "tier",
                                "profile_id")) + f"·{k}")
    if not measured:
        bullets.append("**复测稳定性**：无可计算 CV 的单元。")
    else:
        bullets.append(f"**复测不稳定**：{len(unstable)}/{measured} 单元超 CV 门 —— "
                       f"{_top(unstable)}。" if unstable else
                       f"**复测稳定性**：{measured} 个单元全部达门。")

    tr = transport_rollup.analyze(records, min_samples)
    worse = [f"{_cell_label(c['cell'])}(Δ{cc.fmt_num(c['cellular_minus_wifi'], 1)})"
             for c in tr["cells"]
             if c["cellular_minus_wifi"] is not None and c["cellular_minus_wifi"] < 0]
    if tr["only_unknown"]:
        bullets.append("**接入介质**：无 transport 证据（覆盖缺口）。")
    elif worse:
        bullets.append(f"**蜂窝劣于 wifi**：{len(worse)} 个格 —— {_top(worse)}。")
    else:
        bullets.append("**接入介质**：无同格双介质可比，或蜂窝不劣于 wifi。")

    # Score-side counterpart to the path attribution: the latency matrix says
    # WHICH SEGMENT is slow, this says WHICH KPI DIMENSION drags the score (D-143).
    sres = subscore_rollup.analyze(records, min_samples)
    drags = Counter(c["dragging_dim"] for c in sres["cells"] if c["dragging_dim"])
    if not sres["cells"]:
        bullets.append("**分数侧归因**：无 AQS 子分（覆盖缺口，非各维皆好）。")
    elif not drags:
        bullets.append("**分数侧归因**：各格均无可用子分，拖累维度不可计算。")
    else:
        worst_cell = min((c for c in sres["cells"] if c["dragging_median"] is not None),
                         key=lambda c: c["dragging_median"], default=None)
        tail = ("；最低 " + _cell_label(worst_cell["cell"]) + "·" +
                f"{worst_cell['dragging_dim']}={cc.fmt_num(worst_cell['dragging_median'], 1)}"
                ) if worst_cell else ""
        bullets.append("**分数侧归因**（拖累维度）：" +
                       "、".join(f"{d} {n} 格" for d, n in drags.most_common()) + tail + "。")

    # "Did it get better" — the headline question of any second round (D-143).
    inv_ = inventory(records)
    before_id, after_id = _auto_compare_ids(inv_)
    labeled = [c for c in inv_["campaigns"] if c != "unlabeled"]
    if before_id and after_id:
        rows = compare_campaigns(records, before_id, after_id, min_samples)["rows"]
        deltas = [r["delta"] for r in rows if r["delta"] is not None]
        if not deltas:
            bullets.append(f"**优化前后**：{before_id} → {after_id} 无共同单元可比。")
        else:
            up = sum(1 for d in deltas if d > 0)
            down = sum(1 for d in deltas if d < 0)
            bullets.append(f"**优化前后**（{before_id} → {after_id}）：{len(deltas)} 个共同格中"
                           f"改善 {up}、回退 {down}、持平 {len(deltas) - up - down}；"
                           f"AQS 中位Δ {cc.fmt_num(cc.median(deltas), 1)}。")
    elif len(labeled) >= 3:
        tres = trend.analyze(records, min_samples=min_samples)
        verdict = Counter(c["direction"] for c in tres["cells"] if c["direction"])
        bullets.append("**纵向趋势**：" +
                       "、".join(f"{k} {v} 格" for k, v in verdict.most_common())
                       + f"（{len(labeled)} 个战役）。" if verdict else
                       "**纵向趋势**：各格在场点不足 2，方向不可计算。")

    lines += [f"- {b}" for b in bullets]
    lines += ["", "> 以上为下方各段的**指路**，证据与完整表格见对应段落；"
                  "口径与不可计算说明以各段为准。"]
    return "\n".join(lines)


# ---------------------------------------------------------------- heat card

def heat_cells(records, min_samples=cc.DEFAULT_MIN_SAMPLES, campaign_id=None):
    """AQS by (point_id, carrier, time_band). Returns sorted list of cell dicts.
    Optional campaign_id filter (for before/after)."""
    buckets = defaultdict(list)
    seen_campaigns = {}
    for rec in records:
        labels = cc.campaign_labels(rec)
        if campaign_id is not None and labels["campaign_id"] != campaign_id:
            continue
        aqs = cc.run_aqs(rec)
        if aqs is None:
            continue
        key = tuple(labels[d] for d in HEAT_DIMS)
        buckets[key].append(aqs)
        seen_campaigns.setdefault(key, set()).add(labels["campaign_id"])
    cells = []
    for key in sorted(buckets):
        vals = buckets[key]
        med = cc.median(vals)
        ids = sorted(seen_campaigns.get(key) or [])
        cells.append({
            "cell": dict(zip(HEAT_DIMS, key)),
            "aqs_median": med,
            "grade": cc.aqs_grade(med),
            "n": len(vals),
            "low_confidence": len(vals) < min_samples,
            # a cell pooling a baseline round with an optimisation round shows a
            # median that is NEITHER of them — flag it, never hide it (D-135)
            "mixed_campaigns": ids if len(ids) > 1 else [],
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
        notes = []
        if c.get("mixed_campaigns"):
            notes.append("MIXED_CAMPAIGN:" + "/".join(c["mixed_campaigns"]))
        if c["low_confidence"]:
            notes.append("low_conf")
        note = "; ".join(notes) or "—"
        lines.append(
            f"| {cc.md_cell(c['cell']['point_id'])} | {cc.md_cell(c['cell']['carrier'])} "
            f"| {cc.md_cell(c['cell']['time_band'])} | "
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
            f"| {cc.md_cell(r['cell']['point_id'])} | {cc.md_cell(r['cell']['carrier'])} "
            f"| {cc.md_cell(r['cell']['time_band'])} | "
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
            f"| {cc.md_cell(c['cell']['point_id'])} | {cc.md_cell(c['cell']['carrier'])} "
            f"| {cc.md_cell(c['cell']['time_band'])} | "
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
    ]
    # Fabricated numbers must never be mistakable for field results (D-116).
    # First thing after the title, ahead of any measurement claim.
    n_synth = cc.count_synthetic(records)
    if n_synth:
        parts += [
            f"> # ⛔ 合成数据警告：本报告 {n_synth}/{len(records)} 条记录为**合成语料**",
            "> ",
            "> 由 `scripts/synth_campaign.py` **生成**，数字是**虚构的**、**不是实测**。"
            "仅供工具链彩排/演示——**不得**作为外场结论、进局点材料或任何对外结论的依据。",
            "",
        ]
    parts += [
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
        f"- run 状态 status：{dict(inv['statuses'])}",
        f"- profile 版本：{dict(inv['profile_version_sets'])}",
        f"- 采集时间窗：{_utc_stamp(inv['first_ms']) or '—'} → "
        f"{_utc_stamp(inv['last_ms']) or '—'}"
        + ("" if inv["first_ms"] is not None else "（记录缺 started_at_epoch_ms）"),
        "",
    ]
    # Aborted/unknown runs are SURFACED, never silently dropped (survey gap 4):
    # their completed scenarios are real measurements and stay in scenario-level
    # stats; an aborted run's AQS is typically null and never enters medians.
    if set(inv["statuses"]) - {"completed"}:
        parts.append("> ⚠ 存在非 `completed` run（见上行分布）——其已完成场景仍计入场景级统计"
                     "（run 级 AQS 为 null 不进中位）；**只显性化，不静默剔除**。")
        parts.append("")
    # Optional chain-of-custody block. Omitted (None) keeps the body deterministic
    # for the regression snapshot; the CLI injects a real manifest.
    if provenance is not None:
        parts.append(prov_mod.render_markdown(provenance))
        parts.append("")
    if inv["with_campaign"] == 0:
        parts.append("> ⚠ 全部记录无 `run.campaign` 标签——热力卡/归因/前后对比塌缩为单格 "
                     "`unlabeled`。接线见 docs/CAMPAIGN_LABELS_CONVENTION.md §4。")
        parts.append("")
    # Version dimensions define what the numbers MEAN. Pooling two kpi_sets
    # averages metrics that may not be the same metric; pooling two aqs_versions
    # mixes scoring systems. The tool cannot know whether a given bump changed the
    # definitions, so it states the fact and leaves the judgement to a human (D-137).
    for w in corpus_warnings(inv):
        parts.append("> ⚠ " + w)
        parts.append("")
    # Signal before evidence: the findings that decide next actions, ahead of the
    # ~1600 lines of tables they point into (D-117).
    parts.append(render_summary_markdown(records, min_samples, attr_kpi))
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
    # Instrument trust behind the timing medians: clock / stream / parse (D-111)
    parts.append(trust_rollup.render_markdown(trust_rollup.analyze(records, min_samples)))
    parts.append("")
    for k in attribution.ATTRIBUTABLE_KPIS:
        attr = attribution.attribute(records, kpi=k, min_samples=min_samples)
        if k == attr_kpi or attr["cells"]:  # primary always; secondary only if it has cells
            parts.append(attribution.render_markdown(attr))
            parts.append("")
    # Score-side complement to the latency attribution: which AQS dimension drags. (D-100)
    parts.append(subscore_rollup.render_markdown(subscore_rollup.analyze(records, min_samples)))
    parts.append("")
    # Forensic distortion accounting: is a median slow because the network is slow,
    # or because something batched the stream? Annotation only — R-05 forbids any
    # re-judging of validity/score from it. (D-104)
    parts.append(buffering_rollup.render_markdown(buffering_rollup.analyze(records, min_samples)))
    parts.append("")
    # Access-medium comparison: is cellular worse than wifi in this cell? (D-110)
    parts.append(transport_rollup.render_markdown(transport_rollup.analyze(records, min_samples)))
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
            lc = (" *" if c["low_confidence"] else "") \
                + (" ⚠混战役" if c.get("mixed_campaigns") else "")
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
            notes.append("inversion:" + "/".join(c["inversions"]))   # same separator as md
        if c.get("mixed_profile_versions"):
            notes.append("MIXED_PROFILE_VERSION:" + "/".join(c["mixed_profile_versions"]))
        if c.get("mixed_histogram_edges"):
            notes.append("MIXED_HIST_EDGES")
        if c.get("mixed_modes"):
            notes.append("MIXED_MODE:" + "/".join(c["mixed_modes"]))
        if c.get("mixed_profile_sources"):
            notes.append("MIXED_PROFILE_SOURCE:" + "/".join(c["mixed_profile_sources"]))
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


# Restricted markdown -> HTML: the tools' render_markdown() functions stay the
# single source of truth for every non-rich section, so the HTML report can never
# drift out of sync with the markdown report (D-107).
_INLINE_MD = ((re.compile(r"\*\*(.+?)\*\*"), r"<b>\1</b>"),
              (re.compile(r"`([^`]+)`"), r"<code>\1</code>"))


def _md_inline(text):
    s = esc(text)
    for pat, rep in _INLINE_MD:
        s = pat.sub(rep, s)
    return s


def _md_section_html(md):
    """Render one tool's markdown section as HTML. Supports only the restricted
    markdown our renderers emit: ## headings, > blockquotes, pipe tables,
    - list items, _italic_ empty-notes, plain paragraphs."""
    out, table = [], []

    def flush():
        if not table:
            return
        head, *body = table
        ths = "".join(f"<th>{_md_inline(c)}</th>" for c in head)
        trs = []
        for r in body:
            tds = [f"<td class='lbl'>{_md_inline(r[0])}</td>"] \
                + [f"<td>{_md_inline(c)}</td>" for c in r[1:]]
            trs.append("<tr>" + "".join(tds) + "</tr>")
        out.append(f"<div class='scroll'><table><tr>{ths}</tr>{''.join(trs)}</table></div>")
        table.clear()

    for line in md.splitlines():
        s = line.strip()
        if s.startswith("|"):
            cells_ = [c.strip() for c in s.strip("|").split("|")]
            if all(c and set(c) <= {"-", ":", " "} for c in cells_):  # |---| separator
                continue
            table.append(cells_)
            continue
        flush()
        if not s:
            continue
        if s.startswith("## "):
            out.append(f"<h2>{_md_inline(s[3:])}</h2>")
        elif s.startswith("### "):
            out.append(f"<h3>{_md_inline(s[4:])}</h3>")
        elif s.startswith("> "):
            out.append(f"<p class='note'>{_md_inline(s[2:])}</p>")
        elif s.startswith("- "):
            out.append(f"<p class='note'>• {_md_inline(s[2:])}</p>")
        elif len(s) > 1 and s.startswith("_") and s.endswith("_"):
            out.append(f"<p class='empty'>{_md_inline(s.strip('_'))}</p>")
        else:
            out.append(f"<p>{_md_inline(s)}</p>")
    flush()
    return "".join(out)


# Sections the HTML report renders natively (colored grids, richer than a table).
_HTML_RICH_PREFIXES = ("点位 × 忙闲", "分 KPI 热力卡", "三级差分归因矩阵",
                       "优化前后对比")


def _md_only_sections_html(records, min_samples, attr_kpi, before_id, after_id,
                           provenance):
    """Every markdown-report section without a native HTML rendering, converted.
    Extracted from build_report_markdown's own output so section assembly logic
    exists exactly once — a new markdown section joins the HTML automatically."""
    md = build_report_markdown(records, min_samples, attr_kpi, before_id, after_id,
                               provenance=provenance)
    chunks = re.split(r"(?m)^## ", md)[1:]          # drop the # title preamble
    keep = [c for c in chunks if not c.startswith(_HTML_RICH_PREFIXES)]
    return "".join(_md_section_html("## " + c) for c in keep)


def build_report_html(records, generated_at, min_samples=cc.DEFAULT_MIN_SAMPLES,
                      attr_kpi=attribution.DEFAULT_KPI, before_id=None, after_id=None,
                      provenance=None):
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
    # same corpus-wide notices the markdown carries — they used to exist only in
    # the markdown preamble, which the md->html conversion drops (D-140)
    warn += "".join(f"<p class='warn'>⚠ {_md_inline(w)}</p>" for w in corpus_warnings(inv))
    # Same unmissable synthetic-data banner as the markdown report (D-116).
    n_synth = cc.count_synthetic(records)
    synth_banner = ("" if not n_synth else
                    f"<div class='synth'><b>⛔ 合成数据警告：本报告 {n_synth}/{len(records)} "
                    "条记录为合成语料</b><br>由 <code>scripts/synth_campaign.py</code> 生成，"
                    "数字是虚构的、不是实测。仅供工具链彩排/演示——<b>不得</b>作为外场结论、"
                    "进局点材料或任何对外结论的依据。</div>")

    # 溯源/稳定性/序位/有效性/分数侧/批化/趋势 — converted from the markdown
    # renderers (single source of truth), appended after the rich grids (D-107).
    md_only = _md_only_sections_html(records, min_samples, attr_kpi, before_id,
                                     after_id, provenance)

    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ANEB 战役级综合报告</title>
<style>
body{{font-family:'Segoe UI',system-ui,sans-serif;margin:0;background:#f6f7f9;color:#202124}}
.wrap{{max-width:1000px;margin:0 auto;padding:24px 16px 48px}}
h1{{font-size:22px}} h2{{font-size:16px;margin:28px 0 10px;border-bottom:1px solid #ddd;padding-bottom:6px}}
h3{{font-size:13.5px;margin:18px 0 8px}}
table{{border-collapse:collapse;width:100%;font-size:12.5px;background:#fff}}
th,td{{border:1px solid #e0e0e0;padding:5px 8px;text-align:right;white-space:nowrap}}
th{{background:#f1f3f4;text-align:center}} td.lbl{{text-align:left;font-weight:600}}
td .sub{{display:block;font-size:10px;opacity:.75;font-weight:400}}
.scroll{{overflow-x:auto}}
.empty{{color:#5f6368;font-style:italic;text-align:center}}
.warn{{color:#b06000;background:#fef7e0;padding:8px 12px;border-radius:6px}}
.synth{{color:#fff;background:#c5221f;padding:14px 16px;border-radius:8px;font-size:15px;
        line-height:1.6;margin:16px 0;border:3px solid #7f0f0d}}
.synth code{{background:rgba(255,255,255,.22);padding:1px 4px;border-radius:3px}}
.note{{font-size:12px;color:#5f6368}}
footer{{margin-top:36px;font-size:12px;color:#5f6368;border-top:1px solid #ddd;padding-top:12px}}
</style></head><body><div class="wrap">
<h1>ANEB 战役级综合报告</h1>
{synth_banner}
<p class="note">生成时间：{esc(generated_at)} · 记录 {inv['records']} · 含 AQS {inv['aqs_present']} · 含标签 {inv['with_campaign']} · min_samples={min_samples}</p>
{warn}
<h2>点位 × 忙闲 × 运营商 热力卡（AQS 中位；* = 样本不足 low_conf）</h2>
{_heat_grid_html(cells)}
{kpi_grids}
{attr_sections}
{cmp_html}
{md_only}
<footer>claim_scope: <b>application_end_to_end_to_probe_node</b> — 应用层路径分段，不代表运营商网络端到端体验/MOS。<br>
ANEB 战役级报告 · stdlib-only 生成 · 标签约定见 docs/CAMPAIGN_LABELS_CONVENTION.md。</footer>
</div></body></html>"""


# UTF-8 *with BOM*: these CSVs exist to be opened in Excel, and Excel on a
# Chinese Windows reads a BOM-less UTF-8 file as GBK — a point named 深圳-CBD-01
# comes out as 娣卞湷-CBD-01 (verified, D-129). pandas strips the BOM itself;
# a plain Python reader should use encoding="utf-8-sig".
CSV_ENCODING = "utf-8-sig"


def write_csv_tables(records, prefix, min_samples=cc.DEFAULT_MIN_SAMPLES,
                     before_id=None, after_id=None):
    """Dump the campaign tables as CSV for external analysis (Excel/pandas).
    Covers the same KPI sets the rendered report shows — an analyst pulling only
    the CSVs must not silently lose sections visible in the report (D-109).
    None values are emitted as empty cells (R-10: not fabricated to 0)."""
    def _cell(v):
        return "" if v is None else v

    written = []
    heat = heat_cells(records, min_samples)
    p = prefix + "_heat.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = csv.writer(f)
        # mixed_campaigns must reach the CSV too: an analyst working from the
        # tables sees only columns — without it, a pooled median arrives looking
        # like an ordinary trustworthy number (D-141)
        w.writerow(["point_id", "carrier", "time_band", "aqs_median", "grade", "n",
                    "low_confidence", "mixed_campaigns"])
        for c in heat:
            w.writerow([c["cell"]["point_id"], c["cell"]["carrier"], c["cell"]["time_band"],
                        _cell(c["aqs_median"]), c["grade"], c["n"], c["low_confidence"],
                        "/".join(c.get("mixed_campaigns") or [])])
    written.append(p)

    p = prefix + "_attribution.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = csv.writer(f)
        w.writerow(["point_id", "carrier", "time_band", "profile_id", "kpi", "access",
                    "regional_incr", "core_incr", "end_to_end_core", "coverage",
                    "low_confidence", "not_computable_reason", "incomparability"])
        for k in attribution.ATTRIBUTABLE_KPIS:
            attr = attribution.attribute(records, kpi=k, min_samples=min_samples)
            for c in attr["cells"]:
                cell = c["cell"]
                # same markers the rendered notes column carries, so a filter like
                # incomparability.str.contains('MIXED_CAMPAIGN') works (D-141)
                flags = []
                for field, tag in (("mixed_campaigns", "MIXED_CAMPAIGN"),
                                   ("mixed_profile_versions", "MIXED_PROFILE_VERSION"),
                                   ("mixed_modes", "MIXED_MODE"),
                                   ("mixed_profile_sources", "MIXED_PROFILE_SOURCE")):
                    if c.get(field):
                        flags.append(f"{tag}:" + "/".join(c[field]))
                if c.get("mixed_histogram_edges"):
                    flags.append("MIXED_HIST_EDGES")
                w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                            cell.get("profile_id"), attr["kpi"], _cell(c["access_component"]),
                            _cell(c["regional_backbone_incr"]), _cell(c["core_backbone_incr"]),
                            _cell(c["end_to_end_core"]), "|".join(c["coverage"]),
                            c["low_confidence"], c["not_computable_reason"] or "",
                            ";".join(flags)])
    written.append(p)

    p = prefix + "_stability.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = csv.writer(f)
        w.writerow(["point_id", "carrier", "time_band", "tier", "profile_id", "kpi", "n",
                    "median", "mean", "cv_percent", "unstable", "low_confidence"])
        for k in stability.DEFAULT_STABILITY_KPIS:
            for c in stability.stability_cells(records, k, min_samples=min_samples):
                cell = c["cell"]
                w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                            cell.get("tier"), cell.get("profile_id"), c["kpi"], c["n"],
                            _cell(c["median"]), _cell(c["mean"]), _cell(c["cv_percent"]),
                            c["unstable"], c["low_confidence"]])
    written.append(p)

    # The sample denominator behind every median above (D-96) — external analysis
    # without it re-creates the survivor bias the rollup exists to expose.
    vcells = validity_rollup.analyze(records)["cells"]
    p = prefix + "_validity.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = csv.writer(f)
        w.writerow(["point_id", "carrier", "time_band", "profile_id", "attempted", "valid",
                    "valid_low_confidence", "invalid", "unknown", "valid_rate",
                    "below_min_rate", "reasons"])
        for c in vcells:
            cell = c["cell"]
            w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                        cell.get("profile_id"), c["attempted"], c["valid"],
                        c["valid_low_confidence"], c["invalid"], c["unknown"],
                        _cell(c["valid_rate"]), _cell(c["below_min_rate"]),
                        ";".join(f"{r}:{n}" for r, n in c["reasons"].items())])
    written.append(p)

    sscells = subscore_rollup.analyze(records, min_samples)["cells"]
    p = prefix + "_subscores.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = csv.writer(f)
        w.writerow(["point_id", "carrier", "time_band", "runs", "dragging_dim",
                    "dragging_median", "spread", "low_confidence", "dim_medians"])
        for c in sscells:
            cell = c["cell"]
            w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                        c["runs"], _cell(c["dragging_dim"]), _cell(c["dragging_median"]),
                        _cell(c["spread"]), c["low_confidence"],
                        ";".join(f"{d}:{v['median']}" for d, v in c["dims"].items())])
    written.append(p)

    ucells = trust_rollup.analyze(records, min_samples)["cells"]
    p = prefix + "_trust.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = csv.writer(f)
        w.writerow(["point_id", "carrier", "time_band", "scenarios", "clock_annotated",
                    "clock_suspect", "clock_suspect_share", "abs_drift_ppm_median",
                    "stream_counted", "stream_bad", "parse_per_event_us_median",
                    "clock_hotspot", "low_confidence"])
        for c in ucells:
            cell = c["cell"]
            w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                        c["scenarios"], c["clock_annotated"], c["clock_suspect"],
                        _cell(c["clock_suspect_share"]), _cell(c["abs_drift_ppm_median"]),
                        c["stream_counted"], c["stream_bad"],
                        _cell(c["parse_per_event_us_median"]), c["clock_hotspot"],
                        c["low_confidence"]])
    written.append(p)

    tcells = transport_rollup.analyze(records, min_samples)["cells"]
    p = prefix + "_transport.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = csv.writer(f)
        w.writerow(["point_id", "carrier", "time_band", "transport", "n", "aqs_median",
                    "low_confidence", "cellular_minus_wifi"])
        for c in tcells:
            cell = c["cell"]
            for t in sorted(c["transports"]):
                b = c["transports"][t]
                w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                            t, b["n"], _cell(b["aqs_median"]), b["low_confidence"],
                            _cell(c["cellular_minus_wifi"]) if t == "cellular" else ""])
    written.append(p)

    # The headline "did it get better" payloads (survey gap 6): before/after delta
    # and the N-campaign trajectory, in spreadsheet-consumable long format (D-114).
    if before_id is None and after_id is None:
        before_id, after_id = _auto_compare_ids(inventory(records))
    p = prefix + "_comparison.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = csv.writer(f)
        w.writerow(["point_id", "carrier", "time_band", "before_id", "after_id",
                    "before", "after", "delta"])
        if before_id and after_id:
            cmp_res = compare_campaigns(records, before_id, after_id, min_samples)
            for r in cmp_res["rows"]:
                cell = r["cell"]
                w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                            before_id, after_id, _cell(r["before"]), _cell(r["after"]),
                            _cell(r["delta"])])
    written.append(p)

    tres = trend.analyze(records, min_samples=min_samples)
    p = prefix + "_trend.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = csv.writer(f)
        w.writerow(["point_id", "carrier", "time_band", "campaign_id", "order_index",
                    "median", "n", "direction", "first_last_delta", "low_confidence"])
        for c in tres["cells"]:
            cell = c["cell"]
            for i, cid in enumerate(tres["campaigns"]):
                w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                            cid, i, _cell(c["trajectory"][i]), c["sample_counts"][i],
                            _cell(c["direction"]), _cell(c["first_last_delta"]),
                            c["low_confidence"]])
    written.append(p)

    bcells = buffering_rollup.analyze(records, min_samples)["cells"]
    p = prefix + "_buffering.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = csv.writer(f)
        w.writerow(["point_id", "carrier", "time_band", "n", "modal_attribution",
                    "score_median", "sawtooth_median", "near_zero_median",
                    "suspect_share", "distortion_hotspot", "low_confidence"])
        for c in bcells:
            cell = c["cell"]
            w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                        c["n"], c["modal_attribution"], _cell(c["score_median"]),
                        _cell(c["sawtooth_median"]), _cell(c["near_zero_median"]),
                        _cell(c["suspect_share"]), c["distortion_hotspot"],
                        c["low_confidence"]])
    written.append(p)
    return written


def effective_thresholds():
    """Every module-level gate that decides what the report SAYS, read live from
    the modules so the manifest can never drift from the code (D-122). `params`
    covers the CLI knobs; these are the ones a reader would otherwise have to
    guess at when a re-run disagrees with an archived report."""
    return {
        "cv_gate_percent": stability.DEFAULT_CV_GATE,
        "stability_max_stable_rows": stability.DEFAULT_MAX_STABLE_ROWS,
        "validity_min_rate": validity_rollup.DEFAULT_MIN_RATE,
        "buffering_hotspot_share": buffering_rollup.HOTSPOT_SHARE,
        "clock_hotspot_share": trust_rollup.CLOCK_HOTSPOT_SHARE,
        "aqs_grade_bands": [[b, g] for b, g in cc.AQS_GRADE_BANDS],
        "heat_kpis": list(DEFAULT_KPI_HEAT),
        "stability_kpis": list(stability.DEFAULT_STABILITY_KPIS),
        "attribution_kpis": list(attribution.ATTRIBUTABLE_KPIS),
    }


def contract_gate(records):
    """Front-door input check (D-105): the report is the 'ammunition into the
    operator meeting' (M2) — a quietly-wrong report is worse than none, so records
    violating the result-run contract refuse a report instead of degrading into
    empty/misleading sections. Returns the error list ([] = pass), or None when
    the schema file is unreadable (NOT_EXECUTED — 'cannot check' is not 'checked',
    mirroring validate_results exit 2)."""
    try:
        sch = vr.load_schema(vr.DEFAULT_SCHEMA)
    except Exception:
        return None
    errors, _warnings = vr.validate_records(records, sch)
    return errors


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB campaign-level comprehensive report")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--html", help="also write a self-contained HTML report to this path")
    ap.add_argument("--md", help="write the markdown report to this path (else stdout)")
    ap.add_argument("--attr-kpi", default=attribution.DEFAULT_KPI,
                    choices=attribution.ATTRIBUTABLE_KPIS)
    ap.add_argument("--min-samples", type=int, default=cc.DEFAULT_MIN_SAMPLES)
    ap.add_argument("--campaign", help="report on ONE campaign_id only. Headline "
                                       "numbers should come from a single campaign: "
                                       "pooling rounds yields a median that is "
                                       "neither of them (D-136)")
    ap.add_argument("--before", help="campaign_id for before/after 'before'")
    ap.add_argument("--after", help="campaign_id for before/after 'after'")
    ap.add_argument("--csv", help="also write heat/attribution/stability tables as <PREFIX>_*.csv")
    ap.add_argument("--provenance", help="write the full manifest (with sha256) to this JSON path")
    ap.add_argument("--skip-contract-check", action="store_true",
                    help="bypass the input contract gate (emergency escape hatch; "
                         "the report loses its 'validated input' claim)")
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")

    stats = {}
    recs, files = cc.load_records(args.inputs, stats=stats)
    if args.campaign:
        available = sorted({cc.campaign_labels(r)["campaign_id"] for r in recs})
        recs = [r for r in recs
                if cc.campaign_labels(r)["campaign_id"] == args.campaign]
        if not recs:
            # a typo'd id must not silently yield an empty report
            print(f"--campaign {args.campaign} 匹配 0 条记录；语料中的战役："
                  + ", ".join(available), file=sys.stderr)
            return 2
    if not recs:
        # Mirror validate_results/corpus_health: no corpus is NOT_EXECUTED (exit 2),
        # never a valid-looking empty report (D-109).
        print("无记录可报（文件缺失/全坏行/空输入）——不产出空报告（NOT_EXECUTED）",
              file=sys.stderr)
        return 2
    if not args.skip_contract_check:
        # Corpus integrity first: a conflicting duplicate run_id (same id, two
        # different bodies) or malformed lines mean the corpus itself is damaged —
        # the silently-dropped copy could be the true one (D-109; corpus_health
        # classifies both as ERROR).
        integrity = []
        if stats.get("conflicts"):
            integrity.append(f"conflicting run_id × {len(stats['conflicts'])}: "
                             + ", ".join(stats["conflicts"][:5]))
        if stats.get("malformed"):
            integrity.append(f"malformed lines × {stats['malformed']}")
        if integrity:
            print("语料完整性 FAIL：" + "；".join(integrity)
                  + " —— 拒绝出报告（先用 corpus_health.py 诊断；"
                    "确需强行出报告用 --skip-contract-check）", file=sys.stderr)
            return 1
        errors = contract_gate(recs)
        if errors is None:
            print("⚠ 契约门未执行（schema 不可读）——本报告输入未经校验", file=sys.stderr)
        elif errors:
            print(f"契约门 FAIL：{len(errors)} 条违规——拒绝出报告（这不是 result-run 语料，"
                  "或生产者已破坏契约；确需强行出报告用 --skip-contract-check）", file=sys.stderr)
            for e in errors[:10]:
                print("  - " + e, file=sys.stderr)
            if len(errors) > 10:
                print(f"  … 其余 {len(errors) - 10} 条略", file=sys.stderr)
            return 1
    params = {"min_samples": args.min_samples, "attr_kpi": args.attr_kpi,
              "campaign": args.campaign, "before": args.before, "after": args.after}
    prov = prov_mod.compute(files, stats, params, generated_at=now,
                            thresholds=effective_thresholds())

    md = build_report_markdown(recs, args.min_samples, args.attr_kpi, args.before,
                               args.after, provenance=prov)
    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"markdown -> {args.md} (records={len(recs)})")
    else:
        print(md)
    if args.html:
        out = build_report_html(recs, now, args.min_samples, args.attr_kpi, args.before,
                                args.after, provenance=prov)
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"html -> {args.html}")
    if args.csv:
        paths = write_csv_tables(recs, args.csv, args.min_samples,
                                 before_id=args.before, after_id=args.after)
        print("csv -> " + ", ".join(paths))
    if args.provenance:
        prov_mod.write_sidecar(prov, args.provenance)
        print(f"provenance -> {args.provenance}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
