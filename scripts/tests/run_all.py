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

# pytest.skip() raises Skipped, and Skipped derives from BaseException, *not*
# from Exception -- so the `except Exception` in main() is structurally unable
# to catch it. One skipping test therefore aborted the whole run: on 2026-09-06
# it died inside module 10 of 34, leaving 24 modules unrun and printing no
# summary line at all, so the operator sees a traceback where the tally belongs
# and cannot tell "a test failed" from "the runner never finished".
#
# This fires only where a skip condition is true, which is why it hid: the main
# tree has both corpus roots, so it stayed green there while every worktree and
# fresh clone was dead. Same runner, two trees, two verdicts -- and both sides
# were honestly reporting "the gate runner".
#
# Resolve the class when pytest is importable; otherwise fall back to a
# placeholder nothing ever raises, keeping this runner's "no pytest dep"
# promise (see module docstring) intact.
try:
    from _pytest.outcomes import Skipped as _Skipped
except Exception:  # pytest absent: nothing can raise Skipped anyway
    class _Skipped(BaseException):
        """Never raised; only keeps the except clause in main() well-formed."""


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
    skips = []
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
            except _Skipped as e:
                # A skip is NOT a pass, and it is NOT a failure either.
                #
                # It stays in `total` while staying out of `passed`, so the
                # printed ratio drops below N/N. That visible gap is the entire
                # point: these guards did not run. Counting a skip as passed --
                # or quietly dropping it from `total` -- would print a clean
                # N/N over a gate that covered less than it did yesterday,
                # which is the exact shape this repo keeps getting bitten by.
                #
                # Skips do not set a non-zero exit code: a skip condition like
                # "corpus roots absent" is true and legitimate in a fresh
                # clone, and failing there would make the gate unrunnable
                # rather than honest. The signal is the ratio and the SKIP
                # lines below, both of which land in the verify_all log.
                skips.append((f"{modname}.{name}", str(e)))
            except Exception as e:
                failures.append((f"{modname}.{name}", "".join(
                    traceback.format_exception_only(type(e), e)).strip()))
    # The suffix goes after "passed" on purpose: badges.py matches
    # `(\w+) reflex:\s*(\d+)/(\d+)\s*passed` with no end-of-line anchor, so it
    # keeps reading the same two numbers, and verify_all.ps1 echoes this whole
    # line into the gate result where a reviewer will see the skip count.
    summary = f"campaign-analysis reflex: {passed}/{total} passed"
    if skips:
        summary += f", {len(skips)} SKIPPED (did not run)"
    _say(summary)
    for name, why in skips:
        _say(f"  SKIP {name}: {why}")
    for name, err in failures:
        _say(f"  FAIL {name}: {err}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
