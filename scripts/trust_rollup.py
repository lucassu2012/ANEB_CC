#!/usr/bin/env python3
"""ANEB campaign measurement-trust rollup (stdlib only).

The heat cards present timing medians; this table answers "can the instrument
behind those medians be trusted in this cell?" — three previously-unconsumed
evidence blocks (survey gaps 3 + 10):

  clock  — scenarios[].clock.offset_suspect (R-22: |drift|>100ppm or missing
           endpoint) + drift_ppm. A suspect clock means that scenario's
           TTFT/ITL numbers may be unreliable.
  wall   — scenarios[].clock.wall_skew_ms (D-506/T68). drift_ppm answers "钟走得
           稳吗"; this one answers "钟指得对吗". The flag is a MARK, never a veto:
           KPI timing runs on the monotonic clock (R-24), so a wrong wall clock
           does not corrupt KPI values — it corrupts "which day this was
           measured", which is exactly what day-bucketing reads. D-494 is the
           real event this gate exists for (host+device were 10 days slow and no
           产物 could show it).
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

# 墙钟偏差判疑阈值（毫秒）。**这是 AnebClient.WALL_SKEW_MAX_MS 的跨语言副本**——
# 设备侧算得出 wallClockSuspect() 却没把那个 bool 落进 wire（clock 块只有数值
# wall_skew_ms，没有 wall_clock_suspect），所以分析层只能拿阈值自己重算。
# 副本=D-264 风险，故配一条跨端守卫（test_trust_rollup 里直接从 AnebClient.kt
# 抽字面量比对），改动任一侧都会当场变红。上游若哪天把 bool 落进 wire，
# 这里应改为直接读那个 bool、并删掉本常量（同 offset_suspect 的既有形状）。
# 值的出处=D-506：高于 RTT/NTP 正常波动 3 个量级、低于时区错(3600s)一个量级；
# 设备侧 KDoc 标 **PROVISIONAL**（有真实 skew 分布支撑前不精调），本侧同此状态。
WALL_SKEW_MAX_MS = 60_000


def wall_clock_suspect(skew_ms):
    """墙钟是否可疑。与 `AnebClient.wallClockSuspect` 同判据同语义（D-506）。

    `None`（测不出/旧生产者不带该字段）⇒ **False**——不因缺证据判疑；
    缺席由 `wall_annotated` 的分母如实表达，绝不当作"干净"。
    """
    v = cc.fnum(skew_ms)
    return v is not None and abs(v) > WALL_SKEW_MAX_MS


def _bucket():
    return {"scenarios": 0,
            "clock_annotated": 0, "clock_suspect": 0, "drift_abs": [],
            "wall_annotated": 0, "wall_suspect": 0, "skew_abs": [],
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

            # 墙钟（D-506/T68）：自己的分母——只数真的带 wall_skew_ms 的场景。
            # 与 offset_suspect 分开计，因为旧生产者带 offset_suspect 却不带
            # wall_skew_ms（EchoWire 接线之前），共用分母会把"没测"读成"没问题"。
            if isinstance(clock, dict):
                skew = cc.fnum(clock.get("wall_skew_ms"))
                if skew is not None:
                    g["wall_annotated"] += 1
                    g["skew_abs"].append(abs(skew))
                    if wall_clock_suspect(skew):
                        g["wall_suspect"] += 1

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
            "wall_annotated": g["wall_annotated"],
            "wall_suspect": g["wall_suspect"],
            "wall_suspect_share": (g["wall_suspect"] / g["wall_annotated"]
                                   if g["wall_annotated"] else None),
            "abs_wall_skew_ms_median": cc.median(g["skew_abs"]) if g["skew_abs"] else None,
            "stream_counted": g["stream_counted"],
            "stream_bad": g["stream_bad"],
            "parse_per_event_us_median": cc.median(g["parse_us"]) if g["parse_us"] else None,
            # majority of annotated clocks suspect => timing medians untrustworthy here
            "clock_hotspot": bool(suspect_share is not None
                                  and suspect_share > CLOCK_HOTSPOT_SHARE),
            "low_confidence": g["scenarios"] < min_samples,
        })
    return cells


def kpi_quality_rollup(records):
    """Corpus-level per-KPI quality (D-373): {short_name: {annotated, low,
    min_n}}. Empty dict when NO scenario carries kpi_quality — the pre-v17
    shape, reported as a collection gap rather than silence (缺席≠全好)."""
    agg = {}
    for rec in records:
        for scn in cc.iter_scenarios(rec):
            for name, q in cc.scenario_kpi_quality(scn).items():
                slot = agg.setdefault(name, {"annotated": 0, "low": 0, "min_n": None})
                slot["annotated"] += 1
                if q["low_confidence"]:
                    slot["low"] += 1
                n = q["sample_count"]
                if n is not None and (slot["min_n"] is None or n < slot["min_n"]):
                    slot["min_n"] = n
    return agg


def analyze(records, min_samples=cc.DEFAULT_MIN_SAMPLES):
    cells = trust_cells(records, min_samples)
    no_evidence = all(c["clock_annotated"] == 0 and c["wall_annotated"] == 0
                      and c["stream_counted"] == 0
                      and c["parse_per_event_us_median"] is None for c in cells)
    return {"cells": cells, "min_samples": min_samples,
            "kpi_quality": kpi_quality_rollup(records),
            "no_evidence": no_evidence if cells else True}


def render_markdown(res):
    lines = [
        "## 测量可信度（时钟 / 流完整性 / 解析开销）",
        "",
        "> 上方时延中位数背后的**仪器**可信度：时钟可疑=R-22（|漂移|>100ppm 或端点缺失），"
        "该场景 TTFT/ITL 存疑；**墙钟可疑**=|设备与服务端墙钟差|>60s（D-506，"
        "**标记非否决**——KPI 计时走单调钟 R-24 不受污染，被污染的是「哪天测的」，"
        "按日分桶的钟源已由 B2 自动判定——见有效率趋势表头与 CSV `day_clock` 列）；seq 异常=gap/dup>0；解析开销大会混淆 ITL"
        "（端侧算力≠网络）。各信号**各自**的分母=实际带该标注的场景数，"
        "未标注**不算干净**（墙钟与时钟分母不同：EchoWire 接线前的语料带 offset_suspect "
        "却不带 wall_skew_ms）。时钟可疑过半标 `时钟可疑热点`。",
        "",
    ]
    if res["no_evidence"]:
        lines.append("_无可信度证据（clock/seq/parse 块均未标注）——覆盖缺口，非全部可信。_")
        return "\n".join(lines)
    lines += ["| 点位 | 运营商 | 时段 | 场景 | 时钟标注 | 时钟可疑 | 漂移中位 ppm | "
              "墙钟标注 | 墙钟可疑 | \\|墙钟差\\| 中位 ms | seq 异常 | 解析 us 中位 | 备注 |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in res["cells"]:
        cl = {k: cc.md_cell(v) for k, v in c["cell"].items()}   # labels are human-typed
        share = "—" if c["clock_suspect_share"] is None \
            else f"{c['clock_suspect']} ({c['clock_suspect_share'] * 100:.0f}%)"
        wall = "—" if c["wall_suspect_share"] is None \
            else f"{c['wall_suspect']} ({c['wall_suspect_share'] * 100:.0f}%)"
        stream = "—" if not c["stream_counted"] else f"{c['stream_bad']}/{c['stream_counted']}"
        notes = []
        if c["clock_hotspot"]:
            notes.append("**时钟可疑热点**")
        # 墙钟只标记不否决（D-506）：出现即点名，不设"过半"门槛——一条墙钟错
        # 就足以让那一条的「哪天测的」不可信，而按日分桶是逐条读的。
        if c["wall_suspect"]:
            notes.append(f"**墙钟可疑 {c['wall_suspect']} 条**（分桶钟源见有效率趋势表头/day_clock 列）")
        if c["low_confidence"]:
            notes.append("low_conf")
        lines.append(
            f"| {cl['point_id']} | {cl['carrier']} | {cl['time_band']} | {c['scenarios']} | "
            f"{c['clock_annotated']} | {share} | {cc.fmt_num(c['abs_drift_ppm_median'])} | "
            f"{c['wall_annotated']} | {wall} | {cc.fmt_num(c['abs_wall_skew_ms_median'])} | "
            f"{stream} | {cc.fmt_num(c['parse_per_event_us_median'])} | "
            f"{'; '.join(notes) or '—'} |")

    # 低置信定位（D-373）：判词从此带理由——哪个 KPI 低置信、差到几个样本。
    lines += ["", "### 低置信定位（per-KPI 样本数）", ""]
    kq = res.get("kpi_quality") or {}
    if not kq:
        lines.append("_语料未携带 `kpi_quality`（v17 之前的生产者）——低置信**无法定位**，"
                     "不等于没有。_")
    else:
        lines += ["| KPI | 标注场景 | 低置信 | 最小样本数 |",
                  "|---|---|---|---|"]
        ordered = sorted(kq.items(),
                         key=lambda kv: (-(kv[1]["low"] / kv[1]["annotated"]),
                                         kv[0]))
        for name, s in ordered:
            lines.append(f"| {cc.md_cell(name)} | {s['annotated']} | "
                         f"{s['low']} ({s['low'] / s['annotated'] * 100:.0f}%) | "
                         f"{cc.fmt_num(s['min_n'])} |")
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
