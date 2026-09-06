#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""簇阈并排复算（B-11 / D-718 补充令）：**只报，不换口径**。

生产侧的簇分割门限是 **400ms 绝对值**（`ObsStats.kt` 的 `CLUSTER_GAP_NANOS`，
D-52/D-53）。本工具把同一批数据在四种门限下**并排算一遍**：

  · `abs400` —— 生产口径原样（值从 `ObsStats.kt` 读，这里不打字面量）
  · `k10 / k20 / k40` —— 相对门限 `gap > k × median(该通道该轮的相邻间隔)`

它要回答的问题只有一个（`evidence/DW-20260905-02/README.md` §4.1 ⑤ / M-B-014①）：
**「DeepSeek A 侧可用轮 0/12」是 400ms 这个绝对阈的口径效应，还是事实？**
换成相对门限后 A2 大量闭合 ⇒ 口径效应；照样闭合不了 ⇒ 事实。

⚠ **本工具不改任何生产判据**，也不写判词。它只把几种量摆在一起看同一批数据。
改口径要走裁定，不走一个复算脚本。

⚠ **默认只打 stdout，不往 run-dir 写文件**：往 `evidence/` 落产物会让语料台账
漂（2026-09-06 当天实测吃过两次）。要落盘请显式给 `--out`。

⚠ **零事件与单簇分开计数**（A-3 顺带项）：两者都「切不出 A2」，但病因相反——
零事件是 A 侧根本没数据（查无障碍服务与包名过滤），单簇是有数据而结构不足
（调 gap／换负载）。合成一个数会把下游引向对前者完全无效的处置。
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import e234_common as ec        # noqa: E402
import e234_session as es       # noqa: E402
import e1_io                    # noqa: E402  (D-648③ 输出编码自锁)

DEFAULT_KS = (10, 20, 40)


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return None
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def relative_gap_ns(ts_ns, k):
    """`k × median(相邻间隔)`；不足两点或中位数为 0 ⇒ None（**不拿 0 顶替**）。

    0 会让「每个间隔都超阈」，把「算不了」印成「全断开」——两种状态在簇数上
    都会给出一个像样的数字，而它们的含义相反。
    """
    ts = sorted(ts_ns)
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    med = _median(gaps)
    if not med:
        return None
    return k * med


def channel_rows(ts_ns, abs_gap_ns, ks=DEFAULT_KS):
    """一条通道在各门限下的 (口径, 门限ms, 簇数, A2, 闭合) 表。

    `closed` ＝ 切不切得出 A2（次簇首）。判据**复用 `ec.v3_anchors`**，
    不另写一个「簇数 ≥2」的比较——同一判据两处实现必有一天分叉。
    """
    ts = sorted(ts_ns)
    out = []
    variants = [("abs400", abs_gap_ns)] + [
        ("k%d" % k, relative_gap_ns(ts, k)) for k in ks]
    for name, gap in variants:
        if gap is None:
            out.append({"criterion": name, "gap_ms": None, "clusters": None,
                        "a2_ns": None, "closed": None,
                        "why": "样本不足两点或中位间隔为 0，定义不出相对门限"})
            continue
        _a0p, a2, cl = ec.v3_anchors(ts, gap)
        out.append({"criterion": name, "gap_ms": round(gap / ec.NS_PER_MS, 3),
                    "clusters": len(cl), "a2_ns": a2, "closed": a2 is not None,
                    "why": None})
    return out


def compare(run_dir, pkg, ks=DEFAULT_KS):
    """一格的并排复算结果（纯读，不写盘）。"""
    lines = ec.read_lines(run_dir, "adapter.log")
    evts, dropped_pkg, dropped_dim = es.content_events(lines, pkg)
    fit = ec.fit_wall_to_boot(lines)
    marks = es.parse_marks(lines, fit)
    turns, method = es.segment_turns(evts, marks)
    pin = ec.clock_pin(ec.read_lines(run_dir, "stim_pre.log"),
                       ec.read_lines(run_dir, "stim_post.log"), None)
    _period_ns, frames = ec.ea.parse_sf_latency(
        ec.read_text(run_dir, "sf_latency.txt"))
    frames, _dup = ec.dedupe_by(frames, "actual_ns")
    abs_gap = ec.cluster_gap_nanos()

    res = {"run_dir": run_dir, "pkg": pkg, "turn_method": method,
           "turns_total": len(turns), "events_used": len(evts),
           "events_other_pkg": dropped_pkg, "events_bad_dimension": dropped_dim,
           "abs_gap_ms": round(abs_gap / ec.NS_PER_MS, 3),
           "ks": list(ks), "clock_pin_ok": pin.get("status") == ec.PASS,
           "per_turn": []}
    for t in turns:
        a_ts = [e["t_boot_ns"] for e in t["events"]]
        c_ts = []
        if res["clock_pin_ok"]:
            lo = ec.boot_to_mono_ns(t["t_start_ns"], pin)
            hi = ec.boot_to_mono_ns(t["t_end_ns"], pin)
            c_ts = [f["actual_ns"] for f in es.frames_in(frames, lo, hi)]
        row = {"turn": t["idx"],
               "A": {"n": len(a_ts),
                     "variants": channel_rows(a_ts, abs_gap, ks)},
               "C": {"n": len(c_ts),
                     "variants": channel_rows(c_ts, abs_gap, ks)}}
        a_abs = row["A"]["variants"][0]
        row["a_shape"] = ("zero_events" if not a_ts else
                          "single_cluster" if a_abs["clusters"] == 1 else
                          "multi_cluster")
        res["per_turn"].append(row)

    res["a_shape_counts"] = {
        k: sum(1 for r in res["per_turn"] if r["a_shape"] == k)
        for k in ("zero_events", "single_cluster", "multi_cluster")}
    res["closed_counts"] = {}
    for name in ["abs400"] + ["k%d" % k for k in ks]:
        for ch in ("A", "C"):
            res["closed_counts"]["%s_%s" % (ch, name)] = sum(
                1 for r in res["per_turn"]
                for v in r[ch]["variants"]
                if v["criterion"] == name and v["closed"])
    return res


def render(res):
    name = os.path.basename(res["run_dir"].rstrip("/\\"))
    L = ["# 簇阈并排复算 %s" % name, ""]
    L.append("目标包 `%s`；切轮 `%s`；轮数 %s；可用内容事件 %s；"
             "绝对阈 %s ms；时钟钉桩 %s"
             % (res["pkg"], res["turn_method"], res["turns_total"],
                res["events_used"], res["abs_gap_ms"],
                "PASS" if res["clock_pin_ok"] else "不可用（C 侧不出数）"))
    L.append("")
    L.append("A 侧形状（**零事件与单簇分开**）：%s" % res["a_shape_counts"])
    L.append("各口径闭合轮数：%s" % res["closed_counts"])
    L.append("")
    if not res["per_turn"]:
        L.append("（无轮次）")
        return "\n".join(L) + "\n"
    crits = [v["criterion"] for v in res["per_turn"][0]["A"]["variants"]]
    L.append("| 轮 | 通道 | n | " + " | ".join(crits) + " |")
    L.append("|---|---|---|" + "---|" * len(crits))
    for r in res["per_turn"]:
        for ch in ("A", "C"):
            cells = []
            for v in r[ch]["variants"]:
                cells.append("—" if v["clusters"] is None else
                             "%d簇/%s" % (v["clusters"],
                                          "闭合" if v["closed"] else "不闭合"))
            L.append("| %s | %s | %s | %s |"
                     % (r["turn"], ch, r[ch]["n"], " | ".join(cells)))
    return "\n".join(L) + "\n"


def main(argv=None):
    e1_io.pin_console_utf8()
    ap = argparse.ArgumentParser(description="簇阈并排复算（只报不换口径）")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--k", default=",".join(str(k) for k in DEFAULT_KS),
                    help="相对门限倍数，逗号分隔（默认 10,20,40）")
    ap.add_argument("--out", default=None,
                    help="可选：把 JSON 写到该路径。**默认不写** —— "
                         "往 evidence/ 里落产物会让语料台账漂")
    ap.add_argument("--json", action="store_true", help="stdout 打 JSON 而非表格")
    a = ap.parse_args(argv)
    ks = tuple(int(x) for x in a.k.split(",") if x.strip())
    res = compare(a.run_dir, a.pkg, ks)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=2) if a.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
