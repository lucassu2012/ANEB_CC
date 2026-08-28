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
    check, weights_version_ids, registered_version_ids, WEIGHTS, VERSIONS,
)

# 采集时（2026-08-29）weights.yaml 的七个 version_id——GREEN 基线，也是「漏一个就红」的锚。
_EXPECTED_IDS = {
    "aqs-v0.1", "aqs-v0.2", "aqs-token-v0.1",
    "aqs-voice-v0.1", "aqs-voice-v0.2",
    "aqs-voice-sim-v0.1", "aqs-voice-sim-v0.2",
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
