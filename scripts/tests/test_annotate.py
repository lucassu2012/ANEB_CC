# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/annotate_campaign.py."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import annotate_campaign as ann
import campaign_report as rpt
from synth import make_record


def _rec(run_id="r1", epoch=1783944000000, campaign=None):
    r = make_record(aqs=90, scenarios=[])
    r["run"]["run_id"] = run_id
    r["run"]["started_at_epoch_ms"] = epoch
    if campaign is not None:
        r["run"]["campaign"] = campaign
    else:
        r["run"].pop("campaign", None)
    return r


def test_uniform_set_applied():
    out, changed = ann.annotate([_rec()], uniform={"point_id": "P1", "tier": "metro"})
    assert changed == 1
    camp = out[0]["run"]["campaign"]
    assert camp["point_id"] == "P1"
    assert camp["tier"] == "metro"
    assert "set" in camp["label_source"]


def test_infer_time_band_busy_and_idle():
    # local hour = (epoch_ms//1000//3600 + tz) % 24; tz=8
    busy_epoch = 2 * 3600 * 1000      # -> hour 10 busy
    idle_epoch = 19 * 3600 * 1000     # -> hour 3 idle
    assert ann.infer_time_band(busy_epoch) == "busy"
    assert ann.infer_time_band(idle_epoch) == "idle"
    assert ann.infer_time_band(None) is None
    out, _ = ann.annotate([_rec(epoch=busy_epoch)], infer_tb=True)
    assert out[0]["run"]["campaign"]["time_band"] == "busy"
    assert "inferred:time_band" in out[0]["run"]["campaign"]["label_source"]


def test_existing_label_not_overwritten():
    r = _rec(campaign={"tier": "core", "campaign_id": "orig"})
    out, _ = ann.annotate([r], uniform={"tier": "metro", "point_id": "P9"})
    camp = out[0]["run"]["campaign"]
    assert camp["tier"] == "core"      # original wins, not clobbered
    assert camp["point_id"] == "P9"    # gap filled


def test_map_per_run_only_matching():
    recs = [_rec(run_id="a"), _rec(run_id="b")]
    mapping = {"a": {"point_id": "PA", "tier": "metro"}}
    out, changed = ann.annotate(recs, mapping=mapping)
    assert out[0]["run"]["campaign"]["point_id"] == "PA"
    assert changed == 1
    assert not out[1]["run"].get("campaign")  # 'b' untouched


def test_map_precedence_over_set():
    recs = [_rec(run_id="a")]
    out, _ = ann.annotate(recs, uniform={"point_id": "SET"},
                          mapping={"a": {"point_id": "MAP"}})
    assert out[0]["run"]["campaign"]["point_id"] == "MAP"  # map applied before set


def test_non_destructive_preserves_input_and_fields():
    src = _rec(campaign={"tier": "metro"})
    src["scenarios"] = [{"profile_id": "s1", "kpi": {"n1_rtt_p50_ms": 5}}]
    before = str(src)
    out, _ = ann.annotate([src], uniform={"point_id": "P1"})
    assert str(src) == before                            # input object unchanged
    assert out[0]["scenarios"][0]["profile_id"] == "s1"  # other fields preserved
    assert out[0]["run"]["campaign"]["tier"] == "metro"


def test_annotated_record_flows_into_heatcard():
    out, _ = ann.annotate([_rec()], uniform={"point_id": "P1", "carrier": "cmcc",
                                             "time_band": "busy", "tier": "metro"})
    cells = rpt.heat_cells(out)
    assert len(cells) == 1
    assert cells[0]["cell"] == {"point_id": "P1", "carrier": "cmcc", "time_band": "busy"}


def test_no_labels_no_change():
    out, changed = ann.annotate([_rec()])  # no uniform/map/infer
    assert changed == 0
    assert not out[0]["run"].get("campaign")


def test_inferred_time_band_records_the_offset_it_used():
    """time_band is a heat-card dimension, and two operators running with
    different --tz-offset produce differently labelled corpora. The rule has to
    travel with the data (D-153)."""
    from synth import make_record
    recs = [make_record(campaign={"campaign_id": "base", "point_id": "P1",
                                  "carrier": "cmcc", "tier": "metro"},
                        aqs=80, scenarios=[], started_ms=1783944000000)]
    out, _ = ann.annotate([dict(r) for r in recs], infer_tb=True)
    assert "inferred:time_band(tz=+8)" in out[0]["run"]["campaign"]["label_source"]
    out2, _ = ann.annotate([dict(r) for r in recs], infer_tb=True, tz_offset_h=-5)
    assert "inferred:time_band(tz=-5)" in out2[0]["run"]["campaign"]["label_source"]
    # and the two offsets really can disagree about the band
    assert (out[0]["run"]["campaign"]["time_band"]
            != out2[0]["run"]["campaign"]["time_band"])
