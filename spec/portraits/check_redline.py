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
  R18 every fit field carries provenance metadata source_layer / confidence / note, AND that
      metadata is consistent with caliber (spine-3 #8): source_layer in {network, ui, none},
      confidence in {LOW, INCONCLUSIVE}; caliber none => (none, INCONCLUSIVE), ui-proxy => (ui, LOW),
      direct|order-of-magnitude => (network, LOW). Keeps provenance from drifting off the fit's
      real strength/layer (confidence is LOW-at-best per methodology §1.2).
  R19 per-field capture_status gate (spine-3 §1.4 plan B, PO-decided 2026-07-31, D-348):
      a. params_capture_status present, key set EXACTLY the 7 PARAM_FIELDS;
      b. every entry carries status in CAPTURE_STATUSES + a non-empty reason;
      c. status == CAPTURED  <=>  params[field] is not null — BOTH directions. Left-to-right stops
         a flip from whitewashing an uncaptured field; right-to-left stops a distribution appearing
         with no status behind it;
      d. the by-caliber rulings are frozen: token_interval / think_pause = PENDING-BY-CALIBER
         (needs root mitm, outside D-24's red line), tool_loop_cadence = N/A-BY-CALIBER (consumer
         chat apps orchestrate no tools — this methodology can never capture it);
      e. no half-flip: once source_portrait leaves PENDING-CAPTURE it must match a traceable
         capture id AND no field may still read plain PENDING.
  Mode: source_portrait == "PENDING-CAPTURE" => PENDING mode (R1 all-null applies); anything else
      => CAPTURED mode, where R1 is replaced by R19c per-field consistency. Without this, a
      legitimate flip would be judged FAIL by R1/R2 and the gate could never open honestly.
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
SOURCE_LAYERS = {"network", "ui", "none"}          # R18: provenance layer (api excluded: App portraits
#   never source from the API-direct token layer — that's the ApiProbe gate, §6 口径 boundary).
CONFIDENCE = {"LOW", "INCONCLUSIVE"}                # R18: matches observed-layer + methodology vocabulary
#   ("LOW/INCONCLUSIVE"); LLM-portrait confidence is LOW-at-best (§1.2), INCONCLUSIVE when PENDING.
# R18: caliber -> (expected source_layer, expected confidence). Provenance must track caliber so the
# metadata cannot silently drift off the fit's real strength/layer.
CALIBER_PROVENANCE = {
    "none": ("none", "INCONCLUSIVE"),
    "ui-proxy": ("ui", "LOW"),
    "order-of-magnitude": ("network", "LOW"),
    "direct": ("network", "LOW"),
}
# R19: per-field capture gate vocabulary (spine-3 plan B). The two "-BY-CALIBER" values are NOT
# synonyms: N/A means this methodology can never reach it (no future capture changes that);
# PENDING-BY-CALIBER means reachable only outside the current red line (root mitm), so we decline
# to capture it — a later PO authorization could still turn it CAPTURED. Only plain PENDING blocks
# the source_portrait flip; otherwise one permanently-unreachable field freezes the gate forever
# (that is exactly the plan-A defect this replaces).
CAPTURE_STATUSES = {"PENDING", "PENDING-BY-CALIBER", "N/A-BY-CALIBER", "CAPTURED"}
BLOCKING_STATUSES = {"PENDING"}
# R19d — the 2026-07-31 PO rulings, frozen machine-side so a later edit cannot quietly promote a
# field the methodology cannot honestly reach.
RULED_STATUS = {
    "token_interval_ms_dist": "PENDING-BY-CALIBER",
    "think_pause_ms_dist": "PENDING-BY-CALIBER",
    "tool_loop_cadence": "N/A-BY-CALIBER",
}
# R19e — a flipped source_portrait must name a traceable capture, e.g. kimi-app-capture-2026-08-15.
CAPTURE_ID = re.compile(r"^[a-z0-9_]+-app-capture-\d{4}-\d{2}-\d{2}$")
PENDING_PORTRAIT = "PENDING-CAPTURE"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6 = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,}[0-9a-fA-F]{0,4}\b")


def _has_ip(s):
    return bool(IPV4.search(s) or IPV6.search(s))


def portrait_mode(d):
    """PENDING while source_portrait is the sentinel; CAPTURED once it names a capture."""
    return "PENDING" if d.get("source_portrait") == PENDING_PORTRAIT else "CAPTURED"


def gate_state(app, d):
    """(ready_to_flip, blockers) — the plan-B flip criterion, computed from capture_status.

    Blockers are only the plain-PENDING fields: a field ruled N/A-BY-CALIBER or
    PENDING-BY-CALIBER is honestly out of reach, and letting it block would freeze the
    gate forever (the plan-A defect). main() prints this so the status has a consumer
    an operator acts on, not just a guard that reads it.
    """
    st = d.get("params_capture_status", {}) or {}
    blockers = sorted(k for k in PARAM_FIELDS
                      if (st.get(k) or {}).get("status") in BLOCKING_STATUSES)
    return (not blockers), blockers


def check_portrait(app, d):
    """Single-portrait dict -> list of violation strings (pure, no IO). Carries R1-R20."""
    v = []

    def bad(cond, rule, msg):
        if not cond:
            v.append(f"[{app}] {rule}: {msg}")

    params = d.get("params", {}) or {}
    mode = portrait_mode(d)
    st = d.get("params_capture_status") or {}
    # R1 — no params field may carry a value without a CAPTURED status behind it. This is the
    # original all-null red line generalised for plan B: before D-348 every status was PENDING,
    # so "filled requires CAPTURED" and "all null" said the same thing. Stated this way, a field
    # that genuinely reached its sample threshold can be unlocked ON ITS OWN (plan B's whole
    # point) while every other field stays null and blocking. The converse direction
    # (CAPTURED but null) is R19c — one defect, one rule name, never both (§2.14).
    unbacked = [k for k in PARAM_FIELDS
                if params.get(k) is not None and (st.get(k) or {}).get("status") != "CAPTURED"]
    bad(not unbacked, "R1", f"params filled with no CAPTURED status behind them: {unbacked}")
    # R2 — the sentinel, or a traceable capture id; never a free-form string
    sp = d.get("source_portrait")
    bad(sp == PENDING_PORTRAIT or bool(CAPTURE_ID.match(str(sp))), "R2",
        f"source_portrait={sp} (must be {PENDING_PORTRAIT} or <app>-app-capture-YYYY-MM-DD)")
    # R9
    bad(bool(SEMVER.match(str(d.get("schema_version", "")))), "R9",
        f"schema_version={d.get('schema_version')} not semver")

    v += _check_capture_status(app, d, params, mode)
    v += _check_ui_dist(app, d)

    pf = d.get("params_fit_approx")
    if pf is None:
        return v  # portrait may predate D-62 fit; R1/R2/R9/R19 still enforced
    # R3 — the fit segment never gates params (any mode); unlocked tracks the mode so the
    # two cannot disagree about whether this portrait has flipped.
    bad(pf.get("gates_params") is False, "R3", f"gates_params={pf.get('gates_params')} (must be false)")
    bad(pf.get("source_portrait_unlocked") is (mode == "CAPTURED"), "R3",
        f"source_portrait_unlocked={pf.get('source_portrait_unlocked')} (must be {mode == 'CAPTURED'} in {mode} mode)")
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
        # R18 — provenance metadata present AND consistent with caliber (traceability §1.5;
        # confidence LOW-at-best per §1.2, NONE for PENDING/none-caliber fields).
        prov_missing = [k for k in ("source_layer", "confidence", "note") if k not in fl]
        bad(not prov_missing, "R18", f"{name} missing provenance keys {prov_missing}")
        sl = fl.get("source_layer"); conf = fl.get("confidence")
        bad(sl in SOURCE_LAYERS, "R18", f"{name} source_layer={sl} not in {sorted(SOURCE_LAYERS)}")
        bad(conf in CONFIDENCE, "R18", f"{name} confidence={conf} not in {sorted(CONFIDENCE)}")
        exp = CALIBER_PROVENANCE.get(cal)
        if exp is not None:
            bad(sl == exp[0], "R18", f"{name} caliber={cal} requires source_layer={exp[0]} (got {sl})")
            bad(conf == exp[1], "R18", f"{name} caliber={cal} requires confidence={exp[1]} (got {conf})")
    return v


# R20 — observed_ui_layer.dist (INSTRUMENTATION_SPEC §4.5; brain ruling 6-7, 2026-08-01).
#
# The whole point of this section is that a single value is not a distribution. doubao's
# ttft_ui_ms 1984 came from two runs that agreed (D-52/D-54) — agreement is a good sign and
# still not a distribution. So the rule is: the section may be ABSENT (that is the honest state
# while samples are short), but once present it must be complete. "Absent" and "present with
# nulls" say different things, exactly as PENDING and N/A-BY-CALIBER do on the params side
# (D-348) — a half-filled dist reads as "we measured this" to every downstream reader.
#
# Thresholds are the evidence ladder from the spine-3 blueprint §1.2, named once here so a
# later edit changes them in one place rather than being re-typed at each call site (D-264).
DIST_MIN_N = 30            # >=30 turns
DIST_MIN_SESSIONS = 5      # >=5 sessions
DIST_MIN_NETWORKS = 2      # >=2 network conditions (e.g. WiFi + 5G)
DIST_METRIC_KEYS = ("p50", "p90", "p99", "n", "sessions", "networks")
# Scalar companions of the metric entries — they are not distributions and must not be
# checked as such.
DIST_META_KEYS = ("method", "captured_at")


def _check_ui_dist(app, d):
    """R20 — observed_ui_layer.dist: absent is fine, half-filled is not. Pure, no IO."""
    v = []

    def bad(cond, rule, msg):
        if not cond:
            v.append(f"[{app}] {rule}: {msg}")

    ui = d.get("observed_ui_layer")
    if not isinstance(ui, dict) or "dist" not in ui:
        return v  # absent = the honest state while samples are short; not a violation
    dist = ui.get("dist")
    # R20a — present means present. A null/empty dist is the "half-filled" state this rule exists
    # to forbid: it looks like a section and carries nothing.
    bad(isinstance(dist, dict) and bool(dist), "R20a",
        "observed_ui_layer.dist present but not a non-empty mapping "
        "(omit the whole section instead of writing an empty one)")
    if not isinstance(dist, dict) or not dist:
        return v
    # R20b — the scalar companions must be there; a distribution whose method is unknown cannot
    # be compared with the next one (§1.6: every value carries its method tag).
    for k in DIST_META_KEYS:
        bad(dist.get(k) is not None, "R20b", f"dist.{k} missing or null")
    metrics = [k for k in dist if k not in DIST_META_KEYS]
    bad(bool(metrics), "R20b", "dist carries no metric entry")
    for name in sorted(metrics):
        e = dist.get(name)
        if not isinstance(e, dict):
            bad(False, "R20c", f"dist.{name} is not a mapping")
            continue
        # R20c — no nulls, no missing keys. This is the rule the brain named.
        missing = [k for k in DIST_METRIC_KEYS if e.get(k) is None]
        bad(not missing, "R20c", f"dist.{name} has null/missing {missing}")
        if missing:
            continue
        # R20d — below the evidence ladder it is not a distribution, it is a few readings.
        # Writing it anyway is how "n=3" ends up quoted as a p99 downstream.
        bad(isinstance(e["n"], int) and e["n"] >= DIST_MIN_N, "R20d",
            f"dist.{name}.n={e['n']} < {DIST_MIN_N} turns (blueprint §1.2 ladder)")
        bad(isinstance(e["sessions"], int) and e["sessions"] >= DIST_MIN_SESSIONS, "R20d",
            f"dist.{name}.sessions={e['sessions']} < {DIST_MIN_SESSIONS}")
        nets = e["networks"]
        bad(isinstance(nets, list) and len(nets) >= DIST_MIN_NETWORKS
            and all(isinstance(s, str) and s.strip() for s in nets), "R20d",
            f"dist.{name}.networks={nets} needs >={DIST_MIN_NETWORKS} named conditions")
        # R20e — percentiles must be ordered. An unordered triple is not a mis-typed number,
        # it is a sign the three came from different pools.
        try:
            bad(float(e["p50"]) <= float(e["p90"]) <= float(e["p99"]), "R20e",
                f"dist.{name} percentiles not ascending: "
                f"p50={e['p50']} p90={e['p90']} p99={e['p99']}")
        except (TypeError, ValueError):
            bad(False, "R20e", f"dist.{name} percentiles not numeric")
    return v


def _check_capture_status(app, d, params, mode):
    """R19 — per-field capture gate (spine-3 plan B). Split out because it is the one
    invariant that reads three places at once (status block, params, source_portrait)."""
    v = []

    def bad(cond, rule, msg):
        if not cond:
            v.append(f"[{app}] {rule}: {msg}")

    st = d.get("params_capture_status")
    # R19a — presence + exact key set. Absent is a violation, not a skip: a portrait with no
    # status block has no gate criterion at all, and "no criterion" reads as "nothing blocking".
    bad(isinstance(st, dict), "R19a", "params_capture_status missing (plan-B gate has no criterion)")
    if not isinstance(st, dict):
        return v
    bad(set(st.keys()) == set(PARAM_FIELDS), "R19a",
        f"params_capture_status key set != 7 PARAM_FIELDS: extra={sorted(set(st)-set(PARAM_FIELDS))} "
        f"missing={sorted(set(PARAM_FIELDS)-set(st))}")

    for name in PARAM_FIELDS:
        e = st.get(name) or {}
        status = e.get("status")
        # R19b — vocabulary + a reason. A status with no reason is a verdict nobody can audit.
        bad(status in CAPTURE_STATUSES, "R19b",
            f"{name} status={status} not in {sorted(CAPTURE_STATUSES)}")
        bad(bool(str(e.get("reason", "")).strip()), "R19b", f"{name} status carries no reason")
        # R19c — CAPTURED must be backed by a real value. The other direction (a value with no
        # CAPTURED behind it) is R1, deliberately not repeated here: two rule names for one
        # defect make a report where fixing one line clears two findings (§2.14).
        if status == "CAPTURED":
            bad(params.get(name) is not None, "R19c",
                f"{name} status=CAPTURED but params.{name} is null (claims a capture it has not got)")
        # R19d — frozen PO rulings
        ruled = RULED_STATUS.get(name)
        if ruled is not None:
            bad(status == ruled, "R19d",
                f"{name} status={status} but the 2026-07-31 ruling fixes it at {ruled}")
        # R19e — no half-flip
        if mode == "CAPTURED":
            bad(status != "PENDING", "R19e",
                f"{name} still PENDING while source_portrait has flipped (half-flip whitewashes it)")
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
    # Gate state per portrait — what an operator acts on: which fields still block the flip.
    for app in sorted(portraits):
        ready, blockers = gate_state(app, portraits[app])
        print(f"  gate[{app}]: " + ("READY to flip source_portrait (no PENDING fields left)"
                                    if ready else f"blocked by {len(blockers)}: {', '.join(blockers)}"))
    if violations:
        print(f"\nRED-LINE VIOLATIONS ({len(violations)}):")
        for x in violations:
            print("  -", x)
        return 1
    print("OK: all red-line invariants hold (R1-R20: params gate intact, no caliber overclaim, "
          "provenance consistent, per-field capture status backs every filled param).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
