#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2/E3/E4 同轨采集 —— 一次会话录轨，三个实验共用。

出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §3.3。该节的依赖序图逐字写着
「E4（可与 E3 并行，**共用同一批会话录轨**）」，E2 又与它们同为「一次真实会话
同时开三条通道」。所以采集侧只有**一只脚本**，判读侧才分三只 —— 一次设备窗
最贵的是会话本身，不是解析。

## 一次采集做四件事（顺序不可换）

1. **钉桩·前**：跑一小段 E1 刺激源，拿到 BOOTTIME↔MONOTONIC 偏移（`stim_pre.log`）。
2. **会话录轨**：操作者把目标 App 切到前台真人对话；本脚本同时收
   - 通道 A：`logcat -s AnebProbe:I AnebE4MARK:I`（`ADAPTER_EVT ... t_boot_ns=`）
   - 通道 B：定周期 `screencap` 的 ROI 均值（**只落标量**，spec §2.2 红线）
   - 操作者标记：每敲一次键，往**设备自己的 logcat** 里打一行 `E4MARK`
3. **钉桩·后**：再跑一段刺激源（`stim_post.log`）。两次之差 = 会话跨度内的时钟漂移。
4. **通道 C 快照**：`dumpsys SurfaceFlinger --latency <layer>` + `gfxinfo framestats`。

## 设备门：本脚本**不替谁解除 P40 红线**

`e1_collect.device_allowed()` 对 P40 一族是硬拒绝（`DENY_REASON` 逐字：
「P40 Pro 归设备批（任务板 T1/T2）独占」）。而 spec §3.3 又逐条写着 E2/E3/E4
的资源就是「P40 + 已装 App + 少量额度，**需排窗**」。两者不矛盾 —— 缺的是
一次**排窗授权**，而授权不是一个脚本能自己给自己发的。

于是这里的做法是：型号被 denylist 拒时，必须显式给 `--device-window <ID>`，
且**该 ID 必须能在 `docs/BRAIN_TASKBOARD.md` 里找到**。授权得存在于那块
大家都看得见的板子上，不能只存在于操作者的记忆里 —— 一个能被现场编出来的
字符串不是授权。是否接受这个解锁形状，属大脑裁定（见 README「待裁」）。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import e234_common as ec        # noqa: E402
import e234_session as es       # noqa: E402

sys.path.insert(0, os.path.join(ec.REPO_ROOT, "tools", "e1"))
import e1_collect as e1c        # noqa: E402

TASKBOARD = os.path.join(ec.REPO_ROOT, "docs", "BRAIN_TASKBOARD.md")


# ── 设备门 ────────────────────────────────────────────────────────────────
def device_gate(serial, model, allow_real_device, device_window, taskboard_text):
    """(ok, reason)。纯函数，无 IO —— 判定要能被反例钉住（同 e1 的 `device_allowed`）。

    先走 `e1_collect.device_allowed()`：型号未知 fail-closed、模拟器规则、
    denylist 次序三件事一件不重复实现（那是 D-392① 修过的地方，重实现就是重犯）。
    只有当它因为 **denylist** 拒绝时，本函数才去看排窗授权。
    """
    ok, reason = e1c.device_allowed(serial, model, allow_real_device)
    if ok:
        return True, reason
    if "DENY_MODELS" not in reason:
        return False, reason          # 型号未知 / 非模拟器无旗标 —— 与排窗无关，照拒
    if not device_window:
        return False, ("%s；E2–E4 确实需要这台设备（spec §3.3 资源栏），"
                       "但解除它要一次排窗授权：请给 --device-window <任务板上的窗 ID>"
                       % reason)
    if not taskboard_text:
        return False, "读不到任务板：无从核对 --device-window，拒绝在无授权凭据下连真机"
    if device_window not in taskboard_text:
        return False, ("--device-window %r 在 docs/BRAIN_TASKBOARD.md 里查无此项："
                       "授权要存在于板上，不是存在于操作者记忆里" % device_window)
    return True, "型号在 denylist，但排窗授权 %s 已在任务板上核到" % device_window


def read_taskboard():
    if not os.path.exists(TASKBOARD):
        return ""
    with open(TASKBOARD, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


# ── 参数解析（打错不许以栈回溯收场，D-272/D-306）──────────────────────────
_ROI_RE = re.compile(r"^\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*$")


def parse_roi(text):
    """`x,y,w,h` -> (x, y, w, h)。打错 -> ValueError 带人话，**不是** 栈回溯。

    刻意**没有默认值**：ROI 是「响应区在这台设备这个 App 上的位置」，
    它是一次实测，猜一个坐标出来会让通道 B 安静地测一块空白（选错层不报错
    那件事的同款形状，e1 README §4 第 2 条）。
    """
    m = _ROI_RE.match(text or "")
    if not m:
        raise ValueError("ROI 要写成 `x,y,w,h` 四个非负整数（收到 %r）" % text)
    x, y, w, h = (int(g) for g in m.groups())
    if w <= 0 or h <= 0:
        raise ValueError("ROI 的宽高必须为正（收到 w=%d h=%d）" % (w, h))
    return x, y, w, h


MARK_KEYS = {"a": es.KIND_ANSWER_COMPLETE, "s": es.KIND_ANSWER_START,
             "t": es.KIND_TURN_START}


def mark_payload(kind, n):
    """打进设备 logcat 的那一行。**格式由判读侧的 `_MARK_RE` 决定，不是我起的名字**。

    这是 D-276 的反面用法：先看消费方要什么，再决定生产者写什么。
    `e234_session.parse_marks()` 认的就是 `E4MARK kind=<kind> n=<n>`。
    """
    if kind not in es.MARK_KINDS:
        raise ValueError("未知标记类型 %r（只有 %s）" % (kind, "/".join(es.MARK_KINDS)))
    return "E4MARK kind=%s n=%d" % (kind, n)


# ── 采集 ──────────────────────────────────────────────────────────────────
def _pin(adb, out_dir, tag, flips, interval_ms):
    """跑一小段 E1 刺激源，只留它的 logcat（不采 ROI、不 dump 帧）。

    刺激源是**我们自己的 App**：不联网、不申请权限、不碰目标 App 的额度或账号
    （`tools/e1/README.md` §0）。它在这里唯一的职责是把两个时钟同帧打出来。
    """
    path = os.path.join(out_dir, "stim_%s.log" % tag)
    adb.text("logcat", "-c", timeout=20)
    fh = open(path, "wb")
    proc = adb.popen("logcat", "-v", "time", "-s", "E1_STIM:I")
    t = threading.Thread(target=e1c._pump, args=(proc, fh), daemon=True)
    t.start()
    adb.text("shell", "am", "force-stop", e1c.STIM_PKG, timeout=20)
    adb.text("shell", "am", "start", "-n", e1c.STIM_ACT,
             "--ei", "interval_ms", str(interval_ms),
             "--ei", "count", str(flips),
             "--ei", "roi_px", "480",
             "--ei", "warmup", "1", timeout=30)
    time.sleep((interval_ms * (flips + 2)) / 1000.0)
    adb.text("shell", "am", "force-stop", e1c.STIM_PKG, timeout=20)
    time.sleep(0.5)
    proc.terminate()
    t.join(timeout=5)
    fh.close()
    return path


class _MarkPump(object):
    """操作者标记：敲一个键 -> 往**设备**的 logcat 里打一行。

    为什么打进设备而不是记宿主时刻：宿主时钟与设备 BOOTTIME 之间隔着一次 adb
    往返，而这个往返**没人量过**。打进设备 logcat 后，标记与 `ADAPTER_EVT`
    落在同一条流里、共享同一份墙钟前缀，换算靠 `fit_wall_to_boot()` **量出来**
    的偏移（残差同时被报出来），一次假设都不用做。
    """

    def __init__(self, adb, log_path):
        self.adb, self.n, self.stop = adb, 0, False
        self.log = open(log_path, "a", encoding="utf-8")

    def loop(self):
        sys.stdout.write("标记键：a=回答完成  s=回答开始  t=本轮开始  q=结束采集\n")
        sys.stdout.flush()
        while not self.stop:
            line = sys.stdin.readline()
            if not line:
                return
            key = line.strip().lower()[:1]
            if key == "q":
                self.stop = True
                return
            kind = MARK_KEYS.get(key)
            if kind is None:
                continue
            self.n += 1
            t0 = time.time_ns()
            self.adb.text("shell", "log", "-p", "i", "-t", es.MARK_TAG,
                          mark_payload(kind, self.n), timeout=15)
            rtt_ms = (time.time_ns() - t0) / ec.NS_PER_MS
            # 往返耗时**落盘**：它就是这条标记的不确定度上界。
            # 一个没有不确定度的人工标记，读者没法判断它够不够格当真值。
            self.log.write(json.dumps(
                {"n": self.n, "kind": kind, "adb_rtt_ms": round(rtt_ms, 3)},
                ensure_ascii=False) + "\n")
            self.log.flush()
            sys.stdout.write("  mark #%d %s (adb 往返 %.1f ms)\n" % (self.n, kind, rtt_ms))
            sys.stdout.flush()


def collect(adb, out_dir, pkg, roi, screencap_period_ms, session_seconds,
            pin_flips, pin_interval_ms, interactive, device_window,
            framestats_period_s=20):
    ec.write_run_kind(out_dir, ec.KIND_DEVICE, {
        "experiments": ["E2", "E3", "E4"],
        "pkg": pkg, "roi": list(roi), "device_window": device_window,
        "serial": adb.serial,
        "spec": "spec/adapters/INSTRUMENTATION_SPEC.md §3.3",
    })
    notes = {"device_window": device_window, "pkg": pkg}

    notes["stim_pre"] = _pin(adb, out_dir, "pre", pin_flips, pin_interval_ms)

    adb.text("logcat", "-c", timeout=20)
    adapter_path = os.path.join(out_dir, "adapter.log")
    fh = open(adapter_path, "wb")
    proc = adb.popen("logcat", "-v", "time", "-s",
                     "AnebProbe:I", "%s:I" % es.MARK_TAG)
    pump = threading.Thread(target=e1c._pump, args=(proc, fh), daemon=True)
    pump.start()

    marker = None
    if interactive:
        marker = _MarkPump(adb, os.path.join(out_dir, "mark_rtt.jsonl"))
        threading.Thread(target=marker.loop, daemon=True).start()

    # 通道 C 必须**周期性**取：`framestats` 与 `--latency` 读的都是环形缓冲
    # （各约 120/128 帧）。一次真实会话的帧数远超环缓冲深度 —— 会话结束才 dump
    # 一次，拿到的只是最后十几秒。这与 logcat 环缓冲七分钟冲净是同一类问题
    # （任务板设备注意条），处置也一样：边跑边落盘。判读侧按帧时戳去重。
    layer = e1c.find_layer_name(adb, pkg)
    notes["layer"] = layer
    if not layer:
        # 「图层没找到」与「图层找到但零帧」必须分得开 —— e1 就是在这上面
        # 一度把环境边界误判成自己的 bug（README §4 第 2 条的连带后果）。
        notes["sf_status"] = "NOT_EXECUTED: SurfaceFlinger --list 未找到该包的图层"
    stop_c = {"stop": False}
    tc = threading.Thread(target=_dump_channel_c, daemon=True,
                          args=(adb, out_dir, pkg, layer, framestats_period_s, stop_c))
    tc.start()

    idx_path = os.path.join(out_dir, "screencap_index.jsonl")
    notes["screencap_samples"] = _sample_roi(
        adb, idx_path, roi, screencap_period_ms, session_seconds,
        stop_flag=(lambda: marker.stop) if marker else (lambda: False))
    if marker:
        marker.stop = True
        notes["marks"] = marker.n

    stop_c["stop"] = True
    tc.join(timeout=60)
    time.sleep(1.0)
    proc.terminate()
    pump.join(timeout=5)
    fh.close()

    notes["stim_post"] = _pin(adb, out_dir, "post", pin_flips, pin_interval_ms)

    _write(os.path.join(out_dir, "collect_notes.json"),
           json.dumps(notes, ensure_ascii=False, indent=2))
    return notes


def _dump_channel_c(adb, out_dir, pkg, layer, period_s, stop):
    """周期性追加通道 C 的两条支路。相邻 dump 必然重叠，去重是判读侧的事。"""
    sf_path = os.path.join(out_dir, "sf_latency.txt")
    fs_path = os.path.join(out_dir, "framestats.txt")
    while not stop["stop"]:
        if layer:
            _append(sf_path, adb.text("shell", "dumpsys", "SurfaceFlinger",
                                      "--latency", layer))
        _append(fs_path, adb.text("shell", "dumpsys", "gfxinfo", pkg,
                                  "framestats", timeout=45))
        for _ in range(int(max(1, period_s) * 4)):
            if stop["stop"]:
                return
            time.sleep(0.25)


def _append(path, text):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write((text or "") + "\n")


def _sample_roi(adb, idx_path, roi, period_ms, duration_s, stop_flag):
    """通道 B：只落 ROI 均值标量与宿主时戳，**绝不落原始帧**（spec §2.2 红线）。

    与 e1 的 `_sample_screencaps` 的唯一差别是 ROI 可以不从原点起（真实 App 的
    响应区在屏幕中段）。取帧与解析复用 `e1_collect.roi_mean_from_raw`。
    """
    x, y, w, h = roi
    n, t_end = 0, time.time() + duration_s
    with open(idx_path, "w", encoding="utf-8") as fh:
        while time.time() < t_end and not stop_flag():
            t0 = time.time_ns()
            try:
                buf = adb.raw("exec-out", "screencap", timeout=20)
            except subprocess.TimeoutExpired:
                continue
            mean = e1c.roi_mean_from_raw(buf, x, y, w, h)
            if mean is None:
                continue
            fh.write(json.dumps({"t_host_ns": t0, "roi_mean": round(mean, 3),
                                 "path": None}) + "\n")
            fh.flush()
            n += 1
            rest = (period_ms / 1000.0) - (time.time_ns() - t0) / 1e9
            if rest > 0:
                time.sleep(rest)
    return n


def _write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text or "")


def main(argv=None):
    ap = argparse.ArgumentParser(description="E2/E3/E4 同轨采集（一次会话，三实验共用）")
    ap.add_argument("--serial", required=True, help="adb 序列号；必填，无自动挑设备的路径")
    ap.add_argument("--pkg", required=True, help="目标 App 包名（com.larus.nova / com.deepseek.chat）")
    ap.add_argument("--roi", required=True, help="通道 B 的响应区 ROI：`x,y,w,h`（无默认值，见 parse_roi）")
    ap.add_argument("--allow-real-device", action="store_true")
    ap.add_argument("--device-window", default=None,
                    help="排窗授权 ID；型号命中 denylist 时必填，且须能在任务板上查到")
    ap.add_argument("--out", default=None)
    ap.add_argument("--screencap-period-ms", type=int, default=400)
    ap.add_argument("--session-seconds", type=int, default=600)
    ap.add_argument("--pin-flips", type=int, default=6)
    ap.add_argument("--pin-interval-ms", type=int, default=800)
    ap.add_argument("--framestats-period-s", type=int, default=20,
                    help="通道 C 的取样周期；环缓冲约 120 帧，取得太稀就丢帧")
    ap.add_argument("--no-marks", action="store_true",
                    help="不收操作者标记（那时整段=一轮，E4 结构上判不了，判读侧会说）")
    args = ap.parse_args(argv)

    try:
        roi = parse_roi(args.roi)
    except ValueError as e:
        sys.stderr.write("--roi 有误：%s\n" % e)
        return 2

    adb = e1c.Adb(args.serial)
    try:
        model = adb.text("shell", "getprop", "ro.product.model", timeout=15).strip()
    except Exception as e:
        sys.stderr.write("无法读取设备型号（%s）：拒绝在型号未知的设备上运行\n"
                         % e.__class__.__name__)
        return 2

    ok, reason = device_gate(args.serial, model, args.allow_real_device,
                             args.device_window, read_taskboard())
    sys.stdout.write("device: serial=%s model=%s -> %s (%s)\n"
                     % (args.serial, model or "?", "ALLOW" if ok else "REFUSE", reason))
    if not ok:
        return 3

    out = args.out or os.path.join(ec.REPO_ROOT, "evidence", "e234",
                                   time.strftime("%Y%m%d-%H%M%S"))
    try:
        ec.assert_isolation_before_write(out, ec.KIND_DEVICE)
    except RuntimeError as e:
        sys.stderr.write("%s\n" % e)
        return 2

    notes = collect(adb, out, args.pkg, roi, args.screencap_period_ms,
                    args.session_seconds, args.pin_flips, args.pin_interval_ms,
                    not args.no_marks, args.device_window, args.framestats_period_s)
    sys.stdout.write("collected -> %s\n%s\n"
                     % (out, json.dumps(notes, ensure_ascii=False)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
