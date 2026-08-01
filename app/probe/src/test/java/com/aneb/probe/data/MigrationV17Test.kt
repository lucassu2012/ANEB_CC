package com.aneb.probe.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * DB v17 迁移 SQL 存在性单测（D-373：scenario_result 加 kpiSampleCounts 列）。
 * 取舍同 [MigrationV16Test]：JVM 层锚定迁移合同——版本号 16→17、additive-only、
 * 新列可空无默认（R-10）。
 */
class MigrationV17Test {

    @Test
    fun migrationVersionsAre16To17() {
        assertEquals(16, AnebDatabase.MIGRATION_16_17.startVersion)
        assertEquals(17, AnebDatabase.MIGRATION_16_17.endVersion)
    }

    @Test
    fun onlyAddsKpiSampleCountsColumnAdditively() {
        assertEquals(1, AnebDatabase.MIGRATION_16_17_SQL.size)
        val sql = AnebDatabase.MIGRATION_16_17_SQL.single()
        assertTrue(
            "非 scenario_result 加列语句: $sql",
            sql.startsWith("ALTER TABLE `scenario_result` ADD COLUMN `kpiSampleCounts`"),
        )
        val upper = sql.uppercase()
        assertTrue("新列须 TEXT affinity", upper.endsWith("`KPISAMPLECOUNTS` TEXT"))
        assertTrue(
            "破坏性语句: $sql",
            !upper.contains("DROP TABLE") && !upper.contains("DROP COLUMN") &&
                !upper.contains("DELETE FROM"),
        )
        assertTrue("新列不得 NOT NULL（R-10 可空）", !upper.contains("NOT NULL"))
        assertTrue("新列不得带默认值（R-10）", !upper.contains("DEFAULT"))
    }
}
