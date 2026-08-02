# T24 判别查询：radio 归零根因——协程死亡 vs 活着吐空（大脑代查，2026-08-03 00:4x）

> 执行者：大脑（Fable 5）。v3 的 T24 派单消息积压约 50 分钟未处理（sent≠processed），
> 判别是修复方向的前置、下个 NR 窗随时可能开，按主动参与模式代查。**数字归本文件，
> 判读备忘仍归 T24 属主（v3），推荐 v3 自行复核而非转录本文数字——独立复核比转录值钱。**
>
> 设备操作：只读（`adb exec-out run-as com.aneb.probe cat databases/aneb-probe.db[,-wal,-shm]`，
> 与 `scripts/pull_device_corpus.py` 同机制），预检干净（无 VPN/抓包、无 ANEB 活动服务）。
> 库文件落在大脑 scratchpad，不入仓；本文件只归档查询结果与复现命令。

## 1. 判别结果：两假说一杀一留

对 `run_id=019fc1a6-ff97-7c91-843b-a1fa3e1a5118` 查 `radio_sample` 表：

| 量 | 实测值 | 协程死亡假说预测 | 活着吐空假说预测 |
|---|---|---|---|
| 总行数 | **413** | ~44（场景 1 后无行） | ~400+（1Hz×全程） |
| 带 rsrp/sinr 的行 | **44** | 44 | 44 |
| stale=1 的行 | 369 | 0（死了不写行） | ~369 |
| 采样节拍 | **gap 中位 1.00s / 最大 1.04s，全程无缺口** | 44 秒后停止 | 全程 1Hz |

**协程死亡假说被杀死**：采样循环 1Hz 节拍从 run 起跑到第 412 秒一秒不差——它活到了 run 结束。
v2 T23 备忘的头号候选（未捕获异常杀死协程）不成立；对抗核验（wf_0d4d6c9e ⑤）提出的
「活着吐空」被数据留下。

## 2. 边界时刻与屏灭区间吻合；静态原因被健康前段排除

- 最后一行带真实读数的样本：**run 起后第 43.0 秒**；第一行全 null+stale：**第 44.0 秒**。
- run 起于 16:46:14.9（epoch 1785660374943），边界即 **16:46:58.9 左右**。
- rat_watch.tsv（31 秒粒度）：16:46:33 屏 **ON** → 16:47:05 屏 **OFF**——屏灭发生在
  (16:46:33, 16:47:05] 区间内，**数据边界 16:46:59 恰落在该区间**。
- **静态原因全部被排除**：定位服务关闭、权限缺失等 run 前就存在的状态，无法解释
  「前 44 秒健康、之后归零」——若是静态因素，场景 0/1 也该是空的。只有 **run 中发生的
  状态变化**能解释这个边界，而该时刻唯一已知的状态变化就是**屏灭**。
- 机制侧（对抗核验已核）：`requestCellInfoUpdate` 超时/空返回时 `RadioCollector.kt:221-227`
  返回 `(emptyList, true)`，`buildSample` 产出全 null+stale 样本——Android 屏灭节流
  cell info 更新是文档化行为，与观测形状零矛盾。
- 细节留观：dead 行仍带 `nrState='nsa_unknown'`（非 null）——说明部分字段在陈旧路径下
  仍被赋值，字段级行为差异留给修复实现者核对。

**定性（大脑判断，供 T24 备忘复核后确认或推翻）**：根因方向 = **屏灭后系统节流 cell info，
采集器如实降级为陈旧样本**——数据没有说谎（stale=1 就是陈旧，导出面已正确把它排除出
sampled_n），缺的是「为什么陈旧」的标注与「测量窗内不该让屏灭」的运维约束。

## 3. 复现命令

```
adb -s 8MY0221126002537 exec-out run-as com.aneb.probe cat databases/aneb-probe.db > aneb-probe.db
# (-wal/-shm 同理)
sqlite3: SELECT COUNT(*), SUM(rsrp IS NOT NULL OR sinr IS NOT NULL), SUM(stale=1)
         FROM radio_sample WHERE runId='019fc1a6-ff97-7c91-843b-a1fa3e1a5118';
-- 413 | 44 | 369
```

## 4. 遗留矛盾（如实记，交修复批）

pounce 脚本在 run 前执行了 `svc power stayon usb`（16:46 前后），wrap-up 16:53 才恢复
false——**stayon usb 生效期内屏为何 16:47 前后灭了**？候选：EMUI 对 stayon 的覆盖、
或 stayon 只防锁屏不防灭屏、或 wakeup+swipe 后无真实用户活动触发系统超时灭屏无视
stayon。此矛盾未判别，修复批（运维侧保屏方案）必须先把它查清，否则「保持屏亮」的
修复可能落在与 stayon 相同的无效路径上。
