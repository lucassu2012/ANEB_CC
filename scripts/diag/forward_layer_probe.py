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
4. 🔴 **P2 出口守卫，前后各查一次**（判据 §0b）：设备必须**经 PC 热点**出网，否则
   **`NOT_EXECUTED`，此前不碰驱动**。没有这一条，热点关着时 B/C **必然为 0**，
   而那不是「两层看不见转发包」，是**根本没有流量经过 PC**——一个漂亮、可复现、
   **完全错误**的结论。跑后再查一次，出口漂移即整轮 `VOID`。
   **这条不靠「记得先开热点」，它焊在脚本里。**

⚠ **不用 pydivert**，两条实测理由（见判据 §0）：本机 pydivert 2.1.0 的 `WINDIVERT_ADDRESS`
是 **12 字节**而 WinDivert 2.x 是 **64 字节**（用它收 2.2.2 的包＝让驱动往 12 字节缓冲区写
64 字节，是内存越界不是结果不对）；且它的 `DLL_PATH` 硬编码到自带的**未验**驱动、无覆盖点。
本文件**只数 `Recv` 成功次数，从不解析地址结构**，地址缓冲区给足 128 字节 ⇒ ABI 风险为零。

运行：**管理员** PowerShell 里 `python forward_layer_probe.py`（`WinDivertOpen` 要求管理员）。
"""
import ctypes
import hashlib
import io
import os
import subprocess
import sys
import threading
import time

# PO 的控制台多半是 cp936：`⚠`/`🔴` 不可编码会让 print **抛异常、脚本以 RC=1 崩掉**（实测）。
# 保留原编码（中文在 cp936 下是可编码的），只把不可编码字符降级，别让输出层决定实验成败。
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

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

# P2（判据 §0b）：出口必须走 PC 热点，否则设备的包**根本不经过 PC**。
# ⚠ **只认 `dev wlan0` 不够** —— 设备连别的 WiFi 时同样是 `wlan0`，那一格**分不开两张网**；
#    必须再认网关或源地址，否则热点关着也能「过」P2，而那正是本守卫要挡的情形。
HOTSPOT_GW = "192.168.137.1"
HOTSPOT_NET = "192.168.137."

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


def judge_egress(raw):
    """**纯函数**：从 `ip route get` 的一行判出口 → `(ok, via, src)`。

    抽成纯函数是为了**能喂实测过的字符串**——守卫本身要有正反两向的对照，
    否则「守卫在不在干活」只能靠现场碰运气（现场的前提会变，实测那天它就变了）。
    由 `scripts/tests/test_forward_probe_egress_guard.py` 用真实观测到的两行钉住。
    """
    tok = raw.split()
    via = tok[tok.index("via") + 1] if "via" in tok else ""
    src = tok[tok.index("src") + 1] if "src" in tok else ""
    ok = ("dev wlan0" in raw) and (via == HOTSPOT_GW or src.startswith(HOTSPOT_NET))
    return ok, via, src


def egress():
    """P2：读设备到 TARGET 的**实际出口** → `(ok, via, src, 原文)`。**只读，不改任何东西。**"""
    r = subprocess.run([ADB, "shell", "ip route get %s" % TARGET],
                       capture_output=True, encoding="utf-8", errors="replace", timeout=60)
    raw = ((r.stdout or "").strip().splitlines() or [""])[0].strip()
    ok, via, src = judge_egress(raw)
    return ok, via, src, raw


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


class _Tee(object):
    """把 stdout 同时写进证据目录里的一个 UTF-8 文件。

    🔴 **为什么这不是「顺手留个日志」**：实测发现「PO 贴来的原文」与**脚本真正印出的字节**
    不同——末行脚本是 `可见 != 可整`，贴来的是 `可见 != 与可整`。差异进在
    **stdout → 控制台 → 复制粘贴**这一跳（控制台编码／IME／选区）。
    ⇒ **「PO 原文」离 stdout 还有一跳，它不是原文。**
    本文件用 **UTF-8 直写**，不经控制台代码页 ⇒ **`⚠` 之类不会被降级成 `?`**，
    这一份才是逐字的；PO 的粘贴自此降为**旁证**。
    今天差别落在一个无害的「与」上，**下次可能落在一个数字上。**
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
    """→ (_Tee 或 None, 说明)。写不进去就如实说，**不因为留不下记录而不跑**。"""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    d = os.path.join(root, "evidence", "c_forward_layer_probe_20260912")
    try:
        if not os.path.isdir(d):
            os.makedirs(d)
        p = os.path.join(d, "stdout_%s.txt" % time.strftime("%Y%m%d-%H%M%S"))
        return _Tee(sys.stdout, p), p
    except Exception as e:
        return None, "写不进证据目录（%s）⇒ 本轮只有控制台输出，如实记" % e


def driver_rc():
    """`sc query WinDivert` 的退出码：1060 ＝ 服务不存在（已卸载）；0 ＝ 服务仍在。"""
    return subprocess.run(["sc.exe", "query", "WinDivert"], capture_output=True,
                          encoding="utf-8", errors="replace").returncode


def teardown(opened_any):
    """判据 §5 的收尾，**标签跟着值走**。

    🔴 **这一行原来是错的，错法留在代码里**：原文把「1060 ＝ 已卸载，符合判据 §5」
    **写死在格式串里**，于是 `rc=0`（服务仍在）也照印「已卸载，符合判据」。
    **一个固定标签焊在变量旁边，读起来就像结果。** 那行输出直接传进了转述、再进了裁定
    （见 `evidence/c_forward_layer_probe_20260912/README.md` §1b）。
    ⇒ **凡把读数与解释印在同一行，解释必须由读数算出来，不许先写死。**

    另：WinDivert「最后一个句柄关掉即自停自删」**本机实测不成立**（至少那一次没发生），
    故收尾要主动清，而且**只清本脚本自己装的那一份**。
    """
    rc = driver_rc()
    print("-- 收尾：sc query WinDivert rc=%d ⇒ %s --"
          % (rc, "1060 服务不存在（已卸载，判据 §5 达成）" if rc == 1060
                 else "服务仍在（判据 §5 FAIL：驱动未卸）"))
    # 「要不要手动 stop」本身是一个读数：它说的是「句柄关闭有没有触发 stop」。
    print("   句柄关闭是否已触发 stop：%s" % ("是（无需手动）" if rc == 1060 else "否（需手动 stop）"))
    if rc == 1060:
        return
    if not opened_any:
        print("   本次一个句柄都没开成 ⇒ **这不是本脚本装的**，不动它，如实报人处理")
        return
    busy = subprocess.run(["tasklist", "/FI", "IMAGENAME eq BeanNetworkTester.exe"],
                          capture_output=True, encoding="utf-8", errors="replace")
    if "BeanNetworkTester" in (busy.stdout or ""):
        print("   ⚠ BeanNetworkTester 正在跑 ⇒ **不停服务**（会掐掉别人的整形），如实报人处理")
        return
    # `sc stop` 才是清理的实质；实测 stop 一执行，WinDivert 就自己把服务条目删掉了
    # ⇒ 「自删」那一半是活的，缺的只是「句柄关闭 → stop」那一半。
    rs = subprocess.run(["sc.exe", "stop", "WinDivert"], capture_output=True,
                        encoding="utf-8", errors="replace")
    print("   sc stop   -> rc=%d" % rs.returncode)
    q = driver_rc()
    print("   stop 后 sc query rc=%d ⇒ %s"
          % (q, "1060 服务条目已消失（WinDivert 自删生效）" if q == 1060 else "服务仍在"))
    if q != 1060:
        # 只有 stop 没清掉时才 delete。⚠ 此处 1060 是「已自删」不是失败——
        # 把一个真成功印成看起来像失败，与「静态括注」同形、方向相反。
        rd = subprocess.run(["sc.exe", "delete", "WinDivert"], capture_output=True,
                            encoding="utf-8", errors="replace")
        print("   sc delete -> rc=%d ⇒ %s"
              % (rd.returncode,
                 "0 已删除" if rd.returncode == 0
                 else ("1060 服务已不存在 ⇒ **已自删，不是失败**" if rd.returncode == 1060
                       else "未预期的 rc，如实记")))
    rc2 = driver_rc()
    print("-- 收尾复核：rc=%d ⇒ %s --"
          % (rc2, "已清干净" if rc2 == 1060 else "仍未清掉，需人处理（判据 §5 FAIL）"))


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
    _tee, _note = _open_tee()
    if _tee is not None:
        sys.stdout = _tee
    print("WinDivert 两层可见性探针 —— 只数不改（SNIFF|RECV_ONLY），零参数")
    print("本轮 stdout 逐字副本（UTF-8，不经控制台代码页）：%s"
          % (_tee.path if _tee is not None else _note))
    print("filter = %s   每格 %d 个 ICMP   判据门槛 >=%d" % (FILTER.decode(), N_PING, HIT))
    print("-- P2-pre：设备出口（判据 §0b；不满足即 NOT_EXECUTED，此前不碰驱动）--")
    ok0, via0, src0, raw0 = egress()
    print("   " + (raw0 or "（ip route get 无输出）"))
    if not ok0:
        raise SystemExit(
            "NOT_EXECUTED：出口不在 PC 热点上 ⇒ 不加载驱动、不开任何句柄、不数任何包。\n"
            "  期望：dev wlan0 且 via %s（或 src %s0/24）\n"
            "  实得：%s\n"
            "  ⇒ 此刻开跑 B/C **必然为 0**，而那不是「两层看不见转发包」，\n"
            "     是**根本没有流量经过 PC** —— 一个漂亮、可复现、完全错误的结论。\n"
            "  修法：先开 PC 移动热点（共享源＝以太网）并把 P40 连上，再跑本脚本。"
            % (HOTSPOT_GW, HOTSPOT_NET, raw0 or "（无输出）"))
    print("-- 加载前哈希比对 --")
    preflight()
    d = load()
    print("-- A：NETWORK 层 + PC 打（正对照，>0 才证明这条链是活的）--")
    a = cell(d, "A NETWORK   / PC ", LAYER_NETWORK, pc_ping)
    print("-- B：NETWORK 层 + P40 打 --")
    b = cell(d, "B NETWORK   / P40", LAYER_NETWORK, dev_ping)
    print("-- C：NETWORK_FORWARD 层 + P40 打 --")
    c = cell(d, "C FORWARD   / P40", LAYER_NETWORK_FORWARD, dev_ping)
    print("-- P2-post：再查一次出口（承 D-880：随动作变化的量要前后各查）--")
    ok1, via1, src1, raw1 = egress()
    print("   " + (raw1 or "（ip route get 无输出）"))
    drift = (not ok1) or (via1, src1) != (via0, src0)
    print("-- 汇总：计数与前提**并印**（读者不必相信我们，自己就能看出前提在不在）--")
    print("   A=%s  B=%s  C=%s" % (a, b, c))
    print("   P2-pre : %s" % raw0)
    print("   P2-post: %s" % raw1)
    print("-- 判定（判据 §3，跑前写死）--")
    if drift:
        print("  🔴 VOID：出口在跑动中变了或已不在热点上 ⇒ 三格计数不可用，不得据此判任何事")
    else:
        print("  " + verdict(a, b, c))
    teardown(opened_any=any(x is not None for x in (a, b, c)))
    print("⚠ 本探针只判**可见性**，不判可整形性：可见 != 可整（整还要能改包并重注入）。")
    if _tee is not None:
        print("⇒ 请把上面那个 stdout 副本文件交出去（它是逐字的）；"
              "**控制台里复制的那份只作旁证**——实测两者曾差一个字。")
        sys.stdout = _tee._s
        _tee.close()
