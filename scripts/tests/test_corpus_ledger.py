# -*- coding: utf-8 -*-
"""语料台账守卫（SPEC-3 §3.1 / T81）。

钉四件事：①与 campaign_report 清点行的对拍（任务书点名的那条）；
②合成语料单列绝不混入真实总数；③跨文件重复不虚增；④运营商全称别名
归一（台账首算咬出的 D-149 拆格实例）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import campaign_common as cc
import campaign_report as rpt
import corpus_ledger as cl
import synth_campaign as sc
from synth import make_record

_T46 = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "evidence",
    "t46_full_corpus_analysis_20260804", "full_corpus_labelled.jsonl")


def test_ledger_matches_campaign_report_head_count_on_the_same_corpus():
    """任务书点名的对拍：台账真实 run 数 == 报告清点行「输入记录：N」的 N。

    两面共用 cc.load_records，但台账在其上再做合成拆分与自己的计数——
    这条钉的是「台账没有偷偷加第二层过滤」。语料=t46 全量（73 run 基线族）。
    """
    if not os.path.exists(_T46):
        import pytest
        pytest.skip("t46 corpus not present in this checkout")
    real, synth, _ = cl.summarize([_T46])
    inv = rpt.inventory(cc.load_records([_T46])[0])
    assert len(real) == inv["records"] == 73
    assert synth == []                       # t46 是纯真实语料


def test_synthetic_records_never_enter_the_real_total():
    """混入整份合成战役语料 ⇒ 真实总数纹丝不动、合成侧全额单列。

    反例证伪：summarize 里去掉 is_synthetic 拆分，本条即红。
    """
    synth_recs = sc.generate(points=2, repeats=2, campaigns=("base",),
                             radio=False)
    real_recs = [make_record(aqs=80, started_ms=1783944000000 + i * 90_000,
                             campaign={"campaign_id": "field", "tier": "metro",
                                       "point_id": "P1", "carrier": "ctcc",
                                       "time_band": "busy"},
                             scenarios=[("s1_chat", {})], run_id=f"real-{i:04d}")
                 for i in range(5)]
    import json
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "mixed.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            for r in real_recs + synth_recs:
                f.write(json.dumps(r) + "\n")
        real, synth, _ = cl.summarize([p])
    assert len(real) == 5
    assert len(synth) == len(synth_recs)


def test_duplicate_files_do_not_inflate_the_total():
    """同一文件喂两遍 ⇒ 总数不变（run_id 去重，cc.load_records 语义）。"""
    if not os.path.exists(_T46):
        import pytest
        pytest.skip("t46 corpus not present in this checkout")
    once, _, _ = cl.summarize([_T46])
    twice, _, st = cl.summarize([_T46, _T46])
    assert len(twice) == len(once)
    assert st["duplicates"] >= len(once)     # 第二遍整份被去


def test_full_width_carrier_name_buckets_with_its_short_alias():
    """「中国电信」与 ctcc 必须落同一桶——实采语料真实写法（acceptance
    十条 run），两字简称接不住四字全称时跨语料视图拆格（D-149 形状）。

    反例证伪：从 _CARRIER_ALIASES 删掉全称三条，本条即红。
    """
    recs = [make_record(aqs=80, started_ms=1783944000000,
                        campaign={"campaign_id": "c", "tier": "metro",
                                  "point_id": "P1", "carrier": car,
                                  "time_band": "busy"},
                        scenarios=[("s1_chat", {})], run_id=f"r-{i}")
            for i, car in enumerate(["ctcc", "中国电信", "中国移动", "中国联通"])]
    bk = cl.buckets(recs)
    assert bk["by"]["carrier"] == {"ctcc": 2, "cmcc": 1, "cucc": 1}


def test_md_face_carries_the_do_not_hand_edit_and_no_sum_rules():
    """产物头两条规则句必须在渲染面上：勿手编 + 两节不可相加。

    规则只活在生成器注释里等于没有——读者拿到的是 md（D-303 同理）。
    """
    real = [make_record(aqs=80, started_ms=1783944000000,
                        campaign={"campaign_id": "c", "tier": "metro",
                                  "point_id": "P1", "carrier": "ctcc",
                                  "time_band": "busy"},
                        scenarios=[("s1_chat", {})], run_id="r-0")]
    md = cl.render_md([("f.jsonl", 1, 1)], [], real, [], {"lines": 1},
                      cl.buckets(real), [])
    assert "勿手编" in md
    assert "不可相加" in md
    assert "进展」声明必须引用本台账" in md


# ---- 审计续轮补的两条：零守卫函数里的「查不了被读成查过了」（T81 自审）----

def test_a_corrupt_corpus_file_is_not_reported_as_not_a_corpus():
    """坏行文件与「本来就不是语料」必须分开说。

    两者都装不出契约记录，合成一个桶就是把「查不了」印成「查过了，不是
    语料」——一份坏掉的语料文件会静静地被算成本来就不该计入。
    反例证伪：discover 回到 2 元组（不带失败计数），本条即红。
    """
    import io as _io
    import os as _os
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        _io.open(_os.path.join(d, "empty.jsonl"), "w").write("")
        _io.open(_os.path.join(d, "bad.jsonl"), "w",
                 encoding="utf-8").write("{broken\n")
        corpus, skipped = cl.discover(d)
    assert corpus == []
    by = {_os.path.basename(p): bad for p, _, bad in skipped}
    assert by["bad.jsonl"] > 0, "装载失败的文件必须带失败计数"
    assert by["empty.jsonl"] == 0, "空文件是真的不是语料，不该被说成坏了"
    md = cl.render_md([], skipped, [], [], {"lines": 1},
                      cl.buckets([]), [])
    assert "装载失败" in md and "不等于「不是语料」" in md
    assert "`" + "bad.jsonl" not in md.split("装载失败")[0], \
        "坏文件不该同时出现在「非语料」那句里"


def test_an_unreadable_db_says_so_instead_of_rendering_three_dashes():
    """损坏的库要报「读不了」，不能渲染成三个「—」冒充「表不存在」。

    sqlite3 对非法文件在 connect 不抛、在 execute 才抛，被逐表的内层 except
    吞成 None——docstring 承诺的「如实记读不了」曾因此落空（本条钉住它）。
    反例证伪：去掉 all(...) 那段兜底，本条即红。
    """
    import io as _io
    import os as _os
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        _io.open(_os.path.join(d, "broken.db"), "w").write("not a database")
        rows = cl.room_dbs(d)
    assert len(rows) == 1 and "error" in rows[0]
    md = cl.render_md([], [], [], [], {"lines": 0}, cl.buckets([]), rows)
    assert "读不了" in md


# ---- 范围边界与占位符（2026-08-29，v2 实证后扩）----

def test_the_ledger_scans_the_server_landing_dir_too():
    """服务端落盘也是真实测量的**另一个落点**，不是另一个数据面——只扫
    evidence 会把只存在于那里的 run 无声排除（实测过 1 条），而一个自称
    「单一事实源」的台账不该有无声排除。

    反例证伪：DEFAULT_ROOTS 收回单根，本条即红。
    """
    assert len(cl.DEFAULT_ROOTS) >= 2
    assert any("server" in r for r in cl.DEFAULT_ROOTS)
    import io as _io
    import json as _json
    import os as _os
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        a, b = _os.path.join(d, "ev"), _os.path.join(d, "srv")
        _os.makedirs(a), _os.makedirs(b)
        for root, rid in ((a, "in-evidence"), (b, "only-on-server")):
            rec = make_record(aqs=80, started_ms=1783944000000,
                              campaign={"campaign_id": "c", "tier": "metro",
                                        "point_id": "P1", "carrier": "ctcc",
                                        "time_band": "busy"},
                              scenarios=[("s1_chat", {})], run_id=rid)
            _io.open(_os.path.join(root, "x.jsonl"), "w",
                     encoding="utf-8").write(_json.dumps(rec) + "\n")
        corpus, _ = cl.discover([a, b])
        real, _, _ = cl.summarize([p for p, _, _ in corpus])
    assert {cc.run_obj(r)["run_id"] for r in real} == {"in-evidence",
                                                       "only-on-server"}


def test_a_placeholder_point_id_is_labelled_as_one():
    """`PENDING-…` 是「真名待回填」的占位符，不是一个真实站点——当普通点位
    计数会让读者把它读成覆盖里的一个站点（真实发生过一次跨会话对账考古）。

    反例证伪：去掉渲染面的标注，本条即红。
    """
    recs = [make_record(aqs=80, started_ms=1783944000000,
                        campaign={"campaign_id": "c", "tier": "metro",
                                  "point_id": pid, "carrier": "ctcc",
                                  "time_band": "busy"},
                        scenarios=[("s1_chat", {})], run_id="r-%d" % i)
            for i, pid in enumerate(["SZ-REAL-01", "PENDING-PO-01"])]
    md = cl.render_md([("f.jsonl", 2, 2)], [], recs, [], {"lines": 2},
                      cl.buckets(recs), [])
    assert "PENDING-PO-01 是占位符不是点位" in md
    assert "不可当作一个真实站点计入覆盖" in md
