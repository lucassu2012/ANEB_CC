# -*- coding: utf-8 -*-
"""把探针的 P2 出口守卫钉住（判据 `evidence/c_forward_layer_probe_20260912/` §0b）。

🔴 **为什么这道门存在**：探针的 B／C 两格在「设备没走 PC 热点」时**必然为 0**，
而那**不是**「两层都看不见转发包」，是**根本没有流量经过 PC**——一个漂亮、可复现、
**完全错误**的「ICS 路径判死」。P2 就是挡这个的那一格。

⚠ **为什么不能靠现场验证这道守卫**：实测当天前提**自己变了两次**（热点 14:46:53 关、
其后又被重开），所以「跑一次看它红不红」取决于**那一刻的现场**，不取决于守卫对不对。
⇒ 把判定抽成纯函数，用**实际观测到的字符串**喂它，正反两向各下断言。

夹具全部是本会话 `adb shell ip route get 223.5.5.5` 的**真实输出**，不是编的。
"""
import os
import sys

_DIAG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "diag")
if _DIAG not in sys.path:
    sys.path.insert(0, _DIAG)

from forward_layer_probe import judge_egress          # noqa: E402

# --- 实测夹具（原样照抄，含 table/uid 尾巴） ---------------------------------
ON_HOTSPOT = "223.5.5.5 via 192.168.137.1 dev wlan0 table 1040 src 192.168.137.129 uid 2000"
ON_OTHER_WIFI = "223.5.5.5 via 10.10.0.1 dev wlan0 table 1040 src 10.10.7.37 uid 2000"


def test_on_hotspot_passes():
    """真命中方向：设备确实走热点时**必须放行**。

    收紧判据自带把守卫推成「永不通过」的风险，而那个方向**不会被下面的反例顺带确认**。
    """
    ok, via, src = judge_egress(ON_HOTSPOT)
    assert ok, (ok, via, src)
    assert via == "192.168.137.1" and src == "192.168.137.129", (via, src)


def test_other_wifi_is_rejected():
    """🔴 阳性对照：设备连的是**别的 WiFi**（同样 `dev wlan0`）时必须拒。

    **没有它，一道恒真的守卫与一道好守卫长得一样。**
    """
    ok, via, src = judge_egress(ON_OTHER_WIFI)
    assert not ok, "别的 WiFi 竟被放行 ⇒ B/C 会在没有流量经过 PC 时被当成有效计数"
    assert via == "10.10.0.1" and src == "10.10.7.37", (via, src)


def test_dev_wlan0_alone_is_not_enough():
    """🔴 这条是整道守卫的要害：**只认 `dev wlan0` 分不开两张网**。

    两个夹具的 `dev` 字段**完全相同**，区别只在 `via`／`src`——若守卫只看 `dev`，
    它对两者都会放行。此处把「只有 dev、没有 via/src」这一形态显式钉成拒绝。
    """
    assert "dev wlan0" in ON_HOTSPOT and "dev wlan0" in ON_OTHER_WIFI, "夹具前提变了"
    ok, _, _ = judge_egress("223.5.5.5 dev wlan0 table 1040 uid 2000")
    assert not ok, "只有 dev wlan0、无 via/src 竟被放行"


def test_empty_or_garbage_is_rejected():
    """读不到就是读不到——**不许当成「在热点上」**（缺席不等于通过）。

    末一条是「有 via 无 dev」：两个条件是**与**不是**或**。
    """
    for raw in ("", "   ", "error: device offline", "223.5.5.5 via 192.168.137.1"):
        ok, _, _ = judge_egress(raw)
        assert not ok, "该拒的输入竟被放行：%r" % raw
