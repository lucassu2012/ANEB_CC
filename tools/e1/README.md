# E1 已知真值刺激装置 —— 操作说明与现状

> 承 `spec/adapters/INSTRUMENTATION_SPEC.md` §3.3 实验 E1（T7 产出，2026-08-01）。
> 状态词只用 `PASS` / `FAIL` / `NOT_EXECUTED` / `BLOCKED_EXTERNAL`。
> 下列命令的工作目录**一律是仓根**（D-320：带路径的命令要按它自己的工作目录解析一遍）。

## 0. 设备红线（先读，违反即数据作废）

- **绝不装 P40**。`e1_collect.py` 内置拒绝：型号命中 P40 一族（`ELS-*` / `P40*`）时**即便带
  `--allow-real-device` 也拒**（`tools/e1/tests/test_e1_collect_guard.py` 有反例钉住，
  含「序列号伪装成模拟器」与「大小写／连字符变形」两种绕法）。
- 真机需显式 `--allow-real-device`；默认只放行模拟器。**`--serial` 必填**，不允许缺省挑设备
  ——同刻工作区可能连着别人的手机。
- 刺激源 APK 只装模拟器／受控测试机；它不联网、不申请任何权限（见 `AndroidManifest.xml`）。

## 1. 怎么跑

```bash
python tools/e1/e1_collect.py --serial emulator-5554 --interval-ms 1200 --count 12 --warmup 2 --roi-px 480 --screencap-period-ms 400
```

```bash
python tools/e1/e1_analyze.py --run-dir evidence/e1/20260801-170127
```

离线反例（不需要任何设备）：

```bash
python tools/e1/tests/run_tests.py
```

刺激源重建（**独立 Gradle 工程，刻意不进 `app/settings.gradle.kts`**——`:probe` 的构建面
今日归 v2 的 T1「核对构建对应提交」，本装置一个字节都不碰它）：

```bash
app/gradlew -p tools/e1_stimulus assembleDebug
```

## 2. 装置在测什么

刺激源在已知时刻把一块 ROI 翻色并同步改一段文本，两个时戳都落 logcat：

- `t_req`：调用发生的时刻；
- `t_commit`：`registerFrameCommitCallback` 报的**帧提交**时刻 —— 这才是真值锚点，
  它最接近「像素上屏」（对齐大脑裁定 6-1 ＝ 呈现口径）。

判读脚本对每条通道各算各的 `t_obs − t_commit` 分布（p50/p90/p99 + n），**按通道分列、不合池**
（规格 §1.6 第 4 条）。门限用**实测刷新率**换算的「1 帧」，不硬编码 33 ms
（规格 §3.1；`test_gate_uses_measured_frame_not_hardcoded_33ms` 钉住）。

## 3. 三条通道的现状（2026-08-01 模拟器 dry-run，`sdk_gphone64_x86_64` / 1080x2400 / 60 Hz）

| 通道 | 状态 | 依据 |
|---|---|---|
| **A** 无障碍事件 | `NOT_EXECUTED` | **缺逐事件时戳**。`ADAPTER_EVT` 只在 click 事件打，且字段为 `type/cls/desc/txt_len/pkg`，**不带任何时间戳**；`ADAPTER_OBS` 是 5 秒聚合快照。→ 需 probe 侧补一行（逐个观察事件 emit `elapsedRealtimeNanos`）。**本轮不动 `:probe`**（构建面归 v2），列为待排。 |
| **B** screencap 帧差 | `PASS`（装置跑通） | 实测取帧周期远大于一帧：一轮 18 s 内仅 5 帧、二轮 8 帧（≈2–3.5 s/帧）。**这坐实了规格 §2.2 的 `[INFERRED, HIGH]` 判断**——B 不能用于判 M3 门，只能报采样周期与检出率，脚本亦按此设计（`test_channel_b_reports_period_never_a_timing_error`）。 |
| **C** 系统渲染时间线 | `BLOCKED_EXTERNAL` | 两条支路在本模拟器上都取不到帧行：①`dumpsys SurfaceFlinger --latency <layer>` **只回一行刷新周期 `16666666`、零帧记录**（图层名已确认正确）；②`dumpsys gfxinfo <pkg> framestats` 的 `PROFILEDATA` 块为空——20 帧已渲染、`debug.hwui.profile true` 已置，`Flags,IntendedVsync` 头行仍为 **0 条**。**缺**：一台真机窗口。这正是规格 §7.2 第 4 项「通道 C 在 P40 上的可用性与精度 —— 待实测」，需大脑排窗。 |

> **模拟器数字一律不入任何统计池、不作标定**（T7 纪律⑤）。本节数字只有一个用途：
> 判定装置与脚本是否正确、判定各通道能不能取到数据。

## 4. dry-run 抓出的两个真缺陷（装置存在的意义）

1. **解析正则对不上真实 logcat 行形状**。真实行是 `I/E1_STIM ( 5939): CFG ...`——标签只在前缀
   出现一次、消息体不重复标签；首版写死了 `E1_STIM CFG` 相邻，离线夹具自造成那个样子于是全绿，
   首次上机一行都没解析出来。**夹具自洽 ≠ 与生产者真写出的形状对过账**（D-309 原样形状）。
   已修，并用**实测那三行**作反例钉住。
2. **图层选错且不会报错**。首版取「最后一条含包名的行」，选中了 `ActivityRecordInputSink`
   （输入接收层，永远没有帧），`--latency` 于是安静返回一份空表——**空表与「这层没出帧」长得一模一样**。
   已提取纯函数 `pick_layer` 并用实测 `--list` 输出作反例（选对层／不许再选回输入接收层／
   不串包／选不出是 None 而非猜一个／全是噪声时也返回 None）。

> 第 2 条的连带后果值得单记：**它一度把通道 C 的失败伪装成「图层 bug」**。修好图层后
> `--latency` 仍只回刷新周期，才认出真正的边界是环境而非我的代码。
> 先修掉自己的 bug，才有资格说「这里取不到数据」。

## 5. 产物

`evidence/e1/<YYYYMMDD-HHMMSS>/`：`stim.log`（真值）、`framestats.txt`、`sf_latency.txt`、
`adapter.log`、`screencap_index.jsonl`（每行 `{seq,t_host_ns,path}`）、`collect_notes.json`
（`{screencap_samples,layer}`）、判读产物 `e1_report.md`。

---
*E1 装置 v0.1 · 2026-08-01 · T7 ① · 装置就绪，通道 C 待真机窗*
