# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/validate_results.py.

A schema-complete valid record is built in-test, then each test breaks exactly
one thing and asserts the corresponding error — with special attention to the
R-10 cross-field invariants draft-07 cannot express, and to the known
schema/producer validity CASE drift being an advisory, not a gate failure.
"""
import copy
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import validate_results as vd

SCH = vd.load_schema(vd.DEFAULT_SCHEMA)


def _valid_kpi():
    kpi = {"seq_gap_count": 0, "seq_dup_count": 0}
    for k in ("t1_ttft_ms", "t2_itl_p95_ms", "t3_stall_rate", "t4_severe_stall_rate",
              "n1_rtt_p50_ms", "n2_jitter_ms", "u1_goodput_mbps", "u2_tool_loop_p95_ms"):
        kpi[k] = 10.0
        kpi[k.split("_")[0] + "_grade"] = "good"
    return kpi


def _valid_record():
    """A fully schema-complete, R-10-consistent record (validity UPPER = no advisory)."""
    return {
        "claim_scope": "application_end_to_end_to_probe_node",
        "kpi_set": "agent-qoe-kpi-v0.1", "aqs_version": "aqs-v0.1",
        "profile_versions": "s1@0.2", "schema_version": "1.0",
        "run": {
            "run_id": "0198a7b0-0000-7000-8000-000000000001",
            "started_at_epoch_ms": 1783944000000, "mode": "quick", "scenario_order": "s1",
            "transport": "cellular", "profile_source": "server", "app_version_name": "1.0",
            "app_version_code": 1, "guard_metadata": None, "status": "completed",
            "aqs": {"score": 90.0, "low_confidence": False, "veto_applied": False,
                    "not_computable_reason": None, "input_mapping": "m", "sub_scores": {}},
        },
        "scenarios": [{
            "profile_id": "s1_chat", "profile_version": "0.2", "repeat_index": 0,
            "order_index": 0, "validity": "VALID", "invalid_reasons": "",
            "kpi": _valid_kpi(),
            "clock": {"offset_start_us": 1, "offset_end_us": 2, "drift_ppm": 0.0,
                      "offset_suspect": False},
            "network_snapshot": {"transport": "cellular", "capabilities": "c",
                                 "interface": "rmnet0", "server_observed_addr": "1.2.3.4:5"},
            "parse": {"parse_dur_us": 10, "per_event_parse_us": 1.0},
            "buffering": {"score": None, "attribution": None, "sample_count": None},
            "itl_histogram": {"buckets_version": "v1", "edges_ms": [10, 20, 50],
                              "counts": [1, 2, 3, 4], "total": 10},
        }],
    }


def _errors(rec):
    return vd.validate_records([rec], SCH)[0]


def _warnings(rec):
    return vd.validate_records([rec], SCH)[1]


# ---------------------------------------------------------------- happy path

def test_valid_record_has_no_errors():
    assert _errors(_valid_record()) == []
    assert _warnings(_valid_record()) == []


# ---------------------------------------------------------------- structural

def test_missing_top_required_field():
    rec = _valid_record()
    del rec["kpi_set"]
    assert any("missing required field 'kpi_set'" in e for e in _errors(rec))


def test_claim_scope_const_enforced():
    rec = _valid_record()
    rec["claim_scope"] = "radio_layer_mos"
    assert any("claim_scope" in e for e in _errors(rec))


def test_missing_run_required_field():
    rec = _valid_record()
    del rec["run"]["scenario_order"]
    assert any("run: missing required field 'scenario_order'" in e for e in _errors(rec))


def test_missing_scenario_required_field():
    rec = _valid_record()
    del rec["scenarios"][0]["order_index"]
    assert any("order_index" in e for e in _errors(rec))


def test_unknown_validity_state_fails():
    rec = _valid_record()
    rec["scenarios"][0]["validity"] = "MAYBE"
    assert any("validity" in e for e in _errors(rec))


# ---------------------------------------------------------------- case drift

def test_lowercase_validity_is_advisory_not_error():
    """The real producer emits lower-case: must pass (exit 0) with an advisory."""
    rec = _valid_record()
    rec["scenarios"][0]["validity"] = "valid_low_confidence"
    assert _errors(rec) == []
    assert any("case drift" in w for w in _warnings(rec))


# ---------------------------------------------------------------- R-10 cross-field

def test_aqs_null_score_needs_reason():
    rec = _valid_record()
    rec["run"]["aqs"]["score"] = None          # reason still None -> violation
    assert any("not_computable_reason is empty" in e for e in _errors(rec))


def test_aqs_null_score_with_reason_ok():
    rec = _valid_record()
    rec["run"]["aqs"]["score"] = None
    rec["run"]["aqs"]["not_computable_reason"] = "KPI_MISSING:D1"
    assert _errors(rec) == []


def test_aqs_score_with_reason_is_contradictory():
    rec = _valid_record()
    rec["run"]["aqs"]["not_computable_reason"] = "KPI_MISSING:D1"   # score still 90
    assert any("contradictory" in e for e in _errors(rec))


def test_kpi_value_without_grade_fails():
    rec = _valid_record()
    rec["scenarios"][0]["kpi"]["n1_grade"] = None    # value present, grade null
    assert any("value/grade nullness" in e for e in _errors(rec))


def test_kpi_null_value_with_grade_fails():
    rec = _valid_record()
    rec["scenarios"][0]["kpi"]["n1_rtt_p50_ms"] = None   # grade still 'good'
    assert any("value/grade nullness" in e for e in _errors(rec))


def test_kpi_both_null_ok():
    rec = _valid_record()
    rec["scenarios"][0]["kpi"]["n1_rtt_p50_ms"] = None
    rec["scenarios"][0]["kpi"]["n1_grade"] = None
    assert _errors(rec) == []


def test_histogram_counts_length_invariant():
    rec = _valid_record()
    rec["scenarios"][0]["itl_histogram"]["counts"] = [1, 2, 3]   # need len(edges)+1 = 4
    assert any("open-ended bins" in e for e in _errors(rec))


# ---------------------------------------------------------------- CLI

def test_cli_valid_and_invalid():
    with tempfile.TemporaryDirectory() as d:
        good = os.path.join(d, "good.jsonl")
        bad = os.path.join(d, "bad.jsonl")
        with open(good, "w", encoding="utf-8") as f:
            f.write(json.dumps(_valid_record()) + "\n")
        broken = copy.deepcopy(_valid_record())
        broken["claim_scope"] = "wrong"
        with open(bad, "w", encoding="utf-8") as f:
            f.write(json.dumps(broken) + "\n")
        assert vd.main([good]) == 0
        assert vd.main([bad]) == 1


def test_cli_missing_schema_returns_2():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "x.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps(_valid_record()) + "\n")
        assert vd.main([p, "--schema", os.path.join(d, "nope.json")]) == 2
