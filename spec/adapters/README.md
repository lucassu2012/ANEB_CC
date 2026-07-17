# spec/adapters/ —— Profile 3 真实 App 适配器规格（数据文件，权威）

> 铁律 1：**适配器规格 = 数据文件，不是代码分支**（spec/README.md 治理规则对本目录全量生效）。
> 计划依据：《SYSTEM_DEV_PLAN v1.0》§4.1（关键模块「(Profile 3) 真实 App 适配器宿主」）、
> §4.3（适配器按**易耗品**设计，App 改版即重写规格数据）、§8 风险表（打点走无障碍节点监听为主）。
> 首批 App = 豆包 + DeepSeek（D-48 拍板）。

## 格式决定：JSON（非 YAML）

与 `spec/profiles/client/client_profiles.json` 一致性优先：kotlinx.serialization 严格模式
（未知键即失败）原生支持 JSON、加载链与 TestModeProfileLoader 完全同模式；YAML 需引入
第三方解析依赖且无同等严格模式保证。spec/ 与 assets 镜像两份保持同格式（JSON）。

## 镜像关系（与 client_profiles 同模式）

- 权威副本：本目录 `*.json`（先改 spec、后动代码）；
- 运行时镜像：`app/probe/src/main/assets/spec_adapters/*.json`；
- 防漂移：`AdapterSpecTest` 守护两份文件**字节级一致** + 严格模式解析 + 关键字段钉死。

## 消费者

- `app/probe/src/main/java/com/aneb/probe/adapter/AdapterSpec.kt`：DTO + 严格解析 + assets 加载
  （fail-safe：任何异常 → 空列表 + 日志 KEY `ADAPTER_SPEC_FALLBACK`，宿主降级为通用观察，不崩）；
- `app/probe/src/main/java/com/aneb/probe/adapter/AnebAccessibilityService.kt`：观察模式宿主，
  按前台包名匹配规格；未匹配 → 通用观察（generic mode，机制验证路径）。

## 口径红线（双声明：本目录数据文件 caliber_redlines 字段 + 代码 KDoc）

1. **无障碍打点 = 端到端体验代理**（含 App 渲染，≈帧级精度上界 16–33ms），**≠网络口径**；
   与 Profile 2 服务端仿真口径**严格分标**，数值不可互比。
2. **观察模式不构成测量宣称**：规格 `status: PENDING-VALIDATION` 撤销前，其驱动的一切输出
   恒标 **LOW/INCONCLUSIVE**。
3. **R-10**：无事件 → first_delta / cadence 记 **null**，绝不折 0。
4. **观察模式 only**：宿主绝不 performAction / 注入任何操作（动真实账号是用户红线）。

## 发送锚定 TTFT（ttft_send_ms）口径——启发式声明

会话级 first_delta（观察启动→首事件）之外，宿主另测**发送锚定 TTFT**：

- **send_anchor = 输入框文本非空→空**（对话类 App 发送后输入框即清空）。判定仅用
  TYPE_VIEW_TEXT_CHANGED 事件自带 className 匹配规格 `input_node.class_name_regex`
  （generic mode / 规格缺该维度 → 兜底 `android\.widget\.EditText` 正则，数据缺失不瘫机制；
  绝不取 event.source，R-16）；只计文本**长度**不读内容（文本红线不变）。
- **锚定 TTFT = send_anchor → 其后首个非输入框内容变化事件**（TYPE_WINDOW_CONTENT_CHANGED
  或非输入框 TEXT_CHANGED）间隔。多次发送逐次重新武装（覆盖=取消上一个未闭合锚点）；
  历史保留最近 8 个完成值（环形）。
- **启发式声明（如实）**：send-anchor=input-clear 是启发式——观察口径**无法区分**
  "发送清空"与"用户手动清空"，锚定值可能包含手动清空误检。故其驱动的一切输出
  **恒标 LOW/INCONCLUSIVE**，不构成测量宣称。
- **R-10**：无发送锚点 / 锚点未闭合 → `ttft_send_ms` 记 **null**，绝不折 0。

## PENDING-VALIDATION 生命周期

- 当前测试机（P40）未安装豆包/DeepSeek，账号是用户资源——`package` 字段为 [COMMON] 公开渠道
  值待装机核实；`input_node`/`response_node` 匹配规则为 [GUESS] 占位。
- **PENDING-VALIDATION 期间节点规则仅作标注计数、不作打点闸门**（规则错误不得静默丢事件，
  事件时戳流全量记录）。
- 真机验证（主会话执行）后：核实 `package`、经 uiautomator dump 回填精确 `view_id_regex`、
  撤销对应 `status` 字段并升版本；语义变化走新 id 并列（additive-only）。
