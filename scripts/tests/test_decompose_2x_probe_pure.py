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


# ── 第一道门与空闲窗长（终审后新增；2026-09-13／09-18 实测驱动）──────────────
DEV_OK = "PING 223.5.5.5 (223.5.5.5) 56(84) bytes of data.\n" \
         "64 bytes from 223.5.5.5: icmp_seq=1 ttl=51 time=31.2 ms\n" \
         "--- 223.5.5.5 ping statistics ---\n" \
         "3 packets transmitted, 3 received, 0% packet loss, time 2041ms\n"
DEV_DEAD = "PING 223.5.5.5 (223.5.5.5) 56(84) bytes of data.\n" \
           "--- 223.5.5.5 ping statistics ---\n" \
           "3 packets transmitted, 0 received, 100% packet loss, time 2039ms\n"


def test_first_hop_requires_a_reply_not_rc_zero():
    """🔴 承重条：判据是**收到回复**。

    2026-09-13 实测：关联在、RSSI −18、网关 ARP REACHABLE，而 ICMP 与 TCP 一个包都不过；
    当时四个前提读数全绿且**同源**（都派生自配置而非往返）⇒ 一致不构成互证。
    """
    from decompose_2x_probe import judge_first_hop
    assert judge_first_hop(0, DEV_OK)[0] == "OK"
    code, why = judge_first_hop(1, DEV_DEAD)
    assert code == "NO_REPLY", (code, why)
    # 失败文本只许印读数,不许印解释(那次「设备不在热点上」恰好是错的)
    assert "3 发 0 收" in why, why
    assert "热点" not in why, "失败文本印了解释而不是读数：%s" % why


def test_first_hop_unreadable_is_its_own_code():
    """读不到 ⇒ 第三态。**不等于不通，也不等于通。**"""
    from decompose_2x_probe import judge_first_hop
    for out in ("", "error: device offline", "adb: no devices/emulators found"):
        assert judge_first_hop(None, out)[0] == "UNREADABLE", out


def test_first_hop_rc_zero_with_zero_replies_still_fails():
    """反向对照：`rc==0` 而 0 收 ⇒ 仍须 NO_REPLY（rc 不是判据）。"""
    from decompose_2x_probe import judge_first_hop
    assert judge_first_hop(0, DEV_DEAD)[0] == "NO_REPLY"


def test_idle_seconds_is_derived_and_beats_the_measured_target_window():
    """🔴 空闲格必须**长于**目标格：用 09-18 实测的那组数。

    实测 `ping -c 20 -i 1` wall=29.56s（ping 自报 19.445s，差约 10s 是 adb 开销）
    ⇒ 目标格 ≈31.6s。原写死的 20.0（＋2 宽限＝22s）**短于它** ⇒ 底噪全不可用。
    """
    from decompose_2x_probe import derive_idle_seconds
    secs, why = derive_idle_seconds(probe_wall_s=12.0, probe_n=3, n_ping=20)
    assert secs > 29.56, "推出的空闲窗 %.2f 仍短于实测目标格 29.56s" % secs
    assert "adb 开销" in why and "12.00" in why, why
    # 写死 20.0 的老值必须被本条判为不够 —— 证明本门有区分力
    assert 20.0 < 29.56


def test_idle_seconds_scales_with_measured_overhead():
    """开销越大空闲窗越长 —— 否则它不是由实测推出的。"""
    from decompose_2x_probe import derive_idle_seconds
    a, _ = derive_idle_seconds(probe_wall_s=5.0, probe_n=3, n_ping=20)
    b, _ = derive_idle_seconds(probe_wall_s=25.0, probe_n=3, n_ping=20)
    assert b - a == 20.0, (a, b)


# ── §2-1(c)：UTF-8 模式那个世界，**同进程内跑不出来** ──────────────────────
_CHILD = ("import sys; sys.path.insert(0, sys.argv[1]); "
          "import decompose_2x_probe as P; "
          "raw = bytes.fromhex(sys.argv[2]); t, note = P._decode(raw); "
          "print(P._acp(), P._sent_count(t), sys.flags.utf8_mode)")


def _run_child(*flags):
    import subprocess
    import sys as _s
    diag = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "diag")
    hexed = PING_ZH.encode("cp936").hex()
    r = subprocess.run([_s.executable] + list(flags) + ["-c", _CHILD, diag, hexed],
                       capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    return r.stdout.split()


def test_decode_survives_python_utf8_mode():
    """🔴 终审 §2-1(c)：**同进程内跑不出这个世界**，必须起子进程。

    `locale.getpreferredencoding(False)` 在 UTF-8 模式下返回 `'utf-8'` ⇒ 旧实现两条严格路
    退化成同一条 ⇒ `_sent_count` 恒 `None`，而**所有 PC 打的格 `T` 由它来**。
    ⚠ 本文件其它 `_decode` 用例**全在默认 locale 的同进程里**，一条都看不见这个世界
    ——「我测过」在这一族上是**反向证据**：正因为它在我的环境里绿，我才停在了那里。
    """
    acp0, sent0, mode0 = _run_child()
    acp1, sent1, mode1 = _run_child("-X", "utf8")
    assert (mode0, mode1) == ("0", "1"), "子进程没进 UTF-8 模式,本条就没测到那个世界"
    # 期望值**从夹具算出来**，不写死一个描述别处的数
    # （本条首次跑就咬住了我写死的 3）。
    want = str(_sent_count(PING_ZH))
    assert want == "20", "夹具自身变了：%s" % want
    assert sent0 == want, (acp0, sent0, want)
    assert sent1 == want, "UTF-8 模式下取不到发包数 ⇒ 回归 A 复发：acp=%s sent=%s 期望=%s" % (acp1, sent1, want)


def test_acp_does_not_come_from_locale():
    """🔴 判别量：`_acp()` 在 UTF-8 模式下**仍须给出 ACP**，不得跟着解释器变。

    这一条才是「把常量换成查询」那个坑的守卫——它钉的不是解码结果，是**那个查询的来源**。
    """
    acp0 = _run_child()[0]
    acp1 = _run_child("-X", "utf8")[0]
    assert acp0 == acp1, "两种模式下 _acp() 不一致（%s vs %s）⇒ 它又取自 locale 了" % (acp0, acp1)
    assert "utf" not in acp1.lower(), acp1
    # 反向对照:locale 那条路在两模式下**确实**不一致 —— 证明本门钉的是真差异
    import subprocess
    import sys as _s
    out = []
    for flags in ([], ["-X", "utf8"]):
        r = subprocess.run([_s.executable] + flags +
                           ["-c", "import locale; print(locale.getpreferredencoding(False))"],
                           capture_output=True, encoding="utf-8", errors="replace", timeout=60)
        out.append(r.stdout.strip())
    assert out[0] != out[1], "locale 在两模式下一致 ⇒ 本机复现不出该坑,本门无区分力：%s" % (out,)
