# T37：E2 真机采集操作协议

> 一页协议，供大脑按序执行。数据归 v4（本文件作者）首判（E2 是本 lane）。

## ① 前提核查清单

**AnebAccessibilityService 的观察范围**（`app/probe/src/main/java/com/aneb/probe/adapter/AnebAccessibilityService.kt`）：
- **不按包名过滤**——`onAccessibilityEvent`（:162）对任意前台包都会走到 `logAdapterEvent`，只豁免自身包/IME/`com.android.systemui` 三类（:165-170），**不要求命中 `spec/adapters/` 里已注册规格的 App**。`accessibility_service_config.xml` 也**没有** `android:packageNames` 限制（无该属性=不限制）。
- **`com.aneb.e1stimulus` 在观察集内，无需任何改动**：其 ROI 翻转同时改背景色**和** TextView 文本 `seq=<n>`（`tools/e1_stimulus/.../StimulusActivity.kt:144-145`，注释原文："纯色块变化不派发 `TYPE_VIEW_TEXT_CHANGED`"，故设计上专门带了文本变化这一路）——`TYPE_VIEW_TEXT_CHANGED` 正落在 `AnebAccessibilityService` 订阅的事件类型内，会触发 `logAdapterEvent`。**这不是 E2 真正需要的信号**（E2 的通道 A 输入是真实目标 App 的观察，不是刺激源自身），但可作为**冒烟自检**：若钉桩窗口的 adapter.log 里出现 `pkg=com.aneb.e1stimulus` 的行，说明"无障碍服务确实在收事件"这条链路本身是通的；`e234_session.content_events(lines, pkg)` 按 `pkg` 过滤，这类行不会污染真实分析（落入 `dropped_pkg`）。
- **⚠️ 唯一真实风险点（`evidence/e1_realdevice_20260802/QUICKCHECK_MEMO.md` §④ 已记，本次复核未变）**：`logAdapterEvent` 首行是 `if (!BuildConfig.DEBUG) return`——**若设备装的是 release 签名包，`ADAPTER_EVT`（含 `t_boot_ns`）永远不会打印，且不报错，会被误读成"改动没生效"**。采集前必须核实：
  ```
  adb shell dumpsys package com.aneb.probe | grep -i -A2 "applicationInfo\|flags="
  ```
  确认 `flags` 含 `DEBUGGABLE`。
- **无障碍服务在位性只读查**（`docs/launchpad/crosscut-device-unlock-udp-contend-runbook.md:261` 已有先例）：
  ```
  adb shell settings get secure enabled_accessibility_services
  ```
  确认列表含 `com.aneb.probe/com.aneb.probe.adapter.AnebAccessibilityService`；`adb shell dumpsys accessibility | grep -A3 AnebAccessibilityService` 看是否 bound。**已知坑（D-50）：`force-stop com.aneb.probe` 会杀服务且系统不自动重绑**——若近期 force-stop 过 `com.aneb.probe`（`e234_collect.py` 的 `_pin` 只 force-stop 刺激源 `com.aneb.e1stimulus`，不碰 probe，正常流程不触发这个坑；但若操作者手动 force-stop 过 probe，需重新开关一次无障碍设置触发重绑）。

## ② 命令序列

目标 App 用 `com.larus.nova`（豆包，已有规格）；ROI 沿用 `tools/e234/README.md` 现成示例（**未标注为实测校准值，若通道 B 全程零方差，先怀疑这个坐标**，见④）：

```bash
python tools/e234/e234_collect.py --serial <serial> --pkg com.larus.nova \
    --roi 60,900,960,600 --allow-real-device --device-window <任务板窗ID> \
    --session-seconds 600 --framestats-period-s 20
```

**不加 `--pin-through-session`**——该旗标只用于 `--pkg` 即刺激源本身的自测场景，
真实 App 测试要靠中段窗口操作者手动前台驱动（脚本自己的文档，:376-380）。

**中段窗口**（脚本 `_pin_before` 结束后到 `_pin_after` 开始前，`--session-seconds` 秒内）：
操作者切到豆包前台，真人对话若干轮；每轮按标记键（终端会提示）：
`t`=本轮开始、`s`=回答首字上屏（Compose 栈可选）、`a`=回答完成、`q`=结束采集。
**至少留 2-3 轮完整对话**——零标记时 `e2_analyze` 会把整段判成"一轮"（n 结构上=1，
不是错，但撑不起分布）。

## ③ 预期产物与判读入口

`--out` 落 `evidence/e234/<timestamp>/`，应含：`stim_pre.log`/`stim_post.log`
（各若干 `FLIP`+`COMMIT` 行，`e1_analyze.clock_offset_ns` 靠它算 BOOT-MONO 偏移）、
`adapter.log`（**关键**：应有大量 `ADAPTER_EVT type=content ... pkg=com.larus.nova
... t_boot_ns=<ns>` 行——这是通道 A 的输入）、`sf_latency.txt`/`framestats.txt`
（通道 C）、`screencap_index.jsonl`（通道 B）、`mark_rtt.jsonl`（操作者标记）、
`collect_notes.json`（元数据，含 `layer` 是否找到）。

判读：
```bash
python tools/e234/e2_analyze.py --run-dir <run> --pkg com.larus.nova
```

`|t_A-t_C|` 首算口径（`e234_common.py`/`e234_session.py` 既有实现，不新写判据）：
两侧**各自独立**分簇（`split_clusters`，400ms 门限，从 `ObsStats.kt.CLUSTER_GAP_NANOS`
取，不写死）——通道 A 的 A2=次簇首事件，通道 C 的 A2=同判据施加在帧
`actual_ns` 序列上的次簇首帧；**不用"commit 之后最近一帧"配对**（那样算出来
恒非负、恒小于一帧，是循环论证）。轮边界靠操作者标记（`segment_turns`）；
每轮 `drop_reasons` 非静默计数（"该轮不足两簇"分通道 A/C 两种原因分别计）。
判定复用 `gate_verdict`（p99 vs 实测帧长，不硬编码 33），**同时**印 `g2_true_meaning()`
（恒 NOT_EXECUTED，本判据不等于 G-2 本义）与有符号分布（方向本身是信息，
spec §2.1：事件不保证像素已上屏，早于/晚于呈现都可能）。

## ④ 中止判据（别在设备旁边猜）

| 观察到的形状 | 含义 | 处置 |
|---|---|---|
| `adapter.log` 全程 0 字节 | 无障碍服务未 bind，或装的是 release 包，或豆包全程没有触发 `CONTENT_CHANGED`/`TEXT_CHANGED`（比如只在后台） | 先查①的 DEBUG 包与 `enabled_accessibility_services`；确认豆包确实在前台且有交互 |
| `adapter.log` 有行但全是 `pkg=com.aneb.e1stimulus`，零 `pkg=com.larus.nova` | 中段窗口豆包没被切到前台，或切了但没产生内容变化事件 | 重采，中段窗口确认操作者真的在豆包上打字/收到回复 |
| `e2_result.json` 的 `clock_pin.status != PASS` | `stim_pre`/`stim_post` 至少一侧无可用 commit 时戳对，或两次钉桩漂移超 1 帧 | 检查 `stim_pre.log`/`stim_post.log` 是否各有 ≥2 组 FLIP+COMMIT；若漂移超限，采集窗口可能过长或设备深睡异常，缩短 `--session-seconds` 重采 |
| `screencap_index.jsonl` 的 `roi_mean` 全程同一个数字 | ROI 坐标没对上响应区（本协议②的示例坐标未经本次实测校准）或响应区全程无变化 | 用 `adb shell wm size`/截图核对 ROI 坐标；不影响 E2 主判据（|t_A-t_C| 不依赖通道 B），可继续判读，但通道 B 佐证段会是 `NOT_EXECUTED`/全零，如实标注不是采集失败 |
| `collect_notes.json` 的 `layer` 为 `null` | `SurfaceFlinger --list` 没找到该包图层，通道 C 会是 `NOT_EXECUTED` | 确认豆包采集期间确实在前台（图层名会变），必要时用 `adb shell dumpsys SurfaceFlinger --list` 现场核对包含目标包的行 |
| `e2_result.json` 的 `channel_a_vs_c.n=0` 但 `clock_pin.status==PASS` | 时钟基没问题，是每轮都"不足两簇"（`drop_reasons` 会写明是通道 A 还是通道 C 那边不闭合） | 查 `drop_reasons`：若是通道 A 侧，可能豆包是 Compose 自绘栈、v3 簇分割在思考期播放动画时不闭合（spec §1.4 已知限制，DeepSeek 同款问题）；换成豆包本就是为了绕开这个 |

---
*T37 · v4 · 2026-08-03 · 依据=`AnebAccessibilityService.kt`/`accessibility_service_config.xml`/
`StimulusActivity.kt`/`e234_collect.py`/`e234_common.py`/`e234_session.py` 源码通读
+ `evidence/e1_realdevice_20260802/QUICKCHECK_MEMO.md`（DEBUG 门控风险先例）+
`docs/launchpad/crosscut-device-unlock-udp-contend-runbook.md`（无障碍在位查先例）*
