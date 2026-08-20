# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/transport_rollup.py (wifi vs cellular)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import transport_rollup as tr
from synth import aqs_records


def _recs(transport, aqs, n, *, point="P1"):
    out = aqs_records(aqs, n, point=point)
    for r in out:
        r["run"]["transport"] = transport
    return out


def _observed(rec, *transports):
    rec["run"]["transport"] = "auto"
    rec["scenarios"] = [{"profile_id": "s1_chat", "network_snapshot": {"transport": t},
                         "validity": "valid", "invalid_reasons": "", "kpi": {}}
                        for t in transports]
    return rec


def _spread(transport, values, *, point="P1"):
    """One record per value so the bucket has real spread."""
    return [r for v in values for r in _recs(transport, v, 1, point=point)]


def test_small_media_delta_is_marked_as_noise():
    """D-144 gave the before/after delta a noise scale; this section differences
    two medians the same way and never got one. On the rehearsal grid all seven
    cells the summary called "cellular worse than wifi" sat inside the noise — a
    flat claim in the section decision-makers actually read (D-180)."""
    recs = (_spread("wifi", [60, 70, 80, 90, 100])
            + _spread("cellular", [58, 68, 78, 88, 98]))
    c = tr.analyze(recs)["cells"][0]
    assert c["cellular_minus_wifi"] == -2
    assert c["noise"] > 2
    assert c["within_noise"] is True
    md = tr.render_markdown(tr.analyze(recs))
    assert "**噪声内**" in md
    assert "不是显著性检验" in md          # the caveat, not just the number


def test_real_media_delta_still_gets_through():
    """Negative verification: the guard must not swallow a genuine difference."""
    recs = (_spread("wifi", [60, 70, 80, 90, 100])
            + _spread("cellular", [10, 20, 30, 40, 50]))
    c = tr.analyze(recs)["cells"][0]
    assert c["cellular_minus_wifi"] == -50
    assert c["within_noise"] is False
    # …and one sample per side resolves nothing: not False, not 0
    one = tr.analyze(_recs("wifi", 80, 1) + _recs("cellular", 60, 1))["cells"][0]
    assert one["cellular_minus_wifi"] == -20
    assert one["noise"] is None
    assert one["within_noise"] is None


def test_resolve_explicit_setting_wins():
    assert tr.resolve_transport(_recs("wifi", 90, 1)[0]) == "wifi"
    assert tr.resolve_transport(_recs("CELLULAR", 90, 1)[0]) == "cellular"


def test_resolve_real_producer_compound_format():
    """Real corpus writes run.transport = "auto(cellular)" — the resolved medium
    in parentheses must win (observed on server/data/results, D-110)."""
    assert tr.resolve_transport(_recs("auto(cellular)", 90, 1)[0]) == "cellular"
    assert tr.resolve_transport(_recs("auto(wifi)", 90, 1)[0]) == "wifi"
    assert tr.resolve_transport(_recs("auto(vpn)", 90, 1)[0]) == "unknown"


def test_resolve_auto_uses_observed_consensus():
    assert tr.resolve_transport(_observed(_recs("auto", 90, 1)[0], "cellular", "cellular")) \
        == "cellular"


def test_resolve_auto_disagreement_is_mixed_not_a_medium():
    assert tr.resolve_transport(_observed(_recs("auto", 90, 1)[0], "wifi", "cellular")) \
        == "mixed"


def test_resolve_no_observation_is_unknown():
    assert tr.resolve_transport(_recs("auto", 90, 1)[0]) == "unknown"


def test_delta_cellular_minus_wifi():
    recs = _recs("wifi", 90, 5) + _recs("cellular", 82, 5)
    c = tr.analyze(recs)["cells"][0]
    assert c["transports"]["wifi"]["aqs_median"] == 90
    assert c["transports"]["cellular"]["aqs_median"] == 82
    assert c["cellular_minus_wifi"] == -8          # negative = cellular worse


def test_single_medium_has_no_delta():
    c = tr.analyze(_recs("wifi", 90, 5))["cells"][0]
    assert c["cellular_minus_wifi"] is None


def test_unknown_bucket_not_merged():
    recs = _recs("wifi", 90, 5) + _recs("auto", 40, 5)   # auto+no obs -> unknown
    c = tr.analyze(recs)["cells"][0]
    assert c["transports"]["wifi"]["aqs_median"] == 90   # 40s stayed out of wifi
    assert c["transports"]["unknown"]["n"] == 5


def test_low_confidence_per_transport():
    recs = _recs("wifi", 90, 5) + _recs("cellular", 82, 2)
    c = tr.analyze(recs)["cells"][0]
    assert c["transports"]["wifi"]["low_confidence"] is False
    assert c["transports"]["cellular"]["low_confidence"] is True


def test_markdown_renders_delta_and_caveat():
    md = tr.render_markdown(tr.analyze(_recs("wifi", 90, 5) + _recs("cellular", 82, 5)))
    assert "接入介质对比" in md
    assert "-8" in md
    assert "蜂窝更差" in md


def test_all_unknown_renders_coverage_gap_not_table():
    md = tr.render_markdown(tr.analyze(_recs("auto", 90, 3)))
    assert "无 transport 证据" in md
    assert "|" not in md.split("覆盖缺口")[1]      # no data table after the note


# The two ways a run ends up outside both media. 「不一致=mixed、无观测=unknown，
# **均不并入任何介质**」 names both, and only unknown had the pooling half
# checked — mixed was pinned one step earlier, at resolve_transport, where a run
# can be labelled right and still be pooled wrong (D-235).
_NOT_A_MEDIUM = {
    "unknown": lambda: _recs("auto", 40, 5),                      # auto, nothing observed
    "mixed": lambda: [_observed(r, "wifi", "cellular")            # auto, observers disagree
                      for r in _recs("auto", 40, 5)],
}


def test_no_bucket_outside_the_two_media_is_pooled_into_one():
    """A run whose medium is mixed or unknown must land in its own bucket and
    leave the wifi/cellular medians exactly where they were — 40s pooled into a
    90 wifi cell is a medium comparison drawn from runs nobody could place."""
    assert set(tr.EXPLICIT) == {"wifi", "cellular"}, (
        f"EXPLICIT is now {tr.EXPLICIT} — a third medium needs its own row here")

    for name, build in _NOT_A_MEDIUM.items():
        cells = tr.analyze(_recs("wifi", 90, 5) + build())["cells"]
        assert len(cells) == 1, (name, len(cells))
        buckets = cells[0]["transports"]
        # membership first: indexing a bucket that pooling made disappear raises
        # KeyError, and a guard that crashes reports nothing (D-220)
        assert name in buckets, (
            f"{name}: no such bucket — the 5 unplaceable runs went somewhere "
            f"else entirely (buckets: {sorted(buckets)})")
        assert buckets[name]["n"] == 5, (
            f"{name}: the 5 unplaceable runs did not land in their own bucket")
        assert buckets["wifi"]["aqs_median"] == 90, (
            f"{name}: pooled into wifi — its median moved to "
            f"{buckets['wifi']['aqs_median']}")
        assert "cellular" not in buckets, (
            f"{name}: pooled into cellular, a medium this corpus never measured")


def test_aborted_run_aqs_stays_out_of_the_transport_median():
    """D-534 SS3: an aborted run's run-level AQS does not pool here either.

    This site had no targeted guard until a mutation run showed that removing
    `cc.run_pools_into_stats` turned only the campaign_report tests red -- the
    transport and trend gates could have been deleted in silence.

    The numbers are chosen so the gate is visible: three completed runs at 100
    and three aborted at 0. Gate on -> median 100. Gate off -> median 50.
    `n` counts records either way (6): it has always been allowed to exceed the
    pool, exactly as it does when an AQS is null.
    """
    recs = _recs("wifi", 100, 3)
    bad = _recs("wifi", 0, 3)
    for r in bad:
        r["run"]["status"] = "aborted:timeout"
    wifi = tr.transport_cells(recs + bad)[0]["transports"]["wifi"]
    assert wifi["aqs_median"] == 100
    assert wifi["n"] == 6
