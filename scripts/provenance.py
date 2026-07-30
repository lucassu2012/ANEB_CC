#!/usr/bin/env python3
"""ANEB report provenance / reproducibility manifest (stdlib only).

A published heat/attribution report is "ammunition into the bureau" (M2) — it must
be traceable to the exact inputs it was built from and reproducible. The project
already treats sha256 provenance as doctrine (verify_all regenerates a sha256
manifest of evidence/), yet the campaign reports carried only a timestamp + record
count. This attaches the missing chain of custody.

A manifest records:
  * each input file's basename + sha256 (content identity, not the local path)
  * lines read / records kept / duplicates dropped / conflicts / malformed /
    records with no run_id (the load-path decisions from D-93 dedup — what was
    and wasn't counted). The last one was emitted but neither listed here nor
    rendered: the description said five, build() sent six, the page showed four
    (D-333).
  * the tool parameters that shaped the numbers (min_samples, attr_kpi, …)
  * tool version + an injected generated_at (injected, not wall-clocked, so the
    deterministic report body stays snapshot-testable)

Rendered as a compact report-header block and writable as a sidecar JSON.
"""
import hashlib
import json
import os

import campaign_common as cc

TOOL_VERSION = "aneb-campaign-analysis/1.0"
_SHORT = 12   # chars of sha256 shown inline (full hash kept in the sidecar JSON)


def file_sha256(path):
    """Streaming sha256 of a file's bytes, or None if unreadable."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def compute(files, load_stats, params, generated_at, tool_version=TOOL_VERSION,
            thresholds=None):
    """Build the manifest dict. generated_at is INJECTED (caller supplies it) so
    the core stays deterministic; load_stats is the dict from cc.load_records.

    `thresholds` closes a hole in the reproducibility claim (D-122): `params`
    only covers the CLI-settable knobs, but the module-level gates (CV gate,
    validity floor, AQS grade bands, hot-spot shares, which KPIs get sections)
    equally decide what the report says. Retune one of those and a re-run yields
    different numbers under an identical-looking manifest — exactly what a
    provenance record exists to prevent."""
    inputs = []
    for p in sorted(set(files)):
        inputs.append({"file": os.path.basename(p), "sha256": file_sha256(p)})
    st = load_stats or {}
    return {
        "tool_version": tool_version,
        "generated_at": generated_at,
        "inputs": inputs,
        "input_count": len(inputs),
        "lines_read": st.get("lines"),
        "records_kept": st.get("kept"),
        "duplicates_dropped": st.get("duplicates"),
        "conflicting_run_ids": list(st.get("conflicts") or []),
        "no_run_id": st.get("no_run_id"),
        "malformed_lines": st.get("malformed"),
        "params": dict(params or {}),
        "thresholds": dict(thresholds or {}),
    }


def render_markdown(prov):
    lines = [
        "## 溯源 / provenance（可复现性）",
        "",
        f"> 工具 `{prov['tool_version']}` · 生成 {prov['generated_at']} · "
        f"读 {prov['lines_read']} 行 → 保留 {prov['records_kept']} 条"
        f"（去重丢 {prov['duplicates_dropped']}"
        + (f"，冲突 {len(prov['conflicting_run_ids'])}" if prov["conflicting_run_ids"] else "")
        + (f"，坏行 {prov['malformed_lines']}" if prov["malformed_lines"] else "")
        # Emitted into the sidecar since D-93 and never rendered. It belongs
        # beside the other two: these records cannot be de-duplicated at all
        # (R-10 forbids a fabricated key), so repeats among them are invisible
        # and the kept count may exceed the runs actually performed — which is
        # precisely what this line exists to disclose (D-333).
        + (f"，无 run_id {prov['no_run_id']}" if prov.get("no_run_id") else "")
        + f"）。参数 {json.dumps(prov['params'], ensure_ascii=False)}。",
        "",
    ]
    if prov.get("thresholds"):
        lines += ["> **生效门限**（改动其一即改变报告结论，复现须同值）："
                  f"{json.dumps(prov['thresholds'], ensure_ascii=False)}", ""]
    lines += [
        "| 输入文件 | sha256 |",
        "|---|---|",
    ]
    if not prov["inputs"]:
        lines.append("| _（无）_ | — |")
    for inp in prov["inputs"]:
        sha = inp["sha256"]
        short = (sha[:_SHORT] + "…") if sha else "（不可读）"
        # a basename may legally contain '|' on POSIX, and this is a table cell
        # like any other — the sidecar JSON still carries the raw name (D-334)
        lines.append(f"| {cc.md_cell(inp['file'])} | `{short}` |")
    lines.append("")
    return "\n".join(lines)


def write_sidecar(prov, path):
    """Write the full manifest (full sha256 hashes) as JSON next to the report."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(prov, f, ensure_ascii=False, indent=2, sort_keys=True)
    return path
