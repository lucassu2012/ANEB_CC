#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2/E3/E4 守卫的突变审计 —— **运行时突变，不落盘**。

为什么不做文件级突变：本工作树是共享的，同刻另有会话在改别的文件；把源码改成
突变态再还原，一旦中途被杀就会把一份突变源留在盘上（D-321 实录）。运行时包装
只活在内存里，进程一结束什么都不剩。代价是「共享实现使某些面隔离不开」，
那种情况在下面逐条注明（D-322）。

纪律（D-321/D-394）：
- 记的是**失败测试的集合**，不只是 CAUGHT/SURVIVED —— 恰好一条才叫单点守卫；
- 非单点的也如实写清，**标错比不标更误导**；
- 先预测再验：预测与实测不一致时，写下来的是实测（D-325）。
"""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "e1", "tests"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "e1"))

import e234_common as ec        # noqa: E402
import e234_session as es       # noqa: E402
import e1_analyze as ea         # noqa: E402
import sim_session as sim       # noqa: E402


def _load(modnames):
    import importlib
    out = []
    for m in modnames:
        mod = importlib.import_module(m)
        for name in sorted(dir(mod)):
            fn = getattr(mod, name)
            if name.startswith("test_") and callable(fn):
                out.append(("%s::%s" % (m, name), fn))
    return out


# ⚠ **这是一张手写清单**，而 `run_tests.py` 那边是**从磁盘枚举**的 —— 两者会分叉：
# 新增一个 `test_*.py` 会自动进反例跑器，**却不会自动进突变审计**。
# 分叉时没有任何报错，症状只是「这份守卫从没被突变考过」，而它在反例跑器里照样报绿。
# 加测试文件时**必须同时加到这里**；`test_e2_precheck` 即 2026-08-30 新增的一条。
TESTS = _load(["test_e234_common", "test_e234_collect", "test_e2_analyze",
               "test_e2_precheck", "test_e3_analyze", "test_e4_analyze",
               "test_e1_analyze", "test_e1_collect_guard"])


def _say(text):
    """经 `ec.say` 输出 —— **报告通道自己不许死在报告上**（D-265）。

    实测：本文件原用裸 `print`，把输出重定向到文件时 stdout 编码退回 GBK，
    而 M11 的名字里有 `↔`（U+2194，GBK 里没有）⇒ **整个审计在打印第 11 行时崩掉**，
    前 10 条结果已印、后 8 条与「还原后复跑」永远没印出来，退出码 1。
    **看起来像审计失败，其实审计早就跑完了。** 交互式跑时不复现（那次我带了
    `PYTHONIOENCODING=utf-8`）——**同一份代码在两种跑法下结论不同**，
    而门禁用的是不带环境变量的那种。
    """
    ec.say(text + "\n")


def run_all():
    failed = set()
    for name, fn in TESTS:
        try:
            fn()
        except Exception:
            failed.add(name)
    return failed


# ── 突变清单：(名字, 预测, 施加, 还原) ─────────────────────────────────────
def _mut(target, attr, new):
    old = getattr(target, attr)
    setattr(target, attr, new)
    return lambda: setattr(target, attr, old)


MUTATIONS = []


def mutation(name, predicted):
    def deco(fn):
        MUTATIONS.append((name, predicted, fn))
        return fn
    return deco


@mutation("M1 门改回单边（判有符号的 Δ 而非 |Δ|）", "CAUGHT")
def m1():
    import e2_analyze as e2
    real = e2.analyze

    def patched(run_dir, pkg):
        res = real(run_dir, pkg)
        if res.get("signed", {}).get("status") == ec.PASS:
            res["channel_a_vs_c"] = res["signed"]
            res["verdict"] = ea.gate_verdict(res["signed"], res["frame_ms"])
        return res
    return _mut(e2, "analyze", patched)


@mutation("M2 隔离断言恒放行（写盘前不再拦）", "CAUGHT")
def m2():
    return _mut(ec, "assert_isolation_before_write", lambda out_dir, kind: True)


@mutation("M3 时戳量纲守卫恒真（截断的时戳照收）", "CAUGHT")
def m3():
    return _mut(ec, "plausible_boot_ns", lambda v: isinstance(v, int))


@mutation("M4 时钟钉桩不再查漂移", "CAUGHT")
def m4():
    real = ec.clock_pin

    def patched(pre, post, frame_ms):
        r = real(pre, post, frame_ms)
        if r.get("status") != ec.PASS and "漂移" in (r.get("reason") or ""):
            r = dict(r, status=ec.PASS,
                     offset_ns=r.get("drift_ns", 0), reason=None)
        return r
    return _mut(ec, "clock_pin", patched)


@mutation("M5 通道 A 不按 pkg 过滤", "CAUGHT")
def m5():
    real = es.content_events

    def patched(lines, pkg):
        evts = ea.parse_adapter_events(lines or [])
        same = [e for e in evts if e.get("type") == "content"]
        kept, bad = ec.reject_implausible(same, "t_boot_ns")
        return kept, len(evts) - len(same), bad
    return _mut(es, "content_events", patched)


@mutation("M6 nearest_after 允许一帧被配两次", "CAUGHT")
def m6():
    def patched(t0, candidates, key, max_gap_ns, used=None):
        cand = next((c for c in candidates if c[key] >= t0), None)
        if cand is None:
            return None, "none"
        if (cand[key] - t0) > max_gap_ns:
            return None, "gap"
        return cand, None
    return _mut(ec, "nearest_after", patched)


@mutation("M7 簇分割门限退回硬编码字面量", "CAUGHT")
def m7():
    return _mut(ec, "cluster_gap_nanos", lambda kt_path=None: 400_000_000)


@mutation("M8 framestats 不再剥尾部空字段", "CAUGHT")
def m8():
    return _mut(ea, "_drop_trailing_blank", lambda fields: [f.strip() for f in fields])


@mutation("M9 标定前门恒放行（dry-run 也能产 T_quiet）", "CAUGHT")
def m9():
    return _mut(ec, "refuse_calibration_from_dry_run", lambda kind: (True, None))


@mutation("M10 未出数的轮次不再计数（静默改分母）", "CAUGHT")
def m10():
    import e2_analyze as e2
    real = e2.analyze

    def patched(run_dir, pkg):
        res = real(run_dir, pkg)
        res["drop_reasons"] = {}
        return res
    return _mut(e2, "analyze", patched)


@mutation("M11 墙钟↔BOOTTIME 不再查单调性", "CAUGHT")
def m11():
    real = ec.fit_wall_to_boot

    def patched(lines):
        r = real(lines)
        if r.get("status") != ec.PASS and "单调" in (r.get("reason") or ""):
            return {"status": ec.PASS, "offset_ns": 0, "n": r.get("n", 0),
                    "residual_ms_p50": 0.0, "residual_ms_max": 0.0}
        return r
    return _mut(ec, "fit_wall_to_boot", patched)


@mutation("M12 E4 分离判据只看中位数不看极值", "CAUGHT")
def m12():
    import e4_analyze as e4
    real = e4.separation

    def patched(intra, post):
        r = real(intra, post)
        if r.get("verdict") == e4.OVERLAP:
            mi = sorted(intra)[len(intra) // 2] if intra else None
            mp = sorted(post)[len(post) // 2] if post else None
            if mi is not None and mp is not None and mi < mp:
                r = dict(r, verdict=e4.SEPARABLE, gap_lo_ms=mi, gap_hi_ms=mp)
        return r
    return _mut(e4, "separation", patched)


# ── e2_precheck（2026-08-30 新增）─────────────────────────────────────────
# 这五条对着的是同一件事的五个侧面：**「记录里的一个洞」与「App 的一次静默」
# 在去重后的帧序列里长得一模一样**。每一条都把「把后者读成前者」的一种走法堵上。

@mutation("M13 disjoint 不再断段（丢帧的洞被并进连续段）", "CAUGHT")
def m13():
    import e2_precheck as ep
    real = ep.classify_pairs

    def patched(dumps):
        counts, _runs = real(dumps)
        # 坏实现：不管断没断，全场当成一整段连续观测 ⇒ 洞被读成静默。
        frames = sorted(set(t for d in dumps for t in d))
        return counts, ([(frames[0], frames[-1])] if frames else [])
    return _mut(ep, "classify_pairs", patched)


# ── 一条**等价突变**的记录（D-325：预测与实测不一致时，写下来的是实测）──────
#
# 初版 M13 是「把 `identical` 也当断点」，预测 CAUGHT，**实测 SURVIVED**。
# 追下去发现它是**等价突变**，不是守卫漏了：`classify_pairs` 里 `identical` 与
# `overlap` 走的是**同一个分支**（都只延长 `hi`），只有 `disjoint` 断段；而一对
# identical 的两次 dump **跨度完全相同**，所以「在这里断一刀」不改变任何区间的覆盖性。
#
# ⇒ **`identical` 这一支是诊断计数，不是承重逻辑**（承重的是 `disjoint`）。
# 这条留在这里，是因为它纠正了一个我差点写进文档的错误印象：
# **「我为某个判断写了一条分支」不等于「那个判断在承重」** —— 分支存在感很强，
# 而它是否改变输出，只有突变审计答得出。改 M13 去打真正承重的那一支后即 CAUGHT。


@mutation("M14 丢帧边界不再拦（跨洞间隔算成静默）", "CAUGHT")
def m14():
    import e2_precheck as ep

    def patched(dumps, runs, gap_ns):
        frames = sorted(set(t for d in dumps for t in d))
        ver = [(frames[i] - frames[i - 1]) / ec.NS_PER_MS
               for i in range(1, len(frames))
               if frames[i] - frames[i - 1] > gap_ns]
        return {"frames_deduped": len(frames), "observed_gaps": ver,
                "unjudgeable_gaps": []}
    return _mut(ep, "gap_census", patched)


@mutation("M15 NOT_APPLICABLE 与 CANNOT_TELL 合并（「没看见」写成「不静默」）", "CAUGHT")
def m15():
    import e2_precheck as ep

    # ⚠ 签名必须跟着 `_verdict` 走（现为 5 参，含 A 侧）：桩子签名对不上时，
    # 每个用到它的测试都会 TypeError ⇒ 报 CAUGHT，**但那是崩的不是被抓的**。
    # **一个因签名不符而崩出来的 CAUGHT，与真的被守卫咬住长得一模一样。**
    def patched(counts, ver, unj, b, a=None):
        if not ver:
            return (ep.NOT_APPLICABLE, "无静默")
        return (ep.WORTH_RUNNING, "有静默")
    return _mut(ep, "_verdict", patched)


@mutation("M16 通道 B 的反驳被摘掉（两通道矛盾照给绿）", "CAUGHT")
def m16():
    import e2_precheck as ep
    real = ep.channel_b_motion

    def patched(samples, threshold=ep.B_FLIP_THRESHOLD):
        r = real(samples, threshold)
        if r.get("status") == ec.PASS:
            r = dict(r, motion_rate=0.0)      # 永远不反驳
        return r
    return _mut(ep, "channel_b_motion", patched)


@mutation("M17 可核静默下界脱离 GATE_MIN_N（自取一个更松的数）", "CAUGHT")
def m17():
    import e2_precheck as ep
    return _mut(ep, "MIN_OBSERVED_GAPS", 1)


@mutation("M18 A 侧不足不再拦（只查 C 侧就给绿）", "CAUGHT")
def m18():
    import e2_precheck as ep
    real = ep.channel_a_anchors

    def patched(run_dir, pkg, gap_ns):
        r = real(run_dir, pkg, gap_ns)
        # 坏实现：A 侧永远报「够」⇒ 判据只验了一半却给绿。
        return dict(r, status=ec.PASS, turns=99, turns_with_anchor=99)
    return _mut(ep, "channel_a_anchors", patched)


# ── T90：通道 C 图层失效自愈（D-644）────────────────────────────────────

@mutation("M19 失效判据退回「响应是否为空」（死图层的有头无帧被当成有帧）", "CAUGHT")
def m19():
    import e234_collect as e2c
    # 坏实现：只看响应空不空。而死图层返回的**不是空**——它有刷新周期头。
    return _mut(e2c, "_sf_frame_rows", lambda text: 1 if (text or "").strip() else 0)


@mutation("M20 重挑判据不看「这个图层出过帧没有」（每格开头白重挑）", "CAUGHT")
def m20():
    import e234_collect as e2c
    real = e2c._should_relist
    return _mut(e2c, "_should_relist",
                lambda ever, streak, since: real(True, streak, since))


@mutation("M21 分母改成数所有非空行（孤立回车与帧行都被算进 dump 次数）", "CAUGHT")
def m21():
    import e2_precheck as ep
    def patched(text):
        return sum(1 for l in (text or "").splitlines() if l.strip())
    return _mut(ep, "count_issued_dumps", patched)


@mutation("M22 存活率门限放到 0（仪器失效不再拦，作废格重新表面全绿）", "CAUGHT")
def m22():
    import e2_precheck as ep
    return _mut(ep, "DUMP_SURVIVAL_FLOOR", 0.0)


@mutation("M23 「样本太少」与「图层死了」合并（两种病共用一个判词）", "CAUGHT")
def m23():
    import e2_precheck as ep
    return _mut(ep, "DUMP_SURVIVAL_MIN_N", 0)


@mutation("M24 逐段行数改用 split_dumps 的口径（滤掉待定帧后再数）", "CAUGHT")
def m24():
    import e2_precheck as ep
    # 坏实现：拿过滤后的帧数当原始行数 ⇒「环满但全待定」与「图层死了」合成一种病。
    return _mut(ep, "dump_row_counts",
                lambda text: [len(d) for d in ep.split_dumps(text)])


@mutation("M25 逐段行数丢掉空段（长度不再等于发出次数）", "CAUGHT")
def m25():
    import e2_precheck as ep
    real = ep.dump_row_counts
    return _mut(ep, "dump_row_counts", lambda text: [n for n in real(text) if n])


def main():
    base = run_all()
    _say("基线：%d 条测试，失败 %d 条" % (len(TESTS), len(base)))
    if base:
        for n in sorted(base):
            _say("  基线失败：%s" % n)
        _say("基线不绿，突变审计的红与绿都不是你以为的那个意思（D-394）。")
        return 1
    rows = []
    for name, predicted, apply_fn in MUTATIONS:
        undo = apply_fn()
        try:
            failed = run_all()
        finally:
            undo()
        verdict = "CAUGHT" if failed else "SURVIVED"
        rows.append((name, predicted, verdict, sorted(failed)))
    _say("")
    for name, predicted, verdict, failed in rows:
        mark = "" if verdict == predicted else "  ⚠ 预测=%s" % predicted
        sole = "（**单点守卫**）" if len(failed) == 1 else ""
        _say("%-46s %-9s %d 条承重%s%s" % (name, verdict, len(failed), sole, mark))
        for f in failed:
            _say("      %s" % f)
    after = run_all()
    _say("\n还原后复跑：失败 %d 条（应为 0）" % len(after))
    return 0 if not after else 1


if __name__ == "__main__":
    raise SystemExit(main())
