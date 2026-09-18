# 2× 分解 · 大脑终审裁定 v4（2026-09-18；对象 `1ad20a71`）

> 四面复审（修法正确性／回归／上轮未竟项／可跑性）→ 归并 27 → 送复核 6 → 每条三视角，另混两条方向相反的盲对照。
> 🟢 **面板本轮完全有效**：真缺陷 0/3 被否、假缺陷 3/3 被否 ⇒ 票有区分力。送复核 6 条**全部存活、零被否**。
> ⚠ **27 条归并里只送了 6 条复核，21 条一票未投**——按未核处理，**不是**按没问题处理。
> 本文件由脚本从 workflow journal 直接生成，代理文本未经转述；只做两处机械归一（代码行号改锚文字；代理写的节号加「判据」前缀，本文自身小节为 §0–§10）。

## §0 结论

**verdict：`no_go`。不开窗，PO 单子不发。**

四笔提交把上一轮点名的三条 HIGH 真修掉了（V1/V2/V3 我独立复核为真），但同一批代码上仍有六条会**烧掉整窗**或**印出自信错误结论**的缺陷，其中两条我在本机直调复现：分流世界下 verdict_s3 判 PASS、UTF-8 模式下 _decode 退化成单条路使所有 T=None；再加上本窗唯一要 PO 动手的 A-off 格在任何路径上都调不到 —— 不开窗。

## §1 大脑亲复现（2026-09-18，本机）

| 发现 | 复现 |
|---|---|
| 回归 A：`_decode` 回退编码取自解释器 locale | 同一批 cp936 字节：默认 `python` → `getpreferredencoding='cp936'`、`sent=3`；`python -X utf8` → `'utf-8'`、**`sent=None`**。`GetACP()` 实读 **936**，不随解释器模式变 |
| 回归 B：A-off 零调用 | `a_off_stage` 全文件仅两处出现：定义处，与一个**被打印的字符串**里；`__main__` 只调 `main()` 与 `apply_verdicts()`。`teardown` 在 `main()` 的 `finally`，而 `main()` 先 return、`apply_verdicts` 后跑 ⇒ **判词印出时驱动已卸** |
| 无提权门 | `IsUserAnAdmin`／`shell32` 全仓零命中；`stdout_20260918-194103.txt` 的 `err=5` 计 12 次，判定块只剩一行 ⇒ **整轮无声报废已发生过一次** |
| T 取发包数（对同侪反驳的裁决） | `verdict_identity(20,0,{})` → `LOSS` ✅；但 `zero_reading_ok(0,True,True)` → **True**（线程正常退出的真掉线场景**没被**接住），同侪引的第二道支撑不成立。枚举各档：全掉线／重丢 → `LOSS`，轻丢 18 收 2× → `TWICE`（±2 容差吸收）⇒ **T 必须留作发包数**，可达性另设读数 |

## §2 仍拦窗（11 条）

1. 【S1 复现】_decode 的回退编码取自 locale.getpreferredencoding(False)（probe:136）。本机实测：默认 python 返回 cp936，`python -X utf8` 返回 **utf-8** ⇒ 「先 utf-8 严格、失败再按 ACP 严格」退化成同一条，落 replace ⇒ _sent_count 恒 None ⇒ 所有 PC 打的格 T=None ⇒ apply_verdicts:792 早退，整窗只剩一行。`or "cp936"` 救不了（'utf-8' 是真值），🔴 那行只 print 不中止。可检查的改法：(a) acp 改由取到字节的那一层决定 —— `acp = "cp%d" % ctypes.windll.kernel32.GetACP()`，并显式断言 acp.lower() 不含 'utf'，相等即 SystemExit；(b) preflight 第一件事跑 `ping.exe -n 1 127.0.0.1`，_sent_count != 1 即 SystemExit「量法在本解释器上不工作」——零设备零提权零秒，是把这条坑从「烧整窗」压成「preflight 一行」的唯一动作，而同一批提交为设备可达性加了第一道门、成本相同却只做了一个；(c) 门里用 subprocess 以 `-X utf8` 跑同一夹具（同进程内跑不出这个世界）。

2. 【S4 复现】verdict_s3 分不开「SNIFF 是复制」与「2T 个目击被两句柄按目击交错分掉」。本机直调：verdict_s3(20, 每 seq 两次共 40, 同样 40) → PASS；verdict_s3(20, 每 seq 一次共 20, 同样 20) → **PASS**。三条件里唯一能分开这两世界的量是目击数（复制 2T／分流 T），而活性条件只给下界 T−TOL、没有上界、也不与本层单句柄格比。门这一侧同源：test_decompose_2x_verdicts.py 的 FULL 只有 T 个元素却被当**正对照**钉住，全套夹具里没有一个重复 seq 的例子 —— 本实验要研究的那个 2× 世界在门里根本不存在。可检查的改法：补第四条件在**目击数**维度（｜seqs_a｜ 与同层单句柄格 A1 的 count 在 ±TOL 内，或 ｜mult_a − mult_b｜ <= 1），docstring 世界表把 W4 拆成 W4a（按 seq 切）／W4b（按目击切）各算读数；门侧 FULL 换成「每 seq 两次」的复制夹具，并加反例：每 seq 一次的 20/20 必须**不**判 PASS。

3. 【S5 复现】C1（FORWARD 层）的 impostor 判词由 NETWORK 层的 S3 自证放行。probe:822-834 汇出单个 s3_code，probe:837-841 把同一个 `s3_code == "PASS"` 同时喂给 ('A1', code) 与 ('C1', cc)；而 plan（probe:742-743）里 S3a/S3b 都是 LAYER_NETWORK ＋ pc_ping，C1 是 LAYER_NETWORK_FORWARD（probe:746）。列世界：W-a 两层都复制 ⇒ C1 侧 I≈0.5；W-b NETWORK 复制、FORWARD 只给一个句柄 ⇒ C1′ 读 0 —— **两个世界下 s3_ok 都是 True**。直调 verdict_impostor(20,40,False,True,'TWICE') → VOID_S3，证明闸本身是活的，被绕开的是入参来源。可检查的改法：apply_verdicts 按层分别汇总 s3_code，FORWARD 层没有 S3 就喂 False；verdict_impostor 加 layer 入参，前提来自另一层返回 VOID_S3_FOREIGN_LAYER（与 verdict_h2 的 VOID_T_FOREIGN 同形）；判据 §3 矩阵给 FORWARD 层补一对 S3。补到之前，C1 的 判据 §4.3 显名标为本轮不可自证。

4. 【S3 复现】verdict_identity 的 TWICE 未按 SrcAddr 拆支。直调 verdict_identity(20,20,{2:20}) → 'TWICE'，与 src 无关；签名（verdicts:32）没有 src 参数，TWICE 分支写死「同一数据报被呈现两次」。而 criteria:295-300 明写这一行必须再按 SrcAddr 拆两支，criteria:142-145 还说把它做成 summarize() 返回字段就是为了「它不可能只挂在判定表的一行下」——两个调用点（probe:797-798、807-808）手里都有 src_same_within_key，一个都没传。可检查的改法：src_same_within_key 变必填参数，TWICE 拆成 TWICE_SAME_POINT／TWICE_TWO_POINTS／TWICE_SRC_UNKNOWN，说明文字由该值算出；门＝去重数与重数分布相同、只差 src 旗标必须给出不同的码。⚠ 每键单例时该字段空真，须与重数检查配套。

5. 【S2 复现】A2 的 count 是 ICMP-only ⇒ 判据 §4.1 第 5 行结构上不可达。pkt_identity.py 对 protocol != 1 一律 return None，cell():465 `out["count"] = len(out["recs"])` ⇒ A2（filter 去掉 `and icmp`）只数 ICMP，A2−A1 恒为 0。直调：verdict_identity(20,20,{1:20},20) → NO_2X_NOT_REPRODUCED「原 A=40 连原 filter 都不复现 ⇒ 本轮前提消失，H1/H2/H4 全部不可判」；同样读数换成真实匹配总数 verdict_identity(20,20,{1:20},40) → NO_2X_BACKGROUND。即：在「20 个 ICMP ＋ 20 个背景包」这个 MECHANISM_SWEEP.md 实测过的世界里，40 其实复现了，而判词会关掉整个 2× 分解。可检查的改法：每格加 `count_all = len(recs) + len(unparsed)`，A2 用它喂 verdict_identity，判词那行并印三个数（匹配总数／ICMP／非 ICMP）；判据 §4.1 与 判据 §4.6 明写 A2 计数＝该格 filter 匹配总数。

6. 【S6 复现】verdict_s3 按目击计数而 SKEW=2 是按包推导的（verdicts:344-346 自述「开头与结尾各可能差一个包 ⇒ 上界 2」），在 2× 世界里一个包是两次目击，声明的容差只剩半个包。直调：twice 对 twice[:-3] → FAIL_SKEW，twice[:-4] → FAIL_SKEW。另一半更重：cell():427-429 在句柄 b 开失败时置 hb=None 且不记 open 错误，recs_b 保持空，probe:826 只检查 `s3.get('count') is not None` ⇒ 空列表进 verdict_s3，直调 verdict_s3(20, twice, []) → **FAIL_SKEW**，文本是「两句柄看不见同一个包 ⇒ 配对法不成立」——一次取数失败被写成一条关于驱动语义的结果，且 s3_code 转 FAIL 后 A1 与 C1 的 判据 §4.3 一律 VOID_S3，整节丢掉。可检查的改法：三条件统一用集合基数，或按目击重新推导 SKEW 并写出来历（2 包 × 2 次目击 = 4），**不得复用那个按包推出的 2**；cell() 记 hb_open_err，非空时印 VOID_HANDLE_B 而不调 verdict_s3。

7. 【我独立复现，未经面板投票】A-off —— 本窗唯一要 PO 动手的那一格 —— 在任何路径上都到不了。a_off_stage(d, cells, identity_code, up_addr, up_ifidx, fb)（probe:869）的六个入参全是局部量；main() 只 `return cells, pre, opened_any`（probe:766）；__main__（probe:898-915）只调 main() 与 apply_verdicts()。更重的一环：X1 把 teardown 接进 main() 的 **finally**（probe:781），它在 apply_verdicts 印出 判据 §4.1 判词**之前**就 `sc stop WinDivert` ⇒ PO 读到 TWICE 那一行时驱动已卸、句柄已关、pre_state 已随进程作废；重开进程又会撞上 preflight 的第一跳门与 `dc != "ON_HOTSPOT"` SystemExit（热点一关必然命中）。而脚本末行（probe:908-909）明文写着「跑法：拿本轮 判据 §4.1 的判词调 a_off_stage()」——点名了一个调不出来的函数。可检查的改法：二选一 —— (a) apply_verdicts 返回 identity 后，在 tee 仍打开、同一 try/finally 内，且仅当 identity == 'TWICE' 时印「请关热点，关好后按 Enter」并阻塞 input()，格前格后各印一次 hotspot_readings 与 device_egress，teardown 挪到 A-off 之后；(b) 或删掉末行那句「跑法」，把 判据 §5／判据 §4.4 显名标为「本轮不执行」——一条不可执行的指令比没有指令更贵。

8. 【我独立复现，未经面板投票】C1 的身份判词 a2_count 写死 None（probe:807-808），而 FORWARD 层按 判据 §3 矩阵没有 A2 格、也没计划加。直调 verdict_identity(20, 20, {1:20}, None) → ('UNDECIDABLE', '…**但 A2 计数未取到** ⇒ 分不开…')。⇒ 只要转发层实测是「20 个数据报各被看见一次」（本轮两个主要可能答案之一），C1 的身份**永远**判不出来，下游连锁 判据 §4.2 UNDECIDABLE_IDENTITY、判据 §4.3 UNDECIDABLE_PREMISE —— 提权窗换来「FORWARD 全不可判，因为一格我们从没打算跑的对照没读到」，而数据本身已经回答了问题。V2 的修法把这条路径从惰性变成承重，所以它现在才致命。可检查的改法：给 verdict_identity 一个显式 has_a2_cell=False 入参，无 A2 的层返回独立的码（NO_2X_AT_THIS_LAYER），说明里不得出现「A2」；或 plan 补一格 C2（FORWARD、去 and icmp、dev_ping）。

9. 【协调方 V4 ＋ 我找到的上游】零读数通则的判别量是个常量。cell() 的 finally（probe:446）无条件 `out["shutting_down"] = True`，_reader（probe:384-393）不接收也不采样任何旗标 ⇒ 判定时该值恒真，zero_reading_ok 三个入参里唯一活的是 thread_exited，而「线程开跑就死」时它同样为真。直调 zero_reading_ok(0, True, True) → (True, '这个 0 成立')。**这直接违反本轮房规「零必须与仪器从未跑过可分」**，且是三条错误归因情景的使能条件（S1 的 NOISE_NONE 放行整层／C1′ 的 ZERO／F2 的退化支）。关于 V4 本身（格级 status 算了不消费：zero_reading_ok 的布尔只在 report_cell:543 印、noise_policy 在 864 于所有判词之后才跑、void_constants 在 765 设而无人读、count_b 不过零规则直接进 verdict_impostor）——**V4 单独也足以按住这扇窗**，因为它使「不可判」无法压制任何一条已印出的自信判词；加上上游这条，那道通则即使被消费也没有区分力。可检查的改法：_reader 拿一个 threading.Event（主线程在 Shutdown **之前** set），在 Recv 返回 FALSE 的那一瞬同线程记下 (last_error, evt.is_set(), time.time()) 并返回；cell() 的 shutting_down 取**读线程观察到的那个值**，另派生 exited_before_traffic；apply_verdicts 在印任何判词**之前**消费格级 status，不满足即印 NOT_EXECUTED 并拒判该格全部判词。

10. 【盘上已有实证】没有提权门。grep IsUserAnAdmin／shell32 在 scripts/diag/ 零命中；evidence/c_2x_decompose_20260912/stdout_20260918-194103.txt 里 `err=5` 出现 **12 次**，判定块只有一行「判据 §4.1 A1：读数或 T 取不到 ⇒ 全部不可判」——整轮无声报废，已经发生过一次。可检查的改法：preflight 第一行 `ctypes.windll.shell32.IsUserAnAdmin()` 不过即 SystemExit「未提权 ⇒ 12 格必然全 err=5」。把白烧 6 分钟变成 0 秒，一行。

11. 【当前设备状态直接命中】T 取「已发送」，能抓住设备掉线的读数已经在同一文件里却没被用。dev_ping/pc_ping（probe:600、610）只调 _sent_count 取「已发送」，收数只作为原文印一行、无人消费 ⇒ T 恒为 20（发了 20 个，不管有没有一个过得去）；而 PING_RECV（probe:200）就在同一文件里给第一道门用。judge_first_hop 与 device_egress 各只在 preflight 跑一次（grep 确认唯一调用点），其后 12 格约 6 分钟内没有任何往返复查；格后复查（probe:758-764）重跑的是 derive_constants，而 criteria:238-240 自己写着「ICS 把邻居项钉成 Permanent…『邻居项仍在』单独用就是假绿」。可检查的改法（不新增任何一次设备调用、不延长窗口）：dev_ping/pc_ping 复用 PING_RECV 同时取 (sent, recv) 并都返回；recv == 0 ⇒ 该格不给 T 并印「本格往返 N 发 0 收」；连续两格 recv == 0 ⇒ SystemExit 收尾。

## §3 Conditions（应改但不单独拦窗，16 条）

1. 判据与脚本对不上四处，且都是这四笔提交只改了一侧：①**第一道门整条不在判据里** —— grep「第一跳／往返」在 CRITERIA_PREREG.md 零命中，而它是一条能让整轮 SystemExit 的门，有三个码和一个门槛；derive_idle_seconds 与 margin_s 同理。②criteria:506-509 仍用现在时写「现有代码的空闲格只观测约 2 秒…按现状 S1／S2 把底噪低估约一个数量级」，而 IDLE_SLEEP_S 已退役 —— 按史实改写（「写于 c976ac66 之前的现态观察」），**不要就地改数字**，那会把史实改成假的；三句还用了被禁的「约」。③criteria:598 一句话两个假断言：「其中 **8 格打 adb**（挂死即上抛）⇒ 中止机会比上一轮**翻四倍**」——probe:718-723 同批已订正成 5 格、2.5 倍，错数的来源处没改；「挂死即上抛」grep 全仓只在这一处，且是假的（见下条）。④判据 §1.2 适用清单半修：X3 移出了 S1／S2，S3a/S3b 与 A1 同形却两个清单都不在，也没说明为什么。

2. run() 把 TimeoutExpired 和别的异常一起吞掉（probe:155-163 的 `except Exception`）⇒ adb ping 挂死时不抛异常，该格照常走完、T=None，而那句 `调用失败：TimeoutExpired(...)` 从未被印。五个设备格各最多 180 s，全挂即 15 分钟静默等待，PO 面前只有一个不动的光标，事后证据里没有任何一行说明原因是 adb 超时。改：超时与其它异常分开，印「⚠ <argv0> 超时 %ds，本格 T 将缺席」，并让该格带 acquisition_failed 标记进判定层（与「读数为 0」分开）。

3. 正常成功的提权跑，逐字副本里会印一行「判据 §5 FAIL：驱动未卸」。teardown()（forward_layer_probe.py）先 driver_rc()、再 teardown_labels 并立刻 print，**之后**才 stop/delete/复核；我直调 teardown_labels(0, True, 1060) 与 (0, False, 1060) 都返回 ('服务仍在（判据 §5 FAIL：驱动未卸）', '否（需手动 stop）')。X1 之前这是对的（那时 teardown 根本没被调用），现在它是清理**开始前**的一张快照，却印成判据级终局断言 —— 而一次成功的跑必然 rc==0 走到这一支。改：标签挪到清理之后用 rc2 算；清理前只印裸读数「收尾前 sc query WinDivert rc=%d」。

4. opened_any 只在 cell() 正常返回后才置真（probe:756 在 `c = cell(...)` 之后），而句柄是在 cell() 内 WinDivertOpen 成功那一刻开成、驱动此刻已装。S0 从 open 成功到返回之间有 2 秒 GRACE，期间 Ctrl+C 或任何异常都会让这条赋值被跳过 ⇒ finally 调 teardown(False, 1060) ⇒ 印「本次一个句柄都没开成 ⇒ **这不是本脚本装的**，不动它」——在服务明明是本轮装上的时候，驱动留在 PO 机器上，证据里写着本轮没装过它，下一轮的 pre_state 读到 0 于是也不敢碰。改：在 ha 非 INVALID 那一行就记账（模块级或可变对象），门＝合成「第一格 open 成功后抛异常」断言 finally 拿到 True。

5. 编译自证覆盖的 (filter, layer) 对与真正开句柄的对不上：fb@1（S2、C1）、f_imp@1（C1 第二句柄）、f_nsrc（N2）、f_noicmp（A2）都没编译过；负对照 nonsense_field==1 只在 layer=0 跑 ⇒ FORWARD 层没有任何一行证明编译器在该层有区分力。另一半是**实证不是推断**：compile_selfproof:379-380 印 `filt[:44]` 而「ip.DstAddr == 223.5.5.5 and icmp and ifIdx == 」超过 44 字符 ⇒ stdout_20260918-194103.txt 第 22、23 行逐字相同，F1 与 F2 的不同 ifIdx 本该在那里可见。改：proofs 从 plan 自动派生（使「编译过的」与「要开的」由构造相等）、负对照两层各跑一次、删掉 [:44] 整串印。

6. 自我标识在 git 不可用时 fail-open：print_self_id（probe:569-577）两处都丢掉返回码，run() 异常返回 (None, '', ...)，self_id_lines:74 的 `dirty = bool((porcelain or '').strip())` 让空串落 WORKTREE_CLEAN，文本写「下面那个提交哈希就是运行字节」而 HEAD 行是空的；criteria:165-176 明写「缺一件即拒跑」而无处 raise。另：哈希与 porcelain 只作用于 `__file__`，承载全部判词的 decompose_2x_verdicts.py 与 pkt_identity.py 可以是 ' M' 而输出里说不出来。改：rc 非 0 或 head 不是 40 位十六进制即 SystemExit；三个模块各印 SHA256 与 porcelain。

7. 起跑驱动基线不是门：criteria:41 判据 §1 抬头写「五道门，任一不过整轮作废」、判据 §1.4 指定了逐字的那一行，而 probe:687-692 印的是另一个格式，rc != 1060 时印一句就**直接落到 load()**。叠上 MECHANISM_SWEEP.md 记的本机两个不同 WinDivert 2.2 构建：若服务已由另一构建装着运行，12 格全部数在一个未经自证的驱动上，而 DLL/SYS 的 SHA256 比对验的是**盘上的文件**不是已装载的内核驱动。另 S0 格由 report_cell 印出来但 apply_verdicts 全程不读，仪器自证格没有任何后果；criteria:589-591 判据 §6-2 又把 pre_state == 0 当正当状态 —— 同一读数两种相反处置，须调和。

8. 判据 §1.3 预登记的跑中结构自检（seq 多重集须落在 1..T 内且覆盖 ≥ T−2，否则该格身份判 NOT_EXECUTED）有名字、有后果，却没有实现也没有调用者：grep distinct_seq/seq_min 只命中 pkt_identity 的字段与 probe:551-553 的打印。这正是房规「每个目标状态必须点名由谁达成」。另：1..T 是从发包数推断的值域，ping.exe 的 seq 编码本树从未实测 —— 要么实测一次记下读数，要么在 判据 §1.3 写明它是推断。

9. 判据 §4.3 那条决定整节有没有前提的守卫用了被禁的「显著」：criteria:430「n 显著偏离 2T 时本节所有带的前提已不成立」——没有数值区间、没有推导、也没有实现（probe:844-848 印 n 与带，从不把 n 与 2T 比）。上一轮终审已提过，1ad20a71 没碰它。改：写成「n 不在 [2T − 2*TOL, 2T] ⇒ VOID_N_PREMISE」，在 verdict_impostor 里实现成**先于**算带的一条分支，两个方向各设门。

10. 判据 §4.3 的两条 VOID 分支从探针这边够不着：probe:840 的 `if c and c.get("count_b") is not None:` 没有 else ⇒ 句柄 b 开失败时该格的 判据 §4.3 行根本不印，缺席产出沉默而不是 VOID（criteria:501 预登记的是 VOID）；另一条 VOID_NOT_SAME_WINDOW 不可能触发 —— 六个时刻在单线程上按严格源码次序取得（open_a < open_b < traffic_start < grace_end < close_a < close_b），是一个不可能失败的检查充当前提。改：补 else 以 num=None 调 verdict_impostor；same_window 要么改成从真可能不一致的两点取时刻，要么删掉并在 判据 §4.3 点名那个构造。

11. 空闲窗的余量 3.0s（probe:235）无推导，推导式 `target = overhead + (n_ping − 1)` 把目标格纯等待记作 19 s，而 docstring 自己引的实测是 ping 自报 19.445 s。按盘上那组数：derive_idle_seconds(12.0,3,20)=32.0 s，实测目标格 wall 29.56 s ⇒ 真实净余量 **2.44 s**（GRACE_S 两边相消；三份原始报告分别给了 0.44／2.585／24.03，全部算错，已重算）。另 probe:861 只把 S1 与 A1、S2 与 C1 各比一次，而 criteria:513 要的是「不短于**同层最长目标格**」，FORWARD 层五个目标格里最长的几乎不会是 C1；且 S1/S2 排在 plan 第 2、3 位，事后无从重定长。改：margin 由实测推出并印出来历与真实净余量；推导式改用 ping 自报时长；去掉 max(0.0,…) 钳位；noise_policy 的 target 改成同层全部目标格 window_s 的最大值并印出它来自哪一格；更稳的做法是把 S1/S2 挪到同层最后一个目标格之后。

12. verdict_h2 的退化支次序让「指向仪器」那条码在它最该响的世界里被抢走：near_c1(x) = C1−TOL <= x <= C1，C1 自己是 0 时 near_c1(0) 为真 ⇒ 第一支先命中。我枚举确认 C1=0 → DEGENERATE_UPSTREAM_ONLY。两条码都是「不可判」所以判词不翻，翻的是**理由** —— 被写成一个实体机制假说「转发层只暴露上游腿索引」，而理由会被单独抄走独立生效，下一轮去查 ifIdx 层语义，那是错的方向。附带 `F1=0 ≈ C1=0` 本身是空话。改：把 `F1==0 and F2==0` 提到三条退化支之首；C1 <= TOL 时换独立的码 VOID_NO_FORWARD_TRAFFIC。

13. apply_verdicts 在 A1 缺席时早退（probe:792-794 `return out`），把刚被分层修法变成独立的 FORWARD 那一半一起丢掉 —— C1 身份、H2、S3、N1/N2、底噪现在都显式只用各自的前提（probe:801-804、850-851 的注释逐字写着这一点），却在 NETWORK 层那个格失败时被一并跳过。改：换成逐条守卫，印「A1 不可得 ⇒ A1 的身份、A1 的 impostor 与 H4 不可判」后继续往下走。

14. 关热点之后没有任何恢复与核验步骤：grep「恢复／重开／restore」在判据、sweep、探针零命中；判据 §5 只规定怎么确认已关，判据 §6 只管 WinDivert 服务。这与 CLAUDE.md P40 实况流程第 4 条冲突，而此处被改动的是手机唯一的上行。另：热点是动态创建的虚拟卡，2026-09-15 实测重启后 ifIndex 13→14、以太 9→11 ⇒ 热点重开后 hot_ifidx 几乎必然换号。还有：criteria:556-566 把 H2 的要求值钉成「SharedAccess != Running」，而「关掉移动热点后这个服务会不会离开 Running」本树从未实测。改：开窗前在非提权只读下把热点关一次开一次，抓两遍 Get-Service SharedAccess 与 Get-NetIPAddress 192.168.137.1 写进 判据 §5-2 预登记；A-off 末尾焊进恢复段，由脚本印四行原文，第四行必须是**往返**（前三行同源、一致不构成互证）。

15. 判据 §5 的 H3（route_ifindex != upstream_ifindex）在它要分开的两个世界里读数相同：热点开着时 PC 到 223.5.5.5 的路由走上游腿，关掉后仍是上游腿 ⇒ 它只能检测「PC 自己的路由在 T0 与现在之间变了」。而 TRUE 分支把它呈现成三重合取里的一项。另：criteria:560 把 H3 的比较对象写成「判据 §2-2 现场推导出的上游腿索引」，而 判据 §2-2（criteria:246）推导的是**热点腿**，判据 §2 六条里没有一条推导上游腿 ⇒ up_ifidx 落在预登记的常量纪律之外却为 判据 §5 承重。改：docstring 的表为 H1/H2/H3 各列世界并算各世界读数；删掉 H3 或换成在开/关之间真的不同的读数；订正 criteria:560 的引用。

16. 第一道门判 OK 时印的「同协议同路径」是写死的（probe:229），而这道门刻意排在 device_egress() 之前 —— 印这句话的那一刻脚本还没有任何读数说明这次往返走的是 PC 热点这条路。排序本身是安全的（紧接的 OFF_HOTSPOT 会中止），问题在这句进了不可追改的证据，且它恰是这道门唯一的承重断言。改：文案改成由值算出的那一半（「%d 发 %d 收 ⇒ 往返成立（路径尚未判定，见下一行）」），device_egress 判 ON_HOTSPOT 后补印一行；门＝OK 文案里不得出现「同路径」除非入参带上已判定的出口态。

## §4 已确认真修好（下一版别改回去）

1. V1 为真且我独立复核：run()（probe:155-163）拿裸字节自己解，_decode（probe:116-147）三段式「utf-8 严格 → ACP 严格 → replace 并印替换符个数」，`errors="replace"` 是放大器那段 docstring —— **这个结构是对的，别推翻，要改的只有 acp 的来源那一行（136）**。

2. V2 为真且我独立复核：verdict_h2 的四码可分（VOID_T_MISSING／VOID_T_FOREIGN／VOID_T_MISMATCH／H2_HOLDS），调用点 probe:801-812 对 C1 传 c1 自己的 T 与 cc、probe:820 消费 cc，probe:850-851 的 N1／N2 用它们自己的 T 并在注释里逐字写明「**不得借用 A1 的 T 当区间基**」，以及 tn1 != tn2 时拒判 —— 这一整套分层前提是本轮最扎实的部分。

3. V3 为真且我独立复核：teardown 被 import 并在 main() 的 finally 真的调用（probe:781），且 `pre is None` 时走「无从归因，不动它」而不是一句假的「已卸载」。teardown 内四道闸（rc==1060 已干净／not opened_any／pre_state != 1060／BeanNetworkTester 在跑）方向都对；**特别保留 sc delete 的 1060 判「已自删，不是失败」那段**（forward_layer_probe.py）——那是 D-891 退出码坑的正确实现。

4. judge_first_hop（probe:203-233）：判据是「收到回复 ≥1」而不是 rc==0、不是路由存在、不是邻居项在；排在 ip route get 之前；失败文本只印读数不印解释；docstring 里「那道交叉核对的两个读数同源 ⇒ 一致不构成互证」与「不能改成 ping 热点网关」两段推理都成立。**今天盘上的 stdout_20260918-195813.txt 就是它起作用的实证**：NO_REPLY、3 发 0 收、不加载驱动、不开句柄、收尾 rc=1060 —— 这道门今天替 PO 省了一整窗，不要动它。

5. verdict_s3 的第 1 条件（活性，排 W3「根本没有流量匹配」）与第 3 条件（seq 交集，排按包切的那一半 W4），以及 docstring 里那张世界表的写法 —— 缺的只是按目击切的那一支，已有的三行不要删。

6. verdict_impostor 的 s3_ok 闸本身是活的：我直调 verdict_impostor(20,40,False,True,'TWICE') → VOID_S3。缺陷在入参来源，不在这道闸。

7. judge_hotspot_off（verdicts:299-341）的三条正对照设计与 NOT_EXECUTED／FALSE 不并成一句（「前者要重跑量法，后者要 PO 再动一次手」），以及「读不到 ⇒ 不得并进 FALSE」那段 —— 这是本文件里最好的一段，只有 H3 那一项要换。

8. verdict_identity 的 LOSS／THIRD_PARTY 两行，以及末行「不落任何一行 ⇒ 不可单判，如实记，**不取整到近的一端**」。

9. derive_idle_seconds 取代写死 IDLE_SLEEP_S 的方向（probe:235-262、563-565 的退役注释）—— 推导式与 margin 要改，但「窗长由实测推出而不是写死」这个方向是对的。

10. print_self_id 的 WORKTREE_DIRTY 分支确实在盘上的 stdout 里印出来了（stdout_20260918-195813.txt 第 2 行，原样带 git status 串）—— 这条自证在 git 可用时是活的。

11. apply_verdicts 抬头那条注释「这一行**不许印门的条数**：它会进逐字副本，而证据不可追改 —— 五份旧 stdout 里的『26 条门』有一份印出来那一刻就已经是假的」，以及 __main__ 末行「控制台里复制的那份只作旁证 —— 实测两者曾差一个字」与 tee 写 UTF-8 副本不经控制台代码页。

12. probe:766 后那段 判据 §2-6 格后复查会置 void_constants 的结构（复查对象要扩、且要有人消费，但「每个 FORWARD 格后重推常量并与基线比」这个动作本身要保留）。

## §5 Stop rules

1. 「NO_REPLY：第一跳不通：223.5.5.5 3 发 0 收 ⇒ NOT_EXECUTED」——脚本自己 SystemExit，不加载驱动、不开句柄。这是**预期的正确行为**，不是故障：去修网（po_sheet 第 2 步），不要绕过它。

2. 「UNREADABLE：第一跳：ping 摘要行读不到」——量法本身没工作（不是不通、也不是通）。停，报回来，不要重试到它碰巧读到为止。

3. 任一格出现「err=5」——未提权。**当前没有门会拦你**，只能靠眼睛：一见到就 Ctrl+C，重新用管理员 PowerShell 起。盘上的 stdout_20260918-194103.txt 里这个字串出现了 12 次，判定块只有一行，那一轮整个白烧。

4. 「🔴 解码：两种严格解码都失败，按 … replace 解，含 N 个替换符 ⇒ **由此得出的读数不可信**」——立刻 Ctrl+C。这条**只 print、不中止**，脚本会照跑到底并把每个 T 印成 None。

5. 连续两格出现「设备侧 ping 自述：（无摘要行）⇒ T=None」——设备或 adb 掉了。停。**当前没有门会拦你**；再跑下去后面每一格都会读 0，而那个 0 会被读成「转发层看不见转发包」。

6. 「打开句柄 a 失败 err=87 参数无效 —— filter 写错」——该格已烧掉且脚本不会中止。记下是哪一格、继续看完，但那一格在判定块里可能**连一行 VOID 都不印**（判据 §4.3 尤其如此），交件时要点名说明。

7. 「🔴 判据 §2-6 前后不一致 ⇒ 该格 VOID」——热点腿或上游腿在跑中变了（重启／VPN 起来／漫游）。停，整轮读数的归属已不可靠。

8. 「判据 §4.1 A1：读数或 T 取不到 ⇒ 全部不可判」——这是判定块的**唯一一行**时，本轮无产出。不要从前面印出的计数自己推结论；apply_verdicts 在这里直接 return，后面 C1／H2／S3／N／底噪一条都没跑。

9. 「🔴 中止：SystemExit(…) ⇒ 未跑完的格一律 NOT_EXECUTED，不得据已跑的格外推」——按字面执行：已跑完的格不得用来外推未跑的格。

10. 「闸一不过：判据 §4.1 判 <码> 而非 TWICE ⇒ **本格不必跑**」——这是好消息：你不用关热点。

11. 「热点未关(该格 NOT_EXECUTED，需 PO 再动手)」与「缺席不等于通过 —— …没在工作」是**两件不同的事**：前者是你再关一次手，后者是量法坏了要重跑量法。不要并成一句处理。

## §6 PO 单子（**本轮不发**，留档供修法收敛后复用）

1. **第 0 步（不是操作，是前置）**：still_blocking 那 11 条清掉之前不要开提权窗。成功判据＝执行会话交回一份**不接设备、不提权**的离线跑 stdout，里面能逐字 grep 到这两行：「preflight 量法自证：ping -n 1 127.0.0.1 ⇒ sent=1」和「提权检查：已提权」（或未提权时的 SystemExit 那一行）。这两行现在都不存在。

2. **第 1 步：先让门拒跑，不要先修网。** 手机现在只有 L2 关联、两个方向都没有 L3，第一道门必然拒。就这样跑一次（不提权也行）。成功判据＝stdout 里出现「NO_REPLY：第一跳不通：223.5.5.5 3 发 0 收 ⇒ NOT_EXECUTED」，紧接着「**不加载驱动、不开句柄、不数任何包**」，末尾「收尾…rc=1060」。这一跑证明门是活的、没在坏环境上烧任何格，且不花提权窗。**盘上的 stdout_20260918-195813.txt 已经是这一跑**——若不想重跑，直接用它。

3. **第 2 步：修网，且在 PC 侧修。** 本树对「手机关联着但一个包不过」这个症状猜过两次（AP 隔离、防火墙），真因两次都在 PC 的 WLAN／共享侧。成功判据（两条都要，缺一不算）：①在 PC 上 `ping 223.5.5.5` 能收到回复；②在**手机上**打开任意网页能出内容。**不要**用手机 WiFi 图标连着、或 PC 上「移动热点已开启」当判据——那两个正是历史上判绿而实际不通的读数。

4. **第 3 步：确认设备在 PC 的热点上而不是别的网。** 手机上打开设置看当前连的 WiFi 名，必须是 PC 那块移动热点的名字。成功判据＝名字对上；若手机自己跑去连了办公室 WiFi，第 2 步的两条判据也会过，但整轮测的就不是这条路径了。

5. **第 4 步：提权。** 开始菜单搜 PowerShell，右键「以管理员身份运行」。**不要用 Git Bash** —— Windows 原生工具的退出码在 bash 里被截成 8 位，1060（服务未安装＝干净）会读成 36，你会把一次成功读成失败。成功判据＝窗口标题栏里有「管理员」三个字。

6. **第 5 步：起跑，一条零参数命令**：`python "E:\C Project\ANEB\scripts\diag\decompose_2x_probe.py"`。成功判据＝头四行分别印出：stdout 副本文件的完整路径、WORKTREE_CLEAN 或 WORKTREE_DIRTY、一个 64 位 SHA256、一个 **40 位**的 git HEAD。**若 HEAD 那一行是空的，立刻 Ctrl+C 并报回来**——那说明 git 没取到，而脚本会把它当干净继续跑。

7. **第 6 步：跑中不要动。** 五个设备格各最长 180 秒，最坏情况光标 15 分钟不动。不要 Ctrl+C。成功判据＝最终看到「-- 判定（判据 §4…」那一行；在那之前的任何静默都算正常等待。

8. **第 7 步：读判定块。** 从「-- 判定（判据 §4」读到结束，大约十几行。成功判据＝**判据 §4.1 那一行不是**「读数或 T 取不到 ⇒ 全部不可判」。若它就是那一行，本轮没有产出，按停跑规则处理，不要试图从前面的计数自己推结论。

9. **第 8 步：热点干预（很可能不做）。** 这一格只在 判据 §4.1 印出 TWICE 时才需要你动手；印别的码就不必关热点，也不承担「关了之后 FORWARD 格不得再跑」那条硬顺序。⚠ **按当前代码，即使印了 TWICE 也没有入口可跑**（见 still_blocking 第 7 条）——所以本轮请一律按「不做」处理。若执行会话补了入口，唯一正确的做法是等脚本自己印出「请关热点，关好后按 Enter」再动手；**不要**自己去 Stop-Service SharedAccess（那是系统服务变更，属禁区）。

10. **第 9 步：恢复热点（只有第 8 步真做了才需要）。** 设置 → 网络和 Internet → 移动热点 → 打开。成功判据（两条）：①PC 上 `ipconfig` 的输出里能找到 192.168.137.1；②**手机上打开一个网页能出内容**。第 ② 条不能用图标或路由表代替。

11. **第 10 步：核验 PC 干净。** 先读 stdout 最后那行「收尾复核：rc=1060 ⇒ 已清干净」。若印的是别的，在**同一个管理员 PowerShell** 里跑 `sc.exe query WinDivert`，读它印出来的**文字**：含「指定的服务未安装」即干净。⚠ 不要去看 `$?` 或 `$LASTEXITCODE` 之外的东西，更不要在 Git Bash 里跑这条。⚠ 另：正常成功的跑**目前也会**在收尾开头印一行「判据 §5 FAIL：驱动未卸」（见 conditions 第 3 条），那是清理**开始前**的快照，**不是**结论——以最后那行复核为准。

12. **第 11 步：核验手机干净。** 手机退回华为桌面，确认能打开网页。⚠ 不要对任何提供无障碍服务的 App 用 force-stop（会被系统标记 Crashed 并整体禁用，恢复要动 secure 设置）——退回桌面或 `am kill`。

13. **第 12 步：交件。** 交**第 1 行点名的那个 stdout_*.txt 文件本身**，不要贴控制台里复制的那份（实测两者曾差一个字）。

## §7 送复核并存活的 6 条（面板有效，票可用）

1. **[high] _decode 的回退编码取自解释器 locale：UTF-8 模式下两条「严格」路是同一条 ⇒ 终审 HIGH #1 原样复发（已实跑复现）**（0/3 refuted）
   - 主张：probe:136 `acp = locale.getpreferredencoding(False) or "cp936"`。该 API 在 Python UTF-8 模式下按文档返回 'utf-8'，不是子控制台程序 ping.exe 实际输出的 ACP。于是「先 utf-8 严格、失败再按 ACP 严格」退化成同一条，落 replace 分支 ⇒ _sent_count 恒 None ⇒ 所有 PC 打的格 T=None ⇒ apply_verdicts:792 早退。`or "cp936"` 兜底救不了：'utf-8' 是真值。本机实跑同一批 cp936 字节：默认 `python` → note='按 cp936 解'、sent=20；`python -X utf8`（等同 PYTHONUTF8=1）→ note='🔴 两种严格解码都失败…42 个替换符'、**sent=None**。这条新分支没有闸（🔴 只是 print，脚本照跑到底），也没有门能看见它（probe_pure 的 _decode 用例全部在默认 locale 下跑，没有一条改变 getpreferredencoding 的返回值；且它们跑在 pytest 的解释器里而探针跑在提权壳里，两者 utf8_mode 无人比对）。上一版终审给的那条零成本正对照（preflight 里 `ping.exe -n 1 127.0.0.1` 须 _sent_count==1，否则 SystemExit）没有实现，而同一批提交为设备可达性加了第一道门——两者成本相同，只做了一个。
   - 位置：scripts/diag/decompose_2x_probe.py（_decode，回退编码 136 行）、594-613（pc_ping/dev_ping）、646-712（preflight 全段无量法自证）；门 scripts/tests/test_decompose_2x_probe_pure.py 的 _decode 四条
   - 失败情景：PO 的提权壳环境里带 PYTHONUTF8=1（或半年后机器升到 Python 3.15，PEP 686 使 UTF-8 模式成为默认）。preflight 全绿，12 个句柄全开成、每格计数都印出来，每个 PC 打的格印「PC 侧 ping 自述：（无摘要行）⇒ T=None」并多印一行 🔴 解码不可信；判定块只剩一行「判据 §4.1 A1：读数或 T 取不到 ⇒ 全部不可判」。整窗白烧，而全部证据离线一条命令就能复现——与上一轮被判 HIGH 的那次逐字同形，只是多了一句没人拦的警告。
   - 修法：(1) ACP 由**取到字节的那一层**决定：`acp = "cp%d" % ctypes.windll.kernel32.GetACP()`（本机实测 936），locale 只在 GetACP 不可用时兜底，并显式断言它 != 'utf-8'（相等即说明没有第二条路，判 NOT_EXECUTED 而不是 replace）；两者不一致本身就是读数，一并印出。(2) 把 docstring 里那个已做过的实验焊成 preflight 第一类自证：`ping.exe -n 1 127.0.0.1` 的 _sent_count != 1 即 SystemExit「量法在本解释器上不工作」——零设备零提权零秒，是唯一能把这条坑从「烧整窗」压成「preflight 一行」的动作。(3) 门里补一条用 subprocess 以 `-X utf8` 跑同一夹具的用例（同一进程内跑不出这个世界）。

2. **[high] A2 的 count 是 ICMP-only ⇒ 判据 §4.1 第 5 行（真实背景世界）结构上不可达，会被印成「本轮前提消失」**（0/3 refuted）
   - 主张：A2 的全部用途是数主 filter 的 `and icmp` 排掉的那些（criteria:282「A2 − A1 ＝ 背景非 ICMP 贡献」，判据 §4.1 第 5/6 行按 A2 ∈ [2T−2,2T] vs ∈ [T−2,T] 分两支），其 filter 是 f_noicmp = 'ip.DstAddr == 223.5.5.5'（probe:702）。但 pkt_identity.py 对 protocol != 1 一律 `return None`，_reader（probe:384-393）把这些丢进 `unparsed`，cell():465 `out["count"] = len(out["recs"])` ⇒ A2 的 count 只数 ICMP，结构上等于 A1，A2−A1 恒约等于 0，NO_2X_BACKGROUND 这一支不可达。实调现行代码：verdict_identity(20,20,{1:20},20) → NO_2X_NOT_REPRODUCED；同样读数换成真实匹配总数 verdict_identity(20,20,{1:20},40) → NO_2X_BACKGROUND。全仓搜 `count_all` 零命中。unparsed 只在 report_cell 印一行旁白，无人消费。
   - 位置：scripts/diag/decompose_2x_probe.py、465、702、745、796；scripts/diag/pkt_identity.py；criteria:282、302-303、530-532
   - 失败情景：MECHANISM_SWEEP.md 实测过一条到 223.5.5.5:443 的背景 TCP 流。设原 A=40 的真相是「20 个 ICMP ＋ 20 个背景包」：A1 去重 20、重数 1（读数完全正确）；A2 实际匹配 40 个包但 count=20（另 20 个进了 unparsed）⇒ 判定块逐字印「原 A=40 连原 filter 都不复现 ⇒ **本轮前提消失，H1/H2/H4 全部不可判**」——而 40 恰恰复现了。判据为这个世界预登记的正确处置（改写 A=40 的含义）永远够不到。「⚠ 未解析 20 条」那行在两屏之前、无人消费。读数正常、判词自信、结论完全错，且它会关掉整个 2× 分解。
   - 修法：每格加 `count_all = len(recs) + len(unparsed)`；A2 用 count_all 喂 verdict_identity，并在判词那一行**并印三个数**（匹配总数／ICMP／非 ICMP）；criteria 判据 §4.1 第 5/6 行与 判据 §4.6 末句明写「A2 计数 ＝ 该格 filter 匹配总数（含未解析）」。合成门：A1 去重 T 重数 1、A2 = 20 recs + 20 unparsed ⇒ 必须 NO_2X_BACKGROUND 而不是 NO_2X_NOT_REPRODUCED。

3. **[high] verdict_identity 的 TWICE 未按 SrcAddr 拆支，而分开这两个含义相反世界的那个字段在两个调用点都在手里、一个都没传**（0/3 refuted）
   - 主张：criteria:295-300 明写「第一行必须再按 SrcAddr 拆两支：三元组相同且 SrcAddr 相同 ⇒ 同一点被呈现两次；三元组相同而 SrcAddr 不同 ⇒ 同一数据报在两点各一次（H1 形态）」，criteria:142-145 还说把它做成 summarize() 的返回字段就是为了「它不可能只挂在判定表的一行下」。现行签名仍是 `verdict_identity(T, n_distinct, hist, a2_count=None)`（verdicts:32），没有 src 参数，TWICE 分支（verdicts:42-44）写死「同一数据报被呈现两次」。实调 verdict_identity(20,20,{2:20}) → 'TWICE'，与 src 无关。probe:797-798 与 807-808 手里有 a1['summary'] 与 c1['summary']（都带 src_same_within_key），两处都不传；该字段全程只有一个消费者 verdict_n（probe:854）。下游 verdict_h2:143、verdict_impostor:192、verdict_h4:213 全都只认字符串 'TWICE'。
   - 位置：scripts/diag/decompose_2x_verdicts.py、143、192、213；scripts/diag/decompose_2x_probe.py、807-808、854；criteria:142-145、295-300
   - 失败情景：C1 读到 20 个不同键、重数 {2:20}、src_same_within_key=False——即 NAT 前后各一次的 H1 形态，在 divert 下**不会**让延迟翻倍。判词却印「TWICE：…同一数据报被呈现两次」，那是判据留给 clone+reinject 世界的措辞，对整形器意味着相反的事（延迟翻倍，或线上多一个包——正是本实验第一页写的最坏失效）。这行字会被抄进 DECISION_LOG 与整形器设计，而 src 字段在另一行、没有消费者；H2／impostor／H4 一律照着 'TWICE' 这个串继续往下走。
   - 修法：把 src_same_within_key 变成 verdict_identity 的必填参数；TWICE 拆成 TWICE_SAME_POINT / TWICE_TWO_POINTS，None 时给 TWICE_SRC_UNKNOWN，说明文字由该值算出；两个调用点都传 summary['src_same_within_key']；criteria 判据 §4.2/判据 §4.3/判据 §4.4 点名各自接受哪些码。门：去重数与重数分布完全相同、只差 src 旗标 ⇒ 必须给出不同的码。⚠ 另注：每个键都是单例时 src_same_within_key 空真（pkt_identity.py），故必须与重数检查配套使用。

4. **[high] verdict_s3 分不开「SNIFF 是复制」与「2T 个目击被两句柄逐目击分掉」——两世界同判 PASS，而它是 判据 §4.3 的唯一前提，且正对照夹具钉下的正是分流世界的读数**（0/3 refuted）
   - 主张：criteria 判据 §1.6 与 verdicts:349-386 的世界表把 W4 写成「H_A≈T、H_B≈T、seq 交集≈0」，那只是**按数据报**切的分法。按**目击**交错切（a 拿每个数据报的第一次目击、b 拿第二次）时两边 seq 集合完全相同，交集≈T，第三条件照过。三条件里唯一能分开这两个世界的量是目击数（复制 2T、分流 T），而活性条件只给了下界 T−TOL，没有上界、也不与本层单句柄格比。实调现行代码：verdict_s3(20, 每 seq 两次共 40, 同样 40) → PASS；verdict_s3(20, 每 seq 一次共 20, 同样 20) → **PASS**。门这一侧更要紧：test_decompose_2x_verdicts.py 的 FULL = list(range(1,21)) 只有 T 个元素，被 test_s3_positive_control_copying_passes 当**正对照**钉住 ⇒ 这道门在这一维上零区分力；号称覆盖 W4 的 test_s3_four_worlds_get_four_distinct_codes（tests:298-316）把 W4 建模成 `[x+100 for x in FULL]`，那是 2T 个互不相同的包，即 DIFFERENT 世界，不是 W4。全套测试里没有任何一个重复 seq 的夹具——本实验要研究的那个 2× 世界在门里根本不存在。
   - 位置：scripts/diag/decompose_2x_verdicts.py（世界表 354-359、活性 372、配对 380-383）；夹具 scripts/tests/test_decompose_2x_verdicts.py、289-346；调用点 scripts/diag/decompose_2x_probe.py
   - 失败情景：真机上两个同 filter 句柄并不各得一份完整复制，而是把 2T 个目击分掉。S3a/S3b 都印 PASS ⇒ 本轮宣布配对法已自证 ⇒ 判据 §4.3 前提满足 ⇒ A1/C1 的 impostor 比值照算，而此时分子句柄与分母句柄看的根本不是同一批目击，比值没有意义；I 很容易落进 [0.345,0.655] ⇒ 印 IN_BAND「与『每个数据报的第二次目击是重注入』一致」。同一分流世界里 A1 单句柄只看见每包一次、A2 看见 40 ⇒ verdict_identity(20,20,{1:20},40) → NO_2X_BACKGROUND，印「原 A=40 ≈ 20 个 ICMP ＋ 背景非 ICMP」——而 40 个全是 ICMP、2× 是真的。整轮以一个自信的错分解收场，证据里还额外写着配对法已自证。
   - 修法：给 S3 补第四条件，且必须在**目击数**维度：要求 ｜seqs_a｜ 与同层单句柄格（A1，同一 T、同一打流量方式）的 count 在 ±TOL 内（分流世界里 S3a 的句柄 a 只有 A1 的一半，当场红），或比较每个 seq 在 a 与 b 中的重数分布 ｜mult_a − mult_b｜ <= 1；并把重数分布并印进逐字副本。docstring 的世界表把 W4 拆成 W4a（按 seq 切）与 W4b（按目击切）并各算读数；判据 §1.6 同表补同一行。门侧把 FULL 换成「每 seq 两次」的复制夹具，并新增反例：每 seq 一次的 20/20 必须**不**判 PASS（现在判 PASS）。

5. **[high] HIGH #2 的分层修法漏了第三个前提：C1（FORWARD 层）的 impostor 判词仍由 NETWORK 层的 S3 自证放行**（0/3 refuted）
   - 主张：b8e15166/02013d15 把跨层外推逐处修掉了（verdict_h2 收 T_C1 并加 VOID_T_FOREIGN、C1 的身份改喂 cc、verdict_n 改用 N1/N2 自己的 T）。唯独 s3_ok 没改：probe:822-834 由 S3a/S3b 算出单个 s3_code，probe:840-843 把同一个布尔 `s3_code == "PASS"` 同时喂给 ('A1', code) 与 ('C1', cc)。plan 里 S3a/S3b 都是 LAYER_NETWORK ＋ pc_ping（probe:742-743，criteria 判据 §3 矩阵两行的「层」列也都是 NETWORK），而 C1 是 LAYER_NETWORK_FORWARD（probe:746）。判据 §1.6 自己写明这道自证要证的命题「SNIFF 复制不摘走 ⇒ 同一个包可被每个匹配的句柄各看见一次」是**本方从未测过**的文档语义，判据 §7 又写明「转发层暴露的接口语义未经本方实测」——在 NETWORK 层测出它成立，不构成它在 FORWARD 层也成立。列世界：W-a 两层都复制 ⇒ C1 侧 I≈0.5；W-b NETWORK 复制、FORWARD 只给一个句柄 ⇒ C1′ 读 0。**两个世界下 s3_ok 都是 True**，它对 FORWARD 侧要分开的这两个世界完全失明。实调 verdict_impostor(20,40,False,True,'TWICE') → VOID_S3，证明这道闸本身是活的——被绕开的是它的入参来源。
   - 位置：scripts/diag/decompose_2x_probe.py（s3_code 汇总 832，两次 verdict_impostor 调用 840-848）、742-743 vs 746（plan 的层）；scripts/diag/decompose_2x_verdicts.py（s3_ok 闸）；criteria 判据 §1.6（181-221）、判据 §3 矩阵（269-292）、判据 §4.3 前提句（399-401）
   - 失败情景：S3a/S3b 在 NETWORK 层双双 PASS（PC 侧 SNIFF 确实复制）。FORWARD 层的第二个句柄因该层呈现方式不同只拿到 0 条。判定块印「判据 §1.6 两支均须过 ⇒ PASS」，紧接着「判据 §4.3 impostor（C1，n=40，带=[0.345,0.655]）⇒ ZERO：该位在本路径未观测到置位」。判据里写死的「S3 不过 ⇒ 本节整节 VOID，**不是**『impostor 为 0』，否则自证失败会被读成阴性结果」，恰好被一张在**另一层**开出的通行证绕开：一次自证缺席被印成一个阴性测量结果，而这正是整形器会建在哪一层上的那个判断。镜像方向同样成立：FORWARD 层的 S3 失败根本看不见，因为那里从没跑过 S3。
   - 修法：两条都要（缺一条就是纸面对齐）：①判据 §3 矩阵给 FORWARD 层补一对 S3（同 filter／恒真子句两支，设备打流量），判据 §4.3 写明 A1 侧消费 NETWORK 的 S3、C1 侧消费 FORWARD 的 S3；apply_verdicts 按层分别汇总 s3_code，FORWARD 侧没有 S3 就喂 False（即 VOID_S3，不是 True）。②verdict_impostor 新增 layer 入参，前提来自另一层时返回独立的 VOID_S3_FOREIGN_LAYER（与 verdict_h2 的 VOID_T_FOREIGN 同形），使调用点与函数两道都要错才放得过去。门：NETWORK 的 S3 PASS、FORWARD 的 S3 缺席 ⇒ C1 的 判据 §4.3 行不得出现 ZERO/IN_BAND。补到之前，C1 侧的 判据 §4.3 应显名标为本轮不可自证。

6. **[high] verdict_s3 按目击计数而 SKEW=2 是按包推导的；句柄 b 开失败读成 FAIL_SKEW（一句关于驱动语义的断言）而不是 VOID**（0/3 refuted）
   - 主张：verdicts:370 `na, nb = len(seqs_a), len(seqs_b)` 作用在 probe:827-828 传来的**逐目击** seq 列表（含重复），而 SKEW 的推导（verdicts:344-346）明写是按包的：「两个句柄的 open 与 shutdown 不在同一瞬间 ⇒ 开头与结尾各可能差一个包 ⇒ 上界 2」。在本实验预设的 2× 世界里一个包是两次目击，声明的「每端一个包」容差只剩半个包。实调：verdict_s3(20, twice, twice) → PASS；verdict_s3(20, twice, twice[:-3]) → FAIL_SKEW；verdict_s3(20, twice, twice[:-4]) → FAIL_SKEW（twice ＝ seq 1..20 各两次）。另一半：cell():427-429 在句柄 b 开失败时置 hb=None 且不记任何 open 错误，recs_b 保持空；probe:826 只检查 `s3.get('count') is not None` ⇒ 一个没开成的句柄 b 以空列表进入 verdict_s3：实调 verdict_s3(20, twice, []) → FAIL_SKEW，文本是「两句柄看见的数量差太多（W2）⇒ 配对法不成立」——一次取数失败被写成一条关于驱动语义的结果。
   - 位置：scripts/diag/decompose_2x_verdicts.py（SKEW 推导 344-346、na/nb 370）；scripts/diag/decompose_2x_probe.py、822-834；夹具 scripts/tests/test_decompose_2x_verdicts.py
   - 失败情景：S3a 跑起来，句柄 b 晚开几毫秒，错过第一个包的两次目击又多丢一次：na=40、nb=37 ⇒ ｜40−37｜=3 > SKEW=2 ⇒ FAIL_SKEW ⇒ probe:832 的 s3_code 变 FAIL ⇒ A1 与 C1 两格的 impostor 一律返回 VOID_S3（直调确认），整个 判据 §4.3 在这次提权窗里全丢。逐字副本里留下「同一层上的两个 SNIFF 句柄看不见同一个包」——一句否定配对法根基的断言，而真相是两毫秒的开窗偏移。句柄 b 开失败那条路径产出**完全相同的句子**，来源却是纯仪器失效。
   - 修法：要么传去重后的 seq 数（len(set(...))）让三个条件都用判据的单位（集合基数），要么按目击重新推导 SKEW 并写出来历（2 包 × 2 次目击 = 4），**不得复用那个按包推出的 2**。cell() 记下 hb_open_err；apply_verdicts 在它非空时直接印 VOID_HANDLE_B，不调 verdict_s3。夹具补：2× 世界里 b 少 3-4 次目击仍须 PASS；recs_b 为空时码不得是 FAIL_*。

## §8 未送复核的 21 条（上限 6）——按未核处理，不算被否

1. **[high] C1 的身份判词 a2_count 写死 None，而 FORWARD 层按设计没有 A2 格 ⇒ 「转发层没有 2×」这个活世界结构上判不出来，理由还指向一格永不存在的对照**
   - 主张：V2 的修法本身是真的，但它把一个**结构上解不开的分支**从「只印」变成了「承重」。probe:807-808 对 C1 调 `verdict_identity(c1["T"], …, None)`——第四个参数写死 None，因为 A2（去掉 `and icmp` 的那格）按 criteria 判据 §3 矩阵只存在于 NETWORK 层，FORWARD 层没有对应格也没有计划要加。verdict_identity:54-60 的第五行正是「去重 ∈ [T−2,T] 且重数 1 占多数」这一支：a2_count is None ⇒ 一律 UNDECIDABLE，说明写「**但 A2 计数未取到** ⇒ 分不开『背景非 ICMP』与『原 A=40 不复现』」。实调 verdict_identity(20, 20, {1:20}, None) → ('UNDECIDABLE', '…**但 A2 计数未取到**…')。⇒ 只要转发层实测是「20 个数据报各被看见一次」（本轮两个主要可能答案之一，也正是「40 不复现」该长的样子），C1 的身份**永远**判不出来。下游连锁：cc='UNDECIDABLE' ⇒ 判据 §4.2 UNDECIDABLE_IDENTITY、判据 §4.3 UNDECIDABLE_PREMISE。改之前 cc 算完即丢，这条路径是惰性的；改之后它决定 FORWARD 那一半的全部判词。
   - 位置：scripts/diag/decompose_2x_probe.py（写死 None）、820（H2 消费 cc）、845-851（impostor 消费 cc）；被卡住的分支 scripts/diag/decompose_2x_verdicts.py
   - 失败情景：提权窗一切正常，C1 开成句柄、T=20、收到 20 个目击、重数分布 {1:20}——即转发层**没有**倍增，A=40 在转发口径下不复现，一个干净、可复现、有价值的结果。逐字副本印「判据 §4.1 身份（C1，T=20）⇒ UNDECIDABLE：…**但 A2 计数未取到** ⇒ 不可单判」，随后「判据 §4.2 H2 ⇒ UNDECIDABLE_IDENTITY」「判据 §4.3 impostor ⇒ UNDECIDABLE_PREMISE」。PO 花掉的窗换来「FORWARD 全不可判，因为一格我们从没打算跑的对照没读到」，而数据本身已经回答了问题。
   - 修法：二选一并写进判据：①plan 补一格 C2（FORWARD 层、filter 去 `and icmp`、dev_ping），把它的 count 当 a2_count 传；②承认本层无 A2，给 verdict_identity 一个显式的 has_a2_cell=False 入参，让第五行在无 A2 的层返回一个**独立的码**（如 NO_2X_AT_THIS_LAYER，说明写「本层无 A2 对照 ⇒ 只能断言『本层每个数据报只被看见一次』，不能进一步归因」），而不是复用那个指向缺席读数的 UNDECIDABLE。门：合成 {1:20} ＋ 无 A2 ⇒ 码不得为 UNDECIDABLE，且说明里不得出现「A2」。

2. **[high] T 取「已发送」而每格 ping 自带的「收到几个」被丢掉；第一道门只在 T0 查一次，格后复查的是判据自己点名「单独用就是假绿」的那套配置读数**
   - 主张：judge_first_hop 的整条来历（09-13：关联在、ARP REACHABLE 而一个包不过）说的是一个**随时间变化**的量，而它只在 preflight 跑一次（probe:650-662，grep 确认全文件唯一调用点）；device_egress 同样只有一次（probe:668，唯一调用点）。其后 12 格约 6 分钟内没有任何往返复查。格后复查（probe:758-764）重跑的是 derive_constants()＋constants_verdict(k2, dsrc)：PC 侧持有 192.168.137.1 的接口数、上游腿索引、以及 **T0 缓存下来的**设备 src 是否还在热点腿邻居表里——而 criteria:238-240 自己写着「ICS 把邻居项钉成 Permanent，它不会因为设备离开而消失 ⇒『邻居项仍在』单独用就是假绿」。判据 §2-6 的前后比较（probe:763）只比 hot_ifidx，up_ifidx/up_addr/nb_kept/设备 src 都不比，且永远比的是 T0 那份 k。真正能抓住的读数**已经取到了**：PING_RECV（probe:200）就在同一文件里给第一道门用，dev_ping/pc_ping（probe:600、610）却只调 _sent_count 取「已发送」，收数只作为原文印一行、无人消费 ⇒ T 恒为 20（发了 20 个，不管有没有一个过得去）。
   - 位置：scripts/diag/decompose_2x_probe.py（pc_ping/dev_ping 只取 sent）、646-662（第一道门唯一一次）、666-674（device_egress 唯一一次）、752-765（格后只重跑 derive_constants）；criteria:236-262、判据 §5-1:538（对热点状态已要求「该格前后各印一次」）、DECISION_LOG D-880/D-906
   - 失败情景：设备在 S3b 与 A1 之间掉出热点，或进入 09-13 那个「关联在但一个包不过」的状态。第一道门早已过，格后复查照常全绿（邻居项是 Permanent、src 缓存自 preflight）。C1/F1/F2/N1/N2 的 ping 每次都印「20 packets transmitted, 0 received」而 T 仍取到 20；五格全读 0 且 shutting_down=True、线程已退出 ⇒ 零读数通则放行每一个 0。判定块印「C1 ⇒ LOSS」「H2 ⇒ 退化：指向仪器，ifIdx 语义或该 filter 增量本身不匹配」「N1/N2 ⇒ UNDECIDABLE_N2_ZERO」。回答本问题的那五格烧掉，证据把真因（设备不在场）写成转发层的 ifIdx 语义问题——下一轮会去查错的东西。
   - 修法：(1) dev_ping/pc_ping 复用已有的 PING_RECV 同时取 (sent, recv) 并都返回；recv == 0 ⇒ 该格不给 T（走已有的「缺读数就拒给 T」路径）并印「本格往返 N 发 0 收」；连续两格 recv == 0 ⇒ SystemExit 收尾，不再烧后面的格。这一改不新增任何一次设备调用、不延长窗口。(2) 把 judge_first_hop 与 device_egress 放进每个 FORWARD 格的前后（与 derive_constants 并排），NO_REPLY／UNREADABLE／非 ON_HOTSPOT ⇒ 给该格打 unreachable 标记，由 apply_verdicts 在该格所有判词前印 VOID_UNREACHABLE 并拒判——**不要只印不消费**。若嫌每格 12 秒贵，至少在 C1 之前与 N2 之后各做一次并把两次读数与时刻并印。(3) 判据 §2-6 的比较扩到 (hot_ifidx, up_ifidx, up_addr, nb_kept, 设备 src) 并与**上一格**而非只与 T0 比。

3. **[high] A-off —— 本窗唯一要 PO 动手的那一格 —— 在任何路径上都到不了，而 X1 的收尾修法把门关得更死**
   - 主张：逐环复核，全部仍成立：①a_off_stage(d, cells, identity_code, up_addr, up_ifidx, fb)（probe:869）的六个入参全是 main()/preflight() 的局部量，main() 只 `return cells, pre, opened_any`（probe:766），__main__（probe:898-915）只调 main() 与 apply_verdicts()，d／up_addr／up_ifidx／fb 进程内无处可取。②唯一能造出这些量的 preflight() 里有两道在「热点已关」状态下**必然命中**的 SystemExit：judge_first_hop 要求设备 ping 通 223.5.5.5（热点一关设备就没那条路），以及 `if dc != "ON_HOTSPOT": raise SystemExit`（probe:670-674）⇒ 重开进程也拿不到输入。③🔴 X1 的修法把 teardown(opened_any, pre) 接进 main() 的 finally（probe:781），它执行 `sc.exe stop WinDivert` 与必要时的 delete（forward_layer_probe.py），**先于** apply_verdicts 印出 判据 §4.1 判词 ⇒ PO 读到 TWICE 那行时驱动已卸、句柄已关、pre_state 已随进程作废。④tee 在 __main__ 的 finally 里 close()，此后一切输出不进逐字副本。⑤脚本末行（probe:908-909）明文把这件事交给人：「跑法：拿本轮 判据 §4.1 的判词调 a_off_stage()」——点名了一个调不出来的函数。⑥a_off_stage 内 hotspot_readings 只在格前调一次（probe:882，grep 确认无第二次），而 criteria:538 判据 §5-1 写死「由脚本在该格**前后各印一次**」；判据 §5-5 的 device_egress 三态旁证在本格根本不读。⑦仓内无 PO 操作单：docs/ 下 decompose_2x／A-off 只出现在三份 review 文档里。
   - 位置：scripts/diag/decompose_2x_probe.py、770-781、869-896、898-915、670-674；scripts/diag/forward_layer_probe.py；criteria:534-592（判据 §5 全节）、450-466（判据 §4.4）
   - 失败情景：12 格跑完、判据 §4.1 印 TWICE，PO 按纸面关热点。此刻没有命令可跑：进程已退出、tee 已关、驱动已被 teardown 停掉，重跑又在 ON_HOTSPOT 闸上被拒。要么这格根本不做（H4 与 判据 §5 整节、verdict_h4、judge_hotspot_off、hotspot_readings 全成死文本），要么 PO 在提权 REPL 里即兴：手打 load()、手敲 up_addr/up_ifidx（直接违反 判据 §0-3「常量不许写死」，而这两个数正是判据反复警告会漂的那种）、手打 identity_code='TWICE'（把要被检验的结论当入参喂进检验它的函数）。那一跑没有 SHA/HEAD 自我标识、没有 tee、没有 finally，pre_state=0 ⇒ 将来任何 teardown 都按「不是本轮装的」拒清。且格后 hotspot_readings 不存在 ⇒ 热点若在 20 个 ping 中途被 Windows 静默拉起，输出里没有任何一行能暴露它，A-off 读出重数 2 ⇒ 逐字印「DIFFERENT_CAUSE：A 的 2× 与热点无关，确为不同因，H4 成立」进证据——本实验最贵的一条结论。此时 PO 那次动手已经花掉，判据 §5-6 又禁止事后再跑任何 FORWARD 格。
   - 修法：开窗前二选一，且必须同进程：(a) apply_verdicts 返回 identity 后，在 **tee 仍打开、同一 try/finally 内**，若且仅若 identity == 'TWICE' 才印「请关热点，关好后按 Enter」并阻塞 input()；随后调 a_off_stage，格前格后各调一次 hotspot_readings 与 device_egress 并印，格后任一项非 TRUE／非 OFF_HOTSPOT ⇒ 该格 VOID；把 teardown 挪到 A-off 之后。(b) 或 `--a-off` 重入：跳过 ON_HOTSPOT 与第一跳两道闸（对本阶段按构造必然失败），改用 判据 §5 的 HOTSPOT_OFF 谓词作前提，按 判据 §5-6 重推 判据 §2 全部常量，identity 从上一份 stdout 副本读回并逐字回显。配纯函数门：identity 非 TWICE 时不得提示、不得等待。若决定本轮不做 A-off，末行那句「跑法」必须删掉或改成「本轮不提供入口」，且 判据 §5／判据 §4.4 显名标为「本轮不执行」——一条不可执行的指令比没有指令更贵。

4. **[high] 没有提权门、也没有 PO 操作单：未提权跑完 12 格只换回一行判词，而那道门零成本；起点状态（设备当前不通）本身就要 PO 即兴**
   - 主张：脚本对提权只有失败后的 err=5 提示（cell():425 的 hint），preflight 里没有任何提权检查（grep IsUserAnAdmin/shell32 在 scripts/diag/ 零命中）。实证在盘上：evidence/.../stdout_20260918-194103.txt 里 `err=5` 出现 **12 次**，判定块只有一行「判据 §4.1 A1：读数或 T 取不到 ⇒ 全部不可判」，整轮无声报废。仓内没有任何 PO 操作单：`docs/` 下 decompose_2x／A-off 只出现在三份 review 文档里，evidence/c_2x_decompose_20260912/ 只有判据、sweep 与九份 stdout；对本探针**没有一句**说怎么提权（forward_layer_probe.py 那句「管理员 PowerShell 里跑」在另一个文件、另一个脚本上）。preflight 之后没有任何东西会中止：12 个句柄全 err=5 不中止、err=87 不中止、adb 挂到超时不中止、S0 不设门、S3 FAIL 不中止、底噪超标不中止——PO 只能靠读判定块分辨整轮是否作废。而本窗的起点（任务已说设备只有 L2 关联、两个方向都没有 L3）是只有 PO 能在 PC 侧改的状态，脚本对它给出的正是 stdout_20260918-195813.txt 那一行「第一跳不通：223.5.5.5 3 发 0 收」——按判据故意只印读数不印解释（那条纪律是对的），于是 PO 手上有一个正确的读数和零条下一步。
   - 位置：scripts/diag/decompose_2x_probe.py（preflight 无提权门）、415-425（err=5 只提示）；实证 evidence/c_2x_decompose_20260912/stdout_20260918-194103.txt（12 × err=5，判定块一行）与 stdout_20260918-195813.txt（第一跳 3 发 0 收）；docs/ 下无 runsheet
   - 失败情景：PO 用 Git Bash 或计划任务起脚本（提权壳常见做法），或忘了提权：6 分钟窗只换回一行「读数或 T 取不到」，而一条 `ctypes.windll.shell32.IsUserAnAdmin()` 就能把它压成 0 秒。或 PO 拿到「3 发 0 收」后去猜——本树对这个症状的历史猜法（AP 隔离、防火墙）已被证伪过两次，真因两次都在 PC 的 WLAN 侧。或收尾时看到「服务仍在（判据 §5 FAIL：驱动未卸）」（见另一条 finding，正常跑也会印），在 Git Bash 里 `sc stop WinDivert; echo $?` 读到 36 而不是 1060（D-891 实证，退出码被截成 8 位），把成功读成失败并去手动折腾一个已经干净的服务。三处即兴本树各兑现过一次：D-884 残留驱动、D-880 设备离网、D-890 粘贴改字。
   - 修法：①preflight 第一行加提权门：`ctypes.windll.shell32.IsUserAnAdmin()` 不过即 SystemExit「未提权 ⇒ 12 格必然全 err=5」，把白烧 6 分钟变成 0 秒。②由执行会话写 evidence/c_2x_decompose_20260912/PO_RUNSHEET.md（大脑核），每一步的成功判据只引用 stdout 里能逐字 grep 的那行文本，至少覆盖：唯一提权面是右键「以管理员身份运行 PowerShell」（**不用 Git Bash**，写明理由是退出码 8 位截断）；一条零参数命令；开跑前确认设备能 ping 通目标且这一步归 PO；五条中止文本各对应什么处置；判定块该读哪几行；关/开热点的设置路径与恢复核验命令；卸驱动命令与「读文本里的 1060、不读 $?」；交件＝首行点名的 stdout 文件本身而非控制台粘贴（D-890）。

5. **[high] 零读数通则的判别量是个常量：shutting_down 在 finally 里无条件置真、读线程从不采样它 ⇒ 真零与「读线程开跑即死」在所有被判字段上逐字相同**
   - 主张：这是协调方 V4 的**上游**：V4 说格级 status 算了不消费，这一条说**即使消费了也没有区分力**。cell() 的 finally（probe:446）无条件 `out["shutting_down"] = True` 然后才 Shutdown；_reader（probe:384-393）不接收也不采样任何旗标，只在 Recv 循环退出后 append 错误码。report_cell（probe:543）事后读这个字段。⇒ 判定时 shutting_down 恒 True，zero_reading_ok 的三个入参里唯一活的是 thread_exited，而「线程开跑就死」时它同样为 True。实算 zero_reading_ok(0, True, True) → (True, '这个 0 成立')。criteria 判据 §1.1-2（56-80）要求的是读线程**在 Recv 失败的那一瞬**把错误码「与 shutting_down 一起返回」——用失败瞬间观察到的旗标分开两个世界；盘上的实现把它换成了主线程事后写的一个常量。房规「零必须与仪器从未跑过可分」在纸面上由一个不可能失败的检查满足。
   - 位置：scripts/diag/decompose_2x_probe.py（_reader 不采样）、440-452（finally 无条件置真）、543（report_cell 读它）；scripts/diag/decompose_2x_verdicts.py（zero_reading_ok）；criteria:56-80（判据 §1.1-2 与 判据 §1.1-6）
   - 失败情景：F2 的读线程第一次 WinDivertRecv 就返回 FALSE（该层/该 filter 上的意外错误，例如 ifIdx 已漂），线程带 count=0 在流量开始前 20 秒就退出。finally 置 shutting_down=True、join 立刻成功、thread_exited=True。格块印「count=0 shutting_down=True 线程已退出=True」与「零读数通则：…⇒ **这个 0 成立**」。几行后 判据 §4.2 拿这个 0 走退化支——一次纯仪器失效被改写成一条关于 ifIdx 语义的发现并被带走。同一形状对 S1（NOISE_NONE 放行整个 NETWORK 层）与 C1′（ZERO：该位未观测到置位）各兑现一次。
   - 修法：给 _reader 一个 threading.Event（主线程在 Shutdown **之前** set），在 Recv 返回 FALSE 的那一瞬同线程记下 (get_last_error(), evt.is_set(), time.time()) 三件并返回；cell() 的 shutting_down 取**读线程观察到的那个值**，另派生 exited_before_traffic = (t_exit < t_traffic_start)；句柄 b 同样做并把结果送 verdict_impostor（不满足 ⇒ VOID_MISSING，不是 ZERO）。门两个方向都要：t_exit 早于 traffic_start ⇒ 该格必须 NOT_EXECUTED；且必须有一条反方向用例证明真零仍被判成立。

6. **[medium] 五个 FORWARD 格全读 0 时判出 DEGENERATE_UPSTREAM_ONLY 而不是 DEGENERATE_BOTH_ZERO：near_c1(0) 在 C1<=TOL 时恒真，指向仪器的那条分支恰在它该响的世界里够不着**
   - 主张：verdict_h2 的退化支次序是 `near_c1(F1) and F2==0` → `F1==0 and near_c1(F2)` → `F1==0 and F2==0`，其中 near_c1(x) = C1−TOL <= x <= C1（verdicts:128）。当 C1 自己也是 0 时 near_c1(0) 为真，第一支先命中。实调枚举：C1=0/1/2 → DEGENERATE_UPSTREAM_ONLY；C1=3/4/5 → DEGENERATE_BOTH_ZERO。即：写给「仪器没活」的那条码，在「仪器没活到连 C1 都是 0」这个最彻底的世界里被另一条码抢走，而抢走它的那条码印出的是一个**实体机制假说**「转发层只暴露上游腿索引」；附带 `F1=0 ≈ C1=0` 这句本身是空话（0≈0 对任何世界都真）。门这一侧同源：test_h2_degenerate_branches_come_before_conservation（tests:74-88）三条退化支全用 C1=40，从未跑过 C1=0，所以 DEGENERATE_UPSTREAM_ONLY 的实际可达面没人核；上一轮终审文档 docs/C_2X_DECOMPOSE_REVIEW_V3_20260915.md 描述这个完全相同的场景时写的是「印 DEGENERATE_BOTH_ZERO」，即这条读数此前从未被正确算过一次。
   - 位置：scripts/diag/decompose_2x_verdicts.py；调用点 scripts/diag/decompose_2x_probe.py；门 scripts/tests/test_decompose_2x_verdicts.py
   - 失败情景：P40 在 S3/A1/A2 那几分钟里漫游到别的 WiFi（本树 09-12 发生过两次）。adb ping 照发 20 包（T=20），C1/F1/F2/N1/N2 全读 0，零读数通则放行每一个 0，每格 判据 §2 格后复核照绿。判定块印「判据 §4.2 H2 ⇒ DEGENERATE_UPSTREAM_ONLY：F1=0 ≈ C1=0 而 F2=0 ⇒ 在『H2 不成立』与『转发层只暴露上游腿索引』之间歧义」。两条码都是「不可判」所以判词本身没翻，但**理由**被写成一个关于转发层语义的机制假说——而理由会被单独抄走独立生效，下一轮去查 ifIdx 的层语义，那是错的方向。
   - 修法：把 `F1 == 0 and F2 == 0` 那一支**提到三条退化支之首**（它是最强的约束，先跑不会抢走另外两支：另外两支各要求一腿非零或 C1>TOL）。给 DEGENERATE_BOTH_ZERO 的说明加上 C1 自身的读数，并在 C1 <= TOL 时换一条独立的码（VOID_NO_FORWARD_TRAFFIC：「C1 自己也是 0 ⇒ 本层这一轮没有任何流量到达，先查设备是否在场，不得从 F1/F2 读出任何腿的语义」）。门：verdict_h2(20,0,0,0,20,20,20,'TWICE') 的码不得含 UPSTREAM_ONLY，说明里不得出现「转发层只暴露上游腿索引」。

7. **[medium] 空闲窗的余量 3.0s 无推导、推导式漏掉 ping 等末包回复的那一段；底噪比较对象是单格而判据要的是「同层最长目标格」；S1/S2 又排在所有目标格之前，事后无从重定长**
   - 主张：①derive_idle_seconds 的 margin_s=3.0（probe:235）是一个拍出来的数，房规要求每个门限是跑前钉死的精确区间并给出推导，这里没有兑现，而它要压住的量（adb 开销抖动、Android ping 等最后一个回复的 linger）方差就在秒量级。②推导式 `target = overhead + (n_ping − 1)` 把目标格纯等待记作 19 s，而 docstring 自己引的实测是 ping 自报 19.445 s（`-c 20 -i 1` 要等末包回复）⇒ 用门里那组数展开：derive_idle_seconds(12.0,3,20) = 32.0 s，实测目标格 wall 29.56 s，真实净余量 **2.44 s**（GRACE_S=2.0 两边都加、相消），不是 3 s；这个数在代码、docstring、判据、门里都没有出现过。③probe:861 只把 S1 与 A1、S2 与 C1 各比一次，而 criteria:513 判据 §4.6-1 要求空闲窗「不短于**同层最长目标格**」——FORWARD 层有五个目标格全是 dev_ping，最长的几乎不会是 C1；A2/S3a/S3b/F1/F2/N1/N2 的窗长从不参与比较。④S1/S2 排在 plan 第 2、3 位，跑在所有目标格之前，脚本没有机会按实测重定长。⑤`overhead = max(0.0, …)` 的钳位会把一个不合理的短 wall 悄悄变成看起来正常的推导。
   - 位置：scripts/diag/decompose_2x_probe.py（derive_idle_seconds，margin 235、钳位 252）、664-665（调用点）、739-741（S1/S2 在 plan 第 2、3 位）、861-866（noise_policy 只与 A1／C1 比）；scripts/diag/decompose_2x_verdicts.py（noise_policy）；criteria:504-528（判据 §4.6）
   - 失败情景：C1 那次 `adb shell ping -c 20 -i 1` 丢一两个回包（身份仍在容差内、完全合法），或 adb 开销比第一跳那次多抖了两秒多 ⇒ C1 的 window_s 越过 S2 的。判定块末尾印「判据 §4.6 S2 底噪 ⇒ SHORT_WINDOW_NO_PASS：底噪 0 ≤ 2 **但 S 窗短于目标格** ⇒ 不得用来放行任何格、也不得按速率外推」——按预登记，FORWARD 层五格全部没有底噪放行依据，而 判据 §5-6 又禁止关热点后重跑 FORWARD 格 ⇒ 回答本问题的那半个窗作废。更隐蔽的那支：C1 侥幸没超而 F1 或 N2 超了——noise_policy 根本不看它们，「S 窗不短于同层最长目标格」这条判据要求在纸上成立、在数据上不成立，输出里没有一行能暴露。（注：这条的当下表现被协调方 V4 那条「只印不消费」盖住——SHORT_WINDOW_NO_PASS 印在所有判词之后且不压制任何一条，同一份逐字副本里会同时有 H2_HOLDS 和「不得放行任何格」。）
   - 修法：①margin 由实测推出并写明来历（例如取第一道门那次 wall 的一个显式倍数，理由＝adb 开销的相对抖动），把它和真实净余量一起印进说明。②推导式改用 ping 自报时长而不是 n_ping−1（第一道门那次的 `time NNNNms` 已在 stdout 里，一行正则就能取），去掉 `-i 1` 的隐含假设；probe_n 与 `-c` 的字面量合成一个模块常量。③去掉 max(0.0,…) 钳位，wall 小于 probe_n−1 即 SystemExit。④noise_policy 的 target 改成 max(同层全部目标格的 window_s) 并印出该最大值来自哪一格，与 判据 §4.6-1 的措辞逐字对齐；配门：S2 窗 > C1 窗但 < F1 窗 ⇒ 必须 SHORT_WINDOW_NO_PASS（现在返回 NOISE_NONE）。⑤更稳的做法：把 S1/S2 挪到同层**最后一个**目标格之后跑，窗长直接取该层已实测最长窗 + 余量——「不短于」由构造成立。⑥门夹具用盘上那个真实的 12.19（stdout_20260918-195813.txt）。

8. **[medium] opened_any 只在 cell() 正常返回后才置真：中止路径上「本轮开过句柄」被丢掉 ⇒ 收尾拒清本轮自己装的驱动，并印出一句假的历史**
   - 主张：probe:756 `opened_any = opened_any or (c["count"] is not None)` 在 `c = cell(...)` 之后；句柄是在 cell() 内 WinDivertOpen 成功那一刻开成（驱动此刻已装上）。只要 cell() 里抛出异常（criteria 判据 §6-1 点名的 Ctrl+C 最典型，第一格 S0 从 open 成功到返回之间有 time.sleep(GRACE_S)=2 秒），该赋值整条被跳过，「开过句柄」这个事实只存在于已退栈的局部变量里。随后 main 的 finally 调 teardown(False, 1060)：driver_rc() 返回 0（服务在），teardown 走 `if not opened_any` 分支印「本次一个句柄都没开成 ⇒ **这不是本脚本装的**，不动它，如实报人处理」并 return——在服务明明是本轮装上的时候。改之前 finally 只算标签、从不动手，这句话没有后果；改之后（X1）它是「拒绝清理」的依据，正好是 D-884（残留驱动）那一笔。暴露面窄（S0 的窗口约 2 秒），但方向正是 X1 要修的那件事。
   - 位置：scripts/diag/decompose_2x_probe.py（初值）、753-757（赋值在 cell 返回之后）、775-781（finally 调 teardown）；被误导的闸 scripts/diag/forward_layer_probe.py
   - 失败情景：PO 提权起跑，S0 格开成句柄（驱动装上），在那 2 秒的 GRACE 里按下 Ctrl+C（或该格里任何一次 print/ctypes 抛异常）。逐字副本末尾印「服务仍在（判据 §5 FAIL：驱动未卸）」＋「本次一个句柄都没开成 ⇒ **这不是本脚本装的**，不动它，如实报人处理」。WinDivert 内核驱动留在 PO 机器上，而证据文件里写着本轮没装过它——下一轮的 pre_state 读到 0，于是那一轮也不敢碰，问题会自我延续。
   - 修法：把「开成过句柄」记在**开成的那一刻**而不是格返回之后：cell() 接一个可变的记账对象（list/dict）或在 ha 非 INVALID 那一行置模块级 _OPENED_ANY=True，main 的 finally 读它。门：合成「第一格 open 成功后抛异常」的调用，断言 finally 拿到的 opened_any 为 True（现状给 False）。另给 teardown 加一条：rc != 1060 且 pre_state == 1060 时，opened_any=False 必须印「无从归因」而不是「本轮没装过它」——后者断言的是一段 rc 与 opened_any 都承不起的历史。

9. **[medium] 正常成功的提权跑，逐字副本里会印一行「判据 §5 FAIL：驱动未卸」——X1 修法把标签留在了它不再成立的位置**
   - 主张：teardown()（forward_layer_probe.py）的第一件事是 rc = driver_rc()，第二件是 teardown_labels(rc, opened_any, pre_state) 并立刻 print，**之后**才做 sc stop／delete／复核。teardown_labels 对 rc != 1060 一律返回 ('服务仍在（判据 §5 FAIL：驱动未卸）', '否（需手动 stop）')（实调两种 opened_any 都一样）。在 X1 之前这是对的：那时 teardown() 根本没被调用，rc != 1060 确实等于「这一轮结束时驱动还在」。X1（02013d15）把真正的 stop/delete 接上之后，这两行变成了**清理开始前的一张快照**，而它印的却是一句判据级别的终局断言。而一次成功的提权跑**必然**走到这一支：句柄开过 ⇒ 服务已装 ⇒ rc == 0。
   - 位置：scripts/diag/forward_layer_probe.py（272-275 先印标签、298-316 才清理）、249-250（rc != 1060 分支）；调用点 scripts/diag/decompose_2x_probe.py
   - 失败情景：一切顺利的 6 分钟跑，PO 拿到的逐字副本里有：「-- 收尾：sc query WinDivert rc=0 ⇒ 服务仍在（判据 §5 FAIL：驱动未卸）--」「句柄关闭是否已触发 stop：否（需手动 stop）」……十几行之后才是「-- 收尾复核：rc=1060 ⇒ 已清干净 --」。PO 单（若有）与事后读者按 grep FAIL 核收这一轮，命中的是第一行；或 PO 读到「需手动 stop」当场去手动折腾一个下一秒就会被脚本自己清掉的服务——在 Git Bash 里他还会把 `sc stop` 的 1060 读成 36（D-891），于是「已经干净」被读成「清不掉」。一次成功被写成一次 FAIL，而这行字进的是不可追改的证据。
   - 修法：teardown() 里把这两行标签挪到清理**之后**，用清理后的 rc2＋opened_any＋pre_state 算；清理前那次 driver_rc() 只印裸读数（「收尾前 sc query WinDivert rc=%d」），不附任何判据级措辞。要保留「清理前服务在不在」就显名成两段：「收尾前 rc=…」与「收尾后判据 §5：…」。门：合成 rc_before=0, rc_after=1060, opened_any=True, pre_state=1060 ⇒ 输出里不得出现 FAIL。

10. **[medium] 自我标识在 git 不可用时 fail-open（空串被当成干净），且只给探针本身算哈希——整个判定层不受任何自证覆盖**
   - 主张：print_self_id（probe:569-577）做 `_, head, _ = run([...rev-parse...])` 与 `_, por, _ = run([...status --porcelain...])`，两处都丢掉返回码；run() 在任何异常下返回 (None, '', ...)（probe:162-163）。self_id_lines:74 计算 `dirty = bool((porcelain or '').strip())`，于是空串——正是 git 缺席时的取值——落 WORKTREE_CLEAN 分支（probe:80），其文本写「该文件无未提交改动 ⇒ 下面那个提交哈希就是运行字节」，而它上面印的 HEAD 行是空的。criteria:165-176 判据 §1.5 明写「第一行印三件，**缺一件即拒跑**」，而没有任何地方 raise。另：sha256_file 与 porcelain 查询都只作用于 `__file__`（probe:571-574）——decompose_2x_verdicts.py 与 pkt_identity.py 承载全部判词，它们可以是 ' M' 而输出里没有一行说得出来。
   - 位置：scripts/diag/decompose_2x_probe.py、155-163、569-577；criteria:165-176
   - 失败情景：PO 从计划任务（/RL HIGHEST）或从 PATH 里没有 git 的提权壳启动。前三行读作 WORKTREE_CLEAN、SHA256=<有效值>、「git rev-parse HEAD = 」（空）。事后读者信了 CLEAN，无从解析字节血统，而 判据 §1.5 存在的目的——暴露「这个哈希对应的不是正在跑的字节」——被藏在「CLEAN」这个词后面。若判定层当时是本地改过的，整轮输出里没有任何一行说得出来。
   - 修法：rc != 0／rc is None，或 head 不是 40 个十六进制字符 ⇒ 判 SELF_ID_UNAVAILABLE 并 SystemExit（就是判据那句「缺一件即拒跑」）。给 self_id_lines 第三个状态，配门断言 porcelain=None 或非零 rc 永不产出 CLEAN。三个模块（probe、verdicts、pkt_identity）各印 SHA256 与 porcelain，任一 ' M' 即第一行 WORKTREE_DIRTY。

11. **[medium] 起跑驱动基线不是门：rc != 1060 只印一句就往下跑；S0 这格从头到尾没有消费者；且哈希验的是盘上的文件不是已装载的内核驱动**
   - 主张：criteria:41 判据 §1 抬头是「五道门，任一不过整轮作废」，判据 §1.4（150-154）指定了逐字的那一行 `-- 起跑：sc query WinDivert rc=%d ⇒ %s --` 并写「判据＝那一行文本须为 rc=1060」。probe:688-691 印的是 `   跑格前 sc query WinDivert rc=%d ⇒ %s`（格式不同），rc != 1060 时印「服务已在 ⇒ **不是本轮装的**，收尾不得归因、不得停它」然后**直接落到 load()**，开句柄、数完 12 格。另：S0（plan 第一格，filter 'false'，probe:739）由 report_cell 印出来，但 apply_verdicts 全程不读 cells['S0']（grep 确认），也没有任何 SystemExit 绑在它上面 ⇒ 仪器自证格没有任何后果。criteria:589-591 判据 §6-2 又把 pre_state == 0 当作一个正当的、只需如实报告的状态——与 判据 §1「任一不过整轮作废」对同一个读数给出相反处置。
   - 位置：scripts/diag/decompose_2x_probe.py、739、784-794；criteria:41、150-154、589-591；MECHANISM_SWEEP.md
   - 失败情景：MECHANISM_SWEEP.md 记着本机有**两个不同的 WinDivert 2.2 构建**（Program Files 下 94,144 字节，探针按哈希钉的就是它；E:\tools\aneb-shaper\bin\ 与 \clumsy\ 下 90,288 字节）。若服务已由另一个构建装着运行（clumsy 残留、整形器还开着），sc query 返回 0，探针印那句话然后照跑。DLL/SYS 的 SHA256 比对（probe:347-353）验的是**盘上的文件**，不是已经装载在内核里的那个驱动 ⇒ 12 格全部数在一个未经自证的驱动上，而证据抬头写着哈希已符。整轮读数都被归到并没有在跑的那些字节上。
   - 修法：按 判据 §1 做成真门：rc != 1060 即 SystemExit，除非给出显式且落进日志的 override；那一行按 判据 §1.4 钉的格式印（或把 判据 §1.4 改成实际用的格式——两者取一，不要两份）。给 S0 一个判词和一个后果：count 必须为 0 且 shutting_down True、线程已退出，否则 ROUND_VOID，在读任何目标格之前。调和 判据 §1 与 判据 §6-2，让同一个读数只有一种处置。

12. **[medium] 判据 §1.3 预登记的跑中结构自检有名字、有后果，却没有实现也没有调用者**
   - 主张：criteria:148-155 判据 §1.3 预登记：「观测到的 seq 多重集须落在 1..T 内且覆盖 ≥ T−2 个不同值；不满足 ⇒ 该格身份判 NOT_EXECUTED」，并在 2026-09-18 的 X3 修法后把作用域收到全捕获格 A1/A2/C1/A-off。没有任何代码实现它：全仓 grep distinct_seq/seq_min 只命中 pkt_identity.py（字段）、probe:551-553（把它们印出来）以及 test_pkt_identity.py 里两条关于 summarize 字段自身的断言。没有任何函数把多重集与 1..T 比，decompose_2x_verdicts.py 里没有对应判词，apply_verdicts 从不去取这些字段。这正是房规「每个目标状态必须点名由谁达成，否则只是期望」——判据点名了状态（该格身份 ⇒ NOT_EXECUTED），而没有代码达成它。附带：'1..T' 是从发包数推断出来的值域，ping.exe 的 seq 编码本树从未实测，值域本身未经验证。
   - 位置：criteria:148-155；scripts/diag/decompose_2x_verdicts.py 与 scripts/diag/decompose_2x_probe.py 均无实现（只有 probe:551-553 的打印）
   - 失败情景：A1 捕到 40 次目击，其 seq 值是 0..19 或 256..275（另一种 seq 编码、计数器回绕、或混进了第二个 ping 进程）。身份键 (recv_len, ip_id, icmp_seq) 仍产出 20 个键、重数 2，于是 verdict_identity 满怀信心地印 TWICE。唯一预登记来抓这件事的检查把 seq=[0..19] 印在一行无人读的文本里，整轮在一批可能不是发出去的那些包上继续往下走。
   - 修法：在 decompose_2x_verdicts 里实现成纯函数（seq 多重集 vs 1..T，覆盖 ≥ T−TOL），在 apply_verdicts 里只对 A1/A2/C1/A-off 调用，失败时把该格身份印成 NOT_EXECUTED 而不是一个码。补三条门：落域内、落域外、覆盖不足。另：要么实测一次 ping.exe 的 seq 编码并记下读数，要么在 判据 §1.3 里写明 1..T 是推断的值域以及它若不对会长成什么样。

13. **[medium] 编译自证覆盖的 (filter, layer) 对与真正开句柄的对不上；[:44] 截断让 F1 与 F2 的自证行在逐字副本里逐字相同（盘上已有实证）**
   - 主张：preflight:703-710 编译八行：fb@0、true@0、nonsense_field==1@0(负)、f_up@1、f_hot@1、f_imp@0、f_src@1、f_taut@0。而 plan（probe:738-751）真正会被 WinDivertOpen 的对里：fb@1（S2、C1 两格）**从未编译过**；f_imp@1（C1 的第二句柄）只在 layer=0 编译过；f_nsrc（N2）**任何层都没编译过**；f_noicmp（A2）**从未编译过**。负对照 nonsense_field==1 只在 layer=0 跑 ⇒ FORWARD 层没有任何一行证明这个编译器在该层有区分力，那一层的四个 True 分不开「都合法」与「该层什么都收」；判据自己在 X6 里已写明 判据 §1.6 那张表的 FORWARD 列「无处可查」。另一半是**实证不是推断**：compile_selfproof:379-380 印 `filt[:44]`，而 `ip.DstAddr == 223.5.5.5 and icmp and ifIdx == ` 超过 44 字符 ⇒ 索引号被切掉；evidence/c_2x_decompose_20260912/stdout_20260918-194103.txt 第 22、23 行逐字相同：`compile(ip.DstAddr == 223.5.5.5 and icmp and ifIdx = layer=1) -> True  期望 True  符合预期` 出现两次，F1 与 F2 的不同 ifIdx 本该在那里可见。
   - 位置：scripts/diag/decompose_2x_probe.py（filt[:44] 在 380）、696-712（proofs 列表）、738-751（plan 的真实 filter×layer）；实证 evidence/c_2x_decompose_20260912/stdout_20260918-194103.txt:22-23；criteria:190-200、252-262
   - 失败情景：提权窗跑到第 12 格，N2 的 `ip.SrcAddr != <设备 src>` 被驱动拒收 ⇒「打开句柄 a 失败 err=87 参数无效 —— filter 写错」⇒ 该格 count=None，**不中止**，后面照跑，判定块里 判据 §4.5 直接不印（连 VOID 都没有）。一格烧掉，而这道零成本、零提权、零设备的离线自证本来就是为拦它而设的。C1′ 的 impostor@FORWARD 若被拒同样烧掉 C 侧整个 判据 §4.3，且它会以 count_b=None 的形态静默跳过。另一半：derive_constants 若因任何原因让 hot_ifidx == up_ifidx（两条腿读成同一块），自证会把同一个 filter 编译两次并印出两行看起来正常的通过行，读者数出 8/8，而 F1／F2 测的是同一件事——逐字副本里没有任何字符能区分它们（这正是盘上已经发生的那两行）。
   - 修法：①proofs 列表改成**从 plan 自动派生**：遍历每格的 (filt, layer) 与 (filt_b, layer)，去重后逐对编译，使「编译过的」与「要开的」由构造相等。②负对照 nonsense_field==1 在两层各跑一次。③删掉 filt[:44]，整串印（这一行是事后唯一能核对「当时用的是哪个索引」的产物，截掉的恰恰是唯一有区分力的那几位）；宽度有顾虑就把 ifIdx 值另起一行。④加门：编译过的 (filter, layer) 集合必须等于会被打开的那个集合。⑤判据 §1.6 那张表按 X6 自己的要求，用这一轮双层自证的真实 stdout 替换，或显名标注为未复核的整理。

14. **[medium] 判据 §4.3 的两条 VOID 分支从探针这边够不着：分子缺席被静默跳过（连 VOID 都不印），而 same_window 按构造恒真**
   - 主张：criteria:501 判据 §4.3 预登记「分子或分母任一读不到 ⇒ **VOID**——缺席不等于通过，也不等于 I == 0」，verdict_impostor:177-178 实现了 VOID_MISSING。但 probe:840 用 `if c and c.get("count_b") is not None:` 守住调用且**没有 else** ⇒ 句柄 b 开失败时（cell:427-429 置 hb=None，:467 的 `if hb is not None` 使 count_b 保持 None）该格的 判据 §4.3 行根本不印，缺席产出的是沉默而不是 VOID。另一条：VOID_NOT_SAME_WINDOW（verdict_impostor:174-176）不可能触发——same_window（probe:87-105）拿到的六个时刻在单线程上按严格源码次序取得：open_a(:416) < open_b(:426) < traffic_start(:440) < grace_end(:444) < close_a(:456) < close_b(:464)，故 `t_open_a > t_traffic_start` 与 `t_close_a < t_grace_end` 都不可能成立。这是一个不可能失败的检查，充当了一条前提。
   - 位置：scripts/diag/decompose_2x_probe.py、415-473、838-848；scripts/diag/decompose_2x_verdicts.py；criteria:501
   - 失败情景：C1 的 impostor 句柄在 FORWARD 层开失败（见编译覆盖那一条）。整轮输出里只有夹在十二格中间的一行 err=87，判定块里干脆没有「判据 §4.3 impostor（C1 …）」这一行。扫判词块的读者看到 判据 §4.1、判据 §4.2、判据 §1.6、判据 §4.5、判据 §4.6 都在、唯独 C1 没有 判据 §4.3，读起来像「不适用」而不是「仪器失败了」。与此同时，那条以「已满足的条件」形式呈现在输出里的四时刻同窗前提，从来就没有能力报告别的结果。
   - 修法：给 apply_verdicts 补 else 分支：以 num=None 调 verdict_impostor（或直接印 VOID_MISSING 与理由），使缺席永远是一个印出来的码。same_window 要么改成从真正可能不一致的两点取时刻（例如记 WinDivertOpen 的尝试时刻并与第一个包的到达时刻比），要么删掉并在 判据 §4.3 里写明同窗性由构造保证、点名那个构造——不要让一句同义反复站在「前提」的位置上。

15. **[medium] 判据 §4.3 那条决定整节有没有前提的守卫用了被禁的「显著」一词，没有区间、没有推导，也没有实现**
   - 主张：criteria:430 写「⚠ **n 必须与 T 一起印**：n 显著偏离 2T 时，本节所有带的前提（每包两次目击）已不成立」。这是决定整个 impostor 带节有没有前提的守卫，而「显著」没有数值区间、没有推导、也没有实现：probe:844-848 印 n 与带，从不把 n 与 2T 比；grep 在 decompose_2x_verdicts.py 里找不到任何这样的比较。房规是每个门限都是跑前钉死的精确区间并给出推导，且判据点名的机制必须存在并被调用。上一轮终审已提过这条（判据 §5 第 13 项），1ad20a71 那笔「判据文字六条」没有碰它。
   - 位置：criteria:430；scripts/diag/decompose_2x_probe.py；scripts/diag/decompose_2x_verdicts.py
   - 失败情景：C1 的分母 n 来到 22 而不是 40——大多数目击丢了，或该层每包只给一次目击。impostor_band(22) 照算并作为一个合法区间印出来，I = count_b/22 被放进带内或带外并被当成结果读。带所依赖的前提（每个数据报被看见两次）是假的，而唯一本该检测到这件事的东西是一份文档里的一个形容词，没有实现。
   - 修法：写成带推导的区间，例如「n 不在 [2T − 2*TOL, 2T] ⇒ 本节 VOID_N_PREMISE」，在 verdict_impostor 里实现成**先于**算带的一条分支，并两个方向都设门：n 落在边界上仍须可判、n 落在界外必须作废。

16. **[medium] 判据与脚本对不上四处，且都是这四笔提交只改了一侧：第一道门与空闲窗推导只存在于脚本；判据 §4.6 仍以现在时描述已退役的实现；判据 §6-1 的「8 格打 adb／翻四倍」与「挂死即上抛」都是假的；判据 §1.2 适用清单半修**
   - 主张：逐条核的是判据现文，不是节标题：①**第一道门整条不在判据里**——judge_first_hop 是一条能让整轮 SystemExit 的门，有三个码（OK/NO_REPLY/UNREADABLE）和一个门槛（收到 ≥1 个回复），而 CRITERIA_PREREG.md 全文对「第一跳／往返／可达」零命中，它只记在 DECISION_LOG D-906；derive_idle_seconds 同理，判据里没有这个方法、没有 margin_s。判据是本轮脚本自己抬头指名的那份「跑前写死」，两侧都必须成立。②**判据 §4.6 的现在时断言已被这批提交改成假的**：criteria:506-509 仍写「🔴 **现有代码的空闲格只观测约 2 秒，目标格约 21 秒**……⇒ **按现状 S1／S2 把底噪低估约一个数量级**」——IDLE_SLEEP_S 已退役（probe:563-565），空闲格现由 derive_idle_seconds 推出（门里那组数给 32 s）；1ad20a71 那笔「判据文字六条」没碰它，且这三句还用了被禁的「约」。③**criteria:598 一句话里有两个假断言**：「本轮 12 格、其中 **8 格打 adb**（timeout=180，**挂死即上抛**）⇒ 中止机会比上一轮**翻四倍**」——probe 的 main docstring（:718-723）在同一批里刚订正成「打 adb 的是 C1/F1/F2/N1/N2 **5 格**……那个 8 从来没对过……按 5 对 2 是 2.5 倍」，错数的来源处没改、被订正的是抄它的那一处；而「挂死即上抛」在盘上的字节里同样是假的（见 run() 吞超时那一条），grep 确认这五个字全仓只出现在 criteria:598 这一处。④**判据 §1.2 适用清单是半修**：X3 把 S1／S2 移出去了（criteria:148-152），另一半没动——S3a/S3b 是 NETWORK 层、pc_ping、句柄 a 用全 filter，与 A1 同形，既不在全捕获格清单（A1／A2／C1／A-off）里也不在窄格清单（A1′／C1′／F1／F2／N1／N2）里，也没有一句话说明为什么。
   - 位置：evidence/c_2x_decompose_20260912/CRITERIA_PREREG.md（判据 §1.2 清单缺 S3a/S3b）、506-509（已过期的现在时断言）、598（8 格／翻四倍／挂死即上抛）；脚本侧 scripts/diag/decompose_2x_probe.py（第一道门）、235-262（空闲窗推导）、563-565（IDLE_SLEEP_S 退役）、718-723（已订正的 5 格）
   - 失败情景：开窗当天脚本印 NO_REPLY 直接 SystemExit。PO 回去翻判据想知道这道门是什么、门槛是多少、失败该怎么处置——判据里一个字都没有，只能即兴（本树已兑现过三次「PO 现场即兴」的代价）。同一天另一个人读 判据 §4.6，按「空闲格只观测约 2 秒、低估一个数量级」去改脚本，把刚修好的推导改回写死。再一个人读 判据 §6-1，把「8 格打 adb」抄进下一轮的排期与超时预算（那个数从来没对过，脚本刚认过错），并按「挂死即上抛」去精简 finally——而真挂死时 run() 会吞掉超时，精简后一次真挂死就会留下装载态的驱动。
   - 修法：①给判据加一节 判据 §1.7「第一道门：同协议同路径往返」，写明命令、码集合、门槛（received >= 1，是精确区间不是「约」）、失败处置（NOT_EXECUTED，不加载驱动），并把「必须在 FORWARD 格前后各做一次」一并预登记；判据 §4.6 加一小节写空闲窗的推导式与 margin_s 的来历。②criteria:506-509 按史实改写（「写于 c976ac66 之前的现态观察；c976ac66 起空闲窗由 derive_idle_seconds 从第一跳实测推出」）——**不要就地改数字**，那会把史实改成假的。③criteria:598 的 8 改成 5、删掉「翻四倍」那句理由（结论保留）、删掉或订正「挂死即上抛」，并在同一动作里跑一次同字面全仓搜索确认没有第三处。④判据 §1.2 清单补 S3a／S3b，或写明为什么不适用。

17. **[medium] run() 把 TimeoutExpired 和别的异常一起吞掉：preflight 之后没有任何东西会中止，而超时这件事从不印出来**
   - 主张：run()（probe:155-163）的 `except Exception` 把 subprocess.TimeoutExpired 一并接住并返回 (None, '', '调用失败：…')。因此 adb shell ping（timeout=180）挂死时**不抛异常**：该格照常走完，_sent_count('') 得 None ⇒ 该格 T=None，只留一行「设备侧 ping 自述：（无 summary 行）⇒ T=None」，而 err 里那句 `调用失败：TimeoutExpired(...)` 从未被印。五个设备格各最多 180 s，全挂即 15 分钟静默等待，PO 面前只有一个不动的光标。判据 criteria:598 把「挂死即上抛」当成事实写在 finally 设计的理由里——那半是假的（见上一条）。
   - 位置：scripts/diag/decompose_2x_probe.py（run 的 except Exception）、605-613（dev_ping）；criteria:598
   - 失败情景：手机在第 8 格中途息屏／adb 抖一下，C1/F1/F2/N1/N2 里有三格的 ping 超时。三格 T=None、count 却是真的（句柄确实在数）。verdict_h2 会正确地返回 VOID_T_MISSING（那一支是安全的），但 PO 看到的是：五格计数都印出来了、判据 §4.2 印 VOID、判据 §4.5 印「T 缺席 ⇒ 不可判」，而**没有任何一行说明原因是 adb 超时**。整轮 FORWARD 侧作废，原因不可从证据里读出，且窗已经花掉。
   - 修法：run() 把 TimeoutExpired 与其它异常分开，超时时把这件事印出来（「⚠ <argv0> 超时 %ds，本格 T 将缺席」），并让该格带一个 acquisition_failed 标记进判定层（verdict_* 对它一律 VOID，与「读数为 0」分开）。PO 单里写明「五个设备格各最长 180 s，看到光标不动不要 Ctrl+C」（Ctrl+C 走 BaseException 分支会正常收尾，但 PO 现在无从知道）。

18. **[medium] 判据 §5 的 H3 在它要分开的两个世界里读数相同，且它比较的那个常量不在 判据 §2 推导的六条里**
   - 主张：judge_hotspot_off（verdicts:299-341）合取三个条件，H3 是 `route_ifindex != upstream_ifindex`（verdicts:335）。两个值来自同一个查询 `Find-NetRoute -RemoteIPAddress 223.5.5.5`——upstream_ifindex 在 preflight 时取（probe:303-310），route_ifindex 在 A-off 时取（probe:621-640）。列世界：热点开着时，PC 自己到 223.5.5.5 的路由走上游腿（热点是另一块服务下游客户端的接口）⇒ route_ifindex == upstream_ifindex；热点关掉后，不变，仍是上游腿。两个世界读数相同 ⇒ 它不是这条命题的判别器，它只能检测「PC 自己的路由在 T0 与现在之间变了」。另：criteria:560 把 H3 的比较对象写成「判据 §2-2 现场推导出的**上游腿**索引」，而 判据 §2-2（criteria:246）推导的是**热点腿**（持有 192.168.137.1 的唯一一块接口）；判据 §2 的六条里没有一条推导上游腿，于是 up_ifidx 落在预登记的常量纪律之外（没有前后复查、没有双侧交叉核对），却为 判据 §5 承重。
   - 位置：scripts/diag/decompose_2x_verdicts.py（H3 在 322-323、335-337）；scripts/diag/decompose_2x_probe.py、621-640；criteria:246、556-566
   - 失败情景：两个方向。虚高的信心：TRUE 分支印「H1 接口数 0、H2 状态 %s、H3 路由在上游腿 ifIndex=%s，三项皆满足且三个正对照皆活」，呈现成一个三重合取，而其中只有 H1 与 H2 携带任何关于热点是否已关的信息。假 FALSE：PC 的上游路由在 preflight 与 A-off 之间合法地变了（VPN 起来、以太换 WiFi——记忆文件记着两天前重启后 ifIndex 9→11、13→14）。H3 于是报「不满足：PC 到目标的路由在 ifIndex=X 而上游腿是 Y」，状态回 FALSE，PO 被派去关一个已经关掉的热点。
   - 修法：在 docstring 的表里为 H1/H2/H3 各列世界并算各世界读数；删掉 H3，或换成一个在热点开/关之间真的不同的读数（例如热点接口索引上是否还存在任何路由、或该接口是否还存在）。订正 criteria:560 的引用——要么把「推导上游腿索引与地址」加成一条显式的 判据 §2 条目并纳入前后复查，要么让 H3 引用 up_ifidx 真正的来处。

19. **[medium] apply_verdicts 在 A1 缺席时早退，把刚被分层修法变成独立的 FORWARD 那一半一起丢掉**
   - 主张：probe:792-794：`if a1 is None or a1.get('summary') is None or a1.get('T') is None: print(...); return out`。它之后的每一块——C1 自己的身份（806-812）、H2（813-821）、S3a/S3b（822-834）、N1/N2（849-860）与底噪（861-865）——现在都**显式地**只用 FORWARD 层或各自格的前提；HIGH #2 修法的全部要点（probe:801-804、850-851 的注释逐字写着）就是这些判词不得借用 A1 的。它们却在 NETWORK 层那个正对照格失败时被一并跳过。
   - 位置：scripts/diag/decompose_2x_probe.py，随后 801-865
   - 失败情景：ping.exe 被策略拦下，或 A1 的 NETWORK 句柄什么都没看见（判据自述 FORWARD 层语义未经实测，镜像方向同样可能）。A1 的 T 或 summary 为 None。整个判定块只印一行「判据 §4.1 A1：读数或 T 取不到 ⇒ 全部不可判」，提权窗结束时 C1 身份、H2、S3、N、底噪一条判词都没有——而这些读数已经采到、它们的前提也都在。整窗烧在一格上，而其余各格已不再依赖它。
   - 修法：把早退换成逐条守卫：印「判据 §4.1 A1：不可得 ⇒ A1 的身份、A1 的 impostor 与 H4 不可判」后继续进入 C1/H2/S3/N/底噪各块，它们各自已经带着自己的前提检查。

20. **[medium] 关热点之后没有任何恢复与核验步骤：手机唯一的上行被切断，脚本与判据都不管把它接回来；而 判据 §5-2 预登记的那个要求值本树从未实测过**
   - 主张：全仓搜「恢复／重开／restore／开热点」在判据、sweep、探针里零命中。criteria 判据 §5（534-592）只规定怎么**确认已关**（HOTSPOT_OFF = H1∧H2∧H3 ＋三条正对照），判据 §6（594-606）整节只管 WinDivert 服务的 stop/delete，对热点、对设备回网、对设备能否上网一行都没有。脚本同构：hotspot_readings() 只答「关了吗」，device_egress() 只在 preflight 调，收尾路径里没有任何一条读数与手机有关。这与本树常设纪律直接冲突：CLAUDE.md 的 P40 实况流程第 4 条要求「测后……恢复 stayon 等临时设置，回到华为桌面并立即复验干净」——此处被改动的是手机唯一的上行，比 stayon 重得多。另有一条只在恢复侧发作的既有实证：热点是移动热点动态创建的虚拟卡（criteria 判据 §2 抬头自述，名中 *10 是重建计数器），2026-09-15 实测重启后 ifIndex 13→14、以太 9→11 ⇒ 热点重开后 hot_ifidx 几乎必然换号，任何缓存了 `f_hot = '... and ifIdx == 13'` 的后续动作都会安静地读成 0。还有一处：criteria:556-566 把 H2 的预登记要求值钉成「SharedAccess != Running」，而「关掉移动热点后这个服务会不会离开 Running」本树从未实测。
   - 位置：criteria:534-592（判据 §5 只有关、没有开）、594-606（判据 §6 只管驱动）、556-566（H2 要求值）；scripts/diag/decompose_2x_probe.py（a_off_stage 无恢复段）、775-781（finally 只调 teardown）；CLAUDE.md P40 实况流程第 4 条
   - 失败情景：情形 A：PO 关热点做完 A-off、跑完关窗。Windows 移动热点重开后手机没自动回连（本树已发生过：D-880，设备离网导致下一会话的前提静默失败），或手机自己连去了另一张 WiFi。**没有任何产物记录离场时设备在哪张网**，下一个会话拿到一台看起来正常、实际不在热点上的手机——正是今天这一轮开不了窗的同一个坑。情形 B：HOTSPOT_OFF 判 FALSE（H1=0、H3 在上游腿，但 SharedAccess 仍读 Running）。脚本印「热点未关（该格 NOT_EXECUTED，需 PO 再动手）」，而「再动一次手」动什么没写；PO 手上只剩两条路：去 Stop-Service SharedAccess（系统服务变更，属禁区），或放弃这一格——而他刚刚已经把手机的网切了。情形 C：PO 手动把热点开回来，新虚拟卡拿到新 ifIndex；若此后有人重跑 FORWARD 格而没按 判据 §5-6 重推 判据 §2 六条，F2 会安静读 0 ⇒ 一次纯仪器失效被记成一条关于 ifIdx 语义的发现。
   - 修法：开窗前两件，都在提权窗之外零成本做：①在本机非提权只读地把热点关一次、开一次，各抓一遍 `Get-Service SharedAccess` 与 `Get-NetIPAddress 192.168.137.1`，把两个实测串写进 判据 §5-2 的预登记（现在那里写的是一个从未观测过的期望值）；若关后仍 Running，H2 降为只印读数、或改成「!= Running 或（Running 且 H1==0 且 H3 成立）」并附推导。②A-off 阶段末尾焊进恢复段（不靠记性、不靠单子）：印「请把热点开回来，按 Enter」→ 随后**由脚本**印四行原文：Get-NetIPAddress 192.168.137.1 计数、Get-Service SharedAccess、adb shell ip route get 223.5.5.5、adb shell ping -c 3 223.5.5.5 摘要；任一缺席即印「恢复未核验」并让整轮带着这句话交付。第四行必须是**往返**，理由与第一道门同一条：前三行同源、都派生自配置，一致不构成互证。

21. **[low] 第一道门判 OK 时印的「同协议同路径」是写死的，而这道门排在 device_egress() 之前——路径此刻还没有任何读数支撑**
   - 主张：judge_first_hop 的成功文案是 `"第一跳：%s %d 发 %d 收 ⇒ 往返成立，同协议同路径"`（probe:229）：「%d 发 %d 收」由值算出，「同协议同路径」是常量。而这道门被刻意排在 device_egress()（判 ON_HOTSPOT/OFF_HOTSPOT/UNREADABLE）**之前**（probe:648-662 vs 666-674）——印这句话的那一刻，脚本还没有任何读数说明这次往返走的是 PC 热点这条路。设备连着任何别的 WiFi 或蜂窝都能 3 发 3 收，照样印出「同协议同路径」。排序本身是安全的（紧接着的 OFF_HOTSPOT 会中止），问题在这句进了不可追改的逐字副本，而它恰是这道门唯一的承重断言——房规是「印在值旁边的文字必须由值算出」，以及「正确结论配错误理由，理由会被单独抄走独立生效」。
   - 位置：scripts/diag/decompose_2x_probe.py（OK 文案）；排序见 648-662（第一道门）与 666-674（device_egress）
   - 失败情景：PO 忘了让 P40 连热点，设备还在办公室 WiFi 上。逐字副本先印「OK：第一跳：223.5.5.5 3 发 3 收 ⇒ 往返成立，同协议同路径（wall=1.83s）」，两行之后印「NOT_EXECUTED：设备不在 PC 热点上（OFF_HOTSPOT）」。两行互相矛盾，而被引用、被抄走的通常是那句肯定的；下一轮有人据「第一道门已证同路径」把 device_egress 那一道当冗余删掉。
   - 修法：二选一并配门：①把 device_egress() 的三态判断提到第一道门之前（它是只读的 ip route get，零代价），只有 ON_HOTSPOT 才跑往返，OK 文案里的「同路径」随即有读数支撑；②保留现排序，文案改成由值算出的那一半——「%d 发 %d 收 ⇒ 往返成立（**路径尚未判定，见下一行 P2-pre**）」，并在 device_egress 判 ON_HOTSPOT 之后补印一行。门：断言 OK 文案里不得出现「同路径」除非入参带上已判定的出口态。

## §9 覆盖声明

本轮覆盖到的范围与它的边界：①**我没有跑过探针**——只读、无设备、未提权。六条 survivor 与三条我自己加进 still_blocking 的项，全部是在本机默认 cp936 解释器里**直调纯函数**复现的（verdict_s3 的分流世界、verdict_identity 的 src 无关与 a2=None、verdict_impostor 的 VOID_S3、zero_reading_ok(0,True,True)、teardown_labels、verdict_h2 的 C1=0 支），加上对 probe/verdicts/pkt_identity 选定行段与 forward_layer_probe.teardown 的通读。UTF-8 模式那条我只复现到 `python -X utf8` 下 locale.getpreferredencoding(False) 返回 'utf-8' 这一步，**没有在 UTF-8 模式下真跑一次探针**——从那一步到「所有 T=None」是沿着代码推出来的，不是实测的。②**我没有读的**：scripts/tests/ 下四份测试文件（关于夹具 FULL、W4 建模、h2 退化支 C1=40 的指认我是转述面板的，没有自己打开）、docs/DECISION_LOG.md D-878..D-907、MECHANISM_SWEEP.md 全文（只用了面板引的第 54 行）、docs/C_2X_DECOMPOSE_REVIEW_V3_20260915.md、forward_layer_probe.py 除 teardown 外的部分、九份 stdout 里的七份。③**13 条 finding 因上限 6 从未送去验证**——它们在面板里是**未检验**，不是被驳回。我自己额外复现了其中三条（A-off 无入口、C1 的 a2_count 写死 None、无提权门），所以把它们提进了 still_blocking；**其余十条我逐条读了但没有逐条实调**，放在 conditions 里的定级因此比六条 survivor 弱一档。若其中任何一条实际上比我判的重，代价是它会以 conditions 的身份溜进窗口。④面板 VALID（两条盲对照都按预期动作、投票有区分力），所以六条 survivor 的 0/3 refuted 是有分量的；但这个分量**只覆盖那六条**，不外延到十三条未送检的，也不外延到「除此之外没有别的」——本次没有任何一条 lens 去查「判定层之外」（tee 的实现、_open_tee 的失败路径、WinDivert ctypes 绑定的结构体布局与 ABI，后者本树 09-12 刚栽过一次 12 字节结构体对 64 字节写入的跟头）。⑤**没有跑测试套件**——「门里没有重复 seq 的夹具」「test_h2 三条退化支都用 C1=40」这两条指认我采信面板，未独立核。⑥我引的所有行号按 1ad20a71 的盘上字节核过一遍（面板原始报告里有 1~30 行的偏差，已替换）；但**行号会随下一笔提交漂**，执行会话按内容找、别按行号找。

## §10 现场（2026-09-18 核）

- `HEAD == origin == 1ad20a71`，工作树干净。驱动 `sc query WinDivert` rc=1060（python returncode 印成文本）。
- PC 于 09-16 21:29 重启；热点腿 ifIndex **13**、以太 **9** ——09-14 那次重启后曾是 14／11，**索引会振荡**，写死的常量可能偶然重新变对。
- 设备关联着热点、地址在，**L3 双向不通**：PC→公网 3/3，PC→手机 0/3，手机→公网 0/3。因果不猜（判因要动 PC 状态）。
- 证据目录 **9 份** stdout，`count=` 行合计 **0** ⇒ 至今一个包都没有过。
