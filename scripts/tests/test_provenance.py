# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/provenance.py + its report integration."""
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import attribution
import buffering_rollup
import campaign_common
import order_effect
import provenance as prov
import campaign_report as rpt
import stability
import transport_rollup
import trend
import trust_rollup
import validity_rollup
from synth import aqs_records


def _write(path, text):
    # newline="" prevents Windows \n -> \r\n translation, so the on-disk bytes
    # match `text` exactly and the sha256 assertion is platform-independent.
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def test_sha256_matches_content():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.jsonl")
        _write(p, "hello\n")
        expect = hashlib.sha256(b"hello\n").hexdigest()
        assert prov.file_sha256(p) == expect


def test_unreadable_file_sha_is_none():
    assert prov.file_sha256(os.path.join("no", "such", "file.jsonl")) is None


def test_compute_carries_load_stats_and_params():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.jsonl")
        _write(p, "{}\n")
        stats = {"lines": 10, "kept": 8, "duplicates": 2, "conflicts": ["x"],
                 "no_run_id": 0, "malformed": 1}
        m = prov.compute([p], stats, {"min_samples": 5}, generated_at="2026-01-01")
        assert m["generated_at"] == "2026-01-01"
        assert m["lines_read"] == 10
        assert m["records_kept"] == 8
        assert m["duplicates_dropped"] == 2
        assert m["conflicting_run_ids"] == ["x"]
        assert m["malformed_lines"] == 1
        assert m["params"]["min_samples"] == 5
        assert m["input_count"] == 1
        assert m["inputs"][0]["file"] == "a.jsonl"
        assert m["inputs"][0]["sha256"] == hashlib.sha256(b"{}\n").hexdigest()


def test_compute_is_deterministic_given_generated_at():
    """Same inputs + same injected timestamp -> identical manifest (reproducible)."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.jsonl")
        _write(p, "x\n")
        a = prov.compute([p], {"kept": 1}, {}, generated_at="T")
        b = prov.compute([p], {"kept": 1}, {}, generated_at="T")
        assert a == b


def test_render_markdown_shows_files_and_counts():
    m = prov.compute([], {"lines": 3, "kept": 3, "duplicates": 0},
                     {"min_samples": 5}, generated_at="2026-01-01")
    md = prov.render_markdown(m)
    assert "provenance" in md
    assert "保留 3 条" in md
    assert "aneb-campaign-analysis/1.0" in md


def test_write_sidecar_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        m = prov.compute([], {"kept": 1}, {"attr_kpi": "n1_rtt_p50_ms"}, generated_at="T")
        out = os.path.join(d, "prov.json")
        prov.write_sidecar(m, out)
        with open(out, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["records_kept"] == 1
        assert loaded["params"]["attr_kpi"] == "n1_rtt_p50_ms"


# ---- integration: report body stays deterministic without provenance ----

def test_report_body_deterministic_without_provenance():
    """No manifest unless asked — but SAY it is missing (D-194).

    The old assertion was `"provenance" not in a`: a bare word match standing in
    for "no fabricated manifest". It also forbade stating that the section is
    absent, which is the opposite of this layer's rule that a silently missing
    section cannot be told apart from one that did not apply. Asserted against
    the manifest's actual content now, not against the word."""
    recs = aqs_records(90, 5)
    a = rpt.build_report_markdown(recs)
    b = rpt.build_report_markdown(recs)
    assert a == b                                   # snapshot-safe
    assert "未生成溯源信息" in a                      # absence is stated…
    assert "无法复现" in a                           # …with what it costs
    # …and nothing is invented. Match the manifest's ROW/BLOCK form, not the
    # words: the absence notice names sha256 and 生效门限 itself, so a bare word
    # check is true for every report — the over-broad-assertion trap, walked into
    # a third time this window while writing the fix for the second.
    assert "| 输入文件 | sha256 |" not in a          # no manifest table
    assert '"cv_gate_percent"' not in a             # no fabricated thresholds


def test_report_includes_provenance_when_supplied():
    recs = aqs_records(90, 5)
    m = prov.compute([], {"lines": 5, "kept": 5}, {"min_samples": 5}, generated_at="2026-01-01")
    md = rpt.build_report_markdown(recs, provenance=m)
    assert "溯源 / provenance" in md
    assert "2026-01-01" in md


# The modules whose module-level numbers decide what the REPORT says. Generators
# and per-run tools are deliberately absent: synth_campaign fabricates corpora,
# annotate_campaign runs BEFORE the report and records its own choices in
# `label_source` (D-153), and dashboard/validate_* do not feed this report.
_GATE_MODULES = (attribution, buffering_rollup, campaign_common, order_effect,
                 stability, transport_rollup, trend, trust_rollup, validity_rollup)

# Numeric module constants that do NOT decide report output, each with the reason
# it is exempt. This table is where the judgement lives — visibly, so that adding
# a gate and forgetting to archive it is a test failure rather than a silence.
_NOT_A_REPORT_GATE = {
    ("campaign_common", "DEFAULT_MIN_SAMPLES"):
        "a CLI knob; the manifest records it under `params`, not `thresholds`",
    ("stability", "DEFAULT_TARGET_EFFECT_PCT"):
        "only the standalone `--plan` sample-size CLI; no report section reads it",
    ("provenance", "_SHORT"): "display width of the inline hash, not a gate",
}

# module constant -> the key it is archived under. Not a list someone extends by
# remembering to: the scan below fails on any scanned constant absent from BOTH
# this map and the exemption table.
_GATE_KEY = {
    ("attribution", "TIER_TIME_SPREAD_GATE_MS"): "tier_time_spread_gate_ms",
    ("attribution", "OUTLIER_K"): "segment_outlier_k",
    ("buffering_rollup", "HOTSPOT_SHARE"): "buffering_hotspot_share",
    ("campaign_common", "EPOCH_MS_MIN"): None,      # archived as a pair, below
    ("campaign_common", "EPOCH_MS_MAX"): None,
    ("campaign_common", "MAD_TO_SIGMA"): "mad_to_sigma",
    ("campaign_common", "MEDIAN_SE_FACTOR"): "median_se_factor",
    ("order_effect", "DEFAULT_THRESHOLD_PCT"): "order_effect_threshold_percent",
    ("stability", "DEFAULT_CV_GATE"): "cv_gate_percent",
    ("stability", "DEFAULT_MAX_STABLE_ROWS"): "stability_max_stable_rows",
    ("trend", "MIN_CAMPAIGNS_FOR_TREND"): "min_campaigns_for_trend",
    ("trust_rollup", "CLOCK_HOTSPOT_SHARE"): "clock_hotspot_share",
    ("validity_rollup", "DEFAULT_MIN_RATE"): "validity_min_rate",
}

# the two epoch bounds share one manifest entry; checked as a pair so neither can
# drop out of it unnoticed
_GATE_PAIRS = {"epoch_ms_bounds": (("campaign_common", "EPOCH_MS_MIN"),
                                   ("campaign_common", "EPOCH_MS_MAX"))}


def test_effective_thresholds_cover_every_output_deciding_gate():
    """A manifest recording only the CLI knobs lets a retuned module-level gate
    change the numbers under an identical-looking manifest (D-122).

    This test used to check a HAND-WRITTEN list of nine key names — so it could
    not, in principle, notice a tenth gate that was never added, which is exactly
    what happened to four of them (D-198). Worse than a gap: the function it
    guards is called `effective_thresholds` and this test is called "cover every
    output-deciding gate", so two names asserted a completeness nobody checked.

    Enumerate instead: every public numeric constant in the report's own modules
    must be archived, or exempt with a stated reason.
    """
    t = rpt.effective_thresholds()
    missing, wrong = [], []
    scanned = 0
    for mod in _GATE_MODULES:
        for name, val in sorted(vars(mod).items()):
            if name.startswith("_") or name != name.upper():
                continue
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                continue
            scanned += 1
            ref = (mod.__name__, name)
            if ref in _NOT_A_REPORT_GATE:
                continue
            if ref not in _GATE_KEY:
                missing.append(f"{mod.__name__}.{name} = {val!r} — archive it in "
                               "effective_thresholds() and name it in _GATE_KEY, "
                               "or exempt it with a reason in _NOT_A_REPORT_GATE")
                continue
            key = _GATE_KEY[ref]
            if key is None:
                continue                    # part of a pair, checked below
            if t.get(key) != val:
                # matching by VALUE alone would let a gate pass on a coincidence:
                # MIN_CAMPAIGNS_FOR_TREND is 3 and segment_outlier_k is 3.0, and
                # 3 == 3.0 — so dropping the former from the manifest would go
                # unnoticed. Name and value, both.
                wrong.append(f"{mod.__name__}.{name}={val!r} vs {key}={t.get(key)!r}")
    for key, refs in _GATE_PAIRS.items():
        expect = [getattr(sys.modules[m], n) for m, n in refs]
        assert list(t.get(key) or []) == expect, (key, t.get(key), expect)
    assert scanned >= 12, scanned          # the scan must actually find constants
    assert not missing, missing
    assert not wrong, wrong
    assert t["cv_gate_percent"] == stability.DEFAULT_CV_GATE
    assert t["buffering_hotspot_share"] == buffering_rollup.HOTSPOT_SHARE


def test_gate_exemptions_still_refer_to_real_constants():
    """An exemption for a constant that no longer exists silently widens the
    exemption list — the same rot that let the hand-written key list go stale."""
    for (modname, name), reason in _NOT_A_REPORT_GATE.items():
        mod = sys.modules.get(modname) or __import__(modname)
        assert hasattr(mod, name), f"{modname}.{name} is gone; drop the exemption"
        assert reason.strip(), (modname, name)


def test_thresholds_are_read_live_not_snapshotted():
    """Retuning a gate must show up in the manifest — otherwise the record lies."""
    original = stability.DEFAULT_CV_GATE
    try:
        stability.DEFAULT_CV_GATE = 7.5
        assert rpt.effective_thresholds()["cv_gate_percent"] == 7.5
    finally:
        stability.DEFAULT_CV_GATE = original


def test_thresholds_render_and_round_trip():
    m = prov.compute([], {"lines": 1, "kept": 1}, {"min_samples": 5},
                     generated_at="2026-01-01", thresholds={"cv_gate_percent": 10.0})
    assert "生效门限" in prov.render_markdown(m)
    with tempfile.TemporaryDirectory() as d:
        p = prov.write_sidecar(m, os.path.join(d, "prov.json"))
        with open(p, encoding="utf-8") as f:
            assert json.load(f)["thresholds"]["cv_gate_percent"] == 10.0


def test_manifest_without_thresholds_renders_no_gate_line():
    """Back-compatible: omitting thresholds keeps the old header shape."""
    m = prov.compute([], {"lines": 1, "kept": 1}, {}, generated_at="2026-01-01")
    assert "生效门限" not in prov.render_markdown(m)
