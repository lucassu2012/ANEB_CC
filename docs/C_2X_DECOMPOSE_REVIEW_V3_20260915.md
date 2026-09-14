# 2× 分解判据 v3 · 大脑终审裁定（2026-09-15；对象 `b225b7c8`）

> 六面复审（内部一致性／脚本对判据／仪器侧取法／世界枚举／证据诚实／可跑性）→ 归并 27 → 送复核 14 → 每条三视角，另混两条盲对照。
> ⚠ **面板作废，原因是没跑完不是跑错**：用量上限在复核阶段截断，两条盲对照与 go/no-go 共 20 个代理未返回。票无区分力。
> **替代**：大脑对三条最重的 HIGH 亲手复现（§1），并以 K1–K13、X1–X15 已知项（两天前逐条核实）补全。
> 本文件由脚本从 journal 生成，代理文本未经转述，只做两处机械归一（代码行号改锚文字；代理写的节号加「判据」前缀，本文自身小节为 §0–§8）。

## §0 结论

**verdict：`no_go`。不开窗，PO 单子不发。**

三条足以各自单独否决：①T 在本机所有 PC 打的格取不到，判定层整段静默——**整窗白烧且离线一分钟可复现**；②FORWARD 格的 H2／impostor／N 拿 NETWORK 格 A1 的判词与 T 做前提——D-885 明令禁止的跨层外推，结论随传错的那个码反转；③`verdict_h2` 三个设备侧 T 全缺席时 `None==None` 放行——获取坏了看到的是「前提已满足」。

另两条无论面板：K12 前提门四读数全对「流量是否真过得去」盲且同源；X1 判据写「`finally` 调 `teardown()`」而探针里没有这个函数。

## §1 大脑亲复现（2026-09-15，本机）

| 发现 | 复现 |
|---|---|
| `run()` 第 117 行 `encoding="utf-8"` vs `ping.exe` | 本机 ACP=cp936；`ping -n 1 127.0.0.1` 首字节 `\r\n\xd5\xfd\xd4\xda`（「正在」）；utf-8 解码得 **78 个 U+FFFD**；cp936 解码才含「已发送」 ⇒ `_sent_count`→None ⇒ 第 630 行 early return |
| H2 用 A1 的判词 | 第 645 行 `verdict_h2(T,…,code)`，`code` 来自 A1；C1 的 `cc` 第 640 行算完只印。实调：同读数 `code='TWICE'`→`H2_HOLDS`，`'DIFFERENT'`→`UNDECIDABLE_IDENTITY` |
| `None==None` | 实调 `verdict_h2(20,20,20,40,None,None,None,'TWICE')` → **`H2_HOLDS`** |

## §2 存活（复核 3 票中否决少于半数）

1. **[high] T 在本机对所有 PC 打的格取不到：ping.exe 输出 cp936、run() 按 UTF-8 解码 ⇒ _sent_count 恒 None ⇒ 判定层整段静默（烧窗，离线一分钟可复现）**（0/3 refuted）
   - 主张：decompose_2x_probe.run()（113-121）写死 encoding="utf-8"；pc_ping()（471-477）把 ping.exe 的 stdout 经它解码后喂 _sent_count，正则只认「Sent =」/「已发送 =」。本机实测：GetACP/GetOEMCP=936，`ping.exe` 裸 stdout 以 b'\r\n\xd3\xc3\xb7\xa8'（cp936「用法」）开头，UTF-8 解码得 393 个 U+FFFD；把「数据包: 已发送 = 20，…」按 cp936 编码再走同一路径 ⇒ '????? = 20' ⇒ _sent_count → None，tail 过滤（474 行找「已发送」）也不中 ⇒ 印「（无摘要行）⇒ T=None」。于是 S3a/S3b/A1/A2/A-off 五格 T=None；apply_verdicts 第 630-632 行因 A1 的 T 为 None 直接 return，S3、C1 身份、H2、impostor、N、底噪一行都不印。七份烟测全在 err=5 处止步，从未到达 pc_ping；test_sent_count_reads_three_locales（probe_pure 99-107）喂的是已解码 str，bytes→str 这一跳没有门。设备侧 adb ping 输出英文「packets transmitted」不受影响，PowerShell 读数全是 ASCII 也不受影响——只有 ping.exe 这一条通道坏。
   - 位置：scripts/diag/decompose_2x_probe.py（run）、453-477（PING_SENT_WIN/_sent_count/pc_ping）、630-632（early return）；scripts/tests/test_decompose_2x_probe_pure.py
   - 失败情景：PO 提权开窗，12 个句柄全开成、每格计数都印出来了；每个 PC 格印「PC 侧 ping 自述：（无摘要行）⇒ T=None」；判定块只有一行「判据 §4.1 A1：读数或 T 取不到 ⇒ 全部不可判」，S3 VOID_NO_T、判据 §4.2/4.3/4.5/4.6 全不印、A-off 闸一无从判。整窗白烧，且原因在无设备无提权下一分钟就能复现。
   - 修法：run() 改为 capture bytes 后按 locale.getpreferredencoding(False)（cp936）或显式 OEM 代码页解码（至少对 ping.exe），并印出所用解码器；加一条门：把中文摘要行按 cp936 编码成 bytes 推过真实解码路径断言得 20；preflight 在开任何句柄前做 T 量法活性对照（`ping.exe -n 1 127.0.0.1` 须 _sent_count==1，否则 SystemExit NOT_EXECUTED），与 S0 给计数的活性证明同级。

2. **[high] A2 的「计数」只数能解析成 ICMP 的包 ⇒ 判据 §4.1 第 5/6 行永远够不到 NO_2X_BACKGROUND，真实背景世界被印成「原 A=40 连原 filter 都不复现，本轮前提消失」**（0/3 refuted）
   - 主张：判据 §3 A2 行与 判据 §4.6 末句把 A2 定义为去掉 `and icmp` 后的匹配总数（A2−A1＝背景非 ICMP 贡献），判据 §4.1 第 5/6 行按「A2 计数 ∈ [2T−2,2T]」vs「∈ [T−2,T]」分支。脚本 _reader（288-292）对 pkt_parse 返回 None 的包只 append 进 unparsed，pkt_identity.parse 第 39-40 行对 protocol != 1 一律 None；cell() 第 363 行 count=len(recs)；apply_verdicts 第 634 行把这个 ICMP-only 的 a2['count'] 喂 verdict_identity。实算：verdict_identity(20,20,{1:20},a2_count=20) → NO_2X_NOT_REPRODUCED；同读数 a2_count=40 → NO_2X_BACKGROUND。A2−A1 在结构上恒≈0，unparsed 只在 report_cell 425 行印一句「⚠ 未解析 N 条」，无判词消费它。
   - 位置：scripts/diag/decompose_2x_probe.py、363、634-638；scripts/diag/pkt_identity.py；evidence/c_2x_decompose_20260912/CRITERIA_PREREG.md、291-292、519-521
   - 失败情景：MECHANISM_SWEEP 判据 §2 第 53 行实测过一条到 223.5.5.5:443 的 TCP 流。若原 A=40 是 20 ICMP＋20 TCP：A1 去重 20 重数 1（对）；A2 看见 20 ICMP＋20 TCP 但 count=20 ⇒ 判词印「NO_2X_NOT_REPRODUCED：原 A=40 连原 filter 都不复现 ⇒ 本轮前提消失，H1/H2/H4 全部不可判」——而 40 恰恰复现了。预登记的正确行（改写 A=40 含义）不可达；「未解析 20 条」那行在两屏之前，无人消费。自信的错结论进证据、整轮分解据此关闭。
   - 修法：给每格加 count_all=len(recs)+len(unparsed)；A2 以 count_all 喂 verdict_identity 并在判词行并印「匹配总数／ICMP／非 ICMP」三个数；判据 §4.1 第 5/6 行与 判据 §4.6 末句明写「A2 计数＝该格 filter 匹配总数（含未解析）」；合成门：A1 去重 T 重数 1、A2 20 recs＋20 unparsed ⇒ 必须 NO_2X_BACKGROUND 而非 NO_2X_NOT_REPRODUCED。

3. **[high] 判据 §4.2 H2、判据 §4.3 C1-impostor、判据 §4.5 N 全部拿 A1（NETWORK、PC 打）的身份判词与 T 做前提，而不是被判的 FORWARD 格自己的——D-885 明令禁止的跨层外推，C1 的判词算出后被丢弃**（0/3 refuted）
   - 主张：apply_verdicts 第 633 行 T=a1['T']，635-637 行 code 取自 A1；640-642 行算出 C1 的 cc 只印不用；645-646 行 verdict_h2(T, …, code)、668-670 行对 nm∈('A1','C1') 一律传 code、679 行 verdict_n(T, …) 用 PC 侧 T 做设备侧两格的区间基。verdict_h2 内 in_t 用这个 T，(c) 只核 T_F1==T_F2==T_C1 从不核它等于 T。判据 §4.2 首行（341）与 判据 §4.3 条件句（398）写「判据 §4.1 须判为呈现两次」但没点名哪一格；对 FORWARD 层的 H2/C1′ 相关的只能是 C1 的判词。实算：verdict_h2(20,20,20,40,20,20,20,'TWICE') → H2_HOLDS 与 C1 判什么无关，同读数 'DIFFERENT' → UNDECIDABLE_IDENTITY；verdict_impostor(20,40,True,True,'TWICE') → IN_BAND vs 'DIFFERENT' → UNDECIDABLE_PREMISE；verdict_h2(T=20,15,15,30,15,15,15,'TWICE') → UNDECIDABLE 而 T=15 → H2_HOLDS。
   - 位置：scripts/diag/decompose_2x_probe.py、665-670、676-679；scripts/diag/decompose_2x_verdicts.py、147-182、209-231；CRITERIA_PREREG.md、398、485-486
   - 失败情景：A1（NETWORK）{2:20} ⇒ TWICE；C1（FORWARD）40 个互异键 {1:40} ⇒ DIFFERENT（两个群体）；F1=F2=20。stdout 相邻两行：「判据 §4.1 身份（C1）⇒ DIFFERENT」与「判据 §4.2 H2 ⇒ H2_HOLDS：… 且 判据 §4.1 判 TWICE ⇒ H2 成立(每接口各一次)」——判据第 341 行自己写这时本支不成立；C1 impostor 同样印 IN_BAND。镜像方向：A1 非 TWICE 而 C1 TWICE ⇒ FORWARD 层真实读数被 UNDECIDABLE_* 压掉。另：设备 ping 只发 18 而 PC 发 20 时 N1=N2=17 落 A1 的 [18,20] 外判 UNDECIDABLE，按各自 T 本在带内。33 条门无一条区分 A1 判词与 C1 判词。
   - 修法：verdict_h2 与 C1 的 verdict_impostor 传 cc 与 c1['T']；verdict_n 传 n1['T']/n2['T'] 并要求相等；A1 的 code 只给 A1 的 impostor 与 verdict_h4。判据 §4.2/判据 §4.3/判据 §4.5 写明各消费哪一格的 判据 §4.1 与哪一格的 T。加门：同一 F/C 读数、A1=TWICE 且 C1=DIFFERENT ⇒ H2 不得为 H2_HOLDS、C1 impostor 须 UNDECIDABLE_PREMISE。

4. **[high] verdict_h2 的 T 相等前提在缺席时 fail-open：三个 FORWARD T 全为 None 时 None==None==None 成立，照用 A1 的 T 印 H2_HOLDS**（0/3 refuted）
   - 主张：decompose_2x_verdicts.verdict_h2 第 102 行 `if not (T_F1 == T_F2 == T_C1)` 只拦不等，不拦缺席；随后 in_t 用的是另传入的 T（A1 的）。apply_verdicts 第 644 行只对三个 count 查 None，不查三个 T。实算：verdict_h2(20,20,20,40,None,None,None,'TWICE') → H2_HOLDS；(…,20,19,20,…) → VOID_T_MISMATCH。test_h2_t_mismatch_is_void_not_a_reading（test 第 100 行）只覆盖真不等，不覆盖缺席。孪生规则：获取坏了（adb 摘要行没解析出来）看到的是「前提已满足」。
   - 位置：scripts/diag/decompose_2x_verdicts.py、119；scripts/diag/decompose_2x_probe.py；scripts/tests/test_decompose_2x_verdicts.py
   - 失败情景：三个设备格的 adb ping 被 180 s 超时截断或摘要行格式不中 ⇒ 每格印「设备侧 ping 自述：（无 summary 行）⇒ T=None」，计数是真的（F1=20 F2=20 C1=40）。判定块印「判据 §4.2 H2 ⇒ H2_HOLDS：F1=20 F2=20 各 ∈ [18,20] 且 判据 §4.1 判 TWICE」，区间来自 PC ping 的 T=20，页面上没有一行说设备发包数从未取得。
   - 修法：verdict_h2 在相等检查前加 `if None in (T_F1,T_F2,T_C1): return ('VOID_NO_T', …)`，区间用 T_C1；apply_verdicts 对 f1/f2/c1 任一 T 缺席印拒判；门加全 None、单 None 两例断言 != H2_HOLDS，加「FORWARD T 与 A1 T 不同时区间须随 FORWARD T」。

5. **[high] 格级 NOT_EXECUTED／VOID／底噪处置全部只印不消费：zero_reading_ok 的布尔被丢、thread_exited(_b) 不进判定、void_constants 无人读、S0 不设门、noise_policy 排在所有判词之后且 1–2 从不减、S1 count=0 放行整层**（0/3 refuted）
   - 主张：report_cell 第 420 行 `ok0, why0 = zero_reading_ok(...)`，ok0 全文件未再使用；apply_verdicts（624-686）取数只看 `count is not None`（644、667、677、683），从不看 thread_exited/thread_exited_b/void_constants/ok0；`c['void_constants']=True`（610）全文件仅此一处出现；S0 格未被 apply_verdicts 读取；noise_policy 在 681-685 行印在 判据 §4.1/4.2/1.6/4.3/4.5 判词之后，NOISE_TOO_HIGH 不压制任何判词、NOISE_SUBTRACT 从不减、减前/减后两个数从不印；count_b（impostor 分子，判据 §1.1-6 明列）不经 zero rule 直接进 verdict_impostor ⇒ verdict_impostor(0,40,True,True,'TWICE') → ZERO。判据 §1.1-5/判据 §1.1-6/判据 §2-6/判据 §4.6 把这些写成判定前提，脚本把它们写成旁白。
   - 位置：scripts/diag/decompose_2x_probe.py、363-364、420-434、604-610、624-686；scripts/diag/decompose_2x_verdicts.py、234-255；CRITERIA_PREREG.md、58、66、69-71、252、504-512
   - 失败情景：F2 读线程 join 5 s 未退出、count=0：格块印「⚠ 读线程 a 未退出 ⇒ 不 Close，记 NOT_EXECUTED」与「零读数通则：… 该格 NOT_EXECUTED」，几行后 判据 §4.2 印「DEGENERATE_UPSTREAM_ONLY：F1≈C1 而 F2=0 ⇒ 在『H2 不成立』与『转发层只暴露上游腿』之间歧义」——仪器故障被改写成 ifIdx 语义问题并被带走。S2=5：先印 H2_HOLDS/H1_FORM，末尾才印「NOISE_TOO_HIGH ⇒ 同层各格 NOT_EXECUTED」，同一逐字副本两条互斥判词，被抄走的是前一条。C1′ 读线程 b 挂死 count_b=0 ⇒ 「判据 §4.3 ⇒ ZERO：该位在本路径未观测到置位」。
   - 修法：每格算一个 status ∈ {OK, NOT_EXECUTED, VOID}（由 count is None、thread_exited/_b、zero_reading_ok(count,…)/zero_reading_ok(count_b,…)、void_constants、same_window 合成，抽成纯函数配门）；apply_verdicts 先算 S0 门与每层 noise_policy，S0 不过印 ROUND_VOID 停；NOISE_TOO_HIGH ⇒ 该层判词一律印 GATED_BY_NOISE；NOISE_SUBTRACT ⇒ 减后再判并印减前/减后；任一输入格 status≠OK ⇒ 该判词印拒判与原因（verdict_impostor 走 VOID_MISSING）。门：合成 cells 里 S1 count=0 thread_exited=False ⇒ 判据 §4.6 行不得出现 NOISE_NONE；F2 未退出 ⇒ 判据 §4.2 不得出现 DEGENERATE_*。

6. **[high] 零读数通则的判别量是常量：shutting_down 在 cell() 的 finally 里无条件置 True、读线程从不采样它 ⇒ 「读线程开跑即死」与「真零」在所有被判字段上逐字相同**（0/3 refuted）
   - 主张：判据 §1.1-1/2 要求读线程在 Recv 失败处把错误码「与 shutting_down 一起返回」，用失败瞬间观察到的旗标分开「开跑就死」与「收尾时退出」。脚本 _reader（282-293）不接收也不采样任何旗标；cell() 第 344 行在 finally 里先 `out['shutting_down']=True` 再 Shutdown，report_cell 事后读这个字段 ⇒ 判定时恒 True，唯一活的输入是 thread_exited，而线程在开跑就死时同样已退出。实算 zero_reading_ok(0,True,True) → (True,「这个 0 成立」)。term_err 按 判据 §1.1-4 只印不判。这条规则要分开的两个世界（仪器没跑 vs 真的是 0）读数相同——D-901 形状的判别器长在零读数通则本身上。
   - 位置：scripts/diag/decompose_2x_probe.py、337-349、420；scripts/diag/decompose_2x_verdicts.py；CRITERIA_PREREG.md、69-77
   - 失败情景：S1 或 F2 的读线程第一次 WinDivertRecv 立即返回 FALSE（该层/该 filter 的意外错误），线程带 count=0 退出，比流量早 20 s；finally 置 shutting_down=True、join 立即成功、thread_exited=True；报告印「count=0 shutting_down=True 线程已退出=True」「零读数通则：这个 0 成立」。S1=0 ⇒ NOISE_NONE 放行整个 NETWORK 层；F2=0 进 verdict_h2。房规「零必须与仪器没跑可分」在纸面上由一个不可能失败的检查满足。
   - 修法：给 _reader 一个 threading.Event（主线程在 Shutdown 前 set），Recv 返回 FALSE 的瞬间记录 (get_last_error(), evt.is_set(), time.time())；cell 的 shutting_down 取读线程观察到的那个值，并派生 exited_before_traffic=(t_exit < t_traffic_start)；对句柄 b 同样做并把结果送 verdict_impostor（不满足 ⇒ VOID_MISSING）；门：t_exit 早于 traffic_start ⇒ NOT_EXECUTED。

7. **[high] A-off——本窗唯一要 PO 动手买的格——没有可执行入口：a_off_stage 需要已退出进程里的 DLL 句柄与常量，__main__ 不调它、tee 已关、重跑 preflight() 会因热点已关而 SystemExit；且 判据 §5-1「前后各印一次」只印了前、判据 §5-5 设备三态在本格根本不读**（0/3 refuted）
   - 主张：__main__（718-735）只调 main() 与 apply_verdicts()，末行印「跑法：拿本轮 判据 §4.1 的判词调 a_off_stage()」。a_off_stage(d, cells, identity_code, up_addr, up_ifidx, fb)（689）的六个入参全是 main() 局部量，main() 只返回 (cells, pre, opened_any)（611），进程退出即消失；__main__ 的 finally（730-735）已关 tee。唯一能取得 d/k 的 preflight() 在 524-528 行对 dc != 'ON_HOTSPOT' 直接 raise SystemExit ⇒ 热点一关，主入口必拒跑，A-off 永远无法在「热点已关」状态下合法取得输入。a_off_stage 内 hotspot_readings 只在 702 行（格前）调一次，判据 §5-1（540）要求「前后各印一次」；device_egress() 全文件只在 preflight 522 行调用，判据 §5-5（578-579）的三态旁证在本格缺席。判据 §5 与 判据 §4.4 以「该格会跑」为前提，脚本侧无人达成（D-886 形状）。
   - 位置：scripts/diag/decompose_2x_probe.py、571-611、689-715、718-735；CRITERIA_PREREG.md、578-581
   - 失败情景：12 格跑完、判据 §4.1 印 TWICE，PO 关热点。没有命令可跑：操作者在提权 REPL 手写 d=load()、手敲 up_addr/up_ifidx（违反 判据 §0-3 常量不写死）、手打 identity_code='TWICE'；输出只在控制台（D-890 判为旁证）、无 SHA/HEAD 行、无 finally、新进程 pre_state=0 ⇒ 将来任何 teardown 拒清。热点在 20 个 ping 中途被 Windows 静默重开或从未真关——只有格前读数，格后没有任何一行能暴露 ⇒ A-off 重数 2 ⇒ 「DIFFERENT_CAUSE：确为不同因，H4 成立」进证据。这正是裁定 blocking #5 描述的坏结局换了个位置回来。
   - 修法：改成同进程两阶段：apply_verdicts 返回 identity 后若为 TWICE，在 tee 仍打开、同一 try/finally 内打印「请关热点，关好后按 Enter」并阻塞 input()（或 --a-off 重入：跳过 P2-pre 的 ON_HOTSPOT 拒跑、改用 判据 §5 HOTSPOT_OFF 谓词作前提、按 判据 §5-6 重推 判据 §2 常量、identity 从上一份 stdout 副本读回并逐字回显）；格前格后各调 hotspot_readings 与 device_egress 并印，任一格后非 TRUE/非 OFF_HOTSPOT ⇒ 该格 VOID；identity != TWICE 时不提示不等待（配纯函数门）。

8. **[high] 收尾从不停驱动：finally 只算标签，forward_layer_probe.teardown() 从未被 import 或调用，无 sc stop/delete ⇒ 每次成功的提权跑都以「判据 §5 FAIL：驱动未卸」结束、内核驱动留在 PO 机器上，卸载靠 PO 即兴**（0/3 refuted）
   - 主张：probe 第 241 行只 `from forward_layer_probe import driver_rc, teardown_labels`；main() 的 finally（615-621）只做 rc=driver_rc(); teardown_labels(rc, opened_any, pre) 并打印；grep `teardown(`、`sc.exe`、`stop`、`delete` 在 probe 内零调用。forward_layer_probe.teardown()（264-316）已实现 pre_state==1060 白名单、BeanNetworkTester 忙碌检测、stop 后 1060=已自删读法，但未被复用。D-888 实证句柄关闭不触发 stop；teardown_labels 在 rc != 1060 时返回「服务仍在（判据 §5 FAIL：驱动未卸）／否（需手动 stop）」——且那个「判据 §5」是上一轮判据的节号，本轮 判据 §5 是干预。判据 §6-1 写「finally 无条件调 teardown()」、判据 §6-3 写「sc stop 是实质」：目标状态没有任何达成者（D-886 形状）。
   - 位置：scripts/diag/decompose_2x_probe.py、612-621；scripts/diag/forward_layer_probe.py；CRITERIA_PREREG.md
   - 失败情景：pre=1060、句柄开成、12 格跑完：末尾印「sc query WinDivert rc=0 ⇒ 服务仍在（判据 §5 FAIL：驱动未卸）」「否（需手动 stop）」；PO 单上没有下一步，PO 要么在 Git Bash 里读到 $?=36 误判（D-891）要么忘记，驱动留在机器上——D-884/D-886 已发生过一次。若 PO 先关热点再起第二个进程跑 A-off，那个进程 pre_state=0 ⇒ 即使日后接上 teardown 也会以「不是本轮装的」拒停，归属在两进程间断裂。
   - 修法：main() 的 finally 改调 forward_layer_probe.teardown(opened_any, pre)（它已带 判据 §6-2/判据 §6-3 全部逻辑与 7 条门），把 stop/delete 的 returncode 印成文本进逐字副本；teardown_labels 的「判据 §5」节号由调用方传入或删去；加纯函数门断言 pre is not None 时 finally 路径调用 teardown；末尾印期望终态（rc=1060）使其缺席可见。若坚持由人清，则 判据 §6 与 PO 单必须写清命令、判据（sc.exe query 文本含 1060）与「在 PowerShell 不在 bash 里读」。

9. **[high] 判据 §4.1 第一行按 SrcAddr 拆两支「不得并成一行」没有任何判定路径：verdict_identity 无 src 入参、只出单一 TWICE 并印「同一数据报被呈现两次」，src_same_within_key 只在汇总行并印、除 判据 §4.5 外无人消费；下游 H2/impostor/H4 全按字符串 'TWICE' 键控**（0/2 refuted）
   - 主张：判据 295-300 行要求 TWICE 按 SrcAddr 拆「同一点被呈现两次」与「同一数据报在两点各一次（H1 形态）」，142-143 行称做成 summarize() 返回字段就「不可能只挂在判定表的一行下」。verdict_identity(T, n_distinct, hist, a2_count=None)（verdicts 32-74）无 src 参数，返回单码 TWICE，说明文字即同点世界的措辞；apply_verdicts 635-642 行调用处虽有 a1['summary']['src_same_within_key'] 可用却不传；该字段只在 report_cell 428-430 行与其他字段并印，只在 verdict_n（679）被 判据 §4.5 用到。verdict_h2/verdict_impostor/verdict_h4 全以 identity_code == 'TWICE' 为前提，不区分拆支。test_pkt_identity.test_src_split_distinguishes_two_worlds 只钉 summarize 字段，33 条判定门无一条要求两个码。这是 v1 blocking #2／v2 no-go #2 的判词半边，作者称已闭合，实际只闭合了记录侧。
   - 位置：scripts/diag/decompose_2x_verdicts.py；scripts/diag/decompose_2x_probe.py、635-642；CRITERIA_PREREG.md、295-300
   - 失败情景：C1 去重 20、{2:20}、src_same_within_key=False（NAT 前后各一次，H1 形态，divert 下不会延迟翻倍）。判词行印「判据 §4.1 身份（C1）⇒ TWICE：… ⇒ 同一数据报被呈现两次」——判据为同点 clone+reinject 世界保留的措辞、页首点名对整形器含义相反；被抄进 DECISION_LOG 与整形器设计的是这一行，src 字段在另一行没人引用。H2/impostor 各支以 TWICE 为前提照常展开。
   - 修法：verdict_identity 增必填参 src_same_within_key，TWICE 拆为 TWICE_SAME_POINT／TWICE_TWO_POINTS（None ⇒ TWICE_SRC_UNKNOWN 不可单判），说明文字由该值算出；apply_verdicts 对 A1、C1 都传 summary['src_same_within_key']；判据 §4.2 首支、判据 §4.3 条件句、判据 §4.4 前提写明接受哪一个（或两个）码；门：同去重同重数仅 src 标志不同 ⇒ 码必须不同。

10. **[high] 判据 §2「每个 FORWARD 格前后各做、双侧必须同意」退化为单侧：设备 src 只在 preflight 读一次，格后复核拿缓存 src 对 Permanent 邻居表——正是判据自己点名的假绿形态；判据 §2-6 不一致检查只比 hot_ifidx，C1 之前无格前检查**（0/2 refuted）
   - 主张：device_egress() 全文件只在 preflight 第 522 行调用一次；main() 604-610 行每个 FORWARD 格后调 derive_constants()（PC 侧）后 constants_verdict(k2, dsrc) 用的是 T0 的 dsrc；判据 §2 第 238-240 行自述「ICS 把邻居项钉成 Permanent，它不会因为设备离开而消失 ⇒ 邻居项仍在单独用就是假绿」；判据 §2-6 比较只有 `k2.get('hot_ifidx') != k.get('hot_ifidx')`，up_ifidx/up_addr/nb_kept/设备 src 不比。C1 的最近一次前置检查是 S2 的格后复核，中间隔 S3a/S3b/A1/A2 四格（约 90 s）。D-880（判据引用）已裁「随动作变化的量前提只查一次等于没查那段时间」并记录设备离网实际发生。
   - 位置：scripts/diag/decompose_2x_probe.py、597-610；CRITERIA_PREREG.md
   - 失败情景：P40 在 A1/A2 期间漫游到别的 WiFi/蜂窝（判据自述 09-12 发生过两次）。adb ping 照发 20（T=20）经别的网络，C1/F1/F2/N1/N2 全读 0 且 shutting_down=True、线程已退出（零通则放行）；每格「判据 §2 格后复核」照绿（Permanent 邻居项仍含缓存 src）。判词印「判据 §4.1 C1 ⇒ LOSS」「判据 §4.2 ⇒ DEGENERATE_BOTH_ZERO：指向仪器：ifIdx 语义或该 filter 增量本身不匹配」「判据 §4.5 ⇒ UNDECIDABLE_N2_ZERO」——五个 FORWARD 格烧掉，证据把真因（设备离开）写成 ifIdx 语义问题，下一轮去查错的东西。
   - 修法：每个 FORWARD 格前后各调 device_egress()，要求 ON_HOTSPOT 且 src 与 preflight 相同，否则该格 VOID（由 apply_verdicts 消费，见格级状态那条）并印「设备侧出口已变」；判据 §2-6 比较扩到 (hot_ifidx, up_ifidx, up_addr, nb_kept, 设备 src) 且与上一次读数比而非只与初始比；dev_ping 里 transmitted−received==T 时另印一行「设备侧全丢，先疑出口」。

11. **[medium] 判据 §1.2「每包一行进逐字副本」从未写出：recs/recs_b 只在内存里汇总后丢弃，判据 §4.1 解耦规则与所有「不可单判 ⇒ 事后按每包日志查询」行没有可查的产物**（0/1 refuted）
   - 主张：判据 §1.2 第 104 行「逐行进 stdout 逐字副本（不只印汇总）」，判据 §4.1 第 302-304 行（blocking #4 解耦）「构成一律按 判据 §1.2 的每包日志事后查询」，判据 §4.2 第 350 行要求印未落桶的目击数。report_cell（414-435）只印 count、去重、重数分布、distinct_seq、seq 极值、src 组内一致；全文件对 c['recs'] 的逐条访问只有 655-656 行为 S3 取 seq 列表；无任何逐包打印。probe 第 8 行 docstring 自称做「每包日志」，实际没有。
   - 位置：scripts/diag/decompose_2x_probe.py、414-435、655-656；CRITERIA_PREREG.md、302-304、350
   - 失败情景：A1 去重 21、{2:19,1:2} ⇒ UNDECIDABLE「如实记」。判据说构成随后从每包日志读——日志不存在，原始目击已在进程内丢弃；该格结论只能靠再开一个提权窗。同样适用于 H2 UNDECIDABLE「如实记三个数」、CONS_UNDERCOUNT「印出未落桶的目击数」、S3 配对差异的定位、TTL 差、未解析包的协议构成。
   - 修法：report_cell（或 cell 返回后）对两个句柄各印一行每记录：`<格> <句柄> seq ip_id recv_len src dst ttl type id`，以格标签前缀便于 grep；unparsed 逐条印长度与协议号。每轮 ≤ 数百行，代价可忽略。

## §3 被否

（无）

## §4 送复核但票未返回（用量上限）——按未核处理，不算被否

1. **[medium] verdict_s3 单位混用（活性/偏移数目击列表长度、配对数 seq 集合）且 SKEW=2 按「包」推导却按「目击」比较；句柄 b 打不开时空 recs_b 照送 verdict_s3 ⇒ 读成 W2「配对法不成立」而非 VOID**
   - 主张：判据 §1.6（197-199）三条件都写在 ｜seq(A)｜、｜seq(B)｜、｜seq(A)∩seq(B)｜ 上（集合势），SKEW=2 的推导是「open/shutdown 不同瞬 ⇒ 开头结尾各差一个包」。实现 verdict_s3 第 348 行 na,nb=len(seqs_a),len(seqs_b)（apply_verdicts 655-656 行传入含重复的列表），349 行交集用 set。在本实验预设的 2× 世界里每包两次目击，一个包的差=2 个目击。实算 verdict_s3(20,twice,twice[:-3]) → FAIL_SKEW、twice[2:-2] → FAIL_SKEW。cell() 323-327 行 hb 打开失败只印一句置 hb=None、recs_b 留空；apply_verdicts 654-657 行只要 count 非 None 就送 verdict_s3 ⇒ nb=0 ⇒ FAIL_SKEW「两句柄看见的数量差太多（W2）⇒ 配对法不成立」——获取失败被写成驱动语义（孪生规则）。门只用无重复的 FULL=range(1,21)，两者都看不见。
   - 位置：scripts/diag/decompose_2x_verdicts.py；scripts/diag/decompose_2x_probe.py、650-662；scripts/tests/test_decompose_2x_verdicts.py；CRITERIA_PREREG.md
   - 失败情景：S3a 句柄 a 40 个目击、句柄 b 37（晚开几 ms 漏掉首包两次目击＋一次丢失）⇒ FAIL_SKEW ⇒ s3_code FAIL ⇒ A1/C1 两格 impostor 全 VOID_S3，本轮 判据 §4.3 烧掉，且证据里记下「同层两个 SNIFF 句柄看不到同一个包」——这句会被抄进整形器设计（它恰恰否定配对法基础），真相只是偏移/一次 open 失败。
   - 修法：na,nb 取 len(set(...))（或由调用方传 distinct seq），三条件同用判据的单位；门加含重复 seq（2× 世界）且 b 缺 3–4 个目击须 PASS 的用例；cell() 记录 hb_open_err，apply_verdicts 对其非 None 的格印 VOID_HANDLE_B 而非送 verdict_s3；门：recs_b 空且 hb_open_err 非 None ⇒ 码不得为 FAIL_*。

2. **[medium] S3 第三条件（seq 交集）在 TWICE 世界里分不开 W1（复制）与 W4（目击被两句柄各分一半）：两个目击共享同一 seq ⇒ 两世界都 PASS；判据 W4 行的「交集≈0」算的是另一个世界，门夹具用互异 seq 模的是 DIFFERENT 世界**
   - 主张：判据 §1.6 表（185-190）写 W4「H_A≈T, H_B≈T, seq 交集≈0」并称「W4 唯由配对条件排除」。但本实验预设的世界里同一数据报的两次目击 icmp_seq 相同：按目击切分（每 seq 第 1 次到 a、第 2 次到 b）⇒ seq(A)=seq(B)={1..T}。实算 verdict_s3(20,FULL,FULL) → PASS（切分世界）、verdict_s3(20,twice,twice) → PASS（复制世界）。test_s3_four_worlds_get_four_distinct_codes（298-316）用 [x+100 for x in FULL] 模 W4——那是 2T 个不同包，不是 W4。判据自述 SNIFF 复制语义「本方从未测过」，故该子世界不能被文档义排除；D-901：两个世界读数相同就不是判别器。另：n 显著偏离 2T 的守卫（判据 419 行）无实现、无区间，apply_verdicts 671-675 只印 n 与带。
   - 位置：CRITERIA_PREREG.md、419；scripts/diag/decompose_2x_verdicts.py；scripts/tests/test_decompose_2x_verdicts.py；scripts/diag/decompose_2x_probe.py
   - 失败情景：若驱动把每个目击只交给两个相同 SNIFF 句柄之一：S3a/S3b PASS（na=nb=20、交集 20）；A1 句柄 a 每包只见一次 ⇒ 去重 20 重数 1；A2 单句柄见 40 ⇒ verdict_identity → NO_2X_BACKGROUND「原 A=40 ≈ T 个 ICMP ＋ 背景非 ICMP」——40 全是 ICMP 的 2× 被写成背景；n≈T 而非 2T 无人核。文档记下「配对法已自证」而它声称排除的世界与接受的世界读数相同。
   - 修法：S3 加第四条合取：句柄 a 的目击数须与同层单句柄格（A2 减非 ICMP，或加一支 S3-0 单句柄对照）在 ±2 内一致（「开第二个句柄不改变句柄 a 的计数」），或按 seq 比较两句柄重数 ｜mult_a−mult_b｜≤1；判据 W4 拆成 W4a（按 seq 切分）与 W4b（按目击切分）各算读数；门夹具改为 seqs_a==seqs_b==[1..20]、各半记录、断言不得 PASS；第 419 行改为「n ∉ [2T−4, 2T] ⇒ 本节 VOID_N_PREMISE」并实现。

3. **[medium] 空闲对照窗长 IDLE_SLEEP_S=20 是名义常量、无推导，对目标格约 21–22 s 只留不到一秒余量，noise_policy 用严格 <，且只与 A1/C1 比而非「同层最长目标格」；S1/S2 排在目标格之前，脚本无法按实测定长**
   - 主张：probe 第 438 行 IDLE_SLEEP_S=20.0（注释自述「实际由 noise_policy 判」），S 窗=20+GRACE 2=22.0 s；目标格窗=ping 时长+2 s，`ping -n 20 -w 1000`（472）与 `adb shell ping -c 20 -i 1`（481）约 19 s＋末包 RTT＋进程/adb 开销 ⇒ 21–22 s；每丢一个 PC 回包多等 1 s。verdicts 第 241 行 `short = s_window_s < target_window_s` 无容差；实算 noise_policy(0,22.0,22.3) → SHORT_WINDOW_NO_PASS。apply_verdicts 681-685 只配对 (S1,A1)、(S2,C1)，同层 A2/S3a/S3b、F1/F2/N1/N2 不参与「最长」。判据 §4.6-1 要求「不短于同层最长目标格」，判据 §4.6-3 短窗 ≤2「不得放行任何格」，而 S1/S2 是计划第 2、3 格，跑在所有目标格之前。20 这个数无出处。
   - 位置：scripts/diag/decompose_2x_probe.py、438、472、481、489-491、583-596、681-685；scripts/diag/decompose_2x_verdicts.py；CRITERIA_PREREG.md
   - 失败情景：C1 有 1–2 个设备回包丢失（身份仍在容差内：去重 18 ∈ [18,20]）⇒ C1 window_s 22.6–24 s > S2 的 22.0 s ⇒ 印「判据 §4.6 S2 底噪 ⇒ SHORT_WINDOW_NO_PASS：不得用来放行任何格」。按预登记 FORWARD 层 C1/F1/F2/N1/N2 无底噪放行依据，判据 §5-6 又禁止关热点后重跑 FORWARD 格；若格级状态那条修好则整层作废，不修则判据与脚本各说各话。一秒余量烧掉半个窗，可离线避免。
   - 修法：S1/S2 排到同层目标格之后，sleep=max(同层各目标格实测 window_s)+余量并印推导；或保持顺序但 IDLE_SLEEP_S 取明显覆盖最坏时长的值（N_PING×(间隔+超时)+GRACE，如 ≥42 s）并在判据写出来历；noise_policy 的 target_window_s 传同层各目标格 window_s 最大值；门：0.3 s 超出不得作废对照。

## §5 未送复核（上限 14）——按未核处理

1. **[medium] 判据 §1.5 自我标识在 git 不可用时 fail-open：run() 的 rc 被丢弃、空 porcelain 判 WORKTREE_CLEAN、HEAD 印空；「缺一件即拒跑」未实现；只哈希/查状态 probe 一个文件，承载全部判词的 verdicts.py 与 pkt_identity.py 不在其中**
   - 主张：print_self_id（442-450）`_, head, _ = run([...rev-parse...])`、`_, por, _ = run([...status --porcelain...])` 丢掉 rc；run()（113-121）异常时返回 (None, '', …)；self_id_lines 第 71 行 `dirty = bool((porcelain or '').strip())` ⇒ 空串判 CLEAN。实算 self_id_lines('abc','','')[0][0] 以「WORKTREE_CLEAN：该文件无未提交改动 ⇒ 下面那个提交哈希就是运行字节」开头而 HEAD 行为空。判据 §1.5 第 160 行「第一行印三件，缺一件即拒跑」。sha256_file 与 porcelain 只对 __file__（probe）做；decompose_2x_verdicts.py、pkt_identity.py 可以是 ` M` 而没有任何一行说出来。
   - 位置：scripts/diag/decompose_2x_probe.py、113-121、442-450；CRITERIA_PREREG.md
   - 失败情景：PO 用计划任务 /RL HIGHEST 或 PATH 无 git 的提权壳启动（提权壳常见）。首三行：WORKTREE_CLEAN、SHA256=<ok>、`git rev-parse HEAD = `（空）。事后读者信 CLEAN、解析不出字节血统——判据 §1.5 要暴露的「哈希不对应运行字节」被藏在 CLEAN 一词之下；判定层若被本地改过也无人知。
   - 修法：run() rc 非 0 或 None、或 head 非 40 位十六进制 ⇒ 第一行印 SELF_ID_UNAVAILABLE 并 SystemExit（判据「缺一件即拒跑」）；self_id_lines 增第三态并配门（porcelain 为 None/rc 非 0 时不得判 CLEAN）；对 probe、verdicts、pkt_identity 三个模块各印 SHA256 与 porcelain，任一 ` M` 即 WORKTREE_DIRTY。

2. **[medium] 判据 §1「五道门任一不过整轮作废」在脚本里不是门：pre != 1060 时印一句照跑（且行格式与 判据 §1.4 规定不同）、S0 无判词无中止；判据 §1.4「须为 rc=1060」与 判据 §6-2「pre_state==0 一律不碰、如实报人」对同一读数给出「作废」与「照跑」两种处置**
   - 主张：判据 §1 抬头（43）「五道门，任一不过整轮作废」；判据 §1.4（152-154）规定印 `-- 起跑：sc query WinDivert rc=%d ⇒ %s --` 且「那一行文本须为 rc=1060」；判据 §6-2（589-591）把 pre_state==0 当合法状态处理。脚本 preflight 542-546 行印「   跑格前 sc query WinDivert rc=%d ⇒ …」，pre≠1060 时印「服务已在 ⇒ 不是本轮装的，收尾不得归因、不得停它」并继续 load()、开句柄、数 12 格。S0（plan 584）跑完只经 report_cell 印零读数通则，apply_verdicts 不读 S0、无 SystemExit。MECHANISM_SWEEP 第 54 行实测盘上有另两份 2.2 构建（E:\tools\aneb-shaper\bin\ 与 \clumsy\）。
   - 位置：scripts/diag/decompose_2x_probe.py、584、624-632；CRITERIA_PREREG.md、58、150-154、589-591；evidence/c_2x_decompose_20260912/MECHANISM_SWEEP.md
   - 失败情景：另一会话的 clumsy/整形器已把 WinDivert 留在 RUNNING（rc=0）：脚本印「服务已在」照跑，所有 SNIFF 计数与别人的 divert 句柄同处一层（它自己的重注入会进 impostor 分子），判词照印；事后一方按 判据 §1.4 判整轮作废、另一方按 判据 §6-2 判有效。S0 在 `false` filter 上数到 3（仪器故障）：只印、不作废，后续全部判词照算照记。
   - 修法：二选一并写成同一句：判据 §1.4 与 判据 §6-2 统一为「pre≠1060 ⇒ 拒跑」并让 preflight 在 load() 前 SystemExit('NOT_EXECUTED: 起跑基线非 1060')，行格式按 判据 §1.4 原文以便 grep；或降 判据 §1.4 为「读数须印成文本、pre≠1060 时两句柄格须标『同层有他人句柄』」。S0 做成 verdict_s0(count, shutting_down, thread_exited) 纯函数配门，不过即 ROUND_VOID 并停止。

3. **[medium] 判据 §1.3 跑中结构自检（seq ∈ 1..T 且覆盖 ≥ T−2）两个模块都没实现、没有门；判据适用清单把 T=0 的 S1/S2 列入使区间为空、S3a/S3b 两边都不在；「1..T」是从发包数推出的取值域，PC 侧 ping.exe 的 seq 编码本树零实测——复审 v2 判据 §6-5（high）未闭合**
   - 主张：判据 145-148 行规定全捕获格（S1/S2/A1/A2/C1/A-off）的 seq 多重集须落 1..T 且覆盖 ≥ T−2，否则身份 NOT_EXECUTED。verdicts.py 无对应函数；report_cell 428-430 只印 distinct_seq/seq_min/seq_max；apply_verdicts 无此判。清单含 S1/S2（T=0 ⇒ 1..0 空集、≥−2 恒真）而不含 S3a/S3b。pkt_identity.parse 第 50 行按 `!H` 大端读 seq；判据 §1.2 表未规定字节序；grep DECISION_LOG 与两轮 evidence 目录 endian/字节序/大端/小端 零命中。复审 v2 判据 §6-5（docs/C_2X_DECOMPOSE_REVIEW_V2_20260912.md）已点名并判 high，本轮判据与脚本对此无实测记录也无处置；作者「blocking 全闭合」的断言在此条不成立。去重与 S3 交集不依赖字节序（值互异即可），受害的只是这条范围检查。
   - 位置：CRITERIA_PREREG.md；scripts/diag/pkt_identity.py；scripts/diag/decompose_2x_probe.py；docs/C_2X_DECOMPOSE_REVIEW_V2_20260912.md
   - 失败情景：两条路都坏：(a) 事后复核者按字面对 A1 的「seq=[256..5120]」（若 Windows seq 果真不从 1 起——未测）判五个 PC 格身份 NOT_EXECUTED ⇒ H4 闸一无法为 TWICE ⇒ 干预被判不必要或已跑的 A-off 被撤回，而脚本印的是 TWICE/H4；或复核者现场放宽，预登记当场失效。(b) 现状不实现：解析偏移出错（Id 读成 Seq 类）在跑中无人抓，身份表收到去重≈1 ⇒ LOSS ⇒ 「NOT_EXECUTED 重跑」而重跑不可能成功。
   - 修法：开窗前二选一写进判据：①删「落在 1..T 内」只留 distinct_seq ≥ T−TOL（seq 只当不透明键），做成 verdicts.structural_check(T, summary, cell_kind) 并接进 report_cell/apply_verdicts 配门；S1/S2 移出清单、S3a/S3b 列入；②保留范围检查则先在非提权下实测 Windows ping seq 取值并在 判据 §1.2 写死字节序，再实现。任一情况把首次提权跑的实际 seq 范围记为测量。

4. **[medium] 判据 §4.3「分子或分母任一读不到 ⇒ VOID」在判定块里静默：句柄 b 打不开时 count_b=None ⇒ apply_verdicts 直接跳过、VOID_MISSING 分支从探针不可达；判据 §4.5/判据 §4.6 缺读数同样不印；same_window 四时刻同线程顺序取得 ⇒ 由构造恒真、VOID_NOT_SAME_WINDOW 不可达（作者自己的「同义反复」形状）**
   - 主张：cell() 323-327 行 hb 失败印「打开句柄 b 失败 err=… ⇒ 本格比值 VOID」置 hb=None，count_b 留 None；apply_verdicts 667 行 `if c and c.get('count_b') is not None` 才调 verdict_impostor ⇒ 判定块无任何 判据 §4.3 行，判据 §4.3 末行（415）的 VOID 无输出载体。判据 §4.5（677）与 判据 §4.6（683）缺席时同样什么都不印（判据 §4.2 649 行有印「读数缺席」）。同窗：open_a(314)→open_b(324)→traffic_start(338)→grace_end(342)→close_a(354)→close_b(362) 在同一线程顺序执行，same_window（84-102）的四个不等式必然成立，在真实跑中只能返回 True。
   - 位置：scripts/diag/decompose_2x_probe.py、313-327、338-362、665-685；CRITERIA_PREREG.md、415
   - 失败情景：C1 的第二句柄因 impostor 在 FORWARD 层开句柄时被拒（err=87，编译自证只在 NETWORK 测过 f_imp）：格块中段有一行 VOID，判定块列 判据 §4.1、判据 §4.2、判据 §1.6、判据 §4.3（只有 A1）、判据 §4.5、判据 §4.6——统计判词的读者看不到 C1 impostor 行也看不到 VOID，可能把它读成「C 侧 impostor 不在范围」。同窗检查印「同窗」而它量不到任何东西。
   - 修法：凡声明了 filter_b 的格 count_b 为 None 时调 verdict_impostor(None, count, …) 使 VOID_MISSING 被印；每张判定表对每个被判格必出一行（缺席即印该表的 VOID/UNDECIDABLE 码），去掉 判据 §4.1 后的 early return；same_window 要么降为只印四时刻不作门，要么改用读线程首次 Recv 成功时刻等能失败的量。

5. **[medium] 闸二 H2「SharedAccess != Running」是本机在热点关闭态从未观测过的预登记期望值、无正对照证明可达；HOTSPOT_OFF=FALSE 时「PO 再动手」动什么未定义（若真需停系统服务则属禁区）；跑后热点重开与 P40 回网没有任何一行核验（复审 v1 建议 8(a) 未落，撞 CLAUDE.md P40 第 4 条）**
   - 主张：判据 §5-1 表（548）钉 H2 要求 `!= "Running"`；judge_hotspot_off（verdicts 311-312、317）svc_state=='Running' ⇒ FALSE，实算 judge_hotspot_off(0,1,'Running',9,9) → FALSE「热点未关（需 PO 再动手）」。判据 §5-2 正对照只查状态串在已知集内，不证关闭态可达；evidence 目录与 DECISION_LOG 无「热点关后 Get-Service SharedAccess」的读数（复审 v2 判据 §6-12 已提「SharedAccess 可以是 Running 而热点腿已消失」，作者以三项合取回应，未测）。判据 §5-3 写 FALSE ⇒「PO 再动一次手」，没写动什么。判据 §6 与脚本都没有「热点重开」「设备回热点」「设备能上网」读数；复审 v1 第 8(a) 条（docs/C_2X_DECOMPOSE_REVIEW_20260912.md）要求脚本印 Get-NetIPAddress 192.168.137.1 与 adb ip route get 两行原文、缺即收尾 FAIL。SharedAccess 关热点后是否离开 Running 本树未测——本条不断言它会留在 Running，只断言它未测而判据把它当已知。
   - 位置：CRITERIA_PREREG.md、565-567、583-594；scripts/diag/decompose_2x_verdicts.py；scripts/diag/decompose_2x_probe.py、689-715；docs/C_2X_DECOMPOSE_REVIEW_20260912.md
   - 失败情景：情形 A：PO 关热点，H1=0、H3 在上游腿、H2 读 Running ⇒ 印「HOTSPOT_OFF = FALSE：H2 不满足 ⇒ 需 PO 再动手」；PO 无第二个可做的动作，要么 Stop-Service SharedAccess（系统设置变更、禁区）要么放弃——干预烧掉或现场改判据。情形 B：跑完 PO 忘开热点或 P40 自动连去别的网络，下一会话的 P2 前提静默失败（D-880 已发生过），且无产物记录离场时设备在哪张网。
   - 修法：开窗前在本机非提权只读地把热点关/开各测一次 Get-Service SharedAccess 与 Get-NetIPAddress 192.168.137.1，把实测串写进 判据 §5-2 预登记；若关后仍 Running 则 H2 降为只印读数或改为「!= Running 或 (Running 且 H1==0 且 H3)」并附推导。第二阶段末尾加「请把热点开回来，按 Enter」→ 印 Get-NetIPAddress 192.168.137.1 计数、Get-Service SharedAccess、adb shell ip route get 223.5.5.5、adb ping -c 3 摘要四行原文，任一缺席印「恢复未核验」。PO 单写明操作路径（设置 › 网络和 Internet › 移动热点）。

6. **[medium] 判据 §1.5 血统面错位：判据抬头引的烟测 023615 是被 判据 §1.6 自己判错的旧字节（第二句柄 `true`、11 格、7 行编译表、SHA 554d6b90、HEAD 6eb51401）；当前将跑的字节（SHA 66144db3 == b225b7c8）唯一的烟测 024746 首行是 WORKTREE_DIRTY（HEAD 7e2897cc）；「首次落地 6eb51401」实为第二次（首次 9db7e992）；「26 条门」写死在 stdout 里而实际 33 条；stdout 文件七份不是六份**
   - 主张：逐条核：CRITERIA 27-29 行引 stdout_20260913-023615.txt「11 格全部 err=5、编译自证 7/7」；该文件 SHA256=554d6b90、HEAD=6eb51401，第 36 行 S3 第二句柄是 `true`（判据 202-203 行自述「不是 true …（我初版正是这么写的）」），编译表 7 行无 `(icmp or not icmp)`。当前盘上 probe sha256=66144db3=`git show b225b7c8:…`；含 S3a/S3b、8 行编译的唯一烟测 stdout_20260913-024746.txt 首行「WORKTREE_DIRTY：**提交哈希不代表运行字节**」、HEAD=7e2897cc、SHA=66144db3——它跑的确是 HEAD 的字节但盘上无任何产物说出这点。`git log --diff-filter=A -- scripts/diag/decompose_2x_probe.py` = 9db7e992（02:22:42，SHA 3d9bcf93，stdout_022300 印的正是它）；6eb51401（02:36:02）是第二次提交，判据 19、23、170 行称其「首次落地（不可变）」。probe 第 5、626 行与判据第 20 行写死「26 条门」，`grep -c '^def test_'` = 33（fa4bfa94 时 20、dc2924fa 时 26、a676ebfc 起 33）；每份逐字副本都会印这个过期数。evidence 目录有七份 stdout（022300/022714/022804/022904/023014/023615/024746）。
   - 位置：CRITERIA_PREREG.md、27-29、170、202-203；scripts/diag/decompose_2x_probe.py、626；evidence/c_2x_decompose_20260912/stdout_20260913-023615.txt:3-6、19-25、36；stdout_20260913-024746.txt:3-6、19-26、37-42；stdout_20260913-022300.txt:3-5
   - 失败情景：复核者按判据自己的纪律「要知道跑的是哪些字节，读那一轮的 stdout 副本」打开 023615，看到 CLEAN＋HEAD 6eb51401，认定通过烟测的仪器就是将跑的仪器——不是（那版第二句柄 `true` 会给 判据 §4.3 虚假的 FAIL_SKEW）；反之跑了真字节的那份首行叫读者不要信它的哈希。有人按「首次落地」锚取回探针首版会拿到 6eb51401 而不是 9db7e992——烟测抓到广播邻居 bug 的那一版从血统里消失。提权跑的逐字副本会印「26 条门」而实跑的门有 33 条，证据错报自身覆盖。
   - 修法：开窗前在干净 HEAD b225b7c8 上再跑一次非提权烟测，使存在 WORKTREE_CLEAN＋SHA 66144db3＋HEAD b225b7c8＋S3a/S3b 行的副本，并在第 27 行引它（或改写第 27 行：023615=旧字节的干净跑、024746=当前字节的脏树跑且 SHA 等于 b225b7c8）；「11 格/7/7」改为当前 12 格/8 行或标明各属哪一跑；锚改 9db7e992 并把 6eb51401 记为第二次落地；删掉写死的门数或运行时 import 测试模块数 test_ 函数印出；抬头文件数按实数。

7. **[medium] 编译自证覆盖与实际开句柄的 (filter, layer) 对不一致：f_imp 只在 NETWORK 编译而 C1 在 FORWARD 开它，f_nsrc（N2 的 !=）与 f_noicmp（A2）从未编译；行印 filt[:44] 截断使 F1/F2 两行在逐字副本里无法区分；判据 §1.6 编译表含本目录任何 stdout 都没量过的 outbound 行**
   - 主张：preflight 557-564 行 proofs 列表：fb@0、true@0、nonsense@0、f_up@1、f_hot@1、f_imp@0、f_src@1、f_taut@0；plan 591 行 C1 用 f_imp 作 FORWARD 第二句柄，595 行 N2 用 f_nsrc、590 行 A2 用 f_noicmp，三者无编译自证。compile_selfproof 277-278 行 `filt[:44]` ⇒ 每份 stdout 第 22-23 行都是「compile(ip.DstAddr == 223.5.5.5 and icmp and ifIdx = layer=1) -> True」两行相同，读者看不出 9 与 13 都编过；impostor/SrcAddr/(icmp or not icmp) 同样被截。判据 216-228 行编译表在「编译性已自量」下列 `... and outbound → True False`，grep evidence 目录该行只存在于 c_forward_layer_probe_20260912/README.md（上一轮），本轮七份 stdout 无 outbound 行、无 NETWORK 层的 ifIdx/SrcAddr 编译。
   - 位置：scripts/diag/decompose_2x_probe.py、549-566、590-595；evidence/c_2x_decompose_20260912/stdout_20260913-024746.txt:19-26；CRITERIA_PREREG.md
   - 失败情景：derive_constants 的 off-by-one 让 ifIdx == 9 被编译两次：stdout 显示两行相同的通过行，自证读作 8/8。N2 的 `!=`（从未编译）在提权窗内 open 时 err=87 ⇒ 一格烧掉，而零成本的离线自证本为此而设；C1′ 的 impostor@FORWARD 若被拒同样烧掉 C 侧 判据 §4.3。
   - 修法：preflight 对 plan 里实际用到的每个 (filter, layer) 对各编译一次（加 f_imp@1、f_nsrc@1、f_noicmp@0），任一不符即中止；印完整 filter 串（或第二行印全文）；判据 §1.6 表逐行标注来源跑（本轮 stdout vs 上一轮 README）。

8. **[medium] 本轮没有任何 PO 操作单：docs 与 BRAIN_TASKBOARD 对 decompose_2x/A-off 零命中，按现态 PO 至少要在三处即兴（A-off 怎么跑、HOTSPOT_OFF=FALSE 怎么办、驱动怎么卸），每处本树都兑现过一次（D-884 残留驱动、D-880 设备离网、D-890 粘贴改字）**
   - 主张：`grep -rln 'decompose_2x\｜A-off\｜a_off' docs/` 零命中；判据 §5-3「PO 再动手」无动作文字；脚本 __main__ 末行让 PO「调 a_off_stage()」；finally 印「需手动 stop」而无命令与判读通道（bash $? 会把 1060 读成 36，D-891）。脚本会自动止跑的条件（设备不在热点／判据 §2 不过／哈希不符／编译不符）都在开句柄之前；不会止跑却使整轮作废的条件（S0 err=5、S0 count≠0、判据 §1.6 FAIL、pre≠1060）PO 只能靠读判定块。
   - 位置：docs/（零命中）；scripts/diag/decompose_2x_probe.py、615-621、728-729；CRITERIA_PREREG.md、583-594
   - 失败情景：PO 在提权窗里看到「判据 §4.1 ⇒ TWICE」后没有下一条可执行指令；或看到「HOTSPOT_OFF = FALSE」后不知动什么；或看到「服务仍在 FAIL」后在 Git Bash 里 `sc stop; echo $?` 读 36 误判。任一处即兴都让本窗最贵的读数或机器现场失去可核的产物。
   - 修法：先修 A-off 入口、teardown、HOTSPOT_OFF 三条 high/medium 使即兴步骤消失，再由执行会话写 evidence/c_2x_decompose_20260912/PO_RUNSHEET.md（大脑核）：每步成功判据只引用 stdout 里能逐字 grep 的文本；写明唯一提权面是右键管理员 PowerShell（不用 Git Bash）、零参数一条命令、判定块读哪一行、关/开热点的设置路径、恢复核验三条命令、卸驱动命令与「读文本含 1060 不读 $?」、交件＝首行点名的 stdout 文件而非粘贴。

9. **[low] apply_verdicts 在 A1 缺 summary 或 T 时整段 early return：S3 自证、C1 身份、H2、N、底噪这些不依赖 A1 的判词全部不印**
   - 主张：apply_verdicts 630-632 行 `if a1 is None or a1.get('summary') is None or a1.get('T') is None: print(...); return out`；report_cell 对空 recs 返回 None ⇒ A1 count=0 即 summary None。S3（自证）、C1 身份、N1/N2、S1/S2 底噪与 A1 无关却随之消失。七份烟测的判定块因此都只有一行，判据 §1.6/判据 §4.2-4.6 连「未判」都没被点名。与 cp936 那条叠加时它是放大器；单独在 A1 因本机防护挡 ping 而 0 计数时也触发。
   - 位置：scripts/diag/decompose_2x_probe.py
   - 失败情景：A1 句柄开成但见 0 包（PC ping 走了别的接口或被本机防护挡）：判定块一行「全部不可判」，S3a/S3b、C1、F/N、S1/S2 已花掉窗时却没有判词进逐字副本，事后只能人手重算；S3 自证结果（解释任何 impostor 读数所需）从副本丢失。
   - 修法：去掉 early return，各段各自判前提缺席并印「<表> 前提缺席 ⇒ 不可判」；后续段把 code is None 当「前提缺席」处理。

10. **[low] S3 自证只在 NETWORK 层做（PC 打）却被当作 FORWARD 层 C1/C1′ 配对的前提；「a 空 b 全」被标成 W3「量法没活」而它是 W2 的镜像**
   - 主张：plan 587-588 行 S3a/S3b 都是 LAYER_NETWORK＋pc_ping；apply_verdicts 668-670 行把 s3_code=='PASS' 作为 A1 与 C1 两格 impostor 的共同前提。判据 §3 矩阵 S3 层＝NETWORK（269），判据 §4.3 第 388 行把 S3 作为整节前提；判据 §1.6 编译表第 226 行与 D-887 都实证两层语义可不同（outbound：NETWORK True、FORWARD False）；D-885/判据 §7 禁止跨层搬读数。verdict_s3 351-354 行 na<floor 即 VOID_NOT_ALIVE「量法没活（W3）」，实算 verdict_s3(20,[],FULL) → VOID_NOT_ALIVE——而句柄 b 全收证明量法活着，这是 W2 镜像。
   - 位置：scripts/diag/decompose_2x_probe.py、665-670；scripts/diag/decompose_2x_verdicts.py；CRITERIA_PREREG.md、269、388-389
   - 失败情景：多句柄复制语义在 NETWORK 成立而在 NETWORK_FORWARD 不成立（或反之）：S3 PASS 放行 C1′/C1，FORWARD 层 impostor 比值以「S3 已过」为前提报 IN_BAND。a 空 b 全时印「量法没活」误导去重跑量法。
   - 修法：补一格 S3-F（FORWARD、设备打、同 filter 两句柄，约 21 s）并让 C1 的 s3_ok 接它；或在 判据 §1.6 与 C1 判词文字里明写「S3 只证 NETWORK 层，C1 配对前提外推自 NETWORK，属边界」。verdict_s3 对 na<floor 且 nb≥floor 返回独立码 FAIL_ONLY_B。

11. **[low] 判据的 T 前提不闭合：判据 §4.1 第 5/6 行拿 A2 计数比 A1 的 T 而无 T_A2==T_A1 前提；判据 §4.5 的 [T−2,T] 不说 T 是谁的，且无 T_N1==T_N2 前提**
   - 主张：判据 §3（262）定义「T ＝ 该格实际印出的发包数」；判据 §4.2(c)（333-334）立了「T 不等时是三个不同分母的裸相加」这把尺，但 判据 §4.1 第 291-292 行「A2 计数 ∈ [2T−2,2T]」用的 T 是 A1 的、无 T_A2==T_A1 前提；判据 §4.5 表（485-486）用 [T−2,T] 判 N1/N2 却不指明 T 取自谁，N1、N2 是两次独立设备 ping，也无相等前提。脚本侧 verdict_identity 从不看 a2['T']。
   - 位置：CRITERIA_PREREG.md、291-292、333-334、485-486；scripts/diag/decompose_2x_probe.py、679
   - 失败情景：A2 那次 PC ping 只发 18 而 A1 发 20：A2 匹配 36 ∈ [2·18−2,36] 却不在 [38,40] ⇒ 落「既不在也不在 ⇒ 不可单判」——一次合法读数被判成不可判（方向保守，不是错结论，但 判据 §4.2 自己立的尺 判据 §4.1/判据 §4.5 没用）。
   - 修法：判据 §4.1 第 5/6 行加前提 T_A2==T_A1（不等 ⇒ 两支 VOID）；判据 §4.5 明写「T 取 N1、N2 各自实印发包数且 T_N1==T_N2 为前提」；verdict_identity 增参 T_A2、verdict_n 增参 T_N1/T_N2，说明文字并印三个 T。

12. **[low] 判据文本悬空与无出处项：第 351 行「判据 §5-4 之后不得再跑」应为 判据 §5-6；判据 §5-1 H3 引「判据 §2-2 推导的上游腿索引」而 判据 §2 六条无一条推导上游腿（复审 v2 判据 §6-19 未闭合）；判据 §6-1 与 probe docstring「8 格打 adb」实为 5；第 63 行「集合外的码记 OBSERVED_NEW_CODE」而集合已不存在；H3 在热点开/关两世界读数相同；MCAST_CIDR 死常量；C1 的 UNDECIDABLE 文案引 A2**
   - 主张：(1) CRITERIA 351 行「FORWARD 格在 判据 §5-4 之后不得再跑」——判据 §5-4 是纯函数实现条款，硬顺序在 判据 §5-6（527 行引用正确）。(2) 549 行 H3「== 判据 §2-2 现场推导出的上游腿索引」、563 行「上游腿地址取自 判据 §2 同一次读数」——判据 §2 第 242-252 行六条只有热点腿（②）；上游腿只在脚本 derive_constants 202-208 行由 Find-NetRoute 取得，判据无此规则；复审 v2 判据 §6-19（docs/…V2:129）已指出、未修。(3) 判据 586 行与 probe 574 行「12 格、其中 8 格打 adb」，plan 里 dev_ping 只有 C1/F1/F2/N1/N2 五格。(4) 63 行「集合外的码记 OBSERVED_NEW_CODE」，59-60 行已把三个码降为推断值，文件里没有一个显名集合。(5) H3「PC 到目标的路由在上游腿」在热点开着时同样为真（热点腿是 /24 局域网，从不是到 223.5.5.5 的路由）⇒ 按 D-901 不区分两世界，只是活性对照；test 249-252 行把 route_ifindex=13 当「单独使假」展示。(6) probe 48-52 行 MCAST_CIDR 定义未用（作者自注「不可达的守卫是一个邀请」而常量仍留着）。(7) verdict_identity 对 C1 传 a2_count=None 时印「但 A2 计数未取到 ⇒ 分不开背景非 ICMP…」——A2 是 NETWORK 格，对 C1 这是旁边常量的文案。
   - 位置：CRITERIA_PREREG.md、242-252、351、549、563、586；scripts/diag/decompose_2x_probe.py、202-208、574、639-642；scripts/tests/test_decompose_2x_verdicts.py；docs/C_2X_DECOMPOSE_REVIEW_V2_20260912.md
   - 失败情景：(2) 有后果：F1 的常量与 判据 §5 H1 正对照地址在判据里无推导规则，操作者只能信脚本；换机器（多默认路由，sweep 判据 §2 实测 WLAN 仍带一条 0.0.0.0/0）时 Find-NetRoute 取到 WLAN 腿，F1 读 0 落 DEGENERATE_HOTSPOT_ONLY，证据把「常量打偏」写成「转发层语义」。其余为悬空文本，会在现场削弱正确条款的可信度。
   - 修法：改 判据 §5-4→判据 §5-6；判据 §2 补第 7 条「上游腿＝Find-NetRoute 到目标的接口索引与源地址，count 须恰好 1，与 判据 §5 H1/H3 同源」；「8 格」改为脚本印出的实数或删；删 OBSERVED_NEW_CODE 句或恢复显名「待钉集合＝∅」；H3 在判据标注为活性对照并改「路由 ifIndex ≠ 热点腿索引」；删 MCAST_CIDR 或使用；verdict_identity 带 cell 标签使 A2 缺席文案只对 A1 发。

13. **[low] 被禁的「约」与无区间的「显著」仍在判据里：第 419 行「n 显著偏离 2T 时本节所有带的前提已不成立」是承重前提守卫却无数值也无实现；第 403、495-498、535 行含「约」（叙述/史实用法）**
   - 主张：grep 实得「约」在 109、403、441-442（引用 v1 措辞）、495-498、535 行；「≈」在 187-190、291、341、394、401、404、476-478 行；「显著」仅 419 行。其中 419 行直接承重：它是 判据 §4.3 整节带的前提（每包两次目击），既无区间也无实现（apply_verdicts 671-675 只印 n 与带）；NEAR_ALL／TOLERANCE_LEVEL 两支不要求 TWICE，n 偏离时 1−2/n、2/n 照算照判。其余「约」多为叙述或引用旧文，非操作性阈值。
   - 位置：CRITERIA_PREREG.md、419、495-498、535；scripts/diag/decompose_2x_probe.py
   - 失败情景：n=28（A1 丢了 12 个第二次目击）：识别可能已非 TWICE，但 NEAR_ALL／TOLERANCE_LEVEL 不要求 TWICE，2/n=0.071、1−2/n=0.929 照算；「显著偏离」谁也不判，带的前提失效而判词照印。
   - 修法：419 行改为「n ∉ [2T−4, 2T] ⇒ 本节 VOID_N_PREMISE」（与 判据 §4.1 第二行同源容差）并在 verdict_impostor 加该分支与门；403、495-498 的「约」换成实测值与出处（2.0 s 读自 GRACE_S、19 s 读自上一轮 19031 ms）。

## §6 已知项 K1–K13 与交叉一致性 X1–X15（大脑两天前逐条核实，原文照录，仅去掉代码行号）

### 后处理原件:大脑在面板返回前已独立核实的事实(对象 b225b7c8,2026-09-13)

### 已知项(v4 报、大脑核实),面板重发现者并入此处,不算新发现
| 位置 | 判据现文 | 实际 | 类别 | 修法 |
|---|---|---|---|---|
| §1 抬头 L20 | 判定层 fa4bfa94→dc2924fa,门 26 条 | verdict_s3 落在 a676ebfc;门 33 条 | 现态 | 冻结解除后改为指向文件,不写计数 |
| §1 抬头 L21 | 突变 9+5+7 | 另有 S3 的 4 个 | 现态 | 同上 |
| §1 抬头 L29 | 编译自证 7/7 | 023615 那轮**确实 7 行**(stdout 第 19-25 行,无恒真子句行);现表 8 行 | **史实** | **只加时刻限定,不许改数**(坑 6);任何面建议改成 8/8 的,否其修法、留其发现 |
| §1.6 L201 | verdict_s3 门 6 条 | 7 条(含 test_s3_tol_and_skew_drive_different_branches) | 现态 | 同 L20 |

### 盲对照 must_survive 的前提(大脑独立核实,真缺陷非真话)
- 判据抬头钉探针「首次落地」= 6eb51401;git log --diff-filter=A 唯一 A 提交 = **9db7e992**(02:22「12 格探针落地」),6eb51401(02:36)是修复提交且 9db7e992 是其祖先、二者皆在 origin。
- 后处理: 若面板正确让 CONTROL-R 存活,则此缺陷本身也要进裁定(它不只是对照,是真缺陷)。

### 冻结边界的洞(v4 报、大脑认)
- decompose_2x_probe.py `from forward_layer_probe import driver_rc, teardown_labels` ⇒ 冻结集须含 forward_layer_probe.py、test_forward_probe_teardown_labels.py(7 条门,函数在 :222/:228)、run_all.py;v4 已自行冻结并冻结期不跑探针。
- 后处理: 核是否有面顺 import 追进 forward_layer_probe.py;无则大脑补查并显名写进覆盖声明。

### 大脑自己这轮的取值教训(不进裁定,进记忆已做)
- grep|head -14 把 verdict_s3/SKEW 挤到截断线外 ⇒ 一度以为不存在;粗 grep 数编译行得 8 是把节标题算进去 ⇒ 计数会骗人,看原文。

### 已知项 #5(v4 冻结期只读核出、大脑核实): MECHANISM_SWEEP.md §3-1 残留被 §6 推翻的理由
- SWEEP:60 「它就是为这个问题造的:一次运行、零风险地回答」、:63 「在一个只读测试能回答同一问题时不该伸手去碰」**原样还在**;
- SWEEP:97/:104 §6 已收窄成只剩「不可逆且扩大攻击面」;判据 :435 自己写着「SWEEP §6 的理由须改成只剩前半句」⇒ 判据要求了,被引文件只改了一半。
- 形状:「我把正文改了 ≠ 这条已被订正」(self-audit-scans-its-own-map),v4 今日第二次;处方=写「已订正」的同一动作跑同字面全仓搜索。
- 类别:现态;修法(v4 解冻后那一笔第 1 步):§3-1 两句改成「impostor 只回答该包是否经某注入句柄进入;不说明哪个驱动;不排除同驱动重注入/LWF 复制/协议栈二次呈现;I==0 本轮无正对照、结构上无法自证(判据 §4.3)」,理由收窄同 §6。
- 同字面全仓基线(解冻前,供 v4 修后比对):「只读测试能回答」1 处、「一次运行、零风险」1 处、「门 6 条」1 处、「26 条」7 处(不全是 L20 那条,修时逐处分辨)。
- 后处理:核是否有面读到 SWEEP:60/63;无则记为我编排的盲区(无专读「判据↔被引文件」的面),已另起交叉一致性代理补。

### 已知项 #7–#10(v4 自做交叉一致性面报、大脑核实;格数**读自 plan 原文**,非解析器)
- **#7(结构,重)**: 判据 §3 矩阵第 269 行只有一行 S3,原文「并开两句柄(a:同 filter;b:恒真改写)」把两个互斥配置压成一格——句柄 b 不可能同格既同 filter 又恒真改写;§1.6 与脚本(plan 有 S3a/S3b 两条)都是两支 ⇒ 须拆 S3a/S3b 两行。不是计数问题,是表描述了跑不出来的配置。
- **#8(现态)**: 「12 格」7 处(判据 :19/:159/:587;脚本 :2/:517/:572/:574) ⇒ plan 实为 12 格(S0 S1 S2 S3a S3b A1 A2 C1 F1 F2 N1 N2)+ A-off 单独一格(:708)= 13。
- **#9(从来没对过)**: 判据 :587 与脚本 :574 写「其中 8 格打 adb」⇒ plan 里 dev_ping 恰 **5** 格(C1 F1 F2 N1 N2);pc_ping 4(S3a S3b A1 A2);空闲 3(S0 S1 S2)。拆 S3 前后都是 5 ⇒ 不是改旧的,是一开始没数。「中止机会翻四倍」理由不成立(结论 try/finally 仍该要,理由错;错数已从判据抄进实现 docstring)。
- **#10(进 PO 单子)**: 「先跑前 11 格」是拆 S3 前的数;023615 的 err=5 共 11 次(拆前)、024746 共 12 次(拆后)⇒ **PO 应当看到 12 格报数,A-off 另计**。写 11 会让 PO 把正常运行读成异常(两个方向)。
- 修法(v4 解冻后,大脑同意): 判据与 docstring 不写描述别处的计数与「最新」哈希,指向文件;确需跨文件的数须同一动作数一遍并注「数自 plan」。
- v4 在总结这族的同一条消息里又口头复述错两处(11 格),不在文件里改不回来 ⇒ 这正是「不写计数、指向来源」而非「把数改对」的理由。
- 大脑自己这轮两次数到 0(正则模式不匹配含空格与中文的格标签),都被断言拦在写盘前 ⇒ **计数的量法要先证能数到**;最后是把 plan 块原样打印出来读的。

### 已知项 #11(v4 报、大脑核实): 运行时 print 把「26 条门」印进五份不可追改的证据
- 「26 条」7 处分类(大脑逐处核): 现态 3 处 = 判据 :20、探针 :5(docstring)、探针 :626(**运行时 print**);另 4 处同字面不同物 = REVIEW_20260905_FULL :4/:491、DECISION_LOG D-287/D-527 ⇒ **解冻后改 3 处不改 7 处**;把 7 当清单就伪造 4 条别人的记录(没锚定的匹配器匹配到超集,落在修法搜索上)。
- 五份 stdout 各含一次(022804/022904/023014/023615 第 68 行;024746 第 72 行)。时间线: a676ebfc(02:56:00)使 verdicts 门 26→33;023615 自印 HEAD=6eb51401、工作树 CLEAN、无 S3a/S3b ⇒ 当时门确为 26,**印的是史实**;024746 自印 HEAD=7e2897cc(早于 a676ebfc)但**WORKTREE_DIRTY**、格清单含 S3a/S3b ⇒ 跑的是未提交的拆 S3 版本、盘上门已 32 ⇒ **印出来那一刻就错**;且它自印的 HEAD 戳**不代表运行字节**——正是 §1.5 要 WORKTREE 状态的理由。
- 🔴 证据不可追改: 五份 stdout 一个字都不改;只在 README/裁定加时刻限定。面板若建议改 stdout 里的 26 ⇒ 否其修法。
- 规则收紧(v4 提、大脑同意): 从「判据不写跨文件计数」到**「脚本也不许 print 另一个文件里的计数」**——写在文件里的过期数还能改,印进运行输出的会落进不可追改的证据。解冻后 :626 改为不带数的指向。

### 已知项 #12(🔴 最重,v4 报、大脑独立核实): 前提门对可达性盲,设备已断热点两小时而四道门全绿
- 大脑实测(只读): 设备→网关 192.168.137.1 **0/3**、→223.5.5.5 **0/3**;wlan0 仍 `inet 192.168.137.129/24 state UP,LOWER_UP`;`ip route get` 仍 `via 192.168.137.1 src .129`;wifi 日志 09-13 00:36:48 `NETWORK_DISCONNECTION_EVENT reason=3:DEAUTH_LEAVING`。
- 四道门全假绿且**同源**: ①ip route get(路由仍配着) ②设备 src token(仍绑着) ③PC 邻居 Permanent(§2 已记载不随设备离开消失) ④§2-3「双侧必须同意」——两侧都派生自同一份过期关联 ⇒ **一致不构成互证**。唯一能抓住的量「一个包真的过了第一跳」不在任何一道门里。
- 已入库四份烟测(022300–024746,02:23–02:47)全跑在此状态下,逐字印着 ON_HOTSPOT 与 §2 六条通过 ⇒ 它们是**这个缺口的诚实记录**,证据面按此读,不算污点。
- 🔴 大脑自己的过期报告: 大脑此前向 PO 报「P40 已回热点」,依据正是 `ip route get`(同一条假绿)⇒ 须向 PO 订正。
- 修法(v4 提、大脑同意,进 still_blocking): 前提门第一步加**第一跳可达性正对照**——`adb shell ping -c 3 <热点网关>` 须**收到 ≥1 回复**(不是 rc==0、不是路由在、不是邻居在),否则 NOT_EXECUTED,且**排在 ip route get 之前**;承记忆「先证对端在网,再谈路径上的过滤器」(第四例 ARP FAILED 怪 AP 隔离,真因 PC WLAN 没连)。
- 解冻后 v4 改门再跑非提权烟测: 设备若仍断开,新门**应当拒跑**——那就是它的正对照。PO 重连热点排在门修好之后,不在之前。

### 已知项 #13(v4 报;窗长数大脑未独立核出): 空闲格窗长短于目标格窗长 ⇒ FORWARD 底噪无法放行
- 探针 :438 `IDLE_SLEEP_S = 20.0`(+2 宽限 = 22 s);verdicts :234 `noise_policy(s_count, s_window_s, target_window_s)` 在 s_window < target 时返 SHORT_WINDOW_NO_PASS(:249)。
- 024746 未印可解析的窗长字段(大脑未核出数);v4 报 adb ping -c 20 -i 1 wall 29.56 s ⇒ 目标格约 31.6 s,**此数暂按 v4 所报、未经大脑独立核**。若目标格 ≈31.6 s > 22 s ⇒ S2 必返 SHORT_WINDOW_NO_PASS ⇒ FORWARD 各格底噪不可用于放行,而那正是回答本问题的那半。
- 这个 20 是 v4 选的,没测过它要压住的时长 ⇒ 「从旁边的常量推出一个数」。修法(进 still_blocking): 由第一格实测窗长推出空闲窗长(或给足余量,由 noise_policy 跑完自判)。

### K12 订正(v4 撤回因果、大脑复核并撤回自己抄的推断)
- **撤回**: 「设备已解除关联」「DEAUTH_LEAVING 00:36」——那条日志的 SSID 是 DE8D723F7A,不是热点;大脑打印时 cut -c1-140 恰把 SSID 截掉,照抄了推断。
- **现态(大脑实测)**: `cmd wifi status` 连着 "DESKTOP-C1AHCTT 6482"(RSSI -18, Supplicant COMPLETED);设备邻居 192.168.137.1 lladdr 0e:7a:15:1f:4d:a7 **REACHABLE**;connectivity `WIFI CONNECTED … EVER_VALIDATED`(非 VALIDATED);设备→223.5.5.5 ICMP 无回复。⇒ **关联在、L3 不通、今早 ICS 干跑时通过(PC 11→213→11,设备 20/20)** ⇒ 中间有东西变了,因果**不猜**(判因要动 PC 状态)。
- ⚠ 大脑的 `/dev/tcp` TCP 探测报 TCP_FAIL 是设备 sh 不支持该语法 ⇒ **工具伪影,不作证据**;v4 的 TCP_FAIL 用的是别的方法,按其所报。
- **发现不变**: 四道前提门全对「流量是否真过得去」盲且同源 ⇒ 双侧一致不构成互证。已入库四份烟测是此缺口的诚实记录。
- **修法订正**: 不是 ping 网关(PC 可合法不回 ICMP echo 而转发正常),而是**同协议同路径的往返正对照**——前提门第一步 `adb shell ping -c 3 223.5.5.5` 须收到 ≥1 回复,否则 NOT_EXECUTED,排在 ip route get 之前;它测的正是 C1/F1/F2/N1/N2 全部依赖的往返,**今天会拒跑,即其正对照**。失败文本印读数不印解释。

### 交叉一致性代理(a9236726907dbd7af)结果: K1–K6 全部找到;另报 15 条,按严重度
- 证据目录实有 **7** 份 stdout(024746 由 a676ebfc 入库),我任务单写 6 —— 我的过期数。
### HIGH
- X1 **§6-1 :585-586 「finally 无条件调 teardown()」——decompose 探针里没有这个函数**;只 import driver_rc/teardown_labels(:241),main 的 finally(:615-621)只算标签并打印,全文无 sc.exe/stop/delete。§6-2/6-3 描述的是 forward_layer_probe.teardown() 的行为,该函数未被调用 ⇒ 12 格跑完 WinDivert 仍 RUNNING。**D-884/886 形状原样重演**。⇒ still_blocking。
- X2 **K1 第二处**: §1.5 :170 「self_id_lines(6eb51401)」同错,应 9db7e992;7e2897cc 自述「写进两处」⇒ 两处同改。
- X13 **§1.2 :104 要求每包记录逐行进 stdout、§4.1 :304 靠「事后查询每包日志」——探针从不印每包记录**(report_cell 只印 summarize 汇总 :428,recs 留内存)⇒ SrcAddr 拆支与事后查询在 stdout 里无数据源;抬头「12 格主脚本已落地」覆盖了一条未实现的记录要求。⇒ still_blocking。
### MEDIUM
- X3 §1.3 :145 把跑中结构自检适用集写成含 S1/S2,而被引裁定 v2 :34 明写「窄格与空闲格另立判词」;空闲格 T=0 ⇒ 「seq ∈ 1..T」空集 ⇒ S1/S2 一抓到底噪包即 NOT_EXECUTED——恰在底噪格有话说时作废。
- X4 §4.6 :495-498 「空闲格只观测约 2 秒…time.sleep(2)」是 891cddb4 时对 forward_layer_probe 的读数,现探针 IDLE_SLEEP_S=20+GRACE 2 ⇒ **史实,只加时刻限定**;同句在 test_decompose_2x_verdicts :186 注释。
- X5 = K9(「8 格打 adb」任何版本都没有 8;v1 矩阵 6、现 5)。
- X6 **§1.6 :216-228 两层编译表(8 行×N/F)自称「已自量」,仓内无任何仪器输出对应**——所有 stdout 的编译行都是单层且从未编译 outbound;表自 a0dca7b5 起就是 8 行;⇒ K4 的指认物订正: 抬头「7/7」指探针 compile_selfproof 调用数(023615 印 7、024746 印 8),**不是这张表**;表的 FORWARD 列与 outbound 负对照无处可查。
- X7 §4.3 :435-437 指令态写一件同提交已做完的事(a0dca7b5 同笔改了 sweep :97),且引号内那句是判据 v2 自己的文字,sweep 原句是「而 impostor 只读即可回答同一问题」。LOW→MEDIUM 合并 K6。
- X8 **反向: DECISION_LOG D-899 仍以「两句柄计数之差不超过 2、不满足则 VOID」为现行裁定,判据 §1.6 :182 已判其非判别器并以三合取替换(a676ebfc),日志无条目记录推翻** ⇒ **大脑的账**: 按追加制新增 D 条引用 D-899,不改 D-899。
- X9 反向: sweep §3-2 :65-67 「H2 在转发层可由 filter 单独判定」未收窄;判据 §2-4/§4.2 已标 ifIdx 语义未实测。与 K6 同形不同行。
### LOW
- X10 §1.5 「第一行印三件/第一行明写 WORKTREE_DIRTY」vs 七份 stdout 一律在**第 3 行**(第 1 行副本路径、第 2 行标题);门断言的是 self_id_lines 返回列表的 lines[0] 不是文件首行;「缺一件即拒跑」在 print_self_id 无对应拒跑路径。
- X11 §1.4 :152 规定印「-- 起跑:sc query WinDivert rc=%d ⇒ %s --」,探针 :543 实印「跑格前 sc query …」;grep「起跑」在任何 stdout 为 0。
- X12 = K11 旁支(26 焊在探针 :5/:626)。
- X14 sweep :5 「将被判据 §0 引用」——§0 现不引 sweep,实引在抬头 :12/§4.3 :435/§7 :603。Review v2 §6-25 已指出未动。
- X15 Review v2 §6-28 两处未验推断原样保留: §2 :256-257 MAC 持久随机化那句、§5 :530 「今天真的发生过两次」——无测量无 D 锚。

## §7 现场（2026-09-15 核）

- PC 于 09-14 22:57 重启。**热点虚拟卡 ifIndex 13→14、以太 9→11**——两天前判「虚拟卡索引不稳」（D-880 族）的缺陷今日实证；判据 §1b 现场推导是对的。
- 设备连着热点（RSSI 强、Supplicant COMPLETED），**同协议同路径往返 5/5 收到回复、RTT≈50 ms**；网关不回 echo（PC 默认），故「ping 网关」不是对照。
- 驱动 `sc query WinDivert` rc=1060（python returncode 印成文本）。
- **v4 会话已不在本机**（随重启消失）。冻结解除；十条修法 ＋ X1–X15 ＋ §2 三条**无属主**——这是 PO 的决定。

## §8 覆盖声明

没做的：go/no-go 综合代理未跑，本裁定由大脑手写；两条盲对照未跑，面板区分力**未证**，故 §2 的「存活」只表示三票中否决少于半数，不表示被证实——被证实的只有 §1 三条与 §6 的已知项；§4/§5 共 16 条一票未投。本审没有跑任何句柄、没提权、没碰设备状态。「完备」一词不使用。
