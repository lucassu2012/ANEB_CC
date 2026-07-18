# -*- coding: utf-8 -*-
"""
Profile-3 portrait red-line guard (D-62).
Machine-enforces the honesty red line so no future edit silently unlocks the
params gate or overclaims caliber. Mirrors the SpecScoringParityTest 防漂移
philosophy for scoring, applied to portraits.

Run:  python spec/portraits/check_redline.py
Exit: 0 = all invariants hold; 1 = violation(s) found (printed).
Wire into pre-commit / CI to keep the red line enforced.

Invariants (per portrait *.yaml):
  R1  params: all 7 fields are null (gate not filled).
  R2  source_portrait == "PENDING-CAPTURE" (capture gate intact).
  R3  params_fit_approx.gates_params == false AND source_portrait_unlocked == false.
  R4  every fit field caliber in {direct, order-of-magnitude, ui-proxy, none}.
  R5  cross-layer: token_interval_ms_dist / think_pause_ms_dist caliber must be
      ui-proxy or none (never direct/order-of-magnitude) — UI/proxy != network ITL.
  R6  caliber == none  => value starts with "PENDING".
  R7  keep_pending == false is allowed ONLY for caliber == direct (resolved
      infra fact, e.g. pop_ip with real IP). Any non-direct field must stay pending.
  R8  keep_pending == false value must NOT start with "PENDING".
"""
import sys, os, glob

try:
    import yaml
except ImportError:
    print("FAIL: pyyaml required (pip install pyyaml)"); sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
PARAM_FIELDS = ["request_size_bytes_dist", "token_interval_ms_dist", "think_pause_ms_dist",
                "tool_loop_cadence", "session_duration_s_dist", "downlink_media_bytes_dist", "pop_ip_list"]
CALIBERS = {"direct", "order-of-magnitude", "ui-proxy", "none"}
NETWORK_TIMING = {"token_interval_ms_dist", "think_pause_ms_dist"}  # must never be direct/OoM (cross-layer)

violations = []

def check(app, cond, rule, msg):
    if not cond:
        violations.append(f"[{app}] {rule}: {msg}")

files = sorted(glob.glob(os.path.join(HERE, "*.yaml")))
if not files:
    print("FAIL: no portrait yaml found"); sys.exit(2)

for path in files:
    app = os.path.splitext(os.path.basename(path))[0]
    with open(path, encoding="utf-8") as f:
        d = yaml.safe_load(f)
    params = d.get("params", {}) or {}
    # R1
    check(app, all(params.get(k) is None for k in PARAM_FIELDS), "R1",
          f"params not all null: {[k for k in PARAM_FIELDS if params.get(k) is not None]}")
    # R2
    check(app, d.get("source_portrait") == "PENDING-CAPTURE", "R2",
          f"source_portrait={d.get('source_portrait')} (must be PENDING-CAPTURE)")
    pf = d.get("params_fit_approx")
    if pf is None:
        continue  # portrait may predate D-62 fit; R1/R2 still enforced
    # R3
    check(app, pf.get("gates_params") is False, "R3", f"gates_params={pf.get('gates_params')} (must be false)")
    check(app, pf.get("source_portrait_unlocked") is False, "R3",
          f"source_portrait_unlocked={pf.get('source_portrait_unlocked')} (must be false)")
    fields = pf.get("fields", {}) or {}
    for name, fl in fields.items():
        cal = fl.get("caliber"); val = str(fl.get("value", "")); kp = fl.get("keep_pending")
        # R4
        check(app, cal in CALIBERS, "R4", f"{name} caliber={cal} not in {CALIBERS}")
        # R5
        if name in NETWORK_TIMING:
            check(app, cal in {"ui-proxy", "none"}, "R5",
                  f"{name} caliber={cal} — network-timing field must be ui-proxy/none (cross-layer guard)")
        # R6
        if cal == "none":
            check(app, val.startswith("PENDING"), "R6", f"{name} caliber=none but value not PENDING: {val[:40]}")
        # R7
        if kp is False:
            check(app, cal == "direct", "R7",
                  f"{name} keep_pending=false but caliber={cal} (only direct may escape PENDING)")
            # R8
            check(app, not val.startswith("PENDING"), "R8", f"{name} keep_pending=false but value=PENDING")

print(f"Checked {len(files)} portraits: {', '.join(os.path.basename(p) for p in files)}")
if violations:
    print(f"\nRED-LINE VIOLATIONS ({len(violations)}):")
    for v in violations: print("  -", v)
    sys.exit(1)
print("OK: all red-line invariants hold (params gate intact, no caliber overclaim).")
sys.exit(0)
