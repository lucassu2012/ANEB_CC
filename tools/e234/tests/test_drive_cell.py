# -*- coding: utf-8 -*-
"""`drive_cell.py`（com.larus.nova 版）与 `drive_cell_ds.py`（DeepSeek 孪生）的反例守卫。

对应 REVIEW_20260905_FULL §7.1 A-1 的四件：① pin_console_utf8 是 main() 首条语句、
② focus_ok 全等包名＋Awake、③ `adb -s SERIAL shell` 与单引号包裹＋SH 注入点、
④ prompt 必 ASCII 且落账目首行。**每条对两只驱动器各跑一遍**——这对孪生最可能的
分叉形状就是「一只改了另一只没改」（148/154 行逐字重复，修一处漏一处即签名分叉）。

⚠ 本文件**不许用 pytest fixture**：跑器（`tools/e1/tests/run_tests.py:main`）从磁盘枚举
模块后**直接 `fn()` 无参调用**，带参测试全部 TypeError（仓里已付过学费，见
test_e2_precheck 头注）。注入一律手工 swap 模块属性、在 finally 里还原。
⚠ `SystemExit` 不是 `Exception`：跑器的 `except Exception` 接不住它——放它逃出去会把
**整只跑器**杀掉、后面的测试一条都不跑。凡预期 SystemExit 的测试必须自己接。
⚠ 假件不碰 adb：`SH` 与 `subprocess` 都被换成内存假件，本文件在没有设备的机器上必须全绿。
"""
import ast
import contextlib
import difflib
import io
import json
import os
import shlex
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import drive_cell as dc          # noqa: E402
import drive_cell_ds as dcd      # noqa: E402

DRIVERS = (dc, dcd)
SERIAL = "TESTSERIAL0001"
AWAKE = "POWER MANAGER (dumpsys power)\n  mWakefulness=Awake\n  mWakefulnessChanging=false\n"
ASLEEP = "POWER MANAGER (dumpsys power)\n  mWakefulness=Asleep\n  mWakefulnessChanging=false\n"


# ── 夹具 ──────────────────────────────────────────────────────────────────
@contextlib.contextmanager
def _swap(obj, name, value):
    """临时替换 obj.name，退出时还原（fixture 的手工替身）。"""
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


@contextlib.contextmanager
def _env(name, value):
    """临时设置/删除环境变量（value=None ＝ 删除），退出时还原。"""
    had, old = name in os.environ, os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        yield
    finally:
        if had:
            os.environ[name] = old
        else:
            os.environ.pop(name, None)


def _window_dump(focus_pkg, other_pkgs=()):
    """仿 `dumpsys window` 的片段：一行 mCurrentFocus，外加若干**非焦点**窗口行。

    非焦点窗口行是 (b) 用的：旧的子串判据只要 PKG 在整段里出现就放行，
    而焦点其实在别的包上——正是探针自家窗口/前缀同名包会造出的形状。
    """
    lines = ["WINDOW MANAGER WINDOWS (dumpsys window windows)"]
    for i, p in enumerate(other_pkgs):
        lines.append("  Window #%d Window{1a2b3c%d u0 %s/%s.OverlayActivity}:" % (i, i, p, p))
    lines.append("  mCurrentFocus=Window{7a3f1c2 u0 %s/%s.MainActivity}" % (focus_pkg, focus_pkg))
    lines.append("  mFocusedApp=AppWindowToken{9d8e7f token=Token{...}}")
    return "\n".join(lines) + "\n"


class _FakeSH:
    """SH 的假件：按 (dumpsys window / dumpsys power) 回预置文本，其余回空串，并记下每次 argv。"""

    def __init__(self, window, power):
        self.window, self.power, self.calls = window, power, []

    def __call__(self, *args):
        self.calls.append(tuple(args))
        if args == ("dumpsys", "window"):
            return self.window
        if args == ("dumpsys", "power"):
            return self.power
        return ""


class _FakeSubprocess:
    """`subprocess` 模块的假件：只提供 run()，记下 argv 与 kwargs，回一个带 stdout 的对象。"""

    class _Done:
        def __init__(self, stdout):
            self.stdout, self.returncode = stdout, 0

    def __init__(self, stdout="ok\n", forbid=False):
        self.stdout, self.forbid, self.calls = stdout, forbid, []

    def run(self, argv, **kwargs):
        if self.forbid:
            raise AssertionError("adb 不该被调用，但 subprocess.run 收到了 %r" % (argv,))
        self.calls.append((list(argv), dict(kwargs)))
        return self._Done(self.stdout)


class _FakeClock:
    """把 `time` 模块换成可控时钟：sleep 直接拨表，wait_until 的轮询于是确定且零耗时。"""

    def __init__(self, t0=1_000_000.0):
        self.t = t0

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += s


def _source(mod):
    with open(mod.__file__, encoding="utf-8") as fh:
        return fh.read().replace("\r\n", "\n")


def _pin_calls(tree):
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and (
        (isinstance(n.func, ast.Attribute) and n.func.attr == "pin_console_utf8")
        or (isinstance(n.func, ast.Name) and n.func.id == "pin_console_utf8"))]


# ── (a) pin_console_utf8：恰一个 Call 且是 main() 首条语句 ─────────────────────
def test_pin_console_utf8_is_first_statement_of_main():
    """A-1 ①：此前它**写在 docstring 里**——字面在、Call 不在、空转一天。

    三断言缺一不可：Call 恰 1（0＝没调，2＝有人在模块层又调了一次，两者都不是「首条语句」）；
    `main.body[0]` 就是那个 Call（不是跳过 docstring 后的第一条——docstring 也是一条语句，
    留着它这句就永远不是首条）；任何字符串常量里都不再含这个名字（把旧形状钉死）。
    """
    for mod in DRIVERS:
        tree = ast.parse(_source(mod))
        calls = _pin_calls(tree)
        assert len(calls) == 1, "%s: pin_console_utf8 Call 数=%d，须恰为 1" % (mod.__name__, len(calls))
        main = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
        assert len(main) == 1, "%s: 找不到唯一的 main()" % mod.__name__
        first = main[0].body[0]
        assert isinstance(first, ast.Expr) and first.value is calls[0], \
            "%s: main() 首条语句不是 pin_console_utf8()，而是 %s（行 %d）" % (
                mod.__name__, type(first).__name__, first.lineno)
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                assert "pin_console_utf8" not in n.value, \
                    "%s: 字符串常量里仍出现 pin_console_utf8（旧的空转形状）" % mod.__name__


# ── (b) focus 三态 ──────────────────────────────────────────────────────────
def test_focus_ok_three_states():
    """A-1 ②：前台正是 PKG 且 Awake → True；前缀包（PKG+'.ctree'）→ False；Awake 缺失 → False。

    前缀包那格刻意在**非焦点窗口行**里放一个真 PKG：旧判据 `PKG in <整段>` 会放行它，
    新判据只看 mCurrentFocus 且全等——这一格能把旧实现打红。
    另附 None 态：旧实现是 TypeError 炸掉，新实现须是 False（不炸、且停）。
    """
    for mod in DRIVERS:
        pkg = mod.PKG
        # 态 1：前台正是 PKG、屏醒 → True
        ok = _FakeSH(_window_dump(pkg), AWAKE)
        with _swap(mod, "SH", ok):
            assert mod.focus_ok() is True, "%s: 正常态应为 True" % mod.__name__
        assert ("dumpsys", "window") in ok.calls and ("dumpsys", "power") in ok.calls, \
            "%s: True 必须两条 dumpsys 都问过（只问一条＝判据只落了一半）" % mod.__name__
        # 态 2：焦点在前缀包上，PKG 只出现在别的窗口行 → False
        prefix = _FakeSH(_window_dump(pkg + ".ctree", other_pkgs=(pkg,)), AWAKE)
        with _swap(mod, "SH", prefix):
            assert mod.focus_ok() is False, \
                "%s: 前缀包 %s 顶焦点时应为 False（子串判据会误放行）" % (mod.__name__, pkg + ".ctree")
        # 态 3：前台对、但屏没醒（无 mWakefulness=Awake） → False
        asleep = _FakeSH(_window_dump(pkg), ASLEEP)
        with _swap(mod, "SH", asleep):
            assert mod.focus_ok() is False, "%s: Awake 缺失时应为 False" % mod.__name__
        # 附：SH 回 None（D-630 静默丢失通道）→ False 而非 TypeError
        with _swap(mod, "SH", lambda *a: None):
            assert mod.focus_ok() is False, "%s: SH 回 None 时应为 False 且不炸" % mod.__name__


# ── (c) 引号转义与 argv 形状 ───────────────────────────────────────────────────
def test_sh_argv_serial_and_quoting():
    """A-1 ③：argv 前四项 ['adb','-s',SERIAL,'shell']，其后每项单引号包裹、内含单引号按 '"'"' 拆接。

    两层核：(1) 逐项字面正确；(2) 把设备侧那半用 POSIX 规则（shlex）再解析一次，
    须**逐项还原**成原参数——这是「引号对不对」真正要回答的问题：设备 shell 拆完
    等不等于我想传的。另核 D-648③ 自锁没被顺手改掉：encoding=utf-8 + errors=replace。
    """
    raw = ("input", "text", "it's a 'quoted'  arg", "plain", "E4MARK kind=turn_start n=1")
    for mod in DRIVERS:
        fake = _FakeSubprocess(stdout="ok\n")
        with _env("ANEB_SERIAL", SERIAL), _swap(mod, "subprocess", fake):
            out = mod.sh(*raw)
        assert out == "ok\n", "%s: sh() 须回 stdout" % mod.__name__
        assert len(fake.calls) == 1, "%s: sh() 应恰调一次 subprocess.run" % mod.__name__
        argv, kwargs = fake.calls[0]
        assert argv[:4] == ["adb", "-s", SERIAL, "shell"], "%s: argv 前四项=%r" % (mod.__name__, argv[:4])
        expect = ["'input'", "'text'", "'it'\"'\"'s a '\"'\"'quoted'\"'\"'  arg'", "'plain'",
                  "'E4MARK kind=turn_start n=1'"]
        assert argv[4:] == expect, "%s: 设备侧参数逐项=%r，期望 %r" % (mod.__name__, argv[4:], expect)
        assert shlex.split(" ".join(argv[4:])) == list(raw), \
            "%s: 设备侧 shell 按 POSIX 拆回来不等于原参数" % mod.__name__
        assert kwargs.get("encoding") == "utf-8" and kwargs.get("errors") == "replace", \
            "%s: D-648③ 自锁（encoding=utf-8, errors=replace）被改动：%r" % (mod.__name__, kwargs)
        # 模块级注入点存在且默认就是 sh 本体
        assert getattr(mod, "SH", None) is mod.sh, "%s: 缺模块级 SH = sh 注入点" % mod.__name__


# ── (e) 缺 serial ────────────────────────────────────────────────────────────
def test_sh_without_serial_exits_2_before_touching_adb():
    """A-1 ③：未设 ANEB_SERIAL（或设成空白）→ SystemExit(2)，stderr 有一句原因，adb 一次都不碰。

    SystemExit 在这里自己接：漏出去会杀掉整只跑器（见文件头注）。
    """
    for mod in DRIVERS:
        for bad in (None, "", "   "):
            fake = _FakeSubprocess(forbid=True)
            err = io.StringIO()
            with _env("ANEB_SERIAL", bad), _swap(mod, "subprocess", fake), \
                    contextlib.redirect_stderr(err):
                try:
                    mod.sh("echo", "x")
                except SystemExit as e:
                    assert e.code == 2, "%s: ANEB_SERIAL=%r 时退出码=%r，须为 2" % (mod.__name__, bad, e.code)
                else:
                    raise AssertionError("%s: ANEB_SERIAL=%r 时 sh() 没有 SystemExit" % (mod.__name__, bad))
            assert "ANEB_SERIAL" in err.getvalue(), \
                "%s: 退出前须在 stderr 打印含 ANEB_SERIAL 的原因，实得 %r" % (mod.__name__, err.getvalue())
            assert fake.calls == [], "%s: 缺 serial 时不该碰 adb" % mod.__name__


# ── (d) 多轮账目 ────────────────────────────────────────────────────────────
def test_three_rounds_ledger_prompt_first_then_one_line_per_round():
    """A-1 ④：跑 N=3 轮（SH 假件、时钟假件），账目首行 kind=prompt，其后每轮一行且带实际等待值。

    顺带把 D-621 最在意的那件钉死：每轮里 `input text` → `turn_start` → `tap SEND` →
    `answer_complete` 的**先后**——本轮改动不许动它，这条断言让「动了」当场现形。
    """
    prompt = "hello world  test"
    for mod in DRIVERS:
        tmp = tempfile.mkdtemp(prefix="drv_")
        try:
            out_dir = os.path.join(tmp, "cell_x")
            fake = _FakeSH(_window_dump(mod.PKG), AWAKE)
            clock = _FakeClock()
            argv = ["drive_cell.py", out_dir, "3", prompt, "0.3", "0.2"]
            with _env("ANEB_SERIAL", SERIAL), _swap(mod, "SH", fake), _swap(mod, "time", clock), \
                    _swap(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                mod.main()
            path = os.path.join(tmp, "cell_x_driver_timing.jsonl")
            with open(path, encoding="utf-8") as fh:
                lines = [ln for ln in fh.read().split("\n") if ln.strip()]
            assert len(lines) == 4, "%s: 账目应 1 首行 + 3 轮 = 4 行，实得 %d" % (mod.__name__, len(lines))
            head = json.loads(lines[0])
            assert head == {"kind": "prompt", "text": prompt, "pkg": mod.PKG, "serial": SERIAL}, \
                "%s: 首行=%r" % (mod.__name__, head)
            for i, ln in enumerate(lines[1:], 1):
                rec = json.loads(ln)
                assert rec["round"] == i, "%s: 第 %d 行 round=%r" % (mod.__name__, i, rec.get("round"))
                for key, intended in (("answer_wait", 0.3), ("quiet", 0.2)):
                    act = rec["%s_actual_s" % key]
                    assert rec["%s_intended_s" % key] == intended
                    assert intended <= act <= intended + mod.POLL_S + 1e-9, \
                        "%s: 轮 %d %s 实际值 %r 不在 [%r, %r+POLL_S]" % (mod.__name__, i, key, act, intended, intended)
            # 设备侧动作的先后（每轮）：text → turn_start → tap SEND → answer_complete
            text_call = ("input", "text", prompt.replace(" ", "%s"))
            assert fake.calls.count(text_call) == 3, "%s: input text 应打 3 次，实得 %d" % (
                mod.__name__, fake.calls.count(text_call))
            for n in range(1, 4):
                t_text = [k for k, c in enumerate(fake.calls) if c == text_call][n - 1]
                t_start = fake.calls.index(("log", "-t", "AnebE4MARK", "E4MARK kind=turn_start n=%d" % n))
                t_done = fake.calls.index(("log", "-t", "AnebE4MARK", "E4MARK kind=answer_complete n=%d" % n))
                t_send = t_start + 1
                assert fake.calls[t_send] == ("input", "tap", *mod.TAP_SEND), \
                    "%s: 轮 %d turn_start 之后紧跟的不是 tap SEND：%r" % (mod.__name__, n, fake.calls[t_send])
                assert t_text < t_start < t_send < t_done, \
                    "%s: 轮 %d 先后乱了 text=%d start=%d send=%d done=%d" % (
                        mod.__name__, n, t_text, t_start, t_send, t_done)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def test_non_ascii_prompt_refused_before_any_device_action():
    """A-1 ④：非 ASCII 提示词 → AssertionError，且在**任何**设备动作与账目落盘之前。"""
    for mod in DRIVERS:
        tmp = tempfile.mkdtemp(prefix="drv_")
        try:
            out_dir = os.path.join(tmp, "cell_x")
            fake = _FakeSH(_window_dump(mod.PKG), AWAKE)
            argv = ["drive_cell.py", out_dir, "1", "你好 world", "0.1", "0.1"]
            with _env("ANEB_SERIAL", SERIAL), _swap(mod, "SH", fake), _swap(mod, "time", _FakeClock()), \
                    _swap(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                try:
                    mod.main()
                except AssertionError:
                    pass
                else:
                    raise AssertionError("%s: 非 ASCII prompt 没被拒" % mod.__name__)
            assert fake.calls == [], "%s: 拒收前不该有任何设备动作：%r" % (mod.__name__, fake.calls)
            assert not os.path.exists(os.path.join(tmp, "cell_x_driver_timing.jsonl")), \
                "%s: 拒收前不该落账目" % mod.__name__
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ── STOP 文案与源码级机检（把 §7.1 的三条 grep 验收钉进套件） ───────────────────
def test_stop_message_names_pkg_and_sources_pass_grep_gates():
    """require_focus 的 STOP 文案必须含 PKG 变量值；ds 源码零「豆包」；两只源码零 `PKG in sh`。"""
    for mod in DRIVERS:
        with _swap(mod, "SH", _FakeSH(_window_dump("com.other.app"), AWAKE)):
            try:
                mod.require_focus("轮 1 开头")
            except SystemExit as e:
                msg = str(e)
            else:
                raise AssertionError("%s: 前台不对时 require_focus 没停" % mod.__name__)
        assert mod.PKG in msg and "轮 1 开头" in msg, "%s: STOP 文案=%r" % (mod.__name__, msg)
        assert "PKG in sh" not in _source(mod), "%s: 源码仍含子串判据 `PKG in sh`" % mod.__name__
    assert "豆包" not in _source(dcd), "drive_cell_ds.py 源码仍含「豆包」字面"
    assert "豆包" not in msg, "ds 版 STOP 文案仍含「豆包」"


def test_twins_differ_only_in_pkg_and_tap_lines():
    """两只驱动器在模块 docstring 之后须逐字一致，差异行只许是 PKG = / TAP_ 那五行。

    只比 docstring 之后：头部 prose 本就允许描述各自坐标的来历。代码段哪怕差一个字符
    ——尤其是时序、标记先后、SH 调用点——就是签名分叉，判读侧的偏移会静默漂。
    """
    bodies = []
    for mod in DRIVERS:
        src = _source(mod)
        doc_end = ast.parse(src).body[0].end_lineno       # 模块 docstring 的末行
        bodies.append(src.split("\n")[doc_end:])
    changed = [ln for ln in difflib.unified_diff(bodies[0], bodies[1], lineterm="", n=0)
               if (ln.startswith("+") or ln.startswith("-")) and not ln.startswith(("+++", "---"))]
    assert changed, "两只代码段完全相同——PKG/TAP_ 至少该不同，比较本身可能没比到东西"
    bad = [ln for ln in changed if not (ln[1:].startswith("PKG = ") or ln[1:].startswith("TAP_"))]
    assert not bad, "孪生代码段出现 PKG/TAP_ 之外的差异行：\n%s" % "\n".join(bad)
    assert len(changed) == 10, "PKG+四 TAP_ 各两侧应恰 10 行差异，实得 %d" % len(changed)
