package com.aneb.probe.net

import android.content.Context
import android.os.PowerManager
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf

/**
 * 测前省电/Doze 快照进 guard metadata（D-557 裁 B：标记非否决）。
 *
 * 三条不变量：
 * 1. 两键恒在（`power_save`/`device_idle`）——分析层拿到 guard_metadata 就能判断，
 *    不用先问「这个 run 采没采过电源态」；
 * 2. 键值随真实电源态翻转（不是写死的字面量）；
 * 3. **省电态不改 ok 判定、不进 reasons**——这是「标记非否决」的全部含义，
 *    也是案 C（拒测）被否决的原因：拒测=系统性删掉弱网外场（电池供电）的样本，
 *    是对分母的选择性偏倚（D-557 §3）。
 */
@RunWith(RobolectricTestRunner::class)
class NetGuardPowerMetadataTest {

    private val ctx: Context = ApplicationProvider.getApplicationContext()

    @Test
    fun powerKeysAlwaysPresentAndDefaultFalse() {
        val r = NetGuard.guardCheck(ctx)
        assertEquals("false", r.metadata["power_save"])
        assertEquals("false", r.metadata["device_idle"])
    }

    @Test
    fun powerSaveFlipsTheValueButNeverTheVerdict() {
        val pm = ctx.getSystemService(PowerManager::class.java)
        val before = NetGuard.guardCheck(ctx)
        shadowOf(pm).setIsPowerSaveMode(true)
        shadowOf(pm).setIsDeviceIdleMode(true)
        val after = NetGuard.guardCheck(ctx)

        assertEquals("true", after.metadata["power_save"])
        assertEquals("true", after.metadata["device_idle"])
        // 标记非否决：省电态不得改变拒测判定，也不得出现在 reasons 里
        assertEquals(
            "省电态不得改变 ok 判定（标记非否决，D-557 裁 B）",
            before.ok, after.ok,
        )
        assertTrue(
            "reasons 里不得出现电源相关条目（实收: ${after.reasons}）",
            after.reasons.none { it.contains("power") || it.contains("idle") || it.contains("doze") },
        )
    }
}
