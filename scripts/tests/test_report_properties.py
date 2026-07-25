# -*- coding: utf-8 -*-
"""Property tests: invariants that must hold for ANY corpus, not just the fixtures.

Every other golden here is "known input -> known output". Those cannot catch a
rule that breaks only on a shape nobody wrote a fixture for — an all-null cell,
a single record, an empty scenario list, a KPI present but ungraded.

These generate structurally valid but arbitrary corpora from seeded RNG
(deterministic, so a failure is reproducible without a fuzzing dependency) and
assert what must be true regardless of the numbers (D-127):

  * nothing crashes — every renderer survives every shape
  * nothing is fabricated — a not-computable value renders as the em-dash,
    never as 0
  * low-confidence discipline — a cell under the sample floor is always marked
  * determinism — the same corpus always yields the same bytes
"""
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import buffering_rollup
import campaign_common as cc
import campaign_report as rpt
import publish_check as pc
import stability
import subscore_rollup
import transport_rollup
import trend
import trust_rollup
import validity_rollup

SEEDS = range(20)
_POINTS = ("P1", "P2", "P3")
_CARRIERS = ("cmcc", "cucc")
_BANDS = ("busy", "idle")
_TIERS = ("metro", "regional", "core", None)
_PROFILES = ("s1_chat", "s2_coding_agent")
_KPIS = ("t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps", "t2_itl_p95_ms")


def _maybe(rng, value, p=0.7):
    """value with probability p, else None — so nulls appear everywhere."""
    return value if rng.random() < p else None


def _random_corpus(seed):
    """Structurally valid, arbitrarily shaped. Deliberately includes degenerate
    cases: no scenarios, no labels, all-null KPIs, missing blocks."""
    rng = random.Random(seed)
    out = []
    for i in range(rng.randint(1, 25)):
        scns = []
        for _ in range(rng.choice([0, 1, 1, 2, 3])):
            kpi = {}
            for k in _KPIS:
                v = _maybe(rng, round(rng.uniform(1, 500), 2))
                kpi[k] = v
                if rng.random() < 0.8:          # sometimes the grade is missing
                    kpi[k.split("_")[0] + "_grade"] = (
                        None if v is None else rng.choice(["good", "fair", "poor"]))
            scn = {
                "profile_id": rng.choice(_PROFILES),
                "profile_version": rng.choice(["0.2", "0.3"]),
                "repeat_index": 0, "order_index": rng.randint(0, 2),
                "validity": rng.choice(["valid", "valid_low_confidence", "invalid"]),
                "invalid_reasons": rng.choice(["", "STREAM_ABORTED", "A;B"]),
                "kpi": kpi,
            }
            if rng.random() < 0.6:
                scn["clock"] = {"drift_ppm": _maybe(rng, round(rng.uniform(-500, 500), 2)),
                                "offset_suspect": rng.random() < 0.3}
            if rng.random() < 0.6:
                scn["buffering"] = {"score": _maybe(rng, round(rng.random(), 4)),
                                    "attribution": rng.choice(
                                        ["none", "middlebox_suspect", None]),
                                    "sample_count": 100}
            if rng.random() < 0.5:
                scn["parse"] = {"per_event_parse_us": _maybe(rng, rng.uniform(5, 200))}
            if rng.random() < 0.5:
                edges = rng.choice([[10, 20], [10, 25, 50]])
                scn["itl_histogram"] = {"buckets_version": "v1", "edges_ms": edges,
                                        "counts": [0] * (len(edges) + 1), "total": 0}
            scns.append(scn)

        run = {"run_id": f"prop-{seed}-{i:04d}",
               "started_at_epoch_ms": 1783944000000 + i * 60000,
               "mode": rng.choice(["quick", "forensic"]), "scenario_order": "",
               "transport": rng.choice(["auto", "wifi", "auto(cellular)", "cellular"]),
               "profile_source": rng.choice(["server", "assets_fallback"]),
               "app_version_name": "t", "app_version_code": 1, "guard_metadata": None,
               "status": rng.choice(["completed", "completed", "aborted:timeout"]),
               "aqs": {"score": _maybe(rng, round(rng.uniform(0, 100), 2)),
                       "low_confidence": rng.random() < 0.3, "veto_applied": False,
                       "not_computable_reason": None, "input_mapping": "t",
                       "sub_scores": ({} if rng.random() < 0.4 else
                                      {d: round(rng.uniform(0, 100), 2)
                                       for d in ("T1", "N1", "N2")})}}
        if rng.random() < 0.8:                  # some records carry no labels
            run["campaign"] = {"campaign_id": rng.choice(["base", "opt"]),
                               "tier": rng.choice(_TIERS),
                               "point_id": rng.choice(_POINTS),
                               "carrier": rng.choice(_CARRIERS),
                               "time_band": rng.choice(_BANDS)}
        out.append({"claim_scope": cc.CLAIM_SCOPE, "kpi_set": "t", "aqs_version": "t",
                    "profile_versions": "t", "schema_version": "1.0",
                    "run": run, "scenarios": scns})
    return out


def test_no_renderer_crashes_on_any_shape():
    for seed in SEEDS:
        recs = _random_corpus(seed)
        try:
            rpt.build_report_markdown(recs)
            rpt.build_report_html(recs, "2026-01-01 00:00:00 +0800")
            pc.check(recs)
            for mod in (buffering_rollup, trust_rollup, transport_rollup,
                        subscore_rollup):
                mod.render_markdown(mod.analyze(recs))
            validity_rollup.render_markdown(validity_rollup.analyze(recs))
            trend.render_markdown(trend.analyze(recs))
            for k in stability.DEFAULT_STABILITY_KPIS:
                stability.render_markdown(stability.stability_cells(recs, k), k)
        except Exception as e:                   # noqa: BLE001 - report the seed
            raise AssertionError(f"seed {seed} crashed: {type(e).__name__}: {e}")


def test_report_is_deterministic_for_a_given_corpus():
    for seed in SEEDS:
        recs = _random_corpus(seed)
        assert rpt.build_report_markdown(recs) == rpt.build_report_markdown(recs), seed


def test_low_confidence_marked_whenever_below_the_floor():
    """Never silently present a cell built from too few samples."""
    for seed in SEEDS:
        for c in rpt.heat_cells(_random_corpus(seed), cc.DEFAULT_MIN_SAMPLES):
            assert c["low_confidence"] == (c["n"] < cc.DEFAULT_MIN_SAMPLES), seed


def test_null_medians_never_render_as_zero():
    """A cell with no usable samples must show the placeholder, not 0 (R-10)."""
    for seed in SEEDS:
        for c in buffering_rollup.analyze(_random_corpus(seed))["cells"]:
            for key in ("score_median", "sawtooth_median", "near_zero_median"):
                if c[key] is None:
                    assert cc.fmt_num(c[key], 3) == "—", (seed, key)


def test_suspect_shares_stay_in_range():
    for seed in SEEDS:
        recs = _random_corpus(seed)
        for c in buffering_rollup.analyze(recs)["cells"]:
            if c["suspect_share"] is not None:
                assert 0.0 <= c["suspect_share"] <= 1.0, seed
        for c in trust_rollup.analyze(recs)["cells"]:
            if c["clock_suspect_share"] is not None:
                assert 0.0 <= c["clock_suspect_share"] <= 1.0, seed
            assert c["clock_suspect"] <= c["clock_annotated"], seed
            assert c["stream_bad"] <= c["stream_counted"], seed


def test_validity_counts_never_exceed_attempts():
    for seed in SEEDS:
        for c in validity_rollup.analyze(_random_corpus(seed))["cells"]:
            total = c["valid"] + c["valid_low_confidence"] + c["invalid"] + c["unknown"]
            assert total == c["attempted"], seed
            if c["valid_rate"] is not None:
                assert 0.0 <= c["valid_rate"] <= 1.0, seed


def test_publish_check_always_returns_known_severities():
    known = {pc.FAIL, pc.WARN, pc.PASS}
    for seed in SEEDS:
        rows = pc.check(_random_corpus(seed))
        assert rows, seed
        assert all(r["severity"] in known for r in rows), seed
        assert all(r["item"] and r["detail"] for r in rows), seed


def test_every_markdown_table_has_a_uniform_column_count():
    """A ragged table renders as garbage in any markdown viewer."""
    for seed in SEEDS:
        md = rpt.build_report_markdown(_random_corpus(seed))
        for chunk in re.split(r"(?m)^#{2,3} ", md)[1:]:
            widths = {len(ln.strip("|").split("|"))
                      for ln in chunk.splitlines() if ln.startswith("| ")}
            assert len(widths) <= 1, (seed, chunk.splitlines()[0], widths)
