#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `glm_capture` 抓的 `raw_sse.jsonl` 还原成**流文本**，供生产解析器的 JVM 单测吃。

⚠ **本文件也不解析**：它只做逐行拼接这一件事。`raw_sse.jsonl` 每行是抓取时的一条
物理行（含 SSE event 之间的空行），按 `\n` 拼回去就是原流；`SseFixtures.toRawEvents`
再按 `\n\n` 切 event —— **切分规则留在 Kotlin 侧，与生产 `SseReader.readRaw` 同源**。

⚠ 为什么要有这个转换、而不把 jsonl 直接给 Kotlin：jsonl 是**抓取层**的产物（多带了
宿主时戳），而解析器吃的是 wire 本身。**多带的那一列若被一起喂进去，解析器就在吃一份
我加工过的东西** —— 那正是本批极力避免的「校一份重新实现」的变体。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "e1"))
import e1_io                    # noqa: E402


def stream_text(jsonl_path):
    """-> 原始流文本（LF 结尾）。**逐行拼接，不做任何解释。**"""
    lines = []
    with open(jsonl_path, encoding="utf-8", errors="strict") as fh:
        for ln in fh:
            if ln.strip():
                lines.append(json.loads(ln)["raw"])
    return "\n".join(lines) + "\n"


def main(argv=None):
    e1_io.pin_console_utf8()
    ap = argparse.ArgumentParser(description="raw_sse.jsonl -> 流文本夹具（不解析）")
    ap.add_argument("--jsonl", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    text = stream_text(args.jsonl)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", errors="strict", newline="\n") as fh:
        fh.write(text)
    sys.stdout.write("sse_fixture: %d 字符 -> %s\n" % (len(text), args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
