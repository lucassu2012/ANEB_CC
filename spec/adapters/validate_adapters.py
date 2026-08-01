#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec/adapters/*.json 的形状门（T11 ③，裁定 6-4）。

放在数据文件旁边、与 `spec/portraits/check_redline.py` 同构：一个校验器 + 一份反例，
由 `scripts/verify_all.ps1` 作为 `adapters-spec` 步调用。

为什么需要它（三条，都是实测出来的，不是设想）
──────────────────────────────────────────────────────────────────────────────
A1 **加一个键就能让观察静默停摆**。`AdapterSpecLoader` 用的是默认严格 `Json`
   （源码注释逐字："默认严格：未知键/类型不符即抛 → 触发 fail-safe 空列表"）。
   规格文件多一个 DTO 不认识的键 → 解析抛 → fail-safe 返回空列表 → 两个 App
   全部落回 generic 模式；而 D-54 规定落库要求 `specId != null`，于是
   **adapter_obs 从此一条不入库，且没有任何一处会报错**。
   `spec/README.md` 治理规则 3 说 additive-only 是安全的——**对 adapters 不成立**：
   这里的"加一个字段"是双侧变更，消费方是严格解析的。本门把这条隐含契约变成显式的、
   会失败的检查。

A2 **允许键集不能手写**。手写清单会漏、会过期（D-275）。本门直接从
   `AdapterSpec.kt` 的 DTO 定义**派生**允许键与必填键：DTO 加了字段，门自动放行；
   DTO 没加而 JSON 先加了，门当场拦下。判据与消费方是同一个来源。

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

# JSON 里的位置 -> 承接它的 DTO 类名。键名用 DTO 名而非路径，因为派生源是 DTO。
DTO_OF_ROOT = "AdapterSpecFileDto"
DTO_OF_ADAPTER = "AdapterDto"
DTO_OF_NODE = "NodeRuleDto"
DTO_OF_SEND = "SendButtonRuleDto"
DTO_OF_KPI = "KpiProxyDto"
DTO_OF_CALIBER = "CaliberDto"

STATUS_VALUES = {"PENDING-VALIDATION", "VALIDATED-PARTIAL", "VALIDATED-OBSERVED", "STALE"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATA_CLASS_RE = re.compile(r"data\s+class\s+(\w+)\s*\(", re.S)
_SERIAL_NAME_RE = re.compile(r'@SerialName\("([^"]+)"\)')
_VAL_RE = re.compile(r"\bval\s+(\w+)\s*:")


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
    """Kotlin 源码 -> {DTO 名: (允许键集, 必填键集)}。纯函数。

    必填 = 参数没有 `=` 默认值。这正是严格解析下"少了就抛"的那一批。
    """
    out = {}
    for m in _DATA_CLASS_RE.finditer(kotlin_src):
        name = m.group(1)
        i, depth = m.end() - 1, 0
        for j in range(m.end() - 1, len(kotlin_src)):
            if kotlin_src[j] == "(":
                depth += 1
            elif kotlin_src[j] == ")":
                depth -= 1
                if depth == 0:
                    i = j
                    break
        body = kotlin_src[m.end():i]
        allowed, required = set(), set()
        for part in _split_top_level(body):
            vm = _VAL_RE.search(part)
            if not vm:
                continue
            sm = _SERIAL_NAME_RE.search(part)
            key = sm.group(1) if sm else vm.group(1)
            allowed.add(key)
            if "=" not in part.split(":", 1)[-1]:
                required.add(key)
        if allowed:
            out[name] = (allowed, required)
    return out


def _check_keys(app, where, obj, dto_name, dtos, v):
    """未知键 / 缺必填键——两条都按 DTO 派生的集合判。"""
    if dto_name not in dtos:
        v.append("[%s] A2: DTO %s not found in AdapterSpec.kt — cannot derive the key set; "
                 "the guard refuses to pass rather than pass vacuously" % (app, dto_name))
        return
    allowed, required = dtos[dto_name]
    for k in sorted(set(obj) - allowed):
        v.append("[%s] A1: %s has key '%s' that %s does not declare — the app parses this file "
                 "with a strict Json, so an unknown key throws and the fail-safe returns an EMPTY "
                 "spec list: every app silently drops to generic and adapter_obs stops persisting "
                 "(D-54). Add the field to the DTO first, then to this file." % (app, where, k, dto_name))
    for k in sorted(required - set(obj)):
        v.append("[%s] A2: %s is missing required key '%s' (%s declares it with no default)"
                 % (app, where, k, dto_name))


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


def check_one(app, doc, dtos):
    """单份规格 -> 违规串列表。纯函数，无 IO。"""
    v = []
    _check_keys(app, "root", doc, DTO_OF_ROOT, dtos, v)
    adapter = doc.get("adapter")
    if not isinstance(adapter, dict):
        v.append("[%s] A2: 'adapter' must be an object" % app)
        return v
    _check_keys(app, "adapter", adapter, DTO_OF_ADAPTER, dtos, v)
    for key, dto in (("input_node", DTO_OF_NODE), ("response_node", DTO_OF_NODE),
                     ("send_button", DTO_OF_SEND), ("caliber_redlines", DTO_OF_CALIBER)):
        sub = adapter.get(key)
        if isinstance(sub, dict):
            _check_keys(app, "adapter.%s" % key, sub, dto, dtos, v)
    kpis = adapter.get("kpi_mapping")
    if isinstance(kpis, dict):
        for kname, kobj in sorted(kpis.items()):
            if isinstance(kobj, dict):
                _check_keys(app, "adapter.kpi_mapping.%s" % kname, kobj, DTO_OF_KPI, dtos, v)

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


def main():
    if not os.path.isfile(KOTLIN_DTO):
        print("cannot read the DTO source at %s — refusing to validate against a hand-written "
              "key list" % KOTLIN_DTO)
        return 1
    with open(KOTLIN_DTO, encoding="utf-8") as fh:
        dtos = parse_dtos(fh.read())
    if DTO_OF_ADAPTER not in dtos:
        print("parsed %d DTO(s) from AdapterSpec.kt but not %s — the derivation broke; refusing "
              "to pass" % (len(dtos), DTO_OF_ADAPTER))
        return 1

    names = sorted(f for f in os.listdir(HERE) if f.endswith(".json"))
    if not names:
        print("no adapter specs found in %s" % HERE)
        return 1

    violations = []
    for name in names:
        path = os.path.join(HERE, name)
        with open(path, "rb") as fh:
            raw = fh.read()
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            violations.append("[%s] parse error: %s" % (name, exc))
            continue
        violations += check_one(name, doc, dtos)
        violations += check_mirror(name, raw, os.path.join(ASSETS_DIR, name))

    print("Checked %d adapter spec(s): %s" % (len(names), ", ".join(names)))
    print("  key sets derived from %s (%d DTOs)" % (os.path.basename(KOTLIN_DTO), len(dtos)))
    if violations:
        print("VIOLATIONS: %d" % len(violations))
        for item in violations:
            print("  - %s" % item)
        return 1
    print("OK: all adapter-spec invariants hold (A1 no key the strict parser would reject, "
          "A2 required keys present, A3 assets mirror byte-identical, R21 version stamp "
          "complete-if-present, R22 status recognised).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
