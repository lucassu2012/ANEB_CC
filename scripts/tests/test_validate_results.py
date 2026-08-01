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
            "order_index": 0, "validity": "valid", "invalid_reasons": "",
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

def test_lowercase_validity_is_the_exact_match_now():
    """D-371 aligned the schema to the producer's lower-case (every real corpus
    is lower-case; the upper-case enum was the aspirational copy, D-190). The
    authoritative spelling must pass with NO advisory — a warning that fires on
    every honest record teaches the operator to ignore warnings."""
    rec = _valid_record()
    rec["scenarios"][0]["validity"] = "valid_low_confidence"
    assert _errors(rec) == []
    assert _warnings(rec) == []


def test_uppercase_validity_is_advisory_not_error():
    """The drift direction inverted with D-371: legacy upper-case (old fixtures,
    pre-alignment tools) now matches only by case-fold — advisory, not a
    rejection (the record still carries a usable measurement)."""
    rec = _valid_record()
    rec["scenarios"][0]["validity"] = "VALID_LOW_CONFIDENCE"
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


def test_non_finite_numbers_are_contract_errors():
    """The aggregates refuse NaN so the numbers stay honest, but "silently not
    computable" is not the same as telling the operator the corpus is broken."""
    from synth import contractify, kpi_scenario_records
    recs = [contractify(r) for r in kpi_scenario_records(2, kpi={"n1_rtt_p50_ms": 20})]
    recs[0]["scenarios"][0]["kpi"]["n1_rtt_p50_ms"] = float("nan")
    errors, _ = vd.validate_records(recs, SCH)
    hits = [e for e in errors if "NaN/Infinity" in e]
    assert len(hits) == 1
    assert "n1_rtt_p50_ms" in hits[0]
    clean, _ = vd.validate_records(
        [contractify(r) for r in kpi_scenario_records(2, kpi={"n1_rtt_p50_ms": 20})],
        SCH)
    assert not [e for e in clean if "NaN/Infinity" in e]


# ------------------------------------------------- the schema is the contract

def _dig(node, *path):
    for step in path:
        node = node[step]
    return node


# Where each rule load_schema() extracts lives in the JSON, and how to break it
# there. Keyed by the names load_schema returns, so a rule added to the extractor
# without an entry here fails the test instead of sliding in unchecked (D-234).
_SCHEMA_SITE = {
    "top_required":
        lambda s: _dig(s, "required").append("zzz_not_a_field"),
    "claim_scope_const":
        lambda s: _dig(s, "properties", "claim_scope").__setitem__("const", "zzz"),
    "run_required":
        lambda s: _dig(s, "properties", "run", "required").append("zzz_not_a_field"),
    "aqs_required":
        lambda s: _dig(s, "properties", "run", "properties", "aqs",
                       "required").append("zzz_not_a_field"),
    "scenario_required":
        lambda s: _dig(s, "definitions", "scenario", "required").append("zzz_not_a_field"),
    "validity_enum":
        lambda s: _dig(s, "definitions", "scenario", "properties",
                       "validity").__setitem__("enum", ["ZZZ_ONLY"]),
    "kpi_required":
        lambda s: _dig(s, "definitions", "scenario", "properties", "kpi",
                       "required").append("zzz_not_a_field"),
    "hist_required":
        lambda s: _dig(s, "definitions", "scenario", "properties", "itl_histogram",
                       "required").append("zzz_not_a_field"),
}


def test_every_rule_this_validator_enforces_is_read_from_the_schema():
    """`load_schema` promises the validator 「tracks the contract instead of
    hard-coding a second copy」, and nothing checked it: every test in this file
    loads the real schema, so a validator that opened the file and then enforced
    its own hard-coded copy would pass all of them (D-234).

    Two halves per rule, because either can drift on its own: doctoring the JSON
    must change what load_schema extracts, and the doctored rule must change the
    verdict on a record that was clean a moment ago.
    """
    with open(vd.DEFAULT_SCHEMA, encoding="utf-8") as fh:
        raw = json.load(fh)
    assert set(SCH) == set(_SCHEMA_SITE), (
        f"rules with no doctor: {sorted(set(SCH) - set(_SCHEMA_SITE))}; "
        f"doctors for rules that are gone: {sorted(set(_SCHEMA_SITE) - set(SCH))}")
    assert _errors(_valid_record()) == [], "the fixture has to start clean"

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "doctored.schema.json")
        for rule, break_it in _SCHEMA_SITE.items():
            doctored = copy.deepcopy(raw)
            break_it(doctored)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(doctored, fh)
            reloaded = vd.load_schema(path)
            assert reloaded[rule] != SCH[rule], (
                f"{rule}: the schema file changed and load_schema returned the "
                "same thing — this rule is not being read from the contract")
            errors, _ = vd.validate_records([_valid_record()], reloaded)
            assert errors, (
                f"{rule}: the rule changed and a record that now violates it "
                "still passed — the verdict is not using what was read")
