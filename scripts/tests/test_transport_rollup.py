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
