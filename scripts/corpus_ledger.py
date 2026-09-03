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


def missing_roots(roots):
    """返回**配置了却不存在**的扫描根。

    为什么需要它（2026-08-30，v4 的 worktree 试点实证）：`server/data/` 被 `.gitignore`
    挡住、**零个受跟踪文件** ⇒ **任何全新 worktree 里该目录根本不存在**；主树里它在，
    只是因为长期积累。而 `DEFAULT_ROOTS` 含 `server/data/results` ⇒
    **同一份代码在 worktree 里算出一个不同的语料范围，不报错，只给一个不同的数**
    ——而这个数正是台账、正是「进展」声明的单一事实源。

    ⇒ 这与 `discover()` 里已经写下的那条是**同一条原则、不同成因**：
    「**一个自称『单一事实源』的台账不该有无声排除**」。
    那次的成因是**根没配**（漏扫 server 落盘），这次是**根不存在**（worktree）。
    **「根不在」与「根里没有语料」在结果上完全同形**——都是少一批数、都不吭声。
    """
    if isinstance(roots, str):
        roots = [roots]
    return [r for r in roots if not os.path.isdir(r)]


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

# 无点位标签那一桶——它不是一个点位（D-332：无名桶要有名字，且不得混进有序
# 集合）。**桶名走 `cc.UNLABELED` 不另写字面量**：我初版在这里自定义了一份，
# 被既有守卫 `test_the_unlabeled_bucket_is_spelled_in_exactly_one_place` 当场
# 逮住——改桶名时留下一份对不上的抄件，正是它钉的那件事（D-264 单一来源）。
UNLABELED_POINT = cc.UNLABELED

# **不是外场点位**的显式清单。手写清单会漏，所以它只做减法、且**逐条印在正文里**
# ——读者看得见「按外场计入了哪些」，可审计胜过看不见的分类。
# 默认新点位算外场（外场是常态）；反过来默认不算，会让新外场点位悄悄不进数，
# 那个方向更糟。代价是新增室内点位需要有人来加这一行，而它印在正文里，看得见。
NON_FIELD_POINT_IDS = ("home_indoor",)


def is_placeholder_point(pid):
    """占位符点位（真名待回填），不是一个真实站点。

    抽成具名谓词是为了让「维度表的标注」与「单点位行项」**共用同一判断**——
    两处各写一个 `startswith` 就是 §2.14 那种会各自漂的同名实现。
    """
    return str(pid).startswith("PENDING-")


def field_points(bk):
    """具名外场点位 → run 数，降序。排除占位符、无标签桶、已知非外场点位。

    **为什么要有这个函数**：此前「外场单点位有多少」只能让读者自己从维度表
    四个桶里挑一个——**能自己挑就能挑错**，而 2026-08-29 挑错的那次正好落在
    PO 页头条（写 73，实为 57；73 是一次自造扫描的假象数）。给它一个有名字的
    行项，引用者就不必挑。
    """
    out = [(p, c) for p, c in bk["by"]["point_id"].items()
           if p != UNLABELED_POINT and not is_placeholder_point(p)
           and p not in NON_FIELD_POINT_IDS]
    return sorted(out, key=lambda kv: (-kv[1], str(kv[0])))


# 观察目录的三分类（D-676⑤ 立第三类）。**判定只写一处**：`render_md` 与
# `render_csv_rows` 都调它 —— 同一分类写两处必有一处先漂，而漂的那处不报错。
#
# ⚠ **为什么必须在回填 `RUN_KIND.json` 的同一笔里加这一类**：`dry_run_dirs` 原本是
# `len(obs) - device_real`，即**「不是真机的都算干跑」**。E-03 十二格一旦带上标记，
# 就会被算成十二个**干跑格** —— **把真花了配额的 API 抓取标成 dry run**。
# **缺一个数只是不可见，错一个数会被人当真用**；本文件的出身正是拦这种合并
# （见下方 `real_dirs` 处注释：初版把 6 个 dry-run 并进「13 个采集目录」）。
API_CMP_KIND = "api_cmp"      # 名字钉死防漂（D-676⑤）


def classify_obs(obs):
    """-> (device_real, api_cmp, dry_run) 三个计数。**三者相加恒等于 len(obs)。**"""
    dev = sum(1 for r in obs if r.get("kind") == "DEVICE_REAL")
    api = sum(1 for r in obs if r.get("kind") == API_CMP_KIND)
    return dev, api, len(obs) - dev - api


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
        real_dirs, api_dirs, dry_dirs = classify_obs(obs)
        lines.append(f"- 观察通道另有 **{real_dirs} 个真机采集目录**"
                     f"（dry-run {dry_dirs} 个、API 对照批 {api_dirs} 个，"
                     f"**三者各自单列、均不计入上行**；第四节）——"
                     f"其产物结构上进不了 wire 池")
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
    # 单点位口径**给成有名字的行项**，别让引用者自己从维度表挑（挑得动就挑得错，
    # 2026-08-29 PO 页头条写 73、实为 57 即此）。**数字与点位 id 绑在一起给**：
    # 数字被搬进别的文档后，才不会失去「它是哪个点」这条信息。
    fps = field_points(bk)
    if fps:
        pid, cnt = fps[0]
        rest = "、".join("`%s` %d" % (p, c) for p, c in fps[1:]) or "无"
        excl = []
        ph = sorted(p for p in bk["by"]["point_id"] if is_placeholder_point(p))
        for p in ph:
            excl.append("`%s` %d（占位符，真名待回填，**不是第二个点位的证据**）"
                        % (p, bk["by"]["point_id"][p]))
        for p in NON_FIELD_POINT_IDS:
            if p in bk["by"]["point_id"]:
                excl.append("`%s` %d（非外场）" % (p, bk["by"]["point_id"][p]))
        if UNLABELED_POINT in bk["by"]["point_id"]:
            excl.append("无点位标签 %d（不是一个点位）"
                        % bk["by"]["point_id"][UNLABELED_POINT])
        lines.append(f"- **单点位最大样本：`{pid}` {cnt} 条**"
                     f"（其余具名外场点位：{rest}）"
                     f"｜**已排除**：{'；'.join(excl) or '无'}")
        lines.append("  > 引用「（外场）单点位有多少」**直接引本行**，"
                     "不要自己从下方维度表里挑——能自己挑就能挑错。")
    lines.append("| 维度 | 分布（run 计） |\n|---|---|")
    for k, title in (("campaign_id", "战役"), ("point_id", "点位"),
                     ("carrier", "运营商"), ("time_band", "时窗")):
        cell = n(bk["by"][k])
        if k == "point_id":
            ph = [p for p in bk["by"][k] if is_placeholder_point(p)]
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
    _dev, _api, _dry = classify_obs(obs)
    rows.append(("observation", "device_real_dirs", _dev))
    rows.append(("observation", "api_cmp_dirs", _api))
    rows.append(("observation", "dry_run_dirs", _dry))
    # 机器面同样给具名行项：**机器消费方也不该自己去挑哪个是外场最大点**。
    # key 用点位 id（不是 "max"），数字与身份于是一起进 CSV，搬不散。
    for pid, cnt in field_points(bk)[:1]:
        rows.append(("field_point_max", pid, cnt))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="ANEB 语料台账（进展的单一事实源）")
    ap.add_argument("--root", action="append",
                    help="语料根目录，可重复；默认 evidence + server/data/results")
    ap.add_argument("--md", default=os.path.join("docs", "CORPUS_LEDGER.md"))
    ap.add_argument("--csv", default=os.path.join("docs", "CORPUS_LEDGER.csv"))
    ap.add_argument("--check", action="store_true",
                    help="只比不写：落盘的两面与现算是否一致（exit 1=不一致）")
    a = ap.parse_args(argv)
    roots = a.root or DEFAULT_ROOTS
    # **前提检查排在「算」之前**：根不存在时算出来的是一个**更小但看起来正常**的数，
    # 而这个数正是台账、正是「进展」声明的单一事实源 ⇒ 宁可拒算，不可静默少算。
    # ⚠ 本检查 2026-08-30 首版**只定义了 `missing_roots()` 却没人调用**——
    # 函数在、测试也绿（那条测试只测函数本身），而生产路径一次都没走过它。
    # 正是本仓那条「**写好了一道门 ≠ 那道门在门禁清单上**」，这次是我自己犯的。
    gone = missing_roots(roots)
    if gone:
        # ⚠ 这一行必须打到 **stdout** 且必须带 `corpus ledger check:` 前缀：
        # `verify_all.ps1` 的判词是**捞含该前缀的那一行**，捞不到就把 NOT_EXECUTED
        # 写成一句空判词。首版（我加的）只写了下面那段 stderr、没打这行标记
        # ⇒ 摘要面只剩「corpus-ledger-fresh  NOT_EXECUTED」六个字，**读者分不出
        # 「缺根/环境不对」和「别的没比成」**。而 D-609③ 给这条路径的定位正是
        # **响亮拒算** —— 响亮丢在摘要面上就等于没响（「摘要面才是被执行的那面」）。
        # ⚠ 复用状态词 CANNOT_COMPARE 是对的（两条 RC=2 回答同一个问题＝「为什么没比成」），
        # 但**成因必须写在同一行**：状态相同、处置不同（这条＝回主树；那条＝先确认 cwd）。
        print("corpus ledger check: CANNOT_COMPARE —— 扫描根不存在：%s"
              "（多半在 git worktree 里；处置＝回主树跑，或 --root 显式声明范围）"
              % ", ".join(gone))
        sys.stderr.write(
            "拒算：扫描根不存在 —— %s\n"
            "  这多半意味着你在一个全新的 git worktree 里（`server/data/` 被 .gitignore 挡、"
            "零受跟踪文件，故任何新 worktree 里它都不存在）。\n"
            "  **别把这里算出的数当台账**：少一个根＝少一批语料，而结果看起来完全正常。\n"
            "  处置：回主树跑；或用 --root 显式声明你真正想扫的范围。\n"
            % ", ".join(gone))
        return 2
    corpus, skipped = discover(roots)
    real, synth, st = summarize([p for p, _, _ in corpus])
    bk = buckets(real)
    # Room 库只在 evidence 侧（server 落盘没有），扫描根仍取第一个
    dbs = room_dbs(roots[0])
    obs = observation_runs(roots)
    md = render_md(corpus, skipped, real, synth, st, bk, dbs, obs)
    import csv as _csv
    import io as _io
    _buf = _io.StringIO()
    _w = _csv.writer(_buf, lineterminator="\r\n")
    _w.writerow(["face", "key", "count"])
    for row in render_csv_rows(real, synth, bk, obs):
        _w.writerow(row)
    csv_text = _buf.getvalue()

    if a.check:
        # 「勿手编」此前只是一句话——没有任何东西核对它，手改能活到下次重算
        # （而下次重算可能在很久以后，期间这两面一直被当作单一事实源引用）。
        # **只比不写**：落盘那份必须与现算逐字节相同。不一致有两种成因——有人
        # 手改了，或语料变了而没重算——**两者都该红**，因为两者的后果一样：
        # 被引用的数字不再是当前语料算出来的。
        # ⚠ **「读不了」不是 DRIFT**（2026-08-30 实测）：本门曾在一次 `-Scope all` 里
        # 报 `DRIFT`，而日志里真正的话是 `No such file or directory: docs\CORPUS_LEDGER.md`
        # ——**台账没问题，是这次跑的工作目录不对**（本门当时未 `Push-Location`，
        # 相对路径落在了别处）。可 `DRIFT` 的处置句写着「重算并提交」⇒
        # **它会指使人去重算一份本来就正确的台账，并提交一个由错误 cwd 算出的结果。**
        # ⇒ **判词必须点对成因**：比不了（文件不在／读不了）与比过了不一致，是两件事。
        drift, unreadable = [], []
        for path, want, enc in ((a.md, md, "utf-8"),
                                (a.csv, csv_text, "utf-8-sig")):
            try:
                got = io.open(path, encoding=enc, newline="").read()
            except OSError as e:
                unreadable.append("%s 读不了：%s" % (path, e))
                continue
            if got != want:
                drift.append("%s 与现算不一致（落盘 %d 字符 / 现算 %d 字符）"
                             % (path, len(got), len(want)))
        if unreadable:
            # 第三态：**没比成**。既不宣布一致，也不宣布漂移。
            # 成因写进**同一行**：门只把这一行当判词，写在后续行里到不了摘要面。
            print("corpus ledger check: CANNOT_COMPARE —— 落盘文件读不了（%d 个）"
                  "（先确认 cwd 是仓根，本门默认路径是相对路径）" % len(unreadable))
            for u in unreadable:
                print("  " + u)
            for d in drift:
                print("  " + d)
            print("  处置：**先确认工作目录是仓根**（本门的默认路径是相对路径），"
                  "别急着重算——重算不会让文件出现在一个错的 cwd 下。"
                  "确认在仓根后仍读不到，才是文件真的缺了。")
            return 2
        print("corpus ledger check: %s" % ("DRIFT" if drift else "in sync"))
        for d in drift:
            print("  " + d)
        if drift:
            print("  处置：跑 `python scripts/corpus_ledger.py` 重算并提交，"
                  "不要手改这两份文件。")
        return 1 if drift else 0

    io.open(a.md, "w", encoding="utf-8", newline="").write(md)
    io.open(a.csv, "w", encoding="utf-8-sig", newline="").write(csv_text)
    broken_n = sum(1 for _, _, bad in skipped if bad)
    print(f"real_runs={len(real)} synthetic={len(synth)} "
          f"files={len(corpus)} skipped={len(skipped)}"
          + (f" (其中装载失败 {broken_n})" if broken_n else "")
          + f" obs_dirs={len(obs)}")
    print(f"written: {a.md}, {a.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
