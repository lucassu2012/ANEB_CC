# 链跑 flake 记录：`:probe:kspDebugKotlin` 偶发红（sqlite-jdbc 原生库）

> 落这份摘要而**不入库红门日志**，是 2026-09-07 的裁定：`.gitignore` 排除链跑日志是有意的，
> 为一次 flake 破例会让下一个人以为可以照办。**日志本体留在原地，本文件指向它的文件名。**
> 下一个撞上它的人不必从头查。

## 1. 症状与根因链

`verify_all -Scope all` 的 `app-assembleDebug` 门红，链条：

```
:probe:kspDebugKotlin FAILED
  → androidx.room.processor.DatabaseProcessor.doProcess
  → androidx.room.verifier.DatabaseVerifier.<clinit>
  → org.sqlite.SQLiteJDBCLoader.loadSQLiteNativeLibrary
  → java.lang.Exception: No native library found for os.name=Windows, os.arch=x86_64
```

**单一根因，无第二条隐藏 FAIL**（这条特意查过——本仓上一次同族问题的真因就藏在另一条 FAIL 里）。

## 2. 两份日志（**红那份不在仓里**）

| 跑 | 文件名 | 结果 |
|---|---|---|
| 第一跑 | `verify_all_20260907-111907-33416.log` | **RC=1**，`app-assembleDebug` FAIL。**未入库**（见页首裁定） |
| 第二跑 | `verify_all_20260907-113134-32880.log` | **RC=0**，27 门全绿。**已入库**（D-604②：badges 点名的日志须随批 `git add -f`） |

## 3. 复现率

近 **12** 次全链日志里出现 **2** 次：本次，与 `verify_all_20260904-020338-45184.log`。
⚠ **后者远早于 2026-09-07 的全部提交**（含跑器修复本身）⇒ **与那批改动无关**。

## 4. 已排除的两个候选（各有判决性依据，不是印象）

| 候选 | 排除依据 |
|---|---|
| **sqlite-jdbc JAR 里缺原生库** | 那会是**持续性**的、重跑必再红。实测重跑通过 ⇒ 不成立 |
| **2026-09-07 的改动引入** | 同一错误在 `20260904-020338` 已出现过，**早于全部这些提交** ⇒ 不成立 |

⚠ **触发条件仍未定，本文件不编一个。**「近 12 次出现 2 次」「另一次早于今天所有提交」
是**它是什么**的证据，**不是它为什么**的证据——两者不能混。

## 5. 🔴 判它是 flake 时最容易走空的一步

**同一跑内它已自证**：同一个 `kspDebugKotlin` 在红门里 FAILED，**几分钟后在
`app-parity-tests` 里跑成功**（该门 PASS），随后 UP-TO-DATE ⇒ 源码可编译。

而**独立复验时差点走空**：

> 先重跑 `:probe:assembleDebug`，rc=0 —— **但那一跑里 `kspDebugKotlin` 是 `UP-TO-DATE`、
> 根本没有执行**。**那次绿不构成证据。**

⇒ 必须 `./gradlew :probe:kspDebugKotlin --rerun --no-daemon` **强制该任务真的重新执行**
（输出里不带 `UP-TO-DATE` 才算数），结果 BUILD SUCCESSFUL。

**「重跑一次就好了」是一个结论，不是一次观察。** 下次照做这一步，别停在 `assembleDebug` 绿。

## 6. 撞上时怎么办

1. 先看**同一份日志里后面的 gradle 门**（`app-parity-tests`／`app-unit-tests-full`）有没有跑过同一任务并 PASS；
2. 再 `--rerun` 强制那一个任务执行，**确认输出里没有 `UP-TO-DATE`**；
3. 两条都过 ⇒ 记为本 flake，**不改代码**，把新的复现次数补进 §3；
4. 若 `--rerun` 仍红 ⇒ **它不再是 flake**，按持续性故障查，且本文件 §4 的两个排除结论作废。
