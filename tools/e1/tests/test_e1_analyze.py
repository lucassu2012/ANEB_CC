# -*- coding: utf-8 -*-
"""E1 判读侧反例测试。

每条不变量一个"违规夹具"（断言被捉）+ 一个"合规夹具"（断言放行）。
夹具全在内存，不碰设备、不碰真 logcat。

本文件钉的是判读的**判断**，不是它的措辞：断言尽量落在数字与状态词上，
落在文案上的那种测试改一句话就红，且改一个常量它反而不红（D-318 形状）。
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tools/e1/

import e1_analyze as ea  # noqa: E402

INT64_MAX = (1 << 63) - 1


# ── 夹具 ──────────────────────────────────────────────────────────────────
def _stim_lines(count=6, warmup=2, interval_ms=2000, frame_ms=16.667,
                commit_gap_ns=5_000_000, boot_off_ns=7_000_000_000):
    """一串合规的刺激日志。commit 时刻 = req + commit_gap_ns。"""
    L = ["01-01 00:00:00.000 I/E1_STIM( 100): E1_STIM CFG interval_ms=%d count=%d "
         "roi_px=480 warmup=%d refresh_hz=%.3f frame_ms=%.3f density=3.0 "
         "screen_px=1080x2340 boot_mono_offset_ns=%d"
         % (interval_ms, count, warmup, 1000.0 / frame_ms, frame_ms, boot_off_ns)]
    for seq in range(1, count + 1):
        mono = 1_000_000_000 + seq * interval_ms * 1_000_000
        boot = mono + boot_off_ns
        L.append("01-01 00:00:00.000 I/E1_STIM( 100): E1_STIM FLIP seq=%d color=%s "
                 "warmup=%s t_req_boot_ns=%d t_req_mono_ns=%d"
                 % (seq, "B" if seq % 2 else "A", "true" if seq <= warmup else "false",
                    boot, mono))
        L.append("01-01 00:00:00.000 I/E1_STIM( 100): E1_STIM COMMIT seq=%d "
                 "t_commit_boot_ns=%d t_commit_mono_ns=%d"
                 % (seq, boot + commit_gap_ns, mono + commit_gap_ns))
    return L


def _sf_text(count=6, interval_ms=2000, frame_ms=16.667, commit_gap_ns=5_000_000,
             present_delay_ns=8_000_000):
    """与 _stim_lines 对得上的一份 SurfaceFlinger latency。"""
    period_ns = int(frame_ms * 1_000_000)
    rows = [str(period_ns)]
    for seq in range(1, count + 1):
        mono = 1_000_000_000 + seq * interval_ms * 1_000_000
        actual = mono + commit_gap_ns + present_delay_ns
        rows.append("%d\t%d\t%d" % (actual - period_ns, actual, actual - 1_000_000))
    return "\n".join(rows)


# ── 刺激日志解析 ──────────────────────────────────────────────────────────
def test_stim_cfg_and_flips_parsed():
    cfg, flips = ea.parse_stim_log(_stim_lines(count=6, warmup=2))
    assert cfg["interval_ms"] == 2000 and cfg["count"] == 6 and cfg["warmup"] == 2
    assert cfg["frame_ms"] is not None
    assert len(flips) == 6
    assert flips[1]["warmup"] is True and flips[3]["warmup"] is False
    assert flips[1]["t_commit_mono_ns"] is not None


def test_parses_the_real_logcat_line_shape_not_just_our_fixture_shape():
    """夹具自洽 ≠ 与生产者真写出的形状对过账。

    下面三行是 2026-08-01 模拟器 dry-run 里 `logcat -s E1_STIM:I` 的**逐字实测输出**。
    首版正则写死了 "E1_STIM CFG" 相邻，离线 37 条全绿，而这三行一条也解析不出来——
    因为标签只在前缀 `I/E1_STIM ( 5939):` 里出现一次，消息体不重复标签（D-309 形状）。
    """
    real = [
        "--------- beginning of main",
        "08-01 07:05:12.776 I/E1_STIM ( 5939): CFG interval_ms=1500 count=10 roi_px=480 "
        "warmup=2 refresh_hz=60.000004 frame_ms=16.667 density=2.625 screen_px=1080x2400 "
        "boot_mono_offset_ns=-31200",
        "08-01 07:05:14.708 I/E1_STIM ( 5939): FLIP seq=1 color=B warmup=true "
        "t_req_boot_ns=1271036972171 t_req_mono_ns=1271036996371",
        "08-01 07:05:15.272 I/E1_STIM ( 5939): COMMIT seq=1 "
        "t_commit_boot_ns=1271600800971 t_commit_mono_ns=1271600831471",
    ]
    cfg, flips = ea.parse_stim_log(real)
    assert cfg["interval_ms"] == 1500 and cfg["count"] == 10 and cfg["warmup"] == 2
    assert abs(cfg["frame_ms"] - 16.667) < 1e-9
    assert cfg["boot_mono_offset_ns"] == -31200
    assert len(flips) == 1
    assert flips[1]["warmup"] is True
    assert flips[1]["t_commit_mono_ns"] == 1271600831471


def test_orphan_commit_does_not_invent_a_flip():
    """COMMIT 先于 FLIP 到（FLIP 行被环缓冲冲掉）时不得凭空造出一次翻转。"""
    lines = ["01-01 I/E1_STIM: E1_STIM COMMIT seq=99 t_commit_boot_ns=1 t_commit_mono_ns=1"]
    _cfg, flips = ea.parse_stim_log(lines)
    assert flips == {}


def test_duplicate_seq_is_counted_not_silent():
    """App 被重启导致 seq 重号时，覆盖必须留痕——静默覆盖会让分母悄悄变小。"""
    lines = _stim_lines(count=3, warmup=0) + _stim_lines(count=3, warmup=0)[1:]
    cfg, _flips = ea.parse_stim_log(lines)
    assert cfg.get("duplicate_seq") == 3
    # 这份夹具用 [1:] 剥掉了第二段的 CFG 行——只有一个 CFG 块，
    # 不该触发多块告警；反例见下面两条（D-409 K-2）。
    assert cfg.get("cfg_blocks") is None


def test_single_cfg_block_is_not_flagged_as_multi_block():
    """合规夹具：一次会话只有一个 CFG 块，不该出现多块告警键。"""
    cfg, _flips = ea.parse_stim_log(_stim_lines(count=6, warmup=0))
    assert cfg.get("cfg_blocks") is None
    md = ea.render_markdown(ea.analyze(_stim_lines(count=6, warmup=0), [], "", "", []))
    assert "CFG 块" not in md


def test_multiple_cfg_blocks_are_counted_and_the_header_caveat_renders():
    """违规夹具（D-409 K-2 原始形状）：App 重启产生两段完整 CFG，
    表头只反映最后一段，必须显式告警，不能让读者拿表头 interval_ms 当全局配置用。
    """
    lines = _stim_lines(count=3, warmup=0, interval_ms=2000) + \
        _stim_lines(count=3, warmup=0, interval_ms=800)
    cfg, _flips = ea.parse_stim_log(lines)
    assert cfg.get("cfg_blocks") == 2
    assert cfg["interval_ms"] == 800  # 表头 = 最后一块，不是合并值
    md = ea.render_markdown(ea.analyze(lines, [], "", "", []))
    assert "2 个 CFG 块" in md and "D-409 K-2" in md


def test_warmup_flips_dropped_and_commitless_dropped():
    cfg, flips = ea.parse_stim_log(_stim_lines(count=6, warmup=2))
    assert cfg["warmup"] == 2
    flips[5]["t_commit_mono_ns"] = None  # 该帧没触发提交回调
    good = ea.usable_flips(flips)
    assert [f["seq"] for f in good] == [3, 4, 6]


def test_clock_offset_recovered_and_spread_reported():
    good = ea.usable_flips(ea.parse_stim_log(_stim_lines(count=5, warmup=0))[1])
    off, spread, n = ea.clock_offset_ns(good)
    assert off == 7_000_000_000 and spread == 0 and n == 5


# ── SurfaceFlinger / framestats ───────────────────────────────────────────
def test_sf_latency_drops_pending_frames_not_counts_them_as_zero():
    text = "\n".join(["16666666",
                      "1000\t2000\t1500",
                      "0\t0\t0",
                      "1\t%d\t%d" % (INT64_MAX, INT64_MAX),
                      "3000\t4000\t3500"])
    period, frames = ea.parse_sf_latency(text)
    assert period == 16666666
    assert [f["actual_ns"] for f in frames] == [2000, 4000]


def _framestats_text(count=6, interval_ms=2000, commit_gap_ns=5_000_000,
                     present_delay_ns=8_000_000):
    """与 `_stim_lines` 对得上的一份 framestats（L-2）。同构 `_sf_text`。"""
    header = "Flags,IntendedVsync,Vsync,SwapBuffersCompleted"
    lines = [header]
    for seq in range(1, count + 1):
        mono = 1_000_000_000 + seq * interval_ms * 1_000_000
        actual = mono + commit_gap_ns + present_delay_ns
        lines.append("0,0,0,%d" % actual)
    return "\n".join(lines)


# ── L-2（2026-08-02）：framestats 交叉验证 ───────────────────────────────────
def test_dedup_framestats_present_times_collapses_exact_duplicates():
    """`_dump_channel_c` 周期性重叠 dump 会把同一帧的 SwapBuffersCompleted 重复
    落两次——run3 真实数据里 23 行去重后只剩 10 条，本条钉住去重本身。"""
    rows = [{"SwapBuffersCompleted": 100}, {"SwapBuffersCompleted": 200},
            {"SwapBuffersCompleted": 100}]      # 100 出现两次
    out = ea.dedup_framestats_present_times(rows)
    assert out == [{"actual_ns": 100}, {"actual_ns": 200}]


def test_dedup_framestats_skips_missing_or_zero_present_time():
    """该字段没测到时是 0（R-10：不当真值用），不是"合法的第 0 纳秒"。"""
    rows = [{"SwapBuffersCompleted": 0}, {}, {"SwapBuffersCompleted": 50}]
    assert ea.dedup_framestats_present_times(rows) == [{"actual_ns": 50}]


def test_cross_check_refuses_to_fabricate_when_one_side_has_no_data():
    """只有一条支路有数据时不虚构交叉验证结论——这条要造反例证明，不能靠推理
    （D-322）。这正是 run3 真实数据的形状：framestats 只覆盖会话头 7.2s，
    --latency 覆盖 43.6s，两者交集处的翻转仍可能一个都对不上。"""
    have_data = {"status": ea.PASS, "p50_ms": 5.0}
    no_data = {"status": ea.NOT_EXECUTED, "n": 0}
    for a, b in ((have_data, no_data), (no_data, have_data), (no_data, no_data)):
        r = ea.cross_check_channel_c(a, b, 16.667)
        assert r["status"] == ea.NOT_EXECUTED, r
        assert "p50_delta_ms" not in r, "没有可比的两侧就不该算出一个差值"


def test_cross_check_agrees_within_one_frame():
    a = {"status": ea.PASS, "p50_ms": 20.0}
    b = {"status": ea.PASS, "p50_ms": 25.0}     # 差 5ms，小于 16.667ms
    r = ea.cross_check_channel_c(a, b, 16.667)
    assert r["status"] == ea.PASS
    assert abs(r["p50_delta_ms"] - 5.0) < 1e-9


def test_cross_check_disagrees_beyond_one_frame_names_a_candidate_explanation_not_a_verdict():
    """分歧超过 1 帧时如实报，且不预设哪边对——措辞里不能出现"latency 错了"
    这类单方定论，只能是候选解释。"""
    a = {"status": ea.PASS, "p50_ms": 5.0}
    b = {"status": ea.PASS, "p50_ms": 30.0}     # 差 25ms，大于 16.667ms
    r = ea.cross_check_channel_c(a, b, 16.667)
    assert r["status"] == ea.FAIL
    assert abs(r["p50_delta_ms"] - 25.0) < 1e-9
    assert "不预设哪边对" in r["reason"]


def test_analyze_wires_framestats_channel_and_cross_check_end_to_end():
    """`analyze()` 端到端：framestats 支路与 --latency 对上同一批真值时二者一致，
    交叉验证给 PASS——同一批合成数据下两条支路本该完全一致。"""
    res = ea.analyze(_stim_lines(count=4, warmup=0), [],
                     _sf_text(count=4), _framestats_text(count=4), [])
    assert res["channel_c_framestats"]["status"] == ea.PASS
    assert res["channel_c_cross_check"]["status"] == ea.PASS
    md = ea.render_markdown(res)
    assert "C（framestats，L-2）" in md
    assert "通道 C 交叉验证" in md
    assert md.count("| C 渲染时间线") == 1     # 既有行的字面量没被撞车


def test_analyze_framestats_absent_reports_not_executed_not_zero():
    res = ea.analyze(_stim_lines(count=4, warmup=0), [], _sf_text(count=4), "", [])
    assert res["channel_c_framestats"]["status"] == ea.NOT_EXECUTED
    assert res["channel_c_cross_check"]["status"] == ea.NOT_EXECUTED
    md = ea.render_markdown(res)
    assert "NOT_EXECUTED" in md.split("交叉验证")[1]


def test_sf_latency_empty_input_is_none_not_zero():
    period, frames = ea.parse_sf_latency("")
    assert period is None and frames == []


# ── T40：--latency 多 dump 拼接去重（DW-20260803-03 实测 86% 重复）───────────
def test_dedup_sf_latency_frames_collapses_exact_duplicates():
    """同结构、同根因的 `dedup_framestats_present_times` 姊妹测试——`_dump_
    channel_c` 周期性重叠 dump 会把同一帧的 actual_ns 重复落两次。"""
    frames = [{"actual_ns": 100, "desired_ns": 90, "ready_ns": 95},
             {"actual_ns": 200, "desired_ns": 190, "ready_ns": 195},
             {"actual_ns": 100, "desired_ns": 90, "ready_ns": 95}]      # 100 重复
    out = ea.dedup_sf_latency_frames(frames)
    assert [f["actual_ns"] for f in out] == [100, 200]


def test_dedup_sf_latency_frames_preserves_full_dict_not_just_actual_ns():
    """去重不能把 `desired_ns`/`ready_ns` 丢掉——跟 framestats 那份不同，
    sf_latency 的帧字典本来就带这些字段，去重只应该做去重这一件事。"""
    frames = [{"actual_ns": 100, "desired_ns": 90, "ready_ns": 95}]
    out = ea.dedup_sf_latency_frames(frames)
    assert out == frames


def test_analyze_multi_dump_sf_latency_dedup_does_not_change_the_verdict():
    """核心不变量（DW-20260803-03 实测证实）：把同一份 dump 拼接两次（模拟周期性
    重叠采集），去重前后 `align_present` 的判定结果必须逐位相同——`align_present`
    对每次翻转只取"commit 之后最近一帧"的单一匹配，重复行不改变匹配到的时刻。
    """
    stim = _stim_lines(count=4, warmup=0)
    single = _sf_text(count=4)
    duplicated = single + "\n" + single       # 两份完全相同的 dump 拼接
    res_single = ea.analyze(stim, [], single, "", [])
    res_dup = ea.analyze(stim, [], duplicated, "", [])
    assert res_dup["channel_c"] == res_single["channel_c"]
    assert res_dup["channel_c_verdict"] == res_single["channel_c_verdict"]
    assert res_dup["sf_frames"]["duplicate_dropped"] > 0
    assert res_single["sf_frames"]["duplicate_dropped"] == 0


def test_render_reports_dedup_line_only_when_duplicates_exist():
    """单 dump（无重复）时不冒出"原始行数不等于捕捉到的帧数"这行——避免给
    每一份正常报告都加一句用不上的免责声明。"""
    stim = _stim_lines(count=4, warmup=0)
    single = _sf_text(count=4)
    md_single = ea.render_markdown(ea.analyze(stim, [], single, "", []))
    md_dup = ea.render_markdown(ea.analyze(stim, [], single + "\n" + single, "", []))
    assert "原始行" not in md_single
    assert "原始行" in md_dup


def test_framestats_read_by_header_name_not_index():
    """列集变了也要读对：加一列 GpuCompleted 后 FrameCompleted 仍须取到同一个值。"""
    a = "Flags,IntendedVsync,Vsync,FrameCompleted\n0,10,20,30\n"
    b = "Flags,IntendedVsync,Vsync,FrameCompleted,GpuCompleted\n0,10,20,30,40\n"
    ra, rb = ea.parse_framestats(a), ea.parse_framestats(b)
    assert ra[0]["FrameCompleted"] == 30
    assert rb[0]["FrameCompleted"] == 30  # 按下标读会在这里取到 40


def test_framestats_skips_rows_whose_width_mismatches():
    text = "Flags,IntendedVsync,Vsync,FrameCompleted\n0,10,20,30\n0,10,20\n"
    assert len(ea.parse_framestats(text)) == 1


# 下面这一行是 `evidence/e1/20260801-170127/framestats.txt` 的**逐字表头**
# （2026-08-01 模拟器 dry-run 归档）。它以逗号结尾——首版解析器不剥这个空字段，
# 于是真实 framestats 无论数据行带不带尾逗号都解析出 **0 行**。
# 该缺陷此前无人察觉：模拟器上 PROFILEDATA 本就是空的，而 `framestats_rows`
# 是只写不读字段（T14 §4.2），没有任何一个面会因为它恒为 0 而变红。
_REAL_FRAMESTATS_HEADER = (
    "Flags,FrameTimelineVsyncId,IntendedVsync,Vsync,InputEventId,HandleInputStart,"
    "AnimationStart,PerformTraversalsStart,DrawStart,FrameDeadline,FrameInterval,"
    "FrameStartTime,SyncQueued,SyncStart,IssueDrawCommandsStart,SwapBuffers,"
    "FrameCompleted,DequeueBufferDuration,QueueBufferDuration,GpuCompleted,"
    "SwapBuffersCompleted,DisplayPresentTime,CommandSubmissionCompleted,")


def test_framestats_parses_the_real_header_shape_which_ends_in_a_comma():
    row = ",".join(str(100 + i) for i in range(23)) + ","
    rows = ea.parse_framestats(_REAL_FRAMESTATS_HEADER + "\n" + row + "\n")
    assert len(rows) == 1, "真实 framestats 形状解析出 0 行"
    assert rows[0]["FrameCompleted"] == 116
    assert "" not in rows[0]


def test_framestats_still_accepts_rows_without_the_trailing_comma():
    """剥尾逗号不能把「表头有、数据行没有」这一路也一起放行错列。"""
    row = ",".join(str(100 + i) for i in range(23))
    rows = ea.parse_framestats(_REAL_FRAMESTATS_HEADER + "\n" + row + "\n")
    assert len(rows) == 1 and rows[0]["Flags"] == 100


# ── 对齐 ──────────────────────────────────────────────────────────────────
def test_align_picks_first_frame_after_commit():
    _cfg, flips = ea.parse_stim_log(_stim_lines(count=4, warmup=0))
    good = ea.usable_flips(flips)
    _p, frames = ea.parse_sf_latency(_sf_text(count=4))
    aligned, missed = ea.align_present(good, frames, max_gap_ns=100_000_000)
    assert missed == []
    assert len(aligned) == 4
    assert abs(aligned[0]["delta_ms"] - 8.0) < 1e-6


def test_align_refuses_when_gap_exceeds_budget():
    """帧离得太远时记 missed，而不是硬配一帧——硬配会产出一个像样的错数。"""
    _cfg, flips = ea.parse_stim_log(_stim_lines(count=2, warmup=0))
    good = ea.usable_flips(flips)
    _p, frames = ea.parse_sf_latency(_sf_text(count=2, present_delay_ns=900_000_000))
    aligned, missed = ea.align_present(good, frames, max_gap_ns=60_000_000)
    assert aligned == [] and len(missed) == 2


# ── 汇总与判据 ────────────────────────────────────────────────────────────
def test_summarize_empty_is_not_executed_not_a_row_of_zeros():
    s = ea.summarize([])
    assert s["status"] == ea.NOT_EXECUTED and s["n"] == 0
    assert "p50_ms" not in s


def test_gate_uses_measured_frame_not_hardcoded_33ms():
    """把 33ms 写死会让这条通过——20ms 的 p99 在 60Hz 屏上是 FAIL。

    这正是 spec §3.1 说的那件事：门限按实测刷新率换算，不硬编码 33
    （一个常量被改后谁还在用旧基数算它，D-312）。
    """
    s = {"status": ea.PASS, "p99_ms": 20.0}
    assert ea.gate_verdict(s, 16.667)[0] == ea.FAIL
    assert ea.gate_verdict(s, 33.333)[0] == ea.PASS


def test_gate_without_frame_ms_is_not_executed_not_fail():
    s = {"status": ea.PASS, "p99_ms": 1.0}
    assert ea.gate_verdict(s, None)[0] == ea.NOT_EXECUTED


def test_gate_on_empty_summary_is_not_executed():
    assert ea.gate_verdict(ea.summarize([]), 16.667)[0] == ea.NOT_EXECUTED


# ── 通道 A ────────────────────────────────────────────────────────────────
def test_channel_a_without_per_event_timestamps_is_not_executed():
    """今天的实现只打 click 型 ADAPTER_EVT（无 t_boot_ns）与 5s 聚合。

    通道 A 必须报 NOT_EXECUTED 并给原因，**绝不用聚合值折算出一个数**。
    """
    adapter = ["01-01 I/AnebProbe: ADAPTER_EVT type=click cls=android.widget.Button "
               "desc=null txt_len=0 pkg=com.x",
               "01-01 I/AnebProbe: ADAPTER_OBS pkg=com.x mode=generic events=8 "
               "first_delta_ms=12.0 cadence_p50_ms=2000.0"]
    res = ea.analyze(_stim_lines(count=4, warmup=0), adapter, _sf_text(count=4), "", [])
    assert res["channel_a"]["status"] == ea.NOT_EXECUTED
    assert res["channel_a_verdict"][0] == ea.NOT_EXECUTED
    assert "逐事件时戳" in res["channel_a"]["reason"]


def test_channel_a_reads_per_event_timestamps_when_present():
    """提案落地后的形态：带 t_boot_ns 的 ADAPTER_EVT 行应被判读出分布。"""
    stim = _stim_lines(count=4, warmup=0)
    _cfg, flips = ea.parse_stim_log(stim)
    adapter = []
    for seq in sorted(flips):
        t = flips[seq]["t_commit_boot_ns"] + 3_000_000  # 事件比提交晚 3ms
        adapter.append("01-01 I/AnebProbe: ADAPTER_EVT type=content cls=X txt_len=3 "
                       "pkg=com.aneb.e1stimulus t_boot_ns=%d" % t)
    res = ea.analyze(stim, adapter, _sf_text(count=4), "", [])
    a = res["channel_a"]
    assert a["status"] == ea.PASS and a["n"] == 4
    # 事件比提交晚 3ms，上屏比提交晚 8ms → 事件相对上屏为 −5ms
    assert abs(a["p50_ms"] + 5.0) < 1e-6


def test_channel_a_refuses_when_clock_offset_missing():
    """缺时钟偏移时宁可不报，也不拿「偏移=0」去减出一个看着合理的错数。"""
    good = [{"seq": 1, "t_commit_boot_ns": 10, "t_commit_mono_ns": 10}]
    s, v, _r = ea._analyze_channel_a(good, [], [{"t_boot_ns": 11}], None, 16.667, 10 ** 9)
    assert s["status"] == ea.NOT_EXECUTED and v == ea.NOT_EXECUTED


def test_cadence_check_is_three_valued_not_a_score():
    obs = [{"cadence_p50_ms": 2000.0}]
    assert ea._cadence_check(obs, 2000)["status"] == "MATCH"
    assert ea._cadence_check([{"cadence_p50_ms": 100.0}], 2000)["status"] == "MISMATCH"
    assert ea._cadence_check([], 2000)["status"] == ea.NOT_EXECUTED
    assert ea._cadence_check(obs, None)["status"] == ea.NOT_EXECUTED


# ── 通道 B ────────────────────────────────────────────────────────────────
def test_channel_b_reports_period_never_a_timing_error():
    rows = [{"t_host_ns": i * 300_000_000, "roi_mean": 0.0 if i % 2 else 255.0}
            for i in range(6)]
    st = ea.screencap_sampling_stats(ea.parse_screencap_index(rows), 8.0)
    assert st["status"] == ea.PASS and st["n"] == 6
    assert st["transitions_detected"] == 5
    assert abs(st["period_ms_p50"] - 300.0) < 1e-6
    # 刻意不提供任何"误差"键：B 报时间误差就是伪精确（spec §2.2）
    assert not any(k.startswith("delta") or k.endswith("_error") for k in st)


def test_channel_b_single_sample_is_not_executed():
    st = ea.screencap_sampling_stats([{"t_host_ns": 1, "roi_mean": 1.0}], 8.0)
    assert st["status"] == ea.NOT_EXECUTED


# ── --stim-file（D-407：复用 e234_collect 产物，e1_collect 红线不动）───────
def _write_run_dir(d, stim_name, count):
    """在 run-dir 里落一份最小可判读的采集产物，stim 部分按 stim_name 命名。

    `_stim_lines()` 返回的字符串不带尾部换行（供内存态直接喂给解析函数用）；
    落盘时必须手动补 `\\n`——`writelines()` 不做这件事，漏了会把整批日志拼成一行，
    真机文件必有换行、这个坑只在测试夹具里才会犯。
    """
    with open(os.path.join(d, stim_name), "w", encoding="utf-8") as fh:
        fh.write("\n".join(_stim_lines(count=count, warmup=0)) + "\n")
    with open(os.path.join(d, "adapter.log"), "w", encoding="utf-8") as fh:
        pass
    with open(os.path.join(d, "sf_latency.txt"), "w", encoding="utf-8") as fh:
        fh.write(_sf_text(count=count))
    with open(os.path.join(d, "framestats.txt"), "w", encoding="utf-8") as fh:
        pass
    with open(os.path.join(d, "screencap_index.jsonl"), "w", encoding="utf-8") as fh:
        pass


def test_stim_file_default_still_reads_stim_log_not_a_renamed_file():
    """不给 --stim-file 时必须还是读 stim.log——向后兼容，e1_collect 的老产物不受影响。"""
    with tempfile.TemporaryDirectory() as d:
        _write_run_dir(d, "stim.log", count=3)
        # 同目录另放一份不同翻转数的 stim_pre.log：若默认值悄悄漂移到它身上，这条会把它测出来。
        with open(os.path.join(d, "stim_pre.log"), "w", encoding="utf-8") as fh:
            fh.write(chr(10).join(_stim_lines(count=9, warmup=0)) + chr(10))
        out_md = os.path.join(d, "out.md")
        rc = ea.main(["--run-dir", d, "--out-md", out_md])
        assert rc == 0
        with open(out_md, encoding="utf-8") as fh:
            md = fh.read()
        # 精确落在渲染出的那一行：数字来自 stim.log(3)，不是 stim_pre.log(9)。
        assert "| 3 / 3 |" in md
        assert "| 9 / 9 |" not in md


def test_stim_file_flag_redirects_to_e234_collect_output_name():
    """给 --stim-file stim_pre.log 时必须真的读它，而不是继续读默认的 stim.log。"""
    with tempfile.TemporaryDirectory() as d:
        _write_run_dir(d, "stim_pre.log", count=7)
        # 同目录放一份翻转数不同的 stim.log：若旗标被忽略、悄悄退回默认值，这条会测出来。
        with open(os.path.join(d, "stim.log"), "w", encoding="utf-8") as fh:
            fh.write(chr(10).join(_stim_lines(count=2, warmup=0)) + chr(10))
        out_md = os.path.join(d, "out.md")
        rc = ea.main(["--run-dir", d, "--stim-file", "stim_pre.log", "--out-md", out_md])
        assert rc == 0
        with open(out_md, encoding="utf-8") as fh:
            md = fh.read()
        # 数字来自 stim_pre.log(7)，证明真的按旗标切换了文件，不是恒读 stim.log(2)。
        assert "| 7 / 7 |" in md
        assert "| 2 / 2 |" not in md


# ── frame_ms 取值来源（L-1，2026-08-02；D-413 run3 首次暴露 90Hz 自报 vs
#    60Hz 实测打架后固化为显式字段，不再只是 analyze() 里一行注释）─────────
def test_frame_ms_source_prefers_measured_and_flags_disagreement():
    """run3 的真实形状：刺激源自报 90Hz(11.111ms)，SurfaceFlinger 实测 60Hz(16.667ms)。

    判据来源必须是显式字段（不是只有渲染文案里才看得出来），且分歧必须在报告里
    被点名——不能让读者拿表头的 refresh_hz 心算出一个跟正文对不上的数。
    """
    res = ea.analyze(_stim_lines(count=4, warmup=0, frame_ms=11.111),
                     [], _sf_text(count=4, frame_ms=16.667), "", [])
    assert res["frame_ms_source"] == ea.FRAME_MS_SRC_MEASURED
    assert abs(res["frame_ms_measured"] - 16.667) < 0.01
    assert abs(res["frame_ms_from_stimulus"] - 11.111) < 0.01
    md = ea.render_markdown(res)
    assert "两个候选值不一致" in md
    assert "LTPO" in md
    assert "D-413" in md
    assert "16.667" in md and "11.111" in md


def test_frame_ms_source_is_stimulus_when_sf_latency_absent():
    """没有 sf_latency 数据时回退到刺激源自报，且不该渲染一条"分歧"提示——
    只有一个候选值，谈不上分歧。"""
    res = ea.analyze(_stim_lines(count=4, warmup=0, frame_ms=11.111), [], "", "", [])
    assert res["frame_ms_source"] == ea.FRAME_MS_SRC_STIMULUS
    assert abs(res["frame_ms_measured"] - 11.111) < 0.01
    md = ea.render_markdown(res)
    assert "两个候选值不一致" not in md
    assert "刺激源自报" in md


def test_no_disagreement_caveat_when_measured_and_stimulus_agree():
    """两个候选值本就一致（同一块面板、没有 LTPO 降频）时不该无中生有一条警告。"""
    res = ea.analyze(_stim_lines(count=4, warmup=0, frame_ms=16.667),
                     [], _sf_text(count=4, frame_ms=16.667), "", [])
    assert res["frame_ms_source"] == ea.FRAME_MS_SRC_MEASURED
    md = ea.render_markdown(res)
    assert "两个候选值不一致" not in md


# ── 端到端渲染 ────────────────────────────────────────────────────────────
def test_render_reports_measured_frame_and_channel_verdicts():
    res = ea.analyze(_stim_lines(count=4, warmup=0), [], _sf_text(count=4), "", [])
    md = ea.render_markdown(res)
    assert "E1 已知真值刺激实验" in md
    assert "NOT_EXECUTED" in md          # 通道 A 今天必然是它
    assert "16.666" in md or "16.667" in md
    # 三条通道各占一行，绝不合并成一个"总误差"
    assert md.count("| A 无障碍事件") == 1
    assert md.count("| C 渲染时间线") == 1
    assert md.count("| B screencap 帧差") == 1


# ── G-2 本义独立于「总量 vs 1 帧」（D-417/D-418）────────────────────────────
def test_g2_true_meaning_is_a_fixed_not_executed_value():
    """G-2 本义在 E2 把 E_pipeline 从总量里分解出去之前恒为 NOT_EXECUTED——
    这是一个固定值，不看任何输入（D-417/D-418）。"""
    assert ea.g2_true_meaning()[0] == ea.NOT_EXECUTED


def test_g2_true_meaning_does_not_move_with_the_total_verdict():
    """总量判定可以是 PASS 也可以是 FAIL，G-2 本义两种情况下都不变——
    证明两者是独立字段，不是同一个判断换了个措辞（D-417/D-418 形状）。
    """
    passing = {"status": ea.PASS, "p99_ms": 1.0}
    failing = {"status": ea.PASS, "p99_ms": 999.0}
    assert ea.gate_verdict(passing, 16.667)[0] == ea.PASS
    assert ea.g2_true_meaning()[0] == ea.NOT_EXECUTED
    assert ea.gate_verdict(failing, 16.667)[0] == ea.FAIL
    assert ea.g2_true_meaning()[0] == ea.NOT_EXECUTED


def test_analyze_carries_g2_true_meaning_independent_of_channel_c_verdict():
    """端到端：合规夹具下通道 C 总量本该 PASS，但 g2_true_meaning 字段
    仍独立存在且为 NOT_EXECUTED——不是从 channel_c_verdict 派生或复制出来的
    （run3 真机数据是反过来的形状：总量 FAIL、G-2 本义同样 NOT_EXECUTED，
    见 docs/G2_REACHABILITY_MEMO_20260802.md；这里用合成数据钉住"不管总量
    是哪个状态词，G-2 本义都不跟着变"这条不变量）。
    """
    res = ea.analyze(_stim_lines(count=4, warmup=0), [], _sf_text(count=4), "", [])
    assert res["channel_c_verdict"][0] == ea.PASS
    assert res["g2_true_meaning"][0] == ea.NOT_EXECUTED
    assert res["g2_true_meaning"] != res["channel_c_verdict"]


def test_render_shows_total_and_g2_true_meaning_as_two_separate_lines():
    """渲染层：「总量 vs 1 帧」列头与「G-2 本义」是两处独立文本，各出现一次，
    且 G-2 本义那一行的状态词固定为 NOT_EXECUTED，不随总量列的判定变化。
    """
    res = ea.analyze(_stim_lines(count=4, warmup=0), [], _sf_text(count=4), "", [])
    md = ea.render_markdown(res)
    assert "总量 vs 1 帧" in md
    g2_lines = [ln for ln in md.splitlines() if ln.startswith("**G-2 本义")]
    assert len(g2_lines) == 1              # 判定行只出现一次，不重复
    assert ea.NOT_EXECUTED in g2_lines[0]  # 即便总量列（见上）是 PASS，这行仍是 NOT_EXECUTED


def test_render_still_shows_g2_true_meaning_line_when_total_is_fail_shaped():
    """上一条用的是总量=PASS 夹具——单靠它测不出"G-2 本义"这行是不是被悄悄
    挂在了 `channel_c_verdict == PASS` 这个条件上（真实 run3 就是总量 FAIL
    的形状：若未来有人这样改，PASS 形状的夹具全绿，run3 形状的报告却会
    静默丢掉这行）。这里专门用总量 FAIL 的夹具钉住"该行不随总量判定的
    正负而消失"（大脑 D-421 追补③）。
    """
    res = ea.analyze(_stim_lines(count=4, warmup=0), [],
                     _sf_text(count=4, present_delay_ns=30_000_000), "", [])
    assert res["channel_c_verdict"][0] == ea.FAIL   # 确认夹具真的是 FAIL 形状
    md = ea.render_markdown(res)
    g2_lines = [ln for ln in md.splitlines() if ln.startswith("**G-2 本义")]
    assert len(g2_lines) == 1
    assert ea.NOT_EXECUTED in g2_lines[0]


# ── 候选 C 治理状态（T31，PO 批复 D-432②；D-434 措辞订正）─────────────────
def test_g2_candidate_c_is_a_fixed_governance_fact_not_a_measurement():
    """候选 C 是政策事实，不是测量结果——返回结构里不该出现 PASS/FAIL/NOT_EXECUTED
    三态词（那会诱人把治理决定读成又一次测量，同 `cadence_check()` 用
    MATCH/MISMATCH 而非 PASS/FAIL 的理由）。"""
    cc = ea.g2_candidate_c(16.667)
    assert cc["active"] is True
    assert cc["band_frames"] == 2
    for word in (ea.PASS, ea.FAIL, ea.NOT_EXECUTED):
        assert word not in cc["note"]


def test_g2_candidate_c_band_ms_is_derived_not_hardcoded():
    """带宽毫秒数必须从传入的实测 `frame_ms` 派生（D-312/D-414 纪律的延伸），
    不能是写死的 33.334——换一个帧基准，数字要跟着动；没有实测帧长时不编一个
    默认值出来（R-10：宁可 `None`，不拿假数顶上）。
    """
    assert ea.g2_candidate_c(16.667)["band_ms"] == 2 * 16.667   # 60Hz 实测
    assert ea.g2_candidate_c(11.111)["band_ms"] == 2 * 11.111   # 90Hz 自报兜底
    assert ea.g2_candidate_c(None)["band_ms"] is None


def test_g2_candidate_c_does_not_move_with_the_total_verdict():
    """总量判定可以是 PASS 也可以是 FAIL，候选 C 的治理状态（同一 frame_ms 下）
    两种情况下都不变——证明它与 `g2_true_meaning()` 一样，是独立于本次数据
    的固定字段，只随 frame_ms 这个共享输入变，不随总量判定变。
    """
    passing = {"status": ea.PASS, "p99_ms": 1.0}
    failing = {"status": ea.PASS, "p99_ms": 999.0}
    assert ea.gate_verdict(passing, 16.667)[0] == ea.PASS
    assert ea.g2_candidate_c(16.667) == ea.g2_candidate_c(16.667)
    assert ea.gate_verdict(failing, 16.667)[0] == ea.FAIL
    assert ea.g2_candidate_c(16.667) == ea.g2_candidate_c(16.667)


def test_render_shows_candidate_c_line_once_regardless_of_total_verdict():
    """渲染层：「候选 C 生效」这一行在总量 PASS 形状与 FAIL 形状下都恰好出现
    一次，带毫秒数（不是裸"~2 帧"，D-434 订正）与候选 B 升级路径——不随总量
    判定的正负而消失或复制（与「G-2 本义」那两条测试同一形状）。
    """
    for res in (
        ea.analyze(_stim_lines(count=4, warmup=0), [], _sf_text(count=4), "", []),
        ea.analyze(_stim_lines(count=4, warmup=0), [],
                   _sf_text(count=4, present_delay_ns=30_000_000), "", []),
    ):
        assert res["g2_candidate_c"]["band_ms"] == 2 * 16.667  # 两夹具帧长相同
        md = ea.render_markdown(res)
        lines = [ln for ln in md.splitlines() if ln.startswith("**候选 C 生效")]
        assert len(lines) == 1
        assert "33.334ms" in lines[0]
        assert "候选 B" in lines[0]
