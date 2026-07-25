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


def test_effect_within_noise_is_warn():
    """A round whose every Δ sits inside the noise must not ship as 'improved'."""
    rows = pc.check(_two_campaigns([60, 70, 80, 90, 100], [62, 72, 82, 92, 102]))
    assert _sev(rows, "效应量") == pc.WARN
    assert "不得表述为改善或回退" in _detail(rows, "效应量")


def test_effect_beyond_noise_passes():
    rows = pc.check(_two_campaigns([60, 70, 80, 90, 100], [110, 120, 130, 140, 150]))
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
