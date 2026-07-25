#!/usr/bin/env python3
"""ANEB campaign measurement-trust rollup (stdlib only).

The heat cards present timing medians; this table answers "can the instrument
behind those medians be trusted in this cell?" — three previously-unconsumed
evidence blocks (survey gaps 3 + 10):

  clock  — scenarios[].clock.offset_suspect (R-22: |drift|>100ppm or missing
           endpoint) + drift_ppm. A suspect clock means that scenario's
           TTFT/ITL numbers may be unreliable.
  stream — kpi.seq_gap_count / seq_dup_count. A nonzero gap/dup is a
           data-quality red flag on that scenario's stream KPIs.
  parse  — parse.per_event_parse_us. Client parse overhead confounds ITL/TTFT
           (device compute vs network) — worth a caveat when it is large.

Honesty (R-10): each signal keeps its OWN denominator (scenarios that actually
carry the annotation); unannotated scenarios are counted as "未标注", never as
clean. A cell with no evidence at all renders a coverage note, not zeros.
A majority-suspect-clock cell is flagged 时钟可疑热点 (strictly > 0.5).

Usage:
    python trust_rollup.py results/*.jsonl
"""
import argparse
import sys
from collections import defaultdict

import campaign_common as cc

CELL_DIMS = ("point_id", "carrier", "time_band")
# Share of ANNOTATED clocks that must be suspect for the cell to be a hot-spot.
# Named so the provenance manifest can record it (D-122).
CLOCK_HOTSPOT_SHARE = 0.5


def _bucket():
    return {"scenarios": 0,
            "clock_annotated": 0, "clock_suspect": 0, "drift_abs": [],
            "stream_counted": 0, "stream_bad": 0,
            "parse_us": []}


def trust_cells(records, min_samples=cc.DEFAULT_MIN_SAMPLES):
    buckets = defaultdict(_bucket)
    for rec in records:
        labels = cc.campaign_labels(rec)
        key = tuple(labels[d] for d in CELL_DIMS)
        for scn in cc.iter_scenarios(rec):
            g = buckets[key]
            g["scenarios"] += 1

            clock = scn.get("clock")
            if isinstance(clock, dict) and isinstance(clock.get("offset_suspect"), bool):
                g["clock_annotated"] += 1
                if clock["offset_suspect"]:
                    g["clock_suspect"] += 1
                drift = cc.fnum(clock.get("drift_ppm"))
                if drift is not None:
                    g["drift_abs"].append(abs(drift))

            kpi = scn.get("kpi") if isinstance(scn.get("kpi"), dict) else {}
            gap, dup = cc.fnum(kpi.get("seq_gap_count")), cc.fnum(kpi.get("seq_dup_count"))
            if gap is not None or dup is not None:
                g["stream_counted"] += 1
                if (gap or 0) > 0 or (dup or 0) > 0:
                    g["stream_bad"] += 1

            parse = scn.get("parse")
            if isinstance(parse, dict):
                v = cc.fnum(parse.get("per_event_parse_us"))
                if v is not None:
                    g["parse_us"].append(v)

    cells = []
    for key in sorted(buckets):
        g = buckets[key]
        ca, cs = g["clock_annotated"], g["clock_suspect"]
        suspect_share = (cs / ca) if ca else None
        cells.append({
            "cell": dict(zip(CELL_DIMS, key)),
            "scenarios": g["scenarios"],
            "clock_annotated": ca,
            "clock_suspect": cs,
            "clock_suspect_share": suspect_share,
            "abs_drift_ppm_median": cc.median(g["drift_abs"]) if g["drift_abs"] else None,
            "stream_counted": g["stream_counted"],
            "stream_bad": g["stream_bad"],
            "parse_per_event_us_median": cc.median(g["parse_us"]) if g["parse_us"] else None,
            # majority of annotated clocks suspect => timing medians untrustworthy here
            "clock_hotspot": bool(suspect_share is not None
                                  and suspect_share > CLOCK_HOTSPOT_SHARE),
            "low_confidence": g["scenarios"] < min_samples,
        })
    return cells


def analyze(records, min_samples=cc.DEFAULT_MIN_SAMPLES):
    cells = trust_cells(records, min_samples)
    no_evidence = all(c["clock_annotated"] == 0 and c["stream_counted"] == 0
                      and c["parse_per_event_us_median"] is None for c in cells)
    return {"cells": cells, "min_samples": min_samples,
            "no_evidence": no_evidence if cells else True}


def render_markdown(res):
    lines = [
        "## 测量可信度（时钟 / 流完整性 / 解析开销）",
        "",
        "> 上方时延中位数背后的**仪器**可信度：时钟可疑=R-22（|漂移|>100ppm 或端点缺失），"
        "该场景 TTFT/ITL 存疑；seq 异常=gap/dup>0；解析开销大会混淆 ITL（端侧算力≠网络）。"
        "各信号分母=实际带标注的场景数，未标注**不算干净**。时钟可疑过半标 `时钟可疑热点`。",
        "",
    ]
    if res["no_evidence"]:
        lines.append("_无可信度证据（clock/seq/parse 块均未标注）——覆盖缺口，非全部可信。_")
        return "\n".join(lines)
    lines += ["| 点位 | 运营商 | 时段 | 场景 | 时钟标注 | 时钟可疑 | 漂移中位 ppm | seq 异常 | 解析 us 中位 | 备注 |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for c in res["cells"]:
        cl = c["cell"]
        share = "—" if c["clock_suspect_share"] is None \
            else f"{c['clock_suspect']} ({c['clock_suspect_share'] * 100:.0f}%)"
        stream = "—" if not c["stream_counted"] else f"{c['stream_bad']}/{c['stream_counted']}"
        notes = []
        if c["clock_hotspot"]:
            notes.append("**时钟可疑热点**")
        if c["low_confidence"]:
            notes.append("low_conf")
        lines.append(
            f"| {cl['point_id']} | {cl['carrier']} | {cl['time_band']} | {c['scenarios']} | "
            f"{c['clock_annotated']} | {share} | {cc.fmt_num(c['abs_drift_ppm_median'])} | "
            f"{stream} | {cc.fmt_num(c['parse_per_event_us_median'])} | "
            f"{'; '.join(notes) or '—'} |")
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB campaign measurement-trust rollup")
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
