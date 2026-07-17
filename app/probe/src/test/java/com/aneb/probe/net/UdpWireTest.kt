package com.aneb.probe.net

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * UDP ANEB1 探针 wire 编解码单测（纯 JVM）。
 *
 * 合同：服务端对 `ANEB1` 开头且总长 >5 的 UDP 包整包原样回显，不解析布局；
 * 客户端自定 17B 布局＝`ANEB1`(5B ASCII) + u32 seq BE(4B) + u64 tsNanos BE(8B)，
 * 回显后自行按 seq 对账。坏包（magic 错/长度不足）→ null（R-10 不折成样本）。
 */
class UdpWireTest {

    @Test
    fun `encode 布局逐字节：ANEB1 + u32 seq BE + u64 ts BE = 17B`() {
        val b = UdpWire.encode(0x01020304, 0x1122334455667788L)
        assertEquals(UdpWire.PACKET_BYTES, b.size)
        assertEquals(17, b.size)
        // magic "ANEB1"（ASCII 0x41 0x4E 0x45 0x42 0x31）
        assertArrayEquals(byteArrayOf(0x41, 0x4E, 0x45, 0x42, 0x31), b.copyOfRange(0, 5))
        // u32 seq 大端
        assertArrayEquals(byteArrayOf(0x01, 0x02, 0x03, 0x04), b.copyOfRange(5, 9))
        // u64 tsNanos 大端
        assertArrayEquals(
            byteArrayOf(0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88.toByte()),
            b.copyOfRange(9, 17),
        )
    }

    @Test
    fun `decode 往返恒等：含 seq 高位与负 ts 边界`() {
        val cases = listOf(
            0 to 0L,
            1 to 1L,
            0x01020304 to 0x1122334455667788L,
            Int.MAX_VALUE to Long.MAX_VALUE,
            -1 to -1L, // u32 0xFFFFFFFF / u64 0xFF..FF 按位往返
            Int.MIN_VALUE to Long.MIN_VALUE,
        )
        for ((seq, ts) in cases) {
            assertEquals(seq to ts, UdpWire.decode(UdpWire.encode(seq, ts)))
        }
    }

    @Test
    fun `magic 校验失败返回 null`() {
        val good = UdpWire.encode(7, 42L)
        // 首字节损坏
        val bad1 = good.copyOf().also { it[0] = 0x42 }
        assertNull(UdpWire.decode(bad1))
        // 版本位损坏（"ANEB2"）
        val bad2 = good.copyOf().also { it[4] = 0x32 }
        assertNull(UdpWire.decode(bad2))
    }

    @Test
    fun `长度不足返回 null：裸 magic 与 16B 截断`() {
        assertNull(UdpWire.decode(byteArrayOf(0x41, 0x4E, 0x45, 0x42, 0x31))) // 裸 5B magic
        assertNull(UdpWire.decode(UdpWire.encode(7, 42L).copyOfRange(0, 16))) // 差 1 字节
        assertNull(UdpWire.decode(ByteArray(0)))
    }

    @Test
    fun `超长包忽略尾部字节（服务端整包回显语义）`() {
        val padded = UdpWire.encode(9, 100L) + byteArrayOf(0x00, 0x7F)
        assertEquals(9 to 100L, UdpWire.decode(padded))
    }
}
