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
from collections import defaultdict

import campaign_common as cc
import trend

# Same triple the order-effect diagnostic uses: the KPIs where a systematic shift
# would bias the campaign medians (§2.14 - one list, one meaning).
ROUND_KPIS = ("t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps")

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
    """({round_index -> [values]}, [values with no round], ruled_out_n) for one KPI.

    A scenario carrying no `repeat_index` is NOT silently treated as round 0: it
    lands in the unknown bucket and is reported, never merged (R-10). A scenario
    the PO ruling excludes from this KPI's cross-profile pool (D-366: s1_chat's
    2KB burst is a latency proxy, not throughput) is counted, never silent.
    """
    rounds, unknown, ruled_out = defaultdict(list), [], 0
    for rec in records:
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
            else:
                unknown.append(v)
    return dict(rounds), unknown, ruled_out


def analyze_kpi(rounds, unknown, kpi, threshold_pct=DEFAULT_WARMUP_PCT, ruled_out=0):
    """Warm-up verdict for one KPI. `rounds`: {round -> [values]}."""
    per_round = {r: {"median": cc.median(v), "n": len(v)}
                 for r, v in sorted(rounds.items())}
    out = {
        "kpi": kpi,
        "rounds": per_round,
        "unknown_round_n": len(unknown),
        "ruled_out_n": ruled_out,
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
    out["warm_up_suspected"] = out["first_round_penalty_pct"] > threshold_pct
    return out


def analyze(records, kpis=ROUND_KPIS, threshold_pct=None):
    """Per-KPI warm-up verdicts + the corpus-level round count."""
    # read live, not captured in the signature - this gate is archived in the
    # provenance manifest, which promises changing it changes the report (D-204)
    threshold_pct = DEFAULT_WARMUP_PCT if threshold_pct is None else threshold_pct
    entries, seen_rounds = [], set()
    for kpi in kpis:
        rounds, unknown, ruled_out = round_values(records, kpi)
        seen_rounds |= set(rounds)
        entries.append(analyze_kpi(rounds, unknown, kpi, threshold_pct, ruled_out))
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
        notes = []
        if e["not_computable_reason"]:
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
