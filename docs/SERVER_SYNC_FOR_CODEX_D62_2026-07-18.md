# Server calibration sync for Codex (D-62: mitm conclusion + Profile-3 fit)

> Deploy authority = Codex (D-35). Syncs mitm-confirmed-inaccessible + 4-app 3-layer fit results for Profile 2 server simulation. Strict caliber layering; no cross-layer/cross-product fill.

## 1.
mitm 明文 token 时序确认不可得(D-61):免 root 抓包对全部 4 个消费 App 均无法采到明文 token 间隔/思考停顿。Profile 2 服务端仿真禁止将 token_interval_ms_dist/think_pause_ms_dist 当作已知真实分布;这两类字段对消费 App 恒 PENDING,只有 UI-proxy 弱锚(doubao~100ms、tongyi~66ms cadence)且显式≠网络ITL。

## 2.
各 App 网络字节量级(order-of-magnitude,非分布,均含上下行聚合未拆纯上行):doubao ~10–18KB/turn(上下行合计);deepseek ~13.8KB/轮(mitm 活跃峰 38.5KB);tongyi ~0.3–1.8KB 采样(未含完整流式响应体,量级偏小,captured=partial);kimi 不可切分(加密非标长连聚合 TCP,无 per-request 语义)。仿真作字节基线时须标'聚合非上行、非分布'。

## 3.
Kimi Code API 口径(k2.7 编程产品,API 明文 token 口径)独立标定,禁止映射到 Kimi App 消费画像:ITL 259ms(区间 253–337,n=5)、首字/强制思考 ttft ~3063ms(思考主导)。此为跨产品+跨口径双重越界样本;仅可用于校准独立的'编程 Agent/API' profile,不得注入 Kimi App(消费聊天)的 token/think 字段。

## 4.
四种传输架构对仿真的含义:(a) doubao=WSS 多端点(wss100 对话 WS 文本流 + frontier5 audio-ws-lq 音频端点[存在但未字节隔离,本次媒体实测=0] + api5 + log),文本走 WS,媒体端点存在但未测,不得用文本下行冒充媒体;(b) deepseek=HTTPS 文本流式(chat/hif-dliq)+ 第三方 CDN(zztfly cdn-api-auth/cfgc)+ 火山遥测(apmplus/gator.volces.com);(c) tongyi=HTTPS/TLS 443 到阿里·UC夸克(upaas.quark.cn),真实入云 PoP IP 已解析可归因(110.253.191.12/114.250.44.6),是唯一 IP 级完整字段;(d) kimi=非标 TCP 长连端口 7003(自有 IM)+ jpush,加密聚合字节不可按 HTTP 请求/响应语义切分——仿真不得假设其为标准 HTTP 请求-响应模型。

## 5.
pop_ip_list 门控口径统一:IP 端点属基础设施事实(非行为分布 param),不受 source_portrait=PENDING-CAPTURE 行为门控约束,可独立落值。但字段规范内容=解析后 POP IP;仅采到 SNI 主机名(doubao/deepseek)须 keep_pending=true 待 DNS 解析,不得当解析 POP IP 用于归因/对外宣称。tongyi/kimi 已有真实 IP 可 keep_pending=false。

