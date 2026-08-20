#!/usr/bin/env python3
"""ANEB SYNTHETIC campaign corpus generator (stdlib only) — REHEARSAL FUEL ONLY.

=============================================================================
THE NUMBERS THIS PRODUCES ARE FABRICATED. THEY ARE NOT MEASUREMENTS.
Never present a report built from this corpus as a field result, and never
mix it into a real corpus. Every record is stamped twice (an additive
`synthetic` block AND a `SYNTH-` campaign_id prefix) so campaign_report
detects it and prints a warning banner it is not possible to miss.
=============================================================================

Why it exists: the analysis layer was only ever exercised on 1-3 real records
and unit-scale fixtures. M2 is a 6-8 point x 2 carrier x busy/idle x 3 tier
grid — roughly 500 runs / 1500 scenarios. Discovering on field day that a
32-cell heat card renders unreadably, or that a section breaks at scale, is
the expensive way to find out. This generates a full-grid corpus so the whole
toolchain can be rehearsed end to end beforehand.

The model is deliberately simple and openly approximate:
  * per-tier base RTT (metro < regional < core), a per-point quality factor,
    a busy-hour penalty and a small carrier difference, plus seeded noise;
  * other KPIs derived from that RTT so the cells stay internally consistent;
  * grades from coarse bands — KpiGrading.kt remains authoritative, these are
    plausible labels, not a reimplementation of it;
  * AQS/sub-scores likewise plausible, NOT the spec/scoring pipeline.
It also seeds the awkward cases on purpose (invalid scenarios, suspect clocks,
a batching hot-spot, mixed transports, rotated order indices) so every report
section has something to render.

Deterministic: same --seed => byte-identical corpus, so a rehearsal is
reproducible.

Usage:
    python synth_campaign.py -o rehearsal.jsonl              # default M2 grid
    python synth_campaign.py -o r.jsonl --points 8 --repeats 5 --campaigns base,opt
"""
import argparse
import csv
import json
import random
import sys
from collections import Counter

# The M3 expansion-round shape reads the scenario-side / network-side KPI lists
# from here rather than restating them: `stability` is the ONE place either side
# is named (§2.14), and it is also the code that has to RECOGNISE the shape this
# generator plants. See the 扩展轮 section near the bottom for why a second copy
# would be worse than a dependency.
import stability

GENERATOR = "synth_campaign.py"
GENERATOR_VERSION = "1"
WARNING = "SYNTHETIC - fabricated data, NOT measurements"
CAMPAIGN_PREFIX = "SYNTH-"

TIER_BASE_RTT_MS = {"metro": 20.0, "regional": 38.0, "core": 65.0}
PROFILES = ("s1_chat", "s2_coding_agent", "s3_multimodal")
GRADED = ("t1_ttft_ms", "t2_itl_p95_ms", "t3_stall_rate", "t4_severe_stall_rate",
          "n1_rtt_p50_ms", "n2_jitter_ms", "u1_goodput_mbps", "u2_tool_loop_p95_ms")
# Coarse presentation bands (good/fair/poor). KpiGrading.kt is authoritative;
# these exist only so the synthetic records carry self-consistent grade labels.
BANDS = {
    "t1_ttft_ms": (800, 2000, False), "t2_itl_p95_ms": (120, 250, False),
    "t3_stall_rate": (0.02, 0.08, False), "t4_severe_stall_rate": (0.005, 0.02, False),
    "n1_rtt_p50_ms": (40, 90, False), "n2_jitter_ms": (10, 25, False),
    "u1_goodput_mbps": (30, 12, True), "u2_tool_loop_p95_ms": (1500, 3000, False),
}


def _grade(kpi, value):
    if value is None:
        return None
    good, fair, higher_better = BANDS[kpi]
    if higher_better:
        return "good" if value >= good else ("fair" if value >= fair else "poor")
    return "good" if value <= good else ("fair" if value <= fair else "poor")


def _point_ids(n):
    return [f"SYNTH-P{i:02d}" for i in range(1, n + 1)]


def _quality_factor(point_index, n_points):
    """Spread point quality 0.85..1.4 and make the last point clearly the worst,
    so the heat card has a real gradient plus one obvious problem point."""
    if point_index == n_points - 1:
        return 1.85
    return 0.85 + 0.55 * (point_index / max(1, n_points - 1))


def _kpis(rng, rtt, noise=0.045):
    """All contract-required KPIs, derived from this cell's RTT so a slow cell
    is slow consistently across KPIs (an incoherent corpus rehearses nothing).

    `noise` is RELATIVE (fraction of the value), not absolute: repeat-to-repeat
    spread has to stay under the CV gate for a healthy cell, otherwise the whole
    corpus reads as an unstable harness rather than as network differences.
    Pass a larger value to model a genuinely jittery point.
    """
    def jit(v):
        return max(0.0, v * (1.0 + rng.gauss(0, noise)))

    jitter = max(0.5, jit(rtt * 0.12))
    ttft = max(120.0, jit(380 + rtt * 3.2))
    itl = max(20.0, jit(60 + rtt * 0.8))
    stall = max(0.0, jit(max(0.0, rtt - 15) / 900.0))
    severe = max(0.0, stall * 0.25)
    goodput = max(1.0, jit(60.0 / (1 + rtt / 40.0)))
    tool = max(200.0, jit(900 + rtt * 5))
    kpi = {
        "t1_ttft_ms": round(ttft, 1), "t2_itl_p95_ms": round(itl, 1),
        "t3_stall_rate": round(stall, 4), "t4_severe_stall_rate": round(severe, 4),
        "n1_rtt_p50_ms": round(rtt, 2), "n2_jitter_ms": round(jitter, 2),
        "u1_goodput_mbps": round(goodput, 2), "u2_tool_loop_p95_ms": round(tool, 1),
        "seq_gap_count": 1 if rng.random() < 0.02 else 0,
        "seq_dup_count": 1 if rng.random() < 0.01 else 0,
    }
    for k in GRADED:
        kpi[k.split("_")[0] + "_grade"] = _grade(k, kpi[k])
    return kpi


def _sub_scores(kpi):
    """Plausible 0-100 dimension scores. NOT the spec/scoring pipeline."""
    def band(v, good, poor):
        span = (poor - good) or 1.0
        return round(max(0.0, min(100.0, 100.0 - 100.0 * (v - good) / span)), 2)

    def band_up(v, good, poor):        # higher value is better (goodput)
        span = (good - poor) or 1.0
        return round(max(0.0, min(100.0, 100.0 * (v - poor) / span)), 2)

    return {
        "T1": band(kpi["t1_ttft_ms"], 500, 2500),
        "T2": band(kpi["t2_itl_p95_ms"], 70, 300),
        "T3": band(kpi["t3_stall_rate"], 0.005, 0.12),
        "N1": band(kpi["n1_rtt_p50_ms"], 15, 110),
        "N2": band(kpi["n2_jitter_ms"], 3, 35),
        "U1": band_up(kpi["u1_goodput_mbps"], 55, 12),
        "U2": band(kpi["u2_tool_loop_p95_ms"], 800, 3500),
    }


# Synthetic radio, rehearsal only. Bands are assigned by point so a rehearsal
# shows 弱/中/良 all three, and four pathologies are planted so every marker the
# rollup can raise has something to raise it on — a rehearsal that only produces
# clean rows never demonstrates the check that matters (D-270).
_RADIO_BANDS = [(-85.0, 15.0), (-85.0, 15.0), (-85.0, 15.0),
                (-100.0, 5.0), (-100.0, 5.0), (-100.0, 5.0),
                (-112.0, -2.0), (-112.0, -2.0)]
RADIO_HANDOVER_POINT = 1         # handover WITHIN one cell (busy and idle both)
RADIO_THIN_POINT = 2             # producer samples once or twice per scenario
RADIO_CELL_CHANGE_POINT = 4      # different serving cell in busy vs idle
RADIO_MIXED_RAT_POINT = 5        # NR and LTE inside one cell
RADIO_STALE_POINT = 6            # some samples arrive stale
RADIO_IMPLAUSIBLE_POINT = 7      # "unavailable" written as 0 dBm
# Points where pi % 3 == 0 alternate wifi/cellular by repeat, so rep 0 there
# carries no radio at all — planting a cellular-only pathology on an even repeat
# of such a point produces a rehearsal that silently never exercises it.
_DUAL_MEDIUM_EVERY = 3


def _radio(rng, pi, band, rep, scn_index):
    """One synthetic radio block. Cellular only — wifi has no serving cell."""
    base_rsrp, base_sinr = _RADIO_BANDS[pi % len(_RADIO_BANDS)]
    rsrp = round(base_rsrp + rng.gauss(0, 2.5), 1)
    sinr = round(base_sinr + rng.gauss(0, 1.5), 1)
    rat = "LTE" if (pi == RADIO_MIXED_RAT_POINT and scn_index == 1) else "NR"
    pci = 200 + pi
    if pi == RADIO_CELL_CHANGE_POINT and band == "idle":
        pci = 300 + pi          # a DIFFERENT cell served idle than served busy
    elif pi == RADIO_HANDOVER_POINT and rep >= 2 and band == "busy":
        # Handover part-way through the busy visit only, so this one point shows
        # BOTH markers: the busy cell mixes two serving cells, and the busy/idle
        # pair overlaps partially rather than not at all.
        pci = 250 + pi
    if pi == RADIO_IMPLAUSIBLE_POINT and rep == 1 and scn_index == 0:
        rsrp = 0        # the classic sentinel: not a strong signal, not a value
    n = rng.randint(1, 2) if pi == RADIO_THIN_POINT else rng.randint(6, 20)
    # rep 1 rather than rep 0: RADIO_STALE_POINT is a dual-medium point, whose
    # even repeats are measured on wifi and therefore carry no radio block.
    stale = (pi == RADIO_STALE_POINT and rep == 1 and scn_index == 0)
    return {"rat": rat, "rsrp_dbm": rsrp, "sinr_db": sinr,
            "pci": pci, "tac": 12000 + pi, "arfcn": 504990,
            "sampled_n": n, "stale": bool(stale)}


def _scenario(rng, idx, rtt, *, order_index, suspect_clock, suspect_wall=False,
              batching, transport,
              noise=0.045, radio=None):
    kpi = _kpis(rng, rtt, noise)
    roll = rng.random()
    if roll < 0.06:
        validity, reasons = "invalid", rng.choice(
            ["STREAM_ABORTED", "CLOCK_OFFSET_SUSPECT", "PROFILE_MISMATCH;RETRY_EXHAUSTED"])
        for k in GRADED:                       # invalid => no KPI values (R-10 pairing)
            kpi[k] = None
            kpi[k.split("_")[0] + "_grade"] = None
    elif roll < 0.22:
        validity, reasons = "valid_low_confidence", ""
    else:
        validity, reasons = "valid", ""
    drift = rng.gauss(0, 18) if not suspect_clock else rng.choice([-1, 1]) * rng.uniform(110, 400)
    return {
        "profile_id": PROFILES[idx % len(PROFILES)],
        "profile_version": "0.2", "repeat_index": 0, "order_index": order_index,
        "validity": validity, "invalid_reasons": reasons, "kpi": kpi,
        "clock": {"offset_start_us": int(rng.uniform(-4000, 4000)),
                  "offset_end_us": int(rng.uniform(-4000, 4000)),
                  "drift_ppm": round(drift, 2), "offset_suspect": bool(suspect_clock),
                  # 墙钟差（D-506/T68）。与 offset_suspect **分开**取值：钟"走得稳"
                  # 与钟"指得对"是两回事，真实语料里确实会一个正常一个不正常；
                  # 若绑在同一个开关上，墙钟那一列在彩排里永远走不到独立分支。
                  "wall_skew_ms": (int(rng.choice([-1, 1]) * rng.uniform(70_000, 900_000))
                                   if suspect_wall else int(rng.gauss(0, 300)))},
        "network_snapshot": dict(
            {"transport": transport, "capabilities": "INTERNET,VALIDATED",
             "interface": "rmnet0" if transport == "cellular" else "wlan0",
             "server_observed_addr": "203.0.113.7:8443"},
            **({"radio": radio} if radio else {})),
        "parse": {"parse_dur_us": int(rng.uniform(400, 3000)),
                  "per_event_parse_us": round(rng.uniform(20, 110), 1)},
        "buffering": ({"score": round(rng.uniform(0.35, 0.7), 4),
                       "attribution": "middlebox_suspect", "sample_count": 100,
                       "sawtooth_ratio": round(rng.uniform(0.25, 0.5), 4),
                       "near_zero_arrival_ratio": round(rng.uniform(0.2, 0.4), 4),
                       "batch_count": int(rng.uniform(4, 12))}
                      if batching else
                      {"score": round(rng.uniform(0.0, 0.03), 4), "attribution": "none",
                       "sample_count": 100, "sawtooth_ratio": round(rng.uniform(0, 0.02), 4),
                       "near_zero_arrival_ratio": 0.0, "batch_count": 0}),
        "itl_histogram": {"buckets_version": "v1", "edges_ms": [10, 20, 50, 100],
                          "counts": [12, 30, 40, 12, 6], "total": 100},
    }


# The point whose optimisation round is designed to be BIG ENOUGH TO DETECT.
# Chosen to carry no other special role: index 1 has the broken clock, 2 the
# batching, 3 the jitter, and every third point is dual-medium.
OPTIMISED_POINT_INDEX = 4
OPTIMISED_POINT_GAIN = 0.55        # extra RTT factor on the later campaign


# What a rehearsal is SUPPOSED to conclude. Same idea as CHAOS_PATHOLOGIES: an
# expected answer turns "look at the output" into "check the output", which is
# the difference between a rehearsal and a demo.
#
# Why this exists: with only the uniform 10% campaign gain, the designed effect
# worked out to ~3 AQS points against a ~6-point noise scale, so at the runbook's
# default grid ALL 32 comparable cells landed inside the noise — every rehearsal
# ended in "no change beyond measurement noise". Honest, but it means a broken
# improvement-detection path and a working one produce identical rehearsal
# output: the vacuous-test trap wearing a corpus (D-182).
DESIGNED_EFFECTS = (
    ("real_improvement",
     f"SYNTH-P{OPTIMISED_POINT_INDEX + 1:02d} 在 opt 战役有**真实**改善（设计值远超噪声尺度）"
     "→ 「优化前后对比」必须把它判为**超出噪声**，摘要必须点名它。"
     "**若报告说全部格都在噪声内，是改善检测坏了，不是数据没效果。**"),
    ("sub_noise_improvement",
     "其余点位的 opt 改善（均匀 10% RTT）**刻意小于**噪声尺度 → 必须判为 `噪声内`。"
     "这是正确行为而非工具迟钝：真实外场里这种量级的差异同样不能当结论。"),
    ("media_difference",
     "双介质点位的 wifi/cellular 差异同样小于噪声 → 「接入介质」信号必须说"
     "**未观察到超出测量噪声的介质差异**，不得点名「蜂窝劣于 wifi」。"),
)


def generate(*, points=8, carriers=("cmcc", "cucc"), time_bands=("busy", "idle"),
             tiers=("metro", "regional", "core"), repeats=5,
             campaigns=("base", "opt"), seed=20260725, start_ms=1783944000000,
             radio=False):
    """Full-grid synthetic corpus. Returns a list of contract-complete records.

    Carries the outcomes listed in DESIGNED_EFFECTS — one detectable improvement,
    everything else deliberately sub-noise — so a rehearsal can tell a working
    toolchain from a silent one."""
    rng = random.Random(seed)
    pids = _point_ids(points)
    records = []
    counter = 0
    for ci, campaign in enumerate(campaigns):
        # later campaigns are modelled as an optimisation round: modestly better
        campaign_gain = 1.0 - 0.10 * ci
        campaign_start = start_ms + ci * 7 * 86400_000
        for pi, point in enumerate(pids):
            qf = _quality_factor(pi, len(pids))
            # one point has a broken clock, one has middlebox batching, and every
            # third point is on wifi — so trust/buffering/transport all have data
            suspect_point = (pi == 1)
            batching_point = (pi == 2)
            # one point is genuinely jittery, so the CV gate has real work to do
            # without every cell tripping it
            noise = 0.20 if pi == 3 else 0.045
            # every third point is measured on BOTH media (alternating repeats),
            # the way a field crew compares them at one location; the rest are
            # cellular-only, so the rollup sees both the comparable and the
            # single-medium case
            dual_medium = (pi % 3 == 0)
            # ONE point gets an optimisation large enough to clear the noise, so
            # the rehearsal has a positive answer to check against (D-182).
            opt_gain = (OPTIMISED_POINT_GAIN
                        if (ci > 0 and pi == OPTIMISED_POINT_INDEX) else 1.0)
            for carrier in carriers:
                carrier_f = 1.0 if carrier == "cmcc" else 1.12
                for band in time_bands:
                    band_f = 1.35 if band == "busy" else 1.0
                    for tier in tiers:
                        base = TIER_BASE_RTT_MS[tier]
                        for rep in range(repeats):
                            counter += 1
                            medium = ("wifi" if (dual_medium and rep % 2 == 0)
                                      else "cellular")
                            # wifi backhaul modelled as modestly better here
                            medium_f = 0.88 if medium == "wifi" else 1.0
                            rtt = base * qf * carrier_f * band_f * campaign_gain \
                                * opt_gain * medium_f * (1.0 + rng.gauss(0, noise * 0.5))
                            rtt = max(3.0, rtt)
                            scns = [
                                _scenario(rng, i, rtt,
                                          order_index=(rep + i) % len(PROFILES),
                                          suspect_clock=suspect_point and rng.random() < 0.7,
                                          # 墙钟独立于时钟抽（D-506/T68）：低频但确实出现，
                                          # 让彩排语料同时走到"可疑"与"正常"两个分支
                                          suspect_wall=rng.random() < 0.08,
                                          batching=batching_point and band == "busy",
                                          transport=medium, noise=noise,
                                          radio=(_radio(rng, pi, band, rep, i)
                                                 if radio and medium == "cellular"
                                                 else None))
                                for i in range(len(PROFILES))
                            ]
                            usable = [s for s in scns if s["validity"] != "invalid"]
                            if usable:
                                subs = _sub_scores(usable[0]["kpi"])
                                score = round(sum(subs.values()) / len(subs), 2)
                                aqs = {"score": score, "low_confidence": len(usable) < 2,
                                       "veto_applied": False, "not_computable_reason": None,
                                       "input_mapping": "synthetic", "sub_scores": subs}
                            else:
                                aqs = {"score": None, "low_confidence": True,
                                       "veto_applied": False,
                                       "not_computable_reason": "ALL_SCENARIOS_INVALID",
                                       "input_mapping": "synthetic", "sub_scores": {}}
                            records.append({
                                "claim_scope": "application_end_to_end_to_probe_node",
                                "kpi_set": "agent-qoe-kpi-v0.2", "aqs_version": "aqs-v0.1",
                                "profile_versions": "s1@0.2,s2@0.2,s3@0.2",
                                "schema_version": "1.0",
                                # additive marker #1 (schema allows extra properties)
                                "synthetic": {"generator": GENERATOR,
                                              "version": GENERATOR_VERSION,
                                              "seed": seed, "warning": WARNING},
                                "run": {
                                    "run_id": f"synth-{seed}-{campaign}-{counter:06d}",
                                    "started_at_epoch_ms": campaign_start + counter * 90_000,
                                    "mode": "quick", "scenario_order": ",".join(PROFILES),
                                    "transport": f"auto({medium})",
                                    "profile_source": "server",
                                    "app_version_name": "0.0-synthetic",
                                    "app_version_code": 0, "guard_metadata": None,
                                    "status": "completed" if usable else "aborted:all_invalid",
                                    "aqs": aqs,
                                    "campaign": {  # marker #2: the SYNTH- prefix
                                        "campaign_id": CAMPAIGN_PREFIX + campaign,
                                        "tier": tier, "point_id": point,
                                        "carrier": carrier, "time_band": band,
                                        # One endpoint per tier, because that is
                                        # what a campaign the wiring spec asks
                                        # for looks like. Without it every
                                        # multi-tier row carries
                                        # TIER_ENDPOINT_UNVERIFIED (D-292) and
                                        # the rehearsal can no longer show the
                                        # operator a clean attribution row.
                                        "server_tier_endpoint":
                                            "https://e-01-%s.invalid" % tier},
                                },
                                "scenarios": scns,
                            })
    return records


# --------------------------------------------------------------- chaos mode
#
# The clean corpus above rehearses the happy path. Real field data is messier,
# and every mess has a specific honest-degradation behaviour the analysis layer
# is supposed to show. This seeds those messes on purpose so a rehearsal can
# check the layer degrades honestly instead of crashing or inventing numbers.
# Each entry names the pathology and the behaviour it should produce (D-125).
CHAOS_PATHOLOGIES = (
    ("missing_tier", "某点位缺 core 层 → 归因记 TIER_MISSING，不外推"),
    ("single_carrier", "某点位只测到一个运营商 → 覆盖矩阵列为未测，不补齐"),
    ("aborted_runs", "中途 abort 的 run → 盘点显示非 completed，AQS 为 null 不进中位"),
    ("mixed_profile_version", "同格混 profile 版本 → 标 MIXED_PROFILE_VERSION"),
    ("mixed_histogram_edges", "同格混直方图边界 → 标 MIXED_HIST_EDGES（R-27 不可相加）"),
    ("mixed_mode", "同格混 quick/forensic → 标 MIXED_MODE"),
    ("clock_jump", "某格时钟跳变 → 时钟可疑热点，该格时延中位数存疑"),
    ("extreme_outlier", "单条极端离群 → 中位数稳健但 CV 超门（复测不稳定）"),
    ("all_invalid_cell", "某格全部失效 → 有效率 0%，KPI 值全 null"),
    ("unlabelled_records", "部分记录无战役标签 → 落 unlabeled 桶，覆盖盘点显示"),
)


def inject_chaos(records, seed=20260726):
    """Seed realistic field pathologies into a clean corpus. Returns a new list.

    NOT a fuzzer: each pathology is one a field crew actually produces, and each
    has an expected honest-degradation behaviour listed in CHAOS_PATHOLOGIES.
    Duplicate run_ids are deliberately NOT seeded — the report front door refuses
    those outright (D-109), which would stop the rehearsal before it could look
    at how everything else degrades; that path has its own golden.
    """
    rng = random.Random(seed)
    if not records:
        return records
    points = sorted({r["run"]["campaign"]["point_id"] for r in records})
    if len(points) < 4:
        return records                     # too small a grid to place pathologies

    kept = []
    for rec in records:
        c = rec["run"]["campaign"]
        # 1. a point where the core tier was never reached
        if c["point_id"] == points[0] and c["tier"] == "core":
            continue
        # 2. a point measured on one carrier only
        if c["point_id"] == points[1] and c["carrier"] != "cmcc":
            continue
        kept.append(rec)

    for i, rec in enumerate(kept):
        c = rec["run"]["campaign"]
        scns = rec.get("scenarios") or []
        cell = (c["point_id"], c["carrier"], c["time_band"])

        # 3. aborted runs (AQS not computable — never a zero)
        if i % 37 == 0:
            rec["run"]["status"] = "aborted:" + rng.choice(["timeout", "user", "network"])
            rec["run"]["aqs"] = {"score": None, "low_confidence": True,
                                 "veto_applied": False,
                                 "not_computable_reason": "RUN_ABORTED",
                                 "input_mapping": "synthetic", "sub_scores": {}}
        # 4/5/6. incomparable things pooled into one cell
        if c["point_id"] == points[2] and c["time_band"] == "busy":
            if i % 2 == 0:
                for s in scns:
                    s["profile_version"] = "0.3"
            if i % 3 == 0:
                for s in scns:
                    h = s.get("itl_histogram")
                    if isinstance(h, dict):
                        h["edges_ms"] = [10, 25, 50, 120]
            if i % 5 == 0:
                rec["run"]["mode"] = "forensic"
        # 7. a clock that jumped (drift far beyond the R-22 threshold)
        if c["point_id"] == points[3] and c["time_band"] == "idle":
            for s in scns:
                s["clock"] = dict(s.get("clock") or {},
                                  drift_ppm=round(rng.uniform(600, 1500), 2),
                                  offset_suspect=True)
        # 8. one extreme outlier run (median must stay robust, CV must not)
        if i == len(kept) // 2:
            for s in scns:
                kpi = s.get("kpi") or {}
                if kpi.get("n1_rtt_p50_ms") is not None:
                    kpi["n1_rtt_p50_ms"] = round(kpi["n1_rtt_p50_ms"] * 50, 2)
        # 9. a cell where everything failed
        if cell == (points[-1], "cucc", "busy"):
            for s in scns:
                s["validity"] = "invalid"
                s["invalid_reasons"] = "STREAM_ABORTED;RETRY_EXHAUSTED"
                for k in GRADED:
                    s["kpi"][k] = None
                    s["kpi"][k.split("_")[0] + "_grade"] = None
        # 10. records that never got labelled
        if i % 53 == 0:
            rec["run"].pop("campaign", None)
    return kept


# ------------------------------------------------------------ M3 扩展轮形状
#
# `generate()` 造的是 **M2 的形状**——`mode="quick"`、每场景 `repeat_index=0`、
# 全语料同一个 `scenario_order`。扩展轮（`docs/M3_EXPANSION_ROUND_RUNBOOK_ADDENDUM.md`）
# 要三样它造不出的东西，此前靠一只一次性整形器补齐
# （`evidence/m3_expansion_rehearsal_20260801/shape_expansion_corpus.py`，现已降格为
# 历史证据）——**而一次性脚本没有守卫**（GUARD_DIFF C-4）。本节把它接了进来。
#
# 下面每个幅度都只是**设计值**，其出处是决策号里已归档的实测值；本文件不产生任何
# 新的测量，其输出也不得被引用为测量。
S2_EXTRA_JITTER = 0.11            # s2 场景侧额外相对抖动（设计源 D-353 / D-372）
WARMUP_PENALTY = 0.16             # 预热轮整体更差的比例（设计源 D-358）
FORENSIC_ROUND0_RESIDUAL = 0.04   # 预热丢弃后，取证第 0 轮的 App/TLS 残余（D-358）

EXPANSION_TIER = "metro"          # 单层级（D-48：单实例 E-01，扩展轮不排三层级行程）
EXPANSION_CAMPAIGN = "EXP"        # 单战役（生成器自动加 `SYNTH-` 前缀＝合成标记 #2）
EXPANSION_COUNTED_REPEATS = 15    # 提案 §1：扩展轮 n≥15（依 s1/s3 网络侧 CV）
EXPANSION_WARMUP_RUNS = 1         # 每格丢弃的预热轮数（口径见 D-366，此处只给指针）
EXPANSION_FORENSIC_RUNS = 5       # D-379：取证 5 轮（提案原「建议 4 轮」已随之作废）

# 台账列。**预热轮在语料里没有任何字段说明自己是预热**——它会正常上报，
# 唯一认得它的是台账（口径 D-366，此处刻意不复述其记账细则：复述必漂）。
# 也刻意不给记录加一个「我是预热」的合成专用字段：那等于让彩排去演一个外场
# 根本造不出来的形状，正是 D-309 要防的那件事的反面。
WARMUP_DISPOSITION = "预热丢弃"
WARMUP_AUTHORITY = "D-366"
WARMUP_LEDGER_HEADER = ("run_id", "mode", "point_id", "carrier", "time_band",
                        "disposition", "authority", "synthetic")

EXPANSION_ARTIFACTS = (("raw", "_raw.jsonl"), ("counted", "_counted.jsonl"),
                       ("counted_quick", "_counted_quick.jsonl"),
                       ("counted_forensic", "_counted_forensic.jsonl"))
WARMUP_LEDGER_SUFFIX = "_warmup_ledger.csv"


def latin_square(items=PROFILES):
    """n×n 循环拉丁方（第 r 行 = items 左移 r 位）——D-354 验证过轮转正确的形状。

    刻意**算**出来而不是写成字面量：一张手写的 3×3 表被人编辑后可以悄悄不再是
    拉丁方（某个位次上某个 profile 出现两次），而算出来的那张不可能。
    """
    n = len(items)
    return tuple(tuple(items[(r + c) % n] for c in range(n)) for r in range(n))


LATIN_SQUARE = latin_square()
# 契约示例即此写法：三个轮次以 `|` 连接，轮内以 `,` 连接。
FORENSIC_SCENARIO_ORDER = "|".join(",".join(r) for r in LATIN_SQUARE)


def warmup_scaled_kpis():
    """预热轮劣化落在哪些 KPI 上：场景侧 + 网络侧 + `u1_goodput_mbps`。

    两张清单**读 `stability`**（§2.14 说它是「场景侧/网络侧」在全仓唯一被命名的
    地方），不在这里另抄一份。理由不是省事：s2 的设计效应与**检测它的那条判据**
    （`SCENARIO_INTRINSIC_JITTER`，D-382）必须是同一张清单，否则两边可以悄悄分叉，
    而分叉的那天彩排会安静地不再演示那个标记——一个不再演示要教的那件事的彩排，
    和坏掉的彩排在输出上分不开（D-182 的形状）。「两处逐字相同」恰是最容易分叉、
    又最难察觉的状态（D-317）。
    """
    return (tuple(stability.SCENARIO_SIDE_KPIS) + tuple(stability.NETWORK_SIDE_KPIS)
            + ("u1_goodput_mbps",))


def _scale_kpi(kpi, keys, factor, *, higher_better=("u1_goodput_mbps",)):
    """把一组 KPI 按 factor 缩放（factor>1 = 更差）。等级标签随之重算。"""
    for k in keys:
        v = kpi.get(k)
        if v is None:
            continue
        kpi[k] = round(v / factor if k in higher_better else v * factor,
                       4 if k in ("t3_stall_rate", "t4_severe_stall_rate") else 2)
    for k in GRADED:
        if k in kpi:
            kpi[k.split("_")[0] + "_grade"] = _grade(k, kpi[k])


def apply_s2_intrinsic_jitter(records, rng):
    """只给 s2 的**场景侧** KPI 加一层 per-run 抖动，网络侧 KPI 一个不动。

    这正是 D-372 判定、D-382 变成判据的那个形状：同格同 profile 下场景侧超 CV 门
    而网络侧未超门。`n1_rtt_p50_ms` / `n2_jitter_ms` 不动，是**判别证据本身**。
    """
    touched = 0
    for rec in records:
        for scn in rec.get("scenarios") or []:
            if scn.get("profile_id") != PROFILES[1]:
                continue
            f = max(0.5, 1.0 + rng.gauss(0, S2_EXTRA_JITTER))
            _scale_kpi(scn.get("kpi") or {}, stability.SCENARIO_SIDE_KPIS, f)
            touched += 1
    return touched


def _expansion_cell_key(rec):
    c = (rec.get("run") or {}).get("campaign") or {}
    return (c.get("campaign_id"), c.get("point_id"), c.get("carrier"),
            c.get("time_band"), c.get("tier"))


def _expansion_quick(rng, *, points, carriers, time_bands, tier, campaign,
                     counted_repeats, warmup_runs, seed, start_ms, radio):
    """quick 主体：每格 (counted_repeats + warmup_runs) 条，预热轮 = 每格文件序前 N 条。

    `generate()` 把 repeats 放在最内层循环，所以每格的头几条就是该格最先跑的那几条
    ——正好是预热轮的位置。台账记下它们的 `run_id`。
    """
    recs = generate(points=points, carriers=carriers, time_bands=time_bands,
                    tiers=(tier,), repeats=counted_repeats + warmup_runs,
                    campaigns=(campaign,), seed=seed, start_ms=start_ms, radio=radio)
    seen, warmup_ids = {}, []
    scaled = warmup_scaled_kpis()
    for rec in recs:
        k = _expansion_cell_key(rec)
        if seen.get(k, 0) >= warmup_runs:
            continue
        seen[k] = seen.get(k, 0) + 1
        warmup_ids.append(rec["run"]["run_id"])
        # 预热轮整体更差（无线唤醒）：网络侧与场景侧**一起**劣化——这与 s2 的
        # 内生抖动是两回事（那个只动场景侧），故两处分别施加。
        for scn in rec.get("scenarios") or []:
            _scale_kpi(scn.get("kpi") or {}, scaled, 1.0 + WARMUP_PENALTY)
    apply_s2_intrinsic_jitter(recs, rng)
    return recs, warmup_ids


def _expansion_forensic(rng, start_ms, *, points, carriers, time_bands, tier,
                        campaign, point_indices, runs_per_cell, warmup_runs,
                        seed, radio):
    """取证子集：每格 (runs_per_cell + warmup_runs) 条取证 run，每条 9 场景、3×3 轮转。

    一次取证 run = len(PROFILES)² 个场景：`order_index` 0..8、`repeat_index` 逐轮
    0,0,0/1,1,1/2,2,2、`scenario_order` 为三个轮次以 `|` 连接。
    """
    recs, warmup_ids = [], []
    counter = 0
    pids = _point_ids(points)
    for pi in point_indices:
        point = pids[pi]
        qf = _quality_factor(pi, points)     # 与 quick 主体里同一点位同一质量因子
        for carrier in carriers:
            carrier_f = 1.0 if carrier == "cmcc" else 1.12
            for band in time_bands:
                band_f = 1.35 if band == "busy" else 1.0
                for run_i in range(warmup_runs + runs_per_cell):
                    counter += 1
                    is_warmup = run_i < warmup_runs
                    base = TIER_BASE_RTT_MS[tier]
                    scns = []
                    for rnd, row in enumerate(LATIN_SQUARE):
                        # 预热轮整条更差；计入轮只剩 App/TLS 残余，且残余只落在
                        # **轮内第 0 轮**（口径 D-358）。
                        if is_warmup:
                            round_f = 1.0 + WARMUP_PENALTY
                        else:
                            round_f = 1.0 + (FORENSIC_ROUND0_RESIDUAL if rnd == 0 else 0.0)
                        for pos, profile in enumerate(row):
                            oi = rnd * len(row) + pos
                            rtt = max(3.0, base * qf * carrier_f * band_f * round_f
                                      * (1.0 + rng.gauss(0, 0.045 * 0.5)))
                            block = _radio(rng, pi, band, rnd, pos) if radio else None
                            scn = _scenario(rng, PROFILES.index(profile), rtt,
                                            order_index=oi, suspect_clock=False,
                                            batching=False, transport="cellular",
                                            radio=block)
                            scn["profile_id"] = profile   # 位次由拉丁方决定
                            scn["repeat_index"] = rnd     # 轮次（D-354 语义）
                            scns.append(scn)
                    usable = [s for s in scns if s["validity"] != "invalid"]
                    if usable:
                        subs = _sub_scores(usable[0]["kpi"])
                        score = round(sum(subs.values()) / len(subs), 2)
                        aqs = {"score": score, "low_confidence": len(usable) < 2,
                               "veto_applied": False, "not_computable_reason": None,
                               "input_mapping": "synthetic", "sub_scores": subs}
                    else:
                        aqs = {"score": None, "low_confidence": True,
                               "veto_applied": False,
                               "not_computable_reason": "ALL_SCENARIOS_INVALID",
                               "input_mapping": "synthetic", "sub_scores": {}}
                    run_id = f"synth-{seed}-{campaign}-forensic-{counter:06d}"
                    if is_warmup:
                        warmup_ids.append(run_id)
                    recs.append({
                        "claim_scope": "application_end_to_end_to_probe_node",
                        "kpi_set": "agent-qoe-kpi-v0.2", "aqs_version": "aqs-v0.1",
                        "profile_versions": "s1@0.2,s2@0.2,s3@0.2",
                        "schema_version": "1.0",
                        "synthetic": {"generator": GENERATOR,
                                      "version": GENERATOR_VERSION,
                                      "seed": seed, "warning": WARNING},
                        "run": {
                            "run_id": run_id,
                            "started_at_epoch_ms": start_ms + counter * 400_000,
                            "mode": "forensic",
                            "scenario_order": FORENSIC_SCENARIO_ORDER,
                            "transport": "auto(cellular)", "profile_source": "server",
                            "app_version_name": "0.0-synthetic", "app_version_code": 0,
                            "guard_metadata": None,
                            "status": "completed" if usable else "aborted:all_invalid",
                            "aqs": aqs,
                            "campaign": {
                                "campaign_id": CAMPAIGN_PREFIX + campaign,
                                "tier": tier, "point_id": point,
                                "carrier": carrier, "time_band": band,
                                "server_tier_endpoint":
                                    "https://e-01-%s.invalid" % tier},
                        },
                        "scenarios": scns,
                    })
    apply_s2_intrinsic_jitter(recs, rng)
    return recs, warmup_ids


def generate_expansion(*, points=8, carriers=("cmcc", "cucc"),
                       time_bands=("busy", "idle"), tier="metro", campaign="EXP",
                       counted_repeats=EXPANSION_COUNTED_REPEATS,
                       warmup_runs=EXPANSION_WARMUP_RUNS, forensic_points=2,
                       forensic_runs_per_cell=EXPANSION_FORENSIC_RUNS,
                       forensic_warmup_runs=1, seed=20260801,
                       start_ms=1783944000000, radio=True):
    """M3 扩展轮语料。返回 dict：raw / counted / counted_quick / counted_forensic /
    warmup_ids / ledger_rows。

    同时产出 `_raw`（拉取到的全部）与 `_counted`（按台账排除预热后）两份语料，
    是为了让「台账排除到底改变了什么」可以**被对着核**，而不是被声称。
    """
    rng = random.Random(seed)
    quick, quick_warmup = _expansion_quick(
        rng, points=points, carriers=carriers, time_bands=time_bands, tier=tier,
        campaign=campaign, counted_repeats=counted_repeats, warmup_runs=warmup_runs,
        seed=seed, start_ms=start_ms, radio=radio)
    forensic_start = quick[-1]["run"]["started_at_epoch_ms"] + 600_000
    forensic, forensic_warmup = _expansion_forensic(
        rng, forensic_start, points=points, carriers=carriers,
        time_bands=time_bands, tier=tier, campaign=campaign,
        point_indices=tuple(range(forensic_points)),
        runs_per_cell=forensic_runs_per_cell, warmup_runs=forensic_warmup_runs,
        seed=seed, radio=radio)

    raw = quick + forensic
    warmup_ids = set(quick_warmup) | set(forensic_warmup)
    counted = [r for r in raw if r["run"]["run_id"] not in warmup_ids]
    ledger_rows = []
    for r in raw:
        rid = r["run"]["run_id"]
        if rid not in warmup_ids:
            continue
        c = r["run"]["campaign"]
        ledger_rows.append((rid, r["run"]["mode"], c["point_id"], c["carrier"],
                            c["time_band"], WARMUP_DISPOSITION, WARMUP_AUTHORITY,
                            "True"))
    return {"raw": raw, "counted": counted,
            # 分面语料：两块池化在一份报告里时，序位与预热两段都会被「位次由不同
            # 格供样」污染，而那正是取证子集存在的目的（D-380）。故各自也要能单独出报告。
            "counted_quick": [r for r in counted if r["run"]["mode"] == "quick"],
            "counted_forensic": [r for r in counted if r["run"]["mode"] == "forensic"],
            "warmup_ids": warmup_ids, "ledger_rows": ledger_rows}


def assert_double_marked(records):
    """D-270 隔离自检：每条记录都必须**双重**带标（`synthetic` 块 + `SYNTH-` 前缀）。

    在写盘**之前**跑；任一条不成立就不产出任何文件。
    """
    bad = [(r.get("run") or {}).get("run_id") for r in records
           if not isinstance(r.get("synthetic"), dict)
           or not str(((r.get("run") or {}).get("campaign") or {})
                      .get("campaign_id", "")).startswith(CAMPAIGN_PREFIX)]
    if bad:
        raise ValueError(f"隔离自检失败：{len(bad)} 条记录缺合成标记，例：{bad[0]}")
    return len(records)


def write_expansion_artifacts(prefix, bundle):
    """写出五份产物，返回路径列表。隔离自检先行——不合格就一个文件都不写。"""
    assert_double_marked(bundle["raw"])
    paths = []
    for key, suffix in EXPANSION_ARTIFACTS:
        p = prefix + suffix
        with open(p, "w", encoding="utf-8") as f:
            for r in bundle[key]:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        paths.append(p)
    ledger = prefix + WARMUP_LEDGER_SUFFIX
    with open(ledger, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(WARMUP_LEDGER_HEADER)
        w.writerows(bundle["ledger_rows"])
    paths.append(ledger)
    return paths


def _expansion_conflicts(args):
    """扩展轮模式与哪些参数冲突。**列出来拒绝，而不是静默忽略**——一个被悄悄
    忽略的 `--repeats 5` 会让操作者以为自己拿到的是每格 5 条。"""
    out = []
    if args.repeats is not None:
        out.append("--repeats：扩展轮拆成 --counted-repeats + --warmup-runs")
    if args.chaos:
        out.append("--chaos：会删记录/改 mode，取证轮转与每格 n 随之失真")
    if args.unlabelled:
        out.append("--unlabelled：剥掉 run.campaign 后格与台账都无从认")
    if args.tiers is not None and len(args.tiers.split(",")) != 1:
        out.append("--tiers：扩展轮是单层级（D-48 单实例 E-01），请只给一个")
    if args.campaigns is not None and len(args.campaigns.split(",")) != 1:
        out.append("--campaigns：扩展轮是单战役，请只给一个")
    if args.out.endswith(".jsonl"):
        out.append("-o：扩展轮模式下它是**路径前缀**，不要以 .jsonl 结尾")
    return out


def _main_expansion(args):
    conflicts = _expansion_conflicts(args)
    if conflicts:
        print("--expansion 与以下参数冲突（拒绝静默忽略）：", file=sys.stderr)
        for c in conflicts:
            print("  - " + c, file=sys.stderr)
        return 2
    bundle = generate_expansion(
        points=args.points, carriers=tuple(args.carriers.split(",")),
        time_bands=tuple(args.time_bands.split(",")),
        tier=args.tiers or EXPANSION_TIER, campaign=args.campaigns or EXPANSION_CAMPAIGN,
        counted_repeats=args.counted_repeats,
        warmup_runs=args.warmup_runs, forensic_points=args.forensic_points,
        forensic_runs_per_cell=args.forensic_runs,
        forensic_warmup_runs=args.forensic_warmup_runs, seed=args.seed)
    try:
        paths = write_expansion_artifacts(args.out, bundle)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    cells = {_expansion_cell_key(r) for r in bundle["counted"]}
    quick_n = Counter(_expansion_cell_key(r) for r in bundle["counted_quick"])
    per_cell = sorted(set(quick_n.values()))
    print(WARNING)
    for key, path in zip([k for k, _ in EXPANSION_ARTIFACTS], paths):
        print(f"{key:16s}: {len(bundle[key]):5d} runs -> {path}")
    print(f"{'warmup_ledger':16s}: {len(bundle['ledger_rows']):5d} 条"
          f"（{WARMUP_DISPOSITION}，authority={WARMUP_AUTHORITY}）-> {paths[-1]}")
    print(f"格数 (counted) = {len(cells)}；quick 每格计入 n = {per_cell}")
    print(f"取证 run 数 (counted) = {len(bundle['counted_forensic'])}"
          f"；scenario_order 轮次数 = {len(FORENSIC_SCENARIO_ORDER.split('|'))}"
          f"；radio = on（--expansion 隐含）")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(
        description="Generate a SYNTHETIC ANEB campaign corpus (rehearsal only — "
                    "the numbers are fabricated, never present them as measurements)")
    ap.add_argument("-o", "--out", required=True,
                    help="output JSONL path — or, with --expansion, the PATH "
                         "PREFIX the five expansion artifacts hang off")
    ap.add_argument("--points", type=int, default=8)
    # default is None, not 5, so --expansion can REFUSE an explicitly passed
    # --repeats instead of silently ignoring it (the expansion round splits it
    # into --counted-repeats + --warmup-runs).
    ap.add_argument("--repeats", type=int, default=None,
                    help="repeats per cell (default 5; not valid with --expansion)")
    ap.add_argument("--carriers", default="cmcc,cucc")
    ap.add_argument("--time-bands", default="busy,idle")
    # None rather than the M2 default, for the same reason as --repeats: with
    # --expansion these have DIFFERENT defaults (single tier, single campaign),
    # and an explicitly passed multi-value list must be refused, not overridden.
    ap.add_argument("--tiers", default=None,
                    help="comma-separated tiers (default metro,regional,core; "
                         "with --expansion exactly one, default %s)" % EXPANSION_TIER)
    ap.add_argument("--campaigns", default=None,
                    help="comma-separated campaign ids (all get the SYNTH- prefix; "
                         "default base,opt; with --expansion exactly one, default %s)"
                         % EXPANSION_CAMPAIGN)
    ap.add_argument("--seed", type=int, default=20260725)
    ap.add_argument("--unlabelled", action="store_true",
                    help="strip run.campaign, matching what the app emits TODAY "
                         "(label wiring not landed) — so a rehearsal also practises "
                         "the annotate step, the one most likely to go wrong")
    ap.add_argument("--radio", action="store_true",
                    help="attach a synthetic network_snapshot.radio block to "
                         "cellular scenarios — the shape docs/"
                         "RADIO_CONTEXT_WIRING_SPEC.md asks the app to emit, so "
                         "the rollup can be rehearsed before the wiring lands")
    ap.add_argument("--chaos", action="store_true",
                    help="seed realistic field pathologies (missing tier, aborted "
                         "runs, mixed profile versions, clock jumps, all-invalid "
                         "cell, unlabelled records…) to rehearse honest degradation")
    ap.add_argument("--expansion", action="store_true",
                    help="generate the M3 EXPANSION-ROUND shape instead of the M2 "
                         "grid: a quick body with one discarded warm-up run per "
                         "cell (ledger = the only thing that knows which), a "
                         "forensic subset on a 3x3 Latin square, and s2 scenario-"
                         "intrinsic jitter. -o becomes a path PREFIX and five "
                         "artifacts are written; --radio is implied")
    ap.add_argument("--counted-repeats", type=int, default=EXPANSION_COUNTED_REPEATS,
                    help="expansion: repeats per cell that COUNT (default %d)"
                         % EXPANSION_COUNTED_REPEATS)
    ap.add_argument("--warmup-runs", type=int, default=EXPANSION_WARMUP_RUNS,
                    help="expansion: discarded warm-up runs per quick cell "
                         "(default %d)" % EXPANSION_WARMUP_RUNS)
    ap.add_argument("--forensic-points", type=int, default=2,
                    help="expansion: how many leading points carry the forensic "
                         "subset (default 2)")
    ap.add_argument("--forensic-runs", type=int, default=EXPANSION_FORENSIC_RUNS,
                    help="expansion: counted forensic runs per forensic cell "
                         "(default %d)" % EXPANSION_FORENSIC_RUNS)
    ap.add_argument("--forensic-warmup-runs", type=int, default=1,
                    help="expansion: discarded warm-up runs per forensic cell")
    args = ap.parse_args(argv)

    if args.expansion:
        return _main_expansion(args)

    recs = generate(points=args.points,
                    repeats=5 if args.repeats is None else args.repeats,
                    carriers=tuple(args.carriers.split(",")),
                    time_bands=tuple(args.time_bands.split(",")),
                    tiers=tuple((args.tiers or "metro,regional,core").split(",")),
                    campaigns=tuple((args.campaigns or "base,opt").split(",")),
                    seed=args.seed, radio=args.radio)
    if args.chaos:
        recs = inject_chaos(recs, seed=args.seed + 1)
        print("chaos: " + "; ".join(name for name, _ in CHAOS_PATHOLOGIES))
    if args.unlabelled:
        # the additive `synthetic` block stays, so these are still detectable as
        # fabricated even with no campaign_id prefix to give them away
        for r in recs:
            r["run"].pop("campaign", None)
        print("unlabelled: run.campaign stripped (rehearse the annotate step)")
    with open(args.out, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    scenarios = sum(len(r["scenarios"]) for r in recs)
    print(f"{WARNING}\nwrote {len(recs)} runs / {scenarios} scenarios -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
