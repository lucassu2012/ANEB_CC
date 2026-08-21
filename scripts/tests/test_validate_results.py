# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/validate_results.py.

A schema-complete valid record is built in-test, then each test breaks exactly
one thing and asserts the corresponding error — with special attention to the
R-10 cross-field invariants draft-07 cannot express, and to the known
schema/producer validity CASE drift being an advisory, not a gate failure.
"""
import copy
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import validate_results as vd

SCH = vd.load_schema(vd.DEFAULT_SCHEMA)


def _valid_kpi():
    kpi = {"seq_gap_count": 0, "seq_dup_count": 0}
    for k in ("t1_ttft_ms", "t2_itl_p95_ms", "t3_stall_rate", "t4_severe_stall_rate",
              "n1_rtt_p50_ms", "n2_jitter_ms", "u1_goodput_mbps", "u2_tool_loop_p95_ms"):
        kpi[k] = 10.0
        kpi[k.split("_")[0] + "_grade"] = "good"
    return kpi


def _valid_record():
    """A fully schema-complete, R-10-consistent record (validity UPPER = no advisory)."""
    return {
        "claim_scope": "application_end_to_end_to_probe_node",
        "kpi_set": "agent-qoe-kpi-v0.1", "aqs_version": "aqs-v0.1",
        "profile_versions": "s1@0.2", "schema_version": "1.0",
        "run": {
            "run_id": "0198a7b0-0000-7000-8000-000000000001",
            "started_at_epoch_ms": 1783944000000, "mode": "quick", "scenario_order": "s1",
            "transport": "cellular", "profile_source": "server", "app_version_name": "1.0",
            "app_version_code": 1, "guard_metadata": None, "status": "completed",
            "aqs": {"score": 90.0, "low_confidence": False, "veto_applied": False,
                    "not_computable_reason": None, "input_mapping": "m", "sub_scores": {}},
            # THERMAL 接线（D-556）：接线后的生产端每条 run 恒带 env 块（TestEngine 恒传
            # fold 结果）——夹具跟上今天的生产者形状；块缺席=老语料，另有专测钉其合法。
            "env": {"thermal_max_status": "none", "thermal_polluting_event_count": 0},
            # voice 摘要（大脑 08-22 裁定 voice 半）：24h 窗内有 Done 行时生产端带 voice 块。
            # 夹具取 v2 口径全值行；v1 形状（caliber/turns_ok/proxy 恒 null）另有专测钉其合法。
            "voice": {"caliber": "server-sim-v2", "m7_max_frame_gap_ms": 180.5,
                      "mouth_ear_proxy_p50_ms": 412.0, "low_confidence": False,
                      "turns_ok": 12, "ts_epoch_ms": 1783943000000},
        },
        "scenarios": [{
            "profile_id": "s1_chat", "profile_version": "0.2", "repeat_index": 0,
            "order_index": 0, "validity": "valid", "invalid_reasons": "",
            "kpi": _valid_kpi(),
            "clock": {"offset_start_us": 1, "offset_end_us": 2, "drift_ppm": 0.0,
                      "offset_suspect": False},
            "network_snapshot": {"transport": "cellular", "capabilities": "c",
                                 "interface": "rmnet0", "server_observed_addr": "1.2.3.4:5"},
            "parse": {"parse_dur_us": 10, "per_event_parse_us": 1.0},
            "buffering": {"score": None, "attribution": None, "sample_count": None},
            "itl_histogram": {"buckets_version": "v1", "edges_ms": [10, 20, 50],
                              "counts": [1, 2, 3, 4], "total": 10},
        }],
    }


def _errors(rec):
    return vd.validate_records([rec], SCH)[0]


def _warnings(rec):
    return vd.validate_records([rec], SCH)[1]


# ---------------------------------------------------------------- happy path

def test_valid_record_has_no_errors():
    assert _errors(_valid_record()) == []
    assert _warnings(_valid_record()) == []


# ---------------------------------------------------------------- structural

def test_missing_top_required_field():
    rec = _valid_record()
    del rec["kpi_set"]
    assert any("missing required field 'kpi_set'" in e for e in _errors(rec))


def test_claim_scope_const_enforced():
    rec = _valid_record()
    rec["claim_scope"] = "radio_layer_mos"
    assert any("claim_scope" in e for e in _errors(rec))


def test_missing_run_required_field():
    rec = _valid_record()
    del rec["run"]["scenario_order"]
    assert any("run: missing required field 'scenario_order'" in e for e in _errors(rec))


def test_missing_scenario_required_field():
    rec = _valid_record()
    del rec["scenarios"][0]["order_index"]
    assert any("order_index" in e for e in _errors(rec))


def test_unknown_validity_state_fails():
    rec = _valid_record()
    rec["scenarios"][0]["validity"] = "MAYBE"
    assert any("validity" in e for e in _errors(rec))


# ---------------------------------------------------------------- case drift

def test_lowercase_validity_is_the_exact_match_now():
    """D-371 aligned the schema to the producer's lower-case (every real corpus
    is lower-case; the upper-case enum was the aspirational copy, D-190). The
    authoritative spelling must pass with NO advisory — a warning that fires on
    every honest record teaches the operator to ignore warnings."""
    rec = _valid_record()
    rec["scenarios"][0]["validity"] = "valid_low_confidence"
    assert _errors(rec) == []
    assert _warnings(rec) == []


def test_uppercase_validity_is_advisory_not_error():
    """The drift direction inverted with D-371: legacy upper-case (old fixtures,
    pre-alignment tools) now matches only by case-fold — advisory, not a
    rejection (the record still carries a usable measurement)."""
    rec = _valid_record()
    rec["scenarios"][0]["validity"] = "VALID_LOW_CONFIDENCE"
    assert _errors(rec) == []
    assert any("case drift" in w for w in _warnings(rec))


# ---------------------------------------------------------------- R-10 cross-field

def test_aqs_null_score_needs_reason():
    rec = _valid_record()
    rec["run"]["aqs"]["score"] = None          # reason still None -> violation
    assert any("not_computable_reason is empty" in e for e in _errors(rec))


def test_aqs_null_score_with_reason_ok():
    rec = _valid_record()
    rec["run"]["aqs"]["score"] = None
    rec["run"]["aqs"]["not_computable_reason"] = "KPI_MISSING:D1"
    assert _errors(rec) == []


def test_aqs_score_with_reason_is_contradictory():
    rec = _valid_record()
    rec["run"]["aqs"]["not_computable_reason"] = "KPI_MISSING:D1"   # score still 90
    assert any("contradictory" in e for e in _errors(rec))


def test_kpi_value_without_grade_fails():
    rec = _valid_record()
    rec["scenarios"][0]["kpi"]["n1_grade"] = None    # value present, grade null
    assert any("value/grade nullness" in e for e in _errors(rec))


def test_kpi_null_value_with_grade_fails():
    rec = _valid_record()
    rec["scenarios"][0]["kpi"]["n1_rtt_p50_ms"] = None   # grade still 'good'
    assert any("value/grade nullness" in e for e in _errors(rec))


def test_kpi_both_null_ok():
    rec = _valid_record()
    rec["scenarios"][0]["kpi"]["n1_rtt_p50_ms"] = None
    rec["scenarios"][0]["kpi"]["n1_grade"] = None
    assert _errors(rec) == []


def test_histogram_counts_length_invariant():
    rec = _valid_record()
    rec["scenarios"][0]["itl_histogram"]["counts"] = [1, 2, 3]   # need len(edges)+1 = 4
    assert any("open-ended bins" in e for e in _errors(rec))


# ---------------------------------------------------------------- CLI

def test_cli_valid_and_invalid():
    with tempfile.TemporaryDirectory() as d:
        good = os.path.join(d, "good.jsonl")
        bad = os.path.join(d, "bad.jsonl")
        with open(good, "w", encoding="utf-8") as f:
            f.write(json.dumps(_valid_record()) + "\n")
        broken = copy.deepcopy(_valid_record())
        broken["claim_scope"] = "wrong"
        with open(bad, "w", encoding="utf-8") as f:
            f.write(json.dumps(broken) + "\n")
        assert vd.main([good]) == 0
        assert vd.main([bad]) == 1


def test_cli_missing_schema_returns_2():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "x.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps(_valid_record()) + "\n")
        assert vd.main([p, "--schema", os.path.join(d, "nope.json")]) == 2


def test_non_finite_numbers_are_contract_errors():
    """The aggregates refuse NaN so the numbers stay honest, but "silently not
    computable" is not the same as telling the operator the corpus is broken."""
    from synth import contractify, kpi_scenario_records
    recs = [contractify(r) for r in kpi_scenario_records(2, kpi={"n1_rtt_p50_ms": 20})]
    recs[0]["scenarios"][0]["kpi"]["n1_rtt_p50_ms"] = float("nan")
    errors, _ = vd.validate_records(recs, SCH)
    hits = [e for e in errors if "NaN/Infinity" in e]
    assert len(hits) == 1
    assert "n1_rtt_p50_ms" in hits[0]
    clean, _ = vd.validate_records(
        [contractify(r) for r in kpi_scenario_records(2, kpi={"n1_rtt_p50_ms": 20})],
        SCH)
    assert not [e for e in clean if "NaN/Infinity" in e]


# ------------------------------------------------- the schema is the contract

def _dig(node, *path):
    for step in path:
        node = node[step]
    return node


# Where each rule load_schema() extracts lives in the JSON, and how to break it
# there. Keyed by the names load_schema returns, so a rule added to the extractor
# without an entry here fails the test instead of sliding in unchecked (D-234).
_SCHEMA_SITE = {
    "top_required":
        lambda s: _dig(s, "required").append("zzz_not_a_field"),
    "claim_scope_const":
        lambda s: _dig(s, "properties", "claim_scope").__setitem__("const", "zzz"),
    "run_required":
        lambda s: _dig(s, "properties", "run", "required").append("zzz_not_a_field"),
    "aqs_required":
        lambda s: _dig(s, "properties", "run", "properties", "aqs",
                       "required").append("zzz_not_a_field"),
    "scenario_required":
        lambda s: _dig(s, "definitions", "scenario", "required").append("zzz_not_a_field"),
    "validity_enum":
        lambda s: _dig(s, "definitions", "scenario", "properties",
                       "validity").__setitem__("enum", ["ZZZ_ONLY"]),
    "kpi_required":
        lambda s: _dig(s, "definitions", "scenario", "properties", "kpi",
                       "required").append("zzz_not_a_field"),
    # T72 新增的两条规则各配一个篡改点：把某个字段的 type 声明改成一个记录里
    # 绝不可能是的类型，则原本干净的记录必须变脏——证明 load_schema 抽的 type
    # 真的在被 validator 使用，而不是它自己硬编码了一份。
    "kpi_types":
        lambda s: _dig(s, "definitions", "scenario", "properties", "kpi",
                       "properties", "t1_ttft_ms").__setitem__("type", ["string"]),
    "run_types":
        lambda s: _dig(s, "properties", "run", "properties",
                       "run_id").__setitem__("type", ["number"]),
    "env_spec":
        lambda s: _dig(s, "properties", "run", "properties", "env", "properties",
                       "thermal_max_status").__setitem__("enum", ["ZZZ_ONLY"]),
    "voice_spec":
        lambda s: _dig(s, "properties", "run", "properties", "voice", "properties",
                       "ts_epoch_ms").__setitem__("type", ["string"]),
    "hist_required":
        lambda s: _dig(s, "definitions", "scenario", "properties", "itl_histogram",
                       "required").append("zzz_not_a_field"),
}


def test_every_rule_this_validator_enforces_is_read_from_the_schema():
    """`load_schema` promises the validator 「tracks the contract instead of
    hard-coding a second copy」, and nothing checked it: every test in this file
    loads the real schema, so a validator that opened the file and then enforced
    its own hard-coded copy would pass all of them (D-234).

    Two halves per rule, because either can drift on its own: doctoring the JSON
    must change what load_schema extracts, and the doctored rule must change the
    verdict on a record that was clean a moment ago.
    """
    with open(vd.DEFAULT_SCHEMA, encoding="utf-8") as fh:
        raw = json.load(fh)
    assert set(SCH) == set(_SCHEMA_SITE), (
        f"rules with no doctor: {sorted(set(SCH) - set(_SCHEMA_SITE))}; "
        f"doctors for rules that are gone: {sorted(set(_SCHEMA_SITE) - set(SCH))}")
    assert _errors(_valid_record()) == [], "the fixture has to start clean"

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "doctored.schema.json")
        for rule, break_it in _SCHEMA_SITE.items():
            doctored = copy.deepcopy(raw)
            break_it(doctored)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(doctored, fh)
            reloaded = vd.load_schema(path)
            assert reloaded[rule] != SCH[rule], (
                f"{rule}: the schema file changed and load_schema returned the "
                "same thing — this rule is not being read from the contract")
            errors, _ = vd.validate_records([_valid_record()], reloaded)
            assert errors, (
                f"{rule}: the rule changed and a record that now violates it "
                "still passed — the verdict is not using what was read")


# ---- 类型校验（T72，承 T67/D-514 high#4）----
# 缺口实证：把 t1_ttft_ms 从 6.266667 改成字符串 "6.266667"，契约门此前返回
# **0 条 findings** 放行；而下游 cc.fnum('6.266667') 返回 None，于是一个真实测到
# 的数值被当成「没测到」，从每张热力卡、每个中位数里整批消失，cc.value_problem
# 也不报（它只查数值范围不查类型）。三道门全部沉默。

def test_type_mismatch_number_serialised_as_string_is_an_error():
    """数值被序列化成字符串必须报 error（最常见的生产端回归形状之一）。"""
    rec = _valid_record()
    rec["scenarios"][0]["kpi"]["t1_ttft_ms"] = "6.266667"
    errs = _errors(rec)
    assert any("type mismatch" in m and "t1_ttft_ms" in m for m in errs), errs


def test_type_check_accepts_null_because_null_is_in_the_declaration():
    """反例方向：null 是契约允许的（R-10「测不出就是 null」），不得误报。"""
    rec = _valid_record()
    rec["scenarios"][0]["kpi"]["t1_ttft_ms"] = None
    rec["scenarios"][0]["kpi"]["t1_grade"] = None   # R-10 交叉不变量：值 null <=> 档 null
    errs = _errors(rec)
    assert not any("type mismatch" in m for m in errs), errs


def test_boolean_does_not_pass_as_a_number():
    """Python 里 isinstance(True, int) 为真——若不特判，布尔会冒充合法 number。"""
    assert vd._type_ok(True, ["number", "null"]) is False
    assert vd._type_ok(True, ["boolean"]) is True
    assert vd._type_ok(1, ["integer"]) is True
    assert vd._type_ok("6.2", ["number", "null"]) is False


def test_type_check_ignores_absent_fields_required_is_a_separate_job():
    """缺席不由类型校验管（必填由 _require 管，选填缺席合法）——避免双重报错。"""
    out = []
    vd._check_types({}, {"t1_ttft_ms": ["number", "null"]}, "x", out)
    assert out == []


# ---- run.env（THERMAL 接线，D-556）----
# 缺口实证：schema 先行加了 env 块之后，本门对 thermal_max_status="toasty" 返回
# 0 条 findings 放行——手写结构门不吃 schema 的 enum/required/minimum，每条都要在
# validate_record 里显式接线（D-305 同形状：schema 会写、生产端会发，唯独门最容易
# 没学会新块）。判据全从 env_spec（即 schema）派生，doctor 见 _SCHEMA_SITE。

def test_env_block_absent_is_legal_old_corpus():
    """块缺席=该 run 早于字段上线（R-10：缺失≠空）——老语料照常过。"""
    rec = _valid_record()
    del rec["run"]["env"]
    assert _errors(rec) == []


def test_env_double_null_is_legal_unmonitored():
    """双 null=本 run 无热监控（PowerManager 不可用/监听注册失败）——合法且自证。"""
    rec = _valid_record()
    rec["run"]["env"] = {"thermal_max_status": None, "thermal_polluting_event_count": None}
    assert _errors(rec) == []


def test_env_bad_enum_rejected():
    rec = _valid_record()
    rec["run"]["env"]["thermal_max_status"] = "toasty"
    assert any("thermal_max_status" in e and "enum" in e for e in _errors(rec))


def test_env_missing_key_rejected():
    """块内两键恒在（schema required）——只发一半的生产端要当场咬。"""
    rec = _valid_record()
    del rec["run"]["env"]["thermal_polluting_event_count"]
    assert any("missing required field 'thermal_polluting_event_count'" in e
               for e in _errors(rec))


def test_env_extra_key_rejected():
    """additionalProperties=false：未声明键混进块里=生产端在发没契约的东西。"""
    rec = _valid_record()
    rec["run"]["env"]["oops"] = 1
    assert any("unknown key" in e for e in _errors(rec))


def test_env_negative_count_rejected():
    rec = _valid_record()
    rec["run"]["env"]["thermal_polluting_event_count"] = -1
    assert any("thermal_polluting_event_count" in e and ">= 0" in e for e in _errors(rec))


def test_env_null_mix_rejected():
    """R-10 cross-field：双键同 null 同非 null——status=null 而 count=0 的混搭无语义
    （null=无监控、0=在位且干净，一半说没监控一半说监控到了）。draft-07 写不出这条，
    正是本门第 2 层的职责。"""
    rec = _valid_record()
    rec["run"]["env"]["thermal_max_status"] = None
    errs = _errors(rec)
    assert any("null-ness mismatch" in e for e in errs), errs


def test_env_count_as_string_rejected():
    """数值序列化成字符串（T72 t1_ttft_ms 同形状的生产端回归）在 env 块里也要咬。"""
    rec = _valid_record()
    rec["run"]["env"]["thermal_polluting_event_count"] = "0"
    assert any("type mismatch" in e and "thermal_polluting_event_count" in e
               for e in _errors(rec))


# ---- run.voice（大脑 08-22 裁定 voice 半）----
# 判据全从 voice_spec（即 schema）派生，经通用 _check_block（与 env 共用，D-315 抽共用）。
# 六键无块级 cross-field——各自独立可空是 voice_result 实体语义（v1 行多键恒 null），
# 不造假不变量（D-337）。voice_spec 的 doctor 见 _SCHEMA_SITE。

def test_voice_block_absent_is_legal_old_corpus():
    """块缺席=窗内无 Done 行或 run 早于上线（R-10：缺失≠空）——老语料照常过。"""
    rec = _valid_record()
    del rec["run"]["voice"]
    assert _errors(rec) == []


def test_voice_v1_shape_is_legal():
    """v1 paced-proxy 行：caliber/m7/proxy/turns_ok 恒 null、low_confidence 恒 false——
    全部是实体写明的合法状态，六键恒在值可空。"""
    rec = _valid_record()
    rec["run"]["voice"] = {"caliber": None, "m7_max_frame_gap_ms": None,
                           "mouth_ear_proxy_p50_ms": None, "low_confidence": False,
                           "turns_ok": None, "ts_epoch_ms": 1783943000000}
    assert _errors(rec) == []


def test_voice_missing_ts_rejected():
    """溯源键 ts_epoch_ms 是块内 required——没有它跨纪元无从对账（D-513）。"""
    rec = _valid_record()
    del rec["run"]["voice"]["ts_epoch_ms"]
    assert any("missing required field 'ts_epoch_ms'" in e for e in _errors(rec))


def test_voice_null_ts_rejected():
    """ts_epoch_ms 类型 integer 不含 null——被挂接的行必然有落库时刻。"""
    rec = _valid_record()
    rec["run"]["voice"]["ts_epoch_ms"] = None
    assert any("type mismatch" in e and "ts_epoch_ms" in e for e in _errors(rec))


def test_voice_extra_key_rejected():
    """additionalProperties=false：v3 普查定的最小集之外的列上 wire=D-276 反模式复活。"""
    rec = _valid_record()
    rec["run"]["voice"]["rtt_ms"] = 42.0
    assert any("unknown key" in e for e in _errors(rec))


def test_voice_m7_as_string_rejected():
    """数值序列化成字符串（T72 同形状）在 voice 块也要咬。"""
    rec = _valid_record()
    rec["run"]["voice"]["m7_max_frame_gap_ms"] = "180.5"
    assert any("type mismatch" in e and "m7_max_frame_gap_ms" in e for e in _errors(rec))


def test_voice_negative_turns_rejected():
    rec = _valid_record()
    rec["run"]["voice"]["turns_ok"] = -1
    assert any("turns_ok" in e and ">= 0" in e for e in _errors(rec))
