# E1 真机窗判读（v4 独立判读）—— DW-20260802-01

> 判读对象：`evidence/e1_realdevice_20260802/`（v2 采集，`e234_collect.py`，2026-08-02 16:13–16:15）。
> 判读人：v4（E1 装置原设计者）。与 v3 的 e234 判读**互为独立复核**，方法、工具链、结论各自独立，
> 未参考 v3 尚未产出的判读文本。工具：本人 `tools/e1/e1_analyze.py`（`--stim-file` 指到
> `stim_pre.log`/`stim_post.log`，D-407 已加此支路，复用而非重写）。
> 状态词只用 `PASS`/`FAIL`/`NOT_EXECUTED`/`BLOCKED_EXTERNAL`。

---

## 0. 一页结论

| 问题 | 答案 |
|---|---|
| **E_transport⊕E_quant 分布**（spec §3.3 E1 原始目标） | **`NOT_EXECUTED`，且原因可判定**：三条通道的观测窗口与刺激源翻转窗口**时间上零重叠**——不是精度不够，是压根没看见事件发生的那几秒。 |
| **通道 C 在 P40 的可用性（W-2）** | **仍不可判定**，且理由与「空表」不同：`framestats.txt` 的 322 字节是 **8 次 `No process found for: com.aneb.e1stimulus`**——探测时目标进程根本没在跑。P40 上 `gfxinfo`/`SurfaceFlinger --list` 这两条支路**从未在进程存活时被真正问过**。 |
| **根因** | **采集脚本的时序缺陷**，非设备限制。`tools/e234/e234_collect.py` 的 `collect()` 把通道 B（screencap）与通道 C（framestats/`--latency`）的整段观测，安排在两次 `_pin()`（各自拉起又 force-stop 刺激源）**之间**，而不是**期间**。已给出精确行号与修法建议，本文件**不代改**（`tools/e234/` 归 v3 在办面）。 |
| **意外收获** | `E_clock`（BOOTTIME↔MONOTONIC 偏移）首次在真机上得到实测确认：跨度 1042 ns / 1563 ns（n=5），与 spec §3.2 原判断一致——**这是本窗唯一算落地的 spec §3 结论**。 |
| **附带复现** | 通道 B 实际采样周期（真机）：p50 3353.6ms / p90 7709.1ms / p99 9974.1ms——比模拟器 dry-run（≈2–3.5s/帧）**更差**，进一步坐实 spec §2.2「`[INFERRED,HIGH]`：B 不能判 M3 门」。 |

---

## 1. 输入清单（全部逐字节读过，非摘要转述）

```
evidence/e1_realdevice_20260802/
  RUN_KIND.json          — kind=DEVICE_REAL, experiments=[E2,E3,E4], pkg=com.aneb.e1stimulus,
                            device_window=DW-20260802-01, serial=8MY0221126002537
  collect_notes.json     — layer:null, sf_status:"NOT_EXECUTED: SurfaceFlinger --list 未找到该包的图层"
  stim_pre.log  (1772B)  — pid 11374，CFG+6×FLIP/COMMIT，16:13:01.538–16:13:06.388
  stim_post.log (1772B)  — pid 11747，CFG+6×FLIP/COMMIT，16:15:21.518–16:15:26.377
  adapter.log     (0B)
  mark_rtt.jsonl  (0B)
  framestats.txt (322B)  — 8×"No process found for: com.aneb.e1stimulus"（逐字）
  screencap_index.jsonl  — 30 行，t_host_ns ∈ [16:13:11.297, 16:15:10.976]，roi_mean 全部 158.1
  （无 sf_latency.txt —— layer=null 时代码本就跳过该支路，行为正确，非缺陷）
```

`RUN_KIND.experiments=[E2,E3,E4]` 但 `pkg=com.aneb.e1stimulus`——这是**用 E1 已知真值刺激源校准
E234 采集管线本身**的一次真机烟测，不是对豆包/DeepSeek 的正式采集。这与我 T17 交接时设想的路径
一致（先用可控真值验证装置，再花真实 App 额度），值得记一笔：**这个用法是对的**。

---

## 2. 关键发现：三条通道的观测窗口与刺激事件零时间重叠

| 阶段 | 时刻区间（设备本地时间） | 时长 |
|---|---|---|
| stim_pre 翻转（6 次，pid 11374） | 16:13:02.344 → 16:13:06.388 | ≈4.0s |
| **通道 B/C 观测窗**（screencap 首/末样本） | **16:13:11.297 → 16:15:10.976** | ≈119.7s |
| stim_post 翻转（6 次，pid 11747） | 16:15:22.323 → 16:15:26.377 | ≈4.1s |

观测窗**在 stim_pre 结束后 4.9 秒才开始，在 stim_post 开始前 11.3 秒就已结束**。三段互不相交。

**这不是我的推断，是直接测量结果**：30 个 screencap 样本的 `roi_mean` **全部等于 158.1**——一个数值零方差。刺激源在这 30 个样本窗口内实际上没有翻转过，样本理应恒定；若窗口与翻转有任何交集，至少会有几个样本落在翻转附近而读到不同的 ROI 均值。零方差与「零重叠」相互印证，不是偶然。

### 2.1 根因定位（`tools/e234/e234_collect.py`，只读，不代改）

```
201:  notes["stim_pre"] = _pin(adb, out_dir, "pre", pin_flips, pin_interval_ms)   # 拉起→翻转→force-stop
...
220:  layer = e1c.find_layer_name(adb, pkg)      # 此刻刺激源已被 201 行 force-stop，进程不存在
...
229:  tc.start()                                  # 通道 C 周期 dump 开始（进程仍不存在）
232:  notes["screencap_samples"] = _sample_roi(...)  # 通道 B 采样开始（同上）
...
240:  tc.join(timeout=60)                         # 通道 C 停止
246:  notes["stim_post"] = _pin(adb, out_dir, "post", pin_flips, pin_interval_ms)  # 再次拉起→翻转→force-stop
```

`_pin()`（`e234_collect.py:119-142`）自身的收尾就是 `force-stop`；201 行执行完毕时刺激源已死。
220 行紧接着才去找它的图层——**找不到是必然结果，不是设备能力问题**。229/232 行开始的两条
观测支路，从头到尾运行在「刺激源不存在」的窗口里，直到 246 行才把它重新拉起——但那时通道 B/C
已经停止采集。

**建议修法方向（不代改，供 v3 参考）**：让通道 B/C 的观测线程在 `_pin("pre", ...)` **之前**启动、
横跨两次 `_pin` 调用**持续**运行到 `_pin("post", ...)` 结束，而不是夹在两次 `_pin` 之间。
这样两段翻转窗口都落在观测窗口内部，才谈得上对齐判读。

### 2.2 覆盖盲区：这条时序前提此前没有测试钉住

`tools/e234/tests/test_e234_collect.py` 现有 20 条测试（门/mark 格式/模拟器产物结构），
**没有一条断言「通道 B/C 的采样窗口必须与 `_pin` 的翻转窗口有交集」**。此前唯一发现这个问题的
方式是拿真机数据肉眼核对时刻——如果没有这次真机窗，这个缺陷会一直不可见（模拟器 dry-run 用的
`sim_session.py` 是否复现了这条时序，我未查，不在本次判读范围内，留给 v3 或后续核实）。

---

## 3. E_transport⊕E_quant：为什么三条通道各自都是 `NOT_EXECUTED`，逐条给出机器判读原文

跑了两次 `e1_analyze.py`（`--stim-file stim_pre.log` 与 `--stim-file stim_post.log`），
两次结果在通道判定上一致，仅时钟偏移数值有别（下表）：

| | pre | post |
|---|---|---|
| BOOTTIME−MONOTONIC 偏移中位数 | 94513649503167 ns | 94513649503166 ns |
| 跨度（n=5） | **1042 ns** | **1563 ns** |
| 通道 A | `NOT_EXECUTED`（n=0，无逐事件时戳，设计已知缺口） | 同左 |
| 通道 C | `NOT_EXECUTED`（n=0，dropped=5，无可用帧） | 同左 |
| 通道 B | `PASS`（装置意义上），检出翻转 0/6，采样周期 p50 3353.6 / p90 7709.1 / p99 9974.1 ms | 同左 |

- **通道 A**：`adapter.log` 0 字节——`AnebProbe:I` 与 `E4MARK` 标签的 logcat 抓取窗口
  （`e234_collect.py:207-217`）与通道 B/C **同一个窗口**，同样与两段翻转不重叠；且通道 A
  本身仍卡在 T7 已知的缺口（`ADAPTER_EVT` 不带时戳）。两个原因叠加，此次判读**不能**把
  「通道 A 为空」单归因于时序问题——需要先补上 T7 那行 additive 时戳扩展，才谈得上用真机窗
  重验通道 A 本身的可用性。

- **通道 C**：见 §2；`dropped=5` 是 `align_present()` 尝试把 5 个可用翻转与 framestats 帧对齐、
  一个都对不上（因为 framestats 里根本没有帧行）后的诚实记账——不是静默丢弃，是`e1_analyze.py`
  按设计把它们计入 `dropped` 而非悄悄从分母消失。

- **通道 B**：**唯一在时间上"跑起来"的通道**，但因为观测窗口本身就没有覆盖任何翻转，
  30 个样本检出翻转次数为 0——这不是通道 B 的判据失败，是它被喂了一段不含事件的输入，
  如实报告"没看见"（`e1_report_pre.md`/`_post.md` 原文："检出率不是时序主张，只说明 ROI
  与阈值选得对不对"）。

**结论**：**这次真机窗没有产出任何一条可用于判 M3 打点误差门的分布**。§3.4 的 M3 打点误差门
判据表（G-1..G-5）维持 `NOT_EXECUTED`，与 T7/T13 的既有结论一致——只是现在多了一条更精确的
理由：不是「没测」，是「测了但观测窗对不上事件窗」。

---

## 4. W-2 答案：通道 C 在 P40 上的可用性——**仍未回答**，且回答的前提条件被证明了

W-2 问的是「`gfxinfo`/`SurfaceFlinger --latency` 在 P40 上，进程存活、图层存在时，能不能给出
帧级数据」。这次真机窗**没有回答这个问题**，因为它从未在进程存活期间问过。

对比两次失效模式，两者**性质不同**，不可混为一谈：

| | 2026-08-01 模拟器 dry-run（T7） | 2026-08-02 真机窗（本次） |
|---|---|---|
| 目标进程是否存活 | **存活**（图层找对、`--latency` 有响应） | **不存活**（`force-stop` 之后才探测） |
| `SurfaceFlinger --latency` | 只回一行刷新周期，零帧记录 | 未执行（`layer=null` 时代码本就跳过） |
| `gfxinfo framestats` | `PROFILEDATA` 块存在但为空 | 返回 adb 错误文本「进程不存在」，**不是** `PROFILEDATA` 空 |
| 结论 | 该环境下两条支路都取不到帧行（环境限制的初步证据） | **无法判断该环境的能力**——问的时机不对，答案没有信息量 |

**W-2 仍待一次真正的测试**：进程存活期间（例如在 `_pin` 的 `am start` 与 `force-stop`
之间的那段窗口内）对同一个包发起 `gfxinfo framestats` 与 `SurfaceFlinger --latency <layer>`，
才是能回答 W-2 的实验设计。这正是 §2.1 建议的修法方向所解决的同一个缺口。

---

## 5. 数字账（本文件的自查，防止下游把「测了没测到」读成「测出了 0」）

### 5.1 本文件引用的全部实测数字（逐条标出处）

| 数字 | 来源 |
|---|---|
| stim_pre 6 次翻转，16:13:02.344–16:13:06.388，pid 11374 | `stim_pre.log` 逐字 |
| stim_post 6 次翻转，16:15:21.518–16:15:26.377，pid 11747 | `stim_post.log` 逐字 |
| 观测窗 16:13:11.297–16:15:10.976，n=30，roi_mean 恒 158.1 | `screencap_index.jsonl` 逐行读出+脚本换算（host epoch ns → 本地时间） |
| framestats.txt 322 字节 = 8×「No process found」 | 文件逐字节读出 |
| `layer=null`，`sf_status=NOT_EXECUTED` | `collect_notes.json` 逐字 |
| BOOTTIME−MONOTONIC 跨度 1042ns(pre)/1563ns(post)，n=5 | `e1_analyze.py` 实跑输出（`e1_report_pre.md`/`_post.md`） |
| 通道 B 采样周期 p50/p90/p99 = 3353.6/7709.1/9974.1 ms | 同上 |
| 通道 A/C 判定与 dropped 计数 | 同上 |
| `e234_collect.py` 行号 201/220/229/232/240/246 | 本次判读时 `grep -n` 实测 |
| `test_e234_collect.py` 现有 20 条测试均不含重叠断言 | 本次判读时通读该文件测试名清单 |

### 5.2 本文件明确没有给出的量（防止被误读为已知）

1. `sim_session.py`（E234 模拟器夹具）是否复现了这条时序缺陷——未查，非本次判读范围。
2. 通道 A 在「时序修复 + T7 时戳扩展」都到位后，在 P40 上的真实检出能力——两个前置条件都不满足，无法测。
3. 修复 §2.1 时序缺陷后，通道 C 在 P40 上的真实精度——需要重新开一次真机窗验证，本文件不预判结果。

---

## 6. 待裁定 / 交大脑

| # | 事项 | 本文件立场 |
|---|---|---|
| J-1 | `e234_collect.py` 的通道 B/C 观测窗时序缺陷（§2.1）由谁修 | 归 v3（`tools/e234/` 在办面），本文件只诊断+给行号，不代改 |
| J-2 | 修复后是否值得再开一次真机窗专门验证 W-2 | 建议排期，且**只需**验证通道 C（不必重跑完整 E2/E3/E4），成本应远低于本次 |
| J-3 | `test_e234_collect.py` 补一条「观测窗与 pin 窗必须有交集」的不变量测试 | 建议随 §2.1 修复同批加，避免同一缺陷再犯（同 D-321/D-322 一贯做法：运行时可测的前提就该有断言） |

---

*E1 真机窗判读 · v4 独立判读 · 2026-08-02 · 与 v3 判读互为复核，未预先对齐结论*
