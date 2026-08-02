#!/usr/bin/env python3
"""按 run.mode 把结果 JSONL 切成 quick / forensic 两个子集（纯 stdlib）。

出处：`docs/M3_EXPANSION_ROUND_RUNBOOK_ADDENDUM.md` §5 第 4 项——现场当天要跑
两条 `--plan`（默认 KPI + n1_rtt_p50_ms）做采样量核算，若不先按 mode 分面，
`--plan` 会把 quick 与 forensic 两种截然不同的采样密度混在一起算，核算出的
"是否够量"没有意义（D-415 裁定②：分面工具升为扩展轮出发前必做项）。

`run.mode` 是契约必填字段（`spec/schemas/result-run.schema.json:25` required
含 `mode`），缺失 = 违约数据，如实拒绝并计数——**不是第三种 mode，不静默丢**
（D-336 形状）。值只认恰好等于 `"quick"` / `"forensic"`（schema description
逐字 "quick / forensic"）；其余任何字符串一律归入 rejected 的 `other_mode`
桶，不猜测归类——**这个桶不等于"数据错误"**：`MainActivity.kt:78` 的 adb
自动化注释显示 `mode` 实际支持 `quick|forensic|continuity|ab` 四个合法值，
schema 的字段描述只写了前两个。`continuity`/`ab` 的记录落进这个桶是**正确
行为**（它们不该被这个工具悄悄并进 quick 或 forensic），本工具不替调用方
判断"这是不是真的错了"，只如实分桶+留痕原始值，排查交给下游。

守恒（本文件唯一的正确性契约）：
    len(quick) + len(forensic) + len(rejected) == 输入的合法记录数
非法 JSON 行由 `campaign_common.load_records()` 单独计入 `malformed`，
不进入上面这个等式（它们从未成为一条"记录"）。

用法：
    python split_by_run_mode.py in.jsonl --quick-out q.jsonl --forensic-out f.jsonl
    # 不给 --quick-out/--forensic-out 时默认写到 <stem>_quick.jsonl / <stem>_forensic.jsonl
"""
import argparse
import json
import os
import sys

import campaign_common as cc

MODE_QUICK = "quick"
MODE_FORENSIC = "forensic"


def split_records(records):
    """[]rec -> (quick, forensic, rejected)。

    rejected 的每一项是 {"reason": "missing_mode"|"other_mode", "run_id": ...,
    ["mode": <原始值>]}——拒绝要留痕、留下"拒了什么样的值"，不是一个裸计数
    （D-325：只收计数、不收能判断"为什么"的输入，等于构造性失明）。

    空字符串/纯空白视为 missing_mode（等价于"没写"），而非 other_mode——
    一个写了空字符串的记录和一个压根没有 mode 键的记录，对下游 --plan 采样
    核算而言是同一件事：都不能被计入任何一个 mode 的样本量。
    """
    quick, forensic, rejected = [], [], []
    for rec in records:
        run = cc.run_obj(rec)
        mode = run.get("mode")
        if mode is None or (isinstance(mode, str) and not mode.strip()):
            rejected.append({"reason": "missing_mode", "run_id": cc.run_id(rec)})
        elif mode == MODE_QUICK:
            quick.append(rec)
        elif mode == MODE_FORENSIC:
            forensic.append(rec)
        else:
            rejected.append({"reason": "other_mode", "run_id": cc.run_id(rec), "mode": mode})
    return quick, forensic, rejected


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _default_out(input_path, suffix):
    stem, _ext = os.path.splitext(input_path)
    return "%s_%s.jsonl" % (stem, suffix)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="按 run.mode 把结果 JSONL 切成 quick/forensic 两份（契约必填字段，缺失即拒绝）")
    ap.add_argument("input", help="结果 JSONL（campaign_report.py 同源输入）")
    ap.add_argument("--quick-out", help="quick 子集输出路径（默认 <stem>_quick.jsonl）")
    ap.add_argument("--forensic-out", help="forensic 子集输出路径（默认 <stem>_forensic.jsonl）")
    args = ap.parse_args(argv)
    cc.force_utf8_stdout()

    stats = {}
    records, files = cc.load_records([args.input], dedupe=False, stats=stats)
    if not files:
        raise SystemExit("no such file: %s" % args.input)

    quick, forensic, rejected = split_records(records)
    # 守恒不是"应该成立"，是这段代码结构本身保证的：split_records 里每条记录
    # 恰好落进三个列表之一。断言留在这里，是为了未来任何人改动这段逻辑时，
    # 一旦破坏了这个不变量会立刻响，而不是被下游某个更晚的检查悄悄吸收。
    assert len(quick) + len(forensic) + len(rejected) == len(records)

    quick_out = args.quick_out or _default_out(args.input, "quick")
    forensic_out = args.forensic_out or _default_out(args.input, "forensic")
    _write_jsonl(quick_out, quick)
    _write_jsonl(forensic_out, forensic)

    missing = sum(1 for r in rejected if r["reason"] == "missing_mode")
    other = sum(1 for r in rejected if r["reason"] == "other_mode")
    print("input records: %d (malformed lines skipped: %d)"
         % (len(records), stats.get("malformed", 0)))
    print("quick -> %s (%d)" % (quick_out, len(quick)))
    print("forensic -> %s (%d)" % (forensic_out, len(forensic)))
    print("rejected: %d (missing_mode=%d, other_mode=%d)" % (len(rejected), missing, other))
    for r in rejected:
        detail = " mode=%r" % r["mode"] if "mode" in r else ""
        print("  reject run_id=%s%s reason=%s" % (r["run_id"], detail, r["reason"]),
             file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
