#!/usr/bin/env python3
"""ANEB profile validator: spec<->runtime parity + phase structure (stdlib only).

The inline verify_all `profiles-valid` step checks only the RUNTIME copy for four
present fields + non-empty phases. It never checks the spec authority copy, never
spec<->runtime parity, and never phase internals — so a semantic edit to one copy
but not the other, or a phase missing a required numeric field, slips through.
client_profiles.json has a byte-parity guard; the server profiles have none.

This deepens that gate (铁律1「Profile 即数据」; §7 先改 spec 后动代码):

  (a) PARITY — for each profile, the spec copy (spec/profiles/server/<id>.json) and
      the runtime mirror (profiles/<id>.json) must be SEMANTICALLY equal (parsed
      JSON compared; robust to CRLF/whitespace/key-order, which byte-parity is not).
      Present on one side only is an error.
  (b) STRUCTURE — top-level required fields, and each phase's `type` is known and
      carries its required, correctly-typed fields.

Read-only over both trees. Exit: 0 = PASS / 1 = violations / 2 = a tree is absent
(NOT_EXECUTED).

Usage:
    python validate_profiles.py [--spec spec/profiles/server] [--runtime profiles]
"""
import argparse
import json
import os
import sys

TOP_REQUIRED = ("profile_id", "version", "kpi_set", "phases")

# phase type -> {field: kind}. kind: 'num' (int/float, not bool), 'int', 'map'.
PHASE_SPEC = {
    "clock_sync":    {"samples": "int"},
    "upload_burst":  {"bytes": "num", "chunk_kb": "num"},
    "download_burst": {"bytes": "num", "chunk_kb": "num"},
    "think_pause":   {"duration_ms": "num"},
    "token_stream":  {"tokens": "num", "rate_tps": "num", "token_bytes": "map"},
    "tool_loop":     {"rounds": "num", "up_bytes": "num", "down_bytes": "num",
                      "server_proc_ms": "num"},
}
DEFAULT_SPEC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "spec", "profiles", "server")
DEFAULT_RUNTIME = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "profiles")


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _kind_ok(v, kind):
    if kind == "int":
        return isinstance(v, int) and not isinstance(v, bool)
    if kind == "num":
        return _is_num(v)
    if kind == "map":
        return isinstance(v, dict)
    return False


def check_structure(profile, name):
    """Top-level required fields + per-phase type/field checks. -> [errors]."""
    errs = []
    if not isinstance(profile, dict):
        return [f"{name}: not a JSON object"]
    for field in TOP_REQUIRED:
        if profile.get(field) in (None, ""):
            errs.append(f"{name}: missing '{field}'")
    phases = profile.get("phases")
    if not isinstance(phases, list) or not phases:
        errs.append(f"{name}: 'phases' must be a non-empty array")
        return errs
    for i, ph in enumerate(phases):
        if not isinstance(ph, dict):
            errs.append(f"{name}.phases[{i}]: not an object")
            continue
        ptype = ph.get("type")
        if ptype not in PHASE_SPEC:
            errs.append(f"{name}.phases[{i}]: unknown phase type {ptype!r}")
            continue
        for field, kind in PHASE_SPEC[ptype].items():
            if field not in ph:
                errs.append(f"{name}.phases[{i}] ({ptype}): missing '{field}'")
            elif not _kind_ok(ph[field], kind):
                errs.append(f"{name}.phases[{i}] ({ptype}): '{field}'="
                            f"{ph[field]!r} not a {kind}")
    return errs


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_dirs(spec_dir, runtime_dir):
    """Validate parity + structure across both trees. Returns [errors]."""
    errs = []
    spec_files = {f for f in os.listdir(spec_dir) if f.endswith(".json")} \
        if os.path.isdir(spec_dir) else set()
    runtime_files = {f for f in os.listdir(runtime_dir) if f.endswith(".json")} \
        if os.path.isdir(runtime_dir) else set()

    for name in sorted(spec_files - runtime_files):
        errs.append(f"{name}: in spec but missing from runtime (profiles/)")
    for name in sorted(runtime_files - spec_files):
        errs.append(f"{name}: in runtime but missing from spec (spec/profiles/server/)")

    for name in sorted(spec_files & runtime_files):
        try:
            spec_obj = _load(os.path.join(spec_dir, name))
        except (OSError, json.JSONDecodeError) as e:
            errs.append(f"spec/{name}: parse error: {e}")
            spec_obj = None
        try:
            rt_obj = _load(os.path.join(runtime_dir, name))
        except (OSError, json.JSONDecodeError) as e:
            errs.append(f"runtime/{name}: parse error: {e}")
            rt_obj = None
        if spec_obj is None or rt_obj is None:
            continue
        # (a) semantic parity — parsed equality ignores CRLF/whitespace/key order
        if spec_obj != rt_obj:
            errs.append(f"{name}: spec<->runtime content DIVERGES (semantic mismatch)")
        # (b) structure (validate the spec authority copy)
        errs.extend(check_structure(spec_obj, name))
    return errs


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB profile spec<->runtime + structure validator")
    ap.add_argument("--spec", default=DEFAULT_SPEC)
    ap.add_argument("--runtime", default=DEFAULT_RUNTIME)
    args = ap.parse_args(argv)

    if not os.path.isdir(args.spec) or not os.path.isdir(args.runtime):
        missing = [d for d in (args.spec, args.runtime) if not os.path.isdir(d)]
        print(f"profile tree(s) absent: {missing}", file=sys.stderr)
        return 2

    errors = validate_dirs(args.spec, args.runtime)
    if not errors:
        n = len([f for f in os.listdir(args.spec) if f.endswith(".json")])
        print(f"profiles OK: {n} profile(s) - spec<->runtime parity + phase structure hold")
        return 0
    print(f"profiles VIOLATIONS: {len(errors)}")
    for e in errors:
        print(f"  - {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
