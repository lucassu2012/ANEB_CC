package com.aneb.probe.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * DB v14 迁移 SQL 存在性单测（Profile 3 观察数据落库：无障碍观察会话快照）。
 *
 * 取舍同 [MigrationV13Test]：不引 androidTest 基建，JVM 层锚定迁移合同——版本号 13→14、
 * additive-only（只新建 adapter_obs 表，不触碰既有表＝v13 旧数据存活）、NOT NULL 恰 6 列
 * （id/tsEpochMs/pkg/events/ruleMatchedEvents/confidence），指标列全部可空无默认值
 * （R-10：Snapshot 的 null 原样落库，禁 0/哨兵值）。
 */
class MigrationV14Test {

    @Test
    fun migrationVersionsAre13To14() {
        assertEquals(13, AnebDatabase.MIGRATION_13_14.startVersion)
        assertEquals(14, AnebDatabase.MIGRATION_13_14.endVersion)
    }

    @Test
    fun onlyCreatesNewAdapterObsTable() {
        assertEquals(1, AnebDatabase.MIGRATION_13_14_SQL.size)
        AnebDatabase.MIGRATION_13_14_SQL.forEach { sql ->
            assertTrue(
                "非新建 adapter_obs 表语句: $sql",
                sql.startsWith("CREATE TABLE IF NOT EXISTS `adapter_obs` ("),
            )
            // additive-only：无任何破坏性语句 → v13 旧数据（synthetic_result 及之前全部表）存活
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
        val sql = AnebDatabase.MIGRATION_13_14_SQL.single()
        // 全列比对（Entities.kt AdapterObsEntity 字段序）：缺列＝迁移后 Room 逐列校验
        // fail-fast（升级即崩），在 JVM 层先行锚定。affinity：Long→INTEGER、Double→REAL、
        // String→TEXT，与 KSP 生成的期望 schema 一致。
        listOf(
            "`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL",
            "`tsEpochMs` INTEGER NOT NULL",
            "`pkg` TEXT NOT NULL",
            "`specId` TEXT",
            "`appLabel` TEXT",
            "`events` INTEGER NOT NULL",
            "`ruleMatchedEvents` INTEGER NOT NULL",
            "`firstDeltaMs` INTEGER",
            "`cadenceP50Ms` REAL",
            "`ttftClusterMs` REAL",
            "`ttftSendMs` REAL",
            "`anchorSource` TEXT",
            "`confidence` TEXT NOT NULL",
        ).forEach { col ->
            assertTrue("缺少列定义: $col", sql.contains(col))
        }
    }

    @Test
    fun notNullColumnsAreExactlySix() {
        val sql = AnebDatabase.MIGRATION_13_14_SQL.single()
        // NOT NULL 只允许出现在 id / tsEpochMs / pkg / events / ruleMatchedEvents / confidence
        // 六个非指标列上；指标列（firstDelta/cadence/ttftCluster/ttftSend/anchorSource）与
        // specId/appLabel 一律可空（R-10），且全表无 DEFAULT。
        assertEquals(
            "NOT NULL 只允许 6 处（id/tsEpochMs/pkg/events/ruleMatchedEvents/confidence）",
            6,
            Regex("NOT NULL").findAll(sql).count(),
        )
        assertTrue("新列不得带默认值: $sql", !sql.uppercase().contains("DEFAULT"))
    }
}
