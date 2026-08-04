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
