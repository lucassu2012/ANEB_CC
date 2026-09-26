# 设备三层前提门 · 只读诊断（2026-09-26，执行窗 61bd2401）

- **派单**：大脑 2026-09-26「② 设备三层前提门·只读诊断」。输入：PO 称 P40 已连热点；大脑实测 P40→223.5.5.5 为 0/3；D-871（共享源选成死卡，判决性对照＝指定源 ping）、D-906（派生读数同源不互证，只有收到回复的往返算门）、D-907（热点虚拟卡 ifIndex 会漂）。
- **性质**：只读。本次**没有**启动、停止任何 App 或服务，**没有**改任何设置（PC 与手机两侧都没改），没有点亮或解锁手机屏幕。
- **结论三态只用在「门」这几格**（通／不通／未执行）；其余格是读数，标「—（读数，非门）」。

## 0. 结论

**三层门＝不通。** 手机 ping 223.5.5.5 在两个时刻都没收到回复（#20 回复 0/3；#38 回复 0/3）。

**断在哪一段，现有读数判别不了，两个假说并列：**

- **H1 屏灭致第一跳下行不到手机**：回复到了 PC、PC 发给了手机，但没进手机网络栈；
- **H2 共享源选错（D-871 形态）**：手机的包经 PC 转发出以太网时没被 NAT，回复根本回不来。

> **订正（2026-09-26，大脑核收时指出，执行窗采纳并扩大）**：本文件初版（`261703fe`，其提交标题同样如此）写「故障落在第一跳的下行方向，不在 PC 的上游」「与 D-871 不是同一个故障」，**两句都不成立**。①「热点地址作源能出能回」读的是 **PC 自己发包时的路由表**，手机的包走的是 ICS 转发加共享源那张卡上的 NAT，不是同一条路径（派生读数 vs 往返的又一例）；WLAN 此刻是 Disconnected 加 169.254，若共享源恰是它，症状与今天同形。②执行窗顺着这条再列一遍世界，发现初版当「强读数」用的「手机 ping 上游期间收包增量 0」**在 H1 与 H2 下读数相同**（H2 下根本没有回复可收），**不是判别器**；PC→手机反向 ping 0/3 也归不到下行——屏灭的手机回不回 echo 本身未知。下表与下方世界表是订正后的版本。

分层：

| 层 | 读数 | 三态 | 依据 |
|---|---|---|---|
| PC 上游（以太网） | 以太网作源 ping 223.5.5.5 | 通 | #10、#31 |
| PC 上游（WLAN） | WLAN 状态 Disconnected、地址 169.254（无租约），作源发送即 General failure | 不通 | #22、#32 |
| 热点地址作源（PC 本机发出，读的是 PC 自己的路由表，**不是**手机经 ICS 转发的路径） | 以热点虚拟卡地址 192.168.137.1 作源 ping 223.5.5.5 | 通（不据此排除 H2） | #9、#29 |
| ICS 共享源（直读） | 三次非提权读取都失败（两种读法） | 未执行 | #4、#24、#25 |
| 第一跳上行（手机 → PC） | 手机 wlan0 发包增量与 PC 热点卡收包增量相等 | —（弱读数，非门） | #37、#38 |
| 手机收包（ping 上游 3 包期间） | 手机 wlan0 收包增量 0 | —（读数；H1、H2 下同值，**不是判别器**） | #38 |
| PC → 手机反向 ping（往返） | 回复 0/3 | 不通（但屏灭手机回不回 echo 未知，归不到下行） | #34 |
| 第一跳下行（单独判定） | 没有只在 H1 下失败、在 H2 下成功的往返 | 未执行 | 见下方世界表 |
| 手机 → 网关 | 不回 | 不通（**不作判据**：D-906，PC 可以合法地不回 echo） | #19 |

**世界表**（每个读数在各世界下的预期；任两世界预期相同的读数不是判别器）。H2 按手机屏灭时回不回 echo 再分两支：

| 读数 | H1 屏灭下行不到 | H2a 共享源错＋手机回 echo | H2b 共享源错＋手机不回 echo | 实测 | 能否判别 |
|---|---|---|---|---|---|
| 手机 ping 223.5.5.5 | 0/3 | 0/3 | 0/3 | 0/3 与 0/3 | 否 |
| ping 上游期间手机收包增量 | ≈0 | ≈0 | ≈0 | 0 | 否 |
| PC→手机反向 ping | 0/3 | 3/3 | 0/3 | 0/3 | 只排除 H2a |
| ping 上游期间 PC 热点卡发包增量 | ≈3（回复被转给手机） | ≈背景 | ≈背景 | 3（同法在 ping 网关窗口读得 1） | **弱**：唯一分得开 H1 与 H2b 的一格，但 psutil 计数含非单播、只一个窗口、背景未单独测 |
| 亮屏后复跑 run5 | 通 | 仍不通 | 仍不通 | 未执行 | **能**，即给 PO 的第 1 条 |

H1 与 H2b 目前只靠一格弱读数区分，**不据此下结论**。另有 **H3 关联本身坏了（与屏幕无关）**：它在前四行的预期与 H1 相同，亮屏后仍不通。所以第 1 节的动作顺序是：第 1 条（亮屏）把 H1 与 {H2, H3} 分开，第 2 条（看共享源）再把 H2 与 H3 分开，一次只动一个量。

**派生读数全绿，与往返结果矛盾**，这正是 D-906 的形态：手机 `ip route get` 出口 wlan0、经网关 192.168.137.1（#18）；默认网络 WIFI 且 VALIDATED（#21）；PC 侧对手机的邻居项 Permanent（#35）；PC 热点在 17 个连接配置文件上报的客户端数都是 1（#5）；手机无线信号见第 4 节 run4 说明。**这几格一律不当门用。** VALIDATED 是某个过去时刻的探测结果，不是现在的往返。

**一个混杂量没有排除：全程手机屏灭锁屏**（mWakefulness=Asleep、锁屏显示中，#16、#36、#39）。它是 H1 的来源；本诊断在屏灭态下**区分不了 H1/H2/H3，不猜**。即便是 H1，「下行不到」的确切含义也只到这一层：包**没进手机网络栈**（手机 wlan0 收包计数不动）；是空口就没送到，还是到了被手机网卡固件过滤掉，计数分不开。大脑那次 0/3 当时的屏幕态不知道。

**与 D-871 是不是同一个故障：未排除。** D-871 是共享源选到了死卡：手机能连上、能拿到地址，但转发出去的包回不来。今天 WLAN 是 Disconnected 加 169.254；若共享源恰是它，今天的全部读数都与 D-871 同形（见世界表 H2）。共享源直读是「未执行」。

⚠ 下面这条是推断，不是直读，**不据此排除 H2**：以热点地址为源的回复 TTL 比以太网直发的回复**少 1**（逐条原样见表），像是多经过了一次本机转发，由此可以推测以太网出口上有 NAT。但这是 PC 本机发包的路径，手机的包是否在同一处被 NAT，这条读数答不了。

## 1. 给 PO 的动作（每条一行，按顺序；本窗不代做）

一次只动一个量；每步之后我原样复跑 run5（约 15 秒、只读）。大脑已确认此顺序，PO 动手后由大脑点执行窗复跑。

1. **点亮 P40 屏幕（不必解锁）**。复跑通 ⇒ H1；仍不通 ⇒ 第 2 条。
2. （仅当第 1 条后仍不通）**在 PC「设置 → 网络和 Internet → 移动热点 →『共享我的以下 Internet 连接』」看选的是哪张卡**；若是 WLAN，改成「以太网」（改设置由 PO 做）。改后复跑通 ⇒ H2；选的本来就是以太网、或改后仍不通 ⇒ 第 3 条。
3. （仅当第 2 条后仍不通）**在 P40 上关开一次 WLAN、重连 PC 热点**（改设备状态，由 PO 做），然后复跑。

## 2. 读数表（39 行，由三份 JSON 生成，不是手抄）

列说明：**时刻**＝该条命令发出的本机时间；**命令原样**＝实际传给 CreateProcess 的参数（PowerShell 的 `-Command` 串原样收录，其中的竖线在表内转义）；**rc**＝该进程的原生退出码，一律取自 python `subprocess` 的 `returncode`，**不是** bash `$?`（D-891）。「通」只按**收到来自目标、带 TTL 的回复行**计（Windows ping 对「无法访问目标主机」也可能回 0，故不看退出码判通）。

| # | 跑次 | 层 | 读数项 | 时刻 | 命令原样 | 取读数通道 | rc | 读数 | 三态 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | run2 | PC | 网卡清单 | 2026-09-26T12:18:50 | `powershell -NoProfile -NonInteractive -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; & { Get-NetAdapter \| Select-Object Name,InterfaceIndex,Status,InterfaceDescription,InterfaceGuid } \| ConvertTo-Json -Depth 4 -Compress"` | PowerShell 5.1 → ConvertTo-Json → python 解析；rc＝powershell.exe 的 python returncode | None（未跑或超时） | 超时（timeout 90s），本跑无网卡状态；run3 补读 | —（读数，非门） |
| 2 | run2 | PC | IPv4 地址 | 2026-09-26T12:20:22 | `powershell -NoProfile -NonInteractive -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; & { Get-NetIPAddress -AddressFamily IPv4 \| Select-Object InterfaceIndex,InterfaceAlias,IPAddress,PrefixLength } \| ConvertTo-Json -Depth 4 -Compress"` | PowerShell 5.1 → ConvertTo-Json → python 解析；rc＝powershell.exe 的 python returncode | 0 | vEthernet (WSL (Hyper-V firewall))(if45)=192.168.144.1；vEthernet (Default Switch)(if24)=172.18.128.1；本地连接* 10(if13)=192.168.137.1；本地连接* 1(if11)=169.254.23.9；以太网(if9)=10.10.8.9；WLAN(if4)=169.254.219.25；Loopback Pseudo-Interface 1(if1)=127.0.0.1 | —（读数，非门） |
| 3 | run2 | PC | 默认路由（含接口跃点） | 2026-09-26T12:21:09 | `powershell -NoProfile -NonInteractive -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; & { Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' \| Select-Object ifIndex,InterfaceAlias,NextHop,RouteMetric } \| ConvertTo-Json -Depth 4 -Compress" ； powershell -NoProfile -NonInteractive -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; & { Get-NetIPInterface -AddressFamily IPv4 \| Select-Object ifIndex,InterfaceAlias,InterfaceMetric,ConnectionState } \| ConvertTo-Json -Depth 4 -Compress"` | PowerShell 5.1 → ConvertTo-Json → python 解析；rc＝powershell.exe 的 python returncode | 0 | 以太网(if9) via 10.10.8.1 接口跃点 25；WLAN(if4) via 10.10.0.1 接口跃点 55 | —（读数，非门） |
| 4 | run2 | PC | ICS 共享配置（HNetCfg） | 2026-09-26T12:21:46 | `powershell -NoProfile -NonInteractive -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; & { $m=New-Object -ComObject HNetCfg.HNetShare; foreach($c in $m.EnumEveryConnection){ $p=$m.NetConnectionProps.Invoke($c); $s=$m.INetSharingConfigurationForINetConnection.Invoke($c); [pscustomobject]@{Name=$p.Name;Guid=$p.Guid;SharingEnabled=$s.SharingEnabled;SharingType=$s.SharingConnectionType} } } \| ConvertTo-Json -Depth 4 -Compress"` | PowerShell 5.1 → ConvertTo-Json → python 解析；rc＝powershell.exe 的 python returncode | 0 | rows=[]；public=[]；private=[]；err 空 | 未执行（量法失败） |
| 5 | run2 | PC | 移动热点状态（WinRT，按连接逐个问） | 2026-09-26T12:21:52 | `powershell -NoProfile -NonInteractive -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; & { $null=[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]; $null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]; foreach($pr in [Windows.Networking.Connectivity.NetworkInformation]::GetConnectionProfiles()){ $aid=$null; try{$aid=$pr.NetworkAdapter.NetworkAdapterId.ToString()}catch{}; if(-not $aid){continue}; $st=$null;$cc=$null;$e=$null; try{$tm=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($pr); $st=$tm.TetheringOperationalState.ToString(); $cc=$tm.ClientCount}catch{$e=$_.Exception.GetType().Name}; [pscustomobject]@{AdapterId=$aid;State=$st;Clients=$cc;Err=$e} } } \| ConvertTo-Json -Depth 4 -Compress"` | PowerShell 5.1 → ConvertTo-Json → python 解析；rc＝powershell.exe 的 python returncode | 0 | 17 个连接配置文件，取值集合 (State, Clients, Adapter)=[('On', 1, None)]——全部相同 ⇒ 推断这是全局热点状态而非逐连接，区分不出共享源；Adapter 映射全空（同跑网卡清单超时） | —（读数，非门） |
| 6 | run2 | PC | 热点虚拟卡 ifIndex（现场推导） | 2026-09-26T12:22:17 | `（由上两项推出）` | 由「IPv4 地址」与「ICS 共享配置」两条读数推出 | 0 | {"by_ip": [{"ifIndex": 13, "alias": "本地连接* 10"}], "by_ics": []} | —（读数，非门） |
| 7 | run2 | PC | 源地址 ping 上游（vEthernet (WSL (Hyper-V firewall))） | 2026-09-26T12:22:17 | `ping -n 3 -w 2000 -S 192.168.144.1 223.5.5.5` | ping.exe 原生输出（cp936 解码）→ 只数来自目标且带 TTL= 的行；rc＝ping.exe 的 python returncode | 1 | 来自目标的回复 0/3；首条：PING: transmit failed. General failure. | 不通 |
| 8 | run2 | PC | 源地址 ping 上游（vEthernet (Default Switch)） | 2026-09-26T12:22:20 | `ping -n 3 -w 2000 -S 172.18.128.1 223.5.5.5` | ping.exe 原生输出（cp936 解码）→ 只数来自目标且带 TTL= 的行；rc＝ping.exe 的 python returncode | 1 | 来自目标的回复 0/3；首条：PING: transmit failed. General failure. | 不通 |
| 9 | run2 | PC | 源地址 ping 上游（本地连接* 10） | 2026-09-26T12:22:24 | `ping -n 3 -w 2000 -S 192.168.137.1 223.5.5.5` | ping.exe 原生输出（cp936 解码）→ 只数来自目标且带 TTL= 的行；rc＝ping.exe 的 python returncode | 0 | 来自目标的回复 3/3；首条：Reply from 223.5.5.5: bytes=32 time=17ms TTL=112 | 通 |
| 10 | run2 | PC | 源地址 ping 上游（以太网） | 2026-09-26T12:22:28 | `ping -n 3 -w 2000 -S 10.10.8.9 223.5.5.5` | ping.exe 原生输出（cp936 解码）→ 只数来自目标且带 TTL= 的行；rc＝ping.exe 的 python returncode | 0 | 来自目标的回复 3/3；首条：Reply from 223.5.5.5: bytes=32 time=17ms TTL=113 | 通 |
| 11 | run2 | PC | 不指定源 ping 上游（对照） | 2026-09-26T12:22:32 | `ping -n 3 -w 2000 223.5.5.5` | ping.exe 原生输出（cp936 解码）→ 只数来自目标且带 TTL= 的行；rc＝ping.exe 的 python returncode | 0 | 来自目标的回复 3/3；首条：Reply from 223.5.5.5: bytes=32 time=17ms TTL=113 | 通 |
| 12 | run2 | P40 | 设备在线 | 2026-09-26T12:22:35 | `adb devices` | adb shell → python；rc＝adb 的 python returncode（shell v2 透传远端退出码） | 0 | {"devices": 1, "serial": "8MY0221126002537"} | 通 |
| 13 | run2 | P40 | 前台焦点（P40 流程第 1 步） | 2026-09-26T12:22:37 | `adb -s 8MY0221126002537 shell dumpsys window （只取 mCurrentFocus）` | adb shell → python；rc＝adb 的 python returncode（shell v2 透传远端退出码） | 0 | {"focus": "NotificationShade", "is_launcher": false} | —（读数，非门） |
| 14 | run2 | P40 | ANEB 进程（只读） | 2026-09-26T12:22:39 | `adb -s 8MY0221126002537 shell ps -A -o NAME` | adb shell → python；rc＝adb 的 python returncode（shell v2 透传远端退出码） | 0 | {"names": []} | —（读数，非门） |
| 15 | run2 | P40 | VPN/隧道接口（只取接口名） | 2026-09-26T12:22:42 | `adb -s 8MY0221126002537 shell ip link` | adb shell → python；rc＝adb 的 python returncode（shell v2 透传远端退出码） | 0 | {"tun_ppp_up": []} | —（读数，非门） |
| 16 | run2 | P40 | 屏幕与锁屏态（只读） | 2026-09-26T12:22:44 | `adb -s 8MY0221126002537 shell dumpsys power （只取 mWakefulness） ； adb -s 8MY0221126002537 shell dumpsys window （只取 mFocusedApp/isKeyguardShowing）` | adb shell → python；rc＝adb 的 python returncode（shell v2 透传远端退出码） | 0 | {"wakefulness": "Asleep", "focused_app": "com.huawei.android.launcher/.unihome.UniHomeLauncher", "keyguard": "true"} | —（读数，非门） |
| 17 | run2 | P40 | 邻居表（配置派生，旁证；lladdr 不落） | 2026-09-26T12:22:49 | `adb -s 8MY0221126002537 shell ip neigh show` | adb shell → python；rc＝adb 的 python returncode（shell v2 透传远端退出码） | 0 | {"rows": [{"ip": "192.168.137.1", "dev": "wlan0", "state": "STALE"}]} | —（旁证，非门） |
| 18 | run2 | P40 | ip route get（配置派生，旁证，不作门） | 2026-09-26T12:22:52 | `adb -s 8MY0221126002537 shell ip route get 223.5.5.5` | adb shell → python；rc＝adb 的 python returncode（shell v2 透传远端退出码） | 0 | {"via": "192.168.137.1", "dev": "wlan0"}；原样：223.5.5.5 via 192.168.137.1 dev wlan0 table 1040 src 192.168.137.129 uid 2000  ⏎     cache | —（旁证，非门） |
| 19 | run2 | P40 | ping 网关（第一跳，门） | 2026-09-26T12:22:55 | `adb -s 8MY0221126002537 shell ping -c 3 -W 2 192.168.137.1` | adb shell → python；rc＝adb 的 python returncode（shell v2 透传远端退出码） | 1 | 来自目标的回复 0/3；首条：3 packets transmitted, 0 received, 100% packet loss, time 2030ms | 不通（不作判据，D-906） |
| 20 | run2 | P40 | ping 上游目标（门） | 2026-09-26T12:23:02 | `adb -s 8MY0221126002537 shell ping -c 3 -W 2 223.5.5.5` | adb shell → python；rc＝adb 的 python returncode（shell v2 透传远端退出码） | 1 | 来自目标的回复 0/3；首条：3 packets transmitted, 0 received, 100% packet loss, time 2049ms | 不通 |
| 21 | run2 | P40 | dumpsys connectivity 默认网络与 VALIDATED（旁证，只落派生字段） | 2026-09-26T12:23:07 | `adb -s 8MY0221126002537 shell dumpsys connectivity` | adb shell → python；rc＝adb 的 python returncode（shell v2 透传远端退出码）；原文只在内存解析、不落盘 | 0 | {"default_network": "243", "transport": "WIFI", "VALIDATED": true, "INTERNET": true, "PARTIAL_CONNECTIVITY": false, "CAPTIVE_PORTAL": false} | —（旁证，非门） |
| 22 | run3 | PC | 网卡状态（含隐藏） | 2026-09-26T12:29:45 | `powershell -NoProfile -NonInteractive -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ErrorActionPreference='Continue'; & { Get-NetAdapter -IncludeHidden \| Select-Object Name,InterfaceIndex,Status,InterfaceDescription } \| ConvertTo-Json -Depth 4 -Compress"` | PowerShell 5.1 → ConvertTo-Json → python 解析；rc＝powershell.exe 的 python returncode | 0 | 本地连接* 10(if13) Up〔Microsoft Wi-Fi Direct Virtual Adapter #2〕；本地连接* 1(if11) Disconnected〔Microsoft Wi-Fi Direct Virtual Adapter〕；以太网(if9) Up〔Intel(R) Ethernet Connection (7) I219-V〕；WLAN(if4) Disconnected〔Intel(R) Wireless-AC 9560 160MHz〕（只列相关四张，全表见 JSON） | —（读数，非门） |
| 23 | run3 | PC | ICS/移动热点服务状态 | 2026-09-26T12:31:10 | `powershell -NoProfile -NonInteractive -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ErrorActionPreference='Continue'; & { Get-Service SharedAccess,icssvc \| Select-Object Name,@{n='Status';e={$_.Status.ToString()}} } \| ConvertTo-Json -Depth 4 -Compress"` | PowerShell 5.1 → ConvertTo-Json → python 解析；rc＝powershell.exe 的 python returncode | 0 | {"rows": [{"Name": "icssvc", "Status": "Running"}, {"Name": "SharedAccess", "Status": "Running"}]} | —（读数，非门） |
| 24 | run3 | PC | ICS 共享源（读法一 WMI HomeNet） | 2026-09-26T12:31:18 | `powershell -NoProfile -NonInteractive -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ErrorActionPreference='Continue'; & { Get-CimInstance -Namespace root/Microsoft/HomeNet -ClassName HNet_ConnectionProperties \| ForEach-Object { [pscustomobject]@{ConnRef=[string]$_.Connection; IsIcsPublic=$_.IsIcsPublic; IsIcsPrivate=$_.IsIcsPrivate} } } \| ConvertTo-Json -Depth 4 -Compress" ； powershell -NoProfile -NonInteractive -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ErrorActionPreference='Continue'; & { Get-CimInstance -Namespace root/Microsoft/HomeNet -ClassName HNet_Connection \| Select-Object Guid,Name } \| ConvertTo-Json -Depth 4 -Compress"` | PowerShell 5.1 → ConvertTo-Json → python 解析；rc＝powershell.exe 的 python returncode | 0 | rows=[]；public=[]；private=[]；n_conn=0；err 空 | 未执行（量法失败） |
| 25 | run3 | PC | ICS 共享源（读法二 HNetCfg，@() 展开） | 2026-09-26T12:31:40 | `powershell -NoProfile -NonInteractive -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ErrorActionPreference='Continue'; & { $m=New-Object -ComObject HNetCfg.HNetShare; $all=@($m.EnumEveryConnection); [pscustomobject]@{Count=$all.Count}; foreach($c in $all){ $p=$m.NetConnectionProps.Invoke($c); $s=$m.INetSharingConfigurationForINetConnection.Invoke($c); [pscustomobject]@{Name=$p.Name;SharingEnabled=$s.SharingEnabled;SharingType=$s.SharingConnectionType} } } \| ConvertTo-Json -Depth 4 -Compress"` | PowerShell 5.1 → ConvertTo-Json → python 解析；rc＝powershell.exe 的 python returncode | 0 | rows=[{"Name": null, "SharingEnabled": null, "SharingType": null}]；public=[]；private=[]；enum_count=1；err 首行：Exception calling "Invoke" with "1" argument(s): "Cannot process argument because the value of argument "arguments" is  | 未执行（量法失败） |
| 26 | run3 | PC | IPv4 地址（run3 复读） | 2026-09-26T12:31:48 | `powershell -NoProfile -NonInteractive -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ErrorActionPreference='Continue'; & { Get-NetIPAddress -AddressFamily IPv4 \| Select-Object InterfaceIndex,InterfaceAlias,IPAddress } \| ConvertTo-Json -Depth 4 -Compress"` | PowerShell 5.1 → ConvertTo-Json → python 解析；rc＝powershell.exe 的 python returncode | 0 | vEthernet (WSL (Hyper-V firewall))(if45)=192.168.144.1；vEthernet (Default Switch)(if24)=172.18.128.1；本地连接* 10(if13)=192.168.137.1；本地连接* 1(if11)=169.254.23.9；以太网(if9)=10.10.8.9；WLAN(if4)=169.254.219.25；Loopback Pseudo-Interface 1(if1)=127.0.0.1 | —（读数，非门） |
| 27 | run3 | PC | 源地址 ping 上游（vEthernet (WSL (Hyper-V firewall))） | 2026-09-26T12:32:04 | `ping -n 3 -w 2000 -S 192.168.144.1 223.5.5.5` | ping.exe 原生输出（cp936 解码）→ 只数来自目标且带 TTL= 的行；rc＝ping.exe 的 python returncode | 1 | 来自目标的回复 0/3；首条：PING: transmit failed. General failure. | 不通 |
| 28 | run3 | PC | 源地址 ping 上游（vEthernet (Default Switch)） | 2026-09-26T12:32:07 | `ping -n 3 -w 2000 -S 172.18.128.1 223.5.5.5` | ping.exe 原生输出（cp936 解码）→ 只数来自目标且带 TTL= 的行；rc＝ping.exe 的 python returncode | 1 | 来自目标的回复 0/3；首条：PING: transmit failed. General failure. | 不通 |
| 29 | run3 | PC | 源地址 ping 上游（本地连接* 10） | 2026-09-26T12:32:11 | `ping -n 3 -w 2000 -S 192.168.137.1 223.5.5.5` | ping.exe 原生输出（cp936 解码）→ 只数来自目标且带 TTL= 的行；rc＝ping.exe 的 python returncode | 0 | 来自目标的回复 3/3；首条：Reply from 223.5.5.5: bytes=32 time=17ms TTL=112 | 通 |
| 30 | run3 | PC | 源地址 ping 上游（本地连接* 1） | 2026-09-26T12:32:16 | `ping -n 3 -w 2000 -S 169.254.23.9 223.5.5.5` | ping.exe 原生输出（cp936 解码）→ 只数来自目标且带 TTL= 的行；rc＝ping.exe 的 python returncode | 1 | 来自目标的回复 0/3；首条：PING: transmit failed. General failure. | 不通 |
| 31 | run3 | PC | 源地址 ping 上游（以太网） | 2026-09-26T12:32:20 | `ping -n 3 -w 2000 -S 10.10.8.9 223.5.5.5` | ping.exe 原生输出（cp936 解码）→ 只数来自目标且带 TTL= 的行；rc＝ping.exe 的 python returncode | 0 | 来自目标的回复 3/3；首条：Reply from 223.5.5.5: bytes=32 time=17ms TTL=113 | 通 |
| 32 | run3 | PC | 源地址 ping 上游（WLAN） | 2026-09-26T12:32:25 | `ping -n 3 -w 2000 -S 169.254.219.25 223.5.5.5` | ping.exe 原生输出（cp936 解码）→ 只数来自目标且带 TTL= 的行；rc＝ping.exe 的 python returncode | 1 | 来自目标的回复 0/3；首条：PING: transmit failed. General failure. | 不通 |
| 33 | run3 | P40 | 手机 wlan0 地址（只取 inet） | 2026-09-26T12:32:32 | `adb -s 8MY0221126002537 shell ip -4 addr show wlan0` | adb shell → python；rc＝adb 的 python returncode | 0 | {"inet": "192.168.137.129"} | —（读数，非门） |
| 34 | run3 | PC | 反向第一跳 ping 手机（源＝热点虚拟卡） | 2026-09-26T12:32:34 | `ping -n 3 -w 2000 -S 192.168.137.1 192.168.137.129` | ping.exe 原生输出（cp936 解码）→ 只数来自目标且带 TTL= 的行；rc＝ping.exe 的 python returncode | 1 | 来自目标的回复 0/3；首条：Request timed out. | 不通 |
| 35 | run3 | PC | PC 侧对手机的邻居状态（配置派生，旁证） | 2026-09-26T12:32:43 | `powershell -NoProfile -NonInteractive -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ErrorActionPreference='Continue'; & { Get-NetNeighbor -AddressFamily IPv4 -IPAddress 192.168.137.129 -ErrorAction SilentlyContinue \| Select-Object ifIndex,IPAddress,@{n='State';e={$_.State.ToString()}} } \| ConvertTo-Json -Depth 4 -Compress"` | PowerShell 5.1 → ConvertTo-Json → python 解析；rc＝powershell.exe 的 python returncode | 0 | {"rows": [{"ifIndex": 13, "IPAddress": "192.168.137.129", "State": "Permanent"}]} | —（旁证，非门） |
| 36 | run3 | P40 | 屏幕态（与本跑同时刻） | 2026-09-26T12:33:01 | `adb -s 8MY0221126002537 shell dumpsys power （只取 mWakefulness）` | adb shell → python；rc＝adb 的 python returncode | 0 | {"wakefulness": "Asleep"} | —（读数，非门） |
| 37 | run5 | P40+PC | 第一跳方向判别：手机 ping 网关 | 2026-09-26T12:44:05 | `adb -s 8MY0221126002537 shell "cat /proc/net/dev \| grep wlan0; ping -c 3 -W 2 192.168.137.1; echo PING_RC=$?; cat /proc/net/dev \| grep wlan0"` | adb shell（计数/ping/计数同一条命令）；PC 计数 psutil.net_io_counters 紧贴 adb 前后读（本地连接* 10）；rc＝adb 的 python returncode，ping 自身退出码另记 ping_rc_inside_shell | 0 | {"replies_from_target": 0, "ping_rc_inside_shell": 1, "pc_window": ["2026-09-26T12:44:05", "2026-09-26T12:44:12"], "pc_recv_delta": 5, "pc_sent_delta": 1, "stderr": "", "phone_rx_delta": 1, "phone_tx_delta": 5, "phone_tx_drop_delta": 0, "phone_rx_drop_delta": 0} | 不通（不作判据，D-906） |
| 38 | run5 | P40+PC | 方向判别：手机 ping 上游目标 | 2026-09-26T12:44:12 | `adb -s 8MY0221126002537 shell "cat /proc/net/dev \| grep wlan0; ping -c 3 -W 2 223.5.5.5; echo PING_RC=$?; cat /proc/net/dev \| grep wlan0"` | adb shell（计数/ping/计数同一条命令）；PC 计数 psutil.net_io_counters 紧贴 adb 前后读（本地连接* 10）；rc＝adb 的 python returncode，ping 自身退出码另记 ping_rc_inside_shell | 0 | {"replies_from_target": 0, "ping_rc_inside_shell": 1, "pc_window": ["2026-09-26T12:44:12", "2026-09-26T12:44:18"], "pc_recv_delta": 3, "pc_sent_delta": 3, "stderr": "", "phone_rx_delta": 0, "phone_tx_delta": 3, "phone_tx_drop_delta": 0, "phone_rx_drop_delta": 0} | 不通 |
| 39 | run5 | P40 | 屏幕态（本跑收尾） | 2026-09-26T12:44:18 | `adb -s 8MY0221126002537 shell dumpsys power （只取 mWakefulness）` | adb shell → python；rc＝adb 的 python returncode | 0 | {"wakefulness": "Asleep"} | —（读数，非门） |

## 3. 门的修订（run1 → run2；大脑已裁成立，D-918）

**大脑裁定（2026-09-26）：门成立，下面四行有效。** 理由摘要：CLAUDE.md 第 1 步「华为桌面为焦点」的目的是设备无冲突使用，不是一条量法；锁屏态下 `mCurrentFocus` 必为 NotificationShade，按字面这道门在锁屏态永远过不了，而修订后的三条查得比字面更严；改门发生在发 ping 之前，改的是冲突门而不是判定量。字面歧义入 D-918，CLAUDE.md 措辞交 PO 定。以下是修订当时的原始记录，保留不改。

- **跑前写下的门**：设备 `mCurrentFocus` 是华为桌面、且无 tun/ppp 接口在起，才从设备发 ping；否则设备侧 ping 记「未执行」。
- **run1 实读**：`mCurrentFocus=NotificationShade`，门不过，设备侧两格 ping 未执行（readings_run1.json）。
- **随后只读补查**：`mWakefulness=Asleep`、`isKeyguardShowing=true`、锁屏下的前台应用 `mFocusedApp` 是华为桌面、没有 ANEB 进程、没有 tun/ppp 接口。即焦点不在桌面是因为**锁屏盖在桌面上**，不是有别的会话在前台测。
- **run2 起的门**：锁屏下的前台应用是华为桌面、且无 tun/ppp ⇒ 发 ping。门的目的（不打扰他人在飞测量）不变，判法换了。
- ⚠ **这是看过 run1 数据之后改的门**。CLAUDE.md P40 流程第 1 步字面「华为桌面为焦点」**没有满足**（锁屏在上）。我据门的目的判断可以发 ping；这个判断是否成立由大脑定。若不成立，#19、#20、#37、#38 这四行作废，设备侧结论退回「未执行」。

## 4. 保留但不进主表的两跑

- **readings_run1.json**：①PowerShell 我用 `(...)` 包了多条语句，属语法错误，ICS 与热点两格 rc=1、没读出来；②按跑前的门，设备侧 ping 未执行。其余读数与 run2 同形。
- **readings_run4_direction.json**：⚠ **其中 `operstate` 字段是解析错误，不是读数**——手机 `/sys/class/net` 对 shell 无权限（`Permission denied`），我的解析把 ping 的头一行当成了 operstate；手机计数因此 0 行、未计增量。PC 侧增量（rx +4 / tx +1）来自两次 PowerShell 读数，两读相隔两分多钟，混有背景流量，只算弱读数。它的 `/proc/net/wireless` 读数（{'status': '0000', 'link': '70.', 'level': '-25.', 'noise': '-256'}，level 单位 dBm）是真读数：手机关联在、信号强——关联在而往返不通，与 D-906 那次同形。run5 用 `/proc/net/dev` 与 psutil 重做了方向判别。

## 5. 量法与纪律

- **ifIndex 现场推导**：持有 192.168.137.1 的接口，本次读到的见 #6（D-907 那次重启后读到的是另一个值——写死必过期，这次又证了一遍）。
- **不落盘的东西**：`dumpsys connectivity` 原文只在内存里解析，只落默认网络编号、传输类型、VALIDATED、INTERNET、PARTIAL_CONNECTIVITY、CAPTIVE_PORTAL 六项（D-608⑤）；邻居表不落链路层地址；热点配置文件不读名称。每个 JSON 写盘前都断言不含 MAC 样式串与网络名字段。
- **ICS 直读失败的原样**：读法一 WMI `root/Microsoft/HomeNet` 返回 0 条连接（同一跑的 IPv4 地址表里有 7 个接口（含回环），**0 条是量法失败，不是「没开共享」**）；读法二 HNetCfg 枚举到 1 条但元素是 null。两法都是非提权跑的；提权读不属于只读诊断该做的事，所以没做。
- **计数增量的读法**：增量为 0 是可靠的**读数**，增量 ≥3 混有背景流量，只当弱读数；但一个读数可靠不等于它是**判别器**，要另看世界表——本诊断的手机收包增量 0 就是在各世界下同值的例子（初版把它当判别器用了，见第 0 节订正）。run5 的 PC 侧计数是 psutil（GetIfEntry2，单播加非单播），紧贴 adb 调用前后读，窗口秒级。
- **执行通道**：所有脚本经 Write 工具落盘后再用 python 跑；PowerShell 输出强制 UTF-8；ping.exe 输出按 cp936 解码。

## 6. P40 流程收尾

本次没有启动任何 App 或服务，没有停止任何 App，没有 VPN/抓包，没有改 `stayon` 或任何设置，没有点亮屏幕。收尾时屏幕态仍是 Asleep（#39），与开测一致。实况与开测前相同，没有需要恢复的东西。

## 7. 复现

在仓根按顺序跑（均只读；设备序列号写死在脚本里）：

```bash
python evidence/c_device_gate_20260926/gate_diag.py
python evidence/c_device_gate_20260926/gate_diag3.py
python evidence/c_device_gate_20260926/gate_diag5.py
```

- gate_diag.py 是 run2 的版本（run1 版的 PowerShell 括号写法与门已按第 3、4 节改掉）；它写 readings_run2.json，复跑会覆盖。
- gate_diag4.py 是 run4 的版本，保留只为可审计，不要复跑（读法有缺陷，见第 4 节）。
- 读数表由 scratchpad 里一次性的生成器从三份 JSON 生成；它没入库，表内每格都能在 JSON 里逐字找到。
