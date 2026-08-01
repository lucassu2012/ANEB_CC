#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_adapters.py 的反例（T11 ③）。

守卫"能不能失败"要造反例证明，不能推理（D-322）。本文件对每一条不变量各造一个
会踩中它的输入，并额外钉住两件事：

  * **今天**把 `validated_against_version` 写进 JSON 会被拦下——因为 DTO 还没有它，
    而 App 用严格解析（这正是 T11 ① 被阻塞的机器可判证据，不是我的判断）；
  * **明天** v2 给 DTO 加上该字段后，同一个门自动放行——判据与消费方同源，
    不需要有人记得回来改这份守卫。

exit 0 = 全过 / 1 = 有失败。
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import validate_adapters as va  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(HERE))

# 真实 DTO 派生结果——反例要跑在真的键集上，不是我编的键集。
with open(va.KOTLIN_DTO, encoding="utf-8") as _fh:
    REAL_DTOS = va.parse_dtos(_fh.read())

with open(os.path.join(HERE, "doubao.json"), encoding="utf-8") as _fh:
    GOOD = json.load(_fh)


def _codes(violations):
    """['[x] A1: ...'] -> {'A1', ...}，只比规则号，不比措辞。"""
    out = set()
    for item in violations:
        tail = item.split("] ", 1)[-1]
        out.add(tail.split(":", 1)[0].strip())
    return out


# ── A1：未知键（今天这个任务差点造成的那个事故） ──────────────────────────────

def test_the_real_specs_are_clean():
    assert va.check_one("doubao.json", GOOD, REAL_DTOS) == []


def test_an_unknown_key_is_caught_not_shrugged_off():
    d = copy.deepcopy(GOOD)
    d["adapter"]["some_new_field"] = "x"
    assert "A1" in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_unknown_key_in_a_nested_object_is_caught_too():
    d = copy.deepcopy(GOOD)
    d["adapter"]["input_node"]["extra"] = 1
    assert "A1" in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_unknown_key_inside_kpi_mapping_entry_is_caught():
    d = copy.deepcopy(GOOD)
    first = sorted(d["adapter"]["kpi_mapping"])[0]
    d["adapter"]["kpi_mapping"][first]["note"] = "x"
    assert "A1" in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_validated_against_version_is_rejected_today():
    """T11 ① 被阻塞的机器可判证据。

    DTO 目前没有这个字段，App 又是严格解析——所以今天把它写进 JSON，
    设备上的后果是解析抛异常 → fail-safe 空列表 → 全部降级 generic →
    adapter_obs 停止入库，而且**没有任何一处会报错**。门必须替我们拦住。
    """
    d = copy.deepcopy(GOOD)
    d["adapter"]["validated_against_version"] = {
        "version_name": "1.2.3", "version_code": 1203,
        "captured_at": "2026-08-02", "source": "dumpsys package com.larus.nova",
    }
    assert "A1" in _codes(va.check_one("doubao.json", d, REAL_DTOS))
    assert "validated_against_version" not in REAL_DTOS[va.DTO_OF_ADAPTER][0]


def test_the_same_field_passes_once_the_dto_declares_it():
    """明天 v2 给 DTO 加上字段后，同一个门自动放行——不需要有人回来改守卫。"""
    allowed, required = REAL_DTOS[va.DTO_OF_ADAPTER]
    future = dict(REAL_DTOS)
    future[va.DTO_OF_ADAPTER] = (allowed | {"validated_against_version"}, required)
    d = copy.deepcopy(GOOD)
    d["adapter"]["validated_against_version"] = {
        "version_name": "1.2.3", "version_code": 1203,
        "captured_at": "2026-08-02", "source": "dumpsys package com.larus.nova",
    }
    assert va.check_one("doubao.json", d, future) == []


# ── A2：必填键 / 派生本身 ────────────────────────────────────────────────────

def test_a_missing_required_key_is_caught():
    d = copy.deepcopy(GOOD)
    del d["adapter"]["package"]
    assert "A2" in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_an_optional_key_may_be_absent():
    d = copy.deepcopy(GOOD)
    d["adapter"].pop("launch_hint", None)      # DTO 有默认值
    assert _codes(va.check_one("doubao.json", d, REAL_DTOS)) <= {"A1"}


def test_missing_dto_refuses_rather_than_passing_vacuously():
    """派生不出键集时要报错，不能"没查到问题"就放行——那是构造性失明。"""
    assert "A2" in _codes(va.check_one("x.json", GOOD, {}))


def test_dto_derivation_reads_serial_names_not_kotlin_identifiers():
    allowed, required = REAL_DTOS[va.DTO_OF_ADAPTER]
    assert "package_note" in allowed and "packageNote" not in allowed
    assert "package" in required and "kpi_mapping" in required
    assert "package_note" not in required        # 有默认值 ⇒ 非必填


def test_generic_commas_do_not_split_a_dto_field():
    """`Map<String, KpiProxyDto>` 里的逗号不是参数分隔符。"""
    src = 'data class T(\n  val a: Map<String, Int>,\n  @SerialName("b_c") val b: String = "",\n)'
    allowed, required = va.parse_dtos(src)["T"]
    assert allowed == {"a", "b_c"} and required == {"a"}


# ── R21：版本戳「可缺席，但不可半填」 ───────────────────────────────────────

def _with_version(**over):
    d = copy.deepcopy(GOOD)
    val = {"version_name": "1.2.3", "version_code": 1203,
           "captured_at": "2026-08-02", "source": "dumpsys package com.larus.nova"}
    val.update(over)
    d["adapter"]["validated_against_version"] = val
    allowed, required = REAL_DTOS[va.DTO_OF_ADAPTER]
    future = dict(REAL_DTOS)
    future[va.DTO_OF_ADAPTER] = (allowed | {"validated_against_version"}, required)
    return d, future


def test_absent_version_stamp_is_not_a_violation():
    """两个 App 装机核实时没留版本号（D-50/D-51）——没采到就是没采到，不编造。"""
    assert "validated_against_version" not in GOOD["adapter"]
    assert va.check_one("doubao.json", GOOD, REAL_DTOS) == []


def test_empty_version_object_is_caught():
    d, future = _with_version()
    d["adapter"]["validated_against_version"] = {}
    assert "R21a" in _codes(va.check_one("doubao.json", d, future))


def test_blank_version_name_is_caught():
    d, future = _with_version(version_name="  ")
    assert "R21b" in _codes(va.check_one("doubao.json", d, future))


def test_non_positive_version_code_is_caught():
    d, future = _with_version(version_code=0)
    assert "R21c" in _codes(va.check_one("doubao.json", d, future))


def test_boolean_version_code_is_caught_because_bool_is_an_int():
    """Python 里 True 是 int 的子类——不显式排除的话它会冒充一个合法 versionCode。"""
    d, future = _with_version(version_code=True)
    assert "R21c" in _codes(va.check_one("doubao.json", d, future))


def test_bad_date_format_is_caught():
    d, future = _with_version(captured_at="2026/08/02")
    assert "R21d" in _codes(va.check_one("doubao.json", d, future))


def test_missing_source_is_caught():
    """版本号本身没用——要能回答"这个数是怎么读出来的"。"""
    d, future = _with_version()
    del d["adapter"]["validated_against_version"]["source"]
    assert "R21e" in _codes(va.check_one("doubao.json", d, future))


# ── R22 / A3 ────────────────────────────────────────────────────────────────

def test_unrecognised_status_is_caught():
    d = copy.deepcopy(GOOD)
    d["adapter"]["status"] = "OK"
    assert "R22" in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_stale_is_a_recognised_status():
    """裁定 6-4 的降级态必须是合法值，否则宿主标了 STALE 反而被门拦下。"""
    d = copy.deepcopy(GOOD)
    d["adapter"]["status"] = "STALE"
    assert "R22" not in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_mirror_mismatch_is_caught():
    assert va.check_mirror("doubao.json", b"{}", os.path.join(va.ASSETS_DIR, "doubao.json"))


def test_missing_mirror_is_caught_not_skipped():
    assert va.check_mirror("nope.json", b"{}", os.path.join(va.ASSETS_DIR, "nope.json"))


def test_mirror_match_is_silent():
    with open(os.path.join(HERE, "doubao.json"), "rb") as fh:
        raw = fh.read()
    assert va.check_mirror("doubao.json", raw, os.path.join(va.ASSETS_DIR, "doubao.json")) == []


def main():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
        except Exception as exc:                                  # noqa: BLE001
            failed += 1
            print("FAIL %s: %s" % (name, exc))
    print("ran %d reflex tests: %d passed, %d failed"
          % (len(tests), len(tests) - failed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
