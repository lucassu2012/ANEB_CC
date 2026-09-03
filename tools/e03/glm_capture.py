#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E-03 · GLM 真端点 **原始 SSE 抓取器**（D-655①／命题单 GLM-E03-20260903）。

## 它刻意**不做**什么

**不解析、不算 TTFT、不数 token。** 全部量法留在生产解析器
`app/probe/.../apiprobe/OpenAiSseAdapter.kt` 里；本脚本只把**真 wire 字节**抓下来，
再由纯 JVM 单测喂给那个解析器。

⚠ 这条边界是本批的设计核心，不是洁癖：若在这里另写一份解析，**我校的就是一份重新
实现，而不是别人真正在用的那份代码**。本仓为「我验的对象与别人要用的对象是不是同
一个」付过学费。解析器零 Android import、`app/probe/src/test/java/` 是纯 JVM 源集
（已有 `SseFixtures.kt`／`OpenAiAdapterTest.kt`），故**不需要设备**也能测生产代码。

## 红线（PO 令，D-655①）

**key 永不入库／不入消息／不入日志。** 具体到本文件：
1. key 只在运行时从磁盘读，读进来的字符串**只用于构造请求头**；
2. **请求头绝不落盘** —— 落盘的元数据由 `build_meta()` 构造，它**结构上就没有**放
   header 的位置（守卫直接钉这一条：**结构上做不到，胜过纪律上不许**）；
3. 任何异常路径都不得把 header 或 key 打出来：网络异常只记类型与状态码。

⚠ 附一条只对「人」成立的纪律：**别 `cat` 那个 key 文件**。一旦回显，它就永久留在
会话记录/终端回滚里 —— 红线含「不入消息」，回显本身即一次泄漏。

## 端点不猜，取自仓内已核预设

`ProviderPresets.kt` 逐字写着 `baseUrl = "https://open.bigmodel.cn/api/paas/v4"`、
`defaultModel = "glm-4-flash"`，并点名陷阱「**base 必须精确到 /api/paas/v4（勿加
/v1，否则 404）**」。本文件照抄该值，不自行拼版本路径。
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "e1"))
import e1_io                    # noqa: E402  (D-648③ 输出编码自锁)

# 取自 `ProviderPresets.kt` 的已核值（核对日期 2026-07-13）。**勿加 /v1**。
GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
GLM_DEFAULT_MODEL = "glm-4-flash"
DEFAULT_KEY_PATH = os.path.join(os.path.expanduser("~"), ".aneb", "glm_api_key.txt")

# 固定 prompt：逐字写死并随证据包留存（命题单 §1b）。换 prompt 即另开一格。
FIXED_PROMPT = "请用中文写一段约 300 字的说明，介绍潮汐是怎么形成的。直接开始，不要寒暄。"


def read_key(path):
    """从磁盘读 key。**返回值绝不可进入任何落盘/打印路径。**

    只做三件事：读、strip、非空校验。校验失败时的报错**只说路径**，不回显任何片段
    ——「只印前几位」也不行：key 的前缀足以定位账号。
    """
    with open(path, "r", encoding="utf-8", errors="strict") as fh:
        key = fh.read().strip()
    if not key:
        raise ValueError("key 文件为空: %s" % path)
    return key


def build_meta(ts, model, base_url, prompt, params, http_status, note=None):
    """构造**要落盘**的元数据。**这个结构里没有放 header 的位置，这是刻意的。**

    它根本不接受 header/key 形参 —— 于是「请求头绝不落盘」这条红线**不依赖调用方
    自觉**。守卫会拿一个合成 key 走完整条路径，断言它不出现在任何产物里。
    """
    return {
        "ts": ts,
        "batch": "GLM-E03-20260903",
        "model": model,
        "base_url": base_url,
        "prompt": prompt,
        "params": dict(params),
        "http_status": http_status,
        "key_source": "file (path and value intentionally not recorded)",
        "note": note,
    }


def capture(out_dir, key_path=DEFAULT_KEY_PATH, model=GLM_DEFAULT_MODEL,
            base_url=GLM_BASE_URL, max_tokens=800, timeout=120):
    """打一次真调用，把**原始 SSE 行**逐行落盘。返回落盘的元数据 dict。

    ⚠ 逐行都带 `t_host_ns`：**时戳是抓取器唯一被允许产生的量**，因为它必须在字节
    到达的那一刻取；其余一切（TTFT、token 数、速率）都留给判读侧。
    """
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    params = {"temperature": 0, "max_tokens": max_tokens, "stream": True}
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": FIXED_PROMPT}],
        "stream": True,
        "temperature": 0,
        "max_tokens": max_tokens,
    }, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        base_url + "/chat/completions", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "text/event-stream")
    req.add_header("Authorization", "Bearer " + read_key(key_path))  # 不落盘、不打印

    raw_path = os.path.join(out_dir, "raw_sse.jsonl")
    status, note, seq = None, None, 0
    t0 = time.time_ns()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, \
                open(raw_path, "w", encoding="utf-8", errors="strict") as fh:
            status = resp.status
            for line in resp:
                seq += 1
                fh.write(json.dumps({
                    "seq": seq,
                    "t_host_ns": time.time_ns(),
                    "t_rel_ms": (time.time_ns() - t0) / 1e6,
                    "raw": line.decode("utf-8", errors="replace").rstrip("\r\n"),
                }, ensure_ascii=False) + "\n")
                fh.flush()
    except urllib.error.HTTPError as e:
        # ⚠ 只记状态码与异常类型：HTTPError 的 headers/body 可能回显请求上下文。
        status, note = e.code, "HTTPError"
    except (urllib.error.URLError, OSError) as e:
        status, note = None, type(e).__name__

    meta = build_meta(ts, model, base_url, FIXED_PROMPT, params, status, note)
    meta["raw_lines"] = seq
    meta["t_start_ns"] = t0
    with open(os.path.join(out_dir, "capture_meta.json"), "w",
              encoding="utf-8", errors="strict") as fh:
        fh.write(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def main(argv=None):
    e1_io.pin_console_utf8()   # D-648③：重定向落盘时别退回 GBK
    ap = argparse.ArgumentParser(description="E-03 GLM 真端点原始 SSE 抓取（不解析）")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--key-path", default=DEFAULT_KEY_PATH)
    ap.add_argument("--model", default=GLM_DEFAULT_MODEL)
    ap.add_argument("--max-tokens", type=int, default=800)
    args = ap.parse_args(argv)
    meta = capture(args.out_dir, key_path=args.key_path, model=args.model,
                   max_tokens=args.max_tokens)
    sys.stdout.write("glm_capture: status=%s raw_lines=%s -> %s\n"
                     % (meta["http_status"], meta["raw_lines"], args.out_dir))
    return 0 if meta["http_status"] == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
