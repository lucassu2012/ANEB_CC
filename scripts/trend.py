#!/usr/bin/env python3
"""ANEB longitudinal campaign trend (stdlib only).

campaign_report's before/after compares exactly two campaigns; this generalizes
it to N campaigns in chronological order, per (point, carrier, time_band) cell —
the shape the standing multi-round net-perf goal needs (optimize, re-measure,
re-optimize, …, and see whether each cell is actually improving).

Per cell:
    trajectory = [median(metric in campaign_1), …, median(metric in campaign_N)]
    first_last_delta, and a monotonicity/direction verdict interpreted through the
    metric's polarity (AQS & goodput: higher is better; latency KPIs: lower is
    better) -> improving / regressing / mixed / flat.

Campaign ordering (default) is chronological by each campaign's EARLIEST
run.started_at_epoch_ms — not campaign_id sort, which need not match time. Pass
--order to fix it explicitly.

Honesty (R-10): a cell missing from some campaigns yields a trajectory with None
gaps (never interpolated); direction over <2 present points is None, not "flat".

Usage:
    python trend.py results/*.jsonl [--metric aqs|<kpi_key>] [--order id1,id2,id3]
"""
import argparse
import sys
from collections import Counter, defaultdict

import campaign_common as cc

METRIC_AQS = "aqs"
DEFAULT_METRIC = METRIC_AQS
CELL_DIMS = ("point_id", "carrier", "time_band")
# Metrics where a HIGHER value is better. Everything else (latency/jitter/stall)
# is better when lower — this drives the improving/regressing interpretation.
_HIGHER_IS_BETTER = {"aqs", "u1_goodput_mbps"}


def metric_higher_is_better(metric):
    return metric in _HIGHER_IS_BETTER


def _range_field(metric):
    """The VALUE_RANGES key for a trend metric ("aqs" is scored as aqs_score)."""
    return "aqs_score" if metric == METRIC_AQS else metric


def _record_values(rec, metric, implausible):
    """Metric values contributed by one record: one AQS, or per-scenario KPIs.

    Impossible values are counted in `implausible` and left out. A trajectory is
    a chain of medians and a first-to-last delta across campaigns, so one
    corrupt reading does not just misstate one round — it decides 改善 vs 回退
    for the whole cell, and it inflates the noise scale that is supposed to catch
    exactly that (D-197)."""
    field = _range_field(metric)
    if metric == METRIC_AQS:
        v = cc.run_aqs(rec)
        if v is None or not cc.keep_value(field, v, implausible):
            return []
        return [v]
    out = []
    for scn in cc.iter_scenarios(rec):
        v = cc.scenario_kpi(scn, metric)
        if v is not None and cc.keep_value(field, v, implausible):
            out.append(v)
    return out


# Two campaigns is the before/after case, which campaign_report answers with a
# noise-qualified delta. A trajectory needs a third point — and until D-196 this
# module rendered a trend for two while the integrated report suppressed the
# section: one corpus, two answers. The threshold lives here so the renderer, the
# report's section gate and the CSV writer cannot disagree about it (D-173).
MIN_CAMPAIGNS_FOR_TREND = 3


def _earliest_by_campaign(records):
    """({campaign_id: earliest plausible started_at_epoch_ms}, all ids, bad ids).

    A timestamp whose magnitude is not a millisecond epoch is left OUT of the
    ordering rather than allowed to sort — it still sorts, just to the wrong
    place."""
    earliest, present, bad = {}, set(), set()
    for rec in records:
        cid = cc.campaign_labels(rec)["campaign_id"]
        present.add(cid)
        ms = cc.run_started_ms(rec)
        if ms is None:
            continue
        if cc.epoch_ms_problem(ms):
            bad.add(cid)
            continue
        if cid not in earliest or ms < earliest[cid]:
            earliest[cid] = ms
    return earliest, present, bad


def order_basis(records, explicit=None):
    """Why (or why not) the campaign order can be trusted.

    "explicit" | "time" | "no_timestamps" | "bad_timestamps". A seconds-valued
    epoch still SORTS, so without this check a campaign lands in 1970 and the
    whole trajectory — with its 改善/回退 verdict — comes out backwards: exactly
    the inversion D-176 closed for the two-campaign path and left open here
    (D-196)."""
    if explicit:
        return "explicit"
    earliest, present, bad = _earliest_by_campaign(records)
    if bad:
        return "bad_timestamps"
    if any(c not in earliest for c in present):
        return "no_timestamps"
    return "time"


def campaign_order(records, explicit=None):
    """Ordered list of campaign_ids. Default: chronological by earliest run ms.

    The `unlabeled` bucket is NOT one of them. It used to sort into the middle of
    the chronology and become a column of its own, so a cell measured once
    without a label and once in a real campaign got a two-point trajectory and an
    改善/回退 verdict computed against "the records nobody labelled" — while the
    section header printed `base → unlabeled → SYNTH-base → SYNTH-opt` with
    nothing saying the second one is not a campaign (D-210). Unlabeled records
    may come from any number of rounds; putting them at one point in time is a
    fabrication, so they are counted and reported, never positioned.
    """
    earliest, present, _bad = _earliest_by_campaign(records)
    present = {c for c in present if c != cc.UNLABELED}
    if explicit:
        # keep only requested ids actually present, preserve requested order
        return [c for c in explicit if c in present]
    # chronological; campaigns with no timestamp sort last, tie-break by id
    return sorted(present, key=lambda c: (earliest.get(c, float("inf")), c))


def _direction(traj, higher_better, within_noise=None, order_ok=True):
    """Classify a trajectory (list of medians / None) -> verdict dict.

    `within_noise` is the three-state verdict on the first-to-last delta. A
    difference smaller than the repeat spread is not a direction: this was the
    report's THIRD difference-of-two-medians and the only one D-144/D-180 never
    reached, so a 1-point drift against a ±12.5 noise scale shipped as 改善
    (D-196). `order_ok=False` means the chronology itself is untrustworthy, so
    no direction may be claimed at all."""
    pts = [v for v in traj if v is not None]
    if len(pts) < 2:
        return {"first_last_delta": None, "direction": None, "monotonic": None,
                "not_computable_reason": "NEED_2_POINTS"}
    delta = pts[-1] - pts[0]
    if not order_ok:
        return {"first_last_delta": delta, "direction": None, "monotonic": None,
                "not_computable_reason": "ORDER_UNTRUSTWORTHY"}
    if within_noise is True:
        return {"first_last_delta": delta, "direction": "within_noise",
                "monotonic": None, "not_computable_reason": None}
    if within_noise is None and delta != 0:
        return {"first_last_delta": delta, "direction": "noise_unknown",
                "monotonic": None, "not_computable_reason": None}
    steps = [b - a for a, b in zip(pts, pts[1:])]
    ups = sum(1 for s in steps if s > 0)
    downs = sum(1 for s in steps if s < 0)
    monotonic = (ups == 0) or (downs == 0)
    net_better = delta if higher_better else -delta   # net movement toward "better"
    if net_better > 0:
        direction = "improving"
    elif net_better < 0:
        direction = "regressing"
    else:
        direction = "flat"
    # a non-monotonic path that nets a change is "mixed" — don't overclaim a trend
    if direction in ("improving", "regressing") and not monotonic:
        direction = "mixed"
    return {"first_last_delta": delta, "direction": direction,
            "monotonic": monotonic, "not_computable_reason": None}


def analyze(records, metric=DEFAULT_METRIC, order=None,
            min_samples=cc.DEFAULT_MIN_SAMPLES):
    ids = campaign_order(records, order)
    cells = defaultdict(lambda: defaultdict(list))   # cell -> campaign_id -> [values]
    implausible = defaultdict(Counter)
    for rec in records:
        labels = cc.campaign_labels(rec)
        cid = labels["campaign_id"]
        key = tuple(labels[d] for d in CELL_DIMS)
        cells[key][cid].extend(_record_values(rec, metric, implausible[key]))

    higher_better = metric_higher_is_better(metric)
    basis = order_basis(records, order)
    order_ok = basis != "bad_timestamps"
    results = []
    for key in sorted(cells):
        per = cells[key]
        traj, ns, low, present_vals = [], [], False, []
        for cid in ids:
            vals = per.get(cid) or []
            traj.append(cc.median(vals) if vals else None)
            ns.append(len(vals))
            if vals:
                present_vals.append(vals)
            if vals and len(vals) < min_samples:
                low = True
        # Same noise machinery the before/after delta uses (D-144) and the media
        # delta uses (D-180) — first-to-last is the same shape and was the one
        # place it never reached (D-196). cc owns the maths so the three cannot
        # drift apart.
        noise = (cc.noise_scale(present_vals[-1], present_vals[0])
                 if len(present_vals) >= 2 else None)
        pts = [v for v in traj if v is not None]
        delta = (pts[-1] - pts[0]) if len(pts) >= 2 else None
        wn = cc.within_noise(delta, noise)
        verdict = _direction(traj, higher_better, within_noise=wn, order_ok=order_ok)
        results.append({
            "cell": dict(zip(CELL_DIMS, key)),
            "trajectory": traj, "sample_counts": ns,
            "present_count": sum(1 for v in traj if v is not None),
            "low_confidence": low, "noise": noise, "within_noise": wn,
            "implausible_values": dict(sorted((implausible.get(key) or {}).items())),
            **verdict,
        })
    return {
        "metric": metric,
        "higher_is_better": higher_better,
        "campaigns": ids,
        "order_basis": basis,
        # excluded from the chronology, never from the accounting (D-210)
        "unlabeled_records": sum(
            1 for r in records
            if cc.campaign_labels(r)["campaign_id"] == cc.UNLABELED),
        "cells": results,
    }


def render_markdown(res):
    arrow = "↑ 越大越好" if res["higher_is_better"] else "↓ 越小越好"
    lines = [
        f"## 纵向趋势（{res['metric']}；{arrow}）",
        "",
        f"> 战役时序：{' → '.join(res['campaigns']) or '（无标签战役）'}。"
        "缺席战役的格记 `—` 不插值；方向按指标极性解释为 改善/回退/混合。",
        "",
        "> **噪声尺度**：" + cc.NOISE_CAVEAT,
        "",
    ]
    if res.get("unlabeled_records"):
        lines += [f"> ⚠ 另有 **{res['unlabeled_records']} 条记录无战役标签**，"
                  "**未列入上面的时序**——「无标签」不是一个战役，它可能来自任意多个轮次，"
                  "把它摆在时间轴的某一点上就是**凭空造出一个战役**（D-210）。"
                  "这些记录仍计入其他各段；要让它们进入趋势，先用 "
                  "`annotate_campaign.py` 补注 `campaign_id`。", ""]
    if res.get("order_basis") == "bad_timestamps":
        lines += ["> ⚠ **战役时序不可信**：有战役的 `started_at_epoch_ms` 取值不像毫秒时间戳"
                  "（见语料级告警）。按它排序会把战役排到错误的先后上、把改善印成回退，"
                  "故**本段不给方向判定**；先修生产端时间戳，或用 `--order` 显式指定顺序。", ""]
    if len(res["campaigns"]) < MIN_CAMPAIGNS_FOR_TREND:
        lines.append(
            f"_少于 {MIN_CAMPAIGNS_FOR_TREND} 个战役，无法成趋势_——"
            "两个战役是「优化前后」的情形，请看该段（它给的是**带噪声尺度**的 Δ）；"
            "单战役请用热力卡/归因。")
        return "\n".join(lines)
    if not res["cells"]:
        lines.append("_无可成轨迹的单元。_")
        return "\n".join(lines)

    head = ("| 点位 | 运营商 | 时段 | " + " | ".join(res["campaigns"])
            + " | 首末Δ | 噪声 | 方向 | 备注 |")
    sep = "|" + "---|" * (3 + len(res["campaigns"]) + 4)
    lines += [head, sep]
    for c in res["cells"]:
        cl = {k: cc.md_cell(v) for k, v in c["cell"].items()}   # labels are human-typed
        traj = " | ".join(cc.fmt_num(v) for v in c["trajectory"])
        dir_map = {"improving": "改善", "regressing": "回退", "mixed": "混合",
                   "flat": "持平", "within_noise": "**噪声内**",
                   "noise_unknown": "噪声不可估", None: "不可计算"}
        notes = []
        if c["not_computable_reason"]:
            notes.append(c["not_computable_reason"])
        if c.get("implausible_values"):
            notes.append("**IMPLAUSIBLE_VALUE:" + "; ".join(
                f"{r}×{n}" for r, n in sorted(c["implausible_values"].items())) + "**")
        if c["low_confidence"]:
            notes.append("low_conf")
        noise = f"±{cc.fmt_num(c.get('noise'), 1)}" if c.get("noise") is not None else "—"
        # 「噪声不可估」 beside a printed ±0 denies the estimate standing next to
        # it. The data-side key stays `noise_unknown`; only the word the reader
        # sees separates the two causes (D-224).
        if c["direction"] == "noise_unknown":
            dir_map = dict(dir_map,
                           noise_unknown=cc.noise_unjudgeable_note(c.get("noise")))
        lines.append(
            f"| {cl['point_id']} | {cl['carrier']} | {cl['time_band']} | {traj} | "
            f"{cc.fmt_num(c['first_last_delta'])} | {noise} | {dir_map[c['direction']]} | "
            f"{'; '.join(notes) or '—'} |")
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB longitudinal campaign trend")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--metric", default=DEFAULT_METRIC,
                    help="'aqs' (default) or a KPI key like n1_rtt_p50_ms")
    ap.add_argument("--order", help="explicit campaign_id order, comma-separated")
    ap.add_argument("--min-samples", type=int, default=cc.DEFAULT_MIN_SAMPLES)
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    order = [c.strip() for c in args.order.split(",")] if args.order else None
    recs, files = cc.load_records(args.inputs)
    res = analyze(recs, args.metric, order, args.min_samples)
    print(render_markdown(res))
    print(f"\n<!-- records={len(recs)} files={len(files)} campaigns={len(res['campaigns'])} -->",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
