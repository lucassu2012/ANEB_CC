#!/usr/bin/env python3
"""ANEB 语料台账（SPEC-3 §3.1）——「进展」的单一事实源（stdlib only）。

回答一个此前没人能一眼答出的问题：**数据资产到底有多少**（诊断报告 §1：
561 条决策对 73 run，没有客观度量）。此后任何「进展」声明必须引用本台账的
增量，而不是各自手抄数字。

判据全部派生自既有读法，不自创解析（§2.14/D-264）：
  * 装载/去重/完整性 = `cc.load_records`（run_id 去重、body 冲突记账、坏行计数）；
  * 战役标签 = `cc.campaign_labels`；合成判定 = `cc.is_synthetic`（单列，绝不混入）；
  * RAT = `radio_rollup.radio_of(scn)["rat"]`（场景级证据，按场景计数——
    一个 run 可跨 RAT，把它折成 run 级单值就是编造）。
发现规则同样从产物枚举（D-273）：evidence/ 下所有 *.jsonl 逐文件试装载，
0 条契约记录的列入跳过清单——不靠手写文件名黑名单。

设备侧 Room 库单独一节：同一 run 在 wire 与设备库各有一面，**两节数字不可
相加**（会双计），台账正文写明。

对拍锚（守卫钉住）：对同一语料，本台账的真实 run 数 == `campaign_report`
清点行「输入记录：N」的 N（同一装载器，两面必须相等）。

用法：
    python corpus_ledger.py                       # 全量重算，写 docs/ 两面
    python corpus_ledger.py --root evidence --md docs/CORPUS_LEDGER.md
"""
import argparse
import glob
import io
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign_common as cc          # noqa: E402
import radio_rollup                   # noqa: E402

MD_HEADER = (
    "# 语料台账（自动生成——勿手编）\n\n"
    "> 本文件由 `scripts/corpus_ledger.py` 全量重算生成，手改会在下次重算时丢失。\n"
    "> **使用规则**：任何「进展」声明必须引用本台账的总数与增量（例：\n"
    "> 「真实 run 73 → 103（+30，豆包首批）」），不得各自手抄数字（SPEC-3 §3.1）。\n"
    "> 判据：装载/去重=`cc.load_records`（run_id 首见保留、body 冲突单记），\n"
    "> 合成=`cc.is_synthetic` 单列，RAT=场景级计数（一 run 可跨 RAT，不折单值）。\n")


def discover(root):
    """evidence/ 下全部 jsonl 逐文件试装载。返回 (语料文件表, 跳过表)。

    「哪些文件是语料」从内容判定（装出 ≥1 条带 run 的记录），不写名字黑名单
    ——黑名单会漏会过期，枚举漏不掉（D-273）。"""
    corpus, skipped = [], []
    for path in sorted(glob.glob(os.path.join(root, "**", "*.jsonl"),
                                 recursive=True)):
        st = {}
        recs, _ = cc.load_records([path], dedupe=False, stats=st, quiet=True)
        n = sum(1 for r in recs if isinstance(cc.run_obj(r), dict)
                and cc.run_obj(r))
        if n:
            corpus.append((path, n, st.get("lines", 0)))
        else:
            skipped.append((path, st.get("lines", 0)))
    return corpus, skipped


def summarize(paths):
    """全语料一次去重装载 → (真实 records, 合成 records, 装载 stats)。"""
    st = {}
    recs, _ = cc.load_records(paths, dedupe=True, stats=st, quiet=True)
    real = [r for r in recs if not cc.is_synthetic(r)]
    synth = [r for r in recs if cc.is_synthetic(r)]
    return real, synth, st


def buckets(real):
    """run 级标签桶 + 场景级 RAT/有效性桶 + low_confidence 比例。"""
    by = {k: Counter() for k in ("campaign_id", "point_id", "carrier",
                                 "time_band")}
    rat = Counter()
    validity = Counter()
    aqs_runs = low_conf = 0
    scn_total = 0
    for r in real:
        labels = cc.campaign_labels(r)
        for k in by:
            by[k][labels.get(k) or cc.UNLABELED] += 1
        aqs = (cc.run_obj(r).get("aqs") or {})
        if isinstance(aqs, dict) and aqs.get("score") is not None:
            aqs_runs += 1
            if aqs.get("low_confidence"):
                low_conf += 1
        for scn in cc.iter_scenarios(r):
            scn_total += 1
            validity[cc.scenario_validity(scn)] += 1
            radio = radio_rollup.radio_of(scn)
            rat[(radio or {}).get("rat") or "no_radio_block"] += 1
    return {"by": by, "rat": rat, "validity": validity, "scn_total": scn_total,
            "aqs_runs": aqs_runs, "low_conf": low_conf}


def room_dbs(root):
    """已拉取设备库的行数（只读）。缺表=None 渲染成 —，不是 0（R-10）；
    读不了整库时如实记，绝不静默缺席。"""
    out = []
    import sqlite3
    for path in sorted(glob.glob(os.path.join(root, "**", "*.db"),
                                 recursive=True)):
        row = {"path": path.replace(os.sep, "/")}
        try:
            con = sqlite3.connect("file:%s?mode=ro" % path.replace(os.sep, "/"),
                                  uri=True)
            for table, key in (("test_run", "runs"),
                               ("scenario_result", "scenarios"),
                               ("voice_result", "voice_rows")):
                try:
                    row[key] = con.execute(
                        'SELECT COUNT(*) FROM "%s"' % table).fetchone()[0]
                except sqlite3.Error:
                    row[key] = None          # 表不存在=None，不是 0（R-10）
            con.close()
        except sqlite3.Error as e:
            row["error"] = str(e)
        out.append(row)
    return out


def render_md(corpus, skipped, real, synth, st, bk, dbs):
    n = lambda c: "、".join(f"{k}×{v}" for k, v in cc.ranked(c)) or "—"
    lines = [MD_HEADER]
    lines.append("## 一、wire 语料（真实测量，run_id 去重后）\n")
    lines.append(f"- **真实 run 总数：{len(real)}**（场景 {bk['scn_total']}；"
                 f"文件 {len(corpus)} 份、原始行 {st.get('lines', 0)}、"
                 f"跨文件重复 {st.get('duplicates', 0)} 条已去、"
                 f"body 冲突 {len(st.get('conflicts') or [])} 条单记、"
                 f"坏行 {st.get('malformed', 0)}、无 run_id {st.get('no_run_id', 0)}）")
    lines.append(f"- 合成记录（`is_synthetic`）：**{len(synth)} 条，单列不计入上行**")
    lc = (f"{bk['low_conf']}/{bk['aqs_runs']}"
          f"（{bk['low_conf'] / bk['aqs_runs'] * 100:.0f}%）"
          if bk["aqs_runs"] else "0/0（无带分 run，无从判断）")
    lines.append(f"- 带 AQS 的 run：{bk['aqs_runs']}；其中 low_confidence：{lc}\n")
    lines.append("| 维度 | 分布（run 计） |\n|---|---|")
    for k, title in (("campaign_id", "战役"), ("point_id", "点位"),
                     ("carrier", "运营商"), ("time_band", "时窗")):
        lines.append(f"| {title} | {n(bk['by'][k])} |")
    lines.append(f"| RAT（**场景**计——一 run 可跨 RAT，不折单值） | {n(bk['rat'])} |")
    lines.append(f"| 场景有效性 | {n(bk['validity'])} |\n")
    lines.append("## 二、设备侧 Room 库（与第一节**不可相加**——同 run 两面）\n")
    lines.append("| 库 | test_run | scenario_result | voice_result |\n|---|---|---|---|")
    for d in dbs:
        cell = lambda v: "读不了" if "error" in d else ("—" if v is None else v)
        lines.append(f"| {d['path']} | {cell(d.get('runs'))} | "
                     f"{cell(d.get('scenarios'))} | {cell(d.get('voice_rows'))} |")
    lines.append("\n## 三、装载明细\n")
    lines.append("| 文件 | 契约记录 | 原始行 |\n|---|---|---|")
    for path, kept, total in corpus:
        lines.append(f"| {path.replace(os.sep, '/')} | {kept} | {total} |")
    if skipped:
        lines.append("\n跳过（0 条契约记录，非语料）：" +
                     "、".join(f"`{p.replace(os.sep, '/')}`" for p, _ in skipped))
    lines.append("")
    return "\n".join(lines)


def render_csv_rows(real, synth, bk):
    rows = [("total", "real_runs", len(real)),
            ("total", "synthetic_records", len(synth)),
            ("total", "scenarios", bk["scn_total"]),
            ("total", "aqs_runs", bk["aqs_runs"]),
            ("total", "low_confidence_runs", bk["low_conf"])]
    for k in ("campaign_id", "point_id", "carrier", "time_band"):
        rows += [(k, key, cnt) for key, cnt in cc.ranked(bk["by"][k])]
    rows += [("rat_scenarios", key, cnt) for key, cnt in cc.ranked(bk["rat"])]
    rows += [("validity_scenarios", key, cnt)
             for key, cnt in cc.ranked(bk["validity"])]
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="ANEB 语料台账（进展的单一事实源）")
    ap.add_argument("--root", default="evidence")
    ap.add_argument("--md", default=os.path.join("docs", "CORPUS_LEDGER.md"))
    ap.add_argument("--csv", default=os.path.join("docs", "CORPUS_LEDGER.csv"))
    a = ap.parse_args(argv)
    corpus, skipped = discover(a.root)
    real, synth, st = summarize([p for p, _, _ in corpus])
    bk = buckets(real)
    dbs = room_dbs(a.root)
    md = render_md(corpus, skipped, real, synth, st, bk, dbs)
    io.open(a.md, "w", encoding="utf-8", newline="").write(md)
    import csv as _csv
    with open(a.csv, "w", newline="", encoding="utf-8-sig") as f:
        w = _csv.writer(f)
        w.writerow(["face", "key", "count"])
        for row in render_csv_rows(real, synth, bk):
            w.writerow(row)
    print(f"real_runs={len(real)} synthetic={len(synth)} "
          f"files={len(corpus)} skipped={len(skipped)}")
    print(f"written: {a.md}, {a.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
