#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""会话语料的读取与切轮 —— E2/E3/E4 三个判读脚本共用的那一层。

出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §1.2（锚点）、§2.1（通道 A）。

## 为什么切轮要靠**操作者标记**，而不是靠静默门限

E4 要标定的正是「多长的静默算回答结束」（`T_quiet`，§1.5 C-1）。若切轮本身
用一个静默门限来做，那么 E4 就是拿待标定量去标定它自己 —— 分离点会被造出来，
而且造得很好看。所以本层的轮边界只有两个合法来源：

1. **操作者标记**（`E4MARK`）：会话进行中由采集侧往设备 logcat 里打一行，
   与 `ADAPTER_EVT` 落在同一条流里，因而共享同一份墙钟前缀 ——
   换算靠 `fit_wall_to_boot()` **量出来**的偏移，不靠假设（见 e234_common）。
2. **整段当一轮**（无标记时的退化态）：这时 n 结构上就是 1，判读侧必须把
   「n=1」印出来而不是印一个 p99。**一个样本算得出 p99，但那个 p99 什么也不是。**

`answer_complete` 标记本身是 §1.5 C-2 那一级判据的人工版：它是**独立于 C-1**
的结束信号，这正是标定 C-1 时必须有的那个外部真值。
"""
import re

import e234_common as ec

MARK_TAG = "AnebE4MARK"
_MARK_RE = re.compile(r"E4MARK\s+(?P<kv>kind=\S.*)$")
_KV_RE = re.compile(r"(\w+)=([^\s]+)")

KIND_TURN_START = "turn_start"
KIND_ANSWER_COMPLETE = "answer_complete"
KIND_ANSWER_START = "answer_start"
MARK_KINDS = (KIND_TURN_START, KIND_ANSWER_START, KIND_ANSWER_COMPLETE)

TURN_METHOD_MARKS = "operator-marks"
TURN_METHOD_WHOLE_RUN = "whole-run"


def content_events(lines, pkg):
    """通道 A 的逐事件时戳（只收 `type=content` 且 pkg 命中的行）。

    复用 `e1_analyze.parse_adapter_events`（它只收带 `t_boot_ns=` 的行，
    没有该字段的行被如实忽略）。这里只加两件 E1 不需要的事：
    按 pkg 过滤（T14 §4.2：`_cadence_check` 不按 pkg 过滤，别的 App 一条
    OBS 就能得出「通道 A 看见了这串翻转」），以及量纲过滤（T14 §2.1②）。
    返回 (events, dropped_pkg, dropped_dimension)。
    """
    evts = ec.ea.parse_adapter_events(lines or [])
    same = [e for e in evts if e.get("type") == "content" and e.get("pkg") == pkg]
    kept, bad_dim = ec.reject_implausible(same, "t_boot_ns")
    return kept, len(evts) - len(same), bad_dim


def parse_marks(lines, fit):
    """`E4MARK kind=... n=...` -> [{'kind','n','t_boot_ns','wall_ms'}]（升序）。

    `fit` 是 `fit_wall_to_boot()` 的结果；它不 PASS 就一条标记都不返回 ——
    **没有换算依据时给出的标记时刻是编的**，而编出来的时刻会安静地改变分母。
    """
    out = []
    if fit.get("status") != ec.PASS:
        return out
    for raw in lines or []:
        m = _MARK_RE.search(raw)
        if not m:
            continue
        w = ec.wall_ms_of_line(raw)
        if w is None:
            continue
        d = dict(_KV_RE.findall(m.group("kv")))
        kind = d.get("kind")
        if kind not in MARK_KINDS:
            continue
        out.append({"kind": kind, "n": d.get("n"), "wall_ms": w,
                    "t_boot_ns": ec.wall_ms_to_boot_ns(w, fit)})
    out.sort(key=lambda r: r["wall_ms"])
    return out


def segment_turns(events, marks):
    """事件流 + 标记 -> [{'idx','t_start_ns','t_end_ns','events','answer_start_ns'}]。

    轮窗 = (上一个 `answer_complete`，本次 `answer_complete`]，起点可被
    `turn_start` 覆盖。`answer_start` 若有则原样带出（DeepSeek 用得上：
    §1.4 记 A0' 与 v3 簇分割在自绘 Compose 栈上都不可得，那时 A2 只能靠人标）。

    返回 (turns, method)。无标记 -> 整段一轮，method=`whole-run`，
    **由调用方在每一个面上印出这件事**（n 结构上等于 1，别让它长得像 n 很多）。
    """
    if not events:
        return [], TURN_METHOD_WHOLE_RUN
    ends = [m for m in marks if m["kind"] == KIND_ANSWER_COMPLETE
            and m.get("t_boot_ns") is not None]
    if not ends:
        return ([{"idx": 0, "t_start_ns": events[0]["t_boot_ns"],
                  "t_end_ns": events[-1]["t_boot_ns"], "answer_start_ns": None,
                  "events": list(events)}], TURN_METHOD_WHOLE_RUN)
    starts = [m for m in marks if m["kind"] == KIND_TURN_START
              and m.get("t_boot_ns") is not None]
    a_starts = [m for m in marks if m["kind"] == KIND_ANSWER_START
                and m.get("t_boot_ns") is not None]
    turns, prev = [], None
    for i, e in enumerate(ends):
        lo = prev if prev is not None else events[0]["t_boot_ns"] - 1
        explicit = [s["t_boot_ns"] for s in starts
                    if lo < s["t_boot_ns"] <= e["t_boot_ns"]]
        if explicit:
            lo = min(explicit) - 1
        a_s = [s["t_boot_ns"] for s in a_starts
               if lo < s["t_boot_ns"] <= e["t_boot_ns"]]
        turns.append({
            "idx": i,
            "t_start_ns": lo + 1,
            "t_end_ns": e["t_boot_ns"],
            "answer_start_ns": min(a_s) if a_s else None,
            "events": [ev for ev in events
                       if lo < ev["t_boot_ns"] <= e["t_boot_ns"]],
        })
        prev = e["t_boot_ns"]
    return turns, TURN_METHOD_MARKS


def frames_in(frames, lo_mono_ns, hi_mono_ns):
    return [f for f in frames if lo_mono_ns <= f["actual_ns"] <= hi_mono_ns]
