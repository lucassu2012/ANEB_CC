# -*- coding: utf-8 -*-
"""E1 判读侧反例测试。

每条不变量一个"违规夹具"（断言被捉）+ 一个"合规夹具"（断言放行）。
夹具全在内存，不碰设备、不碰真 logcat。

本文件钉的是判读的**判断**，不是它的措辞：断言尽量落在数字与状态词上，
落在文案上的那种测试改一句话就红，且改一个常量它反而不红（D-318 形状）。
"""
import os
import sys

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


def test_sf_latency_empty_input_is_none_not_zero():
    period, frames = ea.parse_sf_latency("")
    assert period is None and frames == []


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
