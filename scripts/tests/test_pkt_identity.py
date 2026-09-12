# -*- coding: utf-8 -*-
"""身份解析器的合成对照门（判据 §1.3；与 S0 同级：不过即整轮作废）。

🔴 **为什么必须有这道门**：探针的 S0 自证用 `false` filter ⇒ **解析路径零次执行**，
偏移写错不会被 S0 发现，而后果直接落在判定表上：得到约 `2T` 个互异键 ⇒ 误判
「根本不是倍增，原问题提错了」，分解就此关闭；或把 `icmp.Id`（同一 ping 进程内**恒定**）
读成 `Seq` ⇒ 去重 1–2，**判定表上没有小于 `T−2` 的行**，只能现场即兴。

🔴 **第 3 组的期望值是 `1`，不是 `2`——这一条被上游改法写反过一次，值得留在代码里。**
纯逻辑：两个**只差 `icmp.Id`** 的包——

| 去重键 | 去重数 |
|---|---|
| 键**不含** `Id`（正确） | **1** |
| 键**含** `Id`，或解析器把 `Id` 当成了 `Seq`（缺陷） | 2 |

⇒ 期望 `2` 恰恰**证明 `Id` 在键里**，与它自述的目的相反：那样这道「不过即整轮作废」的门
会**对正确实现判红、对它要抓的缺陷判绿**。
⚠ 形状：**被抄走的不是理由，是操作性数值——它不需要任何人同意就会生效。**

**第 4 组是新加的**：前三组**没有一组隔离 `Seq`**（第 1 组 `ip.ID` 自己就顶到 20、
与 seq 偏移无关；第 2 组任何确定性解析器都给 1）⇒ 补一组把
`recv_len`／`ip_id`／`src`／`icmp_id` 全钉死、**只让 `icmp_seq` 变**。

四组均在 **60 B（Windows ping）与 84 B（Android ping）两种形态**上各跑一次；
IHL 一律由首字节低四位算出。
"""
import os
import struct
import sys

_DIAG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "diag")
if _DIAG not in sys.path:
    sys.path.insert(0, _DIAG)

from pkt_identity import identity_key, parse, summarize      # noqa: E402

PAY = {60: 32, 84: 56}          # 总长 -> ICMP 负载长度（20 IP + 8 ICMP + payload）


def mk(total, src="192.168.137.129", dst="223.5.5.5", ip_id=0x1234,
       icmp_type=8, icmp_id=0x0001, seq=1, ttl=64, ihl_words=5):
    """合成一个 IPv4+ICMP 包。校验和留 0——解析器不校验校验和，本门测的是**偏移**。"""
    payload = bytes((0x61 + (i % 23)) for i in range(PAY[total]))
    icmp = struct.pack("!BBHHH", icmp_type, 0, 0, icmp_id, seq) + payload
    opt_len = (ihl_words - 5) * 4
    assert opt_len >= 0 and opt_len % 4 == 0, ihl_words
    # IHL != 5 时塞 opt_len 字节 IP 选项(NOP...EOL)。**把 ihl 写死成 20 的解析器**
    # 会从选项里读 icmp_type、从 ICMP 校验和里读 seq —— 第 5 组专抓这个。
    opts = (bytes([1]) * (opt_len - 1) + bytes([0])) if opt_len else bytes()
    ver_ihl = 0x40 | ihl_words
    ip = (struct.pack("!BBHHHBBH", ver_ihl, 0, 20 + opt_len + len(icmp), ip_id, 0, ttl, 1, 0)
          + bytes(int(x) for x in src.split("."))
          + bytes(int(x) for x in dst.split(".")) + opts)
    p = ip + icmp
    assert len(p) == total + opt_len, (len(p), total, opt_len)
    return p


def _recs(pkts):
    out = []
    for p in pkts:
        r = parse(p, len(p))
        assert r is not None, "解析器对合成的合法包回了 None"
        out.append(r)
    return out


def test_group1_twenty_distinct_packets():
    """① 20 个 `(ID, seq)` 互不相同 ⇒ 去重 20、重数全 1。"""
    for total in (60, 84):
        recs = _recs([mk(total, ip_id=0x1000 + i, seq=i + 1) for i in range(20)])
        s = summarize(recs)
        assert s["n_distinct_keys"] == 20, (total, s)
        assert s["multiplicity_hist"] == {1: 20}, (total, s)


def test_group2_same_packet_twenty_times():
    """② 同一包复制 20 份 ⇒ 去重 1、重数 20。"""
    for total in (60, 84):
        p = mk(total, ip_id=0x2222, seq=7)
        s = summarize(_recs([p] * 20))
        assert s["n_distinct_keys"] == 1, (total, s)
        assert s["multiplicity_hist"] == {20: 1}, (total, s)


def test_group3_only_icmp_id_differs_must_dedup_to_ONE():
    """🔴 ③ 只差 `icmp.Id` 的两个包 ⇒ 去重 **1**。

    读到 2 就说明 `Id` 进了键、或被当成了 `Seq`——**那正是本门要抓的缺陷**。
    （上游改法曾把期望写成 2，方向正好相反，见本文件抬头。）
    """
    for total in (60, 84):
        a = mk(total, ip_id=0x3333, seq=5, icmp_id=0x00AA)
        b = mk(total, ip_id=0x3333, seq=5, icmp_id=0x00BB)
        assert a != b, "两个夹具必须真的不同,否则本条恒过"
        s = summarize(_recs([a, b]))
        assert s["n_distinct_keys"] == 1, (
            "去重 %s != 1 ⇒ icmp.Id 进了身份键或被读成了 Seq：%s" % (s["n_distinct_keys"], s))
        assert s["multiplicity_hist"] == {2: 1}, (total, s)


def test_group4_only_seq_differs_isolates_the_seq_offset():
    """④ 只让 `icmp.Seq` 变（其余全钉死）⇒ 去重 N。

    前三组**没有一组隔离 Seq**：第 1 组 `ip.ID` 自己就顶到 20，第 2 组任何确定性解析器都给 1。
    若解析器读的是 `Id` 而非 `Seq`，本条会读到 **1**。
    """
    N = 12
    for total in (60, 84):
        recs = _recs([mk(total, ip_id=0x4444, icmp_id=0x00CC, seq=i + 1) for i in range(N)])
        s = summarize(recs)
        assert s["n_distinct_keys"] == N, (
            "去重 %s != %d ⇒ icmp.Seq 没被读到（很可能读的是 Id）：%s"
            % (s["n_distinct_keys"], N, s))
        assert s["distinct_seq"] == N and s["seq_min"] == 1 and s["seq_max"] == N, s


def test_src_split_distinguishes_two_worlds():
    """🔴 按 `src` 的拆支：两个含义相反的世界必须分开（判据 §4.1）。

    同键但 `src` 不同 ⇒ 同一数据报在**两点各一次**（H1／NAT 形态）；
    同键且 `src` 相同 ⇒ **同一点被呈现两次**（clone+reinject 形态）。
    **对整形器含义相反，不得并成一行。**
    """
    for total in (60, 84):
        same = summarize(_recs([mk(total, seq=3)] * 2))
        assert same["n_distinct_keys"] == 1 and same["src_same_within_key"] is True, same
        pre = mk(total, src="192.168.137.129", ip_id=0x5555, seq=3)
        post = mk(total, src="10.10.8.9", ip_id=0x5555, seq=3)
        nat = summarize(_recs([pre, post]))
        assert nat["n_distinct_keys"] == 1, (
            "NAT 前后两份必须同键（键不含 src）：%s" % nat)
        assert nat["src_same_within_key"] is False, (
            "同键而 src 不同必须被标出,否则 H1 那一支永不触发：%s" % nat)


def test_key_is_exactly_three_fields():
    """键必须**恰好**是那三项——多一项就会让 H1 那一支落进「是不同的包」。"""
    r = parse(mk(60), 60)
    assert identity_key(r) == (60, 0x1234, 1), identity_key(r)
    r2 = parse(mk(60, src="10.10.8.9", ttl=63), 60)
    assert identity_key(r) == identity_key(r2), (
        "换 src 与 ttl 后键变了 ⇒ 它们进了键：%s vs %s" % (identity_key(r), identity_key(r2)))


def test_parser_refuses_what_it_cannot_read():
    """读不出就回 None，**不猜**（缺席不等于通过）。"""
    assert parse(b"", 0) is None
    assert parse(b"E" + b"\x00" * 10, 11) is None              # 长度不足
    assert parse(mk(60)[:20], 20) is None                      # 有 IP 头无 ICMP 头
    bad_ver = bytearray(mk(60)); bad_ver[0] = 0x65             # version=6
    assert parse(bytes(bad_ver), 60) is None
    not_icmp = bytearray(mk(60)); not_icmp[9] = 6              # protocol=TCP
    assert parse(bytes(not_icmp), 60) is None
    assert parse(mk(60), 999) is None                          # recv_len 大于缓冲


def test_group5_ihl_not_five_catches_a_hardcoded_header_length():
    """🔴 ⑤ IHL ≠ 5（带 4 字节 IP 选项）⇒ 抓「把 `ihl` 写死成 20」的实现。

    **前四组对这个缺陷完全失明**：60 B 与 84 B 两种形态 IHL 同为 5
    ⇒ `ihl = 20` 与 `ihl = (b[0] & 0x0F) * 4` 逐字节等价。
    实测突变「`ihl = 20`」在只有前四组时 **7/7 全绿**。
    ⇒ **CAUGHT 是真的、覆盖可以是假的**：先前那四个突变全落在
    「键含哪些字段」与「ICMP 内偏移」这一维，**没有一个碰头长计算**。

    IHL=6 的布局：`0..19` IP 头、`20..23` 选项、`24` type、`25` code、
    `26..27` 校验和、`28..29` id、`30..31` seq。
    把 `ihl` 写死成 20 的解析器于是**从选项里读 type（得 1，不是 8）、
    从 ICMP 校验和里读 seq（恒 0）** ⇒ 只让 seq 变的那一组塌成去重 1。
    """
    N = 9
    for total in (60, 84):
        one = mk(total, ihl_words=6)
        assert (one[0] & 0x0F) == 6, "夹具本身不是 IHL=6,本条会恒过"
        r = parse(one, len(one))
        assert r is not None, "IHL=6 的合法包被判 None"
        assert r["ihl"] == 24, "IHL 没按低四位×4 算：ihl=%s" % r["ihl"]
        assert r["icmp_type"] == 8, (
            "icmp_type=%s（期望 8）⇒ ICMP 偏移没随 IHL 走,很可能写死了 20" % r["icmp_type"])
        recs = _recs([mk(total, ip_id=0x6666, icmp_id=0x00DD, seq=i + 1, ihl_words=6)
                      for i in range(N)])
        s = summarize(recs)
        assert s["n_distinct_keys"] == N, (
            "去重 %s != %d ⇒ seq 偏移没随 IHL 走(读到的很可能是 ICMP 校验和)：%s"
            % (s["n_distinct_keys"], N, s))
        assert s["seq_min"] == 1 and s["seq_max"] == N, s
