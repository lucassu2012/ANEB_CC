# `split_by_run_mode.py` 只读复核（T21③，D-419 之后）

> 写作条件：全程只用 Read（工具层故障期间），未跑任何命令、未执行任何测试。
> 复核对象：`scripts/split_by_run_mode.py` + `scripts/tests/test_split_by_run_mode.py`。
> 与大脑同时在跑的三路对抗核验互为独立，本备忘不对齐其结论，照自己的读法来。

大脑派单的三个重点，逐条给结论；**找到一处真实的测试覆盖缺口（非缺陷）**，详见 §1 结尾。

---

## ① mode 缺失行的处置——代码对，且比测试覆盖的范围更宽

**代码**（`split_records()`）：`mode is None or (isinstance(mode, str) and not mode.strip())`
→ 判 `missing_mode`，`rejected` 列表留痕 `{"reason": "missing_mode", "run_id": ...}`。
**不静默丢、不当第三种 mode**——文档声称与代码行为一致。

**已测的两种缺失形态**：
- `run.mode` 键本身不存在（`del rec["run"]["mode"]`）——`test_missing_mode_key_is_rejected_not_silently_dropped`。
- `run.mode` 是空字符串——`test_empty_string_mode_is_treated_as_missing_not_unknown`，
  与文档正文"空字符串等价于没写"的说法一致。

**发现的缺口——`run` 键本身整个不存在的记录，代码处理对了，但没有任何测试覆盖它**：

`run_obj(rec)` 的实现是 `rec.get("run") or {}`（`campaign_common.py:427-428`）。
若 `rec` 里根本没有 `"run"` 这个键，`rec.get("run")` 返回 `None`，`None or {}` 落到 `{}`，
再 `{}.get("mode")` 得 `None`，走进 `missing_mode` 分支——**逐字追过代码，这条路径是对的**，
和"`run` 存在但缺 `mode`"归到同一个桶，语义上也说得通（两种情况对下游 `--plan` 而言
都是"这条记录判不了 mode"）。

**但测试套件里没有任何一条构造过"`rec` 没有 `run` 这个顶层键"的夹具**——`test_split_by_run_mode.py`
的 `_with_mode()` 辅助函数（:23-30）永远先 `make_record()` 拿到一个带完整 `run` 对象的记录，
`drop_key=True` 只删 `run` 内部的 `mode` 键，从未删过 `run` 这个键本身。全文件 Grep
`del rec["run"]` 或任何构造"无 run 键"字面量的写法——**零命中**。

**为什么这不是理论洁癖，是一个真实会发生的输入形状**：`split_by_run_mode.py` 的 `main()`
不像 `campaign_report.py` 那样在入口自动跑契约门（base runbook §4 的"入口自动跑契约门，
坏语料拒绝出报告"这条对这个新工具不成立——读了 `main()` 全文，只调用了
`cc.load_records()`，没有调 `validate_results.py` 的等价逻辑）。若操作者跳过契约校验、
或喂了一份手改/半成品 JSONL 直接进这个工具，"某条记录压根没有 `run` 键"是**契约违规但
现实会发生**的输入，不是构造出来的边角案例。

**建议**：补一条测试，构造 `rec = {"scenarios": [...]}`（或更简的空字典）这类完全没有
`run` 键的记录，断言它同样落进 `missing_mode` 且不抛异常——把"代码读出来是对的"升级为
"有一条测试证明它对"。这正是本仓一贯的纪律（D-321：预测某突变会存活再去验，比事后
发现好；本条是"预测这条路径没被测到"，验证方式是通读测试文件确认零命中）。

---

## ② 行数守恒——测了非正常路径，且有代码级断言兜底

**主张的不变量**：`len(quick) + len(forensic) + len(rejected) == len(records)`（不含
`malformed` 行——那些"从未成为一条记录"，在 `load_records()` 层面就被过滤，不进入这个
等式，文档 docstring 与实现口径一致）。

**不止测了"正常混合批次"**：
- `test_quick_forensic_rejected_counts_conserve_the_input_row_count`——3 quick + 2
  forensic + 1 missing + 1 other，混合批次，守恒式显式断言。
- `test_conservation_holds_for_an_all_rejected_batch`——**全批次都不合规**（missing/
  bogus/empty 各一条），守恒式**仍然**显式断言。这正是大脑担心的"是不是只测了正常路径"
  ——答案是没有，这条边界情形（极端到"零条记录进任何一个合法桶"）被专门覆盖了。

**额外的一层防护，测试之外**：`main()` 里守恒式本身还写成一条**运行时 `assert`**
（:94），不是只活在测试里——真实运行中如果这条不变量被打破（比如未来有人改坏
`split_records()` 的分支逻辑），工具会当场崩溃报错，而不是悄悄写出行数不对的两份文件。
CLI 端到端测试（`test_cli_round_trip_writes_two_files_with_the_right_counts`）没有再重复
断言这条公式，但因为生产代码自己有这层断言，CLI 测试若真的触发了守恒被破坏的场景，
测试本身会因为 `main()` 抛异常而失败——**不是覆盖缺口，是合理的不重复**（守恒式在纯函数
层测得很扎实，CLI 层的职责是测 I/O 往返，两层各司其职）。

**结论：这条判据测得比较到位，且有代码级兜底，未发现问题。**

---

## ③ 未知 mode 值——处置与文档声称逐条对得上，两处引用出处也核实存在

| 情形 | 测试 | 结果 |
|---|---|---|
| 大小写变体（`"Quick"`） | `test_case_mismatch_is_other_mode_not_silently_normalized` | 落 `other_mode`，不做归一化猜测 |
| 空串 | 见 §1 | 落 `missing_mode`（不是 `other_mode`——这是刻意的口径，理由已在 §1 引用） |
| `run` 键整缺 | **无测试**（见 §1 的缺口） | 代码读出来对，缺一条测试 |
| 非字符串（如 `0`） | `test_non_string_mode_is_other_mode_not_a_crash` | 落 `other_mode`，不抛异常，原值带出 |
| `continuity`/`ab`（真实合法值，schema 描述没写全） | `test_continuity_and_ab_modes_are_other_mode_not_a_data_error` | 落 `other_mode`，且测试原话说明"这是正确行为，不是数据错误" |
| 普通未知字符串（`"chaos"`） | `test_other_mode_value_is_rejected_and_the_value_is_recorded` | 落 `other_mode`，原始值留痕 |

**两处引用出处逐字核实，均真实存在，不是编出来的引用**：
- `MainActivity.kt:78`——原文 `am start ... [--es mode quick|forensic|continuity|ab]`，
  与 docstring 的转述逐字一致（含四个合法值的顺序）。
- `spec/schemas/result-run.schema.json:25/29`——`run.required` 数组第 25 行确含
  `"mode"`；第 29 行 `mode` 字段的 `description` 确为 `"quick / forensic"`，
  与 docstring"schema description 逐字 'quick / forensic'"的说法逐字对得上。

**结论：③ 项处置与文档声称一致，未发现分歧。**

---

## 总体判断

三个重点里，②③ 未发现问题；①（连带"run 键整缺"这个 ③ 关心的子情形）找到**一处
真实的测试覆盖缺口**——代码本身是对的，缺的是一条测试把"读代码认为它对"变成
"有反例证明它对"。这个缺口不阻塞工具投入使用（默认调用路径不会触发它），但建议在
下一次改动这个工具时补上，避免以后有人改坏 `run_obj()`/`split_records()` 的这条路径
而没有任何东西会红。

---

*本复核仅使用 Read 工具完成，未跑 pytest、未验证测试当前是否真的全部通过（该动作需要
shell，此刻不可用）——本备忘只能确认"测试写了什么、测了什么、没测什么"，不能确认
"测试跑起来是否真的通过"，如实标注这层边界。落盘后由大脑或 v3 带入提交。*
