#!/usr/bin/env python3
"""ANEB campaign radio-context rollup (stdlib only).

Why this exists now. D-48 dropped the three-tier deployment, so the differential
that separated access from backbone is gone for good. The mitigation of record
(PLAN_ALIGNMENT §7.3) is "单点参考端 + 多维协变量（无线上下文/忙闲/双运营商）" —
and radio context is the first covariate named. It is collected (RadioCollector),
stored (Room) and consumed inside the app (BufferingDetector R1, ReportAnalyzer),
but `ResultReporter` writes only transport/capabilities/interface/
server_observed_addr into `network_snapshot`, so no radio value has ever reached
this layer. The fallback for losing tiers names a covariate the analysis layer
cannot see (D-284).

This module is the consumer half, written first on purpose: a wiring spec that
asks for fields nobody reads is the mistake D-276 exists to prevent. Every field
docs/RADIO_CONTEXT_WIRING_SPEC.md requests is consumed here, by name.

What it answers, per (point_id, carrier, time_band):
  * signal band (弱/中/良) by the app's own R1 rule, so a campaign report and a
    per-run report cannot disagree about what "weak" means
  * whether the cell pooled MORE THAN ONE serving cell, which makes its own
    median a mixture
  * whether busy and idle at one point were served by DIFFERENT cells — with
    tiers gone, busy-vs-idle is one of only two comparisons left, and a cell
    change underneath it is the same confound TIER_ENDPOINT_CONFLICT catches

Honesty (R-10): no radio evidence is a coverage gap, never "signal was fine".
Stale samples are excluded and counted, never pooled. Impossible values (an
unavailable reading encoded as 0 dBm, or Android's Integer.MAX_VALUE sentinel)
are rejected by the shared range check rather than averaged in.

Usage:
    python radio_rollup.py results/*.jsonl
"""
import argparse
import sys
from collections import Counter, defaultdict

import campaign_common as cc

CELL_DIMS = ("point_id", "carrier", "time_band")
# The busy/idle comparison lives one level up: same place, same carrier.
PLACE_DIMS = ("point_id", "carrier")


def radio_of(scn):
    """The radio block of one scenario, or None. Never invents a shape."""
    ns = scn.get("network_snapshot")
    if not isinstance(ns, dict):
        return None
    r = ns.get("radio")
    return r if isinstance(r, dict) else None


def egress_ip(scn):
    """The IP half of `network_snapshot.server_observed_addr` (D-376).

    The field has been in the contract and on the wire since the beginning, and
    until now no analysis-layer code read it — the D-276 shape, found by D-374
    needing it: the NR window egressed 106.92.23.196 and all three LTE windows
    106.80.108.105, so RAT and egress path move together in every corpus we
    have. A reader cannot separate them without seeing both, so this belongs
    beside the serving cell, not in a separate table.

    Port is dropped on purpose: it is per-connection noise, and keeping it would
    make every scenario look like a different egress.
    """
    ns = scn.get("network_snapshot")
    if not isinstance(ns, dict):
        return None
    addr = ns.get("server_observed_addr")
    if not isinstance(addr, str) or not addr.strip():
        return None
    # IPv6 literals arrive bracketed ("[2001:db8::1]:443"); IPv4 as "a.b.c.d:p".
    addr = addr.strip()
    if addr.startswith("["):
        end = addr.find("]")
        return addr[1:end] if end > 1 else None
    return addr.rsplit(":", 1)[0] if ":" in addr else addr


def cell_key(r):
    """A serving-cell identity from the parts the producer can read without
    location permission. None unless at least one part is present — an identity
    made of nothing would make every cell look identical, which is worse than
    admitting the field is missing."""
    parts = [r.get("pci"), r.get("tac"), r.get("arfcn")]
    if all(p is None for p in parts):
        return None
    return "-".join("?" if p is None else str(p) for p in parts)


def _samples(records):
    """One pass producing both groupings, so they cannot disagree about which
    runs they saw. Returns (cells, places, stale, implausible)."""
    cells = defaultdict(lambda: {"rsrp": [], "sinr": [], "rats": Counter(),
                                 "keys": Counter(), "n_with_radio": 0, "n": 0,
                                 "samples": [], "egress": Counter()})
    places = defaultdict(lambda: defaultdict(Counter))   # place -> band -> keys
    stale = Counter()
    implausible = defaultdict(Counter)

    for rec in records:
        labels = cc.campaign_labels(rec)
        ckey = tuple(labels[d] for d in CELL_DIMS)
        pkey = tuple(labels[d] for d in PLACE_DIMS)
        band_label = labels["time_band"]
        c = cells[ckey]
        c["n"] += 1
        saw_radio = False
        for scn in cc.iter_scenarios(rec):
            # Egress is read BEFORE the radio guard clauses: it is a property of
            # the path, not of the radio block, and a wifi scenario (no radio
            # key) still has one. Tying it to `continue`-guarded radio parsing
            # would silently make it a cellular-only column (D-336's shape).
            ip = egress_ip(scn)
            if ip:
                c["egress"][ip] += 1
            r = radio_of(scn)
            if r is None:
                continue
            # A stale sample is not a measurement of this run's radio conditions.
            if r.get("stale") is True:
                stale[ckey] += 1
                continue
            saw_radio = True
            # How many readings the producer's own median came from. A cell can
            # have plenty of runs and still rest on one reading each, which is a
            # different kind of thin than "few runs" and is invisible without it.
            n_s = cc.fnum(r.get("sampled_n"))
            if n_s is not None and n_s >= 0:
                c["samples"].append(int(n_s))
            rsrp, sinr = cc.fnum(r.get("rsrp_dbm")), cc.fnum(r.get("sinr_db"))
            if rsrp is not None and cc.keep_value("rsrp_dbm", rsrp, implausible[ckey]):
                c["rsrp"].append(rsrp)
            if sinr is not None and cc.keep_value("sinr_db", sinr, implausible[ckey]):
                c["sinr"].append(sinr)
            rat = r.get("rat")
            if isinstance(rat, str) and rat.strip():
                c["rats"][rat.strip()] += 1
            k = cell_key(r)
            if k:
                c["keys"][k] += 1
                places[pkey][band_label][k] += 1
        if saw_radio:
            c["n_with_radio"] += 1
    return cells, places, stale, implausible


def radio_cells(records, min_samples=cc.DEFAULT_MIN_SAMPLES):
    cells, places, stale, implausible = _samples(records)
    out = []
    for key in sorted(cells):
        c = cells[key]
        rsrp_med = cc.median(c["rsrp"]) if c["rsrp"] else None
        sinr_med = cc.median(c["sinr"]) if c["sinr"] else None
        out.append({
            "cell": dict(zip(CELL_DIMS, key)),
            "n": c["n"],
            "n_with_radio": c["n_with_radio"],
            "rsrp_median_dbm": rsrp_med,
            "sinr_median_db": sinr_med,
            "band": cc.signal_band(rsrp_med, sinr_med),
            "rats": dict(sorted(c["rats"].items())),
            "cell_keys": dict(sorted(c["keys"].items())),
            "stale_samples": stale.get(key, 0),
            "sampled_n_median": cc.median(c["samples"]) if c["samples"] else None,
            # Two ways to be thin, same floor. The second is per scenario, not a
            # cell total: a cell always accumulates a large sum, so a sum-based
            # check could never fire — a guard that cannot fire is worse than
            # none, because it reads as a check that passed.
            "low_confidence": c["n_with_radio"] < min_samples,
            "thin_samples": bool(c["samples"]) and cc.median(c["samples"]) < min_samples,
            "implausible_values": dict(sorted((implausible.get(key) or {}).items())),
            # Egress path beside the serving cell, because D-374 measured them
            # moving together and a reader who sees only one cannot tell which
            # of the two a between-window difference belongs to (D-376).
            "egress_ips": dict(sorted(c["egress"].items())),
        })
    return out, places


def place_comparability(places):
    """Per (point_id, carrier): did the time bands see the same serving cell?

    Only places with radio evidence in at least two bands are returned — the
    only situation in which the question can be asked. A place with one band is
    not "comparable", it is unasked, and it is left out rather than reported as
    agreeing with itself.
    """
    out = []
    for pkey in sorted(places):
        bands = {b: set(k) for b, k in places[pkey].items() if k}
        if len(bands) < 2:
            continue
        shared = set.intersection(*bands.values())
        union = set.union(*bands.values())
        out.append({
            "place": dict(zip(PLACE_DIMS, pkey)),
            "bands": {b: sorted(k) for b, k in sorted(bands.items())},
            "shared_cells": sorted(shared),
            "changed": not shared,
            "partial": bool(shared) and len(union) > len(shared),
        })
    return out


def analyze(records, min_samples=cc.DEFAULT_MIN_SAMPLES):
    cells, places = radio_cells(records, min_samples)
    return {
        "cells": cells,
        "places": place_comparability(places),
        "min_samples": min_samples,
        # Counted, not inferred from an empty table: "the corpus carries no radio
        # block" and "every radio block was stale" are different findings.
        "any_radio": any(c["n_with_radio"] for c in cells),
        "any_block": any(c["n_with_radio"] or c["stale_samples"] for c in cells),
    }


ABSENT_NOTE = (
    "_本轮语料**不含无线上下文**——这是**采集缺口，不是「信号良好」**。"
    "无线量在设备侧已采集(RadioCollector)并被 App 内部消费,但 `ResultReporter` "
    "写入 `network_snapshot` 的只有 transport/capabilities/interface/"
    "server_observed_addr,故本层从未见过任何无线取值。三级归因按 D-48 取消后,"
    "无线上下文是 `PLAN_ALIGNMENT` §7.3 点名的**第一顺位替代协变量**——"
    "接线规格见 `docs/RADIO_CONTEXT_WIRING_SPEC.md`。_")


def render_markdown(res):
    lines = ["## 无线上下文（信号档与小区一致性）", ""]
    if not res["any_radio"]:
        if res["any_block"]:
            lines.append(
                "_本轮所有无线样本均标 `stale`,已全部排除——**排除不等于没问题**,"
                "也不等于信号良好;须核对采集侧的取样新鲜度窗口。_")
        else:
            lines.append(ABSENT_NOTE)
        return "\n".join(lines)

    lines += [
        "> 信号档沿用 App 侧 R1 判据（`BufferingDetector`）：弱=任一已知分量越线"
        f"（RSRP<{cc.fmt_num(cc.RSRP_WEAK_DBM, 0)}dBm 或 SINR<{cc.fmt_num(cc.SINR_WEAK_DB, 0)}dB）；"
        f"良=已知分量均不越线（RSRP≥{cc.fmt_num(cc.RSRP_GOOD_DBM, 0)}dBm 且 "
        f"SINR≥{cc.fmt_num(cc.SINR_GOOD_DB, 0)}dB）；其余为中。"
        "**两个分量都不可得则记 `—`，不记档**。* = 带无线证据的 run 不足。",
        "",
    ]
    # Ordered by the declared vocabulary rather than by whatever the data
    # happened to contain, so a band with zero cells still appears as 0 — an
    # absent row would read as "no weak cells" exactly like a missing one.
    dist = Counter(c["band"] for c in res["cells"])
    unbanded = dist.get(None, 0)
    lines += [
        "**档位分布**：" + " / ".join(
            "%s %d 格" % (cc.SIGNAL_LABELS[b], dist.get(b, 0)) for b in cc.SIGNAL_BANDS)
        + ("；另有 **%d 格无法定档**（两个分量都不可得，**不是「中」**）" % unbanded
           if unbanded else ""),
        "",
        "| 点位 | 运营商 | 时段 | 信号档 | RSRP中位 | SINR中位 | 制式 | 服务小区 | 出口 IP | 备注 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in res["cells"]:
        cl = {k: cc.md_cell(v) for k, v in c["cell"].items()}
        band = cc.SIGNAL_LABELS.get(c["band"], "—")
        lc = "*" if c["low_confidence"] else ""
        notes = []
        if c["n_with_radio"] == 0:
            notes.append("**RADIO_ABSENT**")
        if len(c["cell_keys"]) > 1:
            # the cell's own median mixes serving cells, so it characterises none
            notes.append("**MIXED_SERVING_CELL:%d**" % len(c["cell_keys"]))
        if len(c["rats"]) > 1:
            notes.append("**MIXED_RAT:" + "/".join(sorted(c["rats"])) + "**")
        if c["stale_samples"]:
            notes.append("RADIO_STALE:%d" % c["stale_samples"])
        if c["thin_samples"]:
            notes.append("**RADIO_THIN:每场景中位 %s 个读数**"
                         % cc.fmt_num(c["sampled_n_median"], 1))
        if c["implausible_values"]:
            notes.append("**IMPLAUSIBLE_VALUE:" + "; ".join(
                "%s×%d" % (r, n) for r, n in sorted(c["implausible_values"].items())) + "**")
        if len(c.get("egress_ips") or {}) > 1:
            # Same shape as MIXED_SERVING_CELL one line up: the window's numbers
            # pool more than one egress path, so they characterise neither.
            notes.append("**MIXED_EGRESS:%d**" % len(c["egress_ips"]))
        # One IP prints itself; several print a count — the reader needs to know
        # the window egressed from one path or wandered, not read a list.
        eg = c.get("egress_ips") or {}
        egress = ("—" if not eg else
                  cc.md_cell(next(iter(eg))) if len(eg) == 1 else "%d 个" % len(eg))
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                cl["point_id"], cl["carrier"], cl["time_band"], band,
                cc.fmt_num(c["rsrp_median_dbm"], 1), cc.fmt_num(c["sinr_median_db"], 1),
                "/".join(sorted(c["rats"])) or "—",
                ("%d 个%s" % (len(c["cell_keys"]), lc)) if c["cell_keys"] else "—",
                egress,
                "; ".join(notes) or "—"))

    lines += ["", "### 忙闲可比性（同点位是否挂同一小区）", ""]
    if not res["places"]:
        lines.append(
            "_无一点位在两个时段都留下小区标识——**本条无从核对**，"
            "不等于忙闲可比。_")
        return "\n".join(lines)
    lines += [
        "> 三级归因取消后，忙闲对比是仅剩的两个对照维度之一。"
        "**若忙时与闲时挂的不是同一小区，该点位的忙闲差里混着小区差**——"
        "与 `TIER_ENDPOINT_CONFLICT` 同形，故同样只报不删。",
        "",
        "| 点位 | 运营商 | 各时段小区 | 判定 |",
        "|---|---|---|---|",
    ]
    for p in res["places"]:
        pl = {k: cc.md_cell(v) for k, v in p["place"].items()}
        detail = "; ".join("%s:%s" % (cc.md_cell(b), "/".join(k))
                           for b, k in sorted(p["bands"].items()))
        if p["changed"]:
            verdict = "**CELL_CHANGED——该点位忙闲差不可单独归因于时段**"
        elif p["partial"]:
            verdict = "**CELL_PARTIAL——部分时段另挂了小区，差值含小区成分**"
        else:
            verdict = "同一小区"
        lines.append("| %s | %s | %s | %s |" % (
            pl["point_id"], pl["carrier"], detail, verdict))
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB campaign radio-context rollup")
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
