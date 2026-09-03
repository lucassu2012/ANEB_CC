# -*- coding: utf-8 -*-
"""`glm_capture` 的红线守卫（D-655① / 命题单 GLM-E03-20260903 §3）。

**每条都必须能失败**：断言落在「产物里有没有那串字节」上，不落在措辞上。

⚠ 本文件**不许用 pytest fixture**：本仓的 reflex 跑器从磁盘枚举模块后**直接 `fn()`
无参调用**，带 fixture 参数的测试在门上全部 TypeError。一律 `tempfile` + 手写 setup。
"""
import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import glm_capture as gc        # noqa: E402

# 合成 key：形状像真的、值绝不是真的。**守卫的全部意义是它不许出现在产物里。**
SYNTHETIC_KEY = "SYNTHETIC-KEY-e03-DO-NOT-USE-8f3a91c7"


def _files_under(d):
    out = []
    for root, _dirs, files in os.walk(d):
        for n in files:
            out.append(os.path.join(root, n))
    return out


def test_the_key_never_reaches_disk_even_on_the_error_path():
    """**错误路径也不许泄漏** —— 而错误路径正是泄漏最常发生的地方。

    异常对象往往携带请求上下文（`HTTPError.headers` / `URLError.reason`），
    「顺手把 e 打进日志」是这类泄漏的标准形态。故本条**刻意让请求打不通**
    （连一个必定拒绝的端口），走完整条异常 + 落盘路径，再逐文件搜那串合成 key。
    """
    d = tempfile.mkdtemp(prefix="e03guard_")
    try:
        key_path = os.path.join(d, "key.txt")
        with open(key_path, "w", encoding="utf-8") as fh:
            fh.write(SYNTHETIC_KEY + "\n")
        out_dir = os.path.join(d, "out")
        meta = gc.capture(out_dir, key_path=key_path,
                          base_url="http://127.0.0.1:1/api/paas/v4", timeout=3)
        assert meta["http_status"] != 200, "本条依赖请求打不通；它居然通了"

        produced = _files_under(out_dir)
        assert produced, "错误路径下一个产物都没写 —— 那本条什么也没验到"
        for p in produced:
            blob = open(p, "rb").read().decode("utf-8", errors="replace")
            assert SYNTHETIC_KEY not in blob, "key 出现在 %s" % p
            assert "Authorization" not in blob, "请求头出现在 %s" % p
            assert "Bearer" not in blob, "Bearer 前缀出现在 %s" % p
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_build_meta_has_no_slot_for_headers_at_all():
    """**结构上做不到，胜过纪律上不许。**

    `build_meta()` 不接受 header/key 形参 ⇒「请求头绝不落盘」不依赖调用方自觉。
    本条钉的是那个**缺席**：谁给它加一个能装密钥的形参，这里就红。
    """
    import inspect
    names = set(inspect.signature(gc.build_meta).parameters)
    for banned in ("headers", "header", "key", "api_key", "auth", "authorization"):
        assert banned not in names, "build_meta 长出了一个能装密钥的形参：%s" % banned
    meta = gc.build_meta("20260903-101500", "glm-4-flash", gc.GLM_BASE_URL,
                         "p", {"temperature": 0}, 200)
    blob = json.dumps(meta, ensure_ascii=False)
    assert "Bearer" not in blob and "Authorization" not in blob, blob


def test_the_base_url_matches_the_repo_preset_and_carries_no_v1():
    """端点不许漂，也不许被「顺手补个 /v1」。

    ⚠ 这条守的是**同一事实写在两处**：base URL 的权威副本在 `ProviderPresets.kt`
    （已核，逐字注明「base 必须精确到 /api/paas/v4，勿加 /v1，否则 404」），
    我在 Python 里抄了一份 —— **抄了就必有一处先漂**，故直接读 Kotlin 源码对账，
    而不是两边各写各的。
    """
    # _HERE = tools/e03/tests => 要三级才到仓根（首版只写两级，停在 tools/）
    root = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
    preset = os.path.join(root, "app", "probe", "src", "main", "java", "com",
                          "aneb", "probe", "apiprobe", "ProviderPresets.kt")
    assert os.path.exists(preset), "对账源不在：%s" % preset
    src = open(preset, encoding="utf-8").read()
    assert gc.GLM_BASE_URL in src, (
        "Python 侧的 GLM base URL 与 ProviderPresets.kt 对不上了：%s" % gc.GLM_BASE_URL)
    assert not gc.GLM_BASE_URL.rstrip("/").endswith("/v1"), (
        "base 被加了 /v1 —— 预设里逐字写着这会 404")
    assert gc.GLM_DEFAULT_MODEL in src, gc.GLM_DEFAULT_MODEL


def test_the_capturer_does_not_parse_anything():
    """抓取器只许产生**时戳**，不许算 TTFT/token 数 —— 量法留在生产解析器里。

    ⚠ 本条是**设计边界的守卫**，不是风格检查：一旦这里长出解析，本批就从
    「校生产量法」退化成「校一份重新实现」，**而判词读起来一模一样**。
    """
    import ast
    src = open(os.path.join(os.path.dirname(_HERE), "glm_capture.py"),
               encoding="utf-8").read()
    # ⚠ 判据落在**标识符**上，不落在散文上：首版按行搜全文，被 `capture()` 自己那句
    # 「其余一切（TTFT、token 数…）都留给判读侧」咬中 —— **那句正是在声明本边界**。
    # 「解析长出来了」的形态是出现同名的变量/函数/属性/短字面量，不是文档里提到它。
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Name):
            names.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            names.add(node.attr.lower())
        elif isinstance(node, ast.FunctionDef):
            names.add(node.name.lower())
            names |= {a.arg.lower() for a in node.args.args}
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if len(node.value) < 40 and chr(10) not in node.value:
                names.add(node.value.lower())      # 短字面量（多为字典键）也算
    for banned in ("ttft", "completion_tokens", "token_count", "itl"):
        assert banned not in names, (
            "抓取器里长出了判读侧的标识符 `%s` —— 解析必须留在 OpenAiSseAdapter" % banned)
