package com.aneb.probe.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * [AdapterObsEntity.appLabelFor] 契约锚定：4 个已知规格 id → 友好名，**未知/null/generic → null**
 * （展示层据此缺退到 pkg——若此 helper 误返 "" 或原始 specId，UI 的 pkg 兜底会静默失效）。
 */
class AdapterObsEntityTest {

    @Test
    fun `known spec ids map to friendly labels`() {
        assertEquals("豆包", AdapterObsEntity.appLabelFor("doubao"))
        assertEquals("DeepSeek", AdapterObsEntity.appLabelFor("deepseek"))
        assertEquals("通义千问", AdapterObsEntity.appLabelFor("tongyi"))
        assertEquals("Kimi", AdapterObsEntity.appLabelFor("kimi"))
    }

    @Test
    fun `null generic and unknown fall back to null`() {
        assertNull("null → null", AdapterObsEntity.appLabelFor(null))
        assertNull("generic（specId=null 的兜底名）→ null", AdapterObsEntity.appLabelFor("generic"))
        assertNull("未知规格 → null（展示层缺退 pkg）", AdapterObsEntity.appLabelFor("unknown_spec"))
    }
}
