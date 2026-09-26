# 补丁：判据 V4 拦窗 #9（§2-9／§8-5）零读数判别量去常量化

> **状态：已做好、已验证、未落树。** 协调侧在自己容器的隔离工作树（基准 `df78728`）上完成；**没有碰共享树的 `scripts/`**（承 D-582：未点名不动）。
> 属主（v4 或大脑点名者）一条命令即落：`git apply docs/coordination/patches/c2x_s2_9_zero_reading.patch`
> ⚠ v4 今日正在改同一文件（第一／二／三批）；若先落了别的批次，按 §4 的锚点重核 `git apply --check`，冲突时以本文 §2 的规格为准手工合并——**门（新测试文件）是最可移植的部分，任何重构后都应原样通过**。

## 1. 修的是什么（审阅原文 §2-9 的规格，逐条对应）

| 审阅要求 | 实现 |
|---|---|
| `_reader` 拿一个 `threading.Event`，主线程在 Shutdown **之前** set | `cell()` 建 `stop_a／stop_b`，`finally` 里先 `set()` 再 `WinDivertShutdown` |
| Recv 失败那一瞬、同线程记下 (last_error, evt.is_set(), time.time()) | `_reader` 循环退出后依次取 `get_last_error()`→`is_set()`→`time.time()`，写入 `obs` |
| `shutting_down` 取读线程观察到的值 | 删掉 `finally` 里无条件的 `out["shutting_down"] = True`；改为 `obs_a["stopping_seen"]`（未退出＝None） |
| 派生 `exited_before_traffic` | `t_exit < traffic_start`，a／b 各自一份 |
| 句柄 b 同样做，结果送 `verdict_impostor`，不满足 ⇒ VOID_MISSING 不是 ZERO | b 过 `cell_status`，不满足则分子喂 `None` ⇒ `verdict_impostor` 返回 VOID_MISSING |
| `apply_verdicts` 在印任何判词之前消费格级 status，不满足即 NOT_EXECUTED 并拒判该格全部判词 | 函数开头逐格过 `cell_status`，不合格者印 NOT_EXECUTED 并**整格丢弃** |
| 门两个方向都要 | 世界 A（读线程自己死）必 NOT_EXECUTED；世界 B（被叫停的真零）必成立 |

**关键设计点**：`zero_reading_ok` 本身没改——**它没错，错的是它的输入是常量**。新增的纯函数 `cell_status()`（`decompose_2x_verdicts.py`，紧接 `zero_reading_ok` 之后）只是在它前面加两道：句柄没开成、先于流量退出。

**为什么是"整格丢弃"而不是"计数改 None"**：协调侧逐个实调了下游五个消费者——
`verdict_identity(a2=None)` ⇒ UNDECIDABLE「A2 计数未取到」；`verdict_impostor(num=None)` ⇒ VOID_MISSING；
H2／N1N2 调用点有 `None not in (...)` 守卫；S3 缺格 ⇒ VOID_NO_T ⇒ FAIL。**缺席在每条路径上都落「不可判」**。
而 `verdict_h2`／`verdict_n` 对 `None` **直接抛 TypeError**——把计数改 None 喂进去会崩。

## 2. 门（新文件 `scripts/tests/test_decompose_2x_zero_reading.py`，16 条，零参、兼容 `run_all.py`）

- 纯函数：真零成立（反方向）／读线程自己死 ⇒ NOT_EXECUTED／先于流量退出即便计数非 0 也 NOT_EXECUTED／句柄没开成／**范围边界**（窗口中途死而计数非 0 本条不管，钉住以免有人悄悄扩范围）／史实对照（旧常量输入为何放行）
- `cell()` 两个世界：假驱动 A（首次 Recv 即 FALSE）、假驱动 B（阻塞到 Shutdown）；B 的 Shutdown **放行读线程后故意慢 0.2s 返回** ⇒ 「stop 在 Shutdown 之后才 set」这个顺序错**确定性**变红
- 句柄 b：观察值与 a 分开；**受控时钟**把 a／b 读线程的退出时刻钉成确定值 ⇒ 「b 错用 a 的退出时刻」确定性可抓（真实时钟下它是调度竞态，只会偶尔被抓）
- `apply_verdicts`：死掉的 S1 必须先印 NOT_EXECUTED 且不再印底噪判词；死掉的 A1 拒判全部；句柄 b 死 ⇒ VOID_MISSING；句柄 b 真零 ⇒ 仍判 ZERO（反方向）
- 报告行与判定一致：`report_cell` 印的零读数通则必须用同一个 `cell_status`（逐字副本进证据，D-890）

## 3. 突变审计（禁用字节码缓存；每次核「盘上字节真变了」）

| 突变 | 结果 |
|---|---|
| M1 恢复 `finally` 里无条件置真 | CAUGHT |
| M2 stop 挪到 Shutdown 之后 | CAUGHT |
| M3 去掉 `apply_verdicts` 的格级拒判 | CAUGHT |
| M4 impostor 分子不看句柄 b 的 status | CAUGHT |
| M5 `cell_status` 丢掉先于流量退出那支 | CAUGHT |
| M6 句柄 b 共用 a 的旗标（等长） | CAUGHT |
| M7 读线程里取时刻与取错误码互换（等长） | **SURVIVED——等价突变**：Linux 桩上两者顺序不可观测；代码里的顺序是给 Windows `GetLastError` 的防御，非 Windows 不可测 |
| M8 句柄 b 用 a 的退出时刻（等长） | CAUGHT（受控时钟门） |
| M9 a 的 exited 比较取反 | CAUGHT |
| M10 读线程不采样、旗标恒 True | CAUGHT |
| M11 报告行仍用旧 `zero_reading_ok` | CAUGHT（报告一致性门） |

**10／11 被抓，唯一存活是等价突变。**

⚠ **审计仪器自己瞎过一次，如实记**：首轮 M6、M8 显示 SURVIVED——它们是**等长突变**，而 Python 的 `.pyc` 按「源 mtime（秒）＋长度」判新旧，与上次还原落在同一秒内就继续用旧字节码 ⇒ 突变从未被执行。禁用字节码缓存（`python -B`、`PYTHONDONTWRITEBYTECODE=1`、每轮清 `__pycache__`）后 M6 立即 CAUGHT；M8 则是真缺口，补了受控时钟门后 CAUGHT。
⇒ 通则（承 D-898「没红先问改动了没有」的下一层）：**核「盘上字节变了」不够，还要核「解释器跑的是新字节」——等长突变必须禁缓存。**

## 4. 回归

**基准 `df78728`，pytest 跑全部 `scripts/tests/`（禁字节码缓存），补丁前后逐名对比：**

| | 败 | 过 | 跳 |
|---|---|---|---|
| 上游原样 `df78728` | 8 | 952 | 7 |
| 打补丁后 | 8 | **968** | 7 |

- 多出的 **16 过**＝新门文件；**失败集合逐名相同**，补丁零新增失败、零消失。
- 8 条基线红**均与本补丁无关、补丁前即在**：7 条是 Windows 专有 API 在 Linux 上缺席（`ctypes.windll`／`ctypes.get_last_error`），Windows 上应绿；1 条 `test_manifest_hashes`＝`evidence/phase0/sha256-manifest.txt` 与本机检出的四个日志哈希不符（成因未核，疑为检出时行尾换算，不下结论）。
- ⚠ **`run_all.py` 在本机不能当完整仪器**：它在 `_acp()` 的 `SystemExit` 处整体中止、不出汇总（见 §5-3）；补丁前后中止在同一处、输出除临时目录名外逐行相同。故全量回归改用 pytest（按用例隔离 `SystemExit`）。
- `git apply --check` 在 `df78728` 上干净；落树前 `df78728` 之后上游无人动这两个文件。
- **未在 Windows 上跑过**：7 条平台红在 Windows 上的表现、以及真驱动下的行为，须属主在本机再跑一遍 `run_all` 确认。

## 5. 不在本补丁范围、但值得另立的

1. **窗口中途读线程自己死、计数非 0 但偏少**：本条通则只管 0；偏少的计数喂进身份判词可能判出错误的 DIFFERENT／LOSS。已用「范围边界」门钉住现状，要收紧请另立条目。
2. **S3 两句柄格的句柄 b 死掉**：本补丁没动 S3 分支（那是簇 A `verdict_s3` 的地盘，避免与之撞车）。实调下 b 死 ⇒ `verdict_s3` 拿到残缺序列 ⇒ 不会判 PASS（安全方向），但原因不会被说出来。
3. **`run_all.py` 在 `SystemExit` 处整体中止**：`_acp()` 在 GetACP 不可用或含 utf 时抛 `SystemExit`（`BaseException`），`run_all` 的 `except Exception` 接不住 ⇒ 运行器在该模块处死掉、**不出汇总**。与 `run_all.py` 注释里自记的 `pytest.skip` 那次同形。Windows 正常路径不触发，但 GetACP 真返回 utf 时 Windows 上也会同样无汇总地死。
