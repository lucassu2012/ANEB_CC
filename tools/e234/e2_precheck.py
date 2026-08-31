#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2 适用性**前置**断言 —— 开跑前几秒回答「这一格值不值得开 e2」。

判据（T81 §7-2，采集侧提、大脑 2026-08-30 派）：
**「该 App 在思考期，两条通道须同时静默」**。仓里已有反例——`ObsStats.kt` 记着
DeepSeek 型「思考期播放生成动画」栈：持续 CONTENT、无 >gap 静默 ⇒ `ttftClusterMs=null`。
**画面在动 ⇒ C 永不静默 ⇒ 门限取什么都没用，C 的次簇根本不是 A2。**

## 但这只是第二个问题。第一个问题是「这套装置看得见静默吗」

`e2_analyze` 在 C 侧对**去重后的帧序列**做簇分割，把 >gap 的间隔当作思考静默。
**这一步默认了帧序列是连续观测的，而它不是。**

`dumpsys SurfaceFlinger --latency` 读的是**环形缓冲**（本机实测固定 127 行/次），
采集器按 `--framestats-period-s`（默认 20s）周期 dump。**若两次 dump 之间渲染的帧
超过环缓冲深度，中间的帧就永远丢了** —— 而丢帧在去重后的序列里长得**和静默一模一样**：
都是一个「相邻两帧相距很远」的间隔。

⇒ **在判「App 静不静」之前，必须先把「记录连不连」判出来。**
两者混在一起时，工具会把采集排期的洞读成 App 的思考静默 —— 这正是本仓反复付学费的
「**验时量法失败与目标缺席长得一样**」那一族。

## 相邻两次 dump 的三态（本模块的核心）

拿两次 dump 各自的有效帧集合比对：

- **identical**（集合完全相同）⇒ 这段时间**一帧都没渲染** ⇒ **这是被证明的静默**，不是洞。
- **overlap**（交集非空但不等）⇒ 帧数没顶破环缓冲 ⇒ **这段是连续观测的**。
- **disjoint**（交集为空）⇒ 期间渲染的帧**多于环缓冲深度** ⇒ **确证丢帧** ⇒
  跨越该边界的任何「间隔」**不可判**，既不能算静默也不能算非静默。

⚠ **`identical` 必须算作「已观测」而不是「洞」** —— 本判据的初版把覆盖率按
「帧时戳跨度 / 会话跨度」算，于是把「什么都没发生」算成了「什么都没看见」，
得出 19–37% 的假覆盖率。**一个自造的中间量，只要它听起来合理，就足以撑起一整段错的叙述。**

⚠ 但**承重的只有 `disjoint` 这一支**：`identical` 与 `overlap` 在 `classify_pairs`
里走同一分支（都只延长 `hi`），且 identical 的两次 dump 跨度相同 ⇒ 在那里断不断刀
都不改变任何区间的覆盖性。突变审计实测为**等价突变**（`mutation_audit.py` M13 记录）。
两者的计数仍照报——它对操作者有用（`identical` 多＝App 大段空闲），
但**它是诊断量，不是判据**。写在这里是因为我差点把它当成安全关键写进文档：
**「我为某个判断写了一条分支」不等于「那个判断在承重」。**

## 三态判定（三者互不代偿；**判词刻意不与产线四态共用 token**，理由见下方常量处）

- **`WORTH_RUNNING`**：C 侧已观测间隔 ≥ `MIN_OBSERVED_GAPS`、不可判数不多于可核数，
  **且 A 侧可用轮数也够** ⇒ 值得开 e2。
- **`NOT_APPLICABLE`**：**全程连续覆盖（零 disjoint）且一次 ≥gap 静默都没有** ⇒
  App 真的不静默，e2 对该 App/场景**结构性不适用**，加轮数不解。
- **`CANNOT_TELL`**：装置判不了 —— 无帧 / 记录太碎 / 两通道互相矛盾 / **A 侧不足或查不了**。

⚠ **A 侧是首版漏掉的一半**：判据原文写的是「**两条通道**须同时静默」，而首版只做了
C 侧（＋B 作反驳）。结果对首窗五格中的两格给出 `PASS`，而 `e2_analyze` 实跑
`NOT_EXECUTED`——它们栽在 A 侧（3/8、4/6 轮）。**`|t_A−t_C|` 的每个样本都要两侧
同时切得出次簇，所以 A 侧可用轮数是 n 的另一个上界。**
**瓶颈在哪决定修法**：C 侧不足或记录碎 ⇒ 改采集周期有救；**A 侧不足改周期毫无用处**。

**`NOT_APPLICABLE` 与 `CANNOT_TELL` 绝不可混**：前者是「App 不静默」，后者是「我们没看见」。
把后者写成前者，会让人取消一个本来可行的测量；反过来会让人再烧一格。
故 **`NOT_APPLICABLE` 要求零 disjoint**（全程连续才敢说「从未」），不设任何自造时长门限。
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import e234_common as ec    # noqa: E402
import e234_session as es   # noqa: E402

PENDING_NS = (1 << 63) - 1

# 通道 B 的翻转阈值：与 `e2_analyze` 调 `screencap_sampling_stats` 时用的同一个 8.0。
# **不另取一个**——同一个物理判断在两处用两个阈值，是 D-326（同名不同义）的镜像。
B_FLIP_THRESHOLD = 8.0

# 需要多少次**可核**静默才敢说「值得开 e2」。
#
# **这不是一个新门限，是 e2 自己那道门的算术下界**（故不需要独立的敏感性分析背书）：
# `e1_analyze.GATE_MIN_N` = 5 表示 e2 的 `|t_A-t_C|` 判定在 n<5 时直接 NOT_EXECUTED；
# 而**每一个 n 都要求该轮 C 侧切得出次簇**，即至少一次 ≥gap 的静默。
# ⇒ 少于 5 次已观测间隔时，e2 连自己的门都到不了。取值随 GATE_MIN_N 走，不写死。
MIN_OBSERVED_GAPS = ec.ea.GATE_MIN_N

# ── 本工具的判词**刻意不与产线四态共用 token**（v2 2026-08-30 核出，D-326 形状）──
#
# 初版直接用了 `PASS/FAIL/NOT_EXECUTED`，于是 `NOT_EXECUTED` 在同一份判读页里有了两个意思：
# 本工具的＝「**C 侧的次簇多半是 dump 洞，别信这个数**」；`e2_analyze` 的＝「**样本不够，没算**」。
# **后果当场发生**：我写下「首窗五格全部 NOT_EXECUTED」，读起来是「e2 从没出过判词」，
# **而 `cell_f2` 出过**（FAIL，n=6 dropped=0）——**而且那正是我自己先前称作
# 「本批第一格让 e2 真正跑起来的」那一格**。**新工具悄悄盖掉了我自己先前正确的实测，两边都不报错。**
#
# ⇒ 三个判词换成本工具专用的动词短语：它们回答的是「**要不要跑**」，
# 而四态回答的是「**跑了没有 / 跑出什么**」——**本来就是两个问题，不该共用词。**
# ⚠ 但**子测量仍用四态**（`channel_a["status"]` / `channel_b["status"]`）：
# 那一层问的确实是「这次测量执行了吗」，正是四态的本义。同一份 JSON 里两套词各司其职，
# 别把它们统一——统一才是这次事故的成因。
WORTH_RUNNING = "WORTH_RUNNING"      # 值得开 e2
NOT_APPLICABLE = "NOT_APPLICABLE"    # 该 App/场景结构性不适用，加轮数不解
CANNOT_TELL = "CANNOT_TELL"          # 装置判不了：记录太碎 / 两通道矛盾 / A 侧查不了


def split_dumps(text):
    """`sf_latency.txt`（多次 dump 追加而成）-> [[actual_ns, ...], ...]，逐次 dump 分开。

    每次 dump 的首行是刷新周期（单 token），其后是三列帧行。**按单 token 行切段**。

    警告：别用 `awk NF==1` 数这件事 —— 本仓实测 dump 之间还夹着一个**孤立回车**，
    awk 把它当成一个字段，数出来的 dump 次数**正好是真值的两倍**。
    「正好 2 倍」是最危险的错：它看起来像一条干净的结构性事实（「每次两个标记」），
    而且当时另有一个来源不同的量（framestats 的 PROFILEDATA 计数）**恰好也是那个双倍值**
    ——**两个数因不同机制而巧合相等，与互证长得一模一样**。
    Python 的 `strip()` 把孤立回车清成空行，故本函数天然免疫；写下这条是为了让下一个
    拿别的量法来核的人不必再栽一次。
    """
    out, cur = [], None
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        parts = s.split()
        if len(parts) == 1:
            if cur is not None:
                out.append(cur)
            cur = []
        elif cur is not None and len(parts) >= 3:
            try:
                _desired, actual, ready = int(parts[0]), int(parts[1]), int(parts[2])
            except ValueError:
                continue
            # 待定帧一律剔除，与 `e1_analyze.parse_sf_latency` 同口径（R-10）。
            if actual in (0, PENDING_NS) or ready in (0, PENDING_NS):
                continue
            cur.append(actual)
    if cur is not None:
        out.append(cur)
    return [sorted(set(d)) for d in out if d]


# 图层失效判据的门限（T90／D-644）。**从数据标定，不是拍的**：
# 全仓 27 个格实测存活率呈双峰且中间是空的 —— 健康格**无一例外恰好 100.0%**
# （含 `wifi_f6` 583/583 的长跑），异常格 68.2%（`wifi_f1_VOID2`，本就已作废）
# 与 7.9%（`wifi_f6_b_VOID1`，图层失效）。空区是 (68.2, 100)，门限切在其中任何
# 一处等价，取 0.95 只为留裕量。
DUMP_SURVIVAL_FLOOR = 0.95
# 太少的样本不套比例判据：退化跑（发出 1～5 次）会以 0% 命中，而它们的病因是
# 「根本没跑起来」不是「图层死了」——**两种病共用一个判词会把下游引向错的修法**。
DUMP_SURVIVAL_MIN_N = 3


def count_issued_dumps(text):
    """**发出**了几次 `--latency`（不管有没有取到帧）。

    判据＝单 token 行数，与 `split_dumps` 的切段判据同源：每次 dump 的首行是
    刷新周期。图层失效时响应**不是空的**——它有那一行头、只是零帧行
    （实测尾部逐段 `16666666` 后直接跟空行，退出码 0、stderr 空）。
    ⇒ **这个数是唯一能把「没发生」与「发生了但取空」分开的量**，
    而它此前从未被任何人记下来过。

    ⚠ 别用 `awk NF==1` 数它（见 `split_dumps` 的警告：dump 之间夹着孤立回车，
    awk 把它当字段，数出来正好是真值的两倍）。Python 的 `strip()` 天然免疫。
    """
    n = 0
    for line in (text or "").splitlines():
        s = line.strip()
        if s and len(s.split()) == 1:
            n += 1
    return n


def parse_ring_shape(text):
    """-> (refresh_period_ns, ring_depth_rows)。环缓冲的**容量**，不是本场的内容。

    `ring_depth` 取各次 dump 的**最大原始行数**（本机实测恒为 127）：这是缓冲区的
    深度上界，而深度乘以一帧的时长，就是「满速渲染时这只缓冲最多能覆盖多长墙钟」。
    """
    period_ns, rows, cur = None, [], None
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        parts = s.split()
        if len(parts) == 1:
            if cur is not None:
                rows.append(cur)
            cur = 0
            if period_ns is None:
                try:
                    period_ns = int(parts[0])
                except ValueError:
                    period_ns = None
        elif cur is not None and len(parts) >= 3:
            cur += 1
    if cur is not None:
        rows.append(cur)
    return period_ns, (max(rows) if rows else 0)


def classify_pairs(dumps):
    """相邻 dump 两两比对 -> ({'identical','overlap','disjoint'} 计数, 连续覆盖区间)。

    `runs` 是 [(lo_ns, hi_ns)]，每段内部**帧序列连续可信**；disjoint 处断段，
    跨越断点的间隔不可判。
    """
    counts = {"identical": 0, "overlap": 0, "disjoint": 0}
    if not dumps:
        return counts, []
    runs, lo, hi = [], dumps[0][0], dumps[0][-1]
    for i in range(1, len(dumps)):
        prev, cur = set(dumps[i - 1]), set(dumps[i])
        if prev == cur:
            counts["identical"] += 1
            hi = max(hi, dumps[i][-1])
        elif prev & cur:
            counts["overlap"] += 1
            hi = max(hi, dumps[i][-1])
        else:
            counts["disjoint"] += 1
            runs.append((lo, hi))
            lo, hi = dumps[i][0], dumps[i][-1]
    runs.append((lo, hi))
    return counts, runs


def gap_census(dumps, runs, gap_ns):
    """数 ≥gap 的间隔，分成**已观测**（落在同一连续段内）与**不可判**（跨越断点）。

    ⚠ **本函数与 `observed_gaps` 这个键，2026-08-30 由「可核静默 / silence」改名而来**（D-617②）。
    改名的理由不是措辞偏好，是**旧名断言了它没有证明的东西**：
    它证明的只有「**这个间隔从头到尾都在观测之下，期间没有帧到达**」，
    **不证明「这是一次思考停顿」**。

    **触发改名的实测**：`cell_f1b` 的 C 侧最大间隔逐轮复现
    （1591.3 / 1608.1 / 1591.5 / 1607.6 / 1574.8 / 1590.9 ms，位置 120/126 五轮相同），
    这簇值**占了本键计数的一半**（`cell_f1b` 6/12、`wifi_f5` 6/14）。
    ⚠ 但**不要因此认为它们是伪影**——我逐条核过：它们**全部落在单个 dump 的帧跨度之内**，
    是**真实观测到的间隔**。对抗核查由此推出的「逐轮复现 ⇒ 采集排期产物」**不成立**：
    **驱动器是脚本化的，每轮做同样的事，本来就会产生复现的真实行为——复现本身不区分真伪。**
    ⇒ 成立的那半是：**这簇间隔的语义未定**。旧名把「未定」读成了「思考静默」。
    """
    frames = sorted(set(t for d in dumps for t in d))
    verifiable, unjudgeable = [], []
    for i in range(1, len(frames)):
        g = frames[i] - frames[i - 1]
        if g <= gap_ns:
            continue
        inside = any(lo <= frames[i - 1] and frames[i] <= hi for lo, hi in runs)
        (verifiable if inside else unjudgeable).append(g / ec.NS_PER_MS)
    return {"frames_deduped": len(frames),
            "observed_gaps": verifiable,
            "unjudgeable_gaps": unjudgeable}


def channel_b_motion(samples, threshold=B_FLIP_THRESHOLD):
    """通道 B 的**免对齐**统计：相邻采样中 ROI 变化 ≥ 阈值的比例。

    **B 只被允许朝一个方向用**：B 的时戳是宿主侧的、与设备时钟之间隔着一次
    **从未标定过**的 adb 往返（spec §2.2，e2 就是为此不拿 B 做时序）。
    所以这里既不与 C 对齐、也不给时刻，只给一个整场的比例：

    - `rate == 1.0`（**每一对**相邻采样都在动）⇒ ROI 全程没有一刻是静的 ⇒
      **可以反驳** C 侧的「静默」（要么 App 真在动，要么 C 读错了图层）。
    - `rate` 低 ⇒ **什么都不能说**：B 的采样周期是秒级，动画时标是十几毫秒，
      B 看不见不等于没动。**不可反用为「静默的证据」。**

    取 `1.0` 而不是「≥0.9」是刻意的：**一个自造的百分比门限需要自己的依据，
    而「一次都没静过」不需要**。
    """
    if len(samples) < 2:
        return {"status": ec.NOT_EXECUTED, "n": len(samples),
                "reason": "样本 <2，无法构成相邻对"}
    moved = sum(1 for i in range(1, len(samples))
                if abs(samples[i]["roi_mean"] - samples[i - 1]["roi_mean"]) >= threshold)
    pairs = len(samples) - 1
    return {"status": ec.PASS, "n": len(samples), "pairs": pairs,
            "moved_pairs": moved, "motion_rate": moved / float(pairs),
            "threshold": threshold}


def channel_a_anchors(run_dir, pkg, gap_ns):
    """通道 A 侧：有几轮切得出 A2（次簇首事件）。

    **判据原文是「思考期**两条通道**须同时静默」，所以只查 C 侧是不够的。**
    本函数补上 A 侧——它是 2026-08-30 首版漏掉的一半：首版只答了「装置看得见静默吗」
    与「C 侧静不静」，于是对 `wifi_f1_anchor` 给出 `PASS`（C 侧 11 次已观测间隔），
    而 `e2_analyze` 实跑 `NOT_EXECUTED`：**6 轮里 3 轮栽在 A 侧**（该轮不足两簇）。
    ⇒ **一个只查一半的前置断言，会把「值得开 e2」说得比事实更满。**

    **复用 `e2_analyze` 用的同一批函数**（`es.content_events` / `es.segment_turns` /
    `ec.v3_anchors`），不另写一份：口径分叉时不会报错，只会让前置与实跑各说各话（D-315）。
    """
    lines = ec.read_lines(run_dir, "adapter.log")
    if not lines:
        return {"status": ec.NOT_EXECUTED, "reason": "无 adapter.log", "turns": 0,
                "turns_with_anchor": 0}
    evts, _dropped_pkg, _dropped_dim = es.content_events(lines, pkg)
    fit = ec.fit_wall_to_boot(lines)
    marks = es.parse_marks(lines, fit)
    turns, method = es.segment_turns(evts, marks)
    with_anchor = 0
    for t in turns:
        _a0p, a2, _cl = ec.v3_anchors([e["t_boot_ns"] for e in t["events"]], gap_ns)
        if a2 is not None:
            with_anchor += 1
    return {"status": ec.PASS, "turn_method": method, "turns": len(turns),
            "turns_with_anchor": with_anchor, "events_used": len(evts)}


def _verdict(counts, ver, unj, b, a=None):
    """三态判定。**FAIL 与 NOT_EXECUTED 的区分是本模块存在的理由，别合并。**"""
    # 先杀假阳性：两条通道互相矛盾时不许给绿（D-511 fail-closed）。
    if b.get("status") == ec.PASS and b.get("motion_rate") == 1.0 and ver:
        return (CANNOT_TELL,
                "两通道矛盾：C 报 %d 次已观测间隔，而 B 的**每一对**相邻采样都在动"
                "（ROI 全程无一刻静止）⇒ 先查通道 C 的图层是不是选错了" % len(ver))
    if counts["disjoint"] == 0 and not ver:
        return (NOT_APPLICABLE,
                "全程连续覆盖（零丢帧边界）且一次 >=gap 静默都没有 ⇒ "
                "该 App/场景**结构性不适用** e2：C 侧永远切不出次簇，加轮数不解")
    if len(ver) < MIN_OBSERVED_GAPS:
        return (CANNOT_TELL,
                "已观测间隔仅 %d 次 < %d（e2 自己那道门的算术下界）；"
                "另有 %d 个间隔跨越丢帧边界、不可判 ⇒ 先修采集排期再谈适用性"
                % (len(ver), MIN_OBSERVED_GAPS, len(unj)))
    if len(unj) > len(ver):
        return (CANNOT_TELL,
                "记录太碎：不可判间隔 %d > 已观测间隔 %d ⇒ "
                "C 侧的次簇有一半以上可能是 dump 排期的洞，不是思考静默"
                % (len(unj), len(ver)))
    # A 侧：`|t_A-t_C|` 每一个样本都要**两侧同时**切得出次簇，所以 A 侧可用轮数
    # 是 n 的另一个上界。只报 C 侧会把「值得开」说得比事实满（首版即如此，见
    # `channel_a_anchors` 的说明）。
    # A 侧查不了就不许给绿（fail-closed，D-511）：判据要的是**两条通道同时**静默，
    # A 侧缺席时我们只验了一半。**「没查」与「查过没问题」绝不可同判**——
    # 这一支是补 A 侧时顺手堵的：初版把 A 缺席写成「跳过该检查」，于是
    # 一个没有 adapter.log 的目录照样能拿到 PASS，而 PASS 的措辞是「值得开 e2」。
    if not a or a.get("status") != ec.PASS:
        return (CANNOT_TELL,
                "C 侧够了（已观测间隔 %d 次），**但 A 侧查不了**（%s）⇒ "
                "判据要两条通道同时静默，只验一半不给绿"
                % (len(ver), (a or {}).get("reason", "无 channel_a 结果")))
    if a.get("turns") and a["turns_with_anchor"] < MIN_OBSERVED_GAPS:
        return (CANNOT_TELL,
                "C 侧够了（已观测间隔 %d 次），**但 A 侧只有 %d/%d 轮切得出次簇** "
                "< %d ⇒ n 的上界不够；瓶颈在 A 不在 C，加采样周期不解"
                % (len(ver), a["turns_with_anchor"], a["turns"],
                   MIN_OBSERVED_GAPS))
    return (WORTH_RUNNING,
            "已观测间隔 %d 次（>=%d）、不可判间隔 %d 不占多数，A 侧 %s 轮可用 ⇒ 值得开 e2"
            % (len(ver), MIN_OBSERVED_GAPS, len(unj),
               (a or {}).get("turns_with_anchor", "?")))


def precheck(run_dir, pkg=None):
    run_kind = ec.read_run_kind(run_dir).get("kind")
    gap_ns = ec.cluster_gap_nanos()
    res = {"tool": "e2_precheck", "run_dir": run_dir, "run_kind": run_kind,
           "dry_run": run_kind == ec.KIND_DRY_RUN,
           "cluster_gap_ms": gap_ns / ec.NS_PER_MS,
           "min_observed_gaps": MIN_OBSERVED_GAPS,
           "criterion": ("T81 §7-2：思考期两条通道须同时静默"
                         "（先判记录连不连，再判 App 静不静）")}

    sf_text = ec.read_text(run_dir, "sf_latency.txt")
    dumps = split_dumps(sf_text)
    res["dumps"] = len(dumps)

    # ── 仪器自检：发出了几次 dump，其中几次真有帧（T90／D-644）────────────
    # ⚠ `res["dumps"]` 是**过滤之后**的数：`split_dumps` 末尾 `if d` 把空 dump
    # 整批丢弃。`wifi_f6_b_VOID1` 上它显示 45，看着完全健康——而实际发出了 569 次、
    # 524 次取空（图层约 55 秒被重建，采集器只挑过一次图层）。
    # **判词面上少了「分母」这个数，作废格就会表面全绿逐条通过收窗清单。**
    res["dumps_issued"] = count_issued_dumps(sf_text)
    res["dumps_with_frames"] = len(dumps)
    if res["dumps_issued"]:
        res["dump_survival"] = round(len(dumps) / float(res["dumps_issued"]), 4)
    else:
        res["dump_survival"] = None

    if not dumps:
        res["verdict"] = (CANNOT_TELL,
                          "通道 C 无帧记录（sf_latency.txt 缺失或全为待定帧）")
        return res

    # 仪器坏了就别评这一格：**幸存的那些 dump 本身是好的，正因如此才危险**
    # ——它们会拼出一份看着健康的判词，而覆盖的只是会话最前面的一小段。
    if (res["dump_survival"] is not None
            and res["dumps_issued"] >= DUMP_SURVIVAL_MIN_N
            and res["dump_survival"] < DUMP_SURVIVAL_FLOOR):
        res["verdict"] = (CANNOT_TELL,
                          "通道 C 仪器失效：发出 %d 次 dump，仅 %d 次取到帧"
                          "（存活 %.1f%%，健康格实测恒为 100%%）——图层多半在跑动中"
                          "被重建而采集器只挑过一次（T90／D-644）。"
                          "**幸存的 dump 只覆盖失效之前那一小段，不代表整场**"
                          % (res["dumps_issued"], res["dumps_with_frames"],
                             100.0 * res["dump_survival"]))
        return res

    counts, runs = classify_pairs(dumps)
    res["pair_states"] = counts
    res["covered_runs"] = len(runs)
    cen = gap_census(dumps, runs, gap_ns)
    ver, unj = cen["observed_gaps"], cen["unjudgeable_gaps"]
    res["frames_deduped"] = cen["frames_deduped"]
    res["observed_gaps"] = len(ver)
    res["unjudgeable_gaps"] = len(unj)
    res["observed_gap_ms"] = ec.ea.summarize(ver)
    res["unjudgeable_gap_ms"] = ec.ea.summarize(unj)

    # ── dump 周期该设多少：**用第一性原理算，再用实测校**（两条独立的路） ──
    #
    # 路一（主）：环缓冲满速时能覆盖的墙钟上界 ＝ 环深 × 一帧。
    #   本机 127 × 16.667ms ≈ 2.12s。**dump 周期必须短于它**，否则忙时必丢帧。
    # 路二（校）：实测各次 dump 内帧时戳跨度的 p10（忙时环覆盖最短的那一成）。
    #
    # 两条路在本批上落到 2.12s vs 2.09–2.39s —— **它们共享同一个物理机制，
    # 所以这次的一致是真互证**。⚠ 与之相对，本工具注释里记的那次「42 vs 42」
    # 是**两个不同机制凑巧相等**，长得一模一样却毫无证明力：
    # **判断一致算不算互证，要看两条路是否共享机制，不是看数字是否吻合。**
    # 若两者显著背离（实测 p10 远小于理论界），说明该 App 根本达不到满帧率，
    # 此时**以实测为准**——理论界只是上界。
    period_ns, ring_depth = parse_ring_shape(ec.read_text(run_dir, "sf_latency.txt"))
    spans = sorted((d[-1] - d[0]) / 1e9 for d in dumps)
    p10 = spans[max(0, int(0.10 * (len(spans) - 1)))]
    res["ring_depth_rows"] = ring_depth
    res["ring_wallspan_s"] = {"p10": p10, "p50": spans[len(spans) // 2],
                              "max": spans[-1]}
    bound_s = (ring_depth * period_ns / 1e9) if (period_ns and ring_depth) else None
    res["ring_bound_s"] = bound_s
    basis = min(x for x in (bound_s, p10) if x) if (bound_s or p10) else None
    # 留一半余量后向下取整到秒；下界 1s（再短就被 adb 往返本身吃掉）。
    res["recommended_framestats_period_s"] = max(1, int(basis / 2)) if basis else None
    res["period_basis"] = (
        "环深 %s × 一帧 %.3fms = %.2fs（理论界）；实测 p10 %.2fs；取小者的一半"
        % (ring_depth, (period_ns or 0) / ec.NS_PER_MS, bound_s or 0, p10)
        if bound_s else "仅实测 p10 %.2fs（刷新周期行不可解析）" % p10)

    b = channel_b_motion(ec.ea.parse_screencap_index(
        ec.read_jsonl(run_dir, "screencap_index.jsonl")))
    res["channel_b"] = b

    # 目标包默认从 `RUN_KIND.json` 取（采集侧写的那份），不要求调用方再报一次 ——
    # 同一个事实被人手抄第二遍就会有抄错的那一天。
    pkg = pkg or ec.read_run_kind(run_dir).get("pkg")
    res["pkg"] = pkg
    res["channel_a"] = (channel_a_anchors(run_dir, pkg, gap_ns) if pkg else
                        {"status": ec.NOT_EXECUTED,
                         "reason": "RUN_KIND.json 无 pkg，且未经 --pkg 指定",
                         "turns": 0, "turns_with_anchor": 0})

    res["verdict"] = _verdict(counts, ver, unj, b, res["channel_a"])
    return res


def _f(v, nd=1):
    if v is None:
        return "-"
    return ("%.*f" % (nd, v)) if isinstance(v, float) else str(v)


def render_line(res):
    """一行判定 —— 这是**开窗前清单**上会被人真正读到的那一行，不是报告。"""
    v, why = res["verdict"]
    if "pair_states" not in res:
        return "e2_precheck %s: %s - %s" % (os.path.basename(res["run_dir"]), v, why)
    ps, a = res["pair_states"], res.get("channel_a") or {}
    # ⚠ 存活率**只在不足 100% 时出声**（T90）：硬门限 DUMP_SURVIVAL_FLOOR 只拦
    # 灾难性失效，而 96% 那种**部分**退化会从门限底下静默走过去。健康格实测恒为
    # 100%，所以「有话说」本身就是信号；沉默时不占版面，是为了让它出现时刺眼。
    surv = res.get("dump_survival")
    warn = ("" if surv is None or surv >= 1.0
            else " ⚠dump存活=%.1f%%(发出%d/有帧%d)" % (
                100.0 * surv, res["dumps_issued"], res["dumps_with_frames"]))
    return ("e2_precheck %s: %s - %s%s | dump=%d(同=%d 叠=%d 断=%d) "
            "C侧已观测间隔=%d 不可判=%d | A侧可用轮=%s/%s | B动率=%s "
            "建议 --framestats-period-s=%s"
            % (os.path.basename(res["run_dir"]), v, why, warn, res["dumps"],
               ps["identical"], ps["overlap"], ps["disjoint"],
               res["observed_gaps"], res["unjudgeable_gaps"],
               a.get("turns_with_anchor", "?"), a.get("turns", "?"),
               _f(res["channel_b"].get("motion_rate"), 3),
               res["recommended_framestats_period_s"]))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="E2 适用性前置断言：开跑前判「这一格值不值得开 e2」")
    ap.add_argument("--run-dir", required=True, action="append",
                    help="已有的观察通道 run 目录；可重复给多个")
    ap.add_argument("--pkg", default=None,
                    help="目标包；默认从该格 RUN_KIND.json 的 pkg 取")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args(argv)

    if args.json_out:
        # 落点检查在**算之前**（D-306：e1 至今是算完才崩，操作者拿到半套交付物）。
        d = os.path.dirname(os.path.abspath(args.json_out))
        if not os.path.isdir(d):
            ec.say("--json-out 的目录不存在: %s\n" % d, sys.stderr)
            return 2

    results, bad = [], False
    for run_dir in args.run_dir:
        if not os.path.isdir(run_dir):
            ec.say("run-dir 不存在: %s\n" % run_dir, sys.stderr)
            return 2
        r = precheck(run_dir, args.pkg)
        results.append(r)
        ec.say(render_line(r) + "\n")
        if r["verdict"][0] != WORTH_RUNNING:
            bad = True

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)
    # 退出码：0 = 每一格都值得开 e2；1 = 至少一格 FAIL 或 NOT_EXECUTED。
    # **两者都返回 1** 是刻意的：对「要不要开窗」这个决定，「不适用」与「判不了」
    # 都意味着**别照原样开**；区别写在那一行文字里，由人读。
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
