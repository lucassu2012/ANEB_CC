# 补丁：判据 V4 拦窗 #11（§2-11）＋ §8-17——`T` 的前提是往返，超时当场印

> **状态：已做好、已验证、未落树。** 协调侧在自己容器的隔离工作树（基准 `df78728`）上完成；**没有碰共享树的 `scripts/`**（承 D-582：未点名不动）。
> 属主一条命令即落：`git apply docs/coordination/patches/c2x_s2_11_roundtrip.patch`
> **与 #9 补丁互不依赖、两种先后顺序都能落**（已实测：单独／先 #9 后本／先本后 #9，`git apply --check` 全干净；两份一起落后全量回归见 §4）。
> 簇 C（采集与零读数路径）三条 = §2-9（#9 补丁）＋ §2-11 ＋ §8-17（本补丁）⇒ **两份补丁落下即簇 C 的代码侧清空**；余下的是判据文本（§5）。

## 1. 修的是什么（审阅原文逐条对应）

| 审阅要求 | 实现 |
|---|---|
| §2-11：dev_ping／pc_ping 同时取 (sent, recv) 并都返回 | 新纯函数 `ping_roundtrip(side, out, err)` → `{sent, recv, T, why}`；两个 ping 助手照旧**返回 `T`**（零参调用不变），另可传 `acq` 字典回填四个字段 |
| recv == 0 ⇒ 该格不给 T 并印「本格往返 N 发 0 收」 | 走已有的「缺读数就拒给 T」路径；那句话进 ping 自述行的括号里，逐字进证据 |
| 连续两格 recv == 0 ⇒ SystemExit 收尾 | 新纯函数 `roundtrip_streak(streak, acq)`；`main()` 格循环末尾满 2 即 `SystemExit("NOT_EXECUTED：连续 2 个打包格未见往返…")`，走既有 `except BaseException`＋`finally teardown`，**收尾照做** |
| 不新增任何一次设备调用、不延长窗口 | 零新增调用；只多读已有输出里的一个数 |
| §8-17：run() 把 TimeoutExpired 与其它异常分开，超时时印出来 | `except subprocess.TimeoutExpired` 单列：当场印「⚠ adb.exe 超时 180s ⇒ 本次调用无读数」，`err` 回「超时：180s」；其它异常原样不变 |
| §8-17：该格带 acquisition_failed 标记进判定层，与「读数为 0」分开 | 见下「为什么不另设 acquisition_failed」 |

### 协调侧在审阅原文之外加的两处，各有理由，属主可否决

1. **PC 侧收数不信摘要行，只数「来自目标、带 `TTL=`」的回显行。** Windows ping 把网关回的「无法访问目标主机」也记作「已接收」——上游断了照样能印「已发送 = 20，已接收 = 20」。照审阅原文「复用 PING_RECV」在 PC 侧也做不到（那条正则只认 Linux 格式），而改读 Windows 摘要的收数就会把这个假收数当往返。中英文回显行都含 `TTL=`（Windows 不本地化它），与 locale 无关。设备侧（Android ping，iputils 系）的 `received` 不含 ICMP 差错（差错单列 `+N errors`），直接用第一道门那条 `PING_RECV`。
2. **连续计数不只数「0 收」，也数「收数／发包数读不到」（含超时）。** 审阅原文 Stop rule 5 写的正是「连续两格出现『设备侧 ping 自述：（无摘要行）⇒ T=None』——设备或 adb 掉了。停。**当前没有门会拦你**」——那一格是「读不到」不是「0 收」。只数 0 收就拦不住 Stop rule 5 点名的那种。空闲格（S0／S1／S2）不打包，**不计也不清零**。

### 为什么不另设 `acquisition_failed`

`T=None` 本身就是那个标记，且判定层已经按它走「不可判」：`verdict_h2` 回 VOID_T_MISSING、A1 缺 T 走「全部不可判」、S3 缺 T 回 VOID_NO_T（协调侧 #9 那轮逐个实调过）。它与「读数为 0」天然分开——`T` 和 `count` 是两个字段，0 收拒的是 `T`，`count` 照印。缺的从来不是标记，是**原因没被说出来**：本补丁让原因出现两次——`run()` 当场印超时，ping 自述行括号里印 `why`（「发包数读不到（超时：180s）⇒ T 缺席」）。每格的 `acq` 另挂在 `cells[label]["acq"]`，判定层要消费随时可取；再加一个布尔字段只会多一个能与 `T` 不一致的量。

## 2. 门（新文件 `scripts/tests/test_decompose_2x_roundtrip.py`，16 条，零参、兼容 `run_all.py`）

- `ping_roundtrip` 纯函数：PC 全通给 T；**Windows 把 20 个「无法访问目标主机」记成 Received = 20 ⇒ 必须拒**（夹具先断言那个假收数真在）；别的主机回的 TTL 行不算；PC 全超时拒；**部分丢包 20 发 3 收 ⇒ T=20 不是 3**（§3：T 取已发送）；设备 0 收拒且印「本格往返 20 发 0 收」；收数读不到 ⇒ `recv` 是 None 不是 0；发包数读不到 ⇒ 说明里带上 `run()` 给的「超时：180s」
- `run()`：`TimeoutExpired` ⇒ 当场印「超时 180s」且 `err` 形状可辨；别的异常形状不变、不印超时
- 两个 ping 助手：带 `acq` 回填、零参照旧可调
- `roundtrip_streak`：空闲格插在两格断之间不得洗掉连续数；有往返清零；断—通—断只算 1
- **`main()` 接线**（桩掉 preflight／cell／run／teardown，不碰驱动）：C1 0 收＋F1 adb 超时 ⇒ 在 F1 之后中止、F2／N1／N2 不跑、**收尾照做一次**、中止文本以 NOT_EXECUTED 开头并带 `[F1` 与超时原因；断一格（C1、F2 各断一次、中间有通）⇒ 不中止、跑满、每格挂 `acq`、空闲格 `acq` 是 None

## 3. 突变审计（禁字节码缓存；审计后源文件 sha256 与审计前逐字相同）

| 突变 | 被哪条门抓 |
|---|---|
| M1 `run()` 不单接超时 | `test_run_prints_timeout_and_returns_a_distinct_err` |
| M2 超时不印 | 同上 |
| M3 PC 不要求回显来自目标 | `…from_another_host…` |
| M4 PC 改信摘要行收数 | `…windows_counts_as_received…` 等 2 条 |
| M5 0 收照给 T | 4 条 |
| M6 T 取收数而非已发送 | `test_partial_loss_still_gives_T_as_sent_not_recv` |
| M7 收数读不到当 0 | `test_recv_unreadable_is_not_zero_and_not_a_roundtrip` |
| M8 缺席说明不带 `err` | 2 条（含 `main` 接线门） |
| M9 空闲格清零 | `test_streak_idle_cells_neither_count_nor_reset` |
| M10 有往返不清零 | 3 条 |
| M11 阈值改 3 | `main` 中止门 |
| M12 `main` 不包 traffic（`acq` 永空） | `main` 两条门 |
| M13 空闲格 `acq` 留空 dict 不归 None | `main` 不中止门 |
| M14 `dev_ping` 不回填 `acq` | 3 条 |
| M15 中止改成只印不停 | `main` 中止门 |

**15／15 被抓，且逐个核过是被预期那条门抓的**（`-rf` 列出失败用例名），不是收集期语法错。

## 4. 回归

**基准 `df78728`，pytest 跑全部 `scripts/tests/`（`python -B`、`PYTHONDONTWRITEBYTECODE=1`、先清 `__pycache__`），逐名比对失败集合：**

| | 败 | 过 | 跳 |
|---|---|---|---|
| 上游原样 `df78728` | 8 | 952 | 7 |
| 只落本补丁 | 8 | **968** | 7 |
| 本补丁 ＋ #9 补丁 | 8 | **984** | 7 |

- 多出的 16 过＝新门文件；两份一起落 952＋16＋16＝984 对得上；**失败集合三次逐名相同**。（首次测得 967 是补第 16 条门之前的字节，已在最终字节上重跑得 968，表里是重跑值。）8 条基线红同 #9 README §4：7 条 Windows 专有 API 在 Linux 缺席、1 条 `test_manifest_hashes` 行尾疑点。
- 探针文件无人以哈希钉住（`git grep` 过 manifest／json／sha256），落树不需要重钉。
- `pc_ping`／`dev_ping` 在 `plan` 之外没有别的调用点；preflight 的 `_sent_count` 自检（`ping.exe -n 1 127.0.0.1`）不经过它们，不受影响。
- **未在 Windows 上跑过**：PC 侧回显行格式（中文「来自 … 的回复: 字节=32 时间=12ms TTL=116」）按常见输出写的夹具，属主在本机跑一次 `ping.exe -n 2 223.5.5.5` 看一眼行里有 `TTL=` 即可确认；若本机 ping 输出格式不同，改的是 `PING_ECHO_WIN` 一处。

## 5. 不在本补丁范围、但须有人接

1. **判据文本**（属主是判据作者，不是代码）：§3 的 `T` 定义补一句「前提＝本格往返 ≥1，否则 T 缺席」；criteria:598 那句「挂死即上抛」**半是假的**（审阅 §8-17 原话）——`run()` 仍不抛，是由调用方拒给 T；PO 单子补一句「五个设备格各最长 180 s，光标不动不要 Ctrl+C」（Ctrl+C 会正常收尾，但 PO 现在无从知道）。
2. **审阅 §8 同条的 (2)(3) 两项没做**：(2) 每个 FORWARD 格前后重跑 `judge_first_hop`／`device_egress` 并打 unreachable 标记（每格多约 12 s，审阅自己给了「至少 C1 前与 N2 后各一次」的降级）；(3) §2-6 格后复核的比较扩到 (hot_ifidx, up_ifidx, up_addr, nb_kept, 设备 src) 且与上一格比。本补丁只做了审阅在 §2 拦窗条目里写的那一项（零新增调用）；(2)(3) 会加时长或改 §2-6 语义，该由判据作者定。
3. **adb ping 的超时 180 s 本身偏长**：20 个包 1 s 间隔正常 ~20 s 走完，180 s 意味着一格挂死最多白等 2.5 分钟。本补丁已让连续两格即中止（最坏白等 6 分钟而不是 15 分钟），是否再压到 60 s 由属主定——那是改一个常量、但会改 PO 单子上的时长说明。
