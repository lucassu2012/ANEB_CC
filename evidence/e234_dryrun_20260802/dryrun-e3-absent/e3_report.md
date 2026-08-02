# E3 `A0 → A0′` 间隔 —— 判读结果

> ⚠ DRY_RUN_SIMULATED —— 本页每一个数字都由模拟器生成，只证明装置本身是否正确；**不得入任何统计池、不得作标定值**。

> 出处：`spec/adapters/INSTRUMENTATION_SPEC.md` §3.3 E3、§6-6。
> **这不是「误差」，是被测 App 的输入处理耗时**（spec 原话）。
> 因此本页没有 PASS/FAIL 型的门 —— 给一个被测对象的性质安一个门，
> 等于把它说成我们打点的性质。

## 1. 判据可得性

| 项 | 值 |
|---|---|
| A0 判据（通道 C 输入事件时间线） | `不可得` |
| A0′ 判据（通道 A v3 首簇首事件） | `v3-cluster` |
| framestats 行数（去重后 / 重复丢弃） | 174 / 30 |
| 切轮方式（轮数） | `operator-marks`（6） |
| 可用内容事件 / 他包滤除 / 量纲拒收 | 174 / 1 / 0 |

**A0 不可得的原因**：本设备的 framestats 表头没有 OldestInputEvent/NewestInputEvent —— 它只有 `InputEventId` 这类**标识符**，不是时戳。A0 的主判据在这种形态下取不到。实际列：Flags, FrameTimelineVsyncId, IntendedVsync, Vsync, InputEventId, HandleInputStart, AnimationStart, PerformTraversalsStart, DrawStart, FrameDeadline, FrameInterval, FrameStartTime, SyncQueued, SyncStart, IssueDrawCommandsStart, SwapBuffers, FrameCompleted, DequeueBufferDuration, QueueBufferDuration, GpuCompleted, SwapBuffersCompleted, DisplayPresentTime, CommandSubmissionCompleted

> 这一条不是「没数据」，是**这台设备的 framestats 形态里没有那两列**。
> 列名已逐字印在上面，下一个人才判断得了是设备形态变了还是我们读错了。

## 2. `A0 → A0′` 分布

| method | n | dropped | p50 (ms) | p90 (ms) | p99 (ms) | min | max |
|---|---|---|---|---|---|---|---|
| `—` | 0 | — | — | — | — | — | — |

## 5. 逐轮

| 轮 | 簇数 | 窗内输入事件数 | A0→A0′ (ms) |
|---|---|---|---|

