# 段 B 步骤 0–2：BeanNetworkTester 无头验收（2026-09-07）

> 批次：段 B（整形器换 clumsy → BeanNetworkTester v0.6.0）验收的**非提权可做部分**。
> 口径：本目录**只记步骤 0–2**（下载校验／`--print-config`／`--dry-run`），三步全在**非提权会话**内、
> **零副作用**完成。**步骤 3–6（真整形、驱动加载）不在本目录**——它们需 admin 接线，候 PO。
> ⚠ **本文件不主张「整形有效」**：dry-run 说「config 合法」≠「运行时会整形」（承 D-789）。
> 授权基础＝用户本会话常设授权「驱动加载授权，后续一律同意授权」（覆盖整形链），下载独立取、独立校验。

## 0. 独立下载 + 完整性校验（独立取一次＝再验一次）

```
url    = https://github.com/donislawdev/BeanNetworkTester/releases/download/v0.6.0/BeanNetworkTester-v0.6.0-windows-x64.zip
字节    实测 12900470 == 期望 12900470            匹配 True
sha256 实测 3d6a17ae8880a675f0fc23eeb1f5520a638fb1433ae9ea6ef77ca4df85cbed1a
sha256 期望 3d6a17ae8880a675f0fc23eeb1f5520a638fb1433ae9ea6ef77ca4df85cbed1a  匹配 True
```

⚠ **首次 curl（协调侧）曾截断到 5,093,058 字节、curl 仍报 `http=200`**——「下载成功」≠「下载完整」，
是校验和当场逮住的。本次为独立完整取。解包＝PyInstaller 冻结的 Python 应用，**自带 tk/tkinter ⇒ 有 GUI**；
随包 `_internal/pydivert/windivert_dll/WinDivert64.dll`(47616)/`.sys`(94144) 在位（即协调侧逐字节核过的
basil00 v2.2.2 那两个，见 `docs/B2_SHAPER_VERIFICATION_20260907.md`）。

## 1. `--print-config`（正面判据，不是结论）

**命令**：`BeanNetworkTester.exe --print-config`（非提权，30s 硬超时包裹）
**观测**：**在 30s 超时内自行退出**；stdout 一段合法 JSON；stderr **空**；**无 GUI 窗口、无 UAC、无驱动加载**。

> 🔴 这是「它不是 clumsy 第二」的**唯一强数据点**：clumsy 带参启动只开 GUI 等点击（D-792）；
> 本工具**有真正的无头 CLI**。因它自带 GUI，我**没轻信文档**，改为实跑＋硬超时——超时没触发、它自己退了。

stdout（33 键，整形旋钮全暴露）：

```json
{ "block_ip": "", "block_port": "", "buffer": 1000, "corrupt": 0, "down": 0, "dst_ip": "",
  "dst_port": "", "dup": 0, "duration": 0, "filter": "both", "flap_down": 0, "flap_period": 0,
  "internet_only": false, "ipv4_only": false, "ipv6_only": false, "jitter": 0, "lan_mode": false,
  "latency": 0, "loss": 0, "loss_burst": 0, "max_size": 0, "narrow_filter": false, "nat_timeout": 0,
  "rate_schedule": "", "row_limit": 50000, "rst_cooldown": 3, "rst_prob": 0, "seed": -1,
  "spike_ms": 0, "spike_prob": 0, "syn_drop": 0, "target": "", "up": 0 }
```

⚠ 破坏性旋钮就在此列：`rst_prob`（TCP RST 注入）、`block_ip`/`block_port`（阻断）、`lan_mode`。见 §3。

## 2. `--dry-run`（含对否定命题的正对照）

**命令**：`BeanNetworkTester.exe --latency 200 --target 120.79.148.0 --dry-run`（`BEAN_NO_ELEVATE=1`，30s 超时）
**stderr 原文**：

```
[bean] Configuration is valid (--dry-run: nothing was started). This checks the settings, not the machine - run --doctor for Administrator rights and the WinDivert driver.
```

🔴 **跑后 `sc.exe query WinDivert` = 1060（服务不存在）** —— 这是**对「dry-run 什么都没碰」的正对照**：
不是「我没看到驱动」，是**用一个能看见驱动的量法去看，它确实不在**。
**这条（外部观测）的证据力高于上面那句文案（工具自述）。**
附带发现工具自带 **`--doctor`**（查 admin 权限 + WinDivert 驱动）——步骤 5 的天然预检。

**收尾**：无 BeanNetworkTester/clumsy 残留进程、无驱动、全程无提权无窗口。机器干净。

## 3. §三 部署安全：三条提权路径，白名单正则是唯一边界

**effective 实测**（直接试写，**不读 ACL**——ACL 骗过一次：根目录 ACL 显示 Modify，而 `bin` 的实际写入失败）：

| 目录 | 非管理员可写 | 含义 |
|---|---|---|
| `E:\tools\aneb-shaper`（根） | **YES** | §4-B：未签名 `WinDivert64.dll` 可被换 ⇒ 提权路径 |
| `E:\tools\aneb-shaper\bin` | NO | 安全（`shaper.ps1` 在此），但非管理员也放不进工具 |
| `E:\tools\aneb-shaper\profiles` | **YES** | 🔴 **第三条路径**：`shaper.ps1` 从此读 `current.args` 喂给 `/RL HIGHEST` 提权进程 |

三条提权路径互不相同：①换未签名 DLL（§4-B）②根目录可写 ③**非管理员可写文件喂参数给提权进程**（本目录 profiles）。
**今天拦住 ③ 的只有 `shaper.ps1` 里那条白名单正则**——它只认 clumsy 旗标、字符类收得紧。
**那条正则是这条链上唯一的安全边界，不是装饰。**

⚠ **治理缺口**：`shaper.ps1`／`shaper_stop.ps1` **均不受 git 跟踪**（`git ls-files | grep shaper` 只有 docs 与一份 m3 evidence）
⇒ 一条承重的安全控制只活在磁盘上、无版本、无守卫、改了没有任何东西会报。归 PO 单子。

§三 结论（供 PO admin 落地，非管理员做不了）：
- **(A)** 工具自提权（`ShellExecuteW runas`，`BEAN_NO_ELEVATE` 可关）；经 `/RL HIGHEST` 任务起时应设 `BEAN_NO_ELEVATE=1`（已提权、无需自提）。
- **(B)** 工具家目录必须**管理员独写**：建议 `C:\Program Files\aneb-shaper\`（Windows 默认即管理员独写，免动 ACL）。
- **(C)** 默认作用域＝全机流量 + RST 注入 + 阻断 ⇒ 每次调用**显式** `--filter`/`--target`，绝不吃默认值。
- **重写白名单硬要求**：正面枚举要用的那几个旗标（三档＋`--filter`/`--target`）、**显式确保 `rst_prob`/`block_ip`/`lan_mode` 过不了并造反例测它**（只有正例的白名单放宽成「全放行」照样全绿）、字符类沿用现有紧度。

## 4. 已证 vs 仍未证

- **已证**：工具有**真无头 CLI**（config 校验层）⇒「换 clumsy 是因为它只能 GUI」这个前提在新工具上**不成立**。
- **仍未证**（步骤 4–6，候 admin 接线）：**它真跑起来到底加不加载驱动、整不整形**。承 D-789：读文档＋dry-run「config 合法」**不构成运行时断言**。

## 5. 复现命令

```
# 下载 + 校验
Invoke-WebRequest -Uri <url 见 §0> -OutFile bean.zip
(Get-FileHash -Algorithm SHA256 bean.zip).Hash   # 须 == 3d6a17ae…cbed1a ；字节须 == 12900470
Expand-Archive bean.zip -DestinationPath ext
# 步骤 1（零副作用）
ext\BeanNetworkTester\BeanNetworkTester.exe --print-config      # 应自行退出、打印 JSON、无 GUI
# 步骤 2（规划期不提权）
$env:BEAN_NO_ELEVATE='1'; .\BeanNetworkTester.exe --latency 200 --target <ip> --dry-run
sc.exe query WinDivert    # 应 1060（服务不存在）＝驱动确未被碰
```

## 6. 边界

- 本目录原始产物（校验输出、`pc_out.txt`、`dr_err.txt`）在会话 scratchpad，非入库；上面的命令＋数据可独立重算。
- 步骤 3 的「非提权触发 /RL HIGHEST、不弹 UAC」**已由 D-790 证过**（我自己做的，clumsy PID 34812）——**本轮不重跑**；现在唯一开着的窄问题是「BeanNetworkTester 在 /RL HIGHEST＋BEAN_NO_ELEVATE=1 下起来弹不弹交互提示」，只有用真工具才有意义（步骤 4–6）。
