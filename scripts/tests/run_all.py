#!/usr/bin/env python3
"""Self-contained runner for campaign-analysis golden tests (no pytest dep).

exit 0 = all reflex tests pass / 1 = any failed. Mirrors the spec/portraits
reflex-runner convention so it wires into scripts/verify_all.ps1 as the
`campaign-analysis-unit` gate step.

Usage:  python run_all.py
"""
import importlib
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # scripts/
sys.path.insert(0, HERE)                    # scripts/tests/

TEST_MODULES = ["test_attribution", "test_campaign_report"]


def main():
    total = passed = 0
    failures = []
    for modname in TEST_MODULES:
        try:
            mod = importlib.import_module(modname)
        except Exception as e:  # import-time failure counts as a hard fail
            failures.append((modname, "import: " + "".join(
                traceback.format_exception_only(type(e), e)).strip()))
            continue
        for name in sorted(dir(mod)):
            if not name.startswith("test_"):
                continue
            fn = getattr(mod, name)
            if not callable(fn):
                continue
            total += 1
            try:
                fn()
                passed += 1
            except Exception as e:
                failures.append((f"{modname}.{name}", "".join(
                    traceback.format_exception_only(type(e), e)).strip()))
    print(f"campaign-analysis reflex: {passed}/{total} passed")
    for name, err in failures:
        print(f"  FAIL {name}: {err}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
