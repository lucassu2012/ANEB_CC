#!/usr/bin/env python3
"""ANEB validity / invalid_reasons rollup (stdlib only).

Exposes the DENOMINATOR behind every number in the campaign report.

INVALID scenarios carry null KPIs, so they are silently dropped by the heat card
and attribution: a cell can advertise "n=4" while 40 attempts were actually made
and 36 failed. The median is then computed over a survivor population — which may
be exactly the healthy subset, i.e. survivorship bias pointing the wrong way. The
report shows the survivors' count; nothing showed the attempts. This does.

Per (point, carrier, time_band, profile):
    valid / valid_low_confidence / invalid / unknown counts, valid_rate,
    and the invalid_reasons histogram explaining WHY attempts were lost.
Plus a corpus-level reasons histogram and a per-LOCAL-day validity trend
(UTC+8, the offset annotate_campaign derives the time band at — D-318)
(a collapsing valid_rate over time is a regression signal in the harness,
not in the network under test).

Honesty (R-10): a cell with no scenarios yields valid_rate None (never 0/0=0);
`unknown` validity is kept as its own bucket rather than assumed valid.

Usage:
    python validity_rollup.py results/*.jsonl [--min-rate 0.8]
"""
import argparse
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import campaign_common as cc

CELL_DIMS = ("point_id", "carrier", "time_band")
VALIDITY_STATES = ("valid", "valid_low_confidence", "invalid", "unknown")
DEFAULT_MIN_RATE = 0.8      # below this share of valid attempts -> flagged
_REASON_SPLIT = re.compile(r"[;,|]")


def split_reasons(scn):
    """scenarios[].invalid_reasons -> list of individual reason tokens."""
    raw = scn.get("invalid_reasons")
    if not isinstance(raw, str) or not raw.strip():
        return []
    return [t.strip() for t in _REASON_SPLIT.split(raw) if t.strip()]


def validity_cells(records, min_rate=None):
    # read live, not captured in the signature — the provenance manifest archives
    # this gate and promises that changing it changes the report (D-204)
    min_rate = DEFAULT_MIN_RATE if min_rate is None else min_rate
    """Per-cell validity breakdown + reason histogram. Returns (cells, reasons)."""
    buckets = defaultdict(lambda: {"counts": Counter(), "reasons": Counter()})
    corpus_reasons = Counter()
    for rec in records:
        labels = cc.campaign_labels(rec)
        for scn in cc.iter_scenarios(rec):
            key = tuple(labels[d] for d in CELL_DIMS) + (scn.get("profile_id") or "?",)
            state = cc.scenario_validity(scn)
            if state not in VALIDITY_STATES:
                state = "unknown"
            b = buckets[key]
            b["counts"][state] += 1
            for r in split_reasons(scn):
                b["reasons"][r] += 1
                corpus_reasons[r] += 1

    cells = []
    for key in sorted(buckets):
        counts = buckets[key]["counts"]
        attempted = sum(counts.values())
        # VALID_LOW_CONFIDENCE still produced a usable measurement -> counts as valid.
        usable = counts["valid"] + counts["valid_low_confidence"]
        cells.append({
            "cell": dict(zip(CELL_DIMS + ("profile_id",), key)),
            "attempted": attempted,
            "valid": counts["valid"],
            "valid_low_confidence": counts["valid_low_confidence"],
            "invalid": counts["invalid"],
            "unknown": counts["unknown"],
            "valid_rate": (usable / attempted) if attempted else None,
            "below_min_rate": (usable / attempted < min_rate) if attempted else None,
            # An unrecognised validity state is not a failure — it is a state
            # nobody here knows how to read — and it lands in the denominator, so
            # a cell full of them reports 有效率 0% and trips LOW_VALID_RATE as
            # though everything failed. Real corpora do carry a fourth value
            # (`degraded`) the schema enum does not list. Counting it as
            # not-usable is the conservative direction and stays, but the share
            # must travel with the rate or the number claims more than it knows
            # (D-190).
            "unknown_share": (counts["unknown"] / attempted) if attempted else None,
            # ranked, not most_common: reasons tied at the same count would otherwise
            # order by input order and the CSV row differs run to run (D-148)
            "reasons": dict(cc.ranked(buckets[key]["reasons"])),
        })
    return cells, corpus_reasons


def validity_trend(records, tz_offset_h=None, stats=None):
    """Per-LOCAL-day usable-rate. A decaying rate is a harness regression signal.

    Local, not UTC, and at the same offset annotate_campaign uses for the time
    band — otherwise one report carries two answers to "when". Measured while
    this still bucketed by UTC: the UTC day rolls over at 08:00 CST, so a
    Shenzhen field day running 03:00 to 20:00 local came out as TWO rows, one of
    them holding the single deep-night idle session. Worse than a mis-dated row:
    the table only renders when there is more than one row, so the timezone
    artefact manufactured a trend out of a single field day — in a table whose
    whole purpose is to make a decaying rate visible (D-318).
    """
    # Read live, not as a default argument: a default is evaluated once at
    # definition time, so the shared constant would be frozen at import and
    # changing it would move the printed heading while leaving the buckets at
    # +8 — load-bearing in appearance only (D-264/D-318).
    if tz_offset_h is None:
        tz_offset_h = cc.DEFAULT_TZ_OFFSET_H
    days = defaultdict(Counter)
    day_cells = defaultdict(set)
    undated = 0
    shift = timedelta(hours=tz_offset_h)
    for rec in records:
        ms = cc.run_started_ms(rec)
        if ms is None:
            # `run.started_at_epoch_ms` is absent from validate_results.py, so a
            # record without it is contract-legal and lands here. Skipping it
            # silently made the trend's totals smaller than the corpus totals
            # printed four lines above, with nothing to say so (D-336, the same
            # shape D-332 fixed for run_id). Counted in SCENARIOS, the unit
            # `attempted` uses, or the two numbers would not be comparable.
            undated += sum(1 for _ in cc.iter_scenarios(rec))
            continue
        day = (datetime.fromtimestamp(ms / 1000.0, timezone.utc)
               + shift).strftime("%Y-%m-%d")
        labels = cc.campaign_labels(rec)
        cell = "/".join(str(labels[d]) for d in CELL_DIMS)
        for scn in cc.iter_scenarios(rec):
            days[day][cc.scenario_validity(scn)] += 1
            day_cells[day].add(cell)
    out = []
    for day in sorted(days):
        c = days[day]
        attempted = sum(c.values())
        usable = c["valid"] + c["valid_low_confidence"]
        out.append({"day": day, "attempted": attempted, "usable": usable,
                    "valid_rate": (usable / attempted) if attempted else None,
                    # which cells fed this day: a falling rate across days that
                    # measured different sites is a change of site, not the
                    # harness regression this table exists to surface (D-336)
                    "cells": sorted(day_cells[day])})
    if stats is not None:
        sets = [frozenset(r["cells"]) for r in out]
        common = set(sets[0]).intersection(*sets[1:]) if len(sets) > 1 else set()
        union = set().union(*sets) if sets else set()
        stats["undated_scenarios"] = undated
        # flag and evidence out of one computation, so they cannot disagree
        stats["cells_uneven"] = sorted(union - common) if len(sets) > 1 else []
        stats["days_share_cells"] = (
            None if len(sets) < 2 else not (union - common))
    return out


def analyze(records, min_rate=None):      # None -> the live gate (D-204)
    # resolved HERE too: the result dict publishes `min_rate`, and consumers
    # render it as the gate in force
    min_rate = DEFAULT_MIN_RATE if min_rate is None else min_rate
    cells, reasons = validity_cells(records, min_rate)
    trend_stats = {}
    attempted = sum(c["attempted"] for c in cells)
    usable = sum(c["valid"] + c["valid_low_confidence"] for c in cells)
    return {
        "min_rate": min_rate,
        "cells": cells,
        "corpus_reasons": dict(cc.ranked(reasons)),
        "trend": validity_trend(records, stats=trend_stats),
        "trend_stats": trend_stats,
        "attempted": attempted,
        "usable": usable,
        "overall_valid_rate": (usable / attempted) if attempted else None,
    }


def _pct(rate):
    return "—" if rate is None else f"{rate * 100:.1f}%"


def render_markdown(res):
    lines = [
        "## 有效性与失效原因（每格的有效样本分母）",
        "",
        f"> 全语料尝试 {res['attempted']} 个场景，可用 {res['usable']} "
        f"（{_pct(res['overall_valid_rate'])}）；低于 {res['min_rate'] * 100:.0f}% 的单元标 "
        "`LOW_VALID_RATE`。INVALID 场景 KPI 为空、会被热力卡/归因静默丢弃——"
        "**此表即那些被丢弃样本的去向**。",
        "",
        "> **有效率的分子是两列之和**：`有效率 =（有效(严格) + 低置信）/ 尝试`。"
        "低置信的场景**仍产出了可用测量**，所以它计入分子；"
        "**「有效(严格)」那一列不是分子**，拿它去除尝试会得到另一个数——"
        "`有效(严格)=0` 与 `有效率=100%` 可以同时成立，且都没错。",
        "",
        "> **「未知」的口径**：`validity` 取值不在已知三态内（本层大小写不敏感）即计入"
        "**未知**列。**未知按「不可用」计入有效率**——这是保守方向，但它**不是失效**，"
        "而是本层读不懂那个状态。故未知占比高的格会标 `UNKNOWN_VALIDITY:x%`："
        "该格的有效率**不应读成「这里全失败了」**，应先去查生产者写了什么。",
        "",
    ]
    if not res["cells"]:
        lines.append("_无场景数据。_")
        return "\n".join(lines)

    lines += ["| 点位 | 运营商 | 时段 | profile | 尝试 | 有效(严格) | 低置信 | 失效 | 未知 | 有效率 | 备注 |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in res["cells"]:
        cl = {k: cc.md_cell(v) for k, v in c["cell"].items()}   # labels are human-typed
        notes = []
        if c["below_min_rate"]:
            notes.append("LOW_VALID_RATE")
        # a rate dragged down by states this layer cannot read is a different
        # finding from a rate dragged down by failures (D-190)
        if c.get("unknown_share"):
            notes.append(f"**UNKNOWN_VALIDITY:{_pct(c['unknown_share'])}**")
        note = "; ".join(notes) or "—"
        lines.append(
            f"| {cl['point_id']} | {cl['carrier']} | {cl['time_band']} | {cl['profile_id']} | "
            f"{c['attempted']} | {c['valid']} | {c['valid_low_confidence']} | {c['invalid']} | "
            f"{c['unknown']} | {_pct(c['valid_rate'])} | {note} |")
    lines.append("")

    if res["corpus_reasons"]:
        lines += ["### 失效原因分布", ""]
        lines += [f"- `{r}` × {n}" for r, n in res["corpus_reasons"].items()]
        lines.append("")
    if len(res["trend"]) > 1:
        lines += [f"### 有效率趋势（按本地日，UTC+{cc.DEFAULT_TZ_OFFSET_H}）", "",
                  "| 日期 | 尝试 | 可用 | 有效率 |", "|---|---|---|---|"]
        for t in res["trend"]:
            lines.append(f"| {t['day']} | {t['attempted']} | {t['usable']} | "
                         f"{_pct(t['valid_rate'])} |")
        lines.append("")
        # This table's stated purpose is to make a harness regression visible.
        # It pools every cell into one daily rate, so a corpus that measured an
        # easy site on one day and a hard one on the next draws exactly the same
        # falling line — and the per-cell table above carries no dates, so the
        # reader cannot connect them (D-336).
        ts = res.get("trend_stats") or {}
        uneven = ts.get("cells_uneven") or []
        if uneven:
            shown = "、".join(cc.md_cell(c) for c in uneven[:3])
            lines += [f"> ⚠ 各日**并非测的同一组单元**（{shown}"
                      + (f" 等 {len(uneven)} 个" if len(uneven) > 3 else "")
                      + "未出现在每一天）——率的升降**可能是换了点位/运营商/时段**，"
                      "而不是装置回归信号。逐单元的率见上表。", ""]
        if ts.get("undated_scenarios"):
            lines += [f"> ⚠ 另有 {ts['undated_scenarios']} 个场景**缺 "
                      "`run.started_at_epoch_ms`**，不属于任何一天——"
                      "**本表分母因此小于上方的全语料合计**（该字段非契约必填）。", ""]
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB validity / invalid_reasons rollup")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--min-rate", type=float, default=DEFAULT_MIN_RATE)
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    recs, files = cc.load_records(args.inputs)
    res = analyze(recs, args.min_rate)
    print(render_markdown(res))
    print(f"\n<!-- records={len(recs)} files={len(files)} -->", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
