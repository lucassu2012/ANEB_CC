#!/usr/bin/env python3
"""`run_all.py` 对 `pytest.skip` 的处置守卫。

**这组测试存在的理由，写在这里以免日后被当成冗余删掉**：
`pytest.skip()` 抛的 `Skipped` 继承自 **`BaseException` 而非 `Exception`**
（实测 MRO：`Skipped → OutcomeException → BaseException`），于是 `run_all.py`
里的 `except Exception` **结构上接不住它** —— 一条会跳过的测试就能让整只跑器中断。

2026-09-06 实测：它死在 34 个模块里的**第 10 个**，其后 **24 个模块一条没跑**，
**且连汇总行都没印** ⇒ 操作者看到的是一段 traceback，
分不清「有测试失败」与「跑器根本没跑完」——而这两件事的处置完全不同。

⚠ **它为什么能藏一整天**：只有 skip 条件为真的地方才触发。主树两个语料根都在
⇒ skip 不触发 ⇒ 主树一直报 835/835 绿；而**每个 worktree 与新克隆都是死的**。
**同一只跑器、两棵树、两个结论，两边还都在诚实地报「门禁那只跑器」。**
上一层的洞是「你报哪只跑器我就报哪只」，这是它底下的第二层。

⚠ **不用 pytest 夹具**（承 f0f1286 的同族事故）：本目录的跑器是 `run_all.py`，
它**直接调函数**、不提供 monkeypatch/tmp_path/capsys，带夹具参数的测试在那边
一律 TypeError，而 pytest 侧照样全绿。本条一律手工建临时目录 + try/finally 清理。

⚠ **合成夹具刻意全 ASCII**：本组要量的是 skip 处置，**不是编码**。掺中文会把
`_say` 的转义行为卷进断言，让守卫在本该绿的时候红——量法不能把别的东西一起量进来。
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_ALL = os.path.join(HERE, "run_all.py")

# badges.py 的 reflex_tests() 用这条正则从链跑日志里读汇总行。
# **逐字抄来而不是 import**：抄一份，等于把「消费方的口径」变成本条里一个
# 被断言的常量 —— 谁改了 badges.py 的正则而没同步这里，两边会各自红，
# 而不是徽章静默读出一个错数。（run_all 的产物是那行 stdout，
# 它的读者有两个：badges.py 解析它，verify_all.ps1 原样回显它。）
BADGES_RE = r"([A-Za-z0-9_-]+) reflex:\s*(\d+)/(\d+)\s*passed"

# 一个会跳过的测试 + 一个会通过的测试。`run_all.py` 按 sorted(dir(mod)) 取名，
# 故 `test_a_passes` 先跑、`test_b_skips` 后跑 —— 旧代码正是在这里中断，
# 那时 passed 已经加到 1，**却因为汇总行还没印而谁也没看见**。
_SKIPPING = (
    "import pytest\n"
    "def test_a_passes():\n"
    "    assert True\n"
    "def test_b_skips():\n"
    "    pytest.skip('synthetic-skip-reason')\n"
)

_FAILING = (
    "def test_boom():\n"
    "    raise AssertionError('synthetic-failure-reason')\n"
)

_ALL_PASS = (
    "def test_a_passes():\n"
    "    assert True\n"
    "def test_b_passes():\n"
    "    assert True\n"
)


def _run_in_sandbox(modules):
    """把 `run_all.py` 复制进临时目录，只让它看见 `modules` 里的合成测试。

    `run_all.py` 的 `TEST_MODULES` 来自**它自己所在目录**的 `os.listdir`，
    所以换一个目录就换掉整套被测集合 —— 不必、也不该为了可测性去改它的代码。
    沙箱里只有 run_all.py 与合成模块，**本文件不在其中，故不会递归**。
    """
    tmp = tempfile.mkdtemp(prefix="run_all_skip_guard_")
    try:
        shutil.copy2(RUN_ALL, os.path.join(tmp, "run_all.py"))
        for name, src in modules.items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(src)
        proc = subprocess.run(
            [sys.executable, "run_all.py"], cwd=tmp,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        # ⚠ 刻意不给 `text=True`：不带 encoding= 时父进程按 cp936 解子进程的
        # utf-8，`UnicodeDecodeError` 抛在读取线程里被吞掉，`run()` 照常返回而
        # **stdout 静默变 None**（本仓为此红过一次）。拿字节自己解，坏字符替换。
        return proc.returncode, proc.stdout.decode("utf-8", errors="replace")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_a_skipping_test_neither_aborts_the_runner_nor_counts_as_passed():
    """跳过既不该中断跑器，也不该被算成通过。"""
    rc, out = _run_in_sandbox({"test_synthetic_skip.py": _SKIPPING})

    assert "Traceback" not in out, (
        "跑器被 Skipped 掀了 —— 这正是它继承 BaseException 而 except Exception "
        "接不住的那条路；此时后面的模块一条都不会跑：\n" + out)
    assert rc == 0, (
        "跳过不是失败：语料根不全在新克隆里是**真的且合理**，判它红会让门禁"
        "在那里根本不可用，而不是更诚实。实得 rc=%r\n%s" % (rc, out))
    assert "campaign-analysis reflex: 1/2 passed, 1 SKIPPED (did not run)" in out, (
        "汇总行没如实报出跳过：\n" + out)
    assert "SKIP test_synthetic_skip.test_b_skips: synthetic-skip-reason" in out, (
        "跳过没有逐条点名带理由 —— 只报一个计数，读者无从知道是哪几道门没跑：\n" + out)

    # 反例证伪（这两条才是「不许算成通过」的承重面）：
    # 把 skip 计进 passed ⇒ 汇总行会是 2/2；把它从 total 里丢掉 ⇒ 会是 1/1。
    # **两种写法都会印出一个干净的 N/N，盖住一道少跑了的门**，而那正是本仓
    # 反复被咬的形状。分母必须留着，缺口才看得见。
    assert "2/2 passed" not in out, "跳过被算成了通过 —— N/N 会盖住没跑的那道门"
    assert "1/1 passed" not in out, "跳过被从 total 里丢掉了 —— 同样印出干净的 N/N"


def test_a_real_failure_still_fails_the_gate():
    """正对照：新增的 skip 分支不得顺手吞掉真失败。

    少了这条，一个把 `except Exception` 一并改宽的实现同样能通过上面那条 ——
    而那会让门禁**永远绿**，比原来的崩溃坏得多（崩溃至少是响亮的）。
    """
    rc, out = _run_in_sandbox({"test_synthetic_fail.py": _FAILING})
    assert rc == 1, "真失败必须让门禁红，实得 rc=%r\n%s" % (rc, out)
    assert "FAIL test_synthetic_fail.test_boom" in out, (
        "失败没被点名：\n" + out)
    assert "0/1 passed" in out, "失败不该被算进 passed：\n" + out


def test_the_badge_regex_still_reads_the_summary_when_a_skip_suffix_is_present():
    """带 SKIPPED 后缀的汇总行，badges.py 那条正则仍须读出同样两个数。

    后缀刻意放在 `passed` **之后**：那条正则没有行尾锚，因此照旧命中前两个数。
    本条把这件事钉成断言，而不是留给下一个改汇总行的人去猜。
    """
    rc, out = _run_in_sandbox({"test_synthetic_skip.py": _SKIPPING})
    hits = re.findall(BADGES_RE, out)
    assert ("campaign-analysis", "1", "2") in hits, (
        "消费方(badges.py)的正则在带后缀的汇总行上读不出 1/2，实得 %r\n%s"
        % (hits, out))

    # 阳性对照：无跳过时同一条正则读出 N/N —— 证明上面那条命中不是因为
    # 正则宽松到什么都匹配，而是它确实在读这行汇总。
    rc2, out2 = _run_in_sandbox({"test_synthetic_pass.py": _ALL_PASS})
    assert rc2 == 0, out2
    assert ("campaign-analysis", "2", "2") in re.findall(BADGES_RE, out2), (
        "无跳过时正则读不出 2/2 —— 量法本身有问题：\n" + out2)
