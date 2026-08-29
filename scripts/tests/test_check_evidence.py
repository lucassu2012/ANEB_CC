# -*- coding: utf-8 -*-
"""`check_evidence.py` 的反例电池——每条检查都要**造得出红**才算数。

夹具一律合成，**不对真树下断言**：真树断言会因别的会话的改动把本套件推红
（共享树里「跑门撞在飞态」那个坑），而守卫对真树的判定归 `verify_all` 跑。
分工：这里证明「它能抓」，`verify_all` 证明「它现在看的是真东西」。

**不用 pytest fixture**（`tmp_path`/`monkeypatch`/`raises`）：跑门的是
`scripts/tests/run_all.py`，它**直接调用函数**，带 fixture 参数的测试在那边
一律 TypeError。初版用了 fixture、pytest 下 18/18 全绿，而门那侧 17 条全红
——**「绿」是拿门不用的那只 runner 量的**。房子里既有测试全用 `tempfile`
显式造目录，正是为此；照更严的那只写，两边都能跑。
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_evidence as ce                                    # noqa: E402

README = """# evidence/

## 规则

1. **四态**：任何验收检查只允许 `PASS / FAIL / NOT_EXECUTED / BLOCKED_EXTERNAL` 四种状态。
2. **PASS 必须有证据**：命令 + 原始输出 + 产物文件落盘。
"""

LEGEND = "PASS / FAIL / NOT_EXECUTED / BLOCKED_EXTERNAL"


@contextlib.contextmanager
def _tmp():
    d = tempfile.mkdtemp()
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@contextlib.contextmanager
def _patched(**kw):
    """临时改模块属性；**还原进 finally**（D-321：会污染工作区的夹具比测试失败危险）。"""
    old = dict((k, getattr(ce, k)) for k in kw)
    for k, v in kw.items():
        setattr(ce, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(ce, k, v)


def _check(cid="C1", state="PASS", files=("e.log",), date="2026-08-29", **kw):
    c = {"check_id": cid, "state": state, "command": "cmd",
         "evidence_files": list(files), "date": date}
    c.update(kw)
    return c


def _tree(tmp, checks=None, legend=LEGEND, readme=README, phase="phase1",
          make_files=True):
    """造一棵最小 evidence 树，返回根目录。"""
    io.open(os.path.join(tmp, "README.md"), "w", encoding="utf-8").write(readme)
    d = os.path.join(tmp, phase)
    if not os.path.isdir(d):
        os.makedirs(d)
    checks = [_check()] if checks is None else checks
    doc = {"phase": phase, "updated": "2026-08-29", "legend": legend,
           "checks": checks}
    io.open(os.path.join(d, "STATUS.json"), "w", encoding="utf-8").write(
        json.dumps(doc, ensure_ascii=False))
    if make_files:
        for c in checks:
            for f in c.get("evidence_files") or []:
                io.open(os.path.join(d, f), "w", encoding="utf-8").write("x")
    return tmp


def test_a_clean_tree_passes():
    """先证阴性：干净树必须 0 违规——否则后面每条红都可能是噪声。

    （本条曾咬出一个真缺陷：冻结豁免泄漏到别的根，见最后一条。）
    """
    with _tmp() as t:
        bad, stale = ce.run(_tree(t))
    assert bad == [] and stale == [], (bad, stale)


def test_pass_without_evidence_is_caught():
    """#4 的正主：`PASS` + 空 `evidence_files`。

    反例证伪：去掉 check_pass_has_evidence，本条即绿。
    """
    with _tmp() as t:
        bad, _ = ce.run(_tree(t, [_check(files=())]))
    assert any("evidence_files 为空" in b for b in bad), bad


def test_a_non_pass_state_may_have_no_evidence():
    """假阳性先杀：规则 2 只管 `PASS`——`NOT_EXECUTED` 空证据是**正常**的。

    这条比上一条更要紧：一个见谁都红的守卫会被关掉。
    """
    with _tmp() as t:
        bad, _ = ce.run(_tree(t, [_check(state="NOT_EXECUTED", files=())]))
    assert bad == [], bad


def test_a_dangling_evidence_file_is_caught():
    """列了证据但文件不在盘上——比空列表更危险，因为它长得像合规。"""
    with _tmp() as t:
        bad, _ = ce.run(_tree(t, [_check(files=("gone.log",))],
                              make_files=False))
    assert any("不在盘上" in b for b in bad), bad


def test_a_state_outside_the_four_is_caught():
    """#6：四态之外的状态词（例：把 SKIPPED 混进来）。"""
    with _tmp() as t:
        bad, _ = ce.run(_tree(t, [_check(state="SKIPPED")]))
    assert any("不在四态内" in b for b in bad), bad


def test_a_missing_required_key_is_caught():
    """#6：必填字段缺失。"""
    c = _check()
    del c["command"]
    with _tmp() as t:
        bad, _ = ce.run(_tree(t, [c]))
    assert any("缺必填字段 `command`" in b for b in bad), bad


def test_a_malformed_date_is_caught():
    """#6：`date` 必须 YYYY-MM-DD——日期格式散掉，按日对账就无从做起。"""
    with _tmp() as t:
        bad, _ = ce.run(_tree(t, [_check(date="2026/08/29")]))
    assert any("非 YYYY-MM-DD" in b for b in bad), bad


def test_a_legend_that_disagrees_with_the_readme_is_caught():
    """legend 与 README 规则 1 分叉——**这正是我不硬编码四态的理由**：
    判据只有一个源，其余都是受检派生物。

    反例证伪：把 states 改回模块级常量，本条永远绿（两边都是同一份抄的）。
    """
    with _tmp() as t:
        bad, _ = ce.run(_tree(t, legend="PASS / FAIL / SKIPPED"))
    assert any("legend 与 README 规则 1 不一致" in b for b in bad), bad


def test_a_readme_without_the_rule_aborts_instead_of_passing():
    """判据缺失必须**报错而不是放行**（D-511 fail-closed）。

    一条找不到自己判据的检查没有资格说「通过」——那是 D-532「门从没跑过
    却一直报 PASS」的同一个形状。
    """
    with _tmp() as t:
        root = _tree(t, readme="# evidence/\n\n没有规则节。\n")
        try:
            ce.run(root)
        except RuntimeError:
            return
    raise AssertionError("判据缺失时必须抛 RuntimeError，不得放行")


def test_an_unreadable_status_file_says_so_instead_of_being_skipped():
    """坏掉的 STATUS.json 要喊出来——静默跳过等于把「查不了」印成「没问题」。"""
    with _tmp() as t:
        root = _tree(t)
        io.open(os.path.join(root, "phase1", "STATUS.json"), "w",
                encoding="utf-8").write("{broken")
        bad, _ = ce.run(root)
    assert any("读不了" in b for b in bad), bad


def test_a_date_package_without_readme_is_caught():
    """#7：日期包必须自带 README。"""
    with _tmp() as t:
        root = _tree(t)
        os.makedirs(os.path.join(root, "newbatch_20260830"))
        bad, _ = ce.run(root)
    assert any("是日期包但没有 README.md" in b for b in bad), bad


def test_a_non_date_directory_needs_no_readme():
    """假阳性先杀：`phase1/` 这类阶段目录不是日期包，不该被要求 README。"""
    with _tmp() as t:
        bad, _ = ce.run(_tree(t))
    assert not any("日期包" in b for b in bad), bad


def test_build_in_a_directory_name_is_caught():
    """#14：命名禁区 `build`（会被构建产物排除规则误伤）。"""
    with _tmp() as t:
        root = _tree(t)
        os.makedirs(os.path.join(root, "phase1", "buildout"))
        bad, _ = ce.run(root)
    assert any("命名含 `build`" in b for b in bad), bad


def test_a_non_utf8_log_is_caught():
    """#13：日志编码——一份解不开的日志与正常日志在目录列表里长得一样。"""
    with _tmp() as t:
        root = _tree(t)
        with open(os.path.join(root, "phase1", "gbk.log"), "wb") as fh:
            fh.write(b"\xc4\xe3\xba\xc3\xff\xfe")        # 非法 UTF-8 序列
        bad, _ = ce.run(root)
    assert any("不是 utf-8" in b for b in bad), bad


def test_a_legacy_exemption_that_is_no_longer_needed_goes_stale():
    """豁免必须**会自己过期**（D-275）：债清偿后清单里那条要反过来报红。

    否则一份冻结清单会永远留着，把「已经修好的」和「还没修的」混在一起，
    而**读者无从知道它到底还欠几条**。
    反例证伪：删掉 stale 分支，本条即绿。
    """
    with _tmp() as t:
        root = _tree(t)                               # C1 是 PASS 且**有**证据
        key = "phase1/STATUS.json"        # 键相对被扫根，与路径拼法无关
        with _patched(LEGACY_PASS_WITHOUT_EVIDENCE={key: ("C1",)},
                      LEGACY_ROOT=root):
            bad, stale = ce.run(root)
    assert bad == [], bad
    assert any("已不再违规" in s for s in stale), stale


def test_stale_exemptions_make_the_cli_exit_nonzero():
    """过期豁免也要让退出码非零——只印不红等于没说（本仓反复咬中的形状）。"""
    with _tmp() as t:
        root = _tree(t)
        key = "phase1/STATUS.json"        # 键相对被扫根，与路径拼法无关
        with _patched(LEGACY_PASS_WITHOUT_EVIDENCE={key: ("C1",)},
                      LEGACY_ROOT=root):
            rc = ce.main(["--root", root])
    assert rc == 1, rc


def test_a_missing_rule_aborts_with_code_2_not_a_silent_pass():
    """判据缺失的退出码要与「有违规」区分开：2＝没法判，1＝判了有问题。"""
    with _tmp() as t:
        io.open(os.path.join(t, "README.md"), "w",
                encoding="utf-8").write("# 没有规则节\n")
        rc = ce.main(["--root", t])
    assert rc == 2, rc


def test_the_frozen_lists_never_leak_into_another_root():
    """冻结豁免**有归属**：换一棵树扫，它既不赦免谁，也不宣告谁还清了。

    此坑由本文件的阴性对照测试咬出——干净合成树曾报出 7 条假过期豁免，因为
    「那边压根没有这些目录」被当成了「债已清偿」。两者在输出上一模一样，而
    处置相反（一个该去删清单、一个什么都不该做）。
    反例证伪：把 `_legacy_applies` 恒返回 True，本条即红。
    """
    with _tmp() as t:
        root = _tree(t)
        os.makedirs(os.path.join(root, "m2_rerun_20260819"))  # 与真树重名
        bad, stale = ce.run(root)
    assert stale == [], "别的根不该产生过期豁免：%r" % (stale,)
    assert any("m2_rerun_20260819" in b for b in bad), \
        "别的根里的同名目录不该被真树的豁免赦免：%r" % (bad,)


def test_absolute_and_relative_roots_give_the_same_verdict():
    """同一棵树，`--root evidence` 与 `--root <绝对路径>` 必须**同答案**。

    此坑实发：门传绝对路径、我手跑传相对，冻结清单的键是仓相对的，于是
    **同一个脚本手跑 0 违规、门 7 违规**——而两边都自称跑过了。豁免的身份
    不该依赖路径怎么拼（与「豁免不该泄漏到别的根」是同一条要求的两半）。
    反例证伪：把清单键换回含 `evidence/` 前缀的形式，本条即红。
    """
    with _tmp() as t:
        root = _tree(t, [_check(files=())])           # 造一条 PASS 无证据
        key = "phase1/STATUS.json"
        with _patched(LEGACY_PASS_WITHOUT_EVIDENCE={key: ("C1",)},
                      LEGACY_ROOT=root):
            # 两种拼法解析到同一目录：直给，与绕一层 `..`。
            # （初版想用 cwd 相对路径，但 tmpdir 在 C:、cwd 在 E:，Windows
            #  跨盘算不出 relpath——**量法本身不成立**，换等价拼法即可。）
            other = os.path.join(root, "phase1", os.pardir)
            a, _ = ce.run(os.path.abspath(root))
            b, _ = ce.run(other)
    assert a == [] and b == [], (a, b)
