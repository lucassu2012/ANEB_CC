#!/usr/bin/env python3
"""Offline campaign-label annotation for ANEB results JSONL (stdlib only).

Injects the OPTIONAL run.campaign block (docs/CAMPAIGN_LABELS_CONVENTION.md) into
existing result records so the campaign-analysis layer (campaign_report.py /
attribution.py) is usable on real data BEFORE the app-side wiring lands (spec
additive def + ResultReporter + P1a tag UI — convention §4).

Additive & non-destructive: existing fields are preserved; only run.campaign is
merged/added; provenance is recorded in run.campaign.label_source. The input file
is never overwritten unless --inplace is given explicitly.

Precedence (high -> low): labels already on the record win, then --map (per
run_id), then --set (uniform), then --infer-time-band. A layer only fills gaps a
higher layer left — an explicit app-written label is never clobbered.

Usage:
    python annotate_campaign.py in.jsonl -o out.jsonl \
        --set point_id=SZ-CBD-01 --set carrier=cmcc --set tier=metro \
        --set campaign_id=sz-2026Q3-baseline --infer-time-band
"""
import argparse
import copy
import glob
import json
import os
import sys

import campaign_common as cc

CAMPAIGN_KEYS = ("campaign_id", "tier", "point_id", "carrier", "time_band",
                 "server_tier_endpoint")
DEFAULT_TZ_OFFSET_H = 8  # China Standard Time; records carry no tz, so state it explicitly
# 忙时(busy) local-hour set: morning + afternoon/evening peaks. Approximation, flagged inferred.
DEFAULT_BUSY_HOURS = frozenset(range(8, 12)) | frozenset(range(14, 23))


def infer_time_band(epoch_ms, tz_offset_h=DEFAULT_TZ_OFFSET_H, busy_hours=DEFAULT_BUSY_HOURS):
    """Local-hour heuristic, deterministic from the epoch (no wall clock). None if
    no usable epoch. Result is an approximation — callers mark it inferred."""
    v = cc.fnum(epoch_ms)
    if v is None:
        return None
    hour = int((v // 1000 // 3600 + tz_offset_h) % 24)
    return "busy" if hour in busy_hours else "idle"


def annotate_record(rec, uniform=None, mapping=None, infer_tb=False,
                    tz_offset_h=DEFAULT_TZ_OFFSET_H):
    """Return (new_record, changed). Non-destructive: the input rec is deep-copied.
    run.campaign is merged; only gaps are filled; label_source records what added."""
    rec = copy.deepcopy(rec)
    run = rec.setdefault("run", {})
    final = dict(run.get("campaign") or {})   # original labels start in `final`, so they win
    used = []

    def layer(pairs, tag):
        added = False
        for k, v in pairs:
            if k not in final:                # never override a higher-precedence value
                final[k] = v
                added = True
        if added:
            used.append(tag)

    rid = run.get("run_id")
    per_run = (mapping or {}).get(rid) if rid is not None else None
    if per_run:
        layer(list(per_run.items()), f"map:{rid}")
    if uniform:
        layer(list(uniform.items()), "set")
    if infer_tb:
        tb = infer_time_band(run.get("started_at_epoch_ms"), tz_offset_h)
        if tb is not None:
            layer([("time_band", tb)], "inferred:time_band")

    if used:
        prior = [final["label_source"]] if final.get("label_source") else []
        final["label_source"] = "+".join(prior + used)
        run["campaign"] = final
    elif final:
        run["campaign"] = final
    return rec, bool(used)


def annotate(records, uniform=None, mapping=None, infer_tb=False,
             tz_offset_h=DEFAULT_TZ_OFFSET_H):
    out, changed = [], 0
    for rec in records:
        r, ch = annotate_record(rec, uniform, mapping, infer_tb, tz_offset_h)
        out.append(r)
        changed += int(ch)
    return out, changed


# ---------------------------------------------------------------- CLI

def _parse_set(pairs):
    labels = {}
    for item in pairs or []:
        if "=" not in item:
            raise SystemExit(f"--set expects KEY=VALUE, got: {item}")
        k, v = item.split("=", 1)
        k = k.strip()
        if k not in CAMPAIGN_KEYS:
            raise SystemExit(f"--set unknown label key '{k}'; allowed: {', '.join(CAMPAIGN_KEYS)}")
        labels[k] = v.strip()
    return labels


def _write_jsonl(records, fh):
    for r in records:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv):
    ap = argparse.ArgumentParser(description="Offline ANEB campaign-label annotation")
    ap.add_argument("inputs", nargs="+", help="results JSONL file(s)")
    ap.add_argument("-o", "--output", help="output path (single input only; else stdout/--inplace)")
    ap.add_argument("--out-dir", help="batch: write each annotated input to DIR/<same filename> "
                                      "(a field day has dozens of files; -o one at a time is the "
                                      "main manual-error source)")
    ap.add_argument("--inplace", action="store_true", help="overwrite each input in place")
    ap.add_argument("--set", dest="sets", action="append", metavar="KEY=VALUE",
                    help="uniform label, repeatable (keys: " + ",".join(CAMPAIGN_KEYS) + ")")
    ap.add_argument("--map", dest="map_path", help="JSON {run_id: {label:value,...}}")
    ap.add_argument("--infer-time-band", action="store_true",
                    help="fill time_band from started_at_epoch_ms local hour (inferred)")
    ap.add_argument("--tz-offset", type=int, default=DEFAULT_TZ_OFFSET_H,
                    help=f"local UTC offset hours for inference (default {DEFAULT_TZ_OFFSET_H})")
    args = ap.parse_args(argv)
    cc.force_utf8_stdout()

    uniform = _parse_set(args.sets)
    mapping = None
    if args.map_path:
        with open(args.map_path, encoding="utf-8") as f:
            mapping = json.load(f)

    # Expand globs HERE, not per-file inside the loop: PowerShell (the primary
    # shell on this project) does not expand wildcards for external programs, so
    # a documented `raw/day1_*.jsonl` would otherwise reach --out-dir as a literal
    # filename containing '*'. A pattern matching nothing is a mistake, not a
    # no-op — silently writing an empty output is exactly the failure mode this
    # toolkit refuses everywhere else.
    inputs = []
    for pat in args.inputs:
        hits = sorted(glob.glob(pat))
        if not hits:
            raise SystemExit(f"no files match: {pat}")
        inputs.extend(hits)

    if sum(bool(x) for x in (args.output, args.out_dir, args.inplace)) > 1:
        raise SystemExit("choose ONE of -o/--output, --out-dir, --inplace")
    if len(inputs) > 1 and not (args.inplace or args.out_dir):
        raise SystemExit("multiple inputs require --out-dir (batch) or --inplace "
                         "(or annotate one at a time with -o)")
    if args.output and len(inputs) != 1:
        raise SystemExit("-o/--output is only valid with a single input")
    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        seen = {}
        for path in inputs:
            name = os.path.basename(path)
            dest = os.path.abspath(os.path.join(args.out_dir, name))
            # never let a batch run masquerade as --inplace, and never let two
            # inputs from different directories collide onto one output
            if dest == os.path.abspath(path):
                raise SystemExit(f"--out-dir would overwrite the input {path}; "
                                 "use --inplace if that is what you mean")
            if dest in seen:
                raise SystemExit(f"two inputs share the basename '{name}' "
                                 f"({seen[dest]} and {path}) — they would collide in --out-dir")
            seen[dest] = path

    total = total_changed = 0
    for path in inputs:
        recs, _ = cc.load_records([path])
        out, changed = annotate(recs, uniform, mapping, args.infer_time_band, args.tz_offset)
        total += len(out)
        total_changed += changed
        if args.inplace:
            with open(path, "w", encoding="utf-8") as f:
                _write_jsonl(out, f)
        elif args.out_dir:
            dest = os.path.join(args.out_dir, os.path.basename(path))
            with open(dest, "w", encoding="utf-8") as f:
                _write_jsonl(out, f)
        elif args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                _write_jsonl(out, f)
        else:
            _write_jsonl(out, sys.stdout)
    print(f"annotated {total_changed}/{total} records "
          f"(uniform={list(uniform)}, map={'yes' if mapping else 'no'}, "
          f"infer_time_band={args.infer_time_band})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
