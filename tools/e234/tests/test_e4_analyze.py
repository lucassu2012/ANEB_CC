# -*- coding: utf-8 -*-
"""E4 判读的反例测试。夹具由 `sim_session` 生成到临时 dry-run 目录，跑完删干净。

E4 是三个实验里**唯一有作弊余地**的那个：只要判据肯用分位数、或者肯拿静默门限
去切轮，一个漂亮的分离点随时可以造出来。所以这里的反例多半在钉「不许怎么做」。
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import e234_common as ec     # noqa: E402
import e234_session as es    # noqa: E402
import sim_session as sim    # noqa: E402
import e4_analyze as e4      # noqa: E402

PKG = sim.SIM_PKG


class _Run(object):
    def __init__(self, scenario, mutate=None):
        self.scenario, self.mutate = scenario, mutate

    def __enter__(self):
        self.d = tempfile.mkdtemp(prefix="e234_dryrun_e4_")
        sim.write(self.d, self.scenario)
        if self.mutate:
            self.mutate(self.d)
        return self.d

    def __exit__(self, *exc):
        shutil.rmtree(self.d, ignore_errors=True)
        return False


# ── 两个方向的对照组 ──────────────────────────────────────────────────────
def test_the_separable_control_finds_an_interval_bounded_by_the_injected_truth():
    with _Run("e4_separable") as d:
        res = e4.analyze(d, PKG)
        p = sim.SCENARIOS["e4_separable"]
        assert res["separation"]["verdict"] == e4.SEPARABLE
        assert res["c1_usable"] is True
        # 下界 = 注入的最大流式内停顿；上界 ≥ 注入的最短轮间静默
        assert abs(res["separation"]["gap_lo_ms"] - max(p["stream_gap_ms"])) < 2.0
        assert res["separation"]["gap_hi_ms"] >= min(p["post_silence_ms"]) - 1.0


def test_the_overlap_control_reports_c1_unusable_and_shows_the_overlap():
    """spec §3.3 E4：重叠 -> 「C-1 单独不可用，A4 必须走 C-3 合取」，
    这是合法且有价值的否定结论，不得为了拿到数值而硬凑。"""
    with _Run("e4_overlap") as d:
        res = e4.analyze(d, PKG)
        sep = res["separation"]
        assert sep["verdict"] == e4.OVERLAP
        assert res["c1_usable"] is False
        assert res["t_quiet"]["status"] == ec.NOT_EXECUTED
        assert "value_ms" not in res["t_quiet"], "重叠时仍然给出了一个 T_quiet 数值"
        assert sep["overlap_hi_ms"] > sep["overlap_lo_ms"]
        assert sep["intra_gaps_inside_overlap"] > 0
        assert sep["worst_intra_examples_ms"], "只说重叠不给样例，读者无从判断严重程度"
        md = e4.render_markdown(res)
        assert "C-3" in md and "C-1" in md


# ── 判据本身不许被稀释 ────────────────────────────────────────────────────
def test_separation_uses_extremes_not_percentiles():
    """C-1 是**逐轮**应用的规则：只要有一次流式内停顿超过 T_quiet，那一次就误判。

    这里造的语料在分位数下「可分」（intra 的 p99=100ms 远小于 post 的 3000ms），
    只有极值判据才看得见那一次 5000ms 的停顿。
    """
    intra = [100.0] * 199 + [5000.0]
    post = [3000.0] * 10
    assert ec.percentile(intra, 99) < min(post), "夹具没造出「分位数会说可分」的形状"
    out = e4.separation(intra, post)
    assert out["verdict"] == e4.OVERLAP
    assert out["overlap_hi_ms"] == 5000.0


def test_separation_needs_both_distributions_to_be_non_empty():
    assert e4.separation([], [1.0])["verdict"] == ec.NOT_EXECUTED
    assert e4.separation([1.0], [])["verdict"] == ec.NOT_EXECUTED


def _strip_marks(d):
    p = os.path.join(d, "adapter.log")
    with open(p, "r", encoding="utf-8") as fh:
        kept = [l for l in fh if es.MARK_TAG not in l]
    with open(p, "w", encoding="utf-8") as fh:
        fh.writelines(kept)


def test_without_an_external_end_label_the_answer_is_not_executed_not_a_number():
    """拿静默门限切轮 = 用待标定量标定它自己；分离点会被造出来，而且造得很好看。"""
    with _Run("e4_separable", mutate=_strip_marks) as d:
        res = e4.analyze(d, PKG)
        assert res["separation"]["verdict"] == ec.NOT_EXECUTED
        assert res["c1_usable"] is None
        assert res["t_quiet"]["status"] == ec.NOT_EXECUTED
        assert "intra_gaps" not in res, "没有外部标签却仍然算出了分布"


# ── 标定前门 ──────────────────────────────────────────────────────────────
def test_a_dry_run_corpus_cannot_produce_a_t_quiet_value():
    with _Run("e4_separable") as d:
        res = e4.analyze(d, PKG)
        assert res["separation"]["verdict"] == e4.SEPARABLE
        assert res["t_quiet"]["status"] == ec.NOT_EXECUTED
        assert "T_quiet" in res["t_quiet"]["reason"]
        assert "value_ms" not in res["t_quiet"]


def test_the_front_door_is_not_vacuous_the_other_branch_really_produces_a_value():
    """先证明这道门**拦得住东西**，再说它拦住了（D-394 §2.16）。

    做法：把同一份语料的 `RUN_KIND` 改成真实采集，看那条分支是不是真的出数。
    这只发生在临时目录里，**不是**让 dry-run 数字穿真实采集的外衣流出去 ——
    它证明的恰恰是「上一条测试里的 NOT_EXECUTED 来自前门，不是来自算不出来」。
    """
    with _Run("e4_separable") as d:
        with open(os.path.join(d, ec.RUN_KIND_FILE), "w", encoding="utf-8") as fh:
            json.dump({"kind": ec.KIND_DEVICE}, fh)
        res = e4.analyze(d, PKG)
        assert res["t_quiet"]["status"] == ec.PASS
        assert res["t_quiet"]["value_ms"] > 0
        assert "conditional" in res["t_quiet"], "分离时给了数值却没带条件说明"


def test_even_when_a_value_is_produced_it_is_marked_conditional():
    with _Run("e4_separable") as d:
        with open(os.path.join(d, ec.RUN_KIND_FILE), "w", encoding="utf-8") as fh:
            json.dump({"kind": ec.KIND_DEVICE}, fh)
        res = e4.analyze(d, PKG)
        lo, hi = res["t_quiet"]["interval_ms"]
        assert lo < res["t_quiet"]["value_ms"] < hi
        assert "上界" in res["t_quiet"]["conditional"] or "条件" in res["t_quiet"]["conditional"]


# ── 口径与诊断量必须落在每个面上 ──────────────────────────────────────────
def test_the_optimistic_caliber_of_post_silence_is_stated_on_every_face():
    """「结束后静默含操作者停顿」是这一页最容易被读错的一句，三个面都要有。"""
    with _Run("e4_overlap") as d:
        res = e4.analyze(d, PKG)
        assert "操作者停顿" in res["post_silence_caliber"]
        md = e4.render_markdown(res)
        assert res["post_silence_caliber"] in md
        assert "上界" in md


def test_mark_lag_is_reported_so_an_early_mark_is_visible():
    """标记滞后若为负，说明操作者标早了，本轮尾巴被算进下一轮 ——
    那会让「结束后静默」凭空变短、让重叠看起来更严重。"""
    with _Run("e4_separable") as d:
        res = e4.analyze(d, PKG)
        assert res["mark_lag"]["n"] > 0
        assert abs(res["mark_lag"]["p50_ms"] - sim.MARK_LAG_MS) < 2.0
        assert "标记滞后" in e4.render_markdown(res)


def test_turns_that_cannot_yield_an_anchor_are_counted_with_a_reason():
    def _flatten(d):
        p = os.path.join(d, "adapter.log")
        with open(p, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        out, k = [], 0
        for line in lines:
            if "t_boot_ns=" in line and "type=content" in line:
                head, _v = line.rsplit("t_boot_ns=", 1)
                line = head + "t_boot_ns=%d\n" % (sim.BOOT_BASE_NS + k * 1_000_000)
                k += 1
            out.append(line)
        with open(p, "w", encoding="utf-8") as fh:
            fh.writelines(out)

    with _Run("e4_separable", mutate=_flatten) as d:
        res = e4.analyze(d, PKG)
        assert sum(res["drop_reasons"].values()) > 0
        assert res["separation"]["verdict"] == ec.NOT_EXECUTED


def test_the_last_turn_has_no_post_silence_and_says_so():
    """末轮之后没有下一轮事件，这段静默量不了 —— 记原因，不是记 0。"""
    with _Run("e4_separable") as d:
        res = e4.analyze(d, PKG)
        assert any("末轮" in k for k in res["drop_reasons"])
        turns = sim.SCENARIOS["e4_separable"]["turns"]
        assert res["post_silences"]["n"] == turns - 1
        assert res["intra_gaps"]["n"] > res["post_silences"]["n"]


def test_c1_usable_always_agrees_with_the_separation_verdict():
    """两处判词不许各说各话（D-303：同一事实在几个面上必须同一个判定源）。"""
    for scenario, expect in (("e4_separable", True), ("e4_overlap", False)):
        with _Run(scenario) as d:
            res = e4.analyze(d, PKG)
            assert res["c1_usable"] is expect
            assert (res["separation"]["verdict"] == e4.SEPARABLE) is expect


def test_the_dry_run_banner_reaches_the_e4_markdown():
    with _Run("e4_overlap") as d:
        res = e4.analyze(d, PKG)
        assert res["dry_run"] is True
        assert ec.DRY_RUN_BANNER in e4.render_markdown(res)
