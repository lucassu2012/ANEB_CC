# -*- coding: utf-8 -*-
"""探针里那几个**承载判词**的纯函数的合成门。

🔴 探针的其余部分（开句柄、数包）只有真机能跑，但它**不承载任何判词**。
这里钉的四个都是「读数 → 一句会被读成结果的话」的转换：
`self_id_lines`（§1.5 的 `WORKTREE_DIRTY` 必须是第一行）、`same_window`（§4.3 四时刻）、
`judge_device_egress`（§5-5 三态，`UNREADABLE` 两个方向都不得满足前提）、
`_sent_count`（§3 的 `T` 取实测，取不到回 `None` 而不是名义值）。
"""
import os
import sys

_DIAG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "diag")
if _DIAG not in sys.path:
    sys.path.insert(0, _DIAG)

from decompose_2x_probe import (                                   # noqa: E402
    _sent_count, constants_verdict, judge_device_egress, same_window, self_id_lines)


def test_worktree_dirty_must_be_the_first_line():
    """🔴 脏树时 `WORKTREE_DIRTY` 必须在**第一行**——放后面等于放在没人读的地方。"""
    lines, dirty = self_id_lines("aa", "bb", " M scripts/diag/x.py")
    assert dirty is True
    assert lines[0].startswith("WORKTREE_DIRTY"), lines
    assert "不代表运行字节" in lines[0], lines[0]


def test_clean_worktree_says_so_and_is_not_dirty():
    """正对照：干净时必须说干净——否则一个恒 DIRTY 的实现也能过门。"""
    lines, dirty = self_id_lines("aa", "bb", "")
    assert dirty is False
    assert lines[0].startswith("WORKTREE_CLEAN"), lines


def test_whitespace_only_porcelain_is_clean_not_dirty():
    lines, dirty = self_id_lines("aa", "bb", "   \n  ")
    assert dirty is False, lines


def test_self_id_prints_all_three_items():
    lines, _ = self_id_lines("thesha", "thehead", " M x")
    body = "\n".join(lines)
    for need in ("thesha", "thehead", "SHA256", "rev-parse"):
        assert need in body, (need, body)


def test_same_window_positive_control():
    """正对照：真的同窗必须判过。"""
    ok, why = same_window(1.0, 1.1, 2.0, 22.0, 23.0, 23.1)
    assert ok is True, why


def test_same_window_rejects_each_of_the_four_violations():
    """四个时刻各违反一次 ⇒ 四次都必须判不同窗,且说明里点名是哪一个。"""
    base = dict(t_open_a=1.0, t_open_b=1.1, t_traffic_start=2.0,
                t_grace_end=22.0, t_close_a=23.0, t_close_b=23.1)
    for key, bad, token in (("t_open_a", 3.0, "句柄 a 开"), ("t_open_b", 3.0, "句柄 b 开"),
                            ("t_close_a", 21.0, "句柄 a 关"), ("t_close_b", 21.0, "句柄 b 关")):
        kw = dict(base)
        kw[key] = bad
        ok, why = same_window(**kw)
        assert ok is False, (key, why)
        assert token in why, (key, why)


ON = "223.5.5.5 via 192.168.137.1 dev wlan0 table 1040 src 192.168.137.129 uid 2000"
OFF = "223.5.5.5 via 10.10.0.1 dev wlan0 table 1040 src 10.10.7.37 uid 2000"


def test_device_egress_three_states_from_real_observed_strings():
    """🔴 用**真实抓到的**两行做夹具:它们共享 `dev wlan0`,只有 via／src 不同。

    ⚠ 不用「跑一次看它红不红」——那测的是那一刻的现场,而反例会自己消失。
    """
    assert judge_device_egress(ON)[0] == "ON_HOTSPOT"
    assert judge_device_egress(OFF)[0] == "OFF_HOTSPOT"
    assert "dev wlan0" in ON and "dev wlan0" in OFF, "两夹具必须共享 dev wlan0,否则本条无区分力"


def test_device_egress_unreadable_has_its_own_code_never_off_hotspot():
    """🔴 承重条：读不到**自己有一个码**。

    v1 的坑正是这里:`judge_egress` 对读不到一律 `ok=False`,
    而 §5 一旦取 `not ok` 作「已关」的前提,**四种读不到全部变成通过**。
    """
    for raw in ("", "   ", "error: device offline", "adb: device offline"):
        code, why, src = judge_device_egress(raw)
        assert code == "UNREADABLE", (raw, code, why)
        assert code != "OFF_HOTSPOT"


def test_device_egress_missing_dev_field_is_unreadable_not_a_verdict():
    code, why, src = judge_device_egress("223.5.5.5 via 192.168.137.1 src 192.168.137.129")
    assert code == "UNREADABLE", (code, why)


def test_sent_count_reads_three_locales_and_refuses_when_absent():
    """§3：`T` 取实测发包数。取不到回 `None`,**不退回名义值 20**。"""
    assert _sent_count("20 packets transmitted, 20 received, 0% packet loss") == 20
    assert _sent_count("Packets: Sent = 20, Received = 20, Lost = 0") == 20
    assert _sent_count("数据包: 已发送 = 20，已接收 = 20，丢失 = 0") == 20
    assert _sent_count("18 packets transmitted, 17 received") == 18, "必须读实测值而非常数"
    assert _sent_count("pong") is None
    assert _sent_count("") is None
    assert _sent_count(None) is None


def test_constants_verdict_requires_two_sided_agreement():
    """§2-3 双侧必须同意；不等 ⇒ NOT_EXECUTED（不是「用 PC 侧那个」）。"""
    good = dict(hot_count=1, hot_ifidx=13, up_ifidx=9, up_addr="10.10.8.9",
                up_raw="9|10.10.8.9", neighbor="192.168.137.129")
    ok, why = constants_verdict(good, "192.168.137.129")
    assert ok is True, why
    bad = dict(good)
    bad["neighbor"] = "192.168.137.55"
    ok2, why2 = constants_verdict(bad, "192.168.137.129")
    assert ok2 is False and "双侧不同意" in why2, why2


def test_constants_verdict_rejects_hot_count_not_exactly_one():
    """§2-2 `count != 1` ⇒ NOT_EXECUTED。两个方向都钉:0 与 2 都不行。"""
    for n in (0, 2, None):
        d = dict(hot_count=n, hot_ifidx=13, up_ifidx=9, up_addr="10.10.8.9",
                 up_raw="9|10.10.8.9", neighbor="192.168.137.129")
        ok, why = constants_verdict(d, "192.168.137.129")
        assert ok is False, (n, why)


def test_constants_verdict_refuses_when_device_src_missing():
    d = dict(hot_count=1, hot_ifidx=13, up_ifidx=9, up_addr="10.10.8.9",
             up_raw="9|10.10.8.9", neighbor="192.168.137.129")
    ok, why = constants_verdict(d, None)
    assert ok is False and "src token" in why, why
