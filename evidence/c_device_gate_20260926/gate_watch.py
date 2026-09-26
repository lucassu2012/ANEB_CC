# -*- coding: utf-8 -*-
"""PC 热点虚拟卡计数与链路态采样（只读，只在 PC 侧，不碰设备）。

起因：run6 自检两次（13:36、13:42）读到同一张卡的单播计数从 2657 掉到 138，run4（12:37）时是 866052
⇒ 该卡统计在一小时内至少被清零两次。本脚本回答：清零多频繁、伴不伴随链路态翻转，从而判断 run6 的
秒级窗口会不会被清零打穿。

用法（仓根）：python evidence/c_device_gate_20260926/gate_watch.py [秒数，默认 180]
每秒一读 GetIfEntry2（与 gate_diag6.py 同一结构体与自检），记 OutUcastPkts/InUcastPkts/OutNUcastPkts/
OperStatus/MediaConnectState；接口号每次按热点地址现场推出（清零若伴随重建，接口号可能变）。
「清零」＝任一累计计数比上一读小。产物 readings_hotspot_watch_<开始时刻>.json。
"""
import datetime
import importlib.util
import json
import os
import re
import sys
import time

D = "evidence/c_device_gate_20260926"
spec = importlib.util.spec_from_file_location("g6", os.path.join(D, "gate_diag6.py"))
g6 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g6)


def main():
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    t_start = datetime.datetime.now()
    samples, events = [], []
    prev = None
    end = time.monotonic() + secs
    while time.monotonic() < end:
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        idxs = g6.ifindex_by_ip(g6.HOT_IP)
        if len(idxs) != 1:
            s = dict(ts=ts, ifindex_by_ip=idxs)
        else:
            rc, r = g6.uc_read(idxs[0])
            s = dict(ts=ts, ifindex=idxs[0], rc=rc, alias=r.Alias, oper=r.OperStatus, media=r.MediaConnectState,
                     out_ucast=r.OutUcastPkts, in_ucast=r.InUcastPkts, out_nucast=r.OutNUcastPkts)
        if prev is not None:
            ch = [k for k in ("ifindex", "oper", "media", "alias") if s.get(k) != prev.get(k)]
            dn = [k for k in ("out_ucast", "in_ucast", "out_nucast")
                  if k in s and k in prev and s[k] < prev[k]]
            if ch or dn:
                events.append(dict(ts=ts, changed=ch, decreased=dn,
                                   before={k: prev.get(k) for k in ch + dn}, after={k: s.get(k) for k in ch + dn}))
        samples.append(s)
        prev = s
        time.sleep(1)
    rec = dict(started=t_start.isoformat(timespec="seconds"), seconds=secs, n=len(samples),
               sizeof=g6.ctypes.sizeof(g6.MIB_IF_ROW2),
               channel="python ctypes → iphlpapi.GetIfEntry2（结构体同 gate_diag6.py）；接口号每次由 GetIpAddrTable 按热点地址推出",
               events=events, samples=samples)
    blob = json.dumps(rec, ensure_ascii=False, indent=1)
    assert not re.search(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b", blob)
    data = blob.encode("utf-8")
    path = os.path.join(D, "readings_hotspot_watch_%s.json" % t_start.strftime("%H%M%S"))
    with open(path, "wb") as fh:
        fh.write(data)
    with open(path, "rb") as fh:
        assert fh.read() == data
    print("samples=%d events=%d -> %s" % (len(samples), len(events), path))
    for e in events:
        print(json.dumps(e, ensure_ascii=False))


if __name__ == "__main__":
    main()
