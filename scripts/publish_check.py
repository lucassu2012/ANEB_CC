#!/usr/bin/env python3
"""ANEB pre-publish self-check for a campaign report corpus (stdlib only).

The runbook's pre-publish checklist is eight manual items — and a manual
checklist at the end of a field day is exactly what gets skipped. This runs the
mechanically decidable ones in a single command (D-124).

Two severities, deliberately separated:

  FAIL — objectively wrong, blocks publication. The machine can be sure:
         synthetic (fabricated) records mixed in, contract violations, a corpus
         with no campaign labels at all, an empty corpus.
  WARN — needs a human to explain before publishing, not something a tool can
         settle: cells below the validity floor, distortion hot-spots, suspect
         clocks, low-confidence cells, order-effect evidence.

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
import trust_rollup
import validity_rollup

FAIL, WARN, PASS = "FAIL", "WARN", "PASS"


def _row(sev, item, detail):
    return {"severity": sev, "item": item, "detail": detail}


def check(records, min_samples=cc.DEFAULT_MIN_SAMPLES):
    """Return a list of {severity, item, detail} rows, most severe first."""
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

    inv = rpt.inventory(records)
    # A non-empty run.campaign block is not a usable label set. The staged C1
    # rollout writes campaign_id/carrier/time_band before point_id, and that
    # corpus used to PASS while the heat card collapsed to one `unlabeled` row
    # (D-162). Judge per grouping dimension, not by block presence.
    total = inv["records"]
    gaps = []
    for key, dim, bucket in (("campaigns", "campaign_id", "unlabeled"),
                             ("points", "point_id", "unlabeled"),
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
    rows.append(_row(WARN, "样本充分性", f"{len(lowconf)}/{len(cells)} 个格 "
                                         f"n<{min_samples}（标 low_conf，结论不应依赖）")
                if lowconf else
                _row(PASS, "样本充分性", f"全部 {len(cells)} 个格样本充足"))

    mixed_tp = []
    for k in attribution.ATTRIBUTABLE_KPIS:
        for c in attribution.attribute(records, kpi=k, min_samples=min_samples)["cells"]:
            if c.get("mixed_transports"):
                mixed_tp.append(c)
    if mixed_tp:
        rows.append(_row(WARN, "同一接入",
                         f"{len(mixed_tp)} 个格的三层级混用了不同接入介质"
                         "——该格的骨干增量其实含 wifi/蜂窝差，不可用"))
    else:
        rows.append(_row(PASS, "同一接入", "各格三层级接入介质一致"))

    # 层级对账: the tier label is typed by the operator; server_tier_endpoint is
    # what the run actually hit. Written by annotate, read by nobody — so a
    # corpus whose three "tiers" all hit the metro mirror produced a full
    # backbone decomposition with an empty note and a green gate (D-167).
    conflicts, known_cells, total_cells = [], 0, 0
    for k in attribution.ATTRIBUTABLE_KPIS:
        for c in attribution.attribute(records, kpi=k, min_samples=min_samples)["cells"]:
            total_cells += 1
            known_cells += int(bool(c.get("tier_endpoints_known")))
            if c.get("tier_endpoint_conflicts"):
                conflicts.append(c)
    if conflicts:
        rows.append(_row(FAIL, "层级对账",
                         f"{len(conflicts)} 个格的同一端点被标成多种层级"
                         "——三层其实打的同一个端,**骨干分解不成立**"))
    elif not total_cells:
        rows.append(_row(PASS, "层级对账", "无可归因单元,无需对账"))
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
    conf, unknown, judged = [], 0, 0
    for k in attribution.ATTRIBUTABLE_KPIS:
        for c in attribution.attribute(records, kpi=k, min_samples=min_samples)["cells"]:
            if c.get("tier_time_confound") is None:
                if len(c.get("coverage") or []) > 1:
                    unknown += 1
                continue
            judged += 1
            if c["tier_time_confound"]:
                conf.append(c)
    if conf:
        worst = max(c["tier_time_spread_ms"] for c in conf) / 3600_000.0
        rows.append(_row(WARN, "层级同时性",
                         f"{len(conf)}/{judged} 个格的三层级测量相隔过久（最大 {worst:.1f}h）"
                         "——共模不再抵消，该格的骨干增量可能是时段差异"))
    elif not judged and unknown:
        rows.append(_row(WARN, "层级同时性", f"{unknown} 个多层级格无时间戳——无法核对同时性"))
    else:
        rows.append(_row(PASS, "层级同时性",
                         f"{judged} 个格的三层级测量在门限内" if judged else "无多层级格可核对"))

    # A veto caps the score at 70/54 — the grade-band edges — so a low grade can
    # mean the sessions failed rather than the network being slow (D-154)
    veto_cells = [c for c in cells if c.get("veto_n")]
    if veto_cells:
        n_runs = sum(c["veto_n"] for c in veto_cells)
        rows.append(_row(WARN, "否决封顶",
                         f"{len(veto_cells)}/{len(cells)} 个格含被否决封顶的 run（共 {n_runs} 条，"
                         "T4 严重卡顿率 >1% → 封顶 54）——封顶分只说明「至少这么差」，"
                         "不是该格体验的度量，须回到卡顿证据本身"))
    else:
        rows.append(_row(PASS, "否决封顶", "无被否决封顶的 run"))

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
    labeled = [c for c in inv["campaigns"] if c != "unlabeled"]
    if len(labeled) > 1:
        rows.append(_row(WARN, "战役池化",
                         f"本语料含 {len(labeled)} 个战役（{', '.join(labeled)}）——"
                         "除「优化前后对比」/「纵向趋势」外各段均按格池化，其中位数"
                         "**既不是前也不是后**；头条数字须取自 `--campaign <id>` 的单战役报告"))
    else:
        rows.append(_row(PASS, "战役池化",
                         f"单战役（{labeled[0]}）" if labeled else "无战役标签，无池化风险"))

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
        # cannot be told apart from a check that was forgotten (D-150)
        rows.append(_row(PASS, "效应量", "单战役语料，无前后对比可核算"))

    biased, judged = [], 0
    no_evidence, never_rotated = True, False
    for k in order_effect.ORDER_SENSITIVE_KPIS:
        res = order_effect.analyze(records, kpi=k, min_samples=min_samples)
        no_evidence = no_evidence and res["no_order_evidence"]
        never_rotated = never_rotated or res["rotation_warning"]
        for p in res["profiles"]:
            if p["order_effect_suspected"] is None:
                continue                      # not computable — not "no effect"
            judged += 1
            if p["order_effect_suspected"]:
                biased.append(p)
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
        rows.append(_row(WARN, "序位效应", "已轮转，但各 profile 在场位次不足 2——"
                                           "**本轮无法校验**是否残留序位偏倚"))
    elif biased:
        rows.append(_row(WARN, "序位效应", f"{len(biased)}/{judged} 处疑似位置-KPI 相关"
                                           "（反平衡可能失效，须复核）"))
    else:
        rows.append(_row(PASS, "序位效应", f"{judged} 处均未见序位偏倚"))

    rank = {FAIL: 0, WARN: 1, PASS: 2}
    return sorted(rows, key=lambda r: rank[r["severity"]])


def render_markdown(rows):
    lines = ["## 发布前自检", "",
             "> FAIL=客观错误，**阻断发布**；WARN=**须由人解释**后才可发布"
             "（工具不替人判断）；PASS=该项无问题。本自检**不能**替代 runbook §5 中"
             "需要人工判断的条目（结论措辞、归档完整性、claim_scope 落款）。", "",
             "| 判定 | 检查项 | 说明 |", "|---|---|---|"]
    icon = {FAIL: "⛔ FAIL", WARN: "⚠ WARN", PASS: "✅ PASS"}
    for r in rows:
        lines.append(f"| {icon[r['severity']]} | {r['item']} | {r['detail']} |")
    fails = sum(1 for r in rows if r["severity"] == FAIL)
    warns = sum(1 for r in rows if r["severity"] == WARN)
    lines += ["", f"**结论：{'不可发布' if fails else '可发布'}**"
                  f"（FAIL {fails} / WARN {warns}）。"
                  + ("" if fails else "每条 WARN 都须在报告正文有对应说明。")]
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="ANEB pre-publish self-check")
    ap.add_argument("inputs", nargs="+", help="results JSONL files / globs")
    ap.add_argument("--min-samples", type=int, default=cc.DEFAULT_MIN_SAMPLES)
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    recs, files = cc.load_records(args.inputs)
    rows = check(recs, args.min_samples)
    print(render_markdown(rows))
    print(f"\n<!-- records={len(recs)} files={len(files)} -->", file=sys.stderr)
    return 1 if any(r["severity"] == FAIL for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
