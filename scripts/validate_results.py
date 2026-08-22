#!/usr/bin/env python3
"""ANEB result JSONL contract validator (stdlib only).

The analysis layer has no front door: campaign_common.load_records tolerates
anything and degrades on missing fields, so a malformed producer change reaches
the report as quietly wrong numbers. This is the gate that fails loudly instead.

Two layers of checking:

1. STRUCTURAL — the schema's own constraints, read live from
   spec/schemas/result-run.schema.json (required-field lists per object, the
   claim_scope const, the validity enum). No jsonschema dependency: the required
   arrays are read from the schema file so this can never drift out of sync with
   it, but the traversal is hand-rolled stdlib.

2. CROSS-FIELD (R-10) — invariants draft-07 cannot express, which are exactly the
   ones that make aggregates silently wrong if violated:
     * kpi value null  <=>  its <k>_grade null   (a graded null / an ungraded value)
     * aqs.score null  <=>  not_computable_reason present (a null with no reason,
                            or a reason attached to a real score)
     * itl_histogram: len(counts) == len(edges_ms) + 1   (open-ended bins, R-27)

Exit: 0 = all records valid / 1 = violations found / 2 = could not run
(schema unreadable, no records). Wires into verify_all as results-contract-unit.

Usage:
    python validate_results.py results/*.jsonl [--schema PATH] [--max-report N]
"""
import argparse
import json
import math
import os
import sys

import campaign_common as cc

DEFAULT_SCHEMA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "spec", "schemas", "result-run.schema.json")
# KPI ids whose value<->grade coupling we enforce (grade field = <prefix>_grade).
GRADED_KPIS = ("t1_ttft_ms", "t2_itl_p95_ms", "t3_stall_rate", "t4_severe_stall_rate",
               "n1_rtt_p50_ms", "n2_jitter_ms", "u1_goodput_mbps", "u2_tool_loop_p95_ms")


def load_schema(path):
    """Read the required-field lists + enums we enforce from the schema file, so
    this validator tracks the contract instead of hard-coding a second copy."""
    with open(path, encoding="utf-8") as f:
        schema = json.load(f)
    props = schema.get("properties", {})
    defs = schema.get("definitions", {})
    scenario = defs.get("scenario", {})
    scn_props = scenario.get("properties", {})
    run_schema = props.get("run", {})
    return {
        "top_required": schema.get("required", []),
        "claim_scope_const": props.get("claim_scope", {}).get("const"),
        "run_required": run_schema.get("required", []),
        "aqs_required": run_schema.get("properties", {}).get("aqs", {}).get("required", []),
        "scenario_required": scenario.get("required", []),
        "validity_enum": scn_props.get("validity", {}).get("enum", []),
        "kpi_required": scn_props.get("kpi", {}).get("required", []),
        "hist_required": scn_props.get("itl_histogram", {}).get("required", []),
        # 字段 -> JSON 类型声明。抽出来而不是在本文件手写一份，理由同上面那句
        # docstring：validator 要**跟踪**契约，不是再造第二份会各自漂移的副本
        # （D-315 同名实现纪律）。schema 里 46 个 kpi 字段全带 type 声明。
        "kpi_types": {k: v.get("type") for k, v in
                      scn_props.get("kpi", {}).get("properties", {}).items()
                      if v.get("type")},
        "run_types": {k: v.get("type") for k, v in
                      run_schema.get("properties", {}).items() if v.get("type")},
        # THERMAL 接线（D-556）：run.env 块内契约整块抽出（required/enum/minimum/
        # additionalProperties 全从 schema 读，不手写第二份——理由同上）。老 schema 无
        # env 键时为 {}，validate_record 侧整段跳过。
        "env_spec": run_schema.get("properties", {}).get("env", {}),
        # voice 摘要接线（大脑 08-22 裁定 voice 半）：同 env_spec 一字不差的提取逻辑。
        "voice_spec": run_schema.get("properties", {}).get("voice", {}),
        # aqs_v02/aqs_token（大脑 08-22 裁定，D-560 同族第三例）：并列出分块的
        # required/type 提取，enforcement 走 _check_block（提取逻辑与 env/voice 一字不差）。
        "aqs_v02_spec": run_schema.get("properties", {}).get("aqs_v02", {}),
        "aqs_token_spec": run_schema.get("properties", {}).get("aqs_token", {}),
    }


def _err(out, path, msg):
    out.append(("error", f"{path}: {msg}"))


def _warn(out, path, msg):
    out.append(("warn", f"{path}: {msg}"))


def _require(obj, keys, path, out):
    if not isinstance(obj, dict):
        _err(out, path, f"expected object, got {type(obj).__name__}")
        return False
    for k in keys:
        if k not in obj:
            _err(out, path, f"missing required field '{k}'")
    return True


def _is_null(v):
    return v is None


# JSON Schema 类型名 -> Python 类型。bool 必须特判：Python 里 isinstance(True, int)
# 为真，若不排除，一个布尔值会被当成合法 number/integer 放行。
_JSON_TYPES = {
    "number": (int, float),
    "integer": (int,),
    "string": (str,),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
}


def _type_ok(value, decl):
    """value 是否符合 schema 的 type 声明（decl 可为字符串或字符串列表）。"""
    names = decl if isinstance(decl, list) else [decl]
    if value is None:
        return "null" in names
    for nm in names:
        py = _JSON_TYPES.get(nm)
        if not py:
            continue
        if nm in ("number", "integer"):
            if isinstance(value, bool):
                continue
            if isinstance(value, py):
                return True
        elif isinstance(value, py):
            return True
    return False


def _check_types(obj, types, path, out):
    """逐字段核对类型；缺席不报（必填由 _require 管，选填缺席合法）。

    为什么必须有这一层：此前 _require 只查「键在不在」。把一个数值序列化成字符串
    （最常见的生产端回归形状之一）能**零 findings 通过契约门**，而下游 cc.fnum()
    对字符串返回 None —— 一个真实测到的数值就此被当作「没测到」，从每张热力卡、
    每个中位数里整批消失，且 value_problem 也不报（它只查数值范围不查类型）。
    实证：把 t1_ttft_ms 改成 "6.266667"，三道门全部放行。
    """
    if not isinstance(obj, dict):
        return
    for k, decl in types.items():
        if k not in obj:
            continue
        if not _type_ok(obj[k], decl):
            want = "|".join(decl) if isinstance(decl, list) else str(decl)
            _err(out, "%s.%s" % (path, k),
                 "type mismatch: expected %s, got %s (%.40r)"
                 % (want, type(obj[k]).__name__, obj[k]))


def _check_block(obj, spec, path, out):
    """按 schema 提取件（required/additionalProperties/type/enum/minimum）核一个嵌套块。

    判据全部从 spec（load_schema 的提取物，即契约本身）读出——不在本文件手写第二份
    （load_schema docstring 同理）。THERMAL（D-556）与 voice（大脑 08-22 裁定）两块共用：
    同一逻辑第二个消费方出现时立即抽共用，不留两份会各自漂移的副本（D-315）。
    块级 cross-field 不变量（如 env 的双键同 null）不在此处——那是各块自己的语义，留在调用点。
    """
    props = spec.get("properties", {})
    _require(obj, spec.get("required", []), path, out)
    if spec.get("additionalProperties") is False:
        unknown = sorted(set(obj) - set(props))
        if unknown:
            _err(out, path, f"unknown key(s) {unknown} (additionalProperties=false)")
    _check_types(obj, {k: v.get("type") for k, v in props.items() if v.get("type")},
                 path, out)
    for k, p in props.items():
        if k not in obj:
            continue
        v = obj[k]
        enum = p.get("enum")
        if enum and v not in enum:
            _err(out, f"{path}.{k}", f"not in enum: {v!r}")
        minimum = p.get("minimum")
        if (minimum is not None and isinstance(v, (int, float))
                and not isinstance(v, bool) and v < minimum):
            _err(out, f"{path}.{k}", f"must be >= {minimum}, got {v!r}")


def validate_record(rec, sch, idx):
    """Return a list of (severity, message) findings for one record.

    severity 'error' fails the gate (exit 1); 'warn' is advisory (exit 0) — used
    for known schema/producer drift that is not the data's fault to fix.
    """
    f = []
    tag = f"record[{idx}]"
    if not isinstance(rec, dict):
        return [("error", f"{tag}: not a JSON object")]

    _require(rec, sch["top_required"], tag, f)
    if sch["claim_scope_const"] is not None and "claim_scope" in rec:
        if rec.get("claim_scope") != sch["claim_scope_const"]:
            _err(f, f"{tag}.claim_scope",
                 f"must be '{sch['claim_scope_const']}', got {rec.get('claim_scope')!r}")

    run = rec.get("run")
    if isinstance(run, dict):
        _require(run, sch["run_required"], f"{tag}.run", f)
        _check_types(run, sch.get("run_types") or {}, f"{tag}.run", f)
        aqs = run.get("aqs")
        if isinstance(aqs, dict):
            _require(aqs, sch["aqs_required"], f"{tag}.run.aqs", f)
            # R-10: score null <=> a reason is present.
            score_null = _is_null(aqs.get("score"))
            reason = aqs.get("not_computable_reason")
            has_reason = isinstance(reason, str) and reason.strip() != ""
            if score_null and not has_reason:
                _err(f, f"{tag}.run.aqs", "score is null but not_computable_reason is empty (R-10)")
            if not score_null and has_reason:
                _err(f, f"{tag}.run.aqs", f"score present ({aqs.get('score')}) yet "
                     f"not_computable_reason set ({reason!r}) — contradictory")
        # THERMAL 接线（D-556）：run.env 块内不变量。本门是手写结构检查，schema 的
        # enum/required/minimum 不会自动生效——不在这里显式接线，非法枚举照样过门
        # （接线前实测 "toasty" 零 findings 通过）。D-305 同形状：schema 会写、生产端
        # 会发，唯独门最容易没学会新块。判据全从 env_spec（即 schema）派生。
        env = run.get("env")
        env_spec = sch.get("env_spec") or {}
        if isinstance(env, dict) and env_spec:
            _check_block(env, env_spec, f"{tag}.run.env", f)
            st = env.get("thermal_max_status")
            cnt = env.get("thermal_polluting_event_count")
            # R-10：双键同 null 同非 null——双 null=无监控、"none"+0=在位且干净，混搭
            # 无语义。这是 draft-07 写不出的 cross-field 不变量，正是本门第 2 层的职责。
            if ("thermal_max_status" in env and "thermal_polluting_event_count" in env
                    and (st is None) != (cnt is None)):
                _err(f, f"{tag}.run.env",
                     f"null-ness mismatch: status={st!r} count={cnt!r} (双键同进退, R-10)")
        # voice 摘要（大脑 08-22 裁定 voice 半）：块内契约同走 _check_block（判据从
        # voice_spec 即 schema 派生）。无块级 cross-field——六键各自独立可空是实体语义
        # （v1 行 caliber/turns_ok/proxy 恒 null 而 low_confidence 恒 false），不造假不变量
        # （D-337「这种情况下正确的动作是不加守卫」）。
        voice = run.get("voice")
        voice_spec = sch.get("voice_spec") or {}
        if isinstance(voice, dict) and voice_spec:
            _check_block(voice, voice_spec, f"{tag}.run.voice", f)
        # aqs_v02 / aqs_token（大脑 08-22 裁定：同族同待遇——D-560 家族第三例）：schema
        # 声明了 required/type 而门此前一条不管（接线前合成案实测「aqs_v02 缺 score」零
        # findings 过门）。「生产端单一来源」是缓释不是豁免——合同门防的正是未来第二生产者
        # 与损坏语料。additionalProperties 非 false 故无未知键检查；score↔reason 的 R-10
        # cross-field 仅主 aqs 有裁定与测试，两并列块不在本单擅自外推（D-337）。
        for blk_key, spec_key in (("aqs_v02", "aqs_v02_spec"), ("aqs_token", "aqs_token_spec")):
            blk = run.get(blk_key)
            blk_spec = sch.get(spec_key) or {}
            if isinstance(blk, dict) and blk_spec:
                _check_block(blk, blk_spec, f"{tag}.run.{blk_key}", f)
    elif "run" in rec:
        _err(f, f"{tag}.run", "expected object")

    scns = rec.get("scenarios")
    if isinstance(scns, list):
        for si, scn in enumerate(scns):
            f.extend(validate_scenario(scn, sch, f"{tag}.scenarios[{si}]"))
    elif "scenarios" in rec:
        _err(f, f"{tag}.scenarios", "expected array")
    return f


def validate_scenario(scn, sch, path):
    f = []
    if not _require(scn, sch["scenario_required"], path, f):
        return f

    validity = scn.get("validity")
    enum = sch["validity_enum"]
    if enum:
        # The three STATES are the contract; the schema enum is upper-case but the
        # producer (ResultReporter) emits lower-case — a known schema/producer
        # drift (see campaign_common.scenario_validity). Compare case-insensitively
        # so real data passes; surface the casing mismatch as a non-fatal advisory
        # for the schema owner, and fail only a genuinely unknown state.
        low = {e.lower() for e in enum}
        got = validity.lower() if isinstance(validity, str) else validity
        if got not in low:
            _err(f, f"{path}.validity", f"'{validity}' not in {enum} (case-insensitive)")
        elif isinstance(validity, str) and validity not in enum:
            _warn(f, f"{path}.validity",
                  f"'{validity}' matches a valid state only by case-fold; schema enum "
                  f"is {enum} — schema/producer case drift")

    kpi = scn.get("kpi")
    if isinstance(kpi, dict):
        _require(kpi, sch["kpi_required"], f"{path}.kpi", f)
        _check_types(kpi, sch.get("kpi_types") or {}, f"{path}.kpi", f)
        # R-10: value null <=> grade null (no graded nulls, no ungraded values).
        for k in GRADED_KPIS:
            if k not in kpi:
                continue
            gfield = k.split("_")[0] + "_grade"
            if gfield not in kpi:
                continue
            if _is_null(kpi.get(k)) != _is_null(kpi.get(gfield)):
                _err(f, f"{path}.kpi", f"{k}={kpi.get(k)!r} but {gfield}="
                     f"{kpi.get(gfield)!r} (value/grade nullness must match, R-10)")
    elif "kpi" in scn:
        _err(f, f"{path}.kpi", "expected object")

    hist = scn.get("itl_histogram")
    if isinstance(hist, dict):
        _require(hist, sch["hist_required"], f"{path}.itl_histogram", f)
        edges, counts = hist.get("edges_ms"), hist.get("counts")
        if isinstance(edges, list) and isinstance(counts, list):
            if len(counts) != len(edges) + 1:
                _err(f, f"{path}.itl_histogram", f"len(counts)={len(counts)} must equal "
                     f"len(edges_ms)+1={len(edges) + 1} (open-ended bins, R-27)")
    elif "itl_histogram" in scn:
        _err(f, f"{path}.itl_histogram", "expected object")
    return f


def _nonfinite_paths(node, path="", out=None):
    """Every NaN/±Infinity leaf, with its dotted path.

    JSON has no such literals, but Python's json module emits and accepts the
    bare words by default, so a producer or a converting tool can put them in a
    corpus. The aggregates now refuse them (D-148), which keeps the numbers
    honest — but "silently not computable" is not the same as telling the
    operator the corpus is broken, so the gate names them.
    """
    out = [] if out is None else out
    if isinstance(node, dict):
        for k, v in node.items():
            _nonfinite_paths(v, f"{path}.{k}" if path else str(k), out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _nonfinite_paths(v, f"{path}[{i}]", out)
    elif isinstance(node, float) and not math.isfinite(node):
        out.append(f"{path}={node}")
    return out


def validate_records(records, sch):
    """Return (errors, warnings) as two lists of message strings."""
    findings = []
    for i, rec in enumerate(records):
        findings.extend(validate_record(rec, sch, i))
        bad = _nonfinite_paths(rec)
        if bad:
            findings.append(("error", f"record[{i}]: 非法数值（JSON 不允许 NaN/Infinity）"
                                      f"：{', '.join(bad[:5])}"
                                      + (f" 等共 {len(bad)} 处" if len(bad) > 5 else "")))
    errors = [m for sev, m in findings if sev == "error"]
    warnings = [m for sev, m in findings if sev == "warn"]
    return errors, warnings


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB result JSONL contract validator")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--schema", default=DEFAULT_SCHEMA)
    ap.add_argument("--max-report", type=int, default=50, help="max violations to print")
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    try:
        sch = load_schema(args.schema)
    except (OSError, json.JSONDecodeError) as e:
        print(f"cannot read schema {args.schema}: {e}", file=sys.stderr)
        return 2

    recs, files = cc.load_records(args.inputs)
    if not recs:
        print("no records loaded", file=sys.stderr)
        return 2

    errors, warnings = validate_records(recs, sch)

    # De-duplicate advisories (e.g. the same schema case-drift on every scenario).
    seen, uniq_warn = set(), []
    for w in warnings:
        key = w.split(":", 1)[-1].strip()
        if key not in seen:
            seen.add(key)
            uniq_warn.append(w)
    if uniq_warn:
        print(f"advisories (non-fatal, {len(warnings)} occurrence(s), "
              f"{len(uniq_warn)} distinct):")
        for line in uniq_warn[:args.max_report]:
            print(f"  ~ {line}")

    if not errors:
        print(f"contract OK: {len(recs)} record(s) across {len(files)} file(s) — "
              "structural + R-10 cross-field invariants hold")
        return 0
    print(f"contract VIOLATIONS: {len(errors)} in {len(recs)} record(s)")
    for line in errors[:args.max_report]:
        print(f"  - {line}")
    if len(errors) > args.max_report:
        print(f"  … and {len(errors) - args.max_report} more")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
