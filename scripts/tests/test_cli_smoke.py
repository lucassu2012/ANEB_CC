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

from synth import aqs_records, contractify, tier_records


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
                       "_comparison", "_trend"):
            assert os.path.exists(csv_prefix + suffix + ".csv"), suffix


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
