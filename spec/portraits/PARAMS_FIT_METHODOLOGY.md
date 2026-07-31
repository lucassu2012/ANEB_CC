# Profile-3 Portrait Params Fitting Methodology (D-62)

> observation -> Profile params honest approximate fit. RED LINE: params gate NOT unlocked (params all null, source_portrait=PENDING-CAPTURE); approx values live only in params_fit_approx. Adversarial audit caught 2 overclaims (doubao downlink_media / deepseek pop_ip, both corrected).

## Schema record decision

决策:不翻门控。`params:` 七字段全部保持 null,`source_portrait` 仍为 "PENDING-CAPTURE"(与仓内 tongyi.yaml/doubao.yaml 现状一致)。近似拟合值不得写回 params(写回=消费方可拿去"模拟真实业务"对外宣称=严重违规)。改为新增一个与 observed_ui_layer/observed_network_layer 平级的独立段 params_fit_approx,段头显式声明"近似/非模拟级/口径分层/不解禁门控"。该段仅承载观测锚点,不构成分布,keep_pending=true 的字段禁止对外作分布/仿真表述。

YAML 结构(建议追加到各 App 的 *.yaml,params 段之后):

params_fit_approx:
  # ⚠️ 近似拟合段——非模拟级(non-simulation-grade)、口径分层、不解禁 params 门控。
  # 铁律:本段存在≠params 可填;source_portrait 仍 PENDING-CAPTURE。
  # caliber∈{direct, order-of-magnitude, ui-proxy, none};keep_pending=true 的字段
  # 不得对外作分布宣称,不得被 Profile 2 服务端仿真当真实业务口径引用。
  _meta:
    non_simulation_grade: true
    gates_params: false          # 本段不解禁 params=null 门控
    unlocks_source_portrait: false
    caliber_legend:
      direct: "同层直采(如网络层 IP/字节),精度受样本限,恒 LOW"
      order-of-magnitude: "仅量级锚点,聚合/未拆分,非分布,keep_pending=true"
      ui-proxy: "UI 呈现层代理(含 App 渲染),显式 ≠网络ITL/推理停顿,keep_pending=true"
      none: "无同口径直采源→PENDING,不落值(R-10 诚实缺席)"
  fields:
    <field_name>:
      value: <观测锚点 或 "PENDING">
      caliber: <direct|order-of-magnitude|ui-proxy|none>
      source_layer: <network|ui|api|none>
      keep_pending: <bool>       # true=不脱 PENDING
      confidence: <LOW|INCONCLUSIVE>
      cross_caliber_note: "本值不得跨层/跨口径/跨产品互填"
      note: <披露越界残留风险,如'合计非纯上行'/'文本非媒体'/'SNI主机名非解析POP IP'>

## Fitting methodology

观测→参数拟合方法学(三层口径 + caliber 分级):

1) 口径分层来源映射(铁律3,不可互填):
   - 网络传输层(SNI/IP/字节)→ 只填 pop_ip_list、request_size_bytes_dist(量级)、downlink_media_bytes_dist(需真媒体字节)。
   - UI 呈现层(含 App 渲染,a11y/cadence/TTFT)→ 至多作 ui-proxy 填 token_interval_ms_dist,且必须显式标 ≠网络ITL;绝不填 think_pause/网络字节。
   - API token 层(明文时序)→ 免 root mitm 确认拿不到(D-61),故 token_interval/think_pause 对全部消费 App 无同层直采源。且跨产品不可借(Kimi Code k2.7 API ≠ Kimi App)。

2) caliber 分级规则:
   - direct:字段与来源同层且为事实型直采(如网络层 IP:port)。IP 已解析→可 keep_pending=false(tongyi/kimi);仅采到 SNI 主机名未解析 IP→caliber 仍 direct 但 keep_pending=true(doubao/deepseek)。
   - order-of-magnitude:同层字节但聚合/未拆上行/未含完整流式体→仅量级锚点,keep_pending=true(doubao/deepseek request_size)。
   - ui-proxy:UI 层代理网络时序,keep_pending=true + 显式≠网络ITL(doubao~100ms/tongyi~66ms token_interval)。
   - none:无同口径来源→PENDING,不落值。

3) PENDING 判据(满足任一即保持 PENDING/keep_pending=true):
   - 无同层直采源(R-10 诚实缺席);
   - 仅有跨层/跨口径/跨产品代理(UI cadence→网络ITL、TTFT→思考停顿、文本字节→媒体字节、事件计数→时长、k2.7 API→App);
   - 字段规范内容缺席(如 pop_ip_list 规范=解析后 POP IP,仅有 SNI 主机名即缺席);
   - 加密聚合不可切分为字段语义(kimi 7003 非标长连+jpush)。
   样本少(每 App 数次)→ 一律 LOW/INCONCLUSIVE,禁止升 order-of-magnitude 以上。

## Provenance metadata (R18, IMPLEMENTED — spine-3 #8, D-71/72)

上文 "Schema record decision" 段的 `_meta`/`cross_caliber_note` 是 D-62 的**提案**;**实际落地**的
`params_fit_approx` 结构更精简(`gates_params`/`source_portrait_unlocked` 在段级,`fields.<f>` 每字段
value/caliber/keep_pending),D-71 起每个 fit 字段再 additive 补三键 **provenance**,并由 `check_redline.py`
**R18 机器强制**(presence + 枚举 + 与 caliber 一致):

| 键 | 域 | 语义 |
|---|---|---|
| `source_layer` | `network` / `ui` / `none` | 该 fit 值取自哪个观测层。**不含 `api`**——App 画像口径**绝不**从 API 直调 token 层取值(那是 ApiProbe 门,§6 口径边界);api-direct 属另一 caliber,跨层即红线。 |
| `confidence` | `LOW` / `INCONCLUSIVE` | 与 observed_*层同词汇。LLM 画像恒 LOW-at-best(§1.2);无同层源(PENDING)→ INCONCLUSIVE。 |
| `note` | 短标准标 | 简短口径标;详细 prose 仍在 `value`。 |

**caliber ↔ provenance 一致性(R18c,机器强制)**——provenance 不得与 fit 真实强度/层漂移:

| caliber | source_layer | confidence |
|---|---|---|
| `direct` | `network` | `LOW` |
| `order-of-magnitude` | `network` | `LOW` |
| `ui-proxy` | `ui` | `LOW` |
| `none` | `none` | `INCONCLUSIVE` |

任一 fit 字段的三键缺失、枚举越界、或与 caliber 不符 → R18 FAIL(反例见 `test_check_redline.py`
的 `test_R18_*`)。形状(键在不在、类型对不对)另由 `portrait.schema.json` + `validate_schema.py` 守(#6):
**schema 管形状 / redline 管语义**,双门互补。

## Per-field capture gate — plan B (R19, IMPLEMENTED — PO 批复 2026-07-31, D-348)

`source_portrait` 曾是**单个字符串**：要么全 PENDING、要么一翻全翻。缺陷是可算的——
token/think/tool 三字段在本方法学口径下**永不可得**，单串门于是要么被它们永久卡死，
要么翻门时把它们一起洗白成"已采"。**两者都错**，所以 PO 选定方案 B：逐字段门控。

每份画像新增 `params_capture_status:`，7 个 param 字段各带 `status` + `reason`：

| status | 含义 | 阻塞翻门? | 能否将来变 CAPTURED |
|---|---|---|---|
| `PENDING` | 本方法学够得到，只是尚未采 | **是** | 能（采到即可） |
| `PENDING-BY-CALIBER` | 仅现红线外够得到（root mitm，D-24/D-61），据此不采 | 否 | 仅当 PO 另行授权越线 |
| `N/A-BY-CALIBER` | 口径上永不可得 | 否 | **永不** |
| `CAPTURED` | 已采到真分布 | — | — |

两个 `-BY-CALIBER` **不是同义词**：N/A 是"这条路不存在"，PENDING-BY-CALIBER 是
"路在红线外，我们选择不走"。二者都不阻塞翻门（否则就是方案 A 的死锁），但**语义必须分开**，
因为前者永远不会变，后者可能因一纸授权而变。

**本轮定性裁定（D-348，机器冻结在 `check_redline.RULED_STATUS`）**：
`token_interval_ms_dist` / `think_pause_ms_dist` = `PENDING-BY-CALIBER`；
`tool_loop_cadence` = `N/A-BY-CALIBER`。改动它们会被 R19d 直接拒绝。

**翻门判据** = 无 `PENDING` 字段剩余；`check_redline` 每次运行逐画像打印门态
（`gate[<app>]: blocked by N: …` / `READY to flip`），所以这个状态有一个操作者据以行动的读者，
不是只被守卫读一次的死字段。

**咬合方式（R1 与 R19c 各管一个方向，不重复报同一缺陷）**：
R1 = 「params 有值 ⇒ 该字段 status 必须是 CAPTURED」（防编造）；
R19c = 「status 是 CAPTURED ⇒ params 必须有值」（防空口宣称）。
R1 由此从"全 null"推广为"有值必须有采集背书"——**在方案 B 之前两句话说的是同一件事**，
而现在前者允许单字段独立解锁，后者不允许。R19e 另外禁止"半翻"：`source_portrait`
一旦离开 `PENDING-CAPTURE`（须形如 `<app>-app-capture-YYYY-MM-DD`），就不得再有 `PENDING` 字段。

## PENDING gaps (what is needed to fill)

- token_interval_ms_dist(全 4 App 保持 PENDING):根因是免 root mitm 拿不到明文 token 时序(D-61)。补齐需 root/TLS keylog 抓包解密,或 App 明文 token 事件源。当前仅 doubao(~100ms)/tongyi(~66ms)有 UI-proxy 弱锚(≠网络ITL),deepseek/kimi 连 UI cadence 都为 null。
- think_pause_ms_dist(全 4 App):同 root mitm 阻塞;须能区分流内思考停顿 vs 端到端 TTFT(现有 TTFT 均含网络+App 渲染)。补齐需明文流式 token 时间戳。
- tool_loop_cadence(全 4 App):四者均消费聊天 App,无工具编排。补齐需在具备工具调用/Agentic 场景下新增一维观测(tool-call 事件序列采集),消费聊天口径可能永久 PENDING/不适用。
- session_duration_s_dist(全 4 App):现仅 per-turn 时序,无会话边界埋点。补齐需会话级 instrumentation(会话开始/结束事件),而非 per-turn 或 UI 事件计数换算。
- downlink_media_bytes_dist(全 4 App):无真实媒体字节隔离。补齐需真媒体场景(图片/文件/音频)+ 端点级字节隔离;doubao frontier5 audio-ws-lq 音频 WS 已存在但未做字节隔离,是最近的可补采点;禁止以文本下行冒充媒体。
- request_size_bytes_dist:doubao/deepseek 有 order-of-magnitude(需隔离纯上行才能脱聚合);tongyi 需采到完整流式响应体(现 partial);kimi 需可解密切分 per-request(现加密聚合不可切)。
- pop_ip_list:doubao(4 SNI 主机名)与 deepseek(SNI 主机名+第三方 CDN/遥测端点)需 DNS 解析出原始 POP IP 才能 keep_pending=false;tongyi/kimi 已有真实 IP,其中 kimi 的'华为云广州段/自有 IM'轻推断需多点复采确认 ASN/地理归属。
