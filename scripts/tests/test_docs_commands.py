# -*- coding: utf-8 -*-
"""Guard: every command printed in the operator docs must still be runnable.

Doc drift bit this project three times in one session — the README was eight
tools behind, the runbook's grid-config example used key names the tool does not
read (D-119), and its glob example crashed in the project's primary shell
(D-120). Those were found by hand; this makes the mechanical half automatic.

Static check (no subprocess, so it stays fast): for every `python <script>.py`
command in a fenced block of the operator docs, the script must exist and every
`--flag` used must actually be declared in that script's argparse. It cannot
catch semantic mistakes (a wrong JSON key inside a config file), but it does
catch renamed flags and scripts — the drift that silently makes docs lie.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(SCRIPTS)
def _doc_files():
    """Every doc that could carry a runnable command, walked rather than listed.

    This was two hand-typed paths while `_commands`'s own docstring promised
    "every documented python invocation" — 26 commands checked, 7 outside the
    list entirely. One of the seven was `python scripts/update_shared_test_status.py`
    in a launchpad blueprint: a copy-pasteable command for a script that no longer
    exists. The guard that exists to catch exactly that had never been pointed at
    the only doc that needed it (D-287).
    """
    out = [os.path.join(SCRIPTS, "README.md")]
    for root, _dirs, files in os.walk(os.path.join(REPO, "docs")):
        out += [os.path.join(root, f) for f in sorted(files) if f.endswith(".md")]
    return out


DOCS = _doc_files()

# The two pages an operator actually reads before and during a field trip. Named
# rather than walked, and the distinction is the point: which docs carry runnable
# commands is a property of their content, so DOCS is derived; which pages owe
# the operator a description of the gate's verdicts is an editorial decision
# about audience, and pretending to derive it would silently demand that every
# blueprint in docs/ explain publish_check (D-287).
_SEVERITY_PAGES = [os.path.join(SCRIPTS, "README.md"),
                   os.path.join(REPO, "docs", "M2_CAMPAIGN_RUNBOOK.md")]

_FENCE = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.S)
_CMD = re.compile(r"^python\s+(\S+\.py)\s*(.*)$")
_FLAG = re.compile(r"(?<![\w-])(--[a-zA-Z][\w-]*)")


def _commands():
    """(doc, script_path, [flags]) for every documented python invocation."""
    out = []
    for doc in DOCS:
        if not os.path.exists(doc):
            continue
        with open(doc, encoding="utf-8") as f:
            body = f.read()
        for block in _FENCE.findall(body):
            # join shell line continuations so multi-line commands stay one command
            block = block.replace("\\\n", " ")
            for line in block.splitlines():
                line = line.strip()
                if line.startswith("#") or line.startswith("//"):
                    continue
                m = _CMD.match(line)
                if m:
                    # docs outside scripts/ spell the path from the repo root;
                    # the checks below resolve names against scripts/
                    script = m.group(1).replace("\\", "/")
                    if script.startswith("scripts/"):
                        script = script[len("scripts/"):]
                    out.append((os.path.basename(doc), script,
                                _FLAG.findall(m.group(2))))
    return out


def test_the_grid_proposal_plans_by_the_arithmetic_the_tool_judges_by():
    """The field trip is planned from a table in the grid proposal — how many
    repeats a cell needs for an 80% chance of seeing a 5% difference, and what
    that costs in field days. On day one the operator runs `stability.py
    --plan`, which computes the same number from cc.required_n_at_power.

    Two artefacts, one question, and nothing reconciled them. Retune the power
    factor and the tool would demand several times the repeats while the
    proposal still says eleven: a trip planned at 5.1 field days, declared
    insufficient by the first check run on arrival (D-273).

    The doc's column came from 40000 simulations and the tool from a closed
    form, so exact equality was not a given — it was measured, and holds on
    every row. The rows are read out of the document, so editing the table is
    caught as surely as editing the function.
    """
    import campaign_common as cc
    docs = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "docs")
    with open(os.path.join(docs, "M2_GRID_DESIGN_PROPOSAL.md"),
              encoding="utf-8-sig") as fh:
        lines = fh.read().split("\n")

    # This document has a second CV table whose rows also start with `| 3% |`,
    # so find the header that names the column and read only what follows it.
    heads = [i for i, ln in enumerate(lines) if "八成把握需 n≥" in ln]
    assert len(heads) == 1, f"expected one power table, found {len(heads)}"
    rows = []
    for ln in lines[heads[0] + 2:]:
        m = re.match(r"^\|\s*(\d+)%\s*\|.*\|\s*\*{0,2}(\d+)\*{0,2}\s*\|\s*$", ln)
        if not m:
            break
        rows.append((int(m.group(1)), int(m.group(2))))

    assert len(rows) == 4, (
        f"read {rows} out of the power table — the shape changed and this "
        "check is comparing whatever it happened to match")
    for cv, need in rows:
        # the median cancels out of n, so CV and the 5% target go in as-is
        got = cc.required_n_at_power(cv, 5.0)
        assert got == need, (
            f"CV {cv}%: the proposal plans for n≥{need}, the tool requires "
            f"n≥{got}. The trip is planned from one and judged by the other")


def test_every_row_of_the_field_budget_uses_the_same_arithmetic():
    """§2 turns a run count into hours and field days, and the PO picks a design
    off that table. Its three inputs — seconds per run, the field-overhead
    factor, the hours in a field day — are stated in that section's own prose,
    so every other column is derivable and nothing needs typing twice.

    Nothing recomputed them. v2.0 rewrote every row for the single-tier grid
    (D-283), and a slip in any one plans a trip by a number no tool agrees
    with — the same shape D-273 found in the power column, one table down.

    Rows are read out of the document, so adding a design is covered without
    anyone remembering to. Tolerance is 0.06 because the document rounds some
    cells and truncates others; what is being checked is that the columns are
    one arithmetic, not how the digits were rendered.
    """
    docs = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "docs")
    with open(os.path.join(docs, "M2_GRID_DESIGN_PROPOSAL.md"),
              encoding="utf-8-sig") as fh:
        lines = fh.read().split("\n")
    text = "\n".join(lines)

    def one(pattern, what):
        m = re.search(pattern, text)
        assert m, "§2 no longer states %s" % what
        return m.group(1)

    per_run_s = float(one(r"=\s*([\d.]+)\s*秒", "the per-run duration"))
    overhead = 1 + int(one(r"现场开销\s*(\d+)%", "the field overhead")) / 100.0
    day_h = float(one(r"外场日（(\d+)h/天）", "the hours in a field day"))

    # §0 has a five-column table too, so anchor on the header naming this one.
    heads = [i for i, ln in enumerate(lines)
             if ln.startswith("|") and "纯测量" in ln]
    assert len(heads) == 1, "expected one budget table, found %d" % len(heads)

    rows = []
    for ln in lines[heads[0] + 2:]:
        cells = [c.strip().strip("*").strip()
                 for c in ln.strip().strip("|").split("|")]
        if len(cells) != 5 or not re.match(r"^\d+$", cells[1]):
            break
        rows.append((int(cells[1]),
                     float(cells[2].rstrip(" h")),
                     float(cells[3].rstrip(" h")),
                     float(cells[4].rstrip(" 天"))))

    assert len(rows) >= 6, (
        "read %r out of the budget table — the shape changed and this check is "
        "comparing whatever it happened to match" % (rows,))

    for runs, pure_h, with_oh_h, days in rows:
        want_pure = runs * per_run_s / 3600.0
        want_oh = want_pure * overhead
        want_days = want_oh / day_h
        for got, want, col in ((pure_h, want_pure, "纯测量"),
                               (with_oh_h, want_oh, "含开销"),
                               (days, want_days, "外场日")):
            assert abs(got - want) <= 0.06, (
                "%d runs: the table says %s=%s, the stated arithmetic "
                "(%.1fs/run, x%.1f, %.0fh/day) gives %.3f"
                % (runs, col, got, per_run_s, overhead, day_h, want))


def test_the_numbers_the_proposal_quotes_from_the_layer_still_hold():
    """D-273 reconciled the power column. Applying the same question to the
    rest of that document turns up two more numbers it states as facts about
    this layer (D-274).

    Both matter to the reader in the same way. The whole case for n=5 rests on
    it lining up with the layer's sample floor, so if that constant moves the
    argument is quietly wrong. And the sentence telling an operator that cells
    above 10% CV need the apparatus checked is the report's own gate — retune
    it and the proposal advises one threshold while the report marks another.
    """
    import campaign_common as cc
    import stability
    docs = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "docs")
    with open(os.path.join(docs, "M2_GRID_DESIGN_PROPOSAL.md"),
              encoding="utf-8-sig") as fh:
        text = fh.read()

    m = re.search(r"`min_samples=(\d+)`", text)
    assert m, "the proposal no longer states the sample floor it aligns with"
    assert int(m.group(1)) == cc.DEFAULT_MIN_SAMPLES, (
        f"the proposal aligns n=5 with min_samples={m.group(1)}, the layer "
        f"uses {cc.DEFAULT_MIN_SAMPLES} — the case for n=5 rests on that "
        "alignment")

    m = re.search(r"CV>(\d+)%\s*的格", text)
    assert m, "the proposal no longer states the CV threshold it sends to the tool"
    assert float(m.group(1)) == stability.DEFAULT_CV_GATE, (
        f"the proposal tells the operator to check the apparatus above "
        f"{m.group(1)}%, the report marks 超门 above "
        f"{stability.DEFAULT_CV_GATE}%")


def test_every_default_the_readme_states_is_the_one_the_code_uses():
    """The README is this layer's front door, and it states six defaults as
    plain fact. Every one of them is a tunable — the CV gate, the plan target,
    the order-effect threshold, the validity floor, the sample floor, and the
    shape of the synthetic grid. Retune any and the front door starts lying
    (D-275).

    The sites are enumerated FROM the document: every 「默认」 followed by a
    number must be registered here. The four non-numeric mentions (stdout, an
    ordering rule, a gate that runs at the entrance, and a sentence saying
    `unknown` is never counted valid by default) carry no digit and so never
    enter the list — no hand-written exemptions to go stale.
    """
    import campaign_common as cc
    import order_effect
    import stability
    import synth_campaign as sc
    import validity_rollup

    docs = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(docs, "README.md"), encoding="utf-8-sig") as fh:
        lines = fh.read().split("\n")

    recs = sc.generate()
    scenarios = sum(len(list(cc.iter_scenarios(r))) for r in recs)
    registry = [
        ("CV% = 样本 stdev/mean", [stability.DEFAULT_CV_GATE]),
        ("--plan [PCT]", [stability.DEFAULT_TARGET_EFFECT_PCT]),
        ("生成 M2 规模网格", [len(recs), scenarios]),
        ("spread_pct = ", [order_effect.DEFAULT_THRESHOLD_PCT]),
        ("低于门默认", [validity_rollup.DEFAULT_MIN_RATE * 100]),
        ("样本 < `min_samples`", [cc.DEFAULT_MIN_SAMPLES]),
    ]

    sites = [ln for ln in lines if re.search(r"默认\s*\d", ln)]
    assert len(sites) == 6, (
        f"{len(sites)} numeric defaults in the README, 6 registered — a new "
        f"one was written into the prose without being reconciled: {sites}")

    for ln in sites:
        hits = [(ctx, vals) for ctx, vals in registry if ctx in ln]
        assert len(hits) == 1, (
            f"this default matches {len(hits)} registry entries, need exactly "
            f"one: {ln}")
        numbers = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", ln)]
        for want in hits[0][1]:
            assert float(want) in numbers, (
                f"the code uses {want}, the README line does not carry it: {ln}")


def test_every_field_the_wiring_spec_asks_for_has_a_consumer():
    """The wiring spec is what the other lane implements from. A field it names
    that this layer never reads is data the app writes for nobody, and the way
    that surfaces is a field trip coming back unusable (D-276).

    All seven have consumers today — the five cell dimensions, `label_source`
    in the inventory (D-153) and `server_tier_endpoint` in the tier-endpoint
    reconciliation (D-155). Nothing checked it.

    Consumption is read off the AST, not the file text: a field named only in a
    docstring is documentation, not a consumer.
    """
    import ast
    docs = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "docs")
    with open(os.path.join(docs, "CAMPAIGN_LABELS_WIRING_SPEC.md"),
              encoding="utf-8-sig") as fh:
        # only the string-typed leaves: the enclosing `campaign` object is
        # declared ["object","null"] and is not one of the label fields. Told
        # apart by shape rather than by naming it, so nothing has to be kept
        # in an exemption list (D-275).
        fields = re.findall(r'^\s*"(\w+)":\s*\{\s*"type":\s*\[\s*"string"',
                            fh.read(), re.M)
    assert len(fields) == 7, (
        f"read {fields} out of the spec — the schema fragment changed shape "
        "and this check is comparing whatever it happened to match")

    scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    consumed = set()
    scanned = 0
    for name in sorted(os.listdir(scripts_dir)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(scripts_dir, name), encoding="utf-8-sig") as fh:
            try:
                tree = ast.parse(fh.read(), name)
            except SyntaxError:
                continue
        scanned += 1
        docstrings = {
            id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
            and getattr(n, "body", None) and isinstance(n.body[0], ast.Expr)
            and isinstance(n.body[0].value, ast.Constant)
            and isinstance(n.body[0].value.value, str)}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and node.value in fields and id(node) not in docstrings):
                consumed.add(node.value)
    assert scanned >= 18, f"only {scanned} modules scanned — did the scan break?"

    orphans = [f for f in fields if f not in consumed]
    assert not orphans, (
        f"the wiring spec asks the app to write {orphans}, and no module here "
        "reads them — the other lane would ship a field this layer ignores, "
        "and the trip comes back before anyone notices")


def test_every_field_the_radio_spec_asks_for_has_a_consumer():
    """The radio spec's whole claim is that its consumer was written first, so a
    field in it that nothing reads would falsify the document's own premise —
    and would be the D-276 mistake committed by the guard against D-276.

    The field list is read out of the spec's §3 table, which is the column that
    also names the consumer: one table, so a field cannot be requested in one
    place and justified in another. Consumption is read off the AST, not the file
    text — a field named only in a docstring is documentation, not a reader.
    """
    import ast
    docs = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "docs")
    path = os.path.join(docs, "RADIO_CONTEXT_WIRING_SPEC.md")
    assert os.path.exists(path), (
        "the radio wiring spec is gone, but radio_rollup's coverage notice still "
        "sends every report's reader to it")
    with open(path, encoding="utf-8-sig") as fh:
        text = fh.read()
    body = text.split("## 3.", 1)[1].split("\n## ", 1)[0]
    fields = re.findall(r"^\|\s*`(\w+)`\s*\|", body, re.M)
    assert len(fields) == 8, (
        f"read {fields} out of the spec — the field table changed shape and "
        "this check is comparing whatever it happened to match")

    scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    consumed, scanned = set(), 0
    for name in sorted(os.listdir(scripts_dir)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(scripts_dir, name), encoding="utf-8-sig") as fh:
            try:
                tree = ast.parse(fh.read(), name)
            except SyntaxError:
                continue
        scanned += 1
        docstrings = {
            id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
            and getattr(n, "body", None) and isinstance(n.body[0], ast.Expr)
            and isinstance(n.body[0].value, ast.Constant)
            and isinstance(n.body[0].value.value, str)}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and node.value in fields and id(node) not in docstrings):
                consumed.add(node.value)
    assert scanned >= 18, f"only {scanned} modules scanned — did the scan break?"

    orphans = [f for f in fields if f not in consumed]
    assert not orphans, (
        f"the radio spec asks the app to write {orphans}, and no module here "
        "reads them — the document promises a consumer for every field")


def test_the_canonical_labels_the_layer_produces_are_named_in_the_convention():
    """The convention doc is what an annotator reads before typing a label. The
    alias tables decide what those labels become. A canonical value the tables
    can produce and the doc never names is a column in the heat card that the
    convention does not describe (D-277).

    Six today, all named. The doc deliberately teaches only the canonical form
    and does not list the aliases — behaviour more forgiving than documented,
    which is the safe direction, so this checks the outputs and not the inputs.
    """
    import campaign_common as cc
    docs = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "docs")
    with open(os.path.join(docs, "CAMPAIGN_LABELS_CONVENTION.md"),
              encoding="utf-8-sig") as fh:
        text = fh.read()

    tiers = set(cc._TIER_ALIASES.values())
    carriers = set(cc._CARRIER_ALIASES.values())
    assert tiers == set(cc.TIERS), (
        f"the tier aliases canonicalise to {sorted(tiers)} but the layer's "
        f"tiers are {cc.TIERS} — one of them can never reach attribution")
    produced = sorted(tiers | carriers)
    assert len(produced) == 6, (
        f"{produced} canonical labels — the tables changed shape and this "
        "check is comparing whatever it happened to find")
    missing = [v for v in produced if v not in text]
    assert not missing, (
        f"the alias tables can produce {missing}, and the convention names "
        "neither — an annotator meets a value the document never described")


def test_docs_contain_commands():
    """Guard the guard: if the extraction breaks, the checks below go vacuous.

    The floor moved from 8 to 25 when DOCS stopped being two typed paths: the
    walk finds 33, and a floor left at 8 would let three quarters of them
    disappear without a word (D-287)."""
    cmds = _commands()
    assert len(cmds) >= 25, f"only found {len(cmds)} documented commands — parser broken?"


def test_documented_scripts_exist():
    """A doc that tells you to run a script it no longer has is the retirement
    trap one level down: the banner says the mechanism is dead, and a fenced
    block three sections later still runs it.

    Commands naming the retired script inside a doc that carries the banner are
    exempt — that reader has already been told not to run them. Both halves of
    the exemption are read from the files rather than typed here, so a different
    missing script in the same doc still fails (D-287).
    """
    bannered = {os.path.basename(p) for p in DOCS
                if os.path.exists(p) and _has_retirement_banner(p)}
    missing = []
    for doc, script, _flags in _commands():
        if os.path.exists(os.path.join(SCRIPTS, script)):
            continue
        if doc in bannered and script in _RETIRED_SCRIPTS:
            continue
        missing.append((doc, script))
    assert not missing, f"docs reference scripts that do not exist: {missing}"


# Report sections the deliverable skeleton deliberately does not carry, each with
# its reason. Empty today — every section the report renders has a home in the
# skeleton — and kept so that dropping one is a written decision rather than an
# omission nobody notices.
_SECTION_NOT_IN_SKELETON = {}


def test_deliverable_template_section_map_resolves():
    """The deliverable skeleton tells the author which report section each of its
    chapters comes from. If a section is renamed and the map is not updated, the
    skeleton silently points at nothing — and the author only finds out while
    assembling the report (D-134).

    Checked against an EXPLICIT map block rather than by scraping prose: a regex
    over free text also matches phrases, banners and bullet labels, and a guard
    that cries wolf trains people to ignore it.
    """
    import provenance as prov
    import campaign_report as rpt
    import synth_campaign as sc

    tmpl = os.path.join(REPO, "docs", "M2_REPORT_TEMPLATE.md")
    with open(tmpl, encoding="utf-8") as f:
        body = f.read()
    block = re.search(r"<!-- SECTION-MAP:BEGIN -->(.*?)<!-- SECTION-MAP:END -->",
                      body, re.S)
    assert block, "SECTION-MAP block missing from the deliverable template"
    wanted = []
    for line in block.group(1).splitlines():
        if not line.startswith("| ") or line.startswith("| 骨架章节") or set(
                line.strip("| ")) <= set("-| "):
            continue
        wanted.append(line.strip("|").split("|")[1].strip())
    assert len(wanted) >= 10, f"section map looks truncated: {wanted}"

    # union over corpus shapes: 2 campaigns render before/after, 3+ render trend;
    # radio=True so that section renders its table rather than its gap notice
    headings = set()
    for campaigns in (("base", "opt"), ("base", "opt", "r3")):
        recs = sc.generate(points=3, repeats=5, campaigns=campaigns, radio=True)
        md = rpt.build_report_markdown(recs, provenance=prov.compute(
            [], {"lines": 1, "kept": 1}, {}, generated_at="2026-01-01",
            thresholds=rpt.effective_thresholds()))
        headings |= {ln[3:].strip() for ln in md.splitlines() if ln.startswith("## ")}

    missing = [w for w in wanted if not any(w in h for h in headings)]
    assert not missing, f"template maps to sections the report does not emit: {missing}"

    # ...and the other direction, which had no test. The map was complete by
    # hand, but nothing kept it that way: the radio section walked straight past
    # it, and an author assembling the deliverable from the skeleton would never
    # have learned the section exists. D-267's shape — of a two-way promise, ask
    # which half is checked (D-284).
    unmapped = sorted(h for h in headings
                      if not any(w in h for w in wanted)
                      and h not in _SECTION_NOT_IN_SKELETON)
    assert not unmapped, (
        f"the report renders {unmapped} and the skeleton never mentions them — "
        "add a row to SECTION-MAP, or say in _SECTION_NOT_IN_SKELETON why the "
        "deliverable does not carry that section")


def test_deliverable_template_field_map_resolves():
    """Sections existing is not enough — the skeleton asks for FIELDS inside
    them. It asked for the collection window and the profile version, neither of
    which the report emitted (D-138/139). This checks the fields, not the
    headings."""
    import provenance as prov
    import campaign_report as rpt
    import synth_campaign as sc

    tmpl = os.path.join(REPO, "docs", "M2_REPORT_TEMPLATE.md")
    with open(tmpl, encoding="utf-8") as f:
        body = f.read()
    block = re.search(r"<!-- FIELD-MAP:BEGIN -->(.*?)<!-- FIELD-MAP:END -->", body, re.S)
    assert block, "FIELD-MAP block missing from the deliverable template"
    wanted = []
    for line in block.group(1).splitlines():
        if not line.startswith("| ") or line.startswith("| 骨架索取") or set(
                line.strip("| ")) <= set("-| "):
            continue
        wanted.append(line.strip("|").split("|")[1].strip())
    assert len(wanted) >= 5, f"field map looks truncated: {wanted}"

    # union over corpus shapes, as the section map does: fields living in the
    # conditional before/after and trend sections only exist in a multi-campaign
    # report, and a single-campaign corpus would flag them as never emitted
    md = ""
    for campaigns in (("base",), ("base", "opt"), ("base", "opt", "r3")):
        recs = sc.generate(points=3, repeats=2, campaigns=campaigns)
        md += rpt.build_report_markdown(recs, provenance=prov.compute(
            [], {"lines": 1, "kept": 1}, {}, generated_at="2026-01-01",
            thresholds=rpt.effective_thresholds()))
    missing = [w for w in wanted if w not in md]
    assert not missing, f"template asks for fields the report never emits: {missing}"


# The decision log is the one place the retired mechanism SHOULD appear without a
# banner: it records what was decided and when, including things since retired.
# Banner-ing it would be editing the record rather than annotating a runbook.
_RETIRED_BANNER_NOT_NEEDED = {
    "DECISION_LOG.md": "records history, including mechanisms since retired",
}

_RETIRED_MARKS = ("SHARED_TEST_STATUS", "update_shared_test_status")
_RETIRED_BANNER = "> ⛔ **本文中所有 `SHARED_TEST_STATUS.md`"
# Scripts the retirement removed. Named so that a doc carrying the banner is
# excused for THESE and nothing else: a different missing script in the same
# file is still a broken instruction.
_RETIRED_SCRIPTS = ("update_shared_test_status.py",)


def _has_retirement_banner(path):
    """Does this doc say, before its first section, that the lease is retired?

    Before the first `## `, because a reader has to meet it ahead of the
    instructions rather than after following them.
    """
    with open(path, encoding="utf-8-sig") as fh:
        lines = fh.read().split("\n")
    first = next((i for i, ln in enumerate(lines) if ln.startswith("## ")),
                 len(lines))
    return any(ln.startswith(_RETIRED_BANNER) for ln in lines[:first])


def test_every_doc_describing_the_retired_lease_says_it_is_retired():
    """The PO retired the SHARED_TEST_STATUS lease on 2026-07-19, and CLAUDE.md
    forbids treating it as authorisation to use the device. One runbook was given
    a banner saying exactly that. Four other operational docs went on describing
    the mechanism — command templates included — with nothing marking it dead,
    so an agent that picked one up would run a retired coordination protocol and
    wait on a hand-off that is never coming.

    Measured before fixing: seven docs mention it, two carried the banner. This
    is D-272's shape on the documentation side — a mature remedy exists, and the
    question is which of the paths into it the remedy actually covers (D-286).

    The banner must appear BEFORE the first `## ` section: a reader has to meet
    it before the instructions, not after following them.
    """
    docs = os.path.join(REPO, "docs")
    scanned, offenders = 0, []
    for root, _dirs, files in os.walk(docs):
        for name in sorted(files):
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8-sig") as fh:
                lines = fh.read().split("\n")
            if not any(m in ln for ln in lines for m in _RETIRED_MARKS):
                continue
            scanned += 1
            if name in _RETIRED_BANNER_NOT_NEEDED:
                continue
            if not _has_retirement_banner(path):
                offenders.append(os.path.relpath(path, REPO))
    assert scanned >= 5, (
        "only %d docs mention the retired mechanism — the scan probably broke, "
        "and a guard that finds nothing to check passes for the wrong reason"
        % scanned)
    assert not offenders, (
        "these docs still describe the retired lease with nothing saying it is "
        "retired: %s — copy the banner from the crosscut runbook, or exempt it "
        "with a reason in _RETIRED_BANNER_NOT_NEEDED" % offenders)


def test_every_tool_is_mentioned_in_the_readme():
    """The command guard checks that documented commands work; it cannot notice a
    tool nobody documented. corpus_health.py and order_effect.py sat unmentioned
    in the README for weeks (D-131) — a reader had no way to discover them."""
    readme = os.path.join(SCRIPTS, "README.md")
    with open(readme, encoding="utf-8") as f:
        body = f.read()
    tools = [n for n in sorted(os.listdir(SCRIPTS))
             if n.endswith(".py") and not n.startswith("_")]
    # The filename, not the bare stem. `trend`, `stability` and `provenance` are
    # ordinary words in this prose, so the stem fallback would have accepted a
    # tool the README never names — a criterion weaker than the promise. All 22
    # tools already appear by filename, so this only closes the hole (D-249).
    missing = [n for n in tools if n not in body]
    assert not missing, f"tools missing from scripts/README.md: {missing}"
    assert len(tools) >= 20, f"only {len(tools)} tools scanned — did the scan break?"


def test_documented_flags_exist_in_argparse():
    """A renamed flag makes the docs lie; the reader only finds out mid-field."""
    bad = []
    sources = {}
    for doc, script, flags in _commands():
        path = os.path.join(SCRIPTS, script)
        if not os.path.exists(path):
            continue                      # covered by the test above
        if path not in sources:
            with open(path, encoding="utf-8") as f:
                sources[path] = f.read()
        for flag in flags:
            if f'"{flag}"' not in sources[path] and f"'{flag}'" not in sources[path]:
                bad.append(f"{doc}: {script} has no {flag}")
    assert not bad, "documented flags missing from argparse: " + "; ".join(bad)


# --------------------------------------------------- quoted tool output (D-202)

_QUOTES_BLOCK = re.compile(r"OUTPUT-QUOTES:(.*?)OUTPUT-QUOTES", re.S)


QUOTED_DOCS = [os.path.join(REPO, "docs", "M2_CAMPAIGN_RUNBOOK.md"),
               os.path.join(REPO, "docs", "M2_REPORT_TEMPLATE.md")]


def _output_quotes(docs=None):
    """{'<doc-stem>.<key>': phrase} from every OUTPUT-QUOTES contract block."""
    out = {}
    for doc in (docs or QUOTED_DOCS):
        if not os.path.exists(doc):
            continue
        with open(doc, encoding="utf-8") as f:
            m = _QUOTES_BLOCK.search(f.read())
        if not m:
            continue
        stem = os.path.splitext(os.path.basename(doc))[0]
        for line in m.group(1).splitlines():
            if "|" not in line:
                continue
            key, _, phrase = line.partition("|")
            key, phrase = key.strip(), phrase.strip()
            if key and phrase and " " not in key:
                out[f"{stem}.{key}"] = phrase
    return out


def _noisy_plan_md():
    import stability
    from synth import kpi_scenario_records
    recs = [r for v in (100, 130, 70, 115, 85)
            for r in kpi_scenario_records(1, kpi={"t1_ttft_ms": v})]
    rows = stability.plan_cells(stability.stability_cells(recs, "t1_ttft_ms"), 5.0)
    return stability.render_plan_markdown(rows, "t1_ttft_ms", 5.0)


def _within_noise_md():
    import campaign_report as rpt
    from synth import aqs_records, contractify
    recs = [contractify(r) for v, c in ((58, "base"), (68, "base"), (78, "base"),
                                        (60, "opt"), (70, "opt"), (80, "opt"))
            for r in aqs_records(v, 1, campaign_id=c)]
    return rpt.build_report_markdown(recs, before_id="base", after_id="opt")


def _segment_profile_md():
    """One corpus carrying BOTH segment verdicts: access varies without an
    outlier (-> 未见单点异常), core has a gross one (-> 存在单点异常)."""
    import attribution
    from synth import tier_records
    recs = []
    access = (28, 30, 32, 29, 31, 30, 29, 31)
    core = (50, 70, 90, 60, 80, 70, 65, 400)
    for i in range(len(core)):
        for tier, val in (("metro", access[i]), ("regional", access[i] + 12),
                          ("core", core[i])):
            recs += tier_records(tier, "n1_rtt_p50_ms", val, 5, point="P%02d" % i)
    return attribution.render_segment_profile_markdown(
        attribution.segment_profile(attribution.attribute(recs)))


# '<doc-stem>.<key>' -> what to render to prove the doc's quote is still emitted.
# Adding a quote to a doc without adding a renderer here fails, and vice versa.
_QUOTE_RENDERERS = {
    "M2_CAMPAIGN_RUNBOOK.plan_verdict_short": _noisy_plan_md,
    "M2_CAMPAIGN_RUNBOOK.plan_col_power": _noisy_plan_md,
    "M2_CAMPAIGN_RUNBOOK.plan_col_breakeven": _noisy_plan_md,
    # the second pair, added when the power figure finally reached the page
    # (D-240) — the runbook had warned about 需 n≥ alone until then
    "M2_CAMPAIGN_RUNBOOK.plan_col_mde_power": _noisy_plan_md,
    "M2_CAMPAIGN_RUNBOOK.plan_col_mde_flat": _noisy_plan_md,
    "M2_CAMPAIGN_RUNBOOK.noise_marker": _within_noise_md,
    "M2_REPORT_TEMPLATE.seg_anomaly_yes": _segment_profile_md,
    "M2_REPORT_TEMPLATE.seg_anomaly_no": _segment_profile_md,
    "M2_REPORT_TEMPLATE.seg_verdict_col": _segment_profile_md,
    "M2_REPORT_TEMPLATE.seg_spread_col": _segment_profile_md,
}


def test_quoted_tool_output_is_still_produced():
    """The runbook tells the operator "if you see X, do Y". X must still exist.

    D-121 made the documented COMMANDS machine-checked; the words the docs quote
    BACK from those commands were not. D-201 renamed a verdict line and the
    runbook kept quoting the old one — an operator would have stood in the field
    watching for a sentence the tool no longer prints, and nothing failed (D-202).

    An explicit contract block, not a regex over prose: a wide regex here would
    scrape ordinary sentences and produce exactly the noisy guard this layer
    rejects (D-134).

    Covers the deliverable skeleton too. The first cut covered only the runbook,
    and on the same day this guard shipped I wrote a reference in the SKELETON to
    a `判据` column that does not exist — the caliber is printed inside the
    `判读` column. The guard could not see it, because it was not looking there.
    Whatever a guard does not cover is where the next one lands (D-203).
    """
    quotes = _output_quotes()
    assert quotes, "OUTPUT-QUOTES block missing or unparsable"
    assert len({k.split(".")[0] for k in quotes}) == len(QUOTED_DOCS), sorted(quotes)
    assert set(quotes) == set(_QUOTE_RENDERERS), (
        "doc quotes and renderers disagree: "
        f"only in doc={sorted(set(quotes) - set(_QUOTE_RENDERERS))}, "
        f"only in test={sorted(set(_QUOTE_RENDERERS) - set(quotes))}")

    # The contract had only ever guarded the TOOL side — the renderer must still
    # emit the phrase. Nothing checked the DOC side: rewrite the paragraph, drop
    # the quotation, and the registration goes on protecting a quotation the
    # document no longer makes. Compared with emphasis stripped, because the
    # bold/backtick wrapper is the author's choice and not the tool's wording —
    # seg_anomaly_no is quoted in backticks while the tool emits it in bold, and
    # a literal comparison would have failed a document that does quote it
    # (D-257).
    def _bare(s):
        return s.replace("*", "").replace("`", "")

    seen = 0
    for key, phrase in sorted(quotes.items()):
        doc = next(d for d in QUOTED_DOCS
                   if os.path.splitext(os.path.basename(d))[0] == key.split(".")[0])
        with open(doc, encoding="utf-8") as f:
            text = f.read()
        m = _QUOTES_BLOCK.search(text)
        body = (text[:m.start()] + text[m.end():]) if m else text
        assert _bare(phrase) in _bare(body), (
            f"{key} is registered but its prose no longer quotes it: {phrase}")
        seen += 1
    assert seen >= 10, f"only {seen} quotes checked against prose"
    rendered = {}
    for key, phrase in sorted(quotes.items()):
        fn = _QUOTE_RENDERERS[key]
        if fn not in rendered:
            rendered[fn] = fn()
        md = rendered[fn]
        assert phrase in md, (key, phrase)
        # Containment alone is too weak, and the escape is not hypothetical: the
        # runbook used to quote the column as `需 n≥`, and D-201 split it into
        # `需 n≥(平)` and `需 n≥(80%)`. The stale, now-ambiguous label is still a
        # SUBSTRING of both, so a containment check calls it fine while an
        # operator follows the wrong column.
        #
        # HEADER cells only. Checking every cell flagged `**未见单点异常**` for
        # being a prefix of the verdict cell it legitimately begins — a guard
        # crying wolf, which this layer holds to be worse than no guard. Column
        # labels are the only thing a truncated quote can mis-aim, and they live
        # in the header row.
        lines = md.splitlines()
        headers = set()
        for i, line in enumerate(lines[:-1]):
            if line.startswith("| ") and re.fullmatch(r"\|[-|: ]+\|", lines[i + 1].strip()):
                headers |= {c.strip() for c in line.strip().strip("|").split("|")}
        longer = sorted(c for c in headers if c != phrase and c.startswith(phrase))
        assert not longer, (
            f"{key}: the doc quotes {phrase!r}, but the tool prints "
            f"{longer} — quoting the shorter form points the operator at "
            "whichever column they happen to read first")


# Read from the directory, not typed here. The list used to name five docs out of
# the twenty-two in docs/, under a test called "every doc table row" — sixteen of
# the unnamed ones have tables, one of them 74 rows long, and none was ever
# checked. Widening it costs nothing: measured, all of them already pass (D-249).
_TABLE_DOCS = [os.path.join(SCRIPTS, "README.md")] + [
    os.path.join(REPO, "docs", name)
    for name in sorted(os.listdir(os.path.join(REPO, "docs")))
    if name.endswith(".md")]

_DELIM = re.compile(r"\|[-|: ]+\|")


def _looks_like_row(line):
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and len(s) > 1


def _cells(line):
    """A row's cells. Splits on unescaped pipes only -- an escaped one is text."""
    return re.split(r"(?<!\\)\|", line.strip())[1:-1]


def test_every_doc_table_row_survives_rendering():
    """Docs are read rendered, so a row has to render as a row.

    Two ways a row silently stops being one, both found in DECISION_LOG.md
    (D-214). A bare pipe in the prose splits the row, and a renderer drops the
    cells that overflow the header -- the tail of the sentence disappears
    without a trace; 18 rows were losing text that way. And a blank line ends
    a GFM table outright, so every row after it renders as a paragraph full of
    literal pipes: 36 such blanks had split the decision table into fragments,
    leaving about 190 of its 212 rows as raw text. Neither shows up in the
    source, which is the only place a writer looks. The same sweep caught the
    D-213 row shipping with three cells where the header declares four.
    """
    tables = rows = 0
    orphans, mismatched = [], []
    for doc in _TABLE_DOCS:
        assert os.path.exists(doc), f"{doc} is gone -- this guard would go quiet"
        with open(doc, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
        in_fence = False
        width = None
        for i, line in enumerate(lines):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if not _looks_like_row(line):
                width = None
                continue
            if width is None:
                nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if not _DELIM.fullmatch(nxt):
                    orphans.append(f"{os.path.basename(doc)}:{i + 1}")
                    continue
                width = len(_cells(line))
                tables += 1
            rows += 1
            if len(_cells(line)) != width:
                mismatched.append(
                    f"{os.path.basename(doc)}:{i + 1} has {len(_cells(line))} "
                    f"cells, its header has {width}")

    # Named defects first. A split table also starves the counts below, and
    # that assertion would blame the scan ("stopped finding tables") for what
    # is a defect in the doc -- a true alarm carrying a false diagnosis.
    assert not orphans, (
        f"{len(orphans)} table row(s) belong to no table (no delimiter line "
        f"above them, usually a blank line splitting the table): {orphans[:6]} "
        "-- these render as literal pipes, not as rows")
    assert not mismatched, (
        f"{len(mismatched)} row(s) disagree with their header's column count "
        f"-- the overflow is dropped when rendered: {mismatched[:6]}")
    # Backstop only: the corpus has to reach the branch, or a scan that quietly
    # stopped recognising tables would report a clean sweep of nothing.
    # Measured 67 tables / 831 rows across every doc; the five-doc list this
    # replaced reached 15 / 393. The floor sits above THAT, so narrowing the
    # sweep back to a hand-picked few fails here instead of passing quietly
    # (D-249).
    assert tables >= 55 and rows >= 700, (
        f"only {tables} tables / {rows} rows seen across {len(_TABLE_DOCS)} "
        "docs -- either the scan stopped finding tables or the doc list was "
        "narrowed; either way its verdict means nothing")


def test_every_severity_the_gate_can_emit_is_described_where_the_operator_reads():
    """D-229 gave publish_check a fourth severity and the runbook kept saying
    there were three -- 「"无法判断"一律记 WARN」 on the page an operator reads in
    the field, for a gate that had started answering N/A. My change, someone
    else's sentence (D-244).

    The set comes from what check() actually emits, not from the module's
    constants: a severity that exists but can never be produced is not something
    the docs owe the reader, and one produced under a name nobody documented is
    exactly the drift this catches.
    """
    import publish_check as pc
    import synth_campaign as sc
    from synth import aqs_records, contractify, make_record

    def labelled(n, aqs=90, campaign="base"):
        out = []
        for r in aqs_records(aqs, n):
            r["run"]["campaign"] = {"campaign_id": campaign, "tier": "metro",
                                    "point_id": "P1", "carrier": "cmcc",
                                    "time_band": "busy"}
            out.append(contractify(r))
        return out

    corpora = [
        labelled(6),
        labelled(6) + labelled(6, aqs=70, campaign="opt"),
        [contractify(make_record(aqs=90, scenarios=[])) for _ in range(3)],
        sc.generate(points=1, repeats=2, campaigns=("base",), carriers=("cmcc",),
                    time_bands=("busy",), tiers=("metro",)),
    ]
    emitted = {r["severity"] for recs in corpora for r in pc.check(recs)}
    assert len(emitted) >= 4, (
        f"only {sorted(emitted)} were produced — the corpora stopped reaching "
        "the branches, so this proves nothing about the docs")

    for path in _SEVERITY_PAGES:
        with open(path, encoding="utf-8-sig") as fh:
            text = fh.read()
        missing = sorted(s for s in emitted if s not in text)
        assert not missing, (
            f"{os.path.basename(path)} never mentions {missing}, and the gate "
            "answers with it — the page the operator reads is a severity behind")

        # ...and mentioned TOGETHER. `PASS in text` is a four-character
        # substring test that any unrelated verify_all example satisfies, while
        # the promise is that the operator finds them described. Both docs put
        # all four inside three lines today, so a window of ten has room without
        # being vacuous; scatter one out of the passage and this fails (D-258).
        lines, best = text.split("\n"), None
        for i in range(len(lines)):
            seen = set()
            for j in range(i, len(lines)):
                seen |= {s for s in emitted if s in lines[j]}
                if seen == emitted:
                    best = j - i if best is None else min(best, j - i)
                    break
        assert best is not None and best <= 9, (
            f"{os.path.basename(path)} never lists {sorted(emitted)} within one "
            f"passage (closest span: {'none' if best is None else best + 1} lines)"
            " — they are mentioned, but nowhere described side by side")
