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
  2. 每一段盲点序列之前复核 mCurrentFocus；前台不是豆包就抛错停住。
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


def sh(*args):
    """跑一条 `adb shell`，返回 stdout。

    🔴 `encoding=` 与 `errors=` 缺一不可（v3 报，2026-08-31 实测复现）：
    裸 `text=True` 时父侧按 `locale.getencoding()` 解（本机 PowerShell 下＝`cp936`），
    而设备吐的是 UTF-8 ⇒ `UnicodeDecodeError` **抛在 `subprocess._readerthread` 线程里被吞掉**，
    `run()` **正常返回、`returncode=0`、而 `stdout` 是 `None`**——调用方收不到任何错误。
    随后 `focus_ok()` 的 `PKG in sh(...)` 就是 `PKG in None` ⇒ **TypeError，跑到一半炸，该格作废**。

    ⚠ 复现要构造：`dumpsys window` 的输出**恰好全是合法 GBK 时不炸**——我第一次测就是阴性的。
    构造法：`adb shell echo 测试中文abc` ⇒ 裸 `text=True` 回 `None`，本行的写法回 `'测试中文abc'`。
    ⇒ **「我没复现」不等于「它不会发生」，要去构造触发条件。**

    ⚠ 不带 `PYTHONIOENCODING`：v3 给的三件套里那一件是为 **Python 子进程**准备的，
    而 `adb` 是 C++ 二进制，对它无效。**照抄整套会带进一个在此处没有作用的项。**
    """
    return subprocess.run(["adb", "shell", *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


def focus_ok():
    return PKG in sh("dumpsys", "window")


def require_focus(where):
    if not focus_ok():
        raise SystemExit("STOP: 前台已不是豆包（%s）。不继续盲点。" % where)


def mark(kind, n):
    sh("log", "-t", "AnebE4MARK", "E4MARK kind=%s n=%d" % (kind, n))


def wait_until(t0, seconds):
    """从 t0 起等 seconds 秒。返回**实际**经过的秒数。"""
    while time.time() - t0 < seconds:
        time.sleep(POLL_S)
    return time.time() - t0


def main():
    """用法: drive_cell.py <out_dir> <rounds> <prompt> <answer_wait_s> <quiet_s>
    e1_io.pin_console_utf8()   # D-648③：重定向落盘时别退回 GBK（中文键名是分流信号）

    静置期（quiet）＝答完标记之后、切下一轮之前什么都不做的一段。它一个防御一个进攻：
      防御 —— 若「高模」由驱动器的切轮动作触发，静置期把那个动作推远，真簇才有机会先形成；
      进攻 —— 若高模**仍然**出现、且数值 ≈ 答窗＋静置，那就直接证明是驱动器造的。
    """
    out_dir = Path(sys.argv[1])
    rounds = int(sys.argv[2])
    prompt = sys.argv[3]
    answer_wait_s = float(sys.argv[4])
    quiet_s = float(sys.argv[5])
    timing_path = out_dir.parent / (out_dir.name + "_driver_timing.jsonl")
    t_batch = time.time()

    print("答窗意图=%.2fs 静置意图=%.2fs 轮数=%d" % (answer_wait_s, quiet_s, rounds), flush=True)

    for n in range(1, rounds + 1):
        if time.time() - t_batch > STOP_ISSUING_AT_S:
            print("轮 %d 未起：已过 %ds，留尾巴给采集器" % (n, STOP_ISSUING_AT_S), flush=True)
            break
        require_focus("轮 %d 开头" % n)
        t_round0 = time.time()
        sh("input", "tap", *TAP_MENU)
        time.sleep(1.6)
        sh("input", "tap", *TAP_NEW)
        time.sleep(2.6)
        require_focus("轮 %d 新对话之后" % n)
        sh("input", "tap", *TAP_INPUT)
        time.sleep(1.3)
        sh("input", "text", prompt.replace(" ", "%s"))
        time.sleep(1.8)
        require_focus("轮 %d 输入之后" % n)

        t_send = time.time()
        mark("turn_start", n)
        sh("input", "tap", *TAP_SEND)
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
