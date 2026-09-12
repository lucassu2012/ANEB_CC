# -*- coding: utf-8 -*-
"""2× 分解的**判定层**：把 `CRITERIA_PREREG.md` §4 的六张表变成纯函数。

🔴 **为什么判定必须是纯函数而不是脚本里的 if**（复审 v2 第 7 条：判据与仪器之间没有一根线）：

- 判定表是**跑前写死**的东西，而「跑前写死」只有在**跑之前能被检验**时才有意义
  ⇒ 判定必须能在**没有设备、没有驱动、没有管理员权限**的情况下喂合成读数跑一遍；
- 本文件每个函数都返回 `(code, 说明)`，**说明由值算出，不许写死**
  （本树今日在 `forward_layer_probe.teardown_labels` 上同一形状犯过两次：
  先是标签焊在格式串里，再是只由一个读数算而那个读数承不起那句话）；
- 判据里凡 `NOT_EXECUTED`／`VOID`／`不可单判` 的格，这里一律是**独立的 code**，
  **不得压进「为假」**——处置不同：重跑量法 vs 再动一次手 vs 如实记。

配套合成门：`scripts/tests/test_decompose_2x_verdicts.py`（与 §1.3 同级）。
每条判词两个方向都钉：既要「假的不出现」，也要「真的仍被认出」
——只钉前者会得到一个把正确实现也判红的门（本树今日对抗面板 25 条存活 0 条即此）。
"""
import math

# 每格允许丢的目击数。§4.1／§4.2(b)／§4.6 三处同源 —— 改这里等于同时改三处判词。
TOL = 2
# 重数占比门槛（§4.1 第一、二行；§4.4 的前提句原样取自 §4.1 第一行）。
MAJORITY = 0.90


def _frac(hist, mult):
    """重数为 `mult` 的**键**占全部键的比例。分母是键数,不是目击数。"""
    total = sum(hist.values())
    return (hist.get(mult, 0) / float(total)) if total else 0.0


def verdict_identity(T, n_distinct, hist, a2_count=None):
    """§4.1 身份：七行。`hist` ＝ `summarize()` 的 `multiplicity_hist`。

    行序**按判据原样**，且两条 `A2` 相关的行（复审 (a) 那条我拆成的两支）
    必须在「其余」之前求值。`a2_count is None` ⇒ 那两支取不到前提 ⇒ 落「不可单判」，
    **不是**落其中任一支。
    """
    f1, f2 = _frac(hist, 1), _frac(hist, 2)
    lo1, hi1 = T - TOL, T
    lo2, hi2 = 2 * T - 2 * TOL, 2 * T
    if lo1 <= n_distinct <= hi1 and f2 >= MAJORITY:
        return ("TWICE", "去重 %d ∈ [%d,%d] 且重数 2 占比 %.0f%% ≥ %.0f%% ⇒ 同一数据报被呈现两次"
                % (n_distinct, lo1, hi1, f2 * 100, MAJORITY * 100))
    if lo2 <= n_distinct <= hi2 and f1 >= MAJORITY:
        return ("DIFFERENT", "去重 %d ∈ [%d,%d] 且重数 1 占比 %.0f%% ⇒ 是不同的包,不是倍增"
                % (n_distinct, lo2, hi2, f1 * 100))
    if n_distinct < lo1:
        return ("LOSS", "去重 %d < %d ⇒ 丢包或收尾截断过多,该格 NOT_EXECUTED 重跑;不得当成倍增"
                % (n_distinct, lo1))
    if n_distinct > hi2:
        return ("THIRD_PARTY", "去重 %d > %d ⇒ 有第三方群体混入,查 A2−A1 与 S1/S2 底噪后重判"
                % (n_distinct, hi2))
    if lo1 <= n_distinct <= hi1 and f1 >= MAJORITY:
        if a2_count is None:
            return ("UNDECIDABLE",
                    "去重 %d ∈ [%d,%d] 且重数 1 占比 %.0f%%,**但 A2 计数未取到** "
                    "⇒ 分不开「背景非 ICMP」与「原 A=40 不复现」,不可单判"
                    % (n_distinct, lo1, hi1, f1 * 100))
        if 2 * T - TOL <= a2_count <= 2 * T:
            return ("NO_2X_BACKGROUND",
                    "去重 %d 重数 1 而 A2 计数 %d ∈ [%d,%d] ⇒ 2× 在 ICMP 口径下不复现: "
                    "原 A=40 ≈ %d 个 ICMP ＋ 背景非 ICMP,须按 §4.6 末句改写 A=40 的含义"
                    % (n_distinct, a2_count, 2 * T - TOL, 2 * T, T))
        if lo1 <= a2_count <= hi1:
            return ("NO_2X_NOT_REPRODUCED",
                    "去重 %d 重数 1 且 A2 计数 %d 也 ∈ [%d,%d] ⇒ 原 A=40 连原 filter 都不复现 "
                    "⇒ 本轮前提消失,H1/H2/H4 全部不可判" % (n_distinct, a2_count, lo1, hi1))
        return ("UNDECIDABLE",
                "去重 %d 重数 1 而 A2 计数 %d 既不在 [%d,%d] 也不在 [%d,%d] ⇒ 不可单判"
                % (n_distinct, a2_count, 2 * T - TOL, 2 * T, lo1, hi1))
    return ("UNDECIDABLE",
            "去重 %d、重数分布 %s 不落任何一行 ⇒ 不可单判,如实记,不取整到近的一端"
            % (n_distinct, hist))


def conservation_selfcheck(F1, F2, C1):
    """§4.2(d) 守恒式自检。区间 `[-2*TOL, +TOL]` ＝ `[-4, +2]`,**不对称**。

    来历:`F1`／`F2` **两格**的丢包同向累加压低左端,`C1` **一格**的丢包抬高右端。
    ⚠ `|F1+F2-C1| <= 2` 会把「F1、F2 各丢 2 个」这一完全合法的情形判成违反守恒。
    """
    d = F1 + F2 - C1
    lo, hi = -2 * TOL, TOL
    if lo <= d <= hi:
        return ("CONS_OK", "F1+F2-C1 = %d ∈ [%d,%d] ⇒ 两桶合起来接住了 C1 的全部目击" % (d, lo, hi))
    if d < lo:
        return ("CONS_UNDERCOUNT",
                "F1+F2-C1 = %d < %d ⇒ 有 %d 个目击两桶皆不落 ⇒ 结论降级为「在被接住的那部分上成立」"
                % (d, lo, -d))
    return ("CONS_DOUBLE_COUNT",
            "F1+F2-C1 = %d > %d ⇒ 有目击被两腿各记一次 ⇒ ifIdx 不是互斥划分,本节 VOID" % (d, hi))


def verdict_h2(T, F1, F2, C1, T_F1, T_F2, T_C1, identity_code):
    """§4.2 H2：**判别器是划分,不是守恒式**。求值次序写死:T 前提 → 退化型 → 划分 → 守恒自检。

    🔴 守恒式在 H2 真假两个世界里**都成立**(H2 真 F1=F2=T 和 2T;H2 假同腿 clone F1=2T
    F2=0 和同样 2T)⇒ 它连主命题都分不开。下面前两条退化支**满足守恒式**,
    所以守恒式必须最后跑,否则会给它们发通行证。
    """
    if not (T_F1 == T_F2 == T_C1):
        return ("VOID_T_MISMATCH",
                "T 不等(F1:%s F2:%s C1:%s)⇒ 这不是守恒式,是三个不同分母的裸相加,本节 VOID"
                % (T_F1, T_F2, T_C1))
    near_c1 = lambda x: C1 - TOL <= x <= C1
    if near_c1(F1) and F2 == 0:
        return ("DEGENERATE_UPSTREAM_ONLY",
                "F1=%d ≈ C1=%d 而 F2=0 ⇒ 不可判:在「H2 不成立」与「转发层只暴露上游腿索引」之间歧义"
                % (F1, C1))
    if F1 == 0 and near_c1(F2):
        return ("DEGENERATE_HOTSPOT_ONLY",
                "F1=0 而 F2=%d ≈ C1=%d ⇒ 不可判(镜像极性)。sweep 把热点腿标为**入口**而 F2 要的是"
                "**到达接口** ⇒ 这一支比上一支更可能,不得因为它像「H2 被否」就读出结论" % (F2, C1))
    if F1 == 0 and F2 == 0:
        return ("DEGENERATE_BOTH_ZERO",
                "F1=F2=0 ⇒ 不可判且指向仪器:ifIdx 语义或该 filter 增量本身不匹配"
                "——这不是「H2 为假」,是这一问的量法没活")
    in_t = lambda x: T - TOL <= x <= T
    if in_t(F1) and in_t(F2):
        if identity_code != "TWICE":
            return ("UNDECIDABLE_IDENTITY",
                    "F1=%d F2=%d 各 ∈ [%d,%d],但 §4.1 判的是 %s 而非 TWICE "
                    "⇒ F1≈F2≈T 另有解释,本支不成立" % (F1, F2, T - TOL, T, identity_code))
        cc, cd = conservation_selfcheck(F1, F2, C1)
        if cc == "CONS_DOUBLE_COUNT":
            return ("VOID_DOUBLE_COUNT", "划分本支成立,但守恒自检否掉:" + cd)
        return ("H2_HOLDS", "F1=%d F2=%d 各 ∈ [%d,%d] 且 §4.1 判 TWICE ⇒ H2 成立(每接口各一次)。%s"
                % (F1, F2, T - TOL, T, cd))
    cc, cd = conservation_selfcheck(F1, F2, C1)
    return ("UNDECIDABLE",
            "F1=%d F2=%d C1=%d 不落任何一支 ⇒ 不可判,如实记三个数与三个 T;"
            "不得取整到近的一端,不得据此宣布 H2 为假。守恒自检:%s" % (F1, F2, C1, cd))


def impostor_band(n):
    """§4.3 中间带 ＝ `0.5 ± 1.96*sqrt(0.25/n)`。**由实测 n 现场算出,不写死。**

    n=40 时 ≈ [0.345, 0.655]。⚠ **不采用上游给的 [0.4,0.6]**:实算只有 ±1.26σ、
    覆盖 79.4% ⇒ 在「每包第二次目击是重注入」为真的世界里也有约 21% 会被判出带外。
    """
    assert n > 0, n
    h = 1.96 * math.sqrt(0.25 / n)
    return (0.5 - h, 0.5 + h)


def verdict_impostor(num, den, s3_ok, same_window, identity_code):
    """§4.3 impostor 占比。前提两条(S3、同窗)不过一律 VOID,**不是「impostor 为 0」**。"""
    if not s3_ok:
        return ("VOID_S3", "§1.6 的 S3 未过 ⇒ 本节整节 VOID。**不是「impostor 为 0」**"
                           "——否则自证失败会被读成阴性结果")
    if not same_window:
        return ("VOID_NOT_SAME_WINDOW",
                "分子分母不同窗 ⇒ VOID:跨格比值不是比值(四个时刻须并印)")
    if num is None or den is None or den == 0:
        return ("VOID_MISSING", "分子=%s 分母=%s ⇒ VOID:缺席不等于通过,也不等于 I==0" % (num, den))
    I = num / float(den)
    lo, hi = impostor_band(den)
    tol_f = TOL / float(den)
    if num == 0:
        return ("ZERO", "I=0(分子 0/%d)⇒ 该位在本路径未观测到置位。**不等于排除重注入**;"
                        "不得据此认为「已排除去碰安全软件的必要」" % den)
    if I <= tol_f:
        return ("TOLERANCE_LEVEL", "I=%.3f ≤ 2/n=%.3f ⇒ 置位数在每格容差量级内,不可单判:"
                                   "先看 S1/S2 底噪(§4.6)与 A2−A1" % (I, tol_f))
    if I < lo:
        return ("BELOW_BAND", "I=%.3f 落在 (2/n=%.3f, 带下界 %.3f) ⇒ 不可单判,如实记 %d/%d 与 n"
                % (I, tol_f, lo, num, den))
    if I <= hi:
        if identity_code != "TWICE":
            return ("UNDECIDABLE_PREMISE",
                    "I=%.3f ∈ [%.3f,%.3f],但本带的前提是 §4.1 判 TWICE 而实判 %s "
                    "⇒ 本带不适用(「一半目击是重注入」正是从「呈现两次」推出来的,"
                    "没有它就是循环论证)" % (I, lo, hi, identity_code))
        return ("IN_BAND", "I=%.3f ∈ [%.3f,%.3f](n=%d 现算)⇒ 与「每个数据报的第二次目击是重注入」"
                           "一致。⚠ **一致不等于已证**:impostor 为真至多说明「经某个注入句柄进入」"
                % (I, lo, hi, den))
    if I < 1 - tol_f:
        return ("ABOVE_BAND", "I=%.3f 落在 (带上界 %.3f, 1−2/n=%.3f) ⇒ 不可单判,如实记四个数"
                % (I, hi, 1 - tol_f))
    return ("NEAR_ALL", "I=%.3f ≥ 1−2/n=%.3f ⇒ 绝大多数或全部目击在 WinDivert 看见之前已是注入。"
                        "⚠ 下界取 1−2/n 而**不取上游的 0.9**(那是 4/n)" % (I, 1 - tol_f))


def verdict_h4(T, a_off_distinct, a_off_hist, a1_identity_code):
    """§4.4 H4：**前提是 `A1` 判 TWICE**（复审 v2 (b)；原先该节 `A1` 出现 0 次）。

    缺前提的后果不是「读数歧义」而是**自信的错结论**:A1 本来重数 1(2× 根本不存在)时,
    A-off 重数 1 会逐字判「2× 由 ICS 造成 ⇒ 同因,H4 为假」——而那里没有 2× 需要归因。
    """
    if a1_identity_code != "TWICE":
        return ("NOT_APPLICABLE",
                "A1 判的是 %s 而非 TWICE ⇒ 2× 在 ICMP 口径下本就不存在 "
                "⇒ H4 本轮不可判,**且本格不必跑**(§5 抬头的排期触发条件)" % a1_identity_code)
    f1, f2 = _frac(a_off_hist, 1), _frac(a_off_hist, 2)
    lo, hi = T - TOL, T
    if lo <= a_off_distinct <= hi and f1 >= MAJORITY:
        return ("SAME_CAUSE", "A-off 去重 %d ∈ [%d,%d] 且重数 1 占比 %.0f%% "
                              "⇒ A 的 2× 由 ICS 造成,两格同因,H4 为假"
                % (a_off_distinct, lo, hi, f1 * 100))
    if lo <= a_off_distinct <= hi and f2 >= MAJORITY:
        return ("DIFFERENT_CAUSE", "A-off 去重 %d ∈ [%d,%d] 且重数 2 占比 %.0f%% "
                                   "⇒ A 的 2× 与热点无关,确为不同因,H4 成立"
                % (a_off_distinct, lo, hi, f2 * 100))
    return ("UNDECIDABLE", "A-off 去重 %d、重数分布 %s ⇒ 不可单判,如实记"
            % (a_off_distinct, a_off_hist))


def verdict_n(T, N1, N2, src_same_within_key):
    """§4.5 N1／N2：**旁证**,单独不作结论。

    两格读数在「H1／NAT 形态」与「两个不同群体」这两个含义相反的世界里**逐字相同**
    ⇒ 分辨它们的不是计数,是 §4.1 的身份键(`summarize()` 的 `src_same_within_key`)。
    """
    in_t = lambda x: T - TOL <= x <= T
    if N2 == 0:
        return ("UNDECIDABLE_N2_ZERO",
                "N2=0 ⇒ 不可判:「NAT 后不呈现」与「本层看不见 NAT 后」歧义")
    if N1 == 0:
        return ("UNDECIDABLE_N1_ZERO", "N1=0 ⇒ 不可判(上一支的镜像极性)")
    if in_t(N1) and in_t(N2):
        if src_same_within_key is False:
            return ("H1_FORM", "N1=%d N2=%d 各 ∈ [%d,%d] 且同键而 src 不同 "
                               "⇒ H1 形态:同一数据报在 NAT 前后各一次" % (N1, N2, T - TOL, T))
        if src_same_within_key is True:
            return ("TWO_GROUPS", "N1=%d N2=%d 各 ∈ [%d,%d] 而键不跨 src ⇒ 两个不同群体,不是倍增"
                                  " ⇒ 须先按 §4.6 减底噪,并查 A2−A1" % (N1, N2, T - TOL, T))
        return ("UNDECIDABLE", "N1=%d N2=%d 落区间但 src_same_within_key=%s(未取到)⇒ 不可判"
                % (N1, N2, src_same_within_key))
    return ("UNDECIDABLE", "N1=%d N2=%d 不落区间 ⇒ 不可判,如实记两个数与 src_same_within_key=%s"
            % (N1, N2, src_same_within_key))


def noise_policy(s_count, s_window_s, target_window_s):
    """§4.6 底噪处置。门限 0／1-2／>=3 **是算的不是选的**:底噪 <= TOL 落在 §4.1 那把尺之内
    ⇒ 可被减法吸收;> TOL 足以把读数推过带边界 ⇒ 吸收不了。

    🔴 **窗长不足时只许单向使用**:短窗已超即可信(短窗只会低估),短窗未超**不得放行**,
    **也不得按速率外推**——外推就是「从旁边的常量推出一个数」。
    """
    short = s_window_s < target_window_s
    rate = s_count / float(s_window_s) if s_window_s else None
    tail = "(S 窗 %.1fs / 目标格 %.1fs,速率 %s 目击每秒)" % (
        s_window_s, target_window_s, "N/A" if rate is None else "%.3f" % rate)
    if s_count > TOL:
        return ("NOISE_TOO_HIGH", "底噪 %d > %d ⇒ 同层各格 NOT_EXECUTED%s%s"
                % (s_count, TOL, tail, "。短窗已超即可信,短窗只会低估" if short else ""))
    if short:
        return ("SHORT_WINDOW_NO_PASS",
                "底噪 %d <= %d **但 S 窗短于目标格** ⇒ 不得用来放行任何格、也不得按速率外推%s"
                % (s_count, TOL, tail))
    if s_count == 0:
        return ("NOISE_NONE", "底噪 0 ⇒ 同层各格按原样判%s" % tail)
    return ("NOISE_SUBTRACT", "底噪 %d ∈ [1,%d] ⇒ 同层各格先减底噪再判,并印出减前/减后两个数%s"
            % (s_count, TOL, tail))


def zero_reading_ok(count, shutting_down, thread_exited):
    """§1.1-6 零读数的**全格通则**：任何含 0 的读数仅当 `shutting_down` 且读线程已退出时成立。

    ⚠ `term_err` **不进本通则**(§1.1-4 已把它降为只印不判)。
    🔴 `0` 是唯一一个**既可能是结论、又可能是缺席**的读数 ⇒ 这条必须是全格而不是只给 S0。
    """
    if count != 0:
        return (True, "计数 %d 非 0 ⇒ 本通则不适用" % count)
    if shutting_down and thread_exited:
        return (True, "计数 0 且 shutting_down=True 且读线程已退出 ⇒ 这个 0 成立")
    return (False, "计数 0 而 shutting_down=%s 线程已退出=%s ⇒ 该格 NOT_EXECUTED"
                   "(分不开「仪器没跑」与「真的是 0」)" % (shutting_down, thread_exited))
