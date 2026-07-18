#!/usr/bin/env python3
"""Portrait SHAPE gate — validate spec/portraits/*.yaml against portrait.schema.json.

Complements check_redline.py (semantics): this checks document *shape* (the three-layer
structure params / params_fit_approx / observed_*). A portrait must pass both gates.

exit 0 = all portraits conform / 1 = schema violation(s) / 2 = env gap
(pyyaml or jsonschema missing, or schema file absent) -> verify_all maps 2 -> NOT_EXECUTED.
Mirrors check_redline.py's exit contract so verify_all.ps1 wiring is symmetric.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(HERE, "portrait.schema.json")


def main() -> int:
    try:
        import yaml
        import jsonschema
    except ImportError as e:
        print(f"NOT_EXECUTED: missing dependency ({e})")
        return 2

    if not os.path.isfile(SCHEMA_PATH):
        print(f"NOT_EXECUTED: schema not found: {SCHEMA_PATH}")
        return 2
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    validator = jsonschema.Draft202012Validator(schema)

    files = sorted(glob.glob(os.path.join(HERE, "*.yaml")))
    if not files:
        print("NOT_EXECUTED: no portrait yaml found")
        return 2

    violations = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        app = os.path.basename(path)
        for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
            loc = "/".join(str(p) for p in err.path) or "<root>"
            violations.append(f"{app}: [{loc}] {err.message}")

    if violations:
        for v in violations:
            print("FAIL", v)
        print(f"FAIL: {len(violations)} schema violation(s) across {len(files)} portrait(s).")
        return 1
    print(f"OK: {len(files)} portrait(s) conform to portrait.schema.json (shape gate).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
