# -*- coding: utf-8 -*-
"""簇阈并排复算的守卫（B-11 / D-718 补充令）。

钉四件事：①相对门限算不出来时给 None，**不拿 0 顶替**；②两种口径在**两种
事件节拍**下方向相反（这正是本工具复算出来的结论，写成测试免得被人当巧合）；
③`abs400` 那一行必须是生产口径原样；④零事件与单簇分开（A-3 顺带项）。

夹具全是内存合成时戳，不碰 evidence、不写文件。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import gap_compare as gc        # noqa: E402

MS = 1_000_000
ABS400 = 400 * MS


def _by(rows, name):
    return next(r for r in rows if r["criterion"] == name)


def test_a_relative_threshold_that_cannot_be_defined_is_none_not_zero():
    """反例①：不足两点／中位间隔为 0 ⇒ **None**，绝不返回 0。

    0 会让「每个间隔都超阈」，把「算不了」印成「全断开」——两种状态都会给出
    一个像样的簇数，而它们的含义相反（R-10 同族）。
    反例证伪：把 `return None` 改成 `return 0`，本条即红。
    """
    assert gc.relative_gap_ns([], 10) is None
    assert gc.relative_gap_ns([1_000], 10) is None
    assert gc.relative_gap_ns([5, 5, 5], 10) is None      # 中位间隔 0
    assert gc.relative_gap_ns([0, 10 * MS, 20 * MS], 10) == 10 * 10 * MS


def test_the_two_criteria_move_in_opposite_directions_by_event_cadence():
    """反例②：**同一个 k，在两种节拍上效果相反**——本工具的核心发现。

    · 密集流（DeepSeek 形状，实测中位间隔 0.1–0.2 ms）：`k10` 只有几毫秒，
      **远小于** 400ms ⇒ 到处能切、A2 闭合；而 abs400 一簇都切不开。
    · 稀疏流（豆包形状，实测中位间隔 ~100 ms）：`k10` 变成 ~1000 ms，
      **大于** 400ms ⇒ 比绝对阈更严，abs400 能切的它反而切不出。
    ⇒ 相对门限**不是绝对门限的免费替代品**：换口径会让一批格由能判变不能判。
    反例证伪：把相对门限写成 `k × 常数` 而不是 `k × median`，本条即红。
    """
    dense = [i * MS // 5 for i in range(200)]            # 中位间隔 0.2ms
    dense += [dense[-1] + 3 * MS + i * MS // 5 for i in range(200)]
    dense_rows = gc.channel_rows(dense, ABS400)
    assert _by(dense_rows, "abs400")["closed"] is False, dense_rows
    assert _by(dense_rows, "k10")["closed"] is True, dense_rows

    sparse = [i * 100 * MS for i in range(6)]            # 中位间隔 100ms
    sparse += [sparse[-1] + 600 * MS + i * 100 * MS for i in range(6)]
    sparse_rows = gc.channel_rows(sparse, ABS400)
    assert _by(sparse_rows, "abs400")["closed"] is True, sparse_rows
    assert _by(sparse_rows, "k10")["closed"] is False, sparse_rows


def test_the_absolute_criterion_is_reported_untouched():
    """反例③：`abs400` 那一行必须是**生产口径原样**，本工具不换口径。

    传进来的绝对阈原样出现在报表里（毫秒），不被相对逻辑改写。
    反例证伪：把 abs 那一行也换成 k×median，本条即红。
    """
    rows = gc.channel_rows([0, 10 * MS, 500 * MS], ABS400)
    assert _by(rows, "abs400")["gap_ms"] == 400.0, rows
    assert _by(rows, "abs400")["clusters"] == 2, rows


def test_zero_events_and_single_cluster_look_identical_on_closed():
    """反例④（A-3 顺带项）：零事件与单簇在 `closed` 上**同形**，故必须另行分开。

    两者都切不出 A2，但病因相反：零事件是 A 侧根本没数据（查无障碍服务与
    包名过滤），单簇是有数据而结构不足（调 gap／换负载）。本条钉住「同形」
    这个事实本身——正因为同形，`a_shape` 那一列才不能省。
    反例证伪：把 `a_shape` 的两支合并成一个 "no_a2"，调用方就再也分不开。
    """
    empty = gc.channel_rows([], ABS400)
    assert _by(empty, "abs400")["clusters"] == 0, empty
    assert _by(empty, "abs400")["closed"] is False, empty
    one = gc.channel_rows([0, 10 * MS, 20 * MS], ABS400)
    assert _by(one, "abs400")["clusters"] == 1, one
    assert _by(one, "abs400")["closed"] is False, one
    assert _by(empty, "abs400")["closed"] == _by(one, "abs400")["closed"]
