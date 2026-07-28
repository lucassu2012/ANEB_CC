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
from collections import Counter, defaultdict

import campaign_common as cc

CELL_DIMS = ("point_id", "carrier", "time_band")
EXPLICIT = ("wifi", "cellular")


def _medium(s):
    return cc._transport_medium(s)


def resolve_transport(rec):
    """One transport label per run — see campaign_common (D-157)."""
    return cc.resolve_transport(rec)


def transport_cells(records, min_samples=cc.DEFAULT_MIN_SAMPLES):
    buckets = defaultdict(lambda: defaultdict(lambda: {"aqs": [], "n": 0}))
    implausible = defaultdict(Counter)
    for rec in records:
        labels = cc.campaign_labels(rec)
        key = tuple(labels[d] for d in CELL_DIMS)
        g = buckets[key][resolve_transport(rec)]
        g["n"] += 1
        score = cc.run_aqs(rec)
        # The heat card has excluded impossible scores since D-178 and this
        # section did not, so one AQS of 9999 left two sections of one report
        # disagreeing about whether that run counts. The median survives it; the
        # NOISE SCALE does not — a single 9999 pushed it to ±3110 on a 0..100
        # metric, and every real medium difference then reads 噪声内 (D-197).
        if score is not None and cc.keep_value("aqs_score", score, implausible[key]):
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
        # The same treatment the before/after delta got in D-144, which this
        # section never received although it is the same shape: two medians
        # differenced. On the rehearsal grid ALL SEVEN cells the summary was
        # reporting as "cellular worse than wifi" turned out to sit inside the
        # noise — a flat claim in the one section decision-makers read (D-180).
        noise = cc.noise_scale(buckets[key].get("cellular", {}).get("aqs"),
                               buckets[key].get("wifi", {}).get("aqs"))
        cells.append({
            "cell": dict(zip(CELL_DIMS, key)),
            "transports": by_t,
            # cellular - wifi on AQS (higher = better): negative => cellular worse
            "cellular_minus_wifi": delta,
            "noise": noise,
            "within_noise": cc.within_noise(delta, noise),
            "implausible_values": dict(sorted((implausible.get(key) or {}).items())),
        })
    return cells


def analyze(records, min_samples=cc.DEFAULT_MIN_SAMPLES):
    cells = transport_cells(records, min_samples)
    only_unknown = all(set(c["transports"]) <= {"unknown"} for c in cells) if cells else True
    return {"cells": cells, "min_samples": min_samples, "only_unknown": only_unknown}


def _bucket_with(b, median_str):
    """A bucket cell rendered at a caller-chosen precision, n suffix intact.

    The row prints wifi, cellular and their difference, so the precision is not
    this function's to pick: the three have to agree (D-221)."""
    if not b:
        return "—"
    lc = "*" if b["low_confidence"] else ""
    return f"{median_str} (n={b['n']}{lc})"


def _fmt_bucket(b):
    return _bucket_with(b, cc.fmt_num(b["aqs_median"])) if b else "—"


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
    # after the no-evidence early return: a noise caveat above a "no data" line
    # would be a caveat about nothing
    lines += ["> **噪声尺度**：" + cc.NOISE_CAVEAT, "",
              "| 点位 | 运营商 | 时段 | wifi | cellular | Δ(cell−wifi) | 噪声 | 备注 | 其他桶 |",
              "|---|---|---|---|---|---|---|---|---|"]
    for c in res["cells"]:
        cl = {k: cc.md_cell(v) for k, v in c["cell"].items()}   # labels are human-typed
        others = [f"{t}:n={b['n']}" for t, b in sorted(c["transports"].items())
                  if t not in EXPLICIT]
        # three states, never two: "cannot estimate" is not "no difference"
        notes = []
        if c["within_noise"] is True:
            notes.append("**噪声内**")
        elif c["within_noise"] is None and c["cellular_minus_wifi"] is not None:
            # two causes, two words: a spread of zero is not a missing spread
            notes.append(cc.noise_unjudgeable_note(c["noise"]))
        if c.get("implausible_values"):
            notes.append("**IMPLAUSIBLE_VALUE:" + "; ".join(
                f"{r}×{n}" for r, n in sorted(c["implausible_values"].items())) + "**")
        # wifi + Δ = cellular is an addition the reader can do on the row, so
        # the three share one precision (D-221).
        wb = c["transports"].get("wifi")
        cb = c["transports"].get("cellular")
        wstr, cstr, dstr, adds_up = cc.fmt_delta_row(
            wb["aqs_median"] if wb else None,
            cb["aqs_median"] if cb else None,
            c["cellular_minus_wifi"])
        if adds_up is False:
            notes.append("ROUNDING_UNRECONCILED")
        note = "; ".join(notes) or "—"
        noise = f"±{cc.fmt_num(c['noise'], 1)}" if c["noise"] is not None else "—"
        lines.append(
            f"| {cl['point_id']} | {cl['carrier']} | {cl['time_band']} | "
            f"{_bucket_with(wb, wstr)} | {_bucket_with(cb, cstr)} | "
            f"{dstr} | {noise} | {note} | "
            f"{'; '.join(others) or '—'} |")
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
