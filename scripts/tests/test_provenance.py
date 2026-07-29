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

# Module constants that do NOT decide report output, each with the reason it is
# exempt. This table is where the judgement lives — visibly, so that adding a
# gate and forgetting to archive it is a test failure rather than a silence.
#
# It used to say "Numeric" here, and the scan below matched: int/float only. A
# gate that happens to be a tuple of KPI names or a list of tiers was therefore
# outside a check whose own name promises every output-deciding gate — and five
# such gates were unarchived when the scan was widened (D-248).
_NOT_A_REPORT_GATE = {
    ("campaign_common", "DEFAULT_MIN_SAMPLES"):
        "a CLI knob; the manifest records it under `params`, not `thresholds`",
    # ---- vocabulary and display: changing them changes wording, not a number
    ("campaign_common", "TIER_LABELS"):
        "the Chinese display name of each tier; the tiers themselves are archived "
        "as `tiers`. Perturbing it changes words on the page and leaves every "
        "numeral identical",
    ("campaign_common", "GRADE_COLORS"): "HTML swatch colours",
    ("campaign_common", "NOISE_CAVEAT"):
        "the sentence printed under every 噪声内 verdict; the factors it "
        "describes are archived as median_se_factor / mad_to_sigma",
    ("campaign_common", "NOISE_UNJUDGEABLE"):
        "the two reasons a noise scale cannot be computed, as display strings",
    ("campaign_common", "UNKNOWN"): "the placeholder printed for a missing label",
    ("campaign_common", "UNLABELED"):
        "the placeholder printed for an absent campaign label",
    ("campaign_common", "CLAIM_SCOPE"):
        "the contract's claim-scope string, enforced by validate_results on the "
        "way IN; no report section computes from it",
    ("campaign_common", "SYNTHETIC_CAMPAIGN_PREFIX"):
        "half of the synthetic-corpus detector (D-116/117). It decides whether "
        "the red banner appears, not what any number is, and a real corpus is "
        "unaffected by its value",
    # ---- structural: what a cell IS, not a level anyone retunes
    ("campaign_common", "TRANSPORT_EXPLICIT"):
        "the same two media as `transport_media`, in the normaliser that maps a "
        "raw string onto them; the archived key is the one the section reads",
    ("buffering_rollup", "CELL_DIMS"): "the cell key: structural, not a level",
    ("transport_rollup", "CELL_DIMS"): "the cell key: structural, not a level",
    ("trend", "CELL_DIMS"): "the cell key: structural, not a level",
    ("trust_rollup", "CELL_DIMS"): "the cell key: structural, not a level",
    ("validity_rollup", "CELL_DIMS"): "the cell key: structural, not a level",
    ("validity_rollup", "VALIDITY_STATES"):
        "the four states the result contract defines; changing it does not "
        "retune this report, it describes a different input format",
    # ---- default ARGUMENTS of the standalone CLIs. The report never takes them:
    # ---- it loops the archived KPI lists instead
    ("attribution", "DEFAULT_KPI"):
        "the report's own signature defaults to it, so it IS taken when nobody "
        "passes --attr-kpi — what exempts it is that the CHOICE is archived "
        "under `params`, the same footing as DEFAULT_MIN_SAMPLES, rather than "
        "under `thresholds` (D-263 corrected the earlier wording, which implied "
        "the report never takes it)",
    ("order_effect", "DEFAULT_KPI"):
        "the `--kpi` default of order_effect's own CLI; the report loops "
        "`order_effect_kpis`",
    ("trend", "DEFAULT_METRIC"):
        "every trend.analyze call in the report omits `metric`, so the report "
        "DOES take this default — calling it 'the CLI's default' was wrong "
        "(D-263). What exempts it is that its value is `METRIC_AQS`, archived "
        "as `trend_metric_key`: retune the metric and the archived key moves "
        "with it, so the manifest cannot look unchanged",
    ("stability", "DEFAULT_TARGET_EFFECT_PCT"):
        "only the standalone `--plan` sample-size CLI; no report section reads it",
    ("campaign_common", "PLAN_POWER"):
        "same: the `--plan` sample-size CLI only. It shapes advice about a FUTURE "
        "campaign, not any number in this report — nothing here is reproduced "
        "differently by changing it",
    ("provenance", "_SHORT"): "display width of the inline hash, not a gate",
}

# module constant -> the key it is archived under. Not a list someone extends by
# remembering to: the scan below fails on any scanned constant absent from BOTH
# this map and the exemption table.
_GATE_KEY = {
    ("attribution", "TIER_TIME_SPREAD_GATE_MS"): "tier_time_spread_gate_ms",
    ("attribution", "OUTLIER_TARGET_FALSE_ALARM"):
        "segment_outlier_target_false_alarm",
    ("attribution", "MIN_CELLS_TO_SCREEN"): "segment_min_cells_to_screen",
    ("buffering_rollup", "HOTSPOT_SHARE"): "buffering_hotspot_share",
    ("campaign_common", "EPOCH_MS_MIN"): None,      # archived as a pair, below
    ("campaign_common", "EPOCH_MS_MAX"): None,
    ("campaign_common", "NON_KPI_RANGES"): "value_ranges_non_kpi",
    ("campaign_common", "MAD_TO_SIGMA"): "mad_to_sigma",
    ("campaign_common", "MEDIAN_SE_FACTOR"): "median_se_factor",
    ("order_effect", "DEFAULT_THRESHOLD_PCT"): "order_effect_threshold_percent",
    ("stability", "DEFAULT_CV_GATE"): "cv_gate_percent",
    ("stability", "DEFAULT_MAX_STABLE_ROWS"): "stability_max_stable_rows",
    ("trend", "MIN_CAMPAIGNS_FOR_TREND"): "min_campaigns_for_trend",
    ("trust_rollup", "CLOCK_HOTSPOT_SHARE"): "clock_hotspot_share",
    ("validity_rollup", "DEFAULT_MIN_RATE"): "validity_min_rate",
    # The first four were already in the manifest and in NEITHER table here,
    # because the scan could not see a constant that is not a number. The rest
    # are the gates that widening it turned up unarchived (D-248).
    ("attribution", "ATTRIBUTABLE_KPIS"): "attribution_kpis",
    ("campaign_common", "AQS_GRADE_BANDS"): "aqs_grade_bands",
    # Radio bands (D-284): they decide the 弱/中/良 printed for every cellular
    # cell, and unlike every other gate here they are a COPY of a constant that
    # lives in the app — so the archived value is also the record of which copy
    # produced the report.
    ("campaign_common", "RSRP_WEAK_DBM"): "rsrp_weak_dbm",
    ("campaign_common", "RSRP_GOOD_DBM"): "rsrp_good_dbm",
    ("campaign_common", "SINR_WEAK_DB"): "sinr_weak_db",
    ("campaign_common", "SINR_GOOD_DB"): "sinr_good_db",
    ("campaign_common", "SIGNAL_BANDS"): "signal_bands",
    ("campaign_common", "SIGNAL_LABELS"): "signal_labels",
    # exempt until D-266 gave it a reader in the summary; archived once the
    # perturbation guard showed it moving printed numbers (D-267)
    ("campaign_common", "GRADE_ORDER"): "grade_order",
    # exempt as "structural" until source-level mutation reached them: setattr
    # cannot touch a captured default, so the perturbation that would have
    # noticed never ran on either one (D-269)
    ("attribution", "DEFAULT_GROUP_BY"): "attribution_group_by",
    ("stability", "STAB_GROUP_BY"): "stability_group_by",
    ("campaign_common", "VALUE_RANGES"): "value_ranges",
    ("stability", "DEFAULT_STABILITY_KPIS"): "stability_kpis",
    ("attribution", "SEGMENTS"): "attribution_segments",
    ("attribution", "SEVERE_FLAGS"): "severe_incomparability_flags",
    ("campaign_common", "TIERS"): "tiers",
    ("order_effect", "ORDER_SENSITIVE_KPIS"): "order_effect_kpis",
    ("transport_rollup", "EXPLICIT"): "transport_media",
    ("trend", "METRIC_AQS"): "trend_metric_key",
}

# A gate archived in reduced form: the manifest keeps the part a reader can
# compare, not the display half. Anything absent here is archived as itself.
_GATE_PROJECTION = {
    ("attribution", "SEGMENTS"): lambda v: [s for s, _ in v],
}


def _same(archived, live):
    """JSON round-trips tuples to lists and dicts to objects; compare shapes."""
    def norm(x):
        if isinstance(x, dict):
            return sorted((norm(k), norm(v)) for k, v in x.items())
        if isinstance(x, (list, tuple)):
            return [norm(i) for i in x]
        if isinstance(x, (set, frozenset)):
            return sorted(norm(i) for i in x)
        return x
    return norm(archived) == norm(live)

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
            # every kind a gate can BE. Restricting this to int/float is what
            # hid five of them (D-248); bools are flags, not levels.
            if not isinstance(val, (int, float, str, bytes,
                                    tuple, list, dict, set, frozenset)):
                continue
            if isinstance(val, bool):
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
            if not _same(t.get(key), _GATE_PROJECTION.get(ref, lambda v: v)(val)):
                # matching by VALUE alone would let a gate pass on a coincidence:
                # MIN_CAMPAIGNS_FOR_TREND is 3 and segment_outlier_k is 3.0, and
                # 3 == 3.0 — so dropping the former from the manifest would go
                # unnoticed. Name and value, both.
                wrong.append(f"{mod.__name__}.{name}={val!r} vs {key}={t.get(key)!r}")
    for key, refs in _GATE_PAIRS.items():
        expect = [getattr(sys.modules[m], n) for m, n in refs]
        assert list(t.get(key) or []) == expect, (key, t.get(key), expect)
    # the floor was 12 while the scan saw numbers only; widening it to every kind
    # a gate can be roughly tripled what it looks at, and a floor left at the old
    # number would pass with the widening quietly reverted (D-248)
    assert scanned >= 40, scanned          # the scan must actually find constants
    assert not missing, missing
    assert not wrong, wrong
    assert t["cv_gate_percent"] == stability.DEFAULT_CV_GATE
    assert t["buffering_hotspot_share"] == buffering_rollup.HOTSPOT_SHARE


# manifest key -> (module, attribute, a value that CROSSES the observed data).
# Choosing the perturbation is the whole difficulty. Two ways to get a false
# "inert" verdict, both of which happened while building this (D-204):
#   * the constant is captured as a default ARGUMENT, so setattr cannot reach it
#     (fixed at the source: archived gates are now read live);
#   * the new value does not cross the values actually present — pushing the
#     buffering hot-spot share DOWN when the corpus only ever has shares of 0.0
#     and 1.0 changes nothing, and says nothing.
_PERTURB = {
    "cv_gate_percent": (stability, "DEFAULT_CV_GATE", 1.0),
    "stability_max_stable_rows": (stability, "DEFAULT_MAX_STABLE_ROWS", 3),
    "stability_kpis": (stability, "DEFAULT_STABILITY_KPIS", ("t1_ttft_ms",)),
    "validity_min_rate": (validity_rollup, "DEFAULT_MIN_RATE", 0.999),
    "buffering_hotspot_share": (buffering_rollup, "HOTSPOT_SHARE", 1.0),
    "clock_hotspot_share": (trust_rollup, "CLOCK_HOTSPOT_SHARE", 0.99),
    "aqs_grade_bands": (campaign_common, "AQS_GRADE_BANDS",
                        [(95.0, "excellent"), (90.0, "good"),
                         (85.0, "fair"), (0.0, "poor")]),
    # drop the worst grade rather than reorder: the summary asks this constant
    # which grades rank below good, so removing one changes which cells the
    # report calls the city's worst (D-267)
    "grade_order": (campaign_common, "GRADE_ORDER", ["excellent", "good", "fair"]),
    # drop the last dimension of each cell key: measured at 418 and 494 printed
    # numerals moved, and reachable by setattr only because D-269 stopped both
    # from being captured in a signature
    "attribution_group_by": (attribution, "DEFAULT_GROUP_BY",
                             ("point_id", "carrier", "time_band")),
    "stability_group_by": (stability, "STAB_GROUP_BY",
                           ("campaign_id", "point_id", "carrier", "time_band",
                            "tier")),
    "heat_kpis": (rpt, "DEFAULT_KPI_HEAT", ("t1_ttft_ms",)),
    "attribution_kpis": (attribution, "ATTRIBUTABLE_KPIS", ("n1_rtt_p50_ms",)),
    "tier_time_spread_gate_ms": (attribution, "TIER_TIME_SPREAD_GATE_MS", 1),
    "segment_outlier_target_false_alarm":
        (attribution, "OUTLIER_TARGET_FALSE_ALARM", 0.99),
    "segment_outlier_k_by_cells": (attribution, "_OUTLIER_K_BY_CELLS",
                                   ((10 ** 9, 0.5),)),
    "segment_min_cells_to_screen": (attribution, "MIN_CELLS_TO_SCREEN", 999),
    "order_effect_threshold_percent": (order_effect, "DEFAULT_THRESHOLD_PCT", 0.0001),
    # raised ABOVE the corpus's campaign count, not lowered below it: the corpus
    # now has three, so lowering the gate to 2 changes nothing
    "min_campaigns_for_trend": (trend, "MIN_CAMPAIGNS_FOR_TREND", 4),
    "median_se_factor": (campaign_common, "MEDIAN_SE_FACTOR", 12.53),
    "mad_to_sigma": (campaign_common, "MAD_TO_SIGMA", 0.014826),
    "epoch_ms_bounds": (campaign_common, "EPOCH_MS_MIN", 4_000_000_000_000),
    "value_ranges": (campaign_common, "VALUE_RANGES",
                     dict(campaign_common.VALUE_RANGES, aqs_score=(0.0, 50.0))),
    "tiers": (campaign_common, "TIERS", ["metro", "regional"]),
    "attribution_segments": (attribution, "SEGMENTS", attribution.SEGMENTS[:2]),
    # emptied, not shortened: shortening drops IMPLAUSIBLE_VALUE, which a clean
    # corpus never produces, and the verdict would be a silent "inert" that says
    # nothing — the exact trap this table's header warns about
    "severe_incomparability_flags": (attribution, "SEVERE_FLAGS", ()),
    "order_effect_kpis": (order_effect, "ORDER_SENSITIVE_KPIS", ("t1_ttft_ms",)),
    "transport_media": (transport_rollup, "EXPLICIT", ("wifi",)),
    "trend_metric_key": (trend, "METRIC_AQS", "aqs_X"),
    # The rehearsal's radio points sit at -85 dBm / 15 dB, so each perturbation
    # is chosen to CROSS that: move a threshold past the observed reading and the
    # printed band changes. Pushing them the other way would read as inert and
    # prove nothing, which is what this table's header warns about.
    # tightened past the readings the rehearsal actually contains (-85 dBm), so
    # they become "impossible" and drop out — loosening it would change nothing
    "value_ranges_non_kpi": (campaign_common, "NON_KPI_RANGES",
                             {"rsrp_dbm": (-160.0, -90.0), "sinr_db": (-30.0, 45.0)}),
    "rsrp_weak_dbm": (campaign_common, "RSRP_WEAK_DBM", -80.0),
    "rsrp_good_dbm": (campaign_common, "RSRP_GOOD_DBM", -80.0),
    "sinr_weak_db": (campaign_common, "SINR_WEAK_DB", 20.0),
    "sinr_good_db": (campaign_common, "SINR_GOOD_DB", 20.0),
    "signal_bands": (campaign_common, "SIGNAL_BANDS", ["weak"]),
    "signal_labels": (campaign_common, "SIGNAL_LABELS",
                      {"weak": "W", "medium": "M", "good": "G"}),
}


def test_every_archived_threshold_actually_decides_the_report():
    """The manifest header says 「改动其一即改变报告结论」. Make that true.

    D-198's scan is the other half — every output-deciding gate must be
    archived. This is the converse: every archived gate must decide something.
    Together, archived <=> load-bearing, and the sentence the report prints above
    the manifest is a checked claim rather than a hope.

    It found one: `segment_outlier_k` was archived while unreachable, kept only
    "so the manifest keeps a stable key" (D-200). A manifest padded with inert
    entries teaches the reader that the list is decorative.
    """
    import synth_campaign as sc
    # three campaigns, so the trend section actually renders: with two, the gate
    # keeps it off the page and every trend-side perturbation reads as inert
    # while proving nothing (D-248)
    # radio=True for the same reason three campaigns are used: without it the
    # radio section renders its coverage-gap notice instead of a table, and every
    # band-side perturbation reads as inert while proving nothing (D-284).
    recs = sc.generate(points=3, repeats=3, campaigns=("base", "opt", "later"),
                       radio=True)
    base = rpt.build_report_markdown(recs)
    th = rpt.effective_thresholds()
    assert set(th) == set(_PERTURB), (
        f"only archived={sorted(set(th) - set(_PERTURB))}, "
        f"only perturbed={sorted(set(_PERTURB) - set(th))}")
    inert = []
    for key, (mod, attr, newval) in sorted(_PERTURB.items()):
        old = getattr(mod, attr)
        try:
            setattr(mod, attr, newval)
            if rpt.build_report_markdown(recs) == base:
                inert.append(key)
        finally:
            setattr(mod, attr, old)
    assert not inert, (
        "archived as output-deciding but the report is byte-identical with them "
        f"changed: {inert}")
    # every perturbation restored — otherwise this test poisons the ones after it
    assert rpt.build_report_markdown(recs) == base


def _perturbed_value(v):
    """A generic nudge by type, or None when there is no way to move this one."""
    if isinstance(v, bool):
        return not v
    if isinstance(v, (int, float)):
        return v + 5
    if isinstance(v, str):
        return v + "_X"
    if isinstance(v, dict) and len(v) > 1:
        drop = sorted(v, key=str)[-1]
        return {k: val for k, val in v.items() if k != drop}
    if isinstance(v, (list, tuple)) and len(v) > 1:
        return type(v)(list(v)[:-1])
    if isinstance(v, (set, frozenset)) and len(v) > 1:
        return type(v)(sorted(v, key=str)[:-1])
    return None


def _captured_as_a_default(mod, name):
    """Frozen into a signature, where setattr cannot reach it.

    This is the first of the two ways to get a false 'inert' verdict, recorded
    above _PERTURB. Such constants are counted and reported rather than passed
    quietly: "cannot be checked this way" is not the same as "checked".
    """
    import ast
    import io
    with io.open(mod.__file__, encoding="utf-8-sig") as fh:
        tree = ast.parse(fh.read(), mod.__name__)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for d in (list(node.args.defaults)
                  + [x for x in node.args.kw_defaults if x is not None]):
            for sub in ast.walk(d):
                if isinstance(sub, ast.Name) and sub.id == name:
                    return True
    return False


def test_every_exempt_constant_leaves_the_numbers_alone():
    """The converse of the test above, for the other half of the biconditional.

    「every archived gate must decide something」 has a test. 「every gate that
    decides something must be archived」 rests on _NOT_A_REPORT_GATE, and that
    table was checked only for existing and carrying a non-empty reason — the
    judgements themselves went unverified until D-263 read three by hand and
    found two misworded.

    Perturb each exemption and require the NUMERALS to stay put. Numerals, not
    the whole page, because that is what the exemptions claim: they say the
    value changes wording, not a number.

    This is a tripwire, not a proof. A perturbation too weak to cross the values
    in the corpus reads as inert and says nothing, so this can miss — it cannot
    lie. What it catches is an exemption that STOPS being true: D-264's bucket
    literal moved three printed counts, and D-266 gave GRADE_ORDER a reader in
    the summary while its exemption still said the bands already encoded it.
    The second was caught here, by this test, on its first run (D-267).

    The exemptions fall into three kinds: most are inert under perturbation,
    some are frozen into signatures where setattr cannot reach them, and the
    cell-key tuples raise rather than regroup. The counts are deliberately not
    written here — an enumeration in a comment is a number nothing compares,
    and this one had already gone stale by two buckets when D-269 moved two
    constants out of the table (D-279). The floor below carries the only count
    that has to stay true, and the assertion prints the rest when it fires.
    """
    import re
    import synth_campaign as sc
    numeral = re.compile(r"\d+(?:\.\d+)?")
    hex_colour = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    # chaos, or the placeholder constants never render and half of this is idle
    recs = sc.inject_chaos(sc.generate(points=2, repeats=3,
                                       campaigns=("base", "opt", "later")))

    def numerals():
        text = (rpt.build_report_markdown(recs)
                + rpt.build_report_html(recs, "2026-01-01 00:00:00"))
        return sorted(numeral.findall(hex_colour.sub("#", text)))

    base = numerals()

    # A control, through the same perturbation function: if that function ever
    # became a no-op, or the corpus stopped reaching these sections, every
    # exemption below would read "inert" and this test would pass by doing
    # nothing at all — which is the failure mode it exists to catch elsewhere.
    control_old = stability.DEFAULT_CV_GATE
    try:
        stability.DEFAULT_CV_GATE = _perturbed_value(control_old)
        assert numerals() != base, (
            "the control moved no numeral: an archived gate known to decide the "
            "report changed nothing here, so the perturbation, the corpus or the "
            "extraction is inert and every verdict below is empty")
    finally:
        stability.DEFAULT_CV_GATE = control_old

    moved, captured, unmovable, raised, inert = [], [], [], [], []
    for (modname, name) in sorted(_NOT_A_REPORT_GATE):
        mod = sys.modules.get(modname) or __import__(modname)
        label = f"{modname}.{name}"
        if _captured_as_a_default(mod, name):
            captured.append(label)
            continue
        old = getattr(mod, name)
        new = _perturbed_value(old)
        if new is None:
            unmovable.append(f"{label} ({type(old).__name__})")
            continue
        # The control below only exercises the numeric branch. Checking the
        # nudge here covers every branch: a dispatcher that quietly starts
        # handing back what it was given would leave these reading "inert".
        assert new != old, (
            f"the perturbation for {label} returns the value unchanged — that "
            f"branch of _perturbed_value has gone limp and every "
            f"{type(old).__name__} exemption reads inert while proving nothing")
        try:
            setattr(mod, name, new)
            try:
                (moved if numerals() != base else inert).append(label)
            except Exception as e:                        # noqa: BLE001
                raised.append(f"{label} -> {type(e).__name__}")
        finally:
            setattr(mod, name, old)

    assert numerals() == base, "a perturbation was not restored — results void"
    assert not moved, (
        f"exempt from the manifest, yet perturbing them moves printed numbers: "
        f"{moved} — archive them in effective_thresholds(), or say in the "
        "exemption why the number that moved does not belong to this report")
    assert not unmovable, (
        f"nothing here can move {unmovable} — an exemption no perturbation "
        "reaches is an exemption nothing checks. Teach _perturbed_value how to "
        "move that kind of value, or record in the exemption itself that it "
        "cannot be tested this way")
    assert len(inert) >= 12, (
        f"only {len(inert)} exemptions were actually exercised "
        f"({len(captured)} frozen into signatures, {len(unmovable)} unmovable, "
        f"{len(raised)} raised) — the perturbations have stopped reaching the "
        "report and this test is measuring almost nothing")
    assert (len(moved) + len(captured) + len(unmovable) + len(raised)
            + len(inert)) == len(_NOT_A_REPORT_GATE), "an exemption went uncounted"


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
