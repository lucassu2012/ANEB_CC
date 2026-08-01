#!/usr/bin/env python3
"""M3 扩展轮「彩排语料」整形器 —— 一次性工具，仅供彩排（T6 ②）。

=============================================================================
⚠ 已被替代（SUPERSEDED），2026-08-01 · D-389 · T12 ③ / GUARD_DIFF C-4
-----------------------------------------------------------------------------
**替代者**：`scripts/synth_campaign.py --expansion`（`generate_expansion()`）。
下面这三样它现在原生就会造，不必再带一只一次性脚本——**而一次性脚本没有守卫**，
那正是 C-4 登记的问题本身。生成器侧已配 10 条守卫，见
`scripts/tests/test_synth_campaign.py` 的「M3 扩展轮形状」一节。

**本文件保留、不删**，有两个用处，都还在跑：
  1. 它是 `evidence/m3_expansion_rehearsal_20260801/` 这份彩排证据包的**出处**，
     删掉它，那批归档产物就变成无法复现的孤儿；
  2. `test_the_generator_still_reproduces_the_one_off_shaper` **仍然 import 它**，
     把它当金标准逐条对拍。所以它不是死代码，是**一条守卫的参照物**。

**新代码不要再用它。** 对拍已实测的唯一差异：取证记录的 `synthetic.generator`
如实改成了 `synth_campaign.py`（该字段全仓零读者；归档语料的 quick 半边本来就
写着 `synth_campaign.py`，即它自相矛盾）。另注：本文件里的
`FORENSIC_RUNS_PER_CELL = 4` 已被 **D-379（取证 5 轮）** 作废，生成器默认取 5；
**此处刻意不改**——历史证据照它当时的样子留着。
=============================================================================

=============================================================================
本脚本产出的每一个数字都是**虚构的**。它不是测量。
产物一律留在本目录（`evidence/m3_expansion_rehearsal_20260801/`），
**绝不可**与外场语料同目录、绝不可外发（runbook §0.5 页脚 / D-270）。
=============================================================================

为什么需要它（而不是直接 `synth_campaign.py`）：
`synth_campaign.generate()` 造的是 M2 的形状——`mode="quick"`、每场景
`repeat_index=0`、全语料同一个 `scenario_order`。扩展轮（T3 提案
`docs/M3_EXPANSION_ROUND_PROPOSAL.md`）要的是**另外三样东西**，现有生成器
一样都造不出来：

  ① **n=15 计入 + 每格 1 轮丢弃预热**（D-366 口径）——预热轮**会**正常上报，
     只能靠**台账**在拉取时排除。本脚本因此同时产出两份语料
     （`_raw` = 拉取到的全部 16/格；`_counted` = 按台账排除后的 15/格）
     与一份台账 CSV，让「台账排除到底改变了什么」可被对着核，而不是被声称。
  ② **取证子集的 3×3 拉丁方轮转**（D-354 已验证轮转正确的那个形状）——
     一次取证 run = 9 场景，`order_index` 0..8、`repeat_index` 0,0,0,1,1,1,2,2,2、
     `scenario_order` 为三个轮次以 `|` 连接（契约示例即此写法）。
  ③ **s2 场景内生抖动**（D-372 裁定：抖在场景/服务端侧，不在网络路径）——
     对 s2 的 TTFT/ITL 额外加一层 per-run 抖动，**而 `n1_rtt_p50_ms` 不动**，
     复现「同批 RTT 平稳、TTFT 独抖」这个形状。

**设计效应（DESIGNED_EFFECTS 的同一套纪律：给彩排一个「对着核」的答案）**——
下面每个幅度都只是**设计值**，其**出处是决策号里已归档的实测值**，本脚本
不产生任何新的测量，也不得被引用为测量：

  E1  s2 的复测 CV 明显高于 s1/s3，而同批 `n1_rtt_p50_ms` 的 CV 不随之升高。
      （设计源：D-353 实测 CV 5.5/10.3/5.9%；D-372 判定其为场景内生。）
  E2  预热轮（每格第一条）系统性更差，且**只有台账认得它**——
      排除前后每格 n 由 16 变 15。（设计源：D-358 蜂窝丢一轮预热值 RTT≈15%。）
  E3  取证子集三轮次轮转齐全，`order_effect` 不应再报「拉丁方未轮转」。
      （设计源：D-354。）

用法（在本目录下）：
    python shape_expansion_corpus.py
"""
import csv
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, SCRIPTS)

import synth_campaign as sc  # noqa: E402

PROFILES = sc.PROFILES
SEED = 20260801

# ---------------------------------------------------------------- 扩展轮形状
# 网格维度照 T3 提案 §3：6–8 点位 × 忙闲 × 双运营商，**单层级**（D-48 单实例
# E-01，扩展轮不排三层级行程）。点位真名 **PENDING-PO**——此处沿用生成器的
# `SYNTH-P0x`，因为那个前缀本身就是合成标记 #2，换成别的名字会削弱标记。
POINTS = 8
CARRIERS = ("cmcc", "cucc")
TIME_BANDS = ("busy", "idle")
TIERS = ("metro",)
CAMPAIGN = "EXP"          # 生成器会自动加 `SYNTH-` 前缀

N_COUNTED = 15            # T3 提案 §1：扩展轮 n≥15（依 s1/s3 网络侧 CV）
N_WARMUP = 1              # D-366：每格 1 轮丢弃的预热
N_RAW = N_COUNTED + N_WARMUP

# 取证子集（大脑裁定方向 B「quick 主体 + 取证子集」，待 PO 确认）：
# 序位/预热是**协议 + 设备**属性、不是强点位属性，故子集校验后全网格套用轮转。
# 子集取头两个点位 × 双运营商 × 忙闲 = 8 格，每格 4 轮取证（T3 提案 §4.2：
# ≥2 轮为最低、建议 4 轮，使每位次 n≥4）。
FORENSIC_POINT_INDICES = (0, 1)
FORENSIC_RUNS_PER_CELL = 4
FORENSIC_WARMUP_RUNS = 1   # 取证格同样先跑一轮丢弃的预热（口径同 D-366）

# --- 设计效应幅度（设计值，非测量；出处见文件头 E1/E2/E3） ---
S2_EXTRA_JITTER = 0.11     # s2 的 TTFT/ITL 额外相对抖动（只加在场景侧）
WARMUP_PENALTY = 0.16      # 预热轮整体更差的比例
FORENSIC_ROUND0_RESIDUAL = 0.04   # 预热轮已丢弃后，取证第 0 轮的残余（App/TLS）

LATIN_SQUARE = (           # T3 提案 §4.2 的 3×3 循环拉丁方
    (PROFILES[0], PROFILES[1], PROFILES[2]),
    (PROFILES[1], PROFILES[2], PROFILES[0]),
    (PROFILES[2], PROFILES[0], PROFILES[1]),
)
FORENSIC_SCENARIO_ORDER = "|".join(",".join(r) for r in LATIN_SQUARE)

# 这些 KPI 是「场景侧耗时」，s2 的内生抖动加在它们身上；
# `n1_rtt_p50_ms` / `n2_jitter_ms` **刻意不动**——那正是 D-372 的判别证据。
SCENARIO_SIDE_KPIS = ("t1_ttft_ms", "t2_itl_p95_ms", "u2_tool_loop_p95_ms")
NETWORK_SIDE_KPIS = ("n1_rtt_p50_ms", "n2_jitter_ms")
ALL_TIMING_KPIS = SCENARIO_SIDE_KPIS + NETWORK_SIDE_KPIS + ("u1_goodput_mbps",)


def cell_key(rec):
    c = (rec.get("run") or {}).get("campaign") or {}
    return (c.get("campaign_id"), c.get("point_id"), c.get("carrier"),
            c.get("time_band"), c.get("tier"))


def _scale_kpi(kpi, keys, factor, *, higher_better=("u1_goodput_mbps",)):
    """把一组 KPI 按 factor 缩放（factor>1 = 更差）。等级标签随之重算。"""
    for k in keys:
        v = kpi.get(k)
        if v is None:
            continue
        kpi[k] = round(v / factor if k in higher_better else v * factor,
                       4 if k in ("t3_stall_rate", "t4_severe_stall_rate") else 2)
    for k in sc.GRADED:
        if k in kpi:
            kpi[k.split("_")[0] + "_grade"] = sc._grade(k, kpi[k])


def apply_s2_intrinsic_jitter(records, rng):
    """E1：只给 s2 的场景侧 KPI 加一层 per-run 抖动，网络侧 KPI 不动。"""
    touched = 0
    for rec in records:
        for scn in rec.get("scenarios") or []:
            if scn.get("profile_id") != PROFILES[1]:
                continue
            f = max(0.5, 1.0 + rng.gauss(0, S2_EXTRA_JITTER))
            _scale_kpi(scn.get("kpi") or {}, SCENARIO_SIDE_KPIS, f)
            touched += 1
    return touched


def build_quick_body(rng):
    """quick 主体：每格 16 条（15 计入 + 1 预热），预热轮=每格文件序第一条。

    生成器把 repeats 放在最内层循环，所以每格的第一条就是该格第一次跑的那一条
    ——正好是预热轮的位置。台账记下它的 run_id，这是**唯一**能认出它的东西
    （D-366：预热轮会正常上报，语料本身没有任何字段说明它是预热）。
    """
    recs = sc.generate(points=POINTS, carriers=CARRIERS, time_bands=TIME_BANDS,
                       tiers=TIERS, repeats=N_RAW, campaigns=(CAMPAIGN,),
                       seed=SEED, radio=True)
    first_seen, warmup_ids = set(), []
    for rec in recs:
        k = cell_key(rec)
        if k in first_seen:
            continue
        first_seen.add(k)
        warmup_ids.append(rec["run"]["run_id"])
        # E2：预热轮整体更差（无线唤醒），网络侧与场景侧一起劣化——
        # 这与 s2 的内生抖动是两回事，故两处分别施加。
        for scn in rec.get("scenarios") or []:
            _scale_kpi(scn.get("kpi") or {}, ALL_TIMING_KPIS, 1.0 + WARMUP_PENALTY)
    apply_s2_intrinsic_jitter(recs, rng)
    return recs, warmup_ids


def build_forensic_subset(rng, start_ms):
    """取证子集：每格 (4 计入 + 1 预热) 条取证 run，每条 9 场景、3×3 轮转。"""
    recs, warmup_ids = [], []
    counter = 0
    pids = sc._point_ids(POINTS)
    for pi in FORENSIC_POINT_INDICES:
        point = pids[pi]
        qf = sc._quality_factor(pi, POINTS)
        for carrier in CARRIERS:
            carrier_f = 1.0 if carrier == "cmcc" else 1.12
            for band in TIME_BANDS:
                band_f = 1.35 if band == "busy" else 1.0
                for run_i in range(FORENSIC_WARMUP_RUNS + FORENSIC_RUNS_PER_CELL):
                    counter += 1
                    is_warmup = run_i < FORENSIC_WARMUP_RUNS
                    base = sc.TIER_BASE_RTT_MS[TIERS[0]]
                    scns = []
                    for rnd, row in enumerate(LATIN_SQUARE):
                        # E2/E3：预热轮整条更差；计入轮只剩 App/TLS 残余，
                        # 且残余只落在**轮内第 0 轮**（D-358 口径）。
                        if is_warmup:
                            round_f = 1.0 + WARMUP_PENALTY
                        else:
                            round_f = 1.0 + (FORENSIC_ROUND0_RESIDUAL if rnd == 0 else 0.0)
                        for pos, profile in enumerate(row):
                            oi = rnd * len(row) + pos
                            rtt = max(3.0, base * qf * carrier_f * band_f * round_f
                                      * (1.0 + rng.gauss(0, 0.045 * 0.5)))
                            scn = sc._scenario(rng, PROFILES.index(profile), rtt,
                                               order_index=oi, suspect_clock=False,
                                               batching=False, transport="cellular",
                                               radio=sc._radio(rng, pi, band, rnd, pos))
                            scn["profile_id"] = profile      # 位次由拉丁方决定
                            scn["repeat_index"] = rnd        # 轮次（D-354 语义）
                            scns.append(scn)
                    usable = [s for s in scns if s["validity"] != "invalid"]
                    if usable:
                        subs = sc._sub_scores(usable[0]["kpi"])
                        score = round(sum(subs.values()) / len(subs), 2)
                        aqs = {"score": score, "low_confidence": len(usable) < 2,
                               "veto_applied": False, "not_computable_reason": None,
                               "input_mapping": "synthetic", "sub_scores": subs}
                    else:
                        aqs = {"score": None, "low_confidence": True,
                               "veto_applied": False,
                               "not_computable_reason": "ALL_SCENARIOS_INVALID",
                               "input_mapping": "synthetic", "sub_scores": {}}
                    run_id = f"synth-{SEED}-{CAMPAIGN}-forensic-{counter:06d}"
                    if is_warmup:
                        warmup_ids.append(run_id)
                    recs.append({
                        "claim_scope": "application_end_to_end_to_probe_node",
                        "kpi_set": "agent-qoe-kpi-v0.2", "aqs_version": "aqs-v0.1",
                        "profile_versions": "s1@0.2,s2@0.2,s3@0.2",
                        "schema_version": "1.0",
                        "synthetic": {"generator": "shape_expansion_corpus.py",
                                      "version": "1", "seed": SEED,
                                      "warning": sc.WARNING},
                        "run": {
                            "run_id": run_id,
                            "started_at_epoch_ms": start_ms + counter * 400_000,
                            "mode": "forensic",
                            "scenario_order": FORENSIC_SCENARIO_ORDER,
                            "transport": "auto(cellular)", "profile_source": "server",
                            "app_version_name": "0.0-synthetic", "app_version_code": 0,
                            "guard_metadata": None,
                            "status": "completed" if usable else "aborted:all_invalid",
                            "aqs": aqs,
                            "campaign": {
                                "campaign_id": sc.CAMPAIGN_PREFIX + CAMPAIGN,
                                "tier": TIERS[0], "point_id": point,
                                "carrier": carrier, "time_band": band,
                                "server_tier_endpoint":
                                    "https://e-01-%s.invalid" % TIERS[0]},
                        },
                        "scenarios": scns,
                    })
    apply_s2_intrinsic_jitter(recs, rng)
    return recs, warmup_ids


def write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def assert_isolated(records, paths):
    """D-270 隔离自检：每条记录都必须双重带标（`synthetic` 块 + `SYNTH-` 前缀），
    每个产物都必须落在本目录内。任一条不成立就**不写盘**，直接失败。"""
    bad_mark = [r["run"]["run_id"] for r in records
                if not r.get("synthetic")
                or not str((r["run"].get("campaign") or {}).get("campaign_id", ""))
                .startswith(sc.CAMPAIGN_PREFIX)]
    if bad_mark:
        raise SystemExit(f"隔离自检失败：{len(bad_mark)} 条记录缺合成标记，例：{bad_mark[0]}")
    outside = [p for p in paths if os.path.dirname(os.path.abspath(p)) != HERE]
    if outside:
        raise SystemExit(f"隔离自检失败：产物落在本目录之外：{outside}")


def main():
    rng = random.Random(SEED)
    quick, quick_warmup = build_quick_body(rng)
    start = quick[-1]["run"]["started_at_epoch_ms"] + 600_000
    forensic, forensic_warmup = build_forensic_subset(rng, start)

    raw = quick + forensic
    warmup_ids = set(quick_warmup) | set(forensic_warmup)
    counted = [r for r in raw if r["run"]["run_id"] not in warmup_ids]

    raw_p = os.path.join(HERE, "expansion_raw.jsonl")
    counted_p = os.path.join(HERE, "expansion_counted.jsonl")
    # 分面语料：方向 B 的两块（quick 主体 / 取证子集）**各自**也要能单独出报告。
    # 理由见 `README.md` 的 F-1/F-2——两块池化在一份报告里时，序位与预热两段
    # 都会被「位次由不同格供样」污染，而那正是取证子集存在的目的。
    quick_p = os.path.join(HERE, "expansion_counted_quick.jsonl")
    forensic_p = os.path.join(HERE, "expansion_counted_forensic.jsonl")
    ledger_p = os.path.join(HERE, "warmup_ledger.csv")
    assert_isolated(raw, [raw_p, counted_p, quick_p, forensic_p, ledger_p])

    write_jsonl(raw_p, raw)
    write_jsonl(counted_p, counted)
    write_jsonl(quick_p, [r for r in counted if r["run"]["mode"] == "quick"])
    write_jsonl(forensic_p, [r for r in counted if r["run"]["mode"] == "forensic"])
    with open(ledger_p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["run_id", "mode", "point_id", "carrier", "time_band",
                    "disposition", "authority", "synthetic"])
        for r in raw:
            rid = r["run"]["run_id"]
            if rid not in warmup_ids:
                continue
            c = r["run"]["campaign"]
            w.writerow([rid, r["run"]["mode"], c["point_id"], c["carrier"],
                        c["time_band"], "预热丢弃", "D-366", "True"])

    cells = {}
    for r in counted:
        cells.setdefault(cell_key(r), []).append(r)
    quick_cells = {k: v for k, v in cells.items()
                   if any(x["run"]["mode"] == "quick" for x in v)}
    print(sc.WARNING)
    print(f"raw      : {len(raw)} runs -> {raw_p}")
    print(f"counted  : {len(counted)} runs -> {counted_p}")
    print(f"ledger   : {len(warmup_ids)} 条预热丢弃 -> {ledger_p}")
    print(f"格数 (counted) = {len(cells)}；quick 每格计入 n = "
          f"{sorted({sum(1 for x in v if x['run']['mode'] == 'quick') for v in quick_cells.values()})}")
    print(f"取证 run 数 (counted) = {sum(1 for r in counted if r['run']['mode'] == 'forensic')}"
          f"；scenario_order 轮次数 = {len(set(FORENSIC_SCENARIO_ORDER.split('|')))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
