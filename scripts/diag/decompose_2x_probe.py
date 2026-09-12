# -*- coding: utf-8 -*-
"""2× 分解探针 —— 12 格，**只数不改**（`SNIFF|RECV_ONLY`），零参数。

- 判据：`evidence/c_2x_decompose_20260912/CRITERIA_PREREG.md`
- 判定：`scripts/diag/decompose_2x_verdicts.py`（纯函数 ＋ 26 条合成门，零设备可跑）
- 身份：`scripts/diag/pkt_identity.py`（八字段解析，8 条合成门含 IHL≠5）

🔴 **本文件只做 IO，不承载任何判词**：自我标识、常量现场推导、开句柄、数包、每包日志、
收尾归因。所有判定都在 `decompose_2x_verdicts` 里，**那里有门**。
理由是复审 v2 第 7 条：判据与仪器之间要有一根线，而「跑前写死」只有在**跑之前能被检验**时
才成立 ⇒ 承载判词的代码必须能在无设备无提权时喂合成读数跑一遍。

本文件内仍有两处**可判真假且会被读成结果**的东西，故也抽成纯函数并配门：
`self_id_lines`（§1.5 的三件与 `WORKTREE_DIRTY`）与 `same_window`（§4.3 的四时刻）。
"""
import ctypes
import hashlib
import io
import os
import re
import subprocess
import sys
import threading
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from decompose_2x_verdicts import (                                    # noqa: E402
    conservation_selfcheck, impostor_band, judge_hotspot_off, noise_policy,
    verdict_h2, verdict_h4, verdict_identity, verdict_impostor, verdict_n,
    zero_reading_ok)
from pkt_identity import parse as pkt_parse, summarize as pkt_summarize   # noqa: E402

ROUND_DIR = "c_2x_decompose_20260912"      # 本轮证据目录（§1.5）；重写换轮时必须同时改它
DLL = r"C:\Program Files\aneb-shaper\BeanNetworkTester\_internal\pydivert\windivert_dll\WinDivert64.dll"
SYS = r"C:\Program Files\aneb-shaper\BeanNetworkTester\_internal\pydivert\windivert_dll\WinDivert64.sys"
SHA_DLL = "c1e060ee19444a259b2162f8af0f3fe8c4428a1c6f694dce20de194ac8d7d9a2"
SHA_SYS = "8da085332782708d8767bcace5327a6ec7283c17cfb85e40b03cd2323a90ddc2"
ADB = r"E:\tools\android-sdk\platform-tools\adb.exe"

TARGET = "223.5.5.5"
FILTER_BASE = "ip.DstAddr == %s and icmp" % TARGET   # §3 共用主 filter（挡住背景 TCP）
N_PING = 20
GRACE_S = 2.0                              # 收尾宽限
HOTSPOT_IP = "192.168.137.1"
MCAST_CIDR = "224.0.0.0/4"                 # §2-5：按 /4 判，不按 224.*

LAYER_NETWORK = 0
LAYER_NETWORK_FORWARD = 1
FLAG_SNIFF = 0x0001
FLAG_RECV_ONLY = 0x0004
SHUTDOWN_BOTH = 3
INVALID = ctypes.c_void_p(-1).value
# 🔴 HIT=5 已退役（判据 v2 第 9 条）：那是**上一轮的活性门槛**，原文自述「给方向不给精度」，
# 被搬来判构成命题就是把一个方向性门槛当成了尺。本轮活性由 S0／S3 自证与正对照格承担。


def self_id_lines(sha, head, porcelain):
    """§1.5 自我标识三件 → `(lines, dirty)`。**第一行由值决定，不写死。**

    🔴 复审 v2 第 7 条读到盘上脚本正是 ` M` 未提交态 ⇒ **那个哈希对应的字节不是正在跑的字节**。
    故 `porcelain` 非空即 `dirty`，且 `WORKTREE_DIRTY` 必须是**第一行**——
    放在后面等于放在没人读的地方。
    """
    dirty = bool((porcelain or "").strip())
    lines = []
    if dirty:
        lines.append("WORKTREE_DIRTY：**提交哈希不代表运行字节**（git status 原样：%r）"
                     % (porcelain.strip(),))
    else:
        lines.append("WORKTREE_CLEAN：该文件无未提交改动 ⇒ 下面那个提交哈希就是运行字节")
    lines.append("  本脚本 SHA256 = %s" % sha)
    lines.append("  git rev-parse HEAD = %s" % head)
    lines.append("  git status --porcelain -- <本文件> = %r" % (porcelain,))
    return (lines, dirty)


def same_window(t_open_a, t_open_b, t_traffic_start, t_grace_end, t_close_a, t_close_b):
    """§4.3「同窗」→ `(ok, 说明)`：两句柄都在 `traffic()` 起点**之前**打开、
    都在收尾宽限**结束之后**关闭。四个时刻各印一次。

    ⚠ 不满足 ⇒ 该读数 `VOID`，**不是「比值偏低」**——那会把仪器问题读成测量结果。
    """
    bad = []
    if t_open_a > t_traffic_start:
        bad.append("句柄 a 开于 traffic 起点之后（+%.3fs）" % (t_open_a - t_traffic_start))
    if t_open_b > t_traffic_start:
        bad.append("句柄 b 开于 traffic 起点之后（+%.3fs）" % (t_open_b - t_traffic_start))
    if t_close_a < t_grace_end:
        bad.append("句柄 a 关于宽限结束之前（-%.3fs）" % (t_grace_end - t_close_a))
    if t_close_b < t_grace_end:
        bad.append("句柄 b 关于宽限结束之前（-%.3fs）" % (t_grace_end - t_close_b))
    if bad:
        return (False, "不同窗：" + "；".join(bad))
    return (True, "同窗：a 开/关 %.3f/%.3f、b 开/关 %.3f/%.3f，traffic 起点 %.3f、宽限止 %.3f"
            % (t_open_a, t_close_a, t_open_b, t_close_b, t_traffic_start, t_grace_end))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 16), b""):
            h.update(blk)
    return h.hexdigest()


def run(args, timeout=180):
    """→ `(rc, stdout, stderr)`。**父侧两件必给**：`encoding` ＋ `errors`
    （不给 `encoding` 时 `text=True` 会让 stdout 静默变 `None`，本仓害红过一次）。"""
    try:
        p = subprocess.run(args, capture_output=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        return (p.returncode, p.stdout or "", p.stderr or "")
    except Exception as e:
        return (None, "", "调用失败：%r" % (e,))


def ps(script, timeout=60):
    """跑一段 PowerShell。⚠ 退出码经 `returncode` 取，**不经 bash `$?`**（8 位截断）。"""
    return run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], timeout)


def judge_device_egress(raw):
    """§5-5 设备侧**三态**：→ `("ON_HOTSPOT"|"OFF_HOTSPOT"|"UNREADABLE", 说明, src)`。

    🔴 **`UNREADABLE` 在两个方向上都判 `NOT_EXECUTED`，绝不能满足前提。**
    v1 的坑正是这里：`judge_egress` 对读不到的输入一律 `ok=False`，
    而 §5 一旦取 `not ok` 作「已关」的前提，**四种读不到全部变成通过**。
    ⇒ 三态而非布尔，且缺席**自己有一个码**。
    """
    t = (raw or "").strip()
    if not t or "device offline" in t or "error" in t.lower():
        return ("UNREADABLE", "设备侧读不到（%r）⇒ NOT_EXECUTED，两个方向都不得满足前提" % (t,), None)
    tok = t.split()
    via = tok[tok.index("via") + 1] if "via" in tok else None
    src = tok[tok.index("src") + 1] if "src" in tok else None
    if "dev" not in tok:
        return ("UNREADABLE", "输出里没有 dev 字段（%r）⇒ 读不到出口接口" % (t,), src)
    net = HOTSPOT_IP.rsplit(".", 1)[0] + "."
    if via == HOTSPOT_IP or (src or "").startswith(net):
        return ("ON_HOTSPOT", "via=%s src=%s ⇒ 在 PC 热点上" % (via, src), src)
    return ("OFF_HOTSPOT", "via=%s src=%s ⇒ 不在 PC 热点上" % (via, src), src)


def device_egress():
    rc, out, err = run([ADB, "shell", "ip", "route", "get", TARGET], timeout=60)
    raw = out.strip() or err.strip()
    code, why, src = judge_device_egress(raw if rc == 0 else "")
    return (code, why, src, raw, rc)


def derive_constants():
    """§2 六条，**由脚本自己做并把读数逐行印进逐字副本**。→ `dict`。

    ⚠ `ifIdx` 与 `ip.SrcAddr` 都不稳（热点腿是移动热点动态创建的虚拟卡）；
    **失败形态完全静默**：四格安静读成 0 而仪器没坏、filter 语法对、收尾码正常。
    """
    d = {}
    # ② 持有热点地址的接口数必须恰好 1
    rc, out, _ = ps("$a=@(Get-NetIPAddress -IPAddress %s -ErrorAction SilentlyContinue); "
                    "'{0}|{1}' -f $a.Count, ($a | Select-Object -First 1).InterfaceIndex"
                    % HOTSPOT_IP)
    d["hot_raw"] = out.strip()
    parts = d["hot_raw"].split("|")
    d["hot_count"] = int(parts[0]) if parts and parts[0].strip().isdigit() else None
    d["hot_ifidx"] = int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else None
    # 上游腿：PC 自身到目标的路由（索引 ＋ 该腿自己的地址，后者是 §5 的 H1 正对照）
    rc, out, _ = ps("$r=Find-NetRoute -RemoteIPAddress %s -ErrorAction SilentlyContinue | "
                    "Select-Object -First 1; '{0}|{1}' -f $r.InterfaceIndex, $r.IPAddress"
                    % TARGET)
    d["up_raw"] = out.strip()
    up = d["up_raw"].split("|")
    d["up_ifidx"] = int(up[0]) if up and up[0].strip().isdigit() else None
    d["up_addr"] = up[1].strip() if len(up) > 1 and up[1].strip() else None
    # ③ 双侧必须同意：PC 侧邻居 IP 等于设备侧 src
    rc, out, _ = ps("(Get-NetNeighbor -InterfaceIndex %s -ErrorAction SilentlyContinue | "
                    "Where-Object {$_.IPAddress -like '%s*'} | "
                    "Select-Object -First 1).IPAddress"
                    % (d["hot_ifidx"], HOTSPOT_IP.rsplit(".", 1)[0]))
    d["neighbor"] = out.strip() or None
    return d


def constants_verdict(d, device_src):
    """§2 的放行判定（六条里可由读数判的那几条）→ `(ok, 逐条说明)`。"""
    bad = []
    if d.get("hot_count") != 1:
        bad.append("②持有 %s 的接口数 = %s（须恰好 1）" % (HOTSPOT_IP, d.get("hot_count")))
    if d.get("up_ifidx") in (None, 0):
        bad.append("上游腿 ifIndex 读不到（%r）" % (d.get("up_raw"),))
    if d.get("up_addr") in (None, ""):
        bad.append("上游腿自身地址读不到 ⇒ §5 的 H1 正对照无从取得")
    if not device_src:
        bad.append("①设备侧 src token 读不到 ⇒ ip.SrcAddr 无从取值")
    elif d.get("neighbor") != device_src:
        bad.append("③双侧不同意：PC 侧邻居 %r != 设备侧 src %r" % (d.get("neighbor"), device_src))
    if bad:
        return (False, "NOT_EXECUTED —— " + "；".join(bad))
    return (True, "②接口数 1、③双侧同意于 %s、上游腿 ifIndex=%s 地址=%s"
            % (device_src, d["up_ifidx"], d["up_addr"]))


# 收尾标签复用已有纯函数（`2e3ba583` 落地，7 条合成门）——**不重写一份**：
# 同一形状在那里犯过两次，重写一份等于把它请回来。
from forward_layer_probe import driver_rc, teardown_labels               # noqa: E402


def load():
    """哈希比对后加载 DLL。`use_last_error=True` 是 §1.1-2 的前提。"""
    for p, want in ((DLL, SHA_DLL), (SYS, SHA_SYS)):
        got = sha256_file(p)
        print("  %-16s sha256=%s... %s"
              % (os.path.basename(p), got[:16], "OK" if got == want else "**不符**"))
        if got != want:
            raise SystemExit("NOT_EXECUTED：%s 的 sha256 与判据钉的不符 ⇒ 不加载、不数任何包" % p)
    d = ctypes.WinDLL(DLL, use_last_error=True)
    d.WinDivertOpen.restype = ctypes.c_void_p
    d.WinDivertOpen.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_short, ctypes.c_uint64]
    d.WinDivertRecv.restype = ctypes.c_bool
    d.WinDivertRecv.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint,
                                ctypes.POINTER(ctypes.c_uint), ctypes.c_char_p]
    d.WinDivertShutdown.restype = ctypes.c_bool
    d.WinDivertShutdown.argtypes = [ctypes.c_void_p, ctypes.c_int]
    d.WinDivertClose.restype = ctypes.c_bool
    d.WinDivertClose.argtypes = [ctypes.c_void_p]
    d.WinDivertHelperCompileFilter.restype = ctypes.c_bool
    d.WinDivertHelperCompileFilter.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
                                               ctypes.c_uint, ctypes.c_char_p,
                                               ctypes.POINTER(ctypes.c_int)]
    return d


def compile_selfproof(d, filt, layer, expect=True):
    """§2-4 编译自证，**自带正负对照**：只看「全 True」分不开「编译器什么都收」。"""
    buf = ctypes.create_string_buffer(1024)
    err = ctypes.create_string_buffer(256)
    pos = ctypes.c_int(0)
    ok = bool(d.WinDivertHelperCompileFilter(filt.encode(), layer, buf, 1024,
                                             err, ctypes.byref(pos)))
    mark = "符合预期" if ok == expect else "**不符预期**"
    print("    compile(%-44s layer=%d) -> %-5s 期望 %-5s %s"
          % (filt[:44], layer, ok, expect, mark))
    return ok == expect


def _reader(d, h, recs, unparsed, errbox):
    """读线程：每包按 §1.2 取八字段。错误码**同线程立刻取**（§1.1-2）。"""
    pkt = ctypes.create_string_buffer(0xFFFF)
    addr = ctypes.create_string_buffer(128)     # 2.x 需 64；给足且**从不解析**（§0-1）
    rlen = ctypes.c_uint(0)
    while d.WinDivertRecv(h, pkt, 0xFFFF, ctypes.byref(rlen), addr):
        r = pkt_parse(pkt.raw, rlen.value)
        if r is None:
            unparsed.append(rlen.value)
        else:
            recs.append(r)
    errbox.append(ctypes.get_last_error())


def _blank_cell(label, layer, filt, filt_b):
    return {"label": label, "layer": layer, "filter": filt, "filter_b": filt_b,
            "count": None, "count_b": None, "recs": [], "recs_b": [],
            "unparsed": [], "unparsed_b": [], "term_err": None, "term_err_b": None,
            "shutting_down": False, "thread_exited": None, "thread_exited_b": None,
            "t": {}, "window_s": None, "same_window": None, "same_window_why": None,
            "T": None}


def cell(d, label, layer, filt, traffic, filt_b=None):
    """一格。`filt_b` 非空 ⇒ **同窗两句柄**（§4.3 的分母／分子）。

    `try/finally` 保 `Shutdown`；**`Close` 仅当 `is_alive()` 为假**
    （§1.1-5 与 §6-1 的联立：v2 原写「finally 无条件 Shutdown+Close」与那条打架，
    而 995／6 恰是「读线程还阻塞时句柄被关」的产物）。
    """
    out = _blank_cell(label, layer, filt, filt_b)
    ha = d.WinDivertOpen(filt.encode(), layer, 0, FLAG_SNIFF | FLAG_RECV_ONLY)
    out["t"]["open_a"] = time.time()
    if ha is None or ha == INVALID:
        e = ctypes.get_last_error()
        hint = {5: "拒绝访问 —— 没有管理员权限", 87: "参数无效 —— filter 写错",
                577: "驱动签名被拒"}.get(e, "")
        print("  [%s] 打开句柄 a 失败 err=%d %s" % (label, e, hint))
        return out
    hb = None
    if filt_b:
        hb = d.WinDivertOpen(filt_b.encode(), layer, 0, FLAG_SNIFF | FLAG_RECV_ONLY)
        out["t"]["open_b"] = time.time()
        if hb is None or hb == INVALID:
            print("  [%s] 打开句柄 b 失败 err=%d ⇒ 本格比值 VOID" % (label, ctypes.get_last_error()))
            hb = None
    ea, eb = [], []
    ta = threading.Thread(target=_reader, args=(d, ha, out["recs"], out["unparsed"], ea),
                          daemon=True)
    tb = None
    ta.start()
    if hb is not None:
        tb = threading.Thread(target=_reader,
                              args=(d, hb, out["recs_b"], out["unparsed_b"], eb), daemon=True)
        tb.start()
    try:
        out["t"]["traffic_start"] = time.time()
        out["T"] = traffic()      # §3：T 取**实测发包数**，不用名义值 20
        time.sleep(GRACE_S)
    finally:
        out["t"]["grace_end"] = time.time()
        out["window_s"] = out["t"]["grace_end"] - out["t"]["traffic_start"]
        out["shutting_down"] = True
        d.WinDivertShutdown(ha, SHUTDOWN_BOTH)
        if hb is not None:
            d.WinDivertShutdown(hb, SHUTDOWN_BOTH)
        ta.join(timeout=5)
        out["thread_exited"] = not ta.is_alive()
        if out["thread_exited"]:
            d.WinDivertClose(ha)
        else:
            print("  [%s] ⚠ 读线程 a 未退出 ⇒ **不 Close**，记 NOT_EXECUTED，交服务级清理" % label)
        out["t"]["close_a"] = time.time()
        if hb is not None:
            tb.join(timeout=5)
            out["thread_exited_b"] = not tb.is_alive()
            if out["thread_exited_b"]:
                d.WinDivertClose(hb)
            else:
                print("  [%s] ⚠ 读线程 b 未退出 ⇒ 不 Close" % label)
            out["t"]["close_b"] = time.time()
    out["count"] = len(out["recs"])
    out["term_err"] = ea[0] if ea else None
    if hb is not None:
        out["count_b"] = len(out["recs_b"])
        out["term_err_b"] = eb[0] if eb else None
        out["same_window"], out["same_window_why"] = same_window(
            out["t"]["open_a"], out["t"]["open_b"], out["t"]["traffic_start"],
            out["t"]["grace_end"], out["t"]["close_a"], out["t"]["close_b"])
    return out


class _Tee(object):
    """stdout 同时写进证据目录的 UTF-8 文件。**不经控制台代码页**。

    实测「PO 粘贴」与脚本末行差一个字 ⇒ **粘贴离 stdout 还有一跳，它不是原文**。
    """

    def __init__(self, stream, path):
        self._s = stream
        self._f = io.open(path, "w", encoding="utf-8", newline="\n")
        self.path = path

    def write(self, s):
        self._s.write(s)
        self._f.write(s)
        return len(s)

    def flush(self):
        self._s.flush()
        self._f.flush()

    def close(self):
        try:
            self._f.close()
        except Exception:
            pass


def _open_tee():
    """→ `(_Tee 或 None, 说明)`。写不进去就如实说，**不因为留不下记录而不跑**。"""
    root = os.path.dirname(os.path.dirname(_HERE))
    d = os.path.join(root, "evidence", ROUND_DIR)
    try:
        if not os.path.isdir(d):
            os.makedirs(d)
        p = os.path.join(d, "stdout_%s.txt" % time.strftime("%Y%m%d-%H%M%S"))
        return _Tee(sys.stdout, p), p
    except Exception as e:
        return None, "写不进证据目录（%r）⇒ 本轮只有控制台输出，如实记" % (e,)


def report_cell(c):
    """印一格的读数 ＋ §1.1-6 全格通则的判定。**并印前提与计数**。"""
    if c["count"] is None:
        print("  [%s] NOT_EXECUTED：句柄没开成" % c["label"])
        return None
    s = pkt_summarize(c["recs"]) if c["recs"] else None
    ok0, why0 = zero_reading_ok(c["count"], c["shutting_down"], c["thread_exited"])
    print("  [%s] count=%d shutting_down=%s term_err=%s 线程已退出=%s 未解析=%d 窗长=%.1fs"
          % (c["label"], c["count"], c["shutting_down"], c["term_err"],
             c["thread_exited"], len(c["unparsed"]), c["window_s"] or 0.0))
    if c["unparsed"]:
        print("       ⚠ 未解析 %d 条（长度 %s）—— **不静默丢**：它们不进身份统计，"
              "但可能与被统计的那些同源" % (len(c["unparsed"]), c["unparsed"][:8]))
    if s is not None:
        print("       去重=%d 重数分布=%s distinct_seq=%d seq=[%s..%s] src 组内一致=%s"
              % (s["n_distinct_keys"], s["multiplicity_hist"], s["distinct_seq"],
                 s["seq_min"], s["seq_max"], s["src_same_within_key"]))
    print("       零读数通则：%s" % why0)
    if c["count_b"] is not None:
        print("       句柄 b：count=%d term_err=%s 线程已退出=%s；%s"
              % (c["count_b"], c["term_err_b"], c["thread_exited_b"], c["same_window_why"]))
    return s


IDLE_SLEEP_S = 20.0        # 空闲格的观测时长（§4.6 要求不短于同层目标格；实际由 noise_policy 判）
REPO = os.path.dirname(os.path.dirname(_HERE))


def print_self_id():
    """§1.5：三件都印，第一行由值决定。→ `dirty`。"""
    me = os.path.abspath(__file__)
    _, head, _ = run(["git", "-C", REPO, "rev-parse", "HEAD"], timeout=60)
    _, por, _ = run(["git", "-C", REPO, "status", "--porcelain", "--", me], timeout=60)
    lines, dirty = self_id_lines(sha256_file(me), head.strip(), por)
    for l in lines:
        print(l)
    return dirty


PING_SENT = re.compile(r"(\d+)\s*(?:packets transmitted|packets tran)", re.I)
PING_SENT_WIN = re.compile(r"(?:Sent|已发送)\s*=\s*(\d+)", re.I)


def _sent_count(text):
    """从 ping 自述里取**实测发包数**。取不到回 None
    ——**缺读数就拒给 T**，不退回名义值。

    ⚠ Windows 侧 ping 的摘要行是**locale 相关**的（中文「已发送 = 20」/
    英文「Sent = 20」）——两种都试，都不中则 None，**并把原文印出来**。
    """
    for rx in (PING_SENT, PING_SENT_WIN):
        m = rx.search(text or "")
        if m:
            return int(m.group(1))
    return None


def pc_ping():
    rc, out, err = run(["ping.exe", "-n", str(N_PING), "-w", "1000", TARGET], timeout=120)
    t = _sent_count(out)
    tail = [l for l in (out or "").splitlines() if ("=" in l and ("Sent" in l or "已发送" in l))]
    print("       PC 侧 ping 自述：%s ⇒ T=%s"
          % (tail[0].strip() if tail else "（无摘要行）", t))
    return t


def dev_ping():
    rc, out, err = run([ADB, "shell", "ping", "-c", str(N_PING), "-i", "1", TARGET], timeout=180)
    tail = [l for l in (out or "").splitlines() if "packets transmitted" in l]
    t = _sent_count(out)
    print("       设备侧 ping 自述：%s ⇒ T=%s"
          % (tail[0].strip() if tail else "（无 summary 行）", t))
    return t


def no_traffic():
    time.sleep(IDLE_SLEEP_S)
    return 0      # 空闲格确实发了 0 个包；T=0 是读数不是缺席


def hotspot_readings(up_addr, up_ifidx):
    """§5-1/2 的六个读数（三条件 ＋ 三正对照），一次 PowerShell 取齐。"""
    script = (
        "$h=@(Get-NetIPAddress -IPAddress %s -ErrorAction SilentlyContinue).Count; "
        "$c=@(Get-NetIPAddress -IPAddress %s -ErrorAction SilentlyContinue).Count; "
        "$s=(Get-Service SharedAccess -ErrorAction SilentlyContinue).Status; "
        "$r=(Find-NetRoute -RemoteIPAddress %s -ErrorAction SilentlyContinue | "
        "Select-Object -First 1).InterfaceIndex; "
        "'{0}|{1}|{2}|{3}' -f $h, $c, $s, $r"
        % (HOTSPOT_IP, up_addr or "0.0.0.0", TARGET))
    rc, out, err = ps(script)
    raw = (out or "").strip()
    print("    §5 读数原样：%r（rc=%s）" % (raw, rc))
    p = raw.split("|")
    num = lambda x: int(x) if x.strip().isdigit() else None
    n_hot = num(p[0]) if len(p) > 0 else None
    ctrl = num(p[1]) if len(p) > 1 else None
    svc = p[2].strip() if len(p) > 2 else ""
    route = num(p[3]) if len(p) > 3 else None
    return judge_hotspot_off(n_hot, ctrl, svc, route, up_ifidx)


def preflight():
    print("2× 分解探针 —— 12 格，只数不改（SNIFF|RECV_ONLY），零参数")
    dirty = print_self_id()
    print("主 filter = %s   每格 %d 个 ICMP   空闲格 %.0fs" % (FILTER_BASE, N_PING, IDLE_SLEEP_S))

    print("-- P2-pre：设备出口三态（§5-5；UNREADABLE 两个方向都不满足前提）--")
    dc, dwhy, dsrc, draw, drc = device_egress()
    print("   %s：%s（原样 %r，rc=%s）" % (dc, dwhy, draw, drc))
    if dc != "ON_HOTSPOT":
        raise SystemExit(
            "NOT_EXECUTED：设备不在 PC 热点上（%s）⇒ 不加载驱动、不开句柄、不数任何包。\n"
            "  此刻开跑 C／F／N 各格**必然为 0**，而那不是「看不见转发包」，\n"
            "  是**根本没有流量经过 PC** —— 一个漂亮、可复现、完全错误的结论。" % dc)

    print("-- §2 常量现场推导（六条，由脚本自己做）--")
    k = derive_constants()
    print("   热点腿原样=%r 上游腿原样=%r 邻居=%r" % (k["hot_raw"], k["up_raw"], k["neighbor"]))
    ok2, why2 = constants_verdict(k, dsrc)
    print("   %s" % why2)
    if not ok2:
        raise SystemExit("NOT_EXECUTED：§2 六条未过 ⇒ 不数任何包")

    print("-- 加载前哈希比对 --")
    pre = driver_rc()
    print("   跑格前 sc query WinDivert rc=%d ⇒ %s"
          % (pre, "1060 服务不在 ⇒ 本轮若开成句柄就是本轮装的" if pre == 1060
             else "服务已在 ⇒ **不是本轮装的**，收尾不得归因、不得停它"))
    d = load()

    print("-- §2-4 编译自证（自带正负对照：只看「全 True」分不开「编译器什么都收」）--")
    fb = FILTER_BASE
    f_up = "%s and ifIdx == %d" % (fb, k["up_ifidx"])
    f_hot = "%s and ifIdx == %d" % (fb, k["hot_ifidx"])
    f_src = "%s and ip.SrcAddr == %s" % (fb, dsrc)
    f_nsrc = "%s and ip.SrcAddr != %s" % (fb, dsrc)
    f_imp = "%s and impostor" % fb
    f_noicmp = "ip.DstAddr == %s" % TARGET
    proofs = [compile_selfproof(d, fb, LAYER_NETWORK, True),
              compile_selfproof(d, "true", LAYER_NETWORK, True),
              compile_selfproof(d, "nonsense_field == 1", LAYER_NETWORK, False),
              compile_selfproof(d, f_up, LAYER_NETWORK_FORWARD, True),
              compile_selfproof(d, f_hot, LAYER_NETWORK_FORWARD, True),
              compile_selfproof(d, f_imp, LAYER_NETWORK, True),
              compile_selfproof(d, f_src, LAYER_NETWORK_FORWARD, True)]
    if not all(proofs):
        raise SystemExit("NOT_EXECUTED：编译自证有一行不符预期（见上）⇒ 不数任何包")
    return (d, k, dsrc, pre, dirty, fb, f_up, f_hot, f_src, f_nsrc, f_imp, f_noicmp)


def main():
    """12 格 ＋ 判定 ＋ 收尾。**整段 `try/except BaseException/finally`（含 Ctrl+C）。**

    本轮 12 格、其中 8 格打 adb ⇒ **中止机会比上一轮翻四倍**，而上一轮已实证
    **句柄关闭不会触发 stop** ⇒ `finally` 无条件调收尾。
    """
    d = pre = None
    opened_any = False
    try:
        (d, k, dsrc, pre, dirty, fb, f_up, f_hot, f_src, f_nsrc, f_imp, f_noicmp) = preflight()
        cells = {}
        plan = [
            ("S0 仪器自证", LAYER_NETWORK, "false", lambda: None, None),
            ("S1 空闲底噪(N)", LAYER_NETWORK, fb, no_traffic, None),
            ("S2 空闲底噪(F)", LAYER_NETWORK_FORWARD, fb, no_traffic, None),
            ("S3 两句柄自证", LAYER_NETWORK, fb, pc_ping, "true"),
            ("A1 复现 A", LAYER_NETWORK, fb, pc_ping, f_imp),
            ("A2 去 and icmp", LAYER_NETWORK, f_noicmp, pc_ping, None),
            ("C1 复现 C", LAYER_NETWORK_FORWARD, fb, dev_ping, f_imp),
            ("F1 上游腿索引", LAYER_NETWORK_FORWARD, f_up, dev_ping, None),
            ("F2 热点腿索引", LAYER_NETWORK_FORWARD, f_hot, dev_ping, None),
            ("N1 src==设备", LAYER_NETWORK_FORWARD, f_src, dev_ping, None),
            ("N2 src!=设备", LAYER_NETWORK_FORWARD, f_nsrc, dev_ping, None),
        ]
        for label, layer, filt, traf, filt_b in plan:
            print("-- %s（layer=%d filter=%s%s）--"
                  % (label, layer, filt, "  ＋第二句柄 " + filt_b if filt_b else ""))
            c = cell(d, label, layer, filt, traf, filt_b)
            opened_any = opened_any or (c["count"] is not None)
            c["summary"] = report_cell(c)
            cells[label.split()[0]] = c
            if layer == LAYER_NETWORK_FORWARD:
                k2 = derive_constants()
                ok2, why2 = constants_verdict(k2, dsrc)
                print("   §2 格后复核：%s" % why2)
                if not ok2 or k2.get("hot_ifidx") != k.get("hot_ifidx"):
                    print("   🔴 §2-6 前后不一致 ⇒ 该格 VOID")
                    c["void_constants"] = True
        return cells, pre, opened_any
    except BaseException as e:
        print("🔴 中止：%r ⇒ 未跑完的格一律 NOT_EXECUTED，不得据已跑的格外推" % (e,))
        raise
    finally:
        if pre is not None:
            print("-- 收尾（§6-2：只清本轮自己装的那一份）--")
            rc = driver_rc()
            state, stop_read = teardown_labels(rc, opened_any, pre)
            print("   sc query WinDivert rc=%d ⇒ %s" % (rc, state))
            print("   句柄关闭是否已触发 stop：%s" % stop_read)


def apply_verdicts(cells):
    """把判定层套到读数上。**每条判词都带它自己的前提**，前提取不到就印「取不到」。"""
    print("-- 判定（判据 §4，跑前写死；判定逻辑在 decompose_2x_verdicts，26 条门）--")
    get = lambda n: cells.get(n)
    a1, a2, c1 = get("A1"), get("A2"), get("C1")
    out = {}
    if a1 is None or a1.get("summary") is None or a1.get("T") is None:
        print("  §4.1 A1：读数或 T 取不到 ⇒ 全部不可判（T 取实测发包数，不退回名义值）")
        return out
    T = a1["T"]
    a2c = a2["count"] if (a2 and a2.get("count") is not None) else None
    code, why = verdict_identity(T, a1["summary"]["n_distinct_keys"],
                                 a1["summary"]["multiplicity_hist"], a2c)
    out["identity"] = code
    print("  §4.1 身份（T=%s，A2 计数=%s）⇒ %s：%s" % (T, a2c, code, why))
    if c1 and c1.get("summary") and c1.get("T"):
        cc, cw = verdict_identity(c1["T"], c1["summary"]["n_distinct_keys"],
                                  c1["summary"]["multiplicity_hist"], None)
        print("  §4.1 身份（C1，T=%s）⇒ %s：%s" % (c1["T"], cc, cw))
    f1, f2 = get("F1"), get("F2")
    if f1 and f2 and c1 and None not in (f1.get("count"), f2.get("count"), c1.get("count")):
        h2, hw = verdict_h2(T, f1["count"], f2["count"], c1["count"],
                            f1.get("T"), f2.get("T"), c1.get("T"), code)
        print("  §4.2 H2 ⇒ %s：%s" % (h2, hw))
    else:
        print("  §4.2 H2：F1／F2／C1 有读数缺席 ⇒ 不可判")
    for nm in ("A1", "C1"):
        c = get(nm)
        if c and c.get("count_b") is not None:
            ic, iw = verdict_impostor(c["count_b"], c["count"],
                                      bool(get("S3") and get("S3").get("count")),
                                      bool(c.get("same_window")), code)
            lo, hi = impostor_band(c["count"]) if c["count"] else (None, None)
            print("  §4.3 impostor（%s，n=%s，带=[%s,%s]）⇒ %s：%s"
                  % (nm, c["count"],
                     "%.3f" % lo if lo is not None else "N/A",
                     "%.3f" % hi if hi is not None else "N/A", ic, iw))
    n1, n2 = get("N1"), get("N2")
    if n1 and n2 and None not in (n1.get("count"), n2.get("count")):
        same = c1["summary"]["src_same_within_key"] if (c1 and c1.get("summary")) else None
        nc, nw = verdict_n(T, n1["count"], n2["count"], same)
        print("  §4.5 N1／N2 ⇒ %s：%s" % (nc, nw))
    for sn, tn in (("S1", "A1"), ("S2", "C1")):
        s, t = get(sn), get(tn)
        if s and s.get("count") is not None and t and t.get("window_s"):
            pc, pw = noise_policy(s["count"], s["window_s"] or 0.0, t["window_s"])
            print("  §4.6 %s 底噪 ⇒ %s：%s" % (sn, pc, pw))
    return out


def a_off_stage(d, cells, identity_code, up_addr, up_ifidx, fb):
    """§5 那个干预。**两道闸，任一不过即不跑**——不跑不是失败，是省掉 PO 一次动手。

    闸一（§5 抬头 ／ §4.4 前提）：`A1` 判 `TWICE`。否则 2× 本就不存在，无物可归因。
    闸二（§5-1..4）：`HOTSPOT_OFF == TRUE`。`FALSE` ⇒ 该格 `NOT_EXECUTED`（需 PO 再动手）；
    `NOT_EXECUTED` ⇒ 量法没活，**两者处置不同，不得并成一句**。
    """
    print("-- §5 那个干预（A-off）：先判两道闸 --")
    if identity_code != "TWICE":
        print("   闸一不过：§4.1 判 %s 而非 TWICE ⇒ **本格不必跑**，H4 本轮不可判。"
              "PO 不必关热点，也不必承担「关了之后 FORWARD 格不得再跑」那条硬顺序"
              % identity_code)
        return None
    state, why = hotspot_readings(up_addr, up_ifidx)
    print("   闸二 HOTSPOT_OFF = %s：%s" % (state, why))
    if state != "TRUE":
        print("   ⇒ 该格 NOT_EXECUTED（%s）"
              % ("热点未关，需 PO 再动手" if state == "FALSE" else "量法没活，需重跑量法"))
        return None
    c = cell(d, "A-off", LAYER_NETWORK, fb, pc_ping, None)
    c["summary"] = report_cell(c)
    if c.get("summary") and c.get("T"):
        hc, hw = verdict_h4(c["T"], c["summary"]["n_distinct_keys"],
                            c["summary"]["multiplicity_hist"], identity_code)
        print("  §4.4 H4 ⇒ %s：%s" % (hc, hw))
    cells["A-off"] = c
    return c


if __name__ == "__main__":
    _tee, _note = _open_tee()
    if _tee is not None:
        sys.stdout = _tee
    print("本轮 stdout 逐字副本（UTF-8，不经控制台代码页）：%s"
          % (_tee.path if _tee is not None else _note))
    try:
        _cells, _pre, _opened = main()
        _v = apply_verdicts(_cells)
        print("⚠ 本探针只判**构成**，不判可整形性：可见 != 可整（整还要能改包并重注入）。")
        print("⚠ §5 的 A-off 未在本入口自动跑 —— 它要 PO 亲手关热点，且必须排在所有 "
              "FORWARD 格之后。跑法：拿本轮 §4.1 的判词调 a_off_stage()。")
    finally:
        if _tee is not None:
            print("⇒ 请把上面那个 stdout 副本文件交出去（它是逐字的）；"
                  "**控制台里复制的那份只作旁证**——实测两者曾差一个字。")
            sys.stdout = _tee._s
            _tee.close()
