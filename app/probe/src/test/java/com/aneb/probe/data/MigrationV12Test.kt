package com.aneb.probe.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * DB v12 迁移 SQL 存在性单测（D-42 语音结果落库）。
 *
 * 取舍同 [MigrationV11Test]：不引 androidTest 基建，JVM 层锚定迁移合同——版本号 11→12、
 * additive-only（只新建 voice_result 表，不触碰既有表）、指标列全部可空无默认值
 * （R-10：Sample 的 null 原样落库，禁 0/哨兵值）。
 */
class MigrationV12Test {

    @Test
    fun migrationVersionsAre11To12() {
        assertEquals(11, AnebDatabase.MIGRATION_11_12.startVersion)
        assertEquals(12, AnebDatabase.MIGRATION_11_12.endVersion)
    }

    @Test
    fun onlyCreatesNewVoiceResultTable() {
        assertEquals(1, AnebDatabase.MIGRATION_11_12_SQL.size)
        AnebDatabase.MIGRATION_11_12_SQL.forEach { sql ->
            assertTrue(
                "非新建 voice_result 表语句: $sql",
                sql.startsWith("CREATE TABLE IF NOT EXISTS `voice_result` ("),
            )
            val upper = sql.uppercase()
            assertTrue(
                "破坏性语句: $sql",
                !upper.contains("DROP TABLE") && !upper.contains("DROP COLUMN") &&
                    !upper.contains("DELETE FROM") && !upper.contains("ALTER TABLE"),
            )
        }
    }

    @Test
    fun createStatementContainsAllDoneMetricColumns() {
        val sql = AnebDatabase.MIGRATION_11_12_SQL.single()
        // Done 样本全指标列（Entities.kt VoiceResultEntity 字段序）：缺列＝迁移后 Room
        // 逐列校验 fail-fast（升级即崩），在 JVM 层先行锚定。
        listOf(
            "`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL",
            "`tsEpochMs` INTEGER NOT NULL",
            "`caliber` TEXT",
            "`lowConfidence` INTEGER NOT NULL",
            "`rttMs` REAL",
            "`jitterMs` REAL",
            "`upFrameJitterMs` REAL",
            "`downFrameJitterMs` REAL",
            "`mouthEarBudgetMs` REAL",
            "`framesSent` INTEGER",
            "`framesRecv` INTEGER",
            "`ttfbP50Ms` REAL",
            "`ttfbP95Ms` REAL",
            "`downNetJitterMs` REAL",
            "`mouthEarProxyMs` REAL",
            "`turnSwitchP50Ms` REAL",
            "`bargeStopMaxMs` REAL",
            "`turnsOk` INTEGER",
        ).forEach { col ->
            assertTrue("缺少列定义: $col", sql.contains(col))
        }
    }

    @Test
    fun metricColumnsAreNullableWithoutDefaults() {
        val sql = AnebDatabase.MIGRATION_11_12_SQL.single()
        // NOT NULL 只允许出现在 id / tsEpochMs / lowConfidence 三个非指标列上；
        // 指标列一律可空（R-10），且全表无 DEFAULT。
        assertEquals("NOT NULL 只允许 3 处（id/tsEpochMs/lowConfidence）", 3, Regex("NOT NULL").findAll(sql).count())
        assertTrue("新列不得带默认值: $sql", !sql.uppercase().contains("DEFAULT"))
    }
}
