# -*- coding: utf-8 -*-
"""设备三层前提门 · 第一跳方向判别（run4）。只读；产物 readings_run4_direction.json。

同一条 adb shell 里：读 wlan0 收发计数 → ping 网关 3 包 → 再读计数；前后各读一次 PC 热点虚拟卡的单播收发计数。
回答的问题：第一跳不通时，包有没有从手机驱动发出（手机 tx 增量）、PC 那张卡有没有收到（PC rx 增量）、
有没有东西回到手机（手机 rx 增量）。计数是真实流量计数，不是配置派生；但窗口内的背景流量会混入，
故只把「增量为 0」当强读数，「增量 ≥3」只当弱读数。
"""
import datetime
import json
import os
import re
import subprocess

OUTDIR = "evidence/c_device_gate_20260926"
SERIAL = "8MY0221126002537"
GW = "192.168.137.1"
R = []


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def run(argv, timeout=240):
    ts = now()
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout)
        return ts, p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return ts, None, "", "timeout"


PS = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; & { "
      "$i=(Get-NetIPAddress -AddressFamily IPv4 -IPAddress %s).InterfaceIndex; "
      "Get-NetAdapter -InterfaceIndex $i | Get-NetAdapterStatistics | "
      "Select-Object @{n='ifIndex';e={$i}},ReceivedUnicastPackets,SentUnicastPackets } | ConvertTo-Json -Compress" % GW)
CH_PS = "PowerShell 5.1 Get-NetAdapterStatistics → JSON；rc＝powershell.exe 的 python returncode"
CH_ADB = "adb shell（单条命令内读计数/ping/再读计数）→ python；rc＝adb 的 python returncode"


def pc_stats():
    argv = ["powershell", "-NoProfile", "-NonInteractive", "-Command", PS]
    ts, rc, out, err = run(argv)
    d = json.loads(out) if rc == 0 and out.strip() else None
    return argv, ts, rc, d, err.strip()[:300]


argv, ts, rc, pa, err = pc_stats()
R.append(dict(ts=ts, layer="PC", item="热点虚拟卡单播计数（前）", argv=argv, channel=CH_PS, rc=rc, verdict="—", stats=pa, err=err))

SYS = "/sys/class/net/wlan0"
block = ("cat %s/operstate; cat %s/statistics/tx_packets %s/statistics/rx_packets; "
         "ping -c 3 -W 2 %s; echo PING_RC=$?; "
         "cat %s/statistics/tx_packets %s/statistics/rx_packets; cat /proc/net/wireless"
         % (SYS, SYS, SYS, GW, SYS, SYS))
argv = ["adb", "-s", SERIAL, "shell", block]
ts, rc, out, err = run(argv, 60)
lines = [l.strip() for l in out.splitlines()]
oper = lines[0] if lines else None
nums = [int(l) for l in lines if re.fullmatch(r"\d+", l)]
replies = sum(1 for l in lines if ("from %s" % GW) in l and "ttl=" in l.lower())
prc = re.search(r"PING_RC=(\d+)", out)
wl = re.search(r"^\s*wlan0:\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", out, re.M)
f = dict(operstate=oper, replies_from_gw=replies,
         ping_rc_inside_shell=int(prc.group(1)) if prc else None,
         proc_net_wireless=dict(status=wl.group(1), link=wl.group(2), level=wl.group(3), noise=wl.group(4)) if wl else None)
if len(nums) == 4:
    f.update(tx_before=nums[0], rx_before=nums[1], tx_after=nums[2], rx_after=nums[3],
             tx_delta=nums[2] - nums[0], rx_delta=nums[3] - nums[1])
else:
    f["note"] = "计数行数不是 4（%d），不计增量" % len(nums)
R.append(dict(ts=ts, layer="P40", item="wlan0 计数 + ping 网关 + 计数（同一 shell）", argv=argv, channel=CH_ADB,
              rc=rc, verdict="通" if replies else "不通", **f))

argv, ts, rc, pb, err = pc_stats()
R.append(dict(ts=ts, layer="PC", item="热点虚拟卡单播计数（后）", argv=argv, channel=CH_PS, rc=rc, verdict="—", stats=pb, err=err))
if pa and pb:
    R.append(dict(ts=now(), layer="PC", item="热点虚拟卡单播增量（前后两读之差）", argv=["（由前两项算出）"],
                  channel="由两次 Get-NetAdapterStatistics 读数相减", rc=0, verdict="—",
                  rx_delta=pb["ReceivedUnicastPackets"] - pa["ReceivedUnicastPackets"],
                  tx_delta=pb["SentUnicastPackets"] - pa["SentUnicastPackets"]))

argv = ["adb", "-s", SERIAL, "shell", "dumpsys", "power"]
ts, rc, out, err = run(argv, 60)
wk = re.search(r"mWakefulness=(\w+)", out)
R.append(dict(ts=ts, layer="P40", item="屏幕态（本跑收尾）", argv=argv + ["（只取 mWakefulness）"], channel=CH_ADB,
              rc=rc, verdict="—", wakefulness=wk.group(1) if wk else None))

blob = json.dumps(R, ensure_ascii=False, indent=1)
assert not re.search(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b", blob), "读数含 MAC 样式串"
assert not re.search(r"(?i)ssid\s*[:=]", blob), "读数含网络名字段"
data = blob.encode("utf-8")
path = os.path.join(OUTDIR, "readings_run4_direction.json")
with open(path, "wb") as fh:
    fh.write(data)
with open(path, "rb") as fh:
    assert fh.read() == data
for x in R:
    print(json.dumps({k: v for k, v in x.items() if k not in ("argv", "channel")}, ensure_ascii=False))
