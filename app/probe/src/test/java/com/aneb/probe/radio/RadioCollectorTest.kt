package com.aneb.probe.radio

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.util.concurrent.atomic.AtomicInteger

/**
 * [RadioCollector.guardTick] 反例（D-427④/T32②）：`samplerFlow()` 循环体的异常防护
 * 策略被抽成这个独立函数，唯一理由是可测性——`samplerFlow()` 本体深度耦合
 * `Context`/`TelephonyManager`，只能真机验证；`guardTick` 不碰任何 Android API，
 * 三条行为（成功透传 / 普通异常降级 / 取消异常必须重抛不吞）在这里离线钉死。
 */
class RadioCollectorTest {

    @Test
    fun `成功路径原样透传_不触发降级或错误回调`() = runBlocking {
        val errors = AtomicInteger(0)
        val degrades = AtomicInteger(0)
        val result = RadioCollector.guardTick(
            onError = { errors.incrementAndGet() },
            degradeTo = { degrades.incrementAndGet(); -1 },
        ) { 42 }

        assertEquals(42, result)
        assertEquals("成功路径不该调 onError", 0, errors.get())
        assertEquals("成功路径不该调 degradeTo", 0, degrades.get())
    }

    @Test
    fun `普通异常被捕获降级_onError与degradeTo各调一次_异常本身带出`() = runBlocking {
        val boom = IllegalStateException("modem 抽风")
        var seenInError: Throwable? = null
        var seenInDegrade: Throwable? = null
        val result = RadioCollector.guardTick(
            onError = { t -> seenInError = t },
            degradeTo = { t -> seenInDegrade = t; "degraded" },
        ) { throw boom }

        assertEquals("degraded", result)
        assertTrue("onError 必须拿到原始异常", seenInError === boom)
        assertTrue("degradeTo 必须拿到原始异常", seenInDegrade === boom)
    }

    @Test
    fun `CancellationException 必须原样重抛_不吞_不触发降级`() = runBlocking {
        // 这条是本次修复最要紧的一条：D-427 的教训是"未捕获异常永久杀死协程"，
        // 但修法本身若吞掉取消异常，会制造一个新的、更隐蔽的挂起 bug——run 正常
        // 结束/取消时这个协程该退出却退不出。fail-closed：宁可让它继续往外抛。
        val errors = AtomicInteger(0)
        val degrades = AtomicInteger(0)
        var rethrown: Throwable? = null
        try {
            RadioCollector.guardTick(
                onError = { errors.incrementAndGet() },
                degradeTo = { degrades.incrementAndGet(); -1 },
            ) { throw CancellationException("run cancelled") }
            fail("CancellationException 应该穿透 guardTick，不该被吞掉")
        } catch (e: CancellationException) {
            rethrown = e
        }

        assertTrue("必须真的重抛出了 CancellationException", rethrown is CancellationException)
        assertEquals("重抛路径不该调 onError", 0, errors.get())
        assertEquals("重抛路径不该调 degradeTo", 0, degrades.get())
    }

    @Test
    fun `onError抛出的异常不影响degradeTo已经算出的结果_两者互相独立`() = runBlocking {
        // 不是本次修复要解决的形状，但既然把两个回调拆开传，就该确认它们互不依赖
        // 对方的执行顺序副作用——onError 先跑、degradeTo 后跑，一旦以后有人把两者
        // 顺序换了或合并成一个回调，这条测试会先红。
        var order = ""
        RadioCollector.guardTick(
            onError = { order += "E" },
            degradeTo = { order += "D"; 0 },
        ) { throw RuntimeException("x") }
        assertEquals("onError 必须先于 degradeTo 执行", "ED", order)
        assertFalse(order.isEmpty())
    }
}
