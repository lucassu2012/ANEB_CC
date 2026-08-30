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


def test_the_two_aqs_calibers_are_never_conflated():
    """「带 AQS」有两种数法：`run.aqs.score` 非空（真出了分）vs 顶层
    `aqs_version` 版本戳（有戳不等于出了分）。实测差 1 条——**同名不同义比
    不同名更危险**（D-326），故两个数同行并列且差额点名。

    反例证伪：只印一个数、或把版本戳数当成出分数，本条即红。
    """
    scored = make_record(aqs=80, started_ms=1783944000000,
                         campaign={"campaign_id": "c", "tier": "metro",
                                   "point_id": "P1", "carrier": "ctcc",
                                   "time_band": "busy"},
                         scenarios=[("s1_chat", {})], run_id="scored")
    versioned_only = make_record(started_ms=1783944000000,
                                 campaign={"campaign_id": "c", "tier": "metro",
                                           "point_id": "P1", "carrier": "ctcc",
                                           "time_band": "busy"},
                                 scenarios=[("s1_chat", {})], run_id="vonly")
    versioned_only["run"].pop("aqs", None)          # 有顶层版本戳、无分数
    recs = [scored, versioned_only]
    bk = cl.buckets(recs)
    assert bk["aqs_runs"] == 1 and bk["aqs_versioned"] == 2
    md = cl.render_md([("f.jsonl", 2, 2)], [], recs, [], {"lines": 2}, bk, [])
    assert "`run.aqs.score` 非空）：1" in md
    assert "版本戳共 2 条" in md
    assert "1 条只有版本戳、没有分数" in md


def _obs_dir(root, name, kind, pkg="com.x", experiments=("E2",)):
    """造一个观察通道采集目录：判据是 RUN_KIND.json，不是文件名。"""
    import io as _io
    import json as _json
    import os as _os
    d = _os.path.join(root, name)
    _os.makedirs(d)
    _io.open(_os.path.join(d, "RUN_KIND.json"), "w", encoding="utf-8").write(
        _json.dumps({"kind": kind, "pkg": pkg,
                     "experiments": list(experiments)}))
    # 观察通道的真实产物：它是 .jsonl，但装不出契约记录
    _io.open(_os.path.join(d, "screencap_index.jsonl"), "w",
             encoding="utf-8").write('{"t_ms":1,"roi_mean":12.5}\n')
    return d


def test_an_observation_run_is_counted_but_never_merged_into_real_runs():
    """一整个设备窗跑完，台账必须动一个数——但**不能是 real_runs**。

    此前观察通道产物只以 `screencap_index.jsonl` 的身份落进「跳过（非语料）」，
    与 README/配置挤在同一句措辞下：于是「进展单一事实源」在一个设备窗之后
    一个数都不动（D-332 无名桶）。同时它绝不可并入 wire 池——两条链口径不同。
    反例证伪：把 obs 计入 real_runs，或第四节不说「不可相加」，本条即红。
    """
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        _obs_dir(d, "cell_f1", "DEVICE_REAL")
        obs = cl.observation_runs([d])
        corpus, skipped = cl.discover(d)
    assert len(obs) == 1 and obs[0]["kind"] == "DEVICE_REAL"
    assert obs[0]["pkg"] == "com.x" and obs[0]["experiments"] == "E2"
    assert corpus == [], "观察通道产物不得被当成 wire 语料装进来"
    md = cl.render_md([], skipped, [], [], {"lines": 1}, cl.buckets([]), [], obs)
    assert "不可相加" in md and "0 条 wire run" in md
    assert "**1 个真机采集目录**" in md, "第一节必须在会被误加的那个数旁边示警"


def test_dry_run_observation_dirs_are_listed_but_never_counted_as_real():
    """dry-run 目录与真机目录**不能合成一个数**——同 `is_synthetic` 单列。

    这条钉的是我自己踩过的坑：初版印「13 个采集目录」，其中 6 个是 dry-run。
    修好一层就地再问一遍同类（D-341），否则新桶重犯旧桶的病。
    反例证伪：头条数或 CSV 出一个把两者相加的合计，本条即红。
    """
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        _obs_dir(d, "real_cell", "DEVICE_REAL")
        _obs_dir(d, "sim_cell", "DRY_RUN_SIMULATED")
        obs = cl.observation_runs([d])
    assert len(obs) == 2
    md = cl.render_md([], [], [], [], {"lines": 0}, cl.buckets([]), [], obs)
    assert "**1 个真机采集目录**" in md and "dry-run 1 个单列不计入" in md
    rows = {(f, k): v for f, k, v in cl.render_csv_rows([], [], cl.buckets([]), obs)}
    assert rows[("observation", "device_real_dirs")] == 1
    assert rows[("observation", "dry_run_dirs")] == 1
    assert not any(k == "run_dirs" for f, k in rows), \
        "不得出合计行——印好的合计数就是邀请别人去相加"


def test_an_unreadable_run_kind_marker_says_so_instead_of_vanishing():
    """标记读不了要**说出来**，不能静默从表里消失（D-330）。

    「查不了」与「不存在」在渲染面必须长得不一样，否则一个坏掉的采集目录
    会被读成「本次窗没跑这一格」，而两者的处置完全相反。
    反例证伪：解析失败时 continue 掉该目录，本条即红。
    """
    import io as _io
    import os as _os
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        _obs_dir(d, "broken", "DEVICE_REAL")
        _io.open(_os.path.join(d, "broken", "RUN_KIND.json"), "w",
                 encoding="utf-8").write("{not json")
        obs = cl.observation_runs([d])
    assert len(obs) == 1 and "error" in obs[0], "读不了的目录不得消失"
    md = cl.render_md([], [], [], [], {"lines": 0}, cl.buckets([]), [], obs)
    assert "**读不了**" in md


def _pt_recs(counts, started=1783944000000):
    """按 {point_id: n} 造 run，其余战役字段固定，只让点位维度变化。"""
    out = []
    for pid, n in counts.items():
        for i in range(n):
            out.append(make_record(
                started_ms=started,
                campaign={"campaign_id": "c", "tier": "metro", "point_id": pid,
                          "carrier": "ctcc", "time_band": "busy"},
                scenarios=[("s1_chat", {})], run_id="%s-%d" % (pid, i)))
    return out


def test_the_single_point_figure_is_named_and_carries_its_point_id():
    """「外场单点位有多少」必须是**有名字的行项**，且数字与点位 id 绑在一起。

    此前只能让引用者从维度表四个桶里自己挑——**能自己挑就能挑错**，
    2026-08-29 挑错的那次正好落在 PO 页头条（写 73，实为 57）。
    id 与数字同行给，是为了数字被搬进别的文档后不失去「它是哪个点」。
    反例证伪：只印数字不印 id，或不出这一行，本条即红。
    """
    recs = _pt_recs({"SZ-PILOT-01": 5, "home_indoor": 3})
    bk = cl.buckets(recs)
    assert cl.field_points(bk) == [("SZ-PILOT-01", 5)]
    md = cl.render_md([("f.jsonl", 5, 5)], [], recs, [], {"lines": 5}, bk, [])
    assert "**单点位最大样本：`SZ-PILOT-01` 5 条**" in md
    rows = {(f, k): v for f, k, v in cl.render_csv_rows(recs, [], bk)}
    assert rows[("field_point_max", "SZ-PILOT-01")] == 5, \
        "机器面也要给具名行项——消费方同样不该自己去挑"


def test_the_excluded_buckets_are_each_accounted_for_beside_the_figure():
    """排除项要**逐条交代在同一行**——否则 57 就是个没有余数的孤数。

    一个不交代分母余数的数，读者无从判断它是「全部」还是「其中一部分」。
    反例证伪：把 `已排除` 段删掉，本条即红。
    """
    recs = _pt_recs({"SZ-PILOT-01": 5, "home_indoor": 3, "PENDING-PO-01": 2})
    bk = cl.buckets(recs)
    md = cl.render_md([("f.jsonl", 10, 10)], [], recs, [], {"lines": 10}, bk, [])
    line = [l for l in md.split("\n") if "单点位最大样本" in l][0]
    assert "`PENDING-PO-01` 2（占位符" in line
    assert "`home_indoor` 3（非外场）" in line


def test_a_placeholder_point_never_becomes_the_single_point_figure():
    """占位符即使数量最多，也不得当成单点位样本——它不是一个真实站点。

    反例证伪：把 is_placeholder_point 恒返回 False，本条即红。
    """
    recs = _pt_recs({"PENDING-PO-01": 9, "SZ-PILOT-01": 2})
    bk = cl.buckets(recs)
    assert cl.field_points(bk) == [("SZ-PILOT-01", 2)]


def test_the_placeholder_predicate_has_a_single_source():
    """占位符判据只能有一处实现——维度表标注与单点位行项**共用同一判断**。

    两处各写一个 `startswith` 就是 §2.14 那种会各自漂的同名实现：改了一处、
    另一处照旧，而两个面都不会吭声。
    反例证伪：把 render_md 里那处改回内联 `startswith`，本条即红。
    """
    import inspect
    src = inspect.getsource(cl.render_md) + inspect.getsource(cl.render_csv_rows)
    assert 'startswith("PENDING-' not in src, \
        "占位符判据只许走 is_placeholder_point()，不得再内联一份"


def test_a_hand_edit_to_the_ledger_is_detected_by_check_mode():
    """台账开篇写着「勿手编」——`--check` 是那句话的执行面。

    此前它只是一句话：手改能一直活到下次重算，而重算可能在很久以后，
    期间那两面仍被当作单一事实源引用。判据是**逐字节相同**而不是长度或
    某几个数——本条的反例把 `57 条` 改成 `58 条`，字符数一模一样。
    反例证伪：把比对改成长度比较，本条即绿。

    真树的判定归 `verify_all` 的 `corpus-ledger-fresh` 门；这里只证机制
    （夹具/真树分工同 `check_evidence`：避免别的会话改语料时把本套件推红）。
    """
    import io as _io
    import os as _os
    import tempfile
    recs = _pt_recs({"SZ-PILOT-01": 3})
    with tempfile.TemporaryDirectory() as d:
        root = _os.path.join(d, "evidence")
        _os.makedirs(root)
        _io.open(_os.path.join(root, "c.jsonl"), "w", encoding="utf-8").write(
            "\n".join(__import__("json").dumps(r, ensure_ascii=False)
                      for r in recs) + "\n")
        md = _os.path.join(d, "L.md")
        csv = _os.path.join(d, "L.csv")
        args = ["--root", root, "--md", md, "--csv", csv]
        assert cl.main(args) == 0                       # 生成
        assert cl.main(args + ["--check"]) == 0         # 刚生成 → 同步
        txt = _io.open(md, encoding="utf-8", newline="").read()
        assert "3 条" in txt, "夹具没走到含数字的行，反例会测空气"
        _io.open(md, "w", encoding="utf-8", newline="").write(
            txt.replace("3 条", "9 条", 1))             # 手改，字符数不变
        assert cl.main(args + ["--check"]) == 1, "手改必须被抓住"


def test_a_missing_ledger_is_cannot_compare_not_drift():
    """**「读不了」不是「漂移」**——判词必须点对成因，否则处置句会把人带反。

    实测成因（2026-08-30，`-Scope all`）：本门当时不 `Push-Location`，
    `--md/--csv` 的默认相对路径落在别的 cwd 上 ⇒ 文件读不到 ⇒ 旧实现报 **DRIFT**，
    而 DRIFT 的处置句是「**重算并提交**」。
    ⇒ **它会指使人去重算一份本来就正确的台账，并提交一个由错误 cwd 算出的结果。**

    退出码三分：0＝一致 / 1＝真漂移 / **2＝没比成**。
    """
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        gone_md = os.path.join(d, "nope", "CORPUS_LEDGER.md")
        gone_csv = os.path.join(d, "nope", "CORPUS_LEDGER.csv")
        rc = cl.main(["--root", d, "--md", gone_md, "--csv", gone_csv, "--check"])
    assert rc == 2, "文件不在时必须是「没比成」(2)，不能冒充漂移(1)，rc=%s" % rc


def test_the_program_refuses_to_compute_when_a_root_is_missing():
    """**生产路径必须真的走那条检查**——不是「函数存在」，是「main 会拒算」。

    ⚠ 本条补的是我自己的一个洞：首版**只定义了 `missing_roots()` 却没人调用**，
    而下面那条测试只测函数本身 ⇒ **函数在、测试绿、生产路径一次都没走过它**。
    正是本仓「**写好了一道门 ≠ 那道门在门禁清单上**」，也是「测试围着一条
    没被执行的代码路径打转」的同一形状。

    判据：缺根时 `main()` 返回 **2（拒算）**，且**不写出任何台账文件**——
    少一个根＝少一批语料，而算出来的数**看起来完全正常**。
    """
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        good = os.path.join(d, "ev")
        os.makedirs(good)
        gone = os.path.join(d, "not_here")
        md = os.path.join(d, "L.md")
        csv = os.path.join(d, "L.csv")
        rc = cl.main(["--root", good, "--root", gone, "--md", md, "--csv", csv])
        assert rc == 2, "缺根必须拒算(2)，实得 %s" % rc
        assert not os.path.exists(md), "拒算时不得写出台账 md"
        assert not os.path.exists(csv), "拒算时不得写出台账 csv"
        # 对照：根都在时照常算得出来（证明拒算不是把功能整个关掉）
        rc2 = cl.main(["--root", good, "--md", md, "--csv", csv])
        assert rc2 == 0 and os.path.exists(md), "根都在时应正常产出，rc=%s" % rc2


def test_a_configured_root_that_does_not_exist_is_detectable():
    """**「根不在」与「根里没语料」结果同形**——必须有一条判据把前者认出来。

    成因（v4 的 worktree 试点实证）：`server/data/` 被 `.gitignore` 挡、零受跟踪文件
    ⇒ **全新 worktree 里该目录不存在**，而它在 `DEFAULT_ROOTS` 里
    ⇒ **同一份代码算出一个不同的语料范围，不报错，只给一个不同的数**——
    而那个数正是台账、正是「进展」声明的单一事实源。
    """
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        present = os.path.join(d, "here")
        os.makedirs(present)
        absent = os.path.join(d, "not_here")
        assert cl.missing_roots([present]) == []
        assert cl.missing_roots([present, absent]) == [absent]
        # 判据必须落在「根存不存在」上，而不是「扫出来几条」——
        # 空目录与不存在的目录都扫出 0 条，但只有后者是配置/环境问题。
        corpus, _ = cl.discover([present])
        assert corpus == [], "空的真实目录应当扫出 0 条，且**不**被判为缺根"
        assert cl.missing_roots([present]) == []


def test_the_ledgers_claim_about_validate_results_is_actually_true():
    """台账渲染面上那句**关于另一个工具行为**的断言，必须真的成立。

    台账印给 PO 看的原话：观察通道产物「喂 `validate_results.py` 即 contract
    VIOLATIONS，结构上进不了 wire 池」——那是**静态断言**（与本次数据无关，
    只随代码变化而变假），却经渲染**递到读者面前**。
    **一条被机器递送的注释就不再是注释，是数据**：`validate_results.py` 哪天
    放宽了，台账会继续替它说这句话，而没有任何东西会红。

    这条把散文升成受检断言。同族实例（同日）：`e2_analyze` 的 `gate_caveat`
    把 W-4 之前的旧话「未设最小 n」经参数流进判读页，成了一条假免责。
    反例证伪：让 validate_results 接受观察通道产物，本条即红。
    """
    import subprocess
    import sys as _sys
    import tempfile
    import os as _os
    import io as _io
    with tempfile.TemporaryDirectory() as d:
        p = _os.path.join(d, "screencap_index.jsonl")
        _io.open(p, "w", encoding="utf-8").write(
            '{"t_ms":1,"roi_mean":12.5}\n{"t_ms":2,"roi_mean":13.0}\n')
        r = subprocess.run(
            [_sys.executable,
             _os.path.join(_os.path.dirname(_os.path.dirname(
                 _os.path.abspath(__file__))), "validate_results.py"), p],
            # 同上：裸 text=True 会让 stdout 静默变 None。这一处**平时碰不到**
            # （stdout 只在下面断言失败时才被取），所以它会在**最需要判词的那一刻**
            # 以 TypeError 冒充失败原因——比直接红更难查。
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=dict(_os.environ, PYTHONIOENCODING="utf-8"))
    assert r.returncode != 0, (
        "观察通道产物竟通过了 wire 契约校验——台账那句「结构上进不了 wire 池」"
        "已不成立，两条链的隔离前提没了。stdout=%s" % r.stdout[:400])


def test_the_refusal_prints_a_summary_marker_the_gate_can_actually_find():
    """拒算必须打**门捞得到的那一行**，否则「响亮拒算」在摘要面上是哑的。

    实测（2026-08-30，worktree 里跑 `-Scope scripts`）：`verify_all.ps1` 取判词的
    办法是**捞含 `corpus ledger check:` 的那一行**；而我首版给缺根拒算只写了
    stderr 的多行说明、**没打这行标记** ⇒ 摘要面上是

        NOT_EXECUTED checks (these verified NOTHING):
          - corpus-ledger-fresh

    后面**一个成因都没有**，读者分不出「缺根/环境不对」和「别的没比成」。
    D-609③ 给这条路径的定位正是**响亮拒算**——响亮丢在摘要面上就等于没响
    （同族＝本仓那条「摘要面才是被执行的那面」）。

    ⚠ 成因必须与状态词在**同一行**：写在后续行里到不了摘要面。
    ⚠ 两条 RC=2 复用状态词 CANNOT_COMPARE 是对的（它们回答同一个问题＝
    「为什么没比成」），但**处置不同**（这条＝回主树；另一条＝先确认 cwd），
    故各自必须带成因——共用状态词、不共用成因。

    本条走的是**生产路径**（真起子进程、读它的 stdout 与退出码），
    不是只测那个函数——首版的缺陷恰恰是「函数在、测试也绿，而生产路径没走过它」。
    """
    import os as _o
    import subprocess
    import sys as _s
    import tempfile
    repo = _o.path.dirname(_o.path.dirname(_o.path.abspath(cl.__file__)))
    with tempfile.TemporaryDirectory(prefix="dryrun_ledger_") as tmp:
        absent = _o.path.join(tmp, "definitely_not_here")
        # ⚠ 编码必须**两侧都钉死**，否则 stdout 会**静默变成 None**（2026-08-31 实测）：
        # PowerShell 下 `sys.stdout.encoding=utf-8` 而 `locale.getencoding()=cp936`
        # ⇒ 子进程按 UTF-8 写、父进程按 GBK 解 ⇒ UnicodeDecodeError 抛在
        # `subprocess._readerthread` **线程里被吞掉**，`run()` 正常返回、
        # `stdout`/`stderr` 双双是 None，**调用方一个错都收不到**。
        # Git Bash 下两侧同为 cp936 所以不炸——**同一份代码换个壳结论不同**。
        # 三件缺一不可：`encoding=` 钉父侧解码、`PYTHONIOENCODING` 钉子侧编码、
        # `errors=` 保证读线程永不抛（范本＝ test_cli_smoke.py，它早就是对的）。
        r = subprocess.run(
            [_s.executable, _o.path.join(repo, "scripts", "corpus_ledger.py"),
             "--check", "--root", absent],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=repo, env=dict(_o.environ, PYTHONIOENCODING="utf-8"))
    assert r.returncode == 2, (
        "缺根时退出码应为 2（没比成），实得 %r；stderr=%s"
        % (r.returncode, r.stderr[:300]))
    marker = [ln for ln in r.stdout.splitlines() if "corpus ledger check:" in ln]
    assert marker, (
        "拒算没打门捞得到的那一行（须含 `corpus ledger check:` 前缀）⇒ "
        "verify_all 的摘要行会是一句**空判词**。stdout=%r" % r.stdout[:300])
    line = marker[0]
    assert "CANNOT_COMPARE" in line, "标记行丢了状态词：%r" % line
    assert ("definitely_not_here" in line) or ("扫描根不存在" in line), (
        "标记行没带成因 ⇒ 状态到了摘要面、原因没到：%r" % line)
