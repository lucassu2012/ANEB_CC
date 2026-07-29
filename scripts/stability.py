#!/usr/bin/env python3
"""ANEB repeatability / stability analysis — coefficient of variation (stdlib only).

Serves the plan's M1 acceptance「同点位复测 TTFT 变异系数 ≤10%」: for each cell
(point,carrier,time_band,profile) and KPI, compute CV% = stdev/mean*100 across the
repeats gathered there and flag cells whose CV exceeds the gate (default 10%). A
high CV means the measurement isn't repeatable there — the cell's median cannot be
trusted as a stable characterization.

Honesty (R-10): <2 samples -> CV None (not computable, not 0); |mean|≈0 -> None
(CV undefined, never a fabricated 0); `unstable` (CV>gate) is kept distinct from
`low_confidence` (n<min_samples). claim_scope unchanged.

Usage: python stability.py results/*.jsonl [--kpi t1_ttft_ms] [--cv-gate 10]
"""
import argparse
import statistics
import sys
from collections import Counter

import campaign_common as cc

DEFAULT_CV_GATE = 10.0  # percent — plan M1 acceptance「复测 CV ≤ 10%」
DEFAULT_STABILITY_KPIS = ("t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps")
# tier is IN the key: a repeat targets the same server tier, so pooling tiers would
# conflate tier-difference with measurement noise. CV here = true same-condition
# repeatability.
#
# campaign_id is in the key for exactly the same reason (D-145). Two campaigns are
# two conditions — that is the entire premise of the before/after comparison — so
# pooling them makes CV measure the optimisation instead of the repeatability. It
# is not a blend like the heat card's, it is a wrong number: two campaigns of
# CV 0.4% and 0.26% around medians 400 and 600 pool to CV 21% and get flagged
# unstable, and the runbook then tells the operator to go resample a cell whose
# measurement was excellent.
STAB_GROUP_BY = ("campaign_id", "point_id", "carrier", "time_band", "tier", "profile_id")


def cv_percent(values):
    """Coefficient of variation (%) = sample stdev / mean * 100, or None.

    None on <2 usable samples, and also on any mean that is not positive. CV is
    defined on ratio scales with a true zero; a non-positive mean means either
    the pool is corrupt or the quantity is not one CV applies to (a dBm reading,
    say). Dividing anyway does not fail loudly — it yields a NEGATIVE CV, and
    `cv > gate` is then false for every gate, so the least repeatable cell in the
    corpus renders 稳定 with an empty note (D-197). A verdict that is wrong in
    the reassuring direction is worse than no verdict.
    """
    xs = [v for v in values if v is not None]
    if len(xs) < 2:
        return None
    m = statistics.fmean(xs)
    if m <= 1e-9:
        return None
    return statistics.stdev(xs) / m * 100.0


def cv_reason(vals, cv):
    """Why CV is not computable here, or None. Named because the two causes call
    for different actions: measure more, or go fix what produced these numbers."""
    if cv is not None:
        return None
    if len([v for v in vals if v is not None]) < 2:
        return "n<2"
    return "mean<=0"


# `None` already means "no cap" in render_markdown's API, so the archived
# default needs a sentinel of its own (D-204).
_UNSET = object()


def stability_cells(records, kpi_key, group_by=None,
                    cv_gate=None, min_samples=cc.DEFAULT_MIN_SAMPLES):
    # read live, not captured in the signature — see cc.aqs_grade (D-204).
    # group_by sat captured right beside cv_gate until D-269: the fix had been
    # applied to the archived gate and not to the one next to it, which decides
    # what a stability cell IS and was archived nowhere at all.
    cv_gate = DEFAULT_CV_GATE if cv_gate is None else cv_gate
    group_by = STAB_GROUP_BY if group_by is None else group_by
    buckets = {}
    implausible = {}
    for rec in records:
        labels = cc.campaign_labels(rec)
        for scn in cc.iter_scenarios(rec):
            v = cc.scenario_kpi(scn, kpi_key)
            if v is None:
                continue
            pid = scn.get("profile_id") or "?"
            key = tuple(pid if f == "profile_id" else (labels.get(f) or cc.UNLABELED)
                        for f in group_by)
            # Out of the pool, counted where it shows — the treatment the heat
            # card and the attribution matrix have given impossible values since
            # D-178, and which the corpus banner has been promising on this
            # section's behalf ever since (D-197).
            bad = implausible.setdefault(key, Counter())
            if not cc.keep_value(kpi_key, v, bad):
                continue
            buckets.setdefault(key, []).append(v)
    cells = []
    # A cell whose every reading was impossible must still appear: it is the one
    # most in need of the operator's attention, and dropping it without a word is
    # the single outcome R-10 forbids.
    for key in sorted(set(buckets) | {k for k, c in implausible.items() if c}):
        vals = buckets.get(key) or []
        cv = cv_percent(vals)
        cells.append({
            "cell": dict(zip(group_by, key)), "kpi": kpi_key, "n": len(vals),
            "mean": cc.mean(vals), "median": cc.median(vals), "cv_percent": cv,
            "cv_not_computable_reason": cv_reason(vals, cv),
            "stdev": cc.stdev(vals),   # absolute spread, for the sample-size plan
            "unstable": (cv is not None and cv > cv_gate),
            "low_confidence": len(vals) < min_samples,
            "implausible_values": dict(sorted((implausible.get(key) or {}).items())),
        })
    return cells


# At M2 grid scale this table is (point x carrier x band x tier x profile) per KPI
# — ~290 rows each, which buried every other section in the rehearsal (D-117).
# Above the cap, STABLE rows are folded away and the omission is stated in full:
# unstable and not-computable rows are never dropped, and the CSV keeps everything.
DEFAULT_MAX_STABLE_ROWS = 25


def render_markdown(cells, kpi_key, cv_gate=None, max_stable_rows=_UNSET):
    # Both read live (D-204). `None` for max_stable_rows keeps its existing
    # meaning — no cap at all — which is why the default needs `_UNSET`.
    cv_gate = DEFAULT_CV_GATE if cv_gate is None else cv_gate
    if max_stable_rows is _UNSET:
        max_stable_rows = DEFAULT_MAX_STABLE_ROWS
    lines = [f"### 复测稳定性：`{kpi_key}`（CV% = 样本 stdev/mean；门 ≤{cc.fmt_num(cv_gate)}% 为稳定）", ""]
    if not cells:
        lines.append(f"_无 `{kpi_key}` 数据。_")
        return "\n".join(lines)
    # "stable" here means stable AND clean: a cell carrying impossible readings
    # is never a row to fold away, whatever its CV says about the rest.
    stable_ids = [id(c) for c in cells
                  if c["cv_percent"] is not None and not c["unstable"]
                  and not c.get("implausible_values")]
    omitted = 0
    if max_stable_rows is not None and len(stable_ids) > max_stable_rows:
        keep = set(stable_ids[:max_stable_rows])
        omitted = len(stable_ids) - max_stable_rows
        cells = [c for c in cells if id(c) not in set(stable_ids) or id(c) in keep]
    if any(c.get("implausible_values") for c in cells):
        lines += ["> ⚠ **本表含物理上不可能的读数**（标 `IMPLAUSIBLE_VALUE`）。这些读数"
                  "**已排除出该格的 n / 中位 / 均值 / CV**，仅计数。它们不是「测得很差」，"
                  "是**根本不是一次测量**——同一生产者写出过不可能的值，同批其他数值也不可信，"
                  "该格的稳定性结论请整体存疑，而不是只扣掉这几条。", ""]
    lines += ["| 单元 | n | 中位 | 均值 | CV% | 稳定? | 备注 |",
              "|---|---|---|---|---|---|---|"]
    for c in cells:
        cell_label = " · ".join(f"{k}={cc.md_cell(v)}" for k, v in c["cell"].items())
        if c["cv_percent"] is None:
            stable = "—"
        else:
            stable = "稳定" if not c["unstable"] else "✗超门"
        notes = []
        if c["cv_percent"] is None:
            # the two causes are not the same problem: n<2 says measure more,
            # mean<=0 says the numbers in this cell are not what they claim to be
            why = {"n<2": "n<2", "mean<=0": "均值≤0"}.get(
                c.get("cv_not_computable_reason"), "n<2/均值≤0")
            notes.append(f"CV 不可计算({why})")
        if c.get("implausible_values"):
            notes.append("**IMPLAUSIBLE_VALUE:" + "; ".join(
                f"{r}×{n}" for r, n in sorted(c["implausible_values"].items())) + "**")
        if c["low_confidence"]:
            notes.append("low_conf")
        note = "; ".join(notes) or "—"
        lines.append(
            f"| {cell_label} | {c['n']} | {cc.fmt_num(c['median'], 2)} | "
            f"{cc.fmt_num(c['mean'], 2)} | {cc.fmt_num(c['cv_percent'], 1)} | {stable} | {note} |")
    if omitted:
        lines += ["", f"> 另有 **{omitted}** 个**稳定**单元未列出（表内保留全部 ✗超门、"
                      f"CV 不可计算、含不可能读数的单元，以及前 {max_stable_rows} 个稳定单元）。"
                      "完整数据见 `<prefix>_stability.csv`。"]
    return "\n".join(lines)


# The grid proposal sized the campaign at n=5 assuming CV≈5%, which resolves a
# ~5% difference. Field spread is whatever it is, so the assumption has to be
# checked against the first day's data while there is still time to change the
# plan — the noise scale (D-144) only tells you afterwards that the delta drowned.
DEFAULT_TARGET_EFFECT_PCT = 5.0


def plan_cells(cells, target_pct=DEFAULT_TARGET_EFFECT_PCT):
    """Per cell: what the repeats actually resolve, and how many it would take to
    resolve `target_pct`% of the cell median. Unknown spread stays None all the
    way through — 'we cannot say' must not render as 'resolves everything'."""
    out = []
    for c in cells:
        sd, n, med = c["stdev"], c["n"], c["median"]
        mde = cc.min_detectable_effect(sd, n)
        target_abs = (abs(med) * target_pct / 100.0) if med is not None else None
        req = cc.required_n(sd, target_abs)
        row = dict(c)
        row["mde"] = mde
        row["mde_pct"] = (mde / abs(med) * 100.0) if (mde is not None and med) else None
        row["target_abs"] = target_abs
        row["required_n"] = req
        row["resolves_target"] = (req <= n) if req is not None else None
        # `required_n` is the break-even point: at exactly that n the target
        # difference clears the noise about half the time (52-58% measured). The
        # verdict line called that 足够 — a coin flip described as a guarantee —
        # so the number an operator should actually plan with travels beside it
        # now (D-201).
        req_p = cc.required_n_at_power(sd, target_abs)
        row["required_n_power"] = req_p
        row["mde_power"] = cc.detectable_effect_at_power(sd, n)
        row["resolves_at_power"] = (req_p <= n) if req_p is not None else None
        out.append(row)
    return out


def render_plan_markdown(rows, kpi_key, target_pct=DEFAULT_TARGET_EFFECT_PCT):
    lines = [f"### 采样量核算：`{kpi_key}`（目标：分辨 {cc.fmt_num(target_pct, 1)}% 的差异）", ""]
    if not rows:
        lines.append(f"_无 `{kpi_key}` 数据。_")
        return "\n".join(lines)
    lines += [
        "> **口径**：`可辨最小差异` = 以本单元实测离散度，两个同样大小的单元之间需要多大差异"
        "才会超出噪声尺度（√2·1.253·sd/√n）。它是**量级指示、不是显著性检验**（时延右偏）。"
        "离散度未知（n<2）的单元一律留 `—`，**不以 0 或当前 n 顶替**。",
        "",
        "> ⚠ **两个「需 n≥」不是一回事，规划采样量要看后一个**："
        f"`需 n≥(平)` 是让目标差异**正好等于**噪声尺度的复测数——在那个 n 上，"
        "一个**真实存在**的目标差异只有**约五成**会被判为「超出噪声」"
        "（实测 52%~58%，n=5~40，D-201）；此前本段把这个数称作「足够」，"
        "**那是把抛硬币说成了保证**。"
        f"`需 n≥({cc.fmt_num(cc.PLAN_POWER * 100, 0)}%)` 才是"
        f"「有 {cc.fmt_num(cc.PLAN_POWER * 100, 0)}% 把握看见它」所需的数，"
        f"约为前者的 {cc.fmt_num(cc.power_factor() ** 2, 2)} 倍"
        f"（判据是 |Δ|>噪声，故系数为 1+z={cc.fmt_num(cc.power_factor(), 3)}；"
        "**不是**双侧显著性检验的 z₁₋α/₂+z₁₋β，那会多要 7.85 倍的外场工时，"
        "去买一个本报告从不作出的承诺）。",
        "",
        "> ⚠ **两个「可辨最小差异」同理**：`(平)` 是**恰好等于**噪声尺度的差异——"
        "真有这么大的差异，也只有约五成会被判为「超出噪声」；"
        f"`({cc.fmt_num(cc.PLAN_POWER * 100, 0)}%)` 才是"
        f"「这一格有 {cc.fmt_num(cc.PLAN_POWER * 100, 0)}% 把握分辨出来」的差异，"
        f"约为前者的 {cc.fmt_num(cc.power_factor(), 3)} 倍。"
        f"右侧「达标?」按 {cc.fmt_num(cc.PLAN_POWER * 100, 0)}% 判——"
        "**此前本表只印 `(平)` 那一个数，判词却按八成给**，"
        "一列按五成报、一列按八成判，并排放在同一行（D-240）。",
        "",
        f"| 单元 | n | 中位 | CV% | 超门? | 可辨最小差异(平) | 占中位(平) | "
        f"可辨最小差异({cc.fmt_num(cc.PLAN_POWER * 100, 0)}%) | "
        f"达标?({cc.fmt_num(cc.PLAN_POWER * 100, 0)}%) | 需 n≥(平) | "
        f"需 n≥({cc.fmt_num(cc.PLAN_POWER * 100, 0)}%) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        cell_label = " · ".join(f"{k}={cc.md_cell(v)}" for k, v in r["cell"].items())
        # judged at the SAME criterion as the verdict below. Judging the column
        # at break-even and the verdict at power would put "达标" on a row the
        # conclusion calls short — one section, two answers (D-201).
        ok = ("—" if r["resolves_at_power"] is None
              else ("达标" if r["resolves_at_power"] else "✗不足"))
        gate = "**✗超门**" if r["unstable"] else ("—" if r["cv_percent"] is None else "达门")
        lines.append(
            f"| {cell_label} | {r['n']} | {cc.fmt_num(r['median'], 2)} | "
            f"{cc.fmt_num(r['cv_percent'], 1)} | {gate} | {cc.fmt_num(r['mde'], 2)} | "
            f"{cc.fmt_num(r['mde_pct'], 1)}% | {cc.fmt_num(r.get('mde_power'), 2)} | "
            f"{ok} | {cc.fmt_num(r['required_n'])} | "
            f"{cc.fmt_num(r.get('required_n_power'))} |")
    unstable = [r for r in rows if r["unstable"]]
    judged = [r for r in rows if r["resolves_at_power"] is not None]
    # The verdict is judged at the POWER criterion, not at break-even. Judging it
    # at break-even is what let the section say 足够 about a coin flip (D-201).
    short = [r for r in judged if not r["resolves_at_power"]]
    coin = [r for r in judged if r["resolves_at_power"] is False
            and r["resolves_target"] is True]
    unknown = len(rows) - len(judged)
    pw = cc.fmt_num(cc.PLAN_POWER * 100, 0)
    lines.append("")
    if not judged:
        lines.append(f"> **结论**：{len(rows)} 个单元离散度均不可估（n<2），"
                     "**无法核算采样量**——先补足复测再核算。")
    else:
        need = cc.median([r["required_n_power"] for r in short]) if short else None
        if not short:
            verdict = (f"> **结论**：{len(judged)} 个可核算单元在当前 n 下，"
                       f"都有 **≥{pw}% 的把握**看见 {cc.fmt_num(target_pct, 1)}% 的差异。")
        else:
            verdict = (f"> **结论**：{len(short)}/{len(judged)} 个单元在当前 n 下"
                       f"**没有 {pw}% 的把握**看见 {cc.fmt_num(target_pct, 1)}% 的差异"
                       f"；这些单元的建议复测数中位为 **n≥{cc.fmt_num(need)}**（每侧）。")
            if coin:
                verdict += (f" 其中 **{len(coin)} 个**单元的当前 n 恰好落在"
                            "「差异等于噪声尺度」附近——**那只有约五成把握**，"
                            "不要据此认为采样量已经够了。")
        if unknown:
            verdict += f" 另有 {unknown} 个单元离散度不可估，**未计入**。"
        lines.append(verdict)
    if unstable:
        # A prescription of "run more repeats" is the wrong remedy for a cell
        # whose measurement is not repeatable in the first place — the runbook
        # answer there is to find the cause and re-measure (D-170).
        lines.append("")
        lines.append(f"> ⚠ 其中 **{len(unstable)} 个单元 CV 已超门**（标 `✗超门`）。"
                     "对这些单元,`需 n≥` 只是把噪声摊薄的算术,**不解决它们本身不可重复**——"
                     "先查原因(设备/环境/场景本身不稳)再重采,不要照着这个数字硬加复测。")
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB repeatability/stability (CV) analysis")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--kpi", default="t1_ttft_ms")
    ap.add_argument("--cv-gate", type=float, default=DEFAULT_CV_GATE)
    ap.add_argument("--min-samples", type=int, default=cc.DEFAULT_MIN_SAMPLES)
    # The row cap exists because this section would otherwise dominate the
    # comprehensive report (D-117). Someone who ran THIS tool came to look at
    # stability, so the standalone default is uncapped (D-130).
    ap.add_argument("--max-stable-rows", type=int, default=0,
                    help="fold away all but N stable rows (0 = show everything; "
                         f"the comprehensive report uses {DEFAULT_MAX_STABLE_ROWS})")
    ap.add_argument("--plan", nargs="?", type=float, const=DEFAULT_TARGET_EFFECT_PCT,
                    default=None, metavar="PCT",
                    help="sample-size check instead of the CV table: what the "
                         "repeats resolve, and how many are needed to resolve "
                         f"PCT%% of the cell median (default {DEFAULT_TARGET_EFFECT_PCT})")
    args = ap.parse_args(argv)
    cc.force_utf8_stdout()

    recs, files = cc.load_records(args.inputs)
    cells = stability_cells(recs, args.kpi, cv_gate=args.cv_gate, min_samples=args.min_samples)
    if args.plan is not None:
        if args.plan <= 0:
            print("--plan 的目标差异须为正数（它是要分辨的差异占中位的百分比）", file=sys.stderr)
            return 2
        print(render_plan_markdown(plan_cells(cells, args.plan), args.kpi, args.plan))
    else:
        print(render_markdown(cells, args.kpi, args.cv_gate,
                              max_stable_rows=args.max_stable_rows or None))
    unstable = sum(1 for c in cells if c["unstable"])
    print(f"\n<!-- records={len(recs)} cells={len(cells)} unstable={unstable} -->", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
