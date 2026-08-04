package com.aneb.probe.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * DB v19 迁移 SQL 存在性单测（T47 批①，D-468/D-469：scenario_result 加
 * d1GoodputMbps/d1Grade 两列，D1 半成品补齐）。取舍同 [MigrationV18Test]：
 * JVM 层锚定迁移合同——版本号 18→19、additive-only、新列可空无默认（R-10）。
 */
class MigrationV19Test {

    @Test
    fun migrationVersionsAre18To19() {
        assertEquals(18, AnebDatabase.MIGRATION_18_19.startVersion)
        assertEquals(19, AnebDatabase.MIGRATION_18_19.endVersion)
    }

    @Test
    fun onlyAddsTheTwoD1ColumnsAdditively() {
        assertEquals(2, AnebDatabase.MIGRATION_18_19_SQL.size)
        // 与 MIGRATION_17_18（两列同为 Double→REAL）不同：D1 一列 Double(REAL)、一列
        // String(TEXT)，逐列各自核对 affinity，不假设两列同型。
        val expected = mapOf("d1GoodputMbps" to "REAL", "d1Grade" to "TEXT")
        AnebDatabase.MIGRATION_18_19_SQL.forEach { sql ->
            assertTrue(
                "非 scenario_result 加列语句: $sql",
                sql.startsWith("ALTER TABLE `scenario_result` ADD COLUMN `"),
            )
            val col = Regex("ADD COLUMN `([^`]+)`").find(sql)?.groupValues?.get(1)
            assertTrue("从 SQL 取不到列名: $sql", col != null)
            val affinity = expected[col]
            assertTrue("未预期的新列名 `$col`: $sql", affinity != null)
            val upper = sql.uppercase()
            assertTrue("列 `$col` 须 $affinity affinity: $sql", upper.endsWith(" $affinity"))
            assertTrue(
                "破坏性语句: $sql",
                !upper.contains("DROP TABLE") && !upper.contains("DROP COLUMN") &&
                    !upper.contains("DELETE FROM"),
            )
            assertTrue("新列不得 NOT NULL（R-10 可空）", !upper.contains("NOT NULL"))
            assertTrue("新列不得带默认值（R-10）", !upper.contains("DEFAULT"))
        }
    }

    /**
     * 迁移列名必须与实体字段名逐字一致——Room 按 @Entity 期望 schema 逐列校验，
     * 对不上是**真机启动时**才 fail-fast。同 [MigrationV18Test] 纪律。
     */
    @Test
    fun migrationColumnNamesMatchTheEntityFieldNames() {
        val fields = ScenarioResultEntity::class.java.declaredFields.map { it.name }.toSet()
        AnebDatabase.MIGRATION_18_19_SQL.forEach { sql ->
            val col = Regex("ADD COLUMN `([^`]+)`").find(sql)?.groupValues?.get(1)
            assertTrue("从 SQL 取不到列名: $sql", col != null)
            assertTrue(
                "迁移列 `$col` 在 ScenarioResultEntity 里没有同名字段——Room 会在真机启动时才报",
                fields.contains(col),
            )
        }
    }
}
