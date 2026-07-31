package com.aneb.probe.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * DB v16 迁移 SQL 存在性单测（radio_ctx 接线，D-367：scenario_result 加 radio* 八列）。
 *
 * 取舍同 [MigrationV15Test]：不引 androidTest 基建，JVM 层锚定迁移合同——版本号 15→16、
 * **additive-only**（仅 ALTER TABLE ADD COLUMN，无 DROP/DELETE＝v15 旧数据存活）、新列全部
 * 可空无默认（R-10：不可得 null 原样落库，禁 0/哨兵）。列名/affinity 与
 * Entities.kt ScenarioResultEntity 末尾八字段一一对应。
 */
class MigrationV16Test {

    private val expected = mapOf(
        "radioRat" to "TEXT",
        "radioRsrpDbm" to "REAL",
        "radioSinrDb" to "REAL",
        "radioPci" to "INTEGER",
        "radioTac" to "INTEGER",
        "radioArfcn" to "INTEGER",
        "radioSampledN" to "INTEGER",
        "radioStale" to "INTEGER",
    )

    @Test
    fun migrationVersionsAre15To16() {
        assertEquals(15, AnebDatabase.MIGRATION_15_16.startVersion)
        assertEquals(16, AnebDatabase.MIGRATION_15_16.endVersion)
    }

    @Test
    fun addsExactlyTheEightRadioColumnsAdditively() {
        assertEquals(expected.size, AnebDatabase.MIGRATION_15_16_SQL.size)
        for ((column, affinity) in expected) {
            val stmt = AnebDatabase.MIGRATION_15_16_SQL.singleOrNull {
                it.startsWith("ALTER TABLE `scenario_result` ADD COLUMN `$column`")
            }
            assertTrue("缺列或表名错: $column", stmt != null)
            assertTrue(
                "[$column] affinity 应为 $affinity: $stmt",
                stmt!!.uppercase().endsWith("`${column.uppercase()}` $affinity"),
            )
        }
        for (sql in AnebDatabase.MIGRATION_15_16_SQL) {
            val upper = sql.uppercase()
            assertTrue(
                "破坏性语句: $sql",
                !upper.contains("DROP TABLE") && !upper.contains("DROP COLUMN") &&
                    !upper.contains("DELETE FROM"),
            )
            assertTrue("新列不得 NOT NULL（R-10 可空）", !upper.contains("NOT NULL"))
            assertTrue("新列不得带默认值（R-10）", !upper.contains("DEFAULT"))
        }
    }
}
