# 派工看板 DISPATCH（协调会话维护，每巡更新；其他会话只改自己那行的「回执」列）

> 立于 2026-09-26（PO 令：「管理好各个对话，加速开发」）。
> 本表只管**在手件、落点、并行安全性**；决策入册仍走 `DECISION_LOG.md`，进度四态仍走 `BRAIN_TASKBOARD.md`。
> ⚠ **本表是协调侧的提案与记录，不是派令**。派令由大脑签发（承 D-582）；PO 直派的另记来源。

## 一、会话名册与在手（2026-09-26 午后；**在手列以大脑 `BRAIN_PROGRESS_REVIEW_20260926.md` §4 为准**，本表只加落点与回执）

| 会话 | 端点 | 战线 | 在手（大脑 §4） | 协调侧补注 | 回执 |
|---|---|---|---|---|---|
| 大脑 | Fable | 复审与裁定 | 追 PO §5 三件；MIW 回端口即按 D-916 判据验链；裁 V1 清单 §6 第 1、2 条 | 已裁（D-917） | |
| V1 | `local_85fe7be8`（61bd2401） | SPEC-1/2 | ①清单已交（`748decb`，D-917 核收）；②设备 L3 前提门只读诊断 | ②已交：D-918，**run6 门通**（14:14:29 手机 ping 223.5.5.5 3/3）；**③新：旧 E-01 证书 enddate 只读核（PO 已授权，见 §四 派工卡）** | |
| V2 | cd5239ba | 编制外 | T78 报告头部版本号 → 一页 PO 摘要 → 待命 | 摘要已交 `467a028` | |
| V3 | `local_b1769d1f` | SPEC-3 | serverBase 归一片（进行中）；裁 V1 清单 §6 第 3、4 条；回执 A-3/A-2 | | |
| v4 | `local_00236200` | SPEC-4 | 2× 余下拦窗与 conditions **继续按批交** | ⚠ 协调侧 M-B-036 提「按落点拆三簇并行」，**大脑 §2-B 自己也写「卡点在 v4 的修法速度与大脑核收速度」**——两者同向，待大脑裁 | |
| Codex | G 树 | **MIW 上 ANEB 服务端应用的维护方**（PO 09-26 明示） | 迁址的**应用侧**：在 MIW 新址上让 ANEB 服务端用 MIW 签的 RSA 证书对外服务 | 渠道按 D-35／D-37 先例：文件经 PO 转交 | |
| MIW 云端运维 | 外部 | **托管 E-01 的平台**（`E01_PROFILE_INQUIRY_20260907.md` 抬头） | 签 RSA 测试证书 → 正式证书；提供新 IP／端口 | 外部往返，PO 转发请求 | |
| 协调（本会话） | 云端 | 巡检／看板／代呈 | 4h 一巡；只读核查 | **不碰 `scripts/`（未点名前）** | |

## 二、判据线：V4 §2 拦窗 11 条 ＋ §8 从未送检 21 条的逐条现状（`df78728`；核状态工作流：每条一名读者＋对抗核查，46 代理 0 失败）

**先说结论**：
- **§2 拦窗 11 条**：#1／#10／#5 已修、#7 已裁 (b)；**其余 7 条（#2 #3 #4 #6 #8 #9 #11）全部核实仍开**，无一被怀疑者推翻。
- **§8 从未送检的 16 条（§8-6..21；§8-1..5 与 §2 重复）**：**14 条仍开**（含 2 条部分修）、2 条本轮不可达（§8-18／§8-20，D-915 下 A-off 不跑，缺陷潜伏）。**「未送检」不等于「没问题」。**
- **会让一次提权窗静默白烧的共 6 条**：§2-8、§2-9、§2-11，**以及未送检堆里的 §8-11、§8-17、§8-19**——后三条若没人核，会在开窗后才冒出来。
- **唯一的「已修」（§8-9，第二批 `0f7d771`）被两名怀疑者推翻 ⇒ 部分修，且修法引入同族回归**：`forward_layer_probe.teardown` 终局标签印「判据 §5 达成」，而 decompose 判据里 §5 是 A-off、收尾是 §6；decompose 经 import 用的是同一个 teardown；新门 `test_forward_probe_teardown_labels.py:139` 把「§5 达成」钉成了期望。

| 条 | 现状 | 白烧 | 簇 | 主落点 |
|---|---|---|---|---|
| §2-2 | 🔴 仍开 |  | A | `scripts/diag/decompose_2x_verdicts.py:verdict_s3 (:370-384 @df78728，只有` |
| §2-3 | 🔴 仍开 |  | other | `decompose_2x_probe.py apply_verdicts:950-959` |
| §2-4 | 🔴 仍开 |  | B | `verdicts.py:32 verdict_identity 签名无 src 入参，:43-44 TWICE 判词写死` |
| §2-6 | 🔴 仍开 |  | A | `verdicts.py:344-346 SKEW=2` |
| §2-8 | 🔴 仍开 | **⚠ 会白烧** | B | `verdicts.py:32/54-59 verdict_identity` |
| §2-9 | 🔴 仍开 | **⚠ 会白烧** | C | `probe.py _reader:457-466` |
| §2-11 | 🔴 仍开 | **⚠ 会白烧** | C | `probe.py pc_ping:685-692 与 dev_ping:694-700 只取 _sent_count` |
| §8-6 | 🔴 仍开 |  | other | `verdicts.py verdict_h2:128-138` |
| §8-7 | 🔴 仍开 |  | other | `probe.py derive_idle_seconds:262-285` |
| §8-8 | 🟡 部分 |  | other | `已修的一半：probe.py cell():503-504 在开成那刻记账，main :852/874/899` |
| §8-9 | 🟡 部分 |  | other | `forward_layer_probe.py teardown()/teardown_labels。窄缺陷` |
| §8-10 | 🔴 仍开 |  | other | `probe.py print_self_id:656-664` |
| §8-11 | 🔴 仍开 | **⚠ 会白烧** | other | `主落点在 probe.py preflight():806-810，pre!=1060 只打印不 SystemExit` |
| §8-12 | 🔴 仍开 |  | B | `CRITERIA §1.3:148/153 预登记的 seq 值域自检` |
| §8-13 | 🔴 仍开 |  | other | `probe.py compile_selfproof:406-407` |
| §8-14 | 🔴 仍开 |  | other | `probe.py apply_verdicts:967` |
| §8-15 | 🔴 仍开 |  | other | `verdicts.py verdict_impostor:169-181` |
| §8-16 | 🔴 仍开 |  | other | `只落判据文档 evidence/c_2x_decompose_20260912/CRITERIA_PREREG.md：①缺 §1.7 第一道` |
| §8-17 | 🔴 仍开 | **⚠ 会白烧** | C | `probe.py run():176-190` |
| §8-18 | ⚪ 本轮不可达 |  | other | `verdicts.py judge_hotspot_off:335/340-341` |
| §8-19 | 🔴 仍开 | **⚠ 会白烧** | B | `probe.py apply_verdicts:910-912，A1 缺 summary 或 T 时 return out 早退，把 C1/` |
| §8-20 | ⚪ 本轮不可达 |  | other | `a_off_stage()` |
| §8-21 | 🔴 仍开 |  | other | `probe.py judge_first_hop:255-256 的 OK 文案写死「同协议同路径」` |

**派工分簇（仍开 21 条）**：
- **A（`verdict_s3`）2 条**：§2-2 ＋ §2-6——同一函数的单位与目击数，门里 FULL 夹具须改成「每 seq 两次」。一人一笔。
- **B（`verdict_identity` 签名＋ probe 两个调用点）4 条**：§2-4 ＋ §2-8 ＋ §8-12 ＋ §8-19。一人一笔。
- **C（采集与零读数路径）3 条**：§2-9（**补丁已备**）＋ §2-11 ＋ §8-17。§8-11 的 S0 半边也挂在 `zero_reading_ok` 上。
- **other 12 条，可再并**：impostor 子簇（§2-3 ＋ §8-14 ＋ §8-15，同在 `apply_verdicts` impostor 循环与 `verdict_impostor` 签名）；teardown 子簇（§8-8 ＋ §8-9 残余）；纯判据文档（§8-16，另 §8-17 顺带改 CRITERIA:615）；单条 §8-6／§8-7／§8-10／§8-11／§8-13／§8-21。

⚠ **冲突预警（已处置）**：协调侧 #9 补丁 v1 有一条门把 §8-19 的缺陷钉成了期望，核状态工作流指出后已改为 v2 并实证不再钉住（见补丁 README 抬头）。

## 三、三条零成本但会在开窗当天咬人的

1. 🔴 **V4 §6 步 0 的「逐字 grep」判据与实现对不上**（协调侧第 162 巡提、至今未动）：
   判据要 `preflight 量法自证：ping -n 1 127.0.0.1 ⇒ sent=1` / `提权检查：已提权`；
   代码印 `-- 量法自证：ping.exe -n 1 127.0.0.1 ⇒ 取到「已发送」= 1（ACP=…）--`（`probe:756`）/ `-- 提权门：IsUserAnAdmin() = True --`（`probe:746`）。
   ⇒ **两道门都真做出来了，逐字验却双双零命中 ⇒ 已修的被读成没修。** 改法：判据改按**内容**判（v4 自己 §9⑥「行号会漂，按内容找」同理；且这批一改行号又漂了一次）。**一行文字，零代码。**
2. ⚪ **21 条从未送检的候选**（D-908：27 条归并只送了 6 条）——修完 11 条拦窗后它们仍在。建议**不逐条投票**，先按「会不会让整窗白烧」做一次粗筛分两类，避免开窗后才冒出来。
3. ⚪ 死函数 `a_off_stage` 的长期处置（D-915 留给 v4 选：删 or 留而入口即抛）——现取「留而即抛」，**记在此处以免下任接手时又被天真接线**。

## 四、E-01 迁址线：PO 09-26 三条答复已到；**大脑 §5 给 PO 的清单以大脑为准**，本节只记分工与派工卡

### PO 2026-09-26 三条答复（原话，协调侧收；请大脑入册）
1. 「**MIW 是服务器，上面有很多应用，其中 ANEB 测速应用就在上面，由 Codex 维护**」
2. 「**D-692④ 选 B**」＝授权执行窗按受保护变更流程办（本机免密 SSH 通道；会话不经手凭据明文）
3. 「**授权只读登 E-01 核证书**」

### 分工（由上三条 ＋ 仓内既有裁定推出）

| 谁 | 管什么 | 依据 |
|---|---|---|
| **MIW 云端运维**（外部） | 平台：签 RSA 测试证书→正式证书；新 IP 120.77.174.207／端口 | PO ①；D-913／D-916；`E01_PROFILE_INQUIRY_20260907.md` 抬头「致 MIW 云端运维：E-01 上 ANEB server」⇒ **MIW 即托管 E-01 的平台** |
| **Codex** | 应用：MIW 新址上的 ANEB 服务端（0.8.3 血统）配新地址、装 MIW 签的 RSA 证书、对外服务；**0.8.3 是否写死旧 IP 由它自己处理，不再是要问我们的问题** | PO ①「由 Codex 维护」；D-35／D-37 未撤销且今日再确认；D-695③ 本树不得重建 |
| **执行窗（V1，61bd2401）** | 旧 E-01 上受保护流程内的操作：**只读核证书**（今日）、迁址前归档 `/opt/aneb/backups`、D-751 捞 `s1_chat@0.2.1` | PO ②③；D-692④ B；D-695① 免密通道在 PC |
| **本方各窗** | `.ctree` 包 6 处常量＋两份 NSC＋parity；`server/` 9 行注释级；D-912 两处脚本；`shaper.ps1 --dst-ip`（提权窗）；V3 serverBase 归一 | V1 清单「现态·代码/配置 9 文件 11 行」；大脑 §4 |
| **PO** | 转 MIW 请求（务必 RSA）；定节点命名与停旧时间；09-30 保险丝拉不拉 | 大脑 §5 ①②④ |

⚠ 大脑 §3 关键路径写的是「MIW 签测试证书 → 验链 → **MIW 正式部署** → App 端点切换」——按 PO ①，「正式部署」里**应用那一半是 Codex 的**，MIW 只出平台与证书。已在 M-B-038 提醒。

### 派工卡 · 旧 E-01 证书 enddate 只读核（PO 已授权；执行人＝持 `~/.ssh/aneb_e01` 的窗，默认 V1；派令仍请大脑签）

**为什么值得先做**：`acme_sslip_cert_20260713.log:100/:104` 记 cron 自动续期计划 **2026-09-10**，仓内**没有其后任何证据** ⇒ 10-11 08:37 是不是硬期限，至今无人核过。一条只读命令即定。

**判据（跑前写死）**
- `notAfter` **晚于** 2026-10-11 ⇒ **已自动续期**，10-11 不再是硬期限，记新到期日；**但**（D-916）若 issuer 仍是 YE2／密钥 ec-256 ⇒ 手机系统锚验不了，**方案 A 换 RSA 照做，只是期限松了**。
- `notAfter` **＝** `Oct 11 00:37:47 2026 GMT` ⇒ 未续期，硬期限成立；顺带看 `acme.sh.log` 为何 09-10 没续（`--alpn` 占 443 失败？）。
- 连不上／命令报错 ⇒ **NOT_EXECUTED**，不得判任一（承 D-916「连不上为未执行不得判不通过」）。

**命令（只读；使用非变更，D-852；stdout 逐字落盘，D-890）**
```powershell
# 在 PC 上的执行窗跑；$out 目录若无则先建
$out = "evidence/e01_migration_20260926"; New-Item -ItemType Directory -Force $out | Out-Null
$f = "$out/cert_enddate_$(Get-Date -Format yyyyMMdd-HHmmss -AsUTC).txt"
ssh -i ~/.ssh/aneb_e01 root@120.79.148.0 'echo "== date -u =="; date -u; echo "== public/cert.pem =="; openssl x509 -in /opt/aneb/tls/public/cert.pem -noout -subject -issuer -enddate -fingerprint -sha256; echo "== 公钥类型 =="; openssl x509 -in /opt/aneb/tls/public/cert.pem -noout -text | grep -E "Public Key Algorithm|Public-Key"; echo "== acme.sh --list =="; /root/.acme.sh/acme.sh --list; echo "== acme.sh.log 尾 40 =="; tail -n 40 /root/.acme.sh/acme.sh.log 2>/dev/null' 2>&1 | Tee-Object -FilePath $f
"rc=$LASTEXITCODE" | Tee-Object -FilePath $f -Append
```
**交付**：该 stdout 文件路径 ＋ 按上面判据的一行结论（三选一），入 `evidence/e01_migration_20260926/README.md`；不改任何线上东西。

## 五、协调侧可立即承接（纯 Python，不占本地窗口、不碰设备／提权）

> **2026-09-26 已交一件（PO 令「加速推进」）**：拦窗 #9 的修法＋门，做成**未落树的补丁**放在 `docs/coordination/patches/`——在自己容器的隔离工作树上完成，**共享树 `scripts/` 一个字节没碰**。这样既不越 D-582（没点名不动共享树），又把「点名即交」变成「点名即落」：属主 `git apply` 一条命令。详见补丁 README。

- **簇 C 的判词侧**：`zero_reading_ok` 的三态化与 `shutting_down` 去常量化（#9），含会红的门与夹具。
- **§6 步 0 判据文字改按内容判**（上面第三节第 1 条）。
- ⚠ **点名即交，未点名前不碰 `scripts/`**（承 D-582）。协调侧不自派。

## 六、Codex 边界（PO 问「是否需要 Codex 配合」；五镜头并行读仓 → 综合 → 三名怀疑者对抗核查，2026-09-26）

> **✅ 2026-09-26 午后 PO 已澄清**：「MIW 是服务器……ANEB 测速应用就在上面，由 Codex 维护」。⇒ 本节「不清楚」项①（MIW 是否＝Codex）**已解**：**MIW＝平台，Codex＝平台上 ANEB 应用的维护方**，二者不是一回事。本节「唯一必须 Codex 答的问题」（0.8.3 是否写死旧 IP）**随之消解**——应用侧迁址整体归 Codex，那是它自己的内部事；我方要的是**交付**（新址＋MIW 的 RSA 证书对外服务），不是答案。分工表见 §四。以下正文保留作推导记录。

**一句话**：需要，但**只需要两件**，且**都不该放在关键路径上**。

**法理与实务的矛盾（需 PO 对齐认知）**
- 法理：**D-35／D-37 从未撤销**——「部署所有权＝仅 Codex」「能力合同 Codex 维护」；D-547 板面、`spec/README.md:95` 仍写「仅 Codex」。
- 实务：**09-04 起 Codex 在决策线零出现**——D-692④ 大脑给 PO 的正式二选一（A＝PO 本人按包＋回滚单／B＝授权执行窗按受保护流程）**里没有 Codex**；PO D-694 原话「这份 server 是你帮忙部署的」；本方有**三次亲手部署 E-01 的先例**（`server_provision_20260712.log:4-5`、`acme_sslip_cert_20260713.log:3`、D-32），现役 sslip 证书与 `/opt/aneb/tls` 本就是本方在 E-01 上建的；迁址唯一外部对口是「MIW 云端运维」，**仓内无一处能证 MIW 是否＝Codex**。
- Codex 响应史**不对称**：一次当日闭环（D-35 11:29→D-37 14:24）、一次 **31 天无回执后撤回**（D-483→D-699，D-547「转交未达」）。

**技术硬约束（与谁执行无关）**
- 线上 E-01 跑的是 **0.8.3（G 树 Codex lane 血统）**，本树 `server/` 是 **0.1.0 对照副本**（`server/main.go:15`），「两条独立血统而非 patch 关系」（D-695②）；**D-695③ 禁令：不得从本仓 HEAD 重建部署**，D-712(4) 维持。
- ⇒ **不管谁部署新节点，源只能是：Codex 从 G 树重建，或原样搬运现有 0.8.3 二进制＋unit＋execution-profiles，只换证书。**

**Codex 必须答的（唯一一个技术问题）**：**0.8.3 源码（G 树 `codex/release-sprint-r1`）有没有写死旧 IP／sslip 主机名？** 若没有（与本树 `tls.go:38` 同构，SNI 分流只判空／IP 字面量）⇒ **原样搬运即可，不需 Codex 改码**；若有 ⇒ 必须 Codex 改码重建，届时才进关键路径。**只有能读 G 树的人能答。**

**Codex 可能要做的**：能力合同 `TEST_SERVER_CAPABILITIES.md`（G 树）若载有地址／证书条目，回写属 Codex（D-37），本方只能采认入册（D-37／D-39 先例）。

**不需要 Codex 的（本方可即刻做）**：`.ctree` 包 6 处常量＋两份 NSC＋parity 测试；`server/` 9 行注释级；D-912 两处脚本（`pull_device_corpus.py` JOIN 无条件＋`annotate_campaign.py` 按 run 填 serverBase）；`shaper.ps1:51 --dst-ip`（提权窗）；旧 IP 清单；方案 A 设备侧实测（证书 MIW 签，实测本方做）。

**⚠ 上一版综合曾把「gencert 重签 `aneb_ip_ca.pem`」列为本方项，被怀疑者推翻**：方案 A 下 bare-IP 通道改由公共 CA 证书呈现身份，不再 gencert 自签；且 pem 的私钥半须落到新节点 `/opt/aneb/tls/ip/`，那是部署侧的事。**撤回。**

**建议的排法**：先按「原样搬运」假设推进全部本方项；**同时把那一个问题发给 Codex（或 MIW，视 PO 答②）**；答「没写死」⇒ 搬运；答「写死」⇒ Codex 改码进关键路径。**不让 Codex 的响应时延卡住其他一切。**
