# A-8 总收口逐件对照表（2026-09-07，v4）

> 判据＝`docs/coordination/REVIEW_20260905_FULL.md` §7.1 **A-8 行原文**（不是任何派单摘要——D-719①）。
> 本表**是核，不是宣布**。每件写清「核到的是哪一层」。

---

## ⚠ 状态更新（2026-09-07 晚）：**OPEN-1 已关闭**，详见 §6

**§1 第 7 件与 §2 V4b 保留收口当时的判定原文，不就地改写**——它们是 D-805 引用的**史实**，
改掉会让那条 D 引到一份说着别的话的文件。**现态一律看 §6。**

## 0. 层的定义（这份表的量词）

| 层 | 含义 | 它**不**说什么 |
|---|---|---|
| **L0 未交付** | 代码不存在 | —— |
| **L1 在库** | 代码在库 | 不说它被测过 |
| **L2 跑过** | 有针对**该件**的测试，且**本轮实跑绿** | 不说验收判据被机检过 |
| **L3 验收过** | 验收列**原文**的机检判据本轮实跑通过 | —— |
| **L4 真机未达** | 须真机端到端，本窗结构不可达 | 不说它没写 |

⚠ 「在清单上／被枚举到／跑过」是三层。**本表把每件钉到其中一层，不合并。**

## 1. 步骤 13 件

| # | §7.1 原文（节录） | 现态（本轮实测） | 层 | 锚 |
|---|---|---|---|---|
| 1 | `uploadWindow` 解析 `UploadServerView`，`bytesTransferred=serverView.bytes`（与 written 不一致记 diagnostic） | `AnebClient.buildWindowResult` 内走 `UploadResponseView.bytesTransferred(serverView, writtenBytes)`；差值以 `clientWrittenBytes` 单列为诊断量 | **L2** | `50df3e7`／判据抽出 `b7e688d` |
| 2 | `endNanos`＝响应头到达 | `AnebClient.uploadWindow` 取 `val headersNanos = SystemClock.elapsedRealtimeNanos()`（在 `executeCancellable` 的响应回调首行），`buildWindowResult` 内 `endNanos = headersNanos` | **L2** | `50df3e7`；测试面在 C-3 `54b0b0a` |
| 3 | `adaptiveWindow` 上行改 `UploadAnalysis.estimateSlowStart(chunkUs, recvStartUs, 65536)` | `ScenarioKpi.adaptiveWindow` 内 `UploadAnalysis.estimateSlowStart(` | **L2** | `50df3e7` |
| 4 | `serverView==null` 时 **U1/U3** `durationNanos` 置 null（R-10） | **按 D-721 收窄为只置 U3**：`ScenarioKpi.adaptiveWindow` 的 `val serverCountMissing = isUpload && r.serverView == null` | **L2** | `0fb4c77`；⚠ 原文的 **U1 半已作废**，测试显名断言「U1 不据此判死」 |
| 5 | `server/main.go` 设 `TLSNextProto` 空 map | `server/main.go` 的 `TLSNextProto: map[string]func(` | **L3** | `9c646cd` |
| 6 | `tls_test` 断言 TLS 下 `resp.Proto=="HTTP/1.1"` | `server/tls_test.go` 的 `TestTLSPinsHTTP11`（断言 `resp.Proto != "HTTP/1.1"` 即 Fatal）；且其注释显名防「拿到 h1 是因为客户端默认值」的假过 | **L2** | `9c646cd` |
| 7 | **`AnebClient` 逐样本记 `response.protocol` 与 `X-Aneb-Proto` 上报（additive）** | 🔴 **未交付**：`X-Aneb-Proto` 在 `app/` **零命中**；`negotiated_protocol` 在 `app/ scripts/ server/ spec/` **零命中**；`AnebClient.kt` 无任何 `protocol` 读取。服务端侧已在发（`server/h3.go` 的 `withProtoEvidence` 里 `w.Header().Set("X-Aneb-Proto"`），且该文件头注释自述「**客户端一侧逐样本记录**」＝对侧存在而客户端半件没写 | **L0**（收口当时）→ **已补做，见 §6** | 八笔 A-8 提交无一涉及 |
| 8 | `build.gradle.kts` `buildConfigField GIT_SHA/BUILD_TYPE/APPLICATION_ID` ＋ `require(anebAppIdSuffix.startsWith('.'))` | 四处 `buildConfigField("String", "GIT_SHA"` / `"APPLICATION_ID_DECLARED"` / 两个 `"BUILD_TYPE"`；require 实为 `isEmpty() \|\| startsWith(".")`（默认构建空后缀须放行——**与原文有差，是有意的**） | **L2** | `2e0871f` |
| 9 | TestRun 加三列（Room v23＋`MigrationV23Test`＋`schemas/23.json`） | v23 实测 **7 列 / 2 表**：`test_run` 4（`buildGitSha`/`buildType`/`buildApplicationId`/`injectUsed`，第四键 D-729）＋ `adapter_obs` 3（C-6 并入，D-719②）。`MigrationV23Test` 五条断言：版本 22→23、七列恰两表、全 additive+nullable、亲和性、**列名与实体字段名对齐** | **L2** | `7a21a53`／`45a08da` |
| 10 | `ResultReporter.run.build{git_sha,build_type,application_id,inject_used}` | `ResultReporter.kt` 的 `put("build", buildJsonObject {` 块四键齐 | **L2** | `cf547e6`／`45a08da`／契约 `66549ee` |
| 11 | scripts 对 debug∧inject 标 `non_forensic` | D-730 改名＋改派 v3。`campaign_common.is_admissible` 三态（块缺席⇒`None`，**不默认 True**）＋ `corpus_ledger.admissibility_counts` 单列。`grep non_forensic scripts/`＝0 | **L2** | `eb17779`；⚠ D-730 点名的两个**字段名** `evidence_admissible`／`admissibility_reason` **全仓零命中**——判定只作**函数返回值**存在、不落进任何记录；将来按证据资格分池需先补字段 |
| 12 | `KpiCalculatorU3D3Test`「written=34 MB、server=30 MB ⇒ 30 MB」 | 该用例实际在 **`ScenarioKpiUploadBytesTest`**（`U3取服务端权威计数_written34MB_server30MB_判30MB`）。`KpiCalculatorU3D3Test` 存在且有 10 个 U3/D3 用例，**但不含此案** | **L2**（实质在库，**文件归属与原文不符**） | `0fb4c77` |
| 13 | `ScenarioKpiUploadBytesTest`「2xx＋坏 JSON ⇒ null」 | `U3在2xx但坏JSON时字节与时长与慢启动全null_不退回written`，三个 `assertNull` | **L2** | `0fb4c77` |

## 2. 验收 5 条（原文机检）

| V | §7.1 验收列原文 | 本轮实测结果 |
|---|---|---|
| **V1** | `go test -race -count=1 .` 绿 | ❌ **本机不可跑**：无 `gcc`、`CGO_ENABLED=0`，`-race` 直接拒绝（`-race requires cgo`，rc=2）。**可达的那半实跑了**：`go test -count=1 .` → `ok aneb-server 2.452s`。D-727 记协调侧代跑绿——**那是他方证据，本表未独立核** |
| **V2** | `grep -n TLSNextProto server/main.go` 非空 | ✅ 命中两处：`TLSNextProto: map[string]func(` 与一行注释 |
| **V3** | `./gradlew :probe:testDebugUnitTest` 绿 | ✅ **本轮实跑 975 tests / 0 failures / 0 errors / 0 skipped**，读 test-results XML 计数（不信 stdout），XML mtime 与跑毕相差 9 秒 |
| **V4a** | 新 run JSONL `.run.build.git_sha` 与 `git rev-parse --short HEAD` 一致 | ⛔ **L4 真机未达**（挂 C-2）：发射端已在库（第 10 件），值取自 `BuildConfig.GIT_SHA`，须真机装新 APK 打 C 树 server |
| **V4b** | `negotiated_protocol` 全为 `http/1.1` | 🔴 **不是真机阻塞，是发射端不存在**（见第 7 件）。**D-719③ 把 V4a 与 V4b 并列挂 C-2，那条挂错了层**——即便明天开真机窗，这一条也不会有值。**⇒ 已由 D-808 改变阻塞层，见 §6** |
| **V5** | D-703 首样本在**台账**标「U3 客户端口径、h2」禁合池 | ⚠ **分层**：台账 `docs/CORPUS_LEDGER.md` 该行（`evidence/t54_ctree_quick_20260904/t54_quick_raw.jsonl`，2 条）**只有计数、无口径列**，且台账**自动生成**（页首「勿手编」）⇒ 要加标须改 `corpus_ledger.py`。口径限定**落在证据目录 README 首行**，逐字含「A-8 合入前 **U3 为本地写口径、h2 不记协议**、无构建指纹」与「不与…相加或对比」。**实质在，位置不在验收点名的那个文件** |

⚠ 顺带一条**路径勘误**：§7.3 C-2 行把 D-703 首样本写作 `evidence/t54_wifi_smoke_20260904/`，**该目录不存在**；实为 `evidence/t54_ctree_quick_20260904/`。

## 3. 两枚已知存活突变：本轮实测**已关闭**

D-765 记「A-8 仍有已知 SURVIVED，换了一枚」＝ W1／W2 双双存活。**C-3 交付后无人重跑过**，本轮补跑：

| 突变 | 改法（接线点） | 结果 |
|---|---|---|
| **W1** | `bytesTransferred` 忽略服务端权威计数、直接用 `writtenBytes` | **CAUGHT** —— `AnebClientWindowTest`（真路径）＋ `UploadWindowResponseTest`（判据层）**双红** |
| **W2** | `headersNanos` 退回最后一次 write 返回的时刻 | **CAUGHT** —— `AnebClientWindowTest`「终点戳＝响应头到达_不是最后一次写入返回」 |

**咬住它们的是 C-3 的 `AnebClientWindowTest`（`54b0b0a`）**——这正是 D-725 把 C-3 定为 A-8 收口前提的理由，现在兑现了。

⚠ **审计卫生四条全满足**：①基线绿（975/0，突变前实跑）；②两次突变均 `compileDebugKotlin` **实际重跑**（非 UP-TO-DATE）；③两次均**正常终止**（`BUILD FAILED` 是测试红，不是挂死）；④还原后 `git diff` **空**、`mutated` 残留 0。
⚠ **还原后那次 gradle 是 `FROM-CACHE`，不是新跑**——故「还原后仍绿」的证据是 **`git diff` 空 ＋ 缓存命中**（缓存键＝输入哈希，命中本身即证明输入与突变前逐字节相同），**不是**又跑了一遍。写出来免得被引成「还原后实跑绿」。

## 4. 收口结论

- **步骤 13 件：12 件在 L2 及以上，1 件（第 7 件，客户端记协商协议）在 L0＝未交付。**
- **验收 5 条：V2／V3 达 L3；V1 本机结构不可跑；V4a L4 真机未达；V4b 因第 7 件未交付而不可达；V5 实质在、位置不符。**
- **两枚已知存活突变已关闭（2/2 CAUGHT，本轮实测）。**

⇒ **A-8 可收口，但须带三条显名未完成项**，不得随收口消失：

1. **A-8-OPEN-1**：客户端逐样本记协商协议（`response.protocol` ＋ `X-Aneb-Proto`）**未交付**；连带 V4b 不可达。**这不是真机项。** —— **✅ 已关闭（D-806 裁补做 → D-808 交付），见 §6**
2. **A-8-OPEN-2**：V4a（`.run.build.git_sha` 一致）**真机未验**，挂 C-2。
3. **A-8-OPEN-3**：V1（`-race`）本机不可跑；V5 的台账标注位置不符；D-730 两个字段名未落地为数据键。

## 5. 本表自身的边界

- 第 7 件的判定基于**四次零命中**（`X-Aneb-Proto` 于 `app/`；`negotiated_protocol` 于四个目录；`AnebClient.kt` 内 `protocol`；八笔提交主题）。**零命中的两个失败模式**——量法坏、范围错——已各查一遍：服务端侧同名 grep **有命中**（证明量法可用），范围按「原文点名的类 `AnebClient`」与「验收点名的键 `negotiated_protocol`」双取。
- V3 的 975 是**本轮**数值；同目录曾有一份 932 的旧 XML，**是上一轮残留**，不得引用。
- 第 11 件我第一次 grep 用的是**字段名**、零命中，差点判成未交付；实际交付用的是**函数名**。**这条写出来，是因为它和第 7 件长得一模一样，而结论相反。**

## 6. 状态更新：OPEN-1 已关闭（D-806 裁补做 → D-808 交付，提交 `3869c58`）

**这一节记现态；上面各节记收口当日的判定，两者都不删。**

| 收口当时（§1／§2 原文） | 现态（`3869c58`） |
|---|---|
| 步骤第 7 件＝**L0 未交付** | **L2**：`AnebClient.executeCancellable`（11 条请求路径的**唯一漏斗**）逐响应记 `response.protocol` 与 `X-Aneb-Proto`；上 wire 为 `run.negotiated_protocol`（`ResultReporter` 可选参数，挂接先例＝同文件的 env/voice）。**不动 Room、不发 v24**；未碰 `AbRunner`／`CronetStreamClient` 的同名字段（D-806 明令，同名不同义不合并） |
| 验收 V4b＝**发射端不存在，非真机阻塞** | **阻塞层已换**：发射端在库，剩真机端到端 ⇒ 与 V4a 同挂 C-2。**「设了它」与「拿得出它生效了」是两件事，现在后者有了发射端** |
| 「13 件 12 件达 L2＋」 | **13/13 达 L2＋** |
| 「带三条显名未完成项」 | **OPEN-1 关闭**；OPEN-2 维持挂 C-2；OPEN-3 维持（V1 不补、V5 登记不迁、D-730 字段名归 v3 车道）——三条处置见 D-806 |

**新增守卫（随 `3869c58`）**：`NegotiatedProtocolLogTest`（纯 JVM）／`AnebClientProtocolLogTest`（MockWebServer 真路径）／`ResultReporterProtocolTest`（wire 形状）。套件 975 → **993 实跑 0 failures**。

🔴 **突变审计 5/5 CAUGHT，其中 P3 首跑 SURVIVED**——夹具原本用生产常量 `AnebClient.PROTO_EVIDENCE_HEADER` 去**设置** MockResponse 的头 ⇒ **常量写岔时两侧一起岔、测试照样全绿**。这与本表 §5 记的第 11 件、以及 D-707 笔② 的 `check_expected_n` 是**同一形状：判据与被测方出自同一个假设**。修法＝夹具改**字面量**解耦 ＋ 加**跨语言钉**（读 `server/h3.go` 断言它以该字面量 `Set(...)`，再断言 Kotlin 常量与之逐字相同；范式承 D-264／D-508）。

⚠ **值得记的不是 5/5，是那个 1**：这条规矩我三小时前刚写进 D-707 证据文档，随后仍在自己新写的测试里犯了它——**逮住它的是突变审计这个不依赖记忆的装置，不是我记得那条规矩**。

