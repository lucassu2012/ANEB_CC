#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T14 特别镜头 B（DTO 派生键集）28 条发现的对抗验证。

原镜头零对抗验证（两名验证者均死于连接错误）。本脚本**不转述结论**：每一条各造一个
沙箱实验，把 Kotlin 源做文本突变后重新 parse_dtos / parse_loader_contract，再对一份
真实 spec 文档跑 check_one，打印实际违规。判定由输出得出，不由推理得出。

用法：python verify_lens_b.py
"""
import copy
import io
import json
import os
import sys

ROOT = r"E:\C Project\ANEB"
SPEC = os.path.join(ROOT, "spec", "adapters")
sys.path.insert(0, SPEC)
import validate_adapters as va  # noqa: E402

with open(va.KOTLIN_DTO, encoding="utf-8") as fh:
    KOTLIN = fh.read()
with open(os.path.join(SPEC, "doubao.json"), encoding="utf-8") as fh:
    GOOD = json.load(fh)

# 被反复用作插入锚点的那一行（夹具自检：必须恰好命中一次）
ANCHOR = '        @SerialName("caliber_redlines") val caliberRedlines: CaliberDto,'
assert KOTLIN.count(ANCHOR) == 1, "锚点歧义/失效——D-341"

RESULTS = []


def run(tag, claim, kotlin_src, doc, expect_desc):
    """跑一次实验，打印实际违规码与文本。"""
    dtos = va.parse_dtos(kotlin_src)
    contract = va.parse_loader_contract(kotlin_src)
    try:
        v = va.check_one("doubao.json", doc, dtos, contract)
    except Exception as exc:            # 崩溃本身也是一种结果
        v = ["<EXCEPTION> %s: %s" % (type(exc).__name__, exc)]
    codes = []
    for item in v:
        tail = item.split("] ", 1)[-1]
        codes.append(tail.split(":", 1)[0].strip())
    print("=" * 78)
    print("[%s] %s" % (tag, claim))
    print("  期望（原镜头）: %s" % expect_desc)
    print("  实测违规数: %d  码: %s" % (len(v), sorted(set(codes)) or "—"))
    for item in v:
        print("     - %s" % item[:190])
    RESULTS.append((tag, len(v), sorted(set(codes))))
    return v


def add_field(src, line):
    return src.replace(ANCHOR, ANCHOR + "\n" + line)


def with_key(key, value):
    d = copy.deepcopy(GOOD)
    d["adapter"][key] = value
    return d


# ───────────────────────── 基线 ─────────────────────────
run("BASE", "未突变：真语料应零违规", KOTLIN, copy.deepcopy(GOOD), "0 违规")

# ───────────────── [OK] 组：原镜头称「主线演进全部正确」 ─────────────────

# (a) 新增必填字段（无默认值）→ 四份 JSON 当场缺必填
run("a1", "DTO 新增**必填**字段，JSON 未跟进",
    add_field(KOTLIN, '        @SerialName("new_req") val newReq: String,'),
    copy.deepcopy(GOOD), "A2 缺必填键")

# (b) 新增可选字段（带默认值）→ JSON 缺席应放行
run("a2", "DTO 新增**带默认值**字段，JSON 未跟进",
    add_field(KOTLIN, '        @SerialName("new_opt") val newOpt: String = "",'),
    copy.deepcopy(GOOD), "0 违规（自动放行）")

run("a3", "DTO 新增带默认值字段，JSON 也写了该键",
    add_field(KOTLIN, '        @SerialName("new_opt") val newOpt: String = "",'),
    with_key("new_opt", "x"), "0 违规")

run("a4", "JSON 写了 DTO 没有的键（A1 主线）",
    KOTLIN, with_key("some_new_field", "x"), "A1 未知键")

# (c) 类型变更
run("b1", "DTO 声明 Int，JSON 给 String",
    add_field(KOTLIN, '        @SerialName("n") val n: Int = 0,'),
    with_key("n", "12"), "A4 类型不符")

run("b2", "DTO 声明非空 String，JSON 给 null",
    add_field(KOTLIN, '        @SerialName("s") val s: String = "",'),
    with_key("s", None), "A4 null 落非空字段")

run("b3", "DTO 声明 List<String>，JSON 给 String",
    add_field(KOTLIN, '        @SerialName("l") val l: List<String> = emptyList(),'),
    with_key("l", "not-a-list"), "A4 必须是数组")

# (d) 新增嵌套 data class（同文件）
NEST_PLAIN = ('\n@Serializable\ndata class NestDto(\n'
              '    @SerialName("aa") val aa: String,\n'
              '    val bb: Int,\n)\n')
run("c1", "嵌套 data class（同文件）内部写未知键",
    add_field(KOTLIN, '        @SerialName("nest") val nest: NestDto? = null,') + NEST_PLAIN,
    with_key("nest", {"aa": "x", "bb": 1, "ghost": 1}), "A1 咬住内部未知键")

run("c2", "List<嵌套 DTO> 内部未知键",
    add_field(KOTLIN, '        @SerialName("nests") val nests: List<NestDto> = emptyList(),') + NEST_PLAIN,
    with_key("nests", [{"aa": "x", "bb": 1, "ghost": 1}]), "A1 咬住")

run("c3", "Map<String, List<嵌套 DTO>> 内部未知键",
    add_field(KOTLIN, '        @SerialName("m") val m: Map<String, List<NestDto>> = emptyMap(),') + NEST_PLAIN,
    with_key("m", {"k": [{"aa": "x", "bb": 1, "ghost": 1}]}), "A1 咬住")

# 声明在 object 内的 data class（即 AdapterSpecLoader 内部）
NEST_IN_OBJECT = KOTLIN.replace(
    "    @Serializable\n    data class CaliberDto(",
    "    @Serializable\n    data class NestDto(\n"
    "        @SerialName(\"aa\") val aa: String,\n"
    "    )\n\n    @Serializable\n    data class CaliberDto(")
assert NEST_IN_OBJECT != KOTLIN
run("c4", "嵌套 data class 声明在 `object` 内部",
    add_field(NEST_IN_OBJECT, '        @SerialName("nest") val nest: NestDto? = null,'),
    with_key("nest", {"aa": "x", "ghost": 1}), "A1 咬住")

# (e) @SerialName 重命名 / 字段删除
run("d1", "@SerialName 重命名（package → package_id）",
    KOTLIN.replace('@SerialName("package") val packageName', '@SerialName("package_id") val packageName'),
    copy.deepcopy(GOOD), "A1 未知键 + A2 缺必填 双报")

run("d2", "DTO 删掉一个字段（launch_hint）",
    KOTLIN.replace('        @SerialName("launch_hint") val launchHint: String = "",\n', ''),
    copy.deepcopy(GOOD), "A1 未知键")

# ───────────────── [BAD] 组：原镜头称「静默给出错的键集」 ─────────────────

# F1 嵌套类型不是 data class
run("F1a", "嵌套类型是普通 `class`（非 data）",
    add_field(KOTLIN, '        @SerialName("nest") val nest: PlainNest? = null,')
    + '\n@Serializable\nclass PlainNest(\n    @SerialName("aa") val aa: String,\n)\n',
    with_key("nest", {"ghost": 1}), "[BAD] 0 违规，整块静默不查")

run("F1b", "嵌套类型是 `enum class`",
    add_field(KOTLIN, '        @SerialName("nest") val nest: NestEnum? = null,')
    + '\n@Serializable\nenum class NestEnum { A, B }\n',
    with_key("nest", {"ghost": 1}), "[BAD] 0 违规")

run("F1c", "嵌套类型经 `typealias` 指向",
    add_field(KOTLIN, '        @SerialName("nest") val nest: NestAlias? = null,')
    + '\ntypealias NestAlias = Map<String, String>\n',
    with_key("nest", {"ghost": 1}), "[BAD] 0 违规")

run("F1d", "【最要紧】嵌套 DTO **声明在别的文件**（v2 明天要踩的那处）",
    add_field(KOTLIN, '        @SerialName("validated_against_version")\n'
                      '        val validatedAgainstVersion: VersionStampDto? = null,'),
    with_key("validated_against_version",
             {"version_name": "1.2.3", "version_code": 1203,
              "captured_at": "2026-08-02", "source": "dumpsys",
              "ghost_key_a_strict_parser_would_reject": 1}),
    "[BAD] 门印 OK、零违规（严格解析器必拒的键）")

# F2 默认值字符串里的特殊字符吃掉下一个字段
run("F2a", "默认值字符串里带 `//`",
    add_field(KOTLIN, '        @SerialName("u") val u: String = "http://x",\n'
                      '        @SerialName("after") val after: String,'),
    copy.deepcopy(GOOD), "[BAD] 下一个字段整个从键集里消失")

run("F2b", "默认值字符串里带 `)`",
    add_field(KOTLIN, '        @SerialName("u") val u: String = "a)b",\n'
                      '        @SerialName("after") val after: String,'),
    copy.deepcopy(GOOD), "[BAD] 下一个字段消失")

run("F2c", "默认值字符串里带 `>`",
    add_field(KOTLIN, '        @SerialName("u") val u: String = "a>b",\n'
                      '        @SerialName("after") val after: String,'),
    copy.deepcopy(GOOD), "[BAD] 下一个字段消失")

# F3 var 代替 val
run("F3", "`var` 代替 `val`",
    add_field(KOTLIN, '        @SerialName("mut") var mut: String,'),
    with_key("mut", "x"), "[BAD] 该字段既不在 allowed 也不在 required")

# F4 注解里带冒号的字符串
run("F4", "注解里带冒号的字符串 → 必填被判成可选",
    add_field(KOTLIN, '        @Deprecated("a:b", level = DeprecationLevel.WARNING)\n'
                      '        @SerialName("dep") val dep: String,'),
    copy.deepcopy(GOOD), "[BAD] 必填字段被判成可选（不报 A2）")

# F5 parse() 的 require 演进
run("F5a", "`parse()` 删掉一条 require（a.id.isNotBlank）",
    KOTLIN.replace('        require(a.id.isNotBlank()) { "adapter.id blank" }\n', ''),
    (lambda: (lambda d: (d["adapter"].__setitem__("id", "  "), d)[1])(copy.deepcopy(GOOD)))(),
    "[BAD] 判据静默变窄：空白 id 不再被拦")

run("F5b", "`parse()` 新增一条形状不同的 require（size >= 2）",
    KOTLIN.replace('        require(a.observeEvents.isNotEmpty()) { "observe_events empty" }',
                   '        require(a.observeEvents.size >= 2) { "observe_events too few" }'),
    copy.deepcopy(GOOD), "[BAD] 派生正则认不出，静默不覆盖")

# 对照：把 require 全删光 → 应报「派生坏了」（refuses to pass vacuously）
_all_req_gone = KOTLIN
for _line in ['        require(a.id.isNotBlank()) { "adapter.id blank" }\n',
              '        require(a.packageName.isNotBlank()) { "adapter.package blank" }\n',
              '        require(a.observeEvents.isNotEmpty()) { "observe_events empty" }\n']:
    _all_req_gone = _all_req_gone.replace(_line, '')
run("F5c", "对照：require 全删 → 应报「派生坏了」而非放行",
    _all_req_gone, copy.deepcopy(GOOD), "A5 came back empty（refuses to pass）")

# ───────────────── v2 落地建议的三条机器可判断言 ─────────────────
VSTAMP_SAME_FILE = ('\n@Serializable\ndata class VersionStampDto(\n'
                    '    @SerialName("version_name") val versionName: String,\n'
                    '    @SerialName("version_code") val versionCode: Int,\n'
                    '    @SerialName("captured_at") val capturedAt: String,\n'
                    '    val source: String,\n)\n')

run("V2a", "v2 建议①：同文件 data class + `= null` 默认 → 今日四份 JSON 应放行",
    add_field(KOTLIN, '        @SerialName("validated_against_version")\n'
                      '        val validatedAgainstVersion: VersionStampDto? = null,') + VSTAMP_SAME_FILE,
    copy.deepcopy(GOOD), "0 违规")

run("V2b", "v2 建议①反面：同文件但**不带默认值** → 四份 JSON 当场全红",
    add_field(KOTLIN, '        @SerialName("validated_against_version")\n'
                      '        val validatedAgainstVersion: VersionStampDto,') + VSTAMP_SAME_FILE,
    copy.deepcopy(GOOD), "A2 缺必填")

run("V2c", "v2 建议①正向：同文件 data class，内部未知键被咬",
    add_field(KOTLIN, '        @SerialName("validated_against_version")\n'
                      '        val validatedAgainstVersion: VersionStampDto? = null,') + VSTAMP_SAME_FILE,
    with_key("validated_against_version",
             {"version_name": "1.2.3", "version_code": 1203, "captured_at": "2026-08-02",
              "source": "dumpsys", "ghost": 1}), "A1 咬住")

run("V2d", "v2 建议②：序列名改掉（version_name→app_version_name）→ 一份**设备接受**的合法文件被报四条",
    add_field(KOTLIN, '        @SerialName("validated_against_version")\n'
                      '        val validatedAgainstVersion: VersionStampDto? = null,')
    + VSTAMP_SAME_FILE.replace('@SerialName("version_name") val versionName',
                               '@SerialName("app_version_name") val versionName')
                      .replace('@SerialName("version_code") val versionCode',
                               '@SerialName("app_version_code") val versionCode')
                      .replace('@SerialName("captured_at") val capturedAt',
                               '@SerialName("stamped_at") val capturedAt')
                      .replace('    val source: String,', '    val obtained_via: String,'),
    with_key("validated_against_version",
             {"app_version_name": "1.2.3", "app_version_code": 1203,
              "stamped_at": "2026-08-02", "obtained_via": "dumpsys"}),
    "R21b–e 是手写字面量 → 四条违规")

print("\n" + "=" * 78)
print("汇总：")
for tag, n, codes in RESULTS:
    print("  %-6s violations=%-3d codes=%s" % (tag, n, codes or "—"))
