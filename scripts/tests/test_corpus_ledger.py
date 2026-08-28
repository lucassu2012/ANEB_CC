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
