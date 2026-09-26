# -*- coding: utf-8 -*-
"""设备三层前提门 · run6：run5 原样 + PC 热点卡单播计数 + 等长背景窗（大脑 2026-09-26 批准）。只读。

用法（仓根）：
  python evidence/c_device_gate_20260926/gate_diag6.py --selftest   # 只在 PC 侧验计数器，不碰设备
  python evidence/c_device_gate_20260926/gate_diag6.py              # 正式跑（等大脑点）

- run5 的字段名、adb 命令块、判「通」的方法一字不改；新增字段只在计数器自检通过时出现。
- 计数器：iphlpapi.GetIfEntry2 返回的 MIB_IF_ROW2.OutUcastPkts / OutDiscards / InUcastPkts
  （python ctypes 直调，ULONG64 原值；函数返回码记为 rc，0＝NO_ERROR）。接口号现场由
  GetIpAddrTable 按热点地址推出（D-907），不写死。
- 自检（任一不过 ⇒ 计数器视为取不到 ⇒ 不做背景窗、不出判词，只跑 run5 原样字段；不凑替代量法）：
  结构体大小 1352；GetIfEntry2 返回 0；别名与 psutil 持有热点地址的网卡同名；接口号一致；
  psutil 的发/收包数与字节数被 ctypes 前后两读夹住（psutil 在 Windows 上即 Ucast+NUcast 之和）；
  单播发送计数非零。--selftest 另加一道：PowerShell Get-NetAdapterStatistics 的 SentUnicastPackets
  被 ctypes 前后两读夹住（独立来源）。
- 判据从 README 的 PREREG 行解析（单一来源），解析不出就抛，不兜底。
- 设备侧 ping 的门同 run2（D-918 裁定成立）：锁屏下前台应用＝华为桌面、无 tun/ppp、无 ANEB 进程。
"""
import ctypes
import datetime
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time

import psutil

D = "evidence/c_device_gate_20260926"
SERIAL = "8MY0221126002537"
HOT_IP = "192.168.137.1"
LAUNCHER = "com.huawei.android.launcher"
U64 = ctypes.c_uint64


class MIB_IF_ROW2(ctypes.Structure):
    _fields_ = [
        ("InterfaceLuid", U64), ("InterfaceIndex", ctypes.c_ulong), ("InterfaceGuid", ctypes.c_ubyte * 16),
        ("Alias", ctypes.c_wchar * 257), ("Description", ctypes.c_wchar * 257),
        ("PhysicalAddressLength", ctypes.c_ulong),
        ("PhysicalAddress", ctypes.c_ubyte * 32), ("PermanentPhysicalAddress", ctypes.c_ubyte * 32),
        ("Mtu", ctypes.c_ulong), ("Type", ctypes.c_ulong), ("TunnelType", ctypes.c_int),
        ("MediaType", ctypes.c_int), ("PhysicalMediumType", ctypes.c_int), ("AccessType", ctypes.c_int),
        ("DirectionType", ctypes.c_int), ("InterfaceAndOperStatusFlags", ctypes.c_ubyte),
        ("OperStatus", ctypes.c_int), ("AdminStatus", ctypes.c_int), ("MediaConnectState", ctypes.c_int),
        ("NetworkGuid", ctypes.c_ubyte * 16), ("ConnectionType", ctypes.c_int),
        ("TransmitLinkSpeed", U64), ("ReceiveLinkSpeed", U64),
        ("InOctets", U64), ("InUcastPkts", U64), ("InNUcastPkts", U64), ("InDiscards", U64),
        ("InErrors", U64), ("InUnknownProtos", U64), ("InUcastOctets", U64), ("InMulticastOctets", U64),
        ("InBroadcastOctets", U64),
        ("OutOctets", U64), ("OutUcastPkts", U64), ("OutNUcastPkts", U64), ("OutDiscards", U64),
        ("OutErrors", U64), ("OutUcastOctets", U64), ("OutMulticastOctets", U64), ("OutBroadcastOctets", U64),
        ("OutQLen", U64),
    ]


IPH = ctypes.WinDLL("iphlpapi")
R = []


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def load_prereg():
    with open(os.path.join(D, "README.md"), encoding="utf-8") as fh:
        lines = re.findall(r"^PREREG: (.+)$", fh.read(), re.M)
    assert len(lines) == 1, "README 里 PREREG 行应恰有 1 条，实有 %d" % len(lines)
    kv = dict(p.strip().split("=", 1) for p in lines[0].split(";"))
    want = {"replies", "bg_max", "d_reply", "d_bg", "disc_reply", "disc_zero"}
    assert set(kv) == want, sorted(kv)

    def rng(s):
        a, b = re.fullmatch(r"\[(-?\d+),(-?\d+)\]", s.strip()).groups()
        return int(a), int(b)
    P = dict(replies=int(kv["replies"]), bg_max=int(kv["bg_max"]))
    for k in ("d_reply", "d_bg", "disc_reply", "disc_zero"):
        P[k] = rng(kv[k])
    return P, lines[0]


def ifindex_by_ip(ip):
    size = ctypes.c_ulong(0)
    IPH.GetIpAddrTable(None, ctypes.byref(size), False)
    buf = ctypes.create_string_buffer(size.value)
    rc = IPH.GetIpAddrTable(buf, ctypes.byref(size), False)
    assert rc == 0, "GetIpAddrTable rc=%d" % rc
    n = struct.unpack_from("<I", buf, 0)[0]
    want = struct.unpack("<I", socket.inet_aton(ip))[0]
    hits = [struct.unpack_from("<I", buf, 4 + 24 * i + 4)[0] for i in range(n)
            if struct.unpack_from("<I", buf, 4 + 24 * i)[0] == want]
    return hits


def uc_read(idx):
    row = MIB_IF_ROW2()
    row.InterfaceIndex = idx
    rc = IPH.GetIfEntry2(ctypes.byref(row))
    return rc, row


def uc_snap(idx):
    rc, r = uc_read(idx)
    return dict(rc=rc, out_ucast=r.OutUcastPkts, out_discards=r.OutDiscards, in_ucast=r.InUcastPkts,
                out_nucast=r.OutNUcastPkts, in_nucast=r.InNUcastPkts, out_octets=r.OutOctets, in_octets=r.InOctets)


def hot_nic():
    names = [n for n, addrs in psutil.net_if_addrs().items() if any(a.address == HOT_IP for a in addrs)]
    return names[0] if len(names) == 1 else None


def selfcheck(nic, deep):
    """返回 (ok, 记录)。每条检查都落原值，不只落真假。"""
    c = dict(sizeof=ctypes.sizeof(MIB_IF_ROW2), nic=nic)
    ok = c["sizeof"] == 1352 and nic is not None
    idxs = ifindex_by_ip(HOT_IP)
    c["ifindex_by_ip"] = idxs
    ok = ok and len(idxs) == 1
    if not ok:
        return False, c
    idx = idxs[0]
    rc, row = uc_read(idx)
    c.update(getifentry2_rc=rc, alias=row.Alias, row_ifindex=row.InterfaceIndex)
    ok = rc == 0 and row.Alias == nic and row.InterfaceIndex == idx
    s1 = uc_snap(idx)
    p = psutil.net_io_counters(pernic=True)[nic]
    s2 = uc_snap(idx)
    sand = dict(
        sent=[s1["out_ucast"] + s1["out_nucast"], p.packets_sent, s2["out_ucast"] + s2["out_nucast"]],
        recv=[s1["in_ucast"] + s1["in_nucast"], p.packets_recv, s2["in_ucast"] + s2["in_nucast"]],
        bytes_sent=[s1["out_octets"], p.bytes_sent, s2["out_octets"]],
        bytes_recv=[s1["in_octets"], p.bytes_recv, s2["in_octets"]])
    c["psutil_sandwich"] = sand
    ok = ok and all(a <= b <= z for a, b, z in sand.values()) and s1["out_ucast"] > 0
    c["out_ucast_nonzero"] = s1["out_ucast"] > 0
    if deep:
        ps = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-NetAdapter -InterfaceIndex %d | "
              "Get-NetAdapterStatistics | Select-Object SentUnicastPackets,ReceivedUnicastPackets | "
              "ConvertTo-Json -Compress" % idx)
        a = uc_snap(idx)
        pr = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                            capture_output=True, timeout=300)
        b = uc_snap(idx)
        c["ps_rc"] = pr.returncode
        try:
            j = json.loads(pr.stdout.decode("utf-8", "replace"))
            c["ps_sandwich"] = dict(sent_ucast=[a["out_ucast"], j["SentUnicastPackets"], b["out_ucast"]],
                                    recv_ucast=[a["in_ucast"], j["ReceivedUnicastPackets"], b["in_ucast"]])
            ok = ok and pr.returncode == 0 and all(x <= y <= z for x, y, z in c["ps_sandwich"].values())
        except (ValueError, KeyError, TypeError) as e:
            c["ps_error"] = repr(e)
            ok = False
        # 旁证：热点全局状态与客户端数、该卡状态（WinRT 的状态是全局的，见 README 第 2 节 #5）。不参与 ok。
        hs = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; & { "
              "$null=[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]; "
              "$null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]; "
              "$pr=[Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile(); "
              "$tm=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($pr); "
              "$a=Get-NetAdapter -InterfaceIndex %d; "
              "[pscustomobject]@{State=$tm.TetheringOperationalState.ToString();Clients=$tm.ClientCount;"
              "NicStatus=$a.Status} } | ConvertTo-Json -Compress" % idx)
        t = now()
        hp = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", hs],
                            capture_output=True, timeout=300)
        try:
            hj = json.loads(hp.stdout.decode("utf-8", "replace"))
        except ValueError:
            hj = {"unparsed": hp.stdout.decode("utf-8", "replace").strip()[:300]}
        c["hotspot"] = dict(ts=t, rc=hp.returncode, **hj)
    c["ifindex"] = idx
    return ok, c


def write(name):
    blob = json.dumps(R, ensure_ascii=False, indent=1)
    assert not re.search(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b", blob), "读数含 MAC 样式串"
    assert not re.search(r"(?i)ssid\s*[:=]", blob), "读数含网络名字段"
    data = blob.encode("utf-8")
    path = os.path.join(D, name)
    with open(path, "wb") as fh:
        fh.write(data)
    with open(path, "rb") as fh:
        assert fh.read() == data
    return path


CH_UC = "python ctypes → iphlpapi.GetIfEntry2 → MIB_IF_ROW2 原值（rc＝函数返回码，0＝NO_ERROR）"


def adb_sh(*a, timeout=60):
    argv = ["adb", "-s", SERIAL, "shell", *a]
    ts = now()
    p = subprocess.run(argv, capture_output=True, timeout=timeout)
    return argv, ts, p.returncode, p.stdout.decode("utf-8", "replace")


def verdict(P, d, disc, bg_sent):
    """判词只由读数与 PREREG 算出。"""
    inr = lambda v, r: r[0] <= v <= r[1]
    if bg_sent > P["bg_max"]:
        return "判不了（背景窗单播发送增量 %d 超过上限 %d）" % (bg_sent, P["bg_max"])
    if inr(d, P["d_reply"]):
        return "d=%d≈回复数：PC 向手机发出了回复 ⇒ 排除「纯 H2」（共享源错且 PC 不回差错）" % d
    if inr(d, P["d_bg"]) and inr(disc, P["disc_zero"]):
        return "d=%d≈背景、丢弃增量 %d≈0：没有东西要发给手机 ⇒ 支持 H2" % (d, disc)
    if inr(d, P["d_bg"]) and inr(disc, P["disc_reply"]):
        return "d=%d≈背景、丢弃增量 %d≈回复数：要发给手机的包被驱动丢弃 ⇒ 支持 H3" % (d, disc)
    return "判不了（d=%d、丢弃增量 %d 不落在任何预登记区间）" % (d, disc)


def main():
    selftest = "--selftest" in sys.argv[1:]
    t_start = datetime.datetime.now().strftime("%H%M%S")
    P, prereg_line = load_prereg()
    nic = hot_nic()
    ok, c = selfcheck(nic, deep=selftest)
    R.append(dict(ts=now(), layer="PC", item="单播计数器自检", argv=["（进程内 ctypes/psutil 调用）"],
                  channel=CH_UC + "；psutil.net_io_counters；--selftest 另调 PowerShell Get-NetAdapterStatistics",
                  rc=0, verdict="通" if ok else "未执行（计数器取不到，退回 run5 原样字段）",
                  prereg=prereg_line, **c))
    if selftest:
        # 文件名带开始时刻：13:36 与 13:42 两次自检曾写同一文件名，前一次被覆盖（README 第 8 节）
        print("selftest ok=%s -> %s" % (ok, write("readings_run6_selftest_%s.json" % t_start)))
        print(json.dumps(R[-1], ensure_ascii=False)[:2000])
        return
    idx = c.get("ifindex")

    argv = ["adb", "devices"]
    ts = now()
    p = subprocess.run(argv, capture_output=True, timeout=60)
    online = ("%s\tdevice" % SERIAL) in p.stdout.decode("utf-8", "replace")
    R.append(dict(ts=ts, layer="P40", item="设备在线", argv=argv, channel="adb → python；rc＝adb 的 python returncode",
                  rc=p.returncode, verdict="通" if online else "不通"))
    if not online:
        print("device offline -> %s" % write("readings_run6_%s.json" % t_start))
        return

    argv, ts, rc, out = adb_sh("dumpsys", "power")
    wk = re.search(r"mWakefulness=(\w+)", out)
    argv2, ts2, rc2, out2 = adb_sh("dumpsys", "window")
    cf = re.search(r"mCurrentFocus=Window\{\S+ \S+ (\S+?)\}", out2)
    fa = re.search(r"mFocusedApp=ActivityRecord\{\S+ \S+ (\S+?)[ }]", out2)
    kg = re.search(r"isKeyguardShowing=(\w+)", out2)
    argv3, ts3, rc3, out3 = adb_sh("ps", "-A", "-o", "NAME")
    anebs = sorted({l.strip() for l in out3.splitlines() if "aneb" in l})
    argv4, ts4, rc4, out4 = adb_sh("ip", "link")
    tun = sorted({m.group(1) for m in re.finditer(r"^\d+: ((?:tun|ppp)\w*)[:@].*\bUP\b", out4, re.M)})
    fapp = fa.group(1) if fa else None
    gate = bool(fapp and fapp.startswith(LAUNCHER)) and not tun and not anebs
    R.append(dict(ts=ts, layer="P40", item="开跑前设备态与冲突门（D-918）",
                  argv=[argv + ["（只取 mWakefulness）"], argv2 + ["（只取 mCurrentFocus/mFocusedApp/isKeyguardShowing）"],
                        argv3, argv4 + ["（只取 tun/ppp 接口名）"]],
                  channel="adb shell → python；rc＝adb 的 python returncode", rc=[rc, rc2, rc3, rc4],
                  verdict="通" if gate else "不通（不发 ping）",
                  wakefulness=wk.group(1) if wk else None, current_focus=cf.group(1) if cf else None,
                  focused_app=fapp, keyguard=kg.group(1) if kg else None, aneb_procs=anebs, tun_ppp_up=tun))

    def assoc_snap():
        """关联稳定性（大脑 14:0x 追加，跑前入库）：手机 supplicant 态与 wlan0 地址（输出不含网络名）＋ PC 虚拟卡链路态。"""
        o = subprocess.run(["adb", "-s", SERIAL, "shell",
                            "cmd wifi status | grep -o 'Supplicant state: [A-Z_]*'; "
                            "ip -4 addr show wlan0 | grep -o 'inet [0-9./]*'"],
                           capture_output=True, timeout=60).stdout.decode("utf-8", "replace")
        sup = re.search(r"Supplicant state: (\w+)", o)
        ip = re.search(r"inet ([0-9./]+)", o)
        ids = ifindex_by_ip(HOT_IP)
        link = None
        if ok and ids == [idx]:
            rc_, r_ = uc_read(idx)
            link = dict(rc=rc_, oper=r_.OperStatus, media=r_.MediaConnectState)
        return dict(ts=now(), supplicant=sup.group(1) if sup else None, inet=ip.group(1) if ip else None,
                    ifindex=ids, pc_link=link)

    def probe(dst, label, decide):
        block = ("cat /proc/net/dev | grep wlan0; ping -c 3 -W 2 %s; echo PING_RC=$?; "
                 "cat /proc/net/dev | grep wlan0" % dst)
        argv = ["adb", "-s", SERIAL, "shell", block]
        if not gate:
            R.append(dict(ts=now(), layer="P40+PC", item=label, argv=argv, channel="—", rc=None, verdict="未执行",
                          reason="冲突门不过"))
            return
        as0 = assoc_snap()
        a = psutil.net_io_counters(pernic=True)[nic]
        ua = uc_snap(idx) if ok else None
        ts = now()
        t0 = time.monotonic()
        p = subprocess.run(argv, capture_output=True, timeout=60)
        dur = time.monotonic() - t0
        ub = uc_snap(idx) if ok else None
        b = psutil.net_io_counters(pernic=True)[nic]
        out = p.stdout.decode("utf-8", "replace")
        rows = [l for l in out.splitlines() if l.strip().startswith("wlan0:")]
        f = {}
        if len(rows) == 2:
            x0, x1 = rows[0].split(":", 1)[1].split(), rows[1].split(":", 1)[1].split()
            f.update(phone_rx_delta=int(x1[1]) - int(x0[1]), phone_tx_delta=int(x1[9]) - int(x0[9]),
                     phone_tx_drop_delta=int(x1[11]) - int(x0[11]), phone_rx_drop_delta=int(x1[3]) - int(x0[3]))
        else:
            f["note"] = "wlan0 行数不是 2（%d），不计手机增量" % len(rows)
        n = sum(1 for l in out.splitlines() if ("from %s" % dst) in l and "ttl=" in l.lower())
        prc = re.search(r"PING_RC=(\d+)", out)
        rec = dict(ts=ts, layer="P40+PC", item=label, argv=argv,
                   channel="adb shell（计数/ping/计数同一条命令）；PC 计数 psutil 与 %s 紧贴 adb 前后读（%s）；"
                           "rc＝adb 的 python returncode" % (CH_UC, nic),
                   rc=p.returncode, verdict="通" if n else "不通", replies_from_target=n,
                   ping_rc_inside_shell=int(prc.group(1)) if prc else None,
                   pc_recv_delta=b.packets_recv - a.packets_recv, pc_sent_delta=b.packets_sent - a.packets_sent,
                   stderr=p.stderr.decode("utf-8", "replace").strip()[:200], **f)
        if ok:
            # 该卡统计一小时内被清零过至少两次（README 第 8 节）：窗口内任一累计计数变小或接口号变了 ⇒ 该窗作废
            idx_after = ifindex_by_ip(HOT_IP)
            keys = ("out_ucast", "in_ucast", "out_discards")
            reset = [k for k in keys if ub[k] < ua[k]] + (["ifindex"] if idx_after != [idx] else [])
            rec.update(psutil_reset_in_window=b.packets_sent < a.packets_sent or b.packets_recv < a.packets_recv)
            rec.update(window_s=round(dur, 2), uc_rc=[ua["rc"], ub["rc"]], reset_in_window=reset,
                       pc_ucast_sent_delta=ub["out_ucast"] - ua["out_ucast"],
                       pc_ucast_recv_delta=ub["in_ucast"] - ua["in_ucast"],
                       pc_out_discards_delta=ub["out_discards"] - ua["out_discards"])
            g0 = uc_snap(idx)
            tsb = now()
            time.sleep(dur)
            g1 = uc_snap(idx)
            reset_bg = [k for k in keys if g1[k] < g0[k]] + (["ifindex"] if ifindex_by_ip(HOT_IP) != [idx] else [])
            rec.update(bg_ts=tsb, bg_window_s=round(dur, 2), bg_reset_in_window=reset_bg,
                       bg_ucast_sent_delta=g1["out_ucast"] - g0["out_ucast"],
                       bg_ucast_recv_delta=g1["in_ucast"] - g0["in_ucast"],
                       bg_out_discards_delta=g1["out_discards"] - g0["out_discards"])
            d = rec["pc_ucast_sent_delta"] - rec["bg_ucast_sent_delta"]
            disc = rec["pc_out_discards_delta"] - rec["bg_out_discards_delta"]
            as1 = assoc_snap()
            unstable = [k for k in ("supplicant", "inet", "ifindex", "pc_link") if as0[k] != as1[k]]
            if as0["supplicant"] != "COMPLETED":
                unstable.append("supplicant_not_completed")
            rec.update(assoc_before=as0, assoc_after=as1, assoc_changed=unstable)
            if unstable:
                rec.update(d=None, disc=None, window_label="关联不稳")
                if decide:
                    rec["judgement"] = "判不了（关联不稳：%s 在 ping 窗与背景窗前后不一致）" % unstable
            elif reset or reset_bg:
                rec.update(d=None, disc=None)
                if decide:
                    rec["judgement"] = "判不了（窗口内计数器被清零或接口号变化：ping 窗 %s，背景窗 %s）" % (reset, reset_bg)
            else:
                rec.update(d=d, disc=disc)
                if decide:
                    rec["judgement"] = ("手机已收到回复（通），计数只作一致性核对：" if n else "") + \
                        verdict(P, d, disc, rec["bg_ucast_sent_delta"])
        R.append(rec)

    def clients():
        ps = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; & { "
              "$null=[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]; "
              "$null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]; "
              "$pr=[Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile(); "
              "$tm=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($pr); "
              "[pscustomobject]@{State=$tm.TetheringOperationalState.ToString();Clients=$tm.ClientCount} } "
              "| ConvertTo-Json -Compress")
        t = now()
        p = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, timeout=300)
        try:
            j = json.loads(p.stdout.decode("utf-8", "replace"))
        except ValueError:
            j = {}
        return dict(ts=t, rc=p.returncode, state=j.get("State"), clients=j.get("Clients"))

    cl0 = clients() if gate else None
    probe(HOT_IP, "run6 第一跳：手机 ping 网关（辅助，不出判词）", decide=False)
    probe("223.5.5.5", "run6 方向判别：手机 ping 上游目标", decide=True)
    if gate:
        cl1 = clients()
        R.append(dict(ts=cl1["ts"], layer="PC", item="热点客户端数（整轮前后，WinRT 全局态）",
                      argv=["powershell", "（脚本内 clients() 原样）"],
                      channel="PowerShell 5.1 → JSON → python；rc＝powershell.exe 的 python returncode",
                      rc=[cl0["rc"], cl1["rc"]], verdict="—", before=cl0, after=cl1,
                      changed=(cl0["state"], cl0["clients"]) != (cl1["state"], cl1["clients"])))

    argv, ts, rc, out = adb_sh("dumpsys", "power")
    wk = re.search(r"mWakefulness=(\w+)", out)
    R.append(dict(ts=ts, layer="P40", item="屏幕态（本跑收尾）", argv=argv + ["（只取 mWakefulness）"],
                  channel="adb shell → python；rc＝adb 的 python returncode", rc=rc, verdict="—",
                  wakefulness=wk.group(1) if wk else None))
    path = write("readings_run6_%s.json" % t_start)
    for x in R:
        print(json.dumps({k: v for k, v in x.items() if k not in ("argv", "channel")}, ensure_ascii=False)[:1500])
    print("->", path)


if __name__ == "__main__":
    main()
