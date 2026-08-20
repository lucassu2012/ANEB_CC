#!/usr/bin/env python3
"""ANEB pre-publish self-check for a campaign report corpus (stdlib only).

The runbook's pre-publish checklist is eight manual items — and a manual
checklist at the end of a field day is exactly what gets skipped. This runs the
mechanically decidable ones in a single command (D-124).

Four severities, deliberately separated:

  FAIL — objectively wrong, blocks publication. The machine can be sure:
         synthetic (fabricated) records mixed in, contract violations, a corpus
         with no campaign labels at all, an empty corpus.
  WARN — needs a human to explain before publishing, not something a tool can
         settle: cells below the validity floor, distortion hot-spots, suspect
         clocks, low-confidence cells, order-effect evidence.
  N/A  — the check had nothing to run on, so it reached no verdict. NOT a quiet
         PASS: the reader's first action on this table is to scan the icons, and
         a green tick against a check that never ran is the same lie D-163 and
         D-198 removed from three items and left standing in the rest (D-229).
  PASS — the check ran over a non-empty set and found nothing wrong.

What separates the last two is the object, not the evidence: no object at all is
N/A, while objects whose evidence is missing stay WARN — a corpus that has cells
but no `server_tier_endpoint` cannot be reconciled, and someone has to say why.

A WARN is never auto-upgraded to PASS and never silently swallowed: the point is
that the report author must be able to answer "why is this cell like that?"
before the report becomes ammunition. Exit 0 = no FAIL (WARNs may remain),
1 = at least one FAIL.

Usage:
    python publish_check.py labeled/*.jsonl
"""
import argparse
import sys

import attribution
import buffering_rollup
import campaign_common as cc
import campaign_report as rpt
import order_effect
import radio_rollup
import round_effect
import transport_rollup
# 墙钟判据复用单一实现，本文件不造第四份阈值副本（D-264）。
import trust_rollup
import trust_rollup
import validity_rollup

FAIL, WARN, NA, PASS = "FAIL", "WARN", "N/A", "PASS"


def _row(sev, item, detail):
    return {"severity": sev, "item": item, "detail": detail}


def st_int(stats, key):
    """A loader counter, or a KeyError — never a plausible-looking default.

    `stats.get(key, 0)` disguises a mistyped key as a value of zero. It did
    exactly that here: the integrity row printed 「读 2 行」 for a three-line
    corpus because `read` is the per-run loaders' name and campaign_common
    calls it `lines` (D-325).
    """
    return int(stats[key])


def _cell_key(cell):
    """Hashable identity of an attribution cell, for de-duplicating across the
    per-KPI sweeps (D-191). Sorted so two dicts with the same content agree."""
    return tuple(sorted((cell.get("cell") or {}).items()))


def check(records, min_samples=cc.DEFAULT_MIN_SAMPLES, stats=None):
    """Return a list of {severity, item, detail} rows, most severe first.

    `stats` is load_records' integrity counters. Without them the corpus
    integrity item reaches N/A, not PASS — this gate exists because the manual
    checklist gets skipped, and a green tick against a check that never ran is
    the lie the severities were separated to prevent (D-229).
    """
    if not records:
        return [_row(FAIL, "语料", "无记录——没有可发布的内容")]

    rows = []

    # --- FAIL class: objectively wrong -------------------------------------
    n_synth = cc.count_synthetic(records)
    rows.append(_row(FAIL, "合成语料", f"{n_synth}/{len(records)} 条为合成数据"
                                       "（彩排语料混入，绝不可外发）")
                if n_synth else
                _row(PASS, "合成语料", "无合成记录"))

    errors = rpt.contract_gate(records)
    if errors is None:
        rows.append(_row(WARN, "输入契约", "schema 不可读——本次未校验"
                                           "（NOT_EXECUTED，不等于通过）"))
    elif errors:
        rows.append(_row(FAIL, "输入契约", f"{len(errors)} 条违规，例：{errors[0]}"))
    else:
        rows.append(_row(PASS, "输入契约", f"{len(records)} 条记录全部合规"))

    # load_records calls a repeated run_id with a DIFFERENT body "a real
    # data-integrity fault ... must never be averaged together", and the report
    # prints it on its integrity line. The gate could not see it: check() was
    # handed records only, so the one signal that says two runs disagree about
    # what happened lived on the page and nowhere in the checklist that exists
    # because the page gets skipped (D-325, the shape of D-305).
    if stats is None:
        # 未核算 is not a wording choice: an existing guard asserts the
        # biconditional 「未核算 in detail」 <=> 「severity is N/A」, so that
        # neither half can drift into an N/A that reads like a clean result
        # (D-229). It caught this row the first time it ran.
        rows.append(_row(NA, "语料完整性", "未提供加载统计——本次未核算"
                                           "（NOT_EXECUTED，不等于通过）"))
    else:
        integrity = []
        if stats.get("conflicts"):
            ids = ", ".join(str(c) for c in list(stats["conflicts"])[:3])
            integrity.append(f"同一 run_id 两个不同 body × {len(stats['conflicts'])}"
                             f"（{ids}）——保留了先到的那条，须说明为何有两份")
        if st_int(stats, "malformed"):
            integrity.append(f"坏行 × {stats['malformed']}——已跳过，未计入任何中位数")
        # corpus_health calls this ERROR ("makes aggregates WRONG") and the item
        # written one decision ago checked conflicts and malformed but not this
        # — a rule naming three things whose guard compared two (D-246, D-328).
        # load_records catches OSError and continues, so an unreadable file
        # takes a whole file's records out of every denominator, silently.
        if st_int(stats, "unreadable_files"):
            integrity.append(f"读不了的文件 × {stats['unreadable_files']}"
                             "——整个文件的记录都不在语料里，每个分母都少了一截，"
                             "须查清是哪份、为何读不了")
        # The seventh counter, and the one this item still had not named. A
        # record with no run_id cannot be de-duplicated — R-10 forbids merging
        # under a fabricated key — so repeats among them stay invisible and
        # inflate whatever denominator they land in. Not a bug to fix: a fact
        # the operator has to know (D-329).
        if st_int(stats, "no_run_id"):
            integrity.append(f"无 run_id 的记录 × {stats['no_run_id']}"
                             "——无法去重（R-10 不允许归并到臆造的键下），"
                             "它们之间若有重复也看不见，对应分母可能虚高")
        if integrity:
            rows.append(_row(WARN, "语料完整性", "；".join(integrity)))
        else:
            # load_records' own key names — `lines`/`kept`/`duplicates`, not the
            # `read`/`dropped` the per-run loaders use. Reading one loader's dict
            # with the other's vocabulary printed a plausible-looking 「读 2 行」
            # that was really len(records) coming back from a .get() default:
            # the divergence D-315 pinned at the function level, one layer down
            # in the field names (D-325).
            dup = st_int(stats, "duplicates")
            tail = f"，去重丢 {dup} 条（body 相同的良性重导）" if dup else ""
            rows.append(_row(PASS, "语料完整性",
                             f"读 {st_int(stats, 'lines')} 行、"
                             f"保留 {st_int(stats, 'kept')} 条{tail}，无冲突无坏行"))

    inv = rpt.inventory(records)
    # A non-empty run.campaign block is not a usable label set. The staged C1
    # rollout writes campaign_id/carrier/time_band before point_id, and that
    # corpus used to PASS while the heat card collapsed to one `unlabeled` row
    # (D-162). Judge per grouping dimension, not by block presence.
    total = inv["records"]
    gaps = []
    for key, dim, bucket in (("campaigns", "campaign_id", cc.UNLABELED),
                             ("points", "point_id", cc.UNLABELED),
                             ("carriers", "carrier", "unknown"),
                             ("time_bands", "time_band", "unknown"),
                             ("tiers", "tier", "unknown")):
        n = inv[key].get(bucket, 0)
        if n:
            gaps.append((dim, n, n == total))
    collapsed = [d for d, _, whole in gaps if whole and d in ("point_id", "carrier",
                                                              "time_band", "campaign_id")]
    if inv["with_campaign"] == 0:
        rows.append(_row(FAIL, "战役标签", "全部记录无 run.campaign——热力卡/归因塌缩为"
                                           "单格，报告无分组意义"))
    elif collapsed:
        rows.append(_row(FAIL, "战役标签",
                         "以下分组维度**全部未标注**：" + "、".join(collapsed) +
                         "——该维度上热力卡塌缩为单格，报告在这个方向上没有分组意义"))
    elif gaps:
        detail = "；".join(f"{d} 有 {n}/{total} 条未标注" for d, n, _ in gaps)
        rows.append(_row(WARN, "战役标签", detail + "（落入 unlabeled/unknown 桶，"
                                                   "对应格的口径与其余格不同）"))
    else:
        rows.append(_row(PASS, "战役标签", "全部分组维度均已标注"))

    # --- WARN class: needs a human explanation ------------------------------
    non_completed = {k: v for k, v in inv["statuses"].items() if k != "completed"}
    rows.append(_row(WARN, "run 状态", f"存在非 completed run：{non_completed}"
                                       "（已完成场景仍计入，须在正文说明）")
                if non_completed else
                _row(PASS, "run 状态", "全部 completed"))

    mixed_ver = []
    for key, label in (("kpi_sets", "kpi_set"), ("aqs_versions", "aqs_version"),
                       ("profile_version_sets", "profile_versions"),
                       ("app_versions", "app_version_code")):
        if len(inv[key]) > 1:
            mixed_ver.append(f"{label}={dict(inv[key])}")
    rows.append(_row(WARN, "版本一致性", "；".join(mixed_ver) +
                     "（跨版本聚合可能把不同定义的数字当同一指标平均，须人工确认）")
                if mixed_ver else
                _row(PASS, "版本一致性", "kpi_set / aqs_version / app_version 均一致"))

    vres = validity_rollup.analyze(records)
    low = [c for c in vres["cells"] if c["below_min_rate"]]
    if not vres["cells"]:
        rows.append(_row(WARN, "有效率", "无场景数据——无法判断样本分母"))
    elif low:
        worst = min(low, key=lambda c: c["valid_rate"])
        rows.append(_row(WARN, "有效率", f"{len(low)} 个格低于 "
                                         f"{vres['min_rate'] * 100:.0f}% 门，最低 "
                                         f"{worst['valid_rate'] * 100:.0f}%"
                                         "（须解释失效原因，否则中位数偏乐观）"))
    else:
        rows.append(_row(PASS, "有效率", f"全部格达门（≥{vres['min_rate'] * 100:.0f}%）"))

    bres = buffering_rollup.analyze(records, min_samples)
    hot = [c for c in bres["cells"] if c["distortion_hotspot"]]
    if bres["no_evidence"]:
        # zero measured scenarios used to render as PASS 无失真热点 (D-163) —
        # the same "cannot judge must not read as no problem" rule the
        # 测量可信度 item below already applies
        rows.append(_row(WARN, "批化失真", "无任何场景测到批化（块存在但字段全空）"
                                           "——**无法判断**是否存在失真，非「未见失真」"))
    elif hot:
        rows.append(_row(WARN, "批化失真", f"{len(hot)} 个失真热点格"
                                           "（须先做失真核算，再谈网络结论）"))
    else:
        rows.append(_row(PASS, "批化失真", "无失真热点"))

    tres = trust_rollup.analyze(records, min_samples)
    clock_hot = [c for c in tres["cells"] if c["clock_hotspot"]]
    if tres["no_evidence"]:
        rows.append(_row(WARN, "测量可信度", "无 clock/seq/parse 标注——无法判断仪器可信度"))
    elif clock_hot:
        rows.append(_row(WARN, "测量可信度", f"{len(clock_hot)} 个时钟可疑热点格"
                                             "（该格时延中位数存疑）"))
    else:
        rows.append(_row(PASS, "测量可信度", "无时钟可疑热点"))

    cells = rpt.heat_cells(records, min_samples)
    lowconf = [c for c in cells if c["low_confidence"]]
    if not cells:
        # "全部 0 个格样本充足" — a PASS asserting sufficiency over nothing. The
        # empty set satisfies every predicate, which is precisely why an empty
        # one must not be reported as satisfying this one (§2.2, D-198). Reachable
        # whenever no run carries a usable AQS: every score null, or every score
        # refused as impossible.
        rows.append(_row(WARN, "样本充分性",
                         "无任何可用 AQS 的格——**样本量无从核算**"
                         "（记录都在，但没有一条带得出分数的 run；先查打分侧）"))
    elif lowconf:
        rows.append(_row(WARN, "样本充分性", f"{len(lowconf)}/{len(cells)} 个格 "
                                             f"n<{min_samples}（标 low_conf，结论不应依赖）"))
    else:
        rows.append(_row(PASS, "样本充分性", f"全部 {len(cells)} 个格样本充足"))

    # Every check below sweeps the attribution cells once PER KPI, so a cell that
    # is compromised shows up once for each attributable KPI. Counting those
    # appearances says "12 个格" about six cells — a number the reader cannot
    # find anywhere, and double the apparent severity. Mixed media, tier timing
    # and endpoint conflicts are properties of the CELL, not of the KPI, so the
    # union of cell keys is what to count (D-191).
    mixed_tp, tp_cells, paired_tp = set(), set(), 0
    for k in attribution.ATTRIBUTABLE_KPIS:
        res = attribution.attribute(records, kpi=k, min_samples=min_samples)
        paired_tp += attribution.between_tier_population(res)[0]
        for c in res["cells"]:
            tp_cells.add(_cell_key(c))
            if c.get("mixed_transports"):
                mixed_tp.add(_cell_key(c))
    # Single-tier wording, same as the report body has carried since D-157 — and the
    # SAME predicate (between_tier_population), not a second one that could drift.
    # Measured on the first REAL pilot corpus: the body said 「本轮含义不同」 while this
    # gate — the table an operator reads immediately before publishing — announced
    # 「3 个格三层级接入介质一致」 about a corpus carrying exactly one tier. Nothing about
    # tiers had been verified; and the WARN branch would have been worse, naming a
    # 骨干增量 that cannot exist in a one-server pilot (D-350; the D-330/D-339 shape:
    # one surface fixed, the other left).
    single_tier = bool(tp_cells) and paired_tp == 0
    if mixed_tp:
        rows.append(_row(WARN, "同一接入",
                         (f"{len(mixed_tp)} 个格内混用了不同接入介质"
                          "——本轮单层级，无层级间增量，该格**绝对值不可混池**"
                          if single_tier else
                          f"{len(mixed_tp)} 个格的三层级混用了不同接入介质"
                          "——该格的骨干增量其实含 wifi/蜂窝差，不可用")))
    elif tp_cells:
        rows.append(_row(PASS, "同一接入",
                         (f"{len(tp_cells)} 个格内接入介质一致（本轮单层级，"
                          "**层级间**一致性无对象可核）"
                          if single_tier else
                          f"{len(tp_cells)} 个格三层级接入介质一致")))
    else:
        rows.append(_row(NA, "同一接入", "无可归因单元——接入介质一致性**未核算**"))

    # 层级对账: the tier label is typed by the operator; server_tier_endpoint is
    # what the run actually hit. Written by annotate, read by nobody — so a
    # corpus whose three "tiers" all hit the metro mirror produced a full
    # backbone decomposition with an empty note and a green gate (D-167).
    conflicts, known, seen = set(), set(), set()
    for k in attribution.ATTRIBUTABLE_KPIS:
        for c in attribution.attribute(records, kpi=k, min_samples=min_samples)["cells"]:
            key = _cell_key(c)
            seen.add(key)
            if c.get("tier_endpoints_known"):
                known.add(key)
            if c.get("tier_endpoint_conflicts"):
                conflicts.add(key)
    known_cells, total_cells = len(known), len(seen)
    if conflicts:
        rows.append(_row(FAIL, "层级对账",
                         f"{len(conflicts)} 个格的同一端点被标成多种层级"
                         "——三层其实打的同一个端,**骨干分解不成立**"))
    elif not total_cells:
        rows.append(_row(NA, "层级对账", "无可归因单元——层级对账**未核算**"))
    elif not known_cells:
        rows.append(_row(WARN, "层级对账",
                         "语料无 `server_tier_endpoint`——**无法对账** tier 标签是否"
                         "对应实际打到的镜像端(不等于对上了)"))
    else:
        rows.append(_row(PASS, "层级对账",
                         f"{known_cells}/{total_cells} 个格可对账,未见端点与层级冲突"))

    # The other half of 铁律 3's premise. Unlike simultaneity this one is not
    # merely unchecked, it is uncheckable: the contract carries no device
    # identity at all. Saying nothing would let a reader assume it held (D-156).
    rows.append(_row(WARN, "同一客户端",
                     "结果契约无设备标识字段——**工具无法核对**三层级是否同一台设备所测；"
                     "中途换机的差异会整个计入骨干增量且无任何标记，须由采集方书面确认"))

    # 铁律 3 cancels the common mode only if the tiers were measured together;
    # time_band is hours wide, so this is checkable and was never checked (D-155)
    conf, unknown_keys, judged_keys, worst_ms = {}, set(), set(), 0
    for k in attribution.ATTRIBUTABLE_KPIS:
        for c in attribution.attribute(records, kpi=k, min_samples=min_samples)["cells"]:
            key = _cell_key(c)
            if c.get("tier_time_confound") is None:
                if len(c.get("coverage") or []) > 1:
                    unknown_keys.add(key)
                continue
            judged_keys.add(key)
            if c["tier_time_confound"]:
                conf[key] = max(conf.get(key, 0), c["tier_time_spread_ms"] or 0)
    unknown, judged = len(unknown_keys - judged_keys), len(judged_keys)
    if conf:
        worst = max(conf.values()) / 3600_000.0
        rows.append(_row(WARN, "层级同时性",
                         f"{len(conf)}/{judged} 个格的三层级测量相隔过久（最大 {worst:.1f}h）"
                         "——共模不再抵消，该格的骨干增量可能是时段差异"))
    elif not judged and unknown:
        rows.append(_row(WARN, "层级同时性", f"{unknown} 个多层级格无时间戳——无法核对同时性"))
    elif judged:
        rows.append(_row(PASS, "层级同时性", f"{judged} 个格的三层级测量在门限内"))
    else:
        rows.append(_row(NA, "层级同时性", "无多层级格——层级同时性**未核算**"))

    # The radio covariate. PLAN_ALIGNMENT §7.3 named it the first substitute for
    # the cancelled three-tier decomposition, radio_rollup reads it, the report
    # prints it — and the gate had never heard of it: `radio` matched nothing in
    # this file (D-305). Two rows, both always emitted (D-150): is the context
    # there at all, and does the busy/idle comparison survive what it says.
    radio = radio_rollup.analyze(records, min_samples)
    rcells = radio["cells"]
    if not radio["any_block"]:
        # Same shape as 同一客户端 above: not merely unchecked but uncheckable
        # until the producer writes it, so it can never reach PASS (D-156).
        rows.append(_row(WARN, "无线上下文",
                         "语料无无线上下文——**无从核对**结论里是否混着信号差异；"
                         "生产侧接线规格见 `docs/RADIO_CONTEXT_WIRING_SPEC.md`"))
    elif not radio["any_radio"]:
        rows.append(_row(WARN, "无线上下文",
                         "全部无线样本标 stale 已排除——**排除不等于没问题**，"
                         "须核对采集侧的取样新鲜度窗口"))
    else:
        thin = [c for c in rcells if c["stale_samples"] or c["thin_samples"]]
        if thin:
            rows.append(_row(WARN, "无线上下文",
                             f"{len(thin)}/{len(rcells)} 个格的无线证据 stale 或过薄"
                             "——该格的信号档不足以据此排除信号因素"))
        else:
            rows.append(_row(PASS, "无线上下文",
                             f"{len(rcells)} 个格均有可用无线证据"))

    # 三级归因取消后，忙闲是仅剩的两个对照轴之一；换了小区的点位那条轴就没了。
    places = radio["places"]
    moved = [p for p in places if p["changed"] or p["partial"]]
    if moved:
        rows.append(_row(WARN, "忙闲同小区",
                         f"{len(moved)}/{len(places)} 个点位忙闲挂的不是同一小区"
                         "——**该点位的忙闲差不可单独归因于时段**，不得表述为忙时劣化"))
    elif places:
        rows.append(_row(PASS, "忙闲同小区", f"{len(places)} 个点位忙闲同小区"))
    else:
        rows.append(_row(NA, "忙闲同小区",
                         "无点位在两个时段都留下小区标识——忙闲可比性**未核算**"))

    # `network_snapshot.server_observed_addr`（出口 IP，D-376/T9 已接读者：radio_rollup
    # 读出、campaign_report 渲染，唯独发布门此前从未检查过它——本条补上那一环）。
    # WARN 而非 FAIL：schema 里这个键必填但**值允许 null**（缺键已被更早一层的契约门
    # 拦下，到这里只可能是"键在、值全 null"），不是本文件 FAIL 定义的"机器能确定
    # 客观错误"，是需要人解释的覆盖缺口——同一严重度校准用在"无线上下文"上。
    # 无 N/A 分支：`rcells` 在这里恒非空（函数顶部已挡掉空语料，`campaign_labels()`
    # 对任何记录都会分到一个格，哪怕是 unlabeled/unknown 桶），一个永远走不到的分支
    # 比没有更误导——"无线上下文"检查同一形状也只有 WARN/PASS 两态。
    egress_gaps = [c for c in rcells if c["n"] and not c["egress_ips"]]
    if egress_gaps:
        rows.append(_row(WARN, "出口 IP",
                         f"{len(egress_gaps)}/{len(rcells)} 个格没有读出任何出口 IP"
                         "（`server_observed_addr` 全部为 null 或缺失）——制式与出口路径"
                         "共线判别（D-374/D-424）依赖这个字段，缺了就没法把两者分开"))
    else:
        rows.append(_row(PASS, "出口 IP", f"{len(rcells)} 个格均至少读出一个出口 IP"))

    # radio_rollup 早就算出「一格混几条出口路径」这件事（`MIXED_EGRESS:N`），但那个
    # 标记只印在 radio_rollup 自己的渲染表里，发布门这一面从未读过它——同族 D-303/
    # D-304/D-305：一个信号只活在一个面，另一个面看不见（T39/D-454 实测复现：本轮
    # 语料唯一那格恰好混了两个出口，`publish_check` 之前会给出干净 PASS，读者对混
    # 出口这件事一无所知）。WARN 而非 FAIL：混出口在扩展轮语义下是「该格需按 §10
    # 分段呈现、不可池化平均」的信号，不是机器能确定的客观错误——同一严重度校准用
    # 在上面的"出口 IP"（D-431）上。无 N/A 分支：`rcells` 恒非空的前提与上面那条
    # 检查完全相同，不重复论证。
    mixed_egress = [c for c in rcells if len(c["egress_ips"]) > 1]
    if mixed_egress:
        detail = "; ".join(
            "%s/%s/%s(%d 个)" % (c["cell"]["point_id"], c["cell"]["carrier"],
                                 c["cell"]["time_band"], len(c["egress_ips"]))
            for c in mixed_egress)
        rows.append(_row(WARN, "出口一致性",
                         f"{len(mixed_egress)}/{len(rcells)} 个格混用了不止一个出口 IP"
                         f"（{detail}）——按 §10 纪律须分段呈现，不可池化平均"))
    else:
        rows.append(_row(PASS, "出口一致性", f"{len(rcells)} 个格出口路径均单一"))

    # A veto caps the score at 70/54 — the grade-band edges — so a low grade can
    # mean the sessions failed rather than the network being slow (D-154)
    veto_cells = [c for c in cells if c.get("veto_n")]
    if veto_cells:
        n_runs = sum(c["veto_n"] for c in veto_cells)
        rows.append(_row(WARN, "否决封顶",
                         f"{len(veto_cells)}/{len(cells)} 个格含被否决封顶的 run（共 {n_runs} 条，"
                         "T4 严重卡顿率 >1% → 封顶 54）——封顶分只说明「至少这么差」，"
                         "不是该格体验的度量，须回到卡顿证据本身"))
    elif cells:
        rows.append(_row(PASS, "否决封顶", f"{len(cells)} 个格均无被否决封顶的 run"))
    else:
        rows.append(_row(NA, "否决封顶", "无可用 AQS 的格——否决封顶**未核算**"))

    # 报告已经在印"墙钟可疑 N 条"（D-506/T68）与"忙闲标签会不会翻转"（D-543），
    # 而这道门此前 86 项里**一条都不看它**——门比报告少读一项，正是 D-330 那个形状
    # （报告的前门只读两项、漏掉 unreadable_files，于是整份读不进来也照出报告）。
    # 墙钟错污染的是「哪天测的 / 忙还是闲 / 两战役谁在前」，恰恰是发布前最该拦的判读前提。
    wall_ann = wall_susp = 0
    for rec in records:
        sk = [cc.fnum((s.get("clock") or {}).get("wall_skew_ms"))
              for s in cc.iter_scenarios(rec)]
        sk = [x for x in sk if x is not None]
        if sk:
            wall_ann += 1
            if any(trust_rollup.wall_clock_suspect(x) for x in sk):
                wall_susp += 1
    if wall_susp:
        rows.append(_row(WARN, "墙钟可信度",
                         f"{wall_susp}/{wall_ann} 条 run 的设备墙钟与服务端差 > "
                         f"{trust_rollup.WALL_SKEW_MAX_MS // 1000}s——**KPI 值不受影响**"
                         "（计时走单调钟 R-24），但「哪天测的／忙还是闲／两战役谁在前」"
                         "都由这把钟决定；按日分桶与忙闲结论须核对服务端时刻"
                         "（`started_at_epoch_ms − clock.wall_skew_ms`）"))
    elif wall_ann:
        rows.append(_row(PASS, "墙钟可信度", f"{wall_ann} 条带墙钟证据的 run 均在阈值内"))
    else:
        rows.append(_row(NA, "墙钟可信度",
                         "语料无 `clock.wall_skew_ms`（EchoWire 接线前的生产者）"
                         "——墙钟**未核算**，不等于对得上"))

    # A heat-card dimension filled by a rule of thumb is not the same evidence
    # as one recorded on site, and the report says "busy is N points worse than
    # idle" either way (D-153)
    inferred_tb = sum(n for src, n in (inv.get("label_sources") or {}).items()
                      if "inferred:time_band" in src)
    if inferred_tb:
        rows.append(_row(WARN, "标签来源",
                         f"{inferred_tb}/{inv['records']} 条的 time_band 由工具按本地小时推断"
                         "（非现场记录）——忙闲结论须在正文注明推断口径"))
    else:
        rows.append(_row(PASS, "标签来源", "无推断得到的分组标签"))

    # An impossible value is not a bad measurement — an AQS of 9999 bands as
    # `excellent`, a negative metro RTT manufactures backbone latency out of
    # nothing in the differential (D-178). FAIL, not WARN: unlike every other
    # item here there is no reading of the data under which this is acceptable,
    # and the number it produces is not merely hard to interpret, it is invented.
    bad_vals = inv.get("implausible_values") or {}
    if bad_vals:
        rows.append(_row(FAIL, "取值范围",
                         f"{sum(bad_vals.values())} 个取值物理/定义上不可能（"
                         + "；".join(f"{r} × {n}" for r, n in sorted(bad_vals.items()))
                         + "）——已排除出中位数并标 IMPLAUSIBLE_VALUE；"
                         "写出过不可能值的生产者，其同批其他数值同样不可信，"
                         "请修生产端后重采，勿据此发布"))
    else:
        rows.append(_row(PASS, "取值范围", "AQS 与各 KPI 取值均在定义域内"))

    # A wrong-magnitude epoch still sorts, so before/after comes out confidently
    # backwards while the report states its basis as "time" (D-176). WARN, not
    # FAIL: this layer cannot tell a producer bug from a corpus stitched out of
    # something else — but it must never pass silently.
    bad_ms = inv.get("implausible_ms") or {}
    if bad_ms:
        rows.append(_row(WARN, "时间戳量级",
                         f"{sum(bad_ms.values())}/{inv['records']} 条 started_at_epoch_ms "
                         "不像毫秒时间戳（"
                         + "；".join(f"{r} × {n}" for r, n in sorted(bad_ms.items()))
                         + "）——前后配对、采集时间窗、层级同时性都取自该字段；"
                         "受影响战役已退出自动配对，请先修生产端再出报告"))
    else:
        rows.append(_row(PASS, "时间戳量级", "started_at_epoch_ms 取值均在合理毫秒范围"))

    # One label typed two ways splits a cell and the split is invisible in the
    # rendered table — the operator is the only one who can say which it is (D-149)
    coll = inv.get("label_collisions") or {}
    if coll:
        detail = "；".join(
            f"{field}: " + " / ".join(v for _, vs in sorted(groups.items()) for v in vs)
            for field, groups in sorted(coll.items()))
        rows.append(_row(WARN, "标签同名异写", detail +
                         "——被当作不同的格统计，**未自动合并**；确属同一对象请改语料重出报告"))
    else:
        rows.append(_row(PASS, "标签同名异写", "未见疑似同名异写的标签"))

    # The runbook's multi-campaign workflow is one report per campaign, with the
    # pooled one used only for the before/after section. Nothing until now
    # checked that the corpus being published was the single-campaign kind, so
    # publishing pooled headline numbers was a one-command mistake (D-147).
    labeled = [c for c in inv["campaigns"] if c != cc.UNLABELED]
    if len(labeled) > 1:
        rows.append(_row(WARN, "战役池化",
                         f"本语料含 {len(labeled)} 个战役（{', '.join(labeled)}）——"
                         "除「优化前后对比」/「纵向趋势」外各段均按格池化，其中位数"
                         "**既不是前也不是后**；头条数字须取自 `--campaign <id>` 的单战役报告"))
    elif labeled:
        rows.append(_row(PASS, "战役池化", f"单战役（{labeled[0]}）"))
    else:
        rows.append(_row(NA, "战役池化", "无战役标签——跨战役池化**未核算**"))

    # "It got better" is the claim a second round exists to make. Publishing it
    # when every cell's Δ sits inside the measurement noise is the failure mode
    # this check is here to catch (D-144).
    b_id, a_id = rpt.auto_compare_ids(inv)
    if b_id and a_id:
        cmp_rows = [r for r in rpt.compare_campaigns(records, b_id, a_id, min_samples)["rows"]
                    if r["delta"] is not None]
        real = [r for r in cmp_rows if r["within_noise"] is False]
        noisy = [r for r in cmp_rows if r["within_noise"] is True]
        unknown = [r for r in cmp_rows if r["within_noise"] is None]
        # each bucket stays visible in every branch — "noise not estimable" must
        # never be folded into "within noise", nor either into "no effect" (R-10)
        parts = []
        if real:
            parts.append(f"{len(real)} 个格 Δ 超出噪声")
        if noisy:
            parts.append(f"{len(noisy)} 个格 Δ 在噪声内")
        if unknown:
            parts.append(f"{len(unknown)} 个格噪声不可估（样本不足）")
        detail = f"{b_id} → {a_id}：" + "；".join(parts)
        if not cmp_rows:
            rows.append(_row(WARN, "效应量", f"{b_id} → {a_id} 无共同单元——无法判断是否改善"))
        elif not real:
            rows.append(_row(WARN, "效应量", detail + "——**不得表述为改善或回退**"))
        elif unknown:
            rows.append(_row(WARN, "效应量", detail + "——不可估的格不得计入结论"))
        else:
            rows.append(_row(PASS, "效应量", detail))
    else:
        # every other item emits a row in every case; a silently absent one
        # cannot be told apart from a check that was forgotten (D-150). The row
        # is N/A rather than PASS because a single-campaign corpus has no
        # before/after pair to compare — the summary already says the improvement
        # question is unanswerable this round, and the gate has to agree (D-229).
        rows.append(_row(NA, "效应量", "单战役语料，无前后可比对象——效应量**未核算**"))

    # Same claim shape as 效应量, different section: "cellular is worse than wifi
    # here" is a difference of two medians and was published from the sign alone
    # (D-180). Judged on the same three buckets so the two cannot disagree.
    tres = transport_rollup.analyze(records, min_samples)
    tneg = [c for c in tres["cells"]
            if c["cellular_minus_wifi"] is not None and c["cellular_minus_wifi"] < 0]
    treal = [c for c in tneg if c["within_noise"] is False]
    # The third bucket this item claimed to have and did not: a cell whose noise
    # cannot be estimated was never checked and found real. 效应量 above has had
    # its `elif unknown` branch since D-144, so on a mixed set this item answered
    # PASS where its twin answers WARN — while the comment overhead said the two
    # were judged on the same three buckets, which is what hid the omission
    # (D-198). The same two-state slip D-144 was written to prevent, in the item
    # added to prevent it.
    tunknown = [c for c in tneg if c["within_noise"] is None]
    # A cell is comparable only where both media were measured; elsewhere
    # `cellular_minus_wifi` is None and there is nothing to compare. That state
    # used to share a row with "cellular is not worse", so one green tick meant
    # either "checked, clean" or "never checked" and the reader could not tell
    # which (D-229).
    tcomparable = [c for c in tres["cells"] if c["cellular_minus_wifi"] is not None]
    if tres["only_unknown"]:
        rows.append(_row(NA, "介质效应量", "无 transport 证据——介质效应量**未核算**"))
    elif not tcomparable:
        rows.append(_row(NA, "介质效应量", "无同格双介质可比——介质效应量**未核算**"))
    elif not tneg:
        rows.append(_row(PASS, "介质效应量",
                         f"{len(tcomparable)} 个格同格双介质可比，蜂窝均不劣于 wifi"))
    elif not treal:
        rows.append(_row(WARN, "介质效应量",
                         f"{len(tneg)} 个格 Δ(cellular−wifi) 为负但无一超出噪声尺度"
                         + (f"（其中 {len(tunknown)} 个格噪声不可估）" if tunknown else "")
                         + "——**不得表述为蜂窝劣于 wifi**"))
    elif tunknown:
        rows.append(_row(WARN, "介质效应量",
                         f"{len(treal)}/{len(tneg)} 个负 Δ 超出噪声尺度，另有 "
                         f"{len(tunknown)} 个格**噪声不可估**——不可估的格不得计入结论"))
    else:
        rows.append(_row(PASS, "介质效应量",
                         f"{len(treal)}/{len(tneg)} 个负 Δ 超出噪声尺度"))

    # Partitioned in order_effect.summarize() so this gate and the report
    # summary cannot answer the same question differently (D-338). Confounded
    # profiles are held out of `judged` there, for the reason D-335 gives.
    osum = order_effect.summarize(records, min_samples)
    biased, judged = osum["biased"], osum["judged"]
    confounded, balance_ok = osum["confounded"], osum["balance_ok"]
    no_evidence, never_rotated = osum["no_evidence"], osum["never_rotated"]
    # Three different corpora used to collapse into one message. A corpus that
    # HAS scenario_order and proves the Latin square never rotated is a stronger
    # and quite different finding from one that carries no order evidence at
    # all, and order_effect已 computes both verdicts (D-164) — this gate simply
    # never read them (D-170).
    if no_evidence:
        rows.append(_row(WARN, "序位效应", "语料无 `scenario_order`——"
                                           "**无法校验**反平衡是否奏效"))
    elif never_rotated:
        rows.append(_row(WARN, "序位效应", "全语料只有一种轮次——**拉丁方未轮转**，"
                                           "反平衡在构造上不成立，位次差无法与场景差分离"))
    elif not judged:
        # "nothing was judgeable" has more causes than this gate can enumerate,
        # and naming the wrong one is worse than naming none (§2.12). It used to
        # pick between two with an if/else and got a third one wrong the day it
        # appeared — 「位次不足 2」 about profiles carrying three positions with no
        # replication inside them. Same reason table as the report summary, from
        # the same analysis, so the two front doors cannot explain one refusal
        # two ways (§2.14, D-354).
        why = "、".join(rpt._ORDER_UNJUDGED_WHY.get(code, code)
                        for code in sorted(osum.get("unjudged_reasons") or ()))
        if confounded and not why:
            why = "所有 profile 的执行位次与单元不平衡"
        rows.append(_row(WARN, "序位效应", f"已轮转，但{why or '无可判定对象'}——"
                                           "**本轮无法校验**是否残留序位偏倚"))
    elif biased:
        rows.append(_row(WARN, "序位效应", f"{len(biased)}/{judged} 处疑似位置-KPI 相关"
                                           "（反平衡可能失效，须复核）"))
    else:
        rows.append(_row(PASS, "序位效应", f"{judged} 处均未见序位偏倚"))

    # Warm-up sits here, not only in the summary, because this gate is the one
    # surface with teeth: its contract is that every WARN must be answered in the
    # report body before publishing. A single-round corpus is the ordinary case
    # and its absolute numbers are cold-start numbers — 「TTFT 是 X ms」 without
    # that qualifier is exactly the sentence this row exists to stop (D-355/D-357).
    wsum = round_effect.summarize(records)
    if wsum.get("no_round_labels"):
        # Not quick mode's single round: quick writes repeat_index=0 too, so a
        # corpus with NO labels is a producer regression or a foreign corpus
        # wearing a plausible explanation (D-364).
        rows.append(_row(WARN, "预热效应",
                         f"场景**缺失轮次编号**（`repeat_index` 未写，{wsum['unknown_round_n']} 个"
                         "场景有数无编号）——预热效应**无法核算**，且这**不是** quick 模式的"
                         "正常形状（quick 也写 `repeat_index=0`）：先查生产端/语料来源"))
    elif wsum["single_round"]:
        rows.append(_row(WARN, "预热效应",
                         "语料**只有一轮**——**无法校验**首轮是否更差，而单轮模式测到的"
                         "永远是第一轮：正文中每个**绝对值**都须标明是**冷启动口径**"
                         "（跨格比较不受影响）"))
    elif not wsum["judged"]:
        why = "、".join(rpt._ORDER_UNJUDGED_WHY.get(c, c)
                        for c in sorted(wsum["unjudged_reasons"] or ()))
        rows.append(_row(NA, "预热效应",
                         f"有多轮语料，但{why or '无可判定对象'}——预热效应**本轮未核算**"))
    elif wsum["suspected"]:
        named = "、".join(f"{e['kpi']}({cc.fmt_num(e['first_round_penalty_pct'], 1)}%)"
                          for e in wsum["suspected"])
        rows.append(_row(WARN, "预热效应",
                         f"{len(wsum['suspected'])}/{wsum['judged']} 个 KPI 首轮系统性更差"
                         f"（{named}）——这些 KPI 的**绝对值以后续轮为准**，正文须写明"))
    else:
        rows.append(_row(PASS, "预热效应", f"{wsum['judged']} 个 KPI 均未见首轮劣化"))

    # Said separately rather than folded into the verdict above: these profiles
    # were EXCLUDED from that count, and a reader who is told "3/8 suspected"
    # has no way to learn that four more were unjudgeable unless it is its own
    # line (D-335, same reason as D-330's front door).
    if confounded:
        rows.append(_row(WARN, "序位效应·单元混杂",
                         f"{len(confounded)} 处执行位次与单元不平衡——位次差"
                         "**不可单独归因于序位**，已排除在上一条判定之外"))
    elif balance_ok:
        rows.append(_row(PASS, "序位效应·单元混杂",
                         f"{balance_ok} 处各位次由同一组单元供样，汇池前提成立"))
    else:
        rows.append(_row(NA, "序位效应·单元混杂",
                         "无位次≥2 的 profile——汇池前提**本轮未核算**"))

    # N/A above PASS: "no answer" is closer to the reader's problem than "fine"
    rank = {FAIL: 0, WARN: 1, NA: 2, PASS: 3}
    return sorted(rows, key=lambda r: rank[r["severity"]])


def render_markdown(rows):
    lines = ["## 发布前自检", "",
             "> FAIL=客观错误，**阻断发布**；WARN=**须由人解释**后才可发布"
             "（工具不替人判断）；N/A=**该项无可核算对象，未作判断**——不等于无问题；"
             "PASS=该项已核查且未见问题。本自检**不能**替代 runbook §5 中"
             "需要人工判断的条目（结论措辞、归档完整性、claim_scope 落款）。", "",
             "| 判定 | 检查项 | 说明 |", "|---|---|---|"]
    icon = {FAIL: "⛔ FAIL", WARN: "⚠ WARN", NA: "➖ N/A", PASS: "✅ PASS"}
    for r in rows:
        # detail carries record-derived text — campaign ids, cell labels,
        # conflicting run_ids — so a '|' in a label split this row and the
        # whole self-check table rendered as garbage (D-128's bug, one surface
        # later). item is escaped too: same cell, same rule (D-334).
        lines.append(f"| {icon[r['severity']]} | {cc.md_cell(r['item'])} | "
                     f"{cc.md_cell(r['detail'])} |")
    fails = sum(1 for r in rows if r["severity"] == FAIL)
    warns = sum(1 for r in rows if r["severity"] == WARN)
    nas = sum(1 for r in rows if r["severity"] == NA)
    lines += ["", f"**结论：{'不可发布' if fails else '可发布'}**"
                  f"（FAIL {fails} / WARN {warns} / N/A {nas}）。"
                  + ("" if fails else "每条 WARN 都须在报告正文有对应说明；"
                                      f"另有 {nas} 项**本轮未核算**，"
                                      "报告不得就这些方向作出结论。")]
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB pre-publish self-check")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--min-samples", type=int, default=cc.DEFAULT_MIN_SAMPLES)
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    stats = {}
    recs, files = cc.load_records(args.inputs, stats=stats)
    rows = check(recs, args.min_samples, stats=stats)
    print(render_markdown(rows))
    print(f"\n<!-- records={len(recs)} files={len(files)} -->", file=sys.stderr)
    return 1 if any(r["severity"] == FAIL for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
