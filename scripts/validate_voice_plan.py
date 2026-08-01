#!/usr/bin/env python3
"""ANEB Profile 4 voice execution-plan validator (stdlib only).

Why this exists at all
----------------------
`spec/profiles/client/voice_realtime_plan.json` is an EXPORT of the constants that
actually drive Profile 4 (they still live in `VoiceRunner`'s companion object; the
engine does not read this file). Its only value is that the two sides cannot drift
apart, and that value is exactly as strong as the guard over it.

The Kotlin-side guard `VoiceExecutionPlanParityTest.kt` is stronger in one respect
(it compares against the plan `defaultSimPlan()` actually GENERATES, not just the
constants) but it does not gate anything in practice, for two measured reasons:

  1. `verify_all.ps1` runs `:probe:assembleDebug`, NOT `:probe:testDebugUnitTest`
     -- the same gap its own comment at L90-91 already records for AdapterSpecTest.
  2. Even run by hand, Gradle marks `testDebugUnitTest` UP-TO-DATE when only a file
     OUTSIDE the module changed. Measured: three separate mutations of the spec file
     (interrupted turns 3,6 -> 2,5; derived kbps 64 -> 40; uplink frames 200 -> 199)
     ALL SURVIVED, and the task line read `> Task :probe:testDebugUnitTest UP-TO-DATE`.
     The tests were never executed.

So this checker is the one that actually runs in the gate. It does two things the
existing `validate_spec_scoring.py` deliberately does not: it checks the file's own
invariants AND it reads the Kotlin source to compare the exported numbers against
the constants they claim to mirror.

Extraction is regex over Kotlin source, which is brittle by nature. Every constant
this checker needs is REQUIRED: if a declaration form changes and the regex stops
matching, the run FAILS loudly rather than silently skipping the comparison. That is
deliberate -- a parity checker that quietly compares nothing is worse than none
(the shape D-325 records: a missing key must not masquerade as a value).

Checks
------
  parity  -- every exported constant equals its `VoiceRunner` companion counterpart
  derived -- `frame.derived_nominal_kbps` recomputed from bytes/interval, not trusted
  bounds  -- both plans inside the declared wire limits (turns, frame_ms range)
  sanity  -- barge-in lands inside the uplink; interrupted turns are real turn
             indices; the continuity disconnect turn is not the last planned turn
             (otherwise there is no turn after it and resume cannot be observed)

Exit: 0 = all invariants hold / 1 = violations / 2 = a required input is missing
(NOT_EXECUTED, mirroring validate_spec_scoring.py's degradation).

Usage:
    python validate_voice_plan.py [--spec <path>] [--kotlin <path>]
"""
import argparse
import json
import os
import re
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SPEC = os.path.join(
    _REPO, "spec", "profiles", "client", "voice_realtime_plan.json")
DEFAULT_KOTLIN = os.path.join(
    _REPO, "app", "probe", "src", "main", "java", "com", "aneb", "probe",
    "engine", "VoiceRunner.kt")

# Constant name -> how to read it out of the Kotlin source. Every entry is required;
# a miss is an error, never a skip.
_INT_CONSTS = (
    "FRAME_INTERVAL_MS",
    "FRAME_BYTES",
    "UPLINK_FRAMES",
    "DOWNLINK_FRAMES",
    "SIM_M3_FRAMES",
    "CONT_DISCONNECT_AFTER_TURN",
    "CONT_UPLINK_FRAMES",
    "CONT_DOWNLINK_FRAMES",
)
_STR_CONSTS = ("SIM_CALIBER",)


def extract_kotlin_constants(text):
    """Pull the companion constants out of VoiceRunner.kt.

    Returns (values, errors). A constant that cannot be found is an ERROR, not a
    None -- see the module docstring on why silence is the failure mode to avoid.
    """
    values, errs = {}, []
    for name in _INT_CONSTS:
        m = re.search(
            r"\bconst\s+val\s+%s\s*(?::\s*\w+\s*)?=\s*(\d+)L?\b" % re.escape(name),
            text)
        if m is None:
            errs.append("kotlin: const %s not found (declaration form changed?)" % name)
        else:
            values[name] = int(m.group(1))
    for name in _STR_CONSTS:
        m = re.search(
            r'\bconst\s+val\s+%s\s*(?::\s*\w+\s*)?=\s*"([^"]*)"' % re.escape(name),
            text)
        if m is None:
            errs.append("kotlin: const %s not found (declaration form changed?)" % name)
        else:
            values[name] = m.group(1)
    return values, errs


def extract_default_plan_literals(text):
    """Pull the numbers hard-coded inside defaultSimPlan()/continuitySimPlan().

    These are not `const val`s, so they can only be read positionally. Anything not
    found is reported; the caller decides severity.
    """
    out, errs = {}, []
    pats = {
        "default_turns": r"turns\s*=\s*\(0\s+until\s+(\d+)\)\.map",
        "default_uplink_frames": r"uplinkFrames\s*=\s*(\d+)\s*,",
        "default_response_wait_ms": r"responseWaitMs\s*=\s*(\d+)\s*,",
        "default_planned_downlink": r"plannedDownlinkFrames\s*=\s*(\d+)\s*,",
        "setup_ms": r"setupMs\s*=\s*([\d.]+)\s*,",
        "frame_ms": r"frameMs\s*=\s*(\d+)\s*,",
        "barge_in_after_frames": r"bargeInAfterFrames\s*=\s*if\s*\(interrupted\)\s*(\d+)",
        "expected_stop_within_ms": r"expectedStopWithinMs\s*=\s*if\s*\(interrupted\)\s*(\d+)",
    }
    for key, pat in pats.items():
        m = re.search(pat, text)
        if m is None:
            errs.append("kotlin: could not read %s (pattern %r)" % (key, pat))
        else:
            v = m.group(1)
            out[key] = float(v) if "." in v else int(v)
    m = re.search(r"val\s+interrupted\s*=\s*i\s*==\s*(\d+)\s*\|\|\s*i\s*==\s*(\d+)", text)
    if m is None:
        errs.append("kotlin: could not read interrupted turn indices")
    else:
        out["interrupted_turn_indices"] = sorted(int(g) for g in m.groups())
    return out, errs


def _eq(errs, label, expected, actual):
    if expected != actual:
        errs.append("%s: spec=%r kotlin=%r" % (label, actual, expected))


def check(spec, kconst, kplan):
    """Return a list of violation strings ([] means all invariants hold)."""
    errs = []
    frame = spec.get("frame") or {}
    v1 = spec.get("v1_paced_proxy") or {}
    v2 = spec.get("v2_server_sim") or {}
    plan = v2.get("default_plan") or {}
    cont = v2.get("continuity_plan") or {}
    limits = spec.get("wire_limits") or {}
    for name, obj in (("frame", frame), ("v1_paced_proxy", v1),
                      ("v2_server_sim", v2), ("default_plan", plan),
                      ("continuity_plan", cont), ("wire_limits", limits)):
        if not obj:
            errs.append("spec: section %r missing or empty" % name)
    if errs:
        return errs

    # ---- parity with the Kotlin companion ----
    _eq(errs, "frame.interval_ms", kconst["FRAME_INTERVAL_MS"], frame.get("interval_ms"))
    _eq(errs, "frame.bytes", kconst["FRAME_BYTES"], frame.get("bytes"))
    _eq(errs, "v1.uplink_frames", kconst["UPLINK_FRAMES"], v1.get("uplink_frames"))
    _eq(errs, "v1.downlink_frames", kconst["DOWNLINK_FRAMES"], v1.get("downlink_frames"))
    _eq(errs, "v2.m3_frames", kconst["SIM_M3_FRAMES"], v2.get("m3_frames"))
    _eq(errs, "v2.caliber", kconst["SIM_CALIBER"], v2.get("caliber"))
    _eq(errs, "continuity.disconnect_after_turn",
        kconst["CONT_DISCONNECT_AFTER_TURN"], cont.get("disconnect_after_turn"))
    _eq(errs, "continuity.uplink_frames_per_turn",
        kconst["CONT_UPLINK_FRAMES"], cont.get("uplink_frames_per_turn"))
    _eq(errs, "continuity.downlink_frames_per_turn",
        kconst["CONT_DOWNLINK_FRAMES"], cont.get("downlink_frames_per_turn"))

    # ---- parity with the literals inside the plan factories ----
    _eq(errs, "default_plan.turns", kplan["default_turns"], plan.get("turns"))
    _eq(errs, "default_plan.uplink_frames_per_turn",
        kplan["default_uplink_frames"], plan.get("uplink_frames_per_turn"))
    _eq(errs, "default_plan.response_wait_ms",
        kplan["default_response_wait_ms"], plan.get("response_wait_ms"))
    _eq(errs, "default_plan.planned_downlink_frames_per_turn",
        kplan["default_planned_downlink"], plan.get("planned_downlink_frames_per_turn"))
    _eq(errs, "default_plan.setup_ms", kplan["setup_ms"], plan.get("setup_ms"))
    _eq(errs, "default_plan.frame_ms", kplan["frame_ms"], plan.get("frame_ms"))
    _eq(errs, "default_plan.barge_in_after_frames",
        kplan["barge_in_after_frames"], plan.get("barge_in_after_frames"))
    _eq(errs, "default_plan.expected_stop_within_ms",
        kplan["expected_stop_within_ms"], plan.get("expected_stop_within_ms"))
    _eq(errs, "default_plan.interrupted_turn_indices",
        kplan["interrupted_turn_indices"],
        sorted(plan.get("interrupted_turn_indices") or []))

    # ---- derived value: recomputed, never trusted ----
    interval, nbytes = frame.get("interval_ms"), frame.get("bytes")
    if isinstance(interval, (int, float)) and isinstance(nbytes, (int, float)) and interval:
        want = nbytes * 8.0 / (interval / 1000.0) / 1000.0
        got = frame.get("derived_nominal_kbps")
        if not isinstance(got, (int, float)) or abs(want - got) > 1e-9:
            errs.append("frame.derived_nominal_kbps: stored=%r recomputed=%r"
                        % (got, want))

    # ---- bounds declared by the file itself ----
    max_turns = limits.get("max_turns")
    rng = limits.get("frame_ms_range")
    if isinstance(max_turns, int):
        for label, turns in (("default_plan", plan.get("turns")),
                             ("continuity_plan", cont.get("turns"))):
            if isinstance(turns, int) and turns > max_turns:
                errs.append("%s.turns=%d exceeds wire_limits.max_turns=%d"
                            % (label, turns, max_turns))
    if isinstance(rng, list) and len(rng) == 2:
        for label, fm in (("default_plan", plan.get("frame_ms")),
                          ("continuity_plan", cont.get("frame_ms"))):
            if isinstance(fm, int) and not (rng[0] <= fm <= rng[1]):
                errs.append("%s.frame_ms=%d outside wire_limits.frame_ms_range=%r"
                            % (label, fm, rng))

    # ---- sanity the numbers themselves imply ----
    up = plan.get("uplink_frames_per_turn")
    barge = plan.get("barge_in_after_frames")
    if isinstance(up, int) and isinstance(barge, int) and barge > up:
        errs.append("barge_in_after_frames=%d is past the end of the uplink "
                    "(uplink_frames_per_turn=%d) -- the interruption could never fire"
                    % (barge, up))
    turns = plan.get("turns")
    if isinstance(turns, int):
        bad = [i for i in (plan.get("interrupted_turn_indices") or [])
               if not isinstance(i, int) or not (0 <= i < turns)]
        if bad:
            errs.append("interrupted_turn_indices %r are not valid turn indices "
                        "for turns=%d" % (bad, turns))
    ct, dt = cont.get("turns"), cont.get("disconnect_after_turn")
    if isinstance(ct, int) and isinstance(dt, int) and dt >= ct - 1:
        errs.append("continuity disconnect_after_turn=%d is the last planned turn "
                    "(turns=%d) -- nothing follows it, so resume cannot be observed"
                    % (dt, ct))
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", default=DEFAULT_SPEC)
    ap.add_argument("--kotlin", default=DEFAULT_KOTLIN)
    args = ap.parse_args(argv)

    for path, what in ((args.spec, "spec"), (args.kotlin, "kotlin source")):
        if not os.path.isfile(path):
            print("NOT_EXECUTED: %s not found: %s" % (what, path), file=sys.stderr)
            return 2
    try:
        with open(args.spec, encoding="utf-8-sig") as fh:
            spec = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        print("spec parse error: %s" % e, file=sys.stderr)
        return 1
    try:
        with open(args.kotlin, encoding="utf-8-sig") as fh:
            ktext = fh.read()
    except OSError as e:
        print("kotlin read error: %s" % e, file=sys.stderr)
        return 1

    kconst, e1 = extract_kotlin_constants(ktext)
    kplan, e2 = extract_default_plan_literals(ktext)
    errs = list(e1) + list(e2)
    if not errs:
        errs = check(spec, kconst, kplan)

    if errs:
        print("voice plan parity: %d violation(s)" % len(errs), file=sys.stderr)
        for e in errs:
            print("  - %s" % e, file=sys.stderr)
        return 1
    print("voice plan parity OK: %d constants + %d plan literals matched"
          % (len(kconst), len(kplan)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
