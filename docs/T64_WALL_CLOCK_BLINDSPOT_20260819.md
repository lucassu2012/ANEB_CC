# 墙钟盲区：D-494 那个 10 天误差，在产物侧结构性不可见（T64，2026-08-19）

> **性质**：缺口发现 + 修复提案，**未动任何代码**。改动涉及 wire 契约与 schema，按治理规则
> 「先 spec 后代码」需大脑裁定后再动手。
> **触发**：D-494 待办清单里那条「分析层按日分桶遇 08-05→08-15 断层须并桶」。本文没有直接
> 去写那个守卫——**先去数语料里那个条件出现过几次**（D-302 的教训），结果发现了一个更根本的问题。

## 0. 一句话结论

设备墙钟错了 10 天这件事，**从任何产物里都查不出来**——而唯一能查出它的那个信号，
服务端**每一次 `/echo` 响应都在发**，客户端**连字段都没声明**，反序列化时直接丢弃。
D-494 是靠 `git log` 时间戳偶然发现的，不是靠测量装置发现的。

## 1. 先做的事：数一数那个条件出现过几次

D-494 的待办要求给按日分桶加并桶守卫。动手前先核实语料里真有这个断层——

```
evidence/ 下 63 个 JSONL 语料，按 run.started_at_epoch_ms(+8) 分日：
2026-07-13(922) 07-14(2274) 07-31(80) 08-01(39) 08-03(71) 08-04(103)
```

**没有任何一条记录落在 08-05 或 08-15。** 受时钟事件影响的那批数据是语音语料
（`voice_result` 表），而按 D-482 的核实，语音数据**不进 `ResultReporter`/`campaign_report`/
CSV 任何服务端聚合面**——它根本不流经 `validity_rollup.py` 的按日分桶。

**所以直接写那个并桶守卫就是在测空气**（D-302 同族：「一条突变存活时，先去数语料里那个条件
出现过几次——0 次的话你测的是空气」）。守卫不写。但问题没完——

## 2. 真正的缺口：分析层完全信任设备墙钟，且无从校验

`validity_rollup.py:133` 的按日分桶：

```python
day = (datetime.fromtimestamp(ms / 1000.0, timezone.utc) + shift).strftime("%Y-%m-%d")
```

`ms` 来自 `run.started_at_epoch_ms`，即**设备墙钟**。设备墙钟错 10 天 → 日桶错 10 天 →
趋势表、按日分桶的一切判读全部静默错位，**而没有任何东西会说一句话**。

这不是 `validity_rollup` 一处的问题：`run.started_at_epoch_ms` 是全仓唯一的时间基准，
所有「什么时候测的」都源自它，而它**没有任何交叉校验**。

## 3. 既有的 `offset_suspect` 守卫为什么救不了（按设计如此）

wire body 的 `clock` 块有 `offset_start_us`/`offset_end_us`/`drift_ppm`/`offset_suspect`，
`trust_rollup.py`（D-111）确实消费了 `offset_suspect` 与 `drift_ppm`——不是「只写不读」的字段。

但 **`offset_suspect` 判的是漂移率**（R-22：`|drift_ppm| > 100`），**不是绝对偏移量**。
一台钟差 10 天但走得很稳的设备，`drift_ppm ≈ 0`，`offset_suspect = false`，畅通无阻。

那能不能改用绝对偏移 `|offset_start_us|` 来判？**不能，而且是我先动手查了源码才没踩这个坑：**

- 服务端 `srv_ts_us` = **进程启动单调锚点的微秒差**（`server/clock.go`，R-24 明文有意为之：
  「墙钟步进（NTP makestep、宿主机校时）无法影响任何逐事件时间戳」）；
- 客户端 `t0/t3` = `SystemClock.elapsedRealtimeNanos()`（`AnebClient.kt:849`）＝**设备开机
  单调时钟**；
- 故 `offset = ((t1-t0)+(t2-t3))/2` 是**两个单调计数之差**，其绝对值 ≈「服务端进程运行时长
  − 设备开机时长」，**按设计就不含任何墙钟信息**。

实证吻合：全语料 12906 个场景的 `|offset_start_us|` 最大值 = **12.24 天**（D-479 那条，
本机 Go server 刚启动而 P40 已开机 12 天），次大 **3.73 天**（E-01 进程运行时长差），
全部 `offset_suspect=false`——**这些大数字全是正常的，不是异常信号**。

> 这一步是本文最该记下的方法：我差点用 `|offset|` 建一个守卫，源码一读才发现它按设计
> 就测不了墙钟。**先证明那个量真的是你以为的那个量**（同族：T63 里 `n1_rtt_p50_ms` vs
> `rtt_ref_ms_pre` 的同源性对账）。

## 4. 唯一能查出它的信号：每次 echo 都在发，客户端不接

服务端 `handlers_echo.go:43-44`，**每一个** `/echo` 响应都回带**真墙钟**：

```go
out = append(out, `,"anchor_wall_unix_ns":`...)
out = strconv.AppendInt(out, anchorWallUnixNs, 10)
```

**线上实测**（本机 curl E-01，2026-08-19）：

```json
{"t1_us":448184048659,"anchor_wall_unix_ns":1786663903945004974,
 "observed":"...","t2_us":448184048665}
```

`anchor_wall_unix_ns + srv_ts_us` 可还原服务端真实墙钟：**2026-08-19 12:01:27 (+8)**，
与实际时间吻合。**这就是那个独立参照。**

而客户端 `AnebClient.kt:67-72` 的 `EchoWire`：

```kotlin
private data class EchoWire(
    @SerialName("t1_us") val t1Us: Long,
    @SerialName("t2_us") val t2Us: Long,
    val observed: String? = null,   // <- 只接了这三个
)
```

**`anchor_wall_unix_ns` 连字段都没声明**，反序列化时静默丢弃。全仓 grep 该字段名在
`app/` 下**零命中**。

> 于是链路是这样的：服务端每次都把真墙钟递过来 -> 客户端每次都扔掉 -> 产物里没有它 ->
> 分析层无从校验 -> 设备钟错 10 天全程无人知晓 -> 最后靠 `git log` 偶然发现。

## 5. 第二条参照（已存在但脆弱）

服务端按**自己的墙钟**给结果文件命名（`handlers_results.go:105`）：

```go
path := filepath.Join(dir, time.Now().Format("20060102")+".jsonl")
```

D-494 期间，设备以为 08-05，而 E-01 会把同一批结果归档进 `20260815.jsonl`——**文件名与
文件内容自相矛盾，这本身就是告警**。

但这条参照**脆弱**：产物归档进 `evidence/` 时文件普遍被改名（`wave0_raw.jsonl`、
`full_corpus_labelled.jsonl`…），日期信息随即丢失。可作为辅助佐证，不宜作为主判据。
（另注：D-479 那次两端都错着同样的 10 天，这条参照当时也抓不到——它只在服务端钟正确时
有效，而 E-01 作为 NTP 同步的生产节点满足该前提。）

## 6. 修复提案（三选一，供裁）

| 方案 | 改动 | 强度 | 代价 |
|---|---|---|---|
| **A** | `EchoWire` 加一个字段，随 `clock` 块落进 wire body + schema，分析层加一条「设备墙钟与服务端墙钟之差超阈值」的门 | **最强**（主判据，逐 run 可查） | 动 wire 契约 + schema + 一条新守卫 |
| **B** | 只在 App 侧比对并打 logcat 告警，不进 wire body | 中（操作者当场可见，产物仍无记录） | 最小，纯客户端 |
| **C** | 分析层用服务端文件名日期做辅助校验 | 弱（易因改名失效） | 零代码，纯纪律 |

**本人倾向 A**：这是唯一能让产物**自证时钟可信**的方案，且改动很小（一个字段 + 一条门）。
理由与 R-22 给 `drift_ppm` 设门同构——既然已经为「钟走得稳不稳」设了门，「钟指得对不对」
是同一层面的仪器可信度问题，却至今无门。

**但不擅自动手**：这是 wire 契约 + schema 变更，按 T47 治理规则「先 spec 后代码」需大脑
裁定。且阈值取多少（几秒？几分钟？）本身要定——RTT 量级的偏差是正常的，10 天不是，
中间的线在哪里需要拍板，本文不代定。

## 7. 边界与未做的事

- **未写 D-494 待办的并桶守卫**，理由见 §1（语料里 0 次，会是空气守卫）——如实报告这个
  否定，而不是写一个看起来在干活的守卫。
- **未改任何代码**（提案 A/B/C 均未实施）。
- **未改阈值/常量**。
- 本文不涉及 T63 的三常量议题，两者独立。


## 8. 提案 A 的详细 spec（先 spec 后代码；**本节只是规格，未实施，待裁**）

按 T47 治理规则「先 spec 后代码」，写 spec 是被许可的第一步，**动代码仍需大脑裁定**。
本节把 §6 的提案 A 写到可以直接照着实施的粒度，使裁定通过后无需再设计。

### 8.1 要量的到底是什么

**设备墙钟与服务端墙钟之差**（skew），而**不是**已有的 `offset_*`（那是两个单调计数之差，
§3 已证明它按 R-24 设计就不含墙钟信息）。

服务端真实墙钟可由 echo 响应现有的两个字段还原：

```
serverWallMs ≈ anchor_wall_unix_ns / 1e6 + t1_us / 1e3
```

（`anchor_wall_unix_ns` = 服务端进程启动时的墙钟；`t1_us` = 该请求到达时距进程启动的单调微秒差。
§4 已用线上实测验证这个还原式给出的时刻与实际吻合。）

设备侧需要在**同一时刻**取一次墙钟。现状：`System.currentTimeMillis()` 在
`TestEngine.kt:107` 取过一次（`run.started_at_epoch_ms`），但那是 run 开始时刻，
与 echo 时刻相差整个 run 的前置时长——**不要用它做减法**，应在 echo 打 `t0` 的同一行取。

```
wall_skew_ms = deviceWallMsAtT0 − serverWallMs
```

### 8.2 客户端改动（三处，均 additive）

1. **`AnebClient.EchoWire`** 增字段（`AnebClient.kt:67-72`）：
   ```kotlin
   @SerialName("anchor_wall_unix_ns") val anchorWallUnixNs: Long? = null,
   ```
   **可空且带默认值**——旧服务端不回该字段时反序列化不炸（E-01 现版本已回带，见 §4 实测，
   但客户端不能假设对端一定是新版）。

2. **`AnebClient` 的 echo 路径**：在取 `t0Us` 的同一处加一次 `System.currentTimeMillis()`，
   响应回来后算 `wallSkewMs`；`anchorWallUnixNs == null` 时该样本的 skew 为 `null`
   （R-10：测不出是 null，不是 0）。`EchoResult` 增一个 `wallSkewMs: Long?`。

3. **`ScenarioKpi`**：把该场景 clock_sync 各样本的 `wallSkewMs` 取中位数
   （非 warmup 样本，同既有 `clockSyncRttP50Ms` 惯例），落进 `clock` 块。

### 8.3 契约与 schema

`spec/schemas/result-run.schema.json` 的 `definitions.scenario.clock`（现有 4 个必填字段：
`offset_start_us`/`offset_end_us`/`drift_ppm`/`offset_suspect`）**新增 1 个非必填字段**：

```json
"wall_skew_ms": { "type": ["integer", "null"] }
```

**不进 `required`**——历史语料没有它，进 required 会让既有 63 份 JSONL 全部违约
（`spec/README.md §3` 只增不改不删纪律）。

### 8.4 判据与阈值（**阈值本身待拍板，本节只给取值区间与理由**）

```
wall_clock_suspect ⟺ |wall_skew_ms| > WALL_SKEW_MAX_MS
```

**取值该落在哪个区间——两侧各有硬约束**：

| 下界约束 | 上界约束 |
|---|---|
| 必须**大于**正常的网络/NTP 抖动，否则误报。参照：本项目实测 RTT 上界 106ms（T63 §1），NTP 同步日常偏差通常 <1s | 必须**小于**任何「已经足以毁掉判读」的偏差。参照：D-494 的 10 天 = 8.64×10⁸ ms；按日分桶只要错 1 天（8.64×10⁷ ms）结论就全错 |

**区间极宽（约 3 个数量级）**，故这个常量不敏感——同 T63 §3 的形状，不必精调。
**建议 `60_000`（60 秒）**：比任何合理的 NTP/RTT 偏差高两个数量级以上，比任何会影响
按日分桶的偏差低三个数量级以上。**但这是建议不是决定**，且按 §8.7-2 同族纪律应标
`PROVISIONAL` 直到有真实分布支撑。

**取值不敏感这一点本身要写进代码注释**，否则后人会以为 60000 是标定出来的。

### 8.5 消费方（新字段必须有真实读者，D-276）

1. **App 侧**：`TestEngine` 的 run 前置日志加一行
   `CLOCK_SKEW skew_ms=… suspect=…`——操作者当场可见（这条等价于提案 B，是 A 的子集，
   顺带落地）。
2. **分析层**：`scripts/trust_rollup.py` 已经是「仪器可信度」的归口（D-111 消费
   `offset_suspect`/`drift_ppm`），`wall_skew_ms` 属同一类信号，**加在那里而不是另起一处**。
   输出：按 (点位, 运营商, 时段) 报 skew 标注数 / 可疑数 / `|skew|` 中位。
3. **发布门**：`publish_check.py` 增一条——语料中若有 `wall_clock_suspect` 记录，
   **按日分桶的一切结论不可发布**（这正是 D-494 当时缺的那道门）。

### 8.6 测试计划

- 纯 JVM 单测（`AnebClient`/`ScenarioKpi` 侧）：还原式正确、`anchorWallUnixNs == null` 时
  skew 为 null 不为 0、中位数取法与既有 RTT 惯例一致。
- **反例证伪**（D-322，不推理）：构造一个 skew = 10 天的样本，断言判 suspect；
  构造 skew = 50ms 的样本，断言不判 suspect。
- **绊线**（同 T66/D-508 的形状）：`WALL_SKEW_MAX_MS` 与「会毁掉按日分桶的最小偏差」
  之间的量级关系被钉住，改动即失败。
- Python 侧：`trust_rollup` 与 `publish_check` 各配反例，且**新字段缺失时走缺席分支
  不改分母**（D-111 既有纪律）。

### 8.7 兼容性与回滚

- **全部 additive**：新字段可空非必填、旧服务端不回带即为 null、历史语料不受影响。
- **回滚**：删字段即可，无数据迁移（不落 Room——这是 wire/分析层信号，不需要设备端历史查询）。
- **与 Codex 侧无关**：`anchor_wall_unix_ns` 是 E-01 **既有**回带字段（§4 线上实测确认），
  **本提案不要求 E-01 做任何改动**——与 D-483 那份部署请求单是两件独立的事，不相互阻塞。

---
*§8 追记 2026-08-19 · 规格供裁，未实施 · 与 §6 提案 A 对应*

---
*T64 · 2026-08-19（真实历，D-494 校正后）· 触发自 D-494 待办 · 全部结论有 file:line 与
线上实测支撑 · 分析过程见会话 scratchpad，未入库*
