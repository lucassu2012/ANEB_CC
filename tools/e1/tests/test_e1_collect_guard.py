# -*- coding: utf-8 -*-
"""E1 采集侧的设备守卫与 raw 解析反例测试。

守卫要有能证伪它的反例，不然它只是一段看起来在守的代码。本文件里最要紧的一条是
`test_p40_refused_even_with_allow_real_device`：那个旗标**不该**能放行 P40。
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tools/e1/

import e1_collect as ec  # noqa: E402


# ── 设备守卫 ──────────────────────────────────────────────────────────────
def test_emulator_allowed_by_default():
    ok, _r = ec.device_allowed("emulator-5554", "sdk_gphone64_x86_64", False)
    assert ok is True


def test_real_device_refused_without_flag():
    ok, r = ec.device_allowed("8MY0221126002537", "SomePhone", False)
    assert ok is False and "allow-real-device" in r


def test_real_device_allowed_with_flag_when_not_denied():
    ok, _r = ec.device_allowed("8MY0221126002537", "SomePhone", True)
    assert ok is True


def test_p40_refused_even_with_allow_real_device():
    """本文件的核心不变量：旗标绕不过型号 denylist。

    P40 Pro 归设备批独占（任务板 T1/T2）。若这条断言红了，说明有人把
    `--allow-real-device` 提前到了型号检查之前——那正是顶掉别人设备批的那条路径。
    """
    for model in ec.DENY_MODELS:
        ok, r = ec.device_allowed("8MY0221126002537", model, True)
        assert ok is False, model
        assert "DENY_MODELS" in r


def test_p40_refused_even_if_serial_looks_like_an_emulator():
    """次序守卫：型号检查必须在模拟器规则之前。

    序列号只是个字符串、可以被伪装，型号不容易。先查型号才是 fail-closed 的次序。
    """
    ok, _r = ec.device_allowed("emulator-5554", "ELS-AN00", False)
    assert ok is False


def test_model_match_is_case_insensitive_and_trims():
    ok, _r = ec.device_allowed("emulator-5554", "  els-an00\n", False)
    assert ok is False


def test_model_match_treats_underscore_and_hyphen_as_the_same():
    """同一台 P40 在两处的写法不一样，denylist 必须两种都认。

    `getprop ro.product.model` 给 `ELS-AN00`；`adb devices -l` 的 `model:` 字段
    给 `ELS_AN00`（adb 在那一栏把非字母数字换成下划线）。本轮实机 `adb devices -l`
    实测输出即 `model:ELS_AN00`——只写连字符形，守卫在另一条读取路径上会安静地放行。
    """
    ok, r = ec.device_allowed("8MY0221126002537", "ELS_AN00", True)
    assert ok is False and "DENY_MODELS" in r


def test_empty_serial_refused():
    ok, r = ec.device_allowed("", "sdk_gphone64_x86_64", False)
    assert ok is False and "--serial" in r


def test_unknown_model_does_not_open_the_door_for_real_devices():
    """型号读不到（空串）时，真机仍需显式旗标——未知不等于安全。"""
    ok, _r = ec.device_allowed("8MY0221126002537", "", False)
    assert ok is False


# ── screencap raw 解析 ────────────────────────────────────────────────────
def _raw(width, height, header_fields, fill):
    head = struct.pack("<III", width, height, 1)
    if header_fields == 4:
        head += struct.pack("<I", 0)
    return head + bytes(fill) * (width * height)


# ── pick_layer：选错图层不会报错，只会安静地给一份空表 ──────────────────────
# 下面这段是 2026-08-01 模拟器 dry-run 的 `dumpsys SurfaceFlinger --list` 逐字实测输出。
# 首版实现取"最后一条含包名的行"，于是选中 ActivityRecordInputSink（输入接收层，
# 永远没有帧）——`--latency` 随即只回了一行刷新周期 `16666666`、零帧记录，
# 而这与"这层确实没出帧"长得一模一样。故这里钉的是**判据**，不是"有没有返回值"。
_REAL_SF_LIST = """\
RequestedLayerState{Surface(name=85af5d8 com.aneb.e1stimulus/com.aneb.e1stimulus.StimulusActivity)/@0x6569997 - animation-leash of starting_reveal#160}
RequestedLayerState{ActivityRecord{d7e8c9a u0 com.aneb.e1stimulus/.StimulusActivity#173 parentId=172}
RequestedLayerState{6563454 Splash Screen com.aneb.e1stimulus#174 parentId=173 z=2147483647}
RequestedLayerState{Splash Screen com.aneb.e1stimulus#175 parentId=174}
RequestedLayerState{1c07d45 ActivityRecordInputSink com.aneb.e1stimulus/.StimulusActivity#177 parentId=173 z=-2147483648}
RequestedLayerState{8fc81c6 com.aneb.e1stimulus/com.aneb.e1stimulus.StimulusActivity#178 parentId=173}
RequestedLayerState{com.aneb.e1stimulus/com.aneb.e1stimulus.StimulusActivity#179 parentId=178}
RequestedLayerState{7a1b2c3 com.example.other/com.example.other.MainActivity#180 parentId=1}
"""


def test_pick_layer_on_real_dumpsys_picks_the_presenting_layer():
    got = ec.pick_layer(_REAL_SF_LIST, "com.aneb.e1stimulus")
    assert got == "com.aneb.e1stimulus/com.aneb.e1stimulus.StimulusActivity#179", got


def test_pick_layer_rejects_the_input_sink_that_the_first_version_chose():
    """这是那个真实缺陷本身：不许再选回 ActivityRecordInputSink。"""
    got = ec.pick_layer(_REAL_SF_LIST, "com.aneb.e1stimulus")
    assert "ActivityRecordInputSink" not in got
    assert "Splash Screen" not in got
    assert "animation-leash" not in got


def test_pick_layer_ignores_other_packages():
    assert ec.pick_layer(_REAL_SF_LIST, "com.example.other") == \
        "com.example.other/com.example.other.MainActivity#180"


def test_pick_layer_absent_package_is_none_not_a_guess():
    """选不出就是 None——猜一个名字去 dump，拿回的空表会被读成'没有帧'。"""
    assert ec.pick_layer(_REAL_SF_LIST, "com.aneb.notinstalled") is None
    assert ec.pick_layer("", "com.aneb.e1stimulus") is None
    assert ec.pick_layer(None, "com.aneb.e1stimulus") is None


def test_pick_layer_all_candidates_noise_is_none_not_the_least_bad_one():
    noise = ("RequestedLayerState{1c07d45 ActivityRecordInputSink com.x/.A#7 parentId=3}\n"
             "RequestedLayerState{6563454 Splash Screen com.x#8 parentId=7}\n")
    assert ec.pick_layer(noise, "com.x") is None


def test_raw_three_field_header():
    buf = _raw(4, 4, 3, (10, 20, 30, 255))
    assert abs(ec.roi_mean_from_raw(buf, 0, 0, 4, 4) - 20.0) < 1e-9


def test_raw_four_field_header_autodetected():
    """头部 3 字段与 4 字段两种形态都要读对——按数据长度自检，不按版本猜。"""
    buf = _raw(4, 4, 4, (10, 20, 30, 255))
    assert abs(ec.roi_mean_from_raw(buf, 0, 0, 4, 4) - 20.0) < 1e-9


def test_raw_length_mismatch_is_none_not_a_plausible_number():
    buf = _raw(4, 4, 3, (10, 20, 30, 255))[:-8]  # 截断
    assert ec.roi_mean_from_raw(buf, 0, 0, 4, 4) is None


def test_raw_roi_outside_frame_is_none():
    buf = _raw(4, 4, 3, (10, 20, 30, 255))
    assert ec.roi_mean_from_raw(buf, 100, 100, 10, 10) is None


def test_raw_roi_is_clipped_not_wrapped():
    """ROI 超出右下边界时应裁剪到画面内，而不是绕回去读到别的行。"""
    buf = _raw(4, 4, 3, (0, 0, 0, 255))
    assert ec.roi_mean_from_raw(buf, 2, 2, 10, 10) == 0.0


def test_raw_too_short_is_none():
    assert ec.roi_mean_from_raw(b"\x00\x01", 0, 0, 1, 1) is None


def test_adb_always_carries_serial():
    """没有不带 -s 的路径——那是顶掉别人设备的入口。"""
    argv = ec.Adb("emulator-5554")._argv(["shell", "echo", "hi"])
    assert argv[:3] == ["adb", "-s", "emulator-5554"]
