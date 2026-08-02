# -*- coding: utf-8 -*-
"""采集侧与模拟器的反例测试。**不碰 adb、不碰设备、不碰真实语料。**

采集侧真正能离线钉住的只有三样：设备门的判定、参数解析、以及
「生产者写出来的那一行，判读侧认不认」。第三样是 T14 头条缺陷的**反向守卫**：
e1 的采集器订了一个没有生产者的 logcat 标签，通道 A 因此结构性恒零行，
而离线反例抓不到它 —— 因为夹具自己发明了那个不存在的标签（D-309/D-392②）。
所以这里的标记契约测试是**同一条流**上的往返：产出的那一行，直接喂给判读侧的解析器。
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import e234_common as ec        # noqa: E402
import e234_session as es       # noqa: E402
import e234_collect as e2c      # noqa: E402
import sim_session as sim       # noqa: E402

BOARD = "…| T17 | E2/E3/E4 执行脚本预备 | v3 | 窗号 E234-WIN-1 |…"


# ── 设备门 ────────────────────────────────────────────────────────────────
def test_p40_is_still_refused_when_no_window_is_supplied():
    ok, why = e2c.device_gate("ABCD1234", "ELS-AN00", True, None, BOARD)
    assert ok is False and "排窗授权" in why


def test_a_window_id_that_is_not_on_the_taskboard_is_refused():
    """能被现场编出来的字符串不是授权。"""
    ok, why = e2c.device_gate("ABCD1234", "ELS-AN00", True, "E234-WIN-9", BOARD)
    assert ok is False and "查无此项" in why


def test_a_window_id_found_on_the_taskboard_unlocks_the_denylisted_model():
    ok, why = e2c.device_gate("ABCD1234", "ELS-AN00", True, "E234-WIN-1", BOARD)
    assert ok is True and "E234-WIN-1" in why


def test_the_window_flag_cannot_rescue_a_device_whose_model_is_unknown():
    """D-392① 修的那条 fail-open 不许从这个新入口回来。

    型号读不到时被拒的理由**不是** denylist，所以排窗分支根本够不到它 ——
    这条测的正是「新加的旗标有没有把旧的 fail-closed 顶开」。
    """
    ok, why = e2c.device_gate("ABCD1234", "", True, "E234-WIN-1", BOARD)
    assert ok is False and "型号未知" in why


def test_a_non_emulator_serial_without_the_real_device_flag_is_still_refused():
    ok, _why = e2c.device_gate("ABCD1234", "Pixel 7", False, "E234-WIN-1", BOARD)
    assert ok is False


def test_an_emulator_passes_through_without_needing_a_window():
    ok, why = e2c.device_gate("emulator-5554", "sdk_gphone64_x86_64", False, None, "")
    assert ok is True and "模拟器" in why


def test_the_gate_refuses_when_the_taskboard_cannot_be_read():
    ok, why = e2c.device_gate("ABCD1234", "ELS-AN00", True, "E234-WIN-1", "")
    assert ok is False and "读不到任务板" in why


# ── 参数解析 ──────────────────────────────────────────────────────────────
def test_a_mistyped_roi_gets_a_sentence_not_a_stack_trace():
    """D-272：人手写的那条输入路径最容易漏，而它是以栈回溯崩掉的那条。"""
    for bad in ("", "1,2,3", "a,b,c,d", "1,2,0,5", None):
        try:
            e2c.parse_roi(bad)
        except ValueError as e:
            assert "ROI" in str(e)
        else:
            raise AssertionError("接受了一个错的 ROI: %r" % (bad,))
    assert e2c.parse_roi(" 10, 20 ,300,400 ") == (10, 20, 300, 400)


# ── 生产者/消费方契约（T14 头条缺陷的反向守卫）────────────────────────────
def test_the_mark_line_the_collector_emits_is_the_line_the_analyzer_parses():
    """采集侧打出的那一行，直接喂判读侧的解析器 —— 不许各自对着一份想象的格式。

    e1 的通道 A 恒零行，就是因为两侧对着不同的字面量，而离线夹具自己发明了
    那个不存在的标签，于是全绿（D-392②）。这里的往返把那条路堵死。
    """
    payload = e2c.mark_payload(es.KIND_ANSWER_COMPLETE, 3)
    line = "08-02 01:00:05.000 I/%s( 6001): %s\n" % (es.MARK_TAG, payload)
    evt = ("08-02 01:00:00.000 I/AnebProbe( 1): ADAPTER_EVT type=content cls=X "
           "desc=null txt_len=1 pkg=p t_boot_ns=8000000000000\n")
    evt2 = ("08-02 01:00:01.000 I/AnebProbe( 1): ADAPTER_EVT type=content cls=X "
            "desc=null txt_len=1 pkg=p t_boot_ns=8001000000000\n")
    fit = ec.fit_wall_to_boot([evt, evt2])
    marks = es.parse_marks([evt, evt2, line], fit)
    assert len(marks) == 1 and marks[0]["kind"] == es.KIND_ANSWER_COMPLETE
    assert marks[0]["t_boot_ns"] == 8_005_000_000_000


def test_mark_payload_refuses_a_kind_the_analyzer_would_silently_drop():
    try:
        e2c.mark_payload("done", 1)
    except ValueError as e:
        assert "未知标记类型" in str(e)
    else:
        raise AssertionError("产出了一个判读侧会静默丢掉的标记类型")


def test_every_mark_key_maps_to_a_kind_the_analyzer_knows():
    """按键表是手写的，所以它的**值域**要从消费方那边导出来核（D-275）。"""
    assert set(e2c.MARK_KEYS.values()) <= set(es.MARK_KINDS)


# ── 模拟器 ────────────────────────────────────────────────────────────────
def test_the_simulator_refuses_to_write_outside_a_dryrun_directory():
    d = tempfile.mkdtemp(prefix="e234_sim_")
    try:
        try:
            sim.write(os.path.join(d, "looks_like_a_real_run"), "e2_within_one_frame")
        except RuntimeError as e:
            assert ec.DRY_RUN_DIR_TOKEN in str(e)
        else:
            raise AssertionError("合成语料被允许写进一个看不出来源的目录")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_the_simulator_records_the_injected_truth_in_run_kind():
    d = tempfile.mkdtemp(prefix="e234_dryrun_sim_")
    try:
        sim.write(d, "e4_overlap")
        body = ec.read_run_kind(d)
        assert body["kind"] == ec.KIND_DRY_RUN
        assert body["injected_truth"]["separable_by_construction"] is False
        assert body["params"]["stream_gap_ms"] == sim.SCENARIOS["e4_overlap"]["stream_gap_ms"]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_the_two_e4_controls_point_in_opposite_directions_by_construction():
    """E4 唯一可能的作弊方式是把参数往「看起来可分」挪。

    两个对照组的参数是源码字面量，方向相反，且**判据由参数算出**而不是手写标签 ——
    手写标签会跟参数分叉，而分叉时它不报错。
    """
    sep = sim.build("e4_separable")["truth"]
    ovl = sim.build("e4_overlap")["truth"]
    assert sep["separable_by_construction"] is True
    assert ovl["separable_by_construction"] is False
    assert ovl["max_intra_gap_ms"] > ovl["min_post_silence_ms"]


def test_simulated_artifacts_parse_with_the_e1_parsers_not_just_with_mine():
    """合成语料要能被**既有解析器**吃下去，否则它测的是我自己的两个函数。"""
    d = tempfile.mkdtemp(prefix="e234_dryrun_sim_")
    try:
        s = sim.write(d, "e3_input_timeline_present")
        period, frames = ec.ea.parse_sf_latency(ec.read_text(d, "sf_latency.txt"))
        # 语料是**多块重叠**的（环缓冲装不下一次会话，采集侧周期性追加）：
        # 先去重再比数，这一步本身就是判读侧必须做的那一步。
        frames, dup_sf = ec.dedupe_by(frames, "actual_ns")
        assert period == sim.FRAME_NS and len(frames) == len(s["frames"])
        assert dup_sf > 0, "夹具没造出重叠 dump —— 去重那条路一次没走到"
        rows = ec.ea.parse_framestats(ec.read_text(d, "framestats.txt"))
        assert rows, "真实形状的 framestats 解析出 0 行"
        rows, dup_fs = ec.dedupe_by(rows, "IntendedVsync")
        assert len(rows) == len(s["frames"]) and dup_fs > 0
        assert "NewestInputEvent" in rows[0]
        evts, other, bad = es.content_events(ec.read_lines(d, "adapter.log"), sim.SIM_PKG)
        assert len(evts) == len(s["events"]) and other == 1 and bad == 0
        pin = ec.clock_pin(ec.read_lines(d, "stim_pre.log"),
                           ec.read_lines(d, "stim_post.log"), 16.667)
        assert pin["status"] == ec.PASS
        assert pin["offset_ns"] == sim.BOOT_MINUS_MONO_NS
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_the_new_header_scenario_really_lacks_the_input_timestamp_columns():
    """E3 的「不可锚」场景必须真的不可锚，否则那条 NOT_EXECUTED 是演出来的。"""
    d = tempfile.mkdtemp(prefix="e234_dryrun_sim_")
    try:
        sim.write(d, "e3_input_timeline_absent")
        rows = ec.ea.parse_framestats(ec.read_text(d, "framestats.txt"))
        assert rows and "NewestInputEvent" not in rows[0]
        assert "InputEventId" in rows[0]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_screencap_index_is_scalar_only_never_a_frame_path():
    """spec §2.2 红线：只落 ROI 差值标量，绝不落原始帧。"""
    d = tempfile.mkdtemp(prefix="e234_dryrun_sim_")
    try:
        sim.write(d, "e2_within_one_frame")
        rows = ec.read_jsonl(d, "screencap_index.jsonl")
        assert rows and all(r["path"] is None for r in rows)
        assert all(set(r) == {"t_host_ns", "roi_mean", "path"} for r in rows)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_simulator_output_is_deterministic_for_a_given_seed():
    a = sim.build("e2_within_one_frame", seed=7)
    b = sim.build("e2_within_one_frame", seed=7)
    assert json.dumps(a["turns"]) == json.dumps(b["turns"])
    assert [e["lag_ms"] for e in a["events"]] == [e["lag_ms"] for e in b["events"]]
