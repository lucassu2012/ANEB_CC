#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二轮：把第一轮靠「违规数=0」推断出来的几条，换一种够得到的量法直接量（D-394 规矩 c）。

第一轮有两处是我自己的突变设计坏了（F5b 把唯一的 isNotEmpty 换掉 → 触发的是
「派生坏了」那道自守卫，不是它要测的「静默不覆盖」），本轮重做并如实标注。
"""
import copy
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

ANCHOR = '        @SerialName("caliber_redlines") val caliberRedlines: CaliberDto,'
BASE_ALLOWED = va.parse_dtos(KOTLIN)[va.DTO_OF_ADAPTER]["allowed"]
BASE_REQUIRED = va.parse_dtos(KOTLIN)[va.DTO_OF_ADAPTER]["required"]
print("baseline AdapterDto: allowed=%d required=%d" % (len(BASE_ALLOWED), len(BASE_REQUIRED)))


def add(line):
    return KOTLIN.replace(ANCHOR, ANCHOR + "\n" + line)


def probe(tag, src, keys):
    """直接量派生出的键集，而不是从违规数倒推。"""
    dtos = va.parse_dtos(src)
    a = dtos.get(va.DTO_OF_ADAPTER, {})
    allowed, required = a.get("allowed", set()), a.get("required", set())
    print("-" * 74)
    print("[%s] DTO 名单=%s" % (tag, sorted(dtos)))
    print("   allowed 总数=%d (baseline %d)  required 总数=%d (baseline %d)"
          % (len(allowed), len(BASE_ALLOWED), len(required), len(BASE_REQUIRED)))
    for k in keys:
        print("   key %-28r in allowed=%-5s in required=%-5s"
              % (k, k in allowed, k in required))
    lost = sorted(BASE_ALLOWED - allowed)
    if lost:
        print("   !! 基线里有、突变后消失的键: %s" % lost)
    return allowed, required


def viol(tag, src, doc):
    dtos = va.parse_dtos(src)
    contract = va.parse_loader_contract(src)
    v = va.check_one("doubao.json", doc, dtos, contract)
    print("   -> check_one 违规 %d 条: %s" % (len(v), [x.split("] ", 1)[-1][:70] for x in v]))
    return v


print("\n########## F2：默认值字符串里的特殊字符 ##########")
for tag, poison in (("F2a //", 'http://x'), ("F2b )", 'a)b'), ("F2c >", 'a>b')):
    src = add('        @SerialName("u") val u: String = "%s",\n'
              '        @SerialName("after") val after: String,' % poison)
    probe(tag, src, ["u", "after"])
    viol(tag, src, copy.deepcopy(GOOD))

print("\n########## F3：var 代替 val（两个方向） ##########")
src_var = add('        @SerialName("mut") var mut: String,')
probe("F3", src_var, ["mut"])
print("   方向①：JSON **写了** mut（App 会接受）")
viol("F3-has", src_var, dict(GOOD, adapter=dict(GOOD["adapter"], mut="x")))
print("   方向②：JSON **没写** mut，而 DTO 里它无默认值（App 严格解析必抛）")
viol("F3-missing", src_var, copy.deepcopy(GOOD))

print("\n########## F4：注解里带冒号 ##########")
src_dep = add('        @Deprecated("a:b", level = DeprecationLevel.WARNING)\n'
              '        @SerialName("dep") val dep: String,')
probe("F4", src_dep, ["dep"])
viol("F4-missing", src_dep, copy.deepcopy(GOOD))
print("   对照：同一字段**不带**那个注解时")
src_nodep = add('        @SerialName("dep") val dep: String,')
probe("F4-control", src_nodep, ["dep"])
viol("F4-control", src_nodep, copy.deepcopy(GOOD))

print("\n########## F5a：删一条 require —— 先证明基线**逮得住**它 ##########")
blank_id = copy.deepcopy(GOOD)
blank_id["adapter"]["id"] = "  "
print("   控制组（未突变 Kotlin + 空白 id）:")
viol("F5a-control", KOTLIN, blank_id)
print("   突变组（删掉 require(a.id.isNotBlank())）:")
src_noreq = KOTLIN.replace('        require(a.id.isNotBlank()) { "adapter.id blank" }\n', '')
assert src_noreq != KOTLIN
print("   派生出的 non_blank=%s" % va.parse_loader_contract(src_noreq)["non_blank"])
viol("F5a-mutant", src_noreq, blank_id)

print("\n########## F5b（重做）：**新增**一条形状不同的 require，保留原有的 ##########")
src_add_req = KOTLIN.replace(
    '        require(a.observeEvents.isNotEmpty()) { "observe_events empty" }',
    '        require(a.observeEvents.isNotEmpty()) { "observe_events empty" }\n'
    '        require(a.observeEvents.size >= 99) { "observe_events too few" }')
assert src_add_req != KOTLIN
c = va.parse_loader_contract(src_add_req)
print("   派生出的判据: non_blank=%s non_empty=%s kpi=%s" % (c["non_blank"], c["non_empty"], c["kpi_required"]))
print("   真语料 observe_events 长度=%d（< 99，即 App 上必抛）" % len(GOOD["adapter"]["observe_events"]))
viol("F5b-redo", src_add_req, copy.deepcopy(GOOD))

print("\n########## F1a 复量：PlainNest 到底在不在 dtos 名单里 ##########")
src_plain = (add('        @SerialName("nest") val nest: PlainNest? = null,')
             + '\n@Serializable\nclass PlainNest(\n    @SerialName("aa") val aa: String,\n)\n')
d = va.parse_dtos(src_plain)
print("   dtos 名单=%s   PlainNest in dtos = %s" % (sorted(d), "PlainNest" in d))
print("   nest 的声明类型 = %r" % d[va.DTO_OF_ADAPTER]["types"].get("nest"))

print("\n########## 「refuses to pass vacuously」四处行号核对 ##########")
with open(os.path.join(SPEC, "validate_adapters.py"), encoding="utf-8") as fh:
    lines = fh.read().splitlines()
for n in (187, 259, 280, 292):
    print("   :%d  %s" % (n, lines[n - 1].strip()[:100]))
