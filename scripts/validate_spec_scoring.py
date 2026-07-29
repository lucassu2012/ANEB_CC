#!/usr/bin/env python3
"""ANEB spec scoring-pack validator (pyyaml; NOT_EXECUTED without it).

The authoritative guard over the scoring rule pack — SpecScoringParityTest.kt — is
Android-toolchain-gated, so in the usual (no-Android) verify_all run it is
NOT_EXECUTED and spec/scoring/{weights,anchors,vetoes}.yaml have ZERO enforced
gate. This is a stdlib-adjacent (pyyaml-only) checker of the invariants those
files themselves declare, wired as verify_all step spec-scoring-unit.

Checks (each file's own stated contract, read-only):
  weights.yaml  — every table's weights sum to 1.0 (±1e-9); weights are numbers;
                  each table carries a version_id.
  anchors.yaml  — each anchor's `points` are [value, score] pairs STRICTLY ascending
                  by value; direction ∈ {lower_better, higher_better}; scores 0..100.
  vetoes.yaml   — each veto has metric/comparator/threshold/cap/kind; comparator ∈
                  {<,>,<=,>=}; kind ∈ {hard, soft}; cap is a number in 0..100.

Exit: 0 = all invariants hold / 1 = violations / 2 = pyyaml missing or files absent
(NOT_EXECUTED, mirroring spec/portraits/validate_schema.py's degradation).

Usage:
    python validate_spec_scoring.py [--dir spec/scoring]
"""
import argparse
import os
import sys

_SUM_TOL = 1e-9
_DIRECTIONS = {"lower_better", "higher_better"}
_COMPARATORS = {"<", ">", "<=", ">="}
_KINDS = {"hard", "soft"}
DEFAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "spec", "scoring")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_weights(doc):
    """Validate a parsed weights.yaml dict. Returns a list of error strings."""
    errs = []
    tables = (doc or {}).get("tables")
    if not isinstance(tables, dict) or not tables:
        return ["weights: 'tables' missing or empty"]
    for name, tbl in tables.items():
        if not isinstance(tbl, dict):
            errs.append(f"weights.{name}: not a mapping")
            continue
        if not isinstance(tbl.get("version_id"), str) or not tbl.get("version_id"):
            errs.append(f"weights.{name}: missing version_id")
        weights = tbl.get("weights")
        if not isinstance(weights, dict) or not weights:
            errs.append(f"weights.{name}: 'weights' missing or empty")
            continue
        bad = [k for k, v in weights.items() if not _num(v)]
        if bad:
            errs.append(f"weights.{name}: non-numeric weights {bad}")
            continue
        total = sum(weights.values())
        if abs(total - 1.0) > _SUM_TOL:
            errs.append(f"weights.{name}: Σ weights = {total!r}, must be 1.0 (±{_SUM_TOL})")
    return errs


def check_anchors(doc):
    """Validate a parsed anchors.yaml dict. Returns a list of error strings."""
    errs = []
    anchors = (doc or {}).get("anchors")
    if not isinstance(anchors, dict) or not anchors:
        return ["anchors: 'anchors' missing or empty"]
    for name, a in anchors.items():
        if not isinstance(a, dict):
            errs.append(f"anchors.{name}: not a mapping")
            continue
        direction = a.get("direction")
        if direction not in _DIRECTIONS:
            errs.append(f"anchors.{name}: direction {direction!r} not in {sorted(_DIRECTIONS)}")
        points = a.get("points")
        if not isinstance(points, list) or len(points) < 2:
            errs.append(f"anchors.{name}: 'points' must be a list of >= 2 [value, score] pairs")
            continue
        prev = None
        ok = True
        for i, pt in enumerate(points):
            if not (isinstance(pt, list) and len(pt) == 2 and _num(pt[0]) and _num(pt[1])):
                errs.append(f"anchors.{name}.points[{i}]: not a numeric [value, score] pair")
                ok = False
                break
            if not (0.0 <= pt[1] <= 100.0):
                errs.append(f"anchors.{name}.points[{i}]: score {pt[1]} out of 0..100")
            if prev is not None and not (pt[0] > prev):
                errs.append(f"anchors.{name}.points[{i}]: value {pt[0]} not > previous {prev} "
                            "(must be strictly ascending)")
                ok = False
                break
            prev = pt[0]
        if not ok:
            continue
    return errs


def check_vetoes(doc):
    """Validate a parsed vetoes.yaml dict. Returns a list of error strings."""
    errs = []
    vetoes = (doc or {}).get("vetoes")
    if not isinstance(vetoes, dict) or not vetoes:
        return ["vetoes: 'vetoes' missing or empty"]
    for name, v in vetoes.items():
        if not isinstance(v, dict):
            errs.append(f"vetoes.{name}: not a mapping")
            continue
        for field in ("metric", "comparator", "threshold", "cap", "kind"):
            if field not in v:
                errs.append(f"vetoes.{name}: missing '{field}'")
        if v.get("comparator") not in _COMPARATORS:
            errs.append(f"vetoes.{name}: comparator {v.get('comparator')!r} not in "
                        f"{sorted(_COMPARATORS)}")
        if v.get("kind") not in _KINDS:
            errs.append(f"vetoes.{name}: kind {v.get('kind')!r} not in {sorted(_KINDS)}")
        if "threshold" in v and not _num(v.get("threshold")):
            errs.append(f"vetoes.{name}: threshold not numeric")
        cap = v.get("cap")
        if "cap" in v and (not _num(cap) or not (0.0 <= cap <= 100.0)):
            errs.append(f"vetoes.{name}: cap {cap!r} not a number in 0..100")
    return errs


_CHECKS = (("weights.yaml", check_weights), ("anchors.yaml", check_anchors),
           ("vetoes.yaml", check_vetoes))


# Files in the pack that deliberately carry no invariants of their own, each with
# its reason. Empty today, and kept so that leaving a spec file unchecked is a
# written decision rather than an omission nobody sees.
_NO_INVARIANTS = {}


def validate_dir(scoring_dir):
    """Load + validate the registered files. Returns (errors, missing_files).

    `_CHECKS` names three files and the pack is meant to grow — the radio-band
    handoff proposes a fourth. A file dropped in beside them would be loaded by
    nobody and validated by nothing while `verify_all` went on reporting the
    pack as PASS: the hand-written-subject shape (D-287), on the one gate
    standing between a spec edit and a shipped scoring rule. So the directory is
    walked, and anything unregistered is an error rather than a silence.
    """
    import yaml  # deferred: absence -> NOT_EXECUTED at the CLI edge
    errors, missing = [], []
    for fname, check in _CHECKS:
        path = os.path.join(scoring_dir, fname)
        if not os.path.exists(path):
            missing.append(fname)
            continue
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        errors.extend(check(doc))

    known = {f for f, _c in _CHECKS} | set(_NO_INVARIANTS)
    if os.path.isdir(scoring_dir):
        for fname in sorted(os.listdir(scoring_dir)):
            if fname.endswith((".yaml", ".yml")) and fname not in known:
                errors.append(
                    "%s: in spec/scoring but validated by nothing — add a "
                    "checker to _CHECKS, or say in _NO_INVARIANTS why this file "
                    "has no invariants of its own" % fname)
    return errors, missing


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB spec scoring-pack validator")
    ap.add_argument("--dir", default=DEFAULT_DIR, help="spec/scoring directory")
    args = ap.parse_args(argv)

    try:
        import yaml  # noqa: F401
    except ImportError:
        print("pyyaml not installed — spec-scoring validation NOT_EXECUTED", file=sys.stderr)
        return 2
    if not os.path.isdir(args.dir):
        print(f"scoring dir not found: {args.dir}", file=sys.stderr)
        return 2

    errors, missing = validate_dir(args.dir)
    if missing and len(missing) == len(_CHECKS):
        print(f"no scoring files found in {args.dir}", file=sys.stderr)
        return 2
    for m in missing:
        errors.append(f"{m}: file missing")

    if not errors:
        # ASCII summary: verify_all captures + greps this first line on a GBK console.
        print(f"spec-scoring OK: {len(_CHECKS) - len(missing)} file(s) - "
              "weights sum=1.0, anchors ascending, veto structure hold")
        return 0
    print(f"spec-scoring VIOLATIONS: {len(errors)}")
    for e in errors:
        print(f"  - {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
