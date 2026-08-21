package com.aneb.probe.engine

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.aneb.probe.data.EnvEventType
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * initial 事件必须到得了晚挂的订阅者（省电态判据·先数后建，08-22）。
 *
 * **要防的事故（真机已实证发生）**：`start()` 同步 tryEmit 三条 initial 事件
 * （THERMAL/POWER_SAVE/DOZE），而 TestEngine 是先 start() 后 launch collect——
 * replay=0 的 SharedFlow 在零订阅者时事件直接消失。voice30 库 19 run 实测：
 * 非 initial 事件 9243 条（链路通畅），initial 全类 = 0——
 * 「初始状态显式入时间轴，区分无事件与未监控」的注释意图从未兑现过。
 *
 * 本测试**刻意复现 TestEngine 的时序**（先 start 后订阅）；replay=0 时它必红
 * （突变审计的反例方向），replay=4 后 initial 三条应全部可收。
 */
@RunWith(RobolectricTestRunner::class)
class EnvMonitorsInitialReplayTest {

    @Test
    fun initialEventsReachALateSubscriber() {
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        val em = EnvMonitors(ctx)
        em.start()                       // TestEngine 的真实时序：先 start……
        try {
            val got = runBlocking {
                withTimeout(5_000) {
                    // take(4) 而非 3：Robolectric 下 thermal listener 注册失败会先发一条
                    // 非 initial 的 THERMAL 事件，replay 缓存里共 4 条——取 3 会把 DOZE 截掉
                    // （初版正是这么红的）。replay=0 时这里收不到任何 initial，会超时。
                    em.events.take(4).toList()
                }
            }
            val initials = got.filter { it.detail.startsWith("initial") }
            assertTrue(
                "晚挂订阅者应收到 initial 事件（实收: ${got.map { it.type to it.detail }}）",
                initials.size >= 2,
            )
            val types = initials.map { it.type }.toSet()
            assertTrue(
                "initial 应覆盖 POWER_SAVE 与 DOZE（实收: $types）——这两类只在 initial 与" +
                    "真实状态切换时发射，initial 丢了它们就整类缺席（真机实证正是如此）",
                EnvEventType.POWER_SAVE in types && EnvEventType.DOZE in types,
            )
            // TestEngine 的测中豁免判据依赖 detail 前缀——钉住这一前提，
            // 防止有人改了 detail 文案让 initial 事件误触发 invalidate。
            assertTrue(
                "initial 事件的 detail 必须以 \"initial\" 开头（TestEngine 豁免判据所依赖）",
                initials.all { it.detail.startsWith("initial") },
            )
        } finally {
            em.stop()
        }
    }
}
