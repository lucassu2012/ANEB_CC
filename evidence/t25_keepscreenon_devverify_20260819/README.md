# T25 真机验证（DW-20260819-01）：`KeepScreenOnPolicy` 保屏 + radio 覆盖满额

**性质**：开发验证，非外场战役。**产物按诊断期口径归档，不进任何战役语料。**
**兑现对象**：T25/D-428 挂账已半月的真机验证（「radio 覆盖率预期 2/9→9/9，验证落账前本条不闭环」）。
**设备**：P40 Pro（`8MY0221126002537`）。**服务端**：E-01（`https://120.79.148.0:8443`，bare-IP 通道，只读使用）。

## 1. 验证判据与结果（两条，均通过）

### 判据①：autorun 期间屏幕保持常亮（直接机制）

**设置**：`stay_on_while_plugged_in=0`（**系统级 stayon 全程关闭**——T25 验的正是「不赌系统设置、
只靠窗口 flag」，若 stayon 开着则验证无效）；`screen_off_timeout` **临时改为 30000ms**
（原值 600000ms=10 分钟，比 run 还长，不改则屏本来就不会灭、测试会空过）。

**关键**：`adb shell` 的 `dumpsys`/`logcat`/`settings get` **不算用户活动、不重置屏超时计时器**，
故最后一次用户输入（解锁 swipe）之后的所有采样都是干净的观测。

| 轮次 | 最后用户输入 | 采样结果 | 判读 |
|---|---|---|---|
| 第 2 轮 | 12:54:28 swipe | 12:54:35 / :45 / :56 / 12:55:06 / :16 / :26 / **:37** 全部 `Awake` | **69 秒无用户输入未灭屏**（超时 30s） |
| 第 3 轮 | 12:56:1x swipe | 12:56:40 → **12:57:32** 全部 `Awake` | **76 秒无用户输入未灭屏** |

→ **`FLAG_KEEP_SCREEN_ON` 确实在工作。** 原始采样见 `screen_watch_round3_completed_run.tsv`
（第 3 轮，含 WiFi 开关列）与 `screen_watch_round2_aborted_run.tsv`（第 2 轮）；
各文件的**证据有效窗口**见 §6。

### 判据②：radio 采集覆盖满额（D-428 预期的后果）

`run_id=01a01860-c6ef-757a-9035-a5240e23f8c5`（quick 模式，3 场景，`status=completed`）：

| 场景 | radioRat | RSRP(dBm) | SINR(dB) | PCI | sampledN | **radioStale** |
|---|---|---|---|---|---|---|
| s1_chat | NR | -83.0 | 23.0 | 672 | 27 | **0** |
| s2_coding_agent | NR | -83.0 | 24.0 | 672 | 63 | **0** |
| s3_multimodal | NR | -82.0 | 24.0 | 672 | 30 | **0** |

→ **radio 覆盖 3/3（quick 模式满额），`stale=0` 全部为真采**，`radio_sample` 表本 run 落库
**121 条**。

> **一处必须记下的读法**：收工日志里 `DB_WRITE ... radio_samples_pending=0` **不等于没采到**
> ——那是「写库时待刷新队列为空」（已提前刷盘）。**只看这个计数器会得出完全相反的结论**，
> 必须直接查库（本次查得 121 条）。

## 2. 三个过程中的真实发现（均为实测，非推理）

### 2.1 `--es transport cellular` 的真实适用条件——订正 D-481 我自己的说法

D-481 里我把它记作「比物理关 WiFi 更精确、更可逆的蜂窝路径选择机制」。**本次实测更精确**：

- **WiFi 在场且蜂窝处于冷态时会失败**：首轮 `NET_BIND_FAIL transport=cellular
  error=network_not_ready_within_15000ms`。查 `dumpsys connectivity` 实为**系统里只有 1 个
  真实 NetworkAgent（WiFi），完全没有活的蜂窝网络**（那些 `Transports: CELLULAR` 字样是
  NetworkRequest 声明，不是实存网络），故 15s 内拿不到 validated 蜂窝。
- **蜂窝已起来后即可用**：关 WiFi 让蜂窝实例化并 validated 之后，即便 WiFi 自动重开，
  `NET_BIND transport=cellular validated=true` 也**成功**。

→ **结论订正为**：该机制**依赖已存在的 validated 蜂窝网**，不能把冷态蜂窝唤起；
`DEFAULT_ACQUIRE_TIMEOUT_MS=15_000`（`NetGuard.kt:43`）对冷启动蜂窝不够。

### 2.2 本机 WiFi 会自行重开，并会拆掉绑定的蜂窝网

`svc wifi disable` 后 `wifi_on=0` 生效，但约 1-2 分钟后 EMUI 自行把 WiFi 重新打开
（`wifi_on=1`）。第 2 轮 run 因此在 s2 中途被 `bound_network_lost` 中止
（`RUN_ABORT ... reason=bound_network_lost`）。

→ **fail-closed 守卫（R-01）两次都正确工作**：一次拒绝在环境不就绪时放行（`NET_BIND_FAIL`），
一次在路径变化时中止而**没有伪装成蜂窝继续测 WiFi**。这是守卫在真实条件下的正面证据。
→ **操作建议**：蜂窝窗要么缩短 run 时长（quick 而非 forensic），要么先查明并关闭 WiFi 自动重开。

### 2.3 `adb ... cat > file` 的二进制破坏，`cmd /c` 也救不了——`exec-out` 才行

拉 113MB 的 Room DB 时：

| 方式 | 拉取字节数 | 设备端字节数 | 结果 |
|---|---|---|---|
| bash `adb shell ... cat >` | 113,733,693 | 113,557,504 | **多 176,189 字节**，`sqlite3` 报 `database disk image is malformed` |
| PowerShell `cmd /c ... >` | 113,733,693 | 113,557,504 | **仍多 176,189 字节**（D-488 记的解法在大文件上不成立） |
| **`adb exec-out ...`** | **113,557,504** | 113,557,504 | **逐字节一致，可正常查询** |

多出的字节数恰为文件中 `0x0A` 的个数（LF→CRLF 转换）。**`exec-out` 是唯一正确解法**，
建议后续拉设备二进制一律用它。

## 3. 顺带产出：真实蜂窝路径 RTT（加厚 T63/D-498 的结论）

本 run 三场景 `n1_rtt_p50_ms` = **59.996 / 64.738 / 64.978 ms**（NR_SA，RSRP -82~-83dBm）。
另有 run 前 `ping 120.79.148.0` 实测 2/2 通、44.690–122.385ms。

→ 全部落在 T63 那 489 个历史样本的分布内（蜂窝 max 86.71ms），**再次远离 267–400ms 的
临界区**，与 T63「目标网络条件下 RTT 不会超过临界值」的结论一致。

## 4. 边界与如实标注

- **未达成 D-428 字面的「9/9」**：那是 forensic 模式（9 场景）的口径。本次因 §2.2 的 WiFi
  自动重开风险改用 quick（3 场景，约 4 分钟），得 **3/3 满额**。**机制结论不受影响**
  （覆盖率是否满额与场景数无关），但**字面数字与 D-428 不同，如实标注不冒充**。
- 三场景 `validity=valid_low_confidence`：是既知的 `SCORER_LOW_CONF` 现象（D-466：73/73 全低置信，
  真机制是场景级样本数结构性低于打分器门槛），**与 T25 无关**，不作为本次验证的问题。
- **设备收尾复验**：`wifi_on=1`（原值）、`screen_off_timeout=600000`（原值）、
  `stay_on_while_plugged_in=0`（全程未动）、无 aneb 残留进程、焦点回华为桌面、哨兵已删。
- **E-01 只读使用**：仅 GET profiles + 正常测量端点 + 结果 POST（App 既定行为），**未改任何配置**。

## 5. 关于 logcat 归档的如实说明

**本目录不含 logcat 文件**：收工时先 `force-stop` 才想起导出，而 Android 的 logcat 环形缓冲
在应用停止后已被覆盖，导出结果为 0 字节。**空文件比没有文件更误导**（读者会以为有日志），
故删除而不是留一个空壳。

run 全程的关键日志已由本会话的 Monitor 逐条捕获并转述进 §1/§2 与 D-509 条目
（`RUN_START` / `NET_BIND` / `NET_BIND_FAIL` / `SCENARIO_START` / `RUN_ABORT` /
`DB_WRITE` / `RUN_END` 均逐字引用）；数值结论则全部来自**设备 Room DB 的直接查询**
（比 logcat 更权威）。

**两条教训**：
1. 下次窗口应在 `force-stop` **之前**导出 logcat。
2. 本节自身也踩了一次坑——用 bash heredoc 内嵌 python 写含反引号的文本时，
   **反引号被 shell 当成命令替换**（`force-stop: command not found`），内容被静默吃掉。
   含反引号/中文标点的文本一律写独立脚本，不塞进 shell heredoc。

## 6. 采样文件的证据有效窗口（读者必读）

两份 TSV 都**完整保留了采样器的全部输出**（分别 90 行 / 40 行），但**只有一段是有证据意义的**：

| 文件 | 对应轮次 | **证据有效窗口** | 该窗口外为什么无意义 |
|---|---|---|---|
| `screen_watch_round2_aborted_run.tsv` | 第 2 轮（forensic，中途 `bound_network_lost` 中止） | **12:54:28 → 12:55:37** | 12:54:25 之前是我唤醒前的自然睡眠态；run 已于 12:55:03 中止 |
| `screen_watch_round3_completed_run.tsv` | 第 3 轮（quick，`completed`） | **12:56:1x → 12:57:32** | 见下 |

**13:00 之后的采样一律不具证据意义**——彼时我已把 `screen_off_timeout` 还原为 600000ms
（10 分钟），屏幕保持 `Awake` 只是长超时的自然结果，**与 `FLAG_KEEP_SCREEN_ON` 无关**。
文件尾部一直到 13:08 的 `Awake` 记录属于此类，**不要据其加强结论**。

> 归档时这两份文件曾被误当作已完结而复制了截断版（49/90、29/40 行），后台采样器完成通知
> 到达后发现并补全。**教训：后台采集器的产物要等它真的结束再归档**，否则归档的是半截。

---
*T25 真机验证 · DW-20260819-01 · 2026-08-19（真实历，D-494 校正后）· 兑现 D-428 挂账*
