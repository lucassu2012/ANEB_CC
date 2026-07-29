# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/radio_rollup.py (D-284).

With the three-tier differential gone (D-48), radio context is the first
covariate the recorded fallback names. These pin the two things that make it
usable: the band rule must be the app's own, and absence must never read as
"signal was fine".
"""
import ast
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import campaign_common as cc
import radio_rollup as rr
import synth_campaign as sc

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BUFFERING_KT = os.path.join(
    _ROOT, "app", "probe", "src", "main", "java", "com", "aneb", "probe",
    "scoring", "BufferingDetector.kt")


def _rec(point="P1", carrier="cmcc", band="busy", radios=(), tier="metro"):
    """One run whose scenarios carry the given radio blocks (None = no block)."""
    scns = []
    for r in radios:
        ns = {"transport": "cellular", "capabilities": "INTERNET",
              "interface": "rmnet0", "server_observed_addr": "198.51.100.9:443"}
        if r is not None:
            ns["radio"] = r
        scns.append({"profile_id": "s1_chat", "validity": "valid",
                     "kpi": {"n1_rtt_p50_ms": 20.0}, "network_snapshot": ns})
    return {"run": {"campaign": {"point_id": point, "carrier": carrier,
                                 "time_band": band, "tier": tier}},
            "scenarios": scns}


def _radio(rsrp=-98, sinr=7, pci=238, rat="NR", n=12, stale=False):
    return {"rat": rat, "rsrp_dbm": rsrp, "sinr_db": sinr, "pci": pci,
            "tac": 12345, "arfcn": 504990, "sampled_n": n, "stale": stale}


# --------------------------------------------------------------- the band rule

def test_the_signal_bands_match_the_producer_that_defines_them():
    """The thresholds live in BufferingDetector.kt and are duplicated in this
    layer because spec/ has no home for radio constants — the wiring spec asks
    for that to change. Until it does, the duplication has to be reconciled
    against the producer, or one report says 弱 while another says 中 about the
    same reading and neither is wrong on its own terms."""
    assert os.path.exists(_BUFFERING_KT), (
        "%s is gone — either the producer moved, in which case this guard must "
        "follow it, or the band thresholds now come from somewhere unchecked"
        % _BUFFERING_KT)
    with io.open(_BUFFERING_KT, encoding="utf-8-sig") as fh:
        src = fh.read()
    ours = {"RSRP_WEAK_DBM": cc.RSRP_WEAK_DBM, "RSRP_GOOD_DBM": cc.RSRP_GOOD_DBM,
            "SINR_WEAK_DB": cc.SINR_WEAK_DB, "SINR_GOOD_DB": cc.SINR_GOOD_DB}
    for name, mine in sorted(ours.items()):
        m = re.search(r"const val %s\s*(?::\s*\w+)?\s*=\s*(-?[\d.]+)" % name, src)
        assert m, "BufferingDetector.kt no longer declares %s" % name
        assert float(m.group(1)) == mine, (
            "%s: producer says %s, this layer uses %s" % (name, m.group(1), mine))


def test_an_unknown_component_does_not_invent_a_band():
    """Mirrors the producer's asymmetry, which is easy to get backwards: an
    unknown component cannot make a cell weak, but it also must not block good —
    and both unknown is None, never 中. A band on a cell nobody measured would
    be read as a measurement."""
    assert cc.signal_band(None, None) is None
    assert cc.signal_band(-120, None) == "weak"        # known component crosses
    assert cc.signal_band(None, -3) == "weak"
    assert cc.signal_band(-90, None) == "good"         # unknown does not block
    assert cc.signal_band(None, 20) == "good"
    assert cc.signal_band(-90, 3) == "medium"          # known component fails good
    assert cc.signal_band(-100, 12) == "medium"


# ------------------------------------------------------- absence and exclusion

def test_a_corpus_without_radio_reports_a_gap_not_a_verdict():
    md = rr.render_markdown(rr.analyze([_rec(radios=[None, None])]))
    assert "采集缺口" in md and "信号良好" in md      # names the trap it avoids
    for verdict in ("弱", "中", "良"):
        assert "| %s |" % verdict not in md            # no band is asserted


def test_every_sample_stale_is_not_the_same_as_no_radio_block():
    """Two different findings: the producer never wrote radio, versus it wrote
    radio the collector had already marked out of date. The second points at a
    freshness window to fix; collapsing them hides that."""
    md = rr.render_markdown(rr.analyze([_rec(radios=[_radio(stale=True)] * 3)]))
    assert "stale" in md and "排除不等于没问题" in md
    assert "采集缺口" not in md


def test_an_unavailable_reading_is_not_pooled_as_a_strong_signal():
    """0 dBm is how "unavailable" reaches a JSON field, and it is 65 dB above any
    real reading — pooled, it would turn a weak cell into a good one."""
    cells, _ = rr.radio_cells([_rec(radios=[_radio(rsrp=0), _radio(rsrp=-112),
                                            _radio(rsrp=-110)])])
    c = cells[0]
    assert c["implausible_values"] == {"rsrp_dbm>-30": 1}
    assert c["rsrp_median_dbm"] == -111.0               # the 0 never entered
    assert c["band"] == "weak"


def test_a_stale_sample_is_excluded_and_counted():
    cells, _ = rr.radio_cells([_rec(radios=[_radio(rsrp=-60, stale=True),
                                            _radio(rsrp=-112), _radio(rsrp=-110)])])
    c = cells[0]
    assert c["stale_samples"] == 1
    assert c["rsrp_median_dbm"] == -111.0               # the stale -60 never entered
    assert c["band"] == "weak"


def test_a_cell_with_no_radio_evidence_is_named_in_a_corpus_that_has_some():
    """The whole-corpus gap notice cannot cover this: when other cells do carry
    radio, a cell that carries none is a hole in the middle of a table that
    otherwise reads as measured."""
    res = rr.analyze([_rec(point="P1", radios=[_radio()] * 5),
                      _rec(point="P2", radios=[None, None])])
    md = rr.render_markdown(res)
    assert "RADIO_ABSENT" in md
    p2 = [c for c in res["cells"] if c["cell"]["point_id"] == "P2"][0]
    assert p2["n_with_radio"] == 0 and p2["band"] is None


# ----------------------------------------------------------- the confounds

def test_a_cell_pooling_two_serving_cells_says_so():
    recs = [_rec(radios=[_radio(pci=1), _radio(pci=2)])]
    cells, _ = rr.radio_cells(recs)
    assert len(cells[0]["cell_keys"]) == 2
    assert "MIXED_SERVING_CELL" in rr.render_markdown(rr.analyze(recs))


def test_busy_and_idle_on_different_cells_is_flagged_like_a_tier_conflict():
    """With tiers gone this is one of two comparisons left, so a cell change
    underneath busy-vs-idle is exactly the confound TIER_ENDPOINT_CONFLICT
    catches: the difference is real, its cause is not what the column says."""
    res = rr.analyze([_rec(band="busy", radios=[_radio(pci=1)]),
                      _rec(band="idle", radios=[_radio(pci=2)])])
    assert len(res["places"]) == 1 and res["places"][0]["changed"] is True
    assert "CELL_CHANGED" in rr.render_markdown(res)


def test_a_place_measured_in_one_band_is_left_unasked_not_declared_comparable():
    """One band cannot agree or disagree with anything. Reporting it as 同一小区
    would be a guard answering a question nobody could ask (§2.2)."""
    res = rr.analyze([_rec(band="busy", radios=[_radio(pci=1)])])
    assert res["places"] == []
    assert "无从核对" in rr.render_markdown(res)


def test_a_partial_overlap_is_not_reported_as_agreement():
    res = rr.analyze([_rec(band="busy", radios=[_radio(pci=1), _radio(pci=2)]),
                      _rec(band="idle", radios=[_radio(pci=1)])])
    p = res["places"][0]
    assert p["changed"] is False and p["partial"] is True
    assert "CELL_PARTIAL" in rr.render_markdown(res)


def test_thinness_is_measured_per_scenario_not_by_a_cell_total():
    """A cell accumulates dozens of readings, so a sum-based floor could never
    fire — and a guard that cannot fire reads as a check that passed."""
    thin = rr.analyze([_rec(radios=[_radio(n=1)] * 8)])
    assert thin["cells"][0]["thin_samples"] is True
    assert "RADIO_THIN" in rr.render_markdown(thin)
    fat = rr.analyze([_rec(radios=[_radio(n=12)] * 8)])
    assert fat["cells"][0]["thin_samples"] is False    # both sides pinned
    assert "RADIO_THIN" not in rr.render_markdown(fat)


# --------------------------------------------------- every marker is exercised

def _markers_the_module_can_raise():
    """Marker names read OUT of radio_rollup's own source: the strings it appends
    to `notes` and the verdicts it assigns. Derived rather than typed here, so a
    marker added later is covered without anyone remembering to."""
    with io.open(rr.__file__, encoding="utf-8-sig") as fh:
        tree = ast.parse(fh.read())
    texts = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "append"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "notes"):
            texts += [n.value for n in ast.walk(node)
                      if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "verdict" for t in node.targets):
            texts += [n.value for n in ast.walk(node)
                      if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    found = set()
    for t in texts:
        found.update(re.findall(r"\b[A-Z][A-Z0-9_]{4,}\b", t))
    return found


def test_the_runbook_checklist_for_the_radio_rehearsal_is_true():
    """The runbook tells the operator what the radio rehearsal must show, and
    names the point that carries the cell-change confound. Nothing reconciled
    that: a promise about the tool, made on the page an operator reads before a
    field trip, in the document that changes least often (D-273's shape).

    Both the point name and the rehearsal's parameters are read OUT of the
    runbook, so editing either side is caught rather than only the code side.
    """
    docs = os.path.join(_ROOT, "docs")
    with io.open(os.path.join(docs, "M2_CAMPAIGN_RUNBOOK.md"),
                 encoding="utf-8-sig") as fh:
        book = fh.read()

    cmd = [ln for ln in book.split("\n")
           if ln.startswith("python synth_campaign.py") and "--radio" in ln]
    assert len(cmd) == 1, ("expected one radio rehearsal command in the "
                           "runbook, found %d" % len(cmd))
    tiers = re.search(r"--tiers\s+(\S+)", cmd[0]).group(1).split(",")
    campaigns = re.search(r"--campaigns\s+(\S+)", cmd[0]).group(1).split(",")

    named = re.findall(r"`?(SYNTH-P\d+)`?\*{0,2}\s*被标\s*\*{0,2}`?CELL_CHANGED",
                       book)
    assert len(named) == 1, ("the checklist no longer names exactly one point "
                             "for CELL_CHANGED: %r" % named)

    md = rr.render_markdown(rr.analyze(sc.generate(
        points=8, repeats=5, tiers=tuple(tiers), campaigns=tuple(campaigns),
        radio=True)))
    rows = [ln for ln in md.split("\n")
            if named[0] in ln and "CELL_CHANGED" in ln]
    assert rows, ("the runbook tells the operator %s will carry CELL_CHANGED "
                  "and the rehearsal does not produce it" % named[0])
    for band in cc.SIGNAL_BANDS:
        assert "| %s |" % cc.SIGNAL_LABELS[band] in md, (
            "the checklist promises all three bands; %s never appears" % band)


def test_every_marker_the_module_can_raise_is_demonstrated_somewhere():
    """A marker nobody has ever seen fire is a claim, not a check. Each must show
    up either in the rehearsal corpus — where an operator meets it — or in this
    file, which means it has a test of its own. A criterion, not an exemption
    list: a new marker with neither is caught (D-275)."""
    recs = sc.generate(points=8, repeats=5, tiers=("metro",),
                       campaigns=("SZ",), radio=True)
    rehearsed = rr.render_markdown(rr.analyze(recs))
    with io.open(os.path.abspath(__file__), encoding="utf-8-sig") as fh:
        own = fh.read()
    markers = _markers_the_module_can_raise()
    assert len(markers) >= 6, ("read %r out of the source — the scan stopped "
                               "matching and is now checking almost nothing"
                               % sorted(markers))
    undemonstrated = [m for m in sorted(markers)
                      if m not in rehearsed and m not in own]
    assert not undemonstrated, (
        "markers with neither a rehearsal instance nor a test: %s"
        % undemonstrated)
