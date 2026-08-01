# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/trust_rollup.py (instrument trust)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import trust_rollup as tu
from synth import make_record


def _rec(*, clock=None, kpi=None, parse=None, point="P1"):
    rec = make_record(
        campaign={"campaign_id": "base", "tier": "metro", "point_id": point,
                  "carrier": "cmcc", "time_band": "busy"},
        aqs=90, scenarios=[("s1_chat", dict(kpi or {}))])
    scn = rec["scenarios"][0]
    if clock is not None:
        scn["clock"] = clock
    if parse is not None:
        scn["parse"] = parse
    return rec


def test_suspect_share_and_abs_drift():
    recs = ([_rec(clock={"offset_suspect": True, "drift_ppm": -150.0}) for _ in range(3)]
            + [_rec(clock={"offset_suspect": False, "drift_ppm": 10.0}) for _ in range(2)])
    c = tu.analyze(recs)["cells"][0]
    assert c["clock_annotated"] == 5
    assert c["clock_suspect"] == 3
    assert c["clock_suspect_share"] == 0.6
    assert c["abs_drift_ppm_median"] == 150.0      # |-150| median of [150,150,150,10,10]
    assert c["clock_hotspot"] is True


def test_unannotated_clock_not_counted_as_clean():
    recs = [_rec(clock={"offset_suspect": True, "drift_ppm": 200.0})] \
        + [_rec() for _ in range(4)]               # empty clock {} = unannotated
    c = tu.analyze(recs)["cells"][0]
    assert c["clock_annotated"] == 1               # denominators exclude unannotated
    assert c["clock_suspect_share"] == 1.0
    assert c["clock_hotspot"] is True              # of ANNOTATED clocks, all suspect


def test_exactly_half_suspect_is_not_hotspot():
    recs = ([_rec(clock={"offset_suspect": True}) for _ in range(2)]
            + [_rec(clock={"offset_suspect": False}) for _ in range(2)])
    assert tu.analyze(recs)["cells"][0]["clock_hotspot"] is False


# ------------------------------------------------------- 低置信定位（D-373）

def _rec_quality(quality):
    rec = _rec(clock={"offset_suspect": False})
    rec["scenarios"][0]["kpi_quality"] = quality
    return rec


def test_kpi_quality_rollup_names_which_kpi_is_short_and_by_how_much():
    """试点报告附二第一建议的读者半边:低置信判词带上理由——哪个 KPI、
    低置信几次、最少几个样本。两半都钉:被标注的行与干净的行。"""
    recs = [_rec_quality({"U2": {"sample_count": 5, "low_confidence": True},
                          "N1": {"sample_count": 20, "low_confidence": False}})
            for _ in range(3)]
    res = tu.analyze(recs)
    kq = res["kpi_quality"]
    assert kq["U2"] == {"annotated": 3, "low": 3, "min_n": 5}, kq
    assert kq["N1"] == {"annotated": 3, "low": 0, "min_n": 20}, kq
    md = tu.render_markdown(res)
    assert "低置信定位" in md
    assert "| U2 | 3 | 3 (100%) | 5 |" in md, md
    assert "| N1 | 3 | 0 (0%) | 20 |" in md, md


def test_a_corpus_without_kpi_quality_reports_a_gap_not_silence():
    """v17 之前的语料没有 kpi_quality:定位段必须说「无法定位」,
    而不是消失或渲染一张空表读成「没有低置信」(缺席≠全好,R-10)。"""
    res = tu.analyze([_rec(clock={"offset_suspect": False})])
    assert res["kpi_quality"] == {}
    md = tu.render_markdown(res)
    assert "无法定位" in md and "不等于没有" in md, md


def test_stream_bad_on_gap_or_dup():
    recs = [_rec(kpi={"seq_gap_count": 1, "seq_dup_count": 0}),
            _rec(kpi={"seq_gap_count": 0, "seq_dup_count": 2}),
            _rec(kpi={"seq_gap_count": 0, "seq_dup_count": 0})]
    c = tu.analyze(recs)["cells"][0]
    assert c["stream_counted"] == 3
    assert c["stream_bad"] == 2


def test_null_seq_counts_not_in_denominator():
    recs = [_rec(kpi={"seq_gap_count": None, "seq_dup_count": None}),
            _rec(kpi={"seq_gap_count": 0, "seq_dup_count": 0})]
    c = tu.analyze(recs)["cells"][0]
    assert c["stream_counted"] == 1                # null = not measured, not clean


def test_parse_median():
    recs = [_rec(parse={"per_event_parse_us": v}) for v in (10, 42, 100)]
    assert tu.analyze(recs)["cells"][0]["parse_per_event_us_median"] == 42


def test_no_evidence_renders_coverage_gap():
    md = tu.render_markdown(tu.analyze([_rec() for _ in range(3)]))
    assert "无可信度证据" in md
    assert "非全部可信" in md


def test_markdown_renders_r22_and_hotspot():
    recs = [_rec(clock={"offset_suspect": True, "drift_ppm": 200.0}) for _ in range(5)]
    md = tu.render_markdown(tu.analyze(recs))
    assert "R-22" in md
    assert "时钟可疑热点" in md
    assert "不算干净" in md


def test_cells_separated_by_point():
    recs = ([_rec(clock={"offset_suspect": True}, point="P1") for _ in range(2)]
            + [_rec(clock={"offset_suspect": False}, point="P2") for _ in range(2)])
    by = {c["cell"]["point_id"]: c for c in tu.analyze(recs)["cells"]}
    assert by["P1"]["clock_hotspot"] is True
    assert by["P2"]["clock_hotspot"] is False
