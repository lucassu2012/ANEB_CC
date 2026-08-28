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
    return problems


def main():
    try:
        weights_text = WEIGHTS.read_text(encoding="utf-8")
        versions_text = VERSIONS.read_text(encoding="utf-8")
    except OSError as e:
        print("ERROR: 读不到 spec/scoring 文件: %s" % e)
        return 2
    problems = check(weights_text, versions_text)
    if problems:
        for p in problems:
            print("FAIL:", p)
        print("\n%d 处登记不齐。VERSIONS.md §1 必须登记 weights.yaml 的每个 version_id，反之亦然。"
              % len(problems))
        return 1
    ids = sorted(weights_version_ids(weights_text))
    print("OK: %d 个 aqs version_id 全部登记且双向一致: %s" % (len(ids), ", ".join(ids)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
