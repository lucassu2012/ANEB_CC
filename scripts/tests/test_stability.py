# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/stability.py (coefficient-of-variation gate)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import campaign_common
import stability
import campaign_report as rpt
from synth import kpi_scenario_records


def test_cv_known_values():
    assert stability.cv_percent([10, 10, 10]) == 0.0
    # mean 10, sample stdev 2 -> CV 20%
    cv = stability.cv_percent([8, 10, 12])
    assert abs(cv - 20.0) < 1e-9


def test_cv_below_two_samples_is_none():
    assert stability.cv_percent([5]) is None
    assert stability.cv_percent([]) is None


def _cell(i, *, unstable=False, cv=3.0):
    return {"cell": {"point_id": f"P{i:02d}", "carrier": "cmcc", "time_band": "busy",
                     "tier": "metro", "profile_id": "s1_chat"},
            "n": 5, "median": 100.0, "mean": 100.0, "cv_percent": cv,
            "unstable": unstable, "low_confidence": False, "kpi": "t1_ttft_ms"}


def test_stable_row_cap_declares_what_it_omitted():
    # ⚠ SOLE targeted guard on handover §2.4 "declare what was truncated"
    #   (D-186's mutation map). Deleting or weakening this leaves that red line
    #   held by nothing. Replacing it? Put the replacement in first.
    """No silent truncation (D-117): the omission is stated, with a pointer to
    the complete data."""
    cells = [_cell(i) for i in range(40)]
    md = stability.render_markdown(cells, "t1_ttft_ms", max_stable_rows=25)
    assert md.count("point_id=P") == 25
    assert "另有 **15**" in md
    assert "_stability.csv" in md


def test_cap_never_drops_unstable_or_not_computable_rows():
    """The signal rows survive any cap — only stable ones fold away."""
    cells = ([_cell(i) for i in range(30)]
             + [_cell(90, unstable=True, cv=42.0), _cell(91, cv=None)])
    md = stability.render_markdown(cells, "t1_ttft_ms", max_stable_rows=5)
    assert "point_id=P90" in md and "point_id=P91" in md
    assert md.count("point_id=P") == 7   # 5 stable + unstable + not-computable


def test_cap_can_be_disabled_for_a_focused_look():
    """Someone who ran the standalone tool came to look at stability; the cap
    that keeps this section from swamping the report must not fold rows away
    from them (D-130)."""
    cells = [_cell(i) for i in range(40)]
    md = stability.render_markdown(cells, "t1_ttft_ms", max_stable_rows=None)
    assert md.count("point_id=P") == 40
    assert "另有" not in md


def test_no_cap_note_when_under_the_limit():
    md = stability.render_markdown([_cell(i) for i in range(3)], "t1_ttft_ms")
    assert "另有" not in md


def test_cv_mean_zero_is_none():
    assert stability.cv_percent([2, -2]) is None      # mean 0 -> undefined, not 0


def test_stable_vs_unstable_flag():
    stable = kpi_scenario_records(5, kpi={"t1_ttft_ms": 100})          # identical -> CV 0
    cells = stability.stability_cells(stable, "t1_ttft_ms", cv_gate=10.0)
    assert cells[0]["cv_percent"] == 0.0
    assert cells[0]["unstable"] is False
    # spread values 80,120,80,120,100 -> mean 100, CV ~19% > 10
    recs = (kpi_scenario_records(1, kpi={"t1_ttft_ms": 80})
            + kpi_scenario_records(1, kpi={"t1_ttft_ms": 120})
            + kpi_scenario_records(1, kpi={"t1_ttft_ms": 80})
            + kpi_scenario_records(1, kpi={"t1_ttft_ms": 120})
            + kpi_scenario_records(1, kpi={"t1_ttft_ms": 100}))
    c = stability.stability_cells(recs, "t1_ttft_ms", cv_gate=10.0)[0]
    assert c["cv_percent"] > 10.0
    assert c["unstable"] is True


def test_low_confidence_flag():
    recs = kpi_scenario_records(2, kpi={"t1_ttft_ms": 100})  # n=2 < 5
    c = stability.stability_cells(recs, "t1_ttft_ms")[0]
    assert c["low_confidence"] is True


def _campaign_kpis(values, campaign_id):
    return [r for v in values
            for r in kpi_scenario_records(1, kpi={"t1_ttft_ms": v}, campaign_id=campaign_id)]


def test_campaigns_are_not_pooled_into_repeatability():
    """Two campaigns are two conditions. Pooling them makes CV measure the
    optimisation instead of the measurement — and the runbook then sends the
    operator back to resample a cell that was fine (D-145)."""
    recs = (_campaign_kpis([398, 400, 402, 399, 401], "base")
            + _campaign_kpis([598, 600, 602, 599, 601], "opt"))
    cells = stability.stability_cells(recs, "t1_ttft_ms")
    assert len(cells) == 2
    by = {c["cell"]["campaign_id"]: c for c in cells}
    assert by["base"]["median"] == 400 and by["opt"]["median"] == 600
    for c in cells:
        assert c["n"] == 5
        assert c["cv_percent"] < 1.0
        assert c["unstable"] is False


def test_stability_csv_distinguishes_campaigns():
    """CSV is where analysts compute, and it has no banners: without campaign_id
    the two campaigns emit rows identical in every other column (D-141/145)."""
    import csv as csvmod
    import tempfile
    from synth import contractify
    recs = [contractify(r) for r in
            (_campaign_kpis([398, 400, 402, 399, 401], "base")
             + _campaign_kpis([598, 600, 602, 599, 601], "opt"))]
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "camp")
        rpt.write_csv_tables(recs, prefix)
        with open(prefix + "_stability.csv", encoding="utf-8-sig") as f:
            rows = [r for r in csvmod.DictReader(f) if r["kpi"] == "t1_ttft_ms"]
    assert {r["campaign_id"] for r in rows} == {"base", "opt"}
    assert {float(r["median"]) for r in rows} == {400.0, 600.0}
    assert all(int(r["n"]) == 5 for r in rows)


def test_required_n_and_detectable_effect_are_consistent():
    """The n the planner asks for must actually bring the resolvable difference
    down to the target — otherwise the advice is decorative."""
    import campaign_common as cc
    sd, target = 50.0, 10.0
    n = cc.required_n(sd, target)
    assert cc.min_detectable_effect(sd, n) <= target
    assert cc.min_detectable_effect(sd, n - 1) > target      # and not more than needed
    # tighter targets cost more samples, quadratically
    assert cc.required_n(sd, target / 2) >= 4 * n - 2


def test_plan_leaves_unknown_spread_unknown():
    """n=1: spread unknown, so neither what it resolves nor what it would take
    can be stated — None all the way through, never 0 and never the current n."""
    import campaign_common as cc
    assert cc.min_detectable_effect(None, 5) is None
    assert cc.required_n(None, 10) is None
    assert cc.required_n(5.0, 0) is None                     # non-positive target
    rows = stability.plan_cells(stability.stability_cells(
        kpi_scenario_records(1, kpi={"t1_ttft_ms": 100}), "t1_ttft_ms"))
    assert rows[0]["mde"] is None
    assert rows[0]["required_n"] is None
    assert rows[0]["resolves_target"] is None
    md = stability.render_plan_markdown(rows, "t1_ttft_ms")
    assert "无法核算采样量" in md


def test_plan_flags_cells_that_cannot_resolve_the_target():
    recs = _campaign_kpis([100, 130, 70, 115, 85], "base")   # CV ~24%, n=5
    rows = stability.plan_cells(stability.stability_cells(recs, "t1_ttft_ms"), 5.0)
    assert rows[0]["resolves_target"] is False
    assert rows[0]["required_n"] > 5
    md = stability.render_plan_markdown(rows, "t1_ttft_ms", 5.0)
    assert "1/1 个单元在当前 n 下**没有 80% 的把握**" in md
    assert "不是显著性检验" in md                            # the caveat travels with it


def test_plan_separates_break_even_from_actually_seeing_it():
    """`required_n` is where the target difference EQUALS the noise scale, i.e.
    where it is seen about half the time (52-58% measured). The section used to
    call that 足够 — a coin flip described as a guarantee (D-201).

    The number to plan a campaign with is 3.39x larger, and both must be on the
    page or the operator cannot tell which one they are reading.
    """
    import campaign_common as cc
    sd, target = 5.0, 5.0
    assert cc.required_n(sd, target) == 4
    assert cc.required_n_at_power(sd, target) == 11
    # the factor comes from THIS report's criterion (|delta| > noise, one noise
    # unit), not from a two-sided significance test — that would demand 7.85x
    assert abs(cc.power_factor() - 1.8416) < 0.001
    assert abs(cc.power_factor() ** 2 - 3.39) < 0.01
    rows = stability.plan_cells(
        stability.stability_cells(_campaign_kpis([100, 130, 70, 115, 85], "base"),
                                  "t1_ttft_ms"), 5.0)
    assert rows[0]["required_n_power"] > rows[0]["required_n"]
    md = stability.render_plan_markdown(rows, "t1_ttft_ms", 5.0)
    assert "需 n≥(平)" in md and "需 n≥(80%)" in md
    assert "把抛硬币说成了保证" in md
    assert "当前复测数足够" not in md          # the retired claim, gone


def test_report_includes_stability_section():
    recs = kpi_scenario_records(5, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "excellent"}, aqs=90)
    md = rpt.build_report_markdown(recs)
    assert "复测稳定性" in md


def test_plan_states_the_good_news_positively():
    """Zero failures rendered as "0/N cannot resolve" buries the answer in a
    negation — the operator is reading this to decide whether to change the
    collection plan (D-150)."""
    recs = _campaign_kpis([100, 101, 99, 100, 100], "base")   # very tight
    rows = stability.plan_cells(stability.stability_cells(recs, "t1_ttft_ms"), 5.0)
    assert all(r["resolves_target"] for r in rows)
    md = stability.render_plan_markdown(rows, "t1_ttft_ms", 5.0)
    # the good news, stated positively AND at the caliber it actually holds at —
    # "足够" used to say this about a 50-50 chance (D-150 intent, D-201 caliber)
    assert "都有 **≥80% 的把握**看见" in md
    assert "没有 80% 的把握" not in md
    assert "当前复测数足够" not in md


def test_plan_separates_cells_that_are_not_repeatable():
    """A cell whose CV is over the gate gets a repeat-count prescription, but
    more repeats is the wrong remedy for a measurement that is not repeatable —
    the runbook answer there is to find the cause and re-measure (D-170)."""
    stable = _campaign_kpis([100, 101, 99, 100, 100], "base")
    unstable = [r for v in (100, 130, 70, 115, 85)
                for r in kpi_scenario_records(1, kpi={"t1_ttft_ms": v},
                                              point="P-UNSTABLE", campaign_id="base")]
    rows = stability.plan_cells(
        stability.stability_cells(stable + unstable, "t1_ttft_ms"), 5.0)
    by = {r["cell"]["point_id"]: r for r in rows}
    assert by["P-UNSTABLE"]["unstable"] is True
    assert by["P-UNSTABLE"]["required_n"] > 50      # the arithmetic still runs
    md = stability.render_plan_markdown(rows, "t1_ttft_ms", 5.0)
    assert "超门?" in md                            # the column exists
    assert "**✗超门**" in md
    assert "不解决它们本身不可重复" in md            # and says why n is not the fix


def test_every_declared_kpi_is_ratio_scale_so_a_percentage_target_means_something():
    """The plan states its target as a percentage of the median, and `--kpi`
    takes any name. That only means anything on a ratio scale — a quantity
    where zero is zero and the ratio of two values carries information.

    Every KPI the contract declares is one (times, rates, fractions, scores;
    all bounded below by 0), so the premise holds — but it held by luck until
    something checked it. An interval-scale KPI such as rsrp_dbm would pass
    through unnoticed and make 「占中位 x%」 a number with no physical meaning:
    5% of −105 dBm is 5.25 dB, an enormous signal difference dressed up as a
    small target (D-225).
    """
    import campaign_common as cc

    ranges = cc.VALUE_RANGES
    assert len(ranges) >= 10, f"only {len(ranges)} declared ranges — did the map move?"
    for kpi in stability.DEFAULT_STABILITY_KPIS:
        assert kpi in ranges, f"{kpi} is planned against but has no declared range"

    interval_scale = {k: v for k, v in ranges.items() if v[0] is None or v[0] < 0}
    assert not interval_scale, (
        "these KPIs admit values at or below zero, so the plan section's "
        f"percentage-of-median target is not meaningful for them: {interval_scale} "
        "— give the plan an absolute-effect target before declaring such a KPI")


def test_the_two_detectable_differences_are_one_multiplication_apart():
    """D-201 put both 需 n≥ figures on the page because one of them is a coin
    flip. 可辨最小差异 was left at break-even while the 达标? beside it is judged
    at 80% power — one row reporting at half the time and judging at four in
    five. The power figure was already there: plan_cells wrote `mde_power` and
    nothing ever read it, which is how a switch-off audit found it (D-240).

    Printing it is half the fix. The other half is this: (80%) = (平) × (1+z) is
    an arithmetic the reader can do on the row, so the two columns cannot drift.
    """
    import campaign_common as cc

    rows = stability.plan_cells(
        stability.stability_cells(_campaign_kpis([100, 130, 70, 115, 85], "base"),
                                  "t1_ttft_ms"), 5.0)
    md = stability.render_plan_markdown(rows, "t1_ttft_ms", 5.0)
    table = [l for l in md.splitlines() if l.startswith("| ")]
    header = [c.strip() for c in table[0].strip().strip("|").split("|")]

    pw = cc.fmt_num(cc.PLAN_POWER * 100, 0)
    flat_col, power_col = "可辨最小差异(平)", f"可辨最小差异({pw}%)"
    # membership before indexing: .index() would raise ValueError, and a guard
    # that crashes says nothing about what went wrong (D-235)
    for name in (flat_col, power_col):
        assert name in header, (
            f"no 「{name}」 column — the row no longer shows both figures\n"
            f"  header: {header}")
    i_flat, i_power = header.index(flat_col), header.index(power_col)

    checked = 0
    # past the header only: the |---| rule starts "|-", not "| ", so it never
    # entered `table` — slicing [2:] here quietly skipped the single data row and
    # the floor below is what caught it
    for line in table[1:]:
        if set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        flat, powered = cells[i_flat], cells[i_power]
        if flat == "—" or powered == "—":
            continue                             # spread unknown, both stay blank
        checked += 1
        want = float(flat) * cc.power_factor()
        # each column rounds to 2 digits, so allow both roundings plus the factor
        assert abs(float(powered) - want) <= 0.02, (
            f"the row prints {flat} and {powered}: {powered} is not {flat} × "
            f"{cc.fmt_num(cc.power_factor(), 3)} — the reader multiplying one "
            "column by the stated factor does not arrive at the other\n"
            f"  {line[:150]}")

    assert checked >= 1, (
        "no row printed both figures — this fixture resolves nothing, so the "
        "relation above was never actually evaluated")


# ---------------------------------------------------------------- D-382
#
# s2 jitter is intrinsic to the scenario, not in the network (D-372: same batch,
# TTFT CV 10.3% while RTT CV was 3.6%, TTFT~RTT correlation 0.00). A CV over the
# gate on a scenario-side KPI therefore does not license 「加测网络样本」 — more
# field runs thin a variance that does not live in the path.

def _jitter_corpus(ttft, rtt, *, point="P1", profile="s2_coding_agent"):
    """One cell whose t1 and n1 readings ride the same scenarios, so both land
    in the same stability cell. `rtt=None` leaves the network side unmeasured."""
    from synth import make_record
    recs = []
    for i, t in enumerate(ttft):
        kpi = {"t1_ttft_ms": t}
        if rtt is not None:
            kpi["n1_rtt_p50_ms"] = rtt[i]
        recs.append(make_record(
            campaign={"campaign_id": "base", "tier": "metro", "point_id": point,
                      "carrier": "cmcc", "time_band": "busy"},
            aqs=88, scenarios=[(profile, kpi)]))
    return recs


STEADY_NET = [20.0, 20.1, 19.9, 20.05, 20.0]
JUMPY_TTFT = [400.0, 520.0, 360.0, 480.0, 430.0]


def test_scenario_side_jitter_is_marked_only_when_the_network_side_is_steady():
    """The discriminant, both directions. A guard that fires on the wrong corpus
    is worse than none: the same over-gate TTFT must NOT be called scenario-
    intrinsic when the network side is over the gate too (D-382)."""
    cells = stability.stability_cells(_jitter_corpus(JUMPY_TTFT, STEADY_NET),
                                      "t1_ttft_ms")
    assert len(cells) == 1, cells
    c = cells[0]
    assert c["unstable"] is True, c
    assert c["scenario_intrinsic_jitter"] is True, c
    assert c["scenario_jitter_reason"] == "", c

    jumpy_net = [20.0, 27.0, 15.0, 25.0, 18.0]
    c2 = stability.stability_cells(_jitter_corpus(JUMPY_TTFT, jumpy_net),
                                   "t1_ttft_ms")[0]
    assert c2["unstable"] is True, c2
    assert c2["scenario_intrinsic_jitter"] is False, c2
    assert c2["scenario_jitter_reason"] == "network_side_unstable", c2

    calm = stability.stability_cells(
        _jitter_corpus([400.0, 401.0, 399.0, 400.5, 400.0], STEADY_NET),
        "t1_ttft_ms")[0]
    assert calm["unstable"] is False and calm["scenario_intrinsic_jitter"] is False
    assert calm["scenario_jitter_reason"] == "not_applicable", calm


def test_no_network_reading_is_cannot_tell_not_a_denial():
    """R-10 on the branch that matters most: without the discriminant this check
    cannot answer. A bare False would send the reader to add field runs against
    a cell nothing measured the network in."""
    c = stability.stability_cells(_jitter_corpus(JUMPY_TTFT, None), "t1_ttft_ms")[0]
    assert c["unstable"] is True, c
    assert c["scenario_intrinsic_jitter"] is False, c
    assert c["scenario_jitter_reason"] == "no_network_cv", c
    md = stability.render_markdown([c], "t1_ttft_ms")
    assert "不可判" in md and "判不了" in md, md
    rows = [ln for ln in md.splitlines() if ln.startswith("| campaign_id=")]
    assert rows and all(stability.SCENARIO_JITTER_MARK not in ln for ln in rows), rows


def test_the_marker_reaches_markdown_and_the_banner_states_the_criterion():
    """§2.6: a premise that only appears inside a 备注 cell is a premise most
    readers never see. The banner renders on every scenario-side table, marked or
    not — a paragraph that appears only when it fires never enters a golden and
    its wording rots unwatched (D-318)."""
    cells = stability.stability_cells(_jitter_corpus(JUMPY_TTFT, STEADY_NET),
                                      "t1_ttft_ms")
    md = stability.render_markdown(cells, "t1_ttft_ms")
    assert "场景内生抖动判据" in md, md
    assert stability.SCENARIO_JITTER_MARK in md, md
    # the Chinese gloss travels with the marker: the HTML report is converted
    # from this markdown, so this is also the HTML surface (D-107/D-337)
    assert "场景内生抖动" in md, md
    assert "不是加测网络样本的理由" in md, md
    assert "`n1_rtt_p50_ms`" in md, "the banner must name the corroborating KPIs"
    net_md = stability.render_markdown(
        stability.stability_cells(_jitter_corpus(JUMPY_TTFT, STEADY_NET),
                                  "n1_rtt_p50_ms"), "n1_rtt_p50_ms")
    assert "场景内生抖动判据" not in net_md, net_md


def test_the_plan_conclusion_pools_only_the_network_side():
    """B-2 / D-301: when the criterion changes, the conclusion sentence has to
    change with it. Measured shape: 「43/96 个单元…建议复测数中位 n≥78」 where the 78
    was driven by the s2 cells — the number D-372 proved cannot be read as a
    network sample size, pooled into a network sampling recommendation."""
    import campaign_common as cc_
    mild = [400.0, 424.0, 376.0, 416.0, 400.0]
    recs = (_jitter_corpus(JUMPY_TTFT, STEADY_NET, point="P-jitter")
            + _jitter_corpus(mild, [20.0, 23.0, 17.0, 22.0, 18.0], point="P-net"))
    rows = stability.plan_cells(stability.stability_cells(recs, "t1_ttft_ms"))
    md = stability.render_plan_markdown(rows, "t1_ttft_ms")

    marked = [r for r in rows if r.get("scenario_intrinsic_jitter")]
    assert [r["cell"]["point_id"] for r in marked] == ["P-jitter"], [
        (r["cell"]["point_id"], r.get("scenario_intrinsic_jitter")) for r in rows]

    net_short = [r for r in rows if not r.get("scenario_intrinsic_jitter")
                 and r["resolves_at_power"] is False]
    assert net_short, "fixture must leave a network-side cell short, or this proves nothing"
    need = cc_.median([r["required_n_power"] for r in net_short])
    assert ("n≥**%s**" % cc_.fmt_num(need)) in md.replace("**n≥", "n≥**"), md
    assert "该中位只汇网络侧的" in md, md

    assert stability.SCENARIO_JITTER_MARK in md, md
    assert "单列，不并入上句" in md, md
    assert "买不到网络精度" in md, md
    assert "(场景内生)" in md, "the plan table has no 备注 column - the row must carry it"


def test_a_plan_whose_every_short_cell_is_scenario_intrinsic_refuses_a_median():
    """「没有可汇的」 is itself the finding. Saying nothing would let a reader carry
    over the pooled median they saw last time (§2.4, D-150 恒出行)."""
    rows = stability.plan_cells(
        stability.stability_cells(_jitter_corpus(JUMPY_TTFT, STEADY_NET), "t1_ttft_ms"))
    md = stability.render_plan_markdown(rows, "t1_ttft_ms")
    assert "没有一个可用来推网络采样量" in md, md
    assert "不给**建议复测数中位" in md, md


def test_the_two_kpi_sides_are_disjoint():
    """The two lists are a discriminant: a KPI on both sides would be asked to
    corroborate itself, and every over-gate cell on it would silently read
    network_side_unstable. The recursion is structurally impossible either way
    (_annotate=False), so this pins the MEANING, not the stack (D-382)."""
    both = set(stability.SCENARIO_SIDE_KPIS) & set(stability.NETWORK_SIDE_KPIS)
    assert not both, both


def test_the_marked_ROW_carries_the_marker_not_just_the_banner():
    """Found by mutation audit, not by reasoning: deleting the 备注-column marker
    left every assertion green, because the section BANNER also spells the marker
    out and a whole-page `in md` matched there. A guard whose match lands on the
    wrong surface is a guard that says nothing (§2.14 / the D-319 lesson about
    what a coverage key compares)."""
    cells = stability.stability_cells(_jitter_corpus(JUMPY_TTFT, STEADY_NET),
                                      "t1_ttft_ms")
    md = stability.render_markdown(cells, "t1_ttft_ms")
    rows = [ln for ln in md.splitlines() if ln.startswith("| campaign_id=")]
    assert len(rows) == 1, rows
    assert stability.SCENARIO_JITTER_MARK in rows[0], (
        "the marker is on the banner but not on the row a reader acts on")
    assert "场景内生抖动" in rows[0], rows[0]


def test_the_marker_reaches_the_csv_with_its_reason():
    """CSV is the surface with no banner above it (§2.6/D-141). Exporting
    `unstable=True` with nothing beside it to say the variance is not in the path
    puts two surfaces in open disagreement — and the reason column is what keeps
    `no_network_cv` from reading as 「查过了，是网络问题」 (D-382)."""
    import csv as csvmod
    import os
    import tempfile
    recs = (_jitter_corpus(JUMPY_TTFT, STEADY_NET, point="P-jitter")
            + _jitter_corpus(JUMPY_TTFT, None, point="P-blind"))
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "camp")
        rpt.write_csv_tables(recs, prefix)
        with open(prefix + "_stability.csv", encoding="utf-8-sig") as f:
            rows = [r for r in csvmod.DictReader(f) if r["kpi"] == "t1_ttft_ms"]
    by_point = {r["point_id"]: r for r in rows}
    assert set(by_point) == {"P-jitter", "P-blind"}, sorted(by_point)
    assert by_point["P-jitter"]["scenario_intrinsic_jitter"] == "True", by_point
    assert by_point["P-jitter"]["scenario_jitter_reason"] == "", by_point
    assert by_point["P-blind"]["scenario_intrinsic_jitter"] == "False", by_point
    assert by_point["P-blind"]["scenario_jitter_reason"] == "no_network_cv", by_point


def test_the_summary_bullet_carries_the_scenario_intrinsic_count():
    """B-3: the summary is the paragraph decision-makers read closely, and
    「N/M 单元超 CV 门」 pooled two kinds of noise into one count — the reader's next
    action (go add field runs) is right for one kind and wasted on the other."""
    recs = _jitter_corpus(JUMPY_TTFT, STEADY_NET, point="P-jitter")
    summary = rpt.render_summary_markdown(recs)
    assert "复测不稳定" in summary, summary
    assert "其中 1 个属场景内生抖动" in summary, summary
    assert "不作为加测网络样本的理由" in summary, summary
    assert stability.SCENARIO_JITTER_MARK in summary, summary

    # ...and a corpus with no such cell must not carry the clause: a note that
    # fires on clean corpora trains people to ignore it (D-134).
    calm = _jitter_corpus([400.0, 401.0, 399.0, 400.5, 400.0], STEADY_NET)
    assert "场景内生抖动" not in rpt.render_summary_markdown(calm)


# ---------------------------------------------------------------- D-388
#
# GUARD_DIFF A-1: the number that decided the campaign's own n lived ONLY in
# `stability.py --plan` stdout — a command someone had to know to type. All
# three report surfaces carried none of it.

def test_the_sample_size_table_is_in_the_report_on_all_three_surfaces():
    """md + HTML + CSV. Counted per surface, not per module: per-module counting
    is exactly what hides 「两张表只导一张」 (D-303)."""
    import csv as csvmod
    import os
    import tempfile
    recs = _jitter_corpus(JUMPY_TTFT, STEADY_NET, point="P-jitter")
    md = rpt.build_report_markdown(recs)
    assert "## 采样量核算" in md, md[:2000]
    assert "需 n≥(80%)" in md, "the column that decides n is what A-1 was about"
    html = rpt.build_report_html(recs, "2026-01-01 00:00:00")
    assert "采样量核算" in html, "the md-only section must reach the HTML page"
    assert "需 n≥(80%)" in html, html[:400]

    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "camp")
        paths = rpt.write_csv_tables(recs, prefix)
        assert any(p.endswith("_plan.csv") for p in paths), [
            os.path.basename(p) for p in paths]
        with open(prefix + "_plan.csv", encoding="utf-8-sig") as f:
            rows = list(csvmod.DictReader(f))
    assert rows, "the plan CSV came out empty"
    assert "required_n_at_power" in rows[0], sorted(rows[0])
    # the CSV is where the folded rows live, so it must NOT be capped
    assert len(rows) >= len([r for r in rows]), rows
    got = {r["kpi"] for r in rows}
    assert got == set(stability.DEFAULT_STABILITY_KPIS) & got, got


def test_the_report_copy_of_the_plan_table_declares_what_it_folded():
    """No silent truncation (D-117/D-297): the count line is over the whole
    population and the omission is stated with a pointer to the full data."""
    rows = []
    for i in range(40):
        rows.append({"cell": {"campaign_id": "base", "point_id": "P%02d" % i,
                              "carrier": "cmcc", "time_band": "busy",
                              "tier": "metro", "profile_id": "s1_chat"},
                     "kpi": "t1_ttft_ms", "n": 5, "median": 100.0, "mean": 100.0,
                     "cv_percent": 1.0, "unstable": False, "low_confidence": False,
                     "implausible_values": {}, "stdev": 0.5,
                     "mde": 0.4, "mde_pct": 0.4, "mde_power": 0.7,
                     "target_abs": 5.0, "required_n": 1, "required_n_power": 2,
                     "resolves_target": True, "resolves_at_power": True,
                     "scenario_intrinsic_jitter": False,
                     "scenario_jitter_reason": "not_applicable"})
    capped = stability.render_plan_markdown(rows, "t1_ttft_ms", max_ok_rows=25)
    assert "另有 **15** 个**已达标**单元未列出" in capped, capped[-800:]
    assert "_plan.csv" in capped, "the omission must point at the complete data"
    # the standalone CLI stays uncapped (D-130) — whoever ran the tool came here
    assert "未列出" not in stability.render_plan_markdown(
        rows, "t1_ttft_ms", max_ok_rows=None)


def test_the_fold_never_hides_a_row_the_reader_came_for():
    """Only 达标-and-clean rows may be folded. A short cell, an over-gate cell or
    a scenario-intrinsic one is the whole reason to read this table."""
    keep = {"cell": {"campaign_id": "base", "point_id": "P-short", "carrier": "cmcc",
                     "time_band": "busy", "tier": "metro", "profile_id": "s2_coding_agent"},
            "kpi": "t1_ttft_ms", "n": 5, "median": 100.0, "mean": 100.0,
            "cv_percent": 22.0, "unstable": True, "low_confidence": False,
            "implausible_values": {}, "stdev": 22.0, "mde": 17.0, "mde_pct": 17.0,
            "mde_power": 31.0, "target_abs": 5.0, "required_n": 60,
            "required_n_power": 204, "resolves_target": False,
            "resolves_at_power": False, "scenario_intrinsic_jitter": True,
            "scenario_jitter_reason": ""}
    filler = []
    for i in range(40):
        filler.append(dict(keep, cell=dict(keep["cell"], point_id="P%02d" % i),
                           cv_percent=1.0, unstable=False, required_n_power=2,
                           resolves_target=True, resolves_at_power=True,
                           scenario_intrinsic_jitter=False,
                           scenario_jitter_reason="not_applicable"))
    md = stability.render_plan_markdown(filler + [keep], "t1_ttft_ms", max_ok_rows=25)
    assert "P-short" in md, "a short + over-gate + marked row was folded away"
    assert "另有 **15**" in md, md[-500:]


def test_the_two_plan_gates_move_the_NUMBERS_not_just_the_wording():
    """Found by mutation audit, and it is D-318's lesson again.

    `test_every_archived_threshold_actually_decides_the_report` perturbs a gate
    and requires the report to change. Both of these gates are printed in the
    section HEADING as well as used in the arithmetic — 「目标：分辨 5% 的差异」,
    「需 n≥(80%)」 — so replacing the module constant with a hardcoded literal
    INSIDE the functions leaves that test green: the heading still moves, the
    numbers no longer do. Perturbing a constant and watching the report change
    only proves it moved SOMETHING; it cannot tell a number from a caption, so
    the assertion has to land on the number (D-318).

    Both mutations survived the whole suite before this test existed.
    """
    recs = _jitter_corpus([400.0, 424.0, 376.0, 416.0, 400.0],
                          [20.0, 20.1, 19.9, 20.05, 20.0])
    cells = stability.stability_cells(recs, "t1_ttft_ms")

    def required_ns():
        rows = stability.plan_cells(cells)
        return ([r["required_n"] for r in rows],
                [r["required_n_power"] for r in rows])

    base_even, base_power = required_ns()
    assert any(v for v in base_even), "fixture resolves nothing - proves nothing"

    old = stability.DEFAULT_TARGET_EFFECT_PCT
    try:
        # a bigger target is easier to resolve, so required_n must FALL
        stability.DEFAULT_TARGET_EFFECT_PCT = old * 5
        moved_even, moved_power = required_ns()
    finally:
        stability.DEFAULT_TARGET_EFFECT_PCT = old
    assert moved_even != base_even, (
        "DEFAULT_TARGET_EFFECT_PCT is archived as an output-deciding gate, yet "
        "the sample sizes did not move: it is being read from somewhere the "
        "manifest does not describe")
    assert moved_power != base_power, (moved_power, base_power)

    old_p = campaign_common.PLAN_POWER
    try:
        campaign_common.PLAN_POWER = 0.95
        _, p95 = required_ns()
    finally:
        campaign_common.PLAN_POWER = old_p
    assert p95 != base_power, (
        "PLAN_POWER is archived as an output-deciding gate, yet 需 n≥(80%) did "
        "not move")
    # …and in the right direction: more confidence costs more repeats
    assert all(a >= b for a, b in zip(p95, base_power)
               if a is not None and b is not None), (p95, base_power)
    # the break-even column must NOT move with power - it is the other criterion
    assert required_ns()[0] == base_even

    # …and the CAPTION is derived from the same gate. Mutation audit: hardcoding
    # PLAN_POWER inside power_factor()~s None-branch left every table number
    # right (required_n_at_power resolves the gate before calling it) while the
    # prose still quoted the 80% multiplier under an 「有 95% 把握」 heading — a
    # section disagreeing with itself about which gate is in force (D-301).
    def caption():
        md = stability.render_plan_markdown(stability.plan_cells(cells),
                                            "t1_ttft_ms", max_ok_rows=None)
        # the MULTIPLIER token alone. The whole line also carries 「80%」 →
        # 「95%」, which follows PLAN_POWER directly, so a line-level compare
        # reads "changed" while the multiplier sits frozen - the mutant walked
        # past that version too.
        import re as _re
        return _re.findall(r"1\+z=([0-9.]+)", md)

    base_cap = caption()
    assert base_cap, "the caption line vanished - the guard would prove nothing"
    try:
        campaign_common.PLAN_POWER = 0.95
        moved_cap = caption()
    finally:
        campaign_common.PLAN_POWER = old_p
    # compared against ITSELF at another gate, not against power_factor() -
    # asking the mutated function for the expected value is circular and was
    # the first version of this assertion, which the mutant walked straight past
    assert moved_cap != base_cap, (
        "the caption quotes a multiplier that did not follow PLAN_POWER: "
        "the prose keeps the old gate under a heading announcing the new one")
