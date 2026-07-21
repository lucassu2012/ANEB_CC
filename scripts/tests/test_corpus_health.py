# -*- coding: utf-8 -*-
"""Golden reflex tests for run_id de-duplication + corpus_health.py.

The invariant under test is a CORRECTNESS one: the same run re-exported into two
files must not be counted twice, because double-counting silently inflates every
median's sample count and therefore the reported confidence.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import campaign_common as cc
import corpus_health as ch
import campaign_report as rpt
from synth import make_record, aqs_records


def _write(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- dedup core

def test_unique_run_ids_all_kept():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.jsonl")
        _write(p, aqs_records(90, 5))
        stats = {}
        recs, _ = cc.load_records([p], stats=stats, quiet=True)
        assert len(recs) == 5
        assert stats["duplicates"] == 0
        assert stats["kept"] == 5


def test_same_run_id_across_two_files_counted_once():
    """The exact double-counting bug: one run re-exported into two files."""
    rec = make_record(aqs=90, run_id="dup-1")
    with tempfile.TemporaryDirectory() as d:
        a, b = os.path.join(d, "a.jsonl"), os.path.join(d, "b.jsonl")
        _write(a, [rec])
        _write(b, [rec])          # identical re-export (D-09 dual-write style)
        stats = {}
        recs, files = cc.load_records([a, b], stats=stats, quiet=True)
        assert len(files) == 2
        assert len(recs) == 1     # NOT 2
        assert stats["duplicates"] == 1
        assert stats["conflicts"] == []   # identical body -> benign


def test_conflicting_duplicate_flagged():
    """Same run_id, DIFFERENT body = real integrity fault, not a re-export."""
    a_rec = make_record(aqs=90, run_id="dup-1")
    b_rec = make_record(aqs=42, run_id="dup-1")   # same id, different score
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.jsonl")
        _write(p, [a_rec, b_rec])
        stats = {}
        recs, _ = cc.load_records([p], stats=stats, quiet=True)
        assert len(recs) == 1
        assert stats["duplicates"] == 1
        assert "dup-1" in stats["conflicts"]


def test_records_without_run_id_are_kept_not_merged():
    """No run_id => cannot dedupe => keep both (never merge under a fake key)."""
    r1 = make_record(aqs=90)
    r2 = make_record(aqs=80)
    for r in (r1, r2):
        r["run"].pop("run_id")
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.jsonl")
        _write(p, [r1, r2])
        stats = {}
        recs, _ = cc.load_records([p], stats=stats, quiet=True)
        assert len(recs) == 2
        assert stats["no_run_id"] == 2
        assert stats["duplicates"] == 0


def test_dedupe_can_be_disabled():
    rec = make_record(aqs=90, run_id="dup-1")
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.jsonl")
        _write(p, [rec, rec])
        recs, _ = cc.load_records([p], dedupe=False, quiet=True)
        assert len(recs) == 2


def test_dedup_prevents_inflated_heat_cell_n():
    """End-to-end consequence: duplicate export must not inflate cell n."""
    recs = aqs_records(90, 3, point="P1")
    with tempfile.TemporaryDirectory() as d:
        a, b = os.path.join(d, "a.jsonl"), os.path.join(d, "b.jsonl")
        _write(a, recs)
        _write(b, recs)                     # whole file duplicated
        loaded, _ = cc.load_records([a, b], quiet=True)
        cells = rpt.heat_cells(loaded)
        assert cells[0]["n"] == 3           # not 6


# ---------------------------------------------------------------- health CLI

def test_health_clean_corpus():
    stats = {}
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.jsonl")
        _write(p, aqs_records(90, 5))
        recs, _ = cc.load_records([p], stats=stats, quiet=True)
    rep = ch.analyze(recs, stats)
    assert rep["healthy"] is True
    assert rep["errors"] == []
    assert rep["loaded"] == 5


def test_health_flags_claim_scope_drift():
    rec = make_record(aqs=90)
    rec["claim_scope"] = "radio_layer_mos"      # different measurement scope
    stats = {}
    rep = ch.analyze([rec], stats)
    assert rep["healthy"] is False
    assert any("claim_scope" in e for e in rep["errors"])


def test_health_flags_malformed_and_conflicts():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps(make_record(aqs=90, run_id="x")) + "\n")
            f.write("{not json\n")
            f.write(json.dumps(make_record(aqs=10, run_id="x")) + "\n")
        stats = {}
        recs, _ = cc.load_records([p], stats=stats, quiet=True)
    rep = ch.analyze(recs, stats)
    assert rep["healthy"] is False
    assert any("malformed" in e for e in rep["errors"])
    assert any("conflicting" in e for e in rep["errors"])


def test_health_warns_benign_duplicate_without_failing():
    rec = make_record(aqs=90, run_id="dup-1")
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.jsonl")
        _write(p, [rec, rec])
        stats = {}
        recs, _ = cc.load_records([p], stats=stats, quiet=True)
    rep = ch.analyze(recs, stats)
    assert rep["healthy"] is True                       # benign -> not an error
    assert any("de-duplicated" in w for w in rep["warnings"])


def test_health_warns_unlabeled_corpus():
    recs = [make_record(aqs=88) for _ in range(3)]      # no run.campaign
    rep = ch.analyze(recs, {})
    assert rep["healthy"] is True
    assert any("run.campaign" in w for w in rep["warnings"])


def test_health_markdown_renders():
    recs = aqs_records(90, 5)
    md = ch.render_markdown(ch.analyze(recs, {"lines": 5, "kept": 5}), ["a.jsonl"])
    assert "语料完整性体检" in md
    assert "结论" in md
