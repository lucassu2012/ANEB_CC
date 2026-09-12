# -*- coding: utf-8 -*-
"""WinDivert 两层可见性探针 —— **只数不改**（判据＝evidence/c_forward_layer_probe_20260912/）。

回答一个问题：ICS 转发的设备包，WinDivert **看得见吗**，在**哪一层**看得见。
用它区分 `c_ics_forward_dryrun_20260912` 判定表的第 2 行（层不对）与第 3 行（匹配没中）
——那一轮的对照 B 因信噪比 2.9% 不可判。**本份不靠大流量，靠换观测层**：filter 按 IP
收窄后背景根本进不来。

🔴 **安全关键三条，全部写死在本文件里，不接受任何参数**：

1. **`SNIFF | RECV_ONLY`**：只复制、不摘走。**不带 `SNIFF` 打开句柄会把匹配流量从协议栈上
   摘走，那会真的掐断设备的网络。**
2. **零参数**：filter 字符串、层、时长、目标 IP 全部写死 ⇒ 注入面为零（同 D-840 菜单化的理由）。
3. **加载前比对哈希**：只加载 `B2_SHAPER_VERIFICATION_20260907.md` §1 登记、D-837 逐字节
   核过的那份 WinDivert 2.2.2；**不符即拒跑，不加载**。

⚠ **不用 pydivert**，两条实测理由（见判据 §0）：本机 pydivert 2.1.0 的 `WINDIVERT_ADDRESS`
是 **12 字节**而 WinDivert 2.x 是 **64 字节**（用它收 2.2.2 的包＝让驱动往 12 字节缓冲区写
64 字节，是内存越界不是结果不对）；且它的 `DLL_PATH` 硬编码到自带的**未验**驱动、无覆盖点。
本文件**只数 `Recv` 成功次数，从不解析地址结构**，地址缓冲区给足 128 字节 ⇒ ABI 风险为零。

运行：**管理员** PowerShell 里 `python forward_layer_probe.py`（`WinDivertOpen` 要求管理员）。
"""
import ctypes
import hashlib
import os
import subprocess
import threading
import time

# ---- 全部写死：无参数、无环境变量、无配置文件 ----------------------------------
DLL = r"C:\Program Files\aneb-shaper\BeanNetworkTester\_internal\pydivert\windivert_dll\WinDivert64.dll"
SYS = r"C:\Program Files\aneb-shaper\BeanNetworkTester\_internal\pydivert\windivert_dll\WinDivert64.sys"
SHA_DLL = "c1e060ee19444a259b2162f8af0f3fe8c4428a1c6f694dce20de194ac8d7d9a2"
SHA_SYS = "8da085332782708d8767bcace5327a6ec7283c17cfb85e40b03cd2323a90ddc2"
ADB = r"E:\tools\android-sdk\platform-tools\adb.exe"

TARGET = "223.5.5.5"
FILTER = b"ip.DstAddr == 223.5.5.5"      # 三格共用，共用才使正对照有意义
N_PING = 20                              # 每格 20 个 ICMP
HIT = 5                                  # 判「>0」的门槛（判据 §3，看到计数之前定死）

LAYER_NETWORK = 0
LAYER_NETWORK_FORWARD = 1
FLAG_SNIFF = 0x0001
FLAG_RECV_ONLY = 0x0004
SHUTDOWN_BOTH = 3
INVALID = ctypes.c_void_p(-1).value


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def preflight():
    """哈希不符即拒跑，**不加载任何东西**。"""
    bad = []
    for path, want in ((DLL, SHA_DLL), (SYS, SHA_SYS)):
        if not os.path.isfile(path):
            bad.append("%s 不存在" % path)
            continue
        got = sha256(path)
        print("  %-16s sha256=%s %s" % (os.path.basename(path), got[:16] + "...",
                                        "OK" if got == want else "MISMATCH"))
        if got != want:
            bad.append("%s 哈希不符：期望 %s 实得 %s" % (os.path.basename(path), want, got))
    if bad:
        raise SystemExit("拒绝加载（这正是 D-837 那条穷举比对要防的东西）：\n  " + "\n  ".join(bad))


def load():
    d = ctypes.WinDLL(DLL)
    d.WinDivertOpen.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int16, ctypes.c_uint64]
    d.WinDivertOpen.restype = ctypes.c_void_p
    d.WinDivertRecv.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                                ctypes.POINTER(ctypes.c_uint), ctypes.c_void_p]
    d.WinDivertRecv.restype = ctypes.c_bool
    d.WinDivertShutdown.argtypes = [ctypes.c_void_p, ctypes.c_int]
    d.WinDivertShutdown.restype = ctypes.c_bool
    d.WinDivertClose.argtypes = [ctypes.c_void_p]
    d.WinDivertClose.restype = ctypes.c_bool
    return d


def pc_ping():
    subprocess.run(["ping", "-n", str(N_PING), "-w", "1000", TARGET],
                   capture_output=True, encoding="utf-8", errors="replace", timeout=180)


def dev_ping():
    r = subprocess.run([ADB, "shell", "ping -c %d -W 2 %s" % (N_PING, TARGET)],
                       capture_output=True, encoding="utf-8", errors="replace", timeout=180)
    for line in (r.stdout or "").splitlines():
        if "packets transmitted" in line:
            print("      device: %s" % line.strip())
            return
    print("      device: NO SUMMARY（设备侧没打成 ⇒ 本格记 NOT_EXECUTED，不记 0）")


def cell(d, label, layer, traffic):
    h = d.WinDivertOpen(FILTER, layer, 0, FLAG_SNIFF | FLAG_RECV_ONLY)
    if h is None or h == INVALID:
        err = ctypes.GetLastError()
        hint = {5: "拒绝访问 —— 没有管理员权限", 87: "参数无效 —— filter 写错",
                577: "驱动签名被拒"}.get(err, "")
        print("  [%s] 打开句柄失败 err=%d %s" % (label, err, hint))
        return None
    n = [0]

    def rx():
        pkt = ctypes.create_string_buffer(0xFFFF)
        addr = ctypes.create_string_buffer(128)      # 2.x 需 64；给足且从不解析
        rlen = ctypes.c_uint(0)
        while d.WinDivertRecv(h, pkt, 0xFFFF, ctypes.byref(rlen), addr):
            n[0] += 1

    t = threading.Thread(target=rx, daemon=True)
    t.start()
    traffic()
    time.sleep(2)                                    # 收尾宽限，免得漏计最后几个
    d.WinDivertShutdown(h, SHUTDOWN_BOTH)
    t.join(timeout=5)
    d.WinDivertClose(h)
    print("  [%s] count=%d" % (label, n[0]))
    return n[0]


def verdict(a, b, c):
    if a is None or b is None or c is None:
        return "VOID：有格没跑成（见上），整轮作废"
    if a < HIT:
        return "🔴 VOID：正对照 A=%d < %d ⇒ 量法没活，不得据此判任何事" % (a, HIT)
    if b >= HIT:
        return "第 3 行：转发包在 NETWORK 层可见（B=%d）⇒ 工具看见了却没整（filter/matcher）" % b
    if c >= HIT:
        return "第 2 行：仅在 NETWORK_FORWARD 可见（C=%d）⇒ 工具没开那一层（工具的局限）" % c
    return "两层都不可见（B=%d C=%d）⇒ ICS 路径更深的问题；只报现象，不猜成因" % (b, c)


if __name__ == "__main__":
    print("WinDivert 两层可见性探针 —— 只数不改（SNIFF|RECV_ONLY），零参数")
    print("filter = %s   每格 %d 个 ICMP   判据门槛 >=%d" % (FILTER.decode(), N_PING, HIT))
    print("-- 加载前哈希比对 --")
    preflight()
    d = load()
    print("-- A：NETWORK 层 + PC 打（正对照，>0 才证明这条链是活的）--")
    a = cell(d, "A NETWORK   / PC ", LAYER_NETWORK, pc_ping)
    print("-- B：NETWORK 层 + P40 打 --")
    b = cell(d, "B NETWORK   / P40", LAYER_NETWORK, dev_ping)
    print("-- C：NETWORK_FORWARD 层 + P40 打 --")
    c = cell(d, "C FORWARD   / P40", LAYER_NETWORK_FORWARD, dev_ping)
    print("-- 判定（判据 §3，跑前写死）--")
    print("  " + verdict(a, b, c))
    r = subprocess.run(["sc.exe", "query", "WinDivert"], capture_output=True,
                       encoding="utf-8", errors="replace")
    print("-- 收尾：sc query WinDivert rc=%d（1060 ＝ 已卸载，符合判据 §5）--" % r.returncode)
    print("⚠ 本探针只判**可见性**，不判可整形性：可见 != 可整（整还要能改包并重注入）。")
