#!/usr/bin/env python3
"""ANEB campaign access-medium (transport) comparison rollup (stdlib only).

Answers the operator-meeting question no other tool covers: at this point /
carrier / time band, is CELLULAR actually worse than WIFI? (survey gap 1: both
`run.transport` and per-scenario `network_snapshot.transport` were consumed by
no analysis tool at all.)

Transport resolution per run (honesty first, R-10):
    run.transport wifi|cellular  -> taken as-is (explicit setting)
    run.transport auto/missing   -> derived from the OBSERVED per-scenario
        network_snapshot.transport values: all agree -> that value;
        disagree -> "mixed"; none observed -> "unknown"
"unknown" and "mixed" stay separate buckets — never silently merged into a
medium, and a cell where everything is unknown is a coverage gap, not data.

Per (point_id, carrier, time_band): per-transport run count + AQS median, and
the cellular-minus-wifi AQS delta when BOTH media are present (AQS higher =
better, so a negative delta reads "cellular worse here").

Usage:
    python transport_rollup.py results/*.jsonl
"""
import argparse
import re
import sys
from collections import defaultdict

import campaign_common as cc

CELL_DIMS = ("point_id", "carrier", "time_band")
EXPLICIT = ("wifi", "cellular")


def _medium(s):
    """Normalize one transport string to wifi|cellular|None. The real producer
    writes the RESOLVED medium in a compound form — e.g. `auto(cellular)`
    (observed on real corpus, D-110) — so the parenthesized part wins."""
    if not isinstance(s, str) or not s:
        return None
    s = s.lower()
    if s in EXPLICIT:
        return s
    m = re.fullmatch(r"\w+\((wifi|cellular)\)", s)
    return m.group(1) if m else None


def resolve_transport(rec):
    """One transport label per run: explicit setting, else observed consensus."""
    t = _medium((rec.get("run") or {}).get("transport"))
    if t:
        return t
    seen = set()
    for scn in cc.iter_scenarios(rec):
        ns = scn.get("network_snapshot")
        if isinstance(ns, dict):
            o = _medium(ns.get("transport"))
            if o:
                seen.add(o)
    if not seen:
        return "unknown"
    return seen.pop() if len(seen) == 1 else "mixed"


def transport_cells(records, min_samples=cc.DEFAULT_MIN_SAMPLES):
    buckets = defaultdict(lambda: defaultdict(lambda: {"aqs": [], "n": 0}))
    for rec in records:
        labels = cc.campaign_labels(rec)
        key = tuple(labels[d] for d in CELL_DIMS)
        g = buckets[key][resolve_transport(rec)]
        g["n"] += 1
        score = cc.run_aqs(rec)
        if score is not None:
            g["aqs"].append(score)

    cells = []
    for key in sorted(buckets):
        by_t = {}
        for t, g in buckets[key].items():
            by_t[t] = {"n": g["n"],
                       "aqs_median": cc.median(g["aqs"]) if g["aqs"] else None,
                       "low_confidence": g["n"] < min_samples}
        wifi, cell = by_t.get("wifi"), by_t.get("cellular")
        delta = None
        if wifi and cell and wifi["aqs_median"] is not None and cell["aqs_median"] is not None:
            delta = cell["aqs_median"] - wifi["aqs_median"]
        cells.append({
            "cell": dict(zip(CELL_DIMS, key)),
            "transports": by_t,
            # cellular - wifi on AQS (higher = better): negative => cellular worse
            "cellular_minus_wifi": delta,
        })
    return cells


def analyze(records, min_samples=cc.DEFAULT_MIN_SAMPLES):
    cells = transport_cells(records, min_samples)
    only_unknown = all(set(c["transports"]) <= {"unknown"} for c in cells) if cells else True
    return {"cells": cells, "min_samples": min_samples, "only_unknown": only_unknown}


def _fmt_bucket(b):
    if not b:
        return "—"
    lc = "*" if b["low_confidence"] else ""
    return f"{cc.fmt_num(b['aqs_median'])} (n={b['n']}{lc})"


def render_markdown(res):
    lines = [
        "## 接入介质对比（wifi vs cellular，AQS 中位）",
        "",
        "> transport 取 run 显式设置，`auto` 由各场景 `network_snapshot` 观测共识推得；"
        "不一致=mixed、无观测=unknown，**均不并入任何介质**。Δ=cellular−wifi"
        "（AQS 越大越好，负值=蜂窝更差）。* = 样本不足。",
        "",
    ]
    if res["only_unknown"]:
        lines.append("_无 transport 证据（run 均为 auto 且无 network_snapshot 观测）——覆盖缺口，非数据。_")
        return "\n".join(lines)
    lines += ["| 点位 | 运营商 | 时段 | wifi | cellular | Δ(cell−wifi) | 其他桶 |",
              "|---|---|---|---|---|---|---|"]
    for c in res["cells"]:
        cl = c["cell"]
        others = [f"{t}:n={b['n']}" for t, b in sorted(c["transports"].items())
                  if t not in EXPLICIT]
        lines.append(
            f"| {cl['point_id']} | {cl['carrier']} | {cl['time_band']} | "
            f"{_fmt_bucket(c['transports'].get('wifi'))} | "
            f"{_fmt_bucket(c['transports'].get('cellular'))} | "
            f"{cc.fmt_num(c['cellular_minus_wifi'])} | {'; '.join(others) or '—'} |")
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB campaign transport comparison rollup")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--min-samples", type=int, default=cc.DEFAULT_MIN_SAMPLES)
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    recs, files = cc.load_records(args.inputs)
    res = analyze(recs, args.min_samples)
    print(render_markdown(res))
    print(f"\n<!-- records={len(recs)} files={len(files)} cells={len(res['cells'])} -->",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
