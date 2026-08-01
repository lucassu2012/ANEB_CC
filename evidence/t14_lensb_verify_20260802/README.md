# T14 特别镜头 B（DTO 派生键集）对抗验证 —— 2026-08-02 夜班 ①a

补 `docs/T14_CROSS_AUDIT_20260801.md` §6.2 记的最大缺口：那 28 条**零对抗验证**
（原轮两名验证者均死于连接错误），而它与 v2 今晚的 `:probe` 改动直接相关。
判定见该文件 **§8**（28 CONFIRMED / 0 REFUTED / 2 处订正）。

| 文件 | 内容 |
|---|---|
| `verify_lens_b.py` / `lensb_out.txt` | 第一轮：31 个沙箱实验，逐条打印实际违规码与报文 |
| `verify_lens_b2.py` / `lensb2_out.txt` | 第二轮：把第一轮靠「违规数=0」**倒推**的几条，改为**直接量派生出的键集**（D-394 规矩 c），并补齐控制组 |
| `verify_lens_b3.py` / `lensb3_out.txt` | 第三轮：跑**真的 `main()`**，取门**印出来**的那一行（六组对照） |

**仓库零字节改动**：突变只活在内存与 `tempfile` 临时目录里；第三轮把
`validate_adapters` 的 `KOTLIN_DTO` / `HERE` / `ASSETS_DIR` 三个模块级常量**运行时**指向
临时副本（D-322 的手法），`finally` 里复位；跑完用 `git status` **独立**核过（D-321）。

**再跑**：三份脚本顶部的 `ROOT` 是绝对路径（它们本就在仓外的 scratchpad 里跑），
挪到别的机器需改那一行。`python verify_lens_bN.py`，建议 `PYTHONIOENCODING=utf-8`
——控制台按 GBK 解会在第一个非 GBK 字符上崩（D-394 第②例同族）。
