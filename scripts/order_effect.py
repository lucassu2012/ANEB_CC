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

# Same triple, same meaning, as every other rollup (§2.14). This module groups
# by profile_id and pools every cell together on purpose — sample size is the
# whole point — but pooling has a premise, and this is what checks it (D-335).
CELL_DIMS = ("point_id", "carrier", "time_band")


def collect_positions(records, kpi):
    """{profile_id -> {order_index -> [values]}} plus scenario_order counts.

    Fifth return: {profile_id -> Counter} of readings refused as impossible."""
    cells = defaultdict(lambda: defaultdict(list))
    # profile -> order_index -> Counter(cell key). The verdict below is a
    # difference of medians ACROSS positions, pooled over every cell; if one
    # position was fed by cells another position never saw, that difference is
    # a cell effect wearing an order effect's clothes (D-335).
    cell_mix = defaultdict(lambda: defaultdict(Counter))
    implausible = defaultdict(Counter)
    orders = Counter()
    rounds = Counter()
    rotating_runs = 0
    for rec in records:
        order = cc.run_obj(rec).get("scenario_order")
        orders[order if isinstance(order, str) and order else "absent"] += 1
        # `scenario_order` is ROUND-STRUCTURED: the contract's own example is
        # "s1,s2,s3|s2,s3,s1" — one comma list per round, pipe-joined. Counting
        # whole strings meant a forensic corpus whose every run rotates
        # internally (the shape that DID counterbalance) was reported as
        # "拉丁方未轮转" — a false alarm on exactly the correct corpus (D-164).
        if isinstance(order, str) and order:
            parts = [p.strip() for p in order.split("|") if p.strip()]
            rounds.update(parts)
            if len(set(parts)) > 1:
                rotating_runs += 1
        for scn in cc.iter_scenarios(rec):
            idx = cc.scenario_order_index(scn)
            val = cc.scenario_kpi(scn, kpi)
            if idx is None or val is None:
                continue
            pid = scn.get("profile_id") or "?"
            # This verdict is a RATIO of medians (position spread / overall), so
            # one impossible reading moves both terms at once: it can invent a
            # 拉丁方 failure where the counterbalancing worked, or mask a real one
            # by inflating the denominator. Out of the pool, counted (D-197).
            if not cc.keep_value(kpi, val, implausible[pid]):
                continue
            cells[pid][idx].append(val)
            labels = cc.campaign_labels(rec)
            cell_mix[pid][idx][tuple(labels[d] for d in CELL_DIMS)] += 1
    return cells, orders, rounds, rotating_runs, implausible, cell_mix


def analyze_profile(positions, min_samples=cc.DEFAULT_MIN_SAMPLES,
                    threshold_pct=None):
    """Order-effect verdict for one profile. `positions`: {order_index -> [values]}."""
    # read live, not captured in the signature — this gate is archived in the
    # provenance manifest, which promises changing it changes the report (D-204)
    threshold_pct = DEFAULT_THRESHOLD_PCT if threshold_pct is None else threshold_pct
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
    # Every position holding a single sample means the spread IS the run-to-run
    # noise: there is no within-position variability to judge it against, so the
    # threshold comparison decides nothing. Measured on the first real forensic
    # corpus (D-354): one run, three positions per profile at n=1 each, and the
    # summary announced 「疑似序位偏倚 8/9 … 本报告的 KPI 中位数据此存疑」 — the whole
    # report's medians called into doubt by a comparison that cannot
    # discriminate. This is the arithmetic floor the stability section already
    # applies to CV (needs n>=2), for the same reason, said the same way (§2.14).
    # `low_confidence` alone did not stop it: flagging a verdict is not the same
    # as declining to issue one (D-313).
    unreplicated = all(p["n"] < 2 for p in pos.values())
    if unreplicated:
        reason = "UNREPLICATED_POSITIONS"
    elif spread_pct is None:
        reason = "MEDIAN_NEAR_ZERO"
    else:
        reason = None
    return {
        "positions": pos,
        "spread": spread,
        "spread_pct": spread_pct,
        "overall_median": overall,
        "order_effect_suspected": (None if reason is not None
                                   else spread_pct > threshold_pct),
        "low_confidence": any(p["low_confidence"] for p in pos.values()),
        "not_computable_reason": reason,
    }


def position_cell_spread(mix):
    """Did every execution position draw on the same SET of cells?

    `mix`: {order_index -> Counter(cell key)}. Returns (imbalanced, uneven),
    where `uneven` names the cells missing from at least one position — the
    evidence and the flag come out of the same computation, so they cannot
    drift apart.

    None when there is nothing to compare (fewer than two positions carried
    values): not checkable is not the same as fine (R-10).

    SETS, not distributions, on purpose. An unequal split (7 samples here, 4
    there) confounds too, but a cell one position never saw at all is
    unarguable, and a premise check that cries wolf gets ignored. The stronger
    test is left undone knowingly, not overlooked (D-335).
    """
    seen = [frozenset(c) for c in mix.values() if c]
    if len(seen) < 2:
        return None, []
    union = set().union(*seen)
    common = set(seen[0]).intersection(*seen[1:])
    uneven = sorted("/".join(str(x) for x in k) for k in (union - common))
    return bool(uneven), uneven


def analyze(records, kpi=DEFAULT_KPI, min_samples=cc.DEFAULT_MIN_SAMPLES,
            threshold_pct=None):
    # resolved here as well: the result dict publishes `threshold_pct` and the
    # renderer prints it as the gate in force (D-204)
    threshold_pct = DEFAULT_THRESHOLD_PCT if threshold_pct is None else threshold_pct
    (cells, orders, rounds, rotating_runs, implausible,
     cell_mix) = collect_positions(records, kpi)
    profiles = []
    # a profile whose every reading was refused still gets a row: it has no
    # verdict, and "no verdict because the numbers were impossible" is the thing
    # worth telling the operator
    for pid in sorted(set(cells) | {p for p, c in implausible.items() if c}):
        imbalanced, uneven = position_cell_spread(cell_mix.get(pid) or {})
        profiles.append({"profile_id": pid,
                         "implausible_values": dict(sorted((implausible.get(pid) or {}).items())),
                         "position_cell_imbalance": imbalanced,
                         "position_cells_uneven": uneven,
                         **analyze_profile(cells.get(pid) or {}, min_samples, threshold_pct)})
    distinct = len([k for k in orders if k != "absent"])
    return {
        "kpi": kpi,
        "threshold_pct": threshold_pct,
        "min_samples": min_samples,
        "profiles": profiles,
        "scenario_orders": dict(orders),
        "distinct_orders": distinct,
        # Distinct ROUNDS across the whole corpus — the unit the Latin square
        # actually rotates. One round total = never rotated, whether that is one
        # run repeated or many runs all carrying the same single round (D-164).
        "distinct_rounds": len(rounds),
        "rounds": dict(cc.ranked(rounds)),
        "rotates_within_run": rotating_runs,
        "rotation_warning": len(rounds) == 1,
        "no_order_evidence": distinct == 0,
    }


def summarize(records, min_samples=cc.DEFAULT_MIN_SAMPLES):
    """Corpus-level order-effect verdict, over every ORDER_SENSITIVE_KPIS entry.

    One source for both front doors. publish_check computed this inline and the
    report summary did not compute it at all — so the gate could WARN 「疑似位置-
    KPI 相关」 while the one section decision-makers read closely never mentioned
    order effect existed. Two front doors disagreeing about what the reader has
    to know is D-330's shape; keeping the partition here means they cannot drift
    apart either (§2.14, D-338).

    `confounded` profiles are held out of `judged` exactly as not-computable is:
    positions fed by different cells cannot support a verdict in either
    direction (D-335).
    """
    biased, judged, confounded, balance_ok = [], 0, [], 0
    no_evidence, never_rotated = True, False
    unjudged = Counter()
    for k in ORDER_SENSITIVE_KPIS:
        res = analyze(records, kpi=k, min_samples=min_samples)
        no_evidence = no_evidence and res["no_order_evidence"]
        never_rotated = never_rotated or res["rotation_warning"]
        for p in res["profiles"]:
            if p.get("position_cell_imbalance"):
                confounded.append(dict(p, kpi=k))
                continue
            if p.get("position_cell_imbalance") is False:
                balance_ok += 1
            if p["order_effect_suspected"] is None:
                # WHY it could not be judged, counted rather than guessed at by
                # the caller. The summary used to pick between two reasons with
                # an if/else, so the moment a third existed it printed a false
                # explanation — 「位次不足 2」 about a profile that had three
                # positions and no replication inside them (D-354).
                unjudged[p["not_computable_reason"] or "UNKNOWN"] += 1
                continue
            judged += 1
            if p["order_effect_suspected"]:
                biased.append(dict(p, kpi=k))
    return {"biased": biased, "judged": judged, "confounded": confounded,
            "balance_ok": balance_ok, "no_evidence": no_evidence,
            "never_rotated": never_rotated, "unjudged_reasons": dict(unjudged)}


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
        lines.append("> ⚠ 全语料只有**一种轮次**（`scenario_order` 按 `|` 拆分后）"
                     "——拉丁方未轮转，反平衡在构造上不成立，位次差无法与场景差分离。")
        lines.append("")
    elif res.get("rotates_within_run"):
        lines.append(f"> 轮转口径：共 {res['distinct_rounds']} 种轮次，其中 "
                     f"{res['rotates_within_run']} 条 run **在自身内部**已轮转"
                     "（`s1,s2,s3|s2,s3,s1` 形状），反平衡在构造上成立。")
        lines.append("")

    # Pooling every cell into one per-profile comparison is deliberate — sample
    # size is the point — but it has a premise, and until D-335 nothing checked
    # it. Said once above the table as well as per row: a premise that only
    # appears inside a 备注 cell is a premise most readers never see (§2.6).
    mixed = [p for p in res["profiles"] if p.get("position_cell_imbalance")]
    if mixed:
        lines.append(f"> ⚠ {len(mixed)} 个 profile 的**执行位次与单元不平衡**"
                     "（有单元未出现在每个位次）——本诊断把所有单元汇池比较，"
                     "该前提不成立时位次差**不可单独归因于序位**（可能是点位/运营商/"
                     "时段差穿了序位的外衣，也可能反过来掩盖真效应）。见备注列。")
        lines.append("")

    if not res["profiles"]:
        lines.append("_无可诊断样本（记录缺 order_index 或该 KPI）。_")
        return "\n".join(lines)

    lines += ["| profile | 位次中位数 | 极差 | 极差% | 总体中位 | 判定 | 备注 |",
              "|---|---|---|---|---|---|---|"]
    for p in res["profiles"]:
        # The row prints the position medians, their spread, the overall median
        # and the spread as a percentage of it — two relations the reader can
        # check on the page. Rounded independently they disagreed on 26% and 15%
        # of rows respectively (D-226).
        pos = sorted(p["positions"].items())
        meds = [v["median"] for _, v in pos]
        k = len(meds)

        def _holds(r, d, k=k):
            span_ok = abs((max(r[:k]) - min(r[:k])) - r[k]) < 0.5 * 10 ** -(d + 3)
            if not r[k + 1]:
                return span_ok
            return span_ok and abs(r[k] / abs(r[k + 1]) * 100.0
                                   - r[k + 2]) < 0.5 * 10 ** -d

        shown, reconciled = cc.fmt_values_consistent(
            meds + [p["spread"], p["overall_median"], p["spread_pct"]], _holds)
        pos_txt = " / ".join(f"#{i}:{s}(n={v['n']})"
                             for (i, v), s in zip(pos, shown)) or "—"
        spread_s, overall_s, pct_s = shown[k], shown[k + 1], shown[k + 2]
        if p["order_effect_suspected"] is None:
            verdict = "不可计算"
        elif p["order_effect_suspected"]:
            verdict = "**疑似序位偏倚**"
        else:
            verdict = "无明显效应"
        # A cell that one position never saw makes the position difference
        # unattributable in EITHER direction: a slow point feeding only #1
        # invents an order effect, and it can equally mask a real one. Printing
        # a verdict the numbers cannot support is worse than printing none
        # (§2.12) — the 极差 columns still show exactly what was measured.
        if p.get("position_cell_imbalance"):
            verdict = "**不可单独归因(单元混杂)**"
        notes = []
        if p.get("position_cell_imbalance"):
            uneven = p["position_cells_uneven"]
            shown = "、".join(cc.md_cell(c) for c in uneven[:3])
            notes.append("**CELL_CONFOUNDED:" + shown
                         + (f" 等 {len(uneven)} 个" if len(uneven) > 3 else "")
                         + " 未出现在每个位次**")
        if p["not_computable_reason"]:
            notes.append(p["not_computable_reason"])
        if p.get("implausible_values"):
            notes.append("**IMPLAUSIBLE_VALUE:" + "; ".join(
                f"{r}×{n}" for r, n in sorted(p["implausible_values"].items())) + "**")
        if p["low_confidence"]:
            notes.append("low_conf")
        if reconciled is False:
            notes.append("ROUNDING_UNRECONCILED")
        lines.append(
            # md_cell, like every other label column: D-128 escaped point_id
            # because a '|' or newline splits the row, and profile_id is the
            # same kind of value reaching the same kind of cell (D-334)
            f"| {cc.md_cell(p['profile_id'])} | {pos_txt} | {spread_s} | "
            f"{pct_s} | {overall_s} | "
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
