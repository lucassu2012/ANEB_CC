#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""会话模拟器 —— 生成与 `e234_collect.py` **逐字段同形**的合成语料，供 dry-run。

出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §3.3。本文件**不产生任何测量结果**，
它只回答一个问题：三个判读脚本在已知真值下算得对不对。

## 它为什么必须存在（而不是"直接上机试试"）

E2/E3/E4 都要 P40 + 已装 App + 真实额度，且需排窗（spec §3.3 各自的资源栏）。
一次设备窗最贵的是会话本身。判读脚本第一次见到数据就在设备窗里，等于把
「脚本有没有 bug」和「设备上取不取得到」两件事绑在一起 —— e1 已经付过这笔学费：
图层选错**一度把通道 C 的失败伪装成图层 bug**（`tools/e1/README.md` §4 第 2 条）。

## 它绝不做的一件事：把数字说成测量

每一份产物的第一个文件是 `RUN_KIND.json`，`kind = DRY_RUN_SIMULATED`，
连同**注入的真值参数**一起写进去。判读侧读到它就在每一个面上盖 DRY_RUN 横幅，
E4 更是**结构上产不出**标定值（`e234_common.refuse_calibration_from_dry_run`）。

## E4 的两个场景是**对照组**，参数写死在下面，不许调

`e4_separable` 与 `e4_overlap` 的分布参数是这份源码里的字面量，且原样进
`RUN_KIND.json`。这不是形式主义：E4 唯一可能的作弊方式，就是把参数往
「看起来可分」的方向挪一挪。参数写死 + 落盘 + 两个方向各一个场景，
让「调到可分」这件事做不了也藏不住（spec §3.3 E4 逐字：
「不得为了拿到数值而硬凑」；D-53 先例）。
"""
import argparse
import json
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import e234_common as ec   # noqa: E402
import e234_session as es  # noqa: E402
import e1_io                    # noqa: E402  (D-648③ 输出编码自锁)

# ── 基准（任意但固定；只用于差值，绝对值无意义）────────────────────────────
BOOT_BASE_NS = 8_000_000_000_000        # 开机 8000 s
MONO_BASE_NS = 5_000_000_000_000
BOOT_MINUS_MONO_NS = BOOT_BASE_NS - MONO_BASE_NS
WALL_BASE_MS = 3_600_000                # logcat 墙钟起点（当天 01:00:00.000）
HOST_BASE_NS = 1_785_000_000_000_000_000  # 宿主 epoch 时刻；与设备钟**无标定关系**
FRAME_NS = 16_666_666                   # 60 Hz
SIM_PKG = "com.larus.nova"

# ── 场景表（**参数即真值**；原样进 RUN_KIND.json）──────────────────────────
SCENARIOS = {
    # —— E2：通道 A 相对通道 C 的锚定偏差 ——
    "e2_within_one_frame": {
        "purpose": "E2 装置校验：注入的 A−C 偏差在 1 帧以内，判读应给 PASS",
        "turns": 6, "stream_events": 25, "a_lag_ms": [2.0, 6.0],
        "ttft_ms": 1900, "a0_gap_ms": 120, "stream_gap_ms": [80, 120, 95, 150, 110],
        "post_silence_ms": [4000], "framestats": "new",
    },
    "e2_over_one_frame": {
        "purpose": "E2 装置校验：注入的 A−C 偏差约 3 帧，判读应给 FAIL（门不能只会说 PASS）",
        "turns": 6, "stream_events": 25, "a_lag_ms": [45.0, 55.0],
        "ttft_ms": 1900, "a0_gap_ms": 120, "stream_gap_ms": [80, 120, 95, 150, 110],
        "post_silence_ms": [4000], "framestats": "new",
    },
    # —— E3：A0→A0′ ——
    "e3_input_timeline_present": {
        "purpose": "E3 装置校验：framestats 带输入事件时戳列，A0 可锚，注入间隔 180ms",
        "turns": 6, "stream_events": 25, "a_lag_ms": [3.0, 5.0],
        "ttft_ms": 1900, "a0_gap_ms": 180, "stream_gap_ms": [90, 130],
        "post_silence_ms": [4000], "framestats": "old",
    },
    "e3_input_timeline_absent": {
        "purpose": "E3 装置校验：framestats 只有 InputEventId（实测归档的那种表头），"
                   "A0 不可锚 —— 判读必须 NOT_EXECUTED 并点名，不得拿别的列顶替",
        "turns": 6, "stream_events": 25, "a_lag_ms": [3.0, 5.0],
        "ttft_ms": 1900, "a0_gap_ms": 180, "stream_gap_ms": [90, 130],
        "post_silence_ms": [4000], "framestats": "new",
    },
    # —— E4：T_quiet 的两个对照组 ——
    "e4_separable": {
        "purpose": "E4 对照组·可分：流式内最大停顿 900ms，回答后静默 ≥3000ms",
        "turns": 10, "stream_events": 30, "a_lag_ms": [3.0, 5.0],
        "ttft_ms": 1900, "a0_gap_ms": 150,
        "stream_gap_ms": [60, 90, 120, 200, 380, 640, 900],
        "post_silence_ms": [3000, 4200, 5500, 6000], "framestats": "new",
    },
    "e4_overlap": {
        "purpose": "E4 对照组·重叠：流式内最大停顿 4200ms，回答后静默最短 1800ms —— "
                   "两个分布交叠，正确结论是 C-1 单独不可用（spec §3.3 E4）",
        "turns": 10, "stream_events": 30, "a_lag_ms": [3.0, 5.0],
        "ttft_ms": 1900, "a0_gap_ms": 150,
        "stream_gap_ms": [60, 90, 150, 400, 1100, 2600, 4200],
        "post_silence_ms": [1800, 2400, 3300, 5000], "framestats": "new",
    },
}

MARK_LAG_MS = 350.0     # 操作者看到回答完成到敲键之间的反应时间（人工标记的固有滞后）

OLD_HEADER = ("Flags,IntendedVsync,Vsync,OldestInputEvent,NewestInputEvent,"
              "HandleInputStart,AnimationStart,PerformTraversalsStart,DrawStart,"
              "SyncQueued,SyncStart,IssueDrawCommandsStart,SwapBuffers,FrameCompleted,")
# 下面这一行是 `evidence/e1/20260801-170127/framestats.txt` 的**逐字表头**。
# 它没有 OldestInputEvent/NewestInputEvent，只有一个 `InputEventId`——那是个 id，
# 不是时戳。E3 的 A0 判据挂在这上面，故这个形状必须能被模拟出来。
NEW_HEADER = ("Flags,FrameTimelineVsyncId,IntendedVsync,Vsync,InputEventId,"
              "HandleInputStart,AnimationStart,PerformTraversalsStart,DrawStart,"
              "FrameDeadline,FrameInterval,FrameStartTime,SyncQueued,SyncStart,"
              "IssueDrawCommandsStart,SwapBuffers,FrameCompleted,DequeueBufferDuration,"
              "QueueBufferDuration,GpuCompleted,SwapBuffersCompleted,DisplayPresentTime,"
              "CommandSubmissionCompleted,")


def _wall(ms):
    s, msec = divmod(int(round(ms)), 1000)
    m, sec = divmod(s, 60)
    h, minute = divmod(m, 60)
    return "08-02 %02d:%02d:%02d.%03d" % (h % 24, minute, sec, msec)


def _wall_of_boot(boot_ns):
    return _wall(WALL_BASE_MS + (boot_ns - BOOT_BASE_NS) / ec.NS_PER_MS)


def build(scenario, seed=20260802):
    """场景名 -> 时间线（纯函数；渲染与落盘在 `write()`）。

    返回 dict：`turns`（每轮的真值锚点）、`events`（通道 A）、`frames`（通道 C）、
    `marks`（操作者标记）、`truth`（注入的真值，用于判读结果自查）。
    """
    if scenario not in SCENARIOS:
        raise ValueError("未知场景 %r（有 %s）" % (scenario, "/".join(sorted(SCENARIOS))))
    p = SCENARIOS[scenario]
    rnd = random.Random(seed)
    events, frames, marks, turns = [], [], [], []
    t = BOOT_BASE_NS

    for i in range(p["turns"]):
        t_a0 = t
        t_a0p = t_a0 + int(p["a0_gap_ms"] * ec.NS_PER_MS)
        bubble = [t_a0p, t_a0p + 25_000_000, t_a0p + 55_000_000]
        t_a2 = bubble[-1] + int(p["ttft_ms"] * ec.NS_PER_MS)
        stream, cur = [t_a2], t_a2
        gaps = p["stream_gap_ms"]
        for k in range(p["stream_events"] - 1):
            # 逐轮轮转起点，保证每一轮都取到不同的 gap 组合，而**最大停顿必然出现**
            # （取 max 的那条边不能靠随机撞运气，否则场景的"真值"就不是写死的了）
            cur += int(gaps[(k + i) % len(gaps)] * ec.NS_PER_MS)
            stream.append(cur)
        stream[-1] = max(stream[-1], stream[0] + int(max(gaps) * ec.NS_PER_MS))
        # 把「最大停顿」显式放进每一轮：注入真值必须是确定的，不是抽样出来的
        stream = sorted(set(stream + [stream[-1] + int(max(gaps) * ec.NS_PER_MS)]))
        t_last = stream[-1]
        t_mark = t_last + int(MARK_LAG_MS * ec.NS_PER_MS)
        post = p["post_silence_ms"][i % len(p["post_silence_ms"])]

        for ts in bubble + stream:
            lag = rnd.uniform(*p["a_lag_ms"])
            events.append({"boot": ts, "lag_ms": lag})
            frames.append({"mono": ts - BOOT_MINUS_MONO_NS - int(lag * ec.NS_PER_MS),
                           "input_mono": (t_a0 - BOOT_MINUS_MONO_NS) if ts in bubble else 0})
        marks.append({"kind": es.KIND_ANSWER_COMPLETE, "boot": t_mark})
        turns.append({"idx": i, "t_a0_boot": t_a0, "t_a0p_boot": t_a0p,
                      "t_a2_boot": t_a2, "t_last_boot": t_last, "t_mark_boot": t_mark,
                      "max_intra_gap_ms": max(gaps),
                      "post_silence_ms": post})
        t = t_last + int(post * ec.NS_PER_MS)

    return {"scenario": scenario, "seed": seed, "params": p,
            "events": events, "frames": sorted(frames, key=lambda f: f["mono"]),
            "marks": marks, "turns": turns,
            "truth": {
                "a0_to_a0p_ms": p["a0_gap_ms"],
                "a_minus_c_ms_range": p["a_lag_ms"],
                "max_intra_gap_ms": max(p["stream_gap_ms"]),
                "min_post_silence_ms": min(p["post_silence_ms"]),
                "separable_by_construction":
                    max(p["stream_gap_ms"]) < min(p["post_silence_ms"]),
            }}


def _stim_log(off_ns, base_mono, n=6):
    L = ["%s I/E1_STIM( 100): CFG interval_ms=800 count=%d roi_px=480 warmup=1 "
         "refresh_hz=60.000 frame_ms=16.667 screen_px=1080x2340 boot_mono_offset_ns=%d"
         % (_wall(0), n, off_ns)]
    for seq in range(1, n + 1):
        mono = base_mono + seq * 800_000_000
        boot = mono + off_ns
        L.append("%s I/E1_STIM( 100): FLIP seq=%d color=A warmup=%s "
                 "t_req_boot_ns=%d t_req_mono_ns=%d"
                 % (_wall(0), seq, "true" if seq == 1 else "false", boot, mono))
        L.append("%s I/E1_STIM( 100): COMMIT seq=%d t_commit_boot_ns=%d t_commit_mono_ns=%d"
                 % (_wall(0), seq, boot + 5_000_000, mono + 5_000_000))
    return "\n".join(L) + "\n"


def _adapter_log(sim):
    rows = []
    for e in sim["events"]:
        rows.append((e["boot"], "%s I/AnebProbe( 5939): ADAPTER_EVT type=content "
                                "cls=android.widget.TextView desc=null txt_len=42 "
                                "pkg=%s t_boot_ns=%d"
                                % (_wall_of_boot(e["boot"]), SIM_PKG, e["boot"])))
    for i, m in enumerate(sim["marks"], start=1):
        rows.append((m["boot"], "%s I/AnebE4MARK( 6001): E4MARK kind=%s n=%d"
                     % (_wall_of_boot(m["boot"]), m["kind"], i)))
    # 两类干扰行：真实 logcat 里一定有，而判读侧必须自己滤掉。
    # ①别的包的内容事件（T14 §4.2：不按 pkg 过滤，别的 App 一条就能下结论）；
    # ②不带 t_boot_ns 的 click 行（e1 的 `parse_adapter_events` 只收带时戳的行）。
    first = sim["events"][0]["boot"]
    rows.append((first + 1, "%s I/AnebProbe( 5939): ADAPTER_EVT type=content "
                            "cls=X desc=null txt_len=3 pkg=com.android.launcher "
                            "t_boot_ns=%d" % (_wall_of_boot(first + 1), first + 1)))
    rows.append((first + 2, "%s I/AnebProbe( 5939): ADAPTER_EVT type=click cls=Y "
                            "desc=null txt_len=0 pkg=%s" % (_wall_of_boot(first + 2), SIM_PKG)))
    rows.sort(key=lambda r: r[0])
    return "\n".join(r[1] for r in rows) + "\n"


RING_DEPTH = 120       # gfxinfo / SurfaceFlinger 的环缓冲深度（量级；两者 120/128）
RING_STEP = 90         # 相邻两次 dump 的推进量 -> 必然重叠，判读侧必须去重


def _ring_chunks(frames):
    """把帧序列切成**相互重叠**的若干块，模拟周期性 dump 的真实产物。

    采集侧是边跑边追加的（环缓冲装不下一次会话），所以相邻 dump 一定重叠。
    模拟器如果只写一份不重叠的全量，就是又一次「夹具自造了生产者不写的形状」
    （D-309）—— 那样去重逻辑永远不会被走到。
    """
    if not frames:
        return []
    out, i = [], 0
    while i < len(frames):
        out.append(frames[i:i + RING_DEPTH])
        if i + RING_DEPTH >= len(frames):
            break
        i += RING_STEP
    return out


def _sf_latency(sim):
    blocks = []
    for chunk in _ring_chunks(sim["frames"]):
        L = [str(FRAME_NS)]
        for f in chunk:
            L.append("%d\t%d\t%d" % (f["mono"] - FRAME_NS, f["mono"],
                                     f["mono"] - 1_000_000))
        blocks.append("\n".join(L))
    return "\n".join(blocks) + "\n"


def _framestats(sim, variant):
    """真实形状：**每行末尾都有一个逗号**（归档语料如此），且**多块重叠**。"""
    head, ncol = (OLD_HEADER, 14) if variant == "old" else (NEW_HEADER, 23)
    blocks = []
    for chunk in _ring_chunks(sim["frames"]):
        rows = ["Stats since: 1ns", "---PROFILEDATA---", head]
        for f in chunk:
            vals = [0] * ncol
            if variant == "old":
                vals[1] = f["mono"] - FRAME_NS      # IntendedVsync
                vals[2] = f["mono"] - FRAME_NS      # Vsync
                vals[3] = f["input_mono"]           # OldestInputEvent
                vals[4] = f["input_mono"]           # NewestInputEvent
                vals[13] = f["mono"]                # FrameCompleted
            else:
                vals[2] = f["mono"] - FRAME_NS      # IntendedVsync
                vals[3] = f["mono"] - FRAME_NS      # Vsync
                vals[4] = 0 if not f["input_mono"] else 7  # InputEventId：id 不是时戳
                vals[16] = f["mono"]                # FrameCompleted
                vals[21] = f["mono"]                # DisplayPresentTime
            rows.append(",".join(str(v) for v in vals) + ",")
        blocks.append("\n".join(rows))
    return "\n".join(blocks) + "\n"


def _screencap_index(sim, period_ms=400):
    """通道 B：宿主时钟 + ROI 均值。

    **宿主时钟与设备钟之间没有任何标定**（采集侧写的是 `time.time_ns()`）。
    这不是模拟器偷懒，是采集侧的实况；判读侧因此不许拿 B 的时戳做时序比较，
    只许报采样周期与检出次数 —— 与 e1 对通道 B 的既有裁断同一条（spec §2.2）。
    """
    out, t = [], BOOT_BASE_NS
    end = sim["events"][-1]["boot"] + 2_000_000_000
    streaming = [(tn["t_a2_boot"], tn["t_last_boot"]) for tn in sim["turns"]]
    k = 0
    while t < end:
        active = any(a <= t <= b for a, b in streaming)
        mean = 128.0 + (18.0 if (active and k % 2 == 0) else 0.0)
        out.append({"t_host_ns": HOST_BASE_NS + (t - BOOT_BASE_NS),
                    "roi_mean": round(mean, 3), "path": None})
        t += period_ms * 1_000_000
        k += 1
    return "\n".join(json.dumps(r) for r in out) + "\n"


def write(out_dir, scenario, seed=20260802):
    sim = build(scenario, seed)
    p = sim["params"]
    # 第一个落盘动作就是 RUN_KIND（写盘前先断言目录名，D-270/D-306）。
    ec.write_run_kind(out_dir, ec.KIND_DRY_RUN, {
        "generator": "tools/e234/sim_session.py",
        "scenario": scenario, "seed": seed,
        "purpose": p["purpose"],
        "injected_truth": sim["truth"],
        "params": {k: v for k, v in p.items() if k != "purpose"},
        "spec": "spec/adapters/INSTRUMENTATION_SPEC.md §3.3",
        "warning": ec.DRY_RUN_BANNER,
    })
    files = {
        "stim_pre.log": _stim_log(BOOT_MINUS_MONO_NS, MONO_BASE_NS - 10_000_000_000),
        "stim_post.log": _stim_log(BOOT_MINUS_MONO_NS,
                                   MONO_BASE_NS + (sim["events"][-1]["boot"]
                                                   - BOOT_BASE_NS) + 1_000_000_000),
        "adapter.log": _adapter_log(sim),
        "sf_latency.txt": _sf_latency(sim),
        "framestats.txt": _framestats(sim, p["framestats"]),
        "screencap_index.jsonl": _screencap_index(sim),
        "collect_notes.json": json.dumps(
            {"pkg": SIM_PKG, "layer": "%s/%s.ChatActivity#0" % (SIM_PKG, SIM_PKG),
             "marks": len(sim["marks"]), "simulated": True},
            ensure_ascii=False, indent=2),
        "truth.json": json.dumps(sim["truth"], ensure_ascii=False, indent=2),
    }
    for name, body in files.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            fh.write(body)
    return sim


def main(argv=None):
    e1_io.pin_console_utf8()   # D-648③：重定向落盘时别退回 GBK（中文键名是分流信号）
    ap = argparse.ArgumentParser(description="E2/E3/E4 会话模拟器（dry-run 专用）")
    ap.add_argument("--scenario", required=True, choices=sorted(SCENARIOS))
    ap.add_argument("--out", required=True, help="产出目录（名字必须带 dryrun）")
    ap.add_argument("--seed", type=int, default=20260802)
    args = ap.parse_args(argv)
    try:
        sim = write(args.out, args.scenario, args.seed)
    except RuntimeError as e:
        sys.stderr.write("%s\n" % e)
        return 2
    sys.stdout.write("simulated %s -> %s\n注入真值: %s\n"
                     % (args.scenario, args.out,
                        json.dumps(sim["truth"], ensure_ascii=False)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
