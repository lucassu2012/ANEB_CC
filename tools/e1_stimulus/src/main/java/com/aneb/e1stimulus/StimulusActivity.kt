package com.aneb.e1stimulus

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.TextView

/**
 * E1 已知真值刺激源（`spec/adapters/INSTRUMENTATION_SPEC.md` §3.3 实验 E1 的刺激侧）。
 *
 * ## 它解决的问题
 *
 * 真实 App 的"真值"我们不知道，所以不能拿真实 App 量打点误差（spec §3.3 E1 原理）。
 * 本 Activity 是一个**真值已知**的被观测对象：它在自己选定的时刻把一块 ROI 由 A 变 B，
 * 并把该次变化的时戳打进 logcat。观测通道看到的时刻减去这里打出的时刻，就是误差。
 *
 * ## 一次翻转 = 三样东西同时变，供三条通道各自看见
 *
 * 1. **ROI 背景色** A↔B（高对比黑/白）—— 通道 B（screencap 帧差）看这个；
 * 2. **TextView 文本** `seq=<n>` —— 通道 A（无障碍事件）看这个，
 *    因为纯色块变化不派发 `TYPE_VIEW_TEXT_CHANGED`；
 * 3. 二者在**同一帧**提交 —— 通道 C（渲染时间线）看这一帧。
 *
 * 三者共帧是本设计的要点：若分帧，三条通道量的就不是同一个事件，互相之差里会混进
 * 一个我们自己制造的偏移。
 *
 * ## 两个时钟都打（这是本装置最要紧的一条）
 *
 * - `SystemClock.elapsedRealtimeNanos()` = **CLOCK_BOOTTIME**（含深睡）——
 *   `AnebAccessibilityService` / `ObsStats` 用的就是它（D-49），故通道 A 是这个基。
 * - `System.nanoTime()` = **CLOCK_MONOTONIC**（不含深睡）——
 *   SurfaceFlinger / gfxinfo 的帧时戳是这个基。
 *
 * 两者相差"自开机以来累计的深睡时长"，且该差**会随时间增长**。
 * 通道 A 与通道 C 的时戳因此**不能直接相减**。本装置每次翻转把两个时钟一起打出来，
 * 分析侧据此换算——这也是 spec §3.2「E_clock 已有界」那句话的**修正条件**：
 * 它对"只有通道 A"成立，一旦通道 C 入场就不再成立（详见 tools/e1/README.md）。
 *
 * ## 用法
 *
 * ```
 * am start -n com.aneb.e1stimulus/.StimulusActivity \
 *   --ei interval_ms 2000 --ei count 30 --ei roi_px 480 --ei warmup 3
 * ```
 *
 * `interval_ms` 必须**远大于一帧**（默认 2000ms vs 16.7ms@60Hz）：分析侧要按
 * "翻转后最近的一帧"对齐，翻转间隔小于帧周期时该对齐是二义的。
 *
 * ## 红线
 *
 * 本工程零权限、不联网、不落盘、不读任何其它 App 的内容。它是量尺，不是探针。
 */
class StimulusActivity : Activity() {

    private lateinit var root: FrameLayout
    private lateinit var roi: TextView
    private val handler = Handler(Looper.getMainLooper())

    private var intervalMs = DEFAULT_INTERVAL_MS
    private var totalCount = DEFAULT_COUNT
    private var roiPx = DEFAULT_ROI_PX
    private var warmup = DEFAULT_WARMUP

    private var seq = 0
    private var running = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        intervalMs = intent.getIntExtra("interval_ms", DEFAULT_INTERVAL_MS)
        totalCount = intent.getIntExtra("count", DEFAULT_COUNT)
        roiPx = intent.getIntExtra("roi_px", DEFAULT_ROI_PX)
        warmup = intent.getIntExtra("warmup", DEFAULT_WARMUP)

        // 屏幕常亮：翻转序列跑几十秒，息屏会让帧停发、通道 C 直接断流。
        // 这是本 Activity 自己的窗口标志，不改任何系统设置（不用 `svc power stayon`，
        // 那属于"临时设备设置"，要照原值恢复——量尺不该留下需要恢复的痕迹）。
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        root = FrameLayout(this).apply { setBackgroundColor(Color.DKGRAY) }
        roi = TextView(this).apply {
            gravity = Gravity.CENTER
            textSize = 48f
            setTextColor(Color.RED)          // 与 A/B 两个背景色都保持可辨
            setBackgroundColor(COLOR_A)
            text = "seq=0"
            // 让无障碍树里这个节点可见、有文本——通道 A 靠它。
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_YES
            contentDescription = null        // 只让 text 变化说话，不引入第二个变化源
        }
        root.addView(roi, FrameLayout.LayoutParams(roiPx, roiPx, Gravity.TOP or Gravity.START))
        setContentView(root)

        logConfig()
    }

    override fun onResume() {
        super.onResume()
        if (!running) {
            running = true
            handler.postDelayed(::flip, intervalMs.toLong())
        }
    }

    override fun onPause() {
        super.onPause()
        // 不在后台继续翻：后台窗口不出帧，继续翻只会产出对不上任何帧的孤儿翻转。
        running = false
        handler.removeCallbacksAndMessages(null)
        Log.i(TAG, "PAUSED seq=$seq")
    }

    private fun logConfig() {
        @Suppress("DEPRECATION")
        val hz = windowManager.defaultDisplay.refreshRate
        val dm = resources.displayMetrics
        // refresh_hz 一并打出：spec §7.2 第 5 项「1 帧到底是几毫秒」要的就是它，
        // 而门限按实测刷新率换算、不硬编码 33ms（spec §3.1）。
        Log.i(
            TAG,
            "CFG interval_ms=$intervalMs count=$totalCount roi_px=$roiPx warmup=$warmup " +
                "refresh_hz=$hz frame_ms=${"%.3f".format(1000.0 / hz)} " +
                "density=${dm.density} screen_px=${dm.widthPixels}x${dm.heightPixels} " +
                "boot_mono_offset_ns=${SystemClock.elapsedRealtimeNanos() - System.nanoTime()}"
        )
    }

    private fun flip() {
        if (!running) return
        seq += 1
        val color = if (seq % 2 == 1) COLOR_B else COLOR_A
        val colorName = if (seq % 2 == 1) "B" else "A"
        val isWarmup = seq <= warmup

        // 同一帧内改两样：背景色（像素）+ 文本（无障碍）。
        roi.setBackgroundColor(color)
        roi.text = "seq=$seq"

        // 请求时刻：注意这**不是**真值，真值是下面的 commit。两个都打，供分析侧
        // 分解「请求→提交」与「提交→观测」两段。
        val reqBoot = SystemClock.elapsedRealtimeNanos()
        val reqMono = System.nanoTime()

        val thisSeq = seq
        // 一次性回调：下一帧提交时触发。若某次未触发（窗口不可见等），该 seq 就没有
        // COMMIT 行——分析侧据此记 null 并计入 dropped，绝不拿 t_req 顶替（R-10）。
        root.viewTreeObserver.registerFrameCommitCallback {
            Log.i(
                TAG,
                "COMMIT seq=$thisSeq t_commit_boot_ns=${SystemClock.elapsedRealtimeNanos()} " +
                    "t_commit_mono_ns=${System.nanoTime()}"
            )
        }

        Log.i(
            TAG,
            "FLIP seq=$thisSeq color=$colorName warmup=$isWarmup " +
                "t_req_boot_ns=$reqBoot t_req_mono_ns=$reqMono"
        )

        if (seq >= totalCount) {
            running = false
            Log.i(TAG, "DONE flips=$seq warmup=$warmup")
            return
        }
        handler.postDelayed(::flip, intervalMs.toLong())
    }

    companion object {
        private const val TAG = "E1_STIM"

        // 默认间隔远大于一帧：见类注释「对齐是二义的」那段。
        private const val DEFAULT_INTERVAL_MS = 2000
        private const val DEFAULT_COUNT = 30
        private const val DEFAULT_ROI_PX = 480

        // 预热翻转：首帧要建视图树、分配缓冲、可能触发 JIT，与稳态不可比。
        // 丢弃预热轮是本仓既有纪律（D-366 冷启动协议同源），故默认丢 3 次。
        private const val DEFAULT_WARMUP = 3

        private const val COLOR_A = Color.BLACK
        private const val COLOR_B = Color.WHITE
    }
}
