# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/trend.py (N-campaign longitudinal trend).

Pins: chronological ordering by started_at (not id sort), polarity-correct
improving/regressing, non-monotonic paths reported as 'mixed' not a false trend,
and missing-campaign gaps left as None rather than interpolated.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import trend
from synth import aqs_records, kpi_scenario_records


# A real epoch, and real spread. Both became load-bearing at D-196:
#   * started_ms used to be 1000/2000/3000 — 1970 — which the epoch-magnitude
#     check now refuses to order by, because a number that is not a time must not
#     decide which round came first (D-176's rule, extended to the >=3 path).
#   * every record carried the SAME aqs, so the cell's spread was 0 — and zero
#     observed spread resolves nothing (D-169), so no direction may be claimed.
# A fixture that cannot occur in the field cannot exercise the verdicts either.
_EPOCH = 1783944000000          # 2026-07-13T12:00:00Z
_DAY = 86400000
_SPREAD = (-4, -2, 0, 2, 4)     # sd ~ 3.16 around the target median


def _camp(aqs, cid, started_ms, *, n=5, point="P1", carrier="cmcc", time_band="busy"):
    """n records for one campaign, centred on `aqs`, with a real repeat spread.

    Callers keep their toy `started_ms` scale; it is mapped onto a plausible
    epoch here, preserving the ORDER each caller intends."""
    ms = _EPOCH + int(started_ms) * _DAY // 1000
    out = []
    for i in range(n):
        out += aqs_records(aqs + _SPREAD[i % len(_SPREAD)], 1, point=point,
                           carrier=carrier, time_band=time_band,
                           campaign_id=cid, started_ms=ms)
    return out


def test_three_campaign_improving_aqs():
    recs = (_camp(60, "c1", 1000) + _camp(72, "c2", 2000) + _camp(85, "c3", 3000))
    res = trend.analyze(recs)
    assert res["campaigns"] == ["c1", "c2", "c3"]
    c = res["cells"][0]
    assert c["trajectory"] == [60, 72, 85]
    assert c["first_last_delta"] == 25
    assert c["direction"] == "improving"     # AQS higher=better
    assert c["monotonic"] is True


def test_ordering_is_chronological_not_id_sort():
    """c_zzz ran first, c_aaa last: order must follow time, not the id string."""
    recs = (_camp(50, "c_zzz", 1000) + _camp(90, "c_aaa", 5000))
    assert trend.analyze(recs)["campaigns"] == ["c_zzz", "c_aaa"]


def test_explicit_order_overrides():
    recs = (_camp(50, "c1", 1000) + _camp(90, "c2", 2000))
    res = trend.analyze(recs, order=["c2", "c1"])
    assert res["campaigns"] == ["c2", "c1"]
    assert res["cells"][0]["trajectory"] == [90, 50]


def test_regressing_aqs():
    recs = (_camp(85, "c1", 1000) + _camp(60, "c2", 2000))
    assert trend.analyze(recs)["cells"][0]["direction"] == "regressing"


def test_latency_polarity_lower_is_better():
    """For n1_rtt, a DECREASE is an improvement (equal ts -> id tie-break c1<c2)."""
    # real spread per campaign, or the delta has no noise scale and no direction
    # may be claimed at all (D-169/D-196)
    def rtt(base, cid):
        out = []
        for off in (-4, -2, 0, 2, 4):
            out += kpi_scenario_records(1, kpi={"n1_rtt_p50_ms": base + off},
                                        campaign_id=cid)
        return out
    recs = rtt(80, "c1") + rtt(40, "c2")
    res = trend.analyze(recs, metric="n1_rtt_p50_ms")
    assert res["campaigns"] == ["c1", "c2"]
    c = res["cells"][0]
    assert c["first_last_delta"] == -40
    assert c["direction"] == "improving"     # lower latency = better


def test_non_monotonic_is_mixed_not_false_trend():
    recs = (_camp(60, "c1", 1000) + _camp(90, "c2", 2000) + _camp(65, "c3", 3000))
    c = trend.analyze(recs)["cells"][0]
    assert c["monotonic"] is False
    assert c["direction"] == "mixed"         # net +5 but dipped -> not "improving"


def test_missing_campaign_gap_not_interpolated():
    recs = (_camp(60, "c1", 1000, point="P1") + _camp(80, "c3", 3000, point="P1")
            + _camp(70, "c2", 2000, point="P2"))   # P1 absent from c2
    res = trend.analyze(recs)
    assert res["campaigns"] == ["c1", "c2", "c3"]
    p1 = next(c for c in res["cells"] if c["cell"]["point_id"] == "P1")
    assert p1["trajectory"] == [60, None, 80]      # gap, not 70
    assert p1["present_count"] == 2
    assert p1["first_last_delta"] == 20            # first/last PRESENT points


def test_single_present_point_not_computable():
    recs = (_camp(60, "c1", 1000, point="P1")
            + _camp(70, "c2", 2000, point="P2"))   # each cell in one campaign only
    p1 = next(c for c in trend.analyze(recs)["cells"] if c["cell"]["point_id"] == "P1")
    assert p1["direction"] is None
    assert p1["not_computable_reason"] == "NEED_2_POINTS"


def test_single_campaign_renders_guidance():
    res = trend.analyze(_camp(80, "c1", 1000))
    assert len(res["campaigns"]) == 1
    md = trend.render_markdown(res)
    assert f"少于 {trend.MIN_CAMPAIGNS_FOR_TREND} 个战役" in md
    # …and points at the section that DOES answer the two-campaign case, which is
    # the one with a noise scale on its delta (D-196)
    assert "优化前后" in md


def test_low_confidence_flagged():
    recs = (_camp(60, "c1", 1000, n=2) + _camp(80, "c2", 2000, n=2))
    assert trend.analyze(recs)["cells"][0]["low_confidence"] is True


def test_markdown_renders_trajectory():
    recs = (_camp(60, "c1", 1000) + _camp(72, "c2", 2000) + _camp(85, "c3", 3000))
    md = trend.render_markdown(trend.analyze(recs))
    assert "纵向趋势" in md
    assert "改善" in md
    assert "c1 → c2 → c3" in md


def test_aborted_run_aqs_stays_out_of_the_trajectory():
    """D-534 §3：中止 run 的 run 级 AQS 不进趋势轨迹。

    这处**此前一条针对性守卫都没有**——突变实测显示，把
    `cc.run_pools_into_stats` 删掉只会让 campaign_report 那两条变红，
    trend 与 transport_rollup 的判据可以被无声移除。

    夹具刻意让判据决定的是一个**判词**而不只是一个数字：c2 除五条真实的 72 分
    之外再塞五条 10 分的中止 run。判据在 → 轨迹 60/72/85，读作 improving+单调；
    判据没了 → c2 塌到 ~41，同一份语料读作 mixed——
    **一条中止的 run 会凭空造出一段本不存在的回退**。

    只扣住 run 级 AQS：场景级 metric 走 `_record_values` 的另一支，一字未动，
    这正是横幅对「中止 run 的已完成场景」所作的承诺。
    """
    aborted = _camp(10, "c2", 2000)
    for r in aborted:
        r["run"]["status"] = "aborted:timeout"
    recs = (_camp(60, "c1", 1000) + _camp(72, "c2", 2000) + aborted
            + _camp(85, "c3", 3000))
    c = trend.analyze(recs)["cells"][0]
    assert c["trajectory"] == [60, 72, 85]
    assert c["direction"] == "improving"
    assert c["monotonic"] is True
