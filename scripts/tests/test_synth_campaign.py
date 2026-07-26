# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/synth_campaign.py + the synthetic-data guard.

Two things must hold, and the second one is a safety property:
  1. the generated corpus is contract-complete (it has to survive the report
     front door, or it is useless as rehearsal fuel);
  2. synthetic records are ALWAYS detectable and the report ALWAYS says so —
     fabricated numbers must never be presentable as field measurements.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import campaign_common as cc
import campaign_report as rpt
import synth_campaign as sc
import validate_results as vr
from synth import aqs_records

SMALL = dict(points=2, carriers=("cmcc",), time_bands=("busy", "idle"),
             tiers=("metro", "core"), repeats=2, campaigns=("base",))


def test_generated_corpus_passes_the_contract_gate():
    """The whole point: this corpus must survive validate_results / the report
    front door, exactly like real field data would."""
    recs = sc.generate(**SMALL)
    errors, _warnings = vr.validate_records(recs, vr.load_schema(vr.DEFAULT_SCHEMA))
    assert errors == [], errors[:5]
    assert rpt.contract_gate(recs) == []


def test_deterministic_for_a_given_seed():
    assert sc.generate(seed=7, **SMALL) == sc.generate(seed=7, **SMALL)


def test_different_seed_changes_the_corpus():
    assert sc.generate(seed=7, **SMALL) != sc.generate(seed=8, **SMALL)


def test_every_record_carries_both_markers():
    for r in sc.generate(**SMALL):
        assert isinstance(r["synthetic"], dict)                          # marker 1
        assert r["run"]["campaign"]["campaign_id"].startswith("SYNTH-")  # marker 2
        assert cc.is_synthetic(r) is True


def test_marker_survives_losing_either_half():
    """A corpus stripped of the additive block, or re-labelled away from the
    SYNTH- prefix, must STILL be detected by the remaining marker."""
    rec = sc.generate(**SMALL)[0]
    stripped = {k: v for k, v in rec.items() if k != "synthetic"}
    assert cc.is_synthetic(stripped) is True          # campaign_id prefix remains
    relabelled = dict(rec)
    relabelled["run"] = dict(rec["run"])
    relabelled["run"]["campaign"] = dict(rec["run"]["campaign"],
                                         campaign_id="sz-2026Q3-baseline")
    assert cc.is_synthetic(relabelled) is True        # additive block remains


def test_real_records_are_not_flagged():
    assert cc.count_synthetic(aqs_records(90, 3)) == 0
    assert cc.is_synthetic(aqs_records(90, 1)[0]) is False


def test_report_markdown_carries_the_banner_before_any_claim():
    md = rpt.build_report_markdown(sc.generate(**SMALL))
    assert "合成数据警告" in md
    assert "不得" in md
    # banner precedes the claim_scope line and every data section
    assert md.index("合成数据警告") < md.index("claim_scope")
    assert md.index("合成数据警告") < md.index("## 覆盖盘点")


def test_report_html_carries_the_banner():
    html = rpt.build_report_html(sc.generate(**SMALL), "2026-07-25 00:00:00 +0800")
    assert "合成数据警告" in html
    assert "class='synth'" in html


def test_real_corpus_report_has_no_banner():
    """The guard must not cry wolf on real data — that would train people to
    ignore it."""
    assert "合成数据警告" not in rpt.build_report_markdown(aqs_records(90, 5))


def test_grid_covers_every_requested_cell():
    recs = sc.generate(**SMALL)
    cells = {(r["run"]["campaign"]["point_id"], r["run"]["campaign"]["carrier"],
              r["run"]["campaign"]["time_band"], r["run"]["campaign"]["tier"])
             for r in recs}
    assert len(cells) == 2 * 1 * 2 * 2          # points x carriers x bands x tiers
    assert len(recs) == 2 * 1 * 2 * 2 * 2       # x repeats


def test_invalid_scenarios_null_both_value_and_grade():
    """R-10 pairing: an invalid scenario carries no KPI value AND no grade."""
    seen_invalid = False
    for r in sc.generate(points=4, repeats=4, campaigns=("base",)):
        for s in r["scenarios"]:
            if s["validity"] != "invalid":
                continue
            seen_invalid = True
            for k in sc.GRADED:
                assert s["kpi"][k] is None
                assert s["kpi"][k.split("_")[0] + "_grade"] is None
    assert seen_invalid, "fixture should contain invalid scenarios to exercise this"


def test_rehearsal_can_demonstrate_both_verdicts():
    """A rehearsal whose every verdict is negative cannot tell a working
    improvement-detection path from a silent one — the vacuous-test trap wearing
    a corpus. At the runbook's default grid ALL 32 comparable cells used to land
    inside the noise (designed effect ~3 AQS against a ~6 noise scale), so the
    corpus now carries ONE optimisation big enough to clear it (D-182)."""
    recs = sc.generate()
    inv = rpt.inventory(recs)
    before, after = rpt.auto_compare_ids(inv)
    rows = rpt.compare_campaigns(recs, before, after)["rows"]
    real = [r for r in rows if r["within_noise"] is False]
    noisy = [r for r in rows if r["within_noise"] is True]
    # both paths demonstrable in one rehearsal, which is the whole point
    assert real, "rehearsal must be able to show a detected improvement"
    assert noisy, "…and must still show sub-noise deltas as sub-noise"
    designed = f"SYNTH-P{sc.OPTIMISED_POINT_INDEX + 1:02d}"
    assert {r["cell"]["point_id"] for r in real} == {designed}
    assert all(r["delta"] > 0 for r in real)        # an improvement, not a regression
    # the expected answers are written down where a rehearsing operator reads them
    keys = [k for k, _ in sc.DESIGNED_EFFECTS]
    assert "real_improvement" in keys and "sub_noise_improvement" in keys
    # …and the summary NAMES the improved cells. Every other signal names its
    # examples; this one gave counts only, so the reader learned four cells got
    # better but not which — the question the round exists to answer (D-182).
    line = [ln for ln in rpt.render_summary_markdown(recs).splitlines()
            if ln.startswith("- **优化前后")][0]
    assert designed in line
    assert "±" in line              # named with its noise scale, never bare


def test_tier_ordering_is_realistic():
    """metro < regional < core on RTT — otherwise the attribution matrix
    rehearsal would be meaningless."""
    recs = sc.generate(points=3, repeats=6, campaigns=("base",),
                       carriers=("cmcc",), time_bands=("busy",))
    by_tier = {}
    for r in recs:
        vals = [s["kpi"]["n1_rtt_p50_ms"] for s in r["scenarios"]
                if s["kpi"]["n1_rtt_p50_ms"] is not None]
        by_tier.setdefault(r["run"]["campaign"]["tier"], []).extend(vals)
    med = {t: sorted(v)[len(v) // 2] for t, v in by_tier.items()}
    assert med["metro"] < med["regional"] < med["core"]
