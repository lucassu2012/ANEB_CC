# -*- coding: utf-8 -*-
"""包身份解析：从 IPv4+ICMP 的**原始字节**取身份键与旁证字段。纯函数，无 IO、不碰驱动。

🔴 **为什么身份键只有三项，而记录有八项**（判据 §1.2）：

去重键 ＝ `(recv_len, ip_id, icmp_seq)`。`src`／`dst`／`ttl`／`icmp_type`／`icmp_id`
**只记录、不入键**。理由是判决性的：

- **NAT 改的是源地址**，`recv_len`／`ip_id`／`icmp_seq` 都不变 ⇒ 同一数据报在 NAT 前后
  两次目击**同键、重数 2** ⇒ 落进「同一数据报被呈现两次」，**再按 `src` 拆**
  「同一点两次」与「两点各一次」两支。
- **若把 `src`／`ttl` 也入键**，H1 世界里 `src` 必不同、`ttl` 可能差 1
  ⇒ `2T` 个互异键、重数全 1 ⇒ 落进「是不同的包，不是倍增」，**而按 `src` 的拆支永不触发**。
  ⚠ 这一支**三道合成门全绿而结论反转**，且**不对称**——同点 clone+reinject 判对，
  只有跨 NAT 那一支判反，读数看起来完全可信。**这就是键必须显式定义的原因。**

⚠ `icmp_id` 在同一个 ping 进程内**恒定** ⇒ 入键不改变任何计数，**但把它读成 `seq`
会让所有包看起来同键**。合成对照第 3、4 组专门钉这一点（见 `test_pkt_identity.py`）。

IHL **一律由首字节低四位算出**（×4），不假设 20 字节头。
"""
import struct


def parse(buf, recv_len=None):
    """→ dict 或 None（非 IPv4／非 ICMP／长度不足时 None，**不猜**）。

    `recv_len` 传 `WinDivertRecv` 的出参；None 时退回 `len(buf)`。
    """
    b = bytes(buf)
    n = len(b) if recv_len is None else int(recv_len)
    if n < 20 or n > len(b):
        return None
    if (b[0] >> 4) != 4:
        return None
    ihl = (b[0] & 0x0F) * 4
    if ihl < 20 or n < ihl + 8:
        return None
    if b[9] != 1:                       # protocol 必须是 ICMP
        return None
    return {
        "recv_len": n,
        "ip_id": struct.unpack("!H", b[4:6])[0],
        "ttl": b[8],
        "src": ".".join(str(x) for x in b[12:16]),
        "dst": ".".join(str(x) for x in b[16:20]),
        "ihl": ihl,
        "icmp_type": b[ihl],
        "icmp_id": struct.unpack("!H", b[ihl + 4:ihl + 6])[0],
        "icmp_seq": struct.unpack("!H", b[ihl + 6:ihl + 8])[0],
    }


def identity_key(rec):
    """身份键 ＝ `(recv_len, ip_id, icmp_seq)`。**只有这三项。**"""
    return (rec["recv_len"], rec["ip_id"], rec["icmp_seq"])


def summarize(records):
    """→ dict：去重数、重数分布，以及按 `src` 的拆支所需的信息。

    `src_same_within_key`：所有同键组的 `src` 是否**组内一致**。
    - True  ⇒ 重复目击发生在**同一点**（clone+reinject 形态）；
    - False ⇒ 同一数据报在**两点各一次**（H1／NAT 形态）。
    ⚠ 这个字段**必须与去重数一起报**：单看去重数分不开这两个含义相反的世界。
    """
    groups = {}
    for r in records:
        groups.setdefault(identity_key(r), []).append(r)
    mult = {}
    for g in groups.values():
        mult[len(g)] = mult.get(len(g), 0) + 1
    same = all(len(set(r["src"] for r in g)) == 1 for g in groups.values())
    seqs = [r["icmp_seq"] for r in records]
    return {
        "n_records": len(records),
        "n_distinct_keys": len(groups),
        "multiplicity_hist": dict(sorted(mult.items())),
        "src_same_within_key": same,
        "distinct_seq": len(set(seqs)),
        "seq_min": min(seqs) if seqs else None,
        "seq_max": max(seqs) if seqs else None,
    }
