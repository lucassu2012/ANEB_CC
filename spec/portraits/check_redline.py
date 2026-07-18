# -*- coding: utf-8 -*-
"""
Profile-3 portrait red-line guard (D-62; hardened D-65 spine-3).
Machine-enforces the honesty red line so no future edit silently unlocks the
params gate or overclaims caliber. Mirrors the SpecScoringParityTest 防漂移
philosophy for scoring, applied to portraits.

Run:  python spec/portraits/check_redline.py
Exit: 0 = all invariants hold; 1 = violation(s) found; 2 = harness error.
Wire into pre-commit / CI to keep the red line enforced (see scripts/verify_all.ps1).

Refactored (D-65) into importable pure functions so the guard itself is unit-tested
(spec/portraits/test_check_redline.py); IO stays in main().

Invariants:
  --- per-portrait (check_portrait) ---
  R1  params: all 7 fields are null (gate not filled).
  R2  source_portrait == "PENDING-CAPTURE" (capture gate intact).
  R3  params_fit_approx.gates_params == false AND source_portrait_unlocked == false.
  R4  every fit field caliber in {direct, order-of-magnitude, ui-proxy, none}.
  R5  cross-layer: token_interval_ms_dist / think_pause_ms_dist caliber must be
      ui-proxy or none (never direct/order-of-magnitude) — UI/proxy != network ITL.
  R6  caliber == none  => value starts with "PENDING".
  R7  keep_pending == false is allowed ONLY for caliber == direct.
  R8  keep_pending == false value must NOT start with "PENDING".
  R9  schema_version matches ^\\d+\\.\\d+\\.\\d+$ .
  R10 params_fit_approx.fields key set is EXACTLY the 7 PARAM_FIELDS (no missing / no typo drift).
  R11 every fit field carries all three keys value / caliber / keep_pending (no silent-None passthrough).
  R12 caliber in {direct, order-of-magnitude, ui-proxy} => value does NOT start with "PENDING"
      (inverse of R6: "declared a caliber but left PENDING" self-contradiction).
  R13 keep_pending == false may appear ONLY on the pop_ip_list field (domain fact:
      only infra IPs may escape PENDING inside params_fit_approx).
  R14 keep_pending == false pop_ip value MUST contain an IPv4/IPv6 literal
      (machine-blocks "SNI hostname masquerading as resolved POP IP").
  --- cross-file (check_cross_file) ---
  R15 downlink_media_bytes_dist.caliber == none for ALL portraits (permanent "text != media" red line).
  R16 pop_ip_list.caliber == direct for ALL portraits (infra-fact field caliber fixed, 防漂移).
  R17 keep_pending == false pop_ip requires an IP literal in the SAME file's observed_network_layer
      (traceability: value <-> evidence-segment backlink).
"""
import sys, os, glob, re

try:
    import yaml
except ImportError:
    print("FAIL: pyyaml required (pip install pyyaml)"); sys.exit(2)

PARAM_FIELDS = ["request_size_bytes_dist", "token_interval_ms_dist", "think_pause_ms_dist",
                "tool_loop_cadence", "session_duration_s_dist", "downlink_media_bytes_dist", "pop_ip_list"]
CALIBERS = {"direct", "order-of-magnitude", "ui-proxy", "none"}
CALIBER_NON_PENDING = {"direct", "order-of-magnitude", "ui-proxy"}  # R12: these must not be PENDING
NETWORK_TIMING = {"token_interval_ms_dist", "think_pause_ms_dist"}  # must never be direct/OoM (cross-layer)
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6 = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,}[0-9a-fA-F]{0,4}\b")


def _has_ip(s):
    return bool(IPV4.search(s) or IPV6.search(s))


def check_portrait(app, d):
    """Single-portrait dict -> list of violation strings (pure, no IO). Carries R1-R14."""
    v = []

    def bad(cond, rule, msg):
        if not cond:
            v.append(f"[{app}] {rule}: {msg}")

    params = d.get("params", {}) or {}
    # R1
    bad(all(params.get(k) is None for k in PARAM_FIELDS), "R1",
        f"params not all null: {[k for k in PARAM_FIELDS if params.get(k) is not None]}")
    # R2
    bad(d.get("source_portrait") == "PENDING-CAPTURE", "R2",
        f"source_portrait={d.get('source_portrait')} (must be PENDING-CAPTURE)")
    # R9
    bad(bool(SEMVER.match(str(d.get("schema_version", "")))), "R9",
        f"schema_version={d.get('schema_version')} not semver")

    pf = d.get("params_fit_approx")
    if pf is None:
        return v  # portrait may predate D-62 fit; R1/R2/R9 still enforced
    # R3
    bad(pf.get("gates_params") is False, "R3", f"gates_params={pf.get('gates_params')} (must be false)")
    bad(pf.get("source_portrait_unlocked") is False, "R3",
        f"source_portrait_unlocked={pf.get('source_portrait_unlocked')} (must be false)")
    fields = pf.get("fields", {}) or {}
    # R10 — exact key set (catches typo drift like pop_ip_lst silently escaping per-field checks)
    bad(set(fields.keys()) == set(PARAM_FIELDS), "R10",
        f"fields key set != 7 PARAM_FIELDS: extra={sorted(set(fields)-set(PARAM_FIELDS))} "
        f"missing={sorted(set(PARAM_FIELDS)-set(fields))}")

    for name, fl in fields.items():
        fl = fl or {}
        # R11 — required sub-keys present (else fl.get() returns None and R7 silently passes)
        missing = [k for k in ("value", "caliber", "keep_pending") if k not in fl]
        bad(not missing, "R11", f"{name} missing sub-keys {missing}")
        cal = fl.get("caliber"); val = str(fl.get("value", "")); kp = fl.get("keep_pending")
        # R4
        bad(cal in CALIBERS, "R4", f"{name} caliber={cal} not in {sorted(CALIBERS)}")
        # R5
        if name in NETWORK_TIMING:
            bad(cal in {"ui-proxy", "none"}, "R5",
                f"{name} caliber={cal} — network-timing field must be ui-proxy/none (cross-layer guard)")
        # R6
        if cal == "none":
            bad(val.startswith("PENDING"), "R6", f"{name} caliber=none but value not PENDING: {val[:40]}")
        # R12 — inverse of R6
        if cal in CALIBER_NON_PENDING:
            bad(not val.startswith("PENDING"), "R12",
                f"{name} caliber={cal} but value starts PENDING (declared caliber yet left PENDING)")
        # R7 / R8 / R13 / R14 — keep_pending==false gate escape
        if kp is False:
            bad(cal == "direct", "R7", f"{name} keep_pending=false but caliber={cal} (only direct may escape PENDING)")
            bad(not val.startswith("PENDING"), "R8", f"{name} keep_pending=false but value=PENDING")
            bad(name == "pop_ip_list", "R13",
                f"{name} keep_pending=false — only pop_ip_list may escape PENDING in params_fit_approx")
            if name == "pop_ip_list":
                bad(_has_ip(val), "R14",
                    f"pop_ip keep_pending=false but value has no IP literal (SNI hostname != resolved POP IP): {val[:60]}")
    return v


def check_cross_file(portraits):
    """{app: dict} -> list of cross-file violations (pure). Carries R15-R17."""
    v = []

    def bad(app, cond, rule, msg):
        if not cond:
            v.append(f"[{app}] {rule}: {msg}")

    for app, d in portraits.items():
        pf = d.get("params_fit_approx")
        if pf is None:
            continue
        fields = pf.get("fields", {}) or {}
        media = fields.get("downlink_media_bytes_dist") or {}
        pop = fields.get("pop_ip_list") or {}
        # R15 — media caliber permanently none (text != media)
        if "downlink_media_bytes_dist" in fields:
            bad(app, media.get("caliber") == "none", "R15",
                f"downlink_media caliber={media.get('caliber')} (must be none: text != media red line)")
        # R16 — pop_ip caliber fixed at direct
        if "pop_ip_list" in fields:
            bad(app, pop.get("caliber") == "direct", "R16",
                f"pop_ip caliber={pop.get('caliber')} (infra-fact field must be direct)")
        # R17 — evidence backlink: escaped pop_ip needs IP in observed_network_layer
        if pop.get("keep_pending") is False:
            onl = yaml.safe_dump(d.get("observed_network_layer", {}), allow_unicode=True)
            bad(app, _has_ip(onl), "R17",
                "pop_ip keep_pending=false but observed_network_layer has no IP literal (no evidence backlink)")
    return v


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    files = sorted(glob.glob(os.path.join(here, "*.yaml")))
    if not files:
        print("FAIL: no portrait yaml found"); return 2
    portraits = {}
    for path in files:
        app = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as f:
            portraits[app] = yaml.safe_load(f)
    violations = []
    for app, d in portraits.items():
        violations += check_portrait(app, d)
    violations += check_cross_file(portraits)
    print(f"Checked {len(files)} portraits: {', '.join(os.path.basename(p) for p in files)}")
    if violations:
        print(f"\nRED-LINE VIOLATIONS ({len(violations)}):")
        for x in violations:
            print("  -", x)
        return 1
    print("OK: all red-line invariants hold (R1-R17: params gate intact, no caliber overclaim).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
