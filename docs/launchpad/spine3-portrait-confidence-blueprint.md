<!-- 发射台准备蓝图(launchpad-prep)：2026-07-18 并行工作流产出。
     本文件为设计蓝图，产出时未改任何生产代码/未提交生产代码。
     用途：PO 决策落定 + P40 设备经协议解锁后，据此秒执行。口径红线见正文。 -->

# Spine-3 消费级 App 画像置信提升 — 锁无关实现蓝图
> ⛔ **本文中所有 `SHARED_TEST_STATUS.md` 状态机内容已于 2026-07-19 被 PO 废止,不再是设备使用的授权依据。**
> 保留在此仅作历史记录(它解释了当时为什么那样做),**照做会把外场战役卡死在一个永远不会到来的"复核降为空闲"上**。
> **现行流程**(见仓根 `CLAUDE.md`):开测前直接看**设备实况**——确认在线、华为桌面为前台应用,
> 并只读确认无冲突的 ANEB/业务 App/VPN/抓包进程与残留隧道;实况干净则 Claude 或 Codex **可直接开测**,
> 无需 claim / lease / handoff / 第二方释放。测后停掉本次测试起的一切、撤除临时网络规则与 `stayon`、
> 回到桌面并**立即复验干净**。E-01 与阿里云变更仍走各自的受保护预检、限定变更、回滚与变更后复验。

> 主轴:子项目 P3(spec 单一事实源)+ 采集协议。目标 = 设计"如何把 4 个消费级 App(豆包/DeepSeek/千问/Kimi)画像的置信度提升到**可翻 `source_portrait` 门控**"的锁无关准备。
> 铁律不变:①Profile 即数据不是代码分支;②引擎先行 UI 后行;③指标客户端单侧定义。口径红线:API 直调(`application_end_to_end_to_llm_api`)≠ 消费 App 画像;消费 App 的 token/think 层因 mitm 明文不可得(D-61)**恒 PENDING**,绝不跨层/跨产品/跨口径回填。
> **本文只是蓝图**:含示意代码片段,但不改任何生产文件、不提交。

---

## 0. 现状盘点(已核实)

| 事实 | 证据 |
|---|---|
| 4 画像 yaml 全部 `params:` 七字段 null、`source_portrait: PENDING-CAPTURE` | `E:\C Project\ANEB\spec\portraits\{doubao,deepseek,tongyi,kimi}.yaml` |
| 红线守卫 8 条不变量(R1–R8)现在 **PASS**(exit 0) | 本会话实跑 `python spec/portraits/check_redline.py` → `OK: all red-line invariants hold` |
| 守卫已接入本地门禁 | `E:\C Project\ANEB\scripts\verify_all.ps1` 第 63–86 行 `portraits-redline`(exit 0/1/2 → PASS/FAIL/NOT_EXECUTED) |
| 三层口径已采:UI 呈现层(3/4 App,Kimi 诚实缺席)、网络传输层(4/4 对话主连接) | `observed_ui_layer` / `observed_network_layer` 段;D-50~D-60 |
| 近似拟合段 `params_fit_approx` 存在但不翻门控(D-62) | 各 yaml + `PARAMS_FIT_METHODOLOGY.md` |
| 唯一已脱 PENDING 字段:tongyi/kimi 的 `pop_ip`(有真实 IP,caliber=direct,keep_pending=false) | tongyi.yaml L56-59 / kimi.yaml L63-66 |
| 本机工具链就绪:Python 3.14.2 + pyyaml 6.0.3 + jsonschema 4.26.0 | 本会话实测 → **红线测试脚手架可现在就跑,无需设备** |
| **P40 处异常锁定**,当前执行者 = Codex,不可真机测 | `E:\G Project\ANEB\SHARED_TEST_STATUS.md`(2026-07-18 21:21,code=`p40_aneb_accessibility_bound`) |

**结论**:UI 层 + 网络拓扑已采,但 `params:` 门控字段(分布)全空。要翻门控,缺的是"同层直采的**分布**证据"——而这几乎全部被设备阻;唯有**结构/语义守卫(check_redline 新不变量)与判据文档化**是现在可落地的锁无关工作。

---

## 1. 翻门控的判据(gate-flip criteria)

### 1.1 两个门,别混

| 门 | 判据字段 | 谁能翻 | 本主轴关注 |
|---|---|---|---|
| **App 画像门** | `params:`(7 字段分布)+ `source_portrait` | 消费 App 同层直采分布 | ✅ 本文主体 |
| API/Agent profile 门 | `aneb-token-observation-v1`(API 直调) | `ApiProbe` seam + Codex 校准流水线 | ❌ 另一 caliber(见 §6 边界说明) |

`params_fit_approx` 是**第三态**:观测锚点,`gates_params=false`,永不翻 App 画像门。它只是"诚实的近似",不是通往门控的台阶——通往门控的是 `params:` 里的**真分布**。

### 1.2 单字段脱 PENDING 的证据强度阶梯

一个 `params:` 字段从 `null` → 可写真分布,须同时满足(缺一即保持 null):

1. **同层直采源**(铁律 3):网络字节/IP 只能来自网络层;token 时序只能来自明文 token 层。
2. **caliber = direct**(事实型直采),非 ui-proxy、非 order-of-magnitude、非 none。
3. **样本量达分布阈值**:建议 `≥30 turns / ≥5 sessions`,且跨 `≥2 网络条件`(WiFi + 5G)。少于此一律 LOW,禁升到 order-of-magnitude 以上(方法学既定)。
4. **分布形态齐备**:至少 p50/p90/p99 + 样本数 + 采集环境,而非单一量级锚点。
5. **过跨层守卫**:`token_interval_ms_dist`/`think_pause_ms_dist` 若来源不是明文 token 层,一律拒。

### 1.3 每字段脱 PENDING 矩阵(核心判断)

| params 字段 | 能否脱 PENDING | 缺什么 | 阻断类型 |
|---|---|---|---|
| `pop_ip_list` | **最接近可翻**(tongyi/kimi 已在 fit 段脱;doubao/deepseek 只差 DNS 解析) | doubao 4 SNI、deepseek SNI+CDN 的 **DNS→真实 POP IP 解析**(TLS 下 IP 本就明文,无需解密) | 设备阻 |
| `request_size_bytes_dist` | **可翻**(字节在 TLS 下可见) | **per-direction 上行字节隔离** + 完整流式响应体 + 多样本;当前 doubao/deepseek 仅聚合 OoM、tongyi partial、kimi 加密聚合不可切 | 设备阻 |
| `downlink_media_bytes_dist` | **可翻**(需真媒体场景) | 真媒体(图/文件/音频)+ **端点级字节隔离**;doubao `frontier5-audio-ws-lq` 是最近可补采点;**禁文本冒充媒体**(D-62 越界原样) | 设备阻 |
| `session_duration_s_dist` | **可翻但需新埋点** | 会话级 instrumentation(会话开始/结束事件),非 per-turn、非 UI 事件计数换算 | 设备阻 + 需代码(a11y 增强) |
| `token_interval_ms_dist` | **恒 PENDING**(除非 root mitm 成功) | 明文 token 时间戳;免 root mitm 已证不可得(D-61);UI cadence 是 ui-proxy≠网络 ITL | 设备阻 + PO阻(见 §4) |
| `think_pause_ms_dist` | **恒 PENDING** | 流内思考停顿 vs 端到端 TTFT 的区分,需明文流式 token 时间戳 | 设备阻 + PO阻 |
| `tool_loop_cadence` | **恒 PENDING / 或声明恒不适用** | 4 者皆消费聊天 App,无工具编排;消费聊天口径可能**永久 N/A** | PO阻(定性裁定) |

**关键洞察**:`source_portrait` 是**单个字符串**,但可翻字段与恒 PENDING 字段**并存**——网络层分布(bytes/pop_ip/media/session)可翻,token/think/tool 恒不可。若沿用"单串 source_portrait 一翻全翻",要么被恒 PENDING 字段永久卡死,要么翻门时把 null 的 token 字段一起"洗白"成已采,**两者都错**。

### 1.4 门控粒度设计(PO阻,需拍板)

提出三选一,推荐方案 B:

- **方案 A(现状,单串)**:`source_portrait` 全 PENDING 或全翻。缺陷:被恒 PENDING 字段永久卡死。
- **方案 B(推荐,分层解锁 + 显式 N/A)**:
  - `source_portrait` 保持 PENDING-CAPTURE 直到**所有可翻字段**都采到分布;
  - 恒不可得字段从 `null`(=未采)改标 **`N/A-BY-CALIBER`**(=口径上不可得,非未采)——语义与 `null` 严格区分,`check_redline` 白名单该标记;
  - 新增 per-field `capture_status ∈ {PENDING, CAPTURED, N/A-BY-CALIBER}`,`source_portrait` 翻转判据 = 所有非 `N/A-BY-CALIBER` 字段均 `CAPTURED`。
- **方案 C(每层独立 source)**:`source_portrait_network` / `source_portrait_ui` / `source_portrait_token` 三串各自翻。更细但改动大、消费方需适配。

**方案 B 的机器守卫(CAPTURED 模式)**见 §2.3(R1/R2 mode-aware 改写)。启用 CAPTURED 模式 = PO 决策(见 blockers)。

---

## 2. check_redline 新不变量(**现在可验证**,锁无关核心交付)

现有 R1–R8 见 `E:\C Project\ANEB\spec\portraits\check_redline.py`。以下 R9–R17 为纯结构/语义守卫,**不需设备、不需 PO、现在即可落地并跑绿**;R18 是 CAPTURED 模式的未来态守卫(设计给出,启用 PO阻)。

### 2.1 前置重构(可测性)

`check_redline.py` 现在是一次性脚本,无法单测。重构为可导入纯函数(行为等价,IO 留在 `main`):

```python
# 提议改动:E:\C Project\ANEB\spec\portraits\check_redline.py
def check_portrait(app: str, d: dict) -> list[str]:
    """单画像 dict → 违规列表(纯函数,无 IO)。承载 R1–R14。"""
    ...
def check_cross_file(portraits: dict[str, dict]) -> list[str]:
    """{app: dict} → 跨文件违规列表。承载 R15–R17。"""
    ...
def main() -> int:  # 只留 glob/open/print/exit
    ...
```

### 2.2 新增不变量清单

| ID | 位置 | 判据 | 堵的漏洞 |
|---|---|---|---|
| **R9** | check_portrait | `schema_version` 匹配 `^\d+\.\d+\.\d+$` | 版本串手滑/缺失 |
| **R10** | check_portrait | `params_fit_approx.fields` 键集**恰为** 7 个 `PARAM_FIELDS`(无缺、无拼写漂移) | `pop_ip_lst` 之类拼写错悄悄逃过所有 per-field 检查(现在 `fields.items()` 只遍历存在的键) |
| **R11** | check_portrait | 每个 fit field 必含 `value`/`caliber`/`keep_pending` 三键 | `keep_pending` 缺失时 `fl.get()` 返回 None,R7 的 `kp is False` 恒 False → 静默放行(现存隐患) |
| **R12** | check_portrait | `caliber ∈ {direct,order-of-magnitude,ui-proxy}` ⇒ `value` **不以 "PENDING" 开头**(R6 的逆命题) | "标了口径却留 PENDING"的自相矛盾态 |
| **R13** | check_portrait | `keep_pending==false` **仅允许出现在 `pop_ip_list`** 字段 | 域事实:`params_fit_approx` 内只有 IP 能脱 PENDING;防未来把 bytes/token 违规脱 PENDING |
| **R14** | check_portrait | `keep_pending==false` 的 `pop_ip` 其 `value` 必须含 IPv4/IPv6 字面量 | 机器堵"SNI 主机名冒充解析 IP"(=deepseek 被对抗审计捉到的越界原样) |
| **R15** | check_cross_file | `downlink_media_bytes_dist.caliber` **恒 == none**(全 4 App) | 永久化"文本下行冒充媒体"红线(=doubao 被捉的越界原样) |
| **R16** | check_cross_file | `pop_ip_list.caliber` **恒 == direct**(全 4 App) | 基础设施事实字段口径固定,防漂移 |
| **R17** | check_cross_file | `keep_pending==false` 的 `pop_ip` 需在**同文件 `observed_network_layer`** 内出现 IP 字面量作证据回链 | traceability:"值"与"证据段"绑定,防脱 PENDING 而无网络层实据 |

示意实现(R14 为例):

```python
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6 = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,}[0-9a-fA-F]{0,4}\b")
def _has_ip(s: str) -> bool:
    return bool(IPV4.search(s) or IPV6.search(s))

# R14(在 check_portrait 内,pop_ip 且 keep_pending is False 时):
check(app, _has_ip(val), "R14",
      f"pop_ip keep_pending=false but value has no IP literal (SNI hostname != resolved POP IP): {val[:60]}")
```

### 2.3 R18 — CAPTURED 模式二态守卫(方案 B 的未来态,启用 PO阻)

现 R1/R2 硬要求"全 null + PENDING-CAPTURE",**任何合法翻门都会被它判 FAIL**。翻门前必须把 R1/R2 改成 mode-aware:

```
模式判定:source_portrait == "PENDING-CAPTURE" ? PENDING : CAPTURED
PENDING 模式:沿用 R1(全 null)+ R3(gates_params=false)。
CAPTURED 模式(方案 B):
  R18a  source_portrait 匹配可追溯采集标识正则,如 ^<app>-app-capture-\d{4}(Q[1-4]|-\d{2}-\d{2})$
  R18b  params_fit_approx.source_portrait_unlocked == true
  R18c  每个 params 字段非 null ⇒ 对应 capture_status == CAPTURED 且有 observed_* 证据回链
  R18d  恒 PENDING 字段(token_interval/think_pause[/tool_loop])必须标 "N/A-BY-CALIBER" 或仍 null,禁写分布
  R18e  禁"半翻":不得 source_portrait 已翻但存在 capture_status==PENDING 的非 N/A 字段
```

**禁止半翻**是核心:防止翻门时把没采到的字段一起洗白。R18 的启用(即允许 CAPTURED 模式)需 PO 拍板方案 B/C 与样本阈值。

### 2.4 verify_all.ps1 接线(现在可验证)

在既有 `portraits-redline`(整仓扫描)后并列一步 `portraits-redline-unit`(pytest 反例),两者互补:前者守当前仓状态,后者守守卫本身不退化。

```powershell
# 提议追加:E:\C Project\ANEB\scripts\verify_all.ps1(portraits-redline 之后)
if ($py -and (Test-Path (Join-Path $repo 'spec\portraits\test_check_redline.py'))) {
    $out = & $py -m pytest (Join-Path $repo 'spec\portraits\test_check_redline.py') -q 2>&1 | Out-String
    $code = $LASTEXITCODE
    if     ($code -eq 0) { Add-Result 'portraits-redline-unit' 'PASS' 'pytest test_check_redline.py' }
    elseif ($code -eq 5) { Add-Result 'portraits-redline-unit' 'NOT_EXECUTED' 'no tests collected' }
    else                 { Add-Result 'portraits-redline-unit' 'FAIL' 'reflex test(s) failed; see log' }
}
```

---

## 3. 测试脚手架(测什么 + 无设备下怎么 py/JVM 锚定)

### 3.1 py 反例脚手架 — `spec\portraits\test_check_redline.py`(现在可跑)

**测什么**:每条不变量一个"违规 fixture"(断言被捉)+ 一个"合规 fixture"(断言放行)。fixture 是内存 dict,不碰真 yaml、不碰设备。

```python
# 新建:E:\C Project\ANEB\spec\portraits\test_check_redline.py
import copy, pytest
from check_redline import check_portrait, check_cross_file  # 重构后可导入

def _valid_pending():
    return {  # 合规 PENDING 画像最小骨架
        "schema_version": "1.0.0",
        "source_portrait": "PENDING-CAPTURE",
        "params": {k: None for k in PARAM_FIELDS},
        "params_fit_approx": {"gates_params": False, "source_portrait_unlocked": False,
            "fields": {k: {"value": "PENDING(...)", "caliber": "none", "keep_pending": True}
                       for k in PARAM_FIELDS}},
    }

def test_R10_typo_field_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["pop_ip_lst"] = d["params_fit_approx"]["fields"].pop("pop_ip_list")
    assert any("R10" in v for v in check_portrait("x", d))

def test_R11_missing_keep_pending_caught():
    d = _valid_pending(); del d["params_fit_approx"]["fields"]["pop_ip_list"]["keep_pending"]
    assert any("R11" in v for v in check_portrait("x", d))

def test_R14_hostname_masquerade_caught():
    d = _valid_pending()
    d["params_fit_approx"]["fields"]["pop_ip_list"] = {
        "value": "chat.deepseek.com（仅 SNI 主机名）", "caliber": "direct", "keep_pending": False}
    assert any("R14" in v for v in check_portrait("x", d))  # 无 IP 字面量 → 捉

def test_valid_pending_passes():
    assert check_portrait("x", _valid_pending()) == []
```

**为何能现在跑**:pyyaml/pytest 皆本机就绪(已核实),fixture 纯内存,无真机、无 PO 依赖。这是本蓝图**最先应落地**的一项。

### 3.2 JVM 锚定 — `PortraitCaptureGoldenTest`(捕获轨已录则现可验证)

**问题**:`observed_ui_layer` 的 `ttft_cluster/density`、`cadence` 是 ObsStats(D-52/55/56)算出后**人工回填** yaml 的。若未来改 ObsStats,画像值会静默漂移而无守卫。

**测什么**:用已录的 `ADAPTER_EVT`/`ADAPTER_OBS` 真机事件轨(evidence 中或下次设备会话导出)作 fixture,喂纯 JVM 的 `ObsStats`,断言输出 == yaml 里的落值。

- fixture 格式:`(elapsedRealtimeNanos, eventType, textLen)` 序列 → 复现 D-52 豆包 1984ms / D-55 DeepSeek 500ms / D-56 千问 1203ms。
- 断言:`ObsStats.stats().ttftClusterMs ≈ 1984 ± 量化分辨率`、`cadenceP50 ≈ 100/66`、Kimi 轨 → null(方法边界守卫,D-56)。
- 落点:`E:\C Project\ANEB\app\probe\src\test\...\adapter\PortraitCaptureGoldenTest.kt`,与既有 `ObsStatsClusterTest`/`ObsStatsDensityTest` 并列。

**阻断细分**:若事件轨 fixture 已在 evidence/ADAPTER_EVT 日志中可重建 → **现在可验证**;若需下次会话专门 dump 干净轨 → fixture 获取**设备阻**,但测试骨架现在可写。

### 3.3 跨端契约符合性(现在可验证,已有先例)

沿用 D-63 已跑通的 jsonschema 校验思路:对 `params_fit_approx` 段设计一份**本仓自持** JSON Schema(`spec\portraits\portrait.schema.json`,描述三层段结构),用 jsonschema 4.26.0(已就绪)校验 4 yaml。与 check_redline(语义)互补:schema 管形状,redline 管红线语义。

---

## 4. root mitm 路径(拿消费 App 明文 token — 设备阻 + PO阻)

### 4.1 D-61 已证的现实

免 root 软件 mitm **确认不可得**:CA 装到**用户证书库**后,chat.deepseek.com HTTPS 443(38.5KB 含真实 token)**闭锁=未解密**、zztfly **错误**、全 App 仅 DNS 明文。根因 = Android 7+(API24+)默认不信任用户库 CA + 疑似 pinning。

### 4.2 拿明文 token 的必要条件(全部成立才可能)

1. **root** 设备(或可写系统分区/Magisk 模块) → CA 装**系统库**(绕过 API24+ 用户库不信任);
2. 目标 App **无证书 pinning**(需逐 App 排查);
3. App 无 native/双向 pinning、无 TLS 指纹反制。

### 4.3 各 App pinning 排查计划

**静态(可无设备,若有 APK)**:

| 手段 | 查什么 | 工具 | 阻断 |
|---|---|---|---|
| 解包 APK | `res/xml/network_security_config.xml` 的 `<pin-set>`/`<domain-config>` | apktool / jadx | 需 APK 文件(有则现可验证,否则设备阻取包) |
| 反编译扫码 | `okhttp3.CertificatePinner`、TrustKit、Conscrypt pin、内置 `.pem/.cer/.bks` 资产 | jadx grep | 同上 |
| native 排查 | `libssl`/自绘 pinning(`.so` 内硬编码指纹) | ghidra(重) | 难,常需动态 |

**动态(必须 root,真机)**:

| 手段 | 查什么 | 风险 |
|---|---|---|
| Frida hook 探测 | 运行时是否触发 pinning 校验路径(**只探测,不必绕过**) | 需 root;hook 第三方 App |
| 系统库 CA + 抓包 | 装系统 CA 后该 App 是否解密成功 | D-61 已示 deepseek 疑似 pinning → 大概率仍失败 |

### 4.4 风险与诚实建议

- **越红线**:root mitm 解密消费 App 流量,越过 D-24 明确的"**不解密 TLS、不注入证书、不 MITM**"边界。D-61 的免 root 尝试拿了**一次性**授权;root + 系统 CA + 可能绕 pinning 是**更大一步**,须 PO **显式再授权**且限"自有账号/自有设备/仅观测自身"。
- **大概率仍 PENDING**:即便 root,主流 App 普遍 pinning(D-61 deepseek 已现),单 App 成功也是 n=1 单设备 LOW。
- **建议**:token_interval/think_pause **默认保持恒 PENDING**(方案 B 标 `N/A-BY-CALIBER`)。root mitm 列为"若 PO 坚持且某 App 静态排查确认无 pinning,才对该单 App 小范围尝试"的**可选支线**,不作画像门控的主路径。真实 token 时序的正路 = **API 直调**口径(§6),它翻的是 API/Agent 门,不是 App 画像门。

---

## 5. 多点复采 / 多样本采集协议(设备阻,解锁后执行)

每项 = 采什么 + 工具 + 确切协议 + 脱 PENDING 后的 caliber。全部走 PCAPdroid(免 root,只读 SNI/IP/字节,不解密)+ a11y 观察,**无需 mitm**。

| # | 缺口 | 采集协议(确切) | 解锁字段 | 采后 caliber |
|---|---|---|---|---|
| C1 | doubao/deepseek 无解析 POP IP | PCAPdroid **开 DNS 日志**,抓包窗口内对该 App 发 ≥5 消息;导出 pcap;解析 `wss100/api5/frontier5/log.doubao.com`、`chat/hif-dliq.deepseek.com` 的 A/AAAA 应答 → SNI↔IP 映射;跨 WiFi+5G 各一次以捕获 POP 轮换 | `pop_ip_list`(→ keep_pending=false) | direct |
| C2 | request_size 仅聚合 OoM | PCAPdroid 逐流**方向字节**(它记 up/down),隔离上行字节;发**已知大小**消息序列(短/中/长)分别抓,拟合上行分布;需捕获完整流式响应体(等回复结束再停) | `request_size_bytes_dist` | direct(隔离后) |
| C3 | 无真媒体字节 | 真媒体场景:doubao 走 `frontier5-audio-ws-lq`(语音)或发图;**端点级字节隔离**,只计媒体端点下行;**禁把文本下行计入** | `downlink_media_bytes_dist` | direct |
| C4 | Kimi TCP7003 字节量级未确认 | 专项抓包(D-59 时被 UI 遮挡):发已知消息,量 7003 长连 up/down 字节;区分对话字节 vs jpush 控制字节 | `request_size`(kimi 部分) | order-of-magnitude→direct |
| C5 | doubao 长回复 TTFT 缺 | 英文长 prompt(`adb input text` 不支持中文,D-60);先处理媒体权限弹框(选禁止=最小权限,D-60 卡点);a11y v3/v4 采 cluster/density | `observed_ui_layer`(doubao 长回复) | ui-proxy(不入 params) |
| C6 | 无会话时长 | **需代码增强**:a11y 增会话开始/结束事件埋点(非 per-turn 换算);多会话采样 | `session_duration_s_dist` | direct(需新埋点) |
| C7 | 分布样本不足 | 每可翻字段 `≥30 turns / ≥5 sessions × ≥2 网络`;不足则一律 LOW、保持 fit 段不翻门 | 全可翻字段的样本量前置 | — |

**每次采集必守**:PCAPdroid 只读不解密;采后 force-stop PCAPdroid + 复核 VPN 已清(`rmnet_tun DOWN`);消耗 App 免费额度最小化;英文 prompt。

---

## 6. 口径边界(防跨界回填,红线)

- **API 直调 token 观测(`ApiProbe` seam)** = `application_end_to_end_to_llm_api` 口径,产出喂 Codex 校准流水线,**翻的是 API/Agent profile 门,绝不回填 App 画像 token/think 字段**。代码已建并验证:`E:\C Project\ANEB\app\probe\src\main\java\com\aneb\probe\apiprobe\TokenObservationExport.kt`(18 单测,契约 2/2)。
- **Kimi Code API 标定** = Profile 2 服务端仿真输入,`spec\calibration\kimi-code-api-k2.7.yaml`;**Kimi Code API k2.7 ≠ Kimi App**,跨产品跨口径禁借(kimi.yaml 已守此)。
- 三条来源(App 画像 / API 直调 / Profile 2 标定)**各自 caliber,互不回填**。这是 check_redline R5(跨层守卫)+ 方法学铁律 3 的机器 + 纪律双重保障。**Spine-3 的置信提升绝不靠借 API 口径充数**。

---

## 7. 解锁后 runbook(设备状态机)

### 7.1 前置:异常锁定必须先清

当前 `SHARED_TEST_STATUS.md` = **异常锁定**,执行者 = Codex,因 = E-01 0.8 部署致共享防火墙指纹漂移(exit=97)+ Verifier 两轮只读复核失败(`p40_aneb_accessibility_bound`)。

- **Claude 不是当前执行者,无任何合法状态转换**(不能 claim、不能 handoff、不能复核)。
- **绝不手改 `SHARED_TEST_STATUS.md`**(CLAUDE.md 铁律 + D-63 安全裁定:异常锁定态下手改会破坏 fail-closed 解析或打断 Codex 恢复复核)。
- 等 Codex 侧根因清理 + 独立复核把状态转回 **空闲** 后,方可进入 §7.2。

### 7.2 claim → 采集 → handoff(状态空闲后)

```
1. 读 SHARED_TEST_STATUS.md,确认『空闲』。
2. claim:走脚本 update_shared_test_status.py(D-63,非手改),
   空闲→进行中,填执行者=Claude / 任务=Spine-3 网络层分布采集 / 资源=P40+PCAPdroid / 开始时间。
   钉定 --expected-status-sha256(fail-closed:期间被改则中止)。
3. 焦点闸门(独立成命令,D-53 教训):检查 mCurrentFocus,确认 Codex 不在前台测试。
4. a11y 服务:摘除→加回 settings 重绑(D-50 gotcha:force-stop 会杀服务不自动重绑);
   测试期 dumpsys deviceidle whitelist +com.aneb.probe(D-52,测后成对撤除)。
5. 采集:按 §5 C1–C7 协议逐项 PCAPdroid 抓包 / a11y 观察;英文 prompt;额度最小化。
6. 清理:force-stop PCAPdroid;复核 VPN 已清(rmnet_tun DOWN);
   恢复 a11y setting 再 force-stop 我方包(顺序不可反,D-50)。
7. handoff:进行中→待交接,交接说明写清『已停什么/已清什么/待复核什么』。
8. 释放:由另一固定角色 / 受限 Verifier 独立复核(T+0/T+10 只读),
   全过→待交接→空闲;任一失败→异常锁定。Claude 不能自我复核放行。
9. 回填:采到的分布经 §1 判据 + §2 R18 守卫写入 params;
   若达翻门条件,source_portrait→可追溯标识 + 升 schema_version;
   跑 check_redline + test_check_redline + verify_all 全绿方算落地。
```

---

## 8. 改动清单总表(file:函数,分状态)

| # | 文件:位置 | 改动 | 状态 |
|---|---|---|---|
| 1 | `spec\portraits\check_redline.py`:重构 `check_portrait`/`check_cross_file`/`main` | 拆纯函数,行为等价 | **现可验证** |
| 2 | `spec\portraits\check_redline.py`:`check_portrait` | 加 R9–R14(semver / 键集 / 必填子键 / 口径-PENDING 逆命题 / 只 pop_ip 可脱 / IP 字面量守卫) | **现可验证** |
| 3 | `spec\portraits\check_redline.py`:`check_cross_file` | 加 R15–R17(media 恒 none / pop_ip 恒 direct / IP 证据回链) | **现可验证** |
| 4 | `spec\portraits\test_check_redline.py`(新建) | 每不变量红/绿反例(§3.1) | **现可验证** |
| 5 | `scripts\verify_all.ps1`:portraits 段 | 加 `portraits-redline-unit`(pytest)三态步骤 | **现可验证** |
| 6 | `spec\portraits\portrait.schema.json`(新建)+ 校验接线 | JSON Schema 管三层段形状,jsonschema 校验 | **现可验证** |
| 7 | `spec\portraits\PARAMS_FIT_METHODOLOGY.md` | 加 §1 判据阶梯 + 每字段矩阵 + R18 CAPTURED 模式设计 | **现可验证** |
| 8 | `spec\portraits\*.yaml`:`params_fit_approx.fields.*` | additive 补 `source_layer`/`confidence`/`note` 三子键(不翻门,R1–R8 仍绿)+ 对应 presence 不变量 | **现可验证** |
| 9 | `app\probe\src\test\...\adapter\PortraitCaptureGoldenTest.kt`(新建) | 已录事件轨→ObsStats→锚定 observed_ui_layer 落值 | 现可验证(骨架)/ fixture 获取**设备阻** |
| 10 | `spec\portraits\check_redline.py`:R1/R2 → mode-aware + R18a–e | 启用 CAPTURED 模式二态守卫 | **PO阻**(需拍板方案 B/C + 阈值) |
| 11 | `spec\portraits\*.yaml`:`params:` + `source_portrait` | 回填真分布 + 翻门 | **设备阻**(采集)+ PO阻(阈值) |
| 12 | a11y 会话边界埋点(`AnebAccessibilityService`/`ObsStats`) | session_duration 采集所需新事件 | **设备阻** + 需代码 |
| 13 | root mitm 支线(pinning 静态排查) | 逐 App 解包扫 pinning | 设备阻(取包)/ **PO阻**(越 D-24 红线,需再授权) |

---

## 9. 优先级建议

1. **立即(今天,锁无关)**:# 1→4→5(重构 + R9–R17 + 反例测试 + verify_all 接线)。这是把"诚实红线"从 8 条硬化到 17 条、且守卫本身有测试的最高杠杆动作,全程无设备无 PO。
2. **紧随(锁无关文档/结构)**:# 7(判据文档化)、# 8(fit 段元数据补全)、# 6(schema)、# 9 骨架。
3. **PO 决策就绪后**:# 10(CAPTURED 模式)——先定方案 B/C + 样本阈值。
4. **设备解锁后**:§7 runbook → §5 采集协议 → # 11/# 12 回填翻门。
5. **仅当 PO 显式再授权且静态排查确认无 pinning**:# 13 root mitm 单 App 支线(默认不做,token/think 保持 `N/A-BY-CALIBER`)。
