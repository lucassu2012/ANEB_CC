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
import ast
import copy
import importlib
import io
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import attribution
import buffering_rollup
import campaign_common as cc
import campaign_report as rpt
import coverage_matrix
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


def _render_stability(recs):
    return [stability.render_markdown(stability.stability_cells(recs, k), k)
            for k in stability.DEFAULT_STABILITY_KPIS]


# The one source for "which renderers does the sweep actually call". The set of
# names below is what the coverage test compares against the modules on disk, so
# the loop and the claim cannot drift apart (D-231).
_SWEEP = {
    "buffering_rollup": lambda r: buffering_rollup.render_markdown(buffering_rollup.analyze(r)),
    "trust_rollup": lambda r: trust_rollup.render_markdown(trust_rollup.analyze(r)),
    "transport_rollup": lambda r: transport_rollup.render_markdown(transport_rollup.analyze(r)),
    "subscore_rollup": lambda r: subscore_rollup.render_markdown(subscore_rollup.analyze(r)),
    "validity_rollup": lambda r: validity_rollup.render_markdown(validity_rollup.analyze(r)),
    "trend": lambda r: trend.render_markdown(trend.analyze(r)),
    "stability": _render_stability,
    # both were outside the sweep while the test's name promised every renderer;
    # publish_check's renderer maps severity -> icon, so a severity added without
    # its icon raises KeyError on every corpus and nothing here would have noticed
    "publish_check": lambda r: pc.render_markdown(pc.check(r)),
    "coverage_matrix": lambda r: coverage_matrix.render_markdown(coverage_matrix.analyze(r)),
}

# Reached through build_report_markdown rather than called here (D-231).
_SWEPT_VIA_REPORT = {
    "attribution": "campaign_report.build_report_markdown calls it",
    "order_effect": "campaign_report.build_report_markdown calls it",
}

# Deliberately outside this sweep, with the reason written down rather than the
# module quietly missing from a hand-kept tuple.
_NOT_SWEPT = {
    "provenance": "renders a manifest computed over real files on disk; "
                  "covered by tests/test_provenance.py",
    "corpus_health": "analyze() takes load_records' stats alongside the records, "
                     "not a bare record list",
}


def test_no_renderer_crashes_on_any_shape():
    for seed in SEEDS:
        recs = _random_corpus(seed)
        try:
            rpt.build_report_markdown(recs)
            rpt.build_report_html(recs, "2026-01-01 00:00:00 +0800")
            pc.check(recs)
            for name, render in _SWEEP.items():
                render(recs)
        except Exception as e:                   # noqa: BLE001 - report the seed
            raise AssertionError(f"seed {seed} crashed: {type(e).__name__}: {e}")


def _modules_exposing_render_markdown():
    """Module names under scripts/ that define a top-level render_markdown.

    Parsed, not imported, and above all not hand-listed: a renderer added later
    turns up here on its own, and the test below fails until someone either
    sweeps it or writes down why not (D-231)."""
    scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    found = set()
    for name in sorted(os.listdir(scripts_dir)):
        if not name.endswith(".py"):
            continue
        with io.open(os.path.join(scripts_dir, name), encoding="utf-8-sig") as fh:
            try:
                tree = ast.parse(fh.read(), name)
            except SyntaxError:                  # not ours to police here
                continue
        if any(isinstance(n, ast.FunctionDef) and n.name == "render_markdown"
               for n in tree.body):
            found.add(name[:-3])
    return found


def test_the_renderer_sweep_covers_every_renderer_there_is():
    """「nothing crashes — every renderer survives every shape」 is what this file
    claims in its own docstring, and the sweep was a hand-kept tuple holding 7 of
    the 13 renderers on disk. publish_check and coverage_matrix were simply
    missing; attribution and order_effect ride along inside the report; the last
    two need something a record list cannot give them (D-231).

    A statement covering everything has to derive its list, or it only covers
    what someone remembered.
    """
    found = _modules_exposing_render_markdown()
    accounted = set(_SWEEP) | set(_SWEPT_VIA_REPORT) | set(_NOT_SWEPT)
    assert found - accounted == set(), (
        f"renderer(s) {sorted(found - accounted)} are in scripts/ but outside the "
        "sweep — add them to _SWEEP or say in _NOT_SWEPT why not")
    assert accounted - found == set(), (
        f"{sorted(accounted - found)} no longer define render_markdown — the list "
        "is describing modules that are gone")
    assert len(found) >= 13, f"only {len(found)} renderers found — did the scan break?"


def test_report_is_deterministic_for_a_given_corpus():
    for seed in SEEDS:
        recs = _random_corpus(seed)
        assert rpt.build_report_markdown(recs) == rpt.build_report_markdown(recs), seed


def _at_least(seen, floor, what):
    """The assertions above only mean something if they ran.

    These tests put their only assertion inside a loop over something the
    corpora derive, and several inside an `if` on top of that. They were all
    non-vacuous — measured at 102 to 2049 executions — but by luck, since
    nothing would have noticed a collection going empty. Writing the measured
    count down turns 'it happened to run' into 'it has to run' (D-227).
    """
    assert seen >= floor, (
        f"{what}: the assertion ran {seen} times, below the {floor} these "
        "corpora used to produce — it is passing on almost nothing")


def test_low_confidence_marked_whenever_below_the_floor():
    """Never silently present a cell built from too few samples."""
    seen = 0
    for seed in SEEDS:
        for c in rpt.heat_cells(_random_corpus(seed), cc.DEFAULT_MIN_SAMPLES):
            seen += 1
            assert c["low_confidence"] == (c["n"] < cc.DEFAULT_MIN_SAMPLES), seed
    _at_least(seen, 80, "heat cells checked for the low-confidence mark")


def test_a_low_confidence_cell_still_reaches_the_page_and_says_so():
    """campaign_report's docstring: 「低于样本门的格标 low_confidence —— never
    hidden, never zero-filled」. The test above says 「Never silently present a
    cell built from too few samples」. Both are claims about what the reader
    sees, and both are checked on the analysis dict: a renderer that dropped the
    marker — or the whole row — passes every one of them (D-239, the shape
    D-232 found in the R-10 guard).

    Modules come from _SWEEP, not from a list written here, so a rollup that
    grows a low_confidence flag later joins on its own.
    """
    checked, contributing = 0, set()
    for mod in _cell_modules():
        for tag, recs in _render_guard_corpora():
            res = mod.analyze(recs)
            cells = res["cells"]
            if not cells or "low_confidence" not in cells[0]:
                continue                     # this rollup marks thin data elsewhere
            rows = _table_body(mod.render_markdown(res))
            if len(rows) != len(cells):
                continue                     # section did not render one row per cell
            for cell, row in zip(cells, rows):
                if not cell.get("low_confidence"):
                    continue
                checked += 1
                contributing.add(mod.__name__)
                assert "low_conf" in row, (
                    f"{mod.__name__} {tag}: this cell is below the sample "
                    "floor and its row does not say so — the reader has no way "
                    f"to know\n  {row[:150]}")

    # Floors, measured: 384 rows over buffering / subscore / trust / trend. trend
    # only joined once the corpora carried three campaigns (D-242) — before that
    # it rendered no table and was walked past without a word.
    _at_least(checked, 300, "low-confidence cells whose rendered row was read")
    assert len(contributing) >= 4, (
        f"only {sorted(contributing)} contributed — the sweep stopped reaching "
        "the rollups that carry the flag")


def _numbers_in(cell):
    """Keys currently holding a real number. bool is an int in Python and is
    never a measurement, so it stays out."""
    return [k for k, v in cell.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)]


def _number_slots(cell):
    """Every place in this cell holding a real number: a key, or a position
    inside a list-valued one, as (key, index-or-None).

    Lists matter because a whole column can live in one — trend's `trajectory`
    is the row's campaign columns — and a knock-out that only touches scalars
    walks straight past it. Wiring trend into the corpora was not enough on its
    own; the audit for D-242 said MISSED until the slots included list positions.
    """
    slots = []
    for key, value in cell.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            slots.append((key, None))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, (int, float)) and not isinstance(item, bool):
                    slots.append((key, i))
    return slots


_NUMERAL = re.compile(r"\d+(?:\.\d+)?")


def _cells_of(row):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _numerals_in(cell):
    return len(_NUMERAL.findall(cell))


def _table_body(md):
    """Data rows of the first markdown table: everything after the |---| rule."""
    lines = md.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("|") and set(line) <= set("|- "):
            return [l for l in lines[i + 1:] if l.startswith("| ")]
    return []


def _three_campaign_corpus(seed):
    """A random corpus relabelled into three campaigns in time order.

    The trend section needs MIN_CAMPAIGNS_FOR_TREND (3) before it renders a table
    at all, and _random_corpus tops out at two — so every render-level guard was
    walking past trend without a row to look at, in silence (D-242)."""
    recs = copy.deepcopy(_random_corpus(seed))
    for i, rec in enumerate(recs):
        which = i % 3
        camp = rec["run"].setdefault("campaign", {})
        camp["campaign_id"] = f"c{which + 1}"
        rec["run"]["started_at_epoch_ms"] = 1_700_000_000_000 + which * 86_400_000
    return recs


def _render_guard_corpora():
    """(tag, records) the render-level guards walk. Random corpora plus a few
    three-campaign ones, because a section nobody can render is a section nobody
    is guarding."""
    out = [(f"seed{s}", _random_corpus(s)) for s in SEEDS]
    out += [(f"3camp{s}", _three_campaign_corpus(s)) for s in list(SEEDS)[:5]]
    return out


def _cell_modules():
    """Modules in the sweep whose analyze() returns per-cell rows. Taken from
    _SWEEP so there is one list of renderers, not two."""
    found = []
    for name in _SWEEP:
        mod = importlib.import_module(name)
        if not hasattr(mod, "analyze"):
            continue
        try:
            res = mod.analyze([])
        except Exception:                        # noqa: BLE001 - not a cell module
            continue
        if isinstance(res, dict) and "cells" in res:
            found.append(mod)
    return found


def test_null_medians_never_render_as_zero():
    """A cell with no usable samples must show the placeholder, not 0 (R-10).

    The body this replaces asserted `cc.fmt_num(c[key], 3) == "—"` from inside an
    `if c[key] is None` branch — a property of fmt_num, reached without rendering
    anything, over one module and three keys, while the README promises R-10 of
    every tool. Putting the classic `or 0` into buffering_rollup's median column
    left the whole suite green, and the raw 0.5681499999999999 that came with it
    (fmt_num bypassed, so no rounding either) went unnoticed too (D-232).

    Asked differentially, because the obvious way round does not survive its own
    mutation: read the printed keys off the renderer's source and `or 0` deletes
    the fmt_num call the scan was looking for, so the key silently leaves the
    list. Instead each number is knocked out at the source — set one cell's value
    to None, render again, and the row has to answer with one more placeholder.
    A key the section does not print leaves the row untouched and is skipped.

    What counts as the breach is exactly what R-10 forbids — the value coming
    back as a number. A column that answers 「—」, or a word, or even a bare None,
    has not substituted anything; only a numeral has.
    """
    mods = _cell_modules()
    assert len(mods) >= 4, f"only {[m.__name__ for m in mods]} — did the scan break?"

    knocked = printed_keys = 0
    for tag, recs in _render_guard_corpora():     # ~1s for the whole knock-out sweep
        for mod in mods:
            base = mod.analyze(recs)
            rows = _table_body(mod.render_markdown(base))
            if len(rows) != len(base["cells"]):
                continue                         # section is not one row per cell
            for i, cell in enumerate(base["cells"]):
                for key, idx in _number_slots(cell):
                    doctored = copy.deepcopy(base)
                    if idx is None:
                        doctored["cells"][i][key] = None
                    else:
                        doctored["cells"][i][key][idx] = None
                    row = _table_body(mod.render_markdown(doctored))[i]
                    knocked += 1
                    if row == rows[i]:
                        continue                 # this key reaches no column here
                    printed_keys += 1
                    changed = [(a, b) for a, b in
                               zip(_cells_of(rows[i]), _cells_of(row)) if a != b]
                    # Somewhere a numeral has to have left the row. Not "a cell
                    # turned non-numeric" — one knocked-out value can also shift
                    # the shared precision of its neighbours (D-220), and those
                    # neighbours were answering for it.
                    assert any(_numerals_in(b) < _numerals_in(a) for a, b in changed), (
                        f"{mod.__name__} {tag} cell {i}: {key} was set to "
                        "None and every column it moved still prints as many "
                        f"numbers as before ({changed!r}) — a not-computable "
                        "value reached the page as a number\n"
                        f"  before: {rows[i][:120]}\n  after:  {row[:120]}")

    # Floors, not counts: measured 3649 knock-outs, 2925 reaching a column, 84 of
    # the slots being positions inside a list. The three-campaign corpora brought
    # trend's table into range (3238 -> 3565) and the list slots brought its
    # trajectory columns with it (-> 3649) — wiring the corpus in was not enough
    # on its own, and the audit said MISSED until both were done (D-242).
    _at_least(knocked, 2800, "numbers knocked out and re-rendered")
    _at_least(printed_keys, 2300, "knocked-out numbers that actually reach a column")


def test_suspect_shares_stay_in_range():
    n_suspect = n_clock = 0
    for seed in SEEDS:
        recs = _random_corpus(seed)
        for c in buffering_rollup.analyze(recs)["cells"]:
            if c["suspect_share"] is not None:
                n_suspect += 1
                assert 0.0 <= c["suspect_share"] <= 1.0, seed
        for c in trust_rollup.analyze(recs)["cells"]:
            if c["clock_suspect_share"] is not None:
                n_clock += 1
                assert 0.0 <= c["clock_suspect_share"] <= 1.0, seed
            assert c["clock_suspect"] <= c["clock_annotated"], seed
            assert c["stream_bad"] <= c["stream_counted"], seed
    _at_least(n_suspect, 70, "buffering suspect shares in range")
    _at_least(n_clock, 70, "clock suspect shares in range")


def test_validity_counts_never_exceed_attempts():
    seen = 0
    for seed in SEEDS:
        for c in validity_rollup.analyze(_random_corpus(seed))["cells"]:
            seen += 1
            total = c["valid"] + c["valid_low_confidence"] + c["invalid"] + c["unknown"]
            assert total == c["attempted"], seed
            if c["valid_rate"] is not None:
                assert 0.0 <= c["valid_rate"] <= 1.0, seed
    _at_least(seen, 130, "validity cells whose four buckets were reconciled")


def test_publish_check_always_returns_known_severities():
    known = {pc.FAIL, pc.WARN, pc.NA, pc.PASS}
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
    def _ragged(md, where):
        n = 0
        if not isinstance(md, str):                  # stability renders per KPI
            md = "\n".join(md)
        for chunk in re.split(r"(?m)^#{2,3} ", md)[1:]:
            widths = {_columns(ln) for ln in chunk.splitlines() if ln.startswith("| ")}
            if widths:
                n += 1
            assert len(widths) <= 1, (where, chunk.splitlines()[0], widths)
        return n

    tabled = swept = 0
    for seed in SEEDS:
        recs = _random_corpus(seed)
        tabled += _ragged(rpt.build_report_markdown(recs), seed)
        # ...and every renderer, not only the ones the report assembles.
        # coverage_matrix and publish_check print tables that no report contains,
        # so a ragged row in either rendered as garbage with nothing to say so
        # (D-253). _SWEEP is the derived list — a renderer added later is swept
        # here on its own.
        for name, render in _SWEEP.items():
            swept += _ragged(render(recs), f"{name}@{seed}")
    # An empty width set satisfies `<= 1`, so sections without a table cost
    # nothing to pass — only the ones that have one are evidence (D-227).
    _at_least(tabled, 300, "report sections that actually contained a table")
    _at_least(swept, 150, "renderer sections that actually contained a table")


_EPOCH = 1783944000000          # 2026-07-13T12:00:00Z
_DAY = 86400000


def test_the_summary_only_points_at_things_the_report_actually_contains():
    """The summary keeps saying 「见 X 段的 `Y`」. X and Y have to be there.

    D-209 added 「见稳定性段 `CV 不可计算` 一列」 — and that section's header is
    单元/n/中位/均值/CV%/稳定?/备注. There is no such column; the string lives
    inside 备注 as a marker. The reader is sent to look for a column that does
    not exist (D-212), which is D-202's doc-drift failure happening inside one
    document.

    Two precise rules, deliberately narrow so this cannot start crying wolf:
    every ALL-CAPS marker the summary names in backticks must appear in the body,
    and anything the summary calls 「一列」 must really be a column header.
    """
    import synth_campaign as sc
    from synth import contractify, kpi_scenario_records
    recs = sc.inject_chaos(sc.generate(points=4, repeats=3,
                                       campaigns=("base", "opt", "final")))
    loose = kpi_scenario_records(1, kpi={"t1_ttft_ms": 100}, point="P-ONE")
    for r in loose:
        r["run"].pop("campaign", None)
    recs = list(recs) + [contractify(r) for r in loose]
    md = rpt.build_report_markdown(recs)
    chunks = re.split(r"(?m)^#{2,3} ", md)
    summary = next((c for c in chunks if c.startswith("摘要")), "")
    body = "".join(c for c in chunks if not c.startswith("摘要"))
    assert summary and body

    markers = {m for m in re.findall(r"`([A-Z][A-Z0-9_]{3,})`", summary)}
    assert markers, "no marker pointers in the summary — fixture too thin"
    missing = sorted(m for m in markers if m not in body)
    assert not missing, ("summary points at markers the report never prints",
                         missing)

    headers = set()
    for i, line in enumerate(md.splitlines()[:-1]):
        if line.startswith("| ") and re.fullmatch(
                r"\|[-|: ]+\|", md.splitlines()[i + 1].strip()):
            headers |= {c.strip().strip("*` ") for c in line.strip().strip("|").split("|")}
    for named in re.findall(r"`([^`]+)`\s*一列", summary):
        assert named in headers, (named, sorted(headers))


def test_the_summary_never_sends_anyone_to_the_unlabeled_bucket():
    """`unlabeled/unknown/unknown` is not a place, so it must not be ranked as one.

    A corpus whose only bad scores were unlabelled produced the headline
    「体验最差格 —— unlabeled/unknown/unknown(41)」: the city's worst location,
    with no name and nobody to send (D-211). The count stays — those records are
    real — but it is reported as an unaddressed bucket, not as somewhere to go.

    Also pins the trap this fix walks into: when EVERY bad cell is unlabelled the
    named list is empty, and a bullet keyed on that list reports「no problem at
    all」 because the problems had no address.
    """
    from synth import aqs_records, contractify
    good = [r for pt, v in (("SZ-CBD-01", 88), ("SZ-CBD-02", 84))
            for r in aqs_records(v, 5, point=pt)]
    bad = aqs_records(41, 5, point="X")
    for r in bad:
        r["run"].pop("campaign", None)          # -> the unlabeled bucket
    recs = [contractify(r) for r in good + bad]

    line = [ln for ln in rpt.render_summary_markdown(recs).splitlines()
            if ln.startswith("- **体验最差格")][0]
    assert f"{cc.UNLABELED}/" not in line, line   # never named as a destination
    assert "1 个格 AQS 达 fair/poor" in line, line  # …but still counted
    assert "无点位标签" in line, line               # …and said out loud
    assert "无 fair/poor 格" not in line, line      # …and NOT reported as clean

    # a real bad point alongside it: named, with the bucket disclosed beside it
    mixed = [contractify(r) for r in
             [x for pt, v in (("SZ-CBD-01", 88), ("SZ-BAD-02", 52))
              for x in aqs_records(v, 5, point=pt)] + bad]
    line2 = [ln for ln in rpt.render_summary_markdown(mixed).splitlines()
             if ln.startswith("- **体验最差格")][0]
    assert "SZ-BAD-02" in line2 and f"{cc.UNLABELED}/" not in line2, line2
    assert "2 个格 AQS 达 fair/poor" in line2, line2
    assert "1 个格无点位标签" in line2, line2


def test_unlabeled_records_are_not_a_campaign_in_the_trend():
    """「无标签」 is a bucket, not a point in time.

    It used to sort into the middle of the chronology and become a column:
    `base → unlabeled → SYNTH-base → SYNTH-opt`, with nothing saying the second
    one is not a campaign. A cell measured once without a label and once in a
    real round then got a two-point trajectory and an 改善/回退 verdict computed
    against "the records nobody labelled". Unlabeled records may come from any
    number of rounds, so placing them anywhere on a timeline is a fabrication
    (D-210) — they are excluded from the ordering and counted in the open.

    The summary's own two bugs are pinned here as well: cells with no direction
    were dropped by an `if c["direction"]` filter, and the campaign count came
    from the labelled ids rather than the columns the trend actually used.
    """
    import trend
    import synth_campaign as sc
    from synth import contractify, kpi_scenario_records
    # three LABELLED campaigns, because the trend bullet only renders at three —
    # with two, the summary half of this test skipped itself and two mutations
    # walked straight through the first version of it
    recs = sc.generate(points=3, repeats=3, campaigns=("base", "opt", "final"))
    # records with no run.campaign block at all -> the unlabeled bucket
    unlabelled = [contractify(r) for r in
                  kpi_scenario_records(4, kpi={"t1_ttft_ms": 100}, point="P-NL")]
    for r in unlabelled:
        r["run"].pop("campaign", None)
    recs = list(recs) + unlabelled

    res = trend.analyze(recs)
    assert cc.UNLABELED not in res["campaigns"], res["campaigns"]
    assert res["unlabeled_records"] == len(unlabelled), res["unlabeled_records"]
    md = trend.render_markdown(res)
    assert f"{len(unlabelled)} 条记录无战役标签" in md
    assert f"{cc.UNLABELED} →" not in md and f"→ {cc.UNLABELED}" not in md

    decided = sum(1 for c in res["cells"] if c["direction"])
    undecided = sum(1 for c in res["cells"] if not c["direction"])
    assert decided and undecided, (decided, undecided)   # fixture shows both
    line = [ln for ln in rpt.render_summary_markdown(recs).splitlines()
            if ln.startswith("- **纵向趋势")]
    # With unlabeled out of the ordering these two are the same set, which is
    # why the bullet's old `len(labeled)` now agrees with the columns actually
    # used: fixing the root cause made that symptom unreachable rather than
    # merely unlikely. Pinned, so a future divergence has to answer for itself.
    inv = rpt.inventory(recs)
    assert set(res["campaigns"]) == {c for c in inv["campaigns"] if c != cc.UNLABELED}

    assert line, "the trend bullet did not render — this test would skip itself"
    assert f"{undecided} 格不可计算" in line[0], line[0]
    assert f"（{len(res['campaigns'])} 个战役）" in line[0], line[0]


def test_the_stability_bullet_accounts_for_every_cell_not_just_the_judged_ones():
    """A denominator the reader cannot check is a denominator that hides things.

    「2/3 单元超 CV 门」 on a corpus of seven cells, four of which have no
    computable CV at all — those four appeared nowhere in the summary. Every
    other bullet discloses its remainder (归因「另有 N 个格不可计算」, 介质「另有
    N 个格噪声不可估」); this one did not, so cells that could not be judged read
    as cells that passed (§2.2 / §2.3, D-209).
    """
    import stability
    from synth import contractify, kpi_scenario_records
    recs = []
    for i, vals in enumerate(([100, 130, 70, 115, 85], [100, 101, 99, 100, 100],
                              [50, 80, 40, 70, 60])):
        for v in vals:
            recs += kpi_scenario_records(1, kpi={"t1_ttft_ms": v}, point=f"P{i:02d}")
    for i in range(3, 7):                       # n=1 each -> CV not computable
        recs += kpi_scenario_records(1, kpi={"t1_ttft_ms": 100}, point=f"P{i:02d}")
    recs = [contractify(r) for r in recs]

    total = no_cv = measured = 0
    for k in stability.DEFAULT_STABILITY_KPIS:
        for c in stability.stability_cells(recs, k):
            total += 1
            if c["cv_percent"] is None:
                no_cv += 1
            else:
                measured += 1
    assert no_cv and measured, (no_cv, measured)      # the fixture must show both
    assert measured + no_cv == total

    line = [ln for ln in rpt.render_summary_markdown(recs).splitlines()
            if ln.startswith("- **复测")][0]
    assert f"/{measured} 单元超 CV 门" in line, line
    assert f"{no_cv} 个单元 CV 不可计算" in line, line


def test_summary_examples_really_are_the_worst_ones():
    """The summary promises its examples are the worst three. Check it.

    Only 优化前后 sorted its examples (D-182); the rest listed whichever cells
    came first by label. On the rehearsal grid「172 单元超 CV 门」named three
    cells at CV 23% while the worst were at 39% — and the reader goes and looks
    at the ones you named (D-208).

    Two ways in, because the bullets differ: where a number is printed beside
    each name, assert the printed sequence is monotone; where none is (the
    172-entry stability list), recompute the true worst and require it first.
    """
    import stability
    import synth_campaign as sc
    # the chaos corpus is the one that populates ALL FOUR example lists at once;
    # the plain grid leaves 有效率 and 蜂窝劣于 wifi empty, so a guard built on it
    # would silently exercise a single bullet — the fixture-cannot-reach-the-branch
    # trap this layer keeps falling into
    from synth import aqs_records, contractify
    recs = sc.inject_chaos(sc.generate(points=6, repeats=5, campaigns=("base",)))
    md = rpt.render_summary_markdown(recs)
    assert "最严重的前三个" in md, "the promise itself went missing"

    # the chaos grid yields only ONE cellular-worse cell, and a one-item list is
    # trivially ordered — so that path gets a corpus of its own
    # label order is the REVERSE of severity on purpose: with PA mildest, an
    # unsorted list still comes out looking sorted and the fixture proves nothing
    # — the first cut of this corpus did exactly that and the mutation slipped
    # through
    media = []
    for pt, cellular in (("PA", (80, 81, 82, 83, 84)), ("PB", (70, 71, 72, 73, 74)),
                         ("PC", (50, 51, 52, 53, 54))):
        for medium, vals in (("wifi", (90, 91, 92, 93, 94)), ("cellular", cellular)):
            for v in vals:
                for r in aqs_records(v, 1, point=pt):
                    r["run"]["transport"] = medium
                    media.append(r)
    mds = [md, rpt.render_summary_markdown([contractify(r) for r in media])]

    # 1) monotone where the value is on the page
    checked = 0
    for doc in mds:
        for head, pat in (("体验最差格", r"\((\d+(?:\.\d+)?)[，)]"),
                          ("有效率不达门", r"\((\d+(?:\.\d+)?)%\)"),
                          ("蜂窝劣于 wifi", r"\(Δ(-?\d+(?:\.\d+)?)±")):
            line = [ln for ln in doc.splitlines() if ln.startswith(f"- **{head}")]
            if not line:
                continue
            vals = [float(v) for v in re.findall(pat, line[0])]
            if len(vals) < 2:
                continue
            checked += 1
            assert vals == sorted(vals), (head, vals)   # worst = smallest, first
    assert checked >= 3, (
        f"only {checked} value-bearing example list(s) exercised — the corpus "
        "no longer reaches the others, so this guard has quietly narrowed")

    # 2) the stability list prints no CV, so recompute the true worst
    worst = None
    for k in stability.DEFAULT_STABILITY_KPIS:
        for c in stability.stability_cells(recs, k):
            if c["cv_percent"] is not None and c["unstable"]:
                if worst is None or c["cv_percent"] > worst[0]:
                    worst = (c["cv_percent"], rpt._cell_label(
                        c["cell"], ("point_id", "carrier", "time_band", "tier",
                                    "profile_id")) + f"·{k}")
    assert worst, "fixture has no unstable cell"
    line = [ln for ln in md.splitlines() if ln.startswith("- **复测不稳定")][0]
    assert worst[1] in line, (worst, line)


def _heat_rows(md):
    """(shown_value, grade) per data row of a heat-card markdown table."""
    out = []
    for line in md.splitlines():
        if not line.startswith("| ") or line.startswith("| 点位") or "---" in line:
            continue
        cells = [c.strip() for c in _UNESCAPED_PIPE.split(line.strip().strip("|"))]
        if len(cells) >= 6 and cells[3] != "—":
            out.append((cells[3], cells[5]))
    return out


def test_a_displayed_score_never_contradicts_the_grade_beside_it():
    """The number is rounded for the reader; the grade is computed from the raw
    value. When rounding crosses a band edge the row argues with itself — an AQS
    of 84.96 printed as `85` next to `good`, while the legend right above says 85
    and up is `excellent` (D-207).

    Checked as a property over every heat cell, not just the edges I happened to
    think of: parse the rendered value back and re-grade it.
    """
    from synth import contractify, aqs_records
    for raw in (84.96, 84.999, 69.96, 53.96, 85.0, 70.0, 54.0, 90.0):
        recs = [contractify(r) for r in aqs_records(raw, 5, point="P")]
        rows = _heat_rows(rpt.render_heatcard_markdown(rpt.heat_cells(recs)))
        assert rows, raw
        for shown, grade in rows:
            assert cc.aqs_grade(float(shown)) == grade, (raw, shown, grade)
    for seed in (0, 3, 7, 11, 15):
        rows = _heat_rows(rpt.render_heatcard_markdown(
            rpt.heat_cells(_random_corpus(seed))))
        for shown, grade in rows:
            assert cc.aqs_grade(float(shown)) == grade, (seed, shown, grade)


def test_a_row_of_numbers_subtracts_to_the_delta_printed_on_it():
    """before, after and delta are three columns of one row. Rounding each
    independently let 70.02 and 70.06 print as `70` and `70.1` — a difference of
    0.1 — beside a delta of 0.04 (D-207). A reader subtracting two columns of the
    same table must not get a third answer."""
    from synth import contractify, aqs_records

    def camp(vals, cid):
        return [r for v in vals for r in
                aqs_records(v, 1, campaign_id=cid, point="P1")]

    checked = 0
    for before, after in (([70.00, 70.01, 70.02, 70.03, 70.04],
                           [70.04, 70.05, 70.06, 70.07, 70.08]),
                          ([40, 42, 44, 46, 48], [60, 62, 64, 66, 68])):
        recs = [contractify(r) for r in camp(before, "base") + camp(after, "opt")]
        md = rpt.render_comparison_markdown(
            rpt.compare_campaigns(recs, "base", "opt"))
        rows = [l for l in md.splitlines() if l.startswith("| P1")]
        assert rows, md
        for line in rows:
            c = [x.strip() for x in _UNESCAPED_PIPE.split(line.strip().strip("|"))]
            b, a, delta = c[3], c[4], c[5].split()[0]
            if "—" in (b, a, delta):
                continue
            checked += 1
            assert abs((float(a) - float(b)) - float(delta)) < 1e-9, line
    # `assert rows` only proves the table is there; the subtraction is skipped
    # for any row carrying a placeholder, so a fixture that stopped producing
    # comparable cells would pass having checked nothing (D-227).
    _at_least(checked, 2, "rows whose three numbers were actually subtracted")


def test_fmt_num_agreeing_stays_short_when_there_is_no_conflict():
    """Precision on demand only. Widening every number would trade one honesty
    problem for an unreadable table."""
    assert cc.fmt_num_agreeing(90.0, cc.aqs_grade) == "90"
    assert cc.fmt_num_agreeing(72.5, cc.aqs_grade) == "72.5"
    assert cc.fmt_num_agreeing(84.96, cc.aqs_grade) == "84.96"
    assert cc.fmt_num_agreeing(None, cc.aqs_grade) == "—"
    # a predicate that raises must not take the report down with it
    assert cc.fmt_num_agreeing(1.0, lambda x: 1 / 0) == "1"


_VOID_HTML = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
              "meta", "param", "source", "track", "wbr"}
_HTML_NOW = "2026-01-01 00:00:00 +0800"


def _html_imbalance(doc):
    """Unclosed / mis-nested tags in an HTML document, as readable strings."""
    from html.parser import HTMLParser

    class _Balance(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack, self.errors = [], []

        def handle_starttag(self, tag, attrs):
            if tag not in _VOID_HTML:
                self.stack.append((tag, self.getpos()))

        def handle_endtag(self, tag):
            if tag in _VOID_HTML:
                return
            if not self.stack:
                self.errors.append(f"</{tag}> with nothing open at {self.getpos()}")
                return
            if self.stack[-1][0] != tag:
                self.errors.append(
                    f"</{tag}> while <{self.stack[-1][0]}> is open "
                    f"(opened {self.stack[-1][1]}) at {self.getpos()}")
                for i in range(len(self.stack) - 1, -1, -1):
                    if self.stack[i][0] == tag:
                        del self.stack[i:]
                        break
                return
            self.stack.pop()

    p = _Balance()
    p.feed(doc)
    p.close()
    return p.errors + [f"<{t}> never closed (opened {pos})" for t, pos in p.stack]


def test_html_deliverable_is_structurally_well_formed():
    """The HTML is the form that gets emailed out (D-140), and nothing was
    checking that its tags close.

    Markdown tests cannot see this: a label that breaks the DOM leaves the
    markdown table perfectly intact. Currently clean on every corpus below —
    recorded as a negative result, kept as a guard because the surface had none
    (D-206).
    """
    from synth import contractify, kpi_scenario_records
    cases = {f"random seed {s}": _random_corpus(s) for s in (0, 5, 11)}
    cases["corrupt"] = _corrupt_corpus()
    for pid in ("SZ|CBD-01", "</table><h1>hi</h1>", "A&B<td>x</td>", "P" * 200,
                '行"引"号'):
        cases[f"hostile {pid[:16]}"] = [
            contractify(r) for r in
            kpi_scenario_records(6, aqs=90, kpi={"n1_rtt_p50_ms": 20}, point=pid)]
    for name, recs in cases.items():
        errs = _html_imbalance(rpt.build_report_html(recs, _HTML_NOW))
        assert not errs, (name, errs[:3])


def test_hostile_labels_never_become_live_markup():
    """Tag balance is blind to a well-formed injection: `<b>X</b>` in a point
    name keeps the document balanced while rendering as markup (D-206).

    Each case also asserts the payload is still THERE, escaped — a renderer that
    silently dropped the label would otherwise pass this test while losing the
    operator's data.
    """
    from synth import contractify, kpi_scenario_records
    for pid, live in (("P<b>X</b>", "<b>X</b>"),
                      ("P<td>X</td>", "<td>X</td>"),
                      ("P<img src=x onerror=alert(1)>", "<img src=x"),
                      ('P" onmouseover="alert(1)', 'onmouseover="alert(1)"'),
                      ("P<script>alert(1)</script>", "<script>alert(1)")):
        recs = [contractify(r) for r in
                kpi_scenario_records(6, aqs=90, kpi={"n1_rtt_p50_ms": 20}, point=pid)]
        doc = rpt.build_report_html(recs, _HTML_NOW)
        assert live not in doc, pid
        # …and it was escaped rather than dropped
        assert "&lt;" in doc or "&quot;" in doc, pid


def test_the_summarys_attribution_exclusion_is_reproducible_from_csv():
    """An analyst holding only the CSVs must be able to re-derive the summary.

    The attribution bullet drops every cell the matrix calls NOT USABLE — 62 of
    72 on the two-campaign rehearsal grid — and discloses the count. But WHICH
    markers mean "not usable" lives in attribution.SEVERE_FLAGS, and the
    `incomparability` column ships them mixed in with the advisory ones. So the
    one number the bullet discloses could not be checked against the export it
    came from (D-205). CSV is the surface with no banner above it; a filter
    column nobody can interpret is not a filter.
    """
    import csv as csvmod
    import tempfile
    import attribution
    import synth_campaign as sc
    recs = sc.generate(points=3, repeats=3, campaigns=("base", "opt"))
    line = [ln for ln in rpt.render_summary_markdown(recs).splitlines()
            if "分段归因" in ln][0]
    m = re.search(r"\*\*(\d+) 个格因不可比标记未计入\*\*", line)
    assert m, line
    stated = int(m.group(1))
    assert stated > 0, "the fixture must actually exclude something"

    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "c")
        rpt.write_csv_tables(recs, prefix)
        with open(prefix + "_attribution.csv", encoding="utf-8-sig", newline="") as f:
            rows = [r for r in csvmod.DictReader(f)
                    if r["kpi"] == attribution.DEFAULT_KPI]
    assert rows
    assert sum(1 for r in rows if r["severe_incomparability"]) == stated, stated

    # …and the column earns its place: the pre-existing `incomparability` column
    # gives a different answer, because it also carries advisory markers
    naive = sum(1 for r in rows if r["incomparability"])
    assert naive != stated, (
        "severe_incomparability is indistinguishable from incomparability on "
        "this corpus — the fixture no longer proves the column is needed")


def test_no_module_defines_the_same_top_level_name_twice():
    """Python takes the LAST definition and says nothing about the first.

    Caught while writing D-199: a new helper in this layer's largest test file
    shared a name with one defined 900 lines later, so every call silently
    reached the wrong function — with a different signature, which is the only
    reason it surfaced at all. Same names with COMPATIBLE signatures would have
    run the wrong code quietly, in a test file, where a wrong pass looks exactly
    like a right one.
    """
    import ast
    import glob
    scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tools = sorted(glob.glob(os.path.join(scripts, "*.py")))
    suite = sorted(glob.glob(os.path.join(scripts, "tests", "*.py")))
    files = sorted(tools + suite)
    # Counted per half. A single `>= 20` over the union passed with the tests/
    # half deleted outright — the tools alone are 22 — and tests/ is precisely
    # where the docstring says the shadowing bug was found (D-255).
    assert len(tools) >= 18, f"only {len(tools)} tool modules — scripts/ half shrank"
    assert len(suite) >= 20, f"only {len(suite)} test modules — tests/ half shrank"
    dupes = []
    for path in files:
        # campaign_report.py carries a UTF-8 BOM; Python's importer strips it and
        # a plain utf-8 read does not
        with open(path, encoding="utf-8-sig") as f:
            tree = ast.parse(f.read(), path)
        lines = {}
        for node in tree.body:
            names = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names = [node.name]
            elif isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            for n in names:
                lines.setdefault(n, []).append(node.lineno)
        for n, at in sorted(lines.items()):
            if len(at) > 1:
                dupes.append(f"{os.path.basename(path)}:{n} at lines {at}")
    assert not dupes, dupes


def _modules_the_report_renders():
    """Module names whose render_markdown build_report_markdown actually calls.

    Read from that function's own AST, with import aliases resolved from the
    module header (`import provenance as prov_mod`), so a section added to the
    report turns up here on its own. Same discipline as
    _modules_exposing_render_markdown, pointed at the report rather than the
    directory (D-246)."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "campaign_report.py")
    with io.open(path, encoding="utf-8-sig") as fh:
        tree = ast.parse(fh.read(), "campaign_report.py")
    alias = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                alias[a.asname or a.name] = a.name
    fns = [n for n in tree.body
           if isinstance(n, ast.FunctionDef) and n.name == "build_report_markdown"]
    assert len(fns) == 1, f"expected one build_report_markdown, found {len(fns)}"
    found = set()
    for n in ast.walk(fns[0]):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "render_markdown"
                and isinstance(n.func.value, ast.Name)):
            found.add(alias.get(n.func.value.id, n.func.value.id))
    return found


# Where each report section lands in the CSV bundle. The module list is derived
# above; this only says which file carries it, and the test below checks that
# file is really written and really has rows — a header-only stub answers nobody.
_CSV_FOR_SECTION = {
    "attribution": "attribution",
    "buffering_rollup": "buffering",
    "order_effect": "order_effect",
    "stability": "stability",
    "subscore_rollup": "subscores",
    "transport_rollup": "transport",
    "trend": "trend",
    "trust_rollup": "trust",
    "validity_rollup": "validity",
}

# Exported in another machine-readable form, with the form named — not simply
# missing from the mapping above.
_NO_CSV = {
    "provenance": "campaign_report.py --provenance writes the whole manifest, "
                  "sha256 included, as JSON; the analyst loses nothing by "
                  "pulling only machine-readable artefacts",
}


def test_every_section_of_the_report_reaches_the_csv_bundle():
    """write_csv_tables' own docstring promises 「an analyst pulling only the CSVs
    must not silently lose sections visible in the report」 (D-109), and nothing
    checked it. Nine of the ten modules the report renders shipped a CSV. The
    tenth was order_effect, which puts per-position medians, a spread, a
    percentage and a 疑似序位偏倚 verdict on the page and exported none of it —
    the one methodological verdict an analyst would most want to re-derive at a
    different threshold (D-246).

    The subject list is read from build_report_markdown's AST, so the next
    section added is either exported or has its reason written into _NO_CSV.
    """
    import csv as csvmod
    import tempfile
    rendered = _modules_the_report_renders()
    accounted = set(_CSV_FOR_SECTION) | set(_NO_CSV)
    assert rendered - accounted == set(), (
        f"{sorted(rendered - accounted)} render a section into the report and are "
        "in neither _CSV_FOR_SECTION nor _NO_CSV — export it, or write down here "
        "which machine-readable form carries it instead")
    assert accounted - rendered == set(), (
        f"{sorted(accounted - rendered)} no longer reach the report — this mapping "
        "is describing sections that are gone")
    assert len(rendered) >= 10, (
        f"only {len(rendered)} modules found in build_report_markdown — did the "
        "AST scan break?")

    # ...and the mapping names files that exist and carry data. Three campaigns,
    # because _trend.csv is written only when a trend exists (D-196).
    recs = _three_campaign_corpus(11)
    total = 0
    with tempfile.TemporaryDirectory() as d:
        paths = rpt.write_csv_tables(recs, os.path.join(d, "c"))
        by_suffix = {os.path.basename(p)[len("c_"):-len(".csv")]: p for p in paths}
        for mod, suffix in sorted(_CSV_FOR_SECTION.items()):
            assert suffix in by_suffix, (
                f"{mod} is mapped to _{suffix}.csv, which write_csv_tables does not "
                f"write; it writes {sorted(by_suffix)}")
            with open(by_suffix[suffix], encoding="utf-8-sig", newline="") as f:
                rows = list(csvmod.reader(f))
            assert len(rows) >= 2, (
                f"_{suffix}.csv carries a header and no rows on a corpus whose "
                f"report renders {mod} — an empty file loses the section just as "
                "completely as no file at all")
            total += len(rows) - 1
    assert total >= 100, (
        f"only {total} data rows across the nine mapped CSVs (measured 129 when "
        "this floor was set) — the corpus went degenerate and this guard is "
        "asserting almost nothing")


# Which constant decides the KPI set of every CSV whose rows are per-KPI. The
# subject list is not this dict: the test finds every CSV that HAS a `kpi` column
# and fails on any that is missing from here.
_KPI_SET_FOR_CSV = {
    "kpi_heat": lambda: rpt.DEFAULT_KPI_HEAT,
    "attribution": lambda: attribution.ATTRIBUTABLE_KPIS,
    "segment_profile": lambda: attribution.ATTRIBUTABLE_KPIS,
    "stability": lambda: stability.DEFAULT_STABILITY_KPIS,
    "order_effect": lambda: order_effect.ORDER_SENSITIVE_KPIS,
}


def test_a_per_kpi_csv_carries_every_kpi_its_section_covers():
    """D-246 asked whether each report section reaches the CSV bundle at all, and
    the export it added answered 「yes」 with one KPI out of three: the report
    renders one 序位效应 section per ORDER_SENSITIVE_KPIS entry, while
    write_csv_tables called analyze() with its default kpi. The file existed, had
    rows, and satisfied the new guard — a guard coarser than the promise it was
    written for, which is how it passed while two thirds of the section were
    missing (D-247).

    So the criterion has to be the section's own: a CSV with a `kpi` column
    carries exactly the KPI set that section is computed over.
    """
    import csv as csvmod
    import tempfile
    import synth_campaign as sc
    recs = sc.generate(points=3, repeats=3, campaigns=("base", "opt", "later"))
    seen = 0
    with tempfile.TemporaryDirectory() as d:
        for path in rpt.write_csv_tables(recs, os.path.join(d, "c")):
            suffix = os.path.basename(path)[len("c_"):-len(".csv")]
            with open(path, encoding="utf-8-sig", newline="") as f:
                rows = list(csvmod.DictReader(f))
            if not rows or "kpi" not in rows[0]:
                continue
            seen += 1
            assert suffix in _KPI_SET_FOR_CSV, (
                f"_{suffix}.csv has a kpi column and no entry here — name the "
                "constant that decides which KPIs belong in it")
            want = set(_KPI_SET_FOR_CSV[suffix]())
            got = {r["kpi"] for r in rows}
            assert got == want, (
                f"_{suffix}.csv covers {sorted(got)} but its section is computed "
                f"over {sorted(want)} — missing {sorted(want - got)}, "
                f"unexpected {sorted(got - want)}")
    assert seen == len(_KPI_SET_FOR_CSV), (
        f"only {seen} per-KPI CSVs reached this check, expected "
        f"{len(_KPI_SET_FOR_CSV)} — a corpus this rich should exercise all of them")


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
    # The three-tier matrix pools tier medians and its cells carry the marker
    # through incomparability_flags — and it was the one pooling section this
    # list never named, while being the largest analytical section in the report
    # (D-251). Measured: it already renders the marker; the list simply never
    # asked.
    ("attribution", lambda recs: attribution.render_markdown(
        attribution.attribute(recs, kpi="t1_ttft_ms"))),
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

    ⚠ SOLE targeted guard on two of the nine entries below: order_effect's value
      guard and buffering's marker render. The mutation audit for D-197 broke all
      ten guards one at a time; those two were caught by this test and nothing
      else. Weakening or narrowing it leaves them held by nothing — if you are
      replacing it, put the replacement in first.
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


def _table_rows(md, title):
    """Rows of EVERY table under a heading with this title, as {column: cell}.

    Attribution, segment-profile and order-effect each render one section per
    KPI. Reading only the first occurrence left roughly half the report's rows
    unchecked — 40 of 118, 63 of 123, 95 of 204 — while the guard above still
    called itself a sweep of every printed relation (D-226).
    """
    rows = []
    for part in md.split(title)[1:]:
        header = None
        for ln in part.split("\n## ")[0].splitlines():
            s = ln.strip()
            if not (s.startswith("|") and s.endswith("|")):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if header is None:
                header = cells
                continue
            rows.append(dict(zip(header, cells)))
    return rows


def _lead_num(s):
    """Leading number of a cell like '43.1 (n=1*)', '17.4 ↑', '6.9%'."""
    if s is None:
        return None
    t = s.replace("*", "").replace("%", "").strip()
    for stop in (" ", "("):
        if stop in t:
            t = t.split(stop)[0]
    try:
        return float(t.replace("−", "-").strip())
    except ValueError:
        return None


# (name, section title, columns, relation -> deviation, minimum rows to see).
# The relation is exactly what a reader can check with the numbers on the page.
_ARITH_CASES = (
    # Floors sit near three quarters of what the corpora currently produce
    # (13 / 22 / 13 / 197 / 197 / 103), so a scan that quietly narrows again —
    # reading one section per repeated title, as this one used to — fails here
    # rather than reporting a clean sweep of half the rows (D-226).
    ("接入介质 Δ = cellular − wifi", "## 接入介质对比",
     ("wifi", "cellular", "Δ(cell−wifi)"),
     lambda w, c, d: abs((c - w) - d), 10),
    ("分段 离差/典型 = MAD ÷ |典型|", "## 分段异常定位",
     ("典型值(中位)", "离差(MAD)", "离差/典型"),
     lambda t, m, p: abs(m / abs(t) * 100.0 - p) if t else None, 15),
    ("优化前后 Δ = after − before", "## 优化前后对比",
     ("before", "after", "Δ"),
     lambda b, a, d: abs((a - b) - d), 10),
    ("有效性 尝试 = 有效+低置信+失效+未知", "## 有效性与失效原因",
     ("尝试", "有效(严格)", "低置信", "失效", "未知"),
     lambda att, v, lc, inv, unk: abs((v + lc + inv + unk) - att), 150),
    ("有效率 = (有效+低置信) ÷ 尝试", "## 有效性与失效原因",
     ("尝试", "有效(严格)", "低置信", "有效率"),
     lambda att, v, lc, rate: abs((v + lc) / att * 100.0 - rate) if att else None, 150),
    ("序位 极差% = 极差 ÷ |总体中位|", "## 序位效应诊断",
     ("极差", "总体中位", "极差%"),
     lambda sp, ov, pct: abs(sp / abs(ov) * 100.0 - pct) if ov else None, 80),
    # The decomposition this whole guard was written for. D-219 is cited in the
    # docstring as the reason it exists — 36% of attribution rows disagreed —
    # and the three-tier matrix was the one section it never read (D-252).
    # Floor from the synth grid's 72 checkable rows.
    ("三级差分 端到端 = 接入 + 区域骨干+ + 核心骨干+", "## 三级差分归因矩阵",
     ("接入(metro)", "区域骨干+", "核心骨干+", "端到端(core)"),
     lambda a, r, c, e: abs((a + r + c) - e), 54),
)


def test_every_printed_arithmetic_relation_holds():
    """Whatever the reader can compute from the page has to come out right.

    Six sections print numbers standing in an arithmetic relation, and each
    invites the reader to check it: subtract two columns, add a decomposition,
    divide one column by another. Rounded independently they disagreed — 36% of
    attribution rows (D-219), 23% of sub-score rows (D-220), 8 of 30 transport
    rows and 10 of 41 before/after rows (D-221). This checks all of them at once
    so the next one is not found by reading either.
    """
    import synth_campaign as sc
    mds = [rpt.build_report_markdown(_random_corpus(s)) for s in SEEDS]
    mds.append(rpt.build_report_markdown(_corrupt_corpus()))
    # A full three-tier grid. On the random corpora the attribution matrix prints
    # 204 rows of which exactly ONE has all four increment columns filled — the
    # rest are 「—」 because a tier is missing — so the decomposition below would
    # have been checked on a single row and called covered (D-252).
    mds.append(rpt.build_report_markdown(sc.generate(
        points=3, repeats=3, campaigns=("base", "opt", "later"))))

    for name, title, cols, relation, floor in _ARITH_CASES:
        seen, bad = 0, []
        for md in mds:
            for row in _table_rows(md, title):
                vals = [_lead_num(row.get(c)) for c in cols]
                if any(v is None for v in vals):
                    continue
                seen += 1
                try:
                    off = relation(*vals)
                except (TypeError, ZeroDivisionError):
                    continue
                # half of the last digit the report prints
                if off is not None and off > 0.05:
                    bad.append((dict(zip(cols, vals)), round(off, 4)))
        # The corpora have to reach the relation, or a clean verdict is empty.
        assert seen >= floor, (
            f"{name}: only {seen} rows carried all of {cols} — below the {floor} "
            "this corpus used to produce, so the check proves nothing")
        assert not bad, (
            f"{name}: {len(bad)} row(s) where the numbers on the page do not "
            f"satisfy it: {bad[:3]}")


def _html_table_rows(html, *header_cells):
    """Cell texts of every row of the HTML table whose header carries these."""
    out = []
    for table in html.split("<table>")[1:]:
        table = table.split("</table>")[0]
        head = table.split("</tr>")[0]
        if not all(f"<th>{h}</th>" in head for h in header_cells):
            continue
        for row in table.split("</tr>")[1:]:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if cells:
                out.append([re.sub(r"<[^>]+>", "", c).strip() for c in cells])
    return out


def test_the_html_deliverable_satisfies_the_same_arithmetic():
    """A fix that reached one surface has to be shown to reach the other.

    The attribution table is rendered twice — render_markdown, and a
    hand-maintained _attr_table_html whose own comment records that this is how
    markers went missing before (D-160). D-219 fixed the markdown copy; the HTML
    one kept rounding independently and 39% of its three-tier rows still failed
    the addition while the markdown deliverable was clean (D-222).
    """
    from synth import contractify, kpi_scenario_records

    # The random corpora yield one complete three-tier cell across 20 seeds, so
    # they cannot carry this check — the floor below caught that. Build cells
    # that are complete AND drift under independent rounding.
    recs = []
    for k in range(6):
        metro = 100.04 + k
        for tier, v in (("metro", metro), ("regional", metro + 50.02),
                        ("core", metro + 100.04)):
            for r in kpi_scenario_records(5, aqs=80,
                                          kpi={"n1_rtt_p50_ms": v},
                                          point=f"P{k + 1}"):
                r["run"].setdefault("campaign", {})["tier"] = tier
                recs.append(contractify(r))

    # The fixture must carry the hazard, or the assertion below is free.
    naive = [float(cc.fmt_num(x)) for x in (100.04, 50.02, 50.02)]
    assert abs(sum(naive) - float(cc.fmt_num(200.08))) > 1e-9, \
        "fixture values no longer drift under independent rounding"

    html = rpt.build_report_html(recs, _HTML_NOW)
    seen, bad = 0, []
    for cells in _html_table_rows(html, "接入", "区域骨干+", "核心骨干+", "端到端"):
        if len(cells) < 6:
            continue
        vals = [_lead_num(c) for c in cells[2:6]]
        if any(v is None for v in vals):
            continue
        seen += 1
        access, regional, core, e2e = vals
        if abs((access + regional + core) - e2e) > 1e-9:
            bad.append(cells[:6])
    assert seen >= 5, (
        f"only {seen} complete three-tier rows in the HTML — the check never "
        "reached the relation")
    assert not bad, (
        f"{len(bad)} HTML row(s) where 接入+区域+核心 does not equal 端到端: "
        f"{bad[:3]}")


_GRADE_WORDS = ("excellent", "good", "fair", "poor")


def test_the_html_heat_card_score_never_contradicts_its_grade():
    """The AQS card's grade comes from the number printed in the same box.

    _heat_grid_html takes the verdict as an argument and the AQS call site
    passes cc.aqs_grade, so rounding cannot land on the wrong band — that is
    correct today and measured here (117 coloured cells, no contradictions).
    It is guarded because the markdown copy of this rule had a test and the
    HTML copy did not, which is exactly the asymmetry D-222 was.

    Only the AQS card qualifies. The per-KPI cards colour a raw KPI median by
    the producer's own grade field, so grading 221.74 ms with aqs_grade is
    meaningless — a first pass at this check did that and reported 295 false
    contradictions.
    """
    from synth import aqs_records, contractify

    # Random corpora never land a score on a band edge, so this check passed on
    # the broken renderer too — the mutation audit said MISSED. These scores sit
    # just under an edge: printed at one decimal they cross it.
    # Bands are 85 / 70 / 54, and this card prints two decimals — so the values
    # that can cross an edge are three nines out, not two. A first attempt used
    # 84.96 and the mutation audit came back MISSED: at two decimals that value
    # prints as itself and the renderer cannot get it wrong.
    edges = (84.996, 69.996, 53.996)
    recs = []
    for i, score in enumerate(edges):
        recs += [contractify(r) for r in aqs_records(score, 3, point=f"P{i + 1}")]
    for score in edges:
        assert cc.aqs_grade(score) != cc.aqs_grade(float(cc.fmt_num(score, 2))), (
            f"{score} no longer changes grade at the two decimals this card "
            "prints — the fixture cannot tell the fixed renderer from the "
            "broken one")

    seen, bad = 0, []
    html = rpt.build_report_html(recs, _HTML_NOW)
    for part in html.split("<h2>")[1:]:
        head = part.split("</h2>")[0]
        if "AQS" not in head or "分 KPI" in head:
            continue
        section = part.split("<h2>")[0]
        for td in re.findall(r"<td[^>]*background[^>]*>(.*?)</td>", section, re.S):
            text = re.sub(r"<[^>]+>", " ", td)
            num = re.search(r"(-?\d+(?:\.\d+)?)", text)
            grade = re.search("|".join(_GRADE_WORDS), text)
            if not num or not grade:
                continue
            seen += 1
            want = cc.aqs_grade(float(num.group(1)))
            if want != grade.group(0):
                bad.append((num.group(1), grade.group(0), want))
    assert seen >= len(edges), (
        f"only {seen} graded AQS cells for {len(edges)} band-edge scores — the "
        "check never reached the relation")
    assert not bad, (
        f"{len(bad)} HTML cell(s) whose printed score grades differently from "
        f"the label beside it: {bad[:3]}")


_DELIM_RE = re.compile(r"\|[-|: ]+\|")


def _orphan_rows(md):
    """Rows that belong to no table: (line_number, text).

    A row is only a row if a `|---|` line sits under the header. The two
    existing table guards collect column counts per section, which a blank line
    mid-table does not disturb at all — the rows keep their shape, they just
    stop being rows.
    """
    lines = md.splitlines()
    out = []
    in_fence = False
    width = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|") and len(s) > 1):
            width = None
            continue
        if width is None:
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if not _DELIM_RE.fullmatch(nxt):
                out.append((i + 1, s[:60]))
                continue
            width = _columns(s)
    return out


def test_no_blank_line_leaves_a_report_row_outside_its_table():
    """The PO reads the report rendered, so a row has to render as a row.

    GFM ends a table at the first blank line; every row after one renders as a
    paragraph full of literal pipes. DECISION_LOG.md had 36 such blanks and was
    losing about 190 of its 212 rows that way (D-214), and nothing in this
    layer's guards would have noticed the same thing in the report itself —
    uniform column counts stay uniform across a split.
    """
    tables = rows = 0
    for label, md in ([(f"seed {s}", rpt.build_report_markdown(_random_corpus(s)))
                       for s in SEEDS]
                      + [("chaos", rpt.build_report_markdown(_corrupt_corpus()))]):
        orphans = _orphan_rows(md)
        assert not orphans, (
            f"{label}: {len(orphans)} row(s) sit outside any table "
            f"(no delimiter above them): {orphans[:4]} — these render as "
            "literal pipes, not as rows")
        lines = [ln for ln in md.splitlines() if ln.strip().startswith("|")]
        rows += len(lines)
        tables += sum(1 for ln in md.splitlines() if _DELIM_RE.fullmatch(ln.strip()))

    # The corpora have to actually contain tables, or this proves nothing.
    assert tables >= 20 and rows >= 200, (
        f"only {tables} tables / {rows} rows rendered across {len(SEEDS) + 1} "
        "corpora — the scan found nothing to check")


_SECTION_SPLIT = re.compile(r"[（(：:]")


def _section_key(title):
    """The phrase before the first bracket or colon.

    The two surfaces word their titles differently — HTML says 「…（AQS 中位；
    * = 样本不足 low_conf）」 where markdown says 「…（AQS 中位）」, and splits the
    per-KPI sections into one heading each. Matching the full title reports
    misses that are the matcher's fault, not the report's (D-243)."""
    return _SECTION_SPLIT.split(title.strip())[0].strip()


def _md_section_keys(md):
    return {_section_key(l.lstrip("# ")) for l in md.splitlines()
            if l.startswith("## ")}


def _html_section_keys(html):
    return {_section_key(re.sub(r"<[^>]+>", "", m.group(1)))
            for m in re.finditer(r"<h[1-6][^>]*>(.*?)</h[1-6]>", html, re.S)}


def test_every_markdown_section_reaches_the_html():
    """§2.6: the delivery surfaces carry the same information. What stood behind
    it was a marker-level check (`test_every_attribution_marker_reaches_all_three
    _surfaces`) — a whole section added to markdown alone would pass it (D-243).

    Section by section, not marker by marker, and keyed loosely enough that the
    two surfaces are allowed to phrase a title differently.
    """
    stamp = "2026-01-01 00:00:00 +0800"
    corpora = [("chaos", _corrupt_corpus())]
    corpora += [(f"seed{s}", _random_corpus(s)) for s in SEEDS]
    corpora += [("3camp0", _three_campaign_corpus(0))]

    compared = 0
    for tag, recs in corpora:
        md = _md_section_keys(rpt.build_report_markdown(recs))
        html = _html_section_keys(rpt.build_report_html(recs, stamp))
        compared += len(md)
        missing = sorted(md - html)
        assert not missing, (
            f"{tag}: {missing} appear in the markdown report and nowhere in the "
            "HTML — the two deliverables no longer say the same thing")
        assert len(md) >= 14, (
            f"{tag}: only {len(md)} markdown sections — the corpus stopped "
            "producing a full report and this comparison proves little")

    # Floor: measured 119 sections over these corpora.
    _at_least(compared, 100, "markdown sections compared against the HTML")
