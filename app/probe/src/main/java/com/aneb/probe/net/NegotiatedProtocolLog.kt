package com.aneb.probe.net

import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong

/**
 * 逐样本协商协议账本（A-8⑦／REVIEW §7.1「`AnebClient` 逐样本记 `response.protocol` 与
 * `X-Aneb-Proto` 上报（additive）」；补做理由见 D-806）。
 *
 * **为什么非记不可**：`9c646cd` 已把测量端点钉死成 HTTP/1.1（服务端 `TLSNextProto` 置空）。
 * 那证明的是「**我们设了它**」；**没有逐样本记录，就永远拿不出「它真的生效了」**——
 * **一条只设不记的钉，与一条没设的钉，在语料里长得一模一样。**
 *
 * **「逐样本」不靠调用点自觉**：[observe] 由 [AnebClient] 的 `executeCancellable` 对**每一条
 * 响应**调用一次，而那是 echo、stream、上行/下行各路、toolLoop … **全部 11 条请求路径的唯一漏斗**。
 * 新增一条请求路径也自动被记上，不需要作者记得来加一行。
 *
 * ⚠ **边界，写出来免得被读大**：
 *  - 本账本记的是**计数**，不是逐条明细 ⇒「全为 http/1.1」可直接判，**哪一条样本偏了判不出**。
 *    真出现偏离时计数非零，那时才需要另开明细面；当前验收（「全为 http/1.1」）只要计数。
 *  - **计数覆盖的是「本账本被交给了哪些 client」**，不是进程里的全部流量。挂接见 `TestEngine`。
 *
 * 线程安全：OkHttp 的响应回调跑在 dispatcher 线程上，多条并发响应会同时写这里。
 */
class NegotiatedProtocolLog {

    private val byProtocol = ConcurrentHashMap<String, AtomicLong>()
    private val byProtoHeader = ConcurrentHashMap<String, AtomicLong>()
    private val headerAbsent = AtomicLong()
    private val total = AtomicLong()

    /**
     * 记一条响应。
     *
     * @param protocol OkHttp 协商到的协议（`Response.protocol.toString()`，如 `http/1.1`、`h2`）。
     * @param protoHeader 服务端 `X-Aneb-Proto` 头（服务端侧＝`r.Proto + ";via=" + 处理栈标记）。
     *   **缺席传 null，不要传空串**：老服务端根本不发这个头（缺席），与「发了个空值」
     *   是两个状态（R-10「无事件不造数」）；两者若合并，日后没人能把它们分开。
     */
    fun observe(protocol: String, protoHeader: String?) {
        total.incrementAndGet()
        byProtocol.computeIfAbsent(protocol) { AtomicLong() }.incrementAndGet()
        if (protoHeader == null) {
            headerAbsent.incrementAndGet()
        } else {
            byProtoHeader.computeIfAbsent(protoHeader) { AtomicLong() }.incrementAndGet()
        }
    }

    /**
     * 取一份不可变快照。**按键排序**——上报体要可逐字节比对，`ConcurrentHashMap` 的
     * 迭代顺序不保证稳定，不排序会让同样的数据产出不同的 JSON。
     */
    fun snapshot(): Snapshot = Snapshot(
        samples = total.get(),
        byProtocol = byProtocol.mapValues { it.value.get() }.toSortedMap(),
        byProtoHeader = byProtoHeader.mapValues { it.value.get() }.toSortedMap(),
        headerAbsent = headerAbsent.get(),
    )

    /**
     * @param samples 观测到的响应总数。**`samples == 0` 与「块缺席」不同**：前者＝账本在位
     *   但一条响应都没有（全失败／未跑），后者＝该 run 早于本字段上线。
     * @param headerAbsent 其中**没带** `X-Aneb-Proto` 的条数。
     */
    data class Snapshot(
        val samples: Long,
        val byProtocol: Map<String, Long>,
        val byProtoHeader: Map<String, Long>,
        val headerAbsent: Long,
    )
}
