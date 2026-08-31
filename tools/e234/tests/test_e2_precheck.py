# -*- coding: utf-8 -*-
"""`e2_precheck` 的反例守卫。

**每一条都必须能失败**：断言写在「换一种坏实现就会红」的地方，不写在措辞上。

⚠ 本文件**不许用 pytest fixture**：`tools/e234/tests/run_tests.py` 经
`tools/e1/tests/run_tests.py:discover()` 从磁盘枚举模块、然后**直接 `fn()` 无参调用**。
带 fixture 参数的测试在那只跑器下全部 TypeError —— 本仓已为这条付过一次学费
（`scripts/tests/test_check_evidence.py` 初版在 pytest 下 18/18 绿、在门上 17 条红）。
故一律用 `tempfile` + 手写 setup。
"""
import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import e234_common as ec        # noqa: E402
import e2_precheck as ep        # noqa: E402

FRAME_NS = 16666666
PERIOD_LINE = "16666666"


def _sf_text(dumps):
    """[[actual_ns,...], ...] -> `sf_latency.txt` 文本（含 dump 之间的**孤立回车**）。

    刻意复现真实文件的分隔形态：每次 dump 之后是一个只含回车的行加一个空行。
    """
    out = []
    for frames in dumps:
        out.append(PERIOD_LINE)
        for t in frames:
            out.append("%d\t%d\t%d" % (t - 1000, t, t - 500))
        out.append("\r")
        out.append("")
    return "\n".join(out) + "\n"


def _run(dumps, b_samples=None):
    """把合成数据落进临时 run 目录并跑 precheck。返回 res。"""
    d = tempfile.mkdtemp(prefix="e2pre_")
    try:
        with open(os.path.join(d, "sf_latency.txt"), "w", encoding="utf-8") as fh:
            fh.write(_sf_text(dumps))
        if b_samples is not None:
            with open(os.path.join(d, "screencap_index.jsonl"), "w",
                      encoding="utf-8") as fh:
                for t, m in b_samples:
                    fh.write(json.dumps({"t_host_ns": t, "roi_mean": m}) + "\n")
        return ep.precheck(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _burst(t0, n):
    """连续满帧率的一串帧。"""
    return [t0 + i * FRAME_NS for i in range(n)]


# ── 1. 记录连不连（本模块存在的第一理由）────────────────────────────────────

def test_identical_rings_count_as_observed_silence_not_a_hole():
    """两次 dump 内容完全相同 ⇒ 期间**一帧都没渲染** ⇒ 那是**被证明的静默**。

    本判据的初版把它算成「没看见」（覆盖率按帧跨度算），于是把真正的思考停顿判没了。

    ⚠ **本条是回归钉，不是承重守卫** —— 别把它当后者引用。突变审计实测：
    「把 `identical` 也当断点」是**等价突变**（SURVIVED），因为 `identical` 与
    `overlap` 在 `classify_pairs` 里走同一分支、且 identical 两次 dump 跨度相同，
    断不断刀都不改变覆盖性。承重的那一支是 `disjoint`（见 `mutation_audit.py` M13/M14）。
    """
    gap_ns = ec.cluster_gap_nanos()
    a = _burst(1000000000, 5)
    later = _burst(a[-1] + gap_ns * 3, 5)
    res = _run([a, list(a), a + later])
    assert res["pair_states"]["identical"] == 1, res["pair_states"]
    assert res["pair_states"]["disjoint"] == 0, res["pair_states"]
    assert res["observed_gaps"] == 1, res
    assert res["unjudgeable_gaps"] == 0, res


def test_disjoint_boundary_gap_is_unjudgeable_not_silence():
    """两次 dump 交集为空 ⇒ 期间渲染超过环深 ⇒ **确证丢帧** ⇒ 跨界的间隔不可判。

    这是本工具最核心的假阳性杀手：没有它，采集排期的洞会被读成思考静默。
    """
    gap_ns = ec.cluster_gap_nanos()
    a = _burst(1000000000, 5)
    b = _burst(a[-1] + gap_ns * 5, 5)
    res = _run([a, b])
    assert res["pair_states"]["disjoint"] == 1, res["pair_states"]
    assert res["unjudgeable_gaps"] == 1, res
    assert res["observed_gaps"] == 0, res


def test_lone_carriage_return_between_dumps_does_not_inflate_dump_count():
    """dump 之间夹着孤立回车；**dump 次数必须是真值，不是两倍**。

    实测栽过：`awk NF==1` 把孤立回车当一个字段，数出来正好 2 倍，
    而当时另一个来源（framestats 的 PROFILEDATA）**凑巧也是那个双倍值** ⇒
    看起来像互证。本条把正确计数钉死。
    """
    res = _run([_burst(1000000000, 4), _burst(2000000000, 4),
                _burst(3000000000, 4)])
    assert res["dumps"] == 3, res["dumps"]


def test_pending_frames_are_dropped_not_treated_as_time_zero():
    """待定帧（0 占位）必须剔除，绝不能当成 0 时刻参与统计（R-10）。

    若把 0 当真实时戳，序列首端会凭空多出一个跨越整个会话的巨大「静默」。
    """
    real = _burst(5000000000, 4)
    res = _run([[0, 0] + real])
    assert res["frames_deduped"] == len(real), res
    assert res["observed_gaps"] == 0, res


# ── 2. NOT_APPLICABLE 与 CANNOT_TELL 不可互代（本模块存在的第二理由）────────

def test_continuous_render_with_zero_holes_is_NOT_APPLICABLE():
    """全程连续覆盖、一次 ≥gap 静默都没有 ⇒ App 真的不静默 ⇒ **结构性不适用**。

    这是 DeepSeek 型「思考期播放动画」栈的形状：加轮数不解。
    """
    a = _burst(1000000000, 30)
    b = _burst(a[10], 30)
    res = _run([a, b])
    assert res["pair_states"]["disjoint"] == 0, res["pair_states"]
    assert res["observed_gaps"] == 0, res
    assert res["verdict"][0] == ep.NOT_APPLICABLE, res["verdict"]


def test_holey_record_with_no_silence_is_CANNOT_TELL_not_NOT_APPLICABLE():
    """同样「零已观测间隔」，但记录有丢帧边界 ⇒ 只能说**没看见**，不能说**不静默**。

    把它写成 `NOT_APPLICABLE`，会让人取消一个本来可行的测量。
    **这两条（本条与上一条）成对存在，删掉任一条，另一条的区分力就消失了。**
    """
    gap_ns = ec.cluster_gap_nanos()
    a = _burst(1000000000, 30)
    b = _burst(a[-1] + gap_ns * 4, 30)
    res = _run([a, b])
    assert res["pair_states"]["disjoint"] >= 1, res["pair_states"]
    assert res["observed_gaps"] == 0, res
    assert res["verdict"][0] == ep.CANNOT_TELL, res["verdict"]
    assert res["verdict"][0] != ep.NOT_APPLICABLE


def test_empty_sf_latency_is_CANNOT_TELL_not_NOT_APPLICABLE():
    """通道 C 没有记录 ⇒ 装置没工作，不是 App 不静默。"""
    d = tempfile.mkdtemp(prefix="e2pre_")
    try:
        res = ep.precheck(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    assert res["verdict"][0] == ep.CANNOT_TELL, res["verdict"]
    assert res["dumps"] == 0, res


def test_majority_unjudgeable_blocks_a_green():
    """不可判间隔多于已观测间隔 ⇒ 不许 PASS：C 侧的次簇有一半以上可能是洞。"""
    gap_ns = ec.cluster_gap_nanos()
    a = _burst(1000000000, 4) + _burst(1000000000 + FRAME_NS * 4 + gap_ns * 3, 4)
    dumps = [a]
    for k in range(3):
        dumps.append(_burst(a[-1] + gap_ns * 10 * (k + 1), 4))
    res = _run(dumps)
    assert res["unjudgeable_gaps"] > res["observed_gaps"], res
    assert res["verdict"][0] != ep.WORTH_RUNNING, res["verdict"]


# ── 3. 通道 B 只许朝一个方向用 ──────────────────────────────────────────────

def test_channel_b_full_motion_blocks_a_green():
    """B 的**每一对**相邻采样都在动 ⇒ 反驳 C 的静默 ⇒ fail-closed，不许绿。"""
    gap_ns = ec.cluster_gap_nanos()
    frames, t = [], 1000000000
    for _ in range(ep.MIN_OBSERVED_GAPS + 2):
        frames += _burst(t, 3)
        t = frames[-1] + gap_ns * 3
    b = [(i * 1500000000, 0.0 if i % 2 else 200.0) for i in range(20)]
    res = _run([frames], b_samples=b)
    assert res["channel_b"]["motion_rate"] == 1.0, res["channel_b"]
    assert res["verdict"][0] == ep.CANNOT_TELL, res["verdict"]
    assert "矛盾" in res["verdict"][1], res["verdict"]


def test_channel_b_quiet_is_not_evidence_of_silence():
    """B 安静**什么都不能说**：它的采样周期是秒级，动画时标是十几毫秒。

    若有人把「B 安静」反用成「静默的证据」，本条会红 —— 连续渲染仍须判 `NOT_APPLICABLE`。
    """
    a = _burst(1000000000, 30)
    b = _burst(a[10], 30)
    quiet = [(i * 1500000000, 100.0) for i in range(20)]
    res = _run([a, b], b_samples=quiet)
    assert res["channel_b"]["motion_rate"] == 0.0, res["channel_b"]
    assert res["verdict"][0] == ep.NOT_APPLICABLE, res["verdict"]


# ── 3b. 通道 A 侧：判据要的是**两条通道同时**静默，只查 C 是只验了一半 ──────

def test_channel_a_absent_blocks_a_green_fail_closed():
    """A 侧查不了 ⇒ 不许 PASS。**「没查」与「查过没问题」绝不可同判。**

    初版把 A 缺席写成「跳过该检查」，于是一个连 `adapter.log` 都没有的目录
    照样拿到绿判词，而那个判词的措辞是「值得开 e2」。
    """
    gap_ns = ec.cluster_gap_nanos()
    frames, t = [], 1000000000
    for _ in range(ep.MIN_OBSERVED_GAPS + 3):
        frames += _burst(t, 3)
        t = frames[-1] + gap_ns * 3
    res = _run([frames])          # 临时目录里没有 adapter.log
    assert res["observed_gaps"] >= ep.MIN_OBSERVED_GAPS, res
    assert res["channel_a"]["status"] != ec.PASS, res["channel_a"]
    assert res["verdict"][0] == ep.CANNOT_TELL, res["verdict"]
    assert "A 侧" in res["verdict"][1], res["verdict"]


def test_channel_a_actually_runs_on_a_whole_session():
    """A 侧那条路**要被真正走一遍**，不能只测判定分支。

    **本条是突变审计逼出来的**：M18（「A 侧永远报够」）第一次实测 **SURVIVED**——
    因为我的临时目录没有 `RUN_KIND.json`，`pkg` 取不到，`channel_a_anchors`
    **一次都没被调用**；另两条 A 侧测试又是直接调 `_verdict`。
    ⇒ **三条测试围着一条从没被执行的代码路径打转，而它们全绿。**
    用 `sim_session` 造一整场会话（它同时写 adapter.log 与 RUN_KIND.json），把那条路走通。
    """
    import sim_session as sim
    # 目录名必须带 `dryrun`：写盘前的隔离断言（D-270）会拒绝把模拟语料落进
    # 一个看起来像真实采集的目录。**第一次写这条测试时就被它拦下了**——
    # 那道门是活的，不是摆设。
    d = tempfile.mkdtemp(prefix="dryrun_e2pre_")
    try:
        sim.write(d, "e2_within_one_frame")
        # 显式给 pkg：模拟器写的 `RUN_KIND.json` **不含 `pkg`**（真实采集器写），
        # 所以这里不能靠那条默认路径——**默认值在模拟语料上取不到，是模拟器的边界，
        # 不是本工具的缺陷**；真实格已核过有该字段。
        res = ep.precheck(d, sim.SIM_PKG)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    a = res["channel_a"]
    assert a["status"] == ec.PASS, a
    assert a["turns"] == sim.SCENARIOS["e2_within_one_frame"]["turns"], a
    assert 0 <= a["turns_with_anchor"] <= a["turns"], a


def test_channel_a_shortfall_names_A_as_the_bottleneck():
    """A 侧可用轮数不足时，理由必须点名**瓶颈在 A 不在 C**。

    否则读者会去改采样周期——那治的是 C 侧，对 A 侧一点用都没有。
    实测形状：`cell_f1` C 侧 10 次已观测间隔、A 侧只有 3/8 轮。
    """
    v = ep._verdict({"identical": 0, "overlap": 5, "disjoint": 1},
                    [500.0] * 10, [500.0] * 2,
                    {"status": ec.PASS, "motion_rate": 0.1},
                    {"status": ec.PASS, "turns": 8, "turns_with_anchor": 3})
    assert v[0] == ep.CANNOT_TELL, v
    assert "A 侧" in v[1] and "瓶颈在 A 不在 C" in v[1], v


def test_channel_a_sufficient_lets_it_through():
    """A 侧够了就不该拦——否则这道新检查会把本来可跑的格也判掉。"""
    v = ep._verdict({"identical": 0, "overlap": 5, "disjoint": 1},
                    [500.0] * 10, [500.0] * 2,
                    {"status": ec.PASS, "motion_rate": 0.1},
                    {"status": ec.PASS, "turns": 5, "turns_with_anchor": 5})
    assert v[0] == ep.WORTH_RUNNING, v


# ── 4. 门限与尺子的来源（别写死）──────────────────────────────────────────

def test_min_verifiable_tracks_gate_min_n():
    """已观测间隔下界必须**跟着** `e1_analyze.GATE_MIN_N` 走，不许另取一个数。

    它不是新门限，是 e2 自己那道门的算术下界；两者分叉时判读会静默地宽于门。
    """
    assert ep.MIN_OBSERVED_GAPS == ec.ea.GATE_MIN_N


def test_cluster_gap_comes_from_device_source():
    """簇分割门限须来自设备侧 `ObsStats.kt`，与 e2 **同一把尺**。"""
    res = _run([_burst(1000000000, 4)])
    assert res["cluster_gap_ms"] == ec.cluster_gap_nanos() / ec.NS_PER_MS
    assert res["cluster_gap_ms"] > 0


def test_ring_depth_is_max_rows_per_dump():
    """环深取各次 dump 的最大原始行数 —— 它是缓冲区容量，不是本场内容。"""
    period, depth = ep.parse_ring_shape(
        _sf_text([_burst(1000000000, 3), _burst(2000000000, 7)]))
    assert period == int(PERIOD_LINE), period
    assert depth == 7, depth


def test_recommended_period_is_below_the_ring_bound():
    """建议的 dump 周期必须**严格短于**环缓冲满速覆盖的墙钟上界。

    等于或长于它，忙时必丢帧 —— 而丢帧与静默在去重后的序列里长得一模一样。
    """
    res = _run([_burst(1000000000, 127),
                _burst(1000000000 + 60 * FRAME_NS, 127)])
    assert res["ring_bound_s"] is not None, res
    assert res["recommended_framestats_period_s"] < res["ring_bound_s"], res


# ── T90：图层中途失效（D-644）────────────────────────────────────────────

def test_a_layer_that_dies_mid_run_is_not_judged_as_if_it_were_healthy():
    """图层跑到一半失效的格，**不许**出一份看着健康的判词。

    实测形状（`wifi_f6_b_VOID1`）：图层约 55 秒被重建后，**569 次 dump 里 524 次
    取空**。而 `split_dumps` 末尾 `if d` 把空 dump 整批丢弃 ⇒ 判读侧只看见
    45 段整齐 127，**逐条核收窗清单会全部通过**。
    ⚠ 危险的不是那 524 段没数据，是**幸存的 45 段本身是好的**——
    它们拼出的判词看着健康，而覆盖的只是会话最前面 8% 的时间。
    """
    dumps = [_burst(1_000_000_000 + i * 100_000_000, 20) for i in range(20)]
    dumps += [[] for _ in range(100)]
    res = _run(dumps)
    assert res["verdict"][0] == ep.CANNOT_TELL, res["verdict"]
    why = res["verdict"][1]
    assert "120" in why and "20" in why, why


def test_the_denominator_is_the_dumps_issued_not_the_ones_that_survived():
    """`dumps` 这个字段是**过滤之后**的数；分母必须另记，否则失效不可见。"""
    dumps = [_burst(1_000_000_000 + i * 100_000_000, 20) for i in range(6)]
    dumps += [[] for _ in range(2)]
    res = _run(dumps)
    assert res["dumps_issued"] == 8, res["dumps_issued"]
    assert res["dumps_with_frames"] == 6, res["dumps_with_frames"]
    assert res["dumps"] == res["dumps_with_frames"], "legacy 字段口径变了"
    assert abs(res["dump_survival"] - 0.75) < 1e-9, res["dump_survival"]


def test_a_healthy_run_is_not_flagged_by_the_survival_floor():
    """健康格不许被新判据误伤 —— 实测全仓健康格存活率**恒为 100%**。"""
    dumps = [_burst(1_000_000_000 + i * 100_000_000, 20) for i in range(10)]
    res = _run(dumps)
    assert res["dump_survival"] == 1.0, res["dump_survival"]
    assert "仪器失效" not in res["verdict"][1], res["verdict"]
    assert "dump存活" not in ep.render_line(res), ep.render_line(res)


def test_too_few_dumps_is_not_reported_as_a_layer_failure():
    """**「根本没跑起来」与「图层死了」是两种病，判词不许共用。**

    实测有三个退化跑（发出 1／1／5 次 dump、零帧）会以 0% 命中比例判据，
    而它们的病因是采集根本没起来。共用一个判词会把下游引向错的修法
    ——本仓吃过「共用 token 前先问这两个词回答的是同一个问题吗」的亏。

    ⚠ 用例必须让 `dumps` **非空**：首版写的是 `_run([[], []])`，两段全空会在
    `if not dumps` 那里就返回，**根本走不到本条要守的那个守卫**——突变审计当场
    判它 SURVIVED（拿掉 DUMP_SURVIVAL_MIN_N 它照样绿）。**测试为错误的理由变绿。**
    """
    res = _run([_burst(1_000_000_000, 20), []])
    assert res["dumps_issued"] == 2 and res["dumps_with_frames"] == 1
    assert res["dump_survival"] == 0.5, res["dump_survival"]
    assert "仪器失效" not in res["verdict"][1], res["verdict"]


def test_partial_degradation_speaks_even_when_it_passes_the_floor():
    """**硬门限只拦灾难，部分退化必须自己出声。**

    门限 0.95 是从空区里取的（健康恒 100%，异常 68.2% 与 7.9%）；
    落在 (0.95, 1.0) 的格会从门限底下**静默走过去**，而它同样意味着仪器抖了。
    ⇒ 判词行在存活率不足 100% 时一律带 ⚠，沉默本身才是健康信号。
    """
    dumps = [_burst(1_000_000_000 + i * 100_000_000, 20) for i in range(39)]
    dumps += [[]]
    res = _run(dumps)
    assert res["dump_survival"] == 0.975, res["dump_survival"]
    assert "仪器失效" not in res["verdict"][1], "0.975 不该触发硬门限"
    assert "dump存活=97.5%" in ep.render_line(res), ep.render_line(res)


def test_count_issued_dumps_is_immune_to_the_stray_carriage_return():
    """数分母别用 `awk NF==1`：dump 之间夹着孤立回车，会**正好数出两倍**。

    「正好 2 倍」是最危险的错——它看起来像一条干净的结构性事实
    （「每次两个标记」），本仓已在 framestats 的 PROFILEDATA 上撞过一次巧合等值。
    """
    text = _sf_text([_burst(1_000_000_000, 5), [], _burst(2_000_000_000, 5)])
    assert "\r" in text, "夹具没复现孤立回车，这条守卫就没在守它该守的东西"
    assert ep.count_issued_dumps(text) == 3, ep.count_issued_dumps(text)


def test_the_real_void_fixture_is_refused_with_its_measured_numbers():
    """真反例夹具（`wifi_f6_b_VOID1`）必须被拒判，且数字对得上。

    569 发出／45 有帧／524 取空 —— 524 这个数是我按单 token 行独立数出来的，
    与采集侧独立报的 524 逐字吻合（两条不共享量法）。
    ⚠ 夹具缺失时**红**，不 skip：一条「找不到数据就悄悄通过」的守卫，
    与它要防的静默缺席是同一种病。
    """
    root = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
    d = os.path.join(root, "evidence", "wave1_20260831", "wifi_f6_b_VOID1")
    assert os.path.isdir(d), "反例夹具不在：%s" % d
    res = ep.precheck(d)
    assert res["dumps_issued"] == 569, res["dumps_issued"]
    assert res["dumps_with_frames"] == 45, res["dumps_with_frames"]
    assert res["verdict"][0] == ep.CANNOT_TELL, res["verdict"]


def test_dump_rows_counts_raw_lines_including_the_empty_dumps():
    """逐段行数的长度＝**发出次数**（空段也占一位），否则它答不了「每段满不满」。"""
    text = _sf_text([_burst(1_000_000_000, 20), [], _burst(2_000_000_000, 5)])
    rows = ep.dump_row_counts(text)
    assert len(rows) == 3, rows
    assert rows[1] == 0, rows
    assert len(rows) == ep.count_issued_dumps(text)


def test_a_full_ring_of_pending_frames_is_a_different_disease_from_a_dead_layer():
    """钉住 `dump_row_counts` 与 `split_dumps` 的**口径差**：前者数原始行，后者滤待定帧。

    ⚠ **〔2026-09-01 订正 · D-650②〕本条初版的理由是错的，照录**：我原本写它证明
    「环满但全待定」与「图层死了」是两种病。**真机上那个组合不出现**——图层死则
    原始行也归 0，两数同向、是同一件事的两面。**照抄一句话时，连它断言的那个状态
    存不存在也要验。**

    **但本条留着，因为它钉的东西是真的**：两个函数的口径确实不同，
    而突变 M24（拿 `split_dumps` 的口径冒充原始行）正是被它咬住的。
    ⇒ **「理由错了」不等于「守卫没用」**——这两件要分开判，
    否则订正会顺手删掉一条在承重的守卫。
    """
    pend = ep.PENDING_NS
    lines = [PERIOD_LINE]
    for i in range(30):
        lines.append("%d\t%d\t%d" % (1000 + i, pend, pend))
    lines += ["\r", ""]
    text = "\n".join(lines) + "\n"
    assert ep.dump_row_counts(text) == [30], ep.dump_row_counts(text)
    assert ep.split_dumps(text) == [], "待定帧没有被滤掉，两个口径就不再是两个了"


def test_uniform_segments_stay_silent_and_ragged_ones_speak():
    """真机健康格实测 min=p50=max=127 无一例外 ⇒ **沉默本身是健康信号**。"""
    ok = _run([_burst(1_000_000_000 + i * 100_000_000, 20) for i in range(8)])
    assert ok["dump_rows"]["min"] == ok["dump_rows"]["max"], ok["dump_rows"]
    assert "逐段行数" not in ep.render_line(ok), ep.render_line(ok)
    ragged = _run([_burst(1_000_000_000, 20), _burst(2_000_000_000, 5),
                   _burst(3_000_000_000, 20)])
    assert ragged["dump_rows"]["min"] < ragged["dump_rows"]["max"]
    assert "逐段行数" in ep.render_line(ragged), ep.render_line(ragged)


# ── D-648③：输出编码自锁 ────────────────────────────────────────────────

class _FakeStream(object):
    def __init__(self, encoding, tty):
        self.encoding, self._tty, self.calls = encoding, tty, []

    def isatty(self):
        return self._tty

    def reconfigure(self, **kw):
        self.calls.append(kw)
        self.encoding = kw.get("encoding", self.encoding)


def test_the_encoding_lock_pins_files_and_leaves_the_terminal_alone():
    """**这个不对称是刻意的，别「统一」掉。**

    重定向／管道 ⇒ 读它的是机器与后来的人 ⇒ 必须 UTF-8；
    终端 ⇒ 读它的是此刻的人，老式 GBK 控制台收到 UTF-8 字节会显示成乱码，
    那一侧已由 `e234_common.say()` 兜住（编不出的字符逐个丢，话仍说得完）。
    """
    import sys as _sys
    import e1_io
    old_o, old_e = _sys.stdout, _sys.stderr
    try:
        f_out, f_err = _FakeStream("cp936", False), _FakeStream("cp936", False)
        _sys.stdout, _sys.stderr = f_out, f_err
        e1_io.pin_console_utf8()
        assert f_out.encoding == "utf-8" and f_err.encoding == "utf-8"
        assert f_out.calls[0].get("errors") == "replace", f_out.calls

        t_out = _FakeStream("cp936", True)
        _sys.stdout, _sys.stderr = t_out, t_out
        e1_io.pin_console_utf8()
        assert t_out.calls == [], "终端被改了 —— GBK 控制台会收到 UTF-8 字节变乱码"
    finally:
        _sys.stdout, _sys.stderr = old_o, old_e


def test_a_redirected_verdict_line_can_still_be_grepped_for_its_chinese_keys():
    """端到端：重定向落盘后，**中文键名仍读得回来**。

    实测（修前）：`e2_precheck.py > out.txt` 后 `grep '逐段行数' out.txt` **恒 0**，
    而 `grep 'e2_precheck'` 照常命中 —— Python 重定向时退回 locale 编码（cp936）。
    ⚠ 致命处不在难看：**两个判词键名全是中文**（`dump存活` 与 `逐段行数`），
    而它们答的是两个不同问题（有没有帧／够不够深，见 `dump_row_counts` 的订正段）
    ⇒ 量法只剩 ASCII 命中时，**读的人以为自己读全了**，漏掉的恰是其中一问。
    """
    import subprocess
    import sys as _sys
    d = tempfile.mkdtemp(prefix="e2enc_")
    try:
        with open(os.path.join(d, "sf_latency.txt"), "w", encoding="utf-8") as fh:
            fh.write(_sf_text([_burst(1_000_000_000, 20), _burst(2_000_000_000, 5),
                               _burst(3_000_000_000, 20)]))
        out = os.path.join(d, "stdout.txt")
        tool = os.path.join(os.path.dirname(_HERE), "e2_precheck.py")
        with open(out, "wb") as fh:
            subprocess.call([_sys.executable, tool, "--run-dir", d], stdout=fh,
                            stderr=subprocess.STDOUT)
        raw = open(out, "rb").read()
        text = raw.decode("utf-8")          # 解不出来就是又退回 GBK 了
        assert "逐段行数" in text, text[:200]
    finally:
        shutil.rmtree(d, ignore_errors=True)
