package com.aneb.probe.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * DB v13 迁移 SQL 存在性单测（合成子测结果落库：恢复子测 D-40 / 弱网整形对照 D-43）。
 *
 * 取舍同 [MigrationV12Test]：不引 androidTest 基建，JVM 层锚定迁移合同——版本号 12→13、
 * additive-only（只新建 synthetic_result 表，不触碰既有表＝v12 旧数据存活）、指标列全部
 * 可空无默认值（R-10：Sample 的 null 原样落库，禁 0/哨兵值）。
 */
class MigrationV13Test {

    @Test
    fun migrationVersionsAre12To13() {
        assertEquals(12, AnebDatabase.MIGRATION_12_13.startVersion)
        assertEquals(13, AnebDatabase.MIGRATION_12_13.endVersion)
    }

    @Test
    fun onlyCreatesNewSyntheticResultTable() {
        assertEquals(1, AnebDatabase.MIGRATION_12_13_SQL.size)
        AnebDatabase.MIGRATION_12_13_SQL.forEach { sql ->
            assertTrue(
                "非新建 synthetic_result 表语句: $sql",
                sql.startsWith("CREATE TABLE IF NOT EXISTS `synthetic_result` ("),
            )
            // additive-only：无任何破坏性语句 → v12 旧数据（voice_result 及之前全部表）存活
            val upper = sql.uppercase()
            assertTrue(
                "破坏性语句: $sql",
                !upper.contains("DROP TABLE") && !upper.contains("DROP COLUMN") &&
                    !upper.contains("DELETE FROM") && !upper.contains("ALTER TABLE"),
            )
        }
    }

    @Test
    fun createStatementContainsAllColumns() {
        val sql = AnebDatabase.MIGRATION_12_13_SQL.single()
        // 全列比对（Entities.kt SyntheticResultEntity 字段序）：缺列＝迁移后 Room
        // 逐列校验 fail-fast（升级即崩），在 JVM 层先行锚定。
        listOf(
            "`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL",
            "`tsEpochMs` INTEGER NOT NULL",
            "`kind` TEXT NOT NULL",
            "`confidence` TEXT NOT NULL",
            "`recoveryMs` REAL",
            "`outage503` INTEGER",
            "`postSuccess` INTEGER",
            "`postTotal` INTEGER",
            "`rttP95Ms` REAL",
            "`meetsTargets` INTEGER",
            "`shapedDownMbps` REAL",
            "`shapedUpMbps` REAL",
            "`shapedRttMs` REAL",
        ).forEach { col ->
            assertTrue("缺少列定义: $col", sql.contains(col))
        }
    }

    @Test
    fun metricColumnsAreNullableWithoutDefaults() {
        val sql = AnebDatabase.MIGRATION_12_13_SQL.single()
        // NOT NULL 只允许出现在 id / tsEpochMs / kind / confidence 四个非指标列上；
        // 指标列（recovery/shaped 两组）一律可空（R-10），且全表无 DEFAULT。
        assertEquals(
            "NOT NULL 只允许 4 处（id/tsEpochMs/kind/confidence）",
            4,
            Regex("NOT NULL").findAll(sql).count(),
        )
        assertTrue("新列不得带默认值: $sql", !sql.uppercase().contains("DEFAULT"))
    }
}
