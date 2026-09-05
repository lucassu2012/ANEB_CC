# -*- coding: utf-8 -*-
"""P1 判读（DW-20260905-02 §2 P1 口径，开数前写死）：轮内 C 侧间隔计数。

为什么不是 e2_precheck 的 NOT_APPLICABLE：那条判词对**整场**帧序列数间隔，而带静置期的多轮协议
在静置／切轮处必有 ≥gap 的间隔（DW-20260905-01 两格答窗外分别 19、23 个实证）⇒ 结构性不可达。
本脚本只看每轮 [turn_start, answer_complete] 窗内：
  * gaps_over：窗内相邻帧间隔 > cluster_gap_nanos()（400ms）的个数与值（ms）；
  * disjoint_in_window：与该窗相交的相邻两个 dump 之间不重叠（max(prev) < min(next)）的次数；
  * dumps_in_window / ring_span_s：可观测窗口量（D-642③(c)：单环跨度 × dump 数）。
判词：所有轮 gaps_over==0 且 disjoint 不占多数 ⇒ P1_HOLDS_IN_CELL；任一轮 gaps_over>0 ⇒ COUNTEREXAMPLE（列轮号与间隔）。
时基：标记经 e234_common.clock_pin + boot_to_mono_ns 钉到 MONOTONIC，与 e2_analyze 同一函数（不自造第二套时基）。
用法：python evidence/DW-20260905-02/p1_inwindow_gaps.py --run-dir <格目录> [--gap-ms 400]
"""
import argparse
import io
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "e234"))
sys.path.insert(0, os.path.join(REPO, "tools", "e1"))
import e234_common as ec  # noqa: E402
import e234_session as es  # noqa: E402
import e2_precheck as ep  # noqa: E402


def analyze(run_dir, gap_ms=None):
    gap_ns = int(gap_ms * 1e6) if gap_ms else ec.cluster_gap_nanos()
    dumps = ep.split_dumps(ec.read_text(run_dir, "sf_latency.txt"))
    dumps = [sorted(d) for d in dumps if d]
    frames = sorted(set(t for d in dumps for t in d))
    lines = ec.read_lines(run_dir, "adapter.log")
    fit = ec.fit_wall_to_boot(lines)
    pin = ec.clock_pin(ec.read_lines(run_dir, "stim_pre.log"), ec.read_lines(run_dir, "stim_post.log"), 16.667)
    marks = es.parse_marks(lines, fit)
    starts = {m["n"]: ec.boot_to_mono_ns(m["t_boot_ns"], pin) for m in marks if m["kind"] == "turn_start"}
    ends = {m["n"]: ec.boot_to_mono_ns(m["t_boot_ns"], pin) for m in marks if m["kind"] == "answer_complete"}
    turns = []
    for n in sorted(starts):
        if n not in ends:
            continue
        lo, hi = starts[n], ends[n]
        gaps = []
        for i in range(1, len(frames)):
            a, b = frames[i - 1], frames[i]
            if lo <= a and b <= hi and (b - a) > gap_ns:
                gaps.append(round((b - a) / 1e6, 1))
        inter = [d for d in dumps if d[-1] >= lo and d[0] <= hi]
        disjoint = sum(1 for i in range(1, len(inter)) if inter[i - 1][-1] < inter[i][0])
        spans = [(d[-1] - d[0]) / 1e9 for d in inter]
        turns.append({
            "turn": n, "window_s": round((hi - lo) / 1e9, 1), "gaps_over_ms": gaps,
            "disjoint_in_window": disjoint, "dumps_in_window": len(inter),
            "ring_span_s": round(statistics.median(spans), 2) if spans else None,
        })
    counter = [t for t in turns if t["gaps_over_ms"]]
    frag = [t for t in turns if t["dumps_in_window"] > 1 and t["disjoint_in_window"] * 2 > (t["dumps_in_window"] - 1)]
    if not turns:
        verdict = "NOT_EXECUTED"
    elif frag and len(frag) * 2 > len(turns):
        verdict = "CANNOT_TELL"
    elif counter:
        verdict = "COUNTEREXAMPLE"
    else:
        verdict = "P1_HOLDS_IN_CELL"
    return {
        "run_dir": run_dir.replace(os.sep, "/"), "gap_ms": gap_ns / 1e6, "clock_pin": pin.get("status"),
        "turns_total": len(turns), "turns": turns, "verdict": verdict,
        "counterexample_turns": [t["turn"] for t in counter], "fragmented_turns": [t["turn"] for t in frag],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="P1 轮内 C 侧间隔计数（DW-20260905-02 §2 P1）")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--gap-ms", type=float, default=None, help="默认取 e234_common.cluster_gap_nanos()")
    a = ap.parse_args(argv)
    r = analyze(a.run_dir, a.gap_ms)
    with io.open(os.path.join(a.run_dir, "p1_inwindow_gaps.json"), "w", encoding="utf-8") as fh:
        json.dump(r, fh, ensure_ascii=False, indent=1)
    for t in r["turns"]:
        print("turn=%s window=%.1fs gaps_over=%d %s disjoint=%d dumps=%d ring_span=%ss" % (
            t["turn"], t["window_s"], len(t["gaps_over_ms"]), t["gaps_over_ms"][:6], t["disjoint_in_window"], t["dumps_in_window"], t["ring_span_s"]))
    print("P1 %s | turns=%d gap=%.0fms clock_pin=%s counterexample=%s fragmented=%s" % (
        r["verdict"], r["turns_total"], r["gap_ms"], r["clock_pin"], r["counterexample_turns"], r["fragmented_turns"]))
    return 0 if r["verdict"] in ("P1_HOLDS_IN_CELL", "COUNTEREXAMPLE") else 2


if __name__ == "__main__":
    sys.exit(main())
