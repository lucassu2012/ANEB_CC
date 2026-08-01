# ANEB 发射台准备蓝图索引（launchpad-prep）
> ⛔ **本文中所有 `SHARED_TEST_STATUS.md` 状态机内容已于 2026-07-19 被 PO 废止,不再是设备使用的授权依据。**
> 保留在此仅作历史记录(它解释了当时为什么那样做),**照做会把外场战役卡死在一个永远不会到来的"复核降为空闲"上**。
> **现行流程**(见仓根 `CLAUDE.md`):开测前直接看**设备实况**——确认在线、华为桌面为前台应用,
> 并只读确认无冲突的 ANEB/业务 App/VPN/抓包进程与残留隧道;实况干净则 Claude 或 Codex **可直接开测**,
> 无需 claim / lease / handoff / 第二方释放。测后停掉本次测试起的一切、撤除临时网络规则与 `stayon`、
> 回到桌面并**立即复验干净**。E-01 与阿里云变更仍走各自的受保护预检、限定变更、回滚与变更后复验。


> 2026-07-18 · 由并行工作流产出（4 子项目各一 Agent，读代码后出蓝图）。
> 性质：实现蓝图 + 精确改动清单 + 测试脚手架 + 解锁后 runbook。产出时未改/未提交任何生产代码。
> 用途：等 PO 8 项决策给具体值、且**设备实况确认干净**（见上方现行流程）后，据此在单设备窗口内高效执行。

## 蓝图清单

| 蓝图 | 阻塞项数 | 现在可验证项数 |
|---|---|---|
| [spine1-api-agent-calibration.md](spine1-api-agent-calibration.md) | 3 | 8 |
| [spine3-portrait-confidence-blueprint.md](spine3-portrait-confidence-blueprint.md) | 5 | 7 |
| [spine4-speedtest-dynamism-blueprint.md](spine4-speedtest-dynamism-blueprint.md) | 5 | 7 |
| [crosscut-device-unlock-udp-contend-runbook.md](crosscut-device-unlock-udp-contend-runbook.md) | 3 | 7 |

## 跨蓝图挖出的「现在可验证」代码隐患（下一代码轮首选，非本轮范围）

- ✅ **已修（observationId 碰撞风险，spine-1）**：`observationId` 增 `subjectGroupId` 参并追加其 8 位短哈希（`apiprobe-<provider>-<ms>-<subjHash8>`），同毫秒跨 subject 现产出不同 id，杜绝 Codex `duplicate_observation_id_within_partition`。18 单测绿（含去歧义用例）。同 subject 同 ms 重复触发的边界可接受（探针单次手动）。
- ✅ **已修（workloadKind 与请求体分叉，spine-1，D-66 2026-07-19）**：删 `ObservationSink.workloadKind` 独立字段；`ApiProbe.run` 增 workload 参，`requestBodyJson` 与 observation 的 `workload_kind` **同源**（同一 workload 值），多模态显式 `IllegalArgumentException` 拒——body=text 标 image 的错标路径已不存在。

两项均已闭环（本清单 2026-08-01 对账更新——上一版仍把第二项列为待办，而代码 D-66 当天就修了：被执行的文档最后才被更新，又一例）。

## 当前阻塞态（2026-07-18）

- 设备：P40 处 Codex 触发的「异常锁定」（E-01 防火墙指纹漂移 exit=97；Verifier T+0/T+10 只读复核反复失败，最新 21:53 e01_probe_failed）。PO 决定等 Codex 走协议解锁到「空闲」，Claude 再 claim。
- PO 决策：8 项已授权推进（2026-07-18），6 项待给具体值（账号/密钥托管/subject/范围/去向/保留）——见 ../AUTHORIZED_TOKEN_CAPTURE_SPEC_2026-07-18.md。
- P2/E-01：归 Codex（部署权 D-35/D-37），我方不碰。
