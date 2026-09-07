# `e01_profiles_recovered_20260907` · 从 E-01 取回的 0.2.1 版 profile（**证据，非现行配置**）

> 口径：**这是历史证据，不是当前生效的 profile**。`profiles/` 下现行仍是 0.2.0，本目录不参与任何构建或运行。
> 来源：MIW 云端运维会话 `20260827_MIW云端运维接入` 2026-09-07 只读取证，经 PO 转交。

## 为什么要它

101 个真实 run 里 **89 个**的 `profile_versions` 记着 `s1_chat@0.2.1;s2_coding_agent@0.2.1;s3_multimodal@0.3.0`，
而 `0.2.1` 在本仓全历史零命中（D-750）。运维实测确认：**文件在 `/opt/aneb/profiles/`，version 确为 0.2.1**，
并以三条独立证据链锁定「这就是 07-31 至 08-20 全窗口实际加载的那批字节」。

## 校验和（本目录副本，大脑实算）

| 文件 | 字节 | sha256 | 与运维回执一致 |
|---|---|---|---|
| `s1_chat.json` | 939 | `f0209b7cec6efcaff9c325023c77b50cb923b1a0c40bbdbd864916207424dd31` | 是 |
| `s2_coding_agent.json` | 1519 | `8a5a0a006d948b70429a42c2f10601ee70fda78bd5eafc532fda170bb2509cc2` | 是 |

## 🔴 最要紧的一条：**相位结构与仓内 0.2.0 完全相同**（大脑实核）

两版逐相位比对，`type`／`samples`／`tokens`／`rounds`／`bytes`／`duration_ms`／`rate_tps`／`chunk_kb` 全同。
0.2.1 相对 0.2.0 只多了 **`mode_id`** 与一个 **`presentation` 块**（`live_metric_*`／`metric_ids`／`ui_refresh_ms`／`conclusion_policy_id`）——**全是呈现层字段，不碰测量**。

由相位推导的 `expected_n` 两版逐族相同：

| profile | N1/N2 | ITL | T1 | U1 | U2 | D1 |
|---|---|---|---|---|---|---|
| s1_chat（0.2.0 与 0.2.1 同） | 40 | 599 | 1 | 1 | 0 | 0 |
| s2_coding_agent（同） | 40 | 1098 | 2 | 1 | 8 | 0 |

⇒ **D-750 的后果作废**：那 89 个 run 的 `expected_n` 推得出来且与现行推导一致；
D-772／D-761 里「回放腿分母改成可解析版本的 run（12 比 101）」**不再需要**。

## 不回答什么

- **不入 `profiles/`**：现行 0.2.0 是否该升到 0.2.1 是生产配置变更，归 v4 车道且需另裁。
- 那 5 个部署 commit **在本仓不存在**（对象层面即无，非「不可达」），故本目录不是从版本库恢复，是从主机取回。
- `s3_multimodal@0.2.1` 运维侧亦无留存（在窗口之外）。
