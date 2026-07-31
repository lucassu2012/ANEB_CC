# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/publish_check.py.

The severity split is the whole point: FAIL is for things a machine can be sure
are wrong (blocks publication), WARN is for things that need a human to explain.
A WARN must never be silently upgraded to PASS, and "cannot judge" must never
read as "no problem" — split further by D-229 into WARN (there are objects, the
evidence to judge them is missing) and N/A (there is no object at all).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import publish_check as pc
import synth_campaign as sc
from synth import aqs_records, contractify, kpi_scenario_records, make_record

SYNTH_SMALL = dict(points=2, repeats=2, campaigns=("base",), carriers=("cmcc",),
                   time_bands=("busy",), tiers=("metro",))


def _sev(rows, item):
    for r in rows:
        if r["item"] == item:
            return r["severity"]
    raise AssertionError(f"no such check item: {item}")


def _detail(rows, item):
    for r in rows:
        if r["item"] == item:
            return r["detail"]
    raise AssertionError(f"no such check item: {item}")


_OE_ROT = "s1_chat,s2_rag|s2_rag,s1_chat"


def test_a_confounded_profile_never_counts_as_no_order_bias():
    """The gate's happy path prints 「N 处均未见序位偏倚」. A profile whose
    positions were fed by different cells cannot support that sentence in
    either direction — the report's own markdown refuses to claim it — so it
    must be excluded from the count and named on its own line, exactly as
    not-computable already is (D-335).
    """
    from synth import order_records
    recs = (order_records(5, value=40.0, order_index=0, point="P-fast",
                          scenario_order=_OE_ROT)
            + order_records(5, value=120.0, order_index=1, point="P-slow",
                            scenario_order=_OE_ROT))
    rows = pc.check(recs)
    assert _sev(rows, "序位效应·单元混杂") == pc.WARN, _detail(rows, "序位效应·单元混杂")
    # the headline item must not be a PASS built on the excluded profile
    assert _sev(rows, "序位效应") != pc.PASS, _detail(rows, "序位效应")
    assert "均未见序位偏倚" not in _detail(rows, "序位效应")


def test_a_confounded_profile_with_no_spread_is_still_not_a_pass():
    """The branch the test above never reached. A confounded profile that also
    happens to show no spread lands in the PASS arm — 「N 处均未见序位偏倚」 —
    which is the gate asserting a premise it could not check.

    Found by mutation: dropping the `continue` that excludes confounded
    profiles SURVIVED, because the other fixture's profile had a spread and so
    fell into the WARN arm regardless. A guard whose corpus never reaches the
    branch it names is not guarding it (D-335).
    """
    from synth import order_records
    recs = (order_records(5, value=100.0, order_index=0, point="P-a",
                          scenario_order=_OE_ROT)
            + order_records(5, value=100.0, order_index=1, point="P-b",
                            scenario_order=_OE_ROT))
    p = __import__("order_effect").analyze(recs, kpi="t1_ttft_ms")["profiles"][0]
    assert p["position_cell_imbalance"] is True and p["spread"] == 0, p
    assert p["order_effect_suspected"] is False, "otherwise this is the other test"

    rows = pc.check(recs)
    assert _sev(rows, "序位效应") != pc.PASS, _detail(rows, "序位效应")
    assert "均未见序位偏倚" not in _detail(rows, "序位效应")
    assert _sev(rows, "序位效应·单元混杂") == pc.WARN


def test_a_counterbalanced_corpus_passes_the_pooling_premise():
    """And it has to be a PASS with a count, not an N/A: an item that can only
    ever say 「未核算」 teaches the reader nothing and hides a regression."""
    from synth import order_records
    recs = []
    for point, value in (("P-fast", 40.0), ("P-slow", 120.0)):
        for idx in (0, 1):
            recs += order_records(5, value=value, order_index=idx, point=point,
                                  scenario_order=_OE_ROT)
    rows = pc.check(recs)
    assert _sev(rows, "序位效应·单元混杂") == pc.PASS, _detail(rows, "序位效应·单元混杂")
    assert any(ch.isdigit() for ch in _detail(rows, "序位效应·单元混杂")), \
        "a PASS with no count is not evidence that anything was compared"


def _clean():
    """Labelled, contract-complete, WITH scenarios, no seeded problems.

    Must carry scenarios: a scenario-less fixture makes the validity/buffering
    checks take their 'no data' branch, so a test seeding a problem into
    `scenarios` would pass for entirely the wrong reason.
    """
    return [contractify(r) for r in
            kpi_scenario_records(6, aqs=90, kpi={"n1_rtt_p50_ms": 20})]


def test_empty_corpus_fails():
    rows = pc.check([])
    assert rows[0]["severity"] == pc.FAIL


def test_synthetic_records_block_publication():
    assert _sev(pc.check(sc.generate(**SYNTH_SMALL)), "合成语料") == pc.FAIL


def test_unlabelled_corpus_fails():
    recs = [contractify(make_record(aqs=90, scenarios=[])) for _ in range(5)]
    assert _sev(pc.check(recs), "战役标签") == pc.FAIL
    # 「无战役标签，无池化风险」 was a PASS: true in the letter — you cannot pool
    # two campaigns when there are none — and the opposite of the truth in the
    # eye, since everything is already pooled into one cell (D-229). No random
    # corpus reaches this branch either.
    assert _sev(pc.check(recs), "战役池化") == pc.NA


def test_clean_corpus_has_no_fail():
    assert not [r for r in pc.check(_clean()) if r["severity"] == pc.FAIL]


def test_clean_fixture_actually_has_scenarios():
    """Guard against the vacuous-test trap: with a scenario-less fixture the
    validity/buffering checks take their 'no data' branch and the tests below
    would pass without exercising anything."""
    assert all(r["scenarios"] for r in _clean())


def test_low_validity_is_warn_not_fail():
    """Below-floor validity needs an explanation, but the tool must not decide
    for the author that the report is unpublishable."""
    recs = _clean()
    for r in recs[:4]:
        for s in r["scenarios"]:
            s["validity"] = "invalid"
            s["invalid_reasons"] = "STREAM_ABORTED"
    assert _sev(pc.check(recs), "有效率") == pc.WARN


def test_distortion_hotspot_is_warn():
    recs = _clean()
    for r in recs:
        for s in r["scenarios"]:
            s["buffering"] = {"score": 0.6, "attribution": "middlebox_suspect",
                              "sample_count": 100, "sawtooth_ratio": 0.4,
                              "near_zero_arrival_ratio": 0.3}
    assert _sev(pc.check(recs), "批化失真") == pc.WARN


def test_the_publish_gate_knows_about_the_radio_covariate():
    """Every other analysis module has a gate item. radio_rollup had none — the
    word `radio` matched nothing in publish_check.py — although PLAN_ALIGNMENT
    §7.3 names the radio context the first substitute for the cancelled
    three-tier decomposition, and 「该点位忙闲差不可单独归因于时段」 disqualifies
    one of the two comparison axes that survived it (D-305).

    Both rows must appear on every corpus shape (D-150), 无线上下文 can never
    reach PASS while the producer writes nothing (the shape of D-156), and the
    comparability row must fire where the rehearsal plants a cell change.
    """
    import radio_rollup

    bare = _clean()                  # fixture carries no network_snapshot.radio
    rows = pc.check(bare)
    assert _sev(rows, "无线上下文") == pc.WARN
    assert _sev(rows, "忙闲同小区") == pc.NA

    withradio = sc.generate(points=8, repeats=5, radio=True,
                            campaigns=("base", "opt"))
    places = radio_rollup.analyze(withradio)["places"]
    moved = [p for p in places if p["changed"] or p["partial"]]
    assert moved, "the rehearsal plants no cell change; this half asserts nothing"
    rows2 = pc.check(withradio)
    assert _sev(rows2, "忙闲同小区") == pc.WARN
    assert _sev(rows2, "无线上下文") in (pc.WARN, pc.PASS)

    for label, rs in (("no radio", rows), ("with radio", rows2)):
        names = [r["item"] for r in rs]
        for item in ("无线上下文", "忙闲同小区"):
            assert names.count(item) == 1, (label, item, names.count(item))


def test_mixed_versions_are_warn_not_fail():
    """The tool cannot know whether a kpi_set bump changed the metric
    definitions, so this needs a human, not a machine verdict (D-137)."""
    recs = _clean()
    recs[0]["kpi_set"] = "agent-qoe-kpi-v0.1"
    assert _sev(pc.check(recs), "版本一致性") == pc.WARN
    assert _sev(pc.check(_clean()), "版本一致性") == pc.PASS


def test_no_evidence_is_warn_never_pass():
    """'Cannot judge' must not read as 'no problem' (R-10)."""
    rows = pc.check(_clean())                      # fixture has no clock block
    assert _sev(rows, "测量可信度") == pc.WARN
    assert _sev(rows, "序位效应") == pc.WARN       # no order_index evidence


def test_low_confidence_cells_warn():
    assert _sev(pc.check([contractify(r) for r in aqs_records(90, 2)]),
                "样本充分性") == pc.WARN


def _two_campaigns(before_vals, after_vals):
    recs = [r for v in before_vals for r in aqs_records(v, 1, campaign_id="base")]
    recs += [r for v in after_vals for r in aqs_records(v, 1, campaign_id="opt")]
    return [contractify(r) for r in recs]


# AQS is defined on 0..100; these fixtures used to reach 150, i.e. the effect-size
# gate was being validated on scores the system cannot emit (surfaced by D-178).
# Same medians apart, same spread, values a producer could actually write.
_SUB_A, _SUB_B = [58, 68, 78, 88, 98], [60, 70, 80, 90, 100]     # medians 78 / 80
_REAL_A, _REAL_B = [10, 20, 30, 40, 50], [60, 70, 80, 90, 100]   # medians 30 / 80


def test_effect_within_noise_is_warn():
    """A round whose every Δ sits inside the noise must not ship as 'improved'."""
    rows = pc.check(_two_campaigns(_SUB_A, _SUB_B))
    assert _sev(rows, "效应量") == pc.WARN
    assert "不得表述为改善或回退" in _detail(rows, "效应量")


def test_effect_beyond_noise_passes():
    rows = pc.check(_two_campaigns(_REAL_A, _REAL_B))
    assert _sev(rows, "效应量") == pc.PASS


def test_effect_unknown_noise_is_warn_not_pass():
    """n=1 per side: spread unknown, so the delta cannot be called real (R-10)."""
    rows = pc.check(_two_campaigns([70], [85]))
    assert _sev(rows, "效应量") == pc.WARN
    assert "噪声不可估" in _detail(rows, "效应量")


def _media(cells):
    """cells: {point_id: (wifi_values, cellular_values)} -> a labelled corpus."""
    out = []
    for point, (wifi, cell) in cells.items():
        for medium, vals in (("wifi", wifi), ("cellular", cell)):
            for v in vals:
                for r in aqs_records(v, 1, point=point):
                    r["run"]["transport"] = medium
                    out.append(r)
    return [contractify(r) for r in out]


def test_media_effect_unknown_noise_is_warn_not_pass():
    """The twin of 效应量 above, which has had this branch since D-144.

    P1 has a real gap; P2 has one cellular run, so its noise cannot be estimated
    and its Δ was never judged. Reporting PASS on "1/2 negative Δ beyond noise"
    counts the unjudged cell in the denominator as if it had been judged and
    cleared — and the item's own comment claimed it used the same three buckets
    as 效应量, which is what kept the missing branch invisible (D-198).
    """
    rows = pc.check(_media({"P1": ([80, 82, 84, 86, 88], [50, 52, 54, 56, 58]),
                            "P2": ([80, 82, 84, 86, 88], [60])}))
    assert _sev(rows, "介质效应量") == pc.WARN
    assert "噪声不可估" in _detail(rows, "介质效应量")


def test_media_effect_beyond_noise_still_passes():
    """…and the new branch must not become a blanket refusal."""
    rows = pc.check(_media({"P1": ([80, 82, 84, 86, 88], [50, 52, 54, 56, 58])}))
    assert _sev(rows, "介质效应量") == pc.PASS


def test_no_usable_cell_is_not_sufficient_sampling():
    """PASS「全部 0 个格样本充足」 — sufficiency asserted over nothing.

    The empty set satisfies every predicate, which is exactly why it must not be
    reported as satisfying this one (§2.2, D-198). Reachable whenever no run
    carries a usable AQS.
    """
    rows = pc.check([contractify(r) for r in aqs_records(None, 5)])
    assert _sev(rows, "样本充分性") == pc.WARN
    assert "无从核算" in _detail(rows, "样本充分性")
    # Same corpus, sibling row: with no scoreable cell there is no run whose
    # score could have been veto-capped, and 「无被否决封顶的 run」 read as a
    # clean result over an empty set (D-229). Pinned here because no random
    # corpus reaches this branch.
    assert _sev(rows, "否决封顶") == pc.NA


def test_verdict_wording_states_the_warn_contract():
    md_fail = pc.render_markdown(pc.check([]))
    assert "不可发布" in md_fail
    md_ok = pc.render_markdown(pc.check(_clean()))
    assert "可发布" in md_ok
    assert "不可发布" not in md_ok
    assert "须由人解释" in md_ok


def test_rows_sorted_most_severe_first():
    sev = [r["severity"] for r in pc.check(sc.generate(**SYNTH_SMALL))]
    rank = {pc.FAIL: 0, pc.WARN: 1, pc.NA: 2, pc.PASS: 3}
    assert sev == sorted(sev, key=lambda s: rank[s])


def test_pooled_campaigns_are_flagged_for_publication():
    """The runbook's workflow is one report per campaign; nothing checked that
    the corpus being published was that kind (D-147)."""
    rows = pc.check(_two_campaigns([70, 72, 74, 71, 73], [80, 82, 84, 81, 83]))
    assert _sev(rows, "战役池化") == pc.WARN
    assert "既不是前也不是后" in _detail(rows, "战役池化")


def test_single_campaign_is_not_flagged():
    recs = [contractify(r) for r in aqs_records(90, 5, campaign_id="base")]
    assert _sev(pc.check(recs), "战役池化") == pc.PASS


def test_lookalike_labels_are_warned_before_publication():
    recs = [contractify(r) for r in
            (aqs_records(80, 3, point="SZ-CBD-01") + aqs_records(80, 3, point="sz-cbd-01"))]
    assert _sev(pc.check(recs), "标签同名异写") == pc.WARN
    assert "未自动合并" in _detail(pc.check(recs), "标签同名异写")
    clean = [contractify(r) for r in aqs_records(80, 3, point="SZ-CBD-01")]
    assert _sev(pc.check(clean), "标签同名异写") == pc.PASS


def test_effect_size_row_exists_even_with_one_campaign():
    """Every other item emits a row in every case; a silently absent one cannot
    be told apart from a check that was forgotten (D-150).

    The row is N/A, not PASS: with one campaign there is no before/after pair,
    the summary already tells the reader the improvement question is
    unanswerable this round, and a green tick here said the opposite (D-229).
    """
    recs = [contractify(r) for r in aqs_records(90, 5, campaign_id="base")]
    assert _sev(pc.check(recs), "效应量") == pc.NA
    assert "无前后可比对象" in _detail(pc.check(recs), "效应量")


def test_implausible_epoch_is_warned_before_publication():
    """WARN, not FAIL: this layer cannot tell a producer bug from a corpus
    stitched out of something else. But it must not PASS — an epoch of the wrong
    magnitude still sorts, so before/after comes out backwards with confidence."""
    recs = [contractify(r) for r in aqs_records(90, 5, campaign_id="base")]
    for r in recs[:2]:
        r["run"]["started_at_epoch_ms"] = 1783944000       # seconds, not ms
    rows = pc.check(recs)
    assert _sev(rows, "时间戳量级") == pc.WARN
    assert "疑似秒" in _detail(rows, "时间戳量级")
    clean = [contractify(r) for r in aqs_records(90, 5, campaign_id="base")]
    assert _sev(pc.check(clean), "时间戳量级") == pc.PASS


def test_every_check_item_appears_for_every_corpus_shape():
    """The runbook checklist is read against this output — an item that only
    appears for some corpora makes the checklist unverifiable."""
    import synth_campaign as sc
    from test_report_properties import _corrupt_corpus, _random_corpus

    # Two shapes was not every shape. Seven now, and they do agree — the honest
    # answer is that this promise was being kept; it simply was never asked of a
    # corpus with impossible values, or a chaos rehearsal, or a three-campaign
    # grid where the trend section exists (D-254).
    shapes = {
        "single": [contractify(r) for r in aqs_records(90, 5, campaign_id="base")],
        "two": _two_campaigns([70, 72, 74, 71, 73], [80, 82, 84, 81, 83]),
        "corrupt": _corrupt_corpus(),
        "random0": _random_corpus(0),
        "random3": _random_corpus(3),
        "synth3": sc.generate(points=3, repeats=3,
                              campaigns=("base", "opt", "later")),
        "chaos": sc.inject_chaos(sc.generate(points=3, repeats=3,
                                             campaigns=("base", "opt"))),
    }
    sets = {k: {r["item"] for r in pc.check(v)} for k, v in shapes.items()}
    first = sets["single"]
    for name, items in sorted(sets.items()):
        assert items == first, (name, sorted(items ^ first))
    assert len(first) >= 20, f"only {len(first)} check items — did the gate shrink?"
    assert len(shapes) >= 7, "the shape set was narrowed"

    # The one shape that does NOT produce the full list, pinned rather than left
    # as an unexamined difference: an empty corpus collapses to a single row.
    # That is the right answer — one plain statement beats 22 N/A rows — but it
    # has to be a decided answer, and it must not be green (D-150 / D-229).
    empty = pc.check([])
    assert len(empty) == 1, [r["item"] for r in empty]
    assert empty[0]["severity"] != pc.PASS, empty[0]


def test_inferred_time_band_is_warned_before_publication():
    import annotate_campaign as ann
    recs = [contractify(make_record(
        campaign={"campaign_id": "base", "point_id": "P1", "carrier": "cmcc",
                  "tier": "metro"}, aqs=80, scenarios=[],
        started_ms=1783944000000 + i * 3600000)) for i in range(6)]
    out, _ = ann.annotate(recs, infer_tb=True)
    assert _sev(pc.check(out), "标签来源") == pc.WARN
    assert "非现场记录" in _detail(pc.check(out), "标签来源")
    assert _sev(pc.check(_clean()), "标签来源") == pc.PASS


def test_veto_capped_cells_are_warned_before_publication():
    recs = [contractify(r) for r in aqs_records(54, 6, point="P1")]
    for r in recs[:4]:
        r["run"]["aqs"]["veto_applied"] = True
    rows = pc.check(recs)
    assert _sev(rows, "否决封顶") == pc.WARN
    # the flag is the T4 severe-stall veto, a network-side fault — the wording
    # must not send the reader looking at session failures (D-159)
    assert "T4 严重卡顿率" in _detail(rows, "否决封顶")
    assert "会话" not in _detail(rows, "否决封顶")
    assert _sev(pc.check(_clean()), "否决封顶") == pc.PASS


def test_tier_simultaneity_is_checked_before_publication():
    from synth import make_record
    def at(tier, val, off, n=5):
        c = {"campaign_id": "base", "tier": tier, "point_id": "P1",
             "carrier": "cmcc", "time_band": "idle"}
        return [contractify(make_record(
            campaign=c, scenarios=[("s1_chat", {"n1_rtt_p50_ms": val})], aqs=80,
            started_ms=1783944000000 + off + i * 60000)) for i in range(n)]
    apart = at("metro", 30, 0) + at("regional", 42, 600000) + at("core", 70, 8 * 3600_000)
    rows = pc.check(apart)
    assert _sev(rows, "层级同时性") == pc.WARN
    assert "共模不再抵消" in _detail(rows, "层级同时性")
    together = at("metro", 30, 0) + at("regional", 42, 600000) + at("core", 70, 1200000)
    assert _sev(pc.check(together), "层级同时性") == pc.PASS


def test_every_row_the_gate_produces_reaches_the_page_intact():
    """The individual item guards assert on what check() returns, which is one
    step before the operator. Dropping the detail column from render_markdown
    was caught by exactly one of 498 tests (D-281) — an entire column could
    vanish from what a reader sees and almost nothing noticed.

    So this walks the rows the gate actually produced, rather than a list of
    items typed here, and requires each to arrive whole: named once, carrying
    its own explanation, wearing a verdict (D-282).
    """
    seen = 0
    for corpus in (_clean(), _two_campaigns([70, 72, 74], [80, 82, 84])):
        rows = pc.check(corpus)
        assert rows, "the gate produced no rows to check"
        md = pc.render_markdown(rows)
        for r in rows:
            # by cell, not by substring: 效应量 is inside 介质效应量, and the
            # first version matched both rows (the "too wide a word" trap this
            # layer already records against its own assertions)
            cell = "| %s |" % r["item"]
            named = [ln for ln in md.split("\n") if cell in ln]
            assert len(named) == 1, (r["item"], named)
            assert r["detail"] in named[0], (r["item"], r["detail"], named[0])
            assert any(v in named[0] for v in ("FAIL", "WARN", "N/A", "PASS")), \
                named[0]
            seen += 1
    assert seen >= 20, f"only {seen} rendered rows checked"


def test_uncheckable_premise_is_stated_not_omitted():
    # ⚠ SOLE targeted guard on handover §2.2 "cannot check" != "checked"
    #   (D-186's mutation map). Flipping this item to PASS breaks nothing else.
    """"Same client" is not merely unchecked — the contract carries no device
    identity at all, so it is uncheckable. Saying nothing would let a reader
    assume it held (D-156)."""
    rows = pc.check(_clean())
    assert _sev(rows, "同一客户端") == pc.WARN
    assert "无法核对" in _detail(rows, "同一客户端")
    # Everything above stops at the row dict that CARRIES the words, and the
    # claim is that the reader is told. Drop the detail column from the
    # renderer and all of it still passes while the operator sees a bare WARN
    # (D-281 — the same gap D-280 found in the rehearsal guard).
    named = [ln for ln in pc.render_markdown(rows).split("\n")
             if "同一客户端" in ln]
    assert len(named) == 1, named
    assert "无法核对" in named[0], named[0]
    # …and it must be a WARN on every corpus, since nothing can ever clear it
    for corpus in (_clean(), _two_campaigns([70, 72, 74], [80, 82, 84])):
        assert _sev(pc.check(corpus), "同一客户端") == pc.WARN


def test_cell_counts_are_cells_not_cell_times_kpi():
    """These checks sweep the attribution cells once per attributable KPI, so a
    compromised cell used to be counted once for each — "12 个格" about six
    cells, a number the reader cannot find anywhere and double the apparent
    severity. Mixed media is a property of the CELL (its tiers used different
    access), not of the KPI that happened to expose it (D-191)."""
    import attribution
    from synth import make_record
    def at(tier, transport, n=5):
        c = {"campaign_id": "base", "tier": tier, "point_id": "P1",
             "carrier": "cmcc", "time_band": "busy"}
        out = []
        for _ in range(n):
            # both attributable KPIs present => the same cell appears in both sweeps
            r = make_record(campaign=c, aqs=80,
                            scenarios=[("s1_chat", {"n1_rtt_p50_ms": 20,
                                                    "t1_ttft_ms": 400})])
            r["run"]["transport"] = transport
            out.append(contractify(r))
        return out
    recs = at("metro", "wifi") + at("core", "auto(cellular)")
    distinct = {tuple(sorted(c["cell"].items()))
                for k in attribution.ATTRIBUTABLE_KPIS
                for c in attribution.attribute(recs, kpi=k)["cells"]}
    assert len(attribution.ATTRIBUTABLE_KPIS) > 1, "otherwise this proves nothing"
    detail = _detail(pc.check(recs), "同一接入")
    assert detail.startswith(f"{len(distinct)} 个格"), (detail, len(distinct))


def _with_transport(rec, tp):
    rec["run"]["transport"] = tp
    return rec


def test_the_gate_makes_a_single_round_corpus_answer_for_its_absolute_numbers():
    """D-357: the summary and the deliverable skeleton both mention warm-up, but
    only this gate has teeth — its contract is that every WARN must be answered in
    the report body before publishing. A single-round corpus (quick mode, the
    ordinary case) always samples the cold round, so 「TTFT 是 X ms」 written with no
    qualifier is the exact sentence this row exists to stop (D-355).

    Both halves pinned: a corpus that DID measure several rounds and found no
    warm-up must come back PASS, or the row is noise on every report.
    """
    from synth import make_record

    def corpus(rounds_and_values):
        out = []
        for i in range(3):
            rec = make_record(campaign={"campaign_id": "c", "tier": "metro",
                                        "point_id": "P1", "carrier": "ctcc",
                                        "time_band": "busy"}, aqs=88, scenarios=[])
            rec["scenarios"] = [
                {"profile_id": "s1_chat", "profile_version": "0.2.1",
                 "repeat_index": rnd, "kpi": {"t1_ttft_ms": v + i}}
                for rnd, v in rounds_and_values
            ]
            out.append(contractify(rec))
        return out

    single = corpus([(0, 50.0)])
    assert _sev(pc.check(single), "预热效应") == pc.WARN
    assert "冷启动口径" in _detail(pc.check(single), "预热效应")

    warm = corpus([(0, 56.0), (1, 47.0), (2, 47.5)])
    assert _sev(pc.check(warm), "预热效应") == pc.WARN
    assert "以后续轮为准" in _detail(pc.check(warm), "预热效应")

    flat = corpus([(0, 50.0), (1, 50.2), (2, 49.9)])
    assert _sev(pc.check(flat), "预热效应") == pc.PASS, _detail(pc.check(flat), "预热效应")


def test_gate_and_summary_explain_an_unjudgeable_order_effect_the_same_way():
    """D-354's second half: the gate had its OWN two-way guess at why nothing was
    judgeable, with a comment saying naming the wrong cause is worse than naming
    none — and it named the wrong one the day a third cause appeared. Both front
    doors now read the same reason table off the same analysis (§2.14, D-338).
    """
    import campaign_report as rpt
    from synth import make_record

    rec = make_record(campaign={"campaign_id": "c", "tier": "metro", "point_id": "P1",
                                "carrier": "ctcc", "time_band": "busy"},
                      aqs=88, scenarios=[])
    rec["run"]["mode"] = "forensic"
    rec["run"]["scenario_order"] = "s1,s2,s3|s2,s3,s1|s3,s1,s2"
    rec["scenarios"] = [
        {"profile_id": "s1_chat", "profile_version": "0.2.1", "order_index": i,
         "kpi": {"t1_ttft_ms": v}}
        for i, v in ((0, 50.0), (5, 52.7), (7, 39.0))
    ]
    recs = [contractify(rec)]

    detail = _detail(pc.check(recs), "序位效应")
    assert "位次不足 2" not in detail, detail   # the false explanation
    assert "每个位次仅 1 个样本" in detail, detail

    summary = rpt.render_summary_markdown(recs)
    line = [l for l in summary.splitlines() if "序位效应" in l][0]
    assert "每个位次仅 1 个样本" in line, line


def test_single_tier_corpus_never_claims_three_tiers_were_checked():
    """D-350: found on the FIRST real pilot corpus, not by reading.

    The report body has said 「本轮含义不同」 on single-tier corpora since D-157, but
    this gate — the last table an operator reads before publishing — still said
    「N 个格三层级接入介质一致」 about a corpus carrying exactly one tier. Nothing about
    tiers had been verified. The WARN branch was worse: it names a 骨干增量 that
    cannot exist behind one server.

    Both halves are pinned. The three-tier half keeps the fix from becoming a
    blanket rewording: a corpus that really does pair tiers must still get the
    tier wording.
    """
    from synth import make_record

    def cell(tier, transport, n=5):
        c = {"campaign_id": "base", "tier": tier, "point_id": "P1",
             "carrier": "ctcc", "time_band": "busy"}
        return [contractify(_with_transport(
            make_record(campaign=dict(c), aqs=80,
                        scenarios=[("s1_chat", {"n1_rtt_p50_ms": 20})]), transport))
                for _ in range(n)]

    one_tier = cell("metro", "auto(cellular)")
    detail = _detail(pc.check(one_tier), "同一接入")
    assert _sev(pc.check(one_tier), "同一接入") == pc.PASS
    assert "三层级" not in detail, detail
    assert "单层级" in detail, detail

    paired = cell("metro", "wifi") + cell("core", "wifi")
    paired_detail = _detail(pc.check(paired), "同一接入")
    assert "三层级" in paired_detail, paired_detail

    # …and the mixed-media branch, both ways: single-tier must not promise a
    # backbone increment it cannot have.
    mixed_one = cell("metro", "wifi") + cell("metro", "auto(cellular)")
    mixed_detail = _detail(pc.check(mixed_one), "同一接入")
    assert _sev(pc.check(mixed_one), "同一接入") == pc.WARN
    assert "骨干增量" not in mixed_detail, mixed_detail


def test_mixed_access_media_across_tiers_is_warned():
    from synth import make_record
    def at(tier, val, transport, n=5):
        c = {"campaign_id": "base", "tier": tier, "point_id": "P1",
             "carrier": "cmcc", "time_band": "busy"}
        out = []
        for _ in range(n):
            r = make_record(campaign=c, aqs=80,
                            scenarios=[("s1_chat", {"n1_rtt_p50_ms": val})])
            r["run"]["transport"] = transport
            out.append(contractify(r))
        return out
    mixed = at("metro", 20, "wifi") + at("core", 90, "auto(cellular)")
    assert _sev(pc.check(mixed), "同一接入") == pc.WARN
    same = at("metro", 20, "wifi") + at("core", 90, "wifi")
    assert _sev(pc.check(same), "同一接入") == pc.PASS


def _staged_rollout(n=15, **campaign):
    """The C1 wiring spec ships labels in stages; this is a mid-rollout corpus."""
    base = {"campaign_id": "sz-q3", "carrier": "cmcc", "time_band": "busy",
            "tier": "metro"}
    base.update(campaign)
    return [contractify(make_record(campaign=dict(base), aqs=80, scenarios=[]))
            for _ in range(n)]


def test_unusable_labels_do_not_pass_as_labelled():
    """A non-empty run.campaign block is not a usable label set: the staged C1
    rollout writes everything except point_id, and that corpus used to PASS
    while the heat card collapsed to a single `unlabeled` row (D-162)."""
    recs = _staged_rollout()                      # no point_id at all
    rows = pc.check(recs)
    assert _sev(rows, "战役标签") == pc.FAIL
    assert "point_id" in _detail(rows, "战役标签")
    assert "塌缩为单格" in _detail(rows, "战役标签")


def test_partial_label_gap_is_warn():
    recs = _staged_rollout(n=10, point_id="P1") + _staged_rollout(n=5)
    rows = pc.check(recs)
    assert _sev(rows, "战役标签") == pc.WARN
    assert "5/15" in _detail(rows, "战役标签")


def test_fully_labelled_corpus_passes():
    recs = _staged_rollout(point_id="P1")
    assert _sev(pc.check(recs), "战役标签") == pc.PASS


def test_no_batching_evidence_is_warn_not_pass():
    """Zero measured scenarios used to render as PASS 无失真热点 (D-163)."""
    recs = _clean()
    for r in recs:
        for s in r["scenarios"]:
            s["buffering"] = {"score": None, "attribution": None, "sample_count": None,
                              "sawtooth_ratio": None, "near_zero_arrival_ratio": None}
    rows = pc.check(recs)
    assert _sev(rows, "批化失真") == pc.WARN
    assert "无法判断" in _detail(rows, "批化失真")


def test_tier_endpoint_conflict_blocks_publication():
    from synth import make_record
    def ep(tier_name, val, endpoint, n=5):
        c = {"campaign_id": "base", "tier": tier_name, "point_id": "P1",
             "carrier": "cmcc", "time_band": "busy", "server_tier_endpoint": endpoint}
        return [contractify(make_record(campaign=c, aqs=80,
                                        scenarios=[("s1_chat", {"n1_rtt_p50_ms": val})]))
                for _ in range(n)]
    M = "https://metro.example:8443"
    same = ep("metro", 30, M) + ep("regional", 50, M) + ep("core", 90, M)
    rows = pc.check(same)
    assert _sev(rows, "层级对账") == pc.FAIL
    assert "骨干分解不成立" in _detail(rows, "层级对账")
    distinct = (ep("metro", 30, M) + ep("regional", 50, "https://r.example:8443")
                + ep("core", 90, "https://c.example:8443"))
    assert _sev(pc.check(distinct), "层级对账") == pc.PASS
    # …and a corpus without the field must say it could not reconcile (D-150)
    assert _sev(pc.check(_clean()), "层级对账") == pc.WARN
    assert "无法对账" in _detail(pc.check(_clean()), "层级对账")


def _order_rec(order=None):
    from synth import make_record
    r = make_record(campaign={"campaign_id": "base", "tier": "metro", "point_id": "P1",
                              "carrier": "cmcc", "time_band": "busy"},
                    aqs=80, scenarios=[("s1_chat", {"t1_ttft_ms": 100})])
    if order:
        r["run"]["scenario_order"] = order
    return contractify(r)


def test_order_effect_gate_distinguishes_three_corpora():
    """Three different corpora collapsed into one message. A corpus that HAS
    scenario_order and proves the Latin square never rotated is a stronger and
    quite different finding from one carrying no order evidence at all, and
    order_effect computes both verdicts (D-164) — the gate never read them
    (D-170)."""
    absent = [_order_rec() for _ in range(6)]
    assert _sev(pc.check(absent), "序位效应") == pc.WARN
    assert "无 `scenario_order`" in _detail(pc.check(absent), "序位效应")

    flat = [_order_rec("s1,s2,s3") for _ in range(6)]
    assert _sev(pc.check(flat), "序位效应") == pc.WARN
    assert "拉丁方未轮转" in _detail(pc.check(flat), "序位效应")

    rotated = [_order_rec("s1,s2,s3|s2,s3,s1|s3,s1,s2") for _ in range(6)]
    detail = _detail(pc.check(rotated), "序位效应")
    assert "未轮转" not in detail
    assert "无 `scenario_order`" not in detail


def _summary_flags_validity(summary):
    return any(l.startswith("- **有效率不达门") for l in summary.splitlines())


def _summary_flags_buffering(summary):
    return any(l.startswith("- **批化失真热点**") or "无批化标注" in l
               for l in summary.splitlines())


# (gate item, does the summary flag the same problem?). Both surfaces speak
# about one thing; if they disagree, one of them is lying to the operator.
def _summary_flags_trust(summary):
    # 「时钟可疑热点：无。」 shares its prefix with the hot-spot line, so a prefix
    # test reads "none" as "some" — the probe error D-228 records, kept out of
    # the guard here by matching the negative form explicitly.
    for line in summary.splitlines():
        if line.startswith("- **测量可信度"):            # no clock/seq/parse evidence
            return True
        if (line.startswith("- **时钟可疑热点**：")
                and not line.startswith("- **时钟可疑热点**：无")):
            return True
    return False


_GATE_VS_SUMMARY = (
    ("有效率", _summary_flags_validity),
    ("批化失真", _summary_flags_buffering),
    ("测量可信度", _summary_flags_trust),
)


def test_the_publish_gate_and_the_summary_tell_the_same_story():
    """The gate decides whether a report may be published; the summary is what
    the reader sees. On anything both of them speak about, they have to agree.

    They can drift: the media item carried its unestimable-noise branch since
    D-198 while the summary printed a clean negative for the same cells until
    D-216. Checked here as an enumerable list so the next pair is one line
    (D-228).
    """
    import campaign_report as rpt
    from test_report_properties import _corrupt_corpus, _random_corpus

    corpora = [("chaos", _corrupt_corpus())]
    corpora += [(f"seed{s}", _random_corpus(s)) for s in range(20)]

    seen = {item: set() for item, _ in _GATE_VS_SUMMARY}
    for tag, recs in corpora:
        sev = {r["item"]: r["severity"] for r in pc.check(recs)}
        summary = rpt.render_summary_markdown(recs)
        for item, summary_flags in _GATE_VS_SUMMARY:
            warns = sev.get(item) == pc.WARN
            assert warns == summary_flags(summary), (
                f"{tag}: the gate says {sev.get(item)} for {item} while the "
                "summary says the opposite — one of them is lying")
            seen[item].add(warns)

    # Both sides have to occur, or the agreement was only ever checked one way.
    for item, states in seen.items():
        assert states == {True, False}, (
            f"{item}: only {sorted(states)} occurred across {len(corpora)} "
            "corpora — one side of the agreement was never exercised")


# A loader counter the integrity item deliberately ignores, with the reason.
# Empty today: every counter load_records produces is named in the item.
_COUNTER_NOT_THE_GATES_BUSINESS = {}


def test_the_integrity_item_accounts_for_every_counter_the_loader_produces():
    """Counting what a rule covers, as a guard instead of by hand.

    The item is called 语料完整性 and reads load_records' counters. Twice the
    count came up short and both times it was found by hand: conflicts and
    malformed shipped without unreadable_files (D-328), and that shipped
    without no_run_id (D-329). The loader's key set is derivable, so derive it
    — a criterion beats a list (D-275), and this one retires a manual step that
    had already failed twice.
    """
    import inspect
    import os
    import tempfile
    import campaign_common as cc

    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "c.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write("{}\n")          # valid JSON, no run body, no run_id
        stats = {}
        cc.load_records([p], stats=stats, quiet=True)

    produced = set(stats)
    assert len(produced) >= 7, (
        "load_records handed back only %s — the key set is not being filled, "
        "so this guard would pass on nothing" % sorted(produced))

    # Matched on a READ of the key, not on the key name appearing anywhere.
    # The first version used a bare substring and a mutation removing the only
    # read of `lines` survived it — a comment inside check() happens to list
    # the key names, and a guard a comment can satisfy is barely a guard
    # (§2.12).
    src = inspect.getsource(pc.check)

    def is_read(k):
        return any(form % k in src for form in (
            'stats["%s"]', "stats['%s']",
            'stats.get("%s"', "stats.get('%s'",
            'st_int(stats, "%s")', "st_int(stats, '%s')"))

    unnamed = sorted(k for k in produced
                     if not is_read(k) and k not in _COUNTER_NOT_THE_GATES_BUSINESS)
    assert not unnamed, (
        "the loader reports these and the integrity item never reads them, "
        "so the operator is not told: %s" % unnamed)


def test_the_gate_notices_two_runs_disagreeing_under_one_id():
    """load_records calls a repeated run_id carrying a DIFFERENT body "a real
    data-integrity fault ... must never be averaged together", and the report
    prints it on its integrity line. The gate could not see it: check() was
    handed records and never the loader's counters, so the one signal saying
    two runs disagree about what happened lived on the page and nowhere in the
    checklist that exists because the page gets skipped (D-325, D-305's shape).

    Three states, because the middle one is the trap: no counters is N/A, not a
    quiet PASS.
    """
    from synth import make_record

    recs = [make_record(aqs=90, run_id="R-1"), make_record(aqs=80, run_id="R-2")]

    def item(rows):
        hits = [r for r in rows if r["item"] == "语料完整性"]
        assert len(hits) == 1, ("the integrity item appears %d times" % len(hits))
        return hits[0]

    assert item(pc.check(recs))["severity"] == pc.NA, (
        "handed no counters, the gate must say it did not run the check")

    # load_records' own key names (campaign_common: lines/kept/duplicates), not
    # the read/dropped the per-run loaders use — reading one loader's counters
    # with the other's vocabulary is what D-325 tripped over.
    clean = {"lines": 2, "kept": 2, "duplicates": 0, "conflicts": [],
             "malformed": 0, "unreadable_files": 0, "no_run_id": 0}
    assert item(pc.check(recs, stats=clean))["severity"] == pc.PASS

    bad = dict(clean, lines=3, duplicates=1, conflicts=["R-1"])
    row = item(pc.check(recs, stats=bad))
    assert row["severity"] == pc.WARN, row
    assert "R-1" in row["detail"], (
        "the warning does not name the offending run_id, leaving the operator "
        "nowhere to start: %r" % row["detail"])

    # A file that could not be read takes ALL of its records out of every
    # denominator, and load_records swallows the OSError and carries on.
    # corpus_health calls it ERROR; the item first shipped without it, checking
    # two of the three things it claimed to cover (D-328).
    unread = dict(clean, unreadable_files=1)
    row = item(pc.check(recs, stats=unread))
    assert row["severity"] == pc.WARN, row
    assert "读不了的文件" in row["detail"], row

    # Records with no run_id cannot be de-duplicated at all (R-10 forbids a
    # fabricated key), so repeats among them stay invisible. Not a bug to fix —
    # a fact the operator has to be handed (D-329).
    anon = dict(clean, no_run_id=2)
    row = item(pc.check(recs, stats=anon))
    assert row["severity"] == pc.WARN, row
    assert "无 run_id 的记录" in row["detail"], row


def test_a_check_with_nothing_to_run_on_never_renders_as_pass():
    """A green tick against a check that never ran is the lie D-163 and D-198
    took out of 批化失真 / 测量可信度 / 样本充分性 and left standing everywhere
    else: 「无同格双介质可比，或蜂窝不劣于 wifi」 was one row for both readings,
    and 12 of the 15 times it appeared, nothing had been compared (D-229).

    The invariant ties the machine's severity to the words the reader sees:
    a row says 未核算 exactly when the gate calls it N/A. Either half can drift
    on its own — a PASS whose text admits it checked nothing, or an N/A phrased
    like a clean result — so the biconditional is what gets asserted.
    """
    from test_report_properties import _corrupt_corpus, _random_corpus

    corpora = [("chaos", _corrupt_corpus())]
    corpora += [(f"seed{s}", _random_corpus(s)) for s in range(20)]

    na_rows, na_items = 0, set()
    for tag, recs in corpora:
        for r in pc.check(recs):
            assert ("未核算" in r["detail"]) == (r["severity"] == pc.NA), (
                f"{tag}/{r['item']}: severity {r['severity']} on detail "
                f"{r['detail']!r} — 未核算 and N/A have to mean each other")
            if r["severity"] == pc.NA:
                na_rows += 1
                na_items.add(r["item"])

    # Floors, not counts: measured 27 N/A rows over 5 items on these corpora
    # (介质效应量 12, 层级同时性 11, 效应量 2, 同一接入 1, 层级对账 1). The other
    # two N/A branches are unreachable from random corpora and are pinned in
    # test_no_usable_cell_is_not_sufficient_sampling / test_unlabelled_corpus_fails.
    assert na_rows >= 20, f"only {na_rows} N/A rows — the branches stopped being reached"
    assert len(na_items) >= 4, f"N/A seen on {sorted(na_items)} only"


_UNJUDGEABLE = ("噪声内", "判不了", "噪声不可估")
_BEYOND = re.compile(r"(\d+)/(\d+) 个负 Δ 超出噪声尺度")
_ALL_NOISY = re.compile(r"^(\d+) 个格 Δ\(cellular−wifi\) 为负")


def _counted_in_transport_table(recs):
    """(negative Δ rows, of which beyond noise) — counted the way a reader would,
    off the rendered section rather than off the analysis dict."""
    import transport_rollup

    md = transport_rollup.render_markdown(transport_rollup.analyze(recs))
    neg = real = 0
    for line in md.splitlines():
        if not line.startswith("| ") or line.startswith("| 点位"):
            continue
        if set(line) <= set("|- "):                       # the |---|---| rule row
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 9:
            continue
        delta, note = cells[5], cells[7]
        if delta.startswith("-") and delta != "—":
            neg += 1
            if not any(m in note for m in _UNJUDGEABLE):
                real += 1
    return neg, real


def test_the_gate_figure_can_be_counted_in_the_transport_table():
    """The README promises 「`publish_check` 的「介质效应量」项与本段共用同一判据，
    不会分歧」 and nothing checked it — a stated premise with nothing standing
    behind it is how D-216 got in (D-230).

    The gate prints 「N/M 个负 Δ 超出噪声尺度」; the section renders one row per
    cell. A reader who counts the table has to reach the same N and M. Both
    numbers travel through independent renderings, so a criterion that drifts on
    either side lands here.
    """
    from test_report_properties import _corrupt_corpus, _random_corpus

    corpora = [("chaos", _corrupt_corpus())]
    corpora += [(f"seed{s}", _random_corpus(s)) for s in range(20)]
    # Measured: 6 random corpora carry a figure and every one of them is 0/M.
    # Without these two the guard would only ever check the half where the
    # section has no finding to show.
    corpora += [
        ("media-beyond", _media({"P1": ([80, 82, 84, 86, 88], [50, 52, 54, 56, 58])})),
        ("media-unknown", _media({"P1": ([80, 82, 84, 86, 88], [50, 52, 54, 56, 58]),
                                  "P2": ([80, 82, 84, 86, 88], [60])})),
    ]

    checked, with_finding = 0, 0
    for tag, recs in corpora:
        detail = _detail(pc.check(recs), "介质效应量")
        m, m2 = _BEYOND.search(detail), _ALL_NOISY.match(detail)
        if m:
            gate = (int(m.group(2)), int(m.group(1)))     # (negative, beyond noise)
        elif m2:
            gate = (int(m2.group(1)), 0)
        else:
            continue                                      # N/A row: no figure to check
        checked += 1
        if gate[1]:
            with_finding += 1
        counted = _counted_in_transport_table(recs)
        assert gate == counted, (
            f"{tag}: the gate says {detail[:44]!r} while the section table counts "
            f"{counted} (negative rows, of which beyond noise)")

    assert checked >= 6, f"only {checked} corpora carried a figure to check"
    assert with_finding >= 1, "the half where the section shows a real finding was never reached"
