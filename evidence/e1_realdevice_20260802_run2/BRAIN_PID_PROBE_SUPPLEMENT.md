# 大脑侧 pid 查询补测——补录 **【已作废，按本文自设条款】**

> **2026-08-02 18:1x 作废（D-411）**：run3 实测钉死——「按包名失效、按 pid 可用」的差异
> 是本补录命令里 `head -3` vs `head -5` **截断深度不对称**造出的伪影，与查询方式无关；
> run1/run2 的 No process 由 D-408 结构缺陷（串行分段、轮询时进程真不在）完整解释。
> 本补录按「若 run3 不复现即作废」条款正式作废。**量法红线族追加一例：
> 对两个待比较对象施加不对称的截断，差异可能全部来自截断本身**（与族内 Select-String
> -Context 截断例同形，犯者=大脑）。原文保留如下供审计。

**性质**：本文件是**事后补录**，非采集时落盘。2026-08-02 16:4x 大脑会话执行了一次独立
adb 探测，输出当时只存在于大脑对话中、未写入任何 evidence——**这违反了证据落盘纪律**，
v4 判读（D-409 ②③）按「目录内查无实据」处理完全正确。本补录如实转写当时的命令与输出，
其证据强度**低于**落盘采集（无法排除转写误差），**正式验证以 run3（v3 修复后）为准**。

## 当时的命令（逐字）

    adb -s 8MY0221126002537 shell "pidof com.aneb.e1stimulus;
      dumpsys gfxinfo com.aneb.e1stimulus framestats 2>&1 | head -3;
      dumpsys gfxinfo $(pidof com.aneb.e1stimulus) framestats 2>&1 | head -5"

（执行时刺激 Activity 已确认前台 mFocusedApp；随后 force-stop+HOME+POWER 收尾。）

## 当时的输出（逐字转写）

    16519
    Applications Graphics Acceleration Info:
    Uptime: 776964540 Realtime: 871478189

    Applications Graphics Acceleration Info:
    Uptime: 776964574 Realtime: 871478223

    ** Graphics info for pid 16519 [com.aneb.e1stimulus] **

## 当时的解读（待 run3 证实或证伪）

- 按包名查询：仅返回全局头两行，无该进程段；
- 按 pid 查询：返回 `** Graphics info for pid 16519 [com.aneb.e1stimulus] **` 进程段头。
- 若 run3 复现：EMUI 上 gfxinfo 按包名解析失效、按 pid 可用 → 通道 C 帧时序支路可救；
- 若 run3 不复现：本补录作废，以 run3 为准。

*大脑会话补录于 2026-08-02 17:5x，承 D-409 K-1（核对归因框架证据来源）。*
