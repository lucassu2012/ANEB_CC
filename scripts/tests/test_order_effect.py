# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/order_effect.py.

Pins the diagnostic's core claim: a NULL result (no suspected effect) must mean
"counterbalancing worked", never "we couldn't tell". Every un-decidable case is
required to report itself as un-decidable instead.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import order_effect as oe
from synth import order_records, make_record


def test_no_order_effect_when_positions_agree():
    """Same KPI at both positions -> counterbalancing worked (the good null)."""
    recs = (order_records(5, value=100, order_index=0)
            + order_records(5, value=100, order_index=1))
    p = oe.analyze(recs)["profiles"][0]
    assert p["spread"] == 0
    assert p["spread_pct"] == 0
    assert p["order_effect_suspected"] is False
    assert p["low_confidence"] is False


def test_order_effect_detected_when_position_matters():
    """1st position 100ms, 2nd 140ms -> spread well over the 10% threshold."""
    recs = (order_records(5, value=100, order_index=0)
            + order_records(5, value=140, order_index=1))
    p = oe.analyze(recs)["profiles"][0]
    assert p["spread"] == 40
    assert round(p["spread_pct"], 1) == 33.3      # 40 / median(120) * 100
    assert p["order_effect_suspected"] is True


_FAST, _SLOW = 40.0, 120.0
_ROT = "s1_chat,s2_rag|s2_rag,s1_chat"


def _cell_skewed(**kw):
    """Position #0 fed only by a fast point, #1 only by a slow one. Inside each
    point every position reads the same value, so there is NO order effect at
    all — only a difference in which cell supplied which position."""
    return (order_records(5, value=_FAST, order_index=0, point="P-fast", **kw)
            + order_records(5, value=_SLOW, order_index=1, point="P-slow", **kw))


def test_a_cell_effect_is_not_reported_as_an_order_effect():
    """analyze() pools every cell into one per-profile comparison, on purpose:
    sample size is the point. But pooling has a premise — that each position
    drew on the same cells — and nothing checked it. A two-point corpus with no
    order effect whatsoever came out as 疑似序位偏倚 at spread_pct 100.0 with
    '—' in the 备注 column (D-335).

    scenario_order rotates here on purpose: the corpus that first showed this
    also tripped the 未轮转 warning, which could be mistaken for a caveat — but
    that warning fires on a perfectly counterbalanced corpus too, so it
    discriminates nothing. Rotating removes the alternative explanation.

    The raw statistic still says what it measured; it is the VERDICT that must
    not claim attribution the numbers cannot support (§2.12).
    """
    res = oe.analyze(_cell_skewed(scenario_order=_ROT), kpi="t1_ttft_ms")
    assert res["rotation_warning"] is False, "otherwise this proves nothing"
    p = res["profiles"][0]
    assert p["order_effect_suspected"] is True         # the measurement stands
    assert p["position_cell_imbalance"] is True
    assert p["position_cells_uneven"], "the flag must carry its own evidence"
    md = oe.render_markdown(res)
    assert "不可单独归因" in md
    assert "CELL_CONFOUNDED" in md
    assert "**疑似序位偏倚**" not in md, "a confounded row must not claim a verdict"
    # …and above the table, not only inside a 备注 cell. Asserted present here
    # because the balanced test only asserts it ABSENT, and a mutation that
    # deleted the section line outright survived on that pair alone (D-335).
    assert "单元不平衡" in md, "the premise has to be stated above the table too"


def test_a_counterbalanced_two_cell_corpus_is_not_flagged():
    """The half that matters. A premise check that fires on a correct corpus is
    worse than none — everyone learns to ignore it. Same two points, but each
    one feeds BOTH positions."""
    recs = (order_records(5, value=_FAST, order_index=0, point="P-fast", scenario_order=_ROT)
            + order_records(5, value=_FAST, order_index=1, point="P-fast", scenario_order=_ROT)
            + order_records(5, value=_SLOW, order_index=0, point="P-slow", scenario_order=_ROT)
            + order_records(5, value=_SLOW, order_index=1, point="P-slow", scenario_order=_ROT))
    res = oe.analyze(recs, kpi="t1_ttft_ms")
    p = res["profiles"][0]
    assert p["position_cell_imbalance"] is False
    assert p["position_cells_uneven"] == []
    assert p["order_effect_suspected"] is False
    md = oe.render_markdown(res)
    assert "CELL_CONFOUNDED" not in md
    assert "单元不平衡" not in md


def test_one_position_cannot_be_called_balanced():
    """With a single position there is nothing to compare, and R-10 forbids
    calling that 'fine': False would let publish_check count it as a premise
    that held."""
    recs = order_records(5, value=_FAST, order_index=0, point="P-fast")
    p = oe.analyze(recs, kpi="t1_ttft_ms")["profiles"][0]
    assert p["position_cell_imbalance"] is None
    assert p["position_cells_uneven"] == []


def test_threshold_is_configurable():
    recs = (order_records(5, value=100, order_index=0)
            + order_records(5, value=112, order_index=1))
    assert oe.analyze(recs, threshold_pct=5)["profiles"][0]["order_effect_suspected"] is True
    assert oe.analyze(recs, threshold_pct=50)["profiles"][0]["order_effect_suspected"] is False


def test_single_position_not_computable_not_no_effect():
    """One position can never prove absence of an order effect."""
    p = oe.analyze(order_records(5, value=100, order_index=0))["profiles"][0]
    assert p["order_effect_suspected"] is None          # NOT False
    assert p["not_computable_reason"] == "NEED_2_POSITIONS"
    assert p["low_confidence"] is True


def test_one_sample_per_position_is_not_a_verdict():
    """D-354, measured on the FIRST real forensic corpus: one run rotates three
    orders, so every profile has three positions holding exactly one sample each.
    The spread between those positions IS the run-to-run noise — there is no
    within-position variability to judge it against — yet the threshold fired and
    the summary announced 「疑似序位偏倚 8/9 … 本报告的 KPI 中位数据此存疑」, putting the
    whole report's medians in doubt on a comparison that cannot discriminate.

    Same arithmetic floor the stability section applies to CV (needs n>=2). The
    `low_confidence` flag was already true and did not help: flagging a verdict
    is not the same as declining to issue one (D-313).

    The other half is pinned too — replicated positions with a real spread must
    still be called out, or this fix would have silenced the check.
    """
    single = oe.analyze_profile({0: [50.0], 5: [52.7], 7: [39.0]})
    assert single["order_effect_suspected"] is None, single
    assert single["not_computable_reason"] == "UNREPLICATED_POSITIONS"
    assert single["spread_pct"] > 10, "the spread is still reported, just not judged"

    replicated = oe.analyze_profile({0: [50.0, 51.0], 5: [52.7, 53.0], 7: [39.0, 38.5]})
    assert replicated["order_effect_suspected"] is True, replicated
    assert replicated["not_computable_reason"] is None


def test_summary_names_the_real_reason_it_could_not_judge():
    """The summary used to pick between two reasons with an if/else, so a third
    one printed a FALSE explanation: 「各 profile 在场位次不足 2」 about profiles that
    had three positions and no replication inside them. The reason now comes out
    of the analysis instead of being guessed (D-354)."""
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
    s = oe.summarize([rec])
    assert s["judged"] == 0 and not s["biased"]
    assert s["unjudged_reasons"] == {"UNREPLICATED_POSITIONS": 1}, s["unjudged_reasons"]


def test_low_confidence_below_sample_floor():
    recs = (order_records(2, value=100, order_index=0)
            + order_records(2, value=100, order_index=1))
    p = oe.analyze(recs)["profiles"][0]
    assert p["low_confidence"] is True
    assert p["order_effect_suspected"] is False        # still computable


def test_near_zero_median_makes_pct_undefined_not_infinite():
    recs = (order_records(5, value=0, order_index=0)
            + order_records(5, value=0, order_index=1))
    p = oe.analyze(recs)["profiles"][0]
    assert p["spread_pct"] is None
    assert p["order_effect_suspected"] is None
    assert p["not_computable_reason"] == "MEDIAN_NEAR_ZERO"


def test_rotation_warning_when_order_never_rotated():
    """Same scenario_order everywhere = the Latin square was never rotated."""
    recs = (order_records(5, value=100, order_index=0, scenario_order="s1,s2")
            + order_records(5, value=100, order_index=1, scenario_order="s1,s2"))
    res = oe.analyze(recs)
    assert res["distinct_orders"] == 1
    assert res["rotation_warning"] is True
    assert "未轮转" in oe.render_markdown(res)


def test_no_rotation_warning_when_rotated():
    recs = (order_records(5, value=100, order_index=0, scenario_order="s1,s2")
            + order_records(5, value=100, order_index=1, scenario_order="s2,s1"))
    res = oe.analyze(recs)
    assert res["distinct_orders"] == 2
    assert res["rotation_warning"] is False


def test_absent_order_evidence_reported():
    recs = [make_record(scenarios=[("s1_chat", {"t1_ttft_ms": 100})]) for _ in range(3)]
    res = oe.analyze(recs)
    assert res["no_order_evidence"] is True
    assert "无 `run.scenario_order` 证据" in oe.render_markdown(res)


def test_per_profile_separation():
    """Two profiles must be judged independently, not pooled."""
    recs = (order_records(5, value=100, order_index=0, profile="s1_chat")
            + order_records(5, value=100, order_index=1, profile="s1_chat")
            + order_records(5, value=100, order_index=0, profile="s2_rag")
            + order_records(5, value=200, order_index=1, profile="s2_rag"))
    by = {p["profile_id"]: p for p in oe.analyze(recs)["profiles"]}
    assert by["s1_chat"]["order_effect_suspected"] is False
    assert by["s2_rag"]["order_effect_suspected"] is True


def test_markdown_renders():
    recs = (order_records(5, value=100, order_index=0)
            + order_records(5, value=140, order_index=1))
    md = oe.render_markdown(oe.analyze(recs))
    assert "序位效应诊断" in md
    assert "疑似序位偏倚" in md


def _ordered_rec(order):
    from synth import make_record
    r = make_record(campaign={"campaign_id": "base", "tier": "metro", "point_id": "P1",
                              "carrier": "cmcc", "time_band": "busy"},
                    aqs=80, scenarios=[("s1_chat", {"t1_ttft_ms": 100})])
    r["run"]["scenario_order"] = order
    return r


def test_rotation_within_a_run_is_not_a_missing_rotation():
    """`scenario_order` is round-structured — the contract's own example is
    "s1,s2,s3|s2,s3,s1". Comparing whole strings flagged a forensic corpus whose
    every run rotates internally as 拉丁方未轮转: a false alarm on exactly the
    corpus that DID counterbalance (D-164)."""
    recs = [_ordered_rec("s1,s2,s3|s2,s3,s1|s3,s1,s2") for _ in range(6)]
    res = oe.analyze(recs, kpi="t1_ttft_ms")
    assert res["distinct_rounds"] == 3
    assert res["rotates_within_run"] == 6
    assert res["rotation_warning"] is False
    md = oe.render_markdown(res)
    assert "未轮转" not in md
    assert "在自身内部**已轮转" in md


def test_one_round_everywhere_still_warns():
    recs = [_ordered_rec("s1,s2,s3") for _ in range(6)]
    res = oe.analyze(recs, kpi="t1_ttft_ms")
    assert res["distinct_rounds"] == 1
    assert res["rotation_warning"] is True
    assert "未轮转" in oe.render_markdown(res)


def test_rotation_across_runs_still_counts():
    recs = ([_ordered_rec("s1,s2,s3") for _ in range(3)]
            + [_ordered_rec("s2,s3,s1") for _ in range(3)])
    res = oe.analyze(recs, kpi="t1_ttft_ms")
    assert res["distinct_rounds"] == 2
    assert res["rotation_warning"] is False
    assert res["rotates_within_run"] == 0      # rotation is across runs, not within
