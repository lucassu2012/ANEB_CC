# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/provenance.py + its report integration."""
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import provenance as prov
import campaign_report as rpt
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
    recs = aqs_records(90, 5)
    a = rpt.build_report_markdown(recs)
    b = rpt.build_report_markdown(recs)
    assert a == b                                   # snapshot-safe
    assert "provenance" not in a                    # no manifest unless asked


def test_report_includes_provenance_when_supplied():
    recs = aqs_records(90, 5)
    m = prov.compute([], {"lines": 5, "kept": 5}, {"min_samples": 5}, generated_at="2026-01-01")
    md = rpt.build_report_markdown(recs, provenance=m)
    assert "溯源 / provenance" in md
    assert "2026-01-01" in md
