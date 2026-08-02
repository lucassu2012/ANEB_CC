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


TESTS = _load(["test_e234_common", "test_e234_collect", "test_e2_analyze",
               "test_e3_analyze", "test_e4_analyze", "test_e1_analyze",
               "test_e1_collect_guard"])


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


def main():
    base = run_all()
    print("基线：%d 条测试，失败 %d 条" % (len(TESTS), len(base)))
    if base:
        for n in sorted(base):
            print("  基线失败：%s" % n)
        print("基线不绿，突变审计的红与绿都不是你以为的那个意思（D-394）。")
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
    print("")
    for name, predicted, verdict, failed in rows:
        mark = "" if verdict == predicted else "  ⚠ 预测=%s" % predicted
        sole = "（**单点守卫**）" if len(failed) == 1 else ""
        print("%-46s %-9s %d 条承重%s%s" % (name, verdict, len(failed), sole, mark))
        for f in failed:
            print("      %s" % f)
    after = run_all()
    print("\n还原后复跑：失败 %d 条（应为 0）" % len(after))
    return 0 if not after else 1


if __name__ == "__main__":
    raise SystemExit(main())
