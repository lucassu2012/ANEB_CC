package com.aneb.probe.engine

import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.atomic.AtomicInteger

/**
 * [WeakNet] 锚定（crosscut B1/B2）：[WeakNet.parseContendN] 边界（抽取自 TestEngine 内联解析，
 * 行为逐位一致）+ [WeakNet.launchContendDrains] 编排（N 流启动 + 取消，两引擎共用）。
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

    // ---- launchContendDrains（B2 拥塞编排，两引擎共用） ----

    @Test
    fun `launchContendDrains starts N cancellable flows`() = runBlocking {
        val started = AtomicInteger(0)
        // 每条流跑一次 drain（自增后挂起待取消）——不忙等、可数
        val jobs = WeakNet.launchContendDrains(this, 3) {
            started.incrementAndGet(); awaitCancellation()
        }
        withTimeout(2000) { while (started.get() < 3) delay(5) } // 等 3 条全部起 drain
        assertEquals("起 3 条拥塞流", 3, jobs.size)
        assertEquals("每条各跑一次 drain", 3, started.get())
        assertTrue("取消前全部活跃", jobs.all { it.isActive })
        jobs.forEach { it.cancel() }
        jobs.forEach { it.join() }
        assertTrue("取消后全部完成、无残留活跃流", jobs.all { it.isCompleted && !it.isActive })
    }
}
