#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E1 误差判读 —— 把三条通道的观测时刻减去刺激源的真值时刻，按通道出分布。

出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §3.3 实验 E1（判读侧）。
真值侧 = `tools/e1_stimulus`（每次翻转打 `t_req_*` 与 `t_commit_*` 两组时戳）。

## 本脚本量的是什么（三条通道各不相同，刻意不合并成一个数）

- **通道 C（渲染时间线）**：`t_present − t_commit`。两者同为 CLOCK_MONOTONIC，直接相减。
  按大脑 6-1 裁定（呈现口径），SurfaceFlinger 的 actualPresentTime 就是**真值本身**，
  故通道 C 这一列的语义是"提交→上屏"的残余，不是"通道 C 的误差"。
- **通道 A（无障碍事件）**：`t_event − t_present`。**这一列今天量不出来**——见下「通道 A 现状」。
- **通道 B（screencap 帧差）**：**不报时间误差**，只报有效采样周期与检出次数。
  理由见 spec §2.2：B 的采样周期远大于一帧，拿它报亚帧时间是伪精确。

## 时钟基（最要紧的一条）

- `SystemClock.elapsedRealtimeNanos()` = CLOCK_BOOTTIME（含深睡）——无障碍侧用它（D-49）。
- `System.nanoTime()` / SurfaceFlinger / gfxinfo = CLOCK_MONOTONIC（不含深睡）。

两者之差 = 开机以来累计深睡时长，**随时间增长**。刺激源每次翻转把两个时钟一起打出，
本脚本据此换算（`boot_mono_offset_ns`）。这修正了 spec §3.2「E_clock 已有界」的适用范围：
那句话对"只有通道 A"成立，通道 C 一入场就不再成立。

## 通道 A 现状（诚实缺席，不是 0）

`AnebAccessibilityService` 打两种日志：`ADAPTER_EVT`（DEBUG 门控；**〔订正 08-29〕已扩到
click 与内容变化两类事件、均带 `t_boot_ns`**——`AnebAccessibilityService:194` 注释点名、
`3d31512`/T27 补账；本段下方 §现状/提案是订正前旧态，以本句与文末 `parse_adapter_events`
docstring 为准）与 `ADAPTER_OBS`（**5 秒节流的聚合**：events / first_delta_ms / cadence_p50_ms）。

本脚本对此的处理：
1. 若日志里存在带 `t_boot_ns=` 的 `ADAPTER_EVT` 行（=下述提案落地后的形态），照常判读；
2. 否则通道 A 一律报 `NOT_EXECUTED` + 原因，**绝不用 `ADAPTER_OBS` 的聚合值折算**；
3. 但会跑一条今天就能跑的弱检查：`cadence_p50_ms` 应约等于刺激源的 `interval_ms`
   ——它证不了偏移，只证得了"通道 A 确实看见了这串翻转"。

提案（需大脑排期，属 `:probe` 代码面，与设备批的构建对应关系有冲突，故本轮不动）：
把既有 `ADAPTER_EVT` 扩到内容变化事件并加一个字段——
`ADAPTER_EVT type=content cls=<cls> txt_len=<n> pkg=<pkg> t_boot_ns=<ns>`。
一行、additive、DEBUG 门控，不改任何既有字段。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts"))

# 分位数复用仓内单一实现（nearest-rank），不另造同名函数：同名不同义比不同名更危险
# （D-315/D-317 的原样形状）。
from campaign_common import percentile  # noqa: E402

NS_PER_MS = 1_000_000.0

# ── 状态词（全仓统一，不另立）──────────────────────────────────────────────
PASS = "PASS"
FAIL = "FAIL"
NOT_EXECUTED = "NOT_EXECUTED"

# ── 「1 帧」取值来源（L-1，2026-08-02；此前只是 analyze() 里一行注释，
#    D-413 run3 第一次暴露它会与刺激源自报的 refresh_hz 打架后固化为显式判据）──
# P40 是 LTPO 变刷屏（90Hz 满刷 / 静态内容可能降频合成）。SurfaceFlinger 实测的
# 合成周期与 App 侧 `Display.getRefreshRate()` 的名义值在这类屏幕上**允许不同**
# ——静态画面时 SF 完全可能真的在按更低频率合成，那不是 bug，是省电。
# 本工具选哪个当「1 帧」直接决定通道 C 系「t_commit→t_present 实测总量 vs 1 帧」
# 的 PASS/FAIL（D-417/D-418 起：这**不等于** G-2 本义，见 gate_verdict()/
# g2_true_meaning() 的 docstring——但仍是同一个「1 帧取多少」的口径问题），
# 这条规则因此必须是显式、可审计的字段，不能只是渲染文案里的一句话。
FRAME_MS_SRC_MEASURED = "surfaceflinger_measured"   # 优先：来自 sf_latency.txt 首行周期
FRAME_MS_SRC_STIMULUS = "stimulus_self_report"      # 回退：sf_latency 缺失时，用刺激源 CFG 的 refresh_hz
# 两个候选值差多少才值得渲染分歧提示——远小于任何有意义的帧周期差（run3 的
# 90Hz/60Hz 之差 ≈5.6ms），只用来滤掉浮点表示误差级别的假分歧，不是精度判据。
FRAME_MS_DISAGREEMENT_EPSILON_MS = 0.05

# ── 刺激源日志 ────────────────────────────────────────────────────────────
# 锚定方式：先要求行里出现标签 `E1_STIM`，再宽松地跳到标记词。
#
# 为什么不写 `E1_STIM CFG`：`logcat -s E1_STIM:I` 打出的真实行是
#   `08-01 07:05:12.776 I/E1_STIM ( 5939): CFG interval_ms=...`
# ——标签只在前缀里出现一次，消息体**不重复标签**。首版正则写死了
# "E1_STIM CFG" 相邻，离线夹具自造成那个样子于是全绿，而首次模拟器 dry-run
# 一行都没解析出来。夹具自洽 ≠ 与生产者真写出的形状对过账（D-309 原样形状）。
_CFG_RE = re.compile(r"E1_STIM.*?\bCFG\s+(?P<kv>interval_ms=\S.*)$")
_FLIP_RE = re.compile(r"E1_STIM.*?\bFLIP\s+(?P<kv>seq=\S.*)$")
_COMMIT_RE = re.compile(r"E1_STIM.*?\bCOMMIT\s+(?P<kv>seq=\S.*)$")
_KV_RE = re.compile(r"(\w+)=([^\s]+)")


def _kv(text):
    """`a=1 b=x` -> {'a': '1', 'b': 'x'}. 值一律留字符串，转型由调用方按字段决定。"""
    return dict(_KV_RE.findall(text))


def _int(d, key):
    """取整数字段；缺失或不可解析 -> None（R-10：绝不折 0）。"""
    v = d.get(key)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _float(d, key):
    v = d.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_stim_log(lines):
    """刺激源 logcat -> (cfg, {seq: flip})。

    flip 键：color / warmup(bool) / t_req_boot_ns / t_req_mono_ns /
             t_commit_boot_ns / t_commit_mono_ns（后两者可能缺 = 该帧没提交回调）。
    重复 seq（App 被重启过）时**后者覆盖前者**并计入 cfg['duplicate_seq']——
    静默覆盖会让分母悄悄变小，故计数留痕。
    """
    cfg, flips, dup, cfg_blocks = {}, {}, 0, 0
    for raw in lines:
        line = raw.rstrip("\n")
        m = _CFG_RE.search(line)
        if m:
            cfg_blocks += 1
            d = _kv(m.group("kv"))
            cfg = {
                "interval_ms": _int(d, "interval_ms"),
                "count": _int(d, "count"),
                "roi_px": _int(d, "roi_px"),
                "warmup": _int(d, "warmup"),
                "refresh_hz": _float(d, "refresh_hz"),
                "frame_ms": _float(d, "frame_ms"),
                "boot_mono_offset_ns": _int(d, "boot_mono_offset_ns"),
                "screen_px": d.get("screen_px"),
            }
            continue
        m = _FLIP_RE.search(line)
        if m:
            d = _kv(m.group("kv"))
            seq = _int(d, "seq")
            if seq is None:
                continue
            if seq in flips:
                dup += 1
            flips[seq] = {
                "seq": seq,
                "color": d.get("color"),
                "warmup": d.get("warmup") == "true",
                "t_req_boot_ns": _int(d, "t_req_boot_ns"),
                "t_req_mono_ns": _int(d, "t_req_mono_ns"),
                "t_commit_boot_ns": None,
                "t_commit_mono_ns": None,
            }
            continue
        m = _COMMIT_RE.search(line)
        if m:
            d = _kv(m.group("kv"))
            seq = _int(d, "seq")
            if seq is None or seq not in flips:
                continue  # 孤儿 COMMIT（FLIP 行被 logcat 环缓冲冲掉）——不凭空造 flip
            flips[seq]["t_commit_boot_ns"] = _int(d, "t_commit_boot_ns")
            flips[seq]["t_commit_mono_ns"] = _int(d, "t_commit_mono_ns")
    if dup:
        cfg["duplicate_seq"] = dup
    if cfg_blocks > 1:
        # 表头 cfg 只反映**最后一个** CFG 块（App 被重启过，前面的块被整段覆盖）——
        # 多数可用翻转很可能来自更早的块，读表头 interval_ms 去算「期望节奏」会算错
        # （D-409 K-2：一次真机窗里 48 个可用翻转，约 43 个来自被覆盖的早期块）。
        cfg["cfg_blocks"] = cfg_blocks
    return cfg, flips


def usable_flips(flips, drop_warmup=True):
    """可用于统计的翻转：有 commit 时戳，且（默认）不是预热轮。

    丢弃预热轮是本仓既有纪律（D-366），此处沿用同一口径而不是另起一套。
    """
    out = []
    for seq in sorted(flips):
        f = flips[seq]
        if drop_warmup and f.get("warmup"):
            continue
        if f.get("t_commit_mono_ns") is None or f.get("t_commit_boot_ns") is None:
            continue
        out.append(f)
    return out


def clock_offset_ns(flips):
    """由刺激源同帧打出的两个时钟求 BOOTTIME − MONOTONIC 偏移。

    返回 (median_offset_ns, spread_ns, n)。spread = max−min：它**不是噪声**，
    而是"这段时间里设备深睡了多久"的直接读数。spread 明显大于 0 就意味着
    跨基比较必须逐条换算，不能拿一个常数偏移糊过去。
    """
    offs = [f["t_commit_boot_ns"] - f["t_commit_mono_ns"]
            for f in flips
            if f.get("t_commit_boot_ns") is not None and f.get("t_commit_mono_ns") is not None]
    if not offs:
        return None, None, 0
    return percentile(offs, 50), max(offs) - min(offs), len(offs)


# ── 通道 A：无障碍事件 ─────────────────────────────────────────────────────
_ADAPTER_EVT_RE = re.compile(r"ADAPTER_EVT (?P<kv>.+)$")
_ADAPTER_OBS_RE = re.compile(r"ADAPTER_OBS (?P<kv>.+)$")


def parse_adapter_events(lines):
    """`ADAPTER_EVT ... t_boot_ns=<ns>` -> [{'t_boot_ns','type','pkg'}]（按时戳升序）。

    只收**带 t_boot_ns 的行**，不按 `type` 区分——click 与 content 两类事件
    2026-08-02 起均已携带该字段（`3d31512`，T27 补账）。**不假设一定有该字段**：
    没有它的行（历史数据、或未来新增的事件类型忘了补）被如实忽略——忽略比
    "用行到达顺序编个时戳"安全得多。
    """
    out = []
    for raw in lines:
        m = _ADAPTER_EVT_RE.search(raw)
        if not m:
            continue
        d = _kv(m.group("kv"))
        t = _int(d, "t_boot_ns")
        if t is None:
            continue
        out.append({"t_boot_ns": t, "type": d.get("type"), "pkg": d.get("pkg")})
    out.sort(key=lambda r: r["t_boot_ns"])
    return out


def parse_adapter_obs(lines):
    """`ADAPTER_OBS ...` 聚合行 -> [{'pkg','mode','events','cadence_p50_ms','first_delta_ms'}]。

    仅用于「通道 A 是否看见了这串翻转」的弱检查；**不得**据此折算任何时间误差。
    """
    out = []
    for raw in lines:
        m = _ADAPTER_OBS_RE.search(raw)
        if not m:
            continue
        d = _kv(m.group("kv"))
        out.append({
            "pkg": d.get("pkg"),
            "mode": d.get("mode"),
            "events": _int(d, "events"),
            "cadence_p50_ms": _float(d, "cadence_p50_ms"),
            "first_delta_ms": _float(d, "first_delta_ms"),
        })
    return out


# ── 通道 C：渲染时间线 ─────────────────────────────────────────────────────
def _drop_trailing_blank(fields):
    """`a,b,c,` -> ['a','b','c']。真实 framestats **每一行末尾都有一个逗号**。

    出处是归档语料自己：`evidence/e1/20260801-170127/framestats.txt` 的表头逐字以
    `…,CommandSubmissionCompleted,` 结尾。首版不剥这个空字段，于是**任何一份真实
    framestats 都解析出 0 行**——带尾逗号的数据行 `int("")` 抛而被 `continue` 丢掉，
    不带尾逗号的又与表头宽度对不上，两条路都是 0。它一直没被发现有两个原因：
    模拟器上 `PROFILEDATA` 块本来就是空的（T7 记的通道 C `BLOCKED_EXTERNAL`），
    而 `framestats_rows` 是**只写不读**字段（T14 §4.2 已在册），没有任何一个面
    会因为它恒等于 0 而变红。D-309 的原样形状：夹具自造了一个真实生产者不写的形状。
    """
    out = [f.strip() for f in fields]
    while out and out[-1] == "":
        out.pop()
    return out


def parse_framestats(text):
    """`dumpsys gfxinfo <pkg> framestats` -> [dict]，键取自表头。

    **按表头名取列、不按下标**：framestats 的列集随 API 级别增删过（GpuCompleted
    等是后加的）。按下标读会在换设备时静默错位——错位后的数还是个像样的数字，
    这正是最难发现的那类错。
    """
    rows, header = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if "IntendedVsync" in line and "," in line:
            header = _drop_trailing_blank(line.split(","))
            continue
        if header is None or "," not in line:
            continue
        parts = _drop_trailing_blank(line.split(","))
        if len(parts) != len(header):
            continue  # 截断行/说明行，不猜
        try:
            vals = [int(p) for p in parts]
        except ValueError:
            continue
        rows.append(dict(zip(header, vals)))
    return rows


def parse_sf_latency(text):
    """`dumpsys SurfaceFlinger --latency <layer>` -> (refresh_period_ns, [frames])。

    格式：首行=刷新周期(ns)；其后每行三个数
    (desiredPresentTime, actualPresentTime, frameReadyTime)，单位 ns，CLOCK_MONOTONIC。
    待定帧以 0 或 INT64_MAX 占位 —— 一律剔除，**绝不当成 0 时刻参与统计**（R-10）。
    """
    pending = (1 << 63) - 1
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return None, []
    try:
        period = int(lines[0].split()[0])
    except (ValueError, IndexError):
        return None, []
    frames = []
    for line in lines[1:]:
        parts = line.replace("\t", " ").split()
        if len(parts) < 3:
            continue
        try:
            desired, actual, ready = (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            continue
        if actual in (0, pending) or ready in (0, pending):
            continue
        frames.append({"desired_ns": desired, "actual_ns": actual, "ready_ns": ready})
    frames.sort(key=lambda f: f["actual_ns"])
    return period, frames


def dedup_sf_latency_frames(frames):
    """`parse_sf_latency` 的输出 -> 按 `actual_ns` 去重排序后的同结构列表。

    为什么要去重（T40；与 `dedup_framestats_present_times` 同一根因，D-416 先例）：
    `_dump_channel_c`（e234_collect.py）周期性追加 dump，`--latency` 的环缓冲每次
    dump 都读一遍**当前**全部驻留帧——两次 dump 之间若帧产出速度跟不上
    `--framestats-period-s`，相邻 dump 就会大量重叠。DW-20260803-03 实测：15 段
    dump 拼出 1178 行原始记录，`actual_ns` 唯一值只有 164 个（86% 是重复行）。
    两个不同物理帧撞到同一纳秒是天文数字概率，故按 `actual_ns` **精确相等**去重
    是安全的（不是近似匹配，没有引入容差判据）。

    **对 `align_present` 的判定结果无影响，但仍然值得做**：`align_present` 对每次
    翻转只取"commit 之后最近一帧"（`next()` 单一匹配），重复行的 `actual_ns` 值
    相同，不会改变匹配到的时刻本身——DW-20260803-03 实测去重前后 `n`/`dropped`/
    `p50`/`p90`/`p99` 逐位相同。去重要解决的是**另一件事**：不去重时"原始行数"
    会被读成"捕捉到的帧数"，1178 行读起来像是覆盖密度很高，实际只有 164 个
    不同的物理帧——这是一处会误导读者的计数，不是一处会算错判据的 bug。
    """
    seen, out = set(), []
    for f in frames:
        v = f.get("actual_ns")
        if v is None or v in seen:
            continue
        seen.add(v)
        out.append(f)
    out.sort(key=lambda f: f["actual_ns"])
    return out


# ── L-2（2026-08-02）：framestats PROFILEDATA 接入判读链路，与 --latency 交叉验证 ──
# 目标不是取代 --latency，是给 W-2「通道 C 在 P40 可用」找第二个独立数据源
# （D-413 订正②钉死：run3 的 FAIL 判定此前完全来自 --latency，framestats 的 23 行
# 真实数据一直是只写不读的计数字段）。
#
# 取哪一列当"present"：`DisplayPresentTime`（最贴近字面意义）在本设备/API 级别上
# 实测**恒为 0**（未实现或需要额外的 vsync-id 支持，本文件不猜测成因），不可用。
# `SwapBuffersCompleted`（缓冲区交换完成，帧被移交给合成管线的那一刻）是下一个
# 最接近"上屏"语义的列，取它。`FrameCompleted`（UI 线程渲染工作标记完成）是
# 另一个很接近的候选，但语义更偏"渲染完成"而非"提交给显示"，不用它——
# 两个候选选一个就够，混用两个含义相近但不同的列反而制造第二层歧义。
PRESENT_TIME_KEY_FRAMESTATS = "SwapBuffersCompleted"


def dedup_framestats_present_times(rows, key=PRESENT_TIME_KEY_FRAMESTATS):
    """framestats 行 -> 去重排序后的 `[{"actual_ns": ...}]`（`align_present` 要的形状）。

    为什么要去重：`_dump_channel_c`（e234_collect.py）周期性追加 dump，相邻两次
    必然重叠——同一帧的 `SwapBuffersCompleted` 纳秒级时间戳会在多个 dump 里原样
    重复出现。两个不同帧撞到同一纳秒是天文数字概率，故按这一列**精确相等**去重
    是安全的（不是近似匹配，没有引入容差判据）。不去重会让同一帧被计入多次，
    直接扭曲下游的分位数。

    某行缺这一列，或值为 0（该行这个字段本就没测到，R-10：不当真值用）时跳过。
    """
    seen, out = set(), []
    for r in rows:
        v = r.get(key)
        if not v or v in seen:      # v 为 None/0 一律跳过，不当真值用（R-10）
            continue
        seen.add(v)
        out.append({"actual_ns": v})
    out.sort(key=lambda f: f["actual_ns"])
    return out


def cross_check_channel_c(latency_summary, framestats_summary, frame_ms):
    """`--latency` 与 `framestats` 两条支路对同一批翻转的分布对不对得上。

    **只有一条支路有数据时不虚构结论**——这条规则本身要造反例证明，不能靠推理
    （D-322 一贯要求）。判据：两个 p50 之差是否在 1 帧以内。用 1 帧当容差不是
    随手取的：这是本工具自己对"1 帧"的定义，用它做两条支路的一致性容差，
    跟用它判 M3 门是同一把尺子，不另立一个新常量。

    差距超过容差时**不预设哪边对**——两条支路的锚点本就是渲染管线里两个不同
    阶段（`--latency` 是 SurfaceFlinger 的合成 actual，`framestats` 的
    `SwapBuffersCompleted` 是应用侧缓冲区交换完成），几毫秒的系统性差异是这两个
    阶段之间本就存在的真实间隔，不必然是任一支路测错。
    """
    if latency_summary.get("status") != PASS or framestats_summary.get("status") != PASS:
        return {"status": NOT_EXECUTED,
               "reason": "至少一条支路无可用样本，跨支路比较不可做"}
    d = abs(latency_summary["p50_ms"] - framestats_summary["p50_ms"])
    if d <= frame_ms:
        return {"status": PASS, "p50_delta_ms": d,
               "reason": "两支路 p50 相差 %.3fms，在 1 帧（%.3fms）以内——互相印证，"
                         "W-2「通道 C 在 P40 可用」的结论因此有第二个独立数据源支撑"
                         % (d, frame_ms)}
    return {"status": FAIL, "p50_delta_ms": d,
           "reason": "两支路 p50 相差 %.3fms，超过 1 帧（%.3fms）。不预设哪边对——"
                     "两条支路量的是渲染管线里两个不同阶段（SurfaceFlinger 合成 actual "
                     "vs 应用侧 SwapBuffersCompleted），几毫秒的系统性差异本就可能是"
                     "两阶段之间真实存在的间隔，不必然是任一支路出错" % (d, frame_ms)}


def align_present(flips, frames, max_gap_ns):
    """把每次翻转对到「commit 之后最近的一次上屏」。

    返回 (aligned, missed_seqs)。

    对齐前提（写进判据、不靠读者记得）：翻转间隔必须远大于帧周期，否则
    「commit 之后最近的一帧」是二义的。`max_gap_ns` 就是这条前提的守卫——
    超过它说明没对上，记进 missed 而不是硬配一帧。
    """
    aligned, missed = [], []
    for f in flips:
        t0 = f["t_commit_mono_ns"]
        cand = next((fr for fr in frames if fr["actual_ns"] >= t0), None)
        if cand is None or (cand["actual_ns"] - t0) > max_gap_ns:
            missed.append(f["seq"])
            continue
        aligned.append({
            "seq": f["seq"],
            "t_commit_mono_ns": t0,
            "t_present_ns": cand["actual_ns"],
            "delta_ms": (cand["actual_ns"] - t0) / NS_PER_MS,
        })
    return aligned, missed


# ── 通道 B：screencap 帧差 ─────────────────────────────────────────────────
def parse_screencap_index(rows):
    """采集侧写的 jsonl -> [{'t_host_ns','roi_mean','path'}]（按 t_host_ns 升序）。"""
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        t, m = r.get("t_host_ns"), r.get("roi_mean")
        if t is None or m is None:
            continue
        out.append({"t_host_ns": int(t), "roi_mean": float(m), "path": r.get("path")})
    out.sort(key=lambda r: r["t_host_ns"])
    return out


def screencap_sampling_stats(samples, flip_threshold):
    """通道 B 只报两件事：有效采样周期分布，与检出的翻转次数。

    **刻意不报时间误差**：B 的时戳是宿主侧的（screencap 返回时刻），与设备时钟之间
    还隔着一次 adb 往返；拿它报亚帧误差是伪精确（spec §2.2）。
    """
    if len(samples) < 2:
        return {"status": NOT_EXECUTED, "reason": "样本 <2，无法构成周期", "n": len(samples)}
    periods = [(samples[i]["t_host_ns"] - samples[i - 1]["t_host_ns"]) / NS_PER_MS
               for i in range(1, len(samples))]
    transitions = sum(
        1 for i in range(1, len(samples))
        if abs(samples[i]["roi_mean"] - samples[i - 1]["roi_mean"]) >= flip_threshold)
    return {
        "status": PASS,
        "n": len(samples),
        "period_ms_p50": percentile(periods, 50),
        "period_ms_p90": percentile(periods, 90),
        "period_ms_p99": percentile(periods, 99),
        "period_ms_min": min(periods),
        "period_ms_max": max(periods),
        "transitions_detected": transitions,
    }


# ── 汇总 ──────────────────────────────────────────────────────────────────
def summarize(deltas_ms, dropped=0):
    """[float] -> 分布摘要。空输入 -> NOT_EXECUTED（不是一行 0）。"""
    xs = [d for d in deltas_ms if d is not None]
    if not xs:
        return {"status": NOT_EXECUTED, "n": 0, "dropped": dropped,
                "reason": "无可用样本"}
    return {
        "status": PASS,
        "n": len(xs),
        "dropped": dropped,
        "p50_ms": percentile(xs, 50),
        "p90_ms": percentile(xs, 90),
        "p99_ms": percentile(xs, 99),
        "min_ms": min(xs),
        "max_ms": max(xs),
    }


# 本判据的最小样本量（W-4，大脑 2026-08-29 批 A 行；**PROVISIONAL**）。
#
# **依据是本判据自己的，不借用他处**（D-473：一个 KPI 的算术依据套到另一个上会错）：
# 本仓 percentile 取最近秩，**实测 n<100 时 p99 恒等于最大值**（n=1/5/20/50 各测过）。
# 所以在本装置现实批量下，「p99 ≤ 1 帧」读出来其实是「**最大值** ≤ 1 帧」——
# 它不会因为多采几条就变成一个稳定的尾分位。那么 N_MIN 要挡的就不是「分位不稳」
# （那需要 n≥100，本装置到不了），而是**最大值背后只有一两个样本**：n=1 时
# 「p99 ≤ 1 帧」退化成「这一次没超」，判 PASS 等于用一次观测替一个门做结论。
#
# 取 5：在「最大值至少代表 5 次独立观测」与「不把常规小批量全判成未执行」之间。
# 5 这个数**没有本判据的敏感性分析背书**（那需要多窗实测的 n 分布），故标
# PROVISIONAL——大脑要求实测两三窗后校正。它**不是**从 DEFAULT_MIN_SAMPLES
# 借来的：那是战役层低置信地板，为中位数与 CV 推的，与「最大值 vs 1 帧」无关。
GATE_MIN_N = 5          # PROVISIONAL（W-4/A 行）


def gate_verdict(summary, frame_ms, min_n=GATE_MIN_N):
    """通用判据：一份分布的 p99 是否 ≤ 1 帧。被通道 A/C/C-framestats 复用。

    frame_ms 由实测刷新率换算得出，**不硬编码 33**（spec §3.1；D-312 形状）。
    信息不足一律 NOT_EXECUTED —— 没测过不能判 FAIL。

    **本函数只做这一件机械的事，不代表任何单一通道的最终口径结论**——它是否等于
    spec §3.4 的 G-2 本义，**取决于调用方喂给它的 summary 量的是什么**，本函数
    不知道也不该假装知道。这条界线是 D-417/D-418 划的（此前 D-414 版本的这份
    docstring 曾把"通道 C 系的这个判定"直接等同于"G-2 的机器判读"，**在新口径下
    不准确，已改写**——当时的理由"PASS/FAIL 只是残余相对门限的大小关系，不是给
    设备打分"对通道 C 系不再成立：见下。

    **通道 C 系（t_commit→t_present，`ch_c`/`ch_c_framestats`）调用本函数时**：
    喂进来的 summary 量的是**实测总量**，其中混着 `E_pipeline`（设备渲染管线
    commit→present 的固有延迟，spec §3.2 新增第五项，D-417 §1 口径审计）——
    这一项**是**设备的性质，不是打点方法或观测通道的性质，且哪怕通道零延迟
    零量化误差也不会消失。因此对通道 C 系而言，本函数返回的 PASS/FAIL **不是**
    G-2 本义（纯 `E_transport⊕E_quant`）的判定，只是"总量 vs 1 帧"这道机械比较
    的结果——G-2 本义在 E2 把 `E_pipeline` 分解出去之前恒为 `NOT_EXECUTED`
    （见 `g2_true_meaning()`，两者是**两个独立字段**，不要把其中一个的
    PASS/FAIL 读成另一个的结论）。

    **通道 A 调用本函数时**：喂进来的 summary 量的是 `t_event − t_present`
    （事件 vs 通道 C 已对齐的呈现时刻），不是 `t_commit − t_present`，上面这条
    E_pipeline 混入的论证**不直接套用**——通道 A 的口径问题是另一件事（§1.2 的
    A0/A0′ 缺口），本函数同样不代为裁定。

    「1 帧到底该取多少 ms 才对」（尤其 LTPO 变刷屏下 SurfaceFlinger 实测值可能是
    降频态而非满刷态）也是另一个问题，见 `FRAME_MS_SRC_*` 与 spec §3.4 G-5 —— 那是
    大脑/PO 层的口径议题，本函数不代为裁定，只如实拿传入的 frame_ms 去比。
    """
    if summary.get("status") != PASS or frame_ms is None:
        return NOT_EXECUTED, "缺分布或缺实测刷新率"
    p99 = summary.get("p99_ms")
    if p99 is None:
        return NOT_EXECUTED, "无 p99"
    n = summary.get("n") or 0
    dropped = summary.get("dropped") or 0
    # B1（只报不拦）：判词自带分母——一个 PASS 旁边没有 n/dropped，读者无从
    # 判断它值多少（§2.15「汇池出来的数要交代汇了谁」在判词层的应用）。
    scale = "n=%d" % n + ("，另有 %d 条被丢弃" % dropped if dropped else "")
    # A 行（fail-closed，D-511 同构）：n 不足时不给结论。本函数 docstring 自称
    # 「信息不足一律 NOT_EXECUTED」，而 n 恰是它此前没查的那种信息不足。
    if n < min_n:
        return NOT_EXECUTED, ("样本量不足：%s < 最小 %d（本判据 PROVISIONAL 门限）"
                              "——n<100 时 p99 恒等于最大值，n 太小则「p99 ≤ 1 帧」"
                              "退化成「这一次没超」，不足以当结论" % (scale, min_n))
    if p99 <= frame_ms:
        return PASS, "p99 %.3fms <= 1 帧 %.3fms（%s）" % (p99, frame_ms, scale)
    return FAIL, "p99 %.3fms > 1 帧 %.3fms（%s）" % (p99, frame_ms, scale)


def g2_true_meaning():
    """spec §3.4 G-2 本义（纯 `E_transport⊕E_quant` ≤ 1 帧）的当前判定。

    与 `gate_verdict()` 对通道 C 系算出的「t_commit→t_present 实测总量 vs 1 帧」
    是**两个独立字段**——不要把其中一个的 PASS/FAIL 读成另一个的结论。

    D-417/D-418：E1 目前拿 `t_commit` 代替语义真值 `t0`（§1.2 既有缺口），实测
    总量因此必然混入 `E_pipeline`（spec §3.2 新增第五项，设备渲染管线固有延迟，
    不是通道或方法的性质）。在 E2 把 `E_pipeline` 从总量里分解出去之前，G-2
    本义恒为 `NOT_EXECUTED`——这是一个**固定值**，不依赖本次跑出的任何数字
    （即便总量 PASS，也不代表 G-2 本义 PASS：上界不超门 ≠ 本体不超门）。
    """
    return (NOT_EXECUTED,
            "G-2 本义需 E2 把 E_pipeline 从总量中分解出去后才可判——E1 未做"
            "（spec §3.2/§3.4，D-417/D-418）")


def g2_candidate_c(frame_ms):
    """候选 C 治理状态（PO 批复 D-432②，spec §3.4）——**不是**对 G-2 本义的判定，
    是治理层在 G-2 本义仍 `NOT_EXECUTED` 期间批准的一项操作性豁免。

    与 `g2_true_meaning()` 是两个独立字段：后者答"G-2 判过没有"（技术判断，
    恒 `NOT_EXECUTED`）；本函数答"数据现在能不能带标注用"（治理判断，恒定
    `band_frames=2`，但 `band_ms` 随本次实测帧长而变）。**故意不用 PASS/FAIL/
    NOT_EXECUTED 三态词**——那三个词是测量结果的语汇，本函数返回的是一条
    政策事实，用同一套词会让读者把治理决定误读成又一次测量（`cadence_check()`
    用 `MATCH`/`MISMATCH` 而非 PASS/FAIL 是同一形状的先例）。

    **毫秒数不硬编码 33.334**（D-312/D-414 那条纪律的延伸应用：帧基准从
    `frame_ms` 参数取——同一处代码派生的实测值，不是本函数另编一个）。
    `frame_ms` 为 `None`（例如 sf_latency 缺失、又无刺激源自报兜底）时
    `band_ms` 也是 `None`——**宁可报"本次无实测帧长"，不拿默认值顶上**
    （R-10 同精神）。

    **物理是单侧的，不是对称 ±**：commit ≤ present 恒成立，`band_ms` 描述
    的是"若锚点语义实为 App 提交、只能反推"这一读法下 `t_commit` 相对
    `t_present` 的**下探区间宽度**（`t_commit ∈ [t_present−band_ms,
    t_present]`），不是"早也可能晚也可能"的对称带（大脑技术参谋四条前瞻，
    2026-08-03，供 D-433 之后的措辞订正）。

    候选 B（E2 校正后误差）生效后，本函数应被替换或改写，不属本轮范围。
    """
    band_ms = 2.0 * frame_ms if frame_ms is not None else None
    band_desc = ("%.3fms" % band_ms) if band_ms is not None else "（本次无实测帧长，带宽未定）"
    return {
        "active": True,
        "band_frames": 2,
        "band_ms": band_ms,
        "note": ("Profile 3 时间敏感数据（通道 A 类比读法，借用通道 C 的"
                 "commit→present 量级做保守上界）可读作呈现时刻的**下界**，"
                 "真实呈现可能晚至 +%s（单侧，不是对称±；帧基准取值规则见"
                 "frame_ms_source/D-414），不再因 G-2 本义未判而恒"
                 "LOW/INCONCLUSIVE（spec §3.4 候选 C 例外）。依据=两个独立"
                 "E1 型窗（run3 n=53 + DW-20260803-03 n=160，T40），双峰形状"
                 "互相印证、p99 均在带内，判断=维持带宽不收窄不加宽。这是 E2 分解"
                 "前的当下语义，不是永久判据；"
                 "升级路径=候选 B（E2 可跑后按 T29 占比门提案，阈值待真实数据）。"
                 % band_desc),
    }


def _analyze_channel_a(good, aligned, evts, off_ns, frame_ms_c, max_gap_ns):
    """通道 A：t_event(BOOT) 换算到 MONOTONIC 后减去该翻转的 t_present。

    换算用刺激源同帧测得的偏移；偏移缺失即整条通道 NOT_EXECUTED——
    **宁可不报，也不拿一个假定为 0 的偏移去减**（那会得到一个看着合理的错数）。
    """
    if off_ns is None:
        return ({"status": NOT_EXECUTED, "n": 0,
                 "reason": "缺 BOOTTIME↔MONOTONIC 偏移，跨基比较不可做"},
                NOT_EXECUTED, "缺时钟偏移")
    present_by_seq = {a["seq"]: a["t_present_ns"] for a in aligned}
    deltas, dropped = [], 0
    for f in good:
        t_present = present_by_seq.get(f["seq"])
        if t_present is None:
            dropped += 1
            continue
        t0_boot = f["t_commit_boot_ns"]
        cand = next((e for e in evts if e["t_boot_ns"] >= t0_boot), None)
        if cand is None or (cand["t_boot_ns"] - t0_boot) > max_gap_ns:
            dropped += 1
            continue
        t_evt_mono = cand["t_boot_ns"] - off_ns
        deltas.append((t_evt_mono - t_present) / NS_PER_MS)
    s = summarize(deltas, dropped=dropped)
    v, r = gate_verdict(s, frame_ms_c)
    return s, v, r


def _cadence_check(obs, interval_ms):
    """今天就能跑的弱检查：通道 A 报的 cadence_p50 应约等于刺激源的翻转间隔。

    它证不了偏移（那要逐事件时戳），只证「通道 A 确实看见了这串翻转」。
    结论只有 MATCH / MISMATCH / NOT_EXECUTED —— 不给"接近程度"的分数，
    那会诱人把它读成精度。
    """
    if not obs or interval_ms is None:
        return {"status": NOT_EXECUTED, "reason": "无 ADAPTER_OBS 行或无 interval_ms"}
    cads = [o["cadence_p50_ms"] for o in obs if o.get("cadence_p50_ms") is not None]
    if not cads:
        return {"status": NOT_EXECUTED, "reason": "ADAPTER_OBS 未报 cadence_p50_ms"}
    med = percentile(cads, 50)
    # ±20% 是「看见了没有」的宽带判据，不是精度指标：翻转间隔 2000ms 下它对应 ±400ms，
    # 远宽于任何时序主张。刻意取宽，免得被误读成误差门。
    ok = abs(med - interval_ms) <= 0.2 * interval_ms
    return {"status": "MATCH" if ok else "MISMATCH",
            "cadence_p50_ms": med, "interval_ms": interval_ms, "n": len(cads)}


def analyze(stim_lines, adapter_lines, sf_text, framestats_text, screencap_rows,
            flip_threshold=8.0, max_gap_frames=4.0):
    """全链判读。返回一个 dict（渲染与落盘由调用方做，本函数无 IO）。"""
    cfg, flips = parse_stim_log(stim_lines)
    good = usable_flips(flips)
    frame_ms = cfg.get("frame_ms")

    off_ns, off_spread_ns, off_n = clock_offset_ns(good)

    period_ns, frames_raw = parse_sf_latency(sf_text or "")
    # 帧周期优先取 SurfaceFlinger 实测；缺则退回刺激源报的刷新率换算。
    # 这条规则现在同时是一个显式、可审计的字段（L-1）——不再只活在这行注释里。
    frame_ms_c = (period_ns / NS_PER_MS) if period_ns else frame_ms
    frame_ms_source = FRAME_MS_SRC_MEASURED if period_ns else FRAME_MS_SRC_STIMULUS
    max_gap_ns = int((frame_ms_c or 16.667) * max_gap_frames * NS_PER_MS)

    # T40：周期性 dump（`--framestats-period-s`）会让 --latency 的原始行大量重复，
    # 去重不改判定结果（见 dedup_sf_latency_frames docstring），但原始行数不该
    # 被读成"捕捉到的帧数"——sf_frames 字段把两个数都亮出来，供渲染层如实报。
    frames = dedup_sf_latency_frames(frames_raw)
    sf_frames = {"raw": len(frames_raw), "deduped": len(frames),
                "duplicate_dropped": len(frames_raw) - len(frames)}

    aligned, missed = align_present(good, frames, max_gap_ns)
    ch_c = summarize([a["delta_ms"] for a in aligned], dropped=len(missed))
    verdict_c, reason_c = gate_verdict(ch_c, frame_ms_c)

    # L-2：framestats 是 --latency 之外的第二条通道 C 支路，同一批 good flips、
    # 同一个 frame_ms_c/max_gap_ns，对齐逻辑复用 align_present（不新写一套判据）。
    fs_rows_parsed = parse_framestats(framestats_text or "")
    fs_frames = dedup_framestats_present_times(fs_rows_parsed)
    aligned_fs, missed_fs = align_present(good, fs_frames, max_gap_ns)
    ch_c_framestats = summarize([a["delta_ms"] for a in aligned_fs], dropped=len(missed_fs))
    verdict_c_fs, reason_c_fs = gate_verdict(ch_c_framestats, frame_ms_c)
    cross_check = cross_check_channel_c(ch_c, ch_c_framestats, frame_ms_c)

    evts = parse_adapter_events(adapter_lines or [])
    obs = parse_adapter_obs(adapter_lines or [])
    if not evts:
        ch_a = {
            "status": NOT_EXECUTED,
            "n": 0,
            "reason": ("无障碍侧无逐事件时戳：AnebAccessibilityService 今天只打 "
                       "click 型 ADAPTER_EVT（无 t_boot_ns）与 5s 节流的 ADAPTER_OBS 聚合。"
                       "需 :probe 侧一行 additive 扩展后方可判读，见本文件模块注释。"),
        }
        verdict_a, reason_a = NOT_EXECUTED, "通道 A 无逐事件时戳"
    else:
        ch_a, verdict_a, reason_a = _analyze_channel_a(
            good, aligned, evts, off_ns, frame_ms_c, max_gap_ns)

    ch_b = screencap_sampling_stats(parse_screencap_index(screencap_rows or []), flip_threshold)

    return {
        "cfg": cfg,
        "flips_total": len(flips),
        "flips_usable": len(good),
        "clock": {"boot_minus_mono_ns": off_ns, "spread_ns": off_spread_ns, "n": off_n},
        "frame_ms_measured": frame_ms_c,
        "frame_ms_from_stimulus": frame_ms,
        "frame_ms_source": frame_ms_source,
        "sf_frames": sf_frames,
        "framestats_rows": len(fs_rows_parsed),
        "channel_a": ch_a, "channel_a_verdict": (verdict_a, reason_a),
        "channel_b": ch_b,
        "channel_c": ch_c, "channel_c_verdict": (verdict_c, reason_c),
        "channel_c_framestats": ch_c_framestats,
        "channel_c_framestats_verdict": (verdict_c_fs, reason_c_fs),
        "channel_c_cross_check": cross_check,
        "g2_true_meaning": g2_true_meaning(),
        "g2_candidate_c": g2_candidate_c(frame_ms_c),
        "adapter_obs_lines": obs,
        "cadence_check": _cadence_check(obs, cfg.get("interval_ms")),
    }


# ── 渲染 ──────────────────────────────────────────────────────────────────
def _fmt(v, nd=3):
    if v is None:
        return "—"
    return ("%.*f" % (nd, v)) if isinstance(v, float) else str(v)


def render_markdown(res):
    L = []
    cfg = res["cfg"]
    L.append("# E1 已知真值刺激实验 —— 判读结果")
    L.append("")
    L.append("> 出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §3.3 实验 E1。")
    L.append("> 状态词只用 PASS / FAIL / NOT_EXECUTED。空样本一律 NOT_EXECUTED，不折 0。")
    L.append("")
    L.append("## 0. 本次刺激配置")
    L.append("")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    for k in ("interval_ms", "count", "roi_px", "warmup", "refresh_hz", "screen_px"):
        L.append("| `%s` | %s |" % (k, _fmt(cfg.get(k))))
    L.append("| 翻转总数 / 可用（去预热、有 commit） | %s / %s |"
             % (res["flips_total"], res["flips_usable"]))
    if cfg.get("duplicate_seq"):
        L.append("| ⚠ 重复 seq（App 被重启过，后者覆盖前者） | %s |" % cfg["duplicate_seq"])
    if cfg.get("cfg_blocks"):
        L.append("| ⚠ 本次日志含 %d 个 CFG 块，上表只反映**最后一个**——"
                 "多数可用翻转可能来自更早、已被覆盖的块，勿拿本表 `interval_ms` "
                 "去算「期望节奏」再跟翻转总数比对（D-409 K-2） | — |"
                 % cfg["cfg_blocks"])
    L.append("")
    src_label = {FRAME_MS_SRC_MEASURED: "SurfaceFlinger 实测（优先，L-1）",
                FRAME_MS_SRC_STIMULUS: "刺激源自报 refresh_hz（sf_latency 缺失时回退）"
                }[res["frame_ms_source"]]
    L.append("**一帧 = %s ms**（来源：%s；非硬编码 33ms —— spec §3.1）。"
             % (_fmt(res["frame_ms_measured"]), src_label))
    sfc = res.get("sf_frames")
    if sfc and sfc.get("duplicate_dropped"):
        L.append("")
        L.append("> `--latency` 原始行 %s 条，按 `actual_ns` 去重后 %s 条（丢弃 %s 条重复，"
                 "周期性 dump 相邻重叠所致，同 framestats 既有去重同一根因）——**原始行数"
                 "不等于捕捉到的帧数**，判定用的是去重后的数字，且去重前后判定结果逐位相同"
                 "（`align_present` 对每次翻转只取单一最近匹配，重复行不改变匹配到的时刻）。"
                 % (sfc["raw"], sfc["deduped"], sfc["duplicate_dropped"]))
    stim_ms, measured_ms = res.get("frame_ms_from_stimulus"), res.get("frame_ms_measured")
    if (res["frame_ms_source"] == FRAME_MS_SRC_MEASURED and stim_ms is not None
            and measured_ms is not None
            and abs(measured_ms - stim_ms) > FRAME_MS_DISAGREEMENT_EPSILON_MS):
        L.append("")
        L.append("> ⚠ **两个候选值不一致**：SurfaceFlinger 实测 %s ms，刺激源自报"
                 "（`Display.getRefreshRate()`）算出的却是 %s ms——本工具按上面的判据来源"
                 "取了前者。P40 是 LTPO 变刷屏（90Hz 满刷 / 静态内容可能降频合成），"
                 "SurfaceFlinger 此刻测到的合成周期完全可能是一次真实的降频态，不必然是 bug。"
                 "**「1 帧」该按哪个算，是 M3 门（spec §3.4 G-5）可达性的口径问题，"
                 "本工具不代为裁定**——此处只如实报告两个数字都存在且不相等（G-2 首次实测，"
                 "D-413 run3）。" % (_fmt(measured_ms), _fmt(stim_ms)))
    L.append("")
    c = res["clock"]
    L.append("## 1. 时钟基（跨通道比较的前提）")
    L.append("")
    L.append("BOOTTIME − MONOTONIC 偏移中位数 = %s ns，跨度 = %s ns（n=%s）。"
             % (_fmt(c["boot_minus_mono_ns"], 0), _fmt(c["spread_ns"], 0), c["n"]))
    L.append("")
    L.append("> 跨度不是噪声，是这段时间里设备深睡了多久。它非 0 即意味着通道 A（BOOTTIME）")
    L.append("> 与通道 C（MONOTONIC）**不能直接相减** —— 这修正了 spec §3.2「E_clock 已有界」")
    L.append("> 的适用范围：那句话对「只有通道 A」成立，通道 C 一入场就不再成立。")
    L.append("")
    L.append("## 2. 按通道分列")
    L.append("")
    L.append("| 通道 | 量的是什么 | n | dropped | p50 (ms) | p90 (ms) | p99 (ms) | 总量 vs 1 帧 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for key, name, what in (
            ("channel_a", "A 无障碍事件", "t_event → t_present（跨基，已换算）"),
            ("channel_c", "C 渲染时间线",
             "t_commit → t_present（同基，**实测总量**——含 E_pipeline，非纯通道误差，D-417/D-418）")):
        s = res[key]
        v, r = res[key + "_verdict"]
        L.append("| %s | %s | %s | %s | %s | %s | %s | **%s** — %s |" % (
            name, what, s.get("n", 0), s.get("dropped", "—"),
            _fmt(s.get("p50_ms")), _fmt(s.get("p90_ms")), _fmt(s.get("p99_ms")), v, r))
    fc = res["channel_c_framestats"]
    vfc, rfc = res["channel_c_framestats_verdict"]
    L.append("| C（framestats，L-2） | t_commit → SwapBuffersCompleted（同基，第二支路，**实测总量**——"
             "含 E_pipeline，非纯通道误差，D-417/D-418） | %s | %s | %s | %s | %s | **%s** — %s |"
             % (fc.get("n", 0), fc.get("dropped", "—"), _fmt(fc.get("p50_ms")),
                _fmt(fc.get("p90_ms")), _fmt(fc.get("p99_ms")), vfc, rfc))
    b = res["channel_b"]
    L.append("| B screencap 帧差 | **不报时间误差**，只报采样周期 | %s | — | %s | %s | %s | %s |"
             % (b.get("n", 0), _fmt(b.get("period_ms_p50")), _fmt(b.get("period_ms_p90")),
                _fmt(b.get("period_ms_p99")), b.get("status")))
    L.append("")
    if res["channel_a"].get("reason"):
        L.append("**通道 A 未判读的原因**：%s" % res["channel_a"]["reason"])
        L.append("")
    if b.get("status") == PASS:
        L.append("通道 B 检出翻转 %s 次（刺激源共翻 %s 次）——检出率不是时序主张，"
                 "只说明 ROI 与阈值选得对不对。"
                 % (b.get("transitions_detected"), _fmt(cfg.get("count"))))
        L.append("")
    cross = res["channel_c_cross_check"]
    L.append("**通道 C 交叉验证（`--latency` vs `framestats`，L-2，spec `INSTRUMENTATION_SPEC` "
             "§6 K-2）**：%s — %s" % (cross["status"], cross["reason"]))
    L.append("")
    g2v, g2r = res["g2_true_meaning"]
    L.append("**G-2 本义（spec §3.4，纯 `E_transport⊕E_quant` ≤ 1 帧）**：**%s** — %s" % (g2v, g2r))
    L.append("")
    L.append("> 上面「总量 vs 1 帧」那一列是**独立字段**，不是 G-2 本义——两者语义不同、"
             "互不代表（D-417/D-418）：即便总量列 PASS，也不能读成 G-2 本义 PASS。")
    L.append("")
    g2cc = res["g2_candidate_c"]
    L.append("**候选 C 生效（PO 批复 D-432②）**：%s" % g2cc["note"])
    L.append("")
    cc = res["cadence_check"]
    L.append("## 3. 通道 A 弱检查（今天就能跑的那条）")
    L.append("")
    L.append("`ADAPTER_OBS.cadence_p50_ms` vs 刺激间隔：**%s**"
             "（cadence=%s ms, interval=%s ms, n=%s）。"
             % (cc.get("status"), _fmt(cc.get("cadence_p50_ms")),
                _fmt(cc.get("interval_ms")), cc.get("n", 0)))
    L.append("")
    L.append("> 它证不了偏移，只证「通道 A 确实看见了这串翻转」。判据带宽 ±20% 是刻意取宽的，"
             "免得被读成精度指标。")
    L.append("")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="E1 误差判读（三通道分列）")
    ap.add_argument("--run-dir", required=True, help="e1_collect.py 产出的目录")
    ap.add_argument("--out-md", default=None, help="markdown 落点（默认 <run-dir>/e1_report.md）")
    ap.add_argument("--flip-threshold", type=float, default=8.0,
                    help="ROI 均值变化阈（0-255 灰度），超过即判一次翻转")
    ap.add_argument("--stim-file", default="stim.log",
                    help="真值刺激日志的文件名（run-dir 内），默认 stim.log（向后兼容）；"
                         "e234_collect.py 产出的是 stim_pre.log/stim_post.log，"
                         "指到其中之一即可复用本判读链（D-407）")
    args = ap.parse_args(argv)

    d = args.run_dir
    if not os.path.isdir(d):
        # 报错通道自己也要能活着把话说完（D-265）：不假设路径可读、不假设编码。
        sys.stderr.write("run-dir 不存在: %s\n" % d)
        return 2

    def _read_lines(name):
        p = os.path.join(d, name)
        if not os.path.exists(p):
            return []
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            return fh.readlines()

    def _read_text(name):
        p = os.path.join(d, name)
        if not os.path.exists(p):
            return ""
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()

    rows = []
    p = os.path.join(d, "screencap_index.jsonl")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue  # 半行（采集被中断）——跳过，不让一行坏 JSON 毁掉整次判读

    res = analyze(_read_lines(args.stim_file), _read_lines("adapter.log"),
                  _read_text("sf_latency.txt"), _read_text("framestats.txt"),
                  rows, flip_threshold=args.flip_threshold)

    out = args.out_md or os.path.join(d, "e1_report.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(res))
    sys.stdout.write("E1 report -> %s\n" % out)
    sys.stdout.write("channel_c=%s channel_a=%s\n"
                     % (res["channel_c_verdict"][0], res["channel_a_verdict"][0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
