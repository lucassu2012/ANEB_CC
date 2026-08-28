#!/usr/bin/env python3
"""徽章值产出（SPEC-4 4.4 砍④的脚本侧；转需求经大脑，落 v3 lane）。

**要解决的毛病**：前台文档写死门数/测试数，而这些数每次提交都在变——本仓已因此
反复出现「文档说 15 门、实际 19 门」「758 tests 早已过期」这类漂移，逐次手改治不住。
替代=让链跑自己吐一份机器可引文件，文档引它、不抄它。

**只写这次真测到的值**：任何一项测不到就写 `unknown`，**绝不沿用上一次的值，也不猜**
——一个过期的徽章比没有徽章更危险（读者以为它是刚测的）。每个值都带 `_source`
说明它是从哪一行读出来的，读者可以自己去核。

**判据来源（不自造口径）**：
  * `gate_count` ← verify_all 汇总行 `checks: N total`（该脚本自己印的数，唯一权威）；
  * `reflex_tests` ← `scripts/tests/run_all.py` 汇总行 `campaign-analysis reflex: N/M passed`；
  * `corpus_real_runs` ← `docs/CORPUS_LEDGER.csv` 的 `total,real_runs`（D-565 台账，
    「进展」的单一事实源——徽章不另起一套计数）。

用法：
    python badges.py --log evidence/phase0/verify_all_<ts>.log   # 链跑末尾调用
    python badges.py                                             # 取最新一份链跑日志
"""
import argparse
import glob
import io
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
UNKNOWN = "unknown"


def _read(path):
    """读文件；读不了返回 None（与「读到空」区分开，R-10）。"""
    try:
        return io.open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None


def gate_count(log_path):
    """(值, 来源说明)。取 verify_all 自己印的 `checks: N total`。"""
    if not log_path or not os.path.exists(log_path):
        return UNKNOWN, "no verify_all log given/found"
    txt = _read(log_path)
    if txt is None:
        return UNKNOWN, "log unreadable: %s" % os.path.basename(log_path)
    m = re.findall(r"checks:\s*(\d+)\s*total", txt)
    if not m:
        return UNKNOWN, "no 'checks: N total' line in %s" % os.path.basename(log_path)
    # 一份日志里该行只出现一次；出现多次时取最后一次（汇总在末尾）
    return m[-1], "verify_all log %s" % os.path.basename(log_path)


def reflex_tests(log_path):
    """(值, 来源说明)。取链跑日志里 run_all 的汇总行；两个数不等时如实标出。"""
    if not log_path or not os.path.exists(log_path):
        return UNKNOWN, "no verify_all log given/found"
    txt = _read(log_path)
    if txt is None:
        return UNKNOWN, "log unreadable"
    m = re.findall(r"campaign-analysis reflex:\s*(\d+)/(\d+)\s*passed", txt)
    if not m:
        return UNKNOWN, "no reflex summary line in log"
    passed, total = m[-1]
    if passed != total:
        # 不是徽章该沉默的场合：有红的那次，徽章要说出来
        return "%s/%s" % (passed, total), "reflex line (NOT all green)"
    return total, "reflex line (all green)"


def corpus_real_runs(csv_path):
    """(值, 来源说明)。取 D-565 台账的 total,real_runs——徽章不另起一套计数。"""
    txt = _read(csv_path)
    if txt is None:
        return UNKNOWN, "corpus ledger CSV not readable/absent"
    # 用 csv 模块而不是裸 split(",")。**如实说清它防的是什么，以及为什么没有
    # 守卫**：台账的 `cells` 列是多值串，将来若某值含逗号，裸 split 会把该行
    # 劈错格——但本函数是**逐行找匹配**，劈错的那行 cells[1] 不等于
    # "real_runs" 会被自然跳过，目标行照样读对，**错法因此不产生错误结果**。
    # 我为它写过一条守卫，实测突变存活（裸 split 照样绿）——那是条假守卫，
    # 已撤（§2.17 第 3 条：这句话错了谁会红？没人红就说明它什么也没钉；
    # 「空气守卫不建」）。保留 csv 模块是**健壮性**：将来若改成按行号取值或
    # 需要完整读表，裸 split 就会真的读错。本条由 §2.17 反扫自己的产出时抓到
    # ——我 docstring 写「不自造口径」，而这里确实自造了一份 CSV 解析。
    import csv as _csv
    for row in _csv.reader(io.StringIO(txt)):
        cells = [c.strip().lstrip("﻿") for c in row]
        if len(cells) >= 3 and cells[0] == "total" and cells[1] == "real_runs":
            return cells[2], "CORPUS_LEDGER.csv total,real_runs (D-565)"
    return UNKNOWN, "no total,real_runs row in ledger CSV"


def latest_log(evidence_dir):
    files = sorted(glob.glob(os.path.join(evidence_dir, "verify_all_*.log")))
    return files[-1] if files else None


def build(log_path, csv_path):
    """有序的 (key, value, source) 三元组表。"""
    return [("gate_count",) + gate_count(log_path),
            ("reflex_tests",) + reflex_tests(log_path),
            ("corpus_real_runs",) + corpus_real_runs(csv_path)]


def render(rows, log_path):
    lines = [
        "# 徽章值（自动生成——勿手编；每次链跑覆盖）",
        "# 引用规则：前台文档**引本文件的键**，不要把数字抄进正文（抄的会过期）。",
        "# unknown = 本次没测到，**不是 0，也不是沿用上次**——过期的徽章比没有更危险。",
        "# 来源日志：%s" % (os.path.basename(log_path) if log_path else "(none)"),
        "# 注意：值的新鲜度=来源日志的新鲜度。徽章不知道「今天」，只知道它读了哪一份；",
        "#       引用前请确认该日志就是你要引的那次链跑（分层跑不落 evidence，见 §3.2）。",
        "",
    ]
    for key, value, source in rows:
        lines.append("%s=%s" % (key, value))
        lines.append("%s_source=%s" % (key, source))
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="verify_all 徽章值产出")
    ap.add_argument("--log", help="verify_all 日志路径（默认取 evidence/phase0 最新一份）")
    ap.add_argument("--evidence-dir",
                    default=os.path.join(_REPO, "evidence", "phase0"))
    ap.add_argument("--csv", default=os.path.join(_REPO, "docs", "CORPUS_LEDGER.csv"))
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    log_path = a.log or latest_log(a.evidence_dir)
    out = a.out or os.path.join(a.evidence_dir, "badges.txt")
    rows = build(log_path, a.csv)
    io.open(out, "w", encoding="utf-8", newline="").write(render(rows, log_path))
    for key, value, _ in rows:
        print("%s=%s" % (key, value))
    print("written: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
