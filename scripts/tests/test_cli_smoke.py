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


def _run(script, *args):
    return subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, script), *args],
        capture_output=True, text=True, encoding="utf-8", cwd=SCRIPTS)


def _fixture(d):
    recs = [contractify(r) for r in
            (tier_records("metro", "n1_rtt_p50_ms", 20, 5)
             + tier_records("regional", "n1_rtt_p50_ms", 35, 5)
             + tier_records("core", "n1_rtt_p50_ms", 60, 5)
             + aqs_records(90, 5))]
    path = os.path.join(d, "in.jsonl")
    _write_jsonl(path, recs)
    return path


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
