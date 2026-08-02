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

`AnebAccessibilityService` 今天只打两种日志：`ADAPTER_EVT`（**仅 click 事件**，且 DEBUG 门控）
与 `ADAPTER_OBS`（**5 秒节流的聚合**：events / first_delta_ms / cadence_p50_ms）。
**内容变化事件没有逐事件时戳**，因此 `t_event` 拿不到。

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
    cfg, flips, dup = {}, {}, 0
    for raw in lines:
        line = raw.rstrip("\n")
        m = _CFG_RE.search(line)
        if m:
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

    只收**带 t_boot_ns 的行**。既有实现的 click 行没有该字段，会被如实忽略——
    忽略比"用行到达顺序编个时戳"安全得多。
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


def gate_verdict(summary, frame_ms):
    """spec §3.4 G-2 的机器判读：主用通道 p99 ≤ 1 帧 ?

    frame_ms 由实测刷新率换算得出，**不硬编码 33**（spec §3.1；D-312 形状）。
    信息不足一律 NOT_EXECUTED —— 没测过不能判 FAIL。
    """
    if summary.get("status") != PASS or frame_ms is None:
        return NOT_EXECUTED, "缺分布或缺实测刷新率"
    p99 = summary.get("p99_ms")
    if p99 is None:
        return NOT_EXECUTED, "无 p99"
    if p99 <= frame_ms:
        return PASS, "p99 %.3fms <= 1 帧 %.3fms" % (p99, frame_ms)
    return FAIL, "p99 %.3fms > 1 帧 %.3fms" % (p99, frame_ms)


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

    period_ns, frames = parse_sf_latency(sf_text or "")
    # 帧周期优先取 SurfaceFlinger 实测；缺则退回刺激源报的刷新率换算。
    frame_ms_c = (period_ns / NS_PER_MS) if period_ns else frame_ms
    max_gap_ns = int((frame_ms_c or 16.667) * max_gap_frames * NS_PER_MS)

    aligned, missed = align_present(good, frames, max_gap_ns)
    ch_c = summarize([a["delta_ms"] for a in aligned], dropped=len(missed))
    verdict_c, reason_c = gate_verdict(ch_c, frame_ms_c)

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
        "framestats_rows": len(parse_framestats(framestats_text or "")),
        "channel_a": ch_a, "channel_a_verdict": (verdict_a, reason_a),
        "channel_b": ch_b,
        "channel_c": ch_c, "channel_c_verdict": (verdict_c, reason_c),
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
    L.append("")
    L.append("**一帧 = %s ms**（实测，非硬编码 33ms —— spec §3.1）。"
             % _fmt(res["frame_ms_measured"]))
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
    L.append("| 通道 | 量的是什么 | n | dropped | p50 (ms) | p90 (ms) | p99 (ms) | 判定 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for key, name, what in (
            ("channel_a", "A 无障碍事件", "t_event → t_present（跨基，已换算）"),
            ("channel_c", "C 渲染时间线", "t_commit → t_present（同基）")):
        s = res[key]
        v, r = res[key + "_verdict"]
        L.append("| %s | %s | %s | %s | %s | %s | %s | **%s** — %s |" % (
            name, what, s.get("n", 0), s.get("dropped", "—"),
            _fmt(s.get("p50_ms")), _fmt(s.get("p90_ms")), _fmt(s.get("p99_ms")), v, r))
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
