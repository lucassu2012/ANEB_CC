#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E1 三通道采集 —— 驱动刺激源、同时收 A/B/C 三条通道的原始产物。

出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §2（通道定义）与 §3.3 E1（实验设计）。
判读见同目录 `e1_analyze.py`。

## 设备红线写进代码，不只写进文档

任务板纪律是「全程不碰 P40」。文档里的纪律靠人记得，代码里的拒绝不靠。本脚本：

1. `--serial` **必填**——没有"自动挑一台"的路径。宿主上同时挂着 P40 与模拟器时，
   自动挑选就是一次抛硬币，而抛错的代价是顶掉别人正在跑的设备批。
2. 默认**只允许 `emulator-*` 序列号**。真机需显式 `--allow-real-device`。
3. 无论有没有 `--allow-real-device`，型号命中 `DENY_MODELS` 一律**硬拒绝**——
   P40 Pro（ELS-*）在列。这一条不可用旗标绕过。

判定逻辑抽成纯函数 `device_allowed()`，由 `tests/test_e1_collect_guard.py` 反例钉死：
守卫要有能证伪它的反例，不然它只是一段看起来在守的代码。

## 三条通道各收什么

- **A**：`adb logcat` 里 `AnebProbe` 标签的行（`ADAPTER_EVT` / `ADAPTER_OBS`）。
  注意今天没有逐事件时戳——见 `e1_analyze.py` 模块注释「通道 A 现状」。
- **B**：定周期 `adb exec-out screencap`（**raw 非 png**：raw 头部自带宽高，可直接算
  ROI 均值，免去在无第三方库的环境里解 PNG），只落**均值标量**与宿主时戳，
  **不落原始帧**（spec §2.2 红线：截屏可能含对话原文）。
- **C**：`dumpsys SurfaceFlinger --latency <layer>` 与 `dumpsys gfxinfo <pkg> framestats`。
"""
import argparse
import json
import os
import re
import struct
import subprocess
import sys
import threading
import time

# ── 设备守卫 ──────────────────────────────────────────────────────────────
# P40 Pro 的 ro.product.model。ELS = 该机型代号；列出已知变体而非做前缀匹配，
# 前缀匹配会把无关机型也拦下来——守卫误拦和守卫漏拦一样会让人绕开它。
DENY_MODELS = ("ELS-AN00", "ELS-NX9", "ELS-N04", "ELS-TN00")
DENY_REASON = "P40 Pro 归设备批（任务板 T1/T2）独占，E1 装置一律不得连它"

EMULATOR_SERIAL_RE = re.compile(r"^emulator-\d+$")


def _norm_model(model):
    """型号归一：大写、去空白，并把下划线与连字符视为同一个字符。

    同一台 P40 在两处的写法**不一样**：`getprop ro.product.model` 给
    `ELS-AN00`，而 `adb devices -l` 的 `model:` 字段给 `ELS_AN00`
    （adb 在那一栏把非字母数字换成下划线）。denylist 只写一种形态，
    就会在另一条读取路径上整条失效——而失效时它不报错，只是安静地放行。
    """
    return (model or "").strip().upper().replace("_", "-")


def device_allowed(serial, model, allow_real_device):
    """(serial, model, allow_real_device) -> (bool, reason)。纯函数，无 IO。

    次序要紧：**先查型号 denylist**，再查模拟器规则。反过来的话，
    `--allow-real-device` 会先把 P40 放行到下一关，而下一关不认型号。
    """
    if not serial:
        return False, "未指定 --serial：本脚本没有自动挑设备的路径"
    norm = _norm_model(model)
    if not norm:
        # fail-closed（T14 交叉审查，D-392 ①）：`Adb.text` 不看 returncode，设备
        # offline / unauthorized 时 adb 把错误写 stderr、exit 非零、stdout 为空且
        # **不抛异常**，于是 model 是空串。旧版这里是 `if norm and ...`，空串把整条
        # denylist 短路跳过，随后落到下面那句**断言型号已被检查过**的放行理由上——
        # 守卫放行一台型号未知的设备，还打印一句假话给操作者。未知不等于安全。
        return False, "型号未知（getprop 读回空串）：denylist 无从判定，拒绝在型号未知的设备上运行"
    if any(norm == _norm_model(m) for m in DENY_MODELS):
        return False, "%s（型号 %s 在 DENY_MODELS）" % (DENY_REASON, model.strip())
    if EMULATOR_SERIAL_RE.match(serial):
        return True, "模拟器序列号"
    if allow_real_device:
        return True, "真机，已显式 --allow-real-device 且型号不在 denylist"
    return False, "非模拟器序列号 %s；真机需显式 --allow-real-device" % serial


# ── screencap raw 解析 ────────────────────────────────────────────────────
def roi_mean_from_raw(buf, x, y, w, h):
    """screencap raw（RGBA_8888）-> ROI 灰度均值（0-255）。无 ROI 交集 -> None。

    头部有 3 字段（w,h,format）与 4 字段（+colorSpace）两种历史形态。
    **按数据长度自检而不是按 Android 版本猜**：猜版本会在某台设备上静默错位，
    而错位后的均值仍是个像样的数字。
    """
    if len(buf) < 12:
        return None
    width, height, _fmt = struct.unpack_from("<III", buf, 0)
    if width <= 0 or height <= 0:
        return None
    need = width * height * 4
    off = None
    for header in (12, 16):
        if len(buf) - header == need:
            off = header
            break
    if off is None:
        return None
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(width, x + w), min(height, y + h)
    if x1 <= x0 or y1 <= y0:
        return None
    total, count = 0, 0
    for row in range(y0, y1):
        base = off + (row * width + x0) * 4
        for col in range(x1 - x0):
            p = base + col * 4
            total += buf[p] + buf[p + 1] + buf[p + 2]
            count += 1
    return (total / (count * 3.0)) if count else None


# ── adb 薄封装 ────────────────────────────────────────────────────────────
class Adb(object):
    """每条命令都带 -s <serial>。没有不带 serial 的路径——那是顶掉别人设备的入口。"""

    def __init__(self, serial):
        self.serial = serial

    def _argv(self, args):
        return ["adb", "-s", self.serial] + list(args)

    def text(self, *args, **kw):
        p = subprocess.run(self._argv(args), capture_output=True,
                           timeout=kw.get("timeout", 30))
        return p.stdout.decode("utf-8", "replace")

    def raw(self, *args, **kw):
        p = subprocess.run(self._argv(args), capture_output=True,
                           timeout=kw.get("timeout", 30))
        return p.stdout

    def popen(self, *args):
        return subprocess.Popen(self._argv(args), stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)


# 一个包会在 SurfaceFlinger 里挂出好几层，其中只有一层是真正出画面的。
# 首版取"最后一条含包名的行"，模拟器 dry-run 实测选中了 ActivityRecordInputSink
# ——那是输入接收层，永远没有帧。**选错层不会报错**：`--latency` 会安安静静返回
# 一份空表，而空表与"这层没出帧"长得一模一样。故噪声层要按名字明确排除。
LAYER_NOISE = ("ActivityRecordInputSink", "Splash Screen", "animation-leash",
               "starting_reveal", "ActivityRecord{", "Wallpaper", "Task=",
               "InputMethod", "Dim Layer", "SurfaceView")
_LAYER_RE = re.compile(r"RequestedLayerState\{(?P<body>.+?)(?:\s+parentId=|\}\s*$)")
_LEADING_HEX_RE = re.compile(r"^[0-9a-f]{6,10}\s+")


def pick_layer(list_output, package):
    """`dumpsys SurfaceFlinger --list` 文本 -> 该包出画面的图层名（含 `#id`）。纯函数。

    选不出就返回 None 让上层记 NOT_EXECUTED —— **不猜一个名字去 dump**。
    """
    cands = []
    for raw in (list_output or "").splitlines():
        line = raw.strip()
        if package not in line:
            continue
        m = _LAYER_RE.search(line)
        body = (m.group("body") if m else line).strip()
        body = _LEADING_HEX_RE.sub("", body).strip()   # 去掉行首的句柄十六进制
        if not body or "#" not in body:
            continue
        if any(n in body for n in LAYER_NOISE):
            continue
        cands.append(body)
    if not cands:
        return None
    # 应用自己的画面层名形如 `<pkg>/<pkg>.<Activity>#<id>`；优先取这一形态，
    # 并在同形态里取最后一个（层级最深的那个子层才是实际提交帧的那层）。
    own = [c for c in cands if c.startswith(package + "/")]
    return (own or cands)[-1]


def find_layer_name(adb, package):
    """薄封装：拉 --list 再交给纯函数 `pick_layer` 判定（判定逻辑要能被反例钉住）。"""
    return pick_layer(adb.text("shell", "dumpsys", "SurfaceFlinger", "--list"), package)


# ── 采集主流程 ────────────────────────────────────────────────────────────
STIM_PKG = "com.aneb.e1stimulus"
STIM_ACT = "com.aneb.e1stimulus/.StimulusActivity"

# 通道 A 的 logcat 标签。**必须与生产者逐字相等**：`logcat -s <tag>:I` 是排他过滤，
# 写错一个字母就是**零行**，而零行与「探针没打时戳」在下游长得一模一样。
# 首版写的是 `"AnebAdapter"`，而 `AnebAccessibilityService.kt` 的 `TAG` 是
# `"AnebProbe"`——两次 dry-run 的 `adapter.log` 都是 0 字节，报告却把责任归给 :probe
# （T14 交叉审查，D-392 ②）。`test_adapter_tag_equals_the_producers_tag` 从 .kt 源码
# 正则取出 TAG 与本常量对账，改名再发生一次会当场变红。
DEFAULT_ADAPTER_TAG = "AnebProbe"


def collect(adb, out_dir, interval_ms, count, roi_px, warmup, screencap_period_ms,
            adapter_tag=DEFAULT_ADAPTER_TAG):
    os.makedirs(out_dir, exist_ok=True)
    notes = {}

    adb.text("logcat", "-c", timeout=20)

    stim_fh = open(os.path.join(out_dir, "stim.log"), "wb")
    adapter_fh = open(os.path.join(out_dir, "adapter.log"), "wb")
    procs = [
        (adb.popen("logcat", "-v", "time", "-s", "E1_STIM:I"), stim_fh),
        (adb.popen("logcat", "-v", "time", "-s", "%s:I" % adapter_tag), adapter_fh),
    ]
    pumps = []
    for proc, fh in procs:
        t = threading.Thread(target=_pump, args=(proc, fh), daemon=True)
        t.start()
        pumps.append(t)

    adb.text("shell", "am", "force-stop", STIM_PKG, timeout=20)
    adb.text("shell", "am", "start", "-n", STIM_ACT,
             "--ei", "interval_ms", str(interval_ms),
             "--ei", "count", str(count),
             "--ei", "roi_px", str(roi_px),
             "--ei", "warmup", str(warmup), timeout=30)

    duration_s = (interval_ms * (count + 2)) / 1000.0
    idx_path = os.path.join(out_dir, "screencap_index.jsonl")
    notes["screencap_samples"] = _sample_screencaps(
        adb, idx_path, roi_px, screencap_period_ms, duration_s)

    layer = find_layer_name(adb, STIM_PKG)
    notes["layer"] = layer
    sf_text = adb.text("shell", "dumpsys", "SurfaceFlinger", "--latency", layer) if layer else ""
    _write(os.path.join(out_dir, "sf_latency.txt"), sf_text)
    if not layer:
        notes["sf_status"] = "NOT_EXECUTED: 未在 SurfaceFlinger --list 找到该包的图层"

    fs_text = adb.text("shell", "dumpsys", "gfxinfo", STIM_PKG, "framestats", timeout=45)
    _write(os.path.join(out_dir, "framestats.txt"), fs_text)

    time.sleep(1.0)
    for proc, _fh in procs:
        proc.terminate()
    for t in pumps:
        t.join(timeout=5)
    for _proc, fh in procs:
        fh.close()

    # 清场：停掉本次启动的刺激源。启动了什么就停什么，是仓根 CLAUDE.md 的设备纪律，
    # 模拟器上同样照办（纪律不因设备便宜而打折）。
    adb.text("shell", "am", "force-stop", STIM_PKG, timeout=20)

    _write(os.path.join(out_dir, "collect_notes.json"),
           json.dumps(notes, ensure_ascii=False, indent=2))
    return notes


def _pump(proc, fh):
    try:
        for chunk in iter(lambda: proc.stdout.read(4096), b""):
            fh.write(chunk)
            fh.flush()
    except Exception:
        pass  # 采集端断流不该把整次运行拖垮；缺行由判读侧记 dropped


def _sample_screencaps(adb, idx_path, roi_px, period_ms, duration_s):
    n, t_end = 0, time.time() + duration_s
    with open(idx_path, "w", encoding="utf-8") as fh:
        while time.time() < t_end:
            t0 = time.time_ns()
            try:
                buf = adb.raw("exec-out", "screencap", timeout=20)
            except subprocess.TimeoutExpired:
                continue
            mean = roi_mean_from_raw(buf, 0, 0, roi_px, roi_px)
            if mean is None:
                continue
            # 只落均值标量与时戳，**不落原始帧**（spec §2.2 红线）。
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
    ap = argparse.ArgumentParser(description="E1 三通道采集（设备守卫内建）")
    ap.add_argument("--serial", required=True,
                    help="adb 序列号。必填：本脚本没有自动挑设备的路径")
    ap.add_argument("--allow-real-device", action="store_true",
                    help="允许非模拟器设备（型号 denylist 仍然硬拒绝，此旗标绕不过）")
    ap.add_argument("--out", default=None, help="产出目录（默认 evidence/e1/<时间戳>）")
    ap.add_argument("--interval-ms", type=int, default=2000)
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--roi-px", type=int, default=480)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--screencap-period-ms", type=int, default=300)
    args = ap.parse_args(argv)

    adb = Adb(args.serial)
    try:
        model = adb.text("shell", "getprop", "ro.product.model", timeout=15).strip()
    except Exception as e:
        sys.stderr.write("无法读取设备型号（%s）：拒绝在型号未知的设备上运行\n"
                         % e.__class__.__name__)
        return 2

    ok, reason = device_allowed(args.serial, model, args.allow_real_device)
    sys.stdout.write("device: serial=%s model=%s -> %s (%s)\n"
                     % (args.serial, model or "?", "ALLOW" if ok else "REFUSE", reason))
    if not ok:
        return 3

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out = args.out or os.path.join(root, "evidence", "e1",
                                   time.strftime("%Y%m%d-%H%M%S"))
    notes = collect(adb, out, args.interval_ms, args.count, args.roi_px, args.warmup,
                    args.screencap_period_ms)
    sys.stdout.write("collected -> %s\n%s\n"
                     % (out, json.dumps(notes, ensure_ascii=False)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
