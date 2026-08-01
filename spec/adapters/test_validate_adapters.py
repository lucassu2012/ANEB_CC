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
    KOTLIN_SRC = _fh.read()
REAL_DTOS = va.parse_dtos(KOTLIN_SRC)

# 语料从目录枚举，不点名。函数名是复数就得真的喂复数（T14 交叉审查，D-392）。
SPEC_NAMES = sorted(f for f in os.listdir(HERE) if f.endswith(".json"))
SPECS = {}
for _name in SPEC_NAMES:
    with open(os.path.join(HERE, _name), encoding="utf-8") as _fh:
        SPECS[_name] = json.load(_fh)
GOOD = SPECS["doubao.json"]


def _codes(violations):
    """['[x] A1: ...'] -> {'A1', ...}，只比规则号，不比措辞。"""
    out = set()
    for item in violations:
        tail = item.split("] ", 1)[-1]
        out.add(tail.split(":", 1)[0].strip())
    return out


# ── A1：未知键（今天这个任务差点造成的那个事故） ──────────────────────────────

def test_the_real_specs_are_clean():
    for name in SPEC_NAMES:
        assert va.check_one(name, SPECS[name], REAL_DTOS) == [], name
    assert len(SPEC_NAMES) >= 2, "语料只剩一份时这条测试的复数名字就是假的"


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
    assert "validated_against_version" not in REAL_DTOS[va.DTO_OF_ADAPTER]["allowed"]


def test_the_same_field_passes_once_the_dto_declares_it():
    """明天 v2 给 DTO 加上字段后，同一个门自动放行——不需要有人回来改守卫。"""
    d, future = _with_version()
    assert va.check_one("doubao.json", d, future) == []


def test_an_unknown_key_INSIDE_the_future_version_stamp_is_caught():
    """A2 的下钻路径必须也是派生的。

    首版那张下钻表是**手写**的（input_node/response_node/send_button/caliber_redlines），
    于是明天 v2 把 `validated_against_version` 落成一个 DTO 之后，它**内部**多一个键
    没有任何一处会查——而那正是这道门唯一存在的理由（T14 交叉审查，D-392）。
    """
    d, future = _with_version()
    d["adapter"]["validated_against_version"]["version_code_note"] = "灰度版"
    assert "A1" in _codes(va.check_one("doubao.json", d, future))


# ── A2：必填键 / 派生本身 ────────────────────────────────────────────────────

def test_a_missing_required_key_is_caught():
    d = copy.deepcopy(GOOD)
    del d["adapter"]["package"]
    assert "A2" in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_an_optional_key_may_be_absent():
    d = copy.deepcopy(GOOD)
    d["adapter"].pop("launch_hint", None)      # DTO 有默认值
    # 曾写作 `<= {"A1"}`——删一个键造不出未知键，那条豁免恒不开火（T14 交叉审查，D-392）。
    assert va.check_one("doubao.json", d, REAL_DTOS) == []


def test_missing_dto_refuses_rather_than_passing_vacuously():
    """派生不出键集时要报错，不能"没查到问题"就放行——那是构造性失明。"""
    assert "A2" in _codes(va.check_one("x.json", GOOD, {}))


def test_dto_derivation_reads_serial_names_not_kotlin_identifiers():
    dto = REAL_DTOS[va.DTO_OF_ADAPTER]
    assert "package_note" in dto["allowed"] and "packageNote" not in dto["allowed"]
    assert "package" in dto["required"] and "kpi_mapping" in dto["required"]
    assert "package_note" not in dto["required"]      # 有默认值 ⇒ 非必填
    assert dto["kotlin"]["packageName"] == "package"  # A5 靠它把属性名换回 JSON 键


def test_generic_commas_do_not_split_a_dto_field():
    """`Map<String, KpiProxyDto>` 里的逗号不是参数分隔符。"""
    src = 'data class T(\n  val a: Map<String, Int>,\n  @SerialName("b_c") val b: String = "",\n)'
    dto = va.parse_dtos(src)["T"]
    assert dto["allowed"] == {"a", "b_c"} and dto["required"] == {"a"}
    assert dto["types"]["a"] == "Map<String, Int>"


def test_a_commented_out_field_does_not_become_a_phantom_required_key():
    """构造器里注释掉一行，派生出的键集会多一个既"允许"又"必填"的幽灵键。

    实测（T14 特别镜头）：`// val ghost: String,` 会让门要求一个严格解析器一定会拒的
    键——**派生本身出错比手写清单更难察觉**，因为手写清单至少看得见。
    """
    src = 'data class T(\n  // val ghost: String,\n  val real: String,\n)'
    dto = va.parse_dtos(src)["T"]
    assert dto["allowed"] == {"real"} and dto["required"] == {"real"}


def test_a_trailing_comment_does_not_widen_the_allowed_set():
    """行尾注释里的 `val` 曾被派生成一个额外的允许键——那是**静默放行**的方向。"""
    src = 'data class T(\n  val real: String = "",   // val fake: String,\n)'
    dto = va.parse_dtos(src)["T"]
    assert "fake" not in dto["allowed"]


# ── A4：类型不符（严格解析拒的另一半） ──────────────────────────────────────

def test_a_wrong_scalar_type_is_caught():
    d = copy.deepcopy(GOOD)
    d["adapter"]["display_name"] = 42
    assert "A4" in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_a_list_field_written_as_a_string_is_caught():
    d = copy.deepcopy(GOOD)
    d["adapter"]["observe_events"] = "TYPE_VIEW_CLICKED"
    assert "A4" in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_a_map_field_written_as_a_list_is_caught():
    d = copy.deepcopy(GOOD)
    d["adapter"]["kpi_mapping"] = []
    assert "A4" in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_a_nested_object_written_as_a_string_is_caught():
    d = copy.deepcopy(GOOD)
    d["adapter"]["input_node"] = "x"
    assert "A4" in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_null_in_a_non_nullable_field_is_caught():
    d = copy.deepcopy(GOOD)
    d["adapter"]["status"] = None
    assert "A4" in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_a_nullable_regex_may_be_null():
    """`view_id_regex: String?` 写 null 是合法的——A4 不能把可空字段也拦下来。"""
    d = copy.deepcopy(GOOD)
    d["adapter"]["input_node"]["view_id_regex"] = None
    assert "A4" not in _codes(va.check_one("doubao.json", d, REAL_DTOS))


# ── A5：parse() 在严格解析之后还会抛的那五条 ────────────────────────────────

def test_a_bumped_schema_version_is_caught():
    """`require(file.schemaVersion == SCHEMA_VERSION)`——判据从 Kotlin 常量派生。"""
    d = copy.deepcopy(GOOD)
    d["schema_version"] = "9.9.9"
    assert "A5" in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_a_blank_package_is_caught():
    d = copy.deepcopy(GOOD)
    d["adapter"]["package"] = "   "
    assert "A5" in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_empty_observe_events_is_caught():
    d = copy.deepcopy(GOOD)
    d["adapter"]["observe_events"] = []
    assert "A5" in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_kpi_mapping_missing_first_delta_is_caught():
    d = copy.deepcopy(GOOD)
    d["adapter"]["kpi_mapping"].pop("first_delta", None)
    assert "A5" in _codes(va.check_one("doubao.json", d, REAL_DTOS))


def test_the_require_derivation_is_read_from_parse_not_retyped_here():
    c = va.parse_loader_contract(KOTLIN_SRC)
    assert c["schema_version"] == "1.0.0"
    assert set(c["kpi_required"]) == {"first_delta", "delta_cadence"}
    assert set(c["non_blank"]) == {"id", "packageName"}
    assert c["non_empty"] == ["observeEvents"]


def test_a_broken_require_derivation_refuses_rather_than_passing_vacuously():
    """派生不出 `require` 就报违规——"没查到问题"不等于"没问题"。"""
    v = []
    va.check_loader_requires("x.json", GOOD, {"schema_version": "1.0.0"}, REAL_DTOS, v)
    assert "A5" in _codes(v)


# ── R21：版本戳「可缺席，但不可半填」 ───────────────────────────────────────

def _with_version(**over):
    """造出"v2 明天落地之后"的那个状态：DTO 多一个字段，且该字段是一个真的嵌套 DTO。

    首版这里只往 allowed 里加了个顶层键名，于是"明天自动放行"这条承诺**从没走过嵌套那一步**
    ——而下一步要落的恰恰是一个嵌套对象（T14 交叉审查，D-392）。
    """
    d = copy.deepcopy(GOOD)
    val = {"version_name": "1.2.3", "version_code": 1203,
           "captured_at": "2026-08-02", "source": "dumpsys package com.larus.nova"}
    val.update(over)
    d["adapter"]["validated_against_version"] = val
    return d, _future_with_version_dto()


def _future_with_version_dto():
    src = KOTLIN_SRC.replace(
        '        @SerialName("caliber_redlines") val caliberRedlines: CaliberDto,',
        '        @SerialName("caliber_redlines") val caliberRedlines: CaliberDto,\n'
        '        @SerialName("validated_against_version")\n'
        '        val validatedAgainstVersion: VersionStampDto? = null,')
    src += ('\n@Serializable\ndata class VersionStampDto(\n'
            '    @SerialName("version_name") val versionName: String,\n'
            '    @SerialName("version_code") val versionCode: Int,\n'
            '    @SerialName("captured_at") val capturedAt: String,\n'
            '    val source: String,\n)\n')
    future = va.parse_dtos(src)
    assert "validated_against_version" in future[va.DTO_OF_ADAPTER]["allowed"], \
        "夹具没造出明天的形态——它改的那一行大概已经不在 AdapterSpec.kt 里了"
    return future


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


def test_a_file_that_exists_only_in_assets_is_caught():
    """A3 的另一个方向：设备从 assets 全量枚举，spec 侧删了而镜像忘删，门此前看不见。"""
    assert va.check_assets_extras(["doubao.json"]), "assets 里多出来的文件必须报违规"


def test_todays_two_sides_have_the_same_file_set():
    assert va.check_assets_extras(SPEC_NAMES) == []


def test_the_ok_line_names_every_rule_family_the_file_implements():
    """自述守卫：收尾那句 OK 行是**手写**枚举，加一条规则不会让任何测试变红。

    portraits 侧早有同款守卫（`test_guard_self_description_covers_every_implemented_rule`），
    这一侧一直没有——「一条规则写下来之后，立刻回去数它自己覆盖了几个」（T14，D-392）。
    规则族从源码里数出来，不手写清单。
    """
    import re
    with open(os.path.join(HERE, "validate_adapters.py"), encoding="utf-8") as fh:
        src = fh.read()
    families = {m for m in re.findall(r"\[%s\]\s+([A-Z]+\d+)", src)}
    assert families, "没数出任何规则族，说明这条守卫的量法坏了"
    marker = "OK: all adapter-spec invariants hold"
    i = src.find(marker)
    assert i > 0, "找不到 OK 行"
    tail = src[i:i + 600]
    missing = sorted(f for f in families if f not in tail)
    assert not missing, "实现了 %s，OK 行里没交代：%s" % (sorted(families), missing)


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
