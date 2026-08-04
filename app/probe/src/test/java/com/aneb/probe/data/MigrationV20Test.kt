package com.aneb.probe.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * DB v20 迁移 SQL 存在性单测（T47 批③，D-468/D-469：scenario_result 加 22 列，
 * 单流自适应窗口 goodput 探针 U3/D3）。取舍同 [MigrationV19Test]：JVM 层锚定迁移
 * 合同——版本号 19→20、additive-only、新列可空无默认（R-10）。
 */
class MigrationV20Test {

    @Test
    fun migrationVersionsAre19To20() {
        assertEquals(19, AnebDatabase.MIGRATION_19_20.startVersion)
        assertEquals(20, AnebDatabase.MIGRATION_19_20.endVersion)
    }

    @Test
    fun addsExactlyTwentyTwoColumnsAdditively() {
        assertEquals(22, AnebDatabase.MIGRATION_19_20_SQL.size)
        val expected = mapOf(
            "u3GoodputMbps" to "REAL", "u3Grade" to "TEXT",
            "u3GoodputExclSlowStartMbps" to "REAL", "u3WindowTargetMs" to "INTEGER",
            "u3WindowActualMs" to "REAL", "u3BytesTransferred" to "INTEGER",
            "u3RttRefMsPre" to "REAL", "u3RttRefMsPost" to "REAL",
            "u3RttDriftRatio" to "REAL", "u3RttDominanceRatio" to "REAL",
            "u3RttDominanceOk" to "INTEGER",
            "d3GoodputMbps" to "REAL", "d3Grade" to "TEXT",
            "d3GoodputExclSlowStartMbps" to "REAL", "d3WindowTargetMs" to "INTEGER",
            "d3WindowActualMs" to "REAL", "d3BytesTransferred" to "INTEGER",
            "d3RttRefMsPre" to "REAL", "d3RttRefMsPost" to "REAL",
            "d3RttDriftRatio" to "REAL", "d3RttDominanceRatio" to "REAL",
            "d3RttDominanceOk" to "INTEGER",
        )
        val seenCols = HashSet<String>()
        AnebDatabase.MIGRATION_19_20_SQL.forEach { sql ->
            assertTrue(
                "非 scenario_result 加列语句: $sql",
                sql.startsWith("ALTER TABLE `scenario_result` ADD COLUMN `"),
            )
            val col = Regex("ADD COLUMN `([^`]+)`").find(sql)?.groupValues?.get(1)
            assertTrue("从 SQL 取不到列名: $sql", col != null)
            seenCols.add(col!!)
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
        assertEquals("22 列一个不多一个不少全覆盖", expected.keys, seenCols)
    }

    /**
     * 迁移列名必须与实体字段名逐字一致——Room 按 @Entity 期望 schema 逐列校验，
     * 对不上是**真机启动时**才 fail-fast。同 [MigrationV19Test] 纪律。
     */
    @Test
    fun migrationColumnNamesMatchTheEntityFieldNames() {
        val fields = ScenarioResultEntity::class.java.declaredFields.map { it.name }.toSet()
        AnebDatabase.MIGRATION_19_20_SQL.forEach { sql ->
            val col = Regex("ADD COLUMN `([^`]+)`").find(sql)?.groupValues?.get(1)
            assertTrue("从 SQL 取不到列名: $sql", col != null)
            assertTrue(
                "迁移列 `$col` 在 ScenarioResultEntity 里没有同名字段——Room 会在真机启动时才报",
                fields.contains(col),
            )
        }
    }
}
