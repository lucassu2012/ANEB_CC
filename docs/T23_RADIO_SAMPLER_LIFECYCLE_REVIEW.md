# T23：radio 采样器场景 2 后停止/陈旧——只读代码复核

> 写作条件：全程只用 Read（工具层故障期间），未跑代码、未连设备、未看 logcat。
> 复核对象：`app/probe/src/main/java/com/aneb/probe/radio/RadioCollector.kt` +
> `app/probe/src/main/java/com/aneb/probe/engine/TestEngine.kt`（radio 接线段）+
> `app/probe/src/main/java/com/aneb/probe/engine/BufferingWiring.kt`（场景级聚合）。
> 数据来源：`evidence/nr_timeline_20260802/NR_RUN_REGISTRATION_20260802_019fc1a6.md` §2。

## 0. 一页结论

| 候选方向 | 结论 | 证据 |
|---|---|---|
| 采样周期长于场景切换间隔 | **排除** | 1Hz（`RadioCollector.kt:510` `SAMPLE_PERIOD_NS`），场景 0/1 各自拿到 26/18 个样本，说明健康期间采样密度远高于场景粒度 |
| 生命周期绑定错对象（run 级 vs scenario 级） | **排除** | `radio.start()` 在整个 run 的顶层只调用一次（`TestEngine.kt:249`），收尸只在 run 级 `finally`（`TestEngine.kt:619`）；没有任何逐场景重建/重订阅的代码路径 |
| 某处提前 unregister | **排除**（有限度） | 唯一的场景级取消是 `invalidate()`（`TestEngine.kt:200-204`），只 `cancel` `currentScenario` 这一个 Job，与 `radioShareJob` 是同父的兄弟 Job（父均为 run 级 `coroutineContext[Job]`），结构上互不牵连 |
| **未捕获异常静默杀死采样协程（本文判断的最可能根因）** | **未排除，且是唯一还站得住的候选** | 见 §1 |
| stale 判定窗口太短 | **排除** | `STALE_NS=2_000_000_000L`（2 秒，`RadioCollector.kt:512`）判的是"这一条样本新不新鲜"，与"完全没有样本"是两件事；`radioExport()`（`BufferingWiring.kt:159-174`）在窗口内**零样本**时才会给出观测到的 `sampled_n=0, stale=true` 全 null 形状（`BufferingWiring.kt:156` docstring 原话），不是陈旧样本被误判 |

**本文找不到能把"根因"钉到单一一行代码的证据**（这需要 logcat 或复现实验，Read 做不到）；
能做到的是把候选收窄到一类结构性缺陷，并指出这类缺陷会**必然**产生 D-424 观测到的
确切形状。

---

## 1. 最可能的根因：1Hz 采样循环没有任何顶层异常防护，一次未捕获异常即永久停止

### 1.1 数据怎么走到 `sampled_n=0`

`BufferingWiring.radioExport()`（`BufferingWiring.kt:159-174`）：
```
val inWindow = samples.filter { it.tsNanos >= startNanos && ... }
val fresh = inWindow.filter { !it.stale }
val basis = if (fresh.isNotEmpty()) fresh else inWindow
val stale = fresh.isEmpty()
```
`sampled_n=0` 且全字段 null，只有一种成因：**`inWindow` 为空**——该场景的时间窗口内，
`radioBuf`（`TestEngine.kt:195`，run 级单一 `ConcurrentLinkedQueue`，全程未被重建）
里**一条样本都没有**。这不是"样本陈旧"（那样 `fresh` 会空但 `inWindow` 不空，仍会
落到 `basis=inWindow` 分支给出 stale=true 但**非全空**的读数），是**采集端压根没往
队列里放新东西**。

### 1.2 队列为什么会停止收到新样本

`radioBuf` 的唯一写入路径是 `TestEngine.kt:253`：
```
collectors += launch { radioFlow.collect { radioBuf.add(it); latestRadio.set(it) } }
```
这是**贯穿整个 run、只订阅一次**的收集器。`radioFlow` 来自 `radio.start(scope)`
（`RadioCollector.kt:83-84`）：
```
fun start(scope: CoroutineScope): Flow<RadioSample> =
    samplerFlow().shareIn(scope, SharingStarted.WhileSubscribed(), replay = 0)
```
`samplerFlow()`（`RadioCollector.kt:86-189`）内部是一个 `while (true)` 循环
（:102-185），**循环体本身没有任何顶层 `try/catch`**——外层只有一个 `try { while
(true) {...} } finally { ... }`（:101/186），`finally` 只做监听器收尾，**不捕获、
不记录、不重试任何异常**。

若循环体内任意一次迭代抛出未被内部各个局部 `try/catch`吸收的异常，这个异常会直接
穿出 `flow { }` 构建器——**`shareIn` 链路上没有任何 `.catch{}` 操作符**
（`RadioCollector.kt:84` 逐字确认），异常会杀死 `shareIn` 内部负责真正跑这个循环
的那个协程。

**关键一环，解释了为什么整个 run 不会崩、只有 radio 数据消失**：`TestEngine.kt:247`
`val shareJob = kotlinx.coroutines.SupervisorJob(coroutineContext[Job])`，`radio.
start()` 拿到的 `scope` 挂在这个 `SupervisorJob` 下（:249）。`SupervisorJob` 的
语义是子协程失败**不传染**给同级或父级——**这正好能解释「run 照常跑完 9 个场景、
status=completed」与「radio 从某一刻起永久归零」这两个看似矛盾的现象可以同时成立**。

而 `WhileSubscribed()` 的"有新订阅者时重启上游"这条自愈机制，在本代码里**永远不会
被触发**——`TestEngine.kt:253` 那一次 `collect` 是全程唯一、从不取消重订阅的订阅者，
订阅者数量从未归零再回升，`shareIn` 没有理由重新拉起已经死掉的上游协程。

**净效果**：循环体内一次未捕获异常 → 该协程永久终止 → 没有任何日志、没有任何重试、
run 其余部分完全不受影响地跑完 → 该异常发生时刻之后的每一个场景，`radioExport()`
看到的都是空窗口，如实给出 `sampled_n=0, stale=true`（这一层本身没有 bug，是在
如实反映"没有数据"这个事实）。

### 1.3 循环体内哪些调用没有被单独防护（候选，非定论）

代码里**已经**对好几处高风险 Android API 调用做了防御式包装（`dataNetworkType`
`:246-249`、`networkOperatorName` `:253-256`、`serviceState`/反射 `:359-382`、
`registerDisplayListener` 内部 `:412-418`），说明作者本人清楚这些调用会抛异常，
但下面几处**没有**同等级别的包装：

| 位置 | 调用 | 风险 |
|---|---|---|
| `RadioCollector.kt:120` | `SubscriptionManager.getDefaultDataSubscriptionId()` | 每 tick 都查，双卡切换/临时 IPC 故障时可能抛 |
| `RadioCollector.kt:272-295` | `when (reg) { is CellInfoNr -> {...}; is CellInfoLte -> {...} }` 内对 `cellIdentity`/`cellSignalStrength` 及其字段的访问 | 部分 OEM ROM 的 `CellInfo` 子类在特定状态下访问某些字段会抛（已知的 Android 生态坑，非本仓杜撰） |
| `RadioCollector.kt:343-349` | `cellTimestampNanos()`：`info.timestampMillis` / `info.timeStamp` | 同上，property getter 理论上安全，个别 ROM 出过例外 |
| `RadioCollector.kt:172` | `locationProvider?.invoke()`（GPS 路测开启时） | 外部 lambda，权限中途被收回等情形未包一层 |

**如实标注**：本文**无法确认**这四处里究竟是哪一处（或是否是完全没想到的第五处）
在 D-424 那次 run 里真正抛了异常——这需要现场 logcat 或专门构造复现实验，Read 做
不到。能确定的只是：**只要循环体内任何一处抛出未被捕获的异常，观测到的现象就会
和 D-424 记录的完全一致**，而上面四处是当前代码里**唯一**没有被同等防护的调用点，
是排查时最该先看的地方。

---

## 2. 排除项的证据（供交叉核对，避免重复排查）

- **不是采样周期问题**：场景 0/1 各自 26/18 个样本，证明健康时段内 1Hz 远密于场景
  粒度，"周期太长跟不上切换"这个假设不成立（若真是这个问题，应表现为"样本数偏少
  但每场景都有一些"，不是"前两个场景健康、之后精确归零"）。
- **不是生命周期绑定错对象**：`RadioCollector` 实例与 `radio.start()` 调用都在
  run 顶层各发生一次（`TestEngine.kt:210`/`249`），没有任何逐场景循环体内重新
  `new RadioCollector` 或重新 `radio.start()` 的代码——接线本身绑的就是 run 级，
  与规格意图一致，不是这次的问题。
- **不是提前 unregister**：全仓 Grep `radioShareJob` 只有两处——声明赋值
  （`:218`/`248`）与收尾取消（`:619`），后者在整个 run 函数最外层的 `finally`
  里，与任何单个场景的成功/失败/取消路径都不直接关联；场景级取消
  （`invalidate()`，`:200-204`）只作用于 `currentScenario` 这一个 Job 引用，
  从未涉及 `radioShareJob`。

---

## 3. 修复方案（供裁，未改代码）

### 方案 A（推荐，最小改动、与既有代码风格一致）

在 `samplerFlow()` 的 `while (true)` 循环体外层，或至少覆盖 §1.3 列出的四处
未防护调用，加一层 `try { ... } catch (e: CancellationException) { throw e }
catch (t: Throwable) { /* 记日志，本次 tick 降级为 degradedSample，continue */ }`
——**必须显式重新抛出 `CancellationException`**（同 `TestEngine.kt:605` 的既有
先例："外部取消（fail-closed：不吞取消）"），否则会把 run 正常结束/取消时对这个
协程的合法取消也一起吞掉，制造一个新的、更隐蔽的 bug。

**优点**：把"一次异常永久杀死后续全部 radio 数据"降级为"这一秒的样本缺失、下一秒
继续尝试"——与文件里对其余风险调用一贯的处理哲学（局部捕获、显式降级、不让单点
故障扩散）完全一致，不引入新机制。

**代价**：需要决定"catch 到异常时这一 tick 产出什么"——直接 `continue`（跳过
`emit`，该秒无样本）最简单；产出一个类似 `degradedSample(nowNs, "sampler_exception:
${t.javaClass.simpleName}")`（复用 `:318` 已有的降级样本工厂）能保留"这一秒确实
出过错"这个信号供下游诊断，选哪种是产品判断，不是技术判断。

### 方案 B（补充，非替代）

在 `shareIn` 之前加 `.retry { true }`（kotlinx.coroutines 内置操作符：上游异常
时重新从头收集整个 Flow）作为兜底——即便方案 A 遗漏了某个未预见的异常源，`retry`
能保证采样在下一次调度周期重新开始，而不是永久停摆。**不能替代方案 A**：`retry`
每次重启都要走一遍 `samplerFlow()` 顶部的初始化（`baseTm`/`subId`/`display` 等，
`:87-100`），代价比 tick 级的 try/catch 高，且异常发生到 retry 生效之间仍有一小段
真实的数据缺口；两者结合（tick 级防护为主、retry 为最后一道保险）比单用其一更稳健。

### 明确不建议的做法

**不建议**只加日志不改控制流（即只在 `finally` 里打一行"radio sampler died"
后不做任何恢复）——这只解决"发现问题"，不解决"D-424 那种 run 拿不到后 7/9
场景数据"这个实际损失；诊断价值有，但不是修复。

---

*本复核仅使用 Read 工具完成，未跑代码、未连接设备、未查看任何运行时日志——§1.3 的
候选清单是"结构上唯一缺防护的几处"，不是"确认过的病灶"，这层边界如实标注。落盘后
由大脑带入提交。*

---

## 订正记录（2026-08-02，T24 判别数据，不改正文，只追加）

### ① 头号候选被数据杀死

§0/§1 的头号候选"未捕获异常静默杀死采样协程"**被判别数据推翻**。大脑代查（提交
`ef9381b`，**v3 将独立复核，本条截至写作时尚未经二次核实**）：该 run 的
`radio_sample` 表共 **413 行**，1Hz 节拍**全程无缺口**——直接证明采样协程**活到了
run 结束**，不是在某一刻被未捕获异常杀死后永久停摆。413 行里只有**前 44 行**
（对应前约 43 秒）是"真实读数"（有 rat/rsrp/sinr），第 44 秒起的**369 行**
（413−44=369）全部是陈旧/全空样本，但**仍然每秒产出一条**，与"协程死亡后队列
不再接收新样本"这个我原来的核心假设直接矛盾——如果协程真的死了，413 行根本不会
存在，只会停在第 43-44 行附近。

**根因方向（大脑代查，待 v3 复核，非本文自己验证）**：44 秒边界与设备屏灭时刻
（约 16:47:05）重合；健康前段（0–43 秒）已排除静态原因。指向**屏灭后系统对
cell info 查询节流**——`requestCellInfoUpdate()` 在屏灭后系统性拿不到新鲜数据，
`RadioCollector` 按§1.2 提到的既有降级路径（超时退回 `allCellInfo` 缓存并标
`stale=true`，或缓存本身也为空）**如实**把这种情况报成陈旧/全空样本，这正是
`buildSample`/`requestCellInfo`（`RadioCollector.kt` 内）设计时就有的正常降级
分支——**我原文§1.2 已经读到并描述了这条路径，但没有意识到它可能就是本案的实际
机制，反而把"未捕获异常"当成了唯一站得住的候选。**

**§0/§1 其余排除项不受影响**：采样周期问题、生命周期绑定错对象、提前 unregister
三项的排除证据不涉及"协程是否存活"这个前提，T24 数据不影响它们的排除结论；
"stale 判定窗口太短"一项同样不受影响。

### ② 两条判断纪律，已入 `ANALYSIS_LAYER_HANDOVER.md` §2.16（出处标本文）

大脑核验时指出的两处判断缺口，措辞取我自己复盘时用的说法，比核验员的转述更贴切，
已追加为该文件 §2.16 量法族的新增条目：

- **「必要性冒充充分性」**：本文§1.1 只验证了"未捕获异常能不能推出 sampled_n=0
  全空样本"（能），却没有反过来问"sampled_n=0 是不是只能被这一种机制推出"——
  答案是不能：一个**活着**但每秒吐全空样本的协程（屏灭节流即是一例）同样能产出
  一模一样的观测形状。验证了"A 能推出 B"不等于验证了"B 只能被 A 推出"。
- **「预测清单在确认处截断」**：本文§1.2 给候选写了两条可观测预测（"run 照常跑完"、
  "radio 从某一刻永久归零"）并都对上了现有证据，就此停手下结论——漏了第三条本该
  写出的预测："若真有异常在无 `CoroutineExceptionHandler` 的情况下穿出协程，
  Android 默认行为是杀进程"，而这条预测与"run status=completed 正常发出报告"
  直接矛盾。列预测列到能对上手头证据为止就停，而不是列完一个假设**逻辑上蕴含**
  的全部可观测后果，是这次判断出错的具体机制。

### ③ 方案 A 降级：独立健壮性改进，不是本案修复

§3 方案 A（循环体加 `try/catch` + 显式重抛 `CancellationException`）与方案 B
（`.retry{}` 兜底）**均是针对"未捕获异常杀死协程"这个已被推翻的假设设计的**。
**若根因确认是屏灭节流（待 v3 复核），这两个方案都治不了它**——节流导致的降级
本身没有抛异常，`try/catch` 包不住一个没有发生的异常。

**方案 A/B 仍然值得做，但理由变了，且必须显式说清楚，防止后人把它当成这次事故的
修复依据**：§1.3 点名的几处调用（含大脑核验补充的 `:89`/`:104-105`/`:129`，
本文原列的 4 处是**低估**，实际裸奔点未受防护的比我原文写的更多）确实缺乏与
文件其余部分同等级别的防御式包装，这是一处**独立存在的健壮性缺口**——它可能在
未来某次真正的未捕获异常场景下造成与本次表面相似、但成因不同的数据缺失。**这次
事故不是由它触发的**，补上它是面向未来的预防性加固，不是这次 D-424 覆盖率
2/9 的修复。真正对这次事故对症的修复方向（若屏灭节流成立）应是**测量窗保屏的
运维约束**（外场协议要求全程亮屏，或采集端识别"屏灭导致的节流"并作为一种独立的
`stale` 成因显式标注，而不是与"modem 时戳过期"共用同一个布尔位）——这个方向
本文未展开，留给下一步。
