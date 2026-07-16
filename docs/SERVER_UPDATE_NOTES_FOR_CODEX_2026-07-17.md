# E-01 服务器更新说明(给 Codex)— 2026-07-17

> 更新方:Claude(经用户批准)。本文档说明本次部署改了什么、**为什么不影响你现有功能**、以及你可以选用的新能力。
> 部署方式:`scripts/deploy_server.ps1`(交叉编译 linux/amd64 + scp + systemd 重启,共享主机隔离规则未破:未动 node/mongod/防火墙/chrony)。

## TL;DR

- 服务器二进制更新为当前 `feat/result-dev-v2` 树构建(含一批 **additive** 流式/下载机制,全部默认关闭或向后兼容)。
- **s3_multimodal profile 升版 0.2.0 → 0.3.0**:在两段 token_stream 之后各加一个 `download_burst`(12 MiB,chunk 256KB)相位,模拟"AI 返回图片"下行(D1 指标)。
- **你放在 VM 上的 `basic_network.json` profile 原样保留**(部署脚本只覆盖 s1/s2/s3 三个文件)。
- 全端点部署后公网回归通过:`/stream`(profile 路径 + 显式参数路径)、`/upload`、`/download`(显式 bytes + `?profile=`)、`/toolloop`、`/echo`、`/profiles`、`/serverinfo`。
- `X-Aneb-Server` 指纹串与 `/serverinfo` 的 `version` 字段**保持 `aneb-server/0.1.0` 不变**(避免任何指纹匹配破坏);实际构建以本文档与 git 历史为准。

## 1. 对你的影响评估(结论:无破坏)

| 你的现有行为 | 部署后 | 说明 |
|---|---|---|
| `/stream?profile=&phase=` 取流 | ✅ 不变 | prelude 多一个 additive 字段 `ttft_inject_us`(当前恒 0,见 §3);JSON 解析 ignoreUnknownKeys 即兼容 |
| `/stream?tokens=&rate_tps=` 显式参数 | ✅ 不变 | 回归实测 20ms 节奏精确如旧 |
| `/upload` 逐块 `chunk_us` | ✅ 不变 | 响应结构未动 |
| `/download?bytes=&chunk_kb=`(你加的端点) | ✅ 不变 | 语义保留;新增可选 `?profile=&phase=` 从 download_burst 相位取缺省(§2) |
| `/toolloop` / `/echo` / `/results` / `/serverinfo` | ✅ 不变 | 合同字段未动;`/results` 仍只校验必填、不拒新增字段 |
| 你的 `basic_network.json` | ✅ 原样 | 部署脚本 `mv` 仅覆盖 s1/s2/s3 |
| **s3_multimodal 内容** | ⚠️ 升版 0.3.0 | 唯一实质变化,见 §2。若你的客户端对未知相位类型走 PHASE_SKIP(原始行为),s3 run 会跳过该相位继续,不会失败;`profile_versions` 串会体现 `s3_multimodal@0.3.0`(跨时间横比时注意分版) |

## 2. s3_multimodal 0.3.0(唯一 profile 变更)

新相位序列(粗体为新增):

```
clock_sync → upload 1MB → think 2.5s → token_stream 200@40tps
→ **download_burst 12MiB chunk256KB**
→ upload 1MB → think 2.5s → token_stream 200@40tps
→ **download_burst 12MiB chunk256KB**
→ clock_sync
```

- 语义:多模态业务里"AI 返回图片/文档"的下行大对象(PROFILE_FRAMEWORK §2.4/BM-09 口径(b))。
- 客户端执行方式(我方实现,供参考):对该相位 GET `/api/v1/download?bytes=12582912&chunk_kb=256`,计时端点=请求发出→body 排空最后一字节,喂 D1(下行 goodput)KPI。
- `/download` 新增可选 `?profile=s3_multimodal&phase=N`:从该 profile 第 N 个 download_burst 相位取 bytes/chunk_kb 缺省(显式 query 仍可覆盖)。你可用可不用。
- `est_duration_s` 75→82(新相位在 50Mbps 下约 +2×2s)。

## 3. 服务器二进制新增机制(全部 additive,默认不影响既有请求)

以下能力已在二进制中,均由 **profile 声明或显式 query 触发**,未声明/未传参时行为与旧版一致:

| 机制 | 触发方式 | 默认 |
|---|---|---|
| TTFT 驻留注入(`ttft_inject_us` 经 prelude 透出,供客户端剥离) | profile token_stream 相位声明 | 0(不注入) |
| 非平稳解码曲线 `rate_schedule` | profile 声明 | 无 |
| SSE frame-batching(`tokens_per_frame`,1..64) | profile 声明或 `?tokens_per_frame=` | 每 token 一帧(不变) |
| 每模型 token 字节直方图 | profile `token_bytes.histogram` | lognormal(不变) |
| 流内 think 驻留 | profile `think_injections` | 无 |
| `/api/v1/artifact_stream` 下行渐进生成端点(新) | 显式调用 | 不调用即不存在感 |
| `/download?profile=` 相位缺省解析 | 显式传参 | 不传即旧语义 |

当前 s1/s2/s3 profile **均未启用**上述 token_stream 新字段——你的既有 KPI 时序不受影响(prelude 的 `ttft_inject_us:0` 是唯一可见差异)。

## 4. 部署与回归记录

- 时间:2026-07-17(服务重启一次,中断 <2s;当时确认你的 app 不在测试中)。
- 烟测(VM 本机):`/profiles`(s3@0.3.0 + 你的 basic_network 在列)、`/echo` OK。
- 公网回归(客户端路径):`/stream` profile 路径与显式参数路径首帧节奏正常;`/upload` chunk_us 正常;`/download?bytes=` 与 `?profile=s3_multimodal&phase=0`(精确 12,582,912 字节)正常;`/toolloop` 200;`/serverinfo` h3_enabled=true。
- systemd 单元/资源限额(MemoryMax 384M, CPUQuota 120%)与 sysctl(`tcp_slow_start_after_idle=0`)与此前一致,无新增全局变更。

## 5. 你可能想跟进的(可选,不强制)

1. 若你的客户端想测 D1:对 s3 的 download_burst 相位发 GET `/download`,口径=2xx 有效字节×8/耗时(终点=body 排空),失败样本记 null 不记 0。
2. `report_body` 若要落 D1/token 分:服务端 `/results` 不拒新增字段,additive 即可。
3. 横比注意:`profile_versions` 含 `s3_multimodal@0.3.0` 的 run 与 0.2.0 的 run,s3 场景时长/相位数不同,建议按 profile 版本分组对比。

有问题在共享的 DECISION_LOG(D-29/D-30/D-31 及本次部署条目)可溯源。
