#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E-03（GLM 真端点抓取器）反例自跑器。

**不是 e1／e234 跑器的副本** —— 它 import e1 那一只并把自己的目录交给它枚举，
与 `tools/e234/tests/run_tests.py` 同形。仓里已为「同名不同处的副本」付过学费
（D-315），这里留一条真的依赖边。

exit 0 = 全绿 / 1 = 有红 / 5 = 一个测试都没收集到（三态与退出码同 e1）。

⚠ **为什么现在才有这只跑器**：`tools/e03` 的守卫自 2026-09-03 就在，**却不在
`scripts/verify_all.ps1` 的清单里**（e1／e234／go 在，e03 零命中，v4 核出）。
这是本仓「**门是真绿的、只是不在清单上**」的**第三例** —— 前两例正是 e1／e234 两只跑器，
它们的 docstring 逐字写着「以便直接接进 verify_all」而从未被接进来。
⇒ **「写好了一道门」与「那道门在门禁清单上」是两件事。**
更具体的代价：E-03 那句「夹具转换环节被钉住」的**真钉子**是
`test_the_kotlin_fixtures_are_a_verified_derivation_not_a_second_copy`，
而它此前**只在有人想起时才跑** —— 一个结论挂在没进门禁的守卫上，
读者却会以为它每轮都在被检验。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(HERE)), "e1", "tests"))

import run_tests as e1_runner  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(e1_runner.main(here=HERE, label="e03"))
