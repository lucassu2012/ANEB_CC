# -*- coding: utf-8 -*-
"""`evidence/` 规则的机器执行面（承 T82 §9.2 的 #4/#6/#7/#13/#14）。

`evidence/README.md` 立了六条规则，此前**一条都没有守卫**——「文档写着规则、
机器本可执行、却没执行」正是治理债的定义。本脚本把其中五条接上，外加一条
README 蕴含却没写死的（`evidence_files` 列的文件必须真在盘上——**「有证据」而
文件名悬空，与「没证据」结论等价，却在读者眼里长得像合规**）。

**为什么是一个脚本而不是五个**：五条同源（全出自同一份 README）。拆开会让
「evidence 的规则到底有没有被执行」这个问题**没有单一答案**——而这正是它们
当初一起漏掉的原因。

**四态判据从 README 解析，不在这里硬编码**：该词汇全仓已有三个源（README 规则
1、`e1_analyze`/`e234_common` 常量、各 `STATUS.json` 的 `legend`）。再抄一份就是
第四个会各自漂的副本（§2.14）。这里改为**从 README 读出判据、再拿它去核 legend
与每个 state**，副本因此变成受检派生物。README 若改到解析不出来，**守卫报错而
不是放行**（fail-closed，D-511）——一条找不到判据的检查没有资格说「通过」。

**豁免刻意做成会自己过期的**（D-275「让豁免天然落选」）：历史违规冻结成显式
清单，清单**只能缩不能长**——某条一旦被清偿，它在清单里就成了**过期豁免**、
反过来让守卫红，逼人把它删掉。**新违规没有任何豁免通道**，因为一个好用的
免责通道就是在邀请别人用它。

用法：
    python scripts/check_evidence.py          # 全查；有违规 exit 1
    python scripts/check_evidence.py --root evidence
"""
import argparse
import glob
import io
import json
import os
import re
import sys

README_NAME = "README.md"

# 「状态文件」节写死的字段集。
REQUIRED_KEYS = ("check_id", "state", "command", "evidence_files", "date")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 日期包＝`<战役>_<YYYYMMDD>[_后缀]/`（README「目录形态」节，2026-07-31 明确）。
DATE_PKG_RE = re.compile(r"_(20\d{6})(?:_|$)")

# README 规则 1 里那串反引号包着的状态表：`PASS / FAIL / ... / ...`。
_STATES_IN_README = re.compile(r"`([A-Z_]+(?:\s*/\s*[A-Z_]+){2,})`")

# 从任意 legend 串里取大写状态词（phase0 的 legend 后面还跟着一句中文说明）。
_STATE_TOKEN = re.compile(r"[A-Z][A-Z_]{2,}")

# ---- 冻结的历史违规：**只能缩不能长** ---------------------------------------
# 判据（2026-08-29 实查）：07-12 那批只记了 `command` 与分支提交号（如
# `p1/scoring@d726ec6`），产物未留存、事后不可复原。**不伪造证据**，也**不降级
# 状态**——四态里没有「PASS 但证据没留」这一态，硬塞就是违规则 1。故如实冻结，
# 让这笔债**可见且可数**。phase3 为 0：实践后来自己变好了，这是历史断点不是常态。
# 键是**相对被扫根**的路径，不是仓相对——否则 `--root evidence` 与
# `--root E:\...\evidence` 会得出不同结果（门传绝对路径，我手跑传相对，
# 于是同一个脚本两种答案：手跑 0 违规、门 7 违规）。**豁免的身份不该依赖
# 路径怎么拼**，这与「豁免不该泄漏到别的根」是同一条要求的两半。
LEGACY_PASS_WITHOUT_EVIDENCE = {
    "phase0/STATUS.json": ("P0-C07-review-closure",),
    "phase1/STATUS.json": ("P1-C01-scoring-engine",
                           "P1-C02-netguard-radio",
                           "P1-C03-server-contract-inject",
                           "P1-C04-merged-tree-verify"),
    "phase2/STATUS.json": ("P2-C01-h3-server", "P2-C03-aqs-v02"),
}

# 同上，针对「日期包自带 README」。23 个日期包里 16 个已有——**规则是被实践的**，
# 这 7 个是债；补 README 要知道那批证据的内容与口径，不是本脚本能替人写的。
LEGACY_DATE_PKG_WITHOUT_README = (
    "acceptance_20260820",
    "e1_realdevice_20260802",
    "e1_realdevice_20260802_run2",
    "m2_rerun_20260819",
    "spec4_worktree_drill_20260829",
    "t39_report_chain_rehearsal_20260803",
    "t46_full_corpus_analysis_20260804",
)


_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGACY_ROOT = os.path.join(_REPO, "evidence")


def _norm(p):
    return p.replace(os.sep, "/")


def _legacy_applies(root):
    """冻结清单**只对真 `evidence/` 树生效**。

    它记的是**这一棵树的历史**，不是一条通用规则——拿去套别的根（测试夹具、
    别的仓）会把「那边压根没有这些目录」误报成「债已清偿」。豁免是**有归属的
    事实**：归属不对，它既不该赦免谁，也不该宣告谁还清了。
    （此坑由本模块自己的阴性对照测试咬出：干净合成树报出 7 条假过期豁免。）
    """
    try:
        return os.path.samefile(root, LEGACY_ROOT)
    except OSError:
        return False


def four_states(root):
    """从 `evidence/README.md` 规则 1 解出四态。解不出就抛——不猜、不兜底。"""
    p = os.path.join(root, README_NAME)
    with io.open(p, encoding="utf-8") as fh:
        for line in fh:
            if "四态" not in line:
                continue
            m = _STATES_IN_README.search(line)
            if m:
                return tuple(s.strip() for s in m.group(1).split("/"))
    raise RuntimeError(
        "%s 里解不出规则 1 的状态表——守卫拒绝在判据缺失时放行（D-511）" % _norm(p))


def load_status_files(root):
    """返回 [(归一化路径, dict 或 None, 读取错误)]；读不了要说出来，不静默跳过。"""
    out = []
    for p in sorted(glob.glob(os.path.join(root, "**", "STATUS.json"),
                              recursive=True)):
        try:
            with io.open(p, encoding="utf-8") as fh:
                out.append((_norm(p), json.load(fh), None))
        except (OSError, ValueError) as e:
            out.append((_norm(p), None, "%s: %s" % (type(e).__name__, e)))
    return out


def check_status_schema(status_files, states):
    """#6：四态枚举 + 必填字段 + 日期格式 + legend 与 README 一致。"""
    bad = []
    for path, doc, err in status_files:
        if err:
            bad.append("%s 读不了：%s" % (path, err))
            continue
        legend = doc.get("legend")
        if legend is None:
            bad.append("%s 缺 legend" % path)
        else:
            got = set(_STATE_TOKEN.findall(legend))
            if got != set(states):
                bad.append("%s 的 legend 与 README 规则 1 不一致："
                           "legend=%s README=%s"
                           % (path, sorted(got), sorted(states)))
        checks = doc.get("checks")
        if not isinstance(checks, list):
            bad.append("%s 缺 checks 数组" % path)
            continue
        for i, c in enumerate(checks):
            cid = c.get("check_id") or "#%d(无 check_id)" % i
            for k in REQUIRED_KEYS:
                if k not in c:
                    bad.append("%s %s 缺必填字段 `%s`" % (path, cid, k))
            st = c.get("state")
            if st is not None and st not in states:
                bad.append("%s %s 状态 `%s` 不在四态内（%s）"
                           % (path, cid, st, "/".join(states)))
            d = c.get("date")
            if d is not None and not DATE_RE.match(str(d)):
                bad.append("%s %s date `%s` 非 YYYY-MM-DD" % (path, cid, d))
    return bad


def check_pass_has_evidence(status_files, root, legacy_on=True):
    """#4：`PASS` 必须有证据（README 规则 2）。返回 (违规, 过期豁免)。

    过期豁免单独返回而不是并进违规——两者处置相反：一个要去补证据，另一个是
    **好消息**（债已清偿），只需把名字从冻结清单里删掉。混在一起会让读者
    把「有人还清了债」读成「又出了新违规」。
    """
    bad, stale = [], []
    for path, doc, err in status_files:
        if err or not isinstance(doc.get("checks"), list):
            continue                      # schema 检查已负责报它
        rel = _norm(os.path.relpath(path, root))
        legacy = set(LEGACY_PASS_WITHOUT_EVIDENCE.get(rel, ())) \
            if legacy_on else set()
        seen = set()
        for c in doc["checks"]:
            cid = c.get("check_id")
            if c.get("state") != "PASS" or c.get("evidence_files"):
                continue
            seen.add(cid)
            if cid not in legacy:
                bad.append("%s %s 记 PASS 但 evidence_files 为空"
                           "（README 规则 2：PASS 必须有证据）" % (path, cid))
        for cid in sorted(legacy - seen):
            stale.append("%s %s 已不再违规，请从 LEGACY_PASS_WITHOUT_EVIDENCE "
                         "删掉该条（豁免不得长留）" % (path, cid))
    return bad, stale


def check_evidence_files_exist(status_files):
    """README 规则 2 蕴含项：列出的证据文件必须真在盘上。

    2026-08-29 实测 65 列 0 悬空——本条是**防回归**，不是当下的债。
    """
    bad = []
    for path, doc, err in status_files:
        if err or not isinstance(doc.get("checks"), list):
            continue
        base = os.path.dirname(path)
        for c in doc["checks"]:
            for f in c.get("evidence_files") or []:
                if not os.path.exists(os.path.join(base, f)):
                    bad.append("%s %s 的证据文件不在盘上：%s"
                               % (path, c.get("check_id"), f))
    return bad


def check_date_package_readme(root, legacy_on=True):
    """#7：日期包 `<战役>_<YYYYMMDD>/` 必须自带 README。返回 (违规, 过期豁免)。"""
    bad, stale = [], []
    seen = set()
    exempt = set(LEGACY_DATE_PKG_WITHOUT_README) if legacy_on else set()
    try:
        names = sorted(os.listdir(root))
    except OSError as e:
        return ["%s 读不了：%s" % (_norm(root), e)], []
    for name in names:
        d = os.path.join(root, name)
        if not os.path.isdir(d) or not DATE_PKG_RE.search(name):
            continue
        if os.path.isfile(os.path.join(d, README_NAME)):
            continue
        seen.add(name)
        if name not in exempt:
            bad.append("%s/ 是日期包但没有 README.md"
                       "（README「目录形态」节：每个包自带 README）" % _norm(d))
    for name in sorted(exempt - seen):
        stale.append("%s 已补上 README（或已不存在），请从 "
                     "LEGACY_DATE_PKG_WITHOUT_README 删掉" % name)
    return bad, stale


def check_no_build_in_names(root):
    """#14：命名禁区 `build`（README 规则 4——防被构建产物排除规则误伤）。"""
    bad = []
    for cur, dirs, _files in os.walk(root):
        for d in dirs:
            if "build" in d.lower():
                bad.append("%s 命名含 `build`（README 规则 4：命名禁区）"
                           % _norm(os.path.join(cur, d)))
    return bad


def check_log_encoding(root):
    """#13：日志一律 utf-8（README 规则 5——失败-修复链必须可审计）。

    一份解不开的日志＝一条读不了的证据，而它**在目录列表里与正常日志一模一样**。
    """
    bad = []
    for p in sorted(glob.glob(os.path.join(root, "**", "*.log"), recursive=True)):
        try:
            with io.open(p, encoding="utf-8") as fh:
                fh.read()
        except UnicodeDecodeError as e:
            bad.append("%s 不是 utf-8（%s）" % (_norm(p), e.reason))
        except OSError as e:
            bad.append("%s 读不了：%s" % (_norm(p), e))
    return bad


def run(root, legacy_on=None):
    """跑全部检查，返回 (违规列表, 过期豁免列表)。

    `legacy_on=None` 时自动判定：**只有真 `evidence/` 树才享冻结豁免**
    （见 `_legacy_applies`）。测试可显式置 True 来演练豁免与过期两条路径。
    """
    if legacy_on is None:
        legacy_on = _legacy_applies(root)
    states = four_states(root)
    sf = load_status_files(root)
    pe_bad, pe_stale = check_pass_has_evidence(sf, root, legacy_on)
    dp_bad, dp_stale = check_date_package_readme(root, legacy_on)
    bad = (check_status_schema(sf, states) + pe_bad
           + check_evidence_files_exist(sf) + dp_bad
           + check_no_build_in_names(root) + check_log_encoding(root))
    return bad, pe_stale + dp_stale


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="evidence/ 规则守卫（T82 §9.2 #4/#6/#7/#13/#14）")
    ap.add_argument("--root", default="evidence")
    a = ap.parse_args(argv)
    try:
        bad, stale = run(a.root)
    except RuntimeError as e:
        print("evidence guard: ABORTED %s" % e)
        return 2
    debt = sum(len(v) for v in LEGACY_PASS_WITHOUT_EVIDENCE.values()) \
        + len(LEGACY_DATE_PKG_WITHOUT_README)
    # 债要**印出来**，不能只体现在「没红」里：一个静默的豁免清单等于把债藏起来。
    print("evidence guard: violations=%d stale_exemptions=%d frozen_debt=%d"
          % (len(bad), len(stale), debt))
    for line in bad:
        print("  VIOLATION " + line)
    for line in stale:
        print("  STALE_EXEMPTION " + line)
    return 1 if (bad or stale) else 0


if __name__ == "__main__":
    sys.exit(main())
