#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2 判读 —— 三通道同轨对拍：同一个锚点 A2，各通道给出的时刻两两求差。

出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §3.3 E2 逐字：
「同一次真实会话，同时开通道 A / B / C，记录同一锚点（A2）的三个时刻，两两求差」；
判据「`|t_A − t_C|` 的 p99 即通道 A 相对呈现口径的锚定偏差估计。
若该值 > 1 帧 → **通道 A 单独不足以支撑 M3 门**（须以 C 为主判据，A 降为交叉验证）」。

## 「三个时刻」今天只拿得到两个 —— 这件事必须先说

通道 B 的时戳是**宿主侧**的（`screencap` 返回时刻，采集侧写 `time.time_ns()`），
它与设备时钟之间隔着一次 adb 往返，而**这个往返从没被标定过**。
e1 已经就此下过裁断：通道 B **不报时间误差**，只报采样周期与检出次数（spec §2.2）。
本脚本沿用同一条，不为了凑满「三个时刻」而把 B 的宿主时戳当设备时刻用 ——
那会得到一个看起来合理的错数，而这正是本仓反复付学费的那种错。

**所以 E2 今天产出的是两通道对拍 + 通道 B 的一条佐证（检出/未检出），
不是三通道对拍。** 这不是本脚本的缺陷，是采集面的边界；补它需要一次
宿主↔设备的时钟标定，属新增工作，本轮不发明。

## A 与 C 的锚点各自独立算，不许互相看

- 通道 A 的 A2 = v3 簇分割的**次簇首事件**（D-52；门限从 `ObsStats.kt` 取）。
- 通道 C 的 A2 = 把**同一条簇分割判据**施加在帧的 `actualPresentTime` 序列上，
  取次簇首帧。

用「commit 之后最近的一帧」去定通道 C 的 A2 是循环论证：那样算出来的差恒非负、
且恒小于一帧，门必然 PASS。两侧各自独立分簇，差值才有信息 —— 它的**符号也有信息**
（spec §2.1 逐字：事件「不保证像素已上屏，可能早于或晚于呈现」，连符号都未知）。
故本脚本**同时**报有符号分布与绝对值分布：门判绝对值（判据原文是 `|t_A − t_C|`），
符号单独印出来，免得重蹈 e1 那条单边门的覆辙（T14 §2.1③：通道 A 的期望方向就是负，
而 `p99 <= frame_ms` 让同一个 500ms 滞后在 C 报 FAIL、在 A 报 PASS）。
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import e234_common as ec    # noqa: E402
import e234_session as es   # noqa: E402
import e1_io                    # noqa: E402  (D-648③ 输出编码自锁)


def analyze(run_dir, pkg):
    run_kind = ec.read_run_kind(run_dir).get("kind")
    lines = ec.read_lines(run_dir, "adapter.log")
    evts, dropped_pkg, dropped_dim = es.content_events(lines, pkg)
    fit = ec.fit_wall_to_boot(lines)
    marks = es.parse_marks(lines, fit)
    turns, turn_method = es.segment_turns(evts, marks)

    pin = ec.clock_pin(ec.read_lines(run_dir, "stim_pre.log"),
                       ec.read_lines(run_dir, "stim_post.log"), None)
    period_ns, frames = ec.ea.parse_sf_latency(ec.read_text(run_dir, "sf_latency.txt"))
    # 采集侧是周期性追加的（环缓冲装不下一次会话），相邻 dump 必然重叠。
    # 不去重就是把同一帧数两次 —— T14 §2.1③ 那个形状换了个入口。
    frames, dup_frames = ec.dedupe_by(frames, "actual_ns")
    frame_ms = (period_ns / ec.NS_PER_MS) if period_ns else pin.get("frame_ms")

    res = {
        "experiment": "E2", "run_dir": run_dir, "pkg": pkg,
        "dry_run": run_kind == ec.KIND_DRY_RUN, "run_kind": run_kind,
        "spec": "INSTRUMENTATION_SPEC.md §3.3 E2 / §3.4 G-3",
        "events_used": len(evts), "events_other_pkg": dropped_pkg,
        "events_bad_dimension": dropped_dim,
        "wall_to_boot": fit, "clock_pin": pin, "turn_method": turn_method,
        "turns_total": len(turns), "frames_total": len(frames),
        "frames_duplicate_dropped": dup_frames, "frame_ms": frame_ms,
        "channel_b": ec.ea.screencap_sampling_stats(
            ec.ea.parse_screencap_index(ec.read_jsonl(run_dir, "screencap_index.jsonl")),
            8.0),
        "per_turn": [], "drop_reasons": {},
    }

    gap = ec.cluster_gap_nanos()
    if pin.get("status") != ec.PASS:
        res["channel_a_vs_c"] = {"status": ec.NOT_EXECUTED, "n": 0,
                                 "reason": "时钟钉桩不可用：%s" % pin.get("reason")}
        res["verdict"] = (ec.NOT_EXECUTED, "跨基比较缺时钟钉桩")
        return res

    signed, drops = [], {}

    def _drop(why):
        drops[why] = drops.get(why, 0) + 1

    for t in turns:
        ts = [e["t_boot_ns"] for e in t["events"]]
        _a0p, a2_boot, cl_a = ec.v3_anchors(ts, gap)
        lo_mono = ec.boot_to_mono_ns(t["t_start_ns"], pin)
        hi_mono = ec.boot_to_mono_ns(t["t_end_ns"], pin)
        fr = es.frames_in(frames, lo_mono, hi_mono)
        _a0p_c, a2_mono, cl_c = ec.v3_anchors([f["actual_ns"] for f in fr], gap)
        row = {"turn": t["idx"], "a_clusters": len(cl_a), "c_clusters": len(cl_c),
               "frames": len(fr)}
        if a2_boot is None:
            _drop("通道 A 该轮不足两簇（A2 无判据）")
        elif a2_mono is None:
            _drop("通道 C 该轮不足两簇（帧序列未分出思考静默）")
        else:
            d = (ec.boot_to_mono_ns(a2_boot, pin) - a2_mono) / ec.NS_PER_MS
            signed.append(d)
            row["delta_ms"] = d
        res["per_turn"].append(row)

    res["drop_reasons"] = drops
    dropped = sum(drops.values())
    res["signed"] = ec.summarize(signed, dropped=dropped)
    res["channel_a_vs_c"] = ec.summarize([abs(d) for d in signed], dropped=dropped)
    v, why = ec.ea.gate_verdict(res["channel_a_vs_c"], frame_ms)
    res["verdict"] = (v, why)
    # T14 待裁 C-2 的**一半已解**（2026-08-29 订正，原注释写于 W-4 之前）：
    # `gate_verdict` **现在设了最小 n**（`e1_analyze.GATE_MIN_N`，W-4/A 行），
    # n < 5 直接返回 NOT_EXECUTED——本脚本经 `ec.ea.gate_verdict` 调它，
    # 所以**这道门对本脚本生效**。⚠ 该事实在 `tools/e234/` 里 grep `GATE_MIN_N`
    # 或 `min_n` **一个都搜不到**（跨模块经别名调用，名字不出现在本目录）——
    # 2026-08-29 已有人据此零命中判「e234 侧无 n 门限」，与实测相反。
    # 仍未解的那一半：**dropped 依旧不参与判定**（只被印出来）。
    # 门限定在哪属口径决定，不由本脚本发明；能做的是把数**印在判定旁边**。
    res["gate_caveat"] = ("该判定**已设**最小 n（e1_analyze.GATE_MIN_N，n 不足即 "
                          "NOT_EXECUTED），但**不看 dropped**（T14 C-2 余半）；"
                          "本次 n=%s dropped=%s" % (res["channel_a_vs_c"].get("n"), dropped))
    return res


def _f(v, nd=3):
    if v is None:
        return "—"
    return ("%.*f" % (nd, v)) if isinstance(v, float) else str(v)


def render_markdown(res):
    L = ["# E2 三通道同轨对拍 —— 判读结果", ""]
    L += ["> %s" % b for b in ec.banner_lines(res["run_kind"])]
    if ec.banner_lines(res["run_kind"]):
        L.append("")
    L += ["> 出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §3.3 E2、§3.4 G-3。",
          "> 状态词只用 PASS / FAIL / NOT_EXECUTED。空样本一律 NOT_EXECUTED，不折 0。", ""]
    L += ["## 0. 这一份为什么只有两个时刻", "",
          "spec §3.3 E2 说的是「三个时刻」。通道 B 的时戳是**宿主侧**的，与设备时钟之间",
          "隔着一次**从未标定过**的 adb 往返，故本脚本不拿它做时序比较（沿用 spec §2.2 与",
          "e1 的既有裁断）。B 在这一页只出一条佐证：它有没有看见这些翻转、采样周期多大。", ""]
    L += ["## 1. 前提", "", "| 项 | 值 |", "|---|---|",
          "| 目标包 | `%s` |" % res["pkg"],
          "| 可用内容事件 / 他包滤除 / 量纲拒收 | %s / %s / %s |"
          % (res["events_used"], res["events_other_pkg"], res["events_bad_dimension"]),
          "| 切轮方式 | `%s`（轮数 %s） |" % (res["turn_method"], res["turns_total"]),
          "| 一帧 | %s ms（实测，非硬编码 33ms —— spec §3.1） |" % _f(res["frame_ms"]),
          "| 帧记录条数（去重后 / 重复丢弃） | %s / %s |"
          % (res["frames_total"], res["frames_duplicate_dropped"])]
    fit = res["wall_to_boot"]
    L.append("| 墙钟↔BOOTTIME 标定 | %s（n=%s，残差 p50 %s ms / max %s ms） |"
             % (fit.get("status"), fit.get("n"), _f(fit.get("residual_ms_p50")),
                _f(fit.get("residual_ms_max"))))
    pin = res["clock_pin"]
    L.append("| 时钟钉桩（BOOT−MONO） | %s（偏移 %s ns，前后漂移 %s ns） |"
             % (pin.get("status"), _f(pin.get("offset_ns"), 0), _f(pin.get("drift_ns"), 0)))
    L.append("")
    if res["turn_method"] == es.TURN_METHOD_WHOLE_RUN:
        L += ["> ⚠ 本次没有操作者标记，整段按**一轮**处理 —— 样本数结构上就是 1。",
              "> 一个样本也算得出 p99，但那个 p99 什么也不是。", ""]

    L += ["## 2. `|t_A − t_C|`（判据本体）", ""]
    s, v, why = res["channel_a_vs_c"], res["verdict"][0], res["verdict"][1]
    L += ["| 量 | n | dropped | p50 (ms) | p90 (ms) | p99 (ms) | 判定 |", "|---|---|---|---|---|---|---|",
          "| \\|t_A − t_C\\| | %s | %s | %s | %s | %s | **%s** — %s |"
          % (s.get("n", 0), s.get("dropped", "—"), _f(s.get("p50_ms")),
             _f(s.get("p90_ms")), _f(s.get("p99_ms")), v, why), ""]
    L.append("**%s**" % res.get("gate_caveat", ""))
    L.append("")
    sg = res.get("signed")
    if sg:
        L += ["有符号分布（**方向本身是信息**：spec §2.1 记「事件不保证像素已上屏，"
              "可能早于或晚于呈现，连符号都未知」）：p50 %s / p90 %s / p99 %s / "
              "min %s / max %s ms。"
              % (_f(sg.get("p50_ms")), _f(sg.get("p90_ms")), _f(sg.get("p99_ms")),
                 _f(sg.get("min_ms")), _f(sg.get("max_ms"))), ""]
    if res["drop_reasons"]:
        L += ["未能出数的轮次（逐条计数，不静默）：", ""]
        for why_, n in sorted(res["drop_reasons"].items()):
            L.append("- %s：%s 轮" % (why_, n))
        L.append("")

    b = res["channel_b"]
    L += ["## 3. 通道 B 的佐证（**不是时刻**）", "",
          "采样 n=%s，周期 p50 %s ms / p99 %s ms，检出变化 %s 次。"
          % (b.get("n", 0), _f(b.get("period_ms_p50")), _f(b.get("period_ms_p99")),
             b.get("transitions_detected", "—")), "",
          "> 检出次数不是时序主张，只说明 ROI 与阈值选得对不对。", ""]

    L += ["## 4. 逐轮", "", "| 轮 | A 簇数 | C 簇数 | 该轮帧数 | Δ = t_A − t_C (ms) |",
          "|---|---|---|---|---|"]
    for r in res["per_turn"]:
        L.append("| %s | %s | %s | %s | %s |"
                 % (r["turn"], r["a_clusters"], r["c_clusters"], r["frames"],
                    _f(r.get("delta_ms"))))
    L.append("")
    return "\n".join(L) + "\n"


def main(argv=None):
    e1_io.pin_console_utf8()   # D-648③：重定向落盘时别退回 GBK（中文键名是分流信号）
    ap = argparse.ArgumentParser(description="E2 三通道同轨对拍判读")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--out-md", default=None)
    args = ap.parse_args(argv)

    if not os.path.isdir(args.run_dir):
        sys.stderr.write("run-dir 不存在: %s\n" % args.run_dir)
        return 2
    out = args.out_md or os.path.join(args.run_dir, "e2_report.md")
    # 落点检查在**算之前**（D-306：e1 至今是算完才崩，操作者拿到半套交付物）。
    d = os.path.dirname(os.path.abspath(out))
    if not os.path.isdir(d):
        sys.stderr.write("--out-md 的目录不存在: %s\n" % d)
        return 2

    res = analyze(args.run_dir, args.pkg)
    ec.write_report(out, render_markdown(res))
    with open(os.path.join(args.run_dir, "e2_result.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
    for b in ec.banner_lines(res["run_kind"]):
        sys.stdout.write(b + "\n")
    sys.stdout.write("E2 report -> %s\n" % out)
    # stdout 面与 md 面必须给出同一个印象（T14 §6.1 的 S-1：e1 的 stdout 只印两个
    # 状态词、不印理由、整个不提通道 B，而 md 面上唯一的 PASS 就是 B）。
    sys.stdout.write("E2 |t_A-t_C| verdict=%s (%s) n=%s dropped=%s frame_ms=%s\n"
                     % (res["verdict"][0], res["verdict"][1],
                        res["channel_a_vs_c"].get("n"),
                        res["channel_a_vs_c"].get("dropped"), _f(res["frame_ms"])))
    sys.stdout.write("channel_b=%s (采样周期与检出次数，非时刻) transitions=%s\n"
                     % (res["channel_b"].get("status"),
                        res["channel_b"].get("transitions_detected")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
