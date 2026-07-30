#!/usr/bin/env python3
"""ANEB results analyzer (stdlib only) — precursor of the phase-3 dashboard.

Usage:
    python analyze_results.py data/results/*.jsonl [--csv out.csv]

Reads server-side results JSONL (one JSON object per line, contract schema 1.0)
and prints a markdown summary: run inventory, validity breakdown, per-scenario
KPI medians, AQS distribution. Tolerant of missing/unknown fields — the schema
is still evolving (kpi_set / aqs_version are read from the records themselves).
"""
import json
import sys
import glob
import math
import statistics
from collections import defaultdict


def load_records(patterns, stats=None):
    """Load JSONL records, de-duplicating by `run.run_id` (first wins).

    Mirrors campaign_common.load_records' rule. Measured before this was added:
    listing the same file twice — trivial with overlapping globs, or with D-09
    dual-write files — turned a 20-run corpus into `records: 40` and doubled
    every per-scenario n. Nothing was wrong on screen; the numbers were simply
    inflated, which is the exact failure the campaign loader exists to prevent
    (D-315). A record with no run_id cannot be deduped: it is always kept, never
    merged under a fabricated key (R-10).

    Pass a dict as `stats` to receive the counters, under campaign_common's key
    names and with its meanings: lines (non-blank lines seen, malformed
    included), kept, malformed, duplicates, no_run_id. Reading one loader's
    counters with another's vocabulary is a live trap — it printed a plausible
    「读 2 行」 for a three-line corpus once, because `.get()` turned a mistyped
    key into a default (D-325). Copies may stay; divergence may not (§2.14).
    """
    records, seen = [], set()
    st = {"lines": 0, "kept": 0, "malformed": 0, "duplicates": 0, "no_run_id": 0}
    for pat in patterns:
        for path in glob.glob(pat):
            with open(path, encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    # counted where campaign_common counts it: a line seen,
                    # malformed included, before any parse can reject it
                    st["lines"] += 1
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError as e:
                        st["malformed"] += 1
                        print(f"<!-- skip {path}:{lineno}: {e} -->", file=sys.stderr)
                        continue
                    rid = (rec.get("run") or {}).get("run_id") if isinstance(rec, dict) else None
                    if rid is None:
                        st["no_run_id"] += 1
                    else:
                        if rid in seen:
                            st["duplicates"] += 1
                            continue
                        seen.add(rid)
                    records.append(rec)
                    st["kept"] += 1
    if stats is not None:
        stats.update(st)
    return records


def fnum(v):
    """Numeric-or-None guard. Mirrors campaign_common.fnum, including D-148's
    rejection of NaN/±Infinity — which this copy did not have.

    Python's json module accepts the bare NaN/Infinity literals even though the
    JSON spec forbids them, so a producer or a converting tool can put one in a
    corpus. Measured here before fixing: one NaN in one scenario's t1_ttft_ms
    made this tool print `| t1_ttft_ms | nan | 20 |` — the median of twenty
    samples destroyed by one of them, exit 0, no warning (D-314).
    """
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return None
    return v if math.isfinite(v) else None


def median_or_none(vals):
    # Defence in depth, as campaign_common._finite is for the campaign layer: no
    # path may smuggle a non-finite value into a sort, because NaN does not just
    # spoil its own row, it poisons its neighbours' median (D-148/D-314).
    vals = [v for v in vals
            if v is not None and not (isinstance(v, float) and not math.isfinite(v))]
    return statistics.median(vals) if vals else None


def main(argv):
    csv_out = None
    if "--csv" in argv:
        i = argv.index("--csv")
        csv_out = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if not argv:
        print(__doc__)
        return 1

    stats = {}
    recs = load_records(argv, stats)
    # Direct subscript, not .get with a default: a mistyped key must be visible,
    # not quietly replaced by a plausible number (D-325).
    dup = stats["duplicates"]
    # Say what was dropped. A loader that silently discards half its input is
    # the mirror image of one that silently counts it twice (D-315).
    note = f" (read {stats['lines']} lines, dropped {dup} repeat run_id)" if dup else ""
    print(f"# ANEB results summary\n\nrecords: **{len(recs)}**{note}\n")
    if not recs:
        return 0

    by_version = defaultdict(int)
    validity = defaultdict(int)
    aqs_vals = []
    # scenario -> kpi -> [values]
    kpis = defaultdict(lambda: defaultdict(list))

    for r in recs:
        by_version[(r.get("kpi_set", "?"), r.get("aqs_version", "?"),
                    r.get("schema_version", "?"))] += 1
        # 实际上报体（ResultReporter.kt）：AQS 在 run.aqs.score；保留旧路径兜底
        aqs = fnum(((r.get("run") or {}).get("aqs") or {}).get("score"))
        if aqs is None:
            aqs = fnum(r.get("aqs")) or fnum((r.get("aqs_result") or {}).get("score"))
        if aqs is not None:
            aqs_vals.append(aqs)
        for s in r.get("scenarios", []) or []:
            # 实际字段：profile_id + kpi（不是 scenario_id/kpis）；*_grade 为字符串分级，跳过
            sid = s.get("profile_id") or s.get("scenario_id") or "?"
            validity[s.get("validity", "?")] += 1
            for k, v in (s.get("kpi") or s.get("kpis") or {}).items():
                if k.endswith("_grade"):
                    continue
                val = fnum(v) if not isinstance(v, dict) else fnum(v.get("value"))
                if val is not None:
                    kpis[sid][k].append(val)

    print("## versions\n")
    print("| kpi_set | aqs | schema | runs |")
    print("|---|---|---|---|")
    for (k, a, sv), n in sorted(by_version.items()):
        print(f"| {k} | {a} | {sv} | {n} |")

    print("\n## validity (scenario level)\n")
    print("| validity | count |")
    print("|---|---|")
    for k, n in sorted(validity.items()):
        print(f"| {k} | {n} |")

    if aqs_vals:
        print("\n## AQS\n")
        print(f"- n={len(aqs_vals)} median={statistics.median(aqs_vals):.1f} "
              f"min={min(aqs_vals):.1f} max={max(aqs_vals):.1f}")

    print("\n## per-scenario KPI medians\n")
    for sid in sorted(kpis):
        print(f"### {sid}\n")
        print("| kpi | median | n |")
        print("|---|---|---|")
        for k in sorted(kpis[sid]):
            vals = kpis[sid][k]
            print(f"| {k} | {median_or_none(vals):.3f} | {len(vals)} |")
        print()

    if csv_out:
        import csv
        # utf-8-sig so Excel on a Chinese Windows does not read it as GBK (D-129)
        with open(csv_out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["scenario", "kpi", "value"])
            for sid in kpis:
                for k, vals in kpis[sid].items():
                    for v in vals:
                        w.writerow([sid, k, v])
        print(f"csv written: {csv_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
