# ANEB 发射台准备蓝图索引（launchpad-prep）

> 2026-07-18 · 由并行工作流产出（4 子项目各一 Agent，读代码后出蓝图）。
> 性质：实现蓝图 + 精确改动清单 + 测试脚手架 + 解锁后 runbook。产出时未改/未提交任何生产代码。
> 用途：等 PO 8 项决策给具体值 + P40 设备经 SHARED_TEST_STATUS.md 状态机协议解锁到「空闲」后，据此在单设备窗口内高效执行。

## 蓝图清单

| 蓝图 | 阻塞项数 | 现在可验证项数 |
|---|---|---|
| [spine1-api-agent-calibration.md](spine1-api-agent-calibration.md) | 3 | 8 |
| [spine3-portrait-confidence-blueprint.md](spine3-portrait-confidence-blueprint.md) | 5 | 7 |
| [spine4-speedtest-dynamism-blueprint.md](spine4-speedtest-dynamism-blueprint.md) | 5 | 7 |
| [crosscut-device-unlock-udp-contend-runbook.md](crosscut-device-unlock-udp-contend-runbook.md) | 3 | 7 |

## 跨蓝图挖出的「现在可验证」代码隐患（下一代码轮首选，非本轮范围）

- ✅ **已修（observationId 碰撞风险，spine-1）**：`observationId` 增 `subjectGroupId` 参并追加其 8 位短哈希（`apiprobe-<provider>-<ms>-<subjHash8>`），同毫秒跨 subject 现产出不同 id，杜绝 Codex `duplicate_observation_id_within_partition`。18 单测绿（含去歧义用例）。同 subject 同 ms 重复触发的边界可接受（探针单次手动）。
- workloadKind 应与请求体同源（spine-1）：ApiProbe.run 目前请求体恒 text，而 observation 的 workloadKind 来自 sink，可能 body=text 却标 image。修：run 增 workload 参，请求体与标注同源。

这两项锁无关、可 JVM 单测、非投机——建议作为设备/PO 解锁前的下一代码轮首个任务。

## 当前阻塞态（2026-07-18）

- 设备：P40 处 Codex 触发的「异常锁定」（E-01 防火墙指纹漂移 exit=97；Verifier T+0/T+10 只读复核反复失败，最新 21:53 e01_probe_failed）。PO 决定等 Codex 走协议解锁到「空闲」，Claude 再 claim。
- PO 决策：8 项已授权推进（2026-07-18），6 项待给具体值（账号/密钥托管/subject/范围/去向/保留）——见 ../AUTHORIZED_TOKEN_CAPTURE_SPEC_2026-07-18.md。
- P2/E-01：归 Codex（部署权 D-35/D-37），我方不碰。
