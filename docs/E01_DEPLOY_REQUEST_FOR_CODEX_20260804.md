# 给 Codex 的 E-01 部署请求单：s4_throughput profile 服务端支持（2026-08-04，D-481/D-483）

> # 🔴 2026-09-04 重大修订（D-699）——请先读本块再读下文
>
> **本单的隐含前提「服务端支持了 s4 就能采到 s4 数据」已被实测推翻。范围须扩到客户端。**
> 下文 §1–§6 写于 2026-08-04，其**服务端部分的技术内容仍然正确且仍然需要**；
> 但**只做服务端不足以解阻**，且**本单不再主张部署我方编译的二进制**。三条实测：
>
> **①「部署我方二进制」这条选项须撤回（不是待商榷，是会造成真停服）。**
> E-01 线上二进制是贵方血统 `aneb-server/0.8.3`（`vcs.revision=55554d0e…`，在 C 树不存在），
> 其 unit 传 `-execution-profiles` 与 `-udp-echo-addr` 两个 flag，而 C 树 `server/main.go`
> 只定义 9 个 flag——Go 的 `flag.Parse()` 遇未定义 flag 直接 `os.Exit(2)`；配 unit 的
> `Restart=on-failure`/`RestartSec=3` 会进重启循环。且 C 树产物**没有**线上独有的
> `/api/v1/{impairments,token-sim,realtime-sim,udp-echo}` 四端点与 execution-profiles 机制。
> ⇒ **原文第 6 行三选项中，「直接合并本文附的 diff」应理解为在贵方树上做等价改动，
> 而非替换线上二进制。我方明确撤回后者。**
>
> **②只把 `s4_throughput.json` 放进 `/opt/aneb/profiles/` 会得到一个静默残废的 profile。**
> 0.8.3 的 `Phase` 结构体无 `WindowMs` ⇒ 实测该 profile 能加载、能下发，但回传的两个
> `adaptive_*_window` 相位里 **`window_ms:4000` 被静默丢弃，该相位丧失全部时间信息**，
> 全程零告警。（这正是 §1.1 请求新增 `WindowMs` 字段的理由——**该请求依然成立且必要**。）
>
> **③真正的堵点在客户端，这是本单原先完全没有覆盖的一面。**
> 设备上跑的 `com.aneb.probe`（versionCode 20 / versionName 0.2.0）经 APK sha256 逐位比对，
> 唯一匹配 `G:\...\DevSpace\aneb-prototype-0.1-g3-g4-rc\...\probe-prototypeRelease.apk`
> （分支 `codex/issue-17-g3-g4-rc`）——**既不是 C 树，也不是 `aneb-probe-codex-v0.2.0`，是第三条血统**。
> 该树中 `adaptive_download_window`/`adaptive_upload_window` **零命中**（阳性对照
> `token_stream` 24 命中 / `clock_sync` 27 命中 / `download_throughput` 3 命中，量法有效）；
> 而 `download_throughput`/`upload_throughput` 虽然认，其执行路径**只在 `NetworkSpeedEngine` 内，
> 且该引擎硬绑** `PROFILE_ID = "basic_network"`（`NetworkSpeedEngine.kt:389`）。
> ⇒ **即便服务端完全就绪，设备侧也不会执行 s4。**
>
> ## 修订后的请求（一句话）
> **请在贵方 lane 内实现「单流自适应窗口 goodput」这一测量能力（服务端相位字段 ＋ 客户端执行路径），
> 形式由贵方定；我方提供设计意图、判据与 profile 定义作为输入，不主张具体实现，也不再请求部署我方产物。**
> 设计意图见 §2；可直接复用的实测结论见下面「四条硬子结论」。
>
> ## 四条硬子结论（我方实测，可直接用，省贵方一轮试错）
> 1. **用 `duration_ms`，不要用 `window_ms`。** 在 0.8.3 上 `window_ms` 被静默丢弃且相位丧失全部
>    时间信息；`duration_ms` 无损往返（两者均在本地 0.8.3 复现环境实测）。若贵方新增字段，
>    命名沿用 `duration_ms` 可少改一处。
> 2. **单流请写 `parallel:1`，永远不要写 `parallel:0`。** Go 零值 ＋ `omitempty` 使 `parallel:0`
>    与「省略该键」的回传**逐字节相同**——「0 条流」这个意图过不了服务端一个来回。
>    `parallel:1` 与省略则可区分（实测）。
> 3. **量级安全。** s4 的 512MiB 下行 ceiling 与 48MiB 上行 ceiling 均在 0.8.3 限额内
>    （`downloadMaxBytes` 1GiB / `uploadMaxBytes` 64MiB；边界 400 与 413 路径实测存在）。
> 4. **新增 profile 对线上是安全的加法，但必须重启才生效，且 fail-closed 到整进程。**
>    实测：往运行中的服务的 profiles 目录 cp 文件是**纯 no-op**（接口仍返回原有条目）；
>    而截断文件 → `unexpected end of JSON input` 退出码 1，重复 `profile_id` → 退出码 1。
>    另实测：新增一个 profile 后其余条目的 canonical-JSON **逐条 identical**，
>    `serverinfo.execution_capabilities` 段两侧 sha256 **byte-identical**（`-profiles` 与
>    `-execution-profiles` 是独立参数，后者只遍历子目录）——**既有 preflight 不受影响**。
>
> ## 我方尚未验证的三件（诚实边界，勿当结论）
> (i) 贵方客户端是否把 `duration_ms` 实现成「到点 cancel 的硬窗口」——0.8.3 只在
>     `handlers_download.go:19` 的**注释**里这么说，注释不是被执行面；
> (ii) `parallel:1` 是否真＝恰好一条流（服务端从不读该字段，无代码依据）；
> (iii) `download_throughput` 下 `bytes` 是 ceiling 还是 exact，以及 `parallel>1` 时是每流还是
>     总量（**4 倍差**）。贵方 `basic_network` 用的是 `parallel:4`，这条对读数影响最大。
>
> **本修订块的取证方式**：G 树全程只读（源码复制到 scratchpad 后构建，`profiles.go` mtime 未变）；
> E-01 全程只读（无写入、无重启）；设备全程只读（未 force-stop、未启动 App、未改设置）。

> **性质**：本文是**请求单**，不是部署操作——**E-01 部署所有权=仅 Codex**（D-35/D-37，
> `docs/launchpad/README.md:34`："P2/E-01：归 Codex（部署权 D-35/D-37），我方不碰。"）。
> C 树本文全程未对 E-01 做任何写操作，也不会。是否采纳、何时采纳、以何种形式采纳
> （直接合并本文附的 diff / 在贵方 G 树 `aneb-probe-codex` 基础上另行实现等价改动 /
> 暂缓），均由 Codex 判断。
> **权威口径提醒**：`TEST_SERVER_CAPABILITIES.md`（G 树 `aneb-probe-codex-v0.2.0/docs/`）
> 是 E-01 唯一权威能力合同，本文只是一份待评估的输入，不预设它已经/应该被采纳。

## 0. 触发背景

T49（吞吐探针蜂窝真实路径验证窗，为批④三常量拍板取真实 RTT 主导度边界样本）开窗前做
WiFi 零成本预检，实测 E-01 当前 `/api/v1/profiles` 返回：

```
versions=s1_chat@0.2.1;s2_coding_agent@0.2.1;s3_multimodal@0.3.0
```

**`s4_throughput` 不在列**——C 树批②（D-477）已完成的服务端契约扩展从未同步到 E-01。
若不做这一步核实，T49 原计划的 5-10 发蜂窝采集会全部静默产出零 s4 数据（详见 D-481）。
批④（吞吐探针 `RTT_DOMINANCE_MIN`/`ABS_FLOOR_MS`/`MIN_BYTES_FLOOR` 三常量拍板）在拿到
真实边界样本前无法定案，这条部署因此成为关键路径上的外部依赖。

## 1. 要部署什么

两处改动，来自 C 树 commit **`6f79a0d`**（`feat(D-468): T47批②——Profile相位契约定稿+
对拍守卫扩展(双端同步)`，当前分支 `feat/result-dev-v2` 上的祖先提交，`git merge-base
--is-ancestor 6f79a0d HEAD` 已验证）：

### 1.1 服务端源码改动（需要重新编译二进制）

`server/profiles.go` 的 `Phase` 结构体新增一个字段：

```go
WindowMs int `json:"window_ms,omitempty"`
```

纯 additive——不删不改任何既有字段，`omitempty` 保证旧 profile（s1/s2/s3）序列化结果
逐字节不变。配套改了 `server/profiles_test.go`：把两处硬编码"恰好 3 个 profile"的断言
（`TestLoadRealProfiles`/`TestProfilesEndpoint`）放宽为"至少 N 个 + 逐 ID 存在性检查"
（该硬编码本身是 D-477 自查纠正的一处真实回归——新 profile 文件落地后会先炸掉这两个
既有测试），并新增 `TestLoadS4ThroughputAdaptiveWindowPhases`。

获取完整 diff：

```bash
git -C "<C树路径>" show 6f79a0d -- server/profiles.go server/profiles_test.go
```

### 1.2 新增数据文件（不需要重新编译，放进 profiles 目录即可生效）

`profiles/s4_throughput.json`（与仓库另一份 `spec/profiles/server/s4_throughput.json`
逐字节相同，本人现场重新计算确认——两者 SHA-256 均为
`57cfba7704c863d2a07aaeb76fee7d87f7c63db52ffb693abf06c43695535d97`）：

```json
{
  "profile_id": "s4_throughput",
  "version": "0.1.0",
  "kpi_set": "agent-qoe-kpi-v0.3",
  "phases": [
    { "type": "clock_sync", "samples": 20 },
    { "type": "adaptive_download_window", "window_ms": 4000, "bytes": 536870912, "chunk_kb": 256 },
    { "type": "adaptive_upload_window", "window_ms": 4000, "bytes": 50331648, "chunk_kb": 64 },
    { "type": "clock_sync", "samples": 20 }
  ]
}
```

### 1.3 测试证据（本人现场重跑，非转述历史记录）

```
$ cd server && go test ./... -run TestLoadS4ThroughputAdaptiveWindowPhases -v -count=1
--- PASS: TestLoadS4ThroughputAdaptiveWindowPhases (0.01s)
PASS
ok      aneb-server     1.772s

$ go test ./... -count=1
ok      aneb-server     5.599s   （其余子包 tools/capture 等报 [no test files]，与本次改动无关，符合预期）
```

### 1.4 关于"直接部署这个 commit"的提醒

C 树是**多会话共享工作区**，HEAD 会持续前进且常态性地带着其他会话进行中、尚未提交完成
的改动（例如本文撰写时工作树里就有另一会话 T48 UI 改造批次的未提交编辑）。**建议 Codex
只取上面 1.1/1.2 两处、`6f79a0d` 这一个精确提交点的内容**，不要理解为"拉 C 树最新代码
部署"。若 Codex 的 E-01 服务端源码本就独立维护在 G 树（`aneb-probe-codex-v0.2.0`，
`TEST_SERVER_CAPABILITIES.md` 所在处）而非直接复用 C 树 `server/`，本节应视为**改动
规格**（供在 G 树对应位置实现等价改动），而非可直接合并的 patch——C 树没有核实过
E-01 的实际部署源头是 C 树 `server/`、G 树镜像、还是另一套独立实现（D-481 已如实记此
遗留疑问，不假装已核实）。

## 2. 受保护变更步骤建议（供参考，非强制流程）

1. **预检指纹**：部署前对 E-01 防火墙规则做一次快照（`iptables-save`/`ip6tables-save`
   或贵方现有等价指纹机制）。**若指纹哈希包含运行时时间戳行（如 `Generated by`/
   `Completed on`），建议先裁掉这些行再哈希**——见下文风险①，这正是上次误报的根因，
   而不是"重新做一遍旧流程"就能自动避开。
2. **限定范围变更**：本次改动只有 1.1/1.2 两处，均为 additive（新增字段/新增 profile
   文件），不涉及防火墙/TLS/端口/网络配置层，理论上零 touch 到与本次无关的表面。
3. **回滚**：部署前保留当前二进制与 `profiles/` 目录快照；验证不通过时原样恢复，无需
   额外设计新回滚路径。
4. **变更后验证**：客户端请求 `GET /api/v1/profiles`，确认返回体 `versions` 列表包含
   `s4_throughput@0.1.0`（字段名与本人预检 logcat 观测到的真实响应结构一致——见下方
   "验证方法参考"）；若贵方口径是回写 `TEST_SERVER_CAPABILITIES.md`，建议按 D-37 先例
   一并标注版本号与部署时间。

**验证方法参考**（本人今日 T49 预检时的真实 logcat，可直接复用同一判据）：

- 缺失时：`PROFILES source=server versions=s1_chat@0.2.1;s2_coding_agent@0.2.1;s3_multimodal@0.3.0`
  （无 s4_throughput）
- 期望部署后：同一行的 `versions=` 应变为四项，含 `s4_throughput@0.1.0`

## 3. 风险点（如实列，不代为下判断）

**① 历史先例——E-01 曾因一次部署触发防火墙指纹漂移与自触发"异常锁定"**：
2026-07-18，Codex 对 E-01 完成 0.8 版本合同验收部署后，共享防火墙指纹发生变化，自动
回滚到 0.7.0，但回滚验证 `exit=97`（指纹仍与冻结值不一致），触发"异常锁定"
（`docs/launchpad/crosscut-device-unlock-udp-contend-runbook.md:49-52`）。根因由 Codex
自行定位：旧部署器把 `iptables-save`/`ip6tables-save` 输出里的 `Generated by`/
`Completed on` 运行时时间戳纳入了全量哈希，纯时间行漂移被误判为指纹变化；修复（裁掉
时间戳行）后三次连续采集哈希一致。**该记录截至找到的最后一条相关条目仍停在"E-01 保留
0.7.0，未重新部署 0.8"**——本人没有找到后续"0.8 成功部署"的确认记录，如果这仍是事实，
本次请求可能是该修复后的**第一次实际部署验证**，值得贵方留意，而非默认"这个坑早已趟
过、可以放心"。

**② 本次改动内容本身范围很小**：纯 Go 结构体新增字段 + 新增 JSON 数据文件，不触碰
网络/防火墙/TLS 配置层，从改动内容看重演①的先验概率应该较低。但①的根因是**部署器
本身**（对指纹计算方式的缺陷），不是"改动大小"——如果贵方部署脚本自那之后未有过其他
稳定部署验证，仍建议按第 2 节走一遍预检，不因"这次改动小"而跳过。

**③ E-01 与 C 树/G 树代码状态之间可能存在既有、独立的漂移，与本次改动无关**：本人预检
时同时观测到一条既有信号——`PROFILE_WARN version_mismatch_server=s1_chat@0.2.1;
s2_coding_agent@0.2.1;s3_multimodal@0.3.0_assets=s1_chat@0.2.0;s2_coding_agent@0.2.0;
s3_multimodal@0.3.0_(以服务端为准)`——即 E-01 上 s1/s2 的服务端版本号（0.2.1）已领先于
C 树本地 assets（0.2.0）。这与本次 s4_throughput 部署无关，只是提示"E-01 当前状态"与
"C 树代码状态"之间本就不是实时同步的，供风险评估时一并纳入背景。

## 4. 与 Codex 部署节奏的兼容性

（有意留空——由 Codex 视自身排期与在办事项判断是否、何时安排，C 树不预设时间表或
优先级。）

## 5. 采纳方式

Codex 自行评估是否、以何种形式采纳（直接应用 1.1/1.2 的 diff / 在 G 树独立实现等价
改动 / 部分采纳 / 暂缓）。若采纳并部署，恳请按 D-37 先例回写
`TEST_SERVER_CAPABILITIES.md` 留痕；C 树这边会在下一次 T49 类窗口用第 2 节"变更后验证"
的同一判据独立复核，不会假定部署已完成。本文不改任何 E-01 配置——纯请求单交付。

## 6. 追记（2026-08-15，D-495）：E-01 实况复核——两处过时信息订正 + 兼容性留白已有具体实质

本节为 v4 在真实历 2026-08-15（D-494 时钟校正后）对 E-01 的只读复核结果，供 PO 转交时
以最新实况为准：

**6.1 风险①的"首次部署验证"注记已过时**：E-01 现为 **`aneb-server/0.8.3`**（本人 curl
bare-IP 通道实测 `X-Aneb-Server: aneb-server/0.8.3`）；G 树权威合同
`TEST_SERVER_CAPABILITIES.md` 记载 0.8.2 于 2026-07-27 经完整受保护切换部署成功（锁内验证
运行包/能力/smoke/共享指纹/回滚面五关）——**0.8 事故后的部署管线已恢复并至少成功运行过
两次**（0.8.2→0.8.3），§3 风险①"本次可能是修复后首次实际部署验证"不再成立，第 2 节的
受保护步骤建议仍然适用但其紧迫性背景已缓和。（另注：合同文档记载 0.8.2 而实况 0.8.3，
文档滞后一版，属 Codex lane 的回写事项，本文不代办。）

**6.2 `s4_throughput` 仍未部署**：`/api/v1/profiles` 实测服务 4 个 profile：
`basic_network@0.1.0`（新增）+ s1/s2/s3。**本请求单的核心请求仍然有效**。

**6.3 §4 兼容性留白已有具体实质——Codex 已上线自有吞吐相位契约**：新 `basic_network`
profile 含 `download_throughput`（`parallel:4, duration_ms:10000`）与 `upload_throughput`
（`parallel:2, duration_ms:10000`）两个相位——**多流并行、固定时长**的设计。与本请求单
1.1/1.2 的 `adaptive_download_window`/`adaptive_upload_window`（**单流、window_ms**）是
两种不同的测量哲学，且按我方 spec §8.0 的术语纪律，两者**互补而非竞争**：
- `basic_network` 的多流并行≈链路容量方向（对标 SpeedTest 口径）；
- `s4_throughput` 的单流 goodput 是 token_experience 模式的诊断探针，单流恰是其**有意为之
  的口径边界**（spec 明载"单流应用层 goodput 探针，非真实链路容量"）。

因此本请求不与 `basic_network` 重复，也不请求改动它；但 Codex 评估时自然会面对"同一台
server 维护两套吞吐相位类型"的维护性问题——**这正是 §4 留白等待贵方判断的事项**，如实
点出，不代为决策。可能的走向（仅列举供参考）：(a) 照 1.1/1.2 原样新增两个相位类型；
(b) 在贵方 `download_throughput` 相位上扩一个 `parallel:1` + 窗口语义的变体供 s4 复用
（需我方客户端相应适配，工作量归我方，若贵方倾向此路请回传相位契约细节）；(c) 暂缓。

---
*E-01 部署请求单 v1 · 2026-08-04 · 触发自 T49/D-481 预检发现 · 关联 D-477(批②代码)/
D-478(批③代码)/D-469(批④三常量待批) · §6 追记 2026-08-15（D-495）*
