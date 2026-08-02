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

import pytest

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


# ── run 键本身缺失/为 null（v2 T21③ 复核提出，此前零反例）─────────────────
def test_run_key_entirely_missing_is_missing_mode_not_a_crash():
    """违规夹具：记录里连 `run` 这个键都不存在（不是 run.mode 缺，是 run 本身缺）。

    `cc.run_obj(rec)` = `rec.get("run") or {}`——这条防线此前只被"读代码"
    信任过，从未被反例证明过。
    """
    rec = make_record()
    del rec["run"]
    quick, forensic, rejected = sbm.split_records([rec])
    assert quick == [] and forensic == []
    assert rejected[0]["reason"] == "missing_mode"


def test_run_explicit_null_is_missing_mode_not_a_crash():
    """违规夹具：`run` 键存在但值是 JSON null（`rec.get("run")` 返回 None，
    `or {}` 兜底）——与"键不存在"是不同的输入形状，必须分别有反例。
    """
    rec = make_record()
    rec["run"] = None
    quick, forensic, rejected = sbm.split_records([rec])
    assert quick == [] and forensic == []
    assert rejected[0]["reason"] == "missing_mode"


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


# ── 大脑核验揪出的两条真缺陷（对抗核验批）──────────────────────────────────
def test_unreadable_input_path_exits_nonzero_not_two_silent_empty_files():
    """违规夹具：输入路径打错（文件不存在，且不是 glob 通配）。

    修前的形状：`campaign_common.load_records()` 把字面路径先 append 进
    `files`、再尝试 open——open 失败被计入 `unreadable_files`+打印到
    stderr，但从不抛异常。旧版 `main()` 只检查 `if not files`，对这种
    情况永远为 False（`files` 里明明有那个打不开的路径），于是继续往下跑：
    `records=[]` → `split_records([])` 三个空列表 → 写出两个空文件 →
    打印"input records: 0"这条听起来完全正常的汇总——退出码还是 0
    （D-328/D-330 形状：loader 算出的信号，没有一个消费方在读）。
    """
    d = tempfile.mkdtemp(prefix="split_by_run_mode_badpath_")
    try:
        bad_path = os.path.join(d, "does_not_exist.jsonl")
        quick_out = os.path.join(d, "q.jsonl")
        forensic_out = os.path.join(d, "f.jsonl")
        with pytest.raises(SystemExit):
            sbm.main([bad_path, "--quick-out", quick_out, "--forensic-out", forensic_out])
        # 修复后必须整个拒绝——不能把"打不开"悄悄处理成"两个空子集"。
        assert not os.path.exists(quick_out)
        assert not os.path.exists(forensic_out)
    finally:
        for name in ("q.jsonl", "f.jsonl"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                os.remove(p)
        os.rmdir(d)


def test_same_quick_and_forensic_output_path_is_rejected():
    """违规夹具：`--quick-out` 与 `--forensic-out` 指向同一个文件——
    后写的会静默覆盖先写的，而汇总行仍会对两个路径各自报告"写了 N 条"，
    对文件系统的实际状态做了不实陈述。
    """
    d = tempfile.mkdtemp(prefix="split_by_run_mode_samepath_")
    try:
        src = os.path.join(d, "in.jsonl")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(_with_mode(sbm.MODE_QUICK), ensure_ascii=False) + "\n")
        same = os.path.join(d, "same.jsonl")
        with pytest.raises(SystemExit):
            sbm.main([src, "--quick-out", same, "--forensic-out", same])
    finally:
        for name in ("in.jsonl", "same.jsonl"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                os.remove(p)
        os.rmdir(d)


def test_output_path_pointing_back_at_the_input_is_rejected():
    """违规夹具：`--quick-out`/`--forensic-out` 指回输入文件本身——
    这会在读完之前就地覆盖输入（视写入时机而定，属于最危险的一种同路径碰撞）。
    """
    d = tempfile.mkdtemp(prefix="split_by_run_mode_selfpath_")
    try:
        src = os.path.join(d, "in.jsonl")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(_with_mode(sbm.MODE_QUICK), ensure_ascii=False) + "\n")
        other_out = os.path.join(d, "f.jsonl")
        with pytest.raises(SystemExit):
            sbm.main([src, "--quick-out", src, "--forensic-out", other_out])
    finally:
        for name in ("in.jsonl", "f.jsonl"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                os.remove(p)
        os.rmdir(d)
