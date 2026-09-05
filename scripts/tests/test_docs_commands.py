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
REPO_ROOT = os.path.dirname(SCRIPTS)   # 仓根：tools/ 等 scripts/ 之外的脚本按它解析
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


def test_a_fenced_command_never_names_a_config_the_repo_does_not_ship():
    # ⚠ SOLE targeted guard (D-321's census): pointing a fenced --config at a
    #   file the repo does not ship fails this test and nothing else. The scan
    #   below checks the SCRIPT exists, never the file it is handed.
    """§0 of the runbook tells the operator, in as many words, not to hand-copy
    the grid — use the shipped file, at ../docs/campaign_grid_shenzhen.json.
    §3's daily coverage command then handed them `--config campaign_grid.json`,
    a name that exists nowhere in the repo. One document, an instruction half
    and an executable half, and the wrong one was the half that gets typed at
    the end of a field day, when the coverage check is what decides tomorrow's
    route (D-320, the shape of D-311 recurring).

    The scan above it checks that the SCRIPT in a fenced command exists and had
    never looked at the file the script is handed — a rule naming one thing
    while the guard compares another (D-246).

    Scoped to --config, which in this repo always names a shipped grid
    definition. Operator-authored inputs (labeled/*.jsonl, --map map.json, -o
    targets) are theirs to create and are deliberately not checked.
    """
    docs = [os.path.join(REPO, "docs", "M2_CAMPAIGN_RUNBOOK.md"),
            os.path.join(REPO, "docs", "M2_GRID_DESIGN_PROPOSAL.md"),
            os.path.join(SCRIPTS, "README.md")]
    seen, missing = 0, []
    for doc in docs:
        with open(doc, encoding="utf-8") as f:
            body = f.read()
        for block in _FENCE.findall(body):
            for m in re.finditer(r"--config\s+(\S+)", block):
                arg = m.group(1)
                if not arg.endswith(".json") or any(c in arg for c in "*?<>"):
                    continue
                seen += 1
                # fenced commands are written to run from scripts/
                if not os.path.exists(os.path.join(SCRIPTS, arg)):
                    missing.append("%s -> %s" % (os.path.basename(doc), arg))
    assert seen >= 1, (
        "no --config with a .json argument in any fenced command; this guard "
        "checks nothing")
    assert not missing, (
        "a fenced command hands a config file the repo does not ship; the "
        "operator types it and gets a file-not-found: %s" % missing)


def test_the_runbook_never_tells_the_operator_to_run_a_tier_that_does_not_exist():
    """D-48 abandoned the three-tier deployment for a single E-01 instance, and
    the PO reconfirmed it on 2026-07-29 (reuse the existing server, Shenzhen
    only). The runbook's rehearsal section knew that — it says so in as many
    words — while §2, the part with the commands the operator actually types,
    still walked them through metro → regional → core and gave three annotate
    lines. Following it means driving a trip against mirror endpoints that do
    not exist and labelling metro rounds as backbone ones (D-311).

    Only fenced commands are scanned: the paragraph documenting how to restore a
    multi-tier procedure later is prose and should stay. When multi-tier does
    come back this guard fails, which is the point — updating it should be a
    decision, not a side effect.
    """
    path = os.path.join(REPO, "docs", "M2_CAMPAIGN_RUNBOOK.md")
    with open(path, encoding="utf-8-sig") as fh:
        text = fh.read()
    tiers, unlabelled = [], []
    for block in _FENCE.findall(text):
        for line in block.replace("\\\n", " ").split("\n"):
            found = re.findall(r"--set\s+tier=(\S+)", line)
            tiers += found
            # "省掉它标签就是缺失而不是声明" — a command that names the point but
            # not the tier produces exactly the ambiguity the runbook warns
            # about. Checked per command, because the first cut only asked
            # whether ANY command still labelled a tier: deleting the label from
            # the field procedure left the rehearsal's copy behind and the guard
            # passed (found in this decision's own mutation audit).
            if "--set point_id=" in line and not found:
                unlabelled.append(line.strip()[:90])
    assert tiers, ("no `--set tier=` in any fenced command — either the runbook "
                   "stopped labelling the tier, or this scan broke")
    assert not unlabelled, (
        "these commands label the point but not the tier, so the corpus cannot "
        "say whether it is metro or unfilled: %s" % unlabelled)
    wrong = sorted({t for t in tiers if t != "metro"})
    assert not wrong, (
        "the runbook tells the operator to run tier(s) %s, and the deployment is "
        "a single E-01 instance (D-48) — those endpoints do not exist" % wrong)


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
    """The README is this layer's front door, and it states seven defaults as
    plain fact. Every one of them is a tunable — the CV gate, the plan target,
    the order-effect threshold, the warm-up threshold, the validity floor, the
    sample floor, and the shape of the synthetic grid. Retune any and the front
    door starts lying (D-275).

    The seventh arrived with round_effect (D-356) and this guard caught it the
    moment the prose was written — which is the point: the count is the tripwire,
    so a default cannot be documented without being reconciled.

    The sites are enumerated FROM the document: every 「默认」 followed by a
    number must be registered here. The four non-numeric mentions (stdout, an
    ordering rule, a gate that runs at the entrance, and a sentence saying
    `unknown` is never counted valid by default) carry no digit and so never
    enter the list — no hand-written exemptions to go stale.
    """
    import campaign_common as cc
    import order_effect
    import round_effect
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
        ("首轮劣势%", [round_effect.DEFAULT_WARMUP_PCT]),
        ("低于门默认", [validity_rollup.DEFAULT_MIN_RATE * 100]),
        ("样本 < `min_samples`", [cc.DEFAULT_MIN_SAMPLES]),
    ]

    sites = [ln for ln in lines if re.search(r"默认\s*\d", ln)]
    assert len(sites) == 7, (
        f"{len(sites)} numeric defaults in the README, 7 registered — a new "
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
        # 仓内可执行脚本不止 scripts/ 下一处：tools/e1 与 tools/e234 两套采集装置
        # 也被文档以「python tools/…」的仓根相对路径引用。此前只按 scripts/ 解析，
        # 于是每一条 tools/ 命令都被拼成 scripts/tools/… 而误报缺失——门会对着
        # **存在的**脚本喊不存在，比不查更糟（守卫说谎族，§2 红线）。
        if os.path.exists(os.path.join(REPO_ROOT, script)):
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


def test_the_shipped_grid_config_is_one_the_tool_accepts():
    """The Shenzhen grid stopped being a code block in a proposal and became a
    file an operator points the tool at (D-290). A config that only exists as
    prose is copied by hand; one that ships has to actually load.

    Three things, because each has a different failure: the keys are the ones
    coverage_matrix names (a plural key is rejected outright), the file carries
    no extra key (an unknown key makes the tool warn on every single run, and a
    config that always warns teaches the operator to ignore warnings — measured,
    a `_comment` key did exactly that), and the joint grid it declares is the
    size the proposal says it is.
    """
    import campaign_common as cc
    import coverage_matrix as cm

    path = os.path.join(REPO, "docs", "campaign_grid_shenzhen.json")
    assert os.path.exists(path), (
        "the shipped grid config is gone, but the proposal and runbook both "
        "send the operator to it")
    grid = cc.load_operator_json(path)
    assert set(grid) == set(cm.CELL_DIMS), (
        f"grid keys {sorted(grid)} vs the dimensions the tool reads "
        f"{sorted(cm.CELL_DIMS)} — anything extra warns on every run")
    for dim, values in sorted(grid.items()):
        assert isinstance(values, list) and values, (dim, values)
        assert all(isinstance(v, str) and v.strip() for v in values), (dim, values)

    joint = 1
    for dim in cm.CELL_DIMS:
        joint *= len(grid[dim])
    # D-345's "1 point x ctcc x busy" was the 07-31 PILOT round's fix, not a
    # permanent ceiling — D-432① (PO, 2026-08-03) locked the EXPANSION round's
    # three knobs at 6-8 points x dual carrier x busy/idle, and T33 shipped the
    # grid at the upper bound (8 points) so real names slot in without a second
    # resize. This assertion tracks whichever decision is CURRENT (D-301: a
    # changed decision must be re-transcribed everywhere it was quoted), not
    # D-345 specifically.
    assert joint == 32, (
        f"the shipped grid declares {joint} joint cells; D-432① (PO, 2026-08-03) "
        "locked the expansion round at 8 points x 2 carriers x 2 time bands = 32 "
        "(T33 grid prep)")


_TIER_CLAIM_MARKS = ("三级差分", "三层级", "三级归因")
_TIER_REALITY_MARKS = ("D-48", "单实例", "单层级")
# ⚠ 第二道判据（2026-08-30 收紧）：光有 `_TIER_CLAIM_MARKS` 不算「在讲部署三级」。
# 那三个词都能在**与部署无关**的意义上出现——最常见的是「**三级归因链**」
# （讲因果层级：观察→机制→结论），它含子串 `三级归因`，于是被判成在描述
# 同城/区域/中心三级部署，然后被要求贴一条与它毫不相干的 D-48 说明。
# 故再要求文中出现**部署层级本身的名字**。取值经实测标定：
#   · 原判据命中 15 份，加本条后 13 份；掉出的两份**本来就带着现实标记**
#     ⇒ 没有丢掉任何一份违规文档，纯削误报。
#   · 四个历史真阳（D-283/289/292/293）全部仍在命中集内。
#   · 再收一格（去掉 `metro`）会掉到 11 份，误杀两份**真的**在讲部署层级的
#     spec —— 故 `metro` 必须留。`core`/`regional` 是通用英文词，实测去掉
#     一份不少，所以不收进来（宁可判据窄，也别让通用词把门变松）。
_TIER_DEPLOYMENT_MARKS = ("同城", "metro", "三级部署", "镜像端")


def _claims_three_deployment_tiers(text):
    """这份文本是不是在把**三级部署分解**当成现行设计来讲。

    抽成函数是为了让下面那条**误报反例**能调**同一段代码** —— 反例要证的是
    生产判据本身放过了它，另写一份等价规则去对答案什么也证明不了。
    """
    return (any(m in text for m in _TIER_CLAIM_MARKS)
            and any(m in text for m in _TIER_DEPLOYMENT_MARKS))


def test_every_doc_asserting_three_tiers_also_carries_the_deployment_it_has():
    """Four documents in a row turned out to describe the three-tier
    decomposition as current design while D-48 had already cut the deployment to
    one instance: the grid proposal budgeted three times the trip (D-283), the
    deliverable skeleton taught a decomposition nobody can compute (D-289), the
    wiring spec and the annotator's convention offered a three-way tier choice
    with no servers behind two of them (D-292/D-293). Each was found by hand, one
    at a time, and the fifth would have been found the same way. This is that
    review written down as a criterion (D-294).

    Deliberately NOT reconciled against a declared "how many tiers are deployed"
    constant: no such constant exists, and inventing one would create a second
    thing to keep true — the trap this layer keeps finding. The rule is weaker
    and honest: describe the three-tier method as much as you like, but say in
    the same document what is actually deployed.
    """
    docs = os.path.join(REPO, "docs")
    claiming, offenders = 0, []
    for root, _dirs, files in os.walk(docs):
        for name in sorted(files):
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8-sig") as fh:
                text = fh.read()
            if not _claims_three_deployment_tiers(text):
                continue
            claiming += 1
            if not any(m in text for m in _TIER_REALITY_MARKS):
                offenders.append(os.path.relpath(path, REPO))
    assert claiming >= 8, (
        "only %d docs mention the three-tier decomposition — the scan probably "
        "broke, and a guard with nothing to check passes for the wrong reason"
        % claiming)
    assert not offenders, (
        "these docs describe the three-tier decomposition and never say what is "
        "deployed: %s — add the D-48 delta (a pointer is enough; the baseline "
        "plan keeps its own wording and carries one at the top). "
        "⚠ 若你这份文档里的「三级」根本不是**部署**三级（最常见的是"
        "「三级归因链」＝观察→机制→结论那种因果层级），那这是误报：判据要求"
        "同时出现部署层级名 %s 才算数，去看看是不是文中别处恰好提到了它们；"
        "别为了过门贴一条与本文无关的 D-48 说明。"
        % (offenders, list(_TIER_DEPLOYMENT_MARKS)))


def test_a_three_level_causal_chain_is_not_a_three_tier_deployment_claim():
    """误报反例：讲「三级归因链」的文档**不该**被要求交代部署形态。

    这条门原判据只看 `三级差分/三层级/三级归因` 三个词出不出现，于是任何
    「**三级归因链**」（观察→机制→结论那种因果层级）都会被判成在描述
    同城/区域/中心三级部署 —— 作者要么删掉一个正确的说法，要么贴一条
    与本文无关的 D-48 说明。**两种都是让门去污染它本该保护的东西。**

    ⚠ 本条调的是生产判据 `_claims_three_deployment_tiers` 本身，不是另写
    一份等价规则去对答案：后者只能证明我把规则抄对了两遍。

    正例一起放着，是为了防**反方向的坏修法**——把判据收到什么都不认，
    这条反例照样绿。一红一绿两头钉住，判据才动不了。
    """
    false_positive = (
        "本页给出**三级归因链**：观察 → 机制 → 结论。"
        "三层级的因果推理不可跳级，跳一级就会把「排除候选 A」读成「证成候选 B」。")
    assert not _claims_three_deployment_tiers(false_positive), (
        "「三级归因链」被当成了部署三级声明 ⇒ 门会逼作者贴无关的 D-48 说明")

    true_positive = (
        "部署：同城/区域/中心三级各一实例（镜像同一份），三级差分即归因输入。")
    assert _claims_three_deployment_tiers(true_positive), (
        "判据收得太紧：连点名同城/区域/中心镜像端的文本都不认了，"
        "这道门就再也拦不住 D-283 那类提案")

    # 第三例钉住 `metro`：实测把它从判据里拿掉，命中集会从 13 掉到 11，
    # 掉出的两份是**真的**在讲部署层级、只是全程用英文 tier 值的 spec
    # （`tier: metro / regional / core`）。它们逃出门去不会有任何报错。
    english_only = (
        '"tier": "metro" —— 服务层级取值，三级差分归因的输入字段。')
    assert _claims_three_deployment_tiers(english_only), (
        "只用英文 tier 值（metro）的部署 spec 不再被门认出 ⇒ 它们会静默逃逸")


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
            blocks = _QUOTES_BLOCK.findall(f.read())
        if not blocks:
            continue
        stem = os.path.splitext(os.path.basename(doc))[0]
        # findall, not search: one block per doc today, and a second one added
        # later would have been dropped without a word — the silent-drop path
        # this layer keeps finding, closed before it has anything to drop.
        for line in "\n".join(blocks).splitlines():
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
def _unverified_tiers_attr_md():
    """Three tier labels with no endpoint evidence — the shape the runbook warns
    a Shenzhen operator about, and the only one that raises this marker."""
    import attribution
    from synth import tier_records
    K = "n1_rtt_p50_ms"
    recs = (tier_records("metro", K, 20, 5) + tier_records("regional", K, 26, 5)
            + tier_records("core", K, 31, 5))
    return attribution.render_markdown(attribution.attribute(recs))


def _single_tier_attr_md():
    """The attribution section as the Shenzhen pilot will render it: one tier."""
    import attribution
    import synth_campaign as sc
    recs = sc.generate(points=2, repeats=5, tiers=("metro",), campaigns=("base",))
    return attribution.render_markdown(attribution.attribute(recs))


_QUOTE_RENDERERS = {
    "M2_CAMPAIGN_RUNBOOK.plan_verdict_short": _noisy_plan_md,
    "M2_CAMPAIGN_RUNBOOK.plan_col_power": _noisy_plan_md,
    "M2_CAMPAIGN_RUNBOOK.plan_col_breakeven": _noisy_plan_md,
    # the second pair, added when the power figure finally reached the page
    # (D-240) — the runbook had warned about 需 n≥ alone until then
    "M2_CAMPAIGN_RUNBOOK.plan_col_mde_power": _noisy_plan_md,
    "M2_CAMPAIGN_RUNBOOK.plan_col_mde_flat": _noisy_plan_md,
    "M2_CAMPAIGN_RUNBOOK.noise_marker": _within_noise_md,
    # The runbook tells the operator this marker must not appear in a Shenzhen
    # report, and what it means if it does (D-292). That instruction is only
    # worth anything while the tool still prints the string.
    "M2_CAMPAIGN_RUNBOOK.tier_unverified": _unverified_tiers_attr_md,
    "M2_REPORT_TEMPLATE.seg_anomaly_yes": _segment_profile_md,
    "M2_REPORT_TEMPLATE.seg_anomaly_no": _segment_profile_md,
    "M2_REPORT_TEMPLATE.seg_verdict_col": _segment_profile_md,
    "M2_REPORT_TEMPLATE.seg_spread_col": _segment_profile_md,
    # The skeleton's 分段归因 chapter is written for three tiers, and the pilot
    # has one. It now opens with what to write instead, keyed off the sentence
    # the section prints — so that sentence has to keep being printed (D-289).
    "M2_REPORT_TEMPLATE.tier_single": _single_tier_attr_md,
    # `repeats_reused` (both docs) was withdrawn with its column: the marker keyed
    # on `run.repeat_index`, which the contract defines only inside a scenario
    # and no producer writes at run level, so it could never fire on real data
    # (D-344). The contract scan below is what remains of that lesson.
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
        body = _QUOTES_BLOCK.sub("", text)   # every block, for the same reason
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


def _strip_quote(line):
    """剥掉 markdown 引用块前缀（`> ` / `   > `，可嵌套）——**表格照样是表格**。

    盲区实录（v2 交蓝本时点名，实测确认，2026-08-29）：本文件原来的
    `_looks_like_row` 要求行首就是 `|`，于是**引用块内的表**（协议/提案类文档里
    大量表格长这样）一行都没查过——仓内 61 行、4 个文件在盲区里，
    扫出 1 处真错（`PORTRAITS_TRISTATE_PROPOSAL_20260828.md:56`，2 格 vs 表头 3 格）。
    **「0 假阳性的检查器指错对象，照样一片假绿」**——这是 v2 自验 `check_tables.py`
    时得出的同一教训（它的 PATHS 从没含 `BRAIN_TASKBOARD.md`）。
    """
    prev = None
    while prev != line:
        prev = line
        line = re.sub(r"^\s*>\s?", "", line)
    return line


def _looks_like_row(line):
    s = _strip_quote(line).strip()
    return s.startswith("|") and s.endswith("|") and len(s) > 1


def _cells(line):
    """A row's cells. Splits on unescaped pipes only -- an escaped one is text.

    引用块前缀在这里也要剥（与 `_looks_like_row` 同一判据，否则新纳入的
    `> | a | b |` 会把 `> ` 当成第一格的内容而算错格数）。"""
    return re.split(r"(?<!\\)\|", _strip_quote(line).strip())[1:-1]


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
                # **缺行尾竖线的行曾被整行跳过**（v2 蓝本 ① 点名的第三类，
                # 实测真错一处：`PORTRAITS_TRISTATE_PROPOSAL_20260828.md:56`
                # 表内一行只写到 `| A-3 … | PO …` 就断了）。跳过=表内一行
                # 静默消失，而读者看到的是少一行的表——比格数不符更难发现。
                # 判据：正在一张表里（width 已定）且行首是 `|`，就该有行尾 `|`。
                # 表内一行首有 `|` 而尾无 ⇒ 该行**不会渲染进表**，读者看到的是
                # 少一行的表——比格数不符更难发现（格数不符至少还在表里）。
                # 落地实录（2026-08-29）：本判据实现时咬出两处真错，一处
                # （`M7_ANCHOR_RECALIBRATION_PLAN`）由本 lane 修（五处折行并回
                # 上一格，去空白字符数前后相同=零内容丢失），另一处属他人在建
                # 文件、曾用 `TRAILING_PIPE_OFF` 门控暂缓——**其后经实证是遗弃
                # 草稿并被属主删除**（真交付在 `spec/portraits/…20260829.md`），
                # 阻塞消失遂启用。门控惯例：被关的守卫必须留下解除路径与确切
                # 依赖，否则关闭态会变成永久债。
                s = _strip_quote(line).strip()
                if (width is not None
                        and s.startswith("|") and not s.endswith("|")):
                    orphans.append("%s:%d（行尾缺 `|`，该行不会渲染进表）"
                                   % (os.path.basename(doc), i + 1))
                width = None
                continue
            if width is None:
                # 同样要剥引用前缀：`> |---|---|` 是合法的分隔行，不剥就认不出
                # 表头，整张引用块内的表会被逐行报成孤行（本次扩盲区时实测撞到）。
                nxt = (_strip_quote(lines[i + 1]).strip()
                       if i + 1 < len(lines) else "")
                if not _DELIM.fullmatch(nxt):
                    # **孤行检查只对非引用块行生效**（实测收窄）：本仓惯用
                    # `> | 名 | 值 | 注 |` 把一行事实排成三栏，无表头也不打算
                    # 渲染成表——引用块内实测 7 处正规表 vs **47 处这类单行**，
                    # 一律判孤行会造 47 个假阳性，守卫会立刻失信。
                    # 引用块内因此只查「有表头的表」的格数一致性。
                    if line.lstrip().startswith(">"):
                        continue
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


def test_run_level_reads_stay_inside_the_result_contract():
    """Every run-level field the analysis layer reads must exist in the contract.

    D-340 built a whole column on `run.repeat_index` — a field the schema
    defines only inside a scenario (取证模式第几遍, 快测恒 0), which no producer
    writes at run level and 0 of 4822 real records carried there. On every real
    cell the column read 「0 个不同重复(+N 无编号)」: inert, and implying the
    operator forgot to number repeats (D-344). This scan would have caught it
    the day it was written.

    The allowed set is derived from the schema artifact, not hand-listed
    (D-275). `campaign` is the one reasoned exemption: the OPTIONAL labelling
    block lives in docs/CAMPAIGN_LABELS_CONVENTION.md §2.1, deliberately outside
    the schema's run.properties (additionalProperties admits it).

    Boundary (D-320, redrawn by D-364): three shapes are visible — the direct
    `run_obj(...).get("k")`, the inline raw-dict chain
    `(x.get("run") or {}).get("k")`, and a one-line alias assignment
    (`run = r.get("run") or {}` or `ro = run_obj(rec)`) followed by
    `alias.get("k")`. The first version claimed "no alias exists today
    (grepped)" — that grep covered only run_obj aliases, while the raw-dict
    shape already lived in dashboard/analyze_results/campaign_common (D-364).
    Still invisible: reads whose FIELD is a variable (`run.get(field)` looping
    over a tuple) — those field tuples cannot be resolved statically here, so
    a new one must bring its own contract check.
    """
    import json

    with open(os.path.join(REPO, "spec", "schemas", "result-run.schema.json"),
              encoding="utf-8-sig") as fh:
        schema = json.load(fh)
    allowed = set(schema["properties"]["run"]["properties"]) | {"campaign"}

    pat_direct = re.compile(r'run_obj\([^)]*\)\s*\.get\(\s*"([^"]+)"')
    pat_inline = re.compile(r'\.get\(\s*"run"\s*\)\s*or\s*\{\}\s*\)\s*\.get\(\s*"([^"]+)"')
    pat_alias = re.compile(
        r'^\s*(\w+)\s*=\s*(?:\(?\s*\w+(?:\[[^\]]+\])?\.get\(\s*"run"\s*\)\s*or\s*\{\}\s*\)?'
        r'|run_obj\([^)]*\))\s*$', re.M)
    hits, offenders = 0, []
    for name in sorted(os.listdir(SCRIPTS)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(SCRIPTS, name), encoding="utf-8-sig") as fh:
            src = fh.read()
        fields = [m.group(1) for m in pat_direct.finditer(src)]
        fields += [m.group(1) for m in pat_inline.finditer(src)]
        for m in pat_alias.finditer(src):
            alias = m.group(1)
            fields += [m2.group(1) for m2 in
                       re.finditer(rf'\b{re.escape(alias)}\.get\(\s*"([^"]+)"', src)]
        for field in fields:
            hits += 1
            if field not in allowed:
                offenders.append(f"{name}: run.{field}")
    assert hits >= 10, (
        f"only {hits} run-level reads found — the scan stopped seeing the "
        "shapes it knows, so its verdict means nothing")
    assert not offenders, (
        "run-level fields read but absent from the contract's run.properties "
        f"(the D-340 shape — a column built on a field nobody produces): "
        f"{offenders}")


# ── 跨文件节号引用：§N 真的存在于被引文件里吗（v2 提议，v3 落码）────────

_XREF_RE = re.compile(
    r"([A-Za-z0-9_./-]+\.md)`?\]?(?:\([^)]*\))?[ \u3000]*(?:`)?§ ?(\d+(?:\.\d+)*)")
_NUMBERED_HEADING_RE = re.compile(r"^#{1,6}\s*(?:§\s*)?(\d+(?:\.\d+)*)", re.M)


def _slurp(path):
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def _resolve_doc(src_path, target):
    """把引用里的相对/裸文件名解析到实际文件；解析不到返回 None。"""
    import glob as _glob
    for cand in (os.path.join(os.path.dirname(src_path), target),
                 os.path.join(REPO_ROOT, "docs", target),
                 os.path.join(REPO_ROOT, target)):
        if os.path.exists(cand):
            return cand
    hits = _glob.glob(os.path.join(REPO_ROOT, "**", os.path.basename(target)),
                      recursive=True)
    return hits[0] if len(hits) == 1 else None


def test_cross_file_section_references_point_at_sections_that_exist():
    """`X.md §N` 里的 §N 必须真的是 X.md 的一个小节——「见 X 的 X 存不存在」
    这条红线的节号版（v2 提议，同族于 test_documented_scripts_exist）。

    实例：基线曾把 E-4 归宿指向 `TEST_MASTER_PLAN §3`，而 E1–E4 实际在 §4。

    **量法比缺陷更容易错，这里踩过两次**：①文件名与 § 之间隔着别的词时粗匹配
    会张冠李戴（故只认紧邻）；②目标文件的小节**根本不编号**时（如
    `spec/README.md`），「§3」是「第 3 个小节」的序数写法，按数字比会把 14 处
    正确引用全判成红——故这类目标显式豁免，并把豁免数打印出来（不静默跳过）。
    """
    bad, exempt_unnumbered, unresolved = [], 0, 0
    for doc in DOCS:
        text = _slurp(doc)
        for m in _XREF_RE.finditer(text):
            target, sec = m.group(1), m.group(2)
            path = _resolve_doc(doc, target)
            if path is None:
                unresolved += 1          # 目标文件本身找不到：另一条守卫的地盘
                continue
            secs = set(_NUMBERED_HEADING_RE.findall(_slurp(path)))
            if not secs:
                exempt_unnumbered += 1
                continue
            if sec not in secs:
                bad.append("%s 引 %s §%s，但该文件的编号小节只有 %s"
                           % (os.path.basename(doc), target, sec,
                              "、".join(sorted(secs)[:8])))
    print("  xref: 豁免(目标不编号) %d，目标未解析 %d" % (exempt_unnumbered,
                                                        unresolved))
    assert not bad, "跨文件节号引用指向不存在的小节：\n  " + "\n  ".join(bad)


_SAMEFILE_REF_RE = re.compile(r"见 §\s*(\d+(?:\.\d+)*)")


def test_same_file_section_references_point_at_sections_that_exist():
    """「见 §N」（无文件名 ⇒ 指本文）里的 §N 必须真的是本文的一个小节。

    补的是跨文件那条守卫的**盲区**：它只查 `X.md §N`，而实际悬空引用出现在
    同文件内（实例：基线里一条「见 §5.5」，该文件无 §5.5，`cd1e5c4` 修的）。

    **两类必须排掉，否则全是假阳性**（都实测撞到过）：
    ①紧跟在 `X.md` 之后的 —— 那是跨文件引用，另一条守卫的地盘；
    ②**引号内「将来要写进别处的原话」** —— M3 增补有张「改哪/改成什么」表，
      格子里写着要往 runbook 加的句子「…扩展轮见 §0.7」，指的是 **runbook** 的节，
      不是本文的（v2 在跨文件版里踩过的同一类：把「计划新增的节」当成「引用现有节」）。
      判据：该行提到了另一个 `.md` 文件名。
    """
    bad, exempt = [], 0
    for doc in DOCS:
        text = _slurp(doc)
        secs = set(_NUMBERED_HEADING_RE.findall(text))
        if not secs:
            exempt += len(_SAMEFILE_REF_RE.findall(text))
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            # 排除②：**行级判据够不到表级语境**——实测那句「…见 §0.7」所在的
            # 表格行自己不含 .md，文件名写在同表的上一行（「改哪」列）。故看
            # 前后各 3 行的窗口：窗口内提到别的 .md ⇒ 这段在谈别的文件。
            window = "\n".join(lines[max(0, i - 3):i + 4])
            if ".md" in window:
                continue
            for m in _SAMEFILE_REF_RE.finditer(line):
                if m.group(1) not in secs:
                    bad.append("%s 写「见 §%s」，但本文的编号小节只有 %s"
                               % (os.path.basename(doc), m.group(1),
                                  "、".join(sorted(secs)[:8])))
    print("  same-file xref: 豁免(本文不编号) %d" % exempt)
    assert not bad, "同文件节号引用悬空：\n  " + "\n  ".join(bad)


# BASELINE §5 rule 6：「**行号也不写死**……引用他文一律给『节号 + 可搜索的锚
# 文字』，**不给行号**」。此前无守卫（T82 §9.2 #10）。
# **冻结现存 31 处、只能缩不能长**：它们多在 `DECISION_LOG.md` 这类**追加式历史
# 账**里，那种条目是带时间戳的记述，改写等于篡改记录——所以这条规则**不能追溯**，
# 只能拦新增。清偿一条（改成节号+锚文字）就把它从清单删掉，否则本守卫会红。
_FROZEN_LINE_REFS = frozenset([
    "docs/BRAIN_TASKBOARD.md -> INSTRUMENTATION_SPEC.md:447",
    "docs/BRAIN_TASKBOARD.md -> tools/e234/README.md:109",
    "docs/DECISION_LOG.md -> INSTRUMENTATION_SPEC.md:447",
    "docs/DECISION_LOG.md -> JUDGMENT_v3.md:89",
    "docs/DECISION_LOG.md -> M3_EXPANSION_ROUND_GUARD_DIFF.md:103",
    "docs/DECISION_LOG.md -> PROFILE_FRAMEWORK.md:367",
    "docs/DECISION_LOG.md -> docs/launchpad/README.md:34",
    "docs/DECISION_LOG.md -> docs/launchpad/crosscut-device-unlock-udp-contend-runbook.md:49",
    "docs/DECISION_LOG.md -> evidence/m3_expansion_rehearsal_20260801/README.md:192",
    "docs/DECISION_LOG.md -> report_snapshot.md:202",
    "docs/DECISION_LOG.md -> spec/adapters/INSTRUMENTATION_SPEC.md:447",
    "docs/DELIVERY_PACKAGE_AUDIT_FINDINGS_20260820.md -> DECISION_LOG.md:506",
    "docs/E01_DEPLOY_REQUEST_FOR_CODEX_20260804.md -> docs/launchpad/README.md:34",
    "docs/E01_DEPLOY_REQUEST_FOR_CODEX_20260804.md -> docs/launchpad/crosscut-device-unlock-udp-contend-runbook.md:49",
    "docs/M3_EXPANSION_ROUND_RUNBOOK_ADDENDUM.md -> M3_EXPANSION_ROUND_GUARD_DIFF.md:103",
    "docs/M3_EXPANSION_ROUND_RUNBOOK_ADDENDUM.md -> evidence/m3_expansion_rehearsal_20260801/README.md:192",
    "docs/M7_RECALIBRATION_INDEPENDENT_VERIFICATION_20260819.md -> T55_M7_SCORING_CHAIN_VERIFICATION_20260805.md:120",
    "docs/PLAN_ALIGNMENT_2026-07-17.md -> RADIO_CONTEXT_WIRING_SPEC.md:37",
    "docs/PROFILE4_VOICE_LOOPBACK_SPEC.md -> RADIO_CONTEXT_WIRING_SPEC.md:37",
    "docs/PROFILE4_VOICE_LOOPBACK_SPEC.md -> RADIO_CONTEXT_WIRING_SPEC.md:63",
    "docs/PROFILE4_VOICE_LOOPBACK_SPEC.md -> SYSTEM_DEV_PLAN_v1.0.md:50",
    "docs/PROFILE4_VOICE_LOOPBACK_SPEC.md -> spec/README.md:60",
    "docs/T14_CROSS_AUDIT_20260801.md -> DECISION_LOG.md:63",
    "docs/T50_VOICE_FIRST_COLLECTION_PROTOCOL_20260804.md -> docs/BRAIN_TASKBOARD.md:60",
    "docs/T50_VOICE_FIRST_COLLECTION_PROTOCOL_20260804.md -> docs/PROFILE4_VOICE_LOOPBACK_SPEC.md:33",
    "docs/T50_VOICE_FIRST_COLLECTION_PROTOCOL_20260804.md -> docs/PROFILE4_VOICE_LOOPBACK_SPEC.md:471",
    "docs/VOICE_ANALYSIS_LAYER_INVENTORY.md -> MEASUREMENT_CAMPAIGN_2026-07-17.md:30",
    "docs/VOICE_ANALYSIS_LAYER_INVENTORY.md -> PROFILE4_VOICE_LOOPBACK_SPEC.md:19",
    "evidence/e1_window_narrative_review_20260802.md -> JUDGMENT_v3.md:89",
    "evidence/nr_timeline_20260802/T37_E2_COLLECTION_PROTOCOL_20260803.md -> "
    "docs/launchpad/crosscut-device-unlock-udp-contend-runbook.md:261",
])

_LINE_REF = re.compile(r"([\w./\-]+\.md):(\d+)")



# 外部 lane 的归档件：`docs/coordination/` 是协调侧（另一条 lane）的文档，按 M-B-011⑤ 一次性并入主线作归档，
# **不是本仓起草的文档**——其跨文件行号引用与 D 号引用都指向协调侧自己的语境（它有自己的裁定编号体系），
# 故 rule 6 与「每个被引 D 号须在 DECISION_LOG 解析」两条守卫对它不适用（裁定见 DECISION_LOG 2026-09-05 PR #4 条）。仅此一目录，不做通配。
_EXTERNAL_LANE_DIRS = ("docs" + os.sep + "coordination",)


def _under_external_lane(path):
    rel = os.path.relpath(path, REPO).replace("/", os.sep)
    return any(rel == d or rel.startswith(d + os.sep) for d in _EXTERNAL_LANE_DIRS)

def _all_line_refs():
    """全仓 .md 的跨文件行号引用集合。

    **按 `REPO` 绝对根走 `os.walk`，不用 cwd 相对 glob**：门跑
    `run_all.py` 的工作目录是 `scripts/tests/`，pytest 是仓根——初版用了
    `glob("**/*.md")`，两处会扫出完全不同的集合而各自「通过」。房子里既有
    测试一律用 `REPO`，正是为此。
    """
    found = set()
    for root, dirs, files in os.walk(REPO):
        if _under_external_lane(root):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            if not f.endswith(".md"):
                continue
            p = os.path.join(root, f)
            norm = os.path.relpath(p, REPO).replace(os.sep, "/")
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    txt = fh.read()
            except OSError:
                continue
            for m in _LINE_REF.finditer(txt):
                found.add("%s -> %s:%s" % (norm, m.group(1), m.group(2)))
    return found


def test_the_manifest_is_generated_after_the_badges_it_describes():
    """`sha256-manifest.txt` 必须在 `badges.txt` **之后**生成——否则它永远记旧值。

    实测成因（2026-08-30，D-612）：原顺序是先写清单、后跑 `badges.py`
    ⇒ 写清单那一刻 badges.txt 还是**上一跑**那份 ⇒ **清单里 badges 的哈希从未对过一次**
    （0/2：首跑该文件还不存在被漏收，此后每次归档跑都记成陈旧值）。
    比特级实证：清单记的值 ＝ 拿上一次归档日志重跑 `badges.py` 得到的字节。

    **它能活到今天是因为清单没有读者**——全仓无任何守卫回读它。本条即那个缺席的读者。
    ⚠ 判据是**顺序**，不是「这次哈希对上了没有」：徽章那步没跑时清单反而相符，
    **「相符」不是健康信号**。顺序是唯一能静态查、且不依赖某一次跑的判据。

    ⚠ **用字符串锚，不用行号**（本仓明令；且当天实测过一次行号漂移：
    四路调查引的 706/720 全来自未提交的工作区，HEAD 其实是 695/709）。
    """
    with open(os.path.join(REPO, "scripts", "verify_all.ps1"),
              encoding="utf-8") as fh:
        text = fh.read()
    badge_call = text.find("& $py $badgeScript")
    badge_else = text.find("badges: NOT_EXECUTED")
    manifest_write = text.find("Out-File -Encoding utf8 $manifestPath")
    assert badge_call > 0, "找不到徽章调用锚 `& $py $badgeScript`"
    assert badge_else > 0, "找不到徽章 else 分支锚 `badges: NOT_EXECUTED`"
    assert manifest_write > 0, "找不到清单写入锚 `Out-File ... $manifestPath`"
    assert badge_call < manifest_write, (
        "清单写在了徽章之前 ⇒ 它会永久记录上一跑的 badges.txt 哈希（D-612）")
    # 清单还必须落在徽章 if/else **之外**：else 分支里那句在清单之前，
    # 说明清单不在任一分支内部——徽章没刷新时清单照样要记录真实现态。
    assert badge_else < manifest_write, (
        "清单似乎被并进了徽章的 if 分支 ⇒ 徽章未执行时清单不会刷新（D-612）")


def _verify_all_text():
    with open(os.path.join(REPO, "scripts", "verify_all.ps1"),
              encoding="utf-8") as fh:
        return fh.read()


def _verify_all_code():
    """verify_all.ps1 去掉整行注释后的**代码行列表** —— 「有没有在用」问代码，别问全文。

    ⚠ 这个辅助函数是被一次**真误报**逼出来的（2026-08-30，T89）：下面那条
    「不许再按文件名排除自身」的守卫第一次就咬中了 verify_all.ps1 里
    **解释旧写法为什么错的那句注释**。判据落在「文本里提到 X」而不是
    「代码里在用 X」，就会让**记录一个缺陷的行为本身**变成那个缺陷的证据。

    只剥整行注释（首个非空字符是 `#`）——不处理 `<# #>` 块注释，也不处理
    字符串内部的 `#`。对本文件的用法够了；若哪天要更严，得上真解析器。
    """
    return [line for line in _verify_all_text().splitlines()
            if not line.lstrip().startswith("#")]


def test_the_manifest_excludes_itself_by_path_and_not_by_file_name():
    """清单排除自身必须按**全路径**，不能按 `.Name`。

    实测反例（2026-08-30，T89，合成夹具跑过、非推断）：那一句带着 `-Recurse`，
    于是 `$_.Name -ne 'sha256-manifest.txt'` 会把**任何子目录里的同名文件**
    一并静默排除。同一夹具上旧写法收 4 条、新写法收 5 条，
    差的正是 `sub/sha256-manifest.txt` —— **不报错、不留痕**。
    """
    # ⚠ 用 **去注释后**的代码判，否则解释旧写法的那句注释会自己咬自己（见 _verify_all_code）
    code = _verify_all_code()
    assert not any("$_.Name -ne 'sha256-manifest.txt'" in ln for ln in code), (
        "清单又改回按文件名排除自身了 ⇒ 子目录同名文件会被静默漏收（T89）")
    assert any("$_.FullName -ne $manifestPath" in ln for ln in code), (
        "找不到按全路径排除清单自身的锚 `$_.FullName -ne $manifestPath`")


def test_the_manifest_excludes_ignored_files_and_fails_to_the_safe_side():
    """清单排除 gitignored 文件时，git 判不出来必须朝**不排除**那侧倒。

    背景（T89(b)）：清单 314 条里 297 条是 verify_all 自己的运行日志，
    其中 20 条未跟踪、只在本机存在 ⇒ 留着会让**清单内容变成「本机跑过多少次」的函数**。
    判据必须是 check-ignore 语义（未跟踪 **且** 被忽略）：只用「未跟踪」会连
    刚产生、马上要入库的证据文件一起丢掉。

    ⚠ 本条真正守的是**失败方向**：`& git` 在 git 缺失时**不会**把 $LASTEXITCODE
    置非零，它留着上一条命令的值；若那值恰好是 0，代码会拿一个空集合走进
    「已排除」分支并**宣称排除过**。故须有 `Get-Command git` 前置探测
    ＋ 哨兵预置。实测：对一个非仓库目录跑，gitOk=False（朝不排除倒）。
    """
    text = _verify_all_text()
    assert "ls-files --others --ignored --exclude-standard" in text, (
        "清单不再用 check-ignore 语义筛 gitignored 文件（T89(b)）")
    assert "Get-Command git -ErrorAction SilentlyContinue" in text, (
        "少了 git 存在性前置探测 ⇒ git 缺失时会拿空集合冒充『已排除』（T89(b)）")
    assert "$global:LASTEXITCODE = 99" in text, (
        "少了 $LASTEXITCODE 哨兵预置 ⇒ 会误读上一条命令的退出码（T89(b)）")
    # ⚠ 必须是 `$global:`。首跑实测：裸写会在脚本作用域新建局部变量遮住全局，
    # 而 `& git` 写的是全局那个 ⇒ 读回来永远是哨兵值、排除功能**整个静默失效**。
    assert not any(ln.strip() == "$LASTEXITCODE = 99" for ln in _verify_all_code()), (
        "哨兵写成了局部 `$LASTEXITCODE = 99` ⇒ 它遮住 `& git` 写的全局变量，"
        "gitOk 永远 false、gitignored 排除整条路静默失效（T89(b) 首跑实测）")


def test_the_manifest_declares_what_it_is_without_writing_a_count_into_itself():
    """清单必须自述「本机 checkout 形态快照」，且表头里**不许写条数**。

    自述是为了改掉一个错误的第一反应：哈希对不上时先怀疑内容被改，
    而最常见的真因是**行尾形态**（本机 core.autocrlf/.gitattributes 决定）。

    ⚠ 表头写条数会**每跑一次变一次**，正好抵消掉排除 gitignored 是为了消 churn
    这件事本身 —— 条数走 stdout，不进文件。（本仓旧教训：索引里别写计数。）
    """
    text = _verify_all_text()
    start = text.find("$mhdr = @(")
    assert start > 0, "找不到清单表头锚 `$mhdr = @(`"
    end = text.find(")", text.find("行格式：", start))
    header = text[start:end]
    assert "本机 checkout 形态快照" in header or "本机 checkout 的形态快照" in header, (
        "清单表头不再自述它是本机 checkout 形态快照（T89(a)）")
    for token in ("$skipped", "$mlines.Count", "$($mlines"):
        assert token not in header, (
            "清单表头里出现计数变量 %s ⇒ 清单会每跑一次变一次（T89(a)）" % token)


def test_the_run_log_name_carries_the_pid_and_still_sorts_by_time():
    """运行日志名必须带 PID，且带了之后仍要按时间排得对。

    成因（T89(d)）：`$ts` 原本只有秒级 `yyyyMMdd-HHmmss`，**无进程区分**
    ⇒ 同一秒起跑的两个 verify_all **共用同一个 $logPath 互相覆盖**，且不报错。
    本树是共享工作树、同刻常有多个会话在跑门，这不是理论风险。

    ⚠ 改名会牵动两个下游，本条把它们都算一遍（不是断言，是真跑）：
    ①`.gitignore` 的 `verify_all_*.log`；②`badges.py:latest_log` 取
    `sorted(glob(...))[-1]` ＝ **字典序**。时间戳是定宽前缀，故跨时间戳仍正确；
    同秒内先后由 PID 字符串决定（"9999" > "10000"）——**那是任意的**，
    但 verify_all 总是显式把 $logPath 传给 badges.py，latest_log 只是手工兜底。
    """
    import fnmatch
    text = _verify_all_text()
    assert "$PID" in text, "运行日志名不再带 PID ⇒ 同秒并发会互相覆盖（T89(d)）"
    assert "Get-Date -Format 'yyyyMMdd-HHmmss'" in text, (
        "时间戳格式变了；`latest_log` 的字典序排序依赖它是**定宽前缀**（T89(d)）")
    # 下游①：新名字仍要落进 .gitignore 的模式
    newname = "verify_all_20260830-235959-12345.log"
    assert fnmatch.fnmatch(newname, "verify_all_*.log"), (
        "带 PID 的日志名不再匹配 .gitignore 的 verify_all_*.log")
    with open(os.path.join(REPO, ".gitignore"), encoding="utf-8") as fh:
        assert "evidence/phase0/verify_all_*.log" in fh.read(), (
            ".gitignore 里那条 verify_all_*.log 规则不见了（T89(d) 依赖它）")
    # 下游②：跨时间戳的字典序必须仍等于时间序，即使 PID 位数不同
    names = [
        "verify_all_20260830-235959-99999.log",   # 早，PID 大
        "verify_all_20260831-000000-1.log",       # 晚，PID 小
    ]
    assert sorted(names)[-1] == names[1], (
        "带 PID 后按名排序不再等于按时间排序 ⇒ badges.py:latest_log 会取错日志")


def test_no_new_cross_file_line_number_references():
    """BASELINE §5 rule 6：引他文给节号+锚文字，**不给行号**——行号会悄悄漂。

    **只拦新增、不追溯**：现存 31 处多在追加式历史账里，改写等于篡改记录。
    清单只能缩：清偿一条就删一条，否则下面那半会红。

    **刻意不建「行号越界即报烂」那条检查**，理由是实测：31 处里唯一越界的
    `DECISION_LOG.md -> PROFILE_FRAMEWORK.md:367` **不是烂指针**——那条 D 记录
    记的是一次突变审计，它故意在该文件末尾植入一行、守卫报出 `:367`，还原后
    文件回到 365 行。那是对工具当时输出的**忠实引用**。即该检查在本仓战绩为
    **0 真阳性 / 1 假阳性**，而失信的守卫等于没有（§2.10 同族）。
    反例证伪：在任一 .md 里新写一处 `FOO.md:123`，本条即红。
    """
    found = _all_line_refs()
    new = sorted(found - _FROZEN_LINE_REFS)
    assert not new, (
        "新增了跨文件行号引用（BASELINE §5 rule 6 禁止）：%s\n"
        "改成「节号 + 可搜索的锚文字」；行号会随他人编辑悄悄漂掉。" % new)


def test_frozen_line_reference_exemptions_expire_when_paid_off():
    """冻结清单**只能缩不能长**：清偿后那条要反过来推红，逼人删掉它。

    否则清单会永远留着，把「已经改好的」和「还欠着的」混在一起，
    而读者无从知道到底还欠几条（D-275 让豁免天然落选）。
    反例证伪：把任一条改成节号+锚文字却不删清单条目，本条即红。
    """
    stale = sorted(_FROZEN_LINE_REFS - _all_line_refs())
    assert not stale, (
        "以下行号引用已不存在，请从 _FROZEN_LINE_REFS 删掉（豁免不得长留）：%s"
        % stale)


def test_every_path_literal_in_verify_all_resolves():
    """`verify_all.ps1` 里每个仓相对路径字面量都必须真指得到东西。

    **这条是被一个活了很久的真 bug 逼出来的**：`$badgeScript = Join-Path $repo
    'scripts…badges.py'` 里的「反斜杠-b」在落盘时被吞成**一个真实退格符 0x08**
    （heredoc 转义坑），于是 `Test-Path` 恒 False；而当时那个 `if` **没有 else**，
    这条接线自 `3a1577a` 起**一次都没跑过、也一次都没吭声**，`badges.txt`
    因此从不存在。更毒的是 **grep 与编辑器都把退格符渲染没了**——肉眼、
    `grep 'badges'`、Read 全都看不出异常，所以它躲过了所有人工复核。

    机器查得到，人查不到：这正是该有守卫的那类。顺带禁掉整类不可见控制字符。
    反例证伪：把任一路径字面量改成不存在的名字，本条即红。
    """
    p = os.path.join(REPO, "scripts", "verify_all.ps1")
    with open(p, encoding="utf-8", newline="") as fh:
        src = fh.read()
    ctrl = sorted(set(hex(ord(c)) for c in src
                      if ord(c) < 32 and c not in "\n\r\t"))
    assert not ctrl, (
        "verify_all.ps1 含不可见控制字符 %s——它们在 grep/编辑器里看不见，"
        "却能把路径字面量悄悄改掉（0x08 实例见本条 docstring）" % ctrl)

    bad = []
    for lit in re.findall(r"Join-Path \$repo '([^']+)'", src):
        rel = lit.replace("\\", os.sep).replace("/", os.sep)
        target = os.path.join(REPO, rel)
        if "*" in rel:                      # glob：查它的父目录在不在
            target = os.path.dirname(target)
        if not os.path.exists(target):
            bad.append(lit)
    assert not bad, (
        "verify_all.ps1 里这些路径字面量指不到东西：%s\n"
        "——一条指不到脚本的门会静默跳过，而静默跳过与「跑过且通过」"
        "在输出上一模一样（D-532）。" % bad)


# DECISION_LOG 开篇：「推翻旧决策时新增条目并**引用被推翻的 D-xx**」。
# 引用要能解析——一个指向不存在裁定的 D 号，读者追不到、也无从知道自己追丢了。
# 每条豁免都带**它为什么合法**：一份没有理由的冻结清单就是一堆无理由的赦免。
_D_REF_EXEMPT = {
    "D-1": "零填充写法：日志定义的是 `D-01`，同一条裁定",
    "D-2": "同上，`D-02`",
    "D-177": "**已知跳号**，且引用方自己写明「D-177 从未写入日志——号被跳过，D-364」",
    "D-375": "**已知空号**，板面明记「6-6/6-7 至今零 D 号入册、两处引用空号 D-375」",
    "D-564a": "D-564 的子项编号，见该条正文，非独立行",
    # ⚠ D-700 已于 2026-09-04 被真实编号追上（入册为自审两个 high 的处置条目），故本行撤销。
    #    这些示例号出自 worktree 隔离提案的「**如**按百位分段 v2=D-700..799」——「如」字表明是举例、
    #    是虚指；真实编号单调推进，被追上是必然的。后来人照此处理：真实条目一入册就删掉对应行
    #    （test_decision_number_exemptions_are_still_needed 会当场点名要求删，不必自己记）。
    # D-705 已于 2026-09-05 被真实编号追上（A-6 通道 A 开回），示例号豁免撤销；后续 D-800/803/900 同理。
    "D-800": "同上",
    "D-803": "同上",
    "D-900": "同上",
}

_D_DEF = re.compile(r"^[|] (D-[0-9]+[a-z]?) [|]", re.M)
_D_CITE = re.compile(r"D-([0-9]+)([a-z]?)")
_D_SCAN_EXT = (".md", ".py", ".ps1", ".kt", ".go")


def test_every_cited_decision_number_resolves():
    """全仓引用的每个 `D-号` 都要在 DECISION_LOG 里找得到条目。

    **实测抓到九处真悬空**（本条落地即修）：`campaign_report.py`/`stability.py`/
    `test_provenance.py`/runbook 增补把 `D-382` 写成了转位号「三七八」——那条裁定
    「`SCENARIO_INTRINSIC_JITTER` 三面落地」正是它们描述的判别量来源；同一个错号
    顺着注释惯例扩散到四个文件。**这里刻意把错号写成中文而不是原样敲出来**：
    描述一个悬空引用不该制造一个新的悬空引用（同「表格里写『竖线』二字」那条规矩）。
    生产注释里一个指错的 D 号，读者会追到一条**根本不存在**的裁定上，
    而「追不到」与「我搜错了」在体感上一模一样。

    豁免清单每条自带理由（见 `_D_REF_EXEMPT`），且**只做加白不做兜底**：
    新的悬空号一律红。
    反例证伪：把任一 D 号改成不存在的号，本条即红。
    """
    log = open(os.path.join(REPO, "docs", "DECISION_LOG.md"),
               encoding="utf-8", errors="replace").read()
    defined = set(_D_DEF.findall(log))
    assert len(defined) > 400, "定义集异常小（%d）——多半是量法坏了，不是日志空了" % len(defined)

    cited = {}
    for root, dirs, files in os.walk(REPO):
        if _under_external_lane(root):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "build")]
        for f in files:
            if not f.endswith(_D_SCAN_EXT):
                continue
            p = os.path.join(root, f)
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    txt = fh.read()
            except OSError:
                continue
            rel = os.path.relpath(p, REPO).replace(os.sep, "/")
            for m in _D_CITE.finditer(txt):
                cited.setdefault("D-" + m.group(1) + m.group(2), set()).add(rel)

    dangling = sorted(set(cited) - defined - set(_D_REF_EXEMPT),
                      key=lambda d: int(d[2:].rstrip("abcdefghij")))
    assert not dangling, "\n".join(
        ["以下 D 号被引用但 DECISION_LOG 里没有对应条目："]
        + ["  %s ← %s" % (d, sorted(cited[d])[:4]) for d in dangling]
        + ["若确属合法（跳号/预留号/子项），加进 _D_REF_EXEMPT 并写明理由。"])


def test_decision_number_exemptions_are_still_needed():
    """豁免会自己过期：某个号后来真被写进日志，就该从清单里删掉。

    否则清单会掩盖「这个号现在有主了」，下一个读者仍以为它是空号。
    反例证伪：把一个已定义的号加进 _D_REF_EXEMPT，本条即红。
    """
    log = open(os.path.join(REPO, "docs", "DECISION_LOG.md"),
               encoding="utf-8", errors="replace").read()
    defined = set(_D_DEF.findall(log))
    stale = sorted(set(_D_REF_EXEMPT) & defined)
    assert not stale, (
        "以下号已在日志里有条目，请从 _D_REF_EXEMPT 删掉：%s" % stale)


# spec/README 严格 loader 通则（D-397）自承的缺口，T82 §9.2 #5：
# 「『仓内 spec loader 皆严格』这句话本身没有任何东西核对它——新增第三个严格
# loader 时，上表不会自己长出一行。应有的形态：扫 app/**/*.kt 里 `= Json` 的
# 默认实例，与上表对账（清单从产物导出而非手写，D-329）。」本条即那个形态。
# **两侧都从产物导出**：一侧是源码里的实例，另一侧是 README 表格自己的行——
# 我不在这里手抄一份 loader 清单，那样就又造了一个会漂的第三方真相源。
_BARE_JSON = re.compile(r"=\s*Json\s*(?:$|[^\s{])", re.M)
_ANY_JSON = re.compile(r"=\s*Json\b")
_TABLE_KT = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*\.kt)(?::\d+)?`")


def _main_kotlin_files():
    out = []
    for root, dirs, files in os.walk(os.path.join(REPO, "app")):
        dirs[:] = [d for d in dirs if d not in ("build", ".gradle")]
        if os.sep + "test" + os.sep in root + os.sep:
            continue                        # 测试里的 Json 不是 loader
        for f in files:
            if f.endswith(".kt"):
                out.append(os.path.join(root, f))
    return sorted(out)


def test_strict_json_loaders_reconcile_with_the_spec_readme_table():
    """`app/` 主源里每个**严格**（裸 `Json`）实例都要在 spec/README 的表上，反之亦然。

    严格实例＝未知键即抛＝**能发现 schema 漂移的那种 loader**；宽松实例
    （`Json { ignoreUnknownKeys = true }`）解析的是网络载荷，宽松在那里站得住，
    故不入表也不判违规——**判据是消费方，不是关键字**（同 D-276）。

    两个方向都要查，且**反方向更危险**：有人把某个 loader 从裸 `Json` 改成宽松，
    而表还写着「严格」——那时表不是缺一行，是**在说谎**。

    实测（2026-08-29）：主源 9 个实例里裸的恰好 2 个（`AdapterSpec.kt`、
    `TestModeProfileLoader.kt`），与表逐一对上；另 7 个宽松的均为 SSE/API/服务端
    响应解析（含 `ProfileParser`——它读 `/api/v1/profiles` **响应**而非盘上 spec，
    是另一个信任边界，**诚实的否定**）。
    反例证伪：新增一个裸 `Json` 而不改表，或把表上某个改成宽松，本条即红。
    """
    readme = os.path.join(REPO, "spec", "README.md")
    with open(readme, encoding="utf-8", errors="replace") as fh:
        doc = fh.read()
    table_files = set()
    for line in doc.split("\n"):
        if not line.lstrip().startswith("|") or "= Json" not in line:
            continue
        # **只取第一格（loader 列）**：初版按整行抓 .kt，把「证据强度」列里引的
        # 测试文件（AdapterSpecTest.kt 等）也当成了 loader，守卫当场假红。
        # 一行里出现的文件名不等于这一行在讲的那个文件。
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells:
            table_files.update(_TABLE_KT.findall(cells[0]))
    assert table_files, "spec/README 里没解析出 loader 表——判据缺失即报错，不放行"

    strict, lenient = {}, {}
    for p in _main_kotlin_files():
        with open(p, encoding="utf-8", errors="replace") as fh:
            txt = fh.read()
        if not _ANY_JSON.search(txt):
            continue
        (strict if _BARE_JSON.search(txt) else lenient)[os.path.basename(p)] = p

    missing = sorted(set(strict) - table_files)
    assert not missing, (
        "以下文件有**严格** `= Json` 实例却不在 spec/README 的 loader 表上：%s\n"
        "——表漏一行，就等于「仓内 spec loader 皆严格」这句话少了一个受检对象。"
        % missing)

    no_longer_strict = sorted(f for f in table_files if f not in strict)
    assert not no_longer_strict, (
        "spec/README 的表把以下文件列为严格 loader，但它们主源里已无裸 `Json`：%s\n"
        "——表不是缺一行，是**在说谎**：读者会以为未知键仍会被拒。" % no_longer_strict)


# --- 下面这条守卫的判定逻辑抽成函数，是为了让它的每个分支都能被**合成源码**证明 ---
# ⚠ 抽出来的直接原因：突变审计在仓内扫描形态下判了两条分支 SURVIVED
# （「退回只查 encoding=」「不认裸导入」）——**不是守卫弱，是方法固有**：
# 仓一旦全合规，「拿掉检查」与「存在违规」只能联合观测，单独拿掉检查测不出来。
# 抽成函数后就能喂合成源码，把两条分支各自钉住。
# （本仓规矩：为某判断写了一条分支 ≠ 那分支在承重。）
def _text_mode_subprocess_offenders(source, label):
    """返回 source 里「文本模式抓子进程输出却没钉住解码」的调用清单。

    判据两件都要：`encoding=` ＋ 非 strict 的 `errors=`。理由见调用方 docstring。
    认两种调用形态：`subprocess.run(...)` 与 `from subprocess import run` 后的裸 `run(...)`。
    """
    import ast
    CAPTURING = ("run", "check_output", "Popen")
    TEXT_KEYS = ("text", "universal_newlines")
    try:
        tree = ast.parse(source, filename=label)
    except SyntaxError:
        return [], 0
    aliased = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            aliased |= {a.asname or a.name for a in node.names if a.name in CAPTURING}
    offenders, seen_calls = [], 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        attr_form = (isinstance(fn, ast.Attribute) and fn.attr in CAPTURING
                     and isinstance(fn.value, ast.Name) and fn.value.id == "subprocess")
        bare_form = isinstance(fn, ast.Name) and fn.id in aliased
        if not (attr_form or bare_form):
            continue
        called = fn.attr if attr_form else fn.id
        kw = {k.arg: k.value for k in node.keywords if k.arg}
        if not any(k in kw for k in TEXT_KEYS):
            continue              # 字节模式安全：bytes 不会解码失败
        seen_calls += 1
        missing = []
        if "encoding" not in kw:
            missing.append("encoding=")
        err = kw.get("errors")
        if err is None:
            missing.append("errors=")
        elif isinstance(err, ast.Constant) and err.value == "strict":
            # 只查「有没有 errors=」的话，一行 errors="strict" 就能哄过守卫
            missing.append('errors= 不许是 "strict"')
        if missing:
            offenders.append("%s:%d %s（缺 %s）"
                             % (label, node.lineno, called, "、".join(missing)))
    return offenders, seen_calls



def test_no_captured_subprocess_leaves_its_decoding_to_the_locale():
    """凡以文本模式抓子进程输出，必须**显式给 `encoding=`**，否则 stdout 会静默变 None。

    实测根因（2026-08-31，一条真红逼出来的）：PowerShell 下
    `sys.stdout.encoding = utf-8` 而 `locale.getencoding() = cp936`
    ⇒ 子进程按 UTF-8 写、父进程 `subprocess.run(text=True)` 按 GBK 解
    ⇒ `UnicodeDecodeError` 抛在 `subprocess._readerthread` **线程里被吞掉**，
    `run()` **正常返回**、`stdout` 与 `stderr` **双双是 None**，调用方一个错都收不到。
    Git Bash 下两侧同为 cp936 所以不炸——**同一份代码换个壳结论不同，而门跑的是
    PowerShell 那个壳**（同族＝本仓那条「我跑的对象与别人要用的对象是不是同一个」）。

    ⚠ **判据是「两件都要」，不是二选一**（本条首版写成了二选一，已订正）：
    · `errors=` 非 strict ⇒ **永不变 None**（安全性）——但**不保证解得对**，
      编码不一致时它安静交回乱码，让「输出里应含某句中文」的断言**假红**；
    · `encoding=` 正确 ⇒ **解得对**（正确性）——但默认 `errors='strict'`，
      遇非法字节**照样在读线程里抛而被吞掉**，stdout 照样变 None。
    判决性实验（2026-08-31）：子进程吐 `b'ok-\x80-end'`，
    `encoding='utf-8'` 无 `errors=` ⇒ **rc=0, stdout=None**；加 `errors='replace'`
    ⇒ `'ok-\ufffd-end'`。
    ⚠ 首版的错法值得记：我的理由（「`errors=` 不保证解得对」）**本身没错**，
    错在**从「A 不充分」推出了「A 不必要」**——在二元判断上把关于 A 的偏结论
    直接搬去决定 B（与本仓「排除候选 A ≠ 证成候选 B」同族）。
    缺口由采集侧核出：`test_cli_smoke.py` 有一处只给了 `encoding=`。两者要一起给：
    `encoding=` 钉父侧解码、`errors=` 兜底、子侧再用 `PYTHONIOENCODING` 钉编码。
    范本＝ `test_cli_smoke.py`，它早就是三件齐全的。

    ⚠ **扫描面＝整个仓**。演变值得记：首版只扫 `scripts/`，docstring 里自己写着
    「别把它的绿读成全仓干净」——而**一道扫描面小于它所声称保护的范围的守卫，
    它的绿本身就是一条误导**（这半句由采集侧指出，成立）。第二版改成扫
    `scripts/` ＋ `tools/` 并「逐根断言各根都有货」，**突变审计当场判它 SURVIVED**：
    那条断言遍历的正是 `_ROOTS` 自己 ⇒ **把一个根拿掉，同时也拿掉了对它的检查**，
    守卫悄悄变窄而照样绿——**要防的形状，长在防它的那条守卫里**。
    故本版直接扫全仓，那个问题从构造上消失；完整性改由下面的索引×文件系统互证守。

    用 AST 而不是正则：这些调用跨多行，正则会漏掉换行处的关键字。
    """
    # ⚠ 判据（哪些调用算数、缺什么算违规）**只有一份**，在
    # `_text_mode_subprocess_offenders` 里。抽取时这里残留过一份 TEXT_KEYS/CAPTURING
    # 副本，已删——**同一个事实写在两处，必有一处先漂，而漂的那处不会报错**：
    # 后来人改这里的副本会以为改了判据，其实一点作用都没有。本函数只管「扫哪些文件」。
    SKIP_DIRS = {".git", "__pycache__", "node_modules", "build", ".gradle",
                 ".idea", "venv", ".venv", ".pytest_cache"}
    offenders, scanned, seen = [], 0, set()
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            seen.add(os.path.relpath(path, REPO).replace(chr(92), "/"))
            found, n = _text_mode_subprocess_offenders(
                open(path, encoding="utf-8", errors="replace").read(),
                os.path.relpath(path, REPO).replace(chr(92), "/"))
            offenders.extend(found)
            scanned += n
    # 完整性互证：索引侧枚举出的每一个 .py，文件系统侧都必须走到过。
    # ⚠ 两条腿必须**不共享机制**才算互证：`git ls-files`（读索引）vs `os.walk`
    # （读文件系统）。换了切法也换了读法，才不会「同一缺陷喂出两个假独立方法」。
    # ⚠ 读 git 输出用**字节模式**——这条守卫自己不能踩它要防的那个坑。
    import subprocess
    listed = subprocess.run(["git", "ls-files", "*.py"],
                            capture_output=True, cwd=REPO)
    tracked = {ln for ln in listed.stdout.decode("utf-8", errors="replace")
               .replace(chr(13), "").split(chr(10)) if ln.strip()}
    tracked = {t for t in tracked
               if not any(("/" + d + "/") in ("/" + t) for d in SKIP_DIRS)}
    assert listed.returncode == 0 and tracked, (
        "`git ls-files '*.py'` 没给出东西——互证的另一条腿断了；此时本条的绿"
        "只说明遍历侧没报错，**不说明它走全了**")
    missed = sorted(tracked - seen)
    assert not missed, (
        "这些 .py 在 git 索引里、却没被遍历到（%d 个，前 5：%s）⇒ "
        "**遍历面被收窄了而守卫照样绿**，那正是本条要防的形状" % (len(missed), missed[:5]))
    assert scanned >= 5, (
        "只扫到 %d 处文本模式的子进程调用——扫描八成坏了，而一条什么都没查到的"
        "守卫会因为错误的理由变绿" % scanned)
    assert not offenders, (
        "这些调用用文本模式抓输出却没钉 encoding= ⇒ 编码不一致时 stdout 会"
        "**静默变成 None**（异常被 _readerthread 吞掉，run() 照常返回）：%s\n"
        "修法照 test_cli_smoke.py：encoding=\"utf-8\", errors=\"replace\"，"
        "（子进程若是 **Python**，再给 env `PYTHONIOENCODING=utf-8` 钉子侧；子进程是 "
        "adb 之类**非 Python 二进制**时这一件不起作用——别照抄配方，按场景给）。"
        "\n本条扫描面＝整个仓（跳过 %s）。" % (offenders, sorted(SKIP_DIRS)))


def test_the_decoding_criterion_bites_on_every_shape_it_claims_to_cover():
    """拿**合成源码**逐条钉住上面那个判据的每一个分支。

    ⚠ 为什么需要它：仓内扫描形态下，突变审计判了两条分支 SURVIVED
    （「退回只查 `encoding=`」「不认裸导入形态」）——**不是守卫弱，是方法固有**：
    仓一旦全合规，「拿掉检查」与「存在违规」**只能联合观测**，单独拿掉检查测不出来。
    而本仓的规矩是：**为某判断写了一条分支 ≠ 那分支在承重**，等价突变只有把判定
    逻辑抽出来喂合成输入才答得了。本条即那个答案。

    ⚠ 正例与反例都放着，两头钉住：只有反例时，把判据收紧到「什么都算违规」
    照样全绿；只有正例时，把判据放松到「什么都不算」也照样全绿。
    """
    def offenders(src):
        return _text_mode_subprocess_offenders(src, "synthetic.py")[0]

    # ① 裸 text=True：两件都缺
    bad = offenders("import subprocess\nsubprocess.run(['x'], capture_output=True, text=True)\n")
    assert len(bad) == 1 and "encoding=" in bad[0] and "errors=" in bad[0], bad

    # ② 只给 encoding=：仍违规（strict 下非法字节照样让 stdout 变 None）
    bad = offenders("import subprocess\n"
                    "subprocess.run(['x'], text=True, encoding='utf-8')\n")
    assert len(bad) == 1 and "errors=" in bad[0] and "encoding=" not in bad[0], bad

    # ③ errors='strict' 不许拿来哄守卫
    bad = offenders("import subprocess\n"
                    "subprocess.run(['x'], text=True, encoding='utf-8', errors='strict')\n")
    assert len(bad) == 1 and "strict" in bad[0], bad

    # ④ **裸导入形态**：`from subprocess import run` 后直接 run(...)
    #    ——加它时全仓零命中，本例是它唯一的承重证明
    bad = offenders("from subprocess import run\nrun(['x'], text=True)\n")
    assert len(bad) == 1 and "run" in bad[0], bad
    #    别名也要认
    bad = offenders("from subprocess import run as r\nr(['x'], text=True)\n")
    assert len(bad) == 1, bad

    # ⑤ 正例一：两件齐全 ⇒ 放行
    assert offenders("import subprocess\nsubprocess.run(['x'], text=True, "
                     "encoding='utf-8', errors='replace')\n") == []
    # ⑥ 正例二：**字节模式** ⇒ 放行（bytes 不会解码失败，不该被判违规）
    assert offenders("import subprocess\n"
                     "subprocess.run(['x'], capture_output=True)\n") == []
    # ⑦ 正例三：同名但**不是** subprocess 的函数 ⇒ 不该被误伤
    assert offenders("import shutil\nshutil.run(['x'], text=True)\n") == []
    assert offenders("def run(*a, **k): pass\nrun(['x'], text=True)\n") == []


# ── 清单对账（D-633 ⑤(i)）──────────────────────────────────────────────

MANIFEST_UNLISTED_OK = "verify_all_"


def unlisted_tracked_files(tracked, listed, manifest_rel):
    """git 跟踪了、却没有清单条目的文件。**判据不含时间、不含名单，不会过期。**

    抽成纯函数是为了让「例外只许是运行日志」这一条能被**合成输入**钉住 ——
    仓里此刻恰好只有合规的那一种，靠真实数据永远测不出把例外放宽的坏实现
    （干净仓上「拿掉检查」与「存在违规」只能联合观测）。
    """
    return sorted(f for f in tracked
                  if f not in listed and f != manifest_rel
                  and os.path.basename(f).startswith(MANIFEST_UNLISTED_OK) is False)


def test_every_tracked_evidence_file_has_a_hash_except_the_run_logs():
    """`evidence/phase0` 下**已跟踪但不在清单里**的文件，必须全部是 `verify_all_*.log`。

    守的是这句话：**「清单覆盖了该覆盖的一切」在此之前没有任何东西在守它。**
    一份别人要引用的证据可以躺在库里、没有任何完整性记录，**而不会有人发现**。

    ⚠ 为什么例外恰好是运行日志：顺序是**结构性**的 —— 清单永远先生成，
    当次日志随后才 `git add -f` 入库 ⇒ 每次归档提交之后必然短暂存在
    「已跟踪但未列」的日志，**下次重算即自愈**（实测：两小时前 2 个，一次归档跑后
    变 1 个 —— 旧的被收进清单、新的又添了一条）。
    ⇒ **判据不能写成「一个都不许有」**：那会把正常工作流判成违规，
    而**一条第一天就要加豁免的守卫，它的豁免名单会过期**。

    ⚠ **反向（清单条目指向已删文件）刻意不守**：那种失效会**响亮报错**
    （核对哈希时当场喊），而本条守的是**静默缺席**。危险度不对等，
    为对称加第二条只会把一条精准守卫稀释成两条。实测反向此刻为 ∅。

    ⚠ 读 git 输出用**字节模式**：本仓有过 `text=True` 不给 `encoding=` 时
    stdout 静默变 None 的实例，守卫自己不能踩它要防的坑。
    """
    import subprocess
    ev = "evidence/phase0"
    ls = subprocess.run(["git", "ls-files", ev], capture_output=True, cwd=REPO)
    assert ls.returncode == 0, "git ls-files 跑不动，本条的绿不说明任何事"
    tracked = {x for x in ls.stdout.decode("utf-8", errors="replace")
               .replace(chr(13), "").split(chr(10)) if x.strip()}
    assert tracked, "%s 下一个跟踪文件都没有 —— 扫描八成坏了" % ev

    show = subprocess.run(["git", "show", "HEAD:%s/sha256-manifest.txt" % ev],
                          capture_output=True, cwd=REPO)
    assert show.returncode == 0, "HEAD 里没有清单文件"
    listed = {ev + "/" + ln.split("  ", 1)[1]
              for ln in show.stdout.decode("utf-8-sig", errors="replace")
              .replace(chr(13), "").split(chr(10))
              if ln.strip() and not ln.startswith("#") and "  " in ln}
    assert listed, "清单解析出零条 —— 行格式变了，判据跟不上"

    bad = unlisted_tracked_files(tracked, listed, ev + "/sha256-manifest.txt")
    assert not bad, (
        "这些文件 git 跟踪着、却没有任何完整性记录，且不是运行日志：%s\n"
        "⇒ 别人 checkout 后无从核对它们有没有被改过，而**没有任何东西会报错**。"
        "修法：跑一次 `verify_all.ps1 -Scope all` 让清单重算，与产物同批入库。" % bad)


def test_the_manifest_exception_covers_run_logs_and_nothing_else():
    """拿**合成输入**逐条钉住例外的边界 —— 真实数据此刻只有合规的那一种。

    ⚠ 正例反例都要：只有反例时，把例外收成「什么都不许缺」照样全绿；
    只有正例时，把例外放宽成「什么都可以缺」也照样全绿。
    """
    ev = "evidence/phase0"
    mf = ev + "/sha256-manifest.txt"
    listed = {ev + "/badges.txt"}

    # 反例①：一份**非日志**的证据被跟踪却没有哈希 ⇒ 必须被逮住
    bad = unlisted_tracked_files({ev + "/badges.txt", ev + "/STATUS.json", mf},
                                 listed, mf)
    assert bad == [ev + "/STATUS.json"], bad

    # 正例①：运行日志缺条目是**结构性**的（清单先生成、日志后 add -f）⇒ 放行
    ok = unlisted_tracked_files(
        {ev + "/badges.txt", ev + "/verify_all_20260831-000000-1.log", mf},
        listed, mf)
    assert ok == [], ok

    # 正例②：清单自身永远不在清单里 ⇒ 放行
    assert unlisted_tracked_files({mf}, set(), mf) == []

    # 反例②：**名字里带 verify_all 但不在开头**不算例外 —— 例外按前缀不按包含，
    # 否则任何人只要把 `verify_all` 塞进文件名就能绕过完整性记录。
    sneaky = ev + "/notes_verify_all_hack.json"
    assert unlisted_tracked_files({sneaky, mf}, set(), mf) == [sneaky]
