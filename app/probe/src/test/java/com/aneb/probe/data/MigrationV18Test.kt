package com.aneb.probe.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * DB v18 迁移 SQL 存在性单测（D-390 §5 B′：voice_result 加 M7 两列）。
 * 取舍同 [MigrationV17Test]：JVM 层锚定迁移合同——版本号 17→18、additive-only、
 * 新列可空无默认（R-10）。
 */
class MigrationV18Test {

    @Test
    fun migrationVersionsAre17To18() {
        assertEquals(17, AnebDatabase.MIGRATION_17_18.startVersion)
        assertEquals(18, AnebDatabase.MIGRATION_17_18.endVersion)
    }

    @Test
    fun onlyAddsTheTwoM7ColumnsAdditively() {
        assertEquals(2, AnebDatabase.MIGRATION_17_18_SQL.size)
        val expected = listOf("m7MaxFrameGapMs", "voiceNearZeroArrivalRatio")
        AnebDatabase.MIGRATION_17_18_SQL.forEachIndexed { i, sql ->
            assertTrue(
                "非 voice_result 加列语句: $sql",
                sql.startsWith("ALTER TABLE `voice_result` ADD COLUMN `${expected[i]}`"),
            )
            val upper = sql.uppercase()
            // 两列都是 Double? → REAL；写死 affinity 是为了让「Kotlin 侧改了类型而 SQL 没改」
            // 这种分叉当场红，而不是等 Room 在真机启动时 fail-fast。
            assertTrue("新列须 REAL affinity: $sql", upper.endsWith(" REAL"))
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
     * 对不上是**真机启动时**才 fail-fast，而那时候设备已经在现场了。
     *
     * 这条不是形式主义：v18 两列的名字同时出现在迁移 SQL、实体、以及（将来）
     * 分析层的读取处，正是 §2.14「同一个东西写在几处就必须有东西逼它们一致」
     * 点名的形状。
     */
    @Test
    fun migrationColumnNamesMatchTheEntityFieldNames() {
        val fields = VoiceResultEntity::class.java.declaredFields.map { it.name }.toSet()
        AnebDatabase.MIGRATION_17_18_SQL.forEach { sql ->
            val col = Regex("ADD COLUMN `([^`]+)`").find(sql)?.groupValues?.get(1)
            assertTrue("从 SQL 取不到列名: $sql", col != null)
            assertTrue(
                "迁移列 `$col` 在 VoiceResultEntity 里没有同名字段——Room 会在真机启动时才报",
                fields.contains(col),
            )
        }
    }
}
