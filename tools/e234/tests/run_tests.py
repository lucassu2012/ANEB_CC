#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2/E3/E4 反例自跑器。

**不是 e1 跑器的副本** —— 它 import 那一只并把自己的目录交给它枚举。
仓里已经为「同名不同处的副本」付过学费（D-315：`fnum` 三份、`load_records` 三份，
按 import 图找永远找不到那种刻意独立的副本）。这里留一条真的依赖边。

exit 0 = 全绿 / 1 = 有红 / 5 = 一个测试都没收集到（三态与退出码同 e1）。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(HERE)), "e1", "tests"))

import run_tests as e1_runner  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(e1_runner.main(here=HERE, label="e234"))
