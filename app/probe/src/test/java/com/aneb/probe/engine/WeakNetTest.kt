package com.aneb.probe.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * [WeakNet.parseContendN] 边界锚定（B1，抽取自 TestEngine 内联解析，行为逐位一致）。
 */
class WeakNetTest {

    @Test
    fun `parses contend N in range`() {
        assertEquals(4, WeakNet.parseContendN("contend:4"))
        assertEquals(1, WeakNet.parseContendN("contend:1"))
        assertEquals(8, WeakNet.parseContendN("contend:8"))
    }

    @Test
    fun `clamps to 1 and 8`() {
        assertEquals(1, WeakNet.parseContendN("contend:0")) // 0 抬到下限 1
        assertEquals(1, WeakNet.parseContendN("contend:-3")) // 负数钳到 1
        assertEquals(8, WeakNet.parseContendN("contend:9")) // 超上限钳到 8
        assertEquals(8, WeakNet.parseContendN("contend:100"))
    }

    @Test
    fun `trims surrounding whitespace`() {
        assertEquals(3, WeakNet.parseContendN("contend: 3 "))
    }

    @Test
    fun `null or non-contend or non-numeric yields null`() {
        assertNull("null → 不启拥塞", WeakNet.parseContendN(null))
        assertNull("无 contend: 前缀 → 不启", WeakNet.parseContendN("rsrp:-110"))
        assertNull("空值 → 不启", WeakNet.parseContendN("contend:"))
        assertNull("非数字 → 不启", WeakNet.parseContendN("contend:abc"))
    }
}
