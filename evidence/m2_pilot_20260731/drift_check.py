# -*- coding: utf-8 -*-
"""Are the 11 pilot runs exchangeable, or do they drift across the window?

The sample-size plan (needed n, detectable difference) treats a cell's repeats as
draws from one distribution. If the KPIs trend across the 26-minute capture -
thermal, server warm-up, network load - the repeats are not exchangeable, the CV
understates the spread of a single reading, and a larger n buys less than the plan
says. Measured, not assumed.

Per KPI: the run series in capture order, a rank correlation with elapsed time
(computed by hand - stdlib only, same rule as the rest of the layer), and the
first-half vs second-half medians.
"""
import io
import json
import statistics as st

PATH = r"E:\C Project\ANEB\evidence\m2_pilot_20260731\pilot_labelled.jsonl"
KPIS = ("t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps")


def rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    for pos, i in enumerate(order):
        r[i] = float(pos)
    return r


def spearman(a, b):
    ra, rb = rank(a), rank(b)
    n = len(a)
    if n < 3:
        return None
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return None if da == 0 or db == 0 else num / (da * db)


records = [json.loads(l) for l in io.open(PATH, encoding="utf-8-sig") if l.strip()]
# quick runs only, in capture order; the 13:38 verification run is idle-band and
# is excluded so this measures the campaign window itself
quick = sorted((r for r in records
                if r["run"].get("mode") == "quick"
                and (r["run"].get("campaign") or {}).get("time_band") != "idle"),
               key=lambda r: r["run"]["started_at_epoch_ms"])
print("quick runs in the busy window:", len(quick))
t0 = quick[0]["run"]["started_at_epoch_ms"]
mins = [(r["run"]["started_at_epoch_ms"] - t0) / 60000.0 for r in quick]
print("window span (min): %.1f" % mins[-1])

for kpi in KPIS:
    vals = []
    for r in quick:
        per_run = [v for v in ((s.get("kpi") or {}).get(kpi) for s in r["scenarios"])
                   if isinstance(v, (int, float))]
        vals.append(st.median(per_run) if per_run else None)
    pairs = [(m, v) for m, v in zip(mins, vals) if v is not None]
    if len(pairs) < 3:
        print(kpi, "-> too few runs")
        continue
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    rho = spearman(xs, ys)
    half = len(ys) // 2
    first, second = st.median(ys[:half]), st.median(ys[half:])
    print("%-18s n=%2d  rho_time=%+.2f  first-half=%8.2f  second-half=%8.2f  (%+.1f%%)"
          % (kpi, len(ys), rho, first, second, (second - first) / first * 100.0))
    print("      series:", " ".join("%.1f" % y for y in ys))
