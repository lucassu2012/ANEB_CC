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

# D-372 measured WHY s2 is noisy and answered it: the jitter is intrinsic to the
# scenario, not in the network. Same batch, same cells — TTFT CV 10.3% while RTT
# CV was 3.6%, and TTFT~RTT correlated 0.00. A CV computed on a scenario-side KPI
# therefore does NOT license 「加测网络样本」: more repeats thin a variance that
# does not live in the path. These two lists are the discriminant that ruling
# turned into a check, and the ONE place either side is named (§2.14).
SCENARIO_SIDE_KPIS = ("t1_ttft_ms", "t2_itl_p95_ms", "u2_tool_loop_p95_ms")
NETWORK_SIDE_KPIS = ("n1_rtt_p50_ms", "n2_jitter_ms")
# The marker, written once. markdown prints it as a 备注 prefix and the summary
# names it; the CSV encodes the same fact as a column of its own, because a CSV
# has no banner above it to explain a word (D-141/D-303/D-337).
SCENARIO_JITTER_MARK = "SCENARIO_INTRINSIC_JITTER"


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


def network_side_verdict(records, group_by=None, cv_gate=None,
                         min_samples=cc.DEFAULT_MIN_SAMPLES):
    """{cell key -> True | False | None}: is EVERY network-side KPI in this cell
    computable AND within the CV gate?

    True  = the path was steady here, so a scenario-side KPI that is not is the
            discriminant D-372 used.
    False = the network side is over the gate too — the noise is not specific to
            the scenario, and the ordinary 「先查测量装置」 reading (D-170) stands.
    None  = no computable network-side CV in this cell. 「判不了」 is not 「判否」
            (R-10), and the caller must not mark on it either way.
    """
    group_by = STAB_GROUP_BY if group_by is None else group_by
    per_cell = {}
    for k in NETWORK_SIDE_KPIS:
        # _annotate=False makes the recursion structurally impossible rather than
        # conditionally so. The first version relied on the two lists being
        # disjoint, and a perturbation putting one KPI on both blew the stack —
        # an invariant nothing enforced, holding up a recursion guard (D-378).
        for c in stability_cells(records, k, group_by, cv_gate, min_samples,
                                 _annotate=False):
            if c["cv_percent"] is None:
                continue
            key = tuple(c["cell"][f] for f in group_by)
            per_cell[key] = per_cell.get(key, True) and not c["unstable"]
    return per_cell


def annotate_scenario_jitter(cells, kpi_key, net):
    """Mark the cells whose CV is scenario-intrinsic, in place.

    `scenario_jitter_reason` exists for the same reason
    `cv_not_computable_reason` does next door: a bare False has three causes
    calling for three different actions, and the blank says none of them. The
    dangerous one is `no_network_cv` — without the discriminant this check
    cannot answer, and a reader filtering False would otherwise be told 「网络侧
    问题，去加样本」 about a cell nothing measured the network in.
    """
    live = kpi_key in SCENARIO_SIDE_KPIS
    for c in cells:
        if not (live and c["unstable"]):
            c["scenario_intrinsic_jitter"] = False
            c["scenario_jitter_reason"] = "not_applicable"
            continue
        key = tuple(c["cell"].values())
        v = net.get(key)
        c["scenario_intrinsic_jitter"] = v is True
        c["scenario_jitter_reason"] = {
            True: "", False: "network_side_unstable", None: "no_network_cv"}[v]
    return cells


def stability_cells(records, kpi_key, group_by=None,
                    cv_gate=None, min_samples=cc.DEFAULT_MIN_SAMPLES,
                    _annotate=True):
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
    # Annotated HERE, not at each call site: every surface (report section,
    # summary bullet, CSV, --plan) reads the same field off the same cells, so
    # none of them can forget it and none can compute it differently (§2.14).
    # No recursion risk — the network-side pass is only taken for a scenario-side
    # KPI, and no KPI is on both lists (a guard test pins that).
    if not _annotate:
        return cells
    net = (network_side_verdict(records, group_by, cv_gate, min_samples)
           if kpi_key in SCENARIO_SIDE_KPIS else {})
    return annotate_scenario_jitter(cells, kpi_key, net)


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
    # The summary states 「N/M 单元超 CV 门」 and until D-297 NEITHER number
    # appeared anywhere below it: this section renders rows, not counts, and M is
    # a sum across the KPI subsections. The reader was handed a ratio with no way
    # to reach either half of it. Counted BEFORE any truncation, so M is the
    # population the verdict was computed over rather than the rows that survived.
    total = len(cells)
    n_unstable = sum(1 for c in cells if c["unstable"])
    n_nocv = sum(1 for c in cells if c["cv_percent"] is None)
    lines += [f"> **本表共 {total} 个单元**：✗超门 {n_unstable}，"
              f"CV 不可计算 {n_nocv}，其余稳定。摘要的「N/M 单元超 CV 门」"
              "即各 KPI 分表这两个数各自相加。", ""]
    # The section-head banner half of the D-378 contract. Rendered for every
    # scenario-side KPI table whether or not anything was marked: a paragraph
    # that only appears when it fires never enters a golden, and its wording
    # then rots unwatched (D-318). It also names both KPI lists, which is what
    # makes retuning either one visible on the page rather than only in a flag.
    if kpi_key in SCENARIO_SIDE_KPIS:
        n_jit = sum(1 for c in cells if c.get("scenario_intrinsic_jitter"))
        blind = sum(1 for c in cells
                    if c.get("scenario_jitter_reason") == "no_network_cv")
        lines += [
            f"> **场景内生抖动判据**（承 D-372）：同格同 profile 下本 KPI 超 CV 门、"
            f"而网络侧（{'/'.join('`%s`' % k for k in NETWORK_SIDE_KPIS)}）**未**超门的"
            f"单元标 `{SCENARIO_JITTER_MARK}`（**场景内生抖动**）——D-372 实测同批 "
            "RTT 平稳而 TTFT 独抖、两者相关 0.00，故**这些单元的 `需 n≥` 不是加测网络样本的"
            f"理由**（加 run 只是把一个不在链路上的方差摊薄）。**本表 {n_jit} 个**。"
            + (f"另有 **{blind} 个**超门单元的格内**网络侧 CV 不可算**，故**未打此标**——"
               "那是「判不了」，**不是**「判否」。" if blind else ""),
            "",
        ]
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
        # Prefix, ahead of the older notes: this is the one that changes what the
        # reader should DO about the row. The Chinese gloss travels WITH the
        # marker because the HTML report is converted from this markdown (D-107),
        # so a separate HTML wording would be a second truth free to drift — the
        # surfaces differ in vocabulary where they have their own renderer
        # (the CSV column), not where one is derived from the other (D-337).
        if c.get("scenario_intrinsic_jitter"):
            notes.append(f"**{SCENARIO_JITTER_MARK}（场景内生抖动）**")
        elif c.get("scenario_jitter_reason") == "no_network_cv":
            notes.append("场景内生?**不可判**（格内无网络侧 CV）")
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

# Same reason the CV table has one (D-117): at grid scale this is one row per
# cell per KPI and it would bury every section under it. Rows that already
# resolve the target are folded away and the omission is stated in full;
# 达标 is the only kind ever folded — a cell that is short, over the CV gate,
# not computable or carrying impossible readings is exactly what the reader
# came for. The standalone CLI stays uncapped (D-130: whoever ran the tool
# came to look at this table).
DEFAULT_MAX_PLAN_ROWS = 25


def plan_cells(cells, target_pct=None):
    """Per cell: what the repeats actually resolve, and how many it would take to
    resolve `target_pct`% of the cell median. Unknown spread stays None all the
    way through — 'we cannot say' must not render as 'resolves everything'."""
    # read live (D-204/D-388): captured in the signature, setattr could not
    # reach it, so the perturbation guard never ran on a gate the report
    # now prints
    target_pct = DEFAULT_TARGET_EFFECT_PCT if target_pct is None else target_pct
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


def render_plan_markdown(rows, kpi_key, target_pct=None, max_ok_rows=_UNSET):
    target_pct = DEFAULT_TARGET_EFFECT_PCT if target_pct is None else target_pct
    if max_ok_rows is _UNSET:
        max_ok_rows = DEFAULT_MAX_PLAN_ROWS
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
    # Same fold as the CV table (D-117), and the same rule about WHICH rows may
    # be folded: only a cell that already resolves the target AND is inside the
    # CV gate AND carries no impossible readings. Everything a reader came for —
    # short, over the gate, not computable, marked — stays on the page, and the
    # omission is stated in full below rather than silently applied.
    ok_ids = [id(r) for r in rows
              if r["resolves_at_power"] is True and not r["unstable"]
              and not r.get("implausible_values")
              and not r.get("scenario_intrinsic_jitter")]
    omitted = 0
    if max_ok_rows is not None and len(ok_ids) > max_ok_rows:
        keep = set(ok_ids[:max_ok_rows])
        omitted = len(ok_ids) - max_ok_rows
        shown_rows = [r for r in rows if id(r) not in set(ok_ids) or id(r) in keep]
    else:
        shown_rows = rows
    for r in shown_rows:
        cell_label = " · ".join(f"{k}={cc.md_cell(v)}" for k, v in r["cell"].items())
        # judged at the SAME criterion as the verdict below. Judging the column
        # at break-even and the verdict at power would put "达标" on a row the
        # conclusion calls short — one section, two answers (D-201).
        ok = ("—" if r["resolves_at_power"] is None
              else ("达标" if r["resolves_at_power"] else "✗不足"))
        gate = "**✗超门**" if r["unstable"] else ("—" if r["cv_percent"] is None else "达门")
        # This table has no 备注 column, so the marker rides in the gate cell —
        # the row a reader is about to act on is the row that has to carry it.
        if r.get("scenario_intrinsic_jitter"):
            gate += "(场景内生)"
        lines.append(
            f"| {cell_label} | {r['n']} | {cc.fmt_num(r['median'], 2)} | "
            f"{cc.fmt_num(r['cv_percent'], 1)} | {gate} | {cc.fmt_num(r['mde'], 2)} | "
            f"{cc.fmt_num(r['mde_pct'], 1)}% | {cc.fmt_num(r.get('mde_power'), 2)} | "
            f"{ok} | {cc.fmt_num(r['required_n'])} | "
            f"{cc.fmt_num(r.get('required_n_power'))} |")
    if omitted:
        lines += ["", f"> 另有 **{omitted}** 个**已达标**单元未列出（表内保留全部 ✗不足、"
                      "✗超门、不可核算、场景内生抖动的单元，以及前 "
                      f"{max_ok_rows} 个达标单元）。完整数据见 `<prefix>_plan.csv`。"]
    # Counted over `rows`, never over what survived the fold: the conclusion is
    # about the population the verdict was computed on, not the rows that fit on
    # the page (the reason D-297 gave the CV table its own count line).
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
        # D-378 split the CRITERION; D-301's lesson is that the conclusion
        # sentence has to move with it, or the section keeps reporting the old
        # pooled number under a table that no longer means that. The measured
        # case: 「43/96 个单元…建议复测数中位 n≥78」 on t1_ttft_ms, where the 78 was
        # driven by the s2 cells — the very number D-372 proved cannot be read as
        # a network sample size, pooled into a network sampling recommendation.
        jitter = [r for r in short if r.get("scenario_intrinsic_jitter")]
        net_short = [r for r in short if not r.get("scenario_intrinsic_jitter")]
        need = cc.median([r["required_n_power"] for r in net_short]) if net_short else None
        if not short:
            verdict = (f"> **结论**：{len(judged)} 个可核算单元在当前 n 下，"
                       f"都有 **≥{pw}% 的把握**看见 {cc.fmt_num(target_pct, 1)}% 的差异。")
        else:
            verdict = (f"> **结论**：{len(short)}/{len(judged)} 个单元在当前 n 下"
                       f"**没有 {pw}% 的把握**看见 {cc.fmt_num(target_pct, 1)}% 的差异")
            if not net_short:
                # Saying nothing here would let a reader carry over the pooled
                # median they saw last time; 「没有可汇的」 is itself the finding.
                verdict += (f"；但这 {len(short)} 个**全部**标 "
                            f"`{SCENARIO_JITTER_MARK}`，**没有一个可用来推网络采样量**"
                            "——本段因此**不给**建议复测数中位。")
            else:
                verdict += (f"；这些单元的建议复测数中位为 **n≥{cc.fmt_num(need)}**（每侧）"
                            + (f"——**该中位只汇网络侧的 {len(net_short)} 个**，"
                               f"已排除 {len(jitter)} 个 `{SCENARIO_JITTER_MARK}` 单元"
                               if jitter else "") + "。")
            if coin:
                verdict += (f" 其中 **{len(coin)} 个**单元的当前 n 恰好落在"
                            "「差异等于噪声尺度」附近——**那只有约五成把握**，"
                            "不要据此认为采样量已经够了。")
        if unknown:
            verdict += f" 另有 {unknown} 个单元离散度不可估，**未计入**。"
        lines.append(verdict)
        # The s2 half gets its OWN sentence rather than a clause: pooling it was
        # the defect, and a parenthesis inside the network sentence would read as
        # a footnote to a number it must not contribute to.
        if jitter:
            j_need = cc.median([r["required_n_power"] for r in jitter])
            lines.append("")
            lines.append(
                f"> ⚠ **另有 {len(jitter)} 个单元标 `{SCENARIO_JITTER_MARK}`**"
                f"（其 `需 n≥` 中位 **{cc.fmt_num(j_need)}**，**单列，不并入上句**）。"
                "它们超门的那部分方差**不在链路上**（D-372：同批 RTT 平稳、TTFT~RTT 相关 0.00），"
                "**照这个数加外场 run 买不到网络精度**。要降它只有两条路："
                "改**场景/服务端侧**的测量装置，或对该 KPI **放宽 MDE 目标**并写明理由。")
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
        # uncapped standalone, same reason the CV table is (D-130): whoever ran
        # THIS tool came to look at this table
        print(render_plan_markdown(plan_cells(cells, args.plan), args.kpi, args.plan,
                                   max_ok_rows=None))
    else:
        print(render_markdown(cells, args.kpi, args.cv_gate,
                              max_stable_rows=args.max_stable_rows or None))
    unstable = sum(1 for c in cells if c["unstable"])
    print(f"\n<!-- records={len(recs)} cells={len(cells)} unstable={unstable} -->", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
