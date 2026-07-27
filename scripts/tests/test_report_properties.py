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
import order_effect
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


_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


def _columns(line):
    """Column count of a markdown table row. Splits on UNESCAPED pipes only —
    a renderer that correctly escapes a literal pipe as '\\|' keeps one cell,
    and a counter that ignores the escape would flag it as ragged."""
    return len(_UNESCAPED_PIPE.split(line.strip().strip("|")))


def test_hostile_labels_do_not_break_tables_or_html():
    """point_id is human-typed. A '|' or newline in one used to split every
    table in the report at once; HTML must stay escaped (D-128)."""
    from synth import contractify, kpi_scenario_records
    for pid in ("SZ|CBD-01", "SZ\nCBD", "<script>alert(1)</script>", "深圳-CBD-01",
                "P" * 200):
        recs = [contractify(r) for r in
                kpi_scenario_records(6, aqs=90, kpi={"n1_rtt_p50_ms": 20}, point=pid)]
        md = rpt.build_report_markdown(recs)
        for chunk in re.split(r"(?m)^#{2,3} ", md)[1:]:
            widths = {_columns(ln) for ln in chunk.splitlines() if ln.startswith("| ")}
            assert len(widths) <= 1, (pid, chunk.splitlines()[0], widths)
        html = rpt.build_report_html(recs, "2026-01-01 00:00:00 +0800")
        assert "<script>alert(1)</script>" not in html


def test_every_markdown_table_has_a_uniform_column_count():
    """A ragged table renders as garbage in any markdown viewer."""
    for seed in SEEDS:
        md = rpt.build_report_markdown(_random_corpus(seed))
        for chunk in re.split(r"(?m)^#{2,3} ", md)[1:]:
            widths = {_columns(ln) for ln in chunk.splitlines() if ln.startswith("| ")}
            assert len(widths) <= 1, (seed, chunk.splitlines()[0], widths)


_EPOCH = 1783944000000          # 2026-07-13T12:00:00Z
_DAY = 86400000


def test_every_csv_row_matches_its_header_width():
    """The markdown tables have had this guard since D-128; the CSVs never did —
    and CSV is the surface analysts compute on (D-141).

    A header and its row are written by two statements a dozen lines apart, so
    adding a column to one and not the other is a one-keystroke mistake nothing
    else catches: csv.DictReader does not raise, it files the surplus value under
    the key None (or pads a short row with None), and the file still opens
    cleanly in a spreadsheet.

    Counts only. Same-count, wrong-ORDER is a different failure and this test is
    blind to it — see the next one.
    """
    import csv as csvmod
    import tempfile
    corpora = {"corrupt": _corrupt_corpus(),
               **{f"seed{s}": _random_corpus(s) for s in (0, 3, 7)}}
    for name, recs in corpora.items():
        with tempfile.TemporaryDirectory() as d:
            for path in rpt.write_csv_tables(recs, os.path.join(d, "c")):
                with open(path, encoding="utf-8-sig", newline="") as f:
                    rows = list(csvmod.reader(f))
                assert rows, (name, path)
                width = len(rows[0])
                for i, row in enumerate(rows[1:], start=2):
                    assert len(row) == width, (name, os.path.basename(path), i,
                                               len(row), width, rows[0], row)


_MARKER_RE = re.compile(r"[<>]-?\d+(\.\d+)?×\d+")


def test_the_impossible_value_column_is_the_one_carrying_the_marker():
    """Same-count but wrong-order is the failure the width guard cannot see, and
    it is the one that actually happened while writing D-197: a column inserted
    mid-header while its value was appended at the end of the row. Widths match,
    every value lands under the wrong name, and the file reads fine.

    So: on a corpus with impossible readings, the marker must appear in the
    `implausible_values` column and in NO other — which pins the position of
    that column in every CSV that has one, and proves the whole D-197 wiring
    reaches the surface with no banner above it.
    """
    import csv as csvmod
    import tempfile
    seen = 0
    with tempfile.TemporaryDirectory() as d:
        for path in rpt.write_csv_tables(_corrupt_corpus(), os.path.join(d, "c")):
            with open(path, encoding="utf-8-sig", newline="") as f:
                rows = list(csvmod.DictReader(f))
            if not rows or "implausible_values" not in rows[0]:
                continue
            seen += 1
            marked = [r for r in rows if _MARKER_RE.search(r["implausible_values"] or "")]
            assert marked, (os.path.basename(path), "no marker reached this CSV")
            for r in rows:
                for col, val in r.items():
                    if col != "implausible_values" and _MARKER_RE.search(val or ""):
                        raise AssertionError((os.path.basename(path), col, val))
    # every CSV whose section pools values should have the column by now
    assert seen >= 6, seen


def _corrupt_corpus():
    """Three campaigns at one cell, and one run whose every number is impossible.

    Three because the trend section needs three to say anything at all, and a
    fixture that cannot reach a section cannot testify about it. One cell
    throughout, on purpose: the banner makes a single promise about that cell,
    and each section below either keeps it or does not. The bad run sits in the
    first campaign, so the trajectory's first point is the one at risk.
    """
    from synth import contractify, kpi_scenario_records
    out = []
    for day, (cid, aqs, ttft) in enumerate((("base", 70, 120), ("opt1", 74, 112),
                                            ("opt2", 78, 105))):
        clean = kpi_scenario_records(5, aqs=aqs, campaign_id=cid,
                                     kpi={"t1_ttft_ms": ttft, "t1_grade": "good"})
        for r in clean:
            r["run"]["aqs"]["sub_scores"] = {"N1": 80}
            r["scenarios"][0]["buffering"] = {"score": 0.4, "attribution": "none"}
        if cid == "base":
            bad = kpi_scenario_records(1, aqs=9999, campaign_id=cid,
                                       kpi={"t1_ttft_ms": -500, "t1_grade": "excellent"})
            for r in bad:
                r["run"]["aqs"]["sub_scores"] = {"N1": -5}
                r["scenarios"][0]["buffering"] = {"score": -1.0, "attribution": "none"}
            clean += bad
        for r in clean:
            r["run"]["transport"] = "cellular"
            r["run"]["started_at_epoch_ms"] = _EPOCH + day * _DAY
        out += clean
    return [contractify(r) for r in out]


# Every section that pools numbers into a median, and the render that shows it.
# A new pooling tool belongs in this list, or the banner ends up speaking for a
# section that never agreed to it.
_POOLING_SECTIONS = (
    ("heat_cells", lambda recs: rpt.render_heatcard_markdown(rpt.heat_cells(recs))),
    ("kpi_heat", lambda recs: rpt.render_kpi_heatcard_markdown(
        rpt.kpi_heat_cells(recs, "t1_ttft_ms"), "t1_ttft_ms")),
    ("stability", lambda recs: stability.render_markdown(
        stability.stability_cells(recs, "t1_ttft_ms"), "t1_ttft_ms")),
    ("transport", lambda recs: transport_rollup.render_markdown(
        transport_rollup.analyze(recs))),
    ("order_effect", lambda recs: order_effect.render_markdown(
        order_effect.analyze(recs, kpi="t1_ttft_ms"))),
    ("trend", lambda recs: trend.render_markdown(trend.analyze(recs))),
    ("buffering", lambda recs: buffering_rollup.render_markdown(
        buffering_rollup.analyze(recs))),
    ("subscore", lambda recs: subscore_rollup.render_markdown(
        subscore_rollup.analyze(recs))),
)


def test_every_pooling_section_keeps_the_banner_s_promise():
    """The corpus banner and publish_check both tell the reader that impossible
    values are 「已排除出中位数」 and that the affected cell carries a marker.
    That held in two sections out of seven — the other five pooled the value into
    the median with no marker anywhere, so the banner was not a warning, it was a
    false statement about the tables underneath it (D-197).

    Checked per section, never against the assembled report: the banner NAMES
    the marker, so a whole-report substring search passes while no table carries
    it — the over-wide probe that hid this once already (D-181).
    """
    recs = _corrupt_corpus()
    for name, render in _POOLING_SECTIONS:
        assert "IMPLAUSIBLE_VALUE" in render(recs), name


def test_an_impossible_reading_changes_no_number_it_only_adds_a_marker():
    """Excluded means excluded: every statistic must come out exactly as it does
    on the corpus without that run. A value that still moves the median while a
    marker apologises for it would be the worst of both (D-197)."""
    corrupt = _corrupt_corpus()
    clean = [r for r in corrupt if cc.run_aqs(r) != 9999]
    assert len(clean) == len(corrupt) - 1

    a = stability.stability_cells(corrupt, "t1_ttft_ms")[0]
    b = stability.stability_cells(clean, "t1_ttft_ms")[0]
    for k in ("n", "mean", "median", "cv_percent", "stdev", "unstable"):
        assert a[k] == b[k], (k, a[k], b[k])
    assert a["implausible_values"] and not b["implausible_values"]

    ha, hb = rpt.heat_cells(corrupt)[0], rpt.heat_cells(clean)[0]
    assert (ha["aqs_median"], ha["n"], ha["stdev"]) == (hb["aqs_median"], hb["n"],
                                                        hb["stdev"])

    # The noise scale is the statistic an outlier hurts most: the median shrugs
    # one bad value off, this does not, and a corrupt one quietly declares every
    # real difference in the corpus to be noise.
    ta, tb = transport_rollup.transport_cells(corrupt)[0], \
        transport_rollup.transport_cells(clean)[0]
    assert ta["noise"] == tb["noise"]
    assert ta["transports"]["cellular"]["aqs_median"] == \
        tb["transports"]["cellular"]["aqs_median"]


def test_a_non_positive_mean_yields_no_cv_rather_than_a_reassuring_one():
    """CV = stdev/mean says nothing about sign: a non-positive mean gives a
    NEGATIVE CV, and `cv > gate` is then false for every gate, so the least
    repeatable cell in the corpus renders 稳定 with an empty note (D-197).

    Reachable whenever the pooled quantity has no declared range — a signed
    reading such as dBm — so this guard belongs in cv_percent, not only in the
    range table.
    """
    assert stability.cv_percent([-100, -400]) is None
    assert stability.cv_reason([-100, -400], None) == "mean<=0"
    assert stability.cv_reason([5], None) == "n<2"
    assert stability.cv_reason([8, 10, 12], 20.0) is None
    cell = {"cell": {"point_id": "P1"}, "n": 2, "median": -250.0, "mean": -250.0,
            "cv_percent": None, "cv_not_computable_reason": "mean<=0",
            "unstable": False, "low_confidence": True, "kpi": "rsrp_dbm"}
    body = stability.render_markdown([cell], "rsrp_dbm").split("|---")[-1]
    assert "均值≤0" in body
    assert "稳定" not in body        # no verdict at all, reassuring or otherwise
