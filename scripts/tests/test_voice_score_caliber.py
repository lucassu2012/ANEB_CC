# -*- coding: utf-8 -*-
"""Guard: no doc may cite the historical voice score without naming its caliber.

D-38's 79.8 was measured under `aqs-voice-sim-v0.1` — before M7 (longest frame
gap) existed and before the voice weights were re-cut. After D-395 there is a
second caliber, and the two scores are NOT comparable. The ruling was "annotate
every place that cites it", and the whole failure mode this guards against is
D-301's: **a criterion gets replaced and the places that retell it do not follow**
— which looks fine forever, because prose has no compiler.

WHAT IT CHECKS (and therefore what it does NOT):
  Per FILE, not per LINE: any doc containing the literal score must also contain
  the caliber id somewhere. A per-line rule was the obvious first design and it
  is wrong here — `VOICE_ANALYSIS_LAYER_INVENTORY.md` legitimately shows
  `"t2_itl_p95_ms": 79.8`, a coincidental value from the synthetic corpus with
  nothing to do with voice. Demanding a voice-caliber banner on that line would
  make the guard cry wolf, and a guard nobody trusts is worse than none (D-319).

  The cost of per-file is real and stated here rather than discovered later: a
  file that already names the caliber can grow a new bare citation and stay
  green. What it does catch is the case that actually happens — a NEW report or
  blueprint quoting 79.8 while never telling the reader which ruler produced it.

The caliber id is READ FROM spec/scoring/weights.yaml, not written here: the doc
banner and the scoring table must name the same thing, and a literal copied into
this file would be a third place to drift (§2.14). It also means this guard fails
if WEIGHTS_VOICE_SIM is ever deleted from the spec — which spec/README.md §3
forbids ("published weight tables are add-only") precisely so that scores stamped
with the old id stay recomputable.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(SCRIPTS)

# The number as it is written in prose. Not derived: it is a historical
# measurement, recorded once by hand off a screen (D-38) and stored nowhere else
# — VoiceResultEntity persists neither the score nor the scoring version, by the
# deliberate D-42 design. There is no artifact to derive it from; saying so is
# more honest than dressing a literal up as a lookup.
_HISTORIC_SCORE = "79.8"


def _caliber_id():
    """The v0.1 sim scoring id, read out of the spec rather than hardcoded here.

    Deliberately fails loudly if the table or its version_id is gone: "I could
    not find it" is a finding, not a reason to pass (R-10). A version of this
    that returned None and skipped would report OK on the very change it exists
    to catch — the deletion of the caliber the docs still cite.
    """
    path = os.path.join(REPO, "spec", "scoring", "weights.yaml")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"^  WEIGHTS_VOICE_SIM:\n(?:.*\n)*?    version_id: \"([^\"]+)\"",
                  text, re.MULTILINE)
    assert m, ("spec/scoring/weights.yaml no longer exposes WEIGHTS_VOICE_SIM.version_id "
               "— either the table was deleted (spec/README.md §3 forbids it: published "
               "weight tables are add-only) or this extractor stopped matching. Either "
               "way this guard cannot answer its question and must not report OK.")
    return m.group(1)


def _doc_files():
    """Every markdown page a reader could take the number from, walked not listed.

    Walked for the same reason test_docs_commands.py walks: a hand-typed list of
    pages is exactly what lets the next new report slip through, and the next new
    report is the case this guard exists for.
    """
    out = [os.path.join(SCRIPTS, "README.md")]
    for root, _dirs, files in os.walk(os.path.join(REPO, "docs")):
        out += [os.path.join(root, f) for f in sorted(files) if f.endswith(".md")]
    return out


def test_every_doc_citing_the_historic_voice_score_names_its_caliber():
    caliber = _caliber_id()
    citing, missing = [], []
    for path in _doc_files():
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        # Digit-boundary match, not bare substring: "79.824" (a simulated score
        # band in T59's shortfall-penalty table) is NOT a citation of 79.8, yet
        # `"79.8" in text` says it is — caught live by the 2026-08-19 verify_all
        # dry-run. Same D-319 lesson as the docstring's per-line story, second
        # shape: the comparison key must tolerate surface forms, or the guard
        # cries wolf and stops being believed.
        if not re.search(r"(?<![\d.])" + re.escape(_HISTORIC_SCORE) + r"(?!\d)", text):
            continue
        citing.append(path)
        if caliber not in text:
            missing.append(os.path.relpath(path, REPO).replace("\\", "/"))
    # A zero-citation run would make this test vacuously green forever, which is
    # how a guard quietly stops guarding. If the number ever disappears from the
    # docs entirely, this line makes someone look at whether that was intended.
    assert citing, ("no doc cites %s at all — this guard is now testing nothing; "
                    "delete it or point it at whatever replaced the citation"
                    % _HISTORIC_SCORE)
    assert not missing, (
        "these docs cite the historical voice score %s without naming its caliber "
        "(%s); add \"%s，M7 引入前口径，不与 v0.2 后的分数比较\": %s"
        % (_HISTORIC_SCORE, caliber, caliber, ", ".join(missing)))


if __name__ == "__main__":
    test_every_doc_citing_the_historic_voice_score_names_its_caliber()
    print("OK: voice-score caliber banner present in every citing doc")
