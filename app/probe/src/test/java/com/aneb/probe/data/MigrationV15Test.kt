package com.aneb.probe.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * DB v15 迁移 SQL 存在性单测（spine-3 C6：adapter_obs 加 sessionSpanMs 会话跨度列）。
 *
 * 取舍同 [MigrationV14Test]：不引 androidTest 基建，JVM 层锚定迁移合同——版本号 14→15、
 * **additive-only**（仅 ALTER TABLE ADD COLUMN，无 DROP/DELETE＝v14 旧数据存活）、新列可空
 * 无默认（R-10：Snapshot 的 null 原样落库，禁 0/哨兵）。
 */
class MigrationV15Test {

    @Test
    fun migrationVersionsAre14To15() {
        assertEquals(14, AnebDatabase.MIGRATION_14_15.startVersion)
        assertEquals(15, AnebDatabase.MIGRATION_14_15.endVersion)
    }

    @Test
    fun onlyAddsSessionSpanColumnAdditively() {
        assertEquals(1, AnebDatabase.MIGRATION_14_15_SQL.size)
        val sql = AnebDatabase.MIGRATION_14_15_SQL.single()
        assertTrue(
            "非 adapter_obs 加列语句: $sql",
            sql.startsWith("ALTER TABLE `adapter_obs` ADD COLUMN `sessionSpanMs`"),
        )
        // additive-only：ADD COLUMN 不破坏；禁一切破坏性语句 → v14 旧数据全存活
        val upper = sql.uppercase()
        assertTrue(
            "破坏性语句: $sql",
            !upper.contains("DROP TABLE") && !upper.contains("DROP COLUMN") &&
                !upper.contains("DELETE FROM"),
        )
    }

    @Test
    fun newColumnIsNullableRealWithoutDefault() {
        val sql = AnebDatabase.MIGRATION_14_15_SQL.single().uppercase()
        // affinity REAL（Double），可空（无 NOT NULL），无 DEFAULT（R-10）
        assertTrue("新列须 REAL affinity", sql.contains("SESSIONSPANMS` REAL"))
        assertTrue("新列不得 NOT NULL（R-10 可空）", !sql.contains("NOT NULL"))
        assertTrue("新列不得带默认值（R-10）", !sql.contains("DEFAULT"))
    }
}
