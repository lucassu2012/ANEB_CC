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
import json
import random
import sys

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


def _scenario(rng, idx, rtt, *, order_index, suspect_clock, batching, transport,
              noise=0.045):
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
                  "drift_ppm": round(drift, 2), "offset_suspect": bool(suspect_clock)},
        "network_snapshot": {"transport": transport, "capabilities": "INTERNET,VALIDATED",
                             "interface": "rmnet0" if transport == "cellular" else "wlan0",
                             "server_observed_addr": "203.0.113.7:8443"},
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
             campaigns=("base", "opt"), seed=20260725, start_ms=1783944000000):
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
                                          batching=batching_point and band == "busy",
                                          transport=medium, noise=noise)
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
                                        "carrier": carrier, "time_band": band},
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


def main(argv):
    ap = argparse.ArgumentParser(
        description="Generate a SYNTHETIC ANEB campaign corpus (rehearsal only — "
                    "the numbers are fabricated, never present them as measurements)")
    ap.add_argument("-o", "--out", required=True, help="output JSONL path")
    ap.add_argument("--points", type=int, default=8)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--carriers", default="cmcc,cucc")
    ap.add_argument("--time-bands", default="busy,idle")
    ap.add_argument("--tiers", default="metro,regional,core")
    ap.add_argument("--campaigns", default="base,opt",
                    help="comma-separated campaign ids (all get the SYNTH- prefix)")
    ap.add_argument("--seed", type=int, default=20260725)
    ap.add_argument("--unlabelled", action="store_true",
                    help="strip run.campaign, matching what the app emits TODAY "
                         "(label wiring not landed) — so a rehearsal also practises "
                         "the annotate step, the one most likely to go wrong")
    ap.add_argument("--chaos", action="store_true",
                    help="seed realistic field pathologies (missing tier, aborted "
                         "runs, mixed profile versions, clock jumps, all-invalid "
                         "cell, unlabelled records…) to rehearse honest degradation")
    args = ap.parse_args(argv)

    recs = generate(points=args.points, repeats=args.repeats,
                    carriers=tuple(args.carriers.split(",")),
                    time_bands=tuple(args.time_bands.split(",")),
                    tiers=tuple(args.tiers.split(",")),
                    campaigns=tuple(args.campaigns.split(",")), seed=args.seed)
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
