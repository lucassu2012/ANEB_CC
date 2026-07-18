#!/usr/bin/env python3
"""Reflex tests for portrait.schema.json — the guard's guard (matches test_check_redline.py).

Each test mutates a minimal-valid portrait and asserts the shape gate reacts correctly:
red fixtures must be REJECTED, the green fixture and forward-compat metadata ACCEPTED.
Fixtures are in-memory dicts — no real yaml, no device. Self-contained runner (no pytest);
exit 1 if any reflex fails (schema weakened / a required shape constraint regressed).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(HERE, "portrait.schema.json")

PARAM_FIELDS = [
    "request_size_bytes_dist", "token_interval_ms_dist", "think_pause_ms_dist",
    "tool_loop_cadence", "session_duration_s_dist", "downlink_media_bytes_dist", "pop_ip_list",
]


def _valid():
    """Minimal portrait that must pass the shape gate."""
    fit = {k: {"value": "PENDING(x)", "caliber": "none", "keep_pending": True} for k in PARAM_FIELDS}
    layer = {"captured": True, "source": "aneb-x", "caliber": "LOW/INCONCLUSIVE"}
    return {
        "schema_version": "1.0.0",
        "app_id": "x",
        "display_name": "X",
        "source_portrait": "PENDING-CAPTURE",
        "params": {k: None for k in PARAM_FIELDS},
        "params_fit_approx": {"gates_params": False, "source_portrait_unlocked": False, "fields": fit},
        "observed_ui_layer": dict(layer),
        "observed_network_layer": {"captured": "full", "source": "aneb-pcap", "caliber": "net"},
    }


def _errs(d):
    import jsonschema
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        validator = jsonschema.Draft202012Validator(json.load(f))
    return list(validator.iter_errors(d))


def test_valid_portrait_accepted():
    assert _errs(_valid()) == []


def test_missing_param_field_rejected():
    d = _valid(); del d["params"]["pop_ip_list"]
    assert _errs(d)


def test_typo_param_field_rejected():
    d = _valid(); d["params"]["pop_ip_lst"] = d["params"].pop("pop_ip_list")
    assert _errs(d)


def test_typo_fit_field_rejected():
    d = _valid()
    f = d["params_fit_approx"]["fields"]
    f["pop_ip_lst"] = f.pop("pop_ip_list")
    assert _errs(d)


def test_bad_caliber_rejected():
    d = _valid(); d["params_fit_approx"]["fields"]["pop_ip_list"]["caliber"] = "guess"
    assert _errs(d)


def test_missing_fit_subkey_rejected():
    d = _valid(); del d["params_fit_approx"]["fields"]["pop_ip_list"]["keep_pending"]
    assert _errs(d)


def test_missing_observed_layer_rejected():
    d = _valid(); del d["observed_network_layer"]
    assert _errs(d)


def test_missing_observed_required_key_rejected():
    d = _valid(); del d["observed_ui_layer"]["caliber"]
    assert _errs(d)


def test_bad_semver_rejected():
    d = _valid(); d["schema_version"] = "1.0"
    assert _errs(d)


def test_extra_fit_metadata_allowed():
    # forward-compat: additive provenance metadata (spine-3 #8) must NOT break the shape gate
    d = _valid()
    d["params_fit_approx"]["fields"]["pop_ip_list"].update(
        {"source_layer": "network", "confidence": "LOW", "note": "n=1"}
    )
    assert _errs(d) == []


if __name__ == "__main__":
    import jsonschema  # noqa: F401 — surface a missing dep as a harness failure (non-zero exit)
    tests = {n: f for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)}
    failed = []
    for name, fn in tests.items():
        try:
            fn()
        except AssertionError as e:
            failed.append((name, f"assertion failed: {e}"))
        except Exception as e:  # noqa: BLE001 — surface any harness error as a failure
            failed.append((name, f"{type(e).__name__}: {e}"))
    print(f"ran {len(tests)} schema reflex tests: {len(tests) - len(failed)} passed, {len(failed)} failed")
    for name, why in failed:
        print("  FAIL", name, "-", why)
    sys.exit(1 if failed else 0)
