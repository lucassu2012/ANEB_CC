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
    assert res["verifiable_silences"] == 1, res
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
    assert res["verifiable_silences"] == 0, res


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
    assert res["verifiable_silences"] == 0, res


# ── 2. FAIL 与 NOT_EXECUTED 不可互代（本模块存在的第二理由）─────────────────

def test_continuous_render_with_zero_holes_is_FAIL():
    """全程连续覆盖、一次 ≥gap 静默都没有 ⇒ App 真的不静默 ⇒ **结构性不适用**。

    这是 DeepSeek 型「思考期播放动画」栈的形状：加轮数不解。
    """
    a = _burst(1000000000, 30)
    b = _burst(a[10], 30)
    res = _run([a, b])
    assert res["pair_states"]["disjoint"] == 0, res["pair_states"]
    assert res["verifiable_silences"] == 0, res
    assert res["verdict"][0] == ec.FAIL, res["verdict"]


def test_holey_record_with_no_silence_is_NOT_EXECUTED_not_FAIL():
    """同样「零可核静默」，但记录有丢帧边界 ⇒ 只能说**没看见**，不能说**不静默**。

    把它写成 FAIL，会让人取消一个本来可行的测量。
    **这两条（本条与上一条）成对存在，删掉任一条，另一条的区分力就消失了。**
    """
    gap_ns = ec.cluster_gap_nanos()
    a = _burst(1000000000, 30)
    b = _burst(a[-1] + gap_ns * 4, 30)
    res = _run([a, b])
    assert res["pair_states"]["disjoint"] >= 1, res["pair_states"]
    assert res["verifiable_silences"] == 0, res
    assert res["verdict"][0] == ec.NOT_EXECUTED, res["verdict"]
    assert res["verdict"][0] != ec.FAIL


def test_empty_sf_latency_is_NOT_EXECUTED_not_FAIL():
    """通道 C 没有记录 ⇒ 装置没工作，不是 App 不静默。"""
    d = tempfile.mkdtemp(prefix="e2pre_")
    try:
        res = ep.precheck(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    assert res["verdict"][0] == ec.NOT_EXECUTED, res["verdict"]
    assert res["dumps"] == 0, res


def test_majority_unjudgeable_blocks_a_green():
    """不可判间隔多于可核静默 ⇒ 不许 PASS：C 侧的次簇有一半以上可能是洞。"""
    gap_ns = ec.cluster_gap_nanos()
    a = _burst(1000000000, 4) + _burst(1000000000 + FRAME_NS * 4 + gap_ns * 3, 4)
    dumps = [a]
    for k in range(3):
        dumps.append(_burst(a[-1] + gap_ns * 10 * (k + 1), 4))
    res = _run(dumps)
    assert res["unjudgeable_gaps"] > res["verifiable_silences"], res
    assert res["verdict"][0] != ec.PASS, res["verdict"]


# ── 3. 通道 B 只许朝一个方向用 ──────────────────────────────────────────────

def test_channel_b_full_motion_blocks_a_green():
    """B 的**每一对**相邻采样都在动 ⇒ 反驳 C 的静默 ⇒ fail-closed，不许绿。"""
    gap_ns = ec.cluster_gap_nanos()
    frames, t = [], 1000000000
    for _ in range(ep.MIN_VERIFIABLE_SILENCES + 2):
        frames += _burst(t, 3)
        t = frames[-1] + gap_ns * 3
    b = [(i * 1500000000, 0.0 if i % 2 else 200.0) for i in range(20)]
    res = _run([frames], b_samples=b)
    assert res["channel_b"]["motion_rate"] == 1.0, res["channel_b"]
    assert res["verdict"][0] == ec.NOT_EXECUTED, res["verdict"]
    assert "矛盾" in res["verdict"][1], res["verdict"]


def test_channel_b_quiet_is_not_evidence_of_silence():
    """B 安静**什么都不能说**：它的采样周期是秒级，动画时标是十几毫秒。

    若有人把「B 安静」反用成「静默的证据」，本条会红 —— 连续渲染仍须判 FAIL。
    """
    a = _burst(1000000000, 30)
    b = _burst(a[10], 30)
    quiet = [(i * 1500000000, 100.0) for i in range(20)]
    res = _run([a, b], b_samples=quiet)
    assert res["channel_b"]["motion_rate"] == 0.0, res["channel_b"]
    assert res["verdict"][0] == ec.FAIL, res["verdict"]


# ── 4. 门限与尺子的来源（别写死）──────────────────────────────────────────

def test_min_verifiable_tracks_gate_min_n():
    """可核静默下界必须**跟着** `e1_analyze.GATE_MIN_N` 走，不许另取一个数。

    它不是新门限，是 e2 自己那道门的算术下界；两者分叉时判读会静默地宽于门。
    """
    assert ep.MIN_VERIFIABLE_SILENCES == ec.ea.GATE_MIN_N


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
