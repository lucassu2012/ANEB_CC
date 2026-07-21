# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/validity_rollup.py.

Central claim under test: the rollup must expose the ATTEMPTED denominator, so a
median resting on a small surviving subset is visible rather than implied.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import validity_rollup as vr
from synth import validity_records, make_record


def test_all_valid_cell():
    res = vr.analyze(validity_records(5, validity="valid"))
    c = res["cells"][0]
    assert c["attempted"] == 5
    assert c["valid"] == 5
    assert c["valid_rate"] == 1.0
    assert c["below_min_rate"] is False
    assert res["overall_valid_rate"] == 1.0


def test_survivor_denominator_is_exposed():
    """4 valid out of 40 attempts: the heat card would only ever show n=4."""
    recs = (validity_records(4, validity="valid")
            + validity_records(36, validity="invalid", invalid_reasons="timeout"))
    c = vr.analyze(recs)["cells"][0]
    assert c["attempted"] == 40
    assert c["valid"] == 4
    assert c["invalid"] == 36
    assert c["valid_rate"] == 0.1
    assert c["below_min_rate"] is True


def test_low_confidence_counts_as_usable():
    """VALID_LOW_CONFIDENCE still produced a measurement -> usable, but tracked."""
    recs = (validity_records(3, validity="valid")
            + validity_records(2, validity="VALID_LOW_CONFIDENCE"))
    c = vr.analyze(recs)["cells"][0]
    assert c["valid"] == 3
    assert c["valid_low_confidence"] == 2
    assert c["valid_rate"] == 1.0
    assert c["invalid"] == 0


def test_unknown_validity_is_its_own_bucket_not_assumed_valid():
    recs = validity_records(4, validity="something_else")
    c = vr.analyze(recs)["cells"][0]
    assert c["unknown"] == 4
    assert c["valid"] == 0
    assert c["valid_rate"] == 0.0      # not silently treated as valid


def test_invalid_reasons_histogram():
    recs = (validity_records(3, validity="invalid", invalid_reasons="timeout")
            + validity_records(2, validity="invalid", invalid_reasons="parse_error;timeout"))
    res = vr.analyze(recs)
    assert res["corpus_reasons"]["timeout"] == 5
    assert res["corpus_reasons"]["parse_error"] == 2


def test_reason_splitting_handles_separators():
    recs = validity_records(1, validity="invalid", invalid_reasons="a;b,c|d")
    assert vr.analyze(recs)["corpus_reasons"] == {"a": 1, "b": 1, "c": 1, "d": 1}


def test_blank_reasons_produce_no_tokens():
    recs = validity_records(3, validity="valid", invalid_reasons="")
    assert vr.analyze(recs)["corpus_reasons"] == {}


def test_cells_separated_per_profile_and_point():
    recs = (validity_records(5, validity="valid", point="P1", profile="s1_chat")
            + validity_records(5, validity="invalid", point="P1", profile="s2_rag")
            + validity_records(5, validity="valid", point="P2", profile="s1_chat"))
    res = vr.analyze(recs)
    by = {(c["cell"]["point_id"], c["cell"]["profile_id"]): c for c in res["cells"]}
    assert by[("P1", "s1_chat")]["valid_rate"] == 1.0
    assert by[("P1", "s2_rag")]["valid_rate"] == 0.0
    assert by[("P2", "s1_chat")]["valid_rate"] == 1.0


def test_no_scenarios_yields_no_cells_not_zero_rate():
    res = vr.analyze([make_record(scenarios=[]) for _ in range(3)])
    assert res["cells"] == []
    assert res["overall_valid_rate"] is None      # not 0.0


def test_trend_groups_by_utc_day():
    recs = validity_records(4, validity="valid")
    res = vr.analyze(recs)
    assert len(res["trend"]) == 1
    assert res["trend"][0]["day"] == "2026-07-13"   # 1783944000000 ms UTC
    assert res["trend"][0]["usable"] == 4


def test_markdown_renders_denominator_note():
    md = vr.render_markdown(vr.analyze(
        validity_records(4, validity="valid")
        + validity_records(36, validity="invalid", invalid_reasons="timeout")))
    assert "有效样本分母" in md
    assert "LOW_VALID_RATE" in md
    assert "timeout" in md
