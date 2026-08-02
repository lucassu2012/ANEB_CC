# -*- coding: utf-8 -*-
"""`split_by_run_mode.py` 反例测试。

三条不变量各配一对"违规夹具"（断言被捉）+"合规夹具"（断言放行）：
mode 缺失行拒绝、quick+forensic+rejected 行数守恒、未知 mode 值的处置。
另加一条端到端 CLI 往返，catch 纯函数测试摸不到的 argparse/文件 I/O 层问题
（同 test_cli_smoke.py 的立场——函数对不等于 CLI 对）。
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)

import split_by_run_mode as sbm  # noqa: E402
from synth import make_record  # noqa: E402


def _with_mode(mode_value, drop_key=False):
    """make_record() 默认 mode="quick"；这里按需改写或整个删掉这个键。"""
    rec = make_record()
    if drop_key:
        del rec["run"]["mode"]
    else:
        rec["run"]["mode"] = mode_value
    return rec


# ── mode 缺失行拒绝 ─────────────────────────────────────────────────────────
def test_missing_mode_key_is_rejected_not_silently_dropped():
    """违规夹具：run.mode 键整个不存在（契约必填字段缺失）。"""
    rec = _with_mode(None, drop_key=True)
    quick, forensic, rejected = sbm.split_records([rec])
    assert quick == [] and forensic == []
    assert len(rejected) == 1 and rejected[0]["reason"] == "missing_mode"


def test_empty_string_mode_is_treated_as_missing_not_unknown():
    """空字符串等价于"没写"——都不能被计入任一 mode 的样本量。"""
    rec = _with_mode("")
    _q, _f, rejected = sbm.split_records([rec])
    assert rejected[0]["reason"] == "missing_mode"


def test_a_valid_quick_record_is_not_rejected():
    """合规夹具：mode="quick" 的记录必须放行进 quick 桶，不进 rejected。"""
    rec = _with_mode(sbm.MODE_QUICK)
    quick, forensic, rejected = sbm.split_records([rec])
    assert quick == [rec] and forensic == [] and rejected == []


# ── 行数守恒 ─────────────────────────────────────────────────────────────
def test_quick_forensic_rejected_counts_conserve_the_input_row_count():
    """混合批次：quick + forensic + rejected 的行数之和必须严格等于输入行数——
    差一行都意味着某条记录被吞了，而不是被三个桶之一如实收留。
    """
    records = (
        [_with_mode(sbm.MODE_QUICK) for _ in range(3)]
        + [_with_mode(sbm.MODE_FORENSIC) for _ in range(2)]
        + [_with_mode(None, drop_key=True)]
        + [_with_mode("chaos")]
    )
    quick, forensic, rejected = sbm.split_records(records)
    assert len(quick) == 3 and len(forensic) == 2 and len(rejected) == 2
    assert len(quick) + len(forensic) + len(rejected) == len(records)


def test_conservation_holds_for_an_all_rejected_batch():
    """边界情形：全批次都不合规时，守恒式仍要成立（不是只在"正常"批次里凑巧对）。"""
    records = [_with_mode(None, drop_key=True), _with_mode("bogus"), _with_mode("")]
    quick, forensic, rejected = sbm.split_records(records)
    assert quick == [] and forensic == []
    assert len(rejected) == len(records)


# ── 非 quick/forensic 的 mode 值的处置 ───────────────────────────────────
def test_other_mode_value_is_rejected_and_the_value_is_recorded():
    """违规夹具：mode 是一个真实字符串，但既不是 quick 也不是 forensic——
    本工具不判断它是不是"错的"，只如实落进 rejected 且原始值留痕以便排查。
    """
    rec = _with_mode("chaos")
    quick, forensic, rejected = sbm.split_records([rec])
    assert quick == [] and forensic == []
    assert rejected[0]["reason"] == "other_mode"
    assert rejected[0]["mode"] == "chaos"


def test_continuity_and_ab_modes_are_other_mode_not_a_data_error():
    """`MainActivity.kt:78` 的 adb 自动化注释显示 mode 实际支持
    quick|forensic|continuity|ab 四个合法值，schema 描述只写了前两个——
    continuity/ab 落进 rejected 是**正确行为**（不该被这个工具悄悄并进
    quick 或 forensic），不是"未知/错误值"，reason 桶名不能暗示它们是坏数据。
    """
    for real_mode in ("continuity", "ab"):
        rec = _with_mode(real_mode)
        quick, forensic, rejected = sbm.split_records([rec])
        assert quick == [] and forensic == []
        assert rejected[0]["reason"] == "other_mode"
        assert rejected[0]["mode"] == real_mode


def test_case_mismatch_is_other_mode_not_silently_normalized():
    """不做大小写归一——"Quick" 不等于 "quick"，猜测归类比拒绝更危险。"""
    rec = _with_mode("Quick")
    _q, _f, rejected = sbm.split_records([rec])
    assert rejected[0]["reason"] == "other_mode"


def test_non_string_mode_is_other_mode_not_a_crash():
    """mode 字段若被写成非字符串（如数字），不能让分类逻辑抛异常——
    如实归入 other_mode，原始值原样带出供排查。
    """
    rec = _with_mode(0)
    _q, _f, rejected = sbm.split_records([rec])
    assert rejected[0]["reason"] == "other_mode" and rejected[0]["mode"] == 0


def test_a_valid_forensic_record_is_not_rejected():
    """合规夹具：mode="forensic" 同样必须放行，不是只有 quick 才被正确处理。"""
    rec = _with_mode(sbm.MODE_FORENSIC)
    quick, forensic, rejected = sbm.split_records([rec])
    assert forensic == [rec] and quick == [] and rejected == []


# ── 端到端 CLI 往返（catch 纯函数测试摸不到的 I/O 层问题）───────────────────
def test_cli_round_trip_writes_two_files_with_the_right_counts():
    d = tempfile.mkdtemp(prefix="split_by_run_mode_")
    try:
        records = (
            [_with_mode(sbm.MODE_QUICK) for _ in range(2)]
            + [_with_mode(sbm.MODE_FORENSIC)]
            + [_with_mode(None, drop_key=True)]
        )
        src = os.path.join(d, "in.jsonl")
        with open(src, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        quick_out = os.path.join(d, "q.jsonl")
        forensic_out = os.path.join(d, "f.jsonl")
        rc = sbm.main([src, "--quick-out", quick_out, "--forensic-out", forensic_out])
        assert rc == 0
        with open(quick_out, encoding="utf-8") as fh:
            assert len(fh.readlines()) == 2
        with open(forensic_out, encoding="utf-8") as fh:
            assert len(fh.readlines()) == 1
        # 写出的每一行必须仍是可解析、语义不变的 JSON——不是"行数对了但内容坏了"。
        with open(quick_out, encoding="utf-8") as fh:
            for line in fh:
                assert json.loads(line)["run"]["mode"] == sbm.MODE_QUICK
    finally:
        for name in ("in.jsonl", "q.jsonl", "f.jsonl"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                os.remove(p)
        os.rmdir(d)


def test_cli_default_output_paths_are_derived_from_the_input_stem():
    """不给 --quick-out/--forensic-out 时，默认路径要能从输入文件名猜出来——
    这条如果漂了，操作者按文档默认名去找输出文件会找不到。
    """
    d = tempfile.mkdtemp(prefix="split_by_run_mode_default_")
    try:
        src = os.path.join(d, "batch.jsonl")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(_with_mode(sbm.MODE_QUICK), ensure_ascii=False) + "\n")
        rc = sbm.main([src])
        assert rc == 0
        assert os.path.exists(os.path.join(d, "batch_quick.jsonl"))
        assert os.path.exists(os.path.join(d, "batch_forensic.jsonl"))
    finally:
        for name in ("batch.jsonl", "batch_quick.jsonl", "batch_forensic.jsonl"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                os.remove(p)
        os.rmdir(d)
