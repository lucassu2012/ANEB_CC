# -*- coding: utf-8 -*-
"""部署到管理员目录的那两个 ps1，必须与仓里同名文件**逐字节一致**（D-841 后半）。

🔴 **为什么这道门是安全关键**：`bin\\shaper.ps1` 经 `/RL HIGHEST` **提权**运行，而它里面那张
菜单（`$MENU`）是**整条链上唯一的安全边界**（D-840）。**一条承重的安全控制只活在磁盘上、
无版本、改了没有任何东西会报**——那正是 D-841 立此守卫的理由，与 D-822「一份没有守卫校验的
完整性记录不是完整性记录」同形。

⚠ **判据取字节，不取行**（D-829 实测教训）：`git diff` 是关于**行**的，它**既会漏掉真的字节
改动**（双 CR 行尾那次每行少一字节而 diff 一个字都不显示），**也会虚报整片改动**（blob 是 LF、
盘上是 CRLF 时 14 行全报不同）。所以这里直接比原始字节。

⚠ **部署与仓内的搬运方式也被这条判据钉住**：D-842 要求部署用 `Copy-Item` **按字节搬运**而非
重新创建文件——因为无 BOM 的 ps1 含中文注释时，PS 5.1 下 `param()` 绑定会**静默失效**
（脚本照跑、命名参数不绑、回落默认、不报错，连 `Tokenize` 都过）。**重建文件极易丢 BOM，
而丢了不报错。** 本门比字节，顺带把 BOM 一起钉住。

⚠ **没部署的机器上本门 SKIP，而 SKIP 会被跑器显名印出来**——「没跑」不许伪装成「过了」。
守的是「**部署了就必须一致**」，不是「必须部署」。
"""
import hashlib
import io
import os

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_SHAPER = os.path.join(SCRIPTS, "shaper")

# 部署目标（D-846 订正后的落点：回 bin/，与 profiles/ 并列，脚本的 ArgsFile 推导才成立）。
DEPLOY_DIR = r"E:\tools\aneb-shaper\bin"
PAIRS = ("shaper.ps1", "shaper_stop.ps1")


def _read(path):
    with io.open(path, "rb") as fh:
        return fh.read()


def compare_bytes(a, b):
    """→ (相同?, 诊断串)。**按字节**比；不同时顺带判「是否仅行尾差异」帮人定位成因。

    ⚠ 「仅行尾差异」**也判不同** —— 部署要求按字节搬运（D-842），行尾变了就说明
    不是 `Copy-Item` 搬过去的，而那条路径正是丢 BOM / 丢字节的那条。
    """
    if a == b:
        return True, "逐字节相同"
    diag = ["字节数 仓内=%d 部署=%d" % (len(a), len(b)),
            "sha256 仓内=%s… 部署=%s…" % (hashlib.sha256(a).hexdigest()[:12],
                                          hashlib.sha256(b).hexdigest()[:12])]
    n = min(len(a), len(b))
    first = next((i for i in range(n) if a[i] != b[i]), n)
    diag.append("首处差异偏移=%d" % first)
    # 归一行尾后再比一次：只为把「成因」说清楚，不改变判定
    na = a.replace(b"\r\n", b"\n")
    nb = b.replace(b"\r\n", b"\n")
    diag.append("归一行尾后相同=%s（True ⇒ 成因是行尾，不是内容；但仍判不同，见 docstring）"
                % (na == nb))
    diag.append("BOM 仓内=%s 部署=%s" % (a.startswith(b"\xef\xbb\xbf"),
                                         b.startswith(b"\xef\xbb\xbf")))
    return False, "；".join(diag)


def test_deployed_shaper_scripts_match_the_repo_byte_for_byte():
    if not os.path.isdir(DEPLOY_DIR):
        import pytest
        pytest.skip("本机无部署目录 %s ⇒ 本门不适用（守的是「部署了就必须一致」，"
                    "不是「必须部署」）；合成对照那几条已跑" % DEPLOY_DIR)

    problems = []
    checked = 0
    for name in PAIRS:
        src = os.path.join(REPO_SHAPER, name)
        dst = os.path.join(DEPLOY_DIR, name)
        assert os.path.isfile(src), "仓内缺 %s —— 先怀疑是不是挪走/改名了" % src
        if not os.path.isfile(dst):
            problems.append("%s：部署目录里没有这个文件（部署不完整）" % name)
            continue
        a, b = _read(src), _read(dst)
        # 非空自证：两个空文件也「相同」，那种绿不说明任何事
        assert a, "%s 仓内读到 0 字节 —— 先怀疑量法坏了" % name
        same, diag = compare_bytes(a, b)
        checked += 1
        if not same:
            problems.append("%s：%s" % (name, diag))

    assert checked > 0 or problems, (
        "一个文件都没比到 —— 本条空跑了，等于没有守卫")
    assert not problems, (
        "部署的脚本与仓里对不上：\n  " + "\n  ".join(problems)
        + "\n⚠ `bin\\shaper.ps1` 跑在 /RL HIGHEST 里、其菜单是这条链唯一的安全边界（D-840）。"
        + "\n修法：用 `Copy-Item` 从仓内**按字节**重新部署（D-842：重建文件会丢 BOM 且不报错），"
          "**不要反向把部署那份拷回仓里** —— 仓里那份才是受评审的源。")


# ------------------------------------------------------------------ 合成对照（永远会跑）
def test_a_single_flipped_byte_is_caught():
    """阳性对照：改一个字节必须判不同。**没有它，一道恒真的门与一道好门长得一样。**"""
    a = b"\xef\xbb\xbfparam()\r\n# hi\r\n"
    same, _ = compare_bytes(a, a)
    assert same
    b = bytearray(a)
    b[-3] ^= 0x01
    same, diag = compare_bytes(a, bytes(b))
    assert not same and "首处差异偏移" in diag, diag


def test_a_lost_bom_is_caught_and_named():
    """丢 BOM 必须被逮住并**点名** —— 那正是 D-842 那个静默失效的入口。"""
    a = b"\xef\xbb\xbfparam([string]$X)\r\n"
    b = a[3:]                      # 重建文件时最常见的丢法
    same, diag = compare_bytes(a, b)
    assert not same, "丢了 BOM 却判成相同"
    assert "BOM 仓内=True 部署=False" in diag, diag


def test_eol_only_difference_is_still_a_difference_but_is_named_as_such():
    """仅行尾不同：**仍判不同**（没按字节搬运），但诊断串要说清成因，免得被当成内容被改。"""
    a = b"param()\r\nWrite-Output 1\r\n"
    b = a.replace(b"\r\n", b"\n")
    same, diag = compare_bytes(a, b)
    assert not same
    assert "归一行尾后相同=True" in diag, diag
