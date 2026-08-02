#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E1 反例测试自跑器（无 pytest 依赖）。

exit 0 = 全绿 / 1 = 有红 / 5 = 一个测试都没收集到。
三态与退出码沿用 `scripts/tests/run_all.py` 与 `spec/portraits` 反例跑器的既有约定，
以便直接接进 `scripts/verify_all.ps1`。

模块清单**从磁盘枚举，不手写**：手写的清单会漏、会过期（D-275/D-364 的原样教训——
那张手写清单漏掉一个测试文件漏了整整一天，9 条守卫每次"全绿"都没跑过）。
"""
import importlib
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))


def discover(here):
    """枚举 `here` 下的测试模块，并把它与其父目录接进 `sys.path`。

    抽成函数是为了让**同构的第二个包**（`tools/e234/tests/`）复用这只跑器，
    而不是把它复制一份 —— 复制出来的跑器不会跟着这里的三态退出码演进，
    而「没有依赖边的副本」正是最难察觉的那种分叉（D-315）。
    """
    sys.path.insert(0, os.path.dirname(here))
    sys.path.insert(0, here)
    return sorted(
        f[:-3] for f in os.listdir(here) if f.startswith("test_") and f.endswith(".py"))


TEST_MODULES = discover(HERE)


def _say(text):
    """控制台编码不下这行字时也要把话说完（D-265：报错通道自己最容易死在报错上）。"""
    enc = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        text.encode(enc)
    except (UnicodeEncodeError, LookupError):
        out = []
        for ch in text:
            try:
                ch.encode(enc)
                out.append(ch)
            except (UnicodeEncodeError, LookupError):
                out.append("\\u%04x" % ord(ch))
        text = "".join(out)
    print(text)


def main(here=None, label="e1"):
    total = passed = 0
    failures = []
    for modname in (TEST_MODULES if here is None else discover(here)):
        mod = importlib.import_module(modname)
        for name in sorted(dir(mod)):
            if not name.startswith("test_"):
                continue
            fn = getattr(mod, name)
            if not callable(fn):
                continue
            total += 1
            try:
                fn()
                passed += 1
            except Exception:
                failures.append("%s::%s\n%s" % (modname, name, traceback.format_exc()))
    for f in failures:
        _say(f)
    _say("%s reflex: %d/%d passed" % (label, passed, total))
    if total == 0:
        return 5
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
