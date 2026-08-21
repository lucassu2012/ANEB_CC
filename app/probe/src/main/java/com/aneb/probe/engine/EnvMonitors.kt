package com.aneb.probe.engine

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.PowerManager
import android.os.SystemClock
import com.aneb.probe.data.EnvEvent
import com.aneb.probe.data.EnvEventType
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import java.util.concurrent.Executor

/**
 * 设备侧环境监控（R-12/R-16，设计文档 §4.10），三路监控统一输出到 [events]：
 *
 * 1. 热状态：PowerManager.addThermalStatusListener（API 29+，minSdk 29 直接用），
 *    每次迁移记 THERMAL 事件，SEVERE 及以上标 polluting=true（污染标，R-11）。
 * 2. 省电/Doze：ACTION_POWER_SAVE_MODE_CHANGED / ACTION_DEVICE_IDLE_MODE_CHANGED
 *    广播贯穿测试全程监听（守卫从测前一次性快照升级为持续监控，R-12——
 *    设备侧冻结必须能与链路缓冲区分，否则批化自检会把 Doze 误归因为运营商中间盒）。
 * 3. 10ms 哨兵线程：独立线程周期打戳，相邻戳间隔 >30ms 记 APP_JANK 事件
 *    （进程级停顿证据，R-16；与 token 时间轴对齐后重叠 ITL 样本标 app_contaminated）。
 *
 * start()/stop() 幂等配对；事件时间戳一律 SystemClock.elapsedRealtimeNanos。
 * 本类只产事件，不做判定——三态 Gate 的 invalid/污染判定由 TestEngine 接线（后续批次）。
 */
class EnvMonitors(private val context: Context) {

    private val directExecutor = Executor { it.run() }

    // replay=4（省电态判据·先数后建，08-22）：start() 里那三条 initial 事件
    // （THERMAL/POWER_SAVE/DOZE，注释明言「初始状态显式入时间轴，区分无事件与未监控」）
    // **从未真正进过时间轴**——TestEngine 先调 start()（同步 tryEmit）后 launch collect，
    // 而 replay=0 的 SharedFlow 在零订阅者时事件直接消失。真机实证：voice30 库 19 run
    // 的 env_event 里非 initial 事件 9243 条（APP_JANK/THERMAL/PATH_CHANGE…链路通畅），
    // initial 全类 = 0 —— 写下的意图没有守卫，随启动时序静默漂移（D-267 形状）。
    // 修法选 replay 而非调换 start/collect 顺序：launch 的订阅挂载是异步的，调序
    // 只是把窗口变小，不是关掉。EnvMonitors 每 run 新建实例（TestEngine 局部 val），
    // replay 无跨 run 泄漏；4 = initial 三条 + 1 余量，且 initial 与 collect 挂载之间
    // 无异步回调可插队，不会被挤出 replay 缓存。
    private val _events = MutableSharedFlow<EnvEvent>(
        replay = 4,
        extraBufferCapacity = 256,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )

    /** THERMAL / POWER_SAVE / DOZE / APP_JANK 统一事件流 */
    val events: SharedFlow<EnvEvent> = _events

    private var thermalListener: PowerManager.OnThermalStatusChangedListener? = null
    private var receiver: BroadcastReceiver? = null

    @Volatile
    private var sentinel: Thread? = null

    fun start() {
        if (sentinel != null) return // 幂等

        val pm = context.getSystemService(PowerManager::class.java)

        // ---- 1. 热状态（R-11/R-12） ----
        if (pm != null) {
            val listener = PowerManager.OnThermalStatusChangedListener { status -> emitThermal(status) }
            try {
                pm.addThermalStatusListener(directExecutor, listener)
                thermalListener = listener
            } catch (t: Throwable) {
                _events.tryEmit(
                    EnvEvent(now(), EnvEventType.THERMAL, "listener_registration_failed: $t"),
                )
            }
            // 初始状态显式入时间轴（区分「无事件」与「未监控」）
            emitThermal(
                try {
                    pm.currentThermalStatus
                } catch (t: Throwable) {
                    PowerManager.THERMAL_STATUS_NONE
                },
                initial = true,
            )
            _events.tryEmit(EnvEvent(now(), EnvEventType.POWER_SAVE, "initial power_save=${pm.isPowerSaveMode}"))
            _events.tryEmit(EnvEvent(now(), EnvEventType.DOZE, "initial device_idle=${pm.isDeviceIdleMode}"))
        } else {
            _events.tryEmit(EnvEvent(now(), EnvEventType.THERMAL, "power_manager_unavailable"))
        }

        // ---- 2. 省电/Doze 广播（R-12：测中持续监控） ----
        val r = object : BroadcastReceiver() {
            override fun onReceive(ctx: Context?, intent: Intent?) {
                val p = context.getSystemService(PowerManager::class.java)
                when (intent?.action) {
                    PowerManager.ACTION_POWER_SAVE_MODE_CHANGED ->
                        _events.tryEmit(
                            EnvEvent(now(), EnvEventType.POWER_SAVE, "power_save=${p?.isPowerSaveMode}"),
                        )
                    PowerManager.ACTION_DEVICE_IDLE_MODE_CHANGED ->
                        _events.tryEmit(
                            EnvEvent(now(), EnvEventType.DOZE, "device_idle=${p?.isDeviceIdleMode}"),
                        )
                }
            }
        }
        try {
            // 均为受保护系统广播，无导出面；targetSdk 34+ 的 RECEIVER_* 标志要求不适用于纯系统广播
            context.registerReceiver(
                r,
                IntentFilter().apply {
                    addAction(PowerManager.ACTION_POWER_SAVE_MODE_CHANGED)
                    addAction(PowerManager.ACTION_DEVICE_IDLE_MODE_CHANGED)
                },
            )
            receiver = r
        } catch (t: Throwable) {
            _events.tryEmit(EnvEvent(now(), EnvEventType.DOZE, "receiver_registration_failed: $t"))
        }

        // ---- 3. 10ms 哨兵线程（R-16） ----
        val t = Thread(
            {
                var last = SystemClock.elapsedRealtimeNanos()
                while (!Thread.currentThread().isInterrupted) {
                    try {
                        Thread.sleep(SENTINEL_PERIOD_MS)
                    } catch (ie: InterruptedException) {
                        return@Thread
                    }
                    val nowNs = SystemClock.elapsedRealtimeNanos()
                    val gapNs = nowNs - last
                    if (gapNs > JANK_THRESHOLD_NS) {
                        _events.tryEmit(
                            EnvEvent(
                                nowNs,
                                EnvEventType.APP_JANK,
                                "gap_ms=${gapNs / 1_000_000} expected_ms=$SENTINEL_PERIOD_MS " +
                                    "threshold_ms=${JANK_THRESHOLD_NS / 1_000_000}",
                            ),
                        )
                    }
                    last = nowNs
                }
            },
            "aneb-jank-sentinel",
        )
        t.isDaemon = true
        t.start()
        sentinel = t
    }

    fun stop() {
        sentinel?.interrupt()
        sentinel = null
        receiver?.let { runCatching { context.unregisterReceiver(it) } }
        receiver = null
        thermalListener?.let { l ->
            runCatching {
                context.getSystemService(PowerManager::class.java)?.removeThermalStatusListener(l)
            }
        }
        thermalListener = null
    }

    private fun emitThermal(status: Int, initial: Boolean = false) {
        val polluting = status >= PowerManager.THERMAL_STATUS_SEVERE // SEVERE+ = 污染事件（R-11）
        val prefix = if (initial) "initial " else ""
        _events.tryEmit(
            EnvEvent(now(), EnvEventType.THERMAL, "${prefix}status=${thermalName(status)} polluting=$polluting"),
        )
    }

    private fun thermalName(status: Int): String = when (status) {
        PowerManager.THERMAL_STATUS_NONE -> "none"
        PowerManager.THERMAL_STATUS_LIGHT -> "light"
        PowerManager.THERMAL_STATUS_MODERATE -> "moderate"
        PowerManager.THERMAL_STATUS_SEVERE -> "severe"
        PowerManager.THERMAL_STATUS_CRITICAL -> "critical"
        PowerManager.THERMAL_STATUS_EMERGENCY -> "emergency"
        PowerManager.THERMAL_STATUS_SHUTDOWN -> "shutdown"
        else -> "status($status)"
    }

    private fun now(): Long = SystemClock.elapsedRealtimeNanos()

    companion object {
        private const val SENTINEL_PERIOD_MS = 10L
        private const val JANK_THRESHOLD_NS = 30_000_000L // >30ms 记 APP_JANK（§4.10）
    }
}
