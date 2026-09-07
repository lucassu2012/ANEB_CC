# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/validate_profiles.py.

Unit tests drive check_structure with synthetic profile dicts; parity tests write
spec/runtime copies to temp dirs; one integration test asserts the REAL profiles
pass (proving the validator agrees with the shipped, mirrored profiles).
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import validate_profiles as vp


def _valid_profile(pid="s1_chat"):
    return {
        "profile_id": pid, "version": "0.2.0", "kpi_set": "agent-qoe-kpi-v0.2",
        "phases": [
            {"type": "clock_sync", "samples": 20},
            {"type": "upload_burst", "bytes": 2048, "chunk_kb": 2},
            {"type": "token_stream", "tokens": 600, "rate_tps": 40,
             "token_bytes": {"dist": "lognormal", "median": 120}},
            {"type": "tool_loop", "rounds": 3, "up_bytes": 100, "down_bytes": 200,
             "server_proc_ms": 50},
            {"type": "clock_sync", "samples": 20},
        ],
    }


# ---------------------------------------------------------------- structure

def test_valid_profile_structure_ok():
    assert vp.check_structure(_valid_profile(), "s1") == []


def test_missing_top_field_fails():
    p = _valid_profile()
    del p["kpi_set"]
    assert any("missing 'kpi_set'" in e for e in vp.check_structure(p, "s1"))


def test_empty_phases_fails():
    p = _valid_profile()
    p["phases"] = []
    assert any("non-empty array" in e for e in vp.check_structure(p, "s1"))


def test_unknown_phase_type_fails():
    p = _valid_profile()
    p["phases"][0] = {"type": "warp_drive", "samples": 1}
    assert any("unknown phase type" in e for e in vp.check_structure(p, "s1"))


def test_phase_missing_required_field_fails():
    p = _valid_profile()
    p["phases"][1] = {"type": "upload_burst", "bytes": 2048}   # no chunk_kb
    assert any("missing 'chunk_kb'" in e for e in vp.check_structure(p, "s1"))


def test_phase_field_wrong_type_fails():
    p = _valid_profile()
    p["phases"][2]["rate_tps"] = "fast"                        # must be numeric
    assert any("rate_tps" in e for e in vp.check_structure(p, "s1"))


def test_token_bytes_must_be_map():
    p = _valid_profile()
    p["phases"][2]["token_bytes"] = 120                        # must be a mapping
    assert any("token_bytes" in e for e in vp.check_structure(p, "s1"))


def test_bool_is_not_numeric():
    p = _valid_profile()
    p["phases"][0]["samples"] = True                           # bool != int
    assert any("samples" in e for e in vp.check_structure(p, "s1"))


# ------------------------------------------ adaptive_*_window（T47 批②，D-468/D-469）

def _s4_throughput_profile():
    return {
        "profile_id": "s4_throughput", "version": "0.1.0", "kpi_set": "agent-qoe-kpi-v0.3",
        "phases": [
            {"type": "clock_sync", "samples": 20},
            {"type": "adaptive_download_window", "window_ms": 4000, "bytes": 536870912,
             "chunk_kb": 256},
            {"type": "adaptive_upload_window", "window_ms": 4000, "bytes": 50331648,
             "chunk_kb": 64},
            {"type": "clock_sync", "samples": 20},
        ],
    }


def test_adaptive_window_phases_structure_ok():
    """正例：两个新 phase 类型各自的必填字段齐全时应通过结构校验。"""
    assert vp.check_structure(_s4_throughput_profile(), "s4") == []


def test_adaptive_download_window_missing_window_ms_fails():
    """负例：adaptive_download_window 缺 window_ms 应被拒。"""
    p = _s4_throughput_profile()
    del p["phases"][1]["window_ms"]
    assert any("missing 'window_ms'" in e for e in vp.check_structure(p, "s4"))


def test_adaptive_upload_window_missing_window_ms_fails():
    """负例：adaptive_upload_window 缺 window_ms 应被拒（下行/上行各自独立钉住）。"""
    p = _s4_throughput_profile()
    del p["phases"][2]["window_ms"]
    assert any("missing 'window_ms'" in e for e in vp.check_structure(p, "s4"))


def test_adaptive_window_ms_wrong_type_fails():
    """负例：window_ms 必须是 int，字符串应被拒（同 test_phase_field_wrong_type_fails 纪律）。"""
    p = _s4_throughput_profile()
    p["phases"][1]["window_ms"] = "4000"
    assert any("window_ms" in e for e in vp.check_structure(p, "s4"))


# ---------------------------------------------------------------- parity

def _write(d, name, obj, *, crlf=False):
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    if crlf:
        text = text.replace("\n", "\r\n")
    with open(os.path.join(d, name), "w", encoding="utf-8", newline="") as f:
        f.write(text)


def test_parity_holds_across_crlf_difference():
    """CRLF vs LF must NOT be a divergence — semantic parity, not byte parity."""
    with tempfile.TemporaryDirectory() as spec, tempfile.TemporaryDirectory() as rt:
        _write(spec, "s1_chat.json", _valid_profile(), crlf=False)
        _write(rt, "s1_chat.json", _valid_profile(), crlf=True)   # CRLF only
        assert vp.validate_dirs(spec, rt) == []


def test_semantic_divergence_detected():
    with tempfile.TemporaryDirectory() as spec, tempfile.TemporaryDirectory() as rt:
        a = _valid_profile()
        b = _valid_profile()
        b["phases"][2]["tokens"] = 999                            # a real edit
        _write(spec, "s1_chat.json", a)
        _write(rt, "s1_chat.json", b)
        assert any("DIVERGES" in e for e in vp.validate_dirs(spec, rt))


def test_present_on_one_side_only_fails():
    with tempfile.TemporaryDirectory() as spec, tempfile.TemporaryDirectory() as rt:
        _write(spec, "s1_chat.json", _valid_profile())
        # runtime has none
        errs = vp.validate_dirs(spec, rt)
        assert any("missing from runtime" in e for e in errs)


def test_runtime_extra_profile_fails():
    with tempfile.TemporaryDirectory() as spec, tempfile.TemporaryDirectory() as rt:
        _write(rt, "s9_rogue.json", _valid_profile("s9_rogue"))
        errs = vp.validate_dirs(spec, rt)
        assert any("missing from spec" in e for e in errs)


# ---------------------------------------------------------------- integration

def test_real_profiles_pass():
    if not (os.path.isdir(vp.DEFAULT_SPEC) and os.path.isdir(vp.DEFAULT_RUNTIME)):
        return
    errs = vp.validate_dirs(vp.DEFAULT_SPEC, vp.DEFAULT_RUNTIME)
    assert errs == [], f"real profiles violate parity/structure: {errs}"


# ------------------------------------------------ expected_n（D-707／D-740／D-751）

def _profile(phases):
    return {"profile_id": "p", "version": "0.0.0", "kpi_set": "k", "phases": phases}


def test_expected_n_derives_per_kpi_from_the_right_field():
    """六族各读相位的**不同字段**——这正是 D-740 §1 要求写成具名映射而非二分的理由。"""
    p = _profile([
        {"type": "clock_sync", "samples": 20},
        {"type": "clock_sync", "samples": 20},
        {"type": "token_stream", "tokens": 300},
        {"type": "token_stream", "tokens": 300},
        {"type": "upload_burst", "bytes": 1, "chunk_kb": 1},
        {"type": "tool_loop", "rounds": 8, "up_bytes": 1, "down_bytes": 1,
         "server_proc_ms": 1},
    ])
    got = vp.derive_expected_n(p)
    # 🔴 2026-09-07 随规则订正改：原断言 40（＝两个相位求和），**那是错的**。
    # 本夹具**恰好有两个 clock_sync 相位**，所以这一条同时钉住两件事：
    # ①**只取首个**（否则会是 40）；②**剔 ECHO_WARMUP**（否则会是 20）。
    # 依据：ScenarioKpi.kt:123-124 与 ScenarioRunner.kt:232/481；
    # 语料实测恒为 17（384/384）——见 test_derived_expected_n_matches_what_the_corpus_actually_recorded。
    assert got["N1"] == 17 and got["N2"] == 17, got     # first:samples-warmup = 20-3
    assert got["T1"] == 2, got                          # count
    assert got["T2"] == 598 and got["T3"] == 598, got   # sum:tokens-1
    assert got["U1"] == 1, got                          # count
    assert got["U2"] == 8, got                          # sum:rounds


def test_expected_n_omits_kpis_with_no_source_phase():
    """无来源相位 ⇒ **该 KPI 缺席**，不是期望 0。

    缺席说「这份 profile 不产出它」，0 说「该产出却一个都没有」——
    压成同一个值，下游就分不出「不适用」与「全丢了」。
    """
    got = vp.derive_expected_n(_profile([{"type": "clock_sync", "samples": 10}]))
    assert "D1" not in got and "U1" not in got and "T1" not in got, got
    # 随 2026-09-07 规则订正：10 − ECHO_WARMUP(3) = 7（原断言 10，未剔预热）
    assert got == {"N1": 7, "N2": 7}, got


def test_declared_expected_n_must_equal_derived():
    """声明只作覆盖，不等即红——手写是同一事实的第二份副本，**漂了不报错**。"""
    p = _profile([{"type": "upload_burst", "bytes": 1, "chunk_kb": 1}])
    p["expected_n"] = {"U1": 1}
    assert vp.check_expected_n(p, "p") == []            # 相等 ⇒ 放行（正对照）
    p["expected_n"] = {"U1": 3}
    errs = vp.check_expected_n(p, "p")
    assert any("U1" in e and "3" in e for e in errs), errs


def test_excluded_kpis_may_not_be_declared_and_the_reason_is_named():
    """S1／C1／C2 显名排除（D-751）；报错文案必须带上**为什么**。

    只报「不许声明」而不给理由，下一个人只会把它从清单里删掉——
    而理由（样本单位不是相位）才是它不该在这里的原因。
    """
    for kpi in ("S1", "C1", "C2"):
        p = _profile([{"type": "clock_sync", "samples": 10}])
        p["expected_n"] = {kpi: 3}
        errs = vp.check_expected_n(p, "p")
        assert errs and kpi in errs[0], (kpi, errs)
        assert vp.EXPECTED_N_EXCLUDED[kpi] in errs[0], (kpi, errs)


def test_real_profiles_derivation_matches_measured_corpus():
    """真实 profile 的推导值必须与**语料实测**对得上（承 D-746：s1 599／s3 397–398）。

    ⚠ 这条钉的是「规则没写反」，**不是「规则唯一正确」**——推导规则本身是单源的
    （由裁定给出、未经第二方独立推导），故只与**已实测过的那一族**比对。
    """
    if not os.path.isdir(vp.DEFAULT_RUNTIME):
        return
    got = {}
    for fn in sorted(os.listdir(vp.DEFAULT_RUNTIME)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(vp.DEFAULT_RUNTIME, fn), encoding="utf-8") as fh:
            prof = json.load(fh)
        got[prof.get("profile_id")] = vp.derive_expected_n(prof)
    assert got.get("s1_chat", {}).get("T2") == 599, got.get("s1_chat")
    assert got.get("s3_multimodal", {}).get("T2") == 398, got.get("s3_multimodal")
    # T1／U1／D1 三族对门限 3 **结构性不可达**（D-740 实测结论）——推导值全 < 3。
    for pid in ("s1_chat", "s2_coding_agent", "s3_multimodal"):
        for kpi in ("T1", "U1", "D1"):
            n = got.get(pid, {}).get(kpi)
            if n is not None:
                assert n < 3, (pid, kpi, n)


def test_echo_warmup_matches_the_kotlin_constant():
    """`vp.ECHO_WARMUP` 是 Kotlin 那个常量的**第二份副本**，必须钉死。

    真值在 `ScenarioRunner.kt` 的 `const val ECHO_WARMUP = 3`；N1/N2 的推导要减它。
    ⚠ **两处各写一个数、谁也不看谁**，正是 D-264／D-508 咬过的形状
    （「把 window_ms 减半，RTT 保护同步减半而无人吭声」）。
    照 `tools/e234/tests/test_e2_precheck.py:373` 的既有范式：**直接读那一侧比对**。
    """
    import re
    import pytest
    kt = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "app", "probe", "src", "main", "java", "com", "aneb", "probe", "engine",
        "ScenarioRunner.kt")
    if not os.path.isfile(kt):
        pytest.skip("app/ 不在本 checkout（鲜克隆/worktree）")
    with open(kt, encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"const\s+val\s+ECHO_WARMUP\s*=\s*(\d+)", src)
    assert m, ("在 ScenarioRunner.kt 里找不到 `const val ECHO_WARMUP` —— "
               "**量法失败与目标缺席同形**：先确认那个常量是不是改名/搬家了，别直接改本值")
    assert int(m.group(1)) == vp.ECHO_WARMUP, (
        "ECHO_WARMUP 两侧不一致：Kotlin=%s，validate_profiles=%s。"
        "改一侧不改另一侧，N1/N2 的 expected_n 会静默偏移，而**没有任何东西会报错**"
        % (m.group(1), vp.ECHO_WARMUP))


def test_derived_expected_n_matches_what_the_corpus_actually_recorded():
    """🔴 **推导值 ≟ 语料实测值**——本条的输入与推导规则**不共享任何假设**。

    为什么非有不可（2026-09-07 实证，D-707 笔②）：`check_expected_n` 核的是
    「profile 里**声明的** ≟ 我**推导的**」，**两侧出自同一个假设** ⇒
    一条错的推导规则（N1/N2 原写 `sum:samples`，推出 40 而实测恒为 17）
    **完美通过了那道守卫**。能发现它的只有语料。

    判据分两档，因为两族语义不同：
    - **非 ITL 族**（N1/N2/T1/U1/U2/D1）：**最大正实测 == 推导值**。
      取最大而非逐条相等，是容忍单次运行的丢样本；但**上界必须恰好够得着**——
      够不着就说明推导写错了（正是本次的病）。
    - **ITL 族**（T2/T3）：**最大正实测 <= 推导值**。D-746 已裁 `actual < expected`
      是**合并信号非错误**；本次复核过：s1 是 599==599 精确相等，
      **若存在固定剔除，s1 也会偏——它没偏**，故 s2/s3 的差是数据不是规则。

    ⚠ **非空自证**：末尾断言实际比对过的 (profile, KPI) 对数 > 0，
    否则语料缺席时本条会**空跑变绿**。
    """
    import collections
    import subprocess
    import pytest
    import corpus_ledger as cl

    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if cl.missing_roots([os.path.join(repo, r) for r in cl.DEFAULT_ROOTS]):
        pytest.skip("语料根不全（鲜克隆/worktree）")
    out = subprocess.run(
        [sys.executable, os.path.join(repo, "scripts", "corpus_ledger.py"), "--list-corpus"],
        cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert out.returncode == 0, out.stderr[:400]
    # ⚠ `--list-corpus` 输出的是**仓相对路径**，而门禁跑器的 cwd 是 `scripts/tests`
    # （`verify_all.ps1` 会 Push-Location 到那里）⇒ 直接拿去 open() 全部落空，
    # `summarize` 返回空集，本条会**空跑变绿**。故一律拼成绝对路径。
    # 这正是本仓 D-762 那条「门禁差异第三层是 cwd」的同一形状，落在新写的守卫上。
    paths = [p if os.path.isabs(p) else os.path.join(repo, p)
             for p in out.stdout.decode("utf-8").split("\n") if p.strip()]
    real, _synth, _st = cl.summarize(paths)      # 真实/合成与去重用台账自己的判据
    # 🔴 非空自证：这一句在门禁里真的红过一次（2026-09-07），拦下的正是上面那个 cwd 坑。
    assert real, ("真实语料为空 —— 空集上的比对会静默全绿。"
                  "先查路径是否因 cwd 而打不开，再查语料是不是真的没有")

    prof = {}
    for d in ("profiles", "evidence/e01_profiles_recovered_20260907"):
        dd = os.path.join(repo, d)
        if not os.path.isdir(dd):
            continue
        for fn in sorted(os.listdir(dd)):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(dd, fn), encoding="utf-8") as fh:
                j = json.load(fh)
            # ⚠ 这些 profile 用 `profile_id` 不是 `id`；漏掉这个 or 会让**全部**
            # scenario 判成「取不到 profile」而毫无报错（本轮我在一个临时脚本里正是这么栽的）
            pid, ver = j.get("id") or j.get("profile_id"), j.get("version")
            if pid and ver:
                prof[(pid, ver)] = j

    seen = collections.defaultdict(lambda: collections.defaultdict(int))
    for rec in real:
        for s in rec.get("scenarios", []):
            key = (s.get("profile_id"), s.get("profile_version"))
            for k, v in (s.get("kpi_quality") or {}).items():
                sc = v.get("sample_count")
                if isinstance(sc, int) and sc > 0:
                    seen[key][k] = max(seen[key][k], sc)

    itl = {"T2", "T3"}
    checked, bad = 0, []
    for key, kpis in seen.items():
        p = prof.get(key)
        if p is None:
            continue                 # profile 取不到 ⇒ 无从比对（登记另有守卫管）
        exp = vp.derive_expected_n(p)
        for k, mx in kpis.items():
            e = exp.get(k)
            if e is None:
                continue             # 该 KPI 推不出期望值 ⇒ 不在本条覆盖面内
            checked += 1
            if k in itl:
                if mx > e:
                    bad.append("%s@%s %s: 最大实测 %d > 推导 %d（ITL 只应少不应多）"
                               % (key[0], key[1], k, mx, e))
            elif mx != e:
                bad.append("%s@%s %s: 最大实测 %d != 推导 %d" % (key[0], key[1], k, mx, e))
    assert not bad, (
        "推导值与语料实测对不上：\n  " + "\n  ".join(bad) +
        "\n⇒ **先怀疑推导规则，不要先怀疑数据**：2026-09-07 那次正是推导错了"
        "（N1/N2 求了两个相位的和、又没剔 ECHO_WARMUP），而语料是对的。")
    assert checked > 0, "一对都没比到 —— 本条空跑了，等于没有守卫"
