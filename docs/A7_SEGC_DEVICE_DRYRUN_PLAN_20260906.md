# A-7 段 C · 设备侧预案（2026-09-06）

> 🔴 **本文件只是预案，写完不执行。** 段 C 动设备须**窗令**＋根 `CLAUDE.md` 的 P40 五步。
> **两个前置都未落地**（2026-09-06 现态）：
> ① PO 跑 `docs/E2_SCHTASKS_SETUP_20260906.md` §2（schtasks 常态化，PO 已裁 (b)）；
> ② v4 段 B 自环（零设备，PC 内 clumsy＋WinDivert 自证）。
> **两者任一未过即不得进段 C。**

## 0. 已核实的事实（写进来是因为预案里的路径若不存在，执行者会照着走错）

| 项 | 现态（只读核过，零 adb 调用） |
|---|---|
| gnirehtet 落点 | `E:\tools\aneb-shaper\gnirehtet\gnirehtet-rust-win64\`，含 `gnirehtet.exe`／`gnirehtet.apk`／`gnirehtet-run.cmd` **三件齐** |
| gnirehtet 版本与外部锚 | v2.5.1，**zip 有上游 sha256 锚**（见 `B2_SHAPER_BUILD_SHEET_20260903` 供应链表） |
| clumsy 本体 | **无外部锚**（发布页不提供校验和），如实登记，**不得写成已验证** |
| PCAPdroid 是否在机 | **本预案未核**——它要 adb，属段 C 步 1，不在预案期做 |

⚠ **段 B 过不代表段 C 过。** 段 B 证的是「clumsy 能命中 PC 自己的出站」，
段 C 要证的是「它能命中 **gnirehtet 的转发路径**」——**两条不同的路径，前者过后者未必过**
（`B2_SHAPER_BUILD_SHEET_20260903`，搜锚字串 `两条不同的路径，前者过后者未必过`）。

---

## 1. 步 1（**段 C 第一件事**）：gnirehtet 与 PCAPdroid 的 VPN 互斥验证

**为什么它排第一**：Android 同一时刻通常只允许一个 VPN 槽位，
而 **PCAPdroid 是 F3/F4 上行字节的唯一证据源**。若两者互斥，
「受控档扫描」与「上行字节证据」**只能二选一**。
⚠ **现状是推断不是结论**（`D-656` ③ 列为段 C 首验）。
🔴 **`D-656` ③ 只裁了「什么时候验」，没裁「互斥时怎么选」**——
**别把「已排验」读成「已解决」**；验出互斥后取舍仍待裁。

**脚本（照抄可跑；每步都有正面判据，「没报错」不算过）**

```bash
# 1.0 前提:设备在线、屏亮、探针恰一进程(操作卡 v3 ①/P1a)
adb devices
adb shell dumpsys power | grep -m1 mWakefulness=          # 须 Awake
adb shell ps -A -o PID,NAME | grep -c aneb                # 须 1

# 1.1 PCAPdroid 在不在机(不在则互斥问题不成立,如实记 NOT_APPLICABLE)
adb shell pm list packages | grep -i pcapdroid

# 1.2 基线:当前有没有 VPN 在跑
adb shell ip link | grep -E "tun|ppp"                     # 期望:空
adb shell dumpsys connectivity 2>/dev/null | head -0      # ⚠ 禁用,会打印 SSID(D-608⑤)
```

⚠ **上面最后一行是反例，写出来是为了让人别用**：核网络一律
`ip route get <目标>`，**不用 `dumpsys connectivity`**——它会把 SSID 打进终端。

**1.3 互斥判定（三态，正面写）**

| 观察 | 判定 | 后续 |
|---|---|---|
| PCAPdroid 起 VPN 后，装 gnirehtet 并授权，**PCAPdroid 的 tun 消失** | **互斥成立** | 停下报裁：受控档扫描 vs 上行字节，二选一 |
| 两者 tun **同时在**且各自转发正常 | **不互斥** | 段 C 继续，两通道可并行 |
| gnirehtet 授权弹窗**不出现**或授权被拒 | **NOT_EXECUTED** | 不写成「互斥」——**授权失败与互斥是两回事** |

🔴 **第三行是本表最容易被跳过的一格**：授权没成功时，屏幕上同样看不到 gnirehtet 的 tun，
**与「被 PCAPdroid 占住槽位」在现象上完全同形**。
⇒ **判互斥前必须先证明「gnirehtet 单独跑时能起来」**（即先在**没有 PCAPdroid VPN** 的干净态下跑通一次），
**否则拿到的「互斥」可能只是一次失败的授权。**

---

## 2. 步 2：gnirehtet 装机与授权

```bash
# 2.1 装 apk(路径已核实存在)
adb install -r "E:/tools/aneb-shaper/gnirehtet/gnirehtet-rust-win64/gnirehtet.apk"
adb shell pm list packages | grep -i gnirehtet            # 正面判据:须命中

# 2.2 PC 侧起 relay(前台窗口,便于随时停)
#     E:\tools\aneb-shaper\gnirehtet\gnirehtet-rust-win64\gnirehtet.exe run

# 2.3 设备侧授 VPN —— 人办事项
```
⚠ **2.3 授权弹窗必须由人点**。**凭据与系统级授权一律不代操作**；
会话只做到「把弹窗弄出来」并核结果，**不代点**。

---

## 3. 步 3：出口判据 —— `ip route get 120.79.148.0`

**这是段 C 的核心判据：证明设备流量真的改走了 USB 反向 tether，而不是「装了但没生效」。**

```bash
# 3.1 起 gnirehtet 之前
adb shell ip route get 120.79.148.0        # 期望 dev wlan0 或 rmnet0
# 3.2 起 gnirehtet 并授权之后
adb shell ip route get 120.79.148.0        # 期望 dev tun0(或 gnirehtet 的 tun 名)
```

| 观察 | 判定 |
|---|---|
| 前 `wlan0`／`rmnet0` → 后 **`tun`** | **PASS：转发路径已生效** |
| 前后**都不是 tun** | **FAIL：装了没生效**——别继续跑格，数据会走原路而标签写着「受控」 |
| 前后**都是 tun** | **前提脏**：开跑前已有别的 VPN，回步 1 |

🔴 **为什么判据要盯出口而不是「gnirehtet 有没有报错」**：
`B2_SHAPER_BUILD_SHEET_20260903` 已实证同族形状——
**过滤器写错时 clumsy 安静地什么都不做，「没报错」不算过**。
gnirehtet 同理：**进程活着 ≠ 流量改道**。

⚠ **`120.79.148.0` 是 E-01 公网 IP**，选它是因为它**在设备默认路由之外**、
且段 B 已用它做过 PC 侧基线 ⇒ **两段用同一个目标，出口差异才可比**。

---

## 4. 收尾清单（**当场做，事后补不回**）

```bash
# 4.1 停 PC 侧
#     关 clumsy 窗口;停 gnirehtet(Ctrl+C 或关窗)
# 4.2 停设备侧转发与残留规则
adb reverse --remove-all
# 4.3 复验:tun 无残留
adb shell ip link | grep -E "tun|ppp"                # 正面判据:须为空
# 4.4 复验:出口回到原路
adb shell ip route get 120.79.148.0                  # 须回 wlan0/rmnet0
# 4.5 复验:PC 侧驱动已停
#     sc query WinDivert                             # 须 STOPPED 或查无此服务
# 4.6 回桌面并复核
adb shell input keyevent KEYCODE_HOME
adb shell dumpsys window | grep -m1 mCurrentFocus    # 须华为桌面
```

⚠ **停自家探针不得用 `am force-stop`**（`D-611`：会把无障碍服务标 Crashed 并整体禁用，
恢复需动 `settings secure` ＝人办事项）。用退桌面或 `am kill`。
⚠ **`R3` 不动 App**：clumsy 的 `Tamper` 功能**全程禁用**，不改包内容。
⚠ **卸不卸 gnirehtet.apk 由窗令定**；本预案不默认卸——**卸载会让下一窗重装重授权**，
而**授权是人办事项**，代价不对称。

---

## 5. 本预案**没有**回答的（如实列，别读成已解决）

1. **互斥时怎么取舍**——`D-656` ③ 只裁了「什么时候验」。**验出互斥后仍待裁。**
2. **clumsy 能否命中 gnirehtet 转发路径**——段 B 过**不代表**这条过，需段 C 实测。
3. **带宽帽档位**——clumsy 0.3 有独立 bandwidth 模块，但**本预案未验其在 tun 路径上的行为**。
4. **PCAPdroid 是否在机**——要 adb，属段 C 步 1.1，**预案期不做**。
