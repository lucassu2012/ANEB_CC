# -*- coding: utf-8 -*-
"""CLI smoke tests: subprocess-run each entry point on a tiny synthetic fixture.

Catches argparse / import / encoding regressions that function-level golden tests
miss — e.g. a console-encoding bug where the pure functions pass but the CLI
crashes on print (exactly the Windows GBK/U+26A0 case fixed via force_utf8_stdout).
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)

from synth import aqs_records, contractify, make_record, tier_records


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _run(script, *args, env=None):
    # errors="replace", not strict: a child that emits one non-UTF-8 byte kills
    # subprocess's reader THREAD, and communicate() then hands back stderr=None.
    # Every assertion below indexes r.stderr, so the whole suite answered a real
    # encoding regression with `TypeError: 'NoneType' is not subscriptable` and
    # a PytestUnhandledThreadExceptionWarning buried 300 lines up — a failure
    # that says nothing about the bug (D-380). Replacement characters fail the
    # SAME assertions, and print what actually came back.
    return subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, script), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=SCRIPTS, env=env)


def _fixture(d):
    recs = [contractify(r) for r in
            (tier_records("metro", "n1_rtt_p50_ms", 20, 5)
             + tier_records("regional", "n1_rtt_p50_ms", 35, 5)
             + tier_records("core", "n1_rtt_p50_ms", 60, 5)
             + aqs_records(90, 5))]
    path = os.path.join(d, "in.jsonl")
    _write_jsonl(path, recs)
    return path


def test_a_mistyped_output_path_does_not_answer_with_a_traceback():
    """Input robustness has had five passes; the output side had none. All four
    destination flags answered a missing directory with a raw traceback, and
    since markdown is written before CSV, `--md ok.md --csv nope/c` left half a
    deliverable set behind one (D-306). Mistyping the destination is an
    end-of-field-day mistake, not an exotic one.

    The flag list is read out of --help rather than typed here: a future flag
    that says it writes somewhere fails this until it is covered. COLUMNS is
    widened so argparse does not wrap the help text out of reach.
    """
    env = dict(os.environ, COLUMNS="200", PYTHONIOENCODING="utf-8")
    # ⚠ `errors=` 不是可选项：`encoding=` 只钉「用哪个 codec」，默认 errors='strict'
    # 遇到非法字节仍会**在 `_readerthread` 线程里抛而被吞掉**，`run()` 照常返回、
    # stdout 变 None（2026-08-31 实证：子进程吐 b'ok--end' ⇒ rc=0, stdout=None）。
    # 本文件第 36 行那个 helper 早就两件齐全，只有这一处漏了——由采集侧核出。
    helptext = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "campaign_report.py"), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=SCRIPTS, env=env).stdout
    # argparse puts the help on the NEXT line whenever the invocation is longer
    # than max_help_position — `--provenance PROVENANCE` is — so continuation
    # lines have to be folded back into their flag before looking for "write".
    entries, current = {}, None
    for line in helptext.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            current = stripped.split()[0].split("=")[0]
            entries[current] = stripped
        elif current and line.startswith("  ") and stripped:
            entries[current] += " " + stripped
    flags = {f for f, text in entries.items() if "write" in text}
    assert flags == {"--md", "--html", "--csv", "--provenance"}, (
        "the set of writing flags changed: %s — cover the new one here"
        % sorted(flags))

    for flag in sorted(flags):
        with tempfile.TemporaryDirectory() as d:
            src = _fixture(d)
            target = os.path.join(d, "nope", "out")
            r = _run("campaign_report.py", src, flag, target)
            assert r.returncode == 2, (flag, r.returncode, r.stderr[:400])
            assert "Traceback" not in r.stderr, (flag, r.stderr[:400])
            assert "输出路径不可用" in r.stderr, (flag, r.stderr[:400])
            left = sorted(os.listdir(d))
            assert left == [os.path.basename(src)], (
                "%s produced files before refusing: %s" % (flag, left))


def test_the_refusal_an_operator_reaches_by_mistyping_is_utf8_on_any_console():
    """D-381. `force_utf8_stdout` sat BELOW the output preflight, so the one
    message a mistyped path produces was the single stderr write in
    campaign_report emitted at the console codepage instead of UTF-8.

    On this zh-CN Windows box that meant GBK bytes: the test above decoded them
    as UTF-8, subprocess's reader thread raised, communicate() returned
    stderr=None, and every assertion indexing r.stderr died with
    `TypeError: 'NoneType' is not subscriptable` — a red suite saying nothing
    about the cause. Worse than the noise: one character GBK cannot encode (⚠
    U+26A0, the very case force_utf8_stdout exists for) would have answered a
    mistyped path with the traceback D-306 removed.

    The test above only bites where the console is not UTF-8 already, so it
    cannot pin this on Linux/CI. PYTHONIOENCODING forces the child's stderr to a
    codec that CANNOT represent the message on any platform; reconfigure()
    overrides it, so bytes coming back decodable as UTF-8 prove the call ran
    before the print. A sweep of all 17 CLIs calling force_utf8_stdout found
    campaign_report the only one printing before it.
    """
    for enc in ("gbk", "latin-1", "ascii"):
        with tempfile.TemporaryDirectory() as d:
            src = _fixture(d)
            env = dict(os.environ, PYTHONIOENCODING=enc)
            r = _run("campaign_report.py", src, "--md",
                     os.path.join(d, "nope", "out"), env=env)
            assert r.returncode == 2, (enc, r.returncode, r.stderr[:300])
            # errors="replace" in _run: a byte the UTF-8 decoder rejected comes
            # back as U+FFFD, so the phrase check below fails readably instead
            # of the whole subprocess handing back None.
            assert "�" not in r.stderr, (
                "%s: stderr is not valid UTF-8 — force_utf8_stdout ran after the "
                "message, or not at all: %r" % (enc, r.stderr[:300]))
            assert "输出路径不可用" in r.stderr, (enc, r.stderr[:300])
            assert "Traceback" not in r.stderr, (enc, r.stderr[:300])


def test_the_documented_batch_workflow_creates_its_output_directory():
    """Two tools, two policies, and only one of them was ever decided out loud.

    D-306's sweep for siblings found exactly one other CLI with a path-valued
    write flag: `annotate_campaign --out-dir`, which creates its destination
    (annotate_campaign.py's os.makedirs) while campaign_report's file and prefix
    flags refuse a missing parent. The difference is right — a flag naming a
    DIRECTORY may make it, a flag naming a FILE or a PREFIX must not scatter
    output into a mistyped parent — but the runbook's own step depends on the
    creating half and nothing checked it. Delete that makedirs and the
    documented workflow dies with the traceback D-306 just removed (D-307).

    Both halves are pinned here so neither drifts toward the other.
    """
    with tempfile.TemporaryDirectory() as d:
        src = _fixture(d)
        outdir = os.path.join(d, "labeled")          # deliberately absent
        r = _run("annotate_campaign.py", src, "--out-dir", outdir,
                 "--set", "campaign_id=SZ-2026-07")
        assert r.returncode == 0, (r.returncode, r.stderr[:400])
        assert os.path.isdir(outdir), "the documented step did not create its dir"
        assert os.listdir(outdir) == [os.path.basename(src)], os.listdir(outdir)

    with tempfile.TemporaryDirectory() as d:
        src = _fixture(d)
        r = _run("campaign_report.py", src, "--csv",
                 os.path.join(d, "nope", "c"))
        assert r.returncode == 2, (r.returncode, r.stderr[:400])
        assert not os.path.isdir(os.path.join(d, "nope")), (
            "a prefix flag must not create the parent it was pointed at")


def test_a_section_cli_says_when_two_runs_disagree():
    """Thirteen section CLIs never ask load_records for its counters. Malformed
    lines and unreadable files still reach them, because the loader prints one
    line per skip — but a CONFLICTING run_id printed nothing, so those tools
    computed medians over a corpus where two runs disagree about what happened
    and said not a word (D-331).

    Fixed where it is known rather than in thirteen places (§2.14). Exit codes
    are untouched: this only tells, it does not gate.
    """
    from synth import make_record

    recs = [make_record(aqs=90, run_id="R-1"), make_record(aqs=80, run_id="R-2")]
    clash = json.loads(json.dumps(recs[0]))
    clash["run"]["aqs"]["score"] = 11          # same id, different body

    with tempfile.TemporaryDirectory() as d:
        # A BENIGN re-export, not a corpus without duplicates: the half most
        # easily got wrong is warning on D-09 dual-write, and a corpus with no
        # repeat at all would never exercise it.
        clean_p = os.path.join(d, "clean.jsonl")
        _write_jsonl(clean_p, list(recs) + [json.loads(json.dumps(recs[0]))])
        clean = _run("stability.py", clean_p)

        dirty_p = os.path.join(d, "dirty.jsonl")
        _write_jsonl(dirty_p, list(recs) + [clash])
        dirty = _run("stability.py", dirty_p)

    assert "conflicting run_id" not in clean.stderr, (
        "the warning fires without a conflict, so seeing it on the dirty "
        "corpus would prove nothing: %s" % clean.stderr[:200])
    assert "conflicting run_id R-1" in dirty.stderr, (
        "a section CLI analysed a corpus with two disagreeing runs and said "
        "nothing: %r" % dirty.stderr[:300])
    assert dirty.returncode == clean.returncode, (
        "telling the operator must not change whether the tool succeeds")


def test_a_section_cli_says_when_records_have_no_run_id():
    """run.run_id is contract-LEGAL to omit — neither the server's required
    field set nor validate_results asks for it — so a corpus can hold records
    that cannot be de-duplicated at all, R-10 forbidding a fabricated key.
    Repeats among them are undetectable and inflate every denominator they
    reach, and only the publish gate said so (D-332).

    Printed once per corpus, not per record: with thousands of them a wall of
    identical lines is noise, and that is pinned below by counting occurrences.
    """
    from synth import make_record

    recs = [make_record(aqs=90, run_id="R-%d" % i) for i in range(2)]
    anon = json.loads(json.dumps(recs))
    for r in anon:
        del r["run"]["run_id"]

    with tempfile.TemporaryDirectory() as d:
        clean_p = os.path.join(d, "clean.jsonl")
        _write_jsonl(clean_p, recs)
        clean = _run("stability.py", clean_p)

        anon_p = os.path.join(d, "anon.jsonl")
        _write_jsonl(anon_p, anon)
        got = _run("stability.py", anon_p)

    assert "without run.run_id" not in clean.stderr, (
        "the notice fires on a corpus where every record has an id: %s"
        % clean.stderr[:200])
    assert got.stderr.count("without run.run_id") == 1, (
        "expected exactly one notice for the whole corpus, got %d: %r"
        % (got.stderr.count("without run.run_id"), got.stderr[:300]))
    assert "2 record(s)" in got.stderr, got.stderr[:300]
    assert got.returncode == clean.returncode, (
        "telling the operator must not change whether the tool succeeds")


def test_a_file_that_cannot_be_read_stops_the_report():
    """The report's front door refuses a damaged corpus, citing corpus_health's
    ERROR classification — and listed two of its three. load_records catches
    OSError and carries on, so a file it cannot open takes ALL of its records
    out of the corpus and the report came out regardless, every denominator
    short and nothing saying so (D-330).

    A directory is used as the unreadable path: opening one raises OSError on
    every platform (PermissionError on Windows, IsADirectoryError on POSIX),
    which needs no permission juggling to arrange.
    """
    from synth import make_record

    with tempfile.TemporaryDirectory() as d:
        good = os.path.join(d, "good.jsonl")
        _write_jsonl(good, [make_record(aqs=90, run_id="R-%d" % i)
                            for i in range(3)])

        ok = _run("campaign_report.py", good, "--md", os.path.join(d, "r.md"))
        assert ok.returncode == 0, (
            "the corpus alone does not produce a report, so adding a bad path "
            "proves nothing: %s" % ok.stderr[:300])

        # same inputs plus the directory itself, which cannot be opened
        bad = _run("campaign_report.py", good, d, "--md",
                   os.path.join(d, "r2.md"))

    assert bad.returncode == 1, (
        "a corpus missing an entire file still produced a report (exit %d)"
        % bad.returncode)
    assert "unreadable" in bad.stderr, bad.stderr[:300]


def test_the_publish_gate_reports_integrity_from_the_command_line():
    """The unit guard exercises check(); whether main() actually hands it the
    loader's counters is a different surface. The mutation removing
    `stats=stats` from main survived the whole suite — the CLI would have
    printed 未核算 forever while the function stayed perfectly correct, which
    is the shape D-237/D-238 named: the thing tested is not the thing shipped
    (D-325).

    Scoped to the integrity row on purpose: 未核算 is legitimate on other items
    (a corpus with nothing to compare really did not run those), so asserting
    on the whole page would fail for the wrong reason.
    """
    from synth import make_record

    recs = [make_record(aqs=90, run_id="R-1"), make_record(aqs=80, run_id="R-2")]
    # Same run_id, genuinely DIFFERENT body. The first attempt set scenarios to
    # [] on a record whose scenarios were already empty, so the two serialised
    # identically and the gate correctly called it a benign re-export — the
    # fixture had not built what it claimed, and the assertion below said so.
    clash = json.loads(json.dumps(recs[0]))
    clash["run"]["aqs"]["score"] = 11
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "dup.jsonl")
        _write_jsonl(path, list(recs) + [clash])
        r = _run("publish_check.py", path)

    line = [l for l in r.stdout.splitlines() if "语料完整性" in l]
    assert len(line) == 1, (
        "expected exactly one integrity row on the page, got %d" % len(line))
    row = line[0]
    assert "未核算" not in row, (
        "the CLI never handed the loader's counters to the gate: %r" % row)
    assert "R-1" in row, (
        "the row does not name the conflicting run_id: %r" % row)


def test_a_duplicated_corpus_says_what_it_dropped():
    """Both per-run CLIs now de-duplicate by run.run_id (D-315). Dropping half
    the input without a word is the same fault as counting it twice, so each
    must say so on the surface its reader actually looks at: stdout for
    analyze_results, the page itself for dashboard — stdout scrolls away and
    the html is the deliverable.
    """
    from synth import make_record

    recs = [make_record(aqs=90, run_id="R-1"), make_record(aqs=80, run_id="R-2")]
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "dup.jsonl")
        _write_jsonl(path, list(recs) + [recs[0]])  # R-1 written twice

        r = _run("analyze_results.py", path)
        assert r.returncode == 0, r.stderr
        assert "records: **2**" in r.stdout, r.stdout[:300]
        assert "dropped 1 repeat run_id" in r.stdout, (
            "analyze_results dropped a record without saying so: %r"
            % r.stdout[:300])

        out = os.path.join(d, "d.html")
        r = _run("dashboard.py", path, "-o", out)
        assert r.returncode == 0, r.stderr
        assert "records=2" in r.stdout, r.stdout[:300]
        assert "dropped=1" in r.stdout, r.stdout[:300]
        page = open(out, encoding="utf-8").read()
        assert "去重丢 1" in page, (
            "dashboard dropped a record and the page does not say so")


def test_report_cli_runs():
    with tempfile.TemporaryDirectory() as d:
        r = _run("campaign_report.py", _fixture(d))
        assert r.returncode == 0, r.stderr
        assert "综合报告" in r.stdout


def test_report_cli_html_and_csv():
    with tempfile.TemporaryDirectory() as d:
        f = _fixture(d)
        html_out = os.path.join(d, "r.html")
        csv_prefix = os.path.join(d, "r")
        r = _run("campaign_report.py", f, "--html", html_out, "--csv", csv_prefix)
        assert r.returncode == 0, r.stderr
        assert os.path.exists(html_out)
        with open(html_out, encoding="utf-8") as fh:
            page = fh.read()
        # HTML report carries every markdown-only section too (D-107 parity)
        for marker in ("溯源", "复测稳定性", "序位效应", "有效性与失效原因",
                       "AQS 分数侧归因", "批化(buffering)归因"):
            assert marker in page, f"HTML report missing section: {marker}"
        for suffix in ("_heat", "_attribution", "_stability",
                       "_validity", "_subscores", "_buffering", "_transport", "_trust",
                       "_comparison"):
            assert os.path.exists(csv_prefix + suffix + ".csv"), suffix
        # _trend.csv is written only when a trend EXISTS. Shipping it for a
        # two-campaign corpus put `direction=improving` into the archive for the
        # very cells the _comparison.csv beside it marked within_noise, while the
        # report showed no trend section at all (D-196).
        import campaign_common as cc
        import trend
        recs, _files = cc.load_records([f])
        n_campaigns = len({cc.campaign_labels(r)["campaign_id"] for r in recs})
        assert os.path.exists(csv_prefix + "_trend.csv") == (
            n_campaigns >= trend.MIN_CAMPAIGNS_FOR_TREND), n_campaigns


def test_report_cli_rejects_malformed_corpus():
    """Non-result-run input (e.g. raw token-arrival samples) must refuse a report,
    not degrade into empty sections (D-105 front-door gate)."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "bad.jsonl")
        _write_jsonl(path, [{"seq": 1, "arrival_us": 12345}])
        r = _run("campaign_report.py", path)
        assert r.returncode == 1, r.stdout
        assert "契约门 FAIL" in r.stderr
        assert "拒绝出报告" in r.stderr


def _two_campaign_fixture(d):
    recs = [contractify(r) for r in
            (aqs_records(55, 6, campaign_id="base") + aqs_records(75, 6, campaign_id="opt"))]
    path = os.path.join(d, "two.jsonl")
    _write_jsonl(path, recs)
    return path


def test_report_cli_campaign_filter_gives_a_clean_single_round():
    """Headline numbers must come from ONE campaign — pooled they are neither
    (D-136). --campaign is how the operator gets that."""
    with tempfile.TemporaryDirectory() as d:
        f = _two_campaign_fixture(d)
        md_path = os.path.join(d, "r.md")
        r = _run("campaign_report.py", f, "--campaign", "base", "--md", md_path)
        assert r.returncode == 0, r.stderr
        with open(md_path, encoding="utf-8") as fh:
            md = fh.read()
        assert "MIXED_CAMPAIGN" not in md          # single round: nothing pooled
        assert "本语料含" not in md          # the pooling notice, not any mention of 战役
        assert "| 55 |" in md                      # the baseline's own median


def test_report_cli_unknown_campaign_is_not_an_empty_report():
    with tempfile.TemporaryDirectory() as d:
        f = _two_campaign_fixture(d)
        r = _run("campaign_report.py", f, "--campaign", "typo")
        assert r.returncode == 2, r.stdout
        assert "匹配 0 条记录" in r.stderr
        assert "base" in r.stderr and "opt" in r.stderr   # tells you what exists


def test_report_cli_empty_corpus_not_executed():
    """Zero records must be NOT_EXECUTED (exit 2), never a valid-looking empty
    report (D-109)."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "empty.jsonl")
        open(path, "w").close()
        r = _run("campaign_report.py", path)
        assert r.returncode == 2, r.stdout
        assert "不产出空报告" in r.stderr


def test_report_cli_conflicting_run_id_refused():
    """One run_id with two different bodies = damaged corpus -> refuse (D-109)."""
    with tempfile.TemporaryDirectory() as d:
        recs = [contractify(r) for r in tier_records("metro", "n1_rtt_p50_ms", 20, 2)]
        recs[1]["run"]["run_id"] = recs[0]["run"]["run_id"]
        recs[1]["scenarios"][0]["kpi"]["n1_rtt_p50_ms"] = 999  # different body
        path = os.path.join(d, "conflict.jsonl")
        _write_jsonl(path, recs)
        r = _run("campaign_report.py", path)
        assert r.returncode == 1, r.stdout
        assert "语料完整性 FAIL" in r.stderr


def test_report_cli_skip_contract_check_escape_hatch():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "bad.jsonl")
        _write_jsonl(path, [{"seq": 1, "arrival_us": 12345}])
        r = _run("campaign_report.py", path, "--skip-contract-check")
        assert r.returncode == 0, r.stderr
        assert "综合报告" in r.stdout


def test_attribution_cli_runs():
    with tempfile.TemporaryDirectory() as d:
        r = _run("attribution.py", _fixture(d))
        assert r.returncode == 0, r.stderr
        assert "归因矩阵" in r.stdout


def test_stability_cli_runs():
    with tempfile.TemporaryDirectory() as d:
        r = _run("stability.py", _fixture(d), "--kpi", "n1_rtt_p50_ms")
        assert r.returncode == 0, r.stderr
        assert "复测稳定性" in r.stdout


def test_annotate_batch_out_dir():
    """A field day has dozens of files; --out-dir annotates them in one call
    without touching the inputs (D-118)."""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "in")
        os.makedirs(src)
        names = ["day1_p1.jsonl", "day1_p2.jsonl", "day2_p1.jsonl"]
        for n in names:                       # unlabelled records — labels to be filled
            _write_jsonl(os.path.join(src, n),
                         [contractify(make_record(aqs=90, scenarios=[])) for _ in range(2)])
        before = {n: open(os.path.join(src, n), encoding="utf-8").read() for n in names}
        out = os.path.join(d, "labeled")
        r = _run("annotate_campaign.py", *[os.path.join(src, n) for n in names],
                 "--out-dir", out, "--set", "point_id=P1", "--set", "carrier=cmcc")
        assert r.returncode == 0, r.stderr
        for n in names:
            assert os.path.exists(os.path.join(out, n)), n
            with open(os.path.join(out, n), encoding="utf-8") as f:
                rec = json.loads(f.readline())
            assert rec["run"]["campaign"]["point_id"] == "P1"
            assert rec["run"]["campaign"]["carrier"] == "cmcc"
            # inputs byte-for-byte untouched
            assert open(os.path.join(src, n), encoding="utf-8").read() == before[n], n


def test_annotate_expands_globs_itself():
    """PowerShell does not expand wildcards for external programs, so the tool
    must — otherwise a documented `raw/day1_*.jsonl` reaches --out-dir as a
    literal filename containing '*' and crashes (D-120)."""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "raw")
        os.makedirs(src)
        for n in ("day1_p1.jsonl", "day1_p2.jsonl"):
            _write_jsonl(os.path.join(src, n),
                         [contractify(make_record(aqs=90, scenarios=[]))])
        out = os.path.join(d, "labeled")
        r = _run("annotate_campaign.py", os.path.join(src, "day1_*.jsonl"),
                 "--out-dir", out, "--set", "point_id=P1")
        assert r.returncode == 0, r.stderr
        assert sorted(os.listdir(out)) == ["day1_p1.jsonl", "day1_p2.jsonl"]


def test_annotate_pattern_matching_nothing_is_an_error():
    """A typo'd path used to silently produce an empty output file."""
    with tempfile.TemporaryDirectory() as d:
        r = _run("annotate_campaign.py", os.path.join(d, "nope_*.jsonl"),
                 "-o", os.path.join(d, "out.jsonl"), "--set", "point_id=P1")
        assert r.returncode != 0
        assert "no files match" in r.stderr
        assert not os.path.exists(os.path.join(d, "out.jsonl"))


def test_annotate_warns_when_one_point_id_covers_many_files():
    """A field day spans several points; a day-wide glob plus one --set point_id
    stamps them all identically — wrong labels that look perfectly normal. The
    tool cannot know, so it warns rather than refuses (D-132)."""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "raw")
        os.makedirs(src)
        for n in ("a.jsonl", "b.jsonl"):
            _write_jsonl(os.path.join(src, n),
                         [contractify(make_record(aqs=90, scenarios=[]))])
        r = _run("annotate_campaign.py", os.path.join(src, "a.jsonl"),
                 os.path.join(src, "b.jsonl"), "--out-dir", os.path.join(d, "out"),
                 "--set", "point_id=SZ-CBD-01")
        assert r.returncode == 0, r.stderr          # a warning, not a refusal
        assert "统一打到 2 个文件" in r.stderr
    # one file, one point: the normal case must stay quiet
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.jsonl")
        _write_jsonl(p, [contractify(make_record(aqs=90, scenarios=[]))])
        r = _run("annotate_campaign.py", p, "-o", os.path.join(d, "o.jsonl"),
                 "--set", "point_id=SZ-CBD-01")
        assert "统一打到" not in r.stderr


def test_synth_unlabelled_matches_todays_app_output():
    """The rehearsal corpus must look like what the app emits today (no
    run.campaign), or step 2 of the runbook never gets practised — while still
    being detectable as synthetic (D-132)."""
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "raw.jsonl")
        r = _run("synth_campaign.py", "-o", out, "--points", "2", "--repeats", "1",
                 "--campaigns", "base", "--unlabelled")
        assert r.returncode == 0, r.stderr
        with open(out, encoding="utf-8") as f:
            rec = json.loads(f.readline())
        assert "campaign" not in rec["run"]
        assert isinstance(rec["synthetic"], dict)   # still launder-proof


def test_annotate_is_idempotent():
    """Re-annotating an already-labelled corpus must be a no-op: labels already
    on the record win over every layer (D-130 check of the documented rule)."""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "a.jsonl")
        _write_jsonl(src, [contractify(make_record(aqs=90, scenarios=[]))
                           for _ in range(3)])
        first, second = os.path.join(d, "1.jsonl"), os.path.join(d, "2.jsonl")
        args = ("--set", "point_id=P1", "--set", "carrier=cmcc")
        assert _run("annotate_campaign.py", src, "-o", first, *args).returncode == 0
        r2 = _run("annotate_campaign.py", first, "-o", second, *args)
        assert r2.returncode == 0, r2.stderr
        assert "annotated 0/3" in r2.stderr          # nothing left to fill
        assert open(first, encoding="utf-8").read() == \
            open(second, encoding="utf-8").read()


def test_annotate_warns_when_one_tier_is_stamped_across_files():
    """A cell holds THREE tier rounds measured back to back, so a per-point
    directory normally contains all three. Stamping it `--set tier=metro` labels
    the other two away: the report then reports TIER_MISSING about rounds that
    were measured, the three-tier differential never happens, and the heat card's
    TIER_INCOMPLETE cannot fire either because the corpus is now single-tier.

    Walking the runbook literally produced exactly that — its example ran ONE
    annotate per point while its own red line demands three tier rounds per cell
    (D-189). Warn, not refuse: several files from one tier round is legitimate
    and the tool cannot tell the two cases apart."""
    with tempfile.TemporaryDirectory() as d:
        src, out = os.path.join(d, "raw"), os.path.join(d, "out")
        os.makedirs(src)
        for name in ("r_metro.jsonl", "r_regional.jsonl", "r_core.jsonl"):
            _write_jsonl(os.path.join(src, name),
                         [contractify(r) for r in aqs_records(90, 1)])
        r = _run("annotate_campaign.py", os.path.join(src, "*.jsonl"),
                 "--out-dir", out, "--set", "tier=metro")
        assert r.returncode == 0                     # a warning, not a refusal
        assert "tier=metro" in r.stderr
        assert "标没" in r.stderr                    # says what goes wrong…
        assert "TIER_MISSING" in r.stderr            # …and how it will surface
        # a single file is the normal per-round case and must stay quiet
        one = _run("annotate_campaign.py", os.path.join(src, "r_metro.jsonl"),
                   "-o", os.path.join(d, "one.jsonl"), "--set", "tier=metro")
        assert one.returncode == 0
        assert "标没" not in one.stderr


def test_annotate_out_dir_refuses_to_overwrite_inputs():
    """--out-dir pointing at the input directory would be --inplace in disguise."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "a.jsonl")
        _write_jsonl(path, [contractify(r) for r in aqs_records(90, 1)])
        r = _run("annotate_campaign.py", path, "--out-dir", d, "--set", "point_id=P1")
        assert r.returncode != 0
        assert "overwrite the input" in r.stderr


def test_annotate_out_dir_refuses_basename_collision():
    """Same filename from two directories would silently clobber one another."""
    with tempfile.TemporaryDirectory() as d:
        a, b = os.path.join(d, "day1"), os.path.join(d, "day2")
        os.makedirs(a)
        os.makedirs(b)
        for base in (a, b):
            _write_jsonl(os.path.join(base, "p1.jsonl"),
                         [contractify(r) for r in aqs_records(90, 1)])
        r = _run("annotate_campaign.py", os.path.join(a, "p1.jsonl"),
                 os.path.join(b, "p1.jsonl"), "--out-dir", os.path.join(d, "out"),
                 "--set", "point_id=P1")
        assert r.returncode != 0
        assert "collide" in r.stderr


def test_analyze_results_cli_runs():
    """Per-run layer entry point — never covered before (D-108)."""
    with tempfile.TemporaryDirectory() as d:
        r = _run("analyze_results.py", _fixture(d))
        assert r.returncode == 0, r.stderr
        assert "results summary" in r.stdout


def test_dashboard_cli_runs():
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "dash.html")
        r = _run("dashboard.py", _fixture(d), "-o", out)
        assert r.returncode == 0, r.stderr
        assert os.path.exists(out)


def test_annotate_cli_runs():
    with tempfile.TemporaryDirectory() as d:
        f = _fixture(d)
        out = os.path.join(d, "out.jsonl")
        r = _run("annotate_campaign.py", f, "-o", out,
                 "--set", "point_id=P1", "--infer-time-band")
        assert r.returncode == 0, r.stderr
        assert os.path.exists(out)


# Every place annotate can send its output. 「不覆盖输入（除非 --inplace）」 names
# all four, and only --out-dir had the input checked; --inplace was never run at
# all, so the other direction — that the flag does rewrite the file — had nothing
# behind it either, and a no-op --inplace looks exactly like success (D-236).
_OUTPUT_MODES = {
    "stdout": lambda d, src: [src],
    "-o": lambda d, src: [src, "-o", os.path.join(d, "out.jsonl")],
    "--out-dir": lambda d, src: [src, "--out-dir", os.path.join(d, "labeled")],
    "--inplace": lambda d, src: [src, "--inplace"],
}


def test_only_inplace_ever_writes_back_to_the_input():
    """The input corpus is a field day nobody can re-run. Whether it survives is
    decided by which output flag was passed, so each of the four is checked, and
    the check is a biconditional: the bytes move exactly when --inplace is."""
    import hashlib

    for mode, argv in _OUTPUT_MODES.items():
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "a.jsonl")
            _write_jsonl(src, [contractify(make_record(aqs=90, scenarios=[]))
                               for _ in range(2)])
            with open(src, "rb") as fh:
                before = hashlib.sha256(fh.read()).hexdigest()
            r = _run("annotate_campaign.py", *argv(d, src), "--set", "point_id=P1")
            assert r.returncode == 0, f"{mode}: {r.stderr}"
            with open(src, "rb") as fh:
                after = hashlib.sha256(fh.read()).hexdigest()

            assert (before != after) == (mode == "--inplace"), (
                f"{mode}: the input file was "
                + ("rewritten" if before != after else "left alone")
                + " — only --inplace may touch it, and it must")

            if mode == "--inplace":      # the label has to land, not just bytes move
                with open(src, encoding="utf-8") as fh:
                    rec = json.loads(fh.readline())
                assert rec["run"]["campaign"]["point_id"] == "P1", (
                    "--inplace rewrote the file without applying the label")


# The three things corpus_health calls ERROR, plus the corpus that has none of
# them. 「ERROR（exit 1，会让聚合出错）」 is a promise about the exit code, and
# every test for this module called it in-process — the CLI was never run, so
# nothing would have noticed main() returning 0 on a broken corpus (D-237).
def _health_corpus(kind):
    import copy

    recs = [contractify(r) for r in aqs_records(90, 3)]
    extra = []
    if kind == "claim_scope drift":
        recs[0] = copy.deepcopy(recs[0])
        recs[0]["claim_scope"] = "something_else_entirely"
    elif kind == "malformed line":
        extra = ["{not json at all"]
    elif kind == "same run_id, two bodies":
        twin = copy.deepcopy(recs[0])
        twin["run"]["aqs"]["score"] = 12.0
        recs = recs + [twin]
    return recs, extra


_HEALTH_CASES = {
    "clean": 0,
    "claim_scope drift": 1,
    "malformed line": 1,
    "same run_id, two bodies": 1,
}


def test_corpus_health_exit_code_matches_its_verdict():
    """Whoever runs this at the front door reads the exit code, not the table."""
    for kind, expected in _HEALTH_CASES.items():
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.jsonl")
            recs, extra = _health_corpus(kind)
            with open(path, "w", encoding="utf-8") as fh:
                for r in recs:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                for line in extra:
                    fh.write(line + "\n")

            r = _run("corpus_health.py", path)
            assert r.returncode == expected, (
                f"{kind}: exit {r.returncode}, expected {expected} — the gate's "
                "verdict and its exit code disagree\n" + (r.stdout or "")[:400])
            said_error = "## ERROR" in (r.stdout or "")
            assert said_error == bool(expected), (
                f"{kind}: printed ERROR={said_error} but exited {r.returncode} — "
                "the page and the exit code have to say the same thing")


def _labelled(n, aqs=90, campaign="base"):
    out = []
    for r in aqs_records(aqs, n):
        r["run"]["campaign"] = {"campaign_id": campaign, "tier": "metro",
                                "point_id": "P1", "carrier": "cmcc",
                                "time_band": "busy"}
        out.append(contractify(r))
    return out


def test_publish_check_exit_code_is_decided_by_fail_alone():
    """publish_check says "Exit 0 = no FAIL (WARNs may remain), 1 = at least one
    FAIL" — the number that decides whether a report ships. Nothing invoked it:
    not a test, not verify_all. And D-229 had just added a fourth severity to the
    very rows it counts, so「N/A 不影响退出码」was a promise nobody was keeping
    watch over (D-238).
    """
    import synth_campaign as sc

    corpora = {
        "clean single campaign": _labelled(6),
        "thin but honest": _labelled(2),
        "two campaigns": _labelled(6) + _labelled(6, aqs=70, campaign="opt"),
        "synthetic": sc.generate(points=1, repeats=2, campaigns=("base",),
                                 carriers=("cmcc",), time_bands=("busy",),
                                 tiers=("metro",)),
    }

    seen_exits, warn_and_na_at_exit_zero = set(), 0
    for name, recs in corpora.items():
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.jsonl")
            _write_jsonl(path, recs)
            r = _run("publish_check.py", path)
            out = r.stdout or ""
            fails = out.count("⛔ FAIL")
            assert r.returncode == (1 if fails else 0), (
                f"{name}: {fails} FAIL row(s) but exit {r.returncode} — the exit "
                "code is what decides whether this report ships\n" + out[:400])
            seen_exits.add(r.returncode)
            if r.returncode == 0 and out.count("⚠ WARN") and out.count("➖ N/A"):
                warn_and_na_at_exit_zero += 1

    assert seen_exits == {0, 1}, (
        f"only exit {sorted(seen_exits)} occurred — one side of the contract was "
        "never exercised")
    assert warn_and_na_at_exit_zero >= 2, (
        f"only {warn_and_na_at_exit_zero} corpora exited 0 while carrying both "
        "WARN and N/A rows — 「WARN 可以留着」 and 「N/A 不改判」 went unchecked")


def _encodable_in_gbk(ch):
    try:
        ch.encode("gbk")
    except (UnicodeEncodeError, LookupError):
        return False
    return True


# CLIs whose output carries marks a GBK console cannot encode. corpus_health is
# not one of them — it prints no severity icon at all, which the assertion below
# said so plainly when this list first named it. The test proves membership per
# run rather than trusting the list: a tool that stops printing them fails here
# instead of quietly passing.
_ICON_CLIS = ("publish_check.py", "campaign_report.py")


def test_the_cli_survives_a_gbk_console():
    """This file's docstring says it catches 「exactly the Windows GBK/U+26A0 case
    fixed via force_utf8_stdout」. It did not: _run passes no environment, so every
    child inherits the parent's UTF-8 and that path is never taken. Switching
    force_utf8_stdout off leaves the whole suite green (D-240), while under a GBK
    console the first ⚠ becomes UnicodeEncodeError and the tool exits 1 (D-241).
    """
    exercised = 0
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "a.jsonl")
        _write_jsonl(path, _labelled(4))

        for script in _ICON_CLIS:
            utf8 = _run(script, path)
            unencodable = [ch for ch in (utf8.stdout or "")
                           if not _encodable_in_gbk(ch)]
            assert unencodable, (
                f"{script} no longer prints anything a GBK console would choke "
                "on — this case is not being exercised any more")

            env = dict(os.environ, PYTHONIOENCODING="gbk")
            gbk = subprocess.run(
                [sys.executable, os.path.join(SCRIPTS, script), path],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", cwd=SCRIPTS, env=env)
            exercised += 1
            assert gbk.returncode == utf8.returncode, (
                f"{script}: exits {gbk.returncode} on a GBK console but "
                f"{utf8.returncode} on a UTF-8 one — the console encoding is "
                f"deciding the verdict\n  {(gbk.stderr or '')[-300:]}")

    assert exercised == len(_ICON_CLIS), exercised


_BOM = b"\xef\xbb\xbf"


def test_the_json_an_operator_writes_may_carry_a_bom():
    """Notepad, VS Code's default and PowerShell's `Set-Content -Encoding utf8`
    all emit a BOM, and Windows is this project's primary platform.

    The corpus loader already answers a BOM by name — it prints the file, the
    line and `decode using utf-8-sig`, and the front-door gate then refuses to
    report. The two JSON files a HUMAN writes, the coverage grid and the
    annotate mapping, were opened as plain utf-8 with a bare json.load: the
    operator's daily coverage check ended in a traceback instead (D-272).

    A traceback is the thing being guarded against, not merely the exit code —
    a tool that dies without saying what to fix has failed the operator even
    when the exit code is correct.
    """
    with tempfile.TemporaryDirectory() as d:
        corpus = os.path.join(d, "a.jsonl")
        _write_jsonl(corpus, _labelled(6))

        grid = os.path.join(d, "grid.json")
        with open(grid, "wb") as fh:
            fh.write(_BOM + b'{"point_id": ["P1"], "carrier": ["cmcc"], '
                            b'"time_band": ["busy"]}')
        with open(grid, "rb") as fh:
            assert fh.read(3) == _BOM, "the fixture carries no BOM to be read"

        mapping = os.path.join(d, "map.json")
        with open(mapping, "wb") as fh:
            fh.write(_BOM + b'{"P1": {"tier": "metro"}}')

        bad = os.path.join(d, "bad.json")
        with open(bad, "wb") as fh:
            fh.write(b'{"point_id": [')

        def run(script, *args):
            return subprocess.run(
                [sys.executable, os.path.join(SCRIPTS, script)] + list(args),
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", cwd=SCRIPTS)

        cov = run("coverage_matrix.py", corpus, "--config", grid)
        assert "Traceback" not in (cov.stdout + cov.stderr), cov.stderr[-400:]
        assert cov.returncode == 0, cov.stderr[-400:]

        out = os.path.join(d, "out.jsonl")
        ann = run("annotate_campaign.py", corpus, "-o", out, "--map", mapping)
        assert "Traceback" not in (ann.stdout + ann.stderr), ann.stderr[-400:]
        assert ann.returncode == 0, ann.stderr[-400:]

        broken = run("coverage_matrix.py", corpus, "--config", bad)
        blob = broken.stdout + broken.stderr
        assert broken.returncode != 0, "malformed JSON was accepted"
        assert "Traceback" not in blob, (
            "a hand-written file with a typo still ends in a traceback: " + blob[-400:])
        assert bad in blob and "example" in blob, (
            "the message names neither the file nor what a good one looks "
            "like: " + blob[-400:])


def test_the_runner_reports_a_failure_it_cannot_print():
    """A failure line is assertion text, and assertion text quotes the report,
    which carries marks like the warning sign. The runner printed it bare, so
    on a GBK console the first such failure raised UnicodeEncodeError from
    inside the reporting loop: the operator got a traceback where the finding
    should be, and every failure after that one was never printed at all.

    D-241 hardened the CLIs against this console. This is the runner that
    reports on them, and nothing had pointed the same question at it (D-265).
    """
    import io
    import run_all

    class _Gbk(io.StringIO):
        """Refuses the same characters a GBK console refuses, on any machine."""
        encoding = "gbk"

        def write(self, s):
            s.encode(self.encoding)
            return io.StringIO.write(self, s)

    line = "  FAIL test_x: 缺 ⚠并列good/poor — 见热力卡"
    assert [c for c in line if not _encodable_in_gbk(c)], (
        "the sample carries nothing a GBK console chokes on — this test would "
        "pass whether or not the runner were fixed")

    real = sys.stdout
    try:
        sys.stdout = _Gbk()
        raised = False
        try:
            print(line)
        except UnicodeEncodeError:
            raised = True
        sys.stdout = shown = _Gbk()
        run_all._say(line)
        text = shown.getvalue()
    finally:
        sys.stdout = real

    assert raised, "a bare print survives this console — the hazard is gone " \
                   "and this guard is now measuring nothing"
    assert "\\u26a0" in text, text        # the mark is reported, as an escape
    assert "并列good/poor" in text, text  # Chinese is not collateral damage
    assert "见热力卡" in text, text
    assert "FAIL test_x" in text, text
