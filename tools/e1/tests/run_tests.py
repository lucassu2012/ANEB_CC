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
sys.path.insert(0, os.path.dirname(HERE))  # tools/e1/
sys.path.insert(0, HERE)                   # tools/e1/tests/

TEST_MODULES = sorted(
    f[:-3] for f in os.listdir(HERE) if f.startswith("test_") and f.endswith(".py"))


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


def main():
    total = passed = 0
    failures = []
    for modname in TEST_MODULES:
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
    _say("e1 reflex: %d/%d passed" % (passed, total))
    if total == 0:
        return 5
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
