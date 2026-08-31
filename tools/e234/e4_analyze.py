#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E4 判读 —— `T_quiet` 标定（A4 判据 C-1 的前置）。

出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §3.3 E4 逐字：
「采集足量真实会话的完整事件流，画"增量间隔"的分布；`T_quiet` 取在**流式中最大停顿**
与**结束后静默**之间的分离点。**若两者分布重叠**（即不存在干净的分离点）→ 结论是
**C-1 单独不可用，A4 必须走 C-3 合取**，这是一个合法且有价值的否定结论，
**不得为了拿到数值而硬凑**（R-10 精神；D-53 已有先例）。」

## 三件必须先说清楚的事

### 1. 「回答结束」的真值不能由 C-1 自己给

要标定的正是「多长的静默算结束」。如果拿一个静默门限去切轮，那就是用待标定量
标定它自己 —— 分离点会被造出来，而且造得很好看。所以本脚本**只接受外部标签**：
操作者标记（`E4MARK kind=answer_complete`，§1.5 里 C-2 那一级判据的人工版）。
没有标记 -> 整段一轮 -> **`NOT_EXECUTED`**，不给任何数。

### 2. 「结束后静默」这个量是**乐观**的，方向要写在脸上

本脚本量的「结束后静默」= 本轮最后一个增量 → **下一轮第一个事件**。
下一轮的第一个事件是用户自己发下一条消息触发的，所以这段静默里**含操作者的停顿**。
真实用户可以在回答刚完就立刻发下一条，那时这段静默会短得多。

=> 因此：**这个量是分离性的上界估计**。
- 若**连它**都与流式内停顿重叠 -> `C-1 单独不可用`是**硬结论**；
- 若它分开了，结论只是**有条件**成立（「在本次采集的停顿节奏下可分」），
  不足以直接把 `T_quiet` 钉成一个常量。两种情形本脚本用不同的措辞和不同的
  `c1_usable` 值分开表达，不合并成一句「可分」。

### 3. dry-run 语料**产不出**标定值

`e234_common.refuse_calibration_from_dry_run()` 是这条的前门。模拟器数字一旦以
标定值的形态流出去，往后没有任何一个面能把它认回来（D-270 的 MIXED_CAMPAIGN
是同一形状，那次靠标记，这次靠**产不出来**）。
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

SEPARABLE = "SEPARABLE"
OVERLAP = "OVERLAP"
A2_METHOD_V3 = "v3-cluster"
A2_METHOD_MARK = "operator-mark"


def separation(intra_gaps_ms, post_silences_ms):
    """两个分布 -> 有没有干净的分离点。

    判据就是 spec 那一句的字面意思：`max(流式内停顿) < min(结束后静默)`。
    **刻意用极值而不是分位数**：C-1 是一条会被逐轮应用的规则，只要有**一次**
    流式内停顿超过 T_quiet，那一次就会被误判成结束。用 p95 之类去"抹掉"
    那几次，正是 spec 明令禁止的「为了拿到数值而硬凑」。
    """
    if not intra_gaps_ms or not post_silences_ms:
        return {"verdict": ec.NOT_EXECUTED,
                "reason": "两个分布至少一个为空（流式内停顿 %d 个 / 结束后静默 %d 个）"
                          % (len(intra_gaps_ms), len(post_silences_ms))}
    hi_intra, lo_post = max(intra_gaps_ms), min(post_silences_ms)
    out = {
        "n_intra": len(intra_gaps_ms), "n_post": len(post_silences_ms),
        "intra_max_ms": hi_intra, "intra_p50_ms": ec.percentile(intra_gaps_ms, 50),
        "intra_p99_ms": ec.percentile(intra_gaps_ms, 99),
        "post_min_ms": lo_post, "post_p50_ms": ec.percentile(post_silences_ms, 50),
    }
    if hi_intra < lo_post:
        out.update({
            "verdict": SEPARABLE,
            "gap_lo_ms": hi_intra, "gap_hi_ms": lo_post,
            "candidate_t_quiet_ms": (hi_intra + lo_post) / 2.0,
            # 取中点不是审美：§1.5 明写两个方向的代价都存在（定小了把流式中的长停顿
            # 误判为结束，定大了把 RCT 系统性拉长 T_quiet），中点使两侧余量相等。
            "candidate_rationale": "开区间中点：§1.5 记的两个失效方向余量相等",
        })
    else:
        inside_intra = [g for g in intra_gaps_ms if g >= lo_post]
        inside_post = [s for s in post_silences_ms if s <= hi_intra]
        out.update({
            "verdict": OVERLAP,
            "overlap_lo_ms": lo_post, "overlap_hi_ms": hi_intra,
            "intra_gaps_inside_overlap": len(inside_intra),
            "post_silences_inside_overlap": len(inside_post),
            "worst_intra_examples_ms": sorted(inside_intra, reverse=True)[:5],
            "shortest_post_examples_ms": sorted(inside_post)[:5],
        })
    return out


def analyze(run_dir, pkg, a2_method=A2_METHOD_V3):
    run_kind = ec.read_run_kind(run_dir).get("kind")
    lines = ec.read_lines(run_dir, "adapter.log")
    evts, dropped_pkg, dropped_dim = es.content_events(lines, pkg)
    fit = ec.fit_wall_to_boot(lines)
    marks = es.parse_marks(lines, fit)
    turns, turn_method = es.segment_turns(evts, marks)

    res = {
        "experiment": "E4", "run_dir": run_dir, "pkg": pkg,
        "dry_run": run_kind == ec.KIND_DRY_RUN, "run_kind": run_kind,
        "spec": "INSTRUMENTATION_SPEC.md §3.3 E4 / §1.5 C-1",
        "events_used": len(evts), "events_other_pkg": dropped_pkg,
        "events_bad_dimension": dropped_dim,
        "turn_method": turn_method, "turns_total": len(turns),
        "a2_method": a2_method,
        "post_silence_caliber": ("本轮最后一个增量 → 下一轮第一个事件；"
                                 "**含操作者停顿**，故是分离性的上界估计"),
        "per_turn": [], "drop_reasons": {},
    }

    if turn_method != es.TURN_METHOD_MARKS:
        res["separation"] = {
            "verdict": ec.NOT_EXECUTED,
            "reason": ("没有操作者标记（`E4MARK kind=answer_complete`）。"
                       "「回答结束」的真值若由静默门限给出，就是拿待标定量标定它自己 —— "
                       "分离点会被造出来。故此处不给任何数。"),
        }
        res["c1_usable"] = None
        res["t_quiet"] = {"status": ec.NOT_EXECUTED, "reason": "缺外部结束标签"}
        return res

    gap = ec.cluster_gap_nanos()
    intra_all, post_all, drops = [], [], {}

    def _drop(k):
        drops[k] = drops.get(k, 0) + 1

    for i, t in enumerate(turns):
        ts = sorted(e["t_boot_ns"] for e in t["events"])
        row = {"turn": t["idx"], "events": len(ts)}
        if not ts:
            _drop("该轮窗内零事件")
            res["per_turn"].append(row)
            continue
        if a2_method == A2_METHOD_MARK:
            a2 = t.get("answer_start_ns")
            if a2 is None:
                _drop("该轮缺 answer_start 标记（a2_method=operator-mark 时必需）")
                res["per_turn"].append(row)
                continue
        else:
            _a0p, a2, cl = ec.v3_anchors(ts, gap)
            row["clusters"] = len(cl)
            if a2 is None:
                _drop("该轮不足两簇：A2 无判据（§1.4 的 Compose 形状即如此）")
                res["per_turn"].append(row)
                continue
        answer = [x for x in ts if x >= a2]
        row["answer_events"] = len(answer)
        if len(answer) < 2:
            _drop("该轮回答段事件 <2，构不成一个间隔")
            res["per_turn"].append(row)
            continue
        gaps = [(answer[k] - answer[k - 1]) / ec.NS_PER_MS for k in range(1, len(answer))]
        row["max_intra_gap_ms"] = max(gaps)
        intra_all.extend(gaps)
        # 标记相对最后一个增量的滞后：人工标签的诊断量。
        # 它若为负，说明操作者标早了，本轮的尾巴被算进了下一轮 —— 那会让
        # 「结束后静默」凭空变短。这个数必须印出来，否则读者无从判断标签质量。
        row["mark_lag_ms"] = (t["t_end_ns"] - answer[-1]) / ec.NS_PER_MS
        if i + 1 < len(turns) and turns[i + 1]["events"]:
            nxt = min(e["t_boot_ns"] for e in turns[i + 1]["events"])
            row["post_silence_ms"] = (nxt - answer[-1]) / ec.NS_PER_MS
            post_all.append(row["post_silence_ms"])
        else:
            _drop("末轮之后没有下一轮事件：结束后静默无从量")
        res["per_turn"].append(row)

    res["drop_reasons"] = drops
    res["intra_gaps"] = ec.summarize(intra_all)
    res["post_silences"] = ec.summarize(post_all)
    res["mark_lag"] = ec.summarize([r["mark_lag_ms"] for r in res["per_turn"]
                                    if "mark_lag_ms" in r])
    sep = separation(intra_all, post_all)
    res["separation"] = sep
    res["c1_usable"] = (None if sep["verdict"] == ec.NOT_EXECUTED
                        else sep["verdict"] == SEPARABLE)

    allowed, why = ec.refuse_calibration_from_dry_run(run_kind)
    if not allowed:
        res["t_quiet"] = {"status": ec.NOT_EXECUTED, "reason": why}
    elif sep["verdict"] == SEPARABLE:
        res["t_quiet"] = {
            "status": ec.PASS, "value_ms": sep["candidate_t_quiet_ms"],
            "interval_ms": [sep["gap_lo_ms"], sep["gap_hi_ms"]],
            "conditional": ("仅在本次采集的停顿节奏下成立：结束后静默含操作者停顿，"
                            "是上界估计。落成常量前需再取一批更紧凑的轮间节奏。"),
        }
    else:
        res["t_quiet"] = {
            "status": ec.NOT_EXECUTED,
            "reason": ("两个分布重叠 -> C-1 单独不可用，A4 必须走 C-3 合取"
                       "（spec §3.3 E4；这是合法且有价值的否定结论，不硬凑数值）"),
        }
    return res


def _f(v, nd=1):
    if v is None:
        return "—"
    return ("%.*f" % (nd, v)) if isinstance(v, float) else str(v)


def render_markdown(res):
    L = ["# E4 `T_quiet` 标定 —— 判读结果", ""]
    L += ["> %s" % b for b in ec.banner_lines(res["run_kind"])]
    if ec.banner_lines(res["run_kind"]):
        L.append("")
    L += ["> 出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §3.3 E4、§1.5（A4 判据阶梯）。",
          "> 分离判据用**极值**（`max(流式内停顿) < min(结束后静默)`），不用分位数：",
          "> C-1 是逐轮应用的规则，只要有**一次**流式内停顿超过 T_quiet，那一次就会被",
          "> 误判成结束。用分位数抹掉那几次，正是 spec 明令禁止的「为了拿到数值而硬凑」。", ""]

    sep = res["separation"]
    L += ["## 1. 结论", ""]
    if sep["verdict"] == ec.NOT_EXECUTED:
        L += ["**`NOT_EXECUTED`** —— %s" % sep.get("reason", ""), ""]
    elif sep["verdict"] == OVERLAP:
        L += ["**两个分布重叠 → `C-1 单独不可用`，A4 必须走 C-3 合取。**", "",
              "重叠区 **[%s, %s] ms**：有 %s 个流式内停顿落在结束后静默的最小值之上，"
              "有 %s 段结束后静默落在流式内最大停顿之下。"
              % (_f(sep["overlap_lo_ms"]), _f(sep["overlap_hi_ms"]),
                 sep["intra_gaps_inside_overlap"], sep["post_silences_inside_overlap"]), "",
              "最长的几次流式内停顿（ms）：%s"
              % ", ".join(_f(x) for x in sep["worst_intra_examples_ms"]),
              "", "最短的几段结束后静默（ms）：%s"
              % ", ".join(_f(x) for x in sep["shortest_post_examples_ms"]), "",
              "> 这是**合法且有价值的否定结论**（spec §3.3 E4 原话）。不给 `T_quiet` 数值。",
              "> 而且它比看上去更硬：本页的「结束后静默」**含操作者停顿**（见 §2 口径），",
              "> 是分离性的**上界**估计 —— 连这个乐观的量都重叠，真实用户节奏下只会更糟。", ""]
    else:
        L += ["**存在分离区间 (%s, %s) ms**（**有条件**成立，见下）。"
              % (_f(sep["gap_lo_ms"]), _f(sep["gap_hi_ms"])), ""]
        tq = res["t_quiet"]
        if tq["status"] == ec.PASS:
            L += ["候选 `T_quiet` = **%s ms**（%s）。" % (_f(tq["value_ms"]),
                                                       sep["candidate_rationale"]), "",
                  "> ⚠ %s" % tq["conditional"], ""]
        else:
            L += ["**不产出 `T_quiet` 数值**：%s" % tq.get("reason", ""), ""]

    L += ["## 2. 口径（读数之前必须读这一段）", "",
          "- **流式中最大停顿**：本轮 A2（`%s`）之后相邻增量事件的间隔。" % res["a2_method"],
          "- **结束后静默**：%s" % res["post_silence_caliber"], "",
          "> 方向要写在脸上：这段静默里含操作者自己的停顿，真实用户可以在回答刚完就",
          "> 立刻发下一条。所以**若连它都重叠，`C-1 不可用`是硬结论；若它分开了，",
          "> 结论只是有条件成立**，不足以把 `T_quiet` 钉成一个常量。", ""]

    L += ["## 3. 两个分布", "", "| 分布 | n | p50 (ms) | p90 (ms) | p99 (ms) | min | max |",
          "|---|---|---|---|---|---|---|"]
    for key, name in (("intra_gaps", "流式内增量间隔"), ("post_silences", "结束后静默")):
        s = res.get(key, {})
        L.append("| %s | %s | %s | %s | %s | %s | %s |"
                 % (name, s.get("n", 0), _f(s.get("p50_ms")), _f(s.get("p90_ms")),
                    _f(s.get("p99_ms")), _f(s.get("min_ms")), _f(s.get("max_ms"))))
    L.append("")
    ml = res.get("mark_lag", {})
    if ml.get("n"):
        L += ["人工标记相对最后一个增量的滞后：p50 %s ms / min %s ms / max %s ms（n=%s）。"
              % (_f(ml.get("p50_ms")), _f(ml.get("min_ms")), _f(ml.get("max_ms")),
                 ml.get("n")), "",
              "> **负值意味着操作者标早了**：该轮的尾巴被算进下一轮，会让「结束后静默」",
              "> 凭空变短、让重叠看起来更严重。这个数印出来，读者才判断得了标签质量。", ""]

    if res["drop_reasons"]:
        L += ["## 4. 未出数的轮次（逐条计数，不静默）", ""]
        for k, n in sorted(res["drop_reasons"].items()):
            L.append("- %s：%s 轮" % (k, n))
        L.append("")

    L += ["## 5. 逐轮", "",
          "| 轮 | 事件 | 回答段事件 | 最大流式内停顿 (ms) | 结束后静默 (ms) | 标记滞后 (ms) |",
          "|---|---|---|---|---|---|"]
    for r in res["per_turn"]:
        L.append("| %s | %s | %s | %s | %s | %s |"
                 % (r["turn"], r["events"], r.get("answer_events", "—"),
                    _f(r.get("max_intra_gap_ms")), _f(r.get("post_silence_ms")),
                    _f(r.get("mark_lag_ms"))))
    L.append("")
    return "\n".join(L) + "\n"


def main(argv=None):
    e1_io.pin_console_utf8()   # D-648③：重定向落盘时别退回 GBK（中文键名是分流信号）
    ap = argparse.ArgumentParser(description="E4 T_quiet 标定判读")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--out-md", default=None)
    ap.add_argument("--a2-method", default=A2_METHOD_V3,
                    choices=[A2_METHOD_V3, A2_METHOD_MARK],
                    help="回答起点判据；Compose 栈上 v3 不闭合，那时须用 operator-mark")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.run_dir):
        sys.stderr.write("run-dir 不存在: %s\n" % args.run_dir)
        return 2
    out = args.out_md or os.path.join(args.run_dir, "e4_report.md")
    d = os.path.dirname(os.path.abspath(out))
    if not os.path.isdir(d):
        sys.stderr.write("--out-md 的目录不存在: %s\n" % d)
        return 2

    res = analyze(args.run_dir, args.pkg, args.a2_method)
    ec.write_report(out, render_markdown(res))
    with open(os.path.join(args.run_dir, "e4_result.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
    for b in ec.banner_lines(res["run_kind"]):
        sys.stdout.write(b + "\n")
    sys.stdout.write("E4 report -> %s\n" % out)
    sep, tq = res["separation"], res["t_quiet"]
    sys.stdout.write("E4 separation=%s c1_usable=%s t_quiet=%s\n"
                     % (sep["verdict"], res["c1_usable"], tq.get("status")))
    if sep["verdict"] == OVERLAP:
        sys.stdout.write("E4 重叠区 [%s, %s] ms —— C-1 单独不可用，A4 须走 C-3 合取\n"
                         % (_f(sep["overlap_lo_ms"]), _f(sep["overlap_hi_ms"])))
    elif sep["verdict"] == SEPARABLE:
        sys.stdout.write("E4 分离区间 (%s, %s) ms；T_quiet=%s\n"
                         % (_f(sep["gap_lo_ms"]), _f(sep["gap_hi_ms"]),
                            _f(tq.get("value_ms"))))
    else:
        sys.stdout.write("E4 %s\n" % sep.get("reason", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
