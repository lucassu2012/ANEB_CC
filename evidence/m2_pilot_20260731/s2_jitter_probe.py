"""Read-only: why does s2_coding_agent's TTFT wobble (CV 10.3% vs 5.5/5.9)?

Pilot report recommendation 1 left this open: 's2 CV 超门,先定位它为何抖'.
Candidates checkable from existing corpora alone:
  H1 one outlier run drives the CV (drop-one CV collapses);
  H2 a time trend (warm-up across the campaign, rank correlation with order);
  H3 uniformly wider noise (drop-one barely moves, no trend) — intrinsic to the
     profile's heavier phases (512KB upload + tool_loop before the stream).
Corpus: the 11 counted busy quick runs (pilot_labelled.jsonl, campaign m2-pilot).
"""
import json
import statistics

P = r"E:\C Project\ANEB\evidence\m2_pilot_20260731\pilot_labelled.jsonl"
recs = [json.loads(l) for l in open(P, encoding="utf-8") if l.strip()]
rows = []
for r in recs:
    tb = ((r.get("campaign") or {}).get("time_band")
          or ((r.get("run") or {}).get("campaign") or {}).get("time_band"))
    if tb != "busy":
        continue
    started = (r.get("run") or {}).get("started_at_epoch_ms")
    for s in r.get("scenarios", []):
        if s.get("profile_id") != "s2_coding_agent":
            continue
        k = s.get("kpi") or {}
        rows.append({"t": started, "ttft": k.get("t1_ttft_ms"),
                     "rtt": k.get("n1_rtt_p50_ms"), "u2": k.get("u2_tool_loop_p95_ms")})
rows.sort(key=lambda x: x["t"])
vals = [x["ttft"] for x in rows if x["ttft"] is not None]
print(f"n={len(vals)} ttft values: {[round(v,1) for v in vals]}")


def cv(v):
    return statistics.stdev(v) / statistics.mean(v) * 100


print(f"CV all: {cv(vals):.1f}%")
print("drop-one CVs:", [round(cv(vals[:i] + vals[i+1:]), 1) for i in range(len(vals))])
ranks_t = list(range(len(vals)))
order = sorted(range(len(vals)), key=lambda i: vals[i])
rank_of = [0] * len(vals)
for rk, i in enumerate(order):
    rank_of[i] = rk
n = len(vals)
rho = 1 - 6 * sum((ranks_t[i] - rank_of[i]) ** 2 for i in range(n)) / (n * (n * n - 1))
print(f"spearman rho (time vs ttft): {rho:+.2f}")
rtts = [x["rtt"] for x in rows if x["rtt"] is not None]
print(f"rtt CV: {cv(rtts):.1f}%  (same-run RTT wobble = network-side; flat RTT + "
      "wobbly TTFT = server/scenario-side)")
pairs = [(x["ttft"], x["rtt"]) for x in rows if x["ttft"] and x["rtt"]]
mt = statistics.mean(p[0] for p in pairs)
mr = statistics.mean(p[1] for p in pairs)
num = sum((a - mt) * (b - mr) for a, b in pairs)
den = (sum((a - mt) ** 2 for a, _ in pairs) * sum((b - mr) ** 2 for _, b in pairs)) ** 0.5
print(f"pearson ttft~rtt: {num/den:+.2f}  (high = network path explains the wobble)")
