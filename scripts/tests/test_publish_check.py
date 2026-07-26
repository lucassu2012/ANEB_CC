# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/publish_check.py.

The severity split is the whole point: FAIL is for things a machine can be sure
are wrong (blocks publication), WARN is for things that need a human to explain.
A WARN must never be silently upgraded to PASS, and "cannot judge" must never
read as "no problem".
"""
import os
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


def test_verdict_wording_states_the_warn_contract():
    md_fail = pc.render_markdown(pc.check([]))
    assert "不可发布" in md_fail
    md_ok = pc.render_markdown(pc.check(_clean()))
    assert "可发布" in md_ok
    assert "不可发布" not in md_ok
    assert "须由人解释" in md_ok


def test_rows_sorted_most_severe_first():
    sev = [r["severity"] for r in pc.check(sc.generate(**SYNTH_SMALL))]
    rank = {pc.FAIL: 0, pc.WARN: 1, pc.PASS: 2}
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
    be told apart from a check that was forgotten (D-150)."""
    recs = [contractify(r) for r in aqs_records(90, 5, campaign_id="base")]
    assert _sev(pc.check(recs), "效应量") == pc.PASS
    assert "无前后对比可核算" in _detail(pc.check(recs), "效应量")


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
    single = [contractify(r) for r in aqs_records(90, 5, campaign_id="base")]
    multi = _two_campaigns([70, 72, 74, 71, 73], [80, 82, 84, 81, 83])
    items_single = {r["item"] for r in pc.check(single)}
    items_multi = {r["item"] for r in pc.check(multi)}
    assert items_single == items_multi, items_single ^ items_multi


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


def test_uncheckable_premise_is_stated_not_omitted():
    """"Same client" is not merely unchecked — the contract carries no device
    identity at all, so it is uncheckable. Saying nothing would let a reader
    assume it held (D-156)."""
    rows = pc.check(_clean())
    assert _sev(rows, "同一客户端") == pc.WARN
    assert "无法核对" in _detail(rows, "同一客户端")
    # …and it must be a WARN on every corpus, since nothing can ever clear it
    for corpus in (_clean(), _two_campaigns([70, 72, 74], [80, 82, 84])):
        assert _sev(pc.check(corpus), "同一客户端") == pc.WARN


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
