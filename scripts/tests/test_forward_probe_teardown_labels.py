# -*- coding: utf-8 -*-
"""`teardown_labels` 的合成对照门：收尾标签必须由读数算出，且两个方向都有区分力。

🔴 **本文件存在的理由是同一形状在同一个函数里犯了两次**：

1. 第一次：「1060 ＝ 已卸载，符合判据 §5」**写死在格式串里** ⇒ `rc=0`（服务仍在）
   也照印「已卸载，符合判据」。那行输出进了转述、又进了裁定（README §1b）。
2. 第二次：改成「由 `rc` 算」之后**仍然**印「已卸载」「句柄关闭已触发 stop：是」——
   而非提权轮（实测 17:43 两轮）三个句柄全 `err=5`、**驱动从未装载**，`rc` 照样是 1060。

⇒ 两次都不是措辞问题：**它印出的是一段没发生过的历史**。`rc` 只说「此刻在不在」，
「已卸载」「句柄关闭触发了 stop」说的是「**本轮做了什么**」——后者需要另外两个读数。

⚠ 判据「如果这个标签又错了，**什么东西会报错**」——在本文件存在之前，答案是
「得有人看出来」，即靠记性。**本文件就是那个名字。**

**两个方向都钉**：只钉「假的那句不许出现」会得到一个连正确实现也判红的门
（本树今日已兑现：对抗面板 25 条存活 0 条，成因正是只给了否的方向）。
"""
import os
import sys

_DIAG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "diag")
if _DIAG not in sys.path:
    sys.path.insert(0, _DIAG)

from forward_layer_probe import teardown_labels      # noqa: E402

YES = "是（无需手动）"

# 四个世界，`rc` 全是 1060 —— 单看 `rc` 它们完全同形，这正是问题所在。
POS_ours = (1060, True, 1060)      # 跑格前不在 + 本轮开成句柄 ⇒ 本轮装的、本轮卸的
NEG_no_handle = (1060, False, 1060)  # 🔴 实测那两轮：一个句柄都没开成 ⇒ 没装过
NEG_not_ours = (1060, True, 0)     # 跑格前就在 ⇒ 别人装的，本轮只是搭了个车
NEG_no_reading = (1060, True, None)  # `pre_state` 漏传 ⇒ 无从归因
FAILED = (0, True, 1060)           # 服务仍在 ⇒ 判据 §5 FAIL


def test_positive_control_the_real_thing_must_still_be_recognized():
    """正对照：真的「本轮装的、本轮卸干净了」必须照样判达成。

    没有这一条，一个 `return ("无从归因", "无从判断")` 的实现会让全门变绿。
    """
    state, stop = teardown_labels(*POS_ours)
    assert "§5 达成" in state, state
    assert stop == YES, stop


def test_no_handle_opened_must_not_claim_it_unloaded_anything():
    """🔴 承重条：三个句柄全没开成时，不许说「已卸载」，不许说 stop 被触发。

    这就是 17:43 那两轮实际印出来的东西。
    """
    state, stop = teardown_labels(*NEG_no_handle)
    assert "已卸载" not in state, "没装过却说已卸载：%s" % state
    assert "达成" not in state, "没装过却说判据达成：%s" % state
    assert stop != YES, "没有句柄被关，却说句柄关闭触发了 stop：%s" % stop


def test_service_predating_the_run_must_not_be_credited_to_it():
    """跑格前服务就在 ⇒ 它不是本轮装的，消失也不许记在本轮头上。"""
    state, stop = teardown_labels(*NEG_not_ours)
    assert "达成" not in state, state
    assert stop != YES, stop


def test_missing_reading_degrades_to_no_attribution_not_to_a_nice_sentence():
    """`pre_state` 漏传时退回「无从归因」，**不退回一句好听的话**。"""
    state, stop = teardown_labels(*NEG_no_reading)
    assert "达成" not in state, state
    assert stop != YES, stop


def test_service_still_present_is_a_fail_not_a_pass():
    state, stop = teardown_labels(*FAILED)
    assert "FAIL" in state, state
    assert stop != YES, stop


def test_neither_reading_alone_is_enough():
    """🔴 两个读数都在承重：去掉任一个，两个含义相反的世界就并成一行。

    - `opened_any` 单独不够：`NEG_not_ours` 的 `opened_any` 也是 True。
    - `pre_state` 单独不够：`NEG_no_handle` 的 `pre_state` 也是 1060。
    ⇒ 本条要求这三格的输出**互不相同**。同形即不合格。
    """
    outs = [teardown_labels(*w) for w in (POS_ours, NEG_no_handle, NEG_not_ours)]
    assert len(set(outs)) == 3, "三个世界的输出没有全部分开：%s" % (outs,)


def test_every_world_is_reported_rather_than_silently_dropped():
    """五个世界都得有话说：空串或 None 是缺席，缺席不等于通过。"""
    for w in (POS_ours, NEG_no_handle, NEG_not_ours, NEG_no_reading, FAILED):
        state, stop = teardown_labels(*w)
        assert isinstance(state, str) and state.strip(), w
        assert isinstance(stop, str) and stop.strip(), w
