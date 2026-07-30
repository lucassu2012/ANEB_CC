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
import os
import re
import sys
from collections import Counter, defaultdict

import campaign_common as cc
import attribution
import buffering_rollup
import order_effect
import provenance as prov_mod
import radio_rollup
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


# The boundary-of-claim line, in ONE place because both surfaces owe the reader
# the same sentence (D-262). D-140 already found that notices living in the
# markdown preamble never reach the HTML and fixed the corpus warnings; this
# banner was the same shape, still markdown-only — so the page most likely to be
# forwarded to a stakeholder stated the boundary only in its footer (D-323).
CLAIM_SCOPE_NOTE = ("claim_scope: `application_end_to_end_to_probe_node` — "
                    "应用层端到指定节点路径；**不表述为** MOS / 无线层评级 / "
                    "运营商全网 SLA。")


# ---------------------------------------------------------------- inventory

# The subset of VALUE_RANGES that lives on a scenario's kpi map. The rest sit on
# other blocks (aqs.score, aqs.sub_scores, scenarios[].buffering) and are swept
# from where they actually live — asking scenario_kpi for "sub_score" would
# always return None, i.e. a check that quietly never runs (§2.9).
_SCENARIO_KPI_RANGES = ("t1_ttft_ms", "t2_itl_p95_ms", "t3_stall_rate",
                        "t4_severe_stall_rate", "n1_rtt_p50_ms", "n2_jitter_ms",
                        "u1_goodput_mbps", "u2_tool_loop_p95_ms")


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
        # who put the grouping labels there: declared by the operator, or
        # inferred by a rule of thumb? time_band is a heat-card dimension and a
        # standard finding ("忙时比闲时差 N 分"), so this decides how much that
        # finding is worth (D-153). Written by annotate_campaign, read by no one
        # until now.
        "label_sources": Counter(),
        # earliest run per campaign — before/after ordering is a CHRONOLOGY
        # question, and campaign_id sort need not match time (D-161)
        "campaign_first_ms": {},
        # …and a timestamp only answers that question if it is a plausible
        # millisecond epoch. A seconds-valued one sorts its campaign to 1970 and
        # inverts every delta while the basis still reads "time" (D-176).
        "implausible_ms": Counter(), "campaigns_bad_ms": set(),
        # values that are impossible rather than merely bad — an AQS of 9999
        # bands as `excellent`, a negative metro RTT manufactures backbone
        # latency in the differential (D-178)
        "implausible_values": Counter(),
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
        aqs_v = cc.run_aqs(rec)
        if aqs_v is not None:
            inv["aqs_present"] += 1
            bad_v = cc.value_problem("aqs_score", aqs_v)
            if bad_v:
                inv["implausible_values"][f"aqs_score{bad_v}"] += 1
        for dim, sv in (cc.run_sub_scores(rec) or {}).items():
            bad_v = cc.value_problem("sub_score", sv)
            if bad_v:
                inv["implausible_values"][f"sub_score.{dim}{bad_v}"] += 1
        for scn in cc.iter_scenarios(rec):
            for kpi in _SCENARIO_KPI_RANGES:
                bad_v = cc.value_problem(kpi, cc.scenario_kpi(scn, kpi))
                if bad_v:
                    inv["implausible_values"][f"{kpi}{bad_v}"] += 1
            buf = cc.scenario_buffering(scn) or {}
            for field, range_key in (("score", "buffering_score"),
                                     ("sawtooth_ratio", "sawtooth_ratio"),
                                     ("near_zero_arrival_ratio", "near_zero_arrival_ratio")):
                bad_v = cc.value_problem(range_key, buf.get(field))
                if bad_v:
                    inv["implausible_values"][f"buffering.{field}{bad_v}"] += 1
        started = cc.run_started_ms(rec)
        cid = labels["campaign_id"]
        # Kept in campaign_first_ms even when implausible — dropping it would
        # hide the problem, and the report exists to surface it (R-10).
        bad = cc.epoch_ms_problem(started)
        if bad:
            inv["implausible_ms"][bad] += 1
            inv["campaigns_bad_ms"].add(cid)
        if started is not None and (cid not in inv["campaign_first_ms"]
                                    or started < inv["campaign_first_ms"][cid]):
            inv["campaign_first_ms"][cid] = started
        src = (cc.run_obj(rec).get("campaign") or {}).get("label_source")
        inv["label_sources"][src if isinstance(src, str) and src else "declared"] += 1
    # labels that are probably one label typed two ways: they split a cell in
    # two and the split is invisible in the rendered table (D-149)
    inv["label_collisions"] = cc.label_collisions(records)
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
    for field, groups in sorted((inv.get("label_collisions") or {}).items()):
        shown = "；".join(
            " / ".join(f"`{v}`" for v in variants) for _, variants in sorted(groups.items()))
        out.append(f"**{field} 标签疑似同名异写**：{shown}。"
                   "它们被当作**不同的格**统计（各分走一部分样本，可能都因此被标 `low_conf`），"
                   "而渲染出来几乎看不出区别。**这不是自动合并的**——"
                   "确属同一对象请回改语料后重出报告，确属不同对象请改成可区分的名字。")
    bad_vals = inv.get("implausible_values") or {}
    if bad_vals:
        n_bad = sum(bad_vals.values())
        out.append(f"**{n_bad} 个取值在物理/定义上不可能**"
                   f"（{'；'.join(f'{r} × {n}' for r, n in sorted(bad_vals.items()))}）。"
                   "**这不是「测得很差」,是根本不是一次测量**——AQS 定义在 0~100,"
                   "时延不可能为负,卡顿率是 0~1 的分数。此类值**已排除出中位数**"
                   "(留在各格计数里,受影响的格标 `IMPLAUSIBLE_VALUE`),"
                   "因为它不只拉低一个中位:metro 中位为负会让差分**凭空造出一段骨干时延**。"
                   "**注意波及面**:同一生产者写出过不可能的值,它同时写出的其他值也不可信,"
                   "该格的结论请整体存疑而不是只扣掉这几条。")
    bad_ms = inv.get("implausible_ms") or {}
    if bad_ms:
        total = inv.get("records") or 1
        n_bad = sum(bad_ms.values())
        out.append(f"**{n_bad}/{total} 条记录的 `started_at_epoch_ms` 不像毫秒时间戳**"
                   f"（{'；'.join(f'{r} × {n}' for r, n in sorted(bad_ms.items()))}）。"
                   "该字段决定**前后配对的先后**、报告顶部的**采集时间窗**、"
                   "「层级同时性」判定与 `--infer-time-band` 的推断——"
                   "**一个数量级写错不会报错,只会安静地给出错误的先后**"
                   "（秒当毫秒会把该战役排到 1970,于是改善被印成回退）。"
                   "工具**不猜测也不换算**：受影响的战役不参与自动配对,请先修生产端。")
    inferred_tb = sum(n for src, n in (inv.get("label_sources") or {}).items()
                      if "inferred:time_band" in src)
    if inferred_tb:
        total = sum((inv.get("label_sources") or {}).values()) or 1
        out.append(f"**`time_band` 有 {inferred_tb}/{total} 条是工具推断的**"
                   "（按 `started_at_epoch_ms` 的本地小时,非现场记录;规则与所用时区偏移见"
                   "「覆盖盘点」的 `label_source`）。忙闲差异的结论**须注明这一点**——"
                   "推断错时段会把两类流量混在一起,而表面上看不出来。")
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
    labeled_ids = [c for c in inv["campaigns"] if c != cc.UNLABELED]
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


def _sign(x):
    """-1 / 0 / +1 — what a delta's verdict turns on (D-207)."""
    return (x > 0) - (x < 0)


def _located(cell):
    """Whether this cell is somewhere an operator could actually be sent.

    Records with no `point_id` collapse into the `unlabeled` bucket, and the
    summary ranked that bucket alongside real points — so a corpus whose only bad
    scores were unlabelled produced the headline「体验最差格 ——
    unlabeled/unknown/unknown(41)」: the city's worst place, with no name, and
    nobody to send (D-211). Carrier and time_band may be unknown and the cell is
    still a place; the point id is what makes it one.
    """
    return (cell or {}).get("point_id") not in (None, "", cc.UNLABELED)


_UNLOCATED_MARK = "无点位标签"

_UNLOCATED_LEGEND = (
    f"> 下方带「**{_UNLOCATED_MARK}**」计数的条目：那些格落在 `{cc.UNLABELED}` 桶——"
    "**它不是一个地点，据此派不出人**，所以它们不参与点名；"
    "先用 `annotate_campaign.py` 补注 `point_id` 再看那几条。")


def _unlocated_note(n, what="格"):
    """Say what was set aside from a ranking, and why it is not a destination.

    The why is said once, by _UNLOCATED_LEGEND above the bullets. Each bullet
    keeps its own count — the sets differ per bullet (D-211) — but repeating
    the full explanation put 60 characters of identical boilerplate into four
    of the eleven lines of the one section titled 先看这里 (D-217).
    """
    return (f"；另有 **{n} 个{what}{_UNLOCATED_MARK}**（不可定位，未参与本条点名）"
            if n else "")


def _confidence_caveat(scored, min_samples):
    """How much of the surveyed population is below the sample floor.

    D-300 put the population on the headline; a day cut short then showed the
    other half of the same problem. Every cell at n=3 produced a first line
    word-for-word identical to a full n=11 round — 「32 个格中无 fair/poor」 —
    and nothing said that not one of those 32 numbers meets the floor. The count
    is stated rather than a threshold invented: `low_confidence` is already
    decided per cell by heat_cells, this only refuses to keep it quiet (D-313).
    """
    low = sum(1 for c in scored if c.get("low_confidence"))
    if not low:
        return ""
    if low == len(scored):
        return (f"——但这 **{low} 个格全部 low_confidence**（每格 n<{min_samples}），"
                "**本轮不足以判定好坏**，先把样本补够再读这一条")
    return f"——其中 **{low} 个格 low_confidence**，不要据它们判定好坏"


_SEG_NAMES = {"access_component": "接入", "regional_backbone_incr": "区域骨干",
              "core_backbone_incr": "核心骨干"}

# What each segment-profile basis actually screened on. The summary named "3σ"
# unconditionally, but a segment where over half the cells share one value has no
# usable sigma at all — segment_profile falls back to "differs from the common
# value" and says so in its own section, while the summary was still crediting a
# screen that had not been run (D-199). The table that fixed it was then hand-
# written a second time next to the section's own, and drifted: D-200 retired the
# fixed 3σ for a calibrated K and only the section was updated (D-301). One side
# derived, never two — attribution owns the screen, so attribution names it.
def _basis_text(segments):
    return attribution.screen_basis_label(segments)


def _segment_tally(attr):
    """(dominant Counter, worst (label, value), not_computable, unusable).

    Cells the matrix marks NOT USABLE are counted, not read. Those rows print
    「该格增量不可用」 next to the very numbers this bullet quotes — a mixed-media
    cell's "core backbone increment" is a wifi/cellular gap wearing the backbone's
    name (D-157) — and the summary used to pick the corpus maximum without ever
    asking whether its own row disowned it (D-199).
    """
    dominant, not_computable, unusable = Counter(), 0, 0
    worst = None
    for c in attr["cells"]:
        if any(attribution.is_severe(f) for f in attribution.incomparability_flags(c)):
            unusable += 1
            continue
        parts = {k: c[k] for k in _SEG_NAMES if c[k] is not None}
        if not parts:
            not_computable += 1
            continue
        top = max(parts, key=lambda k: parts[k])
        dominant[_SEG_NAMES[top]] += 1
        if worst is None or parts[top] > worst[1]:
            worst = (f"{_cell_label(c['cell'], attr['group_by'])}·{_SEG_NAMES[top]}",
                     parts[top])
    return dominant, worst, not_computable, unusable


def _cross_kpi_note(records, attr_kpi, dominant, min_samples):
    """Whether the OTHER attributable KPIs point at the same segment.

    The bullet reads as the report's answer to "which part of the path is the
    problem", but it is computed from one KPI — and the matrix section right
    below it renders every attributable KPI. When they disagree, one of the two
    tables contradicts the summary and the reader has no way to know which
    (D-199). Naming the KPI is half the fix; saying that the other one differs is
    the other half.
    """
    if not dominant:
        return ""
    mine = cc.ranked(dominant)[0][0]
    differs = []
    for k in attribution.ATTRIBUTABLE_KPIS:
        if k == attr_kpi:
            continue
        other, _, _, _ = _segment_tally(
            attribution.attribute(records, kpi=k, min_samples=min_samples))
        if other and cc.ranked(other)[0][0] != mine:
            differs.append(f"`{k}` 指向 **{cc.ranked(other)[0][0]}**")
    if not differs:
        return ""
    return ("；⚠ **换一个 KPI 结论就变**：" + "、".join(differs)
            + "——本条只据 `" + attr_kpi + "` 得出，"
            "主导段随 KPI 改变时**不可当作单一结论**（见各 KPI 的归因矩阵）")


def render_summary_markdown(records, min_samples=cc.DEFAULT_MIN_SAMPLES,
                            attr_kpi=attribution.DEFAULT_KPI):
    """Signal before evidence (D-117).

    At M2 grid scale the report is ~1600 lines; the findings that decide what to
    do next — bad cells, distortion hot-spots, suspect clocks, low validity,
    unstable cells — were buried in the middle of it. This lifts them to the top.
    It only points INTO the detailed sections below; nothing is hidden, and the
    distinction between "no problem" and "no data" is kept explicit (R-10).
    """
    lines = ["## 摘要（先看这里）", "",
             # One promise, made once, machine-checked for every bullet. Before
             # D-208 only 优化前后 sorted its examples (D-182); the rest listed
             # whichever cells came first by label, so「172 单元超 CV 门 —— A、B、C
             # 等 172 个」named three cells at CV 23% while the worst sat at 39%.
             # The reader goes and looks at the ones you named.
             "> 下列每条中的示例均为该项**最严重的前三个**（其余以「等 N 个」计数，"
             "完整清单见对应段落与 CSV）。", ""]
    bullets = []

    cells = heat_cells(records, min_samples)
    scored = sorted((c for c in cells if c["aqs_median"] is not None),
                    key=lambda c: c["aqs_median"])
    # a cell built on one run used to head the list of the city's worst points
    # with nothing saying so — the heat card flagged it, the summary did not
    # (D-168). The summary is the only section decision-makers read closely.
    # "bad" is every grade ranked below good, read off cc.GRADE_ORDER rather
    # than spelled out a second time here: that constant exists to be the one
    # place saying which grades are worse than which, and had no reader at all
    # until this line (D-266).
    worse_than_good = cc.GRADE_ORDER[cc.GRADE_ORDER.index("good") + 1:]
    bad_cells = [c for c in scored if c["grade"] in worse_than_good]
    weak = [f"{_cell_label(c['cell'])}({cc.fmt_num(c['aqs_median'], 1)}"
            + (f"，n={c['n']} low_conf" if c["low_confidence"] else "") + ")"
            for c in bad_cells if _located(c["cell"])]     # rankable places only
    weak_unloc = _unlocated_note(sum(1 for c in bad_cells if not _located(c["cell"])))
    if not scored:
        bullets.append("**体验最差格**：无 AQS 数据（覆盖缺口，非全部良好）。")
    elif bad_cells:
        # a veto caps the score at exactly the band edges, so "fair/poor" can
        # mean the sessions failed rather than the network being slow (D-154)
        capped = [c for c in bad_cells if c.get("veto_n")]
        veto_note = (f"；其中 {len(capped)} 个格含**被否决封顶**的 run"
                     "（T4 严重卡顿率 >1% 封顶 54，分数只说明「至少这么差」，"
                     "见热力卡 `VETO_CAPPED`）"
                     if capped else "")
        # keyed on bad_cells, not on `weak`: when EVERY bad cell is unlabelled,
        # `weak` is empty and the old branch fell through to 「无 fair/poor 格」 —
        # reporting no problem at all because the problems had no address
        if weak:
            tail = f" —— {_top(weak)}{veto_note}{weak_unloc}"
        else:
            tail = ("，**全部无点位标签**（落在 `" + cc.UNLABELED + "` 桶——"
                    "**它不是一个地点**，据此派不出人；先用 `annotate_campaign.py` "
                    "补注 `point_id` 再看本条）" + veto_note)
        bullets.append(f"**体验最差格**：{len(bad_cells)}/{len(scored)} 个格"
                       f" AQS 达 fair/poor{tail}{_confidence_caveat(scored, min_samples)}。")
    else:
        # The population, on the report's first line. Day one of a field trip may
        # come back with a single cell, and 「无 fair/poor 格」 over a set of one
        # reads like a survey that found nothing — the shape D-229 fixed for the
        # transport section (「没有可比的格」≠「比过了没问题」) and D-297 for the
        # stability ratio. No threshold is invented here: print the denominator
        # and let the reader see that 共 1 个格 is not a finding (D-300).
        #
        # The denominator alone was not enough. A day cut short gives every cell
        # n=3, and this line then read identically to a full n=11 round — same
        # words, same reassurance, not one cell meeting the sample floor. The
        # naming site also skipped D-168's 「n=… low_conf」 mark, which the other
        # branch has carried since (D-313).
        best = scored[0]
        mark = f"，n={best['n']} low_conf" if best["low_confidence"] else ""
        bullets.append(f"**体验最差格**：{len(scored)} 个格中无 fair/poor（最低 "
                       f"{_cell_label(best['cell'])}="
                       f"{cc.fmt_num(best['aqs_median'], 1)}{mark}）"
                       f"{_confidence_caveat(scored, min_samples)}。")

    # The report is titled "heat card AND ATTRIBUTION"; the summary told the
    # reader which cells are bad but never which path segment caused it — the
    # whole point of the attribution matrix (D-142).
    attr = attribution.attribute(records, kpi=attr_kpi, min_samples=min_samples)
    dominant, worst, not_computable, unusable = _segment_tally(attr)
    if not attr["cells"]:
        bullets.append(f"**分段归因**：无可归因单元（`{attr_kpi}` 缺数据或缺层级）。")
    elif not dominant:
        why = []
        if unusable:
            why.append(f"{unusable} 个格带**不可用标记**（见归因矩阵）")
        if not_computable:
            why.append(f"{not_computable} 个格不可计算（层级缺失，记 TIER_MISSING，不外推）")
        bullets.append(f"**分段归因**（`{attr_kpi}`）：无可读的格——" + "；".join(why) + "。")
    else:
        tail = f"；另有 {not_computable} 个格不可计算" if not_computable else ""
        if unusable:
            # The matrix prints 「该格增量不可用」 on exactly these rows, and this
            # bullet used to quote the largest number in the corpus without ever
            # asking whether its row said that — so the headline attribution
            # figure could be one the tool had already disowned (D-199).
            tail += (f"；**{unusable} 个格因不可比标记未计入**"
                     "（混介质/层级不同时/层级端点冲突/封顶/不可能取值——见归因矩阵）")
        # "core dominates in 4 cells, biggest is P1's 27ms" reads as "P1's core is
        # the problem" — but if every cell's core segment is the same size, the
        # segment is a property of the measured path and no cell is at fault.
        # That distinction decides whether anyone goes and looks at P1 (D-146).
        prof = attribution.segment_profile(attr)
        judged = [s for s in prof["segments"] if s["uniform"] is not None]
        pointy = [s for s in judged if not s["uniform"]]
        if not judged:
            spread_note = "；各段跨单元离差不可比较（可比单元不足）"
        elif not pointy:
            # "no cell crossed the screen" is not "the cells are alike" — say the
            # weaker true thing and point at the column that carries the rest.
            # The basis travels with it: on a zero-spread segment no 3σ screen was
            # run at all, and this line used to credit one by name (D-199).
            spread_note = (f"；各段**均未见单点异常**（判据：{_basis_text(judged)}）"
                           "——最大单项落在该段分布内，不宜单独归因于该单元"
                           "（单元间齐不齐见「分段异常定位」段）")
        else:
            spread_note = ("；**存在单点异常的段**："
                           + "、".join(s["label"] for s in pointy)
                           + f"（判据：{_basis_text(pointy)}）")
        bullets.append(f"**分段归因**（`{attr_kpi}`；主要贡献段）：" +
                       "、".join(f"{k} {v} 格" for k, v in cc.ranked(dominant)) +
                       (f"；最大单项 {worst[0]}={cc.fmt_num(worst[1], 1)}ms" if worst else "")
                       + spread_note + tail
                       + _cross_kpi_note(records, attr_kpi, dominant, min_samples) + "。")

    bres = buffering_rollup.analyze(records, min_samples)
    hot_cells = sorted((c for c in bres["cells"] if c["distortion_hotspot"]),
                       key=lambda c: -(c["suspect_share"] or 0))   # worst first (D-208)
    hot = [_cell_label(c["cell"]) for c in hot_cells if _located(c["cell"])]
    hot_unloc = _unlocated_note(sum(1 for c in hot_cells if not _located(c["cell"])))
    if not bres["cells"]:
        bullets.append("**批化失真**：无批化标注（覆盖缺口，非未见失真）。")
    elif hot_cells:
        # keyed on hot_cells, not on the NAMED subset: with every hot-spot
        # unlabelled, `hot` is empty and this used to print 「无热点格」 (D-211)
        bullets.append(f"**批化失真热点**：{len(hot_cells)} 个"
                       + (f" —— {_top(hot)}" if hot else "，**全部无点位标签**")
                       + f"{hot_unloc}。")
    else:
        bullets.append("**批化失真**：无热点格。")

    tres = trust_rollup.analyze(records, min_samples)
    clock_cells = sorted((c for c in tres["cells"] if c["clock_hotspot"]),
                         key=lambda c: -(c["clock_suspect_share"] or 0))
    clock_hot = [_cell_label(c["cell"]) for c in clock_cells if _located(c["cell"])]
    clock_unloc = _unlocated_note(
        sum(1 for c in clock_cells if not _located(c["cell"])))
    if tres["no_evidence"]:
        bullets.append("**测量可信度**：无 clock/seq/parse 证据（覆盖缺口，非全部可信）。")
    elif clock_cells:
        bullets.append(f"**时钟可疑热点**：{len(clock_cells)} 个"
                       + (f" —— {_top(clock_hot)}" if clock_hot else "，**全部无点位标签**")
                       + f"{clock_unloc}（该格时延中位数存疑）。")
    else:
        bullets.append("**时钟可疑热点**：无。")

    vres = validity_rollup.analyze(records)
    # validity cells are keyed on profile_id too — drop it and several cells
    # render as the same label, which the reader cannot act on (D-125)
    # worst first (D-208): the rate is printed right there, so listing the
    # mildest three is a contradiction the reader can see
    low_cells = sorted((c for c in vres["cells"] if c["below_min_rate"]),
                       key=lambda c: c["valid_rate"])
    low_valid = [_cell_label(c["cell"], ("point_id", "carrier", "time_band",
                                         "profile_id"))
                 + f"({c['valid_rate'] * 100:.0f}%)"
                 for c in low_cells if _located(c["cell"])]
    low_unloc = _unlocated_note(sum(1 for c in low_cells if not _located(c["cell"])))
    if not vres["cells"]:
        bullets.append("**有效率**：无场景数据。")
    elif low_cells:
        bullets.append(f"**有效率不达门**：{len(low_cells)} 个格"
                       + (f" —— {_top(low_valid)}" if low_valid else "，**全部无点位标签**")
                       + f"{low_unloc}。")
    else:
        bullets.append(f"**有效率**：全部达门（≥{vres['min_rate'] * 100:.0f}%）。")

    ranked_unstable, measured, no_cv = [], 0, 0
    for k in stability.DEFAULT_STABILITY_KPIS:
        for c in stability.stability_cells(records, k, min_samples=min_samples):
            if c["cv_percent"] is None:
                # counted, not dropped: the denominator below is measured cells
                # only, and every other bullet in this summary discloses its
                # not-computable remainder. This one did not, so 4 unjudgeable
                # cells out of 7 vanished behind「2/3 单元超 CV 门」(D-209).
                no_cv += 1
                continue
            measured += 1
            if c["unstable"]:
                # stability cells are keyed on tier+profile too — include them,
                # or the labels collapse into indistinguishable duplicates
                ranked_unstable.append((c["cv_percent"], _cell_label(
                    c["cell"], ("point_id", "carrier", "time_band", "tier",
                                "profile_id")) + f"·{k}", _located(c["cell"])))
    # highest CV first (D-208) — this list runs to 172 entries on the rehearsal
    # grid, and the three shown were the mildest of them
    ranked_unstable.sort(key=lambda t: -t[0])
    unstable = [lab for _cv, lab, _loc in ranked_unstable]
    named_unstable = [lab for _cv, lab, loc in ranked_unstable if loc]
    unstable_unloc = _unlocated_note(
        sum(1 for _cv, _lab, loc in ranked_unstable if not loc), what="单元")
    # the remainder, named where the reader sees the denominator (D-209)
    # points at the 备注 column's marker, not at a column of that name: the
    # stability header is 单元/n/中位/均值/CV%/稳定?/备注 and there is no
    # `CV 不可计算` column to look at (D-212)
    nocv_note = (f"；另有 **{no_cv} 个单元 CV 不可计算**（n<2 或均值≤0，**未计入分母**，"
                 "见稳定性段**备注**列的 `CV 不可计算` 标记）" if no_cv else "")
    if not measured:
        bullets.append(f"**复测稳定性**：{no_cv} 个单元**全部无法计算 CV**"
                       "（n<2 或均值≤0）——覆盖缺口，非「全部达门」。")
    else:
        bullets.append(
            f"**复测不稳定**：{len(unstable)}/{measured} 单元超 CV 门"
            + (f" —— {_top(named_unstable)}" if named_unstable
               else "，**全部无点位标签**")
            + f"{unstable_unloc}{nocv_note}。" if unstable else
            f"**复测稳定性**：{measured} 个单元全部达门{nocv_note}。")

    tr = transport_rollup.analyze(records, min_samples)
    # Δ<0 alone is not "cellular is worse" — it is a difference that may be
    # smaller than the repeat spread. On the rehearsal grid every one of the
    # seven cells this used to name was inside the noise (D-180). Three buckets,
    # so "cannot estimate" never gets counted as either answer.
    neg = [c for c in tr["cells"]
           if c["cellular_minus_wifi"] is not None and c["cellular_minus_wifi"] < 0]
    # most negative first (D-208) — the delta is printed beside each name
    worse = [f"{_cell_label(c['cell'])}(Δ{cc.fmt_num(c['cellular_minus_wifi'], 1)}"
             f"±{cc.fmt_num(c['noise'], 1)})"
             for c in sorted((c for c in neg if c["within_noise"] is False),
                             key=lambda c: c["cellular_minus_wifi"])]
    noisy = [c for c in neg if c["within_noise"] is True]
    unknown = [c for c in neg if c["within_noise"] is None]
    tail = ""
    if noisy or unknown:
        bits = ([f"{len(noisy)} 个格 Δ 在噪声内"] if noisy else []) + \
               ([f"{len(unknown)} 个格噪声不可估" for _ in [0]] if unknown else [])
        tail = "；另有 " + "、".join(bits) + "——**不作介质差异的结论**"
    if tr["only_unknown"]:
        bullets.append("**接入介质**：无 transport 证据（覆盖缺口）。")
    elif worse:
        bullets.append(f"**蜂窝劣于 wifi**：{len(worse)} 个格超出噪声 —— {_top(worse)}{tail}。")
    elif neg and not noisy:
        # Every negative delta's noise is unestimable, so not one of them was
        # ever compared to anything: "none exceeded the noise" would be a
        # finding drawn from zero measurements. publish_check.py's twin item
        # grew this branch at D-198; the summary the reader actually opens did
        # not, and on a corpus of one unestimable cell it printed a clean
        # negative verdict (D-216).
        bullets.append(f"**接入介质**：{len(neg)} 个格 Δ 为负，但其**噪声尺度全部不可估**"
                       "（样本不足或复测零离散）——**无法判断**是否存在超出噪声的介质差异，"
                       "本轮不作介质结论。")
    elif neg and unknown:
        bullets.append(f"**接入介质**：{len(neg)} 个格 Δ 为负；{len(noisy)} 个**在噪声内**、"
                       f"{len(unknown)} 个**噪声不可估**（未被判定，不计入结论）"
                       "——本轮**未观察到超出测量噪声的介质差异**。")
    elif neg:
        bullets.append(f"**接入介质**：{len(neg)} 个格 Δ 为负但**无一超出噪声尺度**"
                       f"（{len(noisy)} 个噪声内、{len(unknown)} 个不可估）"
                       "——本轮**未观察到超出测量噪声的介质差异**。")
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
                       "、".join(f"{d} {n} 格" for d, n in cc.ranked(drags)) + tail + "。")

    # "Did it get better" — the headline question of any second round (D-143).
    inv_ = inventory(records)
    before_id, after_id = auto_compare_ids(inv_)
    labeled = [c for c in inv_["campaigns"] if c != cc.UNLABELED]
    if before_id and after_id:
        rows = [r for r in compare_campaigns(records, before_id, after_id,
                                             min_samples)["rows"]
                if r["delta"] is not None]
        if not rows:
            bullets.append(f"**优化前后**：{before_id} → {after_id} 无共同单元可比。")
        else:
            # a change smaller than the measurement noise is not a change; a cell
            # whose noise cannot be estimated is neither one nor the other, so it
            # gets its own bucket rather than being counted as real (D-144, R-10)
            noisy = [r for r in rows if r.get("within_noise") is True]
            unknown = [r for r in rows if r.get("within_noise") is None]
            real = [r for r in rows if r.get("within_noise") is False]
            up = sum(1 for r in real if r["delta"] > 0)
            down = sum(1 for r in real if r["delta"] < 0)
            tail = ""
            if noisy:
                tail += f"；{len(noisy)} 个格 Δ 在噪声内（不作结论）"
            if unknown:
                tail += f"；{len(unknown)} 个格噪声无法估计（样本不足或复测零离散，不作结论）"
            # Every other signal names its examples; this one gave counts only,
            # so the reader learned that four cells improved but not WHICH — and
            # "where did it get better" is the question the round was run to
            # answer (D-182). Biggest movers first.
            named = ""
            if real:
                top = sorted(real, key=lambda r: -abs(r["delta"]))
                named = " —— " + _top([f"{_cell_label(r['cell'])}"
                                       f"(Δ{cc.fmt_num(r['delta'], 1)}"
                                       f"±{cc.fmt_num(r['noise'], 1)})" for r in top])
            bullets.append(f"**优化前后**（{before_id} → {after_id}）：{len(rows)} 个共同格中 "
                           f"{len(real)} 个 Δ 超出噪声——改善 {up}、回退 {down}、"
                           f"持平 {len(real) - up - down}{named}"
                           f"{tail}；AQS 中位Δ "
                           f"{cc.fmt_num(cc.median([r['delta'] for r in rows]), 1)}。")
    elif len(labeled) >= 3:
        tres = trend.analyze(records, min_samples=min_samples)
        verdict = Counter(c["direction"] for c in tres["cells"] if c["direction"])
        # cells with no direction are counted, not dropped: `if c["direction"]`
        # quietly lost 3 of 17 on a partially-labelled corpus, and the campaign
        # count came from `labeled` rather than the columns the trend actually
        # used, so the bullet said 3 campaigns for a 4-column table (D-210)
        undecided = sum(1 for c in tres["cells"] if not c["direction"])
        undecided_note = (f"；另有 **{undecided} 格不可计算**"
                          "（该格在少于 2 个战役里出现，见趋势段 `NEED_2_POINTS`）"
                          if undecided else "")
        bullets.append("**纵向趋势**（" + f"{len(tres['campaigns'])} 个战役）：" +
                       "、".join(f"{k} {v} 格" for k, v in cc.ranked(verdict))
                       + undecided_note + "。" if verdict else
                       "**纵向趋势**：各格在场点不足 2，方向不可计算。")
    elif compare_basis(inv_) == "no_timestamps":
        # two campaigns but no way to know which came first — guessing by name
        # is what inverted the sign in the first place (D-161)
        bullets.append(f"**优化前后**：语料含 2 个战役（{'、'.join(sorted(labeled))}）但"
                       "**缺 `started_at_epoch_ms`，无法确定先后**——不按名称猜，"
                       "请显式 `--before/--after` 后重出。")
    elif compare_basis(inv_) == "bad_timestamps":
        bullets.append(f"**优化前后**：语料含 2 个战役（{'、'.join(sorted(labeled))}）但"
                       "**`started_at_epoch_ms` 取值不像毫秒时间戳**（见语料级告警），"
                       "按它排序会把战役排到错误的先后上、把改善印成回退——**本轮不自动配对**；"
                       "先修生产端时间戳，或确认先后后显式 `--before/--after`。")
    else:
        # Every other signal says something even with no data ("无 transport
        # 证据（覆盖缺口）"). This one used to vanish, so the reader could not
        # tell a single-round corpus from a signal that got dropped (D-152).
        bullets.append(f"**优化前后**：本轮仅 {len(labeled) or '0'} 个战役，无前后可比"
                       "——「有没有变好」本轮**无法回答**（需第二轮在同样的格上复测）。"
                       if labeled else
                       "**优化前后**：语料无战役标签，无法判断轮次——先补注再看此项。")

    # Said once, and only when something below actually carries the count.
    if any(_UNLOCATED_MARK in b for b in bullets):
        lines += [_UNLOCATED_LEGEND, ""]
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
    flags = defaultdict(lambda: [0, 0])   # [veto-capped runs, scorer low-conf runs]
    tier_counts = defaultdict(Counter)    # which server tiers each cell pooled
    homo = {}                             # per-cell comparability accumulator
    implausible = defaultdict(Counter)    # {cell -> {reason -> count}}
    for rec in records:
        labels = cc.campaign_labels(rec)
        if campaign_id is not None and labels["campaign_id"] != campaign_id:
            continue
        aqs = cc.run_aqs(rec)
        if aqs is None:
            continue
        key = tuple(labels[d] for d in HEAT_DIMS)
        # AQS is defined on 0..100, and the grade bands have no upper guard: a
        # score of 9999 lands in `excellent` — the best grade in the report — with
        # nothing marking it. Out of the median, counted where it shows (D-178).
        bad = cc.value_problem("aqs_score", aqs)
        if bad:
            implausible[key][f"aqs_score{bad}"] += 1
            continue
        buckets[key].append(aqs)
        seen_campaigns.setdefault(key, set()).add(labels["campaign_id"])
        veto, scorer_lc = cc.run_aqs_flags(rec)
        flags[key][0] += int(veto)
        flags[key][1] += int(scorer_lc)
        if labels["tier"]:
            tier_counts[key][labels["tier"]] += 1
        # The heat card pooled wifi with cellular and quick with forensic while
        # the attribution matrix flagged the very same cell — one report, two
        # answers about one cell (D-166). Same accumulator, same markers.
        acc = homo.setdefault(key, cc.homogeneity_acc())
        cc.note_run_homogeneity(acc, rec)
        for scn in cc.iter_scenarios(rec):
            cc.note_homogeneity(acc, scn)
    # A heat cell pools whatever tiers it happened to measure. Cells that pooled
    # DIFFERENT tier sets are not comparable with each other: a point that never
    # got its `core` round measured is missing its worst tier, so its median
    # rises and it ranks as the best point in the corpus while being identical
    # to the others on every tier it did measure (D-165). Flag the difference,
    # not the pooling itself — every cell pooling all three is normal.
    corpus_tiers = set()
    for counts in tier_counts.values():
        corpus_tiers |= set(counts)
    cells = []
    # A cell whose every score was impossible would otherwise disappear from the
    # card without a word — the one outcome R-10 forbids.
    for key in sorted(set(buckets) | set(implausible)):
        vals = buckets.get(key) or []
        med = cc.median(vals)
        ids = sorted(seen_campaigns.get(key) or [])
        cells.append({
            "cell": dict(zip(HEAT_DIMS, key)),
            "aqs_median": med,
            "grade": cc.aqs_grade(med),
            "n": len(vals),
            "stdev": cc.stdev(vals),          # spread, for the noise scale (D-144)
            "low_confidence": len(vals) < min_samples,
            # a cell pooling a baseline round with an optimisation round shows a
            # median that is NEITHER of them — flag it, never hide it (D-135)
            "mixed_campaigns": ids if len(ids) > 1 else [],
            # the scorer's own verdicts on these runs: a veto CAPS the score at
            # 70/54, which are the grade-band edges, so a capped run lands on a
            # boundary and the cell's median characterises neither population
            "veto_n": flags[key][0],
            "scorer_low_conf_n": flags[key][1],
            "mixed_transports": cc.mixed_transports(homo.get(key)),
            "mixed_profile_versions": cc.mixed_flags(homo.get(key))[0],
            "mixed_histogram_edges": cc.mixed_flags(homo.get(key))[1],
            "mixed_modes": cc.mixed_run_flags(homo.get(key))[0],
            "mixed_profile_sources": cc.mixed_run_flags(homo.get(key))[1],
            "tier_mix": dict(cc.ranked(tier_counts.get(key) or Counter())),
            "missing_tiers": sorted(corpus_tiers - set(tier_counts.get(key) or ())),
            # same key the attribution cells use, so one shared flag list marks
            # both surfaces from one place (D-160)
            "implausible_values": dict(sorted((implausible.get(key) or {}).items())),
        })
    return cells


def heatcard_notes(cells):
    """Everything above the heat table, as plain strings.

    Single source for the two surfaces that render prose: markdown quotes them
    with '> ', HTML wraps them in <p class='warn'>. This is the D-160 fix applied
    here — the veto explanation used to live inside the markdown branch only, so
    the HTML pivot showed a bare '⚠封顶4' with nothing on the page saying what a
    capped score means."""
    notes = ["`离散(sd)` 是该格 AQS 的样本标准差。**中位相同、离散天差地别的两个格,"
             "读起来一模一样**——sd=0 的格每次都一样,sd=36 的格在 20 与 95 之间来回,"
             "两者的中位数不是同一种东西。<2 个样本时留 `—`(离散未知,不是 0)。"]
    if any(c.get("missing_tiers") for c in cells):
        notes.append("⚠ **各格池化的服务层级不一致**（标 `TIER_INCOMPLETE`）。热力卡按 "
                     "点位×运营商×时段 成格，每格把它**实际测到的层级**一起取中位——"
                     "所以缺了某一层的格，其中位数**与别的格不可比**：少测最慢的中心层，"
                     "该点位会凭空显得更好、甚至排到最前。跨点位比较前，先看该格缺了哪一层。")
    if any(c.get("veto_n") for c in cells):
        notes.append("⚠ **本卡含被否决封顶的 run**（markdown 标 `VETO_CAPPED`，HTML 卡上标 "
                     "`⚠封顶n`）。触发的是 **T4 严重卡顿率 > 1%** 一票否决，分数**封顶 54**"
                     "（语音模式下 M1 口到耳超红线同样置位、同一上限）——**这本身就是体验侧的"
                     "故障信号**。要点在于：封顶分**不是该格真实体验的度量**（它只说明「至少"
                     "这么差」），封顶与未封顶的 run 混在一格，其中位数**两种情形都不代表**；"
                     "下结论前先看该格的 `VETO_CAPPED:n/N`，并回到卡顿证据本身，而不是把它"
                     "当成一个普通低分。")
        notes.append("另注：**会话完成率否决（S1）本层看不到**——它写在 `run.aqs_token."
                     "s1_veto_applied`（仅 Token 模式产出），战役层不读该块，故「会话没跑成」"
                     "在本报告中**无法观测**（不是未发生）。")
    return notes


def render_heatcard_markdown(cells):
    lines = ["## 点位 × 忙闲 × 运营商 热力卡（AQS 中位）", ""]
    if not cells:
        lines.append("_无 AQS 数据可成卡（记录缺 run.aqs.score）。_")
        return "\n".join(lines)
    for n in heatcard_notes(cells):
        lines += ["> " + n, ""]
    lines += [
        "| 点位 | 运营商 | 时段 | AQS中位 | 离散(sd) | 分级 | n | 备注 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in cells:
        # ONE shared list for every marker, so the heat card, the attribution
        # matrix and the CSV filter column cannot disagree about the same cell.
        # TIER_INCOMPLETE / VETO_CAPPED / SCORER_LOW_CONF used to be appended
        # here instead, which is precisely why the CSV never carried them (D-181).
        note = "; ".join(attribution.md_flags(c)) or "—"
        lines.append(
            f"| {cc.md_cell(c['cell']['point_id'])} | {cc.md_cell(c['cell']['carrier'])} "
            f"| {cc.md_cell(c['cell']['time_band'])} | "
            # printed with just enough precision that it cannot land on the wrong
            # side of the grade printed beside it (D-207)
            f"{cc.fmt_num_agreeing(c['aqs_median'], cc.aqs_grade)} | "
            f"{cc.fmt_num(c['stdev'], 1)} | "
            f"{c['grade']} | {c['n']} | {note} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------- before/after

# Both moved to campaign_common so the transport comparison — the report's other
# difference-of-two-medians — computes and words its noise scale identically
# instead of growing a second version of the same idea (D-180).
_within_noise = cc.within_noise


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
        # Indicative noise scale for the delta, so a change smaller than the
        # measurement spread is not read as a finding (D-144). cc owns the maths
        # so this, the transport comparison and the sample-size planning side
        # cannot drift apart (D-180).
        def _se(cell):
            return cc.median_se(cell["stdev"], cell["n"]) if cell else None
        se_b, se_a = _se(b), _se(a)
        noise = ((se_b ** 2 + se_a ** 2) ** 0.5) if (se_b is not None and se_a is not None) else None
        rows.append({
            "cell": dict(zip(HEAT_DIMS, key)),
            "before": bm, "after": am, "delta": delta,
            "before_n": b["n"] if b else None,
            "after_n": a["n"] if a else None,
            "noise": noise,
            # Zero delta is not a change whatever the noise; and zero OBSERVED
            # spread cannot bound anything — `abs(delta) < 0` is False, so a
            # 1-point difference on flat repeats used to publish as a real
            # improvement, and Δ=0 itself counted as "beyond noise" (D-169).
            # D-144's own caveat already says ±0 does not mean "no noise".
            "within_noise": _within_noise(delta, noise),
            "low_confidence": bool((b and b["low_confidence"]) or (a and a["low_confidence"])
                                   or b is None or a is None),
        })
    return {"before_id": before_id, "after_id": after_id, "rows": rows}


# Lives in campaign_common (see there for why); aliased so existing references
# keep working and so there is provably one wording, not two that agree today.
NOISE_CAVEAT = cc.NOISE_CAVEAT


def render_comparison_markdown(cmp):
    lines = [f"## 优化前后对比（before=`{cmp['before_id']}` → after=`{cmp['after_id']}`，AQS 中位）", ""]
    if not cmp["rows"]:
        lines.append("_两战役无共同单元可比。_")
        return "\n".join(lines)
    lines += [
        "> **噪声尺度**：" + NOISE_CAVEAT,
        "",
        "| 点位 | 运营商 | 时段 | before | after | Δ | 备注 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in cmp["rows"]:
        d = r["delta"]
        arrow = ""
        if d is not None:
            arrow = " ↑" if d > 0 else (" ↓" if d < 0 else " =")
        if r.get("noise") is not None:
            arrow += f" ±{cc.fmt_num(r['noise'], 1)}"
        notes = []
        if r["within_noise"] is True:
            notes.append("**噪声内**")
        # Keyed on the verdict, not on the scale: a spread observed as zero also
        # judges nothing, and used to leave the row with no caveat at all. Two
        # causes, two words (D-224).
        elif r["within_noise"] is None and d is not None:
            notes.append(cc.noise_unjudgeable_note(r["noise"]))
        if r["before"] is None:
            notes.append("仅 after")
        if r["after"] is None:
            notes.append("仅 before")
        if r["low_confidence"]:
            notes.append("low_conf")
        bstr, astr, dstr, adds_up = cc.fmt_delta_row(r["before"], r["after"], d)
        if adds_up is False:
            notes.append("ROUNDING_UNRECONCILED")
        note = "; ".join(notes) or "—"
        lines.append(
            f"| {cc.md_cell(r['cell']['point_id'])} | {cc.md_cell(r['cell']['carrier'])} "
            f"| {cc.md_cell(r['cell']['time_band'])} | "
            f"{bstr} | {astr} | "
            # enough precision that the number cannot read as 0 while the note
            # beside it calls the difference real (D-207)
            f"{dstr}{arrow} | {note} |"
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
    buckets = defaultdict(lambda: {"vals": [], "grades": Counter(),
                                   "implausible": Counter()})
    for rec in records:
        labels = cc.campaign_labels(rec)
        key = tuple(labels[d] for d in HEAT_DIMS)
        for scn in cc.iter_scenarios(rec):
            v = cc.scenario_kpi(scn, kpi_key)
            if v is None:
                continue
            # Same rule as the AQS card one screen up (D-178), which this card
            # never got: a negative TTFT lowered the median AND the cell showed
            # the authoritative grade of the runs around it, so the row read as a
            # measured, graded result (D-197). The scenario's own *_grade goes
            # with it — that grade was computed FROM this value, so keeping it
            # would let the impossible reading vote on the cell's grade through
            # the one door the value itself was just refused at.
            if not cc.keep_value(kpi_key, v, buckets[key]["implausible"]):
                continue
            buckets[key]["vals"].append(v)
            g = (scn.get("kpi") or scn.get("kpis") or {}).get(gfield)
            if isinstance(g, str):
                buckets[key]["grades"][g] += 1
    mixed_by_cell = campaigns_by_cell(records)
    cells = []
    for key in sorted(buckets):
        b = buckets[key]
        # a tie is two populations, not a mode — reporting either one as THE
        # grade is a coin flip that the input file order decides (D-148)
        grade, tied = cc.modal(b["grades"])
        cells.append({
            "cell": dict(zip(HEAT_DIMS, key)), "kpi": kpi_key,
            "median": cc.median(b["vals"]), "grade": grade, "grade_tie": tied,
            "n": len(b["vals"]),
            "low_confidence": len(b["vals"]) < min_samples,
            "mixed_campaigns": mixed_by_cell.get(key, []),
            "implausible_values": dict(sorted(b["implausible"].items())),
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
        notes = []
        if c["grade_tie"]:
            notes.append("GRADE_TIE:" + "/".join(c["grade_tie"]))
        if c["mixed_campaigns"]:
            notes.append("MIXED_CAMPAIGN:" + "/".join(c["mixed_campaigns"]))
        if c.get("implausible_values"):
            notes.append("**IMPLAUSIBLE_VALUE:" + "; ".join(
                f"{r}×{n}" for r, n in sorted(c["implausible_values"].items())) + "**")
        if c["low_confidence"]:
            notes.append("low_conf")
        note = "; ".join(notes) or "—"
        lines.append(
            f"| {cc.md_cell(c['cell']['point_id'])} | {cc.md_cell(c['cell']['carrier'])} "
            f"| {cc.md_cell(c['cell']['time_band'])} | "
            f"{cc.fmt_num(c['median'], 2)} | {c['grade'] or '—'} | {c['n']} | {note} |")
    return "\n".join(lines)


# ---------------------------------------------------------------- assembly

def compare_basis(inv):
    """Why (or why not) a before/after pair could be formed automatically.

    "not_two" | "no_timestamps" | "bad_timestamps" | "time". Kept separate from
    the pair itself so a caller can say WHICH case it is instead of the section
    silently vanishing.
    """
    labeled = [c for c in inv["campaigns"] if c != cc.UNLABELED]
    if len(labeled) != 2:
        return "not_two"
    firsts = inv.get("campaign_first_ms") or {}
    if any(c not in firsts for c in labeled):
        return "no_timestamps"
    # An implausible epoch is worse than a missing one: it still sorts, so the
    # pair comes out confidently backwards. Refuse to order rather than order
    # by a number that is not a time (D-176).
    if any(c in (inv.get("campaigns_bad_ms") or set()) for c in labeled):
        return "bad_timestamps"
    return "time"


def auto_compare_ids(inv):
    """(before, after) for exactly two labeled campaigns, ordered by the EARLIEST
    run in each — never by campaign_id.

    Name sort is not chronology: a `pre-*` / `post-*` pair sorts post-before-pre,
    which inverted the sign of every delta on all three surfaces — a 30-point
    improvement published as `回退`, `AQS 中位Δ -30` (D-161). trend.py has
    ordered chronologically since it was written; this path just never did.
    Without timestamps the order is unknowable, so no pair is returned and the
    caller says so rather than guessing (「没法查」≠「查过了」).
    """
    if compare_basis(inv) != "time":
        return (None, None)
    labeled = [c for c in inv["campaigns"] if c != cc.UNLABELED]
    firsts = inv["campaign_first_ms"]
    a, b = sorted(labeled, key=lambda c: (firsts[c], c))
    return (a, b)


def build_report_markdown(records, min_samples=cc.DEFAULT_MIN_SAMPLES,
                          attr_kpi=attribution.DEFAULT_KPI,
                          before_id=None, after_id=None, kpi_heat=None,
                          provenance=None):
    # read live, not captured in the signature — archived in the provenance
    # manifest, which promises that changing it changes the report (D-204)
    kpi_heat = DEFAULT_KPI_HEAT if kpi_heat is None else kpi_heat
    inv = inventory(records)
    cells = heat_cells(records, min_samples)

    if before_id is None and after_id is None:
        before_id, after_id = auto_compare_ids(inv)

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
        "> " + CLAIM_SCOPE_NOTE,
        f"> 输入记录：{inv['records']}；含 run.aqs：{inv['aqs_present']}；"
        f"含 campaign 标签：{inv['with_campaign']}。样本地板 min_samples={min_samples}。",
        "",
        "## 覆盖盘点",
        "",
        # dict(Counter) renders in insertion order, i.e. in the order the files
        # happened to be read — the same corpus in a different order produced a
        # different report, contradicting this report's own reproducibility
        # claim (D-148). Count desc, then key asc, always.
        f"- 战役 campaign_id：{dict(cc.ranked(inv['campaigns']))}",
        f"- 点位 point_id：{dict(cc.ranked(inv['points']))}",
        f"- 运营商 carrier：{dict(cc.ranked(inv['carriers']))}",
        f"- 时段 time_band：{dict(cc.ranked(inv['time_bands']))}",
        f"- 服务层级 tier：{dict(cc.ranked(inv['tiers']))}",
        f"- run 状态 status：{dict(cc.ranked(inv['statuses']))}",
        f"- profile 版本：{dict(cc.ranked(inv['profile_version_sets']))}",
        f"- 标签来源 label_source：{dict(cc.ranked(inv['label_sources']))}",
        f"- 采集时间窗：{_utc_stamp(inv['first_ms']) or '—'} → "
        f"{_utc_stamp(inv['last_ms']) or '—'}"
        + ("" if inv["first_ms"] is not None else "（记录缺 started_at_epoch_ms）")
        # A 1970 endpoint is arithmetic on a bad number, not a measurement window;
        # printed bare it reads as a fact about when the data was collected.
        + ("" if not inv.get("implausible_ms") else
           f"（⚠ 含 {sum(inv['implausible_ms'].values())} 条不像毫秒时间戳的取值，"
           "**此窗口不可信**，见语料级告警）"),
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
    else:
        # A silently absent section cannot be told apart from one that did not
        # apply — the same rule the summary follows for 优化前后 / 纵向趋势
        # (D-150/152). Without this, a report that forgot --provenance looks
        # complete while carrying a claim it cannot support: the appendix
        # promises "same input + same thresholds = same numbers", and the
        # thresholds are exactly what this block archives (D-122, D-194).
        parts += [
            "## 溯源 / provenance（可复现性）",
            "",
            "> ⚠ **本报告未生成溯源信息**（出报告时未给 `--provenance PATH`）。"
            "**输入文件 sha256、读取/去重/坏行计数、本次的生效门限**因此都没有归档——"
            "没有它们，本报告**无法复现，也不应进入归档**"
            "（附录那句「同样的输入 + 同样的生效门限 = 同样的数字」正是靠这一段成立的）。"
            "补法：加 `--provenance provenance.json` 重出一次。",
            "",
        ]
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
            # The matrix alone cannot separate "this point is slow on that
            # segment" from "every point is" — and those are different fixes.
            parts.append(attribution.render_segment_profile_markdown(
                attribution.segment_profile(attr)))
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
    # Radio context: the first covariate the post-D-48 fallback names, and the
    # section renders even when the corpus carries none — that absence is the
    # finding, and burying it would let a wiring gap read as "signal was fine".
    parts.append(radio_rollup.render_markdown(radio_rollup.analyze(records, min_samples)))
    parts.append("")
    if before_id and after_id:
        parts.append(render_comparison_markdown(
            compare_campaigns(records, before_id, after_id, min_samples)))
        parts.append("")
    # 3+ labeled campaigns: before/after can't express a trajectory — add one. (D-98)
    # The threshold comes from trend so this gate, trend's own renderer and the
    # CSV writer cannot disagree about when a trend exists (D-196).
    labeled = [c for c in inv["campaigns"] if c != cc.UNLABELED]
    if len(labeled) >= trend.MIN_CAMPAIGNS_FOR_TREND:
        parts.append(trend.render_markdown(trend.analyze(records, min_samples=min_samples)))
        parts.append("")
    else:
        # The corpus banner names 纵向趋势 among the two campaign-aware sections,
        # and below three campaigns the section simply was not there: a reader
        # sent looking for it found nothing, and no reason. §2.4 and D-150's
        # 恒出行, applied to a whole section rather than a row (D-271).
        parts.append("## 纵向趋势")
        parts.append("")
        parts.append(
            f"> **本段无数据，不是「全部平稳」。** 本语料有 **{len(labeled)} 个带标签战役**，"
            f"而趋势需要至少 **{trend.MIN_CAMPAIGNS_FOR_TREND}** 个才能表达轨迹——"
            "两个只够说前后（见「优化前后对比」段），第三轮起本段自动出现。")
        parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------- HTML

def _heat_grid_html(cells, value_key="aqs_median", agree=None):
    """Pivot: rows = point_id × carrier, cols = time_band, colored by grade.
    value_key selects the numeric shown (aqs_median for the AQS card, median for
    per-KPI cards).

    `agree` is the verdict the printed number must not contradict (D-207). The
    AQS card passes cc.aqs_grade, because its grade is derived from this very
    number; the per-KPI cards pass nothing, because their grade comes from the
    producer's own `*_grade` field and no rounding of the median can disagree
    with it."""
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
            # An unknown word used to borrow the "n/a" grey, so a cell WITH data
            # wore the no-data colour while printing its own unfamiliar grade
            # (D-298). One colour, one meaning; the mark carries it in print too.
            bg, fg, unknown_mark = cc.grade_swatch(grade)
            lc = (f" {unknown_mark}" if unknown_mark else "") \
                + (" *" if c["low_confidence"] else "") \
                + (" ⚠混战役" if c.get("mixed_campaigns") else "") \
                + (f" ⚠封顶{c['veto_n']}" if c.get("veto_n") else "") \
                + (" ⚠缺" + "/".join(c["missing_tiers"]) if c.get("missing_tiers") else "") \
                + (" ⚠并列" + "/".join(c["grade_tie"]) if c.get("grade_tie") else "") \
                + (f" ⚠自评低置信{c['scorer_low_conf_n']}"
                   if c.get("scorer_low_conf_n") else "")
            sd = (f" · sd={cc.fmt_num(c['stdev'], 1)}"
                  if c.get("stdev") is not None else " · sd—")
            shown = (cc.fmt_num_agreeing(c[value_key], agree, digits=2)
                     if agree is not None else cc.fmt_num(c[value_key], 2))
            tds.append(f"<td style='background:{bg};color:{fg}'><b>{shown}</b>"
                       f"<span class='sub'>{esc(grade)} · n={c['n']}{sd}{lc}</span></td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    return f"<div class='scroll'><table>{head}{''.join(body)}</table></div>"


def _attr_table_html(attr):
    """One three-tier attribution table as HTML."""
    rows = []
    for c in attr["cells"]:
        cell_label = " · ".join(f"{k}={v}" for k, v in c["cell"].items())
        cov = ",".join(cc.TIER_LABELS.get(t, t) for t in c["coverage"]) or "—"
        # same list markdown and CSV use — this hand-maintained duplicate is how
        # MIXED_TRANSPORT and the tier-time markers went missing here (D-160)
        notes = attribution.incomparability_flags(c)
        severe = [f for f in notes if attribution.is_severe(f)]
        # The markdown renderer got this at D-219 and this hand-maintained copy
        # did not, so 39% of three-tier rows still failed the addition here
        # while the markdown deliverable was clean (D-222).
        (access, regional, core), e2e, adds_up = cc.fmt_parts_summing(
            (c["access_component"], c["regional_backbone_incr"],
             c["core_backbone_incr"]), c["end_to_end_core"])
        if adds_up is False:
            notes = notes + ["ROUNDING_UNRECONCILED"]
        rows.append(
            f"<tr><td class='lbl'>{esc(cell_label)}</td><td>{esc(cov)}</td>"
            f"<td>{access}</td>"
            f"<td>{regional}</td>"
            f"<td>{core}</td>"
            f"<td>{e2e}</td>"
            + (f"<td class='warn'><b>{esc('; '.join(notes))}</b></td></tr>" if severe
               else f"<td>{esc('; '.join(notes) or '—')}</td></tr>"))
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


_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


def _split_md_row(line):
    """Cells of one markdown table row, splitting on UNESCAPED pipes only.

    `cc.md_cell` escapes a literal pipe in a human-typed label as `\\|` so the
    markdown table survives it (D-128). A naive split("|") treats that escape as
    a separator, producing one extra cell and shifting every later value one
    column right — for the row carrying the unusual label, i.e. exactly the row
    worth reading. Markdown and CSV were always right; only the HTML deliverable
    (the sendable one) was wrong (D-195).

    The escape is a markdown-table concern, so it is undone here: HTML shows the
    label's real name, and esc() handles the HTML-special characters."""
    inner = line[1:] if line.startswith("|") else line
    if inner.endswith("|") and not inner.endswith("\\|"):
        inner = inner[:-1]
    return [c.strip().replace("\\|", "|") for c in _UNESCAPED_PIPE.split(inner)]


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
            cells_ = _split_md_row(s)
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
        before_id, after_id = auto_compare_ids(inv)

    # The sd/tier/veto notes live above the table in markdown; the HTML path
    # rebuilds only the grid, so they are emitted here from the same source —
    # otherwise the pivot shows '⚠封顶4' with no legend anywhere (D-160).
    heat_notes_html = "".join(f"<p class='warn'>{_md_inline(n)}</p>"
                              for n in heatcard_notes(cells)) if cells else ""

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
            attr_sections += (f"<h2>三级差分归因矩阵（{esc(k)}，ms）</h2>"
                              # the premise checklist and the tier-less coverage
                              # line live above the table in markdown; the HTML
                              # path rebuilds only the table, so they have to be
                              # emitted here from the same source (D-160)
                              + "".join(f"<p class='warn'>{_md_inline(n)}</p>"
                                        for n in attribution.premise_notes(attr))
                              + _attr_table_html(attr))

    cmp_html = ""
    if before_id and after_id:
        cmp = compare_campaigns(records, before_id, after_id, min_samples)
        crows = []
        for r in cmp["rows"]:
            d = r["delta"]
            # a sub-noise delta must not be coloured like a result (D-144)
            if r["within_noise"] is not False:
                color = "#666"
            else:
                color = "#137333" if (d is not None and d > 0) else ("#c5221f" if (d is not None and d < 0) else "#444")
            notes = []
            if r["within_noise"] is True:
                notes.append("噪声内")
            elif r["within_noise"] is None and d is not None:
                notes.append(cc.noise_unjudgeable_note(r["noise"]))   # same as md
            if r["before"] is None:
                notes.append("仅 after")
            if r["after"] is None:
                notes.append("仅 before")
            if r["low_confidence"]:
                notes.append("low_conf")
            # same rule as markdown: the row's subtraction has to hold
            bstr, astr, dstr, adds_up = cc.fmt_delta_row(r["before"], r["after"], d)
            if adds_up is False:
                notes.append("ROUNDING_UNRECONCILED")
            note = "; ".join(notes)
            crows.append(
                f"<tr><td class='lbl'>{esc(r['cell']['point_id'])} · {esc(r['cell']['carrier'])} · "
                f"{esc(r['cell']['time_band'])}</td><td>{bstr}</td>"
                f"<td>{astr}</td>"
                f"<td style='color:{color};font-weight:600'>{dstr}</td>"
                f"<td>{('±' + cc.fmt_num(r['noise'], 1)) if r['noise'] is not None else '—'}</td>"
                f"<td>{note}</td></tr>")
        cmp_html = (
            f"<h2>优化前后对比（{esc(before_id)} → {esc(after_id)}）</h2>"
            f"<p class='warn'><b>噪声尺度</b>：{_md_inline(NOISE_CAVEAT)}</p>"
            "<div class='scroll'><table><tr><th>单元</th><th>before</th><th>after</th>"
            "<th>Δ AQS</th><th>噪声</th><th>备注</th></tr>"
            + ("".join(crows) or "<tr><td colspan='6' class='empty'>无共同单元</td></tr>")
            + "</table></div>")

    warn = ""
    if inv["with_campaign"] == 0:
        warn = ("<p class='warn'>全部记录无 run.campaign 标签——热力卡/归因/对比塌缩为单格。"
                "接线见 docs/CAMPAIGN_LABELS_CONVENTION.md §4。</p>")
    # same corpus-wide notices the markdown carries — they used to exist only in
    # the markdown preamble, which the md->html conversion drops (D-140)
    warn += "".join(f"<p class='warn'>⚠ {_md_inline(w)}</p>" for w in corpus_warnings(inv))
    # Rendered through _md_inline for the same reason the corpus warnings above
    # are: the constant is written once, in markdown, and each surface renders
    # it its own way (D-262/D-323).
    claim_note = _md_inline(CLAIM_SCOPE_NOTE)
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
<p class="note">{claim_note}</p>
<p class="note">生成时间：{esc(generated_at)} · 记录 {inv['records']} · 含 AQS {inv['aqs_present']} · 含标签 {inv['with_campaign']} · min_samples={min_samples}</p>
{warn}
<h2>点位 × 忙闲 × 运营商 热力卡（AQS 中位；* = 样本不足 low_conf）</h2>
{heat_notes_html}
{_heat_grid_html(cells, agree=cc.aqs_grade)}
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


def campaigns_by_cell(records, dims=HEAT_DIMS):
    """Cells that pool more than one campaign -> the campaign ids they pool.

    The heat card and the attribution matrix track this themselves; the rollups
    keyed on the same dimensions do not. Markdown and HTML carry the corpus-wide
    notice (D-140), but CSV has no banners — an analyst filtering a rollup table
    would see a median that is neither the before nor the after and nothing to
    say so (D-141). Derived from the records rather than from heat cells so a
    cell without AQS still gets marked.
    """
    acc = {}
    for rec in records:
        labels = cc.campaign_labels(rec)
        key = tuple(labels.get(d) or cc.UNLABELED for d in dims)
        acc.setdefault(key, set()).add(labels.get("campaign_id") or cc.UNLABELED)
    return {k: sorted(v) for k, v in acc.items() if len(v) > 1}


class _TaggedWriter:
    """A csv.writer that appends the fabricated-data flag to every row.

    CSV is the surface with no banner over it — the analyst sees columns and
    nothing else, which is why mixed_campaigns had to become one (D-141). The
    synthetic warning never followed: markdown and HTML print it in red at the
    top, write_csv_tables never called count_synthetic at all. What evidence the
    files did carry was incidental, from `SYNTH-` happening to prefix the ids in
    the data — and two tables key on neither point nor campaign, so nothing in
    them could hint at it however the corpus was labelled (D-303, §2.7).

    The first row each block writes is its header, which is where the column's
    name goes; every row after it gets the value.
    """

    def __init__(self, fh, synthetic):
        self._w = csv.writer(fh)
        self._synthetic = synthetic
        self._header_written = False

    def writerow(self, row):
        if self._header_written:
            tag = self._synthetic
        else:
            tag, self._header_written = "synthetic", True
        self._w.writerow(list(row) + [tag])


def write_csv_tables(records, prefix, min_samples=cc.DEFAULT_MIN_SAMPLES,
                     before_id=None, after_id=None):
    """Dump the campaign tables as CSV for external analysis (Excel/pandas).
    Covers the same KPI sets the rendered report shows — an analyst pulling only
    the CSVs must not silently lose sections visible in the report (D-109).
    None values are emitted as empty cells (R-10: not fabricated to 0)."""
    def _cell(v):
        return "" if v is None else v

    written = []
    # Corpus-level, computed once: a corpus mixing real and fabricated records is
    # already a publish_check FAIL (D-124), so there is no per-row case to split.
    synthetic = bool(cc.count_synthetic(records))
    heat = heat_cells(records, min_samples)
    # cells pooling more than one campaign, for the rollup tables that do
    # not track it themselves (D-147)
    mixed_by_cell = campaigns_by_cell(records)

    def _mixed(cell):
        return "/".join(mixed_by_cell.get(
            tuple(cell.get(d) or cc.UNLABELED for d in HEAT_DIMS), []))

    def _severe(c):
        """Only the flags that mean NOT USABLE, so a CSV filter can reproduce the
        summary's exclusion. `incomparability` mixes both kinds, and which is
        which lives in attribution.SEVERE_FLAGS — never exported (D-205)."""
        return ";".join(f for f in attribution.incomparability_flags(c)
                        if attribution.is_severe(f))

    def _bad(c):
        """The impossible-value marker, in the one form every surface uses.

        CSV is the surface with no banner above it: an analyst computing on these
        files has nothing else to tell them this row's n excludes readings that
        were refused (D-141/D-197)."""
        return "; ".join(f"{r}×{n}" for r, n
                         in sorted((c.get("implausible_values") or {}).items()))

    p = prefix + "_heat.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = _TaggedWriter(f, synthetic)
        # mixed_campaigns must reach the CSV too: an analyst working from the
        # tables sees only columns — without it, a pooled median arrives looking
        # like an ordinary trustworthy number (D-141)
        w.writerow(["point_id", "carrier", "time_band", "aqs_median", "stdev", "grade", "n",
                    "low_confidence", "mixed_campaigns", "veto_n", "scorer_low_conf_n",
                    # which tiers this cell pooled, and which the rest of the
                    # corpus has but it does not — medians over different tier
                    # sets are not comparable across cells (D-165)
                    "tier_mix", "missing_tiers",
                    # same marker string the attribution CSV carries, so one
                    # filter works across both tables (D-166)
                    "incomparability",
                    # …and which of those mean NOT USABLE rather than "read with
                    # care". The summary drops severe-flagged cells from its
                    # attribution conclusion — 62 of 72 on the rehearsal grid —
                    # and a CSV consumer could not reproduce that split, because
                    # SEVERE_FLAGS lives in attribution.py and appears in no
                    # export. A filter column nobody can interpret is not a
                    # filter (D-205).
                    "severe_incomparability"])
        for c in heat:
            w.writerow([c["cell"]["point_id"], c["cell"]["carrier"], c["cell"]["time_band"],
                        _cell(c["aqs_median"]), _cell(c["stdev"]),
                        c["grade"], c["n"], c["low_confidence"],
                        "/".join(c.get("mixed_campaigns") or []),
                        c.get("veto_n", 0), c.get("scorer_low_conf_n", 0),
                        "/".join(f"{t}{n}" for t, n in (c.get("tier_mix") or {}).items()),
                        "/".join(c.get("missing_tiers") or []),
                        ";".join(attribution.incomparability_flags(c)),
                        _severe(c)])
    written.append(p)

    # The per-KPI heat card had a markdown table and an HTML pivot but no CSV at
    # all — and CSV is the surface the analyst computes on (D-141). GRADE_TIE was
    # the same failure in the other direction: markdown printed it, both other
    # surfaces dropped it, so a grade decided by a coin flip arrived looking
    # settled (D-148).
    p = prefix + "_kpi_heat.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = _TaggedWriter(f, synthetic)
        w.writerow(["kpi", "point_id", "carrier", "time_band", "median", "grade",
                    "grade_tie", "n", "low_confidence", "mixed_campaigns",
                    "implausible_values"])
        for k in DEFAULT_KPI_HEAT:
            for c in kpi_heat_cells(records, k, min_samples):
                w.writerow([k, c["cell"]["point_id"], c["cell"]["carrier"],
                            c["cell"]["time_band"], _cell(c["median"]),
                            # grade is None on a tie: no winner is the honest
                            # answer, and grade_tie says which grades tied
                            _cell(c["grade"]), "/".join(c.get("grade_tie") or []),
                            c["n"], c["low_confidence"],
                            "/".join(c.get("mixed_campaigns") or []),
                            # the surface with no banner above it: an analyst
                            # computing on this file has nothing else to tell them
                            # this cell's n excludes readings that were refused
                            "; ".join(f"{r}×{n}" for r, n
                                      in sorted((c.get("implausible_values") or {}).items()))])
    written.append(p)

    p = prefix + "_attribution.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = _TaggedWriter(f, synthetic)
        w.writerow(["point_id", "carrier", "time_band", "profile_id", "kpi", "access",
                    "regional_incr", "core_incr", "end_to_end_core", "coverage",
                    "low_confidence", "not_computable_reason", "incomparability",
                    # numeric so an analyst can threshold it directly instead of
                    # parsing TIER_TIME_SPREAD out of the flag string (D-160)
                    "tier_time_spread_ms",
                    # the summary's attribution conclusion is computed over cells
                    # WITHOUT a severe flag; this is the column that lets an
                    # analyst reproduce that filter (D-205)
                    "severe_incomparability"])
        for k in attribution.ATTRIBUTABLE_KPIS:
            attr = attribution.attribute(records, kpi=k, min_samples=min_samples)
            for c in attr["cells"]:
                cell = c["cell"]
                # same markers the rendered notes column carries, so a filter like
                # incomparability.str.contains('MIXED_CAMPAIGN') works (D-141)
                flags = attribution.incomparability_flags(c)
                w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                            cell.get("profile_id"), attr["kpi"], _cell(c["access_component"]),
                            _cell(c["regional_backbone_incr"]), _cell(c["core_backbone_incr"]),
                            _cell(c["end_to_end_core"]), "|".join(c["coverage"]),
                            c["low_confidence"], c["not_computable_reason"] or "",
                            ";".join(flags), _cell(c.get("tier_time_spread_ms")),
                            _severe(c)])
    written.append(p)

    # Which segment is a point's own problem vs the path's (D-146). The verdict
    # is a column, not a banner — CSV is where the analyst actually computes.
    p = prefix + "_segment_profile.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = _TaggedWriter(f, synthetic)
        w.writerow(["kpi", "segment", "n_cells", "not_computable", "typical", "mad",
                    "rel_mad_percent", "basis", "uniform", "high_cells", "low_cells"])
        for k in attribution.ATTRIBUTABLE_KPIS:
            attr = attribution.attribute(records, kpi=k, min_samples=min_samples)
            if not attr["cells"]:
                continue
            for s in attribution.segment_profile(attr)["segments"]:
                def _cells(items):
                    return "; ".join("/".join(str(v) for v in o["cell"].values())
                                     for o in (items or []))
                w.writerow([k, s["segment"], s["n_cells"], s["not_computable"],
                            _cell(s["typical"]), _cell(s["mad"]), _cell(s["rel_mad"]),
                            s["basis"], _cell(s["uniform"]),
                            _cells(s["high"]), _cells(s["low"])])
    written.append(p)

    p = prefix + "_stability.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = _TaggedWriter(f, synthetic)
        # campaign_id leads the key (D-145): without it two campaigns emit rows
        # identical in every other column and an analyst cannot tell them apart
        w.writerow(["campaign_id", "point_id", "carrier", "time_band", "tier", "profile_id",
                    "kpi", "n", "median", "mean", "cv_percent", "unstable", "low_confidence",
                    # an empty cv_percent has two causes needing two different
                    # actions — measure more, or go fix what produced these
                    # numbers — and the bare blank says neither (D-197)
                    "cv_not_computable_reason", "implausible_values"])
        for k in stability.DEFAULT_STABILITY_KPIS:
            for c in stability.stability_cells(records, k, min_samples=min_samples):
                cell = c["cell"]
                w.writerow([cell.get("campaign_id"),
                            cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                            cell.get("tier"), cell.get("profile_id"), c["kpi"], c["n"],
                            _cell(c["median"]), _cell(c["mean"]), _cell(c["cv_percent"]),
                            c["unstable"], c["low_confidence"],
                            _cell(c.get("cv_not_computable_reason")), _bad(c)])
    written.append(p)

    # The order-effect diagnosis was the one section the report renders as a
    # table of numbers with no machine-readable export at all: nine of the ten
    # modules build_report_markdown calls ship a CSV, and this one did not
    # (D-246). Long format like _trend.csv — one row per profile per position,
    # with the profile-level verdict repeated — so a pivot reproduces the table.
    p = prefix + "_order_effect.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = _TaggedWriter(f, synthetic)
        w.writerow(["profile_id", "kpi", "order_index", "position_median", "position_n",
                    "position_low_confidence", "spread", "spread_pct", "overall_median",
                    "threshold_pct", "order_effect_suspected", "not_computable_reason",
                    "low_confidence", "implausible_values",
                    # CSV is the surface with no banner above it. Whether the
                    # Latin square ever rotated is what decides if a per-position
                    # spread means anything at all — without these columns an
                    # analyst computes 「无明显序位效应」 over a corpus where
                    # counterbalancing never happened (D-164/D-197).
                    "distinct_rounds", "rotation_warning", "no_order_evidence",
                    "rotates_within_run"])
        # every KPI the section covers, not just analyze()'s default one: the
        # report renders one 序位效应 section per ORDER_SENSITIVE_KPIS entry, and
        # a CSV carrying one of the three loses two thirds of the section while
        # looking complete — the very failure D-246 exists to stop (D-247)
        for kpi in order_effect.ORDER_SENSITIVE_KPIS:
            ores = order_effect.analyze(records, kpi=kpi, min_samples=min_samples)
            for pr in ores["profiles"]:
                head = [pr["profile_id"], ores["kpi"]]
                tail = [_cell(pr["spread"]), _cell(pr["spread_pct"]),
                        _cell(pr["overall_median"]), ores["threshold_pct"],
                        _cell(pr["order_effect_suspected"]),
                        pr["not_computable_reason"] or "", pr["low_confidence"], _bad(pr),
                        ores["distinct_rounds"], ores["rotation_warning"],
                        ores["no_order_evidence"], ores["rotates_within_run"]]
                # a profile whose every reading was refused has no positions at
                # all; it still gets its row, for the same reason analyze() does
                positions = sorted(pr["positions"].items()) or [(None, None)]
                for idx, v in positions:
                    w.writerow(head + [_cell(idx), _cell(v["median"]) if v else "",
                                       v["n"] if v else "",
                                       v["low_confidence"] if v else ""] + tail)
    written.append(p)

    # The sample denominator behind every median above (D-96) — external analysis
    # without it re-creates the survivor bias the rollup exists to expose.
    validity = validity_rollup.analyze(records)
    vcells = validity["cells"]
    p = prefix + "_validity.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = _TaggedWriter(f, synthetic)
        w.writerow(["point_id", "carrier", "time_band", "profile_id", "attempted", "valid",
                    "valid_low_confidence", "invalid", "unknown", "valid_rate",
                    "below_min_rate", "reasons", "mixed_campaigns"])
        for c in vcells:
            cell = c["cell"]
            w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                        cell.get("profile_id"), c["attempted"], c["valid"],
                        c["valid_low_confidence"], c["invalid"], c["unknown"],
                        _cell(c["valid_rate"]), _cell(c["below_min_rate"]),
                        ";".join(f"{r}:{n}" for r, n in c["reasons"].items()), _mixed(cell)])
    written.append(p)

    # The validity section's second table, unexported for the same reason radio's
    # was (D-304): "did collection hold up across the trip days" is the signal
    # D-145 wants read on the evening of day one, and it was page-only. Written
    # under the same condition the section renders it, so the CSV bundle never
    # carries a table the report does not show.
    # The file is always written and the rows are conditional, not the other way
    # round: a header with no rows says "no multi-day trend to show", while a
    # missing file reads as "did the export break?" — the same reason the band
    # distribution prints a zero-cell band instead of omitting it.
    p = prefix + "_validity_trend.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = _TaggedWriter(f, synthetic)
        # local_day, not day: the CSV travels without the heading that says
        # which day it is, and UTC-vs-local is exactly what went wrong (D-318).
        w.writerow(["local_day", "attempted", "usable", "valid_rate"])
        if len(validity["trend"]) > 1:
            for t in validity["trend"]:
                w.writerow([t["day"], t["attempted"], t["usable"],
                            _cell(t["valid_rate"])])
    written.append(p)

    sscells = subscore_rollup.analyze(records, min_samples)["cells"]
    p = prefix + "_subscores.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = _TaggedWriter(f, synthetic)
        w.writerow(["point_id", "carrier", "time_band", "runs", "dragging_dim",
                    "dragging_median", "spread", "low_confidence", "dim_medians",
                    # markdown has carried this since D-179 and the CSV did not:
                    # the surface with the banner warned, the surface without one
                    # did not (D-197)
                    "mixed_campaigns", "implausible_values"])
        for c in sscells:
            cell = c["cell"]
            w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                        c["runs"], _cell(c["dragging_dim"]), _cell(c["dragging_median"]),
                        _cell(c["spread"]), c["low_confidence"],
                        ";".join(f"{d}:{v['median']}" for d, v in c["dims"].items()),
                        _mixed(cell), _bad(c)])
    written.append(p)

    ucells = trust_rollup.analyze(records, min_samples)["cells"]
    p = prefix + "_trust.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = _TaggedWriter(f, synthetic)
        w.writerow(["point_id", "carrier", "time_band", "scenarios", "clock_annotated",
                    "clock_suspect", "clock_suspect_share", "abs_drift_ppm_median",
                    "stream_counted", "stream_bad", "parse_per_event_us_median",
                    "clock_hotspot", "low_confidence", "mixed_campaigns"])
        for c in ucells:
            cell = c["cell"]
            w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                        c["scenarios"], c["clock_annotated"], c["clock_suspect"],
                        _cell(c["clock_suspect_share"]), _cell(c["abs_drift_ppm_median"]),
                        c["stream_counted"], c["stream_bad"],
                        _cell(c["parse_per_event_us_median"]), c["clock_hotspot"],
                        c["low_confidence"], _mixed(cell)])
    written.append(p)

    tcells = transport_rollup.analyze(records, min_samples)["cells"]
    p = prefix + "_transport.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = _TaggedWriter(f, synthetic)
        # the delta's noise scale belongs on the surface analysts compute on —
        # a bare Δ column is an invitation to rank cells by repeat jitter (D-180)
        w.writerow(["point_id", "carrier", "time_band", "transport", "n", "aqs_median",
                    "low_confidence", "cellular_minus_wifi", "noise", "within_noise",
                    "mixed_campaigns",
                    # counted per CELL, like the delta and its noise, so it rides
                    # the same is_cell row rather than being repeated per medium
                    "implausible_values"])
        for c in tcells:
            cell = c["cell"]
            for t in sorted(c["transports"]):
                b = c["transports"][t]
                is_cell = t == "cellular"
                w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                            t, b["n"], _cell(b["aqs_median"]), b["low_confidence"],
                            _cell(c["cellular_minus_wifi"]) if is_cell else "",
                            _cell(c["noise"]) if is_cell else "",
                            _cell(c["within_noise"]) if is_cell else "",
                            _mixed(cell), _bad(c) if is_cell else ""])
    written.append(p)

    # Radio context on the surface analysts compute on. The band is the derived
    # verdict and the two medians are what produced it, so all three ride the
    # same row — reading the band without them cannot tell a weak cell from an
    # unmeasured one, which is the whole distinction this section carries.
    radio = radio_rollup.analyze(records, min_samples)
    rcells = radio["cells"]
    p = prefix + "_radio.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = _TaggedWriter(f, synthetic)
        w.writerow(["point_id", "carrier", "time_band", "band", "rsrp_median_dbm",
                    "sinr_median_db", "rats", "serving_cells", "n", "n_with_radio",
                    "sampled_n_median", "stale_samples", "low_confidence",
                    "thin_samples", "implausible_values"])
        for c in rcells:
            cell = c["cell"]
            w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                        c["band"] or "", _cell(c["rsrp_median_dbm"]),
                        _cell(c["sinr_median_db"]), "/".join(sorted(c["rats"])),
                        "/".join(sorted(c["cell_keys"])), c["n"], c["n_with_radio"],
                        _cell(c["sampled_n_median"]), c["stale_samples"],
                        c["low_confidence"], c["thin_samples"], _bad(c)])
    written.append(p)

    # The radio section renders TWO tables and only the first was exported: the
    # busy/idle comparability verdict lived on the page alone (D-304). It is not
    # a footnote — 「CELL_CHANGED——该点位忙闲差不可单独归因于时段」 disqualifies one
    # of the two remaining comparison axes for that place, and an analyst diffing
    # busy against idle in _heat.csv had no column saying so. Keyed by place, not
    # by cell, so it cannot ride on _radio.csv's rows.
    p = prefix + "_radio_comparability.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = _TaggedWriter(f, synthetic)
        w.writerow(["point_id", "carrier", "bands", "shared_cells", "verdict"])
        for pl in radio["places"]:
            # `changed` and `partial` are mutually exclusive by construction
            # (one needs an empty intersection, the other a non-empty one), so
            # the order is not load-bearing; what matters is that both surfaces
            # read the same two fields, which a guard reconciles word for word.
            verdict = ("CELL_CHANGED" if pl["changed"]
                       else "CELL_PARTIAL" if pl["partial"] else "SAME_CELL")
            w.writerow([pl["place"].get("point_id"), pl["place"].get("carrier"),
                        "; ".join("%s:%s" % (b, "/".join(k))
                                  for b, k in sorted(pl["bands"].items())),
                        "/".join(pl["shared_cells"]), verdict])
    written.append(p)

    # The headline "did it get better" payloads (survey gap 6): before/after delta
    # and the N-campaign trajectory, in spreadsheet-consumable long format (D-114).
    if before_id is None and after_id is None:
        before_id, after_id = auto_compare_ids(inventory(records))
    p = prefix + "_comparison.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = _TaggedWriter(f, synthetic)
        w.writerow(["point_id", "carrier", "time_band", "before_id", "after_id",
                    "before", "after", "delta", "noise", "within_noise",
                    # without these an n=3-vs-n=3 delta publishes as a clean
                    # result: markdown flagged it, CSV and HTML did not (D-160)
                    "low_confidence", "before_n", "after_n"])
        if before_id and after_id:
            cmp_res = compare_campaigns(records, before_id, after_id, min_samples)
            for r in cmp_res["rows"]:
                cell = r["cell"]
                w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                            before_id, after_id, _cell(r["before"]), _cell(r["after"]),
                            _cell(r["delta"]), _cell(r.get("noise")),
                            _cell(r.get("within_noise")), r["low_confidence"],
                            _cell(r.get("before_n")), _cell(r.get("after_n"))])
    written.append(p)

    # Written only when a trend EXISTS. It used to ship unconditionally, so a
    # two-campaign corpus — the standard M2 shape — archived a _trend.csv whose
    # `direction` said improving for 31 of 32 cells while the _comparison.csv
    # beside it marked 28 of those same cells within_noise, and the report showed
    # no trend section at all. Three artefacts, two answers (D-196). Same
    # threshold as the section gate and trend's own renderer.
    tres = trend.analyze(records, min_samples=min_samples)
    if len(tres["campaigns"]) >= trend.MIN_CAMPAIGNS_FOR_TREND:
        p = prefix + "_trend.csv"
        with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
            w = _TaggedWriter(f, synthetic)
            # the direction is only as good as its noise scale — ship both or the
            # analyst computing on this file re-derives an unqualified verdict
            w.writerow(["point_id", "carrier", "time_band", "campaign_id", "order_index",
                        "median", "n", "direction", "first_last_delta",
                        "noise", "within_noise", "order_basis", "low_confidence",
                        # per CELL, not per campaign: the trajectory is what the
                        # refused readings would have bent, and the direction
                        # column above is derived from the whole chain (D-197)
                        "implausible_values"])
            for c in tres["cells"]:
                cell = c["cell"]
                for i, cid in enumerate(tres["campaigns"]):
                    w.writerow([cell.get("point_id"), cell.get("carrier"),
                                cell.get("time_band"), cid, i,
                                _cell(c["trajectory"][i]), c["sample_counts"][i],
                                _cell(c["direction"]), _cell(c["first_last_delta"]),
                                _cell(c.get("noise")), _cell(c.get("within_noise")),
                                tres.get("order_basis"), c["low_confidence"], _bad(c)])
        written.append(p)

    bcells = buffering_rollup.analyze(records, min_samples)["cells"]
    p = prefix + "_buffering.csv"
    with open(p, "w", newline="", encoding=CSV_ENCODING) as f:
        w = _TaggedWriter(f, synthetic)
        w.writerow(["point_id", "carrier", "time_band", "n", "modal_attribution",
                    "score_median", "sawtooth_median", "near_zero_median",
                    "suspect_share", "distortion_hotspot", "low_confidence",
                    "mixed_campaigns",
                    # scenarios where NOTHING was measured, kept out of n and out
                    # of the suspect denominator — an empty suspect_share is a
                    # coverage gap, not a clean 0% (D-163)
                    "not_detected", "sample_count_median", "implausible_values"])
        for c in bcells:
            cell = c["cell"]
            w.writerow([cell.get("point_id"), cell.get("carrier"), cell.get("time_band"),
                        c["n"], c["modal_attribution"], _cell(c["score_median"]),
                        _cell(c["sawtooth_median"]), _cell(c["near_zero_median"]),
                        _cell(c["suspect_share"]), c["distortion_hotspot"],
                        c["low_confidence"], _mixed(cell),
                        c["not_detected"], _cell(c["sample_count_median"]), _bad(c)])
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
        # Records carry no timezone, so this offset decides two printed things:
        # which runs are busy and which are idle, and which day a run's validity
        # counts toward. A re-run at a different offset moves rows between days
        # — archived so that disagreement is explainable rather than spooky
        # (D-318).
        "local_day_utc_offset_h": cc.DEFAULT_TZ_OFFSET_H,
        # The radio bands decide the 弱/中/良 printed for every cellular cell,
        # and they are a COPY of the app's constants (spec/ has no home for them
        # yet). A re-run disagreeing with an archived report over a signal band
        # is exactly what this manifest exists to make explainable (D-284).
        "value_ranges_non_kpi": {k: list(v) for k, v in sorted(cc.NON_KPI_RANGES.items())},
        "rsrp_weak_dbm": cc.RSRP_WEAK_DBM,
        "rsrp_good_dbm": cc.RSRP_GOOD_DBM,
        "sinr_weak_db": cc.SINR_WEAK_DB,
        "sinr_good_db": cc.SINR_GOOD_DB,
        "signal_bands": list(cc.SIGNAL_BANDS),
        "signal_labels": dict(cc.SIGNAL_LABELS),
        # Exempt until D-266 gave it a reader: the summary now asks it which
        # grades rank below good, so it decides which cells the city is told
        # are its worst. Archived the moment it started deciding (D-267).
        "grade_order": list(cc.GRADE_ORDER),
        # What a cell IS in the two sections that pool by one. Exempt as
        # "structural, not a level" until source-level mutation showed them
        # moving 418 and 494 printed numbers with nothing archived anywhere —
        # neither here nor under `params` (D-269).
        "attribution_group_by": list(attribution.DEFAULT_GROUP_BY),
        "stability_group_by": list(stability.STAB_GROUP_BY),
        "heat_kpis": list(DEFAULT_KPI_HEAT),
        "stability_kpis": list(stability.DEFAULT_STABILITY_KPIS),
        "attribution_kpis": list(attribution.ATTRIBUTABLE_KPIS),
        # Everything below decides what the report SAYS and was missing from a
        # manifest whose own test is named "cover every output-deciding gate"
        # (D-198). The first one is worse than an omission: D-155 recorded that
        # it was made a named constant SO THAT it would be archived, and the
        # attribution section prints 「相隔超 60 分钟」 to the reader — two places
        # asserting a record that did not exist.
        "tier_time_spread_gate_ms": attribution.TIER_TIME_SPREAD_GATE_MS,
        # which cells get named 单点异常 — retune these and the report accuses a
        # different point (D-146/D-200). The flat `segment_outlier_k` that used
        # to sit here was archived while being unreachable — an entry in a
        # manifest whose header promises the opposite (D-204).
        "segment_outlier_target_false_alarm": attribution.OUTLIER_TARGET_FALSE_ALARM,
        "segment_outlier_k_by_cells": [[n, k] for n, k
                                       in attribution._OUTLIER_K_BY_CELLS],
        # below this the section declines to give a verdict at all
        "segment_min_cells_to_screen": attribution.MIN_CELLS_TO_SCREEN,
        "order_effect_threshold_percent": order_effect.DEFAULT_THRESHOLD_PCT,
        # decides whether the trend section and _trend.csv exist at all (D-196)
        "min_campaigns_for_trend": trend.MIN_CAMPAIGNS_FOR_TREND,
        # every 噪声内 verdict on every surface comes through these two
        "median_se_factor": cc.MEDIAN_SE_FACTOR,
        "mad_to_sigma": cc.MAD_TO_SIGMA,
        # which readings are refused, hence every n and every median (D-178/197)
        "epoch_ms_bounds": [cc.EPOCH_MS_MIN, cc.EPOCH_MS_MAX],
        "value_ranges": {k: list(v) for k, v in sorted(cc.VALUE_RANGES.items())},
        # ---- Gates that are not numbers. The scan enforcing "every
        # ---- output-deciding gate is archived" enumerated int/float only — it
        # ---- said so in its own comment — so this entire class was invisible to
        # ---- it, and the non-numeric entries above are here because somebody
        # ---- remembered rather than because anything checked (D-248).
        # the three tiers the whole differential matrix is built on
        "tiers": list(cc.TIERS),
        # which segments the point-vs-path verdict is computed over
        "attribution_segments": [s for s, _ in attribution.SEGMENTS],
        # which markers mean NOT USABLE: the summary's attribution conclusion is
        # computed over cells WITHOUT one, and on the rehearsal grid that dropped
        # 62 of 72 cells (D-205). Retuning it changes the headline.
        "severe_incomparability_flags": list(attribution.SEVERE_FLAGS),
        # which KPIs the order-effect section screens. A DIFFERENT constant from
        # stability_kpis, holding the same value today — archiving one and not
        # the other left the manifest looking complete until the two diverge
        "order_effect_kpis": list(order_effect.ORDER_SENSITIVE_KPIS),
        # the two media the transport section differences; anything else pools
        # into a third bucket that is never compared
        "transport_media": list(transport_rollup.EXPLICIT),
        # the metric key the trend section scores on
        "trend_metric_key": trend.METRIC_AQS,
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


def _preflight_outputs(args):
    """Every destination this run will write to, checked before it does any work.

    Mistyping the output path is an end-of-field-day mistake, and all four flags
    answered it with a raw traceback (D-306). Worse, markdown is written before
    CSV, so `--md ok.md --csv nope/c` produced half a deliverable set and then a
    stack trace — the operator cannot tell from that what exists on disk.

    Only the enumerable mistakes are caught here: a directory that is not there,
    and a directory handed over where a filename belongs. A directory that
    exists but cannot be written is not decidable in advance on Windows, so it
    is left to the write itself rather than probed with a scratch file.
    """
    problems = []
    for flag, path in (("--md", args.md), ("--html", args.html),
                       ("--provenance", args.provenance)):
        if not path:
            continue
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            problems.append(f"{flag} {path}：目录 `{parent}` 不存在")
        elif os.path.isdir(path):
            problems.append(f"{flag} {path}：这是一个目录，不是文件名")
    # --csv takes a PREFIX, so only its directory is a path; an existing
    # directory as the prefix is legal (files land beside it) and not flagged.
    if args.csv:
        parent = os.path.dirname(args.csv)
        if parent and not os.path.isdir(parent):
            problems.append(f"--csv {args.csv}：目录 `{parent}` 不存在")
    return problems


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

    bad_outputs = _preflight_outputs(args)
    if bad_outputs:
        for b in bad_outputs:
            print("输出路径不可用：" + b, file=sys.stderr)
        print("（先建好目录或改路径再跑；本次未产出任何文件）", file=sys.stderr)
        return 2

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
        # The third ERROR-class counter, and the one this gate omitted. The
        # comment above cites corpus_health's classification but listed two of
        # its three: load_records catches OSError and continues, so a file that
        # cannot be read takes ALL of its records out of the corpus and the
        # report came out anyway, every denominator short (D-330, the shape of
        # D-328 in a second consumer — and this one is the door that refuses).
        if stats.get("unreadable_files"):
            integrity.append(f"unreadable files × {stats['unreadable_files']}")
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
