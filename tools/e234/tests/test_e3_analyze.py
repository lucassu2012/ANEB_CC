# -*- coding: utf-8 -*-
"""E3 判读的反例测试。夹具由 `sim_session` 生成到临时 dry-run 目录，跑完删干净。"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import e234_common as ec     # noqa: E402
import sim_session as sim    # noqa: E402
import e3_analyze as e3      # noqa: E402

PKG = sim.SIM_PKG


class _Run(object):
    def __init__(self, scenario, mutate=None):
        self.scenario, self.mutate = scenario, mutate

    def __enter__(self):
        self.d = tempfile.mkdtemp(prefix="e234_dryrun_e3_")
        sim.write(self.d, self.scenario)
        if self.mutate:
            self.mutate(self.d)
        return self.d

    def __exit__(self, *exc):
        shutil.rmtree(self.d, ignore_errors=True)
        return False


def _rewrite_framestats(d, fn):
    p = os.path.join(d, "framestats.txt")
    with open(p, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    out = []
    for line in lines:
        if line and line[0].isdigit() and "," in line:
            cells = line.split(",")
            fn(cells)
            line = ",".join(cells)
        out.append(line)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


# ── 主判据在场 ────────────────────────────────────────────────────────────
def test_the_injected_a0_to_a0p_interval_is_recovered():
    with _Run("e3_input_timeline_present") as d:
        res = e3.analyze(d, PKG)
        truth = sim.SCENARIOS["e3_input_timeline_present"]["a0_gap_ms"]
        assert res["a0_method"] == e3.METHOD_PRIMARY
        assert res["interval"]["status"] == ec.PASS
        assert abs(res["interval"]["p50_ms"] - truth) < 1.0


def test_the_first_turn_is_not_dropped_by_a_window_that_starts_at_its_own_first_event():
    """首跑实测的那条 off-by-window：A0（手指离屏）在首条事件**之前**。

    6 轮里恰好丢 1 轮，而丢的那轮从表面上看跟「环缓冲冲掉了」长得一模一样 ——
    这正是为什么未出数的轮次必须带**原因**，不能只有一个 dropped 计数。
    """
    with _Run("e3_input_timeline_present") as d:
        res = e3.analyze(d, PKG)
        assert res["interval"]["dropped"] == 0, res["drop_reasons"]
        assert res["interval"]["n"] == sim.SCENARIOS["e3_input_timeline_present"]["turns"]


def test_overlapping_ring_buffer_dumps_are_deduped():
    """环缓冲装不下一次会话 -> 采集侧周期性追加 -> 相邻 dump 必然重叠。"""
    with _Run("e3_input_timeline_present") as d:
        res = e3.analyze(d, PKG)
        assert res["framestats_duplicate_dropped"] > 0, "夹具没造出重叠，这条测了个空气"
        assert res["framestats_rows"] == len(sim.build("e3_input_timeline_present")["frames"])


# ── 主判据缺席 ────────────────────────────────────────────────────────────
def test_a_header_without_input_timestamps_is_not_executed_and_names_the_columns():
    """「没数据」和「这台设备的表头里没有那两列」是两件事。

    印出实际列名，下一个人才判断得了是设备形态变了还是我们读错了。
    """
    with _Run("e3_input_timeline_absent") as d:
        res = e3.analyze(d, PKG)
        assert res["a0_method"] is None
        assert res["verdict"][0] == ec.NOT_EXECUTED
        assert res["interval"]["n"] == 0
        assert "InputEventId" in res["a0_unavailable_reason"]
        assert "InputEventId" in res["framestats_columns"]


def _fill_handle_input_start(d):
    """让旁路列有值（新表头下 HandleInputStart 是第 6 列，下标 5）。"""
    def fn(cells):
        if len(cells) > 5 and cells[2].strip().isdigit():
            cells[5] = cells[2]
    _rewrite_framestats(d, fn)


def test_the_proxy_column_is_never_used_unless_it_is_explicitly_asked_for():
    """§1.6 第 1 条：禁止用备判据的值冒充主判据的口径。"""
    with _Run("e3_input_timeline_absent", mutate=_fill_handle_input_start) as d:
        res = e3.analyze(d, PKG, allow_proxy=False)
        assert res["a0_method"] is None, "旁路被静默启用了"
        assert res["verdict"][0] == ec.NOT_EXECUTED


def test_the_proxy_when_opted_in_carries_its_own_method_tag():
    """§1.6 第 2 条：每个产出值必须携带 method 标签；第 4 条：两个 method 不进同一池。"""
    with _Run("e3_input_timeline_absent", mutate=_fill_handle_input_start) as d:
        res = e3.analyze(d, PKG, allow_proxy=True)
        assert res["a0_method"] == e3.METHOD_PROXY
        assert e3.METHOD_PROXY in e3.render_markdown(res)
        assert res["a0_method"] != e3.METHOD_PRIMARY


# ── 这一页刻意没有门 ──────────────────────────────────────────────────────
def test_the_interval_is_reported_not_gated():
    """spec §3.3 E3 逐字：「它不是"误差"，是被测 App 的输入处理耗时」。

    断言落在**行为**上而不是措辞上：把间隔放大十倍，判定不许因此改变 ——
    会因数值大小改变的判定就是一道门，而这里不该有门（D-318 的教训：
    断言落在措辞上，改一句话就红，而改一个常量它反而不红）。
    """
    def _shift(d):
        delta = 1_620_000_000     # 让 180ms 变成 1800ms
        def fn(cells):
            for i in (3, 4):
                if len(cells) > i and cells[i].strip().isdigit() and int(cells[i]) > 0:
                    cells[i] = str(int(cells[i]) - delta)
        _rewrite_framestats(d, fn)

    with _Run("e3_input_timeline_present") as base:
        v0 = e3.analyze(base, PKG)
    with _Run("e3_input_timeline_present", mutate=_shift) as d:
        v1 = e3.analyze(d, PKG)
    assert v1["interval"]["p50_ms"] > 10 * v0["interval"]["p50_ms"] - 1
    assert v1["verdict"][0] == v0["verdict"][0] == ec.PASS


def test_the_two_numbers_for_ruling_6_6_are_handed_back_without_a_ruling():
    with _Run("e3_input_timeline_present") as d:
        res = e3.analyze(d, PKG)
        assert set(res["for_6_6"]) == {"a0_to_a0p_p50_ms", "a0_to_a0p_p99_ms", "note"}
        assert res["for_6_6"]["a0_to_a0p_p50_ms"] == res["interval"]["p50_ms"]


def test_turns_that_never_close_a_cluster_are_counted_with_a_reason():
    """§1.4 的 Compose 形状：单簇不闭合 -> A0′ 无判据，记原因而不是静默跳过。"""
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

    with _Run("e3_input_timeline_present", mutate=_flatten) as d:
        res = e3.analyze(d, PKG)
        assert sum(res["drop_reasons"].values()) > 0
        assert any("不足两簇" in k for k in res["drop_reasons"])
        assert res["verdict"][0] == ec.NOT_EXECUTED


def test_the_dry_run_banner_reaches_the_e3_markdown():
    with _Run("e3_input_timeline_present") as d:
        res = e3.analyze(d, PKG)
        assert res["dry_run"] is True
        assert ec.DRY_RUN_BANNER in e3.render_markdown(res)
