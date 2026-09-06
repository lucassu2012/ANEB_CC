#!/usr/bin/env python3
"""ANEB profile validator: spec<->runtime parity + phase structure (stdlib only).

The inline verify_all `profiles-valid` step checks only the RUNTIME copy for four
present fields + non-empty phases. It never checks the spec authority copy, never
spec<->runtime parity, and never phase internals — so a semantic edit to one copy
but not the other, or a phase missing a required numeric field, slips through.
client_profiles.json has a byte-parity guard; the server profiles have none.

This deepens that gate (铁律1「Profile 即数据」; §7 先改 spec 后动代码):

  (a) PARITY — for each profile, the spec copy (spec/profiles/server/<id>.json) and
      the runtime mirror (profiles/<id>.json) must be SEMANTICALLY equal (parsed
      JSON compared; robust to CRLF/whitespace/key-order, which byte-parity is not).
      Present on one side only is an error.
  (b) STRUCTURE — top-level required fields, and each phase's `type` is known and
      carries its required, correctly-typed fields.

Read-only over both trees. Exit: 0 = PASS / 1 = violations / 2 = a tree is absent
(NOT_EXECUTED).

Usage:
    python validate_profiles.py [--spec spec/profiles/server] [--runtime profiles]
"""
import argparse
import json
import os
import sys

TOP_REQUIRED = ("profile_id", "version", "kpi_set", "phases")

# phase type -> {field: kind}. kind: 'num' (int/float, not bool), 'int', 'map'.
PHASE_SPEC = {
    "clock_sync":    {"samples": "int"},
    "upload_burst":  {"bytes": "num", "chunk_kb": "num"},
    "download_burst": {"bytes": "num", "chunk_kb": "num"},
    "think_pause":   {"duration_ms": "num"},
    "token_stream":  {"tokens": "num", "rate_tps": "num", "token_bytes": "map"},
    "tool_loop":     {"rounds": "num", "up_bytes": "num", "down_bytes": "num",
                      "server_proc_ms": "num"},
    # T47 批②（D-468/D-469，spec/PROFILE2_THROUGHPUT_PROBE_SPEC.md §8.4.1）：单流
    # 自适应窗口 goodput 探针（U3/D3）。bytes 在这两个 type 下语义是「请求上限
    # (ceiling)」而非精确传输量——与 upload_burst/download_burst 的 bytes 含义不同，
    # 这里只做结构/类型校验，不校验语义。
    "adaptive_download_window": {"window_ms": "int", "bytes": "num", "chunk_kb": "num"},
    "adaptive_upload_window":   {"window_ms": "int", "bytes": "num", "chunk_kb": "num"},
}
DEFAULT_SPEC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "spec", "profiles", "server")
DEFAULT_RUNTIME = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "profiles")


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _kind_ok(v, kind):
    if kind == "int":
        return isinstance(v, int) and not isinstance(v, bool)
    if kind == "num":
        return _is_num(v)
    if kind == "map":
        return isinstance(v, dict)
    return False


def check_structure(profile, name):
    """Top-level required fields + per-phase type/field checks. -> [errors]."""
    errs = []
    if not isinstance(profile, dict):
        return [f"{name}: not a JSON object"]
    for field in TOP_REQUIRED:
        if profile.get(field) in (None, ""):
            errs.append(f"{name}: missing '{field}'")
    phases = profile.get("phases")
    if not isinstance(phases, list) or not phases:
        errs.append(f"{name}: 'phases' must be a non-empty array")
        return errs
    for i, ph in enumerate(phases):
        if not isinstance(ph, dict):
            errs.append(f"{name}.phases[{i}]: not an object")
            continue
        ptype = ph.get("type")
        if ptype not in PHASE_SPEC:
            errs.append(f"{name}.phases[{i}]: unknown phase type {ptype!r}")
            continue
        for field, kind in PHASE_SPEC[ptype].items():
            if field not in ph:
                errs.append(f"{name}.phases[{i}] ({ptype}): missing '{field}'")
            elif not _kind_ok(ph[field], kind):
                errs.append(f"{name}.phases[{i}] ({ptype}): '{field}'="
                            f"{ph[field]!r} not a {kind}")
    return errs


# ------------------------------------------------- expected_n（D-707／D-740／D-751）
#
# `expected_n` ＝「这份 profile **该**产出多少个该 KPI 的样本」，**从 phases 推导**（D-739 裁 (a)）。
# 显式声明只作覆盖，两者同在**必须相等**（见 check_expected_n）。
#
# 🔴 **它只是完备性信号，不是门限**（D-740 §2，承重条款）：
# `lowConfidence` 仍由 `KpiCalculator` 的五个 `MIN_*` 常量决定，**本模块一个都不碰**。
# 两者回答不同问题——门限问「样本够不够密到能下结论」，`expected_n` 问「该拿到的拿到了没有」。
# D-707 原文把两者当成同一个数，照做会把 ITL 那条 100 的密度门限换成 1–2，
# **废掉一条本来有效的门限，而且不报错**。
#
# **写成逐 KPI 的具名字段映射，不写成「密度型/计数型」二分**（D-740 §1）：
# 六族全都可推导，只是每族读相位的不同字段；二分会让人以为有一类推不出来。
EXPECTED_N_RULES = {
    # KPI: (相位类型, 取法, 理由)
    "N1": ("clock_sync", "sum:samples", "echo 样本 ＝ 各 clock_sync 相位 samples 之和"),
    "N2": ("clock_sync", "sum:samples", "同 N1，同一批 echo 样本"),
    "T1": ("token_stream", "count", "每个 token_stream 相位产出 1 个 TTFT"),
    "T2": ("token_stream", "sum:tokens-1", "ITL ＝ 相邻 token 之差 ⇒ 每相位 tokens−1 个间隔"),
    "T3": ("token_stream", "sum:tokens-1", "同 T2，同一条间隔序列"),
    "U1": ("upload_burst", "count", "每个 upload_burst 相位产出 1 个上行样本"),
    "D1": ("download_burst", "count", "每个 download_burst 相位产出 1 个下行样本"),
    "U2": ("tool_loop", "sum:rounds", "tool_loop 每 round 一个样本"),
}

# 🔴 **显名排除并写明理由**（D-740 §4／D-751）——不写出来，下一个人会顺手把 `expected_n`
# 推广到全部 KPI，**而那正是本轮差点发生的事**。
EXPECTED_N_EXCLUDED = {
    "S1": "样本单位是「遍/场景」而非相位；没有任何相位产出它，推导无来源",
    "C1": "由 ContinuityResultEntity 构造，该实体不带 profileId/phases，无从推导",
    "C2": "同 C1",
}

# ⚠ **T2/T3 的推导值是名义值**（D-746）：它假设无合并到达、无丢包。
# 实测与名义**几乎相等**（s1 599/599、s2 1021/1098、s3 397/398），故按**近似等值**理解；
# `actual < expected` 的差额是**合并信号，不是错误**。此处只登记语义，比对实测属判读侧。
EXPECTED_N_ITL_SEMANTICS = "actual < expected 记为合并信号，非错误（D-746）"


def derive_expected_n(profile):
    """从 phases 推导 {KPI: 期望样本数}；无来源相位的 KPI **不出现**在结果里（不记 0）。"""
    phases = profile.get("phases")
    if not isinstance(phases, list):
        return {}
    out = {}
    for kpi, (ptype, how, _why) in EXPECTED_N_RULES.items():
        hits = [p for p in phases if isinstance(p, dict) and p.get("type") == ptype]
        if not hits:
            continue          # 无该相位 ⇒ 这份 profile 不产出此 KPI；缺席 ≠ 期望 0
        if how == "count":
            out[kpi] = len(hits)
        elif how.startswith("sum:"):
            field = how.split(":", 1)[1]
            if field.endswith("-1"):
                base = field[:-2]
                out[kpi] = sum(int(p.get(base, 0)) - 1 for p in hits)
            else:
                out[kpi] = sum(int(p.get(field, 0)) for p in hits)
    return out


def check_expected_n(profile, name):
    """显式声明只作覆盖，且**必须与推导相等**（D-739 (a)）。-> [errors]

    不等即红，理由：手写声明是同一事实的第二份副本，**漂了不报错、只把完备性判歪**。
    **未声明是合法的**——推导本身就是事实源，声明只在需要覆盖时才写。
    """
    declared = profile.get("expected_n")
    if declared is None:
        return []
    if not isinstance(declared, dict):
        return [f"{name}: 'expected_n' must be an object"]
    derived = derive_expected_n(profile)
    errs = []
    for kpi, val in sorted(declared.items()):
        if kpi in EXPECTED_N_EXCLUDED:
            errs.append(f"{name}.expected_n: {kpi} 已显名排除"
                        f"（{EXPECTED_N_EXCLUDED[kpi]}），不得声明")
        elif kpi not in EXPECTED_N_RULES:
            errs.append(f"{name}.expected_n: 未知 KPI {kpi!r}（不在 EXPECTED_N_RULES 里）")
        elif kpi not in derived:
            errs.append(f"{name}.expected_n: {kpi} 在本 profile 无来源相位，推不出，不得声明")
        elif val != derived[kpi]:
            errs.append(f"{name}.expected_n: {kpi} 声明 {val} ≠ 推导 {derived[kpi]}"
                        f"（{EXPECTED_N_RULES[kpi][2]}）")
    return errs


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_dirs(spec_dir, runtime_dir):
    """Validate parity + structure across both trees. Returns [errors]."""
    errs = []
    spec_files = {f for f in os.listdir(spec_dir) if f.endswith(".json")} \
        if os.path.isdir(spec_dir) else set()
    runtime_files = {f for f in os.listdir(runtime_dir) if f.endswith(".json")} \
        if os.path.isdir(runtime_dir) else set()

    for name in sorted(spec_files - runtime_files):
        errs.append(f"{name}: in spec but missing from runtime (profiles/)")
    for name in sorted(runtime_files - spec_files):
        errs.append(f"{name}: in runtime but missing from spec (spec/profiles/server/)")

    for name in sorted(spec_files & runtime_files):
        try:
            spec_obj = _load(os.path.join(spec_dir, name))
        except (OSError, json.JSONDecodeError) as e:
            errs.append(f"spec/{name}: parse error: {e}")
            spec_obj = None
        try:
            rt_obj = _load(os.path.join(runtime_dir, name))
        except (OSError, json.JSONDecodeError) as e:
            errs.append(f"runtime/{name}: parse error: {e}")
            rt_obj = None
        if spec_obj is None or rt_obj is None:
            continue
        # (a) semantic parity — parsed equality ignores CRLF/whitespace/key order
        if spec_obj != rt_obj:
            errs.append(f"{name}: spec<->runtime content DIVERGES (semantic mismatch)")
        # (b) structure (validate the spec authority copy)
        errs.extend(check_structure(spec_obj, name))
    return errs


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB profile spec<->runtime + structure validator")
    ap.add_argument("--spec", default=DEFAULT_SPEC)
    ap.add_argument("--runtime", default=DEFAULT_RUNTIME)
    args = ap.parse_args(argv)

    if not os.path.isdir(args.spec) or not os.path.isdir(args.runtime):
        missing = [d for d in (args.spec, args.runtime) if not os.path.isdir(d)]
        print(f"profile tree(s) absent: {missing}", file=sys.stderr)
        return 2

    errors = validate_dirs(args.spec, args.runtime)
    if not errors:
        n = len([f for f in os.listdir(args.spec) if f.endswith(".json")])
        print(f"profiles OK: {n} profile(s) - spec<->runtime parity + phase structure hold")
        return 0
    print(f"profiles VIOLATIONS: {len(errors)}")
    for e in errors:
        print(f"  - {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
