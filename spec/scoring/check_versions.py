# -*- coding: utf-8 -*-
"""AQS 版本登记守卫（SPEC-4 · 4.1；照 spec/portraits/check_redline.py 的 spec-lane 自守卫先例）。

机器强制「新增评分口径必须先在 VERSIONS.md 登记」——形态承 D-248 常量归档 +
app 单测侧 AqsScorerVoiceTest.kt:182「语音版本→权重表映射须覆盖全部版本」，从「仅语音」推广到全口径。

单一事实源 = spec/scoring/weights.yaml 的 version_id（已由 SpecScoringParityTest 与 AqsScorer.kt 对拍）。
本守卫做**双向咬合**（照 portraits R1/R19c 纪律）：weights 的每个 version_id 必须在 VERSIONS.md §1 表格登记，
反之表格登记的每个 version_id 必须在 weights 真实存在。任一方向不齐即 FAIL。

刻意用 stdlib re 而非 pyyaml：只需取 version_id 字面量与表格行首单元格，无需解析嵌套结构，
少一个依赖（campaign_common stdlib-only 同源纪律）。纯函数可单测（test_check_versions.py），IO 留在 main()。

Run:  python spec/scoring/check_versions.py
Exit: 0 = 双向一致；1 = 登记不齐；2 = harness error（文件读不到）。
"""
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEIGHTS = HERE / "weights.yaml"
VERSIONS = HERE / "VERSIONS.md"

# weights.yaml 里每张权重表的 `    version_id: "aqs-…"`（8 张表 → 7 个去重 id，token MM/TXT 共戳）。
_WEIGHTS_VID = re.compile(r'version_id:\s*"([^"]+)"')
# VERSIONS.md §1 的表格**数据行行首单元格**：`| `aqs-v0.1` | …`。
# 只取行首单元格，不取正文里对 version_id 的提及——「正文提到过」不等于「登记了」。
_REGISTERED_VID = re.compile(r"^\s*\|\s*`(aqs-[a-z0-9.\-]+)`\s*\|")
# weights.yaml `tables:` 下每张权重表的键（2 空格缩进、全大写）：`  WEIGHTS:` / `  WEIGHTS_V02:` …
# 8 张表键 vs 7 个 version_id——同 id 下的两张表（token MM/TXT）在 version_id 层不可分，
# 故 #8 守卫**在表键层**咬合：VERSIONS.md §1 col-2 逐字列了全部 8 张表键（`WEIGHTS`…），
# 每张表键都必须在册，否则「同 version_id 下新增一张表」会绕过 version_id 层的登记检查（D-audit #8）。
_TABLE_KEY = re.compile(r"^  ([A-Z][A-Z0-9_]*):\s*$", re.M)
# #3（D-audit）：某张表的权重值行 `      KPI: 0.20`（6 空格缩进）。用于给每张表的**值集**算指纹，
# 冻结「已发布表只增不改」的**不改**方向——check_versions 原本只比 version_id 集，改值不换 id 即绿。
_WEIGHT_LINE = re.compile(r"^      ([A-Za-z][A-Za-z0-9_]*):\s*([0-9][0-9.]*)\s*$")


def weights_version_ids(weights_text):
    """weights.yaml 里全部 version_id 的去重集合（单一事实源）。"""
    return set(_WEIGHTS_VID.findall(weights_text))


def registered_version_ids(versions_text):
    """VERSIONS.md §1 表格登记的 version_id 集合（只认表格行首单元格）。"""
    out = set()
    for line in versions_text.splitlines():
        m = _REGISTERED_VID.match(line)
        if m:
            out.add(m.group(1))
    return out


def weights_table_keys(weights_text):
    """weights.yaml `tables:` 下全部权重表键的集合（8 张：WEIGHTS…WEIGHTS_VOICE_SIM_V02）。"""
    return set(_TABLE_KEY.findall(weights_text))


def table_value_hashes(weights_text):
    """{表键: 该表权重值集的 sha256 指纹}——用于冻结「已发布表值不改」（#3）。

    指纹取该表 `weights:` 下全部 `KPI: value` 行、按 KPI 名排序后哈希（顺序无关）。
    改任一权重值即改指纹；金标存于 test_check_versions.py `_FROZEN_VALUE_HASHES`（同 _EXPECTED_IDS 先例），
    由 spec-versions-unit 每跑对拍——改已发布值而不新建表+新 id 即 RED。
    """
    out, cur, acc = {}, None, {}
    for line in weights_text.splitlines():
        mk = _TABLE_KEY.match(line)
        if mk:
            if cur is not None:
                out[cur] = _hash_weights(acc)
            cur, acc = mk.group(1), {}
            continue
        mw = _WEIGHT_LINE.match(line)
        if mw and cur is not None:
            acc[mw.group(1)] = mw.group(2)
    if cur is not None:
        out[cur] = _hash_weights(acc)
    return out


def _hash_weights(acc):
    payload = ";".join("%s=%s" % (k, acc[k]) for k in sorted(acc))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def check(weights_text, versions_text):
    """返回问题列表；空列表 = 双向一致。纯函数，不做 IO。"""
    w = weights_version_ids(weights_text)
    r = registered_version_ids(versions_text)
    problems = []
    for vid in sorted(w - r):
        problems.append(
            "weights.yaml 有 version_id `%s`，但 VERSIONS.md §1 未登记"
            " —— 新增评分口径必须先在本表登记（SPEC-4/4.1 守卫）" % vid)
    for vid in sorted(r - w):
        problems.append(
            "VERSIONS.md §1 登记了 `%s`，但 weights.yaml 查无此 version_id"
            " —— 版本号写错或登记了不存在的口径" % vid)
    # #8（D-audit）：表键层咬合——每张 weights.yaml 权重表键都必须在 VERSIONS.md 以 `键` 登记。
    # 反引号定界确保精确匹配（`WEIGHTS` 不会误配 `WEIGHTS_V02`），堵「同 version_id 下新增表绕过登记」。
    for key in sorted(weights_table_keys(weights_text)):
        if ("`%s`" % key) not in versions_text:
            problems.append(
                "weights.yaml 有权重表 `%s`，但 VERSIONS.md 未登记该表键"
                " —— 同 version_id 下新增的表也必须在 §1 登记（SPEC-4/4.1 守卫 #8）" % key)
    return problems


def main():
    try:
        weights_text = WEIGHTS.read_text(encoding="utf-8")
        versions_text = VERSIONS.read_text(encoding="utf-8")
    except OSError as e:
        print("ERROR: 读不到 spec/scoring 文件: %s" % e)
        return 2
    if "--freeze" in sys.argv:
        # 打印当前权重值指纹（#3 金标），供 test_check_versions.py `_FROZEN_VALUE_HASHES` 更新——
        # 仅在**合法新增/改版**（新表+新 version_id）时同批重生成并粘贴，改已发布表的值绝不 --freeze。
        h = table_value_hashes(weights_text)
        print("_FROZEN_VALUE_HASHES = {")
        for k in sorted(h):
            print('    "%s": "%s",' % (k, h[k]))
        print("}")
        return 0
    problems = check(weights_text, versions_text)
    if problems:
        for p in problems:
            print("FAIL:", p)
        print("\n%d 处登记不齐。VERSIONS.md §1 必须登记 weights.yaml 的每个 version_id，反之亦然。"
              % len(problems))
        return 1
    ids = sorted(weights_version_ids(weights_text))
    ntab = len(weights_table_keys(weights_text))
    print("OK: %d 个 aqs version_id / %d 张权重表全部登记且双向一致: %s"
          % (len(ids), ntab, ", ".join(ids)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
