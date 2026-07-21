#!/usr/bin/env python3
"""ANEB corpus integrity preflight (stdlib only).

Run this BEFORE trusting any campaign report: an analysis is only as honest as
the corpus under it. Surfaces the failure modes that silently corrupt aggregates
rather than crashing loudly:

  ERROR (exit 1) — findings that make aggregates WRONG:
    * conflicting duplicate run_id  : one run_id, two different bodies
    * malformed / unparseable lines : silent data loss on load
    * claim_scope drift             : records from a different measurement scope
                                      pooled into one median (R-10 red line)
    * missing run body              : record cannot be attributed to a run
  WARN (exit 0) — findings worth knowing, not corrupting:
    * benign duplicate run_id       : identical re-export (expected with D-09
                                      dual-write); de-duplicated on load
    * records with no run_id        : cannot be de-duplicated, kept as-is
    * mixed schema_version          : contract drift across the corpus
    * missing AQS / campaign labels : coverage gaps the report will show

Usage:
    python corpus_health.py results/*.jsonl [--json]
"""
import argparse
import json
import sys
from collections import Counter

import campaign_common as cc


def analyze(records, stats):
    """Integrity findings over loaded records + the loader's stats dict."""
    schema_versions, scopes = Counter(), Counter()
    missing_run = missing_scenarios = no_aqs = no_campaign = 0
    started = []
    for rec in records:
        schema_versions[rec.get("schema_version") or "absent"] += 1
        scopes[rec.get("claim_scope") or "absent"] += 1
        if not rec.get("run"):
            missing_run += 1
        if not isinstance(rec.get("scenarios"), list):
            missing_scenarios += 1
        if cc.run_aqs(rec) is None:
            no_aqs += 1
        if not cc.run_obj(rec).get("campaign"):
            no_campaign += 1
        ms = cc.run_started_ms(rec)
        if ms is not None:
            started.append(ms)

    scope_drift = {k: v for k, v in scopes.items() if k != cc.CLAIM_SCOPE}
    errors, warnings = [], []

    if stats.get("conflicts"):
        errors.append("conflicting duplicate run_id (same id, different body): "
                      + ", ".join(stats["conflicts"][:5])
                      + (" …" if len(stats["conflicts"]) > 5 else ""))
    if stats.get("malformed"):
        errors.append(f"{stats['malformed']} malformed line(s) skipped on load")
    if stats.get("unreadable_files"):
        errors.append(f"{stats['unreadable_files']} unreadable file(s)")
    if scope_drift:
        errors.append("claim_scope drift (not comparable, must not be pooled): "
                      + json.dumps(scope_drift, ensure_ascii=False))
    if missing_run:
        errors.append(f"{missing_run} record(s) with no run body")

    benign_dupes = stats.get("duplicates", 0) - len(stats.get("conflicts", []))
    if benign_dupes > 0:
        warnings.append(f"{benign_dupes} duplicate run_id occurrence(s) de-duplicated "
                        "on load (identical re-export; would have double-counted)")
    if stats.get("no_run_id"):
        warnings.append(f"{stats['no_run_id']} record(s) with no run_id — cannot be "
                        "de-duplicated")
    if missing_scenarios:
        warnings.append(f"{missing_scenarios} record(s) with no scenarios array")
    if len(schema_versions) > 1:
        warnings.append("mixed schema_version: " + json.dumps(dict(schema_versions),
                                                              ensure_ascii=False))
    if no_aqs:
        warnings.append(f"{no_aqs}/{len(records)} record(s) without run.aqs.score")
    if no_campaign:
        warnings.append(f"{no_campaign}/{len(records)} record(s) without run.campaign "
                        "labels (heat card / attribution will collapse to unlabeled)")

    return {
        "loaded": len(records),
        "load_stats": stats,
        "schema_versions": dict(schema_versions),
        "claim_scopes": dict(scopes),
        "span_epoch_ms": [min(started), max(started)] if started else None,
        "errors": errors,
        "warnings": warnings,
        "healthy": not errors,
    }


def render_markdown(rep, files):
    st = rep["load_stats"]
    lines = [
        "# ANEB 语料完整性体检",
        "",
        f"- 文件：{len(files)}；读到行：{st.get('lines', 0)}；保留记录：{rep['loaded']}",
        f"- 去重丢弃：{st.get('duplicates', 0)}（其中冲突 {len(st.get('conflicts', []))}）"
        f"；无 run_id：{st.get('no_run_id', 0)}；坏行：{st.get('malformed', 0)}",
        f"- schema_version：{rep['schema_versions']}",
        f"- claim_scope：{rep['claim_scopes']}",
    ]
    if rep["span_epoch_ms"]:
        lines.append(f"- 时间跨度(epoch ms)：{rep['span_epoch_ms'][0]} → {rep['span_epoch_ms'][1]}")
    lines.append("")
    if rep["errors"]:
        lines.append("## ERROR（会使聚合结果错误，必须处理）")
        lines += [f"- {e}" for e in rep["errors"]]
        lines.append("")
    if rep["warnings"]:
        lines.append("## WARN（需知悉，不致错）")
        lines += [f"- {w}" for w in rep["warnings"]]
        lines.append("")
    lines.append("**结论：** " + ("语料可用于出报告。" if rep["healthy"]
                                 else "存在 ERROR 级问题，报告前请先修复。"))
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB corpus integrity preflight")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    stats = {}
    recs, files = cc.load_records(args.inputs, stats=stats, quiet=True)
    rep = analyze(recs, stats)
    print(json.dumps(rep, ensure_ascii=False, indent=2) if args.json
          else render_markdown(rep, files))
    if not recs:
        print("no records loaded", file=sys.stderr)
        return 2
    return 0 if rep["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
