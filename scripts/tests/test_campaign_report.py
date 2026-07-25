# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/campaign_report.py + campaign_common bands."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import re

import campaign_common as cc
import campaign_report as rpt
from synth import aqs_records, make_record, kpi_scenario_records


def test_heatcard_cells_and_grades():
    recs = (aqs_records(91, 5, point="P1", time_band="busy")
            + aqs_records(60, 5, point="P1", time_band="idle"))
    cells = rpt.heat_cells(recs)
    by = {(c["cell"]["point_id"], c["cell"]["time_band"]): c for c in cells}
    assert by[("P1", "busy")]["aqs_median"] == 91
    assert by[("P1", "busy")]["grade"] == "excellent"
    assert by[("P1", "busy")]["n"] == 5
    assert by[("P1", "busy")]["low_confidence"] is False
    assert by[("P1", "idle")]["grade"] == "fair"


def test_low_confidence_cell():
    cells = rpt.heat_cells(aqs_records(80, 2, point="P2"))  # n=2 < 5
    assert cells[0]["low_confidence"] is True


def test_inventory_status_buckets_by_prefix():
    recs = aqs_records(90, 3)
    recs[1]["run"]["status"] = "aborted:timeout"
    recs[2]["run"]["status"] = "aborted:user"
    inv = rpt.inventory(recs)
    # `aborted:<reason>` collapses to one bucket; reasons stay in raw records
    assert inv["statuses"] == {"completed": 1, "aborted": 2}


def test_report_surfaces_non_completed_runs():
    recs = aqs_records(90, 5)
    recs[0]["run"]["status"] = "aborted:timeout"
    md = rpt.build_report_markdown(recs)
    assert "run 状态 status" in md
    assert "'aborted': 1" in md
    assert "只显性化，不静默剔除" in md
    # all-completed corpus carries the line but not the warning
    md2 = rpt.build_report_markdown(aqs_records(90, 5))
    assert "run 状态 status" in md2
    assert "只显性化" not in md2


def test_before_after_delta():
    recs = (aqs_records(70, 5, point="P1", time_band="busy", campaign_id="base")
            + aqs_records(85, 5, point="P1", time_band="busy", campaign_id="opt"))
    cmp = rpt.compare_campaigns(recs, "base", "opt")
    assert len(cmp["rows"]) == 1
    r = cmp["rows"][0]
    assert r["before"] == 70
    assert r["after"] == 85
    assert r["delta"] == 15


def test_before_after_only_one_side():
    recs = aqs_records(70, 5, point="P1", campaign_id="base")  # no 'opt' side
    cmp = rpt.compare_campaigns(recs, "base", "opt")
    r = cmp["rows"][0]
    assert r["before"] == 70
    assert r["after"] is None
    assert r["delta"] is None          # not fabricated
    assert r["low_confidence"] is True  # one side missing -> flagged


def _spread(values, **kw):
    """One record per value, so the cell has real spread (aqs_records is constant)."""
    return [r for v in values for r in aqs_records(v, 1, **kw)]


def test_noise_scale_flags_subnoise_delta():
    # same wide spread on both sides, tiny shift -> the shift is not a finding
    recs = (_spread([60, 70, 80, 90, 100], point="P1", campaign_id="base")
            + _spread([62, 72, 82, 92, 102], point="P1", campaign_id="opt"))
    r = rpt.compare_campaigns(recs, "base", "opt")["rows"][0]
    assert r["delta"] == 2
    assert r["noise"] > 2
    assert r["within_noise"] is True


def test_noise_scale_lets_real_delta_through():
    recs = (_spread([60, 70, 80, 90, 100], point="P1", campaign_id="base")
            + _spread([110, 120, 130, 140, 150], point="P1", campaign_id="opt"))
    r = rpt.compare_campaigns(recs, "base", "opt")["rows"][0]
    assert r["delta"] == 50
    assert r["within_noise"] is False


def test_noise_unknown_is_not_reported_as_real():
    # one sample per side -> spread unknown -> noise unknown; R-10: not False, not 0
    recs = (aqs_records(70, 1, point="P1", campaign_id="base")
            + aqs_records(85, 1, point="P1", campaign_id="opt"))
    r = rpt.compare_campaigns(recs, "base", "opt")["rows"][0]
    assert r["delta"] == 15
    assert r["noise"] is None
    assert r["within_noise"] is None
    # and the summary must not bank it as an improvement
    summary = rpt.render_summary_markdown(recs, min_samples=1)
    assert "噪声无法估计" in summary
    assert "0 个 Δ 超出噪声——改善 0" in summary


def test_summary_noise_buckets_add_up():
    recs = (_spread([60, 70, 80, 90, 100], point="P1", campaign_id="base")
            + _spread([62, 72, 82, 92, 102], point="P1", campaign_id="opt")
            + _spread([60, 70, 80, 90, 100], point="P2", campaign_id="base")
            + _spread([110, 120, 130, 140, 150], point="P2", campaign_id="opt"))
    summary = rpt.render_summary_markdown(recs)
    line = [l for l in summary.splitlines() if "优化前后" in l][0]
    assert "2 个共同格中 1 个 Δ 超出噪声——改善 1、回退 0、持平 0" in line
    assert "1 个格 Δ 在噪声内" in line


def test_noise_reaches_all_three_surfaces():
    """The same defect once per surface is this repo's most repeated bug (D-140).
    Markdown, HTML and CSV must agree on which cells are within noise."""
    import csv as csvmod
    import os
    import tempfile
    recs = (_spread([60, 70, 80, 90, 100], point="P1", campaign_id="base")
            + _spread([62, 72, 82, 92, 102], point="P1", campaign_id="opt")     # noisy
            + _spread([60, 70, 80, 90, 100], point="P2", campaign_id="base")
            + _spread([110, 120, 130, 140, 150], point="P2", campaign_id="opt")  # real
            + aqs_records(70, 1, point="P3", campaign_id="base")                 # unknown
            + aqs_records(85, 1, point="P3", campaign_id="opt"))
    md = rpt.build_report_markdown(recs)
    html = rpt.build_report_html(recs, "2026-01-01 00:00:00")
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "camp")
        rpt.write_csv_tables(recs, prefix)
        with open(prefix + "_comparison.csv", encoding="utf-8-sig") as f:
            rows = list(csvmod.DictReader(f))
    csv_noisy = [r for r in rows if r["within_noise"] == "True"]
    csv_unknown = [r for r in rows if not r["within_noise"]]
    assert len(csv_noisy) == 1 and len(csv_unknown) == 1
    # the caveat is the load-bearing half — a bare number invites over-reading
    assert "不是显著性检验" in md and "不是显著性检验" in html
    # match markers that only occur in table rows — the caveat mentions both
    # phrases too, and the summary bullet words it a third way
    assert md.count("**噪声内**") == len(csv_noisy)
    assert html.count("<td>噪声内</td>") == len(csv_noisy)
    assert md.count("噪声不可估") == len(csv_unknown)
    assert html.count("<td>噪声不可估</td>") == len(csv_unknown)
    # …and the summary must carry the same two counts in prose
    assert "1 个格 Δ 在噪声内" in md and "1 个格噪声无法估计" in md
    # unknown noise stays empty in CSV — never 0, never False (R-10)
    assert csv_unknown[0]["noise"] == ""


def test_graceful_without_labels():
    recs = [make_record(aqs=88, scenarios=[]) for _ in range(3)]  # no campaign block
    inv = rpt.inventory(recs)
    assert inv["with_campaign"] == 0
    cells = rpt.heat_cells(recs)
    assert len(cells) == 1
    assert cells[0]["cell"] == {"point_id": "unlabeled", "carrier": "unknown",
                                "time_band": "unknown"}


def test_aqs_grade_band_boundaries():
    assert cc.aqs_grade(85) == "excellent"
    assert cc.aqs_grade(84.999) == "good"
    assert cc.aqs_grade(70) == "good"
    assert cc.aqs_grade(69.999) == "fair"
    assert cc.aqs_grade(54) == "fair"
    assert cc.aqs_grade(53.999) == "poor"
    assert cc.aqs_grade(None) == "n/a"


def test_percentile_nearest_rank():
    assert cc.percentile([1, 2, 3, 4, 5], 50) == 3
    assert cc.percentile([1, 2, 3, 4, 5], 90) == 5
    assert cc.percentile([], 50) is None


def test_full_report_builds_and_marks_claim_scope():
    recs = aqs_records(91, 5)
    md = rpt.build_report_markdown(recs)
    assert "application_end_to_end_to_probe_node" in md
    assert "热力卡" in md
    html_out = rpt.build_report_html(recs, "2026-01-01 00:00:00")
    assert "<!DOCTYPE html>" in html_out
    assert "战役级综合报告" in html_out


def test_report_flags_unlabeled_corpus():
    recs = [make_record(aqs=88, scenarios=[]) for _ in range(3)]
    md = rpt.build_report_markdown(recs)
    assert "无 `run.campaign` 标签" in md  # honest coverage warning


def test_kpi_grade_field_mapping():
    assert rpt.kpi_grade_field("n1_rtt_p50_ms") == "n1_grade"
    assert rpt.kpi_grade_field("t1_ttft_ms") == "t1_grade"
    assert rpt.kpi_grade_field("u1_goodput_mbps") == "u1_grade"


def test_kpi_heatcard_median_and_authoritative_grade():
    recs = kpi_scenario_records(5, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "excellent"})
    cells = rpt.kpi_heat_cells(recs, "n1_rtt_p50_ms")
    assert len(cells) == 1
    c = cells[0]
    assert c["median"] == 20
    assert c["grade"] == "excellent"   # from the record's n1_grade, not AQS bands
    assert c["n"] == 5
    assert c["low_confidence"] is False


def test_kpi_heat_modal_grade_majority():
    recs = (kpi_scenario_records(3, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "excellent"})
            + kpi_scenario_records(2, kpi={"n1_rtt_p50_ms": 90, "n1_grade": "poor"}))
    c = rpt.kpi_heat_cells(recs, "n1_rtt_p50_ms")[0]
    assert c["grade"] == "excellent"   # 3 > 2 modal
    assert c["n"] == 5


def test_report_includes_per_kpi_sections():
    recs = kpi_scenario_records(5, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "excellent"}, aqs=90)
    md = rpt.build_report_markdown(recs)
    assert "分 KPI 热力卡" in md
    assert "n1_rtt_p50_ms" in md


def test_report_includes_stability_and_both_attr_kpis():
    md = rpt.build_report_markdown(kpi_scenario_records(
        5, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "excellent"}, aqs=90))
    assert "复测稳定性" in md


def test_csv_export_content():
    import csv as csvmod
    import os
    import tempfile
    recs = aqs_records(91, 5, point="P1")
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "camp")
        paths = rpt.write_csv_tables(recs, prefix)
        assert any(p.endswith("_heat.csv") for p in paths)
        # utf-8-sig, matching how the files are written (D-129) — a plain utf-8
        # reader would carry the BOM into the first column name
        with open(prefix + "_heat.csv", encoding="utf-8-sig") as f:
            rows = list(csvmod.DictReader(f))
        assert rows[0]["point_id"] == "P1"
        assert rows[0]["grade"] == "excellent"
        assert float(rows[0]["aqs_median"]) == 91.0


# ---------------------------------------------------------------- summary parity
#
# The summary (D-117) re-states each filter condition instead of reusing the
# renderers, so a future threshold edit on either side could make it disagree
# with the very tables it points into — a report that lies about itself. These
# pin the invariant: the count in a summary bullet equals the number of rows a
# READER can count in the corresponding section.

def _section(md, title_startswith):
    """The markdown of one '## ' section, by title prefix."""
    for chunk in re.split(r"(?m)^## ", md)[1:]:
        if chunk.startswith(title_startswith):
            return chunk
    raise AssertionError(f"section not found: {title_startswith}")


def _rows_containing(section, marker):
    return sum(1 for ln in section.splitlines()
               if ln.startswith("| ") and marker in ln)


def _summary_count(md, bullet_prefix):
    """The leading integer of a summary bullet, e.g. '**批化失真热点**：2 个'."""
    summary = _section(md, "摘要")
    for ln in summary.splitlines():
        if ln.startswith(f"- **{bullet_prefix}"):
            m = re.search(r"[：:]\s*\*?\*?(\d+)", ln)
            assert m, f"no count in bullet: {ln}"
            return int(m.group(1))
    return None          # bullet worded as "no problem" / "no data"


def _problem_corpus():
    """Two points: P1 seeded with a batching hot-spot, a suspect clock and a
    low validity rate; P2 clean. Grades: P1 fair (68), P2 excellent (95)."""
    recs = []
    for point, aqs, bad in (("P1", 68, True), ("P2", 95, False)):
        for i in range(6):
            rec = make_record(
                campaign={"campaign_id": "base", "tier": "metro", "point_id": point,
                          "carrier": "cmcc", "time_band": "busy"},
                aqs=aqs, scenarios=[("s1_chat", {"n1_rtt_p50_ms": 20 + i})])
            scn = rec["scenarios"][0]
            scn["buffering"] = ({"score": 0.5, "attribution": "middlebox_suspect",
                                 "sample_count": 100, "sawtooth_ratio": 0.4,
                                 "near_zero_arrival_ratio": 0.3}
                                if bad else
                                {"score": 0.01, "attribution": "none",
                                 "sample_count": 100, "sawtooth_ratio": 0.0,
                                 "near_zero_arrival_ratio": 0.0})
            scn["clock"] = {"offset_suspect": bool(bad), "drift_ppm": 200.0 if bad else 5.0}
            if bad and i >= 3:                 # 3/6 invalid -> 50% < 80% gate
                scn["validity"] = "invalid"
                scn["invalid_reasons"] = "STREAM_ABORTED"
            recs.append(rec)
    return recs


def test_summary_distortion_count_matches_section():
    md = rpt.build_report_markdown(_problem_corpus())
    assert _summary_count(md, "批化失真热点") == \
        _rows_containing(_section(md, "批化(buffering)归因"), "**失真热点**")


def test_summary_clock_count_matches_section():
    md = rpt.build_report_markdown(_problem_corpus())
    assert _summary_count(md, "时钟可疑热点") == \
        _rows_containing(_section(md, "测量可信度"), "**时钟可疑热点**")


def test_summary_weak_cell_count_matches_heatcard():
    """fair/poor cells named in the summary must be exactly those graded so."""
    md = rpt.build_report_markdown(_problem_corpus())
    heat = _section(md, "点位 × 忙闲")
    graded_bad = sum(1 for ln in heat.splitlines()
                     if ln.startswith("| ") and ("| fair " in ln or "| poor " in ln))
    assert _summary_count(md, "体验最差格") == graded_bad


def test_summary_validity_count_matches_section():
    md = rpt.build_report_markdown(_problem_corpus())
    assert _summary_count(md, "有效率不达门") == \
        _rows_containing(_section(md, "有效性与失效原因"), "LOW_VALID_RATE")


def test_summary_names_the_dragging_score_dimension():
    """Path attribution says which SEGMENT is slow; this says which KPI
    DIMENSION drags the score — a different question (D-143)."""
    recs = [make_record(campaign={"campaign_id": "base", "tier": "metro",
                                  "point_id": "P1", "carrier": "cmcc",
                                  "time_band": "busy"},
                        aqs=90, scenarios=[],
                        sub_scores={"T1": 99, "N1": 95, "N2": 70})
            for _ in range(6)]
    line = [ln for ln in _section(rpt.build_report_markdown(recs), "摘要").splitlines()
            if "分数侧归因" in ln][0]
    assert "N2" in line and "70" in line


def test_summary_answers_did_it_get_better():
    """The headline question of any second round (D-143)."""
    recs = (aqs_records(55, 6, campaign_id="base")
            + aqs_records(75, 6, campaign_id="opt"))
    line = [ln for ln in _section(rpt.build_report_markdown(recs), "摘要").splitlines()
            if "优化前后" in ln][0]
    assert "改善 1" in line and "回退 0" in line
    assert "20" in line                      # median delta 75-55


def test_summary_names_the_dominant_path_segment():
    """The report is titled 热力卡与归因; the summary told the reader which cells
    were bad but never which segment caused it (D-142). Access 20ms, regional
    +18, core +27 -> core dominates."""
    from synth import tier_records
    recs = (tier_records("metro", "n1_rtt_p50_ms", 20, 5)
            + tier_records("regional", "n1_rtt_p50_ms", 38, 5)
            + tier_records("core", "n1_rtt_p50_ms", 65, 5))
    summary = _section(rpt.build_report_markdown(recs), "摘要")
    line = [ln for ln in summary.splitlines() if "分段归因" in ln][0]
    assert "核心骨干 1 格" in line
    assert "27" in line                      # the largest single increment


def test_summary_attribution_reports_not_computable_honestly():
    """A cell missing a tier is not computable — never folded into a segment."""
    from synth import tier_records
    recs = tier_records("metro", "n1_rtt_p50_ms", 20, 5)     # no regional/core
    line = [ln for ln in _section(rpt.build_report_markdown(recs), "摘要").splitlines()
            if "分段归因" in ln][0]
    assert "接入 1 格" in line               # access alone is still computable
    assert "TIER_MISSING" in _section(rpt.build_report_markdown(recs),
                                      "三级差分归因矩阵（n1")


def test_csv_carries_the_incomparability_flags():
    """CSV is the surface analysts compute on, and it shows only columns — a
    pooled median arrived there looking like an ordinary trustworthy number,
    with low_confidence=False (D-141)."""
    import csv as csvmod
    import tempfile
    from synth import contractify
    recs = [contractify(r) for r in
            (aqs_records(55, 6, campaign_id="base") + aqs_records(75, 6, campaign_id="opt"))]
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "t")
        rpt.write_csv_tables(recs, prefix)
        with open(prefix + "_heat.csv", encoding="utf-8-sig") as f:
            rows = list(csvmod.DictReader(f))
        assert rows[0]["aqs_median"] == "65.0"          # the pooled value
        assert rows[0]["mixed_campaigns"] == "base/opt"  # …and it says so
        with open(prefix + "_attribution.csv", encoding="utf-8-sig") as f:
            assert "incomparability" in csvmod.DictReader(f).fieldnames


def test_html_carries_the_corpus_notices_and_inventory():
    """HTML is the deliverable surface. The md->html conversion splits on '## ',
    so anything in the markdown preamble was dropped — every corpus-wide notice
    plus the whole coverage inventory were missing from HTML (D-140)."""
    recs = aqs_records(90, 6, campaign_id="base") + aqs_records(70, 6, campaign_id="opt")
    recs[0]["kpi_set"] = "agent-qoe-kpi-v0.1"
    md = rpt.build_report_markdown(recs)
    html = rpt.build_report_html(recs, "2026-01-01 00:00:00 +0800")
    for marker in ("采集时间窗", "profile 版本", "跨版本", "个战役", "run 状态", "覆盖盘点"):
        assert marker in md, f"markdown lost {marker}"
        assert marker in html, f"HTML lost {marker}"


def test_profile_versions_are_reported():
    """The skeleton says to take the profile version from the report; it was
    nowhere in the output (grep count zero) — and it is the precondition for
    comparing one point against another at all (D-139)."""
    recs = aqs_records(90, 4)
    md = rpt.build_report_markdown(recs)
    assert "profile 版本" in _section(md, "覆盖盘点")
    # mixing profile versions across the corpus is surfaced like the other versions
    recs[0]["profile_versions"] = "s1@0.3"
    md2 = rpt.build_report_markdown(recs)
    assert "跨版本" in md2 and "profile_versions=" in md2


def test_measurement_window_is_reported_in_utc():
    """The deliverable skeleton asks the author for the collection window and
    says to take it from 覆盖盘点 — which did not emit it (D-138). UTC, because
    the records carry no timezone and guessing one would be a silent assumption."""
    recs = (aqs_records(90, 2, started_ms=1783944000000)
            + aqs_records(90, 2, started_ms=1784030400000))   # +1 day
    inv = rpt.inventory(recs)
    assert inv["first_ms"] == 1783944000000
    assert inv["last_ms"] == 1784030400000
    md = rpt.build_report_markdown(recs)
    assert "采集时间窗" in _section(md, "覆盖盘点")
    assert "UTC" in _section(md, "覆盖盘点")


def test_missing_timestamps_degrade_honestly():
    recs = aqs_records(90, 3)
    for r in recs:
        r["run"]["started_at_epoch_ms"] = None
    line = [ln for ln in _section(rpt.build_report_markdown(recs), "覆盖盘点").splitlines()
            if "采集时间窗" in ln][0]
    assert "—" in line and "缺 started_at_epoch_ms" in line   # never a fabricated date


def test_mixed_version_dimensions_are_surfaced():
    """kpi_set says what the metric IS, aqs_version how the score is computed,
    app_version_code which build measured it. Pooling across them may average
    numbers that are not the same number (D-137). Real corpora already carry
    three different app_version_code values."""
    recs = aqs_records(90, 6)
    recs[0]["kpi_set"] = "agent-qoe-kpi-v0.1"
    recs[1]["run"]["app_version_code"] = 30
    inv = rpt.inventory(recs)
    assert len(inv["kpi_sets"]) == 2
    assert len(inv["app_versions"]) == 2
    md = rpt.build_report_markdown(recs)
    assert "跨版本" in md
    assert "kpi_set=" in md and "app_version_code=" in md
    assert "当同一指标平均" in md


def test_single_version_corpus_is_not_flagged():
    """No crying wolf on the normal case."""
    assert "跨版本" not in rpt.build_report_markdown(aqs_records(90, 6))


def test_cross_campaign_pooling_is_flagged_not_hidden():
    """A cell holding a baseline round and an optimisation round shows a median
    that is NEITHER — 55 and 75 pool to 65, which never happened. The number is
    still reported (never silently dropped), but the cell says so (D-135)."""
    recs = (aqs_records(55, 6, campaign_id="base")
            + aqs_records(75, 6, campaign_id="opt"))
    cell = rpt.heat_cells(recs)[0]
    assert cell["aqs_median"] == 65          # the pooled value is still shown
    assert cell["mixed_campaigns"] == ["base", "opt"]
    md = rpt.build_report_markdown(recs)
    assert "MIXED_CAMPAIGN:base/opt" in _section(md, "点位 × 忙闲")
    # and the reader is warned before reaching the heat card
    assert md.index("本语料含 **2 个战役**") < md.index("## 点位 × 忙闲")
    assert "既不是前也不是后" in md


def test_single_campaign_carries_no_mixing_flag():
    """Must not cry wolf on the normal single-campaign corpus."""
    md = rpt.build_report_markdown(aqs_records(90, 6, campaign_id="base"))
    assert rpt.heat_cells(aqs_records(90, 6))[0]["mixed_campaigns"] == []
    assert "MIXED_CAMPAIGN" not in md
    assert "个战役" not in md


def test_csv_opens_correctly_in_excel_with_cjk_labels():
    """These CSVs exist to be opened in Excel, and Excel on a Chinese Windows
    reads BOM-less UTF-8 as GBK — 深圳-CBD-01 would arrive as 娣卞湷-CBD-01
    (D-129). The BOM is what prevents that."""
    import csv as csvmod
    import tempfile
    from synth import contractify, kpi_scenario_records
    recs = [contractify(r) for r in
            kpi_scenario_records(6, aqs=90, kpi={"n1_rtt_p50_ms": 20},
                                 point="深圳-CBD-01")]
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "t")
        rpt.write_csv_tables(recs, prefix)
        raw = open(prefix + "_heat.csv", "rb").read()
        assert raw.startswith(b"\xef\xbb\xbf"), "missing UTF-8 BOM"
        with open(prefix + "_heat.csv", encoding="utf-8-sig") as f:
            rows = list(csvmod.DictReader(f))
        assert rows[0]["point_id"] == "深圳-CBD-01"   # round-trips, no mojibake


def test_summary_labels_are_distinguishable():
    """Every name listed in a summary bullet must identify ONE cell. A label that
    drops key dimensions renders duplicates the reader cannot act on — found by
    the chaos rehearsal, where three profiles of one cell all failed (D-125)."""
    recs = _problem_corpus()
    # make all three profiles of P1 fail, so validity has three cells in one
    # (point, carrier, time_band) — they must still render distinguishably
    for r in recs:
        if r["run"]["campaign"]["point_id"] != "P1":
            continue
        base = r["scenarios"][0]
        r["scenarios"] = []
        for pid in ("s1_chat", "s2_coding_agent", "s3_multimodal"):
            s = dict(base, profile_id=pid, validity="invalid",
                     invalid_reasons="STREAM_ABORTED")
            r["scenarios"].append(s)
    summary = _section(rpt.build_report_markdown(recs), "摘要")
    for line in summary.splitlines():
        if not line.startswith("- **"):
            continue
        names = re.findall(r"[／/\w\-.·]+\([^)]*\)", line.split("：", 1)[-1])
        assert len(names) == len(set(names)), f"duplicate labels in bullet: {line}"


def test_summary_says_no_problem_not_no_data_when_clean():
    """A clean corpus must read 'none found', never a bare zero that could be
    mistaken for 'not measured' (R-10)."""
    clean = [r for r in _problem_corpus()
             if r["run"]["campaign"]["point_id"] == "P2"]
    summary = _section(rpt.build_report_markdown(clean), "摘要")
    bullets = {ln.split("**")[1]: ln for ln in summary.splitlines()
               if ln.startswith("- **")}
    # batching and clock DO have evidence here -> must read "none found"
    assert "无热点格" in bullets["批化失真"]
    assert "覆盖缺口" not in bullets["批化失真"]
    assert bullets["时钟可疑热点"].endswith("无。")
    # transport genuinely has no evidence -> must say so, NOT "no problem"
    assert "覆盖缺口" in bullets["接入介质"]
