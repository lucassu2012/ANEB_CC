# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/synth_campaign.py + the synthetic-data guard.

Two things must hold, and the second one is a safety property:
  1. the generated corpus is contract-complete (it has to survive the report
     front door, or it is useless as rehearsal fuel);
  2. synthetic records are ALWAYS detectable and the report ALWAYS says so —
     fabricated numbers must never be presentable as field measurements.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import campaign_common as cc
import campaign_report as rpt
import synth_campaign as sc
import validate_results as vr
from synth import aqs_records

SMALL = dict(points=2, carriers=("cmcc",), time_bands=("busy", "idle"),
             tiers=("metro", "core"), repeats=2, campaigns=("base",))


def test_the_rehearsal_can_show_a_clean_attribution_row():
    """The rehearsal exists so nobody meets a full-scale report for the first
    time in the field. On the default corpus every attribution row carries
    MIXED_CAMPAIGN — the cell key has no campaign dimension and there are two —
    so an operator running only the command the runbook used to give never sees
    the kind of row they will actually read. Scoping to one campaign is the
    second command it now gives them (D-270).

    Both sides have floors. The pooled view must really be fully marked, or
    there is nothing to demonstrate; the scoped view must really come out
    clean, or the demonstration is empty.
    """
    import attribution
    import campaign_common as cc

    def mixed(cell):
        return [f for f in attribution.incomparability_flags(cell)
                if f.startswith("MIXED_CAMPAIGN")]

    recs = sc.generate()
    ids = {cc.campaign_labels(r)["campaign_id"] for r in recs}
    assert len(ids) >= 2, f"corpus has {ids} — the pooled case cannot arise"

    pooled = attribution.attribute(recs)["cells"]
    assert pooled, "no attribution cells at all"
    unmarked = [c for c in pooled if not mixed(c)]
    assert not unmarked, (
        f"{len(unmarked)} of {len(pooled)} pooled rows carry no MIXED_CAMPAIGN "
        "— the rehearsal no longer demonstrates the pooling it warns about")

    one = sorted(ids)[0]
    scoped = attribution.attribute(
        [r for r in recs if cc.campaign_labels(r)["campaign_id"] == one])["cells"]
    still = [c for c in scoped if mixed(c)]
    assert not still, f"{len(still)} rows still pooled after --campaign {one}"
    # 30 of the 96 cells here, measured. The rehearsal CSV showed 58 note-free
    # rows, and that is a DIFFERENT population — one row per (cell, KPI), two
    # KPIs, against one cell per key at the default KPI. A floor lifted from
    # the other population is not a floor for this one.
    # Everything above reads attribute()'s return value, and the claim in the
    # docstring is about what the OPERATOR SEES. Those are different objects:
    # the note lists are written per surface by hand, and markers have gone
    # missing from a rendered table while the analyser still reported them
    # (D-160 / D-222). So the rendered side gets its own look (D-280).
    import csv
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        written = {os.path.basename(p): p for p in rpt.write_csv_tables(
            [r for r in recs
             if cc.campaign_labels(r)["campaign_id"] == one],
            os.path.join(d, "report"))}
        assert "report_attribution.csv" in written, sorted(written)
        with open(written["report_attribution.csv"],
                  encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
    assert rows, "the scoped attribution table rendered no rows at all"
    # The CSV splits what markdown prints as one note into typed columns, so the
    # flags land in `incomparability` rather than a 备注 cell — read off the
    # header rather than assumed, after the first version of this guessed and
    # the missing-column assertion printed the real one (D-280).
    assert "incomparability" in rows[0], list(rows[0])
    rendered_clean = [r for r in rows if not (r["incomparability"] or "").strip()]
    assert rendered_clean, (
        "every rendered attribution row carries a note — the operator still "
        "never meets a clean row, whatever attribute() reports")

    clean = [c for c in scoped if not attribution.incomparability_flags(c)]
    assert len(clean) >= 30, (
        f"only {len(clean)} of {len(scoped)} scoped rows are free of "
        "incomparability flags — the rehearsal can no longer show the operator "
        "a usable attribution row")


def test_generated_corpus_passes_the_contract_gate():
    """The whole point: this corpus must survive validate_results / the report
    front door, exactly like real field data would."""
    recs = sc.generate(**SMALL)
    errors, _warnings = vr.validate_records(recs, vr.load_schema(vr.DEFAULT_SCHEMA))
    assert errors == [], errors[:5]
    assert rpt.contract_gate(recs) == []


def test_deterministic_for_a_given_seed():
    assert sc.generate(seed=7, **SMALL) == sc.generate(seed=7, **SMALL)


def test_different_seed_changes_the_corpus():
    assert sc.generate(seed=7, **SMALL) != sc.generate(seed=8, **SMALL)


def test_every_record_carries_both_markers():
    for r in sc.generate(**SMALL):
        assert isinstance(r["synthetic"], dict)                          # marker 1
        assert r["run"]["campaign"]["campaign_id"].startswith("SYNTH-")  # marker 2
        assert cc.is_synthetic(r) is True


def test_marker_survives_losing_either_half():
    """A corpus stripped of the additive block, or re-labelled away from the
    SYNTH- prefix, must STILL be detected by the remaining marker."""
    rec = sc.generate(**SMALL)[0]
    stripped = {k: v for k, v in rec.items() if k != "synthetic"}
    assert cc.is_synthetic(stripped) is True          # campaign_id prefix remains
    relabelled = dict(rec)
    relabelled["run"] = dict(rec["run"])
    relabelled["run"]["campaign"] = dict(rec["run"]["campaign"],
                                         campaign_id="sz-2026Q3-baseline")
    assert cc.is_synthetic(relabelled) is True        # additive block remains


def test_real_records_are_not_flagged():
    assert cc.count_synthetic(aqs_records(90, 3)) == 0
    assert cc.is_synthetic(aqs_records(90, 1)[0]) is False


def test_report_markdown_carries_the_banner_before_any_claim():
    md = rpt.build_report_markdown(sc.generate(**SMALL))
    assert "合成数据警告" in md
    assert "不得" in md
    # banner precedes the claim_scope line and every data section
    assert md.index("合成数据警告") < md.index("claim_scope")
    assert md.index("合成数据警告") < md.index("## 覆盖盘点")


def test_report_html_carries_the_banner():
    html = rpt.build_report_html(sc.generate(**SMALL), "2026-07-25 00:00:00 +0800")
    assert "合成数据警告" in html
    assert "class='synth'" in html


def test_real_corpus_report_has_no_banner():
    """The guard must not cry wolf on real data — that would train people to
    ignore it."""
    assert "合成数据警告" not in rpt.build_report_markdown(aqs_records(90, 5))


def test_grid_covers_every_requested_cell():
    recs = sc.generate(**SMALL)
    cells = {(r["run"]["campaign"]["point_id"], r["run"]["campaign"]["carrier"],
              r["run"]["campaign"]["time_band"], r["run"]["campaign"]["tier"])
             for r in recs}
    assert len(cells) == 2 * 1 * 2 * 2          # points x carriers x bands x tiers
    assert len(recs) == 2 * 1 * 2 * 2 * 2       # x repeats


def test_invalid_scenarios_null_both_value_and_grade():
    """R-10 pairing: an invalid scenario carries no KPI value AND no grade."""
    seen_invalid = False
    for r in sc.generate(points=4, repeats=4, campaigns=("base",)):
        for s in r["scenarios"]:
            if s["validity"] != "invalid":
                continue
            seen_invalid = True
            for k in sc.GRADED:
                assert s["kpi"][k] is None
                assert s["kpi"][k.split("_")[0] + "_grade"] is None
    assert seen_invalid, "fixture should contain invalid scenarios to exercise this"


def test_rehearsal_can_demonstrate_both_verdicts():
    """A rehearsal whose every verdict is negative cannot tell a working
    improvement-detection path from a silent one — the vacuous-test trap wearing
    a corpus. At the runbook's default grid ALL 32 comparable cells used to land
    inside the noise (designed effect ~3 AQS against a ~6 noise scale), so the
    corpus now carries ONE optimisation big enough to clear it (D-182)."""
    recs = sc.generate()
    inv = rpt.inventory(recs)
    before, after = rpt.auto_compare_ids(inv)
    rows = rpt.compare_campaigns(recs, before, after)["rows"]
    real = [r for r in rows if r["within_noise"] is False]
    noisy = [r for r in rows if r["within_noise"] is True]
    # both paths demonstrable in one rehearsal, which is the whole point
    assert real, "rehearsal must be able to show a detected improvement"
    assert noisy, "…and must still show sub-noise deltas as sub-noise"
    designed = f"SYNTH-P{sc.OPTIMISED_POINT_INDEX + 1:02d}"
    assert {r["cell"]["point_id"] for r in real} == {designed}
    assert all(r["delta"] > 0 for r in real)        # an improvement, not a regression
    # This function covers designed effects real_improvement (the assertions
    # above) and sub_noise_improvement (the `noisy` bucket) and media_difference
    # (just below) — each named so the invariant that follows can find it.
    media = [ln for ln in rpt.render_summary_markdown(recs).splitlines()
             if ln.startswith("- **接入介质") or ln.startswith("- **蜂窝劣")][0]
    assert "未观察到超出测量噪声的介质差异" in media
    # Same invariant D-183 put on CHAOS_PATHOLOGIES, applied to the table D-182
    # created — otherwise this is one more declaration nobody checks.
    with open(__file__, encoding="utf-8") as f:
        src = f.read()
    unchecked = [k for k, _ in sc.DESIGNED_EFFECTS if k not in src]
    assert not unchecked, f"designed effects with no test naming them: {unchecked}"
    # …and the summary NAMES the improved cells. Every other signal names its
    # examples; this one gave counts only, so the reader learned four cells got
    # better but not which — the question the round exists to answer (D-182).
    line = [ln for ln in rpt.render_summary_markdown(recs).splitlines()
            if ln.startswith("- **优化前后")][0]
    assert designed in line
    assert "±" in line              # named with its noise scale, never bare


# ----------------------------------------------------------- M3 扩展轮形状
#
# GUARD_DIFF C-4 的原话是「一次性脚本没有守卫」。把整形器的能力搬进生成器之后，
# 这一节就是那批**缺失的守卫**——每一条都对着扩展轮真正要演示的一件事。

SMALL_EXP = dict(points=3, carriers=("cmcc",), time_bands=("busy", "idle"),
                 counted_repeats=4, warmup_runs=1, forensic_points=1,
                 forensic_runs_per_cell=2, forensic_warmup_runs=1, seed=4242)


def _one_off_shaper():
    """The historical one-off整形器, loaded from evidence/ as a module."""
    import importlib.util
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(root, "evidence", "m3_expansion_rehearsal_20260801",
                        "shape_expansion_corpus.py")
    assert os.path.exists(path), path
    spec = importlib.util.spec_from_file_location("shape_expansion_corpus", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_generator_still_reproduces_the_one_off_shaper():
    """金标准对拍：同参数同种子，生成器的产物必须与那只一次性整形器的等价。

    唯一容许的差异是 `synthetic.generator` 这一处**溯源字段**——记录现在如实指认
    真正造出它的那份代码。它有零个读者（`campaign_common.is_synthetic` 只看
    `synthetic` 是不是 dict，或看 `SYNTH-` 前缀），故不改变任何分析结论；而归档
    的那份语料本来就是**自相矛盾**的：同一次运行里 quick 半边写 `synth_campaign.py`、
    取证半边写 `shape_expansion_corpus.py`。现在两半一致了。

    容许清单写成**逐字段的白名单**而不是「差不多一样就行」：任何第二处差异都会
    让这条守卫红——那正是它存在的理由。整形器留在 evidence/ 里不删，所以这条
    对拍可以一直跑下去，而不是只在交付那天跑过一次（D-322）。
    """
    import random
    old = _one_off_shaper()
    # the golden was built before D-379 raised the forensic round count to 5,
    # so the comparison pins the shaper's own value rather than today's default.
    assert old.FORENSIC_RUNS_PER_CELL == 4, old.FORENSIC_RUNS_PER_CELL
    assert sc.EXPANSION_FORENSIC_RUNS == 5, sc.EXPANSION_FORENSIC_RUNS

    rng = random.Random(old.SEED)
    q, q_warm = old.build_quick_body(rng)
    f, f_warm = old.build_forensic_subset(
        rng, q[-1]["run"]["started_at_epoch_ms"] + 600_000)
    raw = q + f
    warm = set(q_warm) | set(f_warm)
    golden = {"raw": raw,
              "counted": [r for r in raw if r["run"]["run_id"] not in warm]}
    golden["counted_quick"] = [r for r in golden["counted"]
                               if r["run"]["mode"] == "quick"]
    golden["counted_forensic"] = [r for r in golden["counted"]
                                  if r["run"]["mode"] == "forensic"]

    new = sc.generate_expansion(
        points=old.POINTS, carriers=old.CARRIERS, time_bands=old.TIME_BANDS,
        tier=old.TIERS[0], campaign=old.CAMPAIGN, counted_repeats=old.N_COUNTED,
        warmup_runs=old.N_WARMUP, forensic_points=len(old.FORENSIC_POINT_INDICES),
        forensic_runs_per_cell=old.FORENSIC_RUNS_PER_CELL,
        forensic_warmup_runs=old.FORENSIC_WARMUP_RUNS, seed=old.SEED)

    assert new["warmup_ids"] == warm
    # 那一处容许的差异必须**真的在**。否则生成器改回盖整形器的名字时，下面每条
    # 记录都会比出相等、这条守卫全绿，而语料在谎报自己的出处。突变审计里先预测
    # 它会存活、再去验，果然存活（D-325）——这三行就是那次存活逼出来的。
    assert {r["synthetic"]["generator"] for r in new["raw"]} == {sc.GENERATOR}
    assert {r["synthetic"]["generator"] for r in golden["counted_forensic"]} == {
        "shape_expansion_corpus.py"}
    assert {r["synthetic"]["generator"] for r in golden["counted_quick"]} == {
        sc.GENERATOR}, "归档语料的 quick 半边本来就写着 synth_campaign.py（它自相矛盾）"
    for key in ("raw", "counted", "counted_quick", "counted_forensic"):
        a, b = golden[key], new[key]
        assert len(a) == len(b), f"{key}: {len(a)} vs {len(b)}"
        for x, y in zip(a, b):
            if x == y:
                continue
            # exactly one field may differ, and only on the forensic half
            assert y["run"]["mode"] == "forensic", (key, y["run"]["run_id"])
            assert x["synthetic"]["generator"] == "shape_expansion_corpus.py"
            assert y["synthetic"]["generator"] == sc.GENERATOR
            xx = dict(x, synthetic=dict(x["synthetic"], generator=sc.GENERATOR))
            assert xx == y, f"{key}/{y['run']['run_id']}: 差异不止溯源字段一处"


def test_forensic_runs_carry_a_real_latin_square():
    """取证轮转：每轮是一次 profile 全排列，**每个位次跨轮也是一次全排列**。

    后半句才是拉丁方的定义。只检查「每轮三个都不同」的守卫，会放过一张三行完全
    相同的表——那正是「未轮转」，也正是 D-354 要这张表来排除的东西。
    """
    square = sc.latin_square()
    n = len(sc.PROFILES)
    assert len(square) == n
    for row in square:
        assert sorted(row) == sorted(sc.PROFILES)          # 每轮是全排列
    for col in range(n):
        assert sorted(r[col] for r in square) == sorted(sc.PROFILES)  # 每位次也是

    bundle = sc.generate_expansion(**SMALL_EXP)
    assert bundle["counted_forensic"], "取证子集为空，本条什么都没测到"
    for rec in bundle["counted_forensic"]:
        scns = rec["scenarios"]
        assert len(scns) == n * n
        assert [s["order_index"] for s in scns] == list(range(n * n))
        assert [s["repeat_index"] for s in scns] == [r for r in range(n) for _ in range(n)]
        rounds = [tuple(s["profile_id"] for s in scns[r * n:(r + 1) * n])
                  for r in range(n)]
        assert tuple(rounds) == square
        # scenario_order 把同一件事编码在 run 上：三段以 `|` 连，段内以 `,` 连
        order = rec["run"]["scenario_order"]
        assert order.split("|") == [",".join(r) for r in square]
        assert rec["run"]["mode"] == "forensic"


def test_the_ledger_is_the_only_thing_that_knows_which_run_was_a_warm_up():
    """预热轮**会正常上报**（口径 D-366）——语料本身没有任何字段说明它是预热。

    两个方向都要钉住：
      1. `counted` 恰好等于 `raw` 减去台账点名的那些（台账真的说了算）；
      2. 语料里**没有**任何自称预热的字段。少了第 2 条，生成器可以偷偷给记录盖一个
         合成专用的戳，于是彩排演的是一个外场根本造不出来的形状——分析层看着能
         认出预热轮，真到外场那天它一个也认不出（D-309 的反面）。
    """
    bundle = sc.generate_expansion(**SMALL_EXP)
    ids_raw = {r["run"]["run_id"] for r in bundle["raw"]}
    ids_counted = {r["run"]["run_id"] for r in bundle["counted"]}
    ledger_ids = [row[0] for row in bundle["ledger_rows"]]
    assert len(ledger_ids) == len(set(ledger_ids)) == len(bundle["warmup_ids"])
    assert set(ledger_ids) <= ids_raw
    assert ids_counted == ids_raw - set(ledger_ids)
    assert ids_counted, "counted 为空，上一条断言会恒真"

    cols = dict(zip(sc.WARMUP_LEDGER_HEADER, bundle["ledger_rows"][0]))
    assert cols["disposition"] == sc.WARMUP_DISPOSITION
    assert cols["authority"] == sc.WARMUP_AUTHORITY == "D-366"
    assert cols["synthetic"] == "True"

    blob = json.dumps(bundle["raw"], ensure_ascii=False)
    for word in ("warmup", "warm_up", "预热", "discard"):
        assert word not in blob.lower() if word.isascii() else word not in blob, (
            f"语料里出现了自称预热的字样 {word!r} —— 外场语料造不出这个字段")


def test_the_designed_warm_up_penalty_is_actually_present():
    """E2 是个**设计效应**：预热轮系统性更差。它必须真的在，否则「台账排除到底
    改变了什么」这个问题在彩排里没有答案，而那正是要演示的那件事。"""
    bundle = sc.generate_expansion(**SMALL_EXP)
    warm = [r for r in bundle["raw"] if r["run"]["run_id"] in bundle["warmup_ids"]
            and r["run"]["mode"] == "quick"]
    cold = [r for r in bundle["counted_quick"]]
    assert warm and cold

    def med_rtt(recs):
        vals = sorted(s["kpi"]["n1_rtt_p50_ms"] for r in recs for s in r["scenarios"]
                      if s["kpi"].get("n1_rtt_p50_ms") is not None)
        return vals[len(vals) // 2]

    assert med_rtt(warm) > med_rtt(cold) * 1.05, (med_rtt(warm), med_rtt(cold))


def test_the_s2_jitter_lands_where_stability_looks_for_it():
    """s2 场景内生抖动必须被 `SCENARIO_INTRINSIC_JITTER`（D-382）真的认出来。

    这条不查生成器自己的内部状态，而是**把语料喂给判据**：一个设计效应若与检测它
    的判据对不上，彩排就是在演一件没人会看的事，而坏掉的检测路径与好用的那条在
    输出上分不开（D-182 的形状）。反方向同样要钉：网络侧 KPI 上零命中——判据不
    越界，越界了它就不再是判别证据。
    """
    import stability
    bundle = sc.generate_expansion(**dict(SMALL_EXP, counted_repeats=8))
    recs = bundle["counted_quick"]

    scen = stability.stability_cells(recs, "t1_ttft_ms")
    marked = [c for c in scen if c.get("scenario_intrinsic_jitter")]
    assert marked, "没有一个单元被判为场景内生抖动——设计效应与判据对不上了"
    assert {c["cell"]["profile_id"] for c in marked} == {sc.PROFILES[1]}, (
        "被标记的不只是 s2 —— 抖动漏到别的 profile 上了")

    net = stability.stability_cells(recs, "n1_rtt_p50_ms")
    assert not [c for c in net if c.get("scenario_intrinsic_jitter")], (
        "网络侧 KPI 上出现了场景内生抖动标记 —— 判据越界")


def test_the_scenario_side_list_has_exactly_one_home():
    """两张 KPI 清单只能有一处定义。§2.14 说 `stability` 是它们在全仓**唯一**被
    命名的地方；生成器再抄一份，设计效应与判据就能悄悄分叉，而「两处逐字相同」
    正是最容易分叉又最难察觉的状态（D-317）。

    **判据是「有没有第二个绑定拿着同一份值」，不是源码里出没出现过那几个词。**
    第一版拿裸子串去比，被 `GRADED` 当场骗了——它恰好把 `n1`/`n2` 排在相邻位置，
    于是守卫报出一处根本不存在的副本。会误报的守卫等于没有守卫（D-319）。

    边界如实写在这里：它咬的是**副本诞生的那一刻**（新副本必然与本尊相等），
    咬不住一份已经漂过的副本；而漂移正是从相等开始的，所以这是对的那一刻。
    """
    import stability
    assert set(sc.warmup_scaled_kpis()) == (
        set(stability.SCENARIO_SIDE_KPIS) | set(stability.NETWORK_SIDE_KPIS)
        | {"u1_goodput_mbps"})
    assert not (set(stability.SCENARIO_SIDE_KPIS) & set(stability.NETWORK_SIDE_KPIS))
    rivals = [n for n, v in vars(sc).items()
              if isinstance(v, tuple)
              and v in (stability.SCENARIO_SIDE_KPIS, stability.NETWORK_SIDE_KPIS)]
    assert not rivals, (
        f"synth_campaign 里出现了拿着同一份清单的第二个名字：{rivals} —— "
        "清单必须读 stability 的，不是抄它的")
    with open(sc.__file__, encoding="utf-8") as f:
        src = f.read()
    for lst in (stability.SCENARIO_SIDE_KPIS, stability.NETWORK_SIDE_KPIS):
        literal = "(" + ", ".join('"%s"' % k for k in lst) + ")"
        assert literal not in src, f"函数体里内联了一份字面量 {literal}"


def test_expansion_corpus_survives_the_contract_gate_and_the_front_door():
    """新形状不被现有守卫误拒——彩排的合格线之一，且三份分面各自都要过。"""
    bundle = sc.generate_expansion(**SMALL_EXP)
    schema = vr.load_schema(vr.DEFAULT_SCHEMA)
    for key in ("raw", "counted", "counted_quick", "counted_forensic"):
        recs = bundle[key]
        assert recs, key
        errors, _warnings = vr.validate_records(recs, schema)
        assert errors == [], (key, errors[:3])
        assert rpt.contract_gate(recs) == [], key


def test_expansion_records_are_double_marked_before_anything_is_written():
    """D-270：写盘前逐条断言双重标记，任一条不成立就**一个文件都不产出**。"""
    import tempfile
    bundle = sc.generate_expansion(**SMALL_EXP)
    assert sc.assert_double_marked(bundle["raw"]) == len(bundle["raw"])
    for r in bundle["raw"]:
        assert isinstance(r["synthetic"], dict)
        assert r["run"]["campaign"]["campaign_id"].startswith(sc.CAMPAIGN_PREFIX)

    broken = [dict(r) for r in bundle["raw"]]
    broken[3] = {k: v for k, v in broken[3].items() if k != "synthetic"}
    broken[3]["run"] = dict(broken[3]["run"],
                            campaign=dict(broken[3]["run"]["campaign"],
                                          campaign_id="sz-2026Q3-baseline"))
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "exp")
        try:
            sc.write_expansion_artifacts(prefix, dict(bundle, raw=broken))
            raise AssertionError("隔离自检没拦住缺标记的记录")
        except ValueError:
            pass
        assert os.listdir(d) == [], f"自检失败却已经写出文件：{os.listdir(d)}"


def test_expansion_refuses_conflicting_flags_instead_of_ignoring_them():
    """静默忽略一个参数，会让操作者以为自己拿到的是另一份语料。逐条拒绝并点名。"""
    import argparse
    base = dict(repeats=None, chaos=False, unlabelled=False, tiers=None,
                campaigns=None, out="/tmp/exp")
    assert sc._expansion_conflicts(argparse.Namespace(**base)) == []
    for field, value, needle in (("repeats", 5, "--repeats"),
                                 ("chaos", True, "--chaos"),
                                 ("unlabelled", True, "--unlabelled"),
                                 ("tiers", "metro,core", "--tiers"),
                                 ("campaigns", "a,b", "--campaigns"),
                                 ("out", "/tmp/exp.jsonl", "-o")):
        got = sc._expansion_conflicts(argparse.Namespace(**dict(base, **{field: value})))
        assert any(needle in g for g in got), (field, got)


def test_expansion_cli_writes_five_artifacts_and_the_prefix_rule_holds():
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        prefix = os.path.join(d, "expansion")
        cmd = [sys.executable, os.path.join(os.path.dirname(sc.__file__),
                                            "synth_campaign.py"),
               "-o", prefix, "--expansion", "--points", "3", "--carriers", "cmcc",
               "--counted-repeats", "3", "--forensic-points", "1",
               "--forensic-runs", "2", "--seed", "4242"]
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        assert r.returncode == 0, r.stderr[:600]
        written = sorted(os.listdir(d))
        assert written == ["expansion_counted.jsonl", "expansion_counted_forensic.jsonl",
                           "expansion_counted_quick.jsonl", "expansion_raw.jsonl",
                           "expansion_warmup_ledger.csv"], written
        assert sc.WARNING in r.stdout
        assert sc.WARMUP_AUTHORITY in r.stdout        # 台账的出处印在操作者眼前

        bad = subprocess.run(cmd + ["--repeats", "5"], capture_output=True,
                             text=True, errors="replace")
        assert bad.returncode == 2, bad.stdout[:400]
        assert "--repeats" in bad.stderr, bad.stderr[:400]


def test_tier_ordering_is_realistic():
    """metro < regional < core on RTT — otherwise the attribution matrix
    rehearsal would be meaningless."""
    recs = sc.generate(points=3, repeats=6, campaigns=("base",),
                       carriers=("cmcc",), time_bands=("busy",))
    by_tier = {}
    for r in recs:
        vals = [s["kpi"]["n1_rtt_p50_ms"] for s in r["scenarios"]
                if s["kpi"]["n1_rtt_p50_ms"] is not None]
        by_tier.setdefault(r["run"]["campaign"]["tier"], []).extend(vals)
    med = {t: sorted(v)[len(v) // 2] for t, v in by_tier.items()}
    assert med["metro"] < med["regional"] < med["core"]
