# -*- coding: utf-8 -*-
"""Is the first-round penalty a radio wake or an app/TLS cold start?

D-355 measured a first-round penalty over cellular. Two explanations fit: the
radio waking (RRC/C-DRX) or the app/TLS path starting cold. WiFi has no radio
wake worth speaking of, so repeating the experiment over WiFi separates them.

Design note: the quantity compared is the WITHIN-RUN delta (round 0 against the
later rounds of the SAME run), which is paired - so a slow drift between the two
capture windows (cellular 14:58-15:43, wifi 16:23-16:50) cannot manufacture or
hide the effect. Absolute levels are NOT robust that way and are printed only as
context, never as the comparison.
"""
import io
import json
import os
import statistics as st
from collections import defaultdict

# The archived dual-arm corpus in THIS directory (D-364: the first version
# pointed at a session-scratchpad file that dies with the session, contradicting
# the README's "只读本目录的语料、可复跑" promise; numbers verified identical).
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "transport_probe_labelled.jsonl")
KPIS = ("t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps")
HIGHER_BETTER = {"u1_goodput_mbps"}

records = [json.loads(l) for l in io.open(PATH, encoding="utf-8-sig") if l.strip()]
forensic = [r for r in records if r["run"].get("mode") == "forensic"]

by_tp = defaultdict(list)
for rec in forensic:
    by_tp[rec["run"].get("transport")].append(rec)

print("forensic runs by transport:", {k: len(v) for k, v in sorted(by_tp.items())})

for kpi in KPIS:
    print("=" * 66)
    print(kpi, "(higher is better)" if kpi in HIGHER_BETTER else "(lower is better)")
    for tp in sorted(by_tp):
        per_run_deltas, first_all, rest_all = [], [], []
        for rec in by_tp[tp]:
            rounds = defaultdict(list)
            for scn in rec.get("scenarios") or []:
                v = (scn.get("kpi") or {}).get(kpi)
                ri = scn.get("repeat_index")
                if isinstance(v, (int, float)) and isinstance(ri, int):
                    rounds[ri].append(v)
            if len(rounds) < 2:
                continue
            first_key = min(rounds)
            first = st.median(rounds[first_key])
            rest = st.median([x for r, vs in rounds.items() if r != first_key for x in vs])
            first_all.append(first)
            rest_all.append(rest)
            # positive = first round WORSE, as a percentage of the later rounds
            d = (rest - first) if kpi in HIGHER_BETTER else (first - rest)
            per_run_deltas.append(d / abs(rest) * 100.0)
        if not per_run_deltas:
            print("  %-9s no usable runs" % tp)
            continue
        print("  %-9s runs=%d  per-run first-round penalty%%: %s"
              % (tp, len(per_run_deltas),
                 " ".join("%+.1f" % d for d in sorted(per_run_deltas))))
        print("  %-9s median penalty = %+.1f%%   (context only: first=%.2f rest=%.2f)"
              % ("", st.median(per_run_deltas), st.median(first_all), st.median(rest_all)))
