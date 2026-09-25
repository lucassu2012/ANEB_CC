# -*- coding: utf-8 -*-
"""2× 分解探针 —— 12 格，**只数不改**（`SNIFF|RECV_ONLY`），零参数。

- 判据：`evidence/c_2x_decompose_20260912/CRITERIA_PREREG.md`
- 判定：`scripts/diag/decompose_2x_verdicts.py`（纯函数，零设备可跑）；
  门：`scripts/tests/test_decompose_2x_verdicts.py`（**条数以 `pytest` 与全域门为准，此处不写数**
  ——写死的跨文件计数保证会过期，且**印在运行时输出里的会落进不可追改的证据**）
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
import locale
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
    verdict_h2, verdict_h4, verdict_identity, verdict_impostor, verdict_n, verdict_s3,
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
MCAST_CIDR = "224.0.0.0/4"                 # §2-5 的多播口径（按 /4 而非 224.*）
# ⚠ **本轮它不在执行路径上**：主 filter 钉死了单个 `ip.DstAddr == 223.5.5.5` ⇒ 多播本就匹配不上；
# 邻居表也不会有多播项（热点 /24 内的地址永远不是 224-239）。
# 故不给它写守卫：**不可达的守卫是一个邀请**（它写着一个错的世界模型）。
# 换目标或放宽 filter 时，§2-5 要在**filter 构造**那侧兑现，不在这里。

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


def _acp():
    """→ 本机 ANSI 代码页名（如 `"cp936"`），**取自 OS 而不是 Python 的 locale**。

    🔴 **`locale.getpreferredencoding(False)` 在 Python UTF-8 模式下返回 `'utf-8'`**
    （本机实测：默认 `'cp936'`、`python -X utf8` `'utf-8'`）⇒ 拿它当「ACP 严格解码」那一路，
    会与 utf-8 那一路**退化成同一条**，HIGH #1 原样复发；`or "cp936"` 救不了（`'utf-8'` 是真值）。
    实测同一批 cp936 字节：默认模式 `sent=3`、`-X utf8` 下 `sent=None`。

    ⚠ **形状（终审 §2-1）：把写死的常量换成一个查询，而那个查询会返回我正要避开的那个常量。**
    它在我跑的环境里确实自适应，**所以测出来是绿的**——只在我没跑过的那个环境里失效。
    ⇒ 追问句：**那个查询在什么环境下会返回我正要避开的那个值？**
    ⚠ 判别量 `sys.flags.utf8_mode` 一直就在手边，上一版一次都没读。

    `GetACP()` 是 **OS 的**代码页：实测 `-X utf8` 下仍返回 936，不随解释器模式变。
    """
    try:
        cp = int(ctypes.windll.kernel32.GetACP())
    except Exception as e:
        raise SystemExit("NOT_EXECUTED：取不到 GetACP（%r）⇒ 无从确定回退编码，拒跑。"
                         "**不退回 locale**——那正是本条要绕开的东西" % (e,))
    name = "cp%d" % cp
    if "utf" in name.lower():
        raise SystemExit("NOT_EXECUTED：GetACP 给出 %r（含 'utf'）⇒ 两条严格解码路会退化成"
                         "同一条，本轮读数不可信，拒跑" % name)
    return name


def _decode(raw):
    """→ `(text, 说明)`。**先严格、后回退，并把走了哪条路说出来。**

    🔴 **原实现写死 `encoding="utf-8"` ＋ `errors="replace"`，而本机 ACP＝cp936**
    （终审 HIGH #1，2026-09-18 实调）：`ping.exe` 的摘要行「已发送 = 20」被解成
    一串 U+FFFD ⇒ `_sent_count` 的正则永不命中 ⇒ **所有 PC 打的格 `T=None`**
    ⇒ `apply_verdicts` 早退 ⇒ **判定块一行都不印，整个提权窗白烧**。
    实测 `ping.exe -n 1 127.0.0.1`：utf-8 解得 **48 个 U+FFFD、正则命中 `None`**；
    cp936 解得 **0 个替换符、命中 `1`**。

    ⚠ **`errors="replace"` 是这条坑的放大器**：它把解码失败变成一串**合法字符**，
    于是失败长得像数据——没有异常、没有空串、没有非零 rc，只有一个安静的 `None`。
    ⇒ 先 `utf-8` 严格，失败再按本机 ACP 严格，两者都不成才 `replace`，
    **且非 utf-8 路一律印出来**（stdout 有副本 ⇒ 这句话会进证据）。

    ⚠ 残余风险显名记：少数字节串在两种编码下**都合法**而语义不同，本函数取先命中的那条
    ⇒ 说明里写清用了哪条，读者可自行复核。
    """
    if not raw:
        return ("", None)
    acp = _acp()          # **不用 locale**：它在 UTF-8 模式下返回 'utf-8'（终审 §2-1）
    try:
        return (raw.decode("utf-8"), None)
    except (UnicodeDecodeError, LookupError):
        pass
    try:
        return (raw.decode(acp), "按 %s 解（utf-8 严格解码失败）" % acp)
    except (UnicodeDecodeError, LookupError):
        t = raw.decode(acp, errors="replace")
        return (t, "🔴 两种严格解码都失败，按 %s replace 解，含 %d 个替换符 "
                   "⇒ **由此得出的读数不可信**" % (acp, t.count("�")))


def run(args, timeout=180):
    """→ `(rc, stdout, stderr)`。**不写死编码**，解码路径见 `_decode`（终审 HIGH #1）。

    ⚠ 仍不得用 `text=True` 而不给 `encoding=`：那会让 stdout 静默变 `None`（本仓害红过一次）。
    这里改成**拿裸字节自己解**，把「用什么编码」从一个写死的常量变成一个**有说明的读数**。
    """
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        out, note = _decode(p.stdout)
        err, _ = _decode(p.stderr)
        if note:
            print("       ⚠ 解码：%s ← %s" % (note, os.path.basename(str(args[0]))))
        return (p.returncode, out, err)
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


PING_RECV = re.compile(r"(\d+)\s*packets transmitted,\s*(\d+)\s*(?:packets\s*)?received", re.I)


def judge_first_hop(rc, out):
    """**第一道门**：设备到目标的 ICMP 往返须**收到 ≥1 个回复** → `(code, 说明)`。

    🔴 **为什么它必须排在 `ip route get` 之前，而且必须是「收到回复」**（2026-09-13 实测）：
    设备曾在**关联仍在、信号 −18dBm、网关 ARP `REACHABLE`** 的情况下，
    ICMP 与 TCP **一个包都过不去**。当时四个前提读数**全部判绿**——
    `ip route get` 报 `ON_HOTSPOT`（路由是**配着的**，不是测出来的）、
    设备 `src` 仍绑着、PC 邻居项是 ICS 钉的 `Permanent`、于是「双侧必须同意」**也一致**。
    🔴 **那道交叉核对的两个读数同源**（都派生自同一份配置）⇒ **它们的一致不构成互证**。
    在那个状态下开跑，五个 FORWARD 格会全读 0，而判据自己警告过那会被读成
    「转发层看不见转发包」——一个漂亮、可复现、完全错误的结论。

    ⚠ **判据是「收到回复」，不是 `rc == 0`、不是路由存在、不是邻居项在。**
    ⚠ 也**不能**改成 ping 热点网关：PC 完全可以合法地不回 ICMP echo（Public profile 默认就不回）
    而转发一切正常 ⇒ 那样的正对照会把好环境判成坏的。**测实验真正依赖的那条路径、用同一个协议。**
    ⚠ 失败文本只印**读数**（「3 发 0 收」），**不印解释**（「设备不在热点上」）——
    2026-09-13 那次，那句解释恰好是错的。
    """
    t = out or ""
    m = PING_RECV.search(t)
    if m is None:
        return ("UNREADABLE",
                "第一跳：ping 摘要行读不到（rc=%s，原样 %r）⇒ NOT_EXECUTED。"
                "**读不到不等于不通，也不等于通**" % (rc, t.strip()[:120]))
    sent, recv = int(m.group(1)), int(m.group(2))
    if recv >= 1:
        return ("OK", "第一跳：%s %d 发 %d 收 ⇒ 往返成立，同协议同路径" % (TARGET, sent, recv))
    return ("NO_REPLY",
            "第一跳不通：%s %d 发 %d 收 ⇒ NOT_EXECUTED。**不加载驱动、不开句柄、不数任何包**"
            % (TARGET, sent, recv))


def derive_idle_seconds(probe_wall_s, probe_n, n_ping, margin_s=3.0):
    """空闲格时长**由实测推出**，不写死 → `(秒, 推导说明)`。

    🔴 原来这里是我拍的一个 `20.0`，而**我从没测过它要压住的那个时长**（终审 K13）：
    `adb shell ping -c 20 -i 1` 的 **wall 实测 29.56 s**（ping 自报 `time=19445ms`，
    差的约 10 s 是 adb 开销），⇒ 目标格窗长约 31.6 s，而 20+2=22 s **短于它**
    ⇒ `noise_policy` 对同层各格必返 `SHORT_WINDOW_NO_PASS`
    ⇒ **FORWARD 那半的底噪全部不可用**，而那正是回答本问题的那半。

    推导：第一跳那次 `ping -c probe_n` 的 wall 里，纯等待是 `probe_n − 1` 秒
    （`-i 1`，最后一个包不等）⇒ **adb 开销 ≈ `probe_wall_s − (probe_n − 1)`**；
    目标格纯等待是 `n_ping − 1` 秒 ⇒ 目标格 wall ≈ 开销 ＋ `n_ping − 1`。
    空闲格取它再加 `margin_s`。

    ⚠ 本函数只是**让默认值落在对的量级**；最终仍由 `noise_policy` 拿**两边的实测窗长**判——
    推导错了它会红，**不是靠这个推导兜底**。
    """
    overhead = max(0.0, float(probe_wall_s) - (probe_n - 1))
    target = overhead + (n_ping - 1)
    secs = target + margin_s
    return (secs, "由实测推出：第一跳 %d 包 wall=%.2fs ⇒ adb 开销≈%.2fs；"
                  "目标格 %d 包 ⇒ wall≈%.2fs；空闲格取 %.2fs（＋%.1fs 余量）"
            % (probe_n, probe_wall_s, overhead, n_ping, target, secs, margin_s))


def filter_neighbors(addrs, hotspot_ip=None):
    """从热点腿邻居表里挑出**可能是设备**的那些。→ `(kept, dropped)`。

    🔴 **实测踩过**：原实现用 `-like '192.168.137*'` ＋ `Select -First 1`，
    挑中的是**广播地址 192.168.137.255** ⇒ §2-3 报「双侧不同意」，
    而两侧其实一致，**是匹配器挑错了**。形状＝「没锚定的匹配器会匹配到超集」
    （那个模式还会命中 PC 自己的 `192.168.137.1`）。
    ⚠ 修法**不能**改成「按设备 src 去查邻居」——那样 §2-3 由构造保证成立，
    这道检查变成同义反复。故：枚举全部、按规则排除、再要求设备 src 在其中。
    ⚠ `dropped` 带理由一起返回并印出——凡报「丢了 N 条」就要能说出丢的是哪些。
    """
    hot = hotspot_ip or HOTSPOT_IP
    pre = hot.rsplit(".", 1)[0].split(".")
    kept, dropped = [], []
    for a in addrs:
        o = a.split(".")
        if len(o) != 4 or not all(x.isdigit() for x in o):
            dropped.append((a, "不是 IPv4 四段形")); continue
        if o[:3] != pre:
            dropped.append((a, "不在热点 /24 内")); continue
        if o[3] == "255":
            dropped.append((a, "广播地址")); continue
        if a == hot:
            dropped.append((a, "PC 自己的热点地址")); continue
        kept.append(a)
    return (kept, dropped)


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
    # ③ 双侧必须同意：枚举热点腿**全部**邻居，排除后要求设备 src 在其中。
    rc, out, _ = ps("(Get-NetNeighbor -InterfaceIndex %s -ErrorAction SilentlyContinue | "
                    "Select-Object -ExpandProperty IPAddress) -join ','" % d["hot_ifidx"])
    d["nb_raw"] = (out or "").strip()
    d["nb_kept"], d["nb_dropped"] = filter_neighbors(
        [x.strip() for x in d["nb_raw"].split(",") if x.strip()])
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
    elif device_src not in (d.get("nb_kept") or []):
        bad.append("③双侧不同意：设备侧 src %r 不在热点腿邻居表（排除后）%r 中；被排除的 %r" % (device_src, d.get("nb_kept"), d.get("nb_dropped")))
    if bad:
        return (False, "NOT_EXECUTED —— " + "；".join(bad))
    return (True, "②接口数 1、③设备 src %s 在邻居表（留 %d 项，排除 %d 项）中、上游腿 ifIndex=%s 地址=%s"
            % (device_src, len(d.get("nb_kept") or []), len(d.get("nb_dropped") or []),
               d["up_ifidx"], d["up_addr"]))
    # ⚠ 排除明细不在这里重复：它已在 preflight 里逐项印过一次（凡报「丢了 N 条」就要能说出是哪些）。


# 收尾标签复用已有纯函数（`2e3ba583` 落地，7 条合成门）——**不重写一份**：
# 同一形状在那里犯过两次，重写一份等于把它请回来。
from forward_layer_probe import driver_rc, teardown               # noqa: E402


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


def cell(d, label, layer, filt, traffic, filt_b=None, opened=None):
    """一格。`filt_b` 非空 ⇒ **同窗两句柄**（§4.3 的分母／分子）。

    `try/finally` 保 `Shutdown`；**`Close` 仅当 `is_alive()` 为假**
    （§1.1-5 与 §6-1 的联立：v2 原写「finally 无条件 Shutdown+Close」与那条打架，
    而 995／6 恰是「读线程还阻塞时句柄被关」的产物）。

    🔴 `opened`（可变 dict）**在句柄 a 开成的那一刻**置 `opened["any"] = True`（终审 V4 §3-4）。
    原实现由调用方在 `cell()` **返回之后**才记 ⇒ 驱动在 `WinDivertOpen` 成功那一刻就已装上，
    而中间隔着 `traffic()` 与宽限——那段里 Ctrl+C 或任何异常都会跳过那次赋值
    ⇒ 收尾拿到 `False` ⇒ 印「**这不是本脚本装的**，不动它」
    ⇒ **驱动留在机器上，而证据里写着本轮没装过它**；下一轮 `pre_state` 读到 0，也不敢碰。
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
    if opened is not None:
        opened["any"] = True          # 驱动此刻已装——记账不能等 cell() 返回（§3-4）
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


def _dump_records(tag, recs):
    """§1.2：**每包一行印进逐字副本**，不只印汇总（终审 X13）。

    🔴 **为什么汇总不够**：§4.1 的 `src` 拆支与「事后查询」都建立在每包记录上，
    而原实现只把 `recs` 喂给 `pkt_summarize()` 后就让它留在内存里
    ⇒ **stdout 里没有数据源** ⇒ 判据写的「按每包日志事后查询」无物可查，
    读者也无从复核汇总数是不是从这些包算出来的。

    ⚠ **此处禁止截断**：截断会静默丢掉恰恰要被查询的那几行。
    条数多本身就是信息（正常一格 ≤ `2T`），故先印条数再印全部。
    """
    if not recs:
        return
    print("       ── %s 每包记录（%d 条，§1.2 逐行；**不截断**）──" % (tag, len(recs)))
    for i, r in enumerate(recs):
        print("       #%03d len=%-4d id=0x%04x ttl=%-3d src=%-15s dst=%-15s ihl=%d "
              "type=%d icmp_id=0x%04x seq=%d"
              % (i, r["recv_len"], r["ip_id"], r["ttl"], r["src"], r["dst"],
                 r["ihl"], r["icmp_type"], r["icmp_id"], r["icmp_seq"]))


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
    _dump_records("句柄 a", c["recs"])
    _dump_records("句柄 b", c["recs_b"])
    return s


# 🔴 `IDLE_SLEEP_S` 常量已退役（终审 K13）：它是我拍的一个数，而**我从没测过它要压住的
# 那个时长**。现由 `derive_idle_seconds()` 从第一跳那次 ping 的实测 wall 推出，
# 并仍由 `noise_policy` 拿两边的实测窗长最终判——推导错了它会红，不靠推导兜底。
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


def no_traffic(secs):
    time.sleep(secs)
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
    # 🔴 **自我标识排在一切门之前**：它零成本，而且是这份证据**能否被归属到字节**的根据。
    # ⚠ 我初版把两道零秒门插在了它之前 ⇒ 提权门一拒跑，那份 stdout 就**说不出跑的是哪些字节**，直接违反 §1.5。
    dirty = print_self_id()

    # 🔴 **两道零秒门，排在一切之前**（终审 §2-10 与 §2-1(b)）。
    # 两条失败都会让整轮**无声报废**，而且都已经发生过：
    #   未提权 ⇒ 12 格全 err=5（stdout_20260918-194103.txt 里 12 次，判定块只剩一行）；
    #   量法在本解释器上不工作 ⇒ 所有 PC 打的格 T=None ⇒ 判定块早退。
    # 两者加起来把「白烧六分钟」压成「立即拒跑」。
    try:
        _admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception as e:
        _admin = None
        print("   ⚠ 提权检查本身失败（%r）" % (e,))
    print("-- 提权门：IsUserAnAdmin() = %s --" % (_admin,))
    if _admin is not True:
        raise SystemExit(
            "NOT_EXECUTED：未提权（IsUserAnAdmin=%s）⇒ 12 格必然全 err=5。\n"
            "  这不是预防性拒跑：stdout_20260918-194103.txt 已经是这么死的一次。" % (_admin,))

    # 量法自证：本解释器上 ping.exe 的摘要行解不出来就立即拒跑。
    # ⚠ 它只看「已发送」，所以 loopback 的 ICMP 被挡也不影响它（本机实测 1 发 0 收，照样取到 1）。
    _, _sp_out, _ = run(["ping.exe", "-n", "1", "127.0.0.1"], timeout=30)
    _sp = _sent_count(_sp_out)
    print("-- 量法自证：ping.exe -n 1 127.0.0.1 ⇒ 取到「已发送」= %s（ACP=%s，utf8_mode=%s）--"
          % (_sp, _acp(), sys.flags.utf8_mode))
    if _sp != 1:
        raise SystemExit(
            "NOT_EXECUTED：_sent_count 在本解释器上取不到发包数（得 %s，期望 1）\n"
            "  ⇒ 所有 PC 打的格 T=None ⇒ 判定块会早退，整窗白烧。\n"
            "  最可能的成因：解释器处于 UTF-8 模式（utf8_mode=%s）或 ACP 与实际输出不符（ACP=%s）。" % (_sp, sys.flags.utf8_mode, _acp()))

    print("主 filter = %s   每格 %d 个 ICMP" % (FILTER_BASE, N_PING))

    # 🔴 **第一道门，排在一切之前**：同协议同路径的往返（见 `judge_first_hop` 的来历）。
    # 它之前那四个读数**全部对「流量是否真的过得去」盲，而且同源** ⇒ 一致不构成互证。
    print("-- 第一跳往返（**排在 ip route get 之前**；判据＝收到回复，不是 rc==0）--")
    _t0 = time.time()
    frc, fout, ferr = run([ADB, "shell", "ping", "-c", "3", "-i", "1", TARGET], timeout=90)
    _wall = time.time() - _t0
    fcode, fwhy = judge_first_hop(frc, fout or ferr)
    print("   %s：%s（wall=%.2fs）" % (fcode, fwhy, _wall))
    if fcode != "OK":
        raise SystemExit(
            "NOT_EXECUTED：%s\n"
            "  ⚠ 这一条**先于**路由／邻居／服务态三项 —— 那三项曾在\n"
            "     「关联在、RSSI −18dBm、网关 ARP REACHABLE 而一个包都不过」时**全部判绿**，\n"
            "     且它们**同源**（都派生自配置而非往返）⇒ 一致不构成互证。\n"
            "  ⇒ 此刻开跑，五个 FORWARD 格会全读 0，而那会被读成「转发层看不见转发包」。" % fwhy)

    idle_s, idle_why = derive_idle_seconds(_wall, 3, N_PING)
    print("   空闲格时长 %.1fs ← %s" % (idle_s, idle_why))

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
    print("   热点腿原样=%r 上游腿原样=%r 邻居原样=%r"
          % (k["hot_raw"], k["up_raw"], k["nb_raw"]))
    print("   邻居筛选：留 %r；排除 %r"
          % (k["nb_kept"], k["nb_dropped"]))
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
    f_taut = "%s and (icmp or not icmp)" % fb   # §1.6 S3-b：**恒真但写法不同**，匹配集合与 fb 相同
    f_noicmp = "ip.DstAddr == %s" % TARGET
    proofs = [compile_selfproof(d, fb, LAYER_NETWORK, True),
              compile_selfproof(d, "true", LAYER_NETWORK, True),
              compile_selfproof(d, "nonsense_field == 1", LAYER_NETWORK, False),
              compile_selfproof(d, f_up, LAYER_NETWORK_FORWARD, True),
              compile_selfproof(d, f_hot, LAYER_NETWORK_FORWARD, True),
              compile_selfproof(d, f_imp, LAYER_NETWORK, True),
              compile_selfproof(d, f_src, LAYER_NETWORK_FORWARD, True),
              compile_selfproof(d, f_taut, LAYER_NETWORK, True)]
    if not all(proofs):
        raise SystemExit("NOT_EXECUTED：编译自证有一行不符预期（见上）⇒ 不数任何包")
    return (d, k, dsrc, pre, dirty, fb, f_up, f_hot, f_src, f_nsrc, f_imp, f_noicmp,
            f_taut, idle_s)


def main():
    """12 格 ＋ 判定 ＋ 收尾。**整段 `try/except BaseException/finally`（含 Ctrl+C）。**

    本轮 `plan` 12 格 ＋ `A-off` 另一格；打 adb 的是 `C1/F1/F2/N1/N2` **5 格**
    （数自 `plan`，2026-09-18）。⚠ 此处原写「8 格打 adb ⇒ 中止机会翻四倍」，
    **那个 8 从来没对过**（拆 S3 之前也是 5），按 5 对 2 是 2.5 倍。
    **结论不变**（`finally` 该要还是该要），**但理由是错的，而理由会被单独抄走独立生效**。

    🔴 收尾必须**真的清**，不只是印标签（终审 X1）：原实现只调 `teardown_labels()` 算两句话，
    而真正做 `sc stop`／`delete` 的 `forward_layer_probe.teardown()` **从未被调用**
    ⇒ 提权轮跑完 WinDivert 仍留在装载态。⚠ 这在我做过的每一轮里都不可见——
    非提权轮一个句柄都没开成 ⇒ 什么都没装 ⇒ 收尾无事可做。
    **这个缺陷只在我还没做过的那种运行里出现。**
    ⚠ 它违反的正是判据自己那条「**每个目标状态必须点名由谁达成，否则只是期望**」。
    """
    d = pre = None
    # 可变 dict：由 cell() 在句柄开成那一刻写入，**异常中途退出也保得住**（§3-4）。
    opened = {"any": False}
    try:
        (d, k, dsrc, pre, dirty, fb, f_up, f_hot, f_src, f_nsrc, f_imp, f_noicmp,
         f_taut, idle_s) = preflight()
        cells = {}
        plan = [
            ("S0 仪器自证", LAYER_NETWORK, "false", lambda: None, None),
            ("S1 空闲底噪(N)", LAYER_NETWORK, fb, lambda: no_traffic(idle_s), None),
            ("S2 空闲底噪(F)", LAYER_NETWORK_FORWARD, fb, lambda: no_traffic(idle_s), None),
            ("S3a 同 filter 两句柄", LAYER_NETWORK, fb, pc_ping, fb),
            ("S3b 恒真子句", LAYER_NETWORK, fb, pc_ping, f_taut),
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
            c = cell(d, label, layer, filt, traf, filt_b, opened=opened)
            c["summary"] = report_cell(c)
            cells[label.split()[0]] = c
            if layer == LAYER_NETWORK_FORWARD:
                k2 = derive_constants()
                ok2, why2 = constants_verdict(k2, dsrc)
                print("   §2 格后复核：%s" % why2)
                if not ok2 or k2.get("hot_ifidx") != k.get("hot_ifidx"):
                    print("   🔴 §2-6 前后不一致 ⇒ 该格 VOID")
                    c["void_constants"] = True
        return cells, pre, opened["any"]
    except BaseException as e:
        print("🔴 中止：%r ⇒ 未跑完的格一律 NOT_EXECUTED，不得据已跑的格外推" % (e,))
        raise
    finally:
        print("-- 收尾（§6-2：只清本轮自己装的那一份）--")
        if pre is None:
            # `pre` 没取到 ⇒ 连「服务是不是本轮装的」都无从判 ⇒ **不动它**，但要说出来。
            rc = driver_rc()
            print("   sc query WinDivert rc=%d；但跑格前的服务态未取到 ⇒ **无从归因，不动它**，"
                  "如实报人处理" % rc)
        else:
            # 🔴 调**真的收尾**，不是只算标签（终审 X1）。`teardown` 内三道闸依次是：
            # rc==1060 已干净 ／ `not opened_any` 不是本轮装的 ／ `pre_state != 1060` 服务先前已在
            # ／ `BeanNetworkTester` 在跑 —— 任一命中即不停不删，只如实报。
            teardown(opened["any"], pre)


def apply_verdicts(cells):
    """把判定层套到读数上。**每条判词都带它自己的前提**，前提取不到就印「取不到」。"""
    # ⚠ 这一行**不许印门的条数**：它会进逐字副本，而证据不可追改
    # ——五份旧 stdout 里的「26 条门」有一份印出来那一刻就已经是假的。
    print("-- 判定（判据 §4，跑前写死；判定逻辑在 decompose_2x_verdicts，门见其同名测试）--")
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
    # 🔴 **FORWARD 层的判词只许用 FORWARD 层自己的前提**（终审 HIGH #2，D-885 禁止跨层外推）。
    # 原先 `cc` 算完只印不用，而 §4.2／§4.3／§4.5 一律拿 A1（NETWORK／PC 侧）的 `T` 与 `code`
    # ⇒ 实调：同一组读数 `code='TWICE'` → `H2_HOLDS`，换 `'DIFFERENT'` → `UNDECIDABLE_IDENTITY`，
    # **结论随传错的那个码反转**。⇒ `cc` 提到条件之外，本层的判词一律喂 `c1["T"]` 与 `cc`。
    cc = None
    if c1 and c1.get("summary") and c1.get("T"):
        cc, cw = verdict_identity(c1["T"], c1["summary"]["n_distinct_keys"],
                                  c1["summary"]["multiplicity_hist"], None)
        print("  §4.1 身份（C1，T=%s）⇒ %s：%s" % (c1["T"], cc, cw))
    else:
        print("  §4.1 身份（C1）：读数或 T 取不到 ⇒ **FORWARD 层没有自己的前提**，"
              "本层各判词一律不可判（**不得借用 A1 的**）")
    f1, f2 = get("F1"), get("F2")
    if f1 and f2 and c1 and None not in (f1.get("count"), f2.get("count"), c1.get("count")):
        # 区间基传 `c1["T"]` 而非 `T`；`verdict_h2` 内另有一道 `T != T_C1 ⇒ VOID_T_FOREIGN`
        # 的守卫兜底 —— 调用点改对与函数拒收**两道都要**，前者会被后人改回去，后者不会。
        h2, hw = verdict_h2(c1.get("T"), f1["count"], f2["count"], c1["count"],
                            f1.get("T"), f2.get("T"), c1.get("T"), cc)
        print("  §4.2 H2（前提取自 C1：T=%s code=%s）⇒ %s：%s" % (c1.get("T"), cc, h2, hw))
    else:
        print("  §4.2 H2：F1／F2／C1 有读数缺席 ⇒ 不可判")
    s3_pass = {}
    for sn in ("S3a", "S3b"):
        s3 = get(sn)
        code_s, why_s = "VOID_NO_T", "%s 格没读数" % sn
        if s3 and s3.get("count") is not None:
            sa = [r["icmp_seq"] for r in s3["recs"]]
            sb = [r["icmp_seq"] for r in s3["recs_b"]]
            code_s, why_s = verdict_s3(s3.get("T"), sa, sb)
        s3_pass[sn] = (code_s == "PASS")
        print("  §1.6 %s ⇒ %s：%s" % (sn, code_s, why_s))
    s3_code = "PASS" if all(s3_pass.values()) else "FAIL"
    print("  §1.6 两支均须过 ⇒ %s（S3a=%s S3b=%s）"
          % (s3_code, s3_pass.get("S3a"), s3_pass.get("S3b")))


    # 每格喂**它自己那一层**的身份判词：A1 用 `code`，C1 用 `cc`（终审 HIGH #2）。
    for nm, own_code in (("A1", code), ("C1", cc)):
        c = get(nm)
        if c and c.get("count_b") is not None:
            ic, iw = verdict_impostor(c["count_b"], c["count"],
                                      s3_code == "PASS",
                                      bool(c.get("same_window")), own_code)
            lo, hi = impostor_band(c["count"]) if c["count"] else (None, None)
            print("  §4.3 impostor（%s，n=%s，带=[%s,%s]）⇒ %s：%s"
                  % (nm, c["count"],
                     "%.3f" % lo if lo is not None else "N/A",
                     "%.3f" % hi if hi is not None else "N/A", ic, iw))
    n1, n2 = get("N1"), get("N2")
    # 🔴 N1／N2 是**设备侧**两格 ⇒ 区间基只能是它们自己的 T，不是 A1 的（终审 HIGH #2）。
    # 两格各跑一次 ping ⇒ 两个 T 必须相等才谈得上共用一个区间基；不等或缺席即不可判。
    if n1 and n2 and None not in (n1.get("count"), n2.get("count")):
        tn1, tn2 = n1.get("T"), n2.get("T")
        same = c1["summary"]["src_same_within_key"] if (c1 and c1.get("summary")) else None
        if tn1 is None or tn2 is None or tn1 != tn2:
            print("  §4.5 N1／N2：T 缺席或两格不等（N1:%s N2:%s）⇒ 不可判"
                  "（**不得借用 A1 的 T 当区间基**）" % (tn1, tn2))
        else:
            nc, nw = verdict_n(tn1, n1["count"], n2["count"], same)
            print("  §4.5 N1／N2（T=%s，取自本层）⇒ %s：%s" % (tn1, nc, nw))
    for sn, tn in (("S1", "A1"), ("S2", "C1")):
        s, t = get(sn), get(tn)
        if s and s.get("count") is not None and t and t.get("window_s"):
            pc, pw = noise_policy(s["count"], s["window_s"] or 0.0, t["window_s"])
            print("  §4.6 %s 底噪 ⇒ %s：%s" % (sn, pc, pw))
    return out


A_OFF_NOT_THIS_ROUND = (
    "a_off_stage() 本轮不执行（终审 V4 §2-7，大脑裁定选 (b)，D-915）。\n"
    "  🔴 不要把它直接接进 __main__——那会原样重建回归 B：teardown 在 main() 的 finally 里，\n"
    "     到这里时驱动已 sc stop、句柄已关、pre_state 已随进程作废，而重开进程又必撞\n"
    "     第一跳门与 ON_HOTSPOT 那道 SystemExit（热点一关必中）。\n"
    "  接线前须先做三件事：(1) 把 teardown 挪出 main() 的 finally，挪到 A-off 之后；\n"
    "  (2) 让驱动句柄 d 与 §2 常量活过 apply_verdicts；(3) 格前格后各印 hotspot_readings 与\n"
    "  device_egress，并按 §3-14 焊进关热点之后的恢复段（第四行必须是往返）。\n"
    "  做完这三件、且根命题（§4.1 身份）的拦窗项已清，再删掉本守卫。")


def a_off_stage(d, cells, identity_code, up_addr, up_ifidx, fb):
    """§5 那个干预。**两道闸，任一不过即不跑**——不跑不是失败，是省掉 PO 一次动手。

    闸一（§5 抬头 ／ §4.4 前提）：`A1` 判 `TWICE`。否则 2× 本就不存在，无物可归因。
    闸二（§5-1..4）：`HOTSPOT_OFF == TRUE`。`FALSE` ⇒ 该格 `NOT_EXECUTED`（需 PO 再动手）；
    `NOT_EXECUTED` ⇒ 量法没活，**两者处置不同，不得并成一句**。

    🔴 **本轮不执行，入口即抛**（终审 V4 §2-7：选 (b)，D-915）。设计原样保留，但**不许被
    天真地接上**：一个完整却无调用的函数是一个邀请（本树「死代码是一个邀请」），后人最自然
    的动作是把它接进 `__main__`，而那恰好重建回归 B。⇒ 让「天真接线」**第一次调用就响亮失败**，
    而不是静默重建那个回归。选 (a) 的条件与步骤见 `A_OFF_NOT_THIS_ROUND`。
    ⚠ 用 `RuntimeError` 而非 `SystemExit`：这是**接线契约**被违反，不是环境拒跑。
    """
    raise RuntimeError(A_OFF_NOT_THIS_ROUND)
    print("-- §5 那个干预（A-off）：先判两道闸 --")   # 以下保留为设计；接线前不可达
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
        # 🔴 原句「跑法：拿本轮 §4.1 的判词调 a_off_stage()」**点名了一个调不出来的函数**
        # （终审 V4 §2-7）——一条不可执行的指令比没有指令更贵。改成如实说明。
        print("⚠ §5 的 A-off **本轮不执行**（终审 V4 §2-7，选 (b)，D-915）⇒ **H4 本轮不判**。\n"
              "  这不是永久放弃 H4：选项 (a)（同一进程内、驱动仍在时阻塞等 PO 关热点）保留为\n"
              "  **根命题（§4.1 身份）拦窗项清掉之后**的后续选项；届时要连同 PO 单子改动一起给 PO 看。")
    finally:
        if _tee is not None:
            print("⇒ 请把上面那个 stdout 副本文件交出去（它是逐字的）；"
                  "**控制台里复制的那份只作旁证**——实测两者曾差一个字。")
            sys.stdout = _tee._s
            _tee.close()
