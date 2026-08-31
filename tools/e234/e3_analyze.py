#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E3 判读 —— `A0 → A0′` 间隔（那个「从未被测过的量」）。

出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §3.3 E3 逐字：
「通道 C 的输入事件时间线取 A0，通道 A 的 v3 首簇首事件取 A0′，求差」；
判据「给出 `A0→A0′` 的分布。**它不是"误差"，是被测 App 的输入处理耗时**」。
它同时是 §6-6 的解阻条件（`ttft_ui_ms` 的文案要么改成 `A0′→A2`，要么把该间隔加上）。

## 一个必须先摆出来的坏消息：这台设备的 framestats 可能根本没有输入事件时戳

`dumpsys gfxinfo <pkg> framestats` 的列集**随 API 级别改过**。老形态里有
`OldestInputEvent` / `NewestInputEvent` 两列，都是 CLOCK_MONOTONIC 纳秒 —— 那正是
spec §2.3 说的「输入事件时间线」。而 `evidence/e1/20260801-170127/framestats.txt`
（2026-08-01 模拟器 dry-run 归档）的表头**逐字**是：

    Flags,FrameTimelineVsyncId,IntendedVsync,Vsync,InputEventId,HandleInputStart,…

`InputEventId` 是一个 **id**，不是时戳。**在这种表头下 A0 取不到。**

本脚本对此的处置（§1.6 降级纪律第 1 条：禁止用备判据的值冒充主判据的口径）：

1. 表头带 `NewestInputEvent` → 主判据，`a0_method: framestats-input-event`；
2. 否则 → 该条 **`NOT_EXECUTED`**，并把**实际看到的列名**印出来（不是印一句
   「没数据」——印出列名，下一个人才判断得了是设备形态变了还是我们读错了）；
3. `--allow-handle-input-start-proxy` 可另开一个**旁路**，用 `HandleInputStart`
   （帧开始处理输入的时刻，不是输入事件到达的时刻）。它有自己的 method 标签、
   **单独成池**、**不参与主判据**——两个 method 的值不进同一个统计池（§1.6 第 4 条，
   D-366 已经为这个形状付过学费）。

## A0′ 的可得性是**结构判据**，不是一张 App 白名单

§1.4 记 DeepSeek 的 A0′ 不可得，理由是「思考期动画使 >400ms 静默不存在 → 单簇不闭合」。
那是一个**能从数据里看出来的**性质，不需要写死包名：某一轮分不出两簇，该轮就没有
A0′，记 `NOT_EXECUTED` + 原因。写死包名的白名单会在 App 改版那天悄悄说谎。

> 但要如实说清它的边界：本脚本给出的 A0′ 一律带 `a0p_method: v3-cluster`。
> 自绘 Compose 栈上即便偶然分出了两簇，那个「首簇」的语义也不是用户气泡上屏
> （§1.4）。**v3 是豆包型 View 栈的方法**；拿它读 DeepSeek 的数要额外论证。
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

PRIMARY_COLS = ("OldestInputEvent", "NewestInputEvent")
PROXY_COL = "HandleInputStart"
METHOD_PRIMARY = "framestats-input-event"
METHOD_PROXY = "handle-input-start-proxy"


def input_timeline(rows, allow_proxy):
    """framestats 行 -> (method, [t_mono_ns], columns, reason)。

    返回的时刻**只来自一种 method**。缺主判据列时不悄悄退到旁路：
    旁路要显式开，且它带自己的名字（§1.6 第 1/2 条）。
    """
    if not rows:
        return None, [], [], "framestats 零行（环缓冲未取到 / PROFILEDATA 为空）"
    cols = list(rows[0].keys())
    if PRIMARY_COLS[1] in cols:
        ts = sorted({r[PRIMARY_COLS[1]] for r in rows
                     if r.get(PRIMARY_COLS[1]) and ec.MIN_PLAUSIBLE_NS <= r[PRIMARY_COLS[1]]})
        if not ts:
            return None, [], cols, "有 NewestInputEvent 列但全为 0：本次采集里没有输入帧"
        return METHOD_PRIMARY, ts, cols, None
    why = ("本设备的 framestats 表头没有 %s —— 它只有 `InputEventId` 这类**标识符**，"
           "不是时戳。A0 的主判据在这种形态下取不到。实际列：%s"
           % ("/".join(PRIMARY_COLS), ", ".join(cols)))
    if not allow_proxy:
        return None, [], cols, why
    if PROXY_COL not in cols:
        return None, [], cols, why + "；旁路列 %s 也不存在" % PROXY_COL
    ts = sorted({r[PROXY_COL] for r in rows
                 if r.get(PROXY_COL) and ec.MIN_PLAUSIBLE_NS <= r[PROXY_COL]})
    if not ts:
        return None, [], cols, why + "；旁路列 %s 全为 0" % PROXY_COL
    return METHOD_PROXY, ts, cols, None


def analyze(run_dir, pkg, allow_proxy=False):
    run_kind = ec.read_run_kind(run_dir).get("kind")
    lines = ec.read_lines(run_dir, "adapter.log")
    evts, dropped_pkg, dropped_dim = es.content_events(lines, pkg)
    fit = ec.fit_wall_to_boot(lines)
    marks = es.parse_marks(lines, fit)
    turns, turn_method = es.segment_turns(evts, marks)
    pin = ec.clock_pin(ec.read_lines(run_dir, "stim_pre.log"),
                       ec.read_lines(run_dir, "stim_post.log"), None)

    fs_rows = ec.ea.parse_framestats(ec.read_text(run_dir, "framestats.txt"))
    fs_rows, dup_fs = (ec.dedupe_by(fs_rows, "IntendedVsync") if fs_rows else ([], 0))
    method, input_ts, cols, why = input_timeline(fs_rows, allow_proxy)

    res = {
        "experiment": "E3", "run_dir": run_dir, "pkg": pkg,
        "dry_run": run_kind == ec.KIND_DRY_RUN, "run_kind": run_kind,
        "spec": "INSTRUMENTATION_SPEC.md §3.3 E3 / §6-6 / §3.4 G-4",
        "events_used": len(evts), "events_other_pkg": dropped_pkg,
        "events_bad_dimension": dropped_dim,
        "turn_method": turn_method, "turns_total": len(turns),
        "framestats_rows": len(fs_rows), "framestats_duplicate_dropped": dup_fs,
        "framestats_columns": cols,
        "a0_method": method, "a0_unavailable_reason": why,
        "a0p_method": "v3-cluster",
        "clock_pin": pin, "per_turn": [], "drop_reasons": {},
    }

    if method is None:
        res["interval"] = {"status": ec.NOT_EXECUTED, "n": 0, "reason": why}
        res["verdict"] = (ec.NOT_EXECUTED, "A0 无判据：%s" % why)
        return res
    if pin.get("status") != ec.PASS:
        res["interval"] = {"status": ec.NOT_EXECUTED, "n": 0,
                           "reason": "时钟钉桩不可用：%s" % pin.get("reason")}
        res["verdict"] = (ec.NOT_EXECUTED, "跨基比较缺时钟钉桩")
        return res

    gap = ec.cluster_gap_nanos()
    vals, drops = [], {}

    def _drop(k):
        drops[k] = drops.get(k, 0) + 1

    for t in turns:
        ts = [e["t_boot_ns"] for e in t["events"]]
        a0p_boot, _a2, cl = ec.v3_anchors(ts, gap)
        row = {"turn": t["idx"], "clusters": len(cl)}
        if a0p_boot is None:
            _drop("该轮不足两簇：A0′ 无判据（§1.4 的 Compose 形状即如此）")
            res["per_turn"].append(row)
            continue
        a0p_mono = ec.boot_to_mono_ns(a0p_boot, pin)
        # 下界只在**可信**时才用：首轮且无显式标记时，`t_start_ns` 就是第一条事件，
        # 而 A0（手指离屏）在它**之前** —— 拿它当下界会把首轮的 A0 挡在窗外。
        lo = ec.boot_to_mono_ns(t["t_start_ns"], pin) if t.get("start_explicit") else None
        cands = [x for x in input_ts
                 if (lo is None or lo <= x) and x <= a0p_mono]
        row["input_candidates"] = len(cands)
        if not cands:
            _drop("本轮窗内没有输入事件时戳（环缓冲已冲掉 / 该轮没有输入帧）")
            res["per_turn"].append(row)
            continue
        a0 = cands[-1]          # 最接近 A0′ 的那一次输入
        row["a0_mono_ns"] = a0
        row["interval_ms"] = (a0p_mono - a0) / ec.NS_PER_MS
        vals.append(row["interval_ms"])
        res["per_turn"].append(row)

    res["drop_reasons"] = drops
    res["interval"] = ec.summarize(vals, dropped=sum(drops.values()))
    # E3 没有"门"：spec 逐字说它「不是误差，是被测 App 的输入处理耗时」。
    # 硬给它安一个 PASS/FAIL 就是把一个被测对象的性质说成我们打点的性质。
    res["verdict"] = (
        (ec.PASS, "已给出 A0→A0′ 分布（method=%s，n=%s）" % (method, res["interval"].get("n")))
        if res["interval"]["status"] == ec.PASS
        else (ec.NOT_EXECUTED, "无可用轮次"))
    if res["interval"]["status"] == ec.PASS:
        # §6-6 的解阻条件在这里被机器化：拿到分布之后，`ttft_ui_ms` 的文案
        # 要么改成 A0′→A2，要么把这个间隔加上。数字给出来，裁定仍归大脑。
        res["for_6_6"] = {
            "a0_to_a0p_p50_ms": res["interval"]["p50_ms"],
            "a0_to_a0p_p99_ms": res["interval"]["p99_ms"],
            "note": "§6-6 待裁：ttft_ui_ms 改口径为 A0′→A2，或在其上加这一段。本脚本不代裁。",
        }
    return res


def _f(v, nd=3):
    if v is None:
        return "—"
    return ("%.*f" % (nd, v)) if isinstance(v, float) else str(v)


def render_markdown(res):
    L = ["# E3 `A0 → A0′` 间隔 —— 判读结果", ""]
    L += ["> %s" % b for b in ec.banner_lines(res["run_kind"])]
    if ec.banner_lines(res["run_kind"]):
        L.append("")
    L += ["> 出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §3.3 E3、§6-6。",
          "> **这不是「误差」，是被测 App 的输入处理耗时**（spec 原话）。",
          "> 因此本页没有 PASS/FAIL 型的门 —— 给一个被测对象的性质安一个门，",
          "> 等于把它说成我们打点的性质。", ""]
    L += ["## 1. 判据可得性", "", "| 项 | 值 |", "|---|---|",
          "| A0 判据（通道 C 输入事件时间线） | `%s` |" % (res["a0_method"] or "不可得"),
          "| A0′ 判据（通道 A v3 首簇首事件） | `%s` |" % res["a0p_method"],
          "| framestats 行数（去重后 / 重复丢弃） | %s / %s |"
          % (res["framestats_rows"], res["framestats_duplicate_dropped"]),
          "| 切轮方式（轮数） | `%s`（%s） |" % (res["turn_method"], res["turns_total"]),
          "| 可用内容事件 / 他包滤除 / 量纲拒收 | %s / %s / %s |"
          % (res["events_used"], res["events_other_pkg"], res["events_bad_dimension"]), ""]
    if res["a0_unavailable_reason"]:
        L += ["**A0 不可得的原因**：%s" % res["a0_unavailable_reason"], "",
              "> 这一条不是「没数据」，是**这台设备的 framestats 形态里没有那两列**。",
              "> 列名已逐字印在上面，下一个人才判断得了是设备形态变了还是我们读错了。", ""]
    L += ["## 2. `A0 → A0′` 分布", ""]
    s = res["interval"]
    L += ["| method | n | dropped | p50 (ms) | p90 (ms) | p99 (ms) | min | max |",
          "|---|---|---|---|---|---|---|---|",
          "| `%s` | %s | %s | %s | %s | %s | %s | %s |"
          % (res["a0_method"] or "—", s.get("n", 0), s.get("dropped", "—"),
             _f(s.get("p50_ms")), _f(s.get("p90_ms")), _f(s.get("p99_ms")),
             _f(s.get("min_ms")), _f(s.get("max_ms"))), ""]
    if res["a0_method"] == METHOD_PROXY:
        L += ["> ⚠ 本次用的是**旁路** `HandleInputStart`：它是「帧开始处理输入」的时刻，",
              "> 不是「输入事件到达」的时刻。它有自己的 method 名、**单独成池**，",
              "> **不得**与 `framestats-input-event` 的值混在一起统计（§1.6 第 4 条）。", ""]
    if res.get("for_6_6"):
        L += ["## 3. 交回 §6-6 的两个数", "",
              "`A0→A0′` p50 = %s ms，p99 = %s ms。" % (_f(res["for_6_6"]["a0_to_a0p_p50_ms"]),
                                                      _f(res["for_6_6"]["a0_to_a0p_p99_ms"])),
              "", "> %s" % res["for_6_6"]["note"], ""]
    if res["drop_reasons"]:
        L += ["## 4. 未出数的轮次（逐条计数，不静默）", ""]
        for k, n in sorted(res["drop_reasons"].items()):
            L.append("- %s：%s 轮" % (k, n))
        L.append("")
    L += ["## 5. 逐轮", "", "| 轮 | 簇数 | 窗内输入事件数 | A0→A0′ (ms) |", "|---|---|---|---|"]
    for r in res["per_turn"]:
        L.append("| %s | %s | %s | %s |"
                 % (r["turn"], r["clusters"], r.get("input_candidates", "—"),
                    _f(r.get("interval_ms"))))
    L.append("")
    return "\n".join(L) + "\n"


def main(argv=None):
    e1_io.pin_console_utf8()   # D-648③：重定向落盘时别退回 GBK（中文键名是分流信号）
    ap = argparse.ArgumentParser(description="E3 A0→A0′ 间隔判读")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--out-md", default=None)
    ap.add_argument("--allow-handle-input-start-proxy", action="store_true",
                    help="开旁路（HandleInputStart）；它单独成池、不冒充主判据")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.run_dir):
        sys.stderr.write("run-dir 不存在: %s\n" % args.run_dir)
        return 2
    out = args.out_md or os.path.join(args.run_dir, "e3_report.md")
    d = os.path.dirname(os.path.abspath(out))
    if not os.path.isdir(d):
        sys.stderr.write("--out-md 的目录不存在: %s\n" % d)
        return 2

    res = analyze(args.run_dir, args.pkg, args.allow_handle_input_start_proxy)
    ec.write_report(out, render_markdown(res))
    with open(os.path.join(args.run_dir, "e3_result.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
    for b in ec.banner_lines(res["run_kind"]):
        sys.stdout.write(b + "\n")
    sys.stdout.write("E3 report -> %s\n" % out)
    s = res["interval"]
    sys.stdout.write("E3 a0_method=%s status=%s n=%s dropped=%s p50=%s p99=%s\n"
                     % (res["a0_method"], s.get("status"), s.get("n"),
                        s.get("dropped"), _f(s.get("p50_ms")), _f(s.get("p99_ms"))))
    if res["a0_unavailable_reason"]:
        sys.stdout.write("E3 A0 不可得：%s\n" % res["a0_unavailable_reason"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
