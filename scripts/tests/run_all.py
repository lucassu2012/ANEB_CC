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

# Derived from disk, not hand-listed (D-275/D-364): the hand-written list
# missed test_round_effect for its entire first day — 9 guards that every
# "all green" run silently never executed. A list that must be maintained is a
# list that will be forgotten; enumeration cannot skip a file.
TEST_MODULES = sorted(
    f[:-3] for f in os.listdir(os.path.dirname(os.path.abspath(__file__)))
    if f.startswith("test_") and f.endswith(".py"))


def _encodable(ch, enc):
    try:
        ch.encode(enc)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def _say(text):
    """Print a report line even when the console cannot encode what it says.

    What gets printed here is assertion text, and assertions quote the report,
    which carries marks like the warning sign. This console is cp936: print()
    raises on the first such character — from inside the loop below, so every
    remaining failure goes unreported and the operator sees a traceback where
    the findings should be. D-241 hardened the CLIs against exactly this; the
    runner that reports on them was still bare (D-265).

    Escape only what cannot be shown, so Chinese assertion text survives.
    """
    enc = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        text.encode(enc)
    except (UnicodeEncodeError, LookupError):
        text = "".join(c if _encodable(c, enc) else "\\u%04x" % ord(c)
                       for c in text)
    print(text)


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
    _say(f"campaign-analysis reflex: {passed}/{total} passed")
    for name, err in failures:
        _say(f"  FAIL {name}: {err}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
