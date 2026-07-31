# -*- coding: utf-8 -*-
"""One-shot measurement: are forensic round-1 KPIs systematically worse?

The order-effect section groups by absolute order_index (0..8), which for a
three-round Latin square puts each profile's three positions in three different
ROUNDS. So its verdict may be reading a warm-up effect rather than a within-round
position effect. This slices the same corpus by repeat_index (the round) and by
position within the round, to tell the two apart - measured, not argued.
"""
import io
import json
import statistics as st
from collections import defaultdict

PATH = r"E:\C Project\ANEB\evidence\m2_pilot_20260731\forensic_labelled.jsonl"
KPIS = ("t1_ttft_ms", "n1_rtt_p50_ms", "u1_goodput_mbps")

records = [json.loads(l) for l in io.open(PATH, encoding="utf-8-sig") if l.strip()]

by_round = defaultdict(lambda: defaultdict(list))
by_slot = defaultdict(lambda: defaultdict(list))
for rec in records:
    for scn in rec.get("scenarios") or []:
        rnd = scn.get("repeat_index")
        oi = scn.get("order_index")
        slot = None if oi is None else oi % 3          # position WITHIN the round
        for k in KPIS:
            v = (scn.get("kpi") or {}).get(k)
            if isinstance(v, (int, float)):
                by_round[k][rnd].append(v)
                by_slot[k][slot].append(v)

for label, table in (("BY ROUND (repeat_index)", table_a := by_round),
                     ("BY SLOT WITHIN ROUND (order_index mod 3)", by_slot)):
    print("=" * 62)
    print(label)
    for k in KPIS:
        rows = table[k]
        base = None
        print("  " + k)
        for key in sorted(rows, key=lambda x: (x is None, x)):
            med = st.median(rows[key])
            if base is None:
                base = med
            print("     %s: n=%2d  median=%9.3f   vs first: %+6.1f%%"
                  % (key, len(rows[key]), med, (med - base) / base * 100.0))
