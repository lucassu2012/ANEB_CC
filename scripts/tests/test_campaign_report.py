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
    # the HTML note cell is a composite now (D-160 added 仅before/仅after/low_conf),
    # so match the leading marker rather than the whole cell
    assert html.count("<td>噪声内") == len(csv_noisy)
    assert md.count("噪声不可估") == len(csv_unknown)
    assert html.count("<td>噪声不可估") == len(csv_unknown)
    # low_conf must reach all three surfaces too — it used to be markdown-only,
    # so an n=1-vs-n=1 delta published as a clean result (D-160)
    csv_lowconf = [r for r in rows if r["low_confidence"] == "True"]
    assert csv_lowconf, "fixture must contain a low-confidence comparison row"
    # scope to the comparison section: low_conf legitimately appears in the
    # attribution notes too, so a whole-document count would not mean anything
    # split on the HEADING, not the phrase: the corpus banner names the section
    # too, so splitting on the bare words lands in the banner instead
    cmp_html = html.split("<h2>优化前后对比", 1)[1].split("<h2>", 1)[0]
    # …and match the ROW form: the noise caveat names `low_conf` too, which is
    # the third time a caveat word got used as a row-marker proxy (D-152/155/160)
    assert cmp_html.count("low_conf</td>") == len(csv_lowconf)
    cmp_md = md.split("## 优化前后对比", 1)[1].split("\n## ", 1)[0]
    assert cmp_md.count("low_conf |") == len(csv_lowconf)
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
    """The headline question of any second round (D-143).

    The fixture carries real spread: identical repeats give an observed spread
    of zero, which bounds nothing, so such a corpus is now classified as
    "noise not estimable" rather than as a confirmed improvement (D-169).
    """
    recs = (_spread([53, 54, 55, 56, 57, 55], campaign_id="base")
            + _spread([73, 74, 75, 76, 77, 75], campaign_id="opt"))
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
    assert "本语料含" not in md          # the pooling notice, not any mention of 战役


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


def _rollup_csv(tmp_prefix, table):
    import csv as csvmod
    with open(tmp_prefix + f"_{table}.csv", encoding="utf-8-sig") as f:
        return list(csvmod.DictReader(f))


def test_rollup_csvs_mark_pooled_campaigns():
    """CSV has no banners: an analyst filtering a rollup table would otherwise
    see a median that is neither the before nor the after (D-141/147).

    Uses the rehearsal generator because these five tables need validity,
    sub_scores, clock, transport and buffering blocks — a thinner fixture makes
    the tables empty and the test pass for the wrong reason.
    """
    import os
    import tempfile
    import synth_campaign as sc
    recs = sc.generate(points=2, repeats=2, campaigns=("base", "opt"),
                       carriers=("cmcc",), time_bands=("busy",), tiers=("metro",))
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "camp")
        rpt.write_csv_tables(recs, prefix)
        for table in ("validity", "subscores", "trust", "transport", "buffering"):
            rows = _rollup_csv(prefix, table)
            assert rows, f"{table} produced no rows"
            assert all(r["mixed_campaigns"] == "SYNTH-base/SYNTH-opt" for r in rows), table


def test_single_campaign_rollup_csvs_are_unmarked():
    """A flag that fires on clean corpora trains people to ignore it (D-134)."""
    import os
    import tempfile
    import synth_campaign as sc
    recs = sc.generate(points=2, repeats=2, campaigns=("base",),
                       carriers=("cmcc",), time_bands=("busy",), tiers=("metro",))
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "camp")
        rpt.write_csv_tables(recs, prefix)
        for table in ("validity", "subscores", "trust", "transport", "buffering"):
            rows = _rollup_csv(prefix, table)
            assert rows, f"{table} produced no rows"
            assert all(r["mixed_campaigns"] == "" for r in rows), table


def test_report_is_independent_of_input_order():
    """Same records, different file order, byte-identical report.

    The appendix of every report promises "same input + same thresholds = same
    numbers". It was not true: Counter insertion order leaked into the coverage
    inventory, and — far worse — a tied modal grade was decided by whichever
    record was read first, so one cell rendered `good` or `poor` depending on
    the order of the input files (D-148).
    """
    import random
    import synth_campaign as sc
    recs = sc.generate(points=3, repeats=3, campaigns=("base", "opt"),
                       carriers=("cmcc", "cucc"), time_bands=("busy", "idle"),
                       tiers=("metro", "regional", "core"), seed=7)
    shuffled = list(recs)
    random.Random(1).shuffle(shuffled)
    assert rpt.build_report_markdown(shuffled) == rpt.build_report_markdown(recs)
    # all three surfaces, since HTML has its own rich renderers (D-141)
    assert (rpt.build_report_html(shuffled, "X") == rpt.build_report_html(recs, "X"))
    import os
    import tempfile

    def _csvs(rs):
        with tempfile.TemporaryDirectory() as d:
            paths = rpt.write_csv_tables(rs, os.path.join(d, "c"))
            return {os.path.basename(x): open(x, encoding="utf-8-sig").read()
                    for x in paths}

    assert _csvs(shuffled) == _csvs(recs)


def test_tied_kpi_grade_is_not_decided_by_a_coin_flip():
    """A 50/50 split is two populations, not a mode — naming one fabricates a
    verdict, and naming it by input order makes it unreproducible."""
    recs = (kpi_scenario_records(3, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "good"})
            + kpi_scenario_records(3, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "poor"}))
    c = rpt.kpi_heat_cells(recs, "n1_rtt_p50_ms")[0]
    assert c["grade"] is None
    assert c["grade_tie"] == ["good", "poor"]
    md = rpt.render_kpi_heatcard_markdown([c], "n1_rtt_p50_ms")
    assert "GRADE_TIE:good/poor" in md
    # a clear majority still yields a grade
    recs += kpi_scenario_records(1, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "poor"})
    c2 = rpt.kpi_heat_cells(recs, "n1_rtt_p50_ms")[0]
    assert c2["grade"] == "poor" and c2["grade_tie"] == []


def _stamped(cid, aqs, ms, n=5):
    from synth import contractify
    rs = [contractify(r) for r in aqs_records(aqs, n, point="P1", campaign_id=cid)]
    for r in rs:
        r["run"]["started_at_epoch_ms"] = ms
    return rs


def test_seconds_epoch_recreates_the_d161_inversion():
    """An out-of-range epoch is worse than a missing one: it still SORTS. The
    later, better round carried a seconds-valued timestamp, sorted to 1970,
    became 'before', and a 30-point improvement was published as Δ -30 — the
    exact D-161 outcome, through a door D-161 did not close, with the basis
    still reported as 'time'."""
    ms, sec = 1783944000000, 1784030400          # post-qos is later AND better
    recs = _stamped("pre-qos", 50, ms) + _stamped("post-qos", 80, sec)
    inv = rpt.inventory(recs)
    assert inv["campaigns_bad_ms"] == {"post-qos"}
    assert dict(inv["implausible_ms"]) == {"疑似秒(应为毫秒)": 5}
    # refuse to order rather than order by a number that is not a time
    assert rpt.compare_basis(inv) == "bad_timestamps"
    assert rpt.auto_compare_ids(inv) == (None, None)
    # a plausible corpus is untouched — the guard must not cost the normal path
    good = rpt.inventory(_stamped("pre-qos", 50, ms) + _stamped("post-qos", 80, ms + 86400000))
    assert rpt.compare_basis(good) == "time"
    assert rpt.auto_compare_ids(good) == ("pre-qos", "post-qos")


def test_bad_epoch_is_visible_on_every_surface():
    recs = _stamped("pre-qos", 50, 1783944000000) + _stamped("post-qos", 80, 1784030400)
    md = rpt.build_report_markdown(recs)
    html = rpt.build_report_html(recs, "2026-01-01 00:00:00")
    assert "不像毫秒时间戳" in md and "不像毫秒时间戳" in html
    # the window line prints 1970 arithmetic — it must not read as a fact about
    # when the data was collected
    win = [l for l in md.splitlines() if "采集时间窗" in l][0]
    assert "此窗口不可信" in win
    # and the summary says why no pair was formed, instead of the section
    # vanishing (D-150: a silent check is no check)
    bullet = [l for l in md.splitlines() if l.startswith("- **优化前后**")][0]
    assert "不自动配对" in bullet


def test_epoch_problem_names_the_unit_slip():
    """'out of range' does not tell the operator what to fix; seconds and
    microseconds are different producer bugs."""
    assert cc.epoch_ms_problem(1783944000000) is None      # 2026, plausible
    assert cc.epoch_ms_problem(1783944000) == "疑似秒(应为毫秒)"
    assert cc.epoch_ms_problem(1783944000000000) == "疑似微秒/纳秒(应为毫秒)"
    assert cc.epoch_ms_problem(0) == "非正值"
    assert cc.epoch_ms_problem(-5) == "非正值"
    assert cc.epoch_ms_problem(12345) == "超出合理范围"     # uptime clock, not wall clock
    assert cc.epoch_ms_problem(None) is None               # absent != implausible
    assert cc.epoch_ms_problem(float("nan")) is None       # already rejected by fnum


def test_grade_tie_reaches_html_and_csv():
    """GRADE_TIE was markdown-only. The HTML pivot rendered the tied cell as
    'n/a' — indistinguishable from 'never graded' — and the per-KPI card had no
    CSV at all, the one surface an analyst computes on (D-141/148/160)."""
    import csv as csvmod
    import os
    import tempfile
    recs = (kpi_scenario_records(3, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "good"})
            + kpi_scenario_records(3, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "poor"}))
    html = rpt.build_report_html(recs, "2026-01-01 00:00:00")
    assert "⚠并列good/poor" in html
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "camp")
        paths = rpt.write_csv_tables(recs, prefix)
        assert any(p.endswith("_kpi_heat.csv") for p in paths)
        with open(prefix + "_kpi_heat.csv", encoding="utf-8-sig") as f:
            rows = [r for r in csvmod.DictReader(f) if r["kpi"] == "n1_rtt_p50_ms"]
    assert rows, "the per-KPI CSV must carry rows, or this test proves nothing"
    assert rows[0]["grade_tie"] == "good/poor"
    assert rows[0]["grade"] == ""          # R-10: no winner, not a fabricated one


def test_kpi_heatcard_marks_pooled_campaigns():
    """The AQS heat card was marked in D-135; the per-KPI one never was."""
    recs = (kpi_scenario_records(3, kpi={"n1_rtt_p50_ms": 20, "n1_grade": "good"},
                                 campaign_id="base")
            + kpi_scenario_records(3, kpi={"n1_rtt_p50_ms": 90, "n1_grade": "good"},
                                   campaign_id="opt"))
    c = rpt.kpi_heat_cells(recs, "n1_rtt_p50_ms")[0]
    assert c["mixed_campaigns"] == ["base", "opt"]
    assert "MIXED_CAMPAIGN:base/opt" in rpt.render_kpi_heatcard_markdown([c], "n1_rtt_p50_ms")


def test_non_finite_values_are_not_measurements():
    """The json module accepts bare NaN/Infinity though JSON forbids them. One
    NaN does not merely spoil its own cell — it poisons the sort, so the median
    of every other value in the cell becomes NaN too (D-148)."""
    assert cc.fnum(float("nan")) is None
    assert cc.fnum(float("inf")) is None
    assert cc.fnum(float("-inf")) is None
    assert cc.median([10.0, 20.0, float("nan"), 40.0, 50.0]) == 30.0
    assert cc.mean([10.0, float("inf"), 20.0]) == 15.0
    assert cc.stdev([5.0, float("nan")]) is None      # one usable sample -> unknown
    assert cc.mad([5.0, float("nan")]) is None


def test_modal_and_ranked_are_deterministic():
    from collections import Counter
    assert cc.modal(Counter({"b": 3, "a": 3})) == (None, ["a", "b"])
    assert cc.modal(Counter({"b": 3, "a": 1})) == ("b", [])
    assert cc.modal(Counter()) == (None, [])
    # ties in a display list order by key, never by insertion
    assert cc.ranked(Counter({"z": 2, "a": 2, "m": 5})) == [("m", 5), ("a", 2), ("z", 2)]


def test_surrounding_whitespace_in_a_label_does_not_split_a_cell():
    """A hand-typed label with a stray space is invisible in every rendering,
    yet it split one point into two cells with half the samples each — both
    flagged low_conf, and the coverage matrix reporting the planned cell as
    never measured (D-149)."""
    recs = (aqs_records(80, 3, point="SZ-CBD-01")
            + aqs_records(80, 3, point="SZ-CBD-01 ")
            + aqs_records(80, 3, point=" SZ-CBD-01"))
    cells = rpt.heat_cells(recs)
    assert len(cells) == 1
    assert cells[0]["cell"]["point_id"] == "SZ-CBD-01"
    assert cells[0]["n"] == 9
    assert cells[0]["low_confidence"] is False
    # an all-whitespace label is not a label
    assert cc.campaign_labels({"run": {"campaign": {"point_id": "   "}}})["point_id"] \
        == "unlabeled"


def test_lookalike_labels_are_reported_not_merged():
    """Case and full-width digits COULD be meaningful, so merging them would be
    a judgement the tool is not entitled to make — it says so instead."""
    recs = (aqs_records(80, 3, point="SZ-CBD-01")
            + aqs_records(80, 3, point="sz-cbd-01")
            + aqs_records(80, 3, point="SZ-CBD-\uff101"))     # full-width zero
    assert len(rpt.heat_cells(recs)) == 3                     # not merged
    coll = rpt.inventory(recs)["label_collisions"]
    assert list(coll) == ["point_id"]
    assert sorted(v for vs in coll["point_id"].values() for v in vs) == [
        "SZ-CBD-01", "SZ-CBD-\uff101", "sz-cbd-01"]
    md = rpt.build_report_markdown(recs)
    assert "同名异写" in md
    assert "这不是自动合并的" in md
    # and a corpus with distinct labels must stay quiet
    clean = aqs_records(80, 3, point="P1") + aqs_records(80, 3, point="P2")
    assert not rpt.inventory(clean)["label_collisions"]
    assert "同名异写" not in rpt.build_report_markdown(clean)


def test_summary_signal_count_is_the_same_for_every_corpus_shape():
    """Every other signal says something even with no data ("无 transport 证据
    （覆盖缺口）"). The did-it-improve one used to vanish on a single-round
    corpus, so a reader could not tell that shape from a dropped signal — and
    the deliverable skeleton takes its opening section from this list (D-152)."""
    import synth_campaign as sc
    shapes = {
        "single": sc.generate(points=2, repeats=2, campaigns=("base",),
                              carriers=("cmcc",), time_bands=("busy",), tiers=("metro",)),
        "two": sc.generate(points=2, repeats=2, campaigns=("base", "opt"),
                           carriers=("cmcc",), time_bands=("busy",), tiers=("metro",)),
        "three": sc.generate(points=2, repeats=2, campaigns=("base", "opt", "r3"),
                             carriers=("cmcc",), time_bands=("busy",), tiers=("metro",)),
    }
    counts = {}
    for name, recs in shapes.items():
        summary = rpt.render_summary_markdown(recs)
        counts[name] = sum(1 for ln in summary.splitlines() if ln.startswith("- **"))
    assert len(set(counts.values())) == 1, counts
    single = rpt.render_summary_markdown(shapes["single"])
    assert "无法回答" in single                      # says so, rather than going quiet
    # an unlabelled corpus still gets the signal, pointing at the fix
    plain = rpt.render_summary_markdown([make_record(aqs=80, scenarios=[]) for _ in range(3)])
    assert "先补注" in plain


def _inferred_band_records(n=6):
    import annotate_campaign as ann
    recs = [make_record(campaign={"campaign_id": "base", "point_id": "P1",
                                  "carrier": "cmcc", "tier": "metro"},
                        aqs=80, scenarios=[], started_ms=1783944000000 + i * 3600000)
            for i in range(n)]
    out, _ = ann.annotate(recs, infer_tb=True)
    return out


def test_report_says_when_a_grouping_label_was_inferred():
    """label_source was written by annotate_campaign and read by nothing, so the
    report could not tell a time_band recorded on site from one a rule of thumb
    guessed — while still reporting "busy is N points worse than idle" (D-153)."""
    md = rpt.build_report_markdown(_inferred_band_records())
    assert "标签来源 label_source" in md
    assert "工具推断的" in md
    assert "忙闲差异的结论" in md
    # a declared corpus stays quiet
    plain = rpt.build_report_markdown(aqs_records(80, 6))
    assert "标签来源 label_source" in plain          # the line is always there
    assert "工具推断的" not in plain                 # the warning is not


def _veto_corpus(n=6, capped=4, aqs=54):
    from synth import contractify
    recs = [contractify(r) for r in aqs_records(aqs, n, point="P1")]
    for r in recs[:capped]:
        r["run"]["aqs"]["veto_applied"] = True
    return recs


def test_veto_capped_runs_are_visible_in_the_heat_card():
    """A veto caps the score at 70/54 — the grade-band edges — so a low grade
    can mean the sessions failed rather than the network being slow. Only
    dashboard.py ever read the flag; the campaign layer showed the number
    without the reason (D-154)."""
    recs = _veto_corpus()
    c = rpt.heat_cells(recs)[0]
    assert c["veto_n"] == 4 and c["n"] == 6
    md = rpt.render_heatcard_markdown([c])
    assert "**VETO_CAPPED:4/6**" in md
    assert "T4 严重卡顿率" in md                  # the caveat names the real cause
    assert "至少这么差" in md                     # and what a capped score does mean
    # S1 session-success veto lives in run.aqs_token and this layer never reads it,
    # so the report must say it is unobservable rather than imply it was ruled out
    assert "无法观测" in md
    # and a clean corpus stays quiet
    clean = rpt.heat_cells(aqs_records(54, 6, point="P1"))
    assert clean[0]["veto_n"] == 0
    assert "VETO_CAPPED" not in rpt.render_heatcard_markdown(clean)


def test_veto_reaches_summary_html_and_csv():
    import csv as csvmod
    import os
    import tempfile
    recs = _veto_corpus()
    md = rpt.build_report_markdown(recs)
    html = rpt.build_report_html(recs, "2026-01-01 00:00:00")
    assert "被否决封顶" in md                      # summary bullet
    assert "封顶4" in html                         # pivot cell marker
    # …and the marker needs a legend on the same page. The explanation lived in
    # the markdown branch only, so an HTML reader saw '⚠封顶4' with nothing
    # beside the card saying a capped score means "at least this bad" (D-160).
    # NB: a bare `"T4 严重卡顿率" in html` is vacuous — the summary bullet already
    # carries that phrase through the md->html conversion, so it passed before
    # the legend existed. Count instead: summary + card legend = 2.
    assert html.count("至少这么差") == 2
    # unique to the card legend: the summary never mentions the S1 veto, which
    # this layer cannot observe at all (must not read as "ruled out")
    assert "无法观测" in html
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "camp")
        rpt.write_csv_tables(recs, prefix)
        with open(prefix + "_heat.csv", encoding="utf-8-sig") as f:
            rows = list(csvmod.DictReader(f))
    assert rows[0]["veto_n"] == "4"
    assert rows[0]["scorer_low_conf_n"] == "0"


def test_scorer_low_confidence_is_separate_from_sample_count():
    """The scorer's own low-confidence flag (rounds < 3) is a different thing
    from n < min_samples, so they must not collapse into one note."""
    from synth import contractify
    recs = [contractify(r) for r in aqs_records(80, 6, point="P1")]
    for r in recs[:2]:
        r["run"]["aqs"]["low_confidence"] = True
    c = rpt.heat_cells(recs)[0]
    assert c["scorer_low_conf_n"] == 2
    assert c["low_confidence"] is False            # n=6 >= min_samples
    md = rpt.render_heatcard_markdown([c])
    assert "SCORER_LOW_CONF:2/6" in md
    assert "low_conf;" not in md and not md.rstrip().endswith("low_conf |")


def _every_marker_corpus():
    """One cell that trips every per-cell incomparability flag at once."""
    from synth import contractify
    HOUR = 3600_000
    out = []
    for camp in ("base", "opt"):
        for tier, val, off, tp in (("metro", 20, 0, "wifi"),
                                   ("regional", 35, 600_000, "wifi"),
                                   ("core", 90, 9 * HOUR, "auto(cellular)")):
            c = {"campaign_id": camp, "tier": tier, "point_id": "P1",
                 "carrier": "cmcc", "time_band": "busy"}
            for i in range(5):
                r = make_record(campaign=c, aqs=60,
                                scenarios=[("s1_chat", {"n1_rtt_p50_ms": val})],
                                started_ms=1783944000000 + off + i * 60_000)
                r["run"]["transport"] = tp
                out.append(contractify(r))
    return out


def test_every_attribution_marker_reaches_all_three_surfaces():
    """The renderers used to build three separate marker lists, which is how
    MIXED_TRANSPORT (D-157) and the tier-time markers (D-155) shipped in
    markdown only while the HTML deliverable printed a bare em-dash (D-160).
    They now share attribution.incomparability_flags — this pins that."""
    import csv as csvmod
    import os
    import tempfile
    import attribution
    recs = _every_marker_corpus()
    attr = attribution.attribute(recs)
    flags = attribution.incomparability_flags(attr["cells"][0])
    tags = sorted({f.split(":")[0] for f in flags})
    assert {"TIER_TIME_SPREAD", "MIXED_TRANSPORT", "MIXED_CAMPAIGN"} <= set(tags), tags

    md = rpt.build_report_markdown(recs)
    html = rpt.build_report_html(recs, "2026-01-01 00:00:00")
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "camp")
        rpt.write_csv_tables(recs, prefix)
        with open(prefix + "_attribution.csv", encoding="utf-8-sig") as f:
            rows = list(csvmod.DictReader(f))
    csv_flags = " ".join(r["incomparability"] for r in rows)
    for tag in tags:
        assert tag in md, f"{tag} missing from markdown"
        assert tag in html, f"{tag} missing from HTML"
        assert tag in csv_flags, f"{tag} missing from CSV incomparability column"
    # the numeric spread is filterable, not just embedded in a string
    assert any(r["tier_time_spread_ms"] for r in rows)


def test_attribution_premise_checklist_reaches_html():
    """The HTML path rebuilds only the table, so everything markdown puts above
    it was absent from the sendable deliverable (D-160)."""
    import attribution
    recs = _every_marker_corpus()
    md = rpt.build_report_markdown(recs)
    html = rpt.build_report_html(recs, "2026-01-01 00:00:00")
    for note in attribution.premise_notes(attribution.attribute(recs)):
        probe = note.replace("**", "").replace("`", "")[:12]
        assert probe in md.replace("**", "").replace("`", ""), probe
        assert probe in html.replace("<b>", "").replace("</b>", "").replace(
            "<code>", "").replace("</code>", ""), f"{probe} missing from HTML"


DAY_MS = 86_400_000


def _two_rounds(before_id, after_id, before_vals, after_vals, gap_days=3, stamped=True):
    base = 1783944000000
    recs = []
    for v in before_vals:
        recs += aqs_records(v, 1, point="P1", campaign_id=before_id, started_ms=base)
    for v in after_vals:
        recs += aqs_records(v, 1, point="P1", campaign_id=after_id,
                            started_ms=base + gap_days * DAY_MS)
    if not stamped:
        for r in recs:
            r["run"].pop("started_at_epoch_ms", None)
    return recs


def test_before_after_pairs_by_time_not_by_name():
    """`pre-*` sorts after `post-*`, so name ordering inverted the sign of every
    delta on all three surfaces — a 30-point improvement published as 回退 with
    AQS 中位Δ -30 (D-161). trend.py has ordered chronologically all along."""
    recs = _two_rounds("pre-qos", "post-qos", [50, 51, 52, 50, 51], [80, 81, 82, 80, 81])
    inv = rpt.inventory(recs)
    assert rpt.compare_basis(inv) == "time"
    assert rpt.auto_compare_ids(inv) == ("pre-qos", "post-qos")
    r = rpt.compare_campaigns(recs, *rpt.auto_compare_ids(inv))["rows"][0]
    assert r["delta"] > 0                       # an improvement reads as one
    line = [l for l in rpt.build_report_markdown(recs).splitlines()
            if l.startswith("- **优化前后**")][0]
    assert "pre-qos → post-qos" in line
    assert "回退 0" in line


def test_unordered_campaigns_refuse_to_guess():
    """No timestamps means the order is unknowable; falling back to name sort is
    exactly what produced the inversion. Say so instead (R-10)."""
    recs = _two_rounds("pre-qos", "post-qos", [50, 51, 52], [80, 81, 82], stamped=False)
    inv = rpt.inventory(recs)
    assert rpt.compare_basis(inv) == "no_timestamps"
    assert rpt.auto_compare_ids(inv) == (None, None)
    line = [l for l in rpt.build_report_markdown(recs).splitlines()
            if l.startswith("- **优化前后**")][0]
    assert "无法确定先后" in line
    assert "不按名称猜" in line


def test_summary_signal_survives_the_unordered_case():
    """The signal count must not change with corpus shape (D-152)."""
    import synth_campaign as sc
    shaped = sc.generate(points=2, repeats=2, campaigns=("base",), carriers=("cmcc",),
                         time_bands=("busy",), tiers=("metro",))
    unordered = _two_rounds("pre-qos", "post-qos", [50, 51, 52], [80, 81, 82],
                            stamped=False)
    n = lambda recs: sum(1 for ln in rpt.render_summary_markdown(recs).splitlines()
                         if ln.startswith("- **"))
    assert n(shaped) == n(unordered)


def _tiered(point, tier_name, aqs, n=5):
    campaign = {"campaign_id": "base", "tier": tier_name, "point_id": point,
                "carrier": "cmcc", "time_band": "busy"}
    return [make_record(campaign=campaign, aqs=aqs, scenarios=[]) for _ in range(n)]


def test_missing_tier_does_not_silently_improve_a_point():
    """The heat card pools whatever tiers a cell measured. A point that never
    got its `core` round is missing its worst tier, so its median rises and it
    ranks best while being identical to the others on every tier it did
    measure — 81.0 vs 74, unmarked (D-165)."""
    recs = []
    for p in ("P1", "P2", "P3"):
        recs += _tiered(p, "metro", 88) + _tiered(p, "regional", 74)
        if p != "P3":
            recs += _tiered(p, "core", 52)
    by = {c["cell"]["point_id"]: c for c in rpt.heat_cells(recs)}
    assert by["P3"]["aqs_median"] > by["P1"]["aqs_median"]   # the artefact itself
    assert by["P3"]["missing_tiers"] == ["core"]
    assert by["P1"]["missing_tiers"] == []
    md = rpt.render_heatcard_markdown(rpt.heat_cells(recs))
    assert "**TIER_INCOMPLETE:缺core**" in md
    assert "与别的格不可比" in md


def test_uniform_tier_coverage_is_not_flagged():
    """Every cell pooling all three tiers is the normal case — flagging it would
    be crying wolf (D-134)."""
    recs = (_tiered("P1", "metro", 88) + _tiered("P1", "regional", 74)
            + _tiered("P1", "core", 52))
    c = rpt.heat_cells(recs)[0]
    assert c["missing_tiers"] == []
    assert sorted(c["tier_mix"]) == ["core", "metro", "regional"]
    assert "TIER_INCOMPLETE" not in rpt.render_heatcard_markdown(rpt.heat_cells(recs))


def test_tier_composition_reaches_html_and_csv():
    import csv as csvmod
    import os
    import tempfile
    from synth import contractify
    recs = []
    for p in ("P1", "P2"):
        recs += _tiered(p, "metro", 88) + _tiered(p, "regional", 74)
        if p != "P2":
            recs += _tiered(p, "core", 52)
    recs = [contractify(r) for r in recs]
    html = rpt.build_report_html(recs, "2026-01-01 00:00:00")
    assert "⚠缺core" in html
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "camp")
        rpt.write_csv_tables(recs, prefix)
        with open(prefix + "_heat.csv", encoding="utf-8-sig") as f:
            rows = {r["point_id"]: r for r in csvmod.DictReader(f)}
    assert rows["P2"]["missing_tiers"] == "core"
    assert rows["P1"]["missing_tiers"] == ""
    assert "metro5" in rows["P1"]["tier_mix"]


def _mixed_tiers_corpus():
    """One cell pooling wifi with cellular and quick with forensic."""
    from synth import contractify
    out = []
    for tier_name, val, tp in (("metro", 20, "wifi"), ("regional", 35, "wifi"),
                               ("core", 90, "auto(cellular)")):
        c = {"campaign_id": "base", "tier": tier_name, "point_id": "P1",
             "carrier": "cmcc", "time_band": "busy"}
        for _ in range(5):
            r = make_record(campaign=c, aqs=70,
                            scenarios=[("s1_chat", {"n1_rtt_p50_ms": val})])
            r["run"]["transport"] = tp
            r["run"]["mode"] = "forensic" if tp == "wifi" else "quick"
            out.append(contractify(r))
    return out


def test_heat_card_and_attribution_agree_about_the_same_cell():
    """The heat card pooled wifi with cellular and quick with forensic while the
    attribution matrix flagged the very same cell — one report, two answers
    about one cell (D-166)."""
    import attribution
    recs = _mixed_tiers_corpus()
    attr_flags = attribution.incomparability_flags(
        attribution.attribute(recs)["cells"][0])
    heat_flags = attribution.incomparability_flags(rpt.heat_cells(recs)[0])
    assert "MIXED_TRANSPORT:cellular/wifi" in attr_flags
    assert heat_flags == attr_flags
    md = rpt.render_heatcard_markdown(rpt.heat_cells(recs))
    assert "**MIXED_TRANSPORT:cellular/wifi**" in md
    assert "MIXED_MODE:forensic/quick" in md


def test_heat_incomparability_reaches_csv():
    import csv as csvmod
    import os
    import tempfile
    recs = _mixed_tiers_corpus()
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "camp")
        rpt.write_csv_tables(recs, prefix)
        with open(prefix + "_heat.csv", encoding="utf-8-sig") as f:
            rows = list(csvmod.DictReader(f))
    assert "MIXED_TRANSPORT" in rows[0]["incomparability"]
    assert "MIXED_MODE" in rows[0]["incomparability"]


def test_homogeneous_heat_cell_carries_no_markers():
    """Crying wolf on the normal case is the failure mode to avoid (D-134)."""
    import attribution
    assert attribution.incomparability_flags(
        rpt.heat_cells(aqs_records(90, 6, point="P1"))[0]) == []


def test_two_cells_with_the_same_median_are_distinguishable():
    """A median with no spread hides a bimodal cell: sd=0 (every run 60) and
    sd=36 (runs from 20 to 95) rendered as 60 and 59 side by side, identical to
    the reader. stdev was computed for the noise scale and rendered nowhere
    (D-168)."""
    import csv as csvmod
    import os
    import tempfile
    from synth import contractify
    recs = aqs_records(60, 8, point="P2")
    for v in (20, 95, 25, 90, 30, 88, 22, 92):
        recs += aqs_records(v, 1, point="P3")
    recs = [contractify(r) for r in recs]
    by = {c["cell"]["point_id"]: c for c in rpt.heat_cells(recs)}
    assert by["P2"]["stdev"] == 0.0 and by["P3"]["stdev"] > 30
    md = rpt.render_heatcard_markdown(rpt.heat_cells(recs))
    assert "离散(sd)" in md
    p2 = [ln for ln in md.splitlines() if ln.startswith("| P2 ")][0]
    p3 = [ln for ln in md.splitlines() if ln.startswith("| P3 ")][0]
    assert "| 0 |" in p2 and "| 36 |" in p3
    html = rpt.build_report_html(recs, "2026-01-01 00:00:00")
    assert "sd=36" in html
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "camp")
        rpt.write_csv_tables(recs, prefix)
        with open(prefix + "_heat.csv", encoding="utf-8-sig") as f:
            rows = {r["point_id"]: r for r in csvmod.DictReader(f)}
    assert float(rows["P2"]["stdev"]) == 0.0
    assert float(rows["P3"]["stdev"]) > 30


def test_single_sample_cell_is_marked_where_it_is_named():
    """An n=1 cell headed the list of the city's worst points with nothing
    saying so — the heat card flagged it, the summary did not (D-168)."""
    recs = aqs_records(30, 1, point="P1") + aqs_records(60, 8, point="P2")
    line = [ln for ln in rpt.render_summary_markdown(recs).splitlines()
            if "体验最差格" in ln][0]
    assert "P1/cmcc/busy(30，n=1 low_conf)" in line
    assert "P2/cmcc/busy(60)" in line          # a well-sampled cell stays clean


def test_unknown_spread_is_not_rendered_as_zero():
    """<2 samples means the spread is unknown, not 0 (R-10)."""
    c = rpt.heat_cells(aqs_records(30, 1, point="P1"))[0]
    assert c["stdev"] is None
    row = [ln for ln in rpt.render_heatcard_markdown([c]).splitlines()
           if ln.startswith("| P1 ")][0]
    assert "| — |" in row


def _two_rounds_vals(before_vals, after_vals):
    base = 1783944000000
    recs = [r for v in before_vals
            for r in aqs_records(v, 1, point="P1", campaign_id="r1", started_ms=base)]
    recs += [r for v in after_vals
             for r in aqs_records(v, 1, point="P1", campaign_id="r2",
                                  started_ms=base + DAY_MS)]
    return recs


def test_zero_delta_is_never_a_change():
    """`abs(0) < 0` is False, so a zero delta on flat repeats was counted as
    "beyond noise" — a non-change published as a real one (D-169)."""
    r = rpt.compare_campaigns(_two_rounds_vals([60] * 5, [60] * 5), "r1", "r2")["rows"][0]
    assert r["delta"] == 0
    assert r["within_noise"] is True


def test_zero_observed_spread_bounds_nothing():
    """Identical repeats mean this sample saw no variation, not that the
    measurement has none — D-144's own caveat says so. A 1-point delta on flat
    repeats used to publish as a confirmed improvement."""
    r = rpt.compare_campaigns(_two_rounds_vals([60] * 5, [61] * 5), "r1", "r2")["rows"][0]
    assert r["noise"] == 0.0
    assert r["within_noise"] is None          # not False
    line = [ln for ln in rpt.render_summary_markdown(
        _two_rounds_vals([60] * 5, [61] * 5)).splitlines() if "优化前后" in ln][0]
    assert "0 个 Δ 超出噪声" in line
    assert "复测零离散" in line               # names why it could not be judged


def test_real_spread_still_classifies_both_ways():
    small = rpt.compare_campaigns(
        _two_rounds_vals([58, 59, 60, 61, 62], [59, 60, 61, 62, 63]), "r1", "r2")["rows"][0]
    assert small["within_noise"] is True       # 1 point inside the noise
    big = rpt.compare_campaigns(
        _two_rounds_vals([58, 59, 60, 61, 62], [108, 109, 110, 111, 112]),
        "r1", "r2")["rows"][0]
    assert big["within_noise"] is False        # 50 points beyond it
