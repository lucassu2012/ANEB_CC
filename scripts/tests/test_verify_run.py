# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/verify_run.py (T44①).

This wrapper reuses validate_results/radio_rollup's own judgment functions —
these tests pin the ORCHESTRATION (how the three checks combine into one
verdict line), not the underlying judgment logic itself (that is
test_validate_results.py's / test_radio_rollup.py's job).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import synth
import verify_run as vrun


def _ns(egress="198.51.100.9:443", radio=None):
    ns = {"transport": "cellular", "capabilities": "INTERNET",
         "interface": "rmnet0", "server_observed_addr": egress}
    if radio is not None:
        ns["radio"] = radio
    return ns


def _radio(stale=False):
    return {"rat": "NR", "rsrp_dbm": -90, "sinr_db": 10, "pci": 1,
           "tac": 1, "arfcn": 1, "sampled_n": 10, "stale": stale}


def _healthy_record(n_scenarios=3, egress="198.51.100.9:443"):
    """Contract-clean record, N scenarios, uniform egress, zero stale radio —
    the shape a genuinely good run has."""
    rec = synth.make_record(
        scenarios=[("s1_chat", {}) for _ in range(n_scenarios)])
    synth.contractify(rec)
    for scn in rec["scenarios"]:
        scn["network_snapshot"] = _ns(egress=egress, radio=_radio(stale=False))
    return rec


def test_pass_when_all_three_checks_clear():
    ok, line = vrun.verify_run([_healthy_record(n_scenarios=3)])
    assert ok is True
    assert line.startswith("PASS")
    assert "radio 3/3" in line


def test_coverage_line_reports_actual_count_not_a_hardcoded_nine():
    """"9/9" in the task framing is a common shape, not a hardcoded threshold —
    a 5-scenario run must report 5/5, never silently compare against a fixed
    total of 9 (the egress IP fixture happens to contain a literal "9", so
    the assertion targets the coverage phrase specifically, not any digit)."""
    ok, line = vrun.verify_run([_healthy_record(n_scenarios=5)])
    assert ok is True
    assert "radio 5/5" in line
    assert "radio 9/9" not in line
    assert "9/9" not in line


def test_fail_on_contract_violation():
    rec = _healthy_record(n_scenarios=2)
    del rec["run"]["status"]          # drop a required field -> schema violation
    ok, line = vrun.verify_run([rec])
    assert ok is False
    assert line.startswith("FAIL: 契约门")


def test_fail_on_partial_radio_coverage_reports_exact_gap():
    rec = _healthy_record(n_scenarios=4)
    rec["scenarios"][0]["network_snapshot"]["radio"]["stale"] = True
    rec["scenarios"][1]["network_snapshot"].pop("radio")
    ok, line = vrun.verify_run([rec])
    assert ok is False
    assert "radio 覆盖 2/4" in line
    assert "缺 2" in line


def test_fail_on_missing_egress():
    rec = _healthy_record(n_scenarios=2)
    rec["scenarios"][0]["network_snapshot"].pop("server_observed_addr")
    ok, line = vrun.verify_run([rec])
    assert ok is False
    assert "出口读出" in line and "缺" in line


def test_fail_on_mixed_egress_same_shape_as_publish_check():
    """Two different egress IPs inside one verify pass -> same MIXED_EGRESS
    judgment publish_check.py uses (len(egress_ips) > 1), not a new threshold."""
    rec1 = _healthy_record(n_scenarios=2, egress="198.51.100.9:443")
    rec2 = _healthy_record(n_scenarios=2, egress="203.0.113.4:8443")
    ok, line = vrun.verify_run([rec1, rec2])
    assert ok is False
    assert "MIXED_EGRESS" in line
    assert "198.51.100.9" in line and "203.0.113.4" in line


def test_fail_on_empty_input_not_a_silent_pass():
    ok, line = vrun.verify_run([])
    assert ok is False
    assert line.startswith("FAIL")


def test_pass_line_names_the_run_ids():
    rec = _healthy_record(n_scenarios=1)
    rid = rec["run"]["run_id"]
    ok, line = vrun.verify_run([rec])
    assert ok is True
    assert rid in line


def test_fail_on_loader_conflicts_not_a_silent_pass():
    """同一 run_id 两个不同 body 必须让判词变 FAIL（T71，承 T67/D-514 high#6）。

    verify_run 是**外场批式采集的自动化决策点**（T42/D-460：每 RUN_END 后拉库→抽单条→
    verify_run 判词，不过即停），它按退出码决定要不要继续采。此前它调 cc.load_records
    却**不传 stats**，于是 loader 自己命名为 data-integrity fault 的 conflicts
    对它构造性不可见——一批含冲突 run_id 的语料会被判 PASS 放行继续采集。
    同一形状 D-325 在 publish_check、D-330 在 campaign_report 各修过一次，这是第三个消费方。
    """
    rec = _healthy_record(n_scenarios=1)
    ok, line = vrun.verify_run([rec], stats={"conflicts": ["dup-run-id"], "unreadable_files": 0})
    assert ok is False
    assert line.startswith("FAIL")
    assert "完整性" in line


def test_fail_on_unreadable_files_absence_is_not_zero():
    """读不进来的文件必须发声（缺席不是零，R-10 家族）。

    整个文件读不进来时若沉默，「少了一批数据」长得和「这批数据没问题」一模一样。
    """
    rec = _healthy_record(n_scenarios=1)
    ok, line = vrun.verify_run([rec], stats={"conflicts": [], "unreadable_files": 2})
    assert ok is False
    assert line.startswith("FAIL")


def test_healthy_stats_still_pass_the_new_check_is_not_always_on():
    """反例方向：stats 干净时新检查不得误伤（否则它退化为恒 FAIL）。"""
    rec = _healthy_record(n_scenarios=1)
    ok, line = vrun.verify_run([rec], stats={"conflicts": [], "unreadable_files": 0,
                                             "duplicates": 0, "kept": 1, "lines": 1})
    assert ok is True
    assert line.startswith("PASS")


def test_stats_omitted_keeps_backward_compatibility():
    """不传 stats 的既有调用方不受影响（向后兼容）。"""
    rec = _healthy_record(n_scenarios=1)
    ok, line = vrun.verify_run([rec])
    assert ok is True
