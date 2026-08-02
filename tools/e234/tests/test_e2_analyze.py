# -*- coding: utf-8 -*-
"""E2 判读的反例测试。夹具全部由 `sim_session` 生成到临时 dry-run 目录，跑完删干净。

夹具会改 `sim_session.SCENARIOS`（加一个负向滞后的场景），改动一律走 try/finally
还原 —— 会污染工作区的夹具比测试失败危险得多（D-321）。
"""
import copy
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import e234_common as ec     # noqa: E402
import e234_session as es    # noqa: E402
import sim_session as sim    # noqa: E402
import e2_analyze as e2      # noqa: E402

PKG = sim.SIM_PKG


class _Run(object):
    """临时 dry-run 目录；`with` 退出即删。"""

    def __init__(self, scenario, mutate=None):
        self.scenario, self.mutate = scenario, mutate

    def __enter__(self):
        self.d = tempfile.mkdtemp(prefix="e234_dryrun_e2_")
        sim.write(self.d, self.scenario)
        if self.mutate:
            self.mutate(self.d)
        return self.d

    def __exit__(self, *exc):
        shutil.rmtree(self.d, ignore_errors=True)
        return False


def _with_scenario(name, base, **over):
    """临时注册一个场景并还原（夹具不许留在模块里）。"""
    def deco(fn):
        def wrapper():
            sim.SCENARIOS[name] = copy.deepcopy(sim.SCENARIOS[base])
            sim.SCENARIOS[name].update(over)
            try:
                return fn()
            finally:
                sim.SCENARIOS.pop(name, None)
        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        return wrapper
    return deco


# ── 门的两个方向 ──────────────────────────────────────────────────────────
def test_a_sub_frame_anchor_offset_passes_the_gate():
    with _Run("e2_within_one_frame") as d:
        res = e2.analyze(d, PKG)
        assert res["verdict"][0] == ec.PASS
        assert res["channel_a_vs_c"]["n"] == sim.SCENARIOS["e2_within_one_frame"]["turns"]
        assert res["channel_a_vs_c"]["p99_ms"] <= res["frame_ms"]


def test_a_three_frame_anchor_offset_fails_the_gate():
    """门必须会说 FAIL。只会说 PASS 的门等于没有门。"""
    with _Run("e2_over_one_frame") as d:
        res = e2.analyze(d, PKG)
        assert res["verdict"][0] == ec.FAIL
        assert res["channel_a_vs_c"]["p99_ms"] > res["frame_ms"]


@_with_scenario("e2_negative_lag", "e2_over_one_frame", a_lag_ms=[-55.0, -45.0])
def test_a_large_negative_offset_also_fails_instead_of_passing_a_one_sided_gate():
    """T14 §2.1③ 的反向守卫：通道 A 的期望方向**就是负**。

    e1 的 `gate_verdict` 对通道 A 是单边的（`p99 <= frame_ms`），实测同一个 500ms
    滞后 C 报 FAIL、**A 报 PASS**，M3 门对通道 A 名存实亡。这里判据落在 `|Δ|` 上，
    而符号另行印出 —— 所以一个 3 帧的**负**偏差同样过不去。
    """
    with _Run("e2_negative_lag") as d:
        res = e2.analyze(d, PKG)
        assert res["verdict"][0] == ec.FAIL, "负向偏差被单边门放行了"
        assert res["signed"]["p50_ms"] < 0, "符号没有被保留下来"
        assert res["channel_a_vs_c"]["p50_ms"] > 0


# ── 前提不成立时不出数 ────────────────────────────────────────────────────
def _break_post_pin(d):
    """把后钉桩的 MONOTONIC 整体挪 40ms：制造一次超过 1 帧的时钟漂移。"""
    p = os.path.join(d, "stim_post.log")
    with open(p, "r", encoding="utf-8") as fh:
        text = fh.read()
    out = []
    for line in text.splitlines():
        if "t_commit_mono_ns=" in line:
            head, val = line.rsplit("t_commit_mono_ns=", 1)
            line = head + "t_commit_mono_ns=%d" % (int(val) - 40_000_000)
        out.append(line)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


def test_a_drifted_clock_pin_stops_the_whole_comparison():
    """宁可不报，也不拿一个已知漂掉的偏移去减 —— 那会得到一个看着合理的错数。"""
    with _Run("e2_within_one_frame", mutate=_break_post_pin) as d:
        res = e2.analyze(d, PKG)
        assert res["verdict"][0] == ec.NOT_EXECUTED
        assert res["channel_a_vs_c"]["n"] == 0
        assert "钉桩" in res["channel_a_vs_c"]["reason"]


def _strip_marks(d):
    p = os.path.join(d, "adapter.log")
    with open(p, "r", encoding="utf-8") as fh:
        kept = [l for l in fh if es.MARK_TAG not in l]
    with open(p, "w", encoding="utf-8") as fh:
        fh.writelines(kept)


def test_without_marks_the_run_is_one_turn_and_the_result_says_which_method():
    """没有标记时 n 结构上就是 1 —— 那个 p99 什么也不是，读者必须看得见这件事。"""
    with _Run("e2_within_one_frame", mutate=_strip_marks) as d:
        res = e2.analyze(d, PKG)
        assert res["turn_method"] == es.TURN_METHOD_WHOLE_RUN
        assert res["turns_total"] == 1
        assert res["turn_method"] in e2.render_markdown(res)


def test_turns_that_cannot_yield_an_anchor_are_counted_with_a_reason():
    """静默跳过会让分母悄悄变小（D-336）：未出数的轮次必须逐条留痕。"""
    def _flatten(d):
        # 把事件时戳压成等间隔 1ms：簇分割再也分不出两簇（DeepSeek 形状）
        p = os.path.join(d, "adapter.log")
        with open(p, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        out, k = [], 0
        for line in lines:
            if "t_boot_ns=" in line and "type=content" in line:
                head, _val = line.rsplit("t_boot_ns=", 1)
                line = head + "t_boot_ns=%d\n" % (sim.BOOT_BASE_NS + k * 1_000_000)
                k += 1
            out.append(line)
        with open(p, "w", encoding="utf-8") as fh:
            fh.writelines(out)
    with _Run("e2_within_one_frame", mutate=_flatten) as d:
        res = e2.analyze(d, PKG)
        assert sum(res["drop_reasons"].values()) > 0
        assert res["channel_a_vs_c"]["dropped"] == sum(res["drop_reasons"].values())
        assert res["verdict"][0] == ec.NOT_EXECUTED


# ── 通道 B 不许变成一个时刻 ───────────────────────────────────────────────
def test_channel_b_contributes_no_timestamp_at_all():
    """B 的时戳是宿主侧的、与设备钟无标定；它只许报周期与检出次数（spec §2.2）。"""
    with _Run("e2_within_one_frame") as d:
        res = e2.analyze(d, PKG)
        b = res["channel_b"]
        assert b["transitions_detected"] > 0
        assert not ({"p50_ms", "p99_ms", "delta_ms"} & set(b)), \
            "通道 B 出现了时间误差字段 —— 那是宿主时戳冒充设备时刻"


# ── dry-run 横幅必须落在**每一个**面上（D-303）────────────────────────────
def test_the_dry_run_banner_reaches_the_markdown_and_the_result_object():
    with _Run("e2_within_one_frame") as d:
        res = e2.analyze(d, PKG)
        assert res["dry_run"] is True
        assert ec.DRY_RUN_BANNER in e2.render_markdown(res)


def test_a_run_without_run_kind_is_not_silently_treated_as_real():
    with _Run("e2_within_one_frame") as d:
        os.remove(os.path.join(d, ec.RUN_KIND_FILE))
        res = e2.analyze(d, PKG)
        assert res["dry_run"] is False and res["run_kind"] is None
        assert "来源不明" in e2.render_markdown(res)


def test_the_gate_caveat_names_the_two_numbers_the_gate_does_not_look_at():
    """T14 待裁 C-2：门不看 dropped、不设最小 n。门限属口径决定，本脚本不发明，
    但必须把这两个数印在判定旁边。"""
    with _Run("e2_within_one_frame") as d:
        res = e2.analyze(d, PKG)
        assert str(res["channel_a_vs_c"]["n"]) in res["gate_caveat"]
        assert res["gate_caveat"] in e2.render_markdown(res)
