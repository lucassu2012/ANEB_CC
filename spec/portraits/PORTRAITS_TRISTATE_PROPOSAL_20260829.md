# Profile 3 画像字段三态定案提案（SPEC-4 / 4.2 → SPEC-1 裁项 B 供稿）

> 属主：v4（spec lane，T82）。**性质：技术论证 + 代价书，不替 PO 下结论**——每个裁项留【PO-裁定占位】。
> 去向：交 SPEC-1（v2/T79）并入 `docs/DECISION_REQUEST_20260829.md` 裁项 B。
> 单源背景：`docs/PROGRESS_DIAGNOSIS_AND_RESPEC_20260828.md` §1.4「M3 画像字段挂 PENDING-BY-CALIBER 六周无人回头裁」
> ——⚠ **该文件在分析分支 `claude/aneb-project-progress-analysis-x2wn7x`**，本树需 `git show origin/…:docs/…` 读取。
> 验收锚：七字段 × 四 App 全覆盖零遗漏；每选项有可验证代价陈述；v2 可直接引用。
> **本稿经三镜头对抗核验后定稿**（事实/逻辑/消费者），修订记录见文末 §7。

---

## 0. 一句话结论（给赶时间的读者）

**真正需要 PO 裁的暧昧字段精确地只有两个**：`token_interval_ms_dist` 与 `think_pause_ms_dist`
（现态均 `PENDING-BY-CALIBER`）。其余五字段无需进裁项 B——`tool_loop_cadence` 已是
`N/A-BY-CALIBER` 终态（R19d 机器冻结，2026-07-31 PO 已裁），另四字段是红线**内**的
`PENDING`（采集执行问题，不是画像口径问题）。**⚠ 2026-08-30 订正**：本句原写「归属外场/采集线**复活**裁项」——`D-587` C 裁定**外场线终止**（非复活），故这四格改归「替代采集维度或逐格定终态」，详见 §末的 C 裁定注。
**本提案请 PO 只对这两个字段裁**：正式放弃 / 改 UI-proxy 口径纳入 / 解禁受控采集 / **维持暂缓（带触发条件）**。

> ⚠ **一句话防误读**（对抗核验问题2）：裁这两个字段**不解锁画像翻门**。翻门被另外**四个** plain-`PENDING`
> 字段挡着（§4），裁项 B 无论选什么，翻门阻塞计数恒为 4、门照样翻不了。裁项 B 解决的是
> 「一个越线决定悬了六周」的**治理债**（把状态从「悬置」变「确定」），不是「差两格就完工」——
> Profile 3 离完整，差的是那四格的采集，不是这两格的裁定。

---

## 1. 为什么现在必须裁：暧昧态本身是治理债

三态门控（D-348 spine-3 方案 B，2026-07-31 PO 批）已在机器侧生效——`check_redline.py` 的
`gate_state()` 只让 plain `PENDING` 阻塞 `source_portrait` 翻门，`PENDING-BY-CALIBER`/`N/A-BY-CALIBER`
不阻塞（L116-127）。这解决了「一个永不可达字段冻死整个门」的方案 A 死锁，且让暧昧态在机器侧
**非阻塞且诚实**——所以本提案**不主张「紧急」**，只主张「该有个了结」。

`PENDING-BY-CALIBER` 的语义是「路在红线外（root mitm，D-24/D-61），我们**选择**不走，
**但 PO 授权越线后仍可翻 CAPTURED**」（方法学 `PARAMS_FIT_METHODOLOGY.md` Plan B 表 L94/L98-100）。
这是一个**悬而未决的暧昧态**：它既不是「做不到」（那是 `N/A`），也不是「还没做」（那是 `PENDING`），
而是「等一个从未被正式提出的越线授权决定」。六周里没人回头把这个决定摆到 PO 面前——
**它悬着不产生技术故障（门不被它挡），但它是一笔没结的账**：任何读画像的人都要先搞清
「这两格为什么既没采也没放弃」，而答案是「等一个没人提的 PO 决定」。

**裁掉它 = 把这笔账结清**：PO 说「放弃」→ 暧昧转确定的不可得；说「授权越线采」→ 转确定的采集任务；
说「改用 UI 口径」→ 转口径变更；说「维持暂缓」→ 至少写下**触发条件**（什么情况下重新提上台面），
让「悬置」从「无限期」变「有条件」。四条路都让 `PENDING-BY-CALIBER` 这个模糊状态退役或收敛。

---

## 2. 七字段 × 四 App 现态总表（实测，四 App 逐字一致）

四个画像（`doubao`/`deepseek`/`kimi`/`tongyi`）的 `params_capture_status` 七字段**状态与 reason 完全一致**
（D-348 门控统一，三镜头核验逐字节确认；差异全在 `params_fit_approx` 近似层与 `observed_*` 观察层）。

| 字段 | 现态 status | 是否阻塞翻门 | 红线关系 | fit 层已有近似（哪些 App） | 归属 |
|---|---|---|---|---|---|
| `token_interval_ms_dist` | `PENDING-BY-CALIBER` | **否** | 越 D-24（明文 token 时序需 root mitm，D-61 实测不可得） | ui-proxy：tongyi ~66ms、doubao ~100ms；deepseek/kimi 无（Compose 同帧合流不可测） | **裁项 B 核心** |
| `think_pause_ms_dist` | `PENDING-BY-CALIBER` | **否** | 同上（流内思考停顿需明文流式 token 时间戳） | 四 App 全 none/INCONCLUSIVE——TTFT 含网络+服务端，非流内思考停顿 | **裁项 B 核心** |
| `tool_loop_cadence` | `N/A-BY-CALIBER` | 否 | 口径外（四 App 皆消费型对话，无工具编排） | 四 App 全 none | **已终态**（R19d 冻结，无需裁） |
| `request_size_bytes_dist` | `PENDING` | **是** | 红线**内** | order-of-magnitude：deepseek（上 4.7/下 27.9KB）、doubao（下 146.8/上 25.0KB）；HTTP/2 复用致单轮不可隔离 | 采集线（非裁项 B，见 §4） |
| `session_duration_s_dist` | `PENDING` | **是** | 红线**内** | 四 App 全 none（需 a11y 会话埋点，代码未落地） | 采集线（非裁项 B） |
| `downlink_media_bytes_dist` | `PENDING` | **是** | 红线**内** | 四 App 全 none（需真媒体场景+端点级字节隔离；禁文本下行冒充媒体，R15） | 采集线（非裁项 B） |
| `pop_ip_list` | `PENDING` | **是** | 红线**内** | direct/keep_pending=false 三 App：deepseek 单稳定 WAF IP、kimi 华为云 IP 池、tongyi 双 POP；最接近 CAPTURED | 采集线（非裁项 B） |

**读表要点**：阻塞翻门的是**四个 plain-`PENDING`**（右四行「是」），不是两个 `PENDING-BY-CALIBER`。
裁项 B 处理的两个字段本就在阻塞集之外——这就是 §0 那句「裁完门仍翻不了」的机器依据。

---

## 3. 裁项 B：两个 PENDING-BY-CALIBER 字段的四选一代价书

### 现役唯一约束（任何选项的机器边界，先说清）

- **R5**（`check_redline.py` L182-186）：两字段 fit caliber **机器禁止** `direct`/`order-of-magnitude`，只准 `ui-proxy`/`none`——跨层红线（UI cadence ≠ 网络 ITL）。
- **R19d**（L325-329）：两字段 status 冻结在 `PENDING-BY-CALIBER`，任何直接改动**当场 FAIL**。
- **铁律 3**（方法学 L37-42）：口径分层不可互填，UI 层至多 ui-proxy，绝不回填 `think_pause`。

**因此 A/B/C 三选项落地都要连带改 `check_redline.py`（R19d/R5）**——是三者共同成本，非某选项独有；唯选项 D（维持暂缓）零代码改动。

---

### 选项 A｜正式放弃（改 status 为终态不可得）

**动作**：两字段 status 从 `PENDING-BY-CALIBER` 改为终态——建议复用 `N/A-BY-CALIBER`（现行红线下永不可得），
或新增 `ABANDONED-BY-PO`（若 PO 想与「口径上永不可得」区分、保留「红线未来放开则重开」的可追溯性）。R19d 同步改。

**可验证代价**：
1. Profile 3 永久不宣称 token 间隔 / 思考停顿的分布模拟——`params` 两字段恒 null（这本是 R1/R19c 现在钉的，放弃只是定死）。
2. **UI-proxy 近似值不受影响、继续留在 `observed_ui_layer`**（不是 `params`；已核 doubao.yaml `cadence_ui_ms:100`@L134、tongyi `cadence_ui_ms:66`@L122 确在 observed 段，params 两字段四 App 全 null）——仍可作「UI 呈现层流式节奏」有限引用。
3. 放弃后 Profile 3 仍能宣称：①UI 呈现层端到端 TTFT 与流式节奏真实观察（四 App 已采）；②网络传输层拓扑+字节量级（三 App full）；③四个红线内 PENDING 字段若采够仍可 CAPTURED。**失去的只是「流内 token 级时序分布」这一层，而它从 D-24 起就在红线外**。
4. **诚实标注 A 的实质**（对抗核验问题1）：A 对外零改变（params 现状本就 null，A 后仍 null），它退役的是**一个内部 status 标签的暧昧**——即 A 的收益是「治理整洁」，代价是「若未来红线放开需重走登记」。这是一笔小账，不是大动作。

---

### 选项 B｜改 UI-proxy 口径纳入 params

**动作**：把 `token_interval_ms_dist` 的 params 语义从「网络 ITL」重定义为「UI cadence（显式标注 ≠网络 ITL）」，放宽 R5 允许该字段 params 取 ui-proxy 值。

**可验证代价**：
1. **`think_pause` 这条走不通**——四 App 的 UI 层根本区分不出「思考停顿」：TTFT 含网络+服务端排队，非流内 token 间停顿（doubao.yaml L82：「TTFT 1984ms 为首 token 前整体 UI 时延含网络+服务端，非流内思考停顿」）。选 B 只救 `token_interval` 一字段，`think_pause` 仍需单独走 A/C/D——**B 无法整体解决裁项，必留一字段悬空**。
2. **口径四 App 不齐**：ui-proxy 值只有 tongyi(66ms)/doubao(100ms) 有；deepseek/kimi 是 Compose 同帧合流、cadence 为渲染伪影（p50≈0–0.4ms），不能作宣称（deepseek.yaml L137）。纳入后四 App 里两个有值两个 null，横比时该字段一半真值一半空——比全放弃更难解读。
3. **违背铁律 3 与现役 R5**：把 UI cadence 填进 params 正是方法学 L52 点名禁止的跨层回填；落地必须削弱一条现行红线，而这条红线是诚实性体系核心资产（跨层不可互填）。
4. **下游污染——推测性风险（无已知消费方实例，对抗核验问题3）**：方法学 L14-15 立了规则（keep_pending 字段不得被 Profile 2 仿真引用），但**本提案未点名任何真实读 params 且丢弃 caliber 标签的 Profile 2 消费方**；「标签多层传递易丢、UI cadence 被当网络 ITL 消费」是一条**尚无实例的失效模式**，此处如实标为推测，非已验证事实。
5. **代价方向**：中高（救不了 think_pause、口径不齐、要削红线、有推测性下游面）。

---

### 选项 C｜解禁受控采集（PO 授权越 D-24 红线）

**动作**：PO 逐字授权越 D-24 红线，走 root mitm / TLS keylog 采明文 token 时序，两字段翻 CAPTURED。

**可验证代价**：
1. **技术前置已实测为高门槛**：D-61 记录——普通 CA 装**用户证书库**对全 App（含千问）HTTPS 443 **均未解密**（疑似证书锁定），需**系统 CA（root）**。P40 是否可 root、root 后是否触发 App 侧完整性检测（字节生态有风控）均未验证——即授权后仍可能技术上做不成。
2. **合规叙事代价**（对抗核验问题4 已订正范围）：D-24 是项目最重红线之一——「封闭第三方 App 加密流不解密不 MITM」。越线采集自有账号自有设备流量法律上通常可行，但**项目对外的「我们不解密」承诺一旦破例，需重写这条红线叙事**，这是治理级决定不是技术决定。**（订正：此条不牵连 AQS claim-scope 页脚——D-24 item③创建的是独立 claim_scope `application_flow_observation_no_decrypt`「不进 AQS」，与 AQS 评分页脚 `application_end_to_end_to_probe_node` 是两个子系统；前稿把二者嫁接是错的，已删。）**
3. **收益是 PO 的目标函数，不由本提案预判**（对抗核验问题5）：C 若成功，补上的是两字段的**自有账号单设备**明文 token 时序样本——**它是否值这份合规代价，取决于 PO 是否重视「流内 token 级真实分布」高于「UI-proxy 近似」**。若 PO 的目标恰是拿到这层真实数据（哪怕小样本），C 的收益就不是「样本小可忽略」而是「**唯一能到达该层的路径**」；若 UI-proxy 已够用，则 C 收益有限。这个权衡只有 PO 能做，本提案不替他判。
4. **代价方向**：技术不确定 + 合规叙事重写；收益侧留给 PO。

---

### 选项 D｜维持暂缓（零动作，但必须写触发条件）

**动作**：不改代码、不改 status，`PENDING-BY-CALIBER` 保留——**但 PO 写下重新提上台面的触发条件**
（照父容器 `DECISION_REQUEST_20260829.md` L14「暂缓写『暂缓+触发条件』」的既有要求）。

**可验证代价**：
1. **唯一零代码成本选项**——机器侧现状已诚实（门不被它挡），维持不产生技术债增量。
2. **代价是把治理债显式化而非清偿**：账仍没结，但从「无限期悬置」变「有条件悬置」。触发条件候选：
   「若外场线复活并解禁受控采集（裁项 C）」「若换设备/换 App 版本使 D-61 结论失效」「若 M3 交付需要该层数据」。
3. **风险**：若触发条件写得太松（如「以后再说」），等于没裁，六周悬置会变十二周——**D 只在触发条件可验证时才是合法选项**。

---

### v4 技术推荐（**非裁定，仅在「无额外 PO 目标输入」下成立**）

**默认推荐 A（正式放弃）**，理由链——但**推荐的前提假设是「UI-proxy 观察已够用、项目不追求流内 token 级真实分布」**：
- C 的**代价**（技术不确定 + 合规叙事重写）明确，其**收益**取决于 PO 对真实 token 分布的诉求——**若 PO 重视该诉求，权衡轴就变成「真实 token 分布 vs 越 D-24 合规代价」，此时不应默认 A**；
- B 救不了 `think_pause`，且要削一条核心红线、留下四 App 口径不齐；
- A 承认「这一层从 D-24 起就在红线外」的既成事实，UI-proxy 观察值继续留在 `observed_ui_layer` 不受影响，Profile 3 真实宣称范围不变；
- D 是 A 的「暂不定死」版——若 PO 尚未想清是否追求该层数据，D（带触发条件）比 A 更稳，代价是账继续挂。

**PO 裁定占位**：【PO-裁定占位：token_interval_ms_dist = A / B / C / D】【PO-裁定占位：think_pause_ms_dist = A / B / D】
（think_pause 无法走 B；两字段可分别裁。）

---

## 4. 另五字段的定案（无需进裁项 B，此处交代以满足全覆盖验收）

| 字段 | 定案 | 说明 |
|---|---|---|
| `tool_loop_cadence` | **已终态 `N/A-BY-CALIBER`（2026-07-31 PO 已裁，R19d 冻结）** | 四 App 皆消费型对话无工具编排，本方法学口径永不可得；无需 PO 再动，本提案仅确认 |
| `request_size_bytes_dist` | 保持 `PENDING`（红线内采集任务，**阻塞翻门**） | 需 ≥30 turns 多会话 per-direction 字节隔离；HTTP/2 复用是障碍 |
| `session_duration_s_dist` | 保持 `PENDING`（红线内采集任务，**阻塞翻门**） | 需 a11y 会话开始/结束埋点，代码未落地 |
| `downlink_media_bytes_dist` | 保持 `PENDING`（红线内采集任务，**阻塞翻门**） | 需真媒体场景 + 端点级字节隔离（禁文本下行冒充媒体，R15） |
| `pop_ip_list` | 保持 `PENDING`（红线内，最接近 CAPTURED，**阻塞翻门**） | 三 App 已有 direct 观测；翻 CAPTURED 只差「跨 ≥2 网络稳定 POP 集合 + 证据回链复核」 |

**⚠ 给 PO 的两条关键澄清**（对抗核验问题2）：
1. **这四个 plain-`PENDING` 才是画像翻门的真实阻塞**（`gate_state` 阻塞计数=4）。即便裁项 B 裁完，
   `source_portrait` 仍翻不了——Profile 3 离「完整画像」差的是这四格的采集，不是那两个 by-caliber 字段。
2. **这四格同样悬置了六周，且它们绑定外场/采集线**：任务板实况 P40 离线、new run=0、外场 BLOCKED。
   **若外场永不复活，这四个 plain-`PENDING` 会无限期挡住翻门——这正是 D-348 想避免的 plan-A 死锁，
   只是从 by-caliber 字段搬到了 plain-PENDING 字段上**。故它们迟早也需要一个「继续采 or 也放弃」的
   终态决定——归属 SPEC-1 裁项 A（主交付物排序）/裁项 C（外场线处置），**不应与裁项 B 混淆，
   但也不该被当成「反正迟早会采」而无限拖着**。本提案把这一点摆明，供 PO 在裁项 A/C 时一并考虑。

   > **⚠ 本条的前提已于 2026-08-30 成真（`D-587`〔1 层〕C 裁定）**：PO 原话「外场测试不做，换种方式，不要外场了」——
   > **外场线终止**，wave-1／点位／暂停令议题全撤。**故上文那个假设句「若外场永不复活」不再是假设。**
   > 直接后果：**这四格 plain-`PENDING`（`request_size` ／ `session_duration` ／ `downlink_media` ／ `pop_ip`）
   > 靠原外场采集路径已无来源**，`source_portrait` 在现有口径下**不会**再翻门。
   > 因此本条所说的「继续采 or 也放弃」终态决定**现在是必须做的一件事，不再是可推迟的提醒**——
   > 且选项集已随 C 裁定改变：不再有「等外场复活」这一支，只剩
   > ①**改用替代维度采**（大脑提案的「多 App×多网络形态」室内维度，候 PO 确认方向）／
   > ②**逐格定 `N/A-BY-CALIBER` 终态**（承认该口径永不可得，同 `tool_loop_cadence` 先例）／
   > ③**保持 `PENDING` 但显式登记「无采集路径」**（诚实但不解锁，须配自失效复验条件，否则又是静默悬置）。
   > **本提案不替 PO 选**；但**「等外场」这条路已被裁掉，继续把它当默认预期即是过期认知**。
   > （原文「裁项 C（外场暂停解除）」的措辞亦按终态订正为「外场线处置」——**解除与终止是相反的两件事**。）

---

## 5. 给 SPEC-1 裁项 B 的引用块（v2 可直接粘贴；**保留父容器的暂缓/后果框架**）

> **裁项 B｜M3 画像口径**（技术论证：`spec/portraits/PORTRAITS_TRISTATE_PROPOSAL_20260829.md`，SPEC-4/v4 供稿）
>
> **范围**：仅 `token_interval_ms_dist` + `think_pause_ms_dist` 两字段（其余五字段已定案，见供稿 §4）。
> **⚠ 前提认知**：裁本项**不解锁画像翻门**——翻门被另四个 plain-PENDING 字段挡着（供稿 §4）；本项结的是「越线决定悬六周」的治理债。
>
> | 选项 | 动作 | 代价方向 | 关键限制 |
> |---|---|---|---|
> | A 正式放弃 | status→终态；UI-proxy 值留 observed 层 | 最小（实质=退役一个 status 标签） | 无 |
> | B 改 UI-proxy 纳入 params | 重定义口径 + 放宽 R5 | 中高 | **救不了 think_pause**；四 App 口径不齐；削核心红线 |
> | C 解禁受控采集 | PO 授权越 D-24；root mitm | 技术不确定 + 合规叙事重写 | D-61 已证普通 CA 不可得需 root；**收益取决于 PO 是否重视真实 token 分布** |
> | D 维持暂缓 | 零动作，但写触发条件 | 零代码，账继续挂 | 触发条件须可验证，否则等于没裁 |
>
> **不裁的后果**（父容器 L63 既有要求，勿覆盖）：两字段无限期停留 `PENDING-BY-CALIBER`——门不被它挡，但画像状态永远「等一个没人提的决定」。
> **v4 技术推荐 A**（仅在「UI-proxy 已够用、不追求流内 token 真实分布」前提下；若追求，权衡轴转向 C，见供稿 §3 推荐段）。
> **PO 裁定**：【占位：token_interval = A/B/C/D】【占位：think_pause = A/B/D】

---

## 6. 落地清单（PO 裁后，本单或后续单执行）

- **选 A**：`check_redline.py` R19d `RULED_STATUS` 两字段改终态值 + 四 yaml 的 `params_capture_status` 同步；
  若复用 `N/A-BY-CALIBER` 则**无需动 schema**（`portrait.schema.json` 实测**不校验** `params_capture_status`，
  grep 零命中——status 枚举由 `check_redline.py` 的 `CAPTURE_STATUSES` 管，非 schema）；若新增 `ABANDONED-BY-PO`
  则改 `check_redline.py` 的 `CAPTURE_STATUSES` 枚举（不是 schema）+ `test_check_redline.py` 反例夹具（由 `RULED_STATUS` 派生，改值不误伤）。
- **选 B**：R5 放宽 + params 语义注释 + 下游 caliber 标签保护 + think_pause 仍需单独裁。
- **选 C**：新增受控采集授权文档（参照 `docs/AUTHORIZED_TOKEN_CAPTURE_SPEC_2026-07-18.md` 先例）+ root 可行性干跑。
- **选 D**：零代码，仅在 DECISION_LOG 记一条「暂缓 + 触发条件」。
- **A/B/C 共同**：改动过 portraits-redline 守卫层；入一个 D 号（口径定案）。

---

## 7. 修订记录（对抗核验后）

三镜头对抗核验（`wf_4c72bf8a-758`，facts/gaps/consumer 各一独立 agent）：facts=CLEAN（六项事实全准）、
consumer=CLEAN（v2 可直接引用），gaps 抓出并已订正——
①补选项 D（维持暂缓+触发条件）与 §5「不裁后果」行，勿覆盖父容器框架（问题1）；
②订正 §0/§1/§4「差两格就完整」假命题——裁 B 不解锁翻门，真实阻塞是四个 plain-PENDING（问题2）；
③§3 选项 B 第4条标注为「推测性风险、无已知消费方实例」（问题3）；
④§3 选项 C 第2条删除「D-24→AQS 页脚」虚假嫁接（D-24 item③是独立 claim_scope 不进 AQS）（问题4）；
⑤§3 推荐段把 C 的收益侧交还 PO，推荐显式标注前提假设（问题5）；
⑥元信息补「分析分支」限定（溯源）、§6 修正 `portrait.schema.json` 不校验 status 的执行错误（consumer 附注）。
