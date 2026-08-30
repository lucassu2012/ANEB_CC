# -*- coding: utf-8 -*-
"""
Reflex tests for the portrait red-line guard (D-65 spine-3).
Each invariant gets a RED fixture (must be caught) + the GREEN baselines
(valid portraits must pass). Fixtures are in-memory dicts — no real yaml,
no device, no PO dependency. Run:  python -m pytest spec/portraits/test_check_redline.py -q

Guards the guard: if a future refactor weakens an invariant, its RED test fails.
"""
from check_redline import (check_portrait, check_cross_file, gate_state, portrait_mode,
                           PARAM_FIELDS, RULED_STATUS, RULED_STATUS_BY_APP,
                           DIST_MIN_N, DIST_MIN_SESSIONS, DIST_MIN_NETWORKS)


# ── R20: observed_ui_layer.dist (INSTRUMENTATION_SPEC §4.5, brain ruling 6-7) ──────────
def _dist_metric(n=None, sessions=None, networks=None, p50=1980.0, p90=2100.0, p99=2300.0):
    return {"p50": p50, "p90": p90, "p99": p99,
            "n": DIST_MIN_N if n is None else n,
            "sessions": DIST_MIN_SESSIONS if sessions is None else sessions,
            "networks": ["wifi", "5g"] if networks is None else networks}


def _with_dist(dist):
    d = _valid_pending()
    d["observed_ui_layer"] = {"captured": True, "source": "aneb-a11y-observe-2026-08-15",
                              "caliber": "ui-proxy", "ttft_ui_ms": 1984}
    if dist is not None:
        d["observed_ui_layer"]["dist"] = dist
    return d


def _valid_dist():
    return {"ttft_ui_ms": _dist_metric(),
            "cadence_ui_ms": _dist_metric(p50=100.0, p90=110.0, p99=130.0),
            "method": {"ttft": "v3-cluster", "rct": "quiet-only"},
            "captured_at": "2026-08-15"}


def _r20(d):
    return [x for x in check_portrait("x", d) if "R20" in x]


def test_R20_absent_dist_is_not_a_violation():
    """整段缺席是诚实状态（样本没到阈值就别写），不是缺陷。"""
    assert _r20(_with_dist(None)) == []
    assert _r20(_valid_pending()) == []          # 连 observed_ui_layer 都没有的画像同样放行


def test_R20_complete_dist_passes():
    assert _r20(_with_dist(_valid_dist())) == []


def test_R20a_empty_dist_caught():
    """写一个空段 = 看着像有、其实什么都没有——正是本规则要禁的半填状态。"""
    assert any("R20a" in x for x in check_portrait("x", _with_dist({})))


def test_R20c_null_field_caught():
    """大脑点名的那一条：dist 段出现则字段不得为 null。"""
    dist = _valid_dist()
    dist["ttft_ui_ms"]["p99"] = None
    assert any("R20c" in x for x in check_portrait("x", _with_dist(dist)))


def test_R20c_missing_key_caught():
    dist = _valid_dist()
    del dist["ttft_ui_ms"]["sessions"]
    assert any("R20c" in x for x in check_portrait("x", _with_dist(dist)))


def test_R20b_missing_method_caught():
    """没有 method 标签的分布，与下一份分布无从比较（§1.6）。"""
    dist = _valid_dist()
    del dist["method"]
    assert any("R20b" in x for x in check_portrait("x", _with_dist(dist)))


def test_R20d_below_sample_ladder_caught():
    """n=3 不是分布，是几次读数。写下来它就会在下游被当成 p99 引用。"""
    for kw in ({"n": DIST_MIN_N - 1}, {"sessions": DIST_MIN_SESSIONS - 1},
               {"networks": ["wifi"] * (DIST_MIN_NETWORKS - 1)}):
        dist = _valid_dist()
        dist["ttft_ui_ms"] = _dist_metric(**kw)
        assert any("R20d" in x for x in check_portrait("x", _with_dist(dist))), kw


def test_R20e_unordered_percentiles_caught():
    """p50>p99 不是打错一个数，是三个数来自不同的池子。"""
    dist = _valid_dist()
    dist["ttft_ui_ms"] = _dist_metric(p50=9999.0)
    assert any("R20e" in x for x in check_portrait("x", _with_dist(dist)))


def test_R20_does_not_fire_on_network_layer_dist():
    """R20 只管 UI 层。网络层另有口径，别让一条规则越界去管它没见过的段。"""
    d = _valid_pending()
    d["observed_network_layer"]["dist"] = {"whatever": None}
    assert _r20(d) == []


def test_guard_self_description_covers_every_implemented_rule():
    """守卫自己那句「R1-Rxx」必须跟得上它实际实现的规则数。

    这不是洁癖：D-301 的形状正是「判据换了，而摘要还在报旧名字，且钉住旧名字的
    那条守卫让它看起来一直是对的」。本轮加 R20 时，`check_portrait` 的 docstring
    与实跑 OK 行都还自称 R1-R19——**多加一条规则不会让任何测试变红**，
    所以这里让它变红。规则号从源码里数出来，不手写清单（D-275）。
    """
    import os
    import re
    src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_redline.py")
    with open(src_path, "r", encoding="utf-8") as fh:
        src = fh.read()
    # 只数真正被 bad(...) 引用的规则号——注释里提到的编号不算实现。
    used = {int(m) for m in re.findall(r'"R(\d+)[a-z]?"', src)}
    assert used, "没数出任何规则号，说明这条守卫的量法坏了"
    top = max(used)
    assert f"R1-R{top}" in src, (
        f"实现到 R{top}，但源码里找不到自述串 R1-R{top}："
        f"docstring 或 OK 行仍停在旧范围")


def _capture_status(overrides=None):
    """Plan-B status block: everything PENDING except the two by-caliber rulings (D-348)."""
    st = {k: {"status": RULED_STATUS.get(k, "PENDING"), "reason": "fixture reason"}
          for k in PARAM_FIELDS}
    for k, s in (overrides or {}).items():
        st[k] = {"status": s, "reason": "fixture reason"}
    return st


def _valid_pending():
    """Minimal valid PENDING portrait (doubao-style: pop_ip direct+hostname awaiting DNS)."""
    fields = {k: {"value": "PENDING(no same-caliber source)", "caliber": "none", "keep_pending": True,
                  "source_layer": "none", "confidence": "INCONCLUSIVE", "note": "pending"}
              for k in PARAM_FIELDS}
    # pop_ip is the infra-fact field: caliber=direct (R16), value non-PENDING (R12), still pending DNS.
    # R18: direct => source_layer=network, confidence=LOW.
    fields["pop_ip_list"] = {"value": "host.example.com (SNI hostname, DNS pending)",
                             "caliber": "direct", "keep_pending": True,
                             "source_layer": "network", "confidence": "LOW", "note": "infra fact"}
    return {
        "schema_version": "1.0.0",
        "source_portrait": "PENDING-CAPTURE",
        "params": {k: None for k in PARAM_FIELDS},
        "params_capture_status": _capture_status(),
        "observed_network_layer": {"endpoints": ["host.example.com"]},
        "params_fit_approx": {"gates_params": False, "source_portrait_unlocked": False, "fields": fields},
    }


def _flipped():
    """A LEGITIMATE plan-B flip: every capturable field CAPTURED with a real value, the two
    by-caliber rulings left as-is, source_portrait naming a traceable capture.

    This fixture is the half of R19 that matters most: before D-348 a portrait in this state
    was judged FAIL by R1/R2, so the gate could never open honestly and any real capture would
    have been forced to weaken the guard instead."""
    d = _valid_pending()
    capturable = [k for k in PARAM_FIELDS if k not in RULED_STATUS]
    d["source_portrait"] = "x-app-capture-2026-08-15"
    d["params_capture_status"] = _capture_status({k: "CAPTURED" for k in capturable})
    for k in capturable:
        d["params"][k] = {"p50": 1, "p90": 2, "p99": 3, "n": 30}
    d["params_fit_approx"]["source_portrait_unlocked"] = True
    return d


def _valid_escaped_popip():
    """tongyi-style valid: pop_ip escaped PENDING with real IP + evidence backlink."""
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["pop_ip_list"] = {
        "value": "110.253.191.12, 114.250.44.6 (resolved POP IP)", "caliber": "direct", "keep_pending": False,
        "source_layer": "network", "confidence": "LOW", "note": "resolved IP"}
    d["observed_network_layer"] = {"endpoints": ["upaas.quark.cn 110.253.191.12", "114.250.44.6"]}
    return d


def _has(viol, rule):
    return any(rule in v for v in viol)


# ---- GREEN baselines ----

def test_valid_pending_passes():
    assert check_portrait("x", _valid_pending()) == []
    assert check_cross_file({"x": _valid_pending()}) == []


def test_valid_escaped_popip_passes():
    d = _valid_escaped_popip()
    assert check_portrait("x", d) == []
    assert check_cross_file({"x": d}) == []


def test_a_legitimate_plan_b_flip_passes():
    """The half of R19 that matters most: a HONEST flip must be allowed through.

    Before D-348 this exact state was judged FAIL by R1 (all-null) and R2 (sentinel only), so
    the gate could never open honestly — anyone with a real capture would have had to weaken
    the guard to record it, which is how honesty guards die.
    """
    d = _flipped()
    assert check_portrait("x", d) == []
    assert check_cross_file({"x": d}) == []
    assert portrait_mode(d) == "CAPTURED"
    ready, blockers = gate_state("x", d)
    assert ready and blockers == []


def test_by_caliber_fields_never_block_the_flip():
    """The plan-A defect this replaces: one permanently-unreachable field freezing the gate
    forever. token_interval/think_pause (red-line-outside) and tool_loop (never applicable)
    are excluded from the criterion — while plain PENDING still blocks."""
    ready, blockers = gate_state("x", _valid_pending())
    assert not ready
    assert set(blockers) == set(PARAM_FIELDS) - set(RULED_STATUS)
    assert not (set(blockers) & set(RULED_STATUS)), "a by-caliber ruling must never block"


# ---- RED per-invariant (check_portrait) ----

def test_R1_filled_param_caught():
    d = _valid_pending(); d["params"]["request_size_bytes_dist"] = "FAKE-42KB"
    assert _has(check_portrait("x", d), "R1")


def test_R19a_missing_status_block_caught():
    """No status block = no gate criterion, and "no criterion" reads as "nothing blocking".
    Absence must be a violation, never a skip."""
    d = _valid_pending(); del d["params_capture_status"]
    assert _has(check_portrait("x", d), "R19a")


def test_R19b_status_without_reason_caught():
    d = _valid_pending()
    d["params_capture_status"]["pop_ip_list"] = {"status": "PENDING", "reason": "  "}
    assert _has(check_portrait("x", d), "R19b")


def test_R19c_captured_without_value_caught():
    """Claiming a capture the portrait has not got — the direction R1 does not cover."""
    d = _valid_pending()
    d["params_capture_status"]["pop_ip_list"] = {"status": "CAPTURED", "reason": "claimed"}
    assert _has(check_portrait("x", d), "R19c")


def test_R19d_ruled_field_promoted_caught():
    """The 2026-07-31 rulings are frozen machine-side: promoting token_interval to an ordinary
    PENDING (or to CAPTURED) would quietly re-open a field this methodology cannot reach."""
    d = _valid_pending()
    d["params_capture_status"]["token_interval_ms_dist"] = {"status": "PENDING", "reason": "x"}
    assert _has(check_portrait("x", d), "R19d")


def test_a_single_field_may_unlock_on_its_own():
    """Plan B's whole point (「哪个字段采够样本就翻哪个」): one field reaching its threshold is
    filled and CAPTURED while every other stays null and blocking, with source_portrait still
    the sentinel. Under the old all-null R1 this legitimate state was a violation."""
    d = _valid_pending()
    d["params_capture_status"]["pop_ip_list"] = {"status": "CAPTURED", "reason": "dual-network POP set"}
    d["params"]["pop_ip_list"] = ["203.0.113.7", "198.51.100.9"]
    assert check_portrait("x", d) == []
    ready, blockers = gate_state("x", d)
    assert not ready and "pop_ip_list" not in blockers


def test_R2_free_form_source_portrait_caught():
    """R2 changed meaning at D-348 and this test changed with it, deliberately: it used to
    assert that ANY flip was caught, which is now wrong (an honest flip must be allowed,
    see test_a_legitimate_plan_b_flip_passes). What R2 still forbids is a source_portrait
    that is neither the sentinel nor a traceable capture id — an unauditable claim."""
    d = _valid_pending(); d["source_portrait"] = "captured (see chat log)"
    assert _has(check_portrait("x", d), "R2")


def test_R19e_half_flip_caught():
    """The flip is well-formed but a field is still plain PENDING — the whitewash R19e exists
    to stop. This is what the old R2 blanket-ban was really protecting against."""
    d = _valid_pending()
    d["source_portrait"] = "x-app-capture-2026-08-15"
    d["params_fit_approx"]["source_portrait_unlocked"] = True
    assert _has(check_portrait("x", d), "R19e")


def test_R3_gates_params_true_caught():
    d = _valid_pending(); d["params_fit_approx"]["gates_params"] = True
    assert _has(check_portrait("x", d), "R3")


def test_R5_crosslayer_token_interval_direct_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["token_interval_ms_dist"] = {
        "value": "259ms", "caliber": "direct", "keep_pending": True}
    assert _has(check_portrait("x", d), "R5")


def test_R5b_think_pause_uiproxy_caught():
    """think_pause=ui-proxy 过 R5（NETWORK_TIMING 允许 ui-proxy），但 R5b 必抓：
    §1 铁律3——UI 层绝不填 think_pause。这正是 R5 漏、R5b 补的形状。"""
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["think_pause_ms_dist"] = {
        "value": "~50ms (UI approx)", "caliber": "ui-proxy", "keep_pending": True,
        "source_layer": "ui", "confidence": "LOW", "note": "x"}
    viol = check_portrait("x", d)
    assert _has(viol, "R5b"), viol
    assert not _has(viol, "R5:"), viol  # R5 放行 ui-proxy → 证明抓它的是 R5b 而非 R5（"R5:" 带冒号，不误配 "R5b:"）


def test_R5b_request_size_uiproxy_caught():
    """网络字节字段标 ui-proxy = 跨层越界（§1 铁律3：UI 绝不填网络字节）。"""
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["request_size_bytes_dist"] = {
        "value": "13KB (UI guess)", "caliber": "ui-proxy", "keep_pending": True,
        "source_layer": "ui", "confidence": "LOW", "note": "x"}
    assert _has(check_portrait("x", d), "R5b")


def test_R5b_token_interval_uiproxy_allowed():
    """GREEN：token_interval 是唯一允许 ui-proxy 的字段（doubao ~100ms 实况）——R5b 绝不误拒它。"""
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["token_interval_ms_dist"] = {
        "value": "~100ms (UI cadence, != network ITL)", "caliber": "ui-proxy", "keep_pending": True,
        "source_layer": "ui", "confidence": "LOW", "note": "x"}
    assert check_portrait("x", d) == []   # 完整合法：R5b 放行 token_interval 的 ui-proxy


def test_R6_none_not_pending_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["think_pause_ms_dist"]["value"] = "123ms"  # caliber none but not PENDING
    assert _has(check_portrait("x", d), "R6")


def test_R9_bad_semver_caught():
    d = _valid_pending(); d["schema_version"] = "v1"
    assert _has(check_portrait("x", d), "R9")


def test_R10_typo_field_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["pop_ip_lst"] = d["params_fit_approx"]["fields"].pop("pop_ip_list")
    assert _has(check_portrait("x", d), "R10")


def test_R11_missing_keep_pending_caught():
    d = _valid_pending(); del d["params_fit_approx"]["fields"]["tool_loop_cadence"]["keep_pending"]
    assert _has(check_portrait("x", d), "R11")


def test_R12_declared_caliber_left_pending_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["request_size_bytes_dist"] = {
        "value": "PENDING(...)", "caliber": "order-of-magnitude", "keep_pending": True}
    assert _has(check_portrait("x", d), "R12")


def test_R13_nonpopip_escape_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["request_size_bytes_dist"] = {
        "value": "13.8KB", "caliber": "direct", "keep_pending": False}
    assert _has(check_portrait("x", d), "R13")


def test_R14_hostname_masquerade_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["pop_ip_list"] = {
        "value": "chat.deepseek.com (SNI hostname only)", "caliber": "direct", "keep_pending": False}
    assert _has(check_portrait("x", d), "R14")


# ---- RED per-invariant (check_cross_file) ----

def test_R15_media_not_none_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["downlink_media_bytes_dist"] = {
        "value": "17.6KB", "caliber": "order-of-magnitude", "keep_pending": True}
    assert _has(check_cross_file({"x": d}), "R15")


def test_R16_popip_not_direct_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["pop_ip_list"] = {
        "value": "PENDING(...)", "caliber": "none", "keep_pending": True}
    assert _has(check_cross_file({"x": d}), "R16")


def test_R17_no_evidence_backlink_caught():
    d = _valid_escaped_popip()
    d["observed_network_layer"] = {"endpoints": ["upaas.quark.cn (hostname only, no IP)"]}
    assert _has(check_cross_file({"x": d}), "R17")


def test_R18_missing_provenance_caught():
    d = _valid_pending(); del d["params_fit_approx"]["fields"]["think_pause_ms_dist"]["confidence"]
    assert _has(check_portrait("x", d), "R18")


def test_R18_inconsistent_source_layer_caught():
    # caliber=none requires source_layer=none; declaring network is provenance drift
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["think_pause_ms_dist"]["source_layer"] = "network"
    assert _has(check_portrait("x", d), "R18")


def test_R18_bad_confidence_enum_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["pop_ip_list"]["confidence"] = "HIGH"  # not in {LOW, NONE}
    assert _has(check_portrait("x", d), "R18")


def test_R18_uiproxy_requires_ui_source_layer():
    # ui-proxy caliber must carry source_layer=ui (not network) — cross-check with caliber
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["token_interval_ms_dist"].update(
        {"value": "~100ms (UI cadence)", "caliber": "ui-proxy",
         "source_layer": "network", "confidence": "LOW", "note": "x"})
    assert _has(check_portrait("x", d), "R18")


# ── D-595（C 裁定落地）：两条终态 —— session_duration 全 App／kimi 的 request_size 单 App ──

def test_R19d_session_duration_promoted_caught():
    """RED：D-595 把 session_duration 冻结为 N/A-BY-CALIBER 终态——会话边界是 App 内事件，
    本方法学观察面不产生该语义，且唯一近路（per-turn／UI 事件计数换算）被方法学明文禁止。
    把它降回 plain PENDING＝悄悄重开一个"加采集也长不出来"的格，R19d 必抓。"""
    d = _valid_pending()
    d["params_capture_status"]["session_duration_s_dist"] = {"status": "PENDING", "reason": "x"}
    assert _has(check_portrait("x", d), "R19d")


def test_R19f_kimi_request_size_promoted_caught():
    """RED：kimi 的 request_size 是**单 App** 终态（自有 IM 长连加密后聚合，免解密下不可切分
    per-request）。降回 PENDING → R19f 必抓。app 名参与判据——这正是 R19d 表达不了的那一半。"""
    d = _valid_pending()
    d["params_capture_status"]["request_size_bytes_dist"] = {"status": "PENDING", "reason": "x"}
    assert _has(check_portrait("kimi", d), "R19f")


def test_R19f_does_not_reach_the_other_three_apps():
    """GREEN，且是本轮最要紧的一条：doubao/deepseek/tongyi 的 request_size 仍是**可喂格**的
    PENDING（方向字节免解密可得）。R19f 若误伤它们，等于把三家一并冻死——与可行性评估相反，
    而这种过度触及不会报错、只会静默多冻三格。"""
    d = _valid_pending()
    d["params_capture_status"]["request_size_bytes_dist"] = {"status": "PENDING", "reason": "x"}
    for app in ("doubao", "deepseek", "tongyi", "x"):
        assert not _has(check_portrait(app, d), "R19f"), app


def test_R19f_key_stays_app_scoped_not_field_scoped():
    """两张冻结表的分工守在这里：per-App 条目若被误并进全局 RULED_STATUS，四家会一起冻结
    （RULED_STATUS 只按字段名索引，表达不了"这家不能、那家能"）。"""
    assert "request_size_bytes_dist" not in RULED_STATUS
    assert RULED_STATUS_BY_APP[("kimi", "request_size_bytes_dist")] == "N/A-BY-CALIBER"


def test_session_duration_no_longer_blocks_the_flip():
    """GREEN：终态后 session_duration 退出 gate_state 阻塞集（同 tool_loop_cadence 形状）。
    这是 D-595 ① 唯一的可观察后果——若 status 改了而门没跟着改，等于白改。"""
    ready, blockers = gate_state("x", _valid_pending())
    assert not ready
    assert "session_duration_s_dist" not in blockers
    assert set(blockers) == {"request_size_bytes_dist", "downlink_media_bytes_dist", "pop_ip_list"}


if __name__ == "__main__":
    # Self-contained runner so verify_all/CI need no pytest (Python 3.14 env has none).
    # pytest can still collect the test_* functions if present.
    import sys
    tests = {n: f for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)}
    failed = []
    for name, fn in tests.items():
        try:
            fn()
        except AssertionError as e:
            failed.append((name, f"assertion failed: {e}"))
        except Exception as e:  # noqa: BLE001 — surface any harness error as a failure
            failed.append((name, f"{type(e).__name__}: {e}"))
    print(f"ran {len(tests)} reflex tests: {len(tests) - len(failed)} passed, {len(failed)} failed")
    for name, why in failed:
        print("  FAIL", name, "-", why)
    sys.exit(1 if failed else 0)
