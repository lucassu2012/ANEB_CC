#!/usr/bin/env python3
"""per-run 落地即验：一个刚落库的 run，三查合一，单行判词（纯 stdlib）。

出处：大脑 T44 派单——外场/夜间采集时，PO 或 v2 采完一个 run 就要立刻知道
"这条能不能算数"，不能等回程再跑完整的 campaign 报告链才发现要重采。

三查全部**复用既有工具的判据函数，不重写**（D-315"同名实现"教训——两套
"radio 覆盖"或"出口一致"的判法一旦分叉，谁都不知道哪个是权威）：

1. **契约门** = `validate_results.load_schema()` + `.validate_records()`
   （schema 校验+跨字段不变量，逐字复用，本文件不碰 schema 一行）。
2. **radio 覆盖** = `radio_rollup.radio_of()` 逐场景取 `network_snapshot.radio`，
   `stale is True` 判定也是 `radio_rollup._samples()` 那一条，本文件只按同样
   的判据逐场景计数——覆盖率写成 `covered/total`，不是抽象的"9/9"，run 里
   到底有几个场景，数出来，不写死 9。
3. **出口读出** = `radio_rollup.egress_ip()` 逐场景取
   `network_snapshot.server_observed_addr`（剥端口），非空计数+批内去重后
   看唯一值个数——`>1` 即 `publish_check.py` 的 `MIXED_EGRESS` 同一判据
   （`len(egress_ips) > 1`），本文件不重新发明"什么叫出口不一致"。

本文件唯一新增的判断是**把三查的结果合成一行**：三查全过 -> `PASS`；
任一查不过 -> `FAIL: <具体哪一查、差多少>`，不含糊地说"有问题"。

用法：
    python scripts/verify_run.py <run.jsonl 或 glob>
    # 退出码 0=PASS，1=FAIL（契约门/radio覆盖/出口不过之一），2=读不了输入
"""
import argparse
import sys

import campaign_common as cc
import radio_rollup as rr
import validate_results as vr


def verify_run(records, stats=None):
    """(ok: bool, line: str)。三查全过 line 以 "PASS" 开头，否则以 "FAIL" 开头。

    只做编排：每一步的判据都来自被复用的函数，这里不重新判断"什么算合格"。
    """
    if not records:
        return False, "FAIL: 无可读记录（输入为空或全部行解析失败/不合法 JSON）"

    # (0) loader 完整性 —— 在判"数据合不合格"之前，先确认"读进来的这批本身可不可信"。
    # cc.load_records 的 stats 里，conflicts 是它自己命名的 data-integrity fault：
    # 同一 run_id 出现两个**不同的** body。那不是良性重导出，两份不可平均，也不该
    # 被当成一次成功采集放行。unreadable_files 同理——整个文件读不进来时，
    # 沉默会让"少了一批数据"长得和"这批数据没问题"一模一样。
    # 调用方不传 stats 时本段跳过（向后兼容），但 main() 一定会传。
    if stats:
        # 实测 loader 回填的键集与类型（不凭记忆写，D-325：键名/类型猜错会被伪装成"值为 0"）：
        #   conflicts=list（冲突 run_id 列表）、unreadable_files=int、
        #   另有 duplicates/kept/lines/malformed/no_run_id 均为 int。
        conflicts = len(stats.get("conflicts") or [])
        unreadable = int(stats.get("unreadable_files") or 0)
        if conflicts:
            return False, ("FAIL: 语料完整性——%d 个 run_id 出现了两个不同的 body"
                           "（loader 判 data-integrity fault，两份不可平均）" % conflicts)
        if unreadable:
            return False, ("FAIL: 语料完整性——%d 个文件读不进来"
                           "（缺席不是零：少了一批数据不能当成没问题）" % unreadable)

    # ① 契约门 —— 复用 validate_results，不重写 schema 判据。
    try:
        sch = vr.load_schema(vr.DEFAULT_SCHEMA)
    except (OSError, ValueError) as e:
        return False, "FAIL: 契约门——schema 读取失败（%s: %s）" % (e.__class__.__name__, e)
    errors, _warnings = vr.validate_records(records, sch)
    if errors:
        return False, "FAIL: 契约门 %d 处违约（首条：%s）" % (len(errors), errors[0])

    # ② radio 覆盖 —— 复用 radio_rollup.radio_of 的 stale 判据，逐场景计数。
    total, covered = 0, 0
    for rec in records:
        for scn in cc.iter_scenarios(rec):
            total += 1
            r = rr.radio_of(scn)
            if r is not None and r.get("stale") is not True:
                covered += 1
    if total == 0:
        return False, "FAIL: radio 覆盖——run 内零场景，契约门却放行了（异常形状）"
    if covered < total:
        return False, ("FAIL: radio 覆盖 %d/%d（缺 %d 个场景无 radio 或 stale）"
                       % (covered, total, total - covered))

    # ③ 出口读出 —— 复用 radio_rollup.egress_ip；一致性判据同 publish_check
    # 的 MIXED_EGRESS（len(egress_ips) > 1），不重新定义"不一致"是什么。
    egress_ips, missing_egress = set(), 0
    for rec in records:
        for scn in cc.iter_scenarios(rec):
            ip = rr.egress_ip(scn)
            if ip:
                egress_ips.add(ip)
            else:
                missing_egress += 1
    if missing_egress:
        return False, ("FAIL: 出口读出——%d/%d 个场景缺 server_observed_addr"
                       % (missing_egress, total))
    if len(egress_ips) > 1:
        return False, ("FAIL: 出口读出——批内 %d 个不同出口（MIXED_EGRESS：%s）"
                       % (len(egress_ips), ", ".join(sorted(egress_ips))))

    run_ids = sorted({cc.run_obj(r).get("run_id") or "?" for r in records})
    ids_shown = ",".join(run_ids[:3]) + ("…" if len(run_ids) > 3 else "")
    egress_shown = next(iter(egress_ips)) if egress_ips else "—"
    return True, ("PASS: %d run / %d 场景，radio %d/%d，出口 %s（%s）"
                 % (len(records), total, covered, total, egress_shown, ids_shown))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="per-run 落地即验：契约门+radio覆盖+出口读出，单行判词")
    ap.add_argument("inputs", nargs="+", help="刚落库的 run JSONL 文件/glob")
    args = ap.parse_args(argv)

    cc.force_utf8_stdout()
    stats = {}
    records, files = cc.load_records(args.inputs, stats=stats)
    if not files:
        sys.stderr.write("找不到匹配的输入文件：%s\n" % ", ".join(args.inputs))
        return 2

    ok, line = verify_run(records, stats)
    print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
