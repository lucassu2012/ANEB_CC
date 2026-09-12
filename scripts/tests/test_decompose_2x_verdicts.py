# -*- coding: utf-8 -*-
"""判定层的合成对照门（与判据 §1.3 同级：不过即整轮作废）。

🔴 **两个方向都钉**：既钉「假的判词不许出现」，也钉「真的仍被认出」。
只钉前者会得到一个把正确实现也判红的门——本树今日的对抗面板 25 条存活 0 条，
成因正是我只给了「否」的方向。

🔴 **另加一条通用守卫** `test_no_static_labels`：同一分支下两组不同输入
必须产出**不同**的说明文字。它直接防「固定标签焊在变量旁边读起来像结果」那一族
（`forward_layer_probe.teardown_labels` 上同一形状犯过两次）。
"""
import os
import sys

_DIAG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "diag")
if _DIAG not in sys.path:
    sys.path.insert(0, _DIAG)

from decompose_2x_verdicts import (                            # noqa: E402
    TOL, MAJORITY, conservation_selfcheck, impostor_band, noise_policy,
    verdict_h2, verdict_h4, verdict_identity, verdict_impostor, verdict_n,
    zero_reading_ok)

T = 20
TWICE_HIST = {2: 20}          # 20 个键各被看见两次
ONCE_HIST = {1: 20}           # 20 个键各一次
DIFF_HIST = {1: 40}           # 40 个键各一次


def test_identity_positive_controls_must_still_be_recognized():
    """正对照：两个决定性世界必须照样被认出（没有这条,一个恒 UNDECIDABLE 的实现全绿）。"""
    assert verdict_identity(T, 20, TWICE_HIST)[0] == "TWICE"
    assert verdict_identity(T, 40, DIFF_HIST)[0] == "DIFFERENT"


def test_identity_loss_and_third_party():
    assert verdict_identity(T, 5, {1: 5})[0] == "LOSS"
    assert verdict_identity(T, 60, {1: 60})[0] == "THIRD_PARTY"


def test_identity_the_two_new_rows_are_separated_by_a2_alone():
    """🔴 复审 (a) 那一行我拆成两支,本条钉「只有 A2 能分开它们」。

    三次调用的 `n_distinct` 与 `hist` **完全相同**,只有 `a2_count` 不同
    ⇒ 若实现忽略 `a2_count`,三者会同码,本条红。
    """
    bg = verdict_identity(T, 20, ONCE_HIST, a2_count=40)
    nr = verdict_identity(T, 20, ONCE_HIST, a2_count=20)
    un = verdict_identity(T, 20, ONCE_HIST, a2_count=None)
    assert bg[0] == "NO_2X_BACKGROUND", bg
    assert nr[0] == "NO_2X_NOT_REPRODUCED", nr
    assert un[0] == "UNDECIDABLE", un
    assert len({bg[0], nr[0], un[0]}) == 3, (bg, nr, un)


def test_identity_a2_in_neither_band_is_undecidable_not_the_nearer_end():
    """A2 既不在 [2T−2,2T] 也不在 [T−2,T] ⇒ 不可判,**不取整到近的一端**。"""
    code, why = verdict_identity(T, 20, ONCE_HIST, a2_count=30)
    assert code == "UNDECIDABLE", (code, why)
    assert "30" in why, "说明里没有那个数 ⇒ 它不是由值算出的：%s" % why


def test_conservation_interval_is_asymmetric():
    """🔴 `[-4, +2]`,不是 `|.| <= 2`。左端 -4 必须**通过**——那是「F1、F2 各丢 2 个」。

    这条正是我没照抄上游 `|F1+F2-C1| <= 2` 的地方:若实现取了对称的 ±2,本条红。
    """
    assert conservation_selfcheck(18, 18, 40)[0] == "CONS_OK", "F1/F2 各丢 2 个被判成违反守恒"
    assert conservation_selfcheck(17, 18, 40)[0] == "CONS_UNDERCOUNT"
    assert conservation_selfcheck(20, 20, 38)[0] == "CONS_OK"
    assert conservation_selfcheck(20, 20, 37)[0] == "CONS_DOUBLE_COUNT"


def test_h2_degenerate_branches_come_before_conservation():
    """🔴 承重条：前两条退化支**满足守恒式**,必须仍判退化而不是 H2 成立。

    `F1=40 F2=0 C1=40` ⇒ F1+F2-C1 = 0 ⇒ 守恒式过。若求值次序写成「守恒先跑」,
    这一格会拿到通行证。
    """
    up = verdict_h2(T, 40, 0, 40, T, T, T, "TWICE")
    ho = verdict_h2(T, 0, 40, 40, T, T, T, "TWICE")
    bo = verdict_h2(T, 0, 0, 40, T, T, T, "TWICE")
    assert up[0] == "DEGENERATE_UPSTREAM_ONLY", up
    assert ho[0] == "DEGENERATE_HOTSPOT_ONLY", ho
    assert bo[0] == "DEGENERATE_BOTH_ZERO", bo
    for c, _ in (up, ho, bo):
        assert "H2_HOLDS" not in c
    assert conservation_selfcheck(40, 0, 40)[0] == "CONS_OK", "前提:这一格确实满足守恒式"


def test_h2_positive_control_and_identity_gate():
    """正对照 ＋ 与 §4.1 的联合:同样的 F1/F2/C1,身份判词不同 ⇒ 判词必须不同。"""
    ok = verdict_h2(T, 20, 20, 40, T, T, T, "TWICE")
    assert ok[0] == "H2_HOLDS", ok
    for other in ("DIFFERENT", "NO_2X_BACKGROUND", "UNDECIDABLE"):
        bad = verdict_h2(T, 20, 20, 40, T, T, T, other)
        assert bad[0] == "UNDECIDABLE_IDENTITY", (other, bad)


def test_h2_t_mismatch_is_void_not_a_reading():
    code, why = verdict_h2(T, 20, 20, 40, 20, 19, 20, "TWICE")
    assert code == "VOID_T_MISMATCH", (code, why)
    assert "19" in why, why


def test_h2_double_count_can_kill_an_otherwise_passing_split():
    """守恒式唯一能独立否掉结论的那一支:被两腿各记一次。"""
    code, why = verdict_h2(T, 20, 20, 30, T, T, T, "TWICE")
    assert code == "VOID_DOUBLE_COUNT", (code, why)


def test_impostor_band_is_computed_and_is_not_the_upstream_number():
    """🔴 带必须由 n 算出,且 n=40 时**不等于** [0.4, 0.6]。"""
    lo, hi = impostor_band(40)
    assert abs(lo - 0.345) < 0.002 and abs(hi - 0.655) < 0.002, (lo, hi)
    assert not (abs(lo - 0.4) < 0.01 and abs(hi - 0.6) < 0.01), "带被写死成了上游那个数"
    lo2, hi2 = impostor_band(10)
    assert (hi2 - lo2) > (hi - lo), "n 变小带必须变宽 ⇒ 否则它不是由 n 算的"


def test_impostor_preconditions_are_void_not_zero():
    """S3 不过／不同窗／读不到 ⇒ 三个不同的 VOID,**都不得压成 I==0**。"""
    a = verdict_impostor(20, 40, s3_ok=False, same_window=True, identity_code="TWICE")
    b = verdict_impostor(20, 40, s3_ok=True, same_window=False, identity_code="TWICE")
    c = verdict_impostor(None, 40, s3_ok=True, same_window=True, identity_code="TWICE")
    assert (a[0], b[0], c[0]) == ("VOID_S3", "VOID_NOT_SAME_WINDOW", "VOID_MISSING")
    for code, _ in (a, b, c):
        assert code != "ZERO"


def test_impostor_bands_cover_every_ratio_without_a_gap():
    """遍历 0..n 的每个分子,必须都有码、都有非空说明 ⇒ 没有未覆盖段。"""
    den = 40
    seen = {}
    for num in range(den + 1):
        code, why = verdict_impostor(num, den, True, True, "TWICE")
        assert code and why.strip(), (num, code, why)
        seen.setdefault(code, []).append(num)
    for need in ("ZERO", "TOLERANCE_LEVEL", "BELOW_BAND", "IN_BAND", "ABOVE_BAND", "NEAR_ALL"):
        assert need in seen, (need, sorted(seen))


def test_impostor_in_band_requires_the_twice_premise():
    """带的前提是 §4.1 判 TWICE;否则同一个比值必须落到「前提不成立」。"""
    good = verdict_impostor(20, 40, True, True, "TWICE")
    bad = verdict_impostor(20, 40, True, True, "NO_2X_BACKGROUND")
    assert good[0] == "IN_BAND", good
    assert bad[0] == "UNDECIDABLE_PREMISE", bad


def test_h4_precondition_is_load_bearing():
    """🔴 承重条(复审 v2 (b))：**同样的 A-off 读数**,A1 判词不同 ⇒ 判词必须不同。

    A1 重数 1 时,A-off 重数 1 不得判「2× 由 ICS 造成」——那里没有 2× 需要归因。
    """
    same = verdict_h4(T, 20, ONCE_HIST, "TWICE")
    none = verdict_h4(T, 20, ONCE_HIST, "NO_2X_BACKGROUND")
    assert same[0] == "SAME_CAUSE", same
    assert none[0] == "NOT_APPLICABLE", none
    assert "不必跑" in none[1], none


def test_h4_positive_control_different_cause():
    assert verdict_h4(T, 20, TWICE_HIST, "TWICE")[0] == "DIFFERENT_CAUSE"
    assert verdict_h4(T, 33, {1: 20, 2: 13}, "TWICE")[0] == "UNDECIDABLE"


def test_n_cells_are_separated_only_by_src_same_within_key():
    """🔴 承重条：**同样的 N1/N2**,只有 `src_same_within_key` 不同 ⇒ 两个含义相反的世界。"""
    h1 = verdict_n(T, 20, 20, False)
    tg = verdict_n(T, 20, 20, True)
    un = verdict_n(T, 20, 20, None)
    assert (h1[0], tg[0], un[0]) == ("H1_FORM", "TWO_GROUPS", "UNDECIDABLE")


def test_n_zero_branches_are_undecidable_both_polarities():
    assert verdict_n(T, 20, 0, False)[0] == "UNDECIDABLE_N2_ZERO"
    assert verdict_n(T, 0, 20, False)[0] == "UNDECIDABLE_N1_ZERO"


def test_noise_thresholds_and_one_directional_short_window():
    """等长窗三档 ＋ 短窗只许单向:已超可信,未超不得放行。"""
    assert noise_policy(0, 21.0, 21.0)[0] == "NOISE_NONE"
    assert noise_policy(2, 21.0, 21.0)[0] == "NOISE_SUBTRACT"
    assert noise_policy(3, 21.0, 21.0)[0] == "NOISE_TOO_HIGH"
    # 短窗(现有代码的空闲格约 2s,目标格约 21s)
    assert noise_policy(3, 2.0, 21.0)[0] == "NOISE_TOO_HIGH", "短窗已超应当可信"
    assert noise_policy(0, 2.0, 21.0)[0] == "SHORT_WINDOW_NO_PASS", "短窗未超不得放行"
    assert noise_policy(2, 2.0, 21.0)[0] == "SHORT_WINDOW_NO_PASS"


def test_zero_reading_rule_applies_to_every_cell():
    """§1.1-6 全格通则:0 只在 shutting_down 且线程已退出时成立。"""
    assert zero_reading_ok(0, True, True)[0] is True
    assert zero_reading_ok(0, True, False)[0] is False
    assert zero_reading_ok(0, False, True)[0] is False
    assert zero_reading_ok(5, False, False)[0] is True, "非零读数本通则不适用"


def test_no_static_labels():
    """🔴 通用守卫：**同一分支**下两组不同输入必须产出**不同**的说明文字。

    这条直接防「固定标签焊在变量旁边」——那一族在本树的 `teardown_labels` 上犯过两次,
    且第一次那行输出进了转述、又进了裁定。
    """
    pairs = [
        ("identity/TWICE", verdict_identity(T, 20, {2: 20}), verdict_identity(T, 19, {2: 19})),
        ("cons/OK", conservation_selfcheck(20, 20, 40), conservation_selfcheck(18, 18, 40)),
        ("h2/degen", verdict_h2(T, 40, 0, 40, T, T, T, "TWICE"),
                     verdict_h2(T, 39, 0, 39, T, T, T, "TWICE")),
        ("impostor/IN_BAND", verdict_impostor(20, 40, True, True, "TWICE"),
                             verdict_impostor(19, 40, True, True, "TWICE")),
        ("h4/SAME", verdict_h4(T, 20, {1: 20}, "TWICE"), verdict_h4(T, 19, {1: 19}, "TWICE")),
        ("n/H1", verdict_n(T, 20, 20, False), verdict_n(T, 19, 19, False)),
        ("noise/SUBTRACT", noise_policy(1, 21.0, 21.0), noise_policy(2, 21.0, 21.0)),
    ]
    for name, a, b in pairs:
        assert a[0] == b[0], "%s: 两组输入应落同一分支,实得 %s / %s" % (name, a[0], b[0])
        assert a[1] != b[1], "%s: 同分支两组不同输入给出**逐字相同**的说明 ⇒ 那句话是写死的" % name
