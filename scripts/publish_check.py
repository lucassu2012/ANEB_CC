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
    if inv["with_campaign"] == 0:
        rows.append(_row(FAIL, "战役标签", "全部记录无 run.campaign——热力卡/归因塌缩为"
                                           "单格，报告无分组意义"))
    elif inv["with_campaign"] < inv["records"]:
        missing = inv["records"] - inv["with_campaign"]
        rows.append(_row(WARN, "战役标签", f"{missing}/{inv['records']} 条无标签，"
                                           "将落入 unlabeled 桶"))
    else:
        rows.append(_row(PASS, "战役标签", "全部记录已标注"))

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

    hot = [c for c in buffering_rollup.analyze(records, min_samples)["cells"]
           if c["distortion_hotspot"]]
    rows.append(_row(WARN, "批化失真", f"{len(hot)} 个失真热点格"
                                       "（须先做失真核算，再谈网络结论）")
                if hot else _row(PASS, "批化失真", "无失真热点"))

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

    biased, judged = [], 0
    for k in order_effect.ORDER_SENSITIVE_KPIS:
        for p in order_effect.analyze(records, kpi=k, min_samples=min_samples)["profiles"]:
            if p["order_effect_suspected"] is None:
                continue                      # not computable — not "no effect"
            judged += 1
            if p["order_effect_suspected"]:
                biased.append(p)
    if not judged:
        rows.append(_row(WARN, "序位效应", "无 order_index 证据——无法校验反平衡是否奏效"))
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
