# -*- coding: utf-8 -*-
"""设备三层前提门 · 第一跳方向判别（run5，替代 run4 的读法）。只读；产物 readings_run5_direction.json。

run4 的两处缺陷：手机侧 /sys/class/net 对 shell 无权限（计数 0 行）且解析把 ping 头行错标成 operstate；
PC 侧 PowerShell 每读一次 1-2 分钟，窗口 2m23s 混入背景流量。本跑改：
- 手机侧计数读 /proc/net/dev 的 wlan0 行（同一条 adb shell 内：读 → ping 3 包 → 读）；
- PC 侧计数用 psutil.net_io_counters(pernic=True)（GetIfEntry2，含单播与非单播），紧贴 adb 调用前后读，窗口秒级。
对网关与对 223.5.5.5 各做一次。只把「增量为 0」当强读数；增量里混有背景流量，只当弱读数。
"""
import datetime
import json
import os
import re
import subprocess

import psutil

OUTDIR = "evidence/c_device_gate_20260926"
SERIAL = "8MY0221126002537"
HOT_IP = "192.168.137.1"
R = []


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def hot_nic():
    for name, addrs in psutil.net_if_addrs().items():
        if any(a.address == HOT_IP for a in addrs):
            return name
    return None


NIC = hot_nic()
assert NIC, "未找到持有 %s 的网卡" % HOT_IP


def pc():
    c = psutil.net_io_counters(pernic=True)[NIC]
    return dict(t=now(), recv=c.packets_recv, sent=c.packets_sent)


def devline(text):
    m = [l for l in text.splitlines() if l.strip().startswith("wlan0:")]
    return m


def probe(dst, label):
    block = ("cat /proc/net/dev | grep wlan0; ping -c 3 -W 2 %s; echo PING_RC=$?; "
             "cat /proc/net/dev | grep wlan0" % dst)
    argv = ["adb", "-s", SERIAL, "shell", block]
    a = pc()
    ts = now()
    p = subprocess.run(argv, capture_output=True, timeout=60)
    b = pc()
    out = p.stdout.decode("utf-8", "replace")
    err = p.stderr.decode("utf-8", "replace").strip()
    rows = devline(out)
    f = {}
    if len(rows) == 2:
        x0, x1 = rows[0].split(":", 1)[1].split(), rows[1].split(":", 1)[1].split()
        # /proc/net/dev 字段：rx bytes packets errs drop ... (8 个) | tx bytes packets errs drop ...
        f.update(phone_rx_delta=int(x1[1]) - int(x0[1]), phone_tx_delta=int(x1[9]) - int(x0[9]),
                 phone_tx_drop_delta=int(x1[11]) - int(x0[11]), phone_rx_drop_delta=int(x1[3]) - int(x0[3]))
    else:
        f["note"] = "wlan0 行数不是 2（%d），不计手机增量" % len(rows)
    n = sum(1 for l in out.splitlines() if ("from %s" % dst) in l and "ttl=" in l.lower())
    prc = re.search(r"PING_RC=(\d+)", out)
    R.append(dict(ts=ts, layer="P40+PC", item=label, argv=argv,
                  channel="adb shell（计数/ping/计数同一条命令）；PC 计数 psutil.net_io_counters 紧贴 adb 前后读（%s）；"
                          "rc＝adb 的 python returncode，ping 自身退出码另记 ping_rc_inside_shell" % NIC,
                  rc=p.returncode, verdict="通" if n else "不通", replies_from_target=n,
                  ping_rc_inside_shell=int(prc.group(1)) if prc else None,
                  pc_window=[a["t"], b["t"]], pc_recv_delta=b["recv"] - a["recv"], pc_sent_delta=b["sent"] - a["sent"],
                  stderr=err[:200], **f))


probe(HOT_IP, "第一跳方向判别：手机 ping 网关")
probe("223.5.5.5", "方向判别：手机 ping 上游目标")

argv = ["adb", "-s", SERIAL, "shell", "dumpsys", "power"]
ts = now()
p = subprocess.run(argv, capture_output=True, timeout=60)
wk = re.search(r"mWakefulness=(\w+)", p.stdout.decode("utf-8", "replace"))
R.append(dict(ts=ts, layer="P40", item="屏幕态（本跑收尾）", argv=argv + ["（只取 mWakefulness）"],
              channel="adb shell → python；rc＝adb 的 python returncode", rc=p.returncode, verdict="—",
              wakefulness=wk.group(1) if wk else None))

blob = json.dumps(R, ensure_ascii=False, indent=1)
assert not re.search(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b", blob), "读数含 MAC 样式串"
assert not re.search(r"(?i)ssid\s*[:=]", blob), "读数含网络名字段"
data = blob.encode("utf-8")
path = os.path.join(OUTDIR, "readings_run5_direction.json")
with open(path, "wb") as fh:
    fh.write(data)
with open(path, "rb") as fh:
    assert fh.read() == data
for x in R:
    print(json.dumps({k: v for k, v in x.items() if k not in ("argv", "channel")}, ensure_ascii=False))
