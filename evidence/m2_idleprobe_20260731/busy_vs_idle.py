"""busy vs idle, warm rounds only - the one grid question the pilot could not answer.

Usage:  python busy_vs_idle.py <busy_forensic.jsonl> <idle_forensic.jsonl>

Method (decided before the idle data exists, so the data cannot bend it):
- WARM ROUNDS ONLY: scenarios with repeat_index >= 1. D-355/D-358 showed round 1
  is systematically worse (radio wake + residual app cold start); reading rounds
  2-3 keeps a cold-start penalty from masquerading as a time-of-day effect.
- Per profile x KPI: median of warm values per band, gap %, and BOTH bands'
  min-max spreads. Per handover 2.8 a difference needs a scale to mean anything:
  verdict is "exceeds noise" only when the two warm ranges do not overlap at
  all - the crudest honest scale for n=8 per side; anything subtler would be
  ceremony at this sample size.
- u1_goodput for s1_chat is annotated as a latency proxy, not throughput
  (D-363: 2KB completes inside ~2 RTT; its Mbps carries no bandwidth signal).
- Honesty guards: only run.status == completed records count; a corpus whose
  scenarios are all repeat_index 0 (quick mode) is refused, not silently
  averaged; per-band n is printed on every row.

This is a methodology probe for the idle campaign's own evidence dir - it never
feeds the M2 claim. stdlib only.
"""
import json
import statistics
import sys

KPIS = ("t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps")
LOWER_IS_BETTER = {"t1_ttft_ms": True, "n1_rtt_p50_ms": True, "u1_goodput_mbps": False}


def load_warm(path):
    """{(profile_id, kpi): [warm values]}, plus corpus facts for the header."""
    vals, runs, bands, warm_seen = {}, 0, set(), False
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if (rec.get("run") or {}).get("status") != "completed":
                continue
            runs += 1
            tb = ((rec.get("campaign") or {}).get("time_band")
                  or ((rec.get("run") or {}).get("campaign") or {}).get("time_band"))
            if tb:
                bands.add(tb)
            for scn in (rec.get("scenarios") or []):
                ri = scn.get("repeat_index")
                if not isinstance(ri, int) or ri < 1:
                    continue
                warm_seen = True
                pid = scn.get("profile_id")
                for k in KPIS:
                    v = (scn.get("kpi") or {}).get(k)
                    if isinstance(v, dict):
                        v = v.get("value")
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        vals.setdefault((pid, k), []).append(float(v))
    if not warm_seen:
        sys.exit(f"REFUSED: {path} has no warm rounds (repeat_index>=1) - "
                 "quick-mode corpus? This comparison is defined on forensic data only.")
    return vals, runs, bands


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    busy, busy_runs, busy_bands = load_warm(sys.argv[1])
    idle, idle_runs, idle_bands = load_warm(sys.argv[2])
    print(f"busy corpus: {busy_runs} completed run(s), time_band={sorted(busy_bands)}")
    print(f"idle corpus: {idle_runs} completed run(s), time_band={sorted(idle_bands)}")
    if busy_bands & idle_bands:
        print("WARNING: the two corpora share a time_band label - check the pull windows.")
    print()
    hdr = "%-18s %-18s %10s %10s %8s  %-23s %-23s  %s"
    print(hdr % ("profile", "kpi", "busy med", "idle med", "gap%",
                 "busy warm range (n)", "idle warm range (n)", "verdict"))
    for pid in sorted({p for p, _ in list(busy) + list(idle)}):
        for k in KPIS:
            b, i = busy.get((pid, k)), idle.get((pid, k))
            if not b or not i:
                print(hdr % (pid, k, "-", "-", "-",
                             f"n={len(b or [])}", f"n={len(i or [])}",
                             "CANNOT JUDGE: a side is empty"))
                continue
            bm, im = statistics.median(b), statistics.median(i)
            gap = (im - bm) / bm * 100.0 if bm else float("nan")
            disjoint = max(b) < min(i) or max(i) < min(b)
            if disjoint:
                worse_busy = (bm > im) if LOWER_IS_BETTER[k] else (bm < im)
                verdict = "EXCEEDS NOISE: busy worse" if worse_busy else "EXCEEDS NOISE: idle worse"
            else:
                verdict = "within noise (ranges overlap)"
            note = "  [D-363: latency proxy, not throughput]" \
                if (pid == "s1_chat" and k == "u1_goodput_mbps") else ""
            print(hdr % (pid, k, f"{bm:.2f}", f"{im:.2f}", f"{gap:+.1f}",
                         f"{min(b):.2f}-{max(b):.2f} ({len(b)})",
                         f"{min(i):.2f}-{max(i):.2f} ({len(i)})",
                         verdict + note))
    print()
    print("Verdict rule, decided a priori: EXCEEDS NOISE only when the two warm")
    print("ranges are fully disjoint. Overlapping ranges at n~8/side prove nothing")
    print("in either direction - that is 'cannot tell', not 'no difference'.")


if __name__ == "__main__":
    main()
