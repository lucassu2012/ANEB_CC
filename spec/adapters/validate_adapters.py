#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec/adapters/*.json 的形状门（T11 ③，裁定 6-4）。

放在数据文件旁边、与 `spec/portraits/check_redline.py` 同构：一个校验器 + 一份反例，
由 `scripts/verify_all.ps1` 作为 `adapters-spec` 步调用。

为什么需要它（三条，都是实测出来的，不是设想）
──────────────────────────────────────────────────────────────────────────────
A1 **加一个键、或换一个类型，就能让观察静默停摆**。`AdapterSpecLoader` 用的是默认严格
   `Json`（源码注释逐字："默认严格：**未知键/类型不符**即抛 → 触发 fail-safe 空列表"）。
   规格文件多一个 DTO 不认识的键 → 解析抛 → fail-safe 返回空列表 → **当前目录里的
   全部适配器**（不是"两个"：`loadFromAssets` 单文件坏也整体回空，KDoc 逐字如此）
   一起落回 generic 模式；而 D-54 规定落库要求 `specId != null`，于是
   **adapter_obs 从此一条不入库，且没有任何一处会报错**。
   `spec/README.md` 治理规则 3 说 additive-only 是安全的——**对 adapters 不成立**：
   这里的"加一个字段"是双侧变更，消费方是严格解析的。本门把这条隐含契约变成显式的、
   会失败的检查。
   **注意那句注释有两半**（T14 交叉审查，D-392）：首版只实现了"未知键"那半，
   于是 `observe_events: 5`、`kpi_mapping: []` 这类**类型**突变一路放行，而设备上的
   后果与多一个键逐字相同。A4 补的就是另外那半。

A2 **允许键集、嵌套结构与字段类型都不能手写**。手写清单会漏、会过期（D-275）。本门直接
   从 `AdapterSpec.kt` 的 DTO 定义**派生**允许键、必填键**与每个字段的类型**：DTO 加了
   字段，门自动放行；DTO 没加而 JSON 先加了，门当场拦下。判据与消费方是同一个来源。
   下钻同样是派生的——凡字段类型是另一个 DTO（或 `List<DTO>` / `Map<K, DTO>`），本门自动
   递归进去。首版这里回退成了一张手写表，于是**明天要落的 `validated_against_version`
   内部一个键都没人查**（D-392 处置）。

A5 **严格解析不是唯一的门**。`AdapterSpecLoader.parse()` 在 `decodeFromString` 之后还有
   五条 `require`（schema 版本、id/package 非空、observe_events 非空、kpi_mapping 必含
   first_delta 与 delta_cadence）。它们抛出的后果与 A1 逐字相同，故一并从 `parse()`
   的源码里**派生**判据（不是照抄一份到 Python 里，抄来的那份会过期）。

A3 **assets 镜像的字节一致此前不在 verify_all 里**。那条不变量只由 Kotlin 的
   `AdapterSpecTest` 用例 3 守着，而 `verify_all.ps1` 只跑 `assembleDebug`、不跑单测
   ——也就是说，改 `spec/adapters/*.json` 而忘了同步 assets，本地门禁**一声不吭**。
   本门把它搬进 Python 链（只读 app/，不写）。

`validated_against_version`（裁定 6-4）当前是**可选**字段：两个 App 装机核实时
（D-50/D-51）没有留下版本号，本门因此**不要求它存在**——没采到就是没采到，不编造。
但**一旦出现就必须完整且格式正确**，与 portraits 侧 dist 段同一个道理（R20/D-348）：
"缺席"和"半填"说的是两件事。

exit 0 = 全部不变量成立 / 1 = 有违规。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(HERE))
KOTLIN_DTO = os.path.join(_ROOT, "app", "probe", "src", "main", "java", "com",
                          "aneb", "probe", "adapter", "AdapterSpec.kt")
ASSETS_DIR = os.path.join(_ROOT, "app", "probe", "src", "main", "assets", "spec_adapters")

# 根 DTO 的名字——从这里开始按字段类型自动下钻，路径表不再手写（D-392）。
DTO_OF_ROOT = "AdapterSpecFileDto"
DTO_OF_ADAPTER = "AdapterDto"

STATUS_VALUES = {"PENDING-VALIDATION", "VALIDATED-PARTIAL", "VALIDATED-OBSERVED", "STALE"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATA_CLASS_RE = re.compile(r"data\s+class\s+(\w+)\s*\(", re.S)
_SERIAL_NAME_RE = re.compile(r'@SerialName\("([^"]+)"\)')
_VAL_RE = re.compile(r"\bval\s+(\w+)\s*:\s*([^=]+)")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_SCHEMA_CONST_RE = re.compile(r'\bSCHEMA_VERSION\s*=\s*"([^"]+)"')
_PARSE_FUN_RE = re.compile(r"fun\s+parse\s*\(.*?\)\s*:\s*AdapterSpec\s*\{", re.S)
_REQ_NOT_BLANK_RE = re.compile(r"require\(\s*a\.(\w+)\.isNotBlank\(\)")
_REQ_NOT_EMPTY_RE = re.compile(r"require\(\s*a\.(\w+)\.isNotEmpty\(\)")
_REQ_KPI_RE = re.compile(r'"(\w+)"\s+in\s+a\.kpiMapping')

# Kotlin 类型 -> 该字段在 JSON 里必须是什么。只列 DTO 里真出现过的那几种；
# 认不出的类型**不判**（宁可漏一格，也不凭猜测报一个假违规）。
_SCALARS = {
    "String": (str,), "Int": (int,), "Long": (int,), "Short": (int,),
    "Float": (float, int), "Double": (float, int), "Boolean": (bool,),
}


def _strip_comments(src):
    """去掉注释再解析。

    为什么必须做（T14 实测，D-392）：`_VAL_RE` 不认注释，于是
      * 构造器里**注释掉**的一行 `// val ghost: String,` 会被派生成一个既"允许"又"必填"
        的幽灵键——门于是要求一个严格解析器一定会拒的键；
      * 字段后的**行尾注释** `val real: String = "",   // val fake: String,` 会多派生出
        一个 `fake`，于是 JSON 里写 `fake` 门**静默放行**，设备上照旧抛。
    两种都是"派生"这件事本身出错，比手写清单更难察觉——手写清单至少看得见。
    """
    return _LINE_COMMENT_RE.sub("", _BLOCK_COMMENT_RE.sub("", src or ""))


def _split_top_level(body):
    """按顶层逗号切 DTO 参数表——泛型里的逗号（Map<String, X>）不算分隔符。"""
    parts, depth, cur = [], 0, []
    for ch in body:
        if ch in "<([":
            depth += 1
        elif ch in ">)]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur))
    return parts


def parse_dtos(kotlin_src):
    """Kotlin 源码 -> {DTO 名: {'allowed', 'required', 'types', 'kotlin'}}。纯函数。

    * 必填 = 参数没有 `=` 默认值。这正是严格解析下"少了就抛"的那一批；
    * `types` = {JSON 键: Kotlin 类型文本}，A4 的类型判据与 A2 的下钻路径都由它派生；
    * `kotlin` = {Kotlin 属性名: JSON 键}，A5 要拿 `parse()` 里的 `a.packageName`
      这类**属性名**去找它对应的 JSON 键，不能靠人记得 packageName ↔ package。
    """
    src = _strip_comments(kotlin_src)
    out = {}
    for m in _DATA_CLASS_RE.finditer(src):
        name = m.group(1)
        i, depth = m.end() - 1, 0
        for j in range(m.end() - 1, len(src)):
            if src[j] == "(":
                depth += 1
            elif src[j] == ")":
                depth -= 1
                if depth == 0:
                    i = j
                    break
        body = src[m.end():i]
        allowed, required, types, kotlin = set(), set(), {}, {}
        for part in _split_top_level(body):
            vm = _VAL_RE.search(part)
            if not vm:
                continue
            sm = _SERIAL_NAME_RE.search(part)
            key = sm.group(1) if sm else vm.group(1)
            allowed.add(key)
            types[key] = vm.group(2).strip().rstrip(",").strip()
            kotlin[vm.group(1)] = key
            if "=" not in part.split(":", 1)[-1]:
                required.add(key)
        if allowed:
            out[name] = {"allowed": allowed, "required": required,
                         "types": types, "kotlin": kotlin}
    return out


def parse_loader_contract(kotlin_src):
    """`AdapterSpecLoader.parse()` 的五条 `require` -> 机器可判的判据。纯函数。

    A5 的判据必须从**消费方**取，不能在这里照抄一份：抄来的那份会在 `parse()` 改了之后
    悄悄过期，而过期的守卫比没有守卫更危险。派生不出来时返回 `None` 那一项，调用方据此
    报"派生坏了"而不是"没查到问题"（构造性失明的反方向）。
    """
    src = _strip_comments(kotlin_src)
    ver = _SCHEMA_CONST_RE.search(src)
    m = _PARSE_FUN_RE.search(src)
    body = ""
    if m:
        depth, i = 0, m.end() - 1
        for j in range(m.end() - 1, len(src)):
            if src[j] == "{":
                depth += 1
            elif src[j] == "}":
                depth -= 1
                if depth == 0:
                    i = j
                    break
        body = src[m.end():i]
    return {
        "schema_version": ver.group(1) if ver else None,
        "non_blank": sorted(set(_REQ_NOT_BLANK_RE.findall(body))),
        "non_empty": sorted(set(_REQ_NOT_EMPTY_RE.findall(body))),
        "kpi_required": sorted(set(_REQ_KPI_RE.findall(body))),
    }


def _check_keys(app, where, obj, dto_name, dtos, v):
    """未知键 / 缺必填键——两条都按 DTO 派生的集合判。"""
    if dto_name not in dtos:
        v.append("[%s] A2: DTO %s not found in AdapterSpec.kt — cannot derive the key set; "
                 "the guard refuses to pass rather than pass vacuously" % (app, dto_name))
        return
    allowed, required = dtos[dto_name]["allowed"], dtos[dto_name]["required"]
    for k in sorted(set(obj) - allowed):
        v.append("[%s] A1: %s has key '%s' that %s does not declare — the app parses this file "
                 "with a strict Json, so an unknown key throws and the fail-safe returns an EMPTY "
                 "spec list: every app silently drops to generic and adapter_obs stops persisting "
                 "(D-54). Add the field to the DTO first, then to this file." % (app, where, k, dto_name))
    for k in sorted(required - set(obj)):
        v.append("[%s] A2: %s is missing required key '%s' (%s declares it with no default)"
                 % (app, where, k, dto_name))


def _generic_args(type_text):
    """`Map<String, KpiProxyDto>` -> ['String', 'KpiProxyDto']；无泛型 -> []。"""
    i = type_text.find("<")
    if i < 0 or not type_text.rstrip("?").endswith(">"):
        return []
    inner = type_text.rstrip("?")[i + 1:-1]
    return [p.strip() for p in _split_top_level(inner) if p.strip()]


def _check_value(app, where, value, type_text, dtos, v):
    """A4/A2：按 DTO 声明的**类型**判一个值，并在类型是另一个 DTO 时自动下钻。

    严格 `Json` 对类型不符与未知键的处理完全一样（都抛 → fail-safe 空列表），所以这两条
    必须一起查。下钻路径由类型给出，不再手写——手写的那张表恰好漏了明天要落的那个字段。
    """
    base = type_text.strip()
    nullable = base.endswith("?")
    base = base.rstrip("?").strip()
    if value is None:
        if not nullable:
            v.append("[%s] A4: %s is null but %s declares it non-nullable — the strict Json "
                     "throws and the fail-safe returns an EMPTY spec list" % (app, where, base))
        return
    if base in _SCALARS:
        want = _SCALARS[base]
        # 布尔是 int 的子类：不显式排除的话 true 会冒充一个合法的 Int（同 R21c 的坑）。
        okay = isinstance(value, want) and not (bool not in want and isinstance(value, bool))
        if not okay:
            v.append("[%s] A4: %s must be %s per AdapterSpec.kt, got %s"
                     % (app, where, base, type(value).__name__))
        return
    if base.startswith("List<"):
        if not isinstance(value, list):
            v.append("[%s] A4: %s must be a JSON array (%s), got %s"
                     % (app, where, base, type(value).__name__))
            return
        args = _generic_args(type_text)
        if args:
            for i, item in enumerate(value):
                _check_value(app, "%s[%d]" % (where, i), item, args[0], dtos, v)
        return
    if base.startswith("Map<"):
        if not isinstance(value, dict):
            v.append("[%s] A4: %s must be a JSON object (%s), got %s"
                     % (app, where, base, type(value).__name__))
            return
        args = _generic_args(type_text)
        if len(args) == 2:
            for k in sorted(value):
                _check_value(app, "%s.%s" % (where, k), value[k], args[1], dtos, v)
        return
    if base in dtos:
        if not isinstance(value, dict):
            v.append("[%s] A4: %s must be a JSON object (%s), got %s"
                     % (app, where, base, type(value).__name__))
            return
        _check_dto(app, where, value, base, dtos, v)
        return
    # 认不出的类型：不判。凭猜测报违规比漏一格更糟。


def _check_dto(app, where, obj, dto_name, dtos, v):
    """一个 DTO 承接的对象：先查键集，再逐字段查类型并按类型自动下钻。"""
    _check_keys(app, where, obj, dto_name, dtos, v)
    if dto_name not in dtos:
        return
    types = dtos[dto_name]["types"]
    for key in sorted(set(obj) & set(types)):
        _check_value(app, "%s.%s" % (where, key), obj[key], types[key], dtos, v)


def check_loader_requires(app, doc, contract, dtos, v):
    """A5：`AdapterSpecLoader.parse()` 在严格解析之后还会抛的那五条。

    判据全部从 `parse()` 源码派生（见 `parse_loader_contract`）；派生不出来时报违规，
    不"没查到问题就放行"。
    """
    want = contract.get("schema_version")
    if not want:
        v.append("[%s] A5: cannot derive SCHEMA_VERSION from AdapterSpec.kt — refusing to pass "
                 "a version check that would otherwise be vacuous" % app)
    elif doc.get("schema_version") != want:
        v.append("[%s] A5: schema_version=%r but AdapterSpecLoader.parse() requires %r — "
                 "it throws, and the fail-safe returns an EMPTY spec list"
                 % (app, doc.get("schema_version"), want))
    adapter = doc.get("adapter")
    if not isinstance(adapter, dict):
        return
    kmap = dtos.get(DTO_OF_ADAPTER, {}).get("kotlin", {})
    if not contract.get("non_blank") or not contract.get("non_empty") \
            or not contract.get("kpi_required"):
        v.append("[%s] A5: the require() derivation from AdapterSpecLoader.parse() came back "
                 "empty — the shape of parse() changed; fix the derivation rather than trusting "
                 "a check that now looks at nothing" % app)
        return
    for prop in contract["non_blank"]:
        key = kmap.get(prop, prop)
        val = adapter.get(key)
        if not isinstance(val, str) or not val.strip():
            v.append("[%s] A5: adapter.%s must be non-blank (parse() requires a.%s.isNotBlank())"
                     % (app, key, prop))
    for prop in contract["non_empty"]:
        key = kmap.get(prop, prop)
        val = adapter.get(key)
        if not val:
            v.append("[%s] A5: adapter.%s must be non-empty (parse() requires a.%s.isNotEmpty())"
                     % (app, key, prop))
    kpis = adapter.get("kpi_mapping")
    if isinstance(kpis, dict):
        for need in contract["kpi_required"]:
            if need not in kpis:
                v.append("[%s] A5: kpi_mapping must contain '%s' (parse() requires it)"
                         % (app, need))


def check_validated_against_version(app, adapter, v):
    """裁定 6-4：字段可缺席（还没采到），但**一旦出现就必须完整**。"""
    if "validated_against_version" not in adapter:
        return
    val = adapter["validated_against_version"]
    if not isinstance(val, dict) or not val:
        v.append("[%s] R21a: validated_against_version present but not a non-empty object — "
                 "omit it entirely while the version has not been captured (absent != half-filled)" % app)
        return
    name = val.get("version_name")
    if not isinstance(name, str) or not name.strip():
        v.append("[%s] R21b: validated_against_version.version_name must be a non-empty string" % app)
    code = val.get("version_code")
    # 布尔是 int 的子类——不显式排除的话 True 会被当成合法的 versionCode。
    if isinstance(code, bool) or not isinstance(code, int) or code <= 0:
        v.append("[%s] R21c: validated_against_version.version_code must be a positive integer" % app)
    at = val.get("captured_at")
    if not isinstance(at, str) or not _DATE_RE.match(at or ""):
        v.append("[%s] R21d: validated_against_version.captured_at must be YYYY-MM-DD" % app)
    src = val.get("source")
    if not isinstance(src, str) or not src.strip():
        v.append("[%s] R21e: validated_against_version.source must say how the value was obtained "
                 "(the read-only `dumpsys package <pkg>` run that produced it)" % app)


_DEFAULT_CONTRACT = None


def default_contract():
    """从真的 `AdapterSpec.kt` 派生 A5 判据；读不到就返回空 dict（→ A5 报"派生坏了"）。"""
    global _DEFAULT_CONTRACT
    if _DEFAULT_CONTRACT is None:
        try:
            with open(KOTLIN_DTO, encoding="utf-8") as fh:
                _DEFAULT_CONTRACT = parse_loader_contract(fh.read())
        except OSError:
            _DEFAULT_CONTRACT = {}
    return _DEFAULT_CONTRACT


def check_one(app, doc, dtos, contract=None):
    """单份规格 -> 违规串列表。纯函数，无 IO（contract 缺省时按真 DTO 源派生一次）。"""
    v = []
    _check_dto(app, "root", doc, DTO_OF_ROOT, dtos, v)
    adapter = doc.get("adapter")
    if not isinstance(adapter, dict):
        v.append("[%s] A2: 'adapter' must be an object" % app)
        return v
    check_loader_requires(app, doc, contract if contract is not None else default_contract(),
                          dtos, v)

    status = adapter.get("status")
    if status not in STATUS_VALUES:
        v.append("[%s] R22: status '%s' is not one of %s — an unrecognised status reads as "
                 "'validated' to a human skimming the file" % (app, status, sorted(STATUS_VALUES)))
    check_validated_against_version(app, adapter, v)
    return v


def check_mirror(name, spec_bytes, assets_path):
    """A3：spec 权威副本 ↔ assets 运行时镜像，字节级一致。"""
    if not os.path.isfile(assets_path):
        return ["[%s] A3: assets mirror missing at %s — the app ships its own copy; a spec-only "
                "edit would never reach the device" % (name, os.path.relpath(assets_path, _ROOT))]
    with open(assets_path, "rb") as fh:
        if fh.read() != spec_bytes:
            return ["[%s] A3: assets mirror differs from the spec copy byte-for-byte. spec/adapters "
                    "is the single source of truth; the mirror is what actually runs. Until they "
                    "match, what you validated is not what the device loads." % name]
    return []


def check_assets_extras(spec_names):
    """A3 的**另一个方向**：assets 里多出来的文件。

    首版只从 `spec/adapters/*.json` 枚举，再逐个反查 assets——于是"spec 删了而 assets 忘删"
    这一侧永远看不见，而设备加载的恰恰是 assets（`assets.list(ASSET_DIR)` 全量）。更糟的是
    `loadFromAssets` 单文件坏就整体回空：一份陈旧镜像足以让全部规格失效，而门照旧印 OK。
    今天两侧各 4 个文件是巧合，不是守卫（T14 交叉审查，D-392）。
    """
    if not os.path.isdir(ASSETS_DIR):
        return ["[assets] A3: %s is missing — the device loads its specs from there"
                % os.path.relpath(ASSETS_DIR, _ROOT)]
    have = sorted(f for f in os.listdir(ASSETS_DIR) if f.endswith(".json"))
    extra = sorted(set(have) - set(spec_names))
    return ["[%s] A3: present in assets but not in spec/adapters — the device would still load "
            "it. spec/adapters is the single source of truth; delete the stale mirror or restore "
            "the spec copy." % name for name in extra]


def main():
    if not os.path.isfile(KOTLIN_DTO):
        print("cannot read the DTO source at %s — refusing to validate against a hand-written "
              "key list" % KOTLIN_DTO)
        return 1
    with open(KOTLIN_DTO, encoding="utf-8") as fh:
        kotlin_src = fh.read()
    dtos = parse_dtos(kotlin_src)
    contract = parse_loader_contract(kotlin_src)
    if DTO_OF_ADAPTER not in dtos:
        print("parsed %d DTO(s) from AdapterSpec.kt but not %s — the derivation broke; refusing "
              "to pass" % (len(dtos), DTO_OF_ADAPTER))
        return 1

    names = sorted(f for f in os.listdir(HERE) if f.endswith(".json"))
    if not names:
        print("no adapter specs found in %s" % HERE)
        return 1

    violations = check_assets_extras(names)
    for name in names:
        path = os.path.join(HERE, name)
        with open(path, "rb") as fh:
            raw = fh.read()
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            violations.append("[%s] parse error: %s" % (name, exc))
            continue
        violations += check_one(name, doc, dtos, contract)
        violations += check_mirror(name, raw, os.path.join(ASSETS_DIR, name))

    print("Checked %d adapter spec(s): %s" % (len(names), ", ".join(names)))
    print("  key sets derived from %s (%d DTOs)" % (os.path.basename(KOTLIN_DTO), len(dtos)))
    if violations:
        print("VIOLATIONS: %d" % len(violations))
        for item in violations:
            print("  - %s" % item)
        return 1
    print("OK: all adapter-spec invariants hold (A1 no key the strict parser would reject, "
          "A2 required keys present, A3 assets mirror byte-identical and carries nothing extra, "
          "A4 every value has the type its DTO declares, A5 the parse() require()s hold, "
          "R21 version stamp complete-if-present, R22 status recognised).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
