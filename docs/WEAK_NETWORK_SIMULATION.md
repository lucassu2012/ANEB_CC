# ANEB 弱网模拟方法（P40 Pro 真机）

> 问题:真机测试都在好网络下,如何模拟弱网(人为调 RSRP/SINR/速率/时延)?
> 结论先行:**RSRP/SINR 软件不可伪造**(基带物理层测量,未 root 真机无接口);**速率/时延/丢包**可经四法制造,其中「背景伴流」已在 ANEB 内全自动落地。

## 0. 为什么 RSRP/SINR 不能软件模拟

RSRP(参考信号接收功率)、SINR(信干噪比)是**基带芯片对空口物理层的实测量**,经 `TelephonyManager`/`CellSignalStrength` **只读**上报。未 root 的真机没有任何软件接口去"写"这些值——能改的只有真实射频环境:

- **物理衰减**:手机装金属盒/多层锡纸、进电梯/地库/密闭金属空间、走到小区边缘或高负载小区。RSRP/SINR 真降,速率/时延随之真实劣化。
- **换制式**:工程菜单(华为 `*#*#2846579#*#*`)或设置里锁 3G/4G——SINR 语义随制式变,速率分层。
- 配 ANEB 的 **drive_test 模式**(设置里开)全程 1Hz 采 RSRP/SINR/RAT + GPS 打点,把物理弱网量化落库。

> 模拟器可任意设 RSRP/SINR,但无真实测量价值(项目裁定:模拟器只产功能证据)。

## 1. 四种弱网制造法对照

| 方法 | 可动指标 | 真实性 | 自动化 | 落地状态 |
|---|---|---|---|---|
| ①物理射频衰减 | **RSRP/SINR** + 速率/时延/丢包 | 最高 | 人工(drive_test 标注) | 手动可用 |
| ②强制制式降级(锁 4G/3G) | 制式→SINR 语义 + 速率/时延 | 高 | 半自动 | 手动可用 |
| ③**背景伴流(自拥塞)** | 速率/时延/抖动/卡顿 | 高(真实拥塞) | **全自动** | ✅ **已内置(本文 §2)** |
| ④整形 Wi-Fi 网关 | 速率/时延/丢包(参数化扫档) | 中(受控) | 半自动 | 需搭一次热点(本文 §3) |

## 2. ③背景伴流 —— ANEB 已内置(DEBUG,adb 一行触发)

**原理**:run 全程并行 N 条背景 `/download` 无限速大流,挤占**接入链路**(蜂窝/Wi-Fi 上行/下行队列),产生真实 **bufferbloat**——排队时延暴涨、抖动飙升、吞吐被饿死、卡顿浮现。这是真实拥塞,不是数字仿真。

**触发**(仅 DEBUG 构建;标注非取证证据):

```
adb -s <serial> shell am start -n com.aneb.probe/.ui.MainActivity \
  --es server https://120-79-148-0.sslip.io:8443 \
  --ez autorun true \
  --es weaknet contend:4
```

- `contend:N`,N∈[1,8]:并行背景流条数,越多越拥塞。
- 日志出 `WEAKNET_CONTEND streams=N note=non_forensic_debug_contention`;设置页调试横幅显示 `weaknet=contend:N`。
- run 结束背景流随 collectors 统一取消(不残留)。

**真机实证(P40, contend:4, run 019f6e3d)——对比健康基线**:

| 指标 | 健康基线 | contend:4 | 变化 |
|---|---|---|---|
| RTT (N1) | ~24–34 ms | 60–66 ms | ↑2–3× |
| 抖动 (N2) | ~1–5 ms | 28–61 ms | **↑10×+**(bufferbloat 典型) |
| 上行 U1(s1 小上传) | ~5–25 Mbps | **0.16 Mbps** | 被挤占饿死 |
| 卡顿/恢复 | ~0 | t5=790ms、t3_incl=0.062 | 卡顿浮现 |

> 口径:该 run 标 `VALID_LOW_CONFIDENCE`、**非取证证据**(与 inject 同级);用于观察 KPI 在拥塞下的响应与 UI 动态,不作正式测量结论。局限:只压接入队列共有路径,不区分上下行、不动 RSRP/SINR。

## 3. ④整形 Wi-Fi 网关(需搭一次,可参数化精确扫档)

让 P40 连一台你控制的 Wi-Fi 热点,在热点侧注入固定 lag/loss/throttle——可**精确扫档**(+100ms/1% 丢包/2Mbps 限速任调),做受控对照实验。

- **PC 热点 + clumsy(Windows)**:开移动热点,clumsy 按进程/端口注入 Lag/Drop/Throttle/Duplicate。
- **Linux 路由 + tc netem**:`tc qdisc add dev <wlan> root netem delay 100ms 20ms loss 1% rate 2mbit`——教科书级弱网整形。
- 注意:此为 Wi-Fi 路径,claim_scope 是"经该受控网关到 E-01",与蜂窝真机口径分开记。

## 4. 建议用法组合

- **快速看 KPI/UI 在弱网下的动态与打分响应** → ③背景伴流(一行命令,今天就能跑)。
- **要精确复现某档时延/丢包做对照** → ④整形网关。
- **要真实 RSRP/SINR 弱覆盖的取证数据** → ①物理衰减 + drive_test 标注(唯一能动物理层的路径)。
- 三者 claim_scope 分开记;②③④均非物理层弱覆盖,勿表述为"低 RSRP 场景"。
