#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T14 ④「三面一致」镜头的**有界重试**（夜班 ①b）。

原镜头两次启动均死于连接错误。本轮只做一件可机器判定的事：
**一条规则号，在「代码真的发得出来」「门自己的 OK 行」「文档」三个面上分别出现在哪。**
清单从**产物导出**（扫 v.append 的报文），不手写（D-275/D-329）。
"""
import io
import os
import re
import subprocess
import sys

ROOT = r"E:\C Project\ANEB"

# 规则号形状：A1..A5 / R20a / R21b / R22 …
RULE_RE = re.compile(r"\b([AR]\d{1,2}[a-e]?)\b")
# 代码里真正会被打印出来的那批：形如  "[%s] A1: ..."  的报文首词
EMIT_RE = re.compile(r'"\[%s\]\s+([AR]\d{1,2}[a-e]?)\s*:')


def read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def at_head(relpath):
    """读 HEAD 版本——工作区里可能有他会话未提交的改动，扫那个会得出假发现。"""
    out = subprocess.run(["git", "show", "HEAD:" + relpath], cwd=ROOT,
                         capture_output=True)
    return out.stdout.decode("utf-8")


def emitted(src):
    """代码**真的发得出来**的规则号（从报文字面量导出，不是从注释）。"""
    return set(EMIT_RE.findall(src))


def in_ok_line(src, marker="OK:"):
    """门自己那行 OK 里点名了哪些。"""
    for line in src.splitlines():
        if marker in line:
            # OK 行常跨多行字符串续行，取它起始行之后的连续几行
            i = src.splitlines().index(line)
            chunk = "\n".join(src.splitlines()[i:i + 8])
            return set(RULE_RE.findall(chunk.split('")')[0]))
    return set()


def report(title, code_rel, doc_rels, ok_marker="OK:"):
    src = at_head(code_rel)
    emit = emitted(src)
    ok = in_ok_line(src, ok_marker)
    print("=" * 78)
    print(title)
    print("  面①  代码真发得出来 (%d): %s" % (len(emit), sorted(emit)))
    print("  面②  门自己的 OK 行 (%d): %s" % (len(ok), sorted(ok)))
    print("     OK 行少了: %s" % (sorted(emit - ok) or "—"))
    print("     OK 行多说了: %s" % (sorted(ok - emit) or "—"))
    for d in doc_rels:
        p = os.path.join(ROOT, d)
        if not os.path.isfile(p):
            print("  面③  %s —— 文件不存在" % d)
            continue
        doc = set(RULE_RE.findall(read(p)))
        print("  面③  %s (%d): %s" % (d, len(doc & (emit | ok)), sorted(doc & (emit | ok))))
        print("     文档少了: %s" % (sorted(emit - doc) or "—"))
    return emit, ok


report("【validate_adapters】stdout OK 行 ↔ 代码 ↔ README ↔ INSTRUMENTATION_SPEC",
       "spec/adapters/validate_adapters.py",
       ["spec/adapters/README.md", "spec/adapters/INSTRUMENTATION_SPEC.md"])

report("【check_redline】OK 行 ↔ 代码 ↔ 文档（读 HEAD 版，工作区有他会话改动）",
       "spec/portraits/check_redline.py",
       ["spec/portraits/PARAMS_FIT_METHODOLOGY.md",
        "docs/PROFILE3_PORTRAIT_2026-07-18.md"])
