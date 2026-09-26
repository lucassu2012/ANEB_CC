# -*- coding: utf-8 -*-
"""设备三层前提门 · 补读（run3）。只读；产物 evidence/c_device_gate_20260926/readings_run3_supplement.json。

补 run2 的四个缺口：
- 网卡状态（run2 Get-NetAdapter 超时）；
- ICS 共享源：run2 HNetCfg 枚举到 0 条连接（机上 7 张卡 ⇒ 量法失败，不是「没共享」），换两种读法：
  WMI root/Microsoft/HomeNet 的 HNet_ConnectionProperties(IsIcsPublic/IsIcsPrivate)，与 HNetCfg 用 @() 展开重试，
  两路都把错误原样落下；
- 源地址 ping 的候选卡补上 169.254 地址的卡（WLAN 等；run2 按 APIPA 过滤掉了，D-871 的判决性对照恰是 WLAN）；
- 反向第一跳：PC 以热点虚拟卡地址为源 ping 手机的热点地址，外加双方服务状态与 PC 侧邻居状态（不落链路层地址）。
"""
import datetime
import json
import os
import re
import subprocess

OUTDIR = "evidence/c_device_gate_20260926"
TARGET = "223.5.5.5"
SERIAL = "8MY0221126002537"
R = []


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def run(argv, timeout=240, enc="utf-8"):
    ts = now()
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout)
        return ts, p.returncode, p.stdout.decode(enc, "replace"), p.stderr.decode(enc, "replace")
    except subprocess.TimeoutExpired:
        return ts, None, "", "timeout %ss" % timeout


def rec(ts, layer, item, argv, channel, rc, verdict, **f):
    R.append(dict(ts=ts, layer=layer, item=item, argv=argv, channel=channel, rc=rc, verdict=verdict, **f))


PS_PRE = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ErrorActionPreference='Continue'; "
CH_PS = "PowerShell 5.1 → ConvertTo-Json → python 解析；rc＝powershell.exe 的 python returncode"
CH_PING = "ping.exe 原生输出（cp936 解码）→ 只数来自目标且带 TTL= 的行；rc＝ping.exe 的 python returncode"
CH_ADB = "adb shell → python；rc＝adb 的 python returncode"


def ps_json(script, timeout=240):
    argv = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
            PS_PRE + "& { " + script + " } | ConvertTo-Json -Depth 4 -Compress"]
    ts, rc, out, err = run(argv, timeout)
    data = []
    if out.strip():
        try:
            d = json.loads(out)
            data = d if isinstance(d, list) else [d]
        except ValueError:
            data = [{"unparsed": out.strip()[:400]}]
    return argv, ts, rc, data, err.strip()[:600]


def ping_pc(src, dst):
    argv = ["ping", "-n", "3", "-w", "2000"] + (["-S", src] if src else []) + [dst]
    ts, rc, out, err = run(argv, 30, enc="cp936")
    n = sum(1 for l in out.splitlines() if dst in l and "TTL=" in l.upper())
    return argv, ts, rc, n, out.strip()


# ---- PC：网卡状态（不取 MAC）----
argv, ts, rc, ads, err = ps_json(
    "Get-NetAdapter -IncludeHidden | Select-Object Name,InterfaceIndex,Status,InterfaceDescription")
rec(ts, "PC", "网卡状态（含隐藏）", argv, CH_PS, rc, "—", rows=ads, err=err)

# ---- PC：服务状态 ----
argv, ts, rc, sv, err = ps_json(
    "Get-Service SharedAccess,icssvc | Select-Object Name,@{n='Status';e={$_.Status.ToString()}}")
rec(ts, "PC", "ICS/移动热点服务状态", argv, CH_PS, rc, "—", rows=sv, err=err)

# ---- PC：ICS 共享源，读法一：WMI HomeNet ----
argv, ts, rc, hn, err = ps_json(
    "Get-CimInstance -Namespace root/Microsoft/HomeNet -ClassName HNet_ConnectionProperties | "
    "ForEach-Object { [pscustomobject]@{ConnRef=[string]$_.Connection; "
    "IsIcsPublic=$_.IsIcsPublic; IsIcsPrivate=$_.IsIcsPrivate} }")
argv2, ts2, rc2, hc, err2 = ps_json(
    "Get-CimInstance -Namespace root/Microsoft/HomeNet -ClassName HNet_Connection | "
    "Select-Object Guid,Name")
names = {}
for c in hc:
    if isinstance(c, dict) and c.get("Guid"):
        names[c["Guid"].strip("{}").lower()] = c.get("Name")
rows = []
for x in hn:
    if not isinstance(x, dict) or "ConnRef" not in x:
        rows.append(x)
        continue
    g = re.search(r"\{?([0-9A-Fa-f-]{36})\}?", x.get("ConnRef") or "")
    rows.append(dict(Name=names.get(g.group(1).lower()) if g else None,
                     IsIcsPublic=x.get("IsIcsPublic"), IsIcsPrivate=x.get("IsIcsPrivate")))
pub = [r.get("Name") for r in rows if r.get("IsIcsPublic")]
prv = [r.get("Name") for r in rows if r.get("IsIcsPrivate")]
rec(ts, "PC", "ICS 共享源（读法一 WMI HomeNet）", [argv, argv2], CH_PS, rc,
    "—" if rows else "未执行", rows=rows, public=pub, private=prv, n_conn=len(hc), err=(err + " | " + err2).strip(" |"))

# ---- PC：ICS 共享源，读法二：HNetCfg，@() 展开 ----
argv, ts, rc, hs, err = ps_json(
    "$m=New-Object -ComObject HNetCfg.HNetShare; $all=@($m.EnumEveryConnection); "
    "[pscustomobject]@{Count=$all.Count}; "
    "foreach($c in $all){ $p=$m.NetConnectionProps.Invoke($c); "
    "$s=$m.INetSharingConfigurationForINetConnection.Invoke($c); "
    "[pscustomobject]@{Name=$p.Name;SharingEnabled=$s.SharingEnabled;SharingType=$s.SharingConnectionType} }")
cnt = next((x.get("Count") for x in hs if isinstance(x, dict) and "Count" in x), None)
hrows = [x for x in hs if isinstance(x, dict) and "Name" in x]
rec(ts, "PC", "ICS 共享源（读法二 HNetCfg，@() 展开）", argv, CH_PS, rc, "—" if hrows else "未执行",
    enum_count=cnt, rows=hrows,
    public=[x["Name"] for x in hrows if x.get("SharingEnabled") and x.get("SharingType") == 0],
    private=[x["Name"] for x in hrows if x.get("SharingEnabled") and x.get("SharingType") == 1], err=err)

# ---- PC：全部 IPv4 地址（含 169.254）逐个作源 ping 上游 ----
argv, ts, rc, ips, err = ps_json(
    "Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceIndex,InterfaceAlias,IPAddress")
rec(ts, "PC", "IPv4 地址（run3 复读）", argv, CH_PS, rc, "—", rows=ips, err=err)
for x in ips:
    if not isinstance(x, dict) or str(x.get("IPAddress", "")).startswith("127."):
        continue
    argv, ts, rc, n, raw = ping_pc(x["IPAddress"], TARGET)
    rec(ts, "PC", "源地址 ping 上游（%s）" % x["InterfaceAlias"], argv, CH_PING, rc,
        "未执行" if rc is None else ("通" if n else "不通"), ifIndex=x["InterfaceIndex"], replies_from_target=n, raw=raw)

# ---- 反向第一跳：PC(热点虚拟卡地址) → 手机热点地址 ----
argv = ["adb", "-s", SERIAL, "shell", "ip", "-4", "addr", "show", "wlan0"]
ts, rc, out, err = run(argv, 30)
m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)/", out)
phone = m.group(1) if m else None
rec(ts, "P40", "手机 wlan0 地址（只取 inet）", argv, CH_ADB, rc, "—", inet=phone)
hot = next((x for x in ips if isinstance(x, dict) and x.get("IPAddress") == "192.168.137.1"), None)
if phone and hot:
    argv, ts, rc, n, raw = ping_pc(hot["IPAddress"], phone)
    rec(ts, "PC", "反向第一跳 ping 手机（源＝热点虚拟卡）", argv, CH_PING, rc,
        "未执行" if rc is None else ("通" if n else "不通"), replies_from_target=n, raw=raw)
    argv, ts, rc, nb, err = ps_json(
        "Get-NetNeighbor -AddressFamily IPv4 -IPAddress %s -ErrorAction SilentlyContinue | "
        "Select-Object ifIndex,IPAddress,@{n='State';e={$_.State.ToString()}}" % phone)
    rec(ts, "PC", "PC 侧对手机的邻居状态（配置派生，旁证）", argv, CH_PS, rc, "—", rows=nb, err=err)
else:
    rec(now(), "PC", "反向第一跳 ping 手机（源＝热点虚拟卡）", [], CH_PING, None, "未执行",
        reason="未取到手机地址或热点虚拟卡地址")

# ---- 手机屏幕态（与本跑同时刻）----
argv = ["adb", "-s", SERIAL, "shell", "dumpsys", "power"]
ts, rc, out, err = run(argv, 60)
wk = re.search(r"mWakefulness=(\w+)", out)
rec(ts, "P40", "屏幕态（与本跑同时刻）", argv + ["（只取 mWakefulness）"], CH_ADB, rc, "—",
    wakefulness=wk.group(1) if wk else None)

blob = json.dumps(R, ensure_ascii=False, indent=1)
assert not re.search(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b", blob), "读数含 MAC 样式串"
assert not re.search(r"(?i)ssid\s*[:=]", blob), "读数含网络名字段"
data = blob.encode("utf-8")
path = os.path.join(OUTDIR, "readings_run3_supplement.json")
with open(path, "wb") as fh:
    fh.write(data)
with open(path, "rb") as fh:
    assert fh.read() == data
print("OK readings=%d" % len(R))
for x in R:
    print("%s | %-4s | %s | rc=%s | %s" % (x["ts"], x["layer"], x["item"], x["rc"], x["verdict"]))
