# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/validate_spec_scoring.py.

Unit tests drive the pure check_* functions with synthetic dicts (no yaml needed);
one integration test loads the REAL spec/scoring pack and asserts it passes — which
also proves the validator agrees with the shipped scoring rules.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import validate_spec_scoring as vs


# ---------------------------------------------------------------- weights

def test_weights_sum_to_one_ok():
    doc = {"tables": {"W": {"version_id": "v1", "weights": {"T1": 0.5, "T2": 0.5}}}}
    assert vs.check_weights(doc) == []


def test_weights_not_summing_to_one_fails():
    doc = {"tables": {"W": {"version_id": "v1", "weights": {"T1": 0.5, "T2": 0.4}}}}
    errs = vs.check_weights(doc)
    assert any("weights" in e for e in errs)


def test_weights_float_tolerance():
    # 0.2+0.2+0.15+0.15+0.1+0.1+0.1 = 1.0 with binary float wobble -> still OK
    doc = {"tables": {"W": {"version_id": "v1", "weights":
                            {"T1": 0.2, "T3": 0.2, "T2": 0.15, "U1": 0.15,
                             "U2": 0.1, "N1": 0.1, "N2": 0.1}}}}
    assert vs.check_weights(doc) == []


def test_weights_missing_version_id_fails():
    doc = {"tables": {"W": {"weights": {"T1": 1.0}}}}
    assert any("version_id" in e for e in vs.check_weights(doc))


def test_weights_non_numeric_fails():
    doc = {"tables": {"W": {"version_id": "v1", "weights": {"T1": "half", "T2": 0.5}}}}
    assert any("non-numeric" in e for e in vs.check_weights(doc))


# ---------------------------------------------------------------- anchors

def test_anchors_ascending_ok():
    doc = {"anchors": {"T1": {"direction": "lower_better",
                              "points": [[0.0, 100.0], [200.0, 85.0], [500.0, 70.0]]}}}
    assert vs.check_anchors(doc) == []


def test_anchors_non_ascending_fails():
    doc = {"anchors": {"T1": {"direction": "lower_better",
                              "points": [[0.0, 100.0], [500.0, 85.0], [200.0, 70.0]]}}}
    assert any("strictly ascending" in e for e in vs.check_anchors(doc))


def test_anchors_bad_direction_fails():
    doc = {"anchors": {"T1": {"direction": "sideways",
                              "points": [[0.0, 100.0], [1.0, 0.0]]}}}
    assert any("direction" in e for e in vs.check_anchors(doc))


def test_anchors_score_out_of_range_fails():
    doc = {"anchors": {"T1": {"direction": "lower_better",
                              "points": [[0.0, 100.0], [1.0, 150.0]]}}}
    assert any("out of 0..100" in e for e in vs.check_anchors(doc))


def test_anchors_equal_values_not_strictly_ascending():
    doc = {"anchors": {"T1": {"direction": "lower_better",
                              "points": [[0.0, 100.0], [0.0, 90.0]]}}}
    assert any("strictly ascending" in e for e in vs.check_anchors(doc))


# ---------------------------------------------------------------- vetoes

def test_vetoes_ok():
    doc = {"vetoes": {"T4": {"metric": "t4", "comparator": ">", "threshold": 0.01,
                             "cap": 54.0, "kind": "hard"}}}
    assert vs.check_vetoes(doc) == []


def test_vetoes_missing_field_fails():
    doc = {"vetoes": {"T4": {"metric": "t4", "comparator": ">", "threshold": 0.01,
                             "kind": "hard"}}}   # no cap
    assert any("missing 'cap'" in e for e in vs.check_vetoes(doc))


def test_vetoes_bad_comparator_and_kind():
    doc = {"vetoes": {"X": {"metric": "m", "comparator": "~=", "threshold": 1,
                            "cap": 50.0, "kind": "medium"}}}
    errs = vs.check_vetoes(doc)
    assert any("comparator" in e for e in errs)
    assert any("kind" in e for e in errs)


def test_vetoes_cap_out_of_range():
    doc = {"vetoes": {"X": {"metric": "m", "comparator": ">", "threshold": 1,
                            "cap": 200.0, "kind": "hard"}}}
    assert any("cap" in e for e in vs.check_vetoes(doc))


# ---------------------------------------------------------------- integration

def test_real_spec_scoring_pack_passes():
    """The shipped spec/scoring/*.yaml must satisfy every invariant."""
    try:
        import yaml  # noqa: F401
    except ImportError:
        return  # environment without pyyaml -> validator degrades NOT_EXECUTED
    if not os.path.isdir(vs.DEFAULT_DIR):
        return
    errors, missing = vs.validate_dir(vs.DEFAULT_DIR)
    assert missing == [], f"missing scoring files: {missing}"
    assert errors == [], f"real scoring pack violates invariants: {errors}"


def test_a_spec_file_nobody_validates_is_an_error_not_a_silence():
    """`_CHECKS` names three files, and this gate is the only thing standing
    between a spec edit and a shipped scoring rule. The pack is meant to grow —
    the radio-band handoff proposes a fourth file — and until now a YAML dropped
    in beside the three would have been validated by nothing while verify_all
    went on printing PASS (D-291, the D-287 shape on the spec gate).

    Both directions are pinned: unregistered fails, and registering it as
    "no invariants of its own" with a reason makes it pass again. Without the
    second half the remedy would be undemonstrated.
    """
    import shutil
    import tempfile
    try:
        import yaml  # noqa: F401
    except ImportError:
        return
    if not os.path.isdir(vs.DEFAULT_DIR):
        return

    with tempfile.TemporaryDirectory() as tmp:
        for fname, _check in vs._CHECKS:
            shutil.copy(os.path.join(vs.DEFAULT_DIR, fname),
                        os.path.join(tmp, fname))
        errors, missing = vs.validate_dir(tmp)
        assert (errors, missing) == ([], []), (errors, missing)

        stray = "radio_bands.yaml"
        with open(os.path.join(tmp, stray), "w", encoding="utf-8") as fh:
            fh.write('schema_version: "1.0.0"\n')
        errors, _missing = vs.validate_dir(tmp)
        assert any(stray in e for e in errors), (
            "an unregistered spec file passed the gate: %s" % errors)

        vs._NO_INVARIANTS[stray] = "test fixture"
        try:
            errors, _missing = vs.validate_dir(tmp)
            assert errors == [], (
                "registering it as invariant-free left it failing: %s" % errors)
        finally:
            vs._NO_INVARIANTS.pop(stray, None)
