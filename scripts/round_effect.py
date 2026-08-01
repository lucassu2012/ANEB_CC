#!/usr/bin/env python3
"""ANEB warm-up / round effect: is the FIRST round systematically worse? (stdlib only)

Forensic mode runs every scenario several times; `scenarios[].repeat_index` is the
ROUND (0-based). Quick mode runs one round, so its repeat_index is always 0.

Measured on the first real forensic corpus (D-355): round 0 came back 8-12% worse
on latency and 10-16% lower on goodput than rounds 1-2, while position WITHIN a
round moved only 2-4% - noise. That is a warm-up cost (app cold start, TLS
handshake, radio wake), not a position bias.

Why this is a module and not a note: `order_effect` groups by ABSOLUTE
`order_index`, and in a three-round Latin square a profile's three positions land
in three different rounds. Its verdict is numerically right and reads as a
position bias. This module answers the other half, and the two together tell
warm-up from carryover - the distinction decides what an operator should DO
(discard a warm-up round vs. fix counterbalancing).

The consequential case is the ordinary one: a SINGLE-round corpus cannot check
for warm-up at all, and that is precisely when every absolute number it prints is
a cold-start number. This module says so rather than staying silent (R-10:
「查不了」≠「没问题」).

Direction comes from `trend.metric_higher_is_better` - the one place that already
says which way is better (§2.14), never a second copy.

Usage:
    python round_effect.py results/*.jsonl
"""
import argparse
import sys
from collections import Counter, defaultdict

import campaign_common as cc
import trend

# Same triple the order-effect diagnostic uses: the KPIs where a systematic shift
# would bias the campaign medians (§2.14 - one list, one meaning).
ROUND_KPIS = ("t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps")

# Same triple, same meaning, as every other rollup (§2.14). This module pools
# every cell into one per-round comparison on purpose - sample size is the whole
# point - but pooling has a premise, and until D-380 nothing here checked it.
# order_effect has had `position_cell_spread` since D-335; this is the same
# premise on the other axis (D-380).
CELL_DIMS = ("point_id", "carrier", "time_band")

# A first-round penalty above this share of the later-round median is called out.
# 10% is the same magnitude the order-effect gate uses, for the same reason: the
# measured run-to-run CV on this corpus is 5.5-10.3% (D-353), so a shift smaller
# than roughly one noise scale is not distinguishable from noise here. It is a
# screening threshold, not a significance test, and the table prints the measured
# percentage beside it so a reader can judge for themselves.
DEFAULT_WARMUP_PCT = 10.0

# Minimum samples per round for the comparison to mean anything. Two rounds each
# holding one sample is a difference of two readings - the same arithmetic floor
# the stability section applies to CV and the order-effect section to positions.
MIN_PER_ROUND = 2


def round_values(records, kpi):
    """({round -> [values]}, [values with no round], ruled_out_n, {round -> Counter(cell)}).

    A scenario carrying no `repeat_index` is NOT silently treated as round 0: it
    lands in the unknown bucket and is reported, never merged (R-10). A scenario
    the PO ruling excludes from this KPI's cross-profile pool (D-366: s1_chat's
    2KB burst is a latency proxy, not throughput) is counted, never silent.

    The fourth return is the pooling premise's evidence: which cells fed each
    round. The verdict below is a difference of medians ACROSS rounds pooled
    over every cell, so a round fed by cells another round never saw makes that
    difference a cell effect wearing a warm-up's clothes (D-380).
    """
    rounds, unknown, ruled_out = defaultdict(list), [], 0
    cell_mix = defaultdict(Counter)
    for rec in records:
        labels = cc.campaign_labels(rec)
        for scn in cc.iter_scenarios(rec):
            v = cc.scenario_kpi(scn, kpi)
            if v is None:
                continue
            if cc.kpi_profile_excluded(kpi, scn.get("profile_id")):
                ruled_out += 1
                continue
            ri = scn.get("repeat_index")
            if isinstance(ri, int) and not isinstance(ri, bool):
                rounds[ri].append(v)
                cell_mix[ri][tuple(labels[d] for d in CELL_DIMS)] += 1
            else:
                unknown.append(v)
    return dict(rounds), unknown, ruled_out, dict(cell_mix)


def round_cell_spread(mix):
    """Did every ROUND draw on the same SET of cells?

    `mix`: {round -> Counter(cell key)}. Returns (imbalanced, uneven), where
    `uneven` names the cells missing from at least one round — the evidence and
    the flag come out of the same computation, so they cannot drift apart.

    None when there is nothing to compare (fewer than two rounds carried
    values): not checkable is not the same as fine (R-10).

    Deliberately the same shape, the same SETS-not-distributions trade-off and
    the same reasoning as `order_effect.position_cell_spread` (D-335) — one
    premise, one way of checking it, two axes (§2.14). The measured case it
    exists for: a 「quick 主体 + 取证子集」 corpus pools round 0 over all 32 cells
    and rounds 1-2 over the 8-cell forensic subset, and this section printed
    「21% 疑似预热效应」 over per-round n of 1443/88/91. None of the 21% was
    warm-up; all of it was which cells fed which round (T6 rehearsal F-2).
    """
    seen = [frozenset(c) for c in mix.values() if c]
    if len(seen) < 2:
        return None, []
    union = set().union(*seen)
    common = set(seen[0]).intersection(*seen[1:])
    uneven = sorted("/".join(str(x) for x in k) for k in (union - common))
    return bool(uneven), uneven


def analyze_kpi(rounds, unknown, kpi, threshold_pct=DEFAULT_WARMUP_PCT, ruled_out=0,
                cell_mix=None):
    """Warm-up verdict for one KPI. `rounds`: {round -> [values]}."""
    per_round = {r: {"median": cc.median(v), "n": len(v)}
                 for r, v in sorted(rounds.items())}
    imbalanced, uneven = round_cell_spread(cell_mix or {})
    out = {
        "kpi": kpi,
        "rounds": per_round,
        "unknown_round_n": len(unknown),
        "ruled_out_n": ruled_out,
        "round_cell_imbalance": imbalanced,
        "round_cells_uneven": uneven,
        "first_round_penalty_pct": None,
        "warm_up_suspected": None,
        "not_computable_reason": None,
        "low_confidence": any(p["n"] < MIN_PER_ROUND for p in per_round.values()),
    }
    if len(per_round) < 2:
        # The ordinary case for quick mode, and the one worth saying out loud.
        out["not_computable_reason"] = "SINGLE_ROUND"
        return out
    if any(p["n"] < MIN_PER_ROUND for p in per_round.values()):
        out["not_computable_reason"] = "UNREPLICATED_ROUNDS"
        return out

    first_key = min(per_round)
    first = per_round[first_key]["median"]
    rest = cc.median([p["median"] for r, p in per_round.items() if r != first_key])
    if first is None or rest is None or abs(rest) < 1e-9:
        out["not_computable_reason"] = "MEDIAN_NEAR_ZERO"
        return out
    # Positive = the first round is WORSE. Direction from the single source that
    # already knows which way is better, so latency and goodput read alike.
    delta = (rest - first) if trend.metric_higher_is_better(kpi) else (first - rest)
    out["first_round_penalty_pct"] = delta / abs(rest) * 100.0
    if imbalanced:
        # The percentage is still computed and still printed — the premise
        # qualifies what was measured, it does not erase it, exactly as the
        # order-effect section keeps its 极差 columns (D-335). What is refused is
        # the VERDICT: a round difference the cells could equally explain
        # supports neither 「疑似预热」 nor 「无明显预热」. Flagging a verdict is not
        # the same as declining to issue one (D-313/D-354).
        out["not_computable_reason"] = "CELL_CONFOUNDED"
        return out
    out["warm_up_suspected"] = out["first_round_penalty_pct"] > threshold_pct
    return out


def analyze(records, kpis=ROUND_KPIS, threshold_pct=None):
    """Per-KPI warm-up verdicts + the corpus-level round count."""
    # read live, not captured in the signature - this gate is archived in the
    # provenance manifest, which promises changing it changes the report (D-204)
    threshold_pct = DEFAULT_WARMUP_PCT if threshold_pct is None else threshold_pct
    entries, seen_rounds = [], set()
    for kpi in kpis:
        rounds, unknown, ruled_out, cell_mix = round_values(records, kpi)
        seen_rounds |= set(rounds)
        entries.append(analyze_kpi(rounds, unknown, kpi, threshold_pct, ruled_out,
                                   cell_mix))
    return {"kpis": entries, "distinct_rounds": len(seen_rounds),
            "threshold_pct": threshold_pct}


def summarize(records, threshold_pct=None):
    """Corpus-level verdict for the report summary - one source, so the section
    and the summary cannot answer differently (§2.14, D-338)."""
    res = analyze(records, threshold_pct=threshold_pct)
    judged = [e for e in res["kpis"] if e["warm_up_suspected"] is not None]
    reasons = defaultdict(int)
    for e in res["kpis"]:
        if e["not_computable_reason"]:
            reasons[e["not_computable_reason"]] += 1
    # max, not sum: every KPI counts the same label-less scenarios, so summing
    # would multiply one missing label by the number of KPIs.
    unknown = max((e["unknown_round_n"] for e in res["kpis"]), default=0)
    return {
        "distinct_rounds": res["distinct_rounds"],
        "single_round": res["distinct_rounds"] < 2,
        # Zero rounds seen but values exist = the corpus has NO repeat_index at
        # all. That is a producer regression or a foreign corpus, NOT quick mode
        # (quick writes repeat_index=0 too) — consumers must not attribute it to
        # quick's single round (D-364).
        "no_round_labels": res["distinct_rounds"] == 0 and unknown > 0,
        "unknown_round_n": unknown,
        "judged": len(judged),
        "suspected": [e for e in judged if e["warm_up_suspected"]],
        "unjudged_reasons": dict(reasons),
    }


def render_markdown(res):
    lines = ["## 预热效应（首轮是否系统性更差）", ""]
    if res["distinct_rounds"] < 2:
        unknown = max((e["unknown_round_n"] for e in res["kpis"]), default=0)
        if res["distinct_rounds"] == 0:
            # Attributing a label-less corpus to quick mode would be a plausible
            # lie about WHY warm-up cannot be checked (D-364): a forensic corpus
            # that lost its labels would read as "quick 单轮、冷启动口径".
            if unknown:
                lines += [
                    f"> 本轮语料的场景**全部缺失轮次编号**（`repeat_index` 未写，{unknown} 个"
                    "场景有数无编号）——**预热效应无法核算**。这**不是** quick 模式的正常形状"
                    "（quick 也写 `repeat_index=0`）：先查生产端/语料来源，再谈冷启动口径。",
                    "",
                ]
            else:
                lines += ["> 无任何带轮次的 KPI 数据——预热效应无法核算。", ""]
            return "\n".join(lines)
        lines += [
            "> 本轮语料**只有一轮**（quick 模式每场景只跑一遍）——**预热效应无法校验**。"
            "**这不等于没有**：取证语料实测首轮时延高 8–12%、吞吐低 10–16%（D-355），"
            "而单轮模式测到的**永远是那一轮**，所以本报告的**绝对值均为冷启动口径**；"
            "跨格比较不受影响（每格一样冷）。",
            "",
        ]
        if unknown:
            lines += [f"> 另有 {unknown} 个场景无轮次编号（未计入）。", ""]
        return "\n".join(lines)
    lines += [
        f"> 判据：首轮中位与**其后各轮中位的中位数**相比差 >{cc.fmt_num(res['threshold_pct'], 1)}%"
        "（按各 KPI 自己的好坏方向；正值=首轮更差）即疑似预热效应。"
        f"每轮至少 {MIN_PER_ROUND} 个样本才判。",
        "",
    ]
    # The pooling premise, said once above the table as well as per row: a
    # premise that only appears inside a 备注 cell is a premise most readers
    # never see (§2.6, the same reasoning order_effect uses since D-335).
    mixed = [e for e in res["kpis"] if e.get("round_cell_imbalance")]
    if mixed:
        lines += [
            f"> ⚠ {len(mixed)} 个 KPI 的**各轮与单元不平衡**（有单元未出现在每一轮）——"
            "本诊断把所有单元汇池比较，该前提不成立时轮次差**不可单独归因于预热**"
            "（可能是点位/运营商/时段的格构成差穿了预热的外衣，也可能反过来掩盖真效应）。"
            "见备注列点名的单元。**处置：按采集模式分面，各自单独出一次报告**。",
            "",
        ]
    lines += [
        "| KPI | 各轮中位(n) | 首轮劣势% | 判定 | 备注 |",
        "|---|---|---|---|---|",
    ]
    for e in res["kpis"]:
        cells = " / ".join(f"#{r}:{cc.fmt_num(p['median'], 2)}(n={p['n']})"
                           for r, p in sorted(e["rounds"].items())) or "—"
        if e["warm_up_suspected"] is None:
            verdict = "不可计算"
        elif e["warm_up_suspected"]:
            verdict = "**疑似预热效应**"
        else:
            verdict = "无明显预热"
        # A cell that one round never saw makes the round difference
        # unattributable in EITHER direction: a slow point feeding only round 0
        # invents a warm-up penalty, and it can equally mask a real one.
        # Printing a verdict the numbers cannot support is worse than printing
        # none (§2.12) — the 各轮中位(n) and 首轮劣势% columns still show exactly
        # what was measured, including the lopsided per-round n that gave it away.
        if e.get("round_cell_imbalance"):
            verdict = "**不可单独归因(单元混杂)**"
        notes = []
        if e.get("round_cell_imbalance"):
            uneven = e["round_cells_uneven"]
            shown = "、".join(cc.md_cell(c) for c in uneven[:3])
            notes.append("**CELL_CONFOUNDED:" + shown
                         + (f" 等 {len(uneven)} 个" if len(uneven) > 3 else "")
                         + " 未出现在每一轮**")
        # the bare code is redundant next to the line above, which already names
        # it AND the cells; every OTHER code still prints itself (D-354)
        if e["not_computable_reason"] and e["not_computable_reason"] != "CELL_CONFOUNDED":
            notes.append(e["not_computable_reason"])
        if e["unknown_round_n"]:
            notes.append(f"{e['unknown_round_n']} 个场景无轮次编号（未计入）")
        if e.get("ruled_out_n"):
            notes.append(f"RULED_OUT:{e['ruled_out_n']}（D-366）")
        if e["low_confidence"]:
            notes.append("low_conf")
        lines.append(f"| {e['kpi']} | {cells} | "
                     f"{cc.fmt_num(e['first_round_penalty_pct'], 1)} | {verdict} | "
                     f"{'; '.join(notes) or '—'} |")
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB warm-up / round-effect diagnostic")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--threshold-pct", type=float, default=DEFAULT_WARMUP_PCT)
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    recs, files = cc.load_records(args.inputs)
    print(render_markdown(analyze(recs, threshold_pct=args.threshold_pct)))
    print(f"\n<!-- records={len(recs)} files={len(files)} -->", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
