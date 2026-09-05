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


# ── --pin-through-session（D-409）────────────────────────────────────────
def test_pin_through_count_covers_the_whole_session_window_with_margin():
    """翻转序列必须**跨过**整段观测窗口，不能刚好卡在结束那一刻就停。

    反例：一个朴素的「不留余量」算法（`session_seconds*1000 // interval_ms`，
    整除截断、不 +2）在很多组合下会正好卡在或卡不满观测窗口末端——
    这条测试同时钉住「真实实现有余量」与「余量不是可有可无的」两件事。
    """
    session_seconds, interval_ms = 600, 800
    naive = (session_seconds * 1000) // interval_ms
    real = e2c._pin_through_count(session_seconds, interval_ms)
    assert real * interval_ms >= session_seconds * 1000
    assert real > naive, "真实实现必须比不留余量的朴素算法多翻几次"


def test_pin_through_count_never_returns_zero_for_a_short_session():
    """极短会话/超长间隔也不能算出 0 次翻转——0 次意味着刺激源自测源根本没跑起来。"""
    assert e2c._pin_through_count(1, 999999) >= 1


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


# ── 拒绝要带诊断（7-5 案 A：硬约束保留，但假拒必须有线索）──────────

def test_a_refused_window_says_what_it_actually_searched():
    """只报「查无此项」的拒绝，在板面并发编辑/格式漂移时是**无线索假拒**——
    操作者站在设备旁边，分不清是自己写错了窗号还是板上那行刚被人改过。
    故拒绝里必须带：实搜的文件、其大小、匹配方式，以及板上现有窗 ID 供比对。

    反例证伪：去掉诊断串，本条即红。
    """
    board = "…\n| DW-20260829-01 | 窗 |\n| DW-20260828-02 | 窗 |\n"
    ok, why = e2c.device_gate("ABCD1234", "ELS-AN00", True, "DW-19990101-99", board)
    assert ok is False
    assert "BRAIN_TASKBOARD.md" in why            # 搜的是哪个文件
    assert "字符" in why                           # 读到多大（空/半截一眼可见）
    assert "子串精确匹配" in why                   # 用的什么判据
    assert "DW-20260829-01" in why                 # 板上现有的，供比对


def test_a_board_with_no_window_ids_at_all_says_the_format_drifted():
    """一个窗 ID 都搜不到 ⇒ 多半是板面格式漂了，不是操作者写错——两种成因
    的处置完全不同，不能用同一句话打发。"""
    ok, why = e2c.device_gate("ABCD1234", "ELS-AN00", True, "DW-20260829-01",
                              "（这份板面没有任何窗 ID）")
    assert ok is False
    assert "一个窗 ID 都没搜到" in why and "格式漂" in why


def test_the_hint_is_truncated_but_never_silently():
    """板上窗 ID 有几十个，全列会淹掉关键信息；截断可以，**静默截断不行**。"""
    board = "\n".join("| DW-202608%02d-01 |" % d for d in range(1, 21))
    ok, why = e2c.device_gate("ABCD1234", "ELS-AN00", True, "DW-19990101-99", board)
    assert ok is False
    assert "DW-20260820-01" in why                 # 最近的在列（倒序取前 5）
    assert "另有 15 个较早的未列" in why           # 没列的如实说出数量


def test_an_unreadable_board_is_not_reported_as_a_wrong_window_id():
    """读不到板 ⇒ 说清是路径/文件的问题，别让操作者去改一个没错的窗号。"""
    ok, why = e2c.device_gate("ABCD1234", "ELS-AN00", True, "DW-20260829-01", "")
    assert ok is False
    assert "实搜路径" in why and "不是「你写错了窗号」" in why


def test_a_longer_window_id_does_not_authorise_a_shorter_one():
    """**假放行**才是这道门的真风险（大脑 2026-08-29 裁定，v2 六案实证）：
    纯子串匹配下 `DW-20260829-01` 会被板上的 `DW-20260829-011` 放行——
    一个从没被授权过的窗号解锁真机（实测复现过）。故用词边界匹配。

    边界不能只用 `\b`：窗 ID 自带连字符，`\b` 在 `-011` 处判为边界，
    正好漏掉这一族。反例证伪：改回 `in` 子串匹配，本条即红。
    """
    ok, _ = e2c.device_gate("ABCD1234", "ELS-AN00", True, "DW-20260829-01",
                            "| DW-20260829-011 | 某个更长的窗 |")
    assert ok is False, "被更长的窗号假放行了"
    # 后缀方向同理
    ok, _ = e2c.device_gate("ABCD1234", "ELS-AN00", True, "DW-20260829-01",
                            "| XDW-20260829-01 |")
    assert ok is False


def test_word_boundary_still_accepts_a_genuinely_listed_window():
    """收紧不能把真授权也挡掉——行中、行首行尾两种位置都要放行。"""
    for board in ("| DW-20260829-01 | 窗 |", "DW-20260829-01"):
        ok, why = e2c.device_gate("ABCD1234", "ELS-AN00", True,
                                  "DW-20260829-01", board)
        assert ok is True, "真授权被挡：%s" % why


# ── T90：通道 C 图层自愈（D-644）─────────────────────────────────────────

def test_a_header_only_latency_response_counts_as_zero_frames():
    """失效判据必须认「有头无帧」，**不能**认「响应为空」。

    实测（`wifi_f6_b_VOID1` 尾部）：图层被重建后每次 `--latency` 返回的是
    `16666666` 一行刷新周期 + 一个孤立回车，**退出码 0、stderr 空**。
    ⇒ 任何「检查有没有报错」的层都看不见它。
    """
    dead = "16666666\r\n\r\n"
    assert e2c._sf_frame_rows(dead) == 0, "把失效响应当成有帧了"
    alive = "16666666\n1000\t2000\t1500\n1001\t2001\t1501\n\r\n"
    assert e2c._sf_frame_rows(alive) == 2, e2c._sf_frame_rows(alive)
    assert e2c._sf_frame_rows("") == 0
    assert e2c._sf_frame_rows(None) == 0


class _FakeAdb(object):
    """只回答 `--latency` 与 `--list` 两句；图层名切换后才重新出帧。"""

    def __init__(self, live_layer):
        self.live = live_layer
        self.lists = 0

    def text(self, *args, **kw):
        if "--list" in args:
            self.lists += 1
            # 真实 `--list` 形态：`pick_layer` 靠 `RequestedLayerState{...}` 取 body。
            # ⚠ 首版夹具写的是 "handle | <name>"，正则匹配不到时 `pick_layer` 会
            # **把整行当图层名返回** —— 测试于是在验一个生产代码永远不会走到的分支。
            return "  RequestedLayerState{%s parentId=5}\n" % self.live
        if "--latency" in args:
            asked = args[-1]
            if asked != self.live:
                return "16666666\r\n\r\n"          # 死图层：有头无帧
            return "16666666\n1000\t2000\t1500\n\r\n"
        return ""


def test_the_collector_repicks_the_layer_after_frames_stop():
    """出过帧之后连续取空 ⇒ 必须重挑图层，并把 `--list` 原文落盘。

    ⚠ 触发判据可以很紧，因为**真静默产生的是重复的满帧，不是空帧**
    （静默期间不渲染 ⇒ 环缓冲不推进 ⇒ 相邻 dump 内容完全相同）。
    ⇒ 一旦该图层出过帧，零帧行就永远不合法。
    ⚠ 落盘 `--list` 那一半不是附赠：`wifi_f6_b_VOID1` 根因至今未定，
    正因为**没人在失效之后拍过一张 `--list`**。
    """
    d = tempfile.mkdtemp(prefix="t90_")
    try:
        adb = _FakeAdb("pkg/pkg.Act#100")
        acct = {"relists": []}
        new = e2c._relist_layer(adb, "pkg", "pkg/pkg.Act#99", acct,
                                os.path.join(d, "sf_layer_probe.jsonl"), 7)
        assert new == "pkg/pkg.Act#100", new
        assert acct["relists"][0]["switched"] is True, acct["relists"]
        assert acct["relists"][0]["dump_index"] == 7
        probe = os.path.join(d, "sf_layer_probe.jsonl")
        assert os.path.exists(probe), "重挑没有留下 --list 快照 ⇒ 下次照样查不出根因"
        rec = json.loads(open(probe, encoding="utf-8").read().strip())
        assert "pkg/pkg.Act#100" in rec["listing"], rec
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_a_relist_that_finds_the_same_layer_does_not_switch():
    """重挑拿回同一个名字时不许「切换」——否则日志里全是假切换，遮住真的那次。"""
    d = tempfile.mkdtemp(prefix="t90b_")
    try:
        adb = _FakeAdb("pkg/pkg.Act#100")
        acct = {"relists": []}
        same = e2c._relist_layer(adb, "pkg", "pkg/pkg.Act#100", acct,
                                 os.path.join(d, "p.jsonl"), 3)
        assert same == "pkg/pkg.Act#100"
        assert acct["relists"][0]["switched"] is False, acct["relists"]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_the_relist_trigger_covers_every_branch_it_claims():
    """三个条件逐条钉住 —— 正例反例都要，否则「永远重挑」与「永不重挑」都能全绿。"""
    N = e2c.SF_EMPTY_DUMPS_BEFORE_RELIST
    W = e2c.SF_RELIST_MIN_INTERVAL_S
    # 正例：出过帧 + 连续空够 + 间隔够
    assert e2c._should_relist(True, N, W) is True
    assert e2c._should_relist(True, N + 50, W * 3) is True
    # 反例①：还没出过帧 —— App 首帧之前的零帧是正常的，不许每格开头白重挑一次
    assert e2c._should_relist(False, N + 50, W * 3) is False
    # 反例②：空得还不够 —— 单段空可能是别的抖动
    assert e2c._should_relist(True, N - 1, W * 3) is False
    # 反例③：刚重挑过 —— 死图层每段都空，没有这条就是在上面空转
    assert e2c._should_relist(True, N, W - 0.01) is False
    # 判据本身要有意义：N 太大就永远救不回来，太小则出帧前就乱挑
    assert 1 <= N <= 5, "SF_EMPTY_DUMPS_BEFORE_RELIST=%r 偏离标定区间" % N
