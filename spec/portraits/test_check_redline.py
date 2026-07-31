# -*- coding: utf-8 -*-
"""
Reflex tests for the portrait red-line guard (D-65 spine-3).
Each invariant gets a RED fixture (must be caught) + the GREEN baselines
(valid portraits must pass). Fixtures are in-memory dicts — no real yaml,
no device, no PO dependency. Run:  python -m pytest spec/portraits/test_check_redline.py -q

Guards the guard: if a future refactor weakens an invariant, its RED test fails.
"""
from check_redline import (check_portrait, check_cross_file, gate_state, portrait_mode,
                           PARAM_FIELDS, RULED_STATUS)


def _capture_status(overrides=None):
    """Plan-B status block: everything PENDING except the two by-caliber rulings (D-348)."""
    st = {k: {"status": RULED_STATUS.get(k, "PENDING"), "reason": "fixture reason"}
          for k in PARAM_FIELDS}
    for k, s in (overrides or {}).items():
        st[k] = {"status": s, "reason": "fixture reason"}
    return st


def _valid_pending():
    """Minimal valid PENDING portrait (doubao-style: pop_ip direct+hostname awaiting DNS)."""
    fields = {k: {"value": "PENDING(no same-caliber source)", "caliber": "none", "keep_pending": True,
                  "source_layer": "none", "confidence": "INCONCLUSIVE", "note": "pending"}
              for k in PARAM_FIELDS}
    # pop_ip is the infra-fact field: caliber=direct (R16), value non-PENDING (R12), still pending DNS.
    # R18: direct => source_layer=network, confidence=LOW.
    fields["pop_ip_list"] = {"value": "host.example.com (SNI hostname, DNS pending)",
                             "caliber": "direct", "keep_pending": True,
                             "source_layer": "network", "confidence": "LOW", "note": "infra fact"}
    return {
        "schema_version": "1.0.0",
        "source_portrait": "PENDING-CAPTURE",
        "params": {k: None for k in PARAM_FIELDS},
        "params_capture_status": _capture_status(),
        "observed_network_layer": {"endpoints": ["host.example.com"]},
        "params_fit_approx": {"gates_params": False, "source_portrait_unlocked": False, "fields": fields},
    }


def _flipped():
    """A LEGITIMATE plan-B flip: every capturable field CAPTURED with a real value, the two
    by-caliber rulings left as-is, source_portrait naming a traceable capture.

    This fixture is the half of R19 that matters most: before D-348 a portrait in this state
    was judged FAIL by R1/R2, so the gate could never open honestly and any real capture would
    have been forced to weaken the guard instead."""
    d = _valid_pending()
    capturable = [k for k in PARAM_FIELDS if k not in RULED_STATUS]
    d["source_portrait"] = "x-app-capture-2026-08-15"
    d["params_capture_status"] = _capture_status({k: "CAPTURED" for k in capturable})
    for k in capturable:
        d["params"][k] = {"p50": 1, "p90": 2, "p99": 3, "n": 30}
    d["params_fit_approx"]["source_portrait_unlocked"] = True
    return d


def _valid_escaped_popip():
    """tongyi-style valid: pop_ip escaped PENDING with real IP + evidence backlink."""
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["pop_ip_list"] = {
        "value": "110.253.191.12, 114.250.44.6 (resolved POP IP)", "caliber": "direct", "keep_pending": False,
        "source_layer": "network", "confidence": "LOW", "note": "resolved IP"}
    d["observed_network_layer"] = {"endpoints": ["upaas.quark.cn 110.253.191.12", "114.250.44.6"]}
    return d


def _has(viol, rule):
    return any(rule in v for v in viol)


# ---- GREEN baselines ----

def test_valid_pending_passes():
    assert check_portrait("x", _valid_pending()) == []
    assert check_cross_file({"x": _valid_pending()}) == []


def test_valid_escaped_popip_passes():
    d = _valid_escaped_popip()
    assert check_portrait("x", d) == []
    assert check_cross_file({"x": d}) == []


def test_a_legitimate_plan_b_flip_passes():
    """The half of R19 that matters most: a HONEST flip must be allowed through.

    Before D-348 this exact state was judged FAIL by R1 (all-null) and R2 (sentinel only), so
    the gate could never open honestly — anyone with a real capture would have had to weaken
    the guard to record it, which is how honesty guards die.
    """
    d = _flipped()
    assert check_portrait("x", d) == []
    assert check_cross_file({"x": d}) == []
    assert portrait_mode(d) == "CAPTURED"
    ready, blockers = gate_state("x", d)
    assert ready and blockers == []


def test_by_caliber_fields_never_block_the_flip():
    """The plan-A defect this replaces: one permanently-unreachable field freezing the gate
    forever. token_interval/think_pause (red-line-outside) and tool_loop (never applicable)
    are excluded from the criterion — while plain PENDING still blocks."""
    ready, blockers = gate_state("x", _valid_pending())
    assert not ready
    assert set(blockers) == set(PARAM_FIELDS) - set(RULED_STATUS)
    assert not (set(blockers) & set(RULED_STATUS)), "a by-caliber ruling must never block"


# ---- RED per-invariant (check_portrait) ----

def test_R1_filled_param_caught():
    d = _valid_pending(); d["params"]["request_size_bytes_dist"] = "FAKE-42KB"
    assert _has(check_portrait("x", d), "R1")


def test_R19a_missing_status_block_caught():
    """No status block = no gate criterion, and "no criterion" reads as "nothing blocking".
    Absence must be a violation, never a skip."""
    d = _valid_pending(); del d["params_capture_status"]
    assert _has(check_portrait("x", d), "R19a")


def test_R19b_status_without_reason_caught():
    d = _valid_pending()
    d["params_capture_status"]["pop_ip_list"] = {"status": "PENDING", "reason": "  "}
    assert _has(check_portrait("x", d), "R19b")


def test_R19c_captured_without_value_caught():
    """Claiming a capture the portrait has not got — the direction R1 does not cover."""
    d = _valid_pending()
    d["params_capture_status"]["pop_ip_list"] = {"status": "CAPTURED", "reason": "claimed"}
    assert _has(check_portrait("x", d), "R19c")


def test_R19d_ruled_field_promoted_caught():
    """The 2026-07-31 rulings are frozen machine-side: promoting token_interval to an ordinary
    PENDING (or to CAPTURED) would quietly re-open a field this methodology cannot reach."""
    d = _valid_pending()
    d["params_capture_status"]["token_interval_ms_dist"] = {"status": "PENDING", "reason": "x"}
    assert _has(check_portrait("x", d), "R19d")


def test_a_single_field_may_unlock_on_its_own():
    """Plan B's whole point (「哪个字段采够样本就翻哪个」): one field reaching its threshold is
    filled and CAPTURED while every other stays null and blocking, with source_portrait still
    the sentinel. Under the old all-null R1 this legitimate state was a violation."""
    d = _valid_pending()
    d["params_capture_status"]["pop_ip_list"] = {"status": "CAPTURED", "reason": "dual-network POP set"}
    d["params"]["pop_ip_list"] = ["203.0.113.7", "198.51.100.9"]
    assert check_portrait("x", d) == []
    ready, blockers = gate_state("x", d)
    assert not ready and "pop_ip_list" not in blockers


def test_R2_free_form_source_portrait_caught():
    """R2 changed meaning at D-348 and this test changed with it, deliberately: it used to
    assert that ANY flip was caught, which is now wrong (an honest flip must be allowed,
    see test_a_legitimate_plan_b_flip_passes). What R2 still forbids is a source_portrait
    that is neither the sentinel nor a traceable capture id — an unauditable claim."""
    d = _valid_pending(); d["source_portrait"] = "captured (see chat log)"
    assert _has(check_portrait("x", d), "R2")


def test_R19e_half_flip_caught():
    """The flip is well-formed but a field is still plain PENDING — the whitewash R19e exists
    to stop. This is what the old R2 blanket-ban was really protecting against."""
    d = _valid_pending()
    d["source_portrait"] = "x-app-capture-2026-08-15"
    d["params_fit_approx"]["source_portrait_unlocked"] = True
    assert _has(check_portrait("x", d), "R19e")


def test_R3_gates_params_true_caught():
    d = _valid_pending(); d["params_fit_approx"]["gates_params"] = True
    assert _has(check_portrait("x", d), "R3")


def test_R5_crosslayer_token_interval_direct_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["token_interval_ms_dist"] = {
        "value": "259ms", "caliber": "direct", "keep_pending": True}
    assert _has(check_portrait("x", d), "R5")


def test_R6_none_not_pending_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["think_pause_ms_dist"]["value"] = "123ms"  # caliber none but not PENDING
    assert _has(check_portrait("x", d), "R6")


def test_R9_bad_semver_caught():
    d = _valid_pending(); d["schema_version"] = "v1"
    assert _has(check_portrait("x", d), "R9")


def test_R10_typo_field_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["pop_ip_lst"] = d["params_fit_approx"]["fields"].pop("pop_ip_list")
    assert _has(check_portrait("x", d), "R10")


def test_R11_missing_keep_pending_caught():
    d = _valid_pending(); del d["params_fit_approx"]["fields"]["tool_loop_cadence"]["keep_pending"]
    assert _has(check_portrait("x", d), "R11")


def test_R12_declared_caliber_left_pending_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["request_size_bytes_dist"] = {
        "value": "PENDING(...)", "caliber": "order-of-magnitude", "keep_pending": True}
    assert _has(check_portrait("x", d), "R12")


def test_R13_nonpopip_escape_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["request_size_bytes_dist"] = {
        "value": "13.8KB", "caliber": "direct", "keep_pending": False}
    assert _has(check_portrait("x", d), "R13")


def test_R14_hostname_masquerade_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["pop_ip_list"] = {
        "value": "chat.deepseek.com (SNI hostname only)", "caliber": "direct", "keep_pending": False}
    assert _has(check_portrait("x", d), "R14")


# ---- RED per-invariant (check_cross_file) ----

def test_R15_media_not_none_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["downlink_media_bytes_dist"] = {
        "value": "17.6KB", "caliber": "order-of-magnitude", "keep_pending": True}
    assert _has(check_cross_file({"x": d}), "R15")


def test_R16_popip_not_direct_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["pop_ip_list"] = {
        "value": "PENDING(...)", "caliber": "none", "keep_pending": True}
    assert _has(check_cross_file({"x": d}), "R16")


def test_R17_no_evidence_backlink_caught():
    d = _valid_escaped_popip()
    d["observed_network_layer"] = {"endpoints": ["upaas.quark.cn (hostname only, no IP)"]}
    assert _has(check_cross_file({"x": d}), "R17")


def test_R18_missing_provenance_caught():
    d = _valid_pending(); del d["params_fit_approx"]["fields"]["think_pause_ms_dist"]["confidence"]
    assert _has(check_portrait("x", d), "R18")


def test_R18_inconsistent_source_layer_caught():
    # caliber=none requires source_layer=none; declaring network is provenance drift
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["think_pause_ms_dist"]["source_layer"] = "network"
    assert _has(check_portrait("x", d), "R18")


def test_R18_bad_confidence_enum_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["pop_ip_list"]["confidence"] = "HIGH"  # not in {LOW, NONE}
    assert _has(check_portrait("x", d), "R18")


def test_R18_uiproxy_requires_ui_source_layer():
    # ui-proxy caliber must carry source_layer=ui (not network) — cross-check with caliber
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["token_interval_ms_dist"].update(
        {"value": "~100ms (UI cadence)", "caliber": "ui-proxy",
         "source_layer": "network", "confidence": "LOW", "note": "x"})
    assert _has(check_portrait("x", d), "R18")


if __name__ == "__main__":
    # Self-contained runner so verify_all/CI need no pytest (Python 3.14 env has none).
    # pytest can still collect the test_* functions if present.
    import sys
    tests = {n: f for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)}
    failed = []
    for name, fn in tests.items():
        try:
            fn()
        except AssertionError as e:
            failed.append((name, f"assertion failed: {e}"))
        except Exception as e:  # noqa: BLE001 — surface any harness error as a failure
            failed.append((name, f"{type(e).__name__}: {e}"))
    print(f"ran {len(tests)} reflex tests: {len(tests) - len(failed)} passed, {len(failed)} failed")
    for name, why in failed:
        print("  FAIL", name, "-", why)
    sys.exit(1 if failed else 0)
