# -*- coding: utf-8 -*-
"""设备三层前提门 · 只读诊断（大脑 2026-09-26 派单②）。一次性，scratchpad，仓根运行。

纪律：
- 只读：不改任何设置、不停任何 App、不写设备。
- 退出码一律取 python subprocess.returncode（原生值），不用 bash $?（D-891）。
- 「通」只按收到来自目标、带 TTL 的回复判（D-906）；route get 等配置派生读数只作旁证。
- ifIndex 现场取，不写死（D-907）。
- dumpsys connectivity 只在内存里解析，只落派生字段（D-608⑤：原文含网络名）。
- 锁屏下的前台应用（mFocusedApp）不是华为桌面、或有 tun/ppp 在起时，不从设备发 ping（可能有他人测量在跑），
  相应格记「未执行」。run1 用的是 mCurrentFocus＝桌面，看过 run1 后改成现在这样，理由见证据目录 README 第 3 节。
- 写盘前断言产物不含 MAC 样式串与网络名字段。
"""
import datetime
import json
import os
import re
import subprocess

OUTDIR = "evidence/c_device_gate_20260926"
TARGET = "223.5.5.5"
SERIAL_PREF = "8MY0221126002537"
LAUNCHER = "com.huawei.android.launcher"
R = []


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def run(argv, timeout=60, enc="utf-8"):
    ts = now()
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout)
        return ts, p.returncode, p.stdout.decode(enc, "replace"), p.stderr.decode(enc, "replace")
    except FileNotFoundError as e:
        return ts, None, "", "FileNotFound: %s" % e
    except subprocess.TimeoutExpired:
        return ts, None, "", "timeout %ss" % timeout


def rec(ts, layer, item, argv, channel, rc, verdict, **f):
    R.append(dict(ts=ts, layer=layer, item=item, argv=argv, channel=channel, rc=rc, verdict=verdict, **f))


PS_PRE = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "


def ps_json(script, timeout=90):
    argv = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
            PS_PRE + "& { " + script + " } | ConvertTo-Json -Depth 4 -Compress"]
    ts, rc, out, err = run(argv, timeout)
    data = None
    if rc == 0 and out.strip():
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
    return argv, ts, rc, data or [], err.strip()[:300]


CH_PS = "PowerShell 5.1 → ConvertTo-Json → python 解析；rc＝powershell.exe 的 python returncode"
CH_PING = "ping.exe 原生输出（cp936 解码）→ 只数来自目标且带 TTL= 的行；rc＝ping.exe 的 python returncode"
CH_ADB = "adb shell → python；rc＝adb 的 python returncode（shell v2 透传远端退出码）"

# ================= PC 侧 =================
argv, ts, rc, adapters, err = ps_json(
    "Get-NetAdapter | Select-Object Name,InterfaceIndex,Status,InterfaceDescription,InterfaceGuid")
rec(ts, "PC", "网卡清单", argv, CH_PS, rc, "—", n=len(adapters), err=err)
by_guid = {a["InterfaceGuid"].strip("{}").lower(): a for a in adapters if a.get("InterfaceGuid")}
by_idx = {a["InterfaceIndex"]: a for a in adapters}

argv, ts, rc, ips, err = ps_json(
    "Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceIndex,InterfaceAlias,IPAddress,PrefixLength")
rec(ts, "PC", "IPv4 地址", argv, CH_PS, rc, "—", rows=ips, err=err)

argv, ts, rc, routes, err = ps_json(
    "Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' | "
    "Select-Object ifIndex,InterfaceAlias,NextHop,RouteMetric")
argv2, ts2, rc2, ifm, err2 = ps_json(
    "Get-NetIPInterface -AddressFamily IPv4 | Select-Object ifIndex,InterfaceAlias,InterfaceMetric,ConnectionState")
metric = {x["ifIndex"]: x.get("InterfaceMetric") for x in ifm}
for r in routes:
    r["InterfaceMetric"] = metric.get(r["ifIndex"])
rec(ts, "PC", "默认路由（含接口跃点）", [argv, argv2], CH_PS, rc, "—", rows=routes, err=err or err2)

# ICS：HNetCfg；SharingConnectionType 0＝公用（共享源），1＝专用（热点侧）
argv, ts, rc, ics, err = ps_json(
    "$m=New-Object -ComObject HNetCfg.HNetShare; "
    "foreach($c in $m.EnumEveryConnection){ $p=$m.NetConnectionProps.Invoke($c); "
    "$s=$m.INetSharingConfigurationForINetConnection.Invoke($c); "
    "[pscustomobject]@{Name=$p.Name;Guid=$p.Guid;SharingEnabled=$s.SharingEnabled;SharingType=$s.SharingConnectionType} }")
ics_src = [x for x in ics if x.get("SharingEnabled") and x.get("SharingType") == 0]
ics_prv = [x for x in ics if x.get("SharingEnabled") and x.get("SharingType") == 1]
rec(ts, "PC", "ICS 共享配置（HNetCfg）", argv, CH_PS, rc,
    "—" if rc == 0 else "未执行", rows=[{k: x.get(k) for k in ("Name", "SharingEnabled", "SharingType")} for x in ics],
    source=[x["Name"] for x in ics_src], private=[x["Name"] for x in ics_prv], err=err)

# 移动热点：逐连接配置文件问 TetheringOperationalState（不读配置文件名，那往往就是网络名）
argv, ts, rc, teth, err = ps_json(
    "$null=[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]; "
    "$null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]; "
    "foreach($pr in [Windows.Networking.Connectivity.NetworkInformation]::GetConnectionProfiles()){ "
    "$aid=$null; try{$aid=$pr.NetworkAdapter.NetworkAdapterId.ToString()}catch{}; if(-not $aid){continue}; "
    "$st=$null;$cc=$null;$e=$null; try{$tm=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($pr); "
    "$st=$tm.TetheringOperationalState.ToString(); $cc=$tm.ClientCount}catch{$e=$_.Exception.GetType().Name}; "
    "[pscustomobject]@{AdapterId=$aid;State=$st;Clients=$cc;Err=$e} }")
for t in teth:
    a = by_guid.get((t.get("AdapterId") or "").strip("{}").lower())
    t["Adapter"] = a["Name"] if a else None
    t.pop("AdapterId", None)
teth_on = [t for t in teth if t.get("State") == "On"]
rec(ts, "PC", "移动热点状态（WinRT，按连接逐个问）", argv, CH_PS, rc, "—" if rc == 0 else "未执行",
    rows=teth, source=[t["Adapter"] for t in teth_on], err=err)

# 热点虚拟卡 ifIndex：两种推法并列（持有 192.168.137.1 的接口／ICS 专用侧），不写死
vif_by_ip = [x for x in ips if x["IPAddress"] == "192.168.137.1"]
vif_by_ics = [by_guid.get(x["Guid"].strip("{}").lower()) for x in ics_prv]
rec(now(), "PC", "热点虚拟卡 ifIndex（现场推导）", ["（由上两项推出）"], "由「IPv4 地址」与「ICS 共享配置」两条读数推出", 0, "—",
    by_ip=[{"ifIndex": x["InterfaceIndex"], "alias": x["InterfaceAlias"]} for x in vif_by_ip],
    by_ics=[{"ifIndex": a["InterfaceIndex"], "alias": a["Name"]} for a in vif_by_ics if a])

# 每张候选网卡指定源地址 ping 上游目标
cands = [x for x in ips if not x["IPAddress"].startswith(("127.", "169.254."))]
for x in cands:
    argv = ["ping", "-n", "3", "-w", "2000", "-S", x["IPAddress"], TARGET]
    ts, rc, out, err = run(argv, timeout=30, enc="cp936")
    n = sum(1 for l in out.splitlines() if TARGET in l and "TTL=" in l.upper())
    v = "未执行" if rc is None else ("通" if n > 0 else "不通")
    rec(ts, "PC", "源地址 ping 上游（%s）" % x["InterfaceAlias"], argv, CH_PING, rc, v,
        ifIndex=x["InterfaceIndex"], replies_from_target=n, raw=out.strip())
argv = ["ping", "-n", "3", "-w", "2000", TARGET]
ts, rc, out, err = run(argv, timeout=30, enc="cp936")
n = sum(1 for l in out.splitlines() if TARGET in l and "TTL=" in l.upper())
rec(ts, "PC", "不指定源 ping 上游（对照）", argv, CH_PING, rc, "未执行" if rc is None else ("通" if n else "不通"),
    replies_from_target=n, raw=out.strip())

# ================= P40 侧 =================
argv = ["adb", "devices"]
ts, rc, out, err = run(argv)
devs = [l.split("\t")[0] for l in out.splitlines()[1:] if l.strip().endswith("\tdevice")]
serial = SERIAL_PREF if SERIAL_PREF in devs else (devs[0] if len(devs) == 1 else None)
rec(ts, "P40", "设备在线", argv, CH_ADB, rc, "通" if serial else "不通", devices=len(devs), serial=serial)


def adb(*a, timeout=40):
    argv = ["adb", "-s", serial, "shell", *a]
    ts, rc, out, err = run(argv, timeout)
    return argv, ts, rc, out, err


clean = False
if serial:
    argv, ts, rc, out, err = adb("dumpsys", "window")
    m = re.search(r"mCurrentFocus=Window\{\S+ \S+ (\S+?)\}", out)
    focus = m.group(1) if m else None
    rec(ts, "P40", "前台焦点（P40 流程第 1 步）", argv + ["（只取 mCurrentFocus）"], CH_ADB, rc,
        "—", focus=focus, is_launcher=bool(focus and focus.startswith(LAUNCHER)))
    argv, ts, rc, out, err = adb("ps", "-A", "-o", "NAME")
    anebs = sorted({l.strip() for l in out.splitlines() if "aneb" in l})
    rec(ts, "P40", "ANEB 进程（只读）", argv, CH_ADB, rc, "—", names=anebs)
    argv, ts, rc, out, err = adb("ip", "link")
    tun_up = sorted({m.group(1) for m in re.finditer(r"^\d+: ((?:tun|ppp)\w*)[:@].*\bUP\b", out, re.M)})
    rec(ts, "P40", "VPN/隧道接口（只取接口名）", argv, CH_ADB, rc, "—", tun_ppp_up=tun_up)
    argv, ts, rc, out, err = adb("dumpsys", "power")
    wk = re.search(r"mWakefulness=(\w+)", out)
    argv2, ts2, rc2, out2, err2 = adb("dumpsys", "window")
    fa = re.search(r"mFocusedApp=ActivityRecord\{\S+ \S+ (\S+?)[ }]", out2)
    kg = re.search(r"isKeyguardShowing=(\w+)", out2)
    fapp = fa.group(1) if fa else None
    rec(ts, "P40", "屏幕与锁屏态（只读）", [argv + ["（只取 mWakefulness）"], argv2 + ["（只取 mFocusedApp/isKeyguardShowing）"]],
        CH_ADB, rc, "—", wakefulness=wk.group(1) if wk else None, focused_app=fapp,
        keyguard=kg.group(1) if kg else None)
    # 门（第二跑修订，理由见 README）：锁屏下的前台应用＝华为桌面 且 无隧道 ⇒ 无他人前台测量
    clean = bool(fapp and fapp.startswith(LAUNCHER)) and not tun_up

    argv, ts, rc, out, err = adb("ip", "neigh", "show")
    nb = [dict(ip=m.group(1), dev=m.group(2), state=m.group(3)) for m in
          re.finditer(r"^(\S+) dev (\S+)(?: lladdr \S+)?(?: router)?\s+(\w+)\s*$", out, re.M)]
    rec(ts, "P40", "邻居表（配置派生，旁证；lladdr 不落）", argv, CH_ADB, rc, "—", rows=nb)

    argv, ts, rc, out, err = adb("ip", "route", "get", TARGET)
    via = re.search(r"\bvia (\S+)", out)
    dev = re.search(r"\bdev (\S+)", out)
    gw = via.group(1) if via else None
    rec(ts, "P40", "ip route get（配置派生，旁证，不作门）", argv, CH_ADB, rc, "—",
        via=gw, dev=dev.group(1) if dev else None, raw=out.strip())

    def dping(dst, label):
        argv = ["adb", "-s", serial, "shell", "ping", "-c", "3", "-W", "2", dst]
        if not clean:
            rec(now(), "P40", label, argv, CH_ADB, None, "未执行",
                reason="锁屏下前台应用不是华为桌面或有隧道在起——可能有他人测量在跑，不从设备发包")
            return
        if not dst:
            rec(now(), "P40", label, argv, CH_ADB, None, "未执行", reason="route get 未给出网关")
            return
        ts, rc, out, err = run(argv, 40)
        n = sum(1 for l in out.splitlines() if ("from %s" % dst) in l and "ttl=" in l.lower())
        rec(ts, "P40", label, argv, CH_ADB, rc, "未执行" if rc is None else ("通" if n else "不通"),
            replies_from_target=n, raw=out.strip())

    dping(gw, "ping 网关（第一跳，门）")
    dping(TARGET, "ping 上游目标（门）")

    argv, ts, rc, out, err = adb("dumpsys", "connectivity", timeout=60)
    dm = re.search(r"Active default network:\s*(\S+)", out)
    did = dm.group(1) if dm else None
    fields = {"default_network": did}
    verdict = "未执行"
    if did and did.lower() != "none":
        nai = [l for l in out.splitlines() if "NetworkAgentInfo{" in l and ("network{%s}" % did) in l]
        if nai:
            tr = re.search(r"Transports:\s*([A-Z_|]+)", nai[0])
            cp = re.search(r"Capabilities:\s*([A-Z_&]+)", nai[0])
            caps = cp.group(1).split("&") if cp else []
            fields.update(transport=tr.group(1) if tr else None,
                          VALIDATED="VALIDATED" in caps, INTERNET="INTERNET" in caps,
                          PARTIAL_CONNECTIVITY="PARTIAL_CONNECTIVITY" in caps,
                          CAPTIVE_PORTAL="CAPTIVE_PORTAL" in caps)
            verdict = "通" if "VALIDATED" in caps else "不通"
        else:
            fields["note"] = "默认网络的 NetworkAgentInfo 行未识别"
    elif did:
        verdict = "不通"
        fields["note"] = "无默认网络"
    else:
        fields["note"] = "输出格式未识别"
    out = None  # 原文不留
    rec(ts, "P40", "dumpsys connectivity 默认网络与 VALIDATED（旁证，只落派生字段）",
        ["adb", "-s", serial, "shell", "dumpsys", "connectivity"], CH_ADB + "；原文只在内存解析、不落盘", rc, verdict, **fields)
else:
    for label in ("前台焦点（P40 流程第 1 步）", "ip route get（配置派生，旁证，不作门）", "ping 网关（第一跳，门）",
                  "ping 上游目标（门）", "dumpsys connectivity 默认网络与 VALIDATED（旁证，只落派生字段）"):
        rec(now(), "P40", label, [], CH_ADB, None, "未执行", reason="adb 未见设备")

# ================= 写盘（断言前置） =================
blob = json.dumps(R, ensure_ascii=False, indent=1)
assert not re.search(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b", blob), "读数含 MAC 样式串"
assert not re.search(r"(?i)ssid\s*[:=]", blob), "读数含网络名字段"
os.makedirs(OUTDIR, exist_ok=True)
data = blob.encode("utf-8")
with open(os.path.join(OUTDIR, "readings_run2.json"), "wb") as fh:
    fh.write(data)
print("OK readings=%d outdir=%s" % (len(R), OUTDIR))
for x in R:
    print("%s | %-4s | %s | rc=%s | %s" % (x["ts"], x["layer"], x["item"], x["rc"], x["verdict"]))
