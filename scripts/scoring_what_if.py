#!/usr/bin/env python3
"""评分体系三决策的 what-if 模拟器（T59 决策就绪包配套，D-493 三发现的下游）。

**这是模拟器，不改任何生产评分代码**——它把 `full_corpus_labelled.jsonl` 里已落库的
子分当作输入，只重算"如果权重表/总分公式/置信门槛换成另一种写法，73 run 的分数与
档位会怎么变"。生产侧的 `AqsScorer.kt` 一个字节都不动。

自证资格（每次运行开头都跑）：先用**现行**权重表重算 73 run 的总分，与语料里已落库的
`run.aqs.score`/`run.aqs_token.score` 逐 run 比对——只有当最大绝对差落在浮点序差量级
（<1e-9）时，后面的 what-if 数字才有资格被采信。复现不了现状就不许模拟改动。

三个决策的口径（承 D-493，各案编号与决策单 docs/T59_* 一一对应）：
  ①T3 权重再分配   A0 基线 / A1 T3 减半 / A2 T3 降至保险位
  ②短板惩罚函数     B0 基线 / B1 min 拉动 / B2 阈值扣分 / B3 软封顶
  ③置信门槛         C0 基线(门槛3) / C1 门槛→2 / C2 门槛→1

档位阈值取 `campaign_common.AQS_GRADE_BANDS`（单一来源，不在本文件复制常量）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign_common as cc  # noqa: E402

# 现行权重表：逐字取自 AqsScorer.kt:77-85 / :99-108。若那边改了，自证环节会当场失败。
WEIGHTS_MAIN = {"T1": 0.20, "T3": 0.20, "T2": 0.15, "U1": 0.15,
                "U2": 0.10, "N1": 0.10, "N2": 0.10}
WEIGHTS_TOKEN = {"T1": 0.18, "T3": 0.15, "T2": 0.12, "U1": 0.15,
                 "D1": 0.15, "U2": 0.05, "N1": 0.10, "N2": 0.10}

# 场景内样本量门槛：逐字取自 KpiCalculator.kt:328-335
THRESHOLDS = {"T1": 3, "U1": 3, "N1": 10, "N2": 10, "U2": 8, "D1": 3}

DEFAULT_CORPUS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "evidence", "t46_full_corpus_analysis_20260804", "full_corpus_labelled.jsonl")


def load_runs(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def weighted(subs, weights):
    """加权和。缺任一加权项就返回 None——不用 0 填补（那会把"缺席"印成"很差"）。"""
    if any(k not in subs or subs[k] is None for k in weights):
        return None
    return sum(w * subs[k] for k, w in weights.items())


def redistribute(weights, key, new_w):
    """把 key 的权重改成 new_w，释放/占用的量按其余项**现有比例**分摊，Σ 仍为 1。"""
    if key not in weights:
        raise KeyError(key)
    freed = weights[key] - new_w
    rest = {k: v for k, v in weights.items() if k != key}
    rest_sum = sum(rest.values())
    out = {k: v + freed * (v / rest_sum) for k, v in rest.items()}
    out[key] = new_w
    total = sum(out.values())
    if abs(total - 1.0) > 1e-12:
        raise AssertionError("权重和 %r != 1.0" % total)
    return out


def verify_baseline(runs):
    """现行权重表能否逐 run 精确复现已落库分数——不通过则拒绝继续。"""
    worst = {"main": 0.0, "token": 0.0}
    for r in runs:
        for face, key, w in (("main", "aqs", WEIGHTS_MAIN),
                             ("token", "aqs_token", WEIGHTS_TOKEN)):
            stored = r["run"][key]["score"]
            calc = weighted(r["run"][key]["sub_scores"], w)
            if calc is None or stored is None:
                raise AssertionError("%s 子分缺项，无法自证" % face)
            worst[face] = max(worst[face], abs(calc - stored))
    return worst


def grades(scores):
    return Counter(cc.aqs_grade(s) if s is not None else "n/a" for s in scores)


def migration(before, after):
    """档位迁移矩阵：{(原档, 新档): 条数}。"""
    m = Counter()
    for b, a in zip(before, after):
        gb = cc.aqs_grade(b) if b is not None else "n/a"
        ga = cc.aqs_grade(a) if a is not None else "n/a"
        m[(gb, ga)] += 1
    return m


# ---------- 决策②：短板惩罚的四种函数形式 ----------
def penal_none(wa, subs):
    return wa


def penal_min_pull(wa, subs, lam=0.2):
    """(1-λ)·加权平均 + λ·最低子分。λ 越大越"被短板拖住"。"""
    return (1 - lam) * wa + lam * min(subs.values())


def penal_threshold(wa, subs, floor=70.0, deduct=5.0):
    """存在低于 floor 的子分就扣固定分——最粗但最好解释的一种。"""
    return wa - deduct if min(subs.values()) < floor else wa


def penal_soft_cap(wa, subs, delta=20.0):
    """总分不得高于"最低子分 + Δ"——让短板给总分设天花板。"""
    return min(wa, min(subs.values()) + delta)


PENALTIES = {
    "B0_基线": penal_none,
    "B1_min拉动λ0.2": penal_min_pull,
    "B2_阈值扣分(<70扣5)": penal_threshold,
    "B3_软封顶(min+20)": penal_soft_cap,
}


def run_decision1(runs, face):
    key, base_w = ("aqs", WEIGHTS_MAIN) if face == "main" else ("aqs_token", WEIGHTS_TOKEN)
    t3 = base_w["T3"]
    cases = {
        "A0_基线": base_w,
        "A1_T3减半(%.3f->%.3f)" % (t3, t3 / 2): redistribute(base_w, "T3", t3 / 2),
        "A2_T3降至保险位(%.3f->0.05)" % t3: redistribute(base_w, "T3", 0.05),
    }
    baseline = [r["run"][key]["score"] for r in runs]
    out = []
    for name, w in cases.items():
        scores = [weighted(r["run"][key]["sub_scores"], w) for r in runs]
        out.append((name, w, scores, migration(baseline, scores)))
    return out


def run_decision2(runs, face):
    key, w = ("aqs", WEIGHTS_MAIN) if face == "main" else ("aqs_token", WEIGHTS_TOKEN)
    baseline = [r["run"][key]["score"] for r in runs]
    out = []
    for name, fn in PENALTIES.items():
        scores = []
        for r in runs:
            subs = r["run"][key]["sub_scores"]
            wa = weighted(subs, w)
            scores.append(fn(wa, {k: subs[k] for k in w}) if wa is not None else None)
        out.append((name, scores, migration(baseline, scores)))
    return out


def run_decision3(runs):
    """置信门槛：不同门槛下 run 级 low_confidence 会不会翻转。

    生产判据是两条析取（AqsScorer.kt:633-634）：
      lowConf = (composite.validity == VALID_LOW_CONFIDENCE) or 任一 AQS 输入 lowConfidence
    而 composite.validity 由 AqsInputMapper.kt:76-77 定——**三个 profile 任一场景低置信
    即低置信**，场景级 validity 又由该场景内**任一** KPI 低置信驱动。所以只放宽 AQS
    直接消费的那两项是不够的，这正是本表要量化的东西。
    """
    rows = []
    for thr in (3, 2, 1):
        scen_low_runs = 0
        aqs_low_runs = 0
        for r in runs:
            scen_low = False
            aqs_low = False
            for s in r["scenarios"]:
                q = s.get("kpi_quality")
                if not q:
                    continue
                for kpi, meta in q.items():
                    limit = THRESHOLDS.get(kpi)
                    if limit is None:
                        continue
                    eff = thr if limit == 3 else limit  # 只调 3 那一档（T1/U1/D1）
                    n = meta["sample_count"]
                    if 0 < n < eff:
                        scen_low = True
                        # AQS 定向取值：T1<-s2、U1<-s3（AqsInputMapper.kt:40-72）
                        if (kpi == "T1" and s["profile_id"] == "s2_coding_agent") or \
                           (kpi == "U1" and s["profile_id"] == "s3_multimodal"):
                            aqs_low = True
            scen_low_runs += 1 if scen_low else 0
            aqs_low_runs += 1 if aqs_low else 0
        rows.append((thr, scen_low_runs, aqs_low_runs))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="评分体系三决策 what-if 模拟器（不改生产代码）")
    ap.add_argument("corpus", nargs="?", default=DEFAULT_CORPUS, help="全语料 jsonl")
    ap.add_argument("--face", choices=("main", "token", "both"), default="both")
    ap.add_argument("--verify-only", action="store_true", help="只跑自证不做模拟")
    args = ap.parse_args(argv)

    runs = load_runs(args.corpus)
    worst = verify_baseline(runs)
    print("[自证] n=%d run；现行权重表重算 vs 已落库分数：" % len(runs))
    for face, d in worst.items():
        print("  %-5s max|delta| = %.3e  %s" % (face, d, "OK" if d < 1e-9 else "**不通过**"))
    if max(worst.values()) >= 1e-9:
        print("自证未通过——拒绝输出 what-if 数字（复现不了现状就没资格模拟改动）")
        return 1
    if args.verify_only:
        return 0

    faces = ("main", "token") if args.face == "both" else (args.face,)
    for face in faces:
        key = "aqs" if face == "main" else "aqs_token"
        base = [r["run"][key]["score"] for r in runs]
        print("\n" + "=" * 68)
        print("赛道：%s（基线档位 %s）" % (face, dict(grades(base))))
        print("=" * 68)

        print("\n【决策① T3 权重再分配】")
        for name, w, scores, mig in run_decision1(runs, face):
            ok = sorted(s for s in scores if s is not None)
            moved = {"%s->%s" % (a, b): n for (a, b), n in mig.items() if a != b}
            print("  %s: T3权重=%.4f  分数 %.3f~%.3f 中位 %.3f  档位 %s"
                  % (name, w["T3"], ok[0], ok[-1], ok[len(ok) // 2], dict(grades(scores))))
            print("      迁移：%s" % (moved or "无"))

        print("\n【决策② 短板惩罚函数】")
        for name, scores, mig in run_decision2(runs, face):
            ok = sorted(s for s in scores if s is not None)
            moved = {"%s->%s" % (a, b): n for (a, b), n in mig.items() if a != b}
            print("  %s: 分数 %.3f~%.3f 中位 %.3f  档位 %s"
                  % (name, ok[0], ok[-1], ok[len(ok) // 2], dict(grades(scores))))
            print("      迁移：%s" % (moved or "无"))

    print("\n" + "=" * 68)
    print("【决策③ 置信门槛】（与赛道无关，走场景级样本量）")
    print("=" * 68)
    n = len(runs)
    measured_low = sum(1 for r in runs if r["run"]["aqs"].get("low_confidence"))
    annotated = sum(1 for r in runs if any(s.get("kpi_quality") for s in r["scenarios"]))
    print("  【分母先说清楚】语料里 run.aqs.low_confidence 的**实测**值 = %d/%d；"
          % (measured_low, n))
    print("  而本表只能覆盖带 kpi_quality 的 %d 个 run（另 %d 个该字段缺失，D-493 §4）。"
          % (annotated, n - annotated))
    print('  所以下表的 %d 不是「只有这些低置信」，是「这些是本表算得出来的」——'
          % annotated)
    print("  缺字段的那 %d 个 run 按相位数规则同样会低置信（推断，非本表实测）。\n"
          % (n - annotated))
    print("  门槛 | 有场景低置信的run | AQS直接输入低置信的run | run级lowConf")
    for thr, scen_low, aqs_low in run_decision3(runs):
        tag = "  <- 现状" if thr == 3 else ""
        print("   %d   |      %2d/%d        |       %2d/%d           |   %2d/%d%s"
              % (thr, scen_low, n, aqs_low, n, max(scen_low, aqs_low), n, tag))
    print("\n  注1：run 级 lowConf 是两条析取取或（AqsScorer.kt:633-634），故取两列较大者。")
    print("  注2：门槛→2 时 AQS 直接输入全部脱离低置信，但 run 级**纹丝不动**——")
    print("       因为 composite.validity 那条通路仍恒真（s1_chat 的 T1/U1 恒为 1 < 2）。")
    print('       这是本表最该被读到的一行：只放宽门槛到 2 是「看着解决了、实际没解决」。')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
