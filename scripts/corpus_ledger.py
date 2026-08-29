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

# 语料根：两处都是**真实测量的落点**，不是两个数据面（2026-08-29 扩，见 discover）。
DEFAULT_ROOTS = ("evidence", os.path.join("server", "data", "results"))

MD_HEADER = (
    "# 语料台账（自动生成——勿手编）\n\n"
    "> 本文件由 `scripts/corpus_ledger.py` 全量重算生成，手改会在下次重算时丢失。\n"
    "> **使用规则**：任何「进展」声明必须引用本台账的总数与增量（例：\n"
    "> 「真实 run 73 → 103（+30，SZ-PILOT-01 扩展轮）」），不得各自手抄数字（SPEC-3 §3.1）。\n"
    "> ⚠ **增量必须说清是哪条链**：观察通道批次（豆包先行批等）产出 **0 条 wire run**\n"
    "> ——其产物喂 `validate_results.py` 即 contract VIOLATIONS，结构上进不了 wire 池，\n"
    "> 见第四节。把观察批写成「真实 run +N」正是本台账要拦的那种手抄。\n"
    "> 判据：装载/去重=`cc.load_records`（run_id 首见保留、body 冲突单记），\n"
    "> 合成=`cc.is_synthetic` 单列，RAT=场景级计数（一 run 可跨 RAT，不折单值）。\n")


def discover(roots):
    """给定根目录（单个字符串或多个）下全部 jsonl 逐文件试装载。

    返回 (语料文件表, 跳过表)。「哪些文件是语料」从内容判定（装出 ≥1 条带 run
    的记录），不写名字黑名单——黑名单会漏会过期，枚举漏不掉（D-273）。

    **为什么是多根**（2026-08-29，v2 实证后扩）：初版只扫 `evidence/`，于是
    服务端落盘 `server/data/results/` 里那条只存在于该处的真实 run 被无声排除
    （实测 2 条中 1 条：`019f5b59…`，阶段 0 早期，非合成、status=completed）。
    分量只有 1/110，但**一个自称「单一事实源」的台账不该有无声排除**——
    要么收进来，要么把边界写在读者看得见的地方。这里选收进来：server 落盘是
    同一批真实测量的**另一个落点**，不是另一个数据面。"""
    if isinstance(roots, str):
        roots = [roots]
    corpus, skipped = [], []
    paths = []
    for root in roots:
        paths.extend(glob.glob(os.path.join(root, "**", "*.jsonl"),
                               recursive=True))
    for path in sorted(set(paths)):
        st = {}
        recs, _ = cc.load_records([path], dedupe=False, stats=st, quiet=True)
        n = sum(1 for r in recs if isinstance(cc.run_obj(r), dict)
                and cc.run_obj(r))
        bad = st.get("malformed", 0) + st.get("unreadable_files", 0)
        if n:
            corpus.append((path, n, st.get("lines", 0)))
        else:
            # 「装不出契约记录」有两种：真不是语料（空文件/别的 JSON），与
            # **装载失败**（坏行/读不了）。合成一个桶就是把「查不了」印成
            # 「查过了，不是语料」——本仓反复咬中的形状。故带上失败计数，
            # 渲染面据此分开措辞。
            skipped.append((path, st.get("lines", 0), bad))
    return corpus, skipped


OBS_MARKER = "RUN_KIND.json"


def observation_runs(roots):
    """观察通道采集目录（判据＝目录里有 `RUN_KIND.json`，不是文件名清单）。

    **为什么必须单列、又必须出现**：两条链口径完全不同——观察通道产物
    （`adapter.log`／`screencap_index.jsonl`／`mark_rtt.jsonl`…）喂
    `validate_results.py` 会 exit 1（contract VIOLATIONS），结构上进不了 wire 池，
    所以**绝不能相加**；但也**不能因此当它不存在**：一整个设备窗跑完，
    自称「进展单一事实源」的台账若一个数都不动，那是台账失职。此前它们只以
    `screencap_index.jsonl` 的身份落进「跳过（非语料）」那个桶——真实测量数据
    与 README/配置挤在同一句措辞下（D-332 无名桶、D-326 同名不同义）。

    **判据取自既有写者**（`e234_collect` 经 `e234_common.write_run_kind` 落盘），
    不猜文件名——文件名清单会漏（D-273），而标记是采集器自己写的。
    **不跨 lane import**：`scripts/` 无导入 `tools/` 的先例，故此处直读该 JSON，
    只取 `kind`/`experiments`/`pkg`；读不了就如实记 `error`，不静默丢（D-330）。
    **边界**：早于该标记的采集目录（如 `evidence/e1/20260801-*`）没有它，仍落在
    通用桶里——**宁可少认不误认**；这条边界写在这里，而不是留给读者猜。
    """
    import json as _json
    runs = []
    for root in roots:
        for p in sorted(glob.glob(os.path.join(root, "**", OBS_MARKER),
                                  recursive=True)):
            d = os.path.dirname(p)
            row = {"path": d.replace(os.sep, "/")}
            try:
                with io.open(p, encoding="utf-8") as fh:
                    meta = _json.load(fh)
                row["kind"] = meta.get("kind") or "?"
                row["experiments"] = ",".join(meta.get("experiments") or []) or "—"
                row["pkg"] = meta.get("pkg") or "—"
            except (OSError, ValueError) as e:
                row["error"] = type(e).__name__
            try:
                row["files"] = sum(1 for f in os.listdir(d)
                                   if os.path.isfile(os.path.join(d, f)))
            except OSError:
                row["files"] = 0
            runs.append(row)
    return runs


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
    aqs_runs = low_conf = aqs_versioned = 0
    scn_total = 0
    for r in real:
        labels = cc.campaign_labels(r)
        for k in by:
            by[k][labels.get(k) or cc.UNLABELED] += 1
        if r.get("aqs_version"):
            aqs_versioned += 1        # 顶层版本戳：与「出了分」是两个量
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
            "aqs_runs": aqs_runs, "low_conf": low_conf,
            "aqs_versioned": aqs_versioned}


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
            # 三张表全 None = 这个文件读不出任何本项目的表（损坏/根本不是
            # ANEB 库）。只靠内层 except 时它会渲染成三个「—」，与「表不存在」
            # 无从区分——docstring 承诺的「读不了如实记」就落空了（sqlite3
            # 对非法文件在 connect 不抛、在 execute 才抛，被内层吞成 None）。
            if all(row.get(k) is None for k in ("runs", "scenarios",
                                                "voice_rows")):
                row["error"] = "no readable ANEB table"
        except sqlite3.Error as e:
            row["error"] = str(e)
        out.append(row)
    return out


def render_md(corpus, skipped, real, synth, st, bk, dbs, obs=()):
    n = lambda c: "、".join(f"{k}×{v}" for k, v in cc.ranked(c)) or "—"
    lines = [MD_HEADER]
    lines.append("## 一、wire 语料（真实测量，run_id 去重后）\n")
    lines.append(f"- **真实 run 总数：{len(real)}**（场景 {bk['scn_total']}；"
                 f"文件 {len(corpus)} 份、原始行 {st.get('lines', 0)}、"
                 f"跨文件重复 {st.get('duplicates', 0)} 条已去、"
                 f"body 冲突 {len(st.get('conflicts') or [])} 条单记、"
                 f"坏行 {st.get('malformed', 0)}、无 run_id {st.get('no_run_id', 0)}）")
    lines.append(f"- 合成记录（`is_synthetic`）：**{len(synth)} 条，单列不计入上行**")
    # 警告要印在会被误加的那个数**旁边**，不能只印在第四节里（D-330／D-339：
    # 门说了而摘要没说，等于读者最先看的那一行仍然缺信息）。
    if obs:
        # 真机与 dry-run **不能合成一个数**——这与本节把 `is_synthetic` 单列是
        # 同一个角色（D-341：刚写完的修复要立刻当被审对象再问一遍同类。初版
        # 印「13 个采集目录」，其中 6 个是 dry-run，正是本台账要拦的那种合并）。
        real_dirs = sum(1 for r in obs if r.get("kind") == "DEVICE_REAL")
        lines.append(f"- 观察通道另有 **{real_dirs} 个真机采集目录**"
                     f"（dry-run {len(obs) - real_dirs} 个单列不计入；第四节）——"
                     f"**不并入上行**：其产物结构上进不了 wire 池")
    lc = (f"{bk['low_conf']}/{bk['aqs_runs']}"
          f"（{bk['low_conf'] / bk['aqs_runs'] * 100:.0f}%）"
          if bk["aqs_runs"] else "0/0（无带分 run，无从判断）")
    # 「带 AQS」有两种数法，差一条也要说清是哪一种（同名不同义比不同名更危险，
    # D-326）：本行按 **run.aqs.score 非空**（真出了分）计；顶层 `aqs_version`
    # 是另一个量——有版本戳不等于出了分（实测差 1 条：有版本、无分数）。
    _vonly = bk["aqs_versioned"] - bk["aqs_runs"]
    lines.append(f"- 带 AQS **分数**的 run（`run.aqs.score` 非空）：{bk['aqs_runs']}；"
                 f"其中 low_confidence：{lc}"
                 f"｜顶层 `aqs_version` 版本戳共 {bk['aqs_versioned']} 条，"
                 f"其中 **{_vonly} 条只有版本戳、没有分数**（两个量不可混用）\n")
    lines.append("| 维度 | 分布（run 计） |\n|---|---|")
    for k, title in (("campaign_id", "战役"), ("point_id", "点位"),
                     ("carrier", "运营商"), ("time_band", "时窗")):
        cell = n(bk["by"][k])
        if k == "point_id":
            ph = [p for p in bk["by"][k] if str(p).startswith("PENDING-")]
            if ph:
                cell += ("（**%s 是占位符不是点位**：真名待回填，"
                         "不可当作一个真实站点计入覆盖）" % "、".join(sorted(ph)))
        lines.append(f"| {title} | {cell} |")
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
    plain = [p for p, _, bad in skipped if not bad]
    broken = [(p, bad) for p, _, bad in skipped if bad]
    if plain:
        lines.append("\n跳过（0 条契约记录，非语料）：" +
                     "、".join(f"`{p.replace(os.sep, '/')}`" for p in plain))
    if broken:
        # 装载失败 ≠ 不是语料：前者是「查不了」，要单独喊出来，否则一份
        # 坏掉的语料文件会静静地被算成「本来就不该计入」。
        lines.append("\n⚠ **装载失败（坏行/读不了，不等于「不是语料」）**：" +
                     "、".join(f"`{p.replace(os.sep, '/')}`（{bad} 处）"
                               for p, bad in broken))
    lines.append("\n## 四、观察通道采集（与第一节**不可相加**——两条链口径不同）\n")
    if not obs:
        lines.append(f"（本次扫描未发现带 `{OBS_MARKER}` 标记的采集目录。）")
    else:
        lines.append("| 目录 | kind | 实验 | 包名 | 文件数 |\n|---|---|---|---|---|")
        for r in obs:
            if "error" in r:
                lines.append(f"| {r['path']} | **读不了**（{r['error']}） | — | — |"
                             f" {r['files']} |")
            else:
                pkg = f"`{r['pkg']}`" if r["pkg"] != "—" else "—"
                lines.append(f"| {r['path']} | {r['kind']} | {r['experiments']} |"
                             f" {pkg} | {r['files']} |")
        lines.append(f"\n> 这些目录**产出 0 条 wire run**——产物喂 "
                     f"`validate_results.py` 即 contract VIOLATIONS。列在这里是为了"
                     f"让「一个设备窗跑完、台账一个数都不动」不再发生，**不是**为了相加。"
                     f"判据＝目录里有 `{OBS_MARKER}`（采集器自己写的标记，非文件名清单）；"
                     f"早于该标记的采集目录不在此表，仍落在第三节的通用桶里。")
    lines.append("")
    return "\n".join(lines)


def render_csv_rows(real, synth, bk, obs=()):
    rows = [("total", "real_runs", len(real)),
            ("total", "synthetic_records", len(synth)),
            ("total", "scenarios", bk["scn_total"]),
            ("total", "aqs_runs", bk["aqs_runs"]),
            ("total", "aqs_versioned_runs", bk["aqs_versioned"]),
            ("total", "low_confidence_runs", bk["low_conf"])]
    for k in ("campaign_id", "point_id", "carrier", "time_band"):
        rows += [(k, key, cnt) for key, cnt in cc.ranked(bk["by"][k])]
    rows += [("rat_scenarios", key, cnt) for key, cnt in cc.ranked(bk["rat"])]
    rows += [("validity_scenarios", key, cnt)
             for key, cnt in cc.ranked(bk["validity"])]
    # 机器面与 md 面同批加（D-303：只改一面等于让两面无声分叉）。face 用
    # `observation` 而非 `total`，因为 `total` 那族是可以互相印证的 wire 量，
    # 而它恰恰**不属于**那族——面名本身就是「别相加」的第一道提示。
    # 刻意**不出**一个合计行：真机与 dry-run 相加没有任何用途，而一个印好的
    # 合计数就是邀请别人去用它（第一节把合成单列，是同一条理由）。
    _dev = sum(1 for r in obs if r.get("kind") == "DEVICE_REAL")
    rows.append(("observation", "device_real_dirs", _dev))
    rows.append(("observation", "dry_run_dirs", len(obs) - _dev))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="ANEB 语料台账（进展的单一事实源）")
    ap.add_argument("--root", action="append",
                    help="语料根目录，可重复；默认 evidence + server/data/results")
    ap.add_argument("--md", default=os.path.join("docs", "CORPUS_LEDGER.md"))
    ap.add_argument("--csv", default=os.path.join("docs", "CORPUS_LEDGER.csv"))
    a = ap.parse_args(argv)
    roots = a.root or DEFAULT_ROOTS
    corpus, skipped = discover(roots)
    real, synth, st = summarize([p for p, _, _ in corpus])
    bk = buckets(real)
    # Room 库只在 evidence 侧（server 落盘没有），扫描根仍取第一个
    dbs = room_dbs(roots[0])
    obs = observation_runs(roots)
    md = render_md(corpus, skipped, real, synth, st, bk, dbs, obs)
    io.open(a.md, "w", encoding="utf-8", newline="").write(md)
    import csv as _csv
    with open(a.csv, "w", newline="", encoding="utf-8-sig") as f:
        w = _csv.writer(f)
        w.writerow(["face", "key", "count"])
        for row in render_csv_rows(real, synth, bk, obs):
            w.writerow(row)
    broken_n = sum(1 for _, _, bad in skipped if bad)
    print(f"real_runs={len(real)} synthetic={len(synth)} "
          f"files={len(corpus)} skipped={len(skipped)}"
          + (f" (其中装载失败 {broken_n})" if broken_n else "")
          + f" obs_dirs={len(obs)}")
    print(f"written: {a.md}, {a.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
