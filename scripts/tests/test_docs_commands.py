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
DOCS = [os.path.join(SCRIPTS, "README.md"),
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
                    out.append((os.path.basename(doc), m.group(1),
                                _FLAG.findall(m.group(2))))
    return out


def test_docs_contain_commands():
    """Guard the guard: if the extraction breaks, the checks below go vacuous."""
    cmds = _commands()
    assert len(cmds) >= 8, f"only found {len(cmds)} documented commands — parser broken?"


def test_documented_scripts_exist():
    missing = [(doc, s) for doc, s, _ in _commands()
               if not os.path.exists(os.path.join(SCRIPTS, s))]
    assert not missing, f"docs reference scripts that do not exist: {missing}"


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

    # union over corpus shapes: 2 campaigns render before/after, 3+ render trend
    headings = set()
    for campaigns in (("base", "opt"), ("base", "opt", "r3")):
        recs = sc.generate(points=3, repeats=5, campaigns=campaigns)
        md = rpt.build_report_markdown(recs, provenance=prov.compute(
            [], {"lines": 1, "kept": 1}, {}, generated_at="2026-01-01",
            thresholds=rpt.effective_thresholds()))
        headings |= {ln[3:].strip() for ln in md.splitlines() if ln.startswith("## ")}

    missing = [w for w in wanted if not any(w in h for h in headings)]
    assert not missing, f"template maps to sections the report does not emit: {missing}"


def test_every_tool_is_mentioned_in_the_readme():
    """The command guard checks that documented commands work; it cannot notice a
    tool nobody documented. corpus_health.py and order_effect.py sat unmentioned
    in the README for weeks (D-131) — a reader had no way to discover them."""
    readme = os.path.join(SCRIPTS, "README.md")
    with open(readme, encoding="utf-8") as f:
        body = f.read()
    tools = [n for n in sorted(os.listdir(SCRIPTS))
             if n.endswith(".py") and not n.startswith("_")]
    missing = [n for n in tools if n not in body and n[:-3] not in body]
    assert not missing, f"tools missing from scripts/README.md: {missing}"


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
