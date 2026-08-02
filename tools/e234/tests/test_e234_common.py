# -*- coding: utf-8 -*-
"""E2/E3/E4 共用层的反例测试。

每条不变量配一个「违规夹具」（断言被捉）与一个「合规夹具」（断言放行）。
夹具全在内存或临时目录，**不碰设备、不碰真 logcat、不碰真实语料**。

本文件刻意把 T14 交叉审查（`docs/T14_CROSS_AUDIT_20260801.md`）点名的三个
e1 缺陷各写成一条反例：**继承一个已知缺陷比新写一个 bug 更不可原谅**，
因为它已经有人替我们踩过了。
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import e234_common as ec  # noqa: E402
import e234_session as es  # noqa: E402

BOOT0 = 8_000_000_000_000          # 开机 8000 s，量纲合法
MONO0 = 5_000_000_000_000
OFF = BOOT0 - MONO0                 # BOOTTIME − MONOTONIC


# ── 夹具 ──────────────────────────────────────────────────────────────────
def _wall(ms):
    """毫秒偏移 -> `08-02 HH:MM:SS.mmm` 前缀（与 logcat -v time 同形）。"""
    s, msec = divmod(int(ms), 1000)
    m, sec = divmod(s, 60)
    h, minute = divmod(m, 60)
    return "08-02 %02d:%02d:%02d.%03d" % (h % 24, minute, sec, msec)


def _evt(wall_ms, boot_ns, pkg="com.larus.nova"):
    return ("%s I/AnebProbe( 5939): ADAPTER_EVT type=content cls=android.widget.TextView"
            " desc=null txt_len=12 pkg=%s t_boot_ns=%d\n" % (_wall(wall_ms), pkg, boot_ns))


def _mark(wall_ms, kind, n):
    return ("%s I/AnebE4MARK( 6001): E4MARK kind=%s n=%d\n"
            % (_wall(wall_ms), kind, n))


def _stim(n=4, warmup=1, off_ns=OFF, frame_ms=16.667, base_mono=MONO0):
    """一份 E1 刺激源日志（形状与 `tools/e1/tests` 的实测行一致）。"""
    L = ["08-02 00:00:00.000 I/E1_STIM( 100): CFG interval_ms=1000 count=%d roi_px=480 "
         "warmup=%d refresh_hz=%.3f frame_ms=%.3f screen_px=1080x2340 "
         "boot_mono_offset_ns=%d" % (n, warmup, 1000.0 / frame_ms, frame_ms, off_ns)]
    for seq in range(1, n + 1):
        mono = base_mono + seq * 1_000_000_000
        boot = mono + off_ns
        L.append("08-02 00:00:00.000 I/E1_STIM( 100): FLIP seq=%d color=A warmup=%s "
                 "t_req_boot_ns=%d t_req_mono_ns=%d"
                 % (seq, "true" if seq <= warmup else "false", boot, mono))
        L.append("08-02 00:00:00.000 I/E1_STIM( 100): COMMIT seq=%d t_commit_boot_ns=%d "
                 "t_commit_mono_ns=%d" % (seq, boot + 5_000_000, mono + 5_000_000))
    return [x + "\n" for x in L]


# ── 与生产者共享的常量 ────────────────────────────────────────────────────
def test_cluster_gap_is_read_from_the_producer_not_typed_here():
    """D-392② 的原样应用：共享量去生产者那里读。

    断言落在**两处独立读取相等**上，而不是落在 400 这个数字上 ——
    断言写死 400，生产侧改成 500 时这条测试会红，但它红得毫无信息量
    （它只说「有人改了数字」，不说「两侧分叉了」）。
    """
    got = ec.cluster_gap_nanos()
    with open(ec.OBS_STATS_KT, "r", encoding="utf-8", errors="replace") as fh:
        src = fh.read()
    assert ("= %s" % "{:,}".format(got).replace(",", "_") + "L") in src
    assert got > 0


def test_cluster_gap_refuses_to_fall_back_to_a_literal_when_the_producer_renames_it():
    """⚠ SOLE targeted guard（突变审计 M7：门限退回硬编码字面量 -> 只有这一条变红）。"""
    d = tempfile.mkdtemp(prefix="e234_kt_")
    try:
        p = os.path.join(d, "ObsStats.kt")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("const val SILENCE_SPLIT_NANOS: Long = 400_000_000L\n")
        try:
            ec.cluster_gap_nanos(p)
        except RuntimeError as e:
            assert "CLUSTER_GAP_NANOS" in str(e)
        else:
            raise AssertionError("改名之后仍然返回了一个值 —— 那个值没有出处")
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ── T14 §2.1② 被截断的时戳 ────────────────────────────────────────────────
def test_a_truncated_boot_timestamp_parses_as_int_but_fails_the_dimension_guard():
    """`int()` 成功 != 解析对了。

    T14 实测：三种截断全部解析成合法整数、样本数一个不少、退出码 0、零告警，
    而判词把 8263 秒的跨度命名为「深睡」。这里把那条防线补在量纲上。
    """
    truncated = int(str(BOOT0)[:-4])          # 砍掉 4 位，仍是合法 int
    assert isinstance(truncated, int)
    assert ec.plausible_boot_ns(BOOT0) is True
    assert ec.plausible_boot_ns(truncated) is False


def test_reject_implausible_counts_what_it_dropped_instead_of_shrinking_the_denominator():
    rows = [{"t": BOOT0}, {"t": 12345}, {"t": BOOT0 + 1}]
    kept, dropped = ec.reject_implausible(rows, "t")
    assert len(kept) == 2 and dropped == 1


# ── 簇分割 ────────────────────────────────────────────────────────────────
def test_split_clusters_breaks_above_the_gap_and_only_above_it():
    gap = 400_000_000
    ts = [0, gap, 2 * gap + 1, 2 * gap + 2]
    cl = ec.split_clusters(ts, gap)
    assert [len(c) for c in cl] == [2, 2]


def test_v3_anchors_are_absent_not_zero_when_the_stream_never_closes_a_cluster():
    """DeepSeek 形状（§1.4：思考期动画使 >400ms 静默不存在 → 单簇不闭合）。"""
    gap = 400_000_000
    ts = [i * 1_000_000 for i in range(50)]     # 全部 1ms 间隔，一簇
    a0p, a2, cl = ec.v3_anchors(ts, gap)
    assert a0p is None and a2 is None and len(cl) == 1


# ── T14 §2.1③ 一次物理事件被复用成多个样本 ────────────────────────────────
def test_nearest_after_refuses_to_hand_the_same_frame_to_a_second_caller():
    """⚠ SOLE targeted guard（突变审计 M6：去掉复用检查 -> 只有这一条变红）。"""
    frames = [{"actual_ns": 1000}]
    used = set()
    c1, w1 = ec.nearest_after(500, frames, "actual_ns", 10_000, used)
    c2, w2 = ec.nearest_after(600, frames, "actual_ns", 10_000, used)
    assert c1 is frames[0] and w1 is None
    assert c2 is None and w2 == "reused"


def test_nearest_after_separates_no_candidate_from_too_far():
    frames = [{"actual_ns": 10_000_000}]
    assert ec.nearest_after(20_000_000, frames, "actual_ns", 1_000)[1] == "none"
    assert ec.nearest_after(0, frames, "actual_ns", 1_000)[1] == "gap"


# ── 墙钟 ↔ BOOTTIME ───────────────────────────────────────────────────────
def test_wall_to_boot_offset_is_measured_and_carries_a_residual():
    lines = [_evt(1000 * i, BOOT0 + i * 1_000_000_000) for i in range(5)]
    fit = ec.fit_wall_to_boot(lines)
    assert fit["status"] == ec.PASS and fit["n"] == 5
    assert fit["residual_ms_max"] < 1.0
    # 换算要落在**这条流自己的墙钟刻度**上，不是落在「0 号毫秒」上：
    # 墙钟基点是设备当年的 1 月 1 日，偏移是个大负数，写死 0 只会测到我自己的算术。
    assert ec.wall_ms_to_boot_ns(ec.wall_ms_of_line(lines[0]), fit) == BOOT0


def test_wall_to_boot_refuses_when_the_wall_clock_goes_backwards():
    """⚠ SOLE targeted guard（突变审计 M11：去掉单调性检查 -> 只有这一条变红）。"""
    lines = [_evt(5000, BOOT0), _evt(1000, BOOT0 + 1_000_000_000)]
    fit = ec.fit_wall_to_boot(lines)
    assert fit["status"] == ec.NOT_EXECUTED and "单调" in fit["reason"]


def test_wall_to_boot_ignores_lines_whose_boot_ns_is_truncated():
    good = [_evt(1000 * i, BOOT0 + i * 1_000_000_000) for i in range(3)]
    bad = [_evt(4000, 999)]
    assert ec.fit_wall_to_boot(good + bad)["n"] == 3


# ── 时钟钉桩 ──────────────────────────────────────────────────────────────
def test_clock_pin_passes_when_the_two_pins_agree():
    pin = ec.clock_pin(_stim(), _stim(base_mono=MONO0 + 60_000_000_000), 16.667)
    assert pin["status"] == ec.PASS and pin["offset_ns"] == OFF
    assert pin["drift_ns"] == 0


def test_clock_pin_refuses_when_drift_exceeds_one_frame():
    """判据不是审美：E2 的门就是「p99 ≤ 1 帧」，钉桩自己漂过一帧，比出来的数没意义。"""
    drifted = _stim(off_ns=OFF + 20_000_000, base_mono=MONO0 + 60_000_000_000)
    pin = ec.clock_pin(_stim(), drifted, 16.667)
    assert pin["status"] == ec.NOT_EXECUTED
    assert pin["drift_ns"] == 20_000_000
    assert ec.boot_to_mono_ns(BOOT0, pin) is None


def test_clock_pin_refuses_without_a_measured_frame_length():
    """spec §3.1：门限用实测刷新率换算，不硬编码 33 —— 缺帧长就是缺参照系。"""
    pin = ec.clock_pin(_stim(frame_ms=None if False else 16.667), _stim(), None)
    assert pin["status"] == ec.PASS          # 有 cfg 里的 frame_ms 兜底
    empty = ec.clock_pin(["无关行\n"], ["无关行\n"], None)
    assert empty["status"] == ec.NOT_EXECUTED


# ── dry-run 隔离（D-270）──────────────────────────────────────────────────
def test_dry_run_products_refuse_to_be_written_outside_a_dryrun_directory():
    d = tempfile.mkdtemp(prefix="e234_iso_")
    try:
        bad = os.path.join(d, "e234_20260802")
        try:
            ec.assert_isolation_before_write(bad, ec.KIND_DRY_RUN)
        except RuntimeError as e:
            assert ec.DRY_RUN_DIR_TOKEN in str(e)
        else:
            raise AssertionError("dry-run 产物被允许写进一个看不出来源的目录")
        ok = os.path.join(d, "e234_dryrun_20260802")
        assert ec.assert_isolation_before_write(ok, ec.KIND_DRY_RUN) is True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_a_real_capture_refuses_to_wear_the_dry_run_directory_name():
    """两个方向都要拦：只拦一个方向的守卫，在另一个方向上会说「看起来没问题」。"""
    d = tempfile.mkdtemp(prefix="e234_iso_")
    try:
        try:
            ec.assert_isolation_before_write(os.path.join(d, "e234_dryrun_x"),
                                             ec.KIND_DEVICE)
        except RuntimeError as e:
            assert "真实采集" in str(e)
        else:
            raise AssertionError("真实采集被允许写进 dry-run 目录")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_the_isolation_assert_fires_before_the_directory_is_even_created():
    """assert-before-write：断言必须发生在**产出任何字节之前**（D-306 反面）。

    这条测的不是「抛没抛」，是「抛的时候盘上有没有留下东西」——
    D-306 记的正是「失败发生在已经产出一部分之后，操作者拿到半套交付物」。
    """
    d = tempfile.mkdtemp(prefix="e234_iso_")
    try:
        bad = os.path.join(d, "not_marked_at_all")
        try:
            ec.write_run_kind(bad, ec.KIND_DRY_RUN)
        except RuntimeError:
            pass
        else:
            raise AssertionError("没抛")
        assert not os.path.exists(bad), "目录已经被建出来了 —— 断言跑在了写盘之后"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_the_calibration_front_door_refuses_a_dry_run_corpus():
    ok, why = ec.refuse_calibration_from_dry_run(ec.KIND_DRY_RUN)
    assert ok is False and "T_quiet" in why
    assert ec.refuse_calibration_from_dry_run(ec.KIND_DEVICE)[0] is True


def test_an_unknown_run_kind_is_treated_as_conservatively_as_a_real_one():
    """缺 `RUN_KIND.json` 是合法的历史状态（E1 两个归档目录就没有），但不许当成 dry-run。"""
    d = tempfile.mkdtemp(prefix="e234_kind_")
    try:
        assert ec.read_run_kind(d)["kind"] is None
        assert ec.is_dry_run(d) is False
        assert ec.refuse_calibration_from_dry_run(None)[0] is True
        assert ec.banner_lines(None) and "来源不明" in ec.banner_lines(None)[0]
        assert ec.banner_lines(ec.KIND_DRY_RUN)[0].startswith("⚠ DRY_RUN")
        assert ec.banner_lines(ec.KIND_DEVICE) == []
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_run_kind_roundtrips_through_disk():
    d = tempfile.mkdtemp(prefix="e234_dryrun_")
    try:
        ec.write_run_kind(d, ec.KIND_DRY_RUN, {"scenario": "x"})
        body = ec.read_run_kind(d)
        assert body["kind"] == ec.KIND_DRY_RUN and body["scenario"] == "x"
        assert ec.is_dry_run(d) is True
        with open(os.path.join(d, ec.RUN_KIND_FILE), "w", encoding="utf-8") as fh:
            fh.write("{ not json")
        assert ec.read_run_kind(d)["kind"] is None
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_write_report_refuses_a_missing_directory_before_computing_anything():
    """D-306：`--out-md` 指向不存在的目录时**在算完之后**崩掉，是 e1 至今的待办。"""
    try:
        ec.write_report(os.path.join(tempfile.gettempdir(), "no_such_dir_e234", "a.md"), "x")
    except RuntimeError as e:
        assert "落点目录不存在" in str(e)
    else:
        raise AssertionError("写进了一个不存在的目录")


# ── 会话层 ────────────────────────────────────────────────────────────────
def test_content_events_are_filtered_by_package_not_merely_by_tag():
    """T14 §4.2：`_cadence_check` 不按 pkg 过滤，别的 App 一条就能得出结论。"""
    lines = [_evt(0, BOOT0, "com.larus.nova"),
             _evt(10, BOOT0 + 10_000_000, "com.android.launcher"),
             _evt(20, BOOT0 + 20_000_000, "com.larus.nova")]
    evts, other_pkg, bad_dim = es.content_events(lines, "com.larus.nova")
    assert len(evts) == 2 and other_pkg == 1 and bad_dim == 0


def test_content_events_drop_truncated_timestamps_and_say_how_many():
    lines = [_evt(0, BOOT0), _evt(10, 42)]
    evts, _o, bad_dim = es.content_events(lines, "com.larus.nova")
    assert len(evts) == 1 and bad_dim == 1


def test_marks_are_refused_when_the_wall_to_boot_fit_did_not_pass():
    """没有换算依据时给出的标记时刻是编的，而编出来的时刻会安静地改变分母。"""
    lines = [_mark(1000, es.KIND_ANSWER_COMPLETE, 1)]
    assert es.parse_marks(lines, {"status": ec.NOT_EXECUTED}) == []


def test_marks_convert_through_the_measured_offset():
    ev = [_evt(1000 * i, BOOT0 + i * 1_000_000_000) for i in range(3)]
    fit = ec.fit_wall_to_boot(ev)
    marks = es.parse_marks(ev + [_mark(5000, es.KIND_ANSWER_COMPLETE, 1)], fit)
    assert len(marks) == 1
    assert marks[0]["t_boot_ns"] == BOOT0 + 5_000_000_000


def test_turns_are_segmented_by_operator_marks_not_by_a_silence_threshold():
    """切轮若用静默门限，E4 就是拿待标定量标定它自己 —— 分离点会被造出来。"""
    lines = []
    for i in range(3):
        lines.append(_evt(1000 * i, BOOT0 + i * 1_000_000_000))
    lines.append(_mark(3000, es.KIND_ANSWER_COMPLETE, 1))
    for i in range(4, 7):
        lines.append(_evt(1000 * i, BOOT0 + i * 1_000_000_000))
    lines.append(_mark(7000, es.KIND_ANSWER_COMPLETE, 2))
    fit = ec.fit_wall_to_boot(lines)
    evts, _o, _b = es.content_events(lines, "com.larus.nova")
    turns, method = es.segment_turns(evts, es.parse_marks(lines, fit))
    assert method == es.TURN_METHOD_MARKS
    assert len(turns) == 2
    assert [len(t["events"]) for t in turns] == [3, 3]


def test_without_marks_the_whole_run_is_one_turn_and_the_method_says_so():
    lines = [_evt(1000 * i, BOOT0 + i * 1_000_000_000) for i in range(5)]
    evts, _o, _b = es.content_events(lines, "com.larus.nova")
    turns, method = es.segment_turns(evts, [])
    assert method == es.TURN_METHOD_WHOLE_RUN and len(turns) == 1
    assert len(turns[0]["events"]) == 5


def test_read_jsonl_survives_a_half_written_line():
    d = tempfile.mkdtemp(prefix="e234_dryrun_")
    try:
        with open(os.path.join(d, "x.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"a": 1}) + "\n{ half")
        assert ec.read_jsonl(d, "x.jsonl") == [{"a": 1}]
    finally:
        shutil.rmtree(d, ignore_errors=True)
