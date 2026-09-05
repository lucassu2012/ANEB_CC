# -*- coding: utf-8 -*-
"""判读工具的输出编码自锁（D-648③）。

**为什么要单独一个模块**：本仓的规矩是「副本要留依赖边，留不了依赖边时至少留互指」
——而这里依赖边**是建得起来的**：`e234_common` 已 import `tools/e1`，
`e1_collect` 与 `e1_analyze` 是同层同侪。九个工具共用一份定义，比九份互指干净。
"""
import sys


def pin_console_utf8():
    """把 stdout/stderr 的编码钉成 UTF-8 —— **只在它不是终端时**。

    实测触发（采集侧报，我已复现）：`e2_precheck.py > out.txt` 之后
    `grep '逐段行数' out.txt` **恒 0**，而 `grep 'e2_precheck'` 照常命中 1 ——
    重定向时 Python 退回 locale 编码（Windows 上 cp936），把中文写成 GBK 字节，
    `file` 报 ISO-8859。**没有报错、没有丢字，只是编码错了**：
    `ec.say()` 救不了它，因为 `text.encode('cp936')` 对中文是**成功**的。

    ⚠ 为什么这件事致命而不只是难看：**区分「两种病」的两个键名全是中文**
    （`dump存活` 与 `逐段行数`）。量法把中文吃掉、只留 ASCII 命中
    ⇒ **读的人以为自己读全了**，而恰恰漏掉了那个用来分流的信号。

    ⚠ **只钉非终端，这个不对称是刻意的，别「统一」掉**：
    · 重定向／管道 ⇒ 读它的是机器与后来的人 ⇒ 必须是 UTF-8；
    · 终端 ⇒ 读它的是此刻的人，而老式 GBK 控制台收到 UTF-8 字节会显示成乱码；
      那一侧已由 `e234_common.say()` 兜住（编不出的字符逐个丢掉，话仍说得完）。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is None or stream.isatty():
                continue
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            # 流被替换过（测试捕获、非文本流）时静默跳过：**这条自锁失败不该
            # 让工具崩掉**——它是为了让输出可读，不是工具的前置条件。
            pass
