# -*- coding: utf-8 -*-
"""两侧关联状态只读快照（大脑 2026-09-26 急件：PO 截图显示热点已连接设备 0 台）。只读，不发包。

回答「手机此刻在不在 PC 热点上」而**不打印、不落盘任何网络名与链路层地址**（D-608⑤、SSID/BSSID 不入库）：
网络名与地址只在内存里比对，只落布尔值。写盘前断言产物里不含读到的网络名字符串、不含 MAC 样式串。
另读冲突门拦下 run6 的那个进程的来历（包信息、进程、是否在无障碍服务名单里）——只读，不停不动。

用法（仓根）：python evidence/c_device_gate_20260926/gate_assoc.py
产物：readings_assoc_<开始时刻>.json
"""
import datetime
import json
import os
import re
import subprocess

D = "evidence/c_device_gate_20260926"
SERIAL = "8MY0221126002537"
HOT_IP = "192.168.137.1"
PKG = "com.aneb.experiencelab"
R = []
SECRETS = []  # 读到的网络名，只用于写盘前断言


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def run(argv, timeout=120):
    ts = now()
    p = subprocess.run(argv, capture_output=True, timeout=timeout)
    return ts, p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def norm_mac(s):
    return re.sub(r"[^0-9a-f]", "", (s or "").lower())


CH_ADB = "adb shell → python（原文只在内存解析，只落派生字段）；rc＝adb 的 python returncode"
CH_PS = "PowerShell 5.1 → JSON → python（网络名与地址只在内存比对）；rc＝powershell.exe 的 python returncode"

# ---- PC 侧：热点状态、客户端、热点网络名与虚拟卡地址（后两者只进内存）----
ps = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; & { "
      "$null=[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]; "
      "$null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]; "
      "$pr=[Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile(); "
      "$tm=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($pr); "
      "$cl=@(); try{ foreach($c in $tm.GetTetheringClients()){ $cl += [string]$c.MacAddress } }catch{ $cl=$null }; "
      "$i=(Get-NetIPAddress -AddressFamily IPv4 -IPAddress %s).InterfaceIndex; "
      "[pscustomobject]@{State=$tm.TetheringOperationalState.ToString();Clients=$tm.ClientCount;"
      "ApName=$tm.GetCurrentAccessPointConfiguration().Ssid;ClientMacs=$cl;IfIndex=$i;"
      "VMac=(Get-NetAdapter -InterfaceIndex $i).MacAddress} } | ConvertTo-Json -Compress" % HOT_IP)
argv_ps = ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps]
ts, rc, out, err = run(argv_ps, 300)
pc = {}
try:
    pc = json.loads(out)
except ValueError:
    pc = {}
ap_name = pc.get("ApName") or ""
if ap_name:
    SECRETS.append(ap_name)
client_macs = pc.get("ClientMacs")
if isinstance(client_macs, str):
    client_macs = [client_macs]
vmac = norm_mac(pc.get("VMac"))
R.append(dict(ts=ts, layer="PC", item="热点状态与客户端（WinRT；网络名与地址只进内存）",
              argv=["powershell", "-NoProfile", "-NonInteractive", "-Command", "（脚本内原样见 gate_assoc.py 的 ps 变量）"],
              channel=CH_PS, rc=rc, verdict="—", state=pc.get("State"), client_count=pc.get("Clients"),
              client_list_readable=client_macs is not None,
              client_list_len=len(client_macs) if client_macs is not None else None,
              hotspot_ifindex=pc.get("IfIndex"), ap_name_read=bool(ap_name), vmac_read=bool(vmac),
              err=err.strip()[:300]))

# ---- P40 侧 ----
def adb(*a, timeout=60):
    argv = ["adb", "-s", SERIAL, "shell", *a]
    ts, rc, out, err = run(argv, timeout)
    return argv, ts, rc, out, err


argv, ts, rc, st, err = adb("cmd", "wifi", "status")
src = "cmd wifi status"
if rc != 0 or "SSID" not in st:
    argv, ts, rc, st, err = adb("dumpsys", "wifi")
    src = "dumpsys wifi"
# 本机实测（14:07，只看了字段名不看值）：cmd wifi status 的 WifiInfo 行只有 SSID 等字段、不给 BSSID 与本机 MAC；
# 网络名取「Wifi is connected to "…"」那一行；本机网卡地址取 ip link；BSSID 取 dumpsys wifi 的 mWifiInfo 行。
m_ssid = re.search(r'^Wifi is connected to "(.*)"\s*$', st, re.M)
m_sup = re.search(r"Supplicant state: (\w+)", st)
m_rssi = re.search(r"RSSI: (-?\d+)", st)
m_freq = re.search(r"Frequency: (\d+)", st)
phone_ssid = m_ssid.group(1) if m_ssid else ""
if phone_ssid:
    SECRETS.append(phone_ssid)
_, _, _, lk, _ = adb("ip", "link", "show", "wlan0")
m_mac = re.search(r"link/ether ([0-9a-fA-F:]{17})", lk)
phone_mac = norm_mac(m_mac.group(1)) if m_mac else ""
_, _, _, dw, _ = adb("dumpsys", "wifi", timeout=90)
m_bssid = re.search(r"mWifiInfo SSID: .*?, BSSID: ([0-9a-fA-F:]{17})", dw)
phone_bssid = norm_mac(m_bssid.group(1)) if m_bssid else ""
lk = dw = None
connected_line = bool(m_ssid)
R.append(dict(ts=ts, layer="P40", item="手机当前 Wi-Fi 关联（%s；网络名与地址只进内存）" % src,
              argv=argv, channel=CH_ADB, rc=rc, verdict="—",
              wifi_connected_line=connected_line, supplicant_state=m_sup.group(1) if m_sup else None,
              rssi=int(m_rssi.group(1)) if m_rssi else None, frequency_mhz=int(m_freq.group(1)) if m_freq else None,
              ssid_read=bool(phone_ssid), bssid_read=bool(phone_bssid), mac_read=bool(phone_mac),
              same_network_name_as_pc_hotspot=(phone_ssid == ap_name) if (phone_ssid and ap_name) else None,
              bssid_equals_pc_hotspot_adapter=(phone_bssid == vmac) if (phone_bssid and vmac) else None,
              phone_mac_in_hotspot_clients=(phone_mac in [norm_mac(x) for x in client_macs])
              if (phone_mac and client_macs is not None) else None))
st = None

argv, ts, rc, out, err = adb("ip", "-4", "addr", "show", "wlan0")
inet = re.search(r"inet (\d+\.\d+\.\d+\.\d+/\d+)", out)
argv2, ts2, rc2, out2, err2 = adb("ip", "route", "get", "223.5.5.5")
via = re.search(r"\bvia (\S+)", out2)
dev = re.search(r"\bdev (\S+)", out2)
argv3, ts3, rc3, out3, err3 = adb("cat", "/proc/net/wireless")
wl = re.search(r"^\s*wlan0:\s+(\S+)\s+(\S+)\s+(\S+)", out3, re.M)
R.append(dict(ts=ts, layer="P40", item="手机 wlan0 地址、出口、无线链路（配置派生，旁证）",
              argv=[argv, argv2, argv3], channel=CH_ADB, rc=[rc, rc2, rc3], verdict="—",
              inet=inet.group(1) if inet else None, route_via=via.group(1) if via else None,
              route_dev=dev.group(1) if dev else None,
              proc_net_wireless=dict(status=wl.group(1), link=wl.group(2), level=wl.group(3)) if wl else None))

# ---- 冲突门拦下 run6 的进程 ----
argv, ts, rc, out, err = adb("dumpsys", "package", PKG)
f = {k: (re.search(r"%s=(\S+(?: \S+)?)" % k, out).group(1) if re.search(r"%s=" % k, out) else None)
     for k in ("versionName", "firstInstallTime", "lastUpdateTime", "installerPackageName")}
argv2, ts2, rc2, out2, err2 = adb("ps", "-A", "-o", "PID,USER,NAME")
procs = [" ".join(l.split()) for l in out2.splitlines() if PKG in l]
argv3, ts3, rc3, out3, err3 = adb("settings", "get", "secure", "enabled_accessibility_services")
a11y = [x for x in out3.strip().split(":") if x]
argv4, ts4, rc4, out4, err4 = adb("dumpsys", "activity", "services", PKG)
svcs = sorted(set(re.findall(r"ServiceRecord\{\S+ \S+ (%s/\S+?)\}" % re.escape(PKG), out4)))
R.append(dict(ts=ts, layer="P40", item="冲突门拦下的进程 %s 的来历（只读，不停不动）" % PKG,
              argv=[argv, argv2, argv3, argv4], channel="adb shell → python；rc＝adb 的 python returncode",
              rc=[rc, rc2, rc3, rc4], verdict="—", package=f, processes=procs,
              in_enabled_accessibility_services=[x for x in a11y if PKG in x],
              running_services=svcs))

argv, ts, rc, out, err = adb("dumpsys", "power")
wk = re.search(r"mWakefulness=(\w+)", out)
R.append(dict(ts=ts, layer="P40", item="屏幕态（本快照收尾）", argv=argv + ["（只取 mWakefulness）"],
              channel="adb shell → python；rc＝adb 的 python returncode", rc=rc, verdict="—",
              wakefulness=wk.group(1) if wk else None))

blob = json.dumps(R, ensure_ascii=False, indent=1)
assert not re.search(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b", blob), "产物含 MAC 样式串"
assert not re.search(r"(?i)\b[0-9a-f]{12}\b", blob), "产物含 12 位十六进制串（疑似去分隔的地址）"
for s in SECRETS:
    if len(s) >= 3:
        assert s not in blob, "产物含读到的网络名"
data = blob.encode("utf-8")
path = os.path.join(D, "readings_assoc_%s.json" % datetime.datetime.now().strftime("%H%M%S"))
with open(path, "wb") as fh:
    fh.write(data)
with open(path, "rb") as fh:
    assert fh.read() == data
print("->", path)
for x in R:
    print(json.dumps({k: v for k, v in x.items() if k not in ("argv", "channel")}, ensure_ascii=False)[:900])
