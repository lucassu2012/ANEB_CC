#!/usr/bin/env python3
"""ANEB result JSONL contract validator (stdlib only).

The analysis layer has no front door: campaign_common.load_records tolerates
anything and degrades on missing fields, so a malformed producer change reaches
the report as quietly wrong numbers. This is the gate that fails loudly instead.

Two layers of checking:

1. STRUCTURAL — the schema's own constraints, read live from
   spec/schemas/result-run.schema.json (required-field lists per object, the
   claim_scope const, the validity enum). No jsonschema dependency: the required
   arrays are read from the schema file so this can never drift out of sync with
   it, but the traversal is hand-rolled stdlib.

2. CROSS-FIELD (R-10) — invariants draft-07 cannot express, which are exactly the
   ones that make aggregates silently wrong if violated:
     * kpi value null  <=>  its <k>_grade null   (a graded null / an ungraded value)
     * aqs.score null  <=>  not_computable_reason present (a null with no reason,
                            or a reason attached to a real score)
     * itl_histogram: len(counts) == len(edges_ms) + 1   (open-ended bins, R-27)

Exit: 0 = all records valid / 1 = violations found / 2 = could not run
(schema unreadable, no records). Wires into verify_all as results-contract-unit.

Usage:
    python validate_results.py results/*.jsonl [--schema PATH] [--max-report N]
"""
import argparse
import json
import math
import os
import sys

import campaign_common as cc

DEFAULT_SCHEMA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "spec", "schemas", "result-run.schema.json")
# KPI ids whose value<->grade coupling we enforce (grade field = <prefix>_grade).
GRADED_KPIS = ("t1_ttft_ms", "t2_itl_p95_ms", "t3_stall_rate", "t4_severe_stall_rate",
               "n1_rtt_p50_ms", "n2_jitter_ms", "u1_goodput_mbps", "u2_tool_loop_p95_ms")


def load_schema(path):
    """Read the required-field lists + enums we enforce from the schema file, so
    this validator tracks the contract instead of hard-coding a second copy."""
    with open(path, encoding="utf-8") as f:
        schema = json.load(f)
    props = schema.get("properties", {})
    defs = schema.get("definitions", {})
    scenario = defs.get("scenario", {})
    scn_props = scenario.get("properties", {})
    run_schema = props.get("run", {})
    return {
        "top_required": schema.get("required", []),
        "claim_scope_const": props.get("claim_scope", {}).get("const"),
        "run_required": run_schema.get("required", []),
        "aqs_required": run_schema.get("properties", {}).get("aqs", {}).get("required", []),
        "scenario_required": scenario.get("required", []),
        "validity_enum": scn_props.get("validity", {}).get("enum", []),
        "kpi_required": scn_props.get("kpi", {}).get("required", []),
        "hist_required": scn_props.get("itl_histogram", {}).get("required", []),
    }


def _err(out, path, msg):
    out.append(("error", f"{path}: {msg}"))


def _warn(out, path, msg):
    out.append(("warn", f"{path}: {msg}"))


def _require(obj, keys, path, out):
    if not isinstance(obj, dict):
        _err(out, path, f"expected object, got {type(obj).__name__}")
        return False
    for k in keys:
        if k not in obj:
            _err(out, path, f"missing required field '{k}'")
    return True


def _is_null(v):
    return v is None


def validate_record(rec, sch, idx):
    """Return a list of (severity, message) findings for one record.

    severity 'error' fails the gate (exit 1); 'warn' is advisory (exit 0) — used
    for known schema/producer drift that is not the data's fault to fix.
    """
    f = []
    tag = f"record[{idx}]"
    if not isinstance(rec, dict):
        return [("error", f"{tag}: not a JSON object")]

    _require(rec, sch["top_required"], tag, f)
    if sch["claim_scope_const"] is not None and "claim_scope" in rec:
        if rec.get("claim_scope") != sch["claim_scope_const"]:
            _err(f, f"{tag}.claim_scope",
                 f"must be '{sch['claim_scope_const']}', got {rec.get('claim_scope')!r}")

    run = rec.get("run")
    if isinstance(run, dict):
        _require(run, sch["run_required"], f"{tag}.run", f)
        aqs = run.get("aqs")
        if isinstance(aqs, dict):
            _require(aqs, sch["aqs_required"], f"{tag}.run.aqs", f)
            # R-10: score null <=> a reason is present.
            score_null = _is_null(aqs.get("score"))
            reason = aqs.get("not_computable_reason")
            has_reason = isinstance(reason, str) and reason.strip() != ""
            if score_null and not has_reason:
                _err(f, f"{tag}.run.aqs", "score is null but not_computable_reason is empty (R-10)")
            if not score_null and has_reason:
                _err(f, f"{tag}.run.aqs", f"score present ({aqs.get('score')}) yet "
                     f"not_computable_reason set ({reason!r}) — contradictory")
    elif "run" in rec:
        _err(f, f"{tag}.run", "expected object")

    scns = rec.get("scenarios")
    if isinstance(scns, list):
        for si, scn in enumerate(scns):
            f.extend(validate_scenario(scn, sch, f"{tag}.scenarios[{si}]"))
    elif "scenarios" in rec:
        _err(f, f"{tag}.scenarios", "expected array")
    return f


def validate_scenario(scn, sch, path):
    f = []
    if not _require(scn, sch["scenario_required"], path, f):
        return f

    validity = scn.get("validity")
    enum = sch["validity_enum"]
    if enum:
        # The three STATES are the contract; the schema enum is upper-case but the
        # producer (ResultReporter) emits lower-case — a known schema/producer
        # drift (see campaign_common.scenario_validity). Compare case-insensitively
        # so real data passes; surface the casing mismatch as a non-fatal advisory
        # for the schema owner, and fail only a genuinely unknown state.
        low = {e.lower() for e in enum}
        got = validity.lower() if isinstance(validity, str) else validity
        if got not in low:
            _err(f, f"{path}.validity", f"'{validity}' not in {enum} (case-insensitive)")
        elif isinstance(validity, str) and validity not in enum:
            _warn(f, f"{path}.validity",
                  f"'{validity}' matches a valid state only by case-fold; schema enum "
                  f"is {enum} — schema/producer case drift")

    kpi = scn.get("kpi")
    if isinstance(kpi, dict):
        _require(kpi, sch["kpi_required"], f"{path}.kpi", f)
        # R-10: value null <=> grade null (no graded nulls, no ungraded values).
        for k in GRADED_KPIS:
            if k not in kpi:
                continue
            gfield = k.split("_")[0] + "_grade"
            if gfield not in kpi:
                continue
            if _is_null(kpi.get(k)) != _is_null(kpi.get(gfield)):
                _err(f, f"{path}.kpi", f"{k}={kpi.get(k)!r} but {gfield}="
                     f"{kpi.get(gfield)!r} (value/grade nullness must match, R-10)")
    elif "kpi" in scn:
        _err(f, f"{path}.kpi", "expected object")

    hist = scn.get("itl_histogram")
    if isinstance(hist, dict):
        _require(hist, sch["hist_required"], f"{path}.itl_histogram", f)
        edges, counts = hist.get("edges_ms"), hist.get("counts")
        if isinstance(edges, list) and isinstance(counts, list):
            if len(counts) != len(edges) + 1:
                _err(f, f"{path}.itl_histogram", f"len(counts)={len(counts)} must equal "
                     f"len(edges_ms)+1={len(edges) + 1} (open-ended bins, R-27)")
    elif "itl_histogram" in scn:
        _err(f, f"{path}.itl_histogram", "expected object")
    return f


def _nonfinite_paths(node, path="", out=None):
    """Every NaN/±Infinity leaf, with its dotted path.

    JSON has no such literals, but Python's json module emits and accepts the
    bare words by default, so a producer or a converting tool can put them in a
    corpus. The aggregates now refuse them (D-148), which keeps the numbers
    honest — but "silently not computable" is not the same as telling the
    operator the corpus is broken, so the gate names them.
    """
    out = [] if out is None else out
    if isinstance(node, dict):
        for k, v in node.items():
            _nonfinite_paths(v, f"{path}.{k}" if path else str(k), out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _nonfinite_paths(v, f"{path}[{i}]", out)
    elif isinstance(node, float) and not math.isfinite(node):
        out.append(f"{path}={node}")
    return out


def validate_records(records, sch):
    """Return (errors, warnings) as two lists of message strings."""
    findings = []
    for i, rec in enumerate(records):
        findings.extend(validate_record(rec, sch, i))
        bad = _nonfinite_paths(rec)
        if bad:
            findings.append(("error", f"record[{i}]: 非法数值（JSON 不允许 NaN/Infinity）"
                                      f"：{', '.join(bad[:5])}"
                                      + (f" 等共 {len(bad)} 处" if len(bad) > 5 else "")))
    errors = [m for sev, m in findings if sev == "error"]
    warnings = [m for sev, m in findings if sev == "warn"]
    return errors, warnings


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB result JSONL contract validator")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--schema", default=DEFAULT_SCHEMA)
    ap.add_argument("--max-report", type=int, default=50, help="max violations to print")
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    try:
        sch = load_schema(args.schema)
    except (OSError, json.JSONDecodeError) as e:
        print(f"cannot read schema {args.schema}: {e}", file=sys.stderr)
        return 2

    recs, files = cc.load_records(args.inputs)
    if not recs:
        print("no records loaded", file=sys.stderr)
        return 2

    errors, warnings = validate_records(recs, sch)

    # De-duplicate advisories (e.g. the same schema case-drift on every scenario).
    seen, uniq_warn = set(), []
    for w in warnings:
        key = w.split(":", 1)[-1].strip()
        if key not in seen:
            seen.add(key)
            uniq_warn.append(w)
    if uniq_warn:
        print(f"advisories (non-fatal, {len(warnings)} occurrence(s), "
              f"{len(uniq_warn)} distinct):")
        for line in uniq_warn[:args.max_report]:
            print(f"  ~ {line}")

    if not errors:
        print(f"contract OK: {len(recs)} record(s) across {len(files)} file(s) — "
              "structural + R-10 cross-field invariants hold")
        return 0
    print(f"contract VIOLATIONS: {len(errors)} in {len(recs)} record(s)")
    for line in errors[:args.max_report]:
        print(f"  - {line}")
    if len(errors) > args.max_report:
        print(f"  … and {len(errors) - args.max_report} more")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
