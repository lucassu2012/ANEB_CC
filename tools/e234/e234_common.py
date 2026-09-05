#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2/E3/E4 共用层 —— 时钟基、簇分割、锚点、以及 dry-run 隔离。

出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §3.3（E2/E3/E4 三个实验设计）、
§1.2（锚点 A0/A0'/A2/A3/A4）、§1.6（降级纪律）、§2（通道 A/B/C/D/E）。

本文件**不重新实现 E1 已有的东西**。凡 `tools/e1/e1_analyze.py` 里已有的解析与统计
（`parse_stim_log` / `clock_offset_ns` / `parse_sf_latency` / `parse_framestats` /
`parse_adapter_events` / `parse_screencap_index` / `summarize` / `percentile`）
一律 import 复用，不另造同名函数 —— 同名不同义比不同名更危险（D-315/D-317）。

## 三条从 T14 继承下来的教训，在这里各落成一段代码

1. **订一个没有生产者的标签 = 结构性恒零行**（D-392②）。本层不写死任何与生产者
   共享的字面量：簇分割门限从 `ObsStats.kt` 的 `CLUSTER_GAP_NANOS` **正则取出对账**，
   取不到就抛 —— 不给退路常量（退路常量会让「取不到」变成「取到了一个像样的值」）。
2. **被截断的时戳解析成合法整数**（T14 §2.1②，至今待办）。本层新增
   `plausible_boot_ns()` 量纲守卫：BOOTTIME 纳秒被砍掉几位后仍是合法 int，
   `_int()` 挡不住它。凡跨基相减前，两侧都要过这道量纲检查。
3. **单边的门 / 一次物理事件被复用成多个样本**（T14 §2.1③）。本层的
   `nearest_after()` 一次性交出「配到的那个」与「它是否已被别人配走」，
   由调用方决定是丢弃还是记 dropped —— 不在这里悄悄复用。

## dry-run 隔离（D-270 的 MIXED_CAMPAIGN 教训）

模拟器/合成语料产生的数字**一个都不许进真实语料池**。这里的做法是「可核验」而非「声明」：

- 写盘前先断言（`assert_isolation_before_write`）：dry-run 目录名必须带
  `dryrun`，且必须落在 `evidence/` 下的 dry-run 目录里；不满足直接抛，**在产出
  任何字节之前**（D-306：输出侧的失败发生在已经产出一部分之后，最难收拾）。
- 每个 run 目录第一件事写 `RUN_KIND.json`；判读侧读它，把 `DRY_RUN` 横幅印进
  **每一个输出面**（stdout + markdown + 结果 dict 的 `dry_run` 键，D-303 三面）。
- **前门自己拦得住**：`refuse_calibration_from_dry_run()` —— E4 拿 dry-run 语料
  时**结构上产不出** `T_quiet` 标定值。装置验证与标定是两件事，这一条把它钉死。
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools", "e1"))

import e1_analyze as ea  # noqa: E402

# 状态词沿用全仓那一套，不另立（e1_analyze 已定义，这里只做转出口）。
PASS = ea.PASS
FAIL = ea.FAIL
NOT_EXECUTED = ea.NOT_EXECUTED
BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"

NS_PER_MS = ea.NS_PER_MS
percentile = ea.percentile
summarize = ea.summarize


# ── 与生产者共享的常量：取出来对账，不抄字面量 ────────────────────────────
OBS_STATS_KT = os.path.join(REPO_ROOT, "app", "probe", "src", "main", "java",
                            "com", "aneb", "probe", "adapter", "ObsStats.kt")
_CLUSTER_GAP_RE = re.compile(r"CLUSTER_GAP_NANOS\s*:\s*Long\s*=\s*([0-9_]+)L")


def cluster_gap_nanos(kt_path=OBS_STATS_KT):
    """v3 簇分割门限，**从 `ObsStats.kt` 取**（当前值 400ms，D-52/D-53）。

    这是 D-392② 那一手的原样应用：判读侧与生产侧共享的量，只要有生产者，
    就去生产者那里读，不在这边打字面量。读不到 -> 抛，**没有退路常量** ——
    退路常量会把「读不到」伪装成「读到了个像样的值」，而那正是最难发现的那类错。
    """
    with open(kt_path, "r", encoding="utf-8", errors="replace") as fh:
        m = _CLUSTER_GAP_RE.search(fh.read())
    if not m:
        raise RuntimeError(
            "在 %s 里找不到 CLUSTER_GAP_NANOS —— 生产侧改了名字或换了写法，"
            "判读侧的簇分割门限就此失去出处，拒绝用一个字面量顶上" % kt_path)
    return int(m.group(1).replace("_", ""))


# ── 量纲守卫（T14 §2.1② 的落地）────────────────────────────────────────────
# BOOTTIME 纳秒在任何一台开机超过 1 秒、不足 10 年的设备上都落在这个区间里。
# 被截断的时戳（少几位）会掉到下界之下，被拼接/串行的会冲到上界之上。
MIN_PLAUSIBLE_NS = 1_000_000_000              # 1 s
MAX_PLAUSIBLE_NS = 10 * 365 * 24 * 3600 * 1_000_000_000  # ~10 年


def plausible_boot_ns(v):
    """时戳量纲检查：`int()` 解析成功 != 解析对了。

    T14 实测：三种截断全部解析成合法整数、样本数一个不少、退出码 0、零告警，
    而 `spread` 从 21400 ns 变成 8263 秒，紧跟着一句判词把它命名为「深睡」。
    **非法字节那一路反而是安全的**（`int()` 抛→丢弃）——防线的方向反了。
    """
    return isinstance(v, int) and MIN_PLAUSIBLE_NS <= v <= MAX_PLAUSIBLE_NS


def reject_implausible(rows, key):
    """(kept, dropped) —— 量纲不合的整条丢掉并计数，**不静默**（R-10 + D-336）。"""
    kept = [r for r in rows if plausible_boot_ns(r.get(key))]
    return kept, len(rows) - len(kept)


# ── 簇分割（v3；A0'/A2 的可观测判据）──────────────────────────────────────
def split_clusters(ts_ns, gap_ns):
    """升序时戳 -> [[...], [...]]，相邻间隔 > gap_ns 处断开。

    这是 `ObsStats.kt` 里 v3 簇分割的判读侧同构实现：会话内内容事件按
    `> CLUSTER_GAP_NANOS` 静默分簇，首簇=用户气泡上屏、次簇首=A2（D-52）。
    **门限由调用方传入**（来自 `cluster_gap_nanos()`），本函数不带默认值 ——
    带默认值的门限会在某一天悄悄跟生产侧分叉，而分叉时它不报错。
    """
    out = []
    for t in sorted(ts_ns):
        if out and (t - out[-1][-1]) <= gap_ns:
            out[-1].append(t)
        else:
            out.append([t])
    return out


def v3_anchors(ts_ns, gap_ns):
    """簇分割 -> (a0_prime_ns, a2_ns, clusters)；不足两簇 -> (None, None, clusters)。

    不足两簇是**合法状态**而非错误：DeepSeek 型「思考期播放动画」栈上它恒不闭合
    （§1.4，D-51/D-53）。故返回 None 而不是抛，由调用方记 NOT_EXECUTED + 原因。
    """
    cl = split_clusters(ts_ns, gap_ns)
    if len(cl) < 2:
        return None, None, cl
    return cl[0][0], cl[1][0], cl


# ── 一次物理事件只许配一次（T14 §2.1③）────────────────────────────────────
def nearest_after(t0, candidates, key, max_gap_ns, used=None):
    """t0 之后最近的一个候选。返回 (cand, why)；why ∈ {None, 'none', 'gap', 'reused'}。

    `used` 传一个 set 进来就启用**去重**：同一个候选被第二次配到时返回
    `('reused')` 而不是默默再算一个样本。T14 实测过反面：3 次 commit + 1 帧
    -> `n=3, dropped=0, PASS`，一次物理上屏被算成三个样本（D-335 同形）。
    调用方**必须**显式决定要不要去重 —— 这里不替它决定。
    """
    cand = next((c for c in candidates if c[key] >= t0), None)
    if cand is None:
        return None, "none"
    if (cand[key] - t0) > max_gap_ns:
        return None, "gap"
    if used is not None:
        if cand[key] in used:
            return None, "reused"
        used.add(cand[key])
    return cand, None


# ── logcat 墙钟 <-> 设备 BOOTTIME（E4 的操作者标记要用）───────────────────
# `logcat -v time` 的行首形如 `08-01 07:05:12.776 I/AnebProbe( 5939): ...`。
# 同一条流里，`ADAPTER_EVT` 行**同时**带墙钟前缀与 `t_boot_ns=` 载荷 ——
# 于是墙钟↔BOOTTIME 的映射可以**在设备自己身上量出来**，不必假设、不必 adb 往返。
_WALL_RE = re.compile(
    r"^(?P<mon>\d{2})-(?P<day>\d{2})\s+(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})\.(?P<ms>\d{3})\s")


def wall_ms_of_line(line):
    """logcat 行首墙钟 -> 自当年 1 月 1 日起的毫秒数（无年份，只用于**差值**）。"""
    m = _WALL_RE.match(line)
    if not m:
        return None
    mon, day = int(m.group("mon")), int(m.group("day"))
    # 只做差值，故用「月×31 天」这种粗历法即可：同一次采集不会跨月。
    # 跨月/跨年会让差值为负 —— 由 `fit_wall_to_boot` 的单调性检查当场拒绝。
    days = (mon - 1) * 31 + (day - 1)
    return ((days * 24 + int(m.group("h"))) * 3600
            + int(m.group("m")) * 60 + int(m.group("s"))) * 1000 + int(m.group("ms"))


_EVT_BOOT_RE = re.compile(r"ADAPTER_EVT .*?\bt_boot_ns=(\d+)")


def fit_wall_to_boot(lines):
    """由 `ADAPTER_EVT` 行拟合 wall_ms -> boot_ns 的偏移，并给出**残差**。

    返回 dict：`{status, offset_ns, residual_ms_p50, residual_ms_max, n}`。
    偏移取中位数（不做最小二乘：一条直线的斜率固定为 1e6 ns/ms，两个时钟同源，
    真要有斜率差那是另一个问题，应该被残差抓出来而不是被拟合吸收掉）。

    残差是这条通路的**精度读数**，必须报出来 —— 没有残差的换算只是一句断言。
    """
    pairs = []
    for raw in lines:
        w = wall_ms_of_line(raw)
        if w is None:
            continue
        m = _EVT_BOOT_RE.search(raw)
        if not m:
            continue
        b = int(m.group(1))
        if not plausible_boot_ns(b):
            continue
        pairs.append((w, b))
    if len(pairs) < 2:
        return {"status": NOT_EXECUTED, "n": len(pairs),
                "reason": "带 t_boot_ns 的 ADAPTER_EVT 行 <2，墙钟↔BOOTTIME 无从标定"}
    if any(pairs[i][0] < pairs[i - 1][0] for i in range(1, len(pairs))):
        return {"status": NOT_EXECUTED, "n": len(pairs),
                "reason": "墙钟非单调（采集跨月/跨年或设备改过时区）：差值不可信，拒绝换算"}
    offs = [b - int(w * NS_PER_MS) for w, b in pairs]
    off = percentile(offs, 50)
    res = [abs(o - off) / NS_PER_MS for o in offs]
    return {"status": PASS, "offset_ns": off, "n": len(pairs),
            "residual_ms_p50": percentile(res, 50), "residual_ms_max": max(res)}


def wall_ms_to_boot_ns(wall_ms, fit):
    if fit.get("status") != PASS:
        return None
    return int(wall_ms * NS_PER_MS) + fit["offset_ns"]


# ── 时钟基对齐（E2 要把通道 A 的 BOOTTIME 减到通道 C 的 MONOTONIC 上）─────
def clock_pin(pre_lines, post_lines, frame_ms):
    """两次 E1 刺激源「钉桩」-> BOOTTIME−MONOTONIC 偏移 + 跨会话漂移。

    为什么要两次：`e1_analyze` 的模块注释已经写明，两钟之差 = 开机以来累计深睡，
    **随时间增长**。一次真实会话动辄几分钟，拿会话前的一个偏移糊到会话后，
    误差没有上界。两次钉桩之间的差就是这段时间里的漂移，它是**可测的**。

    判据：漂移 > 1 帧即拒。理由不是审美 —— E2 的判据本身就是「p99 ≤ 1 帧」
    （spec §3.4 G-3），钉桩自己漂过一帧，比出来的那个数就没有意义了。
    帧长由实测刷新率给（spec §3.1：不硬编码 33）。
    """
    pre_cfg, pre_flips = ea.parse_stim_log(pre_lines or [])
    post_cfg, post_flips = ea.parse_stim_log(post_lines or [])
    pre_off, pre_spread, pre_n = ea.clock_offset_ns(ea.usable_flips(pre_flips))
    post_off, post_spread, post_n = ea.clock_offset_ns(ea.usable_flips(post_flips))
    if pre_off is None or post_off is None:
        return {"status": NOT_EXECUTED, "pre_n": pre_n, "post_n": post_n,
                "reason": "前/后钉桩至少一侧无可用 commit 时戳对，跨基比较不可做"}
    drift_ns = post_off - pre_off
    fm = frame_ms if frame_ms is not None else (pre_cfg.get("frame_ms")
                                                or post_cfg.get("frame_ms"))
    if fm is None:
        return {"status": NOT_EXECUTED, "pre_n": pre_n, "post_n": post_n,
                "drift_ns": drift_ns,
                "reason": "无实测帧长：漂移判据没有参照系（spec §3.1 不硬编码 33ms）"}
    if abs(drift_ns) > fm * NS_PER_MS:
        return {"status": NOT_EXECUTED, "pre_n": pre_n, "post_n": post_n,
                "drift_ns": drift_ns, "frame_ms": fm,
                "reason": "钉桩漂移 %.3fms > 1 帧 %.3fms：会话跨度内两钟已分开，"
                          "跨基相减得不出 1 帧量级的结论" % (drift_ns / NS_PER_MS, fm)}
    return {"status": PASS, "offset_ns": (pre_off + post_off) // 2,
            "drift_ns": drift_ns, "frame_ms": fm,
            "pre_n": pre_n, "post_n": post_n,
            "pre_spread_ns": pre_spread, "post_spread_ns": post_spread}


def boot_to_mono_ns(t_boot_ns, pin):
    if pin.get("status") != PASS:
        return None
    return t_boot_ns - pin["offset_ns"]


# ── dry-run 隔离 ──────────────────────────────────────────────────────────
RUN_KIND_FILE = "RUN_KIND.json"
KIND_DRY_RUN = "DRY_RUN_SIMULATED"
KIND_DEVICE = "DEVICE_REAL"
DRY_RUN_DIR_TOKEN = "dryrun"
DRY_RUN_BANNER = ("⚠ DRY_RUN_SIMULATED —— 本页每一个数字都由模拟器生成，"
                  "只证明装置本身是否正确；**不得入任何统计池、不得作标定值**。")


def assert_isolation_before_write(out_dir, kind):
    """写第一个字节**之前**先断言，不是写完再声明（D-306/D-270）。

    dry-run 的产物必须落在名字里带 `dryrun` 的目录下 —— 目录名是操作者、
    `git status`、以及未来任何一次 grep 都看得见的那一面。真实采集反过来
    **不许**落进这样的目录，免得真数据穿上 dry-run 的外衣（两个方向都要拦，
    只拦一个方向的守卫会在另一个方向上给出「看起来没问题」）。
    """
    if kind not in (KIND_DRY_RUN, KIND_DEVICE):
        raise ValueError("未知 run kind: %r（只有 %s / %s）"
                         % (kind, KIND_DRY_RUN, KIND_DEVICE))
    norm = os.path.abspath(out_dir).replace("\\", "/").lower()
    has_token = DRY_RUN_DIR_TOKEN in norm
    if kind == KIND_DRY_RUN and not has_token:
        raise RuntimeError(
            "拒绝写入 %s：dry-run 产物的目录名必须带 `%s`，否则它跟真实采集长得一模一样"
            % (out_dir, DRY_RUN_DIR_TOKEN))
    if kind == KIND_DEVICE and has_token:
        raise RuntimeError(
            "拒绝写入 %s：这是一个 dry-run 目录名，真实采集不许落进来" % out_dir)
    return True


def write_run_kind(out_dir, kind, meta=None):
    """第一个落盘动作。断言在前、`makedirs` 在后 —— 顺序本身是判据的一部分。"""
    assert_isolation_before_write(out_dir, kind)
    os.makedirs(out_dir, exist_ok=True)
    body = {"kind": kind}
    body.update(meta or {})
    with open(os.path.join(out_dir, RUN_KIND_FILE), "w", encoding="utf-8") as fh:
        json.dump(body, fh, ensure_ascii=False, indent=2)
    return body


def read_run_kind(run_dir):
    """-> dict。缺文件返回 `{'kind': None}`：**不猜**它是真是假。

    缺文件是合法的历史状态（E1 那两个归档目录就没有这个文件），故不抛；
    但判读侧对 `kind is None` 与 `kind == DEVICE_REAL` 的处置必须一样保守。
    """
    p = os.path.join(run_dir, RUN_KIND_FILE)
    if not os.path.exists(p):
        return {"kind": None}
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            body = json.load(fh)
    except ValueError:
        return {"kind": None, "reason": "RUN_KIND.json 不是合法 JSON"}
    if not isinstance(body, dict):
        return {"kind": None, "reason": "RUN_KIND.json 不是对象"}
    return body


def is_dry_run(run_dir):
    return read_run_kind(run_dir).get("kind") == KIND_DRY_RUN


def refuse_calibration_from_dry_run(run_kind):
    """标定的前门：dry-run 语料**结构上**产不出标定常量。

    这是「装置验证」与「标定」之间那道墙。E4 的产物是一个会被写进代码、
    被到处引用的常量（§1.5「一旦标定，其值必须是单一来源」）；模拟器数字
    一旦以标定值的形态流出去，往后没有任何一个面能把它认回来 ——
    D-270 的 MIXED_CAMPAIGN 就是这个形状，那次靠的是标记，这次靠的是
    **产不出来**。返回 (allowed, reason)。
    """
    if run_kind == KIND_DRY_RUN:
        return False, ("DRY_RUN_SIMULATED 语料：本工具拒绝产出 T_quiet 标定值。"
                       "dry-run 只回答「判据实现得对不对」，不回答「T_quiet 是多少」")
    return True, None


def banner_lines(run_kind):
    """三面共用的横幅行（markdown / stdout 各自渲染，判定只有这一处）。"""
    if run_kind == KIND_DRY_RUN:
        return [DRY_RUN_BANNER]
    if run_kind is None:
        return ["⚠ 本目录无 `RUN_KIND.json`：来源不明，按真实采集的保守口径处理。"]
    return []


def dedupe_by(rows, key):
    """按 `key` 去重，保留首次出现的顺序。返回 (rows, dropped)。

    为什么需要它：`dumpsys gfxinfo … framestats` 与 `SurfaceFlinger --latency`
    读的都是**环形缓冲**（各约 120/128 帧）。一次真实会话的帧数远超环缓冲深度，
    所以采集侧必须**周期性地反复 dump 并追加**，而相邻两次 dump 必然重叠。
    不去重就是把同一帧数进去两次 —— 一次物理上屏被算成两个样本，
    正是 T14 §2.1③ 记的那个形状，只不过换了一个入口。
    """
    seen, out = set(), []
    for r in rows:
        k = r.get(key)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out, len(rows) - len(out)


def read_lines(run_dir, name):
    p = os.path.join(run_dir, name)
    if not os.path.exists(p):
        return []
    with open(p, "r", encoding="utf-8", errors="replace") as fh:
        return fh.readlines()


def read_text(run_dir, name):
    p = os.path.join(run_dir, name)
    if not os.path.exists(p):
        return ""
    with open(p, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def read_jsonl(run_dir, name):
    out = []
    p = os.path.join(run_dir, name)
    if not os.path.exists(p):
        return out
    with open(p, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def write_report(path, text):
    """输出侧的失败要发生在**产出之前**（D-306：md 先于 csv 写出，操作者拿到半套）。"""
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        raise RuntimeError("落点目录不存在: %s" % d)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def say(text, stream=None):
    """控制台编码不下这行字时也要把话说完（D-265：**报错通道自己最容易死在报错上**）。

    实测触发：Windows 控制台是 GBK，而判定理由里的 `⇒` 不在 GBK 里 ⇒
    `sys.stdout.write` 直接抛 `UnicodeEncodeError`，**整个工具带着一条正确的结论崩掉**。
    崩在打印上比算错更隐蔽：退出码非零、看起来像判定失败，而其实判定早就算完了。

    与 `tools/e1/tests/run_tests.py:_say` 同形。**那一只没有被改成 import 这一只**：
    它是测试跑器、在 `sys.path` 尚未接好时就要能说话，依赖边反向会更脆。
    此处留下互指注释，是为了让下次改编码策略的人知道有两处（D-315 的教训是
    「副本要留依赖边」，而**留不了依赖边时，至少留一条互指**）。
    """
    stream = stream or sys.stdout
    enc = getattr(stream, "encoding", None) or "ascii"
    try:
        text.encode(enc)
    except (UnicodeEncodeError, LookupError):
        out = []
        for ch in text:
            try:
                ch.encode(enc)
                out.append(ch)
            except (UnicodeEncodeError, LookupError):
                out.append("\\u%04x" % ord(ch))
        text = "".join(out)
    stream.write(text)
