# E-01 旧址 · 现态/史实 逐处清单（2026-09-26）

> 🔴 **只分类，不修改，不是授权。** 它是给 PO 定下证书方案与节点命名之后动手的人用的输入；在那之前任何一处都不改。判不了现态还是史实的标「待判」，不猜。
>
> **基准**：提交 `8f356eb8`。**范围**：该提交树中**受跟踪**的文件。工作区里未跟踪或被 `.gitignore` 忽略的文件**不在本表**，另在 §7 计数单列——范围是结论的一部分。
>
> **量法（原样，本表即由它们产出）**：
>
> ```
> git -c core.quotePath=false grep -n -I -e '120\.79\.148\.0' -e '120[-]79[-]148[-]0' HEAD --
> git -c core.quotePath=false grep -l -e '120\.79\.148\.0' -e '120[-]79[-]148[-]0' HEAD --
> ```
>
> 两条模式分别是**点分写法**与 **sslip 写法**（`-` 写成 `[-]`、`.` 写成 `\.`，只是为了让本文件自己不含旧址字面量；生成时已断言它与 `-F` 固定串写法的命中**逐行相同**）。`-I` 跳过二进制，二进制文件由第二条的文件集减去文本文件集得出。
>
> **计数**：**55 个文件**＝文本 51 ＋ 二进制 4；文本命中 **172 行**＝evidence 以外 50 ＋ evidence 122。
>
> **关于「27 文件 55 处」**：那是我 09-26 早先报的数，量法是 `grep -rn "120\.79\.148\.0" --include=*.md --include=*.ps1 --include=*.py --include=*.kt --include=*.json .`——**只搜点分、只看五种扩展名**，恰好排掉一半，其中含两份 `network_security_config.xml`。**范围还原已核**：在当时的提交 `8c098a13` 上用同样五种扩展名、只搜点分重算，得 **27 个文件 / 56 行**——**文件数对上，行数我当时报 55，差 1 行是第二个、互相独立的错**：计行数时写的是 `grep -rc … $(cat 清单)`，**未加引号**，于是文件名带空格的那份（`docs/智能体互联网时代（Agentic Internet）…`）被拆成两个不存在的路径，报错又被 `2>/dev/null` 吞掉，**它那 1 行静默丢失**。已在工作区复现（bash）：同一清单未加引号得 46、逐个加引号得 47。⇒ **「文件不存在」被重定向压成了「这个文件没命中」。**那条命令**此刻**在工作区命中 **25** 个文件、**47** 行，全部在本表内（少掉的是我的两份卡，已于 `60253b78` 清零）。§4 的「原55处」列是**行级**的：只有该行含点分写法、且文件在那 27 个里才标「是」。
>
> **行号**钉在提交 `8f356eb8` 上；文件与行号分两列写，漂移后按「锚字串」列搜（锚字串取命中点**前面**的上下文，同样不含旧址）。

## 1. 类别定义

| 类别 | 含义 | 迁址时 |
|---|---|---|
| 现态·代码/配置 | 运行时真的会用到的值 | 随 PO 的方案改 |
| 现态·测试 | 钉住上一类的测试 | 与被测对象同批改 |
| 现态·注释 | 描述上两类当前行为的说明文字 | 与所描述对象同批改；含实测出处的保留出处 |
| 现态·指引 | 会被人照抄执行的命令 | 改，否则照抄即打旧址 |
| 现态·摘要 | 在别处概括上述现状的文字 | 所概括的对象一改即过期；属主另有其人 |
| 待判 | 判不了是现态还是史实 | 先裁再动，见 §6 |
| 史实 | 记录某次已发生的测量或决策 | **不改**——改了就伪造了历史，且改完处处自洽、不报错 |
| 禁止文本工具触碰 | 二进制文件 | **任何文本工具都不许碰**——文本替换会写坏它 |

## 2. 总表

| 类别 | 文件数 | 命中行数 |
|---|---|---|
| 现态·代码/配置 | 9 | 11 |
| 现态·测试 | 2 | 3 |
| 现态·注释 | 7 | 9 |
| 现态·指引 | 1 | 1 |
| 现态·摘要 | 1 | 1 |
| 待判 | 4 | 15 |
| 史实 | 33 | 132 |
| 禁止文本工具触碰 | 4 | —（git 在二进制里报 528，不是有意义的「处」） |

⚠ **同一文件内既有现态、又有史实或待判的**：`docs/BRAIN_TASKBOARD.md`。**对这些文件做整文件替换，会同时改到现态与史实。**（其余文件即使混有「现态·注释」与「现态·代码」，两类都是现态，不在此列。）

## 3. 🔴 耦合组：要改就一起改

**G1 · 客户端 TLS 信任（两份 NSC 与其对等测试）**（5 处）——NSC 是整份覆盖、不是合并：debug 构建只读 debug 那份——而据对等测试的说明，**debug 构建＝当前全部真机测量在用的变体**。对等测试断言每个变体「恰有一个」含该地址的 domain-config 且两份逐字相同 ⇒ 只改 NSC、只改测试、只改一份 NSC，三种都会报红（读断言得出，这是好事，它响亮）。板面那行是对它的现状摘要，归大脑。

- `app/probe/src/debug/res/xml/network_security_config.xml` 第 29 行（现态·代码/配置）
- `app/probe/src/main/res/xml/network_security_config.xml` 第 4 行（现态·注释）
- `app/probe/src/main/res/xml/network_security_config.xml` 第 18 行（现态·代码/配置）
- `app/probe/src/test/java/com/aneb/probe/net/NetworkSecurityConfigParityTest.kt` 第 26 行（现态·测试）
- `docs/BRAIN_TASKBOARD.md` 第 78 行（现态·摘要）

**G2 · 客户端默认端点与设置页预设**（6 处）——冷启动默认走 sslip（MainActivity 那行），设置页却把 bare-IP 标为「默认」——两行原文可对读，迁址时别只改其中一处。

- `app/probe/src/main/java/com/aneb/probe/net/ReachabilityProbe.kt` 第 94 行（现态·代码/配置）
- `app/probe/src/main/java/com/aneb/probe/net/ReachabilityProbe.kt` 第 97 行（现态·代码/配置）
- `app/probe/src/main/java/com/aneb/probe/net/UdpProbe.kt` 第 14 行（现态·注释）
- `app/probe/src/main/java/com/aneb/probe/ui/MainActivity.kt` 第 216 行（现态·代码/配置）
- `app/probe/src/main/java/com/aneb/probe/ui/SettingsScreen.kt` 第 97 行（现态·代码/配置）
- `app/probe/src/main/java/com/aneb/probe/ui/SettingsScreen.kt` 第 98 行（现态·代码/配置）

**G3 · 服务端证书与 SNI 分流（含签发默认值、签发说明、测试）**（9 处）——tls.go 按 sslip 主机名分流证书；gencert 的 -ip 默认值决定新签证书的 IP-SAN——按默认值新签，IP-SAN 仍是旧址。

- `scripts/deploy_server.ps1` 第 27 行（现态·注释）
- `scripts/deploy_server.ps1` 第 31 行（现态·注释）
- `server/main.go` 第 95 行（现态·注释）
- `server/tls.go` 第 5 行（现态·注释）
- `server/tls.go` 第 8 行（现态·注释）
- `server/tls.go` 第 24 行（现态·代码/配置）
- `server/tls_test.go` 第 38 行（现态·测试）
- `server/tls_test.go` 第 57 行（现态·测试）
- `server/tools/gencert/main.go` 第 35 行（现态·代码/配置）

**G4 · 部署目标主机**（1 处）——旧服务器继续服务，是否改指向取决于 PO 的节点命名与切换决定。

- `scripts/deploy_server.ps1` 第 24 行（现态·代码/配置）

**G5 · 整形限速档目标**（2 处）——整形脚本部署在管理员可写目录，改后须管理员重新部署；同文件注释写明有守卫靠子串认 $TARGET，改名会静默错判作用域。

- `scripts/shaper/shaper.ps1` 第 42 行（现态·注释）
- `scripts/shaper/shaper.ps1` 第 51 行（现态·代码/配置）

**G6 · 可照抄的操作命令**（1 处）——另见 V2 所指：--es server 只在冷启动时读取；组件名须写 ctree 包。

- `docs/WEAK_NETWORK_SIMULATION.md` 第 33 行（现态·指引）

**G7 · 合成语料与其生成器**（13 处）——产物由生成器写出；单改产物会与生成器不一致。

- `evidence/phase3/demo_results.jsonl` 第 1 行（待判）
- `evidence/phase3/demo_results.jsonl` 第 2 行（待判）
- `evidence/phase3/demo_results.jsonl` 第 3 行（待判）
- `evidence/phase3/demo_results.jsonl` 第 4 行（待判）
- `evidence/phase3/demo_results.jsonl` 第 5 行（待判）
- `evidence/phase3/demo_results.jsonl` 第 6 行（待判）
- `evidence/phase3/demo_results.jsonl` 第 7 行（待判）
- `evidence/phase3/demo_results.jsonl` 第 8 行（待判）
- `evidence/phase3/demo_results.jsonl` 第 9 行（待判）
- `evidence/phase3/demo_results.jsonl` 第 10 行（待判）
- `evidence/phase3/demo_results.jsonl` 第 11 行（待判）
- `evidence/phase3/demo_results.jsonl` 第 12 行（待判）
- `evidence/phase3/gen_demo_jsonl.py` 第 74 行（待判）

## 4. evidence 以外：逐处

| # | 文件 | 行 | 写法 | 类别 | 组 | 原55处 | 锚字串 | 说明 |
|---|---|---|---|---|---|---|---|---|
| 1 | `app/probe/src/debug/res/xml/network_security_config.xml` | 29 | 点分 | 现态·代码/配置 | G1 | 否 | 「includeSubdomains="false">」＋旧址 | debug 变体 NSC 的受信域 |
| 2 | `app/probe/src/main/java/com/aneb/probe/net/ReachabilityProbe.kt` | 94 | sslip | 现态·代码/配置 | G2 | 否 | 「const val E01_SNI_HOST = "」＋旧址 | REACH 探针 sslip 主机名常量 |
| 3 | `app/probe/src/main/java/com/aneb/probe/net/ReachabilityProbe.kt` | 97 | 点分 | 现态·代码/配置 | G2 | 是 | 「const val E01_IP = "」＋旧址 | REACH 探针 bare-IP 常量 |
| 4 | `app/probe/src/main/java/com/aneb/probe/net/UdpProbe.kt` | 14 | 点分 | 现态·注释 | G2 | 是 | 「ER_CAPABILITIES 口径）：E-01」＋旧址 | UDP 服务端合同说明；其「实测锚定」测的是旧址，新址是否同合同未实测——改时保留出处 |
| 5 | `app/probe/src/main/java/com/aneb/probe/ui/MainActivity.kt` | 216 | sslip | 现态·代码/配置 | G2 | 否 | 「(intentServer ?: "https://」＋旧址 | 🔴 冷启动默认端点（sslip 写法）；V2 核实称该证书 10-11 到期——V2 自标「按代码推断、未上机」 |
| 6 | `app/probe/src/main/java/com/aneb/probe/ui/SettingsScreen.kt` | 97 | 点分 | 现态·代码/配置 | G2 | 是 | 「t("bare-IP（默认）", "https://」＋旧址 | 设置页 bare-IP 预设，标签写「默认」而实际冷启动默认不是它 |
| 7 | `app/probe/src/main/java/com/aneb/probe/ui/SettingsScreen.kt` | 98 | sslip | 现态·代码/配置 | G2 | 否 | 「lip.io（公网 TLS）", "https://」＋旧址 | 设置页 sslip 预设 |
| 8 | `app/probe/src/main/res/xml/network_security_config.xml` | 4 | 点分 | 现态·注释 | G1 | 否 | 「要带私有信任锚：E-01 的 bare-IP 通道（」＋旧址 | 说明 release 为何带私有信任锚；与同文件受信域那行同改 |
| 9 | `app/probe/src/main/res/xml/network_security_config.xml` | 18 | 点分 | 现态·代码/配置 | G1 | 否 | 「includeSubdomains="false">」＋旧址 | 🔴 release 包受信域；改漏则 bare-IP 通道 TLS 握手失败 |
| 10 | `app/probe/src/test/java/com/aneb/probe/net/NetworkSecurityConfigParityTest.kt` | 26 | 点分 | 现态·测试 | G1 | 是 | 「private val e01Ip = "」＋旧址 | 钉住两份 NSC 的对等测试 |
| 11 | `app/probe/src/test/java/com/aneb/probe/scoring/CalibrationFixtureTest.kt` | 18 | 点分 | 史实 | — | 是 | 旧址＋「:8443），600 token @40tps——真」 | ⚠ 在 app/src/test 下却是史实：夹具采集自旧址的出处注释，改它会伪造夹具来历 |
| 12 | `docs/BRAIN_TASKBOARD.md` | 78 | 点分 | 现态·摘要 | G1 | 是 | 「r 的 TLS 路径——App 私有信任锚钉死在」＋旧址 | T54（DOING）行内对 NSC 现状的描述，NSC 一改即过期；板面归大脑托管 |
| 13 | `docs/BRAIN_TASKBOARD.md` | 79 | 点分 | 待判 | — | 是 | 「开头，对不上即停）；②基线 ping -n 10」＋旧址 | T78（DOING）行内嵌 clumsy 段 B 操作指令；其后 09-07 与 09-12 的 b2 证据改用 BeanNetworkTester——是否仍现行需大脑判 |
| 14 | `docs/BRAIN_TASKBOARD.md` | 110 | sslip | 史实 | — | 否 | 「ase 包 RUN_START →https://」＋旧址 | 证书 A 案实证记录 |
| 15 | `docs/BRAIN_TASKBOARD.md` | 117 | 点分 | 史实 | — | 是 | 「移 src/main、main NSC 只含」＋旧址 | T58b 施工完成记录（08-19） |
| 16 | `docs/CODEX_HANDOFF_2026-07-14.md` | 38 | 点分 | 史实 | — | 是 | 「服务端（TCP+H3 双栈；E-01=深圳阿里云」＋旧址 | 带日期的交接快照 |
| 17 | `docs/CODEX_HANDOFF_2026-07-14.md` | 59 | 点分 | 史实 | — | 是 | 「serverUrl 设置（含 bare-IP」＋旧址 | 带日期的交接快照 |
| 18 | `docs/CODEX_HANDOFF_2026-07-14.md` | 72 | 点分+sslip | 史实 | — | 是 | 「- **E-01 端点**：默认 https://」＋旧址 | 带日期的交接快照 |
| 19 | `docs/DECISION_LOG.md` | 33 | sslip | 史实 | — | 否 | 「是 E-01 sslip 主机名 https://」＋旧址 | 决策记录 |
| 20 | `docs/DECISION_LOG.md` | 486 | sslip | 史实 | — | 否 | 「机→E-01 的 curl 诊断（https://」＋旧址 | 决策记录 |
| 21 | `docs/DECISION_LOG.md` | 500 | 点分 | 史实 | — | 是 | 「curl bare-IP 通道（https://」＋旧址 | 决策记录 |
| 22 | `docs/DECISION_LOG.md` | 505 | 点分 | 史实 | — | 是 | 「release（domain-config 钉死」＋旧址 | 决策记录 |
| 23 | `docs/DECISION_LOG.md` | 700 | 点分 | 史实 | — | 是 | 「h -i ~/.ssh/aneb_e01 root@」＋旧址 | 决策记录（实测的免密通道） |
| 24 | `docs/DECISION_LOG.md` | 707 | 点分+sslip | 史实 | — | 是 | 「intentServer ?: "https://」＋旧址 | 决策记录 |
| 25 | `docs/DW_20260905_01_WINDOW_ORDER.md` | 27 | 点分 | 史实 | — | 是 | 「k.type；切网后 ip route get」＋旧址 | 已收窗的窗令（D-711／D-716） |
| 26 | `docs/T58_RELEASE_PREFLIGHT_20260819.md` | 43 | 点分 | 史实 | — | 是 | 旧址＋「（E-01 bare-IP）— https + 自」 | 已裁方案单（D-500③） |
| 27 | `docs/T58_RELEASE_PREFLIGHT_20260819.md` | 50 | 点分 | 史实 | — | 是 | 「到 src/main/，release 保留」＋旧址 | 已裁方案单（D-500③） |
| 28 | `docs/T58_RELEASE_PREFLIGHT_20260819.md` | 53 | 点分 | 史实 | — | 是 | 「**我的建议＝案 A**（收窄版：只留」＋旧址 | 已裁方案单（D-500③） |
| 29 | `docs/T58_RELEASE_PREFLIGHT_20260819.md` | 89 | 点分 | 史实 | — | 是 | 「c/main/res/xml/，**只保留**」＋旧址 | 已裁方案单（D-500③） |
| 30 | `docs/T61_APP_CAPABILITY_FACTCHECK_20260819.md` | 44 | 点分 | 史实 | — | 是 | 「release **携带**收窄版 NSC：仅」＋旧址 | 带日期核查单 |
| 31 | `docs/WEAK_NETWORK_SIMULATION.md` | 33 | sslip | 现态·指引 | G6 | 否 | 「--es server https://」＋旧址 | 方法文档中的可照抄命令 |
| 32 | `docs/coordination/LEDGER.md` | 59 | 点分 | 史实 | — | 是 | 「de 可不经 UI 指向 PC；私有信任锚钉死」＋旧址 | 巡检台账记录 |
| 33 | `docs/coordination/REVIEW_20260905_FULL.md` | 344 | 点分 | 史实 | — | 是 | 「tet 并授权 VPN，ip route get」＋旧址 | 所在节为限时计划（至 09-07 05:00Z），已过期；⚠ 日后段 C 验收取 A-7 预案 §3 的 $DST，不取此行 |
| 34 | `docs/launchpad/spine4-speedtest-dynamism-blueprint.md` | 215 | sslip | 待判 | — | 否 | 「ivity --es server https://」＋旧址 | 07-18 设计蓝图、带作废横幅，却写「据此秒执行」；Spine-4 是否仍待执行需大脑判；若执行，其组件名与地址两处皆过期 |
| 35 | `docs/智能体互联网时代（Agentic Internet）移动通信网络的新型网络性能与体验诉求.md` | 221 | 点分 | 史实 | — | 是 | 「*RST**（握手中途双向复位）；bare-IP」＋旧址 | 论述中引用的实测 |
| 36 | `docs/测量红队清单.md` | 277 | 点分 | 史实 | — | 是 | 「行；改用 **bare-IP**（https://」＋旧址 | 机理条目的实测证据 |
| 37 | `docs/测量红队清单.md` | 278 | 点分+sslip | 史实 | — | 是 | 「SDK31）分钟级 A/B：(1) WiFi +」＋旧址 | 机理条目的实测证据 |
| 38 | `scripts/deploy_server.ps1` | 24 | 点分 | 现态·代码/配置 | G4 | 是 | 「$Remote  = 'root@」＋旧址 | 部署目标主机 |
| 39 | `scripts/deploy_server.ps1` | 27 | 点分 | 现态·注释 | G3 | 是 | 「igned IP-SAN cert+key (IP:」＋旧址 | IP-SAN 证书签发说明 |
| 40 | `scripts/deploy_server.ps1` | 31 | 点分 | 现态·注释 | G3 | 是 | 「ools/gencert -mode=ip -ip=」＋旧址 | gencert 命令示例 |
| 41 | `scripts/shaper/shaper.ps1` | 42 | 点分 | 现态·注释 | G5 | 是 | 「# 限速档的**验证目标**＝E-01」＋旧址 | 限速档目标说明（D-852） |
| 42 | `scripts/shaper/shaper.ps1` | 51 | 点分 | 现态·代码/配置 | G5 | 是 | 「ter', 'out', '--dst-ip', '」＋旧址 | 限速档 --dst-ip |
| 43 | `server/main.go` | 95 | 点分 | 现态·注释 | G3 | 否 | 「ey-ip 指向自签 IP-SAN 证书（含 IP:」＋旧址 | SNI 双通道说明 |
| 44 | `server/tls.go` | 5 | sslip | 现态·注释 | G3 | 否 | 「//   - ServerName == "」＋旧址 | 证书分流说明 |
| 45 | `server/tls.go` | 8 | 点分 | 现态·注释 | G3 | 否 | 「/     供蜂窝 bare-IP 通道（含 IP:」＋旧址 | 证书分流说明 |
| 46 | `server/tls.go` | 24 | sslip | 现态·代码/配置 | G3 | 否 | 「const sslipHostname = "」＋旧址 | 🔴 服务端按此主机名分流证书；新址若沿用本代码，SNI 分流仍认旧主机名 |
| 47 | `server/tls_test.go` | 38 | 点分 | 现态·测试 | G3 | 否 | 「literal SNI -> IP-SAN", "」＋旧址 | SNI 分流测试用例 |
| 48 | `server/tls_test.go` | 57 | 点分 | 现态·测试 | G3 | 否 | 「ni := range []string{"", "」＋旧址 | SNI 分流测试用例 |
| 49 | `server/tools/capture/main.go` | 14 | 点分 | 现态·注释 | — | 否 | 「// capture -url "http://」＋旧址 | 抓取工具用法示例 |
| 50 | `server/tools/gencert/main.go` | 35 | 点分 | 现态·代码/配置 | G3 | 否 | 「Str := flag.String("ip", "」＋旧址 | 🔴 gencert 的 -ip 默认值 |

## 5. evidence：逐文件（文件内各处同类）

写法列按形式各计：同一行两种写法都有时各计一次，故两数之和可大于行数。「原27」列此处是**文件级**。

| 文件 | 行数 | 写法 | 类别 | 组 | 原27 | 行号（@8f356eb8） | 说明 |
|---|---|---|---|---|---|---|---|
| `evidence/afternoonradio_20260801/device_logcat.txt` | 12 | 点分 4、sslip 8 | 史实 | — | 否 | 2, 3, 7, 158, 159, 163, 314, 315, 319, 470, 471, 475 | 设备日志 |
| `evidence/b2_beancap_20260912/CRITERIA_PREREG.md` | 1 | 点分 1 | 史实 | — | 是 | 4 | 预注册判据，按定义冻结 |
| `evidence/b2_beancap_20260912/README.md` | 8 | 点分 8 | 史实 | — | 是 | 3, 30, 66, 71, 72, 75, 120, 166 | 限速档验证记录 |
| `evidence/b2_beanverify_20260907/README.md` | 1 | 点分 1 | 史实 | — | 是 | 46 | 整形器验证记录 |
| `evidence/m2_idleprobe_20260731/idle_logcat.txt` | 12 | 点分 4、sslip 8 | 史实 | — | 否 | 2, 3, 7, 158, 159, 163, 314, 315, 319, 470, 471, 475 | 设备日志 |
| `evidence/phase0/c11_tcpdump_alignment_20260712.log` | 1 | 点分 1 | 史实 | — | 否 | 3 | 实跑日志 |
| `evidence/phase0/c14_prep_20260713.log` | 1 | 点分 1 | 史实 | — | 否 | 8 | 实跑日志 |
| `evidence/phase0/first_internet_baseline_20260712.log` | 1 | 点分 1 | 史实 | — | 否 | 1 | 实跑日志 |
| `evidence/phase0/server_provision_20260712.log` | 2 | 点分 2 | 史实 | — | 否 | 3, 109 | 开服记录 |
| `evidence/phase1/c08_calibration_20260713.md` | 1 | 点分 1 | 史实 | — | 是 | 19 | 校准记录 |
| `evidence/phase2/cronet_ab_public_h3_20260713.log` | 5 | 点分 1、sslip 4 | 史实 | — | 否 | 3, 8, 11, 16, 17 | 实跑日志 |
| `evidence/phase3/acme_sslip_cert_20260713.log` | 18 | 点分 4、sslip 15 | 史实 | — | 否 | 3, 4, 10, 13, 14, 17, 18, 21, 50, 58, 59, 66, 67, 68, 69, 76, 95, 104 | sslip 证书签发记录（与冷启动默认端点所用证书同源） |
| `evidence/phase3/demo_results.jsonl` | 12 | 点分 12 | 待判 | G7 | 否 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 | 合成语料：其中地址不描述任何真实测量；是否随迁址改是设计问题，建议归 v3（台账属主）判 |
| `evidence/phase3/gen_demo_jsonl.py` | 1 | 点分 1 | 待判 | G7 | 是 | 74 | 上一行产物的生成器；与产物同批判、同批改 |
| `evidence/phase3/realdevice_cellular_forensic_20260713.md` | 2 | 点分 1、sslip 1 | 史实 | — | 是 | 13, 14 | 真机取证记录 |
| `evidence/phase3/realdevice_continuity_crossnet_fix_verify_20260713.log` | 5 | 点分 5 | 史实 | — | 否 | 2, 3, 10, 11, 12 | 实跑日志 |
| `evidence/phase3/realdevice_continuity_crossnet_fix_verify_20260713.md` | 1 | 点分 1 | 史实 | — | 是 | 8 | 实跑记录 |
| `evidence/phase3/realdevice_continuity_kimi_20260713.log` | 2 | 点分 2 | 史实 | — | 否 | 19, 61 | 实跑日志 |
| `evidence/phase3/realdevice_first_campaign_20260713.log` | 3 | 点分 2、sslip 1 | 史实 | — | 否 | 16, 18, 21 | 实跑日志 |
| `evidence/phase3/sni_dualpath_impl_20260713.log` | 8 | 点分 6、sslip 2 | 史实 | — | 否 | 17, 26, 53, 55, 77, 80, 81, 99 | 实跑日志 |
| `evidence/phase3/tls_cutover_20260713.log` | 5 | 点分 3、sslip 3 | 史实 | — | 否 | 2, 10, 19, 25, 65 | 实跑日志 |
| `evidence/radiowire_20260801/device_logcat.txt` | 6 | 点分 2、sslip 4 | 史实 | — | 否 | 2, 3, 7, 64, 65, 69 | 设备日志 |
| `evidence/t25_keepscreenon_devverify_20260819/README.md` | 2 | 点分 2 | 史实 | — | 是 | 5, 86 | 真机验证记录 |
| `evidence/t2_idlenight_20260801/device_logcat.txt` | 12 | 点分 4、sslip 8 | 史实 | — | 否 | 2, 3, 7, 158, 159, 163, 314, 315, 319, 470, 471, 475 | 设备日志 |

**二进制（4 个）——禁止文本工具触碰**：

| 文件 | git 报的计数 | 说明 |
|---|---|---|
| `evidence/acceptance_20260820/acceptance_pull_aneb-probe.db` | 3 | 验收时拉回的设备库 |
| `evidence/phase3/realdevice_data/aneb-probe-cellular.db` | 175 | 真机设备库 |
| `evidence/phase3/realdevice_data/aneb-probe-cellular2.db` | 176 | 真机设备库 |
| `evidence/phase3/realdevice_data/aneb-probe.db` | 174 | 真机设备库 |

## 6. 待判（先裁再动）

- `docs/BRAIN_TASKBOARD.md` 第 79 行：T78（DOING）行内嵌 clumsy 段 B 操作指令；其后 09-07 与 09-12 的 b2 证据改用 BeanNetworkTester——是否仍现行需大脑判
- `docs/launchpad/spine4-speedtest-dynamism-blueprint.md` 第 215 行：07-18 设计蓝图、带作废横幅，却写「据此秒执行」；Spine-4 是否仍待执行需大脑判；若执行，其组件名与地址两处皆过期
- `evidence/phase3/demo_results.jsonl` 第 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 行：合成语料：其中地址不描述任何真实测量；是否随迁址改是设计问题，建议归 v3（台账属主）判
- `evidence/phase3/gen_demo_jsonl.py` 第 74 行：上一行产物的生成器；与产物同批判、同批改

## 7. 范围外：工作区中未跟踪或被忽略、却含旧址的文件（不入本表，只计数）

共 **32** 个。按顶层目录：`app` 30、`.claude` 1、`evidence` 1。其中 **31 个是构建产物**（路径含 `/build/`），**1 个不是**。

🔴 **`evidence/phase3/realdevice_data/voice30_aneb-probe.db`**：未跟踪的证据库——**既是史实又是二进制，却不在 git 里**。只按 git 清单改的人碰不到它；**但若有人对工作区（而非 git）跑一次文本替换，它会被写坏，且 git 无法恢复**。

<details><summary>逐个列出</summary>

- `.claude/worktrees/frosty-wright-aedafc/app/probe/build/outputs/apk/debug/probe-debug.apk`
- `app/probe/build/intermediates/compile_app_classes_jar/debug/bundleDebugClassesToCompileJar/classes.jar`
- `app/probe/build/intermediates/dex/debug/mergeProjectDexDebug/6/classes.dex`
- `app/probe/build/intermediates/dex/debug/mergeProjectDexDebug/7/classes.dex`
- `app/probe/build/intermediates/dex/release/mergeDexRelease/classes2.dex`
- `app/probe/build/intermediates/merged_res/debug/mergeDebugResources/xml_network_security_config.xml.flat`
- `app/probe/build/intermediates/merged_res/release/mergeReleaseResources/xml_network_security_config.xml.flat`
- `app/probe/build/intermediates/packaged_res/debug/packageDebugResources/xml/network_security_config.xml`
- `app/probe/build/intermediates/packaged_res/release/packageReleaseResources/xml/network_security_config.xml`
- `app/probe/build/intermediates/project_dex_archive/debug/dexBuilderDebug/out/com/aneb/probe/net/ReachabilityProbe$Companion.dex`
- `app/probe/build/intermediates/project_dex_archive/debug/dexBuilderDebug/out/com/aneb/probe/net/ReachabilityProbe.dex`
- `app/probe/build/intermediates/project_dex_archive/debug/dexBuilderDebug/out/com/aneb/probe/ui/MainActivity$onCreate$5$1$2.dex`
- `app/probe/build/intermediates/project_dex_archive/debug/dexBuilderDebug/out/com/aneb/probe/ui/SettingsScreenKt.dex`
- `app/probe/build/intermediates/project_dex_archive/release/dexBuilderRelease/out/com/aneb/probe/net/ReachabilityProbe$Companion.dex`
- `app/probe/build/intermediates/project_dex_archive/release/dexBuilderRelease/out/com/aneb/probe/net/ReachabilityProbe.dex`
- `app/probe/build/intermediates/project_dex_archive/release/dexBuilderRelease/out/com/aneb/probe/ui/MainActivity$onCreate$5$1$2.dex`
- `app/probe/build/intermediates/project_dex_archive/release/dexBuilderRelease/out/com/aneb/probe/ui/SettingsScreenKt.dex`
- `app/probe/build/intermediates/runtime_app_classes_jar/debug/bundleDebugClassesToRuntimeJar/classes.jar`
- `app/probe/build/outputs/apk/debug/probe-debug.apk`
- `app/probe/build/outputs/apk/release/probe-release-unsigned.apk`
- `app/probe/build/tmp/kotlin-classes/debug/com/aneb/probe/net/ReachabilityProbe$Companion.class`
- `app/probe/build/tmp/kotlin-classes/debug/com/aneb/probe/net/ReachabilityProbe.class`
- `app/probe/build/tmp/kotlin-classes/debug/com/aneb/probe/ui/MainActivity$onCreate$5$1$2.class`
- `app/probe/build/tmp/kotlin-classes/debug/com/aneb/probe/ui/SettingsScreenKt.class`
- `app/probe/build/tmp/kotlin-classes/debugUnitTest/com/aneb/probe/net/NetworkSecurityConfigParityTest.class`
- `app/probe/build/tmp/kotlin-classes/debugUnitTest/com/aneb/probe/net/ReachabilityBaseSelectTest.class`
- `app/probe/build/tmp/kotlin-classes/debugUnitTest/com/aneb/probe/net/ReachabilityProbeTest.class`
- `app/probe/build/tmp/kotlin-classes/release/com/aneb/probe/net/ReachabilityProbe$Companion.class`
- `app/probe/build/tmp/kotlin-classes/release/com/aneb/probe/net/ReachabilityProbe.class`
- `app/probe/build/tmp/kotlin-classes/release/com/aneb/probe/ui/MainActivity$onCreate$5$1$2.class`
- `app/probe/build/tmp/kotlin-classes/release/com/aneb/probe/ui/SettingsScreenKt.class`
- `evidence/phase3/realdevice_data/voice30_aneb-probe.db`

</details>

⚠ 构建产物会在下次构建时按源码重生——**但已经构建出来、已经装到设备上的包仍指向旧址**，直到重新构建并重装。

## 8. 两条顺带核到的事实（原文可对读，不是推断）

1. **设置页把 bare-IP 预设标为「默认」，而冷启动且未带 `server` intent 参数时，端点初值是 sslip 写法**——见 §4 中 `MainActivity.kt` 与 `SettingsScreen.kt` 两行。核法：该初值用 `rememberSaveable`，且 `MainActivity.kt` 内未见 SharedPreferences／DataStore ⇒ 无磁盘持久化覆盖；**核的范围只到这一个文件**。
2. **sslip 证书 10-11 到期、到期后探针会把握手失败记成与 SNI 阻断同形**——这是 V2 的核实结论，**V2 自标「按代码推断、未上机」**，本表照原样保留该限定，不升级。
