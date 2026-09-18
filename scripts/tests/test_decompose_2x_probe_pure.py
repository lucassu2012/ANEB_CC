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
    _sent_count, constants_verdict, filter_neighbors, judge_device_egress,
    same_window, self_id_lines)


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
                up_raw="9|10.10.8.9", nb_kept=["192.168.137.129"],
                nb_dropped=[("192.168.137.255", "广播地址")])
    ok, why = constants_verdict(good, "192.168.137.129")
    assert ok is True, why
    bad = dict(good)
    bad["nb_kept"] = ["192.168.137.55"]
    ok2, why2 = constants_verdict(bad, "192.168.137.129")
    assert ok2 is False and "双侧不同意" in why2, why2


def test_constants_verdict_rejects_hot_count_not_exactly_one():
    """§2-2 `count != 1` ⇒ NOT_EXECUTED。两个方向都钉:0 与 2 都不行。"""
    for n in (0, 2, None):
        d = dict(hot_count=n, hot_ifidx=13, up_ifidx=9, up_addr="10.10.8.9",
                 up_raw="9|10.10.8.9", nb_kept=["192.168.137.129"], nb_dropped=[])
        ok, why = constants_verdict(d, "192.168.137.129")
        assert ok is False, (n, why)


def test_constants_verdict_refuses_when_device_src_missing():
    d = dict(hot_count=1, hot_ifidx=13, up_ifidx=9, up_addr="10.10.8.9",
             up_raw="9|10.10.8.9", nb_kept=["192.168.137.129"], nb_dropped=[])
    ok, why = constants_verdict(d, None)
    assert ok is False and "src token" in why, why


def test_filter_neighbors_drops_the_broadcast_that_actually_broke_the_smoke_run():
    """🔴 夹具是**非提权烟测真实抓到的**那一组：热点腿邻居表里同时有广播与网关。

    原实现用 `-like '192.168.137*'` ＋ `Select -First 1` 挑中了 `192.168.137.255`
    ⇒ §2-3 报「双侧不同意」,而两侧其实一致 —— **是匹配器挑错了**。
    ⚠ 不用「跑一次看它红不红」:反例会自己消失(邻居表顺序会变),故钉成夹具。
    """
    kept, dropped = filter_neighbors(
        ["192.168.137.255", "192.168.137.1", "192.168.137.129"])
    assert kept == ["192.168.137.129"], (kept, dropped)
    reasons = dict(dropped)
    assert "广播" in reasons["192.168.137.255"], reasons
    assert "PC" in reasons["192.168.137.1"], reasons


def test_filter_neighbors_keeps_more_than_one_client_and_never_silently_drops():
    """多个客户端都要留；且**每条被丢的都带理由**——凡报「丢了 N 条」就要能说出是哪些。"""
    kept, dropped = filter_neighbors(
        ["192.168.137.129", "192.168.137.130", "10.10.8.9", "garbage", ""])
    assert kept == ["192.168.137.129", "192.168.137.130"], kept
    assert len(dropped) == 3, dropped
    for a, why in dropped:
        assert why.strip(), (a, why)


def test_filter_neighbors_is_octetwise_not_a_string_prefix():
    """按四段结构判,不按字符串前缀 —— 「没锚定的匹配器会匹配到超集」。"""
    kept, dropped = filter_neighbors(["192.168.13.129", "192.168.1.137", "1.192.168.137"])
    assert kept == [], (kept, dropped)


def test_filter_neighbors_empty_input_is_empty_not_a_crash():
    kept, dropped = filter_neighbors([])
    assert kept == [] and dropped == []


# ── `_decode` 的门（终审 HIGH #1）────────────────────────────────────────────
# 夹具用**真实抓到的那一行**：本机 ping.exe 的摘要行，按 cp936 编码——
# 这正是 `ping.exe -n 1 127.0.0.1` 实际吐出的字节形态（ACP=cp936 实测）。
PING_ZH = "数据包: 已发送 = 20，已接收 = 20，丢失 = 0 (0% 丢失)，"
PING_EN = "    Packets: Sent = 20, Received = 20, Lost = 0 (0% loss),"


def test_decode_cp936_bytes_are_readable_not_replacement_chars():
    """🔴 承重条：cp936 字节必须解得出来，且**不含替换符**。

    原实现写死 `encoding="utf-8"` ＋ `errors="replace"` ⇒ 这一行变成一串 U+FFFD，
    `_sent_count` 的正则永不命中 ⇒ 所有 PC 打的格 T=None ⇒ 判定块一行不印。
    """
    from decompose_2x_probe import _decode
    raw = PING_ZH.encode("cp936")
    text, note = _decode(raw)
    assert chr(65533) not in text, "解出替换符 ⇒ 又走回 utf-8 那条路了：%r" % text
    assert "已发送 = 20" in text, text
    assert note and "cp936" in note, "非 utf-8 路必须把用了哪条编码说出来：%r" % (note,)


def test_decode_cp936_bytes_feed_the_sent_count_regex():
    """把 `_decode` 与 `_sent_count` 串起来测 —— 单测任一半都看不见这条链断没断。"""
    from decompose_2x_probe import _decode, _sent_count
    text, _ = _decode(PING_ZH.encode("cp936"))
    assert _sent_count(text) == 20, "T 取不到 ⇒ HIGH #1 复发：%r" % text
    # 反向:若按 utf-8 replace 解(旧实现),同一批字节必须取不到 —— 证明本门有区分力
    broken = PING_ZH.encode("cp936").decode("utf-8", errors="replace")
    assert _sent_count(broken) is None, "旧实现居然也能取到 ⇒ 本门无区分力"


def test_decode_utf8_and_ascii_take_the_strict_path_silently():
    """正对照：utf-8 与纯 ASCII 走严格路，**不得打印噪音说明**。"""
    from decompose_2x_probe import _decode
    t1, n1 = _decode("设备侧 20 packets transmitted".encode("utf-8"))
    assert "packets transmitted" in t1 and n1 is None, (t1, n1)
    t2, n2 = _decode(PING_EN.encode("ascii"))
    assert "Sent = 20" in t2 and n2 is None, (t2, n2)


def test_decode_reports_when_both_strict_paths_fail():
    """两种严格解码都失败 ⇒ 必须明说读数不可信，**不得静默 replace**。"""
    from decompose_2x_probe import _decode
    bad = bytes([0x81, 0x40, 0xFF, 0xFE, 0x80])
    text, note = _decode(bad)
    assert note is not None and "不可信" in note, (text, note)


def test_decode_empty_is_not_an_error():
    from decompose_2x_probe import _decode
    assert _decode(b"") == ("", None)
    assert _decode(None) == ("", None)


# ── `_dump_records` 的门（终审 X13）──────────────────────────────────────────
def _rec(seq, src="192.168.137.129"):
    return {"recv_len": 84, "ip_id": 0x1000 + seq, "ttl": 64, "src": src,
            "dst": "223.5.5.5", "ihl": 20, "icmp_type": 8, "icmp_id": 0x0001,
            "icmp_seq": seq}


def test_dump_records_prints_one_line_per_packet_and_never_truncates():
    """🔴 承重条：**不许截断**。

    §4.1 的 `src` 拆支与「事后查询」都建立在这些行上；截断会静默丢掉恰要被查询的那几行。
    本条钉「行数 == 记录数」,所以任何 `[:N]` 都会当场红。
    """
    from decompose_2x_probe import _dump_records
    import io as _io
    import sys as _sys
    recs = [_rec(i) for i in range(45)]
    buf = _io.StringIO()
    old = _sys.stdout
    _sys.stdout = buf
    try:
        _dump_records("句柄 a", recs)
    finally:
        _sys.stdout = old
    lines = [l for l in buf.getvalue().splitlines() if l.strip()]
    body = [l for l in lines if "seq=" in l]
    assert len(body) == 45, "印了 %d 行而记录有 45 条 ⇒ 被截断了" % len(body)
    assert "45 条" in lines[0], lines[0]


def test_dump_records_carries_every_field_needed_by_the_src_split():
    """每行必须带 §4.1 拆支要用的字段 —— 少一个,拆支就只能靠汇总那一行的布尔值。"""
    from decompose_2x_probe import _dump_records
    import io as _io
    import sys as _sys
    buf = _io.StringIO()
    old = _sys.stdout
    _sys.stdout = buf
    try:
        _dump_records("句柄 a", [_rec(7, src="10.10.8.9")])
    finally:
        _sys.stdout = old
    line = [l for l in buf.getvalue().splitlines() if "seq=" in l][0]
    for token in ("len=84", "id=0x1007", "ttl=64", "src=10.10.8.9",
                  "dst=223.5.5.5", "ihl=20", "type=8", "icmp_id=0x0001", "seq=7"):
        assert token in line, "缺字段 %s：%s" % (token, line)


def test_dump_records_on_empty_prints_nothing():
    from decompose_2x_probe import _dump_records
    import io as _io
    import sys as _sys
    buf = _io.StringIO()
    old = _sys.stdout
    _sys.stdout = buf
    try:
        _dump_records("句柄 b", [])
    finally:
        _sys.stdout = old
    assert buf.getvalue() == "", buf.getvalue()
