# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/validate_profiles.py.

Unit tests drive check_structure with synthetic profile dicts; parity tests write
spec/runtime copies to temp dirs; one integration test asserts the REAL profiles
pass (proving the validator agrees with the shipped, mirrored profiles).
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import validate_profiles as vp


def _valid_profile(pid="s1_chat"):
    return {
        "profile_id": pid, "version": "0.2.0", "kpi_set": "agent-qoe-kpi-v0.2",
        "phases": [
            {"type": "clock_sync", "samples": 20},
            {"type": "upload_burst", "bytes": 2048, "chunk_kb": 2},
            {"type": "token_stream", "tokens": 600, "rate_tps": 40,
             "token_bytes": {"dist": "lognormal", "median": 120}},
            {"type": "tool_loop", "rounds": 3, "up_bytes": 100, "down_bytes": 200,
             "server_proc_ms": 50},
            {"type": "clock_sync", "samples": 20},
        ],
    }


# ---------------------------------------------------------------- structure

def test_valid_profile_structure_ok():
    assert vp.check_structure(_valid_profile(), "s1") == []


def test_missing_top_field_fails():
    p = _valid_profile()
    del p["kpi_set"]
    assert any("missing 'kpi_set'" in e for e in vp.check_structure(p, "s1"))


def test_empty_phases_fails():
    p = _valid_profile()
    p["phases"] = []
    assert any("non-empty array" in e for e in vp.check_structure(p, "s1"))


def test_unknown_phase_type_fails():
    p = _valid_profile()
    p["phases"][0] = {"type": "warp_drive", "samples": 1}
    assert any("unknown phase type" in e for e in vp.check_structure(p, "s1"))


def test_phase_missing_required_field_fails():
    p = _valid_profile()
    p["phases"][1] = {"type": "upload_burst", "bytes": 2048}   # no chunk_kb
    assert any("missing 'chunk_kb'" in e for e in vp.check_structure(p, "s1"))


def test_phase_field_wrong_type_fails():
    p = _valid_profile()
    p["phases"][2]["rate_tps"] = "fast"                        # must be numeric
    assert any("rate_tps" in e for e in vp.check_structure(p, "s1"))


def test_token_bytes_must_be_map():
    p = _valid_profile()
    p["phases"][2]["token_bytes"] = 120                        # must be a mapping
    assert any("token_bytes" in e for e in vp.check_structure(p, "s1"))


def test_bool_is_not_numeric():
    p = _valid_profile()
    p["phases"][0]["samples"] = True                           # bool != int
    assert any("samples" in e for e in vp.check_structure(p, "s1"))


# ------------------------------------------ adaptive_*_window（T47 批②，D-468/D-469）

def _s4_throughput_profile():
    return {
        "profile_id": "s4_throughput", "version": "0.1.0", "kpi_set": "agent-qoe-kpi-v0.3",
        "phases": [
            {"type": "clock_sync", "samples": 20},
            {"type": "adaptive_download_window", "window_ms": 4000, "bytes": 536870912,
             "chunk_kb": 256},
            {"type": "adaptive_upload_window", "window_ms": 4000, "bytes": 50331648,
             "chunk_kb": 64},
            {"type": "clock_sync", "samples": 20},
        ],
    }


def test_adaptive_window_phases_structure_ok():
    """正例：两个新 phase 类型各自的必填字段齐全时应通过结构校验。"""
    assert vp.check_structure(_s4_throughput_profile(), "s4") == []


def test_adaptive_download_window_missing_window_ms_fails():
    """负例：adaptive_download_window 缺 window_ms 应被拒。"""
    p = _s4_throughput_profile()
    del p["phases"][1]["window_ms"]
    assert any("missing 'window_ms'" in e for e in vp.check_structure(p, "s4"))


def test_adaptive_upload_window_missing_window_ms_fails():
    """负例：adaptive_upload_window 缺 window_ms 应被拒（下行/上行各自独立钉住）。"""
    p = _s4_throughput_profile()
    del p["phases"][2]["window_ms"]
    assert any("missing 'window_ms'" in e for e in vp.check_structure(p, "s4"))


def test_adaptive_window_ms_wrong_type_fails():
    """负例：window_ms 必须是 int，字符串应被拒（同 test_phase_field_wrong_type_fails 纪律）。"""
    p = _s4_throughput_profile()
    p["phases"][1]["window_ms"] = "4000"
    assert any("window_ms" in e for e in vp.check_structure(p, "s4"))


# ---------------------------------------------------------------- parity

def _write(d, name, obj, *, crlf=False):
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    if crlf:
        text = text.replace("\n", "\r\n")
    with open(os.path.join(d, name), "w", encoding="utf-8", newline="") as f:
        f.write(text)


def test_parity_holds_across_crlf_difference():
    """CRLF vs LF must NOT be a divergence — semantic parity, not byte parity."""
    with tempfile.TemporaryDirectory() as spec, tempfile.TemporaryDirectory() as rt:
        _write(spec, "s1_chat.json", _valid_profile(), crlf=False)
        _write(rt, "s1_chat.json", _valid_profile(), crlf=True)   # CRLF only
        assert vp.validate_dirs(spec, rt) == []


def test_semantic_divergence_detected():
    with tempfile.TemporaryDirectory() as spec, tempfile.TemporaryDirectory() as rt:
        a = _valid_profile()
        b = _valid_profile()
        b["phases"][2]["tokens"] = 999                            # a real edit
        _write(spec, "s1_chat.json", a)
        _write(rt, "s1_chat.json", b)
        assert any("DIVERGES" in e for e in vp.validate_dirs(spec, rt))


def test_present_on_one_side_only_fails():
    with tempfile.TemporaryDirectory() as spec, tempfile.TemporaryDirectory() as rt:
        _write(spec, "s1_chat.json", _valid_profile())
        # runtime has none
        errs = vp.validate_dirs(spec, rt)
        assert any("missing from runtime" in e for e in errs)


def test_runtime_extra_profile_fails():
    with tempfile.TemporaryDirectory() as spec, tempfile.TemporaryDirectory() as rt:
        _write(rt, "s9_rogue.json", _valid_profile("s9_rogue"))
        errs = vp.validate_dirs(spec, rt)
        assert any("missing from spec" in e for e in errs)


# ---------------------------------------------------------------- integration

def test_real_profiles_pass():
    if not (os.path.isdir(vp.DEFAULT_SPEC) and os.path.isdir(vp.DEFAULT_RUNTIME)):
        return
    errs = vp.validate_dirs(vp.DEFAULT_SPEC, vp.DEFAULT_RUNTIME)
    assert errs == [], f"real profiles violate parity/structure: {errs}"


# ------------------------------------------------ expected_n（D-707／D-740／D-751）

def _profile(phases):
    return {"profile_id": "p", "version": "0.0.0", "kpi_set": "k", "phases": phases}


def test_expected_n_derives_per_kpi_from_the_right_field():
    """六族各读相位的**不同字段**——这正是 D-740 §1 要求写成具名映射而非二分的理由。"""
    p = _profile([
        {"type": "clock_sync", "samples": 20},
        {"type": "clock_sync", "samples": 20},
        {"type": "token_stream", "tokens": 300},
        {"type": "token_stream", "tokens": 300},
        {"type": "upload_burst", "bytes": 1, "chunk_kb": 1},
        {"type": "tool_loop", "rounds": 8, "up_bytes": 1, "down_bytes": 1,
         "server_proc_ms": 1},
    ])
    got = vp.derive_expected_n(p)
    assert got["N1"] == 40 and got["N2"] == 40, got     # sum:samples
    assert got["T1"] == 2, got                          # count
    assert got["T2"] == 598 and got["T3"] == 598, got   # sum:tokens-1
    assert got["U1"] == 1, got                          # count
    assert got["U2"] == 8, got                          # sum:rounds


def test_expected_n_omits_kpis_with_no_source_phase():
    """无来源相位 ⇒ **该 KPI 缺席**，不是期望 0。

    缺席说「这份 profile 不产出它」，0 说「该产出却一个都没有」——
    压成同一个值，下游就分不出「不适用」与「全丢了」。
    """
    got = vp.derive_expected_n(_profile([{"type": "clock_sync", "samples": 10}]))
    assert "D1" not in got and "U1" not in got and "T1" not in got, got
    assert got == {"N1": 10, "N2": 10}, got


def test_declared_expected_n_must_equal_derived():
    """声明只作覆盖，不等即红——手写是同一事实的第二份副本，**漂了不报错**。"""
    p = _profile([{"type": "upload_burst", "bytes": 1, "chunk_kb": 1}])
    p["expected_n"] = {"U1": 1}
    assert vp.check_expected_n(p, "p") == []            # 相等 ⇒ 放行（正对照）
    p["expected_n"] = {"U1": 3}
    errs = vp.check_expected_n(p, "p")
    assert any("U1" in e and "3" in e for e in errs), errs


def test_excluded_kpis_may_not_be_declared_and_the_reason_is_named():
    """S1／C1／C2 显名排除（D-751）；报错文案必须带上**为什么**。

    只报「不许声明」而不给理由，下一个人只会把它从清单里删掉——
    而理由（样本单位不是相位）才是它不该在这里的原因。
    """
    for kpi in ("S1", "C1", "C2"):
        p = _profile([{"type": "clock_sync", "samples": 10}])
        p["expected_n"] = {kpi: 3}
        errs = vp.check_expected_n(p, "p")
        assert errs and kpi in errs[0], (kpi, errs)
        assert vp.EXPECTED_N_EXCLUDED[kpi] in errs[0], (kpi, errs)


def test_real_profiles_derivation_matches_measured_corpus():
    """真实 profile 的推导值必须与**语料实测**对得上（承 D-746：s1 599／s3 397–398）。

    ⚠ 这条钉的是「规则没写反」，**不是「规则唯一正确」**——推导规则本身是单源的
    （由裁定给出、未经第二方独立推导），故只与**已实测过的那一族**比对。
    """
    if not os.path.isdir(vp.DEFAULT_RUNTIME):
        return
    got = {}
    for fn in sorted(os.listdir(vp.DEFAULT_RUNTIME)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(vp.DEFAULT_RUNTIME, fn), encoding="utf-8") as fh:
            prof = json.load(fh)
        got[prof.get("profile_id")] = vp.derive_expected_n(prof)
    assert got.get("s1_chat", {}).get("T2") == 599, got.get("s1_chat")
    assert got.get("s3_multimodal", {}).get("T2") == 398, got.get("s3_multimodal")
    # T1／U1／D1 三族对门限 3 **结构性不可达**（D-740 实测结论）——推导值全 < 3。
    for pid in ("s1_chat", "s2_coding_agent", "s3_multimodal"):
        for kpi in ("T1", "U1", "D1"):
            n = got.get(pid, {}).get(kpi)
            if n is not None:
                assert n < 3, (pid, kpi, n)
