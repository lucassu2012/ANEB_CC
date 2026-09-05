# -*- coding: utf-8 -*-
"""自主操作驱动器（D-587 授权面）。每轮：新对话 → 输入 → 发送 → 等答完 → 标记 → 静置。

⚠ 入仓理由（D-621 驱动器入仓令）：**这个脚本决定 `turn_start` 标记与打字斜坡的先后**，
而那个偏移是判读侧归轮的必需品，且**会随本脚本改动而静默改变**。它此前只活在会话的
scratchpad 里 ⇒ 「每格记驱动器提交哈希」那条规矩**没有可记的东西**。现入仓以使其成立。

🔴 **首版不可恢复**：DW-20260830-01 的 `wifi_f1` / `wifi_f2` / `cell_f1` 三格用的是**首版**
（顺序为「先打标记、后打字」，实测偏移 +1.8～+2.6s），而**首版已被本文件覆盖、没有副本**。
⇒ 那三格只能靠 `evidence/doubao_wave0_20260830/README.md` §15.4b 的**实测签名**识别。
**这正是「入仓来晚了」的代价，也是这条规矩最强的论据。**

⚠ 使用前必读：**下面四个 TAP_ 坐标是 P40（1200×2640）上豆包 14.7.0 的实测值**，
换设备、换 App、换版本都必须重量（用 screencap 人工核，**不要用 `uiautomator dump`**——
它会把整屏文本落盘，违反「只计长不读内容」红线）。

三条硬规矩，都是 2026-08-30 这一窗踩出来的：

  1. 绝不按 BACK 关抽屉 —— 它会退出 App，随后每一次盲点都精确地落在别的应用上，
     而 `input tap` 对任何坐标都成功，全程零报错。
  2. 每一段盲点序列之前复核 mCurrentFocus；前台不是 PKG（或屏未醒）就抛错停住。
  3. **记实际值，不记意图值。** 曾把 ANSWER_WAIT_S 写成 17.4，而等待循环按 1.0s 轮询，
     实际跑出 18.2 —— 一个「精确的常量」被一个粗的循环悄悄改掉了，而锚格正靠它可比。
     粒度收细只减小误差、不消灭它；能消灭的只有「逐轮把实际值落盘」这条纪律。

答完判据＝**固定等待**，不用 ROI。实证：用 ROI「跳变后连续 N 个静止样本」判答完，
在 F2 上会把**思考静默**读成答完 —— 六轮全部在 6–11s 宣布完成而实际约 50s/轮，
于是每轮都被下一轮的「新对话」拦腰截断，且零报错。ROI (400,1800,400,200) 是按 F1
短答选的，落在输入框/键盘带上，它跳的是打字与键盘收起，不是回答在流式。
⇒ **宁可标晚，绝不标早**：标早截断真数据且不报错，标晚只多算一段空闲。
"""
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
# ⚠ 本文件与其余八只不同：它顶层不 import `e234_common`，故 `tools/e1` 不在
# sys.path 上 —— 批量接线时按「结构一致」假设插入，**命令行一跑当场 ImportError**，
# 而测试套件永远抓不到它（测试是 import 模块，不是跑 CLI）。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "e1"))
import e1_io                    # noqa: E402  (D-648③ 输出编码自锁)

PKG = "com.larus.nova"
TAP_MENU = ("90", "243")        # ☰
TAP_NEW = ("923", "244")        # ✎ 新对话（只在抽屉已开时有效；单独点它是电话图标）
TAP_INPUT = ("436", "2515")     # 输入框（无键盘态）
TAP_SEND = ("1077", "1606")     # ↑ 发送（键盘弹起态）
POLL_S = 0.05                   # 等待轮询粒度，见文件头第 3 条
STOP_ISSUING_AT_S = 1200        # 超过这个点不再起新轮，留尾巴给采集器


def serial():
    """`adb -s` 用的设备序列号：只认环境变量 `ANEB_SERIAL`，缺失即 exit 2（A-1 ③）。

    多设备在线时不带 `-s` 的 adb 报 "more than one device" 而 stdout 为空串——
    在调用方看来与「前台不是 PKG」**同形**，于是一格白跑且归因指向 App。
    序列号在**每次调用时**取（不在 import 时取），测试才 import 得动。
    """
    s = os.environ.get("ANEB_SERIAL", "").strip()
    if not s:
        print("STOP: 环境变量 ANEB_SERIAL 未设置——adb -s 需要设备序列号，"
              "多设备在线时不指定会打到别的设备且不报错。", file=sys.stderr, flush=True)
        sys.exit(2)
    return s


def shell_quote(arg):
    """把一个参数包成设备侧 shell 的单引号串；内含单引号按 '"'"' 拆接（POSIX 惯用法）。"""
    return "'" + str(arg).replace("'", "'\"'\"'") + "'"


def sh_argv(*args):
    """拼 `adb -s SERIAL shell <每个参数单引号包裹>`；与 `sh()` 分开是为了让测试核 argv 不碰 adb。"""
    return ["adb", "-s", serial(), "shell", *(shell_quote(a) for a in args)]


def sh(*args):
    """跑一条 `adb -s SERIAL shell`，返回 stdout。调用点一律经模块级 `SH`（测试注入点）。

    🔴 `encoding=` 与 `errors=` 缺一不可（v3 报，2026-08-31 实测复现）：
    裸 `text=True` 时父侧按 `locale.getencoding()` 解（本机 PowerShell 下＝`cp936`），
    而设备吐的是 UTF-8 ⇒ `UnicodeDecodeError` **抛在 `subprocess._readerthread` 线程里被吞掉**，
    `run()` **正常返回、`returncode=0`、而 `stdout` 是 `None`**——调用方收不到任何错误。
    随后旧版 `focus_ok()`（拿 `PKG` 对整段返回值做 `in` 子串判断）就是 `PKG in None`
    ⇒ **TypeError，跑到一半炸，该格作废**。现版 `focus_ok()` 以 `or ""` 兜住 None，
    但 None 的**成因**仍只靠本行的 `encoding=` 杜绝——兜底不是修因。

    ⚠ 复现要构造：`dumpsys window` 的输出**恰好全是合法 GBK 时不炸**——我第一次测就是阴性的。
    构造法：`adb shell echo 测试中文abc` ⇒ 裸 `text=True` 回 `None`，本行的写法回 `'测试中文abc'`。
    ⇒ **「我没复现」不等于「它不会发生」，要去构造触发条件。**

    ⚠ 不带 `PYTHONIOENCODING`：v3 给的三件套里那一件是为 **Python 子进程**准备的，
    而 `adb` 是 C++ 二进制，对它无效。**照抄整套会带进一个在此处没有作用的项。**

    ⚠ 参数逐个单引号包裹后交给设备侧 shell（A-1 ③）：含空格/引号的提示词与
    `E4MARK kind=... n=...` 这类带空格的日志体才能**原样**到达 `input text` / `log`。
    """
    return subprocess.run(sh_argv(*args), capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


SH = sh     # 测试注入点：调用点一律用 SH，测试把它换成不碰 adb 的假件（A-1 ③）


def focus_ok():
    """前台包名**精确等于** PKG 且屏已醒（`mWakefulness=Awake`），两者同真才 True（A-1 ②）。

    旧写法是对整段 `dumpsys window` 做 PKG 子串匹配，三个洞各对应下面一个判据：
      (a) 返回 None 时 TypeError（见 `sh()` 头注）——`or ""` 兜住；
      (b) 子串会被**任何**窗口里出现的 PKG 放行（探针自己的窗、前缀同名的包如
          PKG+'.ctree'），而焦点其实在别处——只认 `mCurrentFocus=` 那一行并**全等**比较；
      (c) 屏睡着时锁屏罩顶前台、刺激全打在黑屏上而 dumpsys 照绿（D-635 ②a 假 FAIL
          形态）——再核 `dumpsys power` 的 `mWakefulness=Awake`。
    """
    m = re.search(r'mCurrentFocus=Window\{[^}]*\s(\S+)/', SH("dumpsys", "window") or "")
    if m is None or m.group(1) != PKG:
        return False
    return "mWakefulness=Awake" in (SH("dumpsys", "power") or "")


def require_focus(where):
    if not focus_ok():
        raise SystemExit("STOP: 前台已不是 %s 或屏未醒（%s）。不继续盲点。" % (PKG, where))


def mark(kind, n):
    SH("log", "-t", "AnebE4MARK", "E4MARK kind=%s n=%d" % (kind, n))


def wait_until(t0, seconds):
    """从 t0 起等 seconds 秒。返回**实际**经过的秒数。"""
    while time.time() - t0 < seconds:
        time.sleep(POLL_S)
    return time.time() - t0


def main():
    # 用法: drive_cell.py <out_dir> <rounds> <prompt> <answer_wait_s> <quiet_s>
    #
    # ⚠ 这段原是 docstring，A-1 ① 改成注释：下面那句 pin 必须是函数体**首条语句**，
    #   而它此前**写在 docstring 里＝空转**（重定向落盘时中文键名照样退回 GBK，
    #   读的人以为读全了——D-648③ 的病一天都没治过）。
    #
    # 静置期（quiet）＝答完标记之后、切下一轮之前什么都不做的一段。它一个防御一个进攻：
    #   防御 —— 若「高模」由驱动器的切轮动作触发，静置期把那个动作推远，真簇才有机会先形成；
    #   进攻 —— 若高模**仍然**出现、且数值 ≈ 答窗＋静置，那就直接证明是驱动器造的。
    e1_io.pin_console_utf8()   # D-648③：重定向落盘时别退回 GBK（中文键名是分流信号）
    out_dir = Path(sys.argv[1])
    rounds = int(sys.argv[2])
    prompt = sys.argv[3]
    answer_wait_s = float(sys.argv[4])
    quiet_s = float(sys.argv[5])
    # A-1 ④：非 ASCII 提示词经 `input text` 会被吞字（半句进去、零报错）——起跑前就停。
    assert prompt.isascii(), "prompt 含非 ASCII 字符，input text 会吞字: %r" % prompt
    dev = serial()
    timing_path = out_dir.parent / (out_dir.name + "_driver_timing.jsonl")
    t_batch = time.time()

    # A-1 ④：账目首行落 prompt 本体——判读侧才能核「这一格到底打的是哪句」。
    with io.open(timing_path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"kind": "prompt", "text": prompt, "pkg": PKG, "serial": dev},
                           ensure_ascii=False) + "\n")

    print("答窗意图=%.2fs 静置意图=%.2fs 轮数=%d" % (answer_wait_s, quiet_s, rounds), flush=True)

    for n in range(1, rounds + 1):
        if time.time() - t_batch > STOP_ISSUING_AT_S:
            print("轮 %d 未起：已过 %ds，留尾巴给采集器" % (n, STOP_ISSUING_AT_S), flush=True)
            break
        require_focus("轮 %d 开头" % n)
        t_round0 = time.time()
        SH("input", "tap", *TAP_MENU)
        time.sleep(1.6)
        SH("input", "tap", *TAP_NEW)
        time.sleep(2.6)
        require_focus("轮 %d 新对话之后" % n)
        SH("input", "tap", *TAP_INPUT)
        time.sleep(1.3)
        SH("input", "text", prompt.replace(" ", "%s"))
        time.sleep(1.8)
        require_focus("轮 %d 输入之后" % n)

        t_send = time.time()
        mark("turn_start", n)
        SH("input", "tap", *TAP_SEND)
        answer_actual = wait_until(t_send, answer_wait_s)
        mark("answer_complete", n)

        quiet_actual = wait_until(time.time(), quiet_s)

        rec = {
            "round": n,
            "answer_wait_intended_s": answer_wait_s,
            "answer_wait_actual_s": round(answer_actual, 3),
            "quiet_intended_s": quiet_s,
            "quiet_actual_s": round(quiet_actual, 3),
            "prep_before_send_s": round(t_send - t_round0, 3),
            "round_total_s": round(time.time() - t_round0, 3),
        }
        with io.open(timing_path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print("轮 %d: 答窗实际 %.2fs 静置实际 %.2fs 本轮共 %.2fs"
              % (n, answer_actual, quiet_actual, rec["round_total_s"]), flush=True)

    print("driver done, 总耗时 %.0fs" % (time.time() - t_batch), flush=True)


if __name__ == "__main__":
    main()
