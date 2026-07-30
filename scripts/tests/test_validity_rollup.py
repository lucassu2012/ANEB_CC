# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/validity_rollup.py.

Central claim under test: the rollup must expose the ATTEMPTED denominator, so a
median resting on a small surviving subset is visible rather than implied.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import validity_rollup as vr
from synth import validity_records, make_record


def test_one_shenzhen_field_day_is_one_trend_row():
    """The UTC day rolls over at 08:00 CST, and the idle band explicitly covers
    local hours 0..7 — a deep-night idle baseline is a thing an operator goes
    out to collect. Bucketing by UTC therefore put a 03:00 session on the
    PREVIOUS row, and because the trend table only renders with more than one
    row, the timezone artefact manufactured a trend out of a single field day —
    in a table whose stated purpose is to make a decaying rate visible (D-318).
    """
    from datetime import datetime, timedelta, timezone
    import campaign_common as cc

    cst = timezone(timedelta(hours=cc.DEFAULT_TZ_OFFSET_H))
    ms = [int(datetime(2026, 8, 1, h, 0, tzinfo=cst).timestamp() * 1000)
          for h in (3, 9, 20)]

    local = {datetime.fromtimestamp(m / 1000.0, cst).strftime("%Y-%m-%d") for m in ms}
    utc = {datetime.fromtimestamp(m / 1000.0, timezone.utc).strftime("%Y-%m-%d")
           for m in ms}
    assert local == {"2026-08-01"}, local
    assert len(utc) == 2, (
        "the sessions do not straddle a UTC day boundary, so this guard would "
        "pass on any bucketing at all: %s" % sorted(utc))

    recs = [make_record(aqs=90, started_ms=m,
                        scenarios=[("s1_chat", {"t1_ttft_ms": 800})]) for m in ms]

    rows = vr.validity_trend(recs)
    assert [r["day"] for r in rows] == ["2026-08-01"], rows
    assert rows[0]["attempted"] == 3, rows

    # and the mechanism is the offset, not luck: at UTC it really does split
    assert len(vr.validity_trend(recs, tz_offset_h=0)) == 2

    # the default path must read the shared constant LIVE. Written as a default
    # argument it is evaluated once at import, and the mutation restoring that
    # form survived the whole suite: the archived-threshold perturbation was
    # satisfied by the heading and the manifest moving while the buckets stayed
    # at +8 — load-bearing in appearance only (D-318).
    old = cc.DEFAULT_TZ_OFFSET_H
    try:
        cc.DEFAULT_TZ_OFFSET_H = 0
        assert len(vr.validity_trend(recs)) == 2, (
            "changing the shared offset did not move the buckets, so it decides "
            "the wording and not the numbers")
    finally:
        cc.DEFAULT_TZ_OFFSET_H = old
    assert len(vr.validity_trend(recs)) == 1, "the offset was not restored"


def test_the_trend_heading_names_the_offset_it_bucketed_by():
    """The heading is the only thing on the page saying which day this is, and
    one that claims UTC over local buckets is worse than no heading at all
    (§2.12). Nothing pinned it: the mutation putting 「按 UTC 日」 back survived
    the whole suite, because every snapshot corpus spans a single day and the
    table only renders with more than one row — so the heading had never once
    appeared in a golden (D-318).
    """
    from datetime import datetime, timedelta, timezone
    import campaign_common as cc

    cst = timezone(timedelta(hours=cc.DEFAULT_TZ_OFFSET_H))
    recs = [make_record(aqs=90,
                        started_ms=int(datetime(2026, 8, d, 10, 0,
                                                tzinfo=cst).timestamp() * 1000),
                        scenarios=[("s1_chat", {"t1_ttft_ms": 800})])
            for d in (1, 2)]
    res = vr.analyze(recs)
    assert len(res["trend"]) == 2, (
        "corpus does not span two local days, so the table never renders and "
        "the assertions below would pass on an empty string: %s" % res["trend"])

    md = vr.render_markdown(res)
    assert "有效率趋势" in md, md[:400]
    assert f"UTC+{cc.DEFAULT_TZ_OFFSET_H}" in md, (
        "the trend heading does not say which offset it bucketed by")
    assert "按 UTC 日" not in md, (
        "the heading still claims UTC days while the buckets are local")


def test_all_valid_cell():
    res = vr.analyze(validity_records(5, validity="valid"))
    c = res["cells"][0]
    assert c["attempted"] == 5
    assert c["valid"] == 5
    assert c["valid_rate"] == 1.0
    assert c["below_min_rate"] is False
    assert res["overall_valid_rate"] == 1.0


def test_survivor_denominator_is_exposed():
    """4 valid out of 40 attempts: the heat card would only ever show n=4."""
    recs = (validity_records(4, validity="valid")
            + validity_records(36, validity="invalid", invalid_reasons="timeout"))
    c = vr.analyze(recs)["cells"][0]
    assert c["attempted"] == 40
    assert c["valid"] == 4
    assert c["invalid"] == 36
    assert c["valid_rate"] == 0.1
    assert c["below_min_rate"] is True


def test_low_confidence_counts_as_usable():
    """VALID_LOW_CONFIDENCE still produced a measurement -> usable, but tracked."""
    recs = (validity_records(3, validity="valid")
            + validity_records(2, validity="VALID_LOW_CONFIDENCE"))
    c = vr.analyze(recs)["cells"][0]
    assert c["valid"] == 3
    assert c["valid_low_confidence"] == 2
    assert c["valid_rate"] == 1.0
    assert c["invalid"] == 0


def test_unknown_validity_is_its_own_bucket_not_assumed_valid():
    recs = validity_records(4, validity="something_else")
    c = vr.analyze(recs)["cells"][0]
    assert c["unknown"] == 4
    assert c["valid"] == 0
    assert c["valid_rate"] == 0.0      # not silently treated as valid


def test_unreadable_state_is_distinguished_from_failure():
    """0% valid from failures and 0% valid from states nobody can read are two
    different findings with two different next actions — go look at the network,
    or go look at the producer. Real corpora carry `degraded`, a fourth value the
    schema enum does not list, and it lands in the denominator, so a cell full of
    it reported 有效率 0% and tripped LOW_VALID_RATE as though everything failed
    (D-190). Counting it as not-usable is the conservative direction and stays;
    the share now travels with the rate."""
    unread = vr.analyze(validity_records(5, validity="degraded"))["cells"][0]
    failed = vr.analyze(validity_records(5, validity="invalid"))["cells"][0]
    assert unread["valid_rate"] == failed["valid_rate"] == 0.0   # same number…
    assert unread["unknown_share"] == 1.0                        # …different reason
    assert failed["unknown_share"] == 0.0
    md = vr.render_markdown(vr.analyze(validity_records(5, validity="degraded")))
    assert "UNKNOWN_VALIDITY:100.0%" in md
    assert "未知按「不可用」计入有效率" in md      # the convention is stated, not implied
    # A purely failed cell must NOT pick up the marker. Match the ROW form: the
    # caveat above the table names `UNKNOWN_VALIDITY:x%` too, so a bare substring
    # check is true for every corpus — the over-broad-assertion trap this repo's
    # own handover §3 warns about, walked into once more.
    failed_md = vr.render_markdown(vr.analyze(validity_records(5, validity="invalid")))
    assert not [ln for ln in failed_md.splitlines()
                if ln.startswith("| ") and "UNKNOWN_VALIDITY" in ln]


def test_invalid_reasons_histogram():
    recs = (validity_records(3, validity="invalid", invalid_reasons="timeout")
            + validity_records(2, validity="invalid", invalid_reasons="parse_error;timeout"))
    res = vr.analyze(recs)
    assert res["corpus_reasons"]["timeout"] == 5
    assert res["corpus_reasons"]["parse_error"] == 2


def test_reason_splitting_handles_separators():
    recs = validity_records(1, validity="invalid", invalid_reasons="a;b,c|d")
    assert vr.analyze(recs)["corpus_reasons"] == {"a": 1, "b": 1, "c": 1, "d": 1}


def test_blank_reasons_produce_no_tokens():
    recs = validity_records(3, validity="valid", invalid_reasons="")
    assert vr.analyze(recs)["corpus_reasons"] == {}


def test_cells_separated_per_profile_and_point():
    recs = (validity_records(5, validity="valid", point="P1", profile="s1_chat")
            + validity_records(5, validity="invalid", point="P1", profile="s2_rag")
            + validity_records(5, validity="valid", point="P2", profile="s1_chat"))
    res = vr.analyze(recs)
    by = {(c["cell"]["point_id"], c["cell"]["profile_id"]): c for c in res["cells"]}
    assert by[("P1", "s1_chat")]["valid_rate"] == 1.0
    assert by[("P1", "s2_rag")]["valid_rate"] == 0.0
    assert by[("P2", "s1_chat")]["valid_rate"] == 1.0


def test_no_scenarios_yields_no_cells_not_zero_rate():
    res = vr.analyze([make_record(scenarios=[]) for _ in range(3)])
    assert res["cells"] == []
    assert res["overall_valid_rate"] is None      # not 0.0


def test_trend_groups_by_utc_day():
    recs = validity_records(4, validity="valid")
    res = vr.analyze(recs)
    assert len(res["trend"]) == 1
    assert res["trend"][0]["day"] == "2026-07-13"   # 1783944000000 ms UTC
    assert res["trend"][0]["usable"] == 4


def test_markdown_renders_denominator_note():
    md = vr.render_markdown(vr.analyze(
        validity_records(4, validity="valid")
        + validity_records(36, validity="invalid", invalid_reasons="timeout")))
    assert "有效样本分母" in md
    assert "LOW_VALID_RATE" in md
    assert "timeout" in md


def test_a_zero_strict_valid_cell_still_reads_a_full_rate():
    """0 in the valid column beside 100% in the rate column is correct — and
    it has to LOOK correct.

    The rate's numerator is 有效 + 低置信, but the table also carried a column
    named 有效 holding only the first term. A reader dividing that column by
    尝试 gets a different number, and on a cell whose scenarios are all
    low-confidence they get 0 against a printed 100%: the D-207 shape, one
    quantity produced by two rules (D-218). The column now names itself
    strict, and the section states the formula.
    """
    res = vr.analyze(validity_records(3, validity="valid_low_confidence"))
    c = res["cells"][0]
    assert (c["valid"], c["valid_low_confidence"], c["valid_rate"]) == (0, 3, 1.0), c

    md = vr.render_markdown(res)
    header = [ln for ln in md.splitlines() if ln.startswith("| 点位 |")][0]
    cells = [x.strip() for x in header.strip().strip("|").split("|")]
    assert "有效(严格)" in cells, cells
    assert "有效" not in cells, (
        "a column named plainly 有效 sits next to 有效率 and invites the "
        f"division that does not hold: {cells}")

    # The formula travels with the table, naming both terms of the numerator.
    assert "有效率 =（有效(严格) + 低置信）/ 尝试" in md, md[:400]

    rows = [ln for ln in md.splitlines() if ln.startswith("| ") and "100.0%" in ln]
    assert rows, md
    body = [x.strip() for x in rows[0].strip().strip("|").split("|")]
    assert body[cells.index("有效(严格)")] == "0", body
    assert body[cells.index("低置信")] == "3", body
