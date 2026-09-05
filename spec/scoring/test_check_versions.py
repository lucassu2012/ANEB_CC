# -*- coding: utf-8 -*-
"""AQS 版本登记守卫的反例测试（SPEC-4 · 4.1；照 spec/portraits/test_check_redline.py 形态）。

每条不变量配 RED（必须被抓）+ GREEN（真实文件必须过）。守卫的守卫：未来若有人弱化判据，
对应 RED 测试变红。纯内存 fixture，不改真实文件、无设备、无 PO 依赖。
Run:  python -m pytest spec/scoring/test_check_versions.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # spec/scoring/

from check_versions import (  # noqa: E402
    check, weights_version_ids, registered_version_ids, weights_table_keys,
    table_value_hashes, WEIGHTS, VERSIONS,
)

# 采集时（2026-08-29）weights.yaml 的七个 version_id——GREEN 基线，也是「漏一个就红」的锚。
_EXPECTED_IDS = {
    "aqs-v0.1", "aqs-v0.2", "aqs-token-v0.1",
    "aqs-voice-v0.1", "aqs-voice-v0.2",
    "aqs-voice-sim-v0.1", "aqs-voice-sim-v0.2",
}

# #3（D-audit）权重值冻结金标——已发布表「只增不改」的**不改**方向（add-only §3）。
# 采集于 2026-08-29（`python check_versions.py --freeze` 生成）。改任一已发布权重值即改指纹 → 本文件 RED。
# **仅在合法新增表（新 version_id）时同批 `--freeze` 重生成**；改已发布表的值绝不更新此金标。
_FROZEN_VALUE_HASHES = {
    "WEIGHTS": "38d3b2249078fc0af34ccead6de212426ccec9da0ffd707e113ee471f75386e0",
    "WEIGHTS_TOKEN_MM": "69f3160a26e008e3772789f71486d89aa44f3540facb50a789f03a2348a90cd8",
    "WEIGHTS_TOKEN_TXT": "f2a38a94903419c347706ec5fbec77fda9a1bbc53cecf260deda2b9949ebb9cc",
    "WEIGHTS_V02": "6e472b95ef8530afc414991b929174d5327d2c0ca0829591189535cbe688fb9c",
    "WEIGHTS_VOICE": "f026357be4677da9370663c0909f201f893599ba648be0e07bfb382f8ee8b442",
    "WEIGHTS_VOICE_SIM": "960d812af8c65fdc8e7ef85304b1c360dd8a798164ef41691bd4c3844054ce6b",
    "WEIGHTS_VOICE_SIM_V02": "1f321255c29e1befb91e4039eee6222902f49317c62b325e507a9164bfdacec4",
    "WEIGHTS_VOICE_V02": "3ccbcab5b4b19edad1d664700668e219905e35c2fcee139f3dac1112bff8a5f0",
}


def _real_weights():
    return WEIGHTS.read_text(encoding="utf-8")


def _real_versions():
    return VERSIONS.read_text(encoding="utf-8")


# ── GREEN：真实两文件必须双向一致（等价 check_versions.py 退出 0）─────────────
def test_real_files_are_consistent():
    assert check(_real_weights(), _real_versions()) == []


def test_weights_extractor_finds_all_seven():
    # token MM/TXT 共 aqs-token-v0.1，去重后正好七个（八张表 → 七个 id）。
    assert weights_version_ids(_real_weights()) == _EXPECTED_IDS


def test_registered_extractor_matches_weights():
    assert registered_version_ids(_real_versions()) == _EXPECTED_IDS


# ── RED：weights 新增口径而 VERSIONS 未登记 → 必须被抓（本单要防的主形状）──────
def test_unregistered_new_version_is_caught():
    weights = _real_weights() + '\n  WEIGHTS_FAKE:\n    version_id: "aqs-fake-v9.9"\n'
    problems = check(weights, _real_versions())
    assert any("aqs-fake-v9.9" in p and "未登记" in p for p in problems), problems


# ── RED：VERSIONS 登记了 weights 没有的版本 → 必须被抓（版本号写错/列虚构口径）──
def test_stale_registration_is_caught():
    versions = _real_versions() + "\n| `aqs-ghost-v0.1` | 不存在 | 无 | 无 | 无 | 无 |\n"
    problems = check(_real_weights(), versions)
    assert any("aqs-ghost-v0.1" in p and "查无此" in p for p in problems), problems


# ── RED：正文提及 version_id 不算登记——判据只认表格行首单元格 ────────────────
def test_body_mention_does_not_count_as_registration():
    # 构造：weights 有 aqs-only-in-body-v0.1，VERSIONS 只在正文段落提它、不在表格登记。
    weights = _real_weights() + '\n  WEIGHTS_X:\n    version_id: "aqs-only-in-body-v0.1"\n'
    versions = _real_versions() + "\n正文里提到 `aqs-only-in-body-v0.1` 但没进 §1 表格。\n"
    problems = check(weights, versions)
    # 仍应报 missing——「提到过」≠「登记了」。
    assert any("aqs-only-in-body-v0.1" in p and "未登记" in p for p in problems), problems


# ── token 双表共版本戳：weights 里 aqs-token-v0.1 出现两次，去重为一 ───────────
def test_token_dual_table_shares_one_version_id():
    txt = _real_weights()
    assert txt.count('version_id: "aqs-token-v0.1"') == 2   # MM + TXT 两张表各一行
    assert "aqs-token-v0.1" in weights_version_ids(txt)     # 去重后仅一个 id


# ── #8 GREEN：真实 weights.yaml 恰八张表键，且全部在 VERSIONS.md 登记 ──────────
def test_table_key_extractor_finds_all_eight():
    keys = weights_table_keys(_real_weights())
    assert len(keys) == 8, keys
    assert "WEIGHTS" in keys and "WEIGHTS_VOICE_SIM_V02" in keys


# ── #8 RED：同 version_id 下新增一张表、未登记 §1 → version_id 检查放行、表键检查必抓 ──
def test_new_table_under_existing_version_id_is_caught():
    # WEIGHTS_TOKEN_EXTRA 复用已登记的 aqs-token-v0.1——version_id 集不变（id 层看不见），
    # 但表键未进 VERSIONS.md → #8 表键咬合必须报它（这正是 #8 补的、id 层漏掉的形状）。
    weights = _real_weights() + (
        '\n  WEIGHTS_TOKEN_EXTRA:\n    version_id: "aqs-token-v0.1"\n'
        '    weights:\n      T1: 1.0\n')
    problems = check(weights, _real_versions())
    assert any("WEIGHTS_TOKEN_EXTRA" in p and "未登记该表键" in p for p in problems), problems
    # 反证：它没有被误报成 version_id 问题（aqs-token-v0.1 本就在册）——证明抓它的确是 #8 表键层。
    assert not any("aqs-token-v0.1" in p for p in problems), problems


# ── #3 GREEN：真实 weights.yaml 权重值集与冻结金标逐表一致（改任一值即红）──────────
def test_published_weight_values_are_frozen():
    assert table_value_hashes(_real_weights()) == _FROZEN_VALUE_HASHES


# ── #3 RED：原地改一张已发布表的权重值 → 该表指纹变、其它表不变（不改方向被抓）──────
def test_inplace_weight_value_mutation_is_caught():
    mutated = _real_weights().replace("T1: 0.20", "T1: 0.99", 1)  # 改 WEIGHTS 的 T1（0.20 全仓唯此处）
    assert mutated != _real_weights(), "fixture 未改到——replace 目标串漂了，测试量法坏"
    h = table_value_hashes(mutated)
    assert h["WEIGHTS"] != _FROZEN_VALUE_HASHES["WEIGHTS"], "改了值却没改指纹 = 冻结失效"
    assert h["WEIGHTS_V02"] == _FROZEN_VALUE_HASHES["WEIGHTS_V02"]  # 按表隔离，不误伤其它表


if __name__ == "__main__":
    # Self-contained runner（照姊妹 spec/portraits/test_check_redline.py，D-569）：
    # verify_all/CI 直接 `python <file>` 即可跑，无需 pytest（本仓 Python 3.14 env 无 pytest）。
    # 关键：**必须打印跑了几条并按失败数非零退出**——否则 verify_all 照 portraits 形态
    # 用 `& $py <file>` 直跑一个纯 pytest 文件会「零测试恒 RC=0」= 永远绿的假门
    # （D-532 同形，gate-integrity 抓不到：python 在、不抛异常）。pytest 仍可正常收集 test_*。
    tests = {n: f for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)}
    failed = []
    for name, fn in tests.items():
        try:
            fn()
        except AssertionError as e:
            failed.append((name, "assertion failed: %s" % e))
        except Exception as e:  # noqa: BLE001 — 任何 harness 错误都当失败暴露
            failed.append((name, "%s: %s" % (type(e).__name__, e)))
    print("ran %d reflex tests: %d passed, %d failed"
          % (len(tests), len(tests) - len(failed), len(failed)))
    for name, why in failed:
        print("  FAIL", name, "-", why)
    sys.exit(1 if failed else 0)
